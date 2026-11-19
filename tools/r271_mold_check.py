#!/usr/bin/env python3
"""R271 field check: SECTOR molds - 3-part (1 sector cut) and 4-part
(2 cuts) - measured, not assumed.

Synthetic sources (layer 0.2, wall+cross extrusion per band):
  MUSHROOM  stem r=5 to z=8, cap 5+10*sin - top undercut, foot plane
  BOWL      r = 6+9*sin to z=16, then 4 - undercut BELOW the plane
  HOURGLASS r = 4+11*|z-10|/10 - undercut on BOTH sides of the middle
  TREE      rect cross-section: stem, wide collar, taper, head - the
            collar undercuts the top half; a second cut traps a middle
  DISC      stem, 70mm-wide 0.6mm disc, stem - a bridge beyond 25mm
  TWOBLOBS  two separate blobs - cut lands between them, the frame
            blocks the slide (honest refusal)
  BOULDER   r = 6+9*sin - no undercut anywhere (regression)

Checks:
  A  signature & validation: sectors/sec_half in the def line, clamp
     line in the source, bad sec_half refused, sectors=9 behaves as 2,
     sectors=-3 behaves as 0
  B  2-part regression: default call byte-identical to sectors=0,
     sec_half None, bridges None
  C  mushroom 3-part: 3 files (FormUnten + FormOben_S1/S2), AUTO cuts
     the TOP half, 1 cut on the X axis, bridge count + note, piece
     head says assemble ALL pieces, cells_top/layers_top equal to the
     unsectored run (the pieces reassemble to the same cavity)
  D  bowl: AUTO sectors the BOTTOM half; explicit BOTTOM agrees
  E  dowel tunnels: bore core empty over the tunnel span (5 layers),
     axis solid just outside the span, free height 3.4..7.0mm at both
     frame bands in both pieces
  F  piece geometry from the G-code: EXCLUDE polygon = the piece rect
     ending exactly at the cut, S1 body left of the cut, S2 body right,
     brim present beyond the cut face (piece-local, not block-wide)
  G  refusals: hourglass (both halves undercut), tree 4-part (middle
     must lift), twoblobs (slide blocked by the frame), disc (bridge
     span over 25mm) - each with the honest message
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


def write_rect_shape(D, name, xspan_fn, n_lay=100, ylo=42.0, yhi=58.0):
    """rect cross-section [xl(z), xr(z)] x [ylo, yhi] per band."""
    src = os.path.join(D, name)
    with open(src, 'w') as f:
        f.write(';TYPE:Outer wall\nM82\nG90\n')
        e = 0.0
        for li in range(1, n_lay + 1):
            z = round(li * LH, 3)
            xl, xr = xspan_fn(z)
            f.write(';LAYER_CHANGE\nG1 Z%.3f F600\n' % z)
            corners = [(xl, ylo), (xr, ylo), (xr, yhi), (xl, yhi),
                       (xl, ylo)]
            px, py = corners[0]
            f.write('G0 X%.3f Y%.3f F3000\n' % (px, py))
            for (qx, qy) in corners[1:]:
                d = math.hypot(qx - px, qy - py)
                e += d * 0.05
                f.write('G1 X%.3f Y%.3f E%.5f F1200\n' % (qx, qy, e))
                px, py = qx, qy
            for t in (-0.5, 0.0, 0.5):
                xm = (xl + xr) / 2.0 + t * (xr - xl) / 2.0
                f.write('G0 X%.3f Y%.3f F3000\n' % (xm, ylo))
                e += (yhi - ylo) * 0.05
                f.write('G1 X%.3f Y%.3f E%.5f F1200\n' % (xm, yhi, e))
    return src


def layer_points(path):
    """one list of extrusion end points per ;LAYER_CHANGE."""
    layers = []
    cur = None
    x = y = 0.0
    for ln in open(path, errors='replace'):
        if ln.startswith(';LAYER_CHANGE'):
            cur = []
            layers.append(cur)
        else:
            code = ln.split(';', 1)[0].strip()
            parts = code.split()
            if parts and parts[0] in ('G0', 'G1'):
                p = pp.parse_params(code[2:])
                if 'X' in p:
                    x = p['X']
                if 'Y' in p:
                    y = p['Y']
                if parts[0] == 'G1' and 'E' in p and ('X' in p
                                                      or 'Y' in p):
                    cur.append((x, y))
    return layers


def try_mold(src, **kw):
    D = tempfile.mkdtemp(prefix='r271run_')
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
    check('A1 sectors/sec_half in the signature',
          'sectors=0' in sig_block and "sec_half='AUTO'" in sig_block,
          sig_block[:120])
    check('A2 clamp line in the source',
          'sectors = max(0, min(int(sectors or 0), 2))' in src_txt)
    D = tempfile.mkdtemp(prefix='r271val_')
    shroom = write_shape(
        D, 'm.gcode',
        lambda z: (5.0 if z < 8.0 else
                   5.0 + 10.0 * math.sin(math.pi * min(1.0,
                                                        (z - 8.0) / 8.0))))
    try:
        pp.make_mold(shroom, out_dir=D, sec_half='NOPE')
        check('A3 bad sec_half refused', False, 'no ValueError')
    except ValueError as ex:
        check('A3 bad sec_half refused', 'sec_half' in str(ex), str(ex))

    print('B  2-part regression (default == sectors=0)')
    boulder = write_shape(D, 'boulder.gcode',
                          lambda z: 6.0 + 9.0 * math.sin(math.pi * z / 20.0))
    Da, ia, _ = try_mold(boulder, part='BOTH')
    Db, ib, _ = try_mold(boulder, part='BOTH', sectors=0)
    same = (ia['files'] == ib['files'])
    for fn in ia['files']:
        ba = open(os.path.join(Da, fn), 'rb').read()
        bb = open(os.path.join(Db, fn), 'rb').read()
        same = same and ba == bb
    check('B1 default call byte-identical to sectors=0', same,
          (ia['files'], ib['files']))
    check('B2 sec_half/bridges stay None',
          ia['sec_half'] is None and ia['bridges'] is None
          and ia['sectors'] == 0, (ia['sec_half'], ia['bridges']))

    print('C  mushroom 3-part (sectors=1)')
    Dc, ic, err = try_mold(shroom, part='BOTH', plane='OFF', z_off=0.0,
                           sectors=1)
    check('C1 builds 3 files', err is None and len(ic['files']) == 3,
          err or ic['files'])
    if ic:
        names = sorted(ic['files'])
        check('C2 file set = FormUnten + FormOben_S1/S2',
              any('FormUnten' in n for n in names)
              and any('FormOben_S1' in n for n in names)
              and any('FormOben_S2' in n for n in names), names)
        # block rect straight from the bottom half's EXCLUDE polygon
        # (the bed is (0,-3,244,238): X center 122, Y center 117.5 -
        # never assume a symmetric center)
        funten = [n for n in ic['files'] if 'FormUnten' in n][0]
        import re as _re0
        _ex = [ln for ln in open(os.path.join(Dc, funten),
                                 errors='replace').read(3000)
               .splitlines() if ln.startswith('EXCLUDE_OBJECT_DEFINE')][0]
        _m0 = _re0.search(r'POLYGON=\[\[(.*?)\]\]', _ex)
        _pts0 = _re0.findall(r'(-?\d+\.?\d*),(-?\d+\.?\d*)', _m0.group(1))
        bx0 = min(float(a) for (a, b) in _pts0)
        bx1 = max(float(a) for (a, b) in _pts0)
        by0 = min(float(b) for (a, b) in _pts0)
        by1 = max(float(b) for (a, b) in _pts0)
        BW = bx1 - bx0
        BH = by1 - by0
        check('C3 AUTO sectors the TOP half, X axis, 1 cut',
              ic['sec_half'] == 'TOP' and ic['sec_axis'] == 'X'
              and len(ic['sec_cuts']) == 1,
              (ic['sec_half'], ic['sec_axis'], ic['sec_cuts']))
        br = ic['bridges'] or {}
        check('C4 bridges counted, span within 25mm',
              br.get('cells', 0) > 0 and 0.0 < br.get('max_mm', 99)
              <= 25.0, br)
        check('C5 bridge note + slide note',
              any('bridges over the cavity' in n for n in ic['notes'])
              and any('3-part mold' in n and 'slide' in n
                      for n in ic['notes']), ic['notes'][:3])
        s1 = [n for n in ic['files'] if 'FormOben_S1' in n][0]
        head = open(os.path.join(Dc, s1), errors='replace').read(4000)
        check('C6 piece head: R271 + assemble ALL pieces',
              'R271 SECTOR PIECE' in head
              and 'assemble ALL pieces' in head,
              head[:200])
        # C7: the piece BODIES never cross the cut plane - from layer
        # 2 up (layer 1 carries the brim, which may overlap the
        # neighbor's territory by design)
        cut_x = ic['sec_cuts'][0]
        s1 = [n for n in ic['files'] if 'FormOben_S1' in n][0]
        s2 = [n for n in ic['files'] if 'FormOben_S2' in n][0]
        L1 = layer_points(os.path.join(Dc, s1))
        L2 = layer_points(os.path.join(Dc, s2))
        worst = 0.0
        if len(L1) == len(L2):
            for idx, (la, lb) in enumerate(zip(L1, L2)):
                if idx == 0:
                    continue
                m1 = max((px for (px, py) in la), default=-1e9)
                m2 = min((px for (px, py) in lb), default=1e9)
                worst = max(worst, m1 - cut_x, cut_x - m2)
        check('C7 piece bodies stay on their side of the cut',
              len(L1) == len(L2) and worst <= 0.1,
              (len(L1), len(L2), round(worst, 3)))

    print('D  bowl: AUTO sectors the BOTTOM half')
    bowl = write_shape(D, 'bowl.gcode',
                      lambda z: (6.0 + 9.0 * math.sin(math.pi * z / 16.0)
                                 if z < 16.0 else 4.0))
    _, ida, err = try_mold(bowl, sectors=1, plane='OFF', z_off=17.8)
    check('D1 AUTO picks BOTTOM, 3 files',
          err is None and ida['sec_half'] == 'BOTTOM'
          and len(ida['files']) == 3, err or (ida['sec_half'],
                                              ida['files']))
    _, idx, err = try_mold(bowl, sectors=1, sec_half='BOTTOM',
                           plane='OFF', z_off=17.8)
    check('D2 explicit BOTTOM agrees',
          err is None and idx['sec_half'] == 'BOTTOM', err)

    print('E  sector dowel tunnels (mushroom pieces)')
    if ic and ic['sec_axis'] == 'X':
        cut_x = ic['sec_cuts'][0]
        x0 = bx0
        tun_ys = [by0 + 2.5, by0 + BH - 2.5]
        n_top = ic['layers_top']
        lt = max(2 + 4, min(n_top // 2, n_top - 30 - 4 - 2))
        c1 = int(round((cut_x - x0) / WID))
        hole_rc = 3.0 / 2.0 + 0.3
        span_mm = 12.5
        allok = True
        details = []
        for fn in ic['files']:
            if 'FormOben_S' not in fn:
                continue
            lays = layer_points(os.path.join(Dc, fn))
            is_s1 = 'FormOben_S1' in fn
            pc = (0 + c1) / 2.0 if is_s1 else (c1 + BW / WID) / 2.0
            lox = x0 + pc * WID - span_mm / 2.0
            hix = x0 + pc * WID + span_mm / 2.0
            blocked = 0
            ctrl = 0
            for li in range(lt - 2, lt + 3):
                if li < 1 or li > len(lays):
                    continue
                dz = abs(li - lt) * LH
                sh = math.sqrt(max(0.0, hole_rc ** 2 - dz ** 2))
                if sh <= 0.05:
                    continue
                for (px, py) in lays[li - 1]:
                    for ty in tun_ys:
                        if (lox - 0.2 < px < hix + 0.2
                                and abs(py - ty) < sh - 0.25):
                            blocked += 1
            for (px, py) in lays[lt - 1]:
                for ty in tun_ys:
                    if ((lox - 4.0 < px < lox - 0.5
                         or hix + 0.5 < px < hix + 4.0)
                            and abs(py - ty) < 1.0):
                        ctrl += 1
            heights = []
            for ty in tun_ys:
                ys = [py for (px, py) in lays[lt - 1]
                      if lox + 0.5 < px < hix - 0.5]
                below = [yv for yv in ys if yv < ty]
                above = [yv for yv in ys if yv > ty]
                if below and above:
                    heights.append(min(above) - max(below))
            okp = (blocked == 0 and ctrl > 0
                   and len(heights) == 2
                   and all(3.4 <= h <= 7.0 for h in heights))
            allok = allok and okp
            details.append((fn[-20:], blocked, ctrl,
                            [round(h, 2) for h in heights]))
        check('E1 tunnels open + solid beyond the span', allok, details)

    print('F  piece geometry from the G-code')
    if ic and ic['sec_axis'] == 'X':
        cut_x = ic['sec_cuts'][0]
        s1 = [n for n in ic['files'] if 'FormOben_S1' in n][0]
        s2 = [n for n in ic['files'] if 'FormOben_S2' in n][0]
        # (bx0/BW from the parsed bottom-half polygon above)
        p1 = [p for l in layer_points(os.path.join(Dc, s1)) for p in l]
        p2 = [p for l in layer_points(os.path.join(Dc, s2)) for p in l]
        body1 = [px for (px, py) in p1 if px <= cut_x + 0.05]
        body2 = [px for (px, py) in p2 if px >= cut_x - 0.05]
        brim1 = [px for (px, py) in p1 if px > cut_x + 0.3]
        check('F1 S1 body left of the cut, S2 body right',
              body1 and body2 and max(body1) <= cut_x + 0.05
              and min(body2) >= cut_x - 0.05,
              (max(body1) if body1 else None,
               min(body2) if body2 else None, cut_x))
        check('F2 S1 brim reaches past the cut face (piece-local)',
              any(px < cut_x + 3.0 for px in brim1),
              (len(brim1), cut_x))
        head1 = open(os.path.join(Dc, s1), errors='replace').read(6000)
        polys = [ln for ln in head1.splitlines()
                 if ln.startswith('EXCLUDE_OBJECT_DEFINE')]
        okf = False
        info_f3 = polys[:1]
        if polys:
            import re as _re
            m = _re.search(r'POLYGON=\[\[(.*?)\]\]', polys[0])
            if m:
                pts = _re.findall(r'(-?\d+\.?\d*),(-?\d+\.?\d*)', m.group(1))
                xs_p = [float(a) for (a, b) in pts]
                info_f3 = xs_p
                okf = (abs(max(xs_p) - cut_x) < 0.1
                       and min(xs_p) >= bx0 - 0.5
                       and max(xs_p) <= bx0 + BW + 0.5)
        check('F3 EXCLUDE polygon = the piece rect (ends at the cut)',
              okf, info_f3)

    print('G  honest refusals')
    hour = write_shape(D, 'hour.gcode',
                       lambda z: 4.0 + 11.0 * abs(z - 10.0) / 10.0)
    _, _, err = try_mold(hour, sectors=1, plane='MID')
    check('G1 hourglass: both halves undercut',
          err is not None and 'both halves have an undercut' in err, err)

    def tree(z):
        if z < 8.0:
            return (45.0, 55.0)
        if z < 10.0:
            return (25.0, 75.0)
        if z < 14.0:
            t = (z - 10.0) / 4.0
            return (25.0 + 20.0 * t, 75.0 - 20.0 * t)
        t = (z - 14.0) / 6.0
        return (45.0 - 10.0 * t, 55.0 + 10.0 * t)

    treef = write_rect_shape(D, 'tree.gcode', tree)
    _, it3, err3 = try_mold(treef, sectors=1)
    check('G2 tree 3-part builds (bridges within limits)',
          err3 is None and len(it3['files']) == 3, err3)
    _, _, err4 = try_mold(treef, sectors=2)
    check('G3 tree 4-part: the middle must lift',
          err4 is not None and 'MIDDLE sector' in err4
          and 'LIFT' in err4, err4)
    _, _, err9 = try_mold(treef, sectors=9)
    check('G4 sectors=9 clamps to 2 (same refusal)',
          err9 is not None and 'MIDDLE sector' in err9, err9)
    Dbm, ibm, errm3 = try_mold(boulder, sectors=-3)
    check('G5 sectors=-3 clamps to 0 (plain 2-part)',
          errm3 is None and ibm['sectors'] == 0
          and len(ibm['files']) == 2,
          errm3 or ibm['files'])

    srcb = os.path.join(D, 'twoblobs.gcode')
    with open(srcb, 'w') as f:
        f.write(';TYPE:Outer wall\nM82\nG90\n')
        e = 0.0
        for li in range(1, 61):
            z = round(li * LH, 3)
            r = 8.0
            f.write(';LAYER_CHANGE\nG1 Z%.3f F600\n' % z)
            for (cx, cy) in ((35.0, 50.0), (65.0, 50.0)):
                pts = [(cx + r * math.cos(a), cy + r * math.sin(a))
                       for a in [i * math.pi / 30 for i in range(61)]]
                px, py = pts[0]
                f.write('G0 X%.3f Y%.3f F3000\n' % (px, py))
                for (qx, qy) in pts[1:]:
                    d = math.hypot(qx - px, qy - py)
                    e += d * 0.05
                    f.write('G1 X%.3f Y%.3f E%.5f F1200\n'
                            % (qx, qy, e))
    _, _, errb = try_mold(srcb, sectors=1)
    check('G6 cut between blobs: slide blocked by the frame',
          errb is not None and 'cannot slide off' in errb, errb)

    def disc(z):
        if z < 10.0:
            return (45.0, 55.0)
        if z < 10.6:
            return (15.0, 85.0)
        return (45.0, 55.0)

    discf = write_rect_shape(D, 'disc.gcode', disc)
    _, _, errd = try_mold(discf, sectors=1, plane='OFF', z_off=0.0)
    check('G7 disc: bridge span over 25mm refused',
          errd is not None and 'bridge' in errd and '25' in errd, errd)

    print()
    print('%d/%d checks passed' % (count - fails, count))
    return 1 if fails else 0


if __name__ == '__main__':
    sys.exit(main())
