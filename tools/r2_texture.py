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
- the source file: the result is a NEW file <name>_TX_V01.gcode (version
  bumped until free) - never an overwrite, no auto-start (viewer hint instead)

Streaming, Pi-safe: one line in, one line out, no full-file buffers.
"""
import math
import os
import random
import re
import time

TAG = 'R2-TEXTURE v1 (R91)'

_G1 = re.compile(r'^(G1|G0)\s+X([\d.\-]+)\s+Y([\d.\-]+)(?:\s+Z([\d.\-]+))?'
                 r'(?:\s+E([\d.\-]+))?')
_TYPE = re.compile(r'^;TYPE:(.+)')
_MIN_E = 0.0001


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
                  bump_amp=0.35, direction='OUT', bed=None, version=1,
                  seed=91):
    """Returns (new_path, info). Raises ValueError on bad parameters."""
    mode = str(mode).upper()
    direction = str(direction).upper()
    bump_pattern = str(bump_pattern).upper()
    if mode not in ('FUZZY', 'BUMPS'):
        raise ValueError('mode %r must be FUZZY or BUMPS' % mode)
    if direction not in ('OUT', 'IN'):
        raise ValueError('direction %r must be OUT or IN' % direction)
    if not (0.05 <= float(fuzzy_thick) <= 0.6):
        raise ValueError('fuzzy thickness %.2fmm out of range (0.05..0.6)'
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
    # R83 naming: keep a leading 00_, add _TX, version up until free
    stem = re.sub(r'_V\d+$', '', stem)
    ver = max(1, min(int(version), 99))
    while True:
        fname = '%s_TX_V%02d.gcode' % (stem, ver)
        out = os.path.join(out_dir, fname)
        if not os.path.exists(out) or os.path.abspath(out) == os.path.abspath(src):
            break
        ver += 1
        if ver > 99:
            raise ValueError('all _TX versions V01..V99 exist - clean up first')

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

    stats = {'moves': 0, 'shifted': 0, 'clamped': 0, 'layers': 0}
    cur_type = ''
    # px/py = None until the first move is seen: a vertex with no known
    # approach direction gets NO offset (same rule as zero-length moves -
    # never invent a direction from the home position)
    px = py = None
    t0 = time.time()

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
        for line in fi:
            ls = line.rstrip('\n')
            m = _TYPE.match(ls)
            if m:
                cur_type = m.group(1).strip().lower()
                fo.write(ls + '\n')
                continue
            if ls.startswith(';LAYER_CHANGE'):
                stats['layers'] += 1
            g = _G1.match(ls)
            if (g and g.group(1) == 'G1' and cur_type == 'outer wall'
                    and g.group(5) is not None
                    and float(g.group(5)) > _MIN_E and g.group(2) is not None):
                x, y = float(g.group(2)), float(g.group(3))
                dx, dy = (x - px, y - py) if px is not None else (0.0, 0.0)
                ln = math.hypot(dx, dy)
                z = float(g.group(4)) if g.group(4) is not None else None
                stats['moves'] += 1
                nx = ny = 0.0
                if ln > 0.01:
                    # left-hand normal of the move direction (consistent sign)
                    ox, oy = -dy / ln, dx / ln
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
                        ls = re.sub(r'X[\d.\-]+', 'X%.3f' % nx, ls, count=1)
                        ls = re.sub(r'Y[\d.\-]+', 'Y%.3f' % ny, ls, count=1)
                        stats['shifted'] += 1
                px, py = x, y
                fo.write(ls + '\n')
                continue
            gm = _G1.match(ls)
            if gm and gm.group(2) is not None:
                px, py = float(gm.group(2)), float(gm.group(3))
            fo.write(ls + '\n')

    info = {'file': fname, 'src': base, 'mode': mode, 'version': ver,
            'fuzzy_thick': float(fuzzy_thick) if mode == 'FUZZY' else 0.0,
            'fuzzy_density': float(fuzzy_density) if mode == 'FUZZY' else 0.0,
            'pattern': bump_pattern if mode == 'BUMPS' else '',
            'scale': float(bump_scale), 'amp': float(bump_amp),
            'direction': direction, 'shifted': stats['shifted'],
            'outer_moves': stats['moves'], 'clamped': stats['clamped'],
            'layers': stats['layers'], 'secs': round(time.time() - t0, 2)}
    return out, info
