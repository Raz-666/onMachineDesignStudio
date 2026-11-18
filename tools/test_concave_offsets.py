"""Topology-preserving concave offsets with analytic area/volume oracles."""
from pathlib import Path
import tempfile
import unittest
from physical_contours import offset_simple_centerline
from contour_mesh import prism_mesh, binary_stl
from stl_audit import inspect_stl
from contour_preview import preview_from_report
from gcode_contours import collect_contours

L=[(0,0),(3,0),(3,1),(1,1),(1,3),(0,3)]
U=[(0,0),(6,0),(6,6),(4,6),(4,2),(2,2),(2,6),(0,6)]


def area(ring):
    return sum(a[0]*b[1]-b[0]*a[1] for a,b in zip(ring,ring[1:]+ring[:1]))/2


class ConcaveTests(unittest.TestCase):
    def test_L_area_both_roles_and_windings(self):
        for ring in (L,L[::-1]):
            before=ring[:]
            for role,expected in (('outer',7.56),('hole',2.76)):
                result=offset_simple_centerline(ring,width_mm=.4,role=role)
                self.assertAlmostEqual(area(result['points_mm']),expected)
                self.assertEqual(ring,before)

    def test_U_shape_notch_preserved(self):
        shifted=offset_simple_centerline(U,width_mm=.4,role='outer')['points_mm']
        self.assertAlmostEqual(area(shifted),28+32*.2+4*.2**2)
        # Opposite walls of the open notch approach but do not merge.
        self.assertAlmostEqual(shifted[3][0],3.8)
        self.assertAlmostEqual(shifted[6][0],2.2)

    def test_notch_closure_and_arm_collapse_refused(self):
        for ring,width,role in ((U,2,'outer'),(U,3,'outer'),(L,1,'hole'),(L,2,'hole')):
            with self.subTest(width=width,role=role),self.assertRaises(ValueError):
                offset_simple_centerline(ring,width_mm=width,role=role)

    def test_concave_void_mesh(self):
        outer=offset_simple_centerline([(0,0),(10,0),(10,10),(0,10)],width_mm=.4,role='outer')['points_mm']
        hole=offset_simple_centerline([(x+2,y+2) for x,y in L],width_mm=.4,role='hole')['points_mm']
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'concave.stl'
            path.write_bytes(binary_stl(prism_mesh(outer,0,2,holes=[hole])))
            report=inspect_stl(path)
        self.assertAlmostEqual(report['signed_volume'],2*(108.16-2.76),places=4)
        for key in ('boundary_edges','nonmanifold_edges','duplicate_faces','normal_errors','winding_errors'):
            self.assertEqual(report[key],0,key)

    def test_gcode_to_concave_preview(self):
        text='G21\nG90\nM83\nG0 X0 Y0 Z.2\nEXCLUDE_OBJECT_START NAME=L\n;TYPE:Outer wall\n'
        text+=''.join('G1 X%s Y%s E1\n'%p for p in L[1:]+L[:1])
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'L.gcode'
            path.write_text(text)
            report=collect_contours(path,klipper_passive=True,seam_gap_mm=0)
            data,preview=preview_from_report(report,outer_index=0,width_mm=.4,z_bottom=0,z_top=2)
            self.assertEqual(path.read_text(),text)
        self.assertAlmostEqual(preview['audit']['signed_volume'],15.12,places=4)
        self.assertFalse(preview['export_ready'])
        self.assertGreater(len(data),84)


if __name__ == '__main__':unittest.main(verbosity=2)
