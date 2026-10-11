#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""R111: unit + end-to-end tests for the geometry classifier (_GeomScan).

The classifier is the honest fallback for files WITHOUT ;TYPE: tags (roadmap
L3+/L4 in docs/FEATURE_TAGGING.md): walls per closed-loop nesting, infill per
hatch spacing, bottom/top per layer position. This test pins down:

  - dense hatch on layer 1        -> SURFACE-BOTTOM
  - dense hatch on the last layer -> SURFACE-TOP
  - wide hatch (gap >= 3 mm)      -> INFILL-SPARSE
  - closed loops with bbox nesting -> WALL-OUTER / WALL-INNER
  - curved open paths             -> UNCLASSIFIED (no silent guessing)
  - Z-hop travels never fake a layer change (modal-Z semantics)
  - the point cap keeps memory bounded (rest of the layer stays unclassified)
  - end-to-end process(): DERIVED=1 CONF=0.7 COVER=.. TYPES=.. SEAM=..
  - a tagged file is NEVER classified (the first ;TYPE: disarms the heavy
    part) but still gets the LIGHT keys (MAXRATE, SEAM)
  - idempotency

Run: python3 tools/r111_geom_test.py   (exit 0 = all green)
"""
import os
import re
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import r2_postproc as pp  # noqa: E402

D = tempfile.mkdtemp(prefix='r111_geom_')
fails = []


def check(name, ok, info=''):
    if not ok:
        fails.append(name)
        print('  FAIL %s %s' % (name, str(info)[:220]))
    else:
        print('  ok   %s' % name)


# ---------------------------------------------------------------- helpers ----
def loop(out, e, x0, y0, w, f):
    """travel to the corner, then a closed square loop"""
    out.append('G0 X%.1f Y%.1f F9000' % (x0, y0))
    for (x, y) in [(x0 + w, y0), (x0 + w, y0 + w), (x0, y0 + w), (x0, y0)]:
        e += w * 0.05
        out.append('G1 X%.1f Y%.1f F%d E%.3f' % (x, y, f, e))
    return e


def hatch(out, e, x0, y0, w, h, gap, f):
    """zigzag of straight parallel X lines, `gap` mm apart"""
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


def arc(out, e, cx, cy, r, f, n=24):
    """curved open path (semicircle) - must stay UNCLASSIFIED"""
    out.append('G0 X%.1f Y%.1f F9000' % (cx - r, cy))
    import math
    for k in range(1, n + 1):
        a = math.pi * k / n
        e += 0.12
        out.append('G1 X%.2f Y%.2f F%d E%.3f'
                   % (cx - r * math.cos(a), cy + r * math.sin(a), f, e))
    return e


def feed(g, lines):
    for i, l in enumerate(lines):
        g.step(i, i, l)


def info_line(path):
    txt = open(path, errors='replace').read()
    m = re.search(r'_FILE_INFO (.*)', txt)
    return m.group(1) if m else ''


# ------------------------------------------------- 1) dense hatch layer 1 ----
print('--- layer 1 dense hatch -> SURFACE-BOTTOM')
g = pp._GeomScan(1.75)
lines = ['M82', 'G0 X5 Y5 Z0.2 F9000']
e = 0.0
e = hatch(lines, e, 56, 56, 28, 6, 1.0, 1800)
lines.append('G0 X5 Y5 Z0.4 F9000')
e += 1.4
lines.append('G1 X50 Y50 F2400 E%.3f' % e)
feed(g, lines)
g.finish()
check('dense hatch layer 1 -> SURFACE-BOTTOM',
      all(f == 'SURFACE-BOTTOM' for (_, _, f) in g.ranges) and g.ranges,
      g.ranges[:4])

# ------------------------------------------------- 2) dense hatch last -------
print('--- last layer dense hatch -> SURFACE-TOP')
g = pp._GeomScan(1.75)
lines = ['M82', 'G0 X5 Y5 Z0.2 F9000']
e = 0.0
e = loop(lines, e, 50, 50, 40, 2400)
lines.append('G0 X5 Y5 Z0.4 F9000')
e = hatch(lines, e, 56, 56, 28, 6, 1.0, 1800)
feed(g, lines)
g.finish()
feats = set(f for (_, _, f) in g.ranges)
check('last layer dense hatch -> SURFACE-TOP',
      'SURFACE-TOP' in feats and 'INFILL-SOLID' not in feats, sorted(feats))

# ------------------------------------------------- 3) wide hatch -------------
print('--- wide hatch (6 mm) -> INFILL-SPARSE')
g = pp._GeomScan(1.75)
lines = ['M82', 'G0 X5 Y5 Z0.2 F9000']
e = 0.0
e = loop(lines, e, 50, 50, 40, 2400)
lines.append('G0 X5 Y5 Z0.4 F9000')
e = hatch(lines, e, 56, 56, 28, 24, 6.0, 4800)
feed(g, lines)
g.finish()
feats = [f for (_, _, f) in g.ranges]
check('wide hatch -> INFILL-SPARSE',
      feats.count('INFILL-SPARSE') >= 5 and 'INFILL-SOLID' not in feats, feats[:6])

# ------------------------------------------------- 4) loop nesting -----------
print('--- closed loops with nesting -> WALL-OUTER + WALL-INNER')
g = pp._GeomScan(1.75)
lines = ['M82', 'G0 X5 Y5 Z0.2 F9000']
e = 0.0
e = loop(lines, e, 50, 50, 40, 2400)      # outer 40x40
e = loop(lines, e, 55, 55, 30, 3000)      # nested 30x30
e = loop(lines, e, 100, 60, 20, 2400)     # separate island, no nesting
feed(g, lines)
g.finish()
feats = [(f) for (_, _, f) in g.ranges]
check('nested loops -> 2x WALL-OUTER + 1x WALL-INNER',
      feats.count('WALL-OUTER') == 2 and feats.count('WALL-INNER') == 1, feats)

# ------------------------------------------------- 5) curved -> unclassified -
print('--- curved open path stays UNCLASSIFIED')
g = pp._GeomScan(1.75)
lines = ['M82', 'G0 X5 Y5 Z0.2 F9000']
e = 0.0
e = arc(lines, e, 70, 60, 15, 1800)
lines.append('G0 X5 Y5 Z0.4 F9000')
e = loop(lines, e, 50, 50, 40, 2400)
feed(g, lines)
g.finish()
check('arc -> only the loop classified, COVER < 100%',
      [f for (_, _, f) in g.ranges] == ['WALL-OUTER']
      and 0 < g.cls_len < g.tot_len, (g.cls_len, g.tot_len))

# ------------------------------------------------- 6) Z-hop never a layer ----
print('--- Z-hop travels never fake a layer (modal-Z)')
g = pp._GeomScan(1.75)
lines = ['M82', 'G0 X5 Y5 Z0.2 F9000']
e = 0.0
e = loop(lines, e, 50, 50, 40, 2400)
# hop: up, travel, down, continue printing the SAME layer
lines.append('G0 X5 Y5 Z0.6 F9000')
lines.append('G0 X5 Y5 Z0.2 F9000')
e = loop(lines, e, 100, 50, 20, 2400)
lines.append('G0 X5 Y5 Z0.6 F9000')
lines.append('G0 X5 Y5 Z0.2 F9000')
e = loop(lines, e, 130, 50, 10, 2400)
feed(g, lines)
g.finish()
check('hops did not split the layer (1 classify run, all WALL-OUTER)',
      g.layers_classified == 1
      and all(f == 'WALL-OUTER' for (_, _, f) in g.ranges)
      and len(g.ranges) == 3,
      (g.layers_classified, g.ranges[:3]))

# ------------------------------------------------- 7) point cap --------------
print('--- point cap: the rest of the layer stays unclassified')
g = pp._GeomScan(1.75)
g._pts_budget = 2          # one tiny polyline, then the budget is gone
lines = ['M82', 'G0 X5 Y5 Z0.2 F9000']
e = 0.0
e = loop(lines, e, 50, 50, 40, 2400)
e = loop(lines, e, 60, 60, 20, 2400)
feed(g, lines)
g.finish()
check('cap stops buffering (at most 1 range)',
      len(g.ranges) <= 1, g.ranges)

# ------------------------------------------------- 8) end-to-end process() ---
print('--- end-to-end: untagged file through process()')
out = ['; generated by MysterySlicer 0.9', 'M82', 'G28', 'G90',
       'M104 S200', 'M140 S60']
e = 0.0
out.append('G0 X5 Y5 Z0.2 F9000')
e = loop(out, e, 50, 50, 40, 1800)
e = loop(out, e, 55, 55, 30, 1800)
e = hatch(out, e, 56, 56, 28, 28, 1.0, 1800)      # layer 1 solid
out.append('G0 X5 Y5 Z0.4 F9000')
e = loop(out, e, 50, 50, 40, 2400)
e = loop(out, e, 55, 55, 30, 3000)
e = hatch(out, e, 56, 56, 28, 28, 6.0, 4800)      # sparse
out.append('G0 X5 Y5 Z0.6 F9000')
e = loop(out, e, 50, 50, 40, 1800)
e = loop(out, e, 55, 55, 30, 1800)
e = hatch(out, e, 56, 56, 28, 28, 1.0, 1800)      # top solid
out += ['M104 S0', 'M140 S0']
p1 = os.path.join(D, 'untagged.gcode')
open(p1, 'w').write('\n'.join(out) + '\n')
summ = pp.process(p1)
fi = info_line(p1)
types = set(re.findall(r'APPLY_TYPE TYPE=(\S+)', open(p1).read()))
check('E2E TYPES: walls + sparse + bottom + top derived',
      {'WALL-OUTER', 'WALL-INNER', 'INFILL-SPARSE', 'SURFACE-BOTTOM',
       'SURFACE-TOP'} <= types, sorted(types))
check('E2E honesty keys: DERIVED=1 CONF=0.7 COVER>0',
      'DERIVED=1' in fi and 'CONF=0.7' in fi
      and int(re.search(r'COVER=(\d+)', fi).group(1)) >= 80, fi[:150])
check('E2E seam: the outer loop starts at 50,50 (3 layers)',
      'SEAM=50,50' in fi and 'SEAMN=3' in fi,
      re.search(r'SEAM=\S+ SEAMN=\d+', fi).group(0) if 'SEAM=' in fi else 'none')
check('E2E no BRIDGE ever guessed',
      'BRIDGE' not in types and 'BRIDGE' not in fi, '')
summ2 = pp.process(p1)
check('E2E idempotent (second run skips)',
      summ2.get('skipped') is True, summ2)

# ------------------------------------------------- 9) tagged file ------------
print('--- tagged file: heavy part disarmed, light keys still come')
out = ['; generated by OrcaSlicer 2.2.0', 'M82', 'G28', 'G90',
       'M104 S200', 'M140 S60']
e = 0.0
out.append('G0 X5 Y5 Z0.2 F9000')
out.append(';TYPE:Outer wall')
e = loop(out, e, 50, 50, 40, 2400)
out.append(';TYPE:Sparse infill')
e = hatch(out, e, 56, 56, 28, 28, 6.0, 4800)
out += ['M104 S0', 'M140 S0']
p2 = os.path.join(D, 'tagged.gcode')
open(p2, 'w').write('\n'.join(out) + '\n')
pp.process(p2)
fi2 = info_line(p2)
types2 = set(re.findall(r'APPLY_TYPE TYPE=(\S+)', open(p2).read()))
check('tagged file: TYPES only from the ;TYPE: tags',
      types2 == {'WALL-OUTER', 'INFILL-SPARSE'}, sorted(types2))
check('tagged file: NO DERIVED keys (tags always win)',
      'DERIVED' not in fi2, fi2[:150])
check('tagged file: light keys still measured (MAXRATE + SEAM)',
      'MAXRATE=' in fi2 and 'SEAM=' in fi2, fi2[:150])

# ------------------------------------------------- 10) volumetric rate -------
print('--- MAXRATE: feed vs geometry sanity')
g = pp._GeomScan(1.75)          # area = pi*(0.875)^2 = 2.405 mm2
lines = ['M82', 'G0 X0 Y0 Z0.2 F9000', 'G1 X10 Y0 F60 E2.0']   # 1 mm/s, 0.2 mm/mm
feed(g, lines)
g.finish()
# rate = 1 mm/s * 0.2 * 2.405 = 0.481 mm3/s
check('MAXRATE math (1 mm/s x 0.2 mm/mm x 2.405 mm2 = 0.48)',
      abs(g.max_rate - (1.0 * 0.2 * 2.405)) < 0.01, g.max_rate)

print()
if fails:
    print('R111 GEOM CLASSIFIER: %d FAILURE(S)' % len(fails))
    sys.exit(1)
print('R111 GEOM CLASSIFIER: all checks passed')
