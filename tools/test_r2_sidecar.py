#!/usr/bin/env python3
"""Non-destructive Pass 11 sidecar tests; does not access a printer."""
import hashlib
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest

sys.dont_write_bytecode = True
import r2_sidecar as sidecar


class SidecarTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='r2-sidecar-test-')
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.source = self.root / 'input.gcode'
        self.data = (b'G21\nG90\nM83\n;LAYER_CHANGE\n;TYPE:External perimeter\n'
                     b'G1 X0 Y0 Z0.2 F3000\nG1 X10 Y0 E1 F1800\n'
                     b'G1 X10 Y10 E0.5 F1800\nM999\n')
        self.source.write_bytes(self.data)

    def _build(self, **kwargs):
        kwargs.setdefault('created_utc', '2026-11-17T00:00:00Z')
        return sidecar.run(self.source, self.root / 'out.json', **kwargs)

    def test_sidecar_is_written_and_source_untouched(self):
        result = self._build()
        self.assertEqual(self.data, self.source.read_bytes())
        out = self.root / 'out.json'
        self.assertTrue(out.is_file())
        on_disk = json.loads(out.read_text(encoding='utf-8'))
        self.assertEqual(on_disk, result)
        self.assertEqual('r2-sidecar/1', on_disk['schema'])
        self.assertEqual(hashlib.sha256(self.data).hexdigest(),
                         on_disk['source']['sha256'])
        self.assertEqual(len(self.data), on_disk['source']['bytes'])
        self.assertEqual(9, on_disk['source']['lines'])
        self.assertEqual('input.gcode', on_disk['source']['label'])

    def test_payload_hash_verifies_and_detects_tampering(self):
        self._build()
        out = self.root / 'out.json'
        ok, problems = sidecar.verify_sidecar(out)
        self.assertTrue(ok, problems)
        doc = json.loads(out.read_text(encoding='utf-8'))
        doc['analysis']['record_counts']['move'] = 999
        out.write_text(json.dumps(doc, sort_keys=True), encoding='utf-8')
        ok, problems = sidecar.verify_sidecar(out)
        self.assertFalse(ok)
        self.assertTrue(any('hash mismatch' in p for p in problems), problems)

    def test_never_overwrites_existing_destination(self):
        out = self.root / 'out.json'
        out.write_bytes(b'previous')
        with self.assertRaises(FileExistsError):
            self._build()
        self.assertEqual(b'previous', out.read_bytes())
        self.assertEqual(self.data, self.source.read_bytes())

    def test_moves_absent_by_default_and_capped_on_request(self):
        default = self._build()
        self.assertIsNone(default['moves'])
        self.assertEqual(0, default['moves_meta']['records'])
        self.assertFalse(default['moves_meta']['requested'])
        out2 = self.root / 'second.json'
        full = sidecar.run(self.source, out2, include_moves=True,
                           created_utc='2026-11-17T00:00:00Z')
        self.assertEqual(3, full['moves_meta']['records'])
        self.assertEqual(3, len(full['moves']))
        self.assertEqual(['G1', 'G1', 'G1'],
                         [m['command'] for m in full['moves']])
        self.assertEqual(list(range(6, 9)), [m['line'] for m in full['moves']])
        capped = sidecar.run(self.source, self.root / 'third.json',
                             include_moves=True, max_move_records=2,
                             created_utc='2026-11-17T00:00:00Z')
        self.assertEqual(2, capped['moves_meta']['records'])
        self.assertTrue(capped['moves_meta']['truncated'])
        self.assertEqual(2, len(capped['moves']))

    def test_unknown_commands_are_visible_not_hidden(self):
        result = self._build()
        self.assertEqual(1, result['analysis']['record_counts'].get('unknown'))
        reasons = result['analysis']['unknown_reasons']
        self.assertTrue(any('unsupported' in reason for reason in reasons))
        self.assertEqual(1, len(result['analysis']['unknown_examples']))

    def test_trace_options_are_recorded(self):
        result = sidecar.run(
            self.source, self.root / 'opt.json',
            created_utc='2026-11-17T00:00:00Z',
            assume_klipper_defaults=True, klipper_passive=True,
            verified_r2_passive=True, enable_arcs=True, firmware_retract=True)
        opts = result['trace_options']
        self.assertTrue(opts['assume_klipper_defaults'])
        self.assertTrue(opts['klipper_passive'])
        self.assertTrue(opts['verified_r2_passive'])
        self.assertTrue(opts['enable_arcs'])
        self.assertTrue(opts['firmware_retract'])

    def test_deterministic_with_fixed_timestamp(self):
        first = sidecar.run(self.source, self.root / 'a.json',
                            created_utc='2026-11-17T00:00:00Z',
                            include_moves=True)
        second = sidecar.run(self.source, self.root / 'b.json',
                             created_utc='2026-11-17T00:00:00Z',
                             include_moves=True)
        self.assertEqual(
            (self.root / 'a.json').read_bytes(),
            (self.root / 'b.json').read_bytes())
        self.assertEqual(first['integrity'], second['integrity'])

    def test_generator_provenance_comes_from_code(self):
        result = self._build()
        generator = result['generator']
        self.assertEqual('tools/r2_sidecar.py', generator['tool'])
        self.assertNotEqual('unknown', generator['tool_version'])
        self.assertNotEqual('unknown', generator['postproc_build'])
        self.assertTrue(generator['python'])

    def test_rejects_non_json_output_and_bad_cap(self):
        with self.assertRaises(ValueError):
            sidecar.run(self.source, self.root / 'out.gcode')
        with self.assertRaises(ValueError):
            sidecar.run(self.source, self.root / 'out.json',
                        include_moves=True, max_move_records=0)


if __name__ == '__main__':
    unittest.main()
