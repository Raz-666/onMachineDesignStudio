#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""R227 (.136y): regression pins for the .136x reconciliation spew.

FIELD LOG (.136x, after the update + PI reboot): the R226 gen_busy
reconciliation fired EVERY watcher pass (~6 s) - 'stale gen_busy cleared'
8x in 42 s, no VALUE=1 set in between, the console sprayed forever.

ROOT CAUSE: _read_vars() returns STRINGS (its R150 doc says so: the bools
are normalized 'so float() readers work' - every other caller converts).
The R226 test was `if rv.get('gen_busy')` - and the string '0' (from
`variable_gen_busy: False`) is a NON-EMPTY STRING = TRUE in Python. The
flag was False in the file the whole time; the test could never see it.

FIXES PINNED HERE:
  F1  the reconciliation parses the value for real ('1'/'true'/'on'/'yes'
      - everything else is False, including '0' and 'False').
  F2  announce ONCE per stale episode (latch in _JOB_STATE): a refusing
      klippy retries SILENTLY, the console never sprays; the latch rearms
      when a pass sees the flag healthy (or a real job owns it).
  F3  POSTPROC_BUILD was still 'R223' - the boot stamp said
      'R2-2026-11-08.136x (R223)' in the field log. Now the round of the
      running daemon.
  F4  update.sh did not restart moonraker - web/r2_menu.py is loaded at
      moonraker STARTUP, so the .136x klippy.log day export kept running
      the OLD filter (78-byte header-only file, byte-identical to the
      .136w bug) until the PI was rebooted by hand. update.sh restarts
      moonraker now (after the census - it talks TO moonraker before).

Run: python3 tools/r227_reconcile_fix.py   (exit 0 = all green)
"""
import os
import re
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import r2_postproc as pp                                  # noqa: E402

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


print('--- F1: the flag is PARSED, not string-tested')
D = tempfile.mkdtemp(prefix='r227_')
vf = os.path.join(D, 'variables.cfg')


def _rv(content):
    open(vf, 'w').write('[variables]\n' + content + '\n')
    return pp._read_vars(vf)


# the exact representations Klipper writes for the flag
for _lit, _expect in (('False', False), ('True', True), ('0', False),
                      ('1', True), ('false', False), ('true', True)):
    rv = _rv('variable_gen_busy: %s' % _lit)
    _parsed = str(rv.get('gen_busy', '0')).strip().strip('\'"') \
        .lower() in ('1', 'true', 'on', 'yes')
    check('F1 variable_gen_busy: %-5s -> _read_vars %r -> parsed %s '
          '(the R226 truthiness bug read TRUE for ALL of these)'
          % (_lit, rv.get('gen_busy'), _expect),
          _parsed == _expect, repr(rv.get('gen_busy')))
check('F1 missing key -> parsed False (no KeyError, no truthy default)',
      str(_rv('variable_other: 1').get('gen_busy', '0'))
      .strip().strip('\'"').lower() not in ('1', 'true', 'on', 'yes'))

print('--- F2: announce ONCE per stale episode (latch + silent retry)')
src = open(os.path.join(REPO, 'tools', 'r2_postproc.py')).read()
m = re.search(r'R227 \(\.136y field log\): _read_vars returns STRINGS.*?'
              r'rearm the latch\n.*?_JOB_STATE\[\'stale_gb227\'\] = False',
              src, re.S)
check('F2 the R227 block exists (parse + latch + rearm, in this order)',
      bool(m))
blk = m.group(0) if m else ''
check('F2 the parse feeds the condition (no raw rv.get truthiness left '
      'in the reconciliation code - comments may quote the old bug)',
      '_gb227' in blk and 'if _gb227' in blk
      and "rv.get('gen_busy')" not in '\n'.join(
          l for l in blk.split('\n') if not l.lstrip().startswith('#')
      ).replace("str(rv.get('gen_busy', '0'))", ''))
check('F2 announce branch: RESPOND + M117 + journal, gated by the latch',
      "not _JOB_STATE.get('stale_gb227')" in blk
      and '_JOB_STATE[\'stale_gb227\'] = True' in blk
      and 'RESPOND MSG="[queue] stale gen_busy cleared' in blk
      and 'M117 Queue free' in blk
      and "print('[queue] stale gen_busy cleared (reconciled)'" in blk)
check('F2 silent retry branch: SAVE_VARIABLE only - NO RESPOND, no M117, '
      'no print (a down klippy must not spray the console)',
      'SAVE_VARIABLE VARIABLE=gen_busy VALUE=0' in blk
      and blk.count('RESPOND') == 1 and blk.count('M117') == 1)
check('F2 latch rearms when the flag is healthy or a real job owns it '
      '(the else branch)',
      "else:\n                # flag healthy (or a real job owns it) - "
      'rearm the latch' in blk.replace('\r', ''))
check('F2 counts: 7 releases / 3 raises in the daemon '
      '(+1 silent retry vs R226)',
      src.count('SAVE_VARIABLE VARIABLE=gen_busy VALUE=0') == 7
      and src.count('SAVE_VARIABLE VARIABLE=gen_busy VALUE=1') == 3)

print('--- F3: the daemon build stamp names its round')
# .136r lesson: a hard round pin goes stale on the NEXT bump - the checks
# are round-aware now (>= the round that introduced the fix)
_b227m = re.search(r"^POSTPROC_BUILD = 'R(\d+)'$", src, re.M)
check("F3 POSTPROC_BUILD names a round >= R227 (the field boot said "
      "'.136x (R223)' - the stamp had not been bumped since R223)",
      bool(_b227m) and int(_b227m.group(1)) >= 227)
_r227m = re.search(r"^POSTPROC_RELEASE = 'R2-2026-11-08\.136([a-z])'$",
                   src, re.M)
check('F3 POSTPROC_RELEASE >= .136y',
      bool(_r227m) and _r227m.group(1) >= 'y')

print('--- F4: update.sh restarts moonraker (web code lives at startup)')
upd = open(os.path.join(REPO, 'update.sh')).read()
check('F4 moonraker restart present, AFTER the census '
      '(the census talks to moonraker, the restart kills it)',
      'systemctl restart moonraker' in upd
      and upd.find('FINAL watcher census') < upd.find('restart moonraker'))
check('F4 graceful when sudo is missing (a hint, not a crash)',
      'could not restart moonraker' in upd)

import shutil
shutil.rmtree(D, ignore_errors=True)

print()
if fails:
    print('R227 RECONCILE FIX: %d checks, %d FAIL' % (N, len(fails)))
    for f in fails:
        print('  -', f)
    sys.exit(1)
print('R227 RECONCILE FIX: %d checks, 0 FAIL - the spew is pinned dead' % N)
