#!/usr/bin/env python3
"""Build/validate a deterministic source review archive, never an update ZIP.

Tracked workspace files and designated new work files are archived as they
exist, including uncommitted edits. The archive is not installed, published,
or called a production release. Rebuild requires git and a clean destination.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import subprocess
import sys
import tempfile
import zipfile

ROOT = Path(__file__).resolve().parents[1]
NOTICE = ('R2 REVIEW BUILD ONLY - NOT AN UPDATE PACKAGE\n'
          'Do not install or print from this archive. The overall rebuild,\n'
          'integration, hardware testing and safety acceptance are incomplete.\n'
          'See source/analyse/REVIEW-BUILD-V2.md.\n').encode()
MANIFEST = 'MANIFEST.json'
NOTICE_NAME = 'REVIEW_ONLY_DO_NOT_INSTALL.txt'
NEW_PREFIXES = ('analyse/', 'backups/', 'tools/')
MAX_FILES = 10000
MAX_BYTES = 128 * 1024 * 1024


def sha(data): return hashlib.sha256(data).hexdigest()


def git_output(root, *args):
    return subprocess.check_output(['git', '-C', str(root), *args])


def source_paths(root):
    tracked = set(git_output(root, 'ls-files', '-z').decode('utf8').split('\0')) - {''}
    other = set(git_output(root, 'ls-files', '--others', '--exclude-standard', '-z').decode('utf8').split('\0')) - {''}
    candidates = tracked | {p for p in other if p.startswith(NEW_PREFIXES)}
    paths = []
    for path in sorted(candidates):
        if path.startswith('releases/') or path.startswith('.git/'):
            continue
        # Release-ZIPs are build artifacts, not review source: a large ZIP at
        # the repo root would blow the archive size limit. Exclude the same
        # pattern build_release_zip.py produces.
        if (PurePosixPath(path).parent.as_posix() == '.'
                and PurePosixPath(path).name.startswith('klipper-e3-r2d2-UPDATE-')
                and PurePosixPath(path).name.endswith('.zip')):
            continue
        p = PurePosixPath(path)
        if p.is_absolute() or '..' in p.parts or '\\' in path:
            raise ValueError('invalid source path')
        full = root / path
        if full.is_symlink() or not full.is_file():
            raise ValueError('source is missing or not a regular file: ' + path)
        paths.append(path)
    return paths


def entry(name, data, executable=False):
    info = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
    info.create_system = 3
    info.compress_type = zipfile.ZIP_DEFLATED
    info.external_attr = (0o100755 if executable else 0o100644) << 16
    return info, data


def build(root, output):
    root = Path(root).resolve(strict=True)
    output = Path(output).absolute()
    if output.suffix.lower() != '.zip': raise ValueError('output must be a .zip')
    if output.exists() or output.is_symlink(): raise FileExistsError(str(output))
    output.parent.mkdir(parents=True, exist_ok=True)
    paths = source_paths(root)
    revision = git_output(root, 'rev-parse', 'HEAD').decode().strip()
    content = {}
    total = 0
    if len(paths) > MAX_FILES - 2: raise ValueError('too many source files')
    for path in paths:
        full = root / path
        size = full.stat().st_size
        total += size
        if total > MAX_BYTES: raise ValueError('source exceeds review archive size limit')
        data = full.read_bytes()
        if len(data) != size: raise ValueError('source changed during build: ' + path)
        content['source/' + path] = (data, bool(full.stat().st_mode & 0o111))
    content[NOTICE_NAME] = (NOTICE, False)
    manifest = {'format': 'r2-review-source/1', 'base_commit': revision,
                'status': 'review only; incomplete; do not install',
                'files': {name: {'sha256': sha(data), 'bytes': len(data)}
                          for name, (data, _) in sorted(content.items())}}
    manifest_data = (json.dumps(manifest, sort_keys=True, indent=2) + '\n').encode()
    tmp = None
    try:
        fd, tmp = tempfile.mkstemp(prefix='.review-build-', suffix='.tmp', dir=output.parent)
        with os.fdopen(fd, 'w+b') as file:
            with zipfile.ZipFile(file, 'w', compression=zipfile.ZIP_DEFLATED, compresslevel=9) as z:
                for name, (data, executable) in sorted(content.items()):
                    info, value = entry(name, data, executable)
                    z.writestr(info, value, compresslevel=9)
                info, value = entry(MANIFEST, manifest_data)
                z.writestr(info, value, compresslevel=9)
            file.flush(); os.fsync(file.fileno())
        validate(tmp)
        os.link(tmp, output, follow_symlinks=False)  # atomic no overwrite
        return manifest
    finally:
        if tmp is not None:
            try: os.unlink(tmp)
            except FileNotFoundError: pass


def validate(path):
    with zipfile.ZipFile(path) as z:
        names = z.namelist()
        if len(names) > MAX_FILES or sum(i.file_size for i in z.infolist()) > MAX_BYTES:
            raise ValueError('archive exceeds validation limits')
        if len(names) != len(set(names)) or MANIFEST not in names:
            raise ValueError('duplicate entry or missing manifest')
        for name in names:
            p = PurePosixPath(name)
            if (p.is_absolute() or '..' in p.parts or '\\' in name
                    or name not in (MANIFEST, NOTICE_NAME) and not name.startswith('source/')):
                raise ValueError('unsafe entry name')
        doc = json.loads(z.read(MANIFEST))
        if doc.get('format') != 'r2-review-source/1' or doc.get('status') != 'review only; incomplete; do not install':
            raise ValueError('invalid manifest metadata')
        files = doc.get('files')
        if not isinstance(files, dict) or set(names) != set(files) | {MANIFEST}:
            raise ValueError('manifest entry set differs')
        if z.read(NOTICE_NAME) != NOTICE:
            raise ValueError('review notice missing or modified')
        for name, metadata in files.items():
            data = z.read(name)
            if len(data) != metadata.get('bytes') or sha(data) != metadata.get('sha256'):
                raise ValueError('manifest mismatch: ' + name)
    return doc


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=('build', 'verify'))
    parser.add_argument('archive')
    args = parser.parse_args()
    try:
        doc = build(ROOT, args.archive) if args.command == 'build' else validate(args.archive)
        data = Path(args.archive).read_bytes()
        print(json.dumps({'archive': args.archive, 'sha256': sha(data), 'bytes': len(data),
                          'files': len(doc['files']), 'status': doc['status']}, sort_keys=True))
    except (OSError, ValueError, KeyError, zipfile.BadZipFile, subprocess.CalledProcessError) as exc:
        print('review build: %s' % exc, file=sys.stderr)
        return 1
    return 0

if __name__ == '__main__': sys.exit(main())
