#!/usr/bin/env python3
"""Streaming, evidence-first Pass 3-10 layer/object/kinematics/topology/audit engine.

This module never executes G-code and never claims machine-level print safety.
It consumes `r2_shadow` records while keeping unknown modal/coordinate state
explicitly unknown. Tags remain evidence, not slicer-guaranteed ground truth.
All geometric and spatial accumulators run in bounded memory (O(active layer)).
"""
from collections import Counter
import hashlib
import math
import re
import shlex

import r2_postproc as legacy
import r2_shadow

FEATURE = re.compile(
    r'^\s*;\s*(?:TYPE\s*:|FEATURE\s*:|STRUCTURE\s*:|feature\s+)(.*?)\s*$', re.I)
LAYER = re.compile(
    r'^\s*;\s*(?:LAYER_CHANGE|CHANGE_LAYER|LAYER\s*:?\s*-?\d+|'
    r'BEGIN_LAYER_OBJECT\b.*)\s*$', re.I)
Z_COMMENT = re.compile(r'^\s*;\s*Z\s*:\s*([+-]?\d+(?:\.\d+)?)\s*$', re.I)
PATTERN = re.compile(r'^\s*;\s*([a-z_]*pattern)\s*=\s*(.*?)\s*$', re.I)
FIL_DIA_COMMENT = re.compile(
    r'^\s*;\s*filament_diameter\s*=\s*([0-9]+(?:\.[0-9]+)?)', re.I)
CANON = frozenset(legacy.TYPE_MAP.values()) | {'SUPPORT', 'TRAVEL'}

_NONPRINT_TAG_RE = re.compile(
    r'^(?:seams?|(?:destring(?:/wipe/jump)?|wipe|jump)(?:\s+path)?|'
    r'retract(?:ion)?|unretract(?:ion)?|deretract(?:ion)?|'
    r'noop|travel|combing\s+travel|move|non[- ]print\s+move|'
    r'tool\s*changes?|color\s*changes?|pause\s*prints?|'
    r'custom\s+g[- ]?code)$', re.I)


def _name_id(name):
    return 'obj-' + hashlib.sha256(
        name.encode('utf8', 'surrogateescape')).hexdigest()[:20]


def _command(raw):
    # Tokens after a Klipper comment are never interpreted as commands.
    code = raw.split(';', 1)[0].strip()
    if not code:
        return '', {}
    try:
        words = shlex.split(code, comments=False, posix=True)
    except ValueError:
        return '', {}
    if not words:
        return '', {}
    values = {}
    for word in words[1:]:
        if '=' in word:
            key, val = word.split('=', 1)
            key = key.upper()
            if key in values:
                return '', {}
            values[key] = val
    return words[0].upper(), values


def _mapped(label):
    """Map explicit source tags only; ambiguous SKIN stays AMBIGUOUS."""
    label = label.strip()
    if label.lower() in ('skin', 'top-skin'):
        return {'role': 'AMBIGUOUS',
                'alternatives': ['SURFACE-BOTTOM', 'SURFACE-TOP'],
                'basis': 'tag may mean either surface'}
    upper = label.upper()
    role = upper if upper in CANON else legacy._lookup_type(label)
    if role is None:
        return {'role': 'UNKNOWN', 'alternatives': [], 'basis': 'unmapped tag'}
    return {'role': role, 'alternatives': [],
            'basis': 'existing R2 alias map; unverified tag'}


def _raster_cells(x0, y0, x1, y1, cell_mm, cap=1024):
    inv = 1.0 / cell_mm
    c0, r0 = int(math.floor(x0 * inv)), int(math.floor(y0 * inv))
    c1, r1 = int(math.floor(x1 * inv)), int(math.floor(y1 * inv))
    steps = max(abs(c1 - c0), abs(r1 - r0))
    if steps == 0:
        return {(c0, r0)}
    steps = min(steps, cap)
    dx = (x1 - x0) / steps
    dy = (y1 - y0) / steps
    return {(int(math.floor((x0 + k * dx) * inv)),
             int(math.floor((y0 + k * dy) * inv)))
            for k in range(steps + 1)}


def _dilate1(cells):
    out = set()
    for cx, cy in cells:
        out.update((
            (cx - 1, cy - 1), (cx, cy - 1), (cx + 1, cy - 1),
            (cx - 1, cy),     (cx, cy),     (cx + 1, cy),
            (cx - 1, cy + 1), (cx, cy + 1), (cx + 1, cy + 1),
        ))
    return out


def _bbox_contains(outer, inner, tol=1e-4):
    return (outer[0] <= inner[0] + tol and outer[1] <= inner[1] + tol
            and outer[2] >= inner[2] - tol and outer[3] >= inner[3] - tol
            and ((outer[2] - outer[0]) * (outer[3] - outer[1])
                 > (inner[2] - inner[0]) * (inner[3] - inner[1]) + tol))


def _is_parallel_open_hatch(strokes):
    if len(strokes) < 6:
        return False
    angles = []
    for sx0, sy0, sx1, sy1, nseg, slen in strokes:
        if slen < 3.0:
            continue
        chord = math.hypot(sx1 - sx0, sy1 - sy0)
        if chord < 0.85 * slen or nseg > 2:
            return False
        angles.append(math.atan2(sy1 - sy0, sx1 - sx0) % math.pi)
    if len(angles) < 6:
        return False
    ref = angles[0]
    aligned = sum(
        1 for a in angles
        if min(abs(a - ref), math.pi - abs(a - ref)) < math.radians(6.0)
    )
    return aligned >= max(6, int(0.85 * len(angles)))


class Tracker:
    MAX_OBJECTS = 256
    MAX_GROUPS = 10000
    MAX_BOUNDARIES = 100000
    MAX_PATTERNS = 128
    MAX_WARNINGS = 32
    MAX_CONFLICTS = 64
    MAX_LAYER_LOOPS = 512
    MAX_LAYER_CELLS = 50000
    CELL_MM = 1.5
    EPS = 1e-6
    CLOSE_MM = 0.01

    def __init__(self, filament_diameter_mm=1.75):
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

        # Filament area for volumetric flow estimate (explicitly labelled estimate)
        self.filament_dia_mm = max(0.5, float(filament_diameter_mm))
        self.filament_dia_source = 'default_1.75mm'

        # Pass 3: Units, physical layers, Z-hops, vase/non-planar tracking
        self._bed_z = None
        self._unit_id = 0
        self._unit_layer = 0
        self._unit_z = None
        self._physical_layers = 0
        self._pending_comment_layer = False
        self._seen_layer_comment = False
        self._zhop_base_z = None
        self._zhop_raised = False
        self.z_hop_count = 0
        self.continuous_z_extrude_moves = 0
        self.planar_extrude_moves = 0
        self.nonplanar_extrude_moves = 0
        self._units = {}  # unit_id -> dict

        # Pass 4: Kinematics
        self.kin = {
            'linear_extruding_moves': 0,
            'linear_travel_moves': 0,
            'arc_extruding_moves': 0,
            'arc_travel_moves': 0,
            'z_only_moves': 0,
            'retract_moves': 0,
            'deretract_moves': 0,
            'firmware_retracts': 0,
            'firmware_deretracts': 0,
            'motors_off_events': 0,
            'extruding_length_mm': 0.0,
            'arc_extruding_length_mm': 0.0,
            'travel_length_mm': 0.0,
            'positive_e_mm': 0.0,
            'negative_e_mm': 0.0,
            'print_speed_min_mm_s': None,
            'print_speed_max_mm_s': None,
            'travel_speed_max_mm_s': None,
            'volumetric_flow_max_mm3_s': None,
        }

        # Pass 5: Per-object positive-extrusion footprints
        self._footprints = {}  # obj_id or '<unassigned>' -> dict

        # Pass 6: 2D topology (orientation, outer/nested loops, parallel hatch)
        self._layer_loops = []  # [(bbox, area, ccw)]
        self.outer_loops = 0
        self.nested_loops = 0
        self.ccw_loops = 0
        self.cw_loops = 0
        self.parallel_hatch_groups = 0

        # Pass 7 + Pass 8-10: 3D layer support & C1/C2/C3/C5 sequence + tag audit
        self._prev_cells = set()
        self._prev_adhesion = set()
        self._prev_expl_top = set()
        self._prev_iron = set()
        self._prev_had_interior = False
        self._prev_had_walls = False
        self._cur_cells = set()
        self._cur_adhesion = set()
        self._cur_top = set()
        self._cur_support = set()   # R281: G3 support world (solid same-layer)
        self._cur_expl_top = set()
        self._cur_iron = set()
        self._cur_had_interior = False
        self._cur_had_walls = False
        self.supported_upper_cells = 0
        self.total_upper_cells = 0

        self._seq_events = []  # [(unit_layer, canon_role, unit_id)]
        self._xsec_samples = []
        self._blk_moves = 0
        self._blk_len = 0.0
        self._blk_xsecs = []
        self._blk_cells = set()
        self._blk_endpoints = []
        self._blk_strokes = []
        self._blk_cur_stroke = None
        self._cur_iron_blocks = []
        self._cur_adhes_blocks = []
        self._cur_bridge_blocks = []
        self._cur_top_blocks = []
        self.tag_conflicts = []
        self.empty_tag_blocks = 0
        self.tagged_blocks = 0

    @property
    def _fil_area(self):
        return math.pi * (self.filament_dia_mm * 0.5) ** 2

    def _warning(self, line, text):
        self.warning_count += 1
        if len(self.warnings) < self.MAX_WARNINGS:
            self.warnings.append({'line': line, 'reason': text})

    def _add_conflict(self, code, line_no, unit_id, unit_layer, raw_tag,
                      role, detail):
        if len(self.tag_conflicts) < self.MAX_CONFLICTS:
            self.tag_conflicts.append({
                'code': code,
                'line': int(line_no or 0),
                'unit_id': int(unit_id),
                'unit_layer': int(unit_layer),
                'raw_tag': raw_tag,
                'declared_role': role,
                'detail': detail,
            })

    def _obj(self, name):
        if not name or len(name) > 256:
            return None
        oid = _name_id(name)
        if oid not in self.objects:
            if len(self.objects) >= self.MAX_OBJECTS:
                raise ValueError('too many explicit objects')
            self.objects[oid] = {'id': oid, 'name': name, 'defines': 0,
                                 'starts': 0, 'ends': 0, 'evidence_lines': []}
        obj = self.objects[oid]
        if obj['name'] != name:
            raise ValueError('object identifier collision')
        return obj

    def _touch_unit(self, uid, z_val, dist_mm):
        u = self._units.get(uid)
        if u is None:
            u = {'unit_id': uid, 'layer_count': 0, 'z_min_mm': None,
                 'z_max_mm': None, 'extruding_length_mm': 0.0,
                 'object_ids': set()}
            self._units[uid] = u
        u['layer_count'] = max(u['layer_count'], self._unit_layer)
        u['extruding_length_mm'] += dist_mm
        if self.active:
            u['object_ids'].add(self.active)
        if z_val is not None:
            u['z_min_mm'] = z_val if u['z_min_mm'] is None else min(u['z_min_mm'], z_val)
            u['z_max_mm'] = z_val if u['z_max_mm'] is None else max(u['z_max_mm'], z_val)

    def _touch_footprint(self, bbox4, z0, z1, dist_mm, de_mm):
        fid = self.active or '<unassigned>'
        fp = self._footprints.get(fid)
        if fp is None:
            fp = {
                'object_id': self.active,
                'object_name': (self.objects[self.active]['name']
                                if self.active in self.objects else None),
                'bounds_xy_mm': list(bbox4),
                'z_min_mm': None,
                'z_max_mm': None,
                'extruding_length_mm': 0.0,
                'positive_e_mm': 0.0,
                'unit_ids': set(),
            }
            self._footprints[fid] = fp
        else:
            b = fp['bounds_xy_mm']
            b[0] = min(b[0], bbox4[0])
            b[1] = min(b[1], bbox4[1])
            b[2] = max(b[2], bbox4[2])
            b[3] = max(b[3], bbox4[3])
        for zv in (z0, z1):
            if zv is not None:
                fp['z_min_mm'] = zv if fp['z_min_mm'] is None else min(fp['z_min_mm'], zv)
                fp['z_max_mm'] = zv if fp['z_max_mm'] is None else max(fp['z_max_mm'], zv)
        fp['extruding_length_mm'] += dist_mm
        fp['positive_e_mm'] += de_mm
        fp['unit_ids'].add(self._unit_id)

    def _end_path(self):
        p = self.path
        if p is None:
            return
        group = self.group[p['key']]
        group['paths'] += 1
        closed = (p['segments'] >= 3
                  and math.hypot(p['end'][0] - p['start'][0],
                                 p['end'][1] - p['start'][1]) <= self.CLOSE_MM)
        if closed:
            group['closed_xy_paths'] += 1
            signed = p['twice_area'] * 0.5
            area = abs(signed)
            if (not math.isfinite(area)
                    or not math.isfinite(group['closed_xy_area_sum_mm2'] + area)):
                raise ValueError('numeric overflow in path area')
            group['closed_xy_area_sum_mm2'] += area
            if area > 1e-4:
                if signed >= 0:
                    self.ccw_loops += 1
                else:
                    self.cw_loops += 1
                if len(self._layer_loops) < self.MAX_LAYER_LOOPS:
                    self._layer_loops.append((tuple(p['bbox']), area))
        self.path = None

    def _flush_tag_block(self):
        if self._blk_cur_stroke is not None:
            self._blk_strokes.append(self._blk_cur_stroke)
            self._blk_cur_stroke = None
        if self.role_source is not None:
            role = self.role['role']
            raw_txt = self.role_source['text']
            raw_lc = raw_txt.strip().lower()
            if self._blk_moves == 0:
                if role != 'TRAVEL':
                    self.empty_tag_blocks += 1
            else:
                uln = max(1, self._unit_layer)
                is_hatch = _is_parallel_open_hatch(self._blk_strokes)
                if is_hatch:
                    self.parallel_hatch_groups += 1
                # Record sequence event for C2/C3 impossibility audit
                seq_role = role
                if role == 'AMBIGUOUS' and raw_lc in ('skin', 'top-skin'):
                    seq_role = 'SURFACE-BOTTOM' if uln <= 1 else 'SURFACE-TOP'
                if seq_role not in ('UNKNOWN', 'AMBIGUOUS', 'TRAVEL'):
                    self._seq_events.append((uln, seq_role, self._unit_id))
                if role == 'IRONING':
                    sxs = sorted(self._blk_xsecs)
                    med = sxs[len(sxs) // 2] if sxs else 0.0
                    self._cur_iron_blocks.append(
                        (self.role_source['line'], raw_txt,
                         set(self._blk_cells), med, self._blk_len))
                elif role == 'BRIM' or raw_lc.startswith('raft'):
                    self._cur_adhes_blocks.append(
                        (self.role_source['line'], raw_txt, role,
                         set(self._blk_cells), uln, self._unit_id))
                elif role == 'BRIDGE':
                    self._cur_bridge_blocks.append(
                        (self.role_source['line'], raw_txt,
                         set(self._blk_cells), list(self._blk_endpoints),
                         uln, self._unit_id))
                elif (role == 'SURFACE-TOP'
                      and raw_lc not in ('skin', 'top-skin', 'surface')
                      and uln >= 2):
                    self._cur_top_blocks.append(
                        (self.role_source['line'], raw_txt,
                         set(self._blk_cells), uln, self._unit_id))
                elif role == 'WALL-OUTER' and self._blk_len >= 24.0 and is_hatch:
                    self._add_conflict(
                        'G6_OPEN_HATCH_AS_OUTER_WALL',
                        self.role_source['line'], self._unit_id, uln,
                        raw_txt, role,
                        '%d disjoint parallel open strokes (%.1f mm) tagged as outer wall'
                        % (len(self._blk_strokes), self._blk_len))
        self._blk_moves = 0
        self._blk_len = 0.0
        self._blk_xsecs = []
        self._blk_cells = set()
        self._blk_endpoints = []
        self._blk_strokes = []

    def _finish_physical_layer(self, reset_unit=False):
        self._end_path()
        self._flush_tag_block()
        # Pass 6: classify closed loops on this layer into outer vs nested
        loops = self._layer_loops
        if loops:
            for i, (bi, _) in enumerate(loops):
                if any(_bbox_contains(bj, bi) for j, (bj, _) in enumerate(loops) if j != i):
                    self.nested_loops += 1
                else:
                    self.outer_loops += 1
            self._layer_loops = []

        if self._cur_cells:
            uln = max(1, self._unit_layer)
            # Pass 7: 3D vertical support coverage for layers above unit layer 1
            if uln >= 2:
                prev_d = _dilate1(self._prev_cells) if self._prev_cells else set()
                self.total_upper_cells += len(self._cur_cells)
                self.supported_upper_cells += len(self._cur_cells & prev_d)
            else:
                prev_d = set()

            # Pass 9/10: spatial tag-vs-geometry audits G1-G5
            prev_adh_d = _dilate1(self._prev_adhesion) if self._prev_adhesion else set()
            for bline, braw, brole, bcells, buln, buid in self._cur_adhes_blocks:
                if buln > 3 and bcells:
                    ov = len(bcells & prev_adh_d) / float(len(bcells))
                    if ov < 0.30:
                        self._add_conflict(
                            'G1_FLOATING_ADHESION', bline, buid, buln, braw, brole,
                            'adhesion feature at unit layer %d with %.0f%% lower-layer continuation'
                            % (buln, ov * 100.0))

            # R281: same widened G3 support world as the upload audit
            # (r2_postproc.audit_tag_geometry) - every solid same-layer
            # feature, not only SURFACE-TOP - so the offline audit and the
            # upload audit reach the same verdict (Slice Beam's MAN_V3
            # ironed stepped ceilings on plain solid infill: 100% support).
            sup_d = (_dilate1(self._cur_support)
                     if self._cur_support else set())
            nom_xs = 0.0
            if len(self._xsec_samples) >= 4:
                sxs = sorted(self._xsec_samples)
                nom_xs = sxs[len(sxs) // 2]
            for bline, braw, bcells, med_xs, blen in self._cur_iron_blocks:
                if bcells and uln >= 2:
                    ov = ((len(bcells & sup_d) / float(len(bcells)))
                          if sup_d else 0.0)
                    if ov < 0.35:
                        self._add_conflict(
                            'G3_IRONING_UNSUPPORTED', bline, self._unit_id, uln,
                            braw, 'IRONING',
                            'ironing overlaps only %.0f%% of same-layer solid '
                            'support cells (top/infill/wall/gap)'
                            % (ov * 100.0))
                if nom_xs > 1e-4 and med_xs > 0.65 * nom_xs and blen >= 4.0:
                    self._add_conflict(
                        'G2_IRONING_HIGH_FLOW', bline, self._unit_id, uln,
                        braw, 'IRONING',
                        'ironing cross-section %.4f mm2 is %.0f%% of nominal %.4f mm2'
                        % (med_xs, 100.0 * med_xs / nom_xs, nom_xs))

            if (self._prev_expl_top and not self._prev_had_interior
                    and not self._cur_had_interior):
                for bline, braw, bcells, buln, buid in self._cur_top_blocks:
                    if len(bcells) < 4:
                        continue
                    ov = len(bcells & self._prev_expl_top) / float(len(bcells))
                    if ov < 0.75:
                        continue
                    over_iron = (
                        bool(self._prev_iron)
                        and len(bcells & self._prev_iron) / float(len(self._prev_iron)) >= 0.75
                        and len(bcells & self._prev_iron) / float(len(bcells)) >= 0.75
                    )
                    unenclosed = (not self._prev_had_walls and not self._cur_had_walls)
                    if unenclosed or over_iron:
                        self._add_conflict(
                            'G4_STACKED_EXPLICIT_TOP', bline, buid, buln,
                            braw, 'SURFACE-TOP',
                            'explicit top surface re-caps %.0f%% of already-closed %stop cells'
                            % (ov * 100.0, 'ironed ' if over_iron else 'unenclosed '))

            if uln >= 2 and self._cur_bridge_blocks:
                for bline, braw, bcells, beps, buln, buid in self._cur_bridge_blocks:
                    if len(bcells) < 2:
                        continue
                    if not any(ep in prev_d for ep in beps) and not (bcells & prev_d):
                        self._add_conflict(
                            'G5_UNANCHORED_BRIDGE', bline, buid, buln,
                            braw, 'BRIDGE',
                            'bridge has zero lower-layer support or anchored endpoints')

            if reset_unit:
                self._prev_cells = set()
                self._prev_adhesion = set()
                self._prev_expl_top = set()
                self._prev_iron = set()
                self._prev_had_interior = False
                self._prev_had_walls = False
            else:
                self._prev_cells = self._cur_cells
                self._prev_adhesion = self._cur_adhesion
                self._prev_expl_top = self._cur_expl_top
                self._prev_iron = self._cur_iron
                self._prev_had_interior = self._cur_had_interior
                self._prev_had_walls = self._cur_had_walls
        elif reset_unit:
            self._prev_cells = set()
            self._prev_adhesion = set()
            self._prev_expl_top = set()
            self._prev_iron = set()
            self._prev_had_interior = False
            self._prev_had_walls = False

        self._cur_cells = set()
        self._cur_adhesion = set()
        self._cur_top = set()
        self._cur_support = set()
        self._cur_expl_top = set()
        self._cur_iron = set()
        self._cur_had_interior = False
        self._cur_had_walls = False
        self._cur_iron_blocks = []
        self._cur_adhes_blocks = []
        self._cur_bridge_blocks = []
        self._cur_top_blocks = []

    def _group(self):
        role = self.role['role']
        key = (self.active, self.boundary, role,
               self.role_source['line'] if self.role_source else None)
        if key not in self.group:
            if len(self.group) >= self.MAX_GROUPS:
                raise ValueError('too many analysis groups')
            self.group[key] = {
                'object_id': self.active,
                'layer_boundary_id': self.boundary or None,
                'declared_role': role,
                'moves': 0,
                'known_xy_segments': 0,
                'extruding_xy_segments': 0,
                'extruding_xy_length_mm': 0.0,
                'positive_e_mm': 0.0,
                'bounds_xy_mm': None,
                'paths': 0,
                'closed_xy_paths': 0,
                'closed_xy_area_sum_mm2': 0.0,
                'role_alternatives': self.role['alternatives'],
                'role_basis': self.role['basis'],
                'role_source': self.role_source,
            }
        return key, self.group[key]

    def _set_role(self, label, source, number):
        lbl = label.strip()
        # Non-print move annotations (; feature Seam / Destring / Retract / Wipe)
        # do not start a new extrusion feature block.
        if source == 'comment' and _NONPRINT_TAG_RE.match(lbl):
            return
        self._end_path()
        self._flush_tag_block()
        self.tagged_blocks += 1
        if len(lbl) > 160:
            self._warning(number, 'feature tag too long; role unknown')
            self.role = {'role': 'UNKNOWN', 'alternatives': [],
                         'basis': 'tag length limit'}
        else:
            self.role = _mapped(lbl)
        self.role_source = {'line': number, 'kind': source, 'text': lbl[:160]}

    def _update_speed_flow(self, feed_mm_min, dist_mm, de_mm, extruding):
        if feed_mm_min is None or feed_mm_min <= 0:
            return
        spd = feed_mm_min / 60.0
        if extruding:
            lo = self.kin['print_speed_min_mm_s']
            hi = self.kin['print_speed_max_mm_s']
            self.kin['print_speed_min_mm_s'] = spd if lo is None else min(lo, spd)
            self.kin['print_speed_max_mm_s'] = spd if hi is None else max(hi, spd)
            if dist_mm > 1e-4 and de_mm > 0:
                flow = (de_mm * self._fil_area) * (spd / dist_mm)
                if math.isfinite(flow):
                    fmax = self.kin['volumetric_flow_max_mm3_s']
                    self.kin['volumetric_flow_max_mm3_s'] = (
                        flow if fmax is None else max(fmax, flow))
        else:
            tmax = self.kin['travel_speed_max_mm_s']
            self.kin['travel_speed_max_mm_s'] = spd if tmax is None else max(tmax, spd)

    def _advance_physical_layer_on_extrude(self, ez):
        if ez is not None and self._bed_z is None:
            self._bed_z = ez
        if self._pending_comment_layer:
            is_reset = (ez is not None and self._unit_z is not None
                        and self._bed_z is not None
                        and self._unit_z >= self._bed_z + 0.55
                        and ez <= self._bed_z + 0.35)
            self._finish_physical_layer(reset_unit=is_reset)
            if is_reset:
                self._unit_id += 1
                self._unit_layer = 1
            else:
                self._unit_layer += 1
            self._physical_layers += 1
            if ez is not None:
                self._unit_z = ez
            self._pending_comment_layer = False
        elif not self._seen_layer_comment and ez is not None:
            if self._unit_z is None:
                self._unit_layer = max(1, self._unit_layer)
                if self._physical_layers == 0:
                    self._physical_layers = 1
                self._unit_z = ez
            elif (self._bed_z is not None
                  and self._unit_z >= self._bed_z + 0.55
                  and ez <= self._bed_z + 0.35):
                self._finish_physical_layer(reset_unit=True)
                self._unit_id += 1
                self._unit_layer = 1
                self._physical_layers += 1
                self._unit_z = ez
            elif ez >= self._unit_z + 0.039 and self._cur_cells:
                self._finish_physical_layer(reset_unit=False)
                self._unit_layer += 1
                self._physical_layers += 1
                self._unit_z = ez
        elif self._unit_layer == 0:
            self._unit_layer = 1
            self._physical_layers = 1

    def _record_cells_and_tag(self, seg_points, dist_mm, de_mm):
        cells = set()
        if len(self._cur_cells) < self.MAX_LAYER_CELLS:
            for (ax, ay, _), (bx, by, _) in zip(seg_points, seg_points[1:]):
                cells |= _raster_cells(ax, ay, bx, by, self.CELL_MM)
            self._cur_cells |= cells
        xsec = (de_mm * self._fil_area) / dist_mm
        role = self.role['role']
        raw_lc = (self.role_source['text'].strip().lower()
                  if self.role_source else '')
        if role != 'IRONING' and len(self._xsec_samples) < 4000 and 1e-4 < xsec < 5.0:
            self._xsec_samples.append(xsec)
        if self.role_source is not None and role != 'TRAVEL':
            self._blk_moves += 1
            self._blk_len += dist_mm
            self._blk_cells |= cells
            if role == 'IRONING':
                self._blk_xsecs.append(xsec)
                self._cur_iron |= cells
            elif role in ('WALL-OUTER', 'WALL-INNER'):
                self._cur_had_walls = True
                self._cur_support |= cells
                if (role == 'WALL-OUTER' and len(seg_points) == 2
                        and len(self._blk_strokes) < 200):
                    sx0, sy0, _ = seg_points[0]
                    sx1, sy1, _ = seg_points[1]
                    if self._blk_cur_stroke is None:
                        self._blk_cur_stroke = [sx0, sy0, sx1, sy1, 1, dist_mm]
                    else:
                        self._blk_cur_stroke[2] = sx1
                        self._blk_cur_stroke[3] = sy1
                        self._blk_cur_stroke[4] += 1
                        self._blk_cur_stroke[5] += dist_mm
            elif role == 'SURFACE-TOP':
                self._cur_top |= cells
                self._cur_support |= cells
                if raw_lc not in ('skin', 'top-skin', 'surface'):
                    self._cur_expl_top |= cells
            elif role == 'AMBIGUOUS' and raw_lc in ('skin', 'top-skin'):
                if self._unit_layer >= 2:
                    self._cur_top |= cells
                    self._cur_support |= cells
                else:
                    self._cur_had_interior = True
            elif role == 'BRIM' or raw_lc.startswith('raft'):
                self._cur_adhesion |= cells
            elif role in ('INFILL-SPARSE', 'INFILL-SOLID',
                          'INTERNAL-BRIDGE', 'SURFACE-BOTTOM', 'GAPS'):
                self._cur_had_interior = True
                # R281: solid infill / gap fill carry ironing too (parity
                # with the upload audit's G3 support world)
                if role in ('INFILL-SOLID', 'GAPS'):
                    self._cur_support |= cells
            elif role == 'BRIDGE':
                inv = 1.0 / self.CELL_MM
                sx0, sy0, _ = seg_points[0]
                sx1, sy1, _ = seg_points[-1]
                self._blk_endpoints.append(
                    (int(math.floor(sx0 * inv)), int(math.floor(sy0 * inv))))
                self._blk_endpoints.append(
                    (int(math.floor(sx1 * inv)), int(math.floor(sy1 * inv))))

    def observe(self, raw, record):
        number = record['line']
        self.line_count = number
        text = raw.rstrip('\r\n')
        mfd = FIL_DIA_COMMENT.match(text)
        if mfd and self.filament_dia_source == 'default_1.75mm':
            try:
                v = float(mfd.group(1))
                if 0.5 <= v <= 5.0:
                    self.filament_dia_mm = v
                    self.filament_dia_source = 'header_comment'
            except ValueError:
                pass
        tag = FEATURE.match(text)
        if tag:
            self._set_role(tag.group(1), 'comment', number)
        pattern = PATTERN.match(text)
        if pattern:
            key, value = pattern.group(1).lower()[:80], pattern.group(2)[:160]
            if key not in self.patterns and len(self.patterns) >= self.MAX_PATTERNS:
                raise ValueError('too many pattern metadata keys')
            self.patterns.setdefault(
                key, {'value': value, 'line': number, 'source': 'comment metadata'})
        if LAYER.match(text):
            self._end_path()
            self.boundary += 1
            if self.boundary > self.MAX_BOUNDARIES:
                raise ValueError('too many layer evidence boundaries')
            self.boundary_sources['comment'] += 1
            self._seen_layer_comment = True
            self._pending_comment_layer = True
        mz = Z_COMMENT.match(text)
        if mz:
            zv = float(mz.group(1))
            if math.isfinite(zv):
                if self._bed_z is None:
                    self._bed_z = zv
                if self._unit_z is not None and zv < self._unit_z - 0.45:
                    self._finish_physical_layer(reset_unit=True)
                    self._unit_id += 1
                    self._unit_layer = 1
                    self._physical_layers += 1
                    self._unit_z = zv
                    self._pending_comment_layer = False

        cmd, params = _command(text)
        if cmd == 'LAYER_MARK':
            self.mark_count += 1
            if not self.boundary_sources['comment']:
                self._end_path()
                self.boundary += 1
                if self.boundary > self.MAX_BOUNDARIES:
                    raise ValueError('too many layer evidence boundaries')
                self.boundary_sources['marker_before_any_comment'] += 1
                self._seen_layer_comment = True
                self._pending_comment_layer = True
        elif cmd == 'APPLY_TYPE' and 'TYPE' in params:
            self._set_role(params['TYPE'], 'r2-command', number)
        elif cmd in ('EXCLUDE_OBJECT_DEFINE', 'EXCLUDE_OBJECT_START',
                     'EXCLUDE_OBJECT_END'):
            self._end_path()
            name = params.get('NAME', '')
            if cmd == 'EXCLUDE_OBJECT_END' and not name and self.active:
                obj = self.objects[self.active]
            else:
                obj = self._obj(name)
            if not obj:
                self._warning(number, 'object event without valid name')
                if cmd != 'EXCLUDE_OBJECT_DEFINE':
                    self.active = None
            elif cmd == 'EXCLUDE_OBJECT_DEFINE':
                obj['defines'] += 1
            elif cmd == 'EXCLUDE_OBJECT_START':
                if self.active is not None:
                    self._warning(
                        number, 'overlapping object starts; previous span incomplete')
                self.active = obj['id']
                obj['starts'] += 1
            else:
                if self.active != obj['id']:
                    self._warning(number, 'object end does not match active object')
                obj['ends'] += 1
                self.active = None
            if obj and len(obj['evidence_lines']) < 16:
                obj['evidence_lines'].append(number)

        rkind = record['kind']
        if rkind == 'firmware_retract':
            self._end_path()
            if self._blk_cur_stroke is not None:
                self._blk_strokes.append(self._blk_cur_stroke)
                self._blk_cur_stroke = None
            if record.get('retracted'):
                self.kin['firmware_retracts'] += 1
            else:
                self.kin['firmware_deretracts'] += 1
            return
        if rkind == 'motors_off':
            self._end_path()
            self.kin['motors_off_events'] += 1
            return
        if rkind in ('unknown', 'tool', 'coordinate_reset'):
            self._end_path()
            if self._blk_cur_stroke is not None:
                self._blk_strokes.append(self._blk_cur_stroke)
                self._blk_cur_stroke = None
            return
        if rkind not in ('move', 'arc'):
            return

        is_arc = (rkind == 'arc')
        key, group = self._group()
        group['moves'] += 1
        start, end = record['start_mm'], record['end_mm']
        delta = record['commanded_e_delta_mm']
        feed = record.get('feed_mm_min')
        sz, ez = start['Z'], end['Z']

        # Track negative/positive E-only retracts and Z-hops even without XY change
        if delta is not None and delta < -self.EPS:
            self.kin['negative_e_mm'] += abs(delta)

        if any(v is None for v in (start['X'], start['Y'], end['X'], end['Y'])):
            if delta is not None and abs(delta) > self.EPS:
                if delta < 0:
                    self.kin['retract_moves'] += 1
                else:
                    self.kin['deretract_moves'] += 1
            elif sz is not None and ez is not None and abs(ez - sz) > self.EPS:
                self.kin['z_only_moves'] += 1
                self._observe_zhop(sz, ez)
            self._end_path()
            return

        x0, y0, x1, y1 = start['X'], start['Y'], end['X'], end['Y']
        length = (record['arc_length_mm'] if is_arc
                  else math.hypot(x1 - x0, y1 - y0))
        if not math.isfinite(length):
            raise ValueError('non-finite path length')
        if length <= self.EPS:
            if delta is not None and abs(delta) > self.EPS:
                if delta < 0:
                    self.kin['retract_moves'] += 1
                    self._end_path()
                    if self._blk_cur_stroke is not None:
                        self._blk_strokes.append(self._blk_cur_stroke)
                        self._blk_cur_stroke = None
                else:
                    self.kin['deretract_moves'] += 1
            elif sz is not None and ez is not None and abs(ez - sz) > self.EPS:
                self.kin['z_only_moves'] += 1
                self._observe_zhop(sz, ez)
            return

        group['known_xy_segments'] += 1
        if delta is None or delta <= 0:
            # Non-extruding XY travel
            if is_arc:
                self.kin['arc_travel_moves'] += 1
            else:
                self.kin['linear_travel_moves'] += 1
            self.kin['travel_length_mm'] += length
            self._update_speed_flow(feed, length, 0.0, extruding=False)
            if sz is not None and ez is not None and abs(ez - sz) > self.EPS:
                self._observe_zhop(sz, ez)
            self._end_path()
            if self._blk_cur_stroke is not None:
                self._blk_strokes.append(self._blk_cur_stroke)
                self._blk_cur_stroke = None
            return

        # Positive-extrusion XY (or helical arc) segment
        self._zhop_base_z = ez
        self._zhop_raised = False
        self._advance_physical_layer_on_extrude(ez)

        if sz is not None and ez is not None:
            dz = ez - sz
            if abs(dz) <= 1e-4:
                self.planar_extrude_moves += 1
            elif 0.0 < dz <= 0.05:
                self.continuous_z_extrude_moves += 1
            else:
                self.nonplanar_extrude_moves += 1

        group['extruding_xy_segments'] += 1
        group['extruding_xy_length_mm'] += length
        group['positive_e_mm'] += delta
        if (not math.isfinite(group['extruding_xy_length_mm'])
                or not math.isfinite(group['positive_e_mm'])):
            raise ValueError('numeric overflow in geometric summary')

        if is_arc:
            self.kin['arc_extruding_moves'] += 1
            self.kin['arc_extruding_length_mm'] += length
            bbox4 = list(record['bounds_xy_mm'])
            seg_pts = r2_shadow.sample_arc_points(record, resolution_mm=1.0)
        else:
            self.kin['linear_extruding_moves'] += 1
            bbox4 = [min(x0, x1), min(y0, y1), max(x0, x1), max(y0, y1)]
            seg_pts = [(x0, y0, sz), (x1, y1, ez)]

        self.kin['extruding_length_mm'] += length
        self.kin['positive_e_mm'] += delta
        self._update_speed_flow(feed, length, delta, extruding=True)
        self._touch_unit(self._unit_id, ez, length)
        self._touch_footprint(bbox4, sz, ez, length, delta)
        self._record_cells_and_tag(seg_pts, length, delta)

        bounds = group['bounds_xy_mm']
        if bounds is None:
            group['bounds_xy_mm'] = list(bbox4)
        else:
            bounds[0] = min(bounds[0], bbox4[0])
            bounds[1] = min(bounds[1], bbox4[1])
            bounds[2] = max(bounds[2], bbox4[2])
            bounds[3] = max(bounds[3], bbox4[3])

        # Update polyline path continuity + shoelace signed area
        if (self.path is None or self.path['key'] != key
                or math.hypot(self.path['end'][0] - x0,
                              self.path['end'][1] - y0) > self.CLOSE_MM):
            self._end_path()
            self.path = {'key': key, 'start': (x0, y0), 'end': (x0, y0),
                         'segments': 0, 'twice_area': 0.0,
                         'bbox': list(bbox4)}
        else:
            pb = self.path['bbox']
            pb[0] = min(pb[0], bbox4[0])
            pb[1] = min(pb[1], bbox4[1])
            pb[2] = max(pb[2], bbox4[2])
            pb[3] = max(pb[3], bbox4[3])
        for (ax, ay, _), (bx, by, _) in zip(seg_pts, seg_pts[1:]):
            self.path['segments'] += 1
            self.path['twice_area'] += ax * by - bx * ay
            self.path['end'] = (bx, by)

    def _observe_zhop(self, sz, ez):
        base = self._zhop_base_z if self._zhop_base_z is not None else sz
        if not self._zhop_raised and ez > base + 0.05:
            self._zhop_base_z = base
            self._zhop_raised = True
        elif self._zhop_raised and abs(ez - self._zhop_base_z) <= 0.05:
            self.z_hop_count += 1
            self._zhop_raised = False

    def finish(self):
        self._finish_physical_layer(reset_unit=False)
        if self.active:
            self._warning(self.line_count, 'object span open at end of file')

        total_z_ext = (self.planar_extrude_moves
                       + self.continuous_z_extrude_moves
                       + self.nonplanar_extrude_moves)
        vase_likely = (total_z_ext >= 20
                       and self.continuous_z_extrude_moves >= 0.6 * total_z_ext)
        units_out = []
        for uid in sorted(self._units):
            u = self._units[uid]
            units_out.append({
                'unit_id': u['unit_id'],
                'layer_count': u['layer_count'],
                'z_min_mm': (round(u['z_min_mm'], 4)
                             if u['z_min_mm'] is not None else None),
                'z_max_mm': (round(u['z_max_mm'], 4)
                             if u['z_max_mm'] is not None else None),
                'extruding_length_mm': round(u['extruding_length_mm'], 3),
                'object_ids': sorted(u['object_ids']),
            })
        footprints_out = []
        for fid in sorted(self._footprints):
            fp = self._footprints[fid]
            footprints_out.append({
                'object_id': fp['object_id'],
                'object_name': fp['object_name'],
                'bounds_xy_mm': [round(v, 4) for v in fp['bounds_xy_mm']],
                'z_min_mm': (round(fp['z_min_mm'], 4)
                             if fp['z_min_mm'] is not None else None),
                'z_max_mm': (round(fp['z_max_mm'], 4)
                             if fp['z_max_mm'] is not None else None),
                'extruding_length_mm': round(fp['extruding_length_mm'], 3),
                'positive_e_mm': round(fp['positive_e_mm'], 4),
                'unit_ids': sorted(fp['unit_ids']),
            })
        seq_violations = legacy._sequence_audit193(self._seq_events)
        by_code = Counter(c['code'] for c in self.tag_conflicts)
        sup_ratio = (round(self.supported_upper_cells / float(self.total_upper_cells), 4)
                     if self.total_upper_cells > 0 else None)
        kin_out = dict(self.kin)
        for k in ('extruding_length_mm', 'arc_extruding_length_mm',
                  'travel_length_mm', 'positive_e_mm', 'negative_e_mm',
                  'print_speed_min_mm_s', 'print_speed_max_mm_s',
                  'travel_speed_max_mm_s', 'volumetric_flow_max_mm3_s'):
            if kin_out[k] is not None:
                kin_out[k] = round(kin_out[k], 4)
        kin_out['filament_diameter_mm'] = self.filament_dia_mm
        kin_out['filament_diameter_source'] = self.filament_dia_source

        return {
            'schema': 'r2-evidence/1',
            'objects': list(self.objects.values()),
            'layer_evidence': {
                'boundary_count': self.boundary,
                'boundary_sources': dict(self.boundary_sources),
                'marker_count': self.mark_count,
                'note': 'event boundaries, not proven physical layers; see units_and_layers for positive-extrusion layer evidence',
            },
            'units_and_layers': {
                'unit_count': len(units_out),
                'sequential_by_object': len(units_out) > 1,
                'physical_extrusion_layers': self._physical_layers,
                'z_hop_count': self.z_hop_count,
                'planar_extrude_moves': self.planar_extrude_moves,
                'continuous_z_extrude_moves': self.continuous_z_extrude_moves,
                'nonplanar_extrude_moves': self.nonplanar_extrude_moves,
                'vase_mode_likely': vase_likely,
                'units': units_out,
            },
            'kinematics': kin_out,
            'object_footprints': footprints_out,
            'topology_2d': {
                'outer_closed_loops': self.outer_loops,
                'nested_closed_loops': self.nested_loops,
                'ccw_closed_loops': self.ccw_loops,
                'cw_closed_loops': self.cw_loops,
                'parallel_open_hatch_blocks': self.parallel_hatch_groups,
                'note': 'bounding-box loop nesting and open-stroke parallelism over known shadow segments',
            },
            'support_3d': {
                'cell_mm': self.CELL_MM,
                'upper_layer_cells': self.total_upper_cells,
                'supported_upper_cells': self.supported_upper_cells,
                'supported_ratio': sup_ratio,
                'note': '1-cell dilated vertical grid continuity across positive-extrusion shadow moves',
            },
            'sequence_and_tag_audit': {
                'tagged_blocks': self.tagged_blocks,
                'empty_tag_blocks': self.empty_tag_blocks,
                'sequence_violations': seq_violations,
                'geometry_conflicts': self.tag_conflicts,
                'geometry_conflicts_by_code': dict(sorted(by_code.items())),
                'note': 'non-destructive consistency checks between explicit tags and observed trajectories',
            },
            'groups': list(self.group.values()),
            'pattern_metadata': self.patterns,
            'warnings': self.warnings,
            'warning_count': self.warning_count,
            'limitations': [
                'object IDs represent explicit names in this file, not proven geometry',
                'roles are unverified comments or R2 markers, not ground truth',
                'pattern metadata is independent of role and is not geometric pattern recognition',
                'geometry is logical G-code space; unknown commands invalidate shadow state',
                'closed-path area, grid support and flow rates are estimates, not physical certification',
            ],
        }
