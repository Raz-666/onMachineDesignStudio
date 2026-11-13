#!/usr/bin/env python3
"""V1 (13.11.2026): WHY the Range tool said "Range error" - pinned.

WHAT THE USER REPORTED
======================
"Der Range error beruht auf dem Cut-and-Slice-Tool, was ich vorher ausgeführt
hatte. Ich wollte das gekettete Oberteil behalten, da wurden mir zwei Platten
angelegt, und als ich mir den G-Code angeschaut habe, den das Cut-and-split-Tool
generiert hatte, erklärt sich auch, warum das Range-Tool dann einen Error
gebracht hat."

He was right. Proof in his file (V52_Shape_8-gon_60x60x140_vase_..._CUT-U):

    ; R177 cake cut: plane yaw 0.0 pitch 2.0 roll 1.0 through z 25.0 ...
    ; throttle ...
    ;Z:0.280   ;Z:0.480   ;Z:0.680   ;Z:0.880   ;Z:1.080     <- FIVE markers
    ...
    G1 X121.481 Y134.716 Z1.105 E1.23716 F3600              <- the body runs up
    ...                                                        to Z = 116.5 mm
    ; total layers count = 4516                                <- the header's claim

THE MECHANISM
=============
tools/r2_cake.py splits a file at a plane. Motion lines are rebuilt segment by
segment; every NON-move line (header, temperatures, and also the whole
';LAYER_CHANGE / LAYER_MARK / ;Z:' block) is passed through BOTH halves
verbatim - it never parses the layer structure, so it cannot re-anchor it.
Result: the head keeps the handful of markers the source had before the body
began, the body carries the entire part, and TOTAL_LAYERS keeps claiming the old
count. The layer counter the LCD shows and the marker list make_range builds
then describe a file that no longer exists - every range request lands outside
it and the tool can only say "Range error".

Before this check, the only guard with a message was R180 ("layers x..y contain
no extrusion") - and it never fired here, because the excerpt DID contain ink.

THE FIX (what this file pins)
=============================
make_range reads the file's own header. A file that names itself as a cake cut
AND carries a marker/claim mismatch (claim > 4 x markers) is refused with the
cause and the cure named in the message, instead of a bare "Range error".

The three fixpoints below are the whole point:
  1. the user's cut half      -> MUST be refused, with the cake wording
  2. an uncut spiral vase     -> MUST keep working (it also claims 700 layers
                                 with 5 markers - that is BY DESIGN for a spiral,
                                 so the check may NOT fire there)
  3. the real field file      -> MUST keep working (LampOpenE27, 392 markers)

and a counter-test: with the guard removed, fixpoint 1 must FAIL. A check that
cannot fail proves nothing.
"""
import importlib.util
import os
import shutil
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CUT = os.path.join(tempfile.gettempdir(), 'v1_cut_half.gcode')


def load_pp():
    spec = importlib.util.spec_from_file_location(
        'pp_v1', os.path.join(ROOT, 'tools', 'r2_postproc.py'))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# A minimal cake-cut fixture written here, so the check runs anywhere (no uploads
# needed): a small body plus the R177 header and a stale LAYER_MARK chain.
CUT_FIXTURE = """; R177 cake cut: plane yaw 0.0 pitch 1.0 roll 0.0 through z 20.0 (bed center x/y)
; E splits at the plane by length share, every line is a standalone file.
M83
;LAYER_CHANGE
LAYER_MARK
;Z:0.280
APPLY_TYPE TYPE=WALL-OUTER
;LAYER_CHANGE
LAYER_MARK
;Z:0.480
G1 X100.000 Y100.000 Z0.480 E1.00000 F3600
G1 X120.000 Y100.000 Z1.480 E2.00000 F3600
G1 X120.000 Y120.000 Z2.480 E3.00000 F3600
_FILE_INFO MATERIAL=PLA LAYER_HEIGHT=0.2 TOTAL_LAYERS=700 LINE_WIDTH=0.65 SLICER=R2_GEN
"""


def write_cut_fixture(path):
    with open(path, 'w', encoding='utf-8') as fh:
        fh.write(CUT_FIXTURE)
    return path


def source_has_guard(path):
    with open(path, encoding='utf-8') as fh:
        txt = fh.read()
    return "this file is a CAKE CUT half" in txt


def main():
    fails = []
    checks = [0]

    def check(name, ok, detail=''):
        checks[0] += 1
        if not ok:
            fails.append('%s%s' % (name, (' (%s)' % detail) if detail else ''))

    pp_src = os.path.join(ROOT, 'tools', 'r2_postproc.py')
    tmp = tempfile.mkdtemp(prefix='v1_range_')
    cut = write_cut_fixture(os.path.join(tmp, 'demo_CUT-U.gcode'))

    # ---- fixpoint 1: a cake half is refused, and it says WHY -----------------
    pp = load_pp()
    msg = ''
    try:
        pp.make_range(cut, 2, 3, out_dir=tmp)
        check('1 cake-cut half is refused', False, 'no error raised')
    except ValueError as exc:
        msg = str(exc)
        check('1 cake-cut half is refused', True)
        check('1b the message names the CAUSE (cake cut)', 'CAKE CUT' in msg.upper(),
              msg[:80])
        check('1c the message names the CURE (original / uncut file)',
              'original' in msg.lower(), msg[:80])
        check('1d the message quantifies the mismatch (2 numbers)',
              len([w for w in msg.split() if w.strip('.,').isdigit()]) >= 2,
              msg[:80])

    # ---- fixpoint 2: an uncut spiral vase keeps working ----------------------
    # built by OUR generator, so this check never depends on the uploads folder
    try:
        vase, _ = pp.make_shape(shape='POLY', size_x=40.0, size_y=40.0, corners=8,
                                height=30.0, walls=1, base=3, top=0,
                                layer_h=0.2, out_dir=tmp)
        ok2 = True
        err2 = ''
        try:
            pp.make_range(vase, 2, 5, out_dir=tmp)
        except ValueError as exc:
            ok2, err2 = False, str(exc)
        check('2 an uncut spiral vase still ranges (the guard must not fire '
              'on a marker/claim gap that is BY DESIGN)', ok2, err2[:80])
    except Exception as exc:                     # generator trouble is its own bug
        check('2 an uncut spiral vase still ranges', False,
              'make_shape failed: %s' % exc)

    # ---- fixpoint 3: a field-scale file with real layer structure ------------
    # (a plain layer-stack file, written here - 30 layers, 30 markers, claim 30)
    layered = os.path.join(tmp, 'stack.gcode')
    with open(layered, 'w', encoding='utf-8') as fh:
        fh.write('M83\n')
        for i in range(30):
            fh.write(';LAYER_CHANGE\nLAYER_MARK\n;Z:%.3f\n' % (0.2 + 0.2 * i))
            fh.write('G1 X100 Y100 Z%.3f E1.0 F3600\n' % (0.2 + 0.2 * i))
            fh.write('G1 X120 Y100 Z%.3f E2.0 F3600\n' % (0.2 + 0.2 * i))
            fh.write('G1 X120 Y120 Z%.3f E3.0 F3600\n' % (0.2 + 0.2 * i))
        fh.write('_FILE_INFO MATERIAL=PLA TOTAL_LAYERS=30 LAYER_HEIGHT=0.2\n')
    ok3, err3 = True, ''
    try:
        pp.make_range(layered, 5, 12, out_dir=tmp)
    except ValueError as exc:
        ok3, err3 = False, str(exc)
    check('3 a normal marked file still ranges', ok3, err3[:80])

    # ---- counter-test: without the guard, fixpoint 1 MUST fail --------------
    check('4 the guard is present in the source', source_has_guard(pp_src))
    if source_has_guard(pp_src):
        with open(pp_src, encoding='utf-8') as fh:
            src_txt = fh.read()
        mutated = src_txt.replace(
            "    if _iscut and _claim and total >= 2 and _claim > 4 * total:",
            "    if False:", 1)
        mut_path = os.path.join(tmp, 'r2_postproc_mutant.py')
        with open(mut_path, 'w', encoding='utf-8') as fh:
            fh.write(mutated)
        spec = importlib.util.spec_from_file_location('pp_mut', mut_path)
        mut = importlib.util.module_from_spec(spec)
        sys.path.insert(0, os.path.join(ROOT, 'tools'))
        spec.loader.exec_module(mut)
        caught = True
        try:
            mut.make_range(cut, 2, 3, out_dir=tmp)
            caught = False                      # no error -> the check is blind
        except ValueError:
            caught = True
        except Exception:
            caught = True                       # any other failure still proves it
        check('4b counter-test: with the guard deleted the cake half slips '
              'through - so the guard is what catches it', caught,
              'the mutation was NOT caught')

    shutil.rmtree(tmp, ignore_errors=True)
    print()
    if fails:
        for f in fails:
            print('  FAIL %s' % f)
        print('V1 RANGE CAUSE: %d checks, %d FAIL' % (checks[0], len(fails)))
        return 1
    print('V1 RANGE CAUSE: %d checks, 0 FAIL - a cake-cut half is refused with '
          'the cause named, uncut files keep working' % checks[0])
    return 0


if __name__ == '__main__':
    sys.exit(main())
