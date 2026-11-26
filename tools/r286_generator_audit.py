#!/usr/bin/env python3
"""R286 L7 audit: Generator-Audit - alle D3/D4-Generatoren + Labels + Frames + Toolchain.

Prüft:
  1. Alle Generator-Makros existieren + haben gcode (SHAPE/ANGLE/CABLE/SEAL/FRAME)
  2. Valid Shapes: TRIANGLE, SQUARE, POLY, CYLINDER (Shape-Generator)
  3. Shape-Parameter-Validierung (corners 0..64, POLY 3..12, etc.)
  4. Angle-Plate-Generator (GEN_ANGLES) Parameter
  5. Cable-Tie-Generator (GEN_CABLE_TIES) max_ties
  6. Seal-Generator (GEN_SEAL)
  7. Frame-Generator (GEN_FRAME)
  8. Label-Generator (LABEL_GENERATE / GEN_LABELS)
  9. Toolchain-Vertrag (SCHEMA r2-toolchain/1, registry)
 10. _GENERATORS Limits (max_ties, max_plates)
 11. _GEN_ARM / _GEN_GO / _GEN_OUT_SET Sentinel

Run: python3 tools/r286_generator_audit.py
"""
import sys
import os
import re

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


def load(name):
    return open(os.path.join(ROOT, name), encoding='utf-8').read()


gen_cfg = load('macros/17_generator.cfg')
labels_cfg = load('macros/16_labels.cfg')
toolchain_src = load('tools/toolchain.py')

# ---- 1. Generator-Makros existieren ----
gen_macros = ['_GENERATORS', '_GEN_OUT_SET', '_GEN_ARM', '_GEN_GO',
              'GEN_FILE_DEL_SLOT', 'CABLE_TIE_GENERATE', 'GEN_CABLE_TIES',
              'ANGLE_GENERATE', 'GEN_ANGLES', 'SHAPE_GENERATE', 'GEN_SHAPE',
              'SEAL_GENERATE', 'GEN_SEAL', 'FRAME_GENERATE', 'GEN_FRAME',
              '_GEN_PRESET', '_GEN_QUEUE_CLEAR', '_GEN_QUEUE_SKIP',
              '_GEN_QUEUE_STOP']
missing = []
for m in gen_macros:
    if '[gcode_macro %s]' % m not in gen_cfg:
        missing.append(m)
check('1 Generator-Makros existieren', not missing,
      '(%d/%d)' % (len(gen_macros) - len(missing), len(gen_macros)) if not missing else 'fehlen: %s' % missing)

# ---- 2. Valid Shapes ----
valid_shapes = ['TRIANGLE', 'SQUARE', 'POLY', 'CYLINDER']
all_shapes = all(s in gen_cfg for s in valid_shapes)
check('2 Valid Shapes (TRIANGLE/SQUARE/POLY/CYLINDER)', all_shapes,
      '(alle 4 in SHAPE_GENERATE)')

# ---- 3. Shape-Parameter-Validierung ----
# corners 0..64, POLY 3..12
corners_check = 'crn < 0 or crn > 64' in gen_cfg and 'POLY' in gen_cfg
check('3 Shape corners-Validierung (0..64)', corners_check, '(crn 0..64)')

# ---- 4. Angle-Plate-Generator ----
angle_check = 'ANGLE_GENERATE' in gen_cfg and 'GEN_ANGLES' in gen_cfg
check('4 Angle-Plate-Generator', angle_check, '(ANGLE_GENERATE + GEN_ANGLES)')

# ---- 5. Cable-Tie-Generator + max_ties ----
cable_check = 'CABLE_TIE_GENERATE' in gen_cfg and 'GEN_CABLE_TIES' in gen_cfg
max_ties = re.search(r'variable_max_ties:\s*(\d+)', gen_cfg)
check('5 Cable-Tie-Generator + max_ties', cable_check and max_ties,
      '(max_ties=%s)' % (max_ties.group(1) if max_ties else '?'))

# ---- 6. Seal-Generator ----
seal_check = 'SEAL_GENERATE' in gen_cfg and 'GEN_SEAL' in gen_cfg
check('6 Seal-Generator', seal_check, '(SEAL_GENERATE + GEN_SEAL)')

# ---- 7. Frame-Generator ----
frame_check = 'FRAME_GENERATE' in gen_cfg and 'GEN_FRAME' in gen_cfg
check('7 Frame-Generator', frame_check, '(FRAME_GENERATE + GEN_FRAME)')

# ---- 8. Label-Generator ----
label_gen = 'LABEL_GENERATE' in labels_cfg and 'GEN_LABELS' in labels_cfg
check('8 Label-Generator', label_gen, '(LABEL_GENERATE + GEN_LABELS)')

# ---- 9. Toolchain-Vertrag ----
tc_schema = 'r2-toolchain/1' in toolchain_src
tc_registry = 'def build_registry' in toolchain_src
tc_drift = 'def registry_drift' in toolchain_src
check('9 Toolchain-Vertrag', tc_schema and tc_registry and tc_drift,
      '(SCHEMA + registry + drift)')

# ---- 10. _GENERATORS Limits ----
max_plates = re.search(r'variable_max_plates:\s*(\d+)', gen_cfg)
check('10 _GENERATORS Limits', max_ties and max_plates,
      '(max_ties=%s, max_plates=%s)' % (
          max_ties.group(1) if max_ties else '?',
          max_plates.group(1) if max_plates else '?'))

# ---- 11. _GEN_ARM / _GEN_GO / _GEN_OUT_SET Sentinel ----
sentinel = all(x in gen_cfg for x in ['_GEN_ARM', '_GEN_GO', '_GEN_OUT_SET'])
check('11 Generator-Sentinel (_GEN_ARM/_GEN_GO/_GEN_OUT_SET)', sentinel,
      '(alle 3 vorhanden)')

# ---- 12. Shape-Generator Output-Konsistenz (walls/infill/base) ----
# Prüfe, dass SHAPE_GENERATE die Parameter verwendet
shape_params = all(p in gen_cfg for p in
                   ['shape_size_x', 'shape_size_y', 'shape_height', 'shape_walls',
                    'shape_infill', 'shape_base', 'shape_layer_h'])
check('12 Shape-Parameter-Set konsistent', shape_params,
      '(7 Parameter in SHAPE_GENERATE)')

# ---- 13. Vasen-Modus (shape_walls==1 -> VASE/SPIRAL) ----
vase_check = 'VASE' in gen_cfg and 'SPIRAL' in gen_cfg
check('13 Vasen-Modus (SPIRAL/VASE)', vase_check, '(walls==1 -> VASE)')

# ---- 14. Frame-Generator-Presets ----
frame_presets = '_GEN_PRESET' in gen_cfg
check('14 Frame-Generator-Presets', frame_presets, '(_GEN_PRESET)')

# ---- 15. Toolchain Registry + menu_data ----
tc_load_menu = 'def load_menu_data' in toolchain_src
check('15 Toolchain load_menu_data', tc_load_menu, '(Menu-Data-Loader)')

# ---- summary ----
print('\n'.join(results))
print('\n==== %d passed, %d failed ====' % (PASS, FAIL))
sys.exit(0 if FAIL == 0 else 1)
