#Builtin imports
from collections import deque
from time import sleep, time
import json

#Library imports
import evdev
import requests
import RPi.GPIO as GPIO
from pad4pi import rpi_gpio
import serial

from customLCD import *
from config import *

GPIO.setmode(GPIO.BCM)
GPIO.setup(BEER_PIN, GPIO.OUT, initial = GPIO.HIGH)


class InputsQueue:
    def __init__(self, maxlen, timeout):
        self.queue = deque(maxlen=maxlen)
        self.timeout = timeout
        self.lastEditTime = time()
    
    def add(self, item):
        self.lastEditTime = time()
        self.queue.append(item)
    
    def clear(self):
        self.lastEditTime = time()
        self.queue.clear()
        
    def churn(self):
        now = time()
        if now - self.lastEditTime >= self.timeout:
            self.queue.clear()
        elif len(self.queue) == self.queue.maxlen:
            return self.harvest()

    def harvest(self):
        contents = "".join(self.queue)
        self.queue.clear()
        return contents

    def peek(self):
        contents = "".join(self.queue)
        return contents

    def getLen(self):
        return len(self.queue)

class EmptyInputException(Exception):
    pass

def searchForDevice(devName):
    devices = [evdev.InputDevice(path) for path in evdev.list_devices()]
    for device in devices:
        if device.name == devName:
            return device

class BeerMachine:
    def __init__(self):
        self.lastKey = None
        factory = rpi_gpio.KeypadFactory()
        self.keypad = factory.create_keypad(keypad=KEYPAD, row_pins=ROW_PINS, col_pins=COL_PINS)
        self.keypad.registerKeyPressHandler(self.printKey)

        self.ser = serial.Serial(
            port = "/dev/ttyS0",
            baudrate = 9600,
            timeout = 1.0
        )

        self.disp = LCD(
            # ModifiedCharLCD(
            #     pin_rs=25, pin_rw=None, pin_e=24, 
            #     pins_data=[23, 17, 18, 22],
            #     numbering_mode=GPIO.BCM, 
            #     rows = 2, cols = 16
            # )
            ModifiedSparkfunLCD(self.ser)
        )

        self.cardQueue = InputsQueue(maxlen = 10, timeout = 0.5)
        self.keyQueue = InputsQueue(maxlen = 3, timeout = 8)

        self.rfidReader = None
        self.initRfid()

        self.toggleTime = time()
        self.toggle = True

    def initRfid(self):
        try:
            self.rfidReader.ungrab()
        except Exception:
            pass

        if RFID_DEV_NAME != "":
            try:
                self.rfidReader = searchForDevice(RFID_DEV_NAME)
                print(self.rfidReader)
                self.rfidReader.grab()
            except OSError:
                print("OS Error in initRFID")
                self.rfidReader = None
        else:
            self.rfidReader = None

    def printKey(self, key):
        #print("Keypad event:", key)
        self.lastKey = key

    def dispenseBeer(self, balance):
        print("Dispensing beer")
        self.disp.writeLine(0, "Dispensing beer")
        self.disp.writeLine(1, f"New bal: ${balance}")
        GPIO.output(BEER_PIN, GPIO.LOW)
        sleep(0.5)
        GPIO.output(BEER_PIN, GPIO.HIGH)
        sleep(1.0)

    def capturePIN(self):
        pinQueue = InputsQueue(maxlen=6, timeout=5)
        startTime = time()
        while time() - startTime <= 20:
            sleep(THROTTLE_TICK)
            self.disp.tickToggleLine(0)
            self.promptPIN(pinQueue, "PIN")
            try:
                pin = self.handleKeypad(pinQueue)
            except EmptyInputException:
                print("Cancelled")
                self.disp.holdPrint("Cancelled")
                return

            if pin is not None:
                self.disp.writeLine(1, "Enter PIN>******")
                return pin
        print("Capture PIN timed out")
        self.disp.holdPrint("PIN Timeout")

    def promptPIN(self, queue: InputsQueue, name, line = 1):
        currentInput = f"Enter {name}>{'*' * queue.getLen()}"
        self.disp.writeLine(line, currentInput)

    def prompt(self, queue: InputsQueue, name, line = 1):
        currentInput = f"Enter {name}>{queue.peek()}"
        self.disp.writeLine(line, currentInput)

    def handleKeypad(self, queue):
        if self.lastKey is not None:
            if self.lastKey == SPKEY1:
                if queue.getLen() == 0:
                    self.lastKey = None
                    raise EmptyInputException
                else:
                    queue.clear()
            else:
                queue.add(self.lastKey)
            self.lastKey = None
        return queue.churn()

    def handleRFID(self, cardQueue):
        if self.rfidReader is None:
            self.initRfid()
            return
        try:
            for event in self.rfidReader.read():
                if event.type == evdev.ecodes.EV_KEY:
                    data = evdev.categorize(event)
                    if data.keystate == 1:
                        cardQueue.add(data.keycode[-1]) # last character is one of interest
        except BlockingIOError:
            return cardQueue.churn()
        except OSError:
            print("RFID input error. Reinitializing")
            self.initRfid()
            return

    def preauthCompass(self, compassID):
        print("Querying balance for", compassID)
        startTime = time()
        self.disp.writeLine(0, "Pinging server")
        self.disp.writeLine(1, f"RFID {compassID}")
        r = requests.post(
            "https://thetaspd.pythonanywhere.com/beer/query_compass/", 
            data = { "compassID": compassID, "machine": MACHINE_KEY }
        )
        while time() - startTime < 1:
            #spin to allow enough time to look at RFID number
            pass
        try:
            reply = r.json()
            print(reply)
            if "error" in reply:
                self.disp.holdPrint(reply["error"])
            elif reply["can_star_mode"]:
                self.starmode(reply["keyID"], reply["name"])
            elif reply["can_dispense"]:
                self.confirmCompass(compassID, reply["name"], reply["balance"])
            else:
                self.disp.holdPrint("Low bal for thismachine")
        except json.decoder.JSONDecodeError:
            print("JSON error!")
            print(r.text)
        except Exception:
            print("Error state!")
            raise
        cardID = None

    def preauthKeyID(self, keyID):
        self.disp.writeLine(0, "Pinging server")
        self.disp.writeLine(1, f"Enter ID>{keyID}")
        print("Querying balance for", keyID)

        r = requests.post(
            "https://thetaspd.pythonanywhere.com/beer/query_keyID/", 
            data = { "keyID": keyID, "machine": MACHINE_KEY }
        )

        try:
            reply = r.json()
            print(reply)
            if "error" in reply:
                self.disp.holdPrint(reply["error"])
            elif reply["can_star_mode"]:
                self.starmode(reply["keyID"], reply["name"])
            elif reply["can_dispense"]:
                self.disp.setToggleLine(0, [reply["name"], f"Bal: ${reply['balance']}"])
                pin = self.capturePIN()
                if pin is not None:
                    self.confirmPIN(keyID, pin)
            else:
                print("Insufficient funds")
                self.disp.holdPrint("Low bal for thismachine")
        except json.decoder.JSONDecodeError:
            print("JSON error!")
            print(r.text)
        except Exception:
            print("Error state!")
            raise

    def confirmPIN(self, keyID, pin):
        print("Authorizing payment balance for", keyID)
        r = requests.post(
            "https://thetaspd.pythonanywhere.com/beer/pay_pin/", 
            data = { "pin": pin, "keyID": keyID, "machine": MACHINE_KEY }
        )
        try:
            reply = r.json()
            print(reply)
            if "error" in reply:
                self.disp.holdPrint(reply["error"])
            elif reply["dispense"]:
                self.dispenseBeer(reply["balance"])
            else:
                print("Unknown error")
                self.disp.holdPrint("Unknown error")
        except json.decoder.JSONDecodeError:
            print("JSON error!")
            print(r.text)
        except Exception:
            print("Error state!")
            raise

    def confirmCompass(self, cardID, name, bal):
        print(f"${bal} {SPKEY1} to stop")
        print(f"{SPKEY2} to dispense")
        self.disp.setToggleLine(0, [name, f"Bal: ${bal}"])
        self.disp.setToggleLine(1, [f"{SPKEY2} to dispense", f"{SPKEY1} to stop"])

        startTime = time()
        while time() - startTime <= 15:
            sleep(THROTTLE_TICK)
            self.disp.tickToggleLines()

            if self.lastKey == SPKEY2:
                self.lastKey = None
                r = requests.post(
                    "https://thetaspd.pythonanywhere.com/beer/pay_compass/", 
                    data = { "compassID": cardID, "machine": MACHINE_KEY }
                )
                try:
                    reply = r.json()
                    print(reply)
                    if "error" in reply:
                        print(reply["error"])
                        self.disp.holdPrint(reply["error"])
                    elif reply["dispense"]:
                        self.dispenseBeer(reply["balance"])
                    else:
                        print("Unknown error")
                        self.disp.holdPrint("Unknown error")
                except Exception:
                    print(r.text)
                    raise
                return
            elif self.lastKey == SPKEY1:
                self.lastKey = None
                print("Beer cancelled")
                self.disp.holdPrint("Cancelled")
                return
            else:
                self.lastKey = None
        print("Compass confirmation timed out.")
        self.disp.holdPrint("Card timeout")

    def starmode(self, keyID, name):
        self.disp.setToggleLine(0, ["* Star mode *", f"from {name}"])
        self.disp.setToggleLine(1, [f"{SPKEY1} to dispense", f"{SPKEY2} to exit"])
        hasBal = True
        while hasBal:
            sleep(THROTTLE_TICK)
            self.disp.tickToggleLines()

            if self.lastKey == SPKEY1:
                self.lastKey = None
                r = requests.post(
                    "https://thetaspd.pythonanywhere.com/beer/pay_star/", 
                    data = { "keyID": keyID, "machine": MACHINE_KEY }
                )
                try:
                    reply = r.json()
                    print(reply)
                    if "error" in reply:
                        print(reply["error"])
                        self.disp.holdPrint(reply["error"])
                        return
                    elif reply["dispense"]:
                        self.dispenseBeer(reply["star_mode_balance"])
                        hasBal = reply["can_dispense_more"]
                        self.disp.setToggleLine(0, ["* Star mode *", f"by {name}", f"Bal: ${reply['star_mode_balance']}"])
                    else:
                        print("Unknown error")
                        self.disp.holdPrint("Unknown error")
                        return
                except Exception:
                    print(r.text)
                    raise
            elif self.lastKey == SPKEY2:
                self.lastKey = None
                print("Star mode cancelled")
                self.disp.holdPrint("Starmode over :(")
                return
            else:
                self.lastKey = None

    def loop(self):
        try:
            while True:
                sleep(THROTTLE_TICK)
                #Scan for card
                cardID = self.handleRFID(self.cardQueue)
                try:
                    keyID = self.handleKeypad(self.keyQueue)
                except EmptyInputException:
                    pass
                
                if cardID is not None:
                    self.preauthCompass(cardID)
                    cardID = None
                    self.cardQueue.clear()
                    self.keyQueue.clear()
                
                elif keyID is not None:
                    self.preauthKeyID(keyID)
                    keyID = None
                    self.cardQueue.clear()
                    self.keyQueue.clear()
                
                else:
                    self.disp.setToggleScreens(
                        [f"SPD Beer-O-Matic{MACHINE_NAME}", 
                        "Tap Compass Cardor enter ID>",
                        "spd.jtang.ca    /beer for more"]
                    )
                    if self.keyQueue.getLen() == 0:
                        self.disp.tickToggleScreens()
                    else:
                        self.disp.setToggleLine(0, ["SPD Beer-O-Matic", MACHINE_NAME])
                        self.disp.tickToggleLine(0)
                        self.prompt(self.keyQueue, "ID")

        except KeyboardInterrupt:
            print("Caught Ctrl-C")
        finally:
            print("Shutting down")
            if self.rfidReader is not None:
                self.rfidReader.ungrab()
            self.disp.shutdown()
            GPIO.cleanup()

    

