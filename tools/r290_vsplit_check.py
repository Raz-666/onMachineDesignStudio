#!/usr/bin/env python3
"""R290 field check: the VSPLIT standing-mold family - measured, not
assumed. The vertical side-split mold (layout=AUTO/VSPLIT/FLAT):

  CYLINDER r=12, 80 bands  -> AUTO chooses VSPLIT (x-monotone body)
  DUMBBELL (two r=8 lobes, 24mm apart in x) -> hooked silhouette:
       AUTO falls back to FLAT (honest note), VSPLIT refuses clean
  part=TOP / sectors / pocket / master under AUTO -> flat features,
       routed to the flat mold automatically (the tool decides)
  THIN plate (x_span < 6mm) -> AUTO falls back, VSPLIT explains

Checks:
  A  routing: AUTO->VSPLIT on the cylinder, forced VSPLIT, the exact
     two-plate file set (FormLinks + FormRechts), no fallback note
  B  layer math: plate layers == F + slabs per side (from the G-code)
  C  G-code truth: pour channel open at the TOP edge of the parting
     face, sprue at the plate top, 4 dowel discs empty
  D  refusals & fallbacks: dumbbell (hook), thin plate, part=TOP,
     sectors=1, master=True - AUTO always lands on its feet, forced
     VSPLIT refuses with the reason and leaves NO files
  E  release window math: the split x sits inside [x_min+2lh,
     x_max-2lh]; MID pins the middle, OFF honors z_off (x axis)
  F  determinism: a rerun is byte-identical
"""
import math
import os
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import r2_postproc as pp  # noqa: E402

LH = 0.2
fails = 0
count = 0


def check(name, ok, info=''):
    global fails, count
    count += 1
    print(('  ok   ' if ok else '  FAIL ') + name)
    if not ok:
        fails += 1
        print('      -> %s' % str(info)[:240])


def write_cyl(D, name, r=12.0, n_lay=80, cx=60.0, cy=60.0):
    src = os.path.join(D, name)
    with open(src, 'w') as f:
        f.write(';TYPE:Outer wall\nM82\nG90\n')
        e = 0.0
        for li in range(1, n_lay + 1):
            z = round(li * LH, 3)
            pts = [(cx + r * math.cos(a), cy + r * math.sin(a))
                   for a in [i * math.pi / 36 for i in range(73)]]
            f.write(';LAYER_CHANGE\nG1 Z%.3f F600\n' % z)
            px, py = pts[0]
            f.write('G0 X%.3f Y%.3f F3000\n' % (px, py))
            for (qx, qy) in pts[1:]:
                e += math.hypot(qx - px, qy - py) * 0.05
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


def write_dumbbell(D, name, r=8.0, n_lay=60, cy=60.0, cxs=(50.0, 74.0)):
    src = os.path.join(D, name)
    with open(src, 'w') as f:
        f.write(';TYPE:Outer wall\nM82\nG90\n')
        e = 0.0
        for li in range(1, n_lay + 1):
            z = round(li * LH, 3)
            f.write(';LAYER_CHANGE\nG1 Z%.3f F600\n' % z)
            for cx in cxs:
                pts = [(cx + r * math.cos(a), cy + r * math.sin(a))
                       for a in [i * math.pi / 36 for i in range(73)]]
                px, py = pts[0]
                f.write('G0 X%.3f Y%.3f F3000\n' % (px, py))
                for (qx, qy) in pts[1:]:
                    e += math.hypot(qx - px, qy - py) * 0.05
                    f.write('G1 X%.3f Y%.3f E%.5f F1200\n' % (qx, qy, e))
                    px, py = qx, qy
    return src


def layer_points(path):
    """[ [(x, y), ...], ... ] - extrusion endpoints per layer."""
    layers = []
    cur = None
    x = y = 0.0
    with open(path) as f:
        for ln in f:
            if ln.startswith(';LAYER_CHANGE'):
                cur = []
                layers.append(cur)
                continue
            code = ln.split(';', 1)[0].strip()
            if not code:
                continue
            parts = code.split()
            cmd0 = parts[0].upper()
            prm = {}
            for tok in parts[1:]:
                try:
                    prm[tok[0].upper()] = float(tok[1:])
                except (ValueError, IndexError):
                    pass
            if cmd0 in ('G0', 'G1'):
                nx = prm.get('X', x)
                ny = prm.get('Y', y)
                if 'E' in prm and prm['E'] > 0 and cur is not None:
                    cur.append((nx, ny))
                x, y = nx, ny
    return layers


def main():
    D = tempfile.mkdtemp(prefix='r290_')
    cyl = write_cyl(D, 'cyl.gcode')
    dumb = write_dumbbell(D, 'dumb.gcode')

    # ---- A: routing ------------------------------------------------
    out1 = os.path.join(D, 'm1')
    os.mkdir(out1)
    p1, info1 = pp.make_mold(cyl, out_dir=out1, layout='AUTO')
    check('A1 AUTO chooses VSPLIT on a standing cylinder',
          info1.get('layout') == 'VSPLIT', info1.get('layout'))
    check('A2 the file set is exactly the two side plates',
          len(info1['files']) == 2
          and any('FormLinks' in x for x in info1['files'])
          and any('FormRechts' in x for x in info1['files']),
          info1['files'])
    check('A3 a clean VSPLIT carries no fallback note',
          not any('no vertical side split' in n for n in info1['notes']),
          info1['notes'])
    out2 = os.path.join(D, 'm2')
    os.mkdir(out2)
    p2, info2 = pp.make_mold(cyl, out_dir=out2, layout='VSPLIT')
    check('A4 forced VSPLIT works', info2.get('layout') == 'VSPLIT')
    check('A5 FLAT pins the classic mold',
          pp.make_mold(cyl, out_dir=os.path.join(D, 'm2b')
                       if not os.mkdir(os.path.join(D, 'm2b')) else None,
                       layout='FLAT')[1].get('layout') == 'FLAT')

    # ---- B: layer math ----------------------------------------------
    lay = layer_points(p1)
    check('B1 left plate layers == F + p slabs (from the G-code)',
          len(lay) == info1['layers_left'],
          (len(lay), info1['layers_left']))
    right_path = os.path.join(out1, [f for f in info1['files']
                                     if 'FormRechts' in f][0])
    lay_r = layer_points(right_path)
    check('B2 right plate layers == F + (K-p) slabs',
          len(lay_r) == info1['layers_right'],
          (len(lay_r), info1['layers_right']))

    # ---- C: G-code truth ---------------------------------------------
    sx, sy = info1['sprue']
    last = lay[-1]
    near = [pt for pt in last
            if abs(pt[0] - sx) < 3.0 and pt[1] > sy - 12.0]
    check('C1 pour channel open at the top edge on the parting face',
          len(near) == 0, (sx, sy, near[:3]))
    check('C2 the sprue sits at the top edge of the plate',
          sy > info1['block'][1] * 0.9, (sx, sy, info1['block']))
    pins_ok = True
    for (px, py) in info1['pins']:
        for pt in last:
            if math.hypot(pt[0] - px, pt[1] - py) < 1.2:
                pins_ok = False
                break
        if not pins_ok:
            break
    check('C3 the 4 dowel discs are empty on the parting face', pins_ok)
    check('C4 vents carry D%.1f channel positions at the top edge'
          % info1['vent_d'],
          all(abs(vy - sy) < 1.0 for (_vx, vy) in info1['vents'])
          if info1['vents'] else True)

    # ---- D: refusals & fallbacks --------------------------------------
    out3 = os.path.join(D, 'm3')
    os.mkdir(out3)
    _p3, info3 = pp.make_mold(dumb, out_dir=out3, layout='AUTO')
    check('D1 hooked silhouette: AUTO falls back to FLAT',
          info3.get('layout') == 'FLAT', info3.get('layout'))
    check('D2 the fallback carries the honest refusal note',
          any('no vertical side split' in n for n in info3['notes']),
          info3['notes'])
    out4 = os.path.join(D, 'm4')
    os.mkdir(out4)
    try:
        pp.make_mold(dumb, out_dir=out4, layout='VSPLIT')
        check('D3 forced VSPLIT on a hooked silhouette refuses', False,
              'no error')
    except ValueError as ex:
        check('D3 forced VSPLIT on a hooked silhouette refuses',
              'vertical mold refused' in str(ex), str(ex)[:120])
    check('D4 a refusal leaves no files behind',
          os.listdir(out4) == [], os.listdir(out4))
    out5 = os.path.join(D, 'm5')
    os.mkdir(out5)
    _p5, info5 = pp.make_mold(cyl, out_dir=out5, layout='AUTO', part='TOP')
    check('D5 part=TOP routes AUTO to the flat mold',
          info5.get('layout') == 'FLAT', info5.get('layout'))
    out6 = os.path.join(D, 'm6')
    os.mkdir(out6)
    _p6, info6 = pp.make_mold(cyl, out_dir=out6, layout='AUTO', sectors=1)
    check('D6 sectors route AUTO to the flat mold (its undercut answer)',
          info6.get('layout') == 'FLAT' and info6.get('sectors') == 1,
          (info6.get('layout'), info6.get('sectors')))
    out7 = os.path.join(D, 'm7')
    os.mkdir(out7)
    _p7, info7 = pp.make_mold(cyl, out_dir=out7, layout='AUTO',
                              master=True)
    check('D7 master=True routes AUTO to the flat layout',
          info7.get('layout') == 'FLAT', info7.get('layout'))
    thin = os.path.join(D, 'lens.gcode')
    with open(thin, 'w') as f:
        f.write(';TYPE:Outer wall\nM82\nG90\n')
        e = 0.0
        for li in range(1, 61):
            z = round(li * LH, 3)
            pts = [(60.0 + 1.2 * math.cos(a), 60.0 + 12.0 * math.sin(a))
                   for a in [i * math.pi / 36 for i in range(73)]]
            f.write(';LAYER_CHANGE\nG1 Z%.3f F600\n' % z)
            px, py = pts[0]
            f.write('G0 X%.3f Y%.3f F3000\n' % (px, py))
            for (qx, qy) in pts[1:]:
                e += math.hypot(qx - px, qy - py) * 0.05
                f.write('G1 X%.3f Y%.3f E%.5f F1200\n' % (qx, qy, e))
                px, py = qx, qy
    out8 = os.path.join(D, 'm8')
    os.mkdir(out8)
    try:
        pp.make_mold(thin, out_dir=out8, layout='VSPLIT')
        check('D8 thin plate (x<6mm): forced VSPLIT refuses', False,
              'no error')
    except ValueError as ex:
        check('D8 thin plate (x<6mm): forced VSPLIT refuses',
              'thick in X' in str(ex), str(ex)[:120])
    out8b = os.path.join(D, 'm8b')
    os.mkdir(out8b)
    _p8, info8 = pp.make_mold(thin, out_dir=out8b, layout='AUTO')
    check('D8b thin plate: AUTO falls back to the flat mold',
          info8.get('layout') == 'FLAT', info8.get('layout'))

    # ---- E: release window math ---------------------------------------
    check('E1 the split x sits inside the object x span',
          60.0 - 12.0 < info1['x_part'] < 60.0 + 12.0, info1['x_part'])
    out9 = os.path.join(D, 'm9')
    os.mkdir(out9)
    _p9, info9 = pp.make_mold(cyl, out_dir=out9, layout='VSPLIT',
                              plane='MID')
    check('E2 plane=MID pins the x middle',
          abs(info9['x_part'] - 60.0) < 0.6, info9['x_part'])
    out10 = os.path.join(D, 'm10')
    os.mkdir(out10)
    _p10, info10 = pp.make_mold(cyl, out_dir=out10, layout='VSPLIT',
                                plane='OFF', z_off=11.0)
    check('E3 plane=OFF honors z_off as the x offset (inside the '
          'release window)',
          abs(info10['x_part'] - (60.0 - 12.0 + 11.0)) < 0.6,
          info10['x_part'])
    out11 = os.path.join(D, 'm11')
    os.mkdir(out11)
    try:
        pp.make_mold(cyl, out_dir=out11, layout='VSPLIT',
                     plane='OFF', z_off=2.0)
        check('E4 OFF outside the release window refuses with the '
              'window in the message', False, 'no error')
    except ValueError as ex:
        check('E4 OFF outside the release window refuses with the '
              'window in the message',
              'release window' in str(ex), str(ex)[:120])

    # ---- F: determinism ------------------------------------------------
    da = os.path.join(D, 'ma')
    os.mkdir(da)
    pa, _ia = pp.make_mold(cyl, out_dir=da, layout='VSPLIT')
    db = os.path.join(D, 'mb')
    os.mkdir(db)
    pb, _ib = pp.make_mold(cyl, out_dir=db, layout='VSPLIT')
    check('F1 a rerun is byte-identical',
          open(pa, 'rb').read() == open(pb, 'rb').read())

    print('R290 VSPLIT check: %d checks, %d FAIL' % (count, fails))
    return 1 if fails else 0


if __name__ == '__main__':
    sys.exit(main())
