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

Module: esp32s3_touch_display_190.py

Version:
    1.0.0

Description:
    Board abstraction layer for the Waveshare ESP32-S3 1.9" Touch LCD
    (170x320, ST7789V2 + CST816).

    This module encapsulates:
    - ST7789 display initialization and configuration
    - PWM-based backlight control (active-low)
    - Touch controller integration (CST816)
    - High-level touch event processing via TouchEngine

    It provides a unified and hardware-specific interface for display,
    touch input, and brightness control.

Features:
    - Preconfigured SPI display setup (ST7789)
    - Integrated touch controller (CST816 over I2C)
    - Event-based touch handling (DOWN, MOVE, UP, gestures)
    - PWM backlight control with raw and percentage interface
    - Utility helpers (clear, colors, cross drawing)

Design Notes:
    - The class acts as a hardware abstraction layer (HAL) for the
      Waveshare 1.9" ESP32-S3 board.
    - Touch processing is delegated to TouchEngine to separate hardware
      access from gesture interpretation.
    - The backlight is controlled via PWM and is active-low.
      According to the Waveshare schematic, LCD_BL is connected to IO14.
    - Display orientation is handled via the CST816 mapping logic
      (rotation=270 for landscape), matching the ESP32-C6 1.9" version.
    - The API follows a KISS approach to keep usage simple and efficient
      in MicroPython environments.

Author:
    Thomas Tillig

Year:
    2026
"""


import machine
import st7789py as st7789

from touch_cst816 import TouchCST816, TouchEngine


class ESP32S3TouchDisplay190:
    """
    Board abstraction for the Waveshare ESP32-S3-Touch-LCD-1.9.

    Includes:
    - Display (ST7789/ST7789V2)
    - Touch hardware (CST816)
    - State-based touch engine
    """

    SCREEN_W = 320
    SCREEN_H = 170

    # Display SPI / control pins
    PIN_LCD_RST = 9
    PIN_LCD_SCK = 10
    PIN_LCD_DC = 11
    PIN_LCD_CS = 12
    PIN_LCD_MOSI = 13
    PIN_LCD_BL = 14

    # Touch I2C pins
    PIN_TP_RESET = 17
    PIN_TP_INT = 21
    PIN_TP_SDA = 47
    PIN_TP_SCL = 48

    def __init__(
        self,
        spi_baudrate=40_000_000,
        backlight_freq=5000,
        backlight_on_duty=0,
        touch_move_deadzone=2,
        touch_swipe_threshold=30,
        touch_tap_max_distance=10,
        touch_release_misses=4,
        touch_long_tap_ms=600,
        touch_double_tap_ms=700,
        touch_double_tap_distance=100,
    ):
        self.st7789 = st7789

        self.display = self._create_display(spi_baudrate)
        self.backlight = self._create_backlight(backlight_freq)
        self.set_backlight_raw(backlight_on_duty)

        self.touch = TouchCST816(
            i2c_id=0,
            sda_pin=self.PIN_TP_SDA,
            scl_pin=self.PIN_TP_SCL,
            rst_pin=self.PIN_TP_RESET,
            # The hardware INT pin is IO21, but polling works well and keeps
            # the touch driver simple. Use IO21 later only if the driver gets
            # explicit interrupt support.
            int_pin=None,
            addr=0x15,
            screen_w=self.SCREEN_W,
            screen_h=self.SCREEN_H,
            rotation=270,
        )

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
            width=170,
            height=320,
            reset=machine.Pin(self.PIN_LCD_RST, machine.Pin.OUT),
            dc=machine.Pin(self.PIN_LCD_DC, machine.Pin.OUT),
            cs=machine.Pin(self.PIN_LCD_CS, machine.Pin.OUT),
            backlight=None,
            color_order=st7789.BGR,
            rotation=0,
        )

        disp.inversion_mode(True)
        disp.fill(st7789.BLACK)
        return disp

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

    def colors(self):
        """
        Convenient access to color constants.
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

        Note:
        On this board LCD_BL drives the backlight switch active-low:
        0      = maximum brightness
        65535  = off
        """
        if duty_u16 < 0:
            duty_u16 = 0
        elif duty_u16 > 65535:
            duty_u16 = 65535
        self.backlight.duty_u16(duty_u16)


    def set_backlight_percent(self, percent):
        percent = max(0, min(100, percent))

        target = 65535 - (percent * 65535 // 100)
        current = getattr(self, "_last_bl", 65535)

        step = 2000 if target < current else -2000

        for d in range(current, target, -step):
            self.backlight.duty_u16(d)

        self.backlight.duty_u16(target)
        self._last_bl = target

