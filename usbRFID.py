from collections import deque
from time import sleep, time

import evdev
import requests
from pad4pi import rpi_gpio
import RPi.GPIO as GPIO

COST = 2.50

class InputsQueue:
    def __init__(self, maxlen, timeout):
        self.queue = deque(maxlen=maxlen)
        self.timeout = timeout
        self.lastEditTime = time()
    
    def add(self, item):
        self.lastEditTime = time()
        self.queue.append(item)
        
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

cardQueue = InputsQueue(maxlen = 10, timeout = 0.5)
keyQueue = InputsQueue(maxlen = 8, timeout = 3)

KEYPAD = [
    ['1', '2', '3'],
    ['4', '5', '6'],
    ['7', '8', '9'],
    ["*", '0', "#"]
]
ROW_PINS = [5, 6, 13, 19] # BCM numbering
COL_PINS = [16, 20, 21] # BCM numbering
factory = rpi_gpio.KeypadFactory()
keypad = factory.create_keypad(keypad=KEYPAD, row_pins=ROW_PINS, col_pins=COL_PINS)

DONE_KEY = '#'
KEYPAD_DONE_FLAG = False
def handleKey(key):
    if key == DONE_KEY:
        KEYPAD_DONE_FLAG = True
    else:
        keyQueue.add(key)

# printKey will be called each time a keypad button is pressed
keypad.registerKeyPressHandler(printKey)

rfidReader = evdev.InputDevice('/dev/input/event0')
print(rfidReader)

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
            print("Sending request to server for", cardID)
            r = requests.post(
                "https://thetaspd.pythonanywhere.com/beer/compass/", 
                data={
                    "cost": COST,
                    "compassID": cardID
                }
            )
            cardID = None
            try:
                reply = r.json()
                print(reply)
            except Exception:
                print(r.text)
        
        elif KEYPAD_DONE_FLAG:
            KEYPAD_DONE_FLAG = False
            userID = keyQueue.harvest()


except KeyboardInterrupt:
    print("Caught Ctrl-C")
finally:
    print("Shutting down")
    rfidReader.ungrab()
    keypad.cleanup()