import evdev
import time
import config
import traceback

def searchForDevice(devName):
    devices = [evdev.InputDevice(path) for path in evdev.list_devices()]
    for device in devices:
        if device.name == devName:
            return device

def initNumpad():
    global numpad
    if config.NUMPAD_DEV_NAME != "":
        try:
            numpad = searchForDevice(config.NUMPAD_DEV_NAME)
            print(numpad)
            numpad.grab()
        except OSError:
            traceback.print_exc()
            print("OS Error in initKeypad")
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
