import evdev
import time
import config

def initNumpad():
    global numpad
    if config.NUMPAD_LOCATION != "":
        try:
            numpad = evdev.InputDevice(config.NUMPAD_LOCATION)
            print(numpad)
            numpad.grab()
        except OSError:
            print("OS Error in initRFID")
            numpad = None
    else:
        numpad = None

initNumpad()

def handleUSBNumpad():
    global numpad
    if numpad is None:
        initNumpad()
        return
    try:
        for event in numpad.read():
            if event.type == evdev.ecodes.EV_KEY:
                data = evdev.categorize(event)
                if data.keystate == 1:
                    print(data.keycode[-1]) # last character is one of interest
    except BlockingIOError:
        return
    except OSError:
        print("Numpad input error. Reinitializing")
        initNumpad()
        return

while True:
    time.sleep(0.01)
    handleUSBNumpad()