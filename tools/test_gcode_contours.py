"""Source-preserving integration tests through the real normalized motion parser."""
import hashlib
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import gcode_contours as gc

HEADER='G21\nG90\nM83\nG92 E0\nG0 X0 Y0 Z0.2\n'
SQUARE='G1 X10 Y0 E1\nG1 X10 Y10 E1\nG1 X0 Y10 E1\nG1 X0 Y0 E1\n'


class IntegrationTests(unittest.TestCase):
    def run_source(self,text, **options):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'input.gcode'
            path.write_text(text)
            before=hashlib.sha256(path.read_bytes()).digest()
            result=gc.collect_contours(path, **options)
            self.assertEqual(hashlib.sha256(path.read_bytes()).digest(),before)
            self.assertEqual([p.name for p in Path(tmp).iterdir()],['input.gcode'])
        self.assertFalse(result['export_ready'])
        return result

    def test_absolute_relative_modes_and_filament(self):
        absolute=HEADER.replace('M83','M82') + 'G1 X10 Y0 E1\nG1 X10 Y10 E2\nG1 X0 Y10 E3\nG1 X0 Y0 E4\n'
        relative=HEADER+'G91\nG1 X10 E1\nG1 Y10 E1\nG1 X-10 E1\nG1 Y-10 E1\n'
        results=[self.run_source(t) for t in (HEADER+SQUARE,absolute,relative)]
        for result in results:
            self.assertEqual(len(result['loops']),1)
            loop=result['loops'][0]
            self.assertEqual(loop['points_mm'],[(0,0),(10,0),(10,10),(0,10)])
            self.assertEqual(loop['commanded_filament_mm'],4)
            self.assertEqual(loop['classification'],'UNKNOWN')
        self.assertEqual(results[0]['loops'][0]['source_lines'],[6,9])

    def test_layers_kept_distinct(self):
        result=self.run_source(HEADER+SQUARE+'G0 Z0.23\n'+SQUARE)
        self.assertEqual([r['z_mm'] for r in result['loops']],[.2,.23])

    def test_unknown_macro_does_not_bridge(self):
        text=HEADER+SQUARE.splitlines()[0]+'\nMYSTERY_MACRO\n'+'\n'.join(SQUARE.splitlines()[1:])+'\n'
        report=self.run_source(text)
        self.assertEqual(report['loops'],[])
        self.assertGreater(report['diagnostics']['unknown_records'],0)

    def test_travel_gap_and_seam_gap_not_snapped(self):
        for text in (HEADER+SQUARE.replace('X0 Y0 E1','X0.01 Y0 E1'),
                     HEADER+SQUARE.replace('G1 X10 Y10 E1','G0 X10 Y10')):
            self.assertEqual(self.run_source(text)['loops'],[])

    def test_spiral_and_missing_modes_rejected(self):
        report=self.run_source(HEADER+SQUARE.replace('X10 Y0 E1','X10 Y0 Z0.3 E1'))
        self.assertEqual(report['loops'],[])
        self.assertEqual(report['diagnostics']['nonplanar_extrusion'],1)
        self.assertEqual(self.run_source(SQUARE)['loops'],[])

    def test_budgets_are_visible(self):
        with patch.object(gc,'MAX_LOOPS',1):
            result=self.run_source(HEADER+SQUARE+'G0 Z.4\n'+SQUARE)
            self.assertFalse(result['complete_scan'])
            self.assertEqual(result['diagnostics']['loop_budget_reached'],1)
        with patch.object(gc,'MAX_LINE',10):
            result=self.run_source(HEADER+SQUARE)
            self.assertFalse(result['complete_scan'])

    def test_klipper_mode_recovers_only_from_explicit_declarations(self):
        text=('START_PRINT T_EXTRUDER=225 T_BED=60\nG90\nG21\nM83\n'
              'SET_PRESSURE_ADVANCE ADVANCE=.2\nG92 E0\nG0 Z.2\n'
              'EXCLUDE_OBJECT_START NAME=part\nG0 X0 Y0\n'+SQUARE)
        self.assertEqual(self.run_source(text)['loops'],[])
        result=self.run_source(text,klipper_passive=True)
        self.assertEqual(len(result['loops']),1)
        self.assertEqual(result['diagnostics']['unknown_records'],1)  # START_PRINT
        self.assertTrue(result['parser_options']['klipper_passive'])

    def test_klipper_mode_does_not_guess_missing_units_or_macros(self):
        for text in (HEADER.replace('G21\n','')+SQUARE,
                     HEADER+'MYSTERY_MACRO\n'+SQUARE):
            self.assertEqual(self.run_source(text,klipper_passive=True)['loops'],[])

    def test_passive_mode_remains_opt_in(self):
        result=self.run_source(HEADER+SQUARE)
        self.assertFalse(result['parser_options']['klipper_passive'])

    def test_feed_only_move_keeps_path_but_retraction_breaks_it(self):
        for inserted,expected in [('G1 F1500',1),('G1 X10 Y0',1),('G1 E-.5',0)]:
            text=HEADER+SQUARE.replace('G1 X10 Y10',inserted+'\nG1 X10 Y10')
            self.assertEqual(len(self.run_source(text)['loops']),expected)

    def test_real_rose_passive_profile_keeps_unknown_start_macro(self):
        import gzip
        import shutil
        fixture=Path(__file__).resolve().parents[1]/'testfixtures/rose_215c_pla.gcode.gz'
        before=hashlib.sha256(fixture.read_bytes()).digest()
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'rose.gcode'
            with gzip.open(fixture,'rb') as src,path.open('wb') as dst:
                shutil.copyfileobj(src,dst)
            original=hashlib.sha256(path.read_bytes()).digest()
            result=gc.collect_contours(path,klipper_passive=True)
            self.assertEqual(hashlib.sha256(path.read_bytes()).digest(),original)
        self.assertEqual(hashlib.sha256(fixture.read_bytes()).digest(),before)
        self.assertTrue(result['complete_scan'])
        self.assertEqual(result['diagnostics']['unknown_records'],1)
        self.assertEqual(result['unknown_examples'][0]['line'],95)
        evidence=result['path_evidence']
        self.assertEqual(evidence['counts']['paths'],708)
        self.assertEqual(evidence['counts']['segments'],137975)
        self.assertEqual(evidence['counts']['nonplanar_paths'],228)
        self.assertEqual(evidence['longest_path']['source_lines'],[39269,39869])
        self.assertAlmostEqual(evidence['longest_path']['z_span_mm'],.2)
        self.assertFalse(evidence['longest_path']['closed_3d_exact'])
        self.assertEqual(evidence['object_diagnostics'],{})
        self.assertEqual(evidence['longest_path']['object_context']['name'],
                         'vaserose_5cm_withbottom.stl_id_0_copy_0')
        # 22 brim + 108 ironing paths: finishing passes are helpers, not model.
        self.assertEqual(evidence['paths_by_role']['helper_hint_excluded'],130)
        self.assertGreater(result['diagnostics']['nonplanar_extrusion'],0)
        self.assertFalse(result['export_ready'])

    def test_bowtie_closed_but_invalid(self):
        result=self.run_source(HEADER+'G1 X10 Y10 E1\nG1 X0 Y10 E1\nG1 X10 Y0 E1\nG1 X0 Y0 E1\n')
        self.assertEqual(result['loops'],[])
        self.assertEqual(result['diagnostics']['invalid_closed_contours'],1)


if __name__ == '__main__': unittest.main(verbosity=2)
