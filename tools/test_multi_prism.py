"""Multi-island layer previews: disjoint ring groups become separate shells."""
from pathlib import Path
import tempfile
import unittest

from gcode_contours import collect_contours
from contour_preview import preview_from_report, main

ISLANDS='''G21
G90
M83
G0 X0 Y0 Z.2
EXCLUDE_OBJECT_START NAME=part
;TYPE:Outer wall
G1 X10 E1
G1 Y10 E1
G1 X0 E1
G1 Y0 E1
G0 X30 Y0
G1 X40 E1
G1 Y10 E1
G1 X30 E1
G1 Y0 E1
G0 X3 Y3
G1 X7 E1
G1 Y7 E1
G1 X3 E1
G1 Y3 E1
EXCLUDE_OBJECT_END NAME=part
'''
OVERLAP='''G21
G90
M83
G0 X0 Y0 Z.2
EXCLUDE_OBJECT_START NAME=part
;TYPE:Outer wall
G1 X10 E1
G1 Y10 E1
G1 X0 E1
G1 Y0 E1
G0 X5 Y0
G1 X15 E1
G1 Y10 E1
G1 X5 E1
G1 Y0 E1
EXCLUDE_OBJECT_END NAME=part
'''
TWO_OBJECTS='''G21
G90
M83
G0 X0 Y0 Z.2
EXCLUDE_OBJECT_START NAME=a
;TYPE:Outer wall
G1 X10 E1
G1 Y10 E1
G1 X0 E1
G1 Y0 E1
EXCLUDE_OBJECT_END NAME=a
EXCLUDE_OBJECT_START NAME=b
;TYPE:Outer wall
G0 X20 Y0
G1 X30 E1
G1 Y10 E1
G1 X20 E1
G1 Y0 E1
EXCLUDE_OBJECT_END NAME=b
'''
SPLIT_PLANES='''G21
G90
M83
G0 X0 Y0 Z.2
EXCLUDE_OBJECT_START NAME=a
;TYPE:Outer wall
G1 X10 E1
G1 Y10 E1
G1 X0 E1
G1 Y0 E1
G0 Z.3
G0 X20 Y0
G1 X30 E1
G1 Y10 E1
G1 X20 E1
G1 Y0 E1
EXCLUDE_OBJECT_END NAME=a
'''


class MultiPrismTests(unittest.TestCase):
    def collect(self,text):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'source.gcode'
            path.write_text(text)
            report=collect_contours(path,klipper_passive=True,seam_gap_mm=0)
            self.assertEqual(path.read_text(),text)
        return report

    def preview(self,report,groups):
        return preview_from_report(report,groups=groups,width_mm=.4,z_bottom=0,z_top=2)

    def test_two_islands_and_island_with_hole(self):
        report=self.collect(ISLANDS)
        self.assertEqual(len(report['path_evidence']['seam_policy']['proposals']),3)
        data,result=self.preview(report,[(0,()),(1,())])
        self.assertAlmostEqual(result['audit']['signed_volume'],2*2*(10.4**2),places=4)
        self.assertEqual(result['audit']['vertex_connected_components'],2)
        self.assertEqual(result['expected_components'],2)
        self.assertFalse(result['export_ready'])
        data,result=self.preview(report,[(0,(2,)),(1,())])
        self.assertAlmostEqual(result['audit']['signed_volume'],2*(10.4**2-3.6**2)+2*10.4**2,places=4)
        self.assertEqual(result['audit']['vertex_connected_components'],2)
        self.assertEqual(result['object_names'],['part','part'])
        self.assertGreater(len(data),84)

    def test_overlapping_islands_rejected(self):
        report=self.collect(OVERLAP)
        with self.assertRaises(ValueError):self.preview(report,[(0,()),(1,())])

    def test_two_named_objects_allowed_and_recorded(self):
        result=self.preview(self.collect(TWO_OBJECTS),[(0,()),(1,())])[1]
        self.assertEqual(result['object_names'],['a','b'])
        self.assertEqual({g['object_name'] for g in result['groups']},{'a','b'})

    def test_split_planes_rejected(self):
        with self.assertRaises(ValueError):self.preview(self.collect(SPLIT_PLANES),[(0,()),(1,())])

    def test_group_selection_validation(self):
        report=self.collect(ISLANDS)
        for groups in ([],[(0,()),(0,())],[(99,())],[(0,(99,))]):
            with self.subTest(groups=groups),self.assertRaises(ValueError):
                self.preview(report,groups)
        with self.assertRaises(ValueError):
            preview_from_report(report,outer_index=0,groups=[(1,())],width_mm=.4,
                                z_bottom=0,z_top=2)
        with self.assertRaises(ValueError):
            preview_from_report(report,width_mm=.4,z_bottom=0,z_top=2)

    def test_cli_group_selection_and_sidecar(self):
        import json
        with tempfile.TemporaryDirectory() as directory:
            source=Path(directory)/'source.gcode'
            output=Path(directory)/'preview.stl'
            source.write_text(ISLANDS)
            args=[str(source),'--output',str(output),'--group','0:2','--group','1',
                  '--width-mm','.4','--z-bottom','0','--z-top','2','--seam-gap-mm','0',
                  '--klipper-passive']
            main(args)
            sidecar=Path(str(output)+'.json')
            summary=json.loads(sidecar.read_text())
            self.assertEqual(summary['expected_components'],2)
            self.assertEqual(summary['selection_indices'],[[0,[2]],[1,[]]])
            self.assertFalse(summary['export_ready'])
            before=output.read_bytes()
            with self.assertRaises(SystemExit):main(args)
            self.assertEqual(output.read_bytes(),before)
            with self.assertRaises(SystemExit):
                main(args+['--outer-index','0'])


class MixedMarkerTests(unittest.TestCase):
    def test_hole_from_other_object_rejected(self):
        from contour_preview import prism_set_preview
        text=('G21\nG90\nM83\nG0 X0 Y0 Z.2\n'
              'EXCLUDE_OBJECT_START NAME=a\n;TYPE:Outer wall\n'
              'G1 X10 E1\nG1 Y10 E1\nG1 X0 E1\nG1 Y0 E1\n'
              'EXCLUDE_OBJECT_END NAME=a\nEXCLUDE_OBJECT_START NAME=b\n'
              'G0 X3 Y3\nG1 X7 E1\nG1 Y7 E1\nG1 X3 E1\nG1 Y3 E1\n'
              'EXCLUDE_OBJECT_END NAME=b\n')
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'source.gcode'
            path.write_text(text)
            report=collect_contours(path,klipper_passive=True,seam_gap_mm=0)
        proposals=report['path_evidence']['seam_policy']['proposals']
        self.assertEqual([p['object_context']['name'] for p in proposals],['a','b'])
        with self.assertRaises(ValueError):
            prism_set_preview([(proposals[0],[proposals[1]])],width_mm=.4,z_bottom=0,z_top=2)


if __name__ == '__main__':unittest.main(verbosity=2)
