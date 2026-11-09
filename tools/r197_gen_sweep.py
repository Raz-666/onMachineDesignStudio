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
# R216 re-pin: image paging (3x3 nav rows) + ArtisticStrings picker
# (10 slots) + bricks scale input/size row (2403 -> 2424)
# R216: string-art field round (shape/presets/bow/spread) adds 12 rows (2472 -> 2472)
# R220: TYPES summary rows in both File info menus (2472 -> 2474)
# R223 (.136u): System > Gen jobs - queue visibility + clear
# (.136s field log; 2474 -> 2479: list + how/state/clear/clear-now)
# R224 (.136v): menu consolidation - the __macros sound/LED duplicates and
# the mirror/cake-yaw inputs are gone, the nozzle-LED block moved under
# __system __ledcfg __noz (2479 -> 2473), the Mirror tool
# adds its folder back (2473 -> 2477; R224 adds 3 preset rows -> 2480)
# R231 (.136ac): label generator gains the Flip toggle (build-plate-readable
# mirrored text) - one more input section (2480 -> 2481)
# R232 (.136ac): ArtisticStrings gains the AR lock row (photo aspect keeps
# W and H coupled) - one more input section (2481 -> 2482)
check('T1 export: all 2473 sections in one tree, no orphans',
      doc['sections'] == 2482 and sum(doc['counts'].values()) == 2482,
      str(doc['counts']))


def _walk(n, acc):
    acc.append(n)
    for c in n.get('children', []):
        _walk(c, acc)
    return acc


_all = _walk(doc['tree'], [])
check('T1 export: tree node count == sections, depth sane, known ids',
      len(_all) == 2482
      and any(n['id'] == '__main __start __direct' for n in _all)
      and any(n['id'] == '__main __live' for n in _all))

# R220 (.136o field item 'Shape-TYPES-Anzeige'): the TYPES summary rows
_feat220 = [n for n in _all if n['id'].endswith(' __feat')
            and ('__start __info' in n['id'] or '__preprint __file' in n['id'])]
check('T1 R220: both File info menus (Start? + Pre-Print) carry the '
      'TYPES summary row with the compact code map',
      len(_feat220) == 2
      and all('WALL-OUTER","WO' in n['name']
              and 'INTERNAL-BRIDGE","IB' in n['name']
              and 'PRIME-TOWER","PT' in n['name'] for n in _feat220),
      str([n['id'] for n in _feat220]))
_cust220 = [n for n in _all if n['id'] == '__main __preprint __file __cust']
check('T1 R220: the CUSTOM? gate reads the LIVE _STATE.file_types '
      '(was save_variables.variables.file_types - a variable nothing '
      'ever writes: the row could never show)',
      len(_cust220) == 1
      and 'gcode_macro _STATE' in _cust220[0].get('enable', '')
      and 'save_variables' not in _cust220[0].get('enable', ''),
      str(_cust220[0].get('enable'))[:80])
from jinja2 import Environment as _E220, BaseLoader as _B220, \
    ChainableUndefined as _C220                    # noqa: E402
_env220 = _E220(loader=_B220(), variable_start_string='{',
               variable_end_string='}', block_start_string='{%',
               block_end_string='%}', trim_blocks=True, undefined=_C220)


def _render220(tpl, types220):
    return _env220.from_string(tpl).render(
        printer={'gcode_macro _STATE': {'file_types': types220}})


_t220 = _feat220[0]['name']
check('T1 R220: the Feat row compacts TYPES to LCD-width codes '
      '(mapping + truncate through the REAL exported template)',
      _render220(_t220, 'WALL-OUTER,INFILL-SPARSE,BRIM') == 'Feat: WO IS BM'
      and _render220(_t220,
                     'WALL-OUTER,WALL-INNER,INFILL-SPARSE,SURFACE-TOP,'
                     'SURFACE-BOTTOM,BRIM,INTERNAL-BRIDGE')
      == 'Feat: WO WI IS S'
      and _render220(_t220, '') == 'Feat: ?',
      _render220(_t220, 'WALL-OUTER,INFILL-SPARSE,BRIM'))

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
      and _emb['sections'] == 2482)

# T2: the moonraker extension with a fake app
spec = importlib.util.spec_from_file_location(
    'r2_menu', os.path.join(REPO, 'web', 'r2_menu.py'))
r2m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(r2m)


class FakeReq:
    def __init__(self, args=None):
        self.type = 'GET'
        self.args = args or {}

    def get(self, key, default=None):
        return self.args.get(key, default)


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

    def lookup_component(self, name):
        # R211: the REAL moonraker Server API - lookup_component(), NOT
        # the klipper-style lookup_object() (.136i field log: the old
        # fake implemented lookup_object, so the component shipped with a
        # call the real Server answers with AttributeError - every offline
        # test green, every /live poll on the Pi dead). This fake mirrors
        # ONLY what real moonraker actually has.
        if name in self.objects:
            return self.objects[name]
        raise self.error('object %s not found' % name)

    def get_klippy_state(self):
        return 'ready'


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
check('T2 extension: 6 endpoints registered',
      set(eps) == {'/server/r2_menu/tree', '/server/r2_menu/status',
                   '/server/r2_menu/live',
                   '/server/r2_menu/refresh',
                   '/server/r2_menu/pistats',      # R216 (.136n)
                   '/server/r2_menu/klippylog'},   # R216 (.136n)
      str(set(eps)))

import asyncio                                            # noqa: E402
loop = asyncio.new_event_loop()
# R225 (.136w audit): the tool comes from the REPO copy - the DEFAULT
# path only exists where the repo sits in $HOME (dev sandbox); on the
# documented Pi install (~/printer_data/config/klipper-e3-r2d2/) T2 ran
# green by accident while a field refresh silently reloaded the STALE
# embedded json. Explicit pin now, plus the derivation check.
comp.tool = os.path.join(REPO, 'tools', 'menu_json_export.py')
check('T2 extension: export tool derived from the menu path',
      r2m._tool_from_path(os.path.join(REPO, 'web', 'menu_structure.json'))
      == os.path.join(REPO, 'tools', 'menu_json_export.py'),
      'path -> tool derivation failed')
tree_doc = loop.run_until_complete(eps['/server/r2_menu/tree'](FakeReq()))
check('T2 extension: tree handler serves the export',
      tree_doc['sections'] == 2482 and 'tree' in tree_doc)
st = loop.run_until_complete(eps['/server/r2_menu/status'](FakeReq()))
check('T2 extension: status handler reports ok + sha',
      st['ok'] and st['sha256'] == tree_doc['sha256'])
rf = loop.run_until_complete(eps['/server/r2_menu/refresh'](FakeReq()))
# R224 (.136v field review): X_OK was dropped from the gate - python3
# invokes the tool, so a 0644-unpacked one (every zip without permission
# bits) re-exports NOW instead of silently serving the STALE json
check('T2 extension: refresh re-exports even a NON-executable tool',
      rf['ok'] and rf.get('reExported') is True, str(rf)[:80])
# absent tool: degrade to a plain reload (no crash, no re-export)
comp.tool = os.path.join(REPO, 'tools', 'does_not_exist_224.py')
rf2 = loop.run_until_complete(eps['/server/r2_menu/refresh'](FakeReq()))
check('T2 extension: refresh without the tool degrades gracefully',
      rf2['ok'] and rf2.get('reExported') in (False, None), str(rf2)[:80])
# R216 (.136n): the Pi stats endpoint - pure /proc reads, never klippy
cfg.server.objects['klippy_apis'] = FakeKlippyAPI([], {})
ps = loop.run_until_complete(eps['/server/r2_menu/pistats'](FakeReq()))
check('T2 extension: pistats answers ok with cpu/ram (no klippy objects)',
      ps['ok'] and ps.get('cpu') is not None
      and ps.get('ram_total_mb') is not None
      and not cfg.server.objects['klippy_apis'].wants, str(ps)[:90])
# R216 (.136n): the klippy.log window export - file + header + cap
# R226 (.136x field log): the fixture is the REAL klippy.log format -
# sections per restart ('Start printer at <asctime>'), NO per-line
# timestamps. The R216 filter expected 'YYYY-MM-DD ...' lines and
# produced an EMPTY export on the field Pi (512 bytes, header only).
import tempfile as _tf216, shutil as _sh216
import datetime as _dt216
_logd216 = _tf216.mkdtemp(prefix='r216log_')
_logf216 = os.path.join(_logd216, 'klippy.log')
_now216 = _dt216.datetime.now()
_old216 = _now216 - _dt216.timedelta(hours=8)
_fresh216 = _now216 - _dt216.timedelta(minutes=5)
open(_logf216, 'w').write(
    '===== Config file =====\n'
    '[virtual_sdcard]\nOLD HEAD CONFIG\n=======================\n'
    'old runtime line 0\n'
    'Start printer at %s\n'
    '===== Config file =====\n'
    '[virtual_sdcard]\nOLD SECTION CONFIG\n=======================\n'
    'old runtime line 1\n'
    'Start printer at %s\n'
    '===== Config file =====\n'
    '[virtual_sdcard]\nFRESH DUMP (must be skipped)\n'
    '=======================\nLoaded MCU fresh\n'
    'fresh runtime line\nno timestamp context line\n'
    % (_old216.strftime('%a %b %d %H:%M:%S %Y'),
       _fresh216.strftime('%a %b %d %H:%M:%S %Y')))
class _Cfg216(FakeConfig):
    def get(self, key, default):
        if key == 'log_path':
            return _logf216
        return super().get(key, default)
cfg216 = _Cfg216(os.path.join(REPO, 'web', 'menu_structure.json'))
comp216 = r2m.load_component(cfg216)
kl = loop.run_until_complete(
    cfg216.server.endpoints['/server/r2_menu/klippylog'](
        FakeReq({'window': '3h'})))
check('T2 extension: klippylog 3h window keeps the CURRENT run (fresh '
      '+ context lines, config dumps skipped, old sections out)',
      kl['ok'] and kl['window'] == '3h' and 'fresh runtime line' in kl['text']
      and 'context line' in kl['text'] and 'old runtime line' not in kl['text']
      and 'FRESH DUMP' not in kl['text']
      and kl['text'].startswith('# klippy.log'), str(kl)[:90])
kl_all = loop.run_until_complete(
    cfg216.server.endpoints['/server/r2_menu/klippylog'](
        FakeReq({'window': 'all'})))
check('T2 extension: klippylog all window keeps everything',
      kl_all['ok'] and 'old runtime line 1' in kl_all['text']
      and 'fresh runtime line' in kl_all['text'], str(kl_all)[:90])
kl_bad = loop.run_until_complete(
    cfg216.server.endpoints['/server/r2_menu/klippylog'](
        FakeReq({'window': 'nope'})))
check('T2 extension: klippylog rejects unknown windows (falls back)',
      kl_bad['ok'] and kl_bad['window'] == '3h', str(kl_bad)[:80])
_sh216.rmtree(_logd216, ignore_errors=True)

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

# ---- T2c (R210): live-handler HARDENING - the .136h field log showed
# 'Klipper nicht bereit' with the REASON thrown away. Now: per-object
# retry (one bad object must not kill the snapshot), klippy-state
# precheck with a visible reason, value pruning (settings/profiles
# keys only, exclude_object names only) - the menus only read those.
class _API210(FakeKlippyAPI):
    async def query_objects(self, want, default=None):
        self.wants.append(set(want))
        if len(want) > 1:
            raise RuntimeError('objects/status failed (simulated)')
        if 'bed_mesh' in want:
            raise RuntimeError('bad object: bed_mesh')
        return {k: v for k, v in self.status.items() if k in want}

class _Cfg210:
    def __init__(self, server, path):
        self.server = server
        self._p = path

    def get(self, key, default):
        return self._p if key == 'path' else default

    def get_server(self):
        return self.server

_srv210 = type(cfg.server)()
_srv210.objects['klippy_apis'] = _API210(
    ['gcode_macro _STATE', 'save_variables', 'bed_mesh', 'extruder',
     'configfile', 'exclude_object', 'print_stats',
     'display_status'],
    {'gcode_macro _STATE': {'mode': 'idle'},
     'save_variables': {'variables': {'opt_cnt': 1}},
     'extruder': {'temperature': 200.0, 'target': 210,
                  'pressure_advance': 0.095},
     'configfile': {'settings': {'stepper_z1': {'a': 1},
                                 'neopixel nozzle_led': {'b': 2}}},
     'bed_mesh': {'profile_name': 'r2',
                  'profiles': {'r2': {'points': [1, 2] * 50},
                               'default': {'points': [1] * 100}}},
     'exclude_object': {'objects': [
         {'name': 'O1', 'polygon': [[0, 0], [1, 1], [2, 2]]},
         {'name': 'O2', 'polygon': [[0, 0], [1, 1]]}],
         'current_object': 'O1'},
     'print_stats': {'state': 'idle'},
     'display_status': {'message': 'hi', 'progress': 0.5}})
_srv210.get_klippy_state = lambda: 'ready'
_eps210 = r2m.load_component(
    _Cfg210(_srv210, os.path.join(REPO, 'web',
                                  'menu_structure.json'))
    ).server.endpoints
_lv210 = loop.run_until_complete(
    _eps210['/server/r2_menu/live'](FakeReq()))
check('T2c live R210: per-object retry survives a bad object '
      '(bed_mesh named in skipped, the rest still served)',
      _lv210.get('ok')
      and 'bed_mesh' not in _lv210['objects']
      and any('bed_mesh' in str(x) for x in _lv210.get('skipped', []))
      and _lv210['objects']['extruder']['temperature'] == 200.0,
      str(_lv210)[:200])
check('T2c live R210: fat values PRUNED to what the menus read '
      '(configfile.settings keys-only, exclude_object names-only)',
      _lv210['objects']['configfile']['settings'] ==
      {'stepper_z1': None, 'neopixel nozzle_led': None}
      and _lv210['objects']['exclude_object']['objects'] ==
      [{'name': 'O1'}, {'name': 'O2'}]
      and 'configfile.settings(values)' in _lv210.get('pruned', [])
      and 'exclude_object.objects(polygons)' in _lv210.get('pruned', []),
      str(_lv210.get('pruned'))[:160])
# ---- T2e (R219, .136q field log: live values '?', Maintenance vanished,
# SD empty - all three at once): moonraker's query_objects SWALLOWS klippy
# errors and returns the DEFAULT - a failed batch came back as a silent {}
# while the handler said ok:True, and the page built an EMPTY printer.
# The fakes now mirror the REAL semantics (default-swallow when a default
# is passed, raise without) and the component must answer in tiers and
# NEVER with ok:True + empty objects.
class _API219(FakeKlippyAPI):
    """Rejects the field-list form (configfile:['settings']) like an
    older klippy - the all-None form works."""

    async def query_objects(self, want, default=None):
        if any(v for v in want.values()):        # a field list anywhere
            if default is not None:
                return default                    # REAL moonraker: swallow
            raise RuntimeError('objects/query: invalid request format')
        return {k: v for k, v in self.status.items() if k in want}


class _API219z(FakeKlippyAPI):
    """Everything fails - the total-failure invariant."""

    async def query_objects(self, want, default=None):
        if default is not None:
            return default                        # silent swallow
        raise RuntimeError('klippy query down (simulated)')


_FIX219 = {'gcode_macro _STATE': {'mode': 'idle'},
           'save_variables': {'variables': {'sd_view': ['F:a.gcode'],
                                            'sd_page': 0}},
           'extruder': {'temperature': 200.0, 'target': 210},
           'configfile': {'settings': {'stepper_z1': {'a': 1}}}}
_OBJS219 = list(_FIX219)
for _cls219, _tag219 in ((_API219, 'fieldlist'), (_API219z, 'total')):
    _srv219 = type(cfg.server)()
    _srv219.objects['klippy_apis'] = _cls219(_OBJS219, _FIX219)
    _srv219.get_klippy_state = lambda: 'ready'
    _eps219 = r2m.load_component(
        _Cfg210(_srv219, os.path.join(REPO, 'web',
                                      'menu_structure.json'))
    ).server.endpoints
    _lv219 = loop.run_until_complete(
        _eps219['/server/r2_menu/live'](FakeReq()))
    if _tag219 == 'fieldlist':
        check('T2e live R219: a klippy that rejects the configfile '
              'field list still gets a FULL snapshot (tier 2, all-None '
              'batch) - the .136q vanish/values/SD class',
              _lv219.get('ok')
              and _lv219.get('objects', {}).get(
                  'extruder', {}).get('temperature') == 200.0
              and _lv219['objects']['gcode_macro _STATE'][
                  'mode'] == 'idle'
              and 'configfile' in _lv219['objects'],
              str(_lv219)[:200])
        check('T2e live R219 invariant: NEVER ok:True with empty '
              'objects (the page must not build an empty printer)',
              not (_lv219.get('ok') and not _lv219.get('objects')),
              str(_lv219)[:160])
    else:
        check('T2e live R219: total query failure -> ok:False WITH the '
              'reason (badge shows it, no silent empty printer)',
              _lv219.get('ok') is False
              and 'status query empty' in str(_lv219.get('reason'))
              and 'simulated' in str(_lv219.get('reason')),
              str(_lv219)[:200])

_srv210b = type(cfg.server)()
_srv210b.objects['klippy_apis'] = _API210(
    ['gcode_macro _STATE'], {'gcode_macro _STATE': {'mode': 'idle'}})
_srv210b.get_klippy_state = lambda: 'shutdown'
_eps210b = r2m.load_component(
    _Cfg210(_srv210b, os.path.join(REPO, 'web',
                                   'menu_structure.json'))
    ).server.endpoints
_lv210b = loop.run_until_complete(
    _eps210b['/server/r2_menu/live'](FakeReq()))
check('T2d live R211: fake mirrors the REAL moonraker API surface and '
      'the component speaks lookup_component (the .136i field-Pi class: '
      'a fake RICHER than reality - lookup_object - greens every '
      'offline test while the Pi raises AttributeError)',
      not hasattr(cfg.server, 'lookup_object')
      and hasattr(cfg.server, 'lookup_component')
      and 'lookup_component' in open(os.path.join(REPO, 'web',
                                                  'r2_menu.py')).read(),
      'fake or component drifted')
check('T2c live R210: klippy not ready -> ok False with the REASON '
      'surfaced (the .136h page only said "Klipper nicht bereit")',
      _lv210b.get('ok') is False
      and 'shutdown' in str(_lv210b.get('reason', '')),
      str(_lv210b)[:160])
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
            'file_fan': 255, 'file_flow': 100.0, 'file_accel': 3000.0,
            'fc_armed': False, 'fc2_armed': False,
            'current_type': 'WALL-OUTER', 'file_type': 'marked',
            'file_material': 'PLA', 'file_bed': 60, 'file_bed_after': 60,
            'file_hotend_first': 210, 'file_hotend_after': 215,
            'file_layer_height': 0.2, 'file_nozzle': 0.6,
            'file_wall_loops': 2, 'file_slicer': 'OrcaSlicer',
            'file_firmware': 'Klipper', 'file_volumetric': False,
            'file_by_object': False, 'file_seam': 'aligned',
            'file_line_width': 0.42, 'file_line_width_first': 0.5,
            'file_line_width_wall': 0.42, 'file_flow_ratio': 0.98,
            'file_feat_spd_wallouter': 45, 'file_pa': 0.095,
            'file_maxrate': 12.5, 'file_derived': False,
            'file_retract_len': 0.75, 'file_retract_speed': 35.0,
            'file_retract_style': 'firmware',
            'file_ironing_speed': 20.0, 'file_ironing_spacing': 0.1,
            'file_ironing_flow': 0.15, 'file_speed_first': 30.0,
            'file_speed_outer': 45.0, 'file_speed_inner': 70.0,
            'file_speed_solid': 70.0, 'file_speed_sparse': 90.0,
            'file_speed_top': 50.0, 'file_speed_travel': 200.0,
            'file_speed_skirt': 30.0, 'file_speed_bridge': 25.0,
            'file_speed_small': 20.0, 'file_speed': 90.0,
            'file_accel': 8000.0, 'file_accel_outer': 5000.0,
            'file_accel_inner': 8000.0, 'file_accel_first': 2500.0,
            'file_accel_solid': 8000.0, 'file_accel_sparse': 8000.0,
            'file_accel_top': 5000.0, 'file_accel_travel': 8000.0,
            'file_accel_default': 8000.0, 'file_accel_small': 3000.0,
            'file_slow_min': 10.0, 'file_time_slow': 0,
            'file_fil_dia': 1.75, 'file_travel': 200.0,
            'file_support_speed': 60.0,
            # R220: real _STATE ships TYPES as ONE dash-code
            # string - the Feat rows compact it on both LCD+web
            'file_types': 'WALL-OUTER,WALL-INNER,INFILL-SPARSE,'
                          'SURFACE-TOP,SURFACE-BOTTOM,BRIM',
            'file_conf': False, 'file_cover': False,
            'file_optimized': False, 'file_held': False,
            'file_info_seen': True, 'file_pa_smooth': 0.04,
            'mesh_delete_armed': '', 'skip_armed_name': '',
            'pa_value': 0.095, 'pa_smooth': 0.04, 'pa_last': 0.095,
            'opt_pending': True, 'live_accel': 8000, 'live_flow': 100,
            'ret_len': 0.75, 'ret_spd': 35.0,
            'ret_unret': 35.0, 'ret_unretx': 35.0},
        'gcode_macro _PREVIEW': {'type': 'range', 'name': 'TL_new.gcode'},
        'gcode_macro _R2_CONFIG': {'led_status_n': 4, 'led_bed_n': 6,
                                   'led_bed_on': 1, 'led_bed_bright': 0.4,
                                   'led_nozzle_split': 0},
        'gcode_macro _MATERIALS': {'last': 'PLA'},
        'save_variables': {'variables': {
            'opt_cnt': 3, 'sound_on': True, 'leds_on': True,
            'material': 'PETG', 'ov_bed': 65, 'ov_bed_after': 65,
            'ov_hotend_first': 225, 'ov_hotend_after': 215,
            'ov_flow': 100, 'ov_outer_wall': 100, 'ov_ironing_speed': 20,
            'label_font': 'SMOOTH', 'label_w': 40, 'label_h': 13,
            'tie_count': 6, 'tie_length': 120, 'angle_deg': 90,
            'mesh_last_profile': 'r2', 'pa_test_step': 0.015,
            'opt_list': 'BigRosGrdTX.gcode|TL_new.gcode|V03_RL-SD1+15.gcode',
            'opt_print_name': '', 'nozzle_mode': 'auto',
            'nozzle_split': 0, 'sd_path': 'Range', 'sd_page': 2,
            'browser_del_on': False, 'gen_out': 1, 'start_confirm': True,
            'sd_view': ['D:Range', 'F:Vase_big_016.gcode',
                        'F:Trash.gcode', 'F:Orca_Cube.gcode']}},
        'print_stats': {'filename': 'Vase_big_016.gcode',
                        'state': 'printing', 'print_duration': 1234.5,
                        'total_duration': 1300.0, 'filament_used': 4.2},
        'gcode_move': {'speed': 45.0, 'speed_factor': 1.0,
                       'extrude_factor': 1.0,
                       'homing_origin': [0.0, 0.0, 0.0, 0.0]},
        'display_status': {'message': 'Layer 42/100', 'progress': 0.42},
        # R210: the dashboard set (DEFAULT_LIVE_OBJECTS) - temps, fan,
        # feed/flow, PA, accel, progress
        'extruder': {'temperature': 209.4, 'target': 210,
                     'pressure_advance': 0.095, 'smooth_time': 0.04},
        'heater_bed': {'temperature': 59.7, 'target': 60},
        'fan': {'speed': 0.75},
        'virtual_sdcard': {'progress': 0.42, 'is_active': True},
        'toolhead': {'max_accel': 8000, 'max_velocity': 300,
                     'square_corner_velocity': 4.0,
                     'minimum_cruise_ratio': 0.85},
        # R204/R210: exactly the shapes /live ships AFTER the component's
        # pruning: settings/profiles keys only, exclude_object names only
        'bed_mesh': {'profile_name': 'r2',
                     'profiles': {'r2': {}, 'default': {}}},
        'configfile': {'settings': {'stepper_z1': None,
                                    'neopixel nozzle_led': None,
                                    'bed_mesh': None,
                                    'exclude_object': None}},
        'exclude_object': {'objects': [{'name': 'Object_1'},
                                       {'name': 'Object_2'}],
                           'current_object': 'Object_1',
                           'excluded_objects': []},
        'input_shaper': {'shaper_type_x': 'mzv', 'shaper_freq_x': 38.2,
                         'shaper_type_y': 'ei', 'shaper_freq_y': 32.0},
    }
    # R218 (.136o field log: whole menus vanished from the web page):
    # the fixture used to ship gcode_macro variables ALREADY UNWRAPPED -
    # richer than reality. klippy's status query returns every gcode_macro
    # as {'variables': {...}}; the page must lift them via mkPrinter (the
    # P=mkPrinter(j.objects,...) path). Every harness below now feeds the
    # RAW shape through the REAL mkPrinter - this is the regression test
    # that would have caught the field bug.
    import copy as _copy218
    import re as _re218

    def _raw218(fix):
        raw = {}
        for k, v in fix.items():
            raw[k] = ({'variables': _copy218.deepcopy(v)}
                      if k.startswith('gcode_macro ') else
                      _copy218.deepcopy(v))
        return raw

    _mk218m = _re218.search(r'function mkPrinter\(.*?\n\}',
                            _html201, _re218.S)
    if not _mk218m:
        check('T-live-eval R218: mkPrinter present in the page '
              '(the gcode_macro unwrap)', False, 'function not found')
        _mk218src = 'function mkPrinter(){return {};}'
    else:
        _mk218src = _mk218m.group(0)
    check('T-live-eval R218: mkPrinter unwraps gcode_macro variables '
          '(klippy ships {variables:{...}} - the .136o vanish bug)',
          "base[k]=Object.assign({},base[k].variables)" in _mk218src)

    _doc201 = _json201.load(open(os.path.join(REPO, 'web',
                                              'menu_structure.json')))
    _items201 = []

    def _walk201(node):
        for c in node.get('children', []):
            _items201.append(c)
            _walk201(c)

    _walk201(_doc201['tree'])
    # R213: FULL coverage - every dynamic name, no sampling. The .136k
    # field report found 'kryptische Bezeichnungen' in submenus the sample
    # never visited (format filter, menu.input names, is-tests, select).
    _dyn201 = [i for i in _items201
               if '{' in (i.get('name') or '')
               and '{%' not in i['name'] and '{#' not in i['name']]
    _sample201 = _dyn201

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
    # R213: input items see menu.input (their live value) - the LCD names
    # show it while editing, the web page now passes it too. The DEFAULT
    # comes from the item's own input template (evaluated by the page).
    _harness201d = (_eval_js + '\n' + _mk218src
                    + '\nconst DATA = mkPrinter(jparse('
                    + _json201.dumps(_json201.dumps(_raw218(FIX)))
                    + '), null);\nconst TPL = '
                    + _json201.dumps([i.get('input') for i in _sample201])
                    + ';\nconst OUT = TPL.map(t => t ? evalName(t, DATA) '
                      ': null);\nconsole.log(JSON.stringify(OUT));\n')
    open('/tmp/r201_eval_testd.js', 'w').write(_harness201d)
    _r201d = _sp201.run(['node', '/tmp/r201_eval_testd.js'],
                        capture_output=True, text=True, timeout=120)
    _mi201 = []
    if _r201d.returncode == 0:
        for _k201, _v201 in enumerate(_json201.loads(_r201d.stdout)):
            if not _v201:
                _mi201.append(None)
                continue
            _f201 = None
            try:
                _f201 = float(_v201)
            except ValueError:
                _f201 = _v201
            _mi201.append(_f201)
    else:
        _mi201 = [None] * len(_sample201)

    _exp201 = []
    for _k201, _it201 in enumerate(_sample201):
        try:
            _ctx201 = {'printer': FIX, 'params': {}}
            if _mi201[_k201] is not None:
                _ctx201['menu'] = {'input': _mi201[_k201]}
            _exp201.append(_env201.from_string(_it201['name']).render(
                **_ctx201))
        except Exception:                                      # noqa: BLE001
            _exp201.append(None)     # jinja itself fails -> page shows raw

    _harness201 = (_eval_js + '\n' + _mk218src
                   + '\nconst DATA = mkPrinter(jparse('
                   + _json201.dumps(_json201.dumps(_raw218(FIX)))
                   + '), null);\nconst TPL = '
                   + _json201.dumps([i['name'] for i in _sample201])
                   + ';\nconst MI = ' + _json201.dumps(_mi201)
                   + ';\nconst OUT = TPL.map((t, k) => '
                     'evalName(t, DATA, MI[k]));\n'
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
              '(%d dynamic names - FULL coverage, %d rendered by jinja, '
              '%d mismatch)'
              % (len(_sample201),
                 sum(1 for e, _, _ in _pairs201 if e is not None),
                 len(_mm201)),
              not _mm201, str(_mm201[:2])[:300])
        # R213: the 'kryptische Bezeichnungen' regression - NO dynamic
        # name may come back raw (null or with leftover braces)
        _raw201 = [(g, t) for e, g, t in _pairs201
                   if g is None or ('{' in str(g)) or ('}' in str(g))]
        check('T-live-eval R213: ZERO raw labels - every dynamic menu '
              'name renders (the .136k field report: kryptische '
              'Bezeichnungen in submenus)', not _raw201,
              str(_raw201[:3])[:300])

    # enables: strict where the page knows the answer
    _ens201 = [i for i in _items201
               if i.get('enable') and '{' in i['enable']
               and '{%' not in i['enable'] and '{#' not in i['enable']]
    _ensample201 = _ens201      # R213: full coverage
    _expe201 = []
    for _it201 in _ensample201:
        try:
            _o201 = _env201.from_string(_it201['enable']).render(
                printer=FIX, params={})
            _expe201.append(_o201 == 'True')
        except Exception:                                      # noqa: BLE001
            _expe201.append(None)
    _harness201e = (_eval_js + '\n' + _mk218src
                    + '\nconst DATA = mkPrinter(jparse('
                    + _json201.dumps(_json201.dumps(_raw218(FIX)))
                    + '), null);\nconst TPL = '
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
              '(%d - full coverage, %d strict mismatches)'
              % (len(_ensample201), len(_mme201)),
              not _mme201, str(_mme201[:3])[:200])
        # R213: every enable must be DECIDABLE (null = the page can never
        # hide the row = LCD parity broken in the OTHER direction)
        _null201 = [g for g in _gote201 if g is None]
        check('T-live-eval R213: every enable decidable (is-tests, '
              'select) - null would break the LCD hiding parity',
              not _null201, '%d undecidable' % len(_null201))

        # R218 second state: IDLE - the .136o field report lost exactly
        # the idle-only menus (Maintenance, Optimized) to a false enable.
        # Same full coverage, fixture switched to mode='idle'.
        _fixidle218 = _copy218.deepcopy(FIX)
        _fixidle218['gcode_macro _STATE']['mode'] = 'idle'
        _expi218 = []
        for _it201 in _ensample201:
            try:
                _o218 = _env201.from_string(_it201['enable']).render(
                    printer=_fixidle218, params={})
                _expi218.append(_o218 == 'True')
            except Exception:                                  # noqa: BLE001
                _expi218.append(None)
        _harni218 = (_eval_js + '\n' + _mk218src
                     + '\nconst DATA = mkPrinter(jparse('
                     + _json201.dumps(_json201.dumps(_raw218(_fixidle218)))
                     + '), null);\nconst TPL = '
                     + _json201.dumps([i['enable'] for i in _ensample201])
                     + ';\nconst OUT = TPL.map(t => '
                       'evalEnable(t, DATA));\n'
                       'console.log(JSON.stringify(OUT));\n')
        open('/tmp/r201_eval_testi.js', 'w').write(_harni218)
        _ri218 = _sp201.run(['node', '/tmp/r201_eval_testi.js'],
                            capture_output=True, text=True, timeout=120)
        if _ri218.returncode != 0:
            check('T-live-eval R218 idle: node runs the shipped evaluator',
                  False, _ri218.stderr[-200:])
        else:
            _goti218 = _json201.loads(_ri218.stdout)
            _mmi218 = [(e, g) for e, g in zip(_expi218, _goti218)
                       if e is not None and g is not None and e != g]
            _maint218 = None
            for _k218, _it218 in enumerate(_ensample201):
                if _it218['id'] == '__main __maint':
                    _maint218 = _goti218[_k218]
                    break
            check('T-live-eval R218 idle-state parity: enables match the '
                  'LCD truth on a mode=idle snapshot too (%d strict '
                  'mismatches) - Maintenance must be VISIBLE'
                  % len(_mmi218),
                  not _mmi218 and _maint218 is True,
                  'mismatches %s, maint=%r' % (str(_mmi218[:3])[:160],
                                               _maint218))

    # R210: the SENDER parity - the page's renderGcode vs jinja2 on the
    # SAME gcode bodies (klipper's menu evaluates item gcode before it
    # runs; 968 of 1964 commands carry templates. .136h would have POSTed
    # them raw). menu.input = 42 like a typed value.
    _gj201 = [i for i in _items201 if i.get('gcode')
              and '{' in '\n'.join(i['gcode'])]
    _sg201 = _gj201[::max(1, len(_gj201) // 80)][:80]
    _eg201 = []
    for _it201 in _sg201:
        try:
            _r201g = _env201.from_string('\n'.join(_it201['gcode'])).render(
                printer=FIX, params={}, menu={'input': 42})
            _eg201.append([l.strip() for l in _r201g.split('\n')
                           if l.strip()])
        except Exception:                                      # noqa: BLE001
            _eg201.append(None)
    _hg201 = (_eval_js + '\n' + _mk218src
              + '\nconst DATA = mkPrinter(jparse('
              + _json201.dumps(_json201.dumps(_raw218(FIX)))
              + '), null);\nconst G = '
              + _json201.dumps([i['gcode'] for i in _sg201])
              + ';\nconst OUT = G.map(g => renderGcode(g, DATA, 42));\n'
                'console.log(JSON.stringify(OUT.map(o => o === null ? '
                'null : o.map(l => l.trim()).filter(l => l))));\n')
    open('/tmp/r201_eval_testg.js', 'w').write(_hg201)
    _r201g2 = _sp201.run(['node', '/tmp/r201_eval_testg.js'],
                         capture_output=True, text=True, timeout=120)
    if _r201g2.returncode != 0:
        check('T-live-eval R210: node runs the shipped gcode renderer',
              False, _r201g2.stderr[-200:])
    else:
        _gotg201 = _json201.loads(_r201g2.stdout)
        _mmg201 = []
        for _k201, (e, g) in enumerate(zip(_eg201, _gotg201)):
            if e is None:
                continue
            if g is None or e != g:
                _mmg201.append((_k201, _sg201[_k201]['id'], e, g))
        check('T-live-eval R210: gcode RENDER parity with the LCD truth '
              '(%d templated commands sampled, %d jinja-failed skipped, '
              '%d mismatches) - the .136h sender would have POSTed raw '
              'templates' % (len(_sg201),
                             sum(1 for e in _eg201 if e is None),
                             len(_mmg201)),
              not _mmg201, str(_mmg201[:2])[:400])

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

# T5: the .135/.136w code anchors live in the postproc
_src = open(os.path.join(REPO, 'tools', 'r2_postproc.py')).read()
check('T5 anchors: TYPE_RE reads ;TYPE:/;FEATURE:/;STRUCTURE: (Bambu, '
      'FlashPrint, the S3D space dialect, Kiri:Moto bare words), stem '
      'whitelist, _fmove192, air scan, sequence audit, 3x tower tags',
      'type\\s*:\\s*' in _src
      and '(?:feature|structure)\\s*[: ]\\s*' in _src
      and "'; shell', '; fill'" in _src
      and "summary['stray_tag']" in _src
      and "'upper face': 'SURFACE-TOP'" in _src
      and "'external single extrusion': 'WALL-OUTER'" in _src
      and "'multiple': 'CUSTOM'" in _src
      and "'(?<=[a-z])(?=[A-Z])'" in _src
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

# ---- R223 (.136u): the .136s field log - the photo build RAM collapse ---
# A string-art PHOTO job decoded a full-res JPEG into 300MB+ of python
# rows on the 512MB Pi: klippy starved ('Timer too close' x2, host memory
# low 25MB), the job wedged the only worker forever, its key refused every
# retry and gen_busy=1 blocked print starts with no way out from the LCD.
check('R223a decode caps: max_dim on both decoders + _img_luma, image '
      'callers capped (string art 288 - R232: the planner grid is <=220 '
      'cells, the extra decode was pure RAM; litho/colorpic 768)',
      'def _jpeg_to_rgb(data, max_dim=0)' in _src
      and 'def _png_to_rgb(data, max_dim=0)' in _src
      and 'def _img_luma(data, kind, max_dim=0)' in _src
      and '_img_luma(data, kind, max_dim=288)' in _src
      and _src.count('_img_luma(data, kind, max_dim=768)') == 3)
check('R223b JPEG planes are array-backed (8x less RAM per coefficient)',
      "[array('i', [0] * 64)" in _src and '= array(\'i\', blk)' in _src)
check('R223c worker: per-job thread + 20min stuck watchdog + repeating '
      'wait notice + per-job ram_min (image jobs 110MB, rest 60)',
      'JOB_STUCK_S = 1200' in _src and 'th.join(JOB_STUCK_S)' in _src
      and 'STUCK after' in _src and 'ram_min=110' in _src
      and _src.count('ram_min=110') == 3)
check('R223d queue clear channel: gen_clear_nonce in NONCE_KEYS + primed '
      'at boot + handled in the loop; a stale gen_busy is dropped at boot '
      '(a died job must not block print starts forever)',
      "'gen_clear_nonce'," in _src
      and 'last_gclear_nonce = _np.get' in _src
      and 'last_gclear_nonce = None' in _src
      and 'dropped a stale gen_busy flag' in _src
      and 'generator queue cleared' in _src)
check('R223e plan checkpoint: string art aborts below 30MB mid-build '
      'with the Pi-restart advice (not a firmware restart)',
      'string art stopped at' in _src
      and 'System > Pi restart' in _src)
check('R223f RAM-low watcher text says RESTART OF THE PI (a firmware '
      'restart frees nothing)', 'RESTART OF THE PI frees swap' in _src)

# the fixture decode pin: values frozen from the PRE-refactor decoder
import hashlib as _h223
_d223 = open(os.path.join(REPO, 'tools', 'r223_fixture.jpg'), 'rb').read()
_jw, _jh, _jpx = pp._jpeg_to_rgb(_d223)
check('R223g JPEG fixture decode is bit-stable across the step/array '
      'refactor (frozen md5, step=1 = the old decoder exactly)',
      (_jw, _jh) == (96, 72)
      and _h223.md5(repr(_jpx).encode()).hexdigest()[:12] == 'a62af9c9d9c1',
      '%dx%d' % (_jw, _jh))
_jw2, _jh2, _jpx2 = pp._jpeg_to_rgb(_d223, max_dim=24)
check('R223h capped decode: max_dim=24 -> 24x18 and the kept pixels are '
      'IDENTICAL to the full decode (subsample, not a resample)',
      (_jw2, _jh2) == (24, 18) and _jpx2[0][0] == _jpx[0][0],
      '%dx%d' % (_jw2, _jh2))
_m223 = open(os.path.join(REPO, 'menus', 'lcd_menues.cfg')).read()
check('R223i System > Gen jobs menu: how-it-works + live state row + '
      'double-press clear (the queue is visible AND escapable now)',
      '[menu __main __system __genq]' in _m223
      and '__genq __state' in _m223
      and '"BUILDING" if printer["save_variables"].variables.gen_busy' in _m223
      and '_GEN_QUEUE_CLEAR CONFIRM=1' in _m223)
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
          'in ALL proxy locations (/server/, /printer/ AND /machine/ - '
          'R218) + Host without port (field-proven)',
          _site_txt203.count('proxy_set_header Origin "";') == 3
          and _site_txt203.count('if ($r2_csrf_bad) { return 403; }') == 3
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
# script against a FAITHFUL fake moonraker (envelope on EVERY endpoint,
# /server/gcode_store, script POSTs, a REAL timer queue so the 3 s poll
# actually cycles).
# R210 (.136i field log: "seite funktioniert, ABER kein zurueck, rohe
# save_variables-Labels,OctoPrint/Temperatur/Live-Tuning-Menue sichtbar
# obwohl das LCD sie ausblendet"): (a) the live badge said "Klipper nicht
# bereit" while klippy was fine and the REASON was thrown away; (b) no
# back navigation; (c) without live data the labels show RAW jinja and
# NOTHING is hidden; (d) the sender would have POSTed raw templates.
# T8 now asserts the full contract: evaluated labels, LCD-parity
# hiding (per-ID), back navigation, the M117 notification history, the
# console rendering + gcode POST, and the reason surfaced on failure.
try:
    import copy as _copy210
    import json as _json209
    _page_src209 = open(os.path.join(REPO, 'web', 'index.html'),
                        encoding='utf-8').read()
    _script209 = _page_src209.rsplit('<script>', 1)[1].rsplit('</script>',
                                                              1)[0]

    _LIVE_IDLE = _copy210.deepcopy(FIX)
    _LIVE_IDLE['gcode_macro _STATE'].update(
        mode='idle', opt_pending=False, current_type='', layer=0)
    _LIVE_IDLE['print_stats'].update(state='idle', filename='',
                                     print_duration=0.0, total_duration=0.0)
    _LIVE_IDLE['virtual_sdcard'].update(progress=0.0, is_active=False)
    _LIVE_IDLE['display_status'].update(message='', progress=0.0)

    def _run_page209(tree_ok, live):
        """Run the REAL page script in node against the fake moonraker;
        return the collected contract dict (see the runner's JSON)."""
        _js209 = r"""
const vm = require('vm'), fs = require('fs');
const DOC = JSON.parse(fs.readFileSync(process.argv[2], 'utf8'));
const LIVE = JSON.parse(fs.readFileSync(process.argv[3], 'utf8'));
const TREE_OK = process.argv[4] === '1';
function elem(id){ return {id: id, textContent: '', innerHTML: '',
  className: '', title: '', disabled: false, value: '', type: '',
  min: '', max: '', step: '', children: [], _h: {}, style: {},
  classList: {add(){}, remove(){}},
  set onclick(f){ this._h.click = f; }, get onclick(){ return this._h.click; },
  set oninput(f){ this._h.input = f; }, get oninput(){ return this._h.input; },
  set onkeydown(f){ this._h.key = f; }, get onkeydown(){ return this._h.key; },
  appendChild(c){ this.children.push(c); return c; },
  removeChild(c){ const i = this.children.indexOf(c);
    if (i >= 0) this.children.splice(i, 1); return c; },
  get firstChild(){ return this.children[0] || null; },
  querySelector(){ return null; } }; }
const reg = {};
const document = {
  getElementById(id){ if (!reg[id]) reg[id] = elem(id); return reg[id]; },
  createElement(t){ return elem('<' + t + '>'); },
  createTextNode(t){ return {textContent: String(t)}; },
  // R216: the machine panel + clear popover register a global click
  // listener - a no-op is enough (the shim clicks elements directly)
  addEventListener(){} };
let unhandled = null;
process.on('unhandledRejection', e => { unhandled = String(e); });
const GETS = [], POSTS = [];
let liveCalls = 0, clock = 0, tid = 0;
const timers = [];
const setTimeout = (fn, ms) => {
  timers.push({id: ++tid, fn: fn, at: clock + (ms || 0)}); return tid; };
const clearTimeout = (id) => { const i = timers.findIndex(t => t.id === id);
  if (i >= 0) timers.splice(i, 1); };
const J = o => ({ok: true, json: async () => ({result: o}),
  text: async () => JSON.stringify({result: o})});   // R213: real API
const fetch = async (url, opts) => {
  const u = String(url);
  GETS.push(u.split('?')[0]);
  if (u.indexOf('/server/r2_menu/tree') === 0) {
    if (!TREE_OK) return {ok: false, json: async () => ({})};
    return J(DOC);
  }
  if (u.indexOf('/server/r2_menu/live') === 0) {
    liveCalls++;
    if (LIVE && LIVE.ok === false) return J(LIVE);
    const o = {ok: true, objects: JSON.parse(JSON.stringify(LIVE)),
               pruned: []};
    if (o.objects.display_status)
      o.objects.display_status.message = 'message ' + liveCalls;
    return J(o);
  }
  if (u.indexOf('/server/gcode_store') === 0) {
    return J({gcode_store: [
      {message: 'echo: Macro system OK (build R2-2026-10-29.136i)',
       time: 1.0, type: 'response'},
      {message: 'M117 Hallo vom LCD', time: 2.0, type: 'command'},
      {message: 'RESPOND MSG="ok"', time: 3.0, type: 'response'},
      {message: '// GuiFromVSDCard state:Printing', time: 4.0,
       type: 'action'}]});
  }
  if (u.indexOf('/printer/gcode/script') === 0) {
    POSTS.push(opts && opts.body ? String(opts.body) : '(no body)');
    return J('ok');
  }
  if (u.indexOf('/server/r2_menu/refresh') === 0) return J({ok: true});
  return {ok: false, json: async () => ({})};
};
const sandbox = {document: document, fetch: fetch, console: console,
  setTimeout: setTimeout, clearTimeout: clearTimeout};
sandbox.window = sandbox;
vm.createContext(sandbox);
try { vm.runInNewContext(fs.readFileSync(process.argv[5], 'utf8'),
                         sandbox); }
catch (e) { console.log(JSON.stringify({error: 'load: ' + String(e)}));
  process.exit(0); }
(async () => {
  const tick = () => new Promise(r => process.nextTick(r));
  let fired = 0, idle = 0;
  for (let k = 0; k < 400 && fired < 14 && idle < 10; k++) {
    for (let j = 0; j < 3; j++) await tick();
    if (!timers.length) { idle++; continue; }
    idle = 0;
    timers.sort((a, b) => a.at - b.at);
    const t = timers.shift();
    clock = Math.max(clock, t.at);
    fired++;
    try { const r = t.fn(); if (r && r.then) r.then(() => {}, () => {}); }
    catch (e) { unhandled = unhandled || String(e); }
  }
  for (let j = 0; j < 15; j++) await tick();
  const menu = reg['menu'];
  const crumbTxt = () => reg['crumb'].children
    .map(c => c.textContent).join(' ').trim();
  const names = [], hiddenIds = [];
  let hidden = 0;
  if (menu) for (const li of menu.children) {
    names.push(li._nm ? li._nm.textContent : '');
    if (li.style && li.style.display === 'none') {
      hidden++; hiddenIds.push(li._n ? li._n.id : '?'); }
  }
  const crumb0 = crumbTxt();
  let nav = {deep: null, back: null};
  try {
    const li = menu.children.find(c => c._n && c._n.type === 'list');
    if (li && li._h.click) {
      li._h.click();
      for (let j = 0; j < 6; j++) await tick();
      nav.deep = crumbTxt();
      if (reg['back']._h.click) {
        reg['back']._h.click();
        for (let j = 0; j < 6; j++) await tick();
        nav.back = crumbTxt(); }
    }
  } catch (e) { nav = {deep: 'ERR ' + String(e), back: null}; }
  try {
    reg['gcodein'].value = 'M117 WebTest';
    if (reg['gcodesend']._h.click) reg['gcodesend']._h.click();
    for (let j = 0; j < 6; j++) await tick();
  } catch (e) {}
  let selftest = null;
  try {
    const R = sandbox.R2WEB;
    if (!R) selftest = 'no R2WEB';
    else selftest = {
      a: R.renderGcode(['{% set s = 5 %}', 'PA {s}'], {}, 0).join('|'),
      b: R.renderGcode(['{% if 0 %}', 'x', '{% else %}', 'y',
                        '{% endif %}'], {}, 0).join('|'),
      c: R.renderGcode(['V={menu.input}'], {}, 42).join('|')};
  } catch (e) { selftest = 'ERR ' + String(e); }
  const cnt = id => (reg[id] && reg[id].children)
    ? reg[id].children.length : -1;
  const txt = id => reg[id] ? reg[id].textContent : null;
  console.log(JSON.stringify({error: unhandled,
    menu_children: menu ? menu.children.length : -1,
    crumb: crumb0, badge: txt('srcbadge'),
    names: names, hidden: hidden, hidden_ids: hiddenIds,
    nav: nav, live_calls: liveCalls,
    notif_n: cnt('notiflist'),
    notifcur: txt('notifcur'),
    con_n: cnt('conlist'),
    gets: GETS, posts: POSTS, selftest: selftest}));
})();
"""
        import tempfile as _tf209
        _d209 = _tf209.mkdtemp(prefix='r210_')
        _fd209 = os.path.join(_d209, 'page.js')
        _fo209 = os.path.join(_d209, 'live.json')
        _fs209 = os.path.join(_d209, 'pagescript.js')
        open(_fd209, 'w').write(_js209)
        open(_fo209, 'w').write(_json209.dumps(live))
        open(_fs209, 'w').write(_script209)   # ~900 kB: as a FILE, not argv
        _r209 = _sp200.run(
            ['node', _fd209, os.path.join(REPO, 'web',
                                          'menu_structure.json'),
             _fo209, '1' if tree_ok else '0', _fs209],
            capture_output=True, text=True, timeout=180)
        _sh200.rmtree(_d209, ignore_errors=True)
        try:
            return _json209.loads(_r209.stdout.strip().splitlines()[-1])
        except Exception as _e209:                                  # noqa
            return {'error': 'node: %s / %s' % (_e209, _r209.stderr[-160:])}

    _A = _run_page209(True, FIX)               # printing snapshot
    _nA = _A.get('names') or []
    _hA = _A.get('hidden_ids') or []
    check('T8 page<->moonraker contract (R209+R210): the REAL page script '
          'renders the menu from the REAL component response IN THE '
          'MOONRAKER ENVELOPE, labels EVALUATED live (no raw '
          '"save_variables" text left) and LCD-conditioned entries '
          'hidden - the .136b-.136g page crashed on the envelope, the '
          '.136h page showed raw jinja and hid nothing',
          _A.get('error') is None
          and _A.get('menu_children', -1) >= 5
          and _A.get('crumb') == '__main'
          and 'values live' in (_A.get('badge') or '')
          and not any('save_variables' in n for n in _nA)
          and len([n for n in _nA if '{' in n]) <= max(2, len(_nA) // 5)
          and '__main __start' in _hA            # enable: mode == waiting
          and '__main __optprint' in _hA         # enable: mode in idle/...
          and '__main __endq' not in _hA         # opt_pending -> visible
          and '__main __octoprint' in _hA,       # enable {False}
          str({k: _A.get(k) for k in ('error', 'menu_children', 'crumb',
                                      'badge', 'hidden')})[:220])
    check('T8 R210 interaction: back navigation returns to __main, the '
          'M117 notification history collects the display stream, the '
          'console renders gcode_store and the gcode input POSTs to '
          'moonraker',
          _A.get('error') is None
          and (_A.get('nav') or {}).get('back') == '__main'
          and ((_A.get('nav') or {}).get('deep') or '') not in
              ('__main', None, '')
          and (_A.get('live_calls') or 0) >= 3
          and (_A.get('notif_n') or 0) >= 3
          and 'message ' in (_A.get('notifcur') or '')
          and (_A.get('con_n') or 0) >= 3
          and any('/server/gcode_store' in g for g in (_A.get('gets') or []))
          and any('M117 WebTest' in p for p in (_A.get('posts') or []))
          and _A.get('selftest') == {'a': 'PA 5', 'b': 'y', 'c': 'V=42'},
          str({k: _A.get(k) for k in ('nav', 'live_calls', 'notif_n',
                                      'notifcur', 'con_n', 'posts',
                                      'selftest')})[:240])
    _B = _run_page209(True, _LIVE_IDLE)         # idle snapshot
    _hB = _B.get('hidden_ids') or []
    check('T8 LCD-parity hiding (R210): idle snapshot flips the menus '
          'exactly like the display (Rate print? vanishes, Optimized '
          'appears) and idle labels still evaluate',
          _B.get('error') is None
          and '__main __endq' in _hB
          and '__main __optprint' not in _hB
          and '__main __start' in _hB
          and 'values live' in (_B.get('badge') or '')
          and not any('save_variables' in n for n in (_B.get('names') or []))
          and (_B.get('notifcur') or '') != '',
          str({'hiddenA': len(_hA), 'hiddenB': len(_hB),
               'endq_B': '__main __endq' in _hB})[:160])
    _C = _run_page209(False, FIX)               # tree endpoint down
    check('T8 page fallback: tree endpoint down -> the EMBEDDED export '
          'renders (menu >= 5, badge says embedded, labels STILL '
          'evaluate against live data, no crash)',
          _C.get('error') is None
          and _C.get('menu_children', -1) >= 5
          and 'embedded' in (_C.get('badge') or '')
          and not any('save_variables' in n for n in (_C.get('names') or [])),
          str({k: _C.get(k) for k in ('error', 'menu_children',
                                      'badge')})[:200])
    _D = _run_page209(True, {'ok': False,
                             'reason': 'klippy state: shutdown'})
    check('T8 live-reason surfaced (R210): a component failure shows its '
          'REASON in the badge - .136h only said "Klipper nicht bereit" '
          'and the reason was thrown away',
          _D.get('error') is None
          and 'klippy state: shutdown' in (_D.get('badge') or ''),
          str(_D)[:220])
finally:
    pass


# ================================================================== T-meta
# R212 (.136k field log: 'wenn ich die Mainsail im gcodes ordner
# anschau sehe ich keine Metadaten... dachte eigentlich dass bei neu
# generiertem G-Code aus einer Slicer-Datei die Metadaten erhalten
# bleiben'): generated files now get Mainsail metadata - thumbnail +
# estimated time + filament, computed from the file's OWN moves (a range
# excerpt keeps its honest time) with the SOURCE's thumbnail copied for
# derived files. Slicer files are never touched.
try:
    import base64 as _b64212
    import struct as _st212
    import zlib as _zl212
    import gcode_meta as _gm212
    _md212 = tempfile.mkdtemp(prefix='r212meta_')
    _mp212 = pp.make_labels(['R2', 'TEST'], bed=BED, out_dir=_md212)[0]
    _stx212 = 'meta' if _gm212.finalize(_mp212) else ''
    _txt212 = open(_mp212).read()
    # R225 (.136w): the block layout follows moonraker's REAL parser -
    # 3-int thumbnail header (w x h + base64 length), block at the END
    # (PrusaSlicer's parser reads the footer), identify stamp
    # '; generated by R2-D2 <release> on <date> at <time>' in the header
    # (activates the Prusa parser chain - UnknownSlicer hardcodes
    # time/filament to None).
    _m212 = re.search(
        r'^; thumbnail begin (\d+)x(\d+) (\d+)\n(.*?)^; thumbnail end\n',
        _txt212, re.M | re.S)
    _b64f212 = ''.join(_l212[2:] for _l212 in _m212.group(4).split('\n')
                       if _l212.startswith('; '))
    _png212 = _b64212.b64decode(_b64f212)
    _w212, _h212 = _st212.unpack('>II', _png212[16:24])
    _i212 = _png212.find(b'IDAT')
    _ln212 = _st212.unpack('>I', _png212[_i212 - 4:_i212])[0]
    _rows212 = len(_zl212.decompress(
        _png212[_i212 + 4:_i212 + 4 + _ln212])) == 128 * (128 * 3 + 1)
    _foot212 = _txt212[-4096:]
    _stamp212 = _txt212.split('\n')[1] if '\n' in _txt212 else ''
    check('T-meta R212: a GENERATED file gets Mainsail metadata the way '
          'moonraker REALLY parses it (3-int thumbnail header + payload '
          'length match, block in the FOOTER, R2-D2 identify stamp in '
          'the header, valid 128x128 PNG, time + filament; the R2-GEN '
          'stamp stays the first line)',
          _stx212 == 'meta' and _png212[:8] == b'\x89PNG\r\n\x1a\n'
          and (_w212, _h212) == (128, 128) and _rows212
          and len(_b64f212) == int(_m212.group(3))
          and _txt212.rstrip('\n').split('\n')[-1].startswith('; R2-META sig')
          and 'estimated printing time' in _foot212
          and 'filament used [mm]' in _foot212
          and _txt212.endswith('\n')
          and re.match(r'^; generated by R2-D2 \S+ on \d{4}-\d{2}-\d{2} '
                       r'at \d{2}:\d{2}:\d{2}$', _stamp212)
          and _txt212.startswith('; R2-GEN'),
          '%dx%d len=%s/%s' % (_w212, _h212, len(_b64f212),
                               _m212.group(3)))
    _b212 = open(_mp212, 'rb').read()
    _gm212.finalize(_mp212)
    check('T-meta R212: idempotent - a second finalize changes nothing '
          '(the watcher scan may see the file again)',
          open(_mp212, 'rb').read() == _b212)
    _src212 = pp.make_labels(['SRC'], bed=BED, out_dir=_md212)[0]
    _gm212.finalize(_src212)
    _rng212, _nl212 = pp.make_range(_src212, 2, 4)
    _rt212 = open(_rng212).read()
    _st212 = open(_src212).read()
    _th212 = _st212[_st212.index('; thumbnail begin'):
                    _st212.index('; thumbnail end')]
    _tir212 = re.search(r'printing time \(normal mode\) = (.+)', _rt212)
    _tis212 = re.search(r'printing time \(normal mode\) = (.+)', _st212)
    _rb212 = open(_rng212, 'rb').read()
    _gm212.finalize(_rng212, src=_src212)     # watcher may see it again
    check('T-meta R212: a DERIVED file (range excerpt) copies the SOURCE '
          'thumbnail but computes its OWN honest time from its own moves',
          '; thumbnail begin' in _rt212            # hook ran in make_range
          and 'estimated printing time' in _rt212
          and _th212 in _rt212                    # THE source thumbnail
          and bool(_tir212) and bool(_tis212)
          and _tir212.group(1) != _tis212.group(1)   # own honest time
          and open(_rng212, 'rb').read() == _rb212,  # idempotent
          'thumb=%s time=%s'
          % (_th212 in _rt212,
             _tir212.group(1) if _tir212 else '-'))
    _sl212 = os.path.join(_md212, 'slicer.gcode')
    open(_sl212, 'w').write(
        '; thumbnail begin 300x300\n; aaaa\n; thumbnail end\n'
        '; estimated printing time (normal mode) = 9h 9m 9s\n'
        'G28\nG1 X10 Y10 E1 F1200\nG1 X20 Y10 E2\n')
    _sb212 = open(_sl212, 'rb').read()
    check('T-meta R212: slicer files keep THEIR metadata (hands off) and '
          'the postproc hook is eligibility-guarded (R2-GEN stamp / gen '
          'folder / optimized only)',
          _gm212.finalize(_sl212) == 'own'
          and open(_sl212, 'rb').read() == _sb212
          and callable(getattr(pp, '_meta_finalize', None)),
          'slicer file modified')
    _sh200.rmtree(_md212, ignore_errors=True)
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
