#!/usr/bin/env python3
"""R216 travel golden rule check (pinned).

Field wish .136m: NO generator may ever drag the nozzle across freshly
printed plastic - the field log showed threads straight across labels,
band tops and range floors. The golden rule lives in _Pen.travel
(_ink_crossing): every travel that TRANSVERSENSALLY crosses this layer's
ink retracts + Z-hops, no matter how short, even on the first layers.
Parallel neighbor connect moves (the deliberate pressure keepers) never
intersect, so they stay flat - no retract storm (R77 lesson).

This check regenerates a deterministic set of files with small configs
and audits them: a flat, unretracted travel at constant Z that crosses
3+ extrusion segments transversally = a violation. Pins: 0 everywhere.

Also pins the R216 PrusaSlicer shorthand fix: make_range rejected
'E.00715' style E words ('no extrusion' on a perfectly printing file)
because \\bE(-?\\d+ requires a digit - the synthetic range source below
uses the shorthand and must slice cleanly.

Run:  python3 tools/r216_travel_check.py
"""
import importlib.util
import math
import os
import struct
import sys
import tempfile
import zlib

HERE = os.path.dirname(os.path.abspath(__file__))
spec = importlib.util.spec_from_file_location(
    'r2p', os.path.join(HERE, 'r2_postproc.py'))
pp = importlib.util.module_from_spec(spec)
spec.loader.exec_module(pp)

PINS = {}
FAILS = []


def audit(path):
    """flat unretracted travels that transversally cross >=3 ink segments
    of the same layer - the golden-rule violation"""
    viol = []
    x = y = z = 0.0
    e = 0.0
    e_rel = False
    retracted = False
    extr = {}
    cur_type = ''
    for ln in open(path, errors='replace').read().split('\n'):
        if ln.startswith(';TYPE:'):
            cur_type = ln[6:].strip()
            continue
        code = ln.split(';', 1)[0].strip()
        if not code:
            continue
        parts = code.split()
        cmd = parts[0].upper()
        if cmd == 'M83':
            e_rel = True
            continue
        if cmd == 'M82':
            e_rel = False
            continue
        if cmd == 'G10':
            retracted = True
            continue
        if cmd == 'G11':
            retracted = False
            continue
        if cmd == 'G92':
            for p in parts[1:]:
                if p[:1].upper() == 'E':
                    try:
                        e = float(p[1:])
                    except ValueError:
                        pass
            continue
        if cmd not in ('G0', 'G1'):
            continue
        nx = ny = nz = ne = None
        for p in parts[1:]:
            a = p[:1].upper()
            try:
                v = float(p[1:])
            except ValueError:
                continue
            if a == 'X':
                nx = v
            elif a == 'Y':
                ny = v
            elif a == 'Z':
                nz = v
            elif a == 'E':
                ne = v
        px, py, pz = x, y, z
        if nx is not None:
            x = nx
        if ny is not None:
            y = ny
        if nz is not None:
            z = nz
        de = 0.0
        if ne is not None:
            de = (ne - e) if not e_rel else ne
            e = ne if not e_rel else e + ne
        d = math.hypot(x - px, y - py)
        if de > 0.0 and d > 1e-4:
            extr.setdefault(round(pz, 3), []).append((px, py, x, y))
            retracted = False
        elif d > 0.05 and (nz is None or abs(nz - pz) < 0.06):
            if not retracted:
                tvx, tvy = x - px, y - py
                tl = math.hypot(tvx, tvy) or 1.0
                tvx, tvy = tvx / tl, tvy / tl
                hits = 0
                for (a, b, c, d2) in extr.get(round(z, 3), ()):
                    if pp._segs_cross((px, py), (x, y), (a, b), (c, d2)):
                        sx, sy = c - a, d2 - b
                        sl = math.hypot(sx, sy) or 1.0
                        # parallel neighbor lines are the flat connect moves
                        if abs(tvx * sx / sl + tvy * sy / sl) > 0.90:
                            continue
                        hits += 1
                        if hits > 2:
                            break
                if hits > 2 and d >= 0.25:
                    viol.append((cur_type, round(z, 2), code[:40]))
    return viol


def png(path, w=48, h=48):
    raw = b''.join(b'\x00' + bytes(255 if (i * j) % 5 else 0
                                   for j in range(w)) for i in range(h))

    def chunk(t, d):
        c = t + d
        return struct.pack('>I', len(d)) + c + struct.pack('>I', zlib.crc32(c))
    open(path, 'wb').write(
        b'\x89PNG\r\n\x1a\n'
        + chunk(b'IHDR', struct.pack('>IIBBBBB', w, h, 8, 0, 0, 0, 0))
        + chunk(b'IDAT', zlib.compress(raw)) + chunk(b'IEND', b''))


def synth_processed_src(path):
    """a tiny 'processed' file (LAYER_MARK layers) in PrusaSlicer
    shorthand E notation - pins the R216 \\bE(-?\\d*\\.?\\d+) fix"""
    L = ['M83', '; generated test source', ';TYPE:Outer wall']
    for i in range(8):
        L.append('LAYER_MARK')
        L.append('G1 Z%.3f F10800' % (0.2 + i * 0.2))
        # two boxes; the gap travel between them crosses nothing, the
        # mid-box sweep over the hatch pins the ink rule for the excerpt
        for bx in (100.0, 110.0):
            L.append('G0 X%.3f Y100.000 F9000' % bx)
            L.append('G1 X%.3f Y100.000 E.05000 F1200' % (bx + 5))
            L.append('G1 X%.3f Y105.000 E.05000 F1200' % (bx + 5))
            L.append('G1 X%.3f Y105.000 E.05000 F1200' % bx)
            L.append('G1 X%.3f Y100.000 E.05000 F1200' % bx)
            L.append(';TYPE:Internal solid infill')
            for r in range(1, 5):
                yy = 100.0 + r
                L.append('G0 X%.3f Y%.3f F9000' % (bx + 0.5, yy))
                L.append('G1 X%.3f Y%.3f E.05000 F1200' % (bx + 4.5, yy))
        L.append(';TYPE:Outer wall')
    open(path, 'w').write('\n'.join(L) + '\n')


def check(name, path):
    v = audit(path)
    PINS[name] = len(v)
    if v:
        FAILS.append('%s: %d flat crossings %r' % (name, len(v), v[:3]))
    print('%-11s violations %d %s' % (name, len(v),
                                      'CLEAN' if not v else
                                      ' '.join('%s z%.1f' % t for t in v[:3])))


def main():
    d = tempfile.mkdtemp(prefix='r216travel_')
    img = os.path.join(d, 't.png')
    png(img)
    for sub in ('labels', 'bricks', 'ties', 'cpic', 'str', 'fig', 'brg',
                'rng', 'rngsrc'):
        os.makedirs(os.path.join(d, sub), exist_ok=True)

    outs = {}
    outs['labels'] = pp.make_labels(
        ['HELLO', 'WORLD'], w=60, h=30,
        out_dir=os.path.join(d, 'labels'), version=1)[0]
    outs['bricks'] = pp.make_bricks(
        [('B2x4', 2), ('P1x2', 1), ('C1x1', 1)],
        out_dir=os.path.join(d, 'bricks'), bed=(0, -3, 220, 217),
        version=1)[0]
    outs['ties'] = pp.make_cable_ties(
        4, out_dir=os.path.join(d, 'ties'), version=1)[0]
    outs['colorpic'] = pp.make_colorpic(
        img, width_mm=60, bands=4, out_dir=os.path.join(d, 'cpic'),
        version=1)[0]
    outs['stringart'] = pp.make_string_art(
        src=img, pattern='PHOTO', anchors=60, lines=300,
        out_dir=os.path.join(d, 'str'), version=1)[0]
    outs['figures'] = pp.make_figures(
        count=1, out_dir=os.path.join(d, 'fig'), version=1)[0]
    outs['bridge'] = pp.make_bridge(
        out_dir=os.path.join(d, 'brg'), version=1)[0]

    for name, r in outs.items():
        f = r[0] if isinstance(r, list) else r
        check(name, f)

    # range on a PrusaSlicer-shorthand processed source (pins the regex fix)
    src = os.path.join(d, 'rngsrc', 'synth_proc.gcode')
    synth_processed_src(src)
    try:
        r = pp.make_range(src, start=2, end=6, floor=2, top=2, brim=1,
                          out_dir=os.path.join(d, 'rng'), version=1)
        f = r[0] if isinstance(r, (list, tuple)) else r
        check('range', f[0] if isinstance(f, list) else f)
    except ValueError as ex:
        FAILS.append('range: make_range rejected the shorthand source: %s'
                     % ex)
        PINS['range'] = -1
        print('range       FAILED - %s' % ex)

    print()
    if FAILS:
        print('RESULT: FAIL')
        for f in FAILS:
            print('  ' + f)
        return 1
    print('RESULT: PASS - %d generators, 0 flat ink crossings'
          % len(PINS))
    return 0


if __name__ == '__main__':
    sys.exit(main())
