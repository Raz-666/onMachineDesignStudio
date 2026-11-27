#!/usr/bin/env python3
"""R287: render the REAL applied texture result to a PNG (no PIL - stdlib only).

Parses a textured vase G-code, reconstructs the displaced wall outline per
Z-slice, and draws a top-down (XY) + a Z-height profile (side) image so the
actual horizontal banding is visible. Shows what the tool REALLY wrote.
"""
import math
import re
import sys
import os
import zlib
import struct


def parse(src):
    moves = []
    x = y = z = 0.0
    e = 0.0
    emode = True
    cur_z = 0.0
    xre = re.compile(r'X([-\d.]+)')
    yre = re.compile(r'Y([-\d.]+)')
    zre = re.compile(r'Z([-\d.]+)')
    ere = re.compile(r'E([-\d.]+)')
    for ln in open(src, errors='replace'):
        s = ln.strip()
        if s.startswith(';'):
            m = re.search(r'Z:([-\d.]+)', s)
            if m:
                cur_z = float(m.group(1))
            continue
        if s.startswith('M82'):
            emode = True
            continue
        if s.startswith('M83'):
            emode = False
            continue
        if s.startswith('G0') or s.startswith('G1'):
            nx, ny, nz, ne = x, y, z, e
            m = xre.search(s)
            if m:
                nx = float(m.group(1))
            m = yre.search(s)
            if m:
                ny = float(m.group(1))
            m = zre.search(s)
            if m:
                nz = float(m.group(1))
                cur_z = nz
            m = ere.search(s)
            if m:
                ne = float(m.group(1))
            ext = s.startswith('G1') and m is not None and ne != e
            if emode and ext:
                moves.append((cur_z, x, y, nx, ny))
            elif (not emode) and ext and ne > e:
                moves.append((cur_z, x, y, nx, ny))
            x, y, z, e = nx, ny, nz, ne
    return moves


def write_png(path, w, h, pixels):
    raw = bytearray()
    for row in pixels:
        raw.append(0)
        for (r, g, b) in row:
            raw.append(r)
            raw.append(g)
            raw.append(b)
    comp = zlib.compress(bytes(raw), 9)

    def chunk(typ, data):
        c = struct.pack('>I', len(data)) + typ + data
        c += struct.pack('>I', zlib.crc32(typ + data) & 0xffffffff)
        return c

    sig = b'\x89PNG\r\n\x1a\n'
    ihdr = struct.pack('>IIBBBBB', w, h, 8, 2, 0, 0, 0)
    png = sig + chunk(b'IHDR', ihdr) + chunk(b'IDAT', comp) + chunk(b'IEND', b'')
    open(path, 'wb').write(png)


def main(src, out):
    moves = parse(src)
    print('extruding moves:', len(moves))
    if not moves:
        return
    zs = [m[0] for m in moves]
    zmin, zmax = min(zs), max(zs)
    xs = [m[1] for m in moves] + [m[3] for m in moves]
    ys = [m[2] for m in moves] + [m[4] for m in moves]
    xmin, xmax = min(xs), max(xs)
    ymin, ymax = min(ys), max(ys)
    print('Z %.2f..%.2f  XY %.1f..%.1f x %.1f..%.1f'
          % (zmin, zmax, xmin, xmax, ymin, ymax))
    W, H = 1200, 760
    bg = (255, 255, 255)
    canvas = [[bg] * W for _ in range(H)]

    def plot(ix, iy, col):
        ix = int(round(ix))
        iy = int(round(iy))
        if 0 <= ix < W and 0 <= iy < H:
            canvas[iy][ix] = col

    # side profile: radial displacement vs Z
    nbands = 140
    band = (zmax - zmin) / nbands
    prof = []
    for i in range(nbands):
        za = zmin + i * band
        zb = za + band
        rad = []
        for (z, x0, y0, x1, y1) in moves:
            if za <= z < zb or (i == nbands - 1 and z >= za):
                rad.append(math.hypot((x0 + x1) / 2.0, (y0 + y1) / 2.0))
        if rad:
            prof.append((za, sum(rad) / len(rad)))
        else:
            prof.append((za, None))
    px0, py0, px1, py1 = 70, 60, W - 70, H - 180
    for ix in range(px0, px1 + 1):
        plot(ix, py0, (0, 0, 0))
        plot(ix, py1, (0, 0, 0))
    for iy in range(py0, py1 + 1):
        plot(px0, iy, (0, 0, 0))
        plot(px1, iy, (0, 0, 0))
    valid = [(z, r) for (z, r) in prof if r is not None]
    if valid:
        rmin = min(r for _, r in valid)
        rmax = max(r for _, r in valid)
        pts = []
        for (z, r) in valid:
            ix = px0 + (z - zmin) / (zmax - zmin) * (px1 - px0)
            iy = py1 - (r - rmin) / (rmax - rmin + 1e-9) * (py1 - py0)
            for yy in range(int(iy), py1 + 1):
                plot(int(ix), yy, (200, 40, 40))
            pts.append((ix, iy))
        for a, b in zip(pts, pts[1:]):
            n = max(2, int(math.hypot(b[0] - a[0], b[1] - a[1])))
            for t in range(n + 1):
                plot(a[0] + (b[0] - a[0]) * t / n,
                     a[1] + (b[1] - a[1]) * t / n, (0, 0, 0))

    # top-down XY
    tx0, ty0, tx1, ty1 = 70, H - 150, 420, H - 70
    for ix in range(tx0, tx1 + 1):
        plot(ix, ty0, (0, 0, 0))
        plot(ix, ty1, (0, 0, 0))
    for iy in range(ty0, ty1 + 1):
        plot(tx0, iy, (0, 0, 0))
        plot(tx1, iy, (0, 0, 0))
    for (z, x0, y0, x1, y1) in moves:
        ix0 = tx0 + (x0 - xmin) / (xmax - xmin + 1e-9) * (tx1 - tx0)
        iy0 = ty0 + (y0 - ymin) / (ymax - ymin + 1e-9) * (ty1 - ty0)
        ix1 = tx0 + (x1 - xmin) / (xmax - xmin + 1e-9) * (tx1 - tx0)
        iy1 = ty0 + (y1 - ymin) / (ymax - ymin + 1e-9) * (ty1 - ty0)
        n = max(2, int(math.hypot(ix1 - ix0, iy1 - iy0)))
        for t in range(n + 1):
            plot(ix0 + (ix1 - ix0) * t / n,
                 iy0 + (iy1 - iy0) * t / n, (60, 90, 180))

    write_png(out, W, H, canvas)
    print('rendered:', out)


if __name__ == '__main__':
    main(sys.argv[1], sys.argv[2])
