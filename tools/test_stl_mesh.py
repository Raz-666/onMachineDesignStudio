"""Independent numeric mesh checks for the ACTIVE exporter, no printer needed."""
from pathlib import Path
import struct
import tempfile
import unittest

import r2_postproc as pp
from stl_audit import inspect_stl


class MeshTests(unittest.TestCase):
    def export(self, root, start=(0, 0), end=(20, 0), helpers=False):
        # One ribbon, width .5 mm, height .2 mm, length 20 mm.
        e = 20 * .5 * .2 / (1.75**2 * 3.141592653589793 / 4)
        text = 'G90\nM83\nG0 X%d Y%d Z0.2\n' % start
        if helpers:
            text += ';TYPE:Support\nG1 X100 Y100 E1\nG0 X%d Y%d\n' % start
        text += ';TYPE:External perimeter\nG1 X%d Y%d E%.12f\n' % (*end, e)
        source = root/'source.gcode'
        source.write_text(text)
        rel, info = pp._stl_export(str(root), source.name)
        self.assertEqual(source.read_text(), text)
        return root/rel, info

    def test_known_ribbon_geometry_all_axis_directions(self):
        for start, end in [((0,0),(20,0)), ((20,0),(0,0)),
                           ((0,0),(0,20)), ((0,20),(0,0)),
                           ((100,80),(120,80))]:
            with self.subTest(start=start, end=end), tempfile.TemporaryDirectory() as tmp:
                mesh, info = self.export(Path(tmp), start, end)
                report = inspect_stl(mesh)
                self.assertEqual(info['boxes'], 1)
                self.assertEqual(report['triangles'], 12)
                self.assertAlmostEqual(report['signed_volume'], 2, places=5)
                self.assertEqual(report['vertex_connected_components'], 1)
                for key in ('degenerate_faces', 'normal_errors', 'duplicate_faces',
                            'boundary_edges', 'nonmanifold_edges', 'winding_errors'):
                    self.assertEqual(report[key], 0, key)
                moving = 0 if start[0] != end[0] else 1
                for axis in range(3):
                    expected = ((min(start[axis],end[axis]), max(start[axis],end[axis]))
                                if axis == moving else
                                (start[axis]-.25, start[axis]+.25) if axis < 2 else (0,.2))
                    for bound in (0,1):
                        self.assertAlmostEqual(report['bbox'][bound][axis], expected[bound], places=5)

    def test_support_excluded_and_input_unchanged(self):
        with tempfile.TemporaryDirectory() as tmp:
            mesh, info = self.export(Path(tmp), helpers=True)
            self.assertGreater(info['excl']['SUPPORT'], 0)
            self.assertAlmostEqual(inspect_stl(mesh)['signed_volume'], 2, places=5)

    def test_known_stacked_ribbon_topology_defect(self):
        # Characterization, NOT an acceptance test: preserve the reproducer
        # until the exporter can reconstruct a proper surface without boxes.
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            mesh, _ = self.export(root)
            source = root/'source.gcode'
            text = source.read_text()
            last = text.splitlines()[-1]
            source.write_text(text + 'G0 X0 Y0 Z0.4\n' + last + '\n')
            rel, _ = pp._stl_export(tmp, source.name)
            report = inspect_stl(root/rel)
            self.assertEqual(report['duplicate_faces'], 2)
            self.assertEqual(report['nonmanifold_edges'], 5)
            self.assertAlmostEqual(report['signed_volume'], 4, places=5)

    def test_parser_rejects_corrupt_structure_and_nonfinite(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            mesh, _ = self.export(root)
            data = mesh.read_bytes()
            nan = bytearray(data)
            struct.pack_into('<f', nan, 84+12, float('nan'))
            for bad in (data[:50], data[:-1], data+b'garbage', bytes(nan)):
                mesh.write_bytes(bad)
                with self.assertRaises(ValueError): inspect_stl(mesh)

    def test_parser_detects_reversal_duplicate_and_open_mesh(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            mesh, _ = self.export(root)
            data = mesh.read_bytes()
            # Flip one triangle without fixing its normal: both checks must fail.
            flipped = bytearray(data)
            flipped[84+24:84+36], flipped[84+36:84+48] = data[84+36:84+48], data[84+24:84+36]
            mesh.write_bytes(flipped)
            report = inspect_stl(mesh)
            self.assertGreater(report['normal_errors'], 0)
            self.assertGreater(report['winding_errors'], 0)
            duplicate = bytearray(data + data[84:134])
            struct.pack_into('<I', duplicate, 80, 13)
            mesh.write_bytes(duplicate)
            report = inspect_stl(mesh)
            self.assertEqual(report['duplicate_faces'], 1)
            self.assertGreater(report['nonmanifold_edges'], 0)
            opened = bytearray(data[:-50])
            struct.pack_into('<I', opened, 80, 11)
            mesh.write_bytes(opened)
            self.assertGreater(inspect_stl(mesh)['boundary_edges'], 0)


if __name__ == '__main__':
    unittest.main(verbosity=2)
