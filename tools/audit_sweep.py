#!/usr/bin/env python3
"""R-audit sweep: run EVERY generator across a parameter matrix and check
print-safety invariants on the emitted gcode. Also measures the worst-case
move rate (MCU load / 'Timer too close' guard) of every generated file.

Run:  python3 tools/audit_sweep.py
Exit code 0 = all invariants held. This is NOT part of macro_render_test.py
(it generates ~60 files); run it before a release or after generator edits.
"""
import math
import os
import re
import struct
import sys
import tempfile
import zlib

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import r2_postproc as pp  # noqa: E402

BED = (0.0, -3.0, 220.0, 217.0)      # the real Ender-3 plate (manual ch. 23)
KNOWN_TYPES = set(k.lower() for k in pp.TYPE_MAP) | {'custom'}
fails = []
runs = 0


def synth_png(path, w=64, h=96):
    """tiny grayscale gradient PNG for the lithophane generator."""
    def chunk(tag, data):
        c = tag + data
        return struct.pack('>I', len(data)) + c + struct.pack('>I', zlib.crc32(c))
    raw = b''
    for y in range(h):
        raw += b'\x00'
        for x in range(w):
            raw += bytes([(x * 255 // w + y * 255 // h) // 2])
    png = (b'\x89PNG\r\n\x1a\n'
           + chunk(b'IHDR', struct.pack('>IIBBBBB', w, h, 8, 0, 0, 0, 0))
           + chunk(b'IDAT', zlib.compress(raw, 9))
           + chunk(b'IEND', b''))
    open(path, 'wb').write(png)


def check_file(name, path, total_layers=None):
    """invariant checks; returns (ok, notes). Appends to global fails."""
    global runs
    runs += 1
    txt = open(path, encoding='utf-8').read()
    lines = txt.split('\n')
    prob = []
    bed = BED
    # --- bed bounds ---
    for m in re.finditer(r'^G1 X([\d.-]+) Y([\d.-]+)', txt, re.M):
        x, y = float(m.group(1)), float(m.group(2))
        if not (bed[0] - 0.5 <= x <= bed[2] + 0.5 and bed[1] - 0.5 <= y <= bed[3] + 0.5):
            prob.append('out of bed: X%.1f Y%.1f' % (x, y))
            break
    # --- z monotonic ---
    zs = [float(m.group(1)) for m in re.finditer(r'^;Z:([\d.-]+)', txt, re.M)]
    if any(b < a for a, b in zip(zs, zs[1:])):
        prob.append('z not monotonic')
    # --- EXCLUDE balance + DEFINE before START ---
    starts = re.findall(r'^EXCLUDE_OBJECT_START NAME=(\S+)', txt, re.M)
    ends = re.findall(r'^EXCLUDE_OBJECT_END NAME=(\S+)', txt, re.M)
    if sorted(starts) != sorted(ends):
        prob.append('EXCLUDE unbalanced: %d starts vs %d ends' % (len(starts), len(ends)))
    for nm in set(starts):
        if ('EXCLUDE_OBJECT_DEFINE NAME=%s' % nm) not in txt:
            prob.append('EXCLUDE %s used but never defined' % nm)
            break
    first_start = txt.find('EXCLUDE_OBJECT_START')
    first_def = txt.find('EXCLUDE_OBJECT_DEFINE')
    if first_start >= 0 and first_def >= 0 and first_def > first_start:
        prob.append('DEFINE after first START')
    # --- types valid + APPLY after each ---
    types = [l[6:].strip().lower() for l in lines if l.startswith(';TYPE:')]
    bad_t = [t for t in types if t not in KNOWN_TYPES]
    if bad_t:
        prob.append('unknown ;TYPE: %s' % bad_t[:3])
    if txt.count('APPLY_TYPE TYPE=') < txt.count(';TYPE:') - 1:
        prob.append('missing APPLY_TYPE (%d/%d)'
                    % (txt.count('APPLY_TYPE TYPE='), txt.count(';TYPE:')))
    # --- PRINT_START before first move, PRINT_END at the end ---
    nonempty = [l for l in lines if l.strip()]
    if 'PRINT_START' not in txt:
        prob.append('no PRINT_START')
    # after PRINT_END only the end-of-plate trailer may follow (multi-plate
    # handoff: RESPOND / M117 / M300 beeps / G4 dwells / comments)
    _pe = txt.find(chr(10) + 'PRINT_END')
    if _pe < 0:
        prob.append('no PRINT_END line')
    else:
        for tl in txt[_pe:].split(chr(10))[2:]:
            if tl.strip() and not re.match(
                    r'^(RESPOND|M117|M300|G4|;|$)', tl.strip()):
                prob.append('gcode AFTER PRINT_END: %r' % tl[:40])
                break
    fm = re.search(r'^G1 X', txt, re.M)
    if fm and txt.find('PRINT_START') > fm.start():
        prob.append('move before PRINT_START')
    # --- layer count consistency ---
    lc = txt.count(';LAYER_CHANGE')
    if total_layers is not None and lc != total_layers:
        prob.append('layer mismatch: %d LAYER_CHANGE vs info %d' % (lc, total_layers))
    # --- no NaN / absurd coords ---
    for m in re.finditer(r'^G1 X([\d.-]+) Y([\d.-]+)', txt, re.M):
        if abs(float(m.group(1))) > 1000 or abs(float(m.group(2))) > 1000:
            prob.append('absurd coordinate')
            break
    # --- MCU load: worst-case move rate (segments per second) ---
    worst = 0.0
    z = None
    px = py = pf = None
    for l in lines:
        if l.startswith(';Z:'):
            z = float(l[3:])
        m = re.match(r'^G1 X([\d.-]+) Y([\d.-]+).* F(\d+)', l)
        if m and z is not None:
            x, y, f = float(m.group(1)), float(m.group(2)), float(m.group(3))
            if px is not None and f > 0:
                d = math.hypot(x - px, y - py)
                if d > 0.01:
                    rate = f / 60.0 / d          # moves per second for this hop
                    worst = max(worst, rate)
            px, py, pf = x, y, f
    # sustained tiny-segment flood zone: the 8-bit MCU serial budget is
    # ~450 moves/s (250k baud, ~18 bytes/move) - bursts above that risk
    # 'Timer too close' shutdowns. Momentary arc micro-segments (<250/s)
    # are fine.
    if worst > 400.0:
        prob.append('move rate %.0f/s (tiny-segment flood risk)' % worst)
    status = 'OK ' if not prob else 'FAIL'
    if prob:
        fails.append((name, prob))
    print('%s %-58s layers=%-4d moves/s<=%3.0f  %s'
          % (status, os.path.basename(path)[:58], len(zs), worst,
             '; '.join(prob)[:80]))


def run(gen, name, expect_guard=None, **kw):
    d = tempfile.mkdtemp(prefix='audit_')
    try:
        out, info = gen(out_dir=d, **kw)
        if isinstance(info.get('plates'), list):
            for f in info['plates']:
                check_file('%s/%s' % (name, f), os.path.join(d, f))
        else:
            check_file(name, out, info.get('layers'))
    except ValueError as e:
        if expect_guard and expect_guard in str(e):
            print('OK   %-58s guard as expected: %s' % (name, str(e)[:60]))
        else:
            fails.append((name, ['guard fired: %s' % e]))
            print('FAIL %-58s guard: %s' % (name, str(e)[:70]))


print('==== R-AUDIT SWEEP (bed %s) ====' % (BED,))

# ---- frames: the big matrix ----
matrix = []
for preset in ('9x13', '10x15', '13x18', 'A6'):
    matrix.append(dict(preset=preset, depth=8, frame_w=6))
    matrix.append(dict(preset=preset, depth=20, frame_w=8, stand=True))
for front in ('FLIP', 'LINES', 'WAVES', 'HEX'):
    matrix.append(dict(preset='9x13', depth=8, frame_w=6, front=front))
    matrix.append(dict(preset='10x15', depth=20, frame_w=6, front=front,
                       s_dir='IN', cable=True))
for disc, side, t in (('GLASS', 'FRONT', 2.0), ('LITHO', 'BACK', 3.0),
                      ('FOIL', 'FRONT', 0.5)):
    matrix.append(dict(preset='9x13', depth=8, frame_w=6, disc=disc,
                       disc_side=side, disc_t=t))
    matrix.append(dict(preset='13x18', depth=20, frame_w=8, disc=disc,
                       disc_side=side, disc_t=t, cable=True, stand=True))
for closure in ('BACK', 'SIDE'):
    for shape in ('RECT', 'OVAL'):
        matrix.append(dict(preset='10x15', depth=10, frame_w=10,
                           closure=closure, shape=shape, corner=8))
matrix.append(dict(width=40, height=200, depth=6, frame_w=6))          # kit
matrix.append(dict(width=40, height=200, depth=6, frame_w=6, front='HEX',
                   cable=True))                                        # kit skips
matrix.append(dict(width=150, height=60, depth=8, frame_w=12, hang='OFF'))
for i, kw in enumerate(matrix):
    kw.setdefault('bed', BED)
    # R106 (rule ll): OVAL + SIDE raises - the curved wall starves the
    # slot cap's anchors; the guard IS the expected outcome there
    _g106 = ('SIDE closure needs a RECT'
             if kw.get('closure') == 'SIDE' and kw.get('shape') == 'OVAL'
             else None)
    run(pp.make_frame, 'frame-%02d' % i, expect_guard=_g106, **kw)

# ---- other generators ----
run(pp.make_cable_ties, 'ties-CLASSIC', variant='CLASSIC', bed=BED)
run(pp.make_cable_ties, 'ties-LOOP-too-long', variant='LOOP', length=200,
    bed=BED, expect_guard='do not fit the bed')
run(pp.make_cable_ties, 'ties-LOOP', variant='LOOP', length=120, bed=BED)
run(pp.make_angles, 'angles-90', bed=BED)
run(pp.make_angles, 'angles-45-flat', angle_deg=45, flat=True, count=4, bed=BED)
run(pp.make_seal, 'seal-NUT', profile='NUT', ironing=True, bed=BED)
run(pp.make_bridge, 'bridge', bed=BED)
run(pp.make_labels, 'labels-1', texts=['AUDIT'], bed=BED)
run(pp.make_labels, 'labels-5', texts=['R2', 'AUDIT', 'SWEEP', '123', 'OK'], bed=BED)

# labels -> range chain (range needs a generated source)
_d = tempfile.mkdtemp(prefix='audit_')
_p, _i = pp.make_labels(['RANGE SRC'], out_dir=_d, bed=BED)
# make_range writes next to its source and has its own return signature
_r = pp.make_range(_p, 2, 5)
check_file('range', _r if isinstance(_r, str) else _r[0])

# ---- lithophane with a synthetic image ----
_img = os.path.join(tempfile.mkdtemp(prefix='audit_'), 'grad.png')
synth_png(_img)
run(pp.make_lithophane, 'litho', src=_img, bed=BED)

print('==== %d files checked, %d FAIL ====' % (runs, len(fails)))
for name, prob in fails:
    print('  %s: %s' % (name, '; '.join(prob)))
sys.exit(1 if fails else 0)
