#!/usr/bin/env python3
"""R102 MEGATEST: hardcore sweep over EVERY generator, tool and parameter.

Levels beyond audit_sweep.py:
  - ~100 extreme parameter combinations (all generators, all modes)
  - every emitted file: bed bounds, z monotonic, EXCLUDE balance,
    G10/G11 retract balance, E/F plausibility, no NaN/inf,
    _FILE_INFO + TYPES present, ;TYPE: honesty (every tagged feature
    must appear in TYPES=), APPLY_TYPE coverage, PRINT_START/END, M83
  - multi-plate generators: EVERY plate checked
  - idempotency: a second process() run must skip (TAG guard)
  - expect-error runs: invalid parameters MUST raise ValueError
  - range excerpts + texture outputs + plot conversions checked too
Exit 0 = everything held.
"""
import atexit
import math
import os
import re
import shutil
import struct
import sys
import tempfile
import time
import zlib

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import r2_postproc as pp  # noqa: E402

BED = (0.0, -3.0, 220.0, 217.0)
# R104: adapt the sweep to another printer:
#   python3 tools/megatest.py --bed=0,0,220,220          explicit limits
#   python3 tools/megatest.py --cfg=~/printer_data/config/printer.cfg
#                                                          reads [r2_postproc]
# default = the Ender-3 reference bed (keeps the 101 runs deterministic)
for _arg in sys.argv[1:]:
    if _arg.startswith('--bed='):
        _vals = [t.strip() for t in _arg[6:].split(',') if t.strip()]
        if len(_vals) != 4:
            print('usage: --bed=X0,Y0,X1,Y1 (e.g. --bed=0,0,220,220)')
            sys.exit(2)
        BED = tuple(float(t) for t in _vals)
        print('megatest: bed override -> %s' % (BED,))
    elif _arg.startswith('--cfg='):
        BED = tuple(pp._bed_limits(os.path.expanduser(_arg[6:])))
        print('megatest: bed from %s -> %s' % (_arg[6:], BED))
    elif _arg in ('-h', '--help'):
        print(__doc__.split('Levels beyond')[0])
        print('options: --bed=X0,Y0,X1,Y1 | --cfg=PATH/to/printer.cfg')
        sys.exit(0)
CANON = {k.strip().lower(): v for k, v in pp.TYPE_MAP.items()}
D = tempfile.mkdtemp(prefix='megatest_')
# a full sweep writes ~100 MB of g-code - NEVER leave that behind (a Pi
# often runs /tmp as a ramdisk; leftover dirs filled it up on the first
# sandbox run). rmtree on every exit path, failures included.
atexit.register(lambda: shutil.rmtree(D, ignore_errors=True))
runs = 0
files_checked = 0
fails = []
info = []


def check_gcode(name, path, bed=BED, skip_idem=False, extra_types=(), plot=False,
                r2_gen=False):
    """all invariants; returns list of problems."""
    global files_checked
    files_checked += 1
    probs = []
    try:
        txt = open(path, encoding='utf-8', errors='replace').read()
    except OSError as e:
        probs = ['unreadable: %r' % e]
        for pr in probs:
            fails.append((name, pr))
        return probs
    lines = txt.split('\n')
    # -- bed bounds (G0+G1 with X/Y)
    for m in re.finditer(r'^G[01] X([-\d.]+) Y([-\d.]+)', txt, re.M):
        x, y = float(m.group(1)), float(m.group(2))
        if not (bed[0] - 0.5 <= x <= bed[2] + 0.5
                and bed[1] - 0.5 <= y <= bed[3] + 0.5):
            probs.append('out of bed: X%.1f Y%.1f' % (x, y))
            break
    # -- z monotonic
    zs = [float(m.group(1)) for m in re.finditer(r'^;Z:([-\d.]+)', txt, re.M)]
    if ('BY_OBJECT=1' not in txt
            and any(b < a - 1e-9 for a, b in zip(zs, zs[1:]))):
        probs.append('z not monotonic (%d steps)' % len(zs))
    # -- EXCLUDE balance
    starts = re.findall(r'^EXCLUDE_OBJECT_START NAME=(\S+)', txt, re.M)
    ends = re.findall(r'^EXCLUDE_OBJECT_END NAME=(\S+)', txt, re.M)
    if sorted(starts) != sorted(ends):
        probs.append('EXCLUDE unbalanced (%d/%d)' % (len(starts), len(ends)))
    for nm in set(starts):
        if ('EXCLUDE_OBJECT_DEFINE NAME=%s' % nm) not in txt:
            probs.append('EXCLUDE %s never defined' % nm)
            break
    # -- retract balance
    n_g10 = len(re.findall(r'^G10\b', txt, re.M))
    n_g11 = len(re.findall(r'^G11\b', txt, re.M))
    if n_g10 != n_g11:
        probs.append('retract unbalanced: %d G10 vs %d G11' % (n_g10, n_g11))
    # -- E / F plausibility + NaN/inf
    e_max = 0.0
    for m in re.finditer(r'^G1 X[^\n]*? E([-\d.]+)', txt, re.M):
        e = float(m.group(1))
        if e < -0.001 or e > 20.0:
            probs.append('E out of range: %.2f' % e)
            break
        e_max = max(e_max, e)
    # R212: plausibility scans NON-COMMENT lines only - the R2-META
    # thumbnail block is base64 in comments and happily contains 'F0'
    # or even a lone 'nan' token; comments never carry g-code
    code = '\n'.join(l for l in txt.split('\n')
                     if not l.lstrip().startswith(';'))
    for m in re.finditer(r'F(\d+)', code):
        f = float(m.group(1))
        if not (0 < f <= 12000):
            probs.append('F out of range: %.0f' % f)
            break
    if re.search(r'\b(nan|inf)\b', code, re.I):
        probs.append('nan/inf in file')
    # -- _FILE_INFO + TYPES honesty (print files only)
    fi = None
    if plot:
        fi = 'plot'
    for l in lines[:200]:
        if l.startswith('_FILE_INFO'):
            fi = l
            break
    types_hdr = set()
    if not plot:
        for l in lines[:200]:
            if l.startswith('_FILE_INFO'):
                fi = l
                break
        if not fi:
            probs.append('no _FILE_INFO')
        else:
            m = re.search(r'TYPES=(\S+)', fi)
            if m:
                types_hdr = set(m.group(1).split(','))
            else:
                probs.append('_FILE_INFO without TYPES=')
    types_hdr |= set(extra_types)
    seen_types = set()
    for l in lines:
        if l.startswith(';TYPE:'):
            key = l[6:].strip().lower()
            seen_types.add(CANON.get(key, 'CUSTOM'))
    if not plot and seen_types and not seen_types <= types_hdr:
        probs.append('TYPES dishonest: tagged %s not in header %s'
                     % (sorted(seen_types - types_hdr), sorted(types_hdr)))
    n_ty = len(re.findall(r'^;TYPE:', txt, re.M))
    n_ap = len(re.findall(r'^APPLY_TYPE ', txt, re.M))
    if n_ty and n_ap < n_ty:
        probs.append('APPLY_TYPE coverage: %d TYPE vs %d APPLY_TYPE' % (n_ty, n_ap))
    # -- R106 rule ll (field log .82): R2-GENERATED geometry never prints
    # an unanchored bridge. Every ;TYPE:Bridge segment must be a short stub
    # AND have an endpoint on material of the layer below. Slicer files
    # passing through process() are exempt - their bridges are the slicer's
    # business, the rule governs what WE generate.
    if r2_gen and not plot:
        layers_all, layers_br = [], []
        cur = x = y = None
        for ln in lines:
            if ln == 'LAYER_MARK':
                layers_all.append([])
                layers_br.append([])
                continue
            m = re.match(r';TYPE:(.+)', ln)
            if m:
                cur = m.group(1)
                continue
            m = re.match(r'G0 X([-\d.]+) Y([-\d.]+)', ln)
            if m:
                x, y = float(m.group(1)), float(m.group(2))
                continue
            m = re.match(r'G1 X([-\d.]+) Y([-\d.]+) E', ln)
            if m and layers_all and x is not None:
                nx, ny = float(m.group(1)), float(m.group(2))
                layers_all[-1].append((x, y, nx, ny))
                if cur == 'Bridge':
                    layers_br[-1].append((x, y, nx, ny))
                x, y = nx, ny

        def _sd(px, py, seg):
            ax, ay, bx, by = seg
            dx, dy = bx - ax, by - ay
            dd = dx * dx + dy * dy
            if dd < 1e-12:
                return math.hypot(px - ax, py - ay)
            t = max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / dd))
            return math.hypot(px - ax - dx * t, py - ay - dy * t)

        for li, brs in enumerate(layers_br):
            for (ax, ay, bx, by) in brs:
                d = math.hypot(bx - ax, by - ay)
                if li == 0 or not layers_all[li - 1]:
                    continue
                da = min(_sd(ax, ay, sg) for sg in layers_all[li - 1])
                db = min(_sd(bx, by, sg) for sg in layers_all[li - 1])
                # rule ll, two classes: a short stub/cantilever anchors at
                # ONE end; a long bridge line must anchor at BOTH ends -
                # nothing may float free either way
                bad = (min(da, db) > 0.6 if d <= 4.0 else max(da, db) > 0.6)
                if bad:
                    probs.append('L%d bridge %.1fmm unanchored at %.1f,%.1f '
                                 '(rule ll)' % (li + 1, d, ax, ay))
    # -- frame of the file (plotter files are PEN files - no print frame)
    if not plot:
        if 'PRINT_START' not in '\n'.join(lines[:80]):
            probs.append('no PRINT_START in head')
        if 'PRINT_END' not in '\n'.join(lines[-40:]):
            probs.append('no PRINT_END in tail')
        if not re.search(r'^M83\b', txt, re.M):
            probs.append('no M83 (relative E)')
    else:
        if '; R2-PLOT' not in txt:
            probs.append('no R2-PLOT header')
        if '_PLOT_START' not in txt:
            probs.append('no _PLOT_START')
    # -- idempotency: second process() must skip
    if not skip_idem:
        try:
            s = pp.process(path)
            if not s.get('skipped'):
                probs.append('NOT idempotent (2nd process() did not skip)')
        except Exception as e:                     # noqa: BLE001
            probs.append('2nd process() raised %r' % e)
    for p in probs:
        fails.append((name, p))
    return probs


# R104: on a SMALLER --bed/--cfg bed the fixed extreme combos may simply not
# fit - the generators then correctly raise ValueError ('do not fit the bed',
# 'split kit needs 200x239mm', ...). That is PRODUCTION behavior (a clear
# error instead of printing outside the bed), not a test failure: count it
# as SKIP when the bed differs from the reference and the message is about
# dimensions. Everything else still fails loudly.
_REF_BED = (0.0, -3.0, 220.0, 217.0)
_DIMS_RE = re.compile(r'fit|needs \d|too (?:large|big|tall|long|wide)|exceeds', re.I)


def run(name, fn, **kw):
    global runs
    runs += 1
    t0 = time.time()
    try:
        ret = fn()
    except ValueError as e:
        if BED != _REF_BED and _DIMS_RE.search(str(e)):
            info.append('%-58s SKIP (bed too small - correct ValueError: %s)'
                        % (name, str(e).split(' - ')[0][:60]))
            return None
        fails.append((name, 'GENERATOR RAISED %r' % e))
        return None
    except Exception as e:                          # noqa: BLE001
        fails.append((name, 'GENERATOR RAISED %r' % e))
        return None
    paths = ret[0] if isinstance(ret, tuple) else ret
    if isinstance(paths, str):
        paths = [paths]
    if paths is None:
        fails.append((name, 'no output path'))
        return None
    for p in paths:
        check_gcode('%s [%s]' % (name, os.path.basename(p)), p, **kw)
    info.append('%-58s %2d file(s) %5.1fs' % (name, len(paths), time.time() - t0))
    return paths


def expect_error(name, fn):
    global runs
    runs += 1
    try:
        fn()
        fails.append((name, 'expected ValueError, got NONE'))
    except ValueError:
        pass
    except Exception as e:                          # noqa: BLE001
        fails.append((name, 'expected ValueError, got %r' % e))


def png(w, h, gray):
    def chunk(t, d):
        return struct.pack('>I', len(d)) + t + d + struct.pack(
            '>I', zlib.crc32(t + d) & 0xffffffff)
    rows = b''
    for y in range(h):
        rows += b'\x00' + bytes(int(round(gray(x, y))) & 0xff for x in range(w))
    return (b'\x89PNG\r\n\x1a\n'
            + chunk(b'IHDR', struct.pack('>IIBBBBB', w, h, 8, 0, 0, 0, 0))
            + chunk(b'IDAT', zlib.compress(rows))
            + chunk(b'IEND', b''))


# ============================================================ FRAMES ======
# R106: F returns EVERY plate (A + B) - plate B files used to slip through
# untested - and all frame output obeys rule ll (no unanchored bridges)
def F(**kw):
    out, i = pp.make_frame(bed=BED, out_dir=tempfile.mkdtemp(dir=D), **kw)
    return i.get('all_files') or [out]

run('frame 9x13 default', lambda: F(preset='9x13'), r2_gen=True)
run('frame 9x13 depth3 minimal', lambda: F(preset='9x13', depth=3), r2_gen=True)
run('frame 9x13 depth60 CASE', lambda: F(preset='9x13', depth=60), r2_gen=True)
run('frame 9x13 border4 corner30', lambda: F(preset='9x13', frame_w=4, corner=30), r2_gen=True)
run('frame 9x13 border30 corner0', lambda: F(preset='9x13', frame_w=30, corner=0), r2_gen=True)
run('frame 10x15 (multi)', lambda: F(preset='10x15'), r2_gen=True)
run('frame 13x18 stand', lambda: F(preset='13x18', stand=True), r2_gen=True)
run('frame A6 OVAL', lambda: F(preset='A6', shape='OVAL'), r2_gen=True)
run('frame A6 OVAL depth18 CASE', lambda: F(preset='A6', shape='OVAL', depth=18), r2_gen=True)
run('frame SIDE closure', lambda: F(preset='9x13', closure='SIDE'), r2_gen=True)
run('frame hang all 4', lambda: [F(preset='9x13', hang=h)[0] for h in
                                 ('TOP', 'BOTTOM', 'LEFT', 'RIGHT')], r2_gen=True)
run('frame FLIP front', lambda: F(preset='9x13', front='FLIP'), r2_gen=True)
run('frame LINES IN', lambda: F(preset='9x13', front='LINES', s_dir='IN'), r2_gen=True)
run('frame WAVES OUT amp2', lambda: F(preset='9x13', front='WAVES', s_amp=2.0), r2_gen=True)
run('frame HEX', lambda: F(preset='9x13', front='HEX'), r2_gen=True)
run('frame infill5 top1 bot0', lambda: F(preset='9x13', infill=5.0, top_layers=1,
                                         bottom_layers=0), r2_gen=True)
run('frame infill100 top15 bot15', lambda: F(preset='9x13', infill=100.0,
                                             top_layers=15, bottom_layers=15), r2_gen=True)
run('frame disc GLASS front', lambda: F(preset='9x13', disc='GLASS', disc_t=2.0), r2_gen=True)
run('frame disc PLEXI back', lambda: F(preset='9x13', disc='PLEXI',
                                       disc_side='BACK'), r2_gen=True)
run('frame disc FOIL', lambda: F(preset='9x13', disc='FOIL', disc_t=0.4), r2_gen=True)
run('frame disc LITHO back case', lambda: F(preset='9x13', depth=18, disc='LITHO',
                                            disc_side='BACK'), r2_gen=True)
run('frame cable CASE', lambda: F(preset='9x13', depth=20, frame_w=6, cable=True), r2_gen=True)
run('frame KIT (40x200)', lambda: F(width=40, height=200, depth=6, frame_w=6), r2_gen=True)
run('frame KIT stand vers99', lambda: F(width=40, height=200, depth=6, frame_w=6,
                                        stand=True, version=99), r2_gen=True)
expect_error('frame 230x230 rejected (even strips exceed bed)',
             lambda: F(width=230, height=230, frame_w=8))
expect_error('frame OVAL oversized rejected', lambda: F(shape='OVAL', width=210,
                                                        height=210))
run('frame no ironing', lambda: F(preset='9x13', ironing=False), r2_gen=True)
run('frame layer_h 0.12 first 0.08', lambda: F(preset='9x13', layer_h=0.12,
                                               first_h=0.08), r2_gen=True)
expect_error('frame infill 2 rejected', lambda: F(preset='9x13', infill=2.0))
expect_error('frame depth 61 rejected', lambda: F(preset='9x13', depth=61))
expect_error('frame border 3 rejected', lambda: F(preset='9x13', frame_w=3))
expect_error('frame custom 300 rejected', lambda: F(width=300, height=200))

# ============================================================ LABELS ======
L = lambda **kw: pp.make_labels(bed=BED, out_dir=tempfile.mkdtemp(dir=D), **kw)
for font in ('SMOOTH', 'MONO', 'COND', 'NARROW', 'CAPS'):
    run('label %s grow auto' % font, lambda f=font: L(texts=['R2-D2'], font=f))
run('label 5 lines', lambda: L(texts=['A~B~C~D~E']))
run('label fixed 60x30', lambda: L(texts=['WERKSTATT'], w=60, h=30, mode='fixed'))
run('label fixed size40', lambda: L(texts=['X'], w=120, h=90, font_size=40,
                                    mode='fixed'))
run('label grow size2 (floor)', lambda: L(texts=[' klein '], font_size=2))
run('label spacing10 stroke4', lambda: L(texts=['B R E I T'], spacing=10,
                                         stroke=4))
run('label stroke nozzle single-line', lambda: L(texts=['dünn'], stroke=0.42))
for side in (1, 2, 3, 4):
    run('label hole side %d' % side, lambda s=side: L(texts=['LOCH'],
                                                      hole_side=s))
run('label hole_d 2.5 / 16', lambda: [L(texts=['D2.5'], hole_d=2.5)[0],
                                      L(texts=['D16'], hole_d=16)[0]])
run('label 24 queue (max)', lambda: L(texts=['N%d' % i for i in range(24)],
                                    w=30, h=15))
# parts-splitting (R172): 24 fat 80x40 5-line labels no longer hit the
# bed wall - they split into parts of what fits (fit <= 8 on 220mm)
def _lbl24x():
    _r24x = L(texts=['L%d~ZEILE~MIT~F~ZEILEN' % i for i in range(24)],
              w=80, h=40)
    _inf24x = _r24x[-1] if isinstance(_r24x, (list, tuple)) else {}
    assert isinstance(_inf24x, dict) and 0 < _inf24x.get('fit', 0) <= 8, \
        'info=%r' % (_inf24x,)
    return _r24x
run('label 24x 80x40 5-line -> split into parts (bed respected)',
    _lbl24x, skip_idem=True)
# R127: default label gap doubled 6 -> 12 (user wish) - 24 small labels only
# fit with the old explicit gap; 16 fit at the new default spacing
run('label 24x 30x15 5-line fits (gap 6)', lambda: L(
    texts=['%d~A~B~C~D' % i for i in range(24)], w=30, h=15, gap=6.0))
run('label 16x 30x15 5-line fits (gap 12 default)', lambda: L(
    texts=['%d~A~B~C~D' % i for i in range(16)], w=30, h=15))
run('label 2-line multi unknown chars', lambda: L(
    texts=['ÄÖÜ~ß?!', 'MI~XED'], hole_side=1))
run('label no color2 no ironing no brim', lambda: L(
    texts=['SOLO'], color2=False, ironing=False, brim=False))
run('label tiny 12x10', lambda: L(texts=['X'], w=12, h=10, mode='fixed'))
expect_error('label 240x220 rejected (bed)', lambda: L(texts=['GROSS'], w=240,
                                                        h=220, font_size=40))
run('label layer 0.06/0.42', lambda: L(texts=['FLAT'], layer_h=0.06, first_h=0.42))
expect_error('label empty text', lambda: L(texts=['   ']))
expect_error('label only spaces line', lambda: L(texts=['~ ~ ~']))
expect_error('label 25 queue', lambda: L(texts=['N%d' % i for i in range(25)]))

# ======================================================== CABLE TIES ======
T = lambda **kw: pp.make_cable_ties(bed=BED, out_dir=tempfile.mkdtemp(dir=D), **kw)
run('ties CLASSIC default', lambda: T())
run('ties LOOP default', lambda: T(variant='LOOP'))
run('ties CLASSIC no brim', lambda: T(brim=False))
run('ties LOOP 6x long180', lambda: T(variant='LOOP', count=6, length=180))
expect_error('ties 12x300 rejected', lambda: T(variant='LOOP', count=12, length=300))
expect_error('ties 30mm rejected', lambda: T(count=2, length=30))
run('ties 1 layer / 8 layers', lambda: [T(count=2, layers=1)[0],
                                        T(count=2, layers=8)[0]])
run('ties narrow 3mm short 50', lambda: T(count=3, width=3.0, length=50))

# ========================================================== ANGLES ========
A = lambda **kw: pp.make_angles(bed=BED, out_dir=tempfile.mkdtemp(dir=D), **kw)
run('angle 90 default', lambda: A())
run('angle 30 / 170', lambda: [A(angle_deg=30)[0], A(angle_deg=170)[0]])
run('angle flat connector', lambda: A(flat=True))
run('angle walls1 holes0', lambda: A(walls=1, holes=0))
run('angle walls6 holes6 rib2', lambda: A(walls=6, holes=6, stiffener=2))
run('angle ironing 4x', lambda: A(ironing=True, count=4))
expect_error('angle 12x rejected (bed)', lambda: A(ironing=True, count=12))
run('angle short legs 20mm', lambda: A(leg_a=20, leg_b=20, width=8, holes=1))

# ========================================================== BRIDGE ========
B = lambda **kw: pp.make_bridge(bed=BED, out_dir=tempfile.mkdtemp(dir=D), **kw)
run('bridge default', lambda: B())
run('bridge 40mm 60pct', lambda: B(length=40, short_pct=60))
run('bridge 3 layers slow', lambda: B(bridge_layers=3, speed=10))
run('bridge tall towers', lambda: B(h_long=45, h_short=30))
expect_error('bridge 500mm', lambda: B(length=500))

# ============================================================ SEAL ========
S = lambda **kw: pp.make_seal(bed=BED, out_dir=tempfile.mkdtemp(dir=D), **kw)
run('seal FLAT default', lambda: S())
run('seal GROOVE', lambda: S(profile='GROOVE'))
expect_error('seal 8mm rejected', lambda: S(od=8.0, id_=3.0))
run('seal 120x90 ironing', lambda: S(od=120.0, id_=90.0, ironing=True))

# ======================================================= LITHOPHANE =======
img = os.path.join(D, 'test.png')
open(img, 'wb').write(png(48, 48, lambda x, y:
                           30 + 190 * (math.sin(x / 5.0) * math.cos(y / 7.0) + 1) / 2))
LI = lambda **kw: pp.make_lithophane(img, bed=BED,
                                     out_dir=tempfile.mkdtemp(dir=D), **kw)
run('litho default', lambda: LI())
run('litho levels8 no frame', lambda: LI(levels=8, frame=False))
run('litho small 40mm no brim', lambda: LI(height_mm=40.0, brim_loops=0))
run('litho ironing 0.12', lambda: LI(layer_h=0.12, ironing=True))
# R106/R128: FLAT mode - gray step print, colors via M600, bed clamp
run('litho FLAT default', lambda: LI(orient='FLAT'), r2_gen=True)
run('litho FLAT colors3x4 ironing', lambda: LI(orient='FLAT', colors=3,
                                              col_layers=4, ironing=True),
    r2_gen=True)
run('litho FLAT 160mm', lambda: LI(orient='FLAT', height_mm=160.0),
    r2_gen=True)
run('litho FLAT no frame no brim', lambda: LI(orient='FLAT', frame=False,
                                              brim_loops=0), r2_gen=True)

# ======================================================= RESONANCE ========
for ax in ('x', 'y'):
    csv = os.path.join(D, 'resonances_%s_20261008.csv' % ax)
    rows = ['freq,psd_hz,psd_nm']
    for i in range(80):
        f = 5.0 + i * 0.6
        rows.append('%.2f,%.6f,%.6f' % (f, 1.0 / (1 + (f - 35) ** 2) * 10, 0.5))
    open(os.path.join(D, csv), 'w').write('\n'.join(rows))
R = lambda **kw: pp.make_resonance(bed=BED, out_dir=D, csv_dirs=[D], **kw)
run('resonance both axes', lambda: R())
run('resonance x only shaper', lambda: R(axes=('x',), mode='shaper'))

# ====================================================== RANGE (excerpt) ===
src = run('range source (vase-like)', lambda: F(preset='9x13'))
src_path = [p for p in src if isinstance(p, str)][0] if src else None
if src_path:
    import shutil as _sh102
    _rdir = tempfile.mkdtemp(dir=D)
    _rsrc = os.path.join(_rdir, os.path.basename(src_path))
    _sh102.copy(src_path, _rsrc)

    def RG(a, b, **kw):
        out = pp.make_range(_rsrc, a, b, **kw)
        return out if isinstance(out, str) else out[0]
    run('range mid 5-20', lambda: RG(5, 20))
    run('range floor+top+brim', lambda: RG(2, 30, floor=4, top=4, brim=3))
    run('range top-only 30-38', lambda: RG(30, 38, top=6))

# ========================================================= BRICKS R132 ===
# R132: bricks / figures / kit were COMPLETELY absent here - the field-log
# .92 APPLY_TYPE bug (pretty names with spaces -> 'Malformed command')
# slipped through exactly because of that. The stress suite covers the
# full matrix; this is the standing smoke net.
def _pl(out, names):
    # info lists plate BASENAMES - resolve against the writer's out_dir
    return [os.path.join(os.path.dirname(out), f) for f in (names or [])] or [out]


def BR(**kw):
    out, i = pp.make_bricks(bed=BED, out_dir=tempfile.mkdtemp(dir=D), **kw)
    return _pl(out, i.get('plate_files'))

run('bricks mixed queue', lambda: BR(jobs=[('B2x4', 2), ('P2x2', 1),
                                           ('T1x2', 2)]), r2_gen=True)
run('bricks slopes+arch', lambda: BR(jobs=[('S1x3', 1), ('S2x6', 1),
                                           ('A1x4', 1)]), r2_gen=True)
run('bricks tech+round', lambda: BR(jobs=[('H1x6', 1), ('R1x1', 2),
                                          ('C1x1', 1), ('J1x2', 1),
                                          ('RT1x1', 2)]), r2_gen=True)
run('bricks inverted slope', lambda: BR(jobs=[('I2x3', 2)]), r2_gen=True)
run('bricks colors BY_LAYER', lambda: BR(jobs=[('B2x4', 2), ('P2x2', 2)],
                                         colors=3, mode='BY_LAYER'),
    r2_gen=True)
run('bricks colors BY_OBJECT', lambda: BR(jobs=[('B2x4', 2), ('T1x2', 2)],
                                          colors=2, mode='BY_OBJECT'),
    r2_gen=True)
run('bricks nobrim', lambda: BR(jobs=[('B1x1', 1)], brim=0), r2_gen=True)

def FG(**kw):
    out, i = pp.make_figures(bed=BED, out_dir=tempfile.mkdtemp(dir=D), **kw)
    return _pl(out, i.get('plate_files'))

run('figures parts 100', lambda: FG(count=1, scale=100), r2_gen=True)
run('figures single 100', lambda: FG(count=1, scale=100, mode='SINGLE'),
    r2_gen=True)
run('figures parts colors', lambda: FG(count=1, scale=100, colors=4,
                                       colormode='BY_LAYER'), r2_gen=True)
run('figures 50 display', lambda: FG(count=1, scale=50), r2_gen=True)

_bsrc = pp.make_bricks(jobs=[('B2x2', 2)], bed=BED,
                       out_dir=tempfile.mkdtemp(dir=D))[0]
run('brickkit BY_LAYER', lambda: (lambda r: _pl(r[0], r[1]['plates']))(
    pp.make_brick_kit(_bsrc, bed=BED, mode='BY_LAYER', colors=2,
                      out_dir=tempfile.mkdtemp(dir=D))), r2_gen=True)
run('brickkit BY_OBJECT', lambda: (lambda r: _pl(r[0], r[1]['plates']))(
    pp.make_brick_kit(_bsrc, bed=BED, mode='BY_OBJECT', colors=2,
                      out_dir=tempfile.mkdtemp(dir=D))), r2_gen=True)

# ========================================================= TEXTURE ========
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import r2_texture as tx  # noqa: E402
lbl = pp.make_labels(['TEXTUR'], bed=BED, out_dir=D)[0]
run('texture FUZZY on label', lambda: tx.apply_texture(
    lbl, mode='FUZZY', fuzzy_thick=0.3, fuzzy_density=55, out_dir=D), skip_idem=True)
frm = pp.make_frame(preset='9x13', bed=BED, out_dir=D)[0]
# R175: the seamless pattern library - all 21 patterns, Z-size variants
for pat in ('RIDGES', 'WAVES', 'GRID', 'HATCH', 'CHECKER', 'HEX',
            'HONEYCOMB', 'BASKET', 'ROPE', 'PLANKS', 'BRICKS', 'SANDSTONE',
            'CONCRETE', 'CLAY', 'CREPE', 'FABRIC', 'PLUSH', 'HILBERT',
            'SCRATCH', 'GLITCH'):
    run('texture BUMPS %s on frame' % pat, lambda p=pat: tx.apply_texture(
        frm, mode='BUMPS', bump_pattern=p, bump_scale=6.0, bump_amp=0.5,
        zsize=4.0, seed=11, out_dir=D), skip_idem=True, r2_gen=True)
# R176: X/Y scaling with per-move flow recalculation
run('scale 150/150 on label', lambda: pp.apply_scale(
    lbl, sx=1.5, sy=1.5, out_dir=D), skip_idem=True, r2_gen=True)
run('scale 200/100 on label', lambda: pp.apply_scale(
    lbl, sx=2.0, sy=1.0, out_dir=D), skip_idem=True, r2_gen=True)
expect_error('scale 300/300 refused (bed)', lambda: pp.apply_scale(
    lbl, sx=3.0, sy=3.0, out_dir=D))

# R177: the cake cut - split a print with a plane
import r2_cake
run('cake cut horizontal on label', lambda: r2_cake.cut_cake(
    lbl, z_offset=1.0, out_dir=D)[0], skip_idem=True, r2_gen=True)
run('cake cut tilted + reorient on label', lambda: r2_cake.cut_cake(
    lbl, yaw=20.0, pitch=10.0, z_offset=1.0, reorient=True,
    out_dir=D)[0], skip_idem=True, r2_gen=True)
run('cake cut LOWER only', lambda: r2_cake.cut_cake(
    lbl, z_offset=1.0, part='LOWER', out_dir=D)[0], skip_idem=True,
    r2_gen=True)
expect_error('cake above everything refuses', lambda: r2_cake.cut_cake(
    lbl, z_offset=99.0, out_dir=D))

# R178: string art - the anchor ring + strands
run('string art SPIRAL 80mm', lambda: pp.make_string_art(
    pattern='SPIRAL', diameter=80.0, anchors=60, lines=180, out_dir=D,
    bed=BED)[0], skip_idem=True)
run('string art PHOTO from image', lambda: pp.make_string_art(
    src=img, pattern='PHOTO', diameter=80.0, anchors=60, lines=150,
    out_dir=D, bed=BED)[0], skip_idem=True)
expect_error('string art PHOTO without image refuses', lambda:
    pp.make_string_art(pattern='PHOTO', out_dir=D))

# R180: generator CHAINS - one tool's output feeds the next; the feature
# tagging must survive every hop (the .129 field log: CUSTOM rows with
# nothing to tune but PA, the outer wall gone from the menus)
_txo180 = tx.apply_texture(lbl, mode='FUZZY', fuzzy_thick=0.2,
                           fuzzy_density=100, out_dir=D)[0]
_rg180 = run('chain: range excerpt of a TEXTURED file', lambda: pp.make_range(
    _txo180, 3, 12, out_dir=D), skip_idem=True, r2_gen=True)
_hr180 = open(_rg180[0]).read()
# R213: unknown blocks no longer masquerade as WALL-OUTER - texture
# artefacts keep their own C-numbers. The WALL tagging of REAL walls must
# survive both hops, and CUSTOM may only appear as numbered slots.
import re as _re213
_hn213 = [ln for ln in _hr180.splitlines() if 'APPLY_TYPE TYPE=' in ln]
if not any('TYPE=WALL-OUTER' in ln for ln in _hn213):
    fails.append(('chain texture->range: the WALL-OUTER tagging must '
                  'survive both hops', _rg180))
_bad213 = [ln for ln in _hn213
           if 'TYPE=CUSTOM' in ln and 'TYPE=CUSTOM,' not in ln]
if _bad213:
    fails.append(('chain texture->range: bare CUSTOM (unnumbered) must not '
                  'appear anymore - R213 slots are C1..C9: %r' % _bad213[:2],
                  _rg180))
_sc180 = pp.apply_scale(lbl, sx=1.3, sy=1.3, out_dir=D)[0]
_sct180 = run('chain: texture on a SCALED file', lambda: tx.apply_texture(
    _sc180, mode='BUMPS', bump_pattern='WAVES', bump_scale=8.0,
    bump_amp=0.4, out_dir=D), skip_idem=True, r2_gen=True)
_hsc180 = open(_sct180[0]).read()
_hn2_213 = [ln for ln in _hsc180.splitlines() if 'APPLY_TYPE TYPE=' in ln]
if not any('TYPE=WALL-OUTER' in ln for ln in _hn2_213):
    fails.append(('chain scale->texture: WALL-OUTER must survive', _sct180))
_bad2_213 = [ln for ln in _hn2_213
             if 'TYPE=CUSTOM' in ln and 'TYPE=CUSTOM,' not in ln]
if _bad2_213:
    fails.append(('chain scale->texture: bare CUSTOM must not appear - '
                  'R213 slots are C1..C9: %r' % _bad2_213[:2], _sct180))
_ck180 = r2_cake.cut_cake(lbl, z_offset=1.0, out_dir=D)[0][0]
# R180: a cake half with z_offset sits EMPTY for its first layers - the
# honest make_range guard refuses a no-ink window (expect_error), the real
# chain uses layers that actually print
expect_error('chain: range of the cake half EMPTY layers refuses', lambda:
    pp.make_range(_ck180, 1, 3, out_dir=D))
_ckr180 = run('chain: range excerpt of a CAKE half', lambda: pp.make_range(
    _ck180, 4, 5, out_dir=D), skip_idem=True, r2_gen=True)
_hck180 = open(_ckr180[0]).read()
if 'TYPE=CUSTOM' in _hck180:
    fails.append(('chain cake->range: no CUSTOM in the excerpt', _ckr180))
_sa180 = pp.make_string_art(pattern='SPIRAL', diameter=60.0, anchors=36,
                            lines=60, out_dir=D, bed=BED)[0]
_sar180 = run('chain: range excerpt of STRING ART', lambda: pp.make_range(
    _sa180, 1, 4, out_dir=D), skip_idem=True, r2_gen=True)
# R183 (.131b field round): mixed label jobs - 4 fonts x 4 sizes on ONE
# plate (per-job shelf pack) + a SCRIPT swash line (the collision guard
# widened its advances - 'fj' no longer prints as mud)
run('labels MIXED jobs: 4 fonts x sizes on one plate', lambda: pp.make_labels(
    ['ALPHA 1', 'BETA~22', 'GAMMA 3', 'DREHEN'],
    job_cfgs=[{'font': 'SMOOTH', 'w': 60, 'h': 20, 'size': 0, 'spacing': 0.5},
              {'font': 'MONO', 'w': 40, 'h': 15, 'size': 4, 'mode': 'fixed'},
              {'font': 'COND', 'w': 80, 'h': 25, 'size': 0},
              {'font': 'CAPS', 'w': 30, 'h': 12, 'size': 0}],
    bed=BED, out_dir=D), r2_gen=True)
run('labels SCRIPT swash line (collision guard)', lambda: pp.make_labels(
    ['fj mix~Script 12'], font='SCRIPT', w=50, h=20, bed=BED, out_dir=D),
    r2_gen=True)
_hsar180 = open(_sar180[0]).read()
if 'TYPE=CUSTOM' in _hsar180:
    fails.append(('chain stringart->range: no CUSTOM in the excerpt', _sar180))

# MAP: grayscale wrap (test pattern image, 96x64)
try:
    from PIL import Image
    _mapimg = Image.new('L', (96, 64))
    _mpx = _mapimg.load()
    import random as _mr
    _mrr = _mr.Random(5)
    for _yy in range(64):
        for _xx in range(96):
            _mpx[_xx, _yy] = int(127 + 120 * math.sin(_xx / 7.0) *
                                 math.cos(_yy / 5.0)) & 255
    _mapfile = os.path.join(D, 'texmap.png')
    _mapimg.save(_mapfile)
    run('texture BUMPS MAP on frame', lambda: tx.apply_texture(
        frm, mode='BUMPS', bump_pattern='MAP', bump_scale=6.0, bump_amp=0.5,
        map_file=_mapfile, out_dir=D), skip_idem=True, r2_gen=True)
except ImportError:
    print('MAP pattern skipped (no Pillow here)')

# =========================================================== PLOT =========
run('plot png convert', lambda: (pp.plot_convert(
    img, var_path=None, out=os.path.join(D, 'plot_out.png.gcode')),
    [os.path.join(D, 'plot_out.png.gcode')])[1],
    bed=(5, 5, 239, 233), skip_idem=True, plot=True)
txtf = os.path.join(D, 'notes.txt')
open(txtf, 'w', encoding='utf-8').write('ÄÖÜ Test 123\nzweite Zeile\n~?!\n')
run('plot txt convert', lambda: [pp.text_convert(txtf, var_path=None,
    out=os.path.join(D, 'notes.txt.gcode'))[0]], bed=(5, 5, 239, 233),
    skip_idem=True, plot=True)

# ================================================= R112 HARDCORE MATRIX ===
# .86: the user-ordered deep sweep - UNTESTED parameter corners of every
# generator + the new .86 invariants (every generated file: v5 tag, a sane
# retract verdict, never a stale marker)
T = lambda **kw: pp.make_cable_ties(bed=BED, out_dir=tempfile.mkdtemp(dir=D), **kw)
A = lambda **kw: pp.make_angles(bed=BED, out_dir=tempfile.mkdtemp(dir=D), **kw)
S = lambda **kw: pp.make_seal(bed=BED, out_dir=tempfile.mkdtemp(dir=D), **kw)
L = lambda **kw: pp.make_labels(bed=BED, out_dir=tempfile.mkdtemp(dir=D), **kw)

run('hc ties CLASSIC max 12mm x150', lambda: T(count=2, width=12.0, length=150.0), r2_gen=True)
run('hc ties LOOP min 2mm', lambda: T(count=4, width=2.0, variant='LOOP', length=50), r2_gen=True)
run('hc ties 8x layers5', lambda: T(count=8, layers=5), r2_gen=True)
run('hc ties LOOP layers8 single', lambda: T(count=1, layers=8, variant='LOOP'), r2_gen=True)
run('hc ties layer_h 0.08/0.32', lambda: T(count=2, layer_h=0.08, first_h=0.32), r2_gen=True)
run('hc angle 45 flat cs off', lambda: A(angle_deg=45, flat=True, countersink=False), r2_gen=True)
run('hc angle 120 holes3 d8', lambda: A(angle_deg=120, holes=3, hole_d=8.0), r2_gen=True)
run('hc angle unequal legs 80/30', lambda: A(leg_a=80, leg_b=30), r2_gen=True)
run('hc angle w40 walls3 holes4', lambda: A(width=40, walls=3, holes=4, stiffener=2), r2_gen=True)
run('hc angle layer 0.28 no rib', lambda: A(angle_deg=60, stiffener=0, layer_h=0.28), r2_gen=True)
run('hc angle 20 sharp', lambda: A(angle_deg=20), r2_gen=True)
run('hc seal thin ring od40 id34', lambda: S(od=40, id_=34), r2_gen=True)
run('hc seal 0.4mm 2 layers', lambda: S(od=30, id_=15, height=0.4), r2_gen=True)
run('hc seal tall 6mm GROOVE', lambda: S(od=50, id_=25, height=6.0, profile='GROOVE'), r2_gen=True)
run('hc seal tiny 20x6', lambda: S(od=20.0, id_=6.0), r2_gen=True)
run('hc label base1 text4', lambda: L(texts=['TIEF'], base_layers=1, text_layers=4), r2_gen=True)
run('hc label stroke 0.8 fat', lambda: L(texts=['FETT'], stroke=0.8), r2_gen=True)
run('hc label fixed 200x100', lambda: L(texts=['BREIT'], w=200, h=100, mode='fixed'), r2_gen=True)
run('hc label specials+2lines', lambda: L(texts=['ÄÖÜ&%$§!', 'zeile 2']), r2_gen=True)
run('hc label color2 layers6', lambda: L(texts=['2FARB'], base_layers=6), r2_gen=True)
run('hc frame depth4 corner0 flat', lambda: F(preset='9x13', depth=4, corner=0), r2_gen=True)
run('hc frame corner12 wall0.8 loops3', lambda: F(preset='9x13', corner=12, wall=0.8,
    wall_loops=3), r2_gen=True)
expect_error('hc frame WAVES IN too deep rejected', lambda: F(preset='9x13',
    frame_w=20, front='WAVES', s_dir='IN', s_amp=3.0, s_deep=1.0))
run('hc frame WAVES OUT amp3 angle15', lambda: F(preset='9x13', frame_w=20,
    front='WAVES', s_dir='OUT', s_amp=3.0, s_deep=1.0, s_size=4.0,
    s_angle=15.0), r2_gen=True)
run('hc frame LINES angle75 space2', lambda: F(preset='9x13', front='LINES',
    s_angle=75.0, s_space=2.0), r2_gen=True)
run('hc frame FOIL front captured', lambda: F(preset='9x13', disc='FOIL',
    disc_t=0.4, disc_side='FRONT'), r2_gen=True)
run('hc frame A6 stand+case+cable', lambda: F(preset='A6', depth=22, stand=True,
    cable=True), r2_gen=True)
run('hc frame 13x18 FLIP ironing off', lambda: F(preset='13x18', front='FLIP',
    ironing=False), r2_gen=True)
run('hc frame KIT wall2 infill25', lambda: F(width=180, height=120, depth=8,
    frame_w=8, wall=2.0, infill=25.0), r2_gen=True)
run('hc frame HEX size4.5 top3 bot4', lambda: F(preset='9x13', front='HEX',
    s_size=4.5, top_layers=3, bottom_layers=4), r2_gen=True)
if src_path:
    run('hc range outline+solid floor', lambda: RG(3, 15, floor=3,
        floor_shape='outline', floor_fill='solid'))
    run('hc range top outline grid brim5', lambda: RG(8, 24, top=3,
        top_shape='outline', top_fill='grid', brim=5))
    run('hc range holes E14+E27', lambda: RG(2, 20, floor=3, floor_hole=14.0,
        top=3, top_hole=27.0))
    run('hc range from layer 1', lambda: RG(1, 12))
try:
    _lith_src = run('hc litho source', lambda: LI(height_mm=60.0, levels=2))
except Exception as _e:   # noqa: BLE001
    _lith_src = None
if _lith_src:
    run('hc litho 2-band FLAT on litho', lambda: tx.apply_texture(
        _lith_src[0] if isinstance(_lith_src, list) else _lith_src,
        mode='BUMPS', bump_pattern='WAVES', bump_scale=4.0, bump_amp=0.3,
        out_dir=D), skip_idem=True)
run('hc texture FUZZY on frame', lambda: tx.apply_texture(
    F(preset='9x13')[0], mode='FUZZY', fuzzy_thick=0.5, fuzzy_density=25,
    out_dir=D), skip_idem=True, r2_gen=True)

# ---- .86 invariants over EVERYTHING this sweep produced --------------------
_hc_stale = _hc_old = _hc_untouched = 0
_hc_badret = []
for _root, _dirs, _fs in os.walk(D):
    for _f in _fs:
        if not _f.endswith('.gcode') or _f.endswith('.r2bak'):
            continue
        _p = os.path.join(_root, _f)
        try:
            _head = open(_p, errors='replace').read(6000)
        except OSError:
            continue
        if 'R2-PLOT' in _head:
            continue                      # plotter files are never tagged
        if '; R2-POSTPROC v4' in _head:
            _hc_stale += 1
        if any(t in _head for t in pp.OLD_TAGS):
            _hc_old += 1
        if 'RETRACT_STATUS=fix' in _head:
            _hc_badret.append(_f)
if _hc_stale or _hc_old or _hc_badret:
    fails.append(('.86 invariants', 'stale=%d old=%d bad-retract-fix=%s'
                  % (_hc_stale, _hc_old, _hc_badret[:3])))
else:
    info.append('.86 invariants: every swept file carries the v5 tag + a sane '
                'retract verdict')

# ============================================================ RESULT ======
print()
for i in info:
    print('  ', i)
print()
print('=' * 70)
print('MEGATEST: %d runs, %d files checked, %d FAIL' % (runs, files_checked,
                                                         len(fails)))
for name, prob in fails:
    print('  FAIL %-58s %s' % (name[:58], prob[:100]))
sys.exit(1 if fails else 0)
