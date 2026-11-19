"""Measured plane spacing and explicit-assumption width estimates."""
import gzip
from pathlib import Path
import shutil
import tempfile
import unittest

from path_evidence import PathEvidence
from gcode_contours import collect_contours
from r2_shadow import Shadow

LAYERS=('G21\nG90\nM83\nG0 X0 Y0 Z.2\n'
        'EXCLUDE_OBJECT_START NAME=part\n;TYPE:Outer wall\n'
        'G1 X10 E1\nG1 Y10 E1\nG1 X0 E1\nG1 Y0 E1\n'
        'G0 X0 Y0 Z.4\n'
        'G1 X10 E1\nG1 Y10 E1\nG1 X0 E1\nG1 Y0 E1\n'
        'G0 X0 Y0 Z.6\n'
        'G1 X10 E1\nG1 Y10 E1\nG1 X0 E1\nG1 Y0 E1\n'
        'EXCLUDE_OBJECT_END NAME=part\n')


class LayerEvidenceTests(unittest.TestCase):
    def evidence(self, **kw):
        state=Shadow(klipper_passive=True)
        paths=PathEvidence(**kw)
        for n,raw in enumerate(LAYERS.splitlines(),1):
            paths.consume(state.process(raw,n))
        paths.finish('eof')
        return paths.report()

    def test_plane_spacing_measured_not_verified(self):
        planes=self.evidence()['plane_statistics']['objects']['part']
        self.assertEqual(planes['plane_count'],3)
        self.assertEqual(planes['z_min_mm'],.2)
        self.assertEqual(planes['z_max_mm'],.6)
        self.assertEqual(planes['successive_differences_mm'],{0.2:2})
        self.assertEqual(planes['most_common_difference_mm'],0.2)
        self.assertIn('not a verified layer height',self.evidence()['plane_statistics']['note'])

    def test_width_estimates_require_explicit_assumption(self):
        self.assertIsNone(self.evidence()['width_estimates'])
        for bad in (0,-1,float('nan')):
            with self.assertRaises(ValueError):
                PathEvidence(assumed_layer_height_mm=bad)
        with self.assertRaises(ValueError):
            PathEvidence(filament_diameter_mm=0)
        result=self.evidence(assumed_layer_height_mm=.2)['width_estimates']
        self.assertFalse(result['measured'])
        self.assertEqual(result['assumed_layer_height_mm'],.2)
        stats=result['by_role']['outer_wall_hint_unverified']
        self.assertEqual(stats['count'],3)
        self.assertAlmostEqual(stats['min_mm'],stats['max_mm'])
        self.assertEqual(len(result['examples']),3)
        self.assertEqual(result['examples'][0]['source_lines'],[7,10])

    def test_unmarked_object_and_nonplanar_paths(self):
        text=('G21\nG90\nM83\nG0 X0 Y0 Z.2\nG1 X10 E1\n'
              'G0 X0 Y0 Z.4\nG1 X10 E1\n'
              'G0 X0 Y0 Z.6\nG1 X10 E1\nG1 Y10 Z.8 E1\n')
        state=Shadow()
        paths=PathEvidence()
        for n,raw in enumerate(text.splitlines(),1):
            paths.consume(state.process(raw,n))
        paths.finish('eof')
        planes=paths.report()['plane_statistics']['objects']['(unmarked)']
        self.assertEqual(planes['plane_count'],2)
        self.assertEqual(planes['successive_differences_mm'],{0.2:1})

    def test_collector_wiring_and_read_only_source(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'layers.gcode'
            path.write_text(LAYERS)
            report=collect_contours(path,klipper_passive=True,assumed_layer_height_mm=.2)
            self.assertEqual(path.read_text(),LAYERS)
        planes=report['path_evidence']['plane_statistics']['objects']['part']
        self.assertEqual(planes['most_common_difference_mm'],0.2)
        widths=report['path_evidence']['width_estimates']
        self.assertEqual(widths['by_role']['outer_wall_hint_unverified']['count'],3)

    def test_real_rose_plane_and_width_evidence(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'rose.gcode'
            with gzip.open('testfixtures/rose_215c_pla.gcode.gz','rb') as source, path.open('wb') as target:
                shutil.copyfileobj(source,target)
            report=collect_contours(path,klipper_passive=True,assumed_layer_height_mm=.2)
        objects=report['path_evidence']['plane_statistics']['objects']
        self.assertEqual(set(objects),{'vaserose_5cm_withbottom.stl_id_0_copy_0',
                                       'vaserose_5cm_withbottom.stl_id_1_copy_0'})
        # Vase mode: only the bottom is planar; the spiral walls are nonplanar
        # and must NOT appear as planes.
        for name,planes in objects.items():
            self.assertEqual(planes['plane_count'],7)
            self.assertEqual(planes['z_min_mm'],.2)
            self.assertEqual(planes['z_max_mm'],24.0)
            self.assertEqual(planes['successive_differences_mm'],{0.2:5,22.8:1})
            self.assertEqual(planes['paths_on_most_common_plane'],95)
        widths=report['path_evidence']['width_estimates']
        outer=widths['by_role']['outer_wall_hint_unverified']
        self.assertEqual(outer['count'],76)
        self.assertAlmostEqual(outer['min_mm'],.3222229238801557)
        self.assertAlmostEqual(outer['max_mm'],.9100746827310143)
        self.assertEqual(widths['by_role']['helper_hint_excluded']['count'],22)
        self.assertEqual(widths['counts']['unsupported_cross_section'],108)
        self.assertFalse(widths['measured'])


if __name__ == '__main__':unittest.main(verbosity=2)
