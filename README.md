# MicroPython ESP32 ST7789 Touch Boards

MicroPython board abstraction and touch drivers for ESP32-based ST7789 LCD touch displays.

This project provides simple, ready-to-use board abstraction classes for small ESP32 touch display boards using ST7789 displays and capacitive touch controllers.

## Supported boards

| Board | Display | Touch controller | Module |
|---|---:|---|---|
| ESP32-C6 1.47" M-Touch Display | 172x320 | AXS5106L | `esp32c6_touch_display_147.py` |
| Waveshare ESP32-C6 Touch LCD 1.9" | 170x320 | CST816 | `esp32c6_touch_display_190.py` |

Planned:
- ESP32-S3 1.9" 170x320 LCD Touch Display

## Features

- ST7789 display support for 172x320 and 170x320 panels
- Touch support for AXS5106L and CST816
- Landscape coordinate mapping
- Event-based touch handling
- TAP, LONG_TAP, DOUBLE_TAP and SWIPE gesture support
- Simple board abstraction classes for MicroPython applications

## Repository structure

```text
src/
├── st7789py.py
├── touch_axs5106l.py
├── touch_cst816.py
├── esp32c6_touch_display_147.py
└── esp32c6_touch_display_190.py
