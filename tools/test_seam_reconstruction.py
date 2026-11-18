"""Seam proposal contract: explicit budget, unchanged points, no Z flattening."""
import unittest
from seam_reconstruction import close_planar_seam
from path_evidence import PathEvidence
from r2_shadow import Shadow


class SeamTests(unittest.TestCase):
    def test_missing_edge_added_without_moving_vertices(self):
        points=[(0,0,.2),(2,0,.2),(2,2,.2),(0,2,.2),(0,.06,.2)]
        # Collinear final corner is deliberately rejected by contour validator;
        # use a noncollinear near-seam endpoint for this valid test polygon.
        points[-1]=(.01,.06,.2)
        before=points[:]
        report=close_planar_seam(points,max_gap_mm=.1)
        self.assertEqual(points,before)
        self.assertEqual(report['points_mm'][:-1],points)
        self.assertEqual(report['points_mm'][-1],points[0])
        self.assertAlmostEqual(report['added_edge_mm'],(.01**2+.06**2)**.5)
        self.assertFalse(report['export_ready'])

    def test_already_closed_no_added_edge(self):
        points=[(0,0,0),(1,0,0),(0,1,0),(0,0,0)]
        result=close_planar_seam(points,max_gap_mm=0)
        self.assertEqual(result['points_mm'],points)
        self.assertEqual(result['operation'],'none')

    def test_nonplanar_and_large_gap_refused(self):
        for points,budget in [([(0,0,0),(1,0,0),(0,.01,.1)],.1),
                              ([(0,0,0),(1,0,0),(0,1,0)],.1)]:
            with self.assertRaises(ValueError):close_planar_seam(points,max_gap_mm=budget)
        for budget in (-1,float('nan'),float('inf')):
            with self.assertRaises(ValueError):close_planar_seam([(0,0,0)]*3,max_gap_mm=budget)

    def test_self_crossing_closure_refused(self):
        points=[(0,0,0),(2,2,0),(0,2,0),(2,0,0)]
        with self.assertRaises(ValueError):close_planar_seam(points,max_gap_mm=2)

    def test_proposal_storage_bounded(self):
        state=Shadow()
        paths=PathEvidence(seam_gap_mm=.1)
        text='G21\nG90\nM83\nG0 X0 Y0 Z.2\n'
        for _ in range(40):
            text+='G0 X0 Y0\nG1 X2 E1\nG1 Y2 E1\nG1 X0 Y2 E1\nG1 X.01 Y.06 E1\n'
        for line,raw in enumerate(text.splitlines(),1):paths.consume(state.process(raw,line))
        paths.finish('eof')
        policy=paths.report()['seam_policy']
        self.assertEqual(policy['counts']['accepted_proposals'],40)
        self.assertEqual(len(policy['proposals']),32)

    def test_optional_stream_policy_and_provenance(self):
        text='G21\nG90\nM83\nG0 X0 Y0 Z.2\n;TYPE:Brim\nG1 X2 E1\nG1 Y2 E1\nG1 X0 Y2 E1\nG1 X.01 Y.06 E1'
        for enabled in (False,True):
            state=Shadow()
            paths=PathEvidence(seam_gap_mm=.1 if enabled else None)
            for line,raw in enumerate(text.splitlines(),1):paths.consume(state.process(raw,line))
            paths.finish('eof')
            policy=paths.report()['seam_policy']
            self.assertEqual(len(policy['proposals']),1 if enabled else 0)
            if enabled:
                proposal=policy['proposals'][0]
                self.assertEqual(proposal['feature_hint'],'Brim')
                self.assertEqual(proposal['source_lines'],[6,9])
                self.assertFalse(proposal['export_ready'])


if __name__ == '__main__':unittest.main(verbosity=2)
