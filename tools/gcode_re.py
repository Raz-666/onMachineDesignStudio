#!/usr/bin/env python3
"""R2 Reverse-Engineering engine v3 - unified Masterkonzept Pass 0-11 pipeline.

This is the unified, evidence-first analysis entry point described by the
Masterkonzept ("G-Code Reverse Engineering und geometrische Feature-Erkennung
per Post-Processing"). It composes the verified streaming engines:

  Pass 0-2   raw bytes -> modal state -> moves   (r2_shadow, fail-closed)
  Pass 3-10  layer/kinematics/topology evidence  (r2_analysis.Tracker)

and adds the two pieces that were missing as a unified contract:

  Pass 6/9   vector 2D geometry per Z-plane bucket (gap-clustered Z levels,
             not guaranteed physical layers): real loop chaining
             (endpoint-tolerant, online cycle extraction), shoelace area,
             nesting hierarchy from point-in-polygon, open-hatch
             direction/spacing statistics
  Pass 8     feature scoring v2: multi-signal evidence with top-3 hypotheses,
             explicit UNKNOWN/AMBIGUOUS, scores labelled `score` (never
             `probability`) and `calibrated: false`

Pass 10 performs conservation checks (line accounting, extrusion filament,
known-XYZ move length) and reports them as structured checks, never as a
print-safety statement. Pass 11 writes the sidecar JSON atomically; the
source file is opened read-only and is never modified. No move command,
header, comment or setting is ever altered - output is analysis only.

Honesty rules enforced here (Masterkonzept SS0.2/SS8.1):
  * no score is a calibrated probability; every score ships with its evidence
  * low/contradictory evidence yields AMBIGUOUS or UNKNOWN, never a guess
  * limitations are listed in every report
  * comments are evidence, not truth
"""
import argparse
from collections import Counter, defaultdict
from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import re
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import r2_analysis  # noqa: E402
import r2_shadow  # noqa: E402

TOOL_VERSION = '3.0.0'
REPORT_SCHEMA = 'r2-re/2'
MAX_LINE = 1024 * 1024          # 1 MiB per line, matches analysis limits
MAX_BUCKETS = 2048              # Z plane buckets (vase/spiral mode usually 1)
MAX_SEGMENTS = 250000           # extrusion segments kept for Pass 6/9
MAX_LOOPS_PER_BUCKET = 400      # nesting depth computed on the largest loops
MAX_BUCKETS_OUT = 64            # buckets detailed in the report
JOIN_EPS_DEFAULT = 0.1          # mm endpoint tolerance for loop chaining (Orca seams land ~0.06 mm apart)
PLANE_GAP_DEFAULT = 0.05        # mm; extrusion Z levels closer than this join one plane bucket
HATCH_MIN_STROKES = 6           # below this no spacing estimate is issued
MIN_EVIDENCE_FOR_FEATURE = 0.20 # below this -> UNKNOWN (Masterkonzept 8.1)
RE_FEATURE = re.compile(
    r'^\s*;\s*(?:TYPE\s*:|FEATURE\s*:|STRUCTURE\s*:|feature\s+)(.*?)\s*$', re.I)

# Non-calibrated starting weights (Masterkonzept 8.1: configurable, later to be
# calibrated on labelled data). They are NOT probabilities.
W = {
    'tag_file_dominant': 0.15,   # the file's dominant feature tag, applied per bucket
    'depth0_closed_loop': 0.45,  # outermost closed contour on this plane
    'nested_closed_loop': 0.40,  # loop nested inside another contour
    'hatch_dense': 0.35,         # parallel open strokes with tight spacing
    'hatch_sparse': 0.35,        # parallel open strokes with wide spacing
    'first_layer_plane': 0.25,   # lowest extruding plane (bottom/skirt/brim context)
    'last_layer_plane': 0.25,    # highest extruding plane
    'first_layer_adhesion': 0.20,
    'ironing_signature': 0.25,   # very low E/mm on dense last-plane strokes
}


def _fil_area_mm2(diameter_mm):
    return math.pi * (diameter_mm / 2.0) ** 2


def _shoelace_area(points):
    """Signed polygon area of a CLOSED point list, or None if degenerate."""
    n = len(points)
    if n < 3:
        return None
    acc = 0.0
    for i in range(n):
        x0, y0 = points[i][0], points[i][1]
        x1, y1 = points[(i + 1) % n][0], points[(i + 1) % n][1]
        acc += x0 * y1 - x1 * y0
    return acc / 2.0


def _point_in_polygon(point, polygon):
    """Ray casting. polygon is a list of (x, y, ...) points (implicitly closed)."""
    x, y = point[0], point[1]
    inside = False
    n = len(polygon)
    j = n - 1
    for i in range(n):
        xi, yi = polygon[i][0], polygon[i][1]
        xj, yj = polygon[j][0], polygon[j][1]
        if (yi > y) != (yj > y):
            xcross = xi + (y - yi) * (xj - xi) / (yj - yi)
            if x < xcross:
                inside = not inside
        j = i
    return inside


class PlaneBucket:
    """Extrusion segments and loop/hatch evidence for one Z plane bucket.

    `z` is the first Z at which extrusion was observed for this plane bucket;
    buckets are Z levels, not guaranteed physical layers (see Pass 3 notes).
    """

    def __init__(self, z_rounded):
        self.z = z_rounded
        self.z_min = z_rounded
        self.z_max = z_rounded
        self.segments = []          # list of (p0, p1, de_mm) tuples of (x, y)
        self.extruding_length_mm = 0.0
        self.positive_e_mm = 0.0
        self.moves = 0
        self.loops = []             # dicts after Pass 6
        self.open_paths = 0
        self.hatch = None           # open hatch statistics after Pass 6/9

    def add(self, p0, p1, de_mm, seg_len):
        self.moves += 1
        self.extruding_length_mm += seg_len
        self.positive_e_mm += de_mm
        if len(self.segments) < MAX_SEGMENTS:
            self.segments.append((p0, p1, de_mm))

    # ------------------------------------------------------------------ Pass 5/6
    def _chain_loops(self, eps):
        """Greedily join segments into paths; classify closed loops.

        Returns (loops, open_path_count, dropped_segments). Tolerance eps in mm.
        Arcs arrive already subdivided by the caller, so every element is a
        straight chord. A segment may be walked forward or reversed.
        """
        segs = self.segments
        if not segs:
            return [], 0, 0
        eps_cell = max(eps * 4.0, 0.2)
        cell = eps_cell
        index = defaultdict(list)
        for i, (a, b, _de) in enumerate(segs):
            index[(int(math.floor(a[0] / cell)), int(math.floor(a[1] / cell)))].append((i, 0))
            index[(int(math.floor(b[0] / cell)), int(math.floor(b[1] / cell)))].append((i, 1))
        used = [False] * len(segs)

        def match(point, radius):
            cx, cy = int(math.floor(point[0] / cell)), int(math.floor(point[1] / cell))
            best = None
            for dx in (-1, 0, 1):
                for dy in (-1, 0, 1):
                    for i, end in index.get((cx + dx, cy + dy), ()):
                        if used[i]:
                            continue
                        ep = segs[i][end]
                        d = math.hypot(ep[0] - point[0], ep[1] - point[1])
                        if d <= radius and (best is None or d < best[2]):
                            best = (i, end, d)
            return best

        class _Chain:
            """Greedy chain with online cycle extraction.

            A closed loop is emitted as soon as the growing endpoint re-meets an
            earlier vertex of the chain (within eps); the emitted sub-chain is
            detached and growth continues from that junction. This is what makes
            rings work even when another stroke branches off the junction.
            """

            def __init__(self):
                self.path = []
                self.vert_index = {}
                self.loops = []

            def _key(self, point):
                return (int(math.floor(point[0] / eps_cell)),
                        int(math.floor(point[1] / eps_cell)))

            def _rebuild_index(self):
                self.vert_index = {}
                for i, pt in enumerate(self.path):
                    self.vert_index.setdefault(self._key(pt), []).append(i)

            def _try_close_forward(self):
                while True:
                    p = self.path[-1]
                    cx = int(math.floor(p[0] / eps_cell))
                    cy = int(math.floor(p[1] / eps_cell))
                    candidates = []
                    for dx in (-1, 0, 1):
                        for dy in (-1, 0, 1):
                            candidates.extend(self.vert_index.get((cx + dx, cy + dy), ()))
                    cand = [k for k in candidates
                            if 0 <= k <= len(self.path) - 4
                            and math.hypot(self.path[k][0] - p[0],
                                           self.path[k][1] - p[1]) <= eps]
                    if not cand:
                        return
                    k = min(cand)
                    loop = self.path[k:]
                    if _shoelace_area(loop) is None:
                        return
                    self.loops.append(loop)
                    self.path = self.path[:k] + [p]
                    self._rebuild_index()

            def append(self, point):
                self.path.append(point)
                self.vert_index.setdefault(self._key(point), []).append(len(self.path) - 1)
                self._try_close_forward()

            def prepend(self, point):
                self.path.insert(0, point)
                self._rebuild_index()
                # mirror of the forward closure check on the front side
                p = self.path[0]
                candidates = []
                cx = int(math.floor(p[0] / eps_cell))
                cy = int(math.floor(p[1] / eps_cell))
                for dx in (-1, 0, 1):
                    for dy in (-1, 0, 1):
                        candidates.extend(self.vert_index.get((cx + dx, cy + dy), ()))
                cand = [k for k in candidates
                        if len(self.path) - k >= 4
                        and math.hypot(self.path[k][0] - p[0],
                                       self.path[k][1] - p[1]) <= eps]
                if cand:
                    k = max(cand)
                    loop = self.path[:k + 1]
                    if _shoelace_area(loop) is not None:
                        self.loops.append(loop)
                        self.path = [p] + self.path[k + 1:]
                        self._rebuild_index()

        loops, open_paths, dropped = [], 0, 0
        for start_i in range(len(segs)):
            if used[start_i]:
                continue
            used[start_i] = True
            a, b, _de = segs[start_i]
            chain = _Chain()
            chain.append(a)
            chain.append(b)
            # extend forward
            while True:
                nxt = match(chain.path[-1], eps)
                if nxt is None:
                    break
                i, end, _d = nxt
                used[i] = True
                seg = segs[i]
                chain.append(seg[1] if end == 0 else seg[0])
            # extend backward (the reversed polyline grows to the left)
            while True:
                prv = match(chain.path[0], eps)
                if prv is None:
                    break
                i, end, _d = prv
                used[i] = True
                seg = segs[i]
                chain.prepend(seg[1] if end == 0 else seg[0])
            for loop_pts in chain.loops:
                area = _shoelace_area(loop_pts)
                loops.append({
                    'points': loop_pts,
                    'signed_area_mm2': round(area, 4),
                    'area_mm2': round(abs(area), 4),
                    'perimeter_mm': round(sum(
                        math.hypot(loop_pts[k + 1][0] - loop_pts[k][0],
                                   loop_pts[k + 1][1] - loop_pts[k][1])
                        for k in range(len(loop_pts) - 1)), 4),
                    'orientation': 'ccw' if area >= 0 else 'cw',
                    'bbox_mm': [round(min(p[0] for p in loop_pts), 4),
                                round(min(p[1] for p in loop_pts), 4),
                                round(max(p[0] for p in loop_pts), 4),
                                round(max(p[1] for p in loop_pts), 4)],
                })
            if len(chain.path) >= 2:
                open_paths += 1
        return loops, open_paths, dropped

    @staticmethod
    def _nesting_depth(loops):
        """Assign containment depth. Bbox prefilter, ray-cast point-in-polygon."""
        ordered = sorted(range(len(loops)), key=lambda i: loops[i]['area_mm2'], reverse=True)[:MAX_LOOPS_PER_BUCKET]
        depth = {i: 0 for i in ordered}
        for pos, i in enumerate(ordered):
            for j in ordered[:pos]:
                if loops[j]['bbox_mm'][0] > loops[i]['bbox_mm'][2] or \
                   loops[j]['bbox_mm'][2] < loops[i]['bbox_mm'][0] or \
                   loops[j]['bbox_mm'][1] > loops[i]['bbox_mm'][3] or \
                   loops[j]['bbox_mm'][3] < loops[i]['bbox_mm'][1]:
                    continue
                if _point_in_polygon(loops[i]['points'][0], loops[j]['points']):
                    depth[i] += 1
        return depth

    def run_geometry(self, eps):
        loops, open_paths, _dropped = self._chain_loops(eps)
        depth = self._nesting_depth(loops) if loops else {}
        for i, lp in enumerate(loops):
            lp['nesting_depth'] = depth.get(i, 0)
            # drop the heavy point list from the report payload; keep statistics
            lp.pop('points', None)
        self.loops = sorted(loops, key=lambda lp: lp['area_mm2'], reverse=True)
        self.open_paths = open_paths
        return self.loops

    def run_hatch(self):
        """Direction histogram + spacing estimate over open strokes (Pass 9-ish)."""
        strokes = []
        for a, b, _de in self.segments:
            dx, dy = b[0] - a[0], b[1] - a[1]
            length = math.hypot(dx, dy)
            if length >= 2.0:
                strokes.append((a, b, length, math.atan2(dy, dx)))
        if len(strokes) < HATCH_MIN_STROKES:
            self.hatch = {'stroke_count': len(strokes),
                          'verdict': 'INSUFFICIENT_STROKES',
                          'note': f'need at least {HATCH_MIN_STROKES} strokes; no spacing estimate issued'}
            return self.hatch
        # direction histogram in 15-degree buckets, diametrically folded
        hist = Counter()
        for _a, _b, _l, ang in strokes:
            deg = math.degrees(ang) % 180.0
            hist[int(deg // 15) * 15] += 1
        dominant_bucket, dominant_n = max(hist.items(), key=lambda kv: kv[1])
        dominant_share = dominant_n / len(strokes)
        # second orthogonal family?
        orth = ((dominant_bucket + 90) % 180) // 15 * 15
        orth_share = hist.get(orth, 0) / len(strokes)
        cang, sang = math.cos(math.radians(dominant_bucket)), math.sin(math.radians(dominant_bucket))
        nx, ny = -sang, cang            # normal direction
        mids = []
        for a, b, _l, _ang in strokes:
            deg = math.degrees(_ang) % 180.0
            if int(deg // 15) * 15 != dominant_bucket:
                continue
            mx, my = (a[0] + b[0]) / 2.0, (a[1] + b[1]) / 2.0
            mids.append(mx * nx + my * ny)
        mids.sort()
        gaps = [mids[i + 1] - mids[i] for i in range(len(mids) - 1)]
        gaps = [g for g in gaps if g > 1e-3]
        spacing = None
        if len(gaps) >= HATCH_MIN_STROKES - 1:
            sg = sorted(gaps)
            spacing = round(sg[len(sg) // 2], 4)
        if dominant_share >= 0.70:
            verdict = 'RECTILINEAR_LIKE'
        elif orth_share >= 0.25 and dominant_share >= 0.30:
            verdict = 'GRID_LIKE'
        else:
            verdict = 'UNKNOWN_PATTERN'
        self.hatch = {
            'stroke_count': len(strokes),
            'dominant_direction_deg': dominant_bucket,
            'dominant_share': round(dominant_share, 4),
            'orthogonal_share': round(orth_share, 4),
            'spacing_mm': spacing,
            'verdict': verdict,
            'note': 'direction statistics over open strokes only; role is decided by Pass 8, not by this verdict',
        }
        return self.hatch


def _dominant_tag_role(counter):
    if not counter:
        return None
    role, _n = max(counter.items(), key=lambda kv: kv[1])
    return role


def _score_bucket(bucket, *, is_first, is_last, dominant_role, line_width_est_mm):
    """Feature scoring v2 for one plane bucket (Masterkonzept 8.1/8.2-8.13).

    Returns dict with top-3 hypotheses, evidence and confidence. Scores are
    bounded heuristic scores, NOT calibrated probabilities.
    """
    ev = []
    raw = defaultdict(float)
    loops = bucket.loops
    depth0 = sum(1 for lp in loops if lp['nesting_depth'] == 0)
    nested = sum(1 for lp in loops if lp['nesting_depth'] >= 1)
    if depth0:
        raw['OUTER_WALL'] += W['depth0_closed_loop']
        ev.append(f'{depth0} outermost closed loop(s) on plane (depth 0)')
    if nested:
        raw['INNER_WALL'] += W['nested_closed_loop']
        raw['HOLE_WALL'] += W['nested_closed_loop'] * 0.6
        ev.append(f'{nested} nested closed loop(s) (depth >= 1)')
    if is_first:
        raw['BOTTOM_SURFACE'] += W['first_layer_plane']
        raw['SKIRT'] += W['first_layer_adhesion']
        raw['BRIM'] += W['first_layer_adhesion']
        ev.append('lowest extruding plane in file')
    if is_last:
        raw['TOP_SURFACE'] += W['last_layer_plane']
        ev.append('highest extruding plane in file')
    dense = sparse = None
    if bucket.hatch and bucket.hatch.get('spacing_mm') is not None:
        sp = bucket.hatch['spacing_mm']
        if line_width_est_mm:
            ratio = sp / line_width_est_mm
            dense = ratio < 1.6
            sparse = ratio >= 2.4
        else:
            dense = sp < 0.6
            sparse = sp >= 1.2
        if dense:
            raw['SOLID_INFILL'] += W['hatch_dense']
            raw['TOP_SURFACE'] += W['hatch_dense'] * 0.8
            raw['BOTTOM_SURFACE'] += W['hatch_dense'] * 0.8
            raw['INTERNAL_SOLID_INFILL'] += W['hatch_dense'] * 0.6
            ev.append(f'dense parallel hatch, spacing {sp:.3f} mm (ratio vs line width {ratio if line_width_est_mm else "n/a"})')
        elif sparse:
            raw['SPARSE_INFILL'] += W['hatch_sparse']
            ev.append(f'sparse parallel hatch, spacing {sp:.3f} mm (ratio vs line width {ratio if line_width_est_mm else "n/a"})')
        else:
            ev.append(f'hatch spacing {sp:.3f} mm between solid/sparse bands; ambiguous coverage')
        # ironing signature: dense hatch + last plane + very low extrusion per length
        if is_last and bucket.extruding_length_mm > 0:
            e_per_mm = bucket.positive_e_mm / bucket.extruding_length_mm
            if e_per_mm < 0.012:
                raw['IRONING'] += W['ironing_signature']
                ev.append(f'very low filament/mm ({e_per_mm:.4f}) on dense last-plane strokes')
    if dominant_role:
        mapped = dominant_role.upper().replace('-', '_').replace(' ', '_')
        aliases = {
            'SURFACE_TOP': 'TOP_SURFACE', 'SURFACE_BOTTOM': 'BOTTOM_SURFACE',
            'WALL_OUTER': 'OUTER_WALL', 'WALL_INNER': 'INNER_WALL',
            'INFILL': 'SPARSE_INFILL', 'SKIN': 'TOP_SURFACE',
        }
        mapped = aliases.get(mapped, mapped)
        if mapped in ('OUTER_WALL', 'INNER_WALL', 'SPARSE_INFILL', 'SOLID_INFILL',
                      'TOP_SURFACE', 'BOTTOM_SURFACE', 'IRONING', 'BRIM', 'SKIRT',
                      'SUPPORT', 'SUPPORT_INTERFACE', 'GAP_FILL'):
            raw[mapped] += W['tag_file_dominant']
            ev.append(f'file-dominant feature tag: {dominant_role} (comment/APPLY_TYPE evidence)')
    total = sum(raw.values())
    if total < MIN_EVIDENCE_FOR_FEATURE:
        return {
            'plane_z_first_mm': bucket.z,
            'verdict': 'UNKNOWN',
            'reason': 'insufficient independent evidence (no outer/nested loops, no hatch statistics, no usable tag)',
            'score': 0.0,
            'level': 'UNKNOWN',
            'calibrated_probability': None,
            'top3': [],
            'evidence': ev,
        }
    ordered = sorted(raw.items(), key=lambda kv: kv[1], reverse=True)
    top = max(ordered[0][1], 0.0)
    score = min(0.95, round(top, 3))
    lead = top - (ordered[1][1] if len(ordered) > 1 else 0.0)
    if score >= 0.75 and lead >= 0.15:
        level = 'HIGH'
    elif score >= 0.45:
        level = 'MEDIUM'
    else:
        level = 'LOW'
    return {
        'plane_z_first_mm': bucket.z,
        'verdict': ordered[0][0],
        'score': score,
        'level': level,
        'calibrated_probability': None,
        'top3': [{'feature': name, 'score': min(0.95, round(s, 3))} for name, s in ordered[:3]],
        'evidence': ev,
    }


def _sha256_file(path):
    h = hashlib.sha256()
    with open(path, 'rb') as fh:
        while True:
            chunk = fh.read(1024 * 1024)
            if not chunk:
                break
            h.update(chunk)
    return h.hexdigest()


def analyse(path, *, join_eps=JOIN_EPS_DEFAULT, plane_gap=PLANE_GAP_DEFAULT,
            max_bytes=512 * 1024 * 1024,
            assumed_passive=(), assume_klipper_defaults=False, dialect='klipper',
            enable_arcs=False, firmware_retract=False, klipper_passive=False,
            verified_r2_passive=False, with_moves=False, max_moves=None):
    """Full Masterkonzept pass 0-11 offline analysis. Read-only on the source."""
    src = Path(path)
    warnings = []
    state = r2_shadow.Shadow(
        assume_klipper_defaults=assume_klipper_defaults, dialect=dialect,
        assumed_passive=tuple(assumed_passive), enable_arcs=enable_arcs,
        firmware_retract=firmware_retract, klipper_passive=klipper_passive,
        verified_r2_passive=verified_r2_passive)
    evidence = r2_analysis.Tracker()
    record_counts = Counter()
    unknown_reasons = Counter()
    unknown_examples = []
    tag_counter = Counter()
    buckets = {}                    # plane id -> PlaneBucket
    plane_state = {'ref_z': None, 'id': -1}
    segment_dropped = 0
    ratio_samples = []              # E-per-mm per qualifying extrusion move
    z_step_samples = []             # consecutive extrusion-Z diffs in [0.02, 0.6] mm
    prev_extrude_z = [None]
    moves_kept = []
    moves_truncated = False
    known_xyz = 0
    fil_positive = 0.0
    fil_positive_motion = 0.0
    fil_negative = 0.0
    move_len_known = 0.0
    lines = 0
    hash_in = hashlib.sha256()
    bytes_in = 0
    extruding_plane_order = []     # first-appearance order of extruding z buckets
    with open(src, 'rb') as fh:
        while True:
            raw_bytes = fh.readline(MAX_LINE + 1)
            if not raw_bytes:
                break
            if len(raw_bytes) > MAX_LINE:
                raise ValueError('line exceeds 1 MiB analysis limit')
            hash_in.update(raw_bytes)
            bytes_in += len(raw_bytes)
            if bytes_in > max_bytes:
                raise ValueError('source exceeds configured byte limit')
            lines += 1
            raw = raw_bytes.decode('utf-8', errors='surrogateescape')
            number = lines
            record = state.process(raw, number)
            evidence.observe(raw, record)
            kind = record['kind']
            record_counts[kind] += 1
            if kind == 'unknown':
                reason = record.get('reason', 'unknown')
                unknown_reasons[reason] += 1
                if len(unknown_examples) < 12:
                    unknown_examples.append({'line': number,
                                             'text': raw.rstrip('\r\n')[:200],
                                             'reason': reason})
            f = RE_FEATURE.match(raw.rstrip('\r\n'))
            if f:
                tag_counter[f.group(1)[:120]] += 1
            if kind in ('move', 'arc'):
                start, end = record.get('start_mm'), record.get('end_mm')
                de = record.get('commanded_e_delta_mm')
                if end is not None and all(v is not None for v in end.values()):
                    known_xyz += 1
                    if start is not None and all(v is not None for v in start.values()):
                        if kind == 'move':
                            move_len_known += math.dist(
                                (start['X'], start['Y'], start['Z']),
                                (end['X'], end['Y'], end['Z']))
                        else:
                            move_len_known += record.get('path_length_3d_mm') or 0.0
                if de is not None:
                    if de > 0:
                        move_len = None
                        if start is not None and end is not None and all(
                                v is not None for v in (*start.values(), *end.values())):
                            if kind == 'move':
                                move_len = math.hypot(end['X'] - start['X'], end['Y'] - start['Y'])
                            else:
                                move_len = record.get('arc_length_mm')
                        fil_positive += de
                        if move_len and move_len > 1e-9:
                            fil_positive_motion += de
                    elif de < 0:
                        fil_negative += de
                if de is not None and de > 0 and start is not None and end is not None:
                    if end['Z'] is not None:
                        if prev_extrude_z[0] is not None:
                            dz_step = end['Z'] - prev_extrude_z[0]
                            if 0.02 <= dz_step <= 0.6 and len(z_step_samples) < 200000:
                                z_step_samples.append(dz_step)
                        prev_extrude_z[0] = end['Z']
                        z = end['Z']
                        if plane_state['ref_z'] is None or abs(z - plane_state['ref_z']) > plane_gap:
                            plane_state['id'] += 1
                        plane_state['ref_z'] = z
                        zid = plane_state['id']
                        if zid >= MAX_BUCKETS:
                            segment_dropped += 1
                            continue
                        if zid not in buckets:
                            buckets[zid] = PlaneBucket(round(z, 3))
                            extruding_plane_order.append(zid)
                        bucket = buckets[zid]
                        bucket.z_min = min(bucket.z_min, z)
                        bucket.z_max = max(bucket.z_max, z)
                        if kind == 'move':
                            pts = [(start['X'], start['Y']), (end['X'], end['Y'])]
                            seg_len = math.hypot(end['X'] - start['X'], end['Y'] - start['Y'])
                            if seg_len > 1e-9:
                                bucket.add(pts[0], pts[1], de, seg_len)
                            if 1.0 <= seg_len <= 500.0:
                                ratio_samples.append(de / seg_len)
                        else:
                            pts3 = r2_shadow.sample_arc_points(record, resolution_mm=1.0)
                            if len(pts3) >= 2:
                                seg_len = 0.0
                                for k in range(len(pts3) - 1):
                                    a, b = pts3[k], pts3[k + 1]
                                    if a[0] is None or b[0] is None:
                                        continue
                                    seg_len += math.hypot(b[0] - a[0], b[1] - a[1])
                                    bucket.add((a[0], a[1]), (b[0], b[1]), de,
                                               math.hypot(b[0] - a[0], b[1] - a[1]))
            if with_moves and kind in ('move', 'arc'):
                if max_moves is not None and len(moves_kept) >= max_moves:
                    moves_truncated = True
                else:
                    rec_out = {'line': number, 'kind': kind,
                               'command': record.get('command'),
                               'start_mm': record.get('start_mm'),
                               'end_mm': record.get('end_mm'),
                               'commanded_e_delta_mm': de,
                               'feed_mm_min': record.get('feed_mm_min')}
                    if kind == 'arc':
                        rec_out['arc_length_mm'] = record.get('arc_length_mm')
                    moves_kept.append(rec_out)

    # ------------------------------------------------------------------ Pass 6/9
    bucket_summaries = []
    total_loops = total_open = 0
    for zid in sorted(buckets):
        bucket = buckets[zid]
        bucket.run_geometry(join_eps)
        bucket.run_hatch()
        total_loops += len(bucket.loops)
        total_open += bucket.open_paths
        if len(bucket_summaries) < MAX_BUCKETS_OUT:
            bucket_summaries.append({
                'z_first_mm': bucket.z,
                'z_min_mm': round(bucket.z_min, 4),
                'z_max_mm': round(bucket.z_max, 4),
                'extruding_length_mm': round(bucket.extruding_length_mm, 4),
                'positive_e_mm': round(bucket.positive_e_mm, 4),
                'closed_loops': len(bucket.loops),
                'open_paths': bucket.open_paths,
                'outer_loops_depth0': sum(1 for lp in bucket.loops if lp['nesting_depth'] == 0),
                'nested_loops': sum(1 for lp in bucket.loops if lp['nesting_depth'] >= 1),
                'max_loop_area_mm2': (bucket.loops[0]['area_mm2'] if bucket.loops else 0.0),
                'hatch': bucket.hatch,
                'loops': bucket.loops,
            })
    if len(buckets) > MAX_BUCKETS_OUT:
        warnings.append(f'report truncates plane bucket detail to first {MAX_BUCKETS_OUT} of {len(buckets)} buckets')

    # ------------------------------------------------------------- line width
    # Median effective cross-section from tracked extrusion, then line width at
    # the median plane-height delta (estimates, never exact).
    line_width_est = None  # computed after the tracker report exists (filament dia)

    # -------------------------------------------------------------- Pass 10
    tracker_report = evidence.finish()
    # line width estimate: e_per_mm * filament_area / layer_height (100% flow)
    try:
        fil_dia = float(tracker_report['kinematics'].get('filament_diameter_mm') or 1.75)
        ratios = list(ratio_samples)
        if ratios:
            ratios.sort()
            med_e_per_mm = ratios[len(ratios) // 2]
            if len(z_step_samples) >= 5:
                zs = sorted(z_step_samples)
                layer_h = zs[len(zs) // 2]
                if layer_h and layer_h > 1e-6:
                    line_width_est = med_e_per_mm * _fil_area_mm2(fil_dia) / layer_h
    except Exception as exc:  # estimator must never kill the analysis
        warnings.append(f'line width estimate unavailable: {exc}')
        line_width_est = None

    # --------------------------------------------------------------- Pass 8
    dominant_role = _dominant_tag_role(tag_counter)
    if extruding_plane_order:
        first_z, last_z = extruding_plane_order[0], extruding_plane_order[-1]
    else:
        first_z = last_z = None
    feature_planes = []
    for zid in sorted(buckets):
        bucket = buckets[zid]
        feature_planes.append(_score_bucket(
            bucket,
            is_first=(zid == first_z),
            is_last=(zid == last_z),
            dominant_role=dominant_role,
            line_width_est_mm=line_width_est))

    try:
        track_pos_e = float(tracker_report['kinematics'].get('positive_e_mm') or 0.0)
    except (KeyError, TypeError, ValueError):
        track_pos_e = None
    e_ratio = None
    if track_pos_e and fil_positive_motion:
        e_ratio = round(fil_positive_motion / track_pos_e, 6)
    audit = {
        'lines_accounted_for': lines == sum(record_counts.values()),
        'lines_read': lines,
        'record_kind_total': sum(record_counts.values()),
        'moves_with_known_xyz_end': known_xyz,
        'extrusion_filament_mm': round(fil_positive, 4),
        'extrusion_filament_with_motion_mm': round(fil_positive_motion, 4),
        'retraction_filament_mm': round(fil_negative, 4),
        'shadow_vs_tracker_positive_e_ratio': e_ratio,
        'checks': [],
    }
    audit['checks'].append({
        'name': 'line_accounting',
        'status': 'pass' if audit['lines_accounted_for'] else 'FAIL',
        'detail': f'{lines} lines -> {sum(record_counts.values())} records'})
    if e_ratio is None:
        audit['checks'].append({'name': 'extrusion_conservation', 'status': 'skip',
                                'detail': 'no positive extrusion tracked on one of the two sides'})
    elif abs(1.0 - e_ratio) <= 0.02:
        audit['checks'].append({'name': 'extrusion_conservation', 'status': 'pass',
                                'detail': f'ratio {e_ratio} (shadow vs tracker, motion moves only) within 2%'})
    else:
        audit['checks'].append({'name': 'extrusion_conservation', 'status': 'WARN',
                                'detail': f'ratio {e_ratio} (shadow vs tracker, motion moves only) outside 2% - check arcs/settings'})
    audit['status'] = ('FAIL' if any(c['status'] == 'FAIL' for c in audit['checks'])
                       else 'warnings' if any(c['status'] == 'WARN' for c in audit['checks'])
                       else 'ok')

    # ------------------------------------------------------------- Pass 11
    report = {
        'schema': REPORT_SCHEMA,
        'tool': {'name': 'gcode_re', 'version': TOOL_VERSION},
        'provenance': {
            'input_path': src.name,
            'input_sha256': hash_in.hexdigest(),
            'input_bytes': bytes_in,
            'generated_utc': datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'),
            'options': {
                'join_eps_mm': join_eps,
                'plane_gap_mm': plane_gap,
                'layer_height_step_samples': len(z_step_samples),
                'dialect': dialect,
                'enable_arcs': enable_arcs,
                'firmware_retract': firmware_retract,
                'klipper_passive': klipper_passive,
                'verified_r2_passive': verified_r2_passive,
                'klipper_defaults_assumed': bool(assume_klipper_defaults),
                'assumed_passive_commands': sorted(state.assumed_passive),
            },
        },
        'tag_comment_counts': dict(tag_counter),
        'dominant_tag_role': dominant_role,
        'record_counts': dict(record_counts),
        'moves_meta': {'with_moves': with_moves, 'records': len(moves_kept),
                       'truncated': moves_truncated, 'cap': max_moves},
        'unknown_reasons': dict(unknown_reasons),
        'unknown_examples': unknown_examples,
        'segments': {'planes': len(buckets), 'dropped_overflow': segment_dropped,
                     'cap_per_plane': MAX_SEGMENTS},
        'z_planes': bucket_summaries,
        'plane_totals': {'extruding_planes': len(buckets),
                         'closed_loops': total_loops,
                         'open_paths': total_open},
        'line_width_estimate_mm': (round(line_width_est, 4) if line_width_est else None),
        'line_width_note': 'estimate from E-per-mm over median plane spacing; not a measurement',
        'feature_planes': feature_planes,
        'evidence': tracker_report,
        'audit': audit,
        'warnings': warnings,
        'limitations': [
            'scores are heuristic evidence weights, never calibrated probabilities',
            'comments/tags are evidence, not ground truth for feature roles',
            'coordinates are logical G-code values, not measured machine positions',
            'z-plane buckets merge Z levels rising < plane_gap between consecutive extruding moves; on ultra-adaptive or non-planar prints this merges many levels and loop/feature statistics degrade (the tracker physical-layer evidence remains the layer estimate)',
            'loops are found per Z plane bucket with endpoint tolerance; crossing strokes are not split',
            'hatch spacing is a median-of-gaps statistic; grid/concentric families are verdicts, not role assignments',
            'support rolls, raft, prime tower and tool changes are NOT inferred by this tool',
            'no physical print-safety, thermal or mechanical statement is made or implied',
            'unknown commands invalidate shadow state for following lines by design',
        ],
    }
    if with_moves:
        report['moves'] = moves_kept
    return report


def _write_atomic(destination, payload_bytes, force=False):
    dest = Path(destination)
    if dest.exists() and not force:
        raise FileExistsError(f'{dest} exists; pass --force to overwrite (input is never overwritten)')
    if dest.suffix.lower() != '.json':
        raise ValueError('output must end in .json')
    parent = dest.parent.resolve(strict=True)
    fd, tmp = tempfile.mkstemp(prefix='.gcode-re-', dir=parent)
    try:
        with os.fdopen(fd, 'wb') as out:
            out.write(payload_bytes)
            out.flush()
            os.fsync(out.fileno())
        os.replace(tmp, dest)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def _print_summary(report, out_path):
    planes = report['plane_totals']
    audit = report['audit']
    print(f"gcode_re v{TOOL_VERSION} -> {out_path}")
    print(f"  input: {report['provenance']['input_path']} ({report['provenance']['input_bytes']} B, sha256 {report['provenance']['input_sha256'][:16]}…)")
    print(f"  records: {report['record_counts']}")
    print(f"  extruding planes: {planes['extruding_planes']}, closed loops: {planes['closed_loops']}, open paths: {planes['open_paths']}")
    if report['line_width_estimate_mm']:
        print(f"  line width estimate: {report['line_width_estimate_mm']} mm (estimate, not measurement)")
    for fp in report['feature_planes'][:4]:
        if fp.get('top3'):
            top = ', '.join(f"{t['feature']}={t['score']}" for t in fp['top3'])
            print(f"  plane z={fp['plane_z_first_mm']}: {fp['verdict']} [{fp['level']}] ({top})")
        else:
            print(f"  plane z={fp['plane_z_first_mm']}: {fp['verdict']}")
    if len(report['feature_planes']) > 4:
        print(f"  … {len(report['feature_planes']) - 4} more plane(s) in the sidecar")
    print(f"  audit: {audit['status']}")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument('input', help='existing G-code file, opened read-only')
    parser.add_argument('--out', required=True, help='sidecar JSON destination (must not exist unless --force)')
    parser.add_argument('--force', action='store_true', help='overwrite an existing sidecar (never the source)')
    parser.add_argument('--join-eps', type=float, default=JOIN_EPS_DEFAULT,
                        help='loop join tolerance in mm (default %(default)s)')
    parser.add_argument('--plane-gap', type=float, default=PLANE_GAP_DEFAULT,
                        help='max gap between consecutive extruding Z levels of one plane bucket, mm (default %(default)s)')
    parser.add_argument('--max-bytes', type=int, default=512 * 1024 * 1024)
    parser.add_argument('--with-moves', action='store_true', help='embed compact move records in the sidecar')
    parser.add_argument('--max-moves', type=int, default=100000)
    parser.add_argument('--quiet', action='store_true')
    # pass-through options for the verified shadow parser
    parser.add_argument('--assume-klipper-defaults', action='store_true')
    parser.add_argument('--dialect', choices=('klipper', 'generic'), default='klipper')
    parser.add_argument('--enable-arcs', action='store_true')
    parser.add_argument('--firmware-retract', action='store_true')
    parser.add_argument('--klipper-passive', action='store_true')
    parser.add_argument('--verified-r2-passive', action='store_true')
    parser.add_argument('--assume-passive', action='append', default=[], metavar='COMMAND')
    parser.add_argument('--version', action='version', version=f'gcode_re {TOOL_VERSION} ({REPORT_SCHEMA})')
    args = parser.parse_args(argv)
    try:
        report = analyse(
            args.input, join_eps=args.join_eps, plane_gap=args.plane_gap,
            max_bytes=args.max_bytes,
            assumed_passive=args.assume_passive,
            assume_klipper_defaults=args.assume_klipper_defaults, dialect=args.dialect,
            enable_arcs=args.enable_arcs, firmware_retract=args.firmware_retract,
            klipper_passive=args.klipper_passive, verified_r2_passive=args.verified_r2_passive,
            with_moves=args.with_moves, max_moves=args.max_moves)
        payload = json.dumps(report, ensure_ascii=True, separators=(',', ':'),
                             indent=None, sort_keys=False).encode('utf-8')
        _write_atomic(args.out, payload, force=args.force)
    except FileExistsError as exc:
        print(f'gcode_re: {exc}', file=sys.stderr)
        return 2
    except (OSError, ValueError) as exc:
        print(f'gcode_re: {exc}', file=sys.stderr)
        return 1
    if not args.quiet:
        _print_summary(report, args.out)
    return 0


if __name__ == '__main__':
    sys.exit(main())
