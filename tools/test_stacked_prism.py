"""Stacked layer previews: identical outlines over contiguous Z bands."""
from pathlib import Path
import tempfile
import unittest

from gcode_contours import collect_contours
from contour_preview import stacked_preview_from_report

TWO_LAYERS='''G21
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
G0 X0 Y0 Z.4
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
TWO_LAYERS_SHRUNK=TWO_LAYERS.replace('G0 X0 Y0 Z.4\nG1 X10 E1','G0 X0 Y0 Z.4\nG1 X9 E1')
TWO_LAYERS_TWO_ISLANDS=TWO_LAYERS.replace('EXCLUDE_OBJECT_END NAME=part','''G0 X30 Y0 Z.4
G1 X40 E1
G1 Y10 E1
G1 X30 E1
G1 Y0 E1
G0 X30 Y0 Z.2
G1 X40 E1
G1 Y10 E1
G1 X30 E1
G1 Y0 E1
EXCLUDE_OBJECT_END NAME=part''')


class StackedTests(unittest.TestCase):
    def collect(self,text):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'source.gcode'
            path.write_text(text)
            report=collect_contours(path,klipper_passive=True,seam_gap_mm=0)
            self.assertEqual(path.read_text(),text)
        return report

    def stack(self,report,layers):
        return stacked_preview_from_report(report,layers=layers,width_mm=.4)

    def test_two_identical_layers_stack_into_one_prism(self):
        report=self.collect(TWO_LAYERS)
        self.assertEqual(len(report['path_evidence']['seam_policy']['proposals']),4)
        data,result=self.stack(report,[(0,.2,[(0,(1,))]),(.2,.4,[(2,(3,))])])
        self.assertAlmostEqual(result['audit']['signed_volume'],.4*(10.4**2-3.6**2),places=4)
        self.assertEqual(result['audit']['vertex_connected_components'],1)
        self.assertEqual(result['layer_count'],2)
        self.assertEqual(result['source_planes_mm'],[.2,.4])
        self.assertFalse(result['export_ready'])
        self.assertEqual(result['schema'],'r2-stacked-prism-preview/1')
        self.assertGreater(len(data),84)
        # Provenance of BOTH layers is retained.
        self.assertEqual(result['layers'][0]['groups'][0]['sources'][0]['source_lines'],[7,10])
        self.assertEqual(result['layers'][1]['groups'][0]['sources'][0]['source_lines'],[17,20])

    def test_two_islands_stack_with_two_components(self):
        report=self.collect(TWO_LAYERS_TWO_ISLANDS)
        proposals=len(report['path_evidence']['seam_policy']['proposals'])
        self.assertEqual(proposals,6)
        layer1=[(0,(1,)),(5,())]
        layer2=[(2,(3,)),(4,())]
        data,result=self.stack(report,[(0,.2,layer1),(.2,.4,layer2)])
        self.assertAlmostEqual(result['audit']['signed_volume'],
                               .4*((10.4**2-3.6**2)+10.4**2),places=4)
        self.assertEqual(result['audit']['vertex_connected_components'],2)

    def test_differing_outlines_rejected(self):
        report=self.collect(TWO_LAYERS_SHRUNK)
        with self.assertRaises(ValueError):
            self.stack(report,[(0,.2,[(0,(1,))]),(.2,.4,[(2,(3,))])])

    def test_band_and_plane_validation(self):
        report=self.collect(TWO_LAYERS)
        for layers in ([(0,.3,[(0,(1,))]),(.2,.4,[(2,(3,))])],
                       [(0,.2,[(0,(1,))]),(.3,.4,[(2,(3,))])],
                       [(.2,0,[(0,(1,))])],
                       [(0,.2,[(0,(1,))]),(.2,.4,[(2,(3,))]),(.4,.6,[(0,(1,))])],
                       [(0,.2,[(0,(1,))]),(.2,.4,[(2,),(3,)])],
                       []):
            with self.subTest(layers=layers),self.assertRaises(ValueError):
                self.stack(report,layers)

    def test_selection_validation(self):
        report=self.collect(TWO_LAYERS)
        for layers in ([(0,.2,[(0,(1,))]),(.2,.4,[(0,(3,))])],
                       [(0,.2,[(99,())])],
                       [(0,.2,[])],
                       [(.2,.4,[(2,(3,))]),(0,.2,[(0,(1,))])]):
            with self.subTest(layers=layers),self.assertRaises(ValueError):
                self.stack(report,layers)
        report['complete_scan']=False
        with self.assertRaises(ValueError):self.stack(report,[(0,.2,[(0,(1,))])])


if __name__ == '__main__':unittest.main(verbosity=2)
