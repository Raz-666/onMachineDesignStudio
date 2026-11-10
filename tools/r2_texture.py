#!/usr/bin/env python3
"""R175: texture tool v3 - the PATTERN LIBRARY engine for EXISTING g-code
files. A separate script (lazy-imported by the watcher), never part of the
hot interceptor path.

THE R175 RULE (field wish, .130): the user's values are a GUIDELINE, the
GEOMETRY decides. Every pattern is computed in CYLINDER coordinates around
the OBJECT (theta from the object center, z from its base) and is SEAMLESS:
- around: the pattern repeats an INTEGER number of ridges (k) around the
  circumference - your 'size around' is snapped to the nearest whole count,
  so the seam closes perfectly on ANY shape (vase, rose, bracket)
- in Z: the pattern repeats an INTEGER number of times (n) over the object
  height - your 'Z size' snaps to whole repeats, the texture ends flush at
  the top and runs 'endless' (periodic) through the whole height
The snapped values are reported back ('12 ridges x 24 repeats, effective
9.8 x 10.2 mm') - presets stay honest.

R231 ARC-ANCHORED MAPPING (.136ab field log): s used to be pure theta/2pi -
on a wall that runs INWARD (a vase notch, a cut-out) the same angle range
covers two or three times the wall length, so the pattern cells STRETCHED
across the concave section ('the pixels are just pulled to the back, no
structure'). s is now advanced by ARC LENGTH along each wall loop and
anchored to the absolute angle at the loop start:
    s = (theta_start/2pi + arc_pos/loop_len) mod 1
- the anchor keeps the pattern locked in space across layers (spiral seams
  rotate - a pure arc fraction would drift with them), the arc advance
  keeps every cell the same PHYSICAL width on convex AND concave wall
  sections, and the closure stays seamless: one loop = s runs exactly 0->1,
  k integer ridges close flush.
- INNER walls (BUMPS follow mode) do NOT use their own arc-anchored s: they
  sample the s the OUTER loop used at the same ANGLE (per-layer cache) so
  the wall pair moves as one - a reversed inner loop's own s runs mirrored
  and would shear the walls through each other.

Modes
- FUZZY: random displacement of every OUTER WALL vertex within +- thick
  (seeded RNG -> deterministic), density = share of scattered vertices
- BUMPS: displacement along the wall normal proportional to one of 27
  seamless pattern functions (see PATTERNS below). R238: every pattern
  carries an AUTO TILT (PATTERN_TILT) - a helical shift that angles the
  lattice 2 deg off the layer plane (directional looks keep their own
  angle), so the texture never runs parallel to the print layers.
- MAP: a grayscale picture wrapped around the object (cylinder
  projection). R238: the background is detected (Otsu + border vote) and
  treated as ALPHA - zero displacement there, feathered edges; TILE =
  endless mirrored wrap, ONCE = one aspect-true wrap positioned
  TOP/CENTER/BOTTOM (the masked background hides the seam).

Patterns (all seamless, all seeded where random)
  RIDGES      vertical flutes around the object
  WAVES       diagonal waves (the classic)
  GRID        crosshatch egg-crate
  HEX         3-fold sinus honeycomb-ish
  HONEYCOMB   true hex cells (distance field)
  BASKET      woven over/under basket
  ROPE        twisted strands
  PLANKS      VERTICAL boards - seeded stagger, grooved seams, grain up (R238)
  BRICKS      running-bond brick courses with mortar grooves
  SANDSTONE   fine 2-octave noise (cast sandstone)
  CONCRETE    coarse noise + seeded pores
  CLAY        soft overlapping dents (thumb-printed clay)
  CREPE       high-frequency crumple x a mid wave (paper)
  FABRIC      pleats - sharp valleys, wide backs
  PLUSH       dense short fine noise (velvet)
  HILBERT     zig-zag space-filling bands (the curve look)
  CHECKER     checkerboard, soft edges
  SCRATCH     anisotropic scratches around the circumference
  HATCH       hard diagonal hatching
  GLITCH      seeded per-band steps (the melt / shifted-layer look)
  KNIT        nested V-loops in staggered columns (knit/crochet, R238)
  FLUTED      vertical half-round flutes (kills Z-banding on cylinders, R238)
  BARK        vertical ridged cracks - tree bark (R238)
  SCALES      staggered domed shingles - reptile scales (R238)
  FACETS      diamond low-poly relief crosses (R238)
  MACRAME     two twisted cord families crossing into a net (R238)
  MAP         grayscale image, background = alpha (Otsu), TILE or ONCE (R238)

What it never touches
- ;TYPE: tags, LAYER_MARK / APPLY_TYPE, EXCLUDE_OBJECT_*, temps, fans,
  retracts, speeds, E values, Z values - the feature system stays intact
- the source file: the result is a NEW file Vnn_name_TX.gcode (one
  folder-global running number, never reused) - never an overwrite, no
  auto-start (viewer hint instead)

Streaming, Pi-safe: one line in, one line out, no full-file buffers.
"""
import math
import os
import random
import re
import time

TAG = 'R2-TEXTURE v3 (R175)'

# R159 (.119) FIELD FIX: the old _G1 demanded X DIRECTLY after the command
# and Y right behind it. Real slicer output does not keep that order - a
# spiral vase prints as 'G1 Z24.172 X83.376 Y103.03 E.05991' (Z first, and
# an E without a leading digit) - so the texture silently skipped the WHOLE
# spiral and reported a plausible-looking 'shifted' count from the few
# X-first bottom moves (field log: vase came out smooth). Tokens are now
# parsed in ANY order (comments cut before parsing, values rewritten in
# place - the original token order and everything else on the line stays).
_CMD_RE = re.compile(r'^(G1|G0)\b')
_M204_SCRUB = re.compile(r'^(\s*)_M204(\s|$)')   # R237: legacy slicer rename
# R240 (.136ai field log): the old package macro name _M204_SET (digits end
# a klipper command name -> 'Malformed command') - rewrite while streaming.
_M204SET_SCRUB = re.compile(r'^(\s*)_M204_SET\s+VALUE=([0-9.]+)\s*$')
_TOK_RE = {t: re.compile(r'(?:^|\s)' + t + r'(-?[\d.]+)')
           for t in ('X', 'Y', 'Z', 'E', 'I', 'J', 'R', 'F')}


def _tok(body, t):
    m = _TOK_RE[t].search(body)
    return float(m.group(1)) if m else None


def _parse_move(ls):
    """('G1'|'G0', x, y, z, e) for a G0/G1 line in ANY token order, else None."""
    body = ls.split(';', 1)[0]
    m = _CMD_RE.match(body)
    if not m:
        return None
    return (m.group(1), _tok(body, 'X'), _tok(body, 'Y'),
            _tok(body, 'Z'), _tok(body, 'E'))


def _parse_arc(ls):
    """('G2'|'G3', x, y, z, i, j, r, e, f) for a G2/G3 line in ANY token order."""
    body = ls.split(';', 1)[0]
    m = re.match(r'^(G[23])\b', body)
    if not m:
        return None
    return (m.group(1), _tok(body, 'X'), _tok(body, 'Y'), _tok(body, 'Z'),
            _tok(body, 'I'), _tok(body, 'J'), _tok(body, 'R'),
            _tok(body, 'E'), _tok(body, 'F'))
# R95: slicers with arc fitting emit the OUTER WALL as G2/G3 arcs - the R91
# scatter only touched G1 vertices, so round parts (vases!) carried texture
# only in the few straight bits between arcs ("only the corners"). Arcs are
# flattened into short G1 chords first, then textured like any other vertex.


def _arc_points(x0, y0, x1, y1, i=None, j=None, rr=None, cw=True,
                chord=0.35):
    """R95: points of a G2 (cw=True) / G3 arc from (x0,y0) to (x1,y1).
    I/J = center offset from the start, R = radius form. Returns None when
    the arc cannot be resolved (garbage input stays untouched)."""
    cx = cy = None
    if i is not None and j is not None:
        cx, cy = x0 + i, y0 + j
    elif rr is not None and rr != 0:
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

# R175: EXCLUDE_OBJECT_DEFINE CENTER lines (marked files carry them right at
# the top) are the BEST object center - otherwise the texture falls back to
# the outer-wall vertex centroid.
_EOD_CENTER = re.compile(
    r'^EXCLUDE_OBJECT_DEFINE\s+NAME=\S+\s+CENTER=(-?[\d.]+)[, ]+(-?[\d.]+)')


def _is_outer_wall(t):
    t = re.sub(r'[^a-z]+', ' ', (t or '').strip().lower()).strip()
    return t in _OUTER_ALIASES


# R224 task 15: INNER walls follow the embossing in BUMPS mode - an
# untouched inner wall sits one line width behind the surface and CAPS
# the valleys of a deep DIR=IN texture (the pattern reads washed out).
# Following keeps the wall stack parallel: the inner wall stays
# invisible behind the outer surface and keeps wall contact. Dialects
# mirror the r2-postproc lookup table (WALL-INNER).
_INNER_ALIASES = {
    'inner wall',        # Orca/Elegoo/Prusa, R2 canonical WALL-INNER
    'wall inner',        # Cura WALL-INNER via APPLY_TYPE
    'inner perimeter',
    'internal perimeter',
    'perimeter',         # PrusaSlicer: plain perimeters are the inner ones
    'thin wall',         # SuperSlicer
}


def _is_inner_wall(t):
    t = re.sub(r'[^a-z]+', ' ', (t or '').strip().lower()).strip()
    return t in _INNER_ALIASES


# =====================================================================================
#  R175 PATTERN LIBRARY - every pattern is a function f(s, t, k, n, aux)
#  with  s = theta/2pi in [0,1)   (seamless: integer k tiles around)
#        t = z*n/H in [0,1)       (seamless: integer n repeats over the height)
#        k = ridge count around, n = repeat count in Z (both INTEGER -> the
#            user's size guideline snapped to the geometry)
#        aux = (rng, img, noise)  seeded helpers
#  Return: -1..+1 (normal displacement factor). Periodicity in s and t is
#  guaranteed by construction (trig of 2*pi*integer*x or wrapped grids) -
#  the texture is ENDLESS and closes flush at the seam and the top.
# =====================================================================================

def _tri(x):
    """triangle wave -1..+1 (hard-edged hatching without aliases)."""
    return 4.0 * abs(x - math.floor(x + 0.5)) - 1.0


def _smoothstep(e0, e1, x):
    t = max(0.0, min(1.0, (x - e0) / (e1 - e0)))
    return t * t * (3.0 - 2.0 * t)


def _make_noise(seed):
    """R175: periodic VALUE NOISE - hash on an integer grid wrapped modulo
    the period. Seeded, deterministic, seamless by construction."""

    def _h(i, j, p, q):
        # wrapped grid coords -> stable 0..1
        i, j = i % p, j % q
        v = (i * 374761393 + j * 668265263 + seed * 1274126177) & 0xFFFFFFFF
        v = ((v ^ (v >> 13)) * 1274126177) & 0xFFFFFFFF
        return ((v ^ (v >> 16)) & 0xFFFFFFFF) / float(0xFFFFFFFF)

    def noise(s, t, p, q):
        # s,t in [0,1); p x q cells -> value noise, periodic in both axes
        x, y = s * p, t * q
        i, j = int(math.floor(x)), int(math.floor(y))
        fx, fy = x - i, y - j
        fx = fx * fx * (3 - 2 * fx)
        fy = fy * fy * (3 - 2 * fy)
        a = _h(i, j, p, q)
        b = _h(i + 1, j, p, q)
        c = _h(i, j + 1, p, q)
        d = _h(i + 1, j + 1, p, q)
        return (a * (1 - fx) + b * fx) * (1 - fy) + (c * (1 - fx) + d * fx) * fy

    return noise


def _pp(x):
    """ping-pong 0..1..0 - tiles ANY sample seamlessly (mirrored repeat)."""
    x = x % 2.0
    return x if x <= 1.0 else 2.0 - x


def _map_prepare(img):
    """R238 (master prompt): Otsu background detection + soft feathering.
    The background class (decided by the image BORDER vote - a logo lives
    in the middle) becomes an ALPHA channel: 0 = NO displacement, the
    object geometry stays untouched there. The foreground keeps a soft
    grayscale contrast (bump-mapping, not hard displacement edges - the
    layer adhesion survives). Returns an 'L' height map 0..255."""
    from PIL import ImageFilter
    iw, ih = img.size
    hist = [0] * 256
    for v in img.getdata():
        hist[v] += 1
    total = float(iw * ih)
    sum_all = float(sum(i * hist[i] for i in range(256)))
    sum_b = 0.0
    w_b = 0.0
    best_t = 127
    best_var = -1.0
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
        var = w_b * w_f * (m_b - m_f) * (m_b - m_f)
        if var > best_var:
            best_var = var
            best_t = th
    # the border votes which side is background (a full-photo wrap has no
    # border majority - then the brighter half wins, harmless either way)
    pi = img.load()
    border = []
    for x in range(iw):
        border.append(pi[x, 0])
        border.append(pi[x, ih - 1])
    for y in range(ih):
        border.append(pi[0, y])
        border.append(pi[iw - 1, y])
    bmean = sum(border) / float(len(border))
    bg_dark = bmean < best_t
    span = max(1, (255 - best_t) if bg_dark else best_t)
    from PIL import Image as _I238
    out = _I238.new('L', (iw, ih))
    po = out.load()
    for y in range(ih):
        for x in range(iw):
            v = pi[x, y]
            fg = (v > best_t) if bg_dark else (v < best_t)
            if not fg:
                po[x, y] = 0
            else:
                po[x, y] = min(255, 60 + int(abs(v - best_t) * 195 / span))
    return out.filter(ImageFilter.GaussianBlur(1.2))


def _build_patterns(k, n, seed, img, map_mode='TILE', map_pos='CENTER',
                    map_frac=1.0):
    """R175: returns {NAME: fn(s, t) -> -1..+1} with the geometry snapped."""
    rng = random.Random(seed)
    noise = _make_noise(seed)
    two_pi = 2.0 * math.pi

    # pre-rolled per-band randomness for GLITCH / PLANKS / BRICKS stagger
    bands = max(1, n)
    band_rnd = [rng.random() for _ in range(bands * 2 + 4)]
    row_rnd = [rng.random() for _ in range(bands * 2 + 4)]

    pats = {}

    # ---- simple trig families ---------------------------------------------------
    pats['RIDGES'] = (
        lambda s, t: math.sin(two_pi * s * k) *
        (0.72 + 0.28 * math.sin(two_pi * t * 2)))
    pats['WAVES'] = (
        lambda s, t: math.sin(two_pi * (s * k + t * n)) *
        (0.6 + 0.4 * math.sin(two_pi * t * max(1, n // 3))))
    pats['GRID'] = (
        lambda s, t: math.sin(two_pi * s * k) * math.sin(two_pi * t * n))
    pats['HATCH'] = (
        lambda s, t: max(-1.0, min(1.0, 2.2 * _tri(s * k + t * n))) *
        (0.9 + 0.1 * math.sin(two_pi * t)))
    def _checker(s, t):
        # soft-edged checkerboard: cell parity from INTEGER grids (2k x 2n
        # cells -> the wrap lands exactly on a cell boundary), edges eased
        # with smoothstep in BOTH axes (printable, no hard layer steps).
        # R224 name fidelity: cells AND easing on the same 2k x 2n grid
        # (the old k-grid easing left every second boundary a HARD step),
        # and the ease INVERTED - it was 1 at the edges and 0 at the
        # centers, so the pattern showed corner pyramids instead of a
        # chessboard. Now: full +/- at the cell centers, easing to 0 at
        # EVERY boundary (printable, seamless wrap - 2k x 2n are even)
        e_s = 1.0 - _smoothstep(0.62, 0.96,
                                abs(((s * k * 2) % 1.0) - 0.5) * 2)
        e_t = 1.0 - _smoothstep(0.62, 0.96,
                                abs(((t * n * 2) % 1.0) - 0.5) * 2)
        par = (int(s * k * 2) + int(t * n * 2)) % 2
        return (e_s * e_t) * (1.0 if par else -1.0)
    pats['CHECKER'] = _checker

    def _hexcell(s, t):
        # true hex grid on the unrolled (s*k, t*n) plane - seamless because
        # k and the ROW COUNT are integers; rows offset by half a cell
        cols = max(1, k)
        rows = max(1, int(round(n * 2.0 / math.sqrt(3.0))))
        x = s * cols
        y = t * rows
        row = math.floor(y)
        x += 0.5 * (row % 2)
        fx, fy = x - math.floor(x), y - row
        # distance to the nearest hex cell edge (approx as 3 axes)
        d = min(abs(fx - 0.5), abs(fy - 0.5),
                abs((fx - 0.5) * 0.5 + (fy - 0.5) * 0.866))
        return _smoothstep(0.08, 0.30, d) * 2.0 - 1.0
    pats['HONEYCOMB'] = _hexcell
    pats['HEX'] = (
        lambda s, t: (math.sin(two_pi * s * k) * 0.5 +
                      math.sin(two_pi * t * n +
                               math.cos(two_pi * s * k) * 0.5) * 0.5))

    # ---- woven / twisted --------------------------------------------------------
    def _basket(s, t):
        # R224 name fidelity: INTERLACED STRIPS, not pegboard. The old
        # isolated bumps (flat +/-0.55 cells with border dips) read as
        # dots, not as a woven basket. Now every strip is CONTINUOUS
        # along its own direction (rounded spine), arches over the
        # crossing and dips into the shoulders of the strip passing
        # under - the classic over/under weave cue.
        i = s * k
        j = t * n
        col = int(math.floor(i))
        row = int(math.floor(j))
        fx, fy = i - col, j - row
        # rounded strip cross-profiles (0 at the borders, 1 on the spine)
        H = _smoothstep(0.04, 0.32, fy) * (1.0 - _smoothstep(0.68, 0.96, fy))
        V = _smoothstep(0.04, 0.32, fx) * (1.0 - _smoothstep(0.68, 0.96, fx))
        if (col + row) % 2:
            # vertical strip on top: its rounded back crosses OVER the
            # horizontal spine (0.9*V), the horizontal strip's shoulders
            # carve in from the sides
            v = 0.90 * V - 0.55 * (1.0 - H)
        else:
            v = 0.90 * H - 0.55 * (1.0 - V)
        return max(-1.0, min(1.0, v))
    pats['BASKET'] = _basket

    def _rope(s, t):
        # R224 name fidelity: a ROPE is THREE strands by definition. The
        # old strands = k//2 count (10+ on a normal size setting) read as
        # diagonal ridge noise, not rope. tanh() gives flat-topped
        # strands with deep rounded grooves - the twisted-cord look.
        # The size knob still sets the TWIST pitch via n (zsize).
        strands = 3
        turns = max(2, min(48, n))
        v = math.sin(two_pi * (s * strands + t * turns))
        return math.tanh(2.2 * v)
    pats['ROPE'] = _rope

    # ---- boards / bricks --------------------------------------------------------
    def _planks(s, t):
        # R238 (master prompt): VERTICAL boards - lengthwise planks with
        # seeded stagger, seams as grooves and grain stretched UP in Z
        # (the old horizontal rows read as plain stripes).
        ke = k + (k & 1)                # even column count -> clean wrap
        i = s * ke
        col = int(math.floor(i))
        fx = i - col
        jt = row_rnd[col % len(row_rnd)]
        x = (fx + jt) % 1.0
        seam = 1.0 - _smoothstep(0.0, 0.05, min(x, 1.0 - x))
        grain = (noise(s, t, max(2, ke * 6), max(1, n // 3)) - 0.5) * 0.55
        return max(-1.0, min(1.0, 0.5 - 0.95 * seam + grain))
    pats['PLANKS'] = _planks

    def _bricks(s, t):
        rows = max(2, n * 2)
        row = int(math.floor(t * rows))
        x = (s * k + (0.5 if row % 2 else 0.0)) % 1.0
        fy = (t * rows) % 1.0
        face = (_smoothstep(0.0, 0.10, fy) *
                (1.0 - _smoothstep(0.90, 1.0, fy)) *
                (1.0 - _smoothstep(0.0, 0.06, min(x, 1.0 - x))))
        rough = (noise(s, t, k * 3, rows) - 0.5) * 0.35
        return max(-1.0, min(1.0, face * 1.6 - 0.85 + rough))
    pats['BRICKS'] = _bricks

    # ---- R238 (.136ai master prompt): textile, organic, geometric looks --------
    def _knit(s, t):
        # KNIT & CROCHET: nested V-loops in staggered columns - the legs of
        # every stitch arch over the row below (the prompt's sin*cos with
        # phase shift). Reads as a knitted sleeve; the 3 deg auto-tilt
        # breaks the remaining parallelism to the layers.
        ke = k + (k & 1)              # even column count -> clean wrap
        i = s * ke
        col = int(math.floor(i))
        fx = i - col
        j = t * n
        fy = j % 1.0
        fy2 = (fy + (0.5 if col % 2 else 0.0)) % 1.0
        leg = abs(fx - 0.5)
        loop = ((1.0 - _smoothstep(0.10, 0.46, leg))
                * _smoothstep(0.0, 0.28, fy2)
                * (1.0 - _smoothstep(0.62, 0.98, fy2)))
        return max(-1.0, min(1.0, loop * 1.6 - 0.6))
    pats['KNIT'] = _knit

    pats['FLUTED'] = (
        lambda s, t: 0.86 * math.sin(two_pi * s * k)
        + 0.14 * math.sin(two_pi * s * k * 3 + 0.7))

    def _bark(s, t):
        # TREE BARK: vertical cracks - noise stretched hard AROUND the
        # object, calm in Z: the streaks run up; ridged for deep cracks
        v = noise(s, t, max(2, k * 6), max(1, n // 3))
        return max(-1.0, min(1.0, 1.25 * (1.0 - abs(2.0 * v - 1.0)) - 0.4))
    pats['BARK'] = _bark

    def _scales(s, t):
        # REPTILE SCALES: staggered domed shingles (imbricate roof tiles)
        ke = k + (k & 1)
        i = s * ke
        col = int(math.floor(i))
        fx = i - col
        j = t * n
        row = int(math.floor(j))
        fy = j - row
        fx2 = (fx + (0.5 if row % 2 else 0.0)) % 1.0
        d = math.hypot((fx2 - 0.5) * 1.15, (fy - 0.72) * 0.9)
        return max(-1.0, min(1.0,
                             1.5 * (1.0 - _smoothstep(0.18, 0.55, d)) - 0.5))
    pats['SCALES'] = _scales

    def _facets(s, t):
        # GEOMETRIC FACETS: diamond low-poly relief - soft ridge crosses
        fx = abs((s * k % 1.0) - 0.5) + abs((t * n % 1.0) - 0.5)
        return max(-1.0, min(1.0, 1.8 * _smoothstep(0.12, 0.62, fx) - 0.9))
    pats['FACETS'] = _facets

    def _macrame(s, t):
        # MACRAME: two twisted cord families crossing into a net - one
        # winds UP, the other DOWN, the crossings read as knots
        f = max(2, k // 2)
        turns = max(2, min(48, n))
        a = math.sin(two_pi * (s * f + t * turns))
        b = math.sin(two_pi * (s * f - t * turns))
        return max(math.tanh(2.2 * a), math.tanh(2.2 * b))
    pats['MACRAME'] = _macrame


    # ---- noise families (all seeded + periodic) ---------------------------------
    pats['SANDSTONE'] = (
        lambda s, t: (noise(s, t, max(2, k * 2), max(2, n * 2)) - 0.5) * 1.6
        + (noise(s, t, max(2, k * 5), max(2, n * 5)) - 0.5) * 0.6)

    def _concrete(s, t):
        base = (noise(s, t, max(2, k), max(2, n)) - 0.5) * 1.5
        pore = noise(_pp(s * max(2, k // 2)), _pp(t * max(2, n // 2)),
                     3, 3)
        if pore > 0.86:
            base -= (pore - 0.86) * 5.0
        return max(-1.0, min(1.0, base))
    pats['CONCRETE'] = _concrete

    def _clay(s, t):
        # a handful of wide soft dents, placed on the periodic grid
        # (distances wrap in s AND t - the dents close over the seam)
        v = 0.0
        for i in range(3):
            cx = noise(0.3 + i * 0.11, 0.7, 5, 5)
            cy = noise(0.8, 0.2 + i * 0.17, 5, 5)
            dx = min(abs(s - cx), 1.0 - abs(s - cx)) * 2.0
            dy = min(abs(t - cy), 1.0 - abs(t - cy)) * 2.0
            v -= math.exp(-(dx * dx + dy * dy) * 6.0) * 0.9
        return max(-1.0, min(1.0, v + 0.35))
    pats['CLAY'] = _clay

    pats['CREPE'] = (
        lambda s, t: (noise(s, t, max(4, k * 4), max(4, n * 4)) - 0.5) * 1.2
        * (0.6 + 0.4 * math.sin(two_pi * (s * k + t * n))))

    pats['FABRIC'] = (
        lambda s, t: (math.sin(two_pi * s * k) ** 3) *
        (0.85 + 0.15 * noise(s, t, 6, 6)))

    pats['PLUSH'] = (
        lambda s, t: (noise(s, t, max(6, k * 5), max(6, n * 5)) - 0.42) * 1.1)

    def _hilbert(s, t):
        # zig-zag space-filling bands: triangle in s, offset flips per band
        row = int(math.floor(t * n))
        off = 0.5 if row % 2 else 0.0
        v = _tri((s + off) * max(2, k))
        return v * (0.7 + 0.3 * (1.0 - abs(((t * n) % 1.0) - 0.5) * 2))
    pats['HILBERT'] = _hilbert

    def _scratch(s, t):
        # anisotropic: stretched along s (around the object), seeded breaks
        coarse = noise(s, t, max(2, k // 2), max(4, n * 4))
        fine = noise(s, t, max(6, k * 2), max(8, n * 6))
        v = (coarse * 0.65 + fine * 0.35 - 0.5) * 1.7
        return max(-1.0, min(1.0, v))
    pats['SCRATCH'] = _scratch

    def _glitch(s, t):
        # seeded CONSTANT offset per band = stepped 'melted' layers
        band = int(math.floor(t * n))
        r = band_rnd[band % len(band_rnd)]
        r2 = band_rnd[(band + 7) % len(band_rnd)]
        step = (r - 0.5) * 1.6 if r2 > 0.45 else 0.0
        fy = (t * n) % 1.0
        lip = _smoothstep(0.0, 0.08, fy) * (1 - _smoothstep(0.92, 1.0, fy))
        return max(-1.0, min(1.0, step * lip))
    pats['GLITCH'] = _glitch

    # ---- the image wrap ---------------------------------------------------------
    if img is not None:
        iw, ih = img.size
        # R238 (master prompt): ONCE = the picture wraps around exactly one
        # time, aspect-true, positioned TOP/CENTER/BOTTOM (t is the global
        # Z fraction here - apply_texture forces n=1 for ONCE). Outside the
        # picture: flat 0 (the Otsu background mask makes the seam
        # invisible). TILE = the endless mirrored wrap of R175.
        _v0238 = {'TOP': 1.0 - map_frac,
                  'BOTTOM': 0.0}.get(map_pos, (1.0 - map_frac) / 2.0)

        def _map(s, t):
            # hin + mirrored rueckweg over ONE circumference = seamless at
            # the seam (pixel 0 meets pixel 0); same in Z -> flush at the top
            if map_mode == 'ONCE':
                if map_frac <= 0.0 or t < _v0238 or t > _v0238 + map_frac:
                    return 0.0
                u = s % 1.0
                v = (t - _v0238) / map_frac
            else:
                u = _pp(2.0 * s)
                v = _pp(2.0 * t)
            px = min(iw - 1, int(u * iw))
            py = min(ih - 1, int(v * ih))
            lum = img.getpixel((px, py))
            if isinstance(lum, tuple):
                lum = (lum[0] * 299 + lum[1] * 587 + lum[2] * 114) / 1000.0
            return (lum / 255.0) * 2.0 - 1.0
        pats['MAP'] = _map

    return pats


PATTERN_NAMES = ('RIDGES', 'WAVES', 'GRID', 'HATCH', 'CHECKER', 'HEX',
                 'HONEYCOMB', 'BASKET', 'ROPE', 'PLANKS', 'BRICKS',
                 'SANDSTONE', 'CONCRETE', 'CLAY', 'CREPE', 'FABRIC',
                 'PLUSH', 'HILBERT', 'SCRATCH', 'GLITCH', 'KNIT', 'FLUTED',
                 'BARK', 'SCALES', 'FACETS', 'MACRAME', 'MAP')

# R238 (.136ai master prompt): the AUTO TILT - pattern rows never run
# parallel to the print layers (that parallelism is why everything read as
# 'stripes' and why layer lines stayed visible). The tilt is a HELICAL
# shift of m integer cells over the object height: the seam stays perfect
# (s=0 and s=1 differ by exactly k integer cells) and the top closes (the
# total shift m is an integer). Angles in degrees, 0 = self-aligned (the
# pattern carries its own direction: rope lay, vertical flutes/bark,
# crossing facets) - everything else gets the 2 degree micro-tilt that
# optically melts the layer lines away.
PATTERN_TILT = {
    'ROPE': 0.0, 'MACRAME': 0.0, 'FLUTED': 0.0, 'BARK': 0.0,
    'FACETS': 0.0, 'PLANKS': 0.0, 'MAP': 0.0,
    'KNIT': 3.0, 'HILBERT': 4.0, 'BASKET': 30.0,
}


def apply_texture(src, out_dir=None, mode='FUZZY', fuzzy_thick=0.3,
                  fuzzy_density=100.0, bump_pattern='RIDGES', bump_scale=10.0,
                  bump_amp=0.35, direction='OUT', bed=None, version=1,  # version: retired (R158, folder-global auto)
                  seed=91, zsize=None, map_file=None,
                  map_mode='TILE', map_pos='CENTER', progress=None):
    """Returns (new_path, info). Raises ValueError on bad parameters.

    R175 parameter semantics (the LCD speaks these names):
      bump_scale = 'size around' guideline in mm  -> snapped to k ridges
      zsize      = 'Z size' guideline in mm       -> snapped to n repeats
      bump_amp   = 'depth' in mm (0.05..1.0)
      seed       = deterministic randomness (noise patterns, fuzzy)
      map_file   = image for PATTERN=MAP (grayscale wrap)
    """
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
    if bump_pattern not in PATTERN_NAMES:
        raise ValueError('pattern must be one of %s (got %r)'
                         % (', '.join(PATTERN_NAMES), bump_pattern))
    if not (3.0 <= float(bump_scale) <= 80.0):
        raise ValueError('pattern size %.1fmm out of range (3..80)'
                         % float(bump_scale))
    if zsize is None:
        zsize = bump_scale
    if not (0.5 <= float(zsize) <= 200.0):
        raise ValueError('Z size %.1fmm out of range (0.5..200)' % float(zsize))
    if not (0.05 <= float(bump_amp) <= 1.0):
        raise ValueError('pattern depth %.2fmm out of range (0.05..1.0)'
                         % float(bump_amp))
    if not os.path.isfile(src):
        raise ValueError('source file not found: %s' % src)

    img = None
    if bump_pattern == 'MAP':
        if not map_file:
            raise ValueError('PATTERN=MAP needs an image '
                             '(pick one in the SD browser, it copies to the '
                             'main folder)')
        try:
            from PIL import Image                       # lazy (Pi-safe)
        except ImportError:
            raise ValueError('MAP needs Pillow (sudo apt install '
                             'python3-pil) - or pick a different pattern')
        # R237 (.136ah field report 'cannot load images as MAP'): the map
        # name can be a bare root-copy name or a subfolder pick while the
        # source lives elsewhere - try the literal relative first, then the
        # basename next to the source (the watcher passes an ABSOLUTE path
        # since R237, this covers direct CLI callers).
        _dn237 = os.path.dirname(os.path.abspath(src))
        _cands237 = ([map_file] if os.path.isabs(map_file) else
                     [os.path.join(_dn237, map_file),
                      os.path.join(_dn237, os.path.basename(map_file))])
        _mp = next((c for c in _cands237 if os.path.isfile(c)), _cands237[0])
        if not os.path.isfile(_mp):
            raise ValueError('map image not found: %s (tried %s)'
                             % (map_file, ' | '.join(_cands237)))
        # R238 (master prompt): Otsu background -> alpha, soft feathered
        # foreground (bump-mapping - layer adhesion survives)
        img = _map_prepare(Image.open(_mp).convert('L'))
        map_mode = str(map_mode).upper()
        map_pos = str(map_pos).upper()
        if map_mode not in ('TILE', 'ONCE'):
            raise ValueError('MAP mode %r must be TILE or ONCE' % map_mode)
        if map_pos not in ('TOP', 'CENTER', 'BOTTOM'):
            raise ValueError('MAP position %r must be TOP, CENTER or BOTTOM'
                             % map_pos)

    out_dir = out_dir or os.path.dirname(os.path.abspath(src))
    if bed is None:
        bed = (0.0, -3.0, 220.0, 217.0)      # real Ender-3 plate (manual ch.23)

    base = os.path.basename(src)
    stem = base[:-6] if base.lower().endswith('.gcode') else base
    # R158 (.118): version FIRST + ONE folder-global number, mirroring
    # r2_postproc._next_gen_version (kept local on purpose - this script
    # stays importable without the 18k-line post-processor). A new-format
    # source (Vnn_Name.gcode, or R158's 00_Vnn_Name.gcode) contributes just
    # its Name part; a legacy source (00_Name_Vnn.gcode) loses its tail
    # version AND its old 00_ prefix - the output carries exactly one Vnn_
    # head (R160 .120: the 00_ prefix is gone, 3 characters back).
    _m158 = re.match(r'^(?:00_)?V\d+_(.+)$', stem)
    if _m158:
        stem = _m158.group(1)
    else:
        stem = re.sub(r'_V\d+$', '', stem)
        stem = stem[3:] if stem.startswith('00_') else stem
    _hi158 = 0
    try:
        for _p158 in os.listdir(out_dir):
            _mm158 = re.match(r'^(?:00_)?V(\d+)[a-z]?_', _p158)
            if _mm158:
                _hi158 = max(_hi158, int(_mm158.group(1)))
                continue
            _mm158 = re.search(r'_V(\d+)\.gcode$', _p158)
            if _mm158 and _p158.startswith('00_'):
                _hi158 = max(_hi158, int(_mm158.group(1)))
    except OSError:
        pass
    if _hi158 >= 99:
        raise ValueError('all V numbers 01..99 are used in this folder - '
                         'clean up first (a texture never silently '
                         'overwrites)')
    fname = 'V%02d_%s_TX.gcode' % (_hi158 + 1, stem)
    # R160b (.120 field): never overwrite - same number + a small letter if
    # the exact name appeared meanwhile (mirrors r2_postproc._dedupe_gen_fname)
    if os.path.exists(os.path.join(out_dir, fname)):
        _m160 = re.match(r'^(V\d+)(_.*)$', fname)
        if _m160:
            for _c160 in 'bcdefghijklmnopqrstuvwxyz':
                _cand160 = '%s%s%s' % (_m160.group(1), _c160, _m160.group(2))
                if not os.path.exists(os.path.join(out_dir, _cand160)):
                    fname = _cand160
                    break
    out = os.path.join(out_dir, fname)
    if os.path.abspath(out) == os.path.abspath(src):
        raise ValueError('texture output name collides with the source - '
                         'refusing')

    rng = random.Random(seed)
    sign = 1.0 if direction == 'OUT' else -1.0
    sig = float(bump_amp)
    dens = float(fuzzy_density) / 100.0

    # ---- R175 PASS 1: measure the geometry (streaming, no buffers) -----------
    # center: EXCLUDE_OBJECT CENTER lines if the file has them, else the
    # outer-wall vertex centroid. Circumference: mean chord sum per layer.
    # Height: z span of the outer wall. From those: k ridges, n Z-repeats.
    # SMOKE FIX: Z is tracked on EVERY move (slicers put the layer Z in a
    # separate travel line - tracking it only on extruding moves measured
    # 40x the circumference and a 0.2mm height on the vase test file).
    centers = []
    sx = sy = cnt = 0.0
    chord = 0.0
    # R175 litho fallback: files WITHOUT any wall marker (lithophanes are
    # all SURFACE/INFILL) still deserve a real texture - every extrusion
    # path counts as the geometry then. Twin statistics decide later.
    ax = ay = acnt = 0.0
    achord = 0.0
    alast_z = None
    alayers = 0
    aminz = 1e9
    amaxz = -1e9
    any_outer = False       # the file ever claimed an outer wall
    cur_z = None            # last Z seen on ANY move line
    last_extrude_z = None   # last Z an EXTRUDING outer-wall move ran at
    layers_seen = 0
    minz = 1e9
    maxz = -1e9
    px2 = py2 = None
    cur_type = ''
    cur_outer = False
    cur_inner = False       # R224 task 15: inner walls follow the embossing
    wind_o = {}             # per-Z shoelace winding of the outer wall
    wind_i = {}             # per-Z shoelace winding of the inner wall
    with open(src, errors='replace') as fi:
        for line in fi:
            ls = line.rstrip('\n')
            me = _EOD_CENTER.match(ls)
            if me:
                centers.append((float(me.group(1)), float(me.group(2))))
                continue
            m = _TYPE.match(ls)
            if m:
                cur_type = m.group(1).strip().lower()
                cur_outer = _is_outer_wall(cur_type)
                cur_inner = _is_inner_wall(cur_type)
                if cur_outer:
                    any_outer = True
                continue
            _ma152 = _APPLY152.match(ls)
            if _ma152:
                cur_type = _ma152.group(1).strip().lower()
                cur_outer = _is_outer_wall(cur_type)
                cur_inner = _is_inner_wall(cur_type)
                if cur_outer:
                    any_outer = True
                continue
            # R175: geometry pass 1 must ALSO see G2/G3 outer-wall arcs -
            # a vase sliced with arc fitting has no G1 wall vertex at all,
            # so circumference/center/height came out empty and the whole
            # library refused the file. Arcs are flattened into points here
            # with the same _arc_points pass 2 uses (chord 0.35mm).
            g = _parse_move(ls)
            mpts = []           # [(x, y)] points this command moves to
            extruding = False
            if g is not None:
                if g[3] is not None:
                    cur_z = g[3]
                # G0 too: a G0 X.. Y.. sets the position the first arc
                # of the wall starts from (lost that in the first draft -
                # arc-only vases measured zero circumference)
                if g[0] in ('G0', 'G1') and g[1] is not None:
                    mpts = [(g[1], g[2] if g[2] is not None else py2)]
                    extruding = (g[4] is not None and g[4] > _MIN_E)
            else:
                ga = _parse_arc(ls)
                if ga is not None:
                    if ga[3] is not None:
                        cur_z = ga[3]
                    if ga[1] is not None:
                        ay = ga[2] if ga[2] is not None else py2
                        if ay is not None:
                            if px2 is not None:
                                apts = _arc_points(px2, py2, ga[1], ay,
                                                   i=ga[4], j=ga[5], rr=ga[6],
                                                   cw=(ga[0] == 'G2'))
                                mpts = apts or [(ga[1], ay)]
                            else:
                                mpts = [(ga[1], ay)]
                            extruding = (ga[7] is not None and ga[7] > _MIN_E)
            for x, y in mpts:
                if extruding:
                    ax += x
                    ay += y
                    acnt += 1
                    if cur_z is not None:
                        if alast_z is None or \
                                abs(cur_z - alast_z) > 1e-6:
                            alayers += 1
                            alast_z = cur_z
                        aminz = min(aminz, cur_z)
                        amaxz = max(amaxz, cur_z)
                    if px2 is not None:
                        achord += math.hypot(x - px2, y - py2)
                if cur_outer and extruding:
                    sx += x
                    sy += y
                    cnt += 1
                    z_here = cur_z
                    if z_here is not None:
                        if last_extrude_z is None or \
                                abs(z_here - last_extrude_z) > 1e-6:
                            layers_seen += 1
                            last_extrude_z = z_here
                        minz = min(minz, z_here)
                        maxz = max(maxz, z_here)
                    if px2 is not None:
                        chord += math.hypot(x - px2, y - py2)
                        _zk = round(z_here, 3) if z_here is not None else -1.0
                        wind_o[_zk] = wind_o.get(_zk, 0.0) + (px2 * y - x * py2)
                elif cur_inner and extruding and px2 is not None:
                    _zk = round(cur_z, 3) if cur_z is not None else -1.0
                    wind_i[_zk] = wind_i.get(_zk, 0.0) + (px2 * y - x * py2)
                px2, py2 = x, y
    all_is_wall = False
    if cnt < 8 and not any_outer and acnt >= 8:
        # no wall marker ANYWHERE (lithophanes, raw extrusion art): the
        # whole extrusion body becomes the texture surface
        all_is_wall = True
        sx, sy, cnt = ax, ay, acnt
        chord = achord
        layers_seen = alayers
        minz, maxz = aminz, amaxz
    if cnt < 8:
        raise ValueError('no outer wall found in %s - the texture only '
                         'works on files with outer walls (or files without '
                         'any type markers at all)' % base)
    # R224 task 15: if the slicer runs an inner loop the OPPOSITE way
    # round (a strength option in some slicers), a naive same-value shift
    # would push it AWAY from the outer wall - the per-layer winding
    # comparison catches that and flips the inner displacement back.
    flip_by_z = {}
    for _zk, _wi in wind_i.items():
        _wo = wind_o.get(_zk)
        if _wo is not None and _wi and _wo and (_wo > 0) != (_wi > 0):
            flip_by_z[_zk] = -1.0
    if centers:
        cx = sum(c[0] for c in centers) / len(centers)
        cy = sum(c[1] for c in centers) / len(centers)
        src_center = 'exclude-object center%s' % (
            's' if len(centers) > 1 else '')
    else:
        cx, cy = sx / cnt, sy / cnt
        src_center = 'wall centroid'
    # ---- R231: loop-length pre-pass ---------------------------------------
    # The arc-anchored mapping needs every wall loop's own length BEFORE the
    # emission shifts its vertices. This walk mirrors the emission's gating
    # EXACTLY (same type aliases, same _MIN_E, same arc flattening) - the
    # loops it finds are the loops the emission walks, index by index.
    def _scan_loops231():
        lens = []
        cur_len = 0.0
        cur_type_l = ''
        cur_outer_l = False
        cur_inner_l = False
        px_l = py_l = None
        with open(src, errors='replace') as f:
            for line in f:
                ls = line.rstrip('\n')
                m = _TYPE.match(ls)
                if m:
                    cur_type_l = m.group(1).strip().lower()
                    cur_outer_l = _is_outer_wall(cur_type_l)
                    cur_inner_l = _is_inner_wall(cur_type_l)
                    if cur_len > 0.0:
                        lens.append(cur_len)
                        cur_len = 0.0
                    continue
                ma = _APPLY152.match(ls)
                if ma:
                    cur_type_l = ma.group(1).strip().lower()
                    cur_outer_l = _is_outer_wall(cur_type_l)
                    cur_inner_l = _is_inner_wall(cur_type_l)
                    if cur_len > 0.0:
                        lens.append(cur_len)
                        cur_len = 0.0
                    continue
                if ls.startswith(';LAYER_CHANGE'):
                    if cur_len > 0.0:
                        lens.append(cur_len)
                        cur_len = 0.0
                    continue
                gated = (cur_outer_l or all_is_wall
                         or (cur_inner_l and mode == 'BUMPS'))
                g = _parse_move(ls)
                if g is not None and g[1] is not None:
                    if (g[0] == 'G1' and gated and g[4] is not None
                            and g[4] > _MIN_E):
                        if px_l is not None:
                            cur_len += math.hypot(g[1] - px_l, g[2] - py_l)
                        px_l, py_l = g[1], g[2]
                    else:
                        if cur_len > 0.0:
                            lens.append(cur_len)
                            cur_len = 0.0
                        px_l, py_l = g[1], g[2]
                    continue
                ga = _parse_arc(ls)
                if ga is not None and ga[1] is not None and px_l is not None:
                    if (gated and ga[7] is not None and ga[7] > _MIN_E):
                        pts = _arc_points(px_l, py_l, ga[1], ga[2], ga[4],
                                          ga[5], ga[6], cw=(ga[0] == 'G2'))
                        if pts:
                            _allp = [(px_l, py_l)] + pts[:-1]
                            cur_len += sum(
                                math.hypot(b[0] - a[0], b[1] - a[1])
                                for a, b in zip(_allp, pts))
                        else:
                            cur_len += math.hypot(ga[1] - px_l,
                                                  ga[2] - py_l)
                    else:
                        if cur_len > 0.0:
                            lens.append(cur_len)
                            cur_len = 0.0
                    px_l, py_l = ga[1], ga[2]
        if cur_len > 0.0:
            lens.append(cur_len)
        return lens

    loops231 = _scan_loops231()
    if layers_seen < 1:
        layers_seen = 1
    # R236 (.136af field log): chord/layers_seen breaks on SPIRAL VASES -
    # there Z rises with (almost) every move, so layers_seen counts MOVES
    # (~45k on the field rose, 242 real layers) and 'circum' degenerated
    # into the mean SEGMENT length (2.9mm). k = round(2.9/scale) = 1 for
    # every preset = ONE pattern wave around the object = a sinus with a
    # zero crossing: the structure faded out across the whole back side
    # ('the texture slowly disappears'). The R231 loop pre-pass already
    # measures the real wall loops (one spiral winding / one closed
    # contour per segment) - its MEDIAN is the true circumference.
    _ll236 = sorted(l for l in loops231 if l > 1.0)
    circum = _ll236[len(_ll236) // 2] if len(_ll236) >= 2 \
        else chord / layers_seen
    if circum < 1.0:
        circum = 2.0 * math.pi * 8.0     # absurd fallback: 8mm radius
    height = max(0.2, maxz - minz) if maxz > minz else 0.2
    # R186: honesty rule - a BUMP pattern is placed BY HEIGHT; a file with
    # no Z information at all cannot carry one. The old code silently
    # wrote an untextured copy (shifted=0). FUZZY needs no Z and stays.
    if mode == 'BUMPS' and minz > maxz:
        raise ValueError('no Z moves found in %s - a bump pattern needs '
                         'the layer heights (FUZZY works without Z)'
                         % base)
    k = max(1, min(240, int(round(circum / float(bump_scale)))))
    n = max(1, min(400, int(round(height / float(zsize)))))
    # R238: MAP ONCE = one wrap, aspect-true, positioned - t becomes the
    # GLOBAL Z fraction (n=1), the picture height is a physical fraction
    # of the object height (clamped to fit)
    map_frac = 1.0
    if mode == 'BUMPS' and bump_pattern == 'MAP' and img is not None \
            and str(map_mode).upper() == 'ONCE':
        n = 1
        if img.size[0] > 0:
            map_frac = min(1.0, (circum * img.size[1] / img.size[0])
                           / max(0.1, height))
    eff_size = circum / k
    eff_zsize = height / n

    # R238 (master prompt): the AUTO TILT - see PATTERN_TILT above. The
    # helical shift keeps the seam (integer k cells apart) AND the flush
    # top (integer total shift) while the lattice leaves the layer plane.
    _tilt_deg = PATTERN_TILT.get(bump_pattern, 2.0)
    m238 = 0
    if _tilt_deg > 0.0 and circum > 0 and height > 0:
        m238 = max(1, int(round(
            height * k / (circum * math.tan(math.radians(_tilt_deg))))))
    tilt_eff = (math.degrees(math.atan(height * k / (m238 * circum)))
                if m238 else 0.0)

    pats = _build_patterns(k, n, int(seed), img,
                           map_mode=str(map_mode).upper(),
                           map_pos=str(map_pos).upper(),
                           map_frac=map_frac)
    pattern_fn = pats[bump_pattern]

    def pattern(x, y, z, s_arc=None):
        """R175: cylinder coordinates around the OBJECT -> seamless.
        R231: s_arc (if given) is the ARC-ANCHORED loop coordinate (see the
        module header) - it replaces the raw angle fraction wherever the
        wall runs inward, so pattern cells keep their physical size on
        concave sections (vase notches) instead of stretching."""
        if s_arc is not None:
            s = s_arc % 1.0
        else:
            th = math.atan2(y - cy, x - cx)
            s = (th / (2.0 * math.pi)) % 1.0
        t = (((z - minz) * n / height) % 1.0) if height > 0 else 0.0
        # R238: the helical tilt - s drifts by m238/k wraps over the full
        # height (seam-safe: integer cells; top-flush: integer shift)
        if m238:
            s = (s + m238 * (((z - minz) / height) if height > 0 else 0.0)
                 / k) % 1.0
        return pattern_fn(s, t)

    stats = {'moves': 0, 'shifted': 0, 'clamped': 0, 'layers': 0, 'arcs': 0,
             'inner_shifted': 0, 'm204_scrub': 0}
    cur_type = ''
    cur_outer = False       # R152: alias-normalized outer-wall check
    cur_inner = False       # R224 task 15: BUMPS lets inner walls follow
    t0 = time.time()
    # px/py = None until the first move is seen: a vertex with no known
    # approach direction gets NO offset (same rule as zero-length moves -
    # never invent a direction from the home position)
    px = py = None
    # R186: live Z for the EMISSION pass (see _shift_txt) - updated by every
    # move/arc line that carries Z, exactly like the stats pass does
    cur_z_e = None
    # R95: E bookkeeping for arc flattening - chords must carry exactly the
    # arc's extrusion (relative: distributed by chord length; absolute:
    # interpolated from the last E to the arc's end value)
    e_rel = False
    last_e = 0.0

    # R231 emission-side loop bookkeeping: i = current loop index into
    # loops231, arc = mm walked inside it, anchor = absolute angle fraction
    # at its first vertex, z = the Z the loop prints at (layer-jump guard)
    _st231 = {'i': 0, 'arc': 0.0, 'anchor': None, 'len': None, 'z': None,
              'fb': 0}
    # R224/R231: what the OUTER wall's arc-anchored s was at each angle of
    # the current layer - the inner wall samples THIS (its own s runs
    # mirrored on reversed windings and would shear the wall pair apart)
    _sout231 = {}

    def _abin231(x, y):
        return int((math.atan2(y - cy, x - cx) / (2.0 * math.pi)) % 1.0
                   * 360.0)

    def _sout_put231(zz, x, y, sv):
        if sv is not None and zz is not None:
            _sout231[(round(zz, 3), _abin231(x, y))] = sv

    def _sout_get231(zz, x, y):
        if zz is None:
            return None
        _zk = round(zz, 3)
        _b = _abin231(x, y)
        for _d in (0, 1, -1, 2, -2):
            _v = _sout231.get((_zk, (_b + _d) % 360))
            if _v is not None:
                return _v
        return None

    def _loop_close231():
        if _st231['arc'] > 0.0:
            _st231['i'] += 1
            _st231['arc'] = 0.0
            _st231['anchor'] = None
            _st231['len'] = None

    def _s231(x, y, zz, ln):
        """R231: arc-anchored s for the END vertex of a gated move of
        length ln. None -> the caller falls back to the classic angle
        fraction (desync or a degenerate loop - never crashes, never
        stretches the file's own bookkeeping)."""
        if zz is not None:
            if _st231['z'] is not None and abs(zz - _st231['z']) > 0.05:
                # layer jump inside a gapless stream (no travel, no
                # ;LAYER_CHANGE): close the loop so its cells stay real
                _loop_close231()
            _st231['z'] = zz
        if _st231['arc'] <= 0.0:
            _st231['anchor'] = math.atan2(y - cy, x - cx) / (2.0 * math.pi)
            _st231['len'] = (
                loops231[_st231['i']]
                if _st231['i'] < len(loops231)
                and loops231[_st231['i']] > 1.0 else None)
        _L231 = _st231['len']
        if _L231 is None or _st231['anchor'] is None:
            _st231['fb'] += 1
            return None
        return (_st231['anchor'] + (_st231['arc'] + ln) / _L231) % 1.0

    def _shift_txt(txt, x, y, z, inner=False, s_arc=None):
        """R91 displacement on ONE move line -> possibly shifted text.
        Reads px/py from the enclosing scope (approach direction).
        R224 task 15: inner=True lets an inner-wall move FOLLOW the outer
        wall's embossing (BUMPS mode only - FUZZY stays Orca-honest and
        jitters the outer wall alone).
        R231: s_arc = the arc-anchored loop coordinate of the END vertex
        (None -> the classic angle fraction, the safe fallback)."""
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
            # R186 FIX: fall back to the LAST Z SEEN IN THE EMISSION PASS -
            # normal slicer files carry Z only on the layer-change move, so
            # the old 'z if ... else 0.0' evaluated the whole pattern at
            # height 0 (one fixed ring, Z variation lost) and Z-less files
            # textured NOTHING at all (silent no-op)
            zz = z if z is not None else (
                cur_z_e if cur_z_e is not None else 0.0)
            if inner and s_arc is not None:
                # R224/R231: FOLLOW THE OUTER WALL - sample the s the OUTER
                # loop used at THIS angle. The inner loop's own arc-anchored
                # s runs MIRRORED on reversed windings (same angle, other
                # direction) and on notched walls the two loops' arc maps
                # differ anyway - the pair would shear apart (field: inner
                # wall cut past the outer). No outer sample at this angle
                # (inner printed first) -> classic angle fraction below.
                s_arc = _sout_get231(zz, x, y)
            amp = pattern(x, y, zz, s_arc=s_arc) * sig * sign
            if inner:
                # same angle -> same pattern value as the outer wall:
                # the stack moves as one, contact kept. The flip realigns
                # opposite-running inner loops (see flip_by_z above).
                amp *= flip_by_z.get(round(zz, 3), 1.0)
            nx = ox * amp
            ny = oy * amp
        if nx or ny:
            nx, ny = round(x + nx, 3), round(y + ny, 3)
            if not (bed[0] <= nx <= bed[2] and bed[1] <= ny <= bed[3]):
                nx = max(bed[0], min(nx, bed[2]))
                ny = max(bed[1], min(ny, bed[3]))
                stats['clamped'] += 1
            txt = re.sub(r'X[\d.\-]+', 'X%.3f' % nx, txt, count=1)
            txt = re.sub(r'Y[\d.\-]+', 'Y%.3f' % ny, txt, count=1)
            stats['shifted'] += 1
            if inner:
                stats['inner_shifted'] += 1
        return txt

    with open(src, errors='replace') as fi, open(out, 'w') as fo:
        fo.write('; %s applied to %s: mode %s%s\n' % (
            TAG, base, mode,
            ' thick %.2f density %.0f%%' % (float(fuzzy_thick),
                                            float(fuzzy_density))
            if mode == 'FUZZY' else
            ' %s size %.1f z %.1f depth %.2f %s' % (
                bump_pattern, float(bump_scale), float(zsize),
                float(bump_amp), direction)))
        fo.write('; R175 seamless: %d ridges around (effective %.1fmm) x '
                 '%d repeats in Z (effective %.1fmm) - the seam closes, '
                 'the texture runs endless and ends flush at the top\n'
                 % (k, eff_size, n, eff_zsize))
        fo.write('; center from %s at %.1f,%.1f - object height %.1fmm, '
                 'mean circumference %.1fmm, seed %d\n'
                 % (src_center, cx, cy, height, circum, int(seed)))
        fo.write('; fuzzy scatters / bumps displace ONLY outer-wall vertices '
                 '- tags, features, E and Z stay untouched\n')
        fo.write('; R95: G2/G3 outer-wall arcs are flattened into textured '
                 'chords (arc-fitted files get a seamless all-around texture)\n')
        fo.write('; R231 arc-anchored: %d wall loop(s) measured - every '
                 'pattern cell keeps its physical size, walls that run '
                 'inward (notches, cut-outs) carry the structure too\n'
                 % len(loops231))
        if mode == 'BUMPS' and wind_i:
            fo.write('; R224: inner walls follow the embossing - they no '
                     'longer cap the valleys (invisible behind the surface) '
                     'and keep wall contact\n')
        if all_is_wall:
            fo.write('; R175 fallback: no wall markers in this file - the '
                     'texture runs on ALL extrusion paths (lithophane mode)\n')
        _led240 = [0, 0]                # R240: [bytes seen, lines seen]
        _led240_sz = max(1, os.path.getsize(src))
        for line in fi:
            # R240: LED progress bar for this texture job (best effort)
            if progress is not None:
                _led240[0] += len(line)
                _led240[1] += 1
                if not _led240[1] % 4096:
                    progress(min(99, 100 * _led240[0] // _led240_sz))
            # R237 (.136ah field report): legacy '_M204 ...' lines from the
            # slicer profile die as 'Unknown command' - rewrite them to the
            # intercepted M204 while we stream the file anyway.
            if line.startswith('EXCLUDE_OBJECT_DEFINE') and '], [' in line:
                # R239 (.136ai field log): heal a spaced POLYGON while we
                # stream the file anyway - the mirror tool emitted them and
                # every start of such a file died as 'Malformed command'
                line = line.replace('], [', '],[')
            _r240 = _M204SET_SCRUB.sub(
                r'\1M204 S\2', _M204_SCRUB.sub(r'\1M204\2', line))
            if _r240 != line:
                line = _r240
                stats['m204_scrub'] += 1
            ls = line.rstrip('\n')
            m = _TYPE.match(ls)
            if m:
                cur_type = m.group(1).strip().lower()
                cur_outer = _is_outer_wall(cur_type)
                cur_inner = _is_inner_wall(cur_type)
                _loop_close231()      # R231: a type switch ends the loop
                fo.write(ls + '\n')
                continue
            # R152: the r2-postproc injects the CANONICAL type right after
            # every ;TYPE: line (APPLY_TYPE TYPE=WALL-OUTER ...) - trust it
            # too, it already normalized the slicer dialect
            _ma152 = _APPLY152.match(ls)
            if _ma152:
                cur_type = _ma152.group(1).strip().lower()
                cur_outer = _is_outer_wall(cur_type)
                cur_inner = _is_inner_wall(cur_type)
                _loop_close231()      # R231: a type switch ends the loop
            if ls.startswith(';LAYER_CHANGE'):
                stats['layers'] += 1
                _loop_close231()      # R231: one loop per layer
            elif ls == 'M83':
                e_rel = True
            elif ls == 'M82':
                e_rel = False
            elif ls.startswith('G92'):
                me92 = re.match(r'^G92(?:\s+E(-?[\d.]+))?', ls)
                if me92 and me92.group(1) is not None:
                    last_e = float(me92.group(1))
            g = _parse_move(ls)
            if g is not None and g[3] is not None:
                cur_z_e = g[3]           # R186: emission-pass Z tracking
            if (g and g[0] == 'G1' and (cur_outer or all_is_wall
                                        or (cur_inner and mode == 'BUMPS'))
                    and g[4] is not None and g[4] > _MIN_E and g[1] is not None):
                x, y = g[1], g[2]
                z = g[3]
                _zz231 = z if z is not None else cur_z_e
                _ln231 = math.hypot(x - px, y - py) if px is not None else 0.0
                _sar231 = _s231(x, y, _zz231, _ln231)   # R231 arc-anchored s
                if cur_outer:
                    _sout_put231(_zz231, x, y, _sar231)
                fo.write(_shift_txt(ls, x, y, z,
                                    inner=(cur_inner and not cur_outer
                                           and mode == 'BUMPS'),
                                    s_arc=_sar231) + '\n')
                _st231['arc'] += _ln231
                px, py = x, y
                last_e = g[4]
                continue
            # ---- R95: outer-wall G2/G3 arcs -> short G1 chords, textured ---
            ga = _parse_arc(ls)
            if ga is not None and ga[3] is not None:
                cur_z_e = ga[3]           # R186: emission-pass Z tracking
            if (ga and (cur_outer or all_is_wall
                        or (cur_inner and mode == 'BUMPS')) and ga[7] is not None
                    and ga[7] > _MIN_E and px is not None):
                x1, y1 = ga[1], ga[2]
                z1 = ga[3]
                pts = _arc_points(
                    px, py, x1, y1, ga[4], ga[5], ga[6],
                    cw=(ga[0] == 'G2'))
                if pts:
                    stats['arcs'] += 1
                    e_arc = ga[7]
                    _all = [(px, py)] + pts[:-1]
                    arc_len = sum(math.hypot(b[0] - a[0], b[1] - a[1])
                                  for a, b in zip(_all, pts))
                    f_txt = (' F%g' % ga[8]) if ga[8] else ''
                    for (ax, ay), (qx, qy) in zip(_all, pts):
                        cl = math.hypot(qx - ax, qy - ay)
                        frac = (cl / arc_len) if arc_len > 1e-9 else 0.0
                        if e_rel:
                            ec = e_arc * frac
                        else:
                            ec = last_e + (e_arc - last_e) * frac
                        ch = 'G1 X%.3f Y%.3f E%.5f%s' % (qx, qy, ec, f_txt)
                        _zz231 = z1 if z1 is not None else cur_z_e
                        _sar231 = _s231(qx, qy, _zz231, cl)
                        if cur_outer:
                            _sout_put231(_zz231, qx, qy, _sar231)
                        fo.write(_shift_txt(
                            ch, qx, qy, z1,
                            inner=(cur_inner and not cur_outer
                                   and mode == 'BUMPS'),
                            s_arc=_sar231) + '\n')
                        _st231['arc'] += cl
                        if not e_rel:
                            last_e = ec
                    px, py = x1, y1
                    if not e_rel:
                        last_e = e_arc
                    continue
                # unresolvable arc geometry -> untouched passthrough (below)
            gm = _parse_move(ls)
            if gm and gm[1] is not None:
                _loop_close231()   # R231: a travel ends the wall loop
                px, py = gm[1], gm[2]
                if gm[4] is not None:
                    last_e = gm[4]
            fo.write(ls + '\n')

    info = {'file': fname, 'src': base, 'mode': mode, 'version': _hi158 + 1,
            'fuzzy_thick': float(fuzzy_thick) if mode == 'FUZZY' else 0.0,
            'fuzzy_density': float(fuzzy_density) if mode == 'FUZZY' else 0.0,
            'pattern': bump_pattern if mode == 'BUMPS' else '',
            'scale': float(bump_scale), 'amp': float(bump_amp),
            'zsize': float(zsize), 'seed': int(seed),
            'direction': direction,
            'ridges': k, 'z_repeats': n, 'all_paths': all_is_wall,
            'eff_size': round(eff_size, 2), 'eff_zsize': round(eff_zsize, 2),
            'height': round(height, 1), 'circumference': round(circum, 1),
            'center': (round(cx, 1), round(cy, 1)),
            'shifted': stats['shifted'], 'inner_shifted': stats['inner_shifted'],
            'outer_moves': stats['moves'], 'clamped': stats['clamped'],
            'layers': stats['layers'], 'arcs_flattened': stats['arcs'],
            'arc_loops': len(loops231), 'arc_fallback': _st231['fb'],
            'm204_scrub': stats['m204_scrub'],
            'tilt': round(tilt_eff, 1), 'tilt_turns': m238,
            'map_mode': (str(map_mode).upper()
                         if mode == 'BUMPS' and bump_pattern == 'MAP' else ''),
            'map_pos': (str(map_pos).upper()
                        if mode == 'BUMPS' and bump_pattern == 'MAP' else ''),
            'secs': round(time.time() - t0, 2)}
    return out, info
