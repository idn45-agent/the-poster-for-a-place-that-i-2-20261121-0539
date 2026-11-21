#!/usr/bin/env python3
"""VELMARA — a travel poster for a place that isn't there.

VELMARA is an island of one long golden evening: a jade lagoon, a white
lighthouse standing on a black sea-stack, and a huge low amber sun that
never quite sets. Come for the light, stay for the tide.

Pure Python 3 standard library: no PIL, no network. Draws a 768x1024
poster into a pixel buffer, encodes it as a PNG (zlib + struct), and
writes /output/entry.png (or $MAKEFUN_OUTPUT_DIR/entry.png).
"""

import math
import os
import struct
import zlib

W, H = 768, 1024

# ---------------------------------------------------------------- palette
SKY_TOP = (251, 239, 210)      # pale cream
SKY_BOTTOM = (246, 201, 143)   # warm peach
SUN = (232, 134, 46)           # amber sun
SUN_HALO = (244, 178, 92)      # sun halo
SEA_TOP = (42, 140, 126)       # jade lagoon
SEA_BOTTOM = (12, 62, 78)      # deep teal
INK = (22, 35, 63)             # deep indigo silhouettes + type
INK_SOFT = (58, 74, 107)       # tagline
CREAM = (250, 240, 216)        # lighthouse white
LIGHT_BEAM = (250, 214, 140)   # lighthouse glow
REFLECT = (248, 196, 110)      # sun path on the water

HORIZON = 560                  # y of the horizon line


# ---------------------------------------------------------------- canvas
class Canvas:
    def __init__(self, w, h):
        self.w = w
        self.h = h
        self.px = bytearray(w * h * 3)

    def set(self, x, y, c):
        if 0 <= x < self.w and 0 <= y < self.h:
            i = (y * self.w + x) * 3
            self.px[i], self.px[i + 1], self.px[i + 2] = c

    def rect(self, x0, y0, x1, y1, c):
        x0 = max(0, x0)
        y0 = max(0, y0)
        x1 = min(self.w, x1)
        y1 = min(self.h, y1)
        for y in range(y0, y1):
            i = (y * self.w + x0) * 3
            row = bytes(c) * (x1 - x0)
            self.px[i:i + len(row)] = row

    def vgrad(self, y0, y1, c0, c1):
        """Vertical linear gradient between two RGB colours."""
        span = max(1, y1 - y0)
        for y in range(y0, min(y1, self.h)):
            t = (y - y0) / span
            c = tuple(int(c0[k] + (c1[k] - c0[k]) * t) for k in range(3))
            self.rect(0, y, self.w, y + 1, c)

    def disc(self, cx, cy, r, c):
        for dy in range(-r, r + 1):
            dx = int(math.sqrt(max(0, r * r - dy * dy)))
            self.rect(cx - dx, cy + dy, cx + dx + 1, cy + dy + 1, c)

    def ellipse(self, cx, cy, rx, ry, c):
        for dy in range(-ry, ry + 1):
            t = dy / ry
            dx = int(rx * math.sqrt(max(0.0, 1.0 - t * t)))
            self.rect(cx - dx, cy + dy, cx + dx + 1, cy + dy + 1, c)

    def poly(self, pts, c):
        """Scanline fill of a simple polygon (list of (x, y))."""
        ys = [p[1] for p in pts]
        for y in range(max(0, min(ys)), min(self.h, max(ys) + 1)):
            xs = []
            n = len(pts)
            for i in range(n):
                x0, y0 = pts[i]
                x1, y1 = pts[(i + 1) % n]
                if y0 == y1:
                    continue
                if (y0 <= y < y1) or (y1 <= y < y0):
                    xs.append(x0 + (y - y0) * (x1 - x0) / (y1 - y0))
            xs.sort()
            for i in range(0, len(xs) - 1, 2):
                self.rect(int(xs[i]), y, int(xs[i + 1]) + 1, y + 1, c)

    def line(self, x0, y0, x1, y1, c, wdt=1):
        steps = max(abs(x1 - x0), abs(y1 - y0), 1)
        for s in range(steps + 1):
            t = s / steps
            x = int(x0 + (x1 - x0) * t)
            y = int(y0 + (y1 - y0) * t)
            self.rect(x - wdt // 2, y - wdt // 2, x + wdt // 2 + 1,
                      y + wdt // 2 + 1, c)


# ---------------------------------------------------------------- 5x7 font
# Each glyph: 7 rows of 5 bits, '#' = on.
FONT = {
    'A': ("01110", "10001", "10001", "11111", "10001", "10001", "10001"),
    'B': ("11110", "10001", "10001", "11110", "10001", "10001", "11110"),
    'C': ("01110", "10001", "10000", "10000", "10000", "10001", "01110"),
    'D': ("11110", "10001", "10001", "10001", "10001", "10001", "11110"),
    'E': ("11111", "10000", "10000", "11110", "10000", "10000", "11111"),
    'F': ("11111", "10000", "10000", "11110", "10000", "10000", "10000"),
    'G': ("01110", "10001", "10000", "10111", "10001", "10001", "01111"),
    'H': ("10001", "10001", "10001", "11111", "10001", "10001", "10001"),
    'I': ("01110", "00100", "00100", "00100", "00100", "00100", "01110"),
    'J': ("00111", "00010", "00010", "00010", "00010", "10010", "01100"),
    'K': ("10001", "10010", "10100", "11000", "10100", "10010", "10001"),
    'L': ("10000", "10000", "10000", "10000", "10000", "10000", "11111"),
    'M': ("10001", "11011", "10101", "10101", "10001", "10001", "10001"),
    'N': ("10001", "11001", "10101", "10011", "10001", "10001", "10001"),
    'O': ("01110", "10001", "10001", "10001", "10001", "10001", "01110"),
    'P': ("11110", "10001", "10001", "11110", "10000", "10000", "10000"),
    'Q': ("01110", "10001", "10001", "10001", "10101", "10010", "01101"),
    'R': ("11110", "10001", "10001", "11110", "10100", "10010", "10001"),
    'S': ("01111", "10000", "10000", "01110", "00001", "00001", "11110"),
    'T': ("11111", "00100", "00100", "00100", "00100", "00100", "00100"),
    'U': ("10001", "10001", "10001", "10001", "10001", "10001", "01110"),
    'V': ("10001", "10001", "10001", "10001", "10001", "01010", "00100"),
    'W': ("10001", "10001", "10001", "10101", "10101", "11011", "10001"),
    'X': ("10001", "10001", "01010", "00100", "01010", "10001", "10001"),
    'Y': ("10001", "10001", "01010", "00100", "00100", "00100", "00100"),
    'Z': ("11111", "00001", "00010", "00100", "01000", "10000", "11111"),
    '0': ("01110", "10001", "10011", "10101", "11001", "10001", "01110"),
    '1': ("00100", "01100", "00100", "00100", "00100", "00100", "01110"),
    '2': ("01110", "10001", "00001", "00110", "01000", "10000", "11111"),
    '3': ("11111", "00010", "00100", "00010", "00001", "10001", "01110"),
    '4': ("00010", "00110", "01010", "10010", "11111", "00010", "00010"),
    '5': ("11111", "10000", "11110", "00001", "00001", "10001", "01110"),
    '6': ("00110", "01000", "10000", "11110", "10001", "10001", "01110"),
    '7': ("11111", "00001", "00010", "00100", "01000", "01000", "01000"),
    '8': ("01110", "10001", "10001", "01110", "10001", "10001", "01110"),
    '9': ("01110", "10001", "10001", "01111", "00001", "00010", "01100"),
    ' ': ("00000", "00000", "00000", "00000", "00000", "00000", "00000"),
    '.': ("00000", "00000", "00000", "00000", "00000", "01100", "01100"),
    ',': ("00000", "00000", "00000", "00000", "01100", "00100", "01000"),
    "'": ("00100", "00100", "01000", "00000", "00000", "00000", "00000"),
    '-': ("00000", "00000", "00000", "01110", "00000", "00000", "00000"),
    '!': ("00100", "00100", "00100", "00100", "00100", "00000", "00100"),
}


def text_width(s, scale):
    return len(s) * 6 * scale - scale


def draw_text(cv, s, cx, y, scale, color):
    """Draw centred text; returns the bottom y."""
    w = text_width(s, scale)
    x = cx - w // 2
    for ch in s:
        glyph = FONT.get(ch.upper(), FONT[' '])
        for row in range(7):
            bits = glyph[row]
            for col in range(5):
                if bits[col] == '1':
                    cv.rect(x + col * scale, y + row * scale,
                            x + (col + 1) * scale, y + (row + 1) * scale,
                            color)
        x += 6 * scale
    return y + 7 * scale


# ---------------------------------------------------------------- PNG encode
def chunk(typ, data):
    out = struct.pack(">I", len(data)) + typ + data
    out += struct.pack(">I", zlib.crc32(typ + data) & 0xFFFFFFFF)
    return out


def encode_png(cv):
    raw = bytearray()
    stride = cv.w * 3
    for y in range(cv.h):
        raw.append(0)  # filter: None
        raw += cv.px[y * stride:(y + 1) * stride]
    ihdr = struct.pack(">IIBBBBB", cv.w, cv.h, 8, 2, 0, 0, 0)
    png = b"\x89PNG\r\n\x1a\n"
    png += chunk(b"IHDR", ihdr)
    png += chunk(b"IDAT", zlib.compress(bytes(raw), 9))
    png += chunk(b"IEND", b"")
    return png


# ---------------------------------------------------------------- the poster
def build():
    cv = Canvas(W, H)

    # Sky: cream melting into peach above the horizon.
    cv.vgrad(0, HORIZON, SKY_TOP, SKY_BOTTOM)
    # Sea: jade lagoon deepening to dark teal.
    cv.vgrad(HORIZON, H, SEA_TOP, SEA_BOTTOM)

    # Sun: a huge low amber disc with a soft halo, upper right.
    # Kept high and small enough that it never touches the place name.
    cv.disc(600, 185, 112, SUN_HALO)
    cv.disc(600, 185, 90, SUN)

    # A few long, thin evening clouds.
    cv.ellipse(180, 150, 150, 14, (252, 244, 224))
    cv.ellipse(430, 110, 110, 10, (252, 244, 224))
    cv.ellipse(120, 465, 90, 9, (250, 232, 200))

    # Sun path: shimmering gold streaks on the water under the sun.
    for i, (yy, half) in enumerate([(590, 85), (630, 70), (675, 58),
                                    (725, 48), (780, 38), (840, 30),
                                    (905, 22), (965, 16)]):
        cv.rect(600 - half, yy, 600 + half, yy + 7, REFLECT)

    # Cliff headland, dark indigo, rising out of the lower left.
    cv.poly([(0, H), (0, 780), (80, 700), (170, 740), (235, 830),
             (268, 940), (272, H)], INK)

    # The sea-stack: black rock the lighthouse stands on, right of centre.
    # Shifted right and lowered so the tower stands clear above it.
    cv.poly([(492, H), (510, 760), (532, 668), (570, 640), (606, 668),
             (628, 760), (646, H)], INK)

    # Lighthouse: tall cream tower with two dark bands, gallery and lamp
    # room, standing clear of the rock with its lamp above the horizon.
    # Dropped 12px so the lamp glow clears the tagline above it.
    cv.rect(545, 587, 591, 712, CREAM)
    cv.rect(545, 627, 591, 639, INK)
    cv.rect(545, 672, 591, 684, INK)
    cv.rect(538, 575, 598, 587, INK)          # gallery rail
    cv.rect(552, 549, 584, 575, INK)          # lamp room
    cv.rect(558, 555, 578, 569, LIGHT_BEAM)   # lit lamp
    cv.poly([(548, 549), (588, 549), (568, 533)], INK)  # roof
    # Warm glow around the lamp, kept below the tagline.
    cv.disc(568, 562, 20, LIGHT_BEAM)
    cv.rect(552, 549, 584, 575, INK)
    cv.rect(558, 555, 578, 569, LIGHT_BEAM)
    cv.poly([(548, 549), (588, 549), (568, 533)], INK)

    # A small sailboat crossing the lagoon, heading for the light.
    cv.poly([(300, 700), (300, 640), (344, 700)], CREAM)   # sail
    cv.poly([(296, 700), (352, 700), (340, 716), (306, 716)], INK)  # hull

    # Birds, three strokes high in the evening sky.
    for bx, by, s in [(150, 250, 14), (205, 215, 11), (245, 268, 9)]:
        cv.line(bx - s, by, bx, by - 6, INK, 2)
        cv.line(bx, by - 6, bx + s, by, INK, 2)

    # Type: the place name, big and centred in the open sky, then a rule,
    # then the one-line promise of what a stay feels like.
    draw_text(cv, "VELMARA", W // 2, 350, 13, INK)
    cv.rect(204, 468, 564, 472, INK)
    draw_text(cv, "WHERE THE SUN STAYS", W // 2, 492, 4, INK_SOFT)

    return cv


def main():
    out_dir = os.environ.get("MAKEFUN_OUTPUT_DIR", "/output")
    os.makedirs(out_dir, exist_ok=True)
    cv = build()
    data = encode_png(cv)
    path = os.path.join(out_dir, "entry.png")
    with open(path, "wb") as f:
        f.write(data)
    print(f"wrote {path}: {len(data)} bytes, {W}x{H}")


if __name__ == "__main__":
    main()
