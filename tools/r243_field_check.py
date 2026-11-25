#!/usr/bin/env python3
"""R243 (.139) field check - the LED ready-crash.

Field log .138 (klippy-3h (4).txt, Nov 10 13:33): klippy died at EVERY
startup with 'Internal error during ready callback: division by zero'
(first traceback lines 111-123; only two 'Start printer' lines - no
restart loop, klippy stayed in shutdown and refused every SAVE_VARIABLE,
which made the postproc daemon retry its boot push every ~5-6 s: 'push
failed - retrying next cycle', by design, self-healing once ready).

Root cause: the led_effect library builds each cylon sweep as

    frames = int(duration / spf)          # spf = 1/frame_rate
    for frame in range(frames):
        pct = frame / (frames - 1)        # <- the ONLY such division

R242's diet dropped the Dauerlauf rates 6 -> 3 fps, shrinking
r2_leveling's 'cylon 0.6' from 3 frames to ONE -> pct = 0/0 ->
ZeroDivisionError in the ready callback -> printer dead in the field.

Fix (config only - r2_postproc.py is untouched except the version
stamps, so no behavior change in the daemon that hammered the dead
klippy): both cylon layers run 1.0 s = 3 frames at 3 fps.

This battery simulates the library's frame math for EVERY layer of
EVERY [led_effect] in EVERY cfg, reproduces the field crash as a
negative test, pins the .138 rate diet + the fix, and pins the .139
version bump. NOTE on blink: its second parameter is a duty cycle
(frameCountOn/Off, no pct division anywhere in that class) - only
cylon carries the division, so only cylon is crash-reproduced.
"""
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

ok = 0
fails = 0


def check(name, cond, info=''):
    global ok, fails
    if cond:
        ok += 1
        print('PASS %s' % name)
    else:
        fails += 1
        print('FAIL %s   %s' % (name, info))


def rd(*p):
    return open(os.path.join(HERE, '..', *p), encoding='utf-8').read()


# ----------------------------------------------------------------------
# the library's frame math, reproduced (led_effect.py layerCylon)
# ----------------------------------------------------------------------
def cylon_frames(dauer, rate):
    spf = 1.0 / rate            # the layer receives seconds per frame
    return int(dauer / spf)     # == int(dauer * rate)


def cylon_would_crash(dauer, rate):
    """Exact reproduction of the field traceback line:
    layer.__init__ -> pct = frame / (frames - 1)"""
    frames = cylon_frames(dauer, rate)
    try:
        for frame in range(frames):
            _ = frame / (frames - 1)
        return False
    except ZeroDivisionError:
        return True


# layer types whose FIRST parameter is a duration in seconds
TIME_P1 = {'linearfade', 'breathing', 'blink', 'cylon', 'comet',
           'chase', 'twinkle', 'strobe', 'static'}
# moving layers: a 2-step sweep is no sweep (and cylon must stay far
# away from the frames==1 crash line)
MOVE_TYPES = {'cylon', 'comet', 'chase', 'pattern'}
# gradient's first parameter is an interval factor, not a duration
# (gradientLength = int(rate / p1), guarded, no pct division) - format
# checked only
NON_TIME = {'gradient'}

LAYER_RE = re.compile(
    r'^\s*([a-z]+)\s+(-?\d+(?:\.\d+)?)\s+(-?\d+(?:\.\d+)?)\s+'
    r'(top|screen)\s*\(')


def parse_effects():
    """Walk every cfg in the repo, return {name: (rate, [layer lines])}.
    Commented-out sections (leading '#') are ignored."""
    effects = {}
    root = os.path.join(HERE, '..')
    cfgs = []
    for dirpath, _dirs, files in os.walk(root):
        if os.sep + '.git' in dirpath:
            continue
        for fn in sorted(files):
            if fn.endswith('.cfg'):
                cfgs.append(os.path.join(dirpath, fn))
    for path in sorted(cfgs):
        cur, rate, layers, in_layers = None, None, [], False
        for raw in open(path, encoding='utf-8'):
            line = raw.rstrip('\n')
            if line.lstrip().startswith('#'):
                continue
            m = re.match(r'^\[led_effect\s+([\w]+)\]', line)
            if m:
                if cur:
                    effects[cur] = (rate, layers)
                cur, rate, layers, in_layers = m.group(1), None, [], False
                continue
            if cur is None:
                continue
            m = re.match(r'^frame_rate:\s*(\d+)', line)
            if m:
                rate = int(m.group(1))
                continue
            if re.match(r'^layers:\s*$', line):
                in_layers = True
                continue
            if in_layers:
                if line and not line.startswith((' ', '\t')):
                    in_layers = False   # next section key
                    continue
                if LAYER_RE.match(line):
                    layers.append(line.strip())
        if cur:
            effects[cur] = (rate, layers)
    return effects


print('--- A) the frame math, simulated for every layer -------------------')

effects = parse_effects()
bad, moves = [], []
for name, (rate, layers) in sorted(effects.items()):
    if rate is None:
        bad.append('%s: no frame_rate' % name)
        continue
    for ll in layers:
        m = LAYER_RE.match(ll)
        typ, p1 = m.group(1), abs(float(m.group(2)))
        if typ in NON_TIME:
            continue
        if typ not in TIME_P1:
            bad.append('%s: unknown layer type %r' % (name, typ))
            continue
        frames = int(p1 * rate)
        need = 3 if typ in MOVE_TYPES else 2
        if frames < need:
            bad.append('%s: %s %s @ %dfps -> %d frames (<%d)'
                       % (name, typ, p1, rate, frames, need))
        if typ in MOVE_TYPES:
            moves.append((name, typ, p1, rate, frames))
check('A1: every animated layer keeps int(duration*rate)>=2 '
      '(moving>=3) in all %d effects' % len(effects),
      not bad, '; '.join(bad))

check('A2a: the simulator reproduces the field crash '
      '(cylon 0.6 @ 3fps MUST raise)',
      cylon_would_crash(0.6, 3))
check('A2b: .137 survived the same layer (cylon 0.6 @ 6fps = 3 frames)',
      not cylon_would_crash(0.6, 6))
check('A2c: the fix clears it (cylon 1.0 @ 3fps = 3 frames)',
      not cylon_would_crash(1.0, 3))
cyl = [m for m in moves if m[1] == 'cylon']
check('A2d: no parsed cylon layer would crash at its shipped rate',
      all(not cylon_would_crash(m[2], m[3]) for m in cyl),
      repr(cyl))

print('--- B) the fix is in the config -------------------------------------')

leds = rd('macros', '03_leds.cfg')
leds_live = '\n'.join(l for l in leds.split('\n')
                       if not l.lstrip().startswith('#'))
check('B1: both cylones run 1.0 s (r2_homing + r2_leveling)',
      'cylon 1.0 0 screen (0,0.4,0.5)' in leds_live
      and 'cylon 1.0 0 screen (0.5,0.0,0.4)' in leds_live
      and 'cylon 0.6' not in leds_live
      and 'cylon 0.8' not in leds_live)
check('B2: header documents the R243 rule (frames = int(duration*rate))',
      'R243' in leds and 'frames = int(duration * frame_rate)' in leds
      and 'ZeroDivisionError' in leds)

print('--- C) the .138 rate diet stays intact ------------------------------')

EXPECT_RATES = {
    'r2_boot': 6, 'r2_idle': 3, 'r2_waiting': 3, 'r2_heating': 3,
    'r2_homing': 3, 'r2_leveling': 3, 'r2_pid': 3, 'r2_printing': 5,
    'r2_nozzle_on': 6, 'r2_paused': 6, 'r2_filament': 6, 'r2_alarm': 6,
    'r2_finished': 6,
}
diff = [k for k, v in EXPECT_RATES.items()
        if effects.get(k, (None,))[0] != v]
check('C1: the R242 diet + R243 fix rate table is pinned '
      '(13 effects)', not diff and len(effects) == 13,
      'diff=%r effects=%r' % (diff, sorted(effects)))
check('C2: r2_printing stays <= 5 fps (r164 serial budget)',
      effects.get('r2_printing', (0,))[0] <= 5)
check('C3: structure unchanged - 13 active effects, no new/removed',
      set(effects) == set(EXPECT_RATES), repr(sorted(effects)))

print('--- D) daemon untouched except stamps, version .139 everywhere -----')

pp_src = rd('tools', 'r2_postproc.py')
st = rd('macros', '01_state.cfg')
check('D1: daemon retry branch survived (explains the field hammering)',
      "retrying next cycle" in pp_src)
_live = []
for _f in sorted(os.listdir(os.path.join(HERE, '..', 'macros'))):
    if _f.endswith('.cfg'):
        _live += rd('macros', _f).split('\n')
_live += rd('menus', 'lcd_menues.cfg').split('\n')
_live = '\n'.join(l for l in _live if not l.lstrip().startswith('#'))
# R285: dynamic pins (the frozen .142a/R246b strings rotted with every
# release - the r272 repair round made the other batteries dynamic, this
# one was missed). Current version read live, leftover ban stays.
_cur_ver = re.search(r"variable_version: '([^']+)'", st).group(1)
_cur_rel = re.search(r"POSTPROC_RELEASE = '([^']+)'", pp_src).group(1)
_cur_build = re.search(r"POSTPROC_BUILD = '([^']+)'", pp_src).group(1)
check('D2: current version everywhere, no .138/.139/.140 leftovers in '
      'live cfg lines',
      '.138' not in _live and '.139' not in _live and '.140' not in _live
      and _cur_ver in rd('MANUAL.md')
      and _cur_ver == _cur_rel)
html = rd('web', 'index.html')
check('D3: web badge == 01_state version, page state ver == POSTPROC_BUILD',
      ('<span id="ver">%s</span>' % _cur_ver) in html
      and ("ver:'%s'}" % _cur_build) in html)
ta = rd('TESTANLEITUNG.md')
check('D4: TESTANLEITUNG ch. 28 documents the crash + field check',
      '## 28. Die .139-Neuerungen (R243' in ta
      and 'division by zero' in ta
      and '### Field-Check .139' in ta
      and 'R2-2026-11-09.139' in ta)
check('D5: README carries the current release row',
      ('**R2-%s' % _cur_ver.replace('R2-', '')) in rd('README.md'))

print()
print('%d checks, %d failed' % (ok + fails, fails))
sys.exit(1 if fails else 0)
