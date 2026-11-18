#!/usr/bin/env python3
"""Tests for tools/gcode_re.py - Masterkonzept unified Pass 0-11 analysis.

Synthetic, self-contained G-code fixtures only. Mode declarations (G90/M82)
and G92 E0 are re-declared after any homing exactly like real slicer output,
because the verified shadow parser intentionally fail-closes on G28. No
printer, no hardware, no slicer output is required. Every assertion checks an
honesty property of the engine: UNKNOWN stays UNKNOWN, scores ship with
evidence, the source file is never modified, the sidecar is atomic.
"""
import hashlib
import json
import os
from pathlib import Path
import shutil
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import gcode_re  # noqa: E402

TMP = Path(tempfile.mkdtemp(prefix='gcode-re-'))


def write(name, text):
    p = TMP / name
    p.write_text(text, encoding='utf-8')
    return p


def run_analyse(path, **kw):
    args = dict(join_eps=gcode_re.JOIN_EPS_DEFAULT)
    args.update(kw)
    return gcode_re.analyse(str(path), **args)


HEADER = """G21
G90
M82
G92 E0
"""

SIMPLE_SQUARE = HEADER + """G0 Z0.2 F3000
G1 X10 Y10 F1800
G1 X50 Y10 E1.6 F1800
G1 X50 Y50 E3.2
G1 X10 Y50 E4.8
G1 X10 Y10 E6.4
G0 Z5.0 F600
"""

NESTED_SQUARES = HEADER + """G0 Z0.2 F3000
G1 X10 Y10 F1800
G1 X50 Y10 E1.6 F1800
G1 X50 Y50 E3.2
G1 X10 Y50 E4.8
G1 X10 Y10 E6.4
G1 X20 Y20 E6.8 F1800
G1 X40 Y20 E7.6 F1800
G1 X40 Y40 E8.4
G1 X20 Y40 E9.2
G1 X20 Y20 E10.0
"""

HATCH_FILE = HEADER + """G0 Z0.2 F3000
G1 X10 Y10 F1800
G1 X70 Y10 E2.4 F1800
G1 X70 Y12
G1 X10 Y12 E4.8 F1800
G1 X10 Y14
G1 X70 Y14 E7.2 F1800
G1 X70 Y16
G1 X10 Y16 E9.6 F1800
G1 X10 Y18
G1 X70 Y18 E12.0 F1800
G1 X70 Y20
G1 X10 Y20 E14.4 F1800
G1 X10 Y22
G1 X70 Y22 E16.8 F1800
"""

NO_EVIDENCE = HEADER + """G0 X10 Y10 F3000
G0 X20 Y10 F3000
"""

G28_THEN_PRINT = """G21
G90
M82
G28
G21
G90
M82
G92 E0
G0 Z0.2 F3000
G1 X10 Y10 F1800
G1 X50 Y10 E1.6 F1800
G1 X50 Y50 E3.2
G1 X10 Y50 E4.8
G1 X10 Y10 E6.4
"""

EMPTY_NONSENSE = "XYZZY NOT GCODE\n"


def test_square_loop_detected_and_scored():
    p = write('square.gcode', SIMPLE_SQUARE)
    out = run_analyse(p)
    assert out['schema'] == 'r2-re/2'
    assert out['audit']['lines_accounted_for'] is True
    assert out['plane_totals']['closed_loops'] >= 1
    plane = out['z_planes'][0]
    assert plane['outer_loops_depth0'] >= 1
    sq = [lp for lp in plane['loops'] if lp['nesting_depth'] == 0][0]
    assert sq['area_mm2'] > 1000  # 40x40 mm square
    feats = out['feature_planes'][0]
    assert feats['verdict'] != 'UNKNOWN'
    assert feats['top3'], 'scored plane must ship hypotheses'
    assert all('feature' in t and 'score' in t for t in feats['top3'])
    assert feats['calibrated_probability'] is None


def test_nested_loops_containment_depth():
    p = write('nested.gcode', NESTED_SQUARES)
    out = run_analyse(p)
    plane = out['z_planes'][0]
    depths = sorted(lp['nesting_depth'] for lp in plane['loops'])
    assert depths.count(0) == 1, f'expected exactly one depth-0 loop, got {depths}'
    assert depths.count(1) == 1, f'expected exactly one nested loop, got {depths}'
    inner = [lp for lp in plane['loops'] if lp['nesting_depth'] == 1][0]
    assert inner['area_mm2'] < 500


def test_hatch_statistics():
    p = write('hatch.gcode', HATCH_FILE)
    out = run_analyse(p)
    plane = out['z_planes'][0]
    assert plane['hatch']['verdict'] in ('RECTILINEAR_LIKE', 'GRID_LIKE')
    assert plane['hatch']['dominant_share'] >= 0.7
    assert plane['hatch']['spacing_mm'] is not None
    assert 1.5 < plane['hatch']['spacing_mm'] < 2.5  # strokes 2 mm apart


def test_no_evidence_stays_unknown():
    p = write('travels.gcode', NO_EVIDENCE)
    out = run_analyse(p)
    for fp in out['feature_planes']:
        assert fp['verdict'] == 'UNKNOWN'
        assert fp['top3'] == []


def test_g28_invalidates_then_modes_restore():
    p = write('homing.gcode', G28_THEN_PRINT)
    out = run_analyse(p)
    assert out['audit']['lines_accounted_for'] is True
    assert out['plane_totals']['closed_loops'] >= 1


def test_unknown_command_invalidates_but_does_not_crash():
    p = write('nonsense.gcode', EMPTY_NONSENSE)
    out = run_analyse(p)
    assert out['record_counts'].get('unknown', 0) >= 1
    assert out['audit']['lines_accounted_for'] is True


def test_source_hash_and_readability():
    p = write('hashcheck.gcode', SIMPLE_SQUARE)
    before = hashlib.sha256(p.read_bytes()).hexdigest()
    out = run_analyse(p)
    after = hashlib.sha256(p.read_bytes()).hexdigest()
    assert before == after == out['provenance']['input_sha256']


def test_sidecar_atomic_and_no_overwrite():
    p = write('sidecar.gcode', SIMPLE_SQUARE)
    out_path = TMP / 'out.json'
    rc = gcode_re.main([str(p), '--out', str(out_path), '--quiet'])
    assert rc == 0 and out_path.exists()
    rc = gcode_re.main([str(p), '--out', str(out_path), '--quiet'])
    assert rc == 2, 'existing sidecar must be refused without --force'
    rc = gcode_re.main([str(p), '--out', str(out_path), '--quiet', '--force'])
    assert rc == 0
    data = json.loads(out_path.read_text())
    assert data['schema'] == 'r2-re/2'
    assert data['tool']['version'] == gcode_re.TOOL_VERSION


def test_sidecar_suffix_enforced():
    p = write('suffix.gcode', SIMPLE_SQUARE)
    rc = gcode_re.main([str(p), '--out', str(TMP / 'out.gcode'), '--quiet'])
    assert rc == 1


def test_moves_only_with_flag_and_capped():
    p = write('moves.gcode', SIMPLE_SQUARE)
    out = run_analyse(p)
    assert 'moves' not in out
    out = run_analyse(p, with_moves=True, max_moves=2)
    assert len(out['moves']) == 2
    assert out['moves_meta']['truncated'] is True


def main():
    tests = [v for k, v in sorted(globals().items()) if k.startswith('test_')]
    failed = 0
    for fn in tests:
        try:
            fn()
            print(f'PASS {fn.__name__}')
        except AssertionError as exc:
            failed += 1
            print(f'FAIL {fn.__name__}: {exc}')
    shutil.rmtree(TMP, ignore_errors=True)
    print(f'{len(tests) - failed}/{len(tests)} gcode_re tests passed')
    return 1 if failed else 0


if __name__ == '__main__':
    sys.exit(main())
