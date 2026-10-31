#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""R212 (.136k): Mainsail metadata for GENERATED files.

Field log .136j: freshly generated G-code shows NO metadata in Mainsail's
file explorer - no thumbnail, no print time, no filament - unlike the
slicer's own files. Mainsail reads those from plain G-code comments
(PrusaSlicer/Orca dialect):

    ; thumbnail begin 128x128
    ; <base64 PNG, wrapped at 76 chars>
    ; thumbnail end
    ; estimated printing time (normal mode) = 1h 2m 3s
    ; filament used [mm] = 1234.5mm

This module computes them FROM THE FILE ITSELF (so a range excerpt gets
its OWN honest time, not the source's), renders a top-view thumbnail from
the extrusion moves, and - for files DERIVED from a slicer file (range
excerpt, texture variant, optimized copy) - copies the SOURCE's thumbnail
verbatim so the explorer keeps the visual identity the user expects.

Design rules:
  - idempotent: our own block is marked 'R2-META' and REPLACED, never
    duplicated (a re-finalize must not grow the file)
  - slicer files keep THEIR metadata: if the file already carries a
    thumbnail that is not ours, we do not touch it at all
  - never raises at the caller - finalize() returns a status string
  - cheap: one streaming pass, no full-file DOM
"""
import base64
import math
import os
import re
import struct
import zlib

THUMB_SIZE = 128
MARK_OURS = '; R2-META v1'


# ----------------------------------------------------------------- analyze --
def analyze(path, max_moves=4_000_000):
    """One streaming pass: (time_s, filament_mm, segments, zmin, zmax).

    segments = [(x0, y0, x1, y1, z), ...] for EXTRUDING moves only (the
    thumbnail draws those). Time = sum(dist/speed) - no accel model, an
    estimate like every slicer's. Stops after max_moves G1 lines (a
    pathological file must not hang the watcher)."""
    t = 0.0
    fil = 0.0
    segs = []
    x = y = z = e = 0.0
    fx = fy = None
    feed = 1200.0            # mm/min default if the file never sets F
    abs_xyz = abs_e = True
    zmin = zmax = None
    n = 0
    with open(path, 'r', errors='replace') as f:
        for line in f:
            if line.startswith((';', '(', '#', '\n', '\r')):
                continue
            parts = line.split()
            if not parts:
                continue
            g = parts[0].upper()
            if g == 'G90':
                abs_xyz = abs_e = True
                continue
            if g == 'G91':
                abs_xyz = abs_e = False
                continue
            if g == 'M82':
                abs_e = True
                continue
            if g == 'M83':
                abs_e = False
                continue
            if g == 'G92':
                for p in parts[1:]:
                    if p[:1].upper() == 'E':
                        try:
                            e = float(p[1:])
                        except ValueError:
                            pass
                continue
            if g not in ('G0', 'G1', 'G00', 'G01'):
                continue
            n += 1
            if n > max_moves:
                break
            nx = ny = nz = ne = None
            for p in parts[1:]:
                c = p[:1].upper()
                try:
                    v = float(p[1:])
                except (ValueError, IndexError):
                    continue
                if c == 'X':
                    nx = v
                elif c == 'Y':
                    ny = v
                elif c == 'Z':
                    nz = v
                elif c == 'E':
                    ne = v
                elif c == 'F':
                    if v > 0:
                        feed = v
            x2 = (nx if (nx is not None and abs_xyz)
                  else (x + (nx or 0.0)))
            y2 = (ny if (ny is not None and abs_xyz)
                  else (y + (ny or 0.0)))
            z2 = (nz if (nz is not None and abs_xyz)
                  else (z + (nz or 0.0)))
            e2 = (ne if (ne is not None and abs_e)
                  else (e + (ne or 0.0)))
            dist = math.hypot(x2 - x, y2 - y)
            if z2 != z and abs(z2 - z) > 1e-9:
                dist = max(dist, abs(z2 - z))
            if dist > 1e-9 and feed > 0:
                t += dist / (feed / 60.0)
            de = e2 - e
            if de > 0 and dist > 1e-9:
                fil += de
                if fx is not None:
                    segs.append((fx, fy, x2, y2, z2))
                    if zmin is None or z2 < zmin:
                        zmin = z2
                    if zmax is None or z2 > zmax:
                        zmax = z2
            if nx is not None or ny is not None or dist > 1e-9 or True:
                fx, fy = x2, y2
            x, y, z, e = x2, y2, z2, e2
    return t, fil, segs, zmin, zmax


# -------------------------------------------------------------- thumbnail --
def _png_chunk(tag, data):
    return (struct.pack('>I', len(data)) + tag + data
            + struct.pack('>I', zlib.crc32(tag + data) & 0xffffffff))


def render_png(segs, size=THUMB_SIZE):
    """Top-view raster of the extrusion moves, colored by height
    (blue = first layers, green/yellow = top). Pure stdlib."""
    if not segs:
        return None
    xs = [c for s in segs for c in (s[0], s[2])]
    ys = [c for s in segs for c in (s[1], s[3])]
    x0, x1 = min(xs), max(xs)
    y0, y1 = min(ys), max(ys)
    w = max(x1 - x0, 1e-9)
    h = max(y1 - y0, 1e-9)
    m = 6.0
    sc = (size - 2 * m) / max(w, h)
    zlo = min(s[4] for s in segs)
    zhi = max(s[4] for s in segs)
    zspan = max(zhi - zlo, 1e-9)
    px = [[None] * size for _ in range(size)]

    def plot(xi, yi, zf):
        if 0 <= xi < size and 0 <= yi < size:
            # heat: 0 -> dark blue, 0.5 -> green, 1 -> yellow
            t = min(1.0, max(0.0, (zf - zlo) / zspan))
            if t < 0.5:
                k = t / 0.5
                r, g, b = int(20 + 40 * k), int(60 + 140 * k), int(160 + 60 * k)
            else:
                k = (t - 0.5) / 0.5
                r, g, b = int(60 + 190 * k), int(200 - 40 * k), int(220 - 160 * k)
            px[yi][xi] = (r, g, b)

    for (ax, ay, bx, by, zf) in segs:
        xia = int(m + (ax - x0) * sc)
        yia = int(m + (ay - y0) * sc)
        xib = int(m + (bx - x0) * sc)
        yib = int(m + (by - y0) * sc)
        n = max(abs(xib - xia), abs(yib - yia), 1)
        for k in range(n + 1):
            plot(xia + (xib - xia) * k // n, yia + (yib - yia) * k // n, zf)
    rows = bytearray()
    for yi in range(size - 1, -1, -1):          # flip Y: bed view
        rows.append(0)
        for xi in range(size):
            c = px[yi][xi] or (11, 18, 32)      # page background
            rows.extend(c)
    ihdr = struct.pack('>IIBBBBB', size, size, 8, 2, 0, 0, 0)
    return (b'\x89PNG\r\n\x1a\n'
            + _png_chunk(b'IHDR', ihdr)
            + _png_chunk(b'IDAT', zlib.compress(bytes(rows), 6))
            + _png_chunk(b'IEND', b''))


# ------------------------------------------------------------- meta block --
def _fmt_time(t):
    t = int(round(max(0.0, t)))
    h, rem = divmod(t, 3600)
    m, s = divmod(rem, 60)
    return '%dh %dm %ds' % (h, m, s)


def _thumb_block(png):
    b64 = base64.b64encode(png).decode('ascii')
    lines = ['; thumbnail begin %dx%d' % (THUMB_SIZE, THUMB_SIZE)]
    for i in range(0, len(b64), 76):
        lines.append('; ' + b64[i:i + 76])
    lines.append('; thumbnail end')
    return lines


def _has_foreign_thumbnail(head):
    return ('; thumbnail begin' in head and MARK_OURS not in head)


def _read_head(path, nbytes=8192):
    with open(path, 'rb') as f:
        return f.read(nbytes).decode('utf-8', 'replace')


def _src_thumb_lines(src):
    """The source file's LAST (largest) thumbnail block, verbatim."""
    try:
        txt = open(src, 'r', errors='replace').read()
    except OSError:
        return None
    blocks = []
    cur = None
    for line in txt.split('\n'):
        if line.startswith('; thumbnail begin'):
            cur = [line]
        elif cur is not None:
            cur.append(line)
            if line.startswith('; thumbnail end'):
                blocks.append(cur)
                cur = None
    if not blocks:
        return None
    best = max(blocks, key=lambda b: len(b))
    return best


def finalize(path, src=None):
    """Add/refresh OUR metadata block. Returns a status string:
    'meta' (written), 'same' (signature matched - NOTHING written),
    'own' (slicer metadata kept), 'skip' (nothing).

    R215 (.136l field log): the watcher scan calls this for every
    generated file on EVERY pass - and it used to re-analyze the whole
    file (thumbnail render!) and REWRITE it even when nothing changed.
    On the field Pi that meant: mtimes of ~30 files bumped every few
    seconds (the gen-files list flip-flopped endlessly), the SD card
    kept being written and the host sat at load 2+ 'idle' - a direct
    'Timer too close' contributor. The block now ends in a signature
    line: md5 over the file BODY (everything outside our block). Same
    signature -> return 'same' after one read, zero writes. Any real
    change (a fix rewrote the file) changes the body -> one refresh."""
    path = os.path.abspath(path)
    if not os.path.isfile(path):
        return 'missing'
    head = _read_head(path)
    if _has_foreign_thumbnail(head):
        return 'own'                      # slicer file: hands off
    import hashlib as _hl215
    with open(path, 'r', errors='replace') as f:
        raw = f.read()
    _body215 = raw
    if MARK_OURS in raw:
        _i215 = raw.index(MARK_OURS)
        _k215 = raw.find('\n; R2-META sig =', _i215)
        if _k215 < 0:
            _j215 = raw.find('\n',
                             raw.index('; filament used [mm] =', _i215))
        else:
            _j215 = raw.find('\n', _k215 + 1)
            if _j215 < 0:
                _j215 = len(raw) - 1
        _body215 = raw[:_i215] + raw[_j215 + 1:]
    _sig215 = _hl215.md5(
        _body215.encode('utf-8', 'replace')).hexdigest()[:16]
    _m215 = re.search(r'^; R2-META sig = ([0-9a-f]+)', raw, re.M)
    if _m215 and _m215.group(1) == _sig215:
        return 'same'
    t, fil, segs, _, _ = analyze(path)
    if not segs:
        return 'skip'                     # nothing printable to show
    lines = None
    if src:
        lines = _src_thumb_lines(src)
    if lines is None:
        png = render_png(segs)
        if png is None:
            return 'skip'
        lines = _thumb_block(png)
    block = ([MARK_OURS,
              '; generated by R2-D2 (klipper-e3-r2d2) - meta from its '
              'own moves'] + lines
             + ['; estimated printing time (normal mode) = ' + _fmt_time(t),
                '; filament used [mm] = %.1fmm' % fil])
    # raw was read above (R215) - strip a previous block of ours
    # (marker .. sig line; pre-sig blocks end at the filament line)
    if MARK_OURS in raw:
        i = raw.index(MARK_OURS)
        k = raw.find('\n; R2-META sig =', i)
        if k < 0:
            j = raw.find('\n', raw.index('; filament used [mm] =', i))
        else:
            j = raw.find('\n', k + 1)
            if j < 0:
                j = len(raw) - 1
        raw = raw[:i] + raw[j + 1:]
    out = raw.split('\n')
    insert_at = 1 if out and out[0].startswith('; R2-GEN') else 0
    out[insert_at:insert_at] = block + ['; R2-META sig = ' + _sig215]
    with open(path, 'w', encoding='utf-8') as f:
        f.write('\n'.join(out))
    return 'meta'


if __name__ == '__main__':
    import sys
    for p in sys.argv[1:]:
        print('%s: %s' % (p, finalize(p)))
