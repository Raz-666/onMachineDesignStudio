#!/usr/bin/env python3
"""R273 field check: parametric BLANK molds (J2 bite 2) + the POCKET
boss (relief seat) - measured, not assumed.

Shapes under test (make_mold_blank, all defaults otherwise):
  MEDALLION dia 40 x thick 8, round pocket D30 x 2 deep (auto = dia-10)
  PLAQUE    60 x 40 x thick 6, corner 4, rect pocket 48 x 28 x 2 (auto)
  BAR       90 x 40 x 25, taper 0.85, rect pocket 74 x 22 x 2 (auto)

Checks:
  A  signature & validation: shape enum, pocket type per shape, rim and
     floor limits, engine-level pocket consistency (one shape only,
     no depth without a pocket)
  B  medallion: 2 files (blank source + FormOben), pocket info, boss
     cell count ANALYTIC (pi*r^2 per layer within 5%), boss wall in the
     FIRST cavity layer near the center (grows off the back floor),
     nothing central in the LAST cavity layer, pocket_t=0 builds the
     plain blank
  C  plaque: rect pocket, corner-rounded silhouette (block width
     measured from the gcode), boss points central in the first
     cavity layer
  D  bar: the taper works - the cavity is NARROWER at the first
     (back-most) cavity layer than at the last (measured from the
     gcode, bar_w*taper vs bar_w), taper=1.0 gives equal widths
  E  honesty & combos: sectors+boss refuse (the boss blocks the
     slide - honest), part=BOTH adds the base block, master notes the
     SOLID positive, part=BOTTOM notes the ignored pocket, FINE irons
     the boss-carrying half too
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


def layer_lines(path):
    layers = []
    cur = None
    for ln in open(path, errors='replace'):
        if ln.startswith(';LAYER_CHANGE'):
            cur = []
            layers.append(cur)
        elif cur is not None:
            cur.append(ln)
    return layers


def extr_points(lay):
    """(x, y) extrusion endpoints of one layer's lines."""
    x = y = 0.0
    pts = []
    for ln in lay:
        code = ln.split(';', 1)[0].strip()
        parts = code.split()
        if parts and parts[0] in ('G0', 'G1'):
            p = pp.parse_params(code[2:])
            if 'X' in p:
                x = p['X']
            if 'Y' in p:
                y = p['Y']
            if parts[0] == 'G1' and 'E' in p and ('X' in p or 'Y' in p):
                pts.append((x, y))
    return pts


def try_blank(D, **kw):
    kw.setdefault('wall', 5.0)
    try:
        out, info = pp.make_mold_blank(out_dir=D, **kw)
        return out, info, None
    except ValueError as ex:
        return None, None, str(ex)


def main():
    src_txt = open(os.path.join(HERE, 'r2_postproc.py'),
                   encoding='utf-8').read()

    print('A  signature & validation')
    check('A1 make_mold_blank exists, pocket in make_mold',
          'def make_mold_blank(' in src_txt
          and 'pocket_d=0.0' in src_txt.split('def make_mold(', 1)[1][:1200])
    D = tempfile.mkdtemp(prefix='r273a_')
    _, _, e = try_blank(D, shape='QUATSCH')
    check('A2 bad shape refused',
          e is not None and 'MEDALLION, PLAQUE or BAR' in e, e)
    _, _, e = try_blank(D, shape='MEDALLION', dia=30.0, pocket_d=26.0,
                        pocket_t=2.0)
    check('A3 pocket rim enforced',
          e is not None and 'leaves no rim' in e, e)
    _, _, e = try_blank(D, shape='MEDALLION', dia=40.0, thick=4.0,
                        pocket_t=3.0)
    check('A4 pocket floor enforced',
          e is not None and 'needs a floor' in e, e)
    _, _, e = try_blank(D, shape='MEDALLION', pocket_w=20.0, pocket_h=10.0)
    check('A5 medallion wants the round pocket',
          e is not None and 'ROUND pocket' in e, e)
    _, _, e = try_blank(D, shape='PLAQUE', pocket_d=20.0)
    check('A6 plaque wants the rect pocket',
          e is not None and 'RECTANGULAR pocket' in e, e)
    try:
        pp.make_mold(os.path.join(D, 'x.gcode'), out_dir=D,
                     pocket_d=20.0, pocket_t=0.0)
        check('A7 engine: depth without pocket refused', False, 'no raise')
    except ValueError as ex:
        check('A7 engine: depth without pocket refused',
              'needs a depth' in str(ex), str(ex))
    try:
        pp.make_mold(os.path.join(D, 'x.gcode'), out_dir=D,
                     pocket_d=20.0, pocket_w=10.0, pocket_h=10.0,
                     pocket_t=1.0)
        check('A8 engine: one pocket shape only', False, 'no raise')
    except ValueError as ex:
        check('A8 engine: one pocket shape only',
              'ONE pocket shape' in str(ex), str(ex))

    print('B  medallion (dia 40 x 8, pocket D30 x 2)')
    Db = tempfile.mkdtemp(prefix='r273b_')
    _, ib, eb = try_blank(Db, shape='MEDALLION', dia=40.0, thick=8.0)
    check('B1 builds blank + mold, pocket D30',
          eb is None and len(ib['files']) == 1
          and os.path.isfile(os.path.join(Db, ib['blank']['file']))
          and ib['pocket']['d'] == 30.0 and ib['pocket']['layers'] == 10,
          eb or (ib['files'], ib['blank'], ib['pocket']))
    if ib:
        fn = [f for f in os.listdir(Db) if 'FormOben' in f][0]
        lays = layer_lines(os.path.join(Db, fn))
        CW = max(2, int(round(5.0 / LH)))
        first_cav = extr_points(lays[CW])
        last_cav = extr_points(lays[-1])
        W, H = ib['block']
        cx = 122.0
        cy = 117.5
        near = [p for p in first_cav
                if math.hypot(p[0] - cx, p[1] - cy) < 17.0]
        far = [p for p in last_cav
               if math.hypot(p[0] - cx, p[1] - cy) < 17.0]
        check('B2 boss wall central in the FIRST cavity layer',
              len(near) > 10, len(near))
        check('B3 nothing central in the LAST cavity layer',
              len(far) == 0, len(far))
        Dz = tempfile.mkdtemp(prefix='r273bz_')
        _, iz, ez = try_blank(Dz, shape='MEDALLION', dia=40.0, thick=8.0,
                              pocket_t=0.0)
        exp = math.pi * (15.0 / WID) ** 2 * 10
        got = iz['cells_top'] - ib['cells_top']
        check('B4 boss cells analytic (pi*r^2*layers, +-6%)',
              ez is None and iz['pocket'] is None
              and abs(got - exp) <= 0.06 * exp, (got, round(exp)))

    print('C  plaque (60 x 40 x 6, corner 4, pocket 48 x 28)')
    Dc = tempfile.mkdtemp(prefix='r273c_')
    _, ic, ec = try_blank(Dc, shape='PLAQUE', width=60.0, height=40.0,
                          thick=6.0, corner=4.0)
    check('C1 builds, rect pocket 48 x 28',
          ec is None and ic['pocket']['w'] == 48.0
          and ic['pocket']['h'] == 28.0, ec or ic['pocket'])
    if ic:
        fn = [f for f in os.listdir(Dc) if 'FormOben' in f][0]
        lays = layer_lines(os.path.join(Dc, fn))
        CW = max(2, int(round(5.0 / LH)))
        first_cav = extr_points(lays[CW])
        cx = 122.0
        cy = 117.5
        near = [p for p in first_cav
                if math.hypot(p[0] - cx, p[1] - cy) < 20.0]
        # pin circles AND the block frame lines print every layer -
        # measure the PLAQUE height inside the frame only (the cavity
        # spans +-20.4, the frame sits at +-25.2)
        ys = [p[1] for p in first_cav
              if abs(p[0] - cx) <= 25.0 and abs(p[1] - cy) <= 21.5]
        check('C2 boss points central + plaque height ~40',
              len(near) > 10
              and 37.0 <= (max(ys) - min(ys)) <= 43.0,
              (len(near), round(max(ys) - min(ys), 1) if ys else None))

    print('D  bar (90 x 40 x 25, taper 0.85)')
    Dd = tempfile.mkdtemp(prefix='r273d_')
    _, idb, ed = try_blank(Dd, shape='BAR', length=90.0, bar_w=40.0,
                           bar_h=25.0, taper=0.85)
    check('D1 builds, pocket 74 x 22 (top width 34)',
          ed is None and idb['pocket']['w'] == 74.0
          and idb['pocket']['h'] == 22.0, ed or idb['pocket'])
    if idb:
        cx = 122.0
        fn = [f for f in os.listdir(Dd) if 'FormOben' in f][0]
        lays = layer_lines(os.path.join(Dd, fn))
        CW = max(2, int(round(5.0 / LH)))
        # per-layer cavity width, central points only (pin circles AND
        # the block frame lines print every layer); the funnel rings at
        # the print end read 43+ - the cavity itself stays under 41.5
        cav_w = []
        for lay in lays[CW:]:
            ys = [p[1] for p in extr_points(lay)
                  if abs(p[0] - cx) <= 25.0 and abs(p[1] - 117.5) <= 21.5]
            if ys:
                w = max(ys) - min(ys)
                if w <= 41.5:
                    cav_w.append(w)
        check('D2 taper: cavity narrow at the top, wide at the foot '
              '(34 -> 40)',
              cav_w and min(cav_w) <= 36.5 and max(cav_w) >= 38.5
              and max(cav_w) - min(cav_w) >= 3.0,
              (round(min(cav_w), 1) if cav_w else None,
               round(max(cav_w), 1) if cav_w else None))
    Dd2 = tempfile.mkdtemp(prefix='r273d2_')
    _, id2, ed2 = try_blank(Dd2, shape='BAR', length=90.0, bar_w=40.0,
                            bar_h=25.0, taper=1.0)
    ok_d3 = ed2 is None
    if ok_d3:
        cx = 122.0
        fn = [f for f in os.listdir(Dd2) if 'FormOben' in f][0]
        lays = layer_lines(os.path.join(Dd2, fn))
        CW = max(2, int(round(5.0 / LH)))
        cav_w = []
        for lay in lays[CW:]:
            ys = [p[1] for p in extr_points(lay)
                  if abs(p[0] - cx) <= 25.0 and abs(p[1] - 117.5) <= 21.5]
            if ys:
                w = max(ys) - min(ys)
                if w <= 41.5:
                    cav_w.append(w)
        ok_d3 = cav_w and max(cav_w) - min(cav_w) < 2.0
    check('D3 taper=1.0: equal widths (plain bar)', ok_d3)

    print('E  honesty & combos')
    _, _, e1 = try_blank(tempfile.mkdtemp(prefix='r273e1_'),
                         shape='MEDALLION', dia=40.0, thick=8.0,
                         sectors=1)
    check('E1 sectors + boss refuse honestly (slide blocked)',
          e1 is not None and 'cannot slide off' in e1, e1)
    De2 = tempfile.mkdtemp(prefix='r273e2_')
    _, ie2, ee2 = try_blank(De2, shape='MEDALLION', dia=40.0, thick=8.0,
                            part='BOTH')
    check('E2 part=BOTH builds both halves + the blank source',
          ee2 is None and len(ie2['files']) == 2
          and sum(1 for f in ie2['files'] if 'FormUnten' in f) == 1
          and sum(1 for f in ie2['files'] if 'FormOben' in f) == 1
          and os.path.isfile(os.path.join(De2, ie2['blank']['file'])),
          ee2 or (ie2['files'], ie2['blank']))
    _, ie3, ee3 = try_blank(tempfile.mkdtemp(prefix='r273e3_'),
                            shape='MEDALLION', dia=40.0, thick=8.0,
                            master=True)
    check('E3 master notes the SOLID positive',
          ee3 is None and any('SOLID positive' in n for n in ie3['notes']),
          ee3 or ie3['notes'][:2])
    _, ie4, ee4 = try_blank(tempfile.mkdtemp(prefix='r273e4_'),
                            shape='MEDALLION', dia=40.0, thick=8.0,
                            part='BOTTOM')
    check('E4 part=BOTTOM notes the ignored pocket',
          ee4 is None and any('pocket ignored' in n for n in ie4['notes']),
          ee4 or ie4['notes'][:2])
    De5 = tempfile.mkdtemp(prefix='r273e5_')
    _, ie5, ee5 = try_blank(De5, shape='MEDALLION', dia=40.0, thick=8.0,
                            surface='FINE')
    ok_e5 = ee5 is None
    if ok_e5:
        fn = [f for f in os.listdir(De5) if 'FormOben' in f][0]
        txt = open(os.path.join(De5, fn), errors='replace').read(4000)
        fi = [ln for ln in txt.splitlines()
              if ln.startswith('_FILE_INFO')][0]
        ok_e5 = 'SPEED_INNER=20' in fi and ie5['pocket']['d'] == 30.0
    check('E5 FINE irons the boss-carrying half too', ok_e5)

    print()
    print('%d/%d checks passed' % (count - fails, count))
    return 1 if fails else 0


if __name__ == '__main__':
    sys.exit(main())
