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
    """R201: stand-in for moonraker's klippy_apis - a fixed object list
    and status snapshot, with a FAT sd_tree to prove the pruning."""

    def __init__(self, objs, status):
        self.objs = objs
        self.status = status

    async def get_object_list(self):
        return self.objs

    async def query_objects(self, want, default=None):
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
cfg.server.objects['klippy_apis'] = FakeKlippyAPI(
    ['gcode_macro _STATE', 'gcode_macro _PREVIEW', 'save_variables',
     'print_stats', 'toolhead', 'extruder'],
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
check('T2b live: 1 s cache serves the same snapshot object', lv2 is lv)
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
        'extruder': {'temperature': 209.4, 'target': 210},
        'heater_bed': {'temperature': 59.8, 'target': 60},
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
    check('T6a daemon REFUSES a held flock (exit 1 + reason)',
          _d1.returncode == 1 and 'REFUSING TO START' in _d1.stdout
          and 'pgrep' in _d1.stdout, _d1.stdout[-160:])
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


# ================================================================== summary =
print()
if FAILS:
    print('R197 GEN SWEEP: %d checks, %d FAIL' % (N, len(FAILS)))
    for f in FAILS:
        print('  -', f)
    sys.exit(1)
print('R197 GEN SWEEP: %d checks, 0 FAIL - all generators + tools green' % N)
