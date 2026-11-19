#!/usr/bin/env python3
"""R242 (.138) field check - the start-window diet.

Field log .137 (klippy-3h, Nov 10): two 'MCU shutdown: Timer too close'
right in the HOMING phase after file selection, on clean files (MAXRATE
12, gcodein=0). The log showed the reactor stalled 0.541 s ('Reactor busy
for 0.541'), built from our own start-window loads:

  1. the DOUBLE preview push (R62 selection + R195 dialog re-peek, ~20 KB
     each through moonraker->webhooks->klippy while homing plans moves),
  2. the fat web poll (save_variables = the whole variables dict
     serialized inside klippy, every 3 s),
  3. 6 fps LED frames on a link that drops neopixel updates at idle
     ('Neopixel update did not succeed' - klippy retries = churn),
  4. the _WATCHDOG re-arming _STATE_WATCHER at 0.5 s (20% fast ticks).

This battery pins all four fixes + the version bump + the ch. 27 docs.
"""
import importlib.util
import os
import re
import sys
import tempfile
import time

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


print('--- A) the double preview push is deduped ---------------------------')

spec = importlib.util.spec_from_file_location(
    'r2p242', os.path.join(HERE, 'r2_postproc.py'))
pp = importlib.util.module_from_spec(spec)
spec.loader.exec_module(pp)

tmp = tempfile.mkdtemp(prefix='r242_')
f1 = os.path.join(tmp, 'Rose_PLA.gcode')
open(f1, 'w').write('G28\n')
stat1 = os.stat(f1)

# A1: remember(ok) + identical re-peek -> SKIP (the _PREVIEW liveness
# holds: klippy still carries the file's name)
pp._preview_last.update(key=None, t=0.0, ok=False)
pp._moonraker_status = lambda *a, **k: {
    'gcode_macro _PREVIEW': {'name': 'Rose_PLA.gcode'}}
pp._preview_remember('Rose_PLA.gcode', f1, True)
check('A1: identical re-peek within the window is SKIPPED',
      pp._preview_dup_skip('Rose_PLA.gcode', f1) is True)

# A2: klippy restarted (macro reset) -> the push MUST re-fire
pp._moonraker_status = lambda *a, **k: {
    'gcode_macro _PREVIEW': {'name': '-'}}
check('A2: klippy restart (name reset) re-fires the push',
      pp._preview_dup_skip('Rose_PLA.gcode', f1) is False)

# A3: a different file -> push
f2 = os.path.join(tmp, 'Other.gcode')
open(f2, 'w').write('G28\n')
pp._moonraker_status = lambda *a, **k: {
    'gcode_macro _PREVIEW': {'name': 'Rose_PLA.gcode'}}
check('A3: a different file is pushed',
      pp._preview_dup_skip('Other.gcode', f2) is False)

# A4: the file changed on disk (regenerated) -> push
# (A1's remember still holds the OLD stat - the append must invalidate it)
time.sleep(0.01)
with open(f1, 'a') as fh:
    fh.write('G1 X1\n')
pp._moonraker_status = lambda *a, **k: {
    'gcode_macro _PREVIEW': {'name': 'Rose_PLA.gcode'}}
check('A4: changed mtime/size re-fires the push',
      os.stat(f1).st_size != stat1.st_size
      and pp._preview_dup_skip('Rose_PLA.gcode', f1) is False)

# A5: window expiry -> push
pp._preview_remember('Rose_PLA.gcode', f1, True)
check('A5: beyond the dedupe window the push re-fires',
      pp._preview_dup_skip('Rose_PLA.gcode', f1,
                           now=time.time() + pp._PREVIEW_DEDUP_WIN + 1)
      is False)

# A6: a FAILED previous push never satisfies the dedupe
pp._preview_remember('Rose_PLA.gcode', f1, False)
pp._moonraker_status = lambda *a, **k: {
    'gcode_macro _PREVIEW': {'name': 'Rose_PLA.gcode'}}
check('A6: a failed push does not dedupe (moonraker unreachable case)',
      pp._preview_dup_skip('Rose_PLA.gcode', f1) is False)

# A7: the nonce branch is WIRED (skip path + remember on both outcomes)
pp_src = rd('tools', 'r2_postproc.py')
check('A7: watch loop skips on dup + remembers ok AND failure',
      '_preview_dup_skip(pfn, ppath)' in pp_src
      and 'heavy push skipped' in pp_src
      and pp_src.count('_preview_remember(') >= 3)

print('--- B) the web poll diet (r2_menu.py) --------------------------------')

rm = rd('web', 'r2_menu.py')
check('B1: save_variables rides a 10 s tier (the fat dict serializes in klippy)',
      '_sv_fresh' in rm and '- self._sv_t < 10.0' in rm
      and "want.pop('save_variables', None)" in rm
      and '_sv_cache' in rm)
check('B2: the start-window diet: light set + waiting/starting modes',
      "_LIGHT = ('display_status', 'print_stat" in rm
      and "in ('waiting', 'starting')" in rm
      and 'if o in _LIGHT}' in rm)
check('B3: diet serves the rest from the last full snapshot',
      '_diet_cache' in rm and 'status.setdefault(k, v)' in rm)
check('B4: the diet is decided by a tiny precheck (not by the page)',
      "'print_stats', 'gcode_macro _STATE'" in rm
      and '_pre.get' in rm)
check('B5: cached save_variables is served as a COPY (prune deletes keys)',
      "dict(self._sv_cache['variables'])" in rm
      and "dict(svv['variables'])" in rm)

print('--- C) LED frames + watchdog cadence ----------------------------------')

led = rd('macros', '03_leds.cfg')


def fr(eff):
    m = re.search(r'\[led_effect %s\]\n(?:[^\[]*\n)*?frame_rate:\s*(\d+)' % eff,
                  led)
    return int(m.group(1)) if m else None


check('C1: Dauerlauf effects at 3 fps (idle/waiting/heating/homing/'
      'leveling/pid)',
      all(fr(e) == 3 for e in ('r2_idle', 'r2_waiting', 'r2_heating',
                               'r2_homing', 'r2_leveling', 'r2_pid')))
check('C2: boot stays 6 (pre-motion), printing stays 5 (r164 budget)',
      fr('r2_boot') == 6 and fr('r2_printing') == 5)
check('C3: R242 comment explains the frame diet in 03_leds.cfg',
      'R242' in led and 'Neopixel update did not' in led
      and 'frame_rate' in led)

st = rd('macros', '01_state.cfg')
m = re.search(r'\[delayed_gcode _WATCHDOG\]\ninitial_duration: 30\ngcode:\n'
              r'(.*?)(?=\n\[|\Z)', st, re.S)
wd = m.group(1) if m else ''
check('C4: watchdog re-arms the watcher at its OWN cadence (1 s, not 0.5)',
      'ID=_STATE_WATCHER DURATION=1' in wd
      and 'DURATION=0.5' not in wd)

print('--- D) version + docs -------------------------------------------------')

# R243 (.139): the version checks moved with the release (same pattern as
# r240 F1). Ch. 27 stays as history; ch. 28 documents the LED ready-crash.
_live = []
for _f in sorted(os.listdir(os.path.join(HERE, '..', 'macros'))):
    if _f.endswith('.cfg'):
        _live += rd('macros', _f).split('\n')
_live += rd('menus', 'lcd_menues.cfg').split('\n')
_live = '\n'.join(l for l in _live if not l.lstrip().startswith('#'))
_m = re.search(r"variable_version:\s*'(R2-\d{4}-\d{2}-\d{2}\.\d+)'", st)
_ver = _m.group(1) if _m else None
check('D1: the CURRENT version is consistent (01_state == engine == MANUAL), '
      'no dead .13x/.14x scheme in the live state file',
      _ver is not None
      and ("POSTPROC_RELEASE = '%s'" % _ver) in pp_src
      and _ver in rd('MANUAL.md')
      and 'R2-2026-11-09.142a' not in st, _ver)
html = rd('web', 'index.html')
check('D2: web badge == 01_state version',
      ('<span id="ver">%s</span>' % _ver) in html, _ver)
ta = rd('TESTANLEITUNG.md')
check('D3: TESTANLEITUNG ch. 27 (diet, history) + ch. 28 (LED crash fix)',
      '## 27. Die .138-Neuerungen (R242' in ta
      and '## 28. Die .139-Neuerungen (R243' in ta
      and 'Start-Fenster-Di\u00e4t' in ta
      and 'vcgencmd get_throttled' in ta
      and 'identical re-peek' in ta
      and 'division by zero' in ta)
check('D4: README carries the .142 row',
      '**.142a (R246b)**' in rd('README.md'))

print()
print('%d checks, %d failed' % (ok + fails, fails))
sys.exit(1 if fails else 0)
