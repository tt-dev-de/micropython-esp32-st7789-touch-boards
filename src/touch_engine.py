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

Module: touch_engine.py

Version:
    1.0.0

Description:   
    TouchEngine converts raw touch controller input into high-level touch events.

    The engine tracks the complete lifecycle of a touch interaction:
    finger down, movement, release, tap detection, long tap detection,
    swipe detection, and double tap detection.

    Supported base events:
        - DOWN: A new touch has started.
        - MOVE: The finger moved far enough to exceed the move deadzone.
        - UP: The touch ended.
        - DOUBLE_TAP: A second tap occurred close enough in time and position
          to the previous tap.

    UP events may include a gesture classification:
        - TAP
        - LONG_TAP
        - SWIPE_LEFT
        - SWIPE_RIGHT
        - SWIPE_UP
        - SWIPE_DOWN

    The touch object passed to the constructor must provide:
        - read_if_touched() -> (x, y) or None
        - read_continuous() -> (x, y) or None

    poll() should be called repeatedly from the main loop.
    It returns an event dictionary or None if no new event is available.
"""

import time


class TouchEngine:
    STATE_IDLE = 0
    STATE_TOUCHING = 1

        
    def __init__(
        self,
        touch,
        move_deadzone: int = 2,
        swipe_threshold: int = 30,
        tap_max_distance: int = 10,
        release_misses: int = 4,
        long_tap_ms: int = 600,
        double_tap_ms: int = 700,
        double_tap_distance: int = 100,
    ):
        """
        Create a touch event engine.

        Args:
            touch:
                Touch driver instance. Must implement read_if_touched()
                and read_continuous().

            move_deadzone:
                Minimum movement in pixels before a MOVE event is emitted.

            swipe_threshold:
                Minimum movement in pixels required to classify a gesture
                as a swipe.

            tap_max_distance:
                Maximum movement in pixels still accepted as a tap.

            release_misses:
                Number of consecutive missing touch samples before the touch
                is considered released.

            long_tap_ms:
                Minimum touch duration in milliseconds for LONG_TAP.

            double_tap_ms:
                Maximum time between two taps for DOUBLE_TAP detection.

            double_tap_distance:
                Maximum distance in pixels between two taps for DOUBLE_TAP.
        """



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

        if abs(dx) > abs(dy):
            return "SWIPE_RIGHT" if dx > 0 else "SWIPE_LEFT"

        return "SWIPE_DOWN" if dy > 0 else "SWIPE_UP"

    def _is_near(self, x1, y1, x2, y2, dist):
        return (x1 - x2) ** 2 + (y1 - y2) ** 2 <= dist ** 2

    def _tap_center(self):
        return (
            (self.start_x + self.last_x) // 2,
            (self.start_y + self.last_y) // 2,
        )

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
                if (
                    dt <= self.double_tap_ms
                    and self._is_near(
                        x,
                        y,
                        self.last_tap_x,
                        self.last_tap_y,
                        self.double_tap_distance,
                    )
                ):
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

            if (
                abs(x - self.last_x) >= self.move_deadzone
                or abs(y - self.last_y) >= self.move_deadzone
            ):
                self.last_x, self.last_y = x, y
                return self._make_event(
                    "MOVE",
                    x,
                    y,
                    x - self.start_x,
                    y - self.start_y,
                )

        return None
