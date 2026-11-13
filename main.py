"""Neon Horizon - a synthwave sunset drawn pixel by pixel.

A striped sun sinks behind silhouette ridges over a glowing
perspective grid. Pure standard library: a small PNG encoder
(zlib + struct) writes the frame to <out>/entry.png, where
<out> is $ENTRY_OUT when set, else /output.

Deterministic: every pixel is a pure function of its coordinates,
so two runs write byte-identical files.
"""

import os
import struct
import zlib
from math import sin, sqrt

W = 800
H = 800
HOR = 515                    # horizon row
CX = 400.0                   # sun centre x
CY = 452.0                   # sun centre y
SR = 228.0                   # sun radius


def mix(a, b, t):
    return a + (b - a) * t


def gradient(stops, t):
    """Piecewise-linear colour ramp; stops are (pos, (r, g, b))."""
    if t <= stops[0][0]:
        return stops[0][1]
    for i in range(1, len(stops)):
        p1, c1 = stops[i]
        if t <= p1:
            p0, c0 = stops[i - 1]
            u = (t - p0) / (p1 - p0)
            return (mix(c0[0], c1[0], u), mix(c0[1], c1[1], u),
                    mix(c0[2], c1[2], u))
    return stops[-1][1]


SKY = [(0.00, (13, 3, 40)), (0.34, (54, 10, 90)), (0.58, (120, 22, 122)),
       (0.80, (203, 42, 117)), (1.00, (255, 122, 54))]
SUN = [(0.00, (255, 240, 170)), (0.34, (255, 199, 88)),
       (0.58, (255, 132, 62)), (0.80, (250, 72, 112)),
       (1.00, (216, 42, 142))]

FAR = (46, 14, 70)           # far ridge silhouette
FAR_RIM = (255, 96, 172)     # its neon rim light
NEAR = (22, 6, 36)           # near ridge silhouette
GRID = (255, 47, 150)        # grid line neon


def ridge(base, terms):
    """Ridgeline heights: base minus a sum of sines, one per column."""
    return [base - sum(a * sin(x * f + p) for a, f, p in terms)
            for x in range(W)]


H1 = ridge(486, [(26, 0.011, 1.7), (17, 0.023, 0.4), (11, 0.049, 3.1)])
H2 = ridge(508, [(15, 0.017, 4.2), (11, 0.031, 2.0), (7, 0.063, 0.9)])


def star_field():
    """Deterministic star map: key y * W + x -> (r, g, b) to add."""
    stars = {}
    state = 987654321

    def rnd():
        nonlocal state
        state = (1103515245 * state + 12345) & 0x7FFFFFFF
        return state

    for _ in range(260):
        x = rnd() % W
        y = rnd() % 430
        bright = 90 + rnd() % 166
        b = int(bright * (1.0 - y / 560.0))
        tint = rnd() % 3
        if tint == 0:
            col = (b, b, b)
        elif tint == 1:
            col = (b * 4 // 5, b * 4 // 5, b)
        else:
            col = (b, b * 3 // 5, b * 4 // 5)
        stars[y * W + x] = col
        if bright > 225:     # a few bright stars get a plus sparkle
            for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                xx, yy = x + dx, y + dy
                if 0 <= xx < W and 0 <= yy:
                    key = yy * W + xx
                    if key not in stars:
                        stars[key] = (col[0] // 2, col[1] // 2, col[2] // 2)
    return stars


STARS = star_field()


def bird_flock():
    """Distant bird silhouettes: key y * W + x for each dark pixel."""
    pts = set()
    for bx, by in ((168, 138), (222, 112), (618, 96)):
        for dx in range(-7, 8):
            pts.add((by + round(abs(dx) * 0.55)) * W + bx + dx)
        pts.add((by + 2) * W + bx)
    return pts


BIRDS = bird_flock()
XS = [((x - 400) / 400.0) ** 2 for x in range(W)]   # vignette, per column


def sky_pixel(x, y, srow):
    """Colour of a sky pixel (y < HOR); srow is per-row sun data."""
    r, g, b = srow[0], srow[1], srow[2]
    dx = x - CX
    dy = y - CY
    d2 = dx * dx + dy * dy
    gl = 81000.0 / (81000.0 + d2)          # sun glow over the sky
    gl *= gl * 0.26
    r += 255 * gl
    g += 118 * gl
    b += 66 * gl
    r += srow[3]                            # horizon haze
    g += srow[4]
    b += srow[5]
    st = STARS.get(y * W + x)
    if st is not None:
        r += st[0]
        g += st[1]
        b += st[2]
    half, sun, cut = srow[6], srow[7], srow[8]
    if sun is not None and not cut and -half <= dx < half:
        r, g, b = sun
    if y * W + x in BIRDS:
        r, g, b = 12, 5, 26
    if y >= H2[x]:
        r, g, b = NEAR
    elif y >= H1[x]:
        r, g, b = FAR_RIM if y - H1[x] < 2.0 else FAR
    return r, g, b


def floor_pixel(x, y, frow):
    """Colour of a floor pixel (y >= HOR); frow is per-row data."""
    br, bg, bb, v, depth, hline = frow
    r, g, b = br, bg, bb
    dx = x - CX
    wdt = 26.0 + v * 0.6                    # sun reflection column
    rf = 1.0 - abs(dx) / wdt
    if rf > 0:
        k = rf * rf * (1.0 - depth * 0.55) * 0.55
        r += 255 * k
        g += 116 * k
        b += 58 * k
    s = (dx * 6.25 / v) % 1.0               # radial grid lines
    w = 11.0 / v
    if w > 0.5:
        w = 0.5
    if hline or s < w or s > 1.0 - w:
        gi = (0.30 + 0.70 * depth) * (v / 30.0 if v < 30 else 1.0)
        r += (GRID[0] - r) * gi
        g += (GRID[1] - g) * gi
        b += (GRID[2] - b) * gi
    return r, g, b


def clamp(v):
    return 255 if v >= 255 else int(v)


def render():
    rows = []
    for y in range(H):
        row = bytearray(W * 3)
        if y < HOR:
            base = gradient(SKY, y / HOR)
            hz = 1.0 - (HOR - y) / 120.0
            if hz < 0.0:
                hz = 0.0
            haze = (255 * hz * hz * 0.30, 120 * hz * hz * 0.30,
                    50 * hz * hz * 0.30)
            dy = y - CY
            half, sun, cut = 0.0, None, False
            if abs(dy) < SR:
                half = sqrt(SR * SR - dy * dy)
                v = (dy + SR) / (2 * SR)
                sun = gradient(SUN, v)
                if v > 0.40:                # stripe cuts, widening
                    u = v - 0.40            # as the sun sinks
                    cut = (dy % (38.0 - 26.0 * u)) < (2.0 + 44.0 * u)
            srow = (base[0], base[1], base[2], haze[0], haze[1], haze[2],
                    half, sun, cut)
            yterm = ((y - 400) / 400.0) ** 2
            for x in range(W):
                r, g, b = sky_pixel(x, y, srow)
                f = 1.0 - 0.20 * (yterm + XS[x])       # vignette
                i = x * 3
                row[i] = clamp(r * f)
                row[i + 1] = clamp(g * f)
                row[i + 2] = clamp(b * f)
        else:
            v = y - HOR + 1
            depth = v / (H - HOR)
            q = 90.0 / v
            hthick = 170.0 / (v * v)
            hline = (q - int(q)) < (0.85 if hthick > 0.85 else hthick)
            frow = (26 - 14 * depth, 6 - 3 * depth, 44 - 18 * depth,
                    v, depth, hline)
            yterm = ((y - 400) / 400.0) ** 2
            for x in range(W):
                r, g, b = floor_pixel(x, y, frow)
                f = 1.0 - 0.20 * (yterm + XS[x])       # vignette
                i = x * 3
                row[i] = clamp(r * f)
                row[i + 1] = clamp(g * f)
                row[i + 2] = clamp(b * f)
        rows.append(row)
    return rows


def png_bytes(rows):
    """Encode RGB rows as a PNG: filter type 2 (Up), zlib level 9."""
    out = bytearray(b"\x89PNG\r\n\x1a\n")

    def chunk(tag, data):
        out.extend(struct.pack(">I", len(data)))
        out.extend(tag)
        out.extend(data)
        out.extend(struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF))

    chunk(b"IHDR", struct.pack(">IIBBBBB", W, H, 8, 2, 0, 0, 0))
    raw = bytearray()
    prev = bytes(W * 3)
    for row in rows:
        raw.append(2)
        raw.extend(bytes((a - b) & 0xFF for a, b in zip(row, prev)))
        prev = bytes(row)
    chunk(b"IDAT", zlib.compress(bytes(raw), 9))
    chunk(b"IEND", b"")
    return bytes(out)


def main():
    outdir = (os.environ.get("ENTRY_OUT")
              or os.environ.get("MAKEFUN_OUTPUT_DIR") or "/output")
    os.makedirs(outdir, exist_ok=True)
    with open(os.path.join(outdir, "entry.png"), "wb") as f:
        f.write(png_bytes(render()))


if __name__ == "__main__":
    main()
