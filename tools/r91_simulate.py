#!/usr/bin/env python3
"""R91 texture tool - special-case simulation bench.

Runs the fuzzy/bumps tool against tricky slicer files that the unit tests
only sketch: vase mode, OrcaSlicer/Bambu type spellings, absolute E,
CRLF line endings, E-only moves, bed-edge parts, texture-on-texture,
version overflow past 99, single-vertex walls, empty files, huge files.

Every scenario prints PASS/FAIL + the numbers that matter. Exit code is
non-zero if anything fails. No printer required - pure file simulation.
"""
import os
import re
import sys
import time
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from r2_texture import apply_texture  # noqa: E402
from r2_postproc import make_frame  # noqa: E402

BED = (0.0, -3.0, 220.0, 217.0)
FAILS = []


def check(name, ok, detail=''):
    print('%s  %s%s' % ('PASS' if ok else 'FAIL', name,
                        ('  [%s]' % detail) if detail else ''))
    if not ok:
        FAILS.append(name)


def outer_pts(path):
    pts, cur = [], ''
    for line in open(path, encoding='utf-8'):
        if line.startswith(';TYPE:'):
            cur = line[6:].strip().lower()
            continue
        m = re.match(r'^G1 X([\d.\-]+) Y([\d.\-]+).* E([\d.]+)', line)
        if m and float(m.group(3)) > 0 and cur == 'outer wall':
            pts.append((float(m.group(1)), float(m.group(2))))
    return pts


def stripped(path):
    out, cur = [], ''
    for line in open(path, encoding='utf-8'):
        if line.startswith(';TYPE:'):
            cur = line[6:].strip().lower()
            continue
        m = re.match(r'^G1 X([\d.\-]+) Y([\d.\-]+)', line)
        if m and cur == 'outer wall':
            out.append((float(m.group(1)), float(m.group(2))))
    return out


D = tempfile.mkdtemp(prefix='r91sim_')

# ---------------------------------------------------------------------------
print('=== 1. vase mode (spiral, every layer is outer wall) ===')
vase = os.path.join(D, '00_vase_sim.gcode')
with open(vase, 'w', encoding='utf-8') as f:
    f.write(';FLAVOR:Marlin\n;LAYER_COUNT:60\nG90\nM83\nG28\n')
    z = 0.2
    for layer in range(60):
        f.write(';LAYER_CHANGE\n;Z:%.2f\n;TYPE:outer wall\n' % z)
        for i in range(40):
            a = i / 40.0
            x = 110 + 30 * __import__('math').cos(a * 6.283 + layer * 0.1)
            y = 107 + 30 * __import__('math').sin(a * 6.283 + layer * 0.1)
            f.write('G1 X%.3f Y%.3f E%.4f F1800\n' % (x, y, 0.03))
        z += 0.2
src = stripped(vase)
tx, info = apply_texture(vase, out_dir=D, mode='FUZZY', fuzzy_thick=0.25)
dst = stripped(tx)
moved = sum(1 for u, v in zip(src, dst) if abs(u[0]-v[0]) + abs(u[1]-v[1]) > 1e-6)
check('vase: all but the first vertex scattered, E-line count identical',
      moved == info['shifted'] == len(src) - 1 and len(dst) == len(src),
      '%d/%d shifted (1st stays)' % (info['shifted'], len(src)))
check('vase: source untouched, new _TX file', os.path.exists(vase)
      and os.path.basename(tx) == 'V01_vase_sim_TX.gcode')

# ---------------------------------------------------------------------------
print('=== 2. other slicer spellings (OrcaSlicer / Bambu) ===')
for spelling in ('Outer wall', 'OUTER WALL', 'outer wall', 'Outer Wall'):
    p = os.path.join(D, '00_spell.gcode')
    with open(p, 'w', encoding='utf-8') as f:
        f.write(';TYPE:%s\n' % spelling)
        for i in range(6):
            f.write('G1 X%d Y%d E0.1\n' % (20 + i, 20 + i))
    _, i2 = apply_texture(p, out_dir=D, mode='FUZZY', fuzzy_thick=0.3,
                          fuzzy_density=100)
    # the file's very first outer vertex has no approach direction -> stays
    # put by design; every following one must scatter
    check('spelling %-10r recognized' % spelling, i2['shifted'] == 5,
          'shifted=%d' % i2['shifted'])
p = os.path.join(D, '00_spell.gcode')
with open(p, 'w', encoding='utf-8') as f:
    f.write(';TYPE:Perimeter\n;TYPE:Wall-outer\nG1 X20 Y20 E0.1\n')
_, i3 = apply_texture(p, out_dir=D, mode='FUZZY')
check('unknown type names are NOT touched (no crash, 0 shifts)',
      i3['shifted'] == 0, '')

# ---------------------------------------------------------------------------
print('=== 3. absolute E (M82) + retractions + E-only moves ===')
p = os.path.join(D, '00_absE.gcode')
with open(p, 'w', encoding='utf-8') as f:
    f.write('G90\nM82\n;TYPE:outer wall\n')
    e = 0.0
    for i in range(20):
        e += 0.5
        f.write('G1 X%d Y30 E%.3f\n' % (30 + i, e))
        if i % 5 == 4:                       # retract + travel + unretract
            e -= 2.0
            f.write('G1 E%.3f F2400\n' % e)   # E-only move
            f.write('G0 X30 Y10 F9000\n')     # G0 travel
            e += 2.0
            f.write('G1 E%.3f F2400\n' % e)
            f.write('G1 X%d Y30\n' % (30 + i + 1))
src = outer_pts(p)                    # only E>0 extrusions
tx, info = apply_texture(p, out_dir=D, mode='FUZZY', fuzzy_thick=0.3)
dst = outer_pts(tx)
moved = sum(1 for u, v in zip(src, dst) if abs(u[0]-v[0]) + abs(u[1]-v[1]) > 1e-6)
# travels must stay EXACTLY where they were (4 returns + 1 G0)
trav_p = [l for l in open(p) if l.startswith('G1 X') and ' E' not in l]
trav_t = [l for l in open(tx) if l.startswith('G1 X') and ' E' not in l]
# 3 extrusions restart at the exact travel target (zero-length segment:
# no direction -> no offset possible -> skipped by design, never corrupted)
check('M82: 16 real moves shifted, 3 zero-restarts + 1st vertex skipped safely',
      moved == info['shifted'] == 16 and len(src) == 20
      and sum(1 for l in open(tx) if l.startswith('G1 E')) == 8
      and sum(1 for l in open(p) if l.startswith('G1 E')) == 8,
      'shifted=%d/20' % info['shifted'])
check('M82: travel lines stay travels at the exact same spot',
      trav_p == trav_t and sum(1 for l in open(tx) if l.startswith('G0 ')) == 4,
      '%d travels pinned' % len(trav_p))

# ---------------------------------------------------------------------------
print('=== 4. CRLF line endings (Windows slicer) ===')
p = os.path.join(D, '00_crlf.gcode')
with open(p, 'wb') as f:
    f.write(b';TYPE:outer wall\r\n')
    for i in range(8):
        f.write(b'G1 X%d Y40 E0.2\r\n' % (50 + i))
    f.write(b';TYPE:infill\r\nG1 X50 Y50 E0.2\r\n')
_, i4 = apply_texture(p, out_dir=D, mode='BUMPS', bump_pattern='GRID')
check('CRLF: 8 outer moves found (parser tolerates \\r)',
      i4['shifted'] == 7, 'shifted=%d (1st vertex stays)' % i4['shifted'])

# ---------------------------------------------------------------------------
print('=== 5. part at the bed edge (clamping) ===')
p = os.path.join(D, '00_edge.gcode')
with open(p, 'w', encoding='utf-8') as f:
    f.write(';TYPE:outer wall\n')
    for i in range(24):
        f.write('G1 X%.3f Y%.3f E0.1\n' % (0.05 + 0.02 * i, 100))
tx, i5 = apply_texture(p, out_dir=D, mode='FUZZY', fuzzy_thick=0.5)
xs = [x for x, _ in stripped(tx)]
check('bed edge: all x stay >= bed min (0.0), shifts clamped',
      i5['clamped'] > 0 and all(x >= 0.0 - 1e-6 for x in xs)
      and all(x <= BED[2] + 1e-6 for x in xs),
      'clamped=%d, min x=%.3f' % (i5['clamped'], min(xs)))

# ---------------------------------------------------------------------------
print('=== 6. texture on a texture (idempotent chaining) ===')
base, _ = make_frame(preset='9x13', depth=4, frame_w=4, out_dir=D, bed=BED)
t1, _ = apply_texture(base, out_dir=D, mode='FUZZY', fuzzy_thick=0.2)
t2, i6 = apply_texture(t1, out_dir=D, mode='FUZZY', fuzzy_thick=0.2)
check('chaining: _TX of _TX works, versions keep counting',
      os.path.basename(t2) == 'V12_Frame_9x13_FLATx4_TX_TX.gcode'
      and i6['shifted'] > 0, os.path.basename(t2))

# ---------------------------------------------------------------------------
print('=== 7. version overflow past V99 ===')
p = os.path.join(D, '00_ver.gcode')
with open(p, 'w', encoding='utf-8') as f:
    f.write(';TYPE:outer wall\n')
    for i in range(8):
        f.write('G1 X%d Y60 E0.2\n' % (90 + i))
names = []
overflow = None
for _ in range(120):
    try:
        t, _i = apply_texture(p, out_dir=D, mode='FUZZY', fuzzy_thick=0.1)
        names.append(os.path.basename(t))
    except ValueError as e99:
        overflow = str(e99)
        break
check('folder-global numbers: all unique, up to V99, then a CLEAR guard '
      '(no silent overwrite)',
      overflow is not None and len(set(names)) == len(names)
      and names[-1] == 'V99_ver_TX.gcode'
      and 'clean up first' in overflow,
      'n=%d last=%s, err=%r' % (len(names), names[-1] if names else '-', overflow))

# folder-global numbers: D is FULL now (V99 guard) - the rest runs in a
# fresh folder, exactly what the field does (one folder per generator)
D = tempfile.mkdtemp(prefix='r91sim2_')

# ---------------------------------------------------------------------------
print('=== 8. degenerate files ===')
p1 = os.path.join(D, '00_one.gcode')
with open(p1, 'w', encoding='utf-8') as f:
    f.write(';TYPE:outer wall\nG1 X10 Y70 E0.1\n')     # single vertex
_, i8 = apply_texture(p1, out_dir=D, mode='FUZZY')
check('single outer vertex: no direction -> skipped safely',
      i8['shifted'] == 0, '')
p2 = os.path.join(D, '00_empty.gcode')
open(p2, 'w').write('')
_, i82 = apply_texture(p2, out_dir=D, mode='BUMPS')
check('completely empty file: no crash', i82['shifted'] == 0, '')
p3 = os.path.join(D, '00_eonly.gcode')
with open(p3, 'w', encoding='utf-8') as f:
    f.write(';TYPE:outer wall\nG1 E1.0\nG1 E1.0\nG1 E-0.5\n')
_, i83 = apply_texture(p3, out_dir=D, mode='FUZZY')
check('E-only file (no XY): nothing shifted, no crash',
      i83['shifted'] == 0, '')

# ---------------------------------------------------------------------------
print('=== 9. big file performance (Pi-class budget) ===')
# synthetic slicer-sized file: 400 layers x 120 outer-wall vertices + infill
t0 = time.time()
big = os.path.join(D, '00_big.gcode')
with open(big, 'w', encoding='utf-8') as f:
    f.write(';FLAVOR:Marvin\n;LAYER_COUNT:400\nG90\nM83\n')
    for layer in range(400):
        f.write(';LAYER_CHANGE\n;Z:%.2f\n;TYPE:outer wall\n' % (0.2 * (layer + 1)))
        for i in range(120):
            a = i / 120.0 * 6.283
            f.write('G1 X%.3f Y%.3f E0.0300 F1500\n'
                    % (110 + 40 * __import__('math').cos(a),
                       107 + 40 * __import__('math').sin(a)))
        f.write(';TYPE:infill\n')
        for i in range(60):
            f.write('G1 X%.3f Y%.3f E0.0400\n' % (80 + i, 80 + layer * 0.1))
gen_t = time.time() - t0
src = outer_pts(big)
t0 = time.time()
tx, i9 = apply_texture(big, out_dir=D, mode='FUZZY', fuzzy_thick=0.3)
tex_t = i9['secs']
moved = sum(1 for u, v in zip(src, outer_pts(tx))
            if abs(u[0]-v[0]) + abs(u[1]-v[1]) > 1e-6)
mb = os.path.getsize(big) / 1e6
check('big %d outer pts: all but the first scattered, %d layers, %.1f MB in %.1fs'
      % (len(src), i9['layers'], mb, tex_t),
      moved == i9['shifted'] == len(src) - 1 and tex_t < 20,
      'gen=%.1fs tex=%.1fs' % (gen_t, tex_t))
import resource  # streaming proof: RSS stays flat while the file streams
_rss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024.0
check('streaming: peak RSS < 80 MB although the file is %.0f MB'
      % (os.path.getsize(big) / 1e6), _rss < 80, 'peak=%.0f MB' % _rss)

# ---------------------------------------------------------------------------
print('=== 10. output safety net ===')
tx, _ = apply_texture(base, out_dir=D, mode='BUMPS', bump_pattern='MANDELBROT')
head = open(tx, encoding='utf-8').read(400)
check('header documents the run (mode + source)',
      'applied to' in head and 'BUMPS' in head, head.splitlines()[1][:60])
g1 = [l for l in open(tx, encoding='utf-8') if l.startswith('G1 ') and ' X' in l]
check('every G1 keeps its F value (speeds untouched)',
      all(' F' in l for l in g1), '')

# ---------------------------------------------------------------------------
print()
if FAILS:
    print('%d FAILED: %s' % (len(FAILS), ', '.join(FAILS)))
    sys.exit(1)
print('ALL R91 SIMULATIONS PASSED')
