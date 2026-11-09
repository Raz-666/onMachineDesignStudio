#!/usr/bin/env python3
# R237 (.136ah) field check - the two field reports of the round:
#
#  1) 'Texture tool cannot load images as MAP' - THREE breaks worked
#     together: a ROOT image (the Mainsail drag+drop standard) never set
#     the pick (13_system only talked), the watcher copy would have died
#     on SameFileError for root picks, and texture_map is a RELATIVE name
#     that the texture script resolved against the SOURCE file's folder
#     (broken for sources from Texture/, Labels/ ...).
#  2) 'Unknown command:"_M204"' twice per print - the field log proves
#     the calls fire FROM THE FILE (virtual SD, start block right after
#     PRINT_START's post-heat settings). No sender exists in the package
#     or the user's configs - the lines ride in from the slicer profile's
#     start G-code. The tools rewrite them while processing; the _M204
#     macro alias is the runtime safety net.
import os
import re
import shutil
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import r2_texture                                    # noqa: E402
import r2_postproc                                   # noqa: E402

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


# a small two-layer wall file with the legacy lines from the field log
def _write_case(path, extra_start=''):
    with open(path, 'w') as f:
        f.write('PRINT_START BED=60 HOTEND_FIRST=225 MATERIAL=PLA\n')
        f.write('_M204 S4800\n')
        f.write('_M204_SET VALUE=8000\n')
        f.write(extra_start)
        f.write(';LAYER_CHANGE\n;Z:0.20\n;TYPE:Outer wall\n')
        f.write('G1 X100 Y100 Z0.20 E0.5 F2400\nG1 X110 Y100 Z0.21 E0.9\n')
        f.write('G1 X110 Y110 Z0.22 E1.3\nG1 X100 Y110 Z0.23 E1.7\n')
        f.write(';LAYER_CHANGE\n;Z:0.40\n;TYPE:Outer wall\n')
        f.write('G1 X100 Y100 Z0.40 E2.1\nG1 X110 Y100 Z0.41 E2.5\n')
        f.write('G1 X110 Y110 Z0.42 E2.9\n_M204 S8000\nG1 X100 Y110 Z0.43 E3.3\n')


print('--- A) legacy _M204 lines are rewritten while processing --------')
tmpd = tempfile.mkdtemp(prefix='r237_')
try:
    src = os.path.join(tmpd, 'V5_box.gcode')
    _write_case(src)
    out, info = r2_texture.apply_texture(
        src, out_dir=tmpd, mode='BUMPS', bump_pattern='GRID',
        bump_scale=10.0, bump_amp=0.3)
    txt = open(out).read()
    _bare = re.compile(r'^\s*_M204(\s|$)', re.M)
    check('A1: texture rewrites the 2 legacy _M204 lines to M204',
          info.get('m204_scrub') == 2 and not _bare.search(txt)
          and 'M204 S4800' in txt and 'M204 S8000' in txt,
          'scrub=%r' % info.get('m204_scrub'))
    check('A2: _M204_SET stays untouched (the regex knows the boundary)',
          '_M204_SET VALUE=8000' in txt, '')
    seg = os.path.join(tmpd, 'V5_seg.gcode')
    _write_case(seg)
    n, rb, ra, m2 = r2_postproc._segments_fix_file(seg)
    stxt = open(seg).read()
    check('A3: segment fix renames them too (4-tuple return, count 2)',
          m2 == 2 and not _bare.search(stxt) and 'M204 S4800' in stxt,
          'm2=%r n=%r' % (m2, n))
    check('A4: segment fix keeps _M204_SET and still merges nothing here',
          '_M204_SET VALUE=8000' in stxt and n == 0, 'n=%r' % n)

    print('--- B) MAP image loading ----------------------------------------')
    from PIL import Image
    root = os.path.join(tmpd, 'gcodes')
    sub = os.path.join(root, 'Texture')
    os.makedirs(sub)
    img = Image.new('L', (48, 24))
    px = img.load()
    for y in range(24):
        for x in range(48):
            px[x, y] = (x * 5 + y * 3) % 256
    img.save(os.path.join(root, 'foto.png'))
    img.save(os.path.join(sub, 'near.png'))
    src2 = os.path.join(sub, 'V6_obj.gcode')
    _write_case(src2)
    outd = os.path.join(tmpd, 'out')
    os.makedirs(outd, exist_ok=True)
    o1, i1 = r2_texture.apply_texture(
        src2, out_dir=outd, mode='BUMPS', bump_pattern='MAP',
        bump_scale=10.0, bump_amp=0.3,
        map_file=os.path.join(root, 'foto.png'))
    check('B1: MAP loads with an ABSOLUTE path (what the watcher passes '
          'since R237 - source from Texture/, image in the root)',
          os.path.isfile(o1) and i1.get('m204_scrub') == 2
          and i1.get('shifted', 0) > 0,
          'shifted=%r' % i1.get('shifted'))
    o2, i2 = r2_texture.apply_texture(
        src2, out_dir=outd, mode='BUMPS', bump_pattern='MAP',
        bump_scale=10.0, bump_amp=0.3, map_file='near.png')
    check('B2: MAP loads with a RELATIVE name next to the source',
          os.path.isfile(o2) and i2.get('shifted', 0) > 0, '')
    try:
        r2_texture.apply_texture(
            src2, out_dir=outd, mode='BUMPS', bump_pattern='MAP',
            bump_scale=10.0, bump_amp=0.3, map_file='wo.png')
        check('B3: a missing map raises with every tried path', False,
              'no ValueError')
    except ValueError as e:
        check('B3: a missing map raises with every tried path',
              'tried' in str(e) and 'wo.png' in str(e)
              and os.path.join('Texture', 'wo.png') in str(e), str(e)[:120])
    check('B4: the watcher resolves the map name absolutely '
          '(subfolder pick first, then the root copy)',
          '_mapc91' in open(os.path.join(
              os.path.dirname(os.path.abspath(__file__)),
              'r2_postproc.py')).read()
          and 'map_file=(_map91 or None)' in open(os.path.join(
              os.path.dirname(os.path.abspath(__file__)),
              'r2_postproc.py')).read(), '')

    print('--- C) the menu + runtime safety net ----------------------------')
    here = os.path.dirname(os.path.abspath(__file__))
    _13 = open(os.path.join(here, '..', 'macros', '13_system.cfg'),
               encoding='utf-8').read()
    _06 = open(os.path.join(here, '..', 'macros', '06_temp_controls.cfg'),
               encoding='utf-8').read()
    _17 = open(os.path.join(here, '..', 'macros', '17_generator.cfg'),
               encoding='utf-8').read()
    _pp = open(os.path.join(here, 'r2_postproc.py'), encoding='utf-8').read()
    _tx = open(os.path.join(here, 'r2_texture.py'), encoding='utf-8').read()
    check('C1: SD browser root click PICKS (save before the path branch)',
          _13.count('VARIABLE=img_pick_file VALUE=') == 1
          and _13.find('VARIABLE=img_pick_file')
          < _13.find("{% if path == '' %}")
          and 'picked - ready for Texture MAP' in _13
          and _13.count('SDCARD_PRINT_FILE FILENAME="{ fn }"') == 1, '')
    check('C2: _M204 alias forwards rawparams into the interceptor',
          '[gcode_macro _M204]' in _06 and 'M204 {rawparams}' in _06, '')
    check('C3: TEXTURE_APPLY fails early on MAP without any image',
          "pat == 'MAP' and params.MAP is not defined" in _17
          and 'MAP needs an image' in _17, '')
    check('C4: watcher never self-copies a root pick (SameFileError guard)',
          '_isrc174 == _idst174' in _pp and 'already at root' in _pp, '')
    check('C5: scrub + reporting wired through postproc and texture',
          '_m204_r237' in _pp and 'm204_seen' in _pp
          and 'legacy _M204 renamed' in _pp
          and '_M204_SCRUB' in _tx and '_cands237' in _tx
          and "'m204_scrub'" in _tx, '')
    check('C6: no double-brace boot blocker slipped into the edited cfgs',
          '{{' not in _13 and '{{' not in _06 and '{{' not in _17, '')
finally:
    shutil.rmtree(tmpd, ignore_errors=True)

print('\n%d checks, %d failed' % (ok + fails, fails))
raise SystemExit(1 if fails else 0)
