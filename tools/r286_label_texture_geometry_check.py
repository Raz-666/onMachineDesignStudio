#!/usr/bin/env python3
"""R286 L4/L13 audit: label engine + texture-carrier geometry.

  L4  - the label engine (r2_postproc._label_text_lines) renders ALL 5
        label lines (L1..L5) into the label window - engine verification.
  L13 - the make_shape generators (TRIANGLE/SQUARE/POLY/CYLINDER) produce
        proper rough-casts with outer-wall blocks that the texture engine
        (apply_texture) can engrave on - engine verification.

The field check (print the textured generator part and eyeball the texture)
is a separate physical acceptance step, not a code task.

Run: python3 tools/r286_label_texture_geometry_check.py
"""
import sys
import os
import importlib.util

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, '..')
sys.path.insert(0, HERE)

PASS = 0
FAIL = 0
results = []


def check(name, cond, detail=''):
    global PASS, FAIL
    if cond:
        PASS += 1
        results.append('[PASS] %s %s' % (name, detail))
    else:
        FAIL += 1
        results.append('[FAIL] %s %s' % (name, detail))


# load modules
def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m

pp = _load('r2_postproc', os.path.join(ROOT, 'tools', 'r2_postproc.py'))
tp = _load('r2_texture', os.path.join(ROOT, 'tools', 'r2_texture.py'))

work = os.path.join(HERE, '.l13_test')
os.makedirs(work, exist_ok=True)

# ===================== L4: label engine ========================================
try:
    lines5 = ['ALPHA', 'BETA', 'GAMMA', 'DELTA', 'EPS']
    paths, metrics = pp._label_text_lines(lines5, 'SMOOTH',
                                          (10.0, 10.0, 60.0, 30.0),
                                          60.0, 30.0, font_size=7.4,
                                          stroke_w=0.95)
    n_lines = metrics.get('lines', 0)
    check('L4 label engine erfasst alle 5 Zeilen', n_lines == 5,
          '(lines=%d)' % n_lines)
    check('L4 label-path-Punkte vorhanden', len(paths) > 0,
          '(%d Pfade)' % len(paths))
except Exception as e:
    check('L4 label engine', False, '(%r)' % (e,))

# ===================== L13: texture-carrier geometry ===========================
try:
    shapes = [
        ('TRIANGLE', dict(size_x=20.0, size_y=20.0)),
        ('SQUARE', dict(size_x=20.0, size_y=20.0)),
        ('POLY', dict(size_x=20.0, size_y=20.0, corners=6)),
        ('CYLINDER', dict(size_x=20.0, size_y=20.0)),
    ]
    ok_shapes = 0
    ok_carrier = 0
    for sh, kw in shapes:
        path, info = pp.make_shape(sh, out_dir=work, **kw)
        src = path if isinstance(path, str) else path[0]
        out, tinfo = tp.apply_texture(src, out_dir=work, mode='BUMPS')
        tg = open(out, encoding='utf-8', errors='replace').read()
        n_wall = sum(1 for l in tg.splitlines()
                     if ';TYPE:Outer wall' in l or 'APPLY_TYPE TYPE=WALL-OUTER' in l)
        moves = sum(1 for l in tg.splitlines()
                    if l.strip().startswith('G1') and ('E' in l or 'X' in l))
        good = n_wall > 0 and moves > 0
        if good:
            ok_shapes += 1
            ok_carrier += 1
    check('L13 make_shape Generatoren (4)', ok_shapes == 4,
          '(%d/4)' % ok_shapes)
    check('L13 Textur-Träger-Geometrie (outer-wall + moves)', ok_carrier == 4,
          '(%d/4 Textur anwendbar)' % ok_carrier)
except Exception as e:
    check('L13 texture-carrier', False, '(%r)' % (e,))

# ---- summary ----
print('\n'.join(results))
print('\n==== %d passed, %d failed ====' % (PASS, FAIL))
sys.exit(0 if FAIL == 0 else 1)
