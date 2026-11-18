"""Analytic tests for explicit bead-width estimates and restricted offsets."""
import math
from pathlib import Path
import tempfile
import unittest
from physical_contours import width_from_filament, offset_convex_centerline
from contour_mesh import prism_mesh, binary_stl
from stl_audit import inspect_stl


class PhysicalTests(unittest.TestCase):
    def test_stadium_width_round_trip(self):
        for w,h in ((.4,.2),(.6,.3),(.2,.2)):
            area=h*(w-h)+math.pi*h*h/4
            e=area*20/(math.pi*1.75**2/4)
            result=width_from_filament(filament_mm=e,path_length_mm=20,
                                      layer_height_mm=h,filament_diameter_mm=1.75)
            self.assertAlmostEqual(result['width_mm'],w)
            self.assertFalse(result['measured'])

    def test_invalid_extrusion_assumptions_rejected(self):
        good=dict(filament_mm=1,path_length_mm=10,layer_height_mm=.2,filament_diameter_mm=1.75)
        for field in good:
            for bad in (0,-1,float('nan'),float('inf')):
                with self.subTest(field=field,bad=bad),self.assertRaises(ValueError):
                    width_from_filament(**dict(good,**{field:bad}))
        with self.assertRaises(ValueError):width_from_filament(**dict(good,filament_mm=.00001))

    def test_square_outer_and_hole_both_windings(self):
        square=[(0,0),(10,0),(10,10),(0,10)]
        for points in (square,square[::-1]):
            original=points[:]
            for role,low,high in (('outer',-.2,10.2),('hole',.2,9.8)):
                result=offset_convex_centerline(points,width_mm=.4,role=role)
                self.assertEqual(points,original)
                self.assertAlmostEqual(min(p[0] for p in result['points_mm']),low)
                self.assertAlmostEqual(max(p[1] for p in result['points_mm']),high)
                self.assertAlmostEqual(result['max_vertex_displacement_mm'],math.sqrt(2)*.2)
                self.assertFalse(result['export_ready'])

    def test_rotated_diamond(self):
        result=offset_convex_centerline([(0,-2),(2,0),(0,2),(-2,0)],width_mm=.4,role='outer')
        self.assertAlmostEqual(max(p[0] for p in result['points_mm']),2+math.sqrt(2)*.2)

    def test_concavity_miter_and_hole_collapse_rejected(self):
        cases=[([(0,0),(3,0),(3,1),(1,1),(1,3),(0,3)],.4,'outer'),
               ([(0,0),(1,0),(1,1),(0,1)],1,'hole'),
               ([(0,0),(1,0),(1,1),(0,1)],2,'hole'),
               ([(0,0),(10,0),(0,.01)],.4,'outer')]
        for points,width,role in cases:
            with self.assertRaises(ValueError):offset_convex_centerline(points,width_mm=width,role=role)

    def test_explicit_classification_and_width_required(self):
        square=[(0,0),(1,0),(1,1),(0,1)]
        for args in (dict(width_mm=.4,role='UNKNOWN'),dict(width_mm=0,role='outer'),
                     dict(width_mm=float('nan'),role='outer'),dict(width_mm=.4,role='outer',max_miter_ratio=.5)):
            with self.assertRaises(ValueError):offset_convex_centerline(square,**args)

    def test_physical_outer_and_void_mesh_volume(self):
        outer=offset_convex_centerline([(0,0),(10,0),(10,10),(0,10)],width_mm=.4,role='outer')['points_mm']
        hole=offset_convex_centerline([(3,3),(7,3),(7,7),(3,7)],width_mm=.4,role='hole')['points_mm']
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'physical.stl'
            p.write_bytes(binary_stl(prism_mesh(outer,0,2,holes=[hole])))
            report=inspect_stl(p)
        self.assertAlmostEqual(report['signed_volume'],2*(10.4**2-3.6**2),places=4)
        for key in ('boundary_edges','nonmanifold_edges','duplicate_faces','normal_errors','winding_errors'):
            self.assertEqual(report[key],0,key)


if __name__ == '__main__':unittest.main(verbosity=2)
