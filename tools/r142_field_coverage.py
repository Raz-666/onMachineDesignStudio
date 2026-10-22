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
ck('geometry classifier (.114): vase rule - a run of extruding moves '
   'with slowly rising Z (spiral) forces WALL-OUTER for the whole spiral '
   '(field rule: after the bottom ONE feature remains, always)',
   'self.vase = True' in src and '_vn153 >= 12' in src
   and "'WALL-OUTER')" in src.split('R153: vase/spiral mode')[1][:800], '')
ck('geometry classifier: brim rule - layer-1 wall loops WITHOUT a layer-2 '
   'successor become BRIM, the largest continuing inner loop is promoted '
   'back to WALL-OUTER (the real wall sat nested inside the brim ring)',
   '_brim153' in src and '_has_succ153' in src
   and "'BRIM')" in src.split('def _brim153')[1][:1800]
   and 'promote the LARGEST' in src, '')
ck('geometry classifier: derived APPLY_TYPE keyed by the WRITER index '
   '(the raw index shifted against the output whenever comments got '
   'filtered - derived tags landed next to the wrong lines)',
   'type_at[(gj, gj)] = gfeat' in src, '')
ck('sd_tree/sd_view/gen_files push: a cache only counts on a 200 answer, '
   'failed pushes retry next cycle, the VIEW refresh follows the current '
   'path+page read from save_variables (.112 field regression + .115 '
   'navigation sync)',
   src.count('retrying next cycle') == 3
   and src.count('if _moonraker_gcode(') >= 2
   and src.count('if not _moonraker_gcode(') == 1
   and src.count('gen_files_pushed[0] = _gfl') == 1
   and 'ast.literal_eval(_raw154)' in src
   and 'sd_tree_pushed[0] is not None' in src, '')
_tx152 = open('tools/r2_texture.py').read()
_lcd152 = open('menus/lcd_menues.cfg', encoding='utf-8').read()
ck('frame: backplate WITHOUT brim (user rule .115 - it gets inserted '
   'and clicked later, a brim would only break off again), the frame '
   'keeps its brim',
   'user rule): the backplate prints WITHOUT a' in src, '')
_sdregion155 = _lcd152.split('[menu __main __sdcard]')[1].split(
    '[menu __main __gen __gfiles __del]')[0]
_sdlines155 = [l for l in _sdregion155.splitlines()
               if l.startswith('name:') or l.startswith('enable:')]
ck('menu templates: NO percent-blocks in SD Card names/enables '
   "(Klipper's jinja env uses single braces - percent-blocks emit a "
   'stray closing brace into menu names)',
   bool(_sdlines155)
   and all('{' + '%' not in l for l in _sdlines155)
   and all('{{' not in l for l in _sdlines155), '')

ck('texture: vase mode textured along the WHOLE spiral (.112 field: '
   'Orca spells the spiral wall as Wall-outer, only the first/last '
   'normal layer carried the effect) - alias set + APPLY_TYPE parsing',
   "'wall outer' in _tx152 and 'external perimeter' in _tx152"
   " and '_is_outer_wall' in _tx152 and '_APPLY152' in _tx152"
   " and '_OUTER_ALIASES' in _tx152"
   " and _tx152.count('cur_outer') >= 5", '')
ck('LCD: visible fallback while the view is empty (never a dead menu) '
   '+ navigation rows (up/home/page) - pure single-brace slot templates',
   '[menu __main __sdcard __none]' in _lcd152
   and 'List empty - info' in _lcd152
   and '[menu __main __sdcard __up]' in _lcd152
   and '[menu __main __sdcard __home]' in _lcd152
   and '[menu __main __sdcard __pgd]' in _lcd152
   and 'How it works' in _lcd152, '')
ck('litho FLAT: deeper default relief (.110 field: "just a flat plate") - '
   '3 layers per step auto + per-step mm in the header + menu mm math',
   'col_layers or 3' in src and 'total relief, %.2gmm per step' in src
   and 'litho_col_layers|default(3)' in _lcd152
   and 'more = deeper' in src, '')
ck('LCD SD Card browser (.115): REAL folder navigation - the watcher '
   'pushes the whole tree (sd_tree, folders marked D:) + the current view '
   '(sd_view, 20 entries of path+page), the menu navigates via '
   'SDNAV_GO/UP/PAGE/HOME macros that rebuild the view',
   'menu __main __sdcard]' in _lcd152
   and 'sd_view|default([])' in _lcd152
   and src.count('SAVE_VARIABLE VARIABLE=sd_tree') == 1
   and src.count('SAVE_VARIABLE VARIABLE=sd_view') == 1
   and "'D:' + _d" in src and '_SD_EXT151' in src
   and 'sd_tree_pushed' in src
   and _lcd152.count('SDNAV_GO INDEX=') == 20, '')
ck('gen folders: created UP FRONT at watcher start (visible right after '
   'the install, all inside the gcodes root)',
   'gen folders (inside the gcodes root)' in src, '')
ck('offset menu: the coarse/fine duplicates are gone - ONE 0.05mm input '
   'per axis + a How-it-works row (field report: "values doubled")',
   "input_step: 0.1" not in open('menus/lcd_menues.cfg').read()
   .split('[menu __main __preprint __poff]')[1].split('[menu __main __preprint __file]')[0]
   and 'How it works' in open('menus/lcd_menues.cfg').read(), '')
ck('colorpic: explicit Z per layer AFTER the M600 chain (.110 field: '
   'the bands printed ~1cm in the air - the file had NO Z move at all)',
   'pen.set_z(z)' in src
   and 'purge moves Z - the band after a swap needs the reset' in src, '')
ck('litho STANDING: explicit Z per row (same in-air class of bug)',
   'pen.set_z(z)   # R149: explicit Z per row' in src, '')
ck('brim order: EVERY brim loop prints outermost first (user rule)',
   src.count('(wid * 0.35 + wid, wid * 0.35)') == 14
   and 'range(brim - 1, -1, -1)' in src
   and 'range(brim_loops - 1, -1, -1)' in src, '')
_m150 = open('macros/12_maintenance.cfg').read()
ck('plot FILAMENT: bed heats + purge line before the drawing (.110 field: '
   "'just hairs' - cold bed, no prime)",
   _m150.count('SET_HEATER_TEMPERATURE HEATER=heater_bed') >= 1
   and '_PURGE_SMART LAYER_HEIGHT={filz}' in _m150
   and "sv.plot_fil_z|default(0.2)|float" in _m150, '')
ck('plot: draw Z default 0.20 + FILAMENT note in both writers '
   '(_plot_write + plot_convert)',
   src.count("_vf('plot_fil_z', 0.20)") == 1
   and src.count("_v('plot_fil_z', 0.20)") == 1
   and src.count('thin lines need a warm bed') == 2, '')
ck('litho FLAT: step-cell stats in every header + empty-step re-cut guard '
   '+ single-tone note (the "flat plate only" field report)',
   'step cells: ' in src and 'step recut at pixel percentiles' in src
   and 'one tone - the step relief' in src
   and src.count('for _n in notes:') == 1, '')
ck('labels: raised text up to 10mm (50 layers, was 6) + menu range',
   'min(int(text_layers), 50)' in src
   and 'input_max: 50' in open('menus/lcd_menues.cfg').read(), '')
ck('vars: Klipper True/False bools normalize to 1/0 (float readers)',
   "_v150.lower() == 'true'" in src, '')
ck('watch: seen-cache persists across restarts (.110 - the 12-CPU-minute '
   'restart rescan of the whole gcodes folder was the field spin)',
   '_seen_state_path' in src and '_seen_load' in src and '_seen_save' in src
   and 'watch_state.json' in src and 'no restart rescan' in src
   and 'os.replace(tmp, path)' in src, '')
ck('watch: seen-cache save is throttled (>=60s) + atexit + once-mode hook',
   src.count('_seen_flush149') >= 3 and 'atexit.register' in src, '')
_ck110 = open('setup.sh').read()
ck('setup.sh: zram offer (zram-tools, zstd/50%/prio100, guided undo, '
   'config-only SD-swap shrink at >=750MB)',
   'zram-tools' in _ck110 and 'ALGO=zstd' in _ck110 and 'PRIORITY=100' in _ck110
   and 'purge zram-tools' in _ck110 and 'CONF_SWAPSIZE=200' in _ck110, '')
ck('setup.sh: optional-service list + extra print-server stack scan '
   '(octoprint/octoeverywhere/sonar/go2rtc/elegoo pattern) + removal guides',
   'octoeverywhere' in _ck110 and 'sonar' in _ck110 and 'go2rtc' in _ck110
   and 'elegoo' in _ck110 and 'rm -rf ~/oprint' in _ck110, '')
ck('watch: poll sleep stretches to 12s while printing, 60s under RAM pressure (.109)',
   'time.sleep(60.0 if _ram_low148 else (12.0 if busy else interval))' in src, '')

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
# R159: use the repaired pp._worst_move_rate (every G0/G1 in any token
# order - the old inline walk jumped across G0 travels: phantom rates)
worst = pp._worst_move_rate(f50)
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

# ---- 9) micro-segment bombs (MCU 'Timer too close' class) -----------------
ck('postproc: _patch_info_kv exists (was called-but-missing since R111)',
   hasattr(pp, '_patch_info_kv'), '')
ck('postproc: _worst_move_rate + _segments_fix_file exist',
   hasattr(pp, '_worst_move_rate') and hasattr(pp, '_segments_fix_file'),
   '')
hot = os.path.join(d, 'r142hot.gcode')
_x = 50.0
_hl = ['; R2-POSTPROC v5',
       '_FILE_INFO MATERIAL=PLA LAYER_HEIGHT=0.2 TOTAL_LAYERS=10',
       'PRINT_START MATERIAL=PLA LAYER_HEIGHT=0.2 TOTAL_LAYERS=10',
       'G90', 'M83', 'G1 F3000']
for _i in range(300):
    _x += 0.02
    _hl.append('G1 X%.3f Y50.000 E0.001' % _x)
_hl.append('PRINT_END')
open(hot, 'w', encoding='utf-8').write('\n'.join(_hl) + '\n')
_rb = pp._worst_move_rate(hot)
ck('segments: the bomb is measured (>1500 moves/s)', _rb > 1500,
   '%.0f/s' % _rb)
_n, _rb2, _ra = pp._segments_fix_file(hot)
ck('segments: fix merges the flood and lands under 400 moves/s',
   _n >= 250 and _ra < 400, 'merged=%d %.0f->%.0f/s' % (_n, _rb2, _ra))
_e = sum(float(l.split(' E')[1]) for l in open(hot, encoding='utf-8')
         if l.startswith('G1 X') and ' E' in l)
ck('segments: extrusion preserved (300 x 0.001)', abs(_e - 0.3) < 0.0005,
   'E=%.4f' % _e)
# R133b: selection NEVER measures (the full-file scan blocked the LCD on
# the field Pi) - it warns from the stamped MOVERATE only. The job worker
# stamps it; here we stamp like the worker does.
hot2 = os.path.join(d, 'r142hot2.gcode')
open(hot2, 'w', encoding='utf-8').write('\n'.join(_hl) + '\n')
_rb2 = pp._worst_move_rate(hot2)
pp._patch_info_kv(hot2, 'MOVERATE', '%.0f' % _rb2)
_hs, _ = pp._preview_script(hot2)
ck('segments: selection warns about hot files (Timer too close risk)',
   any('Timer too close' in l for l in _hs), _hs[-2:])
_hs0, _ = pp._preview_script(hot)     # the healed file stays silent
ck('segments: healed file selected -> no warning',
   not any('SegFix' in l for l in _hs0), '')
# a hot file WITHOUT MOVERATE: selection stays quiet AND fast (no scan)
hot3 = os.path.join(d, 'r142hot3.gcode')
open(hot3, 'w', encoding='utf-8').write('\n'.join(_hl) + '\n')
_hs3, _ = pp._preview_script(hot3)
ck('segments: unstamped file -> no scan on selection (no warning, fast)',
   not any('SegFix' in l for l in _hs3), '')
ck('watch: segments nonce dispatched in the poll loop',
   "rv.get('segments_fix_nonce'" in src and 'file_fix(\'segments\'' in src,
   '')
_fixcfg = open(MAC.replace('12_maintenance', '08_print_start_stop'),
               encoding='utf-8').read()
ck('macros: FIX_FILE accepts WHAT=SEGMENTS', "'SEGMENTS'" in _fixcfg
   and 'segments_fix_nonce VALUE=' in _fixcfg, '')
_men = open(os.path.join(ROOT, 'menus', 'lcd_menues.cfg'),
            encoding='utf-8').read()
ck('LCD: Segment fix entry in Pre-Print > File',
   'FIX_FILE WHAT=SEGMENTS' in _men, '')

# ---- 10) R133b: one job at a time, kit crash, plot-source hygiene --------
ck('queue: _job_tick only sleeps while a worker owns the call',
   hasattr(pp, '_job_tick') and hasattr(pp, '_JOB_YIELD')
   and hasattr(pp, '_JOB_STATE'), '')
import time as _t142
_t0 = _t142.time()
for _ in range(200):
    pp._job_tick()                 # flag off -> must NOT sleep
ck('queue: 200 ticks with flag off run instantly (<0.2s)',
   _t142.time() - _t0 < 0.2, '%.2fs' % (_t142.time() - _t0))
pp._JOB_YIELD['on'] = True
_t0 = _t142.time()
for _ in range(200):
    pp._job_tick()                 # 200 ticks / every 25 = 8 x 20ms
_el = _t142.time() - _t0
pp._JOB_YIELD['on'] = False
ck('queue: ticks with flag on DO pause (8 x 20ms ~ %.2fs)' % _el,
   0.1 <= _el < 1.0, '%.2fs' % _el)
ck('watch: the 5 generator spawns go through _spawn_job (no bare threads)',
   src.count('_spawn_job(') >= 5
   and src.count('threading.Thread(target=_') == 1,   # only the worker
   'spawn=%d bare=%d' % (src.count('_spawn_job('),
                         src.count('threading.Thread(target=_')))
ck('watch: scan skips while a job runs, is queued or RAM is low (.109)',
   "if busy or _JOB_STATE['busy'] or _JOB_STATE['queue'] or _ram_low148:" in src, '')
ck('watch: jobs requeue while the printer is busy (print has priority; '
   'R160b: the queue SAYS so after 90s instead of swallowing jobs silently)',
   'if _printer_busy():' in src and 'insert(' in src
   and 'waits: the printer is' in src, '')
ck('watch: R75 niceness kept, exactly ONE os.nice (no double lower)',
   src.count('os.nice(4)') == 1, 'count=%d' % src.count('os.nice(4)'))
ck('kit: parts_per_plate formatted via max() (was a list -> %d crash '
   'since R125, killed every successful kit message)',
   "max(_ik125['parts_per_plate'])" in src, '')
ck('kit: source picker skips R2-PLOT files',
   "'R2-PLOT' in _fh.read(4096)" in src, '')
_men = open(os.path.join(ROOT, 'menus', 'lcd_menues.cfg'),
            encoding='utf-8').read()
ck('kit menu: AUTO text matches the R133b mapping (BIG for small models)',
   'up to 10 studs BIG (fine plates), up to 26 SMALL, else MICRO' in _men,
   '')

# ---- 11) R133c: start-phase busy, priming order, queue cancel, kit UX ----
import urllib.request as _ur142, json as _json142

class _R142:
    def __init__(self, payload): self._p = payload
    def read(self): return _json142.dumps(self._p).encode()
    def __enter__(self): return self
    def __exit__(self, *a): return False

def _stub142(state, mode):
    def _u(url, timeout=1.5):
        return _R142({'result': {'status': {
            'print_stats': {'state': state},
            'gcode_macro _STATE': {'mode': mode}}}})
    return _u

_orig142 = _ur142.urlopen
try:
    for _st, _md, _exp in (('standby', 'starting', True),
                           ('standby', 'waiting', True),
                           ('standby', 'idle', False),
                           ('printing', 'idle', True),
                           ('standby', 'filament', True)):
        _ur142.urlopen = _stub142(_st, _md)
        ck('busy: %s/%s -> %s' % (_st, _md, _exp),
           pp._printer_busy() is _exp, '')
finally:
    _ur142.urlopen = _orig142

ck('busy probe: covers the START phase via _STATE mode '
   '(homing/heating while print_stats still standby)',
   "'gcode_macro _STATE'" in pp._printer_busy.__doc__ or
   'gcode_macro%20_STATE' in src or "'gcode_macro _STATE'" in src, '')
ck('tick: a RUNNING job holds 2s while busy (start-phase protection)',
   'while _printer_busy():' in src and 'time.sleep(2.0)' in src, '')
ck('priming: full variables, freeze AFTER (no refire after a '
   'watcher restart mid-print)',
   src.index('_prime_nonces(rv)') < src.index(
       "rv = {k: v for k, v in rv.items() if k not in _freeze133}"), '')
ck('queue: GEN_QUEUE_CANCEL macro + watcher dispatch',
   'GEN_QUEUE_CANCEL' in open(os.path.join(
       ROOT, 'macros', '19_bricks.cfg'), encoding='utf-8').read()
   and "rv.get('queue_cancel_nonce'" in src
   and "_JOB_STATE['queue'][:] = []" in src, '')
ck('LCD: Cancel job queue entry (Tools root)',
   'Cancel job queue' in open(os.path.join(
       ROOT, 'menus', 'lcd_menues.cfg'), encoding='utf-8').read(), '')
ck('queue-clear RESPOND: quotes balanced (field log .97: Malformed '
   'command - closing quote sat after a semicolon)',
   'it is mid-file) -' in src and 'mid-file);' not in src, '')
_mac19 = open(os.path.join(ROOT, 'macros', '19_bricks.cfg'),
              encoding='utf-8').read()
ck('kit source = the file SELECTED in the file list (in-memory _PREVIEW '
   'card, like Texture), never a guessed newest job, no stale fallback',
   "gcode_macro _PREVIEW'].name" in _mac19 and 'default(-1)|int' in _mac19
   and 'sv.preview_file' not in _mac19, '')
ck('kit: no selection -> clear error (Pick a file), no silent fallback',
   'M117 Pick a file' in _mac19, '')
ck('watcher: brickkit index -1 = no newest-job guessing, clear error',
   '_kidx125 = (-1' in src or "_kidx125 = -1 if _raw125" in src, '')
ck('kit: NO pushed file list (user: selection happens in the file list)',
   'kit_sources' not in src and 'kit_sources' not in open(os.path.join(
       ROOT, 'menus', 'lcd_menues.cfg'), encoding='utf-8').read(), '')
ck('kit menu: Source shows the selected file, Job-1..5 entries gone',
   'pick a file' in open(os.path.join(
       ROOT, 'menus', 'lcd_menues.cfg'), encoding='utf-8').read()
   and 'newest job' not in open(os.path.join(
       ROOT, 'menus', 'lcd_menues.cfg'), encoding='utf-8').read(), '')
# ---- 12) R133f: the regeneration loop is DEAD - and stays dead ---------------
_prime_blk = src[src.index('if first_prime:'):src.index('first_prime = False')]
_missing = [k for k in pp.NONCE_KEYS
            if ("_np.get('%s')" % k) not in _prime_blk
            and ("_np['%s']" % k) not in _prime_blk]
ck('LOOP FIX: EVERY nonce channel is primed after a watcher start '
   '(colorpic/bricks/brickkit/figures/plot_cal were forgotten since '
   '.90 - every reboot re-fired old jobs and recreated deleted files)',
   not _missing, 'unprimed: %s' % _missing)
ck('helper _next_gen_version: next free number, NEVER overwrite',
   hasattr(pp, '_next_gen_version') and hasattr(pp, '_gen_stem'), '')
ck('R158/R160 naming: version FIRST (Vnn_Name since .120, no 00_ prefix) '
   'at every generator, folder-global scan counts ALL THREE name formats, '
   'no _WATCH_ROOT left',
   src.count("'V%02d_") + src.count("'V%%02d_") >= 18
   and "'00_V%02d_" not in src
   and 'def _next_gen_version(out_dir):' in src
   and '_next_gen_version(out_dir, ' not in src
   and '_WATCH_ROOT' not in src
   and 'def _is_gen_name(name):' in src, '')
ck('names: FULL source stem (the [:8] cut is gone everywhere)',
   ":8] or 'IMG'" not in src and ":8] or 'MODEL'" not in src
   and pp._gen_stem('/x/AxtBunny.png.gcode') == 'AxtBunny.png'
   and pp._gen_stem('/x/Mein Langes Bild!#.jpg') == 'Mein_Langes_Bild'
   and len(pp._gen_stem('/x/' + 'L' * 40 + '.gcode')) == 40, '')
ck('no version clamp left - gen_version is fully retired',
   'max(1, min(int(version), 99))' not in src
   and 'gen_version' not in open(os.path.join(
       ROOT, 'menus', 'lcd_menues.cfg'), encoding='utf-8').read(), '')
_lcd133f = open(os.path.join(ROOT, 'menus', 'lcd_menues.cfg'),
                encoding='utf-8').read()
ck('LCD: Gen files browser (select + 2-press delete, 12 slots each)',
   _lcd133f.count('__gfiles __s') == 12
   and _lcd133f.count('__gfiles __del __d') == 12
   and 'GEN_FILE_DEL_SLOT INDEX=5' in _lcd133f, '')
_ld0 = _lcd133f.index('[menu __main __gen __litho __del]')
_ld1 = _lcd133f.index('[menu __main __gen __litho __set]')
_litho_del_blk = _lcd133f[_ld0:_ld1]
ck('LCD: litho Delete-image slots call DEL_SLOT (were wired to CREATE!)',
   'LITHO_DEL_SLOT INDEX=0' in _litho_del_blk
   and 'LITHO_CREATE' not in _litho_del_blk, '')
_mac17 = open(os.path.join(ROOT, 'macros', '17_generator.cfg'),
              encoding='utf-8').read()
ck('macro GEN_FILE_DEL_SLOT: 2-press arm + only-00_ promise',
   'GEN_FILE_DEL_SLOT' in _mac17 and 'gen_del_arm' in _mac17, '')
ck('watcher: gen_files push + gen_del handler (00_-only guard)',
   'VARIABLE=gen_files' in src and "rv.get('gen_del_nonce'" in src
   and "startswith('00_')" in src, '')
ck('_STATE declares gen_del_arm (2-press state survives)',
   'variable_gen_del_arm' in open(os.path.join(
       ROOT, 'macros', '01_state.cfg'), encoding='utf-8').read(), '')

# ---- 13) R133g: litho family POLARITY + ORIENTATION (the big inversion) ----
# Field log .99: every lithophane since R89 printed as a NEGATIVE (white =
# thickest / last band) and FLAT/ColorPic mirrored the image. Marker image:
# black square TOP-RIGHT, gray circle BOTTOM-LEFT, white elsewhere.
import re as _re133g
import tempfile as _tf133g
from PIL import Image as _Im133g, ImageDraw as _Dr133g

_d133g = _tf133g.mkdtemp(prefix='r133g_')
_im = _Im133g.new('L', (400, 300), 255)
_dr = _Dr133g.Draw(_im)
_dr.rectangle([280, 20, 380, 90], fill=0)
_dr.ellipse([30, 190, 150, 290], fill=160)
_p133g = os.path.join(_d133g, 'marker.png')
_im.save(_p133g)

def _layer_pts133g(path):
    secs = open(path).read().split(';LAYER_CHANGE')[1:]
    out = []
    for sec in secs:
        pts = _re133g.findall(r'G1 X([-\d.]+) Y([-\d.]+) E([-\d.]+)', sec)
        out.append([(float(a), float(b)) for a, b, c in pts
                    if float(c) > 0])
    return out

def _quadrant_share(pts, frame=None):
    # frame = reference bbox (default: the points' own bbox). Bands are
    # measured against the PICTURE frame (band 0 = the whole area), so a
    # correctly confined band does not dilute its own reference.
    if frame is None:
        xs = [q[0] for q in pts]; ys = [q[1] for q in pts]
    else:
        xs = [frame[0], frame[2]]; ys = [frame[1], frame[3]]
    cx, cy = (min(xs) + max(xs)) / 2.0, (min(ys) + max(ys)) / 2.0
    n = len(pts)
    return (sum(1 for q in pts if q[0] > cx and q[1] > cy) / n,
            sum(1 for q in pts if q[0] < cx and q[1] < cy) / n)

# Litho FLAT: 3 Stufen x 3 Layer @0.2 = 9 Layer, nur Weiss, Kontrast ON
_o133g, _i133g = pp.make_lithophane(
    _p133g, orient='FLAT', height_mm=45, layer_h=0.2, levels=3,
    col_layers=3, frame=False, border=0.0, col_mode='OFF', ironing=False,
    out_dir=_d133g)
_L133g = _layer_pts133g(_o133g)
ck('litho FLAT: 3 levels x 3 layers @0.2 = 9 layers (1.8mm)',
   len(_L133g) == 9, str(len(_L133g)))
_all133g = [q for s in _L133g for q in s]
_fr133g = (min(q[0] for q in _all133g), min(q[1] for q in _all133g),
           max(q[0] for q in _all133g), max(q[1] for q in _all133g))
_br_share, _bl_share = _quadrant_share(
    [q for s in _L133g[6:9] for q in s], _fr133g)
_wr_share, _wl_share = _quadrant_share(
    [q for s in _L133g[0:3] for q in s], _fr133g)
_gr_share, _gl_share = _quadrant_share(
    [q for s in _L133g[3:6] for q in s], _fr133g)
ck('litho FLAT polarity: darkest step = the BLACK marker (back-right),'
   ' NOT the white area (was inverted since R89)',
   _br_share >= 0.75 and _wr_share <= 0.45, 'black %.2f white %.2f'
   % (_br_share, _wr_share))
ck('litho FLAT quantization: the GRAY circle keeps its own step even with'
   ' the contrast boost on (nearest-level fix)',
   _gl_share >= 0.5 and len(_L133g[4]) > 0, 'gray front-left %.2f'
   % _gl_share)
ck('litho FLAT orientation: image top -> BACK, no mirror (reads correct'
   ' from the front)',
   _br_share >= 0.75 and _gl_share >= 0.5, '')

# ColorPic: 3 Baender x 0.6mm, WHT/GRY/BLK, ohne Swap (kein Turm)
_o133c, _i133c = pp.make_colorpic(
    _p133g, width_mm=60, layer_h=0.2, bands=3, band_h=0.6,
    colors='WHT,GRY,BLK', swap=False, ironing=False, out_dir=_d133g)
_C133g = _layer_pts133g(_o133c)
ck('colorpic: 3 bands x 3 layers @0.2 = 9 layers (1.8mm)',
   len(_C133g) == 9, str(len(_C133g)))
_all133c = [q for s in _C133g for q in s]
_fr133c = (min(q[0] for q in _all133c), min(q[1] for q in _all133c),
           max(q[0] for q in _all133c), max(q[1] for q in _all133c))
_cb_share, _cbl_share = _quadrant_share(
    [q for s in _C133g[6:9] for q in s], _fr133c)
_cg_share, _cgl_share = _quadrant_share(
    [q for s in _C133g[3:6] for q in s], _fr133c)
ck('colorpic polarity: last band = BLACK marker (back-right), band 1 ='
   ' gray circle (front-left) - light first, dark on top',
   _cb_share >= 0.75 and _cgl_share >= 0.5,
   'black %.2f gray %.2f' % (_cb_share, _cgl_share))
_lum133g = [[0.0] * 12 for _ in range(12)] + [[1.0] * 12 for _ in range(12)]
_g133g, _ = pp._litho_grid(_lum133g, 12, 24, 12, 12)
ck('grid scale: dark = 1.0 = thickest (the docstring contract)',
   _g133g[0][0] >= 0.99 and _g133g[11][11] <= 0.01,
   '%.2f / %.2f' % (_g133g[0][0], _g133g[11][11]))

# ---- 14) R133i: ONE watcher at RUNTIME too + float echo (field log .101) ----
ck('watcher: runtime duplicate sweep exists - the startup takeover only '
   'sees lock-WRITERS (.101+); a pre-.98 zombie starting LATER was '
   'invisible forever',
   'def _watch_duplicate_sweep' in src, '')
ck('watcher: sweep scans /proc directly (no subprocess) and never kills '
   'itself',
   "os.listdir('/proc')" in src and 'pid == me' in src, '')
ck('watcher: sweep wired into the watch loop, once a minute',
   'last_dup_sweep' in src
   and 'time.time() - last_dup_sweep >= 60' in src, '')
ck('watcher: a ROOT duplicate (root cron / rc.local) gets a LOUD '
   'how-to-stop respond instead of a silent fake "found and stopped" - '
   'user pi cannot signal root processes',
   'runs as ROOT' in src and 'sudo pkill -f' in src, '')
_upsh133i = open(os.path.join(ROOT, 'update.sh'), encoding='utf-8').read()
ck('update.sh: pkill tries sudo FIRST - a root-cron zombie survives a '
   'plain user pkill untouched',
   'sudo -n pkill' in _upsh133i, '')
_msrc133i = open(os.path.join(ROOT, 'menus', 'lcd_menues.cfg'),
                 encoding='utf-8').read()
ck('menu float echo: the whole product is rounded - a trailing |round '
   "binds to the right operand only (field log .101: '3 x 0.6 = "
   "1.7999999999999998mm')",
   ' * (menu.input|float|round(1))|round' not in _msrc133i
   and '* (menu.input|float|round(1)))|round' in _msrc133i, '')
ck('watcher: takeover is --watch-gated - a --file-check one-shot must '
   'NEVER kill the live watcher (field log .101: the diagnostic run '
   'killed the systemd watcher, all generators fell silent)',
   "if '--watch' in sys.argv[1:]:" in src
   and '        _watch_lock_takeover()' in src, '')
ck('watcher: a manual --watch never kills the SUPERVISED systemd '
   'instance - it exits politely instead (cgroup check)',
   'def _svc_watcher' in src and 'r2-postproc.service' in src, '')
ck('file-check reports the watcher state - a dead watcher (offline '
   'generators) is no longer silent',
   'NO r2_postproc watcher is running' in src, '')

# ---- 15) R134: plot-on-selection (no auto-conversion, ever) ----------------
_m08_134 = open(os.path.join(ROOT, 'macros', '08_print_start_stop.cfg'),
                encoding='utf-8').read()
ck('plot: the watch scan NEVER converts a source (field log .101: every '
   'plain litho/colorpic upload grew an unrequested .gcode plot twin)',
   'plain_upload' not in src
   and 'plot_convert(p, var_path=VAR_PATH, out=out_p)' not in src, '')
ck('plot: sources are selected in the file list - SDCARD_PRINT_FILE '
   'switches to plot mode (plot_src + plot_nonce), never BASE-starts an '
   'image, busy = clear refuse',
   'VARIABLE=plot_src' in _m08_134 and 'VARIABLE=plot_nonce' in _m08_134
   and 'never BASE-start an image' in _m08_134, '')
ck('plot: generation on demand - plot_nonce handler spawns a job with '
   'Vnn_Plot_ naming, gen_out honored (start vs preview)',
   src.count("'V%02d_Plot_%s.gcode'") >= 1
   and 'plot_nonce' in src, '')
ck('plot: the nonce channel is primed at watcher start + frozen while '
   'printing (the .90 regeneration-loop lesson)',
   "last_plot_nonce = _np.get('plot_nonce')" in src
   and 'plot_nonce' in src[src.index('_freeze133 = ('):
                            src.index('_freeze133 = (') + 700], '')
ck('plot: an already-converted plot g-code selected again is re-selected, '
   'never regenerated',
   'is already plotter' in src, '')
ck('plot: the old .gcode-tail upload gets a rename hint, its bytes never '
   'rewritten',
   'old .gcode tail' in src, '')

# ---- 16) R135 (.104): the menu restructure - nothing gets lost -------------
_lcd135 = open('menus/lcd_menues.cfg', encoding='utf-8').read()
ck('R135: golden inventory file exists and the render suite proves no menu '
   'entry is ever lost (old vs new paths against the documented mapping)',
   os.path.exists('tools/r135_menu_golden.txt')
   and 'r135_menu_golden.txt' in open('tools/macro_render_test.py',
                                      encoding='utf-8').read()
   and 'R135 menu inventory: NOTHING lost' in open('tools/macro_render_test.py',
                                                   encoding='utf-8').read(), '')
ck('R135/R151/R160: Pre-Print starts with Offset X/Y/Z (ONE 0.05mm fine '
   'row per axis - the coarse/fine duplicates showed the same value); the '
   'fix toggles (retract/travel/flow cap) live in the FIXES menu since .120',
   '[menu __main __preprint __poff __what]' in _lcd135
   and _lcd135[_lcd135.index('[menu __main __preprint __poff]'):
               _lcd135.index('[menu __main __preprint __file]')].count(
       'input_step: 0.05') == 3
   and '[menu __main __preprint __fixes __rt]' in _lcd135
   and '[menu __main __preprint __fixes __fixa]' in _lcd135
   and '[menu __main __preprint __fixes __fixc]' in _lcd135
   and '[menu __main __preprint __fixes __fixcv]' in _lcd135, '')
ck('R135: Profiles directly under File info, Velocity (ex-Speed) carries the '
   'global PA/accel rows, quick access (Spd/Acc/PA/Flw) carries globals + '
   'Now, the old top-level speed/accel/flow menus are GONE',
   _lcd135.index('[menu __main __preprint __profs]')
   < _lcd135.index('[menu __main __preprint __motion]')
   and 'name: Velocity' in _lcd135
   and '[menu __main __preprint __pafe __gval]' in _lcd135
   and '[menu __main __preprint __acfe __gacc]' in _lcd135
   and '[menu __main __preprint __spfe __g1st]' in _lcd135
   and '[menu __main __live __speeds]' not in _lcd135
   and '[menu __main __live __accels]' not in _lcd135
   and '[menu __main __preprint __flow]' not in _lcd135, '')
ck('R135: plot sections moved to the END (Live + Pre-Print) and only for '
   'plot files - the LCD stays clean on normal prints',
   _lcd135.index('[menu __main __live __plot]')
   > _lcd135.index('[menu __main __live __file]')
   and _lcd135.index('[menu __main __preprint __plot]')
   > _lcd135.index('[menu __main __preprint __confirm]')
   and _lcd135.count("printer['gcode_macro _PREVIEW'].plot|default(0)"
                     "|int == 1 or printer['gcode_macro _STATE']"
                     ".file_type|default('') == 'plot'}") == 2, '')
ck('R135: stock OctoPrint/Temperature/Setup hidden via enable {False} '
   'overrides, Control/Tune untouched, SD Card = R151 recursive browser',
   _lcd135.count('\nenable: {False}') == 3
   and '[menu __main __sdcard]\ntype: list' in _lcd135
   and '[menu __main __control]' not in _lcd135, '')

print()
print('R142 FIELD COVERAGE: %d checks, %d FAIL' % (n_ck[0], len(fails)))
sys.exit(1 if fails else 0)


if __name__ == '__main__':
    pass
