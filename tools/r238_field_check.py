#!/usr/bin/env python3
# R238 (.136ai) field check - the master-prompt round:
#
#  1) AUTO segment fix: every freshly generated file above the risk
#     threshold (400 moves/s) is merged MCU-safe in the job worker - no
#     separate menu step anymore (.136ae field log: 6000 moves/s texture).
#  2) Queue KILL channel: Skip ends the RUNNING job (next starts), Stop
#     ends it + clears the queue - the old menu could only clear PENDING.
#     The queue row moved to __queue = DIRECTLY above the SD card.
#  3) STL export: STL folder + .stl.gcode (Mainsail shows + downloads it,
#     strip the ending) - the watcher never processes the data files.
#  4) Texture engine: optional helical tilt (0 deg default, pattern-specific
#     angles when enabled), 6 new patterns (Knit, Fluted,
#     Bark, Scales, Facets, Macrame), vertical Planks, MAP with Otsu
#     background-as-alpha + TILE/ONCE + TOP/CENTER/BOTTOM, and the menu
#     separates FUZZY from BUMPS parameters.
import math
import os
import re
import shutil
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import r2_texture                                     # noqa: E402
import r2_postproc                                    # noqa: E402

ok = 0
fails = 0


def check(name, cond, detail=''):
    global ok, fails
    if cond:
        ok += 1
        print('  ok   %s' % name)
    else:
        fails += 1
        print('  FAIL %s  [%s]' % (name, detail))


HERE = os.path.dirname(os.path.abspath(__file__))
PP = os.path.join(HERE, 'r2_postproc.py')
TX = os.path.join(HERE, 'r2_texture.py')
M13 = os.path.join(HERE, '..', 'macros', '13_system.cfg')
M17 = os.path.join(HERE, '..', 'macros', '17_generator.cfg')
M08 = os.path.join(HERE, '..', 'macros', '08_print_start_stop.cfg')
LCD = os.path.join(HERE, '..', 'menus', 'lcd_menues.cfg')


def mini_vase(path, r=30.0, h=60.0, layers=30, seg=64):
    with open(path, 'w') as f:
        f.write('G21\nG90\nM83\n')
        for L in range(layers):
            z = 0.2 + h * L / layers
            f.write(';LAYER_CHANGE\n;Z:%.2f\n;TYPE:Outer wall\n' % z)
            for i in range(seg):
                a1 = 2 * math.pi * i / seg
                f.write('G1 X%.3f Y%.3f Z%.3f E%.4f F2400\n' % (
                    110 + r * math.cos(a1), 110 + r * math.sin(a1),
                    z + 0.0002 * i, 0.01))
    return path


print('--- A) queue kill channel (Skip / Stop) --------------------------')
_pp = open(PP, encoding='utf-8').read()
_lcd = open(LCD, encoding='utf-8').read()
_m17 = open(M17, encoding='utf-8').read()
check('A1: _JobCancelled + _job_tick raises it on the kill flag',
      hasattr(r2_postproc, '_JobCancelled')
      and "_k238 = _JOB_STATE.get('kill')" in _pp
      and 'raise _JobCancelled' in _pp, '')
saved_yield = dict(r2_postproc._JOB_YIELD)
try:
    r2_postproc._JOB_YIELD['on'] = True
    r2_postproc._JOB_STATE['kill'] = 'SKIP'
    try:
        r2_postproc._job_tick(step=1000, every=1)
        raised = False
    except r2_postproc._JobCancelled as e:
        raised = str(e) == 'SKIP'
    r2_postproc._JOB_STATE['kill'] = None
    r2_postproc._job_tick(step=1000, every=1)      # must NOT raise
    check('A2: tick raises SKIP live and passes clean without a flag',
          raised, 'raised=%r' % raised)
finally:
    r2_postproc._JOB_YIELD.update(saved_yield)
    r2_postproc._JOB_STATE['kill'] = None
check('A3: the nonce channel is primed + dispatched (mode SKIP/STOP)',
      "'genq_kill_nonce'" in _pp and "'genq_kill_mode'" in _pp
      and "_km238 not in ('SKIP', 'STOP')" in _pp
      and '_JOB_STATE[\'kill\'] = _km238' in _pp, '')
check('A4: the worker deletes partial output + reports the cancel',
      'CANCELLED' in _pp and 'output deleted%s' in _pp
      and 'os.remove(_o238)' in _pp, '')
check('A5: menu __queue sits DIRECTLY above __sdcard, with skip/stop/clear',
      '[menu __main __queue]' in _lcd and '[menu __main __sdcard]' in _lcd
      and _lcd.index('[menu __main __queue]') < _lcd.index('[menu __main __sdcard]')
      and '__queue __skip' in _lcd and '__queue __stop' in _lcd
      and '__queue __cancel' in _lcd and '__queue __show' in _lcd
      and '[menu __main __genq]' not in _lcd, '')
check('A6: _GEN_QUEUE_SKIP/_STOP macros write the quoted mode + nonce',
      '[gcode_macro _GEN_QUEUE_SKIP]' in _m17
      and '[gcode_macro _GEN_QUEUE_STOP]' in _m17
      and 'VARIABLE=genq_kill_mode VALUE="\\"SKIP\\""' in _m17
      and 'VARIABLE=genq_kill_mode VALUE="\\"STOP\\""' in _m17
      and 'genq_kill_nonce' in _m17, '')
check('A7: skip needs a running job (honest idle answer)',
      'Nothing is building right now' in _m17
      and 'gen_busy|default(0)|int' in _m17, '')

print('--- B) auto segment fix + STL data safety ------------------------')
d = tempfile.mkdtemp(prefix='r238_')
try:
    bomb = os.path.join(d, 'V2_bomb.gcode')
    with open(bomb, 'w') as f:
        f.write('G21\nG90\nM83\nG1 F3000\n')
        x = 0.0
        for _ in range(400):
            x += 0.02
            f.write('G1 X%.3f Y50.000 E0.001\n' % x)
    rate = r2_postproc._worst_move_rate(bomb)
    n, rb, ra, m2 = r2_postproc._segments_fix_file(bomb)
    check('B1: a generated bomb measures >400/s and heals under 400',
          rate > 400 and ra < 400 and n >= 250,
          'rate=%.0f n=%d ra=%.0f' % (rate, n, ra))
    check('B2: the worker hooks the fix at the 400 threshold (auto)',
          'if _mr and _mr > 400.0:' in _pp and ': AUTO ' in _pp
          and 'segment fix - %d micro move(s) ' in _pp, '')
    check('B3: _is_gen_name refuses STL/OBJ exports (data, not g-code)',
          r2_postproc._is_gen_name('V1_part_object.stl.gcode') is False
          and r2_postproc._is_gen_name('V1_part_object.obj.gcode') is False
          and r2_postproc._is_gen_name('V1_part.gcode') is True, '')
    stlf = os.path.join(d, 'V1_part_object.stl.gcode')
    open(stlf, 'wb').write(b'\x00\x01binarynotgcode')
    check('B4: _meta_finalize hands off STL exports',
          r2_postproc._meta_finalize(stlf) == 'foreign', '')
    check('B5: the stamping loop skips non-gcode + .stl.gcode/.obj.gcode outputs',
          "endswith(('.stl.gcode', '.obj.gcode'))" in _pp, '')

    print('--- C) OBJ export lands in STL/ as .obj.gcode (STL removed) ----')
    src = mini_vase(os.path.join(d, 'V3_obj.gcode'))
    rel, info = r2_postproc._obj_export(d, 'V3_obj.gcode')
    check('C1: output path is STL/<name>_object.obj.gcode',
          rel.replace('\\', '/') == 'STL/V3_obj_object.obj.gcode'
          and os.path.isfile(os.path.join(d, rel.replace('/', os.sep))),
          'rel=%r' % rel)
    check('C2: the mesh is a real Wavefront OBJ (text v/f, not G-code)',
          open(os.path.join(d, rel.replace('/', os.sep)), 'r', encoding='utf-8', errors='replace').read(4)
          != 'G21\n' and info.get('boxes', 0) > 0 and info.get('obj_vertices', 0) > 0, '')
    _m13 = open(M13, encoding='utf-8').read()
    _m08 = open(M08, encoding='utf-8').read()
    check('C3: the SD browser refuses .stl.gcode/.obj.gcode with the download hint',
          "low.endswith(('.stl.gcode', '.obj.gcode'))" in _m13
          and 'download it in Mainsail' in _m13, '')
    check('C4: OBJ_EXPORT macro tells the STL folder + ending trick',
      'STL folder' in _m08 and 'remove the .gcode ending' in _m08
      and 'obj.gcode' in _m08 and 'STL_EXPORT' not in _m08, '')

    print('--- D) texture: tilt, new patterns, MAP ------------------------')
    names = r2_texture.PATTERN_NAMES
    check('D1: 55 patterns, the R238 six + the R265 fourteen + the '
          'R266.2 nine + the R266.3 six present',
          len(names) == 55 and all(p in names for p in (
              'KNIT', 'FLUTED', 'BARK', 'SCALES', 'FACETS', 'MACRAME'))
          and all(p in names for p in (
              'STONEWALL', 'RUBBLE', 'TILES', 'PARQUET', 'LAMINATE',
              'HILBERT', 'MAZE'))
          and all(p in names for p in (
              'PERFORATION', 'VENT', 'CARBON', 'PINDOTS', 'OCTAGONS',
              'CHAINLINK', 'NETGRID'))
          and all(p in names for p in (
              'RINGS', 'OAK', 'BEECH', 'KNOT', 'OLDBARK', 'LEATHER',
              'ORANGE', 'CRACKS', 'WRINKLE'))
          and all(p in names for p in (
              'HEARTS', 'GOLF', 'BASKETBALL', 'RAUFASER', 'ROOFTILES',
              'CROCHET'))
          and set(r2_texture.PATTERN_TILT) == set(names),
          '%d patterns / %d tilt presets' % (
              len(names), len(r2_texture.PATTERN_TILT)))
    bad = []
    for p in names:
        if p == 'MAP':
            continue
        try:
            out, info = r2_texture.apply_texture(
                src, out_dir=d, mode='BUMPS', bump_pattern=p,
                bump_scale=10.0, bump_amp=0.4, zsize=10.0)
            if info['shifted'] <= 0:
                bad.append(p)
        except Exception as e:                        # noqa: BLE001
            bad.append('%s:%r' % (p, e))
    check('D2: every pattern shifts a mini vase end to end',
          not bad, str(bad[:4]))
    _, i_basket = r2_texture.apply_texture(
        src, out_dir=d, mode='BUMPS', bump_pattern='BASKET',
        bump_scale=10.0, bump_amp=0.4, zsize=10.0, tilt=True)
    _, i_ridge = r2_texture.apply_texture(
        src, out_dir=d, mode='BUMPS', bump_pattern='RIDGES',
        bump_scale=10.0, bump_amp=0.4, zsize=10.0, tilt=True)
    _, i_flute = r2_texture.apply_texture(
        src, out_dir=d, mode='BUMPS', bump_pattern='FLUTED',
        bump_scale=10.0, bump_amp=0.4, zsize=10.0, tilt=True)
    _, i_default = r2_texture.apply_texture(
        src, out_dir=d, mode='BUMPS', bump_pattern='BASKET',
        bump_scale=10.0, bump_amp=0.4, zsize=10.0)
    check('D3: tilt is opt-in; enabled preset angles remain explicit',
          i_default['tilt'] == 0.0
          and 25.0 <= i_basket['tilt'] <= 35.0
          and 1.0 <= i_ridge['tilt'] <= 3.0
          and i_flute['tilt'] == 0.0,
          'off %.1f / on %.1f/%.1f/%.1f' % (
              i_default['tilt'], i_basket['tilt'], i_ridge['tilt'],
              i_flute['tilt']))
    pats = r2_texture._build_patterns(11, 5, 91, None)
    worst = 0.0
    for zi in range(21):
        zf = zi / 20.0
        t = (zf * 5) % 1.0
        for nm in ('RIDGES', 'KNIT', 'BASKET', 'SCALES', 'FACETS',
                   'MACRAME'):
            fn = pats[nm]
            s0 = (0.0005 + 9 * zf / 11) % 1.0
            s1 = (0.9995 + 9 * zf / 11) % 1.0
            worst = max(worst, abs(fn(s0, t) - fn(s1, t)))
    check('D4: the helical tilt keeps the seam closed (jump < 0.12)',
          worst < 0.12, '%.4f' % worst)
    # G1: BARK and PLANKS must carry directional, edge-defined relief and
    # remain periodic at the cylinder seam / top, unlike a flat sinus stripe.
    _g1p = r2_texture._build_patterns(12, 8, 29, None)
    _g1metrics = {}
    for _nm in ('BARK', 'PLANKS'):
        _fn = _g1p[_nm]
        _vals = [_fn(i / 240.0, 0.371) for i in range(240)]
        _seam = abs(_fn(1e-7, 0.371) - _fn(1.0 - 1e-7, 0.371))
        _zseam = abs(_fn(0.371, 1e-7) - _fn(0.371, 1.0 - 1e-7))
        _g1metrics[_nm] = (max(_vals) - min(_vals), _seam, _zseam)
    check('G1: bark fissures and board joints have strong relief + closed seams',
          all(v[0] > 0.8 and v[1] < 0.05 and v[2] < 0.05
              for v in _g1metrics.values()), str(_g1metrics))
    _materials = ('BARK', 'PLANKS', 'BRICKS', 'WAVES', 'HONEYCOMB',
                  'BASKET', 'ROPE', 'PLUSH', 'SCALES', 'FLUTED')
    _signatures = {nm: tuple(round(_g1p[nm](x / 32.0, y / 32.0), 2)
                             for y in range(32) for x in range(32))
                   for nm in _materials}
    check('G1: 10 target materials produce distinct code-derived relief fields',
          len(set(_signatures.values())) == len(_materials),
          'unique %d/%d' % (len(set(_signatures.values())), len(_materials)))

    # ---- R265 (J8 texture round II, chunk 1): walls, floors, labyrinths ----
    print('--- R265) texture round II: name fidelity + closed seams --------')
    _r265 = ('STONEWALL', 'RUBBLE', 'TILES', 'PARQUET', 'LAMINATE',
             'HILBERT', 'MAZE')
    _r265m = {}
    for _nm in _r265:
        _fn = _g1p[_nm]
        _vals = [_fn(i / 191.0, j / 127.0) for j in range(128)
                 for i in range(192)]
        _ss265 = max(abs(_fn(1 - 1e-6, _t) - _fn(0.0, _t))
                     for _t in (_x / 31.0 for _x in range(31)))
        _st265 = max(abs(_fn(_s2, 1 - 1e-6) - _fn(_s2, 0.0))
                     for _s2 in (_x / 29.0 for _x in range(29)))
        _r265m[_nm] = (round(max(_vals) - min(_vals), 2),
                       round(_ss265, 4), round(_st265, 4))
    check('R265 relief: all 7 new patterns span > 0.8 with closed seams',
          all(v[0] > 0.8 and v[1] < 0.05 and v[2] < 0.05
              for v in _r265m.values()), str(_r265m))

    _r265b = ('PERFORATION', 'VENT', 'CARBON', 'PINDOTS', 'OCTAGONS',
              'CHAINLINK', 'NETGRID')
    _sig265 = {nm: tuple(round(_g1p[nm](x / 32.0, y / 32.0), 2)
                         for y in range(32) for x in range(32))
               for nm in tuple(_r265) + _r265b}
    check('R265 distinct: the 14 new fields differ from each other AND '
          'from the 10 classic materials',
          len(set(_sig265.values())) == len(_r265) + len(_r265b)
          and not (set(_sig265.values()) & set(_signatures.values())),
          'unique new %d/%d, classic clashes %d' % (
              len(set(_sig265.values())), len(_r265) + len(_r265b),
              len(set(_sig265.values()) & set(_signatures.values()))))

    # ---- R265.3 (bite 2): technical structures ---------------------------
    print('--- R265.3) bite 2: perforation, weave, dots, cells ----------')
    # CARBON and NETGRID carry intentional cell STEPS (weave edges) - the
    # seam promise for them is 'no jump at the wrap beyond the jumps the
    # field itself makes', measured jump-vs-jump (the R175 rule).
    _b2 = {}
    for _nm in _r265b:
        _fn = _g1p[_nm]
        _vals = [_fn(i / 191.0, j / 127.0) for j in range(128)
                 for i in range(192)]
        _fs = max(abs(_fn(_a / 63.0, 0.3) - _fn((_a + 1) / 64.0, 0.3))
                  for _a in range(63))
        _ft = max(abs(_fn(0.3, _b / 63.0) - _fn(0.3, (_b + 1) / 64.0))
                  for _b in range(63))
        _js = abs(_fn(63 / 64.0, 0.3) - _fn(0.0, 0.3))
        _jt = abs(_fn(0.3, 63 / 64.0) - _fn(0.3, 0.0))
        _b2[_nm] = (round(max(_vals) - min(_vals), 2),
                    round(max(_js - _fs, _jt - _ft, 0.0), 4))
    check('R265.3 relief: all 7 technical patterns span > 0.8, wrap jump '
          'never exceeds the field jump',
          all(v[0] > 0.8 and v[1] <= 0.03 for v in _b2.values()), str(_b2))

    # PERFORATION: holes are ROUND (equal depth in all directions at one
    # radius) and the grid is STAGGERED (odd rows centre on the seam,
    # even rows half a cell aside)
    _pf = _g1p['PERFORATION']
    _tc = 1.5 / 8.0

    def _pprobe(_ds, _dt):
        return _pf((0.0 + _ds / 12.0) % 1.0, (_tc + _dt / 8.0) % 1.0)
    _rc = 0.20
    _ax = [_pprobe(_rc, 0), _pprobe(-_rc, 0), _pprobe(0, _rc), _pprobe(0, -_rc)]
    _dg = [_pprobe(_rc * 0.7071, _rc * 0.7071),
           _pprobe(-_rc * 0.7071, _rc * 0.7071),
           _pprobe(_rc * 0.7071, -_rc * 0.7071),
           _pprobe(-_rc * 0.7071, -_rc * 0.7071)]
    _st_ok = (_pf(0.0, _tc) < -0.4                 # hole in an odd row at 0
              and _pf(6.5 / 12.0, 2.5 / 8.0) < -0.4  # even row: centre 0.5
              and _pf(0.0, 2.5 / 8.0) > 0.1)       # even row at 0: sheet
    check('R265.3 PERFORATION: round holes (axial = diagonal depth) in a '
          'staggered grid',
          max(_ax) - min(_ax) < 0.05 and max(_dg) - min(_dg) < 0.05
          and abs(sum(_ax) / 4.0 - sum(_dg) / 4.0) < 0.05 and _st_ok,
          'axial %.3f..%.3f diag %.3f..%.3f stagger %s'
          % (min(_ax), max(_ax), min(_dg), max(_dg), _st_ok))

    # VENT: the recess is SQUARE - the cell-diagonal chord through one
    # recess is ~sqrt(2) longer than the horizontal chord (windowed, so
    # neighbour recesses stay out of the measurement)
    _vf = _g1p['VENT']
    _cs, _ct = 6.5 / 12.0, 2.5 / 8.0
    _wh = sum(1 for _d in range(-9, 10)
              if _vf((_cs + _d * 0.004) % 1.0, _ct) < -0.35)
    # equal SAMPLE RATE on the diagonal (the 45-deg step is sqrt(2)
    # longer, so a square recess must collect ~sqrt(2) more samples)
    _wd = sum(1 for _d in range(-13, 14)
              if _vf((_cs + _d * 0.00283) % 1.0,
                     (_ct + _d * 0.00424) % 1.0) < -0.35)
    check('R265.3 VENT: square recesses (diagonal chord ~ sqrt(2) x '
          'horizontal)',
          _wd > _wh * 1.15,
          'horizontal %d vs diagonal %d samples' % (_wh, _wd))

    # CARBON: the 2/2 twill - band means flip hard and the (2,2)-cell
    # shift is an exact structure period
    _cf = _g1p['CARBON']
    _gA = _gB = _nA = _nB = 0.0
    for _x in range(0, 192, 3):
        for _y in range(0, 128, 3):
            _sx, _ty = _x / 192.0, _y / 128.0
            _v = _cf(_sx, _ty)
            _ci = int(math.floor(_sx * 24))
            _cj = int(math.floor(_ty * 16))
            if ((_ci + _cj) // 2) % 2 == 0:
                _gA += _v; _nA += 1
            else:
                _gB += _v; _nB += 1
    _per = max(abs(_cf(_sx, _ty)
                   - _cf((_sx + 2.0 / 24.0) % 1.0, (_ty + 2.0 / 16.0) % 1.0))
               for _sx in (0.11, 0.37, 0.52, 0.71)
               for _ty in (0.13, 0.29, 0.47, 0.66))
    check('R265.3 CARBON: 2/2 twill - gloss bands flip, weave period '
          'closes',
          abs(_gA / _nA - _gB / _nB) > 0.25 and _per < 1e-6,
          'band means %.3f vs %.3f, period drift %.2g'
          % (_gA / _nA, _gB / _nB, _per))

    # PINDOTS: true hemisphere caps - centre high, half-radius at ~0.72
    # of the cap height, flat base outside the dot
    _pd = _g1p['PINDOTS']
    _v0 = _pd(6.5 / 12.0, 2.5 / 8.0)
    _vh = _pd(6.5 / 12.0 + 0.20 / 12.0, 2.5 / 8.0)
    _ve = _pd(6.5 / 12.0 + 0.40 / 12.0, 2.5 / 8.0)
    _vo = _pd(6.5 / 12.0 + 0.46 / 12.0, 2.5 / 8.0)
    check('R265.3 PINDOTS: hemisphere knobs (cap profile + flat base)',
          _v0 > 0.5 and abs(_vh - (_vo + (_v0 - _vo) * 0.836)) < 0.06
          and abs(_ve - _vo) < 0.02 and abs(_vo - (-0.22)) < 0.05,
          'centre %.2f half %.2f rim %.2f base %.2f' % (_v0, _vh, _ve, _vo))

    # OCTAGONS: octagon faces dominate - the 4.3.8.4 fill factor of the
    # raised area (d8-radius 0.8 of the half cell) is ~0.53
    _oc = [[_g1p['OCTAGONS'](_x / 168.0, _y / 112.0) for _x in range(168)]
           for _y in range(112)]
    _flat = sum(1 for _row in _oc for _v in _row if _v > 0.15)
    check('R265.3 OCTAGONS: octagon trays dominate (fill ~0.53, '
          'grooves + corner squares below)',
          0.40 < _flat / (168.0 * 112.0) < 0.64,
          'raised share %.2f' % (_flat / (168.0 * 112.0)))

    # CHAINLINK: cutting ALONG a wire stays high, cutting across the
    # mesh drops deep - the woven-fence reading (45 deg in mm)
    _chf = _g1p['CHAINLINK']
    _along = [_chf((0.3 + _i * 0.004) % 1.0, (0.3 - _i * 0.006) % 1.0)
              for _i in range(24)]
    _across = [_chf((0.3 + _i * 0.004) % 1.0, 0.3) for _i in range(24)]
    check('R265.3 CHAINLINK: wires run diagonal - along-wire cut reads '
          'higher than the across cut',
          sum(_along) / len(_along) > sum(_across) / len(_across) + 0.15,
          'along %.2f vs across %.2f' % (sum(_along) / len(_along),
                                         sum(_across) / len(_across)))

    # NETGRID: knots proud at the thread crossings, mesh centres deep
    _ng = _g1p['NETGRID']
    _knots = [_ng(_i / 12.0, _j / 8.0) for _i in range(3) for _j in range(3)]
    _mesh = [_ng((_i + 0.5) / 12.0, (_j + 0.5) / 8.0)
             for _i in range(3) for _j in range(3)]
    check('R265.3 NETGRID: knots at the crossings, deep open meshes',
          min(_knots) > 0.2 and max(_mesh) < -0.45
          and min(_knots) - max(_mesh) > 0.7,
          'knots %.2f..%.2f mesh %.2f..%.2f' % (
              min(_knots), max(_knots), min(_mesh), max(_mesh)))

    def _grid265(fn, w=160, h=112):
        return [[fn(x / float(w), y / float(h)) for x in range(w)]
                for y in range(h)]

    def _flood265(grid, pred):
        # connected components (4-neighbour) of pred(cells) on the PERIODIC
        # grid - the wrap counts (the field tiles, so components must close)
        hh, ww = len(grid), len(grid[0])
        seen = [[False] * ww for _ in range(hh)]
        comps = 0
        for y0 in range(hh):
            for x0 in range(ww):
                if seen[y0][x0] or not pred(grid[y0][x0]):
                    continue
                comps += 1
                stack = [(x0, y0)]
                seen[y0][x0] = True
                while stack:
                    cx, cy = stack.pop()
                    for nx, ny in ((cx + 1, cy), (cx - 1, cy),
                                   (cx, cy + 1), (cx, cy - 1)):
                        nx %= ww
                        ny %= hh
                        if not seen[ny][nx] and pred(grid[ny][nx]):
                            seen[ny][nx] = True
                            stack.append((nx, ny))
        return comps

    # HILBERT: the walls form ONE connected network PER TILE (the curve is
    # a single path - 3x2 tiles at k=12/n=8), and the corridors are ONE
    # walkable system across the whole period - the labyrinth promise
    _hb_g = _grid265(_g1p['HILBERT'])
    _hb_wall = sum(1 for row in _hb_g for v in row if v > 0.0)
    check('R265 HILBERT: real curve - one connected wall path per tile, '
          'corridors everywhere walkable',
          0.30 < _hb_wall / (160.0 * 112.0) < 0.68
          and _flood265(_hb_g, lambda v: v > 0.0) == 3 * 2
          and _flood265(_hb_g, lambda v: v < -0.1) == 1,
          'wall %.2f, wall comps %d, corridor comps %d' % (
              _hb_wall / (160.0 * 112.0),
              _flood265(_hb_g, lambda v: v > 0.0),
              _flood265(_hb_g, lambda v: v < -0.1)))

    # MAZE: spanning tree on the torus - the corridor system is ONE connected
    # component (you can walk everywhere), walls stay raised
    _mz_g = _grid265(_g1p['MAZE'])
    _mz_wall = sum(1 for row in _mz_g for v in row if v > 0.0)
    check('R265 MAZE: spanning-tree labyrinth - corridors all connected',
          0.18 < _mz_wall / (160.0 * 112.0) < 0.55
          and _flood265(_mz_g, lambda v: v < -0.05) == 1,
          'wall %.2f, corridor components %d' % (
              _mz_wall / (160.0 * 112.0),
              _flood265(_mz_g, lambda v: v < -0.05)))

    # STONEWALL: exactly n mortar-bed lines (t-periodic courses)
    _sw_g = _grid265(_g1p['STONEWALL'])
    _sw_prof = [sum(row) / len(row) for row in _sw_g]
    _sw_dips = 0
    for _i, _v in enumerate(_sw_prof):
        if (_v < -0.30 and _sw_prof[_i - 1] >= -0.30):
            _sw_dips += 1
    check('R265 STONEWALL: n=8 mortar bed lines around the height period',
          _sw_dips == 8, 'dips=%d (rows n=8)' % _sw_dips)

    # TILES: flat tops dominate, grout valleys are a minority - a tiled
    # wall, not a checkerboard parity flip
    _ti_g = _grid265(_g1p['TILES'])
    _ti_flat = sum(1 for row in _ti_g for v in row if 0.2 <= v <= 0.68)
    _ti_grout = sum(1 for row in _ti_g for v in row if v < -0.45)
    _tot = 160.0 * 112.0
    check('R265 TILES: flat tile faces dominate over recessed grout',
          _ti_flat / _tot > 0.42 and 0.04 < _ti_grout / _tot < 0.35,
          'flat %.2f grout %.2f' % (_ti_flat / _tot, _ti_grout / _tot))

    # PARQUET (R265.2 form truth): a chevron slat must read LONG, the
    # diagonal must be a real diagonal (30..75 deg) and the direction
    # must flip in every column. Measured by TRACKING one joint valley
    # across each column (immune to the aliasing that kills correlation
    # shifts when the slat wave is finer than the shift).
    _pq_g = _grid265(_g1p['PARQUET'], w=168, h=112)
    _pq_cols = 12                      # ke = k+(k&1) at k=12
    _pq_cw = 168 // _pq_cols           # column width in px (14)

    def _pq_slope(_col):
        def _f(_fx, _y):
            return _pq_g[_y % 112][int(_col * _pq_cw + _fx * _pq_cw) % 168]
        _y0 = min(range(112), key=lambda yy: _f(0.3, yy))
        _y = _y0
        for _st in range(9):
            _y = min(range(_y - 3, _y + 4),
                     key=lambda yy: _f(0.35 + (_st + 1) * 0.05, yy))
        return (_y - _y0) / (0.4 * _pq_cw)
    _pq_slopes = [_pq_slope(_c) for _c in range(_pq_cols)]
    _pq_ev = sorted(_pq_slopes[0::2])[len(_pq_slopes[0::2]) // 2]
    _pq_od = sorted(_pq_slopes[1::2])[len(_pq_slopes[1::2]) // 2]
    _pq_m = abs(_pq_ev - _pq_od) / 2.0
    _pq_ang = math.degrees(math.atan(_pq_m))
    # slat aspect: joint spacing on a centre-column t-profile (deep
    # valleys only - the grain rides on the face, the groove is clean)
    def _valleys(_prof, _thr, _gap=4):
        _out = []
        for _i in range(1, len(_prof) - 1):
            if (_prof[_i] < _thr and _prof[_i] <= _prof[_i - 1]
                    and _prof[_i] <= _prof[(_i + 1) % len(_prof)]
                    and (not _out or _i - _out[-1] > _gap)):
                _out.append(_i)
        return len(_out)
    _pq_sc = (_pq_cols // 2 * _pq_cw + _pq_cw // 2) / 168.0
    _pq_A = _valleys([_g1p['PARQUET'](_pq_sc, _y / 112.0) for _y in range(112)], -0.2)
    _pq_dc = 112.0 / max(1, _pq_A)     # joint spacing in px
    _pq_L = _pq_cw * math.sqrt(1 + _pq_m * _pq_m)
    _pq_b = _pq_dc / math.sqrt(1 + _pq_m * _pq_m)
    check('R265 PARQUET: chevron - direction flips per column, slats '
          'read LONG (angle 30..75, L/B > 3)',
          (_pq_ev > 0) != (_pq_od > 0) and abs(_pq_ev) > 0.1
          and abs(_pq_od) > 0.1
          and 30.0 <= _pq_ang <= 75.0 and _pq_L / _pq_b > 3.0,
          'even %+.2f odd %+.2f -> %.0f deg, L/B %.1f (%d joints)'
          % (_pq_ev, _pq_od, _pq_ang, _pq_L / _pq_b, _pq_A))

    # LAMINATE / TILES form truth (R265.2 'the planks read like tiles'):
    # a laminate board is LONG (end-joint spacing >> board width), a wall
    # tile is SQUARE. Measured as deep-valley spacing on the s- and
    # t-profiles of a 168x112 grid (mm-proportional at k=12/n=8/ar=1).
    _ke_l = max(4, 2 * 12)             # laminate board count at k=12
    _lam_sc = (_ke_l // 2 + 0.5) / float(_ke_l)      # board CENTRE
    _lam_B = _valleys([_g1p['LAMINATE'](_x / 168.0, 0.5) for _x in range(168)], -0.25)
    _lam_A = _valleys([_g1p['LAMINATE'](_lam_sc, _y / 112.0) for _y in range(112)], -0.12)
    _lam_asp = (112.0 / max(1, _lam_A)) / (168.0 / max(1, _lam_B))
    _ti_B = _valleys([_g1p['TILES'](_x / 168.0, 0.53) for _x in range(168)], -0.3)
    _ti_A = _valleys([_g1p['TILES'](0.53, _y / 112.0) for _y in range(112)], -0.3)
    _ti_asp = (112.0 / max(1, _ti_A)) / (168.0 / max(1, _ti_B))
    check('R265 LAMINATE: boards read LONG, TILES read SQUARE '
          '(aspect laminate > 2.5, tiles 0.75..1.35)',
          _lam_asp > 2.5 and 0.75 <= _ti_asp <= 1.35 and _lam_asp > _ti_asp * 2.0,
          'laminate %.1f (%d x %d boards), tiles %.2f (%d x %d)'
          % (_lam_asp, _lam_B, _lam_A, _ti_asp, _ti_B, _ti_A))

    # LAMINATE: grain streaks ALONG the plank - horizontal gradients clearly
    # dominate vertical ones, and MORE than on PLANKS (the distinguisher)
    def _aniso265(fn):
        g = _grid265(fn)
        gs = sum(abs(g[y][(x + 1) % 160] - g[y][x])
                 for y in range(112) for x in range(160))
        gt = sum(abs(g[(y + 1) % 112][x] - g[y][x])
                 for y in range(112) for x in range(160))
        return gs / max(1e-9, gt)
    _lam_a = _aniso265(_g1p['LAMINATE'])
    _plk_a = _aniso265(_g1p['PLANKS'])
    check('R265 LAMINATE: dominant along-plank grain (anisotropy > PLANKS)',
          _lam_a > 1.35 and _lam_a > _plk_a * 1.25,
          'laminate %.2f vs planks %.2f' % (_lam_a, _plk_a))

    # RUBBLE: ~gx*gy stones (jittered Voronoi sites), no course reading
    _ru_g = _grid265(_g1p['RUBBLE'])
    _ru_peaks = 0
    for _y in range(2, 110, 3):
        for _x in range(2, 158, 3):
            _v = _ru_g[_y][_x]
            if _v > 0.1 and all(
                    _ru_g[_y + dy][_x + dx] <= _v
                    for dy in (-2, -1, 0, 1, 2) for dx in (-2, -1, 0, 1, 2)):
                _ru_peaks += 1
    check('R265 RUBBLE: stone count matches the site grid (~96)',
          58 <= _ru_peaks <= 132,
          'peaks=%d (grid 12x8=96)' % _ru_peaks)
    from PIL import Image
    imgp = os.path.join(d, 'logo.png')
    im = Image.new('L', (60, 30), 255)
    px = im.load()
    for y in range(30):
        for x in range(60):
            if 15 <= x <= 44 and 8 <= y <= 22:
                px[x, y] = max(0, 30 + (x - 15) * 4)
    im.save(imgp)
    prep = r2_texture._map_prepare(Image.open(imgp).convert('L'))
    check('D5: Otsu background = alpha (corners flat, logo carries)',
          prep.getpixel((2, 2)) == 0 and prep.getpixel((30, 15)) > 60,
          '%r %r' % (prep.getpixel((2, 2)), prep.getpixel((30, 15))))
    res = {}
    for mm, mp in (('TILE', 'CENTER'), ('ONCE', 'TOP'), ('ONCE', 'CENTER'),
                   ('ONCE', 'BOTTOM')):
        out, info = r2_texture.apply_texture(
            src, out_dir=d, mode='BUMPS', bump_pattern='MAP',
            bump_scale=10.0, bump_amp=0.4, zsize=10.0,
            map_file=imgp, map_mode=mm, map_pos=mp)
        res[(mm, mp)] = (info['shifted'], info['z_repeats'])
    check('D6: MAP TILE repeats, ONCE wraps once + all three positions',
          res[('TILE', 'CENTER')][1] > 1
          and all(res[('ONCE', p)][1] == 1
                  for p in ('TOP', 'CENTER', 'BOTTOM'))
          and all(v[0] > 0 for v in res.values()), str(res))
    try:
        r2_texture.apply_texture(
            src, out_dir=d, mode='BUMPS', bump_pattern='MAP',
            bump_scale=10.0, bump_amp=0.4, zsize=10.0,
            map_file=imgp, map_mode='NOPE')
        check('D7: a bad MAP mode is refused', False, 'no ValueError')
    except ValueError:
        check('D7: a bad MAP mode is refused', True, '')
    check('D8: watcher reads the opt-in tilt switch and MAP settings',
      'texture_map_mode' in _pp and 'texture_map_pos' in _pp
      and 'texture_tilt' in _pp and 'optional tilt' in _pp
      and 'MAP once around' in _pp, '')
    check('D9: LCD has opt-in Tilt control and MAP mode/position rows',
          '[menu __main __preprint __mods __tex __tilt]' in _lcd
          and 'texture_tilt' in _lcd
          and '[menu __main __preprint __mods __tex __mmode]' in _lcd
          and '[menu __main __preprint __mods __tex __mpos]' in _lcd, '')
    check('D10: menu - FUZZY and BUMPS parameters are separated by enable',
          'texture_mode|default(\'\')|string == \'FUZZY\'' in _lcd
          and 'texture_mode|default(\'\')|string == \'BUMPS\'' in _lcd, '')
    # ---- R266.2 (bite 3): organics ----------------------------------------
    print('--- R266.2) bite 3: wood, old bark, leather, peel, mud, folds -')
    _b3 = ('RINGS', 'OAK', 'BEECH', 'KNOT', 'OLDBARK', 'LEATHER',
           'ORANGE', 'CRACKS', 'WRINKLE')
    _b3m = {}
    for _nm in _b3:
        _fn = _g1p[_nm]
        _vals = [_fn(i / 191.0, j / 127.0) for j in range(128)
                 for i in range(192)]
        _fs = max(abs(_fn(_a / 63.0, 0.3) - _fn((_a + 1) / 64.0, 0.3))
                  for _a in range(63))
        _ft = max(abs(_fn(0.3, _b / 63.0) - _fn(0.3, (_b + 1) / 64.0))
                  for _b in range(63))
        _js = abs(_fn(63 / 64.0, 0.3) - _fn(0.0, 0.3))
        _jt = abs(_fn(0.3, 63 / 64.0) - _fn(0.3, 0.0))
        _b3m[_nm] = (round(max(_vals) - min(_vals), 2),
                     round(max(_js - _fs, _jt - _ft, 0.0), 4))
    check('R266.2 relief: all 9 organic patterns span > 0.8, wrap jump '
          'never exceeds the field jump',
          all(v[0] > 0.8 and v[1] <= 0.03 for v in _b3m.values()), str(_b3m))

    _sig266 = {nm: tuple(round(_g1p[nm](x / 32.0, y / 32.0), 2)
                         for y in range(32) for x in range(32))
               for nm in _b3}
    _sig_all266 = dict(_signatures)
    _sig_all266.update(_sig265)
    _sig_all266.update(_sig266)
    check('R266.2 distinct: the 9 organic fields differ from each other, '
          'the 14 bite-1/2 fields and the 10 classics',
          len(set(_sig_all266.values())) == len(_sig_all266),
          'unique %d/%d' % (len(set(_sig_all266.values())),
                            len(_sig_all266)))

    _W3, _H3 = 160, 112

    def _grid3(fn):
        return [[fn(x / float(_W3), y / float(_H3))
                 for x in range(_W3)] for y in range(_H3)]

    def _zwgaps3(fn):
        gaps = []
        for y in range(0, _H3, 2):
            row = [fn(x / float(_W3), y / float(_H3)) for x in range(_W3)]
            idx = [i for i in range(_W3)
                   if (row[i] >= 0) != (row[i - 1] >= 0)]
            for a, b in zip(idx, idx[1:]):
                if b - a > 1:
                    gaps.append(b - a)
        gaps.sort()
        return (gaps[len(gaps) // 20] if gaps else 0,
                gaps[len(gaps) // 2] if gaps else 0)

    # RINGS: growth rings run AROUND (horizontal bands, the cross-cut
    # promise) and their SPACING SCATTERS - stonewall courses are even
    _rg_g = _grid3(_g1p['RINGS'])
    _pt = [sum(_rg_g[y][x] for x in range(_W3)) / _W3 for y in range(_H3)]
    _ps = [sum(_rg_g[y][x] for y in range(_H3)) / _H3 for x in range(_W3)]
    _vt = sum((v - sum(_pt) / _H3) ** 2 for v in _pt) / _H3
    _vs = sum((v - sum(_ps) / _W3) ** 2 for v in _ps) / _W3
    _rmins = [y for y in range(1, _H3 - 1)
              if _pt[y] < _pt[y - 1] and _pt[y] < _pt[y + 1]
              and _pt[y] < -0.2]
    _rd = [b - a for a, b in zip(_rmins, _rmins[1:])]
    _rm = sum(_rd) / len(_rd) if _rd else 0.0
    _rs = (sum((d - _rm) ** 2 for d in _rd) / len(_rd)) ** 0.5 \
        if _rd else 0.0
    _sw_g = _grid3(_g1p['STONEWALL'])
    _swp = [sum(_sw_g[y][x] for x in range(_W3)) / _W3 for y in range(_H3)]
    _swm = [y for y in range(1, _H3 - 1)
            if _swp[y] < _swp[y - 1] and _swp[y] < _swp[y + 1]
            and _swp[y] < -0.2]
    _swd = [b - a for a, b in zip(_swm, _swm[1:])]
    _swmm = sum(_swd) / len(_swd) if _swd else 0.0
    _sws = (sum((d - _swmm) ** 2 for d in _swd) / len(_swd)) ** 0.5 \
        if _swd else 0.0
    check('R266.2 RINGS: bands run around (row var >> col var) and the '
          'ring SPACING scatters (growth) - stonewall courses stay even',
          _vt > 20.0 * max(_vs, 1e-9)
          and (_rs / _rm if _rm else 0.0) > 0.30
          and (_sws / _swmm if _swmm else 0.0) < 0.05
          and len(_rd) >= 6,
          'q=%.1f rings rel-std %.2f vs stonewall %.2f (%d rings)'
          % (_vt / max(_vs, 1e-9), _rs / _rm if _rm else 0.0,
             _sws / _swmm if _swmm else 0.0, len(_rd)))

    # OAK: the fibre runs UP - columns vary more than rows, the pores are
    # deep-but-sparse (bundled streaks), the crest distance is COARSE
    _ok_g = _grid3(_g1p['OAK'])
    _okt = [sum(_ok_g[y][x] for x in range(_W3)) / _W3 for y in range(_H3)]
    _oks = [sum(_ok_g[y][x] for y in range(_H3)) / _H3 for x in range(_W3)]
    _okvt = sum((v - sum(_okt) / _H3) ** 2 for v in _okt) / _H3
    _okvs = sum((v - sum(_oks) / _W3) ** 2 for v in _oks) / _W3
    _okv = [v for row in _ok_g for v in row]
    _ok_pores = sum(1 for v in _okv if v < -0.45) / float(len(_okv))
    _okq = _zwgaps3(_g1p['OAK'])[1]
    check('R266.2 OAK: vertical fibre (col var > 2x row var), deep pore '
          'grooves 4..16% of the surface, coarse crest spacing',
          _okvs > 2.0 * _okvt and 0.04 < _ok_pores < 0.16 and _okq > 8,
          'col/row %.2f pores %.2f q50 %dpx' % (
              _okvs / max(_okvt, 1e-9), _ok_pores, _okq))

    # BEECH: the QUIET wood - fine everywhere (closer zero crossings than
    # oak), calm plateaus dominate, no deep pores
    _be_v = [_g1p['BEECH'](i / 191.0, j / 127.0)
             for j in range(128) for i in range(192)]
    _be_span = max(_be_v) - min(_be_v)
    _be_plateau = sum(1 for v in _be_v if 0.2 <= v <= 0.4) / float(len(_be_v))
    _be_deep = sum(1 for v in _be_v if v < -0.45) / float(len(_be_v))
    _beq = _zwgaps3(_g1p['BEECH'])[1]
    check('R266.2 BEECH: fine (zero-cross gaps <= 8px, finer than oak), '
          'calm plateaus > 30%, no deep pores (< 1%)',
          _beq <= 8 and _beq < _okq and _be_plateau > 0.30
          and _be_deep < 0.01 and 0.8 < _be_span <= 1.2,
          'q50 %dpx plateau %.2f deep %.3f span %.2f' % (
              _beq, _be_plateau, _be_deep, _be_span))

    # KNOT: burl eyes - the field stays high (fibre), the valleys fall
    # into MANY SMALL compact components (the eye rings), unlike BARK's
    # long through-going fissures
    _kn_g = _grid3(_g1p['KNOT'])
    _kn_v = [v for row in _kn_g for v in row]
    _kn_high = sum(1 for v in _kn_v if v > 0.0) / float(len(_kn_v))
    _kn_n = _flood265(_kn_g, lambda v: v < -0.05)
    _kn_zw = 0
    for y in range(0, _H3, 2):
        row = [_g1p['KNOT'](x / float(_W3), y / float(_H3))
               for x in range(_W3)]
        _kn_zw += sum(1 for i in range(_W3)
                      if (row[i] >= 0) != (row[i - 1] >= 0))
    _bk_g = _grid3(_g1p['BARK'])
    _bk_zw = 0
    for y in range(0, _H3, 2):
        row = [_g1p['BARK'](x / float(_W3), y / float(_H3))
               for x in range(_W3)]
        _bk_zw += sum(1 for i in range(_W3)
                      if (row[i] >= 0) != (row[i - 1] >= 0))
    check('R266.2 KNOT: burl - high fibre field, valleys as MANY SMALL '
          'eye components, far fewer sign flips than bark fissures',
          _kn_high > 0.55 and _kn_n >= 8 and _kn_zw < 250 and _bk_zw > 500,
          'high %.2f comps %d zw %d (bark %d)' % (
              _kn_high, _kn_n, _kn_zw, _bk_zw))

    # OLDBARK: coarse furrows - few column-profile minima (bark has ~2x),
    # deep furrow share 4..16%, strong span (the deep-relief showpiece)
    _ob_g = _grid3(_g1p['OLDBARK'])
    _obp = [sum(_ob_g[y][x] for y in range(_H3)) / _H3 for x in range(_W3)]
    _obm = [x for x in range(1, _W3 - 1)
            if _obp[x] < _obp[x - 1] and _obp[x] < _obp[x + 1]
            and _obp[x] < -0.1]
    _bkp = [sum(_bk_g[y][x] for y in range(_H3)) / _H3 for x in range(_W3)]
    _bkm = [x for x in range(1, _W3 - 1)
            if _bkp[x] < _bkp[x - 1] and _bkp[x] < _bkp[x + 1]
            and _bkp[x] < -0.1]
    _ob_v = [v for row in _ob_g for v in row]
    _ob_deep = sum(1 for v in _ob_v if v < -0.45) / float(len(_ob_v))
    check('R266.2 OLDBARK: coarse plates (fewer furrow minima than bark), '
          'deep furrow share 4..16%, span > 1.4 (deep-relief material)',
          len(_obm) <= 5 and len(_bkm) >= 6 and 0.04 < _ob_deep < 0.16
          and (max(_ob_v) - min(_ob_v)) > 1.4,
          'furrows %d (bark %d) deep %.2f span %.2f' % (
              len(_obm), len(_bkm), _ob_deep, max(_ob_v) - min(_ob_v)))

    # LEATHER: diamond quilting - cushions high at the cell centres,
    # stitch seams the VALLEYS (chainlink keeps its WIRES high instead)
    _lf = _g1p['LEATHER']
    _kp3, _rw3 = 12, 8
    _cush, _seam = [], []
    for x in range(_W3):
        for y in range(_H3):
            _s3, _t3 = x / float(_W3), y / float(_H3)
            _u3 = (_s3 * _kp3 + _t3 * _rw3) % 1.0
            _v3 = (_t3 * _rw3 - _s3 * _kp3) % 1.0
            _du3, _dv3 = min(_u3, 1 - _u3), min(_v3, 1 - _v3)
            if _du3 > 0.42 and _dv3 > 0.42:
                _cush.append(_lf(_s3, _t3))
            if _du3 < 0.03 or _dv3 < 0.03:
                _seam.append(_lf(_s3, _t3))
    check('R266.2 LEATHER: cushions proud at the diamond centres '
          '(min > 0.5), seams are valleys (mean < -0.2, max <= 0.15)',
          len(_cush) > 200 and len(_seam) > 500
          and min(_cush) > 0.5 and sum(_seam) / len(_seam) < -0.2
          and max(_seam) <= 0.15,
          'cushion n=%d min %.2f | seam n=%d mean %.2f max %.2f' % (
              len(_cush), min(_cush), len(_seam),
              sum(_seam) / len(_seam), max(_seam)))

    # ORANGE: micro peel - wide calm plateaus, one-sided dimple pits,
    # fine structure
    _or_v = [_g1p['ORANGE'](i / 191.0, j / 127.0)
             for j in range(128) for i in range(192)]
    _or_plateau = sum(1 for v in _or_v if 0.2 <= v <= 0.4) \
        / float(len(_or_v))
    _or_pits = sum(1 for v in _or_v if v < 0.0) / float(len(_or_v))
    _orq = _zwgaps3(_g1p['ORANGE'])[1]
    check('R266.2 ORANGE: peel - plateaus > 55%, one-sided pits 15..40%, '
          'fine (zero-cross gaps <= 8px)',
          _or_plateau > 0.55 and 0.15 < _or_pits < 0.40 and _orq <= 8,
          'plateau %.2f pits %.2f q50 %dpx' % (
              _or_plateau, _or_pits, _orq))

    # CRACKS: mud - the crack network is NARROW (much thinner than the
    # maze corridors) and CONNECTED (one shrinks as it dries); plates
    # dominate the area. Measured at 2x resolution - the crack core is
    # ~0.1 cell wide and a 160px grid fragments it into alias slivers.
    _ckW, _ckH = 320, 224
    _ck_g = [[_g1p['CRACKS'](x / float(_ckW), y / float(_ckH))
              for x in range(_ckW)] for y in range(_ckH)]
    _ck_v = [v for row in _ck_g for v in row]
    _ck_crack = sum(1 for v in _ck_v if v < -0.45) / float(len(_ck_v))
    _ck_plate = sum(1 for v in _ck_v if v > 0.3) / float(len(_ck_v))
    _ck_seen = [[False] * _ckW for _ in range(_ckH)]
    _ck_net = 0
    for _y0 in range(_ckH):
        for _x0 in range(_ckW):
            if _ck_seen[_y0][_x0] or not (_ck_g[_y0][_x0] < -0.30):
                continue
            _ck_net += 1
            _stk = [(_x0, _y0)]
            _ck_seen[_y0][_x0] = True
            while _stk:
                _cx, _cy = _stk.pop()
                for _nx, _ny in ((_cx + 1, _cy), (_cx - 1, _cy),
                                 (_cx, _cy + 1), (_cx, _cy - 1)):
                    _nx %= _ckW
                    _ny %= _ckH
                    if not _ck_seen[_ny][_nx] and _ck_g[_ny][_nx] < -0.30:
                        _ck_seen[_ny][_nx] = True
                        _stk.append((_nx, _ny))
    _mz_g = _grid3(_g1p['MAZE'])
    _mz_v = [v for row in _mz_g for v in row]
    _mz_corridor = sum(1 for v in _mz_v if v < -0.05) / float(len(_mz_v))
    # 'narrow' is measured AGAINST THE PLATEAU level (the whole fissure
    # incl. its flanks, v < 0.05) and against the maze corridors - mud
    # cracks are FISSURES, not corridors; the deep cores (v < -0.45)
    # stay a small share of that
    _ck_rille = sum(1 for v in _ck_v if v < 0.05) / float(len(_ck_v))
    check('R266.2 CRACKS: narrow connected crack network (fissure share '
          '< 60% of the maze corridors), crowned plates dominate',
          0.02 < _ck_crack < 0.26 and 0.15 < _ck_rille < 0.45
          and _ck_net <= 4 and _ck_plate > 0.55
          and _ck_rille < 0.60 * _mz_corridor,
          'cores %.3f rille %.3f (maze corridors %.3f) net comps %d '
          'plates %.2f' % (_ck_crack, _ck_rille, _mz_corridor, _ck_net,
                           _ck_plate))

    # WRINKLE: big folds - the s autocorrelation runs long (CREPE is ~5x
    # finer) and the fold valley is ONE connected blanket
    def _acl3(fn):
        row = [fn(x / float(_W3), 0.37) for x in range(_W3)]
        _m = sum(row) / _W3
        row = [v - _m for v in row]
        for lag in range(1, 60):
            if sum(row[i] * row[(i + lag) % _W3]
                   for i in range(_W3 - lag)) <= 0:
                return lag / float(_W3)
        return 1.0
    _wr_acl = _acl3(_g1p['WRINKLE'])
    _cp_acl = _acl3(_g1p['CREPE'])
    _wr_g = _grid3(_g1p['WRINKLE'])
    _wr_v = [v for row in _wr_g for v in row]
    _wr_crest = sum(1 for v in _wr_v if v > 0.3) / float(len(_wr_v))
    check('R266.2 WRINKLE: heavy folds - autocorrelation >= 2.5x CREPE, '
          'crests cover 5..30% (sharp ridges, not blanket noise)',
          _wr_acl > 0.06 and _wr_acl > 2.5 * _cp_acl
          and 0.05 < _wr_crest < 0.30,
          'acl %.3f vs crepe %.3f, crests %.2f' % (
              _wr_acl, _cp_acl, _wr_crest))

    # ---- R266.3 (bite 4): decor & haptics ---------------------------------
    print('--- R266.3) bite 4: hearts, balls, wallpaper, roof, crochet -')
    _b4 = ('HEARTS', 'GOLF', 'BASKETBALL', 'RAUFASER', 'ROOFTILES',
           'CROCHET')
    _b4m = {}
    for _nm in _b4:
        _fn = _g1p[_nm]
        _vals = [_fn(i / 191.0, j / 127.0) for j in range(128)
                 for i in range(192)]
        _fs = max(abs(_fn(_a / 63.0, 0.3) - _fn((_a + 1) / 64.0, 0.3))
                  for _a in range(63))
        _ft = max(abs(_fn(0.3, _b / 63.0) - _fn(0.3, (_b + 1) / 64.0))
                  for _b in range(63))
        _js = abs(_fn(63 / 64.0, 0.3) - _fn(0.0, 0.3))
        _jt = abs(_fn(0.3, 63 / 64.0) - _fn(0.3, 0.0))
        _b4m[_nm] = (round(max(_vals) - min(_vals), 2),
                     round(max(_js - _fs, _jt - _ft, 0.0), 4))
    check('R266.3 relief: all 6 decor patterns span > 0.8, wrap jump '
          'never exceeds the field jump',
          all(v[0] > 0.8 and v[1] <= 0.03 for v in _b4m.values()), str(_b4m))

    _sig2663 = {nm: tuple(round(_g1p[nm](x / 32.0, y / 32.0), 2)
                          for y in range(32) for x in range(32))
                for nm in _b4}
    _sig_all2663 = dict(_sig_all266)
    _sig_all2663.update(_sig2663)
    check('R266.3 distinct: the 6 decor fields differ from each other and '
          'from every earlier pattern',
          len(set(_sig_all2663.values())) == len(_sig_all2663),
          'unique %d/%d' % (len(set(_sig_all2663.values())),
                            len(_sig_all2663)))

    _d4h = _grid3(_g1p['HEARTS'])
    _d4hv = [v for row in _d4h for v in row]
    _d4h_up = sum(1 for v in _d4hv if v > 0.3) / float(len(_d4hv))
    _d4h_first = []
    for _r in range(8):
        for _y in range(_r * 14, (_r + 1) * 14):
            _xs = [x for x in range(_W3) if _d4h[_y][x] > 0.3]
            if _xs:
                _d4h_first.append(min(_xs))
                break
    _d4h_cell = _W3 / 12.0
    _d4h_stag = (len(set(_d4h_first)) == 2
                 and 0.25 * _d4h_cell < abs(_d4h_first[0] - _d4h_first[1])
                 < 0.75 * _d4h_cell)
    check('R266.3 HEARTS: raised share 15..40%, rows staggered by HALF a '
          'cell (adjacent rows start at two alternating offsets)',
          0.15 < _d4h_up < 0.40 and _d4h_stag,
          'up %.3f firsts %s cell %.1f' % (_d4h_up, _d4h_first, _d4h_cell))

    _d4g = [v for row in _grid3(_g1p['GOLF']) for v in row]
    check('R266.3 GOLF: dents cover 22..42% (dense, no rim land), the '
          'deep core is small (spherical cap), nothing rises above the '
          'flat land',
          0.22 < sum(1 for v in _d4g if v < -0.45) / float(len(_d4g)) < 0.42
          and 0.02 < sum(1 for v in _d4g if v < -0.70) / float(len(_d4g)) < 0.12
          and sum(1 for v in _d4g if v > 0.42) == 0,
          'dent %.3f core %.3f' % (
              sum(1 for v in _d4g if v < -0.45) / float(len(_d4g)),
              sum(1 for v in _d4g if v < -0.70) / float(len(_d4g))))

    _d4b = [v for row in _grid3(_g1p['BASKETBALL']) for v in row]
    check('R266.3 BASKETBALL: channels 15..40%, pebble band 20..45% '
          '(both live between the extremes)',
          0.15 < sum(1 for v in _d4b if v < -0.45) / float(len(_d4b)) < 0.40
          and 0.20 < sum(1 for v in _d4b if 0.3 < v < 0.85) / float(len(_d4b)) < 0.45,
          'chan %.3f pebble %.3f' % (
              sum(1 for v in _d4b if v < -0.45) / float(len(_d4b)),
              sum(1 for v in _d4b if 0.3 < v < 0.85) / float(len(_d4b))))

    _d4r = [v for row in _grid3(_g1p['RAUFASER']) for v in row]
    check('R266.3 RAUFASER: sparse chunks (5..25% raised), NO deep values '
          'at all - wallpaper stays a closed wall',
          0.05 < sum(1 for v in _d4r if v > 0.3) / float(len(_d4r)) < 0.25
          and sum(1 for v in _d4r if v < -0.3) == 0,
          'up %.3f deep %d' % (
              sum(1 for v in _d4r if v > 0.3) / float(len(_d4r)),
              sum(1 for v in _d4r if v < -0.3)))

    _d4t = _grid3(_g1p['ROOFTILES'])
    _d4tv = [v for row in _d4t for v in row]
    _d4t_deep = sum(1 for v in _d4tv if v < -0.45) / float(len(_d4tv))
    _d4t_cmin = min(min(_d4t[y][x] for y in range(_H3)) for x in range(_W3))
    _d4t_fx = min((x for x in range(_W3)
                   if min(_d4t[y][x] for y in range(_H3)) == _d4t_cmin))
    _d4t_run = sum(1 for y in range(_H3) if _d4t[y][_d4t_fx] < -0.2) / float(_H3)
    _d4t_rowdeep = [sum(1 for x in range(_W3) if _d4t[y][x] < -0.4)
                    / float(_W3) for y in range(_H3)]
    _d4t_bands = sum(1 for i in range(_H3)
                     if _d4t_rowdeep[i] > 0.3
                     and (i == 0 or _d4t_rowdeep[i - 1] <= 0.3))
    check('R266.3 ROOFTILES: course shadow 15..35% of the area, exactly '
          '2*n course bands (16), and the deepest side fold runs '
          'VERTICALLY through every row (no stagger - the brick '
          'difference)',
          0.15 < _d4t_deep < 0.35 and _d4t_bands == 16 and _d4t_run > 0.9,
          'deep %.3f bands %d falz-run %.3f' % (
              _d4t_deep, _d4t_bands, _d4t_run))

    _d4c = _grid3(_g1p['CROCHET'])
    _d4cv = [v for row in _d4c for v in row]
    _d4c_up = sum(1 for v in _d4cv if v > 0.3) / float(len(_d4cv))
    _d4c_seen = [[False] * _W3 for _ in range(_H3)]
    _d4c_n = 0
    _d4c_max = 0
    for _y0 in range(_H3):
        for _x0 in range(_W3):
            if _d4c_seen[_y0][_x0] or not _d4c[_y0][_x0] < -0.6:
                continue
            _d4c_n += 1
            _sz = 0
            _stk = [(_x0, _y0)]
            _d4c_seen[_y0][_x0] = True
            while _stk:
                _cx, _cy = _stk.pop()
                _sz += 1
                for _nx, _ny in ((_cx + 1, _cy), (_cx - 1, _cy),
                                 (_cx, _cy + 1), (_cx, _cy - 1)):
                    _nx %= _W3
                    _ny %= _H3
                    if not _d4c_seen[_ny][_nx] and _d4c[_ny][_nx] < -0.6:
                        _d4c_seen[_ny][_nx] = True
                        _stk.append((_nx, _ny))
            _d4c_max = max(_d4c_max, _sz)
    check('R266.3 CROCHET: one eyelet per stitch cell (60..130 holes, '
          'k12x8=96 expected), each hole SMALL (no giant gap - the wall '
          'stays printable), knots cover 20..50%',
          60 <= _d4c_n <= 130 and _d4c_max <= 60 and 0.20 < _d4c_up < 0.50,
          'holes %d max %d up %.3f' % (_d4c_n, _d4c_max, _d4c_up))

    # G4: coarse vase paths get resampled to <=1.5 mm XY chords while
    # retaining the final absolute-E coordinate and total relative extrusion.
    _g4src = os.path.join(d, 'coarse_vase.gcode')
    _coords = ((0, 0), (40, 0), (40, 40), (0, 40), (0, 0))
    _g4abs = ['G90', 'M82', ';TYPE:Outer wall']
    _g4rel = ['G90', 'M83', ';TYPE:Outer wall']
    _e = 0.0
    for _z in (0.2, 0.4):
        for _i, (_x, _y) in enumerate(_coords):
            _delta = 0.1 if _i == 0 else 0.4
            _e += _delta
            _g4abs.append('G1 X%d Y%d Z%.1f E%.5f' % (_x, _y, _z, _e))
            _g4rel.append('G1 X%d Y%d Z%.1f E%.5f' % (_x, _y, _z, _delta))
    open(_g4src, 'w').write('\n'.join(_g4abs) + '\n')
    _g4out, _g4info = r2_texture.apply_texture(
        _g4src, out_dir=d, mode='BUMPS', bump_pattern='BARK',
        bump_scale=10, bump_amp=0.4, zsize=4)
    _g4lines = [x for x in open(_g4out).read().splitlines()
                if x.startswith('G1 ')]
    _g4last_e = re.findall(r'(?<![A-Z])E(-?[0-9.]+)', _g4lines[-1])[-1]
    check('G4: coarse vase segments subdivide and absolute E ends unchanged',
          _g4info['subdivisions'] > 100 and len(_g4lines) > 200
          and float(_g4last_e) == 3.4,
          'subdivisions=%s end_E=%s' % (_g4info['subdivisions'], _g4last_e))
    open(_g4src, 'w').write('\n'.join(_g4rel) + '\n')
    _g4out2, _g4info2 = r2_texture.apply_texture(
        _g4src, out_dir=d, mode='BUMPS', bump_pattern='BARK',
        bump_scale=10, bump_amp=0.4, zsize=4)
    _g4eout = sum(float(re.findall(r'(?<![A-Z])E(-?[0-9.]+)', x)[-1])
                  for x in open(_g4out2).read().splitlines()
                  if x.startswith('G1 ') and re.search(r'(?<![A-Z])E', x))
    check('G4: M83 subdivisions conserve total extrusion',
          abs(_g4eout - 3.4) < 1e-6 and _g4info2['subdivisions'] > 100,
          'E %.7f / subdivisions %d' % (_g4eout, _g4info2['subdivisions']))
finally:
    shutil.rmtree(d, ignore_errors=True)

print('\n%d checks, %d failed' % (ok + fails, fails))
raise SystemExit(1 if fails else 0)
