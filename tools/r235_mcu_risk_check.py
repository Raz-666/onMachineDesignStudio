#!/usr/bin/env python3
"""R235 (.136af) field check: the micro-move risk rides the start DIALOG.

Field log 2026-11-09 (.136ae, texture print V04_BigRose_020mm_TX.gcode,
6000 moves/s stamped): two 'Timer too close' clusters -

  cluster 1 (13:44, BEFORE any motion, gcodein=0): reactor busy 0.461 s
  with MenuManager.dispatch_gcode + DelayedGcode + webhook queries - the
  host was already strained (watcher python3 27% CPU, 11 reactor stalls
  up to 0.279 s, HOST_CHECK had said 'the next homing can hit Timer too
  close' - and it did)

  cluster 2 (13:55, 96 s into the print): reactor busy 0.482/0.985 s
  (EncoderSensor + webhooks) - with micro moves queued, klippy's move
  buffer holds only milliseconds of motion, so ANY such stall ends in
  'Timer too close'

The system HAD warned at selection time ('[!] ... up to 6000 moves/s -
Timer too close risk! ... M117 MCU risk - SegFix!') - but by the time the
user answered the start dialog minutes later, the warning had scrolled
away and the print started unmerged.

R235 fix: the risk travels with the preview card (_PREVIEW.moverate,
pushed by _PREVIEW_SET from the MOVERATE the watcher stamps) and the
start dialog itself repeats it - at BOTH catch spots in 08 and in the
2 s waiter's reminder (M117 'SegFix first! Start?' + a [!] RESPOND line)
for as long as the dialog waits.

This audit proves it with klipper-EXACT renders (single braces, NO
trim_blocks - error class 172):
  A) _PREVIEW_SET stores MOVERATE (and always resets it first - the
     R74 rule: never the previous file's values)
  B) the waiter: risky file -> 'SegFix first!' + the [!] line + the
     normal waiting text; smooth file -> the old behavior byte-for-byte
     in spirit ('Changes? -> menu Start?', no [!] line)
  C) both dialog catch spots carry the warning (render + static)
  D) the macro threshold (400) matches the watcher's selection-time
     threshold (mr > 400.0)
  E) pins: _PREVIEW declares variable_moverate, delayed_gcode header
     intact (R235 editing accident guard)

Run:  python3 tools/r235_mcu_risk_check.py
"""
import os
import re
import sys

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


from jinja2 import Environment, BaseLoader   # noqa: E402

# klipper's gcode_macro environment - trim_blocks stays OFF (class 172)
env = Environment(loader=BaseLoader(),
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


def render(tpl, printer, params=None):
    old = env.globals.get('params')
    env.globals['params'] = params or {}
    try:
        return env.from_string(tpl).render(printer=printer)
    finally:
        env.globals['params'] = old


print('--- A) _PREVIEW_SET stores MOVERATE (reset first, R74 rule) ----------')
p08 = open(os.path.join(REPO, 'macros', '08_print_start_stop.cfg'),
           encoding='utf-8').read()
m = re.search(r'^\[gcode_macro _PREVIEW_SET\]\n.*?^gcode:\n(.*?)(?=^\[)',
              p08, re.S | re.M)
check('A0: _PREVIEW_SET body found', m is not None)
if m:
    t = m.group(1)
    out = render(t, M({}), params={'NAME': 'rose.gcode', 'MOVERATE': '6000',
                                   'TYPE': 'MARKED'})
    check('A1: the card RESET clears moverate first (stale risk dies)',
          'VARIABLE=moverate VALUE=0.0' in out)
    check('A2: MOVERATE=6000 lands on the card',
          'VARIABLE=moverate VALUE=6000.0' in out, out[:400])
    out2 = render(t, M({}), params={'NAME': 'rose.gcode'})
    check('A3: no MOVERATE param -> only the reset (no stale carry-over)',
          out2.count('VARIABLE=moverate') == 1
          and 'VALUE=0.0' in out2)
    out3 = render(t, M({}), params={'NAME': 'x.gcode', 'MOVERATE': 'junk'})
    check('A4: junk MOVERATE never raises (float(0) guard)',
          'VARIABLE=moverate VALUE=0.0' in out3)

print('--- B) the waiter repeats the risk while the dialog waits ------------')
p07 = open(os.path.join(REPO, 'macros', '07_start_confirm.cfg'),
           encoding='utf-8').read()
m = re.search(r'^\[delayed_gcode _START_CONFIRM_WAITER\]\ngcode:\n(.*?)(?=^\[)',
              p07, re.S | re.M)
check('B0: _START_CONFIRM_WAITER is still a DELAYED_GCODE (R235 edit guard)',
      m is not None)
if m:
    t = m.group(1)

    def waiter(moverate):
        pr = M({'gcode_macro _STATE': M({'mode': 'waiting',
                                         'wait_ticks': 0}),
                'save_variables': M({'variables': M({'start_decision': ''})}),
                'print_stats': M({'filename': 'Texture/rose.gcode'}),
                'gcode_macro _PREVIEW': M({'moverate': moverate})})
        return render(t, pr)

    risky = waiter(6000.0)
    check("B1: risky file -> M117 'SegFix first! Start?'",
          'M117 SegFix first! Start?' in risky, risky[:300])
    check('B2: risky file -> the [!] moves/s line names the number + the fix',
          '[!] 6000 moves/s micro moves - run the Segment fix FIRST'
          in risky and 'Pre-Print > File > Segment fix' in risky)
    check('B3: risky file -> the normal waiting text still present',
          '>>> Waiting for decision:' in risky)
    check('B4: risky file -> reschedules itself (dialog never dies)',
          'UPDATE_DELAYED_GCODE ID=_START_CONFIRM_WAITER DURATION=2' in risky)
    smooth = waiter(0.0)
    check("B5: smooth file -> the old M117 unchanged",
          'M117 Changes? -> menu Start?' in smooth)
    check('B6: smooth file -> NO [!] risk line',
          'moves/s micro moves' not in smooth)
    check('B7: smooth file -> waiting text unchanged',
          '>>> Waiting for decision:' in smooth
          and 'PRINT_AS_SLICED / PRINT_WITH_OVERRIDES / CANCEL_PENDING_PRINT'
          in smooth)
    edge = waiter(400.0)
    check('B8: exactly 400 is NOT risky (watcher: strictly greater)',
          'moves/s micro moves' not in edge)
    edge2 = waiter(401.0)
    check('B9: 401 IS risky (threshold matches the watcher)',
          'moves/s micro moves' in edge2)
    # realistic empty-card edge: the _PREVIEW OBJECT exists (it loads with
    # the package, like _STATE) but carries no 'moverate' key yet - a fresh
    # klippy restart. Single-level undefined is what |default(0) is FOR;
    # a missing BASE macro cannot happen (the config would not load)
    pr = M({'gcode_macro _STATE': M({'mode': 'waiting', 'wait_ticks': 0}),
            'save_variables': M({'variables': M({'start_decision': ''})}),
            'print_stats': M({'filename': 'rose.gcode'}),
            'gcode_macro _PREVIEW': M({})})
    noCard = render(t, pr)
    check("B10: empty _PREVIEW card (post-restart) -> default(0), no crash",
          'Traceback' not in noCard
          and 'M117 Changes? -> menu Start?' in noCard)

print('--- C) both dialog catch spots carry the warning ----------------------')
n_risk = p08.count('moves/s micro moves - run the Segment fix FIRST')
check('C1: both catch spots in 08 warn (LEGACY + main)', n_risk == 2,
      'found %d' % n_risk)
check('C2: both spots read the card with the safe default',
      p08.count("printer['gcode_macro _PREVIEW'].moverate|default(0)|float")
      == 2)
check('C3: the waiter reads it too',
      "printer['gcode_macro _PREVIEW'].moverate|default(0)|float" in p07)

print('--- D/E) pins: threshold + card variable ------------------------------')
pp = open(os.path.join(REPO, 'tools', 'r2_postproc.py'),
          encoding='utf-8').read()
check('D1: watcher selection threshold still at the MCU budget (same rule)',
      'mr is not None and mr > 450.0' in pp)
check('D2: the watcher still stamps MOVERATE (source of the number)',
      "_patch_info_kv(p, 'MOVERATE'" in pp)
check('E1: _PREVIEW declares variable_moverate: 0.0',
      'variable_moverate: 0.0' in p08)
check('E2: the [!] wording names the MCU budget (like the watcher)',
      p08.count('MCU budget ~450/s') == 2
      and 'MCU budget ~450/s' in p07)

print()
print('R235 MCU RISK CHECK: %d pass, %d fail' % (PASS, FAIL))
sys.exit(1 if FAIL else 0)
