# touch_crosshair.py
# Draws a cross at touch position

# from esp32c6_touch_display_147 import ESP32C6TouchDisplay147 as Board
# from esp32c6_touch_display_190 import ESP32C6TouchDisplay190 as Board
from esp32s3_touch_display_190 import ESP32S3TouchDisplay190 as Board

board = Board()
display = board.display
colors = board.colors()

board.clear(colors.BLACK)

while True:
    event = board.poll()
    if event and event["type"] in ("DOWN", "MOVE"):
        x = event["x"]
        y = event["y"]

        # Clear screen lightly (optional: remove for trails)
        board.clear(colors.BLACK)

        # Draw crosshair
        board.draw_cross(x, y, colors.YELLOW)

        print(event)
