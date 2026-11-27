#!/usr/bin/env python3
"""R287: render a VISUAL PREVIEW image for generated/modified G-code.

The user works blind at the LCD - a rendered picture next to the G-code lets
him SEE what a generator or post-processor produced before he prints it. The
preview is written as a FILE with a .gcode extension (so Clipper/Mainsail
lists and downloads it like any other file) carrying the tag 'PIC' in its
name. The r2-postproc watcher skips every file whose name contains '_PIC'
(see the R287 PIC skip in r2_postproc.py), so the preview is never processed,
tagged or counted as a print file.

NAMING (user rule):
  - keep the version prefix and the name up to the start of the tags
  - push all other tags to the back
  - append '_PIC' in UPPERCASE directly after the filename (before .gcode)

  Example:
    V03_ShapeCyl8s_L112-320_TX.gcode   ->  V03_ShapeCyl8s_PIC.gcode
    V05_Vase_S100_TWR-30_TX.gcode      ->  V05_Vase_S100_PIC.gcode

  The renderer STRIPS the tool-chain tags (_TX, _TWR-*, _S*, _L*-*, ...) for
  the PIC name, keeping only the version prefix + the leading name token.

CLEANUP:
  When the source G-code is renamed, the old PIC is stale. When the source
  is deleted, the PIC must go too. `--cleanup DIR` scans a directory (or a
  generator subfolder) and removes every *_PIC.gcode whose source no longer
  exists. Call it from the watcher or run it manually after a rename.

USAGE:
  python3 tools/r287_pic_render.py FILE.gcode                # render preview
  python3 tools/r287_pic_render.py FILE.gcode --out DIR      # explicit dir
  python3 tools/r287_pic_render.py --cleanup DIR             # stale PICs
  python3 tools/r287_pic_render.py --cleanup DIR --recursive

PURE STDLIB (no PIL) - the Pi Zero 2 W has no image libs and PEP 668 blocks
pip installs. The PNG writer is the same approach as r287_banding_render.py.
"""
import math
import os
import re
import sys
import zlib
import struct

PIC_TAG = '_PIC'
# tags the renderer strips from the PIC name (tool-chain suffixes). The
# version prefix 'Vnn_' and the first real name token are KEPT.
_STRIP_TAGS = re.compile(
    r'(_TX|_TWR-[-0-9.]+|_S[-0-9.]+|_L[0-9]+-[0-9]+|_ROT[-0-9.]+'
    r'|_SC[-0-9.]+|_MAP[-0-9.]+|_BLUR[-0-9.]+|_FUZZY|_BUMP[-0-9.]+'
    r'|_TWIST[-0-9.]+|_SCALE[-0-9.]+|_TX[-0-9.]+)$', re.IGNORECASE)


def pic_name(src_name):
    """-> preview file name for a source G-code name.

    Keeps 'Vnn_' prefix + the leading name token(s) up to the first tool
    tag; pushes the tags to the back is not needed - they are DROPPED, and
    '_PIC' is appended before the .gcode extension.
    """
    base = os.path.basename(src_name)
    if base.lower().endswith('.gcode'):
        stem = base[:-6]
    else:
        stem = base
    # strip one trailing tool tag at a time (there may be several)
    changed = True
    while changed:
        changed = False
        m = _STRIP_TAGS.search(stem)
        if m and m.start() > 0:
            stem = stem[:m.start()]
            changed = True
    # also drop a trailing '_TX' / '_TX-*' that the regex may have missed
    stem = re.sub(r'_TX(?:-[-0-9.]+)?$', '', stem, flags=re.IGNORECASE)
    return stem + PIC_TAG + '.gcode'


# ----------------------------------------------------------------------
# minimal PNG writer (stdlib only)
# ----------------------------------------------------------------------
def _png_chunk(tag, data):
    c = tag + data
    return struct.pack('>I', len(data)) + c + struct.pack('>I', zlib.crc32(c) & 0xffffffff)


def write_png(path, w, h, pixels):
    """pixels: list of rows, each row a list of (r,g,b) tuples."""
    raw = bytearray()
    for y in range(h):
        raw.append(0)  # filter type 0 (none)
        for x in range(w):
            r, g, b = pixels[y][x]
            raw += bytes((r & 255, g & 255, b & 255))
    comp = zlib.compress(bytes(raw), 6)
    sig = b'\x89PNG\r\n\x1a\n'
    ihdr = struct.pack('>IIBBBBB', w, h, 8, 2, 0, 0, 0)
    with open(path, 'wb') as f:
        f.write(sig)
        f.write(_png_chunk(b'IHDR', ihdr))
        f.write(_png_chunk(b'IDAT', comp))
        f.write(_png_chunk(b'IEND', b''))


# ----------------------------------------------------------------------
# G-code parse + render (side profile + top-down, like r287_banding_render)
# ----------------------------------------------------------------------
_XR = re.compile(r'X([-\d.]+)')
_YR = re.compile(r'Y([-\d.]+)')
_ZR = re.compile(r'Z([-\d.]+)')
_ZC = re.compile(r'Z:([-\d.]+)')


def parse(src):
    """-> list of (z, x0, y0, x1, y1) extruding segments."""
    moves = []
    x = y = z = 0.0
    e = 0.0
    emode = True
    cur_z = 0.0
    for ln in open(src, errors='replace'):
        s = ln.strip()
        if s.startswith(';'):
            m = _ZC.search(s)
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
            nx, ny, nz = x, y, z
            mx = _XR.search(s)
            if mx:
                nx = float(mx.group(1))
            my = _YR.search(s)
            if my:
                ny = float(my.group(1))
            mz = _ZR.search(s)
            if mz:
                nz = float(mz.group(1))
                cur_z = nz
            me = re.search(r'E([-\d.]+)', s)
            ext = bool(me) and (emode or (float(me.group(1)) > e))
            if ext:
                moves.append((cur_z, x, y, nx, ny))
            x, y, z = nx, ny, nz
            if me:
                e = float(me.group(1))
    return moves


def render(src, out):
    moves = parse(src)
    if not moves:
        print('[pic] %s: no extruding moves - nothing to render' %
              os.path.basename(src))
        return False
    zs = [m[0] for m in moves]
    zmin, zmax = min(zs), max(zs)
    xs = [v for m in moves for v in (m[1], m[3])]
    ys = [v for m in moves for v in (m[2], m[4])]
    xmin, xmax = min(xs), max(xs)
    ymin, ymax = min(ys), max(ys)

    W, H = 900, 700
    M = 40
    # --- top-down (XY) on the upper 60%, side (Z-X) on the lower 40% ---
    td_h = int(H * 0.60)
    side_h = H - td_h

    pixels = [[(245, 245, 248) for _ in range(W)] for _ in range(H)]

    def plot(px, py, col):
        ix = int(round(px))
        iy = int(round(py))
        if 0 <= ix < W and 0 <= iy < H:
            pixels[iy][ix] = col

    # top-down XY
    tx0, tx1 = M, W - M
    ty0, ty1 = M, td_h - M
    # axes
    for ix in range(tx0, tx1 + 1, 40):
        plot(ix, ty0, (200, 200, 210))
        plot(ix, ty1, (200, 200, 210))
    for iy in range(ty0, ty1 + 1, 40):
        plot(tx0, iy, (200, 200, 210))
        plot(tx1, iy, (200, 200, 210))
    for (z, x0, y0, x1, y1) in moves:
        ix0 = tx0 + (x0 - xmin) / (xmax - xmin + 1e-9) * (tx1 - tx0)
        iy0 = ty0 + (y0 - ymin) / (ymax - ymin + 1e-9) * (ty1 - ty0)
        ix1 = tx0 + (x1 - xmin) / (xmax - xmin + 1e-9) * (tx1 - tx0)
        iy1 = ty0 + (y1 - ymin) / (ymax - ymin + 1e-9) * (ty1 - ty0)
        n = max(2, int(math.hypot(ix1 - ix0, iy1 - iy0)))
        for t in range(n + 1):
            plot(ix0 + (ix1 - ix0) * t / n,
                 iy0 + (iy1 - iy0) * t / n, (70, 110, 190))

    # side profile Z (vertical) vs X (horizontal)
    sx0, sx1 = M, W - M
    sy0, sy1 = td_h + M, H - M
    for ix in range(sx0, sx1 + 1, 40):
        plot(ix, sy0, (200, 200, 210))
        plot(ix, sy1, (200, 200, 210))
    for iy in range(sy0, sy1 + 1, 40):
        plot(sx0, iy, (200, 200, 210))
        plot(sx1, iy, (200, 200, 210))
    for (z, x0, y0, x1, y1) in moves:
        ix0 = sx0 + (x0 - xmin) / (xmax - xmin + 1e-9) * (sx1 - sx0)
        ix1 = sx0 + (x1 - xmin) / (xmax - xmin + 1e-9) * (sx1 - sx0)
        # z maps top=zmax, bottom=zmin
        iz0 = sy1 - (z - zmin) / (zmax - zmin + 1e-9) * (sy1 - sy0)
        n = max(2, int(math.hypot(ix1 - ix0, iz0 - iz0)))
        # draw vertical line at this x from zmin to z (the wall)
        for t in range(n + 1):
            ix = ix0 + (ix1 - ix0) * t / n
            plot(ix, sy1, (60, 90, 180))
            plot(ix, int(iz0), (60, 90, 180))

    write_png(out, W, H, pixels)
    print('[pic] rendered: %s  (%d moves, Z %.2f..%.2f, XY %.1f..%.1f x %.1f..%.1f)'
          % (os.path.basename(out), len(moves), zmin, zmax,
             xmin, xmax, ymin, ymax))
    return True


def cleanup(directory, recursive=False):
    """Remove *_PIC.gcode files whose source no longer exists."""
    removed = 0
    targets = [directory]
    if recursive:
        for dp, dns, fns in os.walk(directory):
            targets.append(dp)
    seen = set()
    for d in targets:
        if d in seen or not os.path.isdir(d):
            continue
        seen.add(d)
        for fn in sorted(os.listdir(d)):
            if not fn.endswith('.gcode') or PIC_TAG not in fn.upper():
                continue
            pic_path = os.path.join(d, fn)
            # derive the source name (strip _PIC)
            src_name = fn.replace(PIC_TAG, '', 1)
            # the source may carry a different tag set; try the exact name
            # and the stripped-name variants
            candidates = [src_name,
                          os.path.splitext(src_name)[0] + '.gcode']
            found = False
            for c in candidates:
                if os.path.isfile(os.path.join(d, c)):
                    found = True
                    break
            if not found:
                # also try: the PIC name without _PIC might not be the exact
                # source (tags differ). If NO .gcode without _PIC shares the
                # stem, treat the PIC as stale.
                stem = os.path.splitext(fn)[0].replace(PIC_TAG, '')
                siblings = [f for f in os.listdir(d)
                            if f.endswith('.gcode') and PIC_TAG not in f.upper()
                            and os.path.splitext(f)[0].startswith(stem[:20])]
                if siblings:
                    continue
                try:
                    os.remove(pic_path)
                    removed += 1
                    print('[pic] removed stale preview: %s' % fn)
                except OSError as e:
                    print('[pic] could not remove %s: %s' % (fn, e))
    print('[pic] cleanup: %d stale preview(s) removed' % removed)
    return removed


def main(argv):
    if not argv:
        print(__doc__)
        return 1
    if argv[0] == '--cleanup':
        if len(argv) < 2:
            print('usage: r287_pic_render.py --cleanup DIR [--recursive]')
            return 1
        recursive = '--recursive' in argv
        return 0 if cleanup(argv[1], recursive) is not None else 1
    src = argv[0]
    if not os.path.isfile(src):
        print('[pic] source not found: %s' % src)
        return 1
    out_dir = None
    for i, a in enumerate(argv):
        if a == '--out' and i + 1 < len(argv):
            out_dir = argv[i + 1]
    if out_dir is None:
        out_dir = os.path.dirname(os.path.abspath(src))
    out = os.path.join(out_dir, pic_name(os.path.basename(src)))
    ok = render(src, out)
    # also clean up stale PICs in the same dir (source may have been renamed)
    cleanup(out_dir, recursive=False)
    return 0 if ok else 1


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
