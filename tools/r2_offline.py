#!/usr/bin/env python3
"""Offline non-destructive G-code report, audit, and derive service.

Modes:
  - report: conservative shadow + Pass 3-10 evidence report on a verified
    snapshot (zero implicit assumptions unless explicitly passed).
  - audit:  snapshot-verified shadow + Pass 3-10 evidence + full-stream
    C1-C5 tag-vs-geometry audit with explicitly declared Klipper/R2/arc
    modelling flags (never modifies source or existing destination).
  - derive: runs r2_postproc_next on a private snapshot and publishes a new
    derived copy via atomic non-overwriting hard link.

No command ever overwrites a source or existing destination, starts a watcher,
or claims physical machine/printer safety certification.
"""
import argparse
from collections import Counter
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import subprocess
import sys
import tempfile

import r2_analysis
import r2_postproc as legacy
import r2_shadow

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
        if not data:
            break
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
            if not data:
                break
            size += len(data)
            if size > max_bytes:
                raise ValueError('source exceeds configured byte limit')
            h.update(data)
            output.write(data)
        output.flush()
        os.fsync(output.fileno())
    _verify_source(fd, path, before, h.hexdigest())
    return before, h.hexdigest(), size


def analyse(path, max_examples=20, assumed_passive=(), *,
            assume_klipper_defaults=False, enable_arcs=False,
            firmware_retract=False, klipper_passive=False,
            verified_r2_passive=False):
    state = r2_shadow.Shadow(
        assume_klipper_defaults=assume_klipper_defaults,
        assumed_passive=assumed_passive,
        enable_arcs=enable_arcs,
        firmware_retract=firmware_retract,
        klipper_passive=klipper_passive,
        verified_r2_passive=verified_r2_passive,
    )
    evidence = r2_analysis.Tracker()
    counts, reasons, features, objects = Counter(), Counter(), Counter(), Counter()
    examples, known_ends = [], 0
    layer_comments = layer_marks = 0
    with open(path, 'r', encoding='utf8', errors='surrogateescape', newline='') as source:
        number = 0
        while True:
            raw = source.readline(1024 * 1024 + 1)
            if not raw:
                break
            if len(raw) > 1024 * 1024:
                raise ValueError('line exceeds 1 MiB analysis limit')
            number += 1
            record = state.process(raw, number)
            evidence.observe(raw, record)
            counts[record['kind']] += 1
            if record['kind'] in ('move', 'arc') and all(
                    x is not None for x in record['end_mm'].values()):
                known_ends += 1
            if record['kind'] == 'unknown':
                reason = record.get('reason', 'unknown')
                reasons[reason] += 1
                if len(examples) < max_examples:
                    examples.append({
                        'line': number,
                        'text': raw.rstrip('\r\n')[:200],
                        'reason': reason,
                    })
            f = FEATURE.match(raw.rstrip('\r\n'))
            if f:
                label = f.group(1)[:160]
                if label not in features and len(features) >= 512:
                    label = '<other>'
                features[label] += 1
            if LAYER.match(raw.rstrip('\r\n')):
                layer_comments += 1
            if raw.strip().split(';', 1)[0].strip().upper() == 'LAYER_MARK':
                layer_marks += 1
            obj = OBJECT.match(raw)
            if obj:
                objects[obj.group(1).upper()] += 1
    opts = state.options_summary()
    opts['assume_klipper_defaults'] = bool(assume_klipper_defaults)
    return {
        'assumed_passive_commands': sorted(state.assumed_passive),
        'trace_options': opts,
        'record_counts': dict(counts),
        'unknown_reasons': dict(reasons),
        'unknown_examples': examples,
        'moves_with_known_xyz_end': known_ends,
        'feature_comment_counts': dict(features),
        'layer_comment_count': layer_comments,
        'layer_mark_count': layer_marks,
        'object_command_counts': dict(objects),
        'evidence': evidence.finish(),
        'limits': [
            'comments are evidence, not verified feature classifications',
            'unknown commands invalidate tracked modal and coordinate state',
            'coordinates are logical, not machine positions',
            'opt-in trace capabilities are listed in trace_options; no print safety certified',
        ],
    }


def run(source, output, mode, *, timeout=120, max_bytes=DEFAULT_MAX_BYTES,
        assumed_passive=(), assume_klipper_defaults=False, enable_arcs=False,
        firmware_retract=False, klipper_passive=False,
        verified_r2_passive=False, machine_config=None):
    if mode not in ('report', 'audit', 'derive'):
        raise ValueError('unknown mode')
    has_trace_opts = bool(
        assumed_passive or assume_klipper_defaults or enable_arcs
        or firmware_retract or klipper_passive or verified_r2_passive
        or machine_config
    )
    if mode == 'derive' and has_trace_opts:
        raise ValueError('passive assumptions and analysis options are report/audit-only')
    if not 1 <= timeout <= 1800:
        raise ValueError('timeout must be 1..1800 seconds')
    if not 1 <= max_bytes <= 2 * 1024 ** 3:
        raise ValueError('max_bytes must be 1..2147483648')
    src = os.path.abspath(os.fspath(source))
    out = Path(output).absolute()
    want_ext = '.json' if mode in ('report', 'audit') else '.gcode'
    if out.name in ('', '.', '..') or out.suffix.lower() != want_ext:
        raise ValueError('output must end in .json (report/audit) or .gcode (derive)')
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
            report = {
                'schema': 'r2-offline/1',
                'mode': mode,
                'source': {'sha256': input_hash, 'bytes': size},
                'safety': 'experimental offline result; no printer safety certification',
            }
            if mode in ('report', 'audit'):
                use_defaults = assume_klipper_defaults or (mode == 'audit')
                use_arcs = enable_arcs or (mode == 'audit')
                use_fwret = firmware_retract or (mode == 'audit')
                use_kpass = klipper_passive or (mode == 'audit')
                use_r2pass = verified_r2_passive or (mode == 'audit')
                ana = analyse(
                    staged,
                    assumed_passive=assumed_passive,
                    assume_klipper_defaults=use_defaults,
                    enable_arcs=use_arcs,
                    firmware_retract=use_fwret,
                    klipper_passive=use_kpass,
                    verified_r2_passive=use_r2pass,
                )
                report['analysis'] = ana
                if mode == 'audit':
                    tag_geo = legacy.audit_tag_geometry(str(staged))
                    ev_audit = ana['evidence']['sequence_and_tag_audit']
                    seq_v = ev_audit['sequence_violations']
                    total_findings = (
                        len(seq_v)
                        + len(tag_geo['conflicts'])
                        + ana['evidence']['warning_count']
                    )
                    report['tag_geometry_audit'] = tag_geo
                    report['audit_summary'] = {
                        'status': 'clean' if total_findings == 0 else 'findings_present',
                        'sequence_violation_count': len(seq_v),
                        'tag_geometry_conflict_count': len(tag_geo['conflicts']),
                        'evidence_warning_count': ana['evidence']['warning_count'],
                        'unknown_command_count': ana['record_counts'].get('unknown', 0),
                    }
                if machine_config is not None:
                    import r2_machine
                    prof = r2_machine.load_machine_profile(machine_config)
                    mchk = r2_machine.check_evidence_against_profile(
                        ana['evidence'], prof)
                    report['machine_check'] = mchk
                    if mode == 'audit' and not mchk['ok']:
                        report['audit_summary']['status'] = 'findings_present'
                        report['audit_summary']['machine_violation_count'] = len(
                            mchk['violations'])
                product = Path(temp) / 'report.json'
                with product.open('x', encoding='utf8') as f:
                    json.dump(report, f, ensure_ascii=True, sort_keys=True, indent=2)
                    f.write('\n')
                    f.flush()
                    os.fsync(f.fileno())
            else:
                engine = Path(__file__).resolve().parent / 'r2_postproc_next.py'
                engine_hash = digest_file(engine)
                proc = subprocess.run(
                    [sys.executable, '-c', WORKER, str(engine.parent), str(staged)],
                    capture_output=True, text=True, timeout=timeout)
                if proc.returncode:
                    raise RuntimeError('processor failed: ' + proc.stderr[-2000:])
                if digest_file(engine) != engine_hash:
                    raise SourceChanged('processor changed during job')
                try:
                    summary = json.loads(proc.stdout)
                except json.JSONDecodeError as exc:
                    raise RuntimeError('processor did not return a summary') from exc
                if not isinstance(summary, dict) or not staged.is_file() or staged.is_symlink():
                    raise RuntimeError('processor output or summary invalid')
                if staged.stat().st_size <= 0 or staged.stat().st_size > max_bytes * 2:
                    raise ValueError('processor output empty or exceeds output limit')
                with staged.open('rb') as f:
                    os.fsync(f.fileno())
                report['engine'] = {
                    'file': engine.name, 'sha256': engine_hash,
                    'retract_rewrite': False,
                }
                report['output'] = {
                    'sha256': digest_file(staged),
                    'bytes': staged.stat().st_size,
                }
                report['summary'] = summary
                product = staged
            _verify_source(fd, src, before, input_hash)
            os.link(product, out.name, dst_dir_fd=dfd, follow_symlinks=False)
            os.fsync(dfd)
            return report
    finally:
        if fd is not None:
            os.close(fd)
        os.close(dfd)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mode', choices=('report', 'audit', 'derive'))
    parser.add_argument('source')
    parser.add_argument('output', help='new .json or .gcode path; never overwritten')
    parser.add_argument('--timeout', type=int, default=120,
                        help='derive worker timeout seconds (1..1800)')
    parser.add_argument('--max-bytes', type=int, default=DEFAULT_MAX_BYTES)
    parser.add_argument('--assume-klipper-defaults', action='store_true',
                        help='report/audit only: assume G21/G90/M82 at entry')
    parser.add_argument('--enable-arcs', action='store_true',
                        help='report/audit only: model G17 XY I/J G2/G3 arcs')
    parser.add_argument('--firmware-retract', action='store_true',
                        help='report/audit only: model G10/G11 firmware retraction')
    parser.add_argument('--klipper-passive', action='store_true',
                        help='report/audit only: allow non-motion Klipper status/object commands')
    parser.add_argument('--verified-r2-passive', action='store_true',
                        help='report/audit only: allow _FILE_INFO, LAYER_MARK, APPLY_TYPE')
    parser.add_argument('--machine-config', default=None, metavar='CFG',
                        help='report/audit only: read-only Klipper config file for bounds/capability check')
    parser.add_argument('--assume-passive', action='append', default=[], metavar='COMMAND',
                        help='report/audit only: assume command has no tracked effects; repeatable')
    args = parser.parse_args(argv)
    try:
        result = run(
            args.source, args.output, args.mode,
            timeout=args.timeout,
            max_bytes=args.max_bytes,
            assumed_passive=args.assume_passive,
            assume_klipper_defaults=args.assume_klipper_defaults,
            enable_arcs=args.enable_arcs,
            firmware_retract=args.firmware_retract,
            klipper_passive=args.klipper_passive,
            verified_r2_passive=args.verified_r2_passive,
            machine_config=args.machine_config,
        )
    except (OSError, ValueError, RuntimeError, subprocess.TimeoutExpired) as exc:
        print('r2-offline: %s' % exc, file=sys.stderr)
        return 1
    print(json.dumps(result, ensure_ascii=True, sort_keys=True))
    return 0


if __name__ == '__main__':
    sys.exit(main())
