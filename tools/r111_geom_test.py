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
# R181 (.131b) void-side rule: a wall with NOTHING on one side is a
# visible surface = WALL-OUTER - the freestanding nested loop (no fill
# around it) is ALL visible surface. The pre-R181 nesting-depth
# expectation was retired with the layer-picture round.
check('nested freestanding loops -> all WALL-OUTER (void-side rule)',
      feats.count('WALL-OUTER') == 3 and feats.count('WALL-INNER') == 0, feats)

# R186: the WALL-INNER case, pinned explicitly - the ring between the
# two loops is DENSELY hatched: the inner wall has material on BOTH
# sides -> WALL-INNER (the hatch itself = SURFACE-BOTTOM on layer 1).
g = pp._GeomScan(1.75)
lines = ['M82', 'G0 X5 Y5 Z0.2 F9000']
e = 0.0
e = loop(lines, e, 50, 50, 40, 2400)
e = loop(lines, e, 55, 55, 30, 3000)
e = hatch(lines, e, 53, 53, 34, 34, 1.0, 4800)
feed(g, lines)
g.finish()
_feats186 = [f for (_, _, f) in g.ranges]
check('filled ring -> WALL-OUTER + WALL-INNER (material both sides)',
      _feats186.count('WALL-OUTER') == 1
      and _feats186.count('WALL-INNER') == 1
      and _feats186.count('SURFACE-BOTTOM') >= 10, _feats186[:5])

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
# R181 (.131b): open arcs classify LIKE LOOPS - a curved wall is a
# wall (the .131a near-closed rule generalized). The pre-R181
# 'curved stays UNCLASSIFIED' expectation was retired.
# R286: the layer-2 loop (50..90) leans out over the layer-1 arc
# (a semicircle of r=15 at (70,60)): the loop's outer edge has NO ink
# below within the 45-degree cone -> OVERHANG-PERIM. The arc itself
# (layer 1) stays WALL-OUTER.
check('arc -> classified as WALL-OUTER (open arcs like loops, R181);'
      ' layer-2 loop over the sparse arc -> OVERHANG-PERIM (R286)',
      [f for (_, _, f) in g.ranges] == ['WALL-OUTER', 'OVERHANG-PERIM']
      and g.cls_len == g.tot_len, (g.cls_len, g.tot_len, g.ranges))

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
# R186: WALL-INNER is pinned by the filled-ring unit above - this E2E
# fixture hatches INSIDE the inner loop, so its 5mm ring stays void
# and both walls are WALL-OUTER by the void-side rule.
check('E2E TYPES: walls + sparse + bottom + top derived (R286 .137:\n'
      ' the last-layer deck over sparse infill is the TOP surface, not a Bridge)',
      {'WALL-OUTER', 'INFILL-SPARSE', 'SURFACE-BOTTOM',
       'SURFACE-TOP'} <= types, sorted(types))
check('E2E honesty keys: DERIVED=1 CONF>=0.9 COVER>0 (R286: CONF targets 1.0)',
      'DERIVED=1' in fi
      and float(re.search(r'CONF=([0-9.]+)', fi).group(1)) >= 0.9
      and int(re.search(r'COVER=(\d+)', fi).group(1)) >= 80, fi[:150])
check('E2E seam: the outer loop starts at 50,50 (3 layers)',
      'SEAM=50,50' in fi and 'SEAMN=3' in fi,
      re.search(r'SEAM=\S+ SEAMN=\d+', fi).group(0) if 'SEAM=' in fi else 'none')
check('E2E the deck over sparse infill IS the top surface, not a bridge (R286 .137)',
      'SURFACE-TOP' in types and 'BRIDGE' not in types, sorted(types))
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

# ------------------------------------------------- 11) R286 recognition ------
print('--- R286: overhang >45deg + support interface recognition')
# a wall whose outer edge leans out beyond the 45-degree cone of the
# layer below -> OVERHANG-PERIM; a fully supported wall stays WALL-OUTER;
# the uppermost support roof under model ink -> SUPPORT-INTERFACE;
# bare support (no model above) stays SUPPORT.
g = pp._GeomScan(1.75)
lines = ['M82', 'G0 X5 Y5 Z0.2 F9000']
e = hatch(lines, 0.0, 50, 50, 40, 40, 1.0, 1800)
lines.append('G0 X5 Y5 Z0.4 F9000')
e = loop(lines, e, 30, 30, 60, 2400)     # rim 10mm out all around
feed(g, lines)
g.finish()
check('overhanging rim -> OVERHANG-PERIM (R286)',
      'OVERHANG-PERIM' in [f for (_, _, f) in g.ranges], g.ranges[:3])

g = pp._GeomScan(1.75)
lines = ['M82', 'G0 X5 Y5 Z0.2 F9000']
e = hatch(lines, 0.0, 50, 50, 40, 40, 1.0, 1800)
lines.append('G0 X5 Y5 Z0.4 F9000')
e = loop(lines, e, 50, 50, 40, 2400)     # same footprint as the block
feed(g, lines)
g.finish()
check('supported wall -> WALL-OUTER, no overhang tag (R286)',
      'OVERHANG-PERIM' not in [f for (_, _, f) in g.ranges]
      and 'WALL-OUTER' in [f for (_, _, f) in g.ranges], g.ranges[:3])

# support tower (detached, prints first) under a model roof -> the roof
# layer resolves the tower to SUPPORT-INTERFACE
g = pp._GeomScan(1.75)
lines = ['M82']
e = 0.0
for z in (0.2, 0.4, 0.6):
    lines.append('G0 X5 Y5 Z%.1f F9000' % z)
    e = hatch(lines, e, 50, 50, 40, 40, 1.0, 1800)
lines.append('G0 X5 Y5 Z0.8 F9000')
e = hatch(lines, e, 100, 100, 12, 12, 1.0, 1800)   # support tower first
e = hatch(lines, e, 50, 50, 40, 40, 1.0, 1800)    # model body
lines.append('G0 X5 Y5 Z1.0 F9000')
e = hatch(lines, e, 100, 100, 12, 12, 1.0, 1800)   # model roof
e = hatch(lines, e, 50, 50, 40, 40, 1.0, 1800)
feed(g, lines)
g.finish()
check('support roof under model -> SUPPORT-INTERFACE (R286)',
      'SUPPORT-INTERFACE' in [f for (_, _, f) in g.ranges],
      sorted(set(f for (_, _, f) in g.ranges)))

g = pp._GeomScan(1.75)
lines = ['M82']
e = 0.0
for z in (0.2, 0.4, 0.6):
    lines.append('G0 X5 Y5 Z%.1f F9000' % z)
    e = hatch(lines, e, 50, 50, 40, 40, 1.0, 1800)
lines.append('G0 X5 Y5 Z0.8 F9000')
e = hatch(lines, e, 100, 100, 12, 12, 1.0, 1800)
e = hatch(lines, e, 50, 50, 40, 40, 1.0, 1800)
lines.append('G0 X5 Y5 Z1.0 F9000')
e = hatch(lines, e, 50, 50, 40, 40, 1.0, 1800)     # no roof over tower
feed(g, lines)
g.finish()
check('bare support -> SUPPORT, no interface tag (R286)',
      'SUPPORT-INTERFACE' not in [f for (_, _, f) in g.ranges]
      and 'SUPPORT' in [f for (_, _, f) in g.ranges],
      sorted(set(f for (_, _, f) in g.ranges)))

# ------------------------------------------------- 12) R286 layer order -------
print('--- R286: no Top on Top, no Bottom on Bottom, no Top on sparse infill')
# a second solid deck on a layer that already carried Top surface must
# NOT become another Top (it is internal solid); a second Bottom on a
# Bottom layer likewise; a deck directly over Sparse infill is a Bridge.
g = pp._GeomScan(1.75)
lines = ['M82']
e = 0.0
for z in (0.2, 0.4):
    lines.append('G0 X5 Y5 Z%.1f F9000' % z)
    e = hatch(lines, e, 50, 50, 40, 40, 1.0, 1800)
lines.append('G0 X5 Y5 Z0.6 F9000')
e = hatch(lines, e, 50, 50, 40, 40, 1.0, 1800)
lines.append('G0 X5 Y5 Z0.8 F9000')
e = hatch(lines, e, 50, 50, 40, 40, 1.0, 1800)
feed(g, lines)
g.finish()
# the top surface sits on the LAST layer only; the layers above the
# first layer are internal solid, never a second Top.
_top_layers = [ln for (ln, f) in g.seq193 if f == 'SURFACE-TOP']
_bot_layers = [ln for (ln, f) in g.seq193 if f == 'SURFACE-BOTTOM']
check('no Top on Top - Top only on the last layer (R286)',
      _top_layers == [g.layers_classified] and _bot_layers == [1],
      (g.seq193, _top_layers, _bot_layers))

g = pp._GeomScan(1.75)
lines = ['M82']
e = 0.0
# layer 1 = dense hatch (Bottom surface), layer 2 = dense hatch again -
# the second layer must NOT be another Bottom surface. The layer stream
# (seq193) shows the rule: Bottom only on layer 1, the top surface on
# the last layer.
lines.append('G0 X5 Y5 Z0.2 F9000')
e = hatch(lines, e, 50, 50, 40, 40, 1.0, 1800)
lines.append('G0 X5 Y5 Z0.4 F9000')
e = hatch(lines, e, 50, 50, 40, 40, 1.0, 1800)
feed(g, lines)
g.finish()
_bot_layers = [ln for (ln, f) in g.seq193 if f == 'SURFACE-BOTTOM']
_top_layers = [ln for (ln, f) in g.seq193 if f == 'SURFACE-TOP']
check('no Bottom on Bottom - Bottom only on the first layer (R286)',
      _bot_layers == [1] and _top_layers == [g.layers_classified],
      (g.seq193, _bot_layers, _top_layers))

g = pp._GeomScan(1.75)
lines = ['M82', 'G0 X5 Y5 Z0.2 F9000']
e = hatch(lines, 0.0, 50, 50, 40, 40, 1.0, 1800)
lines.append('G0 X5 Y5 Z0.4 F9000')
e = hatch(lines, e, 50, 50, 40, 40, 8.0, 1800)   # sparse infill
lines.append('G0 X5 Y5 Z0.6 F9000')
e = hatch(lines, e, 50, 50, 40, 40, 1.0, 1800)   # deck over sparse
feed(g, lines)
g.finish()
_feats_sp = [f for (_, _, f) in g.ranges]
# R286 .137: sparse infill is MATERIAL (the airscan 3% floor counts it), so a
# dense deck over it is supported, never a void bridge. On the LAST layer the
# deck IS the top surface (SURFACE-TOP, the print ends there - never bridge
# speed); on a MID layer it is internal solid (INFILL-SOLID). Neither is BRIDGE.
check('last-layer deck over sparse infill -> SURFACE-TOP, not BRIDGE (R286 .137)',
      'SURFACE-TOP' in _feats_sp and 'BRIDGE' not in _feats_sp,
      sorted(set(_feats_sp)))

# a mid-layer deck over sparse infill is internal solid (supported), not a bridge
g = pp._GeomScan(1.75)
lines = ['M82', 'G0 X5 Y5 Z0.2 F9000']
e = hatch(lines, 0.0, 50, 50, 40, 40, 1.0, 1800)
lines.append('G0 X5 Y5 Z0.4 F9000')
e = hatch(lines, e, 50, 50, 40, 40, 8.0, 1800)   # sparse infill
lines.append('G0 X5 Y5 Z0.6 F9000')
e = hatch(lines, e, 50, 50, 40, 40, 1.0, 1800)   # deck (mid layer)
lines.append('G0 X5 Y5 Z0.8 F9000')
e = hatch(lines, e, 50, 50, 40, 40, 1.0, 1800)   # top (last layer)
feed(g, lines)
g.finish()
_feats_mid = [f for (_, _, f) in g.ranges]
check('mid-layer deck over sparse infill -> INFILL-SOLID, not BRIDGE (R286 .137)',
      'INFILL-SOLID' in _feats_mid and 'BRIDGE' not in _feats_mid,
      sorted(set(_feats_mid)))

print()
if fails:
    print('R111 GEOM CLASSIFIER: %d FAILURE(S)' % len(fails))
    sys.exit(1)
print('R111 GEOM CLASSIFIER: all checks passed')
