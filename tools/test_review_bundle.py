#!/usr/bin/env python3
"""Review archive reproducibility and mutation checks; no publication."""
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
import zipfile

import build_review_bundle as bundle


class BundleTests(unittest.TestCase):
    def test_reproducible_archive_and_manifest_mutation(self):
        with tempfile.TemporaryDirectory(prefix='r2-release-test-') as tmp:
            first, second, corrupt = (Path(tmp) / n for n in ('a.zip', 'b.zip', 'corrupt.zip'))
            doc = bundle.build(bundle.ROOT, first)
            bundle.build(bundle.ROOT, second)
            self.assertEqual(hashlib.sha256(first.read_bytes()).hexdigest(), hashlib.sha256(second.read_bytes()).hexdigest())
            self.assertEqual(doc, bundle.validate(first))
            self.assertIn('source/backups/r2_postproc_R2-2026-11-13.1_V1.py', doc['files'])
            self.assertIn('source/tools/r2_offline.py', doc['files'])
            self.assertEqual('review only; incomplete; do not install', doc['status'])
            with self.assertRaises(FileExistsError): bundle.build(bundle.ROOT, first)
            with zipfile.ZipFile(first) as z, zipfile.ZipFile(corrupt, 'w') as out:
                for info in z.infolist():
                    data = z.read(info.filename)
                    if info.filename == 'source/LICENSE': data = data + b'\nmutated\n'
                    out.writestr(info, data)
            with self.assertRaisesRegex(ValueError, 'manifest mismatch'):
                bundle.validate(corrupt)

    def test_ignored_upload_and_archive_are_not_in_source_list(self):
        # R262: the handoff sources under analyse/uebergabe-quellen/ are
        # TRACKED now (user decision, 13th commissioning round - the research
        # documents live in the repo, see the inner .gitignore). What must
        # stay out of every source list: the generated archives (*.zip,
        # *.zip.png - inner .gitignore), releases/, and the local-only pinned
        # Klipper reference parser.
        paths = bundle.source_paths(bundle.ROOT)
        self.assertFalse(any(p.startswith('analyse/uebergabe-quellen/') and p.endswith(('.zip', '.zip.png')) for p in paths))
        self.assertIn('analyse/uebergabe-quellen/SHA256SUMS', paths)
        self.assertFalse(any(p.startswith('releases/') for p in paths))
        self.assertNotIn('analyse/klipper-referenz/gcode.py', paths)


if __name__ == '__main__': unittest.main(verbosity=2)
