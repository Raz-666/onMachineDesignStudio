#!/usr/bin/env python3
"""R216 string-art check (pinned): the .136n field round on STRING ART.

The field test print (string art spiral) brought seven findings, all
pinned here:

  1. FLOW: every E value is FILAMENT mm again (divided by the 1.75mm
     cross-section FIL_AREA - the old numbers were volumetric scale,
     the print came out ~2.4x over-extruded).
  2. TEMPS: the file carries its temperatures (PRINT_START
     BED/BED_AFTER/HOTEND_FIRST/HOTEND_AFTER + _FILE_INFO HOTEND/BED)
     - the preheat fell back to filament-swap level before.
  3. BOW: each strand runs as a 2mm bow in Z (up from the band, over,
     back down) - the nozzle never drags through the strands laid
     before; the strand-to-strand travel hops OVER the bows.
  4. DIRECTION: strands are pulled from ALTERNATING directions.
  5. SPREAD: the laying order keeps consecutive strand starts >= 15 deg
     apart (_spread_starts - 'not thread after thread from the same
     corner, just to be safe').
  6. FRAME: shape=RECT + size_w/size_h builds a RECTANGULAR frame ring
     with the photo-size presets (9x13/10x15/13x18/15x20/18x24 - the
     Frames sizes), so string art drops into the Frames system.
  7. RING: 2 walls on every layer + 3 solid bottom layers + 3 solid
     top layers + 5 % sparse infill between (not solid all the way up).

Run:  python3 tools/r216_stringart_check.py
"""
import math
import os
import re
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import r2_postproc as pp  # noqa: E402

try:
    from PIL import Image, ImageDraw
    HAVE_PIL = True
except ImportError:
    HAVE_PIL = False

PASS = []
FAIL = []


def ck(name, ok, detail=''):
    (PASS if ok else FAIL).append(name)
    print('%-4s %s%s' % ('PASS' if ok else 'FAIL', name,
                         ('  [%s]' % detail) if detail and not ok else ''))


D = tempfile.mkdtemp(prefix='r216sa_')
BED = (0.0, -3.0, 244.0, 238.0)

# ---------------- 1) flow: E is filament mm -------------------------------
out, info = pp.make_string_art(pattern='SPIRAL', diameter=120.0, anchors=60,
                               lines=120, ring_h=2.4, arc=2.0, out_dir=D,
                               bed=BED)
txt = open(out).read()
Emm = 0.5 * 0.068 / pp.FIL_AREA
lines = open(out).read().split('\n')
strand_e = []
cur_e = cur_len = 0.0
px = py = pz = None
started = False
in_band = False
for ln in lines:
    if ln.startswith(';TYPE:Bridge'):
        in_band = True
    if ln == 'G10' and in_band:
        if started and cur_len > 1:
            strand_e.append((cur_e, cur_len))
        cur_e = cur_len = 0.0
        started = True
        px = py = pz = None
        continue
    m = re.match(r'G1 X([\d.-]+) Y([\d.-]+)(?: Z([\d.-]+))? E([\d.]+)', ln)
    if m and started:
        x, y = float(m.group(1)), float(m.group(2))
        z = float(m.group(3)) if m.group(3) else (pz or 0)
        if px is not None:
            cur_len += math.sqrt((x - px) ** 2 + (y - py) ** 2
                                 + (z - pz) ** 2)
        px, py, pz = x, y, z
        cur_e += float(m.group(4))
if started and cur_len > 1:
    strand_e.append((cur_e, cur_len))
devs = sorted((e / l) / Emm for (e, l) in strand_e)
med = devs[len(devs) // 2]
ck('flow: strand E is filament mm (median E/mm ratio %.3f, was ~%.1f '
   'before - volumetric scale)' % (med, pp.FIL_AREA),
   0.9 < med < 1.1, 'median %r' % med)

# ring walls too: wall E per mm = wid*eff/FIL_AREA (~0.041/mm for
# 0.5x0.2) - NOT the old volumetric ~0.1/mm
wall_segs = re.findall(r'G1 X([\d.-]+) Y([\d.-]+) E([\d.]+)', txt)
wdev = []
lastp = None
for (xs_, ys_, es_) in wall_segs:
    x, y, e = float(xs_), float(ys_), float(es_)
    if lastp is not None:
        dl = math.hypot(x - lastp[0], y - lastp[1])
        if dl > 0.5:
            wdev.append(e / dl)
    lastp = (x, y)
wmed = sorted(wdev)[len(wdev) // 2] if wdev else 0
expect_w = 0.5 * 0.2 / pp.FIL_AREA
ck('flow: ring walls at filament scale too (median %.4f/mm, expect ~%.4f)'
   % (wmed, expect_w),
   expect_w * 0.8 < wmed < expect_w * 1.25, 'median %r' % wmed)

# ---------------- 2) temps -------------------------------------------------
ck('temps: PRINT_START carries BED/HOTEND_FIRST/HOTEND_AFTER',
   'HOTEND_FIRST=225' in txt and 'BED=60 BED_AFTER=55' in txt
   and 'HOTEND_AFTER=220' in txt, '')
ck('temps: _FILE_INFO carries HOTEND/BED (the preview shows them)',
   'HOTEND=220 BED=60' in txt, '')

# ---------------- 3) bow + travel over the bows ----------------------------
segs = re.findall(r'G1 X([\d.]+) Y([\d.]+) Z([\d.]+) E([\d.]+)', txt)
zs = sorted(set(round(float(m[2]), 2) for m in segs))
ring_top = round(0.28 + 11 * 0.2, 3)     # 12 layers, first 0.28
band1 = round(ring_top + 0.20, 3)
band1z = [float(m[2]) for m in segs if band1 - 0.01 <= float(m[2])]
ck('bow: strand Z rises arc-like above the band and returns '
   '(band %.2f + 2mm bow)' % band1,
   len(zs) > 8 and any(abs(z - (band1 + 2.0)) < 0.35 for z in band1z)
   and band1 in [round(z, 3) for z in zs],
   'zs=%s' % zs[:8])
ck('bow: the strand travel hops OVER the bows (Z band+arc+0.5)',
   ('G0 Z%.3f' % (band1 + 2.5)) in txt, '')

# ---------------- 4) alternating pull direction ----------------------------
# band 1 strand starts: anchors 15 deg apart walking the ring; the
# chords must alternate direction: start_i+1 -> end, then reversed
ck('direction: the emit loop alternates (si %% 2 swaps i/j) - pinned '
   'by code presence',
   'if si % 2:' in open('tools/r2_postproc.py').read(), '')

# ---------------- 5) spread ------------------------------------------------
plan = [(k % 60, (k + 20) % 60) for k in range(120)]
sp = pp._spread_starts(plan, 60, 15.0)
mind = min(min(abs(b[0] - a[0]), 60 - abs(b[0] - a[0]))
           for a, b in zip(sp, sp[1:]))
ck('spread: consecutive starts >= 15 deg apart (60 anchors -> >= 3)',
   mind >= 3 and len(sp) == 120, 'min %d' % mind)
sp2 = pp._spread_starts(plan, 360, 15.0)
mind2 = min(min(abs(b[0] - a[0]), 360 - abs(b[0] - a[0]))
            for a, b in zip(sp2, sp2[1:]))
ck('spread: 360 anchors -> >= 15 anchors apart',
   mind2 >= 15 and len(sp2) == 120, 'min %d' % mind2)
ck('spread: a saturated plan (all from one anchor) still emits '
   'everything',
   len(pp._spread_starts([(7, 30)] * 10, 60, 15.0)) == 10, '')

# ---------------- 6) RECT frame + presets ----------------------------------
out2, info2 = pp.make_string_art(pattern='SPIRAL', shape='RECT', size_w=102,
                                 size_h=152, anchors=80, lines=100,
                                 ring_h=2.0, arc=2.0, out_dir=D, bed=BED)
txt2 = open(out2).read()
tr = re.findall(r'G0 X([\d.]+) Y([\d.]+) F\d+', txt2)
xs = [float(t[0]) for t in tr]
ys = [float(t[1]) for t in tr]
oncl = sum(1 for x, y in zip(xs, ys)
           if (abs(abs(x - 122.0) - 48.5) < 0.01
               or abs(abs(y - 117.5) - 73.5) < 0.01))
ck('frame: RECT anchors sit exactly on the ring centerline '
   '(102x152 -> 48.5/73.5 half extents)',
   oncl >= 90, '%d travels on the line' % oncl)
ck('frame: the name carries the size (fits the Frames system)',
   '_102x152' in info2['file'], info2['file'])
ck('frame: the bed guard clamps an oversized frame',
   pp.make_string_art(pattern='SPIRAL', shape='RECT', size_w=400,
                      size_h=390, anchors=60, lines=60, out_dir=D,
                      bed=BED)[1]['notes'] != [],
   'no clamp note')

# ---------------- 7) the ring: walls + solid/sparse/solid ------------------
ck('ring: 3 solid bottom + 3 solid top layers (12-layer ring)',
   txt.count(';TYPE:Internal solid infill') >= 6,
   '%d solid fills' % txt.count(';TYPE:Internal solid infill'))
ck('ring: 5% sparse infill between (the sparse type appears)',
   ';TYPE:Sparse infill' in txt, '')
ck('ring: two walls on every layer (outer + inner)',
   txt.count(';TYPE:Outer wall') >= 12
   and txt.count(';TYPE:Inner wall') >= 12, '')
ck('ring: INFILL-SPARSE is in the file TYPES (feature menus know it)',
   'INFILL-SPARSE' in txt.split('\n')[0:40].__str__()
   or 'INFILL-SPARSE' in txt[:2500], '')

# ring height drives the layer count
out3, info3 = pp.make_string_art(pattern='SPIRAL', diameter=100.0,
                                 anchors=40, lines=40, ring_h=4.0,
                                 out_dir=D, bed=BED)
ck('ring: ring_h=4.0 grows the ring (more layers than 2.4)',
   info3['ring_layers'] > info['ring_layers'],
   '%d vs %d' % (info3['ring_layers'], info['ring_layers']))

# ---------------- 8) PHOTO on a rect (the planner respects the aspect) -----
if HAVE_PIL:
    img = os.path.join(D, 't.png')
    im = Image.new('L', (320, 240), 240)
    dr = ImageDraw.Draw(im)
    dr.ellipse((90, 50, 230, 190), fill=30)
    im.save(img)
    out4, info4 = pp.make_string_art(src=img, pattern='PHOTO', shape='RECT',
                                     size_w=102, size_h=152, anchors=100,
                                     lines=150, ring_h=2.0, arc=2.0,
                                     out_dir=D, grid=60, n_cand=80, bed=BED)
    t4 = open(out4).read()
    mid = re.findall(r'G1 X([\d.]+) Y([\d.]+) Z[\d.]+ E[\d.]+', t4)
    mx = [float(m[0]) for m in mid]
    my = [float(m[1]) for m in mid]
    # the anchors sit ON the centerline, the wrap curls reach 0.3mm
    # beyond it - the window allows exactly that
    inside = sum(1 for x, y in zip(mx, my)
                 if 72.9 <= x <= 171.1 and 43.9 <= y <= 191.1)
    ck('photo RECT: the weave stays inside the frame '
       '(aspect-cropped planner)',
       info4['lines'] == 150 and inside >= len(mid) * 0.995,
       '%d/%d inside' % (inside, len(mid)))
else:
    print('SKIP photo test (no PIL)')

print()
if FAIL:
    print('RESULT: FAIL - %d of %d checks failed'
          % (len(FAIL), len(FAIL) + len(PASS)))
    sys.exit(1)
print('RESULT: PASS - %d checks, the string-art field round fully pinned'
      % len(PASS))
