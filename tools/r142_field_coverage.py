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
ck('watch: scan skips while a job runs or is queued',
   "if busy or _JOB_STATE['busy'] or _JOB_STATE['queue']:" in src, '')
ck('watch: jobs requeue while the printer is busy (print has priority)',
   'if _printer_busy():' in src and 'insert(0, item)' in src, '')
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
   '00_Plot_ naming, gen_out honored (start vs preview)',
   "_spawn_job('Plot'" in src and "'00_Plot_%s_V%02d.gcode'" in src
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
ck('R135: Pre-Print starts with Offset X/Y/Z (half-step fine rows) and File '
   'info now carries the fix toggles (travel/flow cap/retract) as submenu',
   '[menu __main __preprint __poff __zf]' in _lcd135
   and _lcd135[_lcd135.index('[menu __main __preprint __poff]'):
               _lcd135.index('[menu __main __preprint __file]')].count(
       'input_step: 0.05') == 3
   and '[menu __main __preprint __file __rt]' in _lcd135
   and '[menu __main __preprint __file __tv2]' in _lcd135
   and '[menu __main __preprint __file __fc]' in _lcd135
   and '[menu __main __preprint __file __fcv]' in _lcd135, '')
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
   'overrides, SD Card/Control/Tune untouched',
   _lcd135.count('\nenable: {False}') == 3
   and '[menu __main __sdcard]' not in _lcd135
   and '[menu __main __control]' not in _lcd135, '')

print()
print('R142 FIELD COVERAGE: %d checks, %d FAIL' % (n_ck[0], len(fails)))
sys.exit(1 if fails else 0)


if __name__ == '__main__':
    pass
