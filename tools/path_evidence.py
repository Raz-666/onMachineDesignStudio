"""Bounded streaming evidence for extrusion paths, including nonplanar paths.

No point cloud retention, snapping, inferred layers or geometry repair. Near
closure is a measurement bin only, NOT permission to close/export a path.
"""
from collections import Counter
import math
import re

FEATURE = re.compile(r'^\s*(?:TYPE|FEATURE)\s*:\s*(.*?)\s*$', re.I)


class PathEvidence:
    def __init__(self):
        self.current = None
        self.feature = None
        self.counts = Counter()
        self.by_feature = Counter()
        self.examples = []
        self.longest = None

    def finish(self, reason):
        p = self.current
        if p is None:
            return
        gap = math.dist(p['start_mm'][:2], p['end_mm'][:2])
        p['xy_endpoint_gap_mm'] = gap
        p['z_span_mm'] = p['z_max_mm']-p['z_min_mm']
        p['termination'] = reason
        p['closed_3d_exact'] = p['start_mm'] == p['end_mm']
        self.counts['paths'] += 1
        self.counts['segments'] += p['segments']
        self.counts['nonplanar_paths' if p['z_span_mm'] else 'planar_paths'] += 1
        if p['closed_3d_exact']:
            self.counts['exact_3d_closures'] += 1
        elif gap <= .1:
            self.counts['xy_gap_at_most_0.1mm_not_closed_3d'] += 1
        label = p['feature_hint'] or 'UNMARKED'
        if label not in self.by_feature and len(self.by_feature) >= 64:
            label = 'OTHER_HINTS'
        self.by_feature[label] += 1
        if len(self.examples) < 12:
            self.examples.append(p)
        if self.longest is None or p['segments'] > self.longest['segments']:
            self.longest = p
        self.current = None

    def consume(self, record):
        comment = record.get('comment') or ''
        match = FEATURE.match(comment)
        if match and match.group(1) != self.feature:
            self.finish('feature_hint_change')
            # Bound comment storage; hints are not verified feature assignments.
            self.feature = match.group(1)[:120]
        kind = record['kind']
        if kind in ('comment', 'non_motion_event'):
            return
        if kind != 'move':
            self.finish(kind)
            if kind == 'unknown':
                self.feature = None
            return
        a,b = record['start_mm'],record['end_mm']
        start,end = tuple(a[k] for k in 'XYZ'),tuple(b[k] for k in 'XYZ')
        de = record['commanded_e_delta_mm']
        if any(v is None or not math.isfinite(v) for v in (*start,*end,de)):
            self.finish('unknown_motion')
            return
        if de == 0 and start == end:
            return
        if de <= 0 or start[:2] == end[:2]:
            self.finish('travel_retract_or_e_only')
            return
        if self.current and (self.current['end_mm'] != start or
                             self.current['tool'] != record['tool']):
            self.finish('discontinuity')
        if self.current is None:
            self.current = dict(start_mm=start,end_mm=start,source_lines=[record['line'],record['line']],
                                tool=record['tool'],feature_hint=self.feature,segments=0,
                                z_min_mm=start[2],z_max_mm=start[2],z_up_segments=0,z_down_segments=0,
                                length_3d_mm=0.0,commanded_filament_mm=0.0)
        p = self.current
        p['end_mm'] = end
        p['source_lines'][1] = record['line']
        p['segments'] += 1
        p['z_min_mm'] = min(p['z_min_mm'],end[2])
        p['z_max_mm'] = max(p['z_max_mm'],end[2])
        p['z_up_segments'] += end[2] > start[2]
        p['z_down_segments'] += end[2] < start[2]
        p['length_3d_mm'] += math.dist(start,end)
        p['commanded_filament_mm'] += de

    def report(self):
        return dict(counts=dict(self.counts), paths_by_feature_hint=dict(self.by_feature),
                    examples=self.examples,longest_path=self.longest,
                    retained_path_summary_limit=13,
                    note='command-coordinate paths; feature hints unverified; no snapping or inferred layers')
