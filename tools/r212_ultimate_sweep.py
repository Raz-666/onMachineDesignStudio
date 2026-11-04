#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""R212 (.136k): THE ULTIMATE SWEEP - the field-ordered deep audit.

User order (.136j field log): 'mach noch mal ein ultimativen Gesamttest
mit allen Test-Tools ... und intensiviere sie. Schau dir wirklich
strukturiert unseren Systemaufbau an und arbeite dich Schicht fuer
Schicht durch saemtliche Makros, Tools, Generatoren, Python-Skripte.
Und mach ein intensives Syntax- sowie String-Test fuer alle verwendeten
Coding-Sprachen und jede einzelne Zeile. Schau ob irgendwo Befehle,
Skripte, Makros still sterben. Teste die Generatoren mit saemtlichen
Parametern und Kombinationen diverser Generatoren und Tools.'

Layers of THIS sweep (each check names its layer):
  1  SYNTAX   every file through its REAL compiler - python (ast.parse
              = every single line), shell (bash -n), JavaScript
              (node --check on the shipped page script), JSON (json.load)
  2  STRINGS  encoding (utf-8), mixed line endings, smart quotes in code
              (the chr(39) class), jinja brace balance in the menu cfg
  3  DEAD     the silent-death scan: every command word the menus can
              send must be a defined macro or a known klipper builtin -
              a dead button is the worst failure mode a menu can have;
              plus orphan macros (defined, never referenced) as info
  4  CHAINS   generator x generator x tool combinations (label->range,
              stringart->range, label->texture->range, ties->range) -
              every stage tagged, Mainsail-meta'd, sane
  5  PREPRINT the field-named G-code classes through the REAL tagger:
              supports, multiple objects on one plate, vase mode,
              by-layer, by-object, a kitcard (many connected parts that
              count as ONE object), texture output (idempotency)

Exit 0 = the system is clean. 0 FAIL tolerance, same as the whole suite.
"""
import ast
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)

N = [0]
FAILS = []


def check(name, cond, detail=''):
    N[0] += 1
    if cond:
        print('PASS  %s' % name)
    else:
        FAILS.append(name)
        print('FAIL  %s  %s' % (name, str(detail)[:200]))


def info(msg):
    print('  [i] %s' % msg)


# =========================================================== 1  SYNTAX ====
print('== 1  SYNTAX: every file through its real compiler ==')
_py = sorted(
    os.path.join(HERE, f) for f in os.listdir(HERE) if f.endswith('.py'))
_py.append(os.path.join(ROOT, 'web', 'r2_menu.py'))
_bad = []
for p in _py:
    try:
        ast.parse(open(p, encoding='utf-8').read(), filename=p)
    except SyntaxError as e:
        _bad.append('%s:%d %s' % (os.path.basename(p), e.lineno or 0,
                                  e.msg))
check('SYNTAX python: %d tools + component parse (every line compiled)'
      % len(_py), not _bad, str(_bad[:3]))

_sh = []
for sub in (ROOT, HERE, os.path.join(ROOT, 'web')):
    for f in sorted(os.listdir(sub)):
        if f.endswith('.sh'):
            _sh.append(os.path.join(sub, f))
_bad = []
for p in _sh:
    r = subprocess.run(['bash', '-n', p], capture_output=True, text=True)
    if r.returncode != 0:
        _bad.append('%s: %s' % (os.path.basename(p),
                                r.stderr.strip()[:90]))
check('SYNTAX shell: %d scripts pass bash -n' % len(_sh),
      not _bad, str(_bad[:3]))

# R221 (external audit finding): klipper's parser MERGES duplicate sections
# silently - a doubled tail in 08_print_start_stop.cfg (the re-created R117
# commit fell to snapshot truncation) shipped unnoticed from .89 to .136r
# because both copies were identical. The battery's cfg parsers were regex/
# template based and never counted sections. This census is strict: every
# section in every cfg exactly once, or FAIL.
import glob as _gb221                                       # noqa: E402
import re as _re221                                         # noqa: E402
_cfg221 = sorted(_gb221.glob(os.path.join(ROOT, 'macros', '*.cfg'))
                 + _gb221.glob(os.path.join(ROOT, 'menus', '*.cfg')))
_dup221, _nsec221 = [], 0
for _p221 in _cfg221:
    _seen221 = {}
    for _i221, _l221 in enumerate(open(_p221, encoding='utf-8'), 1):
        _m221 = _re221.match(r'^\s*\[([^\]]+)\]', _l221)
        if _m221:
            _nsec221 += 1
            if _m221.group(1) in _seen221:
                _dup221.append('%s [%s] lines %d+%d'
                               % (os.path.basename(_p221), _m221.group(1),
                                  _seen221[_m221.group(1)], _i221))
            _seen221[_m221.group(1)] = _i221
check('SYNTAX cfg: %d sections in %d config files, every section '
      'exactly once (klipper merges duplicates silently - the .89->.136r '
      'doubled 08 tail shipped for 40+ releases while the battery was green)'
      % (_nsec221, len(_cfg221)),
      not _dup221, str(_dup221[:3]))

_html = open(os.path.join(ROOT, 'web', 'index.html'),
             encoding='utf-8').read()
_js = _html.rsplit('<script>', 1)[1].rsplit('</script>', 1)[0]
_jf = tempfile.NamedTemporaryFile('w', suffix='.js', delete=False)
_jf.write(_js)
_jf.close()
_r = subprocess.run(['node', '--check', _jf.name],
                    capture_output=True, text=True)
os.unlink(_jf.name)
check('SYNTAX javascript: the SHIPPED page script parses in node '
      '(every line - the .136 lesson: a syntax error killed the page '
      'for 9 releases while slice tests were green)',
      _r.returncode == 0, _r.stderr.strip()[-160:])

_jsons = [os.path.join(ROOT, 'web', 'menu_structure.json')]
if os.path.exists(os.path.join(ROOT, 'watch_state.json')):
    _jsons.append(os.path.join(ROOT, 'watch_state.json'))
_bad = []
for p in _jsons:
    try:
        json.load(open(p, encoding='utf-8'))
    except Exception as e:                                     # noqa: BLE001
        _bad.append('%s: %r' % (os.path.basename(p), e))
check('SYNTAX json: %d data files parse' % len(_jsons), not _bad,
      str(_bad))

# ========================================================== 2  STRINGS ====
print('== 2  STRINGS: encoding, endings, smart quotes, brace balance ==')
_code_ext = ('.py', '.sh', '.cfg', '.js')
_text = []
for sub in ('tools', 'web', 'macros', 'menus'):
    d = os.path.join(ROOT, sub)
    for f in sorted(os.listdir(d)):
        if f.endswith(_code_ext):
            _text.append(os.path.join(d, f))
for f in ('setup.sh', 'update.sh'):
    p = os.path.join(ROOT, f)
    if os.path.exists(p):
        _text.append(p)
_bad = []
for p in _text:
    raw = open(p, 'rb').read()
    try:
        raw.decode('utf-8')
    except UnicodeDecodeError as e:
        _bad.append('%s: %r' % (os.path.basename(p), e))
check('STRINGS encoding: %d code files are clean utf-8' % len(_text),
      not _bad, str(_bad[:3]))

_bad = [os.path.basename(p) for p in _text
        if b'\r\n' in open(p, 'rb').read()]
check('STRINGS line endings: no CRLF in any code file', not _bad,
      str(_bad[:5]))

_SMART = '\u201e\u201c\u201d\u2018\u2019`'
_bad = []
for p in _text:
    # python/js may use German typography INSIDE display strings (the PDF
    # builders do, deliberately); .sh and .cfg CODE lines construct
    # COMMANDS - a smart quote there breaks them silently (chr(39) class)
    if not p.endswith(('.sh', '.cfg')):
        continue
    for i, line in enumerate(open(p, encoding='utf-8'), 1):
        if line.lstrip().startswith(('#', ';')):
            continue
        for ch in _SMART:
            if ch in line:
                _bad.append('%s:%d smart quote %r'
                            % (os.path.basename(p), i, ch))
                break
check('STRINGS smart quotes: no unicode quotes in shell commands or cfg '
      'CODE lines (the chr(39) class - they silently break command '
      'construction)', not _bad, str(_bad[:4]))


def _brace_balance(line):
    """{ } balance outside single/double-quoted strings (jinja values)."""
    n = 0
    q = None
    k = 0
    while k < len(line):
        c = line[k]
        if q:
            if c == '\\':
                k += 2
                continue
            if c == q:
                q = None
        elif c in ('"', "'"):
            q = c
        elif c == '{':
            n += 1
        elif c == '}':
            n -= 1
        k += 1
    return n


_bad = []
for cfgp in (os.path.join(ROOT, 'menus'), os.path.join(ROOT, 'macros')):
    for f in sorted(os.listdir(cfgp)):
        if not f.endswith('.cfg'):
            continue
        # cfg values are LINE-oriented (a quote must close on its line)
        # but jinja set/if blocks span lines -> the RUNNING sum of the
        # per-line deltas must return to zero at EOF
        run = 0
        for line in open(os.path.join(cfgp, f), encoding='utf-8'):
            run += _brace_balance(line)
        if run != 0:
            _bad.append('%s: net %d brace(s)' % (f, run))
check('STRINGS braces: jinja { } balanced in menus + macros (line-'
      'oriented quotes, multi-line set/if blocks via the running sum)',
      not _bad, str(_bad[:4]))

# ============================================================ 3  DEAD =====
print('== 3  DEAD: the silent-death scan (menu buttons must fire) ==')
_defined = set()
for f in sorted(os.listdir(os.path.join(ROOT, 'macros'))):
    if f.endswith('.cfg'):
        _defined |= set(re.findall(
            r'^\[gcode_macro\s+([\w]+)\]',
            open(os.path.join(ROOT, 'macros', f), encoding='utf-8').read(),
            re.M))
_BUILTIN = {
    'RESPOND', 'SAVE_VARIABLE', 'SET_GCODE_VARIABLE', 'M117', 'M118',
    'PRINT', 'SD_PRINT_FILE', 'CANCEL_PRINT', 'PAUSE', 'RESUME',
    'SAVE_CONFIG', 'RESTART', 'FIRMWARE_RESTART', 'TURN_OFF_HEATERS',
    'SET_PRESSURE_ADVANCE', 'SET_VELOCITY_LIMIT', 'SET_INPUT_SHAPER',
    'SET_HEATER_TEMPERATURE', 'SET_FAN_SPEED', 'Z_TILT_ADJUST',
    'BED_MESH_CALIBRATE', 'BED_MESH_CLEAR', 'BED_MESH_PROFILE_LOAD',
    'QUERY_FILAMENT_SENSOR', 'SET_FILAMENT_SENSOR', 'SET_DISPLAY_GROUP',
    'SET_GCODE_ODOMETER', 'INIT_DISPLAY', 'M84', 'M18', 'M17',
    'SDCARD_RESET_FILE', 'SDCARD_PRINT_FILE', 'GET_POSITION',
    'SAVE_GCODE_STATE', 'RESTORE_GCODE_STATE', 'SET_RETRACTION',
    'EXCLUDE_OBJECT_DEFINE', 'EXCLUDE_OBJECT', 'SET_OBJECT',
    'SET_LED_LAYOUT', 'NOZZLE_LED', 'Z_OFFSET_APPLY_ENDSTOPS',
    'Z_OFFSET_APPLY_PROBE', 'TESTZ', 'ACCEPT', 'ABORT', 'SET_KINEMATICS',
    'SET_GCODE_OFFSET', 'UPDATE_DELAYED_GCODE', 'SET_PIN', 'SET_DIGITAL',
    'SET_SERVO', 'M117', 'M220', 'M221', 'G4', 'M400',
}
_doc = json.load(open(os.path.join(ROOT, 'web', 'menu_structure.json')))
_cmds = set()


def _walk_dead(n):
    for gline in (n.get('gcode') or []):
        l = re.sub(r'\{%-?\s.*?\s*-?%\}', ' ', gline)      # strip blocks
        l = re.sub(r'\{[^{}]*\}', ' ', l)                  # strip exprs
        for tok in l.split():
            if re.match(r'^[GMT]\d+$', tok.upper()):
                break                                       # builtin G/M/T
            if re.match(r'^[A-Za-z_]\w*$', tok):
                _cmds.add((tok, n['id']))
            break                                           # first word only
    for c in (n.get('children') or []):
        _walk_dead(c)


_walk_dead(_doc['tree'])
_dead = sorted(c for c in _cmds
               if c[0] not in _defined and c[0].upper() not in _BUILTIN
               and c[0].upper() not in _defined)
check('DEAD menu->macro: every command word the menus can send is a '
      'defined macro or klipper builtin (%d commands checked) - a dead '
      'button dies SILENTLY, the worst class there is'
      % len(set(c[0] for c in _cmds)),
      not _dead, str(_dead[:6]))

_allsrc = ''
for sub in ('macros', 'menus', 'tools', 'web'):
    d = os.path.join(ROOT, sub)
    for f in sorted(os.listdir(d)):
        if f.endswith(('.cfg', '.py', '.html', '.sh', '.json')):
            try:
                _allsrc += open(os.path.join(d, f), encoding='utf-8').read()
            except (OSError, UnicodeDecodeError):
                pass
_orphans = sorted(m for m in _defined
                  if _allsrc.count(m) < 2
                  and not m.startswith('_'))
info('orphan macros (defined but never referenced - internals excluded): '
     '%d %s' % (len(_orphans), _orphans[:6]))

# ========================================================== 4  CHAINS ====
print('== 4  CHAINS: generator x generator x tool combinations ==')
import r2_postproc as pp                                    # noqa: E402
import gcode_meta                                           # noqa: E402
from r2_texture import apply_texture                        # noqa: E402
BED = (0.0, -3.0, 220.0, 217.0)
D = tempfile.mkdtemp(prefix='r212_')
try:
    lab = pp.make_labels(['CH1'], bed=BED, out_dir=D)[0]
    pp._meta_finalize(lab)              # what the daemon scan does in the field
    _lt = open(lab).read()
    _lthumb = _lt[_lt.index('; thumbnail begin'):
                  _lt.index('; thumbnail end')]
    _ltime = re.search(r'printing time \(normal mode\) = (.+)', _lt)
    rng, nl = pp.make_range(lab, 2, 4)  # the meta hook runs INSIDE (R212)
    _rt = open(rng).read()
    _rtime = re.search(r'printing time \(normal mode\) = (.+)', _rt)
    check('CHAIN label->range: excerpt exists, %d layers, Mainsail meta '
          'with the SOURCE thumbnail, hook inside make_range' % nl,
          os.path.isfile(rng) and nl >= 1
          and '; thumbnail begin' in _rt
          and 'estimated printing time' in _rt
          and _lthumb in _rt                    # the source thumbnail
          and _ltime and _rtime
          and _rtime.group(1) != _ltime.group(1),   # own honest time
          'thumb=%s own-time=%s'
          % (_lthumb in _rt, _rtime.group(1) if _rtime else '-'))

    art = pp.make_string_art(pattern='SPIRAL', diameter=100.0,
                             anchors=60, out_dir=D)
    if isinstance(art, tuple):
        art = art[0]
    art = art[0] if isinstance(art, list) else art
    rng2, nl2 = pp.make_range(art, 2, 4)   # hook inside
    check('CHAIN stringart->range: procedural art excerpted (%d layers), '
          'meta added' % nl2,
          os.path.isfile(rng2) and nl2 >= 1
          and 'thumbnail begin' in open(rng2).read(), 'chain B broken')

    lab3 = pp.make_labels(['CH3'], bed=BED, out_dir=D)[0]
    _texdir = os.path.join(D, 'texture')
    os.makedirs(_texdir, exist_ok=True)   # watch() pre-creates gen folders
    tex, tinfo = apply_texture(lab3, out_dir=_texdir,
                               mode='BUMPS', bed=BED)
    rng3, nl3 = pp.make_range(tex, 2, 3)   # hook inside
    check('CHAIN label->texture->range: 3-stage pipeline - textured '
          'variant exists (%s), excerpt %d layers, meta added'
          % (tinfo.get('mode'), nl3),
          os.path.isfile(tex) and os.path.isfile(rng3) and nl3 >= 1
          and 'thumbnail begin' in open(rng3).read(), 'chain C broken')

    ties = pp.make_cable_ties(count=4, length=90.0, out_dir=D)
    if isinstance(ties, tuple):
        ties = ties[0]
    ties = ties[0] if isinstance(ties, list) else ties
    rng4, nl4 = pp.make_range(ties, 2, 4)  # hook inside
    check('CHAIN ties->range: cable-tie plate excerpted (%d layers), '
          'meta added' % nl4,
          os.path.isfile(rng4) and nl4 >= 1
          and 'thumbnail begin' in open(rng4).read(), 'chain D broken')
finally:
    shutil.rmtree(D, ignore_errors=True)

# ======================================================= 5  PREPRINT =====
print('== 5  PREPRINT: the field-named G-code classes through the tagger ==')
D = tempfile.mkdtemp(prefix='r212pp_')


def gcode(body, header='; generated by OrcaSlicer 2.2.0\n;FLAVOR:Marlin\n'
                        'M83\n'):
    return header + body


def layers(n, types, objects=1, vase=False):
    """Realistic orca-shaped layer stack: ;LAYER + ;Z: comments, one
    ;TYPE block per feature. First layers never carry a top surface (a
    real slicer cannot put one there - the S4 sequence audit is right to
    complain). objects>1 = by-object printing: each object restarts at
    Z0.2, so the ;Z: values fall > 1 mm - the system's by-object proof."""
    out = []
    for o in range(objects):
        z = 0.2
        for i in range(n):
            out.append(';LAYER:%d' % (o * n + i))
            out.append(';Z:%.2f' % z)
            out.append('G1 Z%.2f F600' % z)
            for t, spell in types:
                if spell == 'Top surface' and i == 0:
                    continue          # layer 1 has no top surface, ever
                out.append(';TYPE:%s' % spell)
                out.append('G1 X10 Y10 E.2 F600')
                out.append('G1 X50 Y10 E.3 F600')
                out.append('G1 X50 Y50 E.3 F600')
            if vase:
                out.append('G1 X10 Y60 E.3 F600')   # spiral continues
            z += 0.2
    return '\n'.join(out) + '\n'


def vase_layers(n):
    """Vase mode: one continuous outer-wall spiral, ;LAYER comments on
    every revolution (that is what orca emits), no per-layer type blocks.
    """
    out = []
    for i in range(n):
        out.append(';LAYER:%d' % i)
        out.append(';Z:%.2f' % (0.2 + 0.2 * i))
        out.append('G1 Z%.2f F600' % (0.2 + 0.2 * i))
        out.append(';TYPE:Outer wall')
        out.append('G1 X10 Y10 E.3 F600')
        out.append('G1 X60 Y10 E.6 F600')
        out.append('G1 X60 Y60 E.6 F600')
        out.append('G1 X10 Y60 E.6 F600')
    return '\n'.join(out) + '\n'


ORCA = [('WALL-OUTER', 'Outer wall'), ('WALL-INNER', 'Inner wall'),
        ('INFILL-SPARSE', 'Sparse infill'), ('SURFACE-TOP', 'Top surface')]


def objs(n):
    return '\n'.join('EXCLUDE_OBJECT_DEFINE NAME=obj%d CENTER=50,50'
                     % i for i in range(n)) + '\n'


def run_case(name, path, exp_layers, exp_byobj, exp_types):
    s = pp.process(path)
    txt = open(path, encoding='utf-8').read()
    m = re.search(r'TYPES=([^ ]*)', txt)
    got = set(m.group(1).replace('|', ',').split(',')) if m else set()
    got = {g.strip() for g in got if g.strip()}
    s2 = pp.process(path)
    check('PREPRINT %s: layers=%d by_object=%s TYPES=%s, idempotent'
          % (name, exp_layers, exp_byobj, sorted(exp_types)),
          (not s['skipped']) and s['layers'] == exp_layers
          and bool(s['by_object']) == exp_byobj
          and got == set(exp_types) and s2['skipped'],
          'layers=%r by_object=%r types=%r skipped2=%r'
          % (s.get('layers'), s.get('by_object'), sorted(got),
             s2.get('skipped')))


try:
    p1 = os.path.join(D, 'supports.gcode')
    open(p1, 'w').write(gcode(
        objs(1) + layers(6, ORCA + [('SUPPORT', 'Support material'),
                                    ('SUPPORT', 'Support material '
                                                'interface')])))
    # single object: EXCLUDE_OBJECT_DEFINE data alone is NOT by-object
    # proof - only ;Z: falls (or object changes in the Z scan) are
    run_case('supports', p1, 6, False,
             {'WALL-OUTER', 'WALL-INNER', 'INFILL-SPARSE', 'SURFACE-TOP',
              'SUPPORT'})

    p2 = os.path.join(D, 'multi.gcode')
    # 7 layers per object = 1.4 mm tall: the ;Z: fall back to 0.2 is
    # 1.2 mm - safely over the 1.0 mm by-object proof threshold
    open(p2, 'w').write(gcode(objs(4) + layers(7, ORCA, objects=4)))
    run_case('multi-object plate (printed by object)', p2, 28, True,
             set(x[0] for x in ORCA))

    p3 = os.path.join(D, 'vase.gcode')
    open(p3, 'w').write(gcode(vase_layers(20)))
    run_case('vase mode', p3, 20, False, {'WALL-OUTER'})

    p4 = os.path.join(D, 'bylayer.gcode')
    open(p4, 'w').write(gcode(layers(8, ORCA + [('BRIDGE', 'Bridge')])))
    run_case('by-layer classic', p4, 8, False,
             set(x[0] for x in ORCA) | {'BRIDGE'})

    # kitcard: MANY connected parts, but ONE object (one EXCLUDE_OBJECT_
    # DEFINE) - the tagging must not split it and must see the bridge
    # ribs that hold the parts together
    p5 = os.path.join(D, 'kitcard.gcode')
    open(p5, 'w').write(gcode(objs(1) + layers(7, ORCA + [
        ('BRIDGE', 'Bridge'), ('GAPS', 'gap fill')])))
    run_case('kitcard (one object, many parts)', p5, 7, False,
             set(x[0] for x in ORCA) | {'BRIDGE', 'GAPS'})

    # texture output through the tagger again: generated files carry TAG,
    # the second pass must SKIP (never double-tag a derived file)
    labt = pp.make_labels(['TEX'], bed=BED, out_dir=D)[0]
    s = pp.process(labt)
    check('PREPRINT texture/generated: already tagged - the watcher '
          'scanner SKIPS (no double-tagging of derived files)',
          s['skipped'], 'generated file was re-tagged')
finally:
    shutil.rmtree(D, ignore_errors=True)

# =========================================================== summary ======
print()
if FAILS:
    print('R212 ULTIMATE SWEEP: %d checks, %d FAIL' % (N[0], len(FAILS)))
    for f in FAILS:
        print('  -', f)
    sys.exit(1)
print('R212 ULTIMATE SWEEP: %d checks, 0 FAIL - syntax, strings, dead '
      'commands, chains and pre-print classes all clean' % N[0])
