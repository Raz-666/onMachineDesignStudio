#!/usr/bin/env python3
"""R2 G-code post-processor + folder watcher (R56 / .40) - the LAYER READER.

WHY: Klipper macros cannot read files - comments like ';LAYER_CHANGE' never
reach a macro. This script runs ON THE PI and rewrites gcode files the moment
they land in the gcodes folder (Mainsail upload, USB copy, scp - every path):

  1. LAYER_MARK is injected after every layer-change comment
     (;LAYER_CHANGE / ;LAYER:n / ; CHANGE_LAYER ...) - or, for files without
     any layer comments, after every detected layer rise in the Z moves
     (0.05-0.35 mm jump = layer boundary, slow rise >= 0.18 mm = vase mode).
     Result: fan, speed and L2 temperatures switch at the EXACT layer boundary,
     not on the watcher's 8-second Z estimate.
  2. _FILE_INFO is injected before the first file command - the slicer's real
     parameters (layer height, total layers, line widths, flow ratio, PA,
     by-object) end up in Pre-Print > File (G-code) for EVERY file, even
     foreign downloads without our slicer script.

Idempotent: a processed file gets the tag '; R2-POSTPROC v4' and is skipped;
files tagged v1 (up to .41) are UPGRADED in place (marks stay, APPLY_TYPE +
extended _FILE_INFO added) - see OLD_TAG below.
Files that already carry LAYER_MARK (sliced with the R2 script) only get the
_FILE_INFO block - their markers stay untouched.

Usage:
  r2_postproc.py FILE [FILE...]        process file(s) once
  r2_postproc.py --watch DIR           daemon: process everything in DIR (recursive)
  r2_postproc.py --label "A|B" W H     generate a label plate (see --label without args)
  r2_postproc.py FILE --dry-run        show what would happen, change nothing

R76 (.60): the host check grew up - the .59 field log showed a SATURATED host
(load 4.2 on the Pi Zero 2's four cores) with NO throttle flags, so the check
now also reports swap, iowait and the TOP CPU/RAM processes and weighs an
honest verdict (throttle > swap > overload > OK); /proc is read directly so
the answer stays fast on a busy box.
R75 (.59): host-load hardening after the .58 field log ('Timer too close' MCU
shutdowns around meshing on a Pi Zero host) - preview pushes are ONE in-memory
_PREVIEW_SET command (no more SAVE_VARIABLE disk-write storms at print start),
the file's EXCLUDE_OBJECT_DEFINE lines are replayed at selection so the mesh
runs adaptive instead of full-bed, plot files carry their own object polygon,
the watcher never re-fires old nonces after a restart, runs niced, and answers
HOST_CHECK with the Pi's throttle/temperature/load/disk health report.
"""
import os
import re
import math

from math import cos, pi
import sys
import time
import zlib
import struct
import json

TAG = '; R2-POSTPROC v4'
VAR_PATH = None    # set by watch(): save_variables file (plotter + range requests)
# v1 (up to .41) injected LAYER_MARK + a SHORT _FILE_INFO - but no APPLY_TYPE
# and no speed/accel/nozzle parameters. Files carrying an OLD tag are UPGRADED
# in place: old _FILE_INFO line replaced by the extended one, APPLY_TYPE
# markers rebuilt, existing LAYER_MARK lines STAY (they are valid - never
# double-injected). A file with the CURRENT tag is skipped as before.
# v4 (.44): _FILE_INFO now also carries TYPES= (which features the file really
# contains) and FS_<FEATURE>/FA_<FEATURE> - the REAL per-feature speed (mm/s,
# most frequent F value inside that feature's segments) and acceleration
# (mm/s2, the M204 in effect there) measured from the g-code itself. The
# slicer's config header often only has percentages (bridge_acceleration=50%)
# or nothing at all (support) - the measured values are the honest originals.
OLD_TAGS = ('; R2-POSTPROC v1', '; R2-POSTPROC v2', '; R2-POSTPROC v3')

# ---- layer-change comments (slicer dialects) -------------------------------------
# NOTE: ;BEFORE_LAYER_CHANGE is deliberately NOT matched - Orca/PrusaSlicer emit
# it together with ;LAYER_CHANGE for the SAME boundary -> matching both would
# inject TWO marks per layer and double-count every layer.
LAYER_COMMENT = re.compile(
    r'^\s*;\s*(?:LAYER_CHANGE|LAYER\s*:?\s*\d+|CHANGE_LAYER)\s*$',
    re.IGNORECASE)

# ---- gcode line parsing -----------------------------------------------------------
MOVE_RE = re.compile(r'^(G0|G1)\b\s*(.*)$')
PARAM_RE = re.compile(r'([A-Za-z])\s*([-+]?\d*\.?\d+)')

# ---- feature type comments (;TYPE: ...) -> APPLY_TYPE -----------------------------
# R58: the per-feature overrides (outer wall / support / ironing ...) work on
# EVERY file now - the marker does not need the R2 slicer script anymore.
TYPE_RE = re.compile(r'^\s*;\s*TYPE:\s*(.+?)\s*$', re.IGNORECASE)
TYPE_MAP = {
    'outer wall': 'WALL-OUTER',
    'inner wall': 'WALL-INNER',
    'sparse infill': 'INFILL-SPARSE',
    'internal solid infill': 'INFILL-SOLID',
    'gap infill': 'GAPS',
    'top surface': 'SURFACE-TOP',
    'bottom surface': 'SURFACE-BOTTOM',
    'support': 'SUPPORT',
    'support interface': 'SUPPORT',
    'support/base': 'SUPPORT',
    'ironing': 'IRONING',
    'bridge': 'BRIDGE',
    'skirt': 'SKIRT',
    'brim': 'BRIM',
    'custom': 'CUSTOM',
}

# ---- slicer config header keys (OrcaSlicer / PrusaSlicer '; key = value') ---------
CFG_KEYS = {
    'line_width': 'LINE_WIDTH',
    'initial_layer_line_width': 'LINE_WIDTH_FIRST',
    'outer_wall_line_width': 'LINE_WIDTH_WALL',
    'filament_flow_ratio': 'FLOW_RATIO',
    'flow_ratio': 'FLOW_RATIO',
    'layer_height': 'LAYER_HEIGHT',
    'pressure_advance': 'PA',
    'filament_type': 'MATERIAL',
    'outer_wall_speed': 'SPEED_OUTER',
    'inner_wall_speed': 'SPEED_INNER',
    'sparse_infill_speed': 'SPEED_SPARSE',
    'top_surface_speed': 'SPEED_TOP',
    'initial_layer_speed': 'SPEED_FIRST',
    'travel_speed': 'SPEED_TRAVEL',
    'support_speed': 'SPEED_SUPPORT',
    'ironing_speed': 'SPEED_IRONING',
    'internal_solid_infill_speed': 'SPEED_SOLID',
    'gap_infill_speed': 'SPEED_GAPS',
    'bridge_speed': 'SPEED_BRIDGE',
    'skirt_speed': 'SPEED_SKIRT',
    'support_interface_speed': 'SPEED_SUPPINT',
    'default_acceleration': 'ACCEL_DEFAULT',
    'outer_wall_acceleration': 'ACCEL_OUTER',
    'inner_wall_acceleration': 'ACCEL_INNER',
    'sparse_infill_acceleration': 'ACCEL_SPARSE',
    'top_surface_acceleration': 'ACCEL_TOP',
    'nozzle_diameter': 'NOZZLE',
    'wall_loops': 'WALL_LOOPS',
    'ironing_flow': 'IRONING_FLOW',
    'ironing_spacing': 'IRONING_SPACING',
}
CFG_RE = re.compile(r'^\s*;\s*([A-Za-z0-9_]+)\s*=\s*(.+?)\s*$')


def parse_params(code):
    """G0/G1 parameter dict: {'Z': 2.4, 'E': 1.2, ...}
    R68: comments are stripped first and a malformed token (letter + '-'
    without digits, e.g. hyphenated names in trailing comments like
    '; Felge-V-035' or a bare 'E-') is SKIPPED - foreign files must never
    crash the watcher with: could not convert string to float: '-'"""
    out = {}
    for k, v in PARAM_RE.findall(code.split(';', 1)[0]):
        try:
            out[k.upper()] = float(v)
        except ValueError:
            continue
    return out


def first_value(raw):
    """Orca writes multi-extruder values as '0.055,0.1' or 'PLA;PLA' - first."""
    return re.split(r'[,;]', raw)[0].strip()



# ======================================================================================
#  R61 LAYER RANGE - excerpt generation: print ONLY layers START..END of a marked file.
#  Layer START becomes the FIRST layer and starts mid-air at its real Z. The excerpt
#  carries the v4 tag (the watcher must not re-mark it) + a copied _FILE_INFO with a
#  corrected TOTAL_LAYERS. Absolute-E files are REBASED (E -= E_at_cut) so extrusion
#  continuity survives the cut; relative-E files pass through untouched.
# ======================================================================================
RMOVE_RE = re.compile(r'^(G0|G1|G2|G3)\b')
EWORD_RE = re.compile(r' E(-?\d*\.?\d+)')
FWORD_RE = re.compile(r' F(\d*\.?\d+)')
ZWORD_RE = re.compile(r' Z(-?\d*\.?\d+)')


def _stripped(line):
    """command part of a gcode line - comments (';...') removed (R73)."""
    return line.split(';', 1)[0].strip()


def _hull(points):
    """convex hull (monotone chain) of [(x, y), ...] - CCW, no closing point."""
    pts = sorted(set((round(p[0], 3), round(p[1], 3)) for p in points))
    if len(pts) < 3:
        return pts
    def cross(o, a, b):
        return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])
    lower = []
    for p in pts:
        while len(lower) >= 2 and cross(lower[-2], lower[-1], p) <= 0:
            lower.pop()
        lower.append(p)
    upper = []
    for p in reversed(pts):
        while len(upper) >= 2 and cross(upper[-2], upper[-1], p) <= 0:
            upper.pop()
        upper.append(p)
    return lower[:-1] + upper[:-1]


def _offset_hull(hull, d):
    """convex polygon offset outward by d mm (edge offset + corner cut)."""
    if len(hull) < 3 or d == 0:
        return hull
    n = len(hull)
    out = []
    for i in range(n):
        a, b, c = hull[i], hull[(i + 1) % n], hull[(i + 2) % n]
        # normal of edge a->b (hull is CCW -> outward normal = right side)
        dx, dy = b[0] - a[0], b[1] - a[1]
        ln = math.hypot(dx, dy)
        if ln < 1e-9:
            continue
        nx, ny = dy / ln, -dx / ln
        # offset both adjacent edges, intersect them at the new corner
        p1 = (a[0] + nx * d, a[1] + ny * d)
        p2 = (b[0] + nx * d, b[1] + ny * d)
        dx2, dy2 = c[0] - b[0], c[1] - b[1]
        ln2 = math.hypot(dx2, dy2)
        if ln2 < 1e-9:
            out.append(p2)
            continue
        nx2, ny2 = dy2 / ln2, -dx2 / ln2
        p3 = (b[0] + nx2 * d, b[1] + ny2 * d)
        p4 = (c[0] + nx2 * d, c[1] + ny2 * d)
        # intersect line(p1,p2) x line(p3,p4)
        ex, ey = p2[0] - p1[0], p2[1] - p1[1]
        fx, fy = p4[0] - p3[0], p4[1] - p3[1]
        den = ex * fy - ey * fx
        if abs(den) < 1e-12:
            out.append(p2)
            continue
        t = ((p3[0] - p1[0]) * fy - (p3[1] - p1[1]) * fx) / den
        # cap the miter (sharp corners must not spike)
        t = max(-1.5, min(2.5, t))
        out.append((p1[0] + ex * t, p1[1] + ey * t))
    return out


def _hull_hatch(hull, spacing, angle_deg, min_len=0.4):
    """scanline hatch over a convex hull -> [(p, q), ...] boustrophedon."""
    if len(hull) < 3:
        return []
    ang = math.radians(angle_deg)
    ca, sa = math.cos(ang), math.sin(ang)

    def rot(p):
        return (p[0] * ca + p[1] * sa, -p[0] * sa + p[1] * ca)

    rp = [rot(p) for p in hull]
    ys = [q[1] for q in rp]
    y0, y1 = min(ys), max(ys)
    segs = []
    idx = 0
    k = 0
    while y0 + k * spacing <= y1:
        y = y0 + k * spacing + spacing / 2.0
        cross = []
        for i in range(len(rp)):
            a, b = rp[i], rp[(i + 1) % len(rp)]
            if (a[1] <= y < b[1]) or (b[1] <= y < a[1]):
                t = (y - a[1]) / (b[1] - a[1])
                cross.append(a[0] + t * (b[0] - a[0]))
        cross.sort()
        for i in range(0, len(cross) - 1, 2):
            xa, xb = cross[i], cross[i + 1]
            if xb - xa < min_len:
                continue
            def unrot(x, yy):
                return (x * ca - yy * sa, x * sa + yy * ca)
            p = unrot(xa + 0.15, y)
            q = unrot(xb - 0.15, y)
            segs.append((p, q) if idx % 2 == 0 else (q, p))
            idx += 1
        k += 1
    return segs


def _layer_ink_hull(lines, a, b, e_rel):
    """convex hull of the EXTRUSION geometry of lines[a:b] (R73 range raft).

    Tracks X/Y through the moves and keeps the endpoints of every segment that
    extrudes (E grows). G92 E resets the absolute-E tracker. Returns None when
    the block never extrudes.
    """
    x = y = None
    e_abs = 0.0
    pts = []
    for l in lines[a:b]:
        c = _stripped(l)
        if not c:
            continue
        if c.startswith('G92'):
            m = EWORD_RE.search(c)
            if m and not e_rel:
                e_abs = float(m.group(1))
            continue
        if not RMOVE_RE.match(c):
            continue
        mx = re.search(r'X(-?\d+(?:\.\d+)?)', c)
        my = re.search(r'Y(-?\d+(?:\.\d+)?)', c)
        me = EWORD_RE.search(c)
        grow = False
        if me:
            ev = float(me.group(1))
            if e_rel:
                grow = ev > 1e-6
            else:
                grow = (ev - e_abs) > 1e-6
                e_abs = ev
        nx = float(mx.group(1)) if mx else x
        ny = float(my.group(1)) if my else y
        if grow and x is not None and nx is not None and ny is not None:
            pts.append((x, y))
            pts.append((nx, ny))
        x, y = nx, ny
    if len(pts) >= 3:
        return _hull(pts)
    return ('bbox', pts) if pts else None


def _layer_ink_mask(lines, a, b, e_rel, res, dil, enclose=False):
    """R74 OUTLINE mode: rasterize the EXTRUSION geometry of lines[a:b] into a
    boolean grid - every segment stamped as a capsule of radius 'dil' (= half
    the line width). This is the TRUE outline of the layer: concavities and
    holes stay open (a convex hull bridges them - that is 'FOOTPRINT' mode).
    Returns (mask, x0, y0, nx, ny); cell (i, j) spans
    [x0+i*res, x0+(i+1)*res) x [y0+j*res, y0+(j+1)*res). None when no ink.

    R79 (field log .62: 'outline floor: after the contours NOTHING is
    extruded'): the stamped ink alone is just the wall/infill LINES - a layer
    with a closed wall loop has almost no ink area, so the hatch fill had
    nothing to fill and the floor looked like 'no extrusion at all'. With
    enclose=True the fill covers the AREA INSIDE the true outline: everything
    the border flood-fill cannot reach from outside becomes part of the
    footprint (closed interiors are filled; concave notches and everything
    border-connected stays open - that is what makes OUTLINE differ from
    FOOTPRINT). Enclosed holes (donut) are filled too - for a raft/base that
    is wanted: a closed surface under the section.
    """
    x = y = None
    e_abs = 0.0
    segs = []
    for l in lines[a:b]:
        c = _stripped(l)
        if not c:
            continue
        if c.startswith('G92'):
            m = EWORD_RE.search(c)
            if m and not e_rel:
                e_abs = float(m.group(1))
            continue
        if not RMOVE_RE.match(c):
            continue
        mx = re.search(r'X(-?\d+(?:\.\d+)?)', c)
        my = re.search(r'Y(-?\d+(?:\.\d+)?)', c)
        me = EWORD_RE.search(c)
        grow = False
        if me:
            ev = float(me.group(1))
            if e_rel:
                grow = ev > 1e-6
            else:
                grow = (ev - e_abs) > 1e-6
                e_abs = ev
        nx = float(mx.group(1)) if mx else x
        ny = float(my.group(1)) if my else y
        if grow and x is not None and nx is not None and ny is not None:
            if math.hypot(nx - x, ny - y) > 1e-6:
                segs.append((x, y, nx, ny))
        x, y = nx, ny
    if not segs:
        return None
    xs = [p for s in segs for p in (s[0], s[2])]
    ys = [p for s in segs for p in (s[1], s[3])]
    x0 = min(xs) - dil - res
    y0 = min(ys) - dil - res
    x1 = max(xs) + dil + res
    y1 = max(ys) + dil + res
    nx = int(math.ceil((x1 - x0) / res))
    ny = int(math.ceil((y1 - y0) / res))
    if nx * ny > 6_000_000:            # safety: >6e6 cells never happens on an Ender-3
        res = math.ceil(math.sqrt((x1 - x0) * (y1 - y0) / 6_000_000) * 100) / 100.0
        nx = int(math.ceil((x1 - x0) / res))
        ny = int(math.ceil((y1 - y0) / res))
    mask = [bytearray(nx) for _ in range(ny)]
    rad = dil
    stamp = int(math.ceil(rad / res))
    for (sx, sy, ex, ey) in segs:
        d = math.hypot(ex - sx, ey - sy)
        n = max(1, int(d / (res * 0.5)) + 1)
        for k in range(n + 1):
            t = k / float(n)
            px = sx + (ex - sx) * t
            py = sy + (ey - sy) * t
            ci = int((px - x0) / res)
            cj = int((py - y0) / res)
            for j in range(max(0, cj - stamp), min(ny, cj + stamp + 1)):
                dy = (y0 + (j + 0.5) * res) - py
                row = mask[j]
                for i in range(max(0, ci - stamp), min(nx, ci + stamp + 1)):
                    dx = (x0 + (i + 0.5) * res) - px
                    if dx * dx + dy * dy <= rad * rad:
                        row[i] = 1
    if enclose:
        # ---- R79: flood-fill the OUTSIDE from the border; every empty cell the
        # fill cannot reach is an ENCLOSED interior -> part of the footprint.
        # (iterative scanline fill - no recursion, works on big grids)
        outside = [bytearray(nx) for _ in range(ny)]
        stack = []
        for i in range(nx):
            for j in (0, ny - 1):
                if not mask[j][i] and not outside[j][i]:
                    outside[j][i] = 1
                    stack.append((i, j))
        for j in range(ny):
            for i in (0, nx - 1):
                if not mask[j][i] and not outside[j][i]:
                    outside[j][i] = 1
                    stack.append((i, j))
        while stack:
            i, j = stack.pop()
            for ai, aj in ((i - 1, j), (i + 1, j), (i, j - 1), (i, j + 1)):
                if 0 <= ai < nx and 0 <= aj < ny and not mask[aj][ai] and not outside[aj][ai]:
                    outside[aj][ai] = 1
                    stack.append((ai, aj))
        for j in range(ny):
            row, orow = mask[j], outside[j]
            for i in range(nx):
                if not row[i] and not orow[i]:
                    row[i] = 1
    return mask, x0, y0, nx, ny


def _mask_hatch(mask, x0, y0, nx, ny, res, spacing, angle_deg, min_len=0.4):
    """R74: rotated scanline hatch over a boolean mask -> [(p, q), ...]
    boustrophedon (same contract as _hull_hatch, but for the true outline:
    scanlines are clipped against the MASK, so concavities/holes stay open)."""
    ang = math.radians(angle_deg)
    ca, sa = math.cos(ang), math.sin(ang)
    corners = [(x0, y0), (x0 + nx * res, y0), (x0 + nx * res, y0 + ny * res), (x0, y0 + ny * res)]
    rp = [(px * ca + py * sa, -px * sa + py * ca) for px, py in corners]
    us = [q[0] for q in rp]
    vs = [q[1] for q in rp]
    u0, u1, v0, v1 = min(us), max(us), min(vs), max(vs)

    def inside(u, v):
        # rotate back into grid space, sample the cell under the point
        px = u * ca - v * sa
        py = u * sa + v * ca
        i = int((px - x0) / res)
        j = int((py - y0) / res)
        return 0 <= i < nx and 0 <= j < ny and mask[j][i]

    segs = []
    idx = 0
    k = 0
    while v0 + k * spacing <= v1:
        v = v0 + k * spacing + spacing / 2.0
        u = u0
        run = None
        while u <= u1 + res:
            ok = u <= u1 and inside(u, v)
            if ok and run is None:
                run = u
            elif not ok and run is not None:
                if u - run >= min_len:
                    def unrot(uu, vv):
                        return (uu * ca - vv * sa, uu * sa + vv * ca)
                    p = unrot(run + 0.15, v)
                    q = unrot(u - 0.15, v)
                    segs.append((p, q) if idx % 2 == 0 else (q, p))
                    idx += 1
                run = None
            u += res
        k += 1
    return segs


def _mask_contours(mask, x0, y0, nx, ny, res, tol=0.25):
    """R74: trace the boundary LOOPS of a boolean mask (edge following).
    Returns a list of polygons (outer contours and hole contours alike) in
    mm, decimated to 'tol'. Emitter note: hole contours run clockwise - as
    extrusion loops they are perfectly valid closed paths."""
    edges = {}
    # directed boundary edges: walking CCW, the INSIDE stays on the LEFT
    # (holes automatically come out clockwise - valid extrusion loops too)
    for j in range(ny):
        row = mask[j]
        rowup = mask[j + 1] if j + 1 < ny else None
        for i in range(nx):
            if not row[i]:
                continue
            # top side (neighbor j+1 outside) -> walk -x
            if rowup is None or not rowup[i]:
                edges.setdefault((i + 1, j + 1), []).append((i, j + 1))
            # bottom side (neighbor j-1 outside) -> walk +x
            if j == 0 or not mask[j - 1][i]:
                edges.setdefault((i, j), []).append((i + 1, j))
            # right side (neighbor i+1 outside) -> walk +y
            if i + 1 >= nx or not row[i + 1]:
                edges.setdefault((i + 1, j), []).append((i + 1, j + 1))
            # left side (neighbor i-1 outside) -> walk -y
            if i == 0 or not row[i - 1]:
                edges.setdefault((i, j + 1), []).append((i, j))
    polys = []
    while edges:
        start, outs = next(iter(edges.items()))
        cur = outs.pop()
        if not outs:
            del edges[start]
        pts = [start]
        while cur != start:
            pts.append(cur)
            nxt = edges.get(cur)
            if not nxt:
                break                    # open chain (should not happen) - keep it
            nxp = nxt.pop()
            if not nxt:
                del edges[cur]
            cur = nxp
        if len(pts) >= 4:
            mm = [(x0 + i * res, y0 + j * res) for (i, j) in pts]
            # drop degenerate slivers (a contour smaller than ~2 line widths
            # in BOTH dims is a dilation staircase artifact, not a shape)
            xs = [p[0] for p in mm]
            ys = [p[1] for p in mm]
            if (max(xs) - min(xs)) < res * 4 and (max(ys) - min(ys)) < res * 4:
                continue
            polys.append(_decimate(mm, tol))
    return polys


class _GenE:
    """emits generated geometry (raft/brim/cap) in the file's E mode.

    M83: relative E per segment. M82: G92 E0 once, then ACCUMULATING absolute
    E (the R71 brim bug was exactly this: absolute E must accumulate)."""

    def __init__(self, out, e_rel):
        self.out = out
        self.e_rel = e_rel
        self.acc = 0.0
        if not e_rel:
            out.append('G92 E0   ; R2-RANGE: generated geometry E starts at 0')

    def move(self, x, y, feed):
        self.out.append('G0 X%.3f Y%.3f F%d' % (x, y, feed))

    def line(self, x0, y0, x1, y1, e_per_mm, feed):
        d = math.hypot(x1 - x0, y1 - y0)
        if d < 0.05:
            return
        e = d * e_per_mm
        if self.e_rel:
            self.out.append('G1 X%.3f Y%.3f E%.5f F%d' % (x1, y1, e, feed))
        else:
            self.acc += e
            self.out.append('G1 X%.3f Y%.3f E%.5f F%d' % (x1, y1, self.acc, feed))

    def loop(self, pts, e_per_mm, feed):
        self.move(pts[0][0], pts[0][1], 4800)
        px, py = pts[0]
        for (x, y) in pts[1:]:
            self.line(px, py, x, y, e_per_mm, feed)
            px, py = x, y
        self.line(px, py, pts[0][0], pts[0][1], e_per_mm, feed)


def make_range(src, start, end, floor=0, top=0, brim=0, first_h=0.2, version=1,
               floor_shape='hull', floor_fill='grid',
               top_shape='hull', top_fill='solid'):
    """R62/R73/R74: create <stem>_L<s>-<e>.gcode next to src.

    The excerpt starts ON THE BED: layer START prints as the FIRST layer at
    Z=first_h (0.2mm by default), all following layers keep their original
    spacing (global Z shift).

    R73 FIELD FIX (.56 log 'no filament comes out of the nozzle'):
    Orca writes 'M83 ; use relative distances for extrusion' - WITH a trailing
    comment. The old detection compared the exact string, missed it, and
    labeled relative-E files as M82: every tiny per-move delta became an
    ABSOLUTE target -> the extruder wiggled between ~0.0x values, almost
    nothing came out and no flow percentage could fix it. The modal scan now
    strips comments before comparing.

    R73 base/cap (user request): the range section usually has NO floor of
    its own - FLOOR now prints a solid RAFT under the section with 'floor'
    layers, BRIM wraps N loops around the outline (zero gap, key-ring style)
    and TOP closes the print with 'top' SOLID layers over the last layer.

    R74 (user requests):
    - floor_shape/top_shape: 'hull' = FOOTPRINT (convex hull of the layer -
      bridges concavities) or 'outline' = the TRUE outline of the layer
      (concavities and holes stay open, follows the model wall exactly)
    - floor_fill/top_fill: 'grid' (hatch lattice, the classic look) or
      'solid' (dense hatch, lines overlap into a solid surface)
    - the file now ends with PRINT_END: a proper end sequence runs (park,
      stats, fanfare) - the nozzle no longer stays parked ON the print
      (.57 field log 'nozzle just stays on the finished print')
    - the copied _FILE_INFO sits at the TOP (it used to run at the very
      END of the print - Live > File showed the PREVIOUS file's values
      all along)
    The header carries a PRINT_START call with the source temperatures, so the
    file runs through the NORMAL start flow.

    R81 STREAMING: the old builder read the WHOLE file into ONE Python list -
    a 32MB / 1M-line source (field log .63: 4h24m vase) became ~150MB of
    string objects on a Pi Zero 2 W with ~150MB free -> swap storm ->
    'Timer too close' EXACTLY while a range was generated (02:18:56). Two
    streaming passes now keep memory at O(one layer): pass A collects marks,
    modal state, the anchor layers and the body trackers; pass B pipes the
    body through the Z/E shift straight into the output file. Output is
    byte-identical to the previous builder (R81 golden test).
    """
    start = max(2, int(start))
    end_raw = int(end)

    # ---- pass A: stream once - marks, modal state, anchors, trackers ------
    # Replaces 'lines = f.read().split(chr(10))' (the R81 RAM killer).
    marks = []
    n_stream = 0
    trailing_empty = False
    a_idx = None
    lay1_done = False
    layn_on = False
    body_done = False
    # modal state at the cut: E mode/value, F, Z, fan, heater targets
    # (R73: comment-tolerant - 'M83 ; use relative...' counts as M83)
    e_rel = False
    e_abs = 0.0
    f_mod = None
    z_mod = None
    fan = None
    hot = 0.0
    bed = 0.0
    material = 'PLA'
    lh = 0.2
    lw = 0.6
    # body trackers (original, unshifted values)
    z0 = None
    z_end_body = None
    fx = fy = None
    lay1 = []            # first range layer [a, a2) - raft/brim anchor
    layn = []            # layer 'end_raw' - cap anchor (complete only if end_raw <= total)
    cur_layer = []       # running buffer - holds the file's LAST layer at EOF
    excludes = []        # EXCLUDE_OBJECT_DEFINE lines from the head
    file_info_line = None
    with open(src, 'r', errors='replace') as f:
        for raw in f:
            trailing_empty = raw.endswith('\n')
            line = raw[:-1] if trailing_empty else raw
            i = n_stream
            n_stream += 1
            ls = line.strip()
            is_mark = (ls == 'LAYER_MARK')
            mc = 0
            if is_mark:
                marks.append(i)
                mc = len(marks)
                if mc == start:
                    a_idx = i          # the LAYER_MARK of layer 'start'
            # running last-layer buffer (head lines before the first mark drop out)
            if is_mark:
                cur_layer = [line]
            elif cur_layer:
                cur_layer.append(line)
            # lay1: [a, a2) - ends before the LAYER_MARK of layer start+1
            if is_mark and mc == start + 1:
                lay1_done = True
            if a_idx is not None and i >= a_idx and not lay1_done:
                lay1.append(line)
            # layn: the complete layer 'end_raw' (cap anchor)
            if is_mark and mc == end_raw:
                layn_on = True
            if is_mark and mc == end_raw + 1:
                layn_on = False
                body_done = True       # this line is b (exclusive) - body ends here
            if layn_on:
                layn.append(line)
            # modal state of the head (lines[:a], exclusive of the cut mark)
            if a_idx is None or i < a_idx:
                c = _stripped(line)
                if c:
                    if c == 'M83':
                        e_rel = True
                    elif c == 'M82':
                        e_rel = False
                    elif c.startswith('G92'):
                        m = EWORD_RE.search(c)
                        if m:
                            e_abs = float(m.group(1))
                    elif c.startswith('M106'):
                        m = re.search(r'S(\d+)', c)
                        fan = int(m.group(1)) if m else 255
                    elif c == 'M107':
                        fan = 0
                    elif c.startswith('M104') or c.startswith('M109'):
                        m = re.search(r'S(\d+(?:\.\d+)?)', c)
                        if m and float(m.group(1)) >= 40:
                            hot = float(m.group(1))
                    elif c.startswith('M140') or c.startswith('M190'):
                        m = re.search(r'S(\d+(?:\.\d+)?)', c)
                        if m and float(m.group(1)) >= 40:
                            bed = float(m.group(1))
                    elif c.startswith('_FILE_INFO'):
                        m = re.search(r'MATERIAL=(\w+)', c)
                        if m:
                            material = m.group(1)
                        m = re.search(r'LAYER_HEIGHT=([\d.]+)', c)
                        if m:
                            lh = max(0.05, float(m.group(1)))
                        m = re.search(r'LINE_WIDTH=([\d.]+)', c)
                        if m:
                            lw = max(0.3, min(1.2, float(m.group(1))))
                    elif RMOVE_RE.match(c):
                        m = FWORD_RE.search(c)
                        if m:
                            f_mod = float(m.group(1))
                        m = ZWORD_RE.search(c)
                        if m:
                            z_mod = float(m.group(1))
                        m = EWORD_RE.search(c)
                        if m and not e_rel:
                            e_abs = float(m.group(1))
                if ls.startswith('EXCLUDE_OBJECT_DEFINE'):
                    excludes.append(ls)
            # first _FILE_INFO line anywhere (goes to the top of the excerpt)
            if file_info_line is None and ls.startswith('_FILE_INFO'):
                file_info_line = line
            # body trackers: first Z (z0), last Z (z_end), first print position
            if a_idx is not None and i >= a_idx and not body_done:
                c = _stripped(line)
                if RMOVE_RE.match(c):
                    if z0 is None:
                        m = ZWORD_RE.search(c)
                        if m:
                            z0 = float(m.group(1))
                    m = ZWORD_RE.search(c)
                    if m:
                        z_end_body = float(m.group(1))
                    if fx is None:
                        mx = re.search(r'X(-?\d+(?:\.\d+)?)', c)
                        my = re.search(r'Y(-?\d+(?:\.\d+)?)', c)
                        if mx and my:
                            fx, fy = float(mx.group(1)), float(my.group(1))
    last_layer = cur_layer

    total = len(marks)
    if total < 2:
        raise ValueError('no LAYER_MARK layers found - the file is not processed yet')
    end = min(end_raw, total)
    if end <= start:
        raise ValueError(f'range {start}..{end} invalid (file has {total} layers)')
    floor = max(0, min(int(floor), 10))
    top = max(0, min(int(top), 10))
    brim = max(0, min(int(brim), 10))
    floor_shape = 'outline' if str(floor_shape).lower().startswith('out') else 'hull'
    top_shape = 'outline' if str(top_shape).lower().startswith('out') else 'hull'
    floor_fill = 'solid' if str(floor_fill).lower().startswith('sol') else 'grid'
    top_fill = 'solid' if str(top_fill).lower().startswith('sol') else 'grid'
    a = a_idx                 # first line of layer <start> (its LAYER_MARK)
    b = marks[end] if end < total else n_stream   # exclusive end
    # the cap anchor: layer 'end' complete (falls back to the file's last
    # layer when the requested end was clamped down to total)
    cap_layer = layn if (end < total and layn) else last_layer

    # ---- the first Z inside the body = the source layer's print Z ----
    if z0 is None:
        z0 = z_mod
    if z0 is None:
        raise ValueError('no Z move found before the range - cannot anchor on the bed')
    base_z = round(first_h + floor * lh, 3)      # Z where the first real range layer prints
    dz = z0 - base_z                              # global shift: everything moves DOWN

    # ---- R73: hull of the first range layer (raft/brim anchor, zero gap) ----
    wid = lw           # R74 fix: was only defined in the floor/brim branch - a
                       # top-only range (floor=0, brim=0) crashed with NameError
    hull1 = _layer_ink_hull(lay1, 0, len(lay1), e_rel)
    hull_n = _layer_ink_hull(cap_layer, 0, len(cap_layer), e_rel) if top else None

    # ---- R74: true-outline masks (only when an OUTLINE floor/top is wanted) ----
    res = max(0.25, round(wid / 2.0, 3))
    # R79: enclose=True - the outline mask covers the AREA INSIDE the outline
    # (field log .62: the ink-only mask left nothing to fill -> 'no extrusion')
    mask1 = _layer_ink_mask(lay1, 0, len(lay1), e_rel, res, wid / 2.0, enclose=True) \
        if (floor > 0 and floor_shape == 'outline') else None
    mask_n = None
    if top > 0 and top_shape == 'outline':
        mask_n = _layer_ink_mask(cap_layer, 0, len(cap_layer), e_rel,
                                 res, wid / 2.0, enclose=True)

    def _shape_ok(shape, hull, mask):
        """an OUTLINE needs a mask, a FOOTPRINT needs a hull - fall back when
        the preferred source is missing (e.g. no extrusion moves found)."""
        if shape == 'outline' and mask is not None:
            return 'outline'
        return 'hull' if hull is not None else None

    def _as_poly(h, margin=3.0):
        # 'bbox' fallback marker -> rectangle polygon around the ink points
        if h is None or len(h) == 0:
            return None
        if isinstance(h, tuple) and len(h) == 2 and h[0] == 'bbox':
            pts = h[1]
            xs = [p[0] for p in pts]
            ys = [p[1] for p in pts]
            x0, x1 = min(xs) - margin, max(xs) + margin
            y0, y1 = min(ys) - margin, max(ys) + margin
            return [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]
        return h

    # ---- generated geometry: raft (FLOOR), brim (BRIM), solid cap (TOP) -------
    gen = []            # gcode lines, inserted BEFORE the body (raft/brim)
    gen_top = []        # gcode lines, inserted AFTER the body (cap)
    if floor > 0 or brim > 0:
        anchor = _as_poly(hull1)
        if anchor is None and mask1 is None:
            raise ValueError('the range layers carry no extrusion moves - '
                             'nothing to anchor a raft/brim on')
        g = _GenE(gen, e_rel)
        # RAFT: 'floor' solid layers under the section footprint - the hull is
        # offset by half a line width so the raft edge sits flush with the
        # model walls (ZERO gap - it welds directly to the section).
        if floor > 0:
            f_shape = _shape_ok(floor_shape, anchor, mask1)
            gen.append('; R2-RANGE raft: %d layer(s), %s, %s fill, zero gap to the section'
                       % (floor, {'hull': 'footprint', 'outline': 'true outline'}[f_shape],
                          floor_fill))
            # R79: feature markers for the generated geometry - the raft counts
            # as INFILL-SOLID, so Live > Features (speed/accel/flow) works on
            # it exactly like on any sliced section
            gen.append('APPLY_TYPE TYPE=INFILL-SOLID')
            for i in range(floor):
                z = round(first_h + i * lh, 3)
                gen.append('LAYER_MARK   ; R2-RANGE raft layer %d' % (i + 1))
                gen.append('G0 Z%.3f F600' % z)
                ep = (first_h if i == 0 else lh) * wid / FIL_AREA
                ang = 45.0 if i % 2 == 0 else 135.0
                spacing = wid * 0.92 if floor_fill == 'solid' else 2.0 * wid
                # R77: overlapping SOLID lines must not extrude full width
                # each - scale the per-mm E by the spacing ratio (field log
                # .60: over-extruded solid floors tore the surface apart).
                # GRID (spacing >= wid, no overlap) stays at full width.
                eph = ep * min(1.0, spacing / wid)
                if f_shape == 'outline':
                    for poly in _mask_contours(mask1[0], mask1[1], mask1[2],
                                               mask1[3], mask1[4], res):
                        g.loop(poly, ep, 1200)
                    for (p, q) in _mask_hatch(mask1[0], mask1[1], mask1[2],
                                              mask1[3], mask1[4], res,
                                              spacing, ang):
                        g.move(p[0], p[1], 4800)
                        g.line(p[0], p[1], q[0], q[1], eph, 1200)
                else:
                    hull_off = _offset_hull(anchor, wid / 2.0)
                    g.loop(hull_off, ep, 1200)
                    for (p, q) in _hull_hatch(anchor, spacing, ang):
                        g.move(p[0], p[1], 4800)
                        g.line(p[0], p[1], q[0], q[1], eph, 1200)
        # BRIM: N loops around the raft/section outline - zero gap, the first
        # loop starts directly at the model wall
        if brim > 0:
            gen.append('; R2-RANGE brim: %d loop(s), zero gap' % brim)
            gen.append('APPLY_TYPE TYPE=BRIM')
            # first loop center sits one full line width out from the wall
            # center line -> its inner edge touches the model wall: ZERO gap
            for k in range(brim):
                hull_off = _offset_hull(anchor, wid + k * wid)
                g.loop(hull_off, first_h * wid / FIL_AREA, 1200)

    hull_n = _as_poly(hull_n)
    t_shape = _shape_ok(top_shape, hull_n, mask_n) if top else None
    if top > 0 and t_shape is not None:
        gt = _GenE(gen_top, e_rel)
        gen_top.append('; R2-RANGE cap: %d %s layer(s), %s fill, over the last layer'
                       % (top, {'hull': 'footprint', 'outline': 'true outline'}[t_shape],
                          top_fill))
        gen_top.append('APPLY_TYPE TYPE=INFILL-SOLID')
        # last Z of the shifted body - reproduced from the tracked original
        # (the old builder scanned it back out of the shifted body lines)
        z_end = round(z_end_body - dz, 3) if z_end_body is not None else None
        for i in range(top):
            z = round((z_end if z_end is not None else base_z) + (i + 1) * lh, 3)
            gen_top.append('LAYER_MARK   ; R2-RANGE cap layer %d' % (i + 1))
            gen_top.append('G0 Z%.3f F600' % z)
            ang = 45.0 if i % 2 == 0 else 135.0
            spacing = wid * 0.92 if top_fill == 'solid' else 2.0 * wid
            ep = lh * wid / FIL_AREA
            eph = ep * min(1.0, spacing / wid)   # R77: solid overlap E-compensated
            if t_shape == 'outline':
                for poly in _mask_contours(mask_n[0], mask_n[1], mask_n[2],
                                           mask_n[3], mask_n[4], res):
                    gt.loop(poly, ep, 1200)
                for (p, q) in _mask_hatch(mask_n[0], mask_n[1], mask_n[2],
                                          mask_n[3], mask_n[4], res,
                                          spacing, ang):
                    gt.move(p[0], p[1], 4800)
                    gt.line(p[0], p[1], q[0], q[1], eph, 1200)
            else:
                hull_off = _offset_hull(hull_n, wid / 2.0)
                gt.loop(hull_off, ep, 1200)
                for (p, q) in _hull_hatch(hull_n, spacing, ang):
                    gt.move(p[0], p[1], 4800)
                    gt.line(p[0], p[1], q[0], q[1], eph, 1200)

    # ---- prologue: a NORMAL file head with PRINT_START -> full start flow ----
    n_layers = end - start + 1 + floor + top
    # R74: the copied _FILE_INFO goes in at the TOP (it used to run at the very
    # END of the print - Live > File showed the PREVIOUS print's values during
    # the whole range print). Runs as the first command after the TAG, before
    # PRINT_START, with the corrected layer count.
    if file_info_line:
        file_info_line = re.sub(r'TOTAL_LAYERS=\d+', f'TOTAL_LAYERS={n_layers}', file_info_line)
    out_lines = [
        f'; R2-RANGE excerpt of {os.path.basename(src)}: layers {start}..{end} of {total}',
        f'; layer {start} prints as the FIRST layer at Z{base_z:g} on the bed'
        + (f' (on a {floor}-layer raft)' if floor else '')
        + (f', {top} solid cap layers on top' if top else '')
        + (f', brim {brim}' if brim else ''),
        '; R79: this file AUTO-SELECTS itself after generation (the source file',
        '; selection is replaced - nothing is deleted). AS LEGACY = mesh + purge',
        '; + YOUR pre-print settings (recommended) | AS SLICED = 1:1 (source temps)',
        '; first layer rules apply: 0.2mm layer 1, fan off, L1 temps (Pre-Print)',
        TAG,
    ]
    if file_info_line:
        out_lines.append(file_info_line)
    out_lines += [
        f'PRINT_START MATERIAL={material} BED={bed:g} BED_AFTER={bed:g}'
        f' HOTEND_FIRST={hot:g} HOTEND_AFTER={hot:g} LAYER_HEIGHT={lh:g} TOTAL_LAYERS={n_layers}',
        'G90',
        'M83' if e_rel else 'M82',
    ]
    # R70: keep the source file's EXCLUDE_OBJECT_DEFINE blocks - KAMP's adaptive
    # mesh and the object-aware park need them (without them Klipper's KAMP falls
    # back to a full-bed mesh: field log .53 'No objects detected')
    out_lines += excludes

    if not e_rel:
        out_lines.append('G92 E0')
    if f_mod:
        out_lines.append(f'G1 F{f_mod:g}')
    out_lines.append('M107   ; R2-RANGE: first layer = fan off (layer 2 gets the source fan back)')
    if fx is not None:
        out_lines.append(f'G0 X{fx:g} Y{fy:g} F6000   ; R2-RANGE: travel to the first print position')
    out_lines += gen
    if not e_rel and gen:
        out_lines.append('G92 E0   ; R2-RANGE: body E starts at 0')

    # ---- pass B: stream the body through the Z/E shift into the output -----
    # per-line twin of the old _shift() closure (stateful E base across the
    # body, G92-aware: a 'G92 E0' in a layer head resets the counter, so every
    # following E is relative to THAT value - Orca resets per layer!)
    e_base = [e_abs]

    def _shift_line(l):
        c = _stripped(l)
        if c.startswith('G92'):
            m = EWORD_RE.search(c)
            if m and not e_rel:
                e_base[0] = float(m.group(1))
            return l
        if not RMOVE_RE.match(c):
            return l
        m = ZWORD_RE.search(l)
        if m:
            nz = round(float(m.group(1)) - dz, 3)
            l = l[:m.start(1)] + (f'{nz:g}' if nz > 0 else '0') + l[m.end(1):]
        m = EWORD_RE.search(l)
        if m and not e_rel:
            new_e = round(float(m.group(1)) - e_base[0], 5)
            l = l[:m.start(1)] + f'{new_e:g}' + l[m.end(1):]
        return l

    stem, ext = os.path.splitext(src)
    # R83: 00_ prefix (top of the file list) + 3 source letters + the range
    # + a version suffix. Same name = overwrite (the user's tweaks must not
    # pile up files); the SOURCE itself is never written to.
    _src3 = re.sub(r'[^A-Za-z0-9]', '', os.path.basename(stem))[:3] or 'RNG'
    out = os.path.join(os.path.dirname(stem) or '.',
                       f'00_{_src3}_L{start}-{end}_V{max(1, min(int(version), 99)):02d}{ext or ".gcode"}')
    if os.path.abspath(out) == os.path.abspath(src):
        raise ValueError('range output name collides with the source - refusing')
    # body (E rebased to start at 0) + EXCLUDE_OBJECT cleanup, streamed
    lm_seen = 0
    open_obj = None
    with open(out, 'w') as fo:
        for l in out_lines:
            fo.write(l + '\n')
        with open(src, 'r', errors='replace') as f:
            idx = 0
            for raw in f:
                if idx >= b:
                    break
                if idx >= a:
                    l = _shift_line(raw[:-1] if raw.endswith('\n') else raw)
                    c = _stripped(l)
                    drop = False
                    if c.startswith('EXCLUDE_OBJECT_END'):
                        if open_obj is None:
                            drop = True   # END without an open object (cut artifact) - drop
                        else:
                            open_obj = None
                    elif c.startswith('EXCLUDE_OBJECT_START'):
                        m = re.search(r'NAME=(\S+)', c)
                        open_obj = m.group(1) if m else None
                    if not drop:
                        # carry the source fan into layer 2 (first layer = fan off)
                        if l.strip() == 'LAYER_MARK':
                            lm_seen += 1
                            fo.write(l + '\n')
                            if lm_seen == 2 and fan:
                                fo.write(f'M106 S{fan}   ; R2-RANGE: fan state carried over from the source layers (layer 2+)' + '\n')
                        else:
                            fo.write(l + '\n')
                idx += 1
        # old split('\n') semantics: a source ending in '\n' contributes a
        # final '' element to the body when the body runs to the end of the
        # file - keep the empty line so the output stays byte-identical
        if end >= total and trailing_empty:
            fo.write('\n')
        if open_obj:
            fo.write(f'EXCLUDE_OBJECT_END NAME={open_obj}   ; R2-RANGE: closed open object at the cut' + '\n')
        for l in gen_top:
            fo.write(l + '\n')

        # R74: a proper END sequence - the excerpt used to just stop dead, the
        # nozzle stayed parked ON the finished print (.57 field log). PRINT_END
        # runs the full choreography: stats, fanfare, park away from the part.
        fo.write('M107' + '\n')
        fo.write('PRINT_END   ; R2-RANGE: planned end after layer %d - park + cool down' % end + '\n')
    return out, n_layers


# ======================================================================================
#  R61 PLOTTER - upload an image as 'name.png.gcode' (or 'drawing.svg.gcode') and the
#  watcher converts it IN PLACE into pen-plotter g-code. Filename options between
#  dots: 'bild.c3.s035.png.gcode' = 3 colors, 0.35mm line spacing (defaults: 2/0.40).
#  Pen up/down Z + speeds come from save_variables (LCD: Plotter menu).
#  PNG: luminance bands (band k -> pen k+1, hatched boustrophedon). SVG: vector paths
#  grouped by color (one pen per color). Print it with AS SLICED (1:1 - no purge!).
# ======================================================================================
# R73: plain uploads convert too - 'notes.txt' becomes 'notes.txt.gcode',
# 'photo.png' becomes 'photo.png.gcode' (the original stays untouched)
PLOT_PAT = re.compile(r'\.(png|jpe?g|svg|pdf|txt)(\.gcode)?$', re.I)
PLOT_OPTS = re.compile(r'\.(c(\d)|s(\d{1,3}))(?=\.|$)')


def _read_vars(var_path):
    """Parse a Klipper save_variables.cfg -> dict (best effort, missing file = {}).

    Klipper's configparser writes 'variable_name = value' - the 'variable_'
    prefix is stripped so lookups use the bare name. ':' is tolerated too.
    """
    vals = {}
    try:
        with open(var_path) as f:
            in_var = False
            for l in f:
                if l.strip().startswith('['):
                    in_var = l.strip().lower() == '[variables]'
                    continue
                if in_var:
                    m = re.match(r'(\w+)\s*[:=]\s*(.+)', l)
                    if m:
                        key = m.group(1)
                        if key.startswith('variable_'):
                            key = key[len('variable_'):]
                        vals[key] = m.group(2).strip().strip('\'"')
    except OSError:
        pass
    return vals


def _png_to_rgb(data):
    """Minimal pure-python PNG reader (8-bit gray/RGB/palette/alpha). -> w, h, rows[R,G,B]"""
    import struct
    import zlib
    if data[:8] != b'\x89PNG\r\n\x1a\n':
        raise ValueError('not a PNG file')
    pos = 8
    w = h = None
    bd = ct = None
    plte = None
    idat = b''
    while pos < len(data):
        ln, typ = struct.unpack('>I4s', data[pos:pos + 8])
        pos += 8
        chunk = data[pos:pos + ln]
        pos += ln + 4
        if typ == b'IHDR':
            w, h, bd, ct = struct.unpack('>IIBB', chunk[:10])
            if chunk[12]:
                raise ValueError('interlaced PNG not supported - save it non-interlaced')
        elif typ == b'PLTE':
            plte = [tuple(chunk[i:i + 3]) for i in range(0, len(chunk), 3)]
        elif typ == b'IDAT':
            idat += chunk
        elif typ == b'IEND':
            break
    if bd != 8:
        raise ValueError('only 8-bit PNG is supported (convert: 8-bit RGB/gray/palette)')
    nch = {0: 1, 2: 3, 3: 1, 4: 2, 6: 4}.get(ct)
    if nch is None:
        raise ValueError(f'unsupported PNG color type {ct}')
    raw = zlib.decompress(idat)
    stride = w * nch
    rows = []
    prev = bytearray(stride)
    p = 0
    for _ in range(h):
        ft = raw[p]
        p += 1
        line = bytearray(raw[p:p + stride])
        p += stride
        if ft == 1:
            for i in range(nch, stride):
                line[i] = (line[i] + line[i - nch]) & 255
        elif ft == 2:
            for i in range(stride):
                line[i] = (line[i] + prev[i]) & 255
        elif ft == 3:
            for i in range(stride):
                a = line[i - nch] if i >= nch else 0
                line[i] = (line[i] + ((a + prev[i]) >> 1)) & 255
        elif ft == 4:
            for i in range(stride):
                a = line[i - nch] if i >= nch else 0
                b = prev[i]
                c = prev[i - nch] if i >= nch else 0
                pa, pb, pc = abs(b - c), abs(a - c), abs(a + b - 2 * c)
                pr = a if (pa <= pb and pa <= pc) else (b if pb <= pc else c)
                line[i] = (line[i] + pr) & 255
        row = []
        for x in range(w):
            i = x * nch
            if ct == 3:
                r, g, b = plte[line[i]]
                al = 255
            elif ct == 0:
                r = g = b = line[i]
                al = 255
            elif ct == 4:
                r = g = b = line[i]
                al = line[i + 1]
            elif ct == 2:
                r, g, b = line[i], line[i + 1], line[i + 2]
                al = 255
            else:
                r, g, b = line[i], line[i + 1], line[i + 2]
                al = line[i + 3]
            if al < 128:
                r = g = b = 255
            row.append((r, g, b))
        rows.append(row)
        prev = line
    return w, h, rows


def _svg_to_paths(text, size_mm):
    """Very basic SVG -> [(color, [xy points])]. line/rect/circle/ellipse/poly*,
    path M/L/H/V/C/Q/Z, translate/scale transforms. Everything is fitted into
    size_mm (aspect kept, origin at 10/10mm bed margin)."""
    def num(s):
        return float(s)
    def attrs(tag):
        return dict(re.findall(r'([\w:-]+)\s*=\s*["\']([^"\']*)["\']', tag))
    m = re.search(r'viewBox\s*=\s*"\s*([\d.\-]+)[ ,]+([\d.\-]+)[ ,]+([\d.\-]+)[ ,]+([\d.\-]+)', text)
    if m:
        _, _, vw, vh = map(num, m.groups())
    else:
        mw = re.search(r'width\s*=\s*"[\d.]+', text)
        mh = re.search(r'height\s*=\s*"[\d.]+', text)
        vw = num(mw.group(0).split('"')[1]) if mw else 100.0
        vh = num(mh.group(0).split('"')[1]) if mh else 100.0
    if vw <= 0 or vh <= 0:
        raise ValueError('SVG has no usable viewBox/size')
    sc = (size_mm - 20) / max(vw, vh)

    def xform(a):
        tx = ty = 0.0
        sx = sy = 1.0
        for mm2 in re.finditer(r'(translate|scale)\s*\(([\d.\-,\s]+)\)', a.get('transform', '')):
            nums = [num(v) for v in re.split(r'[\s,]+', mm2.group(2).strip()) if v]
            if mm2.group(1) == 'translate':
                tx += nums[0] if nums else 0
                ty += nums[1] if len(nums) > 1 else 0
            else:
                sx *= nums[0] if nums else 1
                sy *= nums[1] if len(nums) > 1 else nums[0]
        return lambda x, y: (tx + x * sx, ty + y * sy)

    def bezier_c(p0, p1, p2, p3, n=12):
        return [((1 - u) ** 3 * p0[0] + 3 * (1 - u) ** 2 * u * p1[0] + 3 * (1 - u) * u * u * p2[0] + u ** 3 * p3[0],
                 (1 - u) ** 3 * p0[1] + 3 * (1 - u) ** 2 * u * p1[1] + 3 * (1 - u) * u * u * p2[1] + u ** 3 * p3[1])
                for u in [(k / n) for k in range(n + 1)]]

    def bezier_q(p0, p1, p2, n=12):
        return [((1 - u) ** 2 * p0[0] + 2 * (1 - u) * u * p1[0] + u * u * p2[0],
                 (1 - u) ** 2 * p0[1] + 2 * (1 - u) * u * p1[1] + u * u * p2[1])
                for u in [(k / n) for k in range(n + 1)]]

    paths = []
    for tag in re.findall(r'<(line|rect|circle|ellipse|polyline|polygon|path)\b([^>]*)/?>', text):
        kind, raw = tag
        a = attrs(raw)
        tf = xform(a)
        pts = []
        if kind == 'line':
            pts = [tf(num(a['x1']), num(a['y1'])), tf(num(a['x2']), num(a['y2']))]
        elif kind == 'rect':
            x, y, w2, h2 = num(a.get('x', 0)), num(a.get('y', 0)), num(a.get('width', 0)), num(a.get('height', 0))
            if w2 and h2:
                pts = [tf(x, y), tf(x + w2, y), tf(x + w2, y + h2), tf(x, y + h2), tf(x, y)]
        elif kind in ('circle', 'ellipse'):
            cx, cy = num(a.get('cx', 0)), num(a.get('cy', 0))
            rx = num(a.get('r', a.get('rx', 0)))
            ry = num(a.get('ry', a.get('r', 0)))
            if rx and ry:
                pts = [tf(cx + rx * __import__('math').cos(2 * __import__('math').pi * k / 32),
                          cy + ry * __import__('math').sin(2 * __import__('math').pi * k / 32))
                       for k in range(33)]
        elif kind in ('polyline', 'polygon'):
            nums = [num(v) for v in re.split(r'[\s,]+', a.get('points', '')) if v]
            pts = [tf(nums[i], nums[i + 1]) for i in range(0, len(nums) - 1, 2)]
            if kind == 'polygon' and pts:
                pts.append(pts[0])
        elif kind == 'path':
            d = a.get('d', '')
            toks = re.findall(r'([MLHVQCZmlhvqcz])|(-?\d*\.?\d+)', d)
            seq = []
            for cmd, val in toks:
                if cmd:
                    seq.append(cmd)
                else:
                    seq.append(float(val))
            i = 0
            cur = (0.0, 0.0)
            start = (0.0, 0.0)
            while i < len(seq):
                c = seq[i]
                i += 1
                rel = c.islower()
                C = c.upper()
                if C == 'M':
                    x, y = seq[i], seq[i + 1]; i += 2
                    cur = (cur[0] + x, cur[1] + y) if rel else (x, y)
                    start = cur
                    pts.append(tf(*cur))
                elif C in ('L', 'T'):
                    x, y = seq[i], seq[i + 1]; i += 2
                    cur = (cur[0] + x, cur[1] + y) if rel else (x, y)
                    pts.append(tf(*cur))
                elif C == 'H':
                    x = seq[i]; i += 1
                    cur = (cur[0] + x, cur[1]) if rel else (x, cur[1])
                    pts.append(tf(*cur))
                elif C == 'V':
                    y = seq[i]; i += 1
                    cur = (cur[0], cur[1] + y) if rel else (cur[0], y)
                    pts.append(tf(*cur))
                elif C == 'C':
                    p1, p2, p3 = (seq[i], seq[i + 1]), (seq[i + 2], seq[i + 3]), (seq[i + 4], seq[i + 5])
                    i += 6
                    if rel:
                        p1 = (cur[0] + p1[0], cur[1] + p1[1])
                        p2 = (cur[0] + p2[0], cur[1] + p2[1])
                        p3 = (cur[0] + p3[0], cur[1] + p3[1])
                    pts.extend([tf(*q) for q in bezier_c(cur, p1, p2, p3)])
                    cur = p3
                elif C == 'Q':
                    p1, p2 = (seq[i], seq[i + 1]), (seq[i + 2], seq[i + 3])
                    i += 4
                    if rel:
                        p1 = (cur[0] + p1[0], cur[1] + p1[1])
                        p2 = (cur[0] + p2[0], cur[1] + p2[1])
                    pts.extend([tf(*q) for q in bezier_q(cur, p1, p2)])
                    cur = p2
                elif C == 'Z':
                    cur = start
                    pts.append(tf(*cur))
        if len(pts) >= 2:
            color = a.get('stroke') or a.get('fill') or '#000000'
            paths.append((color, pts))
    if not paths:
        raise ValueError('no drawable SVG elements found (line/rect/circle/ellipse/poly*/path)')
    # SVG Y grows down, the bed Y grows up -> flip + fit
    ys = [p[1] for _, ps in paths for p in ps]
    xs = [p[0] for _, ps in paths for p in ps]
    if not xs or not ys:
        raise ValueError('SVG has no coordinates')
    x0, x1, y0, y1 = min(xs), max(xs), min(ys), max(ys)
    span = max(x1 - x0, y1 - y0, 1e-6)
    fit = sc
    out = []
    for color, ps in paths:
        mm = [(10 + (x - x0) * fit, 10 + (y1 - y) * fit) for x, y in ps]
        out.append((color, mm))
    return out


# ======================================================================================
#  R62 JPEG (baseline) decoder - pure Python, no packages needed on the Pi.
#  Supports SOF0 baseline, grayscale/YCbCr, 4:4:4 / 4:2:2 / 4:2:0, DQT/DHT/DRI.
#  Progressive JPEGs (SOF2, most phone photos) are rejected with a clear message
#  ("save as PNG"). A tiny IDCT keeps the code short - a 1MP photo takes ~2s.
# ======================================================================================
_ZIGZAG = [0, 1, 8, 16, 9, 2, 3, 10, 17, 24, 32, 25, 18, 11, 4, 5,
           12, 19, 26, 33, 40, 48, 41, 34, 27, 20, 13, 6, 7, 14, 21, 28,
           35, 42, 49, 56, 57, 50, 43, 36, 29, 22, 15, 23, 30, 37, 44, 51,
           58, 59, 52, 45, 38, 31, 39, 46, 53, 60, 61, 54, 47, 55, 62, 63]


class _JpegBitReader:
    def __init__(self, data, pos):
        self.data = data
        self.pos = pos
        self.bitbuf = 0
        self.nbits = 0

    def _fill(self):
        while self.nbits <= 24:
            if self.pos >= len(self.data):
                self.bitbuf = (self.bitbuf << 8) | 0
                self.nbits += 8
                continue
            b = self.data[self.pos]
            self.pos += 1
            if b == 0xFF:
                nxt = self.data[self.pos] if self.pos < len(self.data) else 0
                if nxt == 0x00:
                    self.pos += 1          # stuffed byte
                elif 0xD0 <= nxt <= 0xD7:
                    # restart marker inside the stream - handled by the caller,
                    # here: stop filling (byte was not consumed)
                    self.pos -= 1
                    b = 0
                else:
                    b = 0
            self.bitbuf = (self.bitbuf << 8) | b
            self.nbits += 8

    def bit(self):
        if self.nbits == 0:
            self._fill()
        self.nbits -= 1
        return (self.bitbuf >> self.nbits) & 1

    def bits(self, n):
        while self.nbits < n:
            self._fill()
        self.nbits -= n
        return (self.bitbuf >> self.nbits) & ((1 << n) - 1)

    def skip_to_byte(self):
        self.nbits = 0


def _jpeg_to_rgb(data):
    """Minimal baseline JPEG decoder -> (w, h, rows[[(r,g,b)..]..])."""
    if data[:2] != b'\xff\xd8':
        raise ValueError('not a JPEG file')
    pos = 2
    qt = {}
    huff_dc = {}
    huff_ac = {}
    comps = []
    restart_interval = 0
    sof = None
    scan = None
    while pos < len(data):
        if data[pos] != 0xFF:
            pos += 1
            continue
        m = data[pos + 1]
        pos += 2
        if m in (0xD8, 0x01) or 0xD0 <= m <= 0xD7:
            continue
        if m == 0xD9:
            break
        ln = (data[pos] << 8) | data[pos + 1]
        seg = data[pos + 2: pos + ln]
        if m == 0xDB:                      # DQT
            i = 0
            while i < len(seg):
                pq = seg[i] >> 4
                tq = seg[i] & 15
                i += 1
                qt[tq] = list(seg[i:i + 64]) if pq == 0 else [((seg[i + 2 * k] << 8) | seg[i + 2 * k + 1]) for k in range(64)]
                i += 64 if pq == 0 else 128
        elif m in (0xC0, 0xC1, 0xC2):      # SOF
            if m == 0xC2:
                raise ValueError('progressive JPEG not supported - save/export the image as PNG (e.g. screenshot or convert)')
            prec, h, w, nc = seg[0], (seg[1] << 8) | seg[2], (seg[3] << 8) | seg[4], seg[5]
            sof = (w, h)
            comps = []
            for c in range(nc):
                cid, hv, tq = seg[6 + 3 * c], seg[7 + 3 * c], seg[8 + 3 * c]
                comps.append({'id': cid, 'h': hv >> 4, 'v': hv & 15, 'tq': tq})
        elif m == 0xC4:                    # DHT
            i = 0
            while i < len(seg):
                tc = seg[i] >> 4
                th = seg[i] & 15
                counts = list(seg[i + 1:i + 17])
                i += 17
                vals = list(seg[i:i + sum(counts)])
                i += sum(counts)
                # build (code length -> {code: value})
                table = {}
                code = 0
                k = 0
                for lnth in range(1, 17):
                    for _ in range(counts[lnth - 1]):
                        table[(lnth, code)] = vals[k]
                        k += 1
                        code += 1
                    code <<= 1
                (huff_dc if tc == 0 else huff_ac)[th] = table
        elif m == 0xDD:                    # DRI
            restart_interval = (seg[0] << 8) | seg[1]
        elif m == 0xDA:                    # SOS
            ns = seg[0]
            for k in range(ns):
                cid = seg[1 + 2 * k]
                sel = seg[2 + 2 * k]
                for c in comps:
                    if c['id'] == cid:
                        c['td'] = sel >> 4
                        c['ta'] = sel & 15
            scan = pos + ln
            break
        pos += ln
    if sof is None or scan is None:
        raise ValueError('unsupported JPEG (no baseline scan found)')
    w, h = sof
    hmax = max(c['h'] for c in comps)
    vmax = max(c['v'] for c in comps)
    mcux = (w + 8 * hmax - 1) // (8 * hmax)
    mcuy = (h + 8 * vmax - 1) // (8 * vmax)

    br = _JpegBitReader(data, scan)

    def huff_decode(table):
        code = 0
        for lnth in range(1, 17):
            code = (code << 1) | br.bit()
            v = table.get((lnth, code))
            if v is not None:
                return v
        raise ValueError('JPEG Huffman decode error')

    def extend(v, n):
        return v - (1 << n) + 1 if v < (1 << (n - 1)) else v

    # per-component coefficient planes (full-resolution blocks)
    planes = {}
    for c in comps:
        bw = mcux * c['h']
        bh = mcuy * c['v']
            # NOTE: 'bh' (block rows) must NOT be named 'h' - the sampling
            # factors c['h']/c['v'] collided with it and silently shrank the plane.
        # NOTE: 'bh' (block rows) must NOT be named 'h' - the sampling
        # factors c['h']/c['v'] collided with it and silently shrank the plane.
        planes[c['id']] = {'w': bw, 'bh': bh, 'blocks': [[0] * 64 for _ in range(bw * bh)],
                       'pred': 0}
    mcus_done = 0
    total_mcus = mcux * mcuy
    rst = 0
    while mcus_done < total_mcus:
        if restart_interval and mcus_done and mcus_done % restart_interval == 0:
            br.skip_to_byte()
            # skip the RSTn marker
            while br.pos < len(data) - 1:
                if data[br.pos] == 0xFF and 0xD0 <= data[br.pos + 1] <= 0xD7:
                    br.pos += 2
                    break
                br.pos += 1
            for pl in planes.values():
                pl['pred'] = 0
            rst += 1
        my, mx = divmod(mcus_done, mcux)
        for c in comps:
            pl = planes[c['id']]
            dct = huff_dc[c['td']]
            act = huff_ac[c['ta']]
            q = qt.get(c['tq'], [16] * 64)
            for by in range(c['v']):
                for bx in range(c['h']):
                    blk = [0] * 64
                    s = huff_decode(dct)
                    if s:
                        pl['pred'] += extend(br.bits(s), s)
                    blk[0] = pl['pred'] * q[0]
                    k = 1
                    while k < 64:
                        rs = huff_decode(act)
                        r, s = rs >> 4, rs & 15
                        if s == 0:
                            if r == 15:
                                k += 16
                                continue
                            break
                        k += r
                        if k > 63:
                            break
                        blk[_ZIGZAG[k]] = extend(br.bits(s), s) * q[_ZIGZAG[k]]
                        k += 1
                    gx = mx * c['h'] + bx
                    gy = my * c['v'] + by
                    pl['blocks'][gy * pl['w'] + gx] = blk
        mcus_done += 1

    def idct8(blk):
        out = [0.0] * 64
        for y in range(8):
            for x in range(8):
                s = 0.0
                for v in range(8):
                    cu = (0.70710678 if v == 0 else 1.0)
                    row = blk[v * 8:v * 8 + 8]
                    su = 0.0
                    for u in range(8):
                        cuv = (0.70710678 if u == 0 else 1.0)
                        su += cuv * row[u] * _COS8[(2 * x + 1) * u % 32]
                    s += cu * su * _COS8[(2 * y + 1) * v % 32]
                out[y * 8 + x] = s / 4.0
        return out

    # cos(n*pi/16) has period 32 (not 16!) - cos(n*pi/16 + pi) flips the sign.
    # A 32-entry table keeps every AC term's sign correct.
    _COS8 = [round(cos(pi * i / 16), 9) for i in range(32)]

    def plane_pixels(pl):
        pix = [[0] * (pl['w'] * 8) for _ in range(pl['bh'] * 8)]
        for gy in range(pl['bh']):
            for gx in range(pl['w']):
                vals = idct8(pl['blocks'][gy * pl['w'] + gx])
                for yy in range(8):
                    row = pix[gy * 8 + yy]
                    base = gx * 8
                    for xx in range(8):
                        row[base + xx] = int(vals[yy * 8 + xx] + 128)
        return pix

    # decode + upsample to full size
    full = {}
    for c in comps:
        pl = planes[c['id']]
        pix = plane_pixels(pl)
        fw, fh = mcux * hmax * 8, mcuy * vmax * 8
        if c['h'] == hmax and c['v'] == vmax:
            up = pix
        else:
            up = [[pix[int(y * c['v'] / vmax)][int(x * c['h'] / hmax)] if int(y * c['v'] / vmax) < len(pix) and int(x * c['h'] / hmax) < len(pix[0]) else 128
                   for x in range(fw)] for y in range(fh)]
        full[c['id']] = (up, fw, fh)
    yid = comps[0]['id']
    ypix, fw, fh = full[yid]
    if len(comps) == 1:
        rows = [[(ypix[y][x], ypix[y][x], ypix[y][x]) if x < len(ypix[y]) else (128, 128, 128) for x in range(w)] for y in range(h)]
        return w, h, rows
    cbpix, _, _ = full[comps[1]['id']]
    crpix, _, _ = full[comps[2]['id']]
    rows = []
    for y in range(h):
        if y >= fh:
            break
        row = []
        yrow = ypix[y]
        cbrow = cbpix[min(y, fh - 1)]
        crrow = crpix[min(y, fh - 1)]
        for x in range(w):
            if x >= len(yrow):
                break
            yy = yrow[x]
            cb = cbrow[min(x, len(cbrow) - 1)] - 128
            cr = crrow[min(x, len(crrow) - 1)] - 128
            r = int(yy + 1.402 * cr)
            g = int(yy - 0.344136 * cb - 0.714136 * cr)
            b = int(yy + 1.772 * cb)
            row.append((max(0, min(255, r)), max(0, min(255, g)), max(0, min(255, b))))
        rows.append(row)
    if len(rows) < h:
        rows += [rows[-1]] * (h - len(rows))
    return w, h, rows


# ======================================================================================
#  R62 PDF vector extraction - reads path operators from Flate-compressed content
#  streams (m/l/c/re/h/S/s/f). Text (BT/ET/Tj) is ignored with a note. One pen.
# ======================================================================================
def _pdf_paths(data, size_mm):
    paths = []
    mat_stack = [(1, 0, 0, 1, 0, 0)]
    cur = []
    start = None
    for m in re.finditer(rb'(\d+)\s+0\s+obj(.{0,4000}?)stream\r?\n', data, re.S):
        s0 = m.end()
        e0 = data.find(b'endstream', s0)
        if e0 < 0:
            continue
        raw = data[s0:e0]
        try:
            txt = zlib.decompress(raw).decode('latin-1', errors='replace')
        except Exception:
            continue
        # only content-stream-looking data (ASCII, operators)
        printable = sum(1 for ch in txt[:2000] if 32 <= ord(ch) < 127 or ch in '\n\r\t')
        if len(txt) < 10 or printable / min(len(txt), 2000) < 0.95:
            continue
        toks = re.findall(r'(-?\d+\.?\d*)|([MmLlCcRrHhSsfWnQq]\b)|(/\w+)|(\[)|(\])|(\(.*?\))', txt)
        nums = []
        for num, op, *_ in toks:
            if num:
                nums.append(float(num))
            elif op:
                o = op
                if o == 'q':
                    mat_stack.append(mat_stack[-1])
                elif o == 'Q' and len(mat_stack) > 1:
                    mat_stack.pop()
                elif o == 'cm' and len(nums) >= 6:
                    a, b, c, d, e, f = nums[-6:]
                    pa = mat_stack[-1]
                    mat_stack[-1] = (pa[0] * a + pa[2] * b,
                                     pa[1] * a + pa[3] * b,
                                     pa[0] * c + pa[2] * d,
                                     pa[1] * c + pa[3] * d,
                                     pa[0] * e + pa[2] * f + pa[4],
                                     pa[1] * e + pa[3] * f + pa[5])
                    nums = []
                elif o == 'm' and len(nums) >= 2:
                    if cur:
                        paths.append(cur)
                    cur = [nums[-2:]
                           ]
                    nums = []
                elif o == 'l' and len(nums) >= 2:
                    if not cur:
                        cur = [nums[-2:]]
                    else:
                        cur.append(nums[-2:])
                    nums = []
                elif o == 'c' and len(nums) >= 6:
                    # bezier: keep the endpoints (coarse flattening)
                    if not cur:
                        cur = [nums[-6:-4]]
                    cur.append(nums[-2:])
                    nums = []
                elif o == 're' and len(nums) >= 4:
                    x, y, rw, rh = nums[-4:]
                    if not cur:
                        cur = [[x, y]]
                    else:
                        cur.append([x, y])
                    cur.append([x + rw, y])
                    cur.append([x + rw, y + rh])
                    cur.append([x, y + rh])
                    cur.append([x, y])
                    nums = []
                elif o in ('S', 's', 'f', 'F', 'B'):
                    if cur:
                        if o == 's' and len(cur) > 1:
                            cur.append(cur[0])
                        paths.append(cur)
                        cur = []
                    nums = []
                elif o in ('h', 'W', 'n'):
                    if o == 'h' and cur and len(cur) > 1:
                        cur.append(cur[0])
                    nums = []
                else:
                    nums = []
        if cur:
            paths.append(cur)
    if not paths:
        return []
    # PDF points (1/72 inch) -> mm, fit into size_mm
    allp = [p for path in paths for p in path]
    minx = min(p[0] for p in allp)
    miny = min(p[1] for p in allp)
    maxx = max(p[0] for p in allp)
    maxy = max(p[1] for p in allp)
    span = max(maxx - minx, maxy - miny, 1e-6)
    k = size_mm / span
    out = []
    for path in paths:
        pts = [((p[0] - minx) * k, (p[1] - miny) * k) for p in path]
        if len(pts) > 1:
            out.append(pts)
    return out


def _otsu_threshold(hist, total):
    """Classic Otsu: threshold that separates dark ink from a light background."""
    best, best_var = 128, -1.0
    w_b = 0
    sum_b = 0
    sum_all = sum(i * h for i, h in enumerate(hist))
    for th in range(256):
        w_b += hist[th]
        if w_b == 0:
            continue
        w_f = total - w_b
        if w_f == 0:
            break
        sum_b += th * hist[th]
        m_b = sum_b / w_b
        m_f = (sum_all - sum_b) / w_f
        var = w_b * w_f * (m_b - m_f) ** 2
        if var > best_var:
            best_var, best = var, th
    return best


def plot_convert(path, var_path=None, out=None):
    """Convert name[.opts].png/.jpg/.svg/.pdf.gcode in place into plotter g-code.

    R62: auto-contrast (Otsu: background -> white, whatever its tint - yellowed
    paper, grey grid paper), draw vs stipple (dots) mode, pen offset X/Y/Z,
    X/Y scaling capped at the bed limits, centered on the bed, optional
    extruder use (draw with filament instead of a pen), JPEG + vector PDF.
    All settings: Plotter menu (baked in at conversion time).
    """
    base = os.path.basename(path)
    pm = PLOT_PAT.search(base)
    kind = pm.group(1).lower()
    head = base[:pm.start()]
    colors, spacing_mm = 2, 0.4
    for m in PLOT_OPTS.finditer(head):
        if m.group(2):
            colors = min(8, max(1, int(m.group(2))))
        if m.group(3):
            spacing_mm = min(2.0, max(0.05, int(m.group(3)) / 100.0))
    v = _read_vars(var_path) if var_path else {}
    def _v(key, d):
        try:
            return float(v.get(key, d))
        except (TypeError, ValueError):
            return d
    z_up = _v('plot_z_up', 3.0)
    z_dn = _v('plot_z_down', 0.0) + _v('plot_off_z', 0.0)
    spd = _v('plot_speed', 40) * 60
    trv = _v('plot_travel', 120) * 60
    size = _v('plot_size', 170)
    mode = int(_v('plot_mode', 0))          # 0 = draw lines, 1 = stipple dots
    dot_gap = max(0.4, _v('plot_dot_gap', 1.5))
    off_x = _v('plot_off_x', 0.0)
    off_y = _v('plot_off_y', 0.0)
    sx_pct = max(10, _v('plot_scale_x', 100))
    sy_pct = max(10, _v('plot_scale_y', 100))
    extrude = int(_v('plot_extrude', 0)) == 1
    autocontrast = int(_v('plot_autocontrast', 1)) == 1
    bmin_x, bmin_y = _v('plot_bed_min_x', 5), _v('plot_bed_min_y', 5)
    bmax_x, bmax_y = _v('plot_bed_max_x', 239), _v('plot_bed_max_y', 233)

    with open(path, 'rb') as f:
        data = f.read()

    # ---------------- raster input (png / jpg) ----------------
    raster = None
    note_lines = []
    if kind == 'png':
        raster = _png_to_rgb(data)
    elif kind in ('jpg', 'jpeg'):
        raster = _jpeg_to_rgb(data)      # raises a clear message on progressive JPEG
    if raster is not None:
        w, h, rows = raster
        # --- R64 polarity: dark background (digital writing boards etc.) -> the
        #     BORDER is sampled (text/drawings rarely touch it) - a dark border
        #     with a lighter interior means: invert, ink = the bright strokes
        invert_mode = int(_v('plot_invert', -1))      # -1 auto, 0 never, 1 always
        border = []
        bstep = max(1, (w + h) // 500)
        for x in range(0, w, bstep):
            border.append(rows[0][x])
            border.append(rows[h - 1][x])
        for y in range(0, h, bstep):
            border.append(rows[y][0])
            border.append(rows[y][w - 1])
        bmean = (sum((r * 299 + g * 587 + b * 114) // 1000 for r, g, b in border)
                 // max(1, len(border)))
        do_invert = invert_mode == 1 or (invert_mode == -1 and bmean < 110)

        def raw_lum(r, g, b):
            l = (r * 299 + g * 587 + b * 114) // 1000
            return 255 - l if do_invert else l
        if do_invert:
            note_lines.append('; polarity: dark background (border mean %d) -> INVERTED, '
                              'ink = the bright pixels' % bmean)
        else:
            note_lines.append('; polarity: light background (border mean %d) - not inverted' % bmean)
        # --- auto contrast (R62): Otsu split, background becomes pure white ---
        if autocontrast:
            hist = [0] * 256
            for row in rows:
                for r, g, b in row:
                    hist[raw_lum(r, g, b)] += 1
            th = _otsu_threshold(hist, w * h)
            # a background that is at least 55% of the image counts as 'light';
            # below that the image is mostly dark - keep the raw bands then
            bg = sum(hist[th + 1:]) / (w * h)   # share BRIGHTER than the threshold
            if bg >= 0.55:
                note_lines.append(f'; auto-contrast: Otsu threshold {th} (background {int(bg * 100)}% -> white)')

                def lum(r, g, b):
                    # everything ABOVE the threshold is background -> pure white;
                    # ink at/below it keeps its darkness for the shade bands
                    # (a pixel exactly ON the threshold is still ink - Otsu's
                    # threshold is the darkest background value, inclusive)
                    return 255 if raw_lum(r, g, b) > th else raw_lum(r, g, b)
            else:
                note_lines.append(f'; auto-contrast: mostly dark image - raw luminance bands kept')

                def lum(r, g, b):
                    return raw_lum(r, g, b)
        else:

            def lum(r, g, b):
                return raw_lum(r, g, b)

    # ---------------- geometry + transform ----------------
    # base extents in mm BEFORE scaling (long side = size)
    pens = []          # list of (label, [polylines [(x_mm, y_mm)..]])
    if raster is not None:
        bw = size * w / max(w, h)
        bh = size * h / max(w, h)
        if mode == 0:
            # ---- draw: boustrophedon hatch lines per luminance band ----
            nlines = max(2, int(round(bh / spacing_mm)))
            for band in range(colors):
                lo = band * 256 // colors
                hi = (band + 1) * 256 // colors
                if autocontrast and band == colors - 1:
                    hi = 255          # pure white = background, never plotted
                polys = []
                for k in range(nlines):
                    yi = int(k * h / nlines)
                    if yi >= h:
                        break
                    runs = []
                    run = None
                    for x in range(w):
                        ink = lo <= lum(*rows[yi][x]) < hi
                        if ink and run is None:
                            run = x
                        elif not ink and run is not None:
                            if x - run >= 2:
                                runs.append((run, x))
                            run = None
                    if run is not None and w - run >= 2:
                        runs.append((run, w))
                    for r0, r1 in runs:
                        xa = r0 * bw / w
                        xb = r1 * bw / w
                        yv = k * bh / h
                        pts = [(xa, yv), (xb, yv)]
                        if k % 2:
                            pts.reverse()
                        polys.append(pts)
                if polys:
                    pens.append((f'band {band + 1} (dark{"est" if band == 0 else ""})', polys))
        else:
            # ---- stipple: dot grid, dot spacing dot_gap / spacing_mm ----
            nx = max(2, int(round(bw / dot_gap)))
            ny = max(2, int(round(bh / spacing_mm)))
            for band in range(colors):
                lo = band * 256 // colors
                hi = (band + 1) * 256 // colors
                if autocontrast and band == colors - 1:
                    hi = 255          # pure white = background, never plotted
                polys = []
                for ky in range(ny):
                    yi = int(ky * h / ny)
                    if yi >= h:
                        break
                    for kx in range(nx):
                        xi = int(kx * w / nx)
                        if xi >= w:
                            break
                        if lo <= lum(*rows[yi][xi]) < hi:
                            polys.append([(kx * bw / nx, ky * bh / ny)])
                if polys:
                    pens.append((f'band {band + 1} (dark{"est" if band == 0 else ""}), dots', polys))
    elif kind == 'svg':
        text = data.decode('utf-8', errors='replace')
        by_color = {}
        for color, pts in _svg_to_paths(text, size):
            by_color.setdefault(color.lower(), []).append(pts)
        def lum_of(c):
            m = re.match(r'#([0-9a-f]{6})$', c)
            if m:
                r, g, b = int(c[1:3], 16), int(c[3:5], 16), int(c[5:7], 16)
                return r * 299 + g * 587 + b * 114
            m = re.match(r'rgb\((\d+)[,(](\d+)[,(](\d+)', c)
            if m:
                r, g, b = map(int, m.groups())
                return r * 299 + g * 587 + b * 114
            return 0
        dropped = len(by_color) - colors
        if dropped > 0:
            note_lines.append(f'; {dropped} more color(s) dropped - rename to .c{len(by_color)}.svg.gcode for all pens')
        for color in sorted(by_color, key=lum_of)[:colors]:
            pens.append((f'color {color}', by_color[color]))
        bw = bh = size
    else:   # pdf
        paths = _pdf_paths(data, size)
        if not paths:
            raise ValueError('no vector paths found in the PDF (text-only PDFs are not supported - export as PNG instead)')
        note_lines.append('; PDF: vector paths only (text/fonts are ignored) - one pen, path colors are not read')
        pens.append(('pdf paths', paths))
        bw = bh = size

    if not pens:
        raise ValueError('nothing to plot (image too light / no paths)')

    # ---------------- scale (capped at the bed limits) + center + pen offset ----------------
    avail_x = (bmax_x - 2) - (bmin_x + 2) - abs(off_x)
    avail_y = (bmax_y - 2) - (bmin_y + 2) - abs(off_y)
    sx = sx_pct / 100.0
    sy = sy_pct / 100.0
    if bw * sx > avail_x:
        sx = avail_x / bw
        note_lines.append(f'; scale X capped at {sx * 100:.0f}% (bed limit {bmax_x - bmin_x:g}mm)')
    if bh * sy > avail_y:
        sy = avail_y / bh
        note_lines.append(f'; scale Y capped at {sy * 100:.0f}% (bed limit {bmax_y - bmin_y:g}mm)')
    all_pts = [p for _, polys in pens for pl in polys for p in pl]
    gx = [p[0] for p in all_pts]
    gy = [p[1] for p in all_pts]
    cx_img = (min(gx) + max(gx)) / 2
    cy_img = (min(gy) + max(gy)) / 2
    cx_bed = (bmin_x + bmax_x) / 2 + off_x
    cy_bed = (bmin_y + bmax_y) / 2 + off_y

    def tr(p):
        return (cx_bed + (p[0] - cx_img) * sx, cy_bed + (p[1] - cy_img) * sy)

    # ---------------- g-code output ----------------
    # R73: FILAMENT mode draws at a real layer height (plot_z_down/0 was a PEN
    # value - the nozzle scraped the bed, nothing came out), extrudes the
    # matching amount per mm, retracts on far travels and CONNECTS nearby
    # hatch runs (<= 1.6mm gap) into one stroke - far fewer dots and hops.
    mode_txt = 'DOTS' if mode else 'DRAW'
    e_per_mm = 0.0
    if extrude:
        fil_z = min(0.4, max(0.1, _v('plot_fil_z', 0.25)))
        z_dn = _v('plot_off_z', 0.0) + fil_z
        e_per_mm = fil_z * 0.65 / FIL_AREA
    trv = min(trv, 4800.0)
    L = [f'; R2-PLOT v4 - generated from {base} ({len(pens)} pen(s), {mode_txt}, hatch {spacing_mm:g}mm',
         f';         dot gap {dot_gap:g}mm, scale {sx * 100:.0f}/{sy * 100:.0f}% of {size:g}mm, pen offset X{off_x:g} Y{off_y:g} Z{z_dn:g})',
         '; mode: %s | draw Z %.2f | travel capped 80mm/s' % ('FILAMENT' if extrude else 'PEN', z_dn),
         '; start via the dialog: AS SLICED = pen only, AS LEGACY = heats too when the extruder is ON',
         '; pen Z/speeds/mode/offsets: Plotter menu (baked in at conversion time)',
         '; live tuning (speed/accel/babystepping) works while plotting - Z-babystep sets the pen pressure',
         TAG,]
    L = note_lines + L
    L += [
         f'_PLOT_START EXTRUDE={1 if extrude else 0}',
         'G21',
         'G90']
    # R75: object definition over the transformed plot area (adaptive mesh)
    _tx0 = cx_bed + (min(gx) - cx_img) * sx
    _tx1 = cx_bed + (max(gx) - cx_img) * sx
    _ty0 = cy_bed + (min(gy) - cy_img) * sy
    _ty1 = cy_bed + (max(gy) - cy_img) * sy
    _poly = '[[%.1f,%.1f],[%.1f,%.1f],[%.1f,%.1f],[%.1f,%.1f]]' % (
        _tx0, _ty0, _tx1, _ty0, _tx1, _ty1, _tx0, _ty1)
    L.append('EXCLUDE_OBJECT_DEFINE NAME=R2PLOT CENTER=%.1f,%.1f POLYGON=%s'
             % ((_tx0 + _tx1) / 2.0, (_ty0 + _ty1) / 2.0, _poly))
    L.append('EXCLUDE_OBJECT_START NAME=R2PLOT')
    if extrude:
        L += ['M83', 'G92 E0']
    for pi, (label, polys) in enumerate(pens):
        L.append(f'RESPOND MSG="Plot pen {pi + 1}/{len(pens)}: {label} - mount the pen, then resume"')
        L.append('M117 Plot: pen ' + str(pi + 1) + '/' + str(len(pens)))
        if pi:
            L.append('M0    # pen change pause (resume = go on)')
        L.append(f'G0 Z{z_up:g} F600')
        if extrude and mode == 0:
            # ---- DRAW + filament: merge nearby runs into continuous strokes ----
            merged = []
            for pts in polys:
                if merged:
                    last = merged[-1]
                    gap = math.hypot(pts[0][0] - last[-1][0], pts[0][1] - last[-1][1])
                    if gap <= 1.6:
                        last.extend(pts)
                        continue
                merged.append(list(pts))
            polys = merged
        _emit_plot(L, [ [tr(p) for p in pts] for pts in polys ],
                   int(trv), int(spd), extrude, z_up, z_dn, e_per_mm)
    L += ['EXCLUDE_OBJECT_END NAME=R2PLOT',
          f'G0 Z{z_up + 5:g} F600', 'G0 X5 Y190 F4800', 'M107', 'M84']
    out = out or path
    with open(out, 'w') as f:
        f.write('\n'.join(L) + '\n')
    return len(pens), len(L)


# ======================================================================================
#  R63 LABEL GENERATOR - printable label plates with engraved text, generated
#  from the LCD (Labels menu) or the console (GEN_LABELS). The watcher picks up
#  a 'label_gen_nonce' change in save_variables and builds the file in the gcodes
#  folder - it then runs through the NORMAL print flow (Pre-Print dialog, mesh,
#  purge, first-layer rules) because it carries PRINT_START + slicer-style
#  config comments (the post-processor tags it like any sliced file).
#
#  Layout follows the golden ratio: with a hole, the hole sits in the minor
#  segment (0.382) of its axis and the text in the major segment (0.618) - they
#  can never collide. Without a hole the text height is capped at 1/phi of the
#  available height. Text auto-scales to fit its band.
#
#  Print order is BY LAYER (all bases first in color 1, then M600 + filament
#  change, then the text layers in color 2). A purge tower is printed alongside
#  and doubles as the prime spot for the new color; every label (and the tower)
#  is registered with EXCLUDE_OBJECT_DEFINE so single labels can be canceled.
# ======================================================================================

LABEL_CHARSET = ("ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz"
                 "0123456789 ÄÖÜäöüß-.,:!?+*/()[]=%#&@°'<>_")
GR = 1.6180339887
FIL_AREA = 2.4053          # pi * (1.75/2)^2



# ---- embedded fonts (generated by tools/make_label_fonts.py - do not edit)
FONT_META_PIXEL = {'cap': 5.0, 'xheight': 3.0, 'desc': 2.0, 'height': 7.0, 'baseline': 5.0}
FONT_PIXEL = {
    'A': [0, 8, 28, 30, 54, 62, 127, 0, 0],
    'B': [0, 60, 62, 54, 62, 55, 62, 0, 0],
    'C': [0, 14, 63, 48, 112, 48, 63, 0, 0],
    'D': [0, 56, 62, 55, 51, 55, 62, 0, 0],
    'E': [0, 62, 62, 48, 62, 48, 62, 0, 0],
    'F': [0, 62, 62, 48, 62, 48, 48, 0, 0],
    'G': [0, 12, 62, 112, 103, 51, 63, 0, 0],
    'H': [0, 34, 54, 54, 62, 54, 54, 0, 0],
    'I': [0, 28, 30, 30, 30, 30, 30, 0, 0],
    'J': [0, 28, 30, 30, 30, 30, 30, 124, 120],
    'K': [0, 34, 54, 60, 56, 62, 55, 0, 0],
    'L': [0, 48, 48, 48, 48, 48, 63, 0, 0],
    'M': [0, 34, 119, 119, 127, 107, 99, 0, 0],
    'N': [0, 34, 54, 62, 62, 62, 54, 0, 0],
    'O': [0, 28, 54, 99, 99, 54, 28, 0, 0],
    'P': [0, 60, 62, 55, 62, 60, 48, 0, 0],
    'Q': [0, 28, 62, 119, 99, 119, 62, 14, 2],
    'R': [0, 60, 62, 54, 62, 62, 55, 0, 0],
    'S': [0, 28, 62, 48, 62, 6, 62, 0, 0],
    'T': [0, 127, 127, 28, 28, 28, 28, 0, 0],
    'U': [0, 34, 54, 54, 54, 54, 62, 0, 0],
    'V': [0, 99, 99, 54, 54, 30, 28, 0, 0],
    'W': [0, 9, 111, 127, 63, 54, 54, 0, 0],
    'X': [0, 34, 54, 30, 28, 62, 54, 0, 0],
    'Y': [0, 99, 119, 62, 28, 28, 28, 0, 0],
    'Z': [0, 62, 63, 14, 28, 56, 127, 0, 0],
    'a': [0, 0, 0, 62, 30, 126, 126, 0, 0],
    'b': [0, 48, 48, 62, 55, 55, 62, 0, 0],
    'c': [0, 0, 0, 62, 48, 112, 62, 0, 0],
    'd': [0, 6, 6, 62, 118, 118, 62, 0, 0],
    'e': [0, 0, 0, 62, 127, 127, 62, 0, 0],
    'f': [0, 15, 31, 127, 28, 28, 28, 0, 0],
    'g': [0, 0, 0, 62, 118, 118, 62, 6, 60],
    'h': [0, 48, 48, 62, 54, 54, 54, 0, 0],
    'i': [0, 28, 0, 28, 28, 28, 28, 28, 0],
    'j': [0, 28, 0, 28, 28, 28, 28, 56, 0],
    'k': [0, 48, 48, 55, 60, 60, 55, 0, 0],
    'l': [0, 28, 28, 28, 28, 28, 28, 28, 0],
    'm': [0, 0, 0, 126, 111, 107, 107, 0, 0],
    'n': [0, 0, 0, 62, 54, 54, 54, 0, 0],
    'o': [0, 0, 0, 62, 119, 119, 62, 0, 0],
    'p': [0, 0, 0, 62, 55, 55, 62, 52, 48],
    'q': [0, 0, 0, 62, 118, 118, 62, 22, 6],
    'r': [0, 0, 0, 63, 56, 56, 56, 0, 0],
    's': [0, 0, 0, 62, 60, 31, 62, 0, 0],
    't': [0, 0, 56, 127, 56, 56, 31, 0, 0],
    'u': [0, 0, 0, 54, 54, 54, 62, 0, 0],
    'v': [0, 0, 0, 119, 54, 62, 28, 0, 0],
    'w': [0, 0, 0, 107, 63, 62, 54, 0, 0],
    'x': [0, 0, 0, 54, 30, 28, 54, 0, 0],
    'y': [0, 0, 0, 119, 54, 62, 28, 28, 56],
    'z': [0, 0, 0, 63, 14, 60, 127, 0, 0],
    '0': [0, 28, 54, 107, 107, 54, 28, 0, 0],
    '1': [0, 8, 60, 12, 12, 12, 63, 0, 0],
    '2': [0, 28, 62, 6, 14, 56, 62, 0, 0],
    '3': [0, 60, 62, 6, 30, 6, 62, 0, 0],
    '4': [0, 4, 30, 30, 54, 127, 62, 0, 0],
    '5': [0, 62, 62, 60, 62, 7, 62, 0, 0],
    '6': [0, 14, 62, 60, 62, 55, 62, 0, 0],
    '7': [0, 62, 62, 6, 12, 28, 24, 0, 0],
    '8': [0, 28, 62, 62, 62, 55, 62, 0, 0],
    '9': [0, 28, 62, 118, 63, 30, 62, 0, 0],
    'Ä': [28, 28, 28, 30, 54, 62, 127, 0, 0],
    'Ö': [28, 28, 62, 119, 99, 119, 62, 0, 0],
    'Ü': [28, 50, 54, 54, 54, 54, 62, 0, 0],
    'ä': [20, 0, 0, 62, 30, 126, 126, 0, 0],
    'ö': [20, 0, 0, 62, 107, 107, 62, 0, 0],
    'ü': [20, 0, 0, 54, 54, 54, 62, 0, 0],
    'ß': [0, 30, 51, 62, 54, 107, 102, 0, 0],
    '-': [0, 0, 0, 0, 0, 62, 0, 0, 0],
    '.': [0, 0, 0, 0, 0, 0, 28, 0, 0],
    ',': [0, 0, 0, 0, 0, 0, 28, 56, 0],
    ':': [0, 0, 0, 0, 28, 0, 28, 0, 0],
    ';': [0, 0, 0, 0, 28, 0, 28, 56, 0],
    '!': [0, 0, 28, 28, 28, 28, 0, 28, 0],
    '?': [0, 62, 99, 6, 28, 12, 0, 12, 0],
    '+': [0, 0, 8, 8, 62, 12, 8, 0, 0],
    '*': [0, 8, 62, 62, 42, 0, 0, 0, 0],
    '/': [0, 2, 7, 14, 12, 24, 56, 0, 0],
    '(': [0, 12, 28, 56, 56, 56, 28, 0, 0],
    ')': [0, 24, 28, 12, 14, 14, 28, 0, 0],
    '[': [0, 62, 60, 56, 56, 56, 56, 62, 0],
    ']': [0, 62, 30, 14, 14, 14, 14, 62, 0],
    '=': [0, 0, 0, 62, 62, 62, 0, 0, 0],
    '%': [0, 32, 116, 124, 63, 29, 23, 2, 0],
    '#': [0, 8, 30, 63, 20, 62, 60, 0, 0],
    '&': [0, 24, 60, 48, 59, 110, 62, 24, 0],
    '@': [0, 0, 62, 46, 125, 119, 62, 62, 12],
    '°': [0, 28, 34, 28, 0, 0, 0, 0, 0],
    "'": [0, 28, 28, 0, 0, 0, 0, 0, 0],
    '<': [0, 0, 0, 14, 56, 60, 6, 0, 0],
    '>': [0, 0, 0, 56, 14, 30, 48, 0, 0],
    '_': [0, 0, 0, 0, 0, 0, 0, 0, 127],
}

FONT_META_MONO = {'cap': 6.1, 'xheight': 4.61, 'desc': 1.77, 'height': 7.87}
FONT_MONO = {
    'A': '4.3,5.89929 3.8,4.49929 3.6,4.39929 3.6,4.39929 3.5,3.49929 3.4,3.19929 2.7,0.799291 2.5,0.599291 2.1,0.699291 2.1,0.699291 2,1.09929 1.3,3.39929 1.1,4.39929;0.3,6.09929 0.5,5.99929 0.3,6.09929;0.3,6.09929 0.6,5.89929 0.9,4.49929 1.1,4.39929 3.6,4.39929;3.4,3.19929 3.4,3.29929 3.5,3.59929',
    'B': '3.1,5.89929 2.4,6.09929 0.4,6.09929 0.4,3.19929 0.4,0.799291 0.5,0.699291 1.9,0.699291 2.9,0.999291 3.2,1.29929 3.3,2.19929 3.1,2.69929 2.7,2.99929 2.3,3.19929 0.4,3.19929;3.1,5.89929 3.3,5.59929 3.4,5.29929 3.5,4.69929 3.2,3.89929 2.6,3.39929 2.7,2.99929 2.7,2.99929 3,2.79929 2.7,2.99929',
    'C': '3.8,0.9 3.6,0.5 3.3,0.3 2.4,0.1 1.4,0.5 0.9,1 0.7,1.3 0.5,1.8 0.4,3.7 0.5,4.3 0.7,4.8 1,5.2 1.6,5.7 2,5.9 3,5.9 3.4,5.7 3.6,5.6 3.8,5.2;0.7,4.8 0.7,4.9 1,5.3;0.9,0.9 0.9,1 0.7,1.3',
    'D': '3,1.39929 2.5,0.999291 1.5,0.699291 0.5,0.699291 0.4,0.799291 0.4,6.09929 1.9,6.09929 2.7,5.79929 3.3,5.19929 3.5,3.59929 3.5,2.49929 3.3,1.69929 3,1.39929',
    'E': '3.4,6.09929 0.4,6.09929 0.4,3.19929 0.4,0.799291 0.5,0.699291 3.3,0.699291;0.4,3.19929 3.2,3.19929',
    'F': '0.4,6.09929 0.4,3.19929 0.4,0.799291 0.5,0.699291 3.2,0.699291;0.4,3.19929 3,3.19929',
    'G': '2.8,3.3 3.7,3.3 3.7,5.3 3.5,5.6 2.9,5.9 2,5.9 1.5,5.7 1,5.3 0.7,4.7 0.4,2.8 0.6,1.6 1,0.8 1.6,0.3 2.6,0.1 3.3,0.3 3.7,0.5 3.7,0.5 3.9,1;0.5,4.3 0.7,4.7 0.5,4.4',
    'H': '0.4,6.09929 0.4,3.19929 0.4,0.799291;0.4,3.19929 3.5,3.19929;3.5,0.799291 3.5,3.19929 3.5,6.09929',
    'I': '1.7,0.699291 1.6,0.599291 0.4,0.599291;1.7,0.699291 3,0.599291;1.7,0.599291 1.7,0.699291 1.6,5.99929 1.6,6.09929;0.4,5.99929 1.6,5.99929 3,5.99929',
    'J': '0,5.1 0.4,5.7 1,5.9 2.1,5.9 2.6,5.6 2.9,5.3;1.5,0.3 3,0.4 3,4.8 2.9,5.3 2.6,5.7',
    'K': '4.4,6.1 3.7,5.7 2.3,3.6 1.6,2.7 1.6,2.7 1.8,2.2 2.9,1.1 3.7,0.2 4.2,0;0.4,3.1 1.1,2.9 1.6,2.7;0.4,0.4 0.4,3 0.4,3.1 0.4,3.3 0.4,5.7',
    'L': '0.4,0.799291 0.4,6.09929 3.5,6.09929',
    'M': '0.4,0.899291 0.6,0.799291 1.1,1.09929 1.8,3.59929 2.2,3.69929 2.4,3.69929 2.2,3.69929;2.2,3.69929 2.5,3.49929 3.2,1.29929 3.5,0.899291;3.5,0.899291 4,0.899291 4,6.09929;0.4,6.09929 0.4,0.899291 0.4,0.799291',
    'N': '0.5,1.09929 1.2,1.49929 1.2,1.49929 1.3,1.89929 1.5,2.39929 1.8,3.09929 2,3.59929 2.3,4.29929 2.7,5.19929 2.8,5.49929 2.7,5.19929 2.5,4.79929;2.8,5.49929 3.2,5.79929 3.4,5.79929;1.7,2.69929 1.8,3.09929 1.7,2.79929;2.2,3.89929 2.3,4.29929 2.2,3.99929;0.5,1.09929 0.4,1.29929 0.4,6.09929;3.4,5.79929 3.5,5.59929 3.5,0.799291',
    'O': '3.4,5 3,5.5 2.4,5.9 1.6,5.9 1.1,5.6 0.7,5 0.5,4.6 0.4,3.5 0.4,2.6 0.7,1.1 1.1,0.5 1.6,0.2 2,0.1 2.6,0.2 2.8,0.4 3.4,1.1 3.6,2 3.6,4.1 3.4,5 3.4,5.1;3.1,0.7 2.8,0.4;3.1,0.6 3.1,0.7 3.4,1.1',
    'P': '0.4,6.09929 0.4,3.69929 0.4,0.799291 0.5,0.699291 2.4,0.799291 2.9,0.999291 3.2,1.29929 3.4,1.69929 3.4,2.69929 3.2,3.09929 2.9,3.39929 2.4,3.69929 0.4,3.69929',
    'Q': '2.9,5.6 2.5,5.9 1.6,5.9 1.1,5.6 0.7,5 0.4,3.5 0.4,2.6 0.7,1.1 1.1,0.5 1.6,0.2 2,0.1 2.6,0.2 2.8,0.4 3.1,0.7 3.4,1.1 3.6,2 3.6,4.1 3.4,5 2.9,5.6 2.6,6 3,6.6 3.4,6.9;2.9,5.6 2.7,5.7 2.9,5.6;3.1,0.6 3.1,0.7 3.4,1.1',
    'R': '0.4,5.99929 0.4,3.49929 0.4,0.699291 0.5,0.599291 2.3,0.699291 2.8,0.899291 3.2,1.19929 3.2,1.19929 3.3,1.59929 3.3,2.39929 3.2,2.79929 2.8,3.19929 2.4,3.49929 2.4,3.49929 2.4,3.29929 2.4,3.49929 2.7,3.99929 3,4.29929 3.9,6.09929;2.4,3.49929 0.4,3.49929',
    'S': '0.4,5.6 1.1,5.9 2.4,5.9 3,5.6 3.2,5.5 3,5.6;3,5.6 3.4,5.1 3.5,4.6 3.5,3.9 3.1,3.4 2.8,3.2 1.1,2.7 0.8,2.6 0.4,2.1 0.4,1.2 0.7,0.8 1.1,0.4 2.1,0.1 3.2,0.4;3.5,0.9 3.2,0.4',
    'T': '2.3,6.09929 2.3,0.799291 2.3,0.699291;2.3,0.799291 2.2,0.699291 0.4,0.699291;2.3,0.799291 2.4,0.699291 4.3,0.699291',
    'U': '3.4,0.4 3.4,4.6 3.3,5.2 2.9,5.6 2.3,5.9 1.4,5.9 0.7,5.4 0.4,5 0.4,4.4 0.4,0.4',
    'V': '4.2,0.699291 4,0.799291 3.7,2.29929 3.4,3.09929 2.7,5.49929 2.5,5.99929 2.5,6.09929;2.5,5.99929 2.1,6.09929 1.9,5.79929 1.2,2.99929 1,2.19929 0.5,0.799291;1.1,2.59929 1.2,2.99929 1.1,2.69929 1,2.19929;3.5,2.79929 3.4,3.09929',
    'W': '3.8,5.59929 3.4,5.39929 3.2,4.69929 3.1,3.99929 2.9,3.39929 2.8,2.79929 2.6,2.59929 2.4,2.69929 2.2,2.79929 2,4.09929 1.8,4.69929 1.5,5.39929 1.3,5.69929 1.3,6.09929;3.8,6.09929 3.8,5.59929 4,5.19929 4.2,3.69929 4.5,1.39929 4.6,0.799291;1.5,5.39929 1.2,5.49929 1.1,5.39929 1,5.29929 0.5,1.19929 0.4,0.799291;1.8,4.79929 1.9,4.39929 2,4.09929 1.9,4.29929',
    'X': '0.6,0.1 1,0.4 1.3,1 2.2,2.4 2.4,2.6 2.8,2.4 3.2,1.8 4.1,0.4 4.6,0.1;4.8,6.1 4.4,5.9 4.1,5.4 3.7,4.8 2.9,3.4 2.6,3.2 2.4,3.2 2.2,3.3 2.4,3.2;0.1,6.1 0.4,6 0.9,5.3 1.5,4.5 2.1,3.5 2.4,3.2 2.8,2.4 2.8,2.4;1.5,1.3 1.3,1',
    'Y': '4.5,0.499291 4.3,0.499291 3.9,1.19929 3.3,2.09929 2.6,3.29929 2.3,6.09929;2.4,3.39929 2,3.19929 1.2,1.79929 0.8,1.09929 0.4,0.499291 0.1,0.399291',
    'Z': '0.5,6.09929 0.6,5.49929 0.8,5.29929 2.9,1.99929 3.4,1.29929 3.4,0.699291 0.4,0.699291;0.5,6.09929 3.8,6.09929',
    'a': '0.6,1.8 1.2,1.7 2.3,1.6 2.9,1.9 3.2,2.3 3.3,2.5 3.4,3.5 3.4,4.8 3.3,5.2 3,5.4 3,5.4 3.4,5.2 3.4,5.7;3.4,3.5 1.7,3.5 0.8,3.9 0.4,4.2 0.4,4.5 0.4,5 0.5,5.5 0.5,5.5 1.1,5.9 1.4,6 2.1,5.9 2.6,5.6 3,5.4;3.2,2.4 3.2,2.3 2.9,1.9',
    'b': '0.4,5.7 0.4,5.2 0.4,2.3 0.4,0.1;0.4,5.2 1.2,5.7 1.9,6 2.4,5.9 3,5.3 3.3,4.5 3.4,3.5 3.3,3 3,2.3 2.3,1.6 1.7,1.6 1.3,1.8 0.4,2.3;1.2,5.7 1.1,5.5 1.2,5.7;3.2,2.6 3.3,3 3.2,2.7 3.3,3;1.3,1.8 1,2.1',
    'c': '3.5,2.3 3.3,1.8 2.7,1.6 1.8,1.6 1.3,1.9 1,2.1 0.7,2.4 0.5,2.9 0.4,3.1 0.4,4.5 0.5,4.7 0.7,5.2 1.2,5.7 1.7,5.9 2.9,5.9 3.3,5.6 3.5,5.2',
    'd': '3.3,2.3 2.8,2 2.1,1.6 1.5,1.6 1.1,1.9 0.7,2.3 0.4,3 0.4,3.7 0.5,4.8 0.7,5.2 1.1,5.7 1.8,6 2.3,5.9 3.2,5.4 3.4,5.4 3.4,5.7 3.2,5.4;3.2,5.4 3.4,4.8 3.3,2.3;3.3,2.3 3.4,2.2 3.4,0.1;0.5,4.8 0.5,4.9 0.7,5.3',
    'e': '3.8,5.5 3.5,5.7 2.5,6 1.4,5.8 1,5.5 0.5,4.8 0.4,3.8 0.4,3.6 0.6,2.7 0.6,2.5 1.1,2 1.8,1.6 2.6,1.6 3.1,2 3.5,2.6 3.7,3.3 3.6,3.6;0.4,3.6 3.6,3.6',
    'f': '1.6,6.09929 1.6,2.09929 1.6,1.19929 1.8,0.799291 2,0.599291 2.3,0.399291 3.2,0.399291;0.3,2.09929 1.6,2.09929 3.3,2.09929',
    'g': '3.4,1.8 3.3,2.4 3.4,4.8 3.3,5.1;3.3,2.4 2.7,2 2.3,1.7 1.5,1.6 1,1.9 0.7,2.3 0.4,3.8 0.5,4.8 0.7,5.2 1,5.5 1.4,5.7 1.8,5.8 2.4,5.6 2.7,5.5 3.3,5.1;0.8,7.4 2.1,7.6 2.9,7.3 2.9,7.3 3.3,6.6 3.4,5.2 3.3,5.1;0.7,2.3 0.5,2.7 0.7,2.4',
    'h': '0.4,6.09929 0.4,2.79929 0.4,0.499291;3.2,6.09929 3.1,2.99929 2.9,2.49929 2.6,2.19929 1.8,1.99929 1.2,2.29929 0.4,2.79929',
    'i': '3.5,6.09929 1.9,6.09929 0.3,6.09929;0.6,1.99929 1.8,1.99929 1.9,2.09929 1.9,6.09929 1.9,6.09929;1.9,-0.00070922 1.9,0.999291',
    'j': '0.6,1.7 1.9,1.7 2.1,1.8 2.1,6.3 1.8,7.2 1.8,7.2 1.4,7.5 0.3,7.6;2.1,-0.3 2.1,0.7',
    'k': '3.5,1.5 3,1.6 2.6,2.1 1.6,3 1.5,3.4;0.4,3.8 1.5,3.4;0.4,0.1 0.4,3.8 0.4,5.7;3.8,6.1 3.3,5.9 3.2,5.7 2.8,5.2 1.5,3.4',
    'l': '2.1,5.99929 1.9,5.89929 2.1,5.99929 2.4,6.09929 3.3,6.09929;2.1,5.99929 1.8,5.69929 1.6,5.29929 1.6,0.399291 1.5,0.199291 0.3,0.199291',
    'm': '0.3,6.09929 0.3,2.49929 0.3,2.19929 0.3,2.39929;0.3,2.49929 0.9,2.19929 1.3,1.99929 1.8,2.19929;2.1,6.09929 2.1,3.19929 2.2,2.49929 2.2,2.49929 2,2.49929 1.8,2.19929;2.2,2.49929 2.7,2.19929 3,1.99929 3.4,1.99929 3.6,2.19929 3.8,2.69929 3.9,3.19929 3.9,6.09929',
    'n': '0.4,2.19929 0.4,2.79929 0.4,6.09929;0.4,2.79929 1,2.49929 1.8,1.99929 2.6,2.19929 2.9,2.49929 3.1,2.99929 3.2,6.09929',
    'o': '3.4,5 3.1,5.4 2.8,5.7 2.5,5.9 1.8,6 1.2,5.8 0.8,5.4 0.5,4.9 0.4,4 0.5,2.7 0.8,2.1 1.2,1.8 1.6,1.6 2.3,1.6 2.8,1.9 3.1,2.1 3.4,2.7 3.4,3 3.5,4.1 3.4,4.5 3.4,5 3.4,5 3.4,4.5',
    'p': '0.4,1.8 0.4,2.3 0.4,5.2 0.4,7.4;0.4,2.3 0.9,2.1 1.3,1.8 1.7,1.6 2.3,1.6 2.9,2.1 3.2,2.7 3.3,4.4 3.2,4.9 2.9,5.5 2.7,5.7 2.1,6 1.5,5.9 1.2,5.7 0.4,5.2',
    'q': '3.4,1.8 3.3,2.4 3.4,4.7 3.3,5.1 3.1,5.3 2.5,5.7 2.3,5.9 1.7,6 1.1,5.7 0.7,5.3 0.5,4.9 0.4,4 0.5,2.7 0.7,2.3 1.1,1.8 1.5,1.6 2.1,1.6 2.4,1.8 2.8,2.1 3.3,2.4;3.1,5.3 3.4,5.3 3.4,7.4;2.5,5.7 2.7,5.5 2.5,5.7',
    'r': '0.4,2.19929 0.4,2.99929 0.4,6.09929;0.4,2.99929 0.9,2.79929 1.5,2.19929 2.3,1.99929 2.8,2.09929;2.8,2.09929 3,2.29929 3.3,2.69929',
    's': '3.1,2.2 2.8,1.7 2.8,1.7 1.3,1.6 0.7,1.9 0.5,2.2 0.4,3 0.7,3.4 1.3,3.7 2.4,3.9 2.9,4.3 3,4.7 2.9,5.2 2.5,5.7 1.8,6 0.9,5.9 0.3,5.7',
    't': '1.8,5.79929 2.3,6.09929 3.4,6.09929;1.6,0.799291 1.6,1.99929 1.6,5.29929 1.8,5.79929 1.8,5.89929;3.4,1.99929 1.6,1.99929 0.3,1.99929',
    'u': '3.2,1.8 3.2,4.8 3.1,5.1 2.7,5.5 2.1,5.8 1.5,6 0.9,5.7 0.6,5.5 0.4,4.8 0.4,1.8;2.7,5.5 3.2,5.2 3.2,5.7',
    'v': '3.8,2.09929 3.8,2.09929 2.8,4.69929 2.4,5.79929 2.3,5.99929 2.3,6.09929;2.3,5.99929 2,6.09929 1.7,5.89929 1.5,5.19929 0.4,2.19929',
    'w': '2.4,3.79929 2.1,4.39929 1.9,5.19929 1.6,5.79929 1.4,6.09929;2.4,3.79929 2.6,3.79929 2.8,4.09929 2.9,4.59929 3.1,5.09929 3.2,5.59929 3.7,5.89929 3.7,5.89929 3.9,5.39929 4.6,2.19929;2.8,4.09929 2.8,3.89929 2.8,4.09929 2.8,4.19929;1.9,5.29929 2,4.89929 2,4.79929 2.1,4.39929 2.1,4.39929;0.4,2.19929 1.2,5.59929 1.3,5.79929 1.6,5.79929 1.6,5.79929 1.6,5.69929',
    'x': '0.4,1.6 1.2,2.4 2.1,3.4 2.9,2.6 3.9,1.6;2.9,2.6 2.5,3.3 2.9,2.6 2.9,2.6 1.5,4.7 0.6,5.8 0.2,6;1.5,4.7 2.3,4 2.9,4.7 3.6,5.6 3.8,5.9;3.8,5.9 4.3,6.1',
    'y': '3.8,1.7 3.8,1.7 3.3,3 3.1,3.6 2.8,4.4 2.5,5.1 2.2,5.4 2.2,5.4 2.1,6.3 1.8,7 1.4,7.4 0.6,7.6;1.8,5.1 1.8,5.2 1.8,5.1 1.4,4.2 1.1,3.3 0.9,2.8 0.5,1.8;1.8,5.1 2.2,5.4',
    'z': '0.4,1.99929 2.8,1.99929 3,2.19929 2.7,2.79929 2.4,3.09929 1.7,4.09929 0.9,5.09929 0.5,5.79929 0.6,6.09929 3.1,6.09929',
    '0': '3,5.4 2.7,5.7 2.3,5.9 1.6,5.9 1,5.5 0.6,5 0.5,4.3 0.4,3.5 0.5,1.8 0.9,0.7 1.2,0.4 1.9,0.1 2.6,0.3 3,0.7 3.3,1.3 3.5,2 3.5,4.1 3.3,4.8 3,5.4 3,5.5;2,2.5 2,3.5',
    '1': '3.1,5.99929 1.8,5.99929 0.5,5.99929;0.3,0.799291 1.6,0.599291 1.8,0.699291 1.8,5.99929 1.8,6.09929',
    '2': '0.5,6.09929 0.7,5.49929 1.5,4.69929 2.4,3.69929 2.9,2.99929 3.2,2.29929 3.1,1.29929 3.1,1.29929 2.7,0.899291 1.8,0.499291 0.4,0.799291 0.4,0.799291 0.1,1.29929;0.5,6.09929 3.3,6.09929',
    '3': '1.4,2.8 2.2,2.8 2.4,2.6 3,2.2 3.3,1.7 3.3,1.2 3.1,0.8 2.8,0.5 2.3,0.2 1.6,0.1 0.7,0.3 0.4,0.5;2.4,2.6 2.5,3 2.4,2.7;2.5,3 3.1,3.4 3.1,3.4 3.4,4.1 3.3,5.2;3.3,5.2 2.9,5.6 2.3,5.9 0.9,5.9 0.3,5.7',
    '4': '3.9,4.69929 3,4.69929 0.3,4.69929;3,6.09929 3,4.69929 2.9,0.899291 2.9,0.799291;2.9,0.899291 2.5,0.999291 2.1,1.29929 1.3,2.59929 0.7,3.69929 0.4,4.09929 0.3,4.69929',
    '5': '2.8,5.6 2.9,5.5 2.8,5.6 2.1,5.9 0.9,5.9 0.3,5.7;2.8,5.6 3.2,5 3.4,4.5 3.3,3.5 3.2,3.2 2.7,2.6 2.2,2.4 1.8,2.3 0.6,2.4 0.6,0.4 3,0.3;3.3,4.8 3.2,5 3.3,4.8 3.2,5',
    '6': '3.4,3.2 3,2.7 2.6,2.4 2.1,2.3 1.4,2.6 0.7,3.1 0.4,3.2 0.5,1.8 0.7,1 0.7,1 1.3,0.5 2.2,0.1 2.9,0.2 3.2,0.4 3.5,0.8;0.7,3.1 0.4,3.3 0.4,4 0.7,5.2 1,5.5 1.2,5.7 1.6,5.9 2.5,5.9 3,5.6 3.4,5.1 3.5,4.5 3.4,3.5 3.4,3.2 3.4,3.4',
    '7': '1.4,6.09929 1.7,5.29929 3.3,1.39929 3.4,0.799291;0.4,0.799291 3.4,0.799291',
    '8': '2.6,2.8 1.5,2.9 0.7,3.4 0.5,3.7 0.4,4.5 0.6,5.2 1,5.6 1.4,5.9 2.5,5.9 3,5.6 3.3,5.3 3.5,4.7 3.5,4 3.2,3.5 2.8,3.1 2.6,3 2.6,2.8 2.6,2.7;2.6,2.8 3.3,1.9 3.4,1.3 3.2,0.8 2.9,0.4 2.5,0.2 1.8,0.1 1,0.4 0.7,0.7 0.5,1.4 0.7,2.2;0.7,2.2 1.4,2.7 1.5,2.9 1.5,3 1.1,3.2 0.7,3.4',
    '9': '3.5,2.9 3.6,3 3.5,4.1 3.1,5.2 2.8,5.6 2.1,5.9 1.2,5.9 0.7,5.7;3.5,2.9 2.6,3.5 2.1,3.7 1.5,3.7 0.9,3.4 0.4,2.6 0.4,1.3 0.6,0.9 1,0.5 1.4,0.2 2.5,0.2 3.2,0.9 3.5,1.7 3.5,2.8 3.5,2.9 3.5,3;2.6,3.5 2.9,3.2;2.8,5.6 2.5,5.7',
    ' ': '',
    'Ä': '1.1,4.39929 1,4.39929 1.1,4.39929 3.6,4.39929 3.6,4.39929 3.5,3.49929 3.4,3.19929 2.7,0.799291 2.5,0.599291 2.1,0.699291 2.1,0.699291 2,1.09929 1.3,3.39929 1.1,4.39929;1.1,4.39929 0.9,4.49929 0.6,5.89929 0.3,6.09929;3.6,4.39929 3.8,4.49929 4.3,5.89929;0.3,6.09929 0.5,5.99929 0.3,6.09929;3.5,3.49929 3.5,3.59929 3.4,3.29929;3.2,-1.50071 3.2,-0.500709;1.6,-1.50071 1.6,-0.500709',
    'Ö': '0.7,1.1 1.1,0.5 1.6,0.2 2,0.1 2.6,0.2 2.8,0.4 3.1,0.7 3.4,1.1 3.6,2 3.6,4.1 3.4,5 3,5.5 2.4,5.9 1.6,5.9 1.1,5.6 0.7,5 0.5,4.6 0.4,3.5 0.4,2.6 0.7,1.1 0.7,1.1;3.1,0.6 3.1,0.7 3.4,1.1;2.9,-1.7 2.9,-0.7;1.2,-1.7 1.2,-0.7',
    'Ü': '3.4,0.4 3.4,4.6 3.3,5.2 2.9,5.6 2.3,5.9 1.4,5.9 0.7,5.4 0.4,5 0.4,4.4 0.4,0.4;2.7,-1.7 2.7,-0.7;1.1,-1.7 1.1,-0.7',
    'ä': '0.6,1.8 1.2,1.7 2.3,1.6 2.9,1.9 3.2,2.3 3.3,2.5 3.4,3.5 3.4,4.8 3.3,5.2 3.3,5.2 3,5.4 2.6,5.6 2.1,5.9 1.4,6 1.1,5.9 0.5,5.5 0.5,5.5 0.4,5 0.4,4.5 0.4,4.2 0.8,3.9 1.7,3.5 3.4,3.5;3.4,5.7 3.4,5.2 3.3,5.2;3.2,2.4 3.2,2.3 2.9,1.9;2.8,-0.4 2.8,0.6;1.2,-0.4 1.2,0.6',
    'ö': '3.4,5 3.1,5.4 2.8,5.7 2.5,5.9 1.8,6 1.2,5.8 0.8,5.4 0.5,4.9 0.4,3.6 0.5,2.7 0.8,2.1 1.2,1.8 1.6,1.6 2.3,1.6 2.8,1.9 3.1,2.1 3.4,2.7 3.4,3 3.5,3.5 3.4,4.5 3.4,5 3.4,5 3.4,4.5;2.8,-0.4 2.8,0.6;1.2,-0.4 1.2,0.6',
    'ü': '0.4,1.8 0.4,4.8 0.6,5.5 0.9,5.7 1.5,6 2.1,5.8 2.7,5.5 3.1,5.1 3.2,4.8 3.2,1.8;2.7,5.5 3.2,5.2 3.2,5.7;2.6,-0.4 2.6,0.6;1,-0.4 1,0.6',
    'ß': '2.9,1.2 2.2,1.7 1.8,2.1 1.8,2.7 1.9,3 3.2,4.1 3.5,4.4 3.5,4.8 3.4,5.5 3.4,5.5 3.1,5.7 2.4,6 1.3,5.8;0.4,5.7 0.4,1.1 0.5,0.7 0.9,0.1 1.3,0 2.1,0 2.7,0.3 2.7,0.3 3,0.8 2.9,1.2',
    '-': '1.7,3.8 0.4,3.8',
    '.': '0.5,5.09929 0.5,6.09929',
    ',': '0.8,5.4 0.5,6.5 0.4,7',
    ':': '0.5,1.99929 0.5,2.99929;0.5,5.09929 0.5,6.09929',
    ';': '0.8,5.4 0.5,6.5 0.4,7;0.9,1.9 0.9,2.9',
    '!': '0.4,0.4 0.4,3.8;0.4,5.1 0.4,6.1',
    '?': '1.4,4 1.6,3.1 2.2,2.4 2.8,1.7 2.8,1.1 2.7,0.8 2.3,0.4 2,0.2 1.5,0.1 0.9,0.2 0.4,0.5 0.1,0.6 0.1,0.9;1.4,5.1 1.4,6.1',
    '+': '4,3.4 2.1,3.4 0.4,3.4;2.1,1.6 2.1,3.4 2.1,5.2',
    '*': '0.2,2.6 1.8,1.7 3.1,1;0.3,0.9 1.8,1.7 2.1,2 3,2.4 3.4,2.6;1.8,0.1 1.8,1.7 1.8,3.3',
    '/': '3.5,0.3 3.3,0.7 2.8,1.7 2.3,2.8 1.8,3.8 1.3,4.8 0.9,5.9 0.5,6.7 0.2,6.9',
    '(': '1.4,7 1.1,6.5 0.6,5.4 0.4,3.8 0.4,2.4 0.7,1.3 1.1,0.5 1.5,-0.1;1.8,7.2 1.4,7',
    ')': '0.4,7 0.7,6.4 1,5.7 1.3,4.8 1.4,3.9 1.2,2.1 0.8,0.7 0.4,-0.1',
    '[': '1.4,7 0.4,6.9 0.4,0 0.4,0 0.5,-0.1 1.4,-0.1',
    ']': '1.2,6.9 1.3,6.8 1.3,0.1 1.2,-0.1 0.3,-0.1;1.2,6.9 0.3,7',
    '=': '0.4,4.3 4,4.3;4,2.6 0.4,2.6',
    '%': '0.5,1.09929 0.9,0.799291 1.3,0.699291 2,0.999291 2.3,1.39929 2.3,2.09929 2,2.49929 1.6,2.79929 1,2.79929 0.5,2.39929 0.2,1.69929 0.5,1.09929 0.5,1.09929;2.7,5.79929 3.2,6.09929 3.8,6.09929 4.2,5.79929 4.5,5.49929 4.5,4.79929 4.2,4.39929 3.8,4.09929 3.5,4.09929 3.1,4.09929 2.7,4.49929 2.4,5.09929 2.7,5.79929 2.7,5.79929;0.4,4.29929 1.3,3.89929 2.2,3.49929 3,3.19929 3.9,2.79929 4.4,2.59929',
    '#': '4,0.599291 3.7,2.29929 3.2,4.29929 2.6,6.09929 2.6,6.09929;2.5,0.499291 2.3,0.599291 2,2.29929 1.5,4.29929 1,5.99929;0.8,2.29929 2,2.29929 3.7,2.29929 4.7,2.29929;4.2,4.29929 3.2,4.29929 1.5,4.29929 0.3,4.29929',
    '&': '4.2,5.9 4,5.6 3.7,5.2 2.6,3.7 1.6,2.5 1.4,2.5 1.4,2.5 1.4,2.2 1.2,1.6 1.1,1.1 1.3,0.6 1.6,0.3 2.3,0.1 3,0.3 3.3,0.7;4.4,3.3 4.3,4.3 3.7,5.2 3,5.7 2.4,5.9 1.6,5.9 1,5.5 0.6,5.1 0.4,4.5 0.5,3.5 1,2.8 1.4,2.5;4.2,5.9 4.5,6',
    '@': '4.4,2.8 3.7,2.4 3.1,2.3 2.6,2.4 2.4,2.6 2.1,3 1.9,3.5 1.9,4.3 2.1,4.7 2.8,5.4 3.5,5.4 3.8,5.2 4.2,5.1 4.4,5;3.8,7.2 2.6,7.2 2,7 1.3,6.5 0.8,5.9 0.5,5.3 0.3,4.3 0.3,3.4 0.5,2.4 1,1.6 1.4,1.1 1.8,0.8 2.3,0.7 3,0.6 3.8,0.8;4.4,2.8 4.5,2.1 4.4,1.6 4.1,1.2 3.8,0.8;4.4,2.8 4.5,3 4.4,5 4.5,5.2 4.2,5.1;2.3,5 2.1,4.7;2.4,2.6 2.4,2.7 2.1,3.1',
    '°': '0.6,0.4 0.3,0.8 0.3,1.5 0.6,2 1.4,2.2 1.8,2.1 2.1,1.8 2.3,1.4 2.3,0.9 2,0.4 1.6,0.1 1,0.1 0.6,0.4',
    "'": '0.3,0.4 0.3,1.9',
    '<': '0.4,3.5 0.7,3.3 1,3 4.1,1.8 4.3,1.6;0.7,3.3 0.6,3.7 0.8,3.8 1.1,3.9 3.8,4.9 4,5 4.3,5.5',
    '>': '0.2,1.8 3.2,3 3.7,3.2;3.8,3.5 3.4,3.9 2.8,4.1 0.6,4.9 0.2,5.1;3.8,3.5 3.8,3.4 3.7,3.2 3.8,3.5 3.7,3.3',
    '_': '0.3,7.8 4.8,7.8',
}

FONT_META_SMOOTH = {'cap': 6.1, 'xheight': 4.61, 'desc': 1.77, 'height': 7.87}
FONT_SMOOTH = {
    'A': (5.8, '3.1,0.999291 4.2,3.69929 4.4,4.59929 4.7,5.19929 5,5.89929 5,5.99929;3.1,0.999291 2.8,0.799291 2.6,0.899291 2.3,1.29929 1.5,3.49929 1.2,4.59929 1.1,4.69929 0.9,5.29929 0.6,5.99929 0.6,6.09929;4.4,4.59929 1.2,4.59929 1.1,4.59929 1.2,4.59929'),
    'B': (5.8, '3.5,1.29929 3.1,0.899291 2.3,0.699291 0.5,0.699291 0.4,0.799291 0.4,3.19929 0.4,6.09929 2.8,6.09929 3.3,5.89929 3.7,5.59929 3.8,5.19929 3.8,4.39929 3.5,3.89929 2.9,3.39929 3.1,2.89929 3.5,2.49929 3.6,2.19929 3.5,1.29929 3.5,1.29929;3.1,2.89929 2.7,3.19929 0.4,3.19929'),
    'C': (5.9, '4.6,5.5 4.1,5.7 3.6,5.9 2.3,5.9 1.6,5.6 1.2,5.3 0.7,4.7 0.5,4.2 0.5,3.8 0.4,3.3 0.5,2.3 0.5,1.9 0.7,1.4 1.3,0.7 1.8,0.4 2.3,0.2 3.2,0.1 4,0.3 4.6,0.6 4.9,1.1;4.6,5.5 4.8,5.2'),
    'D': (6.6, '4.3,5.19929 3.9,5.59929 3.3,5.89929 2.6,6.09929 0.4,6.09929 0.4,0.799291 0.5,0.699291 2.6,0.799291 3.3,0.899291 3.8,1.29929 4.3,1.69929 4.5,2.19929 4.6,2.69929 4.6,4.19929 4.5,4.69929 4.3,5.19929 4.3,5.19929;4.3,1.69929 4.3,1.79929 4.5,2.29929 4.6,2.69929;4.6,4.09929 4.6,4.19929 4.5,4.69929'),
    'E': (5.4, '3.5,0.699291 0.5,0.699291 0.4,0.799291 0.4,3.19929 0.4,6.09929 3.5,6.09929;0.4,3.19929 3.3,3.19929'),
    'F': (4.9, '0.4,6.09929 0.4,3.19929 0.4,0.799291 0.5,0.699291 3.1,0.699291;0.4,3.19929 2.8,3.19929'),
    'G': (6.6, '4.7,5.5 3.7,5.9 2.4,5.9 1.8,5.7 1.3,5.3 0.7,4.7 0.5,4.2 0.5,3.8 0.4,3.3 0.5,2.3 0.5,1.9 0.7,1.4 1.3,0.7 1.8,0.4 2.8,0.1 3.8,0.2 4.5,0.4 5,0.7 5.2,1.2;4.7,5.5 4.9,5.2 4.9,3.3 3.5,3.2'),
    'H': (6.4, '4.3,0.799291 4.2,3.19929 4.3,6.09929;4.2,3.19929 0.4,3.19929;0.4,6.09929 0.4,3.19929 0.4,0.799291'),
    'I': (2.5, '0.4,0.799291 0.4,6.09929'),
    'J': (2.5, '1.5,6.8 1.1,7.2 0.7,7.4 0.4,7.4;1.5,6.8 1.6,6.2 1.6,0.4'),
    'K': (5.6, '0.4,5.7 0.4,2.9 0.4,0.4;4.8,6.1 4.1,5.9 2.7,4.5 1.3,2.9;1.3,2.9 1.3,2.6 1.9,2 3,1 3.8,0.2 4.5,0;1.3,2.9 0.4,2.9'),
    'L': (4.7, '0.4,0.799291 0.4,6.09929 3.4,6.09929'),
    'M': (7.3, '5.2,6.09929 5.2,0.899291 4.9,0.799291 4.5,1.09929 3.1,4.69929 2.7,4.89929 2.3,4.39929 1,0.999291 0.8,0.799291 0.4,0.899291;0.4,6.09929 0.4,0.899291 0.4,0.799291'),
    'N': (6.4, '2.2,3.39929 3.4,5.59929 2.2,3.39929 0.9,1.09929 0.6,0.999291 0.4,0.999291 0.4,0.999291 0.4,6.09929;2.2,3.39929 3.5,5.69929 4,5.89929 4.1,5.89929 4.1,5.89929 4.2,0.799291'),
    'O': (6.7, '0.5,1.9 0.5,2.3 0.4,3.3 0.5,4.2 0.8,4.9 1.5,5.5 2.3,5.9 3.4,5.9 4.2,5.5 4.9,4.8 5.2,3.9 5.2,3 5.2,2.2 4.9,1.3 4.2,0.6 3.7,0.3 2.7,0.1 2.1,0.3 1.4,0.6 0.7,1.4 0.5,1.9 0.5,2.4;0.5,4.2 0.5,3.8 0.5,3.7'),
    'P': (5.1, '0.4,6.09929 0.4,3.69929 0.4,0.799291 0.5,0.699291 2.1,0.699291 2.7,0.799291 3.2,1.19929 3.4,1.59929 3.5,2.59929 3.4,2.79929 3.2,3.19929 2.4,3.69929 0.4,3.69929'),
    'Q': (6.7, '3.7,5.9 2.3,5.9 1.2,5.3 0.5,4.2 0.4,3.3 0.5,2.3 0.5,1.9 0.7,1.4 1.4,0.6 2.1,0.3 2.7,0.1 3.7,0.3 4.2,0.6 4.9,1.3 5.2,2.2 5.2,3 5.2,3.9 4.9,4.8 4.5,5.3 4.2,5.5 3.7,5.9;0.5,4.2 0.5,3.8 0.5,3.7;5,7.2 4.3,6.9 3.8,6.3 3.7,5.9 3.7,5.8'),
    'R': (5.9, '0.4,5.7 0.4,3.2 0.4,0.4 0.5,0.3 2.5,0.4 3,0.6 3.2,0.9 3.5,1.3 3.4,2.3 3.2,2.7 2.6,3.2;0.4,3.2 2.6,3.2;2.6,3.2 2.8,3.6 3.2,4.1 4.1,5.7 4.7,6.1;3.4,2.3 3.4,2.4 3.2,2.8'),
    'S': (5.4, '0.3,5.5 1.3,5.9 2.6,5.9 3.3,5.6 3.7,5.2 3.8,4.8 3.7,3.8 3.4,3.4 2.8,3 2.3,2.9 1.6,2.8 0.9,2.6 0.4,2 0.4,1.1 0.9,0.5 1.3,0.3 2.4,0.1 3.5,0.4 3.9,0.9'),
    'T': (5.2, '2.6,6.09929 2.6,0.799291 2.6,0.699291;2.6,0.799291 2.5,0.699291 0.4,0.699291;2.6,0.799291 2.7,0.699291 4.8,0.699291'),
    'U': (6.2, '1,5.5 0.7,5 0.5,4.7 0.4,3.7 0.4,0.4;1,5.5 1.8,5.9 2.9,5.9 3.7,5.5 4.1,5 4.3,4.5 4.3,3.4 4.3,0.4'),
    'V': (5.8, '3,5.99929 2.7,6.09929 2.4,5.89929 2.3,5.59929 2.1,4.99929 1.9,4.49929 1.7,4.09929 1.6,3.59929 1.2,2.59929 0.7,1.39929 0.7,1.29929;5.1,0.899291 4.7,1.89929 4.1,3.39929 3.8,4.19929 3.7,4.59929 3.4,5.19929 3,5.99929;3.3,5.59929 3.4,5.19929 3.3,5.49929;1.7,3.99929 1.7,4.09929 1.9,4.59929'),
    'W': (8.4, '3.8,1.09929 3.5,1.49929 3.4,1.69929 3.4,1.99929 3.3,2.29929 3.2,2.89929 3.1,3.19929 2.9,3.69929 2.9,3.99929 2.8,4.29929 2.7,4.89929 2.6,5.09929 2.4,5.69929 2.2,6.09929 2.2,6.09929 1.9,6.09929 1.7,5.99929 1.7,5.99929 0.5,0.999291;7.4,0.799291 7.2,0.999291 6.1,5.79929 5.9,5.99929 5.6,6.09929 5.3,5.79929 5.1,5.19929 4.1,1.29929 4,1.09929 3.8,1.09929;5.3,5.79929 5.2,5.49929 5.3,5.69929;2.7,4.49929 2.8,4.29929 2.7,4.79929 2.6,5.09929 2.5,5.39929 2.6,5.19929 2.5,5.39929;3,3.49929 2.9,3.69929 3,3.39929 3.1,3.09929 3.2,2.59929 3.2,2.79929;3.4,1.69929 3.4,1.79929 3.5,1.49929 3.8,1.09929'),
    'X': (5.8, '4.8,0.199291 4.6,0.199291 4,0.999291 3.1,2.39929 2.8,2.69929 2.6,3.19929 0.5,5.99929;3.7,4.59929 2.9,3.39929 3.7,4.59929 4.7,5.99929 5,6.09929;3.7,4.59929 2.8,3.29929 2.6,3.19929;2.6,3.19929 2.3,3.39929;0.2,6.09929 0.5,5.99929;2.8,2.69929 3,2.59929 2.8,2.69929 2.6,2.69929 2.3,2.49929 0.8,0.299291'),
    'Y': (5.2, '0.3,0.499291 0.7,0.799291 1.9,2.59929 2.3,3.19929 2.6,3.19929 2.6,3.19929 2.6,6.09929;4.8,0.499291 4.5,0.799291 3,2.89929 2.6,3.19929'),
    'Z': (5.8, '4.3,0.699291 4.1,1.39929 3.7,1.89929 3.2,2.49929 2.9,2.89929 2.6,3.19929 2.3,3.59929 2,3.99929 1.6,4.39929 1,5.09929 0.8,5.39929 0.6,5.99929 0.6,5.99929 0.4,6.09929;1.6,4.39929 1.3,4.69929 1,5.09929 1,5.19929;0.6,5.99929 0.7,5.99929 4.7,5.99929;4.3,0.699291 4.2,0.599291 0.5,0.599291;2.6,3.29929 2.6,3.19929 2.9,2.79929'),
    'a': (5.2, '3.3,5.2 3.5,4.7 3.5,3.5 3.5,2.8 3.3,2.3 3,2 2.4,1.7 1.3,1.6 0.7,1.8 0.4,2.1;3.5,5.7 3.5,5.2 3.3,5.2 2.8,5.4 2.2,5.9 1.7,6 0.9,5.7 0.5,5.4 0.4,5 0.5,4.3 0.8,3.8 0.8,3.8 1.1,3.7 1.8,3.5 3.5,3.5;0.8,3.8 0.6,3.9 0.8,3.8;3.3,2.4 3.3,2.3 3,1.9'),
    'b': (5.4, '0.4,5.1 1.1,5.5 1.6,5.9 2.3,6 2.6,5.9 2.9,5.7 3.3,5.3 3.6,4.8 3.7,4.3 3.6,2.8 3.3,2.3 2.8,1.8 2.6,1.7 1.6,1.7 0.8,2.3 0.4,2.6 0.4,5.1 0.4,5.7;0.8,2.3 0.4,2.3 0.4,0.1'),
    'c': (4.7, '3.3,1.8 2.8,1.6 1.8,1.6 1.1,2 0.7,2.4 0.4,3.2 0.4,4.4 0.7,5.1 1.1,5.6 1.7,5.9 2.5,6 3.3,5.7'),
    'd': (5.4, '0.6,5.2 0.5,4.7 0.4,4.5 0.4,3.1 0.5,2.9 0.6,2.4 1.1,1.8 1.6,1.6 2.5,1.7 3,2.1 3.6,2.4 3.6,2.4 3.7,4.8 3.6,5.2 3.3,5.4 3.3,5.4 2.9,5.6;3.7,5.7 3.7,5.2 3.6,5.2 2.9,5.6 2.4,5.9 1.8,6 1.1,5.7 0.6,5.2;3.6,2.4 3.7,2.3 3.7,0.1'),
    'e': (5.2, '3.8,3.6 3.8,3 3.7,2.6 3.2,2 2.6,1.6 1.8,1.6 1,2 0.5,2.7 0.4,3.6 0.4,4.4 0.5,4.6 0.6,5.1 1,5.5 1.5,5.8 2.1,6 3.5,5.8 3.9,5.5;3.9,5.5 3.8,5.7 3.9,5.5;0.4,3.6 3.8,3.6'),
    'f': (3.0, '2.6,0.399291 1.8,0.399291 1.3,0.699291 1.3,0.699291 1.1,1.29929 1.1,2.09929 1.1,6.09929;0.3,2.09929 1.1,2.09929 2.4,2.09929'),
    'g': (5.4, '3.6,5 3.1,5.3 2.8,5.5 2.4,5.7 1.8,5.8 1.4,5.7 0.8,5.3 0.6,5 0.5,4.6 0.4,4.3 0.4,3.1 0.5,2.8 0.9,2.1 1.5,1.7;0.8,7.4 1.7,7.6 2.6,7.5 3,7.3 3.4,6.9 3.6,6.5 3.7,5.9 3.6,5 3.7,2.7 3.6,2.4 3.7,1.8;3.6,2.4 2.5,1.7 1.5,1.7;0.9,2 0.6,2.4 0.5,2.8 0.5,2.9'),
    'h': (5.4, '3.4,2.99929 2.9,2.29929 2.4,1.99929 1.6,2.09929 1.2,2.39929 0.5,2.79929 0.5,2.79929 0.4,2.99929 0.4,6.09929;0.5,2.79929 0.4,2.69929 0.4,0.499291;3.5,6.09929 3.4,2.99929 3.4,2.89929;1.6,2.09929 1.6,2.19929 1.2,2.39929'),
    'i': (2.4, '0.4,6.09929 0.4,2.19929;0.4,0.0992908 0.4,1.09929'),
    'j': (2.4, '1.3,1.8 1.3,6.5 1.1,7.2 0.7,7.5 0.3,7.6;1.3,-0.3 1.3,0.7'),
    'k': (4.9, '1.2,3.7 2.3,4.9 3.3,5.9 4,6.1;0.4,3.7 1.2,3.7;0.4,0.1 0.4,3.7 0.4,5.7;1.2,3.7 1.4,3.3 2.1,2.7 2.7,2.2 3.3,1.6 3.8,1.5'),
    'l': (2.4, '0.4,0.499291 0.4,6.09929'),
    'm': (8.3, '0.4,6.09929 0.4,2.99929 0.5,2.79929 0.5,2.69929;0.5,2.79929 0.4,2.69929 0.4,2.19929;0.5,2.79929 0.9,2.69929 1.2,2.29929 1.6,2.09929 2.5,2.09929;3.3,6.09929 3.3,3.19929 3.5,2.99929 3.8,2.89929 3.5,2.99929 3.3,2.99929 3,2.49929 2.5,2.09929;3.5,2.99929 4.1,2.49929 4.5,2.09929;6,2.39929 5.5,2.09929 4.5,2.09929;6,2.39929 6.3,2.99929 6.4,3.69929 6.4,6.09929;4.1,2.49929 4.1,2.39929 4.5,2.09929'),
    'n': (5.4, '0.4,2.19929 0.4,2.69929 0.5,2.79929 0.5,2.79929 0.4,2.99929 0.4,6.09929;0.5,2.79929 1.2,2.39929 1.6,2.09929 2.4,1.99929 2.9,2.29929 3.4,2.99929;3.5,6.09929 3.4,2.99929 3.4,2.89929;1.6,2.09929 1.6,2.19929 1.2,2.39929'),
    'o': (5.2, '3.4,5.3 3,5.7 2.6,5.9 1.9,6 1.1,5.6 0.7,5.2 0.4,4.5 0.4,3.1 0.5,2.7 0.7,2.3 1.1,2 1.6,1.6 2.5,1.6 3,1.9 3.4,2.3 3.7,2.8 3.8,3.3 3.7,4.8 3.4,5.3;0.5,4.9 0.7,5.2'),
    'p': (5.4, '0.8,2.3 0.4,2.3 0.4,1.8;0.4,7.4 0.4,5.1 0.4,2.6 0.8,2.3 1.6,1.7 2.6,1.7 2.8,1.8 3.3,2.3 3.6,2.8 3.7,4.3 3.6,4.8 3.3,5.3 2.9,5.7 2.6,5.9 2.3,6 1.6,5.9 1.1,5.5 0.4,5.1'),
    'q': (5.4, '0.6,5.2 0.5,4.7 0.4,4.5 0.4,3.1 0.5,2.9 0.6,2.4 1.1,1.8 1.6,1.6 2.5,1.7 3,2.1 3.6,2.4;3.7,1.8 3.6,2.4 3.7,4.8 3.6,5.2 3.3,5.4 3.3,5.4 3.7,5.2 3.7,7.4;0.6,5.2 1.1,5.7 1.8,6 2.4,5.9 2.9,5.6 3.3,5.4'),
    'r': (3.5, '2.6,2.49929 2.2,1.99929 1.3,2.29929 0.9,2.59929 0.4,2.89929;0.4,2.19929 0.4,2.89929 0.4,6.09929'),
    's': (4.4, '2.9,4.2 2.4,3.9 1.1,3.6 0.6,3.3 0.6,3.3 0.4,2.9 0.4,2.5 0.7,2 1.3,1.6 2.5,1.6 3,1.9 3.3,2.2;2.9,4.1 2.9,4.2 3,4.4 3.1,5 3,5.3 2.8,5.7 2.8,5.7 1.8,6 0.9,5.9 0.6,5.8 0.3,5.7'),
    't': (3.3, '2.5,6.09929 1.5,5.99929 1.1,5.79929 0.9,5.29929 0.9,1.99929 0.9,0.799291;0.3,1.99929 0.9,1.99929 2.6,1.99929'),
    'u': (5.4, '1.2,5.9 1.7,6 2.3,5.8 2.6,5.6 3.4,5.2;0.4,1.8 0.4,4.8 0.5,5 0.7,5.4 1.2,5.9;3.5,1.8 3.4,5.2 3.5,5.7;0.5,5 0.7,5.4 0.7,5.6 0.7,5.4 0.7,5.4'),
    'v': (5.0, '4,2.09929 2.4,5.99929 2.4,6.09929;0.4,2.19929 1.8,5.99929 2.1,6.09929 2.4,5.99929'),
    'w': (7.0, '2.9,2.69929 2.7,2.89929 2.1,5.39929 1.8,5.89929 1.6,6.09929 1.4,5.89929 0.4,2.39929;4.7,5.99929 4.8,5.89929 4.7,5.99929 4.5,6.09929 4.1,5.69929 3.4,2.79929 3.4,2.79929 3.1,2.69929 2.9,2.69929;4.7,5.99929 4.9,5.79929 5.7,2.49929 5.8,2.29929 5.8,2.29929'),
    'x': (5.0, '0.2,6 0.6,5.8 1.8,4.1 2.1,3.9 3.7,1.7 4.2,1.5;0.4,1.6 0.9,1.8 1.9,3.3 2.3,3.5 2.3,4 2.6,4.3 3.8,5.9 4.3,6.1;2.3,3.4 2.3,3.5 2.1,3.9 2.1,4;3.7,1.7 4,1.6'),
    'y': (5.0, '0.4,1.8 0.5,2 0.8,2.7 1.3,3.8 1.9,5.3 2.1,5.5 2.3,5.4 2.5,5.4 2.3,5.4 2.3,5.4 1.9,6.7 1.5,7.4 0.6,7.6;2.3,5.4 2.6,5.2 3.8,1.9 4,1.7;1.7,5 1.9,5.3;0.7,2.3 0.8,2.7 0.7,2.4'),
    'z': (4.5, '0.5,5.99929 0.6,5.49929 1,5.09929 1.8,4.09929 2.2,3.69929 2.6,3.19929 2.9,2.79929 3.2,2.29929 3,1.99929 0.4,1.99929;3.4,6.09929 0.6,6.09929 0.5,5.99929'),
    '0': (5.4, '3.1,5.6 3.6,4.8 3.8,4 3.8,2.1 3.6,1.3 3.1,0.5 2.5,0.1 1.7,0.1 1.3,0.4 0.8,0.9 0.4,1.9 0.4,3.5 0.5,4.5 0.8,5.2 1.3,5.7 2,6 2.6,5.9 3.1,5.6'),
    '1': (5.4, '0.2,0.899291 1.2,0.599291 1.8,0.699291 1.8,5.99929 1.8,6.09929;0.4,6.09929 1.8,5.99929 3.3,6.09929'),
    '2': (5.4, '0.2,0.899291 0.6,0.699291 1.2,0.499291 2.3,0.399291 2.8,0.699291 3.1,0.999291 3.3,1.39929 3.4,2.09929 3.2,2.79929 2.9,3.19929 2.6,3.59929 1.1,5.09929 0.8,5.49929 0.6,5.99929 0.6,5.99929 0.8,6.09929 3.5,6.09929'),
    '3': (5.4, '1.3,2.8 2.4,2.8 2.6,2.7 3,2.4 3.3,2.1 3.5,1.5 3.4,0.9 3.1,0.5 2.4,0.2 1.1,0.2 0.6,0.3;3.1,0.6 3.4,0.9;0.6,0.3 0.3,0.6;0.3,5.7 0.9,5.9 1.3,6 2.3,5.9 3,5.6 3.3,5.3 3.6,4.6 3.5,3.8 3.4,3.5 3.1,3.2 2.7,2.9 2.6,2.7 2.6,2.6 2.7,2.5 2.6,2.7 2.7,3 3.1,3.3;3.5,5 3.3,5.3;3.4,3.4 3.4,3.5 3.5,3.8'),
    '4': (5.4, '4.1,4.69929 3.1,4.69929 0.4,4.69929 0.6,3.89929 1.8,1.99929 2.4,1.09929 2.7,0.899291 3.1,0.799291 3.1,0.899291 3.1,4.69929 3.1,6.09929;3.1,0.899291 2.7,0.899291'),
    '5': (5.4, '0.7,0.3 0.6,2.3 2.2,2.3 2.8,2.6 3.4,3.3 3.5,3.8 3.5,4.5 3.4,5 3.1,5.4 2.7,5.7 2.3,5.9 1.3,6 0.9,5.9 0.2,5.7;0.7,0.3 3.2,0.3;3.1,5.5 3.1,5.4 3.4,5'),
    '6': (5.4, '3.6,0.4 3,0.1 2.1,0.1 1.5,0.4 1,0.9 0.7,1.3 0.4,2.2 0.4,3 0.6,3 1.2,2.7 1.7,2.4 1.9,2.3 2.7,2.3 3.1,2.5 3.4,2.8 3.7,3.2 3.8,3.8 3.8,4.5 3.7,5 3.4,5.4 3,5.8 2.3,6 1.7,5.9 1.2,5.6 0.8,5.2 0.5,4 0.6,3 0.6,3;3.8,0.8 3.6,0.4'),
    '7': (5.4, '0.3,0.599291 3.4,0.599291 3.4,0.599291 2.7,2.79929 2.3,3.69929 2.2,4.09929 2,4.59929 1.6,5.49929 1.5,5.89929 1.3,6.09929;1.8,4.99929 2,4.59929 2,4.59929'),
    '8': (5.4, '3.7,5.1 3.3,5.6 2.8,5.9 1.8,6 1.5,5.9 0.8,5.5 0.4,4.9 0.4,4 0.6,3.6 1.3,3 1.6,2.8 2.8,2.8 2.8,2.8 2.8,3 2.8,2.8 2.9,2.6 3.1,2.4 3.4,2.2 3.4,2.2 3.6,1.6 3.6,1.2 3.5,0.9 3.2,0.5 2.6,0.2 1.6,0.2 0.9,0.6 0.6,1.1 0.6,1.7 0.9,2.2 1.4,2.7 1.3,3;2.8,2.8 3.4,3.4 3.7,3.8 3.8,4.1 3.7,5.1'),
    '9': (5.4, '0.6,5.7 1.8,6 2.8,5.7 3.2,5.3 3.8,4.1 3.8,3.1 3.6,3.1 3,3.4 2.6,3.8 1.8,3.8 1.1,3.5 0.8,3.2 0.6,2.9 0.4,1.8 0.7,0.8 1,0.5 1.6,0.1 2.5,0.1 3,0.5 3.4,0.9 3.6,1.3 3.8,2.3 3.8,2.9 3.6,3.1'),
    'Ä': (5.8, '3.1,0.999291 4.2,3.69929 4.4,4.59929 4.7,5.19929 5,5.89929 5,5.99929;3.1,0.999291 2.8,0.799291 2.6,0.899291 2.3,1.29929 1.5,3.49929 1.2,4.59929 1.1,4.69929 0.9,5.29929 0.6,5.99929 0.6,6.09929;4.4,4.59929 1.2,4.59929 1.1,4.59929 1.2,4.59929;3.6,-1.30071 3.6,-0.300709;2,-1.30071 2,-0.300709'),
    'Ö': (6.7, '0.8,4.9 1.5,5.5 2.3,5.9 3.4,5.9 4.2,5.5 4.9,4.8 5.2,3.9 5.2,3 5.2,2.2 4.9,1.3 4.2,0.6 3.7,0.3 2.7,0.1 2.1,0.3 1.4,0.6 0.7,1.4 0.5,1.9 0.5,2.3 0.4,2.8 0.5,3.8 0.8,4.9 0.8,4.9;0.5,4.2 0.5,3.8 0.5,3.7;3.7,-1.7 3.7,-0.7;2,-1.7 2,-0.7'),
    'Ü': (6.2, '0.4,0.4 0.4,3.7 0.5,4.7 0.7,5 1,5.5;1,5.5 1.8,5.9 2.9,5.9 3.7,5.5 4.1,5 4.3,4.5 4.3,3.4 4.3,0.4;3.2,-1.7 3.2,-0.7;1.6,-1.7 1.6,-0.7'),
    'ä': (5.2, '3.5,5.7 3.5,5.2 3.3,5.2 2.8,5.4 2.2,5.9 1.7,6 0.9,5.7 0.5,5.4 0.4,5 0.5,4.3 0.8,3.8 0.8,3.8 0.6,3.9 0.8,3.8 1.1,3.7 1.8,3.5 3.5,3.5;3.3,5.2 3.5,4.7 3.5,3.5 3.5,2.8 3.3,2.3 3,2 2.4,1.7 1.3,1.6 0.7,1.8 0.4,2.1;3.3,2.4 3.3,2.3 3,1.9;2.7,-0.4 2.7,0.6;1.1,-0.4 1.1,0.6'),
    'ö': (5.2, '3.4,2.3 3,1.9 2.5,1.6 1.6,1.6 1.1,2 0.7,2.3 0.5,2.7 0.4,3.1 0.4,4.5 0.5,4.9 1.1,5.6 1.9,6 2.6,5.9 3,5.7 3.4,5.3 3.7,4.8 3.8,4.3 3.7,2.8 3.4,2.3 3.4,2.2;0.7,5.2 0.5,4.9;2.9,-0.4 2.9,0.6;1.2,-0.4 1.2,0.6'),
    'ü': (5.4, '3.4,5.2 2.6,5.6 2.3,5.8 1.7,6 1.2,5.9;1.2,5.9 0.7,5.4 0.4,4.8 0.4,1.8;3.5,1.8 3.4,5.2 3.5,5.7;0.5,5 0.7,5.4 0.7,5.6 0.7,5.4 0.5,5;2.7,-0.4 2.7,0.6;1.1,-0.4 1.1,0.6'),
    'ß': (5.4, '1.6,5.8 2.6,6 3.3,5.7 3.7,5.2 3.8,4.8 3.5,4.2 2.6,3.5 2.1,3 1.9,2.6 2,2.2 2.4,1.7 3.2,1.3 3.2,1.3 3.1,0.7 2.8,0.3 2.3,0 1.3,0 0.9,0.2 0.5,0.6 0.5,0.6 0.4,1.1 0.4,5.7'),
    '-': (3.1, '1.8,3.8 0.4,3.8'),
    '.': (2.7, '0.4,5.1 0.4,6.1'),
    ',': (2.7, '0.7,5.5 0.5,6.2 0.2,6.9 0.2,7'),
    ':': (2.9, '0.4,1.8 0.4,2.8;0.4,5.1 0.4,6.1'),
    ';': (2.9, '0.7,5.5 0.5,6.2 0.2,6.9 0.2,7;0.8,1.8 0.8,2.8'),
    '!': (3.4, '0.4,0.4 0.4,3.8;0.4,5.1 0.4,6.1'),
    '?': (4.5, '1.3,4 1.5,3.1 1.9,2.6 2.7,1.8 2.8,1.1 2.7,0.7 2.4,0.4 2,0.2 1.5,0.1 0.9,0.2 0.2,0.5 0.2,0.5 0,0.9;1.4,5.1 1.4,6.1'),
    '+': (7.1, '2.6,6.09929 2.6,3.79929 2.6,1.49929;0.4,3.79929 2.6,3.79929 4.9,3.79929'),
    '*': (4.3, '0.2,2.6 0.6,2.4 1.8,1.7 3,1 3.3,0.9;3.4,2.6 3,2.4 1.8,1.7 0.6,1 0.2,0.9;1.8,3.4 1.8,1.7 1.8,0.1'),
    '/': (2.9, '0.4,6.7 2.1,0.9 2.3,0.3 2.5,0.2'),
    '(': (3.3, '1.8,7.2 1.3,7 1.1,6.3 0.7,5.6 0.6,5 0.4,4.5 0.4,3.5 0.4,2.5 0.6,1.9 0.7,1.3 1.1,0.6 1.3,0 1.6,-0.2;1.6,-0.2 1.4,-0.1 1.6,-0.2'),
    ')': (3.3, '0.4,-0.1 0.7,0.5 1,1.2 1.2,2 1.3,2.5 1.4,4 1.3,4.5 1.2,5 1,5.7 0.7,6.5 0.4,7;1.3,4.4 1.3,4.5 1.2,5'),
    '[': (3.3, '1.4,7 0.4,6.9 0.4,0 0.4,0 0.5,-0.1 1.4,-0.1'),
    ']': (3.3, '1.2,6.9 0.3,7;1.2,6.9 1.3,6.8 1.3,0.1 1.2,-0.1 0.3,-0.1'),
    '=': (7.1, '4.9,4.3 0.4,4.3;0.4,2.6 4.9,2.6'),
    '%': (8.1, '6.4,5.6 6.2,5.9 5.7,6 5.2,6 4.9,5.7 4.7,5.4 4.5,4.9 4.5,4.3 4.7,3.8 5,3.4 5.3,3.1 6,3.1 6.4,3.5 6.7,4.3 6.7,4.9 6.4,5.6 6.4,5.7;1.3,6.2 1.6,6.1 3.5,3 5.5,-0.1 5.6,-0.1;2.1,0.3 1.7,0.1 1.1,0.1 0.6,0.4 0.6,0.4 0.3,1 0.3,2.1 0.6,2.6 1.3,3 1.8,2.9 2.1,2.7 2.3,2.3 2.5,1.7 2.3,0.7 2.1,0.3 2.1,0.3'),
    '#': (7.1, '3.1,6.09929 3.6,4.39929 4,2.39929 4.3,1.49929 4.5,0.699291 4.6,0.599291;0.8,2.39929 2.2,2.39929 4,2.39929 4.2,2.29929 5.4,2.39929;5,4.39929 3.6,4.39929 1.8,4.29929 1.6,4.39929 0.3,4.39929;2.8,0.499291 2.6,0.799291 2.3,2.19929 2.2,2.39929 1.8,4.29929 1.3,6.09929'),
    '&': (6.6, '5.2,3 4.9,3.8 4.7,4.4 4.2,5 3.6,5.5 3,5.8 1.8,5.9 1,5.4 0.5,4.8;5.7,6.1 5.1,5.9 4.3,5.2 4.2,5 2.4,3.2 1.8,2.6 1.4,2.5;1.4,2.5 0.9,3 0.6,3.4 0.4,3.9 0.5,4.8 0.5,4.9;1.5,0.4 2.3,0.1 3.4,0.4;1.5,0.4 1.2,0.8 1.1,1.1 1.3,1.9 1.4,2.5 1.4,2.6'),
    '@': (8.5, '5.6,6.7 4.3,7.2 3,7.2 2.2,7 1.3,6.2 0.6,5.4 0.4,4.8 0.2,3.5 0.4,2.6 1.3,1.4 2.3,0.6 2.8,0.5 3.5,0.4 4.5,0.5 5,0.6 5.7,1 6.4,1.7 6.9,2.6 7,3.3 7,4 6.7,4.5 6.3,5 5.7,5.3 5.1,5.4 5.1,5.4 5,4.9 5.1,4.3 5,2.8 5.1,2.3;3.1,5.4 2.8,5.2 2.4,4.8 2.3,4.4 2.3,3.3 2.5,2.8 2.8,2.5 3.1,2.3 3.5,2.2 4.1,2.3 4.5,2.6 5,2.8;3.1,5.4 3.9,5.4 4.2,5.3 4.5,5.1 5,4.9'),
    '°': (4.3, '0.3,1.6 0.6,2 1.2,2.2 1.7,2.1 2,1.9 2.3,1.3 2.3,0.9 2,0.4 1.6,0.1 1,0.1 0.6,0.4 0.3,0.8 0.3,1.6 0.3,1.6'),
    "'": (2.3, '0.4,0.4 0.4,1.8'),
    '<': (7.1, '0.7,3.3 0.8,3.1 0.7,3.3;0.7,3.3 1.1,3 2.7,2.4 3.7,2.1 4.7,1.7 5,1.6 4.7,1.7;0.7,3.3 0.9,3.8 3.5,4.7 4.6,5.1'),
    '>': (7.1, '4.8,3.4 4.5,3.5 4.2,3.8 2.2,4.5 1.2,4.9 0.4,5.1 0.2,5.3 0.2,5.4 0.2,5.3;4.5,3.5 4.5,3.7 4.5,3.5 4.4,3.1 2.9,2.6 2,2.3 1.1,2 0.3,1.7'),
    '_': (4.3, '4,7.8 0.3,7.8'),
    ' ': (3.0, ''),
}

# ---- R82 label fonts for small text (generated by tools/make_label_fonts.py
#      from Google-Fonts sources in tools/fonts_src/, all SIL OFL) ----
# COND   = Oswald: condensed, tall x-height - the small-text workhorse
#          (more characters per mm than SMOOTH at the same readability)
# NARROW = Roboto Condensed: clean, technical, narrow
# CAPS   = Bebas Neue: display capitals for key fobs / name plates
FONT_META_COND = {'cap': 5.36, 'xheight': 3.8, 'desc': 1.23, 'height': 6.59}
FONT_COND = {
    'A': (3.3, '0.4,5.1 0.6,3.9 0.7,3.7 0.8,3 1.2,1.2 1.4,0.8 1.5,0.7 1.5,0.3;0.7,3.7 2.2,3.7;1.4,0.8 1.8,0.9 2.2,3.3 2.2,3.7 2.2,3.8;2.2,3.7 2.3,3.8 2.6,5.1;1.4,0.8 1.2,0.9 1.4,0.8'),
    'B': (3.5, '1.9,0.663128 2.2,1.06313 2.3,1.36313 2.2,2.16313;1.9,0.663128 1.6,0.563128 1,0.463128 0.5,0.463128 0.4,0.563128 0.3,0.663128 0.3,2.76313 0.3,5.26313 0.4,5.36313 1.7,5.36313 2,5.26313 2.1,5.16313 2,5.26313;2,5.26313 2.3,4.86313 2.5,4.16313 2.3,3.46313 2,3.06313 1.7,2.86313 1.8,2.56313 2.2,2.16313;0.3,2.76313 1.6,2.76313 1.8,2.56313'),
    'C': (3.5, '0.8,5 0.6,4.8 0.5,4.5 0.3,3.7 0.3,1.6 0.5,0.9 0.6,0.6 0.8,0.4 1.1,0.2 1.9,0.3 2.2,0.5;0.8,5 1.3,5.1 1.9,5.1;2.2,0.5 2.3,0.8 2.5,1.5;1.9,5.1 2.3,4.7;2.5,3.7 2.3,4.7 2.3,4.8 1.9,5.1'),
    'D': (3.5, '1.9,0.663128 2.2,0.963128 2.3,1.16313 2.3,1.56313 2.3,4.26313 2.3,4.66313 2.2,4.96313;1.9,0.663128 0.9,0.463128 0.5,0.463128 0.4,0.563128 0.3,0.663128 0.3,5.26313 0.4,5.36313 1.6,5.36313 1.9,5.16313 2.2,4.96313;2.2,0.863128 2.2,0.963128 2.3,1.26313'),
    'E': (2.7, '1.7,0.463128 0.5,0.463128 0.4,0.563128 0.3,0.663128 0.3,2.86313 0.3,5.26313 0.4,5.36313 1.8,5.36313;0.3,2.86313 1.5,2.86313'),
    'F': (2.6, '1.5,2.6 0.3,2.6;1.7,0.2 0.5,0.2 0.4,0.3 0.3,0.4 0.3,2.6 0.3,5'),
    'G': (3.6, '1.8,3 2.4,3 2.5,3.1 2.5,4.4 2.3,4.6 1.8,5 1.3,5.1 0.8,5;2.3,4.6 2.6,4.6 2.6,5.1;2.4,1.3 2.3,0.7 2.2,0.5 1.9,0.3 1.1,0.2 0.8,0.4 0.5,0.7 0.3,1.6 0.3,3.7 0.5,4.6 0.8,5;0.5,0.7 0.5,0.9 0.5,0.7'),
    'H': (3.8, '0.3,0.763128 0.3,2.96313 0.3,5.36313;0.3,2.96313 2.4,2.96313;2.5,0.763128 2.4,2.96313 2.5,5.36313'),
    'I': (1.7, '0.3,5.36313 0.3,0.663128'),
    'J': (2.0, '0.8,5.1 0.3,5.2;0.8,5.1 1.1,4.7 1.1,4.2 1.1,0.3'),
    'K': (3.3, '1.2,2.86313 0.4,3.16313;1.2,2.86313 2,0.863128 2.3,0.463128 2.5,0.363128;1.2,2.86313 1.4,2.96313 2.4,5.36313;0.3,5.26313 0.3,3.36313 0.4,3.16313;0.4,3.16313 0.3,3.06313 0.3,0.663128'),
    'L': (2.7, '1.8,5.36313 0.4,5.36313 0.3,5.26313 0.3,0.663128'),
    'M': (4.4, '1.8,4.86313 2,4.66313 2.1,4.36313 2.2,4.16313 2.6,1.86313 2.9,1.66313 3.1,1.46313 3.1,0.563128;0.9,1.66313 0.5,1.46313;1.8,4.86313 1.6,4.66313 1.5,4.46313 1.5,4.26313 0.9,1.66313 0.4,0.663128;2.9,1.66313 3.1,1.56313 3.2,1.76313 3.2,5.26313;1.8,5.36313 1.8,4.86313 1.8,4.76313;0.5,1.46313 0.3,1.66313 0.3,5.36313'),
    'N': (3.5, '2.4,5.36313 2.2,4.26313 1.6,3.76313 1.2,2.66313 0.9,1.96313;2.2,4.26313 1.8,4.06313 1.6,3.76313 1.5,3.36313;2.2,4.26313 2.3,4.06313 2.3,0.663128;0.9,1.96313 0.4,1.76313 0.4,1.76313 0.2,0.663128;0.4,1.76313 0.3,1.86313 0.3,5.36313'),
    'O': (3.6, '0.8,5 0.6,4.8 0.4,4.5 0.3,3.7 0.3,1.6 0.5,0.7 0.8,0.4 1.2,0.2 1.7,0.2 2.2,0.4 2.2,0.4 2.5,0.9 2.5,1.2 2.5,4.1 2.3,4.8 2.1,5;2.1,5 1.5,5.1 0.8,5'),
    'P': (3.2, '0.3,2.96313 1.6,2.96313 1.9,2.76313 2.2,2.46313 2.3,1.76313 2.1,0.963128 1.9,0.763128 1.1,0.563128 0.5,0.563128 0.4,0.663128 0.3,0.763128 0.3,2.96313 0.3,5.36313'),
    'Q': (3.6, '0.8,5 0.6,4.8 0.4,4.5 0.3,3.7 0.3,1.6 0.5,0.7 0.8,0.4 1.2,0.2 1.7,0.2 2.2,0.4 2.2,0.4 2.5,0.9 2.5,1.2 2.5,4.1 2.3,4.8;2.5,6.1 2.1,5.7 1.9,5.4 1.9,5.1;0.8,5 1.4,5.1 1.9,5.1;1.9,5.1 2.3,4.8'),
    'R': (3.5, '1.7,2.6 1.8,3.4 2.1,4.4 2.3,5.1;1.9,0.4 2,0.4 1.9,0.4 1.6,0.3 0.5,0.2 0.4,0.3 0.3,0.4 0.3,2.6 0.3,5;1.7,2.6 2.1,2.2 2.3,1.4 2.1,0.7 1.9,0.4 1.9,0.5 1.9,0.4;0.3,2.6 1.7,2.6'),
    'S': (3.2, '2.2,4.8 1.8,5.1 1.3,5.1 0.9,5 0.6,4.7 0.3,4.2 0.4,4 0.4,3.9;2.2,4.8 2.3,4.5 2.3,3.7 2.1,3.4 0.8,2.2 0.4,1.6 0.3,1.2 0.3,0.8 0.7,0.4 1.2,0.2 1.8,0.4 2.1,0.7 2.2,1.2'),
    'T': (2.8, '1.3,0.663128 1.1,0.563128 0.3,0.563128;1.3,0.663128 1.2,5.36313;1.3,0.663128 1.4,0.563128 2.2,0.563128'),
    'U': (3.6, '0.3,0.3 0.3,4.1 0.4,4.6 0.7,4.9 0.9,5.1 1.3,5.1 1.9,5.1 2.1,4.9 2.3,4.6 2.5,3.7 2.5,0.3;2.4,4.3 2.3,4.6 2.1,5 2.3,4.7'),
    'V': (3.4, '1.5,5.36313 1.5,4.76313 1.6,4.56313 1.8,4.36313 2.3,1.96313 2.4,1.66313 2.6,0.563128;1.6,4.56313 1.4,4.56313 1.2,4.46313 1.1,4.26313 0.4,0.663128'),
    'W': (4.9, '1.2,5.36313 1.2,4.56313 1.3,4.46313 1.5,4.06313 1.9,1.76313 2.1,1.56313 2.4,1.76313 2.1,1.56313 2.2,0.663128;3.2,5.36313 2.9,4.26313 2.9,3.96313 2.8,3.76313 2.7,3.06313 2.6,2.56313 2.5,1.96313 2.4,1.76313 2.5,1.86313 2.6,2.56313 2.7,3.06313 2.7,2.86313 2.7,3.06313;3.3,4.46313 3.5,4.16313 3.6,3.46313 3.7,3.06313 4.1,0.563128;3.3,4.46313 3.1,4.46313 2.9,4.26313;0.3,0.663128 0.9,4.26313 1.1,4.46313 1.3,4.46313 1.5,4.36313 1.3,4.46313;2.9,3.96313 2.9,4.06313 2.8,3.76313;3.7,3.06313 3.7,3.16313 3.6,3.56313'),
    'X': (3.2, '0.6,0.663128 0.6,0.763128 0.8,1.36313 1,1.76313 1.3,2.26313 1.6,2.26313 1.7,2.26313 1.6,2.26313 1.2,2.16313 1,1.76313;2.5,0.363128 2.4,0.663128 1.9,1.86313 1.6,2.26313 1.5,2.46313 1.5,3.06313 1.4,3.26313 1.4,3.26313 2.2,4.46313;1.4,3.26313 1.1,3.36313 0.8,4.26313 0.6,4.76313 0.3,5.36313 0.3,5.36313;1.4,3.26313 1.7,3.36313'),
    'Y': (3.2, '1.6,3.26313 1.4,3.26313 1.2,3.06313 0.4,0.663128;1.5,5.36313 1.5,3.36313 1.6,3.26313 1.8,3.06313 1.9,2.86313 2.5,0.663128 2.7,0.463128;1.2,3.06313 1.2,3.16313 1.2,3.06313 1.6,3.16313'),
    'Z': (2.8, '2.1,5.36313 0.4,5.26313 0.4,4.76313 1.7,1.36313 1.9,0.563128;1.9,0.563128 1.8,0.463128 0.4,0.463128'),
    'a': (2.7, '0.3,2.5 0.4,2.4 0.5,2 0.7,1.8 1.2,1.7 1.5,1.8;1.8,3.2 1.1,3.4 0.7,3.7 0.5,3.9 0.3,4.4 0.4,4.9 0.7,5.1 0.9,5.1 1.4,4.9 1.8,4.7 1.8,4.8 1.9,5 1.8,4.7 1.8,3.2 1.8,2.2 1.5,1.8'),
    'b': (3.0, '1.8,2 1.5,1.8 0.9,1.9 0.3,2;1.8,2 2,2.9 2,4 1.8,4.9;0.3,0.3 0.3,2 0.4,4.9 0.4,5;0.4,4.9 1.5,5.1 1.8,4.9'),
    'c': (2.8, '0.6,1.9 1.1,1.7 1.5,1.9 1.7,2.1 1.8,2.6;0.6,1.9 0.3,2.6 0.3,4.4 0.4,4.7 0.6,5 0.8,5.1 1.4,5.1 1.6,5 1.6,5 1.8,4.3'),
    'd': (3.0, '0.5,2 0.8,1.8 1.9,2;0.5,2 0.3,2.6 0.3,4.4 0.5,4.9;1.9,0.3 1.9,2 1.9,5 0.8,5.1 0.5,4.9'),
    'e': (2.8, '0.3,3.3 1.6,3.3 1.7,3.2 1.8,3.1 1.8,2.3 1.6,1.9 1.6,1.9 1.2,1.7 0.6,1.9;0.6,1.9 0.5,2.1 0.3,2.6 0.3,3.3 0.4,4.7 0.6,5 0.8,5.1 1.4,5.1 1.6,5 1.6,5 1.8,4.4'),
    'f': (1.9, '1.7,1.06313 1.5,0.763128 1.1,0.763128 0.9,0.963128 0.8,1.36313 0.8,2.06313 0.8,5.36313;0.3,2.06313 0.8,2.06313 1.5,2.06313'),
    'g': (3.0, '0.5,6.2 0.3,5.9 0.5,5.4 0.7,5.1 0.6,4.9 0.4,4.7 0.7,4 0.7,3.7 0.7,3.7 1.5,4 1.8,3.7 2,3.2 2,2.1 2,2;0.6,4.9 1.7,5 2.1,5.2 2.3,5.4 2.3,5.8 2.1,6.1 1.7,6.3 0.8,6.3 0.5,6.2;0.7,3.7 0.5,3.4 0.4,2.9 0.6,2.2 0.9,1.8 1.6,1.8 2,2.1;2.6,1.8 2,2.1;0.6,4.8 0.6,4.9 0.5,5.4'),
    'h': (3.0, '1.7,2.26313 1.4,2.16313 0.7,2.46313 0.3,2.46313;1.9,5.36313 1.9,2.76313 1.7,2.26313 1.7,2.16313;0.3,0.663128 0.3,2.46313 0.3,5.36313'),
    'i': (1.5, '0.3,5.36313 0.3,2.26313;0.3,0.463128 0.3,1.46313'),
    'j': (1.5, '0.9,1.8 0.9,5.3 0.8,5.8 0.8,5.9 0.8,5.8 0.8,5.8 0.6,6 0.3,6;0.9,0.1 0.9,1.1'),
    'k': (2.9, '1.2,3.46313 1.4,2.96313 1.6,2.56313 2,1.96313 2.3,1.86313;0.3,5.26313 0.3,3.76313 0.3,0.563128;2,5.36313 1.2,3.46313;0.3,3.76313 1.2,3.46313'),
    'l': (1.5, '0.3,5.36313 0.3,0.663128'),
    'm': (4.6, '3.3,2.16313 3.1,2.06313 2.5,2.26313 2,2.46313 1.8,2.46313 1.7,2.16313 1.6,2.06313 1.2,2.06313 0.9,2.26313 0.6,2.36313 0.3,2.36313;3.3,2.16313 3.5,2.56313 3.5,5.36313;1.9,5.36313 1.9,2.66313 2,2.46313 1.7,2.16313;0.3,2.36313 0.3,5.36313'),
    'n': (2.9, '1.7,2.26313 1.4,2.16313 0.3,2.46313;1.7,2.26313 1.8,2.66313 1.8,5.36313;0.3,5.36313 0.3,2.46313 0.3,2.26313 0.3,2.36313'),
    'o': (2.8, '1.6,1.9 1.1,1.7 0.7,1.9 0.6,1.9 0.7,1.9;0.7,1.9 0.5,2.1 0.3,2.6 0.3,4.4 0.5,4.8 0.7,5.1 0.8,5.1 1.4,5.1 1.6,5;1.6,5 1.8,4.5 1.9,2.8 1.8,2.2 1.6,1.9'),
    'p': (3.0, '1.8,2 1.5,1.8 0.9,1.9 0.3,2;1.8,2 2,2.9 2,4 1.8,4.9;0.3,2 0.3,5 0.3,6.3;0.3,5 1.5,5.1 1.8,4.9'),
    'q': (3.0, '0.5,4.9 0.3,4.4 0.3,2.6 0.4,2.2 0.5,2 0.8,1.8 1.9,2;0.5,4.9 0.8,5.1 1.9,5;1.9,2 1.9,5 1.9,6.3'),
    'r': (2.2, '0.3,2.56313 0.8,2.56313 1.3,2.36313 1.5,2.06313;0.3,5.36313 0.3,2.56313 0.3,2.26313 0.3,2.56313'),
    's': (2.5, '1.7,2.4 1.7,2.1 1.6,1.9 1.6,1.9 1.4,1.8 1.1,1.7 0.7,1.9 0.4,2.2 0.4,2.7 0.8,3.1 1.5,3.7 1.8,4.1 1.8,4.5 1.7,4.9 1.6,5.1 1.3,5.1 0.9,5.1 0.6,5 0.6,5 0.4,4.7 0.4,4.5'),
    't': (2.1, '0.7,0.8 0.7,1.7 0.7,4.6 1,5.1 1.4,5.1;0.2,1.7 0.7,1.7 1.5,1.7'),
    'u': (2.9, '1.8,1.9 1.8,4.9;0.3,1.9 0.3,4.7 0.4,5 0.4,5 0.6,5.1 0.7,5.1 1.8,4.9'),
    'v': (2.6, '1.3,5.36313 1.1,5.36313 0.9,5.16313 0.6,3.56313 0.4,2.26313;2,2.26313 1.7,3.46313 1.5,5.16313 1.3,5.36313'),
    'w': (3.9, '3.2,2.16313 3.1,2.96313 2.8,4.56313 2.7,4.96313 2.7,4.96313 2.4,4.76313 2.3,4.56313 2,2.96313 1.9,2.86313 1.6,2.86313 1.6,2.86313 1.5,3.36313 1.2,4.76313 1,4.86313;2.6,5.36313 2.7,4.96313 2.8,4.86313 2.7,4.96313;0.3,2.16313 0.5,3.06313 0.8,4.76313 0.9,5.36313;0.8,4.76313 1,4.86313 1.2,4.86313 1,4.86313;1.6,2.86313 1.8,2.66313 1.8,2.26313;1,4.86313 1,4.96313 0.8,4.86313'),
    'x': (2.6, '1.1,3.76313 0.9,3.96313 0.4,5.06313 0.1,5.26313;2.4,5.36313 2,5.06313 1.1,3.86313 1.1,3.76313 1.2,3.16313 1.4,2.86313 2.1,1.66313 2.1,1.66313;1.1,3.76313 1.4,3.86313;1.4,2.86313 1.1,2.96313 0.9,2.86313 0.4,1.76313'),
    'y': (2.6, '1.3,4.6 1.5,4.4 1.6,3.9 1.8,2.7 2.1,1.7;1.3,4.6 1.1,4.6 1,4.5 0.5,2.5 0.4,1.8;1.3,4.6 1.1,5.9 0.4,6'),
    'z': (2.3, '1.6,5.36313 0.4,5.26313 0.5,4.76313 1.2,3.06313 1.3,2.86313 1.5,2.36313 1.4,2.06313 0.4,2.06313;1.2,3.06313 1.2,3.16313 1.3,2.86313'),
    '0': (3.5, '1.7,5.1 2,4.8 2.2,4.4 2.3,3.9 2.3,1.5 2.1,0.8 1.9,0.4 2.1,0.7;1.7,5.1 1.3,5.1 0.9,5.1;1.9,0.4 1.3,0.2 0.9,0.3 0.7,0.5 0.4,0.9 0.3,1.2 0.3,4.1 0.4,4.5 0.6,4.8 0.9,5.1'),
    '1': (2.5, '1.3,5.36313 1.3,0.963128 1.3,0.763128 1.3,0.863128;1.3,0.963128 0.2,1.16313'),
    '2': (3.2, '1.8,0.563128 2.1,0.863128 2.3,1.56313 2.2,2.26313 1.9,2.76313 1.5,3.46313 0.8,4.56313 0.5,5.16313 0.6,5.36313 2.2,5.36313;0.4,1.56313 0.4,1.16313 0.7,0.763128 1.1,0.463128 1.8,0.563128'),
    '3': (3.2, '1.7,5.1 2.1,4.7 2.3,3.9 2.1,3.2 1.9,2.8 1.7,2.6 1.9,2.2 2.2,1.7 2.2,0.9 2.1,0.7 1.8,0.3;1.7,5.1 1.2,5.1 0.7,5;1.9,2.2 1.7,2.3 1.9,2.2;0.7,5 0.4,4.6 0.3,4.2;1.8,0.3 1.2,0.2 0.8,0.4 0.5,0.6 0.5,0.6 0.3,1.2;1.7,5.1 1.7,5 2.1,4.7;1.9,2.8 1.9,2.9 2.1,3.2'),
    '4': (3.2, '1.7,0.863128 1.3,1.06313 1.3,1.26313 0.9,2.16313 0.5,3.06313 0.3,3.76313 0.4,3.96313 1.9,3.96313 2.5,3.96313;1.7,0.863128 1.9,0.963128 1.9,3.96313 1.9,5.36313'),
    '5': (3.2, '1.7,5.1 2.1,4.7;1.7,5.1 0.9,5.1 0.7,5 0.4,4.7 0.3,4.2;0.4,0.4 2,0.3;0.4,0.3 0.4,0.4 0.4,2.4 0.4,2.5;0.4,2.4 1.2,2.2 1.7,2.2 2.1,2.5 2.3,3.5 2.2,4.2 2.1,4.7'),
    '6': (3.4, '2.1,4.7 1.8,5 1.3,5.1 0.9,5.1 0.7,4.9 0.3,4 0.3,2.7 0.4,0.9 0.8,0.3 1.1,0.2 1.6,0.2 2,0.5 2.2,0.7;2.1,4.7 2.3,3.8 2.2,3.1 2.1,2.7 2.1,2.7 1.7,2.4 1,2.5 0.3,2.7;0.6,0.6 0.4,0.9;2.2,0.7 2.2,1'),
    '7': (2.6, '0.8,5.36313 1.7,0.963128 1.7,0.563128 0.3,0.463128'),
    '8': (3.3, '1.7,2.5 1.9,2.3 2.2,1.7 2.2,0.9 2.1,0.6 2.1,0.6 1.7,0.3 1.1,0.2 0.9,0.3 0.6,0.6 0.5,0.8 0.4,1.5 0.4,1.8 0.7,2.2 0.9,2.4 0.9,2.6 0.4,3.3 0.3,3.6 0.4,4.5 0.6,4.8 1,5.1 1.6,5.1 2,4.9 2.2,4.6 2.3,3.9 2.2,3.2 1.9,2.8 1.7,2.5;1.7,2.5 1.1,2.5 0.9,2.6 0.6,2.9'),
    '9': (3.4, '2.3,2.7 1.7,2.8 0.9,3 0.6,2.7 0.3,2.1 0.4,0.9 0.6,0.6 0.9,0.3 1.5,0.2 1.9,0.4 2.1,0.7 2.3,1.6 2.3,2.7 2.3,3.7 2.1,4.6 2.1,4.7 1.7,5.1 0.9,5.1 0.6,4.9 0.4,4.6 0.4,4.6 0.4,4.4;1.9,0.4 1.9,0.5 2.1,0.7'),
    'Ä': (3.3, '2.6,5.1 2.2,3.7 1.8,1 1.8,1 1.6,0.8 1.3,0.9 1.2,0.9 1.3,0.9;2.2,3.7 0.7,3.7;1.5,0.4 1.5,0.7 1.3,0.9 1.1,1.2 0.8,3.1 0.7,3.7 0.6,4 0.4,5.1 0.3,5.2;2.1,-1.7 2.1,-0.7;0.9,-1.7 0.9,-0.7'),
    'Ö': (3.6, '0.8,0.4 0.7,0.4 0.8,0.4 1.2,0.2 1.7,0.2 2.2,0.4 2.2,0.4 2.5,0.9 2.5,1.2 2.5,4.1 2.3,4.8 2.1,5;0.8,0.4 0.5,0.7 0.3,1.6 0.3,3.7 0.4,4.5 0.6,4.8 0.8,5;0.8,5 1.4,5.1 2.1,5;2,-1.7 2,-0.7;0.9,-1.7 0.9,-0.7'),
    'Ü': (3.6, '0.3,0.3 0.3,4.1 0.4,4.6 0.7,4.9 0.9,5.1 1.3,5.1 1.9,5.1 2.1,4.9 2.4,4.3 2.5,3.7 2.5,0.3;2.1,4.9 2.3,4.6 2.3,4.7 2.3,4.6;2,-1.7 2,-0.7;0.8,-1.7 0.8,-0.7'),
    'ä': (2.7, '0.3,2.5 0.4,2.4 0.5,2 0.7,1.8 1.2,1.7 1.5,1.8;1.8,3.2 1.1,3.4 0.7,3.7 0.5,3.9 0.3,4.4 0.4,4.9 0.7,5.1 0.9,5.1 1.4,4.9 1.8,4.7 1.8,4.8 1.9,5 1.8,4.7 1.8,3.2 1.8,2.2 1.5,1.8;0.6,-0.2 0.6,0.8;1.7,-0.2 1.7,0.8'),
    'ö': (2.8, '1.6,1.9 1.1,1.7 0.7,1.9 0.5,2.1 0.3,2.6 0.3,4.4 0.5,4.8 0.7,5.1 0.8,5.1 1.4,5.1 1.6,5;1.6,5 1.8,4.5 1.9,2.8 1.8,2.2 1.6,1.9;0.5,-0.2 0.5,0.8;1.7,-0.2 1.7,0.8'),
    'ü': (2.9, '1.8,4.9 1.8,1.9;1.8,4.9 0.7,5.1 0.6,5.1 0.4,5 0.4,5 0.3,4.7 0.3,1.9;0.6,-0.2 0.6,0.8;1.7,-0.2 1.7,0.8'),
    'ß': (3.5, '1.3,5.1 1.6,5.1 1.8,5 2.1,4.6 2.3,3.9 2.1,3.2 1.9,2.8 1.9,2.8 1.8,2.1 1.8,2.1 2.1,1.7 2.1,0.8 1.9,0.6 1.6,0.3 1,0.2 0.7,0.3 0.4,0.8 0.3,5;1.9,2.8 1.5,2.6'),
    '-': (2.0, '1.2,3.4 0.3,3.4'),
    '.': (1.3, '0.3,4.36313 0.3,5.36313'),
    ',': (1.3, '0.3,5 0.5,5.2 0.5,5.6 0.4,5.9 0.2,6'),
    ':': (1.3, '0.3,1.8 0.3,2.8;0.3,3.9 0.3,4.9'),
    ';': (1.4, '0.3,5.4 0.5,5.2 0.5,4.7 0.3,4.5;0.3,1.5 0.3,2.5'),
    '!': (1.4, '0.3,0.163128 0.3,3.86313;0.3,4.36313 0.3,5.36313'),
    '?': (3.2, '0.3,1.06313 0.5,0.363128 0.5,0.363128 0.8,0.163128 1.5,0.0631285 1.7,0.163128 1.9,0.363128 2.1,0.563128 2.1,0.563128 2.2,1.16313 2.1,1.76313 2,2.06313 1.7,2.46313 1.2,2.96313 1.1,3.06313 1,3.56313;1,4.36313 1,5.36313'),
    '+': (2.8, '1.2,1.6 1.2,2.6 1.2,3.7;0.3,2.6 1.2,2.6 2.1,2.6'),
    '*': (2.7, '0.6,1.9 0.8,1.3 1.1,1.2 1.7,0.9;0.4,0.9 1.1,1.2 1.3,1.3 1.5,1.8 1.6,2;1.1,0.2 1.1,1.2 1.1,1.2'),
    '/': (2.5, '0.4,5.36313 0.5,4.76313 0.7,4.06313 0.9,3.46313 0.9,3.26313 1.1,2.46313 1.3,2.06313 1.3,1.86313 1.5,1.16313 1.6,0.763128 1.7,0.563128 1.6,0.763128 1.4,1.46313 1.3,1.86313;0.7,4.16313 0.8,3.86313 0.9,3.46313 0.9,3.46313;1.1,2.46313 1.1,2.66313 1.1,2.46313;1.5,1.16313 1.5,1.26313 1.4,1.46313'),
    '(': (2.0, '1,6.4 0.6,6 0.3,5 0.3,1.6 0.4,0.9 0.7,0.5 1,0.2'),
    ')': (1.7, '0.2,0.2 0.4,0.3 0.7,0.6 0.9,1.3 0.9,4.5 0.9,5.2 0.7,5.9 0.6,6.1 0.2,6.4'),
    '[': (2.3, '1.2,0.2 0.4,0.2 0.4,0.2 0.3,0.4 0.3,6.3 0.5,6.4 1.2,6.4'),
    ']': (2.1, '0.2,0.2 0.9,0.2 1.1,0.3 1.1,6.2 1,6.3 0.9,6.4 0.2,6.4'),
    '=': (2.8, '1.7,3.2 0.3,3.2;1.7,2 0.3,2'),
    '%': (6.0, '3.4,0.4 3.5,0.2 3.4,0.4 3.2,0.9 3.1,1.3 3,1.6 2.8,2.3 2.7,2.9 2.6,3.2 2.5,3.6 2.4,3.9 2.3,4.2 2.2,4.6 2.1,5 2,5.3 2.1,5.1 2.2,4.6 2.3,4.2 2.4,3.9 2.5,3.6 2.6,3.2 2.7,2.9 2.8,2.3 3,1.6;4.8,2.9 4.4,2.8 4.1,2.8 3.9,3.1 3.7,3.3 3.7,3.7 3.7,4.2 3.9,4.9 4.2,5.1 4.6,5.1 4.8,5.1 5,4.8 5.1,3.5 4.8,2.9;0.5,0.4 0.4,0.6 0.3,1.7 0.5,2.3 0.8,2.6 1.3,2.6 1.5,2.4 1.7,2 1.6,0.6 1.5,0.4 1.5,0.3;0.5,0.4 1,0.2 1.5,0.4'),
    '#': (3.3, '1.7,5.36313 2,3.46313 2.2,2.36313 2.4,0.663128;2.5,3.46313 2,3.46313 0.7,3.46313 0.3,3.46313;1.1,0.663128 0.8,2.36313 0.7,3.46313 0.4,5.36313;0.3,2.36313 0.8,2.36313 2.2,2.36313 2.5,2.36313'),
    '&': (4.1, '2.8,3.2 2.6,4 2.2,4.5 1.6,5.1 0.8,5.1 0.5,4.9 0.5,4.9 0.3,4.4 0.4,3.7 0.6,3.3 0.8,3 1.1,2.9 1.7,2.1 2,1.5 2.1,0.7 1.9,0.4 1.6,0.2 1.2,0.2 0.9,0.3 0.7,0.6 0.6,1.3 0.9,2.3 1.1,2.6 1.3,2.5 1.5,2.5 1.3,2.5;2.2,4.5 2.6,4.7 2.8,4.9 3,5;1.1,2.9 1.2,3 1.7,3.6 2.2,4.3 2.2,4.5 2.2,4.6 2.6,4.8;1.1,2.9 1.3,2.5;1.7,3.6 1.3,3 1.7,3.6'),
    '@': (6.1, '3.6,1.8 2.7,1.7 2.4,1.9 2.1,2.2 1.8,3 1.7,3.5 1.9,4 2,4.3;3.7,5.9 3.4,6 2.2,6 1.6,5.8 1,5.4 0.5,4.7 0.3,3.7 0.4,2.4 0.8,1.4 1.4,0.8 2.1,0.4 2.5,0.3 3.5,0.3 4.2,0.6 4.7,1.2 4.9,1.6 5,2 5.1,2.8 5,3.5 4.8,3.9 4.3,4.4;2,4.3 2.2,4.4 2.5,4.4 2.8,4.3 3.2,4.1 3.4,3.9 3.6,1.8 3.7,1.6;3.2,4.1 3.4,4.1 3.5,4.4 3.7,4.5 4.3,4.4'),
    '°': (3.0, '1.9,1.5 2,0.8 1.8,0.5 1.5,0.2 1.2,0.2 0.8,0.2 0.5,0.5 0.3,0.7 0.2,1.1 0.3,1.5 0.6,1.8 1.1,2 1.6,1.8 1.9,1.5'),
    "'": (0.9, '0.2,1.4 0.2,0.3'),
    '<': (2.5, '1.6,3.5 0.8,3 0.3,2.7 0.3,2.4 0.3,2.3 0.3,2.4 0.3,2.5;0.3,2.4 0.8,2.1 1.6,1.7;0.8,3 0.3,2.8 0.8,3'),
    '>': (2.5, '1.5,2.4 1,2.1 0.2,1.7;0.1,3.7 0.3,3.4 1.1,3 1.5,2.8;1.5,2.4 1.6,2.6 1.5,2.8 1.1,3.1;0.1,3.7 0.2,3.5 0.1,3.7'),
    '_': (2.3, '0.3,6 2,6'),
    ' ': (3.0, ''),
}

FONT_META_NARROW = {'cap': 5.92, 'xheight': 4.37, 'desc': 1.76, 'height': 7.68}
FONT_NARROW = {
    'A': (4.9, '2.1,0.815493 1.9,0.815493 2.1,0.815493 2.3,0.815493 2.5,1.01549 3.2,3.31549 3.3,4.01549;2.1,0.815493 1.8,1.01549 1.2,3.11549 1,4.11549 1,4.11549 0.8,4.21549 0.5,5.41549 0.3,5.71549;2.1,0.815493 2.2,0.415493 2.1,0.715493;3.3,4.01549 3.5,4.21549 3.9,5.61549 4.4,5.91549;3.3,4.01549 3.2,4.11549 1,4.11549'),
    'B': (4.6, '0.4,0.615493 2.1,0.615493 2.3,0.715493 2.7,1.01549;2.7,1.01549 3,1.81549 2.8,2.41549 2.4,3.01549 2.4,3.01549 2.5,3.31549 2.8,3.61549 3,4.11549 3,5.01549 2.9,5.41549 2.9,5.41549 2.5,5.71549 1.9,5.91549 0.4,5.91549 0.4,3.11549 0.4,0.615493;2.4,3.01549 0.4,3.11549'),
    'C': (4.8, '3.4,4.5 3.5,4.4 3.4,4.6 3.2,5.2 2.9,5.4 2.5,5.6 1.8,5.7 1.4,5.6 1,5.3 0.5,4.6 0.4,4 0.4,1.9 0.6,1.1 1,0.6 1.6,0.2 2.5,0.2 2.9,0.5 3.3,1 3.4,1.3 3.5,1.5 3.4,1.4'),
    'D': (4.8, '0.4,0.615493 1.8,0.615493 2.6,1.01549 3,1.51549 3.2,2.61549 3.2,4.01549 3,5.01549 2.6,5.51549 1.9,5.81549 1.5,5.91549 0.4,5.91549 0.4,0.615493'),
    'E': (4.2, '0.4,0.615493 0.4,3.21549 0.4,5.91549 2.8,5.91549;0.4,3.21549 2.5,3.21549;0.4,0.615493 2.8,0.615493'),
    'F': (4.1, '0.4,3.41549 2.4,3.41549;0.4,0.715493 0.4,3.41549 0.4,5.91549;0.4,0.715493 2.7,0.715493'),
    'G': (5.0, '3.3,5.3 2.7,5.6 1.8,5.7 1,5.3 0.6,4.8 0.4,4 0.4,1.8 0.6,1 1,0.5 1.5,0.2 2.5,0.2 2.9,0.4 3.2,0.8 3.4,1.3;3.3,5.3 3.5,4.9 3.5,3.4 2.3,3.3'),
    'H': (5.2, '0.4,0.815493 0.4,3.31549 0.4,5.91549;0.4,3.31549 3.5,3.31549;3.5,5.91549 3.5,3.31549 3.5,0.815493'),
    'I': (2.1, '0.4,0.815493 0.4,5.91549'),
    'J': (4.1, '2.8,0.4 2.8,4.6 2.6,5.1 2.3,5.6 1.5,5.7 0.8,5.5 0.5,5.1 0.4,4.6'),
    'K': (4.6, '1.4,2.91549 0.7,3.11549 0.4,3.31549;1.4,2.91549 1.7,2.11549 1.9,1.81549 3.1,0.215493 3.6,0.015493;1.4,2.91549 1.6,3.01549 1.4,2.91549;1.4,2.91549 1.8,3.21549 2.3,4.11549 2.9,5.01549 3.3,5.71549 3.8,5.91549;0.4,5.51549 0.4,3.41549 0.4,3.31549 0.4,3.21549 0.4,0.415493;3.4,0.115493 3.1,0.215493;0.7,3.11549 0.7,3.21549 0.4,3.31549'),
    'L': (4.0, '0.4,0.715493 0.4,5.91549 2.7,5.91549'),
    'M': (6.4, '4.5,0.815493 4.5,1.21549 4.2,1.51549 3.9,1.91549 2.9,5.11549 2.6,5.41549 2.5,5.71549 2.6,5.51549;2.6,5.41549 2.3,5.41549 2.2,5.21549 1,1.51549 1,1.51549 0.6,1.31549 0.4,1.31549;4.2,1.51549 4.6,1.61549 4.6,5.91549;0.4,5.81549 0.3,1.51549 0.4,1.31549 0.5,0.915493'),
    'N': (5.2, '2.6,4.61549 2.6,4.71549 2.8,5.11549 2.6,4.71549 1.8,3.11549 1.1,1.71549 1.1,1.71549 0.6,1.41549 0.4,1.41549;2.6,4.71549 3,5.21549 3.4,5.31549 3.4,5.31549 3.5,5.81549;0.4,5.91549 0.4,1.41549 0.4,0.815493;3.4,5.31549 3.5,5.21549 3.5,0.815493'),
    'O': (5.1, '2.9,5.5 2.3,5.7 1.5,5.6 0.9,5.3 0.9,5.3 0.6,4.8 0.5,4.3 0.4,3.9 0.4,2 0.5,1.6 0.6,1.1 0.9,0.7 1.3,0.4 1.7,0.2 2.3,0.2 2.9,0.5 3.2,0.8 3.6,1.5 3.7,3.5 3.6,4.4 3.3,4.9 2.9,5.5'),
    'P': (4.7, '0.4,5.91549 0.4,3.71549 0.4,0.715493;0.4,0.715493 2.3,0.715493 2.8,1.01549 3.1,1.31549;0.4,3.71549 2,3.71549 2.4,3.61549 2.7,3.51549 3.1,3.11549;3.1,1.31549 3.3,2.21549 3.1,3.11549 3.1,3.21549'),
    'Q': (5.1, '2.9,5.6 1.8,5.7 1.3,5.6 1,5.3 0.5,4.7 0.4,4.1 0.4,1.8 0.5,1.2 1,0.6 1.4,0.3 2.1,0.2 2.6,0.3 3,0.6 3.3,1.1 3.6,2.1 3.6,3.8 3.5,4.4 3.2,5.1 2.9,5.6 2.9,5.7 3,5.9 3.3,6.2'),
    'R': (4.5, '0.4,0.615493 2.1,0.615493 2.5,0.815493 2.8,1.11549 3,1.61549 3,2.61549 2.9,2.91549 2.6,3.21549 2.2,3.51549;2.2,3.51549 2.2,3.81549 2.5,4.61549 3,5.61549 3.1,5.91549;0.4,5.81549 0.4,3.51549 0.4,0.615493;0.4,3.51549 2.2,3.51549'),
    'S': (4.4, '3.2,1.3 3.2,1.1 2.9,0.6 2.3,0.2 1.4,0.2 0.9,0.5 0.6,0.8 0.5,1.3 0.5,1.7 0.8,2.2 1.3,2.7 2.5,3.2 3,3.6 3.2,3.9 3.2,4.5 3.2,4.9 2.9,5.3 2.5,5.6 2.1,5.7 1.3,5.6 0.9,5.4 0.5,4.9 0.4,4.6 0.5,4.8'),
    'T': (4.4, '0.3,0.715493 2,0.715493 3.5,0.715493;2,0.715493 2,5.91549'),
    'U': (4.7, '2.8,5.4 2,5.7 1.2,5.6 0.8,5.5 0.8,5.5 0.5,5 0.3,4.4 0.3,0.4;2.8,5.4 3.1,5 3.2,4.3 3.2,0.4'),
    'V': (4.7, '3.7,0.915493 4,0.615493 3.7,0.915493 3.6,1.41549 2.7,4.21549 2.6,4.81549 2.2,5.51549 2.1,5.91549;2.2,5.51549 1.8,5.41549 1.4,4.01549 1.2,3.41549 0.7,1.51549 0.5,1.01549 0.5,0.815493 0.5,0.915493'),
    'W': (6.4, '4.4,5.41549 4.6,5.31549 4.4,5.41549 4.4,5.41549 4.4,5.31549;4.4,5.91549 4.4,5.41549 4.6,5.01549 5.4,1.01549 5.4,0.715493 5.4,1.01549;4.4,5.41549 4,5.21549 4,4.91549 3.2,1.61549 3.1,1.51549 2.8,1.51549;3,0.715493 3,1.21549 2.8,1.51549 2.6,1.71549 2,4.71549 1.7,5.21549 1.5,5.51549 1.5,5.91549;4,4.91549 3.9,4.61549 3.9,4.51549;1.7,5.21549 1.4,5.31549 1.2,5.11549 0.5,1.21549 0.5,0.915493 0.4,0.715493'),
    'X': (4.7, '1.9,3.41549 2.1,2.71549 2.4,2.41549 2.9,1.41549 3.4,0.415493 3.4,0.315493;0.6,0.415493 1,1.21549 1.7,2.51549 1.9,2.71549 2.1,2.71549 2.1,2.71549 2.1,2.61549;3.8,0.215493 3.4,0.415493;3.7,5.91549 3.4,5.71549 2.6,4.21549 2.3,3.51549 2.6,4.21549 2.6,4.21549 2.2,3.51549 1.9,3.41549;0.3,5.81549 0.6,5.71549 1.3,4.31549 1.6,3.61549 1.9,3.41549;1.9,3.41549 1.7,3.51549 1.9,3.41549'),
    'Y': (4.4, '3.9,0.515493 3.6,0.715493 3,1.81549 2.4,3.41549 2,3.71549;0.5,0.715493 0.8,1.41549 1,1.81549 1.2,2.41549 1.8,3.51549 2,3.71549 2,3.71549 2,5.91549'),
    'Z': (4.4, '0.4,0.615493 3.1,0.715493 2.8,1.51549 0.8,4.91549 0.4,5.81549 0.4,5.91549;0.4,5.81549 3.3,5.91549'),
    'a': (4.0, '2.4,5.3 1.8,5.5 1.3,5.7 0.8,5.6 0.4,5.3 0.3,4.9 0.4,4.3 0.6,4 1.2,3.6 2.5,3.5;2.4,5.3 2.5,5.1 2.5,3.5 2.5,2.4 2.3,2;2.4,5.3 2.6,5.6;2.3,2 1.9,1.8 1.2,1.8 0.8,1.9 0.6,2.2 0.4,2.5'),
    'b': (4.2, '2,1.8 2.5,2.2 2.7,2.7 2.8,4 2.7,4.8 2.6,5.1 2.1,5.6;0.3,5.5 0.3,5.3 0.3,2.3 0.3,0;0.3,5.3 1.6,5.7 2.1,5.6;2,1.8 1.2,1.8 0.8,2.1 0.3,2.3'),
    'c': (3.9, '0.8,5.5 0.4,4.9 0.3,4.3 0.4,2.8 0.6,2.3 0.8,2 1.2,1.8 2,1.8 2.3,2 2.6,2.3 2.7,2.7;0.8,5.5 1.5,5.7 2.2,5.6;2.2,5.6 2.6,5.1 2.7,4.9 2.6,5.1'),
    'd': (4.2, '2.8,2.1 2.3,2 1.8,1.8 1.2,1.8 0.8,2 0.8,2 0.5,2.5 0.4,3.1 0.4,4.4 0.5,5 0.8,5.4 1.1,5.6 1.6,5.7 2.8,5.3;2.8,5.3 2.8,2.1 2.8,0;2.8,5.3 2.9,5.4 2.9,5.6'),
    'e': (4.0, '2.7,5.4 2.3,5.6 1.9,5.7 1.1,5.6 0.9,5.5 0.4,4.9 0.3,3.7 0.4,2.6 0.7,2.2 1,1.9 1.3,1.8 2,1.8 2.3,2 2.5,2.2 2.7,2.7 2.7,3.7 0.3,3.7'),
    'f': (2.7, '0.3,2.21549 0.9,2.21549 1.8,2.21549;1.9,0.315493 1.4,0.315493 1.1,0.715493 0.9,1.21549 0.9,2.21549 0.9,5.91549'),
    'g': (4.2, '2.8,5.4 1.5,5.7 1.1,5.6 0.8,5.4 0.5,5 0.3,4.3 0.3,3.2 0.6,2.3 1.1,1.8;0.6,7.1 1.1,7.3 2,7.3 2.4,7.1 2.4,7.1 2.6,6.7 2.8,5.4 2.8,2.3 2.8,1.9 2.8,2.2;2.8,2.3 2.2,2 1.7,1.8 1.1,1.8'),
    'h': (4.1, '2,2.11549 1.5,2.11549 1,2.31549 0.4,2.51549 0.4,2.51549 0.3,2.71549 0.3,5.91549;0.4,2.51549 0.3,2.41549 0.3,0.315493;2.4,2.41549 2,2.11549;2.4,2.41549 2.5,2.81549 2.5,5.91549'),
    'i': (1.9, '0.4,2.21549 0.4,5.91549;0.4,0.115493 0.4,1.11549'),
    'j': (1.9, '0.3,7.3 0.7,7.3 0.8,7 0.9,6.9 0.9,1.9;0.9,-0.2 0.9,0.8'),
    'k': (3.8, '3,5.91549 2.6,5.71549 2.6,5.71549 1.7,4.21549 1.4,3.91549 1.2,3.61549 1.2,3.61549 1.4,3.01549 2,2.21549 2.6,1.61549 2.7,1.61549;0.3,5.61549 0.4,3.81549 0.4,3.71549;1.2,3.61549 0.4,3.81549;0.4,3.81549 0.3,3.71549 0.3,0.015493'),
    'l': (1.9, '0.3,0.315493 0.3,5.91549'),
    'm': (6.4, '2.5,5.91549 2.5,3.11549 2.6,2.81549 2.9,2.51549 3.4,2.11549 4.2,2.11549;2.9,2.51549 2.5,2.61549 2.1,2.21549 1.8,2.11549 1.4,2.11549 1,2.21549 0.3,2.51549;0.3,2.21549 0.3,2.51549 0.3,5.91549;4.2,2.11549 4.6,2.41549 4.8,2.81549 4.9,3.51549 4.9,5.81549'),
    'n': (4.1, '0.4,2.51549 0.3,2.21549 0.4,2.51549;0.4,2.51549 0.3,2.71549 0.3,5.91549;0.4,2.51549 1,2.31549 1.5,2.11549 2,2.11549;2,2.11549 2.4,2.41549;2.4,2.41549 2.5,2.81549 2.5,5.91549'),
    'o': (4.2, '2.3,5.6 1.5,5.7 0.9,5.5 0.4,4.9 0.3,4.2 0.3,3.2 0.5,2.5 0.9,2 1.3,1.8 2,1.8 2.5,2.1 2.8,2.5 3,3.5 2.9,4.9 2.7,5.2 2.3,5.6;2.5,2 2.5,2.1 2.8,2.5;2.9,4.8 2.9,4.9 2.7,5.3'),
    'p': (4.2, '0.3,1.8 0.3,2.2 0.3,5.4 0.3,7.3;0.3,2.2 0.9,2 1.4,1.8 2.1,1.8;2.1,1.8 2.5,2.2 2.7,2.7 2.8,3.5 2.7,4.7 2.5,5.2 2.3,5.6 1.8,5.7 1,5.5 0.3,5.4'),
    'q': (4.2, '0.5,2.5 0.5,2.7 0.5,2.5 0.5,2.7 0.4,4.4 0.5,5 0.8,5.4 1.4,5.7 2.2,5.5 2.7,5.4 2.7,5.4 2.8,5.2 2.8,2.1 2.9,1.8 2.8,2.1;2.8,2.1 2.2,1.9 1.8,1.8 1.2,1.8 0.7,2.2 0.5,2.5;2.7,5.4 2.8,5.5 2.8,7.3'),
    'r': (2.6, '1.5,2.11549 0.4,2.61549;0.3,2.21549 0.4,2.61549 0.3,5.91549'),
    's': (3.9, '2.3,2.1 1.8,1.8 0.9,1.9;2.3,5.5 2.5,5.1 2.5,4.3 2.2,4 0.8,3.3 0.5,3 0.4,2.7 0.5,2.3 0.9,1.9;0.4,4.9 0.4,5 0.7,5.5 0.7,5.5 1.3,5.7 2.3,5.5'),
    't': (2.5, '0.3,1.8 1,1.8 1.8,1.8;1,0.8 1,1.8 1,4.9 1.1,5.4 1.3,5.6 1.7,5.7'),
    'u': (4.1, '0.3,1.9 0.3,4.6 0.5,5.3 0.7,5.6 1.1,5.7 1.8,5.5 2.5,5.3;2.5,5.6 2.5,5.3 2.5,1.9'),
    'v': (3.6, '1.5,5.91549 1.6,5.41549 1.9,4.91549 2,4.61549 2.5,2.91549 2.6,2.51549 2.7,2.11549 2.8,2.11549;1.6,5.41549 1.3,5.31549 1.3,5.31549 1.2,5.01549 0.6,2.91549 0.4,2.21549;0.5,2.61549 0.6,2.91549 0.5,2.71549'),
    'w': (5.5, '1.5,5.11549 1.2,5.11549 1,4.91549 0.7,3.71549 0.7,3.41549 0.4,2.11549;3.7,5.21549 3.9,5.01549 4.3,3.11549 4.4,2.81549 4.6,2.11549;3.3,5.11549 3.7,5.21549 3.7,5.21549 3.7,5.31549;3.7,5.81549 3.7,5.21549 3.3,4.81549 2.8,3.01549 2.6,2.81549 2.4,2.81549;2.5,2.31549 2.4,2.81549 2.1,3.21549 2,3.71549 1.9,4.01549 1.7,4.71549 1.5,5.11549 1.7,4.81549;1.5,5.11549 1.3,5.21549 1.3,5.91549'),
    'x': (3.7, '0.2,5.91549 0.6,5.71549 1.3,4.31549 1.5,4.11549;2.8,5.91549 2.6,5.71549 2.1,4.71549 1.9,4.31549 1.5,3.71549 1.8,3.41549 2.5,2.01549 2.9,1.71549;0.6,1.91549 1,2.81549 1.4,3.41549 1.5,3.51549 1.8,3.41549 1.8,3.41549 1.8,3.31549;1.5,4.11549 1.9,4.31549'),
    'y': (3.5, '0.5,1.8 1,3.7 1.6,5 1.4,6.5 1.3,6.9 0.9,7.2 0.5,7.3;2.8,1.7 2.7,1.8 2.3,3.2 2.2,3.5 1.9,4.8 1.6,5;1.6,5 1.8,4.9 1.6,5;1.3,4.8 1.6,5 1.6,5 1.6,4.9'),
    'z': (3.7, '0.4,2.11549 2.4,2.21549 2.3,2.81549 1.5,4.01549 0.6,5.31549 0.6,5.91549 2.6,5.91549'),
    '0': (4.2, '0.9,5.5 0.4,4.4 0.3,3.9 0.3,1.9 0.4,1.5 0.5,1.1 0.8,0.5 1.2,0.2 1.9,0.2 2.3,0.5 2.5,0.8 2.7,1.4 2.8,3.2 2.7,4.4 2.6,4.9 2.3,5.4 2.3,5.5;2.3,5.4 1.7,5.7 0.9,5.5;0.5,4.8 0.4,4.4 0.4,4.3'),
    '1': (4.2, '0.2,1.51549 0.6,1.21549 1.1,1.01549 1.6,1.01549;1.8,0.615493 1.6,1.01549 1.6,5.91549'),
    '2': (4.2, '0.3,1.81549 0.5,1.21549 0.9,0.815493 1.3,0.515493 2,0.515493 2.6,1.01549 2.8,1.41549 2.7,2.51549 2.3,3.31549 1.9,3.81549 1.5,4.41549 1,5.01549 0.8,5.41549 0.7,5.81549 0.7,5.91549;3.1,5.91549 0.8,5.91549 0.7,5.81549'),
    '3': (4.2, '0.4,1.2 0.4,0.9 0.8,0.4 1.2,0.2 1.9,0.2 2.3,0.4 2.3,0.4 2.7,1.1 2.7,1.9 2.3,2.5 2,2.9;0.4,4.7 0.4,5.1 0.8,5.5 1.4,5.7 2.3,5.5 2.3,5.5 2.7,4.8 2.7,3.9 2.5,3.4 2.2,3.1 2,2.9;1.3,2.9 2,2.9;2.6,3.7 2.5,3.4 2.6,3.6'),
    '4': (4.2, '2.6,5.91549 2.6,4.51549 2.6,1.11549 2.4,1.11549 1.9,1.41549 1.7,1.81549 0.7,3.81549 0.5,4.41549 0.6,4.51549 2.6,4.51549 3.3,4.51549;2.6,0.715493 2.4,1.11549 2.4,1.21549'),
    '5': (4.2, '0.6,2.5 2,2.4 2.4,2.7 2.8,3.5 2.8,4.6 2.6,5 2.1,5.6 1.8,5.7 1,5.6;0.6,2.5 0.7,0.4 0.7,0.4 0.8,0.3 2.7,0.3;1,5.6 0.6,5.2 0.4,4.8;2.4,5.4 2.6,5'),
    '6': (4.2, '2.1,0.3 1.6,0.4 1.1,0.7 0.7,1.1 0.5,1.8 0.4,2.8 0.3,4 0.5,4.9 0.9,5.4 1.1,5.6 1.5,5.7 2.2,5.5 2.4,5.3 2.7,4.6 2.7,3.4 2.6,3 2,2.3 1.2,2.4 0.4,2.8'),
    '7': (4.2, '2.9,0.515493 2.8,1.31549 1.5,4.61549 1.2,5.51549 1.1,5.91549 1.2,5.51549 1.2,5.51549;2.9,0.515493 0.3,0.515493'),
    '8': (4.2, '1.1,2.9 0.8,2.5 0.4,1.7 0.5,0.9 0.9,0.4 1.3,0.2 1.9,0.2 2.2,0.4 2.5,0.8 2.6,1 2.6,2 2.5,2.3 2.2,2.7 2,2.9 1.1,2.9;1.1,2.9 0.8,3.2 0.5,3.5 0.4,3.9 0.3,4.3 0.4,4.8 0.8,5.5 0.8,5.5 1.4,5.7 2.2,5.6;2.2,5.6 2.5,5.3 2.6,5 2.7,3.9 2.6,3.5 2.3,3.2 2.2,3.1 2.2,2.7;2.2,0.4 2.2,0.5 2.5,0.8'),
    '9': (4.2, '1,5.91549 1.3,5.81549 1.6,5.81549 2.2,5.31549 2.6,4.71549 2.7,3.41549 2.7,1.81549 2.6,1.41549 2.4,0.915493 2.1,0.715493 1.8,0.515493 1.3,0.515493 0.9,0.815493 0.4,1.41549 0.3,2.11549 0.5,3.31549 0.5,3.31549 0.9,3.71549 1.4,3.91549 2,3.71549 2.7,3.41549'),
    'Ä': (4.9, '2.1,0.815493 2.2,0.415493 2.1,0.715493;3.3,4.01549 3.2,3.31549 2.5,1.01549 2.3,0.815493 2.1,0.815493 1.9,0.815493 2.1,0.815493;2.1,0.815493 1.8,1.01549 1.2,3.11549 1,4.11549 1,4.11549 0.8,4.21549 0.5,5.41549 0.3,5.71549;1,4.11549 3.2,4.11549 3.3,4.01549;4.4,5.91549 3.9,5.61549 3.5,4.21549 3.3,4.01549;3.1,-1.48451 3.1,-0.484507;1.3,-1.48451 1.3,-0.484507'),
    'Ö': (5.1, '2.9,5.5 3.3,4.9 3.6,4.4 3.7,2.4 3.6,1.5 3.2,0.8 2.9,0.5 2.3,0.2 1.7,0.2 1.3,0.4 0.9,0.7 0.6,1.1 0.5,1.6 0.4,2 0.4,3.9 0.5,4.3 0.6,4.8 0.9,5.3 0.9,5.3 1.5,5.6 2.3,5.7 2.9,5.5;2.9,-1.5 2.9,-0.5;1.1,-1.5 1.1,-0.5'),
    'Ü': (4.7, '2.8,5.4 3.1,5 3.2,4.3 3.2,0.4;2.8,5.4 2,5.7 1.2,5.6 0.8,5.5 0.8,5.5 0.5,5 0.3,4.4 0.3,0.4;2.7,-1.5 2.7,-0.5;0.9,-1.5 0.9,-0.5'),
    'ä': (4.0, '2.3,2 1.9,1.8 1.2,1.8 0.8,1.9 0.6,2.2 0.4,2.5;2.6,5.6 2.4,5.3;2.4,5.3 1.8,5.5 1.3,5.7 0.8,5.6 0.4,5.3 0.3,4.9 0.4,4.3 0.6,4 1.2,3.6 2.5,3.5;2.3,2 2.5,2.4 2.5,3.5 2.5,5.1 2.4,5.3;0.7,-0.2 0.7,0.8;2.5,-0.2 2.5,0.8'),
    'ö': (4.2, '0.9,5.5 0.5,5 0.3,4.2 0.3,3.2 0.4,2.6 0.9,2 1.3,1.8 2,1.8 2.5,2.1 2.8,2.5 3,3.5 2.9,4.9 2.7,5.2 2.3,5.6;0.9,5.5 1.5,5.7 2.3,5.6;2.5,2 2.5,2.1 2.8,2.5;2.7,5.3 2.7,5.2 2.9,4.8;0.8,-0.2 0.8,0.8;2.5,-0.2 2.5,0.8'),
    'ü': (4.1, '2.5,5.3 1.8,5.5 1.1,5.7 0.7,5.6 0.5,5.3 0.3,4.6 0.3,1.9;2.5,1.9 2.5,5.3 2.5,5.6;0.6,-0.2 0.6,0.8;2.3,-0.2 2.3,0.8'),
    'ß': (4.4, '0.3,5.6 0.3,1.1 0.4,0.5 0.8,0.1 1.1,-0.1 1.7,-0.1 1.9,0 2.2,0.4 2.3,1.3 1.9,2.5 2,3 2.1,3.2 2.4,3.6 2.9,4.1 3,4.4 3,5.1 2.8,5.4 2.6,5.6 2.3,5.7 1.5,5.6;2.1,3.2 2.1,3.3 2.4,3.6'),
    '-': (2.1, '1.3,3.4 0.3,3.4'),
    '.': (2.2, '0.5,5.1 0.5,6.1'),
    ',': (1.7, '0.7,5.4 0.6,6.4 0.4,6.8'),
    ':': (2.0, '0.5,1.4 0.5,2.4;0.5,5.1 0.5,6.1'),
    ';': (1.7, '0.7,5.4 0.6,6.4 0.4,6.8;0.7,1.4 0.7,2.4'),
    '!': (2.1, '0.4,3.9 0.4,0.4;0.4,5.1 0.4,6.1'),
    '?': (3.6, '1.1,0.2 0.7,0.5 0.4,1.1;1.8,0.2 2.3,0.8 2.4,1 2.4,1.9 1.8,2.8 1.4,3.6 1.3,4;1.8,0.2 1.1,0.2;1.3,5.1 1.3,6.1'),
    '+': (4.2, '0.4,3 1.7,3 3,3;1.7,1.3 1.7,3 1.7,4.9'),
    '*': (3.6, '2.5,3 2,2.4 1.8,2 1.4,2.1 1.4,2.1 1.4,1.6 0.6,1.4 0.4,1.3;2.9,1.3 2.3,1.6 1.9,1.6 1.4,2.1 0.8,3;1.4,2.1 1.6,1.6 1.7,0.2'),
    '/': (3.1, '2.3,0.2 0.4,6.1 0.3,6.2'),
    '(': (2.7, '1.7,7.8 1.4,7.4 1,6.6 0.4,5.2 0.3,2.9 0.5,1.6 1,0.5 1.5,-0.4 1.6,-0.7'),
    ')': (2.7, '0.1,7.6 0.4,7.3 1.1,6.1 1.5,4.4 1.5,2.7 1.2,1.6 1,0.9 0.7,0.4 0.4,-0.2 0.1,-0.5'),
    '[': (2.1, '0.4,-0.6 0.4,6.8 1,6.9;0.4,-0.6 1,-0.6'),
    ']': (2.1, '0.9,-0.6 0.9,6.8 0.3,6.9;0.9,-0.6 0.3,-0.6'),
    '=': (4.0, '2.4,2.2 0.4,2.2;0.4,3.9 2.5,3.9'),
    '%': (5.3, '4,5.6 3.4,5.8 3.1,5.7 2.7,5.3 2.7,4.2 2.9,3.7 3.1,3.6 3.7,3.5 4,3.7 4.2,4.2 4.1,5.3 4,5.6 4,5.6;0.3,1.9 0.8,2.4 1.3,2.4 1.5,2.2 1.8,1.8 1.7,0.6 1.3,0.1 0.8,0.1 0.6,0.3 0.3,0.7 0.2,1.4 0.3,1.9;1.1,5.1 1.5,4.4 2.2,3.1 2.9,1.8 3.3,0.9'),
    '#': (4.6, '2.2,5.91549 2.3,5.41549 2.4,5.01549 2.5,4.21549 2.6,3.31549 2.7,2.91549 2.8,2.21549 3.1,0.515493;0.8,5.91549 0.9,5.41549 1,5.01549 1.1,4.21549 1.2,3.31549 1.3,2.91549 1.4,2.21549 1.6,1.21549 1.7,0.415493;0.3,4.21549 1.1,4.21549 2.5,4.21549 3.2,4.21549;0.5,2.21549 1.4,2.21549 2.8,2.21549 3.5,2.21549;1.7,0.815493 1.6,1.21549'),
    '&': (4.6, '1.2,0.3 0.8,0.8 0.7,1.4 0.8,1.8 1.4,2.7 1.7,3.2 2.3,4 2.6,4.5 2.9,5.2 2.9,5.3;1.2,0.3 1.9,0.2 2.4,0.5 2.4,0.5 2.5,0.9 2.4,1.8 2.4,1.8 1.4,2.7 0.6,3.5 0.4,4.2 0.5,5 0.9,5.5;2.9,5.2 2.4,5.5 1.8,5.7 0.9,5.5 0.7,5.4 0.9,5.5;1.2,2.4 1.4,2.7;2.9,4.6 3.2,4.4 3.4,3.5;2.6,4.5 2.9,4.6 2.9,4.7 2.9,4.6;2.9,5.2 3.2,5.3 3.5,5.7 3.9,5.9'),
    '@': (6.5, '3.6,7.4 2.9,7.6 1.8,7.4 1.1,7 0.6,6.3 0.2,4.9 0.2,3.6 0.6,2.1 1.2,1.1 1.5,0.8 2,0.5 2.7,0.3 3.7,0.4 4.5,1 5,1.7 5.3,2.9 5.2,4.6 4.8,5.4 4.2,5.8 3.8,5.7 3.6,5.5 3.4,5.2;3.6,7.4 3.7,7.1;3.4,5.2 3.6,2.4 3.4,2.2 2.7,2.2 2.1,2.8 1.8,3.8 1.8,5.1 1.9,5.4 1.9,5.5;3.4,5.2 2.9,5.5 2.3,5.7 1.9,5.4'),
    '°': (3.2, '1.6,1.5 1.8,0.8 1.5,0.4 1.3,0.2 0.6,0.2 0.3,0.6 0.2,1.2 0.5,1.5 0.8,1.7 1.2,1.7 1.6,1.5'),
    "'": (1.5, '0.3,-0.1 0.2,1.3'),
    '<': (3.8, '2.7,1.8 2.4,2.1 1.5,2.6 0.7,3 0.5,3.2 0.5,3.2 0.7,3.7 1.5,4 2.5,4.6 2.8,5.1;2.7,1.8 2.6,2 2.7,1.8 2.7,1.7'),
    '>': (3.9, '2.4,3.4 2.4,3.5 2.4,3.4 2.5,3.2 2.3,3 1.1,2.4 0.2,2;2.4,3.4 2.3,3.6 0.4,4.5 0.1,4.7'),
    '_': (3.4, '0.3,6.3 2.8,6.3'),
    ' ': (3.0, ''),
}

FONT_META_CAPS = {'cap': 5.76, 'xheight': 5.76, 'desc': 0.2, 'height': 5.96}
FONT_CAPS = {
    'A': (3.3, '1.3,0.963889 1.7,0.863889 1.9,1.26389 2.3,3.36389 2.3,4.36389 2.5,4.76389 2.6,5.56389;1.3,0.963889 1.1,1.26389 0.9,2.96389 0.7,4.46389 0.5,5.56389 0.3,5.76389;0.7,4.46389 2.2,4.46389 2.3,4.36389'),
    'B': (3.4, '1.9,0.963889 2,1.06389 1.9,0.963889 1.3,0.763889 0.4,0.863889 0.4,3.16389 0.5,5.76389;1.9,0.963889 2.2,1.26389 2.2,2.06389 2.1,2.66389 1.8,3.06389;1.8,3.06389 0.4,3.16389;1.8,3.06389 1.9,3.46389 1.8,3.16389;0.5,5.76389 1.7,5.76389 2.2,5.56389 2.3,5.06389 2.3,4.26389 2.2,3.66389 1.9,3.46389'),
    'C': (3.2, '2,5.2 1.5,5.4 1.1,5.4 0.7,5.2;2,5.2 2.2,4.9 2.2,4.1;2.2,1.4 2,0.6 1.7,0.3 1,0.3 0.5,0.8 0.4,4.7 0.7,5.2 0.7,5.3'),
    'D': (3.4, '0.5,5.76389 1.6,5.76389 1.9,5.66389 2.2,5.36389 2.2,1.66389 2.1,1.16389 1.7,0.863889 0.4,0.863889 0.5,5.76389'),
    'E': (3.0, '1.7,3.16389 0.4,3.16389;2,5.76389 0.5,5.76389;2,0.763889 0.4,0.863889 0.4,3.16389 0.5,5.76389'),
    'F': (2.9, '0.4,5.76389 0.4,3.26389 0.4,0.863889 1.9,0.763889;0.4,3.26389 1.6,3.26389'),
    'G': (3.3, '2.2,1.4 2.2,1 2,0.5 2,0.5 1.7,0.3 1,0.3 0.5,0.8 0.4,4.7 0.6,5.1 0.8,5.3 1.6,5.4 2,5.2 2,5.2 2.2,4.8 2.2,2.9;2.2,2.9 1.8,2.8'),
    'H': (3.5, '2.3,0.963889 2.3,3.16389 2.3,5.76389;0.4,0.863889 0.4,3.16389 0.4,5.76389;2.3,3.16389 0.4,3.16389'),
    'I': (1.6, '0.4,0.863889 0.4,5.76389'),
    'J': (2.2, '0.4,5.76389 0.9,5.66389;0.9,5.66389 1.2,5.36389 1.2,4.86389 1.2,0.863889'),
    'K': (3.5, '0.6,3.26389 1.4,3.16389 1.4,3.16389 1.6,2.06389 2.3,0.663889 2.6,0.463889;0.4,5.66389 0.4,3.66389 0.6,3.26389 0.6,3.16389;0.6,3.26389 0.4,3.16389 0.4,0.763889;2.6,0.463889 2.4,0.563889 2.6,0.463889;1.4,3.16389 1.7,3.36389 2.4,5.76389'),
    'L': (2.9, '0.4,0.863889 0.5,5.76389;0.5,5.76389 1.9,5.76389'),
    'M': (4.5, '0.3,5.76389 0.3,1.96389 0.5,1.76389;3.1,1.16389 2.8,1.66389 2.5,1.96389 2.5,2.36389 2.2,4.66389 1.9,4.96389 1.8,5.16389 1.8,5.76389;2.8,1.66389 3.2,1.56389 3.3,1.66389 3.3,5.76389;0.5,1.76389 0.8,1.76389 1.1,2.06389 1.1,2.06389 1.5,4.76389 1.9,4.96389;0.5,1.76389 0.6,1.06389'),
    'N': (3.6, '0.3,5.76389 0.3,1.86389 0.5,1.66389;2.2,4.26389 2.4,3.96389 2.4,0.863889;2.2,4.26389 2,4.26389 1.6,3.96389 1.2,2.06389 0.8,1.66389 0.5,1.66389;2.3,5.66389 2.2,4.46389 2.2,4.26389 2.2,4.16389;0.6,1.06389 0.5,1.66389'),
    'O': (3.3, '0.4,2.9 0.4,1.1 0.6,0.7 1,0.3 1.9,0.4 2.2,0.9 2.3,1.4 2.3,4.4 2.2,4.9 1.9,5.3 1.1,5.4 0.8,5.3 0.6,5.1 0.4,4.7 0.4,2.5 0.4,1.1 0.6,0.7 1,0.3 1.9,0.4 2.2,0.9 2.3,1.4 2.3,4.4 2.2,4.9 1.9,5.3 1.1,5.4 0.8,5.3 0.6,5.1 0.4,4.7 0.4,2.3 0.4,1.1 0.6,0.7 1,0.3 1.9,0.4 2.2,0.9 2.3,1.4 2.3,4.4 2.2,4.9 1.9,5.3 0.8,5.3 0.5,4.9 0.4,2 0.5,0.8 0.8,0.4 1.7,0.3 2.1,0.6 2.3,1.4 2.3,4.4 2.2,4.9 1.9,5.3 0.8,5.3 0.5,4.9 0.4,1.7 0.5,0.8 0.8,0.4 1.7,0.3 2.1,0.6 2.3,1.4 2.3,4.4 2.2,4.9 1.9,5.3 0.8,5.3 0.5,4.9 0.4,1.6 0.5,0.8 1,0.3 1.7,0.3 2.2,0.9 2.3,4.4 2.2,4.9 1.9,5.3 0.8,5.3 0.5,4.9 0.4,1.9 0.5,0.8 0.8,0.4 1.7,0.3 2.1,0.6 2.3,1.4 2.3,4.4 2.2,4.9 1.9,5.3 0.8,5.3 0.5,4.9 0.4,2.2 0.4,1.1 0.6,0.7 1,0.3 1.9,0.4 2.2,0.9 2.3,1.4 2.3,4.4 2.2,4.9 1.9,5.3 0.8,5.3 0.5,4.9 0.4,2.1 0.4,1.1 0.6,0.7 1,0.3 1.9,0.4 2.2,0.9 2.3,1.4 2.3,4.4 2.2,4.9 1.9,5.3 0.8,5.3 0.5,4.9 0.4,2.4 0.4,1.1 0.6,0.7 1,0.3 1.9,0.4 2.2,0.9 2.3,1.4 2.3,4.4 2.2,4.9 1.9,5.3 0.8,5.3 0.5,4.9 0.4,2.8 0.4,1.1 0.6,0.7 1,0.3 1.9,0.4 2.2,0.9 2.3,1.4 2.3,4.4 2.2,4.9 1.9,5.3 1.1,5.4 0.8,5.3 0.6,5.1 0.4,4.7 0.4,2.7 0.4,1.1 0.6,0.7 1,0.3 1.9,0.4 2.2,0.9 2.3,1.4 2.3,4.4 2.2,4.9 1.9,5.3 1.1,5.4 0.8,5.3 0.6,5.1 0.4,4.7 0.4,2.6 0.4,1.1 0.6,0.7 1,0.3 1.9,0.4 2.2,0.9 2.3,1.4 2.3,4.4 2.2,4.9 1.9,5.3 1.1,5.4 0.8,5.3 0.6,5.1 0.4,4.7 0.4,3 0.4,1.1 0.6,0.7 1,0.3 1.9,0.4 2.2,0.9 2.3,1.4 2.3,4.4 2.2,4.9 1.9,5.3 1.1,5.4 0.8,5.3 0.6,5.1 0.4,4.7 0.4,3.3 0.5,0.8 1,0.3 1.7,0.3 2.1,0.6 2.3,1.4 2.3,4.4 2.2,4.9 1.9,5.3 1.1,5.4 0.8,5.3 0.6,5.1 0.4,4.7 0.4,3.2 0.5,0.8 1,0.3 1.7,0.3 2.1,0.6 2.3,1.4 2.3,4.4 2.2,4.9 1.9,5.3 1.1,5.4 0.8,5.3 0.6,5.1 0.4,4.7 0.4,3.1 0.4,1.1 0.6,0.7 1,0.3 1.9,0.4 2.2,0.9 2.3,1.4 2.3,4.4 2.2,4.9 1.9,5.3 1.1,5.4 0.8,5.3 0.6,5.1 0.4,4.7 0.4,3.5 0.5,0.8 1,0.3 1.7,0.3 2.1,0.6 2.3,1.4 2.3,4.4 2.2,4.9 1.9,5.3 1.1,5.4 0.8,5.3 0.6,5.1 0.4,4.7 0.4,3.8 0.5,0.8 1,0.3 1.7,0.3 2.1,0.6 2.3,1.4 2.3,4.4 2.1,5.1 1.6,5.4 0.8,5.3 0.5,4.9 0.4,3.7 0.5,0.8 1,0.3 1.7,0.3 2.1,0.6 2.3,1.4 2.3,4.4 2.1,5.1 1.6,5.4 0.8,5.3 0.6,5.1 0.4,4.7 0.4,4 0.5,0.8 1,0.3 1.7,0.3 2.1,0.6 2.3,1.4 2.3,4.4 2.1,5.1 1.6,5.4 0.8,5.3 0.5,4.9 0.4,4.4 0.5,0.8 1,0.3 1.7,0.3 2.1,0.6 2.3,1.4 2.2,4.9 1.9,5.3 1.1,5.4 0.8,5.3 0.6,5.1 0.4,4.3 0.5,0.8 1,0.3 1.7,0.3 2.1,0.6 2.3,1.4 2.2,4.9 1.9,5.3 0.8,5.3 0.5,4.9 0.4,4.6 0.5,0.8 1,0.3 1.7,0.3 2.1,0.6 2.3,1.4 2.2,4.9 1.9,5.3 1.1,5.4 0.8,5.3 0.6,5.1 0.5,4.9 0.5,0.8 1,0.3 1.7,0.3 2.1,0.6 2.3,1.4 2.2,4.9 1.9,5.3 1.6,5.4 0.8,5.3 0.7,5.2 0.4,4.7 0.4,1.1 0.6,0.7 0.8,0.4 1.7,0.3 2.1,0.6 2.3,1.4 2.2,4.9 1.9,5.3 1.6,5.4 1.1,5.4 0.8,5.3 0.6,5.1 0.4,4.7 0.4,1.1 0.6,0.7 0.8,0.4 1.7,0.3 2.1,0.6 2.3,1.4 2.2,4.9 1.9,5.3 1,5.3 0.6,5.1 0.4,4.7 0.4,1.1 0.6,0.7 0.8,0.4 1.7,0.3 2.1,0.6 2.3,1.4 2.2,4.9 1.9,5.3 1.3,5.4 0.8,5.3 0.6,5.1 0.4,4.7 0.4,1.1 0.6,0.7 0.8,0.4 1.7,0.3 2.1,0.6 2.3,1.4 2.3,4.4 2.1,5.1 1.9,5.3 1.7,5.3 0.8,5.3 0.6,5.1 0.4,4.7 0.4,1.1 0.6,0.7 1,0.3 1.7,0.3 2.2,0.9 2.3,4.4 2.1,5.1 2.1,5.1 1.6,5.4 0.8,5.3 0.6,5.1 0.4,4.7 0.4,1.1 0.6,0.7 1,0.3 1.7,0.3 2.2,0.9 2.3,4.4 2.2,4.7 2.1,5.1 1.6,5.4 0.8,5.3 0.5,4.9 0.4,1.1 0.6,0.7 1,0.3 1.7,0.3 2.2,0.9 2.2,4.5 2.1,5.1 1.6,5.4 0.8,5.3 0.5,4.9 0.4,1.1 0.6,0.7 1,0.3 1.7,0.3 2.2,0.9 2.3,4.4 2.2,4.9 1.9,5.3 0.8,5.3 0.5,4.9 0.4,1.1 0.6,0.7 1,0.3 1.7,0.3 2.2,0.9 2.3,4 2.2,4.9 1.9,5.3 1.1,5.4 0.8,5.3 0.6,5.1 0.4,4.7 0.4,1.1 0.6,0.7 1,0.3 1.7,0.3 2.2,0.9 2.3,3.7 2.2,4.9 1.9,5.3 1.1,5.4 0.8,5.3 0.6,5.1 0.4,4.7 0.4,1.1 0.6,0.7 1,0.3 1.7,0.3 2.2,0.9 2.3,3.5 2.3,4.4 2.1,5.1 1.6,5.4 0.8,5.3 0.6,5.1 0.4,4.7 0.4,1.1 0.6,0.7 1,0.3 1.7,0.3 2.2,0.9 2.3,3.4 2.3,4.4 2.1,5.1 1.6,5.4 0.8,5.3 0.6,5.1 0.4,4.7 0.4,1.1 0.6,0.7 1,0.3 1.7,0.3 2.2,0.9 2.3,3.1 2.3,4.4 2.1,5.1 1.6,5.4 0.8,5.3 0.6,5.1 0.4,4.7 0.4,1.1 0.6,0.7 0.8,0.4 1.7,0.3 2.1,0.6 2.3,1.4 2.3,2.9 2.3,4.4 2.1,5.1 1.6,5.4 0.8,5.3 0.6,5.1 0.4,4.7 0.4,1.1 0.6,0.7 0.8,0.4 1.7,0.3 2.1,0.6 2.3,1.4 2.3,2.8 2.3,4.4 2.1,5.1 1.6,5.4 0.8,5.3 0.6,5.1 0.4,4.7 0.4,1.1 0.6,0.7 0.8,0.4 1.7,0.3 2.1,0.6 2.3,1.4 2.3,2.4 2.3,4.4 2.1,5.1 1.6,5.4 0.8,5.3 0.6,5.1 0.4,4.7 0.4,1.1 0.6,0.7 0.8,0.4 1.7,0.3 2.1,0.6 2.3,1.4 2.3,2.3 2.2,4.9 1.9,5.3 0.8,5.3 0.6,5.1 0.4,4.7 0.4,1.1 0.6,0.7 0.8,0.4 1.7,0.3 2.1,0.6 2.3,1.4 2.3,2.2 2.2,4.9 1.9,5.3 0.8,5.3 0.6,5.1 0.4,4.7 0.4,1.1 0.6,0.7 0.8,0.4 1.7,0.3 2.1,0.6 2.3,1.4 2.3,2.2 2.2,4.9 1.9,5.3 0.8,5.3 0.6,5.1 0.4,4.7 0.4,1.1 0.6,0.7 1,0.3 1.9,0.4 2.2,0.9 2.3,1.8 2.2,4.9 1.9,5.3 0.8,5.3 0.6,5.1 0.4,4.7 0.4,1.1 0.6,0.7 1,0.3 1.9,0.4 2.2,0.9 2.3,1.7 2.2,4.9 1.9,5.3 0.8,5.3 0.6,5.1 0.4,4.7 0.5,0.8 1,0.3 1.7,0.3 2.2,0.9 2.2,1.3 2.2,4.9 1.9,5.3 0.8,5.3 0.6,5.1 0.4,4.7 0.5,0.8 1,0.3 1.7,0.3 2.1,0.6 2.2,1.2 2.3,1.4 2.2,4.9 1.9,5.3 0.8,5.3 0.6,5.1 0.4,4.7 0.5,0.8 1,0.3 1.7,0.3 2.2,0.8 2.2,0.9 2.3,1.4 2.2,4.9 1.9,5.3 1.1,5.4 0.8,5.3 0.6,5.1 0.4,4.7 0.4,1.1 0.6,0.7 1,0.3 1.7,0.3 1.9,0.5 2.3,1.4 2.2,4.9 1.9,5.3 1.1,5.4 0.8,5.3 0.6,5.1 0.4,4.7 0.4,1.1 0.6,0.7 1,0.3 1.7,0.3 2.1,0.7 2.2,0.9 2.3,1.4 2.2,4.9 1.9,5.3 1.1,5.4 0.8,5.3 0.6,5.1 0.4,4.7 0.4,1.1 0.6,0.7 1,0.3 1.7,0.3 2,0.6 2.1,0.6 2.2,0.9 2.3,4.4 2.2,4.9 1.9,5.3 1.1,5.4 0.8,5.3 0.6,5.1 0.4,4.7 0.4,1.1 0.6,0.7 0.8,0.4 1.7,0.3 1.9,0.4 2.2,0.9 2.3,4.4 2.2,4.9 1.9,5.3 1.1,5.4 0.8,5.3 0.6,5.1 0.4,4.7 0.4,1.1 0.6,0.7 0.8,0.4 1.4,0.3 1.9,0.4 2.2,0.9 2.3,1.4 2.2,4.9 1.9,5.3 1.6,5.4 0.8,5.3 0.6,5.1 0.4,4.7 0.4,1.1 0.6,0.7 1,0.3 1,0.3 1.7,0.3 2.2,0.9 2.3,4.4 2.1,5.1 1.6,5.4 0.8,5.3 0.6,5.1 0.4,4.7 0.4,1.1 0.8,0.5 1,0.3 1.7,0.3 2.2,0.9 2.3,4.4 2.2,4.9 1.9,5.3 0.8,5.3 0.5,4.9 0.5,0.8 0.6,0.7 1,0.3 1.7,0.3 2.2,0.9 2.3,4.4 2.2,4.9 1.9,5.3 0.8,5.3 0.5,4.9 0.4,1.1 0.6,0.7 1,0.3 1.7,0.3 2.2,0.9 2.3,4.4 2.2,4.9 1.9,5.3 0.8,5.3 0.5,4.9 0.5,1 0.6,0.7 1,0.3 1.7,0.3 2.2,0.9 2.3,4.4 2.2,4.9 1.9,5.3 0.8,5.3 0.5,4.9 0.4,1.2 0.6,0.7 1,0.3 1.7,0.3 2.2,0.9 2.3,4.4 2.2,4.9 1.9,5.3 0.8,5.3 0.5,4.9 0.4,1.4 0.5,0.8 1,0.3 1.7,0.3 2.2,0.9 2.3,4.4 2.2,4.9 1.9,5.3 0.8,5.3 0.5,4.9 0.4,1.5 0.5,0.8 0.8,0.4 1.7,0.3 2.1,0.6 2.3,1.4 2.3,4.4 2.2,4.9 1.9,5.3 0.8,5.3 0.5,4.9 0.4,1.8;0.4,3.4 0.5,0.8 1,0.3 1.7,0.3 2.1,0.6 2.3,1.4 2.3,4.4 2.2,4.9 1.9,5.3 1.1,5.4 0.8,5.3 0.6,5.1 0.4,4.7 0.4,3.6 0.5,0.8 1,0.3 1.7,0.3 2.1,0.6 2.3,1.4 2.3,4.4 2.2,4.9 1.9,5.3 1.1,5.4 0.8,5.3 0.6,5.1 0.4,4.7 0.4,3.9 0.5,0.8 1,0.3 1.7,0.3 2.1,0.6 2.3,1.4 2.3,4.4 2.1,5.1 1.6,5.4 0.8,5.3 0.5,4.9 0.4,4.2 0.5,0.8 1,0.3 1.7,0.3 2.1,0.6 2.3,1.4 2.2,4.9 1.9,5.3 0.8,5.3 0.5,4.9 0.4,4.1 0.5,0.8 1,0.3 1.7,0.3 2.1,0.6 2.3,1.4 2.3,4.4 2.1,5.1 1.6,5.4 0.8,5.3 0.5,4.9 0.4,4.5 0.5,0.8 1,0.3 1.7,0.3 2.1,0.6 2.3,1.4 2.2,4.9 1.9,5.3 1.1,5.4 0.8,5.3 0.6,5.1 0.5,4.8 0.5,0.8 1,0.3 1.7,0.3 2.1,0.6 2.3,1.4 2.2,4.9 1.9,5.3 1.1,5.4 0.8,5.3 0.6,5.1 0.6,5 0.4,4.7 0.5,0.8 1,0.3 1.7,0.3 2.1,0.6 2.3,1.4 2.2,4.9 1.9,5.3 1.6,5.4 0.8,5.3 0.9,5.3 0.6,5.1 0.4,4.7 0.4,1.1 0.6,0.7 0.8,0.4 1.7,0.3 2.1,0.6 2.3,1.4 2.2,4.9 1.9,5.3 1.2,5.4 0.8,5.3 0.6,5.1 0.4,4.7 0.4,1.1 0.6,0.7 0.8,0.4 1.7,0.3 2.1,0.6 2.3,1.4 2.3,4.4 2.1,5.1 1.9,5.3 1.4,5.4 0.8,5.3 0.6,5.1 0.4,4.7 0.4,1.1 0.6,0.7 1,0.3 1.9,0.4 2.2,0.9 2.3,1.4 2.2,4.9 1.9,5.3 1.1,5.4 0.8,5.3 0.6,5.1 0.4,4.7 0.4,1.1 0.6,0.7 0.8,0.4 1.7,0.3 2.1,0.6 2.3,1.4 2.3,4.4 2.2,4.9 1.9,5.3 1.5,5.4 0.8,5.3 0.6,5.1 0.4,4.7 0.4,1.1 0.6,0.7 1,0.3 1.9,0.4 2.2,0.9 2.3,1.4 2.2,4.9 1.9,5.3 1.9,5.3 0.8,5.3 0.6,5.1 0.4,4.7 0.4,1.1 0.6,0.7 1,0.3 1.7,0.3 2.2,0.9 2.3,4.4 2.2,4.9 2.2,5 1.9,5.3 1.1,5.4 0.8,5.3 0.5,4.9 0.4,1.1 0.6,0.7 1,0.3 1.7,0.3 2.2,0.9 2.3,4.4 2.2,4.8 1.9,5.3 1.6,5.4 0.8,5.3 0.5,4.9 0.4,1.1 0.6,0.7 1,0.3 1.7,0.3 2.2,0.9 2.2,4.4 2.2,4.9 1.9,5.3 0.8,5.3 0.5,4.9 0.4,1.1 0.6,0.7 1,0.3 1.7,0.3 2.2,0.9 2.3,4.2 2.2,4.9 1.9,5.3 0.8,5.3 0.5,4.9 0.4,1.1 0.6,0.7 1,0.3 1.7,0.3 2.2,0.9 2.3,3.8 2.2,4.9 1.9,5.3 1.1,5.4 0.8,5.3 0.6,5.1 0.4,4.7 0.4,1.1 0.6,0.7 1,0.3 1.7,0.3 2.2,0.9 2.3,3.6 2.2,4.9 1.9,5.3 1.1,5.4 0.8,5.3 0.6,5.1 0.4,4.7 0.4,1.1 0.6,0.7 1,0.3 1.7,0.3 2.2,0.9 2.3,3.3 2.3,4.4 2.1,5.1 1.6,5.4 0.8,5.3 0.6,5.1 0.4,4.7 0.4,1.1 0.6,0.7 1,0.3 1.7,0.3 2.2,0.9 2.3,3.2 2.3,4.4 2.1,5.1 1.6,5.4 0.8,5.3 0.6,5.1 0.4,4.7 0.4,1.1 0.6,0.7 1,0.3 1.7,0.3 2.2,0.9 2.3,3 2.3,4.4 2.1,5.1 1.6,5.4 0.8,5.3 0.6,5.1 0.4,4.7 0.4,1.1 0.6,0.7 0.8,0.4 1.7,0.3 2.1,0.6 2.3,1.4 2.3,2.7 2.3,4.4 2.1,5.1 1.6,5.4 0.8,5.3 0.6,5.1 0.4,4.7 0.4,1.1 0.6,0.7 0.8,0.4 1.7,0.3 2.1,0.6 2.3,1.4 2.3,2.6 2.3,4.4 2.1,5.1 1.6,5.4 0.8,5.3 0.6,5.1 0.4,4.7 0.4,1.1 0.6,0.7 0.8,0.4 1.7,0.3 2.1,0.6 2.3,1.4 2.3,2.5 2.3,4.4 2.1,5.1 1.6,5.4 0.8,5.3 0.6,5.1 0.4,4.7 0.4,1.1 0.6,0.7 0.8,0.4 1.7,0.3 2.1,0.6 2.3,1.4 2.3,2.1 2.2,4.9 1.9,5.3 0.8,5.3 0.6,5.1 0.4,4.7 0.4,1.1 0.6,0.7 1,0.3 1.9,0.4 2.2,0.9 2.3,1.9 2.2,4.9 1.9,5.3 0.8,5.3 0.6,5.1 0.4,4.7 0.4,1.1 0.6,0.7 1,0.3 1.9,0.4 2.2,0.9 2.3,1.5 2.2,4.9 1.9,5.3 0.8,5.3 0.6,5.1 0.4,4.7 0.5,0.8 1,0.3 1.7,0.3 2.2,0.9 2.2,1.1 2.2,4.9 1.9,5.3 0.8,5.3 0.6,5.1 0.4,4.7 0.5,0.8 1,0.3 1.7,0.3 2.1,0.6 2.2,1 2.2,4.9 1.9,5.3 0.8,5.3 0.6,5.1 0.4,4.7 0.5,0.8 1,0.3 1.7,0.3 2.1,0.6 2.1,0.6 2.3,1.4 2.2,4.9 1.9,5.3 1.1,5.4 0.8,5.3 0.6,5.1 0.4,4.7 0.4,1.1 0.6,0.7 1,0.3 1.7,0.3 1.9,0.4 2.2,0.9 2.3,1.4 2.2,4.9 1.9,5.3 1.1,5.4 0.8,5.3 0.6,5.1 0.4,4.7 0.4,1.1 0.6,0.7 1,0.3 1.5,0.3 1.9,0.4 2.2,0.9 2.3,4.4 2.2,4.9 1.9,5.3 1.1,5.4 0.8,5.3 0.6,5.1 0.4,4.7 0.4,1.1 0.6,0.7 0.8,0.4 1.1,0.3 1.9,0.4 2.2,0.9 2.3,1.4 2.2,4.9 1.9,5.3 1.6,5.4 0.8,5.3 0.6,5.1 0.4,4.7 0.4,1.1 0.6,0.7 0.8,0.4 0.8,0.4 1.7,0.3 2.2,0.9 2.3,4.4 2.1,5.1 1.6,5.4 0.8,5.3 0.6,5.1 0.4,4.7 0.4,1.1 0.6,0.7 0.8,0.4 1,0.3 1.7,0.3 2.2,0.9 2.3,4.4 2.1,5.1 1.6,5.4 0.8,5.3 0.6,5.1 0.4,4.7 0.4,1.1 0.7,0.6 1,0.3 1.7,0.3 2.2,0.9 2.3,4.4 2.2,4.9 1.9,5.3 0.8,5.3 0.5,4.9 0.4,1.1 0.6,0.7 1,0.3 1.7,0.3 2.2,0.9 2.3,4.4 2.1,5.1 1.6,5.4 0.8,5.3 0.6,5.1 0.4,4.7 0.4,1.1 0.6,0.6 1,0.3 1.7,0.3 2.2,0.9 2.3,4.4 2.2,4.9 1.9,5.3 0.8,5.3 0.5,4.9 0.4,1.1 0.6,0.8 0.6,0.7 1,0.3 1.7,0.3 2.2,0.9 2.3,4.4 2.2,4.9 1.9,5.3 0.8,5.3 0.5,4.9 0.5,0.9 0.6,0.7 1,0.3 1.7,0.3 2.2,0.9 2.3,4.4 2.2,4.9 1.9,5.3 0.8,5.3 0.5,4.9 0.4,1.3;2.3,1.4 2.2,4.9 1.9,5.3 0.8,5.3 0.6,5.1 0.4,4.7 0.5,0.8 1,0.3 1.7,0.3 2.1,0.6 2.3,1.6 2.2,4.9 1.9,5.3 0.8,5.3 0.6,5.1 0.4,4.7 0.5,0.8 1,0.3 1.7,0.3 2.2,0.9 2.3,1.6 2.2,4.9 1.9,5.3 0.8,5.3 0.6,5.1 0.4,4.7 0.4,1.1 0.6,0.7 1,0.3 1.9,0.4 2.2,0.9 2.3,2;1.6,5.4 0.8,5.3 0.6,5.1 0.4,4.7 0.4,1.1 0.6,0.7 1,0.3 1.9,0.4 2.2,0.9 2.3,1.4 2.2,4.9 1.9,5.3 1.8,5.3 0.8,5.3 0.6,5.1 0.4,4.7 0.4,1.1 0.6,0.7 1,0.3 1.7,0.3 2.2,0.9 2.3,4.4 2.2,4.9 2,5.2 1.6,5.4 0.8,5.3 0.6,5.1 0.4,4.7 0.4,1.1 0.6,0.7 1,0.3 1.7,0.3 2.2,0.9 2.3,4.4 2.2,4.9 2.2,4.9 1.9,5.3 1.1,5.4 0.8,5.3 0.5,4.9 0.4,1.1 0.6,0.7 1,0.3 1.7,0.3 2.2,0.9 2.3,4.4 2.2,4.6 2.1,5.1 1.6,5.4 0.8,5.3 0.5,4.9 0.4,1.1 0.6,0.7 1,0.3 1.7,0.3 2.2,0.9 2.3,4.3 2.2,4.9 1.9,5.3 0.8,5.3 0.5,4.9 0.4,1.1 0.6,0.7 1,0.3 1.7,0.3 2.2,0.9 2.3,4.3 2.2,4.9 1.9,5.3 1.1,5.4 0.8,5.3 0.6,5.1 0.4,4.7 0.4,1.1 0.6,0.7 1,0.3 1.7,0.3 2.2,0.9 2.3,4.1 2.2,4.9 1.9,5.3 1.1,5.4 0.8,5.3 0.6,5.1 0.4,4.7 0.4,1.1 0.6,0.7 1,0.3 1.7,0.3 2.2,0.9 2.3,3.9;0.9,0.4 0.6,0.7 0.4,1.1 0.4,4.7 0.6,5.1 0.8,5.3 1.6,5.4 1.9,5.3 2.2,4.9 2.3,1.4 2.2,0.9 1.9,0.4 1.2,0.3 0.8,0.4 0.6,0.7 0.4,1.1 0.4,4.7 0.6,5.1 0.8,5.3 1.6,5.4 1.9,5.3 2.2,4.9 2.3,1.4 2.1,0.6 1.7,0.3 1.2,0.3 0.8,0.4 0.6,0.7 0.4,1.1 0.4,4.7 0.6,5.1 0.8,5.3 1.1,5.4 1.9,5.3 2.2,4.9 2.3,4.4 2.2,0.9 1.9,0.4 1.6,0.3 1,0.3 0.6,0.7 0.4,1.1 0.4,4.7 0.6,5.1 0.8,5.3 1.1,5.4 1.9,5.3 2.2,4.9 2.3,4.4 2.3,1.4 2.2,0.9 1.8,0.4;2.2,0.9 1.7,0.3 1,0.3 0.5,0.8 0.4,4.7 0.6,5.1 0.8,5.3 1.9,5.3 2.2,4.9 2.2,0.9;0.6,5.1 0.8,5.3 1.6,5.4 1.9,5.3 2.2,4.9 2.3,1.4 2.1,0.6 1.7,0.3 0.8,0.4 0.6,0.7 0.4,1.1 0.4,4.7 0.4,4.7 0.6,5.1 0.8,5.3 1.1,5.4 1.9,5.3 2.2,4.9 2.3,1.4 2.1,0.6 1.7,0.3 1,0.3 0.5,0.8 0.4,4.7 0.6,5.1 0.8,5.3 1.1,5.4 1.9,5.3 2.2,4.9 2.3,1.4 2.1,0.6 1.7,0.3 1,0.3 0.5,0.8 0.5,4.7;1.3,0.3 0.8,0.4 0.6,0.7 0.4,1.1 0.4,4.7 0.6,5.1 0.8,5.3 1.6,5.4 1.9,5.3 2.2,4.9 2.3,1.4 2.1,0.6 1.7,0.3 1.3,0.3'),
    'P': (3.2, '0.4,5.76389 0.4,3.46389 0.4,0.863889 1.7,0.863889 2,1.16389 2.2,1.86389 2.2,2.46389 2,3.16389 2,3.26389;0.4,3.46389 1.6,3.46389 2,3.16389'),
    'Q': (3.3, '2.1,5.3 1.9,5.4 0.8,5.3 0.6,5.1 0.4,4.7 0.4,1.1 0.6,0.7 1,0.3 1.7,0.3 2.2,0.9 2.3,4.4 2.1,5.3 2.1,5.4 2.3,5.7;2.3,5.7 2.6,5.8'),
    'R': (3.4, '2.7,5.76389 2.2,5.26389 2.2,3.96389 2,3.26389 1.8,2.96389 1.8,2.76389 2.1,2.26389 2.2,1.66389 2.2,0.963889 2,0.563889 2,0.563889 1.3,0.263889 0.4,0.363889 0.4,2.76389 0.4,5.26389;0.4,2.76389 1.8,2.76389'),
    'S': (3.1, '2.2,1.1 2,0.5 2,0.5 1.7,0.3 1,0.3 0.7,0.5 0.5,0.8 0.4,1.6 0.6,2.1 1.9,3.5 2.1,3.9 2.2,4.4 2,5.1 1.5,5.4 0.8,5.3;0.8,5.3 0.4,4.9 0.3,4.5'),
    'T': (3.0, '1.4,5.76389 1.4,0.863889 1.4,0.863889 2.4,0.763889;1.4,0.863889 0.4,0.763889'),
    'U': (3.3, '0.4,0.5 0.4,4.1 0.6,5.1 0.6,5.1 1.1,5.4 1.6,5.4 2,5.2 2.2,4.9 2.3,4.3 2.3,0.4'),
    'V': (3.2, '2.5,1.16389 2,4.16389 2,4.66389 1.9,5.46389 1.7,5.76389;1.7,5.76389 1.3,5.76389 1.1,5.56389 1,4.66389 0.5,1.26389'),
    'W': (4.6, '1.3,5.46389 1,5.56389 0.8,5.36389 0.4,1.06389;1.1,5.76389 1.3,5.46389 1.6,5.06389 1.8,2.66389 2,2.36389 2.2,2.16389 2.2,1.26389;3.3,5.46389 3.5,5.36389 3.3,5.46389 3.1,5.56389 2.8,5.26389 2.6,2.56389 2.3,2.36389 2,2.36389;3.9,0.963889 3.5,4.86389 3.5,5.26389 3.3,5.46389 3.2,5.76389 3.3,5.56389'),
    'X': (3.4, '0.6,0.363889 1,1.56389 1.2,2.16389 1,1.56389;1,1.56389 1.3,2.26389 1.5,2.36389;0.1,5.76389 0.4,5.56389 0.6,5.36389 1.1,3.96389 1.7,3.46389 2.1,4.06389 2.5,5.36389;2.1,4.06389 1.9,3.56389 2.1,4.06389;1.1,3.96389 1.5,3.36389 1.9,2.16389 2.2,1.66389 2.6,0.363889 2.6,0.263889;1.5,2.36389 1.9,2.16389;2.6,0.363889 2.9,0.163889'),
    'Y': (3.3, '0.6,0.763889 1.1,2.46389 1.2,2.86389 1.7,2.96389;1.5,5.76389 1.5,3.16389 1.7,2.96389 2,2.66389 2.5,0.763889 2.6,0.663889'),
    'Z': (3.0, '0.5,5.76389 0.7,4.76389 0.9,4.46389 1,4.06389 1.4,3.26389 1.5,2.86389 1.8,2.16389 2.1,1.26389 2,0.763889 0.5,0.763889;1.8,2.16389 1.9,1.86389 1.8,2.16389 1.5,2.86389 1.5,2.96389;1.1,3.66389 1.1,3.76389 1,4.06389 0.9,4.46389;0.5,5.76389 2.2,5.76389'),
    '0': (3.3, '0.4,2.9 0.4,1.1 0.6,0.7 1,0.3 1.9,0.4 2.2,0.9 2.3,1.4 2.3,4.4 2.2,4.9 1.9,5.3 1.1,5.4 0.8,5.3 0.6,5.1 0.4,4.7 0.4,2.5 0.4,1.1 0.6,0.7 1,0.3 1.9,0.4 2.2,0.9 2.3,1.4 2.3,4.4 2.2,4.9 1.9,5.3 1.1,5.4 0.8,5.3 0.6,5.1 0.4,4.7 0.4,2.3 0.4,1.1 0.6,0.7 1,0.3 1.9,0.4 2.2,0.9 2.3,1.4 2.3,4.4 2.2,4.9 1.9,5.3 0.8,5.3 0.5,4.9 0.4,2 0.5,0.8 0.8,0.4 1.7,0.3 2.1,0.6 2.3,1.4 2.3,4.4 2.2,4.9 1.9,5.3 0.8,5.3 0.5,4.9 0.4,1.7 0.5,0.8 0.8,0.4 1.7,0.3 2.1,0.6 2.3,1.4 2.3,4.4 2.2,4.9 1.9,5.3 0.8,5.3 0.5,4.9 0.4,1.6 0.5,0.8 1,0.3 1.7,0.3 2.2,0.9 2.3,4.4 2.2,4.9 1.9,5.3 0.8,5.3 0.5,4.9 0.4,1.9 0.5,0.8 0.8,0.4 1.7,0.3 2.1,0.6 2.3,1.4 2.3,4.4 2.2,4.9 1.9,5.3 0.8,5.3 0.5,4.9 0.4,2.2 0.4,1.1 0.6,0.7 1,0.3 1.9,0.4 2.2,0.9 2.3,1.4 2.3,4.4 2.2,4.9 1.9,5.3 0.8,5.3 0.5,4.9 0.4,2.1 0.4,1.1 0.6,0.7 1,0.3 1.9,0.4 2.2,0.9 2.3,1.4 2.3,4.4 2.2,4.9 1.9,5.3 0.8,5.3 0.5,4.9 0.4,2.4 0.4,1.1 0.6,0.7 1,0.3 1.9,0.4 2.2,0.9 2.3,1.4 2.3,4.4 2.2,4.9 1.9,5.3 0.8,5.3 0.5,4.9 0.4,2.8 0.4,1.1 0.6,0.7 1,0.3 1.9,0.4 2.2,0.9 2.3,1.4 2.3,4.4 2.2,4.9 1.9,5.3 1.1,5.4 0.8,5.3 0.6,5.1 0.4,4.7 0.4,2.7 0.4,1.1 0.6,0.7 1,0.3 1.9,0.4 2.2,0.9 2.3,1.4 2.3,4.4 2.2,4.9 1.9,5.3 1.1,5.4 0.8,5.3 0.6,5.1 0.4,4.7 0.4,2.6 0.4,1.1 0.6,0.7 1,0.3 1.9,0.4 2.2,0.9 2.3,1.4 2.3,4.4 2.2,4.9 1.9,5.3 1.1,5.4 0.8,5.3 0.6,5.1 0.4,4.7 0.4,3 0.4,1.1 0.6,0.7 1,0.3 1.9,0.4 2.2,0.9 2.3,1.4 2.3,4.4 2.2,4.9 1.9,5.3 1.1,5.4 0.8,5.3 0.6,5.1 0.4,4.7 0.4,3.3 0.5,0.8 1,0.3 1.7,0.3 2.1,0.6 2.3,1.4 2.3,4.4 2.2,4.9 1.9,5.3 1.1,5.4 0.8,5.3 0.6,5.1 0.4,4.7 0.4,3.2 0.5,0.8 1,0.3 1.7,0.3 2.1,0.6 2.3,1.4 2.3,4.4 2.2,4.9 1.9,5.3 1.1,5.4 0.8,5.3 0.6,5.1 0.4,4.7 0.4,3.1 0.4,1.1 0.6,0.7 1,0.3 1.9,0.4 2.2,0.9 2.3,1.4 2.3,4.4 2.2,4.9 1.9,5.3 1.1,5.4 0.8,5.3 0.6,5.1 0.4,4.7 0.4,3.5 0.5,0.8 1,0.3 1.7,0.3 2.1,0.6 2.3,1.4 2.3,4.4 2.2,4.9 1.9,5.3 1.1,5.4 0.8,5.3 0.6,5.1 0.4,4.7 0.4,3.8 0.5,0.8 1,0.3 1.7,0.3 2.1,0.6 2.3,1.4 2.3,4.4 2.1,5.1 1.6,5.4 0.8,5.3 0.5,4.9 0.4,3.7 0.5,0.8 1,0.3 1.7,0.3 2.1,0.6 2.3,1.4 2.3,4.4 2.1,5.1 1.6,5.4 0.8,5.3 0.6,5.1 0.4,4.7 0.4,4 0.5,0.8 1,0.3 1.7,0.3 2.1,0.6 2.3,1.4 2.3,4.4 2.1,5.1 1.6,5.4 0.8,5.3 0.5,4.9 0.4,4.4 0.5,0.8 1,0.3 1.7,0.3 2.1,0.6 2.3,1.4 2.2,4.9 1.9,5.3 1.1,5.4 0.8,5.3 0.6,5.1 0.4,4.3 0.5,0.8 1,0.3 1.7,0.3 2.1,0.6 2.3,1.4 2.2,4.9 1.9,5.3 0.8,5.3 0.5,4.9 0.4,4.6 0.5,0.8 1,0.3 1.7,0.3 2.1,0.6 2.3,1.4 2.2,4.9 1.9,5.3 1.1,5.4 0.8,5.3 0.6,5.1 0.5,4.9 0.5,0.8 1,0.3 1.7,0.3 2.1,0.6 2.3,1.4 2.2,4.9 1.9,5.3 1.6,5.4 0.8,5.3 0.7,5.2 0.4,4.7 0.4,1.1 0.6,0.7 0.8,0.4 1.7,0.3 2.1,0.6 2.3,1.4 2.2,4.9 1.9,5.3 1.6,5.4 1.1,5.4 0.8,5.3 0.6,5.1 0.4,4.7 0.4,1.1 0.6,0.7 0.8,0.4 1.7,0.3 2.1,0.6 2.3,1.4 2.2,4.9 1.9,5.3 1,5.3 0.6,5.1 0.4,4.7 0.4,1.1 0.6,0.7 0.8,0.4 1.7,0.3 2.1,0.6 2.3,1.4 2.2,4.9 1.9,5.3 1.3,5.4 0.8,5.3 0.6,5.1 0.4,4.7 0.4,1.1 0.6,0.7 0.8,0.4 1.7,0.3 2.1,0.6 2.3,1.4 2.3,4.4 2.1,5.1 1.9,5.3 1.7,5.3 0.8,5.3 0.6,5.1 0.4,4.7 0.4,1.1 0.6,0.7 1,0.3 1.7,0.3 2.2,0.9 2.3,4.4 2.1,5.1 2.1,5.1 1.6,5.4 0.8,5.3 0.6,5.1 0.4,4.7 0.4,1.1 0.6,0.7 1,0.3 1.7,0.3 2.2,0.9 2.3,4.4 2.2,4.7 2.1,5.1 1.6,5.4 0.8,5.3 0.5,4.9 0.4,1.1 0.6,0.7 1,0.3 1.7,0.3 2.2,0.9 2.2,4.5 2.1,5.1 1.6,5.4 0.8,5.3 0.5,4.9 0.4,1.1 0.6,0.7 1,0.3 1.7,0.3 2.2,0.9 2.3,4.4 2.2,4.9 1.9,5.3 0.8,5.3 0.5,4.9 0.4,1.1 0.6,0.7 1,0.3 1.7,0.3 2.2,0.9 2.3,4 2.2,4.9 1.9,5.3 1.1,5.4 0.8,5.3 0.6,5.1 0.4,4.7 0.4,1.1 0.6,0.7 1,0.3 1.7,0.3 2.2,0.9 2.3,3.7 2.2,4.9 1.9,5.3 1.1,5.4 0.8,5.3 0.6,5.1 0.4,4.7 0.4,1.1 0.6,0.7 1,0.3 1.7,0.3 2.2,0.9 2.3,3.5 2.3,4.4 2.1,5.1 1.6,5.4 0.8,5.3 0.6,5.1 0.4,4.7 0.4,1.1 0.6,0.7 1,0.3 1.7,0.3 2.2,0.9 2.3,3.4 2.3,4.4 2.1,5.1 1.6,5.4 0.8,5.3 0.6,5.1 0.4,4.7 0.4,1.1 0.6,0.7 1,0.3 1.7,0.3 2.2,0.9 2.3,3.1 2.3,4.4 2.1,5.1 1.6,5.4 0.8,5.3 0.6,5.1 0.4,4.7 0.4,1.1 0.6,0.7 0.8,0.4 1.7,0.3 2.1,0.6 2.3,1.4 2.3,2.9 2.3,4.4 2.1,5.1 1.6,5.4 0.8,5.3 0.6,5.1 0.4,4.7 0.4,1.1 0.6,0.7 0.8,0.4 1.7,0.3 2.1,0.6 2.3,1.4 2.3,2.8 2.3,4.4 2.1,5.1 1.6,5.4 0.8,5.3 0.6,5.1 0.4,4.7 0.4,1.1 0.6,0.7 0.8,0.4 1.7,0.3 2.1,0.6 2.3,1.4 2.3,2.4 2.3,4.4 2.1,5.1 1.6,5.4 0.8,5.3 0.6,5.1 0.4,4.7 0.4,1.1 0.6,0.7 0.8,0.4 1.7,0.3 2.1,0.6 2.3,1.4 2.3,2.3 2.2,4.9 1.9,5.3 0.8,5.3 0.6,5.1 0.4,4.7 0.4,1.1 0.6,0.7 0.8,0.4 1.7,0.3 2.1,0.6 2.3,1.4 2.3,2.2 2.2,4.9 1.9,5.3 0.8,5.3 0.6,5.1 0.4,4.7 0.4,1.1 0.6,0.7 0.8,0.4 1.7,0.3 2.1,0.6 2.3,1.4 2.3,2.2 2.2,4.9 1.9,5.3 0.8,5.3 0.6,5.1 0.4,4.7 0.4,1.1 0.6,0.7 1,0.3 1.9,0.4 2.2,0.9 2.3,1.8 2.2,4.9 1.9,5.3 0.8,5.3 0.6,5.1 0.4,4.7 0.4,1.1 0.6,0.7 1,0.3 1.9,0.4 2.2,0.9 2.3,1.7 2.2,4.9 1.9,5.3 0.8,5.3 0.6,5.1 0.4,4.7 0.5,0.8 1,0.3 1.7,0.3 2.2,0.9 2.2,1.3 2.2,4.9 1.9,5.3 0.8,5.3 0.6,5.1 0.4,4.7 0.5,0.8 1,0.3 1.7,0.3 2.1,0.6 2.2,1.2 2.3,1.4 2.2,4.9 1.9,5.3 0.8,5.3 0.6,5.1 0.4,4.7 0.5,0.8 1,0.3 1.7,0.3 2.2,0.8 2.2,0.9 2.3,1.4 2.2,4.9 1.9,5.3 1.1,5.4 0.8,5.3 0.6,5.1 0.4,4.7 0.4,1.1 0.6,0.7 1,0.3 1.7,0.3 1.9,0.5 2.3,1.4 2.2,4.9 1.9,5.3 1.1,5.4 0.8,5.3 0.6,5.1 0.4,4.7 0.4,1.1 0.6,0.7 1,0.3 1.7,0.3 2.1,0.7 2.2,0.9 2.3,1.4 2.2,4.9 1.9,5.3 1.1,5.4 0.8,5.3 0.6,5.1 0.4,4.7 0.4,1.1 0.6,0.7 1,0.3 1.7,0.3 2,0.6 2.1,0.6 2.2,0.9 2.3,4.4 2.2,4.9 1.9,5.3 1.1,5.4 0.8,5.3 0.6,5.1 0.4,4.7 0.4,1.1 0.6,0.7 0.8,0.4 1.7,0.3 1.9,0.4 2.2,0.9 2.3,4.4 2.2,4.9 1.9,5.3 1.1,5.4 0.8,5.3 0.6,5.1 0.4,4.7 0.4,1.1 0.6,0.7 0.8,0.4 1.4,0.3 1.9,0.4 2.2,0.9 2.3,1.4 2.2,4.9 1.9,5.3 1.6,5.4 0.8,5.3 0.6,5.1 0.4,4.7 0.4,1.1 0.6,0.7 1,0.3 1,0.3 1.7,0.3 2.2,0.9 2.3,4.4 2.1,5.1 1.6,5.4 0.8,5.3 0.6,5.1 0.4,4.7 0.4,1.1 0.8,0.5 1,0.3 1.7,0.3 2.2,0.9 2.3,4.4 2.2,4.9 1.9,5.3 0.8,5.3 0.5,4.9 0.5,0.8 0.6,0.7 1,0.3 1.7,0.3 2.2,0.9 2.3,4.4 2.2,4.9 1.9,5.3 0.8,5.3 0.5,4.9 0.4,1.1 0.6,0.7 1,0.3 1.7,0.3 2.2,0.9 2.3,4.4 2.2,4.9 1.9,5.3 0.8,5.3 0.5,4.9 0.5,1 0.6,0.7 1,0.3 1.7,0.3 2.2,0.9 2.3,4.4 2.2,4.9 1.9,5.3 0.8,5.3 0.5,4.9 0.4,1.2 0.6,0.7 1,0.3 1.7,0.3 2.2,0.9 2.3,4.4 2.2,4.9 1.9,5.3 0.8,5.3 0.5,4.9 0.4,1.4 0.5,0.8 1,0.3 1.7,0.3 2.2,0.9 2.3,4.4 2.2,4.9 1.9,5.3 0.8,5.3 0.5,4.9 0.4,1.5 0.5,0.8 0.8,0.4 1.7,0.3 2.1,0.6 2.3,1.4 2.3,4.4 2.2,4.9 1.9,5.3 0.8,5.3 0.5,4.9 0.4,1.8;0.4,3.4 0.5,0.8 1,0.3 1.7,0.3 2.1,0.6 2.3,1.4 2.3,4.4 2.2,4.9 1.9,5.3 1.1,5.4 0.8,5.3 0.6,5.1 0.4,4.7 0.4,3.6 0.5,0.8 1,0.3 1.7,0.3 2.1,0.6 2.3,1.4 2.3,4.4 2.2,4.9 1.9,5.3 1.1,5.4 0.8,5.3 0.6,5.1 0.4,4.7 0.4,3.9 0.5,0.8 1,0.3 1.7,0.3 2.1,0.6 2.3,1.4 2.3,4.4 2.1,5.1 1.6,5.4 0.8,5.3 0.5,4.9 0.4,4.2 0.5,0.8 1,0.3 1.7,0.3 2.1,0.6 2.3,1.4 2.2,4.9 1.9,5.3 0.8,5.3 0.5,4.9 0.4,4.1 0.5,0.8 1,0.3 1.7,0.3 2.1,0.6 2.3,1.4 2.3,4.4 2.1,5.1 1.6,5.4 0.8,5.3 0.5,4.9 0.4,4.5 0.5,0.8 1,0.3 1.7,0.3 2.1,0.6 2.3,1.4 2.2,4.9 1.9,5.3 1.1,5.4 0.8,5.3 0.6,5.1 0.5,4.8 0.5,0.8 1,0.3 1.7,0.3 2.1,0.6 2.3,1.4 2.2,4.9 1.9,5.3 1.1,5.4 0.8,5.3 0.6,5.1 0.6,5 0.4,4.7 0.5,0.8 1,0.3 1.7,0.3 2.1,0.6 2.3,1.4 2.2,4.9 1.9,5.3 1.6,5.4 0.8,5.3 0.9,5.3 0.6,5.1 0.4,4.7 0.4,1.1 0.6,0.7 0.8,0.4 1.7,0.3 2.1,0.6 2.3,1.4 2.2,4.9 1.9,5.3 1.2,5.4 0.8,5.3 0.6,5.1 0.4,4.7 0.4,1.1 0.6,0.7 0.8,0.4 1.7,0.3 2.1,0.6 2.3,1.4 2.3,4.4 2.1,5.1 1.9,5.3 1.4,5.4 0.8,5.3 0.6,5.1 0.4,4.7 0.4,1.1 0.6,0.7 1,0.3 1.9,0.4 2.2,0.9 2.3,1.4 2.2,4.9 1.9,5.3 1.1,5.4 0.8,5.3 0.6,5.1 0.4,4.7 0.4,1.1 0.6,0.7 0.8,0.4 1.7,0.3 2.1,0.6 2.3,1.4 2.3,4.4 2.2,4.9 1.9,5.3 1.5,5.4 0.8,5.3 0.6,5.1 0.4,4.7 0.4,1.1 0.6,0.7 1,0.3 1.9,0.4 2.2,0.9 2.3,1.4 2.2,4.9 1.9,5.3 1.9,5.3 0.8,5.3 0.6,5.1 0.4,4.7 0.4,1.1 0.6,0.7 1,0.3 1.7,0.3 2.2,0.9 2.3,4.4 2.2,4.9 2.2,5 1.9,5.3 1.1,5.4 0.8,5.3 0.5,4.9 0.4,1.1 0.6,0.7 1,0.3 1.7,0.3 2.2,0.9 2.3,4.4 2.2,4.8 1.9,5.3 1.6,5.4 0.8,5.3 0.5,4.9 0.4,1.1 0.6,0.7 1,0.3 1.7,0.3 2.2,0.9 2.2,4.4 2.2,4.9 1.9,5.3 0.8,5.3 0.5,4.9 0.4,1.1 0.6,0.7 1,0.3 1.7,0.3 2.2,0.9 2.3,4.2 2.2,4.9 1.9,5.3 0.8,5.3 0.5,4.9 0.4,1.1 0.6,0.7 1,0.3 1.7,0.3 2.2,0.9 2.3,3.8 2.2,4.9 1.9,5.3 1.1,5.4 0.8,5.3 0.6,5.1 0.4,4.7 0.4,1.1 0.6,0.7 1,0.3 1.7,0.3 2.2,0.9 2.3,3.6 2.2,4.9 1.9,5.3 1.1,5.4 0.8,5.3 0.6,5.1 0.4,4.7 0.4,1.1 0.6,0.7 1,0.3 1.7,0.3 2.2,0.9 2.3,3.3 2.3,4.4 2.1,5.1 1.6,5.4 0.8,5.3 0.6,5.1 0.4,4.7 0.4,1.1 0.6,0.7 1,0.3 1.7,0.3 2.2,0.9 2.3,3.2 2.3,4.4 2.1,5.1 1.6,5.4 0.8,5.3 0.6,5.1 0.4,4.7 0.4,1.1 0.6,0.7 1,0.3 1.7,0.3 2.2,0.9 2.3,3 2.3,4.4 2.1,5.1 1.6,5.4 0.8,5.3 0.6,5.1 0.4,4.7 0.4,1.1 0.6,0.7 0.8,0.4 1.7,0.3 2.1,0.6 2.3,1.4 2.3,2.7 2.3,4.4 2.1,5.1 1.6,5.4 0.8,5.3 0.6,5.1 0.4,4.7 0.4,1.1 0.6,0.7 0.8,0.4 1.7,0.3 2.1,0.6 2.3,1.4 2.3,2.6 2.3,4.4 2.1,5.1 1.6,5.4 0.8,5.3 0.6,5.1 0.4,4.7 0.4,1.1 0.6,0.7 0.8,0.4 1.7,0.3 2.1,0.6 2.3,1.4 2.3,2.5 2.3,4.4 2.1,5.1 1.6,5.4 0.8,5.3 0.6,5.1 0.4,4.7 0.4,1.1 0.6,0.7 0.8,0.4 1.7,0.3 2.1,0.6 2.3,1.4 2.3,2.1 2.2,4.9 1.9,5.3 0.8,5.3 0.6,5.1 0.4,4.7 0.4,1.1 0.6,0.7 1,0.3 1.9,0.4 2.2,0.9 2.3,1.9 2.2,4.9 1.9,5.3 0.8,5.3 0.6,5.1 0.4,4.7 0.4,1.1 0.6,0.7 1,0.3 1.9,0.4 2.2,0.9 2.3,1.5 2.2,4.9 1.9,5.3 0.8,5.3 0.6,5.1 0.4,4.7 0.5,0.8 1,0.3 1.7,0.3 2.2,0.9 2.2,1.1 2.2,4.9 1.9,5.3 0.8,5.3 0.6,5.1 0.4,4.7 0.5,0.8 1,0.3 1.7,0.3 2.1,0.6 2.2,1 2.2,4.9 1.9,5.3 0.8,5.3 0.6,5.1 0.4,4.7 0.5,0.8 1,0.3 1.7,0.3 2.1,0.6 2.1,0.6 2.3,1.4 2.2,4.9 1.9,5.3 1.1,5.4 0.8,5.3 0.6,5.1 0.4,4.7 0.4,1.1 0.6,0.7 1,0.3 1.7,0.3 1.9,0.4 2.2,0.9 2.3,1.4 2.2,4.9 1.9,5.3 1.1,5.4 0.8,5.3 0.6,5.1 0.4,4.7 0.4,1.1 0.6,0.7 1,0.3 1.5,0.3 1.9,0.4 2.2,0.9 2.3,4.4 2.2,4.9 1.9,5.3 1.1,5.4 0.8,5.3 0.6,5.1 0.4,4.7 0.4,1.1 0.6,0.7 0.8,0.4 1.1,0.3 1.9,0.4 2.2,0.9 2.3,1.4 2.2,4.9 1.9,5.3 1.6,5.4 0.8,5.3 0.6,5.1 0.4,4.7 0.4,1.1 0.6,0.7 0.8,0.4 0.8,0.4 1.7,0.3 2.2,0.9 2.3,4.4 2.1,5.1 1.6,5.4 0.8,5.3 0.6,5.1 0.4,4.7 0.4,1.1 0.6,0.7 0.8,0.4 1,0.3 1.7,0.3 2.2,0.9 2.3,4.4 2.1,5.1 1.6,5.4 0.8,5.3 0.6,5.1 0.4,4.7 0.4,1.1 0.7,0.6 1,0.3 1.7,0.3 2.2,0.9 2.3,4.4 2.2,4.9 1.9,5.3 0.8,5.3 0.5,4.9 0.4,1.1 0.6,0.7 1,0.3 1.7,0.3 2.2,0.9 2.3,4.4 2.1,5.1 1.6,5.4 0.8,5.3 0.6,5.1 0.4,4.7 0.4,1.1 0.6,0.6 1,0.3 1.7,0.3 2.2,0.9 2.3,4.4 2.2,4.9 1.9,5.3 0.8,5.3 0.5,4.9 0.4,1.1 0.6,0.8 0.6,0.7 1,0.3 1.7,0.3 2.2,0.9 2.3,4.4 2.2,4.9 1.9,5.3 0.8,5.3 0.5,4.9 0.5,0.9 0.6,0.7 1,0.3 1.7,0.3 2.2,0.9 2.3,4.4 2.2,4.9 1.9,5.3 0.8,5.3 0.5,4.9 0.4,1.3;2.3,1.4 2.2,4.9 1.9,5.3 0.8,5.3 0.6,5.1 0.4,4.7 0.5,0.8 1,0.3 1.7,0.3 2.1,0.6 2.3,1.6 2.2,4.9 1.9,5.3 0.8,5.3 0.6,5.1 0.4,4.7 0.5,0.8 1,0.3 1.7,0.3 2.2,0.9 2.3,1.6 2.2,4.9 1.9,5.3 0.8,5.3 0.6,5.1 0.4,4.7 0.4,1.1 0.6,0.7 1,0.3 1.9,0.4 2.2,0.9 2.3,2;1.6,5.4 0.8,5.3 0.6,5.1 0.4,4.7 0.4,1.1 0.6,0.7 1,0.3 1.9,0.4 2.2,0.9 2.3,1.4 2.2,4.9 1.9,5.3 1.8,5.3 0.8,5.3 0.6,5.1 0.4,4.7 0.4,1.1 0.6,0.7 1,0.3 1.7,0.3 2.2,0.9 2.3,4.4 2.2,4.9 2,5.2 1.6,5.4 0.8,5.3 0.6,5.1 0.4,4.7 0.4,1.1 0.6,0.7 1,0.3 1.7,0.3 2.2,0.9 2.3,4.4 2.2,4.9 2.2,4.9 1.9,5.3 1.1,5.4 0.8,5.3 0.5,4.9 0.4,1.1 0.6,0.7 1,0.3 1.7,0.3 2.2,0.9 2.3,4.4 2.2,4.6 2.1,5.1 1.6,5.4 0.8,5.3 0.5,4.9 0.4,1.1 0.6,0.7 1,0.3 1.7,0.3 2.2,0.9 2.3,4.3 2.2,4.9 1.9,5.3 0.8,5.3 0.5,4.9 0.4,1.1 0.6,0.7 1,0.3 1.7,0.3 2.2,0.9 2.3,4.3 2.2,4.9 1.9,5.3 1.1,5.4 0.8,5.3 0.6,5.1 0.4,4.7 0.4,1.1 0.6,0.7 1,0.3 1.7,0.3 2.2,0.9 2.3,4.1 2.2,4.9 1.9,5.3 1.1,5.4 0.8,5.3 0.6,5.1 0.4,4.7 0.4,1.1 0.6,0.7 1,0.3 1.7,0.3 2.2,0.9 2.3,3.9;0.9,0.4 0.6,0.7 0.4,1.1 0.4,4.7 0.6,5.1 0.8,5.3 1.6,5.4 1.9,5.3 2.2,4.9 2.3,1.4 2.2,0.9 1.9,0.4 1.2,0.3 0.8,0.4 0.6,0.7 0.4,1.1 0.4,4.7 0.6,5.1 0.8,5.3 1.6,5.4 1.9,5.3 2.2,4.9 2.3,1.4 2.1,0.6 1.7,0.3 1.2,0.3 0.8,0.4 0.6,0.7 0.4,1.1 0.4,4.7 0.6,5.1 0.8,5.3 1.1,5.4 1.9,5.3 2.2,4.9 2.3,4.4 2.2,0.9 1.9,0.4 1.6,0.3 1,0.3 0.6,0.7 0.4,1.1 0.4,4.7 0.6,5.1 0.8,5.3 1.1,5.4 1.9,5.3 2.2,4.9 2.3,4.4 2.3,1.4 2.2,0.9 1.8,0.4;2.2,0.9 1.7,0.3 1,0.3 0.5,0.8 0.4,4.7 0.6,5.1 0.8,5.3 1.9,5.3 2.2,4.9 2.2,0.9;0.6,5.1 0.8,5.3 1.6,5.4 1.9,5.3 2.2,4.9 2.3,1.4 2.1,0.6 1.7,0.3 0.8,0.4 0.6,0.7 0.4,1.1 0.4,4.7 0.4,4.7 0.6,5.1 0.8,5.3 1.1,5.4 1.9,5.3 2.2,4.9 2.3,1.4 2.1,0.6 1.7,0.3 1,0.3 0.5,0.8 0.4,4.7 0.6,5.1 0.8,5.3 1.1,5.4 1.9,5.3 2.2,4.9 2.3,1.4 2.1,0.6 1.7,0.3 1,0.3 0.5,0.8 0.5,4.7;1.3,0.3 0.8,0.4 0.6,0.7 0.4,1.1 0.4,4.7 0.6,5.1 0.8,5.3 1.6,5.4 1.9,5.3 2.2,4.9 2.3,1.4 2.1,0.6 1.7,0.3 1.3,0.3'),
    '1': (3.3, '1.4,5.76389 1.4,1.46389 1.5,1.16389 1.5,0.763889;1.4,1.46389 0.3,1.46389'),
    '2': (3.3, '0.3,1.96389 0.6,1.06389 0.9,0.763889 1.7,0.763889 2,1.06389 2.2,1.76389 2.2,2.36389 1.9,2.86389 1.1,3.86389 0.7,4.46389 0.4,5.16389 0.5,5.76389;0.5,5.76389 2.2,5.76389'),
    '3': (3.3, '0.6,5.2 1,5.4 1.6,5.4 1.9,5.3 2,5.1 2.2,4.5 2.2,3.8 2.1,3.3 1.9,3 1.7,2.7;1.7,2.7 2.2,1.9 2.2,0.9 1.7,0.3 1,0.3 0.7,0.5 0.7,0.5 0.4,1.2;0.6,5.2 0.5,5 0.4,4.4;1.7,2.7 1.3,2.7'),
    '4': (3.3, '2.1,0.963889 2,1.66389 2,1.66389 1.5,1.86389 1.3,1.96389 1.2,2.26389 1.1,2.66389 0.5,3.96389 0.4,4.76389 0.4,4.76389 2.2,4.76389 2.6,4.76389;2,1.66389 2.2,1.76389 2.2,4.76389 2.2,5.76389'),
    '5': (3.3, '0.5,2.4 1.8,2.2 2.2,2.6 2.2,2.6 2.3,4.4 2.1,5.1 1.6,5.4 0.8,5.3 0.7,5.3 0.8,5.3;0.8,5.3 0.5,4.9 0.4,4.4;0.6,0.4 2.2,0.3;0.6,0.4 0.5,0.9 0.5,2.4 0.4,2.8 0.5,2.5'),
    '6': (3.3, '0.6,0.7 1,0.3 1.8,0.3 2.1,0.7 2.3,1;2,5.2 1.6,5.4 1.1,5.4 0.6,5.1 0.4,4.2 0.4,2.8 0.4,1.6 0.6,0.7'),
    '7': (3.3, '0.7,5.76389 1,5.56389 2.1,1.76389 2.2,0.663889 0.4,0.563889'),
    '8': (3.3, '2.1,5.2 1.7,5.4 1.2,5.4 0.8,5.2 0.6,5 0.4,4.2 0.6,3.3 0.9,2.9 1.1,2.7 1.9,2.7 2,2.4 1.9,2.7 2,3 2.4,3.8 2.4,4.6 2.1,5.2 2.1,5.3;0.9,2.9 0.9,2.6 0.7,2.3 0.5,1.8 0.6,0.8 0.6,0.7;0.6,0.8 1,0.3 1.8,0.3 2.2,0.7 2.4,1.5 2.2,2.2 2,2.4'),
    '9': (3.3, '0.8,0.5 1,0.3 1.8,0.3 2.2,0.6 2.3,1.2 2.3,3.1 2.3,4.6 2.1,5.1 1.7,5.4 1.1,5.4 0.7,5.2 0.5,4.9'),
    'Ä': (3.3, '1.3,0.963889 1.7,0.863889 1.9,1.26389 2.3,3.36389 2.3,4.36389 2.5,4.76389 2.6,5.56389;1.3,0.963889 1.1,1.26389 0.9,2.96389 0.7,4.46389 0.5,5.56389 0.3,5.76389;0.7,4.46389 2.2,4.46389 2.3,4.36389;2.2,-1.03611 2.2,-0.0361111;0.9,-1.03611 0.9,-0.0361111'),
    'Ö': (3.3, '2.3,3 2.3,1.4 2.1,0.6 1.7,0.3 0.8,0.4 0.6,0.7 0.4,1.1 0.4,4.7 0.6,5.1 0.8,5.3 1.6,5.4 2.1,5.1 2.3,4.4 2.3,3.2 2.2,0.9 1.7,0.3 1,0.3 0.6,0.7 0.4,1.1 0.4,4.7 0.6,5.1 0.8,5.3 1.6,5.4 2.1,5.1 2.3,4.4 2.3,2.8 2.3,1.4 2.1,0.6 1.7,0.3 0.8,0.4 0.6,0.7 0.4,1.1 0.4,4.7 0.6,5.1 0.8,5.3 1.6,5.4 2.1,5.1 2.3,4.4 2.3,2.7 2.3,1.4 2.1,0.6 1.7,0.3 0.8,0.4 0.6,0.7 0.4,1.1 0.4,4.7 0.6,5.1 0.8,5.3 1.6,5.4 2.1,5.1 2.3,4.4 2.3,2.5 2.3,1.4 2.1,0.6 1.7,0.3 0.8,0.4 0.6,0.7 0.4,1.1 0.4,4.7 0.6,5.1 0.8,5.3 1.6,5.4 2.1,5.1 2.3,4.4 2.3,2.2 2.3,1.4 2.1,0.6 1.7,0.3 0.8,0.4 0.6,0.7 0.4,1.1 0.4,4.7 0.6,5.1 0.8,5.3 1.9,5.3 2.2,4.9 2.3,2.1 2.2,0.9 1.9,0.4 1,0.3 0.6,0.7 0.4,1.1 0.4,4.7 0.6,5.1 0.8,5.3 1.9,5.3 2.2,4.9 2.3,2.4 2.3,1.4 2.1,0.6 1.7,0.3 0.8,0.4 0.6,0.7 0.4,1.1 0.4,4.7 0.6,5.1 0.8,5.3 1.6,5.4 2.1,5.1 2.3,4.4 2.3,2.3 2.3,1.4 2.1,0.6 1.7,0.3 0.8,0.4 0.6,0.7 0.4,1.1 0.4,4.7 0.6,5.1 0.8,5.3 1.9,5.3 2.2,4.9 2.3,2.6 2.3,1.4 2.1,0.6 1.7,0.3 0.8,0.4 0.6,0.7 0.4,1.1 0.4,4.7 0.6,5.1 0.8,5.3 1.6,5.4 2.1,5.1 2.3,4.4 2.3,2.9 2.3,1.4 2.1,0.6 1.7,0.3 0.8,0.4 0.6,0.7 0.4,1.1 0.4,4.7 0.6,5.1 0.8,5.3 1.6,5.4 2.1,5.1 2.3,4.4 2.3,3.1 2.3,1.4 2.1,0.6 1.7,0.3 0.8,0.4 0.6,0.7 0.4,1.1 0.4,4.7 0.6,5.1 0.8,5.3 1.6,5.4 2.1,5.1 2.3,4.4 2.3,3.4 2.2,0.9 1.7,0.3 1,0.3 0.6,0.7 0.4,1.1 0.4,4.7 0.6,5.1 0.8,5.3 1.6,5.4 2.1,5.1 2.3,4.4 2.3,3.3 2.2,0.9 1.7,0.3 1,0.3 0.6,0.7 0.4,1.1 0.4,4.7 0.6,5.1 0.8,5.3 1.6,5.4 2.1,5.1 2.3,4.4 2.3,3.5 2.2,0.9 1.7,0.3 1,0.3 0.6,0.7 0.4,1.1 0.4,4.7 0.6,5.1 0.8,5.3 1.6,5.4 2.1,5.1 2.3,4.4 2.3,3.9 2.2,0.9 1.7,0.3 1,0.3 0.6,0.7 0.4,1.1 0.4,4.7 0.6,5.1 0.8,5.3 1.1,5.4 1.9,5.3 2.2,4.9 2.3,3.8 2.2,0.9 1.7,0.3 1,0.3 0.6,0.7 0.4,1.1 0.4,4.7 0.6,5.1 0.8,5.3 1.1,5.4 1.9,5.3 2.2,4.9 2.3,4 2.2,0.9 1.7,0.3 1,0.3 0.6,0.7 0.4,1.1 0.4,4.7 0.6,5.1 0.8,5.3 1.1,5.4 1.9,5.3 2.2,4.9 2.2,4.4 2.2,0.9 1.7,0.3 1,0.3 0.6,0.7 0.4,1.1 0.5,4.9 0.8,5.3 1.9,5.3 2.2,4.9 2.2,4.7 2.2,0.9 1.7,0.3 1,0.3 0.6,0.7 0.4,1.1 0.5,4.9 0.8,5.3 1.6,5.4 2.1,5.1 2.3,4.4 2.2,0.9 1.7,0.3 1,0.3 0.6,0.7 0.4,1.1 0.5,4.9 0.8,5.3 1.9,5.3 2.2,4.9 2.2,4.5 2.2,0.9 1.7,0.3 1,0.3 0.6,0.7 0.4,1.1 0.5,4.9 0.8,5.3 1.6,5.4 2.1,5.1 2.2,4.8 2.2,0.9 1.7,0.3 1,0.3 0.6,0.7 0.4,1.1 0.5,4.9 0.8,5.3 1.6,5.4 1.9,5.3 2,5.2 2.2,4.9 2.3,4.4 2.2,0.9 1.7,0.3 1,0.3 0.6,0.7 0.4,1.1 0.4,4.7 0.6,5.1 0.8,5.3 1.6,5.4 1.6,5.4 1.9,5.3 2.2,4.9 2.3,1.4 2.2,0.9 1.9,0.4 1,0.3 0.6,0.7 0.4,1.1 0.4,4.7 0.6,5.1 0.8,5.3 1.3,5.4 1.9,5.3 2.1,5.1 2.3,4.4 2.3,1.4 2.1,0.6 1.7,0.3 0.8,0.4 0.6,0.7 0.4,1.1 0.4,4.7 0.6,5.1 0.8,5.3 1,5.3 1.9,5.3 2.2,4.9 2.3,1.4 2.1,0.6 1.7,0.3 0.8,0.4 0.6,0.7 0.4,1.1 0.4,4.7 0.6,5.1 0.8,5.3 1.9,5.3 2.2,4.9 2.3,1.4 2.1,0.6 1.7,0.3 0.8,0.4 0.6,0.7 0.4,1.1 0.4,4.7 0.6,5.1 0.6,5 0.8,5.3 1.6,5.4 1.9,5.3 2.2,4.9 2.3,1.4 2.1,0.6 1.7,0.3 1,0.3 0.5,0.8 0.4,4.7 0.4,4.6 0.6,5.1 0.8,5.3 1.1,5.4 1.9,5.3 2.2,4.9 2.3,1.4 2.1,0.6 1.7,0.3 1,0.3 0.5,0.8 0.4,4.4 0.6,5.1 0.8,5.3 1.1,5.4 1.9,5.3 2.2,4.9 2.3,1.4 2.1,0.6 1.7,0.3 1,0.3 0.5,0.8 0.4,4 0.5,4.9 0.8,5.3 1.6,5.4 2.1,5.1 2.3,4.4 2.3,1.4 2.1,0.6 1.7,0.3 1,0.3 0.5,0.8 0.4,3.8 0.5,4.9 0.8,5.3 1.6,5.4 2.1,5.1 2.3,4.4 2.3,1.4 2.1,0.6 1.7,0.3 1,0.3 0.5,0.8 0.4,3.5 0.4,4.7 0.6,5.1 0.8,5.3 1.1,5.4 1.9,5.3 2.2,4.9 2.3,4.4 2.3,1.4 2.1,0.6 1.7,0.3 1,0.3 0.5,0.8 0.4,3.3 0.4,4.7 0.6,5.1 0.8,5.3 1.1,5.4 1.9,5.3 2.2,4.9 2.3,4.4 2.3,1.4 2.1,0.6 1.7,0.3 1,0.3 0.5,0.8 0.4,3.2 0.4,4.7 0.6,5.1 0.8,5.3 1.1,5.4 1.9,5.3 2.2,4.9 2.3,4.4 2.3,1.4 2.1,0.6 1.7,0.3 1,0.3 0.5,0.8 0.4,2.8 0.4,4.7 0.6,5.1 0.8,5.3 1.1,5.4 1.9,5.3 2.2,4.9 2.3,4.4 2.3,1.4 2.2,0.9 1.9,0.4 1,0.3 0.6,0.7 0.4,1.1 0.4,2.7 0.4,4.7 0.6,5.1 0.8,5.3 1.1,5.4 1.9,5.3 2.2,4.9 2.3,4.4 2.3,1.4 2.2,0.9 1.9,0.4 1,0.3 0.6,0.7 0.4,1.1 0.4,2.6 0.4,4.7 0.6,5.1 0.8,5.3 1.1,5.4 1.9,5.3 2.2,4.9 2.3,4.4 2.3,1.4 2.2,0.9 1.9,0.4 1,0.3 0.6,0.7 0.4,1.1 0.4,2.2 0.5,4.9 0.8,5.3 1.9,5.3 2.2,4.9 2.3,4.4 2.3,1.4 2.2,0.9 1.9,0.4 1,0.3 0.6,0.7 0.4,1.1 0.4,2.1 0.5,4.9 0.8,5.3 1.9,5.3 2.2,4.9 2.3,4.4 2.3,1.4 2.2,0.9 1.9,0.4 1,0.3 0.6,0.7 0.4,1.1 0.4,1.9 0.5,4.9 0.8,5.3 1.9,5.3 2.2,4.9 2.3,4.4 2.3,1.4 2.1,0.6 1.7,0.3 0.8,0.4 0.5,0.8 0.4,1.5 0.5,4.9 0.8,5.3 1.9,5.3 2.2,4.9 2.3,4.4 2.2,0.9 1.7,0.3 1,0.3 0.5,0.8 0.4,1.1 0.5,4.9 0.8,5.3 1.9,5.3 2.2,4.9 2.3,4.4 2.2,0.9 1.7,0.3 1,0.3 0.6,0.7 0.6,0.8 0.4,1.1 0.5,4.9 0.8,5.3 1.9,5.3 2.2,4.9 2.3,4.4 2.2,0.9 1.7,0.3 1,0.3 0.7,0.6 0.4,1.1 0.4,4.7 0.6,5.1 0.8,5.3 1.6,5.4 2.1,5.1 2.3,4.4 2.2,0.9 1.7,0.3 1,0.3 1,0.3 0.6,0.7 0.4,1.1 0.4,4.7 0.6,5.1 0.8,5.3 1.6,5.4 1.9,5.3 2.2,4.9 2.3,1.4 2.2,0.9 1.9,0.4 1.4,0.3 0.8,0.4 0.6,0.7 0.4,1.1 0.4,4.7 0.6,5.1 0.8,5.3 1.1,5.4 1.9,5.3 2.2,4.9 2.3,4.4 2.2,0.9 1.9,0.4 1.6,0.3 0.8,0.4 0.6,0.7 0.4,1.1 0.4,4.7 0.6,5.1 0.8,5.3 1.1,5.4 1.9,5.3 2.2,4.9 2.3,4.4 2.2,0.9 1.9,0.4 1.6,0.3 0.8,0.4 0.6,0.7 0.4,1.1 0.4,4.7 0.6,5.1 0.8,5.3 1.1,5.4 1.9,5.3 2.2,4.9 2.3,4.4 2.2,0.9 2.1,0.6 1.7,0.3 1.7,0.3 1,0.3 0.6,0.7 0.4,1.1 0.4,4.7 0.6,5.1 0.8,5.3 1.1,5.4 1.9,5.3 2.2,4.9 2.3,1.4 2.2,0.9 2,0.6 1.7,0.3 1,0.3 0.5,0.8 0.4,4.7 0.6,5.1 0.8,5.3 1.9,5.3 2.2,4.9 2.3,1.4 2.2,0.8 2.1,0.6 1.7,0.3 1,0.3 0.5,0.8 0.4,4.7 0.6,5.1 0.8,5.3 1.9,5.3 2.2,4.9 2.2,1 2.2,0.9 1.7,0.3 1,0.3 0.5,0.8 0.4,4.7 0.6,5.1 0.8,5.3 1.9,5.3 2.2,4.9 2.2,1.3 2.2,0.9 1.9,0.4 1,0.3 0.6,0.7 0.4,1.1 0.4,4.7 0.6,5.1 0.8,5.3 1.9,5.3 2.2,4.9 2.3,1.7 2.2,0.9 1.9,0.4 1,0.3 0.6,0.7 0.4,1.1 0.4,4.7 0.6,5.1 0.8,5.3 1.9,5.3 2.2,4.9 2.3,1.8 2.2,0.9 1.9,0.4 1,0.3 0.6,0.7 0.4,1.1 0.4,4.7 0.6,5.1 0.8,5.3 1.9,5.3 2.2,4.9 2.3,1.9 2.2,0.9 1.7,0.3 1,0.3 0.5,0.8 0.4,4.7 0.6,5.1 0.8,5.3 1.9,5.3 2.2,4.9 2.3,1.5 2.1,0.6 1.7,0.3 1,0.3 0.5,0.8 0.4,4.7 0.6,5.1 0.8,5.3 1.9,5.3 2.2,4.9 2.2,1.1 2.1,0.6 1.7,0.3 1,0.3 0.5,0.8 0.4,4.7 0.6,5.1 0.8,5.3 1.9,5.3 2.2,4.9 2.2,1.2 2.2,0.9 1.7,0.3 1,0.3 0.5,0.8 0.4,4.7 0.6,5.1 0.8,5.3 1.9,5.3 2.2,4.9 2.3,1.6 2.1,0.6 1.7,0.3 1,0.3 0.5,0.8 0.4,4.7 0.6,5.1 0.8,5.3 1.9,5.3 2.2,4.9 2.3,1.4;2.3,3.6 2.2,0.9 1.7,0.3 1,0.3 0.6,0.7 0.4,1.1 0.4,4.7 0.6,5.1 0.8,5.3 1.1,5.4 1.9,5.3 2.2,4.9 2.3,3.7 2.2,0.9 1.7,0.3 1,0.3 0.6,0.7 0.4,1.1 0.4,4.7 0.6,5.1 0.8,5.3 1.1,5.4 1.9,5.3 2.2,4.9 2.3,4.1 2.2,0.9 1.7,0.3 1,0.3 0.6,0.7 0.4,1.1 0.4,4.7 0.6,5.1 0.8,5.3 1.1,5.4 1.9,5.3 2.2,4.9 2.3,4.3 2.2,0.9 1.7,0.3 1,0.3 0.6,0.7 0.4,1.1 0.5,4.9 0.8,5.3 1.9,5.3 2.2,4.9 2.3,4.2 2.2,0.9 1.7,0.3 1,0.3 0.6,0.7 0.4,1.1 0.5,4.9 0.8,5.3 1.9,5.3 2.2,4.9 2.2,4.6 2.2,0.9 1.7,0.3 1,0.3 0.6,0.7 0.4,1.1 0.5,4.9 0.8,5.3 1.6,5.4 2.1,5.1 2.2,4.9 2.3,4.4 2.2,0.9 1.7,0.3 1,0.3 0.6,0.7 0.4,1.1 0.5,4.9 0.8,5.3 1.1,5.4 1.9,5.3 2.2,5 2.3,4.4 2.2,0.9 1.7,0.3 1,0.3 0.6,0.7 0.4,1.1 0.5,4.9 0.8,5.3 1.1,5.4 1.9,5.3 2.1,5.1 2.3,4.4 2.2,0.9 1.7,0.3 1,0.3 0.6,0.7 0.4,1.1 0.4,4.7 0.6,5.1 0.8,5.3 1.6,5.4 1.9,5.3 1.7,5.3 2.1,5.1 2.3,4.4 2.2,0.9 1.7,0.3 1,0.3 0.6,0.7 0.4,1.1 0.4,4.7 0.6,5.1 0.8,5.3 1.4,5.4 1.9,5.3 2.2,4.9 2.3,1.4 2.2,0.9 1.9,0.4 1,0.3 0.6,0.7 0.4,1.1 0.4,4.7 0.6,5.1 0.8,5.3 1.1,5.4 1.9,5.3 2.2,4.9 2.3,4.4 2.3,1.4 2.1,0.6 1.7,0.3 0.8,0.4 0.6,0.7 0.4,1.1 0.4,4.7 0.6,5.1 0.8,5.3 0.7,5.2 1.1,5.4 1.6,5.4 1.9,5.3 2.2,4.9 2.3,1.4 2.1,0.6 1.7,0.3 0.8,0.4 0.6,0.7 0.4,1.1 0.4,4.7 0.6,5.1 0.8,5.3 1.6,5.4 1.9,5.3 2.2,4.9 2.3,1.4 2.1,0.6 1.7,0.3 0.8,0.4 0.6,0.7 0.4,1.1 0.4,4.7 0.6,5.1 0.6,5.1 0.8,5.3 1.1,5.4 1.9,5.3 2.2,4.9 2.3,1.4 2.1,0.6 1.7,0.3 1,0.3 0.5,0.8 0.5,4.8 0.6,5.1 0.8,5.3 1.1,5.4 1.9,5.3 2.2,4.9 2.3,1.4 2.1,0.6 1.7,0.3 1,0.3 0.5,0.8 0.4,4.5 0.5,4.9 0.8,5.3 1.6,5.4 2.1,5.1 2.3,4.4 2.3,1.4 2.1,0.6 1.7,0.3 1,0.3 0.5,0.8 0.4,4.1 0.5,4.9 0.8,5.3 1.9,5.3 2.2,4.9 2.3,1.4 2.1,0.6 1.7,0.3 1,0.3 0.5,0.8 0.4,4.2 0.5,4.9 0.8,5.3 1.6,5.4 2.1,5.1 2.3,4.4 2.3,1.4 2.1,0.6 1.7,0.3 1,0.3 0.5,0.8 0.4,3.9 0.4,4.7 0.6,5.1 0.8,5.3 1.1,5.4 1.9,5.3 2.2,4.9 2.3,4.4 2.3,1.4 2.1,0.6 1.7,0.3 1,0.3 0.5,0.8 0.4,3.6 0.4,4.7 0.6,5.1 0.8,5.3 1.1,5.4 1.9,5.3 2.2,4.9 2.3,4.4 2.3,1.4 2.1,0.6 1.7,0.3 1,0.3 0.5,0.8 0.4,3.4 0.4,4.7 0.6,5.1 0.8,5.3 1.1,5.4 1.9,5.3 2.2,4.9 2.3,4.4 2.3,1.4 2.2,0.9 1.9,0.4 1,0.3 0.6,0.7 0.4,1.1 0.4,3 0.4,4.7 0.6,5.1 0.8,5.3 1.1,5.4 1.9,5.3 2.2,4.9 2.3,4.4 2.3,1.4 2.2,0.9 1.9,0.4 1,0.3 0.6,0.7 0.4,1.1 0.4,3.1 0.4,4.7 0.6,5.1 0.8,5.3 1.1,5.4 1.9,5.3 2.2,4.9 2.3,4.4 2.3,1.4 2.2,0.9 1.9,0.4 1,0.3 0.6,0.7 0.4,1.1 0.4,2.9 0.4,4.7 0.6,5.1 0.8,5.3 1.1,5.4 1.9,5.3 2.2,4.9 2.3,4.4 2.3,1.4 2.2,0.9 1.9,0.4 1,0.3 0.6,0.7 0.4,1.1 0.4,2.5 0.5,4.9 0.8,5.3 1.9,5.3 2.2,4.9 2.3,4.4 2.3,1.4 2.2,0.9 1.9,0.4 1,0.3 0.6,0.7 0.4,1.1 0.4,2.4 0.5,4.9 0.8,5.3 1.9,5.3 2.2,4.9 2.3,4.4 2.3,1.4 2.1,0.6 1.7,0.3 0.8,0.4 0.5,0.8 0.4,2 0.5,4.9 0.8,5.3 1.9,5.3 2.2,4.9 2.3,4.4 2.2,0.9 1.7,0.3 1,0.3 0.5,0.8 0.4,1.6 0.5,4.9 0.8,5.3 1.9,5.3 2.2,4.9 2.3,4.4 2.3,1.4 2.1,0.6 1.7,0.3 0.8,0.4 0.5,0.8 0.4,1.7 0.5,4.9 0.8,5.3 1.9,5.3 2.2,4.9 2.3,4.4 2.2,0.9 1.7,0.3 1,0.3 0.6,0.7 0.4,1.4 0.5,4.9 0.8,5.3 1.9,5.3 2.2,4.9 2.3,4.4 2.2,0.9 1.7,0.3 1,0.3 0.6,0.7 0.4,1.2 0.5,4.9 0.8,5.3 1.9,5.3 2.2,4.9 2.3,4.4 2.2,0.9 1.7,0.3 1,0.3 0.5,0.8 0.4,1.1 0.5,4.9 0.8,5.3 1.9,5.3 2.2,4.9 2.3,4.4 2.2,0.9 1.7,0.3 1,0.3 0.6,0.7 0.6,0.7 0.4,1.1 0.4,4.7 0.6,5.1 0.8,5.3 1.6,5.4 2.1,5.1 2.3,4.4 2.2,0.9 1.7,0.3 0.8,0.4 0.8,0.4 0.6,0.7 0.4,1.1 0.4,4.7 0.6,5.1 0.8,5.3 1.6,5.4 1.9,5.3 2.2,4.9 2.3,1.4 2.2,0.9 1.9,0.4 1.1,0.3 0.8,0.4 0.6,0.7 0.4,1.1 0.4,4.7 0.6,5.1 0.8,5.3 1.1,5.4 1.9,5.3 2.2,4.9 2.3,4.4 2.2,0.9 1.9,0.4 1.5,0.3 1,0.3 0.6,0.7 0.4,1.1 0.4,4.7 0.6,5.1 0.8,5.3 1.1,5.4 1.9,5.3 2.2,4.9 2.3,1.4 2.2,0.9 1.9,0.4 1.7,0.3 1,0.3 0.6,0.7 0.4,1.1 0.4,4.7 0.6,5.1 0.8,5.3 1.1,5.4 1.9,5.3 2.2,4.9 2.3,1.4 2.1,0.6 1.7,0.3 1,0.3 0.5,0.8 0.4,4.7 0.6,5.1 0.8,5.3 1.9,5.3 2.2,4.9 2.2,0.9;1.9,5.3 2.2,4.9 2.3,4.4 2.2,0.9 1.7,0.3 1,0.3 0.6,0.7 0.4,1.1 0.4,4.7 0.6,5.1 0.8,5.3 1.5,5.4 1.9,5.3 2.2,4.9 2.3,1.4 2.2,0.9 1.9,0.4 1,0.3 0.6,0.7 0.4,1.1 0.4,4.7 0.6,5.1 0.8,5.3 1.5,5.4 1.9,5.3 2.1,5.1 2.3,4.4 2.3,1.4 2.1,0.6 1.7,0.3 0.8,0.4 0.6,0.7 0.4,1.1 0.4,4.7 0.6,5.1 0.8,5.3 1.2,5.4 1.9,5.3 2.2,4.9 2.3,1.4 2.1,0.6 1.7,0.3 0.8,0.4 0.6,0.7 0.4,1.1 0.4,4.7 0.6,5.1 0.9,5.3;0.5,0.9 0.5,4.9 0.8,5.3 1.9,5.3 2.2,4.9 2.3,4.4 2.2,0.9 1.7,0.3 1,0.3 0.6,0.7 0.4,1.3 0.5,4.9 0.8,5.3 1.9,5.3 2.2,4.9 2.3,4.4 2.2,0.9 1.7,0.3 1,0.3 0.6,0.7 0.5,1 0.5,4.9 0.8,5.3 1.9,5.3 2.2,4.9 2.3,4.4 2.2,0.9 1.7,0.3 1,0.3 0.6,0.7 0.6,0.6 0.4,1.1 0.4,4.7 0.6,5.1 0.8,5.3 1.6,5.4 2.1,5.1 2.3,4.4 2.2,0.9 1.7,0.3 1,0.3 0.6,0.6 0.4,1.1 0.4,4.7 0.6,5.1 0.8,5.3 1.6,5.4 2.1,5.1 2.3,4.4 2.2,0.9 1.7,0.3 1,0.3 0.8,0.5 0.8,0.4 0.6,0.7 0.4,1.1 0.4,4.7 0.6,5.1 0.8,5.3 1.6,5.4 1.9,5.3 2.2,4.9 2.3,1.4 2.1,0.6 1.7,0.3 1.2,0.3 0.8,0.4 0.6,0.7 0.4,1.1 0.4,4.7 0.6,5.1 0.8,5.3 1.6,5.4 1.9,5.3 2.2,4.9 2.3,1.4 2.1,0.6 1.7,0.3 1.3,0.3;0.5,4.9 0.8,5.3 1.6,5.4 1.9,5.3 2.2,4.9 2.3,1.4 2.1,0.6 1.7,0.3 1,0.3 0.5,0.8 0.5,4.9 0.6,5.1 0.8,5.3 1.1,5.4 1.9,5.3 2.2,4.9 2.3,1.4 2.1,0.6 1.7,0.3 1,0.3 0.5,0.8 0.4,4.7 0.6,5.1 0.8,5.3 1.1,5.4 1.9,5.3 2.2,4.9 2.3,1.4 2.1,0.6 1.7,0.3 1,0.3 0.5,0.8 0.5,4.7 0.5,4.9 0.8,5.3 1.9,5.3 2.2,4.9 2.3,1.4 2.1,0.6 1.7,0.3 1,0.3 0.5,0.8 0.4,4.3;0.4,1.8 0.5,0.8 0.8,0.4 1.7,0.3 2.1,0.6 2.3,1.4 2.3,4.4 2.2,4.9 1.9,5.3 0.8,5.3 0.5,4.9 0.4,1.8;1.8,5.3 0.8,5.3 0.6,5.1 0.4,4.7 0.4,1.1 0.6,0.7 1,0.3 1.7,0.3 2.2,0.9 2.3,4.4 2.2,4.9 1.8,5.3;0.9,0.4 1.9,0.4 2.2,0.9 2.3,1.4 2.2,4.9 1.9,5.3 1.6,5.4 0.8,5.3 0.6,5.1 0.4,4.7 0.4,1.1 0.6,0.7 0.9,0.4;1.8,0.4 1,0.3 0.6,0.7 0.4,1.1 0.4,4.7 0.6,5.1 0.8,5.3 1.1,5.4 1.9,5.3 2.2,4.9 2.3,4.4 2.3,1.4 2.2,0.9 1.8,0.4 1.7,0.3 1,0.3 0.6,0.7 0.4,1.1 0.4,4.7 0.6,5.1 0.8,5.3 1.1,5.4 1.9,5.3 2.2,4.9 2.3,1.4 2.2,0.9 1.9,0.5 1.7,0.3 1,0.3 0.6,0.7 0.4,1.1 0.4,4.7 0.6,5.1 0.8,5.3 1.1,5.4 1.9,5.3 2.2,4.9 2.3,1.4 2.1,0.7;0.4,2.3 0.4,1.1 0.6,0.7 1,0.3 1.9,0.4 2.2,0.9 2.3,1.4 2.3,4.4 2.2,4.9 1.9,5.3 0.8,5.3 0.5,4.9 0.4,2.3;2.3,2 2.2,0.9 1.9,0.4 1,0.3 0.6,0.7 0.4,1.1 0.4,4.7 0.6,5.1 0.8,5.3 1.9,5.3 2.2,4.9 2.3,2;0.4,3.7 0.5,0.8 1,0.3 1.7,0.3 2.1,0.6 2.3,1.4 2.3,4.4 2.1,5.1 1.6,5.4 0.8,5.3 0.6,5.1 0.4,4.7 0.4,3.7;0.7,-1.3 0.7,-0.3;2,-1.3 2,-0.3'),
    'Ü': (3.3, '0.4,0.5 0.4,4.1 0.6,5.1 0.6,5.1 1.1,5.4 1.6,5.4 2,5.2 2.2,4.9 2.3,4.3 2.3,0.4;0.7,-1.3 0.7,-0.3;2,-1.3 2,-0.3'),
    'ß': (3.4, '2.2,3.46389 1.7,3.06389 1.9,2.16389 2.2,1.66389 2.2,0.763889 0.4,0.863889 0.4,5.76389;2.2,3.46389 2.4,4.06389 2.3,5.36389 2.1,5.66389 1.6,5.76389'),
    '-': (2.3, '0.4,2.8 1.4,2.8'),
    '.': (1.6, '0.4,4.76389 0.4,5.76389'),
    ',': (1.6, '0.4,5.3 0.5,5.8 0.3,6.6'),
    ':': (1.6, '0.4,1.66389 0.4,2.66389;0.4,4.76389 0.4,5.76389'),
    ';': (1.6, '0.2,6.7 0.4,6.3 0.6,5.8 0.5,5.3;0.5,1.7 0.5,2.7'),
    '!': (1.8, '0.4,3.76389 0.4,0.363889;0.4,4.76389 0.4,5.76389'),
    '?': (3.0, '0.4,1.46389 0.5,0.763889 0.7,0.463889 1,0.263889 1.7,0.263889 2,0.563889 2.2,1.26389 2,1.96389 1.9,2.36389 1.2,3.46389 1.2,3.86389;1.2,4.76389 1.2,5.76389'),
    '+': (3.3, '1.4,1.8 1.4,2.8 1.4,4;0.3,2.8 1.4,2.8 2.5,2.8'),
    '*': (3.5, '1.6,0.2 1.6,1.4 1.5,1.7 1,2.4 0.9,2.6 1,2.4;1.5,1.7 1.5,1.5 1.2,1.4 0.3,1.2;1.5,1.7 1.7,1.7 2,2.2 2.3,2.6;1.5,1.7 1.9,1.4 2.2,1.4 2.8,1.2;2.5,1.3 2.2,1.4'),
    '/': (3.2, '0.4,5.56389 0.1,5.76389;0.4,5.56389 2.4,0.663889 2.7,0.263889'),
    '(': (2.3, '0.6,0.2 1,-0.1 1.2,-0.1;0.6,0.2 0.4,1 0.4,4.7 0.6,5.6 0.6,5.6 0.8,5.8 1.1,5.8'),
    ')': (2.3, '0.3,-0.1 0.8,0.1 1,0.6 1,5.1 0.9,5.6 0.3,5.8'),
    '[': (2.3, '1,5.8 0.4,5.8 0.5,-0 0.5,-0.1;0.5,-0 1,-0.1'),
    ']': (2.3, '0.3,-0.1 1,0 1,5.7 0.9,5.8 0.3,5.8'),
    '=': (3.3, '0.3,3.5 2.4,3.5;0.3,2.2 2.4,2.2'),
    '%': (4.9, '1.1,5.6 1.4,4.9 1.7,4 1.8,3.6 2.2,2.7 2.5,1.8 3,0.6 3.2,0.2 3.2,0.1;1.3,2.8 1.1,2.9 0.6,2.9 0.3,2.5 0.3,0.4 0.8,0.1 1.2,0.3;2.7,1.5 2.5,1.8;3.8,2.9 4,3.1 4,3.7 4,4.7 3.8,5.4 3.8,5.5'),
    '#': (3.4, '2.4,0.563889 2.3,1.86389 2,4.06389 1.9,5.66389;2.8,1.86389 2.3,1.86389 1,1.96389 0.5,1.96389;2.5,4.06389 2,4.06389 0.7,4.06389 0.3,4.06389;1.2,0.563889 1,0.863889 1,1.96389 0.7,4.06389 0.6,5.76389'),
    '&': (3.5, '2.3,2.2 2.3,2.7 2.3,5.1 2.3,5.3 2.3,5.2;2.3,5.1 1.5,5.2 1,5.4 0.7,5.2 0.4,4.8 0.5,3.4 0.7,3.1 1,2.7;2,0.3 1,0.4 0.6,0.8;0.6,0.7 0.6,0.8 0.5,1.7 0.7,2.2 1,2.7 1,2.8;1,2.7 2.3,2.7 2.6,2.7'),
    '@': (5.8, '4.4,5.1 4.1,5.5 3.3,5.9 2,5.9 1.1,5.4 0.8,5.1 0.3,4 0.3,2.8 0.6,1.8 0.9,1.1 1.3,0.6 2.1,0.1 2.9,-0.1 3.6,0 4.5,0.5 4.9,1.1 5,1.6 5,2.6 4.8,3.3 4.7,3.8 4.3,4.2 3.7,4.2 3.5,4.1 3,4 2.2,4.2 2,4 1.8,3.5 1.9,2.7 1.9,2.3 2.2,1.9 2.4,1.7 2.6,1.7 3,1.9 3.6,2;3.7,1.6 3.6,2 3.5,4.1 3.5,4.1'),
    '°': (3.3, '0.6,0.3 0.8,0.2 1.4,0.3;0.6,0.3 0.3,0.8 0.3,1.3 0.6,1.6;1.4,0.3 1.7,0.6 1.7,0.9 1.7,1.3 1.4,1.6;0.6,1.6 1.4,1.6'),
    "'": (1.6, '0.3,1.5 0.4,0.3'),
    '<': (3.3, '2.3,1.8 1.9,2 1,2.4 0.5,2.8 0.5,2.8 0.6,2.6 0.5,2.8 0.5,2.9 0.7,3.2 1.9,3.7 2.2,3.8;2.3,1.7 2.3,1.8 1.9,2.1'),
    '>': (3.3, '0.2,1.9 0.6,2 1.8,2.6 1.9,2.7 1.9,3 1.9,3.1;1.9,3 1.7,3.3 0.6,3.7 0.2,4'),
    '_': (2.5, '2.1,6.2 0.3,6.2'),
    ' ': (2.6, ''),
}

# R82: Bebas Neue is a CAPS font - lowercase prints as capitals. The literal
# above carries only the capitals; the lowercase slots are cloned from them at
# import time (slightly tighter advance), so 'Garage!' prints as 'GARAGE!'.
for _c in 'ABCDEFGHIJKLMNOPQRSTUVWXYZÄÖÜ':
    _lc = _c.lower()
    if _lc != _c and _lc not in FONT_CAPS:
        FONT_CAPS[_lc] = (round(FONT_CAPS[_c][0] * 0.92, 1), FONT_CAPS[_c][1])
del _c, _lc


def _parse_stroke_str(s):
    """'x,y x,y;x,y x,y' -> [[(x,y),..], ..]"""
    out = []
    for part in s.split(';'):
        pts = []
        for tok in part.split():
            try:
                xs, ys = tok.split(',')
                pts.append((float(xs), float(ys)))
            except ValueError:
                pass
        if len(pts) >= 2:
            out.append(pts)
    return out


# R82: selectable label fonts -> (data, meta, monospaced?). The three new
# ones are optimized for SMALL text: narrow + tall x-height = readable at
# 2.8-3 mm caps where SMOOTH already blurs (stroke density per mm is lower).
_LABEL_STROKE_FONTS = {
    'SMOOTH': (FONT_SMOOTH, FONT_META_SMOOTH, False),
    'MONO':   (FONT_MONO, FONT_META_MONO, True),
    'COND':   (FONT_COND, FONT_META_COND, False),
    'NARROW': (FONT_NARROW, FONT_META_NARROW, False),
    'CAPS':   (FONT_CAPS, FONT_META_CAPS, False),
}
_LABEL_FONT_CACHE = {}


def _label_glyphs(font):
    """font name -> {'height', 'baseline', 'cap_top', 'x_top', 'desc_bot',
    'cap_units', 'x_units', ' ': (adv, []), char: (adv, strokes)}.

    R73: the stroke fonts are BASELINE-ALIGNED (uy = 'baseline' on the baseline,
    cap tops near uy = 'cap_top', x-height tops at 'x_top', descenders down to
    'desc_bot'). 'cap_units'/'x_units' are the printed heights of a cap / a
    lowercase letter. _glyph_class() says whether a character renders FULL
    (cap height) or SMALL (x-height, like lowercase, @, >).
    """
    if font in _LABEL_FONT_CACHE:
        return _LABEL_FONT_CACHE[font]
    glyphs = {' ': (8.0 if font == 'PIXEL' else 7.0 if font == 'MONO' else 3.0, [])}
    if font == 'PIXEL':
        glyphs['height'] = 9.0
        for ch, rows in FONT_PIXEL.items():
            sts = []
            for r, row in enumerate(rows):
                c = 0
                while c < 7:
                    if row & (1 << (6 - c)):
                        c2 = c
                        while c2 < 7 and row & (1 << (6 - c2)):
                            c2 += 1
                        if c2 - c >= 2:
                            sts.append([(float(c), float(r) + 0.5), (float(c2), float(r) + 0.5)])
                        else:
                            sts.append([(float(c) + 0.2, float(r) + 0.5),
                                        (float(c) + 0.8, float(r) + 0.5)])
                        c = c2
                    else:
                        c += 1
            glyphs[ch] = (8.0, sts)
    elif font in _LABEL_STROKE_FONTS:
        data, meta, is_mono = _LABEL_STROKE_FONTS[font]
        glyphs['height'] = 10.0
        if is_mono:
            for ch, s in data.items():
                glyphs[ch] = (7.0, _parse_stroke_str(s))
            glyphs[' '] = (7.0, [])
        else:
            for ch, (adv, s) in data.items():
                glyphs[ch] = (float(adv), _parse_stroke_str(s))
    else:
        # unknown name (or a saved PIXEL selection) -> SMOOTH
        glyphs['height'] = 10.0
        for ch, (adv, s) in FONT_SMOOTH.items():
            glyphs[ch] = (float(adv), _parse_stroke_str(s))
    # ---- R73 runtime vertical metrics (from the real skeleton geometry) ----
    # the baseline sits at uy = cap units in every stroke font's box
    base = {'PIXEL': 6.5}.get(font, _LABEL_STROKE_FONTS.get(
        font, _LABEL_STROKE_FONTS['SMOOTH'])[1]['cap'])
    tops = {}
    for ch, v in glyphs.items():
        if ch in (' ', 'height') or not v[1]:
            continue
        ys = [p[1] for st in v[1] for p in st]
        tops[ch] = (min(ys), max(ys))
    # cap line from the PLAIN A-Z only (umlaut dots sit above it and would
    # pull the line up); median so round overshoot (O, G) cannot skew it
    caps = [c for c in 'ABCDEFGHIJKLMNOPQRSTUVWXYZ' if c in tops]
    xs_ = [c for c in 'xonmuvwz' if c in tops]
    dess = [c for c in 'gjpqy\u00df,;' if c in tops]
    cap_sorted = sorted(tops[c][0] for c in caps)
    cap_top = cap_sorted[len(cap_sorted) // 2] if cap_sorted else base - 5.0
    x_top = sorted(tops[c][0] for c in xs_)[len(xs_) // 2] if xs_ else cap_top
    desc_bot = max((tops[c][1] for c in dess), default=base + 1.7)
    glyphs['baseline'] = base
    glyphs['cap_top'] = cap_top
    glyphs['x_top'] = x_top
    glyphs['desc_bot'] = desc_bot
    glyphs['cap_units'] = max(1.0, base - cap_top)
    glyphs['x_units'] = max(0.5, base - x_top)
    glyphs['height'] = desc_bot
    _LABEL_FONT_CACHE[font] = glyphs
    return glyphs


def _glyph_class(ch, font):
    """FULL (cap height) or SMALL (x-height) for one character (R73).

    User rule (R73 field log): lowercase letters - and correspondingly small
    signs like @ > < - print at 66% of the cap height, uppercase letters and
    digits at the full cap height. Plain geometric class, font-independent.
    """
    if 'A' <= ch <= 'Z' or ch in '\u00c4\u00d6\u00dc' or '0' <= ch <= '9':
        return 'FULL'
    return 'SMALL'    # lowercase (incl. umlauts/sz), punctuation, @ > < degree


def _label_text(text, font):
    """text -> (width_units, height_units, strokes [(x,y)..] with x offsets)"""
    glyphs = _label_glyphs(font)
    x = 0.0
    strokes = []
    for ch in text:
        adv, sts = glyphs.get(ch, glyphs.get(ch.upper(), (4.0, [])))
        for st in sts:
            strokes.append([(x + px, py) for (px, py) in st])
        x += adv
    return x, glyphs['height'], strokes


def _stroke_offsets(pts, half, step):
    """R72: stroke skeleton -> parallel offset paths covering [-half, +half]
    SOLIDLY (line spacing = step = one extrusion width). The outermost paths
    are the two walls, the paths between them are the fill - the field log
    (.55) showed single-line characters are too fragile on a label.
    Mitered vertex offsets; the miter scale is capped so sharp skeleton
    corners cannot spike. Returns a list of point lists (print order:
    +half .. -half, serpentine-ready)."""
    # drop consecutive duplicate points (thinned skeletons contain them) -
    # a vertex without any adjacent segment would have no normal at all
    ded = [pts[0]]
    for q in pts[1:]:
        if math.hypot(q[0] - ded[-1][0], q[1] - ded[-1][1]) > 1e-6:
            ded.append(q)
    pts = ded
    segs = []
    for i in range(len(pts) - 1):
        dx, dy = pts[i + 1][0] - pts[i][0], pts[i + 1][1] - pts[i][1]
        d = math.hypot(dx, dy)
        if d > 1e-6:
            segs.append((i, dx / d, dy / d))
    if not segs:
        return []
    nrm = []
    for j in range(len(pts)):
        n1 = n2 = None
        for (i, ux, uy) in segs:
            if i == j - 1:
                n1 = (-uy, ux)
            elif i == j:
                n2 = (-uy, ux)
        if n1 is None:
            n1 = n2
        if n2 is None:
            n2 = n1
        dot = n1[0] * n2[0] + n1[1] * n2[1]
        bx, by = n1[0] + n2[0], n1[1] + n2[1]
        bl = math.hypot(bx, by)
        if bl < 1e-6:
            nx, ny = n1
            m = 1.0
        else:
            m = 1.0 / max(0.62, math.sqrt(max(0.0, (1.0 + dot) / 2.0)))
            nx, ny = bx / bl * m, by / bl * m
        nrm.append((nx, ny))
    # line CENTERS reach +/-(half - step/2) so the covered width (each line is
    # 'step' wide) is exactly 2*half - symmetric, never one line wider.
    edge = half - step / 2.0
    if edge <= 0.05:
        return [list(pts)]          # stroke ~ one extrusion line: center line only
    n = int(math.ceil(2.0 * edge / step - 1e-9)) + 1
    if n < 2:
        n = 2
    edge2 = (n - 1) * step / 2.0
    if edge2 > edge + 1e-9:
        n -= 1
        edge2 = (n - 1) * step / 2.0
        # prefer one MORE line when the resulting width overshoots only a
        # little (<= 0.35*step): the stroke then matches the requested width
        if n >= 2 and (2.0 * (edge2 + step / 2.0) + step) - 2.0 * half <= 0.35 * step:
            n += 1
            edge2 = (n - 1) * step / 2.0
    return [[(x + nx * (edge2 - k * step), y + ny * (edge2 - k * step))
             for (x, y), (nx, ny) in zip(pts, nrm)] for k in range(n)]

def _label_layout(w, h, hole_side, hole_d):
    """R73: hole + text box.

    The hole now sits CLOSE TO THE EDGE (2mm rim - key rings clip through
    easily; the old golden-ratio band parked it up to 11mm from the edge).
    The text box is the label inset on the THREE sides without the hole -
    the text centers between exactly those sides, away from the hole.
    Local label coords: x 0..w left->right, y 0..h, y=h = 'top' of the label.
    """
    # R80: proportional margins (~7% - user spec: 5-10% air to the border
    # AND to the hole), at least 1.5mm
    m = max(1.5, 0.07 * min(w, h))
    edge = 2.0                      # rim between label edge and hole edge
    if hole_side in (1, 2) and hole_d > 0:      # left / right
        d = max(2.5, min(float(hole_d), h - 2 * edge - 2.0, 16.0))
        cx = edge + d / 2.0 if hole_side == 1 else w - edge - d / 2.0
        cy = h / 2.0
        band = edge + d + max(2.0, 0.07 * min(w, h))   # hole zone + clearance
        if hole_side == 1:
            box = (band, m, w - m, h - m)
        else:
            box = (m, m, w - band, h - m)
        return (cx, cy, d / 2.0), box, d
    if hole_side in (3, 4) and hole_d > 0:      # top / bottom
        d = max(2.5, min(float(hole_d), w - 2 * edge - 2.0, 16.0))
        cy = h - edge - d / 2.0 if hole_side == 3 else edge + d / 2.0
        cx = w / 2.0
        band = edge + d + max(2.0, 0.07 * min(w, h))
        if hole_side == 3:
            box = (m, m, w - m, h - band)
        else:
            box = (m, band, w - m, h - m)
        return (cx, cy, d / 2.0), box, d
    return None, (m, m, w - m, h - m), 0.0


def _label_metrics(lines, font, spacing=0.0):
    """R80: parse label lines once - glyph items, natural width (units),
    ascender overshoot, descender. Shared by the fit math (make_labels,
    auto-grow) and the path builder (_label_text_lines)."""
    g = _label_glyphs(font)
    if not lines:
        raise ValueError('empty label text')
    parsed = []
    for text in lines:
        items = []
        w_units = 0.0
        drawable = False
        for ch in text:
            v = g.get(ch) or g.get(ch.upper())
            if ch == ' ':
                items.append((ch, g[' '][0], None))
                w_units += g[' '][0]
                continue
            if not v or not v[1]:
                items.append((ch, 3.0, None))
                w_units += 3.0
                continue
            items.append((ch, v[0], v))
            w_units += v[0]
            drawable = True
        if not drawable:
            raise ValueError('label line "%s" has no drawable text '
                             '(only spaces/unknown signs)' % text[:16])
        asc_u = 0.0
        has_desc = False
        for ch, _adv, v in items:
            if v is None:
                continue
            if ch in 'gjpqy\u00df,;':
                has_desc = True
            ys = [p[1] for st in v[1] for p in st]
            top = min(ys)
            if top < g['cap_top']:
                asc_u = max(asc_u, g['cap_top'] - top)
        parsed.append({'text': text, 'items': items, 'w_units': w_units,
                       'asc_u': asc_u, 'desc_u': (g['desc_bot'] - g['baseline']) if has_desc else 0.0})
    return g, parsed


def _label_autocap(g, parsed, bw, bh, spacing=0.0, stroke_w=0.0, fill=0.94):
    """R80: the largest uniform cap height at which the WHOLE text block fits
    the usable box (all lines share ONE scale, ~94% fill - user spec: use the
    label, do not waste a quarter of the width like the old 75% rule)."""
    n = len(parsed)
    gap0 = max(1.0, 0.55 * stroke_w + 0.4)
    cu = g['cap_units']
    max_w = max(p['w_units'] for p in parsed)
    max_chars = max(len(p['text']) for p in parsed)
    band_units = sum(cu + p['asc_u'] + p['desc_u'] for p in parsed)
    cap_w = (bw * fill - spacing * (max_chars - 1)) * cu / max(max_w, 0.01)
    cap_h = (bh * fill - gap0 * (n - 1)) * cu / max(band_units, 0.01)
    return max(0.1, min(cap_w, cap_h))


def _label_need_size(g, parsed, cap, spacing=0.0, stroke_w=0.0, fill=0.94):
    """R80: usable (bw, bh) needed so the block prints at exactly `cap` mm
    caps - the inverse of _label_autocap, drives the label AUTO-GROW."""
    n = len(parsed)
    gap0 = max(1.0, 0.55 * stroke_w + 0.4)
    s = cap / g['cap_units']
    max_w = max(p['w_units'] for p in parsed)
    max_chars = max(len(p['text']) for p in parsed)
    bw = (max_w * s + spacing * (max_chars - 1)) / fill
    bh = (sum((g['cap_units'] + p['asc_u'] + p['desc_u']) * s for p in parsed)
          + gap0 * (n - 1)) / fill
    return bw, bh


def _label_grow_fit(all_lines, font, w, h, font_size, spacing, stroke_w,
                    hole_side, hole_d, floor_cap=2.8):
    """R83: the AUTO-FIT + AUTO-GROW pass, shared by make_labels and
    label_preview (the LCD 'Fit' item shows the SAME numbers the generator
    will print). Caps raised for big signs: width up to 240mm, height to
    220mm (the bed fit check still rejects impossible plates)."""
    mcache = [_label_metrics(ls, font, spacing) for ls in all_lines]
    w_cap = min(w * 1.75 + 10.0, 240.0)
    h_cap = min(h * 1.75 + 8.0, 220.0)
    w0, h0 = w, h
    for _it79 in range(4):
        grew = False
        _c79, box79, _d79 = _label_layout(w, h, hole_side, hole_d)
        bw79 = box79[2] - box79[0]
        bh79 = box79[3] - box79[1]
        for g79, parsed79 in mcache:
            auto79 = _label_autocap(g79, parsed79, bw79, bh79, spacing, stroke_w)
            if font_size and float(font_size) > 0:
                want79 = float(font_size)
            elif auto79 >= floor_cap:
                continue
            else:
                want79 = floor_cap
            nbw79, nbh79 = _label_need_size(g79, parsed79, want79, spacing, stroke_w)
            if nbw79 > bw79 + 0.5 or nbh79 > bh79 + 0.5:
                wn79 = min(w + max(nbw79 - bw79, 0.0), w_cap)
                hn79 = min(h + max(nbh79 - bh79, 0.0), h_cap)
                if wn79 > w + 0.05 or hn79 > h + 0.05:
                    w, h = round(wn79, 1), round(hn79, 1)
                    grew = True
        if not grew:
            break
    grown79 = (w > w0 + 0.05) or (h > h0 + 0.05)
    return w, h, grown79, mcache


def _label_text_lines(lines, font, box, w, h, font_size=0.0, spacing=0.0,
                      min_gap=1.0, stroke_w=0.0):
    """R80 label typography v3 (user spec, field log .63):

    - up to 3 lines per label, ONE UNIFORM scale: letters never stretch
    - font_size > 0: TARGET cap height - make_labels GROWS the label so it
      fits (within limits); 0 = AUTO: as large as the label allows (94% fill)
    - NO more 'does not fit' errors: the label adapts, the text stays.
      Only a degenerate <1.6mm font (unreadable with any nozzle) still refuses.
    - lines stack centered (only FILLED lines count), gap keeps the stroke
      clear, block centered between the three sides without the hole
    Returns (paths [(x, y) mm label-local, y UP], metrics dict).
    """
    g, parsed = _label_metrics(lines, font, spacing)
    bw = box[2] - box[0]
    bh = box[3] - box[1]
    spacing = max(0.0, min(float(spacing or 0.0), 0.25 * bw))
    # ---- ONE uniform scale -----------------------------------------------------
    auto = _label_autocap(g, parsed, bw, bh, spacing, stroke_w)
    cap_mm = float(font_size) if (font_size and float(font_size) > 0) else auto
    # a target the (grown) label cannot hold falls back to auto - safety net,
    # make_labels normally grows the label so the target fits
    need_w, need_h = _label_need_size(g, parsed, cap_mm, spacing, stroke_w)
    if need_w > bw + 0.5 or need_h > bh + 0.5:
        cap_mm = min(cap_mm, auto)
    if cap_mm < 1.6:
        longest = max(parsed, key=lambda p: p['w_units'])
        raise ValueError('text "%s" is too long even for a grown label '
                         '(%.1fmm caps) - shorten it or allow a bigger label'
                         % (longest['text'][:16], cap_mm))
    s = cap_mm / g['cap_units']
    # ---- vertical layout: bands + gaps, block centered --------------------------
    bands = [(g['cap_units'] + p['asc_u'] + p['desc_u']) * s for p in parsed]
    n = len(parsed)
    gap0 = max(min_gap, 0.55 * stroke_w + 0.4)
    tot0 = sum(bands) + gap0 * (n - 1)
    free = bh - tot0
    gap = gap0 + (min(free * 0.5 / max(n - 1, 1), max(0.0, 1.0 * cap_mm - gap0)) if n > 1 else 0.0)
    tot = sum(bands) + gap * (n - 1)
    y_top = box[1] + (bh - tot) / 2.0 + tot      # top of the block (walk down)
    paths = []
    small_cap = 0.66 * cap_mm
    cur_top = y_top
    for p in parsed:
        asc_mm = p['asc_u'] * s
        desc_mm = p['desc_u'] * s
        baseline = cur_top - asc_mm - cap_mm
        line_w = p['w_units'] * s + spacing * (len(p['text']) - 1)
        x_cur = box[0] + (bw - line_w) / 2.0
        for ch, adv, v in p['items']:
            if v is None:
                x_cur += adv * s + spacing
                continue
            _a, sts = v
            ys = [p2[1] for st in sts for p2 in st]
            top = min(ys)
            sy_g = s
            if ch in '@<>\u00b0' and top < g['baseline']:
                extent = g['baseline'] - top
                if extent > 0.05:
                    sy_g = min(s, (small_cap / cap_mm) * s * g['cap_units'] / extent)
            for st in sts:
                pts = [(x_cur + px * s,
                        baseline + (g['baseline'] - py) * sy_g) for (px, py) in st]
                if len(pts) >= 2:
                    paths.append(pts)
            x_cur += adv * s + spacing
        cur_top -= (g['cap_units'] + p['asc_u'] + p['desc_u']) * s + gap
    return paths, {'cap_h': cap_mm, 's': s, 'lines': n,
                   'line_w': max(p['w_units'] * s + spacing * (len(p['text']) - 1)
                                 for p in parsed)}


def _decimate(pts, tol=0.10):
    """R73: drop micro segments + merge near-collinear vertices. The .56 label
    jobs froze the printer ('MCU overload') - dense stroke geometry at high
    feed rates is gone: fewer, longer moves at slower feeds instead."""
    if len(pts) < 3:
        return pts
    out = [pts[0]]
    for p in pts[1:]:
        if math.hypot(p[0] - out[-1][0], p[1] - out[-1][1]) >= tol:
            out.append(p)
    if len(out) > 2:
        res = [out[0]]
        for i in range(1, len(out) - 1):
            a, b, c = res[-1], out[i], out[i + 1]
            abx, aby = b[0] - a[0], b[1] - a[1]
            bcx, bcy = c[0] - b[0], c[1] - b[1]
            lab = math.hypot(abx, aby)
            lbc = math.hypot(bcx, bcy)
            if lab < 1e-9 or lbc < 1e-9:
                continue
            # distance of b from the straight line a->c
            acx, acy = c[0] - a[0], c[1] - a[1]
            lac = math.hypot(acx, acy)
            if lac < 1e-9:
                continue
            dist = abs(abx * acy - aby * acx) / lac
            if dist < tol:
                continue                        # collinear -> drop b
            res.append(b)
        res.append(out[-1])
        out = res
    return out


class _Pen:
    """tiny gcode writer with travel/retract/z-hop state (M83 relative E)"""

    def __init__(self, lines, retracts=True, jump_d=2.5):
        self.L = lines
        self.x = None
        self.y = None
        self.z = None
        self.ret = True
        self.retracts = retracts
        # R77: retract/hop only for jumps LONGER than jump_d. 2.5mm fired
        # between neighboring hatch lines (field log: retract storm = the
        # label base tore apart, the filament was 'pulled away'). Print
        # files use 6mm - only real feature jumps (label->label, ->tower)
        # retract, neighboring infill lines just travel flat.
        self.jump_d = float(jump_d)

    def set_z(self, z, feed=1200):
        self.L.append('G0 Z%.3f F%d' % (z, feed))
        self.z = z

    def travel(self, x, y, feed=4500, hop=True, force_d=None):
        # R73: travel capped at 75mm/s (the .56 label jobs overloaded the MCU
        # with 150mm/s travels) and Z-hops only above 2.5mm
        # R83: force_d lowers the retract threshold for THIS move (text
        # bundles retract from 1.2mm gaps - field log .65: no-retract travels
        # between letters drew ghost lines and the letters grew together)
        if self.x is None:
            self.L.append('G0 X%.3f Y%.3f F%d' % (x, y, feed))
        else:
            d = math.hypot(x - self.x, y - self.y)
            if d > (self.jump_d if force_d is None else force_d):
                hopz = hop and self.z is not None and self.z > 0.35
                if self.retracts:
                    self.L.append('G10')
                if hopz:
                    self.L.append('G0 Z%.3f F1200' % (self.z + 0.4))
                self.L.append('G0 X%.3f Y%.3f F%d' % (x, y, feed))
                if hopz:
                    self.L.append('G0 Z%.3f F1200' % self.z)
                if self.retracts:
                    self.L.append('G11')
                self.ret = False
            elif d > 0.02:
                self.L.append('G0 X%.3f Y%.3f F%d' % (x, y, feed))
        self.x, self.y = x, y

    def extrude(self, x, y, e, feed):
        if e <= 0:
            return
        self.L.append('G1 X%.3f Y%.3f E%.5f F%d' % (x, y, e, feed))
        self.x, self.y = x, y

    def push(self, e, feed):
        self.L.append('G1 E%.3f F%d' % (e, feed))


def _circle(cx, cy, r, seg=28):
    pts = []
    for i in range(seg):
        a = 2.0 * math.pi * i / seg
        pts.append((cx + r * math.cos(a), cy + r * math.sin(a)))
    return pts


def _rect_loop(x0, y0, x1, y1):
    return [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]


def _emit_loop(pen, pts, e_per_mm, feed, close=True):
    # R74: start the loop at the vertex CLOSEST to the pen - the fixed start
    # added a travel across the feature after every previous feature
    if close and pen.x is not None and len(pts) > 2:
        k = min(range(len(pts)),
                key=lambda i: (pts[i][0] - pen.x) ** 2 + (pts[i][1] - pen.y) ** 2)
        if k:
            pts = pts[k:] + pts[:k]
    pen.travel(pts[0][0], pts[0][1])
    px, py = pts[0]
    for (x, y) in pts[1:]:
        pen.extrude(x, y, math.hypot(x - px, y - py) * e_per_mm, feed)
        px, py = x, y
    if close:
        pen.extrude(pts[0][0], pts[0][1], math.hypot(pts[0][0] - px, pts[0][1] - py) * e_per_mm, feed)


def _hatch(x0, y0, x1, y1, circ_keep, spacing, angle_deg, min_len=0.35):
    """scanline hatch over rect minus keep-out circle -> [(p,q),..] boustrophedon

    R77 FIX (field log .60: label bases tore apart, 'filament pulled away'):
    the scanlines used to be emitted CENTER-OUT in +-alternating order
    (i=0 center, then -1/+1, -2/+2 ...) - consecutive segments sat up to
    2*i*spacing apart, so the pen travelled across the whole label between
    NEIGHBORING infill lines (with a G10 retract each, once the distance
    passed the jump threshold - a retract storm that starved the nozzle).
    Now the lines are sorted into a real SWEEP from one side to the other:
    neighbors are adjacent by construction, no retracts inside the fill."""
    ang = math.radians(angle_deg)
    dx, dy = math.cos(ang), math.sin(ang)
    nx, ny = -dy, dx
    mx, my = (x0 + x1) / 2.0, (y0 + y1) / 2.0
    corners = [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]
    tmax = max(abs((px - mx) * nx + (py - my) * ny) for px, py in corners) + spacing
    scan = []                                  # [(offset t, intervals), ...]
    i = 0
    while i * spacing <= tmax:
        for t in ((i * spacing,) if i == 0 else (-i * spacing, i * spacing)):
            ox, oy = mx + nx * t, my + ny * t
            s0, s1 = -1e9, 1e9
            ok = True
            for axis in (0, 1):
                d = (dx, dy)[axis]
                o = (ox, oy)[axis]
                lo, hi = (x0, x1) if axis == 0 else (y0, y1)
                if abs(d) < 1e-12:
                    if o < lo - 0.01 or o > hi + 0.01:
                        ok = False
                        break
                else:
                    a = (lo - o) / d
                    b = (hi - o) / d
                    if a > b:
                        a, b = b, a
                    s0 = max(s0, a)
                    s1 = min(s1, b)
            if not ok or s1 - s0 < min_len:
                continue
            intervals = [(s0, s1)]
            if circ_keep:
                ckx, cky, ck = circ_keep
                fx, fy = ox - ckx, oy - cky
                qb = 2.0 * (fx * dx + fy * dy)
                qc = fx * fx + fy * fy - ck * ck
                disc = qb * qb / 4.0 - qc
                if disc >= 0.0:
                    sq = math.sqrt(disc)
                    ta = -qb / 2.0 - sq
                    tb = -qb / 2.0 + sq
                    new = []
                    for (a, b) in intervals:
                        if tb <= a or ta >= b:
                            new.append((a, b))
                        else:
                            if a < ta:
                                new.append((a, min(b, ta)))
                            if b > tb:
                                new.append((max(a, tb), b))
                    intervals = new
            if intervals:
                scan.append((t, intervals))
        i += 1
    scan.sort(key=lambda ti: ti[0])            # R77: sweep, not center-out zigzag
    segs = []
    idx = 0
    for _t, intervals in scan:
        for (a, b) in intervals:
            if b - a < min_len:
                continue
            ox, oy = mx + nx * _t, my + ny * _t
            p = (ox + dx * (a + 0.15), oy + dy * (a + 0.15))
            q = (ox + dx * (b - 0.15), oy + dy * (b - 0.15))
            segs.append((p, q) if idx % 2 == 0 else (q, p))
            idx += 1
    return segs


def _emit_hatch(pen, segs, e_per_mm, feed):
    # R74: start from the END that is closer to the pen. R77 FIX (field log
    # .60: label bases tore apart, 'filament pulled away'): reversing only the
    # LIST breaks the boustrophedon chain - the segments alternate direction,
    # so end(seg[k]) is near start(seg[k+1]) but FAR from start(seg[k-1]).
    # The broken chain made EVERY hatch line a full-width travel with a
    # G10 retract before it (a retract storm that starved the nozzle).
    # Reversing each segment's direction TOO keeps the chain intact:
    # ... end(s2)->start(s1'), end(s1')->start(s0') ...
    if segs and pen.x is not None:
        d0 = (segs[0][0][0] - pen.x) ** 2 + (segs[0][0][1] - pen.y) ** 2
        d1 = (segs[-1][0][0] - pen.x) ** 2 + (segs[-1][0][1] - pen.y) ** 2
        if d1 < d0:
            segs = [(q, p) for (p, q) in reversed(segs)]
    for (p, q) in segs:
        pen.travel(p[0], p[1], hop=False)
        pen.extrude(q[0], q[1], math.hypot(q[0] - p[0], q[1] - p[1]) * e_per_mm, feed)


def _bed_limits(cfg_path):
    """parse [stepper_x]/[stepper_y] position_min/max from a printer.cfg ->
    (x_min, y_min, x_max, y_max); best-effort with sane Ender-3 defaults."""
    dflt = (0.0, -3.0, 244.0, 238.0)
    try:
        with open(cfg_path, errors='replace') as f:
            secs = {}
            cur = None
            for l in f:
                ls = l.strip()
                if ls.startswith('[') and ls.endswith(']'):
                    cur = ls[1:-1].strip().lower()
                    secs.setdefault(cur, {})
                elif cur and ':' in ls and not ls.startswith(('#', ';')):
                    k, v = ls.split(':', 1)
                    v = v.split('#')[0].split(';')[0].strip()
                    if k.strip() and v:
                        secs[cur][k.strip().lower()] = v
    except OSError:
        return dflt

    def val(sec, key, d):
        try:
            return float(secs.get(sec, {}).get(key, d))
        except (TypeError, ValueError):
            return d
    x0 = val('stepper_x', 'position_min', 0.0)
    x1 = val('stepper_x', 'position_max', 244.0)
    y0 = val('stepper_y', 'position_min', -3.0)
    y1 = val('stepper_y', 'position_max', 238.0)
    if x1 <= x0 or y1 <= y0:
        return dflt
    return (x0, y0, x1, y1)


def _safe_label_name(t):
    return (re.sub(r'[^A-Za-z0-9_.-]+', '', t)[:16] or 'label')


def label_preview(texts, w=60.0, h=30.0, font='SMOOTH', base_layers=4,
                   text_layers=2, layer_h=0.2, first_h=0.28, hole_side=0,
                   hole_d=5.0, gap=6.0, color2=True, stroke=0.0, font_size=0.0,
                   spacing=0.0, bed=None, bed_margin=6.0, nozzle=0.6):
    """R83: project the label outcome WITHOUT writing a file. The LCD 'Fit'
    item bumps label_fit_nonce and this answers with the same numbers the
    generator will print: final label size (incl. growth), cap height,
    effective stroke, characters per line, the minimum label size a fixed
    font size needs, and whether the purge tower still fits the bed."""
    font = str(font or 'SMOOTH').upper()
    if font == 'PIXEL':
        font = 'SMOOTH'
    all_lines = []
    for t in texts:
        ls = [x.strip() for x in t.split('~') if x.strip()]
        if not ls:
            raise ValueError('label "%s" has no text' % t[:16])
        if len(ls) > 5:
            raise ValueError('label "%s" has %d lines - at most 5 per label'
                             % (t[:16], len(ls)))
        all_lines.append(ls)
    w = float(w)
    h = float(h)
    spacing = max(0.0, min(float(spacing or 0.0), 10.0))
    twid = max(0.4, nozzle * 1.02)
    stroke_w = float(stroke or 0.0)
    if stroke_w <= 0:
        stroke_w = 3.0 * twid
    stroke_w = max(twid, min(stroke_w, 4.0))
    if bed is None:
        bed = (0.0, -3.0, 244.0, 238.0)
    bx0, by0, bx1, by1 = bed
    ux0, uy0 = bx0 + bed_margin, by0 + bed_margin
    ux1, uy1 = bx1 - bed_margin, by1 - bed_margin
    uw, uh = ux1 - ux0, uy1 - uy0

    w2, h2, grown, mcache = _label_grow_fit(
        all_lines, font, w, h, font_size, spacing, stroke_w, hole_side, hole_d)
    _c, box, _d = _label_layout(w2, h2, hole_side, hole_d)
    bw, bh = box[2] - box[0], box[3] - box[1]
    g, parsed = mcache[0]
    cap_auto = _label_autocap(g, parsed, bw, bh, spacing, stroke_w)
    cap = min(float(font_size), cap_auto) if font_size and float(font_size) > 0 else cap_auto
    cap = max(0.1, cap)
    stroke_eff = round(min(stroke_w, max(twid, 0.2 * cap)), 2)

    # characters per line at the projected cap (font-average advance)
    longest = max(parsed, key=lambda p2: p2['w_units'])
    avg_adv = max(0.01, longest['w_units'] / max(1, len(longest['text'])))
    sc = cap / g['cap_units']
    per_char = avg_adv * sc + spacing
    chars_fit = max(1, int((bw * 0.94 + spacing) / max(per_char, 0.01)))

    # minimum label size for a FIXED font size (width first, then height -
    # the same strategy the generator grows)
    min_w = min_h = None
    if font_size and float(font_size) > 0:
        nbw, nbh = _label_need_size(g, parsed, float(font_size), spacing, stroke_w)
        min_w, min_h = w2, h2
        for cand in [c * 0.5 for c in range(24, 481)]:        # 12..240mm
            _c2, b2, _d2 = _label_layout(cand, h, hole_side, hole_d)
            if b2[2] - b2[0] >= nbw - 0.5:
                min_w = cand
                break
        _c3, b3, _d3 = _label_layout(min_w, h, hole_side, hole_d)
        if b3[3] - b3[1] < nbh - 0.5:
            for cand in [c * 0.5 for c in range(int(h * 2), 441)]:   # h..220mm
                _c4, b4, _d4 = _label_layout(min_w, cand, hole_side, hole_d)
                if b4[3] - b4[1] >= nbh - 0.5:
                    min_h = cand
                    break

    # grid + tower fit on the bed (same math as make_labels)
    n = len(texts)
    cols = rows = None
    for c in range(n, 0, -1):
        r = -(-n // c)
        if c * w2 + (c - 1) * gap <= uw and r * h2 + (r - 1) * gap <= uh:
            cols, rows = c, r
            break
    tower_fits = False
    if cols is not None:
        gw = cols * w2 + (cols - 1) * gap
        gh = rows * h2 + (rows - 1) * gap
        gx0 = ux0 + (uw - gw) / 2.0
        gy0 = uy0 + (uh - gh) / 2.0
        if color2:
            tg, tw = 15.0, 12.0
            for (tx, ty) in [(gx0 + gw + tg, gy0), (gx0, gy0 + gh + tg),
                             (gx0, gy0 - tw - tg), (gx0 - tw - tg, gy0)]:
                if tx >= ux0 and ty >= uy0 and tx + tw <= ux1 and ty + tw <= uy1:
                    tower_fits = True
                    break
    warns = []
    if stroke_eff < stroke_w - 0.01:
        warns.append('stroke %.2fmm capped to %.2fmm (cap/5 - thicker would '
                     'merge the letters)' % (stroke_w, stroke_eff))
    if color2 and cols is not None and not tower_fits:
        warns.append('no room for the purge tower at 15mm clearance - the '
                     'filament change purges at the park position instead')
    if cols is None:
        warns.append('the plate does not fit the bed at %.0fx%.0fmm - smaller '
                     'labels or a smaller gap' % (w2, h2))
    return {'w': round(w2, 1), 'h': round(h2, 1), 'grown': grown,
            'cap_mm': round(cap, 1), 'cap_capped': (font_size and float(font_size) > 0
                                                    and cap < float(font_size) - 0.05),
            'target_mm': round(float(font_size or 0), 1),
            'stroke_eff': stroke_eff, 'chars_fit': chars_fit,
            'lines': max(len(ls) for ls in all_lines), 'count': n,
            'min_w': round(min_w, 1) if min_w else None,
            'min_h': round(min_h, 1) if min_h else None,
            'tower_fits': tower_fits, 'fits_bed': cols is not None,
            'warns': warns}


def make_labels(texts, w=60.0, h=30.0, font='SMOOTH', base_layers=4, text_layers=2,
                layer_h=0.2, first_h=0.28, ironing=True, hole_side=0, hole_d=5.0,
                brim=True, gap=6.0, color2=True, material='PLA', bed=None,
                bed_margin=6.0, nozzle=0.6, stroke=0.0, font_size=0.0, spacing=0.0,
                out_dir='.', version=1):
    """Generate a printable label plate file. Returns (path, info).

    R74: every entry may carry up to 3 lines separated by '~' (LCD: Labels >
    Text > Line). font_size = cap height in mm (0 = auto), spacing = extra
    millimeters between characters. The text block is one UNIFORM scale -
    letters never stretch; lines that do not fit raise an error that names
    the character maximum for this label size."""
    texts = [t.strip() for t in texts if t and t.strip()]
    if not texts:
        raise ValueError('no label text - add one first (LCD: Labels > Text)')
    if len(texts) > 24:
        raise ValueError('at most 24 labels per job (got %d)' % len(texts))
    font = str(font).upper()
    # R80: PIXEL is gone (field log .63: unreadable) - MONO + SMOOTH stay;
    # a saved 'PIXEL' selection falls back to SMOOTH (R80); R82 adds
    # COND / NARROW / CAPS - the small-text fonts
    if font not in _LABEL_STROKE_FONTS:
        font = 'SMOOTH'
    font_size = max(0.0, min(float(font_size or 0.0), 40.0))
    spacing = max(0.0, min(float(spacing or 0.0), 10.0))
    # R74: '~' separates the lines of ONE label (the charset has no '~' - the
    # LCD can never type it into a line by accident)
    all_lines = []
    for t in texts:
        ls = [x.strip() for x in t.split('~') if x.strip()]
        if not ls:
            raise ValueError('label "%s" has no text' % t[:16])
        if len(ls) > 5:
            raise ValueError('label "%s" has %d lines - at most 5 per label' % (t[:16], len(ls)))
        all_lines.append(ls)
    w = float(w)
    h = float(h)
    if not (12.0 <= w <= 320.0) or not (10.0 <= h <= 320.0):
        raise ValueError('label size %.1fx%.1fmm out of range (12..320 / 10..320)' % (w, h))
    base_layers = max(2, min(int(base_layers), 60))
    text_layers = max(1, min(int(text_layers), 6))
    layer_h = max(0.06, min(float(layer_h), 0.34))
    first_h = max(0.08, min(float(first_h), 0.42))
    hole_side = int(hole_side) % 5
    gap = max(2.0, min(float(gap), 30.0))
    # ---- stroke width - 'Stroke' IS the extrusion line width (R80 field Q) ---
    # 0 = auto: 3 extrusion lines (solid, chunky letters). Explicit value =
    # line width in mm - set it to your NOZZLE diameter (0.6 -> single-line
    # letters). The old clamp forced >= 2 lines; a user 0.6 became 1.22.
    twid = max(0.4, nozzle * 1.02)         # one text extrusion line
    stroke_w = float(stroke or 0.0)
    if stroke_w <= 0:
        stroke_w = 3.0 * twid
    stroke_w = max(twid, min(stroke_w, 4.0))
    if bed is None:
        bed = (0.0, -3.0, 244.0, 238.0)
    bx0, by0, bx1, by1 = bed
    ux0, uy0 = bx0 + bed_margin, by0 + bed_margin
    ux1, uy1 = bx1 - bed_margin, by1 - bed_margin
    uw, uh = ux1 - ux0, uy1 - uy0

    # ---- R80 AUTO-FIT + AUTO-GROW (field log .63: endless 'needs X mm but
    #      only Y usable' errors; a 6cm tag that holds 3 characters is useless):
    #      the FONT adapts to the label (94% fill, only filled lines count) -
    #      and if the letters would get unreadable (<2.8mm caps) or an explicit
    #      font size does not fit, the LABEL GROWS (width first, then height,
    #      +75% max) instead of erroring. The text is never shortened.
    w, h, grown79, mcache = _label_grow_fit(
        all_lines, font, w, h, font_size, spacing, stroke_w, hole_side, hole_d)

    # ---- fit the grid: labels read left->right, so use the MOST columns that
    #      still fit the bed (rows fill naturally); max = cols*rows per batch ----
    n = len(texts)
    best = None
    for cols in range(n, 0, -1):
        rows = -(-n // cols)
        gw = cols * w + (cols - 1) * gap
        gh = rows * h + (rows - 1) * gap
        if gw <= uw and gh <= uh:
            best = (cols, rows, gw, gh)
            break
    if best is None:
        # nothing fits - report how many WOULD fit for a helpful error message
        raise ValueError('%d label(s) of %.0fx%.0fmm (+%.0fmm gap) do not fit the bed '
                         '(%.0fx%.0fmm usable) - fewer/smaller labels or a smaller gap'
                         % (n, w, h, gap, uw, uh))
    cols, rows, gw, gh = best
    gx0 = ux0 + (uw - gw) / 2.0
    gy0 = uy0 + (uh - gh) / 2.0
    positions = []
    for i in range(n):
        r, c = divmod(i, cols)
        positions.append((gx0 + c * (w + gap), gy0 + r * (h + gap)))

    # ---- purge tower (only for 2-color jobs): beside / in front of the grid
    tw = 12.0
    tower = None
    if color2:
        # R83: 15mm clearance (field log .65: the probe could catch on the
        # tower's purge corner -> layer shift) and RIGHT of the grid first -
        # the probe hangs ~43mm LEFT of the nozzle, so a left tower sits in
        # its sweep while the label prints
        tg = 15.0
        cands = [(gx0 + gw + tg, gy0), (gx0, gy0 + gh + tg),
                 (gx0, gy0 - tw - tg), (gx0 - tw - tg, gy0)]
        for (tx, ty) in cands:
            if tx >= ux0 and ty >= uy0 and tx + tw <= ux1 and ty + tw <= uy1:
                tower = (tx, ty)
                break

    # (stroke_w was computed before the auto-grow pass - R80; the fit below
    # RESERVES it: the printed stroke is skeleton + stroke_w wide)

    # ---- per-label geometry (R74 line typography + edge hole) -----------------
    labels = []
    for i, ls in enumerate(all_lines):
        lx, ly = positions[i]
        circ, box, hd = _label_layout(w, h, hole_side, hole_d)
        paths, geo = _label_text_lines(ls, font, box, w, h, font_size, spacing,
                                       stroke_w=stroke_w)
        labels.append({'name': 'LABEL_%d' % (i + 1), 'text': ' / '.join(ls),
                       'lines': ls, 'x': lx, 'y': ly,
                       'circ': circ, 'box': box, 'paths': paths, 'hole_d': hd,
                       'cap_h': geo['cap_h'], 's': geo['s'], 'sx': geo['s']})

    # ---- extrusion constants ------------------------------------------------
    wid = max(0.4, nozzle * 1.08)          # perimeter / infill line width
    twid = max(0.4, nozzle * 1.02)         # one text extrusion line
    # R83 anti-merge: the effective stroke never exceeds cap/5 (>= 1 line)
    _capmax79 = max(lb['cap_h'] for lb in labels)
    stroke_eff = round(min(stroke_w, max(twid, 0.2 * _capmax79)), 2)
    fil = FIL_AREA
    total_layers = base_layers + text_layers
    ztop = first_h + (base_layers - 1) * layer_h

    L = []
    a = L.append
    a('; R2-LABELS generated label plate (R63/R73) - start it like any other file')
    a('; R73 typography: caps 66% of the label height, small signs 66% of that,')
    a(';           text ~75% of the label width, one cell per character, baseline aligned')
    a(TAG)
    a('; labels: %d (%s)' % (n, ' | '.join(t['text'] for t in labels)))
    a('; base %.0fx%.0fmm, %d layers @ %.2gmm (first %.2gmm), text %d layer(s), font %s'
      % (w, h, base_layers, layer_h, first_h, text_layers, font))
    a('; R74 text: font size %s, letter spacing +%.1fmm, up to 5 lines per label, uniform scale'
      % ('auto' if not font_size else '%.1fmm caps' % font_size, spacing))
    if stroke_eff < stroke_w - 0.01:
        a('; R83 stroke %.2fmm (capped from %.2fmm: cap/5 anti-merge limit)'
          % (stroke_eff, stroke_w))
    hs = ('NONE', 'LEFT', 'RIGHT', 'TOP', 'BOTTOM')[hole_side]
    a('; hole: %s%s at 2mm from the edge, ironing %s, brim %s, purge tower %s, 2nd color (M600) %s'
      % (hs, (' d=%.1fmm' % labels[0]['hole_d']) if labels[0]['hole_d'] else '',
         'ON' if ironing else 'OFF', 'ON' if brim else 'OFF',
         'ON' if tower else 'OFF', 'ON' if color2 else 'OFF'))
    a('; layout: %dx%d grid %0.0fx%0.0fmm, %d of max %d labels fit the bed'
      % (cols, rows, gw, gh, n, cols * rows))
    # slicer-style config comments -> _FILE_INFO (Pre-Print shows these)
    a('; filament_type = %s' % material)
    a('; layer_height = %.2g' % layer_h)
    a('; nozzle_diameter = %.1f' % nozzle)
    a('; line_width = %.2g' % wid)
    a('; outer_wall_line_width = %.2g' % wid)
    a('; outer_wall_speed = 40')
    a('; inner_wall_speed = 45')
    a('; top_surface_speed = 40')
    a('; internal_solid_infill_speed = 55')
    a('; initial_layer_speed = 25')
    a('; travel_speed = 150')
    if ironing:
        a('; ironing_speed = 30')
        a('; ironing_flow = 0.15')
        a('; ironing_spacing = 0.45')
    a('; wall_loops = 2')
    # R73: the file info line goes in DIRECTLY (no re-parse through process()
    # - half the generation time on slow hosts; the TAG above makes the scan skip)
    types = ['WALL-OUTER', 'WALL-INNER', 'INFILL-SOLID']
    if brim:
        types.insert(0, 'BRIM')
    if ironing:
        types += ['SURFACE-TOP', 'IRONING']
    else:
        types += ['SURFACE-TOP']
    a('_FILE_INFO MATERIAL=%s LAYER_HEIGHT=%.2g TOTAL_LAYERS=%d LINE_WIDTH=%.2g '
      'LINE_WIDTH_FIRST=%.2g LINE_WIDTH_WALL=%.2g FLOW_RATIO=1 NOZZLE=%.1f '
      'WALL_LOOPS=2 SPEED_OUTER=40 SPEED_FIRST=25 SPEED_TRAVEL=150%s TYPES=%s BY_OBJECT=0'
      % (material, layer_h, total_layers, wid, first_h, wid,
         nozzle, ' IRONING_SPEED=30' if ironing else '', ','.join(types)))

    # object definitions (polygons without whitespace - Klipper requirement)
    for lb in labels:
        poly = '[[%.1f,%.1f],[%.1f,%.1f],[%.1f,%.1f],[%.1f,%.1f]]' % (
            lb['x'], lb['y'], lb['x'] + w, lb['y'], lb['x'] + w, lb['y'] + h, lb['x'], lb['y'] + h)
        a('EXCLUDE_OBJECT_DEFINE NAME=%s CENTER=%.1f,%.1f POLYGON=%s'
          % (lb['name'], lb['x'] + w / 2.0, lb['y'] + h / 2.0, poly))
    if tower:
        poly = '[[%.1f,%.1f],[%.1f,%.1f],[%.1f,%.1f],[%.1f,%.1f]]' % (
            tower[0], tower[1], tower[0] + tw, tower[1],
            tower[0] + tw, tower[1] + tw, tower[0], tower[1] + tw)
        a('EXCLUDE_OBJECT_DEFINE NAME=PURGE_TOWER CENTER=%.1f,%.1f POLYGON=%s'
          % (tower[0] + tw / 2.0, tower[1] + tw / 2.0, poly))
    ps = 'PRINT_START MATERIAL=%s LAYER_HEIGHT=%.2g TOTAL_LAYERS=%d OUTER_WALL_SPEED=40' % (
        material, layer_h, total_layers)
    if ironing:
        ps += ' IRONING_SPEED=30'
    a(ps)
    a('G90')
    a('M83')
    a('M107   ; R2-LABELS: first layer = fan off')

    pen = _Pen(L, jump_d=6.0)   # R77: no retracts between neighboring hatch lines

    def base_block(lb, z, layer_idx, first, top):
        """one label's base layer: brim + perimeters + hole + solid infill (+ironing)"""
        lx, ly = lb['x'], lb['y']
        x0, y0 = lx + wid / 2.0, ly + wid / 2.0
        x1, y1 = lx + w - wid / 2.0, ly + h - wid / 2.0
        e_wall = layer_h_eff(layer_idx) * wid / fil
        L.append('EXCLUDE_OBJECT_START NAME=%s' % lb['name'])
        if first and brim:
            L.append(';TYPE:Brim')
            for off in (wid * 0.35, wid * 0.35 + wid, wid * 0.35 + 2 * wid):
                b = (lx - off, ly - off, lx + w + off, ly + h + off)
                _emit_loop(pen, _rect_loop(*b), e_wall, 1500 if first else 2400)
        L.append(';TYPE:Outer wall')
        _emit_loop(pen, _rect_loop(x0, y0, x1, y1), e_wall, 1500 if first else 2400)
        L.append(';TYPE:Inner wall')
        _emit_loop(pen, _rect_loop(x0 + wid, y0 + wid, x1 - wid, y1 - wid), e_wall,
                   1500 if first else 2700)
        if lb['circ']:
            cx, cy, r = lb['circ']
            cx += lx
            cy += ly
            L.append(';TYPE:Outer wall')
            _emit_loop(pen, _circle(cx, cy, r + wid / 2.0), e_wall, 1500 if first else 2400)
            _emit_loop(pen, _circle(cx, cy, r + 1.5 * wid), e_wall, 1500 if first else 2700)
        ix0, iy0 = lx + 2.0 * wid + 0.1, ly + 2.0 * wid + 0.1
        ix1, iy1 = lx + w - 2.0 * wid - 0.1, ly + h - 2.0 * wid - 0.1
        keep = None
        if lb['circ']:
            keep = (lb['circ'][0] + lx, lb['circ'][1] + ly, lb['circ'][2] + 2.0 * wid)
        L.append(';TYPE:%s' % ('Top surface' if top else 'Internal solid infill'))
        segs = _hatch(ix0, iy0, ix1, iy1, keep, wid, 45.0 if layer_idx % 2 else 135.0)
        _emit_hatch(pen, segs, e_wall, 1500 if first else 2700)
        if top and ironing:
            L.append(';TYPE:Ironing')
            ikeep = None
            if lb['circ']:
                ikeep = (lb['circ'][0] + lx, lb['circ'][1] + ly, lb['circ'][2] + 0.4)
            isegs = _hatch(lx + 1.0, ly + 1.0, lx + w - 1.0, ly + h - 1.0, ikeep, 0.45, 90.0,
                           min_len=0.3)
            ei = layer_h_eff(layer_idx) * wid * 0.15 / fil
            _emit_hatch(pen, isegs, ei, 1800)
        L.append('EXCLUDE_OBJECT_END NAME=%s' % lb['name'])

    def layer_h_eff(layer_idx):
        return first_h if layer_idx == 1 else layer_h

    def tower_block(z, layer_idx, first, prime=False):
        x0, y0 = tower[0] + wid / 2.0, tower[1] + wid / 2.0
        x1, y1 = tower[0] + tw - wid / 2.0, tower[1] + tw - wid / 2.0
        e_wall = layer_h_eff(layer_idx) * wid / fil
        L.append('EXCLUDE_OBJECT_START NAME=PURGE_TOWER')
        if prime:
            # after the filament change: push the new color and wipe on the tower
            pen.travel(tower[0] + 1.5, tower[1] + tw - 1.5)
            pen.push(4.0, 180)
            pen.extrude(tower[0] + tw - 1.5, tower[1] + tw - 1.5, 3.0 * 0.1, 1320)
            pen.extrude(tower[0] + 1.5, tower[1] + tw - 1.5, (tw - 3.0) * 0.1, 1320)
        if first and brim:
            L.append(';TYPE:Brim')
            for off in (wid * 0.35, wid * 0.35 + wid):
                b = (tower[0] - off, tower[1] - off, tower[0] + tw + off, tower[1] + tw + off)
                _emit_loop(pen, _rect_loop(*b), e_wall, 1500)
        L.append(';TYPE:Outer wall')
        _emit_loop(pen, _rect_loop(x0, y0, x1, y1), e_wall, 1500 if first else 2400)
        L.append(';TYPE:Inner wall')
        _emit_loop(pen, _rect_loop(x0 + wid, y0 + wid, x1 - wid, y1 - wid), e_wall,
                   1500 if first else 2700)
        L.append(';TYPE:Internal solid infill')
        segs = _hatch(x0 + wid + 0.1, y0 + wid + 0.1, x1 - wid - 0.1, y1 - wid - 0.1,
                      None, wid, 45.0 if layer_idx % 2 else 135.0)
        _emit_hatch(pen, segs, e_wall, 1500 if first else 2700)
        L.append('EXCLUDE_OBJECT_END NAME=PURGE_TOWER')

    def text_block(lb, z, layer_idx):
        """the label's text (R74 line typography) - SOLID double-walled
        strokes (R72: single lines broke off when scratched). Each skeleton
        becomes a bundle of parallel lines +half..-half: the outermost two
        are the walls, the lines between them the fill, printed serpentine.
        R73: ONE feature for the whole text (the .56 file switched
        wall/fill per stroke line -> hundreds of APPLY_TYPE calls -> host/MCU
        overload), decimated vertices, calmer feeds.
        R74: the stroke bundles print NEAREST-FIRST - reading order added a
        travel across the whole word before every glyph."""
        e_txt = layer_h_eff(layer_idx) * twid / fil
        # stroke width: user value (LCD 'Stroke'), auto = 3 extrusion lines;
        # capped by the letter pitch so condensed glyphs keep open counters,
        # and R83 by the cap height (stroke <= cap/5) - 0.8mm strokes on
        # 3.4mm caps printed letters grown together (field log .65)
        half = min(stroke_eff, max(2.0 * twid, 2.1 * lb['sx'])) / 2.0
        L.append('EXCLUDE_OBJECT_START NAME=%s' % lb['name'])
        L.append(';TYPE:Inner wall')
        bundles = []
        for pts in lb['paths']:
            pts = _decimate([(lb['x'] + px, lb['y'] + py) for (px, py) in pts], 0.10)
            if len(pts) >= 2:
                bundles.append(pts)
        while bundles:
            if pen.x is None:
                k = 0
            else:
                k = min(range(len(bundles)),
                        key=lambda i: (bundles[i][0][0] - pen.x) ** 2
                        + (bundles[i][0][1] - pen.y) ** 2)
            pts = bundles.pop(k)
            offs = _stroke_offsets(pts, half, twid)
            for k2, path in enumerate(offs):
                if k2 % 2:
                    path = list(reversed(path))
                # R83: glyph-to-glyph travel (k2 == 0) retracts + hops from
                # 1.2mm - letters must stay discrete, no ooze ghost lines
                pen.travel(path[0][0], path[0][1], feed=4500, hop=(k2 == 0),
                           force_d=(1.2 if k2 == 0 else None))
                px, py = path[0]
                for (x, y) in path[1:]:
                    d = math.hypot(x - px, y - py)
                    if d < 0.05:
                        continue
                    pen.extrude(x, y, d * e_txt, 1200)
                    px, py = x, y
        L.append('EXCLUDE_OBJECT_END NAME=%s' % lb['name'])

    # ---- base layers --------------------------------------------------------
    # R74: label order alternates per layer (serpentine) - layer N ends at the
    # last label, layer N+1 starts right there instead of travelling back
    for li in range(1, base_layers + 1):
        z = round(first_h + (li - 1) * layer_h, 3)
        L.append(';LAYER_CHANGE')
        L.append(';Z:%.3f' % z)
        pen.set_z(z)
        if li == 2:
            L.append('M106 S178   ; R2-LABELS: part fan from layer 2')
        top = (li == base_layers)
        order = labels if li % 2 else list(reversed(labels))
        for lb in order:
            base_block(lb, z, li, li == 1, top)
        if tower:
            tower_block(z, li, li == 1)

    # ---- filament change for the text color ---------------------------------
    if color2:
        a('; R2-LABELS: bases done - PAUSE for the filament change (text color)')
        a('; swap filament, then RESUME - the purge tower primes the new color')
        a('M600')

    # ---- text layers --------------------------------------------------------
    for ti in range(1, text_layers + 1):
        li = base_layers + ti
        z = round(first_h + (base_layers - 1) * layer_h + ti * layer_h, 3)
        L.append(';LAYER_CHANGE')
        L.append(';Z:%.3f' % z)
        pen.set_z(z)
        if tower:
            tower_block(z, li, False, prime=(ti == 1))
        order = labels if li % 2 else list(reversed(labels))
        for lb in order:
            text_block(lb, z, li)

    a('M107')
    a('PRINT_END')

    # R73: inject the R2 markers directly (LAYER_MARK after every layer change,
    # APPLY_TYPE after every ;TYPE:) - no re-parse through process()
    outl = []
    for l in L:
        outl.append(l)
        ls = l.strip()
        if ls.startswith(';TYPE:'):
            key = ls[6:].strip().lower()
            outl.append('APPLY_TYPE TYPE=%s' % TYPE_MAP.get(key, 'CUSTOM'))
        elif LAYER_COMMENT.match(ls):
            outl.append('LAYER_MARK')

    # R83: 00_ prefix (generated files sort to the TOP of the file list) and
    # a _V version suffix. The size is deliberately NOT in the name: the same
    # text regenerated with other settings OVERWRITES its own file instead of
    # piling up near-duplicates (user spec). Version bumps (LCD 'Version')
    # keep an iteration as a new file.
    first_name = _safe_label_name(texts[0])
    extra = '+%d' % (n - 1) if n > 1 else ''
    fname = '00_%s%s_V%02d.gcode' % (first_name, extra,
                                     max(1, min(int(version), 99)))
    out = os.path.join(out_dir, fname)
    with open(out, 'w') as f:
        f.write('\n'.join(outl) + '\n')

    info = {'file': fname, 'count': n, 'cols': cols, 'rows': rows,
            'stroke_eff': stroke_eff, 'stroke_capped': stroke_eff < stroke_w - 0.01,
            'fit': cols * rows, 'grid': '%.0fx%.0f' % (gw, gh),
            'tower': bool(tower), 'layers': total_layers,
            'max_lines': max(len(t['lines']) for t in labels),
            'cap_mm': round(max(lb['cap_h'] for lb in labels), 1),
            'grown': grown79, 'w': round(w, 1), 'h': round(h, 1),
            'height': round(ztop + text_layers * layer_h, 2)}
    return out, info


# ======================================================================================
#  R64 INPUT SHAPER MATH - a faithful port of Klipper's shaper_defs.py +
#  shaper_calibrate.py (pure python, no numpy) so the R64 resonance diagram
#  can fit the shapers EXACTLY like Klipper does, even when the CSV comes from
#  TEST_RESONANCES (no shaper table in the file).
# ======================================================================================

SHAPER_VIBRATION_REDUCTION = 20.0
SHAPER_DEFAULT_DAMPING = 0.1
SHAPER_TEST_DAMPINGS = (0.075, 0.1, 0.15)
AUTOTUNE_SHAPERS = ('zv', 'mzv', 'ei', '2hump_ei', '3hump_ei')
SHAPER_MIN_FREQ = {'zv': 21.0, 'mzv': 23.0, 'zvd': 29.0, 'ei': 29.0,
                   '2hump_ei': 39.0, '3hump_ei': 48.0}
SHAPER_MAX_FREQ = 150.0


def _solve_lsq(M, F):
    """least squares A ~= M^-1 F via normal equations (tiny, well conditioned)."""
    n = len(M[0])
    mtm = [[sum(M[r][i] * M[r][j] for r in range(len(M))) for j in range(n)] for i in range(n)]
    mtf = [sum(M[r][i] * F[r] for r in range(len(M))) for i in range(n)]
    aug = [mtm[i][:] + [mtf[i]] for i in range(n)]
    for col in range(n):
        p = max(range(col, n), key=lambda r: abs(aug[r][col]))
        aug[col], aug[p] = aug[p], aug[col]
        pv = aug[col][col]
        for j in range(col, n + 1):
            aug[col][j] /= pv
        for r in range(n):
            if r != col and aug[r][col] != 0.0:
                f = aug[r][col]
                for j in range(col, n + 1):
                    aug[r][j] -= f * aug[col][j]
    return [aug[i][n] for i in range(n)]


_MZV_BASE = None


def _mzv_base_coeffs():
    """Klipper's get_mzv_coeffs(n=3, t=0.75) - solved once (freq independent)."""
    n, t = 3, 0.75
    tau = t * (n - 2.0) / (n - 2.0 * t - 1.0)
    T = [i * t / (n - 1.0) for i in range(n)]
    M = [[1.0] * n]
    F = [1.0]
    for i in range(n - 1):
        W = [2.0 * math.pi * (1.0 + i / tau) * tj for tj in T]
        M.append([math.cos(w) for w in W])
        F.append(0.0)
        M.append([math.sin(w) for w in W])
        F.append(0.0)
    return _solve_lsq(M, F), T


def _shaper_zv(freq, damping):
    df = math.sqrt(1.0 - damping * damping)
    K = math.exp(-damping * math.pi / df)
    t_d = 1.0 / (freq * df)
    return ([1.0, K], [0.0, 0.5 * t_d])


def _shaper_zvd(freq, damping):
    df = math.sqrt(1.0 - damping * damping)
    K = math.exp(-damping * math.pi / df)
    t_d = 1.0 / (freq * df)
    return ([1.0, 2.0 * K, K * K], [0.0, 0.5 * t_d, t_d])


def _shaper_mzv(freq, damping):
    global _MZV_BASE
    if _MZV_BASE is None:
        _MZV_BASE = _mzv_base_coeffs()
    A, T = list(_MZV_BASE[0]), list(_MZV_BASE[1])
    n, t = 3, 0.75
    df = math.sqrt(1.0 - damping * damping)
    K = math.exp(-2.0 * t * damping * math.pi / ((n - 1.0) * df))
    t_d = 1.0 / (freq * df)
    Kp = K
    for i in range(1, n):
        T[i] *= t_d
        A[i] *= Kp
        Kp *= K
    return (A, T)


def _shaper_ei(freq, damping, v_tol=1.0 / SHAPER_VIBRATION_REDUCTION):
    df = math.sqrt(1.0 - damping * damping)
    t_d = 1.0 / (freq * df)
    dr = damping
    a1 = (0.24968 + 0.24961 * v_tol) + ((0.80008 + 1.23328 * v_tol) +
                                         (0.49599 + 3.17316 * v_tol) * dr) * dr
    a3 = (0.25149 + 0.21474 * v_tol) + ((-0.83249 + 1.41498 * v_tol) +
                                         (0.85181 - 4.90094 * v_tol) * dr) * dr
    a2 = 1.0 - a1 - a3
    t2 = 0.4999 + (((0.46159 + 8.57843 * v_tol) * v_tol) +
                   (((4.26169 - 108.644 * v_tol) * v_tol) +
                    ((1.75601 + 336.989 * v_tol) * v_tol) * dr) * dr) * dr
    return ([a1, a2, a3], [0.0, t2 * t_d, t_d])


def _shaper_expansion(freq, damping, t, a):
    tau = 1.0 / freq
    T, A = [], []
    n, k = len(a), len(a[0])
    for i in range(n):
        u, v = t[i][k - 1], a[i][k - 1]
        for j in range(k - 1):
            u = u * damping + t[i][k - j - 2]
            v = v * damping + a[i][k - j - 2]
        T.append(u * tau)
        A.append(v)
    return (A, T)


def _shaper_2hump(freq, damping):
    t = [[0., 0., 0., 0.],
         [0.49890, 0.16270, -0.54262, 6.16180],
         [0.99748, 0.18382, -1.58270, 8.17120],
         [1.49920, -0.09297, -0.28338, 1.85710]]
    a = [[0.16054, 0.76699, 2.26560, -1.22750],
         [0.33911, 0.45081, -2.58080, 1.73650],
         [0.34089, -0.61533, -0.68765, 0.42261],
         [0.15997, -0.60246, 1.00280, -0.93145]]
    return _shaper_expansion(freq, damping, t, a)


def _shaper_3hump(freq, damping):
    t = [[0., 0., 0., 0.],
         [0.49974, 0.23834, 0.44559, 12.4720],
         [0.99849, 0.29808, -2.36460, 23.3990],
         [1.49870, 0.10306, -2.01390, 17.0320],
         [1.99960, -0.28231, 0.61536, 5.40450]]
    a = [[0.11275, 0.76632, 3.29160, -1.44380],
         [0.23698, 0.61164, -2.57850, 4.85220],
         [0.30008, -0.19062, -2.14560, 0.13744],
         [0.23775, -0.73297, 0.46885, -2.08650],
         [0.11244, -0.45439, 0.96382, -1.46000]]
    return _shaper_expansion(freq, damping, t, a)


def _shaper_get(name, freq, damping=SHAPER_DEFAULT_DAMPING):
    name = str(name).lower()
    if name == 'zv':
        return _shaper_zv(freq, damping)
    if name == 'zvd':
        return _shaper_zvd(freq, damping)
    if name == 'mzv':
        return _shaper_mzv(freq, damping)
    if name == 'ei':
        return _shaper_ei(freq, damping)
    if name == '2hump_ei':
        return _shaper_2hump(freq, damping)
    if name == '3hump_ei':
        return _shaper_3hump(freq, damping)
    raise ValueError('unknown shaper %r' % name)


def _shaper_response(A, T, damping, freqs):
    """Klipper's _estimate_shaper: response amplitude per test frequency."""
    inv_D = 1.0 / sum(A)
    t_end = T[-1]
    out = []
    for f in freqs:
        omega = 2.0 * math.pi * f
        damp = damping * omega
        omega_d = omega * math.sqrt(1.0 - damping * damping)
        S = C = 0.0
        for a_i, t_i in zip(A, T):
            w = a_i * math.exp(-damp * (t_end - t_i))
            S += w * math.sin(omega_d * t_i)
            C += w * math.cos(omega_d * t_i)
        out.append(math.sqrt(S * S + C * C) * inv_D)
    return out


def _remaining_vibrations(A, T, damping, freqs, psd):
    vals = _shaper_response(A, T, damping, freqs)
    pmax = max(psd) if psd else 0.0
    thr = pmax / SHAPER_VIBRATION_REDUCTION
    rem = sum(max(v * p - thr, 0.0) for v, p in zip(vals, psd))
    allv = sum(max(p - thr, 0.0) for p in psd)
    return (rem / allv if allv > 0 else 0.0), vals


def _shaper_smoothing(A, T, accel=5000.0, scv=5.0):
    half = accel * 0.5
    inv_D = 1.0 / sum(A)
    ts = sum(a * t for a, t in zip(A, T)) * inv_D
    off90 = off180 = 0.0
    for a_i, t_i in zip(A, T):
        if t_i >= ts:
            off90 += a_i * (scv + half * (t_i - ts)) * (t_i - ts)
        off180 += a_i * half * (t_i - ts) ** 2
    return max(off90 * inv_D * math.sqrt(2.0), off180 * inv_D)


def _shaper_max_accel(A, T, scv):
    """Klipper's find_shaper_max_accel (TARGET_SMOOTHING = 0.12, bisect)."""
    def ok(accel):
        return _shaper_smoothing(A, T, accel, scv) <= 0.12
    left = right = 1.0
    if not ok(1e-9):
        return 0.0
    while not ok(left):
        right = left
        left *= 0.5
    if right == left:
        while ok(right):
            right *= 2.0
    while right - left > 1e-8:
        middle = (left + right) * 0.5
        if ok(middle):
            left = middle
        else:
            right = middle
    return left


def _fit_one_shaper(name, freqs, psd, scv):
    """Klipper's fit_shaper (no max_smoothing limit - the diagram shows all)."""
    freq_start = min(SHAPER_MIN_FREQ[name], SHAPER_MAX_FREQ - 1e-7)
    tf = []
    f = freq_start
    while f < SHAPER_MAX_FREQ:
        tf.append(round(f, 6))
        f += 0.2
    best_res = None
    results = []
    for test_freq in reversed(tf):
        A, T = _shaper_get(name, test_freq)
        smoothing = _shaper_smoothing(A, T, 5000.0, scv)
        max_accel = _shaper_max_accel(A, T, scv)
        vibrs = 0.0
        for dr in SHAPER_TEST_DAMPINGS:
            v, _vals = _remaining_vibrations(A, T, dr, freqs, psd)
            if v > vibrs:
                vibrs = v
        score = smoothing * (vibrs ** 1.5 + vibrs * 0.2 + 0.01)
        res = {'name': name, 'freq': test_freq, 'vibrs': vibrs,
               'smoothing': smoothing, 'score': score, 'max_accel': max_accel}
        results.append(res)
        if best_res is None or best_res['vibrs'] > res['vibrs']:
            best_res = res
    selected = best_res
    for res in reversed(results):
        if res['vibrs'] < best_res['vibrs'] * 1.1 + 0.0005 and res['score'] < selected['score']:
            selected = res
    return selected, results


def _pick_best(table):
    """Klipper's find_best_shaper selection over an already fitted table."""
    best = None
    for s in table:
        if (best is None or s['score'] * 1.2 < best['score']
                or (s['score'] * 1.05 < best['score'] and s['smoothing'] * 1.1 < best['smoothing'])):
            best = s
    if best['name'] == 'zv':
        for s in table:
            if s['name'] != 'zv' and s['vibrs'] * 1.1 < best['vibrs']:
                best = s
                break
    return best


def _fit_shapers(freqs, psd, scv=5.0):
    best = None
    table = []
    for name in AUTOTUNE_SHAPERS:
        sel, _results = _fit_one_shaper(name, freqs, psd, scv)
        if (best is None or sel['score'] * 1.2 < best['score']
                or (sel['score'] * 1.05 < best['score'] and sel['smoothing'] * 1.1 < best['smoothing'])):
            best = sel
        table.append(sel)
    if best['name'] == 'zv':
        for s in table:
            if s['name'] != 'zv' and s['vibrs'] * 1.1 < best['vibrs']:
                best = s
                break
    return best, table


def _normalize_psd(freqs, psd):
    """Klipper's CalibrationData.normalize_to_frequencies (in place copy)."""
    out = []
    for f, p in zip(freqs, psd):
        val = p / (f + 0.1)
        if f < 10.0:                      # 2 * MIN_FREQ low-frequency rolloff
            val *= math.exp(-((10.0 / (f + 0.1)) ** 2) + 1.0)
        out.append(val)
    return out


# ---- resonance CSV discovery + parsing ----------------------------------------

_RESONANCE_RE = re.compile(r'^(calibration_data|calibrated|resonances)[_\-]([xyz])[_\-]', re.I)


def _cfg_val(cfg_path, section, key, default):
    """read one value from a Klipper config ('=' or ':' separated, comments ok)."""
    try:
        with open(cfg_path) as f:
            text = f.read()
    except OSError:
        return default
    sec = None
    for raw in text.split('\n'):
        l = raw.split('#')[0].split(';')[0].strip()
        if not l:
            continue
        if l.startswith('[') and l.endswith(']'):
            sec = l[1:-1].strip().lower()
            continue
        if sec == section:
            m = re.match(r'([^:=]+)[:=](.*)$', l)
            if m and m.group(1).strip().lower() == key:
                return m.group(2).strip()
    return default


def _resonance_csv_dirs(base_dir):
    """candidate dirs holding the resonance CSVs (save_path first)."""
    cfg_dir = os.path.join(base_dir, 'config')
    sp = _cfg_val(os.path.join(cfg_dir, 'printer.cfg'), 'resonance_tester', 'save_path', '')
    dirs = []
    for c in (sp, '/tmp', os.path.join(base_dir, 'compressor'), cfg_dir):
        if not c:
            continue
        c = os.path.expanduser(c)
        if not os.path.isabs(c):
            c = os.path.abspath(c)
        if c not in dirs and os.path.isdir(c):
            dirs.append(c)
    return dirs or ['/tmp']


def _find_resonance_csv(axis, dirs):
    """newest CSV for AXIS; prefers files that already carry a shaper table."""
    axis = axis.lower()
    cands = []
    for d in dirs:
        try:
            names = os.listdir(d)
        except OSError:
            continue
        for fn in names:
            if not fn.lower().endswith('.csv'):
                continue
            m = _RESONANCE_RE.match(fn)
            if m and m.group(2).lower() == axis:
                p = os.path.join(d, fn)
                try:
                    cands.append((os.path.getmtime(p), p))
                except OSError:
                    pass
    if not cands:
        return None
    cands.sort()
    fallback = None
    for _mt, p in reversed(cands):
        try:
            with open(p) as f:
                head = f.readline()
        except OSError:
            continue
        if 'shapers:' in head:
            return p
        if fallback is None:
            fallback = p
    return fallback


def _parse_resonance_csv(path):
    """Klipper resonance CSV -> dict(freqs, psd, shapers, normalized)."""
    with open(path) as f:
        lines = [l.rstrip('\n') for l in f]
    if not lines:
        raise ValueError('%s: empty CSV' % os.path.basename(path))
    cols = [c.strip() for c in lines[0].split(',')]
    if not cols or cols[0].lower() != 'freq':
        raise ValueError('%s: not a Klipper resonance CSV (first column %r)'
                         % (os.path.basename(path), cols[:1]))
    psd_idx = None
    if 'psd_xyz' in cols:
        psd_idx = cols.index('psd_xyz')
    else:
        for i, c in enumerate(cols[1:], 1):
            if 'psd' in c.lower():
                psd_idx = i
                break
        if psd_idx is None and len(cols) > 1:
            psd_idx = 1                        # multi-dataset: first data column
    if psd_idx is None:
        raise ValueError('%s: no PSD column' % os.path.basename(path))
    shapers = []                                # [(name, freq, col_index)]
    if 'shapers:' in cols:
        for i, c in enumerate(cols):
            m = re.match(r'^(\w+)\(([\d.]+)\)$', c.strip())
            if m and i > psd_idx:
                shapers.append((m.group(1).lower(), float(m.group(2)), i))
    freqs, psd = [], []
    for l in lines[1:]:
        if not l.strip():
            continue
        parts = l.split(',')
        try:
            fr = float(parts[0])
            pv = float(parts[psd_idx])
        except (IndexError, ValueError):
            continue
        freqs.append(fr)
        psd.append(pv)
    if len(freqs) < 8:
        raise ValueError('%s: only %d data rows - not a usable resonance CSV'
                         % (os.path.basename(path), len(freqs)))
    base = os.path.basename(path).lower()
    return {'freqs': freqs, 'psd': psd, 'shapers': shapers,
            'normalized': base.startswith(('calibrated', 'calibration_data'))}


def _resonance_axis_data(axis, dirs, scv=5.0):
    """CSV for one axis -> {'file', 'freqs', 'psd', 'table', 'best'}."""
    p = _find_resonance_csv(axis, dirs)
    if not p:
        raise ValueError('no resonance CSV for axis %s (looked in %s) - run '
                         'CALIBRATE_SHAPER or DUMP_RESONANCES first'
                         % (axis.upper(), ', '.join(dirs)))
    d = _parse_resonance_csv(p)
    freqs, psd = d['freqs'], d['psd']
    if not d['normalized']:
        psd = _normalize_psd(freqs, psd)
    keep = [i for i, f in enumerate(freqs) if f < 200.0]
    freqs = [freqs[i] for i in keep]
    psd = [psd[i] for i in keep]
    table = []
    if d['shapers']:
        # SHAPER_CALIBRATE already fitted these - keep ITS frequencies
        for name, freq, _ci in d['shapers']:
            if name not in SHAPER_MIN_FREQ:
                continue
            A, T = _shaper_get(name, freq)
            vibrs = 0.0
            for dr in SHAPER_TEST_DAMPINGS:
                v, _vals = _remaining_vibrations(A, T, dr, freqs, psd)
                if v > vibrs:
                    vibrs = v
            table.append({'name': name, 'freq': freq, 'vibrs': vibrs,
                          'smoothing': _shaper_smoothing(A, T, 5000.0, scv),
                          'score': None, 'max_accel': _shaper_max_accel(A, T, scv)})
    else:
        _best, table = _fit_shapers(freqs, psd, scv)
    for s in table:
        if s['score'] is None:
            s['score'] = s['smoothing'] * (s['vibrs'] ** 1.5 + s['vibrs'] * 0.2 + 0.01)
    best = _pick_best(table)
    return {'file': os.path.basename(p), 'freqs': freqs, 'psd': psd,
            'table': table, 'best': best}


# ======================================================================================
#  R64 RESONANCE DIAGRAM RENDERER - one portrait plate per axis (PSD curve,
#  all 5 shaper response curves, tick labels, and the SHAPER TABLE with the
#  recommendation boxed). MODE=print -> thin plate via the normal print flow
#  (mesh + purge line + babystepping, like every R2 file); MODE=plot -> the
#  same diagram as a pen-plotter file (R2-PLOT header).
# ======================================================================================

RESO_PLATE_W, RESO_PLATE_H = 112.0, 150.0


def _reso_plate_content(axis, data, measure):
    """one diagram plate -> (strokes, texts) in local mm (origin bottom-left).

    measure(text, height_mm) -> width in mm (font specific, set by the backend)
    """
    strokes = []
    texts = []          # (text, x, y_bottom, height_mm, align 'l'|'c')
    W, H = RESO_PLATE_W, RESO_PLATE_H
    table = data['table']
    best = data['best']
    freqs, psd = data['freqs'], data['psd']

    def _loop(pts):
        return list(pts) + [pts[0]]

    # R73: all heights are CAP heights now (was: box height ~0.53x that) and
    # y values are BASELINES - the plate text is finally as big as it reads
    def _fit_h(text, h, max_w):
        # shrink a text's cap height until it fits max_w (font-proportional:
        # the PIXEL print font is ~1.6x wider per cap than the stroke fonts)
        while h > 2.5 and measure(text, h) > max_w:
            h -= 0.25
        return h

    _title = '%s RESONANCES' % axis.upper()
    texts.append((_title, 4.0, H - 11.0, _fit_h(_title, 8.5, W - 8.0), 'l'))
    src = data['file']
    if len(src) > 26:
        src = src[:25] + '~'
    texts.append((src, 4.0, H - 16.0, _fit_h(src, 4.2, 56.0), 'l'))
    _dt = time.strftime('%Y-%m-%d')
    texts.append((_dt, W - 4.0, H - 16.0, _fit_h(_dt, 4.2, 38.0), 'r'))

    # ---- chart frame -------------------------------------------------------
    x0, x1 = 7.0, W - 7.0
    y0, y1 = 56.0, H - 24.0
    fmax = max(freqs)
    fmax = min(200.0, math.ceil(fmax / 10.0) * 10.0)
    fmax = max(50.0, fmax)

    def fx(f):
        return x0 + (f / fmax) * (x1 - x0)

    # ---- PSD curve (log scale like Klipper's graph) - FIRST = bold stroke --
    logs = [math.log10(max(p, 1e-12)) for p in psd]
    lmin, lmax = min(logs), max(logs)
    if lmax - lmin < 1e-6:
        lmax = lmin + 1.0
    pad = (lmax - lmin) * 0.06
    lmin, lmax = lmin - pad, lmax + pad

    def ly(v):
        return y0 + 1.5 + (v - lmin) / (lmax - lmin) * (y1 - y0 - 3.0)

    step = max(1, len(freqs) // 170)
    curve = [(fx(fr), ly(lv)) for fr, lv in zip(freqs[::step], logs)]
    if freqs[-1] != freqs[::step][-1]:
        curve.append((fx(freqs[-1]), ly(logs[-1])))
    strokes.append(curve)                    # index 0 - drawn double-weight

    strokes.append(_loop(_rect_loop(x0, y0, x1, y1)))
    # x ticks + labels
    tstep = 10.0 if fmax <= 110.0 else 20.0
    f = tstep
    while f < fmax:
        strokes.append([(fx(f), y0), (fx(f), y0 - 1.8)])
        _tk = '%d' % int(f)
        texts.append((_tk, fx(f), y0 - 7.0, _fit_h(_tk, 4.2, 11.0), 'c'))
        f += tstep
    texts.append(('Hz', x1, y0 - 7.0, _fit_h('Hz', 4.2, 10.0), 'r'))
    texts.append(('PSD', x0 + 1.0, y1 + 1.0, _fit_h('PSD', 3.5, 12.0), 'l'))

    # ---- shaper response curves (thin, ride high, dip at the notch) --------
    for s in table:
        try:
            A, T = _shaper_get(s['name'], s['freq'])
            resp = _shaper_response(A, T, SHAPER_DEFAULT_DAMPING, freqs[::step])
        except ValueError:
            continue
        strokes.append([(fx(fr), y1 - v * (y1 - y0) * 0.62)
                        for fr, v in zip(freqs[::step], resp)])

    # ---- peak marker --------------------------------------------------------
    pk = max(range(len(psd)), key=lambda i: psd[i])
    px, py = fx(freqs[pk]), ly(logs[pk])
    strokes.append(_loop(_circle(px, py, 1.1, 14)))
    _pk = '%dHz' % round(freqs[pk])
    _pkh = _fit_h(_pk, 4.2, 24.0)
    _pkw = measure(_pk, _pkh)
    # keep the centered label INSIDE the plate (a peak near the right edge
    # used to push the text past the plate border)
    _pkx = max(2.0 + _pkw / 2.0, min(W - 2.0 - _pkw / 2.0, px))
    texts.append((_pk, _pkx, py + 2.2 if py < y1 - 8 else py - 7.2, _pkh, 'c'))

    # ---- shaper table (R73: cap-height text ~1.8x the old visual size;
    #      columns + adaptive VIBR format keep everything clear of the 112mm) --
    hdr = [('NR', 3.5, 'l', 6.0), ('SHAPER', 9.5, 'l', 24.0), ('FREQ', 52.0, 'r', 15.0),
           ('VIBR', 73.0, 'r', 18.0), ('SMOOTH', 97.0, 'r', 17.0)]
    for t, x, al, mw in hdr:
        texts.append((t, x, 46.0, _fit_h(t, 4.0, mw), al))
    strokes.append([(4.0, 51.5), (W - 4.0, 51.5)])
    names = {'zv': 'ZV', 'mzv': 'MZV', 'zvd': 'ZVD', 'ei': 'EI',
             '2hump_ei': '2HUMP', '3hump_ei': '3HUMP'}
    for i, s in enumerate(table):
        y = 39.0 - i * 7.0
        texts.append(('%d' % (i + 1), 3.5, y, _fit_h('%d' % (i + 1), 4.5, 6.0), 'l'))
        _nm = names.get(s['name'], s['name'].upper())
        texts.append((_nm, 9.5, y, _fit_h(_nm, 4.5, 24.0), 'l'))
        _fr = '%.1f' % s['freq']
        texts.append((_fr, 52.0, y, _fit_h(_fr, 4.5, 15.0), 'r'))
        vib = s['vibrs'] * 100.0
        _vb = ('%.1f%%' % vib) if vib < 9.95 else ('%d%%' % round(vib))
        texts.append((_vb, 73.0, y, _fit_h(_vb, 4.5, 18.0), 'r'))
        _sm = '%.3f' % s['smoothing']
        texts.append((_sm, 97.0, y, _fit_h(_sm, 4.5, 17.0), 'r'))
        if s is best:
            strokes.append(_loop(_rect_loop(2.0, y - 2.0, 74.0, y + 6.5)))
            texts.append(('OK', W - 4.5, y, _fit_h('OK', 4.5, 9.0), 'r'))
    _pick = 'PICK: VIBRATION CAL > APPLY %s' % axis.upper()
    _ph = _fit_h(_pick, 4.2, W - 8.0)
    if measure(_pick, _ph) > W - 8.0:
        # very wide font (PIXEL print plates): shorter wording instead of
        # overflowing the plate border
        _pick = 'PICK: APPLY %s' % axis.upper()
        _ph = _fit_h(_pick, 4.2, W - 8.0)
    texts.append((_pick, 4.0, 2.5, _ph, 'l'))
    return strokes, texts


def _measure_text(text, h, font):
    """width of text at CAP height h mm (R73: sizes mean cap height now)."""
    g = _label_glyphs(font)
    scale = h / g['cap_units']
    return sum(g.get(ch, g.get(ch.upper(), (4.0, [])))[0] for ch in text) * scale


def _render_texts(texts, font):
    """backend text -> stroke polylines via the label font machinery.

    R73: (text, x, y_BASELINE, cap_height_mm, align) - y is the BASELINE the
    glyphs sit on (cap height above it, descenders below), so uppercase,
    lowercase and punctuation finally share one line.
    """
    g = _label_glyphs(font)
    out = []
    for text, x, y, h, align in texts:
        if not text:
            continue
        w = _measure_text(text, h, font)
        if align == 'c':
            x = x - w / 2.0
        elif align == 'r':
            x = x - w
        scale = h / g['cap_units']
        _w, _h, sts = _label_text(text, font)
        base = g['baseline']
        for st in sts:
            pts = [(x + px * scale, y + (base - py) * scale) for (px, py) in st]
            if len(pts) > 1:
                out.append(pts)
    return out


def make_resonance(axes=('x', 'y'), mode='print', out_dir='.', bed=None, version=1,
                   material='PLA', var_path=None, csv_dirs=None, scv=5.0,
                   layer_h=0.2, first_h=0.28, base_layers=3, feat_layers=2,
                   nozzle=0.6):
    """R64: render the resonance diagram plate(s). Returns (files, info)."""
    mode = str(mode).lower()
    if mode not in ('print', 'plot'):
        mode = 'print'
    axes = [str(a).lower() for a in axes if str(a).lower() in ('x', 'y')]
    if not axes:
        raise ValueError('AXIS must be X, Y or BOTH')
    if csv_dirs is None:
        csv_dirs = ['/tmp']
    data = {ax: _resonance_axis_data(ax, csv_dirs, scv=scv) for ax in axes}

    if bed is None:
        bed = (0.0, -1.0, 244.0, 238.0)
    bx0, by0, bx1, by1 = bed
    ux0, uy0 = bx0 + 6.0, by0 + 6.0
    ux1, uy1 = bx1 - 6.0, by1 - 6.0
    uw, uh = ux1 - ux0, uy1 - uy0

    files = []
    info = {'axes': {}, 'mode': mode}
    suffix = ''.join(a.upper() for a in axes)
    # both axes side by side if that fits, otherwise one file per axis
    grouped = len(axes) == 2 and (2 * RESO_PLATE_W + 6.0) <= uw and RESO_PLATE_H <= uh
    if grouped:
        plates = []
        gx0 = ux0 + (uw - (2 * RESO_PLATE_W + 6.0)) / 2.0
        gy0 = uy0 + (uh - RESO_PLATE_H) / 2.0
        for i, ax in enumerate(axes):
            plates.append((ax, gx0 + i * (RESO_PLATE_W + 6.0), gy0))
    else:
        plates = []
        for i, ax in enumerate(axes):
            if RESO_PLATE_W > uw or RESO_PLATE_H > uh:
                raise ValueError('diagram plate %dx%dmm does not fit the bed '
                                 '(%.0fx%.0fmm usable)' % (RESO_PLATE_W, RESO_PLATE_H, uw, uh))
            plates.append((ax, ux0 + (uw - RESO_PLATE_W) / 2.0, uy0 + (uh - RESO_PLATE_H) / 2.0))

    for ax, d in data.items():
        b = d['best']
        info['axes'][ax] = {
            'file': d['file'], 'best': b,
            'best_txt': '%s@%.1fHz %.1f%%' % (b['name'], b['freq'], b['vibrs'] * 100.0),
            'table': [(s['name'], round(s['freq'], 1), round(s['vibrs'] * 100.0, 1),
                       round(s['smoothing'], 3)) for s in d['table']]}

    if mode == 'plot':
        # ---- pen plotter variant ------------------------------------------------
        v = _read_vars(var_path) if var_path else {}

        def _vf(key, dflt):
            try:
                return float(v.get(key, dflt))
            except (TypeError, ValueError):
                return float(dflt)
        bmin_x, bmin_y = _vf('plot_bed_min_x', 5), _vf('plot_bed_min_y', 5)
        bmax_x, bmax_y = _vf('plot_bed_max_x', 239), _vf('plot_bed_max_y', 233)
        pw = max(20.0, min(RESO_PLATE_W, (bmax_x - bmin_x) - 4))
        ph = max(20.0, min(RESO_PLATE_H, (bmax_y - bmin_y) - 4))
        font = str(v.get('plot_text_font', 'SMOOTH') or 'SMOOTH').upper()
        if font not in ('SMOOTH', 'MONO', 'COND', 'NARROW', 'CAPS'):
            font = 'SMOOTH'
        lays = []
        lay_w = sum(1 for _ in plates)
        total_w = lay_w * pw + (lay_w - 1) * 6.0
        sx = min(1.0, ((bmax_x - bmin_x) - 4) / max(total_w, 0.001))
        sy = min(1.0, ((bmax_y - bmin_y) - 4) / ph)
        ox = bmin_x + (((bmax_x - bmin_x) - total_w * sx) / 2.0)
        oy = bmin_y + (((bmax_y - bmin_y) - ph * sy) / 2.0)
        for i, (ax, _gx, _gy) in enumerate(plates):
            strokes, texts = _reso_plate_content(ax, data[ax],
                                                  lambda t, h: _measure_text(t, h, font))
            polys = list(strokes) + _render_texts(texts, font)
            bx = ox + i * (pw + 6.0) * sx
            for pl in polys:
                lays.append([(bx + (px / RESO_PLATE_W) * pw * sx,
                              oy + (py / RESO_PLATE_H) * ph * sy) for px, py in pl])
        fname = '00_Resonance_%s_plot_V%02d.gcode' % (suffix, max(1, min(int(version), 99)))
        out = os.path.join(out_dir, fname)
        notes = ['; R2-RESONANCE diagram (pen plot) from %s'
                 % ', '.join(data[ax]['file'] for ax in axes),
                 '; shaper table + response curves - pick one, then Vibration Cal > Apply %s'
                 % '/'.join(a.upper() for a in axes)]
        _plot_write(out, lays, notes, var_path,
                    extrude=int(_vf('plot_extrude', 0)) == 1)
        files.append(out)
        info['file'] = fname
        return files, info

    # ---- 3d print variant ------------------------------------------------------
    wid = max(0.4, nozzle * 1.08)
    twid = max(0.4, nozzle * 1.02)
    fil = FIL_AREA
    total_layers = base_layers + feat_layers
    L = []
    a = L.append
    a('; R2-RESONANCE generated diagram (R64) - start it like any other file')
    a('; axes: %s | source: %s' % (', '.join(a2.upper() for a2 in axes),
                                   ', '.join(data[ax]['file'] for ax in axes)))
    a('; plate %gx%gmm, %d base + %d feature layers @ %.2gmm (first %.2gmm), single color'
      % (RESO_PLATE_W, RESO_PLATE_H, base_layers, feat_layers, layer_h, first_h))
    for ax in axes:
        b = data[ax]['best']
        a('; %s shaper table: %s | recommended: %s'
          % (ax.upper(), ' '.join('%s(%.1fHz,%.1f%%)' % (s['name'], s['freq'], s['vibrs'] * 100.0)
                                  for s in data[ax]['table']),
             '%s@%.1fHz' % (b['name'], b['freq'])))
    a('; filament_type = %s' % material)
    a('; layer_height = %.2g' % layer_h)
    a('; nozzle_diameter = %.1f' % nozzle)
    a('; line_width = %.2g' % wid)
    a('; outer_wall_line_width = %.2g' % wid)
    a('; outer_wall_speed = 40')
    a('; inner_wall_speed = 45')
    a('; top_surface_speed = 40')
    a('; internal_solid_infill_speed = 55')
    a('; initial_layer_speed = 25')
    a('; travel_speed = 150')
    a('; wall_loops = 2')
    contents = {}
    for ax, gx, gy in plates:
        strokes, texts = _reso_plate_content(ax, data[ax],
                                             lambda t, h: _measure_text(t, h, 'PIXEL'))
        txt_strokes = _render_texts(texts, 'PIXEL')
        contents[ax] = (gx, gy, strokes, txt_strokes)
        poly = '[[%.1f,%.1f],[%.1f,%.1f],[%.1f,%.1f],[%.1f,%.1f]]' % (
            gx, gy, gx + RESO_PLATE_W, gy, gx + RESO_PLATE_W, gy + RESO_PLATE_H, gx, gy + RESO_PLATE_H)
        a('EXCLUDE_OBJECT_DEFINE NAME=RESONANCE_%s CENTER=%.1f,%.1f POLYGON=%s'
          % (ax.upper(), gx + RESO_PLATE_W / 2.0, gy + RESO_PLATE_H / 2.0, poly))
    a('PRINT_START MATERIAL=%s LAYER_HEIGHT=%.2g TOTAL_LAYERS=%d OUTER_WALL_SPEED=40'
      % (material, layer_h, total_layers))
    a('G90')
    a('M83')
    a('M107   ; R2-RESONANCE: first layer = fan off')

    pen = _Pen(L, jump_d=6.0)   # R77: no retracts between neighboring hatch lines

    def layer_h_eff(li):
        return first_h if li == 1 else layer_h

    def base_block(ax, li):
        gx, gy = contents[ax][0], contents[ax][1]
        x0, y0 = gx + wid / 2.0, gy + wid / 2.0
        x1, y1 = gx + RESO_PLATE_W - wid / 2.0, gy + RESO_PLATE_H - wid / 2.0
        e_wall = layer_h_eff(li) * wid / fil
        L.append('EXCLUDE_OBJECT_START NAME=RESONANCE_%s' % ax.upper())
        if li == 1:
            L.append(';TYPE:Brim')
            for off in (wid * 0.35, wid * 0.35 + wid):
                b = (gx - off, gy - off, gx + RESO_PLATE_W + off, gy + RESO_PLATE_H + off)
                _emit_loop(pen, _rect_loop(*b), e_wall, 1500)
        L.append(';TYPE:Outer wall')
        _emit_loop(pen, _rect_loop(x0, y0, x1, y1), e_wall, 1500 if li == 1 else 2400)
        L.append(';TYPE:Inner wall')
        _emit_loop(pen, _rect_loop(x0 + wid, y0 + wid, x1 - wid, y1 - wid), e_wall,
                   1500 if li == 1 else 2700)
        L.append(';TYPE:Internal solid infill')
        segs = _hatch(x0 + wid + 0.1, y0 + wid + 0.1, x1 - wid - 0.1, y1 - wid - 0.1,
                      None, wid, 45.0 if li % 2 else 135.0)
        _emit_hatch(pen, segs, e_wall, 1500 if li == 1 else 3300)
        L.append('EXCLUDE_OBJECT_END NAME=RESONANCE_%s' % ax.upper())

    def feature_block(ax, li):
        gx, gy, strokes, txt_strokes = contents[ax]
        e_line = layer_h_eff(li) * twid / fil
        L.append('EXCLUDE_OBJECT_START NAME=RESONANCE_%s' % ax.upper())
        L.append(';TYPE:Outer wall')
        for pl in strokes:
            pen.travel(pl[0][0] + gx, pl[0][1] + gy, feed=9000, hop=True)
            px, py = pl[0]
            for (x, y) in pl[1:]:
                if math.hypot(x - px, y - py) < 0.12:
                    continue
                pen.extrude(gx + x, gy + y, math.hypot(x - px, y - py) * e_line, 1320)
                px, py = x, y
            if pl is strokes[0]:                 # PSD curve: second pass = bolder
                pen.travel(pl[0][0] + gx + 0.08, pl[0][1] + gy, feed=9000, hop=True)
                px, py = pl[0]
                for (x, y) in pl[1:]:
                    pen.extrude(gx + x + 0.08, gy + y, math.hypot(x - px, y - py) * e_line, 1320)
                    px, py = x, y
        for pl in txt_strokes:
            pen.travel(pl[0][0] + gx, pl[0][1] + gy, feed=9000, hop=True)
            px, py = pl[0]
            for (x, y) in pl[1:]:
                if math.hypot(x - px, y - py) < 0.12:
                    continue
                pen.extrude(gx + x, gy + y, math.hypot(x - px, y - py) * e_line, 1320)
                px, py = x, y
        L.append('EXCLUDE_OBJECT_END NAME=RESONANCE_%s' % ax.upper())

    for li in range(1, base_layers + 1):
        z = round(first_h + (li - 1) * layer_h, 3)
        L.append(';LAYER_CHANGE')
        L.append(';Z:%.3f' % z)
        pen.set_z(z)
        if li == 2:
            L.append('M106 S178   ; R2-RESONANCE: part fan from layer 2')
        for ax in axes:
            base_block(ax, li)
    for fi in range(1, feat_layers + 1):
        z = round(first_h + (base_layers - 1) * layer_h + fi * layer_h, 3)
        L.append(';LAYER_CHANGE')
        L.append(';Z:%.3f' % z)
        pen.set_z(z)
        for ax in axes:
            feature_block(ax, fi)
    a('M107')
    a('PRINT_END')

    fname = '00_Resonance_%s_V%02d.gcode' % (suffix, max(1, min(int(version), 99)))
    out = os.path.join(out_dir, fname)
    with open(out, 'w') as f:
        f.write('\n'.join(L) + '\n')
    try:
        process(out)
    except Exception as e:                                  # noqa: BLE001
        print('[reso] WARNING: post-process failed for %s: %r' % (fname, e), flush=True)
    files.append(out)
    info['file'] = fname
    info['layers'] = total_layers
    return files, info


# ======================================================================================
#  R64 TEXT -> PLOTTER (PLOT_TEXT / name.txt.gcode) + STATUS PLOT (PLOT_STATUS)
#  Plain text files are rendered with the label stroke fonts, auto-wrapped and
#  auto-scaled so the WHOLE text fits one page (= one plot).
# ======================================================================================

def _wrap_text(raw_lines, page_w, size, font):
    # R73: 'size' = CAP height in mm (was the full glyph box - the letters
    # printed at ~53% of the set size)
    glyphs = _label_glyphs(font)
    scale = size / glyphs['cap_units']

    def wlen(s):
        return sum(glyphs.get(ch, glyphs.get(ch.upper(), (4.0, [])))[0] for ch in s) * scale

    out = []
    for raw in raw_lines:
        raw = raw.rstrip()
        if not raw:
            out.append('')
            continue
        out.append('')                      # every source line starts a new line
        for chunk in raw.split(' '):
            # hard-split single words wider than the page
            while wlen(chunk) > page_w and len(chunk) > 1:
                k = len(chunk)
                while k > 1 and wlen(chunk[:k]) > page_w:
                    k -= 1
                out[-1] = chunk[:k]
                out.append('')
                chunk = chunk[k:]
            cur = out[-1]
            cand = chunk if cur == '' else (cur + ' ' + chunk)
            if wlen(cand) <= page_w:
                out[-1] = cand
            else:
                out.append(chunk)
    while out and out[-1] == '':
        out.pop()
    return out


def _fit_text_page(raw_lines, page_w, page_h, size, font, min_size=6.0):
    """R73: letters never shrink below 6mm caps - the page grows COLUMNS
    instead (up to 3 side by side), and only a truly huge text gets truncated
    with a note. Returns (columns, size): columns = list of line-lists."""
    size = max(min_size, size)
    for ncols in (1, 2, 3):
        col_w = (page_w - (ncols - 1) * 6.0) / ncols
        lines = _wrap_text(raw_lines, col_w, size, font)
        per_col = max(1, int(page_h // (size * 1.5)))
        if len(lines) <= ncols * per_col:
            cols = [lines[i * per_col:(i + 1) * per_col]
                    for i in range(ncols)]
            return cols, size
    # still too long at 3 columns: truncate with a note line
    col_w = (page_w - 12.0) / 3.0
    lines = _wrap_text(raw_lines, col_w, size, font)
    per_col = max(1, int(page_h // (size * 1.5)))
    total = 3 * per_col
    if len(lines) > total:
        cut = len(lines) - total
        lines = lines[:total - 1] + ['(+%d more lines)' % cut]
    cols = [lines[i * per_col:(i + 1) * per_col] for i in range(3)]
    return cols, size


def _text_page_polys(cols, page_w, page_h, size, font, solid=False, line_w=0.65):
    """text columns -> polylines in page coords (origin bottom-left, y up).

    R73: baseline-aligned glyphs (shared baseline per line), 'size' = cap
    height. solid=True expands every stroke into a double-walled bundle
    (_stroke_offsets) so FILAMENT plots read solid instead of hairlines.
    """
    g = _label_glyphs(font)
    scale = size / g['cap_units']
    lh = size * 1.5
    ncols = max(1, len(cols))
    col_w = (page_w - (ncols - 1) * 6.0) / ncols
    polys = []
    for c, lines in enumerate(cols):
        col_x = c * (col_w + 6.0)
        for i, line in enumerate(lines):
            if not line:
                continue
            _w, _h, sts = _label_text(line, font)
            base_y = page_h - (i + 1) * lh
            # center the line block horizontally in its column
            lw = _w * scale
            x_off = col_x + (col_w - lw) / 2.0
            for st in sts:
                pts = [(x_off + px * scale,
                        base_y + (g['baseline'] - py) * scale) for (px, py) in st]
                if len(pts) < 2:
                    continue
                if solid:
                    half = min(3.0 * line_w, 0.34 * size) / 2.0
                    for path in _stroke_offsets(pts, half, line_w):
                        polys.append(path)
                else:
                    polys.append(pts)
    return polys


def _plot_write(path, polys, notes, var_path=None, extrude=False):
    """shared pen-plotter g-code writer (single pen).

    R73 FILAMENT mode: the old writer dragged the nozzle at the PEN z (0mm) -
    nothing could exit the nozzle, the plot came out as faint hairs. Filament
    plots now run at a real draw height (plot_fil_z, default 0.25mm) with the
    matching extrusion per mm, a small retract on far travels and SHORT flat
    travels between nearby strokes (no hop, no retract = far fewer 'hops').
    Pen mode keeps the classic up/down taps. Travel is capped at 80mm/s.
    """
    v = _read_vars(var_path) if var_path else {}

    def _vf(key, dflt):
        try:
            return float(v.get(key, dflt))
        except (TypeError, ValueError):
            return float(dflt)
    z_up = _vf('plot_z_up', 3.0)
    spd = _vf('plot_speed', 40) * 60
    trv = min(_vf('plot_travel', 120) * 60, 4800.0)
    e_per_mm = 0.0
    z_dn = _vf('plot_z_down', 0.0) + _vf('plot_off_z', 0.0)
    if extrude:
        fil_z = min(0.4, max(0.1, _vf('plot_fil_z', 0.25)))
        z_dn = _vf('plot_off_z', 0.0) + fil_z
        e_per_mm = fil_z * 0.65 / FIL_AREA
    L = ['; R2-PLOT v4 - %s' % (notes[0][2:] if notes and notes[0].startswith('; ') else 'pen plot')]
    L += notes[1:]
    L += ['; mode: %s | draw Z %.2f | travel capped 80mm/s' % ('FILAMENT' if extrude else 'PEN', z_dn),
          '; pen Z/speeds/mode/offsets: Plotter menu | live: speed %, babystepping = pen pressure',
          '; start overrides (speed/Z/XY) apply at plot start: Plotter > Start',
          TAG,
          '_PLOT_START EXTRUDE=%d' % (1 if extrude else 0),
          'G21',
          'G90']
    # R75: register the plot area as an object - the mesh before the held file
    # runs then covers the plot area only (KAMP adaptive) instead of the full
    # bed (field log .58: full-bed mesh travels = 'Timer too close' shutdowns)
    if polys:
        _xs = [p[0] for pts in polys for p in pts]
        _ys = [p[1] for pts in polys for p in pts]
        _x0, _x1, _y0, _y1 = min(_xs), max(_xs), min(_ys), max(_ys)
        _poly = '[[%.1f,%.1f],[%.1f,%.1f],[%.1f,%.1f],[%.1f,%.1f]]' % (
            _x0, _y0, _x1, _y0, _x1, _y1, _x0, _y1)
        L.append('EXCLUDE_OBJECT_DEFINE NAME=R2PLOT CENTER=%.1f,%.1f POLYGON=%s'
                 % ((_x0 + _x1) / 2.0, (_y0 + _y1) / 2.0, _poly))
        L.append('EXCLUDE_OBJECT_START NAME=R2PLOT')
    if extrude:
        L += ['M83', 'G92 E0']
    _emit_plot(L, polys, trv, spd, extrude, z_up, z_dn, e_per_mm)
    if polys:
        L.append('EXCLUDE_OBJECT_END NAME=R2PLOT')
    L += ['G0 Z%.2f F600' % (z_up + 5), 'G0 X5 Y190 F4800', 'M107', 'M84']
    with open(path, 'w') as f:
        f.write('\n'.join(L) + '\n')
    return len(L)


def _emit_plot(L, polys, trv, spd, extrude, z_up, z_dn, e_per_mm, connect_mm=2.2):
    """R73 plot move emitter - shared by _plot_write and plot_convert.

    Polylines are drawn pen-down; between strokes: far = retract (filament) +
    z-hop + travel, near (<= connect_mm) = short flat travel (filament) or a
    quick hop (pen). Single points = stipple dots.
    """
    cx = cy = None
    for pts in polys:
        if len(pts) < 2:
            if not pts:
                continue
            x0, y0 = pts[0]
            _travel(L, cx, cy, x0, y0, trv, extrude, z_up, z_dn)
            L.append('G1 Z%.2f F600' % z_dn)
            if extrude:
                L.append('G1 E%.3f F120' % max(0.06, e_per_mm * 1.4))
            L.append('G0 Z%.2f F600' % z_up)
            cx, cy = x0, y0
            continue
        x0, y0 = pts[0]
        _travel(L, cx, cy, x0, y0, trv, extrude, z_up, z_dn, connect_mm)
        L.append('G1 Z%.2f F600' % z_dn)
        px, py = x0, y0
        for x, y in pts[1:]:
            d = math.hypot(x - px, y - py)
            if d < 0.02:
                continue
            if extrude:
                L.append('G1 X%.2f Y%.2f E%.4f F%d' % (x, y, d * e_per_mm, spd))
            else:
                L.append('G1 X%.2f Y%.2f F%d' % (x, y, spd))
            px, py = x, y
        L.append('G0 Z%.2f F600' % z_up)
        cx, cy = px, py


def _travel(L, cx, cy, x, y, trv, extrude, z_up, z_dn, connect_mm=2.2):
    if cx is None:
        L.append('G0 X%.2f Y%.2f F%d' % (x, y, trv))
        return
    d = math.hypot(x - cx, y - cy)
    if extrude:
        if d <= connect_mm:
            L.append('G0 X%.2f Y%.2f F%d' % (x, y, trv))    # flat: keeps pressure
            return
        L.append('G10')
        L.append('G0 Z%.2f F600' % z_up)
        L.append('G0 X%.2f Y%.2f F%d' % (x, y, trv))
        L.append('G0 Z%.2f F600' % z_dn)
        L.append('G11')
    else:
        L.append('G0 Z%.2f F600' % z_up)
        L.append('G0 X%.2f Y%.2f F%d' % (x, y, trv))
        L.append('G0 Z%.2f F600' % z_dn)


def text_convert(path, out=None, var_path=None):
    """R64: convert a plain text file into a pen-plotter g-code page."""
    with open(path, 'rb') as f:
        data = f.read()
    text = data.decode('utf-8', errors='replace')
    text = text.replace('\r\n', '\n').replace('\r', '\n').replace('\t', '    ')
    allowed = set(LABEL_CHARSET) | {' '}
    raw = []
    for l in text.split('\n')[:400]:
        raw.append(''.join(ch if ch in allowed else '?' for ch in l.rstrip()))
    if not [l for l in raw if l.strip()]:
        raise ValueError('%s: no printable text' % os.path.basename(path))
    v = _read_vars(var_path) if var_path else {}

    def _vf(key, dflt):
        try:
            return float(v.get(key, dflt))
        except (TypeError, ValueError):
            return float(dflt)
    bmin_x, bmin_y = _vf('plot_bed_min_x', 5), _vf('plot_bed_min_y', 5)
    bmax_x, bmax_y = _vf('plot_bed_max_x', 239), _vf('plot_bed_max_y', 233)
    page_w = (bmax_x - bmin_x) - 8.0
    page_h = (bmax_y - bmin_y) - 8.0
    size = max(6.0, min(_vf('plot_text_size', 7.0), 20.0))    # R73: >=6mm caps
    font = str(v.get('plot_text_font', 'SMOOTH') or 'SMOOTH').upper()
    if font not in ('SMOOTH', 'MONO', 'COND', 'NARROW', 'CAPS'):
        font = 'SMOOTH'
    cols, size = _fit_text_page(raw, page_w, page_h, size, font)
    extrude = int(_vf('plot_extrude', 0)) == 1
    polys = _text_page_polys(cols, page_w, page_h, size, font,
                             solid=extrude, line_w=0.65)
    polys = [[(px + bmin_x + 4.0, py + bmin_y + 4.0) for (px, py) in pl] for pl in polys]
    out = out or (path if path.endswith('.gcode') else path + '.gcode')
    n_lines = sum(len(c) for c in cols)
    notes = ['; text plot: %d line(s) in %d column(s), font %s, %.1fmm CAP letters'
             % (n_lines, len(cols), font, size),
             '; source: %s' % os.path.basename(path)]
    _plot_write(out, polys, notes, var_path, extrude=extrude)
    return out, n_lines, size


def _moonraker_status(host='127.0.0.1', port=7125):
    """query the live printer status via moonraker (best effort)."""
    import urllib.request
    import urllib.parse
    objs = ['gcode_move', 'extruder', 'heater_bed', 'toolhead', 'input_shaper',
            'bed_mesh', 'print_stats', 'gcode_macro _STATE', 'exclude_object']
    url = 'http://%s:%d/printer/objects/query?%s' % (
        host, port, '&'.join(urllib.parse.quote(o) for o in objs))
    with urllib.request.urlopen(url, timeout=3) as r:
        js = json.loads(r.read().decode())
    return (js.get('result') or {}).get('status') or {}


def _r2_version():
    try:
        p = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                         '..', 'macros', '01_state.cfg')
        with open(p) as f:
            for l in f:
                m = re.match(r'\s*variable_version\s*[:=]\s*[\'"]?([^\'"\s#]+)', l)
                if m:
                    return m.group(1)
    except OSError:
        pass
    return '?'


# names of ALL nonce channels (R75: primed after a watcher restart so a
# restart can never re-fire old jobs - field log .58 showed all four tools
# re-running in one burst right after the .58 update installed)
NONCE_KEYS = ('preview_nonce', 'range_nonce', 'label_gen_nonce', 'reso_nonce',
              'bridge_nonce', 'plot_text_nonce', 'plot_status_nonce', 'host_nonce')


def _prime_nonces(rv):
    """first loop pass: adopt the CURRENT counters, fire nothing."""
    return {k: (rv.get(k, '') or None) for k in NONCE_KEYS}


def _parse_ps(out):
    """R76: parse 'ps -eo pcpu,pmem,rss,comm --sort=-pcpu' output -> rows."""
    rows = []
    for row in out.split('\n')[1:]:
        f = row.split(None, 3)
        if len(f) == 4:
            try:
                rows.append((float(f[0]), float(f[1]), int(f[2]) // 1024, f[3].strip()))
            except ValueError:
                continue
    return rows


def _parse_vmstat_wa(line):
    """R76: the iowait percentage from a vmstat output line (None if unparsable)."""
    f = line.split()
    if len(f) >= 16:
        try:
            # 16 cols: ... us sy id wa | 17 cols: ... us sy id wa st
            return float(f[-1]) if len(f) == 16 else float(f[-2])
        except ValueError:
            pass
    return None


def _host_verdict(throttle_bits, load1, cores, swap_used_mb, swap_eaters=None):
    """R76/R78: the honest overall verdict - priority throttle > swap > overload > OK.

    The .59 field log showed why this is needed: 'Throttle: NONE ... Host is
    healthy' while the load average (4.2) SATURATED the Pi Zero 2's four
    cores - the host was starving klippy exactly then. Voltage and heat were
    never the problem; the CPU was simply full.
    R78: the .61 field log was the OPPOSITE picture - load 0.49, 47.2'C,
    Throttle NONE, but 187MB of swap after only 25 minutes uptime. The swap
    verdict now NAMES the processes sitting in the swap (swap_eaters from
    _swap_eaters()) - the top-RAM list alone could not explain them.
    """
    if throttle_bits:
        return False, 'Verdict: THROTTLED - see the flags above. Undervoltage = PSU/USB power, temperature = cooling.'
    if swap_used_mb >= 30:
        who = ''
        if swap_eaters:
            who = (' Swap residents: ' + ', '.join('%s %dMB' % (n, m) for m, n in swap_eaters[:3])
                   + ' - THAT is the RAM eater to switch off.')
        return False, ('Verdict: SWAPPING - %dMB swap in use (SD-card swap is ~100x slower than RAM, '
                       'the host stalls in bursts -> Timer too close).%s' % (swap_used_mb, who))
    if cores and load1 >= cores * 0.9:
        return False, ('Verdict: OVERLOADED - load %.1f on %d core(s) = saturated. The host cannot reliably '
                       'feed Klipper -> Timer too close. Top CPU below shows who.' % (load1, cores))
    return True, 'Verdict: OK - no throttle, load %.1f on %d core(s), no swap. The host can feed Klipper.' % (load1, cores or 1)


# R78: services checked by host_check (one systemctl is-active call covers all)
_SVC_CHECK = 'klipper moonraker avahi-daemon crowsnest sonar octoeverywhere pigpiod'

# R78: the measuring tools themselves must not appear in the top lists - the
# .61 field log showed 'Top CPU: ps 100%' which was the ps call measuring
# its own lifetime, not a real eater
_PS_MEAS = ('ps', 'head', 'tail', 'sh', 'bash', 'dash', 'sort', 'awk', 'grep', 'cut', 'sed', 'vmstat')


def _read_meminfo(path='/proc/meminfo'):
    """R78: /proc/meminfo as {key: MB} - its own function so tests can fake it."""
    mem = {}
    try:
        for l in open(path):
            kv = l.split(':', 1)
            if len(kv) == 2:
                mem[kv[0]] = int(kv[1].strip().split()[0]) // 1024    # MB
    except (OSError, ValueError):
        pass
    return mem


def _swap_eaters(proc='/proc', limit=6):
    """R78: WHO sits in the swap - VmSwap per process, aggregated by name.

    The .61 field log: 187MB swap after only 25 min uptime, load 0.49,
    Throttle NONE - verdict SWAPPING, but the top-3 RAM list (~91MB of
    pythons) could not explain where the rest lives. The missing eaters
    live IN the swap: VmSwap per /proc/<pid>/status, summed per process
    name, biggest first. This is the list that names the culprit.
    """
    agg = {}
    try:
        entries = os.listdir(proc)
    except OSError:
        return []
    for entry in entries:
        if not entry.isdigit():
            continue
        name = vmswap = None
        try:
            for l in open(os.path.join(proc, entry, 'status')):
                if l.startswith('Name:'):
                    name = l.split(':', 1)[1].strip()
                elif l.startswith('VmSwap:'):
                    parts = l.split()
                    vmswap = int(parts[1]) if len(parts) >= 2 else 0    # kB
                    break
        except (OSError, ValueError, IndexError):
            continue
        if name and vmswap:
            agg[name] = agg.get(name, 0) + vmswap
    return sorted(((kb / 1024.0, n) for n, kb in agg.items()), reverse=True)[:limit]


def host_check(host='127.0.0.1', port=7125, cores=None):
    """R75/R76/R78: read the HOST's health and report it in the console.

    'Timer too close' MCU shutdowns mean the host fell behind feeding the
    MCU. R75 checked the Pi's throttle flags (undervoltage/heat); the .59
    field log then showed a host with load 4.2 on four cores, NO throttle -
    a SATURATED but healthy Pi. R76 therefore also reports:
      - swap usage (SD-card swap = burst stalls)
      - the TOP CPU / TOP RAM processes (who eats the Pi?)
      - iowait (SD-card pressure)
    and reads /proc directly wherever possible (fewer subprocess spawns on
    a busy box - the .59 answer took 71 seconds to arrive!).
    R78 (field log .61: 187MB swap after only 25 min uptime, load 0.5,
    Throttle NONE - the top-3 RAM list could NOT explain the swap):
      - Top SWAP: VmSwap per process, aggregated by name -> names the eater
      - Services: one 'systemctl is-active' call (klipper/moonraker/avahi/
        crowsnest/sonar/OctoEverywhere/pigpiod) with targeted hints
      - the ps/head/... measurement artifacts are filtered out of the top
        lists ('Top CPU: ps 100%' in the field log was the ps itself)
      - top lists extended to 5 entries each
    """
    import subprocess

    def sh(cmd):
        try:
            r = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=12)
            return (r.stdout or r.stderr).strip()
        except Exception:                                     # noqa: BLE001
            return ''

    # ---- /proc reads (fast even on a saturated box) --------------------------------
    load1 = load5 = load15 = 0.0
    try:
        _la = open('/proc/loadavg').read().split()
        load1, load5, load15 = float(_la[0]), float(_la[1]), float(_la[2])
    except (OSError, ValueError, IndexError):
        pass
    cores = cores or os.cpu_count() or 1
    mem = _read_meminfo()
    ram_total = mem.get('MemTotal', 0)
    ram_free = mem.get('MemAvailable', 0)
    swap_total = mem.get('SwapTotal', 0)
    swap_used = max(0, swap_total - mem.get('SwapFree', 0))
    temp = ''
    try:
        temp = "temp=%.1f'C" % (int(open('/sys/class/thermal/thermal_zone0/temp').read().strip()) / 1000.0)
    except (OSError, ValueError):
        temp = sh('vcgencmd measure_temp')
    up = ''
    try:
        _up = float(open('/proc/uptime').read().split()[0])
        up = '%d min' % (_up / 60) if _up < 7200 else '%.1f h' % (_up / 3600)
    except (OSError, ValueError):
        up = sh("uptime -p | sed 's/^up //'")

    lines = ['HOST CHECK =========================',
             'Host: load %.2f %.2f %.2f on %d core(s) | CPU %s | RAM %dMB free of %dMB | swap %d/%dMB | up %s'
             % (load1, load5, load15, cores, temp or '?', ram_free, ram_total,
                swap_used, swap_total, up or '?')]

    # ---- throttle flags (Raspberry Pi only) -----------------------------------------
    thr = sh('vcgencmd get_throttled')
    throttle_bits = 0
    if thr.startswith('throttled=0x'):
        throttle_bits = int(thr.split('=')[1], 16)
        if throttle_bits == 0:
            lines.append('Throttle: NONE - no undervoltage, no frequency cap, no temperature limit.')
        else:
            flags = []
            if throttle_bits & 0x1:
                flags.append('UNDERVOLTAGE right now')
            if throttle_bits & 0x2:
                flags.append('CPU frequency capped right now')
            if throttle_bits & 0x4:
                flags.append('throttled right now')
            if throttle_bits & 0x8:
                flags.append('temperature limit right now')
            if throttle_bits & 0x10000:
                flags.append('undervoltage HAS occurred since boot')
            if throttle_bits & 0x20000:
                flags.append('frequency cap HAS occurred since boot')
            if throttle_bits & 0x40000:
                flags.append('throttling HAS occurred since boot')
            if throttle_bits & 0x80000:
                flags.append('temperature limit HAS occurred since boot')
            lines.append('Throttle: %s (raw 0x%x)' % (', '.join(flags) or 'none', throttle_bits))
            lines.append('  -> undervoltage = PSU/USB power too weak for the Pi | temperature = cool it |')
            lines.append('     a throttled Pi cannot feed Klipper -> MCU shutdowns (Timer too close)')
    elif thr:
        lines.append('Throttle: %s (no Raspberry Pi?)' % thr)
    else:
        lines.append('Throttle: vcgencmd not found - not a Raspberry Pi OS?')

    # ---- top processes: who eats the Pi? (R78: 5 entries, no measurement artifacts) ---
    top = [t for t in _parse_ps(sh("ps -eo pcpu,pmem,rss,comm --sort=-pcpu | head -8"))
           if t[3] not in _PS_MEAS]
    if top:
        lines.append('Top CPU: ' + ' | '.join('%s %.0f%%' % (n, c) for c, _m, _r, n in top[:5]))
        _byram = sorted(top, key=lambda t: -t[2])
        lines.append('Top RAM: ' + ' | '.join('%s %dMB' % (n, r) for _c, _m, r, n in _byram[:5]))

    # ---- R78: who SITS in the swap (the .61 field log: 187MB swap, top RAM ~91MB) ----
    swap_eaters = []
    if swap_used >= 30:
        swap_eaters = _swap_eaters()
        if swap_eaters:
            lines.append('Top SWAP: ' + ' | '.join('%s %dMB' % (n, m) for m, n in swap_eaters[:5])
                         + '  <- THESE live in the slow swap = your RAM eaters')
        else:
            lines.append('Top SWAP: no process residents found (kernel memory swapped out)')

    # ---- R78: which services run on the host (one systemctl call) --------------------
    svc_out = sh('systemctl is-active %s' % _SVC_CHECK)
    if svc_out:
        states = [s.strip() for s in svc_out.split('\n') if s.strip()]
        act = set()
        pairs = []
        for nm, st in zip(_SVC_CHECK.split(), states):
            if st == 'active':
                act.add(nm)
                pairs.append('%s=ON' % nm)
            else:
                pairs.append('%s=%s' % (nm, {'inactive': 'off'}.get(st, st or '?')))
        lines.append('Services: ' + ' '.join(pairs))
        if 'crowsnest' in act and 'sonar' in act:
            lines.append("  -> TWO webcam stacks at once (crowsnest + sonar)! One is already one too many on a Pi Zero 2 W;")
            lines.append("     switch off the one you do not use: sudo systemctl disable --now crowsnest   (or: sonar)")
        if 'avahi-daemon' in act:
            lines.append('  -> avahi-daemon still ON (the .60 field log caught it at 99% CPU): sudo systemctl disable --now avahi-daemon')
        if 'octoeverywhere' in act:
            lines.append('  -> OctoEverywhere ON - the cloud relay costs RAM+CPU on every print; off if you do not use it')

    wa = _parse_vmstat_wa(sh('vmstat 1 2 | tail -1'))
    if wa is not None and wa >= 5.0:
        lines.append('IO: %.0f%% iowait - processes are WAITING on the SD card (dying card or heavy I/O)' % wa)

    # ---- verdict (throttle > swap > overload > ok) --------------------------------------
    ok, verdict = _host_verdict(throttle_bits, load1, cores, swap_used, swap_eaters)
    lines.append(verdict)
    if not ok and not throttle_bits:
        lines.append("  typical eaters on a Pi Zero: webcam (crowsnest), sonar, OctoEverywhere,")
        lines.append("  moonraker's object processing (enable_object_processing: True), update manager,")
        lines.append("  a fan/temp script with SOFTWARE PWM (RPi.GPIO) - prefer pigpiod hardware PWM")

    script = ['RESPOND MSG="%s"' % l for l in lines]
    script.append('M117 %s' % ('Host OK' if ok else
                               'Host THROTTLED!' if throttle_bits else
                               'Host SWAPPING!' if swap_used >= 30 else 'Host OVERLOADED!'))
    script.append('_SOUND_LIB NAME=%s' % ('r2_done' if ok else 'r2_error'))
    try:
        _moonraker_gcode('\n'.join(script), host, port)
    except Exception:                                         # noqa: BLE001
        print('[host] moonraker unreachable - report goes here:', flush=True)
        for l in lines:
            print('   ' + l, flush=True)
    return lines


def make_status_plot(out=None, var_path=None, host='127.0.0.1', port=7125):
    """R64: draw the SHOW_STATUS report on paper (one page, auto-fit)."""
    v = _read_vars(var_path) if var_path else {}
    try:
        st = _moonraker_status(host, port)
    except Exception:                                       # noqa: BLE001
        st = {}

    def g(obj, key, dflt='?'):
        try:
            val = st[obj][key]
            return val if val is not None else dflt
        except (KeyError, TypeError):
            return dflt

    def pct(x):
        try:
            return '%d' % round(float(x) * 100)
        except (TypeError, ValueError):
            return '?'

    def n1(x):
        try:
            return '%.1f' % float(x)
        except (TypeError, ValueError):
            return '?'

    def n4(x):
        try:
            return '%.4f' % float(x)
        except (TypeError, ValueError):
            return '?'

    lines = []
    a = lines.append
    a('R2 STATUS ' + time.strftime('%Y-%m-%d %H:%M'))
    a('Version ' + _r2_version())
    a('Mode %s | Layer %s' % (g('gcode_macro _STATE', 'mode', '?'),
                              g('gcode_macro _STATE', 'layer', '?')))
    a('Material %s | File %s' % (v.get('material', 'PLA'),
                                 g('gcode_macro _STATE', 'file_material', '?')))
    a('Hotend %s/%sC Bed %s/%sC' % (n1(g('extruder', 'temperature', 0)),
                                    n1(g('extruder', 'target', 0)),
                                    n1(g('heater_bed', 'temperature', 0)),
                                    n1(g('heater_bed', 'target', 0))))
    a('PA %s | Smooth %s' % (n4(g('extruder', 'pressure_advance', 0)),
                             n1(g('extruder', 'smooth_time', 0.04))))
    a('Flow %s%% | Speed %s%%' % (pct(g('gcode_move', 'extrude_factor', 1)),
                                  pct(g('gcode_move', 'speed_factor', 1))))
    a('Accel %s | Vel %s' % (g('toolhead', 'max_accel', '?'),
                             g('toolhead', 'max_velocity', '?')))
    a('IS X %s %s | Y %s %s' % (g('input_shaper', 'shaper_type_x', '?'),
                                n1(g('input_shaper', 'shaper_freq_x', 0)),
                                g('input_shaper', 'shaper_type_y', '?'),
                                n1(g('input_shaper', 'shaper_freq_y', 0))))
    a('Mesh %s (%s)' % (v.get('mesh_last_profile', '?'),
                        str(v.get('mesh_mode', 'ON')).upper()))
    ovs = []
    for key, label in (('ov_pa', 'PA'), ('ov_fan', 'FAN'), ('ov_flow', 'FLOW'),
                       ('ov_accel', 'ACC'), ('ov_bed', 'BED'), ('ov_hotend_first', 'HOT')):
        if str(v.get(key + '_on', 'False')).lower() == 'true':
            ovs.append('%s(%s)' % (label, v.get(key, '?')))
    a('Overwrites: %s' % (' '.join(ovs[:5]) + (' +%d' % (len(ovs) - 5) if len(ovs) > 5 else '')
                          if ovs else 'NONE'))
    a('Nozzle LED %s %s%%' % (str(v.get('nozzle_mode', 'auto')).upper(),
                              pct(v.get('nozzle_bright', 1.0))))
    if not st:
        a('(!) live values offline - static only')
    else:
        a('Print: %s' % g('print_stats', 'state', '?'))
    a('R2 macro system - SHOW STATUS on paper')

    bmin_x, bmin_y = 5.0, 5.0
    bmax_x, bmax_y = 239.0, 233.0

    def _vf(key, dflt):
        try:
            return float(v.get(key, dflt))
        except (TypeError, ValueError):
            return float(dflt)
    bmin_x, bmin_y = _vf('plot_bed_min_x', 5), _vf('plot_bed_min_y', 5)
    bmax_x, bmax_y = _vf('plot_bed_max_x', 239), _vf('plot_bed_max_y', 233)
    page_w = (bmax_x - bmin_x) - 8.0
    page_h = (bmax_y - bmin_y) - 8.0
    size = max(6.0, min(_vf('plot_text_size', 7.0), 20.0))    # R73: >=6mm caps
    font = str(v.get('plot_text_font', 'SMOOTH') or 'SMOOTH').upper()
    if font not in ('SMOOTH', 'MONO', 'COND', 'NARROW', 'CAPS'):
        font = 'SMOOTH'
    cols, size = _fit_text_page(lines, page_w, page_h, size, font)
    extrude = int(_vf('plot_extrude', 0)) == 1
    polys = _text_page_polys(cols, page_w, page_h, size, font,
                             solid=extrude, line_w=0.65)
    polys = [[(px + bmin_x + 4.0, py + bmin_y + 4.0) for (px, py) in pl] for pl in polys]
    out = out or '00_R2_Status_V01.gcode'
    n_lines = sum(len(c) for c in cols)
    notes = ['; status plot: SHOW_STATUS (%d line(s) in %d column(s), %.1fmm caps)'
             % (n_lines, len(cols), size),
             '; generated ' + time.strftime('%Y-%m-%d %H:%M:%S')]
    _plot_write(out, polys, notes, var_path, extrude=extrude)
    return out, n_lines, size


# ======================================================================================
#  R64 BRIDGING TEST - two tall towers on the bed diagonal (not the full diagonal)
#  + ONE shorter bridge underneath at 10..50% of the long span, carried by its
#  own LOWER tower. Both bridges sit on the same diagonal line, the short one
#  clearly below the long one - inspect both from the side, tune speed/fan/flow
#  LIVE via Live Tuning > Features > BRIDGE. Normal start procedure (mesh,
#  purge line, temperatures) because it is a regular R2 print file.
# ======================================================================================

def make_bridge(length=160.0, short_pct=30, h_long=35.0, h_short=18.0, version=1,
                tower=10.0, bridge_layers=1, speed=20.0, fan=255,
                layer_h=0.2, first_h=0.28, material='PLA', bed=None,
                bed_margin=8.0, nozzle=0.6, out_dir='.'):
    """R64: generate the bridging test file. Returns (path, info)."""
    length = float(length)
    short_pct = int(short_pct)
    h_long = float(h_long)
    h_short = float(h_short)
    tower = float(tower)
    bridge_layers = int(bridge_layers)
    speed = float(speed)
    fan = int(fan)
    layer_h = max(0.06, min(float(layer_h), 0.34))
    first_h = max(0.08, min(float(first_h), 0.42))
    if bed is None:
        bed = (0.0, -1.0, 244.0, 238.0)
    bx0, by0, bx1, by1 = bed
    ux0, uy0 = bx0 + bed_margin, by0 + bed_margin
    ux1, uy1 = bx1 - bed_margin, by1 - bed_margin
    uw, uh = ux1 - ux0, uy1 - uy0
    lmax = min(uw - tower, uh - tower) * math.sqrt(2.0)
    if not (40.0 <= length <= 400.0):
        raise ValueError('bridge length must be 40..400mm (got %.0f)' % length)
    if length > lmax:
        raise ValueError('bridge length %.0fmm does not fit the bed diagonal '
                         '(max %.0fmm with %dmm towers + margin)' % (length, lmax, tower))
    if not (10 <= short_pct <= 60):
        raise ValueError('SHORT_PCT must be 10..60%% (got %d)' % short_pct)
    tower = max(6.0, min(tower, 20.0))
    bridge_layers = max(1, min(bridge_layers, 3))
    speed = max(5.0, min(speed, 80.0))
    fan = max(0, min(fan, 255))
    # layer-aligned tower heights
    nl = max(8, int(round((h_long - first_h) / layer_h)) + 1)
    h_long = first_h + (nl - 1) * layer_h
    ns = int(round((h_short - first_h) / layer_h)) + 1
    # the short bridge must hang CLEARLY below the long one (>= 10mm air, so a
    # sagging long bridge can never touch it and both stay inspectable)
    ns = max(6, min(ns, nl - int(math.ceil(10.0 / layer_h))))
    h_short = first_h + (ns - 1) * layer_h

    cx, cy = (ux0 + ux1) / 2.0, (uy0 + uy1) / 2.0
    d = (1.0 / math.sqrt(2.0), 1.0 / math.sqrt(2.0))
    p = (-d[1], d[0])
    A = (cx - d[0] * length / 2.0, cy - d[1] * length / 2.0)
    B = (cx + d[0] * length / 2.0, cy + d[1] * length / 2.0)
    slen = length * short_pct / 100.0
    C = (A[0] + d[0] * slen, A[1] + d[1] * slen)

    wid = max(0.4, nozzle * 1.08)
    twid = max(0.4, nozzle * 1.02)
    fil = FIL_AREA
    total_layers = nl + bridge_layers

    def trect(c):
        return (c[0] - tower / 2.0, c[1] - tower / 2.0, c[0] + tower / 2.0, c[1] + tower / 2.0)

    def tpoly(c):
        x0, y0, x1, y1 = trect(c)
        return '[[%.1f,%.1f],[%.1f,%.1f],[%.1f,%.1f],[%.1f,%.1f]]' % (x0, y0, x1, y0, x1, y1, x0, y1)

    def bpoly(c0, c1):
        pts = [(c0[0] - p[0] * tower / 2.0, c0[1] - p[1] * tower / 2.0),
               (c0[0] + p[0] * tower / 2.0, c0[1] + p[1] * tower / 2.0),
               (c1[0] + p[0] * tower / 2.0, c1[1] + p[1] * tower / 2.0),
               (c1[0] - p[0] * tower / 2.0, c1[1] - p[1] * tower / 2.0)]
        return '[' + ','.join('[%.1f,%.1f]' % (x, y) for x, y in pts) + ']'

    L = []
    a = L.append
    a('; R2-BRIDGE generated bridging test (R64) - start it like any other file')
    a('; long span %.0fmm (tower center to tower center, on the bed diagonal),' % length)
    a('; short span %.0fmm = %d%% of it, %.0fmm BELOW the long one on its own lower tower'
      % (slen, short_pct, h_long - h_short))
    a('; towers %.0fx%.0fmm, long top %.1fmm, short top %.1fmm, %d bridge layer(s)'
      % (tower, tower, h_long, h_short, bridge_layers))
    a('; bridge speed %.0fmm/s, fan %d/255 - tune LIVE: Live Tuning > Features > BRIDGE'
      % (speed, fan))
    a('; filament_type = %s' % material)
    a('; layer_height = %.2g' % layer_h)
    a('; nozzle_diameter = %.1f' % nozzle)
    a('; line_width = %.2g' % wid)
    a('; outer_wall_line_width = %.2g' % wid)
    a('; outer_wall_speed = 40')
    a('; inner_wall_speed = 45')
    a('; internal_solid_infill_speed = 55')
    a('; initial_layer_speed = 25')
    a('; travel_speed = 150')
    a('; wall_loops = 2')
    for name, c in (('TOWER_A', A), ('TOWER_B', B), ('TOWER_C', C)):
        a('EXCLUDE_OBJECT_DEFINE NAME=%s CENTER=%.1f,%.1f POLYGON=%s'
          % (name, c[0], c[1], tpoly(c)))
    a('EXCLUDE_OBJECT_DEFINE NAME=BRIDGE_SHORT CENTER=%.1f,%.1f POLYGON=%s'
      % ((A[0] + C[0]) / 2.0, (A[1] + C[1]) / 2.0, bpoly(A, C)))
    a('EXCLUDE_OBJECT_DEFINE NAME=BRIDGE_LONG CENTER=%.1f,%.1f POLYGON=%s'
      % ((A[0] + B[0]) / 2.0, (A[1] + B[1]) / 2.0, bpoly(A, B)))
    a('PRINT_START MATERIAL=%s LAYER_HEIGHT=%.2g TOTAL_LAYERS=%d OUTER_WALL_SPEED=40'
      % (material, layer_h, total_layers))
    a('G90')
    a('M83')
    a('M107   ; R2-BRIDGE: first layer = fan off')

    pen = _Pen(L, jump_d=6.0)   # R77: no retracts between neighboring hatch lines

    def layer_h_eff(li):
        return first_h if li == 1 else layer_h

    def tower_block(c, name, li):
        x0, y0, x1, y1 = trect(c)
        ix0, iy0 = x0 + wid / 2.0, y0 + wid / 2.0
        ix1, iy1 = x1 - wid / 2.0, y1 - wid / 2.0
        e_wall = layer_h_eff(li) * wid / fil
        L.append('EXCLUDE_OBJECT_START NAME=%s' % name)
        if li == 1:
            L.append(';TYPE:Brim')
            for off in (wid * 0.35, wid * 0.35 + wid):
                b = (x0 - off, y0 - off, x1 + off, y1 + off)
                _emit_loop(pen, _rect_loop(*b), e_wall, 1500)
        L.append(';TYPE:Outer wall')
        _emit_loop(pen, _rect_loop(ix0, iy0, ix1, iy1), e_wall, 1500 if li == 1 else 2400)
        L.append(';TYPE:Inner wall')
        _emit_loop(pen, _rect_loop(ix0 + wid, iy0 + wid, ix1 - wid, iy1 - wid), e_wall,
                   1500 if li == 1 else 2700)
        L.append(';TYPE:Internal solid infill')
        segs = _hatch(ix0 + wid + 0.05, iy0 + wid + 0.05, ix1 - wid - 0.05, iy1 - wid - 0.05,
                      None, wid, 45.0 if li % 2 else 135.0)
        _emit_hatch(pen, segs, e_wall, 1500 if li == 1 else 3300)
        L.append('EXCLUDE_OBJECT_END NAME=%s' % name)

    def deck(c0, c1, name, li, z):
        """one bridge deck layer: strands along the span, ;TYPE:Bridge"""
        e_line = layer_h_eff(min(li, 3)) * twid / fil
        L.append('EXCLUDE_OBJECT_START NAME=%s' % name)
        L.append(';TYPE:Bridge')
        L.append('M106 S%d   ; R2-BRIDGE: bridge fan' % fan)
        s0 = (c0[0] + d[0] * (tower / 2.0 - 0.8), c0[1] + d[1] * (tower / 2.0 - 0.8))
        s1 = (c1[0] - d[0] * (tower / 2.0 - 0.8), c1[1] - d[1] * (tower / 2.0 - 0.8))
        n = max(2, int(tower / wid))
        for i in range(n):
            o = (i - (n - 1) / 2.0) * (tower / n)
            a0 = (s0[0] + p[0] * o, s0[1] + p[1] * o)
            a1 = (s1[0] + p[0] * o, s1[1] + p[1] * o)
            pen.travel(a0[0], a0[1], feed=9000, hop=False)
            pen.extrude(a1[0], a1[1], math.hypot(a1[0] - a0[0], a1[1] - a0[1]) * e_line,
                        int(speed * 60))
        L.append('M106 S178   ; R2-BRIDGE: back to tower fan')
        L.append('EXCLUDE_OBJECT_END NAME=%s' % name)

    for li in range(1, total_layers + 1):
        z = round(first_h + (li - 1) * layer_h, 3)
        L.append(';LAYER_CHANGE')
        L.append(';Z:%.3f' % z)
        pen.set_z(z)
        if li == 2:
            L.append('M106 S178   ; R2-BRIDGE: part fan from layer 2')
        if li == 1:
            L.append('M117 Bridge: towers...')
        if li <= nl:
            tower_block(A, 'TOWER_A', li)
            tower_block(B, 'TOWER_B', li)
        if li <= ns:
            tower_block(C, 'TOWER_C', li)
        ks = li - ns
        if 1 <= ks <= bridge_layers:
            if ks == 1:
                L.append('M117 Bridge: short %.0fmm' % slen)
                L.append('RESPOND MSG="[bridge] SHORT span %.0fmm now - watch the sag, tune speed/fan LIVE"' % slen)
            deck(A, C, 'BRIDGE_SHORT', li, z)
        kl = li - nl
        if 1 <= kl <= bridge_layers:
            if kl == 1:
                L.append('M117 Bridge: long %.0fmm' % length)
                L.append('RESPOND MSG="[bridge] LONG span %.0fmm now - compare against the short one"' % length)
            deck(A, B, 'BRIDGE_LONG', li, z)
    a('M107')
    a('M117 Bridge test done')
    a('RESPOND MSG="[bridge] done - inspect sag + stringing; better bridges: higher speed, more fan, less flow"')
    a('PRINT_END')

    fname = '00_Bridge_%dmm_%dpct_V%02d.gcode' % (round(length), short_pct,
                                               max(1, min(int(version), 99)))
    out = os.path.join(out_dir, fname)
    with open(out, 'w') as f:
        f.write('\n'.join(L) + '\n')
    try:
        process(out)
    except Exception as e:                                  # noqa: BLE001
        print('[bridge] WARNING: post-process failed for %s: %r' % (fname, e), flush=True)
    info = {'file': fname, 'length': round(length, 1), 'short_len': round(slen, 1),
            'short_pct': short_pct, 'h_long': round(h_long, 1), 'h_short': round(h_short, 1),
            'tower': tower, 'layers': total_layers, 'bridge_layers': bridge_layers,
            'speed': speed, 'fan': fan}
    return out, info


def process(path, dry=False, verbose=False):
    """Inject _FILE_INFO + LAYER_MARK. Returns a change summary dict.

    R81 STREAMING: the old version read the WHOLE file into one string plus a
    split line list - the 32MB upload of field log .63 cost ~130MB of Python
    objects on a Pi Zero 2 W and fed the same swap storm that killed the range
    generation. The file is now streamed twice: pass A collects config,
    layer positions (comments / Z-scan), feature stats and the insertion
    points; pass B applies the insertions cell by cell while writing.
    Memory stays O(number of layers + features), output is byte-identical
    (R81 golden test).
    """
    summary = {'file': os.path.basename(path), 'tagged': False, 'marks_added': 0,
               'info_added': False, 'skipped': False, 'by_object': False,
               'layers': 0, 'method': None, 'types': 0, 'upgraded': False, 'upgraded_from': 'v1'}

    # ---- pass A: stream the file once, collect everything the builder needs ----
    head_buf = ''            # first ~2k chars: pen-plotter detection
    old_tags = set()
    has_marks = False
    count_marks = 0
    cfg = {}
    comment_matches = []     # (idx, line) of LAYER_COMMENT hits - kept small
    zs_fall = []             # ;Z: comment values (by-object proof)
    zre = re.compile(r'^\s*;\s*Z\s*:\s*(-?\d*\.?\d+)', re.IGNORECASE)
    first_cmd_idx = None     # first command line - filtered world (upgrade case)
    first_cmd_raw = None     # first command line - unfiltered world
    type_at = {}             # (raw idx, filtered idx) -> canonical feature
    scan = _ZScan()
    # feat_stats machine (R44): runs inline over the stream - filtered lines
    # (old tags / _FILE_INFO / APPLY_TYPE) never match a feature or move, so
    # the running values are identical to the old filtered-list walk.
    feat_stats = {}          # canonical type -> {'f': {mm/s: count}, 'acc': float|None}
    fseg = {}                # F counter of the CURRENT segment
    cur_type = None
    acc_running = None       # last M204 seen anywhere in the file
    f_running = None         # modal F (mm/min) - slicers set it on separate lines
    acc_seg_start = None     # M204 in effect when the current segment began
    seg_acc = None           # own M204 inside the current segment (last one wins)
    fv_re = re.compile(r'F(\d+(?:\.\d+)?)')

    def _close_seg():
        if cur_type is None:
            return
        d = feat_stats.setdefault(cur_type, {'f': {}, 'acc': None})
        for k, v in fseg.items():
            d['f'][k] = d['f'].get(k, 0) + v
        eff = seg_acc if seg_acc is not None else acc_seg_start
        if eff is not None:
            d['acc'] = eff

    i = 0                     # index in the line list (raw world)
    j = 0                     # index in the line list (upgrade-filtered world)
    n_read = 0
    trailing_cell = True      # empty file == text.split gives one '' cell
    with open(path, 'r', errors='replace') as f:
        for raw in f:
            n_read += 1
            trailing_cell = raw.endswith('\n')
            if len(head_buf) <= 2048:
                head_buf += raw
                if 'R2-PLOT' in head_buf[:2048]:
                    # R64: pen-plotter files (R2-PLOT header) never get print tags
                    summary['skipped'] = True
                    return summary
            line = raw[:-1] if trailing_cell else raw
            ls = line.strip()
            if TAG in line:
                summary['skipped'] = True
                return summary
            if ls in OLD_TAGS:
                old_tags.add(ls)
            filterable = (ls in old_tags or ls.startswith('_FILE_INFO')
                          or ls.startswith('APPLY_TYPE'))
            if ls.startswith('LAYER_MARK'):
                has_marks = True
                count_marks += 1
            if first_cmd_idx is None and not filterable and ls and not ls.startswith(';'):
                first_cmd_idx = j
            if first_cmd_raw is None and ls and not ls.startswith(';'):
                first_cmd_raw = i
            # ---- 1) slicer config header (filtered lines never match CFG_RE) ----
            if len(cfg) < len(CFG_KEYS):
                m = CFG_RE.match(line)
                if m and m.group(1) in CFG_KEYS and m.group(1) not in cfg:
                    cfg[m.group(1)] = first_value(m.group(2))
            # ---- 2) layer positions -------------------------------------------------
            # has_marks is only known at EOF - collect BOTH detectors and
            # decide afterwards, exactly like the old two-branch code.
            if LAYER_COMMENT.match(line):
                comment_matches.append((i, j))
            scan.step(i, j, ls)
            m = zre.match(line)
            if m:
                zs_fall.append(float(m.group(1)))
            # ---- 4b) APPLY_TYPE positions (every ;TYPE: comment with a feature) ----
            # both worlds: pass B counts j (upgrade-filtered) when had_v1, else i
            m = TYPE_RE.match(line)
            feat_here = TYPE_MAP.get(m.group(1).strip().lower()) if m else None
            if feat_here:
                type_at[(i, j)] = feat_here
            # ---- 4c) per-feature measurement (.44) -----------------------------------
            if feat_here:
                _close_seg()
                cur_type = feat_here
                fseg = {}
                seg_acc = None
                acc_seg_start = acc_running
            else:
                if ls.startswith('M204'):
                    m = re.search(r'S(\d+(?:\.\d+)?)', ls)
                    if m:
                        acc_running = float(m.group(1))
                        if cur_type is not None:
                            seg_acc = acc_running
                elif ls[:2] in ('G0', 'G1', 'G2', 'G3'):
                    # F is MODAL in g-code: slicers emit it on its own line
                    # ('G1 F3600') and the print moves carry no F at all ->
                    # track one running value.
                    m = fv_re.search(ls)
                    if m:
                        f_running = float(m.group(1))
                    # only real PRINT moves count: X or Y present, extruding
                    # (E >= 0). Pure retract/prime lines (E only) and travels
                    # (no E) are skipped - otherwise the retract speed
                    # outvotes short segments (field test: every feature
                    # measured 35 mm/s = the E-moves' F2100).
                    if cur_type is not None and ls[:2] != 'G0':
                        if (re.search(r' [XY]-?[\d.]', ls) and re.search(r' E[\d.]', ls)
                                and not re.search(r' E-', ls)):
                            spd = round((f_running or 0) / 60.0, 1)
                            if spd > 0:
                                fseg[spd] = fseg.get(spd, 0) + 1
            i += 1
            if not filterable:
                j += 1
    _close_seg()
    had_v1 = bool(old_tags)
    if had_v1:
        # upgrade: old tag line(s) + old _FILE_INFO are dropped and rebuilt in
        # pass B (LAYER_MARK lines stay untouched, APPLY_TYPE is rebuilt too)
        summary['upgraded'] = True
        summary['upgraded_from'] = '/'.join(sorted({tag.split()[-1] for tag in old_tags}))

    # the apply world: the old code walked the FILTERED line list on upgrade
    # (had_v1) and the raw list otherwise - map every collected position into
    # exactly that world (pass B counts the same way)
    def _aw(x):
        return x[1] if had_v1 else x[0]

    comment_layers = 0
    insert_at = []           # ('after'|'before', apply-world idx)
    obj_changes = 0
    if not has_marks:
        comment_layers = len(comment_matches)
        if comment_layers:
            # inject after every layer-change comment
            insert_at = [('after', _aw(p)) for p in comment_matches]
            summary['method'] = 'layer comments'
        else:
            # Z-scan fallback: watch extruding moves (E + X/Y), absolute Z only
            insert_at, obj_changes = scan.result(had_v1)
            summary['by_object'] = obj_changes > 0
            summary['method'] = 'Z scan'
    summary['layers'] = (comment_layers if comment_layers else len(insert_at)) or count_marks

    # by-object from object data: several objects + Z falls are detected in
    # z_scan; ;Z: comments with FALLING values prove by-object printing - this
    # also holds for UPGRADED files (marks already present) and R2-marked files
    if not summary['by_object']:
        falls = sum(1 for a, b in zip(zs_fall, zs_fall[1:]) if b < a - 1.0)
        summary['by_object'] = falls > 0

    # ---- 3) build the _FILE_INFO call ---------------------------------------------
    info = ['_FILE_INFO']
    for key, name in CFG_KEYS.items():
        if key in cfg:
            try:
                val = float(cfg[key])
                if name == 'MATERIAL':
                    info.append(f'MATERIAL={cfg[key].upper()}')
                elif val > 0:
                    info.append(f'{name}={val:g}')
            except ValueError:
                if name == 'MATERIAL':
                    info.append(f'MATERIAL={cfg[key].upper()}')
    if not any(p.startswith('TOTAL_LAYERS=') for p in info):
        total = summary['layers'] or count_marks
        if total:
            info.append(f'TOTAL_LAYERS={total}')
    info.append('BY_OBJECT={}'.format(1 if summary['by_object'] else 0))
    info_line = ' '.join(info)

    # ---- 4) first command line = _FILE_INFO insertion point -------------------------
    first_cmd = first_cmd_idx if had_v1 else first_cmd_raw

    type_at = {_aw(p): feat for p, feat in type_at.items()}   # -> apply world
    summary['types'] = len(type_at)

    # .44: the REAL originals (measured) + which features the file contains
    for canon in feat_stats:
        d = feat_stats[canon]
        suf = canon.replace('-', '_')
        if d['f']:
            best = max(d['f'], key=d['f'].get)
            info.append(f'FS_{suf}={best:g}')
        if d['acc'] is not None:
            info.append(f'FA_{suf}={d["acc"]:g}')
    if feat_stats:
        info.append('TYPES=' + ','.join(feat_stats))
    info_line = ' '.join(info)   # re-join with the measured values

    # ---- 5) apply --------------------------------------------------------------------
    if dry:
        if verbose:
            print(f'[dry] {path}: marks={len(insert_at)} types={len(type_at)} '
                  f'method={summary["method"]} info={" ".join(info)}')
        return summary

    mark_set = {i2 for kind, i2 in insert_at if kind == 'after'}
    before_set = {i2 for kind, i2 in insert_at if kind == 'before'}
    tmp = path + '.r2tmp'
    with open(tmp, 'w') as fo:
        # new_text = TAG + '\n' + '\n'.join(out2): every following CELL is
        # separated by exactly one '\n' - writing each cell with a leading
        # newline (TAG first, without one) reproduces the join byte-exactly,
        # including a trailing '' cell for files that end in '\n'.
        fo.write(TAG)
        j = 0
        shift = 0              # loop-1 inserts already written -> out-index shift

        def _pre(cell):
            # loop-2 inserts BEFORE an out-cell - the old code checked
            # before_set/first_cmd against the INDEX OF EVERY out cell, insert
            # cells included (a ;TYPE: block before the first command shifts
            # first_cmd onto an APPLY_TYPE cell - kept byte-exact)
            if first_cmd is not None:
                if cell in before_set:
                    fo.write('\nLAYER_MARK')
                if cell == first_cmd:
                    fo.write('\n' + info_line)

        with open(path, 'r', errors='replace') as f:
            for raw in f:
                line = raw[:-1] if raw.endswith('\n') else raw
                ls = line.strip()
                if had_v1:
                    # upgrade: drop the old tag line(s) + the old _FILE_INFO call -
                    # both are replaced below. LAYER_MARK lines stay untouched!
                    # (APPLY_TYPE lines from v2 are also rebuilt - TYPE_MAP may
                    # have learned new types.)
                    if (ls in old_tags or ls.startswith('_FILE_INFO')
                            or ls.startswith('APPLY_TYPE')):
                        continue
                o = j + shift
                _pre(o)
                fo.write('\n' + line)
                if j in mark_set:
                    _pre(o + 1)
                    fo.write('\nLAYER_MARK')
                    shift += 1
                if j in type_at:
                    _pre(o + 2 if j in mark_set else o + 1)
                    fo.write(f'\nAPPLY_TYPE TYPE={type_at[j]}')
                    shift += 1
                j += 1
        # text.split('\n') appends a final '' cell when the file ends in '\n'
        # (or is empty) - it becomes the trailing newline of the output
        if trailing_cell:
            fo.write('\n')
        # note: when first_cmd is also in before_set, the mark lands right after info
        if first_cmd is None:
            fo.write('\n' + info_line)
    os.replace(tmp, path)

    summary['tagged'] = True
    summary['marks_added'] = len(insert_at)
    summary['info_added'] = True
    return summary


class _ZScan:
    """R81 streaming core of z_scan: feed .step(index, stripped_line) for every
    line, call .result() at the end - same detection logic as the old
    list-walking z_scan, O(1) state instead of the full line list."""

    def __init__(self):
        self.inserts = []
        self.obj_changes = 0
        self.prev_z = None      # Z of the last EXTRUDING move
        self.acc = 0.0          # vase-mode accumulator
        self.absolute = True

    def step(self, i, j, ls):
        if ls.startswith('G90'):
            self.absolute = True
        elif ls.startswith('G91'):
            self.absolute = False
        elif ls.startswith('M83'):
            pass                      # relative E - irrelevant for Z
        m = MOVE_RE.match(ls)
        if not m:
            return
        p = parse_params(m.group(2))
        if 'Z' not in p:
            return
        z = p['Z']
        extruding = 'E' in p and ('X' in p or 'Y' in p)
        if not extruding or not self.absolute:
            return
        if self.prev_z is None:
            self.prev_z = z
            return
        dz = z - self.prev_z
        if 0.05 < dz <= 0.35:
            self.inserts.append(('before', i, j))
            self.acc = 0.0
        elif 0 < dz <= 0.05:
            self.acc += dz
            if self.acc >= 0.18:
                self.inserts.append(('before', i, j))
                self.acc = 0.0
        elif dz < -1.0 and self.prev_z >= 1.6:
            self.obj_changes += 1
        self.prev_z = z

    def result(self, had_v1=False):
        # map the (raw, filtered) index pairs into the apply world
        ins = [(kind, (j if had_v1 else i)) for kind, i, j in self.inserts]
        return ins, self.obj_changes


def z_scan(lines):
    """Detect layer rises in the Z moves. Returns (insert-before indexes, object changes)."""
    scan = _ZScan()
    for i, l in enumerate(lines):
        scan.step(i, i, l.strip())
    return scan.result()


def count_existing_marks(lines):
    return sum(1 for l in lines if l.strip().startswith('LAYER_MARK'))


def _peek_file_info(path):
    """Read the _FILE_INFO line + heater commands of a gcode file WITHOUT touching it.

    Returns a dict for the LCD 'File preview' (Pre-Print > File) - shown before
    the print even starts (the file itself only reports via _FILE_INFO once it
    RUNS, which is too late to compare against your pre-print settings).
    R74: EVERY key of the _FILE_INFO line is parsed (not just a small subset) -
    the preview push forwards the whole line to Klipper, so speeds/accels/
    feature values show at SELECTION time. '_RAW' carries the line itself,
    'TYPE' the start-mode guess (MARKED/LEGACY/PLOT).
    """
    info = {}
    raw = ''
    try:
        with open(path, 'r', errors='replace') as f:
            head = f.read(400000)          # start block is enough
    except OSError:
        return info
    for l in head.split('\n'):
        ls = l.strip()
        if ls.startswith('_FILE_INFO'):
            raw = ls
            for m in re.finditer(r'([A-Z][A-Z0-9_]+)=([\w.,+-]+)', ls):
                info[m.group(1)] = m.group(2)
            break
    # heater/fan commands from the file's own start block (like a real print would do)
    hot = bed = fan = 0.0
    first_layer = True
    for l in head.split('\n'):
        ls = l.strip()
        if ls.startswith(';LAYER_CHANGE') or ls == 'LAYER_MARK':
            first_layer = False
        m = re.match(r'M(104|109|140|190)\s+S(\d+(?:\.\d+)?)', ls)
        if m:
            v = float(m.group(2))
            if v >= 40:
                if m.group(1) in ('104', '109'):
                    if first_layer and hot == 0:
                        hot = v
                else:
                    if bed == 0:
                        bed = v
        m = re.match(r'M106\s+S(\d+)', ls)
        if m:
            fan = max(fan, int(m.group(1)) * 100 // 255)
    # files sliced with the R2 script heat via PRINT_START parameters instead of M104
    for l in head.split('\n'):
        if l.startswith('PRINT_START'):
            m = re.search(r'BED=([\d.]+)', l)
            if m and bed == 0:
                bed = float(m.group(1))
            m = re.search(r'HOTEND_FIRST=([\d.]+)', l)
            if m and hot == 0:
                hot = float(m.group(1))
            break
    info['HOTEND'] = f'{hot:g}'
    info['BED'] = f'{bed:g}'
    info['FAN'] = f'{fan:g}'
    # R64: pen-plotter files -> the Pre-Print > File menu grows the plotter group
    if 'R2-PLOT' in head:
        info['PLOT'] = '1'
        m = re.search(r'\((\d+) pen\(s\)', head)
        info['PENS'] = m.group(1) if m else '1'
    # R74: start-mode guess for the info menus (display only - the real
    # file_type is set by the start flow when the file actually runs)
    if 'PLOT' not in info:
        if TAG in head or '\nPRINT_START' in head or head.startswith('PRINT_START'):
            info['TYPE'] = 'MARKED'
        else:
            info['TYPE'] = 'LEGACY'
    else:
        info['TYPE'] = 'PLOT'
    info['_RAW'] = raw
    return info


def _peek_objects(path, limit=80, max_bytes=12288):
    """R75: collect the file's EXCLUDE_OBJECT_DEFINE lines for a verbatim replay.

    The R2 start flow HOLDS the file at position 0 and meshes BEFORE the file
    runs - its own object definitions have not executed yet, so KAMP always
    saw 'no objects' and fell back to a FULL-BED mesh. On the field host
    (Pi Zero) those long, fast mesh travels are exactly where 'Timer too
    close' MCU shutdowns happened (field log .58). The watcher replays the
    defines right after selection: Klipper then knows the object bounds at
    mesh time and KAMP meshes only the print area. Klipper clears the object
    list on every file OPEN (virtual_sdcard:reset_file), so stale objects
    from a previous selection cannot leak into the next mesh.
    """
    defs = []
    total = 0
    try:
        with open(path, 'r', errors='replace') as f:
            head = f.read(400000)
    except OSError:
        return defs
    for l in head.split('\n'):
        ls = l.strip()
        if ls.startswith('EXCLUDE_OBJECT_DEFINE'):
            defs.append(ls)
            total += len(ls) + 1
            if len(defs) >= limit or total >= max_bytes:
                break
    return defs


def _sv_line(var, val):
    """R69: build a SAVE_VARIABLE line that survives Klipper's parser.

    Klipper cuts every command line at ';' and parses SAVE_VARIABLE with
    POSIX shlex (quotes are STRIPPED) + ast.literal_eval, catching ONLY
    ValueError - a malformed string (space, apostrophe, empty, pipes)
    raises SyntaxError = 'Internal error on command' = PRINTER SHUTDOWN.
    Strings therefore go out in the escaped form (a double quote, then an
    escaped double quote, content, escaped double quote, double quote):
    shlex keeps the escaped quotes, literal_eval sees a valid string
    literal. quote/backslash/semicolon are stripped from the content so a
    push can never take the printer down. Numbers/bools go out plain.
    """
    if isinstance(val, str):
        for _bad in ('"', '\\', ';'):
            val = val.replace(_bad, '')
        return 'SAVE_VARIABLE VARIABLE=%s VALUE="\\"%s\\""' % (var, val)
    return 'SAVE_VARIABLE VARIABLE=%s VALUE=%r' % (var, val)


def _moonraker_gcode(script, host='127.0.0.1', port=7125):
    """Send a g-code script to Klipper via moonraker's local HTTP API (best effort)."""
    import urllib.request
    body = json.dumps({'script': script}).encode()
    req = urllib.request.Request(f'http://{host}:{port}/printer/gcode/script',
                                 data=body, headers={'Content-Type': 'application/json'})
    with urllib.request.urlopen(req, timeout=3) as r:
        return r.status == 200


def _preview_script(ppath):
    """R74/R75: the moonraker script that makes the LCD show THIS file the moment
    it is selected - not the values of the last print (the .57 field log:
    'always the same file info, as if stored as a preset').

    R75 (field log .58 - MCU 'Timer too close' shutdowns on a Pi Zero host):
    the push used to be ~21 SAVE_VARIABLE commands = ~21 variables.cfg
    rewrites, fired by the watcher right when homing/meshing starts. Now it
    is ONE _PREVIEW_SET command (in-memory SET_GCODE_VARIABLE - zero disk
    writes while the machine moves), plus:
    2. the file's OWN _FILE_INFO line - the same call the file runs at its
       start, so _STATE.file_* (Start > File info, Pre-Print, Live > File)
       hold the selected file's real slicer values BEFORE the print starts
    3. _PREVIEW_TEMPS - heater/fan values peeked from the start block
    4. the file's EXCLUDE_OBJECT_DEFINE lines - so the mesh BEFORE the held
       file runs is adaptive (object area) instead of full-bed
    (2)/(3)/(4) are SKIPPED while a print is actually running - they would
    overwrite the running file's live values.
    """
    pv = _peek_file_info(ppath)
    raw = pv.pop('_RAW', '')
    busy = False
    excl_ok = False
    try:
        st = _moonraker_status()
        pstate = (st.get('print_stats') or {}).get('state', '')
        r2mode = (st.get('gcode_macro _STATE') or {}).get('mode', '')
        busy = pstate in ('printing', 'paused') and r2mode not in ('waiting', 'idle', 'finished')
        excl_ok = 'exclude_object' in st
    except Exception:                                     # noqa: BLE001
        busy = False          # status unknown - push anyway (best effort)

    def esc(s):
        # quotes/backslash/semicolon/apostrophe can never take the parser down
        for _bad in ('"', '\\', ';', "'"):
            s = str(s).replace(_bad, '')
        return s

    # ONE line, all values - quoted so filenames with spaces survive shlex
    args = ['NAME="%s"' % esc(os.path.basename(ppath))]
    for k, v in pv.items():
        args.append('%s=%s' % (k, esc(v)))
    lines = ['_PREVIEW_SET ' + ' '.join(args)]
    if not busy:
        if excl_ok:
            lines += _peek_objects(ppath)
        if raw:
            lines.append(raw)
        if pv.get('HOTEND', '0') != '0' or pv.get('BED', '0') != '0' or pv.get('FAN', '0') != '0':
            lines.append('_PREVIEW_TEMPS HOTEND=%s BED=%s FAN=%s'
                         % (pv.get('HOTEND', '0'), pv.get('BED', '0'), pv.get('FAN', '0')))
        # R79: range excerpts get the mode hint right at selection (field log
        # .62: 'how am I supposed to print range files - legacy or as sliced?')
        try:
            with open(ppath, 'r', errors='replace') as _fh79:
                if 'R2-RANGE excerpt' in _fh79.read(4096):
                    lines.append('RESPOND MSG="[i] RANGE excerpt: AS LEGACY = your settings + mesh '
                                 '+ purge (recommended) | AS SLICED = 1:1 with the source values"')
        except OSError:
            pass
    return lines, len(pv) + 1


def watch(directory, interval=5.0, once=False):
    """Daemon: process every new/changed .gcode file under DIRECTORY.

    once=True (r2_postproc.py --watch DIR --once): process everything that is
    there RIGHT NOW, print a summary and exit - handy for catch-up runs and
    for testing.
    """
    directory = os.path.abspath(directory)
    if not os.path.isdir(directory):
        # R57: a wrong path used to idle SILENTLY forever ("active" but nothing
        # happens). Fail loudly instead - systemd shows the service as failed.
        print(f'[ERROR] watch directory not found: {directory}', flush=True)
        print('        expected: moonraker gcodes root, usually /home/pi/printer_data/gcodes', flush=True)
        print('        check the ExecStart path in r2-postproc.service!', flush=True)
        sys.exit(1)
    mode = 'one-shot' if once else f'watching, every {interval:g}s'
    print(f'R2 post-processor {mode}: {directory}', flush=True)
    seen = {}
    stats = {'processed': 0, 'tagged_before': 0, 'errors': 0, 'files': 0}
    last_beat = time.time()
    NEW_PREVIEW = []          # R73: freshly processed files -> LCD preview push

    def push_preview(ppath, label='upload'):
        """R73/R74: read the file's parameters and push them to Klipper so
        Pre-Print > File (and the plotter group for plot files) shows them
        BEFORE the print - the old preview only fired on an LCD-started
        SDCARD_PRINT_FILE, Mainsail starts never pushed anything.
        R74: the push now ALSO replays the file's _FILE_INFO line, so the
        Start > File info / Pre-Print / Live menus show THIS file's values."""
        try:
            script_lines, nvals = _preview_script(ppath)
            ok = _moonraker_gcode('\n'.join(script_lines))
            print(f'[preview:{label}] {os.path.basename(ppath)}: '
                  f'{nvals} values pushed' + ('' if ok else ' (moonraker unreachable)'),
                  flush=True)
        except Exception as e:                              # noqa: BLE001
            print(f'[preview:{label}] {ppath}: {e!r}', flush=True)

    def data_head_if_text(p):
        try:
            with open(p, 'rb') as f:
                return f.read(2048)
        except OSError:
            return b''

    def scan():
        for root, dirs, files in os.walk(directory):
            dirs[:] = [d for d in dirs if not d.startswith('.')]
            for fn in sorted(files):
                # R73: plotter sources (.png/.jpg/.svg/.pdf/.txt, with or
                # without a .gcode tail) are scanned too
                if not (fn.lower().endswith(('.gcode', '.gco', '.g'))
                        or PLOT_PAT.search(fn)):
                    continue
                stats['files'] += 1
                p = os.path.join(root, fn)
                try:
                    st = os.stat(p)
                except OSError as e:
                    print(f'[!] {fn}: {e}', flush=True)
                    continue
                key = (st.st_mtime_ns, st.st_size)
                if seen.get(p) == key:
                    continue
                # Settle check: a file written moments ago may still be uploading.
                # R57 FIX: a NEGATIVE age (mtime in the future - Pi clock not yet
                # NTP-synced after boot!) must never skip a file FOREVER ->
                # only skip files that are 0..6 s old.
                if not once and 0 < time.time() - st.st_mtime < 6:
                    continue          # still settling - do NOT mark as seen, the
                                     # next scan picks it up
                seen[p] = key
                # R61 plotter: image smuggled in as *.png.gcode / *.svg.gcode
                # R64: + plain text files (*.txt.gcode) drawn with the stroke fonts
                if PLOT_PAT.search(fn):
                    with open(p, 'rb') as f2:
                        head = f2.read(16)
                    is_img = (head[:4] == b'\x89PNG'          # PNG
                              or head[:3] == b'\xff\xd8\xff'    # JPEG
                              or head[:4] == b'%PDF'            # PDF
                              or b'<svg' in data_head_if_text(p))
                    # R73: a plain 'photo.png' / 'notes.txt' (no .gcode tail)
                    # converts INTO '<name>.png.gcode' - the original stays
                    plain_upload = not fn.lower().endswith('.gcode')
                    already = b'R2-PLOT' in head or b'R2-PLOT' in data_head_if_text(p)
                    if already:
                        stats['tagged_before'] += 1   # converted earlier (R2-PLOT header)
                        continue
                    if is_img:
                        try:
                            out_p = p + '.gcode' if plain_upload else p
                            npens, nlines = plot_convert(p, var_path=VAR_PATH, out=out_p)
                            stats['processed'] += 1
                            NEW_PREVIEW.append(out_p)
                            print(f'[plot] {fn}: converted to pen-plotter g-code '
                                  f'({npens} pen(s), {nlines} lines)'
                                  + (f' -> {os.path.basename(out_p)}' if plain_upload else ''),
                                  flush=True)
                        except Exception as e:              # noqa: BLE001
                            stats['errors'] += 1
                            print(f'[plot] {fn}: {e!r}', flush=True)
                    elif fn.lower().endswith(('.txt.gcode', '.txt')):
                        try:                                  # R64 text plot
                            out_t, nlines, size = text_convert(p, var_path=VAR_PATH)
                            stats['processed'] += 1
                            NEW_PREVIEW.append(out_t)
                            print(f'[plot] {fn}: text -> pen-plotter g-code '
                                  f'({nlines} line(s), {size:g}mm caps)', flush=True)
                        except Exception as e:              # noqa: BLE001
                            stats['errors'] += 1
                            print(f'[plot] {fn}: {e!r}', flush=True)
                    else:
                        stats['tagged_before'] += 1   # already converted (R2-PLOT header)
                    continue
                # R64: generated plotter files without .png/... endings
                # (Resonance_*_plot.gcode, 00_R2_Status_V01.gcode) carry the R2-PLOT header
                if b'R2-PLOT' in data_head_if_text(p):
                    stats['tagged_before'] += 1
                    continue
                try:
                    s = process(p)
                except Exception as e:              # noqa: BLE001
                    stats['errors'] += 1
                    print(f'[!] {fn}: {e!r}', flush=True)
                    continue
                if s['skipped']:
                    stats['tagged_before'] += 1
                else:
                    stats['processed'] += 1
                    NEW_PREVIEW.append(p)
                    print(f'[ok] {fn}: +{s["marks_added"]} LAYER_MARK ({s["method"]}), '
                          f'+{s["types"]} APPLY_TYPE, _FILE_INFO layers={s["layers"]}, '
                          f'by_object={s["by_object"]}'
                          + (' [upgraded from ' + s['upgraded_from'] + ']' if s['upgraded'] else ''), flush=True)

    # R61: plotter settings + layer-range requests live in the save_variables file
    global VAR_PATH
    VAR_PATH = os.path.join(os.path.dirname(os.path.abspath(directory).rstrip('/')), 'variables.cfg')
    # R75: the watcher shares the CPU (and the SD card) with klippy - on weak
    # hosts (Pi Zero class) heavy jobs (label/plot generation) must never
    # steal cycles from motion processing. nice(4) keeps klippy the scheduler's
    # clear favorite; the effect is zero on healthy multi-core hosts.
    try:
        os.nice(4)
    except OSError:
        pass
    last_nonce = None
    last_preview_nonce = None
    last_label_nonce = None
    last_fit_nonce = None
    last_reso_nonce = None
    last_bridge_nonce = None
    last_plottext_nonce = None
    last_plotstatus_nonce = None
    last_host_nonce = None
    first = True
    first_prime = True
    while True:
        stats['files'] = 0
        del NEW_PREVIEW[:]
        # R61: layer-range excerpt request from the LCD (nonce changes on every request)
        try:
            rv = _read_vars(VAR_PATH)
            if first_prime:
                # R75 FIX (field log .58): after a watcher (re)start every
                # stored nonce looked 'new' and re-fired ALL jobs at once -
                # the .58 update restarted the service and label gen + reso +
                # bridge + status plot all ran in one burst right at boot.
                # The first pass only ADOPTS the current counters.
                _np = _prime_nonces(rv)
                last_preview_nonce = _np['preview_nonce']
                last_nonce = _np['range_nonce']
                last_label_nonce = _np['label_gen_nonce']
                last_fit_nonce = _np.get('label_fit_nonce')
                last_reso_nonce = _np['reso_nonce']
                last_bridge_nonce = _np['bridge_nonce']
                last_plottext_nonce = _np['plot_text_nonce']
                last_plotstatus_nonce = _np['plot_status_nonce']
                last_host_nonce = _np['host_nonce']
                first_prime = False
            # R62: file preview request - SDCARD_PRINT_FILE stored the selected
            # name; we read the file's parameters NOW and push them to Klipper
            # via moonraker so Pre-Print > File shows them BEFORE the print.
            pn = rv.get('preview_nonce', '')
            if pn and pn != last_preview_nonce:
                last_preview_nonce = pn
                pfn = rv.get('preview_file', '')
                ppath = os.path.join(directory, pfn.strip())
                if pfn and os.path.isfile(ppath):
                    try:
                        script_lines, nvals = _preview_script(ppath)
                        try:
                            ok = _moonraker_gcode('\n'.join(script_lines))
                            print(f'[preview] {pfn}: {nvals} values pushed to Klipper'
                                  + ('' if ok else ' (moonraker unreachable - values not visible in the LCD)'), flush=True)
                        except Exception as pe:            # noqa: BLE001
                            print(f'[preview] {pfn}: {nvals} values read, but moonraker is unreachable '
                                  f'({pe.__class__.__name__}) - the LCD shows them from the print start instead', flush=True)
                    except Exception as e:              # noqa: BLE001
                        print(f'[preview] {pfn}: {e!r}', flush=True)
            nonce = rv.get('range_nonce', '')
            if nonce and nonce != last_nonce:
                last_nonce = nonce
                rsrc, rs, re_ = rv.get('range_src', ''), rv.get('range_start', ''), rv.get('range_end', '')
                rflo = rv.get('range_floor', '0') or '0'
                rtop = rv.get('range_top', '0') or '0'
                rbrim = rv.get('range_brim', '0') or '0'
                # R74: floor/top shape (0 = footprint/hull, 1 = true outline)
                # and fill (0 = grid hatch, 1 = solid) from the LCD Range menu
                def _rng_flag(key, dflt):
                    v = rv.get(key, dflt)
                    return str(dflt if v is None or str(v).strip() == '' else v).strip().lower() \
                        in ('1', 'true', 'on', 'yes')
                rfs = 'outline' if _rng_flag('range_floor_shape', '0') else 'hull'
                rff = 'solid' if _rng_flag('range_floor_fill', '0') else 'grid'
                rts = 'outline' if _rng_flag('range_top_shape', '0') else 'hull'
                rtf = 'solid' if _rng_flag('range_top_fill', '1') else 'grid'
                src_path = os.path.join(directory, rsrc.strip())
                if rsrc and os.path.isfile(src_path):
                    try:
                        # skip if the excerpt already exists and is NEWER than the source
                        # (a --once catch-up must not rebuild an up-to-date excerpt)
                        _stem62, _ext62 = os.path.splitext(src_path)
                        _src3_62 = re.sub(r'[^A-Za-z0-9]', '',
                                          os.path.basename(_stem62))[:3] or 'RNG'
                        try:
                            _gv62 = max(1, min(int(float(rv.get('gen_version', 1) or 1)), 99))
                        except (TypeError, ValueError):
                            _gv62 = 1
                        _guess62 = os.path.join(
                            os.path.dirname(_stem62) or '.',
                            f'00_{_src3_62}_L{int(float(rs))}-{int(float(re_))}'
                            f'_V{_gv62:02d}{_ext62 or ".gcode"}')
                        if os.path.isfile(_guess62) and os.path.getmtime(_guess62) > os.path.getmtime(src_path):
                            print(f'[range] {os.path.basename(_guess62)}: already up to date - skipped', flush=True)
                        else:
                            out, nl = make_range(src_path, int(float(rs)), int(float(re_)),
                                                 floor=int(float(rflo)), top=int(float(rtop)),
                                                 brim=int(float(rbrim)),
                                                 floor_shape=rfs, floor_fill=rff,
                                                 top_shape=rts, top_fill=rtf,
                                                 version=_gv62)
                            print(f'[range] {os.path.basename(out)}: layers {rs}..{re_} ({nl} layers, '
                                  f'floor {rflo} {rfs}/{rff}, top {rtop} {rts}/{rtf}, '
                                  f'brim {rbrim})', flush=True)
                            # R79: the generated excerpt REPLACES the pending
                            # selection (field log .62: confirming the dialog
                            # after generating printed the SOURCE file). The
                            # macro releases the old selection (nothing is
                            # deleted) and holds the new file for the decision.
                            try:
                                _rel79 = os.path.relpath(out, directory)
                                _moonraker_gcode(
                                    'RESPOND MSG="[OK] Range ready: %s - selected for printing '
                                    '(the source selection is released)"\n'
                                    '_SELECT_FILE FILE="%s"'
                                    % (os.path.basename(out), _rel79))
                            except Exception as se79:              # noqa: BLE001
                                print(f'[range] select-swap unreachable: {se79.__class__.__name__}', flush=True)
                    except Exception as e:              # noqa: BLE001
                        print(f'[range] {rsrc}: {e!r}', flush=True)
                else:
                    print(f'[range] source file not found: {rsrc!r}', flush=True)
        except Exception as e:                          # noqa: BLE001
            print(f'[range] poll error: {e!r}', flush=True)

        # R83: fit preview request (Labels > Settings > 'Fit?' bumps
        # label_fit_nonce) - answers with the REAL numbers the generator
        # will print, using the same fonts + grow math (no file written)
        try:
            fnc = rv.get('label_fit_nonce', '')
            if fnc and fnc != last_fit_nonce:
                last_fit_nonce = fnc
                texts_f = [t for t in (x.strip() for x
                                       in str(rv.get('label_texts', '')).split('|')) if t]
                if not texts_f:
                    raise ValueError('type a text first (Labels > Text)')
                cfg_bed_f = _bed_limits(os.path.join(
                    os.path.dirname(os.path.abspath(directory).rstrip('/')),
                    'config', 'printer.cfg'))

                def _vf_f(key, dflt):
                    try:
                        return float(rv.get(key, dflt) or dflt)
                    except (TypeError, ValueError):
                        return float(dflt)

                def _vb_f(key, dflt):
                    return str(rv.get(key, dflt)).strip().lower()                         in ('true', '1', 'on', 'yes')

                pv = label_preview(
                    texts_f,
                    w=_vf_f('label_w', 60), h=_vf_f('label_h', 30),
                    font=str(rv.get('label_font', 'SMOOTH') or 'SMOOTH'),
                    layer_h=_vf_f('label_layer_h', 0.2),
                    stroke=_vf_f('label_stroke', 0),
                    font_size=_vf_f('label_size', 0),
                    spacing=_vf_f('label_spacing', 0),
                    hole_side=int(_vf_f('label_hole_side', 0)),
                    hole_d=_vf_f('label_hole_d', 5),
                    gap=_vf_f('label_gap', 6),
                    color2=_vb_f('label_color2', True),
                    bed=cfg_bed_f)
                short_f = '%.0fx%.0f%s %.1f' % (
                    pv['w'], pv['h'], '+' if pv['grown'] else '', pv['cap_mm'])
                msg_f = ('Label preview: %s on %.0fx%.0fmm -> %s%.0fx%.0fmm, '
                         'font %.1fmm caps, stroke %.1fmm%s, ~%d chars/line'
                         % (texts_f[0][:20], _vf_f('label_w', 60), _vf_f('label_h', 30),
                            'GROWN ' if pv['grown'] else '', pv['w'], pv['h'],
                            pv['cap_mm'], pv['stroke_eff'],
                            ' (capped)' if (pv['stroke_eff'] < _vf_f('label_stroke', 0) - 0.01
                                            and _vf_f('label_stroke', 0) > 0) else '',
                            pv['chars_fit']))
                extra_f = []
                if pv['cap_capped']:
                    extra_f.append(
                        'Label preview: size %.1fmm caps needs a bigger label - '
                        'it prints at %.1fmm instead (grow limit reached)'
                        % (pv['target_mm'], pv['cap_mm']))
                if pv['min_w']:
                    extra_f.append(
                        'Label preview: for %.1fmm caps make the label >= %.0fx%.0fmm '
                        '(or leave Size auto - the font then fills it)'
                        % (pv['target_mm'], pv['min_w'], pv['min_h'] or pv['h']))
                for w_f in pv['warns']:
                    extra_f.append('Label preview: %s' % w_f)
                _moonraker_gcode(
                    _sv_line('label_fit', short_f) + '\n'
                    + 'RESPOND MSG="%s"\n' % msg_f
                    + ''.join('RESPOND MSG="%s"\n' % x for x in extra_f)
                    + 'M117 %s' % short_f)
                print(f'[fit] {texts_f[0][:20]}: {msg_f}', flush=True)
        except Exception as e:              # noqa: BLE001
            print(f'[fit] error: {e}', flush=True)
            try:
                _moonraker_gcode(
                    'RESPOND MSG="Label preview ERROR: %s"\nM117 Fit error\n'
                    '_SOUND_LIB NAME=r2_error' % e)
            except Exception:               # noqa: BLE001
                pass

        # R63: label generator request from the LCD (label_gen_nonce bumps per job)
        try:
            ln = rv.get('label_gen_nonce', '')
            if ln and ln != last_label_nonce:
                last_label_nonce = ln
                try:
                    texts = [t for t in (x.strip() for x
                                         in str(rv.get('label_texts', '')).split('|')) if t]
                    if not texts:
                        raise ValueError('no label text set - add one first (LCD: Labels > Text)')
                    cfg_bed = _bed_limits(os.path.join(
                        os.path.dirname(os.path.abspath(directory).rstrip('/')),
                        'config', 'printer.cfg'))

                    def _vb(key, dflt):
                        v = str(rv.get(key, dflt)).strip().lower()
                        if v == '':
                            return dflt
                        return v in ('true', '1', 'on', 'yes')

                    def _vf(key, dflt):
                        try:
                            return float(rv.get(key, dflt) or dflt)
                        except (TypeError, ValueError):
                            return float(dflt)

                    out_l, info_l = make_labels(
                        texts,
                        w=_vf('label_w', 60), h=_vf('label_h', 30),
                        font=str(rv.get('label_font', 'SMOOTH') or 'SMOOTH'),
                        base_layers=int(_vf('label_base_layers', 4)),
                        text_layers=int(_vf('label_text_layers', 2)),
                        layer_h=_vf('label_layer_h', 0.2),
                        first_h=_vf('label_first_h', 0.28),
                        stroke=_vf('label_stroke', 0),
                        font_size=_vf('label_size', 0),
                        spacing=_vf('label_spacing', 0),
                        ironing=_vb('label_ironing', True),
                        hole_side=int(_vf('label_hole_side', 0)),
                        hole_d=_vf('label_hole_d', 5),
                        brim=_vb('label_brim', True),
                        gap=_vf('label_gap', 6),
                        color2=_vb('label_color2', True),
                        material=str(rv.get('material', 'PLA') or 'PLA'),
                        bed=cfg_bed, out_dir=directory,
                        version=max(1, min(int(_vf('gen_version', 1)), 99)))
                    fitmsg = '%d fit (%dx%d), using %d' % (
                        info_l['fit'], info_l['cols'], info_l['rows'], info_l['count'])
                    try:
                        _lab_rel79 = os.path.relpath(
                            os.path.join(directory, info_l['file']), directory)
                        # R80: report the FINAL size (auto-grown?) + font -
                        # everything the user needs, no console digging
                        _sz79 = '%.0fx%.0fmm%s' % (
                            info_l['w'], info_l['h'],
                            ' (grown)' if info_l.get('grown') else '')
                        _moonraker_gcode(
                            _sv_line('label_fit', fitmsg) + '\n'
                            'RESPOND MSG="Labels: %s - %d label(s), %s, font %.1fmm caps, '
                            'stroke %.1fmm%s, %d layers, tower %s - selected for printing"'
                            '\nM117 Labels ready\n'
                            '_SOUND_LIB NAME=r2_done\n'
                            '_SELECT_FILE FILE="%s"'
                            % (info_l['file'], info_l['count'], _sz79, info_l['cap_mm'],
                               info_l.get('stroke_eff', 0.0),
                               ' (capped)' if info_l.get('stroke_capped') else '',
                               info_l['layers'], 'on' if info_l['tower'] else 'off',
                               _lab_rel79))
                    except Exception as me:                  # noqa: BLE001
                        print(f'[labels] moonraker unreachable ({me.__class__.__name__})',
                              flush=True)
                    print(f'[labels] {info_l["file"]}: {info_l["count"]} label(s), '
                          f'{info_l["cols"]}x{info_l["rows"]} grid ({fitmsg}), '
                          f'{info_l["layers"]} layers, tower '
                          f'{"on" if info_l["tower"] else "off"}', flush=True)
                except Exception as e:                      # noqa: BLE001
                    print(f'[labels] error: {e}', flush=True)
                    try:
                        _moonraker_gcode(
                            'RESPOND MSG="Labels ERROR: %s"\nM117 Label error\n'
                            '_SOUND_LIB NAME=r2_error' % e)
                    except Exception:                       # noqa: BLE001
                        pass
        except Exception as e:                          # noqa: BLE001
            print(f'[labels] poll error: {e!r}', flush=True)
        # R64: resonance diagram request (reso_nonce bumps per job)
        try:
            rsn = rv.get('reso_nonce', '')
            if rsn and rsn != last_reso_nonce:
                last_reso_nonce = rsn
                try:
                    base_r64 = os.path.dirname(os.path.abspath(directory).rstrip('/'))
                    cfg_bed = _bed_limits(os.path.join(base_r64, 'config', 'printer.cfg'))
                    csv_dirs = _resonance_csv_dirs(base_r64)
                    scv = float(_cfg_val(os.path.join(base_r64, 'config', 'printer.cfg'),
                                         'printer', 'square_corner_velocity', '5') or 5)
                    want = str(rv.get('reso_axis', 'BOTH') or 'BOTH').upper()
                    want = ['x', 'y'] if want == 'BOTH' else [want.lower()]
                    have = [ax for ax in want if _find_resonance_csv(ax, csv_dirs)]
                    missing = [ax.upper() for ax in want if ax not in have]
                    if not have:
                        raise ValueError('no resonance CSVs found (looked in %s) - run '
                                         'CALIBRATE_SHAPER or DUMP_RESONANCES first'
                                         % ', '.join(csv_dirs))
                    mode_r = str(rv.get('reso_mode', 'print') or 'print').lower()
                    files_r, info_r = make_resonance(
                        axes=have, mode=mode_r, out_dir=directory, bed=cfg_bed,
                        material=str(rv.get('material', 'PLA') or 'PLA'),
                        var_path=VAR_PATH, csv_dirs=csv_dirs, scv=scv)
                    script_r = []
                    for ax in have:
                        for nm, fr, _v, _s in info_r['axes'][ax]['table']:
                            script_r.append('SAVE_VARIABLE VARIABLE=shaper_rec_%s_%s VALUE=%.1f' % (ax, nm, fr))
                        script_r.append(_sv_line('shaper_best_' + ax, info_r['axes'][ax]['best_txt']))
                    summ = ', '.join('%s %s' % (ax.upper(), info_r['axes'][ax]['best_txt']) for ax in have)
                    script_r.append('RESPOND MSG="Resonance diagram: %s (%s) - %s%s - '
                                    '%s it, then Vibration Cal > Apply"'
                                    % (info_r['file'], 'pen plot' if mode_r == 'plot' else 'print',
                                       summ, (' | no CSV for ' + '/'.join(missing)) if missing else '',
                                       'plot' if mode_r == 'plot' else 'print'))
                    script_r.append('M117 Resonance ready')
                    script_r.append('_SOUND_LIB NAME=r2_done')
                    try:
                        _moonraker_gcode('\n'.join(script_r))
                    except Exception as me:                  # noqa: BLE001
                        print(f'[reso] moonraker unreachable ({me.__class__.__name__})', flush=True)
                    print(f'[reso] {info_r["file"]}: {summ}'
                          + (f' (no CSV for {"/".join(missing)})' if missing else ''), flush=True)
                except Exception as e:                      # noqa: BLE001
                    print(f'[reso] error: {e}', flush=True)
                    try:
                        _moonraker_gcode(
                            'RESPOND MSG="Resonance ERROR: %s"\nM117 Reso error\n'
                            '_SOUND_LIB NAME=r2_error' % e)
                    except Exception:                       # noqa: BLE001
                        pass
        except Exception as e:                          # noqa: BLE001
            print(f'[reso] poll error: {e!r}', flush=True)
        # R64: bridging test request (bridge_nonce)
        try:
            brn = rv.get('bridge_nonce', '')
            if brn and brn != last_bridge_nonce:
                last_bridge_nonce = brn
                try:
                    cfg_bed = _bed_limits(os.path.join(
                        os.path.dirname(os.path.abspath(directory).rstrip('/')),
                        'config', 'printer.cfg'))

                    def _vf64(key, dflt):
                        try:
                            return float(rv.get(key, dflt) or dflt)
                        except (TypeError, ValueError):
                            return float(dflt)

                    out_b, info_b = make_bridge(
                        length=_vf64('bridge_len', 160),
                        short_pct=int(_vf64('bridge_pct', 30)),
                        h_long=_vf64('bridge_h_long', 35),
                        h_short=_vf64('bridge_h_short', 18),
                        tower=_vf64('bridge_tower', 10),
                        bridge_layers=int(_vf64('bridge_layers', 1)),
                        speed=_vf64('bridge_speed', 20),
                        fan=int(_vf64('bridge_fan', 255)),
                        layer_h=_vf64('bridge_layer_h', 0.2),
                        first_h=_vf64('bridge_first_h', 0.28),
                        material=str(rv.get('material', 'PLA') or 'PLA'),
                        bed=cfg_bed, out_dir=directory)
                    try:
                        _moonraker_gcode(
                            'RESPOND MSG="Bridging test: %s - long %.0fmm, short %.0fmm '
                            '(%d%%) %.0fmm lower - start it like any file"\n'
                            'M117 Bridge ready\n_SOUND_LIB NAME=r2_done'
                            % (info_b['file'], info_b['length'], info_b['short_len'],
                               info_b['short_pct'], info_b['h_long'] - info_b['h_short']))
                    except Exception as me:                  # noqa: BLE001
                        print(f'[bridge] moonraker unreachable ({me.__class__.__name__})', flush=True)
                    print(f'[bridge] {info_b["file"]}: long {info_b["length"]}mm, short '
                          f'{info_b["short_len"]}mm ({info_b["short_pct"]}%), '
                          f'{info_b["layers"]} layers', flush=True)
                except Exception as e:                      # noqa: BLE001
                    print(f'[bridge] error: {e}', flush=True)
                    try:
                        _moonraker_gcode(
                            'RESPOND MSG="Bridge ERROR: %s"\nM117 Bridge error\n'
                            '_SOUND_LIB NAME=r2_error' % e)
                    except Exception:                       # noqa: BLE001
                        pass
        except Exception as e:                          # noqa: BLE001
            print(f'[bridge] poll error: {e!r}', flush=True)
        # R64: plot a text file (plot_text_nonce, set by PLOT_TEXT)
        try:
            ptn = rv.get('plot_text_nonce', '')
            if ptn and ptn != last_plottext_nonce:
                last_plottext_nonce = ptn
                try:
                    src_name = str(rv.get('plot_text_file', '') or '').strip().lstrip('/')
                    if not src_name:
                        raise ValueError('no file set - PLOT_TEXT FILE=name.txt first')
                    src = os.path.join(directory, src_name)
                    if not os.path.isfile(src):
                        alt = src + '.gcode' if not src.endswith('.gcode') else src
                        if os.path.isfile(alt):
                            src = alt
                    if not os.path.isfile(src):
                        raise ValueError('file %r not found in the gcodes folder' % src_name)
                    out_t, nlines, size = text_convert(
                        src, out=(src if src.endswith('.gcode') else src + '.gcode'),
                        var_path=VAR_PATH)
                    try:
                        _moonraker_gcode(
                            'RESPOND MSG="Text plot: %s - %d line(s), %.1fmm letters, one page - '
                            'start it (pen mode)"\nM117 Text ready\n_SOUND_LIB NAME=r2_done'
                            % (os.path.basename(out_t), nlines, size))
                    except Exception as me:                  # noqa: BLE001
                        print(f'[plottext] moonraker unreachable ({me.__class__.__name__})', flush=True)
                    print(f'[plottext] {os.path.basename(out_t)}: {nlines} line(s) at {size:g}mm', flush=True)
                except Exception as e:                      # noqa: BLE001
                    print(f'[plottext] error: {e}', flush=True)
                    try:
                        _moonraker_gcode(
                            'RESPOND MSG="Text plot ERROR: %s"\nM117 Text error\n'
                            '_SOUND_LIB NAME=r2_error' % e)
                    except Exception:                       # noqa: BLE001
                        pass
        except Exception as e:                          # noqa: BLE001
            print(f'[plottext] poll error: {e!r}', flush=True)
        # R64: plot the SHOW_STATUS report (plot_status_nonce, set by PLOT_STATUS)
        try:
            psn = rv.get('plot_status_nonce', '')
            if psn and psn != last_plotstatus_nonce:
                last_plotstatus_nonce = psn
                try:
                    out_s, nlines, size = make_status_plot(
                        out=os.path.join(directory, '00_R2_Status_V01.gcode'), var_path=VAR_PATH)
                    try:
                        _moonraker_gcode(
                            'RESPOND MSG="Status plot: 00_R2_Status_V01.gcode - %d line(s), %.1fmm - '
                            'start it (pen mode)"\nM117 Status ready\n_SOUND_LIB NAME=r2_done'
                            % (nlines, size))
                    except Exception as me:                  # noqa: BLE001
                        print(f'[plotstatus] moonraker unreachable ({me.__class__.__name__})', flush=True)
                    print(f'[plotstatus] 00_R2_Status_V01.gcode: {nlines} line(s) at {size:g}mm', flush=True)
                except Exception as e:                      # noqa: BLE001
                    print(f'[plotstatus] error: {e}', flush=True)
                    try:
                        _moonraker_gcode(
                            'RESPOND MSG="Status plot ERROR: %s"\nM117 Status error\n'
                            '_SOUND_LIB NAME=r2_error' % e)
                    except Exception:                       # noqa: BLE001
                        pass
        except Exception as e:                          # noqa: BLE001
            print(f'[plotstatus] poll error: {e!r}', flush=True)
        # R75: host health check (host_nonce, set by HOST_CHECK on the LCD/console)
        try:
            hn = rv.get('host_nonce', '')
            if hn and hn != last_host_nonce:
                last_host_nonce = hn
                try:
                    host_check()
                except Exception as e:                      # noqa: BLE001
                    print(f'[host] check error: {e!r}', flush=True)
        except Exception as e:                              # noqa: BLE001
            print(f'[host] poll error: {e!r}', flush=True)
        try:
            scan()
        except Exception as e:                      # noqa: BLE001
            print(f'[!] scan error: {e!r}', flush=True)
        # R73: freshly uploaded/converted files -> push their parameters to the
        # LCD right away (Pre-Print > File + the plotter group for plot files)
        for _pp in NEW_PREVIEW[-1:]:
            push_preview(_pp)
        if first:
            # R57: the summary makes the initial batch visible - before, the
            # journal just went quiet after the first files ("nothing happens?")
            print(f'[i] initial scan done: {stats["files"]} gcode file(s) found, '
                  f'{stats["processed"]} processed, {stats["tagged_before"]} already tagged, '
                  f'{stats["errors"]} errors'
                  + (' - now watching for new files' if not once else ''), flush=True)
            first = False
            if once:
                return
        if time.time() - last_beat >= 900:
            # heartbeat every 15 min so it is obvious the daemon is alive
            print(f'[i] still watching {directory} ({stats["files"]} files, '
                  f'{stats["processed"]} processed this run)', flush=True)
            last_beat = time.time()
        time.sleep(interval)


def main():
    args = sys.argv[1:]
    if not args:
        print(__doc__)
        sys.exit(1)
    if args[0] == '--watch':
        if len(args) < 2:
            print('usage: r2_postproc.py --watch DIRECTORY [--once]')
            sys.exit(1)
        watch(args[1], once='--once' in args)
        return
    if args[0] == '--label':
        if len(args) < 4:
            print('usage: r2_postproc.py --label "TEXT1|TEXT2" W H [KEY=VALUE ...]')
            print('  FONT=SMOOTH|MONO|PIXEL BASE_LAYERS=4 TEXT_LAYERS=2 LAYER_H=0.2')
            print('  FIRST_H=0.28 IRONING=1 HOLE_SIDE=0(=none,1L,2R,3T,4B) HOLE_D=5')
            print('  BRIM=1 GAP=6 COLOR2=1 MATERIAL=PLA BED=x0,y0,x1,y1 OUT=dir')
            sys.exit(1)
        texts = [t.strip() for t in args[1].split('|') if t.strip()]
        kw = {}
        for a in args[4:]:
            if '=' in a:
                k, v = a.split('=', 1)
                kw[k.upper()] = v

        def _cb(key, dflt):
            return str(kw.get(key, dflt)).strip().lower() not in ('0', 'false', 'no', 'off', '')

        bed = None
        if 'BED' in kw:
            bed = tuple(float(x) for x in kw['BED'].split(','))
        out, info = make_labels(
            texts, w=float(args[2]), h=float(args[3]),
            font=kw.get('FONT', 'SMOOTH'),
            base_layers=int(float(kw.get('BASE_LAYERS', 4))),
            text_layers=int(float(kw.get('TEXT_LAYERS', 2))),
            layer_h=float(kw.get('LAYER_H', 0.2)),
            first_h=float(kw.get('FIRST_H', 0.28)),
            ironing=_cb('IRONING', '1'),
            hole_side=int(float(kw.get('HOLE_SIDE', 0))),
            hole_d=float(kw.get('HOLE_D', 5)),
            brim=_cb('BRIM', '1'),
            gap=float(kw.get('GAP', 6)),
            color2=_cb('COLOR2', '1'),
            material=kw.get('MATERIAL', 'PLA'),
            bed=bed, out_dir=kw.get('OUT', '.'))
        print('[ok] %s: %d label(s) %dx%d grid, %d layers, tower %s'
              % (info['file'], info['count'], info['cols'], info['rows'],
                 info['layers'], 'on' if info['tower'] else 'off'))
        return
    if args[0] == '--reso':
        if len(args) < 3:
            print('usage: r2_postproc.py --reso X|Y|BOTH PRINT|PLOT [CSVDIR=] [OUT=] [BED=x0,y0,x1,y1]')
            sys.exit(1)
        kw = {}
        for a2 in args[3:]:
            if '=' in a2:
                k, v = a2.split('=', 1)
                kw[k.upper()] = v
        axes = ['x', 'y'] if args[1].upper() == 'BOTH' else [args[1].lower()]
        bed = None
        if 'BED' in kw:
            bed = tuple(float(x) for x in kw['BED'].split(','))
        csv_dirs = [kw['CSVDIR']] if 'CSVDIR' in kw else _resonance_csv_dirs('.')
        files, info = make_resonance(axes=axes, mode=args[2], out_dir=kw.get('OUT', '.'),
                                     bed=bed, csv_dirs=csv_dirs)
        for ax in info['axes']:
            print('[reso] %s: %s' % (ax.upper(), info['axes'][ax]['best_txt']))
        print('[ok] %s' % ', '.join(files))
        return
    if args[0] == '--bridge':
        if len(args) < 3:
            print('usage: r2_postproc.py --bridge LEN SHORT_PCT [KEY=VALUE ...]')
            print('  H_LONG=35 H_SHORT=18 TOWER=10 LAYERS=1 SPEED=20 FAN=255')
            print('  LAYER_H=0.2 FIRST_H=0.28 MATERIAL=PLA BED=x0,y0,x1,y1 OUT=dir')
            sys.exit(1)
        kw = {}
        for a2 in args[3:]:
            if '=' in a2:
                k, v = a2.split('=', 1)
                kw[k.upper()] = v
        bed = None
        if 'BED' in kw:
            bed = tuple(float(x) for x in kw['BED'].split(','))
        out, info = make_bridge(
            length=float(args[1]), short_pct=int(float(args[2])),
            h_long=float(kw.get('H_LONG', 35)), h_short=float(kw.get('H_SHORT', 18)),
            tower=float(kw.get('TOWER', 10)), bridge_layers=int(float(kw.get('LAYERS', 1))),
            speed=float(kw.get('SPEED', 20)), fan=int(float(kw.get('FAN', 255))),
            layer_h=float(kw.get('LAYER_H', 0.2)), first_h=float(kw.get('FIRST_H', 0.28)),
            material=kw.get('MATERIAL', 'PLA'), bed=bed, out_dir=kw.get('OUT', '.'))
        print('[ok] %s: long %.0fmm, short %.0fmm (%d%%), %d layers'
              % (info['file'], info['length'], info['short_len'],
                 info['short_pct'], info['layers']))
        return
    if args[0] == '--plottext':
        if len(args) < 2:
            print('usage: r2_postproc.py --plottext FILE.txt [OUT=] [VARS=variables.cfg]')
            sys.exit(1)
        kw = {}
        for a2 in args[2:]:
            if '=' in a2:
                k, v = a2.split('=', 1)
                kw[k.upper()] = v
        out, nlines, size = text_convert(args[1], out=kw.get('OUT'),
                                         var_path=kw.get('VARS'))
        print('[ok] %s: %d line(s) at %gmm' % (out, nlines, size))
        return
    if args[0] == '--statusplot':
        kw = {}
        for a2 in args[1:]:
            if '=' in a2:
                k, v = a2.split('=', 1)
                kw[k.upper()] = v
        out, nlines, size = make_status_plot(out=kw.get('OUT'), var_path=kw.get('VARS'))
        print('[ok] %s: %d line(s) at %gmm' % (out, nlines, size))
        return
    if args[0] == '--range':
        if len(args) < 4:
            print('usage: r2_postproc.py --range FILE START END [FLOOR TOP BRIM]')
            sys.exit(1)
        fl = int(args[4]) if len(args) > 4 else 0
        tp = int(args[5]) if len(args) > 5 else 0
        br = int(args[6]) if len(args) > 6 else 0
        out, nl = make_range(args[1], int(args[2]), int(args[3]), floor=fl, top=tp, brim=br)
        print(f'[ok] {out}: {nl} layers (floor {fl}/top {tp}/brim {br}) - start via the dialog')
        return
    dry = '--dry-run' in args
    verbose = '-v' in args or '--verbose' in args
    files = [a for a in args if not a.startswith('-')]
    for f in files:
        s = process(f, dry=dry, verbose=verbose)
        if s['skipped']:
            print(f'[skip] {f}: already processed (tag found)')
        elif not dry:
            print(f'[ok] {f}: +{s["marks_added"]} LAYER_MARK ({s["method"]}), '
                  f'+{s["types"]} APPLY_TYPE, _FILE_INFO (layers={s["layers"]}, '
                  f'by_object={s["by_object"]})' + (' [upgraded from ' + s['upgraded_from'] + ']' if s['upgraded'] else ''))


if __name__ == '__main__':
    main()
