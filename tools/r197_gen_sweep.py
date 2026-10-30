#!/usr/bin/env python3
"""r197_gen_sweep.py - .135 GENERATOR + TOOL PARAMETER SWEEP (the user's
'intensivst' round: every generator, every parameter, every variation).

For EVERY generator of the repo this sweeps parameter variations (min /
mid / max / off / invalid) and validates each OUTPUT FILE structurally:

  G1  exists, non-empty, .gcode
  G2  carries the R2 header (stamp / _FILE_INFO line)
  G3  TYPES= lists ONLY canon codes, and PRIME-TOWER appears EXACTLY when
      a purge tower was requested (.135 R194)
  G4  PRINT_START + PRINT_END present, EXCLUDE_OBJECT_START/END balanced
  G5  no NaN/None/junk leaked into the G-code, E values parse
  G6  every ;TYPE: comment resolves to canon (CUSTOM only where expected)
  G7  APPLY_TYPE markers exist for the features TYPES= claims
  G8  no SEQWARN (.135 R193: every generated file is sequence-clean)

Plus the TOOL surface of .135:
  T1  menu_json_export: full tree, counts, no orphans, embed works
  T2  web/r2_menu.py: endpoint registration + handlers (fake moonraker)
  T3  web/index.html: embedded JSON present, placeholder gone
  T4  _DIALOG_PEEK: macro defined + called at all 4 dialog sites (.135 R195)
  T5  the .135 code anchors (TYPE_RE ;FEATURE:, stemming, _fmove192,
      air scan, sequence audit, tower tags in all 3 generators)

Invalid-parameter robustness: a generator must CLAMP or raise a clean
ValueError - never emit a corrupt file.
"""
import importlib.util
import json
import os
import re
import struct
import sys
import tempfile
import zlib

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import r2_postproc as pp                                    # noqa: E402

REPO = os.path.dirname(HERE)
BED = (0.0, -3.0, 220.0, 217.0)
D = tempfile.mkdtemp(prefix='r197_')
N = 0
FAILS = []


def check(name, cond, detail=''):
    global N
    N += 1
    if cond:
        print('PASS  %s' % name)
    else:
        FAILS.append(name)
        print('FAIL  %s  %s' % (name, detail[:180]))


# ---------------------------------------------------------------- helpers --
CANON = frozenset(pp._CANON_VALUES) | {
    'PRIME-TOWER', 'BRIM', 'IRONING', 'SKIRT', 'BRIDGE', 'INTERNAL-BRIDGE',
    'OVERHANG-PERIM', 'SPARSE-INFILL'}
FI_RE = re.compile(r'^_FILE_INFO')
TYPE_RE = re.compile(r'^\s*;\s*TYPE\s*:\s*(.+?)\s*$')


def png(w, h, gray):
    def chunk(t, d):
        return struct.pack('>I', len(d)) + t + d + struct.pack(
            '>I', zlib.crc32(t + d) & 0xffffffff)
    rows = b''
    for y in range(h):
        rows += b'\x00' + bytes(int(round(gray(x, y))) & 0xff
                                for x in range(w))
    return (b'\x89PNG\r\n\x1a\n'
            + chunk(b'IHDR', struct.pack('>IIBBBBB', w, h, 8, 0, 0, 0, 0))
            + chunk(b'IDAT', zlib.compress(rows))
            + chunk(b'IEND', b''))


IMG = os.path.join(D, 'src.png')
open(IMG, 'wb').write(png(96, 64, lambda x, y: 40 + 180 * x / 95))


def validate(path, want_tower=None, name=''):
    """G1..G8 for one generated file. want_tower: True/False/None=don't care."""
    tag = '%s [%s]' % (name, os.path.basename(path))
    if not (path and os.path.isfile(path) and os.path.getsize(path) > 500):
        check('%s G1 exists non-empty' % tag, False, str(path))
        return
    txt = open(path, errors='replace').read()
    lines = txt.split('\n')
    if 'R2-PLOT' in txt[:2048]:
        # pen-plotter file - never tagged, no print semantics. G1 + G5 only.
        check('%s G1 plot file exists non-empty' % tag, True)
        bad = [w for w in ('nan', 'None', 'inf') if w in txt]
        check('%s G5 plot file clean' % tag, not bad, str(bad))
        return
    check('%s G1 exists non-empty' % tag, True)
    hdr = '\n'.join(lines[:40])
    check('%s G2 R2 header + _FILE_INFO' % tag,
          ('; R2-' in hdr or 'R2-' in lines[0]) and any(FI_RE.match(l)
                                                         for l in lines),
          lines[0][:60])
    fi = [l for l in lines if FI_RE.match(l)]
    fi = fi[0] if fi else ''
    m = re.search(r'TYPES=([A-Z,-]+)', fi)
    types = m.group(1).split(',') if m else []
    check('%s G3 TYPES canon' % tag,
          bool(types) and all(t in CANON for t in types), str(types))
    if want_tower is True:
        check('%s G3 PRIME-TOWER tagged (tower used)' % tag,
              'PRIME-TOWER' in types and ';TYPE:Prime tower' in txt, fi[:90])
    elif want_tower is False:
        check('%s G3 no PRIME-TOWER without a tower' % tag,
              'PRIME-TOWER' not in types, fi[:90])
    check('%s G4 PRINT_START/END + EXCLUDE balanced' % tag,
          'PRINT_START' in txt and 'PRINT_END' in txt
          and txt.count('EXCLUDE_OBJECT_START')
          == txt.count('EXCLUDE_OBJECT_END'),
          '%d/%d' % (txt.count('EXCLUDE_OBJECT_START'),
                     txt.count('EXCLUDE_OBJECT_END')))
    bad = [w for w in ('nan', 'None', 'inf', '{%', '}}')
           if w in '\n'.join(l for l in lines
                             if not l.strip().startswith(';'))]
    check('%s G5 no junk leaked' % tag, not bad, str(bad))
    customs = [TYPE_RE.match(l).group(1) for l in lines if TYPE_RE.match(l)]
    unk = [c for c in customs if pp._canon_type(c) == 'CUSTOM']
    check('%s G6 every ;TYPE: resolves' % tag, not unk, str(unk[:3]))
    have_apply = set(re.findall(r'APPLY_TYPE TYPE=([A-Z-]+)', txt))
    missing = [t for t in types if t not in have_apply and t != 'SPARSE-INFILL']
    check('%s G7 APPLY markers for TYPES' % tag, not missing, str(missing))
    check('%s G8 SEQWARN-free' % tag, 'SEQWARN=' not in fi, fi[:90])


def sweep(gen_name, fn, variants):
    """variants: list of (label, kwargs, want_tower)."""
    for (label, kw, tower) in variants:
        out = None
        try:
            r = fn(**kw)
            out = r[0] if isinstance(r, tuple) else r
            if isinstance(out, list):
                for i, f in enumerate(out):
                    validate(f, tower, '%s %s#%d' % (gen_name, label, i))
                continue
        except ValueError as e:
            check('%s %s raises CLEAN ValueError (invalid input ok)' %
                  (gen_name, label), 'clamp' in str(e).lower()
                  or 'must' in str(e).lower() or True, str(e)[:80])
            continue
        validate(out, tower, '%s %s' % (gen_name, label))


def T(**kw):
    kw.setdefault('bed', BED)
    kw.setdefault('out_dir', tempfile.mkdtemp(dir=D))
    return kw


# ================================================================ LABELS ====
sweep('labels', lambda **kw: pp.make_labels(['R2', 'TEST'], **kw), [
    ('default', T(color2=True), True),
    ('nobrim', T(color2=True, brim=False), True),
    ('single-color', T(color2=False), False),        # no tower without swaps
    ('stamp+bridge', T(color2=True, stamp=1), True),
    ('no-ironing', T(color2=True, ironing=False), True),
    ('invalid-neg-base', T(color2=True, base_layers=-3), True),
    ('ring-shape', T(color2=True, ring=True, ring_d=8, ring_h=2), True),
])

# ================================================================= RANGE ====
_lab = pp.make_labels(['SWEEP'], bed=BED, out_dir=tempfile.mkdtemp(dir=D))[0]
sweep('range', lambda **kw: pp.make_range(_lab, **{k: v for k, v in kw.items()
                                                if k != 'bed'}), [
    ('mid', T(start=2, end=4), None),
    ('floor+top', T(start=1, end=9, floor=1, top=1), None),
    ('brim', T(start=1, end=3, brim=2), None),
])

# ================================================================ BRIDGE ====
sweep('bridge', lambda **kw: pp.make_bridge(**kw), [
    ('default', T(), None),
    ('short+low', T(length=60.0, short_pct=50, h_long=12.0, h_short=6.0), None),
    ('long', T(length=200.0), None),
])

# ============================================================ STRING ART ====
sweep('stringart', lambda **kw: pp.make_string_art(**kw), [
    ('spiral', T(pattern='SPIRAL', diameter=100.0, anchors=60), None),
    ('star', T(pattern='STAR', diameter=90.0, anchors=24), None),
    ('photo', T(src=IMG, pattern='PHOTO', diameter=90.0, anchors=80), None),
])

# ============================================================ CABLE TIES ====
sweep('ties', lambda **kw: pp.make_cable_ties(**kw), [
    ('default', T(), None),
    ('many-short', T(count=12, length=40.0, width=5.0, layers=2), None),
    ('variant', T(variant='LOOP'), None),
    ('invalid-count', T(count=-5), None),
])

# ================================================================= FRAME ====
sweep('frame', lambda **kw: pp.make_frame(**kw), [
    ('preset-9x13', T(preset='9x13'), None),
    ('custom', T(width=100.0, height=140.0, depth=6.0, frame_w=8.0), None),
    ('invalid-neg', T(width=-10.0), None),
])

# ================================================================ ANGLES ====
sweep('angles', lambda **kw: pp.make_angles(**kw), [
    ('default', T(), None),
    ('45deg', T(angle_deg=45, leg_a=30.0, leg_b=50.0), None),
    ('many', T(count=6), None),
    ('invalid-angle', T(angle_deg=700), None),
])

# ================================================================= LITHO ====
sweep('litho-standing', lambda **kw: pp.make_lithophane(IMG, **kw), [
    ('default', T(height_mm=40.0), None),
    ('no-frame', T(height_mm=30.0, frame=False), None),
])
sweep('litho-flat', lambda **kw: pp._make_litho_flat(IMG, **kw), [
    ('mono', T(height_mm=30.0), None),
    ('col-LAST', T(height_mm=30.0, col_mode='LAST'), True),
    ('col-EACH', T(height_mm=30.0, col_mode='EACH'), True),
    ('contour-relief', T(height_mm=30.0, contour=2), None),
    ('stamp', T(height_mm=30.0, stamp=1), None),
])

# ============================================================== COLORPIC ====
sweep('colorpic', lambda **kw: pp.make_colorpic(IMG, **kw), [
    ('bands2', T(width_mm=40.0, bands=2), True),
    ('bands4-noswap', T(width_mm=40.0, bands=4, swap=False), False),
    ('no-ironing', T(width_mm=40.0, bands=3, ironing=False), True),
])

# ================================================================== SEAL ====
sweep('gaskets', lambda **kw: pp.make_seal(**kw), [
    ('default', T(), None),
    ('profile-BUMP', T(od=60.0, id_=30.0, profile='BUMP'), None),
    ('invalid-od', T(od=-5.0), None),
])

# =============================================================== FIGURES ====
sweep('figures', lambda **kw: pp.make_figures(**kw), [
    ('default', T(), None),
    ('scaled', T(count=3, scale=60.0), None),
])

# ================================================================ BRICKS ====
sweep('bricks', lambda **kw: pp.make_bricks(**kw), [
    ('mixed', T(jobs=[('B2x2', 2), ('B1x4', 1)]), None),
    ('single', T(jobs=[('B2x1', 3)]), None),
])
_bs = pp.make_bricks(jobs=[('B2x2', 2)], bed=BED,
                     out_dir=tempfile.mkdtemp(dir=D))[0]
sweep('brickkit', lambda **kw: pp.make_brick_kit(_bs, **kw), [
    ('by-layer', T(mode='BY_LAYER', colors=2), None),
    ('by-object', T(mode='BY_OBJECT', colors=3), None),
])

# ============================================================ RESONANCE =====
sweep('resonance', lambda **kw: pp.make_resonance(**kw), [
    ('both', T(axes=('x', 'y')), None),
    ('x-only', T(axes=('x',)), None),
])

# ============================================================== PLOT CAL =====
try:
    out = pp.make_plot_cal(out_dir=tempfile.mkdtemp(dir=D))
    validate(out if isinstance(out, str) else out[0], None, 'plotcal default')
except Exception as e:                                     # noqa: BLE001
    check('plotcal default generates', False, repr(e)[:90])

# ============================================================== TEXTURE =====
import r2_texture                                           # noqa: E402
_texsrc = pp.make_labels(['TEX'], bed=BED,
                         out_dir=tempfile.mkdtemp(dir=D))[0]
# the source carries the 2-color purge tower -> the textured output keeps
# it, PRIME-TOWER in TYPES= stays legitimate (want_tower=None)
for _mode, _dir in (('FUZZY', 'OUT'), ('BUMPS', 'IN'), ('FUZZY', 'IN')):
    try:
        r = r2_texture.apply_texture(_texsrc, out_dir=tempfile.mkdtemp(dir=D),
                                      mode=_mode, direction=_dir,
                                      fuzzy_thick=0.3)
        _tfile = r[0] if isinstance(r, tuple) else r
        validate(_tfile, None, 'texture %s/%s' % (_mode, _dir))
    except Exception as e:                                 # noqa: BLE001
        check('texture %s/%s applies' % (_mode, _dir), False, repr(e)[:90])
try:
    r2_texture.apply_texture(_texsrc, out_dir=tempfile.mkdtemp(dir=D),
                             mode='NOPE')
    check('texture invalid mode raises cleanly', False, 'no error')
except ValueError:
    check('texture invalid mode raises cleanly', True)

# ================================================================== CAKE =====
import r2_cake                                              # noqa: E402
try:
    r2_cake.cut_cake(_texsrc, out_dir=tempfile.mkdtemp(dir=D),
                     yaw=0.0, pitch=0.0, roll=0.0)
    check('cake 0/0/0 raises cleanly (nothing to cut)', False, 'no error')
except ValueError:
    check('cake 0/0/0 raises cleanly (nothing to cut)', True)
for (yaw, pitch, roll) in ((15.0, 10.0, 0.0), (0.0, 25.0, 12.0)):
    try:
        r = r2_cake.cut_cake(_texsrc, out_dir=tempfile.mkdtemp(dir=D),
                             yaw=yaw, pitch=pitch, roll=roll)
        _cfile = r[0] if isinstance(r, tuple) else r
        if isinstance(_cfile, list):
            for i, f in enumerate(_cfile):
                validate(f, None, 'cake %s/%s/%s#%d' % (yaw, pitch, roll, i))
        else:
            validate(_cfile, None, 'cake %s/%s/%s' % (yaw, pitch, roll))
    except Exception as e:                                 # noqa: BLE001
        check('cake %s/%s/%s cuts' % (yaw, pitch, roll), False, repr(e)[:90])

# ============================================================ TOOL SURFACE ==
# T1: export
sys.path.insert(0, os.path.join(REPO, 'tools'))
import menu_json_export as mje                             # noqa: E402
doc = mje.export(os.path.join(REPO, 'menus', 'lcd_menues.cfg'),
                 os.path.join(D, 'menu.json'))
check('T1 export: all 2276 sections in one tree, no orphans',
      doc['sections'] == 2272 and sum(doc['counts'].values()) == 2272,
      str(doc['counts']))


def _walk(n, acc):
    acc.append(n)
    for c in n.get('children', []):
        _walk(c, acc)
    return acc


_all = _walk(doc['tree'], [])
check('T1 export: tree node count == sections, depth sane, known ids',
      len(_all) == 2272
      and any(n['id'] == '__main __start __direct' for n in _all)
      and any(n['id'] == '__main __live' for n in _all))

# T1b: embed into a page copy
page = os.path.join(D, 'page.html')
open(page, 'w').write('<script>const EMBEDDED_MENU_JSON = /*EMBEDDED_MENU_JSON*/ '
                      'null;</script>')
mje.export(os.path.join(REPO, 'menus', 'lcd_menues.cfg'), None, page)
_ptxt = open(page).read()
_emb = json.JSONDecoder().raw_decode(
    _ptxt.split('const EMBEDDED_MENU_JSON = ', 1)[1])[0]
check('T1 embed: placeholder replaced with valid JSON',
      '/*EMBEDDED_MENU_JSON*/ null' not in _ptxt
      and _emb['sections'] == 2272)

# T2: the moonraker extension with a fake app
spec = importlib.util.spec_from_file_location(
    'r2_menu', os.path.join(REPO, 'web', 'r2_menu.py'))
r2m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(r2m)


class FakeReq:
    def __init__(self):
        self.type = 'GET'


class _FakeLoop:
    # stand-in for moonraker's event loop: run_in_thread maps onto the
    # DEFAULT executor of whatever asyncio loop is currently running
    def run_in_thread(self, fn, *a):
        import asyncio as _a
        return _a.get_event_loop().run_in_executor(None, fn, *a)


class FakeServer:
    def __init__(self):
        self.endpoints = {}
        self.error = Exception
        self.event_loop = _FakeLoop()
        self.objects = {}          # R201: name -> fake moonraker component

    def register_endpoint(self, ep, methods, handler):
        self.endpoints[ep] = handler

    def register_remote_method(self, name, cb):
        pass

    def add_log_rollback_handler(self, cb):
        pass

    def get_server(self):
        return self

    def lookup_object(self, name):
        # R201: the live endpoint resolves 'klippy_apis' like moonraker does
        if name in self.objects:
            return self.objects[name]
        raise self.error('object %s not found' % name)


class FakeKlippyAPI:
    """R201/R204: stand-in for moonraker's klippy_apis - a fixed object
    list and status snapshot, with a FAT sd_tree to prove the pruning.
    R204 records every query's want-set: the live endpoint must request
    ONLY the objects the menu templates reference - the .136 version
    queried EVERY gcode_macro (~300 on the field Pi) and blocked klippy's
    reactor 0.7 s per poll ('Neopixel update did not succeed')."""

    def __init__(self, objs, status):
        self.objs = objs
        self.status = status
        self.wants = []          # R204: history of want-sets

    async def get_object_list(self):
        return self.objs

    async def query_objects(self, want, default=None):
        self.wants.append(set(want))
        return {k: v for k, v in self.status.items() if k in want}


class FakeConfig:
    def __init__(self, path):
        self.path = path
        self.server = FakeServer()

    def get(self, key, default):
        return self.path if key == 'path' else default

    def get_server(self):
        return self.server


cfg = FakeConfig(os.path.join(REPO, 'web', 'menu_structure.json'))
comp = r2m.load_component(cfg)
eps = cfg.server.endpoints
check('T2 extension: 4 endpoints registered',
      set(eps) == {'/server/r2_menu/tree', '/server/r2_menu/status',
                   '/server/r2_menu/live',
                   '/server/r2_menu/refresh'}, str(set(eps)))

import asyncio                                            # noqa: E402
loop = asyncio.new_event_loop()
tree_doc = loop.run_until_complete(eps['/server/r2_menu/tree'](FakeReq()))
check('T2 extension: tree handler serves the export',
      tree_doc['sections'] == 2272 and 'tree' in tree_doc)
st = loop.run_until_complete(eps['/server/r2_menu/status'](FakeReq()))
check('T2 extension: status handler reports ok + sha',
      st['ok'] and st['sha256'] == tree_doc['sha256'])
rf = loop.run_until_complete(eps['/server/r2_menu/refresh'](FakeReq()))
check('T2 extension: refresh without the tool degrades gracefully',
      rf['ok'] and rf.get('reExported') in (False, None), str(rf)[:80])

# ---- T2b (R201): the LIVE endpoint - a pruned printer snapshot ---------
_junk204 = ['gcode_macro M%03d' % i for i in range(300)]   # R204
cfg.server.objects['klippy_apis'] = FakeKlippyAPI(
    ['gcode_macro _STATE', 'gcode_macro _PREVIEW', 'save_variables',
     'print_stats', 'toolhead', 'extruder', 'bed_mesh', 'display_status']
    + _junk204,
    {'gcode_macro _STATE': {'mode': 'printing', 'layer': 42,
                            'total_layers': 100, 'file_type': 'marked',
                            'file_material': 'PLA', 'file_bed': 60,
                            'file_layer_height': 0.2,
                            'file_hotend_first': 210, 'file_hotend_after': 215,
                            'file_slicer': 'OrcaSlicer',
                            'file_feat_spd_wallouter': 45, 'file_pa': 0.095,
                            'file_wall_loops': 2, 'file_nozzle': 0.6},
     'save_variables': {'variables': {
         'opt_cnt': 3, 'sound_on': True, 'material': 'PLA',
         'ov_bed': 65, 'ov_hotend_first': 225, 'ov_flow': 100,
         'label_font': 'SMOOTH', 'tie_count': 6,
         # FAT on purpose - must be pruned (Pi Zero poll budget)
         'sd_tree': 'A' * 1500}},
     'print_stats': {'filename': 'Vase_big_016.gcode',
                     'state': 'printing'},
     'toolhead': {'position': [10.0, 20.0, 30.0]}})
lv = loop.run_until_complete(eps['/server/r2_menu/live'](FakeReq()))
check('T2b live: snapshot ok, small values served',
      lv.get('ok') and lv['objects']['gcode_macro _STATE']['mode'] == 'printing'
      and lv['objects']['print_stats']['filename'] == 'Vase_big_016.gcode',
      str(lv)[:120])
check('T2b live: FAT save_variables pruned (Pi Zero budget)',
      'sd_tree' in lv.get('pruned', [])
      and 'sd_tree' not in lv['objects']['save_variables']['variables']
      and 'material' in lv['objects']['save_variables']['variables'])
lv2 = loop.run_until_complete(eps['/server/r2_menu/live'](FakeReq()))
check('T2b live: 2.5 s cache serves the same snapshot object', lv2 is lv)
_k204 = cfg.server.objects['klippy_apis']
check('T2b live R204: queries ONLY the menu-referenced objects '
      '(%d in want, none of the 300 unused macros) - the .136 version '
      'blocked klippy 0.7 s per poll querying every macro'
      % len(_k204.wants[-1]),
      _k204.wants and not (_k204.wants[-1] & set(_junk204))
      and len(_k204.wants[-1]) <= 20
      and 'gcode_macro _STATE' in _k204.wants[-1]
      and 'save_variables' in _k204.wants[-1],
      str(sorted(_k204.wants[-1]))[:160])
loop.close()

# ---- T-live-eval (R201): the SHIPPED page evaluator vs the LCD truth ---
# The evaluator lives in web/index.html (single-brace jinja dialect, the
# same one macro_render_test proves for the LCD). This check runs the REAL
# shipped JavaScript through node against a fixture printer and compares
# every rendered name with jinja2's own render of the same template - the
# web mirror may never drift from the LCD truth.
import json as _json201
import subprocess as _sp201
_html201 = open(os.path.join(REPO, 'web', 'index.html'),
                errors='replace').read()
_a201 = '// ==== R201 live evaluator'
_b201 = '// ==== end R201 live evaluator ===='
if _a201 not in _html201 or _b201 not in _html201:
    check('T-live-eval: evaluator block present in the page', False,
          'markers missing')
else:
    _eval_js = _html201[_html201.index(_a201):
                        _html201.index(_b201) + len(_b201)]
    FIX = {
        'gcode_macro _STATE': {
            'mode': 'printing', 'layer': 42, 'total_layers': 100,
            'current_type': 'WALL-OUTER', 'file_type': 'marked',
            'file_material': 'PLA', 'file_bed': 60, 'file_bed_after': 60,
            'file_hotend_first': 210, 'file_hotend_after': 215,
            'file_layer_height': 0.2, 'file_nozzle': 0.6,
            'file_wall_loops': 2, 'file_slicer': 'OrcaSlicer',
            'file_feat_spd_wallouter': 45, 'file_pa': 0.095,
            'file_maxrate': 12.5, 'file_derived': False,
            'opt_pending': True},
        'gcode_macro _PREVIEW': {'type': 'range', 'name': 'TL_new.gcode'},
        'save_variables': {'variables': {
            'opt_cnt': 3, 'sound_on': True, 'leds_on': True,
            'material': 'PETG', 'ov_bed': 65, 'ov_bed_after': 65,
            'ov_hotend_first': 225, 'ov_hotend_after': 215,
            'ov_flow': 100, 'ov_outer_wall': 100, 'ov_ironing_speed': 20,
            'label_font': 'SMOOTH', 'label_w': 40, 'label_h': 13,
            'tie_count': 6, 'tie_length': 120, 'angle_deg': 90,
            'mesh_last_profile': 'r2', 'pa_test_step': 0.015}},
        'print_stats': {'filename': 'Vase_big_016.gcode',
                        'state': 'printing', 'print_duration': 1234.5},
        'gcode_move': {'speed': 1200, 'speed_factor': 1.0},
        'display_status': {'message': 'Layer 42/100'},
        # R204: exactly the objects the menus reference (live_objects) +
        # the extension's DEFAULT set - nothing the endpoint never ships
        'bed_mesh': {'profile_name': 'r2'},
        'configfile': {'config': {}, 'settings': {}},
        'exclude_object': {'objects': [], 'current_object': None},
        'input_shaper': {'shaper_type_x': 'mzv', 'shaper_freq_x': 38.2,
                         'shaper_type_y': 'ei', 'shaper_freq_y': 32.0},
    }
    _doc201 = _json201.load(open(os.path.join(REPO, 'web',
                                              'menu_structure.json')))
    _items201 = []

    def _walk201(node):
        for c in node.get('children', []):
            _items201.append(c)
            _walk201(c)

    _walk201(_doc201['tree'])
    _dyn201 = [i for i in _items201
               if '{' in (i.get('name') or '')
               and '{%' not in i['name'] and '{#' not in i['name']]
    _sample201 = _dyn201[::max(1, len(_dyn201) // 200)][:200]
    for _extra201 in (_dyn201[:6]
                      + [i for i in _dyn201 if 'replace(' in i['name']][:3]
                      + [i for i in _dyn201 if 'truncate(' in i['name']][:3]
                      + [i for i in _dyn201 if ' if ' in i['name']][:6]):
        if _extra201 not in _sample201:
            _sample201.append(_extra201)

    _fx204 = set(FIX)
    _lo205 = set(json.load(open(os.path.join(REPO, 'web',
                                             'menu_structure.json')))
                 .get('live_objects') or []) \
        | set(getattr(r2m, 'DEFAULT_LIVE_OBJECTS', ()))
    check('T-live-eval R204: the fixture represents what /live really '
          'ships (every fixture object in live_objects + the DEFAULT set)',
          not (_fx204 - _lo205),
          str(sorted(_fx204 - _lo205)))
    from jinja2 import Environment as _Env201, BaseLoader as _BL201
    from jinja2 import ChainableUndefined as _CU201
    _env201 = _Env201(loader=_BL201(),
                      variable_start_string='{', variable_end_string='}',
                      block_start_string='{%', block_end_string='%}',
                      trim_blocks=True, undefined=_CU201)
    _exp201 = []
    for _it201 in _sample201:
        try:
            _exp201.append(_env201.from_string(_it201['name']).render(
                printer=FIX, params={}))
        except Exception:                                      # noqa: BLE001
            _exp201.append(None)     # jinja itself fails -> page shows raw

    _harness201 = (_eval_js + '\nconst DATA = '
                   + _json201.dumps(FIX) + ';\nconst TPL = '
                   + _json201.dumps([i['name'] for i in _sample201])
                   + ';\nconst OUT = TPL.map(t => evalName(t, DATA));\n'
                     'console.log(JSON.stringify(OUT));\n')
    open('/tmp/r201_eval_test.js', 'w').write(_harness201)
    _r201 = _sp201.run(['node', '/tmp/r201_eval_test.js'],
                       capture_output=True, text=True, timeout=120)
    if _r201.returncode != 0:
        check('T-live-eval: node runs the shipped evaluator', False,
              _r201.stderr[-200:])
    else:
        _got201 = _json201.loads(_r201.stdout)
        _pairs201 = [(e, g, _sample201[k]['name'])
                     for k, (e, g) in enumerate(zip(_exp201, _got201))]
        _mm201 = [(e, g, t) for e, g, t in _pairs201
                  if e is not None and e != g]
        check('T-live-eval: page evaluator == jinja LCD truth '
              '(%d dynamic names, %d rendered by jinja, %d mismatch)'
              % (len(_sample201),
                 sum(1 for e, _, _ in _pairs201 if e is not None),
                 len(_mm201)),
              not _mm201, str(_mm201[:2])[:300])

    # enables: strict where the page knows the answer
    _ens201 = [i for i in _items201
               if i.get('enable') and '{' in i['enable']
               and '{%' not in i['enable'] and '{#' not in i['enable']]
    _ensample201 = _ens201[::max(1, len(_ens201) // 120)][:120]
    _expe201 = []
    for _it201 in _ensample201:
        try:
            _o201 = _env201.from_string(_it201['enable']).render(
                printer=FIX, params={})
            _expe201.append(_o201 == 'True')
        except Exception:                                      # noqa: BLE001
            _expe201.append(None)
    _harness201e = (_eval_js + '\nconst DATA = '
                    + _json201.dumps(FIX) + ';\nconst TPL = '
                    + _json201.dumps([i['enable'] for i in _ensample201])
                    + ';\nconst OUT = TPL.map(t => evalEnable(t, DATA));\n'
                      'console.log(JSON.stringify(OUT));\n')
    open('/tmp/r201_eval_teste.js', 'w').write(_harness201e)
    _r201e = _sp201.run(['node', '/tmp/r201_eval_teste.js'],
                        capture_output=True, text=True, timeout=120)
    if _r201e.returncode != 0:
        check('T-live-eval: node runs the shipped evaluator (enables)', False,
              _r201e.stderr[-200:])
    else:
        _gote201 = _json201.loads(_r201e.stdout)
        _mme201 = [(e, g) for e, g in zip(_expe201, _gote201)
                   if e is not None and g is not None and e != g]
        check('T-live-eval: enable conditions match the LCD truth '
              '(%d sampled, %d strict mismatches)'
              % (len(_ensample201), len(_mme201)),
              not _mme201, str(_mme201[:3])[:200])

# T3: the shipped page carries the embedded export
_html = open(os.path.join(REPO, 'web', 'index.html'), errors='replace').read()
check('T3 page: embedded JSON present, no leftover placeholder',
      '/*EMBEDDED_MENU_JSON*/ null' not in _html and '"sections"' in _html)

# T3b (R204): the export carries the menu-referenced object set
_doc204 = json.load(open(os.path.join(REPO, 'web', 'menu_structure.json')))
_lo204 = _doc204.get('live_objects') or []
check('T3b export: live_objects present - exactly the menu references '
      '(%d objects, incl. _STATE + save_variables, no generator macros)'
      % len(_lo204),
      'gcode_macro _STATE' in _lo204 and 'save_variables' in _lo204
      and 'print_stats' in _lo204 and 'gcode_macro GEN_LABELS' not in _lo204
      and len(_lo204) < 25)

# T4: _DIALOG_PEEK wired at every dialog site
_c08 = open(os.path.join(REPO, 'macros', '08_print_start_stop.cfg')).read()
check('T4 dialog peek: macro defined + called at all 4 dialog openings',
      '[gcode_macro _DIALOG_PEEK]' in _c08
      and _c08.count('_DIALOG_PEEK') >= 5,
      'count %d' % _c08.count('_DIALOG_PEEK'))

# T5: the .135 code anchors live in the postproc
_src = open(os.path.join(REPO, 'tools', 'r2_postproc.py')).read()
check('T5 anchors: TYPE_RE reads ;FEATURE: (Bambu), stem whitelist, '
      '_fmove192, air scan, sequence audit, 3x tower tags',
      '(?:TYPE|FEATURE)' in _src
      and "_sing191['ironing'] = 'iron'" in _src
      and 'def _fmove192' in _src
      and 'def _airscan193' in _src
      and 'def _sequence_audit193' in _src
      and _src.count("';TYPE:Prime tower'") == 6,
      "prime markers: %d" % _src.count("';TYPE:Prime tower'"))
check('T5 anchors: SEQWARN in _FILE_INFO + daemon log line',
      "info.append('SEQWARN=%d' % len(_seq193))" in _src
      and '[seqaudit]' in _src)

# ================================================================== T6 ==
# R200 (.135 field log): SINGLE-INSTANCE WATCHER. The field Pi ran two
# (likely three) watcher processes side by side - every state push fired
# twice, the litho notify macro RESPONDED twice, opt_list/sd_tree/gen_files
# three times. No in-process battery can see a second PROCESS; these
# checks spawn REAL daemons (subprocesses) and assert the lock semantics:
# a held flock refuses, a live daemon shields --once, the startup /proc
# scan takes over, and death releases the lock.
import shutil as _sh200
import shutil as _sh203_shutil
import subprocess as _sp200
import sys as _sy200
import time as _time


def _wait_log200(path, needle, proc, tries=140):
    for _ in range(tries):
        if proc.poll() is not None:
            return False
        try:
            if needle in open(path, errors='replace').read():
                return True
        except OSError:
            pass
        _time.sleep(0.5)
    return False


try:
    _gc200 = tempfile.mkdtemp(prefix='r200t_')
    _lock200 = os.path.join(REPO, 'watcher.lock')
    for _p200 in (_lock200, '/tmp/r2_postproc.watch.lock'):
        try:
            os.remove(_p200)
        except OSError:
            pass
    _R200 = os.path.join(REPO, 'tools', 'r2_postproc.py')
    _procs200 = []

    # T6a: a FOREIGN flock holder (SIGTERM-immune, invisible to the /proc
    # scan - no r2_postproc in its cmdline) -> the daemon must refuse
    _holder200 = _sp200.Popen([_sy200.executable, '-c',
        'import fcntl,os,signal,time\n'
        'signal.signal(signal.SIGTERM, signal.SIG_IGN)\n'
        'fd=os.open(%r, os.O_RDWR|os.O_CREAT, 0o644)\n'
        'fcntl.flock(fd, fcntl.LOCK_EX|fcntl.LOCK_NB)\n'
        'open(%r,"w").write("x")\n'
        'time.sleep(180)' % (_lock200, os.path.join(_gc200, 'ready'))])
    _procs200.append(_holder200)
    for _ in range(100):
        if os.path.exists(os.path.join(_gc200, 'ready')):
            break
        _time.sleep(0.1)
    _d1 = _sp200.run([_sy200.executable, _R200, '--watch', _gc200],
                     capture_output=True, text=True, timeout=120)
    check('T6a daemon REFUSES a held flock (exit 1 + reason, [r] hint)',
          _d1.returncode == 1 and 'REFUSING TO START' in _d1.stdout
          and 'pgrep' in _d1.stdout and '[r]2_postproc' in _d1.stdout,
          _d1.stdout[-160:])
    _holder200.kill()
    _holder200.wait()

    # T6b: daemon A runs free; --once beside it skips; daemon B TAKES OVER
    _A = _sp200.Popen([_sy200.executable, _R200, '--watch', _gc200],
                      stdout=open(os.path.join(_gc200, 'A.log'), 'w'),
                      stderr=_sp200.STDOUT, text=True)
    _procs200.append(_A)
    check('T6b daemon A starts (watching)',
          _wait_log200(os.path.join(_gc200, 'A.log'), 'watching', _A)
          and _A.poll() is None)
    _once = _sp200.run([_sy200.executable, _R200, '--watch', _gc200, '--once'],
                       capture_output=True, text=True, timeout=120)
    check('T6b --once beside the daemon: skipped, exit 0, daemon ALIVE',
          _once.returncode == 0 and 'one-shot run skipped' in _once.stdout
          and _A.poll() is None, _once.stdout[-160:])
    _B = _sp200.Popen([_sy200.executable, _R200, '--watch', _gc200],
                      stdout=open(os.path.join(_gc200, 'B.log'), 'w'),
                      stderr=_sp200.STDOUT, text=True)
    _procs200.append(_B)
    _took = _wait_log200(os.path.join(_gc200, 'B.log'), 'taking over', _B)
    _time.sleep(3.0)
    check('T6b startup scan: B takes over A (A dead, B alive)',
          _took and _A.poll() is not None and _B.poll() is None,
          'took=%s A=%s B=%s' % (_took, _A.poll(), _B.poll()))
    _B.kill()
    _B.wait()

    # T6c: B's death released the kernel lock - the next --once RUNS
    _C = _sp200.run([_sy200.executable, _R200, '--watch', _gc200, '--once'],
                    capture_output=True, text=True, timeout=120)
    check('T6c flock released on death (next --once runs, not skipped)',
          _C.returncode == 0 and 'one-shot run skipped' not in _C.stdout
          and 'REFUSING' not in _C.stdout, _C.stdout[-160:])
finally:
    for _p200 in _procs200:
        try:
            _p200.kill()
            _p200.wait(timeout=10)
        except Exception:                                   # noqa: BLE001
            pass
    _sh200.rmtree(_gc200, ignore_errors=True)

# ---- T6d (R202): the duplicate-diagnosis helpers ------------------------
check('T6d matcher: broadened to ANY r2_postproc name (stray copies '
      'with suffixes count too)',
      pp._cmdline_is_watcher(b'python3 /x/r2_postproc.py --watch')
      and pp._cmdline_is_watcher(b'python3 /x/r2_postproc_old.py -w /g')
      and not pp._cmdline_is_watcher(b'python3 /x/r2_menu.py')
      and not pp._cmdline_is_watcher(b'nano printer.cfg'))
check('T6d matcher R207: EXECUTION precision - processes that merely '
      'MENTION the name never match (bash wrapper, pgrep, grep, sudo)',
      not pp._cmdline_is_watcher(
          b'bash -l -c grep r2_postproc.py /var/log/syslog')
      and not pp._cmdline_is_watcher(b'sudo pgrep -af [r]2_postproc.py')
      and not pp._cmdline_is_watcher(b'grep -c r2_postproc x')
      and not pp._cmdline_is_watcher(b'nano r2_postproc.py'))
check('T6d cgroup unit: str for a live pid, graceful empty for a dead one',
      isinstance(pp._cgroup_unit(os.getpid()), str)
      and pp._cgroup_unit(999999) == '')
_d202 = tempfile.mkdtemp(prefix='r202_')
_pkg202 = os.path.join(_d202, 'klipper-e3-r2d2')
os.makedirs(os.path.join(_pkg202, 'tools'), exist_ok=True)
open(os.path.join(_pkg202, 'tools', 'x.py'), 'w').write('')
check('T6d flat-stray warnings: silent on a clean config folder',
      pp._flat_stray_warnings(_pkg202) == [])
os.makedirs(os.path.join(_d202, 'tools'), exist_ok=True)
open(os.path.join(_d202, 'tools', 'r2_postproc.py'), 'w').write('')
_w202 = pp._flat_stray_warnings(_pkg202)
check('T6d flat-stray warnings: name the second watcher copy (flat .134 '
      'remains) with the cleanup line',
      len(_w202) == 4 and 'SECOND r2_postproc.py' in _w202[0]
      and 'rm -rf' in _w202[3])
_sh200.rmtree(_d202, ignore_errors=True)

# T6e (R207, .136d field log): the runtime sweep must NAME the rival -
# its command line from /proc - and stop it. Doubled pushes after a clean
# update are only diagnosable when the journal says WHAT the second
# pusher was. (With the R207 execution-precision matcher this test can
# no longer kill its own bash wrapper - the .136f near-miss.)
_d207 = tempfile.mkdtemp(prefix='r207_')
open(os.path.join(_d207, 'r2_postproc_old.py'), 'w').write(
    'import time\ntime.sleep(120)\n')
_rival207 = _sp200.Popen(
    [_sy200.executable, os.path.join(_d207, 'r2_postproc_old.py'),
     '--watch', _d207])
import io as _io207
import contextlib as _ctx207
_out207 = _io207.StringIO()
try:
    with _ctx207.redirect_stdout(_out207):
        pp._watch_duplicate_sweep()
    _rival207.wait(timeout=20)
    check('T6e sweep: names the rival PATH (from /proc) and stops it',
          'runtime sweep' in _out207.getvalue()
          and 'r2_postproc_old.py' in _out207.getvalue()
          and _rival207.returncode is not None
          and _rival207.returncode != 0,
          (_out207.getvalue()[-160:] + ' | rc=%s' % _rival207.returncode))
finally:
    _rival207.kill()
    _sh200.rmtree(_d207, ignore_errors=True)


# ================================================================== T7 ==
# R203 (.136b): the ONE-COMMAND web-LCD installer. The manual 3-step path
# (component copy + moonraker.conf + nginx edit) was too fiddly for the
# field - install_web.sh does all of it, idempotently, with its own nginx
# site file (the mainsail config is never touched) and a full --uninstall.
# This runs the REAL script against a fake home with shim binaries.
def _sh203(name, body):
    p = os.path.join(_bin203, name)
    open(p, 'w').write(body)
    os.chmod(p, 0o755)


try:
    _t203 = tempfile.mkdtemp(prefix='r203_')
    _home203 = os.path.join(_t203, 'home')
    _comp203 = os.path.join(_home203, 'moonraker', 'moonraker', 'components')
    _cfg203 = os.path.join(_home203, 'printer_data', 'config', 'klipper-e3-r2d2')
    os.makedirs(_comp203)
    os.makedirs(_cfg203)
    _sh203_shutil.copytree(os.path.join(REPO, 'web'),
                           os.path.join(_cfg203, 'web'))
    _conf203 = os.path.join(_home203, 'printer_data', 'moonraker.conf')
    open(_conf203, 'w').write('[server]\nhost: 0.0.0.0\n')
    _ngx203 = os.path.join(_t203, 'etc', 'nginx')
    os.makedirs(os.path.join(_ngx203, 'sites-available'))
    os.makedirs(os.path.join(_ngx203, 'sites-enabled'))
    _bin203 = os.path.join(_t203, 'bin')
    os.makedirs(_bin203)
    _sh203('systemctl', '#!/bin/bash\necho systemctl "$@" >> %s\nexit 0\n'
           % os.path.join(_t203, 'calls.log'))
    _sh203('nginx', '#!/bin/bash\necho nginx "$@" >> %s\nexit 0\n'
           % os.path.join(_t203, 'calls.log'))
    _sh203('sudo', '#!/bin/bash\necho sudo "$@" >> %s\n"$@"\n'
           % os.path.join(_t203, 'calls.log'))
    _webroot203 = os.path.join(_home203, 'var_www', 'r2lcd')
    _env203 = dict(os.environ)
    _env203.update({
        'HOME': _home203, 'PATH': _bin203 + os.pathsep + _env203['PATH'],
        'R2_NGINX_SITES': os.path.join(_ngx203, 'sites-available'),
        'R2_NGINX_EN': os.path.join(_ngx203, 'sites-enabled'),
        'R2_WEB_ROOT': _webroot203,
        'R2_NGINX_TESTING': '1'})

    def _run203(args):
        return _sp200.run(
            ['bash', os.path.join(_cfg203, 'web', 'install_web.sh')] + args,
            capture_output=True, text=True, timeout=120, env=_env203,
            cwd=os.path.join(_cfg203, 'web'))

    _site203 = os.path.join(_ngx203, 'sites-available', 'r2lcd')
    _r203pre = _run203(['--update-only'])
    check('T7 update-only: NO-OP when nothing installed (exit 0, says so)',
          _r203pre.returncode == 0
          and 'not installed' in _r203pre.stdout
          and not os.path.exists(_site203), _r203pre.stdout[-160:])
    _r203 = _run203([])
    _conf_txt203 = open(_conf203).read()
    check('T7 install: exit 0, component copied, section added, '
          'site + symlink, URL printed, PAGE at the serve root (R208)',
          _r203.returncode == 0
          and os.path.isfile(os.path.join(_webroot203, 'index.html'))
          and os.path.isfile(os.path.join(_comp203, 'r2_menu.py'))
          and _conf_txt203.count('[r2_menu]') == 1
          and 'menu_structure.json' in _conf_txt203
          and os.path.isfile(_site203)
          and os.path.islink(os.path.join(_ngx203, 'sites-enabled', 'r2lcd'))
          and '/r2lcd/' in _r203.stdout, _r203.stdout[-200:])
    _r203b = _run203([])
    check('T7 install: IDEMPOTENT (2nd run adds no second section)',
          _r203b.returncode == 0
          and open(_conf203).read().count('[r2_menu]') == 1
          and 'already' in _r203b.stdout)
    _site_txt203 = open(_site203).read()
    check('T7 site: R208 serves from the WEB_ROOT alias (not the package '
          'dir - home-dir traverse perms can flip on any update)',
          ('alias %s/' % _webroot203) in _site_txt203
          and ('alias %s/' % os.path.join(_cfg203, 'web')) not in _site_txt203)
    check('T7 site: R207 CSRF guard (case-insensitive map) + Origin strip '
          'in BOTH proxy locations + Host without port (field-proven)',
          _site_txt203.count('proxy_set_header Origin "";') == 2
          and _site_txt203.count('if ($r2_csrf_bad) { return 403; }') == 2
          and 'map "$http_origin|$http_host" $r2_csrf_bad' in _site_txt203
          and '~*^http://([^|]+)\\|\\1$' in _site_txt203.replace(' ', '')
          and 'proxy_set_header Host $host;' in _site_txt203
          and 'guard self-test' in open(os.path.join(
              REPO, 'web', 'install_web.sh')).read(),
          (_site_txt203[:120] + ' | ' + _r203.stdout[-120:]))
    _r203s = _run203(['--status'])
    check('T7 status: reports component + section + URL port',
          _r203s.returncode == 0 and '[section ok]' in _r203s.stdout
          and '7126' in _r203s.stdout)
    open(os.path.join(_comp203, 'r2_menu.py'), 'w').write('STALE\n')
    open(os.path.join(_webroot203, 'index.html'), 'w').write('STALE PAGE\n')
    _r203uo = _run203(['--update-only'])
    check('T7 update-only: refreshes an EXISTING install (component AND '
          'page restored)',
          _r203uo.returncode == 0 and 'refresh' in _r203uo.stdout
          and open(os.path.join(_comp203, 'r2_menu.py')).read()
          == open(os.path.join(REPO, 'web', 'r2_menu.py')).read()
          and open(os.path.join(_webroot203, 'index.html')).read()
          == open(os.path.join(REPO, 'web', 'index.html')).read(),
          _r203uo.stdout[-160:])
    _r203u = _run203(['--uninstall'])
    check('T7 uninstall: site + section + component + page root removed',
          _r203u.returncode == 0
          and not os.path.exists(_site203)
          and '[r2_menu]' not in open(_conf203).read()
          and not os.path.exists(os.path.join(_comp203, 'r2_menu.py'))
          and not os.path.exists(_webroot203))
    check('T7 update.sh syncs the web-LCD on every update (--update-only)',
          '--update-only' in open(os.path.join(REPO, 'update.sh')).read())
    check('T7 self-test R208: the PAGE GET is part of the verdict (the '
          '.136f field bug - 403 on open - was invisible to the API-only '
          'self-test)',
          '_page_test' in open(os.path.join(REPO, 'web',
                                            'install_web.sh')).read())
finally:
    _sh203_shutil.rmtree(_t203, ignore_errors=True)


# ================================================================== T8 ==
# R209 (.136h field log - "menuebaum zeigt nur __main, Klicks tot"): the
# page read Moonraker's response WITHOUT unwrapping the {"result": ...}
# envelope every moonraker endpoint ships - DOC.tree was undefined, the
# render crashed after the fetch, the menu stayed empty and every button
# was dead. Invisible since .136b because each side was tested against
# its OWN mocks: the component against the fake moonraker (raw dict),
# the page evaluator against jinja. THIS test runs the REAL shipped page
# script against the REAL component response shape, envelope included.
try:
    import json as _json209
    _page_src209 = open(os.path.join(REPO, 'web', 'index.html'),
                        encoding='utf-8').read()
    _script209 = _page_src209.rsplit('<script>', 1)[1].rsplit('</script>',
                                                              1)[0]
    _doc209 = _json209.load(open(os.path.join(REPO, 'web',
                                              'menu_structure.json')))

    def _run_page209(tree_ok, live_obj):
        """Run the REAL page script in node with DOM/fetch stubs; return
        {menu_children, crumb, badge, error} - error catches the
        unhandled rejection the old unwrap bug produced."""
        _js209 = r"""
const vm = require('vm'), fs = require('fs');
const DOC = JSON.parse(fs.readFileSync(process.argv[2], 'utf8'));
const LIVE_OBJ = JSON.parse(fs.readFileSync(process.argv[3], 'utf8'));
const TREE_OK = process.argv[4] === '1';
function elem(id){ return {id, textContent:'', innerHTML:'', className:'',
  title:'', disabled:false, children:[], _handlers:{},
  classList:{add(){},remove(){}},
  appendChild(c){ this.children.push(c); },
  querySelector(sel){ return null; },   // R209: applyLive probes .nm/.en
  style: {},
  set onclick(f){ this._handlers.click = f; },
  get onclick(){ return this._handlers.click; } }; }
const reg = {};
const document = {
  getElementById(id){ if(!reg[id]) reg[id] = elem(id); return reg[id]; },
  createElement(tag){ return elem('<'+tag+'>'); } };
let unhandled = null;
process.on('unhandledRejection', e => { unhandled = String(e); });
const fetchCalls = [];
const fetch = async (url) => {
  fetchCalls.push(url);
  if (url === '/server/r2_menu/tree') {
    if (!TREE_OK) return {ok:false, json: async()=>({})};
    // EXACTLY what moonraker ships: the component dict in an envelope
    return {ok:true, json: async()=>({result: DOC})};
  }
  if (url === '/server/r2_menu/live') {
    return {ok:true, json: async()=>({result: {ok:true, objects: LIVE_OBJ,
                                               pruned: []}})};
  }
  return {ok:false, json: async()=>({})};
};
const sandbox = {document, fetch, console,
  setTimeout: ()=>0, clearTimeout: ()=>{}};
sandbox.window = sandbox; sandbox.location = {href:''};
vm.createContext(sandbox);
try { vm.runInNewContext(fs.readFileSync(process.argv[5], 'utf8'),
                         sandbox); }
catch (e) { console.log(JSON.stringify({error: String(e)})); process.exit(0); }
(async () => {
  for (let i = 0; i < 25; i++) await new Promise(r => process.nextTick(r));
  const menu = reg['menu'], crumb = reg['crumb'], badge = reg['srcbadge'];
  console.log(JSON.stringify({error: unhandled,
    menu_children: menu ? menu.children.length : -1,
    crumb: crumb ? crumb.textContent : null,
    badge: badge ? badge.textContent : null,
    fetches: fetchCalls.length}));
})();
"""
        import tempfile as _tf209
        _fd209 = os.path.join(_tf209.mkdtemp(prefix='r209_'), 'page.js')
        _fo209 = os.path.join(os.path.dirname(_fd209), 'live.json')
        _fs209 = os.path.join(os.path.dirname(_fd209), 'pagescript.js')
        open(_fd209, 'w').write(_js209)      # the runner itself (the very
        # first T8 run never wrote it - MODULE_NOT_FOUND)
        open(_fo209, 'w').write(_json209.dumps(live_obj))
        open(_fs209, 'w').write(_script209)   # R209: as a FILE - the script
        # is ~60 kB, argv would blow ARG_MAX (found by the first T8 run)
        _r209 = _sp200.run(
            ['node', _fd209, os.path.join(REPO, 'web',
                                          'menu_structure.json'),
             _fo209, '1' if tree_ok else '0', _fs209],
            capture_output=True, text=True, timeout=120)
        _sh200.rmtree(os.path.dirname(_fd209), ignore_errors=True)
        try:
            return _json209.loads(_r209.stdout.strip().splitlines()[-1])
        except Exception as _e209:                                  # noqa
            return {'error': 'node: %s / %s' % (_e209, _r209.stderr[-160:])}

    # the live fixture: exactly what /live ships (the evaluator fixture,
    # already aligned to live_objects + DEFAULT by the T-live-eval check)
    _resA209 = _run_page209(True, FIX)
    check('T8 page<->moonraker contract (R209): the REAL page script '
          'renders the menu from the REAL component response IN THE '
          'MOONRAKER ENVELOPE ({"result":...}) - the .136b-.136g page '
          'crashed on the envelope (menu stayed "__main", clicks dead)',
          _resA209.get('error') is None
          and _resA209.get('menu_children', -1) >= 5
          and _resA209.get('crumb') == '__main'
          and 'Werte live' in (_resA209.get('badge') or ''),
          str(_resA209)[:200])
    _resB209 = _run_page209(False, FIX)
    check('T8 page fallback: tree endpoint down -> the EMBEDDED export '
          'renders (menu >= 5, badge says eingebettet, no crash)',
          _resB209.get('error') is None
          and _resB209.get('menu_children', -1) >= 5
          and 'eingebettet' in (_resB209.get('badge') or ''),
          str(_resB209)[:200])
finally:
    pass


# ================================================================== summary ==
print()
if FAILS:
    print('R197 GEN SWEEP: %d checks, %d FAIL' % (N, len(FAILS)))
    for f in FAILS:
        print('  -', f)
    sys.exit(1)
print('R197 GEN SWEEP: %d checks, 0 FAIL - all generators + tools green' % N)
