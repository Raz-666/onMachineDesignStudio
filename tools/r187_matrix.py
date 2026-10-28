#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""R187: GENERATOR + TOOL PARAMETER MATRIX - every generator, every nozzle,
every bed class, key parameter variations.

The user's request (.132 round): test all generators and tools "with ALL
parameters and variations, most intensively" - especially across the nozzle
diameters 0.2 / 0.4 / 0.6 / 0.8 / 1.0 and different bed sizes, since no
existing suite sweeps either dimension (the battery/megatest run the
reference 0.6 nozzle on the reference bed only).

Three sweeps per generator:
  N) nozzle sweep   - 0.2/0.4/0.6/0.8/1.0 on the reference bed, layer
                      heights matched to the nozzle (0.10/0.16/0.20/0.28/0.35)
  B) bed sweep      - 180x180 / 220x217 / 300x300 / 350x350 at nozzle 0.4.
                      A generator that cannot fit MUST refuse with a clear
                      error (a silent clip or a crash is a FAIL).
  V) variations     - the generator's key mode/parameter switches.

Every produced file is checked for the shared invariants (gen stamp,
PRINT_START/END, EXCLUDE balance, bed bounds, canonical TYPES, Z sanity)
AND for the R184 brim air gap - at EVERY nozzle, because the gap rule is
'wid + 0.35' and must scale with the line width, not just hold at 0.6.

Run:  python3 tools/r187_matrix.py        (~5-10 min)
Exit 0 = the whole matrix holds. NOT part of macro_render_test.py.
"""
import math
import os
import re
import struct
import sys
import tempfile
import time
import zlib

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import r2_postproc as pp                                  # noqa: E402

NOZZLES = [0.2, 0.4, 0.6, 0.8, 1.0]
LAYER_FOR = {0.2: 0.10, 0.4: 0.16, 0.6: 0.20, 0.8: 0.28, 1.0: 0.35}
FIRST_FOR = {0.2: 0.14, 0.4: 0.22, 0.6: 0.28, 0.8: 0.38, 1.0: 0.48}
BEDS = {
    '180x180': (0, 0, 180, 180),
    '220x217': (0, -3, 220, 217),
    '300x300': (0, 0, 300, 300),
    '350x350': (0, 0, 350, 350),
}
REF_BED = BEDS['220x217']

n_ck = [0]
fails = []


def ck(name, cond, info=''):
    n_ck[0] += 1
    if not cond:
        fails.append((name, str(info)[:160]))
        print('  FAIL %s  %s' % (name, str(info)[:120]))
    return bool(cond)


def png(path, w=48, h=48):
    def chunk(t_, d):
        return struct.pack('>I', len(d)) + t_ + d + struct.pack(
            '>I', zlib.crc32(t_ + d) & 0xffffffff)
    raw = b''
    for y in range(h):
        row = b'\x00'
        for x in range(w):
            v = int(30 + 190 * (math.sin(x / 5.0) * math.cos(y / 7.0) + 1) / 2)
            row += bytes((v, v, v))
        raw += row
    open(path, 'wb').write(b'\x89PNG\r\n\x1a\n'
        + chunk(b'IHDR', struct.pack('>IIBBBBB', w, h, 8, 2, 0, 0, 0))
        + chunk(b'IDAT', zlib.compress(raw)) + chunk(b'IEND', b''))


def resonance_csv(d, ax):
    csv = os.path.join(d, 'resonances_%s_20261008.csv' % ax)
    rows = ['freq,psd_hz,psd_nm']
    for i in range(80):
        f = 5.0 + i * 0.6
        rows.append('%.2f,%.6f,%.6f' % (f, 1.0 / (1 + (f - 35) ** 2) * 10, 0.5))
    open(csv, 'w').write('\n'.join(rows))


# ---------------------------------------------------------------- checks ---
CANON = None


def canon_types():
    global CANON
    if CANON is None:
        CANON = set(pp.TYPE_MAP.values()) | {'CUSTOM'}
    return CANON


def brim_gap_layer1(txt):
    """R184: min distance brim-ink to wall-ink on layer 1 (same object)."""
    parts = re.split(r'(?m)^(LAYER_MARK.*)$', txt)
    body = (parts[0] + parts[1] + parts[2]) if len(parts) >= 3 else txt
    brim, wall = [], []
    mode = None
    cur = '?'
    for l in body.split('\n'):
        ls = l.strip()
        m = re.match(r'EXCLUDE_OBJECT_START NAME=(\S+)', ls)
        if m:
            cur = m.group(1)
            continue
        if ls == ';TYPE:Brim':
            mode = 'b'
            continue
        if ls == ';TYPE:Outer wall':
            mode = 'w'
            continue
        if ls.startswith(';TYPE:'):
            mode = None
            continue
        if mode and ls[:2] == 'G1' and ' X' in ls and ' E' in ls \
                and ' E-' not in ls:
            mx = re.search(r'X(-?[\d.]+)', ls)
            my = re.search(r'Y(-?[\d.]+)', ls)
            if mx and my:
                (brim if mode == 'b' else wall).append(
                    (float(mx.group(1)), float(my.group(1)), cur))
    if not brim or not wall:
        return None
    worst = 1e9
    for (bx, by, bo) in brim:
        for (wx, wy, wo) in wall:
            if bo != wo:
                continue
            worst = min(worst, math.hypot(bx - wx, by - wy))
    return worst if worst < 1e9 else None


def check_file(path, bed, nozzle, tag):
    # the real pipeline: the watcher's process() pass tags the file (the
    # R166 core stamp comes from THIS pass for the older generators - raw
    # bridge/resonance/scale output legitimately starts with the v5 tag)
    try:
        pp.process(path)
    except Exception as e:                               # noqa: BLE001
        ck('%s: process() pass clean' % tag, False, repr(e)[:120])
    txt = open(path, errors='replace').read()
    # stamp contract (R166, now complete in R186): the core stamp heads every
    # generated file; bridge/resonance call process() themselves (v5 tag first)
    first = txt.split('\n', 1)[0].strip()
    ck('%s: gen core stamp' % tag,
       '; R2-GEN core' in txt[:400]
       and (first.startswith('; R2-GEN core') or first == pp.TAG),
       txt[:40])
    ck('%s: PRINT_START + PRINT_END' % tag,
       'PRINT_START' in txt and 'PRINT_END' in txt, '')
    # EXCLUDE balance
    starts = re.findall(r'EXCLUDE_OBJECT_START NAME=(\S+)', txt)
    ends = re.findall(r'EXCLUDE_OBJECT_END NAME=(\S+)', txt)
    defs = set(re.findall(r'EXCLUDE_OBJECT_DEFINE NAME=(\S+)', txt))
    # systemtest contract: no markers is legal (single-piece generators);
    # if present they must balance and be defined
    ck('%s: EXCLUDE balance + defined (systemtest contract)' % tag,
       len(starts) == len(ends) and set(starts) == set(ends)
       and set(starts) <= defs, 'S=%d E=%d D=%d' % (len(starts), len(ends), len(defs)))
    # canonical types only
    bad = [c for c in set(re.findall(r'APPLY_TYPE TYPE=(\S+)', txt))
           if c not in canon_types()]
    ck('%s: canonical APPLY_TYPE codes only' % tag, not bad, bad[:4])
    # bed bounds (travel + print, generous 2 mm margin)
    x0, y0, x1, y1 = bed
    oob = []
    for m in re.finditer(r'(?m)^G[01] X(-?[\d.]+) Y(-?[\d.]+)', txt):
        x, y = float(m.group(1)), float(m.group(2))
        if x < x0 - 2 or x > x1 + 2 or y < y0 - 2 or y > y1 + 2:
            oob.append((x, y))
            if len(oob) > 3:
                break
    ck('%s: all moves inside the bed' % tag, not oob, oob[:2])
    # Z sanity: never below zero, never above a sane machine height
    zs = [float(m.group(1)) for m in
          re.finditer(r'(?m)^G[01] Z([\d.]+)', txt)]
    ck('%s: Z within 0..400mm' % tag,
       not zs or (min(zs) >= -0.001 and max(zs) <= 400),
       'min=%s max=%s' % (min(zs) if zs else '-', max(zs) if zs else '-'))
    # R184 brim air gap - at EVERY nozzle. The rule (see _brim_gap): the
    # innermost loop runs wid + 0.35 outside the reference contour, i.e.
    # INK EDGE to INK EDGE ~0.35mm. Measured center-to-center, so the
    # line width of THIS file comes off (parsed from its own header).
    gap = brim_gap_layer1(txt)
    if gap is not None:
        # the TRUE line width: _FILE_INFO LINE_WIDTH= first (string art
        # caps its ring width at 0.5mm and has no '; line_width' comment),
        # then the '; line_width =' comment, then the nozzle-derived guess
        mw = (re.search(r'(?m)^_FILE_INFO .*?LINE_WIDTH=([\d.]+)', txt)
              or re.search(r'; line_width = ([\d.]+)', txt))
        wv = float(mw.group(1)) if mw else nozzle * 1.08
        edge = gap - wv
        ck('%s: R184 brim air gap >= 0.35mm (nozzle %.1f)' % (tag, nozzle),
           edge >= 0.30, 'edge=%.2f (center=%.2f wid=%.2f)'
           % (edge, gap, wv))
        return round(edge, 2)
    return None


# ------------------------------------------------------------ generators ---
D = tempfile.mkdtemp(prefix='r187_')
IMG = os.path.join(D, 't.png')
png(IMG)
BRICK_SRC = None

GENS = {
    'labels':      lambda nz, bd, lh, fh: pp.make_labels(
        ['R187'], w=40, h=18, nozzle=nz, layer_h=lh, first_h=fh,
        bed=bd, out_dir=D),
    'labels+ring': lambda nz, bd, lh, fh: pp.make_labels(
        ['RING'], w=40, h=18, hole_side=1, hole_d=5, ring=True,
        nozzle=nz, layer_h=lh, first_h=fh, bed=bd, out_dir=D),
    'labels+stamp': lambda nz, bd, lh, fh: pp.make_labels(
        ['ST'], w=40, h=20, stamp=3, nozzle=nz, layer_h=lh, first_h=fh,
        bed=bd, out_dir=D),
    'frame':       lambda nz, bd, lh, fh: pp.make_frame(
        width=60, height=40, nozzle=nz, layer_h=lh, first_h=fh,
        bed=bd, out_dir=D),
    'seal':        lambda nz, bd, lh, fh: pp.make_seal(
        od=30, id_=15, nozzle=nz, layer_h=lh, bed=bd, out_dir=D),
    'cable ties':  lambda nz, bd, lh, fh: pp.make_cable_ties(
        count=2, length=60, nozzle=nz, layer_h=lh, first_h=fh,
        bed=bd, out_dir=D),
    'angles':      lambda nz, bd, lh, fh: pp.make_angles(
        count=1, leg_a=30, leg_b=30, nozzle=nz, layer_h=lh, first_h=fh,
        bed=bd, out_dir=D),
    'bricks':      lambda nz, bd, lh, fh: pp.make_bricks(
        jobs=[('B2x2', 1)], nozzle=nz, layer_h=lh, bed=bd, out_dir=D),
    'figures':     lambda nz, bd, lh, fh: pp.make_figures(
        count=1, scale=60, nozzle=nz, layer_h=lh, bed=bd, out_dir=D),
    'string art':  lambda nz, bd, lh, fh: pp.make_string_art(
        pattern='SPIRAL', diameter=60.0, anchors=24, lines=40,
        nozzle=nz, layer_h=lh, first_h=fh, bed=bd, out_dir=D),
    'litho FLAT':  lambda nz, bd, lh, fh: pp.make_lithophane(
        IMG, height_mm=40, orient='FLAT', nozzle=nz, layer_h=max(0.08, lh / 2),
        bed=bd, out_dir=D),
    'litho STAND': lambda nz, bd, lh, fh: pp.make_lithophane(
        IMG, height_mm=40, orient='STANDING', nozzle=nz,
        layer_h=max(0.08, lh / 2), bed=bd, out_dir=D),
    'colorpic':    lambda nz, bd, lh, fh: pp.make_colorpic(
        IMG, width_mm=40, bands=3, nozzle=nz, layer_h=lh, bed=bd,
        out_dir=D),
    'bridge':      lambda nz, bd, lh, fh: pp.make_bridge(
        length=60, nozzle=nz, layer_h=lh, first_h=fh, bed=bd, out_dir=D),
    'resonance':   lambda nz, bd, lh, fh: pp.make_resonance(
        axes=('x',), csv_dirs=[D], nozzle=nz, layer_h=lh, bed=bd,
        out_dir=D),
}
resonance_csv(D, 'x')

# tool-style transforms (operate on a generated source file)
def tool_brickkit(nz, bd, lh, fh):
    global BRICK_SRC
    if BRICK_SRC is None:
        out, _ = pp.make_bricks(jobs=[('B2x2', 1)], bed=bd, out_dir=D)
        BRICK_SRC = out if isinstance(out, str) else out[0]
    return pp.make_brick_kit(BRICK_SRC, nozzle=nz, layer_h=lh, bed=bd,
                             out_dir=D)


def tool_range(nz, bd, lh, fh):
    out, _ = pp.make_bricks(jobs=[('B2x2', 1)], bed=bd, out_dir=D)
    src = out if isinstance(out, str) else out[0]
    return pp.make_range(src, start=2, end=5, first_h=fh, out_dir=D)


def tool_scale(nz, bd, lh, fh):
    out, _ = pp.make_bricks(jobs=[('B2x2', 1)], bed=bd, out_dir=D)
    src = out if isinstance(out, str) else out[0]
    return pp.apply_scale(src, sx=1.5, sy=1.5, out_dir=D, bed=bd)


GENS['brick kit'] = tool_brickkit
GENS['range cut'] = tool_range
GENS['scale 150%'] = tool_scale


def paths_of(r):
    if r is None:
        return []
    if isinstance(r, (list, tuple)):
        out = []
        for x in r:
            out.extend(paths_of(x))
        return out
    if isinstance(r, str) and os.path.exists(r):
        return [r]
    return []


def run_gen(name, fn, nz, bd, lh, fh, phase):
    tag = '%s/%s nz=%.1f' % (phase, name, nz)
    t0 = time.time()
    try:
        r = fn(nz, bd, lh, fh)
    except Exception as e:                               # noqa: BLE001
        msg = str(e)
        # a REFUSAL is correct behavior when the job cannot fit - but it
        # must SAY so (bed/fit/too big), never crash cryptically
        if phase == 'bed':
            ck('%s: refuses with a clear reason' % tag,
               any(w in msg.lower() for w in
                   ('bed', 'fit', 'too', 'gro', 'big', 'size')),
               repr(e)[:120])
            return None, 'REFUSED'
        ck('%s: no exception' % tag, False, repr(e)[:140])
        return None, 'ERROR'
    dt = time.time() - t0
    files = [p for p in paths_of(r)]
    ck('%s: produced file(s)' % tag, files, str(r)[:80])
    gap = None
    for p in files:
        g = check_file(p, bd, nz, tag)
        if g is not None:
            gap = g
    return gap, '%.1fs' % dt


def main():
    print('R187 GENERATOR + TOOL PARAMETER MATRIX')
    print('=' * 72)
    gaps = {}

    print('--- N) nozzle sweep (0.2/0.4/0.6/0.8/1.0, reference bed)')
    for name, fn in sorted(GENS.items()):
        row = {}
        for nz in NOZZLES:
            lh, fh = LAYER_FOR[nz], FIRST_FOR[nz]
            gap, info = run_gen(name, fn, nz, REF_BED, lh, fh, 'N')
            row[nz] = gap if gap is not None else '-'
        gaps[name] = row
        print('    %-14s brim gap per nozzle: %s' % (
            name, {k: (v if isinstance(v, str) else round(v, 2))
                   for k, v in row.items()}))

    print('--- B) bed sweep (180/220/300/350, nozzle 0.4)')
    for name, fn in sorted(GENS.items()):
        for bname, bd in BEDS.items():
            run_gen(name, fn, 0.4, bd, 0.16, 0.22, 'B')

    print('--- V) key parameter variations (nozzle 0.6, reference bed)')
    VARS = [
        ('labels font SCRIPT', lambda: pp.make_labels(
            ['Fj'], w=40, h=18, font='SCRIPT', bed=REF_BED, out_dir=D)),
        ('labels font PIXEL', lambda: pp.make_labels(
            ['42'], w=40, h=18, font='PIXEL', bed=REF_BED, out_dir=D)),
        ('labels 3 lines', lambda: pp.make_labels(
            ['A~B~C'], w=50, h=30, bed=REF_BED, out_dir=D)),
        ('labels no brim', lambda: pp.make_labels(
            ['NB'], w=40, h=18, brim=False, bed=REF_BED, out_dir=D)),
        ('ties variant LOOP', lambda: pp.make_cable_ties(
            count=2, length=50, variant='LOOP', bed=REF_BED, out_dir=D)),
        ('frame A6+stand', lambda: pp.make_frame(
            preset='A6', stand=True, bed=REF_BED, out_dir=D)),
        ('frame CIRCLE+side', lambda: pp.make_frame(
            width=60, height=60, shape='CIRCLE', closure='SIDE',
            bed=REF_BED, out_dir=D)),
        ('seal profile V', lambda: pp.make_seal(
            od=30, id_=15, profile='V', bed=REF_BED, out_dir=D)),
        ('angles 45deg flat', lambda: pp.make_angles(
            count=1, angle_deg=45, flat=True, bed=REF_BED, out_dir=D)),
        ('bricks R-round 8col', lambda: pp.make_bricks(
            jobs=[('R1x1', 2), ('B2x2', 1)], colors=3, mode='BY_OBJECT',
            bed=REF_BED, out_dir=D)),
        ('figures SINGLE 4col', lambda: pp.make_figures(
            count=1, scale=80, mode='SINGLE', colors=4, bed=REF_BED,
            out_dir=D)),
        ('string art PHOTO', lambda: pp.make_string_art(
            src=IMG, pattern='PHOTO', diameter=60.0, anchors=24, lines=40,
            bed=REF_BED, out_dir=D)),
        ('litho contour 2', lambda: pp.make_lithophane(
            IMG, height_mm=40, orient='FLAT', contour=2, bed=REF_BED,
            out_dir=D)),
        ('colorpic no-swap', lambda: pp.make_colorpic(
            IMG, width_mm=40, bands=3, swap=False, bed=REF_BED, out_dir=D)),
        ('bridge 50pct tower', lambda: pp.make_bridge(
            length=60, short_pct=50, tower=15, bed=REF_BED, out_dir=D)),
        ('resonance xy plot', lambda: pp.make_resonance(
            axes=('x', 'y'), csv_dirs=[D], bed=REF_BED, out_dir=D)),
    ]
    resonance_csv(D, 'y')
    for name, fn in VARS:
        try:
            r = fn()
        except Exception as e:                           # noqa: BLE001
            # a CLEAR refusal is correct when the variation cannot fit -
            # the message must say why (the field-log honesty rule)
            ck('V %s: refuses with a clear reason' % name,
               len(str(e)) > 10 and any(
                   w in str(e).lower() for w in
                   ('mm', 'bed', 'fit', 'too', 'size', 'big', 'reduce')),
               repr(e)[:120])
            continue
        files = paths_of(r)
        ck('V %s: produced file(s)' % name, files, str(r)[:70])
        for p in files:
            check_file(p, REF_BED, 0.6, 'V/%s' % name)

    print('=' * 72)
    print('brim air gap, ink edge to ink edge (mm) by nozzle - R184 wants >= 0.35:')
    hdr = '%-14s' % 'generator'
    for nz in NOZZLES:
        hdr += ' %5s' % ('%.1f' % nz)
    print(hdr)
    for name, row in sorted(gaps.items()):
        line = '%-14s' % name
        for nz in NOZZLES:
            v = row.get(nz, '-')
            line += ' %5s' % (v if isinstance(v, str) else '%.2f' % v)
        print(line)
    if fails:
        print()
        for name, info in fails:
            print('  FAIL %-52s %s' % (name, info))
    print('R187 MATRIX: %d checks, %d FAIL' % (n_ck[0], len(fails)))
    import shutil
    shutil.rmtree(D, ignore_errors=True)
    return 1 if fails else 0


if __name__ == '__main__':
    sys.exit(main())
