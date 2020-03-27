from pirc522 import RFID
import traceback
from time import sleep
import RPi.GPIO as GPIO

def detect_uid(reader):
    (error, tag_type) = reader.request()
    (error, uid) = reader.anticoll()

    if uid[0] != 0x88:
        rfid_uid = uid[0:4]  # classic 4bytes-rfid card
    else:
        (error, uid2) = reader.anticoll2()
        rfid_uid = uid[1:4] + uid2[:4]  # 7bytes-rfid card

    return rfid_uid


reader = RFID()
    
try:
    while True:
        try:        
            print("UID: " + str(detect_uid(reader)))
        except Exception as e:            
            traceback.print_exc()
        sleep(1)
except:
    traceback.print_exc()
finally:
    GPIO.cleanup()