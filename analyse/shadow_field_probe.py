#!/usr/bin/env python3
"""Summarize read-only shadow traces of repo gzip fixtures; never emit G-code."""
from collections import Counter
import gzip
import hashlib
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
import r2_shadow


def sha256(path):
    h = hashlib.sha256()
    with path.open('rb') as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


for path in sorted((ROOT / 'testfixtures').glob('*.gcode.gz')):
    before = sha256(path)
    for assume in (False, True):
        state = r2_shadow.Shadow(assume_klipper_defaults=assume)
        kinds, reasons, known = Counter(), Counter(), 0
        start = time.monotonic()
        with gzip.open(path, 'rt', encoding='utf8', errors='surrogateescape', newline='') as src:
            for number, line in enumerate(src, 1):
                record = state.process(line, number)
                kinds[record['kind']] += 1
                if record['kind'] == 'unknown': reasons[record.get('reason', '')] += 1
                if record['kind'] == 'move' and all(v is not None for v in record['end_mm'].values()):
                    known += 1
        print(path.name, 'assume_klipper_defaults=', assume, 'lines=', sum(kinds.values()),
              'kinds=', dict(kinds), 'known_xyz_move_ends=', known,
              'reasons=', dict(reasons), 'seconds=', round(time.monotonic() - start, 3))
    assert before == sha256(path), 'compressed input changed'
    print('  gzip_sha256=', before, 'unchanged=True')
