#!/usr/bin/env python3
"""R244 (.140) field check - the MCU-shutdown auto-recovery.

Field log .139 (Nov 10, 15:12): another 'MCU 'mcu' shutdown: Timer too
close' at homing end after selecting a 14746-moves/s texture file (the
flagged SegFix class). User request: the watcher shall recognize an MCU
shutdown and heal it - FIRMWARE_RESTART first, then escalate up to a
full system reboot, exactly like the user would via the UI.

This battery pins:
  A) the engine is wired into the watch loop + the safe-class list,
  B) the STATE MACHINE itself - a faked moonraker/probe/time walks the
     whole ladder: episode -> snapshot -> L1 FIRMWARE_RESTART -> L2
     klipper service restart -> L3 Pi reboot (with the persisted
     1/hour brake), the recurrence shortcut, the unsafe-class stop,
     the off-switch and the recovery summary,
  C) macros + LCD menu entry + the re-embedded menu export (2423),
  D) version .140 everywhere,
  E) the real crash-archive copy (fake HOME with a fake klippy.log,
     capped at 7 snapshots).
"""
import importlib.util
import json
import os
import sys
import tempfile

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


print('--- A) the engine is wired ------------------------------------------')

pp_src = rd('tools', 'r2_postproc.py')
check('A1: _recovery_tick runs inside the watch loop (every cycle)',
      'try:\n            _recovery_tick(directory)' in pp_src
      or '_recovery_tick(directory)' in pp_src)
check('A2: the safe classes are exactly the host/link set '
      '(no heater/thermal!)',
      "_RECOVERY_SAFE_CLASSES = (\n    'timer too close', "
      "'lost communication', 'communication timeout',\n    "
      "'communications timeout', 'can not update mcu',\n    "
      "'missed scheduling of next digital out')" in pp_src)
check('A3: the ladder thresholds are pinned (10 s L1, 90 s L2, 210 s L3, '
      '3 episodes/15 min, 1 h L3 brake)',
      'el >= 210.0' in pp_src and 'el >= 90.0' in pp_src
      and 'el >= 10.0' in pp_src and '900.0' in pp_src
      and '3600.0' in pp_src)
check('A4: klippy.log is snapshotted BEFORE the first restart',
      pp_src.index('def _recovery_archive') < pp_src.index('L1: sending')
      and pp_src.index("_recovery_archive(directory)")
      < pp_src.index("L1: sending FIRMWARE_RESTART"))

print('--- B) the state machine, simulated with a faked moonraker ----------')

spec = importlib.util.spec_from_file_location(
    'r2p244', os.path.join(HERE, 'r2_postproc.py'))
pp = importlib.util.module_from_spec(spec)
spec.loader.exec_module(pp)

tmp = tempfile.mkdtemp(prefix='r244_')
state_file = os.path.join(tmp, 'watcher_recovery.json')

calls = {'gcode': [], 'post': [], 'archive': [], 'probe': []}


class _FakeTime:
    def __init__(self):
        self.t = 1000.0

    def monotonic(self):
        return self.t

    def time(self):
        return self.t + 1700000000.0

    def strftime(self, fmt, *a):
        return 'mcu-sim.log'


_ft = _FakeTime()
_scenario = []
_last = [('ready', '')]


def _probe(**kw):
    if _scenario:
        _last[:] = [_scenario.pop(0)]
    return _last[0]


_orig_archive244 = pp._recovery_archive
pp._klippy_shutdown_probe = _probe
pp._moonraker_gcode = lambda s, **kw: (calls['gcode'].append(s), True)[1]
pp._moonraker_post = lambda path, body=None, **kw: (
    calls['post'].append((path, body)), True)[1]
pp._recovery_archive = lambda d: (calls['archive'].append(d), None)[1]
pp._recovery_state_file = lambda: state_file
pp.time = _ft


def _reset():
    pp._RECOVERY.update(active=False, t0=0.0, msg='', safe=False, l1=0,
                        l2=False, l3=False, archived=False, gave_up=False,
                        noticed='', history=[])
    calls['gcode'][:] = []
    calls['post'][:] = []
    calls['archive'][:] = []
    _scenario[:] = []
    _ft.t = 1000.0
    try:
        os.unlink(state_file)
    except OSError:
        pass


SHUT = ('shutdown', "MCU 'mcu' shutdown: Timer too close")

# B1: the full ladder - episode, snapshot, L1 -> L2 -> L3 + brake stamp
_reset()
_scenario.append(SHUT)
pp._recovery_tick(tmp)
check('B1a: new episode opens + klippy.log snapshot fires first',
      pp._RECOVERY['active'] and calls['archive'] == [tmp]
      and pp._RECOVERY['safe'])
check('B1b: no action before the 10 s settle', not calls['gcode']
      and not calls['post'])
_ft.t += 11.0                     # el = 11 s
pp._recovery_tick(tmp)
check('B1c: L1 FIRMWARE_RESTART at 10 s+',
      calls['gcode'] == ['FIRMWARE_RESTART'] and not calls['post'])
_ft.t += 79.0                     # el = 90 s, klippy still down
pp._recovery_tick(tmp)
check('B1d: L2 klipper service restart at 90 s',
      calls['post'] == [('/machine/services/restart', {'service': 'klipper'})])
_ft.t += 120.0                    # el = 210 s, still down
pp._recovery_tick(tmp)
check('B1e: L3 Pi reboot at 210 s + brake persisted',
      calls['post'][-1] == ('/machine/reboot', None)
      and json.load(open(state_file)).get('last_l3', 0) > 0
      and pp._RECOVERY['gave_up'])
check('B1f: after give-up nothing more fires',
      not (_ft.t + 30.0 or None) or (
          pp._recovery_tick(tmp),
          len(calls['post']) == 2 and len(calls['gcode']) == 1)[1])

# B2: recovery after L1 - episode closes with the console summary
_reset()
_scenario.append(SHUT)
pp._recovery_tick(tmp)
_ft.t += 11.0
pp._recovery_tick(tmp)                     # L1
_ft.t += 6.0
_scenario.append(('ready', 'Printer is ready'))
pp._recovery_tick(tmp)
check('B2: klippy READY closes the episode + RESPOND summary',
      not pp._RECOVERY['active']
      and any('auto-recovery: printer back after' in c
              for c in calls['gcode']))

# B3: heater class stays down (NEVER auto-restart thermal faults)
_reset()
_scenario.append(('shutdown', "MCU 'mcu' shutdown: Heater heater_bed not "
                              "heating at expected rate"))
pp._recovery_tick(tmp)
_ft.t += 60.0
pp._recovery_tick(tmp)
check('B3: heater/thermal shutdown = no restart, ever',
      pp._RECOVERY['gave_up'] and not calls['gcode'] and not calls['post'])

# B4: the off-switch (read from the variables FILE because klippy is dead)
_reset()
pp._recovery_mode_on = lambda: True     # patched per-case below
pp._recovery_mode_on = lambda: False
_scenario.append(SHUT)
pp._recovery_tick(tmp)
_ft.t += 11.0
pp._recovery_tick(tmp)
check('B4: recovery_mode=off leaves the printer down',
      pp._RECOVERY['gave_up'] and not calls['gcode'] and not calls['post'])
pp._recovery_mode_on = lambda: True

# B5: recurrence - the 3rd episode within 15 min goes straight to L3
_reset()
for _ep in range(2):                    # two healed episodes
    _scenario.append(SHUT)
    pp._recovery_tick(tmp)
    _ft.t += 11.0
    pp._recovery_tick(tmp)              # L1
    _scenario.append(('ready', 'Printer is ready'))
    pp._recovery_tick(tmp)
    _ft.t += 120.0                      # 2 min later
_scenario.append(SHUT)
pp._recovery_tick(tmp)                  # 3rd episode, history == 3
_ft.t += 11.0
pp._recovery_tick(tmp)
check('B5: 3rd episode in 15 min -> immediate L3 (no more L1/L2)',
      calls['post'] and calls['post'][-1] == ('/machine/reboot', None)
      and calls['gcode'].count('FIRMWARE_RESTART') == 2)

# B6: the persisted brake - no second reboot within the hour
_reset()
with open(state_file, 'w') as f:
    json.dump({'last_l3': _ft.time() - 60.0}, f)     # 1 min ago
_scenario.append(SHUT)
pp._recovery_tick(tmp)
_ft.t += 220.0                          # way past every threshold
pp._recovery_tick(tmp)
check('B6: L3 rate-limited by the persisted stamp -> gives up loudly',
      pp._RECOVERY['gave_up'] and not any(
          p == ('/machine/reboot', None) for p in calls['post']))

# B7: klippy 'error' state (config/crash class) never triggers the ladder
_reset()
_scenario.append(('error', 'Internal error during ready callback: '
                           'division by zero'))
pp._recovery_tick(tmp)
_ft.t += 120.0
pp._recovery_tick(tmp)
check('B7: klippy error state (the .138 class) = episode closed, no action',
      not pp._RECOVERY['active'] and not calls['gcode'] and not calls['post'])

print('--- C) macros + LCD menu + the re-embedded export -------------------')

st_cfg = rd('macros', '01_state.cfg')
check('C1: SET_RECOVERY stores recovery_mode, TOGGLE_RECOVERY flips it',
      '[gcode_macro SET_RECOVERY]' in st_cfg
      and "[gcode_macro TOGGLE_RECOVERY]" in st_cfg
      and 'SAVE_VARIABLE VARIABLE=recovery_mode' in st_cfg)
menus = rd('menus', 'lcd_menues.cfg')
check('C2: LCD System > MCU Recovery toggle wired to TOGGLE_RECOVERY',
      '[menu __main __system __rec]' in menus
      and 'TOGGLE_RECOVERY' in menus
      and 'MCU Recovery:' in menus)
doc = json.load(open(os.path.join(HERE, '..', 'web',
                                  'menu_structure.json')))
check('C3: menu export carries the new section count (2423)',
      doc['sections'] == 2423
      and sum(doc['counts'].values()) == 2423)
html = rd('web', 'index.html')
_emb = json.JSONDecoder().raw_decode(
    html.split('const EMBEDDED_MENU_JSON = ', 1)[1])[0]
check('C4: web page embed matches the export (sha + sections)',
      _emb['sections'] == 2423 and _emb['sha256'] == doc['sha256']
      and '/*EMBEDDED_MENU_JSON*/ null' not in html)

print('--- D) version .140 everywhere --------------------------------------')

st = rd('macros', '01_state.cfg')
_live = []
for _f in sorted(os.listdir(os.path.join(HERE, '..', 'macros'))):
    if _f.endswith('.cfg'):
        _live += rd('macros', _f).split('\n')
_live += rd('menus', 'lcd_menues.cfg').split('\n')
_live = '\n'.join(l for l in _live if not l.lstrip().startswith('#'))
check('D1: version .142 everywhere, no .138/.139/.140 leftovers in live cfg lines',
      "'R2-2026-11-09.142a'" in st
      and '.138' not in _live and '.139' not in _live and '.140' not in _live
      and 'R2-2026-11-09.142a' in rd('MANUAL.md')
      and "POSTPROC_RELEASE = 'R2-2026-11-09.142a'" in pp_src
      and "POSTPROC_BUILD = 'R246b'" in pp_src)
check('D2: web badge .142, page state ver R246',
      '<span id="ver">.142a</span>' in html and "ver:'R246b'}" in html)
ta = rd('TESTANLEITUNG.md')
check('D3: TESTANLEITUNG ch. 29 documents the ladder + field check',
      '## 29. Die .140-Neuerungen (R244' in ta
      and 'FIRMWARE_RESTART' in ta
      and '### Field-Check .140' in ta
      and 'R2-2026-11-09.140' in ta)
check('D4: README carries the .142 row',
      '**.142a (R246b)**' in rd('README.md'))

print('--- E) the real crash archive (fake HOME) ---------------------------')

pp._recovery_archive = _orig_archive244    # B ran it as a stub

fake_home = os.path.join(tmp, 'home')
os.makedirs(os.path.join(fake_home, 'printer_data', 'logs'))
open(os.path.join(fake_home, 'printer_data', 'logs', 'klippy.log'),
     'w').write('the crash evidence\n')
_gdir = os.path.join(tmp, 'gcodes')
_arch = os.path.join(_gdir, 'crash_archive')
os.makedirs(_arch)
for i in range(9):                      # 9 old snapshots already archived
    open(os.path.join(_arch, 'mcu-20260101-00000%d.log' % i),
         'w').write('old snapshot %d\n' % i)
_exp_orig = pp.os.path.expanduser
pp.os.path.expanduser = lambda p: fake_home + p[1:] if p.startswith('~/') \
    else _exp_orig(p)
try:
    pp._recovery_archive(_gdir)
finally:
    pp.os.path.expanduser = _exp_orig
_snaps = sorted(os.listdir(_arch))
check('E1: klippy.log copied into gcodes/crash_archive/, capped at 7',
      len(_snaps) == 7 and all(s.endswith('.log') for s in _snaps))
_newest = open(os.path.join(_arch, _snaps[-1])).read() \
    if _snaps else ''
check('E2: the snapshot is the CURRENT klippy.log',
      _newest == 'the crash evidence\n')

print()
print('%d checks, %d failed' % (ok + fails, fails))
sys.exit(1 if fails else 0)
