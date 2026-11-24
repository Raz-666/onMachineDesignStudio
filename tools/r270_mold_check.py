#!/usr/bin/env python3
"""R270 field check: the CASTING-MOLD generator (J2 bite 1) - measured,
not assumed.

Synthetic sources (all written by this battery, layer 0.2, 100 bands,
20mm tall, wall+cross extrusion per band):
  BOULDER  r = 6 + 9*sin(pi*z/20)   - widest (r=15) exactly at z=10
  CYLINDER r = 15                   - flat wide top (vents must fit)
  CONE     r = 15 -> 8              - equator at the foot
  MUSHROOM stem r=5 to z=8, cap 5+10*sin - AUTO finds the cap equator,
           a forced FOOT plane has a real undercut

Checks:
  A  generation: BOTH+master = 3 files, part selection TOP/BOTTOM = 1
  B  layer math: floor/cavity/back/ceiling counts analytic, TOTAL_LAYERS
     in _FILE_INFO == ;LAYER_CHANGE count == LAYER_MARK count
  C  split plane: AUTO equator == the widest band (boulder z=10), MID and
     OFFSET land where the band math says
  D  cavity truth from the G-CODE: the parting layer of the bottom half
     has NO extrusion inside the widest section (+gap) and material in
     the frame ring; the top half's back opens the pour channel; the
     first cavity layer connects it
  E  dowel registry: 4 holes at the SAME bed position in both halves'
     parting layers (empty discs), centered in the frame band
  F  vent honesty: boulder -> 0 vents + the honest note (top too small);
     cylinder -> >= 2 vents, open at the back layer
  G  draft & gap evidence: cells_top shrinks with draft, grows with the
     tolerance gap (direct cavity-cell counters)
  H  master: layer count analytic, mid-layer material bbox == the shape
  I  refusals: undercut (fresh dir stays EMPTY - all-or-nothing), bed
     too small, bad part value; determinism: rerun byte-identical
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


def layer_points(path):
    """[(z, [(x, y), ...]), ...] - one entry per ;LAYER_CHANGE, extrusion
    end points only."""
    layers = []
    cur = None
    x = y = z = 0.0
    for ln in open(path, errors='replace'):
        if ln.startswith(';Z:'):
            z = float(ln[3:])
        elif ln.startswith(';LAYER_CHANGE'):
            cur = []
            layers.append((z, cur))
        else:
            code = ln.split(';', 1)[0].strip()
            parts = code.split()
            if parts and parts[0] in ('G0', 'G1'):
                p = pp.parse_params(code[2:])
                if 'X' in p:
                    x = p['X']
                if 'Y' in p:
                    y = p['Y']
                if parts[0] == 'G1' and 'E' in p and ('X' in p or 'Y' in p):
                    cur.append((x, y))
    return layers


def min_dist(pts, cx, cy):
    return min((math.hypot(px - cx, py - cy) for (px, py) in pts),
               default=1e9)


def main():
    D = tempfile.mkdtemp(prefix='r270mold_')
    boulder = write_shape(D, 'boulder.gcode',
                          lambda z: 6.0 + 9.0 * math.sin(math.pi * z / 20.0))
    cylinder = write_shape(D, 'cyl.gcode', lambda z: 15.0)
    cone = write_shape(D, 'cone.gcode', lambda z: 15.0 - 7.0 * (z / 20.0))
    mushroom = write_shape(
        D, 'shroom.gcode',
        lambda z: (5.0 if z < 8.0 else
                   5.0 + 10.0 * math.sin(math.pi * min(1.0, (z - 8.0) / 8.0))))

    # ---- A/B/C: the boulder set ------------------------------------------------
    out, info = pp.make_mold(boulder, layout='FLAT', wall=5.0, part='BOTH', master=True,
                             out_dir=D, layer_h=LH, gap=0.15)
    check('A1 generation: BOTH + master = 3 files (Unten, Oben, Master)',
          len(info['files']) == 3 and
          any('FormUnten' in f for f in info['files']) and
          any('FormOben' in f for f in info['files']) and
          any('Master' in f for f in info['files']), info['files'])
    F = max(2, int(round(5.0 / LH)))
    K_b = max(1, int(math.ceil((info['z_p'] - 0.2) / LH)))
    K_t = max(1, int(math.ceil((20.0 - info['z_p']) / LH)))
    check('B1 layer math bottom: floor %d + cavity %d = %d'
          % (F, K_b, F + K_b),
          info['layers_bot'] == F + K_b, info['layers_bot'])
    check('B2 layer math top: back %d + cavity %d = %d' % (F, K_t, F + K_t),
          info['layers_top'] == F + K_t, info['layers_top'])

    gbot = layer_points(os.path.join(D, info['files'][1]))
    gtop = layer_points(os.path.join(D, info['files'][2]))
    gmas = layer_points(os.path.join(D, info['files'][0]))
    check('B3 gcode layer counts == analytic (bot/top/master)',
          len(gbot) == F + K_b and len(gtop) == F + K_t and
          len(gmas) == max(2, int(math.ceil((20.0 - 0.2 + LH) / LH))),
          (len(gbot), len(gtop), len(gmas)))
    for (fn, lays) in ((info['files'][1], gbot), (info['files'][2], gtop)):
        txt = open(os.path.join(D, fn)).read()
        tl = int(pp.re.search(r'TOTAL_LAYERS=(\d+)', txt).group(1))
        check('B4 %s: _FILE_INFO TOTAL_LAYERS == layers == LAYER_MARKs' % fn,
              tl == len(lays) and txt.count('LAYER_MARK') == len(lays) and
              txt.count(';LAYER_CHANGE') == len(lays), (tl, len(lays)))
        check('B5 %s: PRINT_START/PRINT_END, G90/M83, EXCLUDE_OBJECT' % fn,
              'PRINT_START' in txt and 'PRINT_END' in txt and
              '\nG90\n' in txt and '\nM83\n' in txt and
              'EXCLUDE_OBJECT_DEFINE' in txt, '')

    W, H = info['block']
    cols = int(math.ceil((30.0 + 2 * 5.0) / WID))
    check('A2 block = source bbox + 2*wall, cell-rounded (%.1f x %.1f)'
          % (cols * WID, cols * WID),
          abs(W - cols * WID) < 0.01 and abs(H - cols * WID) < 0.01 and
          info['grid'] == (cols, cols), (W, H, info['grid']))

    check('C1 AUTO equator lands on the widest band (z=10.0)',
          abs(info['z_p'] - 10.0) < 0.25 and
          info['split'].startswith('AUTO'), info['split'])

    _, i_mid = pp.make_mold(cone, layout='FLAT', wall=5.0, part='TOP', out_dir=D,
                            plane='MID')
    check('C2 MID plane at band 50 of 100 (z=10.0)',
          i_mid['split'].startswith('MID') and abs(i_mid['z_p'] - 10.0)
          < 0.25, i_mid['split'])
    _, i_off = pp.make_mold(cone, layout='FLAT', wall=5.0, part='TOP', out_dir=D,
                            plane='OFF', z_off=5.0)
    check('C3 OFFSET plane 5mm above the foot (z=5.2)',
          'OFFSET' in i_off['split'] and abs(i_off['z_p'] - 5.2) < 0.21,
          i_off['split'])

    # ---- D: cavity truth from the gcode ---------------------------------------
    ax = info['block'][0] / 2.0 + (244.0 - 12.0) / 2.0 + 6.0   # block center
    # (bed usable x0..x1 = 6..238, centered -> center = (6+238)/2 = 122)
    ax = (6.0 + 238.0) / 2.0
    ay = (-3.0 + 12.0 + 238.0 - 12.0) / 2.0                    # = 117.5
    z_pt, pts_pt = gbot[-1]            # parting layer of the bottom half
    r_max = 15.0 + 0.15                # widest section + tolerance gap
    check('D1 bottom parting layer: cavity EMPTY inside r=%.2f (min extr '
          'dist %.2f)' % (r_max - WID, min_dist(pts_pt, ax, ay)),
          min_dist(pts_pt, ax, ay) > r_max - WID,
          min_dist(pts_pt, ax, ay))
    ring = [d for (px, py) in pts_pt
            for d in [math.hypot(px - ax, py - ay)]
            if d < r_max + 5.0 + WID]
    check('D2 bottom parting layer: material IN the frame ring', len(ring)
          >= 50, len(ring))

    z_b1, pts_b1 = gtop[0]            # back layer of the top half
    sx, sy = info['sprue']
    check('D3 top back layer: pour channel open (min dist %.2f >= %.2f, '
          'funnel mouth in layer 1)'
          % (min_dist(pts_b1, sx, sy), 8.0 / 2.0 - WID),
          min_dist(pts_b1, sx, sy) >= 8.0 / 2.0 - WID,
          min_dist(pts_b1, sx, sy))
    check('D4 top back layer: material AROUND the channel', len(pts_b1)
          > 100, len(pts_b1))
    F_cav = F + 1                      # first cavity layer index (1-based)
    z_c1, pts_c1 = gtop[F]
    check('D5 first cavity layer: sprue CONNECTED (channel open into '
          'the cavity)',
          min_dist(pts_c1, sx, sy) >= 8.0 / 2.0 - WID,
          min_dist(pts_c1, sx, sy))

    # ---- E: dowel registry -----------------------------------------------------
    # a D3 dowel must FIT: the hole's inscribed radius >= pin radius
    # (the snapped disc guarantees hole_rc - 0.5 cells; walls hug it)
    ok_pins = True
    pin_detail = []
    _hr270 = 3.0 / 2.0 + 0.3
    for (pc, pr) in info['pins']:
        for (lays, tag) in ((gbot, 'bot'), (gtop, 'top')):
            d = min_dist(lays[-1][1], pc, pr)
            pin_detail.append('%s=%.2f' % (tag, d))
            if d < _hr270 - 0.7 * WID:
                ok_pins = False
    check('E1 4 dowel holes at the SAME bed position in both parting '
          'layers (empty discs) [%s]' % ' '.join(pin_detail[:4]),
          ok_pins, pin_detail)
    # centered in the frame band: distance from the block edge ~ wall/2
    bx0 = 122.0 - W / 2.0
    by0 = 117.5 - H / 2.0
    edge_ok = all(abs(min(pc - bx0, bx0 + W - pc) - 5.0 / 2.0) < 0.8
                  and abs(min(pr - by0, by0 + H - pr) - 5.0 / 2.0) < 0.8
                  for (pc, pr) in info['pins'])
    check('E2 dowel holes centered in the frame band (~wall/2 from the '
          'edge)', edge_ok, info['pins'])

    # ---- F: vent honesty --------------------------------------------------------
    check('F1 boulder: no vent bores + the honest note (top too small)',
          len(info['vents']) == 0 and
          any('no vent bores' in n for n in info['notes']),
          info['notes'])
    _, ic = pp.make_mold(cylinder, layout='FLAT', wall=5.0, part='TOP', out_dir=D)
    check('F2 cylinder: >= 2 vent bores at the far high spots',
          len(ic['vents']) >= 2, ic['vents'])
    z_cb1, pts_cb1 = layer_points(
        os.path.join(D, ic['files'][0]))[0]
    vok = all(min_dist(pts_cb1, vx, vy) >= 2.5 / 2.0 - 0.7 * WID
              for (vx, vy) in ic['vents'])
    check('F3 cylinder: vent bores OPEN in the back layer', vok,
          ic['vents'])

    # ---- G: draft & gap evidence -------------------------------------------------
    # draft needs DEPTH: the cylinder's AUTO split degenerates to the top
    # band (equal bead lengths tie -> highest) - the boulder carries a
    # real 50-layer top half whose deep layers erode by 1-2 cells
    _, i_d0 = pp.make_mold(boulder, layout='FLAT', wall=5.0, part='TOP', out_dir=D,
                           draft=0.0)
    _, i_d3 = pp.make_mold(boulder, layout='FLAT', wall=5.0, part='TOP', out_dir=D,
                           draft=3.0)
    check('G1 draft erodes the cavity: cells %d -> %d (top half depth '
          '%.1fmm)' % (i_d3['cells_top'], i_d0['cells_top'],
                       i_d0['layers_top'] * LH),
          i_d3['cells_top'] < i_d0['cells_top'],
          (i_d0['cells_top'], i_d3['cells_top']))
    _, i_gw = pp.make_mold(cylinder, layout='FLAT', wall=5.0, part='TOP', out_dir=D,
                           gap=0.30)
    _, i_gn = pp.make_mold(cylinder, layout='FLAT', wall=5.0, part='TOP', out_dir=D,
                           gap=0.05)
    check('G2 tolerance gap grows the cavity: cells %d -> %d'
          % (i_gn['cells_top'], i_gw['cells_top']),
          i_gw['cells_top'] > i_gn['cells_top'],
          (i_gn['cells_top'], i_gw['cells_top']))

    # ---- H: master ----------------------------------------------------------------
    K_m = max(2, int(math.ceil((20.0 - 0.2 + LH) / LH)))
    check('H1 master layer count == analytic (%d)' % K_m, len(gmas) == K_m,
          len(gmas))
    z_m50, pts_m50 = gmas[K_m // 2]
    r50 = 6.0 + 9.0 * math.sin(math.pi * (z_m50) / 20.0)
    xs = [p[0] for p in pts_m50]
    ys = [p[1] for p in pts_m50]
    w50 = max(xs) - min(xs)
    check('H2 master mid layer bbox ~ the shape (%.1fmm vs %.1f)'
          % (w50, 2 * r50), abs(w50 - 2 * r50) < 1.6, (w50, 2 * r50))

    # ---- I: refusals + determinism ---------------------------------------------------
    _, i_sh = pp.make_mold(mushroom, layout='FLAT', wall=5.0, part='BOTH', out_dir=D)
    check('I1 mushroom AUTO finds the cap equator (no undercut)',
          abs(i_sh['z_p'] - 12.0) < 0.25, i_sh['split'])
    D2 = tempfile.mkdtemp(prefix='r270bad_')
    try:
        pp.make_mold(mushroom, layout='FLAT', wall=5.0, part='BOTH', master=True,
                     out_dir=D2, plane='OFF', z_off=0.0)
        check('I2 forced foot plane refuses (undercut)', False, 'no raise')
    except ValueError as ex:
        check('I2 forced foot plane refuses (undercut)',
              'UNDERCUT in the top half' in str(ex), str(ex)[:90])
    check('I3 all-or-nothing: the refused set leaves NOTHING behind',
          os.listdir(D2) == [], os.listdir(D2))
    huge = write_shape(D2 if False else D, 'huge.gcode', lambda z: 115.0,
                       cx=120.0, cy=120.0)
    try:
        pp.make_mold(huge, layout='FLAT', wall=15.0, part='TOP', out_dir=D)
        check('I4 bed refusal (block > bed)', False, 'no raise')
    except ValueError as ex:
        check('I4 bed refusal (block > bed)', 'mold block needs' in str(ex),
              str(ex)[:90])
    try:
        pp.make_mold(boulder, layout='FLAT', part='QUER', out_dir=D)
        check('I5 bad part value refuses', False, 'no raise')
    except ValueError as ex:
        check('I5 bad part value refuses',
              "part must be BOTH, TOP or BOTTOM" in str(ex), str(ex)[:60])
    try:
        pp.make_mold(boulder, layout='FLAT', wall=5.0, pin_d=6.0, part='TOP', out_dir=D)
        check('I6 dowel-vs-wall validation refuses (D6 in a 5mm wall)',
              False, 'no raise')
    except ValueError as ex:
        check('I6 dowel-vs-wall validation refuses (D6 in a 5mm wall)',
              'do not fit the wall' in str(ex), str(ex)[:80])
    d1 = tempfile.mkdtemp(prefix='r270d1_')
    d2 = tempfile.mkdtemp(prefix='r270d2_')
    _, i_first = pp.make_mold(boulder, layout='FLAT', wall=5.0, part='BOTTOM', out_dir=d1)
    _, i_rerun = pp.make_mold(boulder, layout='FLAT', wall=5.0, part='BOTTOM', out_dir=d2)
    check('I7 determinism: rerun byte-identical',
          open(os.path.join(d1, i_first['files'][0]), 'rb').read()
          == open(os.path.join(d2, i_rerun['files'][0]), 'rb').read(),
          (i_first['files'][0], i_rerun['files'][0]))

    print()
    print('R270 MOLD CHECK: %d checks, %d failed' % (count, fails))
    return 1 if fails else 0


if __name__ == '__main__':
    sys.exit(main())
