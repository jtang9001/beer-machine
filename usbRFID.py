import evdev

device = evdev.InputDevice('/dev/input/event0')
print(device)

cardID = []
with device.grab_context():
    while True:
        try:
            for event in device.read():
                if event.type == evdev.ecodes.EV_KEY:
                    data = evdev.categorize(event)
                    if data.keystate == 1:
                        cardID.append(data.keycode)

        except BlockingIOError:
            if cardID != []:
                print(cardID)
                cardID = []
            pass
