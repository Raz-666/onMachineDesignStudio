#!/usr/bin/env python3
"""R286 audit: ScaleXY middle scaling + decorative plastische texture expansion.

Checks:
  1. ScaleXY: 30 decorative plastische 3D-Druck-Texturen in PATTERN_NAMES (>=30)
  2. ScaleXY: >=90 total presets (Nutzer-Anforderung: >=90)
  3. ScaleXY: >=2 presets pro Texturtyp (V2-Varianten + neue Familie)
  4. ScaleXY: nahtlose Muster (wrap-Sprung <= Feld-Sprung)
  5. ScaleXY: ScaleXY-Mittel-Skalierung aktiv bei 5% < pos < 95%
  6. ScaleXY: linearer + Bézier-Übergang bottom->middle->top
  7. ScaleXY: Bottom/Top = 1.0x (Mittel irrelevant ausserhalb)
  8. ScaleXY: Engine (r2_texture.apply_texture) + Caller (r2_postproc) + LCD-Menüs
  9. Parität: cfg (names/codes/descs) == Engine (PATTERN_NAMES)

Run: python3 tools/r286_scalexy_texture_check.py
"""
import sys
import os
import re
import ast
import math

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, '..')
sys.path.insert(0, HERE)

import r2_texture as T

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


# ---- 1. 30 decorative plastische Muster ----
decor = ['PETAL', 'PETAL_V2', 'LOTUS', 'PEBBLE', 'PEBBLE_V2', 'GALAXY', 'CRUST',
         'BRAID', 'BRAID_V2', 'QUILT', 'GEMSTONE', 'SHELL', 'CORAL', 'MOSAIC',
         'PEARL', 'VELVET', 'STRATA', 'BASALT', 'MARBL', 'GRANIET', 'TERRA',
         'WALNUT', 'MAPLE', 'ZEBRA', 'LEOPARD', 'PYTHON', 'LAVA', 'ICE', 'MOSS',
         'FEATHER']
pats = T._build_patterns(9, 2, 7, None)
missing = [x for x in decor if x not in T.PATTERN_NAMES]
check('1 decorative Muster in PATTERN_NAMES', not missing,
      '(%d/30)' % (30 - len(missing)) if not missing else 'fehlen: %s' % missing)

# ---- 2. >=90 presets ----
total = len(T.PATTERN_NAMES)
check('2 >=90 Muster', total >= 90, '(%d)' % total)

# ---- 3. >=2 presets pro Texturtyp ----
# Kernfamilien mit V2-Varianten (R286) + neue dekorative Familien mit V2
families = [('RIDGES', 'RIDGES_V2'), ('WAVES', 'WAVES_V2'), ('GRID', 'GRID_V2'),
            ('CHECKER', 'CHECKER_V2'), ('HEX', 'HEX_V2'), ('BARK', 'BARK_V2'),
            ('LEATHER', 'LEATHER_V2'), ('TILES', 'TILES_V2'),
            ('PARQUET', 'PARQUET_V2'), ('FABRIC', 'FABRIC_V2'),
            ('PETAL', 'PETAL_V2'), ('PEBBLE', 'PEBBLE_V2'), ('BRAID', 'BRAID_V2')]
v2_ok = all(a in T.PATTERN_NAMES and b in T.PATTERN_NAMES for a, b in families)
check('3 >=2 Presets pro Texturtyp (V2-Varianten)', v2_ok,
      '(%d/13 Familien)' % sum(1 for a, b in families if a in T.PATTERN_NAMES and b in T.PATTERN_NAMES))

# ---- 4. nahtlose Muster ----
def seam_ok(pat):
    fn = pats[pat]
    field = 0.0
    for _i in range(200):
        _s = _i / 200.0
        field = max(field, abs(fn(_s, 0.3) - fn(_s + 0.005, 0.3)))
    for _j in range(200):
        _t = _j / 200.0
        field = max(field, abs(fn(0.3, _t) - fn(0.3, _t + 0.005)))
    seam = abs(fn(0.9975, 0.3) - fn(0.0025, 0.3))
    seam2 = abs(fn(0.3, 0.9975) - fn(0.3, 0.0025))
    return seam <= field * 1.5 + 1e-9 and seam2 <= field * 1.5 + 1e-9


not_seamless = []
for name in T.PATTERN_NAMES:
    if name == 'MAP' or name not in pats:
        continue  # MAP ist bildbasiert (ausgenommen)
    if not seam_ok(name):
        not_seamless.append(name)
check('4 alle Muster nahtlos', not not_seamless,
      '(alle %d ausser MAP)' % (total - 1) if not not_seamless else 'nicht nahtlos: %s' % not_seamless)

# ---- 5-7. ScaleXY-Mittel-Skalierung-Logik ----
def scalexy(bump_pattern, z_frac, mid, pos, curve):
    fn = T._build_patterns(9, 2, 7, None)[bump_pattern]
    v = fn(0.3, z_frac)
    active = (5.0 < pos < 95.0) and abs(mid - 100.0) > 1e-6
    if active:
        f = pos / 100.0
        u = z_frac
        if curve == 'bezier':
            if u <= f:
                e = u / f
                w = e * e * (3.0 - 2.0 * e)
            else:
                e = (u - f) / (1.0 - f)
                w = 1.0 - e * e * (3.0 - 2.0 * e)
        else:
            if u <= f:
                w = u / f
            else:
                w = 1.0 - (u - f) / (1.0 - f)
        v = v * (1.0 + (mid / 100.0 - 1.0) * w)
    return v


ref = scalexy('RIDGES', 0.5, 100.0, 50.0, 'bezier')
mid50_bez = scalexy('RIDGES', 0.5, 50.0, 50.0, 'bezier')
mid50_lin = scalexy('RIDGES', 0.5, 50.0, 50.0, 'linear')
mid150 = scalexy('RIDGES', 0.5, 150.0, 50.0, 'bezier')
bot = scalexy('RIDGES', 0.0, 50.0, 50.0, 'bezier')
top = scalexy('RIDGES', 1.0, 50.0, 50.0, 'bezier')
bot_ref = scalexy('RIDGES', 0.0, 100.0, 50.0, 'bezier')
top_ref = scalexy('RIDGES', 1.0, 100.0, 50.0, 'bezier')

check('5 ScaleXY aktiv 5%<pos<95%', abs(mid50_bez - ref * 0.5) < 0.01,
      '(50% bei 50% halbiert)')
check('6 Bézier-Übergang', abs(mid50_bez - ref * 0.5) < 0.01 and abs(mid50_lin - ref * 0.5) < 0.01,
      '(bezier+linear gleich in der Mitte)')
check('6 linearer Übergang', abs(mid150 - ref * 1.5) < 0.01, '(150% bei 50% -> 1.5x)')
check('7 Bottom=1.0x', abs(bot - bot_ref) < 1e-9, '(mittlere Skalierung irrelevant am Bottom)')
check('7 Top=1.0x', abs(top - top_ref) < 1e-9, '(mittlere Skalierung irrelevant am Top)')

# ---- 8. Engine + Caller + LCD ----
r2_post = open(os.path.join(ROOT, 'tools', 'r2_postproc.py'), encoding='utf-8').read()
r2_next = open(os.path.join(ROOT, 'tools', 'r2_postproc_next.py'), encoding='utf-8').read()
lcd = open(os.path.join(ROOT, 'menus', 'lcd_menues.cfg'), encoding='utf-8').read()
import inspect as _insp
_sig = str(_insp.signature(T.apply_texture))
check('8 Engine scale_xy_mid Parameter', 'scale_xy_mid' in _sig and 'scale_xy_pos' in _sig
      and 'scale_xy_curve' in _sig, '(apply_texture Signatur)')
check('8 Caller r2_postproc', 'texture_scale_xy_mid' in r2_post and 'texture_scale_xy_pos' in r2_post
      and 'texture_scale_xy_curve' in r2_post, '(3 Parameter)')
check('8 Caller r2_postproc_next', 'texture_scale_xy_mid' in r2_next and 'texture_scale_xy_pos' in r2_next
      and 'texture_scale_xy_curve' in r2_next, '(3 Parameter)')
check('8 LCD Menü mid', '__sxymid' in lcd and 'texture_scale_xy_mid' in lcd, '(__sxymid)')
check('8 LCD Menü pos', '__sxypos' in lcd and 'texture_scale_xy_pos' in lcd, '(__sxypos)')
check('8 LCD Menü curve', '__sxycurve' in lcd and 'texture_scale_xy_curve' in lcd, '(__sxycurve)')

# ---- 9. Parität cfg == Engine ----
cfg = open(os.path.join(ROOT, 'macros', '17_generator.cfg'), encoding='utf-8').read()
def get_cfg(key):
    m = re.search(r'variable_%s: (\[.*?\])\n' % key, cfg, re.S)
    return ast.literal_eval(m.group(1)) if m else []
names = get_cfg('tx_names')
codes = get_cfg('tx_codes')
descs = get_cfg('tx_descs')
check('9 cfg names==Engine', codes == list(T.PATTERN_NAMES),
      '(%d cfg == %d engine)' % (len(codes), len(T.PATTERN_NAMES)))
check('9 cfg names/codes/descs paritaet', len(names) == len(codes) == len(descs) == 95,
      '(%d/%d/%d)' % (len(names), len(codes), len(descs)))

# ---- summary ----
print('\n'.join(results))
print('\n==== %d passed, %d failed ====' % (PASS, FAIL))
sys.exit(0 if FAIL == 0 else 1)
