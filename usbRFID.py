from collections import deque
from time import sleep, time

import evdev
import requests
import RPi.GPIO as GPIO

BEER_PIN = 0
GPIO.setmode(GPIO.BCM)
GPIO.setup(BEER_PIN, GPIO.OUT, initial = GPIO.LOW)

L1 = 5
L2 = 6
L3 = 13
L4 = 19

C1 = 16
C2 = 20
C3 = 21

GPIO.setwarnings(False)
GPIO.setmode(GPIO.BCM)

GPIO.setup(L1, GPIO.OUT)
GPIO.setup(L2, GPIO.OUT)
GPIO.setup(L3, GPIO.OUT)
GPIO.setup(L4, GPIO.OUT)

GPIO.setup(C1, GPIO.IN, pull_up_down=GPIO.PUD_DOWN)
GPIO.setup(C2, GPIO.IN, pull_up_down=GPIO.PUD_DOWN)
GPIO.setup(C3, GPIO.IN, pull_up_down=GPIO.PUD_DOWN)

def readLine(line, characters):
    GPIO.output(line, GPIO.HIGH)
    if(GPIO.input(C1) == 1):
        return(characters[0])
    if(GPIO.input(C2) == 1):
        return(characters[1])
    if(GPIO.input(C3) == 1):
        return(characters[2])
    GPIO.output(line, GPIO.LOW)

def readKeypad():
    val1 = readLine(L1, ["1","2","3"])
    val2 = readLine(L2, ["4","5","6"])
    val3 = readLine(L3, ["7","8","9"])
    val4 = readLine(L4, ["*","0","#"])
    if val1 is not None:
        return val1
    elif val2 is not None:
        return val2
    elif val3 is not None:
        return val3
    elif val4 is not None:
        return val4

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

cardID = None
keypadID = None

rfidReader = evdev.InputDevice('/dev/input/event0')
print(rfidReader)

def dispenseBeer():
    print("Dispensing beer")
    GPIO.output(BEER_PIN, GPIO.HIGH)
    sleep(0.5)
    GPIO.output(BEER_PIN, GPIO.LOW)

def confirmCompassBeer(name, bal):
    global POUND_FLAG, STAR_FLAG
    print(f"{name}, ${bal}")
    print("# to dispense, * to cancel")
    startTime = time()
    while time() - startTime <= 5:
        char = readKeypad()
        if char == "#":
            r = requests.post(
                "https://thetaspd.pythonanywhere.com/beer/pay_compass/", 
                data = { "compassID": cardID, "cost": COST }
            )
            try:
                reply = r.json()
                print(reply)
                if reply["dispense"]:
                    dispenseBeer()
                else:
                    print("Could not authorize beer")
            except Exception:
                print(r.text)
                raise
            return

        elif char == "*":
            print("Beer cancelled with *")
            STAR_FLAG = False
            return
        
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

        key = readKeypad()
        if key == "#":
            keypadID = keyQueue.harvest()
        elif key is not None:
            keyQueue.add(key)
        
        if cardID is not None:
            print("Querying balance for", cardID)
            r = requests.post(
                "https://thetaspd.pythonanywhere.com/beer/query_compass/", 
                data = { "compassID": cardID }
            )
            cardID = None
            try:
                reply = r.json()
                print(reply)
                confirmCompassBeer(reply["name"], reply["balance"])
            except Exception:
                print("Error state!")
                print(r.text)
                raise
        
        keyQueue.churn()
        if keypadID is not None:
            print(keypadID)
            keypadID = None

except KeyboardInterrupt:
    print("Caught Ctrl-C")
finally:
    print("Shutting down")
    rfidReader.ungrab()
    GPIO.cleanup()