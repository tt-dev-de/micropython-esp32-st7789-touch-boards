# test_all_fonts.py
#
# Font browser for ESP32 ST7789 touch boards
# The Font Files must be located in /fonts on the ESP32, with names like font_*.py, e.g. font_12x24_spleen.py
# To copy all font files from your local /fonts directory to ESP32, you can use: mpremote cp -r fonts :/
# It is recommended to have a /fonts/__init__.py file on the ESP32, even if it's empty, to make imports work properly.
# To check if all files copied correctly, you can use: mpremote ls /fonts

# Scans /fonts on the ESP32 automatically.
# Every file matching /fonts/font_*.py is tested.
#
# Console:
#   +  next page/font
#   -  previous page/font
#   q  quit

import time
import sys
import uselect
import gc
import os

# ------------------------------------------------------------
# Board selection
# ------------------------------------------------------------

# Select your board:
BOARD_TYPE = "S3_190"  # "C6_147" or "C6_190" or "S3_147" or "S3_190" or "S3_200" or "S3_280"

if BOARD_TYPE == "C6_147":
    from esp32c6_touch_display_147 import ESP32C6TouchDisplay147 as Board
elif BOARD_TYPE == "C6_190":
    from esp32c6_touch_display_190 import ESP32C6TouchDisplay190 as Board
elif BOARD_TYPE == "S3_147":
    from esp32s3_touch_display_147 import ESP32S3TouchDisplay147 as Board
elif BOARD_TYPE == "S3_190":
    from esp32s3_touch_display_190 import ESP32S3TouchDisplay190 as Board
elif BOARD_TYPE == "S3_200":
    from esp32s3_touch_display_200 import ESP32S3TouchDisplay200 as Board
elif BOARD_TYPE == "S3_280":
    from esp32s3_touch_display_280 import ESP32S3TouchDisplay280 as Board
else:
    raise ValueError(f"Unsupported BOARD_TYPE: {BOARD_TYPE}")

# ------------------------------------------------------------
# Font directory scan
# ------------------------------------------------------------

FONT_DIR = "fonts"          # directory on the ESP32: /fonts
FONT_PREFIX = "font_"
FONT_SUFFIX = ".py"

# This font is only used for the header line.
# It should also be located in /fonts.
HEADER_FONT_NAME = "font_12x24_ter_u24n"


# ------------------------------------------------------------
# Settings
# ------------------------------------------------------------

FIRST_CHAR = 32
LAST_CHAR = 126

CHAR_SPACING_X = 2
CHAR_SPACING_Y = 4

HEADER_H = 28
HEADER_X = 2
HEADER_Y = 2

GRID_X = 2
GRID_Y = HEADER_H + 4


# ------------------------------------------------------------
# Helpers
# ------------------------------------------------------------

def list_font_names():
    """
    Return all module names from /fonts that match font_*.py.

    Example:
        /fonts/font_12x24_spleen.py  ->  font_12x24_spleen
    """
    try:
        files = os.listdir("/" + FONT_DIR)
    except Exception:
        try:
            files = os.listdir(FONT_DIR)
        except Exception as e:
            print("Cannot list font directory:", FONT_DIR, e)
            return []

    names = []

    for filename in files:
        if not filename.startswith(FONT_PREFIX):
            continue
        if not filename.endswith(FONT_SUFFIX):
            continue
        if filename == "__init__.py":
            continue

        names.append(filename[:-len(FONT_SUFFIX)])

    names.sort()
    return names


def import_font(module_name):
    # Needs /fonts/__init__.py on MicroPython.
    return __import__(FONT_DIR + "." + module_name, None, None, [module_name])


def get_font_size(font):
    width = getattr(font, "WIDTH", None)
    height = getattr(font, "HEIGHT", None)

    if width is None:
        width = getattr(font, "FONT_WIDTH", None)
    if height is None:
        height = getattr(font, "FONT_HEIGHT", None)

    if width is None or height is None:
        raise ValueError("Font has no WIDTH/HEIGHT information")

    return int(width), int(height)


def get_char_range(font):
    first = getattr(font, "FIRST", FIRST_CHAR)
    last = getattr(font, "LAST", LAST_CHAR)

    first = max(int(first), FIRST_CHAR)
    last = min(int(last), LAST_CHAR)

    return first, last


def read_key():
    if uselect.select([sys.stdin], [], [], 0)[0]:
        return sys.stdin.read(1)
    return None


def clear_screen(board, color):
    board.display.fill_rect(0, 0, board.SCREEN_W, board.SCREEN_H, color)


def draw_header(board, colors, header_font, text):
    board.display.fill_rect(0, 0, board.SCREEN_W, HEADER_H, colors.BLACK)

    try:
        board.display.text(
            header_font,
            text,
            HEADER_X,
            HEADER_Y,
            colors.YELLOW,
            colors.BLACK,
        )
    except Exception:
        # If header font is missing/incompatible, fail silently.
        pass


def page_count_for_font(board, font):
    fw, fh = get_font_size(font)
    first, last = get_char_range(font)

    cols = max(1, (board.SCREEN_W - GRID_X) // (fw + CHAR_SPACING_X))
    rows = max(1, (board.SCREEN_H - GRID_Y) // (fh + CHAR_SPACING_Y))

    chars_per_page = max(1, cols * rows)
    total_chars = max(1, last - first + 1)

    return (total_chars + chars_per_page - 1) // chars_per_page


def draw_font_page(board, colors, font, font_name, page_index, header_font):
    clear_screen(board, colors.BLACK)

    fw, fh = get_font_size(font)
    first, last = get_char_range(font)

    cols = max(1, (board.SCREEN_W - GRID_X) // (fw + CHAR_SPACING_X))
    rows = max(1, (board.SCREEN_H - GRID_Y) // (fh + CHAR_SPACING_Y))

    chars_per_page = max(1, cols * rows)
    total_chars = max(1, last - first + 1)
    pages = (total_chars + chars_per_page - 1) // chars_per_page

    page_index = max(0, min(page_index, pages - 1))

    header = font_name + ".py" 
    """
    header = "{}  {}x{}  page {}/{}".format(
        font_name + ".py",
        fw,
        fh,
        page_index + 1,
        pages,
    )"""

    draw_header(board, colors, header_font, header)

    start_code = first + page_index * chars_per_page
    end_code = min(last, start_code + chars_per_page - 1)

    code = start_code

    for row in range(rows):
        y = GRID_Y + row * (fh + CHAR_SPACING_Y)

        for col in range(cols):
            if code > end_code:
                return page_index, pages

            x = GRID_X + col * (fw + CHAR_SPACING_X)

            try:
                board.display.text(
                    font,
                    chr(code),
                    x,
                    y,
                    colors.WHITE,
                    colors.BLACK,
                )
            except Exception:
                # Skip unsupported/problematic glyphs.
                pass

            code += 1

    return page_index, pages


def load_font_or_none(name):
    try:
        font = import_font(name)
        get_font_size(font)
        return font
    except Exception as e:
        print("Font load failed:", name, e)
        return None


def main():
    board = Board()
    colors = board.colors()

    try:
        board.set_backlight_percent(100)
    except Exception:
        pass

    print()
    print("Font browser")
    print("-------------")
    print("Scanning /{} for {}*.py".format(FONT_DIR, FONT_PREFIX))
    print("+ = next page/font")
    print("- = previous page/font")
    print("q = quit")
    print()

    font_names = list_font_names()

    if not font_names:
        print("No font files found in /{}.".format(FONT_DIR))
        print("Expected files like /{}/font_12x24_spleen.py".format(FONT_DIR))
        return

    print("Found {} font file(s):".format(len(font_names)))
    for name in font_names:
        print(" ", name)
    print()

    header_font = load_font_or_none(HEADER_FONT_NAME)

    fonts = []

    for name in font_names:
        font = load_font_or_none(name)
        if font is not None:
            fonts.append((name, font))

    if not fonts:
        print("No fonts loaded.")
        return

    if header_font is None:
        print("Header font missing:", HEADER_FONT_NAME)
        print("Using first loaded font as fallback.")
        header_font = fonts[0][1]

    font_index = 0
    page_index = 0

    while True:
        gc.collect()

        font_name, font = fonts[font_index]

        if header_font is None:
            header_font = font

        page_index, pages = draw_font_page(
            board,
            colors,
            font,
            font_name,
            page_index,
            header_font,
        )

        print(
            "Font {}/{}: {}   page {}/{}".format(
                font_index + 1,
                len(fonts),
                font_name,
                page_index + 1,
                pages,
            )
        )

        while True:
            key = read_key()

            if key == "+":
                if page_index < pages - 1:
                    page_index += 1
                else:
                    font_index = (font_index + 1) % len(fonts)
                    page_index = 0
                break

            elif key == "-":
                if page_index > 0:
                    page_index -= 1
                else:
                    font_index = (font_index - 1) % len(fonts)
                    prev_font = fonts[font_index][1]
                    page_index = page_count_for_font(board, prev_font) - 1
                break

            elif key in ("q", "Q"):
                clear_screen(board, colors.BLACK)
                print("Quit.")
                return

            time.sleep(0.05)


main()
