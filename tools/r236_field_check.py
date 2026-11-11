#!/usr/bin/env python3
"""R236 (.136ag) field check: the .136af field log round - six fixes.

Field log 2026-11-09 evening (.136af, 24 texture jobs V06..V32 + the
questions around it):

  1) MIRROR Y never selected/confirmed - mirror_axis was saved as a BARE
     string (SAVE_VARIABLE ... VALUE="y"): klipper's save_variables runs
     ast.literal_eval on the value - a bare y is not a Python literal,
     the command DIED silently and the axis stayed 'x' forever (the
     Mirror folder only ever saw _MIRX files). Same class: texture_dir,
     cake_part (menu + macro side). The working pattern (label_fit et
     al) is VALUE="\"y\"" - escaped quotes survive shlex, literal_eval
     then parses 'y'.

  2) The texture faded out across the BACK of the rose: circum was
     chord/layers_seen - on a SPIRAL VASE z rises with (almost) every
     move, so layers_seen counted MOVES (45292 instead of 242 layers on
     the field rose) and 'circum' degenerated into the mean segment
     length (2.9mm). k = round(2.9/scale) = 1 for EVERY preset = ONE
     pattern wave around the object = a sinus with its flat side on the
     back. The R231 loop pre-pass already measures the real wall loops -
     its MEDIAN is the true circumference now.

  3) New g-code never showed in the LCD folder (nor the web UI): the
     tree push deferred while the QUEUE worked (24 jobs = 30 min stale
     lists) - now every finished job pushes immediately (dirty runs
     between jobs, print still wins) and moonraker gets an explicit
     notify_filelist_changed for the web side.

  4) 'when is my file's turn? I only hear beeps' - the queue depth is
     now a save_variable (gen_queue_cnt), shown LIVE in the main menu
     right above the SD card, dropping with every finished job.

  5) Profile loads were silent for seconds (120 SAVE_VARIABLEs): manual
     loads (menu Defaults 1-8 / This file pre+post) now kick you out of
     the menu, beep, show 'Loading profile' and confirm with a done
     sound; automatic loads stay quiet plus one console line.

  6) 'Timer too close' right before prints / at pause moments: LED
     switches + beeps never fire in the SAME reactor tick as the motion
     burst they announce (homing, M24, layer 1, PAUSE, filament-out,
     RESUME) - they follow 1-1.5s later, mode-guarded.

  plus) the false 'IDLE SPIN detected' right after the queue drained:
     the 5-min CPU window contained the job builds - a contaminated
     window is discarded now.

Run:  python3 tools/r236_field_check.py
"""
import ast
import gzip
import math
import os
import re
import shutil
import sys
import tempfile

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REPO = HERE
PASS = 0
FAIL = 0


def ok(msg):
    global PASS
    PASS += 1
    print('  [ok] %s' % msg)


def bad(msg):
    global FAIL
    FAIL += 1
    print('  [!!] FAIL: %s' % msg)


def check(name, cond, info=''):
    if cond:
        ok(name)
    else:
        bad('%s%s' % (name, (' (%s)' % info) if info else ''))


import jinja2                                                     # noqa: E402

# klipper's gcode_macro environment - trim_blocks stays OFF (class 172)
env = jinja2.Environment(
    loader=jinja2.BaseLoader(),
    block_start_string='{%', block_end_string='%}',
    variable_start_string='{', variable_end_string='}',
    comment_start_string='{#', comment_end_string='#}')


class M(dict):
    """dict with attribute access (like Klipper status objects)"""

    def __getattr__(self, k):
        try:
            v = self[k]
        except KeyError:
            raise AttributeError(k)
        return M(v) if isinstance(v, dict) else v


def render(tpl, printer, params=None, menu=None):
    oldp, oldm = env.globals.get('params'), env.globals.get('menu')
    env.globals['params'] = params or {}
    env.globals['menu'] = menu or M({'input': 0})
    try:
        return env.from_string(tpl).render(printer=printer)
    finally:
        env.globals['params'] = oldp
        env.globals['menu'] = oldm


def shlex_value(line):
    """klipper's extended-params view of a SAVE_VARIABLE line: the VALUE
    token after posix shlex (commenters '#;', whitespace_split)."""
    import shlex
    lex = shlex.shlex(line, posix=True)
    lex.whitespace_split = True
    lex.commenters = '#;'
    toks = list(lex)
    if len(toks) >= 3 and toks[0] == 'SAVE_VARIABLE' and toks[1].startswith(
            'VARIABLE='):
        return toks[2][len('VALUE='):]
    return None


menus = open(os.path.join(REPO, 'menus', 'lcd_menues.cfg'),
             encoding='utf-8').read()
m17 = open(os.path.join(REPO, 'macros', '17_generator.cfg'),
           encoding='utf-8').read()
m05 = open(os.path.join(REPO, 'macros', '05_materials.cfg'),
           encoding='utf-8').read()
m08 = open(os.path.join(REPO, 'macros', '08_print_start_stop.cfg'),
           encoding='utf-8').read()
m09 = open(os.path.join(REPO, 'macros', '09_pause_filament.cfg'),
           encoding='utf-8').read()
pp = open(os.path.join(REPO, 'tools', 'r2_postproc.py'),
          encoding='utf-8').read()

print('--- A) Mirror Y + the bare-string class ------------------------------')

# the menu item's gcode block
mm = re.search(r'\[menu __main __preprint __mods __mirror __ax\]\n'
               r'type: input\n.*?\ngcode:\n(.*?)\n\n', menus, re.S)
check('A1: the mirror axis menu item exists', mm is not None)
if mm:
    out = render(mm.group(1), M({}), menu=M({'input': 1}))
    ln = [l for l in out.splitlines()
          if l.strip().startswith('SAVE_VARIABLE VARIABLE=mirror_axis')]
    check('A2: selecting Y saves a PYTHON string (not a bare word)',
          ln and ln[0].strip().endswith('VALUE="\\"y\\""'), out)
    if ln:
        val = shlex_value(ln[0].strip())
        try:
            v = ast.literal_eval(val)
            check('A3: shlex+literal_eval roundtrip -> the axis is really y',
                  v == 'y', repr(val))
        except (ValueError, SyntaxError) as e:
            check('A3: shlex+literal_eval roundtrip -> the axis is really y',
                  False, '%r (%s)' % (val, e))
    # negative control: the OLD bare form must fail the roundtrip
    try:
        ast.literal_eval(shlex_value(
            'SAVE_VARIABLE VARIABLE=mirror_axis VALUE="y"'))
        check('A4: the OLD bare form fails literal_eval (why Y never saved)',
              False)
    except (ValueError, SyntaxError):
        check('A4: the OLD bare form fails literal_eval (why Y never saved)',
              True)

td = re.search(r'\[menu __main __preprint __mods __tex __dir\]\n'
               r'type: input\n.*?\ngcode:\n(.*?)\n\n', menus, re.S)
check('A5: the texture dir menu item exists', td is not None)
if td:
    out = render(td.group(1), M({}), menu=M({'input': 0}))
    ln = [l for l in out.splitlines()
          if l.strip().startswith('SAVE_VARIABLE VARIABLE=texture_dir')]
    check('A6: Dir IN saves as a quoted string (the bare form died too)',
          ln and ln[0].strip().endswith('VALUE="\\"IN\\""'), out)

cp = re.search(r'\[menu __main __preprint __mods __cake __part\]\n'
               r'type: input\n.*?\ngcode:\n(.*?)\n\n', menus, re.S)
check('A7: the cake part menu item exists', cp is not None)
if cp:
    out = render(cp.group(1), M({}), menu=M({'input': 2}))
    ln = [l for l in out.splitlines()
          if l.strip().startswith('SAVE_VARIABLE VARIABLE=cake_part')]
    check('A8: cake part BOTH saves quoted', ln
          and ln[0].strip().endswith('VALUE="\\"BOTH\\""'), out)
cpc = [l for l in m17.splitlines()
       if 'SAVE_VARIABLE VARIABLE=cake_part' in l]
check('A9: macro side (17_generator) saves cake_part quoted too',
      cpc and cpc[0].strip().endswith('VALUE="\\"{pa177}\\""'), cpc)
# the three repaired variables never appear in the bare form again
# (VALUE="{single-var}" stays LEGAL for dict reprs - pending_snap,
# file_profiles, opt_snap: shlex keeps the inner single quotes, the
# dict literal parses. Only bare WORDS die in literal_eval.)
_bare = [l.strip() for l in menus.splitlines() + m17.splitlines()
         if re.match(r'^SAVE_VARIABLE VARIABLE=(mirror_axis|texture_dir|'
                     r'cake_part) VALUE="\{[^"]*\}"$', l.strip())]
check('A10: mirror_axis/texture_dir/cake_part never bare again',
      not _bare, str(_bare[:3]))

print('--- B) texture circumference: spiral vases measure real loops ------')
sys.path.insert(0, os.path.join(REPO, 'tools'))
tmpd = tempfile.mkdtemp(prefix='r236_')
try:
    # a synthetic Orca-style spiral vase: ;LAYER_CHANGE per layer, Z rises
    # with EVERY move (the exact field mode that broke layers_seen)
    vase = os.path.join(tmpd, 'vase.gcode')
    with open(vase, 'w') as f:
        f.write(';FLAVOR:Marlin\nG21\nG90\nM83\nG28\nG1 Z2 F5400\n')
        z = 0.2
        segs = 130
        for layer in range(200):
            f.write(';LAYER_CHANGE\n;TYPE:Outer wall\n')
            for i in range(segs):
                a = 2 * math.pi * i / segs + layer * 0.004
                z += 0.2 / segs
                f.write('G1 X%.3f Y%.3f Z%.3f E%.5f F2400\n'
                        % (110 + 30 * math.cos(a), 110 + 30 * math.sin(a),
                           z, 0.05))
        f.write(';TYPE:Top surface\nG1 E-1 F1800\nM104 S0\n')
    import r2_texture
    par = dict(mode='BUMPS', bump_pattern='WAVES', bump_scale=24.0,
               zsize=20.0, bump_amp=0.3, direction='OUT', seed=12,
               bed=(0, 0, 220, 220))
    _, info = r2_texture.apply_texture(vase, out_dir=tmpd, **par)
    check('B1: spiral vase circumference = 2*pi*r (188.5 +- 1)',
          187.5 <= info.get('circumference', 0) <= 189.5,
          str(info.get('circumference')))
    check('B2: ridges snapped to the guideline (8 x ~24mm, NOT 1 wave)',
          info.get('ridges') == 8, str(info.get('ridges')))
    check('B3: effective ridge size honors the 24mm guideline (+-15%)',
          20.4 <= info.get('eff_size', 0) <= 27.6, str(info.get('eff_size')))
    # the OLD measurement degenerates on the same file (negative control)
    old_circum = None
    with open(vase, errors='replace') as f:
        layers_seen, last_z = 0, None
        for line in f:
            if not line.startswith('G1'):
                continue
            mz = re.search(r'\bZ(-?[\d.]+)', line)
            if mz:
                zv = float(mz.group(1))
                if last_z is None or abs(zv - last_z) > 1e-6:
                    layers_seen += 1
                    last_z = zv
    check('B4: the same file under the OLD rule counts moves as layers '
          '(why circum was 1.5mm)', layers_seen > 25000, str(layers_seen))
finally:
    shutil.rmtree(tmpd, ignore_errors=True)

print('--- C) fresh files go live immediately -------------------------------')
check('C1: the scan defers while a PRINT runs (R133 rule kept)',
      "if busy:\n            if _dirty224:" in pp
      and "elif _JOB_STATE['busy'] and not _dirty224:" in pp)
check('C2: the queue alone no longer blocks the tree push',
      re.search(r"if busy or _JOB_STATE\['busy'\] or _JOB_STATE\['queue'\]:"
                r"\n\s+(if _dirty224|pass)", pp) is None)
check('C3: dirty forces the walk (a finished job pushes RIGHT away)',
      "_dirty224 = _JOB_STATE.pop('dirty', False)" in pp)
check('C4: moonraker notify endpoint for the web UI file list',
      '/server/files/notify_filelist_changed' in pp
      and 'def _moonraker_filelist_notify' in pp)
check('C5: every job output notifies moonraker (best effort)',
      re.search(r"for _o in outs:\n\s+try:\n\s+_moonraker_filelist_notify",
                pp) is not None)

print('--- D) the queue count rides the main menu ---------------------------')
check('D1: gen_queue_cnt is written by _genq_push',
      "SAVE_VARIABLE VARIABLE=gen_queue_cnt VALUE=%d" in pp
      and 'def _genq_push' in pp)
calls = pp.count('_genq_push()')
check('D2: pushed on every change (enqueue/dispatch/finish/clear >= 4 spots)',
      calls >= 4, str(calls))
check('D3: main menu item exists (above the SD card)',
      '[menu __main __queue]' in menus          # R238: renamed from __genq
      and menus.index('[menu __main __queue]') < menus.index(
          '[menu __main __sdcard]'))
check('D4: it is only visible while anything waits or builds',
      "gen_queue_cnt|default(0)|int > 0 or "
      "printer['save_variables'].variables.gen_busy" in menus)
check('D5: the title shows the live count',
      "'Gen queue: ' ~ (printer['save_variables'].variables."
      "gen_queue_cnt|default(0)|int)" in menus)
check('D6: the building-now line names the waiting count',
      "' - %d waiting' % _n236" in pp)
check('D7: a finished job reports what is left',
      '[queue] %s done - %d job(s) still ' in pp)

print('--- E) profile loads answer their press ------------------------------')
pm = re.search(r'\[gcode_macro _PROFILE_APPLY\]\n.*?\ngcode:\n(.*?)(?=\n\[)',
               m05, re.S)
check('E1: _PROFILE_APPLY body found', pm is not None)
if pm:
    body = pm.group(1)
    prof = {'material': 'PLA', 'overrides': 7, 'feats': {},
            'bed': 60.0, 'bed_on': True, 'first_layer_speed': 75.0,
            'shaper_off_feat': '', 'fan_min': 0.0, 'fan_max': 100.0,
            'fan_bridge': 0.0, 'fan_clamp_on': False}
    prn = M({'save_variables': M({'variables': M({
        'default_preset_2': M(prof)})})})
    out = render(body, prn, params={'SRC': 'default', 'N': '2',
                                    'FEEDBACK': '1'})
    check('E2: FEEDBACK press -> display + start beep BEFORE the save storm',
          out.index('M117 Loading profile') < out.index(
              'SAVE_VARIABLE VARIABLE=ov_bed')
          and '_SOUND_LIB NAME=r2_confirm' in out)
    check('E3: FEEDBACK press -> done beep + summary at the end',
          '_SOUND_LIB NAME=r2_done' in out
          and '[OK] profile loaded: 7 override(s) ON' in out)
    out2 = render(body, prn, params={'SRC': 'default', 'N': '2'})
    check('E4: automatic load stays quiet (no beep, one console line)',
          '_SOUND_LIB' not in out2 and 'M117 Loading' not in out2
          and '[OK] profile loaded' in out2)
check('E5: LOAD_DEFAULT_PRESET passes FEEDBACK=1',
      '_PROFILE_APPLY SRC=default N={n} FEEDBACK=1' in m05)
check('E6: FILE_PROFILE_LOAD passes FEEDBACK=1 (beep comes from APPLY)',
      '_PROFILE_APPLY SRC=file WHICH={which} FILE="{fn}" FEEDBACK=1' in m05)
# R240 (.136aj): the 8 default slots retired from the LCD - the ONE Depot
# profile + the this-file 'pre' load took over, every one with the 2-press
# arm (gen_arm) + menu.exit so the display shows the result.
kick = len(re.findall(
    r"\{menu\.exit\(\)\}\{% endif %\}\n\s+LOAD_DEPOT_PRESET CONFIRM=1",
    menus))
check('E7: the Depot load kicks you out to see the display', kick == 1,
      str(kick))
kick2 = len(re.findall(
    r"\{menu\.exit\(\)\}\{% endif %\}\n\s+FILE_PROFILE_LOAD WHICH=pre CONFIRM=1",
    menus))
check('E8: the this-file pre load kicks you out too', kick2 == 1, str(kick2))

print('--- F) AV stagger: no LED/beep in the motion tick --------------------')
# R246d: the _AV bodies self-reschedule now (motion-deferrent retries,
# DURATION 2.0/2.5) - those retry lines live INSIDE the [delayed_gcode]
# bodies and are not flow triggers. Count only the FLOW-side triggers
# (lines outside the delayed_gcode definitions).
_bodies236 = re.findall(r'\[delayed_gcode _AV_\w+\]\ngcode:\n(.*?)(?=\n\n|\Z)',
                        m08 + m09, re.S)
_stripped236 = m08 + m09
for _b236 in _bodies236:
    _stripped236 = _stripped236.replace(_b236, '')
av = re.findall(r'UPDATE_DELAYED_GCODE ID=(_AV_\w+) DURATION=([\d.]+)',
                _stripped236)
check('F1: seven burst spots staggered (homing/print x3/pause/filament/resume)',
      len(av) == 7, str(av))
check('F2: delays are 1.0-1.5s (noticeable relief, no dead time)',
      all(0.9 <= float(d) <= 1.6 for _, d in av))
check('F2b: the AV retries yield to motion (drain-check self-reschedule '
      'inside the bodies, bounded by the 120 s window)',
      re.search(r'_AV_HOMING_AV DURATION=2.0', m08) is not None
      and re.search(r'_AV_PRINT_AV DURATION=1.2', m08) is not None
      and '_dur246d > 120' in m08
      and 'VARIABLE=av_pt VALUE={pt246d|round(6)}' in m08)
defs = re.findall(r'\[delayed_gcode (_AV_\w+)\]', m08 + m09)
check('F3: every stagger has its delayed_gcode definition',
      sorted(set(d for d, _ in av)) == sorted(set(defs)), str(defs))
_av_guarded = True
for d in set(defs):
    dm = re.search(r'\[delayed_gcode %s\]\ngcode:\n(.*?)(?=\n\n|\Z)' % d,
                   m08 + m09, re.S)
    if not dm or ("printer['gcode_macro _STATE'].mode" not in dm.group(1)
                  and '.mode' not in dm.group(1)):   # R246d: s246d.mode
        _av_guarded = False
check('F4: all five AV delayed codes are mode-guarded', _av_guarded)
# render proof: a cancelled print must not light the wrong LED
dg = re.search(r'\[delayed_gcode _AV_PRINT_AV\]\ngcode:\n(.*?)\n\n', m09 + m08,
               re.S)
if not dg:
    dg = re.search(r'\[delayed_gcode _AV_PRINT_AV\]\ngcode:\n(.*)', m08, re.S)
check('F5: _AV_PRINT_AV body found', dg is not None)
if dg:
    o1 = render(dg.group(1), M({'gcode_macro _STATE': M(
        {'mode': 'printing'})}))
    o2 = render(dg.group(1), M({'gcode_macro _STATE': M(
        {'mode': 'idle'})}))
    check('F6: printing mode -> LED + beep arrive',
          'SET_LED_STATE STATE=printing' in o1 and 'r2_printing' in o1)
    check('F7: cancelled meanwhile (idle) -> NOTHING plays',
          'SET_LED_STATE' not in o2 and '_SOUND_LIB' not in o2)
check('F8: the homing burst still shows M117 instantly',
      re.search(r'M117 Homing\.\.\.\n\s*#\s*R236[^\n]*\n'
                r'(\s*#[^\n]*\n)*\s*UPDATE_DELAYED_GCODE ID=_AV_HOMING_AV',
                m08) is not None)

print('--- G) the IDLE SPIN window cannot see job work anymore --------------')
check('G1: the spin window carries a contamination flag',
      "'win': False}" in pp and "and not _spin148['win']" in pp)
check('G2: activity marks the window (loop tick + dispatch + finish)',
      pp.count("_spin148['win'] = True") >= 3)

print()
print('R236 FIELD CHECK: %d pass, %d fail' % (PASS, FAIL))
sys.exit(1 if FAIL else 0)
