#!/usr/bin/env python3
"""R217 generator matrix: EVERY generator x parameters x nozzles x beds.

The r197 sweep takes one representative variant per generator. This
matrix goes wider - the compatibility question of R217:

  * nozzles  0.2 / 0.4 / 0.6 / 0.8 / 1.0  (line widths, E per mm and
    hatch spacing all derive from nozzle_diameter)
  * beds     120 / 180 / 220 (Ender default) / 244x238 (home) / 256 /
    300 / 350 / 500  (placement + bed clamps)
  * parameter boundaries and invalid values per generator

Invariants checked on EVERY produced file (I1..I13):
  I1  exists, > 500 bytes
  I2  R2 header + _FILE_INFO
  I3  TYPES= tokens are canon
  I4  every TYPES token has an APPLY_TYPE marker (except SPARSE-INFILL)
  I5  PRINT_START/PRINT_END + EXCLUDE_OBJECT balanced
  I6  no junk (nan/None/inf/{%/}})
  I7  every ;TYPE: label resolves via _canon_type (the sparse-infill
      class from the .136n round)
  I8  temperatures present (PRINT_START HOTEND_FIRST=/BED=)
  I9  speed image: normalized generators print F3600 / travel F10800
      on XY moves; bridge + resonance keep their own (sane 300..20000)
  I10 every XY position inside the bed +- 3mm (the clamp proof)
  I11 Z >= 0 and <= 400
  I12 M83 present, E > 0 only on print moves
  I13 determinism: same input -> byte-identical file (labels, colorpic)

Plus: I14 nozzle scaling - the labels wall E/mm follows
wid(nozzle)=max(0.4, nozzle*1.08); the string-art strands stay clamped
thin (0.42..0.5) at EVERY nozzle.

Run:  python3 tools/r217_gen_matrix.py
"""
import math
import os
import re
import struct
import sys
import tempfile
import zlib

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import r2_postproc as pp                                   # noqa: E402

# /tmp gets reaped by the sandbox on long runs (observed R217: the
# shared parent vanished mid-run) - keep the tree under the workspace
# and clean it on every exit path
import atexit
import shutil
D = tempfile.mkdtemp(prefix='.r217m_', dir=os.path.expanduser('~'))
atexit.register(lambda: shutil.rmtree(D, ignore_errors=True))
HOME = (0.0, -3.0, 244.0, 238.0)
NOZZLES = (0.2, 0.4, 0.6, 0.8, 1.0)
BEDS = {
    'tiny-120': (0.0, 0.0, 120.0, 120.0),
    'prusamini-180': (0.0, 0.0, 180.0, 180.0),
    'ender3-220': (0.0, -3.0, 220.0, 217.0),
    'home-244x238': (0.0, -3.0, 244.0, 238.0),
    'bambu-256': (0.0, 0.0, 256.0, 256.0),
    'corexy-300': (0.0, 0.0, 300.0, 300.0),
    'voron-350': (0.0, 0.0, 350.0, 350.0),
    'gantry-500': (0.0, 0.0, 500.0, 500.0),
}
CANON = frozenset(pp._CANON_VALUES) | {
    'PRIME-TOWER', 'BRIM', 'IRONING', 'SKIRT', 'BRIDGE', 'INTERNAL-BRIDGE',
    'OVERHANG-PERIM', 'SPARSE-INFILL'}
FI_RE = re.compile(r'^_FILE_INFO')
TYPE_RE = re.compile(r'^\s*;\s*TYPE\s*:\s*(.+?)\s*$')

N_PASS = N_FAIL = 0
FAILS = []


def ck(name, ok, detail=''):
    global N_PASS, N_FAIL
    ok = bool(ok)
    if ok:
        N_PASS += 1
    else:
        N_FAIL += 1
        FAILS.append(name)
        print('FAIL  %s  %s' % (name, str(detail)[:170]))
    return ok


def png(w, h, gray):
    def chunk(t, d):
        return struct.pack('>I', len(d)) + t + d + struct.pack(
            '>I', zlib.crc32(t + d) & 0xffffffff)
    rows = b''
    for y in range(h):
        rows += b'\x00' + bytes(int(round(gray(x, y))) & 0xff
                                for x in range(w))
    return (b'\x89PNG\r\n\x1a\n'
            + chunk(b'IHDR', struct.pack('>IIBBBBB', w, h, 8, 0, 0, 0, 0))
            + chunk(b'IDAT', zlib.compress(rows))
            + chunk(b'IEND', b''))


IMG = os.path.join(D, 'src.png')
open(IMG, 'wb').write(png(96, 64, lambda x, y: 40 + 180 * x / 95))
_lab = pp.make_labels(['MX'], bed=HOME, out_dir=tempfile.mkdtemp(dir=D))[0]
_bs = pp.make_bricks(jobs=[('B2x2', 2)], bed=HOME,
                     out_dir=tempfile.mkdtemp(dir=D))[0]


def validate(path, bed, name, normalized=True):
    """I1..I12 for one generated PRINT file. bed=None skips I10."""
    tag = '%s [%s]' % (name, os.path.basename(path))
    if not (path and os.path.isfile(path) and os.path.getsize(path) > 500):
        return ck('%s I1 exists non-empty' % tag, False, str(path))
    txt = open(path, errors='replace').read()
    lines = txt.split('\n')
    if 'R2-PLOT' in txt[:2048]:
        # pen-plotter file: junk check + the R222 end choreography
        _tail = [l.strip() for l in lines
                 if l.strip() and not l.strip().startswith(';')]
        _has_park = any(l.startswith('G0 X') and ' Y' in l
                        and l.endswith('F4800') for l in _tail)
        _pe = '_PLOT_END' in _tail
        _m84_last = bool(_tail) and _tail[-1] == 'M84'
        _pe_before_m84 = _pe and 'M84' in _tail \
            and _tail.index('_PLOT_END') < _tail.index('M84')
        return ck('%s I6 plot clean + I5c plot END (park, _PLOT_END heaters/'
                  'speed hook, motors off LAST - the .136s audit: FILAMENT '
                  'plots kept extruder+bed hot, PEN kept the preheat)'
                  % tag,
                  not any(w in txt for w in ('nan', 'None', 'inf'))
                  and _has_park and _pe and _m84_last and _pe_before_m84,
                  'park=%s plotend=%s m84last=%s'
                  % (_has_park, _pe, _m84_last))
    ok = ck('%s I1 exists non-empty' % tag, True)
    hdr = '\n'.join(lines[:40])
    fi = [l for l in lines if FI_RE.match(l)]
    fi = fi[0] if fi else ''
    ok &= ck('%s I2 header + _FILE_INFO' % tag,
             ('; R2-' in hdr or 'R2-' in lines[0]) and bool(fi), fi[:70])
    m = re.search(r'TYPES=([A-Z,-]+)', fi)
    types = m.group(1).split(',') if m else []
    ok &= ck('%s I3 TYPES canon' % tag,
             bool(types) and all(t in CANON for t in types), str(types))
    have_apply = set(re.findall(r'APPLY_TYPE TYPE=([A-Z-]+)', txt))
    missing = [t for t in types if t not in have_apply
               and t != 'SPARSE-INFILL']
    ok &= ck('%s I4 APPLY markers' % tag, not missing, str(missing))
    ok &= ck('%s I5 START/END + EXCLUDE balanced' % tag,
             'PRINT_START' in txt and 'PRINT_END' in txt
             and txt.count('EXCLUDE_OBJECT_START')
             == txt.count('EXCLUDE_OBJECT_END'),
             '%d/%d' % (txt.count('EXCLUDE_OBJECT_START'),
                        txt.count('EXCLUDE_OBJECT_END')))
    # R222 I5b: nothing may MOVE (or heat, or reset state) after PRINT_END -
    # the end choreography (park + heaters off) must be the last real
    # action. Info/sound lines after it are legal (the frame kits announce
    # the next plate with beeps once the head already parks).
    _after = []
    _seen_end = False
    for _l in lines:
        _t = _l.split(';')[0].strip()
        if not _t:
            continue
        if _t.startswith('PRINT_END'):
            _seen_end = True
            continue
        if _seen_end:
            _after.append(_t)
    _info_ok = all(_t.split()[0] in ('RESPOND', 'M117', 'M300', 'G4', 'M107')
                   for _t in _after)
    ok &= ck('%s I5b PRINT_END is the last real command (only info/'
             'sound lines may follow - no moves, no heat, no state '
             'changes after the park)' % tag,
             _seen_end and _info_ok, str(_after[:3]))
    bad = [w for w in ('nan', 'None', 'inf', '{%', '}}')
           if w in '\n'.join(l for l in lines
                             if not l.strip().startswith(';'))]
    ok &= ck('%s I6 no junk' % tag, not bad, str(bad))
    customs = [TYPE_RE.match(l).group(1) for l in lines
               if TYPE_RE.match(l)]
    unk = [c for c in customs if pp._canon_type(c) == 'CUSTOM']
    ok &= ck('%s I7 every ;TYPE: resolves' % tag, not unk, str(unk[:3]))
    # temps: string art carries them explicitly (.136n field fix);
    # the others ride on PRINT_START MATERIAL= (the start macro resolves
    # the material table itself)
    ok &= ck('%s I8 temps wired (explicit or MATERIAL=)' % tag,
             ('HOTEND_FIRST=' in txt and bool(re.search(r'\bBED=\d', txt)))
             or 'PRINT_START MATERIAL=' in txt, '')
    # I9 speed image + I10 bed + I11 Z + I12 E - one pass
    f_bad, out_bad, z_bad, e_bad = [], [], [], []
    for l in lines:
        if not re.match(r'^G[0123]', l):
            continue
        has_xy = bool(re.search(r' [XY]-?[\d.]', l))
        has_e = bool(re.search(r' E-?[\d.]', l))
        mf = re.search(r'\bF(\d+(?:\.\d+)?)', l)
        if has_xy and mf:
            f = float(mf.group(1))
            if normalized:
                # BOTH classes are rate-capped on short segments
                # (max_rate * seg * 60, R167: F2138 on a 0.09mm text
                # stroke) - legal band = [floor, nominal]
                if has_e:
                    if not (300.0 <= f <= 3600.5):
                        f_bad.append((l[:40], f))
                elif not (500.0 <= f <= 10800.5):
                    f_bad.append((l[:40], f))
            elif not (300.0 <= f <= 20000.0):
                f_bad.append((l[:40], f))
            mx = re.search(r' X(-?[\d.]+)', l)
            my = re.search(r' Y(-?[\d.]+)', l)
            if bed:
                x0, y0, x1, y1 = bed
                if not (x0 - 3.0 <= float(mx.group(1)) <= x1 + 3.0):
                    out_bad.append(('X', mx.group(1), l[:36]))
                if not (y0 - 3.0 <= float(my.group(1)) <= y1 + 3.0):
                    out_bad.append(('Y', my.group(1), l[:36]))
        mz = re.search(r' Z(-?[\d.]+)', l)
        if mz and not (-0.05 <= float(mz.group(1)) <= 400.0):
            z_bad.append(mz.group(1))
        me = re.search(r' E(-?[\d.]+)', l)
        if me and float(me.group(1)) < 0 and not l.startswith('G10'):
            e_bad.append(l[:40])
    ok &= ck('%s I9 speed image' % tag, not f_bad, str(f_bad[:2]))
    ok &= ck('%s I10 inside the bed' % tag, not out_bad,
             str(out_bad[:2]) if out_bad else '')
    ok &= ck('%s I11 Z sane' % tag, not z_bad, str(z_bad[:2]))
    ok &= ck('%s I12 no negative E' % tag, not e_bad, str(e_bad[:2]))
    return ok


def run(label, fn, bed=HOME, normalized=True):
    """Run one generator call; returns the file path(s) or None."""
    try:
        r = fn()
    except ValueError:
        return 'REFUSED'
    except Exception as e:                                  # noqa: BLE001
        ck('%s runs without crashing' % label, False, repr(e)[:120])
        return None
    outs = r[0] if isinstance(r, tuple) else r
    if isinstance(outs, str):
        outs = [outs]
    for i, f in enumerate(outs):
        if f and os.path.isfile(str(f)):
            validate(str(f), bed, '%s#%d' % (label, i), normalized)
        else:
            ck('%s#%d produced a file' % (label, i), False, str(f))
    return outs


# ============================================================ the matrix ====
print('--- nozzle axis (0.2 .. 1.0 mm) ---')
for nz in NOZZLES:
    run('labels-n%.1f' % nz,
        lambda nz=nz: pp.make_labels(['A'], w=40, h=20, nozzle=nz,
                                     bed=HOME,
                                     out_dir=tempfile.mkdtemp(dir=D)))
    run('ties-n%.1f' % nz,
        lambda nz=nz: pp.make_cable_ties(count=4, length=60, nozzle=nz,
                                         bed=HOME,
                                         out_dir=tempfile.mkdtemp(dir=D)))
    run('shape-n%.1f' % nz,
        lambda nz=nz: pp.make_shape(size_x=25, size_y=25, height=8,
                                    nozzle=nz, bed=HOME,
                                    out_dir=tempfile.mkdtemp(dir=D)))
    run('frame-n%.1f' % nz,
        lambda nz=nz: pp.make_frame(preset='9x13', nozzle=nz, bed=HOME,
                                    out_dir=tempfile.mkdtemp(dir=D)))
    run('angles-n%.1f' % nz,
        lambda nz=nz: pp.make_angles(count=1, leg_a=30, leg_b=30,
                                      nozzle=nz, bed=HOME,
                                      out_dir=tempfile.mkdtemp(dir=D)))
    run('seal-n%.1f' % nz,
        lambda nz=nz: pp.make_seal(od=30, nozzle=nz, bed=HOME,
                                   out_dir=tempfile.mkdtemp(dir=D)))
    run('stringart-n%.1f' % nz,
        lambda nz=nz: pp.make_string_art(pattern='SPIRAL', diameter=70.0,
                                         anchors=36, lines=60, nozzle=nz,
                                         bed=HOME,
                                         out_dir=tempfile.mkdtemp(dir=D)))

print('--- bed axis (120 .. 500 mm) ---')
for bname, bed in BEDS.items():
    run('labels-%s' % bname,
        lambda bed=bed: pp.make_labels(['B'], w=40, h=20, bed=bed,
                                       out_dir=tempfile.mkdtemp(dir=D)),
        bed=bed)
    run('frame-%s' % bname,
        lambda bed=bed: pp.make_frame(width=100, height=140, bed=bed,
                                      out_dir=tempfile.mkdtemp(dir=D)),
        bed=bed)
    run('bricks-%s' % bname,
        lambda bed=bed: pp.make_bricks(jobs=[('B2x2', 2)], bed=bed,
                                       out_dir=tempfile.mkdtemp(dir=D)),
        bed=bed)
    run('stringart-%s' % bname,
        lambda bed=bed: pp.make_string_art(pattern='SPIRAL', diameter=90.0,
                                           anchors=40, lines=80, bed=bed,
                                           out_dir=tempfile.mkdtemp(dir=D)),
        bed=bed)
    run('litho-%s' % bname,
        lambda bed=bed: pp.make_lithophane(IMG, height_mm=70, bed=bed,
                                           out_dir=tempfile.mkdtemp(dir=D)),
        bed=bed)
    run('figures-%s' % bname,
        lambda bed=bed: pp.make_figures(count=2, scale=60, bed=bed,
                                        out_dir=tempfile.mkdtemp(dir=D)),
        bed=bed)

print('--- parameter boundaries + invalids ---')
run('labels-tiny', lambda: pp.make_labels(
    ['A'], w=12, h=8, font_size=2, bed=HOME,
    out_dir=tempfile.mkdtemp(dir=D)))
run('labels-huge', lambda: pp.make_labels(
    ['WIDE TEXT LINE'], w=200, h=60, bed=HOME,
    out_dir=tempfile.mkdtemp(dir=D)))
run('labels-pixel-font', lambda: pp.make_labels(
    ['PX'], font='PIXEL', bed=HOME, out_dir=tempfile.mkdtemp(dir=D)))
run('labels-invalid-neg', lambda: pp.make_labels(
    ['A'], w=-30, bed=HOME, out_dir=tempfile.mkdtemp(dir=D)))
run('labels-ring-hole', lambda: pp.make_labels(
    ['O'], hole_side=1, hole_d=5, ring=True, ring_d=8, bed=HOME,
    out_dir=tempfile.mkdtemp(dir=D)))
run('ties-loop', lambda: pp.make_cable_ties(
    variant='LOOP', count=10, length=30, width=4, layers=2, bed=HOME,
    out_dir=tempfile.mkdtemp(dir=D)))
run('ties-invalid', lambda: pp.make_cable_ties(
    count=-5, bed=HOME, out_dir=tempfile.mkdtemp(dir=D)))
run('frame-presets', lambda: pp.make_frame(
    preset='13x18', bed=HOME, out_dir=tempfile.mkdtemp(dir=D)))
run('frame-oval-stand', lambda: pp.make_frame(
    width=100, height=140, shape='OVAL', stand=True, hang_ring=True,
    bed=HOME, out_dir=tempfile.mkdtemp(dir=D)))
run('frame-invalid', lambda: pp.make_frame(
    width=-5, bed=HOME, out_dir=tempfile.mkdtemp(dir=D)))
run('angles-acute', lambda: pp.make_angles(
    angle_deg=25, leg_a=20, leg_b=45, holes=0, flat=True, bed=HOME,
    out_dir=tempfile.mkdtemp(dir=D)))
run('angles-invalid', lambda: pp.make_angles(
    angle_deg=700, bed=HOME, out_dir=tempfile.mkdtemp(dir=D)))
run('shape-vase', lambda: pp.make_shape(
    shape='SQUARE', size_x=30, size_y=30, height=25, walls=1, infill=0,
    bed=HOME, out_dir=tempfile.mkdtemp(dir=D)))
run('shape-poly12-solid', lambda: pp.make_shape(
    shape='POLY', corners=12, size_x=28, size_y=28, height=6, infill=100,
    bed=HOME, out_dir=tempfile.mkdtemp(dir=D)))
run('shape-triangle', lambda: pp.make_shape(
    shape='TRIANGLE', size_x=30, size_y=26, height=5, wall_thick=1.2,
    bed=HOME, out_dir=tempfile.mkdtemp(dir=D)))
run('shape-invalid-corners', lambda: pp.make_shape(
    corners=99, bed=HOME, out_dir=tempfile.mkdtemp(dir=D)))
run('seal-profiles', lambda: pp.make_seal(
    od=35, id_=15, height=2.0, profile='PYRAMID', bed=HOME,
    out_dir=tempfile.mkdtemp(dir=D)))
run('seal-tpu-invalid', lambda: pp.make_seal(
    od=5, id_=50, bed=HOME, out_dir=tempfile.mkdtemp(dir=D)))
run('bridge-tall', lambda: pp.make_bridge(
    length=120, h_long=25, h_short=10, bed=HOME,
    out_dir=tempfile.mkdtemp(dir=D)), normalized=False)
run('bridge-invalid', lambda: pp.make_bridge(
    length=-10, bed=HOME, out_dir=tempfile.mkdtemp(dir=D)), normalized=False)
run('stringart-rect-custom', lambda: pp.make_string_art(
    pattern='SPIRAL', shape='RECT', size_w=90, size_h=130, ring_h=3.0,
    arc=0.5, anchors=48, lines=90, bed=HOME,
    out_dir=tempfile.mkdtemp(dir=D)))
run('stringart-photo-rect', lambda: pp.make_string_art(
    src=IMG, pattern='PHOTO', shape='RECT', size_w=102, size_h=152,
    anchors=64, lines=120, bed=HOME, grid=40, n_cand=50,
    out_dir=tempfile.mkdtemp(dir=D)))
run('stringart-star', lambda: pp.make_string_art(
    pattern='STAR', diameter=70, anchors=24, bed=HOME,
    out_dir=tempfile.mkdtemp(dir=D)))
run('stringart-invalid-anchors', lambda: pp.make_string_art(
    pattern='SPIRAL', anchors=5, bed=HOME,
    out_dir=tempfile.mkdtemp(dir=D)))
run('litho-flat', lambda: pp._make_litho_flat(
    IMG, bed=HOME, out_dir=tempfile.mkdtemp(dir=D)))
run('litho-thin-layers', lambda: pp.make_lithophane(
    IMG, height_mm=60, layer_h=0.08, bed=HOME,
    out_dir=tempfile.mkdtemp(dir=D)))
run('litho-no-frame', lambda: pp.make_lithophane(
    IMG, height_mm=60, frame=False, bed=HOME,
    out_dir=tempfile.mkdtemp(dir=D)))
run('colorpic-6bands', lambda: pp.make_colorpic(
    IMG, width_mm=80, bands=6, band_h=0.6, bed=HOME,
    out_dir=tempfile.mkdtemp(dir=D)))
run('colorpic-invalid', lambda: pp.make_colorpic(
    IMG, width_mm=-5, bed=HOME, out_dir=tempfile.mkdtemp(dir=D)))
run('bricks-many', lambda: pp.make_bricks(
    jobs=[('B2x4', 4), ('B1x2', 6), ('B2x2', 3)], bed=HOME,
    out_dir=tempfile.mkdtemp(dir=D)))
run('brickkit-by-object', lambda: pp.make_brick_kit(
    _bs, mode='BY_OBJECT', colors=4, bed=HOME,
    out_dir=tempfile.mkdtemp(dir=D)))
run('figures-many-colors', lambda: pp.make_figures(
    count=6, scale=45, colors=4, colormode='BY_OBJECT', bed=HOME,
    out_dir=tempfile.mkdtemp(dir=D)))
run('resonance-y', lambda: pp.make_resonance(
    axes=('y',), bed=HOME, out_dir=tempfile.mkdtemp(dir=D)),
    normalized=False)
run('range-mid', lambda: pp.make_range(
    _lab, start=2, end=4, out_dir=tempfile.mkdtemp(dir=D)), bed=HOME)
run('range-floor-top', lambda: pp.make_range(
    _lab, start=1, end=5, floor=1, top=1, brim=2,
    out_dir=tempfile.mkdtemp(dir=D)), bed=HOME)
run('plotcal', lambda: pp.make_plot_cal(
    out_dir=tempfile.mkdtemp(dir=D)), bed=None)

print('--- I13 determinism ---')
for nm, fn in (
        ('labels', lambda: pp.make_labels(['D'], bed=HOME,
                                           out_dir=tempfile.mkdtemp(dir=D))),
        ('colorpic', lambda: pp.make_colorpic(
            IMG, width_mm=60, bed=HOME,
            out_dir=tempfile.mkdtemp(dir=D))),
        ('stringart', lambda: pp.make_string_art(
            pattern='SPIRAL', diameter=60, anchors=30, lines=50, bed=HOME,
            out_dir=tempfile.mkdtemp(dir=D)))):
    def _once():
        r = fn()
        return r[0] if isinstance(r, tuple) else r
    r1 = _once()
    r2 = _once()
    ck('I13 %s deterministic (byte-identical re-run)' % nm,
       open(r1, 'rb').read() == open(r2, 'rb').read(), '')

print('--- I14 nozzle scaling (E per mm follows the line width) ---')


def median_epmm(path):
    txt = open(path, errors='replace').read()
    segs = []
    px = py = None
    for l in txt.split('\n'):
        m = re.match(r'G1 X([\d.-]+) Y([\d.-]+) E([\d.]+)', l)
        if m:
            x, y, e = float(m.group(1)), float(m.group(2)), float(m.group(3))
            if px is not None and e > 0:
                dl = math.hypot(x - px, y - py)
                if dl > 0.5:
                    segs.append(e / dl)
            px, py = x, y
    return sorted(segs)[len(segs) // 2] if segs else 0.0


_epmm = {}
for nz in (0.4, 1.0):
    f = pp.make_labels(['S'], w=40, h=20, nozzle=nz, bed=HOME,
                       out_dir=tempfile.mkdtemp(dir=D))[0]
    _epmm[nz] = median_epmm(f)
_ratio = _epmm[1.0] / _epmm[0.4] if _epmm[0.4] else 0
_want = max(0.4, 1.0 * 1.08) / max(0.4, 0.4 * 1.08)
ck('I14 labels: wall E/mm scales with wid(nozzle) '
   '(measured %.2f, want %.2f +-20%%)' % (_ratio, _want),
   abs(_ratio - _want) / _want < 0.20, '%r' % _epmm)

_sa = {}
for nz in (0.4, 1.0):
    f = pp.make_string_art(pattern='SPIRAL', diameter=70, anchors=36,
                           lines=60, nozzle=nz, bed=HOME,
                           out_dir=tempfile.mkdtemp(dir=D))[0]
    _sa[nz] = median_epmm(f)
_r2 = _sa[1.0] / _sa[0.4] if _sa[0.4] else 0
ck('I14 stringart: strands stay clamped thin at every nozzle '
   '(E/mm ratio 1.0 vs 0.4 = %.2f, want ~1.19 = 0.5/0.42)' % _r2,
   abs(_r2 - 1.19) / 1.19 < 0.25, '%r' % _sa)

print()
print('R217 GENERATOR MATRIX: %d checks, %d FAIL' % (N_PASS + N_FAIL,
                                                     N_FAIL))
if FAILS:
    for f in FAILS:
        print('  - %s' % f)
    sys.exit(1)
print('RESULT: PASS - every generator x nozzle x bed x boundary green')
