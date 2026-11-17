#!/usr/bin/env python3
"""Pass 11 sidecar writer for the R2 G-code reverse-engineering pipeline.

The master concept (Pass 11, sections 11-12) demands an analysis sidecar
*before* any derived output: the source file stays byte-identical, nothing is
executed, and the result records provenance, evidence and limits explicitly.

This tool is read-only with respect to the source. It:

  1. snapshots the source exactly like ``r2_offline.run`` (no-follow open,
     SHA-256, identity re-check before and after analysis),
  2. runs the shadow interpreter + Pass 3-10 evidence tracker
     (``r2_offline.analyse``) with the caller's explicit opt-in flags,
  3. optionally embeds one record per move/arc (``--moves``), capped by
     ``--max-move-records`` and flagged as truncated when the cap is hit,
  4. publishes a new ``r2-sidecar/1`` JSON document next to the destination
     directory via atomic hard link - an existing destination is never
     overwritten,
  5. stamps the document with a ``payload_sha256`` over all other fields so a
     reader can detect accidental or hostile tampering with the evidence.

It never writes the source, never overwrites an existing file, starts no
watcher, executes nothing, and certifies nothing about printer safety.
"""
import argparse
import datetime
import hashlib
import json
import os
from pathlib import Path
import sys
import tempfile

import r2_offline
import r2_version

CHUNK = 1024 * 1024
SCHEMA = 'r2-sidecar/1'
DEFAULT_MAX_MOVE_RECORDS = 100000


def _count_lines(path):
    lines = 0
    with open(path, 'rb') as handle:
        while True:
            data = handle.read(CHUNK)
            if not data:
                break
            lines += data.count(b'\n')
    return lines


def _canonical(payload):
    return json.dumps(payload, ensure_ascii=True, sort_keys=True,
                      separators=(',', ':')).encode('utf-8')


def payload_digest(report_without_integrity):
    return hashlib.sha256(_canonical(report_without_integrity)).hexdigest()


def build_sidecar(staged_path, source_sha256, source_bytes, *,
                  created_utc=None, label=None, include_moves=False,
                  max_move_records=DEFAULT_MAX_MOVE_RECORDS,
                  assumed_passive=(), assume_klipper_defaults=False,
                  enable_arcs=False, firmware_retract=False,
                  klipper_passive=False, verified_r2_passive=False,
                  machine_config=None):
    """Build the sidecar document for an already staged snapshot."""
    moves = [] if include_moves else None
    analysis = r2_offline.analyse(
        staged_path,
        assumed_passive=assumed_passive,
        assume_klipper_defaults=assume_klipper_defaults,
        enable_arcs=enable_arcs,
        firmware_retract=firmware_retract,
        klipper_passive=klipper_passive,
        verified_r2_passive=verified_r2_passive,
        move_sink=moves,
        max_move_records=(max_move_records if include_moves else None),
    )
    if created_utc is None:
        created_utc = datetime.datetime.now(datetime.timezone.utc).strftime(
            '%Y-%m-%dT%H:%M:%SZ')
    report = {
        'schema': SCHEMA,
        'created_utc': created_utc,
        'generator': {
            'tool': 'tools/r2_sidecar.py',
            'tool_version': r2_version.VERSION,
            'postproc_build': r2_version.BUILD,
            'python': sys.version.split()[0],
        },
        'source': {
            'sha256': source_sha256,
            'bytes': source_bytes,
            'lines': _count_lines(staged_path),
            'label': label,
        },
        'trace_options': analysis['trace_options'],
        'analysis': analysis,
        'moves': moves if include_moves else None,
        'moves_meta': analysis['moves_meta'],
        'limits': [
            'source file is never modified; this sidecar is a separate document',
            'comments and tags are evidence, not verified feature classifications',
            'coordinates are logical G-code values, not machine positions',
            'unknown commands invalidate tracked modal and coordinate state',
            'opt-in trace capabilities are listed in trace_options; nothing here certifies printer safety',
            'roles are unverified comments or R2 markers; UNKNOWN/AMBIGUOUS are honest results, not errors',
        ],
    }
    if machine_config is not None:
        import r2_machine
        profile = r2_machine.load_machine_profile(machine_config)
        report['machine_check'] = r2_machine.check_evidence_against_profile(
            analysis['evidence'], profile)
    digest = payload_digest(report)
    report['integrity'] = {
        'algorithm': 'sha256',
        'scope': 'all fields except integrity',
        'payload_sha256': digest,
    }
    return report


def verify_sidecar(path):
    """Re-check a sidecar document; return (ok, problems)."""
    problems = []
    try:
        with open(path, 'rb') as handle:
            raw = handle.read()
        doc = json.loads(raw.decode('utf-8'))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        return False, ['unreadable sidecar: %s' % exc]
    if doc.get('schema') != SCHEMA:
        problems.append('schema mismatch: %r' % doc.get('schema'))
    integrity = doc.get('integrity')
    if not isinstance(integrity, dict) or 'payload_sha256' not in integrity:
        problems.append('integrity block missing')
    else:
        body = {k: v for k, v in doc.items() if k != 'integrity'}
        if payload_digest(body) != integrity['payload_sha256']:
            problems.append('payload hash mismatch; document was modified or corrupted')
    analysis = doc.get('analysis')
    if not isinstance(analysis, dict) or 'evidence' not in analysis:
        problems.append('analysis/evidence block missing')
    source = doc.get('source')
    if not isinstance(source, dict) or not source.get('sha256'):
        problems.append('source fingerprint missing')
    return (not problems), problems


def run(source, output, *, include_moves=False,
        max_move_records=DEFAULT_MAX_MOVE_RECORDS,
        assumed_passive=(), assume_klipper_defaults=False,
        enable_arcs=False, firmware_retract=False,
        klipper_passive=False, verified_r2_passive=False,
        machine_config=None, label=None, created_utc=None,
        max_bytes=r2_offline.DEFAULT_MAX_BYTES):
    if max_move_records < 1:
        raise ValueError('max_move_records must be >= 1')
    if not hasattr(os, 'O_DIRECTORY') or not hasattr(os, 'O_NOFOLLOW'):
        raise OSError('required safe OS flags are unavailable')
    src = os.path.abspath(os.fspath(source))
    out = Path(output).absolute()
    if out.name in ('', '.', '..') or out.suffix.lower() != '.json':
        raise ValueError('output must end in .json')
    parent = out.parent.resolve(strict=True)
    dfd = os.open(parent, os.O_RDONLY | os.O_DIRECTORY)
    fd = None
    try:
        fd = r2_offline._open_source(src)
        with tempfile.TemporaryDirectory(prefix='.r2-sidecar-', dir=parent) as temp:
            staged = Path(temp) / 'snapshot.gcode'
            before, input_hash, size = r2_offline._snapshot(
                fd, src, staged, max_bytes)
            sidecar = build_sidecar(
                staged, input_hash, size,
                created_utc=created_utc,
                label=label if label is not None else os.path.basename(src),
                include_moves=include_moves,
                max_move_records=max_move_records,
                assumed_passive=assumed_passive,
                assume_klipper_defaults=assume_klipper_defaults,
                enable_arcs=enable_arcs,
                firmware_retract=firmware_retract,
                klipper_passive=klipper_passive,
                verified_r2_passive=verified_r2_passive,
                machine_config=machine_config,
            )
            product = Path(temp) / 'sidecar.json'
            with product.open('x', encoding='utf8') as handle:
                json.dump(sidecar, handle, ensure_ascii=True, sort_keys=True,
                          indent=2)
                handle.write('\n')
                handle.flush()
                os.fsync(handle.fileno())
            r2_offline._verify_source(fd, src, before, input_hash)
            # Atomic publish; fails if the destination exists (never overwrite).
            os.link(product, out.name, dst_dir_fd=dfd, follow_symlinks=False)
            os.fsync(dfd)
            return sidecar
    finally:
        if fd is not None:
            os.close(fd)
        os.close(dfd)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source', help='G-code file, opened for reading only')
    parser.add_argument('output', help='new .json sidecar path; never overwritten')
    parser.add_argument('--moves', action='store_true',
                        help='embed one compact record per move/arc (can be large)')
    parser.add_argument('--max-move-records', type=int,
                        default=DEFAULT_MAX_MOVE_RECORDS,
                        help='cap for --moves embedded records (default %(default)s)')
    parser.add_argument('--label', default=None,
                        help='provenance label (default: source basename)')
    parser.add_argument('--assume-klipper-defaults', action='store_true',
                        help='assume G21/G90/M82 at entry; not proof of machine state')
    parser.add_argument('--enable-arcs', action='store_true',
                        help='model G17 XY I/J G2/G3 arcs; fail closed otherwise')
    parser.add_argument('--firmware-retract', action='store_true',
                        help='model G10/G11 as Klipper firmware retraction')
    parser.add_argument('--klipper-passive', action='store_true',
                        help='treat known non-motion Klipper commands as passive')
    parser.add_argument('--verified-r2-passive', action='store_true',
                        help='treat _FILE_INFO/LAYER_MARK/APPLY_TYPE as passive')
    parser.add_argument('--assume-passive', action='append', default=[],
                        metavar='COMMAND',
                        help='assume command has no tracked effects; repeatable')
    parser.add_argument('--machine-config', default=None, metavar='CFG',
                        help='optional read-only Klipper config for bounds check')
    parser.add_argument('--max-bytes', type=int, default=r2_offline.DEFAULT_MAX_BYTES)
    args = parser.parse_args(argv)
    try:
        sidecar = run(
            args.source, args.output,
            include_moves=args.moves,
            max_move_records=args.max_move_records,
            assumed_passive=args.assume_passive,
            assume_klipper_defaults=args.assume_klipper_defaults,
            enable_arcs=args.enable_arcs,
            firmware_retract=args.firmware_retract,
            klipper_passive=args.klipper_passive,
            verified_r2_passive=args.verified_r2_passive,
            machine_config=args.machine_config,
            label=args.label,
            max_bytes=args.max_bytes,
        )
    except (OSError, ValueError, RuntimeError) as exc:
        print('r2-sidecar: %s' % exc, file=sys.stderr)
        return 1
    print(json.dumps({
        'schema': sidecar['schema'],
        'output': str(Path(args.output).absolute()),
        'source_sha256': sidecar['source']['sha256'],
        'moves_embedded': sidecar['moves_meta']['records'],
        'moves_truncated': sidecar['moves_meta']['truncated'],
        'payload_sha256': sidecar['integrity']['payload_sha256'],
    }, ensure_ascii=True, sort_keys=True))
    return 0


if __name__ == '__main__':
    sys.exit(main())
