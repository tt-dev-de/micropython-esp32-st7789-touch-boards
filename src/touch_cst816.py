"""
MIT License

Copyright (c) 2026 Thomas Tillig

Development assisted by AI tools.

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.

-------------------------------------------------------------------------------

Module: touch_cst816.py

Version:
    1.0.1

Description:
    MicroPython driver and event engine for the CST328 capacitive touch
    controller, as used on Waveshare ESP32 Touch LCD boards.

    The module provides both low-level hardware access and a higher-level,
    state-based touch event engine.

Features:
    - I2C communication with CST816
    - Raw touch data acquisition
    - Coordinate mapping for portrait and landscape rotations
    - Robust touch tracking independent of controller gesture codes
    - State machine-based event processing

Supported Events from touch_engine.py:
    - DOWN
    - MOVE
    - UP
    - DOUBLE_TAP

    UP events may include gesture classification:
    - TAP
    - LONG_TAP
    - SWIPE_LEFT
    - SWIPE_RIGHT
    - SWIPE_UP
    - SWIPE_DOWN

Design Notes:
    - The controller's own gesture register is intentionally not used for final
      gesture classification, because those direction codes usually do not match
      the display orientation after rotation.
    - Gestures are derived from mapped screen coordinates.
    - Higher-level touch event processing such as TAP, LONG_TAP,
      DOUBLE_TAP and SWIPE detection can be implemented using the optional
      touch_engine.py module and its TouchEngine class.
    - The touch driver itself focuses on low-level hardware access and
      coordinate mapping, while touch_engine.py provides a reusable,
      controller-independent event state machine.
    - Default rotation is set to 270 degrees, which is the most likely match for
      landscape mode on boards. If the axes still do not match on your
      firmware/display setup, try rotation=90.

Author:
    Thomas Tillig

Year:
    2026
"""

import machine
import time


class TouchCST816:
    REG_GESTURE = 0x01
    REG_FINGER_NUM = 0x02
    REG_X_H = 0x03
    REG_X_L = 0x04
    REG_Y_H = 0x05
    REG_Y_L = 0x06
    REG_CHIP_ID = 0xA7

    def __init__(
        self,
        i2c_id=0,
        sda_pin=18,
        scl_pin=8,
        rst_pin=21,
        int_pin=None,
        addr=0x15,
        raw_w=170,
        raw_h=320,
        screen_w=320,
        screen_h=170,
        rotation=270,
        raw_x_min=0,
        raw_x_max=169,
        raw_y_min=0,
        raw_y_max=319,
        i2c_freq=400000,
        reset_low_ms=10,
        reset_high_ms=50,
    ):
        self.addr = addr

        self.raw_w = raw_w
        self.raw_h = raw_h
        self.screen_w = screen_w
        self.screen_h = screen_h
        self.rotation = rotation

        self.raw_x_min = raw_x_min
        self.raw_x_max = raw_x_max
        self.raw_y_min = raw_y_min
        self.raw_y_max = raw_y_max

        self.tp_rst = machine.Pin(rst_pin, machine.Pin.OUT, value=1)

        self.tp_int = None
        if int_pin is not None:
            self.tp_int = machine.Pin(int_pin, machine.Pin.IN, machine.Pin.PULL_UP)

        self._reset(reset_low_ms, reset_high_ms)

        self.i2c = machine.I2C(
            i2c_id,
            sda=machine.Pin(sda_pin),
            scl=machine.Pin(scl_pin),
            freq=i2c_freq,
        )

    def _reset(self, low_ms=10, high_ms=50):
        self.tp_rst.value(0)
        time.sleep_ms(low_ms)
        self.tp_rst.value(1)
        time.sleep_ms(high_ms)

    def scan(self):
        return self.i2c.scan()

    def _read_reg(self, reg, n=1):
        self.i2c.writeto(self.addr, bytes([reg]))
        return self.i2c.readfrom(self.addr, n)

    def chip_id(self):
        try:
            return self._read_reg(self.REG_CHIP_ID)[0]
        except Exception:
            return None

    @staticmethod
    def clamp(v, lo, hi):
        if v < lo:
            return lo
        if v > hi:
            return hi
        return v

    def scale(self, v, in_min, in_max, out_min, out_max):
        if in_max <= in_min:
            return out_min
        v = self.clamp(v, in_min, in_max)
        return out_min + (v - in_min) * (out_max - out_min) // (in_max - in_min)

    def is_touched(self):
        if self.tp_int is None:
            return True
        return self.tp_int.value() == 0

    def read_raw(self):
        try:
            data = self._read_reg(self.REG_GESTURE, 6)

            fingers = data[1]
            if fingers == 0:
                return None

            raw_x = ((data[2] & 0x0F) << 8) | data[3]
            raw_y = ((data[4] & 0x0F) << 8) | data[5]

            return raw_x, raw_y
        except Exception:
            return None

    def map_touch(self, raw_x, raw_y):
        xp = self.scale(raw_x, self.raw_x_min, self.raw_x_max, 0, self.raw_w - 1)
        yp = self.scale(raw_y, self.raw_y_min, self.raw_y_max, 0, self.raw_h - 1)

        if self.rotation == 0:
            x = xp
            y = yp
        elif self.rotation == 90:
            x = (self.screen_w - 1) - yp
            y = xp
        elif self.rotation == 180:
            x = (self.screen_w - 1) - xp
            y = (self.screen_h - 1) - yp
        elif self.rotation == 270:
            x = yp
            y = (self.screen_h - 1) - xp
        else:
            x = yp
            y = (self.screen_h - 1) - xp

        return (
            self.clamp(x, 0, self.screen_w - 1),
            self.clamp(y, 0, self.screen_h - 1),
        )

    def read_if_touched(self):
        if self.tp_int is not None and not self.is_touched():
            return None

        raw = self.read_raw()
        if raw is None:
            return None

        return self.map_touch(raw[0], raw[1])

    def read_continuous(self):
        raw = self.read_raw()
        if raw is None:
            return None

        return self.map_touch(raw[0], raw[1])

    def read(self):
        return self.read_if_touched()
    
# Re-export for backward compatibility:
# Allows: from touch_cst816 import TouchCST816, TouchEngine
from touch_engine import TouchEngine
