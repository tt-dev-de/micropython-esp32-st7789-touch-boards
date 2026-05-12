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

Module: touch_axs5106l.py

Version:
    1.0.1

Description:
    MicroPython driver and event engine for the AXS5106L capacitive touch controller,
    as used on as used on Waveshare ESP32 Touch LCD boards.

    The module provides both low-level hardware access and a higher-level,
    state-based touch event engine.

Features:
    - I2C communication with AXS5106L touch controller
    - Raw touch data acquisition (12-bit coordinates)
    - Coordinate mapping to landscape display (320x172)
    - Robust touch tracking independent of INT signal glitches
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


class TouchAXS5106L:
    """
    Hardware-level touch class for the AXS5106L.

    Responsibilities:
    - Reset touch controller
    - Initialize I2C
    - Read raw data
    - Map raw coordinates to screen coordinates

    Designed for:
    - ESP32-C6 1.47" M-Touch display
    - Landscape 320x172
    """

    def __init__(
        self,
        i2c_id=0,
        sda_pin=18,
        scl_pin=19,
        rst_pin=20,
        int_pin=21,
        addr=0x63,
        screen_w=320,
        screen_h=172,
        raw_x_min=0,
        raw_x_max=170,
        raw_y_min=0,
        raw_y_max=320,
        i2c_freq=400000,
        reset_low_ms=100,
        reset_high_ms=200,
    ):
        self.addr = addr

        self.screen_w = screen_w
        self.screen_h = screen_h

        self.raw_x_min = raw_x_min
        self.raw_x_max = raw_x_max
        self.raw_y_min = raw_y_min
        self.raw_y_max = raw_y_max

        self.tp_rst = machine.Pin(rst_pin, machine.Pin.OUT, value=1)
        self.tp_int = machine.Pin(int_pin, machine.Pin.IN, machine.Pin.PULL_UP)

        self._reset(reset_low_ms, reset_high_ms)

        self.i2c = machine.I2C(
            i2c_id,
            sda=machine.Pin(sda_pin),
            scl=machine.Pin(scl_pin),
            freq=i2c_freq,
        )

    def _reset(self, low_ms=100, high_ms=200):
        self.tp_rst.value(0)
        time.sleep_ms(low_ms)
        self.tp_rst.value(1)
        time.sleep_ms(high_ms)

    def scan(self):
        return self.i2c.scan()

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
        """
        INT is active low.
        """
        return self.tp_int.value() == 0

    def read_raw(self):
        """
        Reads raw touch data from the controller.

        Returns:
            (raw_x, raw_y) or None
        """
        try:
            self.i2c.writeto(self.addr, b"\x01")
            data = self.i2c.readfrom(self.addr, 14)

            if data[1] == 0:
                return None

            raw_x = ((data[2] & 0x0F) << 8) | data[3]
            raw_y = ((data[4] & 0x0F) << 8) | data[5]

            return raw_x, raw_y

        except Exception:
            return None

    def map_touch(self, raw_x, raw_y):
        """
        Maps raw data to screen coordinates for landscape 320x172.
        """
        x_unflipped = self.scale(raw_y, self.raw_y_min, self.raw_y_max, 0, self.screen_w - 1)
        y = self.scale(raw_x, self.raw_x_min, self.raw_x_max, self.screen_h - 1, 0)
        x = (self.screen_w - 1) - x_unflipped

        return (
            self.clamp(x, 0, self.screen_w - 1),
            self.clamp(y, 0, self.screen_h - 1),
        )

    def read_if_touched(self):
        """
        Reads only if INT indicates active touch.

        Used for detecting new touch start.
        """
        if not self.is_touched():
            return None

        raw = self.read_raw()
        if raw is None:
            return None

        return self.map_touch(raw[0], raw[1])

    def read_continuous(self):
        """
        Continuous read without checking INT.

        Used for tracking ongoing touch movements.
        """
        raw = self.read_raw()
        if raw is None:
            return None

        return self.map_touch(raw[0], raw[1])

    def read(self):
        """
        Compatibility method (INT-based read).
        """
        return self.read_if_touched()

# Re-export for backward compatibility:
# Allows: from touch_axs5106l import touch_axs5106l, TouchEngine
from touch_engine import TouchEngine


def main():
    print("Starte touch_axs5106l Test...")

    touch = TouchAXS5106L()
    engine = TouchEngine(
        touch,
        move_deadzone=2,
        swipe_threshold=30,
        tap_max_distance=10,
        release_misses=4,
        long_tap_ms=600,
        double_tap_ms=700,
        double_tap_distance=100,
    )

    devices = touch.scan()
    print("I2C scan:", [hex(x) for x in devices])

    if touch.addr not in devices:
        print("WARNING: Touch controller 0x{:02X} not found in I2C scan".format(touch.addr))
    else:
        print("Touch controller found at 0x{:02X}".format(touch.addr))

    print("Touch the display. Events will be printed to the console.")
    print("NEW: LONG_TAP and DOUBLE_TAP are supported.")

    while True:
        evt = engine.poll()
        if evt is not None:
            print(evt)
        time.sleep_ms(10)


if __name__ == "__main__":
    main()
