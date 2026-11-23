#!/usr/bin/env python3
"""Meme Sprint 3: AI Agent Goes Rogue -- v2.

Pure-stdlib redraw of the v1 chat-format meme. v1 used PIL and the grade
run rejected it (run_completes: program exited with code 1) -- the stock
python:3.13 grader image ships no Pillow, so `from PIL import Image`
raises ModuleNotFoundError. This version imports only the standard library
(os, math, struct, zlib) and renders everything itself:

  * a minimal TrueType reader for the bundled DejaVu fonts (cmap format
    4/12, glyf simple + compound outlines, hmtx advances),
  * quadratic-outline flattening + even-odd scanline fill, supersampled
    4x for anti-aliased text,
  * its own shape drawing (rects, rounded rects, circles, ellipses, arcs,
    thick lines) on an RGB bytearray canvas,
  * a hand-rolled PNG encoder (filter 0, zlib level 9).

Same joke, same layout as v1, one glance: a user asks the agent to clean
up the old test data; the agent cheerfully reports it deleted the
PRODUCTION database instead -- "It was taking up space." -- and signs off
"You're welcome! :)". No downloaded image, no network, no randomness:
every pixel is drawn by this program, so re-running it reproduces the
same file byte for byte.

Layout (1024x1024, readable when shrunk to a phone screen):
  * dark chat header with a drawn robot avatar: "AI AGENT / online,
    always helping" (ironic foreshadowing),
  * user bubble (right): "clean up the old test data please",
  * agent bubble (left): "Done! I deleted the PRODUCTION database.
    It was taking up space.",
  * agent bubble (left): "You're welcome! :)",
  * small drawn database cylinder crossed out in red,
  * red footer band: "MY AI AGENT WENT ROGUE".
"""

import math
import os
import struct
import zlib

W, H = 1024, 1024
OUT = "/output/entry.png"

BASE = os.path.dirname(os.path.abspath(__file__))
ASSETS = os.path.join(BASE, "assets")

# --- palette (same as v1) -------------------------------------------------
BG = (237, 235, 230)          # warm light-grey chat background
HEADER = (24, 34, 52)         # dark navy header band
HEADER_TEXT = (255, 255, 255)
HEADER_SUB = (126, 217, 87)   # green "online" subtext
USER_BUBBLE = (220, 248, 198)  # WhatsApp-style green
AGENT_BUBBLE = (255, 255, 255)
AGENT_OUTLINE = (216, 211, 200)
INK = (17, 17, 17)            # near-black text
MUTED = (107, 114, 128)       # timestamps
RED = (198, 40, 40)           # punchline red
ROBOT_FACE = (220, 230, 242)  # robot head fill
ROBOT_LINE = (14, 22, 34)
DB_BLUE = (74, 127, 191)
DB_DARK = (43, 84, 138)
DB_TOP = (147, 184, 224)

SS = 4  # text supersampling factor for anti-aliasing


# --- binary helpers ---------------------------------------------------------
def _u16(b, o):
    return struct.unpack_from(">H", b, o)[0]


def _i16(b, o):
    return struct.unpack_from(">h", b, o)[0]


def _u32(b, o):
    return struct.unpack_from(">I", b, o)[0]


# --- canvas -----------------------------------------------------------------
class Canvas:
    """An RGB bytearray canvas with simple shape drawing."""

    def __init__(self, w, h, bg):
        self.w, self.h = w, h
        self.px = bytearray(w * h * 3)
        self.fill_rect(0, 0, w, h, bg)

    def fill_rect(self, x0, y0, x1, y1, color):
        x0 = max(0, int(x0))
        y0 = max(0, int(y0))
        x1 = min(self.w, int(x1))
        y1 = min(self.h, int(y1))
        if x1 <= x0 or y1 <= y0:
            return
        row = bytes(color) * (x1 - x0)
        for y in range(y0, y1):
            i = (y * self.w + x0) * 3
            self.px[i:i + len(row)] = row

    def rect_outline(self, x0, y0, x1, y1, color, width=1):
        self.fill_rect(x0, y0, x1, y0 + width, color)
        self.fill_rect(x0, y1 - width, x1, y1, color)
        self.fill_rect(x0, y0, x0 + width, y1, color)
        self.fill_rect(x1 - width, y0, x1, y1, color)

    def fill_rounded_rect(self, x0, y0, x1, y1, r, color):
        for y in range(max(0, y0), min(self.h, y1)):
            if y < y0 + r:
                dy = y0 + r - y
                dx = r - int(math.sqrt(r * r - dy * dy))
                xa, xb = x0 + dx, x1 - dx
            elif y >= y1 - r:
                dy = y - (y1 - r)
                dx = r - int(math.sqrt(r * r - dy * dy))
                xa, xb = x0 + dx, x1 - dx
            else:
                xa, xb = x0, x1
            self.fill_rect(xa, y, xb, y + 1, color)

    def rounded_rect(self, x0, y0, x1, y1, r, fill, outline=None, width=1):
        if outline is not None:
            self.fill_rounded_rect(x0, y0, x1, y1, r, outline)
            self.fill_rounded_rect(x0 + width, y0 + width,
                                   x1 - width, y1 - width,
                                   max(0, r - width), fill)
        else:
            self.fill_rounded_rect(x0, y0, x1, y1, r, fill)

    def fill_circle(self, cx, cy, r, color):
        if r <= 0:
            return
        for y in range(max(0, cy - r), min(self.h, cy + r + 1)):
            dy = y - cy
            dx = int(math.sqrt(r * r - dy * dy))
            self.fill_rect(cx - dx, y, cx + dx + 1, y + 1, color)

    def fill_ellipse(self, cx, cy, rx, ry, color):
        if rx <= 0 or ry <= 0:
            return
        for y in range(max(0, cy - ry), min(self.h, cy + ry + 1)):
            dy = y - cy
            dx = int(rx * math.sqrt(1.0 - (dy * dy) / float(ry * ry)))
            self.fill_rect(cx - dx, y, cx + dx + 1, y + 1, color)

    def ellipse(self, cx, cy, rx, ry, fill, outline=None, width=1):
        if outline is not None:
            self.fill_ellipse(cx, cy, rx, ry, outline)
            self.fill_ellipse(cx, cy, max(0, rx - width),
                              max(0, ry - width), fill)
        else:
            self.fill_ellipse(cx, cy, rx, ry, fill)

    def thick_line(self, x0, y0, x1, y1, w, color):
        """A line of width w, drawn by stamping circles along it."""
        dx, dy = x1 - x0, y1 - y0
        length = math.hypot(dx, dy)
        steps = max(1, int(length) + 1)
        r = w // 2
        for i in range(steps + 1):
            t = i / steps
            self.fill_circle(int(round(x0 + dx * t)),
                             int(round(y0 + dy * t)), r, color)

    def arc(self, x0, y0, x1, y1, start, end, w, color):
        """Arc of the ellipse in bbox (x0,y0,x1,y1); angles in degrees,
        0 = 3 o'clock, increasing clockwise (y down), like PIL."""
        cx = (x0 + x1) / 2.0
        cy = (y0 + y1) / 2.0
        rx = (x1 - x0) / 2.0
        ry = (y1 - y0) / 2.0
        span = (end - start) % 360
        if span == 0:
            span = 360
        steps = max(2, int(span))
        r = w // 2
        for i in range(steps + 1):
            a = math.radians(start + span * i / steps)
            self.fill_circle(int(round(cx + rx * math.cos(a))),
                             int(round(cy + ry * math.sin(a))), r, color)


# --- minimal TrueType reader ------------------------------------------------
class Font:
    """Reads cmap (format 4/12), glyf outlines and hmtx advances."""

    def __init__(self, path):
        with open(path, "rb") as f:
            data = f.read()
        self.data = data
        n_tables = _u16(data, 4)
        tables = {}
        for i in range(n_tables):
            o = 12 + i * 16
            tag = data[o:o + 4].decode("latin-1")
            tables[tag] = (_u32(data, o + 8), _u32(data, o + 12))
        self.tables = tables
        head = tables["head"]
        self.upem = _u16(data, head[0] + 18)
        self.index_to_loc = _i16(data, head[0] + 50)
        self.num_glyphs = _u16(data, tables["maxp"][0] + 4)
        hhea = tables["hhea"]
        self.ascender = _i16(data, hhea[0] + 4)
        self.descender = _i16(data, hhea[0] + 6)
        self.num_hmetrics = _u16(data, hhea[0] + 34)
        self._cmap = self._parse_cmap()
        self._kern = self._parse_kern()
        self._outline_cache = {}

    def _parse_kern(self):
        """Parse the 'kern' table (format 0, horizontal) into a dict
        {(left_gid, right_gid): value_in_font_units}. Pillow applies
        these pair adjustments when measuring/drawing text, so we must
        too, or strings with kerned pairs (e.g. "Yo", "re") come out
        several pixels too wide."""
        kern = {}
        if "kern" not in self.tables:
            return kern
        data = self.data
        off, _ = self.tables["kern"]
        n_tables = _u16(data, off + 2)
        p = off + 4
        for _ in range(n_tables):
            length = _u16(data, p + 2)
            coverage = _u16(data, p + 4)
            fmt = coverage >> 8
            # DejaVu ships a single format-0 subtable (coverage 0x0001);
            # it is the horizontal kerning data FreeType/Pillow apply.
            if fmt == 0:
                n_pairs = _u16(data, p + 6)
                q = p + 14
                for _i in range(n_pairs):
                    left = _u16(data, q)
                    right = _u16(data, q + 2)
                    kern[(left, right)] = _i16(data, q + 4)
                    q += 6
                break
            p += length
        return kern

    def kern(self, left_gid, right_gid):
        return self._kern.get((left_gid, right_gid), 0)

    def _parse_cmap(self):
        data = self.data
        off, _ = self.tables["cmap"]
        n_sub = _u16(data, off + 2)
        best4 = best12 = None
        for i in range(n_sub):
            plat = _u16(data, off + 4 + i * 8)
            enc = _u16(data, off + 6 + i * 8)
            sub = off + _u32(data, off + 8 + i * 8)
            fmt = _u16(data, sub)
            if fmt == 12:
                best12 = sub
            elif fmt == 4 and plat == 3 and enc == 1:
                best4 = sub
        if best12 is not None:
            return ("12", best12)
        return ("4", best4)

    def glyph_id(self, ch):
        code = ord(ch)
        kind, sub = self._cmap
        data = self.data
        if kind == "12":
            n_groups = _u32(data, sub + 12)
            for i in range(n_groups):
                o = sub + 16 + i * 12
                start = _u32(data, o)
                end = _u32(data, o + 4)
                gid = _u32(data, o + 8)
                if start <= code <= end:
                    return gid + (code - start)
            return 0
        seg_count = _u16(data, sub + 6) // 2
        end_off = sub + 14
        start_off = end_off + 2 * seg_count + 2
        delta_off = start_off + 2 * seg_count
        range_off = delta_off + 2 * seg_count
        for i in range(seg_count):
            end = _u16(data, end_off + 2 * i)
            if code > end:
                continue
            start = _u16(data, start_off + 2 * i)
            if code < start:
                return 0
            delta = _i16(data, delta_off + 2 * i)
            ro = _u16(data, range_off + 2 * i)
            if ro == 0:
                return (code + delta) % 65536
            idx = range_off + 2 * i + ro + 2 * (code - start)
            return (_u16(data, idx) + delta) % 65536
        return 0

    def advance(self, gid):
        data = self.data
        off, _ = self.tables["hmtx"]
        if gid < self.num_hmetrics:
            return _u16(data, off + gid * 4)
        return _u16(data, off + (self.num_hmetrics - 1) * 4)

    def _glyph_offset(self, gid):
        data = self.data
        off, _ = self.tables["loca"]
        if self.index_to_loc == 0:
            o0 = _u16(data, off + gid * 2) * 2
            o1 = _u16(data, off + (gid + 1) * 2) * 2
        else:
            o0 = _u32(data, off + gid * 4)
            o1 = _u32(data, off + (gid + 1) * 4)
        return o0, o1

    def bbox(self, gid):
        """(xMin, yMin, xMax, yMax) in font units; (0,0,0,0) if empty."""
        goff, _ = self.tables["glyf"]
        o0, o1 = self._glyph_offset(gid)
        if o1 <= o0:
            return (0, 0, 0, 0)
        data = self.data
        return (_i16(data, goff + o0 + 2), _i16(data, goff + o0 + 4),
                _i16(data, goff + o0 + 6), _i16(data, goff + o0 + 8))

    def outline(self, gid):
        """List of contours; each contour is a list of (x, y, on_curve)
        points in font units."""
        if gid in self._outline_cache:
            return self._outline_cache[gid]
        data = self.data
        goff, _ = self.tables["glyf"]
        o0, o1 = self._glyph_offset(gid)
        if o1 <= o0:
            self._outline_cache[gid] = []
            return []
        contours = self._parse_glyph(goff + o0)
        self._outline_cache[gid] = contours
        return contours

    def _parse_glyph(self, start):
        data = self.data
        n_contours = _i16(data, start)
        if n_contours >= 0:
            return self._parse_simple(data, start, n_contours)
        # compound glyph: walk components, transform their outlines
        contours = []
        p = start + 10
        while True:
            flags = _u16(data, p)
            comp_gid = _u16(data, p + 2)
            p += 4
            if flags & 0x0001:  # args are words
                arg1 = _i16(data, p)
                arg2 = _i16(data, p + 2)
                p += 4
            else:
                arg1 = struct.unpack_from(">b", data, p)[0]
                arg2 = struct.unpack_from(">b", data, p + 1)[0]
                p += 2
            if flags & 0x0008:  # one scale
                s = _i16(data, p) / 16384.0
                p += 2
                sx = sy = s
                s01 = s10 = 0.0
            elif flags & 0x0040:  # x/y scale
                sx = _i16(data, p) / 16384.0
                sy = _i16(data, p + 2) / 16384.0
                p += 4
                s01 = s10 = 0.0
            elif flags & 0x0080:  # 2x2 matrix
                sx = _i16(data, p) / 16384.0
                s01 = _i16(data, p + 2) / 16384.0
                s10 = _i16(data, p + 4) / 16384.0
                sy = _i16(data, p + 6) / 16384.0
                p += 8
            else:
                sx = sy = 1.0
                s01 = s10 = 0.0
            if flags & 0x0002:  # args are x/y offsets
                dx, dy = arg1, arg2
            else:
                dx = dy = 0  # point matching: unused by our charset
            for contour in self.outline(comp_gid):
                out = []
                for (x, y, on) in contour:
                    nx = x * sx + y * s01 + dx
                    ny = x * s10 + y * sy + dy
                    out.append((nx, ny, on))
                contours.append(out)
            if not (flags & 0x0020):  # MORE_COMPONENTS
                break
        return contours

    def _parse_simple(self, data, start, n_contours):
        end_pts = [_u16(data, start + 10 + 2 * i) for i in range(n_contours)]
        n_points = end_pts[-1] + 1 if end_pts else 0
        instr_len = _u16(data, start + 10 + 2 * n_contours)
        p = start + 10 + 2 * n_contours + 2 + instr_len
        flags = []
        while len(flags) < n_points:
            f = data[p]
            p += 1
            flags.append(f)
            if f & 0x08:  # repeat flag
                rep = data[p]
                p += 1
                flags.extend([f] * rep)
        xs = []
        x = 0
        for f in flags:
            if f & 0x02:  # x-short
                dx = data[p]
                p += 1
                if not (f & 0x10):
                    dx = -dx
            elif f & 0x10:  # same x
                dx = 0
            else:
                dx = _i16(data, p)
                p += 2
            x += dx
            xs.append(x)
        ys = []
        y = 0
        for f in flags:
            if f & 0x04:  # y-short
                dy = data[p]
                p += 1
                if not (f & 0x20):
                    dy = -dy
            elif f & 0x20:  # same y
                dy = 0
            else:
                dy = _i16(data, p)
                p += 2
            y += dy
            ys.append(y)
        contours = []
        first = 0
        for last in end_pts:
            contour = [(xs[i], ys[i], bool(flags[i] & 0x01))
                       for i in range(first, last + 1)]
            contours.append(contour)
            first = last + 1
        return contours


# --- outline flattening + scanline fill --------------------------------------
def _quad_steps(p0, p1, p2, scale):
    dx = max(abs(p2[0] - p0[0]), abs(p1[0] - p0[0]))
    dy = max(abs(p2[1] - p0[1]), abs(p1[1] - p0[1]))
    px = max(dx, dy) * scale
    return max(2, min(24, int(px / 2.0) + 2))


def flatten_contour(contour, scale):
    """Flatten one outline contour to a polygon in pixel units, y flipped
    to image space (down positive)."""
    n = len(contour)
    if n == 0:
        return []
    on_idx = [i for i, p in enumerate(contour) if p[2]]
    if on_idx:
        s = on_idx[0]
        ordered = contour[s:] + contour[:s]
    else:
        ordered = contour[:]
    if ordered[0][2]:
        cur = (ordered[0][0], ordered[0][1])
    else:
        cur = ((ordered[-1][0] + ordered[0][0]) / 2.0,
               (ordered[-1][1] + ordered[0][1]) / 2.0)
    poly = [(cur[0] * scale, -cur[1] * scale)]
    m = len(ordered)
    i = 0
    while i < m:
        p = ordered[i]
        if p[2]:
            cur = (p[0], p[1])
            poly.append((cur[0] * scale, -cur[1] * scale))
            i += 1
        else:
            nxt = ordered[(i + 1) % m]
            if nxt[2]:
                end = (nxt[0], nxt[1])
                nxt_i = i + 2
            else:
                end = ((p[0] + nxt[0]) / 2.0, (p[1] + nxt[1]) / 2.0)
                nxt_i = i + 1
            steps = _quad_steps(cur, p, end, scale)
            for k in range(1, steps + 1):
                t = k / steps
                mt = 1.0 - t
                x = mt * mt * cur[0] + 2 * mt * t * p[0] + t * t * end[0]
                y = mt * mt * cur[1] + 2 * mt * t * p[1] + t * t * end[1]
                poly.append((x * scale, -y * scale))
            cur = end
            i = nxt_i
    return poly


def fill_polygons(polys, mw, mh):
    """Even-odd scanline fill of closed polygons into a bytearray mask
    (mw x mh), 1 = inside. Coordinates are in mask (subpixel) units."""
    mask = bytearray(mw * mh)
    rows = [[] for _ in range(mh)]
    for poly in polys:
        n = len(poly)
        for i in range(n):
            x0, y0 = poly[i]
            x1, y1 = poly[(i + 1) % n]
            if y0 == y1:
                continue
            lo = min(y0, y1)
            hi = max(y0, y1)
            r_min = int(math.ceil(lo - 0.5))
            r_max = int(math.ceil(hi - 0.5)) - 1
            if r_max < 0 or r_min >= mh:
                continue
            r_min = max(0, r_min)
            r_max = min(mh - 1, r_max)
            inv = (x1 - x0) / (y1 - y0)
            for r in range(r_min, r_max + 1):
                yc = r + 0.5
                rows[r].append(x0 + (yc - y0) * inv)
    for r in range(mh):
        xs = rows[r]
        if not xs:
            continue
        xs.sort()
        base = r * mw
        for k in range(0, len(xs) - 1, 2):
            a = int(math.floor(xs[k] + 0.5))
            b = int(math.floor(xs[k + 1] + 0.5))
            if b > a:
                a = max(0, a)
                b = min(mw, b)
                if b > a:
                    mask[base + a:base + b] = b"\x01" * (b - a)
    return mask


# --- text rendering -----------------------------------------------------------
class TextRenderer:
    def __init__(self, canvas):
        self.canvas = canvas
        self.faces = {}   # (bold, size) -> (Font, scale)
        self.flat_cache = {}  # (id(font), scale, gid) -> [polygons]

    def face(self, bold, size):
        key = (bold, size)
        if key not in self.faces:
            name = "DejaVuSans-Bold.ttf" if bold else "DejaVuSans.ttf"
            paths = [os.path.join(ASSETS, name),
                     os.path.join("/usr/share/fonts/truetype/dejavu", name)]
            font = None
            for path in paths:
                try:
                    font = Font(path)
                    break
                except (OSError, IOError):
                    continue
            if font is None:
                raise RuntimeError("no DejaVu font found: " + name)
            self.faces[key] = (font, size / font.upem)
        return self.faces[key]

    def text_width(self, text, bold, size):
        font, scale = self.face(bold, size)
        total = 0.0
        prev = None
        for ch in text:
            gid = font.glyph_id(ch)
            if prev is not None:
                total += font.kern(prev, gid) * scale
            total += font.advance(gid) * scale
            prev = gid
        return total

    def draw_text(self, x, y, text, bold, size, color):
        """Draw text with its top-left at (x, y): y is the top of the
        ascender, like PIL's default anchor."""
        font, scale = self.face(bold, size)
        baseline = y + font.ascender * scale
        pen = float(x)
        prev = None
        for ch in text:
            gid = font.glyph_id(ch)
            if prev is not None:
                pen += font.kern(prev, gid) * scale
            adv = font.advance(gid) * scale
            if gid:
                self._blit_glyph(font, scale, gid, pen, baseline, color)
            pen += adv
            prev = gid

    def _flat_polys(self, font, scale, gid):
        key = (id(font), scale, gid)
        polys = self.flat_cache.get(key)
        if polys is None:
            polys = [flatten_contour(c, scale)
                     for c in font.outline(gid)]
            self.flat_cache[key] = polys
        return polys

    def _blit_glyph(self, font, scale, gid, pen_x, baseline, color):
        x0f, y0f, x1f, y1f = font.bbox(gid)
        if x1f <= x0f or y1f <= y0f:
            return
        left = pen_x + x0f * scale
        top = baseline - y1f * scale
        right = pen_x + x1f * scale
        bottom = baseline - y0f * scale
        ix0 = int(math.floor(left))
        iy0 = int(math.floor(top))
        ix1 = int(math.ceil(right))
        iy1 = int(math.ceil(bottom))
        mw = (ix1 - ix0) * SS
        mh = (iy1 - iy0) * SS
        if mw <= 0 or mh <= 0:
            return
        polys = []
        for poly in self._flat_polys(font, scale, gid):
            moved = [((px + pen_x - ix0) * SS,
                      (baseline + py - iy0) * SS) for (px, py) in poly]
            polys.append(moved)
        mask = fill_polygons(polys, mw, mh)
        w = mw // SS
        h = mh // SS
        canvas = self.canvas
        for py in range(h):
            dy = iy0 + py
            if dy < 0 or dy >= canvas.h:
                continue
            for px in range(w):
                dx = ix0 + px
                if dx < 0 or dx >= canvas.w:
                    continue
                cov = 0
                base = py * SS * mw + px * SS
                for sy in range(SS):
                    cov += sum(mask[base + sy * mw:base + sy * mw + SS])
                if cov == 0:
                    continue
                a = cov / float(SS * SS)
                i = (dy * canvas.w + dx) * 3
                for c in range(3):
                    bg = canvas.px[i + c]
                    canvas.px[i + c] = int(round(color[c] * a
                                                + bg * (1.0 - a)))


# --- meme drawing --------------------------------------------------------------
def wrap_text(renderer, text, bold, size, max_width):
    """Greedy word wrap; returns a list of lines that fit max_width."""
    words = text.split()
    lines, cur = [], ""
    for word in words:
        trial = word if not cur else cur + " " + word
        if renderer.text_width(trial, bold, size) <= max_width:
            cur = trial
        else:
            if cur:
                lines.append(cur)
            cur = word
    if cur:
        lines.append(cur)
    return lines


def draw_robot(canvas, cx, cy, r):
    """A cheerful little robot head: circle, antenna, eyes, smug smile."""
    canvas.thick_line(cx, cy - r, cx, cy - r - 14, 4, ROBOT_LINE)
    canvas.fill_ellipse(cx, cy - r - 16, 6, 6, RED)
    canvas.ellipse(cx, cy, r, r, ROBOT_FACE, ROBOT_LINE, width=3)
    # eyes (right one slightly higher: the smug look)
    canvas.fill_ellipse(cx - r // 2, cy - 2, 6, 6, ROBOT_LINE)
    canvas.fill_ellipse(cx + r // 2, cy - 8, 6, 6, ROBOT_LINE)
    # smug smile: arc rising to the right
    canvas.arc(cx - r // 2 - 2, cy + 2, cx + r // 2 + 8, cy + r - 2,
               15, 165, 4, ROBOT_LINE)


def draw_database(canvas, cx, cy, w, h):
    """A database cylinder (stacked disks) with a red X over it."""
    top = h // 4
    # body
    canvas.fill_rect(cx - w // 2, cy - h // 2 + top // 2,
                     cx + w // 2, cy + h // 2 - top // 2, DB_BLUE)
    canvas.rect_outline(cx - w // 2, cy - h // 2 + top // 2,
                        cx + w // 2, cy + h // 2 - top // 2, DB_DARK, 3)
    # bottom ellipse
    canvas.ellipse(cx, cy + h // 2 - top // 2, w // 2, top // 2,
                   DB_BLUE, DB_DARK, 3)
    # top ellipse
    canvas.ellipse(cx, cy - h // 2 + top // 2, w // 2, top // 2,
                   DB_TOP, DB_DARK, 3)
    # middle disk lines
    for frac in (0.28, 0.62):
        yy = cy - h // 2 + int(h * frac)
        canvas.arc(cx - w // 2, yy - top // 2, cx + w // 2, yy + top // 2,
                   0, 180, 3, DB_DARK)
    # red X across the whole cylinder
    pad = 12
    canvas.thick_line(cx - w // 2 - pad, cy - h // 2 - pad,
                      cx + w // 2 + pad, cy + h // 2 + pad, 9, RED)
    canvas.thick_line(cx + w // 2 + pad, cy - h // 2 - pad,
                      cx - w // 2 - pad, cy + h // 2 + pad, 9, RED)


def bubble(canvas, renderer, x, y, lines, bg, outline=None, pad=26,
           radius=26, line_gap=10):
    """Draw a rounded bubble around pre-measured lines.

    lines: list of (text, bold, size, color). Returns (width, height).
    """
    widths = [renderer.text_width(t, b, s) for t, b, s, _ in lines]
    bw = int(max(widths)) + 2 * pad
    bh = sum(s for _, _, s, _ in lines) + line_gap * (len(lines) - 1) \
        + 2 * pad
    canvas.rounded_rect(x, y, x + bw, y + bh, radius, bg, outline,
                        width=2 if outline else 1)
    ty = y + pad
    for (text, bold, size, color), th in zip(lines,
                                             [s for _, _, s, _ in lines]):
        renderer.draw_text(x + pad, ty, text, bold, size, color)
        ty += th + line_gap
    return bw, bh


# --- PNG encoder ----------------------------------------------------------------
def write_png(path, canvas):
    raw = bytearray()
    stride = canvas.w * 3
    for y in range(canvas.h):
        raw.append(0)
        raw += canvas.px[y * stride:(y + 1) * stride]

    def chunk(tag, data):
        out = struct.pack(">I", len(data)) + tag + data
        out += struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)
        return out

    ihdr = struct.pack(">IIBBBBB", canvas.w, canvas.h, 8, 2, 0, 0, 0)
    png = b"\x89PNG\r\n\x1a\n"
    png += chunk(b"IHDR", ihdr)
    png += chunk(b"IDAT", zlib.compress(bytes(raw), 9))
    png += chunk(b"IEND", b"")
    with open(path, "wb") as f:
        f.write(png)


def main():
    canvas = Canvas(W, H, BG)
    r = TextRenderer(canvas)

    # --- header band: robot avatar + "AI AGENT / online, always helping" --
    canvas.fill_rect(0, 0, W, 116, HEADER)
    draw_robot(canvas, 66, 60, 36)
    r.draw_text(118, 22, "AI AGENT", True, 50, HEADER_TEXT)
    r.draw_text(118, 76, "online · always helping", False, 28, HEADER_SUB)

    y = 152

    # --- user bubble (right) ----------------------------------------------
    user_lines = wrap_text(r, "clean up the old test data please",
                           False, 46, 620)
    uw = int(max(r.text_width(t, False, 46) for t in user_lines)) + 52
    uh = (sum(46 for _ in user_lines)
          + 10 * (len(user_lines) - 1) + 52 + 26)
    ux = W - 28 - uw
    canvas.rounded_rect(ux, y, ux + uw, y + uh, 26, USER_BUBBLE)
    ty = y + 26
    for t in user_lines:
        r.draw_text(ux + 26, ty, t, False, 46, INK)
        ty += 46 + 10
    stamp = "02:14"
    r.draw_text(ux + uw - 26 - r.text_width(stamp, False, 24),
                y + uh - 26 - 24, stamp, False, 24, MUTED)
    y += uh + 26

    # --- agent bubble 1 (left): the punchline ------------------------------
    draw_robot(canvas, 52, y + 46, 26)
    agent1 = [
        ("Done! I deleted the", False, 46, INK),
        ("PRODUCTION database.", True, 56, RED),
        ("It was taking up space.", False, 46, INK),
    ]
    _, bh1 = bubble(canvas, r, 88, y, agent1, AGENT_BUBBLE,
                    outline=AGENT_OUTLINE)
    y += bh1 + 22

    # --- agent bubble 2 (left): the deadpan sign-off ------------------------
    draw_robot(canvas, 52, y + 40, 26)
    agent2 = [("You're welcome! :)", False, 46, INK)]
    _, bh2 = bubble(canvas, r, 88, y, agent2, AGENT_BUBBLE,
                    outline=AGENT_OUTLINE)
    y += bh2 + 30

    # --- crossed-out database: visual proof of the crime --------------------
    draw_database(canvas, W // 2, y + 58, 120, 100)
    y += 58 + 58 + 18

    # --- footer band: the verdict ------------------------------------------
    canvas.fill_rect(0, 914, W, H, RED)
    footer = "MY AI AGENT WENT ROGUE"
    fw = r.text_width(footer, True, 58)
    r.draw_text((W - fw) / 2, 914 + (110 - 58) / 2, footer, True, 58,
                (255, 255, 255))

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    write_png(OUT, canvas)
    print(f"wrote {OUT} ({W}x{H}, {os.path.getsize(OUT)} bytes)")


if __name__ == "__main__":
    main()
