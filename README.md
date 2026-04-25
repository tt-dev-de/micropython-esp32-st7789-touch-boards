# MicroPython ESP32 ST7789 Touch Boards

MicroPython board abstraction and touch drivers for ESP32-based ST7789 LCD touch displays.

This project provides simple, ready-to-use board abstraction classes for small ESP32 touch display boards using ST7789 displays and capacitive touch controllers.

---

## Supported boards

| Board | Display | Touch controller | Module |
|---|---:|---|---|
| ESP32-C6 1.47" M-Touch Display | 172x320 | AXS5106L | `esp32c6_touch_display_147.py` |
| Waveshare ESP32-C6 Touch LCD 1.9" | 170x320 | CST816 | `esp32c6_touch_display_190.py` |

**Planned:**
- ESP32-S3 1.9" 170x320 LCD Touch Display

---

## Features

- ST7789 display support for 172x320 and 170x320 panels
- Touch support for AXS5106L and CST816
- Landscape coordinate mapping
- Event-based touch handling
- TAP, LONG_TAP, DOUBLE_TAP and SWIPE gesture support
- Simple board abstraction classes for MicroPython applications

---

## Repository structure

```text
src/
├── st7789py.py
├── touch_axs5106l.py
├── touch_cst816.py
├── esp32c6_touch_display_147.py
└── esp32c6_touch_display_190.py
```

---
## Fonts

The examples in this repository do not depend on external fonts.

If you want to use text rendering, compatible bitmap fonts can be found here:

https://github.com/russhughes/st7789py_mpy/tree/master/romfonts

These fonts are designed for the `st7789py` driver and work out of the box.


Example usage:

```python
### Example: Text output with external font

Before running this example, copy a font file (e.g. `vga1_8x16.py`) to your board.

Fonts are available here:  
https://github.com/russhughes/st7789py_mpy/tree/master/romfonts

# Select your board (uncomment ONE line)

# from esp32c6_touch_display_147 import ESP32C6TouchDisplay147 as Board
from esp32c6_touch_display_190 import ESP32C6TouchDisplay190 as Board

import vga1_8x16 as font

board = Board()
display = board.display
colors = board.colors()

# Clear screen
board.clear(colors.BLACK)

# Draw text
display.text(font, "Hello", 10, 10, colors.WHITE, colors.BLACK)
```

## Quick start

Copy the files from `src/` to your MicroPython board.

### Example (1.9" display)

```python
# Works for both 147 and 190 displays
# just change the import

# from esp32c6_touch_display_147 import ESP32C6TouchDisplay147 as Board
from esp32c6_touch_display_190 import ESP32C6TouchDisplay190 as Board

board = ESP32C6TouchDisplay190()
display = board.display
colors = board.colors()

# Clear screen
board.clear(colors.BLACK)

# Outer border (tests full resolution and offsets)
display.rect(0, 0, display.width, display.height, colors.RED)

# Inner centered rectangle
w = display.width // 2
h = display.height // 2
x = (display.width - w) // 2
y = (display.height - h) // 2

display.rect(x, y, w, h, colors.GREEN)

# Touch event loop
while True:
    event = board.poll()
    if event:
        print(event)
```

---

## License

This project is released under the MIT License.

The included `st7789py.py` driver is based on previous MIT-licensed work by:
- Russ Hughes
- Ivan Belokobylskiy
- devbis

Their copyright notices are preserved in the source file.

---

## Author

Thomas Tillig, 2026  
Development assisted by AI tools.
