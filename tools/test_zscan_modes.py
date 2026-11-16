#!/usr/bin/env python3
"""Z-scan position regressions on synthetic, non-executed G-code."""
import importlib.util
import os
from pathlib import Path
import tempfile
import unittest

if os.environ.get('R2_TEST_ENGINE') == 'active':
    import r2_postproc as pp
else:
    import r2_postproc_next as pp

ROOT = Path(__file__).resolve().parents[1]


def scan(module, lines):
    marks, changes = module.z_scan(lines)
    return [lines[i] for kind, i in marks], changes


class ZScanTests(unittest.TestCase):
    def test_m82_and_m83_hop_e_zero_and_retract_have_no_false_marker(self):
        for mode in ('M82', 'M83'):
            for travel_e in ('none', 'zero', 'retract'):
                with self.subTest(mode=mode, travel=travel_e):
                    middle = {'none': '', 'zero': ' E0' if mode == 'M83' else ' E1',
                              'retract': ' E-0.2' if mode == 'M83' else ' E0.8'}[travel_e]
                    first = ' E1' if mode == 'M83' else ' E2'
                    second = ' E1' if mode == 'M83' else ' E3'
                    lines = [mode, 'G90', 'G1 X10 Y0 Z0.2 E1', 'G0 Z0.4',
                             'G1 X12 Y0' + middle, 'G0 Z0.2', 'G1 X20 Y0' + first,
                             'G0 Z0.4', 'G1 X30 Y0' + second]
                    markers, _ = scan(pp, lines)
                    self.assertEqual([lines[-1]], markers)

    def test_absolute_e_only_and_g92_update_state(self):
        lines = ['G90', 'M82', 'G1 X0 Y0 Z0.2 E1', 'G1 E0.8',
                 'G0 Z0.4', 'G1 X1 E0.8', 'G0 Z0.2', 'G92 E0',
                 'G1 X2 E0.1', 'G0 Z0.4', 'G1 X3 E0.2']
        self.assertEqual([lines[-1]], scan(pp, lines)[0])

    def test_klipper_g91_m82_e_mode_is_relative_and_tracks_return_to_g90(self):
        lines = ['G90', 'M82', 'G1 X0 Y0 Z0.2 E1', 'G91', 'G1 E-0.2',
                 'G90', 'G0 Z0.4', 'G1 X1 E0.8', 'G0 Z0.2',
                 'G1 X2 E1.0', 'G0 Z0.4', 'G1 X3 E1.2']
        self.assertEqual([lines[-1]], scan(pp, lines)[0])

    def test_mark_is_before_real_positive_extrusion_in_process(self):
        lines = ['M83', 'G90', ';TYPE:External perimeter', 'G1 X0 Y0 Z0.2 E1',
                 'G0 Z0.4', 'G1 X1 E0', 'G0 Z0.2', 'G1 X2 E1',
                 'G0 Z0.4', 'G1 X3 E1']
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'x.gcode'; path.write_text('\n'.join(lines) + '\n')
            summary = pp.process(str(path))
            output = path.read_text().splitlines()
            self.assertEqual(1, summary['marks_added'])
            self.assertEqual('G1 X3 E1', output[output.index('LAYER_MARK') + 1])

    def test_old_backup_proves_false_e_zero_marker(self):
        spec = importlib.util.spec_from_file_location('old_engine_z', ROOT/'backups/r2_postproc_R2-2026-11-13.1_V1.py')
        old = importlib.util.module_from_spec(spec); spec.loader.exec_module(old)
        lines = ['M83', 'G90', 'G1 X0 Y0 Z0.2 E1', 'G0 Z0.4',
                 'G1 X1 E0', 'G0 Z0.2', 'G1 X2 E1', 'G0 Z0.4', 'G1 X3 E1']
        self.assertEqual([lines[-1]], scan(pp, lines)[0])
        self.assertIn(lines[4], scan(old, lines)[0])
        with self.assertRaises(AssertionError): self.assertEqual([lines[-1]], scan(old, lines)[0])

if __name__ == '__main__': unittest.main(verbosity=2)
