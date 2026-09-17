"""
Pure-Python Icon Forge and Rasterizer.

Generates scalable vector SVG icons (standard and maskable safe-zone compliant),
Windows favicon.ico binary assets, uncompressed 32-bit BMPs, and complete PWA icon packs.
100% Python Standard Library - zero third-party dependencies.
"""

from __future__ import annotations

import math
import struct
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

from .models import IconSpec
from .compat import atomic_write_bytes, atomic_write_text, ensure_dir, normalize_path


STANDARD_ICON_SIZES: List[int] = [16, 32, 48, 72, 96, 128, 144, 152, 180, 192, 384, 512, 1024]

# Built-in SVG glyph path presets (viewBox 0 0 24 24)
SVG_GLYPHS: Dict[str, str] = {
    "sparkles": "M12 2L14.4 7.6L20 10L14.4 12.4L12 18L9.6 12.4L4 10L9.6 7.6L12 2ZM19 17L20.2 19.8L23 21L20.2 22.2L19 25L17.8 22.2L15 21L17.8 19.8L19 17ZM5 17L6 19.4L8.5 20.5L6 21.6L5 24L4 21.6L1.5 20.5L4 19.4L5 17Z",
    "bolt": "M13 2L3 14H12L11 22L21 10H12L13 2Z",
    "code": "M8.7 15.9L4.8 12L8.7 8.1L7.3 6.7L2 12L7.3 17.3L8.7 15.9ZM15.3 15.9L19.2 12L15.3 8.1L16.7 6.7L22 12L16.7 17.3L15.3 15.9ZM14.1 4L9.9 20L11.8 20.5L16 4.5L14.1 4Z",
    "rocket": "M12 2.5C12 2.5 16.5 5 16.5 11C16.5 13.5 15.5 15.8 14 17.5L14 20.5L12 19.5L10 20.5L10 17.5C8.5 15.8 7.5 13.5 7.5 11C7.5 5 12 2.5 12 2.5ZM12 7.5C10.9 7.5 10 8.4 10 9.5C10 10.6 10.9 11.5 12 11.5C13.1 11.5 14 10.6 14 9.5C14 8.4 13.1 7.5 12 7.5ZM5 14.5L7.5 15.5L6.5 18.5L3 17L5 14.5ZM19 14.5L21 17L17.5 18.5L16.5 15.5L19 14.5Z",
    "cube": "M12 2L2 7L12 12L22 7L12 2ZM2 17L12 22L22 17V9.5L12 14.5L2 9.5V17Z",
    "store": "M20 4H4V2H20V4ZM21 6H3L2 12V20C2 20.55 2.45 21 3 21H21C21.55 21 22 20.55 22 20V12L21 6ZM4 19V12.75C4.6 12.91 5.25 13 6 13C7.25 13 8.4 12.4 9 11.5C9.6 12.4 10.75 13 12 13C13.25 13 14.4 12.4 15 11.5C15.6 12.4 16.75 13 18 13C18.75 13 19.4 12.91 20 12.75V19H4Z",
    "chart": "M19 3H5C3.9 3 3 3.9 3 5V19C3 20.1 3.9 21 5 21H19C20.1 21 21 20.1 21 19V5C21 3.9 20.1 3H19ZM9 17H7V10H9V17ZM13 17H11V7H13V17ZM17 17H15V13H17V17Z",
    "music": "M12 3V13.55C11.41 13.21 10.73 13 10 13C7.79 13 6 14.79 6 17C6 19.21 7.79 21 10 21C12.21 21 14 19.21 14 17V7H18V3H12Z",
    "terminal": "M20 4H4C2.89 4 2 4.89 2 6V18C2 19.11 2.89 20 4 20H20C21.11 20 22 19.11 22 18V6C22 4.89 21.11 4 20 4ZM6.5 15.5L5.09 14.09L7.67 11.5L5.09 8.91L6.5 7.5L10.5 11.5L6.5 15.5ZM17 15H11V13H17V15Z",
    "chat": "M20 2H4C2.9 2 2 2.9 2 4V22L6 18H20C21.1 18 22 17.1 22 16V4C22 2.9 21.1 2 20 2ZM20 16H5.17L4 17.17V4H20V16Z",
    "check": "M9 16.17L4.83 12L3.41 13.41L9 19L21 7L19.59 5.59L9 16.17Z",
    "heart": "M12 21.35L10.55 20.03C5.4 15.36 2 12.28 2 8.5C2 5.42 4.42 3 7.5 3C9.24 3 10.91 3.81 12 5.09C13.09 3.81 14.76 3 16.5 3C19.58 3 22 5.42 22 8.5C22 12.28 18.6 15.36 13.45 20.04L12 21.35Z",
    "book": "M18 2H6C4.9 2 4 2.9 4 4V20C4 21.1 4.9 22 6 22H18C19.1 22 20 21.1 20 20V4C20 2.9 19.1 2 18 2ZM6 4H11V12L8.5 10.5L6 12V4Z",
    "game": "M21 6H3C1.9 6 1 6.9 1 8V16C1 17.1 1.9 18 3 18H21C22.1 18 23 17.1 23 16V8C23 6.9 22.1 6 21 6ZM10 13H8V15H6V13H4V11H6V9H8V11H10V13ZM15.5 14C14.67 14 14 13.33 14 12.5C14 11.67 14.67 11 15.5 11C16.33 11 17 11.67 17 12.5C17 13.33 16.33 14 15.5 14ZM18.5 11C17.67 11 17 10.33 17 9.5C17 8.67 17.67 8 18.5 8C19.33 8 20 8.67 20 9.5C20 10.33 19.33 11 18.5 11Z",
    "shield": "M12 2L4 5V11.09C4 16.14 7.41 20.85 12 22C16.59 20.85 20 16.14 20 11.09V5L12 2ZM12 11.99H18C17.47 15.46 15.12 18.54 12 19.93V12H6V6.3L12 4.05V11.99Z",
    "globe": "M12 2C6.48 2 2 6.48 2 12C2 17.52 6.48 22 12 22C17.52 22 22 17.52 22 12C22 6.48 17.52 2 12 2ZM11 19.93C7.05 19.44 4 16.08 4 12C4 11.38 4.08 10.78 4.21 10.21L9 15V16C9 17.1 9.9 18 11 18V19.93ZM17.9 17.39C17.64 16.58 16.9 16 16 16H15V13C15 12.45 14.55 12 14 12H8V10H10C10.55 10 11 9.55 11 9V7H13C14.1 7 15 6.1 15 5V4.59C17.93 5.77 20 8.64 20 12C20 14.08 19.2 15.97 17.9 17.39Z",
    "star": "M12 17.27L18.18 21L16.54 13.97L22 9.24L14.81 8.63L12 2L9.19 8.63L2 9.24L7.46 13.97L5.82 21L12 17.27Z",
}

# 5x7 Basic Bitmap Font for pure-python rasterizer (A-Z, 0-9, symbols)
BITMAP_FONT_5X7: Dict[str, List[int]] = {
    "A": [0b01110, 0b10001, 0b10001, 0b11111, 0b10001, 0b10001, 0b10001],
    "B": [0b11110, 0b10001, 0b10001, 0b11110, 0b10001, 0b10001, 0b11110],
    "C": [0b01111, 0b10000, 0b10000, 0b10000, 0b10000, 0b10000, 0b01111],
    "D": [0b11110, 0b10001, 0b10001, 0b10001, 0b10001, 0b10001, 0b11110],
    "E": [0b11111, 0b10000, 0b10000, 0b11110, 0b10000, 0b10000, 0b11111],
    "F": [0b11111, 0b10000, 0b10000, 0b11110, 0b10000, 0b10000, 0b10000],
    "G": [0b01111, 0b10000, 0b10000, 0b10111, 0b10001, 0b10001, 0b01111],
    "H": [0b10001, 0b10001, 0b10001, 0b11111, 0b10001, 0b10001, 0b10001],
    "I": [0b01110, 0b00100, 0b00100, 0b00100, 0b00100, 0b00100, 0b01110],
    "J": [0b00001, 0b00001, 0b00001, 0b00001, 0b10001, 0b10001, 0b01110],
    "K": [0b10001, 0b10010, 0b10100, 0b11000, 0b10100, 0b10010, 0b10001],
    "L": [0b10000, 0b10000, 0b10000, 0b10000, 0b10000, 0b10000, 0b11111],
    "M": [0b10001, 0b11011, 0b10101, 0b10101, 0b10001, 0b10001, 0b10001],
    "N": [0b10001, 0b11001, 0b10101, 0b10011, 0b10001, 0b10001, 0b10001],
    "O": [0b01110, 0b10001, 0b10001, 0b10001, 0b10001, 0b10001, 0b01110],
    "P": [0b11110, 0b10001, 0b10001, 0b11110, 0b10000, 0b10000, 0b10000],
    "Q": [0b01110, 0b10001, 0b10001, 0b10001, 0b10101, 0b10011, 0b01111],
    "R": [0b11110, 0b10001, 0b10001, 0b11110, 0b10100, 0b10010, 0b10001],
    "S": [0b01111, 0b10000, 0b10000, 0b01110, 0b00001, 0b00001, 0b11110],
    "T": [0b11111, 0b00100, 0b00100, 0b00100, 0b00100, 0b00100, 0b00100],
    "U": [0b10001, 0b10001, 0b10001, 0b10001, 0b10001, 0b10001, 0b01110],
    "V": [0b10001, 0b10001, 0b10001, 0b10001, 0b01010, 0b01010, 0b00100],
    "W": [0b10001, 0b10001, 0b10001, 0b10101, 0b10101, 0b11011, 0b10001],
    "X": [0b10001, 0b10001, 0b01010, 0b00100, 0b01010, 0b10001, 0b10001],
    "Y": [0b10001, 0b10001, 0b01010, 0b00100, 0b00100, 0b00100, 0b00100],
    "Z": [0b11111, 0b00001, 0b00010, 0b00100, 0b01000, 0b10000, 0b11111],
    "0": [0b01110, 0b10011, 0b10101, 0b10101, 0b11001, 0b10001, 0b01110],
    "1": [0b00100, 0b01100, 0b00100, 0b00100, 0b00100, 0b00100, 0b01110],
    "2": [0b01110, 0b10001, 0b00001, 0b00010, 0b00100, 0b01000, 0b11111],
    "3": [0b11110, 0b00001, 0b00001, 0b01110, 0b00001, 0b00001, 0b11110],
    "4": [0b00010, 0b00110, 0b01010, 0b10010, 0b11111, 0b00010, 0b00010],
    "5": [0b11111, 0b10000, 0b11110, 0b00001, 0b00001, 0b10001, 0b01110],
    "6": [0b00110, 0b01000, 0b10000, 0b11110, 0b10001, 0b10001, 0b01110],
    "7": [0b11111, 0b00001, 0b00010, 0b00100, 0b01000, 0b01000, 0b01000],
    "8": [0b01110, 0b10001, 0b10001, 0b01110, 0b10001, 0b10001, 0b01110],
    "9": [0b01110, 0b10001, 0b10001, 0b01111, 0b00001, 0b00010, 0b01100],
    "+": [0b00000, 0b00100, 0b00100, 0b11111, 0b00100, 0b00100, 0b00000],
    "-": [0b00000, 0b00000, 0b00000, 0b11111, 0b00000, 0b00000, 0b00000],
    "?": [0b01110, 0b10001, 0b00001, 0b00110, 0b00100, 0b00000, 0b00100],
    "!": [0b00100, 0b00100, 0b00100, 0b00100, 0b00100, 0b00000, 0b00100],
}


def parse_color_rgba(color_str: str) -> Tuple[int, int, int, int]:
    """
    Parses a hex color (#RGB, #RRGGBB, #RRGGBBAA) or rgb/rgba string into (r, g, b, a).
    Defaults to (26, 115, 232, 255) on invalid input.
    """
    clean = str(color_str).strip()
    named_colors: Dict[str, Tuple[int, int, int, int]] = {
        "black": (0, 0, 0, 255),
        "white": (255, 255, 255, 255),
        "red": (234, 67, 53, 255),
        "green": (52, 168, 83, 255),
        "blue": (26, 115, 232, 255),
        "yellow": (251, 188, 4, 255),
        "purple": (156, 39, 176, 255),
        "orange": (255, 112, 67, 255),
        "transparent": (0, 0, 0, 0),
    }
    if clean.lower() in named_colors:
        return named_colors[clean.lower()]

    if clean.startswith("#"):
        hex_val = clean[1:]
        if len(hex_val) == 3:  # #RGB
            r = int(hex_val[0] * 2, 16)
            g = int(hex_val[1] * 2, 16)
            b = int(hex_val[2] * 2, 16)
            return (r, g, b, 255)
        elif len(hex_val) == 6:  # #RRGGBB
            r = int(hex_val[0:2], 16)
            g = int(hex_val[2:4], 16)
            b = int(hex_val[4:6], 16)
            return (r, g, b, 255)
        elif len(hex_val) == 8:  # #RRGGBBAA
            r = int(hex_val[0:2], 16)
            g = int(hex_val[2:4], 16)
            b = int(hex_val[4:6], 16)
            a = int(hex_val[6:8], 16)
            return (r, g, b, a)

    # Simple rgb(r,g,b) / rgba(r,g,b,a) parsing
    if clean.startswith("rgb"):
        try:
            parts = clean[clean.find("(") + 1 : clean.find(")")].split(",")
            r = int(parts[0].strip())
            g = int(parts[1].strip())
            b = int(parts[2].strip())
            a = int(float(parts[3].strip()) * 255) if len(parts) > 3 else 255
            return (r, g, b, a)
        except Exception:
            pass

    return (26, 115, 232, 255)  # Default Google Blue


def _adjust_color_brightness(rgba: Tuple[int, int, int, int], factor: float) -> str:
    """Adjusts color brightness and returns hex string."""
    r = min(255, max(0, int(rgba[0] * factor)))
    g = min(255, max(0, int(rgba[1] * factor)))
    b = min(255, max(0, int(rgba[2] * factor)))
    return f"#{r:02x}{g:02x}{b:02x}"


def generate_icon_svg(
    name_or_letter: str = "PWA",
    bg_color: str = "#1a73e8",
    fg_color: str = "#ffffff",
    shape: str = "rounded",
    icon_name: Optional[str] = "sparkles",
    maskable: bool = False,
    size: int = 512,
    name: Optional[str] = None,
    letter: Optional[str] = None,
    **kwargs: Any,
) -> str:
    """
    Generates scalable vector SVG icon markup.

    If `maskable=True`:
      - Full-bleed background filling 100% of canvas.
      - Core artwork strictly scaled inside the central 80% safe zone circle (diameter 0.8 * size).

    Shapes supported when not maskable:
      - 'circle', 'rounded' (default rounded rect), 'square', 'squircle', 'hex'.
    """
    if letter:
        name_or_letter = letter
    elif name:
        name_or_letter = name


    bg_rgba = parse_color_rgba(bg_color)
    grad_start = _adjust_color_brightness(bg_rgba, 1.15)
    grad_end = _adjust_color_brightness(bg_rgba, 0.85)

    gradient_def = f"""
    <defs>
      <linearGradient id="pwa-bg-grad" x1="0%" y1="0%" x2="100%" y2="100%">
        <stop offset="0%" stop-color="{grad_start}" />
        <stop offset="100%" stop-color="{grad_end}" />
      </linearGradient>
      <filter id="pwa-shadow" x="-10%" y="-10%" width="120%" height="120%">
        <feDropShadow dx="0" dy="{size * 0.02:.1f}" stdDeviation="{size * 0.03:.1f}" flood-opacity="0.25" />
      </filter>
    </defs>"""

    # Background Geometry
    if maskable:
        # Full bleed rectangle without radius for Android adaptive masking
        bg_element = f'<rect width="{size}" height="{size}" fill="url(#pwa-bg-grad)" />'
        # Scale content inside 80% safe zone
        scale_factor = 0.80
    else:
        if shape == "circle":
            bg_element = f'<circle cx="{size/2}" cy="{size/2}" r="{size/2}" fill="url(#pwa-bg-grad)" />'
        elif shape == "square":
            bg_element = f'<rect width="{size}" height="{size}" fill="url(#pwa-bg-grad)" />'
        elif shape == "hex":
            # 6-pointed regular hexagon points
            r = size / 2
            pts = []
            for i in range(6):
                angle = math.radians(60 * i - 30)
                px = size / 2 + r * math.cos(angle)
                py = size / 2 + r * math.sin(angle)
                pts.append(f"{px:.1f},{py:.1f}")
            bg_element = f'<polygon points="{" ".join(pts)}" fill="url(#pwa-bg-grad)" />'
        else:  # rounded / squircle default
            rx = size * 0.22
            bg_element = f'<rect width="{size}" height="{size}" rx="{rx:.1f}" fill="url(#pwa-bg-grad)" />'
        scale_factor = 0.88

    # Foreground Artwork (Glyph preset or Letter Typography)
    glyph_path = SVG_GLYPHS.get(icon_name.lower() if icon_name else "")
    
    if glyph_path:
        # SVG_GLYPHS are designed in 24x24 viewBox.
        # Scale & center glyph to safe artwork bounds
        art_size = size * 0.48 * scale_factor
        offset = (size - art_size) / 2
        scale_val = art_size / 24.0
        fg_element = (
            f'<g transform="translate({offset:.1f}, {offset:.1f}) scale({scale_val:.4f})" '
            f'filter="url(#pwa-shadow)">\n'
            f'  <path d="{glyph_path}" fill="{fg_color}" />\n'
            f'</g>'
        )
    else:
        # Typography Letter Fallback (1-3 characters)
        chars = name_or_letter.strip().upper()[:3] or "PWA"
        font_size = (size * 0.40 * scale_factor) if len(chars) <= 2 else (size * 0.28 * scale_factor)
        fg_element = (
            f'<text x="50%" y="54%" font-family="system-ui, -apple-system, BlinkMacSystemFont, \'Segoe UI\', Roboto, sans-serif" '
            f'font-size="{font_size:.1f}" font-weight="800" fill="{fg_color}" text-anchor="middle" '
            f'dominant-baseline="central" filter="url(#pwa-shadow)">{chars}</text>'
        )

    svg = f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {size} {size}" width="{size}" height="{size}">
{gradient_def}
  {bg_element}
  {fg_element}
</svg>"""

    return svg.strip() + "\n"


def generate_bmp(
    width: int,
    height: int,
    bg_color: Tuple[int, int, int, int] = (26, 115, 232, 255),
    fg_color: Tuple[int, int, int, int] = (255, 255, 255, 255),
    letter: str = "P"
) -> bytes:
    """
    Generates uncompressed 32-bit Windows BMP image binary without third-party dependencies.
    Renders background and rasterized bitmap letter/symbol.
    """
    header_size = 14
    dib_size = 40
    pixel_offset = header_size + dib_size
    image_bytes_size = width * height * 4
    file_size = pixel_offset + image_bytes_size

    # BMP File Header (14 bytes)
    file_header = struct.pack(
        "<2sIHHI",
        b"BM",
        file_size,
        0,  # reserved 1
        0,  # reserved 2
        pixel_offset
    )

    # BITMAPINFOHEADER (40 bytes)
    dib_header = struct.pack(
        "<IIIHHIIIIII",
        dib_size,
        width,
        height,  # positive = bottom-up
        1,       # color planes
        32,      # bits per pixel
        0,       # BI_RGB (uncompressed)
        image_bytes_size,
        2835,    # 72 DPI (horizontal pels/m)
        2835,    # 72 DPI (vertical pels/m)
        0,       # total colors
        0        # important colors
    )

    # Create pixel grid (height rows from bottom to top, width columns)
    # BGRA ordering in memory
    bg_b, bg_g, bg_r, bg_a = bg_color[2], bg_color[1], bg_color[0], bg_color[3]
    fg_b, fg_g, fg_r, fg_a = fg_color[2], fg_color[1], fg_color[0], fg_color[3]

    pixel_data = bytearray(image_bytes_size)

    # Fill background
    for y in range(height):
        for x in range(width):
            idx = (y * width + x) * 4
            pixel_data[idx + 0] = bg_b
            pixel_data[idx + 1] = bg_g
            pixel_data[idx + 2] = bg_r
            pixel_data[idx + 3] = bg_a

    # Rasterize letter if in bitmap font
    char_key = letter.upper()[:1] if letter else "P"
    font_matrix = BITMAP_FONT_5X7.get(char_key, BITMAP_FONT_5X7.get("P", []))

    if font_matrix and width >= 8 and height >= 8:
        # Scale font to fit centered in bitmap
        font_w = 5
        font_h = 7
        scale_x = max(1, width // 10)
        scale_y = max(1, height // 10)
        
        total_font_w = font_w * scale_x
        total_font_h = font_h * scale_y
        
        start_x = (width - total_font_w) // 2
        start_y = (height - total_font_h) // 2

        for r_idx, row_bits in enumerate(font_matrix):
            # In BMP bottom-up: row 0 of font is at top of letter, so invert Y
            y_pos_base = start_y + (font_h - 1 - r_idx) * scale_y
            for c_idx in range(font_w):
                if (row_bits >> (font_w - 1 - c_idx)) & 1:
                    x_pos_base = start_x + c_idx * scale_x
                    for dy in range(scale_y):
                        for dx in range(scale_x):
                            px = x_pos_base + dx
                            py = y_pos_base + dy
                            if 0 <= px < width and 0 <= py < height:
                                idx = (py * width + px) * 4
                                pixel_data[idx + 0] = fg_b
                                pixel_data[idx + 1] = fg_g
                                pixel_data[idx + 2] = fg_r
                                pixel_data[idx + 3] = fg_a

    return file_header + dib_header + bytes(pixel_data)


def generate_favicon_ico(
    bg_color: str = "#1a73e8",
    fg_color: str = "#ffffff",
    letter: str = "P",
    sizes: Tuple[int, ...] = (16, 32, 48)
) -> bytes:
    """
    Generates a standard multi-resolution Windows Favicon .ico file in pure Python.
    Uses 32-bit RGBA BMP DIB frames with zero third-party dependencies.
    """
    bg_rgba = parse_color_rgba(bg_color)
    fg_rgba = parse_color_rgba(fg_color)

    num_images = len(sizes)
    # Header: 6 bytes
    ico_header = struct.pack("<HHH", 0, 1, num_images)
    
    # Calculate directory entries & offsets
    dir_entry_size = 16
    dir_table_size = num_images * dir_entry_size
    current_offset = 6 + dir_table_size

    entries: List[bytes] = []
    bitmaps: List[bytes] = []

    for size in sizes:
        w = size
        h = size
        # Generate DIB for ICO:
        # In ICO BMP format, biHeight is 2 * h (accounts for XOR bitmap + AND mask)
        dib_header_size = 40
        xor_bytes_size = w * h * 4
        # AND mask is 1 bit per pixel, aligned to 32 bits (4 bytes) per row
        row_and_bytes = ((w + 31) // 32) * 4
        and_bytes_size = row_and_bytes * h
        res_total_size = dib_header_size + xor_bytes_size + and_bytes_size

        # Directory entry (16 bytes)
        entry = struct.pack(
            "<BBBBHHII",
            w if w < 256 else 0,
            h if h < 256 else 0,
            0,  # color count (0 for 32bpp)
            0,  # reserved
            1,  # planes
            32, # bit count
            res_total_size,
            current_offset
        )
        entries.append(entry)
        current_offset += res_total_size

        # DIB Header with double height
        dib_header = struct.pack(
            "<IIIHHIIIIII",
            dib_header_size,
            w,
            h * 2,  # doubled height for ICO
            1,
            32,
            0,
            xor_bytes_size + and_bytes_size,
            0,
            0,
            0,
            0
        )

        # XOR bitmap (BGRA bottom-up)
        # Re-use BMP generator pixel grid
        full_bmp = generate_bmp(w, h, bg_color=bg_rgba, fg_color=fg_rgba, letter=letter)
        # Extract pixel data from BMP (offset 54)
        xor_pixels = full_bmp[54:]

        # AND mask: all 0s (transparent controlled by 32-bit alpha channel)
        and_mask = b"\x00" * and_bytes_size

        bitmap_payload = dib_header + xor_pixels + and_mask
        bitmaps.append(bitmap_payload)

    return ico_header + b"".join(entries) + b"".join(bitmaps)


def generate_ppm(
    width: int,
    height: int,
    bg_color: Tuple[int, int, int] = (26, 115, 232),
    fg_color: Tuple[int, int, int] = (255, 255, 255),
    letter: str = "P"
) -> bytes:
    """
    Generates binary PPM (P6) raster image.
    """
    header = f"P6\n{width} {height}\n255\n".encode("ascii")
    bmp_bytes = generate_bmp(
        width,
        height,
        bg_color=(bg_color[0], bg_color[1], bg_color[2], 255),
        fg_color=(fg_color[0], fg_color[1], fg_color[2], 255),
        letter=letter
    )
    # Convert BMP BGRA (bottom-up) to PPM RGB (top-down)
    pixel_data = bytearray(width * height * 3)
    bmp_pixels = bmp_bytes[54:]

    for y in range(height):
        # BMP is bottom-up; PPM is top-down
        bmp_y = height - 1 - y
        for x in range(width):
            bmp_idx = (bmp_y * width + x) * 4
            ppm_idx = (y * width + x) * 3
            pixel_data[ppm_idx + 0] = bmp_pixels[bmp_idx + 2]  # R
            pixel_data[ppm_idx + 1] = bmp_pixels[bmp_idx + 1]  # G
            pixel_data[ppm_idx + 2] = bmp_pixels[bmp_idx + 0]  # B

    return header + bytes(pixel_data)


def generate_icon_pack(
    name_or_letter: str = "PWA",
    bg_color: str = "#1a73e8",
    fg_color: str = "#ffffff",
    icon_name: Optional[str] = "sparkles",
    output_dir: Optional[Union[str, Path]] = None,
    base_url_prefix: str = "/icons"
) -> Dict[str, Any]:
    """
    Generates a full production icon bundle:
      - Standard SVG and maskable SVG icons
      - Size-specific SVG assets for 16, 32, 48, 72, 96, 128, 144, 152, 180 (Apple touch), 192, 384, 512, 1024
      - Pure-Python multi-resolution favicon.ico
      - Output List[IconSpec] ready for inclusion in PWAManifestConfig
    
    If `output_dir` is provided, writes all files atomically to disk.
    """
    clean_prefix = base_url_prefix.rstrip("/")
    generated_files: Dict[str, Union[str, bytes]] = {}
    icon_specs: List[IconSpec] = []

    # 1. Master Scalable Vectors
    svg_standard = generate_icon_svg(
        name_or_letter=name_or_letter,
        bg_color=bg_color,
        fg_color=fg_color,
        shape="rounded",
        icon_name=icon_name,
        maskable=False,
        size=512
    )
    generated_files["icon.svg"] = svg_standard

    svg_maskable = generate_icon_svg(
        name_or_letter=name_or_letter,
        bg_color=bg_color,
        fg_color=fg_color,
        icon_name=icon_name,
        maskable=True,
        size=512
    )
    generated_files["icon-maskable.svg"] = svg_maskable

    # Master SVG Icon Specs
    icon_specs.append(IconSpec(
        src=f"{clean_prefix}/icon.svg",
        sizes="any",
        type="image/svg+xml",
        purpose="any"
    ))
    icon_specs.append(IconSpec(
        src=f"{clean_prefix}/icon-maskable.svg",
        sizes="any",
        type="image/svg+xml",
        purpose="maskable"
    ))

    # 2. Standard resolution SVGs
    for sz in STANDARD_ICON_SIZES:
        filename = f"icon-{sz}x{sz}.svg"
        svg_content = generate_icon_svg(
            name_or_letter=name_or_letter,
            bg_color=bg_color,
            fg_color=fg_color,
            shape="rounded",
            icon_name=icon_name,
            maskable=False,
            size=sz
        )
        generated_files[filename] = svg_content
        icon_specs.append(IconSpec(
            src=f"{clean_prefix}/{filename}",
            sizes=f"{sz}x{sz}",
            type="image/svg+xml",
            purpose="any"
        ))

    # 3. Maskable specific sizes (192, 512)
    for sz in [192, 512]:
        filename = f"icon-maskable-{sz}x{sz}.svg"
        svg_content = generate_icon_svg(
            name_or_letter=name_or_letter,
            bg_color=bg_color,
            fg_color=fg_color,
            icon_name=icon_name,
            maskable=True,
            size=sz
        )
        generated_files[filename] = svg_content
        icon_specs.append(IconSpec(
            src=f"{clean_prefix}/{filename}",
            sizes=f"{sz}x{sz}",
            type="image/svg+xml",
            purpose="maskable"
        ))

    # 4. Multi-resolution favicon.ico
    favicon_bytes = generate_favicon_ico(
        bg_color=bg_color,
        fg_color=fg_color,
        letter=name_or_letter[:1] or "P",
        sizes=(16, 32, 48)
    )
    generated_files["favicon.ico"] = favicon_bytes

    # 5. Write to disk if output_dir specified
    if output_dir:
        out_path = normalize_path(output_dir)
        ensure_dir(out_path)
        for fname, content in generated_files.items():
            file_dest = out_path / fname
            if isinstance(content, str):
                atomic_write_text(file_dest, content, encoding="utf-8")
            else:
                atomic_write_bytes(file_dest, content)

    return {
        "icons": icon_specs,
        "files": generated_files,
        "apple_touch_icon": f"{clean_prefix}/icon-180x180.svg",
        "favicon": f"{clean_prefix}/favicon.ico"
    }
