"""Bead-width evidence over whole runs: stadium oracle plus the full Rose.

The Rose result replaces the old 0.24 mm lower-bound assumption with hard
G-code evidence: the wall is a uniform 0.6 mm single-wall bead. The
full-run width audit documents that NO uniform width above zero is
accepted by the vertex-normal offset model on every ring — the old
"w<=0.24 all rings" claim was an artefact of a four-ring window.
"""
import gzip
import math
from pathlib import Path
import shutil
import tempfile
import unittest

from bead_evidence import (collect_chained_run, run_width_evidence,
                           wall_width_audit)
from test_vase_closure import helix_run, rose_run
from wall_run import sample_wall_run

FILAMENT_AREA=math.pi*1.75**2/4


def stadium_area(width_mm,layer_height_mm):
    return layer_height_mm*(width_mm-layer_height_mm)+math.pi*layer_height_mm**2/4


class WidthEvidenceTests(unittest.TestCase):
    def test_stadium_roundtrip_recovers_width(self):
        # Filament generated from a known width must be recovered exactly.
        width=0.42
        lengths=[241.7,238.3,256.1,19.5]
        filaments=[L*stadium_area(width,0.2)/FILAMENT_AREA for L in lengths]
        evidence=run_width_evidence(filaments,lengths,layer_height_mm=0.2)
        self.assertEqual(evidence['paths'],4)
        self.assertEqual(evidence['estimated_paths'],4)
        self.assertEqual(evidence['unsupported_indices'],[])
        for value in (evidence['min_mm'],evidence['median_mm'],evidence['max_mm']):
            self.assertAlmostEqual(value,width,places=9)
        self.assertAlmostEqual(evidence['commanded_filament_mm'],math.fsum(filaments),places=9)
        self.assertAlmostEqual(evidence['commanded_volume_mm3'],
                               math.fsum(lengths)*stadium_area(width,0.2),places=9)

    def test_unsupported_cross_section_listed(self):
        # Far too little filament: stadium cannot support the layer height.
        evidence=run_width_evidence([0.001,10.0],[100.0,200.0],layer_height_mm=0.2)
        self.assertEqual(evidence['unsupported_indices'],[0])
        self.assertEqual(evidence['estimated_paths'],1)
        self.assertAlmostEqual(evidence['max_mm'],0.644241,places=5)

    def test_validation_rejections(self):
        for filaments,lengths,kwargs in (([1.0],[],dict(layer_height_mm=.2)),
                                         ([],[1.0],dict(layer_height_mm=.2)),
                                         ([1.0],[1.0],dict(layer_height_mm=0)),
                                         ([1.0],[1.0],dict(layer_height_mm=-.2)),
                                         ([0.0],[1.0],dict(layer_height_mm=.2)),
                                         ([1.0],[math.inf],dict(layer_height_mm=.2)),
                                         ([1.0],[1.0],dict(layer_height_mm=.2,
                                                           filament_diameter_mm=0))):
            with self.subTest(filaments=filaments,lengths=lengths,kwargs=kwargs):
                self.assertRaises(ValueError,run_width_evidence,
                                  filaments,lengths,**kwargs)


class CollectChainedRunTests(unittest.TestCase):
    def test_argument_validation(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'empty.gcode'
            path.write_text('')
            for kwargs in (dict(first_line=0),dict(first_line=1.5),
                           dict(first_line=1,max_join_gap_mm=0),
                           dict(first_line=1,max_join_gap_mm=float('nan'))):
                with self.subTest(kwargs=kwargs):
                    self.assertRaises(ValueError,collect_chained_run,path,**kwargs)

    def test_rose_run_matches_reference_chain(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'rose.gcode'
            with gzip.open('testfixtures/rose_215c_pla.gcode.gz','rb') as source, path.open('wb') as target:
                shutil.copyfileobj(source,target)
            paths,filaments,lengths=collect_chained_run(path,first_line=13404)
        self.assertEqual(paths,rose_run())
        self.assertEqual(len(paths),115)
        self.assertEqual(sum(len(p) for p in paths),62916)
        self.assertEqual(len(filaments),115)
        self.assertEqual(len(lengths),115)
        self.assertTrue(all(f>0 and l>0 for f,l in zip(filaments,lengths)))


class WallWidthAuditTests(unittest.TestCase):
    def test_cylinder_audit_accepts_and_collapses(self):
        rings=sample_wall_run(helix_run(),pitch_mm=1/16,samples_per_revolution=8)['rings']
        audit=wall_width_audit(rings,width_mm=0.4)
        self.assertEqual(audit['outer']['accepted'],len(rings))
        self.assertEqual(audit['outer']['rejected'],0)
        self.assertEqual(audit['inner']['accepted'],len(rings))
        self.assertEqual(audit['inner']['rejected'],0)
        # Offsetting a radius-10 circle inward by 12.5 mm inverts it.
        collapsed=wall_width_audit(rings,width_mm=25.0)
        self.assertEqual(collapsed['inner']['rejected'],len(rings))
        self.assertEqual(collapsed['outer']['rejected'],0)
        self.assertTrue(collapsed['inner']['first_reason'])

    def test_audit_validation(self):
        rings=sample_wall_run(helix_run(),pitch_mm=1/16,samples_per_revolution=8)['rings']
        self.assertRaises(ValueError,wall_width_audit,[],width_mm=1.0)
        for width in (0,-.4,float('inf')):
            self.assertRaises(ValueError,wall_width_audit,rings,width_mm=width)


class RealRoseWidthEvidenceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'rose.gcode'
            with gzip.open('testfixtures/rose_215c_pla.gcode.gz','rb') as source, path.open('wb') as target:
                shutil.copyfileobj(source,target)
            cls.paths,cls.filaments,cls.lengths=collect_chained_run(path,first_line=13404)
        cls.evidence=run_width_evidence(cls.filaments,cls.lengths,layer_height_mm=0.2)
        cls.rings=sample_wall_run(cls.paths,pitch_mm=.2,samples_per_revolution=96,
                                  max_gap_mm=.1)['rings']

    def test_wall_is_uniform_six_tenths_bead(self):
        evidence=self.evidence
        self.assertEqual(evidence['paths'],115)
        self.assertEqual(evidence['estimated_paths'],115)
        self.assertEqual(evidence['unsupported_indices'],[])
        wall=evidence['width_mm'][1:-1]
        self.assertEqual(len(wall),113)
        for width in wall:
            self.assertGreater(width,0.5998)
            self.assertLess(width,0.6001)
        self.assertAlmostEqual(evidence['median_mm'],0.599976,places=5)
        # The bottom closing loop and the top rim loop run noticeably thinner.
        self.assertAlmostEqual(evidence['width_mm'][0],0.322223,places=6)
        self.assertAlmostEqual(evidence['width_mm'][-1],0.320943,places=6)
        self.assertAlmostEqual(evidence['min_mm'],0.320943,places=6)
        self.assertAlmostEqual(evidence['commanded_filament_mm'],1499.7931,places=3)
        self.assertAlmostEqual(evidence['commanded_volume_mm3'],3607.4253,places=3)

    def test_evidence_width_not_representable_by_offsets(self):
        audit=wall_width_audit(self.rings,width_mm=0.6)
        self.assertEqual(audit['outer'],dict(accepted=54,rejected=60,
                                             rejected_ring_indices=audit['outer']['rejected_ring_indices'],
                                             rejection_reasons={'offset changes corner orientation':60},
                                             first_reason='offset changes corner orientation'))
        self.assertEqual(audit['inner']['accepted'],0)
        self.assertEqual(audit['inner']['rejected'],114)
        self.assertEqual(audit['inner']['rejection_reasons'],
                         {'boundary self-intersects or touches itself':114})

    def test_no_uniform_width_zero_rejections(self):
        # Near-collinear sample vertices reject at ANY width: no uniform
        # width above zero is accepted by every ring on both sides.
        audit=wall_width_audit(self.rings,width_mm=0.02)
        self.assertEqual(audit['outer']['rejected_ring_indices'],[106,109,110])
        self.assertEqual(audit['inner']['rejected_ring_indices'],[37,88])
        self.assertEqual(audit['outer']['rejection_reasons'],
                         {'offset changes corner orientation':3})
        self.assertEqual(audit['inner']['rejection_reasons'],
                         {'offset changes corner orientation':2})

    def test_old_window_assumption_corrected(self):
        # "w<=0.24 accepted on all rings" held only for a four-ring window;
        # on the full 114-ring run 0.24 mm is rejected on both sides.
        audit=wall_width_audit(self.rings,width_mm=0.24)
        self.assertEqual(audit['outer']['accepted'],86)
        self.assertEqual(audit['outer']['rejected'],28)
        self.assertEqual(audit['inner']['accepted'],69)
        self.assertEqual(audit['inner']['rejected'],45)


if __name__ == '__main__':unittest.main(verbosity=2)
