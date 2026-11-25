#!/usr/bin/env python3
"""R216 fixes check (pinned): QUALITY fix + SPEED fix (Pre-Print > Fixes).

QUALITY fix (.136n user wish): the travel golden rule on a real sliced
file. A travel may only cost retract + Z-hop when it actually CROSSES
freshly printed plastic of the same layer - endpoint touches and
parallel neighbor lines never count. Non-crossing armor blocks drop
their retract/hop (G10/G11 pairs, E-only retracts, wipes, hops);
crossing blocks keep everything; naked crossings (ink, no retract at
all) are counted and reported. The feature recognition stage is used
for the travel detection ONLY - no feature is re-tagged.

SPEED fix (.136n user wish): direct ways - consecutive travel lines
merge into ONE move with the effective modal X/Y/F (position after the
block identical); ironing skipped - the whole ironing block
(;TYPE:Ironing / ;FEATURE:Ironing / APPLY_TYPE TYPE=IRONING) drops its
extrusion moves, with a G92 E stitch so absolute-E files keep their
meaning.

Run:  python3 tools/r216_fixes_check.py
"""
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import r2_postproc as pp  # noqa: E402

PASS = []
FAIL = []


def ck(name, ok, detail=''):
    (PASS if ok else FAIL).append(name)
    print('%-4s %s%s' % ('PASS' if ok else 'FAIL', name,
                         ('  [%s]' % detail) if detail and not ok else ''))


D = tempfile.mkdtemp(prefix='r216fixchk_')


def qual_fixture(name, blocks):
    """M83 file: a printed square + the given armor blocks"""
    lines = ['M83', 'G90', 'G0 X10 Y10 Z0.2 F9000',
             ';LAYER_CHANGE', 'G1 Z0.2 F600', ';TYPE:Wall outer',
             'G1 X50 Y10 E1 F1800', 'G1 X50 Y50 E2', 'G1 X10 Y50 E3',
             'G1 X10 Y10 E4']
    lines += blocks
    lines += ['M107', 'PRINT_END']
    p = os.path.join(D, name)
    open(p, 'w').write('\n'.join(lines) + '\n')
    return p


# ---------------- 1) quality fix ---------------------------------------------
# block A travels BELOW the square (clean) -> armor drops
# block B travels BACK ACROSS the square -> armor keeps
src = qual_fixture('q1.gcode', [
    'G10', 'G1 Z0.6 F600', 'G0 X70 Y5 F9000', 'G1 Z0.2 F600', 'G11',
    'G1 X90 Y5 E5 F1800',
    'G10', 'G1 Z0.6 F600', 'G0 X30 Y30 F9000', 'G1 Z0.2 F600', 'G11',
    'G1 X30 Y31 E6 F1800',
])
dropped, kept, injected, naked = pp._quality_fix_file(src)
txt = open(src).read()
# R249: the rule is same-layer OR sacred ink - both block travels touch
# the printed wall (sacred), so BOTH keep their armor. naked=1 is the
# file-start travel (no ink known yet -> dangerous by default, no retract
# known -> counted, left as-is).
ck('quality: a block whose travel touches sacred ink keeps its armor '
   '(R249 sacred-ink rule - the skin wins over the saved second)',
   dropped == 0 and kept == 2 and injected == 0 and naked == 1
   and txt.count('\nG10') == 2 and txt.count('Z0.6') == 2
   and 'G0 X70 Y5 F9000' in txt and 'G0 X30 Y30 F9000' in txt,
   'd=%d k=%d i=%d n=%d' % (dropped, kept, injected, naked))
ck('quality: the kept blocks keep their FULL armor (hop up, hop down, '
   'G11)',
   txt.count('G1 Z0.2 F600\nG11') == 2, txt[:200])

# naked crossing: a travel across ink without any retract at all
src = qual_fixture('q2.gcode', ['G0 X70 Y5 F9000', 'G0 X30 Y30 F9000',
                                 'G1 X30 Y31 E6 F1800'])
d2, k2, i2, n2 = pp._quality_fix_file(src)
ck('quality: crossing travels WITHOUT armor are counted (naked: file '
   'start + both crossings), the file stays untouched (nothing to '
   'inject: the fixture shows no retract the fix could reuse)',
   d2 == 0 and k2 == 0 and i2 == 0 and n2 == 3
   and 'G0 X30 Y30 F9000' in open(src).read(), 'd=%d n=%d' % (d2, n2))
# (the first travel runs below the square = clean, the second crosses
#  the right wall = naked: ink, no retract at all)

# E-only retracts (not G10/G11) drop the same way
src = qual_fixture('q3.gcode', [
    'G1 E-2.0 F2400', 'G1 Z0.6 F600', 'G0 X70 Y5 F9000',
    'G1 Z0.2 F600', 'G1 E2.0 F2400',
    'G1 X90 Y5 E5 F1800',
])
d3, k3, i3, n3 = pp._quality_fix_file(src)
ck('quality: E-only retract blocks count the same way (sacred-ink '
   'touch -> kept, R249)',
   d3 == 0 and k3 == 1 and n3 == 1 and 'E-2.0' in open(src).read()
   and 'G0 X70 Y5 F9000' in open(src).read(), 'd=%d k=%d n=%d' % (d3, k3, n3))

# a NEW layer resets the ink: the same travel is clean one layer up
src = qual_fixture('q4.gcode', [
    'G1 X70 Y5 E5 F1800',
    'G10', 'G1 Z0.6 F600', 'G0 X30 Y30 F9000', 'G1 Z0.2 F600', 'G11',
    'G1 X30 Y31 E6 F1800',
    ';LAYER_CHANGE', 'G1 Z0.4 F600',
    'G1 X30 Y40 E7 F1800',
    'G10', 'G1 Z0.8 F600', 'G0 X80 Y35 F9000', 'G1 Z0.4 F600', 'G11',
    'G1 X80 Y36 E8 F1800',
])
d4, k4, i4, n4 = pp._quality_fix_file(src)
# R249: sacred ink (outer wall) counts ACROSS layers - the layer-2
# travel still crosses the printed wall's skin, so the armor stays.
# (The pre-R249 same-layer-only rule would have dropped it.)
ck('quality: sacred ink counts across layers - the layer-2 travel over '
   'the old wall keeps its armor (R249 skin-first rule)',
   d4 == 0 and k4 == 2 and n4 == 1, 'd=%d k=%d n=%d' % (d4, k4, n4))

# the DROP path: a travel far outside any ink loses its armor
src = qual_fixture('q5.gcode', [
    'G1 X60 Y60 E5 F1800',
    'G10', 'G1 Z0.6 F600', 'G0 X90 Y20 F9000', 'G1 Z0.2 F600', 'G11',
    'G1 X92 Y20 E6 F1800',
])
d5, k5, i5, n5 = pp._quality_fix_file(src)
_t5 = open(src).read()
ck('quality: a travel that crosses NO ink drops the armor (the time '
   'saving the fix exists for)',
   d5 == 1 and k5 == 0
   and 'G0 X90 Y20 F9000' in _t5 and _t5.count('\nG10') == 0,
   'd=%d k=%d' % (d5, k5))

# ---------------- 2) speed fix ------------------------------------------------
src = os.path.join(D, 's1.gcode')
lines = [
    'M82', 'G90', 'G0 X10 Y10 Z0.2 F9000',
    ';TYPE:Wall outer',
    'G1 X50 Y10 E4 F1800', 'G1 X50 Y50 E8',
    ';TYPE:Ironing',
    'G1 X12 Y12 E8.4 F300', 'G1 X48 Y12 E8.8', 'G1 X48 Y48 E9.2',
    ';TYPE:Top surface',
    'G1 X50 Y50 E9.6 F1200',
    'G0 X10 Y10 F9000', 'G0 X60 Y60',
    'G1 X80 Y60 E10.0 F1800',
    'M107', 'PRINT_END',
]
open(src, 'w').write('\n'.join(lines) + '\n')
merged, ironed = pp._speed_fix_file(src)
txt = open(src).read()
ck('speed: consecutive travels merge into ONE direct way '
   '(effective X/Y/F)',
   merged == 1 and 'G0 X60 Y60 F9000' in txt
   and 'G0 X10 Y10 F9000\n' not in txt.split('Top surface')[1],
   'm=%d' % merged)
ck('speed: the ironing extrusions drop, the TYPE boundaries stay',
   ironed == 3 and 'E8.4' not in txt and 'E8.8' not in txt
   and ';TYPE:Ironing' in txt and ';TYPE:Top surface' in txt,
   'i=%d' % ironed)
ck('speed: absolute-E files get the G92 stitch (E base continues)',
   'G92 E9.2' in txt and 'G1 X50 Y50 E9.6 F1200' in txt
   and 'G1 X80 Y60 E10.0 F1800' in txt, '')
ck('speed: the R2 stamp names both accelerations',
   'R2-SPEEDFIX: 1 travel line(s) merged' in txt
   and '3 ironing move(s) skipped' in txt, '')

# relative E: no G92 needed, ironing still drops
src = os.path.join(D, 's2.gcode')
lines = [
    'M83', 'G90', 'G0 X10 Y10 Z0.2 F9000',
    ';TYPE:Top surface',
    'G1 X50 Y10 E0.4 F1200',
    ';TYPE:Ironing',
    'G1 X12 Y12 E0.1 F300', 'G1 X48 Y12 E0.1',
    ';TYPE:Wall inner',
    'G1 X50 Y50 E0.4 F1800',
    'M107', 'PRINT_END',
]
open(src, 'w').write('\n'.join(lines) + '\n')
m2, i2 = pp._speed_fix_file(src)
txt2 = open(src).read()
ck('speed: relative-E ironing drops WITHOUT a G92 (M83 needs none)',
   i2 == 2 and 'G92' not in txt2 and ';TYPE:Wall inner' in txt2
   and 'G1 X50 Y50 E0.4 F1800' in txt2, 'i=%d' % i2)

# APPLY_TYPE markers (an already-processed file) work the same
src = os.path.join(D, 's3.gcode')
lines = [
    'M83', 'G90', 'G0 X10 Y10 Z0.2 F9000',
    'APPLY_TYPE TYPE=IRONING',
    'G1 X12 Y12 E0.1 F300', 'G1 X48 Y12 E0.1',
    'APPLY_TYPE TYPE=WALL-OUTER',
    'G1 X50 Y50 E0.4 F1800',
    'M107', 'PRINT_END',
]
open(src, 'w').write('\n'.join(lines) + '\n')
m3, i3 = pp._speed_fix_file(src)
txt3 = open(src).read()
ck('speed: APPLY_TYPE TYPE=IRONING boundaries work (processed files, '
   'the marker stays - only the moves drop)',
   i3 == 2 and 'APPLY_TYPE TYPE=IRONING' in txt3
   and 'APPLY_TYPE TYPE=WALL-OUTER' in txt3
   and 'G1 X50 Y50 E0.4 F1800' in txt3, 'i=%d' % i3)

# nothing to do -> file untouched (no stamp, no rewrite)
src = os.path.join(D, 's4.gcode')
before = 'M83\nG90\nG0 X10 Y10 Z0.2 F9000\nG1 X50 Y10 E1 F1800\nPRINT_END\n'
open(src, 'w').write(before)
m4, i4 = pp._speed_fix_file(src)
ck('speed: nothing to merge or skip -> byte-identical, no stamp',
   m4 == 0 and i4 == 0 and open(src).read() == before, '')

print()
if FAIL:
    print('RESULT: FAIL - %d of %d checks failed'
          % (len(FAIL), len(FAIL) + len(PASS)))
    sys.exit(1)
print('RESULT: PASS - %d checks, quality + speed fix fully pinned'
      % len(PASS))
