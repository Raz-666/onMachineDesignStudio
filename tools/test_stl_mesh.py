"""Independent numeric mesh checks for the ACTIVE object exporter (OBJ), no
printer needed.

R2.14 (arena): the STL binary export was REMOVED - the OBJ is the only object
export (same triangles, vertex-deduped). The geometry checks below run against
the OBJ via inspect_obj; the inspect_stl robustness checks keep a tiny binary
STL fixture inline (inspect_stl is still used by model_export.py).
"""
from pathlib import Path
import struct
import tempfile
import unittest

import r2_postproc as pp
from stl_audit import inspect_stl, inspect_obj


def _ribbon_triangles(start=(0, 0), end=(20, 0)):
    """A closed, non-degenerate box (like the exporter's box soup) as (a,b,c)
    vertex triples - 12 triangles. Used as a binary-STL fixture for the
    inspect_stl robustness checks (the exporter no longer produces STL)."""
    x0, y0, z0 = 0.0, 0.0, 0.0
    x1, y1, z1 = 20.0, 10.0, 1.0
    v = {(i, j, k): (x0 if i == 0 else x1,
                     y0 if j == 0 else y1,
                     z0 if k == 0 else z1)
         for i in (0, 1) for j in (0, 1) for k in (0, 1)}
    def T(a, b, c):
        return (v[a], v[b], v[c])
    return [T((0,0,0),(1,0,0),(1,1,0)), T((0,0,0),(1,1,0),(0,1,0)),
            T((0,0,1),(0,1,1),(1,1,1)), T((0,0,1),(1,1,1),(1,0,1)),
            T((0,0,0),(0,0,1),(0,1,1)), T((0,0,0),(0,1,1),(0,1,0)),
            T((1,0,0),(1,1,0),(1,1,1)), T((1,0,0),(1,1,1),(1,0,1)),
            T((0,0,0),(1,0,1),(1,0,0)), T((0,0,0),(0,0,1),(1,0,1)),
            T((0,1,0),(0,1,1),(1,1,1)), T((0,1,0),(1,1,1),(1,1,0))]


def _write_binary_stl(path, triangles):
    """Write a minimal binary STL from (a,b,c) triples (normals recomputed).
    The triangle count lives at offset 80 inside the 84-byte header block."""
    with open(path, 'wb') as fo:
        fo.write(struct.pack('<80sI', b'test', len(triangles)))
        for a, b, c in triangles:
            u = tuple(b[i] - a[i] for i in range(3))
            v = tuple(c[i] - a[i] for i in range(3))
            n = (u[1]*v[2]-u[2]*v[1], u[2]*v[0]-u[0]*v[2], u[0]*v[1]-u[1]*v[0])
            ln = (n[0]**2 + n[1]**2 + n[2]**2) ** 0.5
            n = (n[0]/ln, n[1]/ln, n[2]/ln) if ln else (0.0, 0.0, 0.0)
            fo.write(struct.pack('<12fH', *n, *a, *b, *c, 0))


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
        rel, info = pp._obj_export(str(root), source.name)
        self.assertEqual(source.read_text(), text)
        return root/rel, info

    def test_known_ribbon_geometry_all_axis_directions(self):
        for start, end in [((0,0),(20,0)), ((20,0),(0,0)),
                           ((0,0),(0,20)), ((0,20),(0,0)),
                           ((100,80),(120,80))]:
            with self.subTest(start=start, end=end), tempfile.TemporaryDirectory() as tmp:
                mesh, info = self.export(Path(tmp), start, end)
                report = inspect_obj(mesh)
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
            self.assertAlmostEqual(inspect_obj(mesh)['signed_volume'], 2, places=5)

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
            rel, _ = pp._obj_export(tmp, source.name)
            report = inspect_obj(root/rel)
            self.assertEqual(report['duplicate_faces'], 2)
            self.assertEqual(report['nonmanifold_edges'], 5)
            self.assertAlmostEqual(report['signed_volume'], 4, places=5)

    def test_obj_parser_rejects_corrupt_structure(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            mesh, _ = self.export(root)
            # An OBJ with no vertices or no faces is corrupt -> ValueError.
            mesh.write_text('# only a comment, no geometry\n')
            with self.assertRaises(ValueError):
                inspect_obj(mesh)
            mesh.write_text('v 0 0 0\nv 1 0 0\nv 0 1 0\n')  # vertices, no faces
            with self.assertRaises(ValueError):
                inspect_obj(mesh)

    def test_stl_parser_robustness_keeps_binary_stl_coverage(self):
        # inspect_stl is still used by model_export.py - keep its robustness
        # checks with an inline binary STL fixture (the exporter no longer
        # produces STL).
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            stl = root/'fixture.stl'
            _write_binary_stl(stl, _ribbon_triangles())
            data = stl.read_bytes()
            nan = bytearray(data)
            struct.pack_into('<f', nan, 84+12, float('nan'))
            for bad in (data[:50], data[:-1], data+b'garbage', bytes(nan)):
                stl.write_bytes(bad)
                with self.assertRaises(ValueError):
                    inspect_stl(stl)

    def test_stl_parser_detects_reversal_duplicate_and_open_mesh(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            stl = root/'fixture.stl'
            _write_binary_stl(stl, _ribbon_triangles())
            data = stl.read_bytes()
            # Flip one triangle without fixing its normal: both checks must fail.
            flipped = bytearray(data)
            flipped[84+24:84+36], flipped[84+36:84+48] = data[84+36:84+48], data[84+24:84+36]
            stl.write_bytes(flipped)
            report = inspect_stl(stl)
            self.assertGreater(report['normal_errors'], 0)
            self.assertGreater(report['winding_errors'], 0)
            duplicate = bytearray(data + data[84:134])
            struct.pack_into('<I', duplicate, 80, 13)
            stl.write_bytes(duplicate)
            report = inspect_stl(stl)
            self.assertEqual(report['duplicate_faces'], 1)
            self.assertGreater(report['nonmanifold_edges'], 0)
            opened = bytearray(data[:-50])
            struct.pack_into('<I', opened, 80, 11)
            stl.write_bytes(opened)
            self.assertGreater(inspect_stl(stl)['boundary_edges'], 0)


if __name__ == '__main__':
    unittest.main(verbosity=2)
