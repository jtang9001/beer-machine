from collections import deque
from time import time, sleep

from sparkfun_serlcd import Sparkfun_SerLCD_UART
from RPLCD.gpio import CharLCD

class LCD:
    def __init__(self, lcd):
        self.lcd = lcd
        self.lcd.clear()
        self.lcd.home()
        self.lines = ["", ""]
        self.scrollLines = ["", ""]
        self.scrollQueues = [deque(), deque()]
        self.toggleQueues = [deque(), deque()]
        self.lastScrollTick = time()
        self.mainLoop()
        
    # def write(self):
    #     self.lcd.write_string(self.line1)
    #     self.lcd.crlf()
    #     self.lcd.write_string(self.line2)

    def mainLoop(self):
        self.clear()
        self.writeLine(0, "SPD Beer Machine")
        self.writeLine(1, "Enter ID > ")

    def clear(self):
        self.lcd.clear()
        self.lcd.home()
        self.lines = ["", ""]

    def debugPrint(self):
        print("LCD0: ", self.lines[0])
        print("LCD1: ", self.lines[1])

    def clearPrint(self, msg):
        msg = str(msg)
        self.lcd.clear()
        self.lcd.home()
        self.lcd.write_string(msg)
        self.lines[0] = msg[:16]
        self.lines[1] = msg[16:32]
        #self.debugPrint()

    def holdPrint(self, msg, delay = 3):
        self.clearPrint(msg)
        sleep(delay)

    def writeLine(self, lineNum, msg):
        msg = str(msg)[:16]
        self.lcd.set_cursor(0, lineNum)
        self.lcd.write_string(msg + " " * (16 - len(msg)))
        self.lines[lineNum] = msg
        #self.debugPrint()

    def appendLine(self, lineNum, char):
        char = str(char)
        self.lines[lineNum] += char
        self.lines[lineNum] = self.lines[lineNum][:16]
        self.lcd.set_cursor(0, lineNum)
        self.lcd.write_string(self.lines[lineNum])
        #self.debugPrint()

    def setScrollLine(self, linenum, msg):
        msg = msg.strip() + '  '
        if self.scrollLines[linenum] != msg:
            self.scrollLines[linenum] = msg
            self.scrollQueues[linenum] = deque(msg)
            self.lastScrollTick = time()
    
    def tickScrollLine(self, linenum, tickPeriod = 0.3):
        if len(self.scrollQueues[linenum]) <= 16:
            self.writeLine(linenum, "".join(self.scrollQueues[linenum]))
        else:
            self.writeLine(linenum, "".join(self.scrollQueues[linenum])[:16])
            currentTime = time()
            if currentTime - self.lastScrollTick >  tickPeriod:
                self.lastScrollTick = currentTime
                self.scrollQueues[linenum].rotate(-1)

    def tickScrollLines(self, tickPeriod = 0.3):
        doScroll = False
        currentTime = time()
        if currentTime - self.lastScrollTick >  tickPeriod:
            doScroll = True
            self.lastScrollTick = currentTime

        self.writeLine(0, "".join(self.scrollQueues[0]))
        self.writeLine(1, "".join(self.scrollQueues[1]))

        if doScroll:
            doScroll = False
            for linenum in [0,1]:
                if len(self.scrollQueues[linenum]) > 16:
                    self.scrollQueues[linenum].rotate(-1)

    def holdScrollPrint(self, linenum, msg, tickPeriod = 0.3):
        origMsg = msg
        self.setScrollLine(linenum, msg)
        self.tickScrollLine(linenum, msg)
        currentMsg = "".join(self.scrollQueues[linenum])
        while currentMsg != origMsg:
            self.tickScrollLine(linenum, tickPeriod)
            currentMsg = "".join(self.scrollQueues[linenum])

    def setToggleLine(self, linenum, msgs):
        msgs = {str(m) for m in msgs}
        if set(self.toggleQueues[linenum]) != msgs:
            self.toggleQueues[linenum] = deque(msgs)
            self.lastToggleTick = time()
    
    def tickToggleLine(self, linenum, tickPeriod = 2):
        self.writeLine(linenum, self.toggleQueues[linenum][0])
        currentTime = time()
        if currentTime - self.lastToggleTick >  tickPeriod:
            self.lastToggleTick = currentTime
            self.toggleQueues[linenum].rotate(-1)

    def tickToggleLines(self, tickPeriod = 2):
        doToggle = False
        currentTime = time()
        if currentTime - self.lastToggleTick >  tickPeriod:
            doToggle = True
            self.lastToggleTick = currentTime

        self.writeLine(0, self.toggleQueues[0][0])
        self.writeLine(1, self.toggleQueues[1][0])

        if doToggle:
            doToggle = False
            self.toggleQueues[0].rotate(-1)
            self.toggleQueues[1].rotate(-1)
         
    def shutdown(self):
        self.lcd.close(clear=True)


class ModifiedSparkfunLCD(Sparkfun_SerLCD_UART):
    def __init__(self, uart):
        super().__init__(uart)

    def write_string(self, msg):
        super().write(msg)

    def close(self, clear = True):
        if clear:
            super().clear()
        super()._uart.close()

class ModifiedCharLCD(CharLCD):
    def __init__(
        self, numbering_mode=None, pin_rs=None, pin_rw=None, pin_e=None, pins_data=None, 
        pin_backlight=None, backlight_mode='active_low', backlight_enabled=True,
        cols=20, rows=4, dotsize=8, charmap='A02', auto_linebreaks=True, compat_mode=False
    ):
        super().__init__(
            numbering_mode, pin_rs, pin_rw, pin_e, pins_data, 
            pin_backlight, backlight_mode, backlight_enabled,
            cols, rows, dotsize, charmap, auto_linebreaks, compat_mode
        )

    def set_cursor(self, col, row):
        super().cursor_pos = (row, col)
        