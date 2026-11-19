#!/usr/bin/env python3
"""Unit and CLI tests of the offline shadow tracer. No hardware or watcher."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

import r2_shadow as sh


class ShadowTests(unittest.TestCase):
    def setUp(self):
        self.s = sh.Shadow(assume_klipper_defaults=True)
        self.line = 0

    def feed(self, line):
        self.line += 1
        return self.s.process(line + '\n', self.line)

    def test_relative_xyz_accumulates_and_e_relative(self):
        self.feed('G90'); self.feed('M83'); self.feed('G1 X0 Y0 Z0.2')
        self.feed('G91')
        a = self.feed('G1 X10 E0.5 F1200')
        b = self.feed('G1 X10 E-0.2')
        self.assertEqual((0.0, 10.0, 20.0), (a['start_mm']['X'], a['end_mm']['X'], b['end_mm']['X']))
        self.assertEqual((0.5, -0.2), (a['commanded_e_delta_mm'], b['commanded_e_delta_mm']))
        self.assertEqual(1200, b['feed_mm_min'])

    def test_m82_g92_and_known_previous_e(self):
        self.feed('M82'); self.feed('G92 E0')
        first = self.feed('G1 X10 E1')
        self.feed('G92 E0')
        second = self.feed('G1 X20 E0.5')
        self.assertEqual(1, first['commanded_e_delta_mm'])
        self.assertEqual(0.5, second['commanded_e_delta_mm'])
        self.assertEqual(10, second['start_mm']['X'])

    def test_absolute_e_unknown_initial_then_known(self):
        first = self.feed('G1 X1 E8')
        second = self.feed('G1 X2 E8.5')
        self.assertIsNone(first['commanded_e_delta_mm'])
        self.assertEqual(0.5, second['commanded_e_delta_mm'])
        self.assertEqual(0, self.feed('G1 X3')['commanded_e_delta_mm'])

    def test_g92_is_coordinate_reset_not_motion(self):
        self.feed('G1 X100')
        reset = self.feed('G92 X0 E0')
        move = self.feed('G1 X10 E1')
        self.assertEqual('coordinate_reset', reset['kind'])
        self.assertEqual(0, move['start_mm']['X'])
        self.assertIn('physical origin not inferred', reset['reason'])

    def test_inch_and_mm_conversions(self):
        self.s = sh.Shadow(assume_klipper_defaults=True, dialect='generic')
        self.feed('G20'); self.feed('M83'); self.feed('G92 X0 E0')
        move = self.feed('G1 X1 E.1 F60')
        self.assertAlmostEqual(25.4, move['end_mm']['X'])
        self.assertAlmostEqual(2.54, move['commanded_e_delta_mm'])
        self.assertAlmostEqual(1524, move['feed_mm_min'])
        self.feed('G21')
        self.assertEqual(30, self.feed('G1 X30')['end_mm']['X'])

    def test_klipper_g91_forces_e_relative_even_after_m82(self):
        self.feed('G92 E0'); self.feed('M82'); self.feed('G91')
        a = self.feed('G1 E1')
        b = self.feed('G1 E1')
        self.assertEqual((1, 1), (a['commanded_e_delta_mm'], b['commanded_e_delta_mm']))
        self.assertEqual('relative', b['e_mode'])
        self.feed('G90')
        self.assertEqual(1, self.feed('G1 E3')['commanded_e_delta_mm'])

    def test_g20_klipper_rejected_generic_explicit(self):
        record = self.feed('G20')
        self.assertEqual('unknown', record['kind'])
        self.assertIn('Klipper rejects G20', record['reason'])
        self.assertIsNone(self.s.units_mm)
        generic = sh.Shadow(assume_klipper_defaults=True, dialect='generic')
        self.assertEqual('mode', generic.process('G20\n', 1)['kind'])
        self.assertEqual(25.4, generic.units_mm)

    def test_passive_macro_requires_explicit_assumption_and_is_labelled(self):
        unsafe = sh.Shadow(assume_klipper_defaults=True)
        unsafe.process('G1 X1 Y2 Z3\n', 1)
        self.assertEqual('unknown', unsafe.process('LAYER_MARK\n', 2)['kind'])
        self.assertIsNone(unsafe.position['X'])
        state = sh.Shadow(assume_klipper_defaults=True, assumed_passive=['layer_mark'])
        state.process('G1 X1 Y2 Z3\n', 1)
        rec = state.process('LAYER_MARK\n', 2)
        self.assertEqual('assumed_passive', rec['kind'])
        self.assertIn('not verified', rec['reason'])
        self.assertEqual(1, state.process('G1 X2\n', 3)['start_mm']['X'])
        self.assertEqual('unknown', state.process('OTHER_MACRO\n', 4)['kind'])

    def test_core_command_cannot_be_reclassified_as_passive(self):
        for name in ('G1', 'G90', 'M83', 'G92', 'bad name', 'G1X1'):
            with self.subTest(name=name), self.assertRaises(ValueError):
                sh.Shadow(assumed_passive=[name])

    def test_arcs_unknown_then_explicit_modes_recover(self):
        self.feed('G1 X10 Y5 E2')
        self.assertEqual('unknown', self.feed('G2 X20 Y10 I5 J5')['kind'])
        self.assertEqual('unknown', self.feed('G1 X30 E3')['kind'])
        self.feed('G21'); self.feed('G90'); self.feed('M82'); self.feed('G92 E0')
        move = self.feed('G1 X30 E3')
        self.assertIsNone(move['start_mm']['X'])
        self.assertEqual(30, move['end_mm']['X'])
        self.assertEqual(3, move['commanded_e_delta_mm'])

    def test_unknown_macro_tool_and_homing_invalidate(self):
        for event in ('MY_MACRO', 'T1', 'G10', 'G90.1'):
            with self.subTest(event=event):
                state = sh.Shadow(assume_klipper_defaults=True)
                state.process('G1 X10 E2\n', 1)
                record = state.process(event+'\n', 2)
                self.assertIn(record['kind'], ('unknown', 'tool'))
                self.assertIsNone(state.position['X'])
                self.assertIsNone(state.e)
                self.assertIsNone(state.units_mm)
                self.assertEqual('unknown', state.process('G1 X20 E3\n', 3)['kind'])

    def test_homing_preserves_modal_state(self):
        # G28 homes axes (logical coordinates unknown) but never changes
        # G90/G91/M82/M83, units, feed or the logical E coordinate.
        state = sh.Shadow(assume_klipper_defaults=True)
        state.process('M83\n', 1)
        state.process('G92 E0\n', 2)
        state.process('G1 X10 Y10 Z5 E2 F1500\n', 3)
        record = state.process('G28\n', 4)
        self.assertEqual('home', record['kind'])
        self.assertEqual(['X', 'Y', 'Z'], record['homed_axes'])
        for axis in 'XYZ':
            self.assertIsNone(state.position[axis])
        self.assertEqual(1.0, state.units_mm)
        self.assertTrue(state.xyz_absolute)
        self.assertFalse(state.e_absolute)
        self.assertEqual(2, state.e)
        move = state.process('G1 X20 E3\n', 5)
        self.assertEqual('move', move['kind'])
        self.assertEqual(20, move['end_mm']['X'])
        self.assertIsNone(move['start_mm']['Z'])
        self.assertIsNone(move['end_mm']['Z'])

    def test_homing_axis_selectors_and_marlin_w_flag(self):
        state = sh.Shadow(assume_klipper_defaults=True)
        state.process('G1 X10 Y10 Z5\n', 1)
        self.assertEqual(['X'], state.process('G28 X\n', 2)['homed_axes'])
        self.assertIsNone(state.position['X'])
        self.assertEqual(10, state.position['Y'])
        self.assertEqual(5, state.position['Z'])
        state.process('G1 X4\n', 3)
        record = state.process('G28 W  ; home all without mesh bed level\n', 4)
        self.assertEqual('home', record['kind'])
        self.assertEqual(['X', 'Y', 'Z'], record['homed_axes'])
        self.assertEqual('move', state.process('G1 X1 Y2 Z3\n', 5)['kind'])
        for token in ('G28 Q1', 'G28 X X', 'G28.1'):
            with self.subTest(token=token):
                broken = sh.Shadow(assume_klipper_defaults=True)
                broken.process('G1 X10\n', 1)
                self.assertEqual('unknown', broken.process(token+'\n', 2)['kind'])
                self.assertIsNone(broken.units_mm)

    def test_syntax_duplicates_nonfinite_and_invalid_feed_invalidate(self):
        for event in ('G1 X1 X2', 'G1 Xnope', 'G1 X1 *123', 'N10 G1 X1',
                      'G1 X'+'9'*400, 'G1 F0', 'G1 X1 A2', 'G4 P1 G28'):
            with self.subTest(event=event):
                state = sh.Shadow()
                self.assertEqual('unknown', state.process(event+'\n', 1)['kind'])
                self.assertIsNone(state.units_mm)

    def test_numeric_overflow_invalidates_instead_of_inf(self):
        self.s = sh.Shadow(assume_klipper_defaults=True, dialect='generic')
        value = '9' * 307
        self.feed('G20')
        result = self.feed('G1 X'+value)
        self.assertEqual('unknown', result['kind'])
        self.assertIn('overflow', result['reason'])
        self.assertIsNone(self.s.position['X'])

    def test_compact_arguments_comments_and_raw_are_preserved(self):
        record = self.s.process('g1x1.5y-2e.1f1800 ; wall\r\n', 42)
        self.assertEqual('move', record['kind'])
        self.assertEqual('g1x1.5y-2e.1f1800 ; wall\r\n', record['raw'])
        self.assertEqual(' wall', record['comment'])
        self.assertEqual((1.5, -2.0), (record['end_mm']['X'], record['end_mm']['Y']))
        blank = self.s.process(';TYPE:Outer wall\n', 43)
        self.assertEqual(('comment', 'TYPE:Outer wall'), (blank['kind'], blank['comment']))

    def test_default_modes_are_unknown_until_explicitly_set(self):
        state = sh.Shadow()
        self.assertEqual('unknown', state.process('G1 X10 E1\n', 1)['kind'])
        for i, mode in enumerate(('G21', 'G90', 'M82', 'G92 E0'), 2):
            state.process(mode + '\n', i)
        move = state.process('G1 X10 E1\n', 6)
        self.assertEqual('move', move['kind'])
        self.assertEqual(1, move['commanded_e_delta_mm'])
        self.assertIsNone(move['start_mm']['X'])

    def test_relative_unknown_position_is_not_invented(self):
        self.feed('G91'); move = self.feed('G1 X10')
        self.assertIsNone(move['start_mm']['X'])
        self.assertIsNone(move['end_mm']['X'])

    def test_passive_event_does_not_change_mode_or_position(self):
        self.feed('G1 X5')
        for event in ('M104 S200', 'M221 S90', 'G4 P100'):
            self.assertEqual('non_motion_event', self.feed(event)['kind'])
        self.assertEqual(5, self.feed('G1 X6')['start_mm']['X'])

    def test_cli_reads_input_without_modifying_and_jsonl_roundtrips(self):
        content = b'G90\r\nM83\n;comment\nG1 X1 E0.5\n;byte:\xff\n'
        with tempfile.TemporaryDirectory(prefix='r2-shadow-') as tmp:
            path = Path(tmp)/'input.gcode'; path.write_bytes(content)
            before = hashlib.sha256(path.read_bytes()).hexdigest()
            run = subprocess.run([sys.executable, str(Path(sh.__file__)), str(path)],
                                 capture_output=True, text=True, check=True)
            records = [json.loads(line) for line in run.stdout.splitlines()]
            self.assertEqual(content, ''.join(r['raw'] for r in records).encode('utf-8', 'surrogateescape'))
            self.assertEqual(before, hashlib.sha256(path.read_bytes()).hexdigest())
            self.assertEqual([1, 2, 3, 4, 5], [r['line'] for r in records])

    def test_fixpoint_mutation_of_relative_state_is_detected(self):
        self.feed('G90'); self.feed('G1 X0'); self.feed('G91')
        self.feed('G1 X10')
        with mock.patch.dict(self.s.position, {'X': 0.0}):
            mutated = self.feed('G1 X10')
        with self.assertRaises(AssertionError):
            self.assertEqual(20, mutated['end_mm']['X'])


if __name__ == '__main__':
    unittest.main(verbosity=2)
