#!/usr/bin/env python3
"""Non-destructive offline service tests; does not access a printer."""
from concurrent.futures import ThreadPoolExecutor
import errno
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

import r2_offline as off


class OfflineTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='r2-offline-test-')
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.source = self.root / 'input.gcode'
        self.data = (b'G21\nG90\nM83\n;LAYER_CHANGE\n;TYPE:External perimeter\n'
                     b'G1 X0 Y0 Z0.2 F3000\nG1 X10 Y0 E1 F1800\n')
        self.source.write_bytes(self.data)

    def remaining(self): return list(self.root.glob('.r2-offline-*'))

    def test_report_preserves_original_and_finds_evidence(self):
        out = self.root / 'report.json'
        result = off.run(self.source, out, 'report')
        self.assertEqual(self.data, self.source.read_bytes())
        self.assertEqual(hashlib.sha256(self.data).hexdigest(), result['source']['sha256'])
        self.assertEqual(result, json.loads(out.read_text()))
        self.assertEqual(1, result['analysis']['layer_comment_count'])
        self.assertEqual({'External perimeter': 1}, result['analysis']['feature_comment_counts'])
        self.assertEqual(2, result['analysis']['moves_with_known_xyz_end'])
        self.assertEqual([], self.remaining())

    def test_assumptions_are_explicit_and_report_only(self):
        self.source.write_bytes(b'G21\nG90\nM83\nG1 X1 Y2 Z3\nLAYER_MARK\nG1 X2\n')
        default = off.run(self.source, self.root / 'default.json', 'report')
        assumed = off.run(self.source, self.root / 'assumed.json', 'report', assumed_passive=['LAYER_MARK'])
        self.assertEqual([], default['analysis']['assumed_passive_commands'])
        self.assertEqual(['LAYER_MARK'], assumed['analysis']['assumed_passive_commands'])
        self.assertEqual(1, assumed['analysis']['record_counts']['assumed_passive'])
        self.assertEqual(1, default['analysis']['moves_with_known_xyz_end'])
        self.assertEqual(2, assumed['analysis']['moves_with_known_xyz_end'])
        with self.assertRaises(ValueError): off.run(self.source, self.root / 'x.gcode', 'derive', assumed_passive=['LAYER_MARK'])

    def test_derive_runs_real_engine_on_copy_only(self):
        out = self.root / 'derived.gcode'
        report = off.run(self.source, out, 'derive')
        self.assertEqual(self.data, self.source.read_bytes())
        self.assertTrue(out.read_bytes().startswith(b'; R2-POSTPROC v5'))
        self.assertEqual(off.digest_file(out), report['output']['sha256'])
        self.assertTrue(report['summary']['tagged'])
        self.assertFalse(report['engine']['retract_rewrite'])
        self.assertEqual([], self.remaining())

    def test_collision_symlink_and_fifo_fail_without_modification(self):
        target = self.root / 'out.json'; target.write_bytes(b'keep')
        with self.assertRaises(FileExistsError): off.run(self.source, target, 'report')
        self.assertEqual(b'keep', target.read_bytes())
        link = self.root / 'source-link.gcode'; link.symlink_to(self.source)
        with self.assertRaises(OSError): off.run(link, self.root / 'x.json', 'report')
        fifo = self.root / 'fifo.gcode'; os.mkfifo(fifo)
        with self.assertRaises(ValueError): off.run(fifo, self.root / 'f.json', 'report')
        self.assertEqual(self.data, self.source.read_bytes())
        self.assertEqual([], self.remaining())

    def test_destination_symlink_and_source_as_output_never_clobbered(self):
        link = self.root / 'out.gcode'; link.symlink_to(self.source)
        with self.assertRaises(FileExistsError): off.run(self.source, link, 'derive')
        with self.assertRaises(FileExistsError): off.run(self.source, self.source, 'derive')
        self.assertTrue(link.is_symlink()); self.assertEqual(self.data, self.source.read_bytes())

    def test_size_empty_and_overlong_line_fail_closed(self):
        with self.assertRaises(ValueError): off.run(self.source, self.root / 'a.json', 'report', max_bytes=3)
        self.source.write_bytes(b'')
        with self.assertRaises(ValueError): off.run(self.source, self.root / 'b.json', 'report')
        self.source.write_bytes(b';' + b'x' * (1024 * 1024) + b'\n')
        with self.assertRaisesRegex(ValueError, 'line exceeds'): off.run(self.source, self.root / 'c.json', 'report')
        self.assertEqual([], self.remaining())

    def test_source_change_before_publish_fails_closed(self):
        analysis = off.analyse
        def change(path, **kwargs):
            result = analysis(path, **kwargs)
            self.source.write_bytes(b'changed')
            return result
        with mock.patch.object(off, 'analyse', side_effect=change):
            with self.assertRaises(off.SourceChanged): off.run(self.source, self.root / 'r.json', 'report')
        self.assertFalse((self.root / 'r.json').exists())
        self.assertEqual([], self.remaining())

    def test_processor_failure_timeout_and_unsupported_link(self):
        for error in (RuntimeError('bad process'), subprocess.TimeoutExpired('engine', 1)):
            with self.subTest(error=error), mock.patch.object(off.subprocess, 'run', side_effect=error):
                with self.assertRaises(type(error)): off.run(self.source, self.root / 'd.gcode', 'derive')
                self.assertFalse((self.root / 'd.gcode').exists())
        with mock.patch.object(off.os, 'link', side_effect=OSError(errno.EOPNOTSUPP, 'no hardlinks')):
            with self.assertRaises(OSError): off.run(self.source, self.root / 'r.json', 'report')
        self.assertEqual(self.data, self.source.read_bytes()); self.assertEqual([], self.remaining())

    def test_parallel_publication_has_one_winner(self):
        target = self.root / 'same.json'
        def job(_):
            try: off.run(self.source, target, 'report'); return 'won'
            except FileExistsError: return 'collision'
        with ThreadPoolExecutor(max_workers=4) as pool: results = list(pool.map(job, range(4)))
        self.assertEqual(1, results.count('won')); self.assertEqual(3, results.count('collision'))
        self.assertEqual(self.data, self.source.read_bytes())
        self.assertEqual([], self.remaining())

    def test_destructive_link_mutation_is_detected(self):
        target = self.root / 'r.json'; target.write_bytes(b'protected')
        def unsafe_link(src, dst, *, dst_dir_fd, follow_symlinks):
            os.replace(src, dst, dst_dir_fd=dst_dir_fd)
        with mock.patch.object(off.os, 'link', side_effect=unsafe_link):
            off.run(self.source, target, 'report')
        with self.assertRaises(AssertionError): self.assertEqual(b'protected', target.read_bytes())

    def test_cli_error_and_valid_json(self):
        tool = str(Path(off.__file__))
        output = self.root / 'a.json'
        cmd = [sys.executable, tool, 'report', str(self.source), str(output)]
        first = subprocess.run(cmd, text=True, capture_output=True)
        self.assertEqual(0, first.returncode, first.stderr)
        self.assertEqual('r2-offline/1', json.loads(first.stdout)['schema'])
        second = subprocess.run(cmd, text=True, capture_output=True)
        self.assertEqual(1, second.returncode)
        self.assertEqual(self.data, self.source.read_bytes())


if __name__ == '__main__': unittest.main(verbosity=2)
