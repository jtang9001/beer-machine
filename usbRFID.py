from collections import deque
from time import sleep, time
import json

import evdev
import requests
import RPi.GPIO as GPIO
from pad4pi import rpi_gpio
from RPLCD.gpio import CharLCD

BEER_PIN = 5
GPIO.setmode(GPIO.BCM)
GPIO.setup(BEER_PIN, GPIO.OUT, initial = GPIO.LOW)

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

lcd = CharLCD(pin_rs=25, pin_rw=None, pin_e=24, pins_data=[23, 17, 18, 22],
              numbering_mode=GPIO.BCM, rows = 2, cols = 16)

lcd.clear()
lcd.write_string("SPD BEER-O-MATIC\n\rEnter ID or tap card")

POUND_FLAG = False
STAR_FLAG = False
def printKey(key):
    global POUND_FLAG, STAR_FLAG, keyQueue
    print("Keypad event:", key)
    if key == "#":
        POUND_FLAG = True
    elif key == "*":
        STAR_FLAG = True
    else:
        keyQueue.add(key)


# printKey will be called each time a keypad button is pressed
keypad.registerKeyPressHandler(printKey)

COST = 2.50

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
keyQueue = InputsQueue(maxlen = 8, timeout = 3)

cardID = None
keypadID = ""
oldKeypadID = ""

rfidReader = evdev.InputDevice('/dev/input/event0')
print(rfidReader)

def capturePIN():
    global POUND_FLAG, STAR_FLAG, keyQueue
    startTime = time()
    keyQueue.clear()
    print("Enter PIN: ")
    oldpin = ""
    lcd.cursor_pos = (1,0)
    lcd.write_string("PIN:")
    while time() - startTime <= 10:
        if POUND_FLAG:
            POUND_FLAG = False
            print("Pound detected. PW done")
            return keyQueue.harvest()
        elif STAR_FLAG:
            print("Star detected. Exiting")
            return
        keyQueue.churn()
        pin = keyQueue.peek()
        if pin != oldpin:
            print("Enter PIN: " + "*" * keyQueue.getLen())
            lcd.cursor_pos = (1,0)
            lcd.write_string("PIN: " + "*" * keyQueue.getLen())
            oldpin = pin
    keyQueue.clear()
    print("Capture PIN timed out")
    lcd.clear()
    lcd.home()
    lcd.write_string("PIN Timeout")
    sleep(1)
        

def dispenseBeer():
    print("Dispensing beer")
    lcd.clear()
    lcd.home()
    lcd.write_string("Dispensing beer")
    GPIO.output(BEER_PIN, GPIO.HIGH)
    sleep(1)
    GPIO.output(BEER_PIN, GPIO.LOW)

def confirmCompassBeer(cardID, name, bal):
    global POUND_FLAG, STAR_FLAG
    print(f"{name}, ${bal}")
    print("# to dispense, * to cancel")
    startTime = time()
    while time() - startTime <= 5:
        if POUND_FLAG:
            POUND_FLAG = False
            r = requests.post(
                "https://thetaspd.pythonanywhere.com/beer/pay_compass/", 
                data = { "compassID": cardID, "cost": COST }
            )
            try:
                reply = r.json()
                print(reply)
                if "error" in reply:
                    print(reply["error"])
                elif reply["dispense"]:
                    dispenseBeer()
                else:
                    print("Could not authorize beer")
            except Exception:
                print(r.text)
                raise
            return

        elif STAR_FLAG:
            print("Beer cancelled with *")
            STAR_FLAG = False
            return
    print("Compass confirmation timed out.")
        
rfidReader.grab()
try:
    while True:
        #Scan for card
        try:
            for event in rfidReader.read():
                if event.type == evdev.ecodes.EV_KEY:
                    data = evdev.categorize(event)
                    if data.keystate == 1:
                        cardQueue.add(data.keycode[-1]) # last character is one of interest
        except BlockingIOError:
            cardID = cardQueue.churn()
            sleep(0.1)
        
        if cardID is not None:
            print("Querying balance for", cardID)
            lcd.write_string(cardID)
            lcd.crlf()
            r = requests.post(
                "https://thetaspd.pythonanywhere.com/beer/query_compass/", 
                data = { "compassID": cardID }
            )
            try:
                reply = r.json()
                print(reply)
                if "error" in reply:
                    print(reply["error"])
                    lcd.write_string(reply["error"])
                    lcd.crlf()
                else:
                    confirmCompassBeer(cardID, reply["name"], reply["balance"])
            except json.decoder.JSONDecodeError:
                print("JSON error!")
                print(r.text)
            except Exception:
                print("Error state!")
                raise
            cardID = None
        
        keyQueue.churn()
        keypadID = keyQueue.peek()
        if keypadID != oldKeypadID:
            print("Enter ID:", keypadID)
            lcd.home()
            lcd.write_string(cardID)
            oldKeypadID = keypadID
            
        elif POUND_FLAG:
            POUND_FLAG = False
            pin = capturePIN()
            if pin is not None:
                print("Querying balance for", keypadID)
                r = requests.post(
                    "https://thetaspd.pythonanywhere.com/beer/pay_pin/", 
                    data = { "pin": pin, "keypadID": keypadID, "cost": COST }
                )
                try:
                    reply = r.json()
                    print(reply)
                    if "error" in reply:
                        print(reply["error"])
                        lcd.crlf()
                        lcd.write_string(reply["error"])
                        lcd.crlf()
                    elif reply["dispense"]:
                        dispenseBeer()

                except json.decoder.JSONDecodeError:
                    print("JSON error!")
                    print(r.text)
                except Exception:
                    print("Error state!")
                    raise
            pin = None
            keypadID = None
            keyQueue.clear()
        
        elif STAR_FLAG:
            STAR_FLAG = False
            keyQueue.clear()



except KeyboardInterrupt:
    print("Caught Ctrl-C")
finally:
    print("Shutting down")
    rfidReader.ungrab()
    GPIO.cleanup()
    lcd.close(clear=True)