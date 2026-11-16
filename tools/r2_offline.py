#!/usr/bin/env python3
"""Experimental offline file service. No printer, watcher, or automatic installation.

report reads a snapshot and publishes a JSON sidecar; derive runs the existing
experimental postprocessor on a private snapshot and publishes a separate copy.
Neither command overwrites a source or existing destination. Derived G-code is
NOT certified safe for printing; the underlying legacy semantics are unchanged.
"""
import argparse
from collections import Counter
import contextlib
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import stat
import subprocess
import sys
import tempfile

import r2_shadow
import r2_analysis

CHUNK = 1024 * 1024
DEFAULT_MAX_BYTES = 512 * 1024 * 1024
FEATURE = re.compile(r'^\s*;\s*(?:TYPE|FEATURE)\s*:\s*(.*?)\s*$', re.I)
LAYER = re.compile(r'^\s*;\s*(?:LAYER_CHANGE|CHANGE_LAYER|LAYER\s*:?\s*\d+)\s*$', re.I)
OBJECT = re.compile(r'^\s*(EXCLUDE_OBJECT_(?:START|END|DEFINE))\b', re.I)
WORKER = """import contextlib,json,sys
sys.path.insert(0,sys.argv[1])
import r2_postproc_next
with contextlib.redirect_stdout(sys.stderr):
    result=r2_postproc_next.process(sys.argv[2],dry=False,verbose=False,retract_rewrite=False)
print(json.dumps(result,sort_keys=True))
"""


class SourceChanged(OSError):
    pass


def digest_file(path):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for data in iter(lambda: f.read(CHUNK), b''):
            h.update(data)
    return h.hexdigest()


def identity(st):
    return (st.st_dev, st.st_ino, st.st_size, st.st_mtime_ns, st.st_ctime_ns)


def _open_source(path):
    if not hasattr(os, 'O_NOFOLLOW'):
        raise OSError('safe no-follow open unavailable')
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    try:
        if not stat.S_ISREG(os.fstat(fd).st_mode):
            raise ValueError('source must be a regular file (no symlink or device)')
        return fd
    except BaseException:
        os.close(fd)
        raise


def _verify_source(fd, path, before, expected_hash):
    if identity(os.fstat(fd)) != before or identity(os.stat(path, follow_symlinks=False)) != before:
        raise SourceChanged('source identity or metadata changed during job')
    os.lseek(fd, 0, os.SEEK_SET)
    h = hashlib.sha256()
    while True:
        data = os.read(fd, CHUNK)
        if not data: break
        h.update(data)
    if h.hexdigest() != expected_hash or identity(os.fstat(fd)) != before:
        raise SourceChanged('source content changed during job')
    if identity(os.stat(path, follow_symlinks=False)) != before:
        raise SourceChanged('source path changed during job')


def _snapshot(fd, path, destination, max_bytes):
    st = os.fstat(fd)
    before = identity(st)
    if st.st_size == 0 or st.st_size > max_bytes:
        raise ValueError('source empty or exceeds configured byte limit')
    h = hashlib.sha256()
    size = 0
    with open(destination, 'xb') as output:
        while True:
            data = os.read(fd, CHUNK)
            if not data: break
            size += len(data)
            if size > max_bytes: raise ValueError('source exceeds configured byte limit')
            h.update(data)
            output.write(data)
        output.flush()
        os.fsync(output.fileno())
    _verify_source(fd, path, before, h.hexdigest())
    return before, h.hexdigest(), size


def analyse(path, max_examples=20, assumed_passive=()):
    state = r2_shadow.Shadow(assumed_passive=assumed_passive)
    evidence = r2_analysis.Tracker()
    counts, reasons, features, objects = Counter(), Counter(), Counter(), Counter()
    examples, known_ends = [], 0
    layer_comments = layer_marks = 0
    with open(path, 'r', encoding='utf8', errors='surrogateescape', newline='') as source:
        number = 0
        while True:
            raw = source.readline(1024 * 1024 + 1)
            if not raw: break
            if len(raw) > 1024 * 1024: raise ValueError('line exceeds 1 MiB analysis limit')
            number += 1
            record = state.process(raw, number)
            evidence.observe(raw, record)
            counts[record['kind']] += 1
            if record['kind'] == 'move' and all(x is not None for x in record['end_mm'].values()):
                known_ends += 1
            if record['kind'] == 'unknown':
                reason = record.get('reason', 'unknown')
                reasons[reason] += 1
                if len(examples) < max_examples:
                    examples.append({'line': number, 'text': raw.rstrip('\r\n')[:200], 'reason': reason})
            f = FEATURE.match(raw.rstrip('\r\n'))
            if f:
                # Bound untrusted-cardinality and label length, without implying
                # that a comment is ground truth or a feature was printed.
                label = f.group(1)[:160]
                if label not in features and len(features) >= 512: label = '<other>'
                features[label] += 1
            if LAYER.match(raw.rstrip('\r\n')): layer_comments += 1
            if raw.strip().split(';', 1)[0].strip().upper() == 'LAYER_MARK': layer_marks += 1
            obj = OBJECT.match(raw)
            if obj: objects[obj.group(1).upper()] += 1
    return {'assumed_passive_commands': sorted(state.assumed_passive),
            'record_counts': dict(counts), 'unknown_reasons': dict(reasons),
            'unknown_examples': examples, 'moves_with_known_xyz_end': known_ends,
            'feature_comment_counts': dict(features), 'layer_comment_count': layer_comments,
            'layer_mark_count': layer_marks, 'object_command_counts': dict(objects),
            'evidence': evidence.finish(),
            'limits': ['comments are evidence, not verified feature classifications',
                       'unknown commands invalidate tracked modal and coordinate state',
                       'coordinates are logical, not machine positions',
                       'no pattern, topology, physical motion, or print safety inferred']}


def run(source, output, mode, *, timeout=120, max_bytes=DEFAULT_MAX_BYTES, assumed_passive=()):
    if mode not in ('report', 'derive'): raise ValueError('unknown mode')
    if mode != 'report' and assumed_passive: raise ValueError('passive assumptions are report-only')
    if not 1 <= timeout <= 1800: raise ValueError('timeout must be 1..1800 seconds')
    if not 1 <= max_bytes <= 2 * 1024**3: raise ValueError('max_bytes must be 1..2147483648')
    src = os.path.abspath(os.fspath(source))
    out = Path(output).absolute()
    if out.name in ('', '.', '..') or out.suffix.lower() != ('.json' if mode == 'report' else '.gcode'):
        raise ValueError('output must end in .json (report) or .gcode (derive)')
    if not hasattr(os, 'O_DIRECTORY') or not hasattr(os, 'O_NOFOLLOW'):
        raise OSError('required safe OS flags are unavailable')
    parent = out.parent.resolve(strict=True)
    dfd = os.open(parent, os.O_RDONLY | os.O_DIRECTORY)
    fd = None
    try:
        fd = _open_source(src)
        with tempfile.TemporaryDirectory(prefix='.r2-offline-', dir=parent) as temp:
            staged = Path(temp) / 'snapshot.gcode'
            before, input_hash, size = _snapshot(fd, src, staged, max_bytes)
            report = {'schema': 'r2-offline/1', 'mode': mode,
                      'source': {'sha256': input_hash, 'bytes': size},
                      'safety': 'experimental offline result; no printer safety certification'}
            if mode == 'report':
                report['analysis'] = analyse(staged, assumed_passive=assumed_passive)
                product = Path(temp) / 'report.json'
                with product.open('x', encoding='utf8') as f:
                    json.dump(report, f, ensure_ascii=True, sort_keys=True, indent=2)
                    f.write('\n'); f.flush(); os.fsync(f.fileno())
            else:
                engine = Path(__file__).resolve().parent / 'r2_postproc_next.py'
                engine_hash = digest_file(engine)
                proc = subprocess.run([sys.executable, '-c', WORKER, str(engine.parent), str(staged)],
                                      capture_output=True, text=True, timeout=timeout)
                if proc.returncode:
                    raise RuntimeError('processor failed: ' + proc.stderr[-2000:])
                if digest_file(engine) != engine_hash:
                    raise SourceChanged('processor changed during job')
                try: summary = json.loads(proc.stdout)
                except json.JSONDecodeError as exc: raise RuntimeError('processor did not return a summary') from exc
                if not isinstance(summary, dict) or not staged.is_file() or staged.is_symlink():
                    raise RuntimeError('processor output or summary invalid')
                if staged.stat().st_size <= 0 or staged.stat().st_size > max_bytes * 2:
                    raise ValueError('processor output empty or exceeds output limit')
                with staged.open('rb') as f: os.fsync(f.fileno())
                report['engine'] = {'file': engine.name, 'sha256': engine_hash,
                                    'retract_rewrite': False}
                report['output'] = {'sha256': digest_file(staged), 'bytes': staged.stat().st_size}
                report['summary'] = summary
                product = staged
            _verify_source(fd, src, before, input_hash)
            # Same filesystem; link is atomic and never replaces an existing
            # file, symlink, or directory. Unsupported filesystems fail closed.
            os.link(product, out.name, dst_dir_fd=dfd, follow_symlinks=False)
            # Once linked, an fsync failure means output may exist even though
            # durability could not be confirmed; never remove an existing name.
            os.fsync(dfd)
            return report
    finally:
        if fd is not None: os.close(fd)
        os.close(dfd)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mode', choices=('report', 'derive'))
    parser.add_argument('source')
    parser.add_argument('output', help='new .json or .gcode path; never overwritten')
    parser.add_argument('--timeout', type=int, default=120, help='derive worker timeout seconds (1..1800)')
    parser.add_argument('--max-bytes', type=int, default=DEFAULT_MAX_BYTES)
    parser.add_argument('--assume-passive', action='append', default=[], metavar='COMMAND',
                        help='report only: assume command has no tracked effects; repeatable and unverified')
    args = parser.parse_args(argv)
    try:
        result = run(args.source, args.output, args.mode, timeout=args.timeout, max_bytes=args.max_bytes,
                     assumed_passive=args.assume_passive)
    except (OSError, ValueError, RuntimeError, subprocess.TimeoutExpired) as exc:
        print('r2-offline: %s' % exc, file=sys.stderr)
        return 1
    print(json.dumps(result, ensure_ascii=True, sort_keys=True))
    return 0


if __name__ == '__main__':
    sys.exit(main())
