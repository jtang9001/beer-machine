from pad4pi import rpi_gpio

# KEYPAD = [
#     [1, 2, 3, "A"],
#     [4, 5, 6, "B"],
#     [7, 8, 9, "C"],
#     ["*", 0, "#", "D"]
# ]

# ROW_PINS = [6, 13, 19, 26] # BCM numbering
# COL_PINS = [12, 16, 20, 21] # BCM numbering


# KEYPAD = [
#     [1, 2, 3],
#     [4, 5, 6],
#     [7, 8, 9],
#     ["*", 0, "#"]
# ]

# ROW_PINS = [6, 13, 19, 26] # BCM numbering
# COL_PINS = [12, 16, 20] # BCM numbering

from config import KEYPAD, ROW_PINS, COL_PINS

factory = rpi_gpio.KeypadFactory()

keypad = factory.create_keypad(keypad=KEYPAD, row_pins=ROW_PINS, col_pins=COL_PINS)

def printKey(key):
    print(key)

# printKey will be called each time a keypad button is pressed
keypad.registerKeyPressHandler(printKey)

try:
    while True:
        pass
except KeyboardInterrupt:
    print("Caught CTRL-C")
    keypad.cleanup()
