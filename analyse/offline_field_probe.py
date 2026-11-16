#!/usr/bin/env python3
"""Compare conservative and hypothetical shadow analysis on compressed fixtures.

All data stays in a temporary directory. No commands from a fixture are run.
Assumptions below deliberately ignore real macro effects; they are not a
recommendation, machine configuration or validation of actual motion.
"""
import gzip
import hashlib
from pathlib import Path
import shutil
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
import r2_offline

# The purpose is to quantify the effect of assumptions, not assert that
# G28, T0, retraction, excludes or layer macros are actually passive.
ASSUMED = ('M73', 'SET_PRESSURE_ADVANCE', 'SET_VELOCITY_LIMIT',
           'EXCLUDE_OBJECT_DEFINE', 'EXCLUDE_OBJECT_START', 'EXCLUDE_OBJECT_END',
           'LAYER_MARK', 'G10', 'G11', 'G28', 'T0')


def sha(path):
    h = hashlib.sha256()
    with path.open('rb') as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b''): h.update(chunk)
    return h.hexdigest()


def main():
    for fixture in sorted((ROOT / 'testfixtures').glob('*.gcode.gz')):
        before = sha(fixture)
        with tempfile.TemporaryDirectory(prefix='r2-offline-field-') as tmp:
            src = Path(tmp) / 'input.gcode'
            with gzip.open(fixture, 'rb') as f, src.open('wb') as out: shutil.copyfileobj(f, out)
            source_hash = sha(src)
            for label, assumed in (('conservative', ()), ('hypothetical', ASSUMED)):
                report = r2_offline.run(src, Path(tmp) / (label + '.json'), 'report', assumed_passive=assumed)
                a = report['analysis']
                print(fixture.name, label, 'input_sha256=', source_hash,
                      'moves=', a['record_counts'].get('move', 0),
                      'known_xyz=', a['moves_with_known_xyz_end'],
                      'unknown=', a['record_counts'].get('unknown', 0),
                      'assumed_events=', a['record_counts'].get('assumed_passive', 0),
                      'layer_comments=', a['layer_comment_count'],
                      'layer_marks=', a['layer_mark_count'],
                      'evidence_groups=', len(a['evidence']['groups']),
                      'explicit_objects=', len(a['evidence']['objects']),
                      'extruding_xy_segments=', sum(g['extruding_xy_segments'] for g in a['evidence']['groups']),
                      'closed_xy_paths=', sum(g['closed_xy_paths'] for g in a['evidence']['groups']),
                      'warnings_retained=', len(a['evidence']['warnings']))
            assert sha(src) == source_hash
        assert before == sha(fixture)
        print('  archive_sha256=', before, 'unchanged=True')
    print('Hypothetical mode assumes, without proof, that the listed commands do not affect tracked state:', ','.join(ASSUMED))
    print('No resulting coordinate is a measured physical position or print-safety guarantee.')

if __name__ == '__main__': main()
