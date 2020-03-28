import evdev as usb

device = usb.InputDevice('/dev/input/event0')
print(device)

cardID = ""
with device.grab_context():
    while True:
        try:
            for event in device.read():
                if event.keystate == 1: #keystate 1 is key down
                    cardID += event.keycode

        except BlockingIOError:
            print(cardID)
            cardID = ""
            pass
