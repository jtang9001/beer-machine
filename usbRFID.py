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
import config

THROTTLE_TICK = 0.01

#output to pin that dispenses beer
BEER_PIN = 5
GPIO.setmode(GPIO.BCM)
GPIO.setup(BEER_PIN, GPIO.OUT, initial = GPIO.HIGH)

# factory = rpi_gpio.KeypadFactory()
# keypad = factory.create_keypad(keypad=config.KEYPAD, row_pins=config.ROW_PINS, col_pins=config.COL_PINS)

LAST_KEY = None
def printKey(key):
    global LAST_KEY
    #print("Keypad event:", key)
    LAST_KEY = key

# printKey will be called each time a keypad button is pressed
# keypad.registerKeyPressHandler(printKey)

ser = serial.Serial(
    port = "/dev/ttyS0",
    baudrate = 9600,
    timeout = 1.0
)

disp = LCD(
    # ModifiedCharLCD(
    #     pin_rs=25, pin_rw=None, pin_e=24, 
    #     pins_data=[23, 17, 18, 22],
    #     numbering_mode=GPIO.BCM, 
    #     rows = 2, cols = 16
    # )
    ModifiedSparkfunLCD(ser)
)

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

cardQueue = InputsQueue(maxlen = 10, timeout = 0.5)
keyQueue = InputsQueue(maxlen = 3, timeout = 8)

def searchForDevice(devName):
    devices = [evdev.InputDevice(path) for path in evdev.list_devices()]
    for device in devices:
        if device.name == devName:
            return device

def initRfid():
    global rfidReader
    if config.RFID_DEV_NAME != "":
        try:
            rfidReader = searchForDevice(config.RFID_DEV_NAME)
            print(rfidReader)
            rfidReader.grab()
        except OSError:
            print("OS Error in initRFID")
            rfidReader = None
    else:
        rfidReader = None

def initNumpad():
    global numpad
    if config.NUMPAD_DEV_NAME != "":
        try:
            numpad = searchForDevice(config.NUMPAD_DEV_NAME)
            print(numpad)
            numpad.grab()
        except OSError:
            print("OS Error in initNumpad")
            numpad = None
    else:
        numpad = None

initRfid()
initNumpad()
toggleTime = time()
toggle = True

def capturePIN():
    pinQueue = InputsQueue(maxlen=6, timeout=5)
    startTime = time()
    while time() - startTime <= 20:
        sleep(THROTTLE_TICK)
        disp.tickToggleLine(0)
        promptPIN(pinQueue, "PIN")
        try:
            pin = handleUSBNumpad(pinQueue)
        except EmptyInputException:
            print("Cancelled")
            disp.holdPrint("Cancelled")
            return

        if pin is not None:
            disp.writeLine(1, "Enter PIN>******")
            return pin
    print("Capture PIN timed out")
    disp.holdPrint("PIN Timeout")
        
def dispenseBeer(balance):
    print("Dispensing beer")
    disp.writeLine(0, "Dispensing beer")
    disp.writeLine(1, f"New bal: ${balance}")
    GPIO.output(BEER_PIN, GPIO.LOW)
    sleep(0.1)
    GPIO.output(BEER_PIN, GPIO.HIGH)
    sleep(1.4)

def confirmCompass(cardID, name, bal):
    global LAST_KEY
    print(f"${bal} {config.SPKEY1} to stop")
    print(f"{config.SPKEY2} to dispense")
    disp.setToggleLine(0, [name, f"Bal: ${bal}"])
    disp.setToggleLine(1, [f"{config.SPKEY2} to dispense", f"{config.SPKEY1} to stop"])

    startTime = time()
    while time() - startTime <= 15:
        sleep(THROTTLE_TICK)
        disp.tickToggleLines()
        if LAST_KEY == config.SPKEY2:
            LAST_KEY = None
            r = requests.post(
                "https://thetaspd.pythonanywhere.com/beer/pay_compass/", 
                data = { "compassID": cardID, "machine": config.MACHINE_KEY }
            )
            try:
                reply = r.json()
                print(reply)
                if "error" in reply:
                    print(reply["error"])
                    disp.holdPrint(reply["error"])
                elif reply["dispense"]:
                    dispenseBeer(reply["balance"])
                else:
                    print("Unknown error")
                    disp.holdPrint("Unknown error")
            except Exception:
                print(r.text)
                raise
            return
        elif LAST_KEY == config.SPKEY1:
            LAST_KEY = None
            print("Beer cancelled")
            disp.holdPrint("Cancelled")
            return
    print("Compass confirmation timed out.")
    disp.holdPrint("Card timeout")
        
def handleRFID(cardQueue):
    global rfidReader
    if rfidReader is None:
        initRfid()
        return
    try:
        for event in rfidReader.read():
            if event.type == evdev.ecodes.EV_KEY:
                data = evdev.categorize(event)
                if data.keystate == 1:
                    cardQueue.add(data.keycode[-1]) # last character is one of interest
    except BlockingIOError:
        return cardQueue.churn()
    except OSError:
        print("RFID input error. Reinitializing")
        initRfid()
        return

def handleUSBNumpad(queue):
    global numpad
    if numpad is None:
        initNumpad()
        return
    try:
        for event in numpad.read():
            if event.type == evdev.ecodes.EV_KEY:
                data = evdev.categorize(event)
                if data.keystate == 1:
                    queue.add(data.keycode[-1]) # last character is one of interest
    except BlockingIOError:
        return queue.churn()
    except OSError:
        print("Numpad input error. Reinitializing")
        initNumpad()
        return

def handleKeypad(queue):
    global LAST_KEY
    if LAST_KEY is not None:
        if LAST_KEY == config.SPKEY1:
            if queue.getLen() == 0:
                LAST_KEY = None
                raise EmptyInputException
            else:
                queue.clear()
        else:
            queue.add(LAST_KEY)
        LAST_KEY = None
    return queue.churn()

def prompt(queue: InputsQueue, name, line = 1):
    currentInput = f"Enter {name}>{queue.peek()}"
    disp.writeLine(line, currentInput)
    
def promptPIN(queue: InputsQueue, name, line = 1):
    currentInput = f"Enter {name}>{'*' * queue.getLen()}"
    disp.writeLine(line, currentInput)

def starmode(keyID, name):
    global LAST_KEY
    disp.setToggleLine(0, ["* Star mode *", f"from {name}"])
    disp.setToggleLine(1, [f"{config.SPKEY1} to dispense", f"{config.SPKEY2} to exit"])
    hasBal = True
    while hasBal:
        sleep(THROTTLE_TICK)
        disp.tickToggleLines()
        if LAST_KEY == config.SPKEY1:
            LAST_KEY = None
            r = requests.post(
                "https://thetaspd.pythonanywhere.com/beer/pay_star/", 
                data = { "keyID": keyID, "machine": config.MACHINE_KEY }
            )
            try:
                reply = r.json()
                print(reply)
                if "error" in reply:
                    print(reply["error"])
                    disp.holdPrint(reply["error"])
                    return
                elif reply["dispense"]:
                    dispenseBeer(reply["star_mode_balance"])
                    hasBal = reply["can_dispense_more"]
                    disp.setToggleLine(0, ["* Star mode *", f"by {name}", f"Bal: ${reply['star_mode_balance']}"])
                else:
                    print("Unknown error")
                    disp.holdPrint("Unknown error")
                    return
            except Exception:
                print(r.text)
                raise
        elif LAST_KEY == config.SPKEY2:
            LAST_KEY = None
            print("Star mode cancelled")
            disp.holdPrint("Starmode over :(")
            return

def preauthCompass(compassID):
    print("Querying balance for", compassID)
    startTime = time()
    disp.writeLine(0, "Pinging server")
    disp.writeLine(1, f"RFID {compassID}")
    r = requests.post(
        "https://thetaspd.pythonanywhere.com/beer/query_compass/", 
        data = { "compassID": compassID, "machine": config.MACHINE_KEY }
    )
    while time() - startTime < 1:
        #spin to allow enough time to look at RFID number
        pass
    try:
        reply = r.json()
        print(reply)
        if "error" in reply:
            disp.holdPrint(reply["error"])
        elif reply["can_star_mode"]:
            starmode(reply["keyID"], reply["name"])
        elif reply["can_dispense"]:
            confirmCompass(compassID, reply["name"], reply["balance"])
        else:
            disp.holdPrint("Low bal for thismachine")
    except json.decoder.JSONDecodeError:
        print("JSON error!")
        print(r.text)
    except Exception:
        print("Error state!")
        raise
    cardID = None

def preauthKeyID(keyID):
    disp.writeLine(0, "Pinging server")
    disp.writeLine(1, f"Enter ID>{keyID}")
    print("Querying balance for", keyID)

    r = requests.post(
        "https://thetaspd.pythonanywhere.com/beer/query_keyID/", 
        data = { "keyID": keyID, "machine": config.MACHINE_KEY }
    )

    try:
        reply = r.json()
        print(reply)
        if "error" in reply:
            disp.holdPrint(reply["error"])
        elif reply["can_star_mode"]:
            starmode(reply["keyID"], reply["name"])
        elif reply["can_dispense"]:
            disp.setToggleLine(0, [reply["name"], f"Bal: ${reply['balance']}"])
            pin = capturePIN()
            if pin is not None:
                confirmPIN(keyID, pin)
        else:
            print("Insufficient funds")
            disp.holdPrint("Low bal for thismachine")
    except json.decoder.JSONDecodeError:
        print("JSON error!")
        print(r.text)
    except Exception:
        print("Error state!")
        raise

def confirmPIN(keyID, pin):
    print("Authorizing payment balance for", keyID)
    r = requests.post(
        "https://thetaspd.pythonanywhere.com/beer/pay_pin/", 
        data = { "pin": pin, "keyID": keyID, "machine": config.MACHINE_KEY }
    )
    try:
        reply = r.json()
        print(reply)
        if "error" in reply:
            disp.holdPrint(reply["error"])
        elif reply["dispense"]:
            dispenseBeer(reply["balance"])
        else:
            print("Unknown error")
            disp.holdPrint("Unknown error")
    except json.decoder.JSONDecodeError:
        print("JSON error!")
        print(r.text)
    except Exception:
        print("Error state!")
        raise


try:
    while True:
        sleep(THROTTLE_TICK)
        #Scan for card
        cardID = handleRFID(cardQueue)
        try:
            keyID = handleUSBNumpad(keyQueue)
        except EmptyInputException:
            pass
        
        if cardID is not None:
            preauthCompass(cardID)
            cardID = None
            cardQueue.clear()
            keyQueue.clear()
        
        elif keyID is not None:
            preauthKeyID(keyID)
            keyID = None
            cardQueue.clear()
            keyQueue.clear()
        
        else:
            disp.setToggleScreens(
                [f"SPD Beer-O-Matic{config.MACHINE_NAME}", 
                "Tap Compass Cardor enter ID>",
                "spd.jtang.ca    /beer for more"]
            )
            if keyQueue.getLen() == 0:
                disp.tickToggleScreens()
            else:
                disp.setToggleLine(0, ["SPD Beer-O-Matic", config.MACHINE_NAME])
                disp.tickToggleLine(0)
                prompt(keyQueue, "ID")

except KeyboardInterrupt:
    print("Caught Ctrl-C")
finally:
    print("Shutting down")
    if rfidReader is not None:
        rfidReader.ungrab()
    disp.shutdown()
    GPIO.cleanup()