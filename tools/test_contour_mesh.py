"""Analytic geometry oracles for the experimental boundary-based surface builder."""
import math
from pathlib import Path
import tempfile
import unittest

from contour_mesh import prism_mesh, loft_mesh, binary_stl
from stl_audit import inspect_stl


class ContourTests(unittest.TestCase):
    def check_mesh(self, boundary, bottom, top, area):
        original = list(boundary)
        mesh = prism_mesh(boundary, bottom, top)
        self.assertEqual(boundary, original)
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp)/'surface.stl'
            path.write_bytes(binary_stl(mesh))
            report = inspect_stl(path)
        self.assertAlmostEqual(report['signed_volume'], area*(top-bottom), places=4)
        for key in ('degenerate_faces','normal_errors','duplicate_faces',
                    'boundary_edges','nonmanifold_edges','winding_errors'):
            self.assertEqual(report[key], 0, key)
        self.assertEqual(report['vertex_connected_components'], 1)
        self.assertEqual(report['triangles'], 4*len(original)-4)
        return report

    def test_rectangle_both_orientations_and_translated(self):
        for boundary in ([(0,0),(20,0),(20,10),(0,10)],
                         [(0,10),(20,10),(20,0),(0,0)],
                         [(-30,50),(-10,50),(-10,60),(-30,60)]):
            with self.subTest(boundary=boundary):
                self.check_mesh(boundary, 2, 12, 200)

    def test_concave_L_caps_preserve_notch(self):
        # A 3x3 square minus its upper-right 2x2 quadrant: area 5.
        boundary = [(0,0),(3,0),(3,1),(1,1),(1,3),(0,3)]
        self.check_mesh(boundary, 0, 2, 5)
        self.check_mesh(boundary[::-1], 0, 2, 5)
        for tri in prism_mesh(boundary, 0, 2):
            if len({v[2] for v in tri}) == 1:
                # Sample each cap triangle, not only its centroid.
                for i in range(11):
                    for j in range(11-i):
                        weights = (i/10,j/10,1-(i+j)/10)
                        x,y = [sum(weights[k]*tri[k][axis] for k in range(3)) for axis in (0,1)]
                        self.assertFalse(x > 1+1e-9 and y > 1+1e-9)

    def test_stacked_height_has_no_internal_caps(self):
        report = self.check_mesh([(0,-.25),(20,-.25),(20,.25),(0,.25)],0,.4,10)
        self.assertEqual(report['triangles'],12)
        self.assertEqual(report['bbox'], [[0,-.25,0],[20,.25,report['bbox'][1][2]]])

    def test_explicit_closure_equivalent(self):
        points = [(0,0),(2,0),(0,2)]
        self.assertEqual(prism_mesh(points,0,1),prism_mesh(points+[points[0]],0,1))

    def test_invalid_boundaries_fail_instead_of_repair(self):
        cases = [[], [(0,0),(1,0)], [(0,0),(1,1),(0,1),(1,0)],
                 [(0,0),(1,0),(2,0),(2,1),(0,1)],
                 [(0,0),(1,0),(1,1),(0,0),(0,1)],
                 [(0,0),(float('nan'),0),(0,1)],
                 [(0,0),(1e6,0),(0,1)],
                 [(math.cos(i),math.sin(i)) for i in range(257)]]
        for points in cases:
            with self.subTest(points=points[:4]), self.assertRaises(ValueError):
                prism_mesh(points,0,1)
        for low,high in [(1,0),(0,0),(0,float('inf'))]:
            with self.assertRaises(ValueError): prism_mesh([(0,0),(1,0),(0,1)],low,high)

    def check_holes(self, outer, holes, expected_volume):
        import copy
        before = copy.deepcopy((outer,holes))
        triangles = prism_mesh(outer,0,2,holes=holes)
        self.assertEqual((outer,holes),before)
        vertices={v for tri in triangles for v in tri}
        edges={tuple(sorted((tri[i],tri[(i+1)%3]))) for tri in triangles for i in range(3)}
        # Closed orientable shell with h through-holes has Euler characteristic 2-2h.
        self.assertEqual(len(vertices)-len(edges)+len(triangles),2-2*len(holes))
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp)/'holes.stl'
            path.write_bytes(binary_stl(triangles))
            report = inspect_stl(path)
        self.assertAlmostEqual(report['signed_volume'],expected_volume,places=4)
        for key in ('boundary_edges','nonmanifold_edges','winding_errors',
                    'degenerate_faces','normal_errors','duplicate_faces'):
            self.assertEqual(report[key],0,key)
        self.assertEqual(report['vertex_connected_components'],1)
        # Independent ray casting at interior samples of every cap triangle.
        def in_hole(x,y,ring):
            crossings = 0
            for a,b in zip(ring,ring[1:]+ring[:1]):
                if (a[1] > y) != (b[1] > y):
                    crossings += x < a[0]+(y-a[1])*(b[0]-a[0])/(b[1]-a[1])
            return crossings % 2 == 1
        for tri in triangles:
            if len({v[2] for v in tri}) == 1:
                for i in range(1,10):
                    for j in range(1,10-i):
                        weights=(i/10,j/10,1-(i+j)/10)
                        x,y=[sum(weights[k]*tri[k][axis] for k in range(3)) for axis in (0,1)]
                        self.assertFalse(any(in_hole(x,y,h) for h in holes))

    def test_square_through_hole_orientations(self):
        outer=[(0,0),(10,0),(10,10),(0,10)]
        hole=[(3,3),(7,3),(7,7),(3,7)]
        for o in (outer,outer[::-1]):
            for h in (hole,hole[::-1]):
                self.check_holes(o,[h],168)

    def test_multiple_holes_order_and_concave_outer(self):
        outer=[(0,0),(10,0),(10,6),(6,6),(6,10),(0,10)]
        holes=[[(1,1),(3,1),(3,3),(1,3)],[(7,1),(9,1),(9,3),(7,3)]]
        self.check_holes(outer,holes,152)
        self.check_holes(outer,holes[::-1],152)

    def test_concave_hole(self):
        self.check_holes([(0,0),(10,0),(10,10),(0,10)],
                         [[(2,2),(6,2),(6,3),(3,3),(3,6),(2,6)]],186)

    def test_three_holes_parameter_sweep(self):
        for size in (.5,1,1.5):
            for shift in (0,.2,.4):
                outer=[(0,0),(12,0),(12,8),(0,8)]
                holes=[]
                for x,y in ((1+shift,1),(5,4+shift),(9-shift,2)):
                    holes.append([(x,y),(x+size,y),(x+size,y+size),(x,y+size)])
                with self.subTest(size=size,shift=shift):
                    self.check_holes(outer,holes,2*(96-3*size*size))

    def test_invalid_hole_relationships(self):
        outer=[(0,0),(10,0),(10,10),(0,10)]
        square=lambda x,y,w:[(x,y),(x+w,y),(x+w,y+w),(x,y+w)]
        cases=[[square(11,1,2)], [square(0,1,2)], [square(9,1,2)],
               [square(1,1,5),square(2,2,1)],
               [square(1,1,3),square(3,3,3)],
               [square(1,1,2),square(3,1,2)]]
        for holes in cases:
            with self.subTest(holes=holes),self.assertRaises(ValueError):
                prism_mesh(outer,0,2,holes=holes)

    def check_loft(self, boundary, sections, area, holes=()):
        import copy
        before=copy.deepcopy((boundary,sections,holes))
        triangles=loft_mesh(boundary,sections,holes=holes)
        self.assertEqual((boundary,sections,holes),before)
        volume=sum(area*(b[0]-a[0])*(a[1]**2+a[1]*b[1]+b[1]**2)/3
                   for a,b in zip(sections,sections[1:]))
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'loft.stl'
            path.write_bytes(binary_stl(triangles))
            report=inspect_stl(path)
        self.assertAlmostEqual(report['signed_volume'],volume,places=4)
        for key in ('boundary_edges','nonmanifold_edges','winding_errors',
                    'degenerate_faces','normal_errors','duplicate_faces'):
            self.assertEqual(report[key],0,key)
        vertices={v for tri in triangles for v in tri}
        edges={tuple(sorted((tri[i],tri[(i+1)%3]))) for tri in triangles for i in range(3)}
        self.assertEqual(len(vertices)-len(edges)+len(triangles),2-2*len(holes))
        self.assertEqual(report['vertex_connected_components'],1)
        for tri in triangles:
            if len({p[2] for p in tri}) == 1:
                self.assertIn(tri[0][2],(sections[0][0],sections[-1][0]))
        return report

    def test_loft_taper_and_expansion(self):
        square=[(0,0),(10,0),(10,10),(0,10)]
        self.check_loft(square,[(0,1,0,0),(10,.5,0,0)],100)
        self.check_loft(square,[(0,.5,0,0),(10,1,0,0)],100)

    def test_loft_variable_heights_lean_and_hole(self):
        outer=[(0,0),(10,0),(10,10),(0,10)]
        hole=[(3,3),(7,3),(7,7),(3,7)]
        sections=[(0,1,0,0),(.2,.8,1,-2),(.7,1.2,-2,1),(4,.5,3,4)]
        self.check_loft(outer,sections,84,[hole])
        self.check_loft(outer[::-1],sections,84,[hole[::-1]])

    def test_loft_concave_cross_section(self):
        self.check_loft([(0,0),(3,0),(3,1),(1,1),(1,3),(0,3)],
                        [(0,1,0,0),(1,2,-1,0),(3,.5,4,2)],5)

    def test_loft_straight_matches_prism_volume_and_bounds(self):
        report=self.check_loft([(0,0),(2,0),(2,3),(0,3)],
                               [(0,1,0,0),(.2,1,0,0),(2,1,0,0)],6)
        self.assertEqual(report['bbox'],[[0,0,0],[2,3,2]])

    def test_loft_invalid_sections_and_float32_collapse(self):
        boundary=[(0,0),(2,0),(2,2),(0,2)]
        cases=[[],[(0,1,0,0)],[(1,1,0,0),(0,1,0,0)],
               [(0,1,0,0),(0,1,0,0)],[(0,1,0,0),(1,0,0,0)],
               [(0,1,0,0),(1,-1,0,0)],[(0,1,0,0),(1,float('nan'),0,0)],
               [(0,1,0,0),(1,1,1e6,0)],[(i,1,0,0) for i in range(65)],
               [(0,1,0,0),(1,1,0)]]
        for sections in cases:
            with self.subTest(sections=sections[:2]),self.assertRaises(ValueError):
                loft_mesh(boundary,sections)
        triangles=loft_mesh(boundary,[(10000,1,0,0),(10000.00001,1,0,0)])
        with self.assertRaises(ValueError): binary_stl(triangles)

    def test_float32_collapse_rejected(self):
        mesh = prism_mesh([(10000,0),(10000.00001,0),(10000.00001,1),(10000,1)],0,1)
        with self.assertRaises(ValueError): binary_stl(mesh)


if __name__ == '__main__': unittest.main(verbosity=2)
