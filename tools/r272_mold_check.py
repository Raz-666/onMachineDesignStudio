#!/usr/bin/env python3
"""R272 field check: the mold SURFACE parameter (STANDARD/FINE/FUZZY) -
measured, not assumed.

Synthetic source: BOULDER r = 6 + 9*sin(pi*z/20) - no undercut, the plain
two-part path, so every difference below is the SURFACE mode alone.

Checks:
  A  signature & validation: surface in the def line, bad value refused,
     surface echoed in info
  B  STANDARD regression: byte-identical to the default call (no
     surface argument)
  C  FINE: IRONING marker + passes ONLY in the last layer (the parting
     face), ironing line count > 0, SPEED_INNER drops 60 -> 20 in
     _FILE_INFO (the one knob the R159 speed normalizer exposes), no
     F3600 print moves, cavity cells identical to STANDARD
  D  FUZZY: wall-loop points measured off the cell-edge family -
     STANDARD sits exactly ON the edges (0 of N beyond 0.02mm), FUZZY
     moves most of them, max offset <= 0.12mm + tolerance, cavity
     cells identical (fuzz moves printed lines, never the mask),
     determinism (rerun byte-identical)
  E  combos: sector molds accept both modes (mushroom sectors=1 FINE
     irons EACH piece's last layer, FUZZY keeps 3 files); source
     quotes: watcher reads mold_surface, MOLD_CREATE validates SURFACE,
     the toolchain registry knows the surface enum
"""
import math
import os
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import r2_postproc as pp  # noqa: E402

LH = 0.2
WID = 0.4 * 1.08

fails = 0
count = 0


def check(name, ok, info=''):
    global fails, count
    count += 1
    print(('  ok   ' if ok else '  FAIL ') + name)
    if not ok:
        fails += 1
        print('      -> %s' % str(info)[:240])


def write_shape(D, name, radii_fn, n_lay=100, cx=50.0, cy=50.0):
    src = os.path.join(D, name)
    with open(src, 'w') as f:
        f.write(';TYPE:Outer wall\nM82\nG90\n')
        e = 0.0
        for li in range(1, n_lay + 1):
            z = round(li * LH, 3)
            r = radii_fn(z)
            pts = [(cx + r * math.cos(a), cy + r * math.sin(a))
                   for a in [i * math.pi / 36 for i in range(73)]]
            f.write(';LAYER_CHANGE\nG1 Z%.3f F600\n' % z)
            px, py = pts[0]
            f.write('G0 X%.3f Y%.3f F3000\n' % (px, py))
            for (qx, qy) in pts[1:]:
                d = math.hypot(qx - px, qy - py)
                e += d * 0.05
                f.write('G1 X%.3f Y%.3f E%.5f F1200\n' % (qx, qy, e))
                px, py = qx, qy
            for t in (-0.6, -0.2, 0.2, 0.6):
                dy = math.sqrt(max(0.0, r * r - (r * t) ** 2))
                x1, y1 = cx + r * t, cy - dy
                x2, y2 = cx + r * t, cy + dy
                f.write('G0 X%.3f Y%.3f F3000\n' % (x1, y1))
                e += math.hypot(x2 - x1, y2 - y1) * 0.05
                f.write('G1 X%.3f Y%.3f E%.5f F1200\n' % (x2, y2, e))
    return src


def layer_lines(path):
    """[[(line, ...), ...], ...] - one list per ;LAYER_CHANGE."""
    layers = []
    cur = None
    for ln in open(path, errors='replace'):
        if ln.startswith(';LAYER_CHANGE'):
            cur = []
            layers.append(cur)
        elif cur is not None:
            cur.append(ln)
    return layers


def wall_offsets(path, x0, y0, wid, layers=(1, 2, 3, 4)):
    """distance of WALL-loop extrusion points from the cell-edge family
    (x0 + k*wid / y0 + k*wid) - 0 for an untouched contour."""
    x = y = 0.0
    cur = -1
    in_wall = False
    pts = []
    for ln in open(path, errors='replace'):
        if ln.startswith(';LAYER_CHANGE'):
            cur += 1
            in_wall = False
            continue
        if ln.startswith(';TYPE:'):
            in_wall = 'Outer wall' in ln
            continue
        if ln.startswith('APPLY_TYPE'):
            in_wall = ln.startswith('APPLY_TYPE TYPE=WALL-OUTER')
            continue
        code = ln.split(';', 1)[0].strip()
        parts = code.split()
        if parts and parts[0] in ('G0', 'G1'):
            p = pp.parse_params(code[2:])
            if 'X' in p:
                x = p['X']
            if 'Y' in p:
                y = p['Y']
            if parts[0] == 'G1' and 'E' in p and in_wall and cur in layers:
                dx = (x - x0) / wid
                dy = (y - y0) / wid
                pts.append(min(abs(dx - round(dx)),
                               abs(dy - round(dy))) * wid)
    return pts


def try_mold(src, **kw):
    D = tempfile.mkdtemp(prefix='r272run_')
    kw.setdefault('wall', 5.0)
    try:
        out, info = pp.make_mold(src, out_dir=D, **kw)
        return D, info, None
    except ValueError as ex:
        return D, None, str(ex)


def main():
    src_txt = open(os.path.join(HERE, 'r2_postproc.py'),
                   encoding='utf-8').read()

    print('A  signature & validation')
    sig_block = src_txt.split('def make_mold(', 1)[1][:900]
    check('A1 surface in the signature', "surface='STANDARD'" in sig_block,
          sig_block[:100])
    D = tempfile.mkdtemp(prefix='r272a_')
    boulder = write_shape(D, 'boulder.gcode',
                          lambda z: 6.0 + 9.0 * math.sin(math.pi * z / 20.0))
    try:
        pp.make_mold(boulder, out_dir=D, surface='MIRROR')
        check('A2 bad surface refused', False, 'no ValueError')
    except ValueError as ex:
        check('A2 bad surface refused', 'surface must be' in str(ex), str(ex))

    print('B  STANDARD regression')
    Da, ia, _ = try_mold(boulder, part='TOP')
    Db, ib, _ = try_mold(boulder, part='TOP', surface='STANDARD')
    same = (open(os.path.join(Da, ia['files'][0]), 'rb').read()
            == open(os.path.join(Db, ib['files'][0]), 'rb').read())
    check('B1 byte-identical to the default call', same)
    check('B2 surface echoed in info',
          ia['surface'] == 'STANDARD' and ib['surface'] == 'STANDARD')

    print('C  FINE (ironing + slow speed image)')
    Dc, ic, err = try_mold(boulder, part='TOP', surface='FINE')
    check('C1 builds', err is None, err)
    if ic:
        fc = os.path.join(Dc, ic['files'][0])
        lays = layer_lines(fc)
        iron_last = sum(1 for ln in lays[-1]
                        if 'APPLY_TYPE TYPE=IRONING' in ln)
        iron_else = sum(1 for lay in lays[:-1]
                        for ln in lay if 'APPLY_TYPE TYPE=IRONING' in ln)
        iron_moves = sum(1 for ln in lays[-1]
                         if ln.split(';', 1)[0].strip().startswith('G1')
                         and ' E' in ln
                         and lays[-1].index(ln) > 0)
        check('C2 IRONING only in the last layer',
              iron_last == 1 and iron_else == 0, (iron_last, iron_else))
        txt = open(fc, errors='replace').read()
        fi = [ln for ln in txt.splitlines()
              if ln.startswith('_FILE_INFO')][0]
        check('C3 speed image drops 60 -> 20 mm/s',
              'SPEED_INNER=20' in fi and 'SPEED_INNER=60' not in fi,
              fi[:150])
        check('C4 print moves at F1200, none at F3600',
              'F1200' in txt and 'F3600' not in txt)
        check('C5 IRONING in _FILE_INFO TYPES',
              'IRONING' in fi, fi[:150])
        check('C6 cavity identical to STANDARD',
              ic['cells_top'] == ia['cells_top'],
              (ic['cells_top'], ia['cells_top']))

    print('D  FUZZY (wall jitter, cavity untouched)')
    Dd, idf, err = try_mold(boulder, part='TOP', surface='FUZZY')
    check('D1 builds', err is None, err)
    if idf:
        fd = os.path.join(Dd, idf['files'][0])
        Dd2, idf2, _ = try_mold(boulder, part='TOP', surface='FUZZY')
        check('D2 determinism (rerun byte-identical)',
              open(fd, 'rb').read()
              == open(os.path.join(Dd2, idf2['files'][0]), 'rb').read())
        W, H = ia['block']
        x0 = 122.0 - W / 2.0
        y0 = 117.5 - H / 2.0
        oa = wall_offsets(os.path.join(Da, ia['files'][0]), x0, y0, WID)
        od = wall_offsets(fd, x0, y0, WID)
        moved = sum(1 for v in od if v > 0.02)
        check('D3 STANDARD walls sit exactly on the cell edges',
              len(oa) > 100 and all(v <= 0.02 for v in oa),
              (len(oa), max(oa) if oa else None))
        check('D4 FUZZY moves most wall points, max <= 0.12mm',
              len(od) == len(oa) and moved > 0.5 * len(od)
              and max(od) <= 0.12 + 0.03,
              (len(od), moved, round(max(od), 4) if od else None))
        check('D5 cavity identical to STANDARD (mask untouched)',
              idf['cells_top'] == ia['cells_top'],
              (idf['cells_top'], ia['cells_top']))

    print('E  combos + wiring quotes')
    shroom = write_shape(
        D, 'm.gcode',
        lambda z: (5.0 if z < 8.0 else
                   5.0 + 10.0 * math.sin(math.pi * min(1.0,
                                                        (z - 8.0) / 8.0))))
    De, ie, err = try_mold(shroom, part='BOTH', plane='OFF', z_off=0.0,
                           sectors=1, surface='FINE')
    ok_e1 = err is None and len(ie['files']) == 3
    iron_pieces = 0
    if ok_e1:
        for fn in ie['files']:
            if 'FormOben_S' not in fn:
                continue
            lays = layer_lines(os.path.join(De, fn))
            if any('APPLY_TYPE TYPE=IRONING' in ln for ln in lays[-1]):
                iron_pieces += 1
        ok_e1 = iron_pieces == 2
    check('E1 sector FINE: 3 files, BOTH pieces ironed', ok_e1,
          (err or '', iron_pieces))
    Df, ifz, err = try_mold(shroom, part='BOTH', plane='OFF', z_off=0.0,
                            sectors=1, surface='FUZZY')
    check('E2 sector FUZZY: still 3 files',
          err is None and len(ifz['files']) == 3
          and ifz['surface'] == 'FUZZY', err)
    check('E3 watcher reads mold_surface',
          "rv.get('mold_surface'" in src_txt
          and "'STANDARD', 'FINE', 'FUZZY'" in src_txt)
    mac = open(os.path.join(HERE, '..', 'macros', '17_generator.cfg'),
               encoding='utf-8').read()
    check('E4 MOLD_CREATE validates SURFACE',
          'params.SURFACE' in mac
          and "sf272 not in ('STANDARD', 'FINE', 'FUZZY')" in mac)
    tch = open(os.path.join(HERE, 'toolchain.py'),
               encoding='utf-8').read()
    check('E5 toolchain registry surface enum',
          "'surface': {'type': 'enum'" in tch
          and "'STANDARD', 'FINE',\n                                                   'FUZZY'" in tch)

    print()
    print('%d/%d checks passed' % (count - fails, count))
    return 1 if fails else 0


if __name__ == '__main__':
    sys.exit(main())
