"""Streaming path measurements: no geometric repair or inferred layers."""
import math
import unittest
from path_evidence import PathEvidence
from r2_shadow import Shadow

HEADER='G21\nG90\nM83\nG92 E0\nG0 X0 Y0 Z.2\n'


def measure(text):
    state=Shadow()
    paths=PathEvidence()
    for line,raw in enumerate(text.splitlines(),1):
        paths.consume(state.process(raw,line))
    paths.finish('eof')
    return paths.report()


class EvidenceTests(unittest.TestCase):
    def test_nonplanar_path_preserves_height_and_gap(self):
        report=measure(HEADER+';TYPE:Outer wall\nG1 X1 Z.3 E1\nG1 Y1 Z.4 E1\nG1 X0 E1\nG1 Y.06 E1\n')
        p=report['longest_path']
        self.assertEqual(p['segments'],4)
        self.assertAlmostEqual(p['z_span_mm'],.2)
        self.assertAlmostEqual(p['xy_endpoint_gap_mm'],.06)
        self.assertEqual(p['z_up_segments'],2)
        self.assertEqual(p['z_down_segments'],0)
        self.assertEqual(p['end_mm'],(0,.06,.4))
        self.assertFalse(p['closed_3d_exact'])
        self.assertAlmostEqual(p['length_3d_mm'],2*math.sqrt(1.01)+1+.94)
        self.assertEqual(report['counts']['nonplanar_paths'],1)

    def test_exact_planar_closure_is_measurement_only(self):
        p=measure(HEADER+'G1 X1 E1\nG1 Y1 E1\nG1 X0 Y0 E1')['longest_path']
        self.assertTrue(p['closed_3d_exact'])
        self.assertEqual(p['z_span_mm'],0)

    def test_feed_retained_travel_and_unknown_break(self):
        report=measure(HEADER+'G1 X1 E1\nG1 F900\nG1 Y1 E1\nG0 X2\nG1 Y2 E1\nMYSTERY\nG1 X3 E1')
        self.assertEqual(report['counts']['paths'],2)
        self.assertEqual(report['counts']['segments'],3)
        self.assertEqual(report['examples'][0]['segments'],2)

    def test_summary_and_hint_storage_bounded(self):
        text=HEADER
        for i in range(100):
            text+=f';TYPE:hint{i}\nG0 X0 Y0\nG1 X1 E1\n'
        report=measure(text)
        self.assertEqual(report['counts']['paths'],100)
        self.assertEqual(len(report['examples']),12)
        self.assertLessEqual(len(report['paths_by_feature_hint']),65)
        self.assertEqual(sum(report['paths_by_feature_hint'].values()),100)

    def test_feature_change_breaks_and_descent_not_hidden(self):
        report=measure(HEADER+';TYPE:Brim\nG1 X1 Z.1 E1\n;TYPE:Outer wall\nG1 Y1 E1')
        self.assertEqual(report['counts']['paths'],2)
        self.assertEqual(report['examples'][0]['z_down_segments'],1)
        self.assertEqual(report['paths_by_feature_hint'],{'Brim':1,'Outer wall':1})


if __name__ == '__main__': unittest.main(verbosity=2)
