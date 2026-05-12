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

Module: esp32s3_touch_display_280.py

Version:
    1.0.1

Description:
    Board abstraction layer for the Waveshare ESP32-S3 2.8" Touch LCD
    (320x240, Display: ST7789T3 / ST7789 compatible, + Touch: CST328).

    This module encapsulates:
    - ST7789 display initialization and configuration
    - PWM-based backlight control (active-low)
    - Touch controller integration (CST328)
    - High-level touch event processing via TouchEngine

    It provides a unified and hardware-specific interface for display,
    touch input, and brightness control.

Features:
    - Preconfigured SPI display setup (ST7789)
    - Integrated touch controller (CST328 over I2C)
    - Event-based touch handling (DOWN, MOVE, UP, gestures)
    - PWM backlight control with raw and percentage interface
    - Utility helpers (clear, colors, cross drawing)

Design Notes:
    - The class acts as a hardware abstraction layer (HAL) for the
      Waveshare 2.8" ESP32-S3 board.
    - Touch processing is delegated to TouchEngine to separate hardware
      access from gesture interpretation.
    - The backlight is controlled via PWM and is active-low.
      According to the Waveshare schematic, LCD_BL is connected to IO14.
    - Display orientation is handled via the CST328 mapping logic
      (rotation=270 for landscape), matching the ESP32-S3 2.8" version.
    - The API follows a KISS approach to keep usage simple and efficient
      in MicroPython environments.

Author:
    Thomas Tillig

Year:
    2026
"""

import machine
import time
import st7789py as st7789

from touch_cst328 import TouchCST328, TouchEngine


class ESP32S3TouchDisplay280:
    SCREEN_W = 320
    SCREEN_H = 240

    # LCD pins
    PIN_LCD_BL = 5
    PIN_LCD_RST = 39
    PIN_LCD_SCK = 40
    PIN_LCD_DC = 41
    PIN_LCD_CS = 42
    PIN_LCD_MOSI = 45
    PIN_LCD_MISO = 46

    # Touch pins CST328
    PIN_TP_SDA = 1
    PIN_TP_RST = 2
    PIN_TP_SCL = 3
    PIN_TP_INT = 4

    def __init__(
        self,
        spi_baudrate=40_000_000,
        backlight_freq=5000,
        backlight_percent=100,
        boot_backlight_pulse=True,

        touch_move_deadzone=2,
        touch_swipe_threshold=30,
        touch_tap_max_distance=10,
        touch_release_misses=4,
        touch_long_tap_ms=600,
        touch_double_tap_ms=700,
        touch_double_tap_distance=100,
        use_touch_int=False,  # CST328: polling is more reliable than INT on this board
    ):
        self.st7789 = st7789
        self._last_bl = 0

        self.display = self._create_display(spi_baudrate)
        self.backlight = self._create_backlight(backlight_freq)

        if boot_backlight_pulse:
            self.set_backlight_percent(10)
            time.sleep_ms(100)

        self.set_backlight_percent(backlight_percent)

        self.touch = self._create_touch(use_touch_int)

        self.engine = TouchEngine(
            self.touch,
            move_deadzone=touch_move_deadzone,
            swipe_threshold=touch_swipe_threshold,
            tap_max_distance=touch_tap_max_distance,
            release_misses=touch_release_misses,
            long_tap_ms=touch_long_tap_ms,
            double_tap_ms=touch_double_tap_ms,
            double_tap_distance=touch_double_tap_distance,
        )

    def _create_display(self, spi_baudrate):
        spi = machine.SPI(
            1,
            baudrate=spi_baudrate,
            polarity=0,
            phase=0,
            sck=machine.Pin(self.PIN_LCD_SCK),
            mosi=machine.Pin(self.PIN_LCD_MOSI),
            miso=machine.Pin(self.PIN_LCD_MISO),
        )

        disp = st7789.ST7789(
            spi,
            width=240,
            height=320,
            reset=machine.Pin(self.PIN_LCD_RST, machine.Pin.OUT),
            dc=machine.Pin(self.PIN_LCD_DC, machine.Pin.OUT),
            cs=machine.Pin(self.PIN_LCD_CS, machine.Pin.OUT),
            backlight=None,
            color_order=st7789.BGR,
            rotation=1,
        )

        disp.inversion_mode(True)
        disp.fill(st7789.BLACK)
        return disp

    def _create_touch(self, use_touch_int):
        return TouchCST328(
            i2c_id=0,
            sda_pin=self.PIN_TP_SDA,
            scl_pin=self.PIN_TP_SCL,
            rst_pin=self.PIN_TP_RST,
            int_pin=self.PIN_TP_INT if use_touch_int else None,
            addr=0x1A,

            raw_w=240,
            raw_h=320,
            screen_w=self.SCREEN_W,
            screen_h=self.SCREEN_H,

            # Falls Achsen nicht passen: 90 testen
            rotation=270,

            raw_x_min=0,
            raw_x_max=239,
            raw_y_min=0,
            raw_y_max=319,
        )

    def _create_backlight(self, freq):
        return machine.PWM(machine.Pin(self.PIN_LCD_BL), freq=freq)

    def clear(self, color=None):
        if color is None:
            color = self.st7789.BLACK
        self.display.fill(color)

    def colors(self):
        return self.st7789

    def poll(self):
        """
        Returns next touch event or None.
        """
        return self.engine.poll()

    def read_touch(self):
        """
        Direct mapped touch read without event engine.
        """
        return self.touch.read()

    def scan_touch_i2c(self):
        return self.touch.scan()

    def touch_chip_id(self):
        return self.touch.chip_id()

    def draw_cross(self, x, y, color, size=4):
        for dx in range(-size, size + 1):
            xx = x + dx
            if 0 <= xx < self.SCREEN_W and 0 <= y < self.SCREEN_H:
                self.display.pixel(xx, y, color)

        for dy in range(-size, size + 1):
            yy = y + dy
            if 0 <= x < self.SCREEN_W and 0 <= yy < self.SCREEN_H:
                self.display.pixel(x, yy, color)

    def set_backlight_raw(self, duty_u16):
        if duty_u16 < 0:
            duty_u16 = 0
        elif duty_u16 > 65535:
            duty_u16 = 65535

        self.backlight.duty_u16(duty_u16)
        self._last_bl = duty_u16

    def set_backlight_percent(self, percent):
        percent = max(0, min(100, percent))
        target = percent * 65535 // 100
        current = getattr(self, "_last_bl", 0)

        if target == current:
            self.backlight.duty_u16(target)
            return

        step = 2000 if target > current else -2000

        for duty in range(current, target, step):
            self.backlight.duty_u16(duty)
            time.sleep_ms(1)

        self.backlight.duty_u16(target)
        self._last_bl = target
