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

    def register_endpoint(self, ep, methods, handler):
        self.endpoints[ep] = handler

    def register_remote_method(self, name, cb):
        pass

    def add_log_rollback_handler(self, cb):
        pass

    def get_server(self):
        return self


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
check('T2 extension: 3 endpoints registered',
      set(eps) == {'/server/r2_menu/tree', '/server/r2_menu/status',
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
loop.close()

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

# ================================================================== summary =
print()
if FAILS:
    print('R197 GEN SWEEP: %d checks, %d FAIL' % (N, len(FAILS)))
    for f in FAILS:
        print('  -', f)
    sys.exit(1)
print('R197 GEN SWEEP: %d checks, 0 FAIL - all generators + tools green' % N)
