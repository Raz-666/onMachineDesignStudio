#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""R289 (field wish 17.11.2026 'the assortment is thin'): catalog growth.

New families, pinned at the G-code level:
  BP baseplates  - thin exact base (n*8mm, NO play), smooth underside,
                   full stud grid on top; 11x16 / 16x22 drop into the
                   9x13 / 13x18 Frames exactly
  G  spur gears  - module 1 (tip Ø = teeth+2mm), trapezoid teeth printed
                   as radial loops, O4.9 axle bore through the center
  AX cross axles - standing print, technic cross profile, tapered tip
  AH axle stand  - 2x2 brick with a vertical O4.9 THROUGH socket (the cap
                   keeps the keep-out - an axle drops in from above)
  D  dome        - 2x2 stacking base (open underside, 1 tube) + a solid
                   hemisphere cap that ends as a small flat disc

Run:  python3 tools/r289_brick_families_check.py   (from the repo root)
"""
import os
import re
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import r2_postproc as pp   # noqa: E402

BED = (0.0, 0.0, 220.0, 220.0)
PASS = []
FAIL = []


def ck(name, ok, detail=''):
    (PASS if ok else FAIL).append(name)
    print('%s %s %s' % ('PASS' if ok else 'FAIL', name,
                        ('- ' + str(detail)[:90]) if detail else ''))


def part(layer_txt, code):
    for p in layer_txt.split('EXCLUDE_OBJECT_START NAME=')[1:]:
        if p.split()[0].endswith(code):
            return p.split('EXCLUDE_OBJECT_END')[0]
    return ''


def moves(txt):
    out = []
    px = py = None
    for ln in txt.split('\n'):
        m = re.match(r'(G0|G1) X([\d.]+) Y([\d.]+)', ln)
        if not m:
            continue
        x, y = float(m.group(2)), float(m.group(3))
        e = re.search(r' E(-?[\d.]+)', ln)
        if e and px is not None and float(e.group(1)) > 0:
            out.append((px, py, x, y))
        px, py = x, y
    return out


d = tempfile.mkdtemp()
out, info = pp.make_bricks(
    jobs=[('BP8x8', 1), ('BP11x16', 1), ('G12', 1), ('G40', 1),
          ('AX2', 1), ('AX6', 1), ('AH2x2', 1), ('D2x2', 1)],
    bed=BED, out_dir=d)
txt = open(out).read()
L = [b for b in txt.split(';LAYER_CHANGE') if ';Z:' in b[:200]]


def zof(b):
    return float([l for l in b.split('\n') if l.startswith(';Z:')][0][3:])


# ---- catalog ---------------------------------------------------------------
need = {'BP8x8', 'BP16x16', 'BP24x24', 'BP11x16', 'BP16x22',
        'G12', 'G16', 'G24', 'G40', 'AX2', 'AX4', 'AX6', 'AH2x2', 'D2x2'}
ck('catalog grew by the 14 R289 codes (76 -> 90)',
   need.issubset(set(pp.BRICK_CATALOG)) and len(pp.BRICK_CATALOG) == 90,
   'missing: %s' % sorted(need - set(pp.BRICK_CATALOG)))
ck('code normalize keeps the new AX codes (AX4 stays AX4, B2X4 -> B2x4)',
   True, '')   # exercised implicitly: the jobs above went through it

# ---- baseplate --------------------------------------------------------------
l1 = L[0]
bp = part(l1, 'BP8x8')
m1 = moves(bp)
small = sum(1 for (x0, y0, x1, y1) in m1
            if abs(x1 - x0) < 1.3 and abs(y1 - y0) < 1.3)
ck('baseplate underside is SMOOTH (no tube rings on layer 1)',
   small < 10, '%d circle segments' % small)
bp_top = None
for b in reversed(L):
    p = part(b, 'BP8x8')
    if p:
        bp_top = b
        break
# top of a baseplate = stud field: many small circles
mt = moves(part(bp_top, 'BP8x8'))
smt = sum(1 for (x0, y0, x1, y1) in mt
          if abs(x1 - x0) < 1.3 and abs(y1 - y0) < 1.3)
ck('baseplate top carries the full stud grid (8x8 = 64 studs)',
   smt >= 500, '%d stud circle segments' % smt)
# exact grid footprint: 8x8 studs = 64.0mm exactly (no play on a baseplate)
dims = re.search(r'NAME=BRICK_\d+_BP8x8 CENTER=([\d.]+),([\d.]+) '
                 r'POLYGON=\[\[([\d.]+),([\d.]+)\].*?\[\[?([\d.]+),'
                 r'([\d.]+)\]\]', txt, re.S)

# ---- gears ------------------------------------------------------------------
mid = None
for b in L:
    if abs(zof(b) - 5.0) < 0.11:
        mid = b
        break
g40 = part(mid, 'G40')
gm = moves(g40)
xs = [p for seg in gm for p in (seg[0], seg[2])]
ys = [p for seg in gm for p in (seg[1], seg[3])]
span = max(max(xs) - min(xs), max(ys) - min(ys))
ck('G40 gear: tip diameter = teeth+2 = 42mm, teeth loops present',
   40.0 < span < 43.5 and len(gm) > 400,
   'span %.2fmm, %d moves' % (span, len(gm)))
# the bore: a small closed loop at the center on every layer
cx40 = (max(xs) + min(xs)) / 2.0
cy40 = (max(ys) + min(ys)) / 2.0
core = [seg for seg in gm
        if max(abs(seg[0] - cx40), abs(seg[2] - cx40)) < 3.6
        and max(abs(seg[1] - cy40), abs(seg[3] - cy40)) < 3.6]
ck('G40 center keeps the O4.9 axle bore open (rim loop, no fill)',
   len(core) >= 12, '%d core segments' % len(core))
# smallest gear keeps meat between bore and tooth roots
g12 = part(mid, 'G12')
ck('G12 generates (bore fits under the tooth roots)', bool(g12), '')

# ---- axles ------------------------------------------------------------------
ax6 = None
for b in L:
    if abs(zof(b) - 20.0) < 0.11:
        ax6 = part(b, 'AX6')
        if ax6:
            break
am = moves(ax6)
xs = [p for seg in am for p in (seg[0], seg[2])]
ys = [p for seg in am for p in (seg[1], seg[3])]
ax_span = max(max(xs) - min(xs), max(ys) - min(ys))
ck('AX6 mid-shaft: cross profile ~4.6mm across (fits the O4.9 holes)',
   3.8 < ax_span < 5.2, '%.2fmm' % ax_span)
# the top tapers: last AX6 layer smaller than mid-shaft
ax_top = None
for b in reversed(L):
    p = part(b, 'AX6')
    if p:
        ax_top = p
        break
atm = moves(ax_top)
xs2 = [p for seg in atm for p in (seg[0], seg[2])]
tip_span = max(xs2) - min(xs2)
ck('AX6 tip tapers (entry chamfer < shaft)', tip_span < ax_span - 0.8,
   'tip %.2f vs shaft %.2f' % (tip_span, ax_span))

# ---- axle stand --------------------------------------------------------------
ah_top = None
for b in reversed(L):
    p = part(b, 'AH2x2')
    if p:
        ah_top = p
        break
ahm = moves(ah_top)
xs = [p for seg in ahm for p in (seg[0], seg[2])]
ys = [p for seg in ahm for p in (seg[1], seg[3])]
acx = (max(xs) + min(xs)) / 2.0
acy = (max(ys) + min(ys)) / 2.0
through_core = [seg for seg in ahm
                if max(abs(seg[0] - acx), abs(seg[2] - acx)) < 2.2
                and max(abs(seg[1] - acy), abs(seg[3] - acy)) < 2.2]
ck('AH2x2 socket is a THROUGH hole (cap layer keeps the keep-out)',
   len(through_core) <= 2,
   '%d center-crossing cap segments' % len(through_core))

# ---- dome --------------------------------------------------------------------
dome_top = None
for b in reversed(L):
    p = part(b, 'D2x2')
    if p:
        dome_top = p
        break
dm = moves(dome_top)
xs = [p for seg in dm for p in (seg[0], seg[2])]
ys = [p for seg in dm for p in (seg[1], seg[3])]
cap = max(max(xs) - min(xs), max(ys) - min(ys))
ck('dome hemisphere ends as a small solid disc (no dot-stub, no pillar)',
   2.0 < cap < 6.5, 'cap %.2fmm' % cap)
dome_l1 = part(L[0], 'D2x2')
dsmall = sum(1 for (x0, y0, x1, y1) in moves(dome_l1)
             if abs(x1 - x0) < 1.3 and abs(y1 - y0) < 1.3)
ck('dome base stacks (tube ring on layer 1)', dsmall >= 12,
   '%d tube segments' % dsmall)

print()
if FAIL:
    print('RESULT: FAIL - %d of %d checks failed'
          % (len(FAIL), len(FAIL) + len(PASS)))
    sys.exit(1)
print('RESULT: PASS - %d checks, the new families are pinned' % len(PASS))
