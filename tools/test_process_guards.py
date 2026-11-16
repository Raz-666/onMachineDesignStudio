#!/usr/bin/env python3
"""Offline process() skip-before-rewrite regressions; temporary files only."""
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
RETRACT = ('M83\nG1 F4800 E-5.2\nG0 X50 Y50 F9000\n'
           'G1 F1800 E5.2\nG1 X60 Y50 E0.5 F1800\n')


class SkipTests(unittest.TestCase):
    def test_skip_unchanged_even_with_retract_rewrite(self):
        for header in ('; R2-POSTPROC v5\n_FILE_INFO RETRACT=slicer\n', '; R2-PLOT\n'):
            for dry in (False, True):
                with self.subTest(header=header, dry=dry), tempfile.TemporaryDirectory() as tmp:
                    path = Path(tmp) / 'input.gcode'
                    data = (header + RETRACT).encode(); path.write_bytes(data)
                    result = pp.process(str(path), retract_rewrite=True, dry=dry)
                    self.assertTrue(result['skipped'])
                    self.assertEqual(0, result['retract_pairs'])
                    self.assertEqual(data, path.read_bytes())

    def test_untagged_opt_in_retract_fix_is_preserved(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'input.gcode'; path.write_text(RETRACT)
            summary = pp.process(str(path), retract_rewrite=True)
            self.assertFalse(summary['skipped'])
            self.assertEqual(1, summary['retract_pairs'])
            self.assertIn('\nG10\n', path.read_text())
            self.assertIn('\nG11\n', path.read_text())

    def test_reference_backup_demonstrates_old_bug(self):
        spec = importlib.util.spec_from_file_location('reference_postproc', ROOT/'backups/r2_postproc_R2-2026-11-13.1_V1.py')
        ref = importlib.util.module_from_spec(spec); spec.loader.exec_module(ref)
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'input.gcode'
            data = ('; R2-POSTPROC v5\n_FILE_INFO RETRACT=slicer\n' + RETRACT).encode()
            path.write_bytes(data)
            summary = ref.process(str(path), retract_rewrite=True)
            self.assertTrue(summary['skipped'])
            with self.assertRaises(AssertionError): self.assertEqual(data, path.read_bytes())

if __name__ == '__main__': unittest.main(verbosity=2)
