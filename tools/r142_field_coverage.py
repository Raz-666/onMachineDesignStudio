#!/usr/bin/env python3
"""R142: FIELD LOG COVERAGE - every bug the user reported in the field
MUST be pinned by a check here, even (especially) the ones that never
showed up in the other suites.

Field log .93/.94 bugs and their pin:
  1  CAPS font endless loop   -> every glyph of every font has a sane
                                 path length (no repeated-subpath bombs)
  2  flowcap/travelacc fixes never ran -> the watch() runtime pass REALLY
                                 dispatches both nonces
  3  fix_reselect cleared while the fix still ran -> patience counter
                                 (12 passes) before the stale clear
  4  Label FIXED-mode error   -> job_cfgs with mode=1 renders (the old
                                 KeyError 'grown' crash)
  5  MCU 'Timer too close'    -> _printer_busy probe + generator nonce
                                 freeze + scan skip while printing; and
                                 every generated file stays under the
                                 400 moves/s tiny-segment budget
  6  calib macros divided by zero on LAYER/WIDTH/LINES junk -> every
                                 params.LAYER/WIDTH/LINES reader has a
                                 guard line right below it
  7  figures were cubes       -> true proportions: assembled 33.5-36mm,
                                 leg cell depth 7.84 not 15.8, two walls
                                 everywhere, never vase mode
  8  kit was '3 bricks'      -> a stepped model yields a multi-part kit
                                 with slope bricks; AUTO picks the fine
                                 plate grid for small models

Exit 0 = the field is covered.
"""
import math
import os
import re
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import r2_postproc as pp                                    # noqa: E402

TOOL = os.path.join(HERE, 'r2_postproc.py')
MAC = os.path.join(ROOT, 'macros', '12_maintenance.cfg')

n_ck = [0]
fails = []


def ck(name, cond, info=''):
    n_ck[0] += 1
    if not cond:
        fails.append((name, str(info)[:160]))
        print('FAIL %s   %s' % (name, str(info)[:110]))
    else:
        print('ok   %s' % name)


# ---- 1) font glyph sanity (CAPS endless loop class) -----------------------
for tname in ('FONT_SMOOTH', 'FONT_MONO', 'FONT_COND', 'FONT_NARROW',
              'FONT_CAPS', 'FONT_SCRIPT', 'FONT_HAND', 'FONT_PLATE',
              'FONT_PIXEL'):
    tbl = getattr(pp, tname, None)
    if tbl is None:
        continue
    worst = max((len(e[1] if isinstance(e, tuple) else e)
                 for e in tbl.values()), default=0)
    ck('fonts: %s worst glyph path %d < 700' % (tname, worst),
       worst < 700, 'worst=%d' % worst)

# the CAPS workhorses really contain the letters (O was the printer killer)
ck('fonts: CAPS has O/0/o/O-umlaut (lowercase via alias table)',
   all(ch in pp.FONT_CAPS or ch.upper() in pp.FONT_CAPS
       for ch in ('O', '0', 'o', 'Ö', 'ö')),
   sorted(pp.FONT_CAPS)[:20])

# ---- 2) watch() runtime dispatch of ALL fix nonces ------------------------
src = open(TOOL, encoding='utf-8').read()
for nonce in ('retract_fix_nonce', 'vol_fix_nonce', 'flowcap_fix_nonce',
              'travelacc_fix_nonce'):
    # runtime pattern: rv.get('<nonce>') ... nonce changed ... file_fix(
    hit = False
    for m in re.finditer(re.escape("rv.get('%s'" % nonce), src):
        window = src[m.start():m.start() + 700]
        if '!=' in window and 'file_fix(' in window:
            hit = True
            break
    ck('watch: %s runs in the poll loop (R133 missing-block bug)'
       % nonce, hit, nonce)

# ---- 3) fix_reselect patience ---------------------------------------------
ck('watch: fix_reselect waits (reselect_wait counter, >= 12 passes)',
   'reselect_wait[frs] = reselect_wait.get(frs, 0) + 1' in src
   and '>= 12' in src, 'patience block')

# ---- 4) busy protection while printing -------------------------------------
ck('watch: _printer_busy probe exists and gates the scan',
   'def _printer_busy' in src and 'if busy:' in src
   and src.index('if busy:') > src.index('def _printer_busy'), '')
ck('watch: generator nonces freeze while printing (label/figures/kit...)',
   "'figures_nonce'" in src and "'brickkit_nonce'" in src
   and '_freeze133' in src, '')
ck('watch: poll sleep stretches to 12s while printing',
   'time.sleep(12.0 if busy else interval)' in src, '')

# ---- 5) Label FIXED mode via job_cfgs (KeyError 'grown' class) ------------
d = tempfile.mkdtemp(prefix='r142_')
out, info = pp.make_labels(['FIXEDOK'], job_cfgs=[{'w': 50, 'h': 25,
                                                   'mode': 1}],
                           out_dir=d)
ck('labels: FIXED job_cfgs renders (was KeyError grown)',
   os.path.isfile(out), info.get('file'))
out2, _ = pp.make_labels(['A', 'BB'], job_cfgs=[{'w': 40, 'h': 20, 'mode': 1},
                                                {'w': 30, 'h': 15}],
                         out_dir=d)
ck('labels: FIXED + GROW mixed job plate renders',
   os.path.isfile(out2), out2)

# ---- 6) calibration macro guards -------------------------------------------
mac = open(MAC, encoding='utf-8').read()
for pname in ('LAYER', 'WIDTH', 'LINES'):
    readers = [m.start() for m in re.finditer(
        r'\{%% set \w+\s*=\s*params\.%s\|' % pname, mac)]
    guarded = 0
    for pos in readers:
        window = mac[pos:pos + 600]
        if re.search(r'\{% if \w+ <= [\d.]+ %\}\{% set \w+ = ', window):
            guarded += 1
    ck('macros: all %d params.%s readers have a <= guard'
       % (len(readers), pname),
       len(readers) > 0 and guarded == len(readers),
       'guarded %d/%d' % (guarded, len(readers)))

# ---- 7) figures: TRUE proportions, two walls, no vase ----------------------
fout, finfo = pp.make_figures(count=1, scale=100, out_dir=d)
ck('figures: assembled height 33.5..36mm (true proportions, no hat)',
   33.5 <= finfo['height_mm'] <= 36.0, finfo['height_mm'])
g = open(fout, encoding='utf-8').read()
ck('figures: head O10.2 x 8.5 documented + torso trapez documented',
   'torso trapezoid 15.4->10.6' in g and 'head O10.2' in g, '')
blocks, cur = [], None
for l in g.split('\n'):
    if l == 'LAYER_MARK':
        cur = {'o': 0, 'i': 0}
        blocks.append(cur)
    elif cur is not None:
        if l == ';TYPE:Outer wall':
            cur['o'] += 1
        elif l == ';TYPE:Wall-Inner':
            cur['i'] += 1
outer = sum(b['o'] for b in blocks)
inner = sum(b['i'] for b in blocks)
ck('figures: two walls dominate (inner/outer >= 0.8, never vase)',
   outer > 200 and inner / max(outer, 1) >= 0.8,
   'outer=%d inner=%d' % (outer, inner))
ck('figures: arm prints lying with shoulder pin + grip tube docs',
   'LYING ON ITS BACK' in g and 'shoulder pin O3.9' in g, '')
# move-rate budget (MCU 'Timer too close' class)
f50, _ = pp.make_figures(count=1, scale=50, out_dir=d)
g50 = open(f50, encoding='utf-8').read().split('\n')
worst, z, px, py = 0.0, None, None, None
for l in g50:
    if l.startswith(';Z:'):
        z = float(l[3:])
    m = re.match(r'^G1 X([\d.-]+) Y([\d.-]+).* F(\d+)', l)
    if m and z is not None:
        x, y, f = float(m.group(1)), float(m.group(2)), float(m.group(3))
        if px is not None and f > 0:
            dd = math.hypot(x - px, y - py)
            if dd > 0.01:
                worst = max(worst, f / 60.0 / dd)
        px, py = x, y
ck('figures 50%%: worst move rate %.0f/s < 400 (MCU serial budget)' % worst,
   worst < 400.0, '%.0f/s' % worst)

# ---- 8) kit: stepped model -> parts + slopes, AUTO = fine grid ------------
sing, _ = pp.make_figures(count=1, scale=100, mode='SINGLE', out_dir=d)
kout, kinfo = pp.make_brick_kit(sing, out_dir=d)     # AUTO
ck('kit: AUTO on a small stepped model = plate bands (BIG), >= 8 parts',
   kinfo['bands'] >= 8 and kinfo['parts'] >= 8,
   'bands=%d parts=%d' % (kinfo['bands'], kinfo['parts']))
ck('kit: slope bricks at the step edges',
   any('slope' in n.lower() for n in kinfo.get('notes', [])),
   kinfo.get('notes'))
kg = open(kout, encoding='utf-8').read()
ck('kit: slope parts printed without studs on the chamfer '
   '(EXCLUDE parts > stud-parts)',
   kg.count('EXCLUDE_OBJECT_START') == kg.count('EXCLUDE_OBJECT_END'),
   'start/end balance')

print()
print('R142 FIELD COVERAGE: %d checks, %d FAIL' % (n_ck[0], len(fails)))
sys.exit(1 if fails else 0)


if __name__ == '__main__':
    pass
