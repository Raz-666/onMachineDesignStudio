#!/usr/bin/env python3
"""Non-destructive original-file archive, output validator, and job lifecycle service.

Implements the offline-verifiable File/Job Service layer from the target
architecture without altering live Klipper/Moonraker wire contracts:
  - OriginalArchive: preserves untouched source G-code files with SHA-256
    verification and atomic fsync writes before in-place mutations; enforces
    strict containment inside root_dir and refuses protected image files.
  - validate_job_output: verifies generated G-code and binary STL outputs
    (existence, size, binary STL layout + float finiteness, G-code NUL/NaN/Inf
    absence, EXCLUDE_OBJECT start/end balance, root containment).
  - JobRegistry: thread-safe structured job state machine
    (queued -> running -> validating -> succeeded | failed | cancelled | stuck)
    with duplicate-key suppression and bounded JSON-serializable history.
"""
from collections import OrderedDict
import hashlib
import json
import math
import os
from pathlib import Path
import re
import struct
import tempfile
import threading
import time

PROTECTED_IMAGE_EXTENSIONS = frozenset({
    '.png', '.jpg', '.jpeg', '.bmp', '.gif', '.webp', '.tif', '.tiff',
    '.pgm', '.ppm', '.pbm', '.pnm', '.svg', '.ico', '.heic', '.heif', '.avif',
})

JOB_STATES = frozenset({
    'queued', 'running', 'validating',
    'succeeded', 'failed', 'cancelled', 'stuck',
})
TERMINAL_JOB_STATES = frozenset({'succeeded', 'failed', 'cancelled'})
_ALLOWED_TRANSITIONS = {
    'queued': frozenset({'running', 'cancelled', 'failed'}),
    'running': frozenset({'validating', 'succeeded', 'failed',
                          'cancelled', 'stuck'}),
    'validating': frozenset({'succeeded', 'failed', 'cancelled'}),
    'stuck': frozenset({'failed', 'cancelled'}),
    'succeeded': frozenset(),
    'failed': frozenset(),
    'cancelled': frozenset(),
}

_NONFINITE_TOKEN_RE = re.compile(
    r'(?:^|[\s=+-]|\b[A-Z][+-]?)(?:nan|inf|infinity)(?:\b|$)', re.I)
_EO_START_RE = re.compile(r'^\s*EXCLUDE_OBJECT_START\s+NAME=(\S+)')
_EO_END_RE = re.compile(r'^\s*EXCLUDE_OBJECT_END(?:\s+NAME=(\S+))?')
_EO_DEF_RE = re.compile(r'^\s*EXCLUDE_OBJECT_DEFINE\s+NAME=(\S+)')


def sha256_file(path):
    h = hashlib.sha256()
    size = 0
    with open(path, 'rb') as fh:
        while True:
            chunk = fh.read(65536)
            if not chunk:
                break
            h.update(chunk)
            size += len(chunk)
    return h.hexdigest(), size


def is_protected_image(path):
    name = os.path.basename(str(path)).lower()
    _, ext = os.path.splitext(name)
    return ext in PROTECTED_IMAGE_EXTENSIONS


def atomic_write_bytes(dst_path, data):
    dst = Path(dst_path)
    dst.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix='.r2atomic_', suffix='.tmp',
                               dir=str(dst.parent))
    try:
        with os.fdopen(fd, 'wb') as fh:
            fh.write(data)
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp, str(dst))
    except Exception:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def atomic_copy_file(src_path, dst_path):
    """Stream-copy src_path to dst_path atomically with fsync; returns (sha256, size)."""
    dst = Path(dst_path)
    dst.parent.mkdir(parents=True, exist_ok=True)
    h = hashlib.sha256()
    size = 0
    fd, tmp = tempfile.mkstemp(prefix='.r2orig_', suffix='.tmp',
                               dir=str(dst.parent))
    try:
        with open(src_path, 'rb') as inp, os.fdopen(fd, 'wb') as out:
            while True:
                chunk = inp.read(65536)
                if not chunk:
                    break
                h.update(chunk)
                size += len(chunk)
                out.write(chunk)
            out.flush()
            os.fsync(out.fileno())
        os.replace(tmp, str(dst))
    except Exception:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise
    return h.hexdigest(), size


def _resolve_inside(root_dir, target_path):
    root = Path(root_dir).resolve(strict=True)
    p = Path(target_path)
    if not p.is_absolute():
        p = root / p
    # Reject symlinks directly on the target before resolving
    if p.is_symlink():
        raise ValueError(f'symlink target refused: {target_path}')
    resolved = p.resolve(strict=False)
    try:
        rel = resolved.relative_to(root)
    except ValueError as exc:
        raise ValueError(
            f'path escapes root {root}: {target_path}') from exc
    if not rel.parts:
        raise ValueError('empty relative path')
    return root, resolved, rel.as_posix()


class OriginalArchive:
    """Non-destructive sidecar archive storing verified untouched source files."""

    SCHEMA = 'r2-originals/1'

    def __init__(self, root_dir, archive_dirname='.r2_originals'):
        if not archive_dirname.startswith('.') or '/' in archive_dirname \
                or '\\' in archive_dirname or archive_dirname in ('.', '..'):
            raise ValueError(
                'archive_dirname must be a single hidden directory name')
        self.root = Path(root_dir).resolve(strict=True)
        self.archive_dirname = archive_dirname
        self.archive_dir = self.root / archive_dirname
        self.blobs_dir = self.archive_dir / 'blobs'
        self.manifest_path = self.archive_dir / 'manifest.json'
        self._lock = threading.Lock()

    def _load_manifest_unlocked(self):
        if not self.manifest_path.is_file():
            return {'schema': self.SCHEMA, 'entries': {}}
        data = json.loads(self.manifest_path.read_text(encoding='utf-8'))
        if data.get('schema') != self.SCHEMA \
                or not isinstance(data.get('entries'), dict):
            raise ValueError('invalid original archive manifest')
        return data

    def _save_manifest_unlocked(self, data):
        raw = (json.dumps(data, indent=2, sort_keys=True, ensure_ascii=True)
               + '\n').encode('utf-8')
        atomic_write_bytes(self.manifest_path, raw)

    def preserve(self, target_path, overwrite_entry=False):
        """Preserve target_path before an in-place modification.

        If an original is already recorded for rel_path and overwrite_entry is
        False, keeps the FIRST untouched original intact (so repeated rewrites
        never clobber the true pre-processing upload).
        """
        _, resolved, rel = _resolve_inside(self.root, target_path)
        if rel.split('/', 1)[0] == self.archive_dirname:
            raise ValueError('refusing to archive internal archive files')
        if is_protected_image(resolved):
            raise ValueError(
                f'protected image file must never enter G-code mutation flow: {rel}')
        if not resolved.is_file():
            raise FileNotFoundError(f'source file not found: {rel}')

        with self._lock:
            manifest = self._load_manifest_unlocked()
            existing = manifest['entries'].get(rel)
            if existing and not overwrite_entry:
                blob = self.blobs_dir / existing['blob']
                if blob.is_file():
                    got_sha, got_sz = sha256_file(blob)
                    if (got_sha == existing['sha256']
                            and got_sz == existing['bytes']):
                        return dict(existing, already_preserved=True)

            digest, size = sha256_file(resolved)
            blob_name = f'{digest}.orig'
            blob_path = self.blobs_dir / blob_name
            if not blob_path.is_file():
                copied_sha, copied_sz = atomic_copy_file(resolved, blob_path)
                if copied_sha != digest or copied_sz != size:
                    raise IOError('source changed while archiving original')
            entry = {
                'rel_path': rel,
                'sha256': digest,
                'bytes': size,
                'blob': blob_name,
                'preserved_at': round(time.time(), 3),
            }
            manifest['entries'][rel] = entry
            self._save_manifest_unlocked(manifest)
            return dict(entry, already_preserved=False)

    def restore(self, rel_path, dst_path=None):
        """Atomically restore a preserved original to dst_path (or original path)."""
        _, orig_resolved, rel = _resolve_inside(self.root, rel_path)
        if dst_path is None:
            target = orig_resolved
        else:
            _, target, _ = _resolve_inside(self.root, dst_path)
        if is_protected_image(target):
            raise ValueError(f'refusing to overwrite protected image: {target}')
        with self._lock:
            manifest = self._load_manifest_unlocked()
            entry = manifest['entries'].get(rel)
            if not entry:
                raise KeyError(f'no preserved original for {rel}')
            blob = self.blobs_dir / entry['blob']
            if not blob.is_file():
                raise FileNotFoundError(f'archived blob missing for {rel}')
            got_sha, got_sz = sha256_file(blob)
            if got_sha != entry['sha256'] or got_sz != entry['bytes']:
                raise ValueError(f'archived blob hash mismatch for {rel}')
            out_sha, out_sz = atomic_copy_file(blob, target)
            if out_sha != entry['sha256'] or out_sz != entry['bytes']:
                raise IOError(f'restored file verification failed for {rel}')
            return str(target)

    def verify(self):
        """Verify all archived blobs against manifest hashes."""
        with self._lock:
            manifest = self._load_manifest_unlocked()
            checked = 0
            errors = []
            for rel, entry in sorted(manifest['entries'].items()):
                checked += 1
                blob = self.blobs_dir / str(entry.get('blob', ''))
                if not blob.is_file():
                    errors.append(f'{rel}: missing blob {entry.get("blob")}')
                    continue
                got_sha, got_sz = sha256_file(blob)
                if got_sha != entry.get('sha256') or got_sz != entry.get('bytes'):
                    errors.append(f'{rel}: sha256/size mismatch')
            return {'ok': not errors, 'checked': checked, 'errors': errors}


def _validate_binary_stl(path, size):
    errors = []
    if size < 84:
        return ['binary STL shorter than 84-byte header']
    with open(path, 'rb') as fh:
        hdr = fh.read(84)
        n_tri = struct.unpack('<I', hdr[80:84])[0]
        expected = 84 + 50 * n_tri
        if n_tri == 0:
            errors.append('binary STL contains 0 triangles')
        if size != expected:
            errors.append(
                f'binary STL size {size} != expected {expected} ({n_tri} tris)')
            return errors
        for idx in range(n_tri):
            rec = fh.read(50)
            if len(rec) != 50:
                errors.append(f'truncated facet at index {idx}')
                break
            vals = struct.unpack('<12f', rec[:48])
            if not all(math.isfinite(v) for v in vals):
                errors.append(f'non-finite float in facet {idx}')
                break
            ax, ay, az, bx, by, bz, cx, cy, cz = vals[3:12]
            ux, uy, uz = bx - ax, by - ay, bz - az
            vx, vy, vz = cx - ax, cy - ay, cz - az
            area2 = math.sqrt(
                (uy * vz - uz * vy) ** 2
                + (uz * vx - ux * vz) ** 2
                + (ux * vy - uy * vx) ** 2)
            if area2 < 1e-12:
                errors.append(f'degenerate zero-area facet at index {idx}')
                break
    return errors


def _validate_text_gcode(path):
    errors = []
    cmd_lines = 0
    eo_defs = set()
    eo_open = None
    eo_starts = 0
    eo_ends = 0
    with open(path, 'rb') as fh:
        for lno, raw in enumerate(fh, 1):
            if b'\x00' in raw:
                errors.append(f'line {lno}: NUL byte in G-code')
                break
            line = raw.decode('utf-8', errors='replace').rstrip('\r\n')
            ls = line.strip()
            if not ls or ls.startswith(';'):
                continue
            code = ls.split(';', 1)[0].strip()
            if not code:
                continue
            cmd_lines += 1
            # Skip quoted RESPOND/NOTIFY/M117 prose when checking NaN/Inf tokens
            head_cmd = code.split(None, 1)[0].upper()
            if head_cmd not in ('RESPOND', 'NOTIFY', 'M117', 'M118',
                                '_FILE_INFO', 'EXCLUDE_OBJECT_DEFINE',
                                'EXCLUDE_OBJECT_START', 'EXCLUDE_OBJECT_END'):
                if _NONFINITE_TOKEN_RE.search(code):
                    errors.append(f'line {lno}: non-finite token in command')
                    break
            md = _EO_DEF_RE.match(code)
            if md:
                eo_defs.add(md.group(1))
                continue
            ms = _EO_START_RE.match(code)
            if ms:
                eo_starts += 1
                nm = ms.group(1)
                if eo_defs and nm not in eo_defs:
                    errors.append(
                        f'line {lno}: EXCLUDE_OBJECT_START {nm} not defined')
                    break
                eo_open = nm
                continue
            me = _EO_END_RE.match(code)
            if me:
                eo_ends += 1
                nm = me.group(1)
                if nm and eo_open and nm != eo_open:
                    errors.append(
                        f'line {lno}: EXCLUDE_OBJECT_END {nm} != open {eo_open}')
                    break
                eo_open = None
    if cmd_lines == 0 and not errors:
        errors.append('G-code contains zero executable commands')
    if eo_starts != eo_ends and not errors:
        errors.append(
            f'unbalanced EXCLUDE_OBJECT ({eo_starts} starts vs {eo_ends} ends)')
    return errors


def validate_job_output(path, root_dir=None):
    """Validate a single job output artifact without modifying it."""
    p_str = str(path or '')
    errors = []
    if not p_str:
        return {'ok': False, 'path': p_str, 'kind': 'missing',
                'bytes': 0, 'sha256': None, 'errors': ['empty output path']}
    p = Path(p_str)
    if root_dir is not None:
        try:
            _, p, _ = _resolve_inside(root_dir, p)
        except ValueError as exc:
            return {'ok': False, 'path': p_str, 'kind': 'invalid',
                    'bytes': 0, 'sha256': None, 'errors': [str(exc)]}
    elif p.is_symlink():
        return {'ok': False, 'path': p_str, 'kind': 'symlink',
                'bytes': 0, 'sha256': None,
                'errors': [f'symlink output refused: {p_str}']}
    if is_protected_image(p):
        return {'ok': False, 'path': str(p), 'kind': 'protected_image',
                'bytes': 0, 'sha256': None,
                'errors': [f'protected image must not be a job output: {p.name}']}
    if not p.is_file():
        return {'ok': False, 'path': str(p), 'kind': 'missing',
                'bytes': 0, 'sha256': None,
                'errors': [f'output file missing: {p}']}
    digest, size = sha256_file(p)
    if size <= 0:
        return {'ok': False, 'path': str(p), 'kind': 'empty',
                'bytes': 0, 'sha256': digest,
                'errors': [f'output file is empty: {p.name}']}
    low = p.name.lower()
    if low.endswith('.stl') or low.endswith('.stl.gcode'):
        kind = 'stl'
        errors.extend(_validate_binary_stl(p, size))
    elif low.endswith(('.gcode', '.gco', '.g')):
        kind = 'gcode'
        errors.extend(_validate_text_gcode(p))
    else:
        kind = 'other'
    return {
        'ok': not errors,
        'path': str(p),
        'kind': kind,
        'bytes': size,
        'sha256': digest,
        'errors': errors,
    }


class JobRegistry:
    """Thread-safe structured lifecycle tracker for background/offline jobs."""

    def __init__(self, max_history=64):
        self.max_history = max(8, int(max_history))
        self._lock = threading.Lock()
        self._seq = 0
        self._jobs = OrderedDict()     # job_id -> record dict
        self._active_by_key = {}       # key -> job_id

    def enqueue(self, name, key, ram_min_mb=60):
        """Register a queued job; returns (job_id, accepted_bool)."""
        key = str(key)
        with self._lock:
            existing_id = self._active_by_key.get(key)
            if existing_id is not None:
                rec = self._jobs.get(existing_id)
                if rec and rec['state'] not in TERMINAL_JOB_STATES:
                    return existing_id, False
                self._active_by_key.pop(key, None)
            self._seq += 1
            jid = f'job-{self._seq:06d}'
            now = round(time.time(), 3)
            self._jobs[jid] = {
                'job_id': jid,
                'name': str(name),
                'key': key,
                'state': 'queued',
                'ram_min_mb': int(ram_min_mb),
                'created_at': now,
                'started_at': None,
                'finished_at': None,
                'outputs': [],
                'validation': [],
                'error': None,
            }
            self._active_by_key[key] = jid
            self._trim_unlocked()
            return jid, True

    def _trim_unlocked(self):
        if len(self._jobs) <= self.max_history:
            return
        drop = []
        for jid, rec in self._jobs.items():
            if len(self._jobs) - len(drop) <= self.max_history:
                break
            if rec['state'] in TERMINAL_JOB_STATES:
                drop.append(jid)
        for jid in drop:
            self._jobs.pop(jid, None)

    def transition(self, job_id, new_state, *, error=None, outputs=None,
                   validation=None):
        """Move job_id to new_state, enforcing allowed lifecycle transitions."""
        if new_state not in JOB_STATES:
            raise ValueError(f'unknown job state: {new_state!r}')
        with self._lock:
            rec = self._jobs.get(job_id)
            if rec is None:
                raise KeyError(f'unknown job_id: {job_id!r}')
            cur = rec['state']
            if new_state not in _ALLOWED_TRANSITIONS[cur]:
                raise ValueError(
                    f'illegal job transition {cur!r} -> {new_state!r}')
            now = round(time.time(), 3)
            rec['state'] = new_state
            if new_state == 'running' and rec['started_at'] is None:
                rec['started_at'] = now
            if outputs is not None:
                rec['outputs'] = [str(o) for o in outputs]
            if validation is not None:
                rec['validation'] = list(validation)
            if error is not None:
                rec['error'] = str(error)
            if new_state in TERMINAL_JOB_STATES:
                rec['finished_at'] = now
                if self._active_by_key.get(rec['key']) == job_id:
                    self._active_by_key.pop(rec['key'], None)
            return dict(rec)

    def active_job_for_key(self, key):
        with self._lock:
            jid = self._active_by_key.get(str(key))
            if jid is None:
                return None
            rec = self._jobs.get(jid)
            if not rec or rec['state'] in TERMINAL_JOB_STATES:
                return None
            return dict(rec)

    def get(self, job_id):
        with self._lock:
            rec = self._jobs.get(job_id)
            return dict(rec) if rec else None

    def snapshot(self):
        with self._lock:
            jobs = [dict(r, outputs=list(r['outputs']),
                         validation=list(r['validation']))
                    for r in self._jobs.values()]
            counts = {}
            for r in jobs:
                counts[r['state']] = counts.get(r['state'], 0) + 1
            return {
                'schema': 'r2-jobs/1',
                'total_recorded': len(jobs),
                'active_keys': sorted(self._active_by_key.keys()),
                'counts': counts,
                'jobs': jobs,
            }

    def run_sync(self, job_id, fn, *, root_dir=None,
                 remove_invalid_outputs=False):
        """Execute fn() through running -> validating -> succeeded/failed."""
        self.transition(job_id, 'running')
        try:
            raw_outs = fn() or []
        except Exception as exc:                              # noqa: BLE001
            return self.transition(
                job_id, 'failed', error=f'{exc.__class__.__name__}: {exc}')
        if isinstance(raw_outs, (str, os.PathLike)):
            outs = [str(raw_outs)]
        else:
            outs = [str(o) for o in raw_outs if o]
        self.transition(job_id, 'validating', outputs=outs)
        checks = [validate_job_output(o, root_dir=root_dir) for o in outs]
        bad = [c for c in checks if not c['ok']]
        if bad:
            if remove_invalid_outputs:
                for c in bad:
                    p = c.get('path')
                    if p and not is_protected_image(p) and os.path.isfile(p):
                        try:
                            os.unlink(p)
                        except OSError:
                            pass
            msg = '; '.join(
                f'{os.path.basename(c["path"])}: {", ".join(c["errors"])}'
                for c in bad)
            return self.transition(
                job_id, 'failed', outputs=outs, validation=checks, error=msg)
        return self.transition(
            job_id, 'succeeded', outputs=outs, validation=checks)
