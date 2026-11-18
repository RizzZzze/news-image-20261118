#!/usr/bin/env python3
"""One-page newspaper: world news of Wednesday 18 November 2026.

Draws the whole 1024x1024 image with the Python standard library only
(no fonts, no network): a stroke typeface defined below, flat vector
scenes, and a schematic world map. Deterministic: same bytes every run.
"""
import math
import os
import struct
import zlib

W = 1024
H = 1024

# ---------------------------------------------------------------- palette
PAPER = (246, 239, 220)
PAPER2 = (238, 229, 203)
INK = (24, 22, 18)
SUB = (46, 42, 35)          # sub-label ink: mid-dark, verified both ways at 300px
RULE = (120, 110, 88)
SKY = (178, 205, 224)
SEA = (126, 164, 196)
LAND = (222, 210, 172)
LAND2 = (205, 192, 150)
WHITE = (250, 248, 242)
GREY = (107, 107, 107)

# Region colours (chip = map pin). 6 regions + space grey.
REG = {
    "EU": (43, 90, 166),
    "AS": (186, 52, 44),
    "AF": (206, 116, 22),
    "NA": (42, 122, 74),
    "SA": (122, 79, 163),
    "OC": (24, 128, 128),
    "SP": (107, 107, 107),
}
REG_NAME = {
    "EU": "EUROPE", "AS": "ASIA", "AF": "AFRICA",
    "NA": "N. AMERICA", "SA": "S. AMERICA", "OC": "OCEANIA", "SP": "SPACE",
}
REG_TINT = {
    "EU": (214, 226, 242), "AS": (244, 214, 210), "AF": (248, 228, 200),
    "NA": (210, 234, 220), "SA": (232, 220, 242), "OC": (206, 234, 232),
    "SP": (226, 226, 226),
}
REG_DARK = {
    "EU": (43, 90, 166), "AS": (170, 44, 36), "AF": (158, 86, 10),
    "NA": (34, 100, 60), "SA": (104, 64, 142), "OC": (14, 98, 98),
    "SP": (90, 90, 90),
}


class Canvas:
    def __init__(self, w, h, bg):
        self.w = w
        self.h = h
        self.buf = bytearray(w * h * 3)
        self.rect(0, 0, w, h, bg)

    def set(self, x, y, c):
        if 0 <= x < self.w and 0 <= y < self.h:
            i = (y * self.w + x) * 3
            self.buf[i] = c[0]
            self.buf[i + 1] = c[1]
            self.buf[i + 2] = c[2]

    def rect(self, x, y, w, h, c):
        x0, y0 = max(0, x), max(0, y)
        x1, y1 = min(self.w, x + w), min(self.h, y + h)
        if x1 <= x0 or y1 <= y0:
            return
        row = bytes(c) * (x1 - x0)
        for yy in range(y0, y1):
            i = (yy * self.w + x0) * 3
            self.buf[i:i + len(row)] = row

    def frame(self, x, y, w, h, c, t=2):
        self.rect(x, y, w, t, c)
        self.rect(x, y + h - t, w, t, c)
        self.rect(x, y, t, h, c)
        self.rect(x + w - t, y, t, h, c)

    def hline(self, x, y, w, c, t=1):
        self.rect(x, y, w, t, c)

    def vline(self, x, y, h, c, t=1):
        self.rect(x, y, t, h, c)

    def line(self, x0, y0, x1, y1, c):
        """Bresenham, 1px."""
        x0, y0, x1, y1 = int(round(x0)), int(round(y0)), int(round(x1)), int(round(y1))
        dx, dy = abs(x1 - x0), abs(y1 - y0)
        sx = 1 if x0 < x1 else -1
        sy = 1 if y0 < y1 else -1
        err = dx - dy
        while True:
            self.set(x0, y0, c)
            if x0 == x1 and y0 == y1:
                break
            e2 = 2 * err
            if e2 > -dy:
                err -= dy
                x0 += sx
            if e2 < dx:
                err += dx
                y0 += sy

    def thick_line(self, x0, y0, x1, y1, c, wdt):
        if wdt <= 1:
            self.line(x0, y0, x1, y1, c)
            return
        dx, dy = x1 - x0, y1 - y0
        ln = math.hypot(dx, dy)
        if ln < 0.001:
            self.disc(x0, y0, wdt / 2.0, c)
            return
        px, py = -dy / ln, dx / ln
        offs = []
        n = int(wdt)
        for k in range(n):
            offs.append(k - (n - 1) / 2.0)
        for o in offs:
            self.line(x0 + px * o, y0 + py * o, x1 + px * o, y1 + py * o, c)
        if wdt >= 3:
            r = (wdt - 1) / 2.0
            self.disc(x0, y0, r, c)
            self.disc(x1, y1, r, c)

    def disc(self, cx, cy, r, c):
        cx, cy = int(round(cx)), int(round(cy))
        ri = int(math.ceil(r))
        for yy in range(cy - ri, cy + ri + 1):
            for xx in range(cx - ri, cx + ri + 1):
                if (xx - cx) ** 2 + (yy - cy) ** 2 <= r * r + 0.4:
                    self.set(xx, yy, c)

    def circle(self, cx, cy, r, c, wdt=2):
        steps = max(24, int(2 * math.pi * r))
        prev = None
        for k in range(steps + 1):
            a = 2 * math.pi * k / steps
            p = (cx + r * math.cos(a), cy + r * math.sin(a))
            if prev is not None:
                self.thick_line(prev[0], prev[1], p[0], p[1], c, wdt)
            prev = p

    def poly(self, pts, c):
        """Scanline fill. pts: list of (x, y)."""
        if len(pts) < 3:
            return
        ys = [p[1] for p in pts]
        y0, y1 = int(math.floor(min(ys))), int(math.ceil(max(ys)))
        edges = []
        n = len(pts)
        for i in range(n):
            x0, yy0 = pts[i]
            x1, yy1 = pts[(i + 1) % n]
            if yy0 != yy1:
                edges.append((x0, yy0, x1, yy1))
        for y in range(max(0, y0), min(self.h, y1 + 1)):
            yc = y + 0.5
            xs = []
            for x0, yy0, x1, yy1 in edges:
                if (yy0 <= yc < yy1) or (yy1 <= yc < yy0):
                    xs.append(x0 + (yc - yy0) * (x1 - x0) / (yy1 - yy0))
            xs.sort()
            for k in range(0, len(xs) - 1, 2):
                xa, xb = int(math.ceil(xs[k])), int(math.floor(xs[k + 1]))
                for xx in range(max(0, xa), min(self.w, xb + 1)):
                    self.set(xx, y, c)

    def polyline(self, pts, c, wdt=2, closed=False):
        seq = list(pts) + ([pts[0]] if closed and len(pts) > 1 else [])
        for i in range(len(seq) - 1):
            self.thick_line(seq[i][0], seq[i][1], seq[i + 1][0], seq[i + 1][1], c, wdt)


# ------------------------------------------------------------------- font
# Stroke typeface on a 10-wide grid: y=0 cap top, y=14 baseline, y=18 descender.
# Each glyph is a list of polylines. Designed from scratch for this page.
G = {
    "0": [[(3, 0), (7, 0), (9, 3), (9, 11), (7, 14), (3, 14), (1, 11), (1, 3), (3, 0)]],
    "1": [[(2, 3), (5, 0), (5, 14)], [(2, 14), (8, 14)]],
    "2": [[(1, 4), (2, 1), (5, 0), (8, 1), (9, 3), (9, 6), (1, 14), (9, 14)]],
    "3": [[(1, 2), (3, 0), (7, 0), (9, 2), (9, 5), (6, 7)], [(6, 7), (9, 9), (9, 12), (7, 14), (3, 14), (1, 12)]],
    "4": [[(7, 0), (1, 10), (9, 10)], [(7, 0), (7, 14)]],
    "5": [[(9, 0), (1, 0), (1, 6), (7, 6), (9, 8), (9, 12), (7, 14), (2, 14), (1, 13)]],
    "6": [[(8, 1), (4, 0), (1, 3), (1, 11), (3, 14), (7, 14), (9, 11), (9, 8), (6, 6), (3, 6), (1, 9)]],
    "7": [[(1, 0), (9, 0), (4, 14)]],
    "8": [[(3, 0), (7, 0), (9, 2), (9, 5), (7, 7), (3, 7), (1, 5), (1, 2), (3, 0)],
          [(3, 7), (7, 7), (9, 9), (9, 12), (7, 14), (3, 14), (1, 12), (1, 9), (3, 7)]],
    "9": [[(1, 13), (3, 14), (7, 13), (9, 10), (9, 3), (7, 0), (3, 0), (1, 3), (1, 6), (3, 8), (7, 8), (9, 5)]],
    "A": [[(1, 14), (5, 0), (9, 14)], [(3, 9), (7, 9)]],
    "B": [[(1, 0), (1, 14)], [(1, 0), (7, 0), (9, 2), (9, 5), (7, 7), (1, 7)], [(7, 7), (9, 9), (9, 12), (7, 14), (1, 14)]],
    "C": [[(9, 2), (7, 0), (3, 0), (1, 3), (1, 11), (3, 14), (7, 14), (9, 12)]],
    "D": [[(1, 0), (1, 14)], [(1, 0), (6, 0), (9, 3), (9, 11), (6, 14), (1, 14)]],
    "E": [[(1, 0), (1, 14)], [(1, 0), (9, 0)], [(1, 7), (7, 7)], [(1, 14), (9, 14)]],
    "F": [[(1, 0), (1, 14)], [(1, 0), (9, 0)], [(1, 7), (7, 7)]],
    "G": [[(9, 2), (7, 0), (3, 0), (1, 3), (1, 11), (3, 14), (7, 14), (9, 12), (9, 8), (6, 8)]],
    "H": [[(1, 0), (1, 14)], [(9, 0), (9, 14)], [(1, 7), (9, 7)]],
    "I": [[(5, 0), (5, 14)], [(2, 0), (8, 0)], [(2, 14), (8, 14)]],
    "J": [[(4, 0), (9, 0)], [(9, 0), (9, 11), (7, 14), (3, 14), (1, 12)]],
    "K": [[(1, 0), (1, 14)], [(9, 0), (1, 7), (9, 14)]],
    "L": [[(1, 0), (1, 14)], [(1, 14), (9, 14)]],
    "M": [[(1, 14), (1, 0), (5, 7), (9, 0), (9, 14)]],
    "N": [[(1, 14), (1, 0), (9, 14), (9, 0)]],
    "O": [[(3, 0), (7, 0), (9, 3), (9, 11), (7, 14), (3, 14), (1, 11), (1, 3), (3, 0)]],
    "P": [[(1, 14), (1, 0)], [(1, 0), (7, 0), (9, 2), (9, 5), (7, 7), (1, 7)]],
    "Q": [[(3, 0), (7, 0), (9, 3), (9, 11), (7, 14), (3, 14), (1, 11), (1, 3), (3, 0)], [(6, 11), (9, 15)]],
    "R": [[(1, 14), (1, 0)], [(1, 0), (7, 0), (9, 2), (9, 5), (7, 7), (1, 7)], [(6, 7), (9, 14)]],
    "S": [[(8, 1), (6, 0), (3, 0), (1, 2), (1, 5), (3, 7), (7, 7), (9, 9), (9, 12), (7, 14), (4, 14), (1, 13)]],
    "T": [[(5, 0), (5, 14)], [(1, 0), (9, 0)]],
    "U": [[(1, 0), (1, 11), (3, 14), (7, 14), (9, 11), (9, 0)]],
    "V": [[(1, 0), (5, 14), (9, 0)]],
    "W": [[(1, 0), (3, 14), (5, 6), (7, 14), (9, 0)]],
    "X": [[(1, 0), (9, 14)], [(9, 0), (1, 14)]],
    "Y": [[(1, 0), (5, 7), (9, 0)], [(5, 7), (5, 14)]],
    "Z": [[(1, 0), (9, 0), (1, 14), (9, 14)]],
    "a": [[(8, 6), (6, 4), (3, 4), (1, 6), (1, 12), (3, 14), (6, 14), (8, 12)], [(9, 4), (9, 14)]],
    "b": [[(1, 0), (1, 14)], [(1, 7), (4, 4), (7, 4), (9, 7), (9, 11), (7, 14), (4, 14), (1, 11)]],
    "c": [[(9, 6), (7, 4), (3, 4), (1, 7), (1, 11), (3, 14), (7, 14), (9, 12)]],
    "d": [[(9, 0), (9, 14)], [(9, 7), (6, 4), (3, 4), (1, 7), (1, 11), (3, 14), (6, 14), (9, 11)]],
    "e": [[(1, 10), (9, 10)], [(9, 7), (7, 4), (3, 4), (1, 7), (1, 11), (3, 14), (7, 14), (9, 12)]],
    "f": [[(6, 0), (3, 1), (2, 4), (2, 14)], [(1, 7), (6, 7)]],
    "g": [[(8, 6), (6, 4), (3, 4), (1, 6), (1, 12), (3, 14), (6, 14), (8, 12)], [(9, 4), (9, 15), (7, 18), (3, 18), (1, 16)]],
    "h": [[(1, 0), (1, 14)], [(1, 8), (4, 4), (7, 4), (9, 7), (9, 14)]],
    "i": [[(5, 4), (5, 14)], [(4, 0), (6, 0), (6, 2), (4, 2), (4, 0)]],
    "j": [[(7, 4), (7, 15), (5, 18), (2, 18)], [(6, 0), (8, 0), (8, 2), (6, 2), (6, 0)]],
    "k": [[(1, 0), (1, 14)], [(8, 4), (1, 9), (9, 14)]],
    "l": [[(5, 0), (5, 14)]],
    "m": [[(1, 4), (1, 14)], [(1, 9), (2, 4), (4, 4), (5, 7), (5, 14)], [(5, 9), (6, 4), (8, 4), (9, 7), (9, 14)]],
    "n": [[(1, 14), (1, 4)], [(1, 9), (3, 4), (6, 4), (9, 7), (9, 14)]],
    "o": [[(3, 4), (7, 4), (9, 7), (9, 11), (7, 14), (3, 14), (1, 11), (1, 7), (3, 4)]],
    "p": [[(1, 4), (1, 18)], [(1, 7), (4, 4), (7, 4), (9, 7), (9, 11), (7, 14), (4, 14), (1, 11)]],
    "q": [[(9, 4), (9, 18)], [(9, 7), (6, 4), (3, 4), (1, 7), (1, 11), (3, 14), (6, 14), (9, 11)]],
    "r": [[(1, 4), (1, 14)], [(1, 8), (4, 4), (7, 4), (9, 6)]],
    "s": [[(8, 5), (6, 4), (3, 4), (1, 6), (1, 8), (3, 9), (7, 9), (9, 11), (9, 13), (7, 14), (4, 14), (1, 13)]],
    "t": [[(5, 0), (5, 13), (8, 14)], [(2, 7), (8, 7)]],
    "u": [[(1, 4), (1, 11), (3, 14), (7, 14), (9, 11), (9, 4)], [(9, 11), (9, 14)]],
    "v": [[(1, 4), (5, 14), (9, 4)]],
    "w": [[(1, 4), (2, 14), (5, 8), (8, 14), (9, 4)]],
    "x": [[(1, 4), (9, 14)], [(9, 4), (1, 14)]],
    "y": [[(1, 4), (5, 13), (9, 4)], [(5, 13), (3, 18)]],
    "z": [[(1, 4), (9, 4), (1, 14), (9, 14)]],
    ".": [[(4, 12), (6, 12), (6, 14), (4, 14), (4, 12)]],
    ",": [[(5, 13), (5, 15), (3, 18)]],
    ":": [[(4, 5), (6, 5), (6, 7), (4, 7), (4, 5)], [(4, 11), (6, 11), (6, 13), (4, 13), (4, 11)]],
    ";": [[(4, 5), (6, 5), (6, 7), (4, 7), (4, 5)], [(5, 11), (5, 15), (3, 18)]],
    "'": [[(5, 0), (4, 4)]],
    "\u2019": [[(5, 0), (4, 4)]],
    '"': [[(3, 0), (2, 4)], [(7, 0), (6, 4)]],
    "\u201c": [[(3, 0), (2, 4)], [(7, 0), (6, 4)]],
    "\u201d": [[(3, 0), (2, 4)], [(7, 0), (6, 4)]],
    "!": [[(5, 0), (5, 10)], [(4, 12), (6, 12), (6, 14), (4, 14), (4, 12)]],
    "?": [[(2, 3), (4, 0), (7, 0), (9, 3), (9, 6), (5, 9), (5, 11)], [(4, 13), (6, 13), (6, 14), (4, 14), (4, 13)]],
    "-": [[(1, 8), (9, 8)]],
    "\u2013": [[(0, 8), (10, 8)]],
    "\u2014": [[(0, 8), (10, 8)]],
    "(": [[(7, 0), (4, 3), (3, 7), (4, 11), (7, 14)]],
    ")": [[(3, 0), (6, 3), (7, 7), (6, 11), (3, 14)]],
    "/": [[(9, 0), (1, 14)]],
    "%": [[(8, 0), (2, 14)],
          [(1, 1), (3, 1), (4, 3), (3, 5), (1, 5), (0, 3), (1, 1)],
          [(7, 9), (9, 9), (10, 11), (9, 13), (7, 13), (6, 11), (7, 9)]],
    "$": [[(5, 0), (5, 14)], [(8, 3), (6, 1), (3, 1), (1, 3), (1, 6), (3, 7), (7, 7), (9, 9), (9, 12), (7, 14), (4, 14), (2, 12)]],
    "+": [[(5, 2), (5, 12)], [(0, 7), (10, 7)]],
    "=": [[(1, 5), (9, 5)], [(1, 10), (9, 10)]],
    "*": [[(5, 1), (5, 8)], [(2, 3), (8, 7)], [(8, 3), (2, 7)]],
    "\u2022": [[(5, 6), (7, 8), (5, 10), (3, 8), (5, 6)]],
    "\u00b0": [[(4, 0), (6, 0), (7, 1), (7, 3), (6, 4), (4, 4), (3, 3), (3, 1), (4, 0)]],
    "\u00d7": [[(2, 4), (8, 10)], [(8, 4), (2, 10)]],
    "&": [[(7, 1), (4, 3), (2, 6), (3, 9), (6, 10), (9, 7)], [(3, 9), (9, 14)]],
    "<": [[(8, 1), (2, 7), (8, 13)]],
    ">": [[(2, 1), (8, 7), (2, 13)]],
}
WIDTHS = {
    " ": 5, "i": 5, "j": 6, "l": 5, ".": 5, ",": 5, ":": 5, ";": 5, "!": 5,
    "'": 4, "\u2019": 4, '"': 7, "\u201c": 7, "\u201d": 7, "(": 6, ")": 6,
    "f": 7, "t": 7, "r": 7, "I": 6, "1": 7, "/": 7, "-": 7, "\u2013": 10,
    "\u2014": 12, "m": 12, "w": 12, "M": 12, "W": 12, "%": 12, "\u2022": 6,
    "\u00b0": 6, "$": 9,
}
TRACK = 0.9  # extra units between glyphs


def glyph_adv(ch):
    return WIDTHS.get(ch, 10) + TRACK


def text_width(text, s):
    return sum(glyph_adv(ch) for ch in text) * s


def draw_glyph(cv, ch, x, ytop, s, c, wdt):
    strokes = G.get(ch)
    if not strokes:
        return
    for pl in strokes:
        for i in range(len(pl) - 1):
            x0, y0 = pl[i]
            x1, y1 = pl[i + 1]
            cv.thick_line(x + x0 * s, ytop + y0 * s, x + x1 * s, ytop + y1 * s, c, wdt)


def draw_text(cv, text, x, ytop, s, c, weight=1.0, align="left", box_w=None):
    """Draw text; ytop is the cap-top line. Returns width in px."""
    wdt = max(1, int(round(1.5 * s * weight)))
    if wdt < 1:
        wdt = 1
    total = text_width(text, s)
    if align == "center" and box_w is not None:
        x = x + (box_w - total) / 2.0
    elif align == "right" and box_w is not None:
        x = x + box_w - total
    cx = x
    for ch in text:
        draw_glyph(cv, ch, cx, ytop, s, c, wdt)
        cx += glyph_adv(ch) * s
    return total


def wrap_lines(text, s, max_w):
    """Greedy word wrap; returns list of lines. Keeps balance: avoid a
    lone short word on the last line when a re-flow can fix it."""
    words = text.split()
    lines = []
    cur = ""
    for wd in words:
        trial = wd if not cur else cur + " " + wd
        if text_width(trial, s) <= max_w or not cur:
            cur = trial
        else:
            lines.append(cur)
            cur = wd
    if cur:
        lines.append(cur)
    # Balance: if last line is a single short word and we have >=2 lines,
    # pull one word down from the previous line when it still fits.
    if len(lines) >= 2:
        last = lines[-1].split()
        if len(last) == 1 and len(lines[-2].split()) > 1:
            prev = lines[-2].split()
            moved = prev[-1]
            cand_last = moved + " " + lines[-1]
            cand_prev = " ".join(prev[:-1])
            if text_width(cand_last, s) <= max_w:
                lines[-2] = cand_prev
                lines[-1] = cand_last
    return lines


# -------------------------------------------------------------------- png
def png_bytes(cv):
    raw = bytearray()
    w, h = cv.w, cv.h
    stride = w * 3
    for y in range(h):
        raw.append(1)  # Sub filter
        row = cv.buf[y * stride:(y + 1) * stride]
        prev = 0
        out = bytearray(stride)
        for i, b in enumerate(row):
            left = row[i - 3] if i >= 3 else 0
            out[i] = (b - left) & 0xFF
        raw += out
    comp = zlib.compress(bytes(raw), 9)

    def chunk(typ, data):
        c = struct.pack(">I", len(data)) + typ + data
        return c + struct.pack(">I", zlib.crc32(typ + data) & 0xFFFFFFFF)

    ihdr = struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0)
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", ihdr)
            + chunk(b"IDAT", comp) + chunk(b"IEND", b""))


def write_output(cv):
    outdir = os.environ.get("MAKEFUN_OUTPUT_DIR", "/output")
    os.makedirs(outdir, exist_ok=True)
    path = os.path.join(outdir, "entry.png")
    with open(path, "wb") as f:
        f.write(png_bytes(cv))
    return path


# ------------------------------------------------------------- helpers
def star_pts(cx, cy, r):
    pts = []
    for k in range(10):
        ang = -math.pi / 2 + k * math.pi / 5
        rr = r if k % 2 == 0 else r * 0.42
        pts.append((cx + rr * math.cos(ang), cy + rr * math.sin(ang)))
    return pts


def dotted_line(cv, x0, y0, x1, y1, c):
    ln = math.hypot(x1 - x0, y1 - y0)
    if ln < 1:
        return
    steps = int(ln / 4)
    for k in range(steps + 1):
        if k % 2 == 0:
            t = k / max(1, steps)
            cv.set(int(round(x0 + (x1 - x0) * t)), int(round(y0 + (y1 - y0) * t)), c)


def draw_chip(cv, cx, cy, r, num, reg):
    cv.disc(cx, cy, r + 1.5, WHITE)
    cv.disc(cx, cy, r, REG[reg])
    cv.circle(cx, cy, r, INK, 1)
    s = 0.78 if num < 10 else 0.70
    s *= min(1.0, r / 9.0)
    txt = str(num)
    tw = text_width(txt, s)
    draw_text(cv, txt, cx - tw / 2, cy - 5, s, WHITE, 1.6)


def fit_size(text, sizes, max_w, max_lines):
    for s in sizes:
        if len(wrap_lines(text, s, max_w)) <= max_lines:
            return s
    return sizes[-1]


# ------------------------------------------------------ feature scenes
def scene_gulf(cv, x, y, w, h):
    cv.rect(x, y, w, h, (216, 228, 238))
    cv.rect(x, y + int(h * 0.45), w, h - int(h * 0.45), (110, 150, 185))
    cv.rect(x, y + int(h * 0.62), w, h - int(h * 0.62), (88, 128, 165))
    cv.disc(x + w - 42, y + 26, 15, (240, 200, 110))
    cv.disc(x + w - 42, y + 26, 19, (240, 200, 110))  # glow halo same tone
    # distant tanker silhouette
    cv.rect(x + 20, y + int(h * 0.55), 132, 11, (52, 52, 52))
    cv.poly([(x + 20, y + int(h * 0.55)), (x + 38, y + int(h * 0.55) - 8),
             (x + 134, y + int(h * 0.55) - 8), (x + 152, y + int(h * 0.55))], (52, 52, 52))
    cv.rect(x + 116, y + int(h * 0.55) - 22, 18, 14, (236, 236, 236))
    cv.frame(x + 116, y + int(h * 0.55) - 22, 18, 14, (52, 52, 52), 1)
    cv.rect(x + 138, y + int(h * 0.55) - 16, 6, 8, (52, 52, 52))
    # smoke puffs
    for dx, dy, r in [(140, -30, 7), (150, -38, 9), (162, -46, 11)]:
        cv.disc(x + dx, y + int(h * 0.52) + dy, r, (105, 105, 105))
    # fire glow on water
    cv.poly([(x + 166, y + h - 6), (x + 204, y + h - 6), (x + 194, y + int(h * 0.70)),
             (x + 178, y + int(h * 0.74))], (226, 110, 40))
    cv.poly([(x + 176, y + h - 6), (x + 194, y + h - 6), (x + 187, y + int(h * 0.75))], (245, 180, 60))
    # drones: small x-shapes with rotor dots
    for dx, dy in [(52, 26), (88, 16)]:
        px, py = x + dx, y + dy
        cv.thick_line(px - 8, py - 4, px + 8, py + 4, INK, 2)
        cv.thick_line(px - 8, py + 4, px + 8, py - 4, INK, 2)
        cv.disc(px, py, 3, INK)
    # wave strokes
    for yy in (int(h * 0.72), int(h * 0.82), int(h * 0.92)):
        for xx in range(10, w - 20, 42):
            cv.thick_line(x + xx, y + yy, x + xx + 18, y + yy, (210, 225, 238), 2)


def scene_bridge(cv, x, y, w, h):
    cv.rect(x, y, w, h, (206, 220, 232))
    cv.rect(x, y + int(h * 0.66), w, h - int(h * 0.66), (120, 158, 190))
    # smoke plumes
    for dx, dy, r in [(70, 26, 12), (86, 16, 15), (104, 8, 11), (250, 22, 10), (264, 12, 13)]:
        cv.disc(x + dx, y + dy, r, (140, 140, 140))
    # bridge towers
    for tx in (52, 218):
        cv.rect(x + tx, y + 34, 10, int(h * 0.66) - 34, (70, 70, 70))
        cv.rect(x + tx - 6, y + 30, 22, 6, (70, 70, 70))
    # deck: left span + right span, gap in the middle
    dy = y + int(h * 0.52)
    cv.rect(x + 8, dy, 118, 7, (45, 45, 45))
    cv.rect(x + 188, dy, 118, 7, (45, 45, 45))
    # fallen span, tilted into the water
    cv.poly([(x + 126, dy + 2), (x + 188, dy + 2), (x + 176, dy + 34), (x + 140, dy + 30)], (60, 60, 60))
    # cables
    for tx in (57, 223):
        for off in (-44, -22, 22, 44):
            cv.line(x + tx, y + 34, x + tx + off, dy, (90, 90, 90))
    # splash marks
    for sx in (140, 158, 176):
        cv.thick_line(x + sx, y + int(h * 0.66) + 4, x + sx, y + int(h * 0.66) + 16, (230, 238, 244), 2)
    # fire glow at the break
    cv.disc(x + 158, dy - 2, 7, (226, 110, 40))
    cv.disc(x + 158, dy - 2, 3, (245, 180, 60))


def scene_summit(cv, x, y, w, h):
    cv.rect(x, y, w, h, (214, 226, 238))
    # skyline
    base = y + h
    for bx, bw, bh in [(6, 26, 52), (36, 20, 70), (60, 30, 44), (230, 24, 60), (258, 30, 40), (292, 20, 55)]:
        cv.rect(x + bx, base - bh, bw, bh, (120, 138, 158))
    cv.thick_line(x + 46, base - 70, x + 46, base - 84, (120, 138, 158), 2)
    cv.disc(x + 46, base - 85, 2, (200, 60, 50))
    # plane
    px, py = x + 190, y + 20
    cv.poly([(px - 26, py), (px + 26, py), (px + 18, py + 4), (px - 18, py + 4)], (60, 60, 60))
    cv.poly([(px - 6, py - 8), (px + 4, py - 8), (px + 2, py), (px - 6, py)], (60, 60, 60))
    cv.thick_line(px - 30, py + 8, px - 52, py + 12, (180, 180, 180), 2)
    # ground band
    cv.rect(x, base - 16, w, 16, (196, 182, 150))
    # three flags
    flags = [("US", 118), ("CN", 158), ("RU", 198)]
    for name, fx in flags:
        cv.thick_line(x + fx, base - 16, x + fx, y + 34, INK, 2)
        fw, fh = 30, 20
        fy = y + 34
        if name == "US":
            cv.rect(x + fx + 2, fy, fw, fh, WHITE)
            for k in range(4):
                cv.rect(x + fx + 2, fy + k * 5, fw, 2, (178, 52, 52))
            cv.rect(x + fx + 2, fy, 13, 10, (43, 90, 166))
        elif name == "CN":
            cv.rect(x + fx + 2, fy, fw, fh, (200, 40, 40))
            cv.poly(star_pts(x + fx + 10, fy + 8, 5), (245, 200, 60))
        else:
            cv.rect(x + fx + 2, fy, fw, 7, WHITE)
            cv.rect(x + fx + 2, fy + 7, fw, 7, (43, 90, 166))
            cv.rect(x + fx + 2, fy + 14, fw, 6, (200, 40, 40))
    # red carpet
    cv.poly([(x + 108, base - 16), (x + 236, base - 16), (x + 252, base), (x + 92, base)], (170, 50, 50))


# --------------------------------------------------------- card icons
def _ic(cv, x, y, w, h, reg, fn):
    cv.rect(x, y, w, h, REG_TINT[reg])
    fn(cv, x, y, w, h, reg)
    cv.frame(x, y, w, h, RULE, 1)


def draw_icon_panel(cv, x, y, w, h, reg, icon):
    cv.rect(x, y, w, h, REG_TINT[reg])
    sq = h - 4
    sx = x + (w - sq) // 2
    sy = y + 2
    mid = y + h // 2
    cv.hline(x + 8, mid, sx - x - 12, RULE, 1)
    cv.hline(sx + sq + 4, mid, x + w - 8 - (sx + sq + 4), RULE, 1)
    cv.disc(x + 8, mid, 3, REG[reg])
    cv.disc(x + w - 9, mid, 3, REG[reg])
    cv.rect(sx, sy, sq, sq, WHITE)
    cv.frame(sx, sy, sq, sq, RULE, 1)
    ICONS[icon](cv, sx + (sq - 60) // 2, sy + (sq - 60) // 2, 60, 60, reg)


def ic_tent(cv, x, y, w, h, reg):
    cv.poly([(x + 8, y + 48), (x + 30, y + 12), (x + 52, y + 48)], REG[reg])
    cv.poly([(x + 24, y + 48), (x + 30, y + 30), (x + 36, y + 48)], INK)
    cv.thick_line(x + 8, y + 48, x + 52, y + 48, INK, 2)


def ic_rubble(cv, x, y, w, h, reg):
    cv.rect(x + 12, y + 16, 36, 32, WHITE)
    cv.frame(x + 12, y + 16, 36, 32, INK, 2)
    cv.thick_line(x + 12, y + 16, x + 30, y + 28, INK, 2)
    cv.thick_line(x + 30, y + 28, x + 24, y + 40, INK, 2)
    cv.rect(x + 34, y + 32, 10, 4, REG[reg])
    cv.rect(x + 37, y + 29, 4, 10, REG[reg])


def ic_globe(cv, x, y, w, h, reg):
    cv.disc(x + 30, y + 30, 19, (126, 164, 196))
    cv.circle(x + 30, y + 30, 19, INK, 2)
    cv.polyline([(x + 14, y + 24), (x + 24, y + 20), (x + 34, y + 26), (x + 46, y + 22)], (60, 120, 70), 2)
    cv.polyline([(x + 18, y + 38), (x + 30, y + 34), (x + 42, y + 40)], (60, 120, 70), 2)
    cv.poly([(x + 44, y + 10), (x + 54, y + 4), (x + 52, y + 14)], REG[reg])


def ic_parliament(cv, x, y, w, h, reg):
    cv.poly([(x + 8, y + 24), (x + 30, y + 10), (x + 52, y + 24)], INK)
    for cx in (16, 27, 38):
        cv.rect(x + cx, y + 28, 5, 18, INK)
    cv.rect(x + 8, y + 48, 44, 4, INK)
    cv.disc(x + 30, y + 20, 3, REG[reg])


def ic_quake(cv, x, y, w, h, reg):
    cv.thick_line(x + 6, y + 44, x + 54, y + 44, INK, 2)
    cv.polyline([(x + 30, y + 44), (x + 26, y + 38), (x + 32, y + 32), (x + 28, y + 26)], REG[reg], 3)
    for r in (8, 14, 20):
        cv.polyline([(x + 30 - r, y + 18), (x + 30, y + 18 - r // 2), (x + 30 + r, y + 18)], INK, 1)


def ic_virus(cv, x, y, w, h, reg):
    for k in range(8):
        a = k * math.pi / 4
        cv.thick_line(x + 30 + 12 * math.cos(a), y + 30 + 12 * math.sin(a),
                      x + 30 + 20 * math.cos(a), y + 30 + 20 * math.sin(a), INK, 2)
        cv.disc(x + 30 + 20 * math.cos(a), y + 30 + 20 * math.sin(a), 3, REG[reg])
    cv.disc(x + 30, y + 30, 12, INK)
    cv.disc(x + 26, y + 27, 3, REG[reg])
    cv.disc(x + 34, y + 33, 3, REG[reg])


def ic_ball(cv, x, y, w, h, reg):
    cv.disc(x + 30, y + 30, 19, WHITE)
    cv.circle(x + 30, y + 30, 19, INK, 2)
    cv.poly(star_pts(x + 30, y + 30, 7), INK)
    for k in range(5):
        a = -math.pi / 2 + k * 2 * math.pi / 5
        cv.line(x + 30 + 7 * math.cos(a), y + 30 + 7 * math.sin(a),
                x + 30 + 18 * math.cos(a), y + 30 + 18 * math.sin(a), INK)


def ic_freezer(cv, x, y, w, h, reg):
    cv.rect(x + 14, y + 8, 32, 44, WHITE)
    cv.frame(x + 14, y + 8, 32, 44, INK, 2)
    cv.hline(x + 14, y + 22, 32, INK, 2)
    cx, cy = x + 30, y + 38
    for a in (0, math.pi / 3, 2 * math.pi / 3):
        cv.thick_line(cx - 8 * math.cos(a), cy - 8 * math.sin(a),
                      cx + 8 * math.cos(a), cy + 8 * math.sin(a), REG[reg], 2)


def ic_barrel(cv, x, y, w, h, reg):
    cv.rect(x + 16, y + 10, 28, 40, REG[reg])
    cv.frame(x + 16, y + 10, 28, 40, INK, 2)
    cv.hline(x + 16, y + 22, 28, INK, 2)
    cv.hline(x + 16, y + 38, 28, INK, 2)
    cv.poly([(x + 30, y + 26), (x + 35, y + 33), (x + 30, y + 36), (x + 25, y + 33)], (245, 180, 60))


def ic_scale(cv, x, y, w, h, reg):
    cv.thick_line(x + 30, y + 10, x + 30, y + 48, INK, 2)
    cv.thick_line(x + 12, y + 16, x + 48, y + 16, INK, 2)
    for px in (12, 48):
        cv.thick_line(x + px, y + 16, x + px - 7, y + 32, INK, 1)
        cv.thick_line(x + px, y + 16, x + px + 7, y + 32, INK, 1)
        cv.polyline([(x + px - 8, y + 32), (x + px, y + 38), (x + px + 8, y + 32)], REG[reg], 2)
    cv.rect(x + 22, y + 48, 16, 3, INK)


def ic_pump(cv, x, y, w, h, reg):
    cv.rect(x + 14, y + 12, 24, 38, WHITE)
    cv.frame(x + 14, y + 12, 24, 38, INK, 2)
    cv.rect(x + 18, y + 17, 16, 10, REG[reg])
    cv.polyline([(x + 38, y + 20), (x + 48, y + 24), (x + 48, y + 40), (x + 42, y + 46)], INK, 2)
    cv.rect(x + 40, y + 44, 5, 6, INK)


def ic_score(cv, x, y, w, h, reg):
    cv.rect(x + 8, y + 16, 44, 26, INK)
    draw_text(cv, "2-0", x + 14, y + 22, 1.1, WHITE, 1.2)
    cv.disc(x + 46, y + 48, 5, WHITE)
    cv.circle(x + 46, y + 48, 5, INK, 1)


def ic_shield(cv, x, y, w, h, reg):
    cv.poly([(x + 14, y + 10), (x + 46, y + 10), (x + 46, y + 30), (x + 30, y + 50), (x + 14, y + 30)], REG[reg])
    cv.polyline([(x + 30, y + 10), (x + 26, y + 22), (x + 34, y + 30), (x + 28, y + 42)], WHITE, 3)


def ic_gavel(cv, x, y, w, h, reg):
    cv.poly([(x + 14, y + 14), (x + 30, y + 8), (x + 36, y + 18), (x + 20, y + 24)], INK)
    cv.thick_line(x + 32, y + 22, x + 46, y + 40, INK, 3)
    cv.rect(x + 12, y + 46, 30, 4, REG[reg])


def ic_flagbldg(cv, x, y, w, h, reg):
    cv.rect(x + 12, y + 20, 30, 30, WHITE)
    cv.frame(x + 12, y + 20, 30, 30, INK, 2)
    for wx in (17, 26, 35):
        for wy in (26, 36):
            cv.rect(x + wx, y + wy, 4, 4, INK)
    cv.thick_line(x + 46, y + 50, x + 46, y + 8, INK, 2)
    cv.poly([(x + 46, y + 8), (x + 56, y + 12), (x + 46, y + 16)], REG[reg])


def ic_hen(cv, x, y, w, h, reg):
    cv.disc(x + 27, y + 35, 14, WHITE)
    cv.circle(x + 27, y + 35, 14, INK, 2)
    cv.disc(x + 42, y + 20, 7, WHITE)
    cv.circle(x + 42, y + 20, 7, INK, 2)
    cv.poly([(x + 48, y + 19), (x + 55, y + 21), (x + 48, y + 23)], REG[reg])
    cv.disc(x + 42, y + 14, 2, REG[reg])
    cv.disc(x + 39, y + 13, 2, REG[reg])
    cv.polyline([(x + 15, y + 30), (x + 6, y + 22), (x + 14, y + 26), (x + 6, y + 18)], INK, 2)


ICONS = {"tent": ic_tent, "rubble": ic_rubble, "globe": ic_globe,
         "parliament": ic_parliament, "quake": ic_quake, "virus": ic_virus,
         "ball": ic_ball, "freezer": ic_freezer, "barrel": ic_barrel,
         "scale": ic_scale, "pump": ic_pump, "score": ic_score,
         "shield": ic_shield, "gavel": ic_gavel, "flagbldg": ic_flagbldg,
         "hen": ic_hen}

# ------------------------------------------------------------- map data
# Simplified continent outlines in (lon, lat). Schematic but recognisable.
LAND_POLYS = [
    # North America
    [(-168, 66), (-158, 58), (-152, 60), (-140, 60), (-135, 57), (-130, 54), (-125, 49),
     (-124, 43), (-120, 34), (-114, 30), (-110, 25), (-105, 20), (-97, 19), (-94, 17),
     (-90, 15), (-86, 13), (-83, 9), (-79, 9), (-81, 13), (-85, 16), (-88, 18), (-90, 21),
     (-97, 26), (-94, 30), (-89, 30), (-84, 30), (-81, 26), (-80, 32), (-76, 35), (-74, 40),
     (-70, 42), (-67, 45), (-60, 47), (-55, 52), (-60, 55), (-65, 58), (-68, 55), (-75, 62),
     (-85, 66), (-95, 68), (-110, 68), (-125, 70), (-140, 70), (-155, 71)],
    # Greenland
    [(-58, 64), (-45, 60), (-35, 68), (-25, 70), (-20, 76), (-35, 80), (-55, 80), (-65, 76), (-62, 70)],
    # Cuba
    [(-85, 22), (-80, 23), (-74, 20), (-80, 21)],
    # South America
    [(-79, 9), (-75, 11), (-72, 12), (-64, 10), (-60, 8), (-52, 5), (-50, 0), (-44, -3),
     (-35, -8), (-38, -15), (-40, -22), (-48, -27), (-53, -33), (-58, -38), (-62, -41),
     (-65, -45), (-68, -50), (-70, -54), (-73, -50), (-73, -42), (-72, -35), (-70, -25),
     (-70, -18), (-75, -15), (-80, -8), (-81, -4), (-80, 1)],
    # Africa
    [(-17, 15), (-10, 28), (-5, 35), (0, 36), (10, 37), (20, 32), (32, 31), (34, 28),
     (35, 24), (38, 20), (43, 12), (48, 11), (51, 10), (46, 5), (41, -2), (40, -10),
     (36, -18), (33, -26), (28, -33), (20, -35), (17, -30), (14, -22), (12, -15),
     (13, -10), (9, -1), (9, 4), (-8, 5), (-13, 8), (-17, 12)],
    # Madagascar
    [(43, -16), (47, -15), (50, -17), (48, -22), (45, -25), (44, -21)],
    # Eurasia
    [(-9, 37), (-9, 43), (-2, 48), (0, 50), (5, 53), (8, 55), (10, 58), (18, 56),
     (21, 60), (25, 65), (30, 70), (40, 68), (50, 69), (60, 70), (70, 72), (80, 73),
     (90, 75), (100, 77), (110, 74), (120, 73), (130, 72), (140, 72), (150, 70), (160, 69),
     (170, 67), (178, 66), (178, 64), (170, 60), (162, 58), (158, 52), (150, 45), (142, 45),
     (140, 40), (135, 35), (130, 33), (126, 38), (122, 32), (120, 28), (114, 22), (109, 18),
     (105, 10), (103, 5), (100, 8), (98, 12), (95, 16), (92, 21), (88, 22), (85, 20),
     (80, 15), (77, 8), (74, 12), (70, 20), (66, 25), (62, 25), (58, 25), (59, 23),
     (55, 17), (48, 14), (45, 12), (43, 15), (40, 20), (38, 25), (35, 29), (34, 31),
     (36, 36), (30, 36), (27, 37), (23, 36), (19, 40), (16, 44), (12, 45), (8, 44), (3, 43), (-2, 37)],
    # Britain
    [(-5, 50), (-3, 53), (-5, 56), (-3, 58), (-1, 57), (0, 53), (1, 51), (-2, 50)],
    # Ireland
    [(-10, 52), (-6, 52), (-6, 55), (-10, 55)],
    # Iceland
    [(-22, 64), (-15, 64), (-14, 66), (-20, 66)],
    # Japan
    [(130, 31), (132, 33), (135, 34), (138, 35), (140, 36), (141, 39), (142, 44), (144, 44),
     (141, 41), (139, 37), (136, 35), (133, 34)],
    # Taiwan
    [(120, 22), (121, 23), (122, 25), (121, 25), (120, 23)],
    # Sri Lanka
    [(80, 6), (81, 7), (82, 9), (81, 9), (80, 7)],
    # Sumatra
    [(95, 5), (100, 0), (104, -3), (106, -6), (103, -6), (99, -2), (95, 2)],
    # Java
    [(105, -6), (110, -7), (114, -8), (114, -7), (108, -6)],
    # Borneo
    [(109, 1), (113, 4), (117, 6), (119, 2), (117, -2), (113, -3), (109, -1)],
    # Sulawesi
    [(119, 0), (121, 1), (123, 0), (121, -3), (120, -5), (119, -2)],
    # New Guinea
    [(131, -1), (136, -2), (141, -3), (146, -6), (150, -10), (146, -9), (141, -8), (136, -6), (132, -4)],
    # Philippines
    [(120, 18), (122, 18), (122, 14), (121, 10), (120, 13)],
    [(124, 8), (126, 7), (126, 5), (124, 6)],
    # Australia
    [(113, -22), (114, -30), (118, -35), (124, -33), (129, -32), (133, -32), (136, -35),
     (140, -38), (145, -38), (150, -37), (153, -32), (153, -27), (150, -23), (146, -19),
     (142, -11), (141, -13), (137, -12), (135, -15), (132, -12), (130, -13), (126, -14),
     (122, -17), (118, -20)],
    # Tasmania
    [(145, -41), (148, -41), (148, -43), (145, -43)],
    # New Zealand (north + south)
    [(173, -35), (176, -38), (178, -38), (175, -41), (173, -39)],
    [(167, -45), (170, -43), (173, -41), (172, -44), (169, -46)],
]

# Badge offsets (dx, dy) from the true pin point, tuned for crowded clusters.
PIN_OFF = {
    1: (18, -14), 2: (38, 20), 3: (14, -14), 4: (-24, 10), 5: (34, -14),
    6: (-18, -16), 7: (26, -2), 8: (-24, 16), 9: (14, -14), 10: (6, -24),
    11: (-14, -12), 12: (-26, 8), 13: (16, -12), 14: (-16, -12), 15: (20, 10),
    16: (-14, 12), 17: (16, -10), 18: (24, -20), 19: (12, 12), 20: (-14, -12),
    21: (26, 14), 22: (-14, 10), 23: (14, -14), 24: (18, 8), 25: (-16, 8),
    26: (14, -12), 28: (-14, -12), 29: (24, 14), 30: (30, -10), 31: (-18, 8),
    32: (-18, -14), 33: (-30, -18), 34: (14, -14), 35: (-14, 12),
}


def draw_map(cv, x, y, w, h, pins):
    cv.rect(x, y, w, h, (168, 196, 216))
    lat_top, lat_bot = 84.0, -58.0

    def proj(lon, lat):
        px = x + (lon + 180.0) / 360.0 * w
        py = y + (lat_top - lat) / (lat_top - lat_bot) * h
        return px, py

    # graticule
    for lon in range(-150, 181, 30):
        gx, _ = proj(lon, 0)
        cv.vline(int(gx), y, h, (150, 182, 205), 1)
    for lat in range(-30, 61, 30):
        _, gy = proj(0, lat)
        cv.hline(x, int(gy), w, (150, 182, 205), 1)
    # ocean labels
    oc = (88, 118, 148)
    draw_text(cv, "PACIFIC", x + 18, y + h - 52, 0.7, oc, 1.0)
    draw_text(cv, "ATLANTIC", x + int(w * 0.33), y + int(h * 0.52), 0.7, oc, 1.0)
    draw_text(cv, "INDIAN", x + int(w * 0.68), y + int(h * 0.72), 0.7, oc, 1.0)
    # land
    for poly_ll in LAND_POLYS:
        pts = [proj(lon, lat) for lon, lat in poly_ll]
        cv.poly(pts, LAND)
        cv.polyline(pts, RULE, 1, closed=True)
    # pins: dot at true location, badge offset, dotted leader.
    # Deterministic repulsion pass so crowded clusters (Europe, Middle
    # East, SE Australia) spread apart instead of piling up; a weak
    # spring keeps each badge near its home offset.
    centers = {}
    for num, reg, lon, lat in pins:
        px, py = proj(lon, lat)
        dx, dy = PIN_OFF.get(num, (0, -14))
        centers[num] = [px + dx, py + dy]
    homes = {n: list(c) for n, c in centers.items()}
    order = [n for n, _, _, _ in pins]

    def relax(spring, rounds):
        for _ in range(rounds):
            for i in range(len(order)):
                for j in range(i + 1, len(order)):
                    a, b = centers[order[i]], centers[order[j]]
                    ddx, ddy = b[0] - a[0], b[1] - a[1]
                    d = math.hypot(ddx, ddy)
                    if 0.01 < d < 23:
                        push = (23 - d) / 2
                        ux, uy = ddx / d, ddy / d
                        a[0] -= ux * push
                        a[1] -= uy * push
                        b[0] += ux * push
                        b[1] += uy * push
            for n in order:
                c, hm = centers[n], homes[n]
                c[0] += (hm[0] - c[0]) * spring
                c[1] += (hm[1] - c[1]) * spring
                c[0] = min(max(c[0], x + 11), x + w - 11)
                c[1] = min(max(c[1], y + 11), y + h - 11)

    relax(0.015, 80)
    relax(0.0, 40)
    for num, reg, lon, lat in pins:
        px, py = proj(lon, lat)
        bx, by = centers[num]
        bx = min(max(bx, x + 11), x + w - 11)
        by = min(max(by, y + 11), y + h - 11)
        dotted_line(cv, px, py, bx, by, INK)
        cv.disc(px, py, 3, WHITE)
        cv.disc(px, py, 2, INK)
        draw_chip(cv, bx, by, 10 if num >= 10 else 9, num, reg)
    cv.frame(x, y, w, h, INK, 2)


# ---------------------------------------------------------------- stories
# Mains: (num, region, "REGION • FIELD" label, headline, sub-label, lon, lat, art key)
# Art keys "gulf"/"bridge"/"summit" are full scenes; the rest are icon keys.
MAINS = [
    (1, "AS", "MIDDLE EAST \u2022 IRAN WAR", "GULF WAR FLARES AGAIN",
     "US SAYS jets hit Qeshm; Iran SAYS drones hit US radar, Bahrain, Kuwait. UNVERIFIED.",
     56.3, 26.6, "gulf"),
    (2, "EU", "EUROPE \u2022 UKRAINE WAR", "KERCH BRIDGE SPAN FALLS",
     "Kyiv SAYS: span fell on night two; Russian hits on Kyiv bridges cut power, water.",
     36.6, 45.3, "bridge"),
    (3, "AS", "ASIA \u2022 DIPLOMACY", "TRUMP FLIES TO XI-PUTIN TALKS",
     "Trump flies to Shenzhen for three-way talks after Manila; Putin is already there.",
     114.1, 22.5, "summit"),
    (4, "AS", "MIDDLE EAST \u2022 CEASEFIRE", "GAZA TRUCE MAY COLLAPSE",
     "Peace board warns the UN council the truce may collapse.", 34.5, 31.4, "tent"),
    (5, "EU", "EUROPE \u2022 UKRAINE WAR", "AID-HUB TOLL RISES TO 40",
     "Zelenskyy raises the aid-hub strike toll to 40 dead.", 35.1, 47.8, "rubble"),
    (6, "EU", "EUROPE \u2022 CLIMATE", "COP31: 144 ITEMS DISPUTED",
     "Antalya talks enter the final stretch; 144 items disputed.", 30.7, 36.9, "globe"),
    (7, "AS", "MIDDLE EAST \u2022 ISRAEL", "EISENKOT TO FORM GOVT",
     "Herzog asks Eisenkot to form Israel's next government.", 35.2, 31.8, "parliament"),
    (8, "EU", "EUROPE \u2022 EARTHQUAKE", "M5.3 QUAKE HITS ROMANIA",
     "Deep quake at 00:48 UTC, felt widely, USGS reports.", 26.5, 45.7, "quake"),
    (9, "AF", "AFRICA \u2022 HEALTH", "EBOLA TOLL PASSES 5,300",
     "Africa CDC: 5,376 dead, 10,444 cases, no vaccine yet.", 29.5, 0.5, "virus"),
    (10, "EU", "EUROPE \u2022 FOOTBALL", "HAALAND PEN SINKS DENMARK",
     "Haaland's 96th-minute penalty seals it; Portugal top group.", 12.6, 55.7, "ball"),
    (11, "SA", "SOUTH AMERICA \u2022 OIL", "US DETAILS $12BN OIL CASH",
     "State Dept details $12bn in oil revenue in 53-page report.", -66.9, 10.5, "barrel"),
]
# List: (num, region, one-line text, lon, lat); 24 items, read down each column.
LISTITEMS = [
    (12, "EU", "Freezers hacked across 7 nations", 9.0, 51.0),
    (13, "OC", "Australia pay gap below 20% at last", 149.1, -35.3),
    (14, "AS", "Pakistan cuts petrol Rs3 a litre", 73.1, 33.7),
    (15, "AS", "Jordan beat Socceroos 2-0 in Doha", 51.5, 25.3),
    (16, "AF", "Congo war goes on despite peace bids", 29.0, -2.5),
    (17, "NA", "27 years for US murder plot", -74.0, 40.7),
    (18, "EU", "Latvia approves Kulbergs cabinet", 24.1, 56.9),
    (19, "AS", "India to unveil H5N1 vaccine Nov 20", 77.4, 23.3),
    (20, "NA", "Guatemala prosecutor shot, wounded", -90.5, 14.6),
    (21, "EU", "UN: 372 civilians killed in Oct", 30.5, 50.4),
    (22, "SA", "Ecuador fishermen sue Trump team", -78.5, -1.0),
    (23, "OC", "One Nation: cut intake by 90%", 153.0, -27.5),
    (24, "OC", "Salvos: 54% of Australians worse off", 151.2, -33.9),
    (25, "OC", "Antibiotic-resistance week opens", 145.0, -37.8),
    (26, "AS", "7 in 10 S. Koreans accept cohabiting", 127.0, 37.6),
    (27, "SP", "C7.2 solar flare at 00:37 UTC", None, None),
    (28, "NA", "Nvidia board: no Huang return", -122.0, 37.4),
    (29, "AS", "Knesset elects Kahana speaker", 35.2, 31.8),
    (30, "AS", "Pakistan condemns Israel's Syria raids", 36.3, 33.5),
    (31, "AS", "28 ALLEGED drone handlers named", 75.8, 26.9),
    (32, "OC", "Study: brain-pressure cases up 7-fold", 145.0, -37.8),
    (33, "EU", "Rooney: I thought of suicide", -2.2, 53.5),
    (34, "AS", "Phages kill resistant Klebsiella in lab", 77.2, 28.6),
    (35, "NA", "Blood test spots colon return early", -89.4, 43.1),
]
SCENES = {"gulf": scene_gulf, "bridge": scene_bridge, "summit": scene_summit}


# ------------------------------------------------------------------ build
def build():
    cv = Canvas(W, H, PAPER)
    cv.frame(6, 6, 1012, 1012, INK, 3)
    X0, X1 = 18, 1006
    CW = X1 - X0

    # ---- masthead: small name, DOMINANT date, small counts line
    draw_text(cv, "WORLD LEDGER", X0, 16, 1.0, INK, 1.3, align="center", box_w=CW)
    ds = 2.9
    while text_width("WEDNESDAY, 18 NOVEMBER 2026", ds) > CW - 16 and ds > 2.5:
        ds -= 0.1
    draw_text(cv, "WEDNESDAY, 18 NOVEMBER 2026", X0, 34, ds, INK, 1.35, align="center", box_w=CW)
    draw_text(cv, "35 STORIES \u2022 6 CONTINENTS \u2022 ONE DAY",
              X0, 82, 1.0, SUB, 1.2, align="center", box_w=CW)
    cv.hline(X0, 100, CW, INK, 2)

    # uniform sub-label size per tier (consistent per tier, no truncation)
    def _fit_sub(sub, w, start):
        ss = start
        while len(wrap_lines(sub, ss, w)) > 2 and ss > 0.76:
            ss -= 0.04
        return ss
    SUB_BIG = min(_fit_sub(m[4], 304, 0.88) for m in MAINS[:3])
    SUB_SMALL = min(_fit_sub(m[4], 226, 0.84) for m in MAINS[3:])

    # ---- 11 mains in 3 rows (3 + 4 + 4): illustration, REGION • FIELD
    # ---- label, bold headline, 2-line sub-label. All framed.
    def draw_main(num, reg, label, head, sub, art, x, y, w, h, big):
        cv.rect(x, y, w, h, WHITE)
        cv.frame(x, y, w, h, INK, 2)
        ih = 92 if big else 64
        if art in SCENES:
            SCENES[art](cv, x + 2, y + 2, w - 4, ih)
        else:
            draw_icon_panel(cv, x + 2, y + 2, w - 4, ih, reg, art)
        cv.hline(x + 2, y + 2 + ih, w - 4, INK, 2)
        draw_chip(cv, x + 20, y + 20, 13 if big else 10, num, reg)
        ls = 0.85 if big else 0.78
        draw_text(cv, label, x + 8, y + 2 + ih + 6, ls, REG_DARK[reg], 1.3)
        hs = fit_size(head, [1.5, 1.42, 1.34] if big else [1.12, 1.05, 0.98], w - 16, 2)
        lines = wrap_lines(head, hs, w - 16)
        ly = y + 2 + ih + 6 + int(14 * ls) + 6
        for ln in lines[:2]:
            draw_text(cv, ln, x + 8, ly, hs, INK, 1.3)
            ly += int(14 * hs) + 5
        ss = SUB_BIG if big else SUB_SMALL
        ly += 1
        for ln in wrap_lines(sub, ss, w - 16)[:2]:
            draw_text(cv, ln, x + 8, ly, ss, SUB, 1.45)
            ly += 13

    ry, rh, rw, gap = 108, 200, 320, 14
    for i in range(3):
        num, reg, label, head, sub, lon, lat, art = MAINS[i]
        draw_main(num, reg, label, head, sub, art, X0 + i * (rw + gap), ry, rw, rh, True)
    rw2, gap2, rh2 = 242, 7, 165
    for r in range(2):
        ry2 = 316 + r * (rh2 + 8)
        for c in range(4):
            num, reg, label, head, sub, lon, lat, art = MAINS[3 + r * 4 + c]
            draw_main(num, reg, label, head, sub, art, X0 + c * (rw2 + gap2), ry2, rw2, rh2, False)

    # ---- bottom: map + 24-item roll call, 2 columns of 12
    by0, bh = 662, 306
    mw = 360
    mx = X0
    cv.rect(mx, by0, mw, bh, WHITE)
    cv.frame(mx, by0, mw, bh, INK, 2)
    draw_text(cv, "WHERE IT HAPPENED", mx + 8, by0 + 8, 1.15, INK, 1.3)
    draw_text(cv, "SCHEMATIC MAP", mx + 8, by0 + 8, 0.85, SUB, 1.2, align="right", box_w=mw - 16)
    pins = [(n, r, lo, la) for (n, r, _lb, _h, _s, lo, la, _k) in MAINS]
    pins += [(n, r, lo, la) for (n, r, _t, lo, la) in LISTITEMS if lo is not None]
    draw_map(cv, mx + 4, by0 + 30, mw - 8, 210, pins)
    # legend: 7 entries (6 regions + space), two rows of four/three
    lx, ly = mx + 10, by0 + 246
    regs = ["EU", "AS", "AF", "NA", "SA", "OC", "SP"]
    for i, r in enumerate(regs):
        gx = lx + (i % 4) * 86
        gy = ly + (i // 4) * 15
        cv.rect(gx, gy, 11, 11, REG[r])
        cv.frame(gx, gy, 11, 11, INK, 1)
        draw_text(cv, REG_NAME[r], gx + 15, gy, 0.75, INK, 1.2)
    draw_text(cv, "Badges offset with leader lines where pins crowd;", mx + 8, by0 + 276, 0.75, SUB, 1.3)
    draw_text(cv, "No. 27 is in space (no pin). Antarctica omitted.", mx + 8, by0 + 289, 0.75, SUB, 1.3)

    lx0 = mx + mw + 10
    lw = X1 - lx0
    cv.rect(lx0, by0, lw, bh, WHITE)
    cv.frame(lx0, by0, lw, bh, INK, 2)
    draw_text(cv, "ALSO ON WEDNESDAY 18 NOVEMBER", lx0 + 8, by0 + 8, 1.15, INK, 1.3)
    col_w = (lw - 16 - 10) // 2
    row_h, row_y0 = 23, by0 + 30
    # uniform list size: one size for every row (consistent per tier)
    lss = 0.82
    while any(text_width(t, lss) > col_w - 26 for (_n, _r, t, _lo, _la) in LISTITEMS) and lss > 0.72:
        lss -= 0.03
    for i, (num, reg, text, lon, lat) in enumerate(LISTITEMS):
        col = i // 12
        row = i % 12
        rx = lx0 + 8 + col * (col_w + 10)
        ry = row_y0 + row * row_h
        draw_chip(cv, rx + 10, ry + 11, 8, num, reg)
        draw_text(cv, text, rx + 24, ry + 4, lss, INK, 1.3)
        if row < 11:
            cv.hline(rx, ry + row_h - 1, col_w, (214, 202, 172), 1)

    # ---- footer: EXACTLY 2 lines (dating sentence + one-line sources)
    draw_text(cv, "Every story was reported on Wednesday 18 November 2026; disputed claims are attributed.",
              X0, 974, 0.78, SUB, 1.3, align="center", box_w=CW)
    src = ("Sources: AAP, Al Jazeera, AppiSToS, DevDiscourse, IANS, Jawawa, Media Alert, "
           "Medianet, Munich Eye, NationPress, Nature, NewsTrend, NOAA, Paris Eye, Pollar, "
           "Socceroos, Stadium Astro, USGS.")
    ss = 0.56
    while text_width(src, ss) > CW - 8 and ss > 0.50:
        ss -= 0.02
    draw_text(cv, src, X0, 991, ss, SUB, 1.3, align="center", box_w=CW)
    return cv


# ------------------------------------------------------- specimen (part 1)
def specimen():
    cv = Canvas(W, H, PAPER)
    y = 30
    draw_text(cv, "ABCDEFGHIJKLM", 30, y, 2.4, INK, 1.2)
    draw_text(cv, "NOPQRSTUVWXYZ", 30, y + 50, 2.4, INK, 1.2)
    draw_text(cv, "abcdefghijklm", 30, y + 100, 2.4, INK, 1.0)
    draw_text(cv, "nopqrstuvwxyz", 30, y + 150, 2.4, INK, 1.0)
    draw_text(cv, "0123456789 . , : ; ! ? - / % $ + = * ' \" ( )", 30, y + 200, 2.4, INK, 1.0)
    draw_text(cv, "WEDNESDAY, 18 NOVEMBER 2026", 30, y + 260, 2.6, INK, 1.3)
    draw_text(cv, "Gulf war flares again as tankers burn", 30, y + 310, 1.7, INK, 1.2)
    draw_text(cv, "US jets hit Qeshm missile site; Iran SAYS drones struck", 30, y + 350, 1.0, SUB, 1.0)
    draw_text(cv, "Board of Peace warns UN Security Council", 30, y + 380, 0.85, SUB, 1.0)
    draw_text(cv, "Guatemala prosecutor wounded in attack  •  C7.2 solar flare", 30, y + 410, 0.95, INK, 1.0)
    draw_text(cv, "The quick brown fox jumps over the lazy dog. 1234567890", 30, y + 450, 1.2, INK, 1.0)
    draw_text(cv, "Pack my box with five dozen liquor jugs!", 30, y + 480, 1.2, INK, 1.0)
    return cv


def main():
    cv = build()
    print(write_output(cv))


if __name__ == "__main__":
    main()
