#!/usr/bin/env python3
"""R63 BUILD-TIME helper: generate the embedded label fonts for r2_postproc.py.

NOT needed on the Pi! The generated data is embedded in r2_postproc.py as
FONT_PIXEL / FONT_MONO / FONT_SMOOTH. Re-run this script only to regenerate
(requires Pillow + DejaVu fonts).

Fonts:
  PIXEL  R116: Press Start 2P (Google Fonts, SIL OFL) as a STROKE font - the
         old 7x9 bitmap dot-matrix was unreadable (removed R80). Blocky
         arcade-pixel letterforms, skeleton = clean single lines
  MONO   single-line stroke font from DejaVuSansMono skeleton, advance 7
  SMOOTH single-line stroke font from DejaVuSans skeleton, proportional
  COND   Oswald (Google Fonts, SIL OFL - tools/fonts_src/) - condensed, tall
         x-height: THE small-text font (R82)
  NARROW Roboto Condensed (Google Fonts, SIL OFL) - clean + narrow (R82)
  CAPS   Bebas Neue (Google Fonts, SIL OFL) - caps-only display font; the
         lowercase slots are cloned from the capitals at import (R82)
  SCRIPT R116: Dancing Script (Google Fonts, SIL OFL) - connected
         calligraphy / Schreibschrift
  HAND   R116: Caveat (Google Fonts, SIL OFL) - casual handwriting
  PLATE  R116: D-DIN (Datto, SIL OFL) - DIN 1451, the German license-plate
         and engineering-lettering look; THE font for small clean labels too

Stroke-font coordinates: x right, y DOWN, every glyph in a box of height
10 units (cap height ~8, descender ~2), ink starts at x=0.
PIXEL grid: 7 wide x 9 tall, advance 8, rows top->bottom, bit 6..0 = col 0..6.

Charset must match the LCD charset in macros/16_labels.cfg exactly.
"""
import os
from PIL import Image, ImageDraw, ImageFont

CHARSET = ("ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz"
           "0123456789 ÄÖÜäöüß-.,:;!?+*/()[]=%#&@°'<>_")

PX = 120           # render size (px) for the stroke fonts
TOTAL_UNITS = 10.0 # stroke fonts: full box height (cap+descender) in units


# ---------------------------------------------------------------- thinning ----
def thin_zhang_suen(px):
    def g(x, y):
        return (x, y) in px
    changed = True
    while changed:
        changed = False
        for step in (0, 1):
            remove = []
            for (x, y) in px:
                vals = [1 if g(x + dx, y + dy) else 0
                        for (dx, dy) in ((0, -1), (1, -1), (1, 0), (1, 1),
                                         (0, 1), (-1, 1), (-1, 0), (-1, -1))]
                b = sum(vals)
                if b < 2 or b > 6:
                    continue
                a = sum(1 for i in range(8) if vals[i] == 0 and vals[(i + 1) % 8] == 1)
                if a != 1:
                    continue
                if step == 0:
                    if (vals[0] and vals[2] and vals[4]) or (vals[2] and vals[4] and vals[6]):
                        continue
                else:
                    if (vals[0] and vals[2] and vals[6]) or (vals[0] and vals[4] and vals[6]):
                        continue
                remove.append((x, y))
            if remove:
                changed = True
                for c in remove:
                    px.discard(c)
    return px


def _neighbors(px, p):
    x, y = p
    out = []
    for dy in (-1, 0, 1):
        for dx in (-1, 0, 1):
            if dx or dy:
                q = (x + dx, y + dy)
                if q in px:
                    out.append(q)
    return out


def vectorize(px):
    """skeleton pixel set -> list of polylines [(x,y), ...] via graph tracing.

    Endpoints (deg 1) and junctions (deg >= 3) form clusters; each cluster
    collapses to its centroid. Edges between clusters become polylines,
    node-free rings become closed polylines, edge-free clusters become dots.
    """
    if not px:
        return []
    px = set(px)
    # drop isolated specks
    px = {p for p in px if _neighbors(px, p)}
    if not px:
        return []
    deg = {p: len(_neighbors(px, p)) for p in px}
    node = {p for p in px if deg[p] != 2}
    # ---- cluster the node pixels (8-conn) ----
    cluster_of = {}
    clusters = []          # list of (rep_pixel, [pixels])
    for p in node:
        if p in cluster_of:
            continue
        cid = len(clusters)
        comp = [p]
        cluster_of[p] = cid
        i = 0
        while i < len(comp):
            for q in _neighbors(px, comp[i]):
                if q in node and q not in cluster_of:
                    cluster_of[q] = cid
                    comp.append(q)
            i += 1
        clusters.append(comp)

    def c_rep(cid):
        comp = clusters[cid]
        return (round(sum(p[0] for p in comp) / len(comp), 1),
                round(sum(p[1] for p in comp) / len(comp), 1))

    in_node = lambda p: p in cluster_of

    # ---- walk edges: from every node pixel to the next cluster ----
    lines = []
    walked = set()          # first edge pixel of a walked edge (dedup)
    for cid, comp in enumerate(clusters):
        for np_ in comp:
            for nb in _neighbors(px, np_):
                if in_node(nb):
                    continue
                if nb in walked:
                    continue
                path = [np_]
                prev, cur = np_, nb
                walked.add(cur)
                while True:
                    path.append(cur)
                    if in_node(cur):
                        break
                    nxts = [q for q in _neighbors(px, cur) if q != prev]
                    if not nxts:
                        break
                    prev, cur = cur, nxts[0]
                    if in_node(cur):
                        path.append(cur)
                        break
                # replace node endpoints with cluster reps for smooth junctions
                pts = [c_rep(cluster_of[path[0]])]
                for p in path[1:-1]:
                    pts.append(p)
                pts.append(c_rep(cluster_of[path[-1]]))
                lines.append(pts)
    # ---- node-free rings ----
    used = set()
    for l in lines:
        used.update(p for p in l)
    for p in px:
        if in_node(p) or p in used or deg[p] != 2:
            continue
        ring = [p]
        cur = p
        while True:
            nxts = [q for q in _neighbors(px, cur) if q not in ring]
            if not nxts:
                break
            cur = nxts[0]
            ring.append(cur)
        if len(ring) >= 4:
            ring.append(ring[0])
            lines.append(ring)
    # ---- clusters without edges: dots ('.' ',' dots of i/j) ----
    touched = set()
    for l in lines:
        for p in l:
            touched.add(p)
    for cid, comp in enumerate(clusters):
        if any(p in touched for p in comp):
            continue
        # standalone dot cluster
        r = c_rep(cid)
        lines.append([(r[0], r[1] - 0.4), (r[0], r[1] + 0.4)])
    return lines


def rdp(points, eps):
    if len(points) < 3:
        return points
    (x1, y1), (x2, y2) = points[0], points[-1]
    dmax, idx = 0.0, 0
    for i in range(1, len(points) - 1):
        x0, y0 = points[i]
        dx, dy = x2 - x1, y2 - y1
        ln2 = dx * dx + dy * dy
        if ln2 == 0:
            d = ((x0 - x1) ** 2 + (y0 - y1) ** 2) ** 0.5
        else:
            t = max(0.0, min(1.0, ((x0 - x1) * dx + (y0 - y1) * dy) / ln2))
            d = ((x0 - x1 - t * dx) ** 2 + (y0 - y1 - t * dy) ** 2) ** 0.5
        if d > dmax:
            dmax, idx = d, i
    if dmax > eps:
        left = rdp(points[:idx + 1], eps)
        right = rdp(points[idx:], eps)
        return left[:-1] + right
    return [points[0], points[-1]]


def stroke_len(pts):
    return sum(((pts[i + 1][0] - pts[i][0]) ** 2 + (pts[i + 1][1] - pts[i][1]) ** 2) ** 0.5
               for i in range(len(pts) - 1))


def _dedupe(strokes):
    """drop reversed/identical duplicates (an edge walked from both ends)"""
    seen = set()
    out = []
    for s in strokes:
        key = (tuple(s[0]), tuple(s[-1])) if s[0] <= s[-1] else (tuple(s[-1]), tuple(s[0]))
        if key in seen:
            continue
        seen.add(key)
        out.append(s)
    return out


def _v(seg):
    """direction vector of a 2-point segment"""
    return (seg[1][0] - seg[0][0], seg[1][1] - seg[0][1])


def _ang(v1, v2):
    import math
    n1 = math.hypot(*v1)
    n2 = math.hypot(*v2)
    if n1 < 1e-9 or n2 < 1e-9:
        return 0.0
    c = max(-1.0, min(1.0, (v1[0] * v2[0] + v1[1] * v2[1]) / (n1 * n2)))
    return math.degrees(math.acos(c))


def merge_strokes(strokes, dist_tol=0.45, ang_tol=32):
    """chain near-collinear strokes whose endpoints touch (junction fuzz)."""
    strokes = [list(s) for s in strokes if len(s) >= 2]
    changed = True
    while changed:
        changed = False
        for i in range(len(strokes)):
            if changed:
                break
            for j in range(len(strokes)):
                if i == j:
                    continue
                a, b = strokes[i], strokes[j]
                if len(a) < 2 or len(b) < 2:
                    continue
                cands = ((a, b, False, False), (a, b, False, True),
                         (a, b, True, False), (a, b, True, True))
                for aa0, bb0, ra, rb in cands:
                    aa = aa0[::-1] if ra else aa0
                    bb = bb0[::-1] if rb else bb0
                    d = ((aa[-1][0] - bb[0][0]) ** 2 + (aa[-1][1] - bb[0][1]) ** 2) ** 0.5
                    if d > dist_tol:
                        continue
                    if len(aa) >= 2 and len(bb) >= 2:
                        if _ang(_v((aa[-2], aa[-1])), _v((bb[0], bb[1]))) > ang_tol:
                            continue
                    merged = aa + bb[1:]
                    strokes[i] = merged
                    del strokes[j]
                    changed = True
                    break
                if changed:
                    break
    return strokes


# ---------------------------------------------------------------- builders ----
def components(grid):
    """8-connected components of a pixel set -> list of sets"""
    seen = set()
    comps = []
    for p in grid:
        if p in seen:
            continue
        comp = {p}
        seen.add(p)
        stack = [p]
        while stack:
            cur = stack.pop()
            for q in _neighbors(grid, cur):
                if q not in seen:
                    seen.add(q)
                    comp.add(q)
                    stack.append(q)
        comps.append(comp)
    return comps


def is_dot_comp(comp):
    """compact, roughly round blob -> print as a dab instead of thinning it
    away (period, umlaut dots, i/j dots, degree sign, ...)"""
    xs = [p[0] for p in comp]
    ys = [p[1] for p in comp]
    w = max(xs) - min(xs) + 1
    h = max(ys) - min(ys) + 1
    if max(w, h) > 20 or len(comp) > 500:
        return False
    return min(w, h) >= 0.55 * max(w, h)


def build_stroke_font(ttf_path, mono=False, thresh=100):
    """R73: BASELINE-ALIGNED stroke fonts.

    Every glyph's y is stored relative to the shared baseline (uy = CAP on the
    baseline, cap tops at uy ~ 0, descenders down to uy ~ CAP + DESC). The old
    build normalized each glyph to its OWN ink box top - so 'x' floated as high
    as 'A' and 'g' barely dipped: the printed text looked 'compressed' and was
    never baseline-aligned. Coordinates stay x-right / y-DOWN as before.
    """
    font = ImageFont.truetype(ttf_path, PX)
    a, dsc = font.getmetrics()
    scale = TOTAL_UNITS / float(a + dsc)

    def _ink(ch):
        img = Image.new('L', (600, 600), 0)
        ImageDraw.Draw(img).text((80, 80), ch, font=font, fill=255)
        bb = img.getbbox()
        if bb is None:
            return None
        return img, bb                  # bbox: (x0, top, x1, row-below-last-ink)

    # ---- shared vertical metrics (medians, so odd glyphs cannot skew them) --
    # baseline measured EMPIRICALLY (flat-bottom caps sit exactly on it) - the
    # Pillow ascender math differs between versions/anchors, ink does not
    bases = sorted(bb[3] - 1 for _i, bb in
                   (_ink(ch) for ch in 'HILMNE') if bb)
    y_base = bases[len(bases) // 2] if bases else 80 + a
    cap_tops = sorted((y_base - bb[1]) * scale for _i, bb in
                      (_ink(ch) for ch in 'ABCDEFGHIJKLMNOPQRSTUVWXYZ') if bb)
    cap_units = cap_tops[len(cap_tops) // 2] if cap_tops else 7.0
    xh = sorted((y_base - bb[1]) * scale for _i, bb in
                (_ink(ch) for ch in 'xonmuvwz') if bb)
    xh_units = xh[len(xh) // 2] if xh else cap_units * 0.66
    dd = sorted((bb[3] - 1 - y_base) * scale for _i, bb in
                (_ink(ch) for ch in 'gjpqy') if bb)
    desc_units = max(0.2, dd[len(dd) // 2]) if dd else 1.8

    glyphs = {}
    for ch in CHARSET:
        adv = font.getlength(ch) * scale
        if ch == ' ':
            glyphs[ch] = [] if mono else (round(max(adv, 2.5), 1), [])
            continue
        r = _ink(ch)
        if r is None:
            glyphs[ch] = [] if mono else (round(max(adv, 2.5), 1), [])
            continue
        img, (x0b, y0b, x1b, y1b) = r
        w, h = x1b - x0b, y1b - y0b
        grid = set()
        for y in range(h):
            for x in range(w):
                if img.getpixel((x0b + x, y0b + y)) > thresh:
                    grid.add((x + 1, y + 1))
        comps = components(grid)
        big = set()
        dots = []           # centroid px coords
        for comp in comps:
            if is_dot_comp(comp):
                dots.append((sum(p[0] for p in comp) / len(comp),
                             sum(p[1] for p in comp) / len(comp)))
            else:
                big |= comp
        sk = thin_zhang_suen(big)
        polys = vectorize(sk)
        xs = [x for (x, y) in grid] or [0]
        gx0 = min(xs)
        # grid coords are relative to the ink bbox (grid (1,1) = pixel
        # (x0b, y0b)) - shift y into IMAGE coords before comparing with y_base
        yoff = y0b - 1
        strokes = []
        for poly in polys:
            simp = rdp(poly, 1.2)
            pts = []
            for (x, y) in simp:
                ux = (x - gx0) * scale
                # BASELINE-relative: pixels above the baseline (smaller y) land
                # below uy = CAP in y-DOWN coords; descenders above it
                uy = (y + yoff - y_base) * scale + cap_units
                q = (round(ux, 1), round(uy, 1))
                if not pts or pts[-1] != q:
                    pts.append(q)
            if len(pts) >= 2:
                strokes.append(pts)
        for (cx, cy) in dots:
            strokes.append([(round((cx - gx0) * scale, 1), round((cy + yoff - y_base) * scale + cap_units - 0.5, 1)),
                            (round((cx - gx0) * scale, 1), round((cy + yoff - y_base) * scale + cap_units + 0.5, 1))])
        strokes = _dedupe(strokes)
        strokes = merge_strokes(strokes)
        # drop micro-fragments (junction noise) - dots are 1.0 long, they survive
        strokes = [s for s in strokes if stroke_len(s) >= 0.30]
        # R73 baseline SNAP: thinning pulls stroke ends ~1-2px inside the ink, so
        # flat-bottom glyphs (A, H, x ...) ended ~0.4 units ABOVE the baseline
        # while round ones (x, o) hit it - mixed text wobbled. Glyphs whose ink
        # bottom sits on the baseline (within 3px above / 0.6px below) get their
        # whole skeleton shifted so the lowest stroke point = the baseline.
        all_ys = [p[1] for s in strokes for p in s]
        if all_ys:
            ink_bottom = y1b - 1
            if y_base - 3.0 <= ink_bottom <= y_base + 0.6:
                sbot = max(all_ys)
                if abs(cap_units - sbot) > 0.01:
                    strokes = [[(px, py + cap_units - sbot) for (px, py) in s]
                               for s in strokes]
        if mono:
            glyphs[ch] = strokes
        else:
            glyphs[ch] = (round(adv, 1), strokes)
    metrics = {'cap': round(cap_units, 2), 'xheight': round(xh_units, 2),
               'desc': round(desc_units, 2), 'height': round(cap_units + desc_units, 2)}
    return glyphs, metrics


# hand-tuned overrides: tiny punctuation/dots auto-sample badly at 7x9
# (rows top->bottom, bit 6..0 = col 0..6)
PIXEL_OVERRIDES = {
    '.': [0b0000000, 0b0000000, 0b0000000, 0b0000000, 0b0000000,
          0b0000000, 0b0011100, 0b0000000, 0b0000000],
    ',': [0b0000000, 0b0000000, 0b0000000, 0b0000000, 0b0000000,
          0b0000000, 0b0011100, 0b0111000, 0b0000000],
    ':': [0b0000000, 0b0000000, 0b0000000, 0b0000000, 0b0011100,
          0b0000000, 0b0011100, 0b0000000, 0b0000000],
    ';': [0b0000000, 0b0000000, 0b0000000, 0b0000000, 0b0011100,
          0b0000000, 0b0011100, 0b0111000, 0b0000000],
    '!': [0b0000000, 0b0000000, 0b0011100, 0b0011100, 0b0011100,
          0b0011100, 0b0000000, 0b0011100, 0b0000000],
    "'": [0b0000000, 0b0011100, 0b0011100, 0b0000000, 0b0000000,
          0b0000000, 0b0000000, 0b0000000, 0b0000000],
    '°': [0b0000000, 0b0011100, 0b0100010, 0b0011100, 0b0000000,
          0b0000000, 0b0000000, 0b0000000, 0b0000000],
    'i': [0b0000000, 0b0011100, 0b0000000, 0b0011100, 0b0011100,
          0b0011100, 0b0011100, 0b0011100, 0b0000000],
    'j': [0b0000000, 0b0011100, 0b0000000, 0b0011100, 0b0011100,
          0b0011100, 0b0011100, 0b0111000, 0b0000000],
    'l': [0b0000000, 0b0011100, 0b0011100, 0b0011100, 0b0011100,
          0b0011100, 0b0011100, 0b0011100, 0b0000000],
    'O': [0b0000000, 0b0011100, 0b0110110, 0b1100011, 0b1100011,
          0b0110110, 0b0011100, 0b0000000, 0b0000000],
    '0': [0b0000000, 0b0011100, 0b0110110, 0b1101011, 0b1101011,
          0b0110110, 0b0011100, 0b0000000, 0b0000000],
    '?': [0b0000000, 0b0111110, 0b1100011, 0b0000110, 0b0011100,
          0b0001100, 0b0000000, 0b0001100, 0b0000000],
    'ä': [0b0010100, 0b0000000, 0b0000000, 0b0111110, 0b0011110,
          0b1111110, 0b1111110, 0b0000000, 0b0000000],
    'ö': [0b0010100, 0b0000000, 0b0000000, 0b0111110, 0b1101011,
          0b1101011, 0b0111110, 0b0000000, 0b0000000],
    'ü': [0b0010100, 0b0000000, 0b0000000, 0b0110110, 0b0110110,
          0b0110110, 0b0111110, 0b0000000, 0b0000000],
    'ß': [0b0000000, 0b0011110, 0b0110011, 0b0111110, 0b0110110,
          0b1101011, 0b1100110, 0b0000000, 0b0000000],
    '_': [0b0000000, 0b0000000, 0b0000000, 0b0000000, 0b0000000,
          0b0000000, 0b0000000, 0b0000000, 0b1111111],
    '-': [0b0000000, 0b0000000, 0b0000000, 0b0000000, 0b0000000,
          0b0111110, 0b0000000, 0b0000000, 0b0000000],
}


KEEP_BOTTOM = set('gjpqy\u00df,;Q!?_@%&')


def build_pixel_font(ttf_path, cols=7, rows=9, thresh=0.22):
    px_size = 72
    font = ImageFont.truetype(ttf_path, px_size)
    a, dsc = font.getmetrics()
    glyphs = {}
    for ch in CHARSET:
        adv_px = max(1, round(font.getlength(ch)))
        img = Image.new('L', (adv_px + 2, a + dsc + 2), 0)
        ImageDraw.Draw(img).text((1, 1), ch, font=font, fill=255)
        w, h = img.size
        grid = []
        for r in range(rows):
            row = 0
            for c in range(cols):
                x0 = int(c * w / cols)
                x1 = max(x0 + 1, int((c + 1) * w / cols))
                y0 = int(r * h / rows)
                y1 = max(y0 + 1, int((r + 1) * h / rows))
                tot = cnt = 0
                for yy in range(y0, y1):
                    for xx in range(x0, x1):
                        tot += img.getpixel((xx, yy))
                        cnt += 1
                if cnt and tot / (cnt * 255.0) > thresh:
                    row |= 1 << (cols - 1 - c)
            grid.append(row)
        # stray cleanup: antialiasing leaves 1-3 dust pixels in the two rows
        # below the baseline. Chars that LEGITIMATELY have ink there (descender
        # tails, dots, the underscore) keep it; everything else gets rows 7-8
        # cleared when there is only dust (<= 3 px) in them.
        if ch not in KEEP_BOTTOM:
            if bin(grid[rows - 2]).count('1') + bin(grid[rows - 1]).count('1') <= 3:
                grid[rows - 2] = 0
                grid[rows - 1] = 0
        glyphs[ch] = PIXEL_OVERRIDES.get(ch, grid)
    return glyphs


# ------------------------------------------------------------------ output ----
def fmt_strokes(strokes):
    return ';'.join(' '.join(f'{x:g},{y:g}' for (x, y) in s) for s in strokes)


def dump_pixel(px):
    for ch in CHARSET:
        art = [''.join('#' if px[ch][r] & (1 << (6 - c)) else '.'
                       for c in range(7)) for r in range(9)]
        print((ch if ch != ' ' else '_') + ' ' + '/'.join(art))


def dump_strokes_ascii(strokes, width=36, height=14, label=''):
    """rasterize traced strokes to ascii so quality is checkable without eyes"""
    if not strokes:
        print(label, '(empty!)')
        return
    xs = [p[0] for s in strokes for p in s]
    ys = [p[1] for s in strokes for p in s]
    x0, x1, y0, y1 = min(xs), max(xs), min(ys), max(ys)
    sx = (width - 1) / max(0.001, x1 - x0)
    sy = (height - 1) / max(0.001, y1 - y0)
    grid = [[' '] * width for _ in range(height)]
    for s in strokes:
        for (xa, ya), (xb, yb) in zip(s, s[1:]):
            ax, ay = (xa - x0) * sx, (ya - y0) * sy
            bx, by = (xb - x0) * sx, (yb - y0) * sy
            n = int(max(abs(bx - ax), abs(by - ay))) * 2 + 1
            for i in range(n + 1):
                t = i / n
                xx = int(round(ax + (bx - ax) * t))
                yy = int(round(ay + (by - ay) * t))
                if 0 <= xx < width and 0 <= yy < height:
                    grid[yy][xx] = '#'
    print(label)
    for row in grid:
        print('  ' + ''.join(row))


def main():
    dejavu = '/usr/share/fonts/truetype/dejavu/'
    if not os.path.isdir(dejavu):
        raise SystemExit('DejaVu fonts not found: ' + dejavu)

    px = build_pixel_font(os.path.join(dejavu, 'DejaVuSans-Bold.ttf'))
    print('== PIXEL (7x9) ==')
    dump_pixel(px)

    mo, m_mo = build_stroke_font(os.path.join(dejavu, 'DejaVuSansMono.ttf'), mono=True)
    print('\n== MONO (first 20) ==')
    for ch in CHARSET[:20]:
        print(repr(ch), fmt_strokes(mo[ch])[:110])

    sm, m_sm = build_stroke_font(os.path.join(dejavu, 'DejaVuSans.ttf'), mono=False)
    print('\n== SMOOTH (first 20) ==')
    for ch in CHARSET[:20]:
        adv, strokes = sm[ch]
        print(repr(ch), adv, fmt_strokes(strokes)[:90])

    # ascii previews for the chars most likely to go wrong
    print('\n== MONO previews ==')
    for ch in 'AMOamgRGWsQNsB8?.ßü':
        dump_strokes_ascii(mo[ch], label='MONO ' + repr(ch))
    print('\n== SMOOTH previews ==')
    for ch in 'AMOamgRGWsQNsBeg?.ßü':
        adv, strokes = sm[ch]
        dump_strokes_ascii(strokes, label='SMOOTH ' + repr(ch))

    m_px = {'cap': 5.0, 'xheight': 3.0, 'desc': 2.0, 'height': 7.0,
            'baseline': 5.0}
    print('\nmetrics PIXEL %r  MONO %r  SMOOTH %r' % (m_px, m_mo, m_sm))
    with open('/tmp/font_pixel.py', 'w') as f:
        f.write('FONT_META_PIXEL = %r\n' % (m_px,))
        f.write('FONT_PIXEL = {\n')
        for ch in CHARSET:
            if ch != ' ':
                f.write('    %r: %r,\n' % (ch, px[ch]))
        f.write('}\n')
    with open('/tmp/font_mono.py', 'w') as f:
        f.write('FONT_META_MONO = %r\n' % (m_mo,))
        f.write('FONT_MONO = {\n')
        for ch in CHARSET:
            f.write('    %r: %r,\n' % (ch, fmt_strokes(mo[ch])))
        f.write('}\n')
    with open('/tmp/font_smooth.py', 'w') as f:
        f.write('FONT_META_SMOOTH = %r\n' % (m_sm,))
        f.write('FONT_SMOOTH = {\n')
        for ch in CHARSET:
            if ch != ' ':
                adv, strokes = sm[ch]
                f.write('    %r: (%r, %r),\n' % (ch, round(adv, 1), fmt_strokes(strokes)))
        f.write("    ' ': (3.0, ''),\n")
        f.write('}\n')
    # ---- R82: small-text fonts from Google-Fonts sources (tools/fonts_src/) ----
    src_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'fonts_src')
    r82 = [
        ('COND', 'Oswald[wght].ttf', None),
        ('NARROW', 'RobotoCondensed[wght].ttf', None),
        ('CAPS', 'BebasNeue-Regular.ttf', 'caps'),
    ]
    for name, fname, mode in r82:
        path = os.path.join(src_dir, fname)
        if not os.path.isfile(path):
            print('!! %s missing (%s) - skipped' % (fname, path))
            continue
        g, m = build_stroke_font(path, mono=False)
        if mode == 'caps':
            # Bebas is a caps font: clone lowercase from the capitals instead
            # of storing its small-caps duplicates (half the data)
            for lo, up in zip('abcdefghijklmnopqrstuvwxyz', 'ABCDEFGHIJKLMNOPQRSTUVWXYZ'):
                g[lo] = (round(g[up][0] * 0.92, 1), g[up][1])
            g['ä'] = (round(g['Ä'][0] * 0.92, 1), g['Ä'][1])
            g['ö'] = (round(g['Ö'][0] * 0.92, 1), g['Ö'][1])
            g['ü'] = (round(g['Ü'][0] * 0.92, 1), g['Ü'][1])
        print('== %s == metrics %r' % (name, m))
        for ch in 'AMOamgÄ':
            dump_strokes_ascii(g[ch][1], width=30, height=12, label='%s %r' % (name, ch))
        with open('/tmp/font_%s.py' % name.lower(), 'w') as f:
            f.write('FONT_META_%s = %r\n' % (name, m))
            f.write('FONT_%s = {\n' % name)
            for ch in CHARSET:
                if ch != ' ':
                    adv, strokes = g[ch]
                    f.write('    %r: (%r, %r),\n' % (ch, round(adv, 1), fmt_strokes(strokes)))
            f.write("    ' ': (%.1f, ''),\n}\n" % (2.6 if mode == 'caps' else 3.0))

    # ---- R116: new fonts (script / handwriting / DIN plate / arcade pixel).
    #      Empty glyphs (a char the TTF does not really draw) fall back to
    #      the SMOOTH glyph so the charset is ALWAYS complete.
    r116 = [
        ('SCRIPT', 'DancingScript[wght].ttf', False),
        ('HAND', 'Caveat[wght].ttf', False),
        ('PLATE', 'D-DIN.ttf', False),
        ('PIXEL', 'PressStart2P-Regular.ttf', False),
    ]
    for name, fname, _unused in r116:
        path = os.path.join(src_dir, fname)
        if not os.path.isfile(path):
            print('!! %s missing (%s) - skipped' % (fname, path))
            continue
        g, m = build_stroke_font(path, mono=False)
        fixed = 0
        for ch in CHARSET:
            if ch == ' ':
                continue
            adv, strokes = g[ch]
            if not strokes:
                g[ch] = sm[ch]          # SMOOTH fallback - charset stays complete
                fixed += 1
        if name == 'PIXEL':
            # the old bitmap FONT_PIXEL/FONT_META_PIXEL blocks in
            # r2_postproc.py are REPLACED by this stroke data (same names)
            pass
        print('== %s == metrics %r (SMOOTH-fallback glyphs: %d)' % (name, m, fixed))
        for ch in 'AMOamgÄ':
            dump_strokes_ascii(g[ch][1], width=30, height=12, label='%s %r' % (name, ch))
        with open('/tmp/font_%s.py' % name.lower(), 'w') as f:
            f.write('FONT_META_%s = %r\n' % (name, m))
            f.write('FONT_%s = {\n' % name)
            for ch in CHARSET:
                if ch != ' ':
                    adv, strokes = g[ch]
                    f.write('    %r: (%r, %r),\n' % (ch, round(adv, 1), fmt_strokes(strokes)))
            f.write("    ' ': (3.0, ''),\n}\n")

    print('\nwritten: /tmp/font_pixel.py /tmp/font_mono.py /tmp/font_smooth.py'
          ' /tmp/font_cond.py /tmp/font_narrow.py /tmp/font_caps.py'
          ' /tmp/font_script.py /tmp/font_hand.py /tmp/font_plate.py')


if __name__ == '__main__':
    main()
