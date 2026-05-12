# touch_test.py
# Touch test for ESP32 ST7789 touch boards without font dependency.
# Touch interactions are printed to the terminal

# Select your board:
# from esp32c6_touch_display_147 import ESP32C6TouchDisplay147 as Board
# from esp32c6_touch_display_190 import ESP32C6TouchDisplay190 as Board
# from esp32s3_touch_display_147 import ESP32S3TouchDisplay147 as Board
from esp32s3_touch_display_190 import ESP32S3TouchDisplay190 as Board
# from esp32s3_touch_display_200 import ESP32S3TouchDisplay200 as Board
# from esp32s3_touch_display_280 import ESP32S3TouchDisplay280 as Board

import time


HEADER_H = 24


def draw_frame(board):
    c = board.colors()
    board.display.rect(0, 0, board.SCREEN_W, board.SCREEN_H, c.WHITE)


def draw_status_bar(board, color):
    c = board.colors()
    board.display.fill_rect(1, 1, board.SCREEN_W - 2, HEADER_H, c.BLACK)
    board.display.fill_rect(6, 6, board.SCREEN_W - 12, HEADER_H - 10, color)
    draw_frame(board)


def clear_screen(board, status_color):
    c = board.colors()
    board.display.fill(c.BLACK)
    draw_frame(board)
    draw_status_bar(board, status_color)


def main():
    board = Board()
    c = board.colors()

    print("I2C scan:", [hex(x) for x in board.scan_touch_i2c()])
    print("Touch test started.")
    print("DOWN = green, MOVE = red, DOUBLE_TAP/LONG_TAP = clear screen")

    clear_screen(board, c.BLUE)

    while True:
        evt = board.poll()

        if evt is not None:
            print(evt)

            etype = evt["type"]
            gesture = evt.get("gesture")

            if etype == "DOWN":
                board.draw_cross(evt["x"], evt["y"], c.GREEN)
                draw_status_bar(board, c.GREEN)

            elif etype == "MOVE":
                board.draw_cross(evt["x"], evt["y"], c.RED)
                draw_status_bar(board, c.RED)

            elif etype == "DOUBLE_TAP":
                clear_screen(board, c.MAGENTA)

            elif etype == "UP":
                if gesture == "LONG_TAP":
                    clear_screen(board, c.YELLOW)

                elif gesture in (
                    "SWIPE_LEFT",
                    "SWIPE_RIGHT",
                    "SWIPE_UP",
                    "SWIPE_DOWN",
                ):
                    draw_status_bar(board, c.CYAN)

                elif gesture == "TAP":
                    draw_status_bar(board, c.WHITE)

                else:
                    draw_status_bar(board, c.BLUE)

        time.sleep_ms(10)


main()
