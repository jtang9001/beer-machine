#These settings are unique to each machine.

#Name of machine to send to Django
MACHINE_NAME = "Basement Right"

#Secret key
MACHINE_KEY = "ro8yckzt7acmpmh8antk9rf5wj0iqd4g2nx8wlpvi41fcbvb"

#Location of USB devices
RFID_LOCATION = '/dev/input/event0' 

NUMPAD_LOCATION = '/dev/input/event1' 

SPKEY1 = "I"
SPKEY2 = "Q"

# #keypad setup
# KEYPAD = [
#     ["1", "2", "3", "A"],
#     ['4', "5", "6", "B"],
#     ['7', "8", "9", "C"],
#     ["*", "0", "#", "D"]
# ]

# ROW_PINS = [6, 13, 19, 26] # BCM numbering
# COL_PINS = [12, 16, 20, 21] # BCM numbering


KEYPAD = [
    ["1", "2", "3"],
    ["4", "5", "6"],
    ["7", "8", "9"],
    ["*", "0", "#"]
]

ROW_PINS = [6, 13, 19, 26] # BCM numbering
COL_PINS = [12, 16, 20] # BCM numbering
