import evdev

device = evdev.InputDevice('/dev/input/event0')
print(device)

cardID = ""
with device.grab_context():
    while True:
        try:
            for event in device.read():
                print(evdev.categorize(event))
        except BlockingIOError:
            print(cardID)
            cardID = ""
            pass
