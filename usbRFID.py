from collections import deque
from time import sleep, time

import evdev
import requests

COST = 2.50

rfidReader = evdev.InputDevice('/dev/input/event0')
print(rfidReader)

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
            contents = "".join(self.queue)
            self.queue.clear()
            return contents

cardQueue = InputsQueue(maxlen = 10, timeout = 0.5)
with rfidReader.grab_context():
    while True:
        try:
            for event in rfidReader.read():
                if event.type == evdev.ecodes.EV_KEY:
                    data = evdev.categorize(event)
                    if data.keystate == 1:
                        cardQueue.add(data.keycode[-1]) # last character is one of interest
        except BlockingIOError:
            cardID = cardQueue.churn()
        
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