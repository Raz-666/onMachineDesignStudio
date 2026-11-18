#!/usr/bin/env python3
"""Tests for the offline golden harness, never touching real inputs in place."""
import contextlib
import copy
import hashlib
import io
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import golden_baseline as g


class BaselineTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.expected = json.loads(g.BASELINE.read_text(encoding='utf-8'))

    def test_copy_of_reference_matches(self):
        self.assertEqual([], g.compare(self.expected, copy.deepcopy(self.expected)))

    def test_input_output_summary_and_engine_mutations_are_detected(self):
        for part in ('input_sha256', 'output_sha256', 'summary'):
            with self.subTest(part=part):
                altered = copy.deepcopy(self.expected)
                if part == 'summary':
                    altered['cases']['m82_zhop']['summary']['marks_added'] += 1
                else:
                    altered['cases']['m82_zhop'][part] = '0' * 64
                self.assertTrue(g.compare(self.expected, altered))
        altered = copy.deepcopy(self.expected)
        altered['engine_sha256'] = '0' * 64
        self.assertTrue(g.compare(self.expected, altered))

    def test_candidate_comparison_ignores_only_engine_identity(self):
        candidate = copy.deepcopy(self.expected)
        candidate['engine'] = 'tools/r2_postproc_next.py'
        candidate['engine_sha256'] = '1' * 64
        self.assertTrue(g.compare(self.expected, candidate))
        self.assertFalse(g.compare(self.expected, candidate, check_engine=False))
        candidate['cases']['tagged']['output_sha256'] = '0' * 64
        self.assertTrue(g.compare(self.expected, candidate, check_engine=False))

    def test_missing_or_extra_fields_and_cases_are_detected(self):
        for mode in ('missing_case', 'extra_case', 'missing_field', 'extra_field'):
            with self.subTest(mode=mode):
                altered = copy.deepcopy(self.expected)
                if mode == 'missing_case': del altered['cases']['tagged']
                elif mode == 'extra_case': altered['cases']['other'] = {}
                elif mode == 'missing_field': del altered['cases']['tagged']['output_sha256']
                else: altered['cases']['tagged']['unexpected'] = 1
                self.assertTrue(g.compare(self.expected, altered))

    def test_worker_uses_current_synthetic_case_and_no_original_write(self):
        before = {name: g.digest(path) for name, path in g.FIXTURES.items()}
        entry = g.run_worker('m83_comments')
        self.assertEqual(self.expected['cases']['m83_comments'], entry['result'])
        self.assertEqual(before, {name: g.digest(path) for name, path in g.FIXTURES.items()})
        self.assertEqual(hashlib.sha256(g.SYNTHETIC['m83_comments']).hexdigest(),
                         entry['result']['input_sha256'])

    def test_documented_zscan_delta_rejects_other_mutations(self):
        delta = json.loads(g.ZSCAN_EXPECTED.read_text())
        expected, errors = g.expected_with_zscan_change(self.expected, delta)
        self.assertFalse(errors)
        self.assertEqual(1, expected['cases']['m82_zhop']['summary']['marks_added'])
        self.assertEqual(2, self.expected['cases']['m82_zhop']['summary']['marks_added'])
        changed = copy.deepcopy(expected)
        changed['cases']['m82_zhop']['output_sha256'] = '0' * 64
        self.assertTrue(g.compare(expected, changed, check_engine=False))
        changed = copy.deepcopy(expected)
        changed['cases']['rose']['output_sha256'] = '0' * 64
        self.assertTrue(g.compare(expected, changed, check_engine=False))
        bad_reference = copy.deepcopy(self.expected)
        bad_reference['cases']['m82_zhop']['output_sha256'] = '0' * 64
        self.assertTrue(g.expected_with_zscan_change(bad_reference, delta)[1])

    def test_documented_r258_delta_rejects_other_mutations(self):
        zscan = json.loads(g.ZSCAN_EXPECTED.read_text())
        expected, errors = g.expected_with_zscan_change(self.expected, zscan)
        self.assertFalse(errors)
        delta = json.loads(g.R258_EXPECTED.read_text())
        expected, errors = g.expected_with_r258_change(expected, delta)
        self.assertFalse(errors)
        self.assertEqual(2, expected['cases']['m82_zhop']['summary']['layers'])
        self.assertEqual(1, expected['cases']['m82_zhop']['summary']['marks_added'])
        changed = copy.deepcopy(expected)
        changed['cases']['m82_zhop']['output_sha256'] = '0' * 64
        self.assertTrue(g.compare(expected, changed, check_engine=False))
        bad_reference = copy.deepcopy(expected)
        bad_reference['cases']['m82_zhop'] = copy.deepcopy(
            json.loads(g.ZSCAN_EXPECTED.read_text())['candidate'])
        bad_reference['cases']['m82_zhop']['output_sha256'] = '0' * 64
        self.assertTrue(g.expected_with_r258_change(bad_reference, delta)[1])

    def test_documented_seq_delta_rejects_other_mutations(self):
        delta = json.loads(g.SEQ_EXPECTED.read_text())
        expected, errors = g.expected_with_seq_change(self.expected, delta)
        self.assertFalse(errors)
        self.assertEqual(
            self.expected['cases']['rose']['output_bytes'] - 10,
            expected['cases']['rose']['output_bytes'])
        self.assertEqual(
            self.expected['cases']['bigrose']['output_sha256'],
            expected['cases']['bigrose']['output_sha256'])
        self.assertEqual(
            self.expected['cases']['stringart']['output_sha256'],
            expected['cases']['stringart']['output_sha256'])
        changed = copy.deepcopy(expected)
        changed['cases']['rose']['output_sha256'] = '0' * 64
        self.assertTrue(g.compare(expected, changed, check_engine=False))
        bad_reference = copy.deepcopy(self.expected)
        bad_reference['cases']['rose']['output_sha256'] = '0' * 64
        self.assertTrue(g.expected_with_seq_change(bad_reference, delta)[1])

    def test_reference_backup_mutation_is_rejected(self):
        actual = copy.deepcopy(self.expected)
        metrics = {name: {} for name in g.CASES}
        with tempfile.TemporaryDirectory(prefix='r2-ref-mutant-') as tmp:
            altered = Path(tmp) / 'backup.py'
            altered.write_bytes(g.REFERENCE_ENGINE.read_bytes() + b'\n# mutation\n')
            err = io.StringIO()
            with mock.patch.object(g, 'REFERENCE_ENGINE', altered), \
                 mock.patch.object(g, 'collect', return_value=(actual, metrics)), \
                 mock.patch.object(sys, 'argv', ['golden_baseline.py', 'verify']), \
                 contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(err):
                self.assertEqual(1, g.main())
            self.assertIn('reference engine identity', err.getvalue())

    def test_end_to_end_mutated_golden_fails(self):
        altered = copy.deepcopy(self.expected)
        altered['cases']['m82_zhop']['output_sha256'] = '0' * 64
        with tempfile.TemporaryDirectory(prefix='r2-baseline-mutant-') as tmp:
            path = Path(tmp) / 'golden.json'
            path.write_text(json.dumps(altered), encoding='utf-8')
            run = subprocess.run([sys.executable, str(HERE / 'golden_baseline.py'),
                                  'verify', '--baseline', str(path)],
                                 cwd=g.ROOT, text=True, capture_output=True, timeout=120)
        self.assertEqual(1, run.returncode, run.stdout + run.stderr)
        self.assertIn('m82_zhop.output_sha256', run.stderr)
        self.assertNotIn('PASS: 6 cases', run.stdout)


if __name__ == '__main__':
    unittest.main(verbosity=2)
