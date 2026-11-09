#!/usr/bin/env python3
"""R232 preset audit: save -> load -> delete for EVERY generator preset engine.

Field report (.136z): 'im Bricks-Tool funktioniert das Loeschen der Queue
nicht' + 'beim Texturing funktioniert glaub ich auch das Speichern von
Presets nicht'. The ask: audit saving, loading and deleting presets for
EVERY tool that uses them in any form.

What this battery proves, per generator (all 13 the engine knows):
  S1  SAVE renders a SAVE_VARIABLE whose VALUE survives Klipper's REAL
      pipeline: POSIX shlex splits the command, ast.literal_eval parses the
      value (the R188 rule) - the stored object is a dict with the snapshot
  S2  the snapshot carries every key the engine's gens[] list promises for
      this generator (a preset that lacks keys 'loads' without moving the
      settings - the old frame field log)
  S3  LOAD (page 0, slot 0) re-emits one SAVE_VARIABLE per key; string
      values come back QUOTED (shlex-proof), numbers/bools stay naked
  S4  DELETE (page 0, slot 0) writes the store WITHOUT the entry and says so
  S5  the LIBRARY shelf: a lib preset loads, a lib delete REFUSES
  S6  CORRUPT-STORE SELF-HEAL: a store saved as a plain string (the silent
      engine killer - dict() on a string raises) no longer kills the macro:
      save works, the store starts fresh, the user hears why

The macros render through the SAME Klipper-mirroring harness macro_render
_test uses (single-brace env, save_variables mock, klipper_strip).
"""

import os
import re
import sys
import ast
import shlex

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
sys.path.insert(0, REPO)

src = open(os.path.join(HERE, 'macro_render_test.py'),
           encoding='utf-8').read()
head = src[:src.index('tests = [')]
ns = {}
exec(compile(head, 'harness', 'exec'), ns)
render, save_vars, state_vars = ns['render'], ns['save_vars'], ns['state_vars']
get_body = ns['get_body']

# R232: render through KLIPPER'S EXACT environment - the big harness uses
# trim_blocks=True for readable output, but klipper's gcode_macro.py builds
# jinja2.Environment('{%', '%}', '{', '}') with the DEFAULT trim_blocks=False
# (verified against klipper master 2026-08). The stricter harness MERGES
# '{% if %}_PACE{% endif %}' with the next line - a phantom bug Klipper cannot
# produce (it keeps every newline). This battery must judge FIELD truth.
from jinja2 import Environment as _E232, BaseLoader as _B232
env232 = _E232(loader=_B232(), variable_start_string='{',
              variable_end_string='}', block_start_string='{%',
              block_end_string='%}', comment_start_string='{#',
              comment_end_string='#}')          # trim_blocks NOT set = klipper

# the REAL 44-look texture library (a Python dict literal in the cfg) - the
# harness mock ships a neutral empty one, S5 needs the real shelf
_libline = [l for l in open(os.path.join(REPO, 'macros', '17_generator.cfg'),
                            encoding='utf-8')
            if l.startswith('variable_texture_lib:')][0]
REAL_LIB = ast.literal_eval(_libline.split('variable_texture_lib:', 1)[1].strip())


def render232(tpl, par=None):
    pr = ns['build_printer']()
    pr['gcode_macro _GEN_PRESET'] = ns['M']({'texture_lib': REAL_LIB})
    g = {'printer': pr, 'params': par or {}}
    return env232.from_string(tpl).render(**g)


BODY = get_body(os.path.join('macros', '17_generator.cfg'), '_GEN_PRESET')

# the engine's own generator list (kept in sync by S2: every entry here must
# exist in the macro - the battery fails if either side drifts)
GENS = {
    'texture': ['texture_mode', 'texture_pattern', 'texture_scale',
                'texture_zsize', 'texture_amp', 'texture_dir'],
    'litho': ['litho_height', 'litho_layer_h', 'litho_contrast',
              'litho_colors', 'litho_orient'],
    'label': ['label_l', 'label_h', 'label_font', 'label_base_layers',
              'label_shape', 'label_mode'],
    'plot': ['plot_mode', 'plot_colors', 'plot_spacing', 'plot_size'],
    'tie': ['tie_count', 'tie_length', 'tie_width', 'tie_variant'],
    'angle': ['angle_deg', 'angle_leg_a', 'angle_leg_b', 'angle_walls'],
    'seal': ['seal_id', 'seal_od', 'seal_height', 'seal_profile'],
    'frame': ['frame_w', 'frame_h', 'frame_depth', 'frame_walls'],
    'bricks': ['brick_mode', 'brick_count', 'brick_colors'],
    'brickkit': ['brickkit_mode', 'brickkit_index', 'brickkit_detail'],
    'figures': ['figures_mode', 'figures_count', 'figures_scale'],
    'colorpic': ['colorpic_bands', 'colorpic_width', 'colorpic_colors'],
    'stringart': ['stringart_pattern', 'stringart_diameter',
                  'stringart_anchors', 'stringart_lines'],
}

# realistic current settings per generator (what sv carries on a real box)
SEED = {
    'texture': {'texture_mode': 'BUMPS', 'texture_fuzzy_thick': 0.3,
                'texture_fuzzy_density': 100, 'texture_pattern': 'ROPE',
                'texture_scale': 14.0, 'texture_zsize': 10.0,
                'texture_amp': 0.5, 'texture_dir': 'OUT',
                'texture_seed': 23},
    'litho': {'litho_height': 0.6, 'litho_layer_h': 0.2,
              'litho_contrast': 1.1, 'litho_levels': 4,
              'litho_colors': 2, 'litho_colmode': 'EACH',
              'litho_col_layers': 2, 'litho_border': 2.0,
              'litho_corner': 2.0, 'litho_brim': True,
              'litho_ironing': True, 'litho_frame': 0,
              'litho_handle': 0, 'litho_stamp': 0,
              'litho_stamp_base': 5.0, 'litho_stamp_tol': 0.25,
              'litho_orient': 'FLAT', 'litho_mirror_x': 0,
              'litho_mirror_y': 0, 'litho_contour': 0},
    'label': {'label_mode': 'grow', 'label_shape': 'RECT',
              'label_l': 'TEST', 'label_h': 30, 'label_size': 0,
              'label_font': 'SMOOTH', 'label_lines': 1,
              'label_max_chars': 14, 'label_spacing': 0,
              'label_layer_h': 0.2, 'label_first_h': 0.28,
              'label_base_layers': 4, 'label_border_walls': 0,
              'label_border_gap': 0, 'label_corner': 0,
              'label_hole_d': 5.0, 'label_hole_side': 1,
              'label_brim': True, 'label_ironing': True,
              'label_mirror_x': 0, 'label_mirror_y': 0,
              'label_handle': 0, 'label_height': 0,
              'label_pos': 1, 'label_gap': 6, 'label_color2': True},
    'plot': {'plot_mode': 'DOTS', 'plot_colors': 2,
             'plot_spacing': 2.5, 'plot_dot_gap': 0.5,
             'plot_speed': 40, 'plot_size': 120,
             'plot_scale_x': 1.0, 'plot_scale_y': 1.0,
             'plot_off_x': 0, 'plot_off_y': 0, 'plot_off_z': 0,
             'plot_extrude': 0.05, 'plot_fil_z': 0.2,
             'plot_invert': 0, 'plot_autocontrast': 1},
    'tie': {'tie_count': 6, 'tie_length': 60, 'tie_width': 4,
            'tie_layers': 3, 'tie_variant': 'HOOK'},
    'angle': {'angle_deg': 90, 'angle_width': 30, 'angle_leg_a': 20,
              'angle_leg_b': 20, 'angle_holes': 1, 'angle_hole_d': 3.2,
              'angle_countersink': 0, 'angle_flat': 1,
              'angle_stiffener': 1, 'angle_walls': 2,
              'angle_infill': 15, 'angle_ironing': 0,
              'angle_layers': 12, 'angle_layer_h': 0.2,
              'angle_count': 2},
    'seal': {'seal_id': 20, 'seal_od': 26, 'seal_height': 3,
             'seal_profile': 'NBR70', 'seal_layer_h': 0.2,
             'seal_ironing': 1},
    'frame': {'frame_preset': 'A5', 'frame_w': 148, 'frame_h': 210,
              'frame_depth': 8, 'frame_border': 12, 'frame_corner': 3,
              'frame_walls': 2, 'frame_shape': 'RECT',
              'frame_closure': 'BACK', 'frame_hang': 1, 'frame_stand': 0,
              'frame_ironing': 1, 'frame_infill': 15,
              'frame_top_l': 2, 'frame_bot_l': 2, 'frame_front': 1,
              'frame_cable': 0, 'frame_disc': 0, 'frame_disc_t': 2,
              'frame_disc_side': 1, 'frame_s_deep': 1.2,
              'frame_s_space': 8, 'frame_s_angle': 45,
              'frame_s_amp': 0.6, 'frame_s_size': 12,
              'frame_s_dir': 'OUT'},
    'bricks': {'brick_mode': 'BY_LAYER', 'brick_count': 2,
               'brick_colors': 1, 'bricks_layer_h': 0.2,
               'brick_brim': 2},
    'brickkit': {'brickkit_mode': 'BY_LAYER', 'brickkit_index': 0,
                 'brickkit_detail': 2, 'brickkit_colors': 3},
    'figures': {'figures_mode': 'BY_LAYER', 'figures_count': 8,
                'figures_scale': 100, 'figures_colors': 2,
                'figures_colormode': 'EACH', 'figures_brim': 1},
    'colorpic': {'colorpic_bands': 3, 'colorpic_bandh': 0.8,
                 'colorpic_width': 100, 'colorpic_colors': 3,
                 'colorpic_contrast': 1.0, 'colorpic_swap': 0,
                 'colorpic_ironing': 1, 'colorpic_layer_h': 0.2,
                 'colorpic_brim': 1},
    'stringart': {'stringart_pattern': 'SPIRAL', 'stringart_diameter': 100,
                  'stringart_anchors': 60, 'stringart_lines': 150},
}

fails = 0
checks = 0


def check(name, ok, ev=''):
    global fails, checks
    checks += 1
    print('%s  %s %s' % ('PASS' if ok else 'FAIL', name,
                         ('-> ' + str(ev)) if not ok else ''))
    if not ok:
        fails += 1


def klipper_value(line):
    """Klipper's real pipeline: shlex splits, literal_eval parses VALUE."""
    toks = shlex.split(line.strip())
    kv = {}
    for t in toks[1:]:
        if '=' in t:
            k, v = t.split('=', 1)
            kv[k] = v
    return ast.literal_eval(kv['VALUE'])


# S7: the engine's gens dict must know exactly our 13 generators
m = re.search(r'\{% set gens = \{(.*?)\} %\}', BODY, re.S)
gens_keys = re.findall(r"'([a-z]+)':", m.group(1)) if m else []
check('S7 the engine knows exactly the audited generators',
      sorted(gens_keys) == sorted(GENS), str(sorted(set(gens_keys)
                                                   ^ set(GENS))))

for gen, keys in GENS.items():
    tag = gen.upper()
    # --- fresh state, realistic settings ---
    save_vars.update(SEED[gen])
    save_vars['%s_user_presets' % gen] = {}
    save_vars['%s_preset_page' % gen] = 0
    save_vars['%s_lib_page' % gen] = 0

    # S1: save -> a dict lands in the store (shlex + literal_eval)
    out = render232(BODY, {'ACTION': 'save', 'GEN': gen, 'NAME': 'audit'})
    svl = [l.strip() for l in out.split('\n')
           if 'SAVE_VARIABLE' in l and '_user_presets' in l]
    ok = bool(svl)
    store = None
    if ok:
        try:
            store = klipper_value(svl[0])
            ok = isinstance(store, dict) and len(store) == 1
        except Exception as e:
            ok = False
            ev = repr(e)[:60]
    check('S1 %s save: store value survives shlex+literal_eval (dict)' % tag,
          ok, svl[:1] if not ok else '')
    if not isinstance(store, dict) or not store:
        continue
    nm = list(store)[0]
    snap = store[nm]

    # S2: the snapshot carries the promised keys
    missing = [k for k in keys if k not in snap]
    check('S2 %s snapshot carries the headline keys (%d values)'
          % (tag, len(snap)), not missing, 'missing %r' % missing)

    # S3: load re-emits per-key saves, strings quoted, numbers naked
    save_vars['%s_user_presets' % gen] = store
    out = render232(BODY, {'ACTION': 'load', 'GEN': gen, 'SLOT': '0'})
    applied = {}
    bad_lines = []
    for l in out.split('\n'):
        l = l.strip()
        if l.startswith('SAVE_VARIABLE') and '_user_presets' not in l:
            mm = re.match(r'SAVE_VARIABLE VARIABLE=(\S+) VALUE=(.*)$', l)
            if not mm:
                bad_lines.append(l)
                continue
            try:
                applied[mm.group(1)] = klipper_value(l)
            except Exception:
                bad_lines.append(l)
    want = {k: SEED[gen][k] for k in snap}
    got = {k: applied.get(k) for k in want}
    check('S3 %s load: every key re-saved, values round-trip exactly' % tag,
          not bad_lines and got == want,
          'bad=%r got=%r' % (bad_lines[:2], got))

    # S4: delete removes the entry, store becomes empty
    out = render232(BODY, {'ACTION': 'delete', 'GEN': gen, 'SLOT': '0'})
    svl = [l.strip() for l in out.split('\n')
           if 'SAVE_VARIABLE' in l and '_user_presets' in l]
    ok = bool(svl)
    if ok:
        try:
            ok = klipper_value(svl[0]) == {}
        except Exception:
            ok = False
    check('S4 %s delete: store without the entry' % tag, ok, svl[:1])

# S5: the texture library shelf - load works, delete refuses
save_vars.update(SEED['texture'])
save_vars['texture_user_presets'] = {}
save_vars['texture_lib_page'] = 0
out = render232(BODY, {'ACTION': 'load', 'GEN': 'texture', 'SLOT': '0',
                    'SRC': 'lib'})
lib_nm = ''
mo = re.search(r"loaded: ", out)
check('S5 texture LIBRARY load works (read-only looks apply)',
      mo is not None and 'SAVE_VARIABLE VARIABLE=texture_pattern' in out,
      out[:120])
out = render232(BODY, {'ACTION': 'delete', 'GEN': 'texture', 'SLOT': '0',
                    'SRC': 'lib'})
check('S5 texture LIBRARY delete refuses honestly',
      'LIBRARY look - read-only' in out
      and '_user_presets' not in ' '.join(out.split()), out[:120])

# S6: a corrupt store (plain string) must not kill the engine
save_vars.update(SEED['texture'])
save_vars['texture_user_presets'] = "{'junk': {'texture_amp': 1}}"
out = render232(BODY, {'ACTION': 'save', 'GEN': 'texture', 'NAME': 'ROPE'})
svl = [l.strip() for l in out.split('\n')
       if 'SAVE_VARIABLE' in l and '_user_presets' in l]
ok = False
if svl:
    try:
        st = klipper_value(svl[0])
        ok = isinstance(st, dict) and 'ROPE01' in st
    except Exception:
        ok = False
check('S6 CORRUPT store: engine survives, save starts fresh + says why',
      ok and 'corrupt' in out, out[:150])

# S6b: the corrupt note must not appear on a healthy store
save_vars['texture_user_presets'] = {}
out = render232(BODY, {'ACTION': 'save', 'GEN': 'texture', 'NAME': 'ROPE'})
check('S6b healthy store: no false corrupt warning',
      'corrupt' not in out and 'SAVED' in out, out[:120])

# S8: pre-fix pollution heal - a store with library copies baked in
# (what the old delete wrote) gets cleaned AND persisted on the next touch
import copy
pol = {k: copy.deepcopy(v) for k, v in list(REAL_LIB.items())[:5]}
pol['myown'] = dict(SEED['texture'])
save_vars['texture_user_presets'] = pol
out = render232(BODY, {'ACTION': 'page', 'GEN': 'texture', 'DELTA': '0'})
heal_line = [l.strip() for l in out.split('\n')
             if 'SAVE_VARIABLE' in l and '_user_presets' in l]
ok = False
if heal_line:
    try:
        st = klipper_value(heal_line[0])
        ok = (isinstance(st, dict) and list(st) == ['myown']
              and 'healed' in out and '5 library copies' in out)
    except Exception:
        ok = False
check('S8 pre-fix pollution: 5 library copies heal + persist, own preset stays',
      ok, out[:160])

print()
if fails:
    print('R232 PRESET AUDIT: %d checks, %d FAIL' % (checks, fails))
    sys.exit(1)
print('R232 PRESET AUDIT: %d checks, 0 FAIL - save/load/delete green '
      'for every generator' % checks)
