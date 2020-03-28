import RPi.GPIO as GPIO
from time import sleep

GPIO.setmode(GPIO.BCM)

L1 = 5
L2 = 6
L3 = 13
L4 = 19

C1 = 12
C2 = 16
C3 = 20
C4 = 21

GPIO.setup(L1, GPIO.OUT)
GPIO.setup(L2, GPIO.OUT)
GPIO.setup(L3, GPIO.OUT)
GPIO.setup(L4, GPIO.OUT)

GPIO.setup(C1, GPIO.IN, pull_up_down=GPIO.PUD_DOWN)
GPIO.setup(C2, GPIO.IN, pull_up_down=GPIO.PUD_DOWN)
GPIO.setup(C3, GPIO.IN, pull_up_down=GPIO.PUD_DOWN)
GPIO.setup(C4, GPIO.IN, pull_up_down=GPIO.PUD_DOWN)

def readLine(line, characters):
    GPIO.output(line, GPIO.HIGH)
    if(GPIO.input(C1) == 1):
        return(characters[0])
    if(GPIO.input(C2) == 1):
        return(characters[1])
    if(GPIO.input(C3) == 1):
        return(characters[2])
    if(GPIO.input(C4) == 1):
        print(characters[3])
    GPIO.output(line, GPIO.LOW)

def readKeypad():
    val1 = readLine(L1, ["1","2","3","A"])
    val2 = readLine(L2, ["4","5","6","B"])
    val3 = readLine(L3, ["7","8","9","C"])
    val4 = readLine(L4, ["*","0","#","D"])
    if val1 is not None:
        return val1
    elif val2 is not None:
        return val2
    elif val3 is not None:
        return val3
    elif val4 is not None:
        return val4

while True:
    char = readKeypad()
    if char is not None:
        print(char)
    sleep(0.1)