"""Bounded streaming evidence for extrusion paths, including nonplanar paths.

Default: no point cloud retention, snapping or inferred layers. Near closure
is a measurement bin only. Optional planar seam proposals retain at most 257
points per active path and 32 proposal examples; never an export approval.
"""
from collections import Counter
import math
import re
from seam_reconstruction import close_planar_seam
from physical_contours import width_from_filament
from contour_mesh import MAX_VERTICES
from contour_context import ObjectContext, feature_role

FEATURE = re.compile(r'^\s*(?:TYPE|FEATURE)\s*:\s*(.*?)\s*$', re.I)


class PathEvidence:
    def __init__(self, *, seam_gap_mm=None, assumed_layer_height_mm=None,
                 filament_diameter_mm=1.75):
        if seam_gap_mm is not None and (not math.isfinite(seam_gap_mm) or seam_gap_mm < 0):
            raise ValueError("finite nonnegative seam budget required")
        if assumed_layer_height_mm is not None and (not math.isfinite(assumed_layer_height_mm)
                                                    or assumed_layer_height_mm <= 0):
            raise ValueError("positive finite assumed layer height required")
        if not math.isfinite(filament_diameter_mm) or filament_diameter_mm <= 0:
            raise ValueError("positive finite filament diameter required")
        self.seam_gap_mm = seam_gap_mm
        self.assumed_layer_height_mm = assumed_layer_height_mm
        self.filament_diameter_mm = filament_diameter_mm
        self.planes = {}
        self.width_by_role = {}
        self.width_examples = []
        self.width_counts = Counter()
        self.seam_counts = Counter()
        self.seam_examples = []
        self.points = []
        self.point_overflow = False
        self.current = None
        self.objects = ObjectContext()
        self.by_role = Counter()
        self.feature = None
        self.counts = Counter()
        self.by_feature = Counter()
        self.examples = []
        self.longest = None

    def finish(self, reason):
        p = self.current
        if p is None:
            return
        if self.seam_gap_mm is not None:
            try:
                if self.point_overflow:
                    raise ValueError('seam point budget exceeded or insufficient points')
                proposal = close_planar_seam(self.points,max_gap_mm=self.seam_gap_mm)
            except ValueError as exc:
                self.seam_counts[str(exc)] += 1
            else:
                self.seam_counts['accepted_proposals'] += 1
                if len(self.seam_examples) < 32:
                    self.seam_examples.append(dict(proposal, source_lines=p['source_lines'][:],
                                                   feature_hint=p['feature_hint'],tool=p['tool'],
                                                   object_context=p['object_context'],
                                                   feature_role=p['feature_role']))
        self.points = []
        self.point_overflow = False
        gap = math.dist(p['start_mm'][:2], p['end_mm'][:2])
        p['xy_endpoint_gap_mm'] = gap
        p['z_span_mm'] = p['z_max_mm']-p['z_min_mm']
        p['termination'] = reason
        p['closed_3d_exact'] = p['start_mm'] == p['end_mm']
        self.by_role[p['feature_role']] += 1
        self._record_plane(p)
        self._record_width(p)
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

    def _record_plane(self, p):
        if p['z_span_mm']:
            return
        name = p['object_context'].get('name') or '(unmarked)'
        if name not in self.planes:
            if len(self.planes) >= 64:
                name = '(other objects)'
        planes = self.planes.setdefault(name, {})
        if len(planes) >= 4096 and p['z_min_mm'] not in planes:
            self.width_counts['plane_budget_exceeded'] += 1
            return
        planes[p['z_min_mm']] = planes.get(p['z_min_mm'], 0) + 1

    def _record_width(self, p):
        if self.assumed_layer_height_mm is None:
            return
        try:
            width = width_from_filament(filament_mm=p['commanded_filament_mm'],
                                        path_length_mm=p['length_3d_mm'],
                                        layer_height_mm=self.assumed_layer_height_mm,
                                        filament_diameter_mm=self.filament_diameter_mm)['width_mm']
        except ValueError:
            self.width_counts['unsupported_cross_section'] += 1
            return
        role = p['feature_role']
        stats = self.width_by_role.setdefault(role, dict(count=0, min_mm=width, max_mm=width))
        stats['count'] += 1
        stats['min_mm'] = min(stats['min_mm'], width)
        stats['max_mm'] = max(stats['max_mm'], width)
        if len(self.width_examples) < 12:
            self.width_examples.append(dict(source_lines=p['source_lines'][:],
                                            object_context=p['object_context'],
                                            feature_hint=p['feature_hint'],
                                            planar=not p['z_span_mm'],
                                            width_mm=width,
                                            commanded_filament_mm=p['commanded_filament_mm'],
                                            length_3d_mm=p['length_3d_mm']))

    def _plane_report(self):
        objects = {}
        for name, planes in self.planes.items():
            ordered = sorted(planes)
            differences = Counter(round(b-a, 6) for a, b in zip(ordered, ordered[1:]))
            if len(differences) > 64:
                keep = Counter(dict(differences.most_common(63)))
                keep['other'] = sum(differences.values()) - sum(keep.values())
                differences = keep
            common = differences.most_common(1)
            objects[name] = dict(plane_count=len(ordered),
                                 z_min_mm=ordered[0], z_max_mm=ordered[-1],
                                 successive_differences_mm=dict(sorted(differences.items(), key=lambda kv: str(kv[0]))),
                                 most_common_difference_mm=common[0][0] if common else None,
                                 paths_on_most_common_plane=max(planes.values()))
        return dict(objects=objects,
                    note='distinct extrusion Z planes per source-file object; nozzle plane spacing is measured evidence, not a verified layer height or first-layer offset')

    def consume(self, record):
        raw_command = (record.get('raw','').strip().split() or [''])[0].upper()
        if raw_command in ('EXCLUDE_OBJECT_START','EXCLUDE_OBJECT_END'):
            self.finish('object_boundary')
        if self.objects.consume(record):
            self.feature = None  # no stale feature hint across object boundaries
            return
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
                                object_context=self.objects.snapshot(),feature_role=feature_role(self.feature),
                                z_min_mm=start[2],z_max_mm=start[2],z_up_segments=0,z_down_segments=0,
                                length_3d_mm=0.0,commanded_filament_mm=0.0)
        if self.seam_gap_mm is not None and not self.point_overflow:
            if not self.points:
                self.points.append(start)
            self.points.append(end)
            if len(self.points) > MAX_VERTICES + 1:
                self.point_overflow = True
                self.points = []
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
        report = dict(object_diagnostics=dict(self.objects.diagnostics), paths_by_role=dict(self.by_role),
                    plane_statistics=self._plane_report(),
                    width_estimates=(None if self.assumed_layer_height_mm is None else
                                     dict(assumed_layer_height_mm=self.assumed_layer_height_mm,
                                          filament_diameter_mm=self.filament_diameter_mm,
                                          model='stadium under explicit assumption',
                                          measured=False,
                                          by_role=self.width_by_role,
                                          counts=dict(self.width_counts),
                                          examples=self.width_examples,
                                          note='width depends on the unverified assumed layer height; effective flow compensation is not modelled')),
                    seam_policy=dict(max_gap_mm=self.seam_gap_mm, enabled=self.seam_gap_mm is not None,
                                     counts=dict(self.seam_counts), proposals=self.seam_examples,
                                     retained_proposal_limit=32), counts=dict(self.counts), paths_by_feature_hint=dict(self.by_feature),
                    examples=self.examples,longest_path=self.longest,
                    retained_path_summary_limit=13,
                    note='command-coordinate paths; feature hints unverified; no snapping or inferred layers')
        return report
