#!/usr/bin/env python3
# R240 (.136aj) field check - the start blocker + the master-prompt round:
#
#  1) THE START BLOCKER (.136ai field log): 6x 'Malformed command
#     '_M204_SET VALUE=8000'' right after the probe-safe prime line, then
#     'Printer reported an ERROR' - no print ever started. Root cause (down
#     to klippy/gcode.py): the dispatcher builds command names from [A-Z_]
#     ONLY - digits END a name. '_M204_SET VALUE=8000' parses as cmd '_M204'
#     with rawparams '_SET VALUE=8000'; the R237 _M204 alias dispatched it,
#     shlex choked on the '='-less token '_SET' and raised a FATAL
#     'Malformed command' (echoed once per macro nesting level = 6x).
#     Before R237 the same line only produced a harmless 'Unknown command'.
#     Fix: _ACCEL_SET (digit-free), alias removed, both tools rewrite both
#     legacy forms, and THIS battery simulates the klipper tokenizer over
#     every macro name so the class of bug can never ship again.
#  2) The master prompt: ONE Depot profile (ALL Pre-Print values incl.
#     inactive ones + Z-hop + drive), max ONE 'pre' profile per file, the
#     optimized copy's post-print tuning becomes its NEW pre profile
#     (original keeps its own), auto-load with confirmation beep, ironing
#     FLOW quick value (15-20% typical instead of the stiff 100% speed),
#     Live mirrors Pre-Print Motion, per-job LED progress bar, every
#     long-unclear action double-press + sound + menu exit.
import json
import os
import re
import sys

here = os.path.dirname(os.path.abspath(__file__))
ok = 0
fails = 0


def check(name, cond, detail=''):
    global ok, fails
    if cond:
        ok += 1
        print('  ok   %s' % name)
    else:
        fails += 1
        print('  FAIL %s  [%s]' % (name, detail))


def rd(*p):
    return open(os.path.join(here, *p), encoding='utf-8').read()


print('--- A) the start blocker: _M204_SET -> _ACCEL_SET ----------------')
m06 = rd('..', 'macros', '06_temp_controls.cfg')
m12 = rd('..', 'macros', '12_maintenance.cfg')
allmacros = '\n'.join(rd('..', 'macros', f)
                      for f in sorted(os.listdir(os.path.join(here, '..', 'macros')))
                      if f.endswith('.cfg'))
check('A1: _ACCEL_SET exists, _M204_SET and the _M204 alias are GONE',
      '[gcode_macro _ACCEL_SET]' in m06
      and '[gcode_macro _M204_SET]' not in allmacros
      and '[gcode_macro _M204]' not in allmacros
      and 'M204 {rawparams}' not in m06, '')
check('A2: both _NOZZLE_WIPE call sites use _ACCEL_SET',
      '_M204_SET' not in m12 and m12.count('_ACCEL_SET VALUE=') == 2, '')

# --- A3: functional - the segfix rewrites _M204_SET lines too -----------
sys.path.insert(0, here)
import tempfile                                     # noqa: E402
import r2_postproc                                 # noqa: E402
td = tempfile.mkdtemp(prefix='r240_')
fx = os.path.join(td, 'blk.gcode')
open(fx, 'w').write(
    'PRINT_START BED=60 HOTEND_FIRST=225 MATERIAL=PLA\n'
    '_M204_SET VALUE=8000\n'
    '_M204 S3000\n'
    'G1 X10.000 Y10.000 E1.00000\n'
    'G1 X10.050 Y10.000 E1.00005\n'
    'G1 X10.100 Y10.000 E1.00010\n')
n240, rb, ra, m2 = r2_postproc._segments_fix_file(fx)
t240 = open(fx).read()
check('A3: segment fix rewrites BOTH legacy forms (Malformed lines die)',
      m2 == 2 and '_M204' not in t240
      and 'M204 S8000' in t240 and 'M204 S3000' in t240,
      'm2=%r' % m2)

# --- A4: THE klipper tokenizer simulation (never again an unparseable name)
# klippy/gcode.py:  args_r = re.compile('([A-Z_]+|[A-Z*])')
#                   parts = args_r.split(line.upper())
#                   cmd = ''.join(parts[:3]).strip()
# An extended command is only safe when the tokenizer reconstructs EXACTLY
# the written word - digits after a letter/underscore would split the name.
ARGS_R = re.compile('([A-Z_]+|[A-Z*])')


def klipper_cmd(line):
    parts = ARGS_R.split(line.upper())
    if ''.join(parts[:2]) == 'N':
        return ''.join(parts[3:5]).strip()
    return ''.join(parts[:3]).strip()


# macros that are only ever READ as status (never dispatched) may carry digits
never_dispatched = set()
for m in re.finditer(r'^\[gcode_macro (_\w+)\]', allmacros, re.M):
    name = m.group(1)
    if klipper_cmd(name) != name:
        never_dispatched.add(name)
whitelist = {n for n in never_dispatched
             if re.match(r'^_(V\d\d_|R2_VERSION)', n)}
# R253: _R2_DOCTOR is the deliberately kept dead alias of DOCTOR_PACK -
# defined so nothing written against R252 breaks, never dispatched (a
# call would be mangled by the tokenizer, exactly this check's point)
whitelist.add('_R2_DOCTOR')
check('A4a: every digit-named macro is a status-only one (whitelisted)',
      never_dispatched == whitelist, str(never_dispatched - whitelist))

# every dispatched word in macro bodies + menu gcode lines must survive the
# tokenizer unchanged (traditional M117/G1 & params are fine - only the
# FIRST word matters)
dispatch_bad = []
for fname in sorted(os.listdir(os.path.join(here, '..', 'macros'))):
    if not fname.endswith('.cfg'):
        continue
    for line in rd('..', 'macros', fname).split('\n'):
        s = line.strip()
        # field-proven style: trailing '#' / ';' comments behind a command -
        # cut them like the field klippy does before the tokenizer looks
        for _c240 in ('#', ';'):
            _p240 = s.find(_c240)
            if _p240 > 0:
                s = s[:_p240].rstrip()
        if (not s or s.startswith('#') or s.startswith(';')
                or ':' in s.split(' ')[0] or s.startswith('{')
                or s.startswith('%')):
            continue
        w = s.split(' ')[0]
        if not re.match(r'^[A-Z_]+$', w):
            continue                          # values, comments, Jinja
        if klipper_cmd(s) != w:
            dispatch_bad.append((fname, w))
lcdtxt = rd('..', 'menus', 'lcd_menues.cfg')
for line in lcdtxt.split('\n'):
    s = line.strip()
    for _c240 in ('#', ';'):
        _p240 = s.find(_c240)
        if _p240 > 0:
            s = s[:_p240].rstrip()
    if not s or s.startswith('#') or s.startswith(('name:', 'enable:', 'type:',
                                                   'input', 'gcode:', '[')):
        continue
    w = s.split(' ')[0]
    if not re.match(r'^[A-Z_]+$', w):
        continue
    if klipper_cmd(s) != w:
        dispatch_bad.append(('lcd_menues.cfg', w))
check('A4b: no dispatched command gets mangled by the klipper tokenizer',
      not dispatch_bad, str(dispatch_bad[:4]))

# --- A5: the _M204_SET probe would have been caught -----------------------
check('A5: the simulator catches the .136ai blocker (regression proof)',
      klipper_cmd('_M204_SET VALUE=8000') == '_M204'
      and klipper_cmd('_ACCEL_SET VALUE=8000') == '_ACCEL_SET', '')

print('--- B) the Depot profile + one profile per file -------------------')
m05 = rd('..', 'macros', '05_materials.cfg')
check('B1: SAVE/LOAD/DELETE_DEPOT_PRESET + DEPOT_INFO + _PROF_ARM exist',
      all('[gcode_macro %s]' % n in m05 for n in
          ('SAVE_DEPOT_PRESET', 'LOAD_DEPOT_PRESET', 'DELETE_DEPOT_PRESET',
           'DEPOT_INFO', '_PROF_ARM')), '')
check('B2: the snapshots carry Z-hop + drive (BOTH builders)',
      m05.count("'zh_on': sv.zh_on|default(False), 'zh_height':") == 2
      and m05.count("'drive': sv.ov_drive|default('direct')|string,") == 2, '')
check('B3: _PROFILE_APPLY knows SRC=depot and applies zh/drive (old '
      'profiles keep their values)',
      "params.SRC|default('') == 'depot'" in m05
      and "{% if 'zh_on' in d %}" in m05
      and "{% if 'drive' in d %}" in m05, '')
check('B4: _PROFILE_WRITE writes the depot (WHICH=depot branch)',
      "which == 'depot'" in m05
      and 'SAVE_VARIABLE VARIABLE=depot_preset VALUE="{d}"' in m05, '')
check('B5: FILE_PROFILE_AUTO confirms with sound + M117',
      'M117 Profile: loaded' in m05
      and m05.find('M117 Profile: loaded')
      > m05.find("RESPOND MSG=\"[i] File profile '{which}' applied"), '')
check('B6: the 2-press idiom guards every profile action',
      m05.count("gen_arm|default('') != 'p") == 6, '')
check('B7: LCD Profiles: Depot rows + no mat/def/file blocks',
      all('[menu __main __preprint __profs __%s]' % c in lcdtxt for c in
          ('sd', 'sf', 'ld', 'lf', 'dd', 'ap', 'df'))
      and '[menu __main __preprint __profs __mat]' not in lcdtxt
      and '[menu __main __preprint __profs __def]' not in lcdtxt
      and '[menu __main __preprint __profs __file]' not in lcdtxt, '')
check('B8: material quick templates live in Pre-Print > Material',
      lcdtxt.count('SAVE_MATERIAL_TEMPS MATERIAL=') == 5
      and '[menu __main __preprint __material __m0 __save]' in lcdtxt
      and '[menu __main __preprint __material __m4 __reset]' in lcdtxt, '')

# --- B9: functional - the optimized copy registers its 'pre' profile -----
pp = rd('r2_postproc.py')
check('B9: the opt job registers the copy\'s pre profile (watcher)',
      '_opt_snap_from_file(' in pp
      and "VALUE=%s' % (_ep240, repr(_fp240), _dest169)" in pp
      .replace("VALUE=%s'\n"
               "                                        'VALUE=%s'\n", 'X')
      or ("_fp240[_dest169] = {" in pp and "'pre': _snap240" in pp), '')

print('--- C) ironing FLOW quick value -----------------------------------')
check('C1: the quick row is the IRONING FLOW (default 15, range 5-100)',
      "name: IR fl: {'%3d' % menu.input}%" in lcdtxt
      and 'SET_OVERRIDE_VALUE NAME=ironing_flow VALUE={menu.input|round|int}'
      in lcdtxt, '')
check('C2: no stiff default(100) ironing flow left in the menus',
      'ov_ironing_flow|default(100)' not in lcdtxt
      and lcdtxt.count('ov_ironing_flow|default(15)') == 5, '')
check('C3: Pre-Print > Features > Ironing carries the Flow row',
      '[menu __main __preprint __feat __ir __fl]' in lcdtxt, '')

print('--- D) Live mirrors Pre-Print Motion -------------------------------')
# R250 (user decision B1) superseded the R240 layout: the four quick
# lists are SIBLINGS at the Live top level again - no Motion detour.
check('D1: the quick lists are Live top-level siblings (R250 B1, the '
      'R240 inside-Motion layout was superseded)',
      '[menu __main __live __spfe]' in lcdtxt
      and '[menu __main __live __acfe]' in lcdtxt
      and '[menu __main __live __pafe]' in lcdtxt
      and '[menu __main __live __flfe]' in lcdtxt
      and '[menu __main __live __lmo __vel __spfe]' not in lcdtxt
      and '[menu __main __live __lmo __extr __pafe]' not in lcdtxt, '')
live_l1 = re.findall(r'^\[menu __main __live (\w+)\]$', lcdtxt, re.M)
check('D2: Live order - temps, Z-hop above the babysteps, the four quick '
      'lists, then Motion',
      live_l1[:12] == ['__temp', '__zhop', '__zoff', '__zup', '__zupf',
                       '__zdown', '__zdownf', '__spfe', '__acfe', '__pafe',
                       '__flfe', '__lmo'],
      str(live_l1[:12]))
check('D3: the activators live in the feature submenus (File keeps __acc)',
      len(re.findall(r'\[menu __main __preprint __feat __\w+ __on\]',
                     lcdtxt)) == 16
      and re.findall(r'\[menu __main __preprint __file __(ac\w+)\]',
                     lcdtxt) == ['acc'], '')
check('D4: the queue Stop row is REALLY double-press now (R238 bug fix)',
      "gen_arm|default('') == 'qstop'" in lcdtxt
      and "_GEN_QUEUE_STOP CONFIRM={1 if" in lcdtxt
      and "VARIABLE=gen_arm VALUE='\"qstop\"'" in rd('..', 'macros',
                                                      '17_generator.cfg'), '')
_n_secs = len(re.findall(r'^\[menu ', lcdtxt, re.M))
check('D5: web menu export embedded + current (section count follows the '
      'menu, not a frozen number)',
      '"sections"' in rd('..', 'web', 'index.html')
      and '/*EMBEDDED_MENU_JSON*/' not in rd('..', 'web', 'index.html')
      and json.load(open(os.path.join(
          here, '..', 'web', 'menu_structure.json')))['sections'] == _n_secs,
      'menu sections=%d' % _n_secs)

print('--- E) per-job LED progress bar ------------------------------------')
m03 = rd('..', 'macros', '03_leds.cfg')
check('E1: _LED_JOB_PROGRESS draws the bar (master switch + power cap)',
      '[gcode_macro _LED_JOB_PROGRESS]' in m03
      and 'leds_on|default(True)' in m03
      and 'GREEN=0.4' in m03 and 'INDEX={i}' in m03, '')
check('E2: _LED_JOB_DONE restores the last state LEDs',
      '[gcode_macro _LED_JOB_DONE]' in m03
      and 'last_led|default(' in m03, '')
check('E3: worker hooks - bar start at job start, restore in finally/zombie',
      "_job_led(1, force=True)" in pp and "_job_led_done()     # R240" in pp
      and pp.count('_job_led_done()') >= 3, '')
check('E4: the heavy loops feed the bar (segfix, opt copy, range, texture)',
      pp.count('_job_led(') >= 6
      and 'progress=_job_led' in pp
      and 'progress(min(99,' in rd('r2_texture.py')
      and '_led240_sz = max(1, os.path.getsize(path))' in pp, '')
check('E5: _moonraker_gcode has the quiet mode (no offline spam)',
      "retries=2, loud=True" in pp
      and "_moonraker_gcode('_LED_JOB_PROGRESS PCT=%d' % pct, loud=False)"
      in pp, '')

print('--- F) version ------------------------------------------------------')
st = rd('..', 'macros', '01_state.cfg')
_live240 = '\n'.join(l for l in allmacros.split('\n')
                    if not l.lstrip().startswith('#'))
# R241 (.137): bare version numbers are first class (odometer: sfx('')=0) -
# the regex must not require a letter any more.
# R242 (.138): the pin moves with every release - current is .138.
# R243 (.139): the pin moves again - current is .139.
# R244 (.140): pin moved - current is .140.
# R246 (.142): pin moved again - current is .142.
_m240 = re.search(r"variable_version:\s*'(R2-\d{4}-\d{2}-\d{2}\.\d+)'", st)
_ver240 = _m240.group(1) if _m240 else None
check('F1: the CURRENT version is consistent (01_state == engine == MANUAL), '
      'no dead .13x/.14x scheme in live cfg lines',
      _ver240 is not None
      and r2_postproc.POSTPROC_RELEASE == _ver240
      and _ver240 in rd('..', 'MANUAL.md')
      and 'R2-2026-11-09.142a' not in st, _ver240)

print()
print('%d checks, %d failed' % (ok + fails, fails))
sys.exit(1 if fails else 0)
