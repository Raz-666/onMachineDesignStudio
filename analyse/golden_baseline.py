#!/usr/bin/env python3
"""Offline baseline of stable process(), exclusively on disposable copies.

record prints candidate golden JSON to stdout, never overwrites a baseline.
verify checks a committed golden before and after every run. No watcher,
Moonraker, printer, texture/shape generator or executable G-code is started.
"""
import argparse
import contextlib
import copy
import gzip
import hashlib
import json
from pathlib import Path
import platform
import resource
import shutil
import subprocess
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parents[1]
ENGINES = {'stable': ROOT / 'tools/r2_postproc.py',
           'next': ROOT / 'tools/r2_postproc_next.py'}
ENGINE = ENGINES['stable']
# The baseline was recorded before the active entry point was updated.
# Keep its exact pre-migration bytes as the pinned comparison reference.
REFERENCE_ENGINE = ROOT / 'backups/r2_postproc_R2-2026-11-13.1_V1.py'
BASELINE = ROOT / 'analyse/golden_baseline.json'
ZSCAN_EXPECTED = ROOT / 'analyse/golden_zscan_expected.json'
FIELDS = ('tagged', 'skipped', 'marks_added', 'info_added', 'layers', 'method',
          'types', 'by_object', 'upgraded', 'retract_pairs')
SYNTHETIC = {
    'm83_comments': ('G90\nM83\n;LAYER_CHANGE\n;TYPE:External perimeter\n'
                     'G1 X0 Y0 Z0.2 F3000\nG1 X20 Y0 E1 F1800\n'
                     ';LAYER_CHANGE\n;TYPE:Top surface\nG1 Z0.4 F600\n'
                     'G1 X20 Y20 E1 F1800\n').encode(),
    'm82_zhop': ('G90\nM82\n;TYPE:External perimeter\nG1 X10 Y0 Z0.2 E1\n'
                 'G0 Z0.4\nG1 X12 Y0 E1\nG0 Z0.2\nG1 X20 Y0 E2\n'
                 'G0 Z0.4\nG1 X30 Y0 E3\n').encode(),
    'tagged': ('; R2-POSTPROC v5\n_FILE_INFO RETRACT=slicer\nM83\n'
               'G1 X0 Y0 Z0.2\nG1 X20 Y0 E1 F1800\n').encode(),
}
FIXTURES = {
    'bigrose': ROOT / 'testfixtures/bigrose_020mm.gcode.gz',
    'rose': ROOT / 'testfixtures/rose_215c_pla.gcode.gz',
    'stringart': ROOT / 'testfixtures/stringart3d_generic.gcode.gz',
}
CASES = tuple(SYNTHETIC) + tuple(FIXTURES)


def digest(path):
    h = hashlib.sha256()
    with path.open('rb') as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


def io_counters():
    try:
        pairs = (line.split(':', 1) for line in Path('/proc/self/io').read_text().splitlines())
        return {k: int(v) for k, v in pairs if k in ('rchar', 'wchar', 'read_bytes', 'write_bytes')}
    except (OSError, ValueError):
        return None


def run_worker(name, engine='stable'):
    # These explicit modules are imported without calling either watcher's main.
    sys.path.insert(0, str(ROOT / 'tools'))
    pp = __import__('r2_postproc' if engine == 'stable' else 'r2_postproc_next')
    before_archive = digest(FIXTURES[name]) if name in FIXTURES else None
    with tempfile.TemporaryDirectory(prefix='r2-golden-') as tmp:
        path = Path(tmp) / (name + '.gcode')
        if name in SYNTHETIC:
            path.write_bytes(SYNTHETIC[name])
        else:
            with gzip.open(FIXTURES[name], 'rb') as src, path.open('wb') as dest:
                shutil.copyfileobj(src, dest, length=1024 * 1024)
        input_sha = digest(path)
        input_size = path.stat().st_size
        usage0, io0, t0 = resource.getrusage(resource.RUSAGE_SELF), io_counters(), time.monotonic()
        # stdout is reserved for JSON even if a future engine prints diagnostics.
        with contextlib.redirect_stdout(sys.stderr):
            summary = pp.process(str(path), dry=False, verbose=False, retract_rewrite=False)
        elapsed = time.monotonic() - t0
        usage1, io1 = resource.getrusage(resource.RUSAGE_SELF), io_counters()
        data = {'input_sha256': input_sha, 'input_bytes': input_size,
                'output_sha256': digest(path), 'output_bytes': path.stat().st_size,
                'summary': {key: summary.get(key) for key in FIELDS},
                'archive_sha256': before_archive}
        if before_archive is not None and digest(FIXTURES[name]) != before_archive:
            raise RuntimeError('Source archive changed during run: ' + name)
        measurements = {'wall_seconds': round(elapsed, 6),
                        'cpu_user_seconds': round(usage1.ru_utime - usage0.ru_utime, 6),
                        'cpu_system_seconds': round(usage1.ru_stime - usage0.ru_stime, 6),
                        # Linux reports KiB, macOS bytes. This includes import and staging.
                        'maxrss_raw': usage1.ru_maxrss,
                        'maxrss_units': 'KiB' if sys.platform.startswith('linux') else 'platform-dependent',
                        'io_delta': {k: io1[k] - io0[k] for k in io0} if io0 and io1 else None}
        return {'case': name, 'result': data, 'metrics': measurements}


def collect(engine='stable'):
    results, metrics = {}, {}
    for name in CASES:
        result = subprocess.run([sys.executable, str(Path(__file__).resolve()), 'worker', name,
                                 '--engine', engine],
                                cwd=ROOT, text=True, stdout=subprocess.PIPE, check=True)
        entry = json.loads(result.stdout)
        results[name], metrics[name] = entry['result'], entry['metrics']
    return ({'format': 1, 'engine': str(ENGINES[engine].relative_to(ROOT)),
             'engine_sha256': digest(ENGINES[engine]),
             'parameters': {'dry': False, 'verbose': False, 'retract_rewrite': False},
             'cases': results}, metrics)


def compare(expected, actual, check_engine=True):
    errors = []
    keys = ('format', 'engine', 'engine_sha256', 'parameters') if check_engine else ('format', 'parameters')
    for key in keys:
        if expected.get(key) != actual.get(key):
            errors.append(f'{key}: expected {expected.get(key)!r}, got {actual.get(key)!r}')
    if set(expected.get('cases', {})) != set(actual.get('cases', {})):
        errors.append('case set differs')
    for name in sorted(set(expected.get('cases', {})) & set(actual.get('cases', {}))):
        if set(expected['cases'][name]) != set(actual['cases'][name]):
            errors.append(f'{name}: result fields differ')
        for key, want in expected['cases'][name].items():
            got = actual['cases'][name].get(key)
            if want != got:
                errors.append(f'{name}.{key}: expected {want!r}, got {got!r}')
    return errors


def expected_with_zscan_change(reference, delta):
    """Apply the one explicitly documented semantic change, never rebaseline other cases."""
    errors = []
    fields = {'output_bytes', 'output_sha256', 'summary'}
    if (delta.get('format') != 1 or delta.get('case') != 'm82_zhop'
            or set(delta.get('reference', {})) != fields
            or set(delta.get('candidate', {})) != fields):
        return copy.deepcopy(reference), ['invalid Z-scan expected-change schema']
    adjusted = copy.deepcopy(reference)
    for key in fields:
        if reference['cases']['m82_zhop'].get(key) != delta['reference'][key]:
            errors.append('m82_zhop.%s: historical reference differs from documented change' % key)
        adjusted['cases']['m82_zhop'][key] = copy.deepcopy(delta['candidate'][key])
    return adjusted, errors


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    sub.add_parser('record', help='print candidate baseline JSON; never overwrite existing files')
    verify = sub.add_parser('verify', help='check pinned data and print per-run metrics')
    verify.add_argument('--baseline', type=Path, default=BASELINE)
    verify.add_argument('--engine', choices=tuple(ENGINES), default='stable')
    worker = sub.add_parser('worker', help=argparse.SUPPRESS)
    worker.add_argument('case', choices=CASES)
    worker.add_argument('--engine', choices=tuple(ENGINES), default='stable')
    args = parser.parse_args()
    if args.command == 'worker':
        print(json.dumps(run_worker(args.case, args.engine), sort_keys=True)); return 0
    engine = args.engine if args.command == 'verify' else 'stable'
    actual, metrics = collect(engine)
    if args.command == 'record':
        print(json.dumps(actual, ensure_ascii=False, indent=2, sort_keys=True)); return 0
    reference = json.loads(args.baseline.read_text(encoding='utf-8'))
    expected, errors = expected_with_zscan_change(
        reference, json.loads(ZSCAN_EXPECTED.read_text(encoding='utf-8')))
    errors.extend(compare(expected, actual, check_engine=False))
    if (reference.get('engine') != str(ENGINE.relative_to(ROOT))
            or not REFERENCE_ENGINE.is_file()
            or reference.get('engine_sha256') != digest(REFERENCE_ENGINE)):
        errors.append('pinned pre-migration reference engine identity does not match backup')
    print('candidate:', actual['engine'], 'sha256:', actual['engine_sha256'])
    print('environment:', platform.platform(), 'Python', platform.python_version(), 'pid isolation: one process per case')
    for name in CASES:
        print(name, json.dumps(metrics[name], sort_keys=True))
    if errors:
        for error in errors: print('FAIL', error, file=sys.stderr)
        return 1
    print('PASS:', len(CASES), 'cases: 5 unchanged, 1 documented Z-scan change; source archives unchanged')
    return 0


if __name__ == '__main__':
    sys.exit(main())
