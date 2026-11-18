"""End-to-end source G-code -> explicit ring selection -> audited prism preview."""
import copy
from pathlib import Path
import tempfile
import unittest

from gcode_contours import collect_contours
from contour_preview import preview_from_report, main

SOURCE='''G21
G90
M83
G0 X0 Y0 Z.2
EXCLUDE_OBJECT_START NAME=part
;TYPE:Outer wall
G1 X10 E1
G1 Y10 E1
G1 X0 E1
G1 Y0 E1
G0 X3 Y3
G1 X7 E1
G1 Y7 E1
G1 X3 E1
G1 Y3 E1
EXCLUDE_OBJECT_END NAME=part
'''


class PreviewTests(unittest.TestCase):
    def report(self):
        with tempfile.TemporaryDirectory() as directory:
            source=Path(directory)/'source.gcode'
            source.write_text(SOURCE)
            report=collect_contours(source,klipper_passive=True,seam_gap_mm=0)
            self.assertEqual(source.read_text(),SOURCE)
            self.assertEqual(len(list(Path(directory).iterdir())),1)
        self.assertEqual(len(report['path_evidence']['seam_policy']['proposals']),2)
        return report

    def preview(self,report,**kw):
        args=dict(outer_index=0,hole_indices=[1],width_mm=.4,z_bottom=0,z_top=2)
        args.update(kw)
        return preview_from_report(report,**args)

    def test_source_to_preview_volume_and_provenance(self):
        report=self.report()
        original=copy.deepcopy(report)
        data,result=self.preview(report)
        self.assertEqual(report,original)
        self.assertAlmostEqual(result['audit']['signed_volume'],190.4,places=4)
        self.assertEqual(len(data),84+50*result['audit']['triangles'])
        self.assertEqual(result['object_name'],'part')
        self.assertEqual(result['sources'][0]['source_lines'],[7,10])
        self.assertEqual(result['sources'][1]['source_lines'],[12,15])
        self.assertTrue(result['experimental'])
        self.assertFalse(result['export_ready'])

    def test_helper_unknown_object_and_cross_object_rejected(self):
        report=self.report()
        for change in ('helper','unknown','object','plane','tool'):
            candidate=copy.deepcopy(report)
            p=candidate['path_evidence']['seam_policy']['proposals'][1]
            if change=='helper':p['feature_role']='helper_hint_excluded'
            if change=='unknown':p['object_context']['name']=None
            if change=='object':p['object_context']['name']='other'
            if change=='plane':p['points_mm']=[(x,y,z+.2) for x,y,z in p['points_mm']]
            if change=='tool':p['tool']=1
            with self.subTest(change=change),self.assertRaises(ValueError):self.preview(candidate)

    def test_selection_and_incomplete_report_rejected(self):
        report=self.report()
        for args in (dict(outer_index=-1),dict(hole_indices=[0]),dict(hole_indices=[99])):
            with self.assertRaises(ValueError):self.preview(report,**args)
        report['complete_scan']=False
        with self.assertRaises(ValueError):self.preview(report)

    def test_swapped_hole_and_outer_rejected(self):
        with self.assertRaises(ValueError):self.preview(self.report(),outer_index=1,hole_indices=[0])

    def test_cli_creates_provenance_and_refuses_overwrite(self):
        import json
        with tempfile.TemporaryDirectory() as directory:
            source=Path(directory)/'source.gcode'
            output=Path(directory)/'preview.stl'
            source.write_text(SOURCE)
            args=[str(source),'--output',str(output),'--outer-index','0','--hole-index','1',
                  '--width-mm','.4','--z-bottom','0','--z-top','2','--seam-gap-mm','0','--klipper-passive']
            main(args)
            before=output.read_bytes()
            sidecar=Path(str(output)+'.json')
            self.assertFalse(json.loads(sidecar.read_text())['export_ready'])
            with self.assertRaises(SystemExit):main(args)
            self.assertEqual(output.read_bytes(),before)
            self.assertEqual(source.read_text(),SOURCE)

    def test_invalid_height_and_width_rejected(self):
        report=self.report()
        for args in (dict(width_mm=0),dict(z_bottom=2,z_top=1),dict(width_mm=4)):
            with self.assertRaises(ValueError):self.preview(report,**args)


if __name__ == '__main__':unittest.main(verbosity=2)
