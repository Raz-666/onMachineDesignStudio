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
    def run_source(self,text):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'input.gcode'
            path.write_text(text)
            before=hashlib.sha256(path.read_bytes()).digest()
            result=gc.collect_contours(path)
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

    def test_bowtie_closed_but_invalid(self):
        result=self.run_source(HEADER+'G1 X10 Y10 E1\nG1 X0 Y10 E1\nG1 X10 Y0 E1\nG1 X0 Y0 E1\n')
        self.assertEqual(result['loops'],[])
        self.assertEqual(result['diagnostics']['invalid_closed_contours'],1)


if __name__ == '__main__': unittest.main(verbosity=2)
