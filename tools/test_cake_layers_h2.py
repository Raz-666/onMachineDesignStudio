#!/usr/bin/env python3
"""H2 regressions: tools/r2_cake.py layer preservation, sloped-move splitting,
feedrate/retract fidelity, atomic output, and direct make_range chaining.
"""
import math
import os
from pathlib import Path
import re
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))

import r2_cake  # noqa: E402
import r2_postproc as pp  # noqa: E402


def _layer_blocks(path):
    """Return list of (z_comment, n_pos_e_moves, z_moves) per LAYER_MARK."""
    lines = Path(path).read_text(encoding='utf-8').splitlines()
    marks = [i for i, l in enumerate(lines) if l.strip() == 'LAYER_MARK']
    e_rel = False
    last_e = 0.0
    cur_idx = -1
    blocks = []
    for i, ln in enumerate(lines):
        ls = ln.strip()
        code = ls.split(';', 1)[0].strip()
        if code == 'M83':
            e_rel = True
            continue
        if code == 'M82':
            e_rel = False
            continue
        if code.startswith('G92'):
            me = re.search(r'E([+-]?[\d.]+)', code)
            if me:
                last_e = float(me.group(1))
            continue
        if ls == 'LAYER_MARK':
            z_tag = None
            if i + 1 < len(lines) and lines[i + 1].startswith(';Z:'):
                z_tag = float(lines[i + 1][3:])
            blocks.append([z_tag, 0, []])
            cur_idx = len(blocks) - 1
            continue
        if code.startswith('G1'):
            me = re.search(r'\bE([+-]?[\d.]+)', code)
            mx = re.search(r'\bX([+-]?[\d.]+)', code)
            my = re.search(r'\bY([+-]?[\d.]+)', code)
            mz = re.search(r'\bZ([+-]?[\d.]+)', code)
            if me:
                ev = float(me.group(1))
                de = ev if e_rel else (ev - last_e)
                if not e_rel:
                    last_e = ev
                if de > 0.0002 and (mx or my) and cur_idx >= 0:
                    blocks[cur_idx][1] += 1
                    if mz:
                        blocks[cur_idx][2].append(float(mz.group(1)))
    return blocks


def _net_extrusion(path):
    e_rel = False
    last_e = 0.0
    total = 0.0
    for ln in Path(path).read_text(encoding='utf-8').splitlines():
        code = ln.split(';', 1)[0].strip()
        if code == 'M83':
            e_rel = True
        elif code == 'M82':
            e_rel = False
        elif code.startswith('G92'):
            me = re.search(r'\bE([+-]?[\d.]+)', code)
            if me:
                last_e = float(me.group(1))
        elif code.startswith(('G0', 'G1')):
            me = re.search(r'\bE([+-]?[\d.]+)', code)
            if me:
                ev = float(me.group(1))
                de = ev if e_rel else (ev - last_e)
                if not e_rel:
                    last_e = ev
                total += de
    return total


class CakeLayerPreservationTests(unittest.TestCase):
    def test_horizontal_cut_rebuilds_exact_layers_headers_and_types(self):
        with tempfile.TemporaryDirectory() as d:
            src = os.path.join(d, 'tower.gcode')
            lines = [
                '; R2-POSTPROC v5',
                '_FILE_INFO MATERIAL=PLA LAYER_HEIGHT=0.2 TOTAL_LAYERS=20 '
                'LINE_WIDTH=0.6 TYPES=SURFACE-BOTTOM,WALL-OUTER,SURFACE-TOP SLICER=ORCA',
                'PRINT_START MATERIAL=PLA LAYER_HEIGHT=0.2 TOTAL_LAYERS=20',
                'SET_PRINT_STATS_INFO TOTAL_LAYER=20',
                ';LAYER_COUNT:20',
                'M83 ; use relative distances for extrusion',
                'G90',
                'G92 E0',
            ]
            src_e = 0.0
            for lay in range(20):
                z = round(0.2 + 0.2 * lay, 3)
                feat, canon = (
                    ('Bottom surface', 'SURFACE-BOTTOM') if lay < 2 else
                    ('Top surface', 'SURFACE-TOP') if lay >= 18 else
                    ('Outer wall', 'WALL-OUTER')
                )
                lines += [
                    ';LAYER_CHANGE',
                    'LAYER_MARK',
                    f';Z:{z:.3f}',
                    f';LAYER:{lay}',
                    f'SET_PRINT_STATS_INFO CURRENT_LAYER={lay + 1}',
                    f'G0 X90 Y90 Z{z:.3f} F7200',
                    f';TYPE:{feat}',
                    f'APPLY_TYPE TYPE={canon}',
                ]
                for x, y in ((130, 90), (130, 130), (90, 130), (90, 90)):
                    lines.append(f'G1 X{x} Y{y} E1.25 F1800')
                    src_e += 1.25
            lines += ['PRINT_END', '; total layers count = 20']
            Path(src).write_text('\n'.join(lines) + '\n', encoding='utf-8')

            (up, lo), info = r2_cake.cut_cake(
                src, z_offset=2.0, out_dir=d, bed=(0, 0, 220, 220))
            # z=0.2..1.8 -> 9 lower layers; z=2.0..4.0 -> 11 upper layers (shifted to 0.2..2.2)
            self.assertEqual(info['layers_lower'], 9)
            self.assertEqual(info['layers_upper'], 11)
            ub = _layer_blocks(up)
            lb = _layer_blocks(lo)
            self.assertEqual(len(ub), 11)
            self.assertEqual(len(lb), 9)
            self.assertTrue(all(b[1] > 0 for b in ub), 'empty layer in UPPER')
            self.assertTrue(all(b[1] > 0 for b in lb), 'empty layer in LOWER')
            self.assertAlmostEqual(ub[0][0], 0.2, places=3)
            self.assertAlmostEqual(ub[-1][0], 2.2, places=3)
            self.assertAlmostEqual(lb[0][0], 0.2, places=3)
            self.assertAlmostEqual(lb[-1][0], 1.8, places=3)
            for z_tag, _, z_moves in ub + lb:
                self.assertAlmostEqual(z_tag, z_moves[0], places=3)

            # Metadata headers/footers match actual per-half layer count & features
            utxt = Path(up).read_text(encoding='utf-8')
            ltxt = Path(lo).read_text(encoding='utf-8')
            self.assertIn('TOTAL_LAYERS=11', utxt)
            self.assertIn('TOTAL_LAYER=11', utxt)
            self.assertIn(';LAYER_COUNT:11', utxt)
            self.assertIn('; total layers count = 11', utxt)
            self.assertNotIn('CURRENT_LAYER=', utxt)
            self.assertNotIn(';LAYER:', utxt)
            self.assertIn('TYPES=WALL-OUTER,SURFACE-TOP', utxt)
            self.assertNotIn('TYPE=SURFACE-BOTTOM', utxt)
            self.assertIn('TYPES=SURFACE-BOTTOM,WALL-OUTER', ltxt)
            self.assertNotIn('TYPE=SURFACE-TOP', ltxt)
            self.assertIn('TOTAL_LAYERS=9', ltxt)

            # E volume conserved across M83-with-comment source
            self.assertAlmostEqual(_net_extrusion(up) + _net_extrusion(lo),
                                   src_e, places=3)

            # make_range works directly on BOTH halves with floor/top/brim
            ru, nlu, *_ = pp.make_range(up, 3, 8, floor=1, top=1, brim=1, out_dir=d)
            rl, nll, *_ = pp.make_range(lo, 2, 7, floor=1, top=1, out_dir=d)
            self.assertTrue(os.path.isfile(ru) and nlu == 6)
            self.assertTrue(os.path.isfile(rl) and nll == 6)

            # Atomic cleanup: zero temp files left behind
            leftovers = [f for f in os.listdir(d) if f.startswith('.r2cake_')]
            self.assertEqual(leftovers, [])

    def test_spiral_vase_tilted_cut_supports_make_range_and_exact_z_split(self):
        with tempfile.TemporaryDirectory() as d:
            vase = os.path.join(d, 'vase.gcode')
            lines = [
                '; R2-POSTPROC v5',
                '_FILE_INFO MATERIAL=PLA LAYER_HEIGHT=0.2 TOTAL_LAYERS=60 '
                'LINE_WIDTH=0.6 TYPES=SURFACE-BOTTOM,WALL-OUTER SLICER=R2_GEN',
                'PRINT_START MATERIAL=PLA LAYER_HEIGHT=0.2 TOTAL_LAYERS=60',
                'G90',
                'M83',
            ]
            src_e = 0.0
            for b in range(2):
                z = 0.2 + 0.2 * b
                lines += [
                    ';LAYER_CHANGE', 'LAYER_MARK', f';Z:{z:.3f}',
                    'APPLY_TYPE TYPE=SURFACE-BOTTOM', ';TYPE:Bottom surface',
                    f'G0 X95 Y95 Z{z:.3f} F6000',
                    'G1 X125 Y95 E1.0 F1500', 'G1 X125 Y125 E1.0',
                    'G1 X95 Y125 E1.0', 'G1 X95 Y95 E1.0',
                ]
                src_e += 4.0
            lines += [';LAYER_CHANGE', 'LAYER_MARK', ';Z:0.600',
                      ';TYPE:Outer wall', 'APPLY_TYPE TYPE=WALL-OUTER']
            z = 0.4
            for step in range(58 * 12):
                ang = 2.0 * math.pi * (step % 12) / 12.0
                x = 110.0 + 18.0 * math.cos(ang)
                y = 110.0 + 18.0 * math.sin(ang)
                z += 0.2 / 12.0
                lines.append(f'G1 X{x:.3f} Y{y:.3f} Z{z:.4f} E0.25 F2400')
                src_e += 0.25
            lines += ['PRINT_END', '; total layers count = 60']
            Path(vase).write_text('\n'.join(lines) + '\n', encoding='utf-8')

            (up, lo), info = r2_cake.cut_cake(
                vase, pitch=2.0, roll=1.0, z_offset=6.0, out_dir=d,
                bed=(0, 0, 220, 220))
            self.assertGreaterEqual(info['layers_upper'], 28)
            self.assertGreaterEqual(info['layers_lower'], 28)
            self.assertAlmostEqual(_net_extrusion(up) + _net_extrusion(lo),
                                   src_e, places=2)
            # Active feature WALL-OUTER declared once in LOWER is emitted in UPPER
            utxt = Path(up).read_text(encoding='utf-8')
            self.assertIn('APPLY_TYPE TYPE=WALL-OUTER', utxt)
            self.assertIn('F2400', utxt)
            # Field failure H2: make_range MUST now succeed on both cut halves!
            ru, nlu, *_ = pp.make_range(up, 4, 15, floor=2, top=2, out_dir=d)
            rl, nll, *_ = pp.make_range(lo, 4, 15, floor=2, top=2, out_dir=d)
            self.assertEqual(nlu, 12)
            self.assertEqual(nll, 12)
            self.assertTrue(os.path.isfile(ru) and os.path.isfile(rl))

    def test_sloped_segment_splits_using_z_prev_not_z_end(self):
        with tempfile.TemporaryDirectory() as d:
            # Single vertical-ramp extrusion from z=1.0 to z=9.0 cut at z=3.0:
            # exact split fraction t = (1-3)/(1-9) = 0.25 -> LOWER gets 2.5mm E,
            # UPPER gets 7.5mm E. Old bug (z_start=z1=9.0) put 100% in UPPER!
            src = os.path.join(d, 'ramp.gcode')
            Path(src).write_text(
                'G90\nM83\n'
                'G0 X90 Y110 Z0.2 F6000\n'
                'G1 X100 Y110 Z1.0 E2.0 F1200\n'
                'G1 X140 Y110 Z9.0 E10.0 F1800\n',
                encoding='utf-8',
            )
            (up, lo), _ = r2_cake.cut_cake(
                src, z_offset=3.0, out_dir=d, bed=(0, 0, 220, 220))
            self.assertAlmostEqual(_net_extrusion(lo), 4.5, places=3)
            self.assertAlmostEqual(_net_extrusion(up), 7.5, places=3)
            # Feedrate F1800 preserved on BOTH split halves
            self.assertIn('F1800', Path(up).read_text(encoding='utf-8'))
            self.assertIn('F1800', Path(lo).read_text(encoding='utf-8'))

    def test_tilted_reorient_has_monotonic_layers_and_ranges_cleanly(self):
        with tempfile.TemporaryDirectory() as d:
            src = os.path.join(d, 'tilted.gcode')
            lines = [
                '; R2-POSTPROC v5',
                '_FILE_INFO MATERIAL=PLA LAYER_HEIGHT=0.2 TOTAL_LAYERS=40 '
                'LINE_WIDTH=0.6 TYPES=WALL-OUTER SLICER=ORCA',
                'PRINT_START MATERIAL=PLA LAYER_HEIGHT=0.2 TOTAL_LAYERS=40',
                'G90', 'M82', 'G92 E0',
            ]
            e = 0.0
            for lay in range(40):
                z = 0.2 + 0.2 * lay
                lines += [';LAYER_CHANGE', 'LAYER_MARK', f';Z:{z:.3f}',
                          f'G0 X95 Y95 Z{z:.3f} F6000',
                          ';TYPE:Outer wall', 'APPLY_TYPE TYPE=WALL-OUTER']
                for x, y in ((125, 95), (125, 125), (95, 125), (95, 95)):
                    e += 1.0
                    lines.append(f'G1 X{x} Y{y} E{e:.4f} F2100')
            lines.append('PRINT_END')
            Path(src).write_text('\n'.join(lines) + '\n', encoding='utf-8')

            (up, lo), info = r2_cake.cut_cake(
                src, pitch=12.0, z_offset=4.0, reorient=True, out_dir=d,
                bed=(0, 0, 220, 220))
            self.assertTrue(os.path.basename(up).startswith('tilted_CUT-U'))
            self.assertTrue(os.path.basename(lo).startswith('tilted_CUT-L'))
            self.assertNotEqual(up, lo)
            # Reorientation is upper-only: LOWER keeps source coordinates;
            # this original first-wall move remains verbatim in its output.
            self.assertIn('G1 X125.000 Y95.000 Z0.200 E1.00000 F2100',
                          Path(lo).read_text(encoding='utf-8'))
            self.assertIn('The cut face was rotated flat onto the bed',
                          Path(up).read_text(encoding='utf-8'))
            self.assertIn('Keeps its original place (it already stands)',
                          Path(lo).read_text(encoding='utf-8'))
            ub = _layer_blocks(up)
            z_tags = [b[0] for b in ub]
            self.assertEqual(len(ub), info['layers_upper'])
            self.assertGreaterEqual(len(ub), 15)
            # Strictly ascending layer Z markers from bed up (cut face at z=0.2), zero empty layers
            self.assertTrue(all(b > a for a, b in zip(z_tags, z_tags[1:])),
                            f'non-ascending layer markers: {z_tags}')
            self.assertLess(z_tags[0], 0.5, f'reorient started in mid-air: {z_tags[0]}')
            self.assertTrue(all(b[1] > 0 for b in ub))
            ru, nlu, *_ = pp.make_range(up, 3, 10, out_dir=d)
            rl, nll, *_ = pp.make_range(lo, 3, 10, out_dir=d)
            self.assertEqual(nlu, 8)
            self.assertEqual(nll, 8)
            self.assertTrue(os.path.isfile(ru) and os.path.isfile(rl))

    def test_m82_retracts_and_g91_g92_helical_arcs_conserve_extrusion(self):
        with tempfile.TemporaryDirectory() as d:
            # M82 with retracts both within a side and across the cutting plane
            src = os.path.join(d, 'ret_m82.gcode')
            Path(src).write_text(
                'M82 ; absolute E\n'
                'G90 ; absolute XYZ\n'
                'G92 E0\n'
                'G0 X90 Y90 Z0.2 F6000\n'
                'G1 X120 Y90 E2.0 F1500\n'
                'G1 E1.2 F2400 ; retract in LOWER\n'
                'G0 X90 Y110 Z0.2 F6000\n'
                'G1 E2.0 F2400 ; unretract in LOWER\n'
                'G1 X120 Y110 E4.0 F1500\n'
                'G1 E3.2 F2400 ; retract in LOWER before crossing to UPPER\n'
                'G0 X90 Y90 Z2.0 F6000\n'
                'G1 E4.0 F2400 ; unretract in UPPER (must NOT overextrude)\n'
                'G1 X120 Y90 E6.0 F1500\n'
                'G0 X90 Y120 Z0.4 F6000 ; return to LOWER -> auto-recovers 0.8\n'
                'G1 X120 Y120 E8.0 F1500\n'
                'G91 ; relative block\n'
                'G1 X0 Y10 Z0 E1.0 F1200\n'
                'G90\n'
                'G0 X90 Y110 Z2.2 F6000\n'
                'G2 X90 Y110 I20 E11.5 F1800 ; full circle arc with omitted J\n',
                encoding='utf-8',
            )
            (up, lo), _ = r2_cake.cut_cake(
                src, z_offset=1.0, out_dir=d, bed=(0, 0, 220, 220))
            # True extruded plastic: 2 + 2 + 2 + 2 + 1 + 2.5 = 11.5 mm
            self.assertAlmostEqual(_net_extrusion(lo), 7.0, places=3)
            self.assertAlmostEqual(_net_extrusion(up), 4.5, places=3)
            # Output never leaks G91 into an absolute coordinate stream
            for p in (up, lo):
                codes = [ln.split(';', 1)[0].strip()
                         for ln in Path(p).read_text(encoding='utf-8').splitlines()]
                self.assertNotIn('G91', codes)

    def test_sequential_objects_and_legacy_broken_cut_guard(self):
        with tempfile.TemporaryDirectory() as d:
            # Sequential two-object file cut at z=1.0: both objects keep layers
            seq = os.path.join(d, 'seq.gcode')
            lines = ['G90', 'M83']
            for obj_x in (70, 150):
                for k in range(8):
                    z = round(0.2 + 0.2 * k, 3)
                    lines += [f'G0 X{obj_x} Y100 Z{z:.3f} F6000',
                              f'G1 X{obj_x + 20} Y100 E1.0 F1800']
            Path(seq).write_text('\n'.join(lines) + '\n', encoding='utf-8')
            (up, lo), info = r2_cake.cut_cake(
                seq, z_offset=1.0, out_dir=d, bed=(0, 0, 220, 220))
            # Each object has 4 lower layers (0.2..0.8) and 4 upper layers (1.0..1.6)
            self.assertEqual(info['layers_lower'], 8)
            self.assertEqual(info['layers_upper'], 8)

            # Legacy pre-H2 broken cake half MUST still be refused by make_range
            legacy = os.path.join(d, 'old_CUT-U.gcode')
            Path(legacy).write_text(
                '; R177 cake cut: plane yaw 0.0 pitch 2.0 roll 1.0 through z 5.0\n'
                '_FILE_INFO MATERIAL=PLA LAYER_HEIGHT=0.2 TOTAL_LAYERS=120 '
                'TYPES=WALL-OUTER SLICER=R2_GEN\n'
                'G90\nM83\n'
                ';LAYER_CHANGE\nLAYER_MARK\n;Z:0.200\n'
                'G1 X10 Y10 Z0.2 E1.0 F1800\n'
                ';LAYER_CHANGE\nLAYER_MARK\n;Z:0.400\n'
                'G1 X20 Y10 Z10.0 E1.0 F1800\n',
                encoding='utf-8',
            )
            with self.assertRaisesRegex(ValueError, 'CAKE CUT'):
                pp.make_range(legacy, 2, 10, out_dir=d)

    def test_counter_mutations_catch_sloped_z_and_missing_layer_marks(self):
        """Prove the H2 tests fail if sloped Z or per-half layer rebuild breaks."""
        src_code = (ROOT / 'tools' / 'r2_cake.py').read_text(encoding='utf-8')
        # Mutation 1: revert sloped segment z_start to z1 (the old R177 bug)
        mut1_code = src_code.replace(
            'z_start = z_prev if z_prev is not None else z1',
            'z_start = z1', 1)
        self.assertNotEqual(mut1_code, src_code)
        ns1 = {}
        exec(compile(mut1_code, 'r2_cake_mut1.py', 'exec'), ns1)
        with tempfile.TemporaryDirectory() as d:
            ramp = os.path.join(d, 'ramp.gcode')
            Path(ramp).write_text(
                'G90\nM83\nG0 X90 Y110 Z0.2 F6000\n'
                'G1 X100 Y110 Z1.0 E2.0 F1200\n'
                'G1 X140 Y110 Z9.0 E10.0 F1800\n', encoding='utf-8')
            (up_m, lo_m), _ = ns1['cut_cake'](
                ramp, z_offset=3.0, out_dir=d, bed=(0, 0, 220, 220))
            # Mutated code puts 10.0 in UPPER (instead of 7.5) and 2.0 in LOWER (instead of 4.5)
            self.assertGreater(abs(_net_extrusion(lo_m) - 4.5), 2.0)
            self.assertGreater(abs(_net_extrusion(up_m) - 7.5), 2.0)

        # Mutation 2: disable per-half LAYER_MARK emission -> make_range fails
        mut2_code = src_code.replace(
            '_maybe_layer_mark(s, q0[2], tz1)', 'pass', 1)
        self.assertNotEqual(mut2_code, src_code)
        ns2 = {}
        exec(compile(mut2_code, 'r2_cake_mut2.py', 'exec'), ns2)
        with tempfile.TemporaryDirectory() as d:
            box = os.path.join(d, 'box.gcode')
            lines = ['G90', 'M83']
            for k in range(10):
                z = round(0.2 + 0.2 * k, 3)
                lines += [f'G0 X90 Y90 Z{z:.3f} F6000',
                          'G1 X120 Y90 E1.0 F1800']
            Path(box).write_text('\n'.join(lines) + '\n', encoding='utf-8')
            (up_m2, _), info_m2 = ns2['cut_cake'](
                box, z_offset=1.0, out_dir=d, bed=(0, 0, 220, 220))
            self.assertEqual(info_m2['layers_upper'], 0)
            with self.assertRaises(ValueError):
                pp.make_range(up_m2, 2, 4, out_dir=d)


if __name__ == '__main__':
    unittest.main(verbosity=2)
