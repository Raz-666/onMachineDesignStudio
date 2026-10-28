#!/usr/bin/env python3
"""R132 HARDCORE STRESS TEST - the bugs the field logs keep finding.

Motivation (field log .92): the standing battery was green while the real
printer died three different ways in one session -
  1. APPLY_TYPE TYPE=Bottom surface    -> 'Malformed command', print dead
  2. _PACE P400                        -> 'Malformed command', FIX_FILE dead
  3. SET_IDLE_TIMEOUT TIMEOUT=0        -> error, start-dialog poller dead
     -> mode wedged 'waiting', every start button did NOTHING
None of these was a wrong NUMBER - all three were SYNTAX/STATE bugs that a
'generated file looks plausible' test cannot catch. This suite attacks
exactly those classes:

  PART A  Klipper syntax lint - EVERY command line of EVERY generated file
          must parse: raw G/M/T commands pass, everything else must be
          NAME KEY=VALUE KEY=VALUE (values may be quoted). Bare tokens and
          unquoted trailing text are what Klipper rejects as 'Malformed'.
  PART B  generation matrix - all 76 catalog codes, both color modes, brim
          0 and 8, figures x modes x scales x colors, kit from a generated
          file, colorpic, ties, angles, seal, labels - twice (idempotence).
  PART C  invariants - bed bounds, CENTERED layout (R132 user rule),
          LAYER_MARK present, EXCLUDE objects, M600 = color boundaries,
          BY_OBJECT flag, no 'APPLY_TYPE TYPE=' with a space, E > 0.
  PART D  static regression net for the .92 bug classes (cfg + watcher).
  PART E  mini render - every [gcode_macro] body rendered with a mock
          printer; the OUTPUT lines go through the PART A lint (catches
          the unbalanced-quote RESPOND class at the source).
Exit code != 0 on any fail.  R140 STRESS summary line at the end.
"""
import atexit
import os
import re
import shutil
import struct
import sys
import tempfile
import zlib

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import importlib.util                                  # noqa: E402

_spec = importlib.util.spec_from_file_location(
    'pp', os.path.join(HERE, 'r2_postproc.py'))
pp = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(pp)

D = tempfile.mkdtemp(prefix='r140_')
atexit.register(lambda: shutil.rmtree(D, ignore_errors=True))
BED = (0.0, 0.0, 220.0, 220.0)
fails = []
n_ck = [0]


def ck(name, cond, info=''):
    n_ck[0] += 1
    if not cond:
        fails.append((name, str(info)[:120]))


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


# ============================================================ PART A ======
EXT_LINE = re.compile(
    r"^[A-Za-z_][A-Za-z0-9_]*(\s+[A-Za-z_][A-Za-z0-9_]*="
    r"(\"[^\"]*\"|'[^']*'|[^ ]*))*$")
RAW_LINE = re.compile(r'^[GMT]\d+')


def klipper_lint(path):
    """every command line in a g-code file must survive Klipper's parser"""
    problems = []
    try:
        lines = open(path, errors='replace').read().splitlines()
    except OSError as e:
        return [(0, 'unreadable: %r' % e)]
    for i, ln in enumerate(lines):
        cpos = ln.find(';')
        cmd = ln[:cpos if cpos >= 0 else None].strip()
        if not cmd:
            continue
        word = cmd.split(' ', 1)[0]
        if RAW_LINE.match(word):
            continue                      # raw G/M/T: Klipper's own parser
        if not EXT_LINE.match(cmd):
            problems.append((i + 1, cmd[:70]))
    return problems


# ============================================================ PART B ======
gen_files = []          # (path, kind, meta)


def gen(name, fn):
    try:
        out, info = fn()
    except Exception as e:                    # noqa: BLE001
        ck('gen ' + name, False, repr(e))
        return None
    ck('gen ' + name, True)
    for f in (info.get('plate_files') or [info.get('file')]):
        if f:
            gen_files.append((os.path.join(D, str(f)), name, info))
    return out, info


codes = sorted(pp.BRICK_CATALOG)
ck('catalog has 76 codes', len(codes) == 76, len(codes))
for need in ('S1x2', 'S2x6', 'I1x3', 'A1x6', 'H1x8', 'C1x1', 'J1x2',
             'RT1x1', 'T8x8', 'RP1x1'):
    ck('catalog has ' + need, need in pp.BRICK_CATALOG)

for bi in range(0, len(codes), 12):
    batch = codes[bi:bi + 12]
    gen('bricks batch%d' % bi,
        lambda b=batch, v=bi // 12 + 1: pp.make_bricks(
            [(c, 1) for c in b], out_dir=D, bed=BED, version=v))

gen('bricks BY_LAYER 3col',
    lambda: pp.make_bricks([('B2x4', 3), ('P2x2', 2), ('S1x3', 1),
                            ('A1x4', 1)], out_dir=D, bed=BED, colors=3,
                           mode='BY_LAYER', version=41))
gen('bricks BY_OBJECT 4col',
    lambda: pp.make_bricks([('B2x4', 3), ('T1x2', 2), ('H1x6', 1),
                            ('C1x1', 2)], out_dir=D, bed=BED, colors=4,
                           mode='BY_OBJECT', version=42))
gen('bricks nobrim',
    lambda: pp.make_bricks([('I2x3', 2), ('RT1x1', 4)], out_dir=D, bed=BED,
                           brim=0, version=43))
gen('bricks brim8',
    lambda: pp.make_bricks([('R1x1', 2), ('J1x2', 2)], out_dir=D, bed=BED,
                           brim=8, version=44))

for sc in (25, 50, 100, 300):
    gen('figures s%d parts' % sc,
        lambda s=sc: pp.make_figures(count=2, scale=s, out_dir=D, bed=BED,
                                     version=45))
gen('figures single',
    lambda: pp.make_figures(count=2, scale=100, out_dir=D, bed=BED,
                            mode='SINGLE', version=46))
gen('figures colors BY_LAYER',
    lambda: pp.make_figures(count=2, scale=100, out_dir=D, bed=BED, colors=4,
                            colormode='BY_LAYER', version=47))
gen('figures colors BY_OBJECT',
    lambda: pp.make_figures(count=2, scale=100, out_dir=D, bed=BED, colors=4,
                            colormode='BY_OBJECT', version=48))
gen('figures 24x s25',
    lambda: pp.make_figures(count=24, scale=25, out_dir=D, bed=BED,
                            version=49))

# kit from a generated file (has APPLY_TYPE markers like a sliced job)
_kit_src = os.path.join(D, 'V01_Bricks.gcode')   # R158/R160: version first, no 00_ prefix
gen('kit BY_LAYER', lambda: pp.make_brick_kit(
    _kit_src, out_dir=D, bed=BED, mode='BY_LAYER', colors=3, version=51))
gen('kit BY_OBJECT', lambda: pp.make_brick_kit(
    _kit_src, out_dir=D, bed=BED, mode='BY_OBJECT', colors=4, version=52))

gen('ties', lambda: pp.make_cable_ties(count=4, length=100, out_dir=D,
                                       bed=BED, version=53))
gen('angles', lambda: pp.make_angles(count=2, out_dir=D, bed=BED,
                                     version=54))
gen('seal', lambda: pp.make_seal(out_dir=D, bed=BED, version=55))
gen('labels', lambda: pp.make_labels(['STRESS', 'TEST'], out_dir=D, bed=BED,
                                     version=56))
_img = os.path.join(D, 'stress.png')
open(_img, 'wb').write(png(48, 48, lambda x, y: (x * 5 + y * 3) % 256))
gen('colorpic', lambda: pp.make_colorpic(_img, out_dir=D, bed=BED,
                                         width_mm=80, bands=4, version=57))

# idempotence: identical job -> identical bytes
_d1 = tempfile.mkdtemp(dir=D)
_d2 = tempfile.mkdtemp(dir=D)
atexit.register(lambda d1=_d1, d2=_d2: (shutil.rmtree(d1, ignore_errors=True),
                                         shutil.rmtree(d2, ignore_errors=True)))
# R133f: versions auto-bump (fresh dir -> V01 on both sides; the returned
# paths carry the real names - SINGLE/PARTS is part of the figure name now)
_oi1, _ = pp.make_bricks([('S1x3', 2), ('A1x4', 1), ('H1x4', 2)], out_dir=_d1,
                         bed=BED, brim=3, colors=2, mode='BY_OBJECT')
_oi2, _ = pp.make_bricks([('S1x3', 2), ('A1x4', 1), ('H1x4', 2)], out_dir=_d2,
                         bed=BED, brim=3, colors=2, mode='BY_OBJECT')
ck('idempotence bricks', open(_oi1).read() == open(_oi2).read(),
   '%s vs %s' % (os.path.basename(_oi1), os.path.basename(_oi2)))
_oi3, _ = pp.make_figures(count=1, scale=100, out_dir=_d1, bed=BED,
                          mode='SINGLE')
_oi4, _ = pp.make_figures(count=1, scale=100, out_dir=_d2, bed=BED,
                          mode='SINGLE')
ck('idempotence figures single (name carries SINGLE + auto version)',
   open(_oi3).read() == open(_oi4).read()
   and os.path.basename(_oi3) == 'V02_Figure_s100_SINGLE.gcode',
   os.path.basename(_oi3))

# ============================================================ PART C ======
CANON = set(pp.TYPE_MAP.values()) | {'CUSTOM'}
for (path, job, info) in gen_files:
    if not os.path.isfile(path):
        ck('exists ' + job + ' ' + os.path.basename(path), False)
        continue
    tag = job + '/' + os.path.basename(path)
    # A) syntax lint
    for (ln, cmd) in klipper_lint(path):
        ck('SYNTAX ' + tag, False, 'line %d: %s' % (ln, cmd))
    txt = open(path, errors='replace').read()
    # B) canonical APPLY_TYPE, no spaces
    for m in re.finditer(r'^APPLY_TYPE TYPE=(\S+)', txt, re.M):
        ck('canon ' + tag, m.group(1) in CANON, m.group(1))
    ck('no pretty APPLY_TYPE ' + tag,
       not re.search(r'^APPLY_TYPE TYPE=\S+ \S', txt, re.M))
    # C) LAYER_MARK + markers
    ck('LAYER_MARK ' + tag, 'LAYER_MARK' in txt)
    ck('markers ' + tag, 'APPLY_TYPE TYPE=' in txt)
    # D) bed bounds
    xs = [float(v) for v in re.findall(r' X(-?[\d.]+) Y', txt)]
    ys = [float(v) for v in re.findall(r' Y(-?[\d.]+)', txt)]
    ck('extrusion ' + tag, ' E' in txt)
    if xs:
        ck('in bed ' + tag,
           min(xs) >= -1.0 and max(xs) <= 221.0 and min(ys) >= -1.0
           and max(ys) <= 221.0,
           '%.1f..%.1f / %.1f..%.1f' % (min(xs), max(xs), min(ys), max(ys)))
        cx = (min(xs) + max(xs)) / 2.0
        cy = (min(ys) + max(ys)) / 2.0
        ck('centered ' + tag, abs(cx - 110) < 15 and abs(cy - 110) < 15,
           '%.1f,%.1f' % (cx, cy))
    # E) M600 = color boundaries (BY_OBJECT: groups-1 changes; header
    #    comment may mention M600 once)
    if (info.get('kind') in ('bricks', 'figures')
            and (info.get('mode') == 'BY_OBJECT'
                 or info.get('colormode') == 'BY_OBJECT')):
        ncol = info.get('colors', 1)
        if isinstance(ncol, list):
            ncol = len(ncol)
        real = txt.count('\nM600')
        ck('m600 count ' + tag, real == max(0, ncol - 1),
           '%d colors, %d M600' % (ncol, real))
        ck('byobject flag ' + tag, 'BY_OBJECT=1' in txt)
    # F) EXCLUDE objects for multi-part files
    if info.get('kind') in ('bricks', 'figures', 'brickkit'):
        ck('exclude objects ' + tag,
           txt.count('EXCLUDE_OBJECT_DEFINE') >= 1)
    # keep /tmp small: validated -> delete
    try:
        os.unlink(path)
    except OSError:
        pass

# ============================================================ PART D ======
def _rd(rel):
    return open(os.path.join(HERE, '..', rel), encoding='utf-8').read()

ROOT = os.path.join(HERE, '..')
MAC = {f: _rd('macros/' + f) for f in os.listdir(os.path.join(ROOT,
                                                             'macros'))}
WATCH = _rd('tools/r2_postproc.py')

# D1: no _PACE with a bare value anywhere
for fn, txt in MAC.items():
    ck('D1 no _PACE P<digits> ' + fn,
       not re.search(r'_PACE\s+P\d', txt))
# D2: _WAIT_IDLE_RESTORE has the floor + FIX_FILE arms fix_reselect
w = MAC['08_print_start_stop.cfg']
ck('D2 idle floor', '{% if t <= 0 %}\n        {% set t = 3600 %}'
   in w or 'set t = 3600' in w)
# R133: 6 armed fixes now (retract/vol/flowcap/travel/travelacc/segments)
ck('D2 fix_reselect armed', w.count("fix_reselect VALUE='\"{fn}\"'") == 6,
   w.count("fix_reselect VALUE='\"{fn}\"'"))
ck('D2 FIX_FILE no cancel-release',
   "VARIABLE=start_decision VALUE='\"cancel\"'" not in w)
# D3: the poller reschedules FIRST
p7 = MAC['07_start_confirm.cfg']
i_wait = p7.index("{% if s.mode == 'waiting' %}")
i_dec = p7.index("{% set dec = sv.start_decision", i_wait)
i_resched = p7.index('UPDATE_DELAYED_GCODE ID=_START_CONFIRM_WAITER', i_wait)
ck('D3 poller reschedules first', i_resched < i_dec)
ck('D3 poller only reschedules while waiting',
   p7.count('UPDATE_DELAYED_GCODE ID=_START_CONFIRM_WAITER DURATION=2')
   - p7.count('ID=_START_CONFIRM_WAITER DURATION=2\n') <= 3)
# D4: Z-hop RESPOND = ONE quoted string
z = MAC['10_live_tuning.cfg']
m = re.search(r'RESPOND MSG="Z-hop \{[^"]+\}(\{%- if [^\n]+)', z)
ck('D4 z-hop single quote', bool(m)
   and z.count('RESPOND MSG="Z-hop {') == 1
   and 'OFF"}"\n' not in z)
# D5: watcher emits FILE_PROFILE_AUTO (macro name!) + re-selects after fix
ck('D5 FILE_PROFILE_AUTO (no underscore)',
   "'FILE_PROFILE_AUTO FILE=\"" in WATCH
   and "'_FILE_PROFILE_AUTO FILE=\"" not in WATCH)
ck('D5 fix reselect in watcher', 'fix_reselect' in WATCH
   and 'SDCARD_PRINT_FILE FILENAME=' in WATCH)
# D6: canonical APPLY_TYPE emission in the generator helpers
# R186: the R179 resolution ladder replaced the bare TYPE_MAP.get -
# _lookup_type resolves unknown spellings by keyword rules first
for helper in ('_ty121', '_ty125', '_ty126'):
    ck('D6 ' + helper + ' maps via the canonical resolver (R179)',
       ("_lookup_type(t) or 'CUSTOM'" in WATCH)
       and WATCH.count(helper) >= 3)
ck('D6 no bare TYPE=%s % t emitters',
   "a('APPLY_TYPE TYPE=%s' % t)" not in WATCH)
# D7: 19_bricks catalog sync (cfg == python)
import ast as _ast                                  # noqa: E402
cfg19 = _rd('macros/19_bricks.cfg')
m = re.search(r"variable_catalog: \[([^\]]+)\]", cfg19)
cfg_codes = _ast.literal_eval('[' + m.group(1) + ']')
ck('D7 catalog sync 76', sorted(cfg_codes) == sorted(pp.BRICK_CATALOG),
   set(cfg_codes) ^ set(pp.BRICK_CATALOG))
# D8: new menu entries exist
lcd = _rd('menus/lcd_menues.cfg')
for entry in ('__bricks __set __brim]', '__bricks __set __col]',
              '__bricks __set __mod __layer]',
              '__bricks __fig __mod __one]', '__bricks __fig __brim]',
              '__bricks __fig __col]', '__bricks __fig __cmod __obj]',
              '__bricks __cat __sl]', '__bricks __cat __te]',
              '__bricks __cat __ro]'):
    ck('D8 menu ' + entry, entry in lcd)
ck('D8 menu 76 catalog entries', lcd.count('BRICK_ADD CODE=') == 76,
   lcd.count('BRICK_ADD CODE='))

# ============================================================ PART E ======
try:
    import jinja2
    HAVE_JINJA = True
except ImportError:
    HAVE_JINJA = False
    print('[E] jinja2 not installed - mini render skipped')

if HAVE_JINJA:
    class M0(int):
        """mock that behaves like 0 but tolerates everything"""
        def __getitem__(self, k):
            return M0(0)
        def __contains__(self, k):
            return False
        def __call__(self, *a, **k):
            return M0(0)
        def __iter__(self):
            return iter(())
        def split(self, *a, **k):
            return []
        def strip(self, *a, **k):
            return ''
        def upper(self, *a, **k):
            return ''
        def lower(self, *a, **k):
            return ''
        def replace(self, *a, **k):
            return ''
        def join(self, *a, **k):
            return ''
        def startswith(self, *a, **k):
            return False
        def endswith(self, *a, **k):
            return False
        def rsplit(self, *a, **k):
            return []

    class NSM:
        """namespace() mock: any attribute reads as 0, writes stick"""
        def __getattr__(self, k):
            return M0(0)
        def __setattr__(self, k, v):
            pass

    class Params(dict):
        def __missing__(self, k):
            return M0(0)

    def render_body(body):
        # Klipper's exact delimiters: {% %} statements, { } expressions
        env = jinja2.Environment('{%', '%}', '{', '}',
                                 undefined=jinja2.Undefined)
        tpl = env.from_string(body)
        # the REAL jinja namespace - {% set ns.x = ... %} needs it
        return tpl.render(params=Params(), printer=M0(0),
                          menu=Params(),
                          namespace=lambda *a, **k: jinja2.utils.Namespace(**k))

    MACRO_RE = re.compile(
        r'\[gcode_macro ([^\]]+)\](.*?)(?=\n\[|\Z)', re.S)
    MUST_RENDER = ('SET_Z_HOP', 'FIX_FILE', '_WAIT_IDLE_RESTORE',
                   'PRINT_AS_LEGACY', 'PRINT_AS_SLICED',
                   'CANCEL_PENDING_PRINT', 'BRICK_ADD', 'BRICK_CREATE',
                   'GEN_BRICKS', 'GEN_FIGURES', 'GEN_BRICKKIT',
                   'APPLY_TYPE', 'SET_MATERIAL', 'SHOW_STATUS')
    rendered = skipped = 0
    for fn in sorted(MAC):
        txt = MAC[fn]
        # balance FIRST - an unbalanced body breaks Klipper's config load
        # (the R132 GEN_BRICKS double-if class - found the hard way)
        for m in MACRO_RE.finditer(txt):
            name, body = m.group(1).strip(), m.group(2)
            if '\ngcode:' not in body:
                continue
            g = body.split('\ngcode:', 1)[1]
            g = re.split(r'\n[a-z_]+:', g)[0]
            # comment lines never reach Klipper's parser
            g = '\n'.join(l for l in g.splitlines()
                          if l.strip() and not l.lstrip().startswith('#'))
            n_if = len(re.findall(r'\{%-?\s*if\b', g))
            n_endif = len(re.findall(r'\{%-?\s*endif\b', g))
            n_for = len(re.findall(r'\{%-?\s*for\b', g))
            n_endfor = len(re.findall(r'\{%-?\s*endfor\b', g))
            ck('E if-balance %s:%s' % (fn, name), n_if == n_endif,
               '%d if / %d endif' % (n_if, n_endif))
            ck('E for-balance %s:%s' % (fn, name), n_for == n_endfor,
               '%d for / %d endfor' % (n_for, n_endfor))
        for m in MACRO_RE.finditer(txt):
            name, body = m.group(1).strip(), m.group(2)
            if '\ngcode:' not in body:
                continue
            gbody = body.split('\ngcode:', 1)[1]
            gbody = re.split(r'\n[a-z_]+:', gbody)[0]
            # Klipper's config parser strips comment-only lines - so do we
            gbody = '\n'.join(l for l in gbody.splitlines()
                              if l.strip() and not l.lstrip().startswith('#'))
            try:
                out = render_body(gbody)
                rendered += 1
            except Exception:                      # noqa: BLE001
                skipped += 1
                ck('E must render %s:%s' % (fn, name),
                   name.strip() not in MUST_RENDER)
                continue
            for ln in out.splitlines():
                # ';' = g-code comment, '#' = config comment (Klipper strips
                # both - inline '#' IS legal inside macro bodies)
                cpos = ln.find(';')
                if cpos < 0:
                    cpos = ln.find('#')
                cmd = ln[:cpos if cpos >= 0 else None].strip()
                if not cmd:
                    continue
                word = cmd.split(' ', 1)[0]
                if RAW_LINE.match(word):
                    continue
                ck('E syntax %s:%s' % (fn, name), bool(EXT_LINE.match(cmd)),
                   cmd[:70])
    ck('E rendered a sane number', rendered > 100, '%d/%d' % (rendered,
                                                              skipped))

# ============================================================ summary =====
print()
print('=' * 70)
print('R140 STRESS: %d checks, %d generated files, %d FAIL'
      % (n_ck[0], len(gen_files), len(fails)))
for (name, info) in fails[:40]:
    print('  FAIL %-40s %s' % (name, info))
if len(fails) > 40:
    print('  ... and %d more' % (len(fails) - 40))
sys.exit(1 if fails else 0)
