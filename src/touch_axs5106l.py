"""
MIT License

Copyright (c) 2026 Thomas Tillig

Development assisted by AI tools.

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction...

-------------------------------------------------------------------------------

Module: touch_axs5106l.py

Version:
    1.0.0

Description:
    MicroPython driver and event engine for the AXS5106L capacitive touch controller,
    as used on ESP32-C6 1.47" 172x320 M-Touch displays.

    The module provides both low-level hardware access and a higher-level,
    state-based touch event engine.

Features:
    - I2C communication with AXS5106L touch controller
    - Raw touch data acquisition (12-bit coordinates)
    - Coordinate mapping to landscape display (320x172)
    - Robust touch tracking independent of INT signal glitches
    - State machine-based event processing

Supported Events:
    - DOWN
    - MOVE
    - UP
    - DOUBLE_TAP (detected on second DOWN for low latency)

    UP events may include gesture classification:
    - TAP
    - LONG_TAP
    - SWIPE_LEFT
    - SWIPE_RIGHT
    - SWIPE_UP
    - SWIPE_DOWN

Design Notes:
    - Touch detection uses INT only for initial contact (IDLE state).
      Continuous tracking is performed via active polling.
    - Double-tap detection is performed on the second DOWN event
      for improved responsiveness.
    - Tap position uses the midpoint between touch start and end.

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
                    if dx*dx + dy*dy <= self.tap_max_distance**2:
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
