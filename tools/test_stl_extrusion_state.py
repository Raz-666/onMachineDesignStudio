#!/usr/bin/env python3
"""STL filtered-segment E-state regressions, temporary synthetic fixtures only."""
import importlib.util
import os
from pathlib import Path
import struct
import tempfile
import unittest

if os.environ.get('R2_TEST_ENGINE') == 'active':
    import r2_postproc as pp
else:
    import r2_postproc_next as pp

ROOT = Path(__file__).resolve().parents[1]


def width(module, root, mode, reset=False):
    root.mkdir(parents=True, exist_ok=True)
    first, second = ('E1', 'E1') if mode == 'M83' else ('E1', 'E2')
    if reset and mode == 'M82': second = 'E1'
    data = (f'{mode}\nG90\nG0 X0 Y0 Z0.2\n;TYPE:Support\n'
            f'G1 X20 Y0 {first}\n' + ('G92 E0\n' if reset and mode == 'M82' else '') +
            f';TYPE:External perimeter\nG1 X40 Y0 {second}\n').encode()
    src = root / 'source.gcode'; src.write_bytes(data)
    rel, info = module._stl_export(str(root), src.name)
    mesh = (root / rel).read_bytes()
    ys = []
    for n in range(info['tris']):
        values = struct.unpack_from('<12fH', mesh, 84 + n * 50)
        ys.extend((values[4], values[7], values[10]))
    assert src.read_bytes() == data
    return max(ys) - min(ys), info


class STLExtrusionTests(unittest.TestCase):
    def test_filtered_absolute_and_relative_e_widths_match(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            a, ai = width(pp, root/'a', 'M82')
            b, bi = width(pp, root/'b', 'M83')
            self.assertGreater(a, 0)
            self.assertAlmostEqual(a, b, places=5)
            self.assertEqual(ai['boxes'], bi['boxes'])
            self.assertEqual(ai['excl'], bi['excl'])

    def test_g92_after_filtered_segment_resets_absolute_e(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            a, _ = width(pp, root/'a', 'M82', reset=True)
            b, _ = width(pp, root/'b', 'M83')
            self.assertAlmostEqual(a, b, places=5)

    def test_reference_backup_demonstrates_absolute_e_bug(self):
        spec = importlib.util.spec_from_file_location('old_engine_stl', ROOT/'backups/r2_postproc_R2-2026-11-13.1_V1.py')
        old = importlib.util.module_from_spec(spec); spec.loader.exec_module(old)
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            a, _ = width(old, root/'old-a', 'M82')
            b, _ = width(old, root/'old-b', 'M83')
            self.assertGreater(a, b * 1.9)
            with self.assertRaises(AssertionError): self.assertAlmostEqual(a, b, places=5)

if __name__ == '__main__': unittest.main(verbosity=2)
