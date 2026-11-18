"""Bounded retention of long nonplanar paths and real Rose spiral sampling."""
import gzip
from pathlib import Path
import shutil
import tempfile
import unittest

from path_evidence import PathEvidence
from gcode_contours import collect_contours
from r2_shadow import Shadow
from spiral_rings import spiral_rings


def gcode_for_paths(paths):
    """paths: list of (moves, rise_per_move). Feed-only continuity keeps chains."""
    text=['G21','G90','M83','EXCLUDE_OBJECT_START NAME=part']
    z=0.2
    for moves,rise in paths:
        text.append('G0 X0 Y0 Z%.3f'%z)
        for k in range(moves):
            text.append('G1 X%d Y%d%s E1'%(k+1,(k+1)%3,
                         (' Z%.3f'%(z+rise*(k+1))) if rise else ''))
        z+=1.0
    text.append('EXCLUDE_OBJECT_END NAME=part')
    return '\n'.join(text)+'\n'


class RetentionTests(unittest.TestCase):
    def collect(self,paths,**kw):
        state=Shadow(klipper_passive=True)
        evidence=PathEvidence(**kw)
        for n,raw in enumerate(gcode_for_paths(paths).splitlines(),1):
            evidence.consume(state.process(raw,n))
        evidence.finish('eof')
        return evidence.report()

    def test_retention_keeps_longest_and_is_opt_in(self):
        report=self.collect([(9,.001),(19,.001),(29,.001),(39,.001),(49,.001),(59,.001),(9,0)],
                            retain_nonplanar_points=True)
        retention=report['nonplanar_retention']
        self.assertTrue(retention['enabled'])
        self.assertEqual(retention['counts'],{'retained_paths':4,'evicted_shorter_paths':2})
        self.assertEqual(sorted(e['point_count'] for e in report['nonplanar_point_sets']),
                         [30,40,50,60])
        self.assertTrue(all(e['points_mm'][0][2] != e['points_mm'][-1][2]
                            for e in report['nonplanar_point_sets']))
        # The planar path is never retained.
        self.assertTrue(all(e['segments'] != 9 or e['point_count'] != 10
                            for e in report['nonplanar_point_sets']))

    def test_overflow_and_default_off(self):
        report=self.collect([(1025,.001),(5,.001)],retain_nonplanar_points=True)
        self.assertEqual(report['nonplanar_retention']['counts'],
                         {'retained_paths':1,'point_overflow_paths':1})
        self.assertEqual([e['point_count'] for e in report['nonplanar_point_sets']],[6])
        report=self.collect([(5,.001),(9,0)])
        self.assertFalse(report['nonplanar_retention']['enabled'])
        self.assertEqual(report['nonplanar_point_sets'],[])

    def test_collector_wiring(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'paths.gcode'
            text=gcode_for_paths([(9,.001),(19,.001),(9,0)])
            path.write_text(text)
            report=collect_contours(path,klipper_passive=True,retain_nonplanar_points=True)
            self.assertEqual(path.read_text(),text)
        sets=report['path_evidence']['nonplanar_point_sets']
        self.assertEqual(sorted(e['point_count'] for e in sets),[10,20])

    def test_real_rose_longest_paths_and_ring(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'rose.gcode'
            with gzip.open('testfixtures/rose_215c_pla.gcode.gz','rb') as source, path.open('wb') as target:
                shutil.copyfileobj(source,target)
            report=collect_contours(path,klipper_passive=True,retain_nonplanar_points=True)
        evidence=report['path_evidence']
        self.assertEqual(evidence['nonplanar_retention']['counts'],
                         {'retained_paths':4,'evicted_shorter_paths':33,'skipped_shorter_paths':191})
        sets=evidence['nonplanar_point_sets']
        self.assertEqual(sorted(e['point_count'] for e in sets),[599,599,602,602])
        self.assertEqual(sorted(e['source_lines'] for e in sets),
                         [[30138,30735],[34369,34967],[39269,39869],[117378,117978]])
        longest=[e for e in sets if e['source_lines']==[39269,39869]][0]
        self.assertEqual(longest['point_count'],602)
        # Explicit assumption: pitch 0.2 equals one full wall traversal (the
        # path returns to its start XY within 0.036 mm while rising 0.2 mm).
        result=spiral_rings(longest['points_mm'],pitch_mm=.2,samples_per_revolution=64)
        self.assertEqual(result['ring_count'],1)
        ring=result['rings'][0]
        self.assertEqual(ring['samples'],64)
        # The float height span (10.4-10.2) marginally exceeds the 0.2 pitch,
        # so one extra sample lands below the end height and is dropped.
        self.assertEqual(result['dropped_incomplete_ring_samples'],1)
        self.assertAlmostEqual(ring['z_band_mm'][0],10.2)
        self.assertAlmostEqual(ring['z_band_mm'][1],10.396875)
        self.assertFalse(result['export_ready'])
        # Coarser sampling aliases the concave flower outline into a
        # self-intersecting polygon and is refused instead of repaired.
        with self.assertRaises(ValueError):
            spiral_rings(longest['points_mm'],pitch_mm=.2,samples_per_revolution=32)


if __name__ == '__main__':unittest.main(verbosity=2)
