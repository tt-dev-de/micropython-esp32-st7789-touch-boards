# easy_rect_test.py
# Simple display test for ESP32 ST7789 touch boards
# Touch interactions are printed to the terminal

# Select your board:
# from esp32c6_touch_display_147 import ESP32C6TouchDisplay147 as Board
from esp32c6_touch_display_190 import ESP32C6TouchDisplay190 as Board

board = Board()
display = board.display
colors = board.colors()

# Clear screen
board.clear(colors.BLACK)

# Outer border
display.rect(0, 0, display.width, display.height, colors.RED)

# Inner centered rectangle
w = display.width // 2
h = display.height // 2
x = (display.width - w) // 2
y = (display.height - h) // 2

display.rect(x, y, w, h, colors.GREEN)

# Touch loop
while True:
    event = board.poll()
    if event:
        print(event)
