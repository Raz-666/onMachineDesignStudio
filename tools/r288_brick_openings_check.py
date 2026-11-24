#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""R288 (field report 17.11.2026): bricks must STACK - openings pinned.

The field found every generated brick a solid slab: studs on top, but the
underside skinned shut (the old 'layer 1 prints SOLID' rule), 1xN parts
filled wall to wall, round parts plugged, and the technic side holes
sealed behind full-length walls (visible as ghost circles on the flank).

This suite pins the fix at the G-code level:
  1. tube rings print FROM LAYER 1 (the underside is open, studs plug in)
  2. 1xN parts keep a HOLLOW core up to the cap (no tubes fit there)
  3. tech hole bands run SEGMENTED long walls (the channel breaks through
     both long sides; the bridge layer above still closes the roof)
  4. every part still ends in a closed top (the cap stays solid)

Run:  python3 tools/r288_brick_openings_check.py   (from the repo root)
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


def layers_of(txt):
    return [b for b in txt.split(';LAYER_CHANGE') if ';Z:' in b[:200]]


def part_block(layer_txt, code):
    for p in layer_txt.split('EXCLUDE_OBJECT_START NAME=')[1:]:
        if p.split()[0].endswith(code):
            return p.split('EXCLUDE_OBJECT_END')[0]
    return ''


def extrusions(txt):
    """(x, y, e>0) moves with modal position tracking (travels included)."""
    px = py = None
    out = []
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
    jobs=[('B2x4', 1), ('B1x4', 1), ('P1x2', 1), ('H1x4', 1),
          ('R1x1', 1), ('S2x3', 1), ('T2x2', 1)],
    bed=BED, out_dir=d)
txt = open(out).read()
L = layers_of(txt)

# ---- 1: tube rings from layer 1 ------------------------------------------
# B2x4 has 3 tubes; their rings are small closed loops (many short moves).
l1 = L[0]
b1 = part_block(l1, 'B2x4')
segs = extrusions(b1)
small = sum(1 for (x0, y0, x1, y1) in segs
            if abs(x1 - x0) < 1.3 and abs(y1 - y0) < 1.3)
ck('B2x4 layer 1 carries the tube rings (open underside)',
   small >= 60, '%d circle segments on layer 1' % small)

s1 = part_block(l1, 'S2x3')
segs = extrusions(s1)
small = sum(1 for (x0, y0, x1, y1) in segs
            if abs(x1 - x0) < 1.3 and abs(y1 - y0) < 1.3)
ck('slope layer 1 carries its rear tube rings too',
   small >= 30, '%d circle segments' % small)

# ---- 2: 1xN hollow core ----------------------------------------------------
mid = None
for b in L:
    z = float([l for l in b.split('\n') if l.startswith(';Z:')][0][3:])
    if 2.0 < z < 8.0:
        mid = b
        break
bn = part_block(mid, 'B1x4')
ck('B1x4 body stays hollow (2 wall loops, no infill hatch)',
   0 < len(extrusions(bn)) <= 12, '%d extruding moves' % len(extrusions(bn)))

# ---- 3: tech holes break through -------------------------------------------
hole_layer = None
for b in L:
    z = float([l for l in b.split('\n') if l.startswith(';Z:')][0][3:])
    if abs(z - 5.8) <= 0.11:
        hole_layer = b
        break
h = part_block(hole_layer, 'H1x4')
verts = [(x0, y0, y1) for (x0, y0, x1, y1) in extrusions(h)
         if abs(x1 - x0) < 0.01 and abs(y1 - y0) > 0.3]
longest = max((abs(y1 - y0) for (_, y0, y1) in verts), default=0.0)
ck('H1x4 hole band: long walls segmented (no full-length side wall)',
   len(verts) >= 8 and longest < 10.0,
   '%d segments, longest %.2fmm' % (len(verts), longest))

# the layer right above the channel (hole center 5.8 + radius 2.45 -> the
# band ends at ~8.25mm) must bridge full walls again
above = None
for b in L:
    z = float([l for l in b.split('\n') if l.startswith(';Z:')][0][3:])
    if 8.4 < z < 9.2:
        above = b
        break
ha = part_block(above, 'H1x4')
verts_a = [abs(y1 - y0) for (x0, y0, x1, y1) in extrusions(ha)
           if abs(x1 - x0) < 0.01]
ck('H1x4 above the channel: full walls close the roof (bridge)',
   bool(verts_a) and max(verts_a) > 20.0,
   'longest %.2fmm' % (max(verts_a) if verts_a else 0.0))

# ---- 4: caps stay solid ----------------------------------------------------
last = L[-1]
cap = part_block(last, 'B2x4')
ck('B2x4 top cap still closes solid (studs sit on a sealed top)',
   len(extrusions(cap)) > 30, '%d cap moves' % len(extrusions(cap)))

print()
if FAIL:
    print('RESULT: FAIL - %d of %d checks failed'
          % (len(FAIL), len(FAIL) + len(PASS)))
    sys.exit(1)
print('RESULT: PASS - %d checks, bricks are open where they must be'
      % len(PASS))
