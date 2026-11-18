"""Cylinder oracles for stitching per-revolution rings into wall surfaces."""
import math
from pathlib import Path
import tempfile
import unittest

from spiral_rings import spiral_rings
from ring_wall import ring_wall_mesh
from stl_audit import inspect_stl

SEGMENTS_PER_REVOLUTION=48


def helix_rings(radius=10, revolutions=12, pitch=1/16, samples=32):
    points=[]
    for i in range(int(revolutions*SEGMENTS_PER_REVOLUTION)+1):
        angle=2*math.pi*i/SEGMENTS_PER_REVOLUTION
        points.append((radius*math.cos(angle),radius*math.sin(angle),
                       pitch*i/SEGMENTS_PER_REVOLUTION))
    return spiral_rings(points,pitch_mm=pitch,samples_per_revolution=samples)['rings']


class RingWallTests(unittest.TestCase):
    def audited(self,data):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'wall.stl'
            path.write_bytes(data)
            return inspect_stl(path)

    def test_cylinder_wall_open_only_at_ends(self):
        rings=helix_rings()
        self.assertEqual(len(rings),12)
        data,report=ring_wall_mesh(rings)
        self.assertEqual(report['triangles'],2*11*32)
        self.assertEqual(report['open_boundary_edges'],64)
        audit=self.audited(data)
        self.assertEqual(audit['boundary_edges'],64)
        self.assertEqual(audit['nonmanifold_edges'],0)
        self.assertEqual(audit['duplicate_faces'],0)
        # Open surfaces imbalance exactly their boundary edges, nothing else.
        self.assertEqual(audit['winding_errors'],64)
        self.assertEqual(audit['vertex_connected_components'],1)
        self.assertFalse(report['export_ready'])
        # Wall points stay on the cylinder within chord interpolation error.
        self.assertEqual(report['audit']['degenerate_faces'],0)

    def test_descending_source_rings_still_stitch(self):
        points=[(10*math.cos(2*math.pi*i/48),10*math.sin(2*math.pi*i/48),(1/16)*i/48)
                for i in range(48*6+1)]
        rings=spiral_rings(points[::-1],pitch_mm=1/16,samples_per_revolution=16)['rings']
        # Descending sources yield top-down bands; stitch them bottom-up.
        data,report=ring_wall_mesh(list(reversed(rings)))
        self.assertEqual(report['ring_count'],6)
        self.assertEqual(report['open_boundary_edges'],32)
        self.assertEqual(self.audited(data)['winding_errors'],32)

    def test_validation_rejections(self):
        rings=helix_rings()
        with self.assertRaises(ValueError):ring_wall_mesh(rings[:1])
        mixed=[dict(rings[0])] + [dict(rings[1],samples=31)]
        with self.assertRaises(ValueError):ring_wall_mesh(mixed)
        with self.assertRaises(ValueError):ring_wall_mesh(list(reversed(rings)))
        degenerate=[dict(rings[0])]
        shifted=[dict(rings[1],points_mm=rings[0]['points_mm'])]
        with self.assertRaises(ValueError):ring_wall_mesh(degenerate+shifted)

    def test_synthetic_vase_from_two_revolutions(self):
        # One monotonic path of two revolutions stands in for a vase wall.
        rings=helix_rings(revolutions=2,samples=16)
        self.assertEqual(len(rings),2)
        data,report=ring_wall_mesh(rings)
        self.assertEqual(report['triangles'],2*1*16)
        audit=self.audited(data)
        self.assertEqual(audit['boundary_edges'],32)
        self.assertEqual(audit['nonmanifold_edges'],0)


if __name__ == '__main__':unittest.main(verbosity=2)
