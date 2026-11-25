#!/usr/bin/env python3
"""R216 stage 7 check (pinned): every infill variant + layers checking
EACH OTHER.

The 7th stage of the feature recognition (.136n user wish):

  - TAGGED side: the infill pattern vocabulary - the 3D families
    (gyroid, cubic, cross, lightning) and the classic patterns - maps
    and ladder-resolves to INFILL-SPARSE; a solid/dense token still
    wins over the pattern name; support grids stay SUPPORT.
  - GEOMETRY side: an open CURVED path bathed in material on both
    sides is 3D infill (INFILL-SPARSE) - UNLESS it turns monotonically
    like a loop arc (the R181 sandwich wall stays WALL-INNER) or has a
    free side (WALL-OUTER). The far probe (sides_ink_far, 8mm) sees
    the 2-6mm line spacing of gyroid/cubic that the 0.7/1.2mm wall
    probe misses.
  - MULTI PASS: the layers check EACH OTHER (elimination). Pass 1
    tags dense hatch INFILL-SOLID; pass 2 (the next layer's picture)
    flips the candidate to SURFACE-TOP when NOTHING - not even a wall
    ring - prints above its region; the final pass (end of file) flips
    everything still pending. A thin wall ring above (the R214
    support-gap class) counts as 'the model goes on' -> stays solid.

Run:  python3 tools/r216_stage7_check.py
"""
import math
import sys
import os
from collections import Counter

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import r2_postproc as pp  # noqa: E402

PASS = []
FAIL = []


def ck(name, ok, detail=''):
    (PASS if ok else FAIL).append(name)
    print('%-4s %s%s' % ('PASS' if ok else 'FAIL', name,
                         ('  [%s]' % detail) if detail and not ok else ''))


# ---------------- 1) tagged vocabulary --------------------------------------
VOCAB = [
    ('Gyroid', 'INFILL-SPARSE'),
    ('gyroid infill', 'INFILL-SPARSE'),
    ('3D Infill', 'INFILL-SPARSE'),
    ('3D-Lattice', 'INFILL-SPARSE'),
    ('Honeycomb', 'INFILL-SPARSE'),
    ('Lightning infill', 'INFILL-SPARSE'),
    ('Cross-Cubic', 'INFILL-SPARSE'),
    ('Cross hatch', 'INFILL-SPARSE'),
    ('Tri-Hexagon', 'INFILL-SPARSE'),
    ('Zig-Zag Infill', 'INFILL-SPARSE'),
    ('Rectilinear', 'INFILL-SPARSE'),
    ('Concentric infill', 'INFILL-SPARSE'),
    ('Grid infill', 'INFILL-SPARSE'),
    ('Octagram spiral', 'INFILL-SPARSE'),
    ('Hilbert curve', 'INFILL-SPARSE'),
    ('Wiggle', 'INFILL-SPARSE'),
    # solid/dense/top/bottom tokens still WIN over the pattern name
    ('Solid gyroid skin', 'INFILL-SOLID'),
    ('gyroid top surface', 'SURFACE-TOP'),
    ('honeycomb bottom', 'SURFACE-BOTTOM'),
    # support grids stay support (substring rule runs first)
    ('Grid support', 'SUPPORT'),
    # R230: 'support cubic' is Prusa's SPARSE INFILL variant (props top
    # surfaces), not a support structure - the exact map wins
    ('support cubic', 'INFILL-SPARSE'),
    # unknown residue stays honest
    ('frobnicate quux', 'CUSTOM'),
]
for (raw, want) in VOCAB:
    ck('vocab: ";TYPE:%s" -> %s' % (raw, want),
       pp._canon_type(raw) == want, pp._canon_type(raw))

# the exact map entries (not just the ladder)
for raw in ('Gyroid', '3d infill', 'lightning infill', 'honeycomb',
            'cross hatch', 'octagram spiral', 'infill (sparse)'):
    ck('exact map carries "%s"' % raw, pp._lookup_type(raw) == 'INFILL-SPARSE',
       str(pp._lookup_type(raw)))

# ---------------- 2) geometry helpers ----------------------------------------
def loop(out, e, x0, y0, w, f):
    out.append('G0 X%.1f Y%.1f F9000' % (x0, y0))
    for (x, y) in [(x0 + w, y0), (x0 + w, y0 + w), (x0, y0 + w), (x0, y0)]:
        e += w * 0.05
        out.append('G1 X%.1f Y%.1f F%d E%.3f' % (x, y, f, e))
    return e


def hatch(out, e, x0, y0, w, h, gap, f):
    y = y0
    n = 0
    while y <= y0 + h + 0.01:
        if n % 2 == 0:
            out.append('G0 X%.1f Y%.1f F9000' % (x0, y))
            e += w * 0.05
            out.append('G1 X%.1f Y%.1f F%d E%.3f' % (x0 + w, y, f, e))
        else:
            out.append('G0 X%.1f Y%.1f F9000' % (x0 + w, y))
            e += w * 0.05
            out.append('G1 X%.1f Y%.1f F%d E%.3f' % (x0, y, f, e))
        y += gap
        n += 1
    return e


def wave(out, e, x0, x1, ybase, amp, turns, f):
    """a gyroid-style open WAVE (curved, both ends open, net turning ~0)"""
    out.append('G0 X%.1f Y%.1f F9000' % (x0, ybase))
    n = 60
    for k in range(1, n + 1):
        t = k / n
        x = x0 + (x1 - x0) * t
        y = ybase + amp * math.sin(turns * 2 * math.pi * t)
        e += 0.12
        out.append('G1 X%.2f Y%.2f F%d E%.3f' % (x, y, f, e))
    return e


def arc(out, e, cx, cy, r, a0, a1, f, n=48):
    out.append('G0 X%.2f Y%.2f F9000' % (cx + r * math.cos(math.radians(a0)),
                                         cy + r * math.sin(math.radians(a0))))
    for k in range(1, n + 1):
        a = math.radians(a0 + (a1 - a0) * k / n)
        e += 0.12
        out.append('G1 X%.2f Y%.2f F%d E%.3f' % (cx + r * math.cos(a),
                                                 cy + r * math.sin(a), f, e))
    return e


def feed(g, lines):
    for i, l in enumerate(lines):
        g.step(i, i, l)


def feats(g):
    return Counter(f for (_, _, f) in g.ranges)


# ---------------- 3) 3D infill geometry --------------------------------------
g = pp._GeomScan(1.75)
lines = ['M82', 'G0 X5 Y5 Z0.2 F9000']
e = 0.0
e = loop(lines, e, 56, 56, 28, 2400)
for yb in (60, 64, 68, 72, 76, 80):
    e = wave(lines, e, 60, 80, yb, 1.6, 3, 4500)
feed(g, lines)
g.finish()
c = feats(g)
ck('gyroid body: the wavy open paths derive INFILL-SPARSE (was: walls)',
   c.get('INFILL-SPARSE', 0) == 6 and c.get('WALL-OUTER', 0) == 1
   and 'WALL-INNER' not in c, str(dict(c)))

g = pp._GeomScan(1.75)
lines = ['M82', 'G0 X5 Y5 Z0.2 F9000']
e = 0.0
for r in (10.0, 12.6, 15.2):
    e = arc(lines, e, 50, 50, r, -45, 225, 1800)
feed(g, lines)
g.finish()
c = feats(g)
ck('R181 sandwich arcs keep their classes (OUTER/INNER/OUTER - a '
   'monotone-turning arc is a wall, not 3D infill)',
   c.get('WALL-OUTER', 0) == 2 and c.get('WALL-INNER', 0) == 1
   and 'INFILL-SPARSE' not in c, str(dict(c)))

g = pp._GeomScan(1.75)
lines = ['M82', 'G0 X5 Y5 Z0.2 F9000']
e = 0.0
e = arc(lines, e, 50, 50, 15, 0, 180, 1800)
feed(g, lines)
g.finish()
c = feats(g)
ck('a boundary arc with a free side stays WALL-OUTER',
   c.get('WALL-OUTER', 0) == 1 and 'INFILL-SPARSE' not in c, str(dict(c)))

# ---------------- 4) multi pass: layers check each other ---------------------
# case TOP: L2 solid, L3 prints NOTHING above the hatch region (walls
# sit outside) -> pass 2 flips L2 to SURFACE-TOP
g = pp._GeomScan(1.75)
lines = ['M82', 'G0 X5 Y5 Z0.2 F9000']
e = 0.0
e = loop(lines, e, 50, 50, 40, 2400)
e = hatch(lines, e, 56, 56, 28, 28, 1.0, 1800)
lines.append('G0 X5 Y5 Z0.4 F9000')
e = loop(lines, e, 50, 50, 40, 2400)
e = hatch(lines, e, 56, 56, 28, 28, 1.0, 1800)
lines.append('G0 X5 Y5 Z0.6 F9000')
e = loop(lines, e, 50, 50, 40, 2400)
feed(g, lines)
g.finish()
c = feats(g)
ck('pass 2: solid with an EMPTY layer above (not even walls) = '
   'SURFACE-TOP, the booking moves too',
   c.get('SURFACE-TOP', 0) == 29 and 'INFILL-SOLID' not in c
   and sum(v for d in [g.fstat.get('SURFACE-TOP', {})] for v in d.values())
   == 29, str(dict(c)))

# case RING: L2 solid, L3 walls sit ON the region rim (the R214
# support-gap class) -> stays INFILL-SOLID
g = pp._GeomScan(1.75)
lines = ['M82', 'G0 X5 Y5 Z0.2 F9000']
e = 0.0
e = loop(lines, e, 56, 56, 28, 2400)
e = hatch(lines, e, 56, 56, 28, 28, 1.0, 1800)
lines.append('G0 X5 Y5 Z0.4 F9000')
e = loop(lines, e, 56, 56, 28, 2400)
e = hatch(lines, e, 56, 56, 28, 28, 1.0, 1800)
lines.append('G0 X5 Y5 Z0.6 F9000')
e = loop(lines, e, 56, 56, 28, 2400)
feed(g, lines)
g.finish()
c = feats(g)
ck('pass 2: a wall ring above (support-gap class) = the model goes on '
   '-> stays INFILL-SOLID',
   c.get('INFILL-SOLID', 0) == 29 and 'SURFACE-TOP' not in c, str(dict(c)))

# case SHELL: a 2-layer top shell over sparse infill - only the UPPERMOST
# becomes SURFACE-TOP, the layer below stays INFILL-SOLID
g = pp._GeomScan(1.75)
lines = ['M82', 'G0 X5 Y5 Z0.2 F9000']
e = 0.0
e = loop(lines, e, 50, 50, 40, 2400)
e = hatch(lines, e, 56, 56, 28, 28, 6.0, 4800)
lines.append('G0 X5 Y5 Z0.4 F9000')
e = loop(lines, e, 50, 50, 40, 2400)
e = hatch(lines, e, 56, 56, 28, 28, 1.0, 1800)
lines.append('G0 X5 Y5 Z0.6 F9000')
e = loop(lines, e, 50, 50, 40, 2400)
e = hatch(lines, e, 56, 56, 28, 28, 1.0, 1800)
feed(g, lines)
g.finish()
c = feats(g)
ck('top shell: 2 stacked solid layers - only the uppermost flips '
   '(is_last), the lower stays INFILL-SOLID',
   c.get('INFILL-SOLID', 0) == 29 and c.get('SURFACE-TOP', 0) == 29,
   str(dict(c)))

# case FINAL: solid, then the file just ENDS (no layer above at all)
g = pp._GeomScan(1.75)
lines = ['M82', 'G0 X5 Y5 Z0.2 F9000']
e = 0.0
e = loop(lines, e, 50, 50, 40, 2400)
lines.append('G0 X5 Y5 Z0.4 F9000')
e = loop(lines, e, 50, 50, 40, 2400)
e = hatch(lines, e, 56, 56, 28, 28, 1.0, 1800)
lines.append('M107')
feed(g, lines)
g.finish()
c = feats(g)
ck('final pass: solid at the end of the file (nothing ever follows) = '
   'SURFACE-TOP',
   c.get('SURFACE-TOP', 0) == 29 and 'INFILL-SOLID' not in c, str(dict(c)))

# case INTERNAL: sparse below AND sparse above -> INFILL-SOLID both passes
g = pp._GeomScan(1.75)
lines = ['M82', 'G0 X5 Y5 Z0.2 F9000']
e = 0.0
e = loop(lines, e, 50, 50, 40, 2400)
e = hatch(lines, e, 56, 56, 28, 28, 6.0, 4800)
lines.append('G0 X5 Y5 Z0.4 F9000')
e = loop(lines, e, 50, 50, 40, 2400)
e = hatch(lines, e, 56, 56, 28, 28, 1.0, 1800)
lines.append('G0 X5 Y5 Z0.6 F9000')
e = loop(lines, e, 50, 50, 40, 2400)
e = hatch(lines, e, 56, 56, 28, 28, 6.0, 4800)
feed(g, lines)
g.finish()
c = feats(g)
ck('internal solid: sparse above AND below -> stays INFILL-SOLID, the '
   'seq stream stays consistent',
   c.get('INFILL-SOLID', 0) == 29
   and (2, 'INFILL-SOLID') in g.seq193
   and (2, 'SURFACE-TOP') not in g.seq193, str(dict(c)))

print()
if FAIL:
    print('RESULT: FAIL - %d of %d checks failed'
          % (len(FAIL), len(FAIL) + len(PASS)))
    sys.exit(1)
print('RESULT: PASS - %d checks, stage 7 fully pinned' % len(PASS))
