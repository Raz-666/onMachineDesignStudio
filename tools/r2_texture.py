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

R266 DEEP RELIEF (amp above 1.0mm, BUMPS only): the same displacement
engine, but honest about extrusion - a displaced chord has a REAL length,
and on relative-E files each chord's E rides it (E_new = E_old * L_new /
L_old, total per move preserved to the rounding digit). Steep flanks are
subdivided to ~0.4mm height steps so the relief resolves; the wall stays
closed (continuous displacement, inner walls follow per R224). On
absolute-E files E stays slicer-true and the header says so.

Modes
- FUZZY: random displacement of every OUTER WALL vertex within +- thick
  (seeded RNG -> deterministic), density = share of scattered vertices
- BUMPS: displacement along the wall normal proportional to one of the
  55 seamless library pattern functions (see PATTERNS below). Helical tilt is opt-in
  (`tilt=True`); when enabled, PATTERN_TILT supplies each pattern's explicit
  angle and the shift remains seam-safe and flush at the top.
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
  HILBERT     REAL order-3 Hilbert curve walls, tiled - the labyrinth (R265)
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
  STONEWALL   coursed ashlar - seeded block widths per row, mortar beds (R265)
  RUBBLE      uncoursed fieldstones - wrapped jittered Voronoi + mortar (R265)
  TILES       glazed square tiles - flat tops, chamfered bevel, grout (R265)
  PARQUET     chevron fishbone - diagonal planks, mitred V-joints (R265)
  LAMINATE    long narrow planks - V-bevel + dominant grain streaks (R265)
  MAZE        true labyrinth - seeded spanning-tree maze on the torus (R265)
  PERFORATION round-hole perforated sheet - staggered hex-style grid (R265.3)
  VENT        square recesses in a staggered grid - vent panel look (R265.3)
  CARBON      2/2 twill weave - diagonal carbon-fibre bands, glossy flip (R265.3)
  PINDOTS     hemisphere dot matrix - round knobs on a flat base (R265.3)
  OCTAGONS    octagon-and-square cell trays, seeded size jitter (R265.3)
  CHAINLINK   woven chain-link fence - two 45-degree wire families (R265.3)
  NETGRID     netting - round threads with knots, deep open meshes (R265.3)
  RINGS       wood cross-cut - growth rings around, jittered widths (R266.2)
  OAK         coarse oak grain - wandering pore streaks, flame waves (R266.2)
  BEECH       fine beech - quiet dense vertical fibre, almost poreless (R266.2)
  KNOT        burl grain - fibre deflects around seeded knot eyes (R266.2)
  OLDBARK     ancient bark - long plates in DEEP furrows (deep relief!) (R266.2)
  LEATHER     padded leather - diamond-quilted cushions + fine grain (R266.2)
  ORANGE      orange peel - fine irregular micro dimples (small depth!) (R266.2)
  CRACKS      dried mud - narrow deep wandering cracks, crowned plates (R266.2)
  WRINKLE     heavy wrinkle - big folds with sharp crests (CREPE's sibling) (R266.2)

What it never touches
- ;TYPE: tags, LAYER_MARK / APPLY_TYPE, EXCLUDE_OBJECT_*, temps, fans,
  retracts, speeds, Z values - the feature system stays intact. E stays
  untouched too, EXCEPT deep relief on relative-E files (R266: chord E
  follows the displaced length, totals preserved)
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
# R266 field fix (rose fixture): slicers write 'M83 ; use relative distances
# for extrusion' - an exact == match never sees it and the E-mode tracker
# silently stayed absolute. Match the COMMAND token, ignore the comment.
_EMODE = re.compile(r'^(G90|G91|M82|M83)\s*$')
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
                    map_frac=1.0, ar=1.0):
    """R175: returns {NAME: fn(s, t) -> -1..+1} with the geometry snapped.

    ar = millimetres of ONE t-period divided by ONE s-period
    (eff_zsize / eff_size). Form-true patterns (planks, parquet slats)
    need it: a laminate board must read LONG even when the periods are
    square-ish, and a chevron diagonal must aim at 45 degrees in real
    millimetres, not in (s, t) units. Callers that render previews pass
    the pixel-equivalent ratio so the picture shows the same shapes the
    printer will raise. Default 1.0 keeps older callers valid."""
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
        # Repeating hexagonal pavers from the axial/Cartesian distance norm.
        # Even column/row periods preserve both cylinder and height seams.
        cols = max(2, k + (k & 1))
        rows = max(2, int(round(2.0 * max(1, n) / math.sqrt(3.0))))
        if rows & 1:
            rows += 1
        dy = math.sqrt(3.0) / 2.0
        x, y = s * cols, t * rows * dy
        r0 = int(round(y / dy))
        best = 1e9
        for rr in (r0 - 1, r0, r0 + 1):
            oy = y - rr * dy
            offset = 0.5 * (rr & 1)
            cc = int(round(x - offset))
            for c in (cc - 1, cc, cc + 1):
                ox = x - (c + offset)
                norm = max(abs(ox), abs(0.5 * ox + 0.8660254 * oy),
                           abs(-0.5 * ox + 0.8660254 * oy))
                best = min(best, norm)
        return 1.0 - 2.0 * _smoothstep(0.39, 0.50, best)
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
        # Long boards with visible vertical grooves, staggered end joints,
        # and low-amplitude longitudinal grain. Even column count guarantees
        # a clean wrap around the cylinder; the joint rhythm is periodic in Z.
        ke = k + (k & 1)
        i = s * ke
        col = int(math.floor(i))
        fx = i - col
        stagger = row_rnd[min(col, ke - 1 - col) % len(row_rnd)]
        zcells = max(2, n * 2)
        z = (t * zcells + stagger * 0.5) % 1.0
        edge = 1.0 - _smoothstep(0.018, 0.095, min(fx, 1.0 - fx))
        end_joint = 1.0 - _smoothstep(0.015, 0.075, min(z, 1.0 - z))
        grain = (noise(s, t, max(2, ke * 5), max(1, n // 3)) - 0.5) * 0.30
        face = 0.56 + 0.20 * math.sin(math.pi * fx)
        return max(-1.0, min(1.0,
            face + grain - 0.85 * edge - 0.45 * end_joint))
    pats['PLANKS'] = _planks

    def _bricks(s, t):
        rows = max(2, n * 2)
        row = int(math.floor(t * rows))
        x = (s * k + (0.5 if row % 2 else 0.0)) % 1.0
        fy = (t * rows) % 1.0
        face = (_smoothstep(0.07, 0.15, min(fy, 1.0 - fy)) *
                _smoothstep(0.04, 0.13, min(x, 1.0 - x)))
        rough = (noise(s, t, k * 3, rows) - 0.5) * 0.35
        return max(-1.0, min(1.0, face * 1.6 - 0.85 + rough))
    pats['BRICKS'] = _bricks

    # ---- R238 (.136ai master prompt): textile, organic, geometric looks --------
    def _knit(s, t):
        # KNIT & CROCHET: nested V-loops in staggered columns - the legs of
        # every stitch arch over the row below (the prompt's sin*cos with
        # phase shift). Reads as a knitted sleeve; optional 3 deg tilt
        # breaks the remaining parallelism to the layers when enabled.
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
        # Bark-like plates, not generic vertical noise: a periodic set of
        # wandering longitudinal fissures, broad raised ridges between them,
        # and sparse cross-cracks. The warp is low-frequency and periodic so
        # the cylinder seam and object top remain closed.
        warp = (noise(s, t, max(2, k * 2), max(2, n)) - 0.5) * 0.22
        phase = (s * k + warp) % 1.0
        edge = min(phase, 1.0 - phase)
        crack = 1.0 - _smoothstep(0.025, 0.095, edge)
        plate = 0.55 + 0.30 * math.sin(math.pi * phase)
        cross = noise(s, t, max(2, k * 3), max(2, n * 2))
        cross_crack = max(0.0, cross - 0.79) * 3.0
        return max(-1.0, min(1.0, plate - 0.95 * crack - cross_crack))
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
        # R265 (J8): a REAL Hilbert curve - raised walls along the order-3
        # space-filling path, tiled (one COMPLETE curve per tile). The user
        # finding was right: the old zig-zag bands were no labyrinth. The
        # distance field is precomputed ONCE into a bitmap (wrap-aware, so
        # walls continue cleanly across tile borders) and read back with a
        # bilinear lookup - O(1) per wall point, Pi-friendly. A gentle ramp
        # along the curve parameter keeps the traversal order readable.
        tx = max(1, int(round(k / 4.0)))
        ty = max(1, int(round(n / 4.0)))
        u = (s * tx) % 1.0
        v = (t * ty) % 1.0
        return _hb_field(u, v)
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

    # ---- R265 helpers: stone layouts, Voronoi sites, curve/maze bitmaps -------
    _sw_cache = {}

    def _sw_layout(row):
        # per-row block widths: seeded, but NORMALIZED to sum exactly ke
        # (the wrap closes flush no matter what the seed draws)
        lay = _sw_cache.get(row)
        if lay is None:
            ke = max(2, k + (k & 1))
            ws = [band_rnd[(row * 7 + i * 3) % len(band_rnd)] + 0.30
                  for i in range(ke)]
            tot = sum(ws)
            lay = [w * ke / tot for w in ws]
            _sw_cache[row] = lay
        return lay

    _rb_gx = max(3, min(24, k))
    _rb_gy = max(3, min(24, n))
    _rb_sites = [[(0.18 + 0.64 * rng.random(), 0.18 + 0.64 * rng.random())
                  for _ in range(_rb_gy)] for _ in range(_rb_gx)]
    _rb_tone = [[rng.random() for _ in range(_rb_gy)]
                for _ in range(_rb_gx)]

    def _field_bitmaps(segs, sx, sy, res, wall_lo, wall_hi):
        """R265: ONE-TIME wrap-aware distance field over a `sx` x `sy`
        torus covered by axis-aligned unit-step `segs`
        (x0, y0, x1, y1, par). Returns lookup(u, v) -> -1..+1 with raised
        walls along the segments (u, v in [0,1) each cover their full
        period, so the field TILES exactly). Bucketed per cell; the eval
        is a bilinear bitmap lookup - O(1) per wall point."""
        cells = {}
        for sg in segs:
            x0, y0, x1, y1, par = sg
            for ex in (x0, x1):
                for ey in (y0, y1):
                    for ox in (-1, 0):
                        for oy in (-1, 0):
                            cells.setdefault(
                                ((ex + ox) % sx, (ey + oy) % sy),
                                []).append(sg)

        def dist_at(px, py):
            # torus-wrapped point-to-segment distance + curve parameter
            best = 1e9
            bpar = 0.0
            cx = int(math.floor(px)) % sx
            cy = int(math.floor(py)) % sy
            for ddy in (-1, 0, 1):
                for ddx in (-1, 0, 1):
                    for sg in cells.get(((cx + ddx) % sx,
                                         (cy + ddy) % sy), ()):
                        x0, y0, x1, y1, par = sg
                        # projection clamp (segments are axis-aligned)
                        tproj = (((px - x0) * (x1 - x0) +
                                  (py - y0) * (y1 - y0)) /
                                 max(1e-12, (x1 - x0) ** 2 + (y1 - y0) ** 2))
                        tproj = max(0.0, min(1.0, tproj))
                        dx = x0 + tproj * (x1 - x0) - px
                        dy = y0 + tproj * (y1 - y0) - py
                        # EXACT torus distance: wrap each axis into
                        # [-period/2, period/2) - equivalent to checking
                        # all 9 copies, at 1/9 the cost
                        if dx > 0.5 * sx:
                            dx -= sx
                        elif dx < -0.5 * sx:
                            dx += sx
                        if dy > 0.5 * sy:
                            dy -= sy
                        elif dy < -0.5 * sy:
                            dy += sy
                        d = dx * dx + dy * dy
                        if d < best:
                            best = d
                            bpar = par
            return math.sqrt(best), bpar

        field = []
        parm = []
        for j in range(res):
            py = (j + 0.5) * sy / res
            frow = []
            prow = []
            for i in range(res):
                px = (i + 0.5) * sx / res
                d, par = dist_at(px, py)
                frow.append(d)
                prow.append(par)
            field.append(frow)
            parm.append(prow)

        def lookup(u, v):
            # bilinear read, tile-local u, v in [0,1)
            fu = u * res - 0.5
            fv = v * res - 0.5
            i0 = int(math.floor(fu)) % res
            j0 = int(math.floor(fv)) % res
            i1 = (i0 + 1) % res
            j1 = (j0 + 1) % res
            ax = fu - math.floor(fu)
            ay = fv - math.floor(fv)
            def bl(mat):
                return (mat[j0][i0] * (1 - ax) * (1 - ay) +
                        mat[j0][i1] * ax * (1 - ay) +
                        mat[j1][i0] * (1 - ax) * ay +
                        mat[j1][i1] * ax * ay)
            d = bl(field)
            par = bl(parm)
            wall = 1.0 - _smoothstep(wall_lo, wall_hi, d)
            return max(-1.0, min(1.0, 0.9 * wall * (0.82 + 0.18 * par) - 0.35))

        return lookup

    # -- the REAL Hilbert curve (order 3, 8x8, classic d2xy mapping) ----------
    _hb_side = 8

    def _hb_d2xy(idx):
        x = y = 0
        t = idx
        s = 1
        while s < _hb_side:
            rx = 1 & (t // 2)
            ry = 1 & (t ^ rx)
            if ry == 0:
                if rx == 1:
                    x = s - 1 - x
                    y = s - 1 - y
                x, y = y, x
            x += s * rx
            y += s * ry
            t //= 4
            s *= 2
        return x, y

    _hb_pts = [_hb_d2xy(i) for i in range(_hb_side * _hb_side)]
    _hb_segs = []
    for _i in range(len(_hb_pts) - 1):
        _a, _b = _hb_pts[_i], _hb_pts[_i + 1]
        _hb_segs.append((_a[0], _a[1], _b[0], _b[1],
                         _i / float(len(_hb_pts) - 1)))
    # walls hug the curve (measured d range 0.10..0.71, median 0.30):
    # 0.12..0.30 leaves real corridors between the runs. LAZY: only a
    # HILBERT apply ever pays the one-time bitmap build.
    _hb_cache = []

    def _hb_field(u, v):
        if not _hb_cache:
            _hb_cache.append(_field_bitmaps(
                _hb_segs, _hb_side, _hb_side, 96, 0.12, 0.30))
        return _hb_cache[0](u, v)

    # -- the TORUS MAZE (seeded spanning tree; walls = uncarved edges) --------
    _mz_gx = max(5, min(13, int(round(k))))
    _mz_gy = max(5, min(13, int(round(n))))
    _mz_walls = set()
    for _i in range(_mz_gx):
        for _j in range(_mz_gy):
            _mz_walls.add(('E', _i, _j))       # edge to the east neighbour
            _mz_walls.add(('S', _i, _j))       # edge to the south neighbour
    _mz_seen = {(0, 0)}
    _mz_stack = [(0, 0)]
    while _mz_stack:
        _cx, _cy = _mz_stack[-1]
        _nbrs = []
        for _wk, _nx, _ny in (
                (('E', _cx, _cy), (_cx + 1) % _mz_gx, _cy),
                (('E', (_cx - 1) % _mz_gx, _cy), (_cx - 1) % _mz_gx, _cy),
                (('S', _cx, _cy), _cx, (_cy + 1) % _mz_gy),
                (('S', _cx, (_cy - 1) % _mz_gy), _cx, (_cy - 1) % _mz_gy)):
            if (_nx, _ny) not in _mz_seen:
                _nbrs.append((_wk, _nx, _ny))
        if _nbrs:
            _wk, _nx, _ny = _nbrs[rng.randrange(len(_nbrs))]
            _mz_walls.discard(_wk)
            _mz_seen.add((_nx, _ny))
            _mz_stack.append((_nx, _ny))
        else:
            _mz_stack.pop()
    # seal-proofing: a lattice vertex whose 4 surrounding edges are ALL
    # walls would enclose a tiny unreachable pocket (wall-cycle around one
    # grid point). Carve one edge of every such vertex - the spanning
    # tree stays intact (removing walls only ADDS connections), and the
    # corridor system becomes ONE walkable component: a perfect maze.
    for _vx in range(_mz_gx):
        for _vy in range(_mz_gy):
            _around = (
                ('E', (_vx - 1) % _mz_gx, (_vy - 1) % _mz_gy),
                ('E', (_vx - 1) % _mz_gx, _vy % _mz_gy),
                ('S', (_vx - 1) % _mz_gx, (_vy - 1) % _mz_gy),
                ('S', _vx % _mz_gx, (_vy - 1) % _mz_gy))
            if all(_wk in _mz_walls for _wk in _around):
                _mz_walls.discard(_around[3])
    _mz_segs = []
    for _ek, _i, _j in sorted(_mz_walls):
        if _ek == 'E':
            # vertical wall segment on the line x = i+1, from y=j to j+1
            _mz_segs.append((_i + 1, _j, _i + 1, _j + 1, 0.5))
        else:
            # horizontal wall segment on the line y = j+1, from x=i to i+1
            _mz_segs.append((_i, _j + 1, _i + 1, _j + 1, 0.5))
    # NOTE: boundary segments (x=gx or y=gy) stay WHERE THEY ARE - the
    # torus distance wraps the deltas per axis, and the cell buckets wrap
    # their keys. Folding the endpoints back to 0 would instead create
    # PHANTOM walls spanning the whole domain (a segment from x=11 to
    # x=0 is 11 cells long, not the 1-cell wall it represents).
    _mz_cache = []

    def _mz_field(u, v):
        if not _mz_cache:
            _mz_cache.append(_field_bitmaps(
                _mz_segs, _mz_gx, _mz_gy, 180, 0.10, 0.26))
        return _mz_cache[0](u, v)

    # ---- R265 (J8 texture round II, chunk 1): walls, floors, labyrinths ---------
    # Every pattern here follows the house rules: seamless by construction
    # (integer periods / wrapped grids / tiled bitmaps), the NAME matches the
    # relief, and the features are sized to READ on a print (no smooth-only
    # near-duplicates of existing families).

    def _stonewall(s, t):
        # COURSED ASHLAR (Natursteinmauer): rows of dressed blocks whose
        # widths are seeded per row but ALWAYS sum to the exact column
        # period (seamless by construction), recessed mortar beds and block
        # joints, per-block face jitter and a fine stone roughness. Reads
        # as stacked stone courses - the BRICKS cousin for irregular,
        # larger blocks with a rough face.
        rows = max(2, n)
        row = min(rows - 1, int(math.floor(t * rows)))
        fy = (t * rows) % 1.0
        ke = max(2, k + (k & 1))
        lay = _sw_layout(row)
        x = s * ke
        acc = 0.0
        col = 0
        w = 1.0
        for i in range(ke):
            w = lay[i]
            if x < acc + w or i == ke - 1:
                col = i
                break
            acc += w
        fx = (x - acc) / max(1e-9, w)
        bed = 1.0 - _smoothstep(0.05, 0.16, min(fy, 1.0 - fy))
        win = _smoothstep(0.02, 0.20, min(fy, 1.0 - fy))
        joint = 1.0 - _smoothstep(0.04, 0.14, min(fx, 1.0 - fx))
        tone = band_rnd[(row * 5 + col * 11) % len(band_rnd)]
        # the block face (incl. its tone) fades INTO the mortar bed and
        # OUT at the joints - the bed line is pure mortar on BOTH sides,
        # so every row boundary and the wrap itself stay closed
        face = (0.55 + 0.25 * math.sin(math.pi * fx)
                + (tone - 0.5) * 0.25 * (1.0 - joint))
        rough = (noise(s, t, max(2, ke * 3), max(2, rows * 2)) - 0.5) * 0.16
        return max(-1.0, min(1.0,
            (face - 0.66 * joint) * win - 0.78 * bed
            + rough * (0.4 + 0.6 * win)))
    pats['STONEWALL'] = _stonewall

    def _rubble(s, t):
        # UNCOURSED RUBBLE (Bruchstein): irregular fieldstones set in a deep
        # mortar bed - a jittered-site Voronoi on the WRAPPED grid
        # (periodic by construction). F1 domes each stone, the F2-F1 ridge
        # becomes the mortar joint, per-stone tone jitter breaks any grid
        # reading. Unlike STONEWALL there are NO courses - organic scatter.
        gx, gy = _rb_gx, _rb_gy
        x = s * gx
        y = t * gy
        ix, iy = int(math.floor(x)), int(math.floor(y))
        f1 = f2 = 1e18
        tone = 0.5
        for dj in (-1, 0, 1):
            for di in (-1, 0, 1):
                cx, cy = ix + di, iy + dj
                jx, jy = _rb_sites[cx % gx][cy % gy]
                dx = cx + jx - x
                dy = cy + jy - y
                d = dx * dx + dy * dy
                if d < f1:
                    f2 = f1
                    f1 = d
                    tone = _rb_tone[cx % gx][cy % gy]
                elif d < f2:
                    f2 = d
        dome = 1.0 - _smoothstep(0.14, 0.58, math.sqrt(f1))
        mortar = 1.0 - _smoothstep(0.03, 0.17, math.sqrt(f2) - math.sqrt(f1))
        return max(-1.0, min(1.0,
            (0.30 + 0.45 * dome + (tone - 0.5) * 0.25) - 0.85 * mortar))
    pats['RUBBLE'] = _rubble

    def _tiles(s, t):
        # GLAZED WALL TILES (Fliesen): a uniform square field - every tile
        # a FLAT top rising over a chamfered bevel (printable, no hard
        # step), grout lines recessed, per-tile height offset and a faint
        # surface noise. NOT a CHECKER twin: no parity flip, bevel + tone
        # instead - reads as a tiled wall.
        ke = k + (k & 1)
        rows = max(2, int(round(n * max(0.25, ar))))
        i = s * ke
        j = t * rows
        col = int(math.floor(i))
        row = int(math.floor(j))
        fx, fy = i - col, j - row
        d_edge = min(fx, 1.0 - fx, fy, 1.0 - fy)
        bevel = _smoothstep(0.03, 0.17, d_edge)
        tone = noise(col / float(ke), row / float(rows), ke, rows)
        peel = (noise(s, t, max(4, ke * 3), max(4, rows * 3)) - 0.5) * 0.10
        # tone rides ONLY on the tile face: the grout line is pure grout
        # on both sides -> the wrap and every grout crossing stay closed
        top = 0.42 * bevel + (tone - 0.5) * 0.30 * bevel
        return max(-1.0, min(1.0, top - 0.62 * (1.0 - bevel) + peel))
    pats['TILES'] = _tiles

    def _parquet(s, t):
        # CHEVRON PARQUET (Fischgraet-Optik): diagonal slats whose slope
        # flips in every column - the mitred V-joints sit exactly on the
        # column borders. R265.2 geometry fix (user review: 'reads like
        # square tiles'): with P = n slats per t-period the slats came
        # out nearly square. Now the slat count P and the diagonal pitch
        # Q are DERIVED from a ~1:5 slat at ~45 degrees in REAL mm:
        #   P = R*n*ar*ke/(2k), Q = P*k/(ke*n*ar)  ->  both INTEGER
        # (integers keep pd periodic in t and continuous across the
        # column border: P*(t) jumps by P, d*Q*fx jumps by Q - both
        # vanish mod 1). The even column count closes the s-wrap.
        ke = max(2, k + (k & 1))
        P = max(2, min(96, int(round(5.0 * n * ar * ke / (2.0 * k)))))
        Q = max(1, min(12, int(round(P * k / float(ke * n * max(0.2, ar))))))
        i = s * ke
        col = int(math.floor(i))
        fx = i - col
        direc = 1.0 if (col % 2 == 0) else -1.0
        pd = (P * t + direc * Q * fx) % 1.0
        joint = 1.0 - _smoothstep(0.05, 0.20, min(pd, 1.0 - pd))
        miter = 1.0 - _smoothstep(0.02, 0.10, min(fx, 1.0 - fx))
        grain = (noise(s, t, max(2, ke * 5), max(2, P)) - 0.5) * 0.22
        grain *= (1.0 - joint) * (1.0 - 0.7 * miter)
        face = 0.55 + 0.18 * math.sin(math.pi * pd)
        return max(-1.0, min(1.0,
            face + grain - 0.88 * joint - 0.58 * miter))
    pats['PARQUET'] = _parquet

    def _laminate(s, t):
        # LAMINATE FLOORING: narrow, LONG boards. R265.2 geometry fix
        # (user review: 'planks/parquet/laminate all read like square
        # tiles'): boards used to be ONE period long and ONE period wide.
        # Now ke = 2k halves the board width and the board LENGTH spans
        # M full t-periods, M a divisor of n picked near a 1:6 aspect
        # (via ar) - a laminate board reads LONG. Staggered end joints
        # per board lane, a chamfered V-bevel at every border (the
        # click-joint look) and DOMINANT fine grain streaks along the
        # board: the HF-embossed decor. The grain is the headline, not
        # the groove - that is what separates it from PLANKS (broad,
        # short, deep-grooved) and PARQUET (diagonal slats).
        ke = max(4, 2 * k)
        Mtar = max(1.0, 6.0 * k / (float(ke) * max(0.2, ar)))
        M = 1
        for m in range(1, max(2, n + 1)):
            if n % m == 0 and abs(m - Mtar) <= abs(M - Mtar):
                M = m
        zc = max(1, n // M)
        i = s * ke
        col = int(math.floor(i))
        fx = i - col
        stagger = row_rnd[min(col, ke - 1 - col) % len(row_rnd)]
        z = (t * zc + stagger * 0.5) % 1.0
        bevel = _smoothstep(0.02, 0.16, min(fx, 1.0 - fx))
        end_joint = 1.0 - _smoothstep(0.02, 0.09, min(z, 1.0 - z))
        tone = noise(col / float(ke), 0.5, ke, 3)
        grain_t = max(1, 2 * zc)
        grain = (noise(s, t, max(6, ke * 4), grain_t) - 0.5) * 0.55
        grain *= bevel * (1.0 - 0.8 * end_joint)
        face = 0.40 + (tone - 0.5) * 0.28
        return max(-1.0, min(1.0,
            face * (0.35 + 0.65 * bevel) + grain
            - 0.55 * (1.0 - bevel) - 0.70 * end_joint))
    pats['LAMINATE'] = _laminate

    def _maze(s, t):
        # TRUE LABYRINTH: a seeded spanning-tree maze on the TORUS (the
        # wall set wraps - corridors cannot dead-end against the seam).
        # Walls are raised bands along the grid edges the maze did NOT
        # carve; the distance field is precomputed once into a wrap-aware
        # bitmap and read back bilinearly (O(1) per wall point). One maze
        # spans the whole object period - a single connected labyrinth.
        return _mz_field(s % 1.0, t % 1.0)
    pats['MAZE'] = _maze

    # ================= R265.3 bite 2: technical structures =====================
    # All form-true: cells that must be ROUND or SQUARE in real millimetres
    # use the row count round(n*ar) so the mm cell is square, and in-cell
    # coordinates are compared in CELL units (which are mm/E) - a circle
    # in cell units is a circle on the print.

    def _perforation(s, t):
        # PERFORATED SHEET: round holes in a staggered grid (the classic
        # tread-plate / sieve look - dimples, NOT through-holes: the wall
        # stays closed). Every second row shifts half a cell; holes are
        # true circles because dx/dy are measured in mm-square cell units.
        kp = max(2, k)
        rows = max(2, int(round(n * max(0.25, ar))))
        rows += rows & 1            # EVEN: the stagger alternates over the wrap
        i = s * kp
        row = int(math.floor(t * rows))
        fy = t * rows - row
        # stagger: even rows centre at 0.5, odd rows at 0.0/1.0 (wrap)
        if row % 2 == 0:
            dx = i - math.floor(i) - 0.5
        else:
            # odd rows centre on the cell border (0.0/1.0 - same hole
            # through the wrap): distance to the NEARER of the two
            dx = min(i - math.floor(i), 1.0 - (i - math.floor(i)))
        dy = fy - 0.5
        d = math.sqrt(dx * dx + dy * dy)
        hole = 1.0 - _smoothstep(0.20, 0.30, d)
        rim = (_smoothstep(0.20, 0.27, d)
               * (1.0 - _smoothstep(0.27, 0.36, d)))
        return max(-1.0, min(1.0, 0.32 - 0.85 * hole + 0.18 * rim))
    pats['PERFORATION'] = _perforation

    def _vent(s, t):
        # VENT PANEL: square recesses in a staggered grid - enclosure
        # ventilation / speaker-grille look. The inverse of TILES (recess
        # not relief) and the staggered sibling of PERFORATION.
        kp = max(2, k)
        rows = max(2, int(round(n * max(0.25, ar))))
        rows += rows & 1            # EVEN: the stagger alternates over the wrap
        i = s * kp
        row = int(math.floor(t * rows))
        fx = i - math.floor(i)
        fy = t * rows - row
        if row % 2 == 0:
            qx = abs(fx - 0.5)
        else:
            qx = min(fx, 1.0 - fx)
        qy = abs(fy - 0.5)
        d_edge = max(qx, qy)              # Chebyshev = square
        hole = 1.0 - _smoothstep(0.26, 0.36, d_edge)
        rim = (_smoothstep(0.26, 0.33, d_edge)
               * (1.0 - _smoothstep(0.33, 0.42, d_edge)))
        return max(-1.0, min(1.0, 0.32 - 0.85 * hole + 0.18 * rim))
    pats['VENT'] = _vent

    def _carbon(s, t):
        # CARBON FIBRE, 2/2 twill: the classic diagonal weave. Cell counts
        # are multiples of 4 so the twill phase closes on BOTH wraps; the
        # diagonal runs at ~45 deg in real mm (F = round(n*ar)); the gloss
        # flips between the two thread families, the seams between cells
        # sit slightly low, and a fine thread relief rides the bands.
        kc = 4 * max(1, int(round(k / 2.0)))
        rc = 4 * max(1, int(round(n * max(0.25, ar) / 2.0)))
        F = max(1, int(round(n * max(0.25, ar))))
        i = s * kc
        j = t * rc
        ci, cj = int(math.floor(i)), int(math.floor(j))
        fx, fy = i - ci, j - cj
        band = ((ci + cj) // 2) % 2        # 2-over-2-under diagonal
        gloss = 0.42 if band == 0 else -0.18
        seam = (1.0 - _smoothstep(0.00, 0.16, min(fx, 1.0 - fx))) \
            + (1.0 - _smoothstep(0.00, 0.16, min(fy, 1.0 - fy)))
        # fine thread relief ALONG the diagonal (period 1/4 cell)
        ph = (i + j) * 0.25
        thread = 0.10 * math.sin(2.0 * math.pi * (ph - math.floor(ph)))
        return max(-1.0, min(1.0,
            gloss + thread - 0.30 * seam))
    pats['CARBON'] = _carbon

    def _pindots(s, t):
        # PIN / DOT MATRIX: true hemisphere knobs on a flat base - the
        # grip-and-decor surface (control panels, organisers). Rows follow
        # ar so the matrix is square in mm; the cap profile is a softened
        # hemisphere (finite slope at the rim - printable).
        kp = max(2, k)
        rows = max(2, int(round(n * max(0.25, ar))))
        i = s * kp
        row = int(math.floor(t * rows))
        fx = i - math.floor(i)
        fy = t * rows - row
        dx, dy = fx - 0.5, fy - 0.5
        d = math.sqrt(dx * dx + dy * dy) / 0.40
        if d >= 1.0:
            cap = 0.0
        else:
            cap = math.pow(1.0 - d * d, 0.62)
        return max(-1.0, min(1.0, -0.22 + 1.05 * cap))
    pats['PINDOTS'] = _pindots

    def _octagons(s, t):
        # OCTAGON-AND-SQUARE trays (the 4.3.8.4 tiling): raised octagon
        # faces with chamfered rims, small square islands in the corners
        # one step below the octagons, deep grooves between. Seeded size
        # jitter gives the 'variable cell diameter' the user asked for.
        kp = max(2, k)
        rows = max(2, int(round(n * max(0.25, ar))))
        i = s * kp
        row = int(math.floor(t * rows))
        fx = i - math.floor(i)
        fy = t * rows - row
        dx, dy = abs(fx - 0.5), abs(fy - 0.5)
        d_oct = max(dx, dy, (dx + dy) * 0.70710678)   # octagon norm
        tone = noise(math.floor(i) / float(kp),
                     row / float(rows), kp, rows)
        face = 0.36 + (tone - 0.5) * 0.12
        oct_r = 0.40 - (tone - 0.5) * 0.05             # size jitter
        oct_face = _smoothstep(oct_r - 0.07, oct_r, d_oct)
        # corner squares: one step below the octagon face
        ex = min(fx, 1.0 - fx)
        ey = min(fy, 1.0 - fy)
        de = max(ex, ey)                               # around grid corner
        sq = (1.0 - _smoothstep(0.10, 0.17, de)) \
            * _smoothstep(0.30, 0.40, d_oct)
        groove = 1.0 - _smoothstep(0.02, 0.09, de)
        return max(-1.0, min(1.0,
            face * oct_face + 0.05 * sq - 0.55 * (1.0 - oct_face)
            - 0.25 * groove * (1.0 - sq)))
    pats['OCTAGONS'] = _octagons

    def _chainlink(s, t):
        # CHAIN-LINK FENCE: two wire families crossing at ~45 deg (in real
        # mm, F = round(n*ar)); each wire is a rounded band, and the weave
        # alternates over/under at the crossings (basket parity on the
        # diamond cell) - the classic raucous Maschendraht look.
        F = max(1, int(round(n * max(0.25, ar))))
        p1 = (k * s + F * t) % 1.0
        p2 = (k * s - F * t) % 1.0
        d1 = min(p1, 1.0 - p1)
        d2 = min(p2, 1.0 - p2)
        w1 = 1.0 - _smoothstep(0.045, 0.115, d1)
        w2 = 1.0 - _smoothstep(0.045, 0.115, d2)
        # dome the wire cross-section
        w1 *= 0.55 + 0.45 * math.cos(math.pi * min(1.0, d1 / 0.16))
        w2 *= 0.55 + 0.45 * math.cos(math.pi * min(1.0, d2 / 0.16))
        # weave parity: which family rides on top in this diamond
        cell = math.floor(k * s + F * t) + math.floor(k * s - F * t)
        top1 = 0.95 if (int(cell) % 2 == 0) else 0.60
        top2 = 1.05 - top1
        return max(-1.0, min(1.0,
            -0.55 + 0.85 * (w1 * top1 + w2 * top2)))
    pats['CHAINLINK'] = _chainlink

    def _netgrid(s, t):
        # NETTING: round threads running around and up, knotted at the
        # crossings, with deep open meshes between - fishing-net look.
        # (MACRAME is thick twisted cords, GRID is a flat egg-crate -
        # this one is thread + knot + hole.)
        kp = max(2, k + (k & 1))   # EVEN: weave parity survives the s-wrap
        rows = max(2, int(round(n * max(0.25, ar))))
        rows += rows & 1          # EVEN: ... and the t-wrap
        i = s * kp
        j = t * rows
        fx = i - math.floor(i)
        fy = j - math.floor(j)
        ci, cj = int(math.floor(i)), int(math.floor(j))
        ds = min(fx, 1.0 - fx)            # distance to vertical thread
        dt = min(fy, 1.0 - fy)            # distance to horizontal thread
        vs = 1.0 - _smoothstep(0.03, 0.10, ds)
        hs = 1.0 - _smoothstep(0.03, 0.10, dt)
        vs *= 0.55 + 0.45 * math.cos(math.pi * min(1.0, ds / 0.14))
        hs *= 0.55 + 0.45 * math.cos(math.pi * min(1.0, dt / 0.14))
        # knot: a little dome at the crossing, alternating with parity
        knot = ((ci + cj) % 2) * 0.22 * vs * hs
        weave = 0.7 if (ci + cj) % 2 == 0 else 1.0
        return max(-1.0, min(1.0,
            -0.62 + 0.80 * vs * weave + 0.80 * hs * (2.0 - weave)
            + 0.35 * knot))
    pats['NETGRID'] = _netgrid

    # ================= R266.2 bite 3: organics ===================================
    # Wood (cross-cut rings, oak, beech, burl), ancient bark (the deep-
    # relief showpiece - pair with depth 2-3.5mm), padded leather, orange
    # peel, dried-mud cracks, heavy wrinkle. All periodic by construction:
    # integer-frequency noise, torus-wrapped distances, toroidal knot
    # sites - no free edges anywhere.

    # ring BOUNDARIES wander (a thin year next to a fat one - the
    # signature of real growth rings) and groove widths jitter per ring.
    # Period n in the ring index: boundary n == boundary 0, the t-wrap
    # closes exactly.
    _rg_n = max(2, n)
    _rg_off = [(rng.random() - 0.5) * 0.55 for _ in range(_rg_n)]
    _rg_w0 = [rng.random() for _ in range(_rg_n)]

    def _rings(s, t):
        # WOOD CROSS-CUT (Jahresringe): growth rings run AROUND the
        # object - horizontal bands up the Z axis, the log seen from the
        # side. Every ring = one wide early-wood arch + one narrow dark
        # late-wood groove. The boundaries WANDER (unequal ring widths),
        # the groove line sways, fine rays streak along the circumference.
        y = t * n + (noise(s, t, max(2, k // 2), max(2, n)) - 0.5) * 0.14
        j0 = int(math.floor(y + 0.5))
        bj, bd = j0, y - j0
        for j in (j0 - 1, j0, j0 + 1):
            d = y - (j + _rg_off[j % _rg_n])
            if abs(d) < abs(bd):
                bj, bd = j, d
        edge = abs(bd)
        o_j = _rg_off[bj % _rg_n]
        o_j1 = _rg_off[(bj + 1) % _rg_n]
        bw = max(0.35, 1.0 + o_j1 - o_j)      # local ring width
        jit = _rg_w0[bj % _rg_n]
        w0 = 0.016 + 0.05 * jit
        late = 1.0 - _smoothstep(w0, w0 + 0.05, edge)
        early = 0.50 + 0.36 * math.sin(
            math.pi * min(1.0, edge / bw))
        ray = (noise(s, t, max(2, k * 3), max(2, max(1, n // 2)))
               - 0.5) * 0.27
        return max(-1.0, min(1.0, early - 0.88 * late + ray))
    pats['RINGS'] = _rings

    def _oak(s, t):
        # OAK (Eiche grob): the fibre runs UP, strong wandering PORE
        # streaks that bundle and part - oak's signature - over broad
        # flame waves. Pores are thresholded (deep, sparse grooves), the
        # wander shifts the whole pore field sideways, low frequency.
        wander = (noise(s, t, max(2, k // 3), max(2, max(1, n // 2)))
                  - 0.5) * 0.45
        u = (s + 0.35 * wander) % 1.0
        pv = noise(u, t, max(2, k), max(2, max(1, n // 3)))
        pore = max(0.0, pv - 0.55) * 3.4
        flame = 0.42 + 0.30 * math.sin(
            two_pi * (u * max(2, k // 2) + 0.8 * wander))
        fibre = (noise(u, t, max(2, k * 2), max(2, n)) - 0.5) * 0.16
        return max(-1.0, min(1.0, flame - 0.85 * pore + fibre))
    pats['OAK'] = _oak

    def _beech(s, t):
        # BEECH (Buche fein): the QUIET wood - very fine dense vertical
        # fibre, almost no pores, one soft wide undulation. Smooth from a
        # distance, finely grained up close (two elongated octaves).
        u = (s + 0.10 * (noise(s, t, max(2, k // 2), max(2, max(1, n // 2)))
                         - 0.5)) % 1.0
        fine = noise(u, t, max(2, k * 3), max(2, max(1, n // 2)))
        finer = noise(u, t, max(2, k * 5), max(2, n))
        wave = 0.34 + 0.16 * math.sin(
            two_pi * (u * max(2, k // 2) + t * 2))
        return max(-1.0, min(1.0,
            wave + (fine - 0.5) * 0.55 + (finer - 0.5) * 0.18))
    pats['BEECH'] = _beech

    _nk266 = max(2, min(4, (k + n) // 12))
    _kn_x = [rng.random() for _ in range(_nk266)]
    _kn_y = [rng.random() for _ in range(_nk266)]
    _kn_r = [0.16 + 0.10 * rng.random() for _ in range(_nk266)]
    _kn_ph = [rng.random() for _ in range(_nk266)]

    def _knot(s, t):
        # BURL GRAIN (Maserwirbel): the vertical fibre DEFLECTS around
        # seeded knot eyes, each eye carries its own concentric rings.
        # Torus-wrapped distances (mm-true via ar) + gaussian swirl ->
        # the grain flows around the knot like real wood; everything
        # periodic, no free edge.
        swirl = 0.0
        eye = 0.0
        for _i in range(_nk266):
            dx = s - _kn_x[_i]
            dx -= math.floor(dx + 0.5)
            dy = t - _kn_y[_i]
            dy -= math.floor(dy + 0.5)
            d = math.hypot(dx, dy * ar)
            r = _kn_r[_i]
            g = math.exp(-(d / r) ** 2 * 2.2)
            swirl += g * _kn_ph[_i]
            eye += g * math.cos(two_pi * (d / r) * 3.0
                                + _kn_ph[_i] * two_pi)
        grain = math.sin(two_pi * (s * max(2, k // 2) + 0.9 * swirl
                 + (noise(s, t, 5, 3) - 0.5) * 0.5))
        return max(-1.0, min(1.0, 0.45 + 0.42 * grain + 0.38 * eye))
    pats['KNOT'] = _knot

    _ob_gx = max(3, min(14, k // 2))
    _ob_gy = max(2, int(round(_ob_gx / max(0.30, ar * 2.6))))
    _ob_sites = [[(rng.random(), rng.random()) for _ in range(_ob_gy)]
                 for _ in range(_ob_gx)]
    _ob_tone = [[rng.random() for _ in range(_ob_gy)]
                for _ in range(_ob_gx)]

    def _oldbark(s, t):
        # ANCIENT BARK (alter Baumstamm): long ragged bark plates in DEEP
        # furrows - the deep-relief showpiece (R266: pair with depth
        # 2-3.5mm, relative E rides the flanks). Anisotropic wrapped
        # Voronoi: s-distance costs 2.2x -> cells stretch along the fibre.
        # Plates chip (per-plate tone + thresholded cross breaks); the
        # furrow floor stays CLOSED - dimples, never holes.
        x = s * _ob_gx
        y = t * _ob_gy
        ix, iy = int(math.floor(x)), int(math.floor(y))
        f1 = f2 = 1e18
        tone = 0.5
        for dj in (-1, 0, 1):
            for di in (-1, 0, 1):
                cx, cy = ix + di, iy + dj
                jx, jy = _ob_sites[cx % _ob_gx][cy % _ob_gy]
                dx = cx + jx - x
                dy = cy + jy - y
                d = (dx * 2.2) ** 2 + dy * dy
                if d < f1:
                    f2 = f1
                    f1 = d
                    tone = _ob_tone[cx % _ob_gx][cy % _ob_gy]
                elif d < f2:
                    f2 = d
        d1, d2 = math.sqrt(f1), math.sqrt(f2)
        plate = 1.0 - _smoothstep(0.30, 1.05, d1)
        furrow = 1.0 - _smoothstep(0.05, 0.26, d2 - d1)
        cross = noise(s, t, max(2, _ob_gx * 3), max(2, _ob_gy * 3))
        cross_brk = max(0.0, cross - 0.82) * 3.0
        return max(-1.0, min(1.0,
            0.34 + 0.46 * plate + (tone - 0.5) * 0.30
            - 0.95 * furrow - 0.40 * cross_brk))
    pats['OLDBARK'] = _oldbark

    def _leather(s, t):
        # PADDED LEATHER (Leder): diamond-quilted cushions - swollen
        # between the stitch seams, a groove along every seam, fine
        # grain (Narben) everywhere. mm-true 45-degree diagonals via the
        # ar-scaled row count; both lattice phases are integer-periodic
        # in s AND t, so the wrap and the top close exactly.
        kp = k + (k & 1)
        rows = max(2, int(round(n * max(0.25, ar))))
        rows += rows & 1
        u = (s * kp + t * rows) % 1.0
        v = (t * rows - s * kp) % 1.0
        du = min(u, 1.0 - u)
        dv = min(v, 1.0 - v)
        de = min(du, dv)
        seam = 1.0 - _smoothstep(0.030, 0.09, de)
        cushion = _smoothstep(0.17, 0.44, max(du, dv))
        grain = (noise(s, t, max(2, kp * 4), max(2, rows * 4))
                 - 0.5) * 0.21
        return max(-1.0, min(1.0,
            0.26 + 0.62 * cushion - 0.88 * seam + grain))
    pats['LEATHER'] = _leather

    def _orange(s, t):
        # ORANGE PEEL (Orangenhaut): deliberate MICRO relief - irregular
        # dimples where two noise octaves agree, wide calm plateaus
        # between. NOT a grid (Pindots) and not velvet (Plush): the
        # one-sided thresholded pits make the skew. Pairs with a SMALL
        # depth (0.10-0.25mm).
        rq = max(2, int(round(n * max(0.25, ar))))
        a = noise(s, t, max(2, k * 4), rq * 2)
        b = noise(s, t, max(2, k * 2), rq)
        v = a * 0.6 + b * 0.4
        pit = _smoothstep(0.55, 0.67, v)
        base = 0.30 + 0.10 * (b - 0.5)
        return max(-1.0, min(1.0, base - 0.90 * pit))
    pats['ORANGE'] = _orange

    _cr_gx = max(3, min(20, k))
    _cr_gy = max(2, int(round(_cr_gx / max(0.25, ar))))
    _cr_sites = [[(rng.random(), rng.random()) for _ in range(_cr_gy)]
                 for _ in range(_cr_gx)]

    def _cracks(s, t):
        # DRIED MUD (Trockenrisse): a voronoi crack network - plates
        # crown slightly, the cracks are NARROW DEEP V-grooves whose
        # width WANDERS (per-point dither - mud never cracks on a grid).
        # The joint is the star: unlike MAZE (even corridors everywhere)
        # and RUBBLE (round stones in wide mortar) the plates dominate
        # the area and only thin dark lines split them.
        x = s * _cr_gx
        y = t * _cr_gy
        ix, iy = int(math.floor(x)), int(math.floor(y))
        f1 = f2 = 1e18
        for dj in (-1, 0, 1):
            for di in (-1, 0, 1):
                cx, cy = ix + di, iy + dj
                jx, jy = _cr_sites[cx % _cr_gx][cy % _cr_gy]
                d = (cx + jx - x) ** 2 + (cy + jy - y) ** 2
                if d < f1:
                    f2 = f1
                    f1 = d
                elif d < f2:
                    f2 = d
        d1, d2 = math.sqrt(f1), math.sqrt(f2)
        wjit = (noise(s, t, max(2, _cr_gx * 2), max(2, _cr_gy * 2))
                - 0.5) * 0.05
        # a PRINTABLE crack: the core keeps full depth for ~0.12 cell
        # (~1mm at a 6mm cell) with steep V-flanks - reads as a fissure,
        # not a hairline the nozzle cannot resolve
        # narrow DEEP core (full depth only within ~0.07 cell of the
        # edge) opening into a wide shallow shoulder - the fissure reads
        # as a dark line with a printable bevel
        crack = 1.0 - _smoothstep(0.07 + wjit, 0.17 + wjit, d2 - d1)
        plate = 0.42 + 0.28 * (1.0 - _smoothstep(0.25, 0.75, d1))
        rough = (noise(s, t, max(2, _cr_gx * 2), max(2, _cr_gy * 2))
                 - 0.5) * 0.10
        return max(-1.0, min(1.0, plate - 1.25 * crack + rough))
    pats['CRACKS'] = _cracks

    def _wrinkle(s, t):
        # HEAVY WRINKLE (grobe Knitterfalten): big soft folds with SHARP
        # crests - two octaves of ridged noise (|n-0.5| -> knife-edge
        # ridges). The folds STRETCH along the fibre (t-cells are 4x
        # coarser) and a slow integer-frequency diagonal swell leans the
        # whole field, like fabric hanging in folds. CREPE's loud sibling:
        # CREPE = fine paper crumple (k*4 cells), this runs k//2 - the
        # autocorrelation length is ~8x longer. (No shear term - a shear
        # breaks the t-periodicity; the swell is integer-safe.)
        a = noise(s, t, max(2, k // 2), max(1, n // 4))
        b = noise(s, t, max(2, k), max(2, n // 2))
        r1 = 1.0 - 2.0 * abs(a - 0.5)
        r2 = 1.0 - 2.0 * abs(b - 0.5)
        swell = 0.82 + 0.18 * math.sin(two_pi * (s * 2 + t))
        return max(-1.0, min(1.0,
            ((0.62 * r1 + 0.38 * r2) * swell - 0.55) * 1.8))
    pats['WRINKLE'] = _wrinkle

    # ================= R266.3 bite 4: decor & haptics ===========================
    # Form-true like bite 2: stagger parities need EVEN row counts
    # (rows += rows & 1) so the offset alternates cleanly over the wrap.

    def _hearts(s, t):
        # DECOR HEARTS: raised hearts in a staggered grid - the classic
        # candy-box / ornament surface. The heart is the implicit classic
        # (x^2+y^2-1)^3 - x^2*y^3 < 0, sampled in mm-square cell units and
        # eased with smoothstep so the print gets a bevel, not a knife
        # edge. Base stays flat and closed (decor, no holes).
        kp = max(2, k)
        rows = max(2, int(round(n * max(0.25, ar))))
        rows += rows & 1            # EVEN: stagger alternates over the wrap
        i = s * kp
        row = int(math.floor(t * rows))
        fx = i - math.floor(i)
        fy = t * rows - row
        u = (fx + (0.5 if row % 2 else 0.0)) % 1.0
        # the heart must stay clear of the row boundaries (flat bands
        # top and bottom) or the stagger phase jumps at the t-wrap
        x = (u - 0.5) * 3.4
        y = (fy - 0.5) * 4.8
        f = (x * x + y * y - 1.0) ** 3 - x * x * y * y * y
        heart = 1.0 - _smoothstep(-0.10, 0.35, f)
        # gentle dome: the swage between the lobes sits highest
        dome = 0.55 + 0.45 * _smoothstep(-1.2, 0.4, y)
        return max(-1.0, min(1.0, -0.32 + 1.15 * heart * dome))
    pats['HEARTS'] = _hearts

    def _golf(s, t):
        # GOLF BALL: dense hemispherical dimples, staggered, NO rim -
        # the aerodynamic skin. Sibling of PERFORATION (holes + raised
        # rim, sparse) and inverse of PINDOTS (knobs): here the dents
        # dominate the surface, the land between is narrow. Cap profile
        # (1-d^2)^0.62 keeps the slope finite at the rim (printable).
        kp = max(2, k)
        rows = max(2, int(round(n * max(0.25, ar))))
        rows += rows & 1            # EVEN: stagger alternates over the wrap
        i = s * kp
        row = int(math.floor(t * rows))
        fx = i - math.floor(i)
        fy = t * rows - row
        if row % 2 == 0:
            u = fx
        else:
            u = (fx + 0.5) % 1.0
        dx, dy = u - 0.5, fy - 0.5
        d = math.sqrt(dx * dx + dy * dy) / 0.49
        if d >= 1.0:
            cap = 0.0
        else:
            cap = math.pow(1.0 - d * d, 0.62)
        return max(-1.0, min(1.0, 0.30 - 1.05 * cap))
    pats['GOLF'] = _golf

    def _basketball(s, t):
        # BASKETBALL: smooth wide CHANNELS over a fine pebble grain.
        # The channels gently snake (integer-frequency wobble only - the
        # wrap stays closed); the pebbles are thresholded value noise
        # (round bumps of near-uniform height, denser and softer than
        # ORANGE peel). Land + pebbles stay positive, channels dive.
        kp = max(2, k)
        rows = max(2, int(round(n * max(0.25, ar))))
        cv = max(2, (kp + 2) // 4)      # vertical channel count
        ch = max(1, rows // 4)          # horizontal channel count
        ws = 0.010 * math.sin(two_pi * t * rows)   # snake, periodic in t
        wt = 0.010 * math.sin(two_pi * s * cv)     # periodic in s
        dv = abs(((s + ws) * cv) % 1.0 - 0.5)
        dh = abs(((t + wt) * ch) % 1.0 - 0.5)
        gv = 1.0 - _smoothstep(0.045, 0.13, dv)
        gh = 1.0 - _smoothstep(0.045, 0.13, dh)
        groove = max(gv, gh)
        pn = noise(s, t, kp * 2, rows * 2)
        pebble = 2.0 * max(0.0, pn - 0.42)
        return max(-1.0, min(1.0, 0.22 + 0.50 * pebble - 1.15 * groove))
    pats['BASKETBALL'] = _basketball

    def _raufaser(s, t):
        # WOODCHIP WALLPAPER (Raufaser): the German classic - a FLAT
        # paper face with sparse short fibre chunks pressed in, two
        # scales, randomly oriented (one family stretched along Z, the
        # other along the perimeter). Reads calm from afar, grippy up
        # close; deliberately NOT noise-all-over (that is SANDSTONE).
        kp = max(2, k)
        rows = max(2, int(round(n * max(0.25, ar))))
        a = noise(s, t, max(2, kp // 2), max(2, rows))          # along t
        b = noise(s, t, max(2, kp), max(2, rows // 2))          # along s
        chunk = (_smoothstep(0.76, 0.84, a)
                 + _smoothstep(0.78, 0.86, b))
        chunk = min(1.0, chunk)
        paper = (noise(s, t, kp * 3, rows * 3) - 0.5) * 0.12
        return max(-1.0, min(1.0, -0.18 + 1.05 * chunk + paper))
    pats['RAUFASER'] = _raufaser

    def _rooftiles(s, t):
        # ROOF TILES (pan tiles, German 'Falzziegel'): overlapping
        # courses - each row of tiles reaches OVER the row below, so
        # every course boundary is a deep shadow step, the belly between
        # steps swells, and the side folds ('Falz') run as vertical
        # grooves with a raised bead beside them. Rows stagger half a
        # tile; EVEN column and row counts keep the wrap closed.
        # pan tiles are NOT staggered: the side folds run STRAIGHT
        # through every course (that is the visual difference to
        # BRICKS) - so no row offset, and the course boundary itself
        # is a symmetric hanging-edge valley (steep, printable)
        ke = max(2, k)
        rows = max(2, int(round(n * max(0.25, ar)))) * 2   # courses
        i = s * ke
        fx = i - math.floor(i)
        j = t * rows
        row = int(math.floor(j))
        fy = j - row
        # course profile: overlap shadow valley at BOTH sides of the
        # course boundary, swelling belly between
        edge = 1.0 - _smoothstep(0.0, 0.16, min(fy, 1.0 - fy))
        belly = (_smoothstep(0.10, 0.48, fy)
                 * (1.0 - _smoothstep(0.52, 0.90, fy)))
        belly = 0.42 + 0.58 * belly
        # side fold: groove at the tile border + raised bead beside it
        db = min(fx, 1.0 - fx)
        falz = 1.0 - _smoothstep(0.03, 0.11, db)
        bead = (_smoothstep(0.11, 0.20, db)
                * (1.0 - _smoothstep(0.24, 0.34, db)))
        grit = (noise(s, t, max(2, ke * 2), max(2, rows)) - 0.5) * 0.14
        return max(-1.0, min(1.0,
            0.30 * belly - 0.28 + 0.38 * bead
            - 1.05 * edge - 0.75 * falz + grit))
    pats['ROOFTILES'] = _rooftiles

    def _crochet(s, t):
        # CROCHET (Haeckeln): chunky handcraft - round knot bumps in a
        # staggered grid, soft arms arching to the row below, and DEEP
        # eyelet holes at the grid corners (the yarn gaps that make
        # crochet read open next to KNIT's closed V-loops). Stagger
        # needs EVEN rows; everything is rounded (printable).
        ke = max(2, k) + (k & 1)
        rows = max(2, int(round(n * max(0.25, ar))))
        rows += rows & 1            # EVEN: stagger alternates over the wrap
        i = s * ke
        row = int(math.floor(t * rows))
        fx = i - math.floor(i)
        fy = t * rows - row
        u = (fx + (0.5 if row % 2 else 0.0)) % 1.0
        # round knot centred in the cell (the flat row-boundary bands
        # keep the stagger phase continuous across the t-wrap)
        dx, dy = u - 0.5, fy - 0.5
        d = math.sqrt(dx * dx + dy * dy) / 0.44
        knot = math.pow(max(0.0, 1.0 - d * d), 0.62) if d < 1.0 else 0.0
        # two soft arms arching out from the knot's flanks, fading
        # BEFORE the row boundary (no content at fy<0.10 / fy>0.90)
        leg = abs(u - 0.5)
        arm = ((1.0 - _smoothstep(0.06, 0.42, leg))
               * _smoothstep(0.10, 0.38, fy)
               * (1.0 - _smoothstep(0.62, 0.88, fy)))
        # eyelet hole: the yarn gap BETWEEN two stitches of a row,
        # centred mid-height at the u-border (symmetric in u)
        ex = min(u, 1.0 - u)
        ey = abs(fy - 0.5) * 0.75
        de = math.sqrt(ex * ex + ey * ey)
        hole = 1.0 - _smoothstep(0.13, 0.26, de)
        return max(-1.0, min(1.0,
            -0.28 + 1.00 * knot + 0.50 * arm - 0.85 * hole))
    pats['CROCHET'] = _crochet

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
                 'BARK', 'SCALES', 'FACETS', 'MACRAME', 'MAP',
                 # R265 (J8 round II, chunk 1): walls, floors, labyrinths
                 'STONEWALL', 'RUBBLE', 'TILES', 'PARQUET', 'LAMINATE',
                 'MAZE', 'PERFORATION', 'VENT', 'CARBON', 'PINDOTS',
                 'OCTAGONS', 'CHAINLINK', 'NETGRID',
                 # R266.2 (J8 bite 3): organics - wood, bark, leather,
                 # orange peel, mud cracks, heavy wrinkle
                 'RINGS', 'OAK', 'BEECH', 'KNOT', 'OLDBARK', 'LEATHER',
                 'ORANGE', 'CRACKS', 'WRINKLE',
                 # R266.3 (J8 bite 4): decor & haptics - hearts, sports
                 # balls, woodchip wallpaper, roof tiles, crochet
                 'HEARTS', 'GOLF', 'BASKETBALL', 'RAUFASER', 'ROOFTILES',
                 'CROCHET')

# R238: opt-in helical tilt angles by pattern. Disabled by default; when
# enabled, the helical shift uses an integer number of turns so the seam
# closes and the texture ends flush at the top. Angles are in degrees.
PATTERN_TILT = {
    'RIDGES': 2.0, 'WAVES': 2.0, 'GRID': 2.0, 'HATCH': 2.0,
    'CHECKER': 2.0, 'HEX': 2.0, 'HONEYCOMB': 2.0,
    'BASKET': 30.0, 'ROPE': 0.0, 'PLANKS': 0.0, 'BRICKS': 2.0,
    'SANDSTONE': 2.0, 'CONCRETE': 2.0, 'CLAY': 2.0, 'CREPE': 2.0,
    'FABRIC': 2.0, 'PLUSH': 2.0, 'HILBERT': 4.0, 'SCRATCH': 2.0,
    'GLITCH': 2.0, 'KNIT': 3.0, 'FLUTED': 0.0, 'BARK': 0.0,
    'SCALES': 2.0, 'FACETS': 0.0, 'MACRAME': 0.0, 'MAP': 0.0,
    'STONEWALL': 0.0, 'RUBBLE': 0.0, 'TILES': 0.0, 'PARQUET': 0.0,
    'LAMINATE': 0.0, 'MAZE': 0.0, 'PERFORATION': 0.0, 'VENT': 0.0,
    'CARBON': 0.0, 'PINDOTS': 0.0, 'OCTAGONS': 0.0, 'CHAINLINK': 0.0,
    'NETGRID': 0.0,
    'RINGS': 0.0, 'OAK': 0.0, 'BEECH': 0.0, 'KNOT': 0.0, 'OLDBARK': 0.0,
    'LEATHER': 0.0, 'ORANGE': 0.0, 'CRACKS': 0.0, 'WRINKLE': 2.0,
    'HEARTS': 0.0, 'GOLF': 0.0, 'BASKETBALL': 0.0, 'RAUFASER': 0.0,
    'ROOFTILES': 0.0, 'CROCHET': 0.0,
}


def apply_texture(src, out_dir=None, mode='FUZZY', fuzzy_thick=0.3,
                  fuzzy_density=100.0, bump_pattern='RIDGES', bump_scale=10.0,
                  bump_amp=0.35, direction='OUT', bed=None, version=1,  # version: retired (R158, folder-global auto)
                  seed=91, zsize=None, map_file=None,
                  map_mode='TILE', map_pos='CENTER', tilt=False, progress=None):
    """Returns (new_path, info). Raises ValueError on bad parameters.

    R175 parameter semantics (the LCD speaks these names):
      bump_scale = 'size around' guideline in mm  -> snapped to k ridges
      zsize      = 'Z size' guideline in mm       -> snapped to n repeats
      bump_amp   = 'depth' in mm (0.05..4.0; above 1.0 = DEEP RELIEF,
                   see the R266 note below)
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
    if not (0.05 <= float(bump_amp) <= 4.0):
        raise ValueError('pattern depth %.2fmm out of range (0.05..4.0)'
                         % float(bump_amp))
    # R266 DEEP RELIEF: above 1.0mm the displaced path gets LONGER (and
    # shorter) in places - leaving E untouched would thin the lines on
    # stretched flanks. In deep mode (BUMPS only) every chord's E rides
    # its real length (relative E only - on absolute-E files we stay
    # slicer-true and SAY so in the header), the subdivision refines by
    # field steepness so the structure resolves before the nozzle
    # smooths it, and the wall stays CLOSED: displacement is continuous
    # and inner walls keep following (R224). Steep flanks print as
    # overhangs - that is physics, not a hole.
    _deep = (mode == 'BUMPS' and float(bump_amp) > 1.0)
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
                # R266 field fix (vwbus fixture): a purge line 'G1 X60 E9'
                # carries X but NO Y - before any Y is known the point has
                # no placeable geometry. Skip it and keep the last known
                # position (never invent one), exactly like pass 2 does.
                if y is None:
                    continue
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
                            and g[4] > _MIN_E and g[2] is not None):
                        # R266: g[2] None = X-only move (purge line) - no
                        # 2D wall geometry, must not touch the loop length
                        if px_l is not None:
                            cur_len += math.hypot(g[1] - px_l, g[2] - py_l)
                        px_l, py_l = g[1], g[2]
                    elif g[2] is not None:
                        if cur_len > 0.0:
                            lens.append(cur_len)
                            cur_len = 0.0
                        px_l, py_l = g[1], g[2]
                    continue
                ga = _parse_arc(ls)
                if (ga is not None and ga[1] is not None
                        and px_l is not None and py_l is not None):
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

    # Optional R238 helical tilt: integer turns preserve the seam and flush
    # top while the lattice leaves the layer plane.
    _tilt_deg = (PATTERN_TILT[bump_pattern] if tilt else 0.0)
    m238 = 0
    if _tilt_deg > 0.0 and circum > 0 and height > 0:
        m238 = max(1, int(round(
            height * k / (circum * math.tan(math.radians(_tilt_deg))))))
    tilt_eff = (math.degrees(math.atan(height * k / (m238 * circum)))
                if m238 else 0.0)

    pats = _build_patterns(k, n, int(seed), img,
                           map_mode=str(map_mode).upper(),
                           map_pos=str(map_pos).upper(),
                           map_frac=map_frac,
                           ar=(eff_zsize / eff_size) if eff_size > 0 else 1.0)
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
             'inner_shifted': 0, 'm204_scrub': 0, 'e_riden': 0}
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
    # R266 deep relief: _sh_out = the position the LAST _shift_txt call
    # actually WROTE (rounded, clamped); _wr = the last position written
    # to the file at all (shifted wall moves and untouched travels both
    # update it) - the E compensation measures chord lengths between the
    # positions the FILE really carries.
    _sh_out = [0.0, 0.0]
    _wr = [None, None]

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
        (None -> the classic angle fraction, the safe fallback).
        R266: also reports the WRITTEN position via _sh_out (rounded and
        bed-clamped) - the deep-relief E compensation needs the real
        chord length after displacement."""
        dx, dy = ((x - px, y - py)
                  if px is not None and py is not None else (0.0, 0.0))
        ln = math.hypot(dx, dy)
        stats['moves'] += 1
        if ln <= 0.01:
            _sh_out[0], _sh_out[1] = x, y
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
            _sh_out[0], _sh_out[1] = nx, ny
        else:
            _sh_out[0], _sh_out[1] = x, y
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
        if _deep and e_rel:
            fo.write('; fuzzy scatters / bumps displace ONLY outer-wall '
                     'vertices - tags, features, Z stay untouched; R266: '
                     'chord E follows the displaced length (totals kept)\n')
        else:
            fo.write('; fuzzy scatters / bumps displace ONLY outer-wall '
                     'vertices - tags, features, E and Z stay untouched\n')
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
        if _deep:
            fo.write('; R266 DEEP RELIEF: depth %.2fmm - on relative-E '
                     'sections every chord E rides its real length '
                     '(totals kept), steep flanks are subdivided; '
                     'absolute-E sections stay slicer-true\n'
                     % float(bump_amp))
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
            elif ls.startswith('G92'):
                me92 = re.match(r'^G92(?:\s+E(-?[\d.]+))?', ls)
                if me92 and me92.group(1) is not None:
                    last_e = float(me92.group(1))
            else:
                _me266 = _EMODE.match(ls.split(';', 1)[0].strip())
                if _me266:
                    # Klipper: G90/G91 reset E to absolute/relative, an
                    # explicit M82/M83 overrides them. Comments ignored
                    # (R266 field fix: 'M83 ; relative...' never matched).
                    e_rel = _me266.group(1) in ('G91', 'M83')
            g = _parse_move(ls)
            if g is not None and g[3] is not None:
                cur_z_e = g[3]           # R186: emission-pass Z tracking
            if (g and g[0] == 'G1' and (cur_outer or all_is_wall
                                        or (cur_inner and mode == 'BUMPS'))
                    and g[4] is not None and g[4] > _MIN_E
                    and g[1] is not None and g[2] is not None):
                # R266: g[2] None = X-only purge move - passthrough below
                x, y = g[1], g[2]
                z = g[3]
                _zz231 = z if z is not None else cur_z_e
                _ln231 = (math.hypot(x - px, y - py)
                          if px is not None and py is not None else 0.0)
                # G4: BUMPS resamples long straight wall moves before applying
                # displacement. A vase with 8 vertices/layer otherwise gets
                # only 8 texture samples. Split by XY arclength, preserve the
                # total E exactly (including relative-E residual), and retain
                # the original line/comment on the final chord.
                _parts = (max(1, min(4096, int(math.ceil(_ln231 / 1.5))))
                          if mode == 'BUMPS' else 1)
                _x0, _y0 = (x, y) if px is None or py is None else (px, py)
                _z0 = cur_z_e if cur_z_e is not None else (z or 0.0)
                # R266 deep relief: refine the subdivision by field
                # STEEPNESS too - a 3mm bark relief needs ~1mm chord
                # resolution in the displacement, not only in the path
                if _deep and px is not None and py is not None:
                    _slope266 = abs(pattern(x, y, _z0)
                                   - pattern(_x0, _y0, _z0)) * sig
                    _parts = max(_parts, min(256,
                                             int(math.ceil(_slope266 / 0.4))))
                _e0 = last_e
                _edelta = (g[4] if e_rel else g[4] - _e0)
                _acc_e = 0.0
                _tgt_e = 0.0 if (_deep and e_rel) else g[4]
                _feed = _tok(ls.split(';', 1)[0], 'F')
                for _part in range(1, _parts + 1):
                    _f = _part / float(_parts)
                    _qx = _x0 + (x - _x0) * _f
                    _qy = _y0 + (y - _y0) * _f
                    _qz = _z0 + (z - _z0) * _f if z is not None else None
                    _seglen = _ln231 / _parts
                    _sar231 = _s231(_qx, _qy, _qz, _seglen)
                    if cur_outer:
                        _sout_put231(_qz, _qx, _qy, _sar231)
                    # R266: displace FIRST, then let E ride the written
                    # chord length (relative E + deep mode only - every
                    # other file keeps the exact legacy numbers)
                    if _part == _parts:
                        _outtxt = _shift_txt(ls, _qx, _qy, _qz,
                            inner=(cur_inner and not cur_outer
                                   and mode == 'BUMPS'), s_arc=_sar231)
                    else:
                        _line = 'G1 X%.3f Y%.3f' % (_qx, _qy)
                        if _qz is not None:
                            _line += ' Z%.3f' % _qz
                        _line += ' E%.5f' % 0.0
                        if _feed is not None:
                            # R246: every inserted sub-part carries the F of the
                            # original move, not only the first one - a reader
                            # must not depend on modal carryover (r91 gate:
                            # every emitted G1 keeps its F value)
                            _line += ' F%g' % _feed
                        _outtxt = _shift_txt(_line, _qx, _qy, _qz,
                            inner=(cur_inner and not cur_outer
                                   and mode == 'BUMPS'), s_arc=_sar231)
                    _f266 = 1.0
                    if _deep and e_rel:
                        _lnew266 = (
                            math.hypot(_sh_out[0] - _wr[0],
                                       _sh_out[1] - _wr[1])
                            if _wr[0] is not None else _seglen)
                        _f266 = (max(0.1, min(8.0, _lnew266 / _seglen))
                                 if _seglen > 1e-9 else 1.0)
                        if _f266 > 1.8 or _f266 < 0.45:
                            stats['steep'] = stats.get('steep', 0) + 1
                        _tgt_e += _edelta * _f266 / _parts
                        stats['e_riden'] += 1
                    _wr[0], _wr[1] = _sh_out[0], _sh_out[1]
                    if e_rel:
                        if _part == _parts:
                            _qe = max(0.0, round(_tgt_e, 5) - _acc_e)
                        else:
                            _qe = round(_edelta * _f266 / _parts, 5)
                            _acc_e += _qe
                        _outtxt = re.sub(r'(?<![A-Z])E-?[\d.]+',
                                         'E%.5f' % _qe, _outtxt, count=1)
                    else:
                        _qe = g[4] if _part == _parts else _e0 + _edelta * _f
                        if _part != _parts:
                            _outtxt = re.sub(r'(?<![A-Z])E-?[\d.]+',
                                             'E%.5f' % _qe, _outtxt, count=1)
                    fo.write(_outtxt + '\n')
                    _st231['arc'] += _seglen
                stats['subdivisions'] = stats.get('subdivisions', 0) + _parts - 1
                px, py = x, y
                last_e = g[4]
                continue
            # ---- R95: outer-wall G2/G3 arcs -> short G1 chords, textured ---
            ga = _parse_arc(ls)
            if ga is not None and ga[3] is not None:
                cur_z_e = ga[3]           # R186: emission-pass Z tracking
            if (ga and (cur_outer or all_is_wall
                        or (cur_inner and mode == 'BUMPS')) and ga[7] is not None
                    and ga[7] > _MIN_E and px is not None and py is not None):
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
                    _accA266 = 0.0
                    _tgtA266 = 0.0 if (_deep and e_rel) else e_arc
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
                        _outA266 = _shift_txt(
                            ch, qx, qy, z1,
                            inner=(cur_inner and not cur_outer
                                   and mode == 'BUMPS'),
                            s_arc=_sar231)
                        if _deep and e_rel:
                            # R266: arc chord, same rule as straight moves
                            _lA266 = (
                                math.hypot(_sh_out[0] - _wr[0],
                                           _sh_out[1] - _wr[1])
                                if _wr[0] is not None else cl)
                            _fA266 = (max(0.1, min(8.0, _lA266 / cl))
                                      if cl > 1e-9 else 1.0)
                            if _fA266 > 1.8 or _fA266 < 0.45:
                                stats['steep'] = stats.get('steep', 0) + 1
                            _tgtA266 += e_arc * frac * _fA266
                            stats['e_riden'] += 1
                            ec = max(0.0, round(_tgtA266, 5) - _accA266)
                            _accA266 += ec
                            _outA266 = re.sub(r'(?<![A-Z])E-?[\d.]+',
                                              'E%.5f' % ec, _outA266, count=1)
                        _wr[0], _wr[1] = _sh_out[0], _sh_out[1]
                        fo.write(_outA266 + '\n')
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
                if gm[2] is not None:      # R266: X-only keeps the last
                    px, py = gm[1], gm[2]  # known position (no crash)
                    # R266: a travel line WRITES a position too - the next
                    # wall chord measures its length from HERE, not from
                    # the last wall vertex before the travel
                    _wr[0], _wr[1] = gm[1], gm[2]
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
            'subdivisions': stats.get('subdivisions', 0),
            'sample_step_mm': 1.5,
            'deep': bool(_deep),
            'deep_e_compensated': bool(_deep and stats['e_riden'] > 0),
            'deep_e_chords': stats['e_riden'],
            'deep_step_mm': (0.4 if _deep else 0.0),
            'steep_segments': stats.get('steep', 0),
            'm204_scrub': stats['m204_scrub'],
            'tilt': round(tilt_eff, 1), 'tilt_turns': m238,
            'map_mode': (str(map_mode).upper()
                         if mode == 'BUMPS' and bump_pattern == 'MAP' else ''),
            'map_pos': (str(map_pos).upper()
                        if mode == 'BUMPS' and bump_pattern == 'MAP' else ''),
            'secs': round(time.time() - t0, 2)}
    return out, info
