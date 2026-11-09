#!/usr/bin/env python3
# R239 (.136ai) field check - the 'print will not start' round:
#
#  Field log klippy-3h (2).txt: 5x
#  'Malformed command EXCLUDE_OBJECT_DEFINE ... POLYGON=[[137.343,111.466],
#  [137.320,110.984], ...]' - spaced point separators. Klipper's shlex
#  splits the value at whitespace -> the token stream carries '='-less
#  fragments -> Malformed -> klippy error state -> every start of such a
#  file died ('Druck laesst sich nicht starten'). ORIGIN: the MIRROR tool
#  re-emits the polygon with ', '.join (R224) - the user's suspicion was
#  right; the texture files inherited the line verbatim, the selection
#  replay pushed it again on every click.
#  Plus: the segment fix left the spiral-vase chord flood at 18 000
#  moves/s (it merged 113 of half a million moves - Z-carrying G1s were
#  invisible to the old regex and the 0.35mm total cap blocked the rest).
import math
import os
import re
import shlex
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


def _has_fragment_tokens(line):
    """klipper's _get_extended_params: posix shlex, whitespace_split -
    a token without '=' (what a spaced POLYGON produces) is malformed."""
    try:
        toks = shlex.split(line, posix=True)
    except ValueError:
        return True
    return any('=' not in t for t in toks[1:])


HERE = os.path.dirname(os.path.abspath(__file__))
PP = os.path.join(HERE, 'r2_postproc.py')
TX = os.path.join(HERE, 'r2_texture.py')

SPACED = ('EXCLUDE_OBJECT_DEFINE NAME=rose_id_0 CENTER=100.0,100.0 '
          'POLYGON=[[110.0,90.0], [110.0,110.0], [90.0,110.0], '
          '[90.0,90.0], [110.0,90.0]]')
COMPACT = SPACED.replace('], [', '],[')

d = tempfile.mkdtemp(prefix='r239_')
try:
    print('--- A) the spaced polygon is unparseable - every writer heals --')
    check('A1: the SPACED line produces =-less tokens (klipper: Malformed)',
          _has_fragment_tokens(SPACED), '')
    check('A2: the COMPACT line parses clean (no fragment tokens)',
          not _has_fragment_tokens(COMPACT), '')
    check('A3: _eod_compact heals the line',
          r2_postproc._eod_compact(SPACED) == COMPACT,
          r2_postproc._eod_compact(SPACED)[:80])

    # mirror E2E: the emitter writes a compact polygon
    src = os.path.join(d, 'V1_obj.gcode')
    with open(src, 'w') as f:
        f.write('G21\nG90\nM83\n')
        f.write(COMPACT + '\n')
        f.write(';LAYER_CHANGE\n;Z:0.20\n;TYPE:Outer wall\n')
        for i in range(40):
            a = 2 * math.pi * i / 40
            f.write('G1 X%.3f Y%.3f Z0.20 E%.4f F2400\n'
                    % (110 + 20 * math.cos(a), 110 + 20 * math.sin(a), 0.01))
    out_m, info_m = r2_postproc.apply_mirror(src, axis='x', out_dir=d)
    mtxt = open(out_m).read()
    check('A4: apply_mirror emits a COMPACT polygon (the R239 emitter fix)',
          'POLYGON=[' in mtxt and '], [' not in mtxt, '')

    # segment fix heals a spaced file in place
    seg = os.path.join(d, 'V2_seg.gcode')
    with open(seg, 'w') as f:
        f.write('G21\nG90\nM83\n')
        f.write(SPACED + '\n')
        f.write('G1 F3000\n')
        x = 0.0
        for _ in range(300):
            x += 0.02
            f.write('G1 X%.3f Y50.000 E0.001\n' % x)
    n, rb, ra, m2 = r2_postproc._segments_fix_file(seg)
    stxt = open(seg).read()
    check('A5: segment fix heals the spaced polygon while rewriting',
          '], [' not in stxt and '],[' in stxt, '')

    # texture heals it too
    tex = os.path.join(d, 'V3_tex.gcode')
    with open(tex, 'w') as f:
        f.write('G21\nG90\nM83\n')
        f.write(SPACED + '\n')
        f.write(';LAYER_CHANGE\n;Z:0.20\n;TYPE:Outer wall\n')
        for i in range(40):
            a = 2 * math.pi * i / 40
            f.write('G1 X%.3f Y%.3f Z0.20 E%.4f F2400\n'
                    % (110 + 20 * math.cos(a), 110 + 20 * math.sin(a), 0.01))
    out_t, info_t = r2_texture.apply_texture(
        tex, out_dir=d, mode='BUMPS', bump_pattern='GRID',
        bump_scale=10.0, bump_amp=0.3, zsize=10.0)
    ttxt = open(out_t).read()
    check('A6: texture heals the spaced polygon while streaming',
          '], [' not in ttxt and '],[' in ttxt, '')

    # the selection replay heals it (no more Malformed on every click)
    spaced_file = os.path.join(d, 'V4_pick.gcode')
    with open(spaced_file, 'w') as f:
        f.write(SPACED + '\nG21\n')
    defs = r2_postproc._peek_objects(spaced_file)
    check('A7: _peek_objects replays the healed form (selection push)',
          len(defs) == 1 and '], [' not in defs[0], str(defs)[:80])

    print('--- B) the spiral-vase chord flood finally heals --------------')
    spiral = os.path.join(d, 'V5_spiral.gcode')
    with open(spiral, 'w') as f:
        f.write('G21\nG90\nM83\nG1 F9000\n')
        # a smooth arc as micro chords WITH Z per move (the field rose
        # class: ~0.03mm per chord, 18 000 moves/s in the log)
        for L in range(2):
            for i in range(2500):
                a = 2 * math.pi * i / 2500
                z = 0.2 + 0.0006 * (L * 2500 + i)
                f.write('G1 X%.3f Y%.3f Z%.4f E%.5f\n'
                        % (110 + 25 * math.cos(a), 110 + 25 * math.sin(a),
                           z, 0.001))
    rb = r2_postproc._worst_move_rate(spiral)
    n, rb2, ra, m2 = r2_postproc._segments_fix_file(spiral)
    stxt = open(spiral).read()
    zvals = [float(m.group(1)) for m in re.finditer(r' Z([\d.]+)', stxt)]
    esum = sum(float(m.group(1)) for m in re.finditer(r' E([\d.]+)', stxt))
    check('B1: the spiral bomb measures >400/s and heals under 400',
          rb > 400 and ra < 400, 'rate %.0f -> %.0f (merged %d)'
          % (rb, ra, n))
    check('B2: Z survives the merge (last-Z wins, monotone end value)',
          bool(zvals) and abs(max(zvals) - (0.2 + 0.0006 * 4999)) < 0.01, '')
    check('B3: E is preserved (5000 x 0.001)',
          abs(esum - 5.0) < 0.03, 'E=%.4f' % esum)

    print('--- C) the deviation bound keeps the geometry honest -----------')
    wand = os.path.join(d, 'V6_wander.gcode')
    with open(wand, 'w') as f:
        f.write('G21\nG90\nM83\nG1 F1200\n')
        # hops < 0.1mm each, but the path WANDERS 6mm away from any chord
        for i in range(120):
            y = 50.0 + 6.0 * math.sin(i * 0.12)
            f.write('G1 X%.3f Y%.3f E0.001\n' % (50.0 + i * 0.08, y))
    n, rb, ra, m2 = r2_postproc._segments_fix_file(wand)
    wlines = [l for l in open(wand) if l.startswith('G1 X')]
    check('C1: a wandering micro path is NOT collapsed into few chords',
          len(wlines) > 60, 'lines left: %d' % len(wlines))

    print('--- D) chain cap + compatibility --------------------------------')
    longline = os.path.join(d, 'V7_straight.gcode')
    with open(longline, 'w') as f:
        f.write('G21\nG90\nM83\nG1 F3000\n')
        x = 0.0
        for _ in range(1000):
            x += 0.02
            f.write('G1 X%.3f Y50.000 E0.001\n' % x)
    n, rb, ra, m2 = r2_postproc._segments_fix_file(longline)
    llines = [l for l in open(longline) if l.startswith('G1 X')]
    check('D1: a straight flood merges to ~1/128 of its moves (cap)',
          n >= 990 and len(llines) <= 12,
          'merged=%d lines=%d' % (n, len(llines)))
    bomb = os.path.join(d, 'V8_bomb.gcode')
    with open(bomb, 'w') as f:
        f.write('G21\nG90\nM83\nG1 F3000\n')
        x = 0.0
        for _ in range(400):
            x += 0.02
            f.write('G1 X%.3f Y50.000 E0.001\n' % x)
    n, rb, ra, m2 = r2_postproc._segments_fix_file(bomb)
    esum = sum(float(m.group(1)) for m in
               re.finditer(r' E([\d.]+)', open(bomb).read()))
    check('D2: the r142 class bomb still heals (n>=250, rate<400, E intact)',
          n >= 250 and ra < 400 and abs(esum - 0.4) < 0.005,
          'n=%d ra=%.0f E=%.4f' % (n, ra, esum))
    _pp = open(PP, encoding='utf-8').read()
    _tx = open(TX, encoding='utf-8').read()
    check('D3: emitter pins - mirror joins compact, Z-group in the merge '
          'regex, texture scrubs',
          "new_pts = ','.join(" in _pp
          and '(?: Z(?P<Z>' in _pp
          and "startswith('EXCLUDE_OBJECT_DEFINE')" in _tx, '')
finally:
    shutil.rmtree(d, ignore_errors=True)

print('\n%d checks, %d failed' % (ok + fails, fails))
raise SystemExit(1 if fails else 0)
