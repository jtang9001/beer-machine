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

#Name of machine to send to Django
MACHINE_NAME = "Basement Left"

#output to pin that dispenses beer
BEER_PIN = 5
GPIO.setmode(GPIO.BCM)
GPIO.setup(BEER_PIN, GPIO.OUT, initial = GPIO.LOW)

#keypad setup
KEYPAD = [
    ["1", "2", "3", "A"],
    ['4', "5", "6", "B"],
    ['7', "8", "9", "C"],
    ["*", "0", "#", "D"]
]

ROW_PINS = [6, 13, 19, 26] # BCM numbering
COL_PINS = [12, 16, 20, 21] # BCM numbering

factory = rpi_gpio.KeypadFactory()
keypad = factory.create_keypad(keypad=KEYPAD, row_pins=ROW_PINS, col_pins=COL_PINS)

LAST_KEY = None
def printKey(key):
    global LAST_KEY
    #print("Keypad event:", key)
    LAST_KEY = key

# printKey will be called each time a keypad button is pressed
keypad.registerKeyPressHandler(printKey)

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
keyQueue = InputsQueue(maxlen = 3, timeout = 5)

rfidReader = evdev.InputDevice('/dev/input/event0')
print(rfidReader)

toggleTime = time()
toggle = True

def capturePIN():
    pinQueue = InputsQueue(maxlen=6, timeout=5)
    startTime = time()
    while time() - startTime <= 20:
        disp.tickToggleLine(0)
        promptPIN(pinQueue, "PIN")
        try:
            pin = handleKeypad(pinQueue)
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
    GPIO.output(BEER_PIN, GPIO.HIGH)
    sleep(1)
    GPIO.output(BEER_PIN, GPIO.LOW)

def confirmCompass(cardID, name, bal):
    global LAST_KEY
    print(f"${bal} * to stop")
    print("# to dispense")
    disp.setToggleLine(0, [name, f"Bal: ${bal}"])
    disp.setToggleLine(1, ["# to dispense", "* to stop"])

    startTime = time()
    while time() - startTime <= 15:
        disp.tickToggleLines()
        if LAST_KEY == "#":
            LAST_KEY = None
            r = requests.post(
                "https://thetaspd.pythonanywhere.com/beer/pay_compass/", 
                data = { "compassID": cardID, "machine": MACHINE_NAME }
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
        elif LAST_KEY == "*":
            LAST_KEY = None
            print("Beer cancelled with *")
            disp.holdPrint("Cancelled")
            return
    print("Compass confirmation timed out.")
    disp.holdPrint("Card timeout")
        
def handleRFID(cardQueue):
    global rfidReader
    try:
        for event in rfidReader.read():
            if event.type == evdev.ecodes.EV_KEY:
                data = evdev.categorize(event)
                if data.keystate == 1:
                    cardQueue.add(data.keycode[-1]) # last character is one of interest
    except BlockingIOError:
        return cardQueue.churn()

def handleKeypad(queue):
    global LAST_KEY
    if LAST_KEY is not None:
        if LAST_KEY == "*":
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
    disp.setToggleLine(0, ["* Star mode *", f"by {name}"])
    disp.setToggleLine(1, ["* to dispense", "# to exit"])
    hasBal = True
    while hasBal:
        disp.tickToggleLines()
        if LAST_KEY == "*":
            LAST_KEY = None
            r = requests.post(
                "https://thetaspd.pythonanywhere.com/beer/pay_star/", 
                data = { "keyID": keyID, "machine": MACHINE_NAME }
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
        elif LAST_KEY == "#":
            LAST_KEY = None
            print("Star mode cancelled with #")
            disp.holdPrint("Starmode over :(")
            return

def preauthCompass(compassID):
    print("Querying balance for", compassID)
    disp.holdPrint(f"Compass Read OK {compassID}", delay = 1)
    r = requests.post(
        "https://thetaspd.pythonanywhere.com/beer/query_compass/", 
        data = { "compassID": compassID, "machine": MACHINE_NAME }
    )
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
    print("Querying balance for", keyID)
    r = requests.post(
        "https://thetaspd.pythonanywhere.com/beer/query_keyID/", 
        data = { "keyID": keyID, "machine": MACHINE_NAME }
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
        data = { "pin": pin, "keyID": keyID, "machine": MACHINE_NAME }
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

rfidReader.grab()
try:
    while True:
        #Scan for card
        cardID = handleRFID(cardQueue)
        try:
            keyID = handleKeypad(keyQueue)
        except EmptyInputException:
            pass
        
        if cardID is not None:
            preauthCompass(cardID)
            cardID = None
        
        elif keyID is not None:
            disp.writeLine(1, f"Enter ID>{keyID}")
            preauthKeyID(keyID)
            keyID = None
        
        else:
            disp.setToggleLine(0, ["SPD Beer-O-Matic", MACHINE_NAME])
            if keyQueue.getLen() == 0:
                disp.setToggleLine(1, ["Tap Compass card", "or enter ID>"])
                disp.tickToggleLines()
            else:
                prompt(keyQueue, "ID")

except KeyboardInterrupt:
    print("Caught Ctrl-C")
finally:
    print("Shutting down")
    rfidReader.ungrab()
    disp.shutdown()
    GPIO.cleanup()