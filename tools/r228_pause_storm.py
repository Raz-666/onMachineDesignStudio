#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""R228 (.136z): regression pins for the .136y pause-storm field log.

FIELD (the Orca vase finally printed - the R226 round works: full-bed mesh
with the CENTER-only hint, probe-safe prime line, 20x20mm park box): but
layer 1 saw a quick-pause/resume churn, "State re-synced: mode was stuck
in 'paused'" after EVERY resume, and the third resume ended in
MCU 'Timer too close' shutdown - after which every reconcile push
re-printed the whole shutdown banner (2x per 6 s). The user asked whether
the filament motion sensor caused the pauses (it chirps 'nothing conveyed'
at every start).

PINNED HERE (the renders live in macro_render_test R228):
  F1  state watcher: an external pause needs THREE ticks before we follow
      (the old instant flip sampled the resume gap between our mode='printing'
      and print_stats following M24 - seconds on a slow file - and knocked
      the mode back to 'paused' after every resume).
  F2  filament sensor grace: _PRIME_LINE arms 30 s at print start,
      _RESUME_COMMON arms 20 s - chatter reports instead of arming pauses;
      a real runout re-fires after the window.
  F3  Pause NOW two-press arm EXPIRES after 5 s (one armed click stayed
      armed forever - any later single click or EMI ghost enter paused).
  F4  the daemon reconcile is rate-limited to one attempt per 10 s AND
      gated on klippy_state=='ready' (no push into a shutdown klippy - each
      one re-printed the full 'Timer too close' banner to every client).

Run: python3 tools/r228_pause_storm.py   (exit 0 = all green)
"""
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)

fails = []
N = 0


def check(name, ok, info=''):
    global N
    N += 1
    if not ok:
        fails.append(name)
        print('  FAIL %s %s' % (name, str(info)[:240]))
    else:
        print('  ok   %s' % name)


m01 = open(os.path.join(REPO, 'macros', '01_state.cfg')).read()
m08 = open(os.path.join(REPO, 'macros', '08_print_start_stop.cfg')).read()
m09 = open(os.path.join(REPO, 'macros', '09_pause_filament.cfg')).read()
menu = open(os.path.join(REPO, 'menus', 'lcd_menues.cfg')).read()
r2p = open(os.path.join(REPO, 'tools', 'r2_postproc.py')).read()

print('--- F1: external pause follows only after 3 ticks')
_w = re.search(r'\[delayed_gcode _STATE_WATCHER\]\ninitial_duration: 8\n'
               r'gcode:\n(.*?)(?=\n\[|\Z)', m01, re.S).group(1)
check('F1 the bypassed-pause branch counts ticks and needs d2 >= 3 '
      '(instant flip is gone)',
      '{% set d2 = s.ext_pause_cnt|default(0) + 1 %}' in _w
      and 'VARIABLE=ext_pause_cnt VALUE={d2}' in _w
      and '{% if d2 >= 3 %}' in _w
      and re.search(r"st == 'paused' and s\.mode == 'printing'",
                    _w) is not None)
check('F1 default + resets: ext_pause_cnt starts at 0, resets when the '
      'desync heal fires',
      'variable_ext_pause_cnt: 0' in m01
      and _w.count('VARIABLE=ext_pause_cnt VALUE=0') >= 1)

print('--- F2: filament sensor grace windows')
check('F2 runout honors the grace flag (first branch gated + chatter elif)',
      "and not s.sensor_grace|default(False)" in m09
      and 'filament sensor event during start/resume grace ignored' in m09)
check('F2 the grace timer exists and clears the flag',
      '[delayed_gcode _SENSOR_GRACE_OFF]' in m09
      and 'VARIABLE=sensor_grace VALUE=False' in m09)
check('F2 _PRIME_LINE arms 30 s at print start (where the chirps happen)',
      'sensor_grace VALUE=True' in m08
      and '_SENSOR_GRACE_OFF DURATION=30' in m08)
check('F2 _RESUME_COMMON arms 20 s after the refill moves',
      m09.count('sensor_grace VALUE=True') == 1   # resume only - 08 has start
      and '_SENSOR_GRACE_OFF DURATION=20' in m09)
check('F2 default flag in _STATE (absent key never breaks the renders)',
      'variable_sensor_grace: False' in m01)

print('--- F3: Pause NOW arm expires')
check('F3 the LCD arm starts a 5 s expiry timer',
      'UPDATE_DELAYED_GCODE ID=_PAUSE_NOW_ARM_OFF DURATION=5' in menu)
check('F3 the expiry timer exists and clears the arm',
      '[delayed_gcode _PAUSE_NOW_ARM_OFF]' in m09
      and 'VARIABLE=pause_now_arm VALUE=0' in m09)

print('--- F4: daemon reconcile - rate limit + klippy-ready gate')
_blk = re.search(r'R228 \(\.136y field log\): rate-limit EVERYTHING.*?'
                 r'_JOB_STATE\[\'stale_gb227\'\] = False',
                 r2p, re.S)
check('F4 the R228 block exists (rate limit + ready gate + latch rearm)',
      bool(_blk))
b = _blk.group(0) if _blk else ''
check('F4 one attempt per 10 s (announce AND silent retry - the backlog '
      'scan amplified 8 pushes in 8 s in the field log)',
      "time.monotonic() - _JOB_STATE.get('gb227_t', 0.0) >= 10.0" in b
      and "_JOB_STATE['gb227_t'] = time.monotonic()" in b)
check('F4 klippy must be READY before any push (each push into a shutdown '
      'klippy re-printed the whole Timer-too-close banner to every client)',
      "_moonraker_json('/server/info')" in b
      and "str(_inf228.get('klippy_state', '')) == 'ready'" in b)
check('F4 the announce/silent structure survived the restructure '
      '(R227 latch semantics intact)',
      "not _JOB_STATE.get('stale_gb227')" in b
      and 'M117 Queue free' in b
      and r2p.count('SAVE_VARIABLE VARIABLE=gen_busy VALUE=0') == 7)

print()
if fails:
    print('R228 PAUSE STORM: %d checks, %d FAIL' % (N, len(fails)))
    for f in fails:
        print('  -', f)
    sys.exit(1)
print('R228 PAUSE STORM: %d checks, 0 FAIL - the storm is pinned dead' % N)
