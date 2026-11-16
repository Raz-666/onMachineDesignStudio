#!/usr/bin/env python3
"""CENTER-only object bounding-box regression tests on temporary files."""
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


def upgrade(module, root, name, mode, extra=''):
    path = root/name
    e1, e2, wipe = ('E1', 'E2', 'E1.8') if mode == 'M82' else ('E1', 'E1', 'E-0.2')
    text = (f'{module.TAG}\n{mode}\nG90\nEXCLUDE_OBJECT_DEFINE NAME=o CENTER=5,5\n'
            f'EXCLUDE_OBJECT_START NAME=o\nG1 X0 Y0 {e1}\nG1 X10 Y10 {e2}\n'
            f'G1 X100 Y100 {wipe}\n{extra}EXCLUDE_OBJECT_END NAME=o\n')
    path.write_text(text)
    changed = module._upgrade_center_excludes(str(path))
    define = next(l for l in path.read_text().splitlines() if l.startswith('EXCLUDE_OBJECT_DEFINE'))
    return changed, define, text, path


class BBoxTests(unittest.TestCase):
    def test_absolute_and_relative_e_exclude_xy_wipe(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for mode in ('M82', 'M83'):
                with self.subTest(mode=mode):
                    changed, line, _, path = upgrade(pp, root, mode+'.gcode', mode)
                    self.assertTrue(changed)
                    self.assertIn('POLYGON=[[0.00,0.00],[10.00,0.00],[10.00,10.00],[0.00,10.00]]', line)
                    before = path.read_bytes()
                    self.assertFalse(pp._upgrade_center_excludes(str(path)))
                    self.assertEqual(before, path.read_bytes())

    def test_unknown_xy_origin_or_arc_fails_closed(self):
        for suffix in ('G92 X0\n', 'G2 X11 Y11 I1 J1 E3\n', 'G20\n'):
            with self.subTest(suffix=suffix), tempfile.TemporaryDirectory() as tmp:
                changed, line, original, path = upgrade(pp, Path(tmp), 'x.gcode', 'M82', suffix)
                self.assertFalse(changed)
                self.assertNotIn('POLYGON=', line)
                self.assertEqual(original, path.read_text())

    def test_g92_e_and_relative_xy_mode(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp)/'x.gcode'
            path.write_text('M82\nG90\nEXCLUDE_OBJECT_DEFINE NAME=o CENTER=5,5\n'
                            'EXCLUDE_OBJECT_START NAME=o\nG1 X0 Y0 E1\nG91\n'
                            'G1 X10 Y10 E1\nG90\nG92 E0\nG1 X100 Y100 E-0.1\nEXCLUDE_OBJECT_END NAME=o\n')
            self.assertTrue(pp._upgrade_center_excludes(str(path)))
            self.assertIn('POLYGON=[[0.00,0.00],[10.00,0.00],[10.00,10.00],[0.00,10.00]]', path.read_text())

    def test_reference_backup_includes_absolute_retraction_wipe(self):
        spec = importlib.util.spec_from_file_location('old_bbox', ROOT/'backups/r2_postproc_R2-2026-11-13.1_V1.py')
        old = importlib.util.module_from_spec(spec); spec.loader.exec_module(old)
        with tempfile.TemporaryDirectory() as tmp:
            _, line, _, _ = upgrade(old, Path(tmp), 'old.gcode', 'M82')
            self.assertIn('100.00', line)
            with self.assertRaises(AssertionError): self.assertNotIn('100.00', line)

if __name__ == '__main__': unittest.main(verbosity=2)
