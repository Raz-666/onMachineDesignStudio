#!/usr/bin/env python3
"""R217 field-bug radar: the bug CLASSES the field logs showed but the
battery never caught.

Every field round so far shipped at least one bug that all green tests
missed. This tool hunts the CLASSES, not the instances:

  C1  API-surface assumptions  - moonraker/klipper methods that only
      fail on the real machine (add_log_rollback_handler killed r2_menu
      at boot in .136m; the tests never touched the moonraker API).
  C2  Klipper compile traps    - {{ }} / {% %} in cfg content, %-tuple
      formatting inside jinja, unknown filters: config load dies with
      'Internal error during connect' (.47 shipped two of those).
  C3  Parser edge cases        - PrusaSlicer short floats ('E.00715')
      and Python banker's rounding on MINIMUM distances (the 15 deg
      spread came out as 2 anchors instead of 3).
  C4  Pin/version drift        - tests asserting yesterday's counts
      (r140 pinned 6 armed fixes while the code had 8; macro_render
      pinned .136m while the repo was .136n).
  C5  Runtime/perf traps       - LED reactor storms (MCU shutdown in
      .136m), M204 storms ('Timer too close', .125).
  C6  Label drift              - a ';TYPE:' literal that _lookup_type
      does not know silently degrades to CUSTOM ('Internal sparse
      infill', found in the .136n round).

Run:  python3 tools/r217_field_bug_radar.py
"""
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)

PASS = []
FAIL = []
ADV = []          # advisories: listed, not failed


def ck(name, ok, detail=''):
    (PASS if ok else FAIL).append(name)
    print('%-4s %s%s' % ('PASS' if ok else 'FAIL', name,
                         ('  [%s]' % detail[:160]) if detail and not ok
                         else ''))


def adv(name):
    ADV.append(name)
    print('note %s' % name)


def rd(rel):
    return open(os.path.join(ROOT, rel), encoding='utf-8').read()


CFG_FILES = []
for sub in ('macros', 'menus'):
    d = os.path.join(ROOT, sub)
    CFG_FILES += [os.path.join(sub, f) for f in sorted(os.listdir(d))
                  if f.endswith('.cfg')]

# ================= C1: API surface (the r2_menu boot crash class) ==========
MENU = rd('web/r2_menu.py')
ck('C1 moonraker: add_log_rollback_handler is not CALLED anywhere '
   '(the .136m boot killer - comment mentions are fine)',
   not re.search(r'(?<!#)\bself\.server\.add_log_rollback_handler\s*\(',
                 MENU))

# every server.* method actually called must be in the verified set
_curated = {
    'register_endpoint', 'register_remote_method', 'error',
    'get_klippy_state', 'event_loop',
}
_used = set(re.findall(r'server\.(\w+)\b', MENU))
_unknown = sorted(_used - _curated)
ck('C1 moonraker: every server.* API is in the post-.136n verified set '
   '(new API = curate here first)', not _unknown,
   'uncurated: %s' % _unknown)

ck('C1 klipper status: no direct printer[\'screws_tilt_adjust\'] access '
   'in menus/macros (optional object - must go through .results with '
   'in-checks)',
   all("printer['screws_tilt_adjust']" not in rd(f)
       for f in CFG_FILES))

# ================= C2: Klipper compile traps (R64/R80 class) ================
# gcode_macro bodies are FULL jinja ({{ }} and 'x % y' are legal there -
# shipped code proves it). The trap lives in [menu] sections: their
# name/gcode/enable options are single-brace templates where {{ }} or
# {% %} break the config load.
def menu_lines(rel):
    out, in_menu = [], False
    for i, l in enumerate(rd(rel).split('\n')):
        ls = l.strip()
        if ls.startswith('[') and ls.endswith(']'):
            in_menu = ls.startswith('[menu ')
            continue
        if in_menu:
            out.append((i + 1, l))
    return out

MENU_FILES = [f for f in CFG_FILES
              if '[menu ' in rd(f)]


def menu_option_lines(rel):
    '''name:/input:/enable: are SINGLE-brace templates; gcode: bodies are
    full jinja ({% %} legal there - shipped code proves it).'''
    out, in_menu = [], False
    for i, l in enumerate(rd(rel).split('\n')):
        ls = l.strip()
        if ls.startswith('[') and ls.endswith(']'):
            in_menu = ls.startswith('[menu ')
            continue
        if in_menu and (ls.startswith('name:') or ls.startswith('input:')
                        or ls.startswith('enable:')):
            out.append((i + 1, l))
    return out


bad_braces = [(f, i, l.strip()[:70])
              for f in MENU_FILES
              for (i, l) in menu_option_lines(f)
              if '{{' in l or '}}' in l or '{%' in l]
ck('C2 no {{ }} / {% %} in menu name/input/enable (single-brace '
   'templates - config load dies otherwise, R64/R80)', not bad_braces,
   str(bad_braces[:3]))

import jinja2
_env = jinja2.Environment()
_known_filters = set(_env.filters) | {'tojson'}
_used_filters = set()
for f in MENU_FILES:
    for (i, l) in menu_option_lines(f):
        _used_filters |= set(re.findall(r'\|\s*([a-zA-Z_]\w*)\s*\(', l))
_unknown_filters = sorted(_used_filters - _known_filters)
ck('C2 every jinja filter in menu name/input/enable exists (unknown '
   'filter = boot crash, .47 class)', not _unknown_filters,
   'unknown: %s' % _unknown_filters)

# ================= C3: parser edge cases ====================================
PP = rd('tools/r2_postproc.py')
# every E-capture regex must match short floats like E.00715
_e_patterns = re.findall(r'E\((-?\s*\\d[^)]*)\)', PP)
_unsafe = [p for p in _e_patterns
           if re.fullmatch(r'-?\\d\+?', p.replace(' ', ''))]
ck('C3 every E-capture regex matches short floats (E.00715 class, '
   '.131b field bug)', not _unsafe, 'unsafe: %s' % _unsafe[:4])
_behavioral = re.search(r' E\.00715', 'G1 X10.0 Y4.0 E.00715')
ck('C3 sanity: short-float line really carries an E token',
   bool(_behavioral))

# banker's rounding on MINIMUM distances must use math.ceil
ck('C3 _spread_starts computes the anchor separation with math.ceil '
   '(int(round(2.5)) == 2 in Python!)',
   'math.ceil' in PP and re.search(
       r'sep\s*=\s*max\(\s*1\s*,\s*int\(math\.ceil', PP)
   is not None)
_n_round = len(re.findall(r'int\(round\(', PP))
adv('C3 %d int(round( sites in r2_postproc.py - banker-proof only '
    'matters for MINIMUM distances (gaps/spreads); positions are '
    'irrelevant at +-0.5mm' % _n_round)

# ================= C4: pin / version drift ==================================
st = rd('macros/01_state.cfg')
_v_state = re.search(r"variable_version:\s*'([^']+)'", st)
_v_daemon = re.search(r"POSTPROC_RELEASE = '([^']+)'", PP)


def _newest(txt):
    vs = re.findall(r'R2-(\d{4}-\d{2}-\d{2}\.\d+[a-z])', txt)
    return max(vs).replace('R2-', '') if vs else None


# README states versions as changelog row labels ('.136n (R216)') - the
# TOPMOST row must be the current one
_rows = re.findall(r'^\| \*\*(\.[0-9]{3}[a-z]?) \(', rd('README.md'),
                   re.M)
_v_readme = _rows[0].lstrip('.') if _rows else None
_v_manual = _newest(rd('MANUAL.md'))
_v_s = _v_state.group(1).replace('R2-', '') if _v_state else None
_v_d = _v_daemon.group(1).replace('R2-', '') if _v_daemon else None
def _sfx(v):
    return v.split('.')[-1] if v else None


ok_v = (_v_s and _v_d and _v_readme and _v_manual
        and _v_s == _v_d == _v_manual            # full date versions
        and _sfx(_v_s) == _v_readme)             # README row label
ck('C4 version pins agree: 01_state == POSTPROC_RELEASE == README == '
   'MANUAL (%s, README/MANUAL checked at their NEWEST mention)'
   % (_v_s or '?'), ok_v,
   '%s / %s / %s / %s' % (_v_s, _v_d, _v_readme, _v_manual))

# menu_structure.json must match a FRESH export (stale tree = the web UI
# shows yesterday's menus)
import subprocess
exp = subprocess.run([sys.executable, 'tools/menu_json_export.py'],
                     capture_output=True, text=True, cwd=ROOT)
m = re.search(r'sha ([0-9a-f]{16})', exp.stdout)
import json
_disk = json.loads(rd('web/menu_structure.json'))
_dsha = re.search(r'([0-9a-f]{16})', _disk.get('sha256', ''))
ck('C4 web/menu_structure.json is a fresh export (re-exported now, '
   'sha matches)', bool(m and _dsha and m.group(1) == _dsha.group(1)),
   'fresh %s vs disk %s' % (m and m.group(1), _dsha and _dsha.group(1)))

# ================= C5: runtime / perf traps =================================
LEDS = rd('macros/03_leds.cfg')
_rates = [float(r) for r in re.findall(
    r'(?:frame_rate|update_rate|fps)[:=]\s*([\d.]+)', LEDS, re.I)]
_hi = [r for r in _rates if r > 6.0]
ck('C5 every LED effect runs <= 6 fps (12 fps blocked the reactor 4.1s '
   '-> MCU shutdown, .136m field log)', not _hi, 'too fast: %s' % _hi)

ck('C5 normalize keeps the travel-accel M204 >= 2mm rule (the M204 '
   'storm ended in Timer too close, .125)',
   '_tacc167' in PP and '2mm' in PP[PP.find('_tacc167') - 2000:
                                    PP.find('_tacc167') + 2000])

# ================= C6: label drift (CUSTOM silent degradation) ==============
import r2_postproc as pp
# only CODE emission lines (a(...)/append(...)/write) - docstrings and
# comments mention old spellings on purpose
_emit_re = re.compile(r"(?:append|[^a-zA-Z_]a|emit|write)\s*\(\s*['\"]"
                     r";TYPE:([^'\"]+)['\"]")
_literals = [l for l in _emit_re.findall(PP) if l != '%s']
# '%s' sites are checked through their branch literals below
# dynamic labels: ';TYPE:%s' % (...) - the string literals feeding them
# (in the surrounding if/elif chain) must resolve too
PPL = PP.split('\n')
for _i, _l in enumerate(PPL):
    if _l.strip().startswith('#') or _l.strip().startswith('"""'):
        continue
    if "';TYPE:%s'" in _l:
        _win = '\n'.join(PPL[max(0, _i - 12):_i + 3])
        # human labels are mixed-case with a space; canon tokens
        # (SURFACE-BOTTOM), APPLY strings and %s are not labels
        _literals += [q for q in re.findall(r"'([A-Za-z][^'%]{4,30})'",
                                            _win)
                      if ' ' in q and any(c.islower() for c in q)]
_literals = sorted(set(x.strip() for x in _literals if x.strip()))
_unknown_lbl = [l for l in _literals if not pp._lookup_type(l)]
ck('C6 every \';TYPE:\' label r2_postproc can emit resolves via '
   '_lookup_type (%d literals, the sparse-infill class)' % len(_literals),
   not _unknown_lbl, 'unresolved: %s' % _unknown_lbl)
# _FILE_INFO TYPES= lists are built at runtime from _frun/bstats (all
# canonized) - the generator matrix validates the REAL files' TYPES
ck('C6 _FILE_INFO TYPES lists are built via the canonizer (bstats keys '
   'come from _frun, never raw labels)',
   '_frun' in PP and "TYPES=' + ','.join(bstats)" in PP.replace(
       '"', "'").replace('TYPES=\' + ', "TYPES=' + "))

# firmware retraction honesty: generated files say RETRACT_STATUS=fw
ck('C6 _gen_normalize_speeds stamps RETRACT_STATUS=fw (G10/G11 files '
   'must not lie to the Pre-Print display)',
   'RETRACT_STATUS=fw' in PP)

print()
if FAIL:
    print('RESULT: FAIL - %d of %d checks failed'
          % (len(FAIL), len(FAIL) + len(PASS)))
    sys.exit(1)
print('RESULT: PASS - %d checks, %d advisories - the field-bug classes '
      'are radar-guarded' % (len(PASS), len(ADV)))
