#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""R229 (.136aa): the vocabulary REST LIST - the last open items of the
slicer-family compilation (uploads/slicer-families.md) the user asked
about after R225.

  F1  NON-EXTRUSION annotations are inert, not features. KISSlicer marks
      retract/travel moves as '; feature Destring' and the seam point as
      '; feature Seam'; G-code viewers show travel/retract/tool-change/
      color-change/pause events as pseudo types. A seam sits INSIDE a
      wall loop - as a feature block it would type the following WALL
      extrusions TRAVEL/CUSTOM and the wall overrides would silently
      stop applying there. The TYPE regex now rejects these words
      (whole-line anchored): the feature context persists through them.
  F2  purge/prime structures are ONE class: PRIME-TOWER (Kiri:Moto
      purge tower, KISSlicer prime pillar/wall + wipe wall (correction:
      SKIRT since R225 - a wipe wall IS a purge structure), purge
      block/line/blob, wiping tower).
  F3  adhesion/extras: belt lead -> skirt (belt-printer adhesion strip),
      brim ears -> brim, painted support -> support, the raft stack ->
      bottom surface (the existing 'raft' approximation).
  F4  infill pattern NAMES (tpms/tpms-d/tpms-fk, octet, tetrahedral,
      stars, lateral honeycomb, lattice, spiral inset, tri-hexagon) are
      patterns, not features - every one reduces to sparse infill
      (R216 stage-7 rule).
  F5  END TO END: a KISSlicer-style file (wall -> '; feature Seam' ->
      wall -> '; feature Destring' travel/retract -> wall) keeps its
      WALL-OUTER context - no TRAVEL/CUSTOM feature appears in the
      processed output, the seam never fragments the wall.

Run: python3 tools/r229_vocab_rest.py   (exit 0 = all green)
"""
import os
import re
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import r2_postproc as pp                                  # noqa: E402

fails = []
N = 0


def check(name, ok, info=''):
    global N
    N += 1
    if not ok:
        fails.append(name)
        print('  FAIL %s %s' % (name, str(info)[:240]))
    else:
        print('  ok   %s' % name)


print('--- F1: non-extrusion annotations stay INERT (no feature switch)')
_nonfeat = [
    '; feature Seam', '; feature seam', '; feature Destring',
    ';TYPE:seam', ';TYPE:Destring', ';TYPE:travel', '; feature Travel',
    '; feature Retract', '; feature Unretract', '; feature Wipe',
    '; feature Noop', '; feature Tool Change', '; feature Color Change',
    '; feature Pause Print', '; feature Custom GCode',
    '; structure:seam',
]
for _ln in _nonfeat:
    m = pp.TYPE_RE.match(_ln)
    check('F1 inert: %-28s -> no feature boundary (move annotation, '
          'not a feature)' % _ln, m is None, m.group(1) if m else '')
# near-miss words that MUST keep matching (reject list is end-anchored)
for _ln, _w in (('; feature wipe wall', 'PRIME-TOWER'),
                ('; feature Wipe Tower', 'PRIME-TOWER'),
                ('; feature traveling art', None),   # prose-ish: ladder
                (';TYPE:WALL-OUTER', 'WALL-OUTER'),
                ('; shell', 'WALL-INNER')):
    m = pp.TYPE_RE.match(_ln)
    got = pp._canon_type(m.group(1)) if m else None
    if _w is None:
        check('F1 near-miss still matches: %s (ladder resolves)' % _ln,
              m is not None)
    else:
        check('F1 near-miss still matches: %s -> %s' % (_ln, _w),
              got == _w, got)

print('--- F2/F3/F4: the rest-list vocabulary resolves')
_rest = [
    ('; feature Prime Wall', 'PRIME-TOWER'),
    ('; feature wipe wall', 'PRIME-TOWER'),
    ('; feature Prime Pillar', 'PRIME-TOWER'),
    (';TYPE:wiping tower', 'PRIME-TOWER'),
    ('; feature Purge Block', 'PRIME-TOWER'),
    (';TYPE:purge line', 'PRIME-TOWER'),
    ('; feature prime blob', 'PRIME-TOWER'),
    ('; feature Belt Lead', 'SKIRT'),
    ('; feature Brim Ears', 'BRIM'),
    ('; feature Painted Support', 'SUPPORT'),
    ('; feature Raft Base', 'SURFACE-BOTTOM'),
    ('; feature Raft Interface', 'SURFACE-BOTTOM'),
    ('; feature Raft Top', 'SURFACE-BOTTOM'),
    (';TYPE:TPMS-D', 'INFILL-SPARSE'),
    (';TYPE:octet', 'INFILL-SPARSE'),
    ('; feature Tetrahedral', 'INFILL-SPARSE'),
    (';TYPE:stars', 'INFILL-SPARSE'),
    ('; feature Lateral Honeycomb', 'INFILL-SPARSE'),
    (';TYPE:lattice', 'INFILL-SPARSE'),
    ('; feature Spiral Inset', 'INFILL-SPARSE'),
    (';TYPE:tri-hexagon', 'INFILL-SPARSE'),
    # map safety net (direct _canon_type callers, replay, dialects)
]
for _ln, _w in _rest:
    m = pp.TYPE_RE.match(_ln)
    got = pp._canon_type(m.group(1)) if m else None
    check('F2-F4 %-32s -> %s' % (_ln, _w), got == _w, got)
check('F2 map safety net: _canon_type(seam/destring/travel) = TRAVEL '
      '(no feature, replay-safe)',
      pp._canon_type('Seam') == 'TRAVEL'
      and pp._canon_type('destring') == 'TRAVEL'
      and pp._canon_type('Travel') == 'TRAVEL')
check('F2 the correction is pinned: wipe wall left the skirt class '
      '(was SKIRT since R225)',
      pp.TYPE_MAP['wipe wall'] == 'PRIME-TOWER'
      and pp.TYPE_MAP['prime wall'] == 'PRIME-TOWER')

print('--- F5: end to end - a seam never fragments the wall')
D = tempfile.mkdtemp(prefix='r229_')
p5 = os.path.join(D, 'kissish.gcode')
open(p5, 'w').write('\n'.join([
    '; generated by KISSlicer 2', 'M82', 'G90', 'G28',
    'G0 X50 Y50 Z0.2 F3000',
    '; feature Perimeter',
    'G1 X150 Y50 E1 F1800', 'G1 X150 Y150 E2',
    '; feature Seam',                       # the seam point inside the loop
    'G1 X50 Y150 E3',
    '; feature Destring',                   # retract + travel
    'G1 E-1 F2400', 'G0 X60 Y60 F9000',
    '; feature Perimeter',
    'G1 E1 F2400', 'G1 X160 Y60 E4 F1800',
    'PRINT_END']) + '\n')
_r5 = pp.process(p5)
_t5 = open(p5).read()
check('F5 the processed file knows ONE feature: WALL (no TRAVEL, no '
      'CUSTOM from the seam/destring markers)',
      'CUSTOM' not in _t5 and 'TYPE=TRAVEL' not in _t5
      and 'APPLY_TYPE TYPE=WALL-INNER' in _t5, [_l for _l in _t5.split('\n')
                                                 if 'APPLY_TYPE' in _l][:4])
check('F5 the seam/destring comments survive as plain comments '
      '(no boundary inserted around them)',
      '; feature Seam' in _t5 and '; feature Destring' in _t5)

import shutil
shutil.rmtree(D, ignore_errors=True)

print()
if fails:
    print('R229 VOCAB REST: %d checks, %d FAIL' % (N, len(fails)))
    for f in fails:
        print('  -', f)
    sys.exit(1)
print('R229 VOCAB REST: %d checks, 0 FAIL - the rest list is closed' % N)
