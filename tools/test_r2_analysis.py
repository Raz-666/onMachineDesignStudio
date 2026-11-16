#!/usr/bin/env python3
"""Offline evidence tests, no machine or generator execution."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock

import r2_analysis as analysis
import r2_offline


class EvidenceTests(unittest.TestCase):
    def analyse(self, text, **kw):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / 'in.gcode'; p.write_text(text)
            return r2_offline.analyse(p, **kw)['evidence']

    def test_closed_loop_geometry_and_provenance(self):
        ev = self.analyse('G21\nG90\nM83\n;LAYER:0\n;TYPE:External perimeter\n'
                          'G1 X0 Y0 Z0.2\nG1 X10 Y0 E1\nG1 X10 Y10 E1\n'
                          'G1 X0 Y10 E1\nG1 X0 Y0 E1\n')
        g = ev['groups'][0]
        self.assertEqual('WALL-OUTER', g['declared_role'])
        self.assertEqual(5, g['role_source']['line'])
        self.assertEqual(4, g['extruding_xy_segments'])
        self.assertAlmostEqual(40, g['extruding_xy_length_mm'])
        self.assertEqual([0, 0, 10, 10], g['bounds_xy_mm'])
        self.assertEqual(1, g['closed_xy_paths'])
        self.assertAlmostEqual(100, g['closed_xy_area_sum_mm2'])
        self.assertEqual(1, ev['layer_evidence']['boundary_count'])

    def test_unknown_state_is_not_a_geometric_guess(self):
        ev = self.analyse('G21\nG90\nM83\nG1 X0 Y0\nG28\nG1 X1 Y1 E1\n')
        self.assertEqual(0, sum(g['extruding_xy_segments'] for g in ev['groups']))
        ev = self.analyse('G21\nG90\nM83\nG1 X0 Y0\nG28\n'
                          'G21\nG90\nM83\nG1 X1 Y1 E1\n')
        self.assertEqual(0, ev['groups'][-1]['extruding_xy_segments'])

    def test_retract_travel_and_reset_split_paths(self):
        ev = self.analyse('G21\nG90\nM83\nG1 X0 Y0\n;TYPE:Perimeter\n'
                          'G1 X1 Y0 E1\nG1 E-1\nG1 X1 Y1\n'
                          'G1 X0 Y1 E1\nG92 X0 Y1\nG1 X0 Y0 E1\n')
        g = next(g for g in ev['groups'] if g['declared_role'] == 'WALL-INNER')
        self.assertEqual(3, g['paths'])
        self.assertEqual(0, g['closed_xy_paths'])
        self.assertEqual(3, g['extruding_xy_segments'])

    def test_explicit_object_spans_and_stable_ids(self):
        s = ('EXCLUDE_OBJECT_DEFINE NAME="a b"\nEXCLUDE_OBJECT_START NAME="a b"\n'
             'G21\nG90\nM83\nG1 X0 Y0\nG1 X1 Y0 E1\nEXCLUDE_OBJECT_END NAME="a b"\n')
        ev = self.analyse(s)
        obj = ev['objects'][0]
        self.assertEqual('a b', obj['name'])
        self.assertEqual((1, 1, 1), (obj['defines'], obj['starts'], obj['ends']))
        self.assertEqual(obj['id'], ev['groups'][0]['object_id'])
        self.assertEqual(obj['id'], self.analyse(s)['objects'][0]['id'])
        self.assertEqual([], ev['warnings'])

    def test_object_mismatch_and_unclosed_warn(self):
        ev = self.analyse('EXCLUDE_OBJECT_START NAME=a\nEXCLUDE_OBJECT_START NAME=b\n'
                          'EXCLUDE_OBJECT_END NAME=a\nEXCLUDE_OBJECT_START NAME=a\n')
        self.assertEqual(3, len(ev['warnings']))

    def test_warning_truncation_is_explicit(self):
        ev = self.analyse('EXCLUDE_OBJECT_END NAME=a\n' * 40)
        self.assertEqual(32, len(ev['warnings']))
        self.assertEqual(40, ev['warning_count'])

    def test_ambiguous_and_unknown_tags_are_not_guessed(self):
        self.assertEqual('AMBIGUOUS', analysis._mapped('SKIN')['role'])
        self.assertEqual(['SURFACE-BOTTOM', 'SURFACE-TOP'], analysis._mapped('SKIN')['alternatives'])
        self.assertEqual('UNKNOWN', analysis._mapped('not-a-role')['role'])
        self.assertEqual('INFILL-SPARSE', analysis._mapped('Sparse infill')['role'])
        self.assertEqual('UNKNOWN', analysis._mapped('InternalInfill')['role'])

    def test_same_role_different_tag_keeps_provenance(self):
        ev = self.analyse('G21\nG90\nM83\nG1 X0 Y0\n;TYPE:Perimeter\n'
                          'G1 X1 E1\n;TYPE:Perimeter\nG1 X2 E1\n')
        self.assertEqual([5, 7], [x['role_source']['line'] for x in ev['groups'] if x['role_source']])

    def test_pattern_is_metadata_not_classification(self):
        ev = self.analyse(';fill_pattern = grid\n;TYPE:Internal infill\n')
        self.assertEqual('grid', ev['pattern_metadata']['fill_pattern']['value'])
        self.assertEqual([], ev['groups'])
        self.assertIn('not geometric pattern recognition', ev['limitations'][2])

    def test_assumptions_not_silent(self):
        s = 'G21\nG90\nM83\nG1 X0 Y0\nMYSTERY\nG1 X1 E1\n'
        default = self.analyse(s)
        hypothetical = self.analyse(s, assumed_passive=['MYSTERY'])
        self.assertEqual(0, sum(x['extruding_xy_segments'] for x in default['groups']))
        self.assertEqual(1, sum(x['extruding_xy_segments'] for x in hypothetical['groups']))

    def test_limits_fail_closed_before_publication(self):
        with tempfile.TemporaryDirectory() as d, mock.patch.object(analysis.Tracker, 'MAX_OBJECTS', 1):
            src = Path(d) / 'in.gcode'; out = Path(d) / 'report.json'
            src.write_text('EXCLUDE_OBJECT_DEFINE NAME=a\nEXCLUDE_OBJECT_DEFINE NAME=b\n')
            with self.assertRaisesRegex(ValueError, 'too many explicit objects'):
                r2_offline.run(src, out, 'report')
            self.assertFalse(out.exists())
            self.assertEqual(2, len(src.read_text().splitlines()))

    def test_mutation_counterchecks_detected(self):
        # A disabled path flush must break the proven closed-loop assertion;
        # treating unknown features as a wall must break the unknown assertion.
        with mock.patch.object(analysis.Tracker, '_end_path', return_value=None):
            with self.assertRaises(AssertionError): self.test_closed_loop_geometry_and_provenance()
        original = analysis._mapped
        def forced_wall(label):
            result = original(label)
            return {'role': 'WALL-INNER'} if result['role'] == 'UNKNOWN' else result
        with mock.patch.object(analysis, '_mapped', side_effect=forced_wall):
            with self.assertRaises(AssertionError): self.test_ambiguous_and_unknown_tags_are_not_guessed()

    def test_overflow_fails_closed(self):
        s = ('G21\nG90\nM83\nG1 X-' + '9'*155 + ' Y0\n'
             'G1 X' + '9'*155 + ' Y' + '9'*155 + ' E1\n'
             'G1 X0 Y0 E1\nG1 X-' + '9'*155 + ' Y0 E1\n')
        with self.assertRaisesRegex(ValueError, 'overflow'):
            self.analyse(s)


if __name__ == '__main__': unittest.main()
