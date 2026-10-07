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
import shutil

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
    'top surface infill': 'SURFACE-TOP',      # R90.1b: frame structure layers
    'bottom surface': 'SURFACE-BOTTOM',
    'support': 'SUPPORT',
    'support interface': 'SUPPORT',
    'support/base': 'SUPPORT',
    'ironing': 'IRONING',
    'bridge': 'BRIDGE',
    'skirt': 'SKIRT',
    'brim': 'BRIM',
    'custom': 'CUSTOM',
    # R94 (field log .73): OrcaSlicer/Bambu Studio emit ';TYPE:gap fill' (the
    # map only knew 'gap infill' - gap fill segments NEVER switched). Plus
    # the classic PrusaSlicer names and Cura's dashed forms - lowercase keys,
    # the lookup is .strip().lower().
    'gap fill': 'GAPS',
    'wall-outer': 'WALL-OUTER',
    'wall-inner': 'WALL-INNER',
    'perimeter': 'WALL-INNER',
    'external perimeter': 'WALL-OUTER',
    'fill': 'INFILL-SPARSE',
    'solid infill': 'INFILL-SOLID',
    'top solid infill': 'SURFACE-TOP',
    'bottom solid infill': 'SURFACE-BOTTOM',
    'bridge infill': 'BRIDGE',
    'support material': 'SUPPORT',
    'support material interface': 'SUPPORT',
    # R95 (field log .73): the remaining slicer features, all families.
    # Prusa/Orca slow-overhang walls, internal bridges, the purge tower
    # (3 spellings) - now EDITABLE features; approximations documented.
    'overhang perimeter': 'OVERHANG-PERIM',
    'internal bridge': 'INTERNAL-BRIDGE',
    'wipe tower': 'PRIME-TOWER',
    'prime tower': 'PRIME-TOWER',
    'prime-tower': 'PRIME-TOWER',
    'thin wall': 'WALL-INNER',        # SuperSlicer: no own override
    'support transition': 'SUPPORT',
    'ooze shield': 'SKIRT',
    # Cura: dashed forms + combined skin (top/bottom share one type)
    'skin': 'SURFACE-TOP',
    'top-skin': 'SURFACE-TOP',
    'bottom-skin': 'SURFACE-BOTTOM',
    'support-interface': 'SUPPORT',
    'raft': 'SURFACE-BOTTOM',
    'infill': 'INFILL-SPARSE',
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
    # R95: small perimeters are a SPEED setting inside the walls (no
    # separate ;TYPE: exists) - shown in the file info instead
    'small_perimeter_speed': 'SPEED_SMALL',
    'small_perimeter_acceleration': 'ACCEL_SMALL',
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
        self.px = None            # R87.2: pen position (travel retract logic)
        self.py = None
        self.hole = None          # (cx, cy, r) - travels crossing it retract
        self.ret_mm = 0.6         # R87.2: retract over open holes (direct drive)
        self.ret_feed = 2400
        if not e_rel:
            out.append('G92 E0   ; R2-RANGE: generated geometry E starts at 0')

    def _retract(self):
        if self.e_rel:
            self.out.append('G1 E-%.3f F%d' % (self.ret_mm, self.ret_feed))
        else:
            self.acc -= self.ret_mm
            self.out.append('G1 E%.5f F%d' % (self.acc, self.ret_feed))

    def _unretract(self):
        if self.e_rel:
            self.out.append('G1 E%.3f F%d' % (self.ret_mm, self.ret_feed))
        else:
            self.acc += self.ret_mm
            self.out.append('G1 E%.5f F%d' % (self.acc, self.ret_feed))

    def move(self, x, y, feed):
        # R87.2: a travel over the OPEN hole retracts first - unretracted
        # crossings dragged strings across the hole (field log .71)
        crosses = (self.hole is not None and self.px is not None
                   and _seg_hits_circle((self.px, self.py), (x, y),
                                        self.hole[0], self.hole[1], self.hole[2]))
        if crosses:
            self._retract()
        self.out.append('G0 X%.3f Y%.3f F%d' % (x, y, feed))
        if crosses:
            self._unretract()
        self.px, self.py = x, y

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
        self.px, self.py = x1, y1

    def loop(self, pts, e_per_mm, feed):
        self.move(pts[0][0], pts[0][1], 4800)
        px, py = pts[0]
        for (x, y) in pts[1:]:
            self.line(px, py, x, y, e_per_mm, feed)
            px, py = x, y
        self.line(px, py, pts[0][0], pts[0][1], e_per_mm, feed)

    def loop_open(self, pts, e_per_mm, feed):
        # R87.2: open polyline (the hole spiral must NOT close back)
        self.move(pts[0][0], pts[0][1], 4800)
        px, py = pts[0]
        for (x, y) in pts[1:]:
            self.line(px, py, x, y, e_per_mm, feed)
            px, py = x, y


def _pt_in_poly(pt, poly):
    """R95: even-odd point-in-polygon (open-slot keep-out support)."""
    x, y = pt
    inside = False
    n = len(poly)
    j = n - 1
    for i in range(n):
        xi, yi = poly[i]
        xj, yj = poly[j]
        if (yi > y) != (yj > y) and x < (xj - xi) * (y - yi) / (yj - yi + 1e-12) + xi:
            inside = not inside
        j = i
    return inside


def _segs_cross(p1, p2, p3, p4):
    """R95: do segments (p1,p2) and (p3,p4) properly cross?"""
    def _c(o, a, b):
        return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])
    d1 = _c(p3, p4, p1)
    d2 = _c(p3, p4, p2)
    d3 = _c(p1, p2, p3)
    d4 = _c(p1, p2, p4)
    return ((d1 > 0) != (d2 > 0)) and ((d3 > 0) != (d4 > 0))


def _seg_hits_poly(p, q, poly):
    """R95: does segment (p,q) enter the polygon? (endpoint inside or an
    edge crossing) - used for open slots like a frame's view opening."""
    if _pt_in_poly(p, poly) or _pt_in_poly(q, poly):
        return True
    for i in range(len(poly)):
        a, b = poly[i], poly[(i + 1) % len(poly)]
        if _segs_cross(p, q, a, b):
            return True
    return False


def _seg_hits_circle(p, q, cx, cy, r):
    """R87.2: does segment (p,q) pass closer than r to (cx,cy)?

    Travel moves that cross an open range hole drag strings across it
    (field log .71: 'the floor fills straight over the hole, filament hangs
    in it') - _GenE uses this to retract before such travels."""
    dx, dy = q[0] - p[0], q[1] - p[1]
    a = dx * dx + dy * dy
    if a < 1e-12:
        return (p[0] - cx) ** 2 + (p[1] - cy) ** 2 < r * r
    t = max(0.0, min(1.0, ((cx - p[0]) * dx + (cy - p[1]) * dy) / a))
    hx, hy = p[0] + t * dx, p[1] + t * dy
    return (hx - cx) ** 2 + (hy - cy) ** 2 < r * r


def _spiral_ring(g, cx, cy, r, r_out, wid, e_per_mm, feed):
    """R87.2: the boss ring around a hole as ONE CONTINUOUS archimedean
    spiral from the hole edge out to r_out.

    Field log .71: the discrete rim loops + clipped hatch left strings across
    the open hole (travels crossed it unretracted). The spiral fills the whole
    band in a single stroke - no travel inside the band at all - and the hatch
    only starts outside r_out (its remaining crossing travels retract via
    _GenE.hole). Same wall thickness as the old rim loops."""
    r0 = r + wid / 2.0                 # wall inner edge touches the hole
    if r_out <= r0:
        r_out = r0 + wid * 0.5
    turns = max(1, int(math.ceil((r_out - r0) / max(wid * 0.95, 0.05))))
    spt = 56                           # points per turn (smooth up to d=80mm)
    total = turns * spt
    pts = []
    for k in range(total + 1):
        frac = k / float(total)
        rr = r0 + (r_out - r0) * frac
        ang = 2.0 * math.pi * frac * turns
        pts.append((cx + rr * math.cos(ang), cy + rr * math.sin(ang)))
    g.loop_open(pts, e_per_mm, feed)


def _seg_outside_circle(p, q, cx, cy, r):
    """R86.2: clip segment (p,q) to the parts OUTSIDE circle (cx,cy,r).

    Range floor/cap holes: hatch lines must stop at the hole's boss ring.
    Returns 0..2 segments."""
    dx, dy = q[0] - p[0], q[1] - p[1]
    fx, fy = p[0] - cx, p[1] - cy
    a = dx * dx + dy * dy
    if a < 1e-12:
        return [(p, q)] if (fx * fx + fy * fy) >= r * r else []
    b = 2.0 * (fx * dx + fy * dy)
    c = fx * fx + fy * fy - r * r
    disc = b * b - 4.0 * a * c
    if disc <= 0.0:
        return [(p, q)] if c > 0.0 else []
    sq = math.sqrt(disc)
    t1 = max(0.0, (-b - sq) / (2.0 * a))
    t2 = min(1.0, (-b + sq) / (2.0 * a))
    if t1 >= t2:
        return [(p, q)]
    parts = []
    if t1 > 0.02:
        parts.append((p, (p[0] + dx * t1, p[1] + dy * t1)))
    if t2 < 0.98:
        parts.append(((p[0] + dx * t2, p[1] + dy * t2), q))
    return parts


def _poly_min_edge_dist(pts, cx, cy):
    """R88 (field log .71, bug 4): min distance from (cx, cy) to the polygon
    edges. For a CONVEX polygon (the layer ink hull / the bbox fallback rect)
    this is exactly the radius of the largest circle around (cx, cy) that fits
    inside the outline - concave shapes need the mask variant below."""
    best = None
    n = len(pts)
    for i in range(n):
        ax, ay = pts[i]
        bx, by = pts[(i + 1) % n]
        dx, dy = bx - ax, by - ay
        l2 = dx * dx + dy * dy
        if l2 < 1e-12:
            d = math.hypot(cx - ax, cy - ay)
        else:
            t = ((cx - ax) * dx + (cy - ay) * dy) / l2
            t = 0.0 if t < 0.0 else (1.0 if t > 1.0 else t)
            d = math.hypot(cx - (ax + dx * t), cy - (ay + dy * t))
        if best is None or d < best:
            best = d
    return best


def _mask_center_dist(grid, res, cx, cy):
    """R88: distance from (cx, cy) to the nearest cell the outline mask does
    NOT cover (the true section boundary, concavities included). Chebyshev
    ring scan with an exact early exit: every cell beyond ring k is at
    Chebyshev distance >= k+1, and the Euclidean distance is never smaller
    than the Chebyshev distance - so once (k+1)*res >= the best hit, no
    unscanned cell can beat it. Cell-center approximation (error <= res*0.71)
    is absorbed by the hole edge margin."""
    rows, x0, y0, nx, ny = grid
    ci = int((cx - x0) / res)
    cj = int((cy - y0) / res)
    if not (0 <= ci < nx and 0 <= cj < ny) or not rows[cj][ci]:
        return 0.0                     # center itself is outside the area
    best = None
    k = 0
    while k < max(nx, ny):
        jlo, jhi = max(0, cj - k), min(ny, cj + k + 1)
        ilo, ihi = max(0, ci - k), min(nx, ci + k + 1)
        for j in range(jlo, jhi):
            row = rows[j]
            edge_j = (j == cj - k or j == cj + k)
            for i in range(ilo, ihi):
                if not edge_j and i != ci - k and i != ci + k:
                    continue            # interior of the ring - already scanned
                if not row[i]:
                    dd = math.hypot(x0 + (i + 0.5) * res - cx,
                                    y0 + (j + 0.5) * res - cy)
                    if best is None or dd < best:
                        best = dd
        if best is not None and (k + 1) * res >= best:
            return best
        k += 1
    return best if best is not None else min(nx, ny) * res


# R88 (field log .71, bug 4): solid rim the boss outer edge keeps INSIDE the
# real section outline - the hatch must have something to weld to outwards
_HOLE_EDGE_MARGIN = 2.0


def _range_hole_prep(hole_d, bbox, wid, notes, what, poly=None, grid=None, res=0.3):
    """R86.2: centered hole in a range floor/cap (cable / E14-E27 lampholder).

    R88 (field log .71, bug 4): the diameter is clamped against the section's
    REAL outline - the hull polygon (FOOTPRINT mode) or the outline mask
    (OUTLINE mode), whichever that floor/cap actually fills - so hole + boss
    + a tolerance margin NEVER stick out of round, L-shaped or otherwise
    non-rectangular sections. (The old clamp only knew the bounding BOX
    around them and happily let the boss float in air.) Returns None (off) or
    a dict(cx, cy, r, rim, r_out)."""
    d = float(hole_d or 0.0)
    if d <= 0.05:
        return None
    x0, y0, x1, y1 = bbox
    cx, cy = (x0 + x1) / 2.0, (y0 + y1) / 2.0
    lim = None                         # available radius at the center
    src = 'bounding box (fallback)'
    if poly is not None:
        lim = _poly_min_edge_dist(poly, cx, cy)
        src = 'footprint hull'
    if grid is not None:
        m = _mask_center_dist(grid, res, cx, cy)
        lim = m if lim is None else min(lim, m)
        src = 'true outline'
    if lim is None:
        lim = min(x1 - x0, y1 - y0) / 2.0
    rim = max(3, min(6, int(round(d / 10.0))))          # boss loops (thick wall)
    max_r = lim - _HOLE_EDGE_MARGIN - rim * wid
    if max_r < 4.0:
        notes.append('%s hole skipped: the section\'s real outline leaves less '
                     'than 8mm for the hole + boss' % what)
        return None
    if d < 3.0:
        d = 3.0
    if d / 2.0 > max_r:
        notes.append('%s hole %.1fmm clamped to %.1fmm - the real outline (%s) '
                     'only fits the boss + %.1fmm margin'
                     % (what, d, 2.0 * max_r, src, _HOLE_EDGE_MARGIN))
        d = 2.0 * max_r
    return {'cx': cx, 'cy': cy, 'r': d / 2.0, 'rim': rim,
            'r_out': d / 2.0 + rim * wid}


def _anchor_bbox(anchor, mask, res):
    """bbox of the raft/cap anchor: hull polygon or outline-mask extents."""
    if anchor:
        return (min(p[0] for p in anchor), min(p[1] for p in anchor),
                max(p[0] for p in anchor), max(p[1] for p in anchor))
    if mask is not None:
        return (mask[1], mask[2], mask[1] + mask[3] * res, mask[2] + mask[4] * res)
    return None


def make_range(src, start, end, floor=0, top=0, brim=0, first_h=0.2, version=1,
               floor_shape='hull', floor_fill='grid',
               top_shape='hull', top_fill='solid',
               floor_hole=0.0, top_hole=0.0):
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
    b_idx = None          # R87.2: raw index where the body ends (mark of end+1)
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
    cut_key = None       # R94: feature ACTIVE at the cut (last ;TYPE: /
                         # APPLY_TYPE before layer 'start') - a vase carries a
                         # single ;TYPE: in layer 1, so a range from layer >= 2
                         # had NO type in its body and printed as the raft's
                         # INFILL-SOLID all the way (field log .73)
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
                b_idx = i
            if layn_on:
                layn.append(line)
            # modal state of the head (lines[:a], exclusive of the cut mark)
            if a_idx is None or i < a_idx:
                c = _stripped(line)
                # R94: ;TYPE: comments are comments - _stripped() empties
                # them. Match the RAW line for the feature, the command
                # string for APPLY_TYPE.
                _mty94 = TYPE_RE.match(line)
                if _mty94:
                    _mk94 = TYPE_MAP.get(_mty94.group(1).strip().lower())
                    if _mk94:
                        cut_key = _mk94
                if c:
                    if c.startswith('APPLY_TYPE'):
                        _ma94 = re.match(r'APPLY_TYPE\s+TYPE=(\S+)', c)
                        if _ma94:
                            cut_key = _ma94.group(1)
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

    # R87.2: body feature diagnostics (field log .71: the model printed as
    # 'solid infill' all the way - the body carried no APPLY_TYPE markers, so
    # the floor's type stayed active). Count what layers start..end carry.
    body_types = 0      # ;TYPE: comments with a known feature
    body_applies = 0    # APPLY_TYPE commands
    bstats = {}         # R94: honest per-feature stats OF THE BODY - the
                        # excerpt's _FILE_INFO must describe what the excerpt
                        # really prints, not the whole source (field log .73:
                        # features from layers outside the range showed as
                        # activatable but never printed)
    if a_idx is not None:
        _b = b_idx if b_idx is not None else n_stream
        _frun = None    # canonical type of the current body segment
        _fv = None      # modal F (mm/min)
        _acc = None     # last M204 seen (mm/s2) - 'in effect there'
        _fvre = re.compile(r'F(\d+(?:\.\d+)?)')
        _evre = re.compile(r'\bE(-?\d+(?:\.\d+)?)')
        with open(src, 'r', errors='replace') as f:
            _i = 0
            for raw in f:
                _ls = raw.strip()
                if _i >= a_idx and _i < _b:
                    _mty = TYPE_RE.match(raw)
                    if _mty and TYPE_MAP.get(_mty.group(1).strip().lower()):
                        body_types += 1
                        _frun = TYPE_MAP[_mty.group(1).strip().lower()]
                    elif _ls.startswith('APPLY_TYPE'):
                        body_applies += 1
                        _ma94 = re.match(r'APPLY_TYPE\s+TYPE=(\S+)', _ls)
                        if _ma94:
                            _frun = _ma94.group(1)
                    elif _ls.startswith('M204'):
                        _mp94 = re.search(r'[PS](\d+(?:\.\d+)?)', _ls)
                        if _mp94:
                            _acc = float(_mp94.group(1))
                    elif _ls.startswith(('G0 ', 'G1 ')):
                        _mf94 = _fvre.search(_ls)
                        if _mf94:
                            _fv = float(_mf94.group(1))
                        _me94 = _evre.search(_ls)
                        if _me94 and _frun and float(_me94.group(1)) > 0:
                            _sp94 = round(_fv / 60.0, 2) if _fv else 0.0
                            d = bstats.setdefault(_frun, {'f': {}, 'acc': None})
                            d['f'][_sp94] = d['f'].get(_sp94, 0) + 1
                            if _acc is not None:
                                d['acc'] = _acc
                _i += 1
    else:
        body_types = body_applies = 0   # invalid range - the checks below raise

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
    # R86.2: centered floor/cap holes, 0 = off (diameter mm)
    floor_hole = max(0.0, min(float(floor_hole or 0.0), 90.0))
    top_hole = max(0.0, min(float(top_hole or 0.0), 90.0))
    notes = []
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
    fh = None           # R86.2: floor hole (bound below when floor > 0)
    if floor > 0 or brim > 0:
        anchor = _as_poly(hull1)
        if anchor is None and mask1 is None:
            raise ValueError('the range layers carry no extrusion moves - '
                             'nothing to anchor a raft/brim on')
        # R88: the shape the raft will actually fill decides which geometry
        # clamps the hole (hull polygon vs. true-outline mask)
        f_shape = _shape_ok(floor_shape, anchor, mask1) if floor > 0 else None
        # R86.2: centered floor hole (cable feed / E14-E27 lampholder)
        fh = None
        if floor_hole > 0 and floor > 0:
            bb = _anchor_bbox(anchor, mask1, res)
            if bb:
                fh = _range_hole_prep(floor_hole, bb, wid, notes, 'floor',
                                      poly=anchor if f_shape == 'hull' else None,
                                      grid=mask1 if f_shape == 'outline' else None,
                                      res=res)
                if fh:
                    gen.append('; R2-RANGE floor hole: centered d=%.1fmm, '
                               'boss %d loops (thick wall)' % (fh['r'] * 2.0, fh['rim']))
        elif floor_hole > 0:
            notes.append('floor hole ignored - no FLOOR layers set')
        g = _GenE(gen, e_rel)
        if fh:
            # R87.2: from the very first travel on, crossings retract
            g.hole = (fh['cx'], fh['cy'], fh['r'])
        # R94 helper: the brim belongs to the FIRST layer, printed right at
        # the outline (field log .73: it used to run AFTER the last raft
        # layer - on top of the raft, where it could not help adhesion)
        def _brim_block():
            gen.append('; R2-RANGE brim: %d loop(s) on the FIRST layer, '
                       'zero gap to the outline' % brim)
            gen.append('APPLY_TYPE TYPE=BRIM')
            for k in range(brim):
                hull_off = _offset_hull(anchor, wid + k * wid)
                g.loop(hull_off, first_h * wid / FIL_AREA, 1200)
        # RAFT: 'floor' solid layers under the section footprint - the hull is
        # offset by half a line width so the raft edge sits flush with the
        # model walls (ZERO gap - it welds directly to the section).
        if floor > 0:
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
                if i == 0 and brim > 0:
                    _brim_block()                     # R94: brim ON layer 1
                    gen.append('APPLY_TYPE TYPE=INFILL-SOLID   ; R2-RANGE: back to the raft')
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
                    segs = _mask_hatch(mask1[0], mask1[1], mask1[2],
                                       mask1[3], mask1[4], res, spacing, ang)
                else:
                    hull_off = _offset_hull(anchor, wid / 2.0)
                    g.loop(hull_off, ep, 1200)
                    segs = _hull_hatch(anchor, spacing, ang)
                if fh:
                    # R87.2 FIELD REWORK (.71 log: strings hung across the open
                    # hole): the boss ring is ONE CONTINUOUS spiral from the
                    # hole edge out to r_out (same wall thickness as the old
                    # rim loops) - not a single travel crosses the open hole;
                    # the hatch only starts outside the band and every travel
                    # that still passes over the hole retracts (_GenE.hole)
                    g.hole = (fh['cx'], fh['cy'], fh['r'])
                    _spiral_ring(g, fh['cx'], fh['cy'], fh['r'],
                                 fh['r_out'], wid, ep, 1200)
                    segs = [s for (p, q) in segs
                            for s in _seg_outside_circle(p, q, fh['cx'],
                                                         fh['cy'], fh['r_out'])]
                for (p, q) in segs:
                    g.move(p[0], p[1], 4800)
                    g.line(p[0], p[1], q[0], q[1], eph, 1200)
        if brim > 0 and floor <= 0:
            # R94: no raft - the brim runs alone BEFORE the body, at the
            # body's first Z (it used to inherit whatever Z was modal -
            # undefined without a raft). Z FIRST, then the loops.
            gen.append('G0 Z%.3f F600   ; R2-RANGE: brim at the first layer Z' % base_z)
            _brim_block()

    hull_n = _as_poly(hull_n)
    t_shape = _shape_ok(top_shape, hull_n, mask_n) if top else None
    # R86.2: centered cap hole (bridge-first, see docstring)
    th = None
    if top_hole > 0:
        if top <= 0 or t_shape is None:
            notes.append('cap hole ignored - no TOP layers (or no cap anchor)')
        else:
            bb = _anchor_bbox(hull_n, mask_n, res)
            if bb:
                th = _range_hole_prep(top_hole, bb, wid, notes, 'cap',
                                      poly=hull_n if t_shape == 'hull' else None,
                                      grid=mask_n if t_shape == 'outline' else None,
                                      res=res)
                if th:
                    if top < 3:
                        notes.append('cap hole: TOP auto-raised %d -> 3 layers '
                                     '(bridge layer + 2 solid)' % top)
                        top = 3
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
                segs = _mask_hatch(mask_n[0], mask_n[1], mask_n[2],
                                   mask_n[3], mask_n[4], res, spacing, ang)
            else:
                hull_off = _offset_hull(hull_n, wid / 2.0)
                gt.loop(hull_off, ep, 1200)
                segs = _hull_hatch(hull_n, spacing, ang)
            if th:
                # R87.2: travels over the open cap hole retract too
                gt.hole = (th['cx'], th['cy'], th['r'])
                if i == 0:
                    # R95 (field log .74): the anchor ring used to print right
                    # ON the hole edge - its inner half hung in the air over
                    # the open hole, sagged into the opening and closed it
                    # with a bridge that had to be picked out. BRIDGE-FIRST
                    # now, exactly like a slicer builds a hole in a top
                    # surface: (1) short radial BRIDGES across the edge, each
                    # anchored on the body outside, (2) the hole ring prints
                    # ON TOP of the bridges (INTERNAL-BRIDGE), (3) only then
                    # the solid hatch fills up TO the hole edge - the opening
                    # itself stays free (spoke tips reach in < 0.15mm).
                    segs = [s for (p, q) in segs
                            for s in _seg_outside_circle(p, q, th['cx'],
                                                         th['cy'], th['r'])]
                    gen_top.append('APPLY_TYPE TYPE=BRIDGE   ; R95: bridges around the hole first')
                    _over95 = min(0.15, 0.4 * wid)
                    _nb95 = max(12, min(64, int((2.0 * math.pi * th['r']) / 4.0)))
                    for k in range(_nb95):
                        _a95 = 2.0 * math.pi * (k + 0.5) / _nb95
                        _ca95, _sa95 = math.cos(_a95), math.sin(_a95)
                        _x095 = th['cx'] + (th['r'] + 1.5 * wid) * _ca95
                        _y095 = th['cy'] + (th['r'] + 1.5 * wid) * _sa95
                        _x195 = th['cx'] + (th['r'] - _over95) * _ca95
                        _y195 = th['cy'] + (th['r'] - _over95) * _sa95
                        gt.move(_x095, _y095, 4800)
                        gt.line(_x095, _y095, _x195, _y195, ep, 1300)
                    gen_top.append('APPLY_TYPE TYPE=INTERNAL-BRIDGE   ; R95: the ring prints ON the bridges')
                    gt.loop(_circle(th['cx'], th['cy'], th['r'], 48), ep, 1200)
                    gen_top.append('APPLY_TYPE TYPE=INFILL-SOLID   ; R95: back to the cap solid')
                else:
                    # R87.2: spiral band (same as the floor) - no strings
                    _spiral_ring(gt, th['cx'], th['cy'], th['r'],
                                 th['r_out'], wid, ep, 1200)
                    segs = [s for (p, q) in segs
                            for s in _seg_outside_circle(p, q, th['cx'],
                                                         th['cy'], th['r_out'])]
            for (p, q) in segs:
                gt.move(p[0], p[1], 4800)
                gt.line(p[0], p[1], q[0], q[1], eph, 1200)

    # R87.2: feature diagnostics for the excerpt header (out_lines is built
    # right below - the notes must be complete before that)
    if body_types > 0 and body_applies == 0:
        notes.append('body feature markers re-derived from the ;TYPE: comments '
                     '(the source carried no APPLY_TYPE - Live > Features works anyway)')
    elif body_types == 0 and body_applies == 0:
        if cut_key:
            notes.append('these layers carry no own ;TYPE: (vase-style: the '
                         'source states it once) - the body opens with %s, '
                         'the feature active at the cut' % cut_key)
        else:
            notes.append('NO feature markers in these layers - Live > Features '
                         'cannot switch, the body prints with the last active feature')
    # R94: the generated geometry is content too - raft/cap count as
    # INFILL-SOLID, the brim as BRIM (both print at F1200 = 20 mm/s)
    if (floor > 0 or top > 0) and 'INFILL-SOLID' not in bstats:
        bstats['INFILL-SOLID'] = {'f': {20.0: 1}, 'acc': None}
    if brim > 0 and 'BRIM' not in bstats:
        bstats['BRIM'] = {'f': {20.0: 1}, 'acc': None}
    # R95: a cap with a hole builds real bridges now (spokes F1300, ring
    # F1200) - both belong in the excerpt's TYPES so the features are honest
    if th is not None:
        if 'BRIDGE' not in bstats:
            bstats['BRIDGE'] = {'f': {21.6: 1}, 'acc': None}
        if 'INTERNAL-BRIDGE' not in bstats:
            bstats['INTERNAL-BRIDGE'] = {'f': {20.0: 1}, 'acc': None}

    # ---- prologue: a NORMAL file head with PRINT_START -> full start flow ----
    n_layers = end - start + 1 + floor + top
    # R74: the copied _FILE_INFO goes in at the TOP (it used to run at the very
    # END of the print - Live > File showed the PREVIOUS print's values during
    # the whole range print). Runs as the first command after the TAG, before
    # PRINT_START, with the corrected layer count.
    if file_info_line:
        file_info_line = re.sub(r'TOTAL_LAYERS=\d+', f'TOTAL_LAYERS={n_layers}', file_info_line)
        # R94 (field log .73): TYPES=/FS_/FA_ described the WHOLE source -
        # features whose layers lie outside the range showed as activatable
        # but never printed. Replace them with what the EXCERPT really
        # contains: the body's own stats + the generated geometry.
        file_info_line = re.sub(r'\s+(TYPES|FS_[A-Z0-9_-]+|FA_[A-Z0-9_-]+)=\S+',
                                '', file_info_line)
        _own94 = []
        for _canon94 in bstats:
            _d94 = bstats[_canon94]
            _suf94 = _canon94.replace('-', '_')
            if _d94['f']:
                _own94.append('FS_%s=%g' % (_suf94,
                                            max(_d94['f'], key=_d94['f'].get)))
            if _d94['acc'] is not None:
                _own94.append('FA_%s=%g' % (_suf94, _d94['acc']))
        if bstats:
            _own94.append('TYPES=' + ','.join(bstats))
        if _own94:
            file_info_line = (file_info_line.rstrip() + ' '
                              + ' '.join(_own94)).rstrip()
    out_lines = [
        f'; R2-RANGE excerpt of {os.path.basename(src)}: layers {start}..{end} of {total}',
        f'; layer {start} prints as the FIRST layer at Z{base_z:g} on the bed'
        + (f' (on a {floor}-layer raft)' if floor else '')
        + (f', {top} solid cap layers on top' if top else '')
        + (f', brim {brim}' if brim else '')
        + ((', floor hole d%gmm' % (fh['r'] * 2.0)) if fh else '')
        + ((', cap hole d%gmm bridge-first' % (th['r'] * 2.0)) if th else ''),
        '; R79: this file AUTO-SELECTS itself after generation (the source file',
        '; selection is replaced - nothing is deleted). AS LEGACY = mesh + purge',
        '; + YOUR pre-print settings (recommended) | AS SLICED = 1:1 (source temps)',
        '; first layer rules apply: 0.2mm layer 1, fan off, L1 temps (Pre-Print)',
        TAG,
    ]
    if file_info_line:
        out_lines.append(file_info_line)
    for _nt in notes:
        out_lines.append('; R2-RANGE note: %s' % _nt)
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
    held_type = None     # R87.2: a ;TYPE: line held back one line - synthesized
    held_key = None      # APPLY_TYPE follows only when the source has none
    cut_pending = cut_key is not None   # R94: re-assert the cut feature right
    body_open = False                   # after the body's first line
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
                        if held_type is not None:
                            fo.write(held_type + '\n')
                            if not c.startswith('APPLY_TYPE'):
                                # R87.2: source without markers (old v1 tag)
                                # - the floor's INFILL-SOLID used to stay
                                # active for the WHOLE model
                                fo.write('APPLY_TYPE TYPE=%s   ; R2-RANGE: marker re-derived (source had none)'
                                         % held_key + '\n')
                            held_type = None
                        # carry the source fan into layer 2 (first layer = fan off)
                        if c == 'LAYER_MARK':
                            lm_seen += 1
                            fo.write(l + '\n')
                            if lm_seen == 2 and fan:
                                fo.write(f'M106 S{fan}   ; R2-RANGE: fan state carried over from the source layers (layer 2+)' + '\n')
                        else:
                            mty = TYPE_RE.match(l)
                            key = TYPE_MAP.get(mty.group(1).strip().lower()) if mty else None
                            if key:
                                held_type = l
                                held_key = key
                            else:
                                fo.write(l + '\n')
                        if not body_open:
                            # R94 (field log .73): the body must OPEN with the
                            # feature that was active at the cut - a vase-style
                            # source states ;TYPE: once in layer 1, so a range
                            # from layer >= 2 printed as the raft's INFILL-
                            # SOLID all the way. Re-asserting here makes every
                            # excerpt self-contained.
                            body_open = True
                            if cut_pending:
                                fo.write('; R2-RANGE: %s was active at the cut '
                                         '(layer %d)\n' % (cut_key, start))
                                fo.write('APPLY_TYPE TYPE=%s   ; R2-RANGE: '
                                         'active at the cut\n' % cut_key)
                            cut_pending = False
                idx += 1
        if held_type is not None:
            fo.write(held_type + '\n')
            fo.write('APPLY_TYPE TYPE=%s   ; R2-RANGE: marker re-derived (source had none)'
                     % held_key + '\n')
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
        # R95 (field log .74, rule dd): open holes [(cx, cy, r), ...] and
        # open slots [poly, ...] - a travel crossing one drags strings across
        # the opening no matter how SHORT it is, so crossings retract even
        # below jump_d
        self.holes = []
        self.hole_polys = []
        # R77: retract/hop only for jumps LONGER than jump_d. 2.5mm fired
        # between neighboring hatch lines (field log: retract storm = the
        # label base tore apart, the filament was 'pulled away'). Print
        # files use 6mm - only real feature jumps (label->label, ->tower)
        # retract, neighboring infill lines just travel flat.
        self.jump_d = float(jump_d)

    def set_z(self, z, feed=1200):
        self.L.append('G0 Z%.3f F%d' % (z, feed))
        self.z = z

    def _hole_cross(self, x, y):
        # R95: does the travel (pen -> x,y) cross an OPEN hole or slot?
        if self.x is None:
            return False
        p, q = (self.x, self.y), (x, y)
        if self.holes and any(_seg_hits_circle(p, q, cx, cy, r)
                              for (cx, cy, r) in self.holes):
            return True
        if self.hole_polys and any(_seg_hits_poly(p, q, poly)
                                   for poly in self.hole_polys):
            return True
        return False

    def travel(self, x, y, feed=4500, hop=True, force_d=None):
        # R73: travel capped at 75mm/s (the .56 label jobs overloaded the MCU
        # with 150mm/s travels) and Z-hops only above 2.5mm
        # R83: force_d lowers the retract threshold for THIS move (text
        # bundles retract from 1.2mm gaps - field log .65: no-retract travels
        # between letters drew ghost lines and the letters grew together)
        # R95: hole crossings retract at ANY length (rule dd)
        if self.x is None:
            self.L.append('G0 X%.3f Y%.3f F%d' % (x, y, feed))
        else:
            d = math.hypot(x - self.x, y - self.y)
            # R96: the hole check only counts REAL moves - a zero-length hop
            # (layer seam straight into the band start) crosses nothing
            if ((d > 0.02 and self._hole_cross(x, y))
                    or d > (self.jump_d if force_d is None else force_d)):
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
    """R92: the REAL printable bed, not the stepper range.

    This machine's position_max values are deliberately lifted (micro probe +
    bed mesh rides beyond the plate), so they must NEVER size generator
    placements. Source chain:
      1. [r2_postproc] section in printer.cfg: bed_min_x / bed_max_x /
         bed_min_y / bed_max_y  (also read by the LCD macros - ONE truth)
      2. Ender-3 default: x 0..220, y -3..217 (confirmed by the user, R92)
    A one-line hint is printed when the section is missing.
    """
    dflt = (0.0, -3.0, 220.0, 217.0)
    secs = {}
    try:
        with open(cfg_path, errors='replace') as f:
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
            return float(d)
    r2 = secs.get('r2_postproc', {})
    if ('bed_min_x' in r2 and 'bed_max_x' in r2
            and 'bed_min_y' in r2 and 'bed_max_y' in r2):
        x0 = val('r2_postproc', 'bed_min_x', 0.0)
        x1 = val('r2_postproc', 'bed_max_x', 220.0)
        y0 = val('r2_postproc', 'bed_min_y', -3.0)
        y1 = val('r2_postproc', 'bed_max_y', 217.0)
        if x1 > x0 and y1 > y0:
            return (x0, y0, x1, y1)
        print('[bed] [r2_postproc] bed values are not sane - using the '
              'Ender-3 default 220x220', flush=True)
    else:
        print('[bed] no [r2_postproc] section in printer.cfg - using the '
              'Ender-3 default 220x220 (add bed_min_x/bed_max_x/bed_min_y/'
              'bed_max_y to configure)', flush=True)
    return dflt



_NOZZLE_CACHE = {}


def _nozzle_diameter(cfg_path):
    """R90.1c(field): the REAL nozzle diameter from printer.cfg [extruder]
    (nozzle_diameter:) - ONE truth for every generator (line widths, E per mm,
    hatch spacing all derive from it). Fallback 0.6 (the machine default).
    Returns (diameter, from_cfg)."""
    try:
        _ck = (cfg_path, os.path.getmtime(cfg_path))
    except OSError:
        _ck = (cfg_path, -1)
    if _ck in _NOZZLE_CACHE:
        return _NOZZLE_CACHE[_ck]
    val, ok = 0.6, False
    try:
        with open(cfg_path, errors='replace') as f:
            cur = None
            for l in f:
                ls = l.strip()
                if ls.startswith('[') and ls.endswith(']'):
                    cur = ls[1:-1].strip().lower()
                elif cur == 'extruder' and ':' in ls and not ls.startswith(('#', ';')):
                    k, v = ls.split(':', 1)
                    if k.strip().lower() == 'nozzle_diameter':
                        try:
                            val = max(0.1, min(float(v.split('#')[0].split(';')[0]), 2.0))
                            ok = True
                        except ValueError:
                            pass
                        break
    except OSError:
        pass
    _NOZZLE_CACHE[_ck] = (val, ok)
    return val, ok


def _gen_nozzle(directory):
    """R90.1c(field): nozzle diameter for the watcher's generator calls -
    reads printer.cfg [extruder] nozzle_diameter next to the gcodes folder.
    One console line when it deviates from the 0.6 machine default (line
    widths / E-per-mm / hatch spacing all derive from it)."""
    val, ok = _nozzle_diameter(os.path.join(
        os.path.dirname(os.path.abspath(directory).rstrip('/')),
        'config', 'printer.cfg'))
    if ok and abs(val - 0.6) > 0.01:
        print(f'[gen] nozzle {val}mm from printer.cfg - line widths adapt',
              flush=True)
    return val

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
    # R95 (field log .74, rule dd): the label holes stay OPEN through every
    # layer - travels across them retract at ANY length now
    pen.holes = [(lb['circ'][0] + lb['x'], lb['circ'][1] + lb['y'], lb['circ'][2])
                 for lb in labels if lb['circ']]

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
              'bridge_nonce', 'plot_text_nonce', 'plot_status_nonce', 'host_nonce',
              'label_fit_nonce', 'retract_fix_nonce', 'vol_fix_nonce',
              'cable_tie_nonce', 'angle_nonce', 'litho_nonce', 'seal_nonce',
              'litho_del_nonce', 'frame_nonce', 'texture_nonce',
              'file_check_nonce')


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
        # R96 (rule dd audit): the span between the tower near-edges is OPEN
        # air at deck height - registered as a polygon keep-out so a travel
        # across it retracts at ANY length. Normally the strand travels are
        # span-long and retract anyway (jump_d); the guard fires only when
        # the towers nearly touch (tiny spans). Cleared again afterwards -
        # tower hatch hops must never see it (R77 retract storm).
        _t9 = tower / 2.0
        _q0 = (c0[0] + d[0] * _t9, c0[1] + d[1] * _t9)
        _q1 = (c1[0] - d[0] * _t9, c1[1] - d[1] * _t9)
        pen.hole_polys = [[
            (_q0[0] - p[0] * _t9, _q0[1] - p[1] * _t9),
            (_q0[0] + p[0] * _t9, _q0[1] + p[1] * _t9),
            (_q1[0] + p[0] * _t9, _q1[1] + p[1] * _t9),
            (_q1[0] - p[0] * _t9, _q1[1] - p[1] * _t9)]]
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
        pen.hole_polys = []
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


# ---- R86: polygon helpers + cable-tie / angle-plate generators ----------------

def _poly_hatch(poly, spacing, angle_deg, keep_circles=None, min_len=0.35):
    """R86: scanline hatch clipped to an ARBITRARY simple polygon (convex or
    concave - a chevron plate has a concave inner corner) minus keep-out
    circles (screw holes). Returns [(p, q), ...] segments in SWEEP order
    (R77 rule: neighbors adjacent, no center-out hopping)."""
    keep_circles = keep_circles or []
    ang = math.radians(angle_deg)
    dx, dy = math.cos(ang), math.sin(ang)
    nx, ny = -dy, dx
    xs = [p[0] for p in poly] + [c[0] + c[2] for c in keep_circles] \
        + [c[0] - c[2] for c in keep_circles]
    ys = [p[1] for p in poly] + [c[1] + c[2] for c in keep_circles] \
        + [c[1] - c[2] for c in keep_circles]
    mx, my = (min(xs) + max(xs)) / 2.0, (min(ys) + max(ys)) / 2.0
    tmax = max(abs((px - mx) * nx + (py - my) * ny) for px, py in poly) + spacing
    segs = []
    n_scan = 0
    t = -tmax
    while t <= tmax:
        ox, oy = mx + nx * t, my + ny * t
        # polygon edge intersections -> inside intervals along the scan direction
        cuts = []
        n = len(poly)
        for i in range(n):
            x1, y1 = poly[i]
            x2, y2 = poly[(i + 1) % n]
            ex, ey = x2 - x1, y2 - y1
            denom = dx * ey - dy * ex
            if abs(denom) < 1e-12:
                continue
            s = ((x1 - ox) * ey - (y1 - oy) * ex) / denom
            u = ((x1 - ox) * dy - (y1 - oy) * dx) / denom
            if -1e-9 <= u <= 1.0 + 1e-9:
                cuts.append(s)
        cuts.sort()
        spans = []
        for i in range(0, len(cuts) - 1, 2):
            a, b = cuts[i], cuts[i + 1]
            if b - a >= min_len:
                spans.append([a, b])
        # subtract keep-out circles
        for (cx, cy, r) in keep_circles:
            dist = (cx - ox) * nx + (cy - oy) * ny
            if abs(dist) >= r:
                continue
            half = math.sqrt(r * r - dist * dist)
            sc = (cx - ox) * dx + (cy - oy) * dy
            lo, hi = sc - half, sc + half
            out = []
            for a, b in spans:
                if hi <= a or lo >= b:
                    out.append([a, b])
                    continue
                if a < lo - min_len:
                    out.append([a, min(b, lo)])
                if b > hi + min_len:
                    out.append([max(a, hi), b])
            spans = out
        line_segs = [((ox + dx * a, oy + dy * a), (ox + dx * b, oy + dy * b))
                     for a, b in spans if b - a >= min_len]
        if n_scan % 2:
            line_segs = [(q, p) for (p, q) in reversed(line_segs)]
        segs.extend(line_segs)
        n_scan += 1
        t += spacing
    return segs


def _inset_poly(poly, d):
    """R86: inset a polygon by d (edge offset, CCW assumed). Returns None if
    the inset degenerates (self-intersection risk) - the caller then skips the
    inner wall loop instead of printing garbage."""
    n = len(poly)
    out = []
    for i in range(n):
        p0 = poly[(i - 1) % n]
        p1 = poly[i]
        p2 = poly[(i + 1) % n]
        v1 = (p1[0] - p0[0], p1[1] - p0[1])
        v2 = (p2[0] - p1[0], p2[1] - p1[1])
        l1 = math.hypot(*v1)
        l2 = math.hypot(*v2)
        if l1 < 1e-9 or l2 < 1e-9:
            return None
        n1 = (-v1[1] / l1, v1[0] / l1)      # left normal = inward for CCW
        n2 = (-v2[1] / l2, v2[0] / l2)
        # intersection of the two inset edge lines
        a1, b1 = n1[0], n1[1]
        a2, b2 = n2[0], n2[1]
        # R86.2 sign fix: for a CCW polygon the LEFT normal points INWARD,
        # so offsetting by +d along the normal shrinks the polygon. (The old
        # '-d' outsized CCW input -> the area guard returned None every time
        # and callers silently skipped the inner wall entirely.)
        c1 = a1 * p1[0] + b1 * p1[1] + d
        c2 = a2 * p1[0] + b2 * p1[1] + d
        det = a1 * b2 - a2 * b1
        if abs(det) < 1e-12:
            out.append((p1[0] + (n1[0] + n2[0]) * d / 2, p1[1] + (n1[1] + n2[1]) * d / 2))
            continue
        x = (c1 * b2 - c2 * b1) / det
        y = (a1 * c2 - a2 * c1) / det
        # guard: the inset vertex must stay near the original (no blow-up)
        if math.hypot(x - p1[0], y - p1[1]) > 3.0 * d + 1.0:
            return None
        out.append((x, y))
    # area sanity: must shrink
    def area(pp):
        s = 0.0
        for i in range(len(pp)):
            x1, y1 = pp[i]
            x2, y2 = pp[(i + 1) % len(pp)]
            s += x1 * y2 - x2 * y1
        return abs(s) / 2.0
    if area(out) >= area(poly) - 1e-6 or len(out) < 3:
        return None
    return out


def _gen_markers(L):
    """R86: inject LAYER_MARK + APPLY_TYPE into a generated line list (the
    labels/angles/ties builders share this post-pass)."""
    outl = []
    for l in L:
        outl.append(l)
        ls = l.strip()
        if ls.startswith(';TYPE:'):
            key = ls[6:].strip().lower()
            outl.append('APPLY_TYPE TYPE=%s' % TYPE_MAP.get(key, 'CUSTOM'))
        elif LAYER_COMMENT.match(ls):
            outl.append('LAYER_MARK')
    return outl


def make_cable_ties(count=6, length=120.0, width=8.0, layers=3, variant='CLASSIC',
                    layer_h=0.2, first_h=0.28, brim=True, material='PLA',
                    bed=None, bed_margin=6.0, nozzle=0.6, out_dir='.', version=1):
    """R89: classic printable cable ties (Kabelbinder) - strap + small head.

    Field request R89 (replaces the R86 oversize closure): a CLASSIC tie with
    a normal-size one-way pawl head (thread the tip in, pull tight, cut to
    remove) and the LOOP variant - a frame loop with an open slot plus BEADS
    along the strap: pull the tip through the loop, it catches on a bead,
    adjustable tighter/looser at every bead and lifts back out = reusable.
    Widths 2-12mm (2mm = fine detail: works best with a 0.4 nozzle),
    lengths 50-300mm. Thin flexing parts - PETG/TPU bend best.
    Returns (path, info).
    """
    count = max(1, min(int(count), 24))
    length = float(length)
    width = float(width)
    layers = max(3, min(int(layers), 6))
    if not (50.0 <= length <= 300.0):
        raise ValueError('tie length %.0fmm out of range (50..300)' % length)
    if not (2.0 <= width <= 12.0):
        raise ValueError('tie width %.0fmm out of range (2..12)' % width)
    variant = str(variant).upper()
    if variant not in ('CLASSIC', 'LOOP'):
        variant = 'CLASSIC'
    if bed is None:
        bed = (0.0, -3.0, 244.0, 238.0)
    layer_h = max(0.06, min(float(layer_h), 0.34))
    first_h = max(0.08, min(float(first_h), 0.42))

    wid = max(0.4, nozzle * 1.08)
    fil = FIL_AREA

    notes = []
    if width < 3.6:
        notes.append('%.1fmm strap = fine detail - a 0.4 nozzle prints the '
                     'teeth/beads crisper than the 0.6 default' % width)

    if variant == 'CLASSIC':
        # ---- classic small pawl head (R89: was 2.4x/2.8x the width - HUGE) --
        HL = round(max(8.0, width + 4.5), 1)      # head along the strap
        HW = round(max(6.0, width + 2.6), 1)      # head across
        clr = 0.25                                # slot clearance per side
        slotw = width + 2 * clr
        head_base = 2                             # channel floor layers
        slot_layers = layers + 3                  # strap + teeth + clearance
        head_layers = head_base + slot_layers + 2 # + ceiling
        pitch = max(2.0, round(0.45 * width, 1))  # tooth pitch
        tooth_len = round(min(1.6, pitch * 0.55), 1)
        pawl_in = 0.8                             # pawl reaches into the slot
        total_layers = head_layers
    else:
        # ---- LOOP: frame with an open slot + beads along the strap ---------
        wall = round(max(2.2, 2.6 * wid), 1)      # frame wall thickness
        hole_w = width + 0.4                      # slot across (strap fits)
        hole_l = round(max(2.0, width * 0.6 + 0.8), 1)   # slot along
        LL = round(hole_l + 2 * wall, 1)          # frame along the strap
        HW = round(hole_w + 2 * wall, 1)          # frame across (= head width)
        HL = LL                                   # head length = frame length
        bead_h = 0.5                              # bead bulge per side (snaps
                                                  # through the slot with a light
                                                  # push but holds under pull)
        bead_l = round(max(1.6, 1.2 * bead_h * 2), 1)    # bead along (45 deg)
        bead_gap = round(max(3.0, width * 0.5 + 1.5), 1) # spacing between beads
        total_layers = layers + 2                 # frame is 2 layers thicker

    # ---- plate layout ------------------------------------------------------
    item_w = HL + length + 6.0
    item_h = max(HW, width) + 6.0
    bx0, by0, bx1, by1 = bed
    ux0, uy0 = bx0 + bed_margin, by0 + bed_margin
    ux1, uy1 = bx1 - bed_margin, by1 - bed_margin
    uw, uh = ux1 - ux0, uy1 - uy0
    best = None
    for cols in range(count, 0, -1):
        rows = -(-count // cols)
        gw = cols * item_w + (cols - 1) * 4.0
        gh = rows * item_h + (rows - 1) * 4.0
        if gw <= uw and gh <= uh:
            best = (cols, rows)
            break
    if best is None:
        raise ValueError('%d ties of %.0fmm do not fit the bed - fewer ties or '
                         'shorter length' % (count, length))
    cols, rows = best
    gw = cols * item_w + (cols - 1) * 4.0
    gh = rows * item_h + (rows - 1) * 4.0
    gx0 = ux0 + (uw - gw) / 2.0
    gy0 = uy0 + (uh - gh) / 2.0
    positions = []
    for i in range(count):
        r, c = divmod(i, cols)
        positions.append((gx0 + c * (item_w + 4.0) + 3.0,
                          gy0 + r * (item_h + 4.0) + 3.0))

    L = []
    a = L.append
    a('; R2-TIES generated cable ties (R89) - start it like any other file')
    a(TAG)
    if variant == 'CLASSIC':
        a('; %d tie(s): CLASSIC one-way pawl, strap %.0fx%.1fmm, %d strap layers '
          '@%.2gmm (head %.1fx%.1fmm, slot %.2fmm, tooth pitch %.1fmm)'
          % (count, length, width, layers, layer_h, HL, HW, slotw, pitch))
    else:
        a('; %d tie(s): LOOP with beads, strap %.0fx%.1fmm, %d strap layers '
          '@%.2gmm (loop %.1fx%.1fmm, slot %.1fx%.1fmm, beads every %.1fmm)'
          % (count, length, width, layers, layer_h, HL, HW, hole_l, hole_w, bead_gap))
    a('; thin flexing parts - PETG/TPU bend best; PLA works for gentle curves')
    a('; every tie is an exclude object - skip single ties live')

    pen = _Pen(L, jump_d=6.0)

    def tie_block(idx, x0, y0, z, li, first):
        """one tie at layer li"""
        cy = y0 + HW / 2.0
        e_wall = (first_h if li == 1 else layer_h) * wid / fil
        # R96 (rule dd audit): the open slots are registered keep-outs -
        # travels across them retract at ANY travel length. CLASSIC: the
        # head channel is open from the first wall layer above the solid
        # floor (the top never closes over it - the strap drops in from
        # above). LOOP: the frame slot is open through every layer.
        if variant == 'CLASSIC':
            pen.hole_polys = (
                [_rect_loop(x0, cy - slotw / 2.0, x0 + HL, cy + slotw / 2.0)]
                if li > head_base else [])
        else:
            pen.hole_polys = [
                _rect_loop(x0 + (LL - hole_l) / 2.0, cy - hole_w / 2.0,
                           x0 + (LL + hole_l) / 2.0, cy + hole_w / 2.0)]
        L.append('EXCLUDE_OBJECT_START NAME=TIE_%d' % (idx + 1))
        if variant == 'CLASSIC':
            hx0, hx1 = x0, x0 + HL
            sx0 = x0 + HL                       # strap starts at the head exit
            sx1 = x0 + HL + length
            if li <= layers:
                # strap rect + tip chamfer - the strap's own layers
                L.append(';TYPE:Outer wall')
                strap = [(sx0, cy - width / 2.0), (sx1 - 4.0, cy - width / 2.0),
                         (sx1, cy - width / 2.0 + width * 0.25),
                         (sx1, cy + width / 2.0 - width * 0.25),
                         (sx1 - 4.0, cy + width / 2.0), (sx0, cy + width / 2.0)]
                _emit_loop(pen, strap, e_wall, 1500 if first else 2400)
                L.append(';TYPE:Internal solid infill')
                _emit_hatch(pen, _hatch(sx0 + wid, cy - width / 2.0 + wid,
                                        sx1 - wid, cy + width / 2.0 - wid,
                                        None, wid, 45.0 if li % 2 else 135.0), e_wall,
                            1500 if first else 2700)
            elif li in (layers + 1, layers + 2):
                # teeth on top of the strap: low nub + steep lock flank
                L.append(';TYPE:Inner wall')
                tx = sx0 + 4.0
                while tx + tooth_len < sx1 - 8.0:
                    if li == layers + 1:
                        _emit_loop(pen, _rect_loop(tx, cy - width / 2.0,
                                                   tx + tooth_len, cy + width / 2.0),
                                   e_wall, 1800)
                    else:
                        _emit_loop(pen, _rect_loop(tx + 0.6, cy - width / 2.0,
                                                   tx + tooth_len, cy + width / 2.0),
                                   e_wall, 1800)
                    tx += pitch
            # ---- head: small classic box with a straight channel ------------
            if li <= head_base:
                # solid bottom plate (the channel floor)
                L.append(';TYPE:Outer wall')
                _emit_loop(pen, _rect_loop(hx0, y0, hx1, y0 + HW), e_wall, 1500 if first else 2400)
                L.append(';TYPE:Internal solid infill')
                _emit_hatch(pen, _hatch(hx0 + wid, y0 + wid, hx1 - wid, y0 + HW - wid,
                                        None, wid, 45.0 if li % 2 else 135.0), e_wall,
                            1500 if first else 2700)
            elif li <= head_base + slot_layers:
                # channel band: two side walls, the slot between stays open
                L.append(';TYPE:Outer wall')
                _emit_loop(pen, _rect_loop(hx0, y0, hx1, cy - slotw / 2.0), e_wall,
                           1500 if first else 2400)
                _emit_loop(pen, _rect_loop(hx0, cy + slotw / 2.0, hx1, y0 + HW), e_wall,
                           1500 if first else 2400)
                L.append(';TYPE:Internal solid infill')
                _emit_hatch(pen, _hatch(hx0 + wid, y0 + wid, hx1 - wid, cy - slotw / 2.0 - wid,
                                        None, wid, 45.0 if li % 2 else 135.0), e_wall,
                            1500 if first else 2700)
                _emit_hatch(pen, _hatch(hx0 + wid, cy + slotw / 2.0 + wid, hx1 - wid, y0 + HW - wid,
                                        None, wid, 45.0 if li % 2 else 135.0), e_wall,
                            1500 if first else 2700)
            else:
                # ceiling band (2 layers). Layer 1 of it = the PAWL: a strip
                # across the channel at the ENTRY that reaches INTO the slot -
                # the strap teeth ratchet under it. Layer 2 closes the box.
                cl = li - head_base - slot_layers          # 1..2
                L.append(';TYPE:Outer wall')
                _emit_loop(pen, _rect_loop(hx0, y0, hx1, cy - slotw / 2.0 - wid), e_wall,
                           1500 if first else 2400)
                _emit_loop(pen, _rect_loop(hx0, cy + slotw / 2.0 + wid, hx1, y0 + HW), e_wall,
                           1500 if first else 2400)
                L.append(';TYPE:Internal solid infill')
                _emit_hatch(pen, _hatch(hx0 + wid, y0 + wid, hx1 - wid,
                                        cy - slotw / 2.0 - wid - wid,
                                        None, wid, 45.0 if li % 2 else 135.0), e_wall,
                            1500 if first else 2700)
                _emit_hatch(pen, _hatch(hx0 + wid, cy + slotw / 2.0 + wid + wid, hx1 - wid,
                                        y0 + HW - wid, None, wid, 45.0 if li % 2 else 135.0),
                            e_wall, 1500 if first else 2700)
                if cl == 1:
                    # the pawl: full-width strip one layer DOWN into the slot,
                    # at the entry, so the teeth catch (classic one-way)
                    L.append(';TYPE:Inner wall')
                    _emit_loop(pen, _rect_loop(hx0 + 1.2, cy - slotw / 2.0 - wid,
                                               hx0 + 1.2 + max(2.5, width * 0.4),
                                               cy + slotw / 2.0 + wid), e_wall, 1800)
        else:
            # ================= LOOP variant =================================
            fx0, fx1 = x0, x0 + LL                 # frame along the strap
            hx0 = (fx0 + fx1 - hole_l) / 2.0       # hole rect
            hx1 = hx0 + hole_l
            hy0 = cy - hole_w / 2.0
            hy1 = cy + hole_w / 2.0
            sx0 = hx1 - wid                        # strap overlaps the right wall
            sx1 = fx1 + length
            # frame ring: outer loop .. hole edge (concentric)
            L.append(';TYPE:Outer wall')
            n_loops = max(2, int(round(wall / wid)))
            for k in range(n_loops + 1):
                off = k * wid
                # shrink the outer rect toward the hole
                ox0 = fx0 + off
                oy0 = cy - (HW / 2.0) + off
                ox1 = fx1 - off
                oy1 = cy + (HW / 2.0) - off
                if ox1 - ox0 < 2 * wid or oy1 - oy0 < 2 * wid:
                    break
                _emit_loop(pen, _rect_loop(ox0, oy0, ox1, oy1), e_wall,
                           1500 if first else 2400)
            # hole edge: the innermost loop must not fall below the hole
            L.append(';TYPE:Inner wall')
            _emit_loop(pen, _rect_loop(hx0, hy0, hx1, hy1), e_wall, 1500 if first else 2400)
            if li <= layers:
                # strap with beads: lower edge + mirrored upper edge
                w2 = width / 2.0
                lower = [(sx0, cy - w2)]
                x = hx1 + 6.0
                while x + bead_l < sx1 - 10.0:
                    lower.append((x, cy - w2))
                    lower.append((x + bead_l / 2.0, cy - w2 - bead_h))
                    lower.append((x + bead_l, cy - w2))
                    x += bead_l + bead_gap
                lower.append((sx1 - 4.0, cy - w2))
                lower.append((sx1, cy - w2 + width * 0.25))
                upper = [(px, 2 * cy - py) for (px, py) in reversed(lower)]
                L.append(';TYPE:Outer wall')
                _emit_loop(pen, lower + upper, e_wall, 1500 if first else 2400)
                L.append(';TYPE:Internal solid infill')
                _emit_hatch(pen, _hatch(sx0 + wid, cy - w2 + wid,
                                        sx1 - wid, cy + w2 - wid,
                                        None, wid, 45.0 if li % 2 else 135.0), e_wall,
                            1500 if first else 2700)
        L.append('EXCLUDE_OBJECT_END NAME=TIE_%d' % (idx + 1))

    # brim (first layer): loops around the head only (the strap needs none)
    def tie_brim(x0, y0):
        e_wall = first_h * wid / fil
        for off in (wid * 0.35, wid * 0.35 + wid):
            b = (x0 - off, y0 - off, x0 + HL + off, y0 + HW + off)
            L.append(';TYPE:Brim')
            _emit_loop(pen, _rect_loop(*b), e_wall, 1500)

    for li in range(1, total_layers + 1):
        z = round(first_h + (li - 1) * layer_h, 3)
        L.append(';LAYER_CHANGE')
        L.append(';Z:%.3f' % z)
        pen.set_z(z)
        if li == 2:
            L.append('M106 S178   ; R2-TIES: part fan from layer 2')
        for idx, (x0, y0) in enumerate(positions):
            if li == 1 and brim:
                L.append('EXCLUDE_OBJECT_START NAME=TIE_%d' % (idx + 1))
                tie_brim(x0, y0)
                L.append('EXCLUDE_OBJECT_END NAME=TIE_%d' % (idx + 1))
            tie_block(idx, x0, y0, z, li, li == 1)

    a('M107')
    a('PRINT_END')

    # header: exclude objects + PRINT_START (labels pattern: TAG first, the
    # first COMMAND is PRINT_START - that is where a legacy _FILE_INFO would go)
    hdr = []
    for idx, (x0, y0) in enumerate(positions):
        # R87.2 FIELD FIX (.71 log): Klipper json-parses POLYGON - no whitespace
        poly = '[[%.1f,%.1f],[%.1f,%.1f],[%.1f,%.1f],[%.1f,%.1f]]' % (
            x0, y0, x0 + HL + length, y0,
            x0 + HL + length, y0 + HW, x0, y0 + HW)
        hdr.append('EXCLUDE_OBJECT_DEFINE NAME=TIE_%d CENTER=%.1f,%.1f POLYGON=%s'
                   % (idx + 1, (x0 + (HL + length) / 2.0), y0 + HW / 2.0, poly))
    ps = 'PRINT_START MATERIAL=%s LAYER_HEIGHT=%.2g TOTAL_LAYERS=%d OUTER_WALL_SPEED=40' % (
        material, layer_h, total_layers)
    i0 = next(i for i, l in enumerate(L) if l.startswith(';LAYER_CHANGE'))
    outl = (L[:i0] + hdr + [ps, 'G90', 'M83',
                            'M107   ; R2-TIES: first layer = fan off']
            + _gen_markers(L[i0:]))

    fname = '00_Ties_%.0fx%.0f_%s_V%02d.gcode' % (
        length, width, variant[:3], max(1, min(int(version), 99)))
    out = os.path.join(out_dir, fname)
    with open(out, 'w') as f:
        f.write('\n'.join(outl) + '\n')
    if variant == 'CLASSIC':
        notes = (['classic one-way pawl: head %.1fx%.1fmm, slot %.2fmm, '
                  'tooth pitch %.1fmm - pull tight, cut to remove'
                  % (HL, HW, slotw, pitch)] + notes)
    else:
        notes = (['ball-loop: pull the tip through the loop - it catches on '
                  'every bead, adjustable, lifts back out (reusable); '
                  'bead every %.1fmm' % bead_gap] + notes)
    info = {'file': fname, 'count': count, 'variant': variant,
            'length': length, 'width': width, 'layers': total_layers,
            'head': '%.1fx%.1fmm' % (HL, HW),
            'slot': round(slotw, 2) if variant == 'CLASSIC' else
                    '%.1fx%.1f' % (hole_l, hole_w),
            'pitch': pitch if variant == 'CLASSIC' else bead_gap,
            'grid': '%dx%d' % (cols, rows), 'notes': notes}
    return out, info



# =====================================================================================
#  R90: PICTURE FRAME / DISPLAY CASE (Bilderrahmen / Schaukasten)
# =====================================================================================
FRAME_PRESETS = {   # photo inner size mm (W x H), R90.1a: sized for the REAL
    # bed (220x220, ~208x214 usable). Frame + backplate side by side fit up
    # to 9x13 border<=8 - everything bigger prints as 2 PLATES (A = frame,
    # B = backplate+stand). 15x21/A5/A4/20x30 overflow the bed even split
    # into strips - not offered (custom W/H caps at 230 and says why).
    '9x13': (90, 130), '10x15': (102, 152), '13x18': (130, 180), 'A6': (105, 148),
}


def _rr_pts(w, h, r):
    """rounded rect contour, CCW, centered on (0,0)."""
    w, h, r = float(w), float(h), max(0.0, min(float(r), min(w, h) / 2.0 - 0.01))
    if r < 0.05:
        return [(-w / 2, -h / 2), (w / 2, -h / 2), (w / 2, h / 2), (-w / 2, h / 2)]
    k = 6
    pts = []
    # R90.1b FIX (audit): the corner order was TR->BR->BL->TL, so each arc
    # ENDED where the next one BEGINS only after a straight line across the
    # shape - the "rounded rect" was a 4-pointed STAR (self-intersecting),
    # which wrecked the hatch clipping and printed bowtie walls. Correct CCW
    # chain: TR -> TL -> BL -> BR, arcs 0/90/180/270 deg chaining edge-to-edge.
    for (sx, sy, a0) in ((1, 1, 0.0), (-1, 1, math.pi / 2),
                         (-1, -1, math.pi), (1, -1, 3 * math.pi / 2)):
        cx, cy = sx * (w / 2 - r), sy * (h / 2 - r)
        for i in range(k):
            a = a0 + (math.pi / 2) * i / (k - 1)
            pts.append((cx + r * math.cos(a), cy + r * math.sin(a)))
    return pts


def _el_pts(a, b, n=48):
    """ellipse contour, CCW, centered on (0,0)."""
    return [(a * math.cos(2.0 * math.pi * i / n), b * math.sin(2.0 * math.pi * i / n))
            for i in range(n)]


def _convex_intervals(poly, ox, oy, dx, dy):
    """scanline through convex poly -> inside interval along (dx,dy) or None."""
    cuts = []
    n = len(poly)
    for i in range(n):
        x1, y1 = poly[i]
        x2, y2 = poly[(i + 1) % n]
        ex, ey = x2 - x1, y2 - y1
        denom = dx * ey - dy * ex
        if abs(denom) < 1e-12:
            continue
        # R90.1b FIX (audit): the edge parameter had a SIGN ERROR - the ray
        # ran backwards, every intersection landed at t<0 and _convex_intervals
        # returned None. Result: the whole R90 frame ring printed as NAKED
        # walls - no infill, no photo shelf, no ironing content. Correct:
        # solve O + s*d = A + u*e for u:
        t = (dy * (x1 - ox) - dx * (y1 - oy)) / denom
        if 0.0 <= t <= 1.0:
            s = (x1 + ex * t - ox) * dx + (y1 + ey * t - oy) * dy
            cuts.append(s)
    if len(cuts) < 2:
        return None
    cuts.sort()
    return (cuts[0], cuts[-1])


def _ring_hatch(outer, inner, spacing, angle_deg, notch=None, min_len=0.35):
    """R90: scanline hatch over the RING between two convex contours (outer,
    inner), optionally minus a rectangular notch (the SIDE-closure slot).
    Boustrophedon sweep like _hatch (R77 rule: neighbors stay adjacent)."""
    ang = math.radians(angle_deg)
    dx, dy = math.cos(ang), math.sin(ang)
    nx, ny = -dy, dx
    xs = [p[0] for p in outer]
    ys = [p[1] for p in outer]
    if notch:
        xs += [notch[0], notch[2]]
        ys += [notch[1], notch[3]]
    mx, my = (min(xs) + max(xs)) / 2.0, (min(ys) + max(ys)) / 2.0
    tmax = max(abs((px - mx) * nx + (py - my) * ny) for px, py in outer) + spacing
    notch_poly = None
    if notch:
        notch_poly = _rect_loop(notch[0], notch[1], notch[2], notch[3])
    segs = []
    flip = False
    t = -tmax
    while t <= tmax:
        ox, oy = mx + nx * t, my + ny * t
        ov = _convex_intervals(outer, ox, oy, dx, dy)
        if ov is None:
            t += spacing
            continue
        gaps = []
        iv = _convex_intervals(inner, ox, oy, dx, dy)
        if iv:
            gaps.append(iv)
        if notch_poly:
            nv = _convex_intervals(notch_poly, ox, oy, dx, dy)
            if nv:
                gaps.append(nv)
        gaps.sort()
        spans = []
        cur = ov[0]
        for g0, g1 in gaps:
            if g1 <= cur or g0 >= ov[1]:
                continue
            if g0 > cur:
                spans.append((cur, g0))
            cur = max(cur, g1)
        if cur < ov[1]:
            spans.append((cur, ov[1]))
        row = []
        for s0, s1 in spans:
            if s1 - s0 < min_len:
                continue
            p = (ox + dx * s0, oy + dy * s0)
            q = (ox + dx * s1, oy + dy * s1)
            row.append((p, q) if not flip else (q, p))
        if row:
            if flip:
                row.reverse()
            segs.extend(row)
            flip = not flip
        t += spacing
    return segs


def _bite_contour(pts, side, y0, y1, nd):
    """rectangular bite into the left('L')/right('R') edge of a closed convex
    contour: material removed for y in [y0, y1], from the edge inwards by nd.
    Used for the R90 backplate bayonet notches (rect or oval plates)."""
    if side == 'L':
        xe = min(p[0] for p in pts)
        xin = xe + nd

        def inb(p):
            return y0 <= p[1] <= y1 and p[0] <= xe + 1e-6
        bite = [(xe, y0), (xin, y0), (xin, y1), (xe, y1)]
    else:
        xe = max(p[0] for p in pts)
        xin = xe - nd

        def inb(p):
            return y0 <= p[1] <= y1 and p[0] >= xe - 1e-6
        bite = [(xe, y0), (xin, y0), (xin, y1), (xe, y1)]
    n = len(pts)
    pts = list(pts)
    if inb(pts[0]):                       # rotate: avoid a wrap-around run
        k = next((i for i in range(n) if not inb(pts[i])), 0)
        pts = pts[k:] + pts[:k]
    out, i, done = [], 0, False
    while i < n:
        if inb(pts[i]):
            if not done:
                out.extend(bite)
                done = True
            while i < n and inb(pts[i]):
                i += 1
        else:
            out.append(pts[i])
            i += 1
    return out


def make_frame(preset='', width=148.0, height=210.0, depth=8.0, frame_w=12.0,
               corner=6.0, shape='RECT', closure='BACK', hang='TOP', stand=False,
               wall=1.6, infill=60.0, ironing=True, layer_h=0.2, first_h=0.28,
               material='PLA', bed=None, bed_margin=6.0, nozzle=0.6,
               out_dir='.', version=1, front='IRON', disc='NONE', disc_t=1.0,
               disc_side='FRONT', cable=False, s_deep=0.8, s_space=6.0,
               s_angle=45.0, s_amp=1.2, s_size=8.0, s_dir='OUT'):
    # R90.1b: front = IRON (ironed, classic) / FLIP (bed texture as the visible
    # face - prints front-down) / LINES / WAVES / HEX (structured front band)
    # disc = disc insert (GLASS/PLEXI/FOIL/LITHO), disc_t thickness, FRONT
    # (captured by a lip in front of the photo) or BACK (backlit, behind the
    # photo on the back band). cable = hidden duct through the bottom wall
    # (CASE only). s_* = structure parameters (depth/space/angle/amp/size/dir).
    """R90: picture frame (Bilderrahmen) or display case (Schaukasten).

    Lying print, FRONT UP = the visible face gets the ironing pass. Classic
    frame profile with ZERO overhangs: solid ring from back to front; the
    photo groove is cut into the INNER edge (the shelf bridges it - R87.2
    short-bridge tech), the closure nubs grow from the ring walls in-plane.

    depth < 15 mm  -> FLAT photo frame (groove = photo + backplate)
    depth >= 15 mm -> display CASE: same profile on a deep hollow body
    Closure BACK: photo from behind; bayonet backplate (edge notches clear
    the 2 side-wall nubs, slide 2.5mm to lock - zero flex needed)
    Closure SIDE: slot through the left wall - photo + card slide in sideways
    Backplate always included: hidden hang keyhole (hang TOP/BOTTOM/LEFT/
    RIGHT/OFF) + 2 stud holes when stand=ON (easel leg plugs in).
    R90.1a MULTI-PLATE: when frame + backplate do not fit side by side the
    generator writes TWO files 'Part A' (frame) + 'Part B' (backplate+stand)
    - kit strips only when even the frame alone overflows the bed.
    Oversized OVAL raises a clear error.

    Returns (path, info).
    """
    preset = str(preset or '')
    _pk = preset.upper()
    for _k, _v in FRAME_PRESETS.items():
        if _k.upper() == _pk:
            preset = _k
            width, height = _v
            break
    width, height = float(width), float(height)
    depth, frame_w = float(depth), float(frame_w)
    shape = str(shape).upper()
    if shape not in ('RECT', 'OVAL'):
        shape = 'RECT'
    closure = str(closure).upper()
    if closure not in ('BACK', 'SIDE'):
        closure = 'BACK'
    hang = str(hang or 'OFF').upper()
    if hang not in ('TOP', 'BOTTOM', 'LEFT', 'RIGHT', 'OFF'):
        hang = 'TOP'
    if not (40.0 <= width <= 230.0 and 40.0 <= height <= 230.0):
        raise ValueError('photo size %.0fx%.0fmm out of range (40..230 each)' % (width, height))
    if not (3.0 <= depth <= 60.0):
        raise ValueError('frame depth %.1fmm out of range (3..60; <15 = photo '
                         'frame, >=15 = display case)' % depth)
    if not (4.0 <= frame_w <= 30.0):
        raise ValueError('frame border %.1fmm out of range (4..30)' % frame_w)
    if not (0.8 <= float(wall) <= 3.0):
        raise ValueError('wall thickness %.1fmm out of range (0.8..3)' % wall)
    if not (20.0 <= float(infill) <= 100.0):
        raise ValueError('infill %.0f%% out of range (20..100)' % infill)
    front = str(front).upper()
    if front not in ('IRON', 'FLIP', 'LINES', 'WAVES', 'HEX'):
        raise ValueError('front %r must be IRON, FLIP, LINES, WAVES or HEX'
                         % front)
    disc = str(disc).upper()
    if disc not in ('NONE', 'GLASS', 'PLEXI', 'FOIL', 'LITHO'):
        raise ValueError('disc %r must be NONE, GLASS, PLEXI, FOIL or LITHO'
                         % disc)
    disc_side = str(disc_side).upper()
    if disc_side not in ('FRONT', 'BACK'):
        raise ValueError('disc_side %r must be FRONT or BACK' % disc_side)
    if disc != 'NONE' and not (0.4 <= float(disc_t) <= 6.0):
        raise ValueError('disc thickness %.1fmm out of range (0.4..6)' % disc_t)
    if front in ('LINES', 'WAVES', 'HEX'):
        if shape != 'RECT':
            raise ValueError('structured front (%s) needs SHAPE=RECT - an oval '
                             'clip is not supported' % front)
        if not (0.4 <= float(s_deep) <= 2.4):
            raise ValueError('structure depth %.1fmm out of range (0.4..2.4)'
                             % s_deep)
        if not (2.0 <= float(s_space) <= 15.0):
            raise ValueError('structure spacing %.1fmm out of range (2..15)'
                             % s_space)
        if not (0.0 <= float(s_angle) <= 90.0):
            raise ValueError('structure angle %.0f out of range (0..90)'
                             % s_angle)
        if front == 'WAVES' and not (0.3 <= float(s_amp) <= 3.0):
            raise ValueError('wave amplitude %.1fmm out of range (0.3..3)'
                             % s_amp)
        if front == 'HEX' and not (4.0 <= float(s_size) <= 20.0):
            raise ValueError('honeycomb cell %.1fmm out of range (4..20)'
                             % s_size)
        if str(s_dir).upper() not in ('IN', 'OUT'):
            raise ValueError('structure direction %r must be IN or OUT' % s_dir)
        s_dir = str(s_dir).upper()
    # R90.1a: default bed = the REAL Ender-3 plate (the watcher passes
    # _bed_limits() anyway - [r2_postproc] section, manual ch. 23)
    if bed is None:
        bed = (0.0, -3.0, 220.0, 217.0)
    layer_h = max(0.06, min(float(layer_h), 0.34))
    first_h = max(0.08, min(float(first_h), 0.42))
    infill = float(infill)

    wid = max(0.4, nozzle * 1.08)
    fil = FIL_AREA
    mode = 'CASE' if depth >= 15.0 else 'FLAT'
    notes = []

    # ---- contours (centered on 0,0) ------------------------------------------
    ow, oh = width + 2 * frame_w, height + 2 * frame_w          # outer
    pw, ph = width + 0.6, height + 0.6                          # photo opening
    vw, vh = width - 3.0, height - 3.0                          # view opening
    # R90.1b: FRONT disc capture lip - the front band opening shrinks so the
    # disc cannot fall out of the front (the lip covers its edge by 1.2mm)
    lip = 1.2 if (disc != 'NONE' and disc_side == 'FRONT') else 0.0
    if shape == 'OVAL':
        outer_c = _el_pts(ow / 2, oh / 2)
        photo_c = _el_pts(pw / 2, ph / 2)
        view_c = _el_pts(vw / 2, vh / 2)
        lip_c = (_el_pts((vw - 2 * lip) / 2, (vh - 2 * lip) / 2)
                 if lip else view_c)
    else:
        outer_c = _rr_pts(ow, oh, corner)
        photo_c = _rr_pts(pw, ph, max(0.0, corner - frame_w * 0.6))
        view_c = _rr_pts(vw, vh, max(0.0, corner - frame_w * 0.6 - 2.0))
        lip_c = (_rr_pts(vw - 2 * lip, vh - 2 * lip,
                         max(0.0, corner - frame_w * 0.6 - 2.0 - lip))
                 if lip else view_c)

    # ---- vertical profile (layer bands, bed = frame BACK) ---------------------
    ft = max(2 * layer_h, 1.0)              # front band (visible face)
    shelf_th = max(layer_h, 0.4)            # photo shelf (bridges the groove)
    # groove = photo + 0.8mm backplate + play; plate locks 0.2mm under the
    # nubs - the photo lies flat between back band and plate
    groove = 1.6 if mode == 'FLAT' else 2.8
    bb = depth - ft - shelf_th - groove     # back band (the rest)
    if bb < 2 * layer_h:
        groove = 1.4
        bb = depth - ft - shelf_th - groove
        if bb < layer_h:
            raise ValueError('depth %.1fmm too shallow for a photo groove '
                             '(needs >= %.1fmm)' % (depth, ft + shelf_th + groove + layer_h))
        notes.append('shallow frame: groove reduced to %.1fmm (thin photo + '
                     '0.8mm backplate)' % groove)
    # ---- R90.1b: disc insert deepens the groove (photo stack grows) ------
    disc_l = 0
    if disc != 'NONE':
        disc_l = max(1, int(round((float(disc_t) + 0.2) / layer_h)))
        groove += disc_l * layer_h
        bb = depth - ft - shelf_th - groove
        if bb < layer_h:
            raise ValueError('depth %.1fmm too shallow for photo + %.1fmm '
                             'disc (needs >= %.1fmm)'
                             % (depth, disc_t,
                                ft + shelf_th + groove + layer_h))
    # ---- R90.1b: structured front band -----------------------------------
    struct_l = 0
    if front in ('LINES', 'WAVES', 'HEX'):
        struct_l = max(2, int(round(float(s_deep) / layer_h)))
        if s_dir == 'OUT':
            ft += struct_l * layer_h     # ridges proud of the face
    n_ft = max(1, int(round(ft / layer_h)))
    n_sh = max(1, int(round(shelf_th / layer_h)))
    n_gr = max(1, int(round(groove / layer_h)))
    n_bb = max(1, int(round(bb / layer_h)))
    frame_layers = n_bb + n_gr + n_sh + n_ft
    # front-band layers that stay solid hatch; the top struct_l layers carry
    # ONLY the pattern (IN: grooves cut in / OUT: ridges added on top)
    solid_ft = n_ft - struct_l if struct_l else n_ft
    if solid_ft < 1:
        raise ValueError('front band too thin for %.1fmm deep grooves - '
                         'increase DEPTH or use direction OUT' % float(s_deep))
    bp_layers = max(3, int(round(0.8 / layer_h)))
    st_layers = max(6, int(round(1.2 / layer_h)))
    stud_layers = 6
    total_layers = frame_layers
    if bp_layers > total_layers:
        total_layers = bp_layers
    if stand and st_layers + stud_layers > total_layers:
        total_layers = st_layers + stud_layers

    # ---- closure nubs (BACK only): mini-bridges 1mm over the backplate -----
    # plate = 4 layers on the back band; nub band = layers n_bb+3..n_bb+4
    # (0.2mm overlap with the plate top). The plate's left/right edge
    # notches clear the nubs on the straight insert; sliding 2mm locks it.
    nub_d, nub_l = 1.0, 6.0
    # BACK disc: the plate rests on the disc rim - the nubs move up with it
    _nub_off = disc_l if (disc != 'NONE' and disc_side == 'BACK') else 0
    nub_zn = (set(range(n_bb + _nub_off + 3, n_bb + _nub_off + 5))
              if closure == 'BACK' else set())

    # SIDE closure: slot through the LEFT wall, open across the groove band
    # and the FULL wall length (photo + cover plate are ph+0.4 tall)
    # R90.1b: hidden cable duct - a 6mm slot through the bottom wall, opening
    # at the BACK edge (2.5mm up from the bed face), straight into the case
    # interior. Printable: the wall above bridges the 6mm gap.
    if front == 'FLIP' and ironing:
        notes.append('FLIP front: the bed texture IS the visible face (front '
                     'prints against the bed) - no ironing pass')
    if front in ('LINES', 'WAVES', 'HEX') and ironing:
        notes.append('%s structure is the finish - no ironing pass'
                     % front.capitalize())
    if disc != 'NONE':
        if disc_side == 'FRONT':
            notes.append('%s disc %.1fmm in FRONT of the photo: insert it '
                         'from behind onto the shelf, the 1.2mm front lip '
                         'holds it captive' % (disc, float(disc_t)))
        else:
            notes.append('%s disc %.1fmm BEHIND the photo on the back band '
                         '(backlit/litho) - the backplate rim clamps the disc '
                         'rim, nubs lock the stack' % (disc, float(disc_t)))
    cable_box = None
    n_cable_l = 0
    if cable:
        n_cable = min(max(2, int(round(2.5 / layer_h))), n_bb)
        n_cable_l = n_cable
        cable_w = 6.0
        cable_box = (-cable_w / 2, -oh / 2 - 1.0,
                     cable_w / 2, -ph / 2 + 0.2)
        notes.append('cable duct: 6mm slot through the bottom bar, 2.5mm '
                     'behind the back face - hidden from the front, opens '
                     'straight into the case interior (LED wiring)')
    side_slot = None
    if closure == 'SIDE':
        # full-height slit: everything left of the photo opening edge goes
        # (wall incl. corner stubs) - the T/B groove layers then simply
        # start 1.5mm further right, still sitting on the back band
        side_slot = (-ow / 2 - 1.0, -oh / 2 - 1.0, -pw / 2 + 0.5, oh / 2 + 1.0)

    # ---- bed layout ------------------------------------------------------------
    # frame left; right column = backplate (top) + stand (below). 4mm gaps,
    # 2mm plate rim - a 10x15 frame with border 10 still fits beside its plate
    gap = 3.0
    if closure == 'BACK':
        # bayonet plate: 1.2mm rim rests on the ring back, L/R edge notches
        bw, bh = pw + 2.4, ph + 2.4
    else:
        # SIDE: the cover plate slides through the wall slot - photo size
        bw, bh = pw + 0.4, ph + 0.4
    sw, sh = (26.0, 62.0) if stand else (0.0, 0.0)
    bx0, by0, bx1, by1 = bed
    ux0, uy0 = bx0 + bed_margin, by0 + bed_margin
    ux1, uy1 = bx1 - bed_margin, by1 - bed_margin
    uw, uh = ux1 - ux0, uy1 - uy0
    kit = False
    multi = False
    stand_ok = stand
    stand_below = False
    # does the frame+plate alone fit as ONE PIECE? (the stand is decided
    # after - it must never force a kit or an error on its own)
    if ow + gap + bw <= uw and max(oh, bh) <= uh:
        if stand:
            # stand below the plate (right column), else under the frame,
            # else dropped with a note (wall mounting still works)
            if ow + gap + max(bw, 26.0) <= uw and max(oh, bh + gap + 62.0) <= uh:
                pass                       # default: stand under the plate
            elif ow + gap + bw <= uw and max(oh + gap + 62.0, bh) <= uh:
                stand_below = True         # stand under the frame
            else:
                stand_ok = False
                notes.append('stand skipped - no room on this bed beside the '
                             'frame (wall mounting still works)')
    else:
        # R90.1a: MULTI-PLATE before kit - Part A = the frame alone, Part B =
        # backplate (+ stand). Glue-kit strips only when even the frame alone
        # overflows the bed (user decision u).
        if ow <= uw and oh <= uh:
            multi = True
        elif shape != 'RECT':
            raise ValueError('oval frame %.0fx%.0fmm does not fit the bed '
                             'together with its backplate (needs %.0fx%.0fmm) - '
                             'smaller photo/preset or less border'
                             % (ow, oh, ow + gap + bw, max(oh, bh)))
        else:
            kit = True
            if corner > 0.5:
                corner = 0.0
                notes.append('corner radius dropped to 0 - the split kit uses '
                             'straight strips with butt joints')
            if front in ('LINES', 'WAVES', 'HEX'):
                notes.append('structure skipped in kit mode - the strips '
                             'print a smooth face')
            if cable:
                cable_box = None
                n_cable_l = 0
                notes.append('cable duct skipped in kit mode - drill the '
                             'bottom strip after gluing (6mm, 2.5mm behind '
                             'the back face)')
            if ow > uw:
                raise ValueError('frame %.0fx%.0fmm exceeds the bed width even '
                                 'split into strips' % (ow, oh))
    sw, sh = (26.0, 62.0) if stand_ok else (0.0, 0.0)
    right_w = max(bw, sw)
    col2_h = bh + (gap + sh if stand_ok and not stand_below else 0.0)
    need_w = ow + gap + right_w
    need_h = max(oh + (gap + sh if stand_below else 0.0), col2_h)
    if kit:
        # kit footprint: 4 strips + the plate row below. If the rows together
        # overflow the bed the plate row moves to its own file (multi).
        vh_st = oh - 2 * frame_w
        strip_h = 4 * frame_w + 3 * gap
        row2_h = max(bh, sh if stand_ok else 0.0)
        kit_w = max(max(ow, vh_st), bw + (gap + sw if stand_ok else 0.0))
        kit_h = strip_h + gap + row2_h
        if (kit_w > uw or kit_h > uh) and stand_ok:
            # drop the stand, keep the printable frame + plate
            stand_ok = False
            sw = sh = 0.0
            row2_h = bh
            kit_w = max(max(ow, vh_st), bw)
            kit_h = strip_h + gap + row2_h
            notes.append('stand skipped - no room on this bed beside the kit '
                         'parts (wall mounting still works)')
        if kit_w > uw or kit_h > uh:
            if max(ow, vh_st) <= uw and strip_h <= uh:
                multi = True          # strips = plate A, backplate = plate B
            else:
                fw_max = (uh - 3 * gap) / 4.0
                raise ValueError('split kit needs %.0fx%.0fmm - even the 4 '
                                 'strips alone need %.0fx%.0fmm. Reduce the '
                                 'border to <= %.0fmm or use a smaller photo/'
                                 'preset' % (kit_w, kit_h, max(ow, vh_st),
                                             strip_h,
                                             max(4.0, min(30.0, fw_max))))
    if kit and (bw > uw or bh > uh):
        # nothing was written yet - bail out BEFORE any file appears
        raise ValueError('backplate %.0fx%.0fmm does not fit the bed - a '
                         'smaller photo or less border is needed' % (bw, bh))
    if cable and mode == 'FLAT' and not kit:
        # a kit skips the duct with a drill hint instead - everything else
        # needs the deep hollow body of a display case
        raise ValueError('cable duct needs a display CASE (DEPTH >= 15) - a '
                         'flat frame has no interior to reach')
    # ---- backplate contour (shared by one-piece + kit) -------------------------
    # the bites clear the nubs on the straight insert; their ASYMMETRIC
    # y-ranges lock the plate against sliding both ways after a 2.5mm drop
    if shape == 'OVAL':
        plate_pts = _el_pts(bw / 2, bh / 2)
    else:
        plate_pts = _rr_pts(bw, bh, max(0.0, corner - frame_w * 0.6))
    if closure == 'BACK':
        # densify: a plain rect contour has no vertices inside the bite
        # zone, so _bite_contour would find nothing to cut
        dens = []
        for i, (x0, y0) in enumerate(plate_pts):
            dens.append((x0, y0))
            x1, y1 = plate_pts[(i + 1) % len(plate_pts)]
            seg = ((x1 - x0) ** 2 + (y1 - y0) ** 2) ** 0.5
            if seg > 1.5:
                k = int(seg / 1.5) + 1
                for t in range(1, k):
                    dens.append((x0 + (x1 - x0) * t / k, y0 + (y1 - y0) * t / k))
        plate_pts = dens
        plate_pts = _bite_contour(plate_pts, 'L', -5.0, 4.0, 2.5)
        plate_pts = _bite_contour(plate_pts, 'R', -4.0, 5.0, 2.5)

    def plate_keeps(px, py):
        keep = []
        if hang != 'OFF':
            if hang in ('TOP', 'BOTTOM'):
                hx, hy = 0.0, (bh / 2 - 6.0) * (1 if hang == 'TOP' else -1)
                keep.append((px + hx, py + hy, 2.6))
                keep.append((px + hx, py + hy - (3.4 if hang == 'TOP' else -3.4), 1.7))
            else:
                hx, hy = (bw / 2 - 6.0) * (1 if hang == 'RIGHT' else -1), 0.0
                keep.append((px + hx, py + hy, 2.6))
                keep.append((px + hx - (3.4 if hang == 'RIGHT' else -3.4), py + hy, 1.7))
        if stand:
            keep.append((px - 12.0, py - bh / 2 + 6.0, 1.35))
            keep.append((px + 12.0, py - bh / 2 + 6.0, 1.35))
        return keep

    # ---- plate plan (R90.1a) ----------------------------------------------------
    # 1 file  = frame + backplate (+stand) side by side on one bed
    # 2 files = Part A: frame alone, Part B: backplate + stand (multi) - no
    #           auto-start, end-of-plate beeps + LCD hint instead (user rule u)
    if multi:
        plates = [('A', True, False), ('B', False, True)]
    else:
        plates = [('', True, True)]

    def frame_fname(sfx):
        return '00_Frame_%s_%sx%.0f%s%s_V%02d.gcode' % (
            preset if preset else '%.0fx%.0f' % (width, height),
            mode, depth, '_KIT' if kit else '', '_' + sfx if sfx else '',
            max(1, min(int(version), 99)))

    files = []
    for sfx, want_frame, want_rest in plates:
        L = []
        a = L.append
        a('; ' + TAG)
        a('; R2-FRAME generated picture frame (R90) - start it like any other file')
        if kit:
            a('; SPLIT KIT (too big for one piece): 4 frame strips to glue + '
              'backplate%s - butt joints, wood glue works' % (' + stand' if stand else ''))
        if multi:
            a('; PLATE %s of %d: %s - print the other file afterwards, '
              'nothing auto-starts' % (sfx, len(plates),
              'the frame' if want_frame else 'backplate%s'
              % (' + stand' if stand_ok else '')))
        a('; %s %s: photo %.0fx%.0fmm, border %.0fmm, depth %.1fmm, closure %s%s'
          % (mode, shape, width, height, frame_w, depth, closure,
             ', hidden hang keyhole %s' % hang if hang != 'OFF' else ''))
        a('; front prints UP (ironing pass on the visible face); %s' % (
            'deep hollow body, backplate closes the back' if mode == 'CASE' else
            'photo lies on the shelf behind the view opening'))
        a('; every part is an exclude object - skip one live in the Objects menu')
        pen = _Pen(L, jump_d=6.0)

        def e_w(li):
            return (first_h if li == 1 else layer_h) * wid / fil

        # ===================  ONE-PIECE frame (the ring) =========================
        if not kit:
            if want_frame and want_rest:
                top = uy0 + need_h
                cx = ux0 + ow / 2
                cy = top - oh / 2
                bx = ux0 + ow + gap + right_w / 2
                by = top - bh / 2
                sx = sy = 0.0
                if stand_ok and not stand_below:
                    sx = ux0 + ow + gap + right_w / 2
                    sy = uy0 + sh / 2
                elif stand_ok:
                    sx = ux0 + sw / 2
                    sy = uy0 + sh / 2
            elif want_frame:
                # PLATE A: the ring alone, bottom-left on the bed
                cx, cy = ux0 + ow / 2, uy0 + oh / 2
                bx = by = sx = sy = 0.0
            else:
                # PLATE B: backplate bottom-left + stand beside/below it
                cx = cy = 0.0
                bx, by = ux0 + bw / 2, uy0 + bh / 2
                sx = sy = 0.0
            # R95 (field log .74, rule dd): the view opening stays OPEN from
            # the bed up to the shelf - travels across it (front band <->
            # backplate <-> stand) drag strings into the opening. Registered
            # as a polygon keep-out: crossings retract at ANY travel length.
            if want_frame:
                pen.hole_polys = [[(x + cx, y + cy) for (x, y) in view_c]]
                if stand_ok:
                    if bw + gap + sw <= uw and max(bh, sh) <= uh:
                        sx, sy = ux0 + bw + gap + sw / 2, uy0 + sh / 2
                    elif max(bw, sw) <= uw and bh + gap + sh <= uh:
                        sx, sy = ux0 + sw / 2, uy0 + bh + gap + sh / 2
                    else:
                        stand_ok = False
                        sw = sh = 0.0
                        notes.append('stand skipped - no room beside the '
                                     'backplate on plate B (wall mounting '
                                     'still works)')
                if bw > uw or bh > uh:
                    raise ValueError('backplate %.0fx%.0fmm does not fit the '
                                     'bed' % (bw, bh))
            # R96 (rule dd audit): the backplate's hang keyhole + stand stud
            # holes stay OPEN through every layer - the hatch splits its
            # scanlines around them, and the hop across the split crossed
            # the raw hole unretracted. Registered as circle keep-outs:
            # crossings retract at ANY travel length.
            if want_rest:
                pen.holes = list(plate_keeps(bx, by))

            def emit_ring(li, inner, notch=None, hatch=True):
                ew = e_w(li)
                f1 = 1500 if li == 1 else 2400
                for loop in (outer_c, inner):
                    if notch and loop is outer_c:
                        # the slot cuts through the whole wall: outer loop split
                        # into polylines OUTSIDE the notch box (local coords!)
                        polylines = []
                        cur = []
                        for (x, y) in list(outer_c) + [outer_c[0]]:
                            if notch[0] <= x <= notch[2] and notch[1] <= y <= notch[3]:
                                if len(cur) > 1:
                                    polylines.append(cur)
                                cur = []
                            else:
                                cur.append((x + cx, y + cy))
                        if len(cur) > 1:
                            polylines.append(cur)
                        for pl in polylines:
                            _emit_loop(pen, pl, ew, f1, close=False)
                    elif notch and loop is inner and inner is photo_c:
                        polylines = []
                        cur = []
                        for (x, y) in list(photo_c) + [photo_c[0]]:
                            if notch[0] <= x <= notch[2] and notch[1] <= y <= notch[3]:
                                if len(cur) > 1:
                                    polylines.append(cur)
                                cur = []
                            else:
                                cur.append((x + cx, y + cy))
                        if len(cur) > 1:
                            polylines.append(cur)
                        for pl in polylines:
                            _emit_loop(pen, pl, ew, f1, close=False)
                    else:
                        _emit_loop(pen, [(x + cx, y + cy) for (x, y) in loop], ew, f1)
                if hatch:
                    # view/lip band = the solid face, photo band = body infill
                    spacing = (wid * 100.0 / max(20.0, infill)
                               if inner is photo_c else wid)
                    hs = _ring_hatch(outer_c, inner, spacing,
                                     45.0 if li % 2 else 135.0, notch=notch)
                    _emit_hatch(pen, [((p[0] + cx, p[1] + cy),
                                       (q[0] + cx, q[1] + cy))
                                      for (p, q) in hs],
                                ew, 1500 if li == 1 else 2700)

            def emit_nubs(li):
                # bayonet: exactly TWO nubs on the left/right wall centers,
                # reaching 1.0mm into the photo opening
                ew = e_w(li)
                for nx in (-pw / 2, pw / 2):
                    x0 = nx - nub_d if nx > 0 else nx
                    x1 = nx if nx > 0 else nx + nub_d
                    _emit_loop(pen, _rect_loop(x0 + cx, cy - nub_l / 2,
                                               x1 + cx, cy + nub_l / 2), ew, 1800)

            # ---- R90.1b: structured front (LINES / WAVES / HEX) -----------
            def _pt_in_rr(x, y, hw, hh, r):
                ax, ay = abs(x), abs(y)
                if ax > hw or ay > hh:
                    return False
                dx, dy = ax - (hw - r), ay - (hh - r)
                if dx > 0 and dy > 0:
                    return dx * dx + dy * dy <= r * r
                return True

            _ic = max(0.0, corner - frame_w * 0.6 - 2.0 - lip)
            _iw2, _ih2 = (vw - 2 * lip) / 2, (vh - 2 * lip) / 2

            def pat_ok(x, y, inset=0.0):
                # inside the front-band region (outer inset by `inset` so
                # ridges do not fuse into the walls, outside the view/lip)
                return (_pt_in_rr(x, y, ow / 2 - inset, oh / 2 - inset,
                                  max(0.0, corner - inset))
                        and not _pt_in_rr(x, y, _iw2, _ih2, _ic))

            def emit_pattern(li):
                ew = e_w(li)
                a(';TYPE:Top surface infill')
                if front == 'LINES':
                    hs = _ring_hatch(outer_c, lip_c if lip else view_c,
                                     float(s_space), float(s_angle))
                    _emit_hatch(pen, [((p[0] + cx, p[1] + cy),
                                       (q[0] + cx, q[1] + cy))
                                      for (p, q) in hs], ew, 1200)
                elif front == 'WAVES':
                    ang = math.radians(float(s_angle))
                    ca_, sa_ = math.cos(ang), math.sin(ang)
                    R = math.hypot(ow, oh) / 2 + 2.0
                    step = 0.4
                    k = 0
                    while -R + k * s_space <= R:
                        off = -R + k * s_space
                        run = []
                        nsteps = int(2 * R / step) + 1
                        for t in range(nsteps):
                            u = -R + t * step
                            v = off + (float(s_amp) *
                                       math.sin(2 * math.pi * u /
                                                max(1.0, float(s_space))))
                            x = cx + u * ca_ - v * sa_
                            y = cy + u * sa_ + v * ca_
                            if pat_ok(x - cx, y - cy, 0.4):
                                run.append((x, y))
                            else:
                                if len(run) > 1:
                                    _emit_loop(pen, run, ew, 1200, close=False)
                                run = []
                        if len(run) > 1:
                            _emit_loop(pen, run, ew, 1200, close=False)
                        k += 1
                else:   # HEX honeycomb, closed cells
                    hr = float(s_size) / 2.0
                    dxh = math.sqrt(3.0) * hr
                    dyh = 1.5 * hr
                    row = 0
                    gy = -oh / 2
                    while gy <= oh / 2:
                        gx = -ow / 2 + (dxh / 2 if row % 2 else 0.0)
                        while gx <= ow / 2:
                            verts = [(gx + hr * math.cos(math.radians(a6)),
                                      gy + hr * math.sin(math.radians(a6)))
                                     for a6 in range(0, 360, 60)]
                            if all(pat_ok(vx, vy, 0.8) for vx, vy in verts):
                                _emit_loop(pen, [(vx + cx, vy + cy)
                                                 for vx, vy in verts],
                                           ew, 1200, close=True)
                            gx += dxh
                        gy += dyh
                        row += 1

            pl_total = frame_layers
            if want_rest:
                pl_total = total_layers
                if not want_frame:
                    pl_total = max(bp_layers,
                                   (st_layers + stud_layers) if stand_ok else 0)

            for li in range(1, pl_total + 1):
                z = round(first_h + (li - 1) * layer_h, 3)
                a(';LAYER_CHANGE')
                a(';Z:%.3f' % z)
                pen.set_z(z)
                if li == 2:
                    a('M106 S178   ; R2-FRAME: part fan from layer 2')
                # ---- frame ring ----
                if want_frame and li <= frame_layers:
                    a('EXCLUDE_OBJECT_START NAME=FRAME')
                    # R90.1b FLIP: the band order mirrors - layer li carries
                    # the geometry of layer frame_layers+1-li (front on bed)
                    eli = frame_layers + 1 - li if front == 'FLIP' else li
                    if eli <= n_bb:
                        a(';TYPE:Outer wall')
                        emit_ring(eli, photo_c,
                                  notch=(cable_box if eli <= n_cable_l
                                         else None))
                    elif eli <= n_bb + n_gr:
                        a(';TYPE:Outer wall')
                        # groove band: the SIDE slot opens the left wall HERE
                        emit_ring(eli, photo_c, notch=side_slot)
                        if eli in nub_zn:
                            a(';TYPE:Inner wall')
                            emit_nubs(eli)
                    elif eli <= n_bb + n_gr + n_sh:
                        # shelf band = the bridge from the view edge to the photo
                        # edge (the photo's front stop) - same contour as the front
                        a(';TYPE:Bridge')
                        emit_ring(eli, view_c)
                    else:
                        a(';TYPE:Outer wall')
                        _fin = lip_c if lip else view_c
                        if eli <= n_bb + n_gr + n_sh + solid_ft:
                            emit_ring(eli, _fin)
                        else:
                            # R90.1b structure layer: walls only + pattern
                            emit_ring(eli, _fin, hatch=False)
                            emit_pattern(eli)
                        if front == 'IRON' and ironing and eli == frame_layers:
                            a(';TYPE:Ironing')
                            iw = _ring_hatch(outer_c, _fin, 2.4, 0.0)
                            _emit_hatch(pen, [((p[0] + cx, p[1] + cy),
                                               (q[0] + cx, q[1] + cy))
                                              for (p, q) in iw],
                                        0.15 * layer_h * wid / fil, 600)
                    a('EXCLUDE_OBJECT_END NAME=FRAME')
                # ---- backplate ----
                if want_rest and li <= bp_layers:
                    a('EXCLUDE_OBJECT_START NAME=BACKPLATE')
                    a(';TYPE:Outer wall')
                    _emit_loop(pen, [(x + bx, y + by) for (x, y) in plate_pts],
                               e_w(li), 1500 if li == 1 else 2400)
                    a(';TYPE:Internal solid infill')
                    segs = _poly_hatch([(x + bx, y + by) for (x, y) in plate_pts],
                                       wid, 45.0 if li % 2 else 135.0,
                                       keep_circles=plate_keeps(bx, by))
                    _emit_hatch(pen, segs, e_w(li), 1500 if li == 1 else 2700)
                    a('EXCLUDE_OBJECT_END NAME=BACKPLATE')
                # ---- stand ----
                if want_rest and stand_ok and li <= st_layers:
                    a('EXCLUDE_OBJECT_START NAME=STAND')
                    a(';TYPE:Outer wall')
                    leg_h = min(58.0, sh - 4.0)
                    tri = [(sx - sw / 2, sy - sh / 2), (sx + sw / 2, sy - sh / 2),
                           (sx - sw / 2, sy - sh / 2 + leg_h)]
                    _emit_loop(pen, tri, e_w(li), 1500 if li == 1 else 2400)
                    a(';TYPE:Internal solid infill')
                    _emit_hatch(pen, _poly_hatch(tri, wid, 45.0 if li % 2 else 135.0),
                                e_w(li), 1500 if li == 1 else 2700)
                    a('EXCLUDE_OBJECT_END NAME=STAND')
                if want_rest and stand_ok and st_layers < li <= st_layers + stud_layers:
                    a('EXCLUDE_OBJECT_START NAME=STAND')
                    a(';TYPE:Outer wall')
                    for sxx in (sx - 12.0, sx + 12.0):
                        _emit_loop(pen, _rect_loop(sxx - 1.1, sy - sh / 2 + 3.0,
                                                   sxx + 1.1, sy - sh / 2 + 5.4),
                                   e_w(li), 900)
                    a('EXCLUDE_OBJECT_END NAME=STAND')

            defs = []
            if want_frame:
                defs.append(('FRAME', cx, cy, ow, oh))
            if want_rest:
                defs.append(('BACKPLATE', bx, by, bw, bh))
                if stand_ok:
                    defs.append(('STAND', sx, sy, sw, sh))
            hdr = []
            for nm, px, py, pww, phh in defs:
                poly = '[[%.1f,%.1f],[%.1f,%.1f],[%.1f,%.1f],[%.1f,%.1f]]' % (
                    px - pww / 2, py - phh / 2, px + pww / 2, py - phh / 2,
                    px + pww / 2, py + phh / 2, px - pww / 2, py + phh / 2)
                hdr.append('EXCLUDE_OBJECT_DEFINE NAME=%s CENTER=%.1f,%.1f POLYGON=%s'
                           % (nm, px, py, poly))
            if not files:
                if closure == 'BACK':
                    notes.append('assembly: photo flat onto the back, then the '
                                 'backplate with its edge notches at the left/right '
                                 'nubs - drop it in and slide 2.5mm to lock')
                else:
                    notes.append('assembly: photo + cover plate slide together into '
                                 'the slot in the left wall')

    # ===================  SPLIT KIT (oversized RECT, corner 0) ==================
        else:
            # 4 butt-jointed strips, each printed FLAT as a horizontal bar
            # (a straight strip has no fixed orientation in the XY plane), one
            # per row; backplate (+ stand beside it) in the row below.
            vh_st = oh - 2 * frame_w
            # edir = which bar edge faces the frame CENTER (shelf+front bands
            # extend by the view overlap, nubs sit at the L/R inner ends)
            rows = [('STRIP_T', ow, 'ym'), ('STRIP_B', ow, 'yp'),
                    ('STRIP_L', vh_st, 'xm'), ('STRIP_R', vh_st, 'xp')]
            strip_h = 4 * frame_w + 3 * gap

            parts = []
            if want_frame:
                yy = uy0
                for nm, slen, edir in rows:
                    parts.append((nm, (ux0, yy, ux0 + slen, yy + frame_w), edir))
                    yy += frame_w + gap
            bpx, bpy, sxk, syk = 0.0, 0.0, 0.0, 0.0
            if want_rest:
                if want_frame:
                    # single kit file: plate row below the strip block
                    bpx = ux0 + bw / 2
                    bpy = uy0 + strip_h + gap + bh / 2
                    if stand_ok:
                        sxk = ux0 + bw + gap + sw / 2
                        syk = uy0 + strip_h + gap + sh / 2
                else:
                    # PLATE B: backplate bottom-left + stand beside/below it
                    bpx, bpy = ux0 + bw / 2, uy0 + bh / 2
                    if stand_ok:
                        if bw + gap + sw <= uw and max(bh, sh) <= uh:
                            sxk, syk = ux0 + bw + gap + sw / 2, uy0 + sh / 2
                        elif max(bw, sw) <= uw and bh + gap + sh <= uh:
                            sxk, syk = ux0 + sw / 2, uy0 + bh + gap + sh / 2
                        else:
                            stand_ok = False
                            sw = sh = 0.0
                            notes.append('stand skipped - no room beside the '
                                         'backplate on plate B (wall mounting '
                                         'still works)')
                    if bw > uw or bh > uh:
                        raise ValueError('backplate %.0fx%.0fmm does not fit '
                                         'the bed' % (bw, bh))
            # R96 (rule dd audit): same keep-out circles for the KIT
            # backplate (Part B): keyhole + stud holes retract-crossed.
            if want_rest:
                pen.holes = list(plate_keeps(bpx, bpy))

            # NOTE: strips carry the profile via their INNER edge position:
            #   band  back band   -> inner edge = photo opening (pw/ph)
            #   band  shelf/front -> inner edge = view opening (vw/vh)
            # For horizontal strips the inner edge is y = y0 + frame_w stays
            # constant; the OPENING size only decides whether the strip is emitted
            # as full rect (it always is - the opening is BETWEEN the strips).

            def emit_strip(li, rect):
                ew = e_w(li)
                x0, y0, x1, y1 = rect
                _emit_loop(pen, _rect_loop(x0, y0, x1, y1), ew, 1500 if li == 1 else 2400)
                a(';TYPE:Internal solid infill')
                _emit_hatch(pen, _hatch(x0 + wid, y0 + wid, x1 - wid, y1 - wid, [],
                                        wid * 100.0 / max(20.0, infill),
                                        45.0 if li % 2 else 135.0),
                            ew, 1500 if li == 1 else 2700)

            # which bands exist per strip: back band (+nubs on the T/B strips),
            # groove (nothing between strips - the whole middle is open in a kit),
            # shelf+front band. In a kit the 'groove' is simply absent: photo +
            # backplate are held by the assembled frame exactly like one piece.
            pl_total = frame_layers
            if want_rest:
                pl_total = total_layers
                if not want_frame:
                    pl_total = max(bp_layers,
                                   (st_layers + stud_layers) if stand_ok else 0)

            for li in range(1, pl_total + 1):
                z = round(first_h + (li - 1) * layer_h, 3)
                a(';LAYER_CHANGE')
                a(';Z:%.3f' % z)
                pen.set_z(z)
                if li == 2:
                    a('M106 S178   ; R2-FRAME: part fan from layer 2')
                if want_frame:
                    for nm, rect, edir in parts:
                        if li <= frame_layers:
                            a('EXCLUDE_OBJECT_START NAME=%s' % nm)
                            a(';TYPE:Outer wall')
                            eli = (frame_layers + 1 - li
                                   if front == 'FLIP' else li)
                            # shelf + front bands extend into the opening by
                            # the view overlap (the photo stop); a FRONT disc
                            # adds the capture lip to the FRONT band only -
                            # back/groove bands stay plain
                            if eli > n_bb + n_gr + n_sh:
                                ext = (pw - vw) / 2.0 + lip
                            elif eli > n_bb + n_gr:
                                ext = (pw - vw) / 2.0
                            else:
                                ext = 0.0
                            r = list(rect)
                            if ext:
                                if edir == 'ym':
                                    r[1] -= ext
                                elif edir == 'yp':
                                    r[3] += ext
                                elif edir == 'xm':
                                    r[0] -= ext
                                else:
                                    r[2] += ext
                            emit_strip(li, tuple(r))
                            if closure == 'BACK' and eli in nub_zn and                                 edir in ('xm', 'xp'):
                                # bayonet nub at the strip's inner END, lengthwise
                                # center - mini bridge, same as the one-piece frame
                                a(';TYPE:Inner wall')
                                yc = (rect[1] + rect[3]) / 2.0
                                if edir == 'xm':
                                    _emit_loop(pen, _rect_loop(rect[0] - nub_d, yc - nub_l / 2,
                                                               rect[0], yc + nub_l / 2),
                                               e_w(li), 1800)
                                else:
                                    _emit_loop(pen, _rect_loop(rect[2], yc - nub_l / 2,
                                                               rect[2] + nub_d, yc + nub_l / 2),
                                               e_w(li), 1800)
                            if front == 'IRON' and ironing                                 and eli == frame_layers:
                                a(';TYPE:Ironing')
                                _emit_hatch(pen, _hatch(r[0] + 1.0, r[1] + 1.0,
                                                        r[2] - 1.0, r[3] - 1.0, [],
                                                        2.4, 0.0),
                                            0.15 * layer_h * wid / fil, 600)
                            a('EXCLUDE_OBJECT_END NAME=%s' % nm)
                if want_rest and li <= bp_layers:
                    a('EXCLUDE_OBJECT_START NAME=BACKPLATE')
                    a(';TYPE:Outer wall')
                    _emit_loop(pen, [(x + bpx, y + bpy) for (x, y) in plate_pts],
                               e_w(li), 1500 if li == 1 else 2400)
                    a(';TYPE:Internal solid infill')
                    _emit_hatch(pen, _poly_hatch([(x + bpx, y + bpy)
                                                  for (x, y) in plate_pts],
                                                 wid, 45.0 if li % 2 else 135.0,
                                                 keep_circles=plate_keeps(bpx, bpy)),
                                e_w(li), 1500 if li == 1 else 2700)
                    a('EXCLUDE_OBJECT_END NAME=BACKPLATE')
                if want_rest and stand_ok and li <= st_layers:
                    a('EXCLUDE_OBJECT_START NAME=STAND')
                    a(';TYPE:Outer wall')
                    leg_h = min(58.0, sh - 4.0)
                    tri = [(sxk - sw / 2, syk - sh / 2), (sxk + sw / 2, syk - sh / 2),
                           (sxk - sw / 2, syk - sh / 2 + leg_h)]
                    _emit_loop(pen, tri, e_w(li), 1500 if li == 1 else 2400)
                    a(';TYPE:Internal solid infill')
                    _emit_hatch(pen, _poly_hatch(tri, wid, 45.0 if li % 2 else 135.0),
                                e_w(li), 1500 if li == 1 else 2700)
                    a('EXCLUDE_OBJECT_END NAME=STAND')
                if want_rest and stand_ok and st_layers < li <= st_layers + stud_layers:
                    a('EXCLUDE_OBJECT_START NAME=STAND')
                    a(';TYPE:Outer wall')
                    for sxx in (sxk - 12.0, sxk + 12.0):
                        _emit_loop(pen, _rect_loop(sxx - 1.1, syk - sh / 2 + 3.0,
                                                   sxx + 1.1, syk - sh / 2 + 5.4),
                                   e_w(li), 900)
                    a('EXCLUDE_OBJECT_END NAME=STAND')

            defs = [(nm, (r[0] + r[2]) / 2, (r[1] + r[3]) / 2, r[2] - r[0], r[3] - r[1])
                    for nm, r, _ed in parts]
            if want_rest:
                defs.append(('BACKPLATE', bpx, bpy, bw, bh))
                if stand_ok:
                    defs.append(('STAND', sxk, syk, sw, sh))
            hdr = []
            for nm, px, py, pww, phh in defs:
                poly = '[[%.1f,%.1f],[%.1f,%.1f],[%.1f,%.1f],[%.1f,%.1f]]' % (
                    px - pww / 2, py - phh / 2, px + pww / 2, py - phh / 2,
                    px + pww / 2, py + phh / 2, px - pww / 2, py + phh / 2)
                hdr.append('EXCLUDE_OBJECT_DEFINE NAME=%s CENTER=%.1f,%.1f POLYGON=%s'
                           % (nm, px, py, poly))
            if not files:
                notes.append('split kit: 4 strips with butt joints - glue the '
                             'corners (wood glue), then insert photo + backplate '
                             'from behind')
                if closure == 'SIDE':
                    notes.append('kit + SIDE: after gluing, cut the side slot into '
                                 'the left strip (the groove band is only ~%.1fmm '
                                 'deep - two passes with a saw knife)' % groove)

        # ---- end of plate: fan off + full END choreography (R90.1a: the old
        # files simply stopped dead - no PRINT_END, no end beeps!) --------------
        a('M107   ; R2-FRAME: plate done - fan off')
        a('PRINT_END')
        if len(plates) > 1 and sfx != plates[-1][0]:
            nxt = plates[-1][0] if sfx == plates[0][0] else plates[0][0]
            a('')
            a('RESPOND MSG="R2-FRAME: plate %s of %d done - next file: %s '
              '(NOT auto-started)"' % (sfx, len(plates), frame_fname(nxt)))
            a('M117 R2-FRAME: next -> Part %s' % nxt)
            for _k in range(len(plates)):
                a('M300 P150 S880   ; R2-FRAME: plate beep')
                a('G4 P300')

        # ---- header assembly (angles pattern) ---------------------------------
        ps = 'PRINT_START MATERIAL=%s LAYER_HEIGHT=%.2g TOTAL_LAYERS=%d OUTER_WALL_SPEED=15' % (
            material, layer_h, pl_total)
        i0 = next(i for i, l in enumerate(L) if l.startswith(';LAYER_CHANGE'))
        outl = (L[:i0] + hdr + [ps, 'G90', 'M83',
                                'M107   ; R2-FRAME: first layer = fan off']
                + _gen_markers(L[i0:]))

        fname = frame_fname(sfx)
        out = os.path.join(out_dir, fname)
        with open(out, 'w') as f:
            f.write('\n'.join(outl) + '\n')
        files.append(fname)

    info = {'file': files[0], 'mode': mode, 'shape': shape, 'preset': preset,
            'width': width, 'height': height, 'depth': depth, 'border': frame_w,
            'closure': closure, 'hang': hang, 'stand': bool(stand_ok), 'kit': kit,
            'multi': multi, 'plates': files, 'front': front,
            'disc': disc if disc != 'NONE' else '', 'disc_side': disc_side,
            'disc_t': float(disc_t) if disc != 'NONE' else 0.0,
            'cable': bool(cable and cable_box),
            'layers': total_layers, 'outer': '%.0fx%.0fmm' % (ow, oh),
            'photo_open': '%.1fx%.1fmm' % (pw, ph),
            'notes': notes + (['stand: easel-leg studs plug into the 2 backplate '
                               'holes (D2.7, 24mm apart)'] if stand_ok else [])}
    return os.path.join(out_dir, files[0]), info



def make_angles(count=2, angle_deg=90, leg_a=60.0, leg_b=60.0, width=25.0,
                layers=6, holes=2, hole_d=4.0, countersink=True, stiffener=1,
                flat=False, layer_h=0.2, first_h=0.28, material='PLA',
                bed=None, bed_margin=6.0, nozzle=0.6, out_dir='.', version=1,
                walls=2, infill=100.0, ironing=False):
    """R86: angle plates (Winkel) + flat connectors (Flachenverbinder).

    ANGLE  - flat plate, two legs at angle_deg (30..170), leg lengths a/b
             (equal legs or not), optional corner gusset rib (stiffener 1/2),
             screw holes per leg (auto-arranged, auto-clamped).
    FLAT   - straight strip joining two boards side by side (flat=True):
             both halves share the SAME hole pattern (leg_a = left half,
             leg_b = right half; set both equal for symmetry).
    Holes: diameter is clamped so a hole NEVER exceeds the leg (>=3mm edge
    all around); the count auto-reduces if the leg is too short. Countersink
    adds a stepped cone (2 layers) for flat-head screws.
    Returns (path, info).
    """
    count = max(1, min(int(count), 12))
    flat = bool(flat)
    theta = 180.0 if flat else max(30.0, min(float(angle_deg), 170.0))
    la = max(20.0, min(float(leg_a), 150.0))
    lb = max(20.0, min(float(leg_b), 150.0))
    width = float(width)
    layers = max(4, min(int(layers), 12))
    holes = max(0, min(int(holes), 6))
    layer_h = max(0.06, min(float(layer_h), 0.34))
    first_h = max(0.08, min(float(first_h), 0.42))
    # R86.2: walls (concentric loops), infill % (100 = solid), ironing pass
    walls = max(1, min(int(walls), 6))
    infill = max(20.0, min(float(infill), 100.0))
    ironing = bool(ironing)
    notes = []
    if flat:
        stiffener = 0                      # a gusset makes no sense on a strip
        if countersink is None:
            countersink = True

    # ---- hole layout (auto-clamp + auto-reduce) ---------------------------
    if not (8.0 <= width <= 60.0):
        raise ValueError('leg width %.0fmm out of range (8..60)' % width)
    edge = 3.0
    max_d = min(round(width - 2 * edge, 1), 10.0)
    if max_d < 2.0:
        raise ValueError('leg width %.0fmm too narrow for holes (needs >= 10mm)' % width)
    hole_d = round(float(hole_d), 1)
    if hole_d > max_d:
        notes.append('hole %.1fmm too big for the %.0fmm leg - clamped to %.1fmm'
                     % (hole_d, width, max_d))
        hole_d = max_d
    if hole_d < 2.0:
        hole_d = 2.0
    cs_d1 = min(round(hole_d * 1.5, 1), max_d)     # countersink step 1 (upper)
    cs_d2 = min(round(hole_d * 2.0, 1), max_d)     # countersink step 2 (top)

    def leg_holes(leg_len, leg_name):
        """hole centers along one leg's centerline (from the corner outward)"""
        if holes == 0:
            return []
        corner_clear = (4.0 if flat else width) + hole_d / 2.0 + 1.5
        end_clear = max(3.5, hole_d * 0.8)
        usable = leg_len - corner_clear - end_clear - hole_d
        n = holes
        if usable < 0:
            notes.append('%s leg too short for holes - none placed' % leg_name)
            return []
        fit = int(usable // (hole_d + 3.0)) + 1
        if n > fit:
            notes.append('%s leg: %d hole(s) do not fit - reduced to %d'
                         % (leg_name, n, fit))
            n = fit
        if n == 0:
            return []
        if n == 1:
            return [corner_clear + hole_d / 2.0 + usable / 2.0]
        step = usable / (n - 1)
        return [corner_clear + hole_d / 2.0 + i * step for i in range(n)]

    holes_a = leg_holes(la, 'A')
    holes_b = leg_holes(lb, 'B') if not flat else list(holes_a)

    if bed is None:
        bed = (0.0, -3.0, 244.0, 238.0)
    wid = max(0.4, nozzle * 1.08)
    fil = FIL_AREA
    # R86.2: the walls must fit the leg (2 x walls x line width + 4mm material)
    max_walls = max(1, int((width / 2.0 - 2.0) / wid))
    if walls > max_walls:
        notes.append('%d walls do not fit the %.0fmm leg - reduced to %d'
                     % (walls, width, max_walls))
        walls = max_walls

    # ---- geometry (local frame, later rotated per copy) --------------------
    uA = (1.0, 0.0)
    th = math.radians(theta)
    uB = (math.cos(th), math.sin(th))
    nA = (0.0, 1.0)                       # into the wedge
    nB = (math.sin(th), -math.cos(th))    # into the wedge (right normal of uB)

    if flat:
        outline = [(0.0, 0.0), (la + lb, 0.0), (la + lb, width), (0.0, width)]
        # holes: left half along uA (from 0), right half mirrored from the end
        hole_pos = []
        for d in holes_a:
            hole_pos.append((d, width / 2.0, 0.0))          # (x, y, 0)
            hole_pos.append((la + lb - d, width / 2.0, 0.0))
        item_w = la + lb + 8.0
        item_h = width + 8.0
    else:
        A2 = (la, 0.0)
        A3 = (la, width)
        # inner concave corner: intersection of the two inner edge lines
        # A inner line: y = width (dir uA); B inner line: through width*nB, dir uB
        bx, by = width * nB[0], width * nB[1]
        # solve: P = (t, width) = (bx + s*uBx, by + s*uBy)
        if abs(uB[1]) < 1e-9:
            P_in = (width, width)
        else:
            s = (width - by) / uB[1]
            P_in = (bx + s * uB[0], width)
        if not (width - 0.01 <= P_in[0] <= la and width - 0.01 <= P_in[1] <= lb + width):
            # very acute angle - clamp the corner point
            P_in = (max(width, min(P_in[0], la)), max(width, min(P_in[1], lb + width)))
        B1 = (lb * uB[0], lb * uB[1])
        B2 = (B1[0] + width * nB[0], B1[1] + width * nB[1])
        B0 = (width * nB[0], width * nB[1])
        outline = [(0.0, 0.0), A2, A3, P_in, B2, B1]
        hole_pos = []
        for d in holes_a:
            hole_pos.append((d, width / 2.0, 0.0))
        for d in holes_b:
            x, y = d * uB[0] + (width / 2.0) * nB[0], d * uB[1] + (width / 2.0) * nB[1]
            hole_pos.append((x, y, th))

    # stiffener gusset triangle (angle mode only)
    rib_layers = 0
    tri = None
    if stiffener and not flat:
        g = min(la, lb, 2.0 * width) * 0.8
        tri = [(2.0, 2.0), (g * uA[0], g * uA[1]), (g * uB[0], g * uB[1])]
        rib_layers = max(2, layers // 2) if stiffener == 1 else max(3, 2 * layers // 3)
        if stiffener == 2:
            tri2 = [(3.0, 3.0), (g * 0.6 * uA[0], g * 0.6 * uA[1]),
                    (g * 0.6 * uB[0], g * 0.6 * uB[1])]

    # ---- plate layout ------------------------------------------------------
    bx0, by0, bx1, by1 = bed
    ux0, uy0 = bx0 + bed_margin, by0 + bed_margin
    ux1, uy1 = bx1 - bed_margin, by1 - bed_margin
    # bounding box of the local geometry (angle legs may reach up-left)
    allpts = list(outline) + [(0.0, 0.0)]
    minx = min(p[0] for p in allpts)
    maxx = max(p[0] for p in allpts)
    miny = min(p[1] for p in allpts)
    maxy = max(p[1] for p in allpts)
    item_w = (maxx - minx) + 8.0
    item_h = (maxy - miny) + 8.0
    uw, uh = ux1 - ux0, uy1 - uy0
    best = None
    for cols in range(count, 0, -1):
        rr = -(-count // cols)
        gw = cols * item_w + (cols - 1) * 6.0
        gh = rr * item_h + (rr - 1) * 6.0
        if gw <= uw and gh <= uh:
            best = (cols, rr)
            break
    if best is None:
        raise ValueError('%d plates of %.0fx%.0fmm do not fit the bed'
                         % (count, item_w, item_h))
    cols, rr = best
    gw = cols * item_w + (cols - 1) * 6.0
    gh = rr * item_h + (rr - 1) * 6.0
    gx0 = ux0 + (uw - gw) / 2.0 - minx
    gy0 = uy0 + (uh - gh) / 2.0 - miny
    positions = []
    for i in range(count):
        r, c = divmod(i, cols)
        positions.append((gx0 + c * (item_w + 6.0) + 4.0, gy0 + r * (item_h + 6.0) + 4.0))

    total_layers = layers + rib_layers
    L = []
    a = L.append
    kind = 'FLAT' if flat else 'ANGLE'
    a('; R2-ANGLES generated %s plates (R86) - start it like any other file' %
      ('flat connector' if flat else 'angle'))
    a(TAG)
    a('; %d plate(s): %s %s, legs %.0f/%.0fmm, width %.0fmm, %d layers @%.2gmm, '
      'holes %d/%d x %.1fmm%s, stiffener %s, walls %d, infill %g%%, ironing %s'
      % (count, kind, ('%g deg' % theta) if not flat else '(180 straight)',
         la, lb, width, layers, layer_h, len(holes_a), len(holes_b), hole_d,
         ' CS%.1f' % cs_d2 if countersink else '',
         ('rib %d layers' % rib_layers) if tri else 'none',
         walls, infill, 'on' if ironing else 'off'))
    a('; holes: auto-arranged, diameter clamped to the leg width, count '
      'auto-reduced when the leg is too short')

    pen = _Pen(L, jump_d=6.0)
    # R95 (rule dd): the screw holes stay OPEN through every layer (incl.
    # the countersink steps) - travels across them retract at ANY length
    pen.holes = [(ox + hx, oy + hy, hole_d / 2.0 + wid * 0.6)
                 for (ox, oy) in positions for (hx, hy, _ha) in hole_pos]

    def plate_block(idx, ox, oy, li, first):
        e_wall = (first_h if li == 1 else layer_h) * wid / fil
        L.append('EXCLUDE_OBJECT_START NAME=PLATE_%d' % (idx + 1))
        plate_z = li
        in_rib = plate_z > layers
        top = plate_z >= layers - 1              # top 2 plate layers = countersink
        if in_rib and tri:
            poly = tri2 if (stiffener == 2 and plate_z > layers + rib_layers // 2) else tri
            L.append(';TYPE:Outer wall')
            _emit_loop(pen, [(ox + px, oy + py) for px, py in poly], e_wall,
                       1500 if first else 2400)
            L.append(';TYPE:Internal solid infill')
            _emit_hatch(pen, _poly_hatch([(ox + px, oy + py) for px, py in poly],
                                          wid, 45.0 if li % 2 else 135.0), e_wall,
                        1500 if first else 2700)
        else:
            L.append(';TYPE:Outer wall')
            _emit_loop(pen, [(ox + px, oy + py) for px, py in outline], e_wall,
                       1500 if first else 2400)
            # R86.2: WALLS = 1 outer + (walls-1) inner concentric loops
            wall_poly = outline
            for _k in range(1, walls):
                _npl = _inset_poly(wall_poly, wid)
                if not _npl or len(_npl) < 3:
                    break
                wall_poly = _npl
                L.append(';TYPE:Inner wall')
                _emit_loop(pen, [(ox + px, oy + py) for px, py in wall_poly], e_wall,
                           1500 if first else 2700)
            # hole walls + keep-outs
            keeps = []
            for (hx, hy, _ha) in hole_pos:
                d = hole_d
                if countersink and top:
                    d = cs_d2 if plate_z == layers else cs_d1
                keeps.append((ox + hx, oy + hy, d / 2.0 + wid * 0.6))
                L.append(';TYPE:Inner wall')
                _emit_loop(pen, _circle(ox + hx, oy + hy, d / 2.0), e_wall,
                           1500 if first else 2400)
            L.append(';TYPE:Internal solid infill')
            # R86.2: INFILL % - line spacing wid at 100 (solid), wider below;
            # the hatch runs INSIDE the walls (no overlap with the loops)
            _sp = wid * (100.0 / infill)
            _emit_hatch(pen, _poly_hatch(
                [(ox + px, oy + py) for px, py in wall_poly],
                _sp, 45.0 if li % 2 else 135.0, keep_circles=keeps), e_wall,
                1500 if first else 2700)
        # R86.2: IRONING - one slow, low-flow pass over the top surface
        # (with a rib: over the rib's top; the face around it stays as printed)
        if ironing and li == total_layers:
            _ipoly = ((tri2 if (stiffener == 2 and plate_z > layers + rib_layers // 2)
                       else tri) if (tri and in_rib) else wall_poly)
            _d_ir = (cs_d2 if countersink else hole_d)
            _kir = [(ox + hx, oy + hy, _d_ir / 2.0 + wid * 0.8)
                    for (hx, hy, _ha) in hole_pos]
            L.append(';TYPE:Ironing')
            _emit_hatch(pen, _poly_hatch(
                [(ox + px, oy + py) for px, py in _ipoly],
                max(wid * 0.8, 0.45), 90.0, keep_circles=_kir),
                0.15 * layer_h * wid / fil, 1500)
        L.append('EXCLUDE_OBJECT_END NAME=PLATE_%d' % (idx + 1))

    for li in range(1, total_layers + 1):
        z = round(first_h + (li - 1) * layer_h, 3)
        L.append(';LAYER_CHANGE')
        L.append(';Z:%.3f' % z)
        pen.set_z(z)
        if li == 2:
            L.append('M106 S178   ; R2-ANGLES: part fan from layer 2')
        for idx, (ox, oy) in enumerate(positions):
            plate_block(idx, ox, oy, li, li == 1)

    a('M107')
    a('PRINT_END')

    hdr = []
    for idx, (ox, oy) in enumerate(positions):
        # R87.2 FIELD FIX: same as the ties - POLYGON must be json
        # ([x,y] tuples, no whitespace) or Klipper aborts the print.
        pts = ','.join('[%.1f,%.1f]' % (ox + px, oy + py) for px, py in outline)
        hdr.append('EXCLUDE_OBJECT_DEFINE NAME=PLATE_%d CENTER=%.1f,%.1f POLYGON=[%s]'
                   % (idx + 1, ox + (minx + maxx) / 2.0, oy + (miny + maxy) / 2.0, pts))
    ps = 'PRINT_START MATERIAL=%s LAYER_HEIGHT=%.2g TOTAL_LAYERS=%d OUTER_WALL_SPEED=40' % (
        material, layer_h, total_layers)
    # R83 header order (labels pattern): TAG + comments, exclude defines,
    # PRINT_START, G90/M83, fan off for the first layer
    i0 = next(i for i, l in enumerate(L) if l.startswith(';LAYER_CHANGE'))
    outl = (L[:i0] + hdr + [ps, 'G90', 'M83',
                            'M107   ; R2-ANGLES: first layer = fan off']
            + _gen_markers(L[i0:]))

    if flat:
        fname = '00_Flat_%.0fx%.0f_V%02d.gcode' % (la + lb, width, max(1, min(int(version), 99)))
    else:
        fname = '00_Angle_%ddeg_%.0fx%.0f_V%02d.gcode' % (
            round(theta), la, lb, max(1, min(int(version), 99)))
    out = os.path.join(out_dir, fname)
    with open(out, 'w') as f:
        f.write('\n'.join(outl) + '\n')
    info = {'file': fname, 'count': count, 'kind': kind, 'angle': round(theta),
            'legs': (la, lb), 'width': width, 'layers': total_layers,
            'holes': '%d+%d' % (len(holes_a), len(holes_b)), 'hole_d': hole_d,
            'cs_d': cs_d2 if countersink else 0, 'stiffener': stiffener,
            'walls': walls, 'infill': infill, 'ironing': ironing,
            'grid': '%dx%d' % (cols, rr), 'notes': notes}
    return out, info


# ---- R89: lithophane + gasket generators ---------------------------------------

def _img_luma(data, kind):
    """R89: decode PNG/JPEG -> (w, h, rows of luminance 0..1)."""
    if kind == 'png':
        w, h, px = _png_to_rgb(data)
    elif kind in ('jpg', 'jpeg'):
        w, h, px = _jpeg_to_rgb(data)   # raises a clear message on progressive
    else:
        raise ValueError('unsupported image type %r (png/jpg/jpeg only)' % kind)
    if w < 8 or h < 8:
        raise ValueError('image too small (%dx%d px) - at least 8x8' % (w, h))
    lum = []
    for y in range(h):
        row = px[y]
        lr = []
        for x in range(w):
            r, g, b = row[x]
            lr.append((0.299 * r + 0.587 * g + 0.114 * b) / 255.0)
        lum.append(lr)
    return w, h, lum


def _litho_grid(lum, w, h, cols, rows, gamma=1.0, levels=0):
    """R89: the 'always beautiful without visual feedback' image pipeline.

    1. robust contrast stretch (2..98 percentiles - a dark photo or a washed
       out scan both end up using the full thickness range)
    2. gamma (optional, default neutral)
    3. box downsample with capped sampling (anti-aliasing, fast on a Pi Zero)
    4. 3x3 gaussian blur (sigma~1 cell) - single-pixel speckle would print as
       pinholes and flicker; the blur costs almost no detail at line width
       resolution
    5. optional quantization to N brightness levels (posterized look + the
       thickness changes come in clean steps = smoother walls)
    6. horizontal mirror (a lithophane is viewed against the light from the
       front face - unmirrored it would read backwards)
    Returns (grid, report) with grid[row][col] in 0..1 (0 = brightest).
    """
    ys = range(0, h, max(1, h // 90))
    xs = range(0, w, max(1, w // 90))
    sample = sorted(lum[y][x] for y in ys for x in xs)
    lo = sample[max(0, int(len(sample) * 0.02))]
    hi = sample[min(len(sample) - 1, int(len(sample) * 0.98))]
    if hi - lo < 0.02:
        lo, hi = 0.0, 1.0        # flat image - nothing to stretch
    grid = []
    for gy in range(rows):
        y0 = gy * h // rows
        y1 = max(y0 + 1, (gy + 1) * h // rows)
        sy = max(1, (y1 - y0) // 4)
        row = []
        for gx in range(cols):
            x0 = gx * w // cols
            x1 = max(x0 + 1, (gx + 1) * w // cols)
            sx = max(1, (x1 - x0) // 4)
            s = n = 0
            for y in range(y0, y1, sy):
                lr = lum[y]
                for x in range(x0, x1, sx):
                    s += lr[x]
                    n += 1
            v = (s / float(n) - lo) / (hi - lo)
            v = 0.0 if v < 0.0 else (1.0 if v > 1.0 else v)
            if gamma != 1.0:
                v = v ** gamma
            row.append(v)
        grid.append(row)
    # 3x3 gaussian (kernel 1 2 1 / 2 4 2 / 1 2 1, normalized)
    k = (1.0 / 16.0, 2.0 / 16.0)
    blur = []
    for y in range(rows):
        yp = grid[y - 1] if y > 0 else grid[0]
        yc = grid[y]
        yn = grid[y + 1] if y < rows - 1 else grid[rows - 1]
        br = []
        for x in range(cols):
            xl = x - 1 if x > 0 else 0
            xr = x + 1 if x < cols - 1 else cols - 1
            br.append((k[0] * (yp[xl] + yp[xr] + yn[xl] + yn[xr])
                       + k[1] * (yp[x] + yn[x] + yc[xl] + yc[xr])
                       + 4.0 / 16.0 * yc[x]))
        blur.append(br)
    grid = blur
    if levels >= 2:
        n1 = float(levels - 1)
        grid = [[round(v * n1) / n1 for v in row] for row in grid]
    grid = [list(reversed(r)) for r in grid]     # mirror: front view reads right
    rep = ('auto-optimize: contrast %d..%d%% stretched, smoothed, mirrored'
           % (round(lo * 100), round(hi * 100)))
    if levels >= 2:
        rep += ', %d brightness levels' % levels
    return grid, rep


class _Sink:
    """R89: streaming line sink - a lithophane runs to ~250k gcode lines,
    building one Python list would eat 40+MB on the Pi Zero (R86 RAM rule).
    Flushes every 4000 lines; _Pen only ever calls .append()."""

    def __init__(self, fh):
        self.fh = fh
        self.buf = []

    def append(self, line):
        self.buf.append(line)
        if len(self.buf) >= 4000:
            self.fh.write('\n'.join(self.buf) + '\n')
            self.buf = []

    def flush(self):
        if self.buf:
            self.fh.write('\n'.join(self.buf) + '\n')
            self.buf = []


def make_lithophane(src, height_mm=100.0, layer_h=0.12, levels=0, frame=True,
                    brim_loops=6, ironing=False, base=0.7, dyn=2.3, gamma=1.0,
                    material='PLA', bed=None, bed_margin=6.0, nozzle=0.6,
                    out_dir='.', version=1):
    """R89: photo -> lithophane g-code, printed STANDING (vertical).

    Why standing (the field recipe from itslitho/3dp.rocks research): the
    plate stands on edge, every layer is ONE thin ribbon across the bed -
    layer lines run ALONG the image, XY resolution carries the detail, no
    top-surface banding, self-supporting. Printed flat you would see every
    layer as a contour line. Each image row becomes ONE layer; the thickness
    per column prints as a zigzag of constant-width beads (front face flat,
    back face = the image). Frame = solid border at full thickness (stability
    + hides edge artifacts), brim holds the narrow base down.
    Dark = thick: brightest highlight = base, deepest shadow = base + dyn.
    """
    height_mm = max(30.0, min(float(height_mm or 100.0), 200.0))
    layer_h = max(0.08, min(float(layer_h or 0.12), 0.2))
    levels = max(0, min(int(levels or 0), 16))
    base = max(0.4, min(float(base or 0.7), 1.5))
    dyn = max(1.2, min(float(dyn or 2.3), 3.5))
    brim_loops = max(0, min(int(brim_loops or 0), 10))
    if bed is None:
        bed = (0.0, -3.0, 244.0, 238.0)
    ext = os.path.splitext(src)[1].lower().lstrip('.')
    kind = {'png': 'png', 'jpg': 'jpg', 'jpeg': 'jpg'}.get(ext)
    if kind is None:
        raise ValueError('lithophane source must be .png/.jpg/.jpeg (got %r)' % ext)
    if not os.path.isfile(src):
        raise ValueError('image not found: %s' % src)
    with open(src, 'rb') as f:
        data = f.read()
    w, h, lum = _img_luma(data, kind)

    wid = max(0.4, nozzle * 1.08)
    fil = FIL_AREA
    notes = []

    # ---- geometry: rows = layers (image height), cols follow the aspect ----
    rows = max(4, int(round(height_mm / layer_h)))
    height_real = rows * layer_h
    # image aspect -> plate width in mm -> columns at LINE WIDTH spacing
    # (each layer is one image row at layer_h; each column is one bead at wid)
    width_target = height_real * (w / float(h))
    cols = max(4, int(round(width_target / wid)))
    bx0, by0, bx1, by1 = bed
    ux0, uy0 = bx0 + bed_margin, by0 + bed_margin
    ux1, uy1 = bx1 - bed_margin, by1 - bed_margin
    max_cols = int((ux1 - ux0) // wid)
    if cols > max_cols:
        old_h = height_real
        cols = max_cols
        width_mm = cols * wid
        rows = max(4, int(round(width_mm * (h / float(w)) / layer_h)))
        height_real = rows * layer_h
        notes.append('image too wide for the bed - height clamped %.0f -> %.0fmm'
                     % (old_h, height_real))
    z_max = 235.0                      # Ender-3 build height, headroom included
    if height_real > z_max:
        old_h = height_real
        rows = max(4, int(z_max / layer_h))
        height_real = rows * layer_h
        cols = max(4, int(round(height_real * (w / float(h)) / wid)))
        notes.append('too tall - height clamped %.0f -> %.0fmm' % (old_h, height_real))
    width_mm = cols * wid

    grid, rep = _litho_grid(lum, w, h, cols, rows, gamma=gamma, levels=levels)
    notes.append(rep)

    # ---- thickness map (dark = thick) + solid frame border ------------------
    t_min = max(base, wid)
    t_max = t_min + dyn
    fw_c = max(2, int(round(2.4 / wid))) if frame else 0
    fw_r = max(2, int(round(2.4 / max(layer_h, wid)))) if frame else 0
    T = []
    for r in range(rows):
        tr = []
        for c in range(cols):
            if frame and (r < fw_r or r >= rows - fw_r or c < fw_c or c >= cols - fw_c):
                tr.append(t_max)
            else:
                tr.append(t_min + dyn * grid[r][c])
        T.append(tr)

    # ---- placement: centered, front face at fixed Y -------------------------
    cx = (ux0 + ux1) / 2.0
    x0 = cx - width_mm / 2.0
    yF = (uy0 + uy1) / 2.0 - t_max / 2.0

    stem = re.sub(r'[^A-Za-z0-9]', '', os.path.splitext(os.path.basename(src))[0])[:8] or 'IMG'
    fname = '00_Litho_%s_V%02d.gcode' % (stem, max(1, min(int(version), 99)))
    out = os.path.join(out_dir, fname)

    e_wall = layer_h * wid / fil
    e_iron = 0.15 * layer_h * wid / fil
    fpoly = '[[%.1f,%.1f],[%.1f,%.1f],[%.1f,%.1f],[%.1f,%.1f]]' % (
        x0, yF, x0 + width_mm, yF, x0 + width_mm, yF + t_max, x0, yF + t_max)

    with open(out, 'w') as f:
        sk = _Sink(f)
        a = sk.append
        a('; R2-LITHO generated lithophane (R89) - start it like any other file')
        a(TAG)
        a('; source %s (%dx%d px) -> %dx%d cells, standing print, dark = thick'
          % (os.path.basename(src), w, h, cols, rows))
        a('; plate %.1f x %.1f mm, thickness %.1f..%.1f mm, %d layers @%.2gmm'
          % (width_mm, height_real, t_min, t_max, rows, layer_h))
        a('; %s' % rep)
        a('; frame %s, brim %d loop(s), ironing %s'
          % ('ON (solid border at full thickness)' if frame else 'OFF',
             brim_loops, 'ON (top edge)' if ironing else 'OFF'))
        a('; print tips: WHITE or natural PLA glows best; slow (the file already'
          ' prints at 25mm/s); light it from BEHIND')
        a('; filament_type = %s' % material)
        a('; layer_height = %.2g' % layer_h)
        a('; nozzle_diameter = %.1f' % nozzle)
        a('; line_width = %.2g' % wid)
        a('; inner_wall_speed = 25')   # ribbon core = solid infill (R92 tags)
        a('; initial_layer_speed = 10')
        a('; travel_speed = 120')
        if ironing:
            a('; ironing_speed = 25')
            a('; ironing_flow = 0.15')
        # R92: honest feature tags - the standing litho is one solid body:
        # first layers = bottom surface, the ribbon core = solid infill,
        # the topmost layers = top surface (brim + ironing on top of that)
        types = ['SURFACE-BOTTOM', 'INFILL-SOLID', 'SURFACE-TOP'] \
            + (['IRONING'] if ironing else [])
        if brim_loops:
            types.insert(0, 'BRIM')
        a('_FILE_INFO MATERIAL=%s LAYER_HEIGHT=%.2g TOTAL_LAYERS=%d LINE_WIDTH=%.2g '
          'LINE_WIDTH_FIRST=%.2g LINE_WIDTH_WALL=%.2g FLOW_RATIO=1 NOZZLE=%.1f '
          'WALL_LOOPS=2 SPEED_INNER=25 SPEED_FIRST=10 SPEED_TRAVEL=120%s TYPES=%s BY_OBJECT=0'
          % (material, layer_h, rows, wid, layer_h, wid, nozzle,
             ' IRONING_SPEED=25' if ironing else '', ','.join(types)))
        a('EXCLUDE_OBJECT_DEFINE NAME=LITHO CENTER=%.1f,%.1f POLYGON=%s'
          % (cx, yF + t_max / 2.0, fpoly))
        ps = ('PRINT_START MATERIAL=%s LAYER_HEIGHT=%.2g TOTAL_LAYERS=%d OUTER_WALL_SPEED=25'
              % (material, layer_h, rows))
        a(ps)
        a('G90')
        a('M83')
        a('M107   ; R2-LITHO: first layer = fan off')

        pen = _Pen(sk, jump_d=6.0)

        def ribbon(li, row, feed, e_per_mm):
            """one layer = one continuous zigzag across all columns.

            State machine: at the BACK of a column (yF+t) the move to the next
            column is a short DIAGONAL along the image face (E = hypot(wid,
            dt)); at the FRONT (yF) it is a straight line (E = wid). Then the
            column prints vertically (E = t). One continuous bead, no travel
            inside the layer."""
            rev = (li % 2 == 0)                # alternate direction per layer
            rng = range(cols - 1, -1, -1) if rev else range(cols)
            first = True
            at_back = False
            pen_t = 0.0
            for c in rng:
                x = x0 + (c + 0.5) * wid
                t = T[row][c]
                if first:
                    pen.travel(x, yF, 4500)
                    pen.extrude(x, yF + t, e_per_mm * t, feed)
                    at_back = True
                    first = False
                elif at_back:
                    pen.extrude(x, yF + t, e_per_mm * math.hypot(wid, t - pen_t), feed)
                    pen.extrude(x, yF, e_per_mm * t, feed)
                    at_back = False
                else:
                    pen.extrude(x, yF, e_per_mm * wid, feed)
                    pen.extrude(x, yF + t, e_per_mm * t, feed)
                    at_back = True
                pen_t = t

        for li in range(1, rows + 1):
            z = round(li * layer_h, 3)         # uniform layers: image stays true
            row = rows - li                    # image row 0 = top = highest layer
            a(';LAYER_CHANGE')
            a(';Z:%.3f' % z)
            a('LAYER_MARK')
            # R92 feature tags: bottom layers / solid ribbon core / top layers
            if li <= 2:
                a(';TYPE:Bottom surface')
                a('APPLY_TYPE TYPE=SURFACE-BOTTOM')
            elif li > rows - 2:
                a(';TYPE:Top surface')
                a('APPLY_TYPE TYPE=SURFACE-TOP')
            else:
                a(';TYPE:Internal solid infill')
                a('APPLY_TYPE TYPE=INFILL-SOLID')
            if li == 2:
                a('M106 S178   ; R2-LITHO: part fan from layer 2')
            a('EXCLUDE_OBJECT_START NAME=LITHO')
            if li == 1 and brim_loops:
                a(';TYPE:Brim')
                a('APPLY_TYPE TYPE=BRIM')
                for k in range(brim_loops):
                    off = wid * (k + 0.5)
                    b = (x0 - off, yF - off, x0 + width_mm + off, yF + t_max + off)
                    _emit_loop(pen, _rect_loop(*b), e_wall, 900)
                # R92 fix: re-assert the layer's main type - the ribbon used
                # to keep running under TYPE=BRIM on layer 1
                a(';TYPE:Bottom surface')
                a('APPLY_TYPE TYPE=SURFACE-BOTTOM')
            ribbon(li, row, 600 if li == 1 else 1500, e_wall)
            if ironing and li == rows:
                a(';TYPE:Ironing')
                a('APPLY_TYPE TYPE=IRONING')
                ribbon(li, row, 1500, e_iron)
            a('EXCLUDE_OBJECT_END NAME=LITHO')
        a('M107')
        a('PRINT_END')
        sk.flush()

    info = {'file': fname, 'source': os.path.basename(src), 'kind': 'lithophane',
            'width': round(width_mm, 1), 'height': round(height_real, 1),
            'thickness': '%.1f..%.1f' % (t_min, t_max), 'layers': rows,
            'cols': cols, 'levels': levels, 'frame': bool(frame),
            'ironing': bool(ironing), 'notes': notes}
    return out, info


def make_seal(od=40.0, id_=20.0, height=1.2, profile='FLAT', ironing=False,
              layer_h=0.2, first_h=None, material='TPU', bed=None,
              bed_margin=6.0, nozzle=0.6, out_dir='.', version=1):
    """R89: gasket / seal ring (Dichtung) - OD/ID/height, FLAT face or with a
    center GROOVE (Nut) that splits the sealing face into two raised lips:
    less contact area = higher surface pressure = seals better on uneven
    flanges. Printed as ONE continuous spiral per band (R87.2 boss tech) -
    no seams, no travel inside the ring. TPU seals best, PETG works; print
    slow and dry (the file prints at 15mm/s after layer 1).
    """
    od = float(od)
    id_ = float(id_)
    height = float(height)
    profile = str(profile).upper()
    if profile not in ('FLAT', 'NUT', 'GROOVE'):
        profile = 'FLAT'
    groove = profile in ('NUT', 'GROOVE')
    if not (12.0 <= od <= 200.0):
        raise ValueError('OD %.0fmm out of range (12..200)' % od)
    if not (6.0 <= id_ <= 190.0):
        raise ValueError('ID %.0fmm out of range (6..190)' % id_)
    layer_h = max(0.06, min(float(layer_h or 0.2), 0.32))
    first_h = layer_h if first_h is None else max(layer_h, min(float(first_h), 0.42))
    if bed is None:
        bed = (0.0, -3.0, 244.0, 238.0)
    wid = max(0.4, nozzle * 1.08)
    fil = FIL_AREA
    r_in, r_out = id_ / 2.0, od / 2.0
    wr = r_out - r_in
    if wr < 2.0 * wid + 0.4:
        raise ValueError('ring band OD-ID=%.1fmm too narrow (need >= %.1fmm)'
                         % (2.0 * wr, 2.0 * (2.0 * wid + 0.4)))
    if groove and wr < 3.0 * wid + 0.8:
        groove = False      # band too narrow for two lips - flat fallback
    notes = []
    if profile in ('NUT', 'GROOVE') and not groove:
        notes.append('groove skipped: ring band too narrow (%.1fmm < %.1fmm) '
                     '- flat sealing face instead' % (2.0 * wr, 2.0 * (3.0 * wid + 0.8)))
    layers = max(2, int(round(height / layer_h)))
    height_real = round(first_h + (layers - 1) * layer_h, 2)
    lip = wr * 0.30 if groove else 0.0
    g_lay = 0
    if groove:
        g_depth = max(layer_h, min(0.6, height_real * 0.4))
        g_lay = max(1, int(round(g_depth / layer_h)))
        notes.append('groove: %.1fmm wide x %.2gmm deep, lips %.1fmm each'
                     % (2.0 * (wr - 2.0 * lip), g_lay * layer_h, lip))
    notes.append('height %.2gmm = %d layers @%.2gmm (first %.2gmm)'
                 % (height_real, layers, layer_h, first_h))
    notes.append('TPU seals best (slow + dry filament), PETG works; PLA only '
                 'for dry, static seals')

    bx0, by0, bx1, by1 = bed
    ux0, uy0 = bx0 + bed_margin, by0 + bed_margin
    ux1, uy1 = bx1 - bed_margin, by1 - bed_margin
    if od > min(ux1 - ux0, uy1 - uy0):
        raise ValueError('OD %.0fmm does not fit the bed' % od)
    cx, cy = (ux0 + ux1) / 2.0, (uy0 + uy1) / 2.0

    def band_pts(r0, r1, out_in=False):
        """archimedean spiral centerline from r0 to r1, spacing ~0.95*wid"""
        if r1 - r0 < wid * 0.4:
            r1 = r0 + wid * 0.4
        turns = max(1, int(math.ceil((r1 - r0) / (wid * 0.95))))
        spt = 56
        total = turns * spt
        pts = []
        for k in range(total + 1):
            frac = k / float(total)
            if out_in:
                frac = 1.0 - frac
            rr = r0 + (r1 - r0) * frac
            ang = 2.0 * math.pi * frac * turns
            pts.append((cx + rr * math.cos(ang), cy + rr * math.sin(ang)))
        return pts

    L = []
    a = L.append
    a('; R2-SEAL generated gasket ring (R89) - start it like any other file')
    a(TAG)
    a('; OD %.1f / ID %.1f / height %.2gmm, face %s'
      % (od, id_, height_real, 'GROOVE (two lips)' if groove else 'FLAT'))
    a('; one continuous spiral per band - no seam, no travel inside the ring')
    a('; %s' % ' | '.join(notes))
    a('; filament_type = %s' % material)
    a('; layer_height = %.2g' % layer_h)
    a('; nozzle_diameter = %.1f' % nozzle)
    a('; line_width = %.2g' % wid)
    a('; internal_solid_infill_speed = 15')
    a('; initial_layer_speed = 10')
    a('; travel_speed = 120')
    if ironing:
        a('; ironing_speed = 25')
        a('; ironing_flow = 0.15')
    types = ['INFILL-SOLID', 'SURFACE-TOP'] + (['IRONING'] if ironing else [])
    a('_FILE_INFO MATERIAL=%s LAYER_HEIGHT=%.2g TOTAL_LAYERS=%d LINE_WIDTH=%.2g '
      'LINE_WIDTH_FIRST=%.2g LINE_WIDTH_WALL=%.2g FLOW_RATIO=1 NOZZLE=%.1f '
      'WALL_LOOPS=2 SPEED_SOLID=15 SPEED_FIRST=10 SPEED_TRAVEL=120%s TYPES=%s BY_OBJECT=0'
      % (material, layer_h, layers, wid, first_h, wid, nozzle,
         ' IRONING_SPEED=25' if ironing else '', ','.join(types)))
    poly = '[[%.1f,%.1f],' % (cx + r_out, cy)
    for k in range(1, 16):
        ang = 2.0 * math.pi * k / 16.0
        poly += '[%.1f,%.1f]%s' % (cx + r_out * math.cos(ang),
                                   cy + r_out * math.sin(ang),
                                   ',' if k < 15 else '')
    poly += ']'
    a('EXCLUDE_OBJECT_DEFINE NAME=SEAL CENTER=%.1f,%.1f POLYGON=%s' % (cx, cy, poly))
    a('PRINT_START MATERIAL=%s LAYER_HEIGHT=%.2g TOTAL_LAYERS=%d OUTER_WALL_SPEED=15'
      % (material, layer_h, layers))
    a('G90')
    a('M83')
    a('M107   ; R2-SEAL: first layer = fan off')

    pen = _Pen(L, jump_d=6.0)

    def spiral_band(r0, r1, e, feed, flip=False):
        _emit_loop(pen, band_pts(r0, r1, out_in=flip), e, feed, close=False)

    for li in range(1, layers + 1):
        z = round(first_h + (li - 1) * layer_h, 3)
        a(';LAYER_CHANGE')
        a(';Z:%.3f' % z)
        a('LAYER_MARK')
        a(';TYPE:Internal solid infill')
        a('APPLY_TYPE TYPE=INFILL-SOLID')
        if li == 2:
            a('M106 S178   ; R2-SEAL: part fan from layer 2')
        a('EXCLUDE_OBJECT_START NAME=SEAL')
        e_wall = (first_h if li == 1 else layer_h) * wid / fil
        feed = 600 if li == 1 else 900
        flip = (li % 2 == 0)
        in_groove = groove and li > layers - g_lay
        # R96 (rule dd audit): the ring's center hole is open through every
        # layer. In the GROOVE layers the annulus between the lips prints
        # NOTHING (that IS the sealing groove) - every travel there (the
        # band->band hop, the layer seam, the ironing pass) crosses the open
        # groove and drags a string across it = a leak path, so the whole
        # groove disc retracts. FLAT rings only ever see zero-length layer
        # seams - nothing crosses, the registration is a pure guard.
        pen.holes = [(cx, cy, r_in)]
        if in_groove:
            pen.holes.append((cx, cy, r_out - wid / 2.0))
        if in_groove:
            spiral_band(r_in + wid / 2.0, r_in + lip - wid / 2.0, e_wall, feed, flip)
            spiral_band(r_out - lip + wid / 2.0, r_out - wid / 2.0, e_wall, feed, not flip)
        else:
            spiral_band(r_in + wid / 2.0, r_out - wid / 2.0, e_wall, feed, flip)
        if ironing and li == layers:
            a(';TYPE:Ironing')
            a('APPLY_TYPE TYPE=IRONING')
            e_ir = 0.15 * layer_h * wid / fil
            if groove:
                spiral_band(r_in + wid / 2.0, r_in + lip - wid / 2.0, e_ir, 1500, False)
                spiral_band(r_out - lip + wid / 2.0, r_out - wid / 2.0, e_ir, 1500, True)
            else:
                spiral_band(r_in + wid / 2.0, r_out - wid / 2.0, e_ir, 1500, False)
        a('EXCLUDE_OBJECT_END NAME=SEAL')
    a('M107')
    a('PRINT_END')

    fname = '00_Seal_%.0fx%.0fx%.2g_V%02d.gcode' % (
        od, id_, height_real, max(1, min(int(version), 99)))
    out = os.path.join(out_dir, fname)
    with open(out, 'w') as f:
        f.write('\n'.join(L) + '\n')
    info = {'file': fname, 'kind': 'seal', 'od': od, 'id': id_,
            'height': height_real, 'layers': layers,
            'profile': 'GROOVE' if groove else 'FLAT', 'ironing': bool(ironing),
            'notes': notes}
    return out, info


# ---- R84: slicer + firmware target detection --------------------------------
_SLICER_NAMES = [
    ('orcaslicer', 'OrcaSlicer'), ('prusaslicer', 'PrusaSlicer'),
    ('superslicer', 'SuperSlicer'), ('bambu', 'Bambu Studio'),
    ('kiri', 'Kiri:Moto'), ('astroprint', 'AstroPrint'),
    ('slicebeam', 'SliceBeam'), ('elegoo', 'Elegoo Slicer'),
    ('ideaemaker', 'ideaMaker'), ('simplify3d', 'Simplify3D'),
    ('flashprint', 'FlashPrint'), ('flashforge', 'FlashPrint'),
    ('cura', 'Cura'),
]


def _detect_slicer(path):
    """R84: which slicer wrote this file, and for which firmware flavor?

    Scans the header (first 128 KB) + the tail (last 64 KB, where the
    PrusaSlicer/Orca family embeds its config as comments). Cheap on any
    file size. Returns {'slicer': 'OrcaSlicer 2.2.0' or '', 'fw': 'Klipper'
    or '', 'volumetric': bool} - Marlin-volumetric files count E in mm3,
    which Klipper does NOT understand (it expects mm) -> warning upstream.
    """
    out = {'slicer': '', 'fw': '', 'volumetric': False}
    try:
        with open(path, 'r', errors='replace') as f:
            txt = f.read(131072)
        size = os.path.getsize(path)
        if size > 131072:
            with open(path, 'rb') as f:
                f.seek(max(0, size - 65536))
                txt += '\n' + f.read().decode('utf-8', 'replace')
    except OSError:
        return out
    name = ver = ''
    m = (re.search(r'(?im)^\s*;\s*generated by\s+([A-Za-z0-9:_.\- ]+?)\s+v?(\d[\w.\-]*)?', txt)
         or re.search(r'(?im)^\s*;\s*generated with\s+([A-Za-z0-9:_.\- ]+?)\s+v?(\d[\w.\-]*)?', txt)
         or re.search(r'(?im)^\s*;\s*sliced (?:by|with)\s+([A-Za-z0-9:_.\- ]+?)\s+v?(\d[\w.\-]*)?', txt))
    if m:
        name, ver = m.group(1).strip(' -_'), (m.group(2) or '')
        low = name.lower().replace('_', ' ')
        for key, nice in _SLICER_NAMES:
            if key in low:
                name = nice
                break
        if name:
            out['slicer'] = (name + (' ' + ver if ver else ''))[:28]
    fw = ''
    m = re.search(r'(?im)^\s*;\s*flavor\s*:\s*(.+?)\s*$', txt)
    if m:
        fw = m.group(1).strip()
    else:
        m = re.search(r'(?im)^\s*;\s*gcode_flavor\s*=\s*([A-Za-z_\-]+)\s*$', txt)
        if m:
            v = m.group(1).lower()
            fw = {'klipper': 'Klipper', 'marlin': 'Marlin', 'reprap': 'RepRap'}.get(v, v.capitalize())
    if fw:
        if 'volumetric' in fw.lower():
            out['volumetric'] = True
            fw = fw.split('(')[0].strip()
        out['fw'] = fw[:16]
    if re.search(r'(?im)^\s*;\s*use_volumetric_e\s*=\s*1', txt):
        out['volumetric'] = True
        if not out['fw']:
            out['fw'] = 'Marlin'
    return out


class _RetractFix:
    """R84: turn explicit slicer retracts into G10/G11 (firmware retraction)
    so the CURRENT extruder settings (and the live retract overrides) apply.

    Only CLEAN pairs are converted: a pure E-only retract, a few pure
    travel/hop lines, then a pure E-only unretract of about the same length.
    Everything else (wipes with XY+E, folded unretracts inside the next print
    move, primes) passes through UNTOUCHED - a half-converted stream would
    extrude wrong amounts. Held lines are ALWAYS emitted unchanged on abort.
    """

    def __init__(self):
        self.mode = 'abs'          # M82 default (slicers state it anyway)
        self.last_e = 0.0
        self.held = None           # {'lines': [...], 'mag': retract magnitude}
        self.pairs = 0
        self.aborted = 0

    @staticmethod
    def _parse(line):
        """(e_val, pure) for G1/G0 lines that carry E - pure = only E/F words."""
        m = re.match(r'^\s*G[01]\s+(\S.*)$', line)
        if not m:
            return None, False
        e = None
        pure = True
        for tok in m.group(1).split():
            t0 = tok[0].upper()
            if t0 == 'E' and len(tok) > 1:
                try:
                    e = float(tok[1:])
                except ValueError:
                    return None, False
            elif t0 == 'F':
                continue
            else:
                pure = False
        return e, (pure and e is not None)

    def _take_held(self):
        lines = self.held['lines'] if self.held else []
        self.held = None
        return lines

    def feed(self, line):
        """returns the list of lines to emit for this input line"""
        ls = line.strip()
        m = re.match(r'^\s*(M83|M82)\b', ls)
        if m:
            out = self._take_held()
            self.mode = 'rel' if m.group(1) == 'M83' else 'abs'
            return out + [line]
        m = re.match(r'^\s*G92\s+E(-?[\d.]+)', ls)
        if m:
            out = self._take_held()
            self.last_e = float(m.group(1))
            return out + [line]
        if ls.startswith(('G10', 'G11')):
            return self._take_held() + [line]
        e, pure = self._parse(line)
        if e is None:
            if self.held and re.match(r'^\s*G[01]\b', ls):
                # a move without E while holding: hop/travel -> buffer it
                self.held['lines'].append(line)
                if len(self.held['lines']) > 10:
                    return self._take_held()
                return []
            return self._take_held() + [line]
        if not pure:
            # E together with X/Y/Z: print move or wipe. If we hold a
            # retract the slicer FOLDED the unretract into it -> abort,
            # the original lines stay byte-for-byte
            out = self._take_held()
            if out:
                self.aborted += 1
            if self.mode == 'abs':
                self.last_e = e
            return out + [line]
        # pure E-only move
        if self.mode == 'rel':
            delta = e
        else:
            delta = e - self.last_e
            self.last_e = e
        if self.held:
            mag = self.held['mag']
            if delta > 0 and 0.65 <= delta / max(mag, 1e-6) <= 1.45:
                self.pairs += 1
                # retract line -> G10, hops/travels stay, unretract -> G11
                held_lines = self.held['lines']
                self.held = None
                return ['G10\n'] + held_lines[1:] + ['G11\n']
            # not the matching unretract: emit the held lines unchanged
            out = self._take_held()
            if delta < 0:
                self.held = {'lines': [line], 'mag': -delta}
                return out
            return out + [line]
        if delta < 0:
            self.held = {'lines': [line], 'mag': -delta}
            return []
        # pure positive without a held retract: a PRIME - never touch it
        return [line]

    def close(self):
        return self._take_held()


def _patch_info_retract(path, style):
    """R89: set/replace RETRACT=<style> in a file's _FILE_INFO line (streamed
    in-place, one pass). Used after the retract fix so a TAGGED file (process()
    skips those) also reports the new state to the preview/LCD."""
    tmp = path + '.riq'
    hit = False
    with open(path, 'r', errors='replace') as fi, open(tmp, 'w') as fo:
        for raw in fi:
            if not hit and raw.startswith('_FILE_INFO'):
                line = raw.rstrip('\n')
                if 'RETRACT=' in line:
                    line = re.sub(r'RETRACT=\w+', 'RETRACT=%s' % style, line)
                else:
                    line = line + ' RETRACT=%s' % style
                fo.write(line + '\n')
                hit = True
            else:
                fo.write(raw)
    if hit:
        os.replace(tmp, path)
    else:
        try:
            os.remove(tmp)
        except OSError:
            pass
    return hit


def _retract_rewrite_file(path):
    """R84: stream-rewrite a file's retract pairs to G10/G11 in place.
    Returns (pairs, aborted). Memory stays O(1) - safe for 30MB+ files."""
    rf = _RetractFix()
    tmp = path + '.rfx'
    pairs = aborted = 0
    with open(path, 'r', errors='replace') as fi, open(tmp, 'w') as fo:
        for raw in fi:
            for l in rf.feed(raw if raw.endswith('\n') else raw + '\n'):
                fo.write(l)
        for l in rf.close():
            fo.write(l)
        pairs, aborted = rf.pairs, rf.aborted
        if pairs:
            # R89: the marker makes process() report RETRACT=fixed (the file
            # info + LCD show 'already fixed' instead of offering again)
            fo.write('\n; R2-RETRACTFIX: %d retract pair(s) rewritten to G10/G11 '
                     '- your CURRENT retraction (overrides/live) applies\n' % pairs)
    if pairs:
        os.replace(tmp, path)
    else:
        try:
            os.remove(tmp)
        except OSError:
            pass
    return pairs, aborted


def _volumetric_convert_file(path, diameter=0.0):
    """R85: convert a Marlin-volumetric file (E in mm3) to Klipper mm.

    Divides every G0/G1 E value and every G92 E value by the filament
    cross-section area (default 1.75mm -> 2.405 mm2), neutralizes the
    volumetric markers (;FLAVOR:...(Volumetric), use_volumetric_e = 1,
    _FILE_INFO VOLUMETRIC=1) and prepends a conversion note. Idempotent: a
    file that no longer LOOKS volumetric is returned untouched (0, area).
    Streamed - O(1) memory, safe for 30MB+ files.
    """
    if not _detect_slicer(path)['volumetric']:
        return 0, 0.0
    if diameter <= 0:
        diameter = 1.75
    area = math.pi * (diameter / 2.0) ** 2
    ge = re.compile(r'^(\s*G[01][^;]*?\bE)(-?\d+\.?\d*)(.*)$')
    g92 = re.compile(r'^(\s*G92\s+[^;]*?\bE)(-?\d+\.?\d*)(.*)$')
    note = '; R85 VOL-CONV: E divided by %.4f mm2 (Marlin volumetric mm3 -> Klipper mm)' % area
    n = 0
    tmp = path + '.vfx'
    with open(path, 'r', errors='replace') as fi, open(tmp, 'w') as fo:
        fo.write(note + '\n')
        for raw in fi:
            line = raw[:-1] if raw.endswith('\n') else raw
            ls = line.strip()
            if ls.startswith(';'):
                low = ls.lower()
                if 'flavor:' in low and 'volumetric' in low:
                    base = ls.split(':', 1)[1].split('(')[0].strip()
                    line = ';FLAVOR:%s  (R85: E in mm)' % base
                elif low.startswith('; use_volumetric_e'):
                    line = '; use_volumetric_e = 0  (R85 converted)'
                fo.write(line + '\n')
                continue
            if ls.startswith('_FILE_INFO') and 'VOLUMETRIC=1' in ls:
                fo.write(line.replace('VOLUMETRIC=1', 'VOLUMETRIC=0') + '\n')
                continue
            m = g92.match(line)
            if m:
                fo.write('%s%.5f%s\n' % (m.group(1), float(m.group(2)) / area, m.group(3)))
                n += 1
                continue
            m = ge.match(line)
            if m:
                fo.write('%s%.5f%s\n' % (m.group(1), float(m.group(2)) / area, m.group(3)))
                n += 1
                continue
            fo.write(line + '\n')
    os.replace(tmp, path)
    return n, area


def process(path, dry=False, verbose=False, retract_rewrite=False):
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
               'layers': 0, 'method': None, 'types': 0, 'upgraded': False, 'upgraded_from': 'v1',
               'retract_pairs': 0}
    # R84: Bowden-era rescue - rewrite explicit retracts to G10/G11 BEFORE the
    # normal processing so the current extruder's retraction applies
    if retract_rewrite and not dry:
        try:
            summary['retract_pairs'], _ab = _retract_rewrite_file(path)
        except OSError as e:
            print(f'[retractfix] {path}: {e!r}', flush=True)

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
    # R89: retraction style - gates the Bowden rescue offer (field log .72:
    # the fix hint showed even on Orca files WITH firmware retraction on)
    fw_ret = 0              # bare G10/G11 = firmware retraction in effect
    slicer_ret = 0          # E-only G1 retracts = slicer moves (fix target)
    fixed_mark = False      # '; R2-RETRACTFIX' = already rewritten by us
    e_rel = False           # M83 seen?
    e_run = 0.0             # running absolute E (M82 world)
    eret_re = re.compile(r'G1\s+E(-?\d+(?:\.\d+)?)(?:\s+F\d+(?:\.\d+)?)?\s*$')

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
            # ---- R89: retraction style counters -----------------------------
            if ls == 'G10' or ls == 'G11':
                fw_ret += 1
            elif ls.startswith('; R2-RETRACTFIX'):
                fixed_mark = True
            elif ls == 'M82':
                e_rel = False
            elif ls == 'M83':
                e_rel = True
            else:
                m = eret_re.match(ls)
                if m:
                    ev = float(m.group(1))
                    if e_rel:
                        if ev < -0.05:
                            slicer_ret += 1
                    elif ev < e_run - 0.05:
                        slicer_ret += 1
                if not e_rel:
                    m = re.match(r'G9?[12]\b[^;]*?\bE(-?\d+(?:\.\d+)?)', ls)
                    if m:
                        e_run = float(m.group(1))
                    elif ls.startswith('G92'):
                        m = EWORD_RE.search(ls)
                        if m:
                            try:
                                e_run = float(m.group(1))
                            except ValueError:
                                pass
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
    # R84: who sliced this, for which firmware (from the file's own comments)
    det84 = _detect_slicer(path)
    if det84['slicer']:
        info.append('SLICER=' + re.sub(r'\s+', '_', det84['slicer']))
    if det84['fw']:
        info.append('FW=' + re.sub(r'[^A-Za-z0-9]', '', det84['fw']))
    if det84['volumetric']:
        info.append('VOLUMETRIC=1')
    # R89: retraction style - 'fw' (G10/G11: the current retraction applies,
    # no fix needed) / 'fixed' (already rewritten by the R84 rescue) /
    # 'slicer' (explicit E retracts - THE case the fix is made for) / ''
    # (nothing detected - old files, keep the offer hidden)
    if fixed_mark:
        retract_style = 'fixed'
    elif fw_ret > 0:
        retract_style = 'fw'
    elif slicer_ret >= 2:
        retract_style = 'slicer'
    else:
        retract_style = ''
    if retract_style:
        info.append('RETRACT=' + retract_style)
    summary['retract_style'] = retract_style
    summary['retract_slicer_moves'] = slicer_ret
    summary['slicer'] = det84['slicer']
    summary['fw'] = det84['fw']
    summary['volumetric'] = det84['volumetric']
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
    # R84: slicer + firmware target - files WITHOUT an _FILE_INFO line (foreign
    # slicers, old downloads) get the detection too, so the file info always
    # shows who made the file and what it expects
    if 'SLICER' not in info:
        det = _detect_slicer(path)
        if det['slicer']:
            info['SLICER'] = re.sub(r'\s+', '_', det['slicer'])
        if det['fw']:
            info['FW'] = re.sub(r'[^A-Za-z0-9]', '', det['fw'])
        if det['volumetric']:
            info['VOLUMETRIC'] = '1'
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


class _SkipHandler(Exception):
    """R89: handler decided everything itself - exit the try block quietly."""



def file_check_scan(directory):
    """R93: version census over every .gcode in DIRECTORY.

    Streams only each file's header (~120 lines) - the tag line, plotter
    marker and _FILE_INFO all live at the top. Returns (rows, totals):
    every row is {'name', 'status', 'age', 'size', 'gen', 'tex'} with
    status CURRENT (tag v4) / OLD (v1-v3, upgradeable in place) /
    PLOT (pen-plotter file - never tagged, fine) / UNTOUCHED (never
    processed: fresh upload from before the system existed or a foreign
    file). Pure read - nothing is modified.
    """
    rows = []
    now = time.time()
    for name in sorted(os.listdir(directory)):
        if not name.lower().endswith('.gcode'):
            continue
        p = os.path.join(directory, name)
        if not os.path.isfile(p):
            continue
        st = os.stat(p)
        head = []
        try:
            with open(p, errors='replace') as f:
                for i, line in enumerate(f):
                    head.append(line)
                    if i > 120:
                        break
        except OSError:
            continue
        h = ''.join(head)
        if 'R2-PLOT' in h[:2048]:
            status = 'PLOT'
        elif TAG in h:
            status = 'CURRENT'
        elif any(t in h for t in OLD_TAGS):
            status = 'OLD'
        else:
            status = 'UNTOUCHED'
        rows.append({'name': name, 'status': status,
                     'age': int(max(0, (now - st.st_mtime)) // 86400),
                     'size': st.st_size / 1e6,
                     'gen': name.startswith('00_'),
                     'tex': '; R2-TEXTURE' in h})
    totals = {'files': len(rows),
              'current': sum(1 for r in rows if r['status'] == 'CURRENT'),
              'old': sum(1 for r in rows if r['status'] == 'OLD'),
              'untouched': sum(1 for r in rows if r['status'] == 'UNTOUCHED'),
              'plot': sum(1 for r in rows if r['status'] == 'PLOT')}
    return rows, totals


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

    def file_fix(kind, name):
        """R85: fix a file IN PLACE - no re-upload (LCD: Pre-Print > File >
        RetFix file / Vol->mm fix queues itself via a save_variables nonce).
        Sound protocol: r2_confirm comes from the macro (start), this end
        reports with r2_done / r2_notice / r2_error."""
        if not name:
            _moonraker_gcode('RESPOND MSG="File fix: no file selected"\n'
                             'M117 Fix: no file\n_SOUND_LIB NAME=r2_error')
            return
        rel = name.strip().lstrip('/')
        p = os.path.join(directory, rel)
        if not os.path.isfile(p):
            _moonraker_gcode('RESPOND MSG="File fix: %s not found"\n'
                             'M117 Fix: no file\n_SOUND_LIB NAME=r2_error' % rel)
            return
        # never touch a file while a print runs (the macro released the
        # start dialog before queueing - this catches console races)
        try:
            st = _moonraker_status()
            if (st.get('print_stats') or {}).get('state') in ('printing', 'paused'):
                _moonraker_gcode('RESPOND MSG="File fix: blocked - a print is '
                                 'running"\nM117 Fix: printing\n_SOUND_LIB NAME=r2_error')
                return
        except Exception:                                   # noqa: BLE001
            pass          # status unknown - the macro side already guarded
        try:
            base = os.path.basename(rel)
            if kind == 'retract':
                with open(p, 'r', errors='replace') as f:
                    tagged = TAG in f.read(8192)
                if tagged:
                    # R2 markers survive the rewrite (they are no G0/G1-E
                    # lines) - no re-processing, no re-upload needed
                    pairs, aborted = _retract_rewrite_file(p)
                    if pairs:
                        _patch_info_retract(p, 'fixed')
                    extra = ''
                else:
                    sm = process(p, retract_rewrite=True)
                    pairs = sm.get('retract_pairs', 0)
                    extra = ' (+R2 markers added)'
                if pairs:
                    msg = ('Retract fix DONE: %d pair(s) rewritten to G10/G11 in '
                           '%s%s - your CURRENT retraction now applies'
                           % (pairs, base, extra))
                    snd = 'r2_done'
                else:
                    msg = ('Retract fix: no clean retract pairs in %s '
                           '(G10/G11 already, or wipes only) - nothing changed'
                           % base)
                    snd = 'r2_notice'
                _moonraker_gcode('RESPOND MSG="%s"\nM117 RetFix done\n'
                                 '_SOUND_LIB NAME=%s' % (msg, snd))
                print(f'[retractfix] {rel}: {msg}', flush=True)
            else:
                n, area = _volumetric_convert_file(p)
                if n:
                    msg = ('Volumetric fix DONE: %d E value(s) divided by %.3f mm2 '
                           'in %s - Klipper-ready (select the file anew)'
                           % (n, area, os.path.basename(rel)))
                    snd = 'r2_done'
                else:
                    msg = ('Volumetric fix: %s is not volumetric - nothing to do'
                           % os.path.basename(rel))
                    snd = 'r2_notice'
                _moonraker_gcode('RESPOND MSG="%s"\nM117 VolFix done\n'
                                 '_SOUND_LIB NAME=%s' % (msg, snd))
                # refresh the LCD preview so the file info drops the warning
                try:
                    _moonraker_gcode('\n'.join(_preview_script(p)))
                except Exception:                           # noqa: BLE001
                    pass
                print(f'[volfix] {rel}: {msg}', flush=True)
        except Exception as e:                              # noqa: BLE001
            _moonraker_gcode('RESPOND MSG="File fix ERROR: %s"\n'
                             'M117 Fix error\n_SOUND_LIB NAME=r2_error' % e)
            print(f'[filefix] {rel}: {e!r}', flush=True)

    def data_head_if_text(p):
        try:
            with open(p, 'rb') as f:
                return f.read(2048)
        except OSError:
            return b''

    def scan(rrw=False):
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
                    s = process(p, retract_rewrite=rrw)
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
                          + (f' [retract-fix: {s["retract_pairs"]} pair(s) -> G10/G11]'
                             if s.get('retract_pairs') else '')
                          + (f' [sliced by {s.get("slicer", "")} for {s.get("fw", "?")}]'
                             if s.get('slicer') else '')
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
    last_cable_tie_nonce = None
    last_angle_nonce = None
    last_litho_nonce = None          # R89: lithophane / seal / image-delete
    last_seal_nonce = None
    last_frame_nonce = None         # R90: picture frame / display case
    last_texture_nonce = None       # R91: fuzzy skin / bumps on an existing file
    last_file_check_nonce = None   # R93: file version census / retag
    last_litho_del_nonce = None
    pushed_images = None             # R89: last image list pushed to the LCD
    last_fit_nonce = None
    last_retract_fix_nonce = None
    last_vol_fix_nonce = None
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
            rrw = str(rv.get('retract_rewrite', '')).strip().lower() in ('true', '1', 'on', 'yes')
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
                last_cable_tie_nonce = _np.get('cable_tie_nonce')
                last_angle_nonce = _np.get('angle_nonce')
                last_fit_nonce = _np.get('label_fit_nonce')
                last_retract_fix_nonce = _np.get('retract_fix_nonce')
                last_vol_fix_nonce = _np.get('vol_fix_nonce')
                last_reso_nonce = _np['reso_nonce']
                last_bridge_nonce = _np['bridge_nonce']
                last_plottext_nonce = _np['plot_text_nonce']
                last_plotstatus_nonce = _np['plot_status_nonce']
                last_host_nonce = _np['host_nonce']
                last_litho_nonce = _np.get('litho_nonce')       # R89
                last_seal_nonce = _np.get('seal_nonce')
                last_frame_nonce = _np.get('frame_nonce')    # R90
                last_texture_nonce = _np.get('texture_nonce')   # R91
                last_file_check_nonce = _np.get('file_check_nonce')  # R93
                last_litho_del_nonce = _np.get('litho_del_nonce')
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
                # R86.2: centered floor/cap holes (mm, 0 = off)
                try:
                    rfh = float(rv.get('range_floor_hole', 0) or 0)
                except (TypeError, ValueError):
                    rfh = 0.0
                try:
                    rth = float(rv.get('range_top_hole', 0) or 0)
                except (TypeError, ValueError):
                    rth = 0.0
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
                                                 floor_hole=rfh, top_hole=rth,
                                                 version=_gv62)
                            print(f'[range] {os.path.basename(out)}: layers {rs}..{re_} ({nl} layers, '
                                  f'floor {rflo} {rfs}/{rff}, top {rtop} {rts}/{rtf}, '
                                  f'brim {rbrim}, holes f{rfh:g}/t{rth:g}mm)', flush=True)
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

        # R85: direct file fixes - no re-upload. The macro (FIX_FILE)
        # released the start dialog and queued the file + nonce.
        try:
            rfn85 = rv.get('retract_fix_nonce', '')
            if rfn85 and rfn85 != last_retract_fix_nonce:
                last_retract_fix_nonce = rfn85
                file_fix('retract', str(rv.get('retract_fix_file', '')).strip())
        except Exception as e:                              # noqa: BLE001
            print(f'[retractfix] poll error: {e!r}', flush=True)
        try:
            vfn85 = rv.get('vol_fix_nonce', '')
            if vfn85 and vfn85 != last_vol_fix_nonce:
                last_vol_fix_nonce = vfn85
                file_fix('vol', str(rv.get('vol_fix_file', '')).strip())
        except Exception as e:                              # noqa: BLE001
            print(f'[volfix] poll error: {e!r}', flush=True)

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
                        bed=cfg_bed, nozzle=_gen_nozzle(directory), out_dir=directory,
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

        # R86: cable-tie generator request (cable_tie_nonce bumps per job)
        try:
            tn = rv.get('cable_tie_nonce', '')
            if tn and tn != last_cable_tie_nonce:
                last_cable_tie_nonce = tn
                try:
                    def _vbt(key, dflt):
                        v = str(rv.get(key, dflt)).strip().lower()
                        if v == '':
                            return dflt
                        return v in ('true', '1', 'on', 'yes')

                    def _vft(key, dflt):
                        try:
                            return float(rv.get(key, dflt) or dflt)
                        except (TypeError, ValueError):
                            return float(dflt)

                    cfg_bed = _bed_limits(os.path.join(
                        os.path.dirname(os.path.abspath(directory).rstrip('/')),
                        'config', 'printer.cfg'))
                    variant_t = str(rv.get('tie_variant', 'CLASSIC') or 'CLASSIC').upper()
                    if variant_t not in ('CLASSIC', 'LOOP'):
                        variant_t = 'CLASSIC'
                    out_t, info_t = make_cable_ties(
                        count=max(1, min(int(_vft('tie_count', 6)), 24)),
                        length=_vft('tie_length', 120),
                        width=_vft('tie_width', 8),
                        layers=max(3, min(int(_vft('tie_layers', 3)), 6)),
                        variant=variant_t,
                        layer_h=_vft('tie_layer_h', 0.2),
                        brim=_vbt('tie_brim', True),
                        material=str(rv.get('material', 'PLA') or 'PLA'),
                        bed=cfg_bed, nozzle=_gen_nozzle(directory), out_dir=directory,
                        version=max(1, min(int(_vft('gen_version', 1)), 99)))
                    _rel86t = os.path.relpath(
                        os.path.join(directory, info_t['file']), directory)
                    _msg86t = ('Ties: %s - %d tie(s), %s, strap %.0fx%.0fmm, '
                               '%d layers, head %s (auto), %s - selected for printing'
                               % (info_t['file'], info_t['count'], info_t['variant'],
                                  info_t['length'], info_t['width'], info_t['layers'],
                                  info_t['head'],
                                  'reusable ball-loop (beads)' if info_t['variant'] == 'LOOP'
                                  else 'classic one-way pawl'))
                    for _note86t in info_t.get('notes', []):
                        _msg86t += ' | ' + _note86t
                    try:
                        _moonraker_gcode(
                            'RESPOND MSG="%s"\n'
                            'M117 Ties ready\n'
                            '_SOUND_LIB NAME=r2_done\n'
                            '_SELECT_FILE FILE="%s"' % (_msg86t, _rel86t))
                    except Exception as me:                      # noqa: BLE001
                        print(f'[ties] moonraker unreachable ({me.__class__.__name__})',
                              flush=True)
                    print(f'[ties] {info_t["file"]}: {info_t["count"]} tie(s), '
                          f'{info_t["variant"]}, grid {info_t["grid"]}, '
                          f'{info_t["layers"]} layers', flush=True)
                except Exception as e:                          # noqa: BLE001
                    print(f'[ties] error: {e}', flush=True)
                    try:
                        _moonraker_gcode(
                            'RESPOND MSG="Ties ERROR: %s"\nM117 Tie error\n'
                            '_SOUND_LIB NAME=r2_error' % e)
                    except Exception:                           # noqa: BLE001
                        pass
        except Exception as e:                              # noqa: BLE001
            print(f'[ties] poll error: {e!r}', flush=True)

        # R86: angle-plate / flat-connector generator (angle_nonce bumps per job)
        try:
            an = rv.get('angle_nonce', '')
            if an and an != last_angle_nonce:
                last_angle_nonce = an
                try:
                    def _vba(key, dflt):
                        v = str(rv.get(key, dflt)).strip().lower()
                        if v == '':
                            return dflt
                        return v in ('true', '1', 'on', 'yes')

                    def _vfa(key, dflt):
                        try:
                            return float(rv.get(key, dflt) or dflt)
                        except (TypeError, ValueError):
                            return float(dflt)

                    cfg_bed = _bed_limits(os.path.join(
                        os.path.dirname(os.path.abspath(directory).rstrip('/')),
                        'config', 'printer.cfg'))
                    out_a, info_a = make_angles(
                        count=max(1, min(int(_vfa('angle_count', 2)), 12)),
                        angle_deg=_vfa('angle_deg', 90),
                        leg_a=_vfa('angle_leg_a', 60),
                        leg_b=_vfa('angle_leg_b', 60),
                        width=_vfa('angle_width', 25),
                        layers=max(4, min(int(_vfa('angle_layers', 6)), 12)),
                        holes=max(0, min(int(_vfa('angle_holes', 2)), 6)),
                        hole_d=_vfa('angle_hole_d', 4.0),
                        countersink=_vba('angle_countersink', True),
                        stiffener=max(0, min(int(_vfa('angle_stiffener', 1)), 2)),
                        walls=max(1, min(int(_vfa('angle_walls', 2)), 6)),
                        infill=max(20.0, min(_vfa('angle_infill', 100.0), 100.0)),
                        ironing=_vba('angle_ironing', False),
                        flat=_vba('angle_flat', False),
                        layer_h=_vfa('angle_layer_h', 0.2),
                        material=str(rv.get('material', 'PLA') or 'PLA'),
                        bed=cfg_bed, nozzle=_gen_nozzle(directory), out_dir=directory,
                        version=max(1, min(int(_vfa('gen_version', 1)), 99)))
                    _rel86a = os.path.relpath(
                        os.path.join(directory, info_a['file']), directory)
                    _msg86a = ('%s: %s - %d plate(s), legs %.0f/%.0fmm, width %.0fmm, '
                               'holes %s x %.1fmm%s%s, %d layers - selected for printing'
                               % (info_a['kind'], info_a['file'], info_a['count'],
                                  info_a['legs'][0], info_a['legs'][1], info_a['width'],
                                  info_a['holes'], info_a['hole_d'],
                                  ' CS%.1f' % info_a['cs_d'] if info_a['cs_d'] else '',
                                  ' +rib' if info_a['stiffener'] else '',
                                  info_a['layers']))
                    for _note86a in info_a.get('notes', []):
                        _msg86a += ' | ' + _note86a
                    try:
                        _moonraker_gcode(
                            'RESPOND MSG="%s"\n'
                            'M117 %s ready\n'
                            '_SOUND_LIB NAME=r2_done\n'
                            '_SELECT_FILE FILE="%s"'
                            % (_msg86a, 'Flat' if info_a['kind'] == 'FLAT' else 'Angle',
                               _rel86a))
                    except Exception as me:                      # noqa: BLE001
                        print(f'[angles] moonraker unreachable ({me.__class__.__name__})',
                              flush=True)
                    print(f'[angles] {info_a["file"]}: {info_a["count"]} plate(s), '
                          f'{info_a["kind"]} {info_a["angle"]}deg, grid {info_a["grid"]}',
                          flush=True)
                except Exception as e:                          # noqa: BLE001
                    print(f'[angles] error: {e}', flush=True)
                    try:
                        _moonraker_gcode(
                            'RESPOND MSG="Angles ERROR: %s"\nM117 Angle error\n'
                            '_SOUND_LIB NAME=r2_error' % e)
                    except Exception:                           # noqa: BLE001
                        pass
        except Exception as e:                              # noqa: BLE001
            print(f'[angles] poll error: {e!r}', flush=True)

        # R89: image list push - the Lithophane browser on the LCD shows the
        # gcodes folder's images. Whenever the set changes, ONE SAVE_VARIABLE
        # via moonraker (the watcher owns the folder view; macros cannot list
        # files). Newest first, 10 slots, only top-level .png/.jpg/.jpeg.
        try:
            _imgs89 = []
            for _fn89 in os.listdir(directory):
                if not _fn89.lower().endswith(('.png', '.jpg', '.jpeg')):
                    continue
                _p89 = os.path.join(directory, _fn89)
                try:
                    if os.path.isfile(_p89) and '"' not in _fn89 and "'" not in _fn89:
                        _imgs89.append((os.path.getmtime(_p89), _fn89))
                except OSError:
                    pass
            _imgs89.sort(reverse=True)
            _names89 = [fn for (_mt, fn) in _imgs89[:10]]
            if _names89 != pushed_images:
                _val89 = '[' + ','.join("'%s'" % fn for fn in _names89) + ']'
                _moonraker_gcode(
                    'SAVE_VARIABLE VARIABLE=litho_files VALUE="%s"\n'
                    'RESPOND MSG="[i] %d image(s) ready for lithophane '
                    '(Tools > Lithophane)"' % (_val89, len(_names89)))
                pushed_images = _names89
        except Exception as e:                              # noqa: BLE001
            print(f'[litholist] push error: {e!r}', flush=True)

        # R89: lithophane generator request (litho_nonce) - runs THREADED:
        # a 100mm lithophane is ~200k gcode lines, the scan loop must keep
        # serving previews/requests while it generates.
        try:
            _ln89 = rv.get('litho_nonce', '')
            if _ln89 and _ln89 != last_litho_nonce:
                last_litho_nonce = _ln89

                def _vbl89(key, dflt):
                    v = str(rv.get(key, dflt)).strip().lower()
                    if v == '':
                        return dflt
                    return v in ('true', '1', 'on', 'yes')

                def _vfl89(key, dflt):
                    try:
                        return float(rv.get(key, dflt) or dflt)
                    except (TypeError, ValueError):
                        return float(dflt)

                _src89 = os.path.basename(str(rv.get('litho_file', '') or ''))
                if not _src89.lower().endswith(('.png', '.jpg', '.jpeg')):
                    raise ValueError('not an image: %r' % _src89)
                _p89 = os.path.join(directory, _src89)
                if not os.path.isfile(_p89):
                    raise ValueError('image not found: %s' % _src89)
                _bed89 = _bed_limits(os.path.join(
                    os.path.dirname(os.path.abspath(directory).rstrip('/')),
                    'config', 'printer.cfg'))
                _params89 = dict(
                    height_mm=_vfl89('litho_height', 100.0),
                    layer_h=_vfl89('litho_layer_h', 0.12),
                    levels=max(0, min(int(_vfl89('litho_levels', 0)), 16)),
                    frame=_vbl89('litho_frame', True),
                    brim_loops=max(0, min(int(_vfl89('litho_brim', 6)), 10)),
                    ironing=_vbl89('litho_ironing', False),
                    material=str(rv.get('material', 'PLA') or 'PLA'),
                    bed=_bed89, nozzle=_gen_nozzle(directory), out_dir=directory,
                    version=max(1, min(int(_vfl89('gen_version', 1)), 99)))

                def _litho_job89(p=_p89, params=_params89, src=_src89):
                    try:
                        out_l, info_l = make_lithophane(p, **params)
                        _rel89 = os.path.relpath(
                            os.path.join(directory, info_l['file']), directory)
                        _msg89 = ('Litho: %s - from %s, %.0fx%.0fmm plate, '
                                  '%d layers, thickness %smm%s - selected '
                                  'for printing'
                                  % (info_l['file'], src, info_l['width'],
                                     info_l['height'], info_l['layers'],
                                     info_l['thickness'],
                                     ', %d levels' % info_l['levels'] if info_l['levels'] else ''))
                        for _n89 in info_l.get('notes', [])[:2]:
                            _msg89 += ' | ' + _n89
                        _moonraker_gcode(
                            'RESPOND MSG="%s"\nM117 Litho ready\n'
                            '_SOUND_LIB NAME=r2_done\n_SELECT_FILE FILE="%s"'
                            % (_msg89, _rel89))
                    except Exception as e:                      # noqa: BLE001
                        print(f'[litho] error: {e!r}', flush=True)
                        try:
                            _moonraker_gcode(
                                'RESPOND MSG="Litho ERROR: %s"\nM117 Litho error\n'
                                '_SOUND_LIB NAME=r2_error' % e)
                        except Exception:                       # noqa: BLE001
                            pass

                import threading
                threading.Thread(target=_litho_job89, daemon=True).start()
        except Exception as e:                              # noqa: BLE001
            print(f'[litho] poll error: {e!r}', flush=True)

        # R89: gasket/seal generator request (seal_nonce) - small file, inline
        try:
            _sn89 = rv.get('seal_nonce', '')
            if _sn89 and _sn89 != last_seal_nonce:
                last_seal_nonce = _sn89

                def _vfs89(key, dflt):
                    try:
                        return float(rv.get(key, dflt) or dflt)
                    except (TypeError, ValueError):
                        return float(dflt)

                def _vbs89(key, dflt):
                    v = str(rv.get(key, dflt)).strip().lower()
                    if v == '':
                        return dflt
                    return v in ('true', '1', 'on', 'yes')

                _bed89s = _bed_limits(os.path.join(
                    os.path.dirname(os.path.abspath(directory).rstrip('/')),
                    'config', 'printer.cfg'))
                _prof89 = str(rv.get('seal_profile', 'FLAT') or 'FLAT').upper()
                if _prof89 not in ('FLAT', 'NUT', 'GROOVE'):
                    _prof89 = 'FLAT'
                out_s, info_s = make_seal(
                    od=_vfs89('seal_od', 40.0),
                    id_=_vfs89('seal_id', 20.0),
                    height=_vfs89('seal_height', 1.2),
                    profile=_prof89,
                    ironing=_vbs89('seal_ironing', False),
                    layer_h=_vfs89('seal_layer_h', 0.2),
                    material=str(rv.get('material', 'PLA') or 'PLA'),
                    bed=_bed89s, nozzle=_gen_nozzle(directory), out_dir=directory,
                    version=max(1, min(int(_vfs89('gen_version', 1)), 99)))
                _rel89s = os.path.relpath(
                    os.path.join(directory, info_s['file']), directory)
                _msg89s = ('Seal: %s - OD %.0f / ID %.0fmm, height %.2gmm, '
                           '%s face - selected for printing'
                           % (info_s['file'], info_s['od'], info_s['id'],
                              info_s['height'], info_s['profile']))
                for _n89 in info_s.get('notes', [])[:2]:
                    _msg89s += ' | ' + _n89
                try:
                    _moonraker_gcode(
                        'RESPOND MSG="%s"\nM117 Seal ready\n'
                        '_SOUND_LIB NAME=r2_done\n_SELECT_FILE FILE="%s"'
                        % (_msg89s, _rel89s))
                except Exception as me:                      # noqa: BLE001
                    print(f'[seal] moonraker unreachable ({me.__class__.__name__})',
                          flush=True)
                print(f'[seal] {info_s["file"]}: OK', flush=True)
        except Exception as e:                              # noqa: BLE001
            print(f'[seal] poll error: {e!r}', flush=True)

        # R91: TEXTURE tool (texture_nonce) - fuzzy skin / bumps on an EXISTING
        # file. Separate script, lazy import; writes a NEW _TX file - never an
        # overwrite, never auto-started (the user checks it in the 3D viewer).
        try:
            _tx91 = rv.get('texture_nonce', '')
            if _tx91 and _tx91 != last_texture_nonce:
                last_texture_nonce = _tx91
                from r2_texture import apply_texture          # lazy (R91 rule)
                _fn91 = os.path.basename(str(rv.get('texture_file', '') or ''))
                _bed91 = _bed_limits(os.path.join(
                    os.path.dirname(os.path.abspath(directory.rstrip('/'))),
                    'config', 'printer.cfg'))
                # NOTE: fuzzy/bump values are ABSOLUTE mm - no hidden scaling
                # (blind-safe parameter rule)
                out_t91, info_t91 = apply_texture(
                    os.path.join(directory, _fn91),
                    out_dir=directory,
                    mode=str(rv.get('texture_mode', 'FUZZY') or 'FUZZY'),
                    fuzzy_thick=float(rv.get('texture_fuzzy_thick', 0.3)
                                      or 0.3),
                    fuzzy_density=float(rv.get('texture_fuzzy_density', 100)
                                        or 100),
                    bump_pattern=str(rv.get('texture_pattern', 'GRID')
                                     or 'GRID'),
                    bump_scale=float(rv.get('texture_scale', 10.0) or 10.0),
                    bump_amp=float(rv.get('texture_amp', 0.35) or 0.35),
                    direction=str(rv.get('texture_dir', 'OUT') or 'OUT'),
                    bed=_bed91,
                    version=max(1, min(int(float(
                        rv.get('gen_version', 1) or 1)), 99)))
                _msg91 = ('Texture: %s -> %s (%s, %d outer-wall points '
                          'shifted, %d layers) - CHECK IT IN THE 3D VIEWER, '
                          'nothing auto-starts'
                          % (info_t91['src'], info_t91['file'],
                             info_t91['mode'], info_t91['shifted'],
                             info_t91['layers']))
                try:
                    _moonraker_gcode(
                        'RESPOND MSG="%s"\nM117 Texture ready\n'
                        '_SOUND_LIB NAME=r2_done' % _msg91)
                except Exception as me:                      # noqa: BLE001
                    print(f'[texture] moonraker unreachable '
                          f'({me.__class__.__name__})', flush=True)
                print(f'[texture] {info_t91["file"]}: OK '
                      f'({info_t91["shifted"]} pts, {info_t91["secs"]}s)',
                      flush=True)
        except ValueError as ve91:
            try:
                _moonraker_gcode(
                    'RESPOND MSG="Texture: %s"\nM117 Texture error\n'
                    '_SOUND_LIB NAME=r2_error' % ve91)
            except Exception:                               # noqa: BLE001
                pass
            print(f'[texture] guard: {ve91}', flush=True)

        # R93: FILE CHECK (file_check_nonce) - version census over every
        # g-code file. RETAG additionally upgrades old/untouched files:
        # .r2bak backup first, never while a print runs, max 20 per run
        # (Pi-friendly - run again for the rest).
        try:
            _fc93 = rv.get('file_check_nonce', '')
            if _fc93 and _fc93 != last_file_check_nonce:
                last_file_check_nonce = _fc93
                _retag93 = str(rv.get('file_check_retag', '') or '').strip().lower() \
                    in ('1', 'true', 'yes', 'on')
                rows93, tot93 = file_check_scan(directory)
                for _r93 in rows93:
                    print('[file-check] %-46s %-9s age=%4dd %7.1f MB%s'
                          % (_r93['name'][:46], _r93['status'], _r93['age'],
                             _r93['size'],
                             ' [texture]' if _r93['tex'] else ''), flush=True)
                _up93 = [r for r in rows93 if r['status'] in ('OLD', 'UNTOUCHED')]
                _extra93 = ''
                if _retag93:
                    _st93 = {}
                    try:
                        _st93 = _moonraker_status()
                    except Exception:                          # noqa: BLE001
                        pass
                    if ((_st93.get('print_stats') or {}).get('state')
                            in ('printing', 'paused')):
                        _extra93 = ' | RETAG refused: printing'
                    elif not _up93:
                        _extra93 = ' | RETAG: nothing to do'
                    else:
                        _n93 = 0
                        for _r93 in _up93[:20]:
                            _p93 = os.path.join(directory, _r93['name'])
                            try:
                                shutil.copy2(_p93, _p93 + '.r2bak')
                                process(_p93)
                                _n93 += 1
                                print('[file-check] retag: %s -> current'
                                      % _r93['name'], flush=True)
                            except OSError as _oe93:
                                print('[file-check] retag failed: %s (%r)'
                                      % (_r93['name'], _oe93), flush=True)
                        _extra93 = (' | RETAG: %d/%d upgraded (backup .r2bak)'
                                    % (_n93, len(_up93)))
                        if len(_up93) > 20:
                            _extra93 += ' - run again for the rest'
                _msg93 = ('File check: %d files - %d current, %d old, %d '
                          'untouched, %d plotter'
                          % (tot93['files'], tot93['current'], tot93['old'],
                             tot93['untouched'], tot93['plot']))
                try:
                    _moonraker_gcode(
                        'RESPOND MSG="%s%s"\nM117 Files: %dcur %dold %dnew\n'
                        '_SOUND_LIB NAME=r2_done'
                        % (_msg93, _extra93, tot93['current'], tot93['old'],
                           tot93['untouched']))
                except Exception as me93:                      # noqa: BLE001
                    print(f'[file-check] moonraker unreachable '
                          f'({me93.__class__.__name__})', flush=True)
                print('[file-check] %s%s' % (_msg93, _extra93), flush=True)
        except Exception as e:                              # noqa: BLE001
            print(f'[texture] poll error: {e!r}', flush=True)

        # R90: picture frame / display case generator (frame_nonce) - inline
        # (a 10x15 frame is ~25k gcode lines, well under a second)
        try:
            _fn90 = rv.get('frame_nonce', '')
            if _fn90 and _fn90 != last_frame_nonce:
                last_frame_nonce = _fn90

                def _vf90(key, dflt):
                    try:
                        return float(rv.get(key, dflt) or dflt)
                    except (TypeError, ValueError):
                        return float(dflt)

                def _vb90(key, dflt):
                    v = str(rv.get(key, dflt)).strip().lower()
                    if v == '':
                        return dflt
                    return v in ('true', '1', 'on', 'yes')

                def _vs90(key, dflt, allowed):
                    v = str(rv.get(key, dflt) or dflt).strip().upper()
                    return v if v in allowed else dflt

                _bed90 = _bed_limits(os.path.join(
                    os.path.dirname(os.path.abspath(directory.rstrip('/'))),
                    'config', 'printer.cfg'))
                _shape90 = _vs90('frame_shape', 'RECT', ('RECT', 'OVAL'))
                _clos90 = _vs90('frame_closure', 'BACK', ('BACK', 'SIDE'))
                _hang90 = _vs90('frame_hang', 'TOP',
                                ('TOP', 'BOTTOM', 'LEFT', 'RIGHT', 'OFF'))
                try:
                    out_f, info_f = make_frame(
                        preset=str(rv.get('frame_preset', '') or ''),
                        width=_vf90('frame_w', 102.0),
                        height=_vf90('frame_h', 152.0),
                        depth=_vf90('frame_depth', 8.0),
                        frame_w=_vf90('frame_border', 12.0),
                        corner=_vf90('frame_corner', 6.0),
                        shape=_shape90,
                        closure=_clos90,
                        hang=_hang90,
                        stand=_vb90('frame_stand', False),
                        ironing=_vb90('frame_ironing', True),
                        infill=_vf90('frame_infill', 60.0),
                        layer_h=_vf90('frame_layer_h', 0.2),
                        front=_vs90('frame_front', 'IRON',
                                    ('IRON', 'FLIP', 'LINES', 'WAVES', 'HEX')),
                        disc=_vs90('frame_disc', 'NONE',
                                   ('NONE', 'GLASS', 'PLEXI', 'FOIL', 'LITHO')),
                        disc_t=_vf90('frame_disc_t', 1.0),
                        disc_side=_vs90('frame_disc_side', 'FRONT',
                                        ('FRONT', 'BACK')),
                        cable=_vb90('frame_cable', False),
                        s_deep=_vf90('frame_s_deep', 0.8),
                        s_space=_vf90('frame_s_space', 6.0),
                        s_angle=_vf90('frame_s_angle', 45.0),
                        s_amp=_vf90('frame_s_amp', 1.2),
                        s_size=_vf90('frame_s_size', 8.0),
                        s_dir=_vs90('frame_s_dir', 'OUT', ('IN', 'OUT')),
                        material=str(rv.get('material', 'PLA') or 'PLA'),
                        bed=_bed90, nozzle=_gen_nozzle(directory), out_dir=directory,
                        version=max(1, min(int(_vf90('gen_version', 1)), 99)))
                except ValueError as ve:
                    print(f'[frame] guard: {ve}', flush=True)
                    try:
                        _moonraker_gcode(
                            'RESPOND MSG="Frame: %s"\nM117 Frame error\n'
                            '_SOUND_LIB NAME=r2_error' % ve)
                    except Exception:                       # noqa: BLE001
                        pass
                else:
                    # R90.1a: multi-plate - Part A selected (NOT started), one
                    # beep per plate, Part B..C stay in the file list
                    _plates90 = list(info_f.get('plates', [info_f['file']]))
                    _rel90 = os.path.relpath(
                        os.path.join(directory, _plates90[0]), directory)
                    _msg90 = ('Frame: %s - %s %s, photo %.0fx%.0f, border '
                              '%.0fmm, %s closure%s - Part A selected'
                              % (info_f['file'], info_f['mode'], info_f['shape'],
                                 info_f['width'], info_f['height'],
                                 info_f['border'], _clos90,
                                 ' (KIT)' if info_f['kit'] else ''))
                    if len(_plates90) > 1:
                        _msg90 += (' - %d PLATES: print Part B afterwards '
                                   '(no auto-start!)' % len(_plates90))
                    for _n90 in info_f.get('notes', [])[:3]:
                        _msg90 += ' | ' + _n90
                    _gc90 = ('RESPOND MSG="%s"\nM117 Frame ready\n'
                             '_SOUND_LIB NAME=r2_done' % _msg90)
                    if len(_plates90) > 1:
                        _gc90 += ('\nM117 Frame: %d plates' % len(_plates90)
                                  + '\nM300 P150 S880\nG4 P300'
                                  * len(_plates90))
                    _gc90 += '\n_SELECT_FILE FILE="%s"' % _rel90
                    try:
                        _moonraker_gcode(_gc90)
                    except Exception as me:                  # noqa: BLE001
                        print(f'[frame] moonraker unreachable '
                              f'({me.__class__.__name__})', flush=True)
                    print(f'[frame] {info_f["file"]}: OK'
                          + ('' if len(_plates90) < 2 else
                             ' + %d more plate(s): %s'
                             % (len(_plates90) - 1, ', '.join(_plates90[1:]))),
                          flush=True)
        except Exception as e:                              # noqa: BLE001
            print(f'[frame] poll error: {e!r}', flush=True)

        # R89: image delete request (litho_del_nonce) - LCD browser housekeeping.
        # Only ever deletes a plain image BASENAME inside the gcodes folder;
        # generated .gcode files (plotter output) are never touched.
        try:
            _dn89 = rv.get('litho_del_nonce', '')
            if _dn89 and _dn89 != last_litho_del_nonce:
                last_litho_del_nonce = _dn89
                _fn89d = os.path.basename(str(rv.get('litho_del_file', '') or ''))
                if not _fn89d.lower().endswith(('.png', '.jpg', '.jpeg')):
                    # LCD slots only ever pass image names - this is a manual
                    # console call: refuse LOUDLY but do not crash the poll
                    _moonraker_gcode(
                        'RESPOND MSG="Image delete refused: %s is not a '
                        '.png/.jpg/.jpeg file"\nM117 Delete refused\n'
                        '_SOUND_LIB NAME=r2_notice' % _fn89d)
                    raise _SkipHandler()
                _p89d = os.path.join(directory, _fn89d)
                if os.path.isfile(_p89d):
                    os.remove(_p89d)
                    _msg89d = ('Image deleted: %s - its plotter .gcode (if any) '
                               'stays in the file list' % _fn89d)
                    _snd89d = 'r2_done'
                else:
                    _msg89d = 'Image not found: %s' % _fn89d
                    _snd89d = 'r2_notice'
                _moonraker_gcode(
                    'RESPOND MSG="%s"\nM117 Image deleted\n'
                    '_SOUND_LIB NAME=%s' % (_msg89d, _snd89d))
        except _SkipHandler:
            pass
        except Exception as e:                              # noqa: BLE001
            print(f'[lithodel] poll error: {e!r}', flush=True)

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
                        bed=cfg_bed, nozzle=_gen_nozzle(directory),
                        out_dir=directory)
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
            scan(rrw)
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
    if args[0] == '--file-check':
        # R93: SSH one-liner - version census over a gcodes folder, no
        # Klipper needed:  r2_postproc.py --file-check ~/printer_data/gcodes
        d93 = args[1] if len(args) > 1 else '.'
        if not os.path.isdir(d93):
            print(f'[ERROR] not a directory: {d93}', flush=True)
            sys.exit(1)
        rows93, tot93 = file_check_scan(d93)
        for _r93 in rows93:
            print('[file-check] %-46s %-9s age=%4dd %7.1f MB%s'
                  % (_r93['name'][:46], _r93['status'], _r93['age'],
                     _r93['size'], ' [texture]' if _r93['tex'] else ''))
        print('[file-check] %d files: %d current, %d old, %d untouched, '
              '%d plotter' % (tot93['files'], tot93['current'], tot93['old'],
                              tot93['untouched'], tot93['plot']))
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
