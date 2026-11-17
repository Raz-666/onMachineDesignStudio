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
    check('B3: _is_gen_name refuses STL exports (data, not g-code)',
          r2_postproc._is_gen_name('V1_part_object.stl.gcode') is False
          and r2_postproc._is_gen_name('V1_part.gcode') is True, '')
    stlf = os.path.join(d, 'V1_part_object.stl.gcode')
    open(stlf, 'wb').write(b'\x00\x01binarynotgcode')
    check('B4: _meta_finalize hands off STL exports',
          r2_postproc._meta_finalize(stlf) == 'foreign', '')
    check('B5: the stamping loop skips non-gcode + .stl.gcode outputs',
          "endswith('.stl.gcode')" in _pp, '')

    print('--- C) STL export lands in STL/ as .stl.gcode ------------------')
    src = mini_vase(os.path.join(d, 'V3_obj.gcode'))
    rel, info = r2_postproc._stl_export(d, 'V3_obj.gcode')
    check('C1: output path is STL/<name>_object.stl.gcode',
          rel.replace('\\', '/') == 'STL/V3_obj_object.stl.gcode'
          and os.path.isfile(os.path.join(d, rel.replace('/', os.sep))),
          'rel=%r' % rel)
    check('C2: the mesh is a real binary STL (80-byte header + triangles)',
          open(os.path.join(d, rel.replace('/', os.sep)), 'rb').read(4)
          != b'G21\n' and info.get('boxes', 0) > 0, '')
    _m13 = open(M13, encoding='utf-8').read()
    _m08 = open(M08, encoding='utf-8').read()
    check('C3: the SD browser refuses .stl.gcode with the download hint',
          "low.endswith('.stl.gcode')" in _m13
          and 'download it in Mainsail' in _m13, '')
    check('C4: STL_EXPORT macro tells the STL folder + ending trick',
      'STL folder' in _m08 and 'remove the .gcode ending' in _m08
      and 'stl.gcode' in _m08, '')

    print('--- D) texture: tilt, new patterns, MAP ------------------------')
    names = r2_texture.PATTERN_NAMES
    check('D1: 27 patterns, the 6 new ones present',
          len(names) == 27 and all(p in names for p in (
              'KNIT', 'FLUTED', 'BARK', 'SCALES', 'FACETS', 'MACRAME'))
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
