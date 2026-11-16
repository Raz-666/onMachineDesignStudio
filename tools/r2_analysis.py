#!/usr/bin/env python3
"""Streaming, evidence-first layer/object/path analysis for the offline service.

This module never executes G-code and does not assign verified object identity,
physical position, geometric feature, pattern, or print safety. It consumes
r2_shadow records; unknown modal state remains unknown. Tags are evidence, not
labels guaranteed by a slicer. The bounded summary deliberately avoids storing
all moves or geometric vertices.
"""
from collections import Counter
import hashlib
import math
import re
import shlex

import r2_postproc as legacy

FEATURE = re.compile(r'^\s*;\s*(?:TYPE|FEATURE)\s*:\s*(.*?)\s*$', re.I)
LAYER = re.compile(r'^\s*;\s*(?:LAYER_CHANGE|CHANGE_LAYER|LAYER\s*:?\s*\d+)\s*$', re.I)
PATTERN = re.compile(r'^\s*;\s*([a-z_]*pattern)\s*=\s*(.*?)\s*$', re.I)
CANON = frozenset(legacy.TYPE_MAP.values()) | {'SUPPORT', 'TRAVEL'}


def _name_id(name):
    return 'obj-' + hashlib.sha256(name.encode('utf8', 'surrogateescape')).hexdigest()[:20]


def _command(raw):
    # Tokens after a Klipper comment are never interpreted as commands.
    code = raw.split(';', 1)[0].strip()
    if not code: return '', {}
    try: words = shlex.split(code, comments=False, posix=True)
    except ValueError: return '', {}
    if not words: return '', {}
    values = {}
    for word in words[1:]:
        if '=' in word:
            key, val = word.split('=', 1)
            key = key.upper()
            if key in values: return '', {}
            values[key] = val
    return words[0].upper(), values


def _mapped(label):
    """Map explicit source tags only; ambiguous SKIN stays ambiguous."""
    label = label.strip()
    if label.lower() in ('skin', 'top-skin'):
        return {'role': 'AMBIGUOUS', 'alternatives': ['SURFACE-BOTTOM', 'SURFACE-TOP'],
                'basis': 'tag may mean either surface'}
    upper = label.upper()
    role = upper if upper in CANON else legacy._lookup_type(label)
    if role is None:
        return {'role': 'UNKNOWN', 'alternatives': [], 'basis': 'unmapped tag'}
    return {'role': role, 'alternatives': [], 'basis': 'existing R2 alias map; unverified tag'}


class Tracker:
    MAX_OBJECTS = 256
    MAX_GROUPS = 10000
    MAX_BOUNDARIES = 100000
    MAX_PATTERNS = 128
    MAX_WARNINGS = 32
    EPS = 1e-6
    CLOSE_MM = 0.01

    def __init__(self):
        self.objects = {}
        self.active = None
        self.boundary = 0
        self.boundary_sources = Counter()
        self.mark_count = 0
        self.role = {'role': 'UNKNOWN', 'alternatives': [], 'basis': 'no tag'}
        self.role_source = None
        self.group = {}
        self.path = None
        self.patterns = {}
        self.warnings = []
        self.warning_count = 0
        self.line_count = 0

    def _warning(self, line, text):
        self.warning_count += 1
        if len(self.warnings) < self.MAX_WARNINGS:
            self.warnings.append({'line': line, 'reason': text})

    def _obj(self, name):
        if not name or len(name) > 256: return None
        oid = _name_id(name)
        if oid not in self.objects:
            if len(self.objects) >= self.MAX_OBJECTS: raise ValueError('too many explicit objects')
            self.objects[oid] = {'id': oid, 'name': name, 'defines': 0, 'starts': 0,
                                 'ends': 0, 'evidence_lines': []}
        obj = self.objects[oid]
        if obj['name'] != name: raise ValueError('object identifier collision')
        return obj

    def _end_path(self):
        p = self.path
        if p is None: return
        group = self.group[p['key']]
        group['paths'] += 1
        closed = p['segments'] >= 3 and math.hypot(p['end'][0] - p['start'][0],
                                                  p['end'][1] - p['start'][1]) <= self.CLOSE_MM
        if closed:
            group['closed_xy_paths'] += 1
            area = abs(p['twice_area']) / 2.0
            if not math.isfinite(area) or not math.isfinite(group['closed_xy_area_sum_mm2'] + area):
                raise ValueError('numeric overflow in path area')
            group['closed_xy_area_sum_mm2'] += area
        self.path = None

    def _group(self):
        role = self.role['role']
        # Separate repeated tags so source provenance is never attributed to
        # the wrong span even if two tags map to the same canonical role.
        key = (self.active, self.boundary, role,
               self.role_source['line'] if self.role_source else None)
        if key not in self.group:
            if len(self.group) >= self.MAX_GROUPS: raise ValueError('too many analysis groups')
            self.group[key] = {'object_id': self.active, 'layer_boundary_id': self.boundary or None,
                               'declared_role': role, 'moves': 0, 'known_xy_segments': 0,
                               'extruding_xy_segments': 0, 'extruding_xy_length_mm': 0.0,
                               'positive_e_mm': 0.0, 'bounds_xy_mm': None,
                               'paths': 0, 'closed_xy_paths': 0, 'closed_xy_area_sum_mm2': 0.0,
                               'role_alternatives': self.role['alternatives'],
                               'role_basis': self.role['basis'], 'role_source': self.role_source}
        return key, self.group[key]

    def _set_role(self, label, source, number):
        self._end_path()
        if len(label) > 160:
            self._warning(number, 'feature tag too long; role unknown')
            self.role = {'role': 'UNKNOWN', 'alternatives': [], 'basis': 'tag length limit'}
        else:
            self.role = _mapped(label)
        self.role_source = {'line': number, 'kind': source, 'text': label[:160]}

    def observe(self, raw, record):
        number = record['line']
        self.line_count = number
        text = raw.rstrip('\r\n')
        tag = FEATURE.match(text)
        if tag: self._set_role(tag.group(1), 'comment', number)
        pattern = PATTERN.match(text)
        if pattern:
            key, value = pattern.group(1).lower()[:80], pattern.group(2)[:160]
            if key not in self.patterns and len(self.patterns) >= self.MAX_PATTERNS:
                raise ValueError('too many pattern metadata keys')
            self.patterns.setdefault(key, {'value': value, 'line': number, 'source': 'comment metadata'})
        if LAYER.match(text):
            self._end_path()
            self.boundary += 1
            if self.boundary > self.MAX_BOUNDARIES: raise ValueError('too many layer evidence boundaries')
            self.boundary_sources['comment'] += 1
        cmd, params = _command(text)
        if cmd == 'LAYER_MARK':
            self.mark_count += 1
            # Avoid claiming marker and comment are equivalent; they are
            # counted independently, not used to invent an extra layer.
            if not self.boundary_sources['comment']:
                self._end_path()
                self.boundary += 1
                if self.boundary > self.MAX_BOUNDARIES: raise ValueError('too many layer evidence boundaries')
                self.boundary_sources['marker_before_any_comment'] += 1
        elif cmd == 'APPLY_TYPE' and 'TYPE' in params:
            self._set_role(params['TYPE'], 'r2-command', number)
        elif cmd in ('EXCLUDE_OBJECT_DEFINE', 'EXCLUDE_OBJECT_START', 'EXCLUDE_OBJECT_END'):
            self._end_path()
            name = params.get('NAME', '')
            if cmd == 'EXCLUDE_OBJECT_END' and not name and self.active:
                obj = self.objects[self.active]
            else:
                obj = self._obj(name)
            if not obj:
                self._warning(number, 'object event without valid name')
                if cmd != 'EXCLUDE_OBJECT_DEFINE': self.active = None
            elif cmd == 'EXCLUDE_OBJECT_DEFINE': obj['defines'] += 1
            elif cmd == 'EXCLUDE_OBJECT_START':
                if self.active is not None:
                    self._warning(number, 'overlapping object starts; previous span incomplete')
                self.active = obj['id']; obj['starts'] += 1
            else:
                if self.active != obj['id']:
                    self._warning(number, 'object end does not match active object')
                obj['ends'] += 1; self.active = None
            if obj and len(obj['evidence_lines']) < 16:
                obj['evidence_lines'].append(number)
        if record['kind'] in ('unknown', 'tool', 'coordinate_reset'):
            self._end_path()
        if record['kind'] != 'move': return
        key, group = self._group()
        group['moves'] += 1
        start, end = record['start_mm'], record['end_mm']
        delta = record['commanded_e_delta_mm']
        if any(v is None for v in (start['X'], start['Y'], end['X'], end['Y'])):
            self._end_path(); return
        x0, y0, x1, y1 = start['X'], start['Y'], end['X'], end['Y']
        length = math.hypot(x1 - x0, y1 - y0)
        if not math.isfinite(length): raise ValueError('non-finite path length')
        if length <= self.EPS:
            if delta is not None and delta < 0: self._end_path()
            return
        group['known_xy_segments'] += 1
        if delta is None or delta <= 0:
            self._end_path(); return
        group['extruding_xy_segments'] += 1
        group['extruding_xy_length_mm'] += length
        group['positive_e_mm'] += delta
        if not math.isfinite(group['extruding_xy_length_mm']) or not math.isfinite(group['positive_e_mm']):
            raise ValueError('numeric overflow in geometric summary')
        bounds = group['bounds_xy_mm']
        if bounds is None:
            group['bounds_xy_mm'] = [min(x0, x1), min(y0, y1), max(x0, x1), max(y0, y1)]
        else:
            bounds[0], bounds[1] = min(bounds[0], x0, x1), min(bounds[1], y0, y1)
            bounds[2], bounds[3] = max(bounds[2], x0, x1), max(bounds[3], y0, y1)
        if self.path is None or self.path['key'] != key or math.hypot(
                self.path['end'][0] - x0, self.path['end'][1] - y0) > self.CLOSE_MM:
            self._end_path()
            self.path = {'key': key, 'start': (x0, y0), 'end': (x0, y0),
                         'segments': 0, 'twice_area': 0.0}
        self.path['segments'] += 1
        self.path['twice_area'] += x0 * y1 - x1 * y0
        self.path['end'] = (x1, y1)

    def finish(self):
        self._end_path()
        if self.active:
            self._warning(self.line_count, 'object span open at end of file')
        return {'schema': 'r2-evidence/1', 'objects': list(self.objects.values()),
                'layer_evidence': {'boundary_count': self.boundary,
                                   'boundary_sources': dict(self.boundary_sources),
                                   'marker_count': self.mark_count,
                                   'note': 'event boundaries, not proven physical layers; per-object sequencing not inferred'},
                'groups': list(self.group.values()), 'pattern_metadata': self.patterns,
                'warnings': self.warnings, 'warning_count': self.warning_count,
                'limitations': ['object IDs represent explicit names in this file, not proven geometry',
                                'roles are unverified comments or R2 markers, not ground truth',
                                'pattern metadata is independent of role and is not geometric pattern recognition',
                                'geometry is logical XY only; unknown commands invalidate shadow state',
                                'closed-path area does not establish holes, footprints or physical volume']}
