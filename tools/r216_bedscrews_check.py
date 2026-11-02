#!/usr/bin/env python3
"""R216 bed-screws LCD flow check (pinned).

The Mainsail-style bed screw calibration: BED_SCREWS_START measures all
screws (SCREWS_TILT_CALCULATE), _BS_EVAL (delayed - fresh expansion AFTER
the probe finished) reads printer.screws_tilt_adjust.results and builds the
display state, BED_SCREWS_NEXT walks the screws, BED_SCREWS_ROUND re-measures
(+1 round), BED_SCREWS_DONE takes over only when every screw is nominal.

This check renders the REAL macro bodies from macros/12_maintenance.cfg
against a fake printer and drives the whole state machine:
  start -> eval(round 1, 2 screws off) -> next x3 -> done (rejected, names
  the bad screw) -> round -> eval(round 2, all nominal) -> done (accepted,
  bs_state cleared) + cancel path + the missing-[screws_tilt_adjust] guard.

Run:  python3 tools/r216_bedscrews_check.py
"""
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from jinja2 import Environment, Undefined, BaseLoader   # noqa: E402

SQ = chr(39)
DQ = chr(34)

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
PASS = []
FAIL = []


def ck(name, ok, detail=''):
    (PASS if ok else FAIL).append(name)
    print('%-4s %s%s' % ('PASS' if ok else 'FAIL', name,
                         ('  [%s]' % detail) if detail and not ok else ''))


class M(dict):
    def __getattr__(self, k):
        try:
            return self[k]
        except KeyError:
            raise AttributeError(k)


env = Environment(loader=BaseLoader(),
                  variable_start_string='{', variable_end_string='}',
                  block_start_string='{%', block_end_string='%}',
                  comment_start_string='{#', comment_end_string='#}',
                  trim_blocks=True, lstrip_blocks=False, undefined=Undefined)

src = open(os.path.join(ROOT, 'macros/12_maintenance.cfg'),
           encoding='utf-8').read()


def macro_body(name):
    m = re.search(r'\[(?:gcode_macro|delayed_gcode) %s\](.*?)(?=\n\[|\Z)'
                  % re.escape(name), src, re.S)
    if not m:
        raise AssertionError('macro not found: ' + name)
    b = re.search(r'gcode:\n((?:[ \t]+.*\n?)*)', m.group(1))
    return b.group(1)


class Fake:
    """minimal klipper-shaped printer + rendered-gcode recorder"""
    def __init__(self, results=None, have_section=True, ui=None, bs=''):
        settings = {}
        if have_section:
            settings['screws_tilt_adjust'] = M({
                'screw1': '45, 25', 'screw1_name': 'front left',
                'screw2': '195, 25', 'screw2_name': 'front right',
                'screw3': '195, 205', 'screw3_name': 'rear right',
                'screw4': '45, 205', 'screw4_name': 'rear left',
                'screw_thread': 'CW-M4'})
        self.printer = M({
            'gcode_macro _STATE': M({'mode': 'idle'}),
            'gcode_macro _BED_SCREWS_UI': M(dict(ui or {
                'head': 'not running', 'cur': 'Start below', 'running': 0,
                'round': 0, 'idx': 0, 'n': 0, 'lines': ''})),
            'save_variables': M({'variables': M({'bs_state': bs})}),
            'configfile': M({'settings': M(settings)}),
            'screws_tilt_adjust': M({'results': M(results or {})}),
        })

    def render(self, name):
        env.globals['printer'] = self.printer
        env.globals['params'] = {}
        text = env.from_string(macro_body(name)).render()
        return [ln.strip() for ln in text.split('\n') if ln.strip()]


def run(results=None, have_section=True, ui=None, bs='',
        name='BED_SCREWS_START'):
    f = Fake(results, have_section, ui, bs)
    return f, f.render(name)


R1 = {                       # round 1: front right CW 1 turn, rear left off
    'screw1': M({'z': 0.0, 'sign': 'CW', 'adjust': '00:00', 'is_base': True}),
    'screw2': M({'z': -0.7, 'sign': 'CW', 'adjust': '01:00', 'is_base': False}),
    'screw3': M({'z': 0.001, 'sign': 'CW', 'adjust': '00:00', 'is_base': False}),
    'screw4': M({'z': 0.35, 'sign': 'CCW', 'adjust': '00:30', 'is_base': False}),
}
R2 = {                       # round 2: everything nominal
    'screw1': M({'z': 0.0, 'sign': 'CW', 'adjust': '00:00', 'is_base': True}),
    'screw2': M({'z': 0.0, 'sign': 'CW', 'adjust': '00:00', 'is_base': False}),
    'screw3': M({'z': 0.0, 'sign': 'CW', 'adjust': '00:00', 'is_base': False}),
    'screw4': M({'z': 0.0, 'sign': 'CCW', 'adjust': '00:00', 'is_base': False}),
}

BS1 = ('R1|I1|N4|front left:base|front right:CW 01:00|rear right:ok|'
       'rear left:CCW 00:30')
UI1 = {'head': 'Round 1 - screw 1/4', 'cur': '1/4 front left:base',
       'running': 1, 'round': 1, 'idx': 1, 'n': 4, 'lines': BS1.split('|', 3)[3]}

# ---- 1) START: guards + probe + delayed eval arm ----
f, out = run(R1)
ck('start homes, measures and arms the delayed eval',
   any('G28' in l for l in out)
   and any('SCREWS_TILT_CALCULATE' in l for l in out)
   and any(l.startswith('UPDATE_DELAYED_GCODE ID=_BS_EVAL') for l in out),
   str(out[:6]))
f2, out2 = run(R1, have_section=False)
ck('start without [screws_tilt_adjust] notifies the config gap',
   not any('SCREWS_TILT_CALCULATE' in l for l in out2)
   and any('screws_tilt_adjust' in l for l in out2), str(out2[:4]))

# ---- 2) EVAL round 1: state build (clock + names + base/ok) ----
f, out = run(R1, ui={'head': 'not running', 'cur': 'Start below',
                     'running': 1, 'round': 0, 'idx': 0, 'n': 0, 'lines': ''},
             name='_BS_EVAL')
sv = [l for l in out if l.startswith('SAVE_VARIABLE VARIABLE=bs_state')]
svv = sv[0].split('VALUE=', 1)[1].strip().strip(SQ + DQ) if sv else ''
ck('eval builds bs_state with round 1 + 4 named screws',
   svv.startswith('R1|I1|N4|')
   and 'front left:base' in svv and 'front right:CW 01:00' in svv
   and 'rear right:ok' in svv and 'rear left:CCW 00:30' in svv, svv)
ck('eval pushes the display state (head/cur/running) into the UI macro',
   any(l.startswith('SET_GCODE_VARIABLE MACRO=_BED_SCREWS_UI '
                   'VARIABLE=running VALUE=1') for l in out)
   and any(('VARIABLE=cur VALUE=' + SQ + DQ + '1/4 front left:base' + DQ + SQ)
           in l for l in out)
   and any(('VARIABLE=head VALUE=' + SQ + DQ + 'Round 1 - screw 1/4'
            + DQ + SQ) in l for l in out),
   str([l for l in out if '_BED_SCREWS_UI' in l][:3]))
f3, out3 = run({}, name='_BS_EVAL')
ck('eval with empty results says so (no crash)',
   any('no result' in l for l in out3), str(out3[:3]))

# ---- 3) NEXT: walks 1 -> 4, then parks ----
f, out = run(ui=UI1, name='BED_SCREWS_NEXT')
ck('next advances to screw 2/4 with its own line',
   any('VARIABLE=idx VALUE=2' in l for l in out)
   and any(('VARIABLE=cur VALUE=' + SQ + DQ + '2/4 front right:CW 01:00'
            + DQ + SQ) in l for l in out), str(out[:5]))
ck('next writes NOTHING to the SD (no SAVE_VARIABLE)',
   not any(l.startswith('SAVE_VARIABLE') for l in out), str(out))
f, out = run(ui=dict(UI1, idx=4), name='BED_SCREWS_NEXT')
ck('next on the last screw parks at round end',
   any('Round done' in l for l in out)
   and not any('VARIABLE=idx' in l for l in out), str(out[:3]))
f, out = run(ui=dict(UI1, running=0), name='BED_SCREWS_NEXT')
ck('next without a running calibration says so',
   any('not running' in l for l in out), str(out[:3]))

# ---- 4) DONE round 1: rejected + names the bad screws ----
f, out = run(bs=BS1, name='BED_SCREWS_DONE')
ck('done with 2 screws off REJECTS and names them',
   any('front right' in l and 'rear left' in l for l in out)
   and not any('all nominal' in l for l in out), str(out[:4]))

# ---- 5) ROUND + EVAL round 2, DONE accepted ----
f, out = run(ui=UI1, name='BED_SCREWS_ROUND')
ck('round re-measures without a re-home',
   any('SCREWS_TILT_CALCULATE' in l for l in out)
   and not any(l == 'G28' for l in out), str(out[:4]))
f, out = run(R2, ui=dict(UI1, round=1, idx=1), name='_BS_EVAL')
ck('eval round 2 counts the round and marks all ok',
   any(('SAVE_VARIABLE VARIABLE=bs_state VALUE=' + SQ + DQ + 'R2|') in l
       for l in out)
   and any(('VARIABLE=head VALUE=' + SQ + DQ + 'Round 2 - screw 1/4'
            + DQ + SQ) in l for l in out),
   str([l for l in out if 'bs_state' in l][:2]))
f, out = run(bs='R2|I1|N4|front left:base|front right:ok|rear right:ok|'
                 'rear left:ok', name='BED_SCREWS_DONE')
clear = 'SAVE_VARIABLE VARIABLE=bs_state VALUE=' + SQ + DQ + DQ + SQ
ck('done with everything nominal TAKES OVER + clears the state',
   any('all nominal' in l.lower() for l in out)
   and any(clear == l for l in out), str(out[:5]))

# ---- 6) CANCEL ----
f, out = run(name='BED_SCREWS_CANCEL')
ck('cancel clears state + display',
   any(clear == l for l in out)
   and any(('VARIABLE=cur VALUE=' + SQ + DQ + 'Start below' + DQ + SQ) in l
           for l in out), str(out[:4]))

print()
if FAIL:
    print('RESULT: FAIL - %d of %d checks failed'
          % (len(FAIL), len(FAIL) + len(PASS)))
    sys.exit(1)
print('RESULT: PASS - %d checks, bed-screw LCD flow fully pinned' % len(PASS))
