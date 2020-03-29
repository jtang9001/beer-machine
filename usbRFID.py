#Builtin imports
from collections import deque
from time import sleep, time
import json

#Library imports
import evdev
import requests
import RPi.GPIO as GPIO
from pad4pi import rpi_gpio
from RPLCD.gpio import CharLCD

#Price of a beer
COST = 2.50

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

#LCD setup
class LCD:
    def __init__(self, lcd):
        self.lcd = lcd
        self.lcd.clear()
        self.lcd.home()
        self.lines = ["", ""]
        self.mainLoop()

    # def write(self):
    #     self.lcd.write_string(self.line1)
    #     self.lcd.crlf()
    #     self.lcd.write_string(self.line2)

    def mainLoop(self):
        self.clear()
        self.writeLine(0, "SPD Beer Machine")
        self.writeLine(1, "Enter ID > ")

    def clear(self):
        self.lcd.clear()
        self.lcd.home()
        self.lines = ["", ""]

    def debugPrint(self):
        print("LCD0: ", self.lines[0])
        print("LCD1: ", self.lines[1])

    def clearPrint(self, msg):
        msg = str(msg)
        self.lcd.clear()
        self.lcd.home()
        self.lcd.write_string(msg)
        self.lines[0] = msg[:16]
        self.lines[1] = msg[16:32]
        #self.debugPrint()

    def holdPrint(self, msg, delay = 3):
        self.clearPrint(msg)
        sleep(delay)

    def writeLine(self, lineNum, msg):
        msg = str(msg)
        self.lcd.cursor_pos = (lineNum, 0)
        self.lcd.write_string(msg[:16] + " " * (16 - len(msg[:16])))
        self.lines[lineNum] = msg[:16]
        #self.debugPrint()

    def appendLine(self, lineNum, msg):
        msg = str(msg)
        self.lines[lineNum] += msg
        self.lines[lineNum] = self.lines[lineNum][:16]
        self.lcd.cursor_pos = (lineNum, 0)
        self.lcd.write_string(self.lines[lineNum])
        #self.debugPrint()
            
    def shutdown(self):
        self.lcd.close(clear=True)

disp = LCD(
    CharLCD(
        pin_rs=25, pin_rw=None, pin_e=24, 
        pins_data=[23, 17, 18, 22],
        numbering_mode=GPIO.BCM, 
        rows = 2, cols = 16
    )
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

cardQueue = InputsQueue(maxlen = 10, timeout = 0.5)
keyQueue = InputsQueue(maxlen = 3, timeout = 5)

rfidReader = evdev.InputDevice('/dev/input/event0')
print(rfidReader)

toggleTime = time()
toggle = True

def capturePIN():
    pinQueue = InputsQueue(maxlen=6, timeout=5)
    startTime = time()
    while time() - startTime <= 10:
        promptPIN(pinQueue, "PIN")
        pin = handleKeypad(pinQueue)
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

def confirmCompassBeer(cardID, name, bal):
    global LAST_KEY
    print(f"${bal} * to stop")
    print("# to dispense")
    disp.writeLine(0, f"${bal} * to stop")
    disp.writeLine(1, "# to dispense")

    startTime = time()
    while time() - startTime <= 10:
        if LAST_KEY == "#":
            LAST_KEY = None
            r = requests.post(
                "https://thetaspd.pythonanywhere.com/beer/pay_compass/", 
                data = { "compassID": cardID, "cost": COST }
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
                    print("Could not authorize beer")
                    disp.holdPrint("Could not authorize beer")
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

def authorizeCompass(compassID):
    print("Querying balance for", compassID)
    disp.holdPrint(f"Compass Read OK {compassID}", delay = 1)
    r = requests.post(
        "https://thetaspd.pythonanywhere.com/beer/query_compass/", 
        data = { "compassID": compassID }
    )
    try:
        reply = r.json()
        print(reply)
        if "error" in reply:
            disp.clearPrint(reply["error"])
            sleep(3)
        else:
            confirmCompassBeer(compassID, reply["name"], reply["balance"])
    except json.decoder.JSONDecodeError:
        print("JSON error!")
        print(r.text)
    except Exception:
        print("Error state!")
        raise
    cardID = None

def authorizePIN(keypadID, pin):
    print("Querying balance for", keypadID)
    r = requests.post(
        "https://thetaspd.pythonanywhere.com/beer/pay_pin/", 
        data = { "pin": pin, "keypadID": keypadID, "cost": COST }
    )
    try:
        reply = r.json()
        print(reply)
        if "error" in reply:
            disp.clearPrint(reply["error"])
            sleep(3)
        elif reply["dispense"]:
            dispenseBeer(reply["balance"])
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
        keyID = handleKeypad(keyQueue)
        
        if cardID is not None:
            authorizeCompass(cardID)
            cardID = None
        
        elif keyID is not None:
            disp.writeLine(0, f"ID {keyID}")
            pin = capturePIN()
            if pin is not None:
                authorizePIN(keyID, pin)
            pin = None
            keyID = None
        
        else:
            currentTime = time()
            if currentTime - toggleTime > 3:
                toggleTime = currentTime
                toggle = not toggle
            disp.writeLine(0, "SPD Beer Machine" if toggle else "Tap card, or")
            prompt(keyQueue, "ID")

except KeyboardInterrupt:
    print("Caught Ctrl-C")
finally:
    print("Shutting down")
    rfidReader.ungrab()
    disp.shutdown()
    GPIO.cleanup()