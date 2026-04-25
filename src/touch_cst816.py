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
    1.0.0

Description:
    MicroPython driver and event engine for the CST816 capacitive touch
    controller, as used on Waveshare ESP32-C6 Touch LCD 1.9 boards.

    The module provides both low-level hardware access and a higher-level,
    state-based touch event engine.

Features:
    - I2C communication with CST816
    - Raw touch data acquisition
    - Coordinate mapping for portrait and landscape rotations
    - Robust touch tracking independent of controller gesture codes
    - State machine-based event processing

Supported Events:
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
    - Gestures are derived from mapped screen coordinates, exactly like in the
      AXS5106L solution.
    - Default rotation is set to 270 degrees, which is the most likely match for
      landscape mode on the Waveshare 1.9" 170x320 board. If the axes still do
      not match on your firmware/display setup, try rotation=90.

Author:
    Thomas Tillig

Year:
    2026
"""

import machine
import time


class TouchCST816:
    """
    Hardware-level touch class for the CST816.

    Responsibilities:
    - Reset touch controller
    - Initialize I2C
    - Read raw data
    - Map raw coordinates to screen coordinates

    Designed for:
    - Waveshare ESP32-C6 Touch LCD 1.9
    - ST7789V2 display with 170x320 pixels
    """

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
        """
        INT is active low on most CST816 designs.
        If INT is not wired or not used, return True so reads are allowed.
        """
        if self.tp_int is None:
            return True
        return self.tp_int.value() == 0

    def read_raw(self):
        """
        Reads raw touch data from the controller.

        Returns:
            (raw_x, raw_y) or None
        """
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
        """
        Maps raw CST816 coordinates to screen coordinates.

        Strategy:
        1. Normalize raw touch into portrait logical coordinates.
        2. Apply target rotation to obtain final screen coordinates.

        Supported rotations:
            0, 90, 180, 270
        Rotation is interpreted clockwise.
        """
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
        """
        Reads only if INT indicates active touch.
        If INT is not available, a read attempt is still performed.
        """
        if self.tp_int is not None and not self.is_touched():
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
        Compatibility method (INT-based read when available).
        """
        return self.read_if_touched()


class TouchEngine:
    STATE_IDLE = 0
    STATE_TOUCHING = 1

    def __init__(
        self,
        touch,
        move_deadzone=2,
        swipe_threshold=30,
        tap_max_distance=10,
        release_misses=4,
        long_tap_ms=600,
        double_tap_ms=700,
        double_tap_distance=100,
    ):
        self.touch = touch
        self.move_deadzone = move_deadzone
        self.swipe_threshold = swipe_threshold
        self.tap_max_distance = tap_max_distance
        self.release_misses = release_misses

        self.long_tap_ms = long_tap_ms
        self.double_tap_ms = double_tap_ms
        self.double_tap_distance = double_tap_distance

        self.state = self.STATE_IDLE

        self.start_x = self.start_y = 0
        self.last_x = self.last_y = 0
        self.current_x = self.current_y = 0

        self.touch_start_ms = 0
        self.misses = 0

        self.last_tap_ms = None
        self.last_tap_x = 0
        self.last_tap_y = 0

        self.skip_next_up = False

    def _make_event(self, etype, x, y, dx=0, dy=0):
        return {
            "type": etype,
            "x": x,
            "y": y,
            "start_x": self.start_x,
            "start_y": self.start_y,
            "dx": dx,
            "dy": dy,
            "duration_ms": time.ticks_diff(time.ticks_ms(), self.touch_start_ms),
        }

    def _make_double_tap_event(self, x, y, dt_ms):
        return {
            "type": "DOUBLE_TAP",
            "x": x,
            "y": y,
            "tap1_x": self.last_tap_x,
            "tap1_y": self.last_tap_y,
            "tap2_x": x,
            "tap2_y": y,
            "dt_ms": dt_ms,
        }

    def _detect_swipe_type(self, dx, dy):
        if abs(dx) < self.swipe_threshold and abs(dy) < self.swipe_threshold:
            return None
        return "SWIPE_RIGHT" if abs(dx) > abs(dy) and dx > 0 else \
               "SWIPE_LEFT" if abs(dx) > abs(dy) else \
               "SWIPE_DOWN" if dy > 0 else "SWIPE_UP"

    def _is_near(self, x1, y1, x2, y2, dist):
        return (x1 - x2) ** 2 + (y1 - y2) ** 2 <= dist ** 2

    def _tap_center(self):
        return (self.start_x + self.last_x) // 2, (self.start_y + self.last_y) // 2

    def poll(self):
        if self.state == self.STATE_IDLE:
            pt = self.touch.read_if_touched()
            if pt is None:
                return None

            x, y = pt
            self.start_x = self.last_x = self.current_x = x
            self.start_y = self.last_y = self.current_y = y
            self.touch_start_ms = time.ticks_ms()
            self.misses = 0
            self.state = self.STATE_TOUCHING

            if self.last_tap_ms:
                dt = time.ticks_diff(self.touch_start_ms, self.last_tap_ms)
                if dt <= self.double_tap_ms and self._is_near(x, y, self.last_tap_x, self.last_tap_y, self.double_tap_distance):
                    self.skip_next_up = True
                    self.last_tap_ms = None
                    return self._make_double_tap_event(x, y, dt)

            return self._make_event("DOWN", x, y)

        if self.state == self.STATE_TOUCHING:
            pt = self.touch.read_continuous()

            if pt is None:
                self.misses += 1
                if self.misses < self.release_misses:
                    return None

                if self.skip_next_up:
                    self.state = self.STATE_IDLE
                    self.skip_next_up = False
                    return None

                dx = self.last_x - self.start_x
                dy = self.last_y - self.start_y
                evt = self._make_event("UP", self.last_x, self.last_y, dx, dy)

                self.state = self.STATE_IDLE

                swipe = self._detect_swipe_type(dx, dy)
                if swipe:
                    evt["gesture"] = swipe
                    self.last_tap_ms = None
                else:
                    if dx * dx + dy * dy <= self.tap_max_distance ** 2:
                        if evt["duration_ms"] >= self.long_tap_ms:
                            evt["gesture"] = "LONG_TAP"
                            self.last_tap_ms = None
                        else:
                            evt["gesture"] = "TAP"
                            self.last_tap_ms = time.ticks_ms()
                            self.last_tap_x, self.last_tap_y = self._tap_center()
                    else:
                        evt["gesture"] = None
                        self.last_tap_ms = None

                return evt

            self.misses = 0
            x, y = pt

            if abs(x - self.last_x) >= self.move_deadzone or abs(y - self.last_y) >= self.move_deadzone:
                self.last_x, self.last_y = x, y
                return self._make_event("MOVE", x, y, x - self.start_x, y - self.start_y)

        return None


def main():
    print("Starting touch_cst816 test...")

    touch = TouchCST816()
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

    cid = touch.chip_id()
    if cid is None:
        print("Chip ID: n/a")
    else:
        print("Chip ID: 0x{:02X}".format(cid))

    print("Touch the display. Events will be printed to the console.")

    while True:
        evt = engine.poll()
        if evt is not None:
            print(evt)
        time.sleep_ms(10)


if __name__ == "__main__":
    main()
