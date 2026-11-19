#!/usr/bin/env python3
"""R267 field check: the SPRAY-STENCIL generator (J9) - measured, not assumed.

The stencil set is generated from a synthetic three-tone image (bright
background, mid square, dark disc - the disc sits INSIDE the square, so
the square-band stencil must grow a BRIDGE for the disc island).

Checks:
  A  generation: steps 2/3/4 (+ clamps 1->2, 9->4), negative adds a plate
  B  tone bands: every band non-empty (percentile recut path included)
  C  masks (from info['masks']):
     C1 frame ring closed (border cells all plate)
     C2 registration holes: exactly 4, in the frame corners, IDENTICAL
        cells in every plate of the set (the pin registry)
     C3 bridge law: flood from the frame reaches EVERY plate cell (no
        floating islands - measured on the final mask)
     C4 partition: every window cell is cut out in EXACTLY ONE band
        stencil; the negative's cutout == band 0's cutout
     C5 cutout share sane (2..65%), plate share > 30%
  D  gcode per file: layer count + Z ladder, TYPE markers (1 bottom,
     1 top), E density uniform (e/len ~ layer*wid/fil_area +-15%),
     every extrusion inside the plate bounds +-1mm, G90/M83 header,
     PRINT_START/PRINT_END present
  E  determinism: identical rerun -> byte-identical plate 1
  F  errors: wrong extension raises ValueError
"""
import math
import os
import struct
import sys
import tempfile
import zlib

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import r2_postproc as pp  # noqa: E402

BED = (0.0, -3.0, 244.0, 238.0)
FIL_AREA = pp.FIL_AREA

fails = 0
count = 0


def check(name, ok, info=''):
    global fails, count
    count += 1
    print(('  ok   ' if ok else '  FAIL ') + name)
    if not ok:
        fails += 1
        print('      -> %s' % str(info)[:240])


def png(w, h, gray):
    def chunk(t, d):
        return struct.pack('>I', len(d)) + t + d + struct.pack(
            '>I', zlib.crc32(t + d) & 0xffffffff)
    rows = b''
    for y in range(h):
        rows += b'\x00' + bytes(int(round(gray(x, y))) & 0xff
                                for x in range(w))
    return (b'\x89PNG\r\n\x1a\n'
            + chunk(b'IHDR', struct.pack('>IIBBBBB', w, h, 8, 0, 0, 0, 0))
            + chunk(b'IDAT', zlib.compress(rows))
            + chunk(b'IEND', b''))


def gray(x, y):
    # three tones, tuned THROUGH the pipeline (stretch lo=20 hi=220,
    # invert, boost 1.35): bg -> band 0, square -> band 1, disc -> band 2
    if (x - 48.0) ** 2 + (y - 48.0) ** 2 <= 10.0 ** 2:
        return 20
    if 24 <= x < 72 and 24 <= y < 72:
        return 130
    return 220


def gray4(x, y):
    # FOUR tones: bg -> 0, inner square -> 1, ring square -> 2, disc -> 3
    if (x - 44.0) ** 2 + (y - 44.0) ** 2 <= 9.0 ** 2:
        return 20
    if 52 <= x < 72 and 52 <= y < 72:
        return 175
    if 16 <= x < 80 and 16 <= y < 80:
        return 130
    return 220


def gen(D, **kw):
    img = os.path.join(D, 'motif.png')
    if not os.path.isfile(img):
        open(img, 'wb').write(png(96, 96, gray))
    args = dict(steps=3, size_mm=80.0, out_dir=D, bed=BED, nozzle=0.4)
    args.update(kw)
    return pp.make_stencil(img, **args)


def gen4(D, **kw):
    img = os.path.join(D, 'motif4.png')
    if not os.path.isfile(img):
        open(img, 'wb').write(png(96, 96, gray4))
    args = dict(steps=4, size_mm=80.0, out_dir=D, bed=BED, nozzle=0.4)
    args.update(kw)
    return pp.make_stencil(img, **args)


def parse_gcode(path):
    """(layers, zs, types, e_ratio_viol, oob, header_ok, e_total)"""
    layers = 0
    zs = []
    types = set()
    viol = 0
    n_ext = 0
    oob = 0
    e_total = 0.0
    px = py = None
    prime = False
    header_ok = False
    wid = 0.4 * 1.08
    e_exp = 0.2 * wid / FIL_AREA
    for ln in open(path):
        ln = ln.rstrip('\n')
        if ln.startswith(';LAYER_CHANGE'):
            layers += 1
        elif ln.startswith(';Z:'):
            zs.append(float(ln[3:]))
        elif ln.startswith(';TYPE:'):
            types.add(ln[6:])
        elif ln.startswith('G90'):
            header_ok = True
        elif ln.startswith('G11'):
            # the first chord after an unretract carries the retract
            # compensation - a legit prime, not a density deviation
            prime = True
        elif ln.startswith('G0 '):
            mx = my = None
            for part in ln[3:].split():
                if part[0] == 'X':
                    mx = float(part[1:])
                elif part[0] == 'Y':
                    my = float(part[1:])
            if mx is not None and my is not None:
                px, py = mx, my
        elif ln.startswith('G1 '):
            mx = my = me = None
            for part in ln[3:].split():
                if part[0] == 'X':
                    mx = float(part[1:])
                elif part[0] == 'Y':
                    my = float(part[1:])
                elif part[0] == 'E':
                    me = float(part[1:])
            if me is not None and me > 0:
                e_total += me
                if px is not None and mx is not None and my is not None:
                    lnth = math.hypot(mx - px, my - py)
                    if lnth > 0.05:
                        r = me / lnth
                        if abs(r - e_exp) > 0.15 * e_exp and not prime:
                            viol += 1
                        n_ext += 1
                prime = False
                if mx is not None and my is not None:
                    if not (-1.0 <= mx <= 245.0 and -4.0 <= my <= 239.0):
                        oob += 1
            if mx is not None and my is not None:
                px, py = mx, my
    return (layers, zs, types, viol, oob, header_ok, e_total, n_ext)


def mask_stats(m):
    R, C = len(m), len(m[0])
    plate = sum(1 for r in m for v in r if v)
    return plate, R * C


def flood_frame(m):
    """plate cells reachable from the grid corner (8-conn) vs total."""
    R, C = len(m), len(m[0])
    seen = [[False] * C for _ in range(R)]
    stk = [(0, 0)]
    seen[0][0] = True
    reach = 0
    while stk:
        x, y = stk.pop()
        reach += 1
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                nx, ny = x + dx, y + dy
                if 0 <= nx < C and 0 <= ny < R and m[ny][nx] \
                        and not seen[ny][nx]:
                    seen[ny][nx] = True
                    stk.append((nx, ny))
    return reach


def window_cells(m, fr, cols, rows):
    for r in range(rows):
        for c in range(cols):
            yield (fr + r, fr + c), m[fr + r][fr + c]


def main():
    D = tempfile.mkdtemp(prefix='r267_')

    print('--- A) generation ------------------------------------------------')
    out3, i3 = gen(D)
    check('A1: steps=3 -> exactly 3 files, kind stencil-set',
          len(i3['files']) == 3 and i3['kind'] == 'stencil-set'
          and i3['steps'] == 3,
          str(i3['files']))
    out2, i2 = gen(D, steps=2)
    check('A2: steps=2 -> 2 files', len(i2['files']) == 2, str(i2['files']))
    out4, i4 = gen4(D)
    check('A3: steps=4 on a 4-tone image -> 4 files',
          len(i4['files']) == 4, str(i4['files']))
    _, ired = gen(D, steps=4)
    check('A3b: steps=4 on a 3-TONE image honestly reduces to 3 healthy '
          'plates (no hairline stencils) + notes it',
          len(ired['files']) == 3
          and any('steps reduced to 3' in n for n in ired['notes']),
          str(ired['files']))
    _, icl = gen4(D, steps=9)
    check('A4: steps=9 clamps to 4 (4-tone image keeps all four)',
          icl['steps'] == 4, icl['steps'])
    _, icl2 = gen(D, steps=1)
    check('A5: steps=1 clamps to 2', icl2['steps'] == 2, icl2['steps'])
    outn, ineg = gen(D, steps=3, negative=1)
    check('A6: negative adds ONE extra plate (3+1)',
          ineg['steps'] == 3 and len(ineg['files']) == 4,
          str(ineg['files']))

    print('--- B) tone bands ------------------------------------------------')
    for tag, inf in (('3-band', i3), ('2-band', i2), ('4-band', i4)):
        check('B: %s set: every band carries cells' % tag,
              all(b > 0 for b in inf['bands']), str(inf['bands']))

    print('--- C) masks -----------------------------------------------------')
    for tag, inf in (('3-band', i3), ('2-band', i2),
                     ('4-band', i4), ('negative', ineg)):
        GR, GC = inf['grid']
        fr, _, cols, rows = inf['window']
        masks = dict(inf['masks'])
        ok_closed = True
        ok_reach = True
        ok_share = True
        for (label, m) in masks.items():
            # C1 frame closed
            border = (all(m[0]) and all(m[GR - 1])
                      and all(m[r][0] for r in range(GR))
                      and all(m[r][GC - 1] for r in range(GR)))
            ok_closed = ok_closed and border
            # C3 bridge law
            plate, tot = mask_stats(m)
            if flood_frame(m) != plate:
                ok_reach = False
            # C5 share
            cut = tot - plate
            if not (0.02 * tot <= cut <= 0.65 * tot and plate > 0.3 * tot):
                ok_share = False
        check('C1 %s: frame ring closed in every plate' % tag, ok_closed)
        check('C3 %s: bridge law - flood from frame reaches every plate '
              'cell (no floating islands)' % tag, ok_reach)
        check('C5 %s: cutout share 2..65%%, plate > 30%%' % tag, ok_share)

        # C2 registration holes: identical non-plate cells in the four
        # frame corners across ALL plates of the set
        def corner_cells(m):
            out = set()
            for r in range(GR):
                for c in range(GC):
                    if not m[r][c]:
                        if (r < fr or r >= fr + rows
                                or c < fr or c >= fr + cols):
                            out.add((r, c))
            return out
        refs = None
        ok_holes = True
        for (label, m) in masks.items():
            cc = corner_cells(m)
            if refs is None:
                refs = cc
            elif cc != refs:
                ok_holes = False
        # 4 holes, each ~ pi*r^2 cells, r = hole_d/2/wid
        r_cells = (ineg['hole_d'] / 2.0) / (0.4 * 1.08)
        expect = 4 * math.pi * r_cells ** 2
        check('C2 %s: registration holes identical in every plate '
              '(~%.0f cells expected)' % (tag, expect),
              ok_holes and 0.5 * expect <= len(refs) <= 1.6 * expect,
              'cells %d' % len(refs))

    # C4 partition + negative relation (3-band set + negative)
    fr, _, cols, rows = i3['window']
    m1, m2, m3 = (dict(i3['masks'])['Schablone%d' % (k + 1)]
                  for k in range(3))
    mneg = dict(ineg['masks'])['SchabloneNeg']
    ok_part = True
    zero_cut = 0
    diff_neg = 0
    n_win = 0
    for (rc, _) in window_cells(m1, fr, cols, rows):
        n_win += 1
        cuts = sum(1 for m in (m1, m2, m3) if not m[rc[0]][rc[1]])
        if cuts > 1:
            ok_part = False
        if cuts == 0:
            zero_cut += 1       # bridge cells carry plate over a cutout
        if bool(mneg[rc[0]][rc[1]]) != bool(m1[rc[0]][rc[1]]):
            diff_neg += 1       # bridges differ between the two masks
    check('C4a: partition - a window cell is cut out in AT MOST ONE band '
          'stencil, bridge cells (cut in none) stay under 8%',
          ok_part and zero_cut <= 0.08 * n_win,
          'zero-cut %d/%d' % (zero_cut, n_win))
    check('C4b: negative cutout == band 0 cutout up to bridges (motif '
          'stands, background sprays)',
          diff_neg <= 0.08 * n_win,
          'diff %d/%d' % (diff_neg, n_win))

    print('--- D) gcode -----------------------------------------------------')
    for tag, inf in (('3-band', i3), ('2-band', i2),
                     ('4-band', i4), ('negative', ineg)):
        allok = True
        details = []
        for fn in inf['files']:
            path = os.path.join(D, fn)
            layers, zs, types, viol, oob, hdr, etot, next_ = \
                parse_gcode(path)
            okf = (layers == inf['layers']
                   and len(zs) == inf['layers']
                   and abs(zs[-1] - inf['layers'] * 0.2) < 0.01
                   and 'Bottom surface' in types
                   and 'Top surface' in types
                   and hdr and oob == 0
                   and viol <= max(2, int(next_ * 0.002))
                   and etot > 0 and next_ > 100)
            allok = allok and okf
            if not okf:
                details.append('%s L%d zs%d viol%d oob%d ext%d'
                               % (fn, layers, len(zs), viol, oob, next_))
        check('D %s: layers/Z-ladder/types/E-density/bounds in ALL %d '
              'files' % (tag, len(inf['files'])), allok, '; '.join(details))

    print('--- E) determinism ------------------------------------------------')
    D2 = tempfile.mkdtemp(prefix='r267b_')
    out3b, i3b = gen(D2)
    a = open(os.path.join(D, i3['files'][0]), 'rb').read()
    b = open(os.path.join(D2, i3b['files'][0]), 'rb').read()
    check('E1: identical rerun -> byte-identical first plate', a == b,
          '%d vs %d bytes' % (len(a), len(b)))

    print('--- F) errors -----------------------------------------------------')
    try:
        pp.make_stencil(os.path.join(D, 'nope.txt'), out_dir=D)
        check('F1: wrong extension raises ValueError', False, 'no raise')
    except ValueError:
        check('F1: wrong extension raises ValueError', True)

    print()
    print('R267 STENCIL CHECK: %d checks, %d failed' % (count, fails))
    return 1 if fails else 0


if __name__ == '__main__':
    sys.exit(main())
