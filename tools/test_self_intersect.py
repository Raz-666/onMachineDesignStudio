"""Self-intersection audit: unit geometry, closed oracles, full Rose.

Scope under test: any pair of triangles WITHOUT a shared (exactly equal)
vertex must not intersect, touching included; vertex-adjacent pairs are
skipped. The full-Rose test promotes the closed-vase volume from an
assumption to a measured value.
"""
import math
import struct
import tempfile
from pathlib import Path
import unittest

from self_intersect import self_intersections, triangles_from_stl, triangles_intersect
from test_vase_closure import helix_run, rose_run
from vase_closure import close_vase_surface
from wall_run import sample_wall_run


TETRAHEDRON_A=[(0,0,0),(10,0,0),(0,10,0),(0,0,10)]
# apex inside A (1+1+1 < 10), far face beyond A's slanted face (13 > 10)
TETRAHEDRON_B=[(1,1,1),(11,1,1),(1,11,1),(1,1,11)]


def closed_tetrahedron(t):
    a,b,c,d=t
    return [(a,b,c),(a,c,d),(a,d,b),(b,d,c)]


def star_ring(notch,n=16,r_outer=2.0,r_inner=0.3,z=0.0):
    points=[]
    for i in range(n):
        angle=2*math.pi*(i+notch)/n
        radius=r_outer if i%2==0 else r_inner
        points.append((radius*math.cos(angle),radius*math.sin(angle),z))
    return points


class TrianglePairTests(unittest.TestCase):
    def test_crossing_triangles_flagged(self):
        report=self_intersections([((-5,0,-1),(5,0,-1),(0,0,1)),
                                    ((0,-5,-1),(0,5,-1),(0,0,3))])
        self.assertEqual(report['intersecting_pair_count'],1)
        self.assertEqual(report['intersecting_pairs'],[(0,1)])
        self.assertEqual(report['tested_pairs'],1)

    def test_separated_and_parallel_nested_clean(self):
        report=self_intersections([((0,0,0),(4,0,0),(0,4,0)),
                                    ((0,0,9),(1,0,9),(0,1,9)),
                                    ((1,1,5),(2,1,5),(1,2,5))])
        self.assertEqual(report['intersecting_pair_count'],0)

    def test_coplanar_overlap_flagged_disjoint_clean(self):
        report=self_intersections([((0,0,0),(4,0,0),(0,4,0)),
                                    ((1,1,0),(3,1,0),(1,3,0))])
        self.assertEqual(report['intersecting_pair_count'],1)
        report=self_intersections([((0,0,0),(1,0,0),(0,1,0)),
                                    ((5,5,0),(6,5,0),(5,6,0))])
        self.assertEqual(report['intersecting_pair_count'],0)

    def test_touching_without_shared_vertex_flagged(self):
        # Conservative: mere touching counts as self-intersection.
        report=self_intersections([((0,0,0),(1,0,0),(0,1,0)),
                                    ((-1,-1,0),(1,-1,0),(0.5,0,0))])
        self.assertEqual(report['intersecting_pair_count'],1)

    def test_vertex_adjacent_pair_skipped(self):
        report=self_intersections([((0,0,0),(1,0,0),(0,1,0)),
                                    ((1,0,0),(1,1,0),(0,1,0))])
        self.assertEqual(report['intersecting_pair_count'],0)
        self.assertEqual(report['adjacent_pairs_skipped'],1)

    def test_crossing_through_shared_vertex_out_of_scope(self):
        # Two triangles that pierce each other but share exactly one vertex
        # are a fold through a shared vertex: documented blind spot, skipped
        # as adjacent, never classified.
        report=self_intersections([((-5,0,-1),(5,0,-1),(0,0,1)),
                                    ((0,-5,-1),(0,5,-1),(0,0,1))])
        self.assertEqual(report['intersecting_pair_count'],0)
        self.assertEqual(report['adjacent_pairs_skipped'],1)
        self.assertTrue(any('folds through a shared vertex'
                            in item for item in report['limitations']))

    def test_degenerate_triangle_rejected(self):
        for degenerate in (((0,0,5),(0,0,5),(1,1,5)),   # duplicate vertex
                            ((0,0,5),(1,1,5),(2,2,5))):  # collinear
            with self.subTest(degenerate=degenerate),self.assertRaises(ValueError):
                self_intersections([((0,0,0),(1,0,0),(0,1,0)),degenerate])

    def test_cell_size_guard(self):
        triangles=closed_tetrahedron(TETRAHEDRON_A)
        with self.assertRaises(ValueError):
            self_intersections(triangles,cell_size=1e-4)
        coarse=self_intersections(triangles,cell_size=100.0)
        self.assertEqual(coarse['intersecting_pair_count'],0)

    def test_reported_pairs_capped_but_counted(self):
        report=self_intersections([((-5,0,-1),(5,0,-1),(0,0,1)),
                                    ((0,-5,-1),(0,5,-1),(0,0,3))],
                                   max_reported_pairs=0)
        self.assertEqual(report['intersecting_pair_count'],1)
        self.assertEqual(report['intersecting_pairs'],[])
        self.assertTrue(report['reported_pairs_capped'])


class ClosedSurfaceTests(unittest.TestCase):
    def test_single_tetrahedron_clean(self):
        report=self_intersections(closed_tetrahedron(TETRAHEDRON_A))
        self.assertEqual(report['intersecting_pair_count'],0)

    def test_interpenetrating_tetrahedra_flagged(self):
        triangles=closed_tetrahedron(TETRAHEDRON_A)+closed_tetrahedron(TETRAHEDRON_B)
        report=self_intersections(triangles)
        self.assertGreaterEqual(report['intersecting_pair_count'],1)
        for i,j in report['intersecting_pairs']:
            self.assertNotEqual(i//4,j//4,'pairs must span both tetrahedra')

    def test_stl_roundtrip_exact_vertices(self):
        triangles=closed_tetrahedron(TETRAHEDRON_A)
        from contour_mesh import binary_stl
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'tetra.stl'
            path.write_bytes(binary_stl(triangles))
            loaded=triangles_from_stl(path)
        self.assertEqual(len(loaded),4)
        for original,triangle in zip(triangles,loaded):
            for point,vertex in zip(original,triangle):
                expected=struct.unpack('<3f',struct.pack('<3f',*point))
                self.assertEqual(tuple(vertex),expected)

    def test_cylinder_closure_self_check_clean(self):
        rings=sample_wall_run(helix_run(),pitch_mm=1/16,samples_per_revolution=8)['rings']
        data,report=close_vase_surface(rings,bottom_z=0,top_z=5/16,
                                       check_self_intersection=True)
        check=report['self_intersection']
        self.assertIsNotNone(check)
        self.assertEqual(check['intersecting_pair_count'],0)
        self.assertEqual(check['triangles'],report['triangles'])
        self.assertFalse(any('self-intersection is not validated'
                             in item for item in report['limitations']))
        # Without the flag the assumption stays explicit in the report.
        _,default=close_vase_surface(rings,bottom_z=0,top_z=5/16)
        self.assertIsNone(default['self_intersection'])
        self.assertTrue(any('self-intersection is not validated'
                            in item for item in default['limitations']))

    def test_twisted_star_rejected_only_by_self_check(self):
        rings=[dict(points_mm=star_ring(0,z=0.0),samples=16,z_band_mm=(0.0,0.0)),
               dict(points_mm=star_ring(1,z=1.0),samples=16,z_band_mm=(1.0,1.0))]
        # Topology, winding and volume all pass; the surface still pierces
        # itself — invisible without the explicit self-intersection audit.
        data,blind=close_vase_surface(rings,bottom_z=0.0,top_z=1.0)
        self.assertGreater(blind['audit']['signed_volume'],0)
        with self.assertRaises(ValueError) as caught:
            close_vase_surface(rings,bottom_z=0.0,top_z=1.0,
                               check_self_intersection=True)
        self.assertIn('self-intersection',str(caught.exception))


class RealRoseSelfIntersectionTests(unittest.TestCase):
    def test_full_rose_closed_volume_is_measured_not_assumed(self):
        run=rose_run()
        sampled=sample_wall_run(run,pitch_mm=.2,samples_per_revolution=96,max_gap_mm=.1)
        data,report=close_vase_surface(sampled['rings'],bottom_z=1.2,top_z=24.0,
                                       check_self_intersection=True)
        check=report['self_intersection']
        self.assertEqual(check['intersecting_pair_count'],0)
        self.assertFalse(check['reported_pairs_capped'])
        self.assertEqual(check['triangles'],22266)
        # The broad phase really pruned: most co-cell pairs were adjacent.
        self.assertGreaterEqual(check['tested_pairs'],60000)
        self.assertGreaterEqual(check['adjacent_pairs_skipped'],130000)
        self.assertFalse(any('self-intersection is not validated'
                             in item for item in report['limitations']))
        self.assertAlmostEqual(report['audit']['signed_volume'],4810.105276,places=3)


if __name__ == '__main__':unittest.main(verbosity=2)
