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

Module: esp32s3_touch_display_200.py

Version:
    1.0.1

Description:
    Board abstraction layer for the Waveshare ESP32-S3-Touch-LCD-2
    / ESP32-S3 2inch Capacitive Touch Display Development Board
    (240x320, ST7789T3 + CST816D).

    The application coordinate system is landscape:
        SCREEN_W = 320
        SCREEN_H = 240

    This module encapsulates:
    - ST7789T3 display initialization and configuration
    - PWM-based backlight control
    - CST816D capacitive touch integration over I2C
    - High-level touch event processing via TouchEngine

Design Notes:
    - LCD reset and touch reset are on the same LCD_RST net on this board.
      Therefore the touch object is created before the display object. The
      display initialization then performs the final reset/init sequence.
    - Backlight control is active-high on this board:
          0      = off
          65535  = maximum brightness
    - Touch INT is wired to IO46, but polling is used by default because it is
      simple and robust with the existing TouchEngine.
    - Display is initialized in landscape mode by using the existing 240x320
      ST7789 rotation table with rotation=1.

Author:
    Thomas Tillig

Year:
    2026
"""

import machine
import time
import st7789py as st7789

from touch_cst816 import TouchCST816, TouchEngine


class ESP32S3TouchDisplay200:
    """
    Board abstraction for the Waveshare ESP32-S3-Touch-LCD-2.

    Includes:
    - Display (ST7789T3/ST7789-compatible)
    - Touch hardware (CST816D/CST816-compatible)
    - State-based touch engine
    - PWM backlight control
    """

    SCREEN_W = 320
    SCREEN_H = 240

    # Display SPI / control pins from Waveshare schematic / pin table
    PIN_LCD_RST = 0
    PIN_LCD_BL = 1
    PIN_LCD_MOSI = 38
    PIN_LCD_SCK = 39
    PIN_LCD_DC = 42
    PIN_LCD_CS = 45

    # Touch I2C pins from Waveshare schematic / pin table
    # TP_RESET shares LCD_RST on this board.
    PIN_TP_RESET = PIN_LCD_RST
    PIN_TP_INT = 46
    PIN_TP_SCL = 47
    PIN_TP_SDA = 48

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
        use_touch_int=False,
    ):
        self.st7789 = st7789
        self._last_bl = 0

        # Touch first: TP_RESET is the same net as LCD_RST on this board.
        self.touch = self._create_touch(use_touch_int)

        self.display = self._create_display(spi_baudrate)
        self.backlight = self._create_backlight(backlight_freq)

        if boot_backlight_pulse:
            self.set_backlight_percent(10)
            time.sleep_ms(100)

        self.set_backlight_percent(backlight_percent)

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
            miso=None,
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
            rotation=1,  # 240x320 physical panel -> 320x240 landscape
        )

        disp.inversion_mode(True)
        disp.fill(st7789.BLACK)
        return disp

    def _create_touch(self, use_touch_int):
        return TouchCST816(
            i2c_id=0,
            sda_pin=self.PIN_TP_SDA,
            scl_pin=self.PIN_TP_SCL,
            rst_pin=self.PIN_TP_RESET,
            int_pin=self.PIN_TP_INT if use_touch_int else None,
            addr=0x15,
            raw_w=240,
            raw_h=320,
            screen_w=self.SCREEN_W,
            screen_h=self.SCREEN_H,
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

    def poll(self):
        """
        Returns the next touch event or None.
        """
        return self.engine.poll()

    def read_touch(self):
        """
        Direct mapped touch read without the event engine.
        """
        return self.touch.read()

    def scan_touch_i2c(self):
        return self.touch.scan()

    def touch_chip_id(self):
        return self.touch.chip_id()

    def colors(self):
        """
        Convenient access to ST7789 color constants.
        """
        return self.st7789

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
        """
        Sets the raw PWM duty.

        Backlight polarity on this board is active-high:
            0      = off
            65535  = maximum brightness
        """
        if duty_u16 < 0:
            duty_u16 = 0
        elif duty_u16 > 65535:
            duty_u16 = 65535

        self.backlight.duty_u16(duty_u16)
        self._last_bl = duty_u16

    def set_backlight_percent(self, percent):
        """
        Sets brightness in percent.

        0   = off
        100 = maximum brightness
        """
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
