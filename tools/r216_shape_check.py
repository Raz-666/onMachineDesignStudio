#!/usr/bin/env python3
"""R216 geometry generator check (pinned).

make_shape (.136n user wish): triangles, squares/rectangles, regular
polygons and cylinders (round = 48 segments or an explicit count), with
height, wall count (1 wall = SPIRAL/VASE: solid floor, then ONE continuous
wall with steadily rising Z - no top, no infill), wall thickness in mm
(overrides the loop count) and infill % (0 = hollow, 100 = solid, between =
sparse grid). The LCD flow: Generator > Geometry (shape_kind/size/corners/
height/walls/wall_thick/infill/base in save_variables, SHAPE_GENERATE bumps
shape_nonce, the watcher calls make_shape into the Shapes/ folder).

Pins:
  - macro validation: bad shape/size/height/walls/infill/corners refuse
    with a NOTIFY, the nonce stays untouched; the happy path bumps
  - GEN_SHAPE maps console params onto the save_variables
  - make_shape: all four shapes build, correct layer count, square names
    itself Rect at X!=Y, cylinder corners 0 -> 48 segments, 6 -> hexagonal
  - vase: single wall, no SURFACE-TOP, no top layers, the body is ONE
    continuous extrusion with strictly rising Z (spiral), floor solid
  - wall thickness overrides the loop count
  - travel golden rule: 0 flat ink crossings in every output

Run:  python3 tools/r216_shape_check.py
"""
import importlib.util
import math
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from jinja2 import Environment, Undefined, BaseLoader   # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
PASS = []
FAIL = []


def ck(name, ok, detail=''):
    (PASS if ok else FAIL).append(name)
    print('%-4s %s%s' % ('PASS' if ok else 'FAIL', name,
                         ('  [%s]' % detail) if detail and not ok else ''))


spec = importlib.util.spec_from_file_location(
    'r2p', os.path.join(HERE, 'r2_postproc.py'))
pp = importlib.util.module_from_spec(spec)
spec.loader.exec_module(pp)

# ---------------- macro rendering -------------------------------------------
env = Environment(loader=BaseLoader(),
                  variable_start_string='{', variable_end_string='}',
                  block_start_string='{%', block_end_string='%}',
                  comment_start_string='{#', comment_end_string='#}',
                  trim_blocks=True, lstrip_blocks=False, undefined=Undefined)
gsrc = open(os.path.join(ROOT, 'macros/17_generator.cfg'),
            encoding='utf-8').read()


def body(name):
    m = re.search(r'\[gcode_macro %s\](.*?)(?=\n\[)' % re.escape(name),
                  gsrc, re.S)
    b = re.search(r'gcode:\n((?:[ \t]+.*\n?)*)', m.group(1))
    return b.group(1)


class M(dict):
    def __getattr__(self, k):
        try:
            return self[k]
        except KeyError:
            raise AttributeError(k)


def render(name, sv_over=None, params=None):
    sv = {'shape_kind': 'CYLINDER', 'shape_size_x': 40, 'shape_size_y': 40,
          'shape_corners': 0, 'shape_height': 20, 'shape_walls': 2,
          'shape_wall_thick': 0, 'shape_infill': 20, 'shape_base': 3,
          'shape_layer_h': 0.2, 'shape_nonce': 5}
    sv.update(sv_over or {})
    printer = M({'save_variables': M({'variables': M(sv)}),
                 'gcode_macro _STATE': M({'mode': 'idle', 'gen_arm': ''})})
    env.globals['printer'] = printer
    env.globals['params'] = params or {}
    return env.from_string(body(name)).render()


out = render('SHAPE_GENERATE', sv_over={'shape_size_x': 300})
ck('macro: size out of range refuses (no nonce bump)',
   'must be 8..200' in out and 'VARIABLE=shape_nonce VALUE=6' not in out,
   out[:100])
out = render('SHAPE_GENERATE', sv_over={'shape_kind': 'BLOB'})
ck('macro: unknown shape refuses', 'TRIANGLE, SQUARE, POLY' in out,
   out[:80])
out = render('SHAPE_GENERATE', sv_over={'shape_walls': 9})
ck('macro: walls > 8 refuse (1 = vase hint)', '1..8 loops' in out, out[:80])
out = render('SHAPE_GENERATE', sv_over={'shape_kind': 'POLY',
                                        'shape_corners': 2})
ck('macro: POLY with < 3 corners refuses', 'corners 0..64' in out, out[:80])
out = render('SHAPE_GENERATE')
ck('macro: happy path bumps the nonce + speaks the file',
   'VARIABLE=shape_nonce VALUE=6' in out and 'creating the CYLINDER' in out
   and 'M117 Shape creating..' in out, out[:120])
out = render('GEN_SHAPE', params={'SHAPE': 'POLY', 'X': '55', 'CORNERS': '5',
                                  'HEIGHT': '12', 'WALLS': '1',
                                  'INFILL': '0'})
ck('macro: GEN_SHAPE maps console params onto the variables',
   "VARIABLE=shape_kind VALUE='\"POLY\"'" in out
   and 'VARIABLE=shape_size_x VALUE=55.0' in out
   and 'VARIABLE=shape_corners VALUE=5' in out
   and 'VARIABLE=shape_height VALUE=12.0' in out
   and 'VARIABLE=shape_walls VALUE=1' in out
   and 'VARIABLE=shape_infill VALUE=0.0' in out, out[:200])

# ---------------- make_shape functional --------------------------------------
import tempfile   # noqa: E402
d = tempfile.mkdtemp(prefix='r216shape_')
shapes = os.path.join(d, 'Shapes')
os.makedirs(shapes, exist_ok=True)


def audit(path):
    x = y = z = 0.0
    e = 0.0
    e_rel = False
    retracted = False
    extr = {}
    viol = []
    for ln in open(path, errors='replace').read().split('\n'):
        code = ln.split(';', 1)[0].strip()
        if not code:
            continue
        parts = code.split()
        cmd = parts[0].upper()
        if cmd == 'M83':
            e_rel = True
            continue
        if cmd == 'M82':
            e_rel = False
            continue
        if cmd == 'G10':
            retracted = True
            continue
        if cmd == 'G11':
            retracted = False
            continue
        if cmd == 'G92':
            for p in parts[1:]:
                if p[:1].upper() == 'E':
                    try:
                        e = float(p[1:])
                    except ValueError:
                        pass
            continue
        if cmd not in ('G0', 'G1'):
            continue
        nx = ny = nz = ne = None
        for p in parts[1:]:
            q = p[:1].upper()
            try:
                v = float(p[1:])
            except ValueError:
                continue
            if q == 'X':
                nx = v
            elif q == 'Y':
                ny = v
            elif q == 'Z':
                nz = v
            elif q == 'E':
                ne = v
        px, py, pz = x, y, z
        if nx is not None:
            x = nx
        if ny is not None:
            y = ny
        if nz is not None:
            z = nz
        de = 0.0
        if ne is not None:
            de = (ne - e) if not e_rel else ne
            e = ne if not e_rel else e + ne
        dd = math.hypot(x - px, y - py)
        if de > 0 and dd > 1e-4:
            extr.setdefault(round(pz, 3), []).append((px, py, x, y))
            retracted = False
        elif dd > 0.05 and (nz is None or abs(nz - pz) < 0.06):
            if not retracted:
                tvx, tvy = x - px, y - py
                tl = math.hypot(tvx, tvy) or 1.0
                tvx, tvy = tvx / tl, tvy / tl
                hits = 0
                for (a, b, c, d2) in extr.get(round(z, 3), ()):
                    if pp._segs_cross((px, py), (x, y), (a, b), (c, d2)):
                        sx, sy = c - a, d2 - b
                        sl = math.hypot(sx, sy) or 1.0
                        if abs(tvx * sx / sl + tvy * sy / sl) > 0.90:
                            continue
                        hits += 1
                        if hits > 2:
                            break
                if hits > 2 and dd >= 0.25:
                    viol.append((round(z, 2), code[:36]))
    return viol


outs = {}
for nm, kw in [
        ('tri', dict(shape='TRIANGLE', size_x=40, size_y=35, height=10,
                     walls=2, infill=20)),
        ('rect', dict(shape='SQUARE', size_x=50, size_y=30, height=8,
                      walls=3, infill=40)),
        ('poly6', dict(shape='POLY', size_x=40, size_y=40, corners=6,
                       height=12, walls=2, infill=15)),
        ('cyl', dict(shape='CYLINDER', size_x=30, size_y=30, height=15,
                     walls=2, infill=0)),
        ('cyl6', dict(shape='CYLINDER', size_x=30, size_y=30, corners=6,
                      height=15, walls=4, infill=100)),
        ('vase', dict(shape='CYLINDER', size_x=35, size_y=35, height=40,
                      walls=1, infill=0, base=3)),
        ('vasetri', dict(shape='TRIANGLE', size_x=30, size_y=30, height=25,
                         walls=1, infill=50)),
        ('thick', dict(shape='SQUARE', size_x=40, size_y=40, height=10,
                       wall_thick=1.9, infill=30))]:
    outs[nm] = pp.make_shape(out_dir=shapes, version=1, **kw)

f, i = outs['tri']
txt = open(f).read()
ck('triangle: 10mm @ 0.2 = 50 layers, 3 corners, clean travels',
   i['layers'] == 50 and i['corners'] == 3 and len(audit(f)) == 0,
   str(i['layers']))
f, i = outs['rect']
ck('square X!=Y names itself Rect (walls 3, infill 40%)',
   i['kind'] == 'rect' and i['walls'] == 3 and i['infill'] == 40
   and 'Sparse infill' in open(f).read() and len(audit(f)) == 0, i['kind'])
f, i = outs['poly6']
ck('polygon: 6 corners, kind 6-gon', i['corners'] == 6
   and i['kind'] == '6-gon' and len(audit(f)) == 0, i['kind'])
f, i = outs['cyl']
ck('cylinder corners 0 = round (48 segments)',
   i['corners'] == 48 and len(audit(f)) == 0, str(i['corners']))
f, i = outs['cyl6']
ck('cylinder with 6 segments = hexagonal, solid infill',
   i['corners'] == 6 and 'SURFACE-TOP' in open(f).read()
   and len(audit(f)) == 0, str(i['corners']))

f, i = outs['vase']
txt = open(f).read()
sp = [l for l in txt.split('\n') if l.startswith('G1 X') and ' Z' in l]
zs = [float(l.split(' Z')[1].split()[0]) for l in sp]
monotone = all(zs[k] < zs[k + 1] + 1e-9 for k in range(len(zs) - 1))
uniq = len(set(round(z, 3) for z in zs))
ck('vase: no top, no sparse infill, WALL_LOOPS=1',
   'SURFACE-TOP' not in txt and 'INFILL-SPARSE' not in txt
   and 'WALL_LOOPS=1' in txt, txt[:80])
ck('vase: body is ONE continuous rising extrusion (spiral)',
   monotone and len(sp) >= 40 and uniq > len(sp) * 0.5,
   '%d moves, %d z-levels' % (len(sp), uniq))
ck('vase: floor is solid (SURFACE-BOTTOM present), clean travels',
   'SURFACE-BOTTOM' in txt and len(audit(f)) == 0, '')
f, i = outs['vasetri']
ck('vase works for the triangle too', i['vase'] and len(audit(f)) == 0,
   str(i)[:60])
f, i = outs['thick']
ck('wall thickness 1.9mm @ 0.65 line = 3 loops (overrides the count)',
   i['walls'] == 3 and abs(i['wall_thick'] - 1.95) < 0.3,
   '%d loops / %s mm' % (i['walls'], i['wall_thick']))
ck('every output carries PRINT_START + EXCLUDE_OBJECT + _FILE_INFO TYPES',
   all(('PRINT_START' in open(o[0]).read()
        and 'EXCLUDE_OBJECT_DEFINE NAME=SHAPE_1' in open(o[0]).read()
        and 'TYPES=' in open(o[0]).read()) for o in outs.values()), '')

print()
if FAIL:
    print('RESULT: FAIL - %d of %d checks failed'
          % (len(FAIL), len(FAIL) + len(PASS)))
    sys.exit(1)
print('RESULT: PASS - %d checks, geometry generator fully pinned' % len(PASS))
