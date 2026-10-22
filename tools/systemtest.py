#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""R129: FULL-SYSTEM INTEGRATION SWEEP.

Runs AFTER the usual battery (render / audit / megatest / goldens /
validator / dialects / geom / texture-sim) as the release gate: every
generator of the package is called with several parameter combinations and
EVERY produced file has to pass the shared structural invariants -

  TAG + PRINT_START/PRINT_END, EXCLUDE_OBJECT balance + defines,
  z monotonic (except BY_OBJECT=1 files), TYPES only known codes,
  coordinates inside the bed, no CRLF, no move flood per layer,
  M600 / purge-tower coherence for the multicolor tools.

Plus the wiring sweep: every nonce channel is actually read by the watcher,
every GEN_* console macro exists and is reachable from the LCD, every
module file carries its version sentinel and _CHECK_INSTALL lists it.

Pure offline simulation - no printer required. Exit code != 0 on any FAIL.
"""
import math
import os
import re
import subprocess
import sys
import tempfile
import zlib
import struct

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import r2_postproc as pp                    # noqa: E402
from r2_texture import apply_texture        # noqa: E402

BED = (0.0, -3.0, 220.0, 217.0)
KNOWN_TYPES = {
    'WALL-OUTER', 'WALL-INNER', 'INFILL-SOLID', 'INFILL-SPARSE',
    'SURFACE-BOTTOM', 'SURFACE-TOP', 'BRIM', 'IRONING', 'BRIDGE',
    'PRIME-TOWER', 'CUSTOM', 'SUPPORT',
}
PASS = FAIL = 0
FILES = 0
LINES = []


def check(name, cond, info=''):
    global PASS, FAIL
    if cond:
        PASS += 1
        LINES.append('PASS  %s' % name)
    else:
        FAIL += 1
        LINES.append('FAIL  %s\n      -> %s' % (name, info))


def png(path, w, h, fn):
    rows = b''
    for y in range(h):
        rows += b'\x00' + b''.join(bytes(fn(x, y)) for x in range(w))
    def chunk(t, d):
        c = t + d
        return struct.pack('>I', len(d)) + c + struct.pack(
            '>I', zlib.crc32(c) & 0xffffffff)
    open(path, 'wb').write(b'\x89PNG\r\n\x1a\n'
                           + chunk(b'IHDR', struct.pack('>IIBBBBB', w, h, 8, 2, 0, 0, 0))
                           + chunk(b'IDAT', zlib.compress(rows))
                           + chunk(b'IEND', b''))


def sliced_box(path, w=32.0, h=24.0, zh=9.6, support=True, lh=0.2):
    """a foreign-style sliced box: ;TYPE: comments, absolute E, support."""
    x0, y0 = 60.0, 60.0
    L = [';FLAVOR:Marlin', 'M82', 'G90', 'G21']
    e = 0.0
    z = 0.0
    while z < zh - 1e-9:
        z = round(z + lh, 3)
        L += [';LAYER_CHANGE', ';Z:%.3f' % z, 'G0 Z%.3f F600' % z,
              'G0 X%.3f Y%.3f F9000' % (x0, y0), ';TYPE:WALL-OUTER']
        for (ax, ay, bx, by) in ((x0, y0, x0 + w, y0), (x0 + w, y0, x0 + w, y0 + h),
                                 (x0 + w, y0 + h, x0, y0 + h), (x0, y0 + h, x0, y0)):
            e += 10.0
            L.append('G1 X%.3f Y%.3f E%.4f F1800' % (bx, by, e))
            e += 2.0
            L.append('G1 X%.3f Y%.3f E%.4f F1800' % (ax, ay, e))
        L.append(';TYPE:Internal solid infill')
        yy = y0 + 1.0
        while yy < y0 + h - 0.5:
            e += 15.0
            L.append('G1 X%.3f Y%.3f E%.4f F2400' % (x0 + 1, yy, e))
            e += 15.0
            L.append('G1 X%.3f Y%.3f E%.4f F2400' % (x0 + w - 1, yy, e))
            yy += 1.6
        if support and z > 2.0:
            L.append(';TYPE:Support')
            e += 20.0
            L.append('G1 X45.000 Y60.000 E%.4f F2400' % e)
            e += 20.0
            L.append('G1 X45.000 Y84.000 E%.4f F2400' % e)
    open(path, 'w').write('\n'.join(L) + '\n')


def invariants(tag, path, bed=BED, expect_m600=None, tower=None):
    """the shared structural contract of every generated file."""
    global FILES
    FILES += 1
    t = open(path, errors='replace').read()
    base = os.path.basename(path)
    head = t[:4000]
    ok = ('; R2-POSTPROC v5' in head and 'PRINT_START' in head
          and '\nPRINT_END' in t and '\r' not in t)
    check('%s: TAG + PRINT_START/END + LF only' % tag, ok, base)
    # exclude balance + defines
    starts = re.findall(r'EXCLUDE_OBJECT_START NAME=(\S+)', t)
    ends = re.findall(r'EXCLUDE_OBJECT_END NAME=(\S+)', t)
    defs = set(re.findall(r'EXCLUDE_OBJECT_DEFINE NAME=(\S+)', t))
    # (range excerpts of a source without objects legitimately carry none)
    check('%s: EXCLUDE start/end balance, all defined' % tag,
          len(starts) == len(ends) and set(starts) == set(ends)
          and set(starts) <= defs,
          '%d/%d/%d' % (len(starts), len(ends), len(defs)))
    # z monotonic unless BY_OBJECT=1
    zs = [float(m.group(1)) for m in re.finditer(r'^;Z:([\d.]+)', t, re.M)]
    by_obj = re.search(r'^_FILE_INFO.*BY_OBJECT=1', t, re.M) is not None
    check('%s: z monotonic (%s)' % (tag, 'BY_OBJECT file' if by_obj else ''),
          by_obj or all(b >= a for a, b in zip(zs, zs[1:])), str(zs[:6]))
    # TYPES known
    m = re.search(r'TYPES=(\S+)', t)
    types = set(m.group(1).rstrip(',').split(',')) if m else set()
    check('%s: _FILE_INFO TYPES known' % tag,
          m is not None and types <= KNOWN_TYPES and types,
          str(sorted(types - KNOWN_TYPES)))
    # coordinates inside the bed (+3mm brim tolerance)
    xs = [float(v) for v in re.findall(r'\bX(-?[\d.]+)', t)]
    ys = [float(v) for v in re.findall(r'\bY(-?[\d.]+)', t)]
    check('%s: coordinates inside the bed' % tag,
          xs and ys and min(xs) >= bed[0] - 3 and max(xs) <= bed[2] + 3
          and min(ys) >= bed[1] - 3 and max(ys) <= bed[3] + 3,
          'X %.1f..%.1f Y %.1f..%.1f' % (min(xs), max(xs), min(ys), max(ys)))
    # sliver flood guard: a degenerate hatch would emit tens of thousands
    # of tiny moves inside ONE layer (the .89 field bug class)
    parts = t.split(';LAYER_CHANGE')
    mx = max((p.count('\nG1 ') for p in parts[1:]), default=0)
    check('%s: no sliver flood (<5000/layer)' % tag, mx < 5000, str(mx))
    # extrusions exist
    check('%s: extruding moves exist' % tag,
          len(re.findall(r'\nG1 X[\d.]+ Y[\d.]+.*E[\d.]+', t)) > 20, '')
    # optional expectations
    n600 = t.count('\nM600')
    if expect_m600 is not None:
        check('%s: M600 count == %d' % (tag, expect_m600),
              n600 == expect_m600, str(n600))
    if tower is not None:
        has = 'EXCLUDE_OBJECT_START NAME=PURGE_TOWER' in t
        check('%s: purge tower %s' % (tag, 'on' if tower else 'off'),
              has == tower, str(has))
    return t


def main():
    D = tempfile.mkdtemp(prefix='sys_')
    # R161: clean the fixture dir on every exit path (25 MB per run filled
    # the 992MB tmpfs after a few battery rounds - same class as R121).
    import atexit, shutil
    atexit.register(lambda: shutil.rmtree(D, ignore_errors=True))

    # ---------------- source fixtures ----------------
    box = os.path.join(D, 'box.gcode')
    sliced_box(box)
    sketch = os.path.join(D, 'sketch.png')
    png(sketch, 96, 96, lambda x, y: (255, 255, 255)
        if not (20 < x < 76 and 20 < y < 76)
        else ((0, 0, 0) if (30 <= x < 34 or 50 <= y < 54)
              else (160, 160, 160)))
    grad = os.path.join(D, 'grad.png')
    png(grad, 64, 64, lambda x, y: (int(255 * (x / 63.0)),) * 3
        if y < 32 else (int(255 * (1 - x / 63.0)),) * 3)
    txt = os.path.join(D, 'note.txt')
    open(txt, 'w').write('R2 SYSTEM TEST\n')

    # ---------------- 1) every generator, several combos ----------------
    boxp = os.path.join(D, 'boxp.gcode')
    open(boxp, 'w').write(open(box).read())
    pp.process(boxp)                      # the watcher pass: TAG + LAYER_MARK
    o, i = pp.make_range(boxp, 3, 8, version=1)
    invariants('range', o, expect_m600=0)
    t_rng = open(o, errors='replace').read()
    check('range: LAYER_MARK layers survived the excerpt',
          t_rng.count('\nLAYER_MARK\n') >= 5, str(t_rng.count('\nLAYER_MARK\n')))

    o, i = pp.make_labels(['ALPHA', 'BETA~ZWEI'], w=50, h=25, hole_side=1,
                          color2=True, out_dir=D, bed=BED)
    invariants('labels 2col', o, expect_m600=1, tower=True)
    o, i = pp.make_labels(['SOLO'], w=40, h=20, color2=False, out_dir=D, bed=BED)
    invariants('labels 1col', o, expect_m600=0, tower=False)

    o, i = pp.make_bridge(length=60, out_dir=D, bed=BED)
    invariants('bridge', o)
    o, i = pp.make_cable_ties(count=3, length=70, out_dir=D, bed=BED)
    invariants('cable ties', o)
    o, i = pp.make_angles(count=2, out_dir=D, bed=BED)
    invariants('angles', o)
    o, i = pp.make_seal(od=40, id_=20, out_dir=D, bed=BED)
    invariants('seal flat', o)
    o, i = pp.make_seal(od=40, id_=20, profile='GROOVE', ironing=True,
                        out_dir=D, bed=BED)
    invariants('seal groove', o)

    o, i = pp.make_frame(preset='10x15', out_dir=D, bed=BED)
    for f in i['all_files']:
        invariants('frame 10x15', f)
    o, i = pp.make_frame(width=90, height=130, depth=20, closure='SIDE',
                         stand=True, out_dir=D, bed=BED)
    for f in i['all_files']:
        invariants('frame CASE side', f)
    o, i = pp.make_frame(width=90, height=130, front='FLIP', disc='GLASS',
                         disc_side='BACK', out_dir=D, bed=BED)
    for f in i['all_files']:
        invariants('frame flip+disc', f)

    o, i = pp.make_lithophane(sketch, height_mm=50.0, out_dir=D, bed=BED)
    invariants('litho standing', o, expect_m600=0, tower=False)
    o, i = pp.make_lithophane(sketch, orient='FLAT', height_mm=50.0,
                              layer_h=0.2, levels=3, col_layers=2, ironing=True,
                              out_dir=D, bed=BED)
    invariants('litho flat steps', o, expect_m600=0, tower=False)
    o, i = pp.make_lithophane(sketch, orient='FLAT', height_mm=50.0,
                              layer_h=0.2, levels=3, col_layers=2,
                              col_mode='LAST', out_dir=D, bed=BED)
    invariants('litho flat LAST', o, expect_m600=1, tower=True)
    o, i = pp.make_lithophane(sketch, orient='FLAT', height_mm=50.0,
                              layer_h=0.2, levels=4, col_layers=1,
                              col_mode='EACH', border=4.0, corner_r=6.0,
                              out_dir=D, bed=BED)
    invariants('litho flat EACH+frame', o, expect_m600=3, tower=True)

    o, i = pp.make_colorpic(grad, width_mm=70.0, bands=4, band_h=0.8,
                            out_dir=D, bed=BED)
    invariants('colorpic swap', o, expect_m600=3, tower=True)
    o, i = pp.make_colorpic(grad, width_mm=70.0, bands=3, band_h=0.6,
                            swap=False, out_dir=D, bed=BED)
    invariants('colorpic noswap', o, expect_m600=0, tower=False)

    o, i = pp.make_bricks([('B2x4', 2), ('P2x2', 1)], out_dir=D, bed=BED)
    invariants('bricks', o)
    o, i = pp.make_brick_kit(box, detail='SMALL', mode='BY_LAYER', colors=2,
                             out_dir=D, bed=BED)
    for f in [os.path.join(D, p) for p in i['plates']]:
        invariants('kit SMALL', f, expect_m600=0, tower=False)
    o, i = pp.make_brick_kit(box, detail='BIG', mode='BY_OBJECT', colors=2,
                             out_dir=D, bed=BED)
    invariants('kit BIG object', o, expect_m600=1, tower=False)

    o, i = pp.make_figures(count=1, scale=100, out_dir=D, bed=BED)
    invariants('figures 100', o, expect_m600=0, tower=False)
    o, i = pp.make_figures(count=2, scale=60, out_dir=D, bed=BED)
    invariants('figures 60', o)

    # pen-plotter dialect: no TAG/PRINT_START/extrusions - its own contract
    o, _nl, _sz = pp.text_convert(txt, out=os.path.join(D, 'note_plot.gcode'))
    global FILES
    FILES += 1
    _tp = open(o, errors='replace').read()
    check('plot text: pen dialect (moves + pen up/down, no printer header)',
          len(re.findall(r'\nG1 X[\d.]+ Y[\d.]+', _tp)) > 20
          and 'PRINT_START' not in _tp and '\r' not in _tp, '')

    o2, _ = apply_texture(pp.make_frame(preset='10x15', out_dir=D, bed=BED)[0],
                          out_dir=D, mode='FUZZY', fuzzy_thick=0.3)
    invariants('texture fuzzy', o2)
    o3, _ = apply_texture(pp.make_frame(preset='10x15', out_dir=D, bed=BED)[0],
                          out_dir=D, mode='BUMPS', bump_pattern='GRID')
    invariants('texture bumps', o3)

    # ---------------- 2) guards across the tools ----------------
    guards = [
        ('labels empty', lambda: pp.make_labels([], out_dir=D)),
        ('litho bad ext', lambda: pp.make_lithophane(txt, out_dir=D)),
        ('colorpic bad color', lambda: pp.make_colorpic(
            grad, colors='FOO', out_dir=D)),
        ('kit colors 9', lambda: pp.make_brick_kit(box, colors=9, out_dir=D)),
        ('kit missing src', lambda: pp.make_brick_kit(
            os.path.join(D, 'nope.gcode'), out_dir=D)),
        ('figures scale 400', lambda: pp.make_figures(scale=400, out_dir=D)),
        ('bricks unknown', lambda: pp.make_bricks([('B9x9', 1)],
                                                  out_dir=D)),
        ('frame depth 2', lambda: pp.make_frame(depth=2.0, out_dir=D)),
        ('seal too small', lambda: pp.make_seal(od=8, id_=3, out_dir=D)),
        ('litho flat bad colmode', lambda: pp.make_lithophane(
            sketch, orient='FLAT', col_mode='NOPE', out_dir=D)),
    ]
    for name, fn in guards:
        try:
            fn()
            check('guard %s raises' % name, False, 'no raise')
        except ValueError:
            check('guard %s raises' % name, True)

    # ---------------- 3) wiring sweep ----------------
    src = open(os.path.join(HERE, 'r2_postproc.py'), encoding='utf-8').read()
    check('wiring: every nonce channel is read by the watcher',
          all("rv.get('%s'" % k in src for k in pp.NONCE_KEYS),
          str([k for k in pp.NONCE_KEYS if "rv.get('%s'" % k not in src]))
    lcd = open(os.path.join(HERE, '..', 'menus', 'lcd_menues.cfg'),
               encoding='utf-8').read()
    gen_macros = ['GEN_LABELS', 'GEN_FRAME', 'GEN_SEAL', 'GEN_CABLE_TIES',
                  'GEN_ANGLES', 'GEN_BRICKS', 'GEN_BRICKKIT', 'GEN_FIGURES',
                  'GEN_COLORPIC', 'LITHO_CREATE', 'COLORPIC_CREATE',
                  'BRICK_CREATE']
    check('wiring: every console macro is reachable from the LCD',
          all(m in lcd for m in gen_macros),
          str([m for m in gen_macros if m not in lcd]))
    macros_dir = os.path.join(HERE, '..', 'macros')
    cfgs = sorted(f for f in os.listdir(macros_dir) if f.endswith('.cfg'))
    sentinels = 0
    for f in cfgs:
        body = open(os.path.join(macros_dir, f), encoding='utf-8').read()
        if re.search(r'\[gcode_macro _V\d+_', body):
            sentinels += 1
    state = open(os.path.join(macros_dir, '01_state.cfg'),
                 encoding='utf-8').read()
    listed = len(re.findall(r"\('\d+_[\w.]+\.cfg',+\s*\['_V", state))
    check('wiring: module sentinels (%d cfg) + _CHECK_INSTALL lists them'
          % len(cfgs), sentinels == len(cfgs) and listed >= len(cfgs) - 1,
          'sentinels %d, listed %d, cfgs %d' % (sentinels, listed, len(cfgs)))

    r = subprocess.run([sys.executable, os.path.join(HERE, 'config_validator.py')],
                       capture_output=True, text=True, cwd=os.path.join(HERE, '..'))
    check('wiring: config validator clean', r.returncode == 0
          and 'No errors found' in r.stdout, r.stdout[-200:])

    # ---------------- report ----------------
    print('\n'.join(LINES))
    print('\n' + '=' * 70)
    print('SYSTEMTEST: %d checks, %d files, %d FAIL' % (PASS + FAIL, FILES, FAIL))
    return 1 if FAIL else 0


if __name__ == '__main__':
    sys.exit(main())
