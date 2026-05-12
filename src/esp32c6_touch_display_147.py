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

Module: esp32c6_touch_display_147.py

Version:
    1.0.1

Description:
    Board abstraction layer for the ESP32-C6 1.47" M-Touch display
    (172x320, ST7789 + AXS5106L).

    This module encapsulates:
    - ST7789 display initialization and configuration
    - Touch controller integration (AXS5106L)
    - High-level touch event processing via TouchEngine

    It provides a unified interface for display and touch handling,
    simplifying application development.

Features:
    - Preconfigured SPI display setup (ST7789)
    - Integrated touch controller (AXS5106L over I2C)
    - Event-based touch handling (DOWN, MOVE, UP, gestures)
    - Custom rotation support for 172x320 landscape mode
    - Utility helpers (clear, colors, cross drawing)

Design Notes:
    - The class acts as a hardware abstraction layer (HAL) for this specific board.
    - Touch processing is delegated to TouchEngine to keep responsibilities separated.
    - Display rotation is handled via a custom rotation table instead of relying
      solely on the driver defaults.
    - The API is intentionally minimalistic (KISS principle) to keep usage simple
      in MicroPython environments.

Author:
    Thomas Tillig

Year:
    2026
"""


import machine
import st7789py as st7789

from touch_axs5106l import TouchAXS5106L, TouchEngine


class ESP32C6TouchDisplay147:
    """
    Board-Abstraktion für das ESP32-C6 1,47" M-Touch-Display.

    Enthält:
    - Display (ST7789)
    - Touch-Hardware (AXS5106L)
    - zustandsbasierte Touch-Engine
    """

    SCREEN_W = 320
    SCREEN_H = 172

    def __init__(
        self,
        spi_baudrate=40_000_000,
        touch_move_deadzone=2,
        touch_swipe_threshold=30,
        touch_tap_max_distance=10,
        touch_release_misses=4,
    ):
        self.st7789 = st7789

        self.display = self._create_display(spi_baudrate)

        self.touch = TouchAXS5106L(
            i2c_id=0,
            sda_pin=18,
            scl_pin=19,
            rst_pin=20,
            int_pin=21,
            addr=0x63,
            screen_w=self.SCREEN_W,
            screen_h=self.SCREEN_H,
            raw_x_min=0,
            raw_x_max=170,
            raw_y_min=0,
            raw_y_max=320,
        )

        self.engine = TouchEngine(
            self.touch,
            move_deadzone=touch_move_deadzone,
            swipe_threshold=touch_swipe_threshold,
            tap_max_distance=touch_tap_max_distance,
            release_misses=touch_release_misses,
        )

    def _create_display(self, spi_baudrate):
        spi = machine.SPI(
            1,
            baudrate=spi_baudrate,
            polarity=0,
            phase=0,
            sck=machine.Pin(1),
            mosi=machine.Pin(2),
            miso=None,
        )

        rotation_table = (
            (0xE0, 320, 172, 0, 34, False),
        )

        disp = st7789.ST7789(
            spi,
            172,
            320,
            reset=machine.Pin(22, machine.Pin.OUT),
            dc=machine.Pin(15, machine.Pin.OUT),
            cs=machine.Pin(14, machine.Pin.OUT),
            backlight=machine.Pin(23, machine.Pin.OUT),
            rotation=0,
            color_order=st7789.BGR,
            custom_rotations=rotation_table,
        )

        disp.inversion_mode(False)
        disp.fill(st7789.BLACK)
        return disp

    def clear(self, color=None):
        if color is None:
            color = self.st7789.BLACK
        self.display.fill(color)

    def poll(self):
        """
        Liefert das nächste Touch-Event oder None.
        """
        return self.engine.poll()

    def read_touch(self):
        """
        Direkter gemappter Touch-Lesezugriff ohne Event-Engine.
        """
        return self.touch.read()

    def scan_touch_i2c(self):
        return self.touch.scan()

    def colors(self):
        """
        Bequemer Zugriff auf Farbkonstanten.
        """
        return self.st7789

    def draw_cross(self, x, y, color, size=4):
        for dx in range(-size, size + 1):
            xx = x + dx
            if 0 <= xx < self.SCREEN_W:
                self.display.pixel(xx, y, color)

        for dy in range(-size, size + 1):
            yy = y + dy
            if 0 <= yy < self.SCREEN_H:
                self.display.pixel(x, yy, color)
