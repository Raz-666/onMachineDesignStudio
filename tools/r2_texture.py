#!/usr/bin/env python3
"""R91: texture tool - fuzzy skin + parametric bump meshing for EXISTING
g-code files. A separate script (lazy-imported by the watcher), never part of
the hot interceptor path.

What it does
- FUZZY: random displacement of every OUTER WALL vertex within +- fuzzy_thick
  (seeded RNG -> deterministic, reproducible), fuzzy_density = share of
  vertices that scatter (100 % = full fuzzy, 20 % = sparse dents)
- BUMPS: displacement along the wall normal proportional to a seamless
  pattern function at (x, y, z):
    GRID         sin(x)*sin(y) egg-crate
    WAVES        diagonal sinus with a z-phase (breaks the layer rhythm)
    HEX          3-fold sinus -> honeycomb
    MANDELBROT   escape-time value of z->z^2+c, c scaled from the bed center
  direction OUT = away from the part shell, IN = into it (flip if the wall
  winding surprises you)
- vertical z-phase everywhere: consecutive layers get a slightly shifted
  pattern - ugly layer lines are camouflaged instead of carrying the bump

What it never touches
- ;TYPE: tags, LAYER_MARK / APPLY_TYPE, EXCLUDE_OBJECT_*, temps, fans,
  retracts, speeds, E values, Z values - the feature system stays intact
- the source file: the result is a NEW file 00_Vnn_name_TX.gcode (one
  folder-global running number, never reused) - never an overwrite, no
  auto-start (viewer hint instead)

Streaming, Pi-safe: one line in, one line out, no full-file buffers.
"""
import math
import os
import random
import re
import time

TAG = 'R2-TEXTURE v2 (R95)'

_G1 = re.compile(r'^(G1|G0)\s+X([\d.\-]+)\s+Y([\d.\-]+)(?:\s+Z([\d.\-]+))?'
                 r'(?:\s+E([\d.\-]+))?')
# R95: slicers with arc fitting emit the OUTER WALL as G2/G3 arcs - the R91
# scatter only touched G1 vertices, so round parts (vases!) carried texture
# only in the few straight bits between arcs ("only the corners"). Arcs are
# flattened into short G1 chords first, then textured like any other vertex.
_GARC = re.compile(r'^(G[23])\s+X([\d.\-]+)\s+Y([\d.\-]+)'
                  r'(?:\s+Z([\d.\-]+))?'
                  r'(?:\s+I([\d.\-]+)\s+J([\d.\-]+)|\s+R([\d.\-]+))?'
                  r'(?:\s+E(-?[\d.]+))?(?:\s+F([\d.]+))?(?:\s*;.*)?$')


def _arc_points(x0, y0, x1, y1, i=None, j=None, rr=None, cw=True,
                chord=0.35):
    """R95: points of a G2 (cw=True) / G3 arc from (x0,y0) to (x1,y1).
    I/J = center offset from the start, R = radius form. Returns None when
    the arc cannot be resolved (garbage input stays untouched)."""
    cx = cy = None
    if i is not None and j is not None:
        cx, cy = x0 + i, y0 + j
    elif rr is not None and rr != 0:
        # Marlin R form: center on the perpendicular bisector, h = side of
        # the chord chosen so the sweep is <= 180 deg for +R, > 180 for -R
        mx, my = (x0 + x1) / 2.0, (y0 + y1) / 2.0
        d = math.hypot(x1 - x0, y1 - y0) / 2.0
        if d > abs(rr):
            return None
        h = math.sqrt(max(0.0, rr * rr - d * d))
        ux, uy = (y1 - y0), -(x1 - x0)        # perpendicular (right of chord)
        if not (rr < 0) == cw:
            ux, uy = -ux, -uy
        cx, cy = mx + ux / (2 * d + 1e-12) * h, my + uy / (2 * d + 1e-12) * h
    else:
        return None
    r = math.hypot(x0 - cx, y0 - cy)
    r2 = math.hypot(x1 - cx, y1 - cy)
    if r < 1e-6 or abs(r - r2) > max(0.05, r * 0.01):
        return None
    a0 = math.atan2(y0 - cy, x0 - cx)
    a1 = math.atan2(y1 - cy, x1 - cx)
    if cw:
        sweep = (a0 - a1) % (2 * math.pi)
    else:
        sweep = (a1 - a0) % (2 * math.pi)
    if sweep < 1e-9:
        sweep = 2 * math.pi
    arclen = sweep * r
    n = int(math.ceil(arclen / max(chord, 0.05)))
    n = max(2, min(n, 720))
    pts = []
    for k in range(1, n + 1):
        a = a0 + (-sweep if cw else sweep) * k / float(n)
        pts.append((cx + r * math.cos(a), cy + r * math.sin(a)))
    return pts
_TYPE = re.compile(r'^;TYPE:(.+)')
_APPLY152 = re.compile(r'^APPLY_TYPE TYPE=(\S+)')
_MIN_E = 0.0001

# R152 (.113) field report: ORCA spells the vase-mode (spiral) wall
# ';TYPE:Wall outer' while normal walls say 'Outer wall' - the texture
# matched only the latter, so a vase print carried the fuzzy skin on the
# first (and the file's last) normal layer and NONE along the spiral.
# Canonical set after normalization (lowercase, non-letters = spaces):
_OUTER_ALIASES = {
    'outer wall',      # Orca/Elegoo/Prusa normal, R2 canonical
    'wall outer',      # Orca VASE mode (spiral), Cura WALL-OUTER
    'external perimeter',   # PrusaSlicer
}


def _is_outer_wall(t):
    t = re.sub(r'[^a-z]+', ' ', (t or '').strip().lower()).strip()
    return t in _OUTER_ALIASES


def _bump_grid(x, y, z, scale):
    return (math.sin(x * 2 * math.pi / scale) *
            math.sin(y * 2 * math.pi / scale))


def _bump_waves(x, y, z, scale):
    ph = z * 2 * math.pi / 1.2          # z-phase: camouflages layer lines
    return (math.sin((x + y) * 2 * math.pi / scale + ph) *
            (0.6 + 0.4 * math.sin(z * 2 * math.pi / 3.7)))


def _bump_hex(x, y, z, scale):
    a = x * 2 * math.pi / scale
    b = y * 2 * math.pi / scale
    return (math.sin(a) * 0.5 +
            math.sin(b + math.cos(a) * 0.5 + z * 0.6) * 0.5)


def _bump_mandelbrot(x, y, z, scale, cx, cy):
    # c scaled from the bed center: deterministic + position-unique
    c = complex((x - cx) / (scale * 10.0), (y - cy) / (scale * 10.0))
    zn = complex(0.0, 0.0)
    for _i in range(12):
        zn = zn * zn + c
        if abs(zn) > 4.0:
            break
    v = min(1.0, abs(zn) / 4.0)
    return v * v * (0.7 + 0.3 * math.sin(z * 2 * math.pi / 1.2))


def apply_texture(src, out_dir=None, mode='FUZZY', fuzzy_thick=0.3,
                  fuzzy_density=100.0, bump_pattern='GRID', bump_scale=10.0,
                  bump_amp=0.35, direction='OUT', bed=None, version=1,  # version: retired (R158, folder-global auto)
                  seed=91):
    """Returns (new_path, info). Raises ValueError on bad parameters."""
    mode = str(mode).upper()
    direction = str(direction).upper()
    bump_pattern = str(bump_pattern).upper()
    if mode not in ('FUZZY', 'BUMPS'):
        raise ValueError('mode %r must be FUZZY or BUMPS' % mode)
    if direction not in ('OUT', 'IN'):
        raise ValueError('direction %r must be OUT or IN' % direction)
    if not (0.05 <= float(fuzzy_thick) <= 1.5):
        raise ValueError('fuzzy thickness %.2fmm out of range (0.05..1.5)'
                         % float(fuzzy_thick))
    if not (10.0 <= float(fuzzy_density) <= 100.0):
        raise ValueError('fuzzy density %.0f%% out of range (10..100)'
                         % float(fuzzy_density))
    if bump_pattern not in ('GRID', 'WAVES', 'HEX', 'MANDELBROT'):
        raise ValueError('bump pattern %r must be GRID, WAVES, HEX or '
                         'MANDELBROT' % bump_pattern)
    if not (3.0 <= float(bump_scale) <= 60.0):
        raise ValueError('bump scale %.1fmm out of range (3..60)'
                         % float(bump_scale))
    if not (0.1 <= float(bump_amp) <= 0.8):
        raise ValueError('bump amplitude %.2fmm out of range (0.1..0.8)'
                         % float(bump_amp))
    if not os.path.isfile(src):
        raise ValueError('source file not found: %s' % src)
    out_dir = out_dir or os.path.dirname(os.path.abspath(src))
    if bed is None:
        bed = (0.0, -3.0, 220.0, 217.0)      # real Ender-3 plate (manual ch.23)

    base = os.path.basename(src)
    stem = base[:-6] if base.lower().endswith('.gcode') else base
    # R158 (.118): version FIRST + ONE folder-global number, mirroring
    # r2_postproc._next_gen_version (kept local on purpose - this script
    # stays importable without the 18k-line post-processor). A new-format
    # source (00_Vnn_Name.gcode) contributes just its Name part; a legacy
    # source (00_Name_Vnn.gcode) loses its tail version AND its old 00_
    # prefix - the output carries exactly one 00_Vnn_ head.
    _m158 = re.match(r'^00_V\d+_(.+)$', stem)
    if _m158:
        stem = _m158.group(1)
    else:
        stem = re.sub(r'_V\d+$', '', stem)
        stem = stem[3:] if stem.startswith('00_') else stem
    _hi158 = 0
    try:
        for _p158 in os.listdir(out_dir):
            _mm158 = re.match(r'^00_V(\d+)_', _p158)
            if _mm158:
                _hi158 = max(_hi158, int(_mm158.group(1)))
                continue
            _mm158 = re.search(r'_V(\d+)\.gcode$', _p158)
            if _mm158 and _p158.startswith('00_'):
                _hi158 = max(_hi158, int(_mm158.group(1)))
    except OSError:
        pass
    if _hi158 >= 99:
        raise ValueError('all 00_V numbers 01..99 are used in this folder - '
                         'clean up first (a texture never silently '
                         'overwrites)')
    fname = '00_V%02d_%s_TX.gcode' % (_hi158 + 1, stem)
    out = os.path.join(out_dir, fname)
    if os.path.abspath(out) == os.path.abspath(src):
        raise ValueError('texture output name collides with the source - '
                         'refusing')

    rng = random.Random(seed)
    cx = (bed[0] + bed[2]) / 2.0
    cy = (bed[1] + bed[3]) / 2.0
    sign = 1.0 if direction == 'OUT' else -1.0
    sig = float(bump_amp)
    dens = float(fuzzy_density) / 100.0

    def pattern(x, y, z):
        if bump_pattern == 'GRID':
            return _bump_grid(x, y, z, float(bump_scale))
        if bump_pattern == 'WAVES':
            return _bump_waves(x, y, z, float(bump_scale))
        if bump_pattern == 'HEX':
            return _bump_hex(x, y, z, float(bump_scale))
        return _bump_mandelbrot(x, y, z, float(bump_scale), cx, cy)

    stats = {'moves': 0, 'shifted': 0, 'clamped': 0, 'layers': 0, 'arcs': 0}
    cur_type = ''
    cur_outer = False       # R152: alias-normalized outer-wall check
    t0 = time.time()
    # px/py = None until the first move is seen: a vertex with no known
    # approach direction gets NO offset (same rule as zero-length moves -
    # never invent a direction from the home position)
    px = py = None
    # R95: E bookkeeping for arc flattening - chords must carry exactly the
    # arc's extrusion (relative: distributed by chord length; absolute:
    # interpolated from the last E to the arc's end value)
    e_rel = False
    last_e = 0.0

    def _shift_txt(txt, x, y, z):
        """R91 displacement on ONE move line -> possibly shifted text.
        Reads px/py from the enclosing scope (approach direction)."""
        dx, dy = (x - px, y - py) if px is not None else (0.0, 0.0)
        ln = math.hypot(dx, dy)
        stats['moves'] += 1
        if ln <= 0.01:
            return txt
        # left-hand normal of the move direction (consistent sign)
        ox, oy = -dy / ln, dx / ln
        nx = ny = 0.0
        if mode == 'FUZZY':
            if rng.random() <= dens:
                # random point in a disc of radius fuzzy_thick
                ang = rng.random() * 2 * math.pi
                rad = math.sqrt(rng.random()) * float(fuzzy_thick)
                nx = ox * math.cos(ang) * rad - oy * math.sin(ang) * rad
                ny = ox * math.sin(ang) * rad + oy * math.cos(ang) * rad
        else:
            zz = z if z is not None else 0.0
            nx = ox * pattern(x, y, zz) * sig * sign
            ny = oy * pattern(x, y, zz) * sig * sign
        if nx or ny:
            nx, ny = round(x + nx, 3), round(y + ny, 3)
            if not (bed[0] <= nx <= bed[2] and bed[1] <= ny <= bed[3]):
                nx = max(bed[0], min(nx, bed[2]))
                ny = max(bed[1], min(ny, bed[3]))
                stats['clamped'] += 1
            txt = re.sub(r'X[\d.\-]+', 'X%.3f' % nx, txt, count=1)
            txt = re.sub(r'Y[\d.\-]+', 'Y%.3f' % ny, txt, count=1)
            stats['shifted'] += 1
        return txt

    with open(src, errors='replace') as fi, open(out, 'w') as fo:
        fo.write('; %s applied to %s: mode %s%s\n' % (
            TAG, base, mode,
            ' thick %.2f density %.0f%%' % (float(fuzzy_thick),
                                            float(fuzzy_density))
            if mode == 'FUZZY' else
            ' %s scale %.1f amp %.2f %s' % (bump_pattern, float(bump_scale),
                                            float(bump_amp), direction)))
        fo.write('; fuzzy scatters / bumps displace ONLY outer-wall vertices '
                 '- tags, features, E and Z stay untouched\n')
        fo.write('; R95: G2/G3 outer-wall arcs are flattened into textured '
                 'chords (arc-fitted files get a seamless all-around texture)\n')
        for line in fi:
            ls = line.rstrip('\n')
            m = _TYPE.match(ls)
            if m:
                cur_type = m.group(1).strip().lower()
                cur_outer = _is_outer_wall(cur_type)
                fo.write(ls + '\n')
                continue
            # R152: the r2-postproc injects the CANONICAL type right after
            # every ;TYPE: line (APPLY_TYPE TYPE=WALL-OUTER ...) - trust it
            # too, it already normalized the slicer dialect
            _ma152 = _APPLY152.match(ls)
            if _ma152:
                cur_type = _ma152.group(1).strip().lower()
                cur_outer = _is_outer_wall(cur_type)
            if ls.startswith(';LAYER_CHANGE'):
                stats['layers'] += 1
            elif ls == 'M83':
                e_rel = True
            elif ls == 'M82':
                e_rel = False
            elif ls.startswith('G92'):
                me92 = re.match(r'^G92(?:\s+E(-?[\d.]+))?', ls)
                if me92 and me92.group(1) is not None:
                    last_e = float(me92.group(1))
            g = _G1.match(ls)
            if (g and g.group(1) == 'G1' and cur_outer
                    and g.group(5) is not None
                    and float(g.group(5)) > _MIN_E and g.group(2) is not None):
                x, y = float(g.group(2)), float(g.group(3))
                z = float(g.group(4)) if g.group(4) is not None else None
                fo.write(_shift_txt(ls, x, y, z) + '\n')
                px, py = x, y
                last_e = float(g.group(5))
                continue
            # ---- R95: outer-wall G2/G3 arcs -> short G1 chords, textured ---
            ga = _GARC.match(ls)
            if (ga and cur_outer and ga.group(8) is not None
                    and float(ga.group(8)) > _MIN_E and px is not None):
                x1, y1 = float(ga.group(2)), float(ga.group(3))
                z1 = float(ga.group(4)) if ga.group(4) is not None else None
                pts = _arc_points(
                    px, py, x1, y1,
                    float(ga.group(5)) if ga.group(5) is not None else None,
                    float(ga.group(6)) if ga.group(6) is not None else None,
                    float(ga.group(7)) if ga.group(7) is not None else None,
                    cw=(ga.group(1) == 'G2'))
                if pts:
                    stats['arcs'] += 1
                    e_arc = float(ga.group(8))
                    _all = [(px, py)] + pts[:-1]
                    arc_len = sum(math.hypot(b[0] - a[0], b[1] - a[1])
                                  for a, b in zip(_all, pts))
                    f_txt = (' F' + ga.group(9)) if ga.group(9) else ''
                    for (ax, ay), (qx, qy) in zip(_all, pts):
                        cl = math.hypot(qx - ax, qy - ay)
                        frac = (cl / arc_len) if arc_len > 1e-9 else 0.0
                        if e_rel:
                            ec = e_arc * frac
                        else:
                            ec = last_e + (e_arc - last_e) * frac
                        ch = 'G1 X%.3f Y%.3f E%.5f%s' % (qx, qy, ec, f_txt)
                        fo.write(_shift_txt(ch, qx, qy, z1) + '\n')
                        if not e_rel:
                            last_e = ec
                    px, py = x1, y1
                    if not e_rel:
                        last_e = e_arc
                    continue
                # unresolvable arc geometry -> untouched passthrough (below)
            gm = _G1.match(ls)
            if gm and gm.group(2) is not None:
                px, py = float(gm.group(2)), float(gm.group(3))
                if gm.group(5) is not None:
                    last_e = float(gm.group(5))
            fo.write(ls + '\n')

    info = {'file': fname, 'src': base, 'mode': mode, 'version': _hi158 + 1,
            'fuzzy_thick': float(fuzzy_thick) if mode == 'FUZZY' else 0.0,
            'fuzzy_density': float(fuzzy_density) if mode == 'FUZZY' else 0.0,
            'pattern': bump_pattern if mode == 'BUMPS' else '',
            'scale': float(bump_scale), 'amp': float(bump_amp),
            'direction': direction, 'shifted': stats['shifted'],
            'outer_moves': stats['moves'], 'clamped': stats['clamped'],
            'layers': stats['layers'], 'arcs_flattened': stats['arcs'],
            'secs': round(time.time() - t0, 2)}
    return out, info
