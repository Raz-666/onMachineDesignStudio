#!/usr/bin/env python3
"""R255 (.142k): the HOMING GUARD - the one layer that keeps our own host work
out of the probe window.

WHY THIS FILE EXISTS
====================
The 12.11.2026 field log (LampOpenE27, and every other file the user tried)
died at the SAME place, three sessions in a row:

    Requested toolhead position at shutdown time 265.666386:
    (115.00000000000003, 115.00000000000003, 10.0)   <- bed centre, after the
                                                        second probe contact,
                                                        on the 1 cm lift

What the log shows around that moment:

  * Reactor stalls of 0.361 s and 0.633 s, all of them
    'SelectReactor._got_pipe_signal' + 'ClientConnection.process_received'
    - i.e. Moonraker requests being processed by klippy's reactor.
  * 'Dumping 20 requests for client ...' - twenty API requests were still
    queued when the MCU gave up.
  * buffer_time = 0.000 in 63-70 % of the Stats lines before the crash: the
    host was never ahead of the MCU, so any stall lands directly on the next
    move's timestamp.
  * bytes_retransmit 9 / 13 and 'Dumping receive queue 100 messages': the
    serial link was congested too (the ACK for 100 queued messages had not
    come back).
  * and OUR OWN payload in that window: two identical 4 KB gcode/script
    pushes at 597.375 s carrying _PREVIEW_SET + the whole EXCLUDE_OBJECT
    polygon - while G28 was running.

Root cause (not "the file", not the move rate): the start dialog homes with
_STATE.mode = 'idle', so every "is the printer moving?" gate in the watcher
was blind exactly there, and the selection preview had NO gate at all.

THE FIVE PARTS OF THE FIX (each one pinned below)
  1. G28 is wrapped (rename_existing) - every homing, from any of the 22 call
     sites, marks mode 'homing' while it runs and restores the old mode after.
     A delayed_gcode releases the guard if a G28 dies mid-way.
  2. Every motion gate has its OWN print_time sample slot. The old code kept
     ONE shared sample, so _printer_busy() and the preview probe cancelled
     each other out ("no delta = not moving") and the push went out during
     homing. A 2 s hold keeps the gate closed across a probe dwell.
  3. The selection-preview push (the branch that reads preview_nonce) is now
     deferred like every other push instead of firing blind.
  4. The EXCLUDE_OBJECT polygon is left to the file when it is longer than
     1200 chars - the file ships and runs the same line, so nothing is lost
     and the script stays small.
  5. The SAVE_VARIABLE (a synchronous SD card write) moved out of the homing
     block it used to stand in.

Exit 0 = every part in place. Run: python3 tools/r255_homing_guard_check.py
"""
import importlib.util
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
P = open(os.path.join(HERE, 'r2_postproc.py'), encoding='utf-8').read()
S = open(os.path.join(ROOT, 'macros', '08_print_start_stop.cfg'),
         encoding='utf-8').read()

fails = []
checks = [0]


def check(name, ok, detail=''):
    checks[0] += 1
    if not ok:
        fails.append(name)
        print('FAIL  %s   %s' % (name, detail))
    else:
        print('ok    %s   %s' % (name, detail))


spec = importlib.util.spec_from_file_location('pp255',
                                              os.path.join(HERE, 'r2_postproc.py'))
pp = importlib.util.module_from_spec(spec)
spec.loader.exec_module(pp)

# ----------------------------------------------------------------- 1) G28 Guard
check('G28 wrapper: exists, renames the built-in, sets and restores the mode',
      '[gcode_macro G28]' in S
      and 'rename_existing: M99110' in S
      and "VARIABLE=mode VALUE='\"homing\"'" in S
      and 'saved_mode' in S
      and 'M99110 {rawparams}' in S)
check('G28 wrapper: a dying G28 releases the guard (delayed_gcode, 15 min)',
      '[delayed_gcode _HOMING_GUARD_OFF]' in S
      and 'UPDATE_DELAYED_GCODE ID=_HOMING_GUARD_OFF DURATION=900' in S
      and S.count("VARIABLE=mode VALUE='\"idle\"'") >= 2)
check('G28 wrapper: zero disk writes (SET_GCODE_VARIABLE only, no SAVE_VARIABLE)',
      'SAVE_VARIABLE' not in S[S.index('[gcode_macro G28]'):
                               S.index('[delayed_gcode _HOMING_GUARD_OFF]')])
check('G28 wrapper: is inert for the rest of the package (rawparams forwarded)',
      'M99110 {rawparams}' in S
      and S.count('rename_existing: M99110') == 1)
# R256 (.142l): THE ACTUAL BOOT HALT. Klipper demands an alias of the same
# name TYPE: 'G28' is traditional g-code, '_G28_RAW' is not ->
# "G-Code macro rename of different types" -> Printer is halted.
check('G28 wrapper: the alias is a TRADITIONAL g-code name (M99110), not '
      '_G28_RAW - that rename halted the printer at boot',
      'rename_existing: M99110' in S
      and 'rename_existing: _G28_RAW' not in S   # code, not the comment above
      and 'M99110 {rawparams}' in S)

# ------------------------------------------- 2) per-consumer motion sampling
check('motion gate: ONE sample slot PER consumer (the shared slot was the bug)',
      "_MOTION246D = {}" in P
      and "def _motion_active246d(st, slot='busy')" in P
      and "_MOTION246D.get(slot)" in P
      and "_motion_active246d(_st, 'busy')" in P
      and "_motion_active246d(_st, 'preview')" in P
      and "_motion_active246d(_st, 'strict')" in P)

# functional proof: two consumers sampling the same moment must NOT cancel
pp._MOTION246D.clear()
pp._MOTION_SEEN255[0] = 0.0
_st = {'idle_timeout': {'state': 'Printing'}, 'toolhead': {'print_time': 100.0}}
_a = pp._motion_active246d(_st, 'busy')             # first look -> moving
_st2 = {'idle_timeout': {'state': 'Printing'}, 'toolhead': {'print_time': 100.0}}
_b = pp._motion_active246d(_st2, 'preview')         # second consumer, same moment
check('motion gate: the same print_time seen by two consumers still reads MOVING',
      _a is True and _b is True, 'busy=%s preview=%s' % (_a, _b))

# functional proof: the hold spans a probe dwell
pp._MOTION246D.clear()
pp._MOTION_SEEN255[0] = 0.0
pp._motion_active246d({'idle_timeout': {'state': 'Printing'},
                       'toolhead': {'print_time': 50.0}}, 'busy')
_still = pp._motion_active246d({'idle_timeout': {'state': 'Printing'},
                                'toolhead': {'print_time': 50.0}}, 'busy')
check('motion gate: a 0 s gap (probe dwell) stays BUSY via the 2 s hold',
      _still is True, 'hold = %s s' % pp._MOTION_HOLD255)
check('motion gate: the hold is bounded (the watcher cannot silence itself)',
      0 < pp._MOTION_HOLD255 <= 5.0, '%.1f s' % pp._MOTION_HOLD255)

# ------------------------------------------------- 3) selection push deferred
_i = P.index('pn = rv.get(\'preview_nonce\', \'\')')
_block = P[_i:_i + 2600]
check('selection preview: gated by motion, deferred (not dropped) to idle',
      'elif _printer_moving():' in _block
      and "PENDING_PREVIEW.append((ppath, 'select'))" in _block
      and 'waits for idle' in _block)
check('selection preview: the old blind push is gone (no unguarded moonraker call '
      'before the gate)',
      _block.index('_printer_moving()')
      < _block.index("'\\n'.join(script_lines))")
      if "'\\n'.join(script_lines)" in _block else True)

# --------------------------------------------------------- 4) payload ceiling
check('preview payload: a long EXCLUDE_OBJECT polygon is left to the file '
      '(ceiling 1200 chars)',
      '_ex255 = _peek_objects(ppath)' in P
      and '<= 1200' in P
      and 'polygon left to the' in P)

# ------------------------------------------------ 5) disk write out of homing
_i = S.index('[gcode_macro _UNIVERSAL_START_INTERCEPT]')
_j = S.index('SET_GCODE_VARIABLE MACRO=_STATE VARIABLE=mode VALUE=\'"waiting"\'', _i)
_home = S[_i:_j]
check('start interceptor: the SD write (SAVE_VARIABLE start_decision) stands AFTER '
      'the homing block, not in it',
      _home.index('SAVE_VARIABLE VARIABLE=start_decision')
      > _home.index('        G28'),
      'position %d vs G28 at %d' % (_home.index('SAVE_VARIABLE VARIABLE=start_decision'),
                                    _home.index('        G28')))

# --------------------------------------------- 6) every gate knows 'homing'
check("busy gate: 'homing' counts as busy (was: mode 'idle' during G28)",
      "return _mode in ('waiting', 'starting', 'homing', 'printing'," in P)
check("strict push gate (SD mirror / gen_files): 'homing' counts as busy",
      "return _mode not in ('waiting', 'starting', 'homing', 'printing'," in P)
check('preview probe: mode homing/starting is motion, mode waiting is not',
      "in ('homing', 'starting'):" in P and "dwell can be longer" in P)

# ------------------------- functional: the probe answer during a real homing
# R255: the G28 wrapper makes klippy answer mode 'homing' - the preview probe
# must read that as MOTION even when print_time stands still (probe dwell).
import json as _json
import urllib.request as _ur


class _FakeResp(object):
    def __init__(self, payload):
        self._p = payload

    def read(self):
        return self._p

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def _fake_moonraker(status):
    def _open(url, timeout=None):
        return _FakeResp(_json.dumps({'result': {'status': status}}).encode())
    return _open


_real_open = _ur.urlopen
try:
    # (a) homing, head standing between two probe contacts
    _ur.urlopen = _fake_moonraker({
        'idle_timeout': {'state': 'Ready'},
        'toolhead': {'print_time': 4711.0},
        'gcode_macro _STATE': {'mode': 'homing'}})
    pp._MOTION246D.clear()
    pp._MOTION_SEEN255[0] = 0.0
    _mv = pp._printer_moving(host='127.0.0.1', port=7125)
    check('functional: mode homing + still head -> the preview probe says MOVING '
          '(push deferred)', _mv is True, 'moving=%s' % _mv)
    # (b) the open start dialog: the preview IS wanted
    _ur.urlopen = _fake_moonraker({
        'idle_timeout': {'state': 'Ready'},
        'toolhead': {'print_time': 4712.0},
        'gcode_macro _STATE': {'mode': 'waiting'}})
    pp._MOTION_SEEN255[0] = 0.0
    pp._MOTION246D.clear()
    pp._MOTION246D['preview'] = 4712.0
    _mv2 = pp._printer_moving(host='127.0.0.1', port=7125)
    check('functional: mode waiting + still head -> NOT moving (the dialog gets '
          'its file info)', _mv2 is False, 'moving=%s' % _mv2)
    # (c) a real move in progress (idle_timeout Printing, print_time advanced)
    _ur.urlopen = _fake_moonraker({
        'idle_timeout': {'state': 'Printing'},
        'toolhead': {'print_time': 4800.0},
        'gcode_macro _STATE': {'mode': 'idle'}})
    pp._MOTION246D['preview'] = 4799.0
    _mv3 = pp._printer_moving(host='127.0.0.1', port=7125)
    check('functional: manual preheat/G28 outside the dialog (mode idle, '
          'print_time advancing) -> MOVING', _mv3 is True, 'moving=%s' % _mv3)
finally:
    _ur.urlopen = _real_open

print()
if fails:
    print('R255 HOMING GUARD: %d checks, %d FAIL - %s'
          % (checks[0], len(fails), ', '.join(fails[:3])))
    sys.exit(1)
print('R255 HOMING GUARD: %d checks, 0 FAIL - our host work stays out of the '
      'probe window' % checks[0])
