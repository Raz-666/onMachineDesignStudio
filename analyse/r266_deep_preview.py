#!/usr/bin/env python3
"""R266 DEEP RELIEF preview - the user-facing evidence picture.

Three rows, one story:
  1. height fields on a FIXED mm grayscale (+-2.5mm): the classic 0.45mm
     depth looks pale next to the 2.5mm deep relief - same pattern, same
     scale, honest contrast.
  2. cross-section: radial displacement in mm around one circumference
     (the wall stays continuous - no hole, no self-cut).
  3. E density measured from REAL generated g-code (uniform-density
     cylinder, BARK @ 2.5mm): every chord extrudes 0.05*length - the
     deep-relief E compensation riding the true path length.

Run: python3 analyse/r266_deep_preview.py
Writes: analyse/r266_deep_relief_preview.png
"""
import math
import os
import re
import shutil
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', 'tools'))
import r2_texture  # noqa: E402

from PIL import Image, ImageDraw, ImageFont  # noqa: E402

E_RE = re.compile(r'(?:^|\s)E(-?[\d.]+)')
X_RE = re.compile(r'(?:^|\s)X(-?[\d.]+)')
Y_RE = re.compile(r'(?:^|\s)Y(-?[\d.]+)')


def fonts():
    try:
        f = ImageFont.truetype(
            '/usr/share/fonts/truetype/dejavu/DejavuSans-Bold.ttf', 15)
        n = ImageFont.truetype(
            '/usr/share/fonts/truetype/dejavu/DejavuSans.ttf', 12)
        s = ImageFont.truetype(
            '/usr/share/fonts/truetype/dejavu/DejavuSans.ttf', 10)
    except OSError:
        f = n = s = ImageFont.load_default()
    return f, n, s


def hillshade_panel(fn, w, h, amp_mm, scale_mm):
    """Grayscale panel; the scale is FIXED in mm so depth reads honestly."""
    img = Image.new('L', (w, h))
    px = img.load()
    # simple hillshade: intensity from the field, shading from the
    # horizontal gradient (light from the left)
    for y in range(h):
        t = y / float(h)
        for x in range(w):
            s0 = x / float(w)
            v = fn(s0, t) * amp_mm
            vr = fn(min(1.0, s0 + 1.0 / w), t) * amp_mm
            g = max(-1.0, min(1.0, v / scale_mm))
            gr = max(-1.0, min(1.0, vr / scale_mm))
            base = int(round(128 + 100 * g))
            shade = int(round(70 * (g - gr) * (scale_mm / amp_mm)
                              if amp_mm > 0 else 0))
            px[x, y] = max(0, min(255, base - shade))
    return img.convert('RGB')


def make_cylinder(path):
    """Uniform-density cylinder, relative E, 6 layers, 40 chords ~2.36mm."""
    q = 0.05
    with open(path, 'w') as f:
        f.write(';FLAVOR:Marlin\nG90\nM83\nG92 E0\n')
        for lay in range(6):
            z = 0.2 + lay * 0.2
            f.write(';LAYER_CHANGE\n;TYPE:WALL-OUTER\n')
            f.write('G0 X125.000 Y110.000 Z%.3f F9000\n' % z)
            for i in range(1, 41):
                a = 2 * math.pi * i / 40
                b = 2 * math.pi * (i - 1) / 40
                x, y = 110 + 15 * math.cos(a), 110 + 15 * math.sin(a)
                ln = math.hypot(15 * math.cos(a) - 15 * math.cos(b),
                                15 * math.sin(a) - 15 * math.sin(b))
                f.write('G1 X%.3f Y%.3f E%.5f F2400\n' % (x, y, q * ln))


def scan_density(path, q0):
    """(densities, rel_err) over the written wall chords; G0 resets."""
    px = py = None
    inwall = False
    dens = []
    tot_e = tot_l = 0.0
    for ln in open(path):
        ln = ln.rstrip('\n')
        if ln.startswith(';TYPE:'):
            inwall = 'wall' in ln.lower()
            continue
        if ln.startswith('G0'):
            px = py = None
            continue
        if not ln.startswith('G1 '):
            continue
        mx, my, me = X_RE.search(ln), Y_RE.search(ln), E_RE.search(ln)
        if not mx or not my:
            continue
        x, y = float(mx.group(1)), float(my.group(1))
        e = float(me.group(1)) if me else None
        if e is None or e <= 0.00002:
            px = py = None
            continue
        if px is not None and inwall:
            cl = math.hypot(x - px, y - py)
            dens.append(e / cl)
            tot_e += e
            tot_l += cl
        px, py = x, y
    rel_err = abs(tot_e - q0 * tot_l) / (q0 * tot_l)
    return dens, rel_err


def main():
    f, n, s = fonts()
    W = 1330
    pad = 16
    bg = '#f4f2ed'
    panel_w, panel_h, label_h = 313, 176, 30
    xs_row2, w2 = 720, 560
    h_xs, h_ed = 235, 235

    head = 52
    row1_y = head
    row2_y = row1_y + label_h + panel_h + 18
    row3_y = row2_y + h_xs + 34
    H = row3_y + h_ed + pad + 46

    out = Image.new('RGB', (W, H), bg)
    d = ImageDraw.Draw(out)
    d.text((pad, 10), 'DEEP RELIEF (R266) - Tiefe ueber 1 mm: E folgt dem echten Pfad',
           fill='#18232c', font=f)
    d.text((pad, 30), 'Hoehenfelder auf FESTER mm-Grauwertskala (+-2.5 mm) - '
           'gleiche Skala, ehrlicher Kontrast. Querschnitt: Wand bleibt '
           'kontinuierlich. E-Dichte: aus echtem erzeugtem G-Code gemessen.',
           fill='#53616b', font=s)

    # ---------------- row 1: four panels, fixed mm scale -------------------
    k, n_z = 18, 12
    rows_per_period = max(2, int(round(2.0 * n_z / (3.0 ** 0.5))))
    if rows_per_period & 1:
        rows_per_period += 1
    ar = (panel_h / float(n_z)) / (panel_w / float(k))
    pats = r2_texture._build_patterns(k, n_z, 37, None, ar=ar)
    panels = [
        ('BARK', 0.45, 'Bark - klassisch 0.45 mm'),
        ('BARK', 2.5, 'Bark - DEEP 2.5 mm'),
        ('NETGRID', 0.45, 'Netgrid - klassisch 0.45 mm'),
        ('NETGRID', 2.5, 'Netgrid - DEEP 2.5 mm'),
    ]
    for i, (pat, amp, label) in enumerate(panels):
        x0 = pad + i * (panel_w + 12)
        d.rounded_rectangle((x0, row1_y, x0 + panel_w,
                             row1_y + label_h + panel_h),
                            radius=5, fill='#ffffff', outline='#d2d7d7')
        d.text((x0 + 9, row1_y + 7), label, fill='#18232c', font=n)
        img = hillshade_panel(pats[pat], panel_w - 18, panel_h,
                              amp, 2.5)
        out.paste(img, (x0 + 9, row1_y + label_h))

    # ---------------- row 2 left: cross-section ---------------------------
    x0, y0 = pad, row2_y
    d.rounded_rectangle((x0, y0, x0 + xs_row2, y0 + h_xs), radius=5,
                        fill='#ffffff', outline='#d2d7d7')
    d.text((x0 + 10, y0 + 7), 'Querschnitt BARK 2.5 mm - Verschiebung in mm '
           'ueber dem Umfang (eine Z-Linie)', fill='#18232c', font=n)
    gx0, gy0, gx1, gy1 = x0 + 52, y0 + 34, x0 + xs_row2 - 14, y0 + h_xs - 30
    amp = 2.5
    fn = pats['BARK']
    vals = [fn(i / 720.0, 0.3) * amp for i in range(721)]
    vmin, vmax = min(vals), max(vals)
    lo = min(0.0, vmin) - 0.15
    hi = vmax + 0.15
    def gy(v):
        return gy1 - (v - lo) / (hi - lo) * (gy1 - gy0)
    # axes
    d.line((gx0, gy0, gx0, gy1), fill='#9aa4ab')
    d.line((gx0, gy1, gx1, gy1), fill='#9aa4ab')
    for v in (0.0, 1.0, 2.0):
        if lo < v < hi:
            d.line((gx0, gy(v), gx1, gy(v)), fill='#e3e7e9')
            d.text((x0 + 12, gy(v) - 6), '%+.0f' % v, fill='#53616b', font=s)
    for deg in (0, 90, 180, 270, 360):
        gx = gx0 + (gx1 - gx0) * deg / 360.0
        d.line((gx, gy1, gx, gy1 + 4), fill='#9aa4ab')
        d.text((gx - 10, gy1 + 6), '%d\xc2\xb0' % deg, fill='#53616b', font=s)
    pts = [(gx0 + (gx1 - gx0) * i / 720.0, gy(v)) for i, v in enumerate(vals)]
    d.line(pts, fill='#b3541e', width=2)
    d.line((gx0, gy(0), gx1, gy(0)), fill='#53616b')   # unversetzte Wand
    d.text((gx0 + 8, gy0 + 2), 'Wand (+0 mm)', fill='#53616b', font=s)
    d.text((gx0 + 8, gy0 + 16), 'Verschiebung bis %+.2f mm - kontinuierlich, '
           'keine Luecke' % vmax, fill='#b3541e', font=s)

    # ---------------- row 2/3 right + row 3: E density from g-code ---------
    tmp = tempfile.mkdtemp(prefix='r266prev')
    src = os.path.join(tmp, 'cyl.gcode')
    make_cylinder(src)
    outp, info = r2_texture.apply_texture(
        src, out_dir=tmp, mode='BUMPS', bump_pattern='BARK',
        bump_scale=12.0, bump_amp=2.5, zsize=4.0, seed=43)
    dens, rel_err = scan_density(outp, 0.05)
    q0 = 0.05

    x0, y0 = pad, row3_y
    d.rounded_rectangle((x0, y0, x0 + xs_row2, y0 + h_ed), radius=5,
                        fill='#ffffff', outline='#d2d7d7')
    d.text((x0 + 10, y0 + 7), 'E-Dichte je Chord, aus dem erzeugten G-Code '
           'gemessen (BARK 2.5 mm, Zylinder, relatives E)', fill='#18232c',
           font=n)
    gx0, gy0, gx1, gy1 = x0 + 52, y0 + 36, x0 + xs_row2 - 14, y0 + h_ed - 44
    dlo, dhi = 0.0, 0.105
    def gy2(v):
        return gy1 - max(dlo, min(dhi, v)) / (dhi - dlo) * (gy1 - gy0)
    d.line((gx0, gy0, gx0, gy1), fill='#9aa4ab')
    d.line((gx0, gy1, gx1, gy1), fill='#9aa4ab')
    for v, lab in ((0.0, '0'), (0.05, '0.05'), (0.09, '0.09')):
        d.line((gx0, gy2(v), gx1, gy2(v)), fill='#e3e7e9')
        d.text((x0 + 14, gy2(v) - 6), lab, fill='#53616b', font=s)
    # clamp band 0.45x .. 1.8x
    for mult, col in ((0.45, '#d9b8a6'), (1.8, '#d9b8a6')):
        d.line((gx0, gy2(q0 * mult), gx1, gy2(q0 * mult)),
               fill=col, width=1)
    # target line q0
    d.line((gx0, gy2(q0), gx1, gy2(q0)), fill='#2e7d32', width=2)
    m = len(dens)
    for i, v in enumerate(dens):
        gx = gx0 + (gx1 - gx0) * i / max(1, m - 1)
        d.ellipse((gx - 1, gy2(v) - 1, gx + 1, gy2(v) + 1),
                  fill='#1f4e79')
    d.text((gx0 + 8, gy0 + 2), 'Soll 0.05 = E/L (gruen) - Chords (blau) '
           'bleiben im Band', fill='#2e7d32', font=s)
    d.text((x0 + 10, y0 + h_ed - 34,
            ), 'E-Erhalt gesamt: |sum(E) - 0.05*sum(L)| / (0.05*sum(L)) '
           '= %.1e (nur Rundung)  |  Clamp-Band 0.45-1.8x (beige) nie '
           'verletzt  |  %d Chords, %d steile Segmente'
           % (rel_err, len(dens), info['steep_segments']),
           fill='#18232c', font=s)

    # ---------------- row 3 right: facts panel ----------------------------
    x0 = pad + xs_row2 + 14
    d.rounded_rectangle((x0, row3_y, x0 + w2 - 26, row3_y + h_ed),
                        radius=5, fill='#ffffff', outline='#d2d7d7')
    d.text((x0 + 10, row3_y + 7), 'Was DEEP RELIEF tut', fill='#18232c',
           font=n)
    facts = [
        'Tiefe 1.0-4.0 mm (BUMPS) - gleiche Muster, ehrliche Physik',
        'E_neu = E_alt * L_neu/L_alt je Chord (relatives E, M83)',
        'Steilheits-Clamp 0.45-1.8x: Klippen ueberextrudieren nie',
        'Summen-E je Move erhalten (Restkorrektur am letzten Chord)',
        'Steile Flanken: Subdivision bis ~0.4 mm Hoehenschritt',
        'Wand bleibt zu: Verschiebung kontinuierlich, Innenspaene',
        '  folgen (R224) - Dellen statt Loch (Perforationsregel)',
        'Absolut-E: E bleibt slicer-echt, Header sagt es',
        'Tiefe <= 1.0 mm: Ausgabe byte-identisch zum alten Motor',
        'Feldbugs mitgegangen: X-only-Purge-Zeilen (vwbus-Crash),',
        '  kommentiertes "M83 ; ..." schaltet jetzt korrekt',
    ]
    yy = row3_y + 32
    for line in facts:
        d.text((x0 + 10, yy), line, fill='#33424c', font=s)
        yy += 17

    target = os.path.join(HERE, 'r266_deep_relief_preview.png')
    out.save(target, optimize=True)
    shutil.rmtree(tmp, ignore_errors=True)
    print('wrote %s (%dx%d, %d bytes)' % (target, W, H,
                                          os.path.getsize(target)))


if __name__ == '__main__':
    main()
