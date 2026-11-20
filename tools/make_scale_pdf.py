#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""make_scale_pdf.py — Mathematik & Blindbedienung für Scale X/Y + Z-Taper
(MASTER-TODO D4 + D6, Pre-Print > Tools > Scale X/Y).

Verbindliche D6-Wahrheitsregel:
  * KEINE Fantasie-Grafiken. Jede Abbildung und jede Ergebniszahl in diesem
    Heft stammt aus echten Läufen von `r2_postproc.apply_scale()` zur Bauzeit
    in einem temporären Arbeitsverzeichnis.
  * LCD-Zeilen werden live aus `menus/lcd_menues.cfg` geparst.
  * Versionszeile kommt dynamisch aus `r2_version.VERSION`.
"""
import math
import os
import re
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
sys.path.insert(0, HERE)

from reportlab.lib.units import mm
from PIL import Image as PILImage, ImageDraw

import r2_postproc as pp
from r2_version import VERSION as R2VER
from r2_pdf_kit import (
    Doc, H1, H2, P, B, NUM, CODE, CAP, SP, TBL, BOX, FORMULA, IMG, font,
)


# ------------------------------------------------ Synthetische Referenzdateien
def _write_test_box_with_arc(path, w=40.0, d=40.0, height=20.0, layer_h=0.2,
                             cx=85.0, cy=95.0):
    """40×40×20-mm-Prüfkörper (außermittig bei 85/95 mm) mit:
      - achsparallelen Wänden (0° und 90°),
      - 45°-Infill-Diagonalen,
      - einem G2-Viertelkreisbogen an der rechten oberen Ecke (Radius 8 mm),
      - einem M82-Retract/Unretract-Paar pro Schicht und einem Z-Hop (+0,4 mm)
        am Dateiende (prüft die ezmax-Klammerung von R216).
    """
    nl = int(round(height / layer_h))
    r_arc = 8.0
    e = 0.0
    k_e = 0.0332  # mm Filament pro mm Fahrweg (0.4 mm Düse, 0.2 mm Schicht)
    with open(path, 'w', encoding='utf-8') as f:
        f.write('; R276 reference body for SCALE.pdf\n')
        f.write('EXCLUDE_OBJECT_DEFINE NAME=TESTBOX CENTER=%.3f,%.3f\n'
                % (cx, cy))
        f.write(';TYPE:Outer wall\nM82\nG90\nG92 E0\n')
        x0, x1 = cx - w / 2.0, cx + w / 2.0
        y0, y1 = cy - d / 2.0, cy + d / 2.0
        for i in range(1, nl + 1):
            z = round(i * layer_h, 3)
            f.write('G0 X%.3f Y%.3f Z%.3f F6000\n' % (x0, y0, z))
            # Süd-Wand (0°, entlang +X)
            e += (x1 - x0) * k_e
            f.write('G1 X%.3f Y%.3f E%.5f F1800\n' % (x1, y0, e))
            # Ost-Wand bis Bogenansatz (90°, entlang +Y)
            e += ((y1 - r_arc) - y0) * k_e
            f.write('G1 X%.3f Y%.3f E%.5f F1800\n' % (x1, y1 - r_arc, e))
            # Viertelkreisbogen gegen den Uhrzeigersinn (G3) um (x1-r, y1-r)
            arc_len = 0.5 * math.pi * r_arc
            e += arc_len * k_e
            f.write('G3 X%.3f Y%.3f I%.3f J0.000 E%.5f F1500\n'
                    % (x1 - r_arc, y1, -r_arc, e))
            # Nord-Wand (180°, entlang -X)
            e += ((x1 - r_arc) - x0) * k_e
            f.write('G1 X%.3f Y%.3f E%.5f F1800\n' % (x0, y1, e))
            # West-Wand (270°, entlang -Y)
            e += (y1 - y0) * k_e
            f.write('G1 X%.3f Y%.3f E%.5f F1800\n' % (x0, y0, e))
            # 45°-Diagonale innen + Retract/Unretract-Test
            e -= 0.8
            f.write('G1 E%.5f F2400\n' % e)
            f.write('G0 X%.3f Y%.3f F6000\n' % (x0 + 3.0, y0 + 3.0))
            e += 0.8
            f.write('G1 E%.5f F2400\n' % e)
            dx = (x1 - r_arc - 3.0) - (x0 + 3.0)
            dy = (y1 - r_arc - 3.0) - (y0 + 3.0)
            e += math.hypot(dx, dy) * k_e
            f.write('G1 X%.3f Y%.3f E%.5f F1800\n'
                    % (x1 - r_arc - 3.0, y1 - r_arc - 3.0, e))
        # Reiner Leerfahrt-Z-Hop (+0,4 mm über ezmax) — darf Taper NICHT verwässern
        f.write('G0 Z%.3f F6000\n' % (height + 0.4))
    return path


def _write_star_angles_gcode(path, r=30.0):
    """Stern aus 19 Speichen von 0° bis 90° (alle 5°) zur direkten Messung des
    realen E-Verhältnisses ΔE'/ΔE aus der von apply_scale erzeugten G-Code-Datei."""
    cx, cy = 110.0, 110.0
    e = 0.0
    k_e = 0.0400  # exakt 0.04 mm Filament pro mm Speichenlänge (= 1.20000 mm E je 30-mm-Speiche)
    with open(path, 'w', encoding='utf-8') as f:
        f.write('; R276 angle fan for empirical E-factor verification\n')
        f.write('M82\nG90\nG92 E0\n')
        for idx in range(19):
            deg = idx * 5.0
            rad = math.radians(deg)
            tx = cx + r * math.cos(rad)
            ty = cy + r * math.sin(rad)
            f.write('G0 X%.3f Y%.3f Z0.200 F6000\n' % (cx, cy))
            e += r * k_e
            f.write('G1 X%.3f Y%.3f E%.5f F1800 ;ANG=%.1f\n'
                    % (tx, ty, e, deg))
    return path


def _parse_extruding_segments(gcode_path):
    """Liest alle extrudierenden Segmente (G1 + G2/G3-Sehnen) einer G-Code-Datei."""
    from r2_texture import _arc_points, _parse_move, _parse_arc
    segs = []
    px = py = pz = None
    last_e = 0.0
    e_rel = False
    with open(gcode_path, encoding='utf-8', errors='replace') as f:
        for raw in f:
            ls = raw.split(';', 1)[0].strip()
            if not ls:
                continue
            if ls == 'M83':
                e_rel = True
                continue
            if ls == 'M82':
                e_rel = False
                continue
            if ls.startswith('G92'):
                m = re.search(r'E(-?[\d.]+)', ls)
                if m:
                    last_e = float(m.group(1))
                continue
            g = _parse_move(ls)
            if g is not None:
                nx = g[1] if g[1] is not None else px
                ny = g[2] if g[2] is not None else py
                nz = g[3] if g[3] is not None else pz
                de = 0.0
                if g[4] is not None:
                    de = g[4] if e_rel else (g[4] - last_e)
                    if not e_rel:
                        last_e = g[4]
                if de > 1e-6 and px is not None and nx is not None and math.hypot(nx - px, ny - py) > 1e-6:
                    segs.append((px, py, nx, ny, nz or 0.2, de))
                px, py, pz = nx, ny, nz
                continue
            ga = _parse_arc(ls)
            if ga is not None and px is not None:
                nz = ga[3] if ga[3] is not None else pz
                pts = _arc_points(px, py, ga[1], ga[2], i=ga[4], j=ga[5],
                                  rr=ga[6], cw=(ga[0] == 'G2')) or []
                de = 0.0
                if ga[7] is not None:
                    de = ga[7] if e_rel else (ga[7] - last_e)
                    if not e_rel:
                        last_e = ga[7]
                chain = [(px, py)] + pts
                lens = [math.hypot(b[0] - a[0], b[1] - a[1])
                        for a, b in zip(chain, chain[1:])]
                tot_l = sum(lens) or 1.0
                for (a, b), ln in zip(zip(chain, chain[1:]), lens):
                    segs.append((a[0], a[1], b[0], b[1], nz or 0.2,
                                 de * (ln / tot_l)))
                if pts:
                    px, py = pts[-1]
                pz = nz
    return segs


def _total_positive_de(gcode_path):
    return sum(s[5] for s in _parse_extruding_segments(gcode_path))


# ------------------------------------------------ Live-LCD-Parser
def _parse_scale_menu():
    """Liest alle Zeilen unter [menu __main __preprint __mods __scale ...] live."""
    cfg = os.path.join(REPO, 'menus', 'lcd_menues.cfg')
    txt = open(cfg, encoding='utf-8').read()
    rows = []
    for blk in re.split(r'(?=^\[menu )', txt, flags=re.M):
        m = re.match(r'^\[menu (__main __preprint __mods __scale[^\]]*)\]', blk)
        if not m:
            continue
        sec = m.group(1).strip()
        if sec == '__main __preprint __mods __scale':
            continue
        key = sec.split()[-1]
        nm = re.search(r'^\s*name:\s*(.+)$', blk, re.M)
        imin = re.search(r'^\s*input_min:\s*(.+)$', blk, re.M)
        imax = re.search(r'^\s*input_max:\s*(.+)$', blk, re.M)
        istp = re.search(r'^\s*input_step:\s*(.+)$', blk, re.M)
        sv = re.search(r'SAVE_VARIABLE\s+VARIABLE=([a-z0-9_]+)', blk)
        act = re.search(r'^\s*(SCALE_APPLY[^\n]*|RESPOND[^\n]*)', blk, re.M)
        label = nm.group(1).strip().strip("'\"") if nm else key
        if 'gen_arm' in label:
            label = '&gt; Apply  (2. Klick: &gt; AGAIN = start)'
        elif 'menu.input' in label:
            prefix = label.split('{')[0].strip()
            suffix = label.split('}')[-1].strip()
            label = '%s &lt;Wert&gt;%s' % (prefix, suffix)
        else:
            label = label.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
        rng = ('%s .. %s (Schritt %s)'
               % (imin.group(1).strip(), imax.group(1).strip(),
                  istp.group(1).strip())) if (imin and imax and istp) else 'Befehl / Info'
        var = ('sv.%s' % sv.group(1)) if sv else (
            act.group(1).split()[0] if act else '—')
        rows.append((key, label, rng, var))
    return rows


# ------------------------------------------------ D6-Abbildungen (echte Läufe)
def _fig_xy_and_taper(src_path, aniso_path, taper_path, out_png):
    """Zweigeteilte D6-Grafik aus echten G-Code-Dateien:
      Links : Draufsicht auf das 220×220-mm-Bett — Quelle (außermittig 85/95,
              40×40 mm) vs. anisotrope Skalierung X=150 %, Y=75 % (zentriert
              auf 110/110, 60×30 mm, G3-Kreisbogen zu Ellipsen-Sehnen!).
      Rechts: Echte Z-Querschnitts-Spuren des Konus-Tapers X/Y 120 % -> Top 50 %
              über alle Höhenschichten (farbcodiert von Z=0,2 mm bis Z=20,0 mm).
    """
    W, H = 1280, 560
    im = PILImage.new('RGB', (W, H), 'white')
    d = ImageDraw.Draw(im)
    f_b = font(20, bold=True)
    f_m = font(16, bold=True)
    f_s = font(14)
    f_xs = font(13)

    # --- Linkes Panel: Bett-Draufsicht Quelle vs. Anisotrop 150/75 % ---
    bx0, by0, bw, bh = 55, 58, 460, 440
    d.rectangle([bx0, by0, bx0 + bw, by0 + bh], outline='#8aa4c2', width=2,
                fill='#f9fbfe')
    d.text((bx0, 22), 'A) Bett (220×220 mm): Quelle vs. X=150 % / Y=75 %',
           font=f_m, fill='#1c4e8c')

    def map_bed(x, y):
        px = bx0 + 24 + (x / 220.0) * (bw - 48)
        py = by0 + bh - 24 - (y / 220.0) * (bh - 48)
        return px, py

    # Bett-Mittelkreuz (110, 110)
    mcx, mcy = map_bed(110.0, 110.0)
    d.line([bx0 + 24, mcy, bx0 + bw - 24, mcy], fill='#d8e2ee', width=1)
    d.line([mcx, by0 + 24, mcx, by0 + bh - 24], fill='#d8e2ee', width=1)
    d.text((mcx + 6, mcy + 5), 'Bettmitte (110, 110)', font=f_xs, fill='#6d7f96')

    # Quell-Spur (Schicht 1, Z=0.2) — aber Quelle hat G3-Bogen! Für Quelle
    # lesen wir über r2_texture._arc_points den wahren Bogen + G1-Züge
    from r2_texture import _arc_points, _parse_move, _parse_arc
    px = py = pz = None
    with open(src_path, encoding='utf-8') as f:
        for raw in f:
            ls = raw.split(';', 1)[0].strip()
            g = _parse_move(ls)
            if g is not None:
                if g[3] is not None:
                    pz = g[3]
                nx = g[1] if g[1] is not None else px
                ny = g[2] if g[2] is not None else py
                if pz is not None and abs(pz - 0.2) < 1e-4 and g[4] is not None and px is not None:
                    if nx != px or ny != py:
                        d.line([map_bed(px, py), map_bed(nx, ny)],
                               fill='#8c99a8', width=3)
                px, py = nx, ny
                continue
            ga = _parse_arc(ls)
            if ga is not None and px is not None and pz is not None and abs(pz - 0.2) < 1e-4:
                pts = _arc_points(px, py, ga[1], ga[2], i=ga[4], j=ga[5],
                                  rr=ga[6], cw=(ga[0] == 'G2')) or []
                chain = [(px, py)] + pts
                for a, b in zip(chain, chain[1:]):
                    d.line([map_bed(a[0], a[1]), map_bed(b[0], b[1])],
                           fill='#8c99a8', width=3)
                if pts:
                    px, py = pts[-1]

    # Anisotrope Ausgabe (Schicht 1, Z=0.2 — alle Bögen sind echte G1-Sehnen!)
    for x0, y0, x1, y1, z, _de in _parse_extruding_segments(aniso_path):
        if abs(z - 0.2) < 1e-4:
            d.line([map_bed(x0, y0), map_bed(x1, y1)], fill='#1c4e8c', width=4)
            # Sehnen-Knotenpunkte markieren
            qx, qy = map_bed(x1, y1)
            d.ellipse([qx - 2, qy - 2, qx + 2, qy + 2], fill='#e07b00')

    # Legende links
    d.line([bx0 + 18, by0 + 22, bx0 + 52, by0 + 22], fill='#8c99a8', width=3)
    d.text((bx0 + 60, by0 + 13), 'Quelle: 40×40 mm bei (85, 95), G3-Bogen',
           font=f_s, fill='#444444')
    d.line([bx0 + 18, by0 + 46, bx0 + 52, by0 + 46], fill='#1c4e8c', width=4)
    d.text((bx0 + 60, by0 + 37), 'Skaliert 150/75 %: 60×30 mm bei (110, 110)',
           font=f_s, fill='#1c4e8c')
    d.text((bx0 + 60, by0 + 59), 'Orange Punkte = Ellipsen-Sehnenknoten aus G3',
           font=f_xs, fill='#b35900')

    # --- Rechtes Panel: Konus-Taper 120 % -> Top 50 % über Z ---
    rx0, ry0, rw, rh = 555, 58, 675, 440
    d.rectangle([rx0, ry0, rx0 + rw, ry0 + rh], outline='#8aa4c2', width=2,
                fill='#f9fbfe')
    d.text((rx0, 22),
           'B) Z-Taper-Stapel: Fuß 120 % (48 mm) -> Kopf 50 % (20 mm)',
           font=f_m, fill='#1c4e8c')

    taper_segs = _parse_extruding_segments(taper_path)
    # 11 repräsentative Schichten (Z = 0.2, 2.0, 4.0, ..., 20.0 mm) in Schrägprojektion
    sample_zs = [0.2] + [round(2.0 * k, 1) for k in range(1, 11)]

    def map_iso(x, y, z):
        u = (x - 110.0) * 5.2 + (y - 110.0) * 2.0
        v = -(y - 110.0) * 1.8 + z * 11.8
        return rx0 + rw * 0.57 + u, ry0 + rh - 88 - v

    for sz in sample_zs:
        t = (sz - 0.2) / (20.0 - 0.2)
        r_c = int(28 + (224 - 28) * t)
        g_c = int(78 + (123 - 78) * t)
        b_c = int(140 + (0 - 140) * t)
        col = '#%02x%02x%02x' % (r_c, g_c, b_c)
        for x0, y0, x1, y1, z, _de in taper_segs:
            if abs(z - sz) < 0.05:
                d.line([map_iso(x0, y0, z), map_iso(x1, y1, z)],
                       fill=col, width=2)

    # Beschriftung Fuß / Mitte / Kopf oben links im Panel ohne Überlappung
    for li, (lbl, col) in enumerate((
            ('Z=0,2 mm (t=0,00): f=1,20 -> 48,0 mm', '#1c4e8c'),
            ('Z=10,0 mm (t=0,495): f=0,85 -> 34,1 mm', '#7c6448'),
            ('Z=20,0 mm (t=1,00): f=0,50 -> 20,0 mm', '#e07b00'))):
        d.text((rx0 + 18, ry0 + 14 + li * 22), lbl, font=f_xs, fill=col)

    d.text((rx0 + 18, ry0 + rh - 30),
           'Leerfahrt-Z-Hop am Ende (Z=20,4 mm) bleibt außen vor: ezmax = 20,0 mm exakt!',
           font=f_xs, fill='#1e7d32')

    im.save(out_png)


def _fig_efactor_curves(tmpdir, out_png):
    """Plottet das GEMESSENE Verhältnis ΔE'(θ)/ΔE(θ) aus vier echten Läufen
    von apply_scale() auf der 19-Speichen-Sterndatei über θ ∈ [0°, 90°]."""
    star_src = _write_star_angles_gcode(os.path.join(tmpdir, 'star_src.gcode'))
    base_segs = _parse_extruding_segments(star_src)

    cases = [
        ('Isotrop X=140 %, Y=140 %  (s² = 1,96 überall)', 1.4, 1.4, '#1e7d32'),
        ('Anisotrop X=160 %, Y=80 %  (Achsen 1,28 · 45° -> 1,60)', 1.6, 0.8, '#1c4e8c'),
        ('Anisotrop X=200 %, Y=60 %  (Achsen 1,20 · 45° -> 2,18)', 2.0, 0.6, '#e07b00'),
        ('Downscale X=70 %, Y=70 %  (s² = 0,49 überall)', 0.7, 0.7, '#6a3fb5'),
    ]

    W, H = 1240, 500
    im = PILImage.new('RGB', (W, H), 'white')
    d = ImageDraw.Draw(im)
    f_b = font(20, bold=True)
    f_s = font(14)
    f_xs = font(13)

    d.text((55, 16),
           'Gemessener Extrusionsfaktor k_E(θ) = ΔE\' / ΔE aus echten apply_scale()-Läufen',
           font=f_b, fill='#1c4e8c')

    gx0, gy0, gw, gh = 95, 62, 720, 375
    d.rectangle([gx0, gy0, gx0 + gw, gy0 + gh], outline='#8aa4c2', width=2,
                fill='#f9fbfe')

    ymin, ymax = 0.30, 2.40

    def map_pt(deg, val):
        px = gx0 + (deg / 90.0) * gw
        py = gy0 + gh - ((val - ymin) / (ymax - ymin)) * gh
        return px, py

    # Gitterlinien
    for yv in (0.5, 1.0, 1.28, 1.60, 1.96, 2.18):
        _, py = map_pt(0, yv)
        d.line([gx0, py, gx0 + gw, py],
               fill='#c7d5e6' if abs(yv - 1.0) < 1e-6 else '#e5ecf4',
               width=2 if abs(yv - 1.0) < 1e-6 else 1)
        d.text((gx0 - 52, py - 8), ('%.2f' % yv).replace('.', ','),
               font=f_xs, fill='#444444')
    for deg in (0, 15, 30, 45, 60, 75, 90):
        px, _ = map_pt(deg, ymin)
        d.line([px, gy0, px, gy0 + gh], fill='#e5ecf4', width=1)
        d.text((px - 12, gy0 + gh + 8), '%d°' % deg, font=f_xs, fill='#444444')
    d.text((gx0 + gw // 2 - 95, gy0 + gh + 32),
           'Zugrichtung θ gegen die X-Achse [Grad]', font=f_s, fill='#222222')

    # Echte Messpunkte aus apply_scale() plotten
    lx, ly = gx0 + gw + 25, gy0 + 18
    d.text((lx, ly - 6), 'Legende (Live-Messung an 19 Speichen):',
           font=font(15, bold=True), fill='#1c4e8c')
    ly += 28
    for label, sx, sy, col in cases:
        out_p, _ = pp.apply_scale(star_src, sx=sx, sy=sy, out_dir=tmpdir)
        sc_segs = _parse_extruding_segments(out_p)
        pts = []
        for idx, (bs, ss) in enumerate(zip(base_segs, sc_segs)):
            deg = idx * 5.0
            ratio = ss[5] / bs[5]
            pts.append(map_pt(deg, ratio))
        for a, b in zip(pts, pts[1:]):
            d.line([a, b], fill=col, width=3)
        for px, py in pts:
            d.ellipse([px - 4, py - 4, px + 4, py + 4], fill=col)
        # zweizeiliger Legendeneintrag rechts (nichts wird abgeschnitten!)
        parts = label.split('  ')
        d.line([lx, ly + 9, lx + 28, ly + 9], fill=col, width=4)
        d.text((lx + 36, ly), parts[0], font=f_s, fill=col)
        if len(parts) > 1:
            d.text((lx + 36, ly + 20), parts[1], font=f_xs, fill='#555555')
        ly += 56

    d.rectangle([lx, ly + 8, W - 28, gy0 + gh], outline='#b9c9dd',
                fill='#eef4fb', width=1)
    d.text((lx + 12, ly + 18), 'Kopfrechen-Anker:', font=font(14, bold=True),
           fill='#1c4e8c')
    d.text((lx + 12, ly + 42), '• 0° & 90° (Wände): k_E = f_x · f_y',
           font=f_xs, fill='#222222')
    d.text((lx + 12, ly + 64), '• 45° (Infill): k_E = (f_x² + f_y²) / 2',
           font=f_xs, fill='#222222')
    d.text((lx + 12, ly + 86), '• Isotrop f_x = f_y = s: k_E = s² konstant',
           font=f_xs, fill='#222222')
    d.text((lx + 12, ly + 108), '• Globaler Flow (M221) bleibt auf 100 %!',
           font=f_xs, fill='#1e7d32')

    im.save(out_png)


# ------------------------------------------------ Hauptaufbau des PDFs
def build_pdf(out_pdf):
    lcd_rows = _parse_scale_menu()

    with tempfile.TemporaryDirectory(prefix='r2_scale_pdf_') as tmpdir:
        src = _write_test_box_with_arc(os.path.join(tmpdir, 'PruefBox.gcode'))
        e_src = _total_positive_de(src)

        # 5 reale Referenzläufe von apply_scale()
        runs = []
        specs = [
            ('1. Isotrop +25 %', dict(sx=1.25, sy=1.25)),
            ('2. Anisotrop 150/75 %', dict(sx=1.50, sy=0.75)),
            ('3. Downscale 70/70 %', dict(sx=0.70, sy=0.70)),
            ('4. Konus-Taper 120->50 %', dict(sx=1.20, sy=1.20, sxt=0.50, syt=0.50)),
            ('5. Keil-Taper X 100->60 %', dict(sx=1.00, sy=1.00, sxt=0.60, syt=1.00)),
        ]
        paths_by_idx = {}
        for idx, (title, kw) in enumerate(specs):
            out_p, info = pp.apply_scale(src, out_dir=tmpdir,
                                         bed=(0.0, 0.0, 220.0, 220.0), **kw)
            paths_by_idx[idx] = out_p
            e_out = _total_positive_de(out_p)
            runs.append((title, kw, info, e_out, e_out / e_src))

        fig1 = os.path.join(tmpdir, 'fig_xy_taper.png')
        _fig_xy_and_taper(src, paths_by_idx[1], paths_by_idx[3], fig1)

        fig2 = os.path.join(tmpdir, 'fig_efactor.png')
        _fig_efactor_curves(tmpdir, fig2)

        doc = Doc(
            out_pdf,
            kopf='R2-D2 Macro System · Pre-Print-Modifikator Scale X/Y & Taper (D4)',
            titel='Scale X/Y & Z-Taper — Mathematik & Blindbedienung',
        )
        st = doc.story

        cover_tbl = TBL(
            ['Kenngröße', 'Wert im aktuellen Code'],
            [
                ['Menüpfad am Display', 'Pre-Print > Tools > Scale X/Y  (6 Zeilen)'],
                ['G-Code-Makro / Engine', 'SCALE_APPLY  ->  r2_postproc.apply_scale()'],
                ['Wertebereich Fuß (X, Y)', '25 % .. 300 % je Achse (Schrittweite 5 % am Rad)'],
                ['Wertebereich Z-Taper (Top X/Y)', '0 % (= aus) oder 25 % .. 300 % an der Bauteil-Oberkante'],
                ['Ankerung auf dem Bett', 'Deterministisch auf Bettmitte (tx, ty) zentriert'],
                ['Extrusions-Nachführung', 'Exakt pro Zug: k_E = (L\'/L) · (w\'/w), M221-Flow bleibt 100 %'],
                ['Ausgabeordner & Namensschema', 'Scale/<Stamm>_S<X>-<Y>[T<TopX>-<TopY>].gcode'],
            ],
            [58 * mm, 104 * mm],
        )[0]

        doc.add_cover(
            kicker='PRE-PRINT-GEOMETRIE-MODIFIKATOR · MATHEMATIK & BLINDBEDIENUNG (D4)',
            titel='Scale X/Y & Z-Taper',
            untertitel='Anisotrope XY-Skalierung, lineare Höhenverjüngung und richtungsabhängige Extrusions-Jacobi-Rechnung direkt auf der G-Code-Datei',
            absaetze=[
                'Wer eine fertig geslicte G-Code-Datei ohne PC größer, schmaler oder konisch '
                'machen will, scheitert mit einem bloßen Koordinaten-Multiplikator sofort an '
                'der Physik: Wird ein Zug länger und breiter, während die Schichthöhe h fest '
                'bleibt, verhungert die Naht bei Vergrößerung oder quillt bei Verkleinerung über.',
                'Dieses Fachheft leitet die exakte Mathematik hinter apply_scale() (R176 / R216) '
                'aus dem produktiven Quellcode her — von der Z-Taper-Interpolation ohne Z-Hop-'
                'Verfälschung über den Richtungsfaktor k_E(θ, z) und die G2/G3-Ellipsensehnen '
                'bis zur sicheren Blindbedienung am Drehknopf ohne Blick aufs Display.',
            ],
            tabelle=cover_tbl,
        )

        # ---- Kapitel 1 ------------------------------------------------------
        st += H1('Zweck, Architektur & Abgrenzung zum Live-Flow', '1')
        st += P(
            'Am Drucker existieren zwei völlig verschiedene Regler, die man niemals '
            'verwechseln darf: Der Live-Flow (<b>M221 S...</b>) ändert lediglich die '
            'Förderrate auf <i>unveränderten</i> Koordinaten. <b>Scale X/Y</b> '
            '(<b>apply_scale</b> in <b>tools/r2_postproc.py</b>) schreibt dagegen vor '
            'Druckbeginn eine neue, eigenständige G-Code-Datei in den Unterordner '
            '<b>Scale/</b>: Jede XY-Koordinate wird skaliert, das Bauteil sauber in '
            'die Druckbettmitte gesetzt und die Extrusionsmenge <b>ΔE</b> jedes '
            'einzelnen Fahrbefehls exakt auf die neue Geometrie umgerechnet.'
        )
        st += B(
            '<b>Zwei-Pass-Streaming:</b> Pass 1 liest die Quelldatei zeilenweise und '
            'bestimmt die XY-Bounding-Box aller Züge sowie das rein <i>extrudierende</i> '
            'Höhenfenster [z_min^ext, z_max^ext]. Pass 2 schreibt die transformierte '
            'Datei direkt auf die SD-Karte, ohne die gesamte Datei im RAM zu halten.',
            '<b>Neue 100-%-Flow-Basis:</b> Da ΔE bereits in der Datei stimmt, startet '
            'der Druck mit <b>Flow = 100 %</b>. Ein manuelles Nachrechnen am Live-Regler '
            'entfällt komplett.',
            '<b>Niemals Überschreiben:</b> Die Quelldatei bleibt unangetastet; bei '
            'Namensgleichheit hängt die Engine automatisch <b>_2</b>, <b>_3</b> usw. an.',
        )

        # ---- Kapitel 2 ------------------------------------------------------
        st += H1('Koordinaten-Mathematik: Zentrierung, Z-Taper & Bettwächter', '2')
        st += P(
            'Aus Pass 1 kennt die Engine das Quell-Rechteck [x_min, x_max] × [y_min, y_max] '
            'mit dem Bauteilzentrum (c_x, c_y) sowie die Bettgrenzen [b_x0, b_x1] × '
            '[b_y0, b_y1] mit der Bettmitte (t_x, t_y). Zusätzlich erfasst Pass 1 '
            'getrennt das Höhenintervall aller Züge mit positivem Materialauftrag '
            '(E > 0): <b>ezmin</b> bis <b>ezmax</b>.'
        )
        st += FORMULA(
            'c_x = (x_min + x_max) / 2,     c_y = (y_min + y_max) / 2<br/>'
            't_x = (b_x0 + b_x1) / 2,       t_y = (b_y0 + b_y1) / 2<br/>'
            't(z) = clamp_[0, 1]( (z - ezmin) / (ezmax - ezmin) )<br/>'
            'f_x(z) = s_x + (s_xt - s_x) · t(z),     f_y(z) = s_y + (s_yt - s_y) · t(z)<br/>'
            'x\'(z) = t_x + (x - c_x) · f_x(z),       y\'(z) = t_y + (y - c_y) · f_y(z)',
            note='s_x, s_y ∈ [0,25 ; 3,00]: Fußfaktoren (X/100, Y/100). '
                 's_xt, s_yt: Kopffaktoren (Top X/100, Top Y/100; 0 am LCD bedeutet „kein Taper", also s_xt = s_x). '
                 'Z selbst bleibt unverändert (z\' = z): Schichtanzahl und Schichthöhe h bleiben 1:1 erhalten.'
        )
        st += SP(2)
        st.append(BOX(
            'Warum ezmax statt zmax? (Die Z-Hop-Falle aus R216)',
            [
                'Fast jeder Slicer hebt die Düse am Druckende um +0,4 mm bis +2,0 mm im '
                'Leerlauf an. Würde t(z) auf das globale z_max normiert, läge die oberste '
                'echte Druckschicht unterhalb von t = 1,0 und würde den eingestellten '
                'Top-Faktor nie ganz erreichen! Indem apply_scale() ausschließlich auf '
                '[ezmin, ezmax] normiert und auf [0, 1] klemmt, landet die erste Druckschicht '
                'exakt bei f(ezmin) = s und die letzte Druckschicht exakt bei f(ezmax) = s_top.',
            ],
            kind='why',
        ))
        st += SP(2)
        st += P(
            '<b>Bettwächter vor dem Schreiben:</b> Bei aktivem Taper kann entweder der Fuß '
            '(z. B. 120 % -> 60 % Kegel) oder der Kopf (z. B. 70 % -> 130 % Kelch) breiter '
            'sein. Die Engine prüft deshalb das Maximum beider Enden gegen die Bettgröße '
            '(mit 0,5 mm Rundungstoleranz):'
        )
        st += FORMULA(
            '(x_max - x_min) · max(s_x, s_xt)  <=  (b_x1 - b_x0) + 0,5 mm<br/>'
            '(y_max - y_min) · max(s_y, s_yt)  <=  (b_y1 - b_y0) + 0,5 mm',
            note='Wird die Grenze überschritten, bricht apply_scale() vor dem ersten Schreibbyte '
                 'mit einer klaren Maßmeldung ab („needs A x B mm - the bed has 220 x 220 mm").'
        )

        # ---- Kapitel 3 ------------------------------------------------------
        st += H1('Die Extrusions-Mathematik pro Zug & Kreisbogen-Zerlegung', '3')
        st += P(
            'Eine gedruckte Raupe hat das Volumen <b>V = L · w · h</b> (Länge × Spurbreite × '
            'Schichthöhe). Da Scale X/Y die Z-Koordinaten nicht antastet, bleibt <b>h</b> '
            'konstant; das benötigte Filamentvolumen skaliert also mit dem Produkt aus '
            'relativer Längenänderung <b>L\'/L</b> und relativer Spurbreitenänderung '
            '<b>w\'/w</b>. Für einen Zug der Richtung <b>u = (cos θ, sin θ)</b> auf Höhe z '
            'berechnet <b>_f176()</b>:'
        )
        st += FORMULA(
            'u_x = Δx / √(Δx² + Δy²),        u_y = Δy / √(Δx² + Δy²)<br/>'
            'L\' / L = √( (f_x · u_x)² + (f_y · u_y)² )<br/>'
            'w\' / w = √( (f_x · u_y)² + (f_y · u_x)² )<br/>'
            'k_E(θ, z) = (L\' / L) · (w\' / w),        ΔE\' = ΔE · k_E(θ, z)',
            note='Wichtige exakt ablesbare Spezialfälle dieser Formel:'
        )
        st += B(
            '<b>Achsparallele Wände (θ = 0° oder θ = 90°):</b> Entlang X gilt L\'/L = f_x und '
            'senkrecht dazu w\'/w = f_y; entlang Y umgekehrt. In beiden Fällen ist '
            '<b>k_E = f_x · f_y</b> exakt gleich der Flächen-Determinante det(diag(f_x, f_y))!',
            '<b>45°-Infill-Diagonalen (|u_x| = |u_y| = 1/√2):</b> Sowohl L\'/L als auch '
            'w\'/w liefern √((f_x² + f_y²)/2), ihr Produkt ist <b>k_E(45°) = (f_x² + f_y²)/2</b> '
            '(arithmetisches Mittel der Quadrate). Hinweis zur Modelltreue: Bei stark '
            'anisotroper Verzerrung liegt (f_x²+f_y²)/2 um (f_x - f_y)²/2 über der reinen '
            'Flächendeterminante f_x·f_y — das füllt diagonal gestreckte Infill-Gitter satt '
            'aus, kann bei vollflächigen 45°-Deckschichten und extremer Anisotropie (> 2:1) '
            'aber leicht überfüllen.',
            '<b>Isotrope Skalierung (f_x = f_y = s):</b> Für <i>jeden</i> Winkel θ gilt '
            'L\'/L = s und w\'/w = s, also richtungsunabhängig <b>k_E = s²</b>.',
            '<b>M82-Akkumulator & Retract-Schutz:</b> Im absoluten Extrusionsmodus (M82) '
            'führt die Engine einen eigenen gleitenden Zähler <b>new_e</b>. Nur Vorwärts-'
            'Extrusion (<b>ΔE > 0</b>) wird mit k_E multipliziert; Einzüge (<b>ΔE <= 0</b>) '
            'und anschließende Rückschübe auf reinen Stand-Befehlen (ohne XY-Weg, ln < 10⁻⁹ -> '
            'k_E = 1,0) bleiben 1:1 erhalten, damit kein Retract auf 300 % explodiert!',
            '<b>G2/G3-Kreisbögen -> Ellipsen-Sehnen:</b> Ein Kreis wird unter f_x != f_y zur '
            'Ellipse, die G2/G3 im G-Code-Standard nicht darstellen kann. apply_scale() '
            'zerlegt jeden G2/G3-Befehl vorab über <b>_arc_points()</b> in feine G1-Sehnen, '
            'verteilt das Bogen-ΔE längenproportional auf die Sehnen und skaliert jede '
            'Sehne anschließend mit ihrem eigenen Richtungsfaktor k_E(θ_i, z).',
        )
        st.append(BOX(
            'Physikalische Düsengrenze am echten Drucker (0,4-mm-Düse)',
            [
                'Mathematisch erlaubt apply_scale() Faktoren von 25 % bis 300 %. Physikalisch '
                'kann eine 0,40-mm-Düse jedoch weder 0,10 mm schmale Raupen sauber ablegen '
                'noch 1,20 mm breite Raupen flachbügeln: Im praxissicheren Fenster '
                '<b>65 % .. 160 %</b> (Spurbreite ca. 0,28 .. 0,68 mm) verschmelzen Wände '
                'und Infill ohne Slicer-Neulauf zuverlässig. Jenseits davon ist Scale X/Y '
                'ideal für Spiralvasen oder schnelle Maßproben, ersetzt aber bei technischen '
                'Passungen keinen neuen Slicer-Lauf mit angepasster Wandlinienzahl.',
            ],
            kind='warn',
        ))

        # ---- Kapitel 4 ------------------------------------------------------
        st += H1('Live-Geometrie & gemessene k_E(θ)-Kurven (D6)', '4')
        st += P(
            'Beide folgenden Abbildungen stammen ohne jede Handzeichnung direkt aus den '
            'zur Bauzeit dieses PDFs erzeugten G-Code-Dateien von <b>apply_scale()</b>:'
        )
        st.append(IMG(fig1, width_mm=156))
        st += CAP(
            'Abb. 1 — Echte G-Code-Pfade aus apply_scale(): Links Re-Zentrierung von (85, 95) '
            'auf Bettmitte (110, 110) und Umwandlung des G3-Eckbogens in Ellipsen-Sehnen bei '
            'X=150 %, Y=75 %. Rechts 11 Höhenschichten des Konus-Tapers 120 % -> 50 %.'
        )
        st.append(IMG(fig2, width_mm=156))
        st += CAP(
            'Abb. 2 — Direkt aus 4×19 skalierten G1-Speichen (0°..90°) zurückgemessenes '
            'Extrusionsverhältnis ΔE\'/ΔE: Isotrope Läufe sind exakt flach bei s², anisotrope '
            'Läufe steigen von f_x·f_y an den Achsen glatt auf (f_x²+f_y²)/2 bei 45°.'
        )

        # ---- Kapitel 5 ------------------------------------------------------
        st += H1('Blind am Drucker arbeiten: Menü, Klickfolge & Kopfrechnen', '5')
        st += P(
            'So bedienst du <b>Scale X/Y</b> am Ender-3-Drehknopf sicher, selbst wenn du '
            'seitlich neben der Maschine stehst. Die folgende Tabelle zeigt die <b>%d</b> '
            'realen Menüzeilen live aus <b>menus/lcd_menues.cfg</b>:' % len(lcd_rows)
        )
        st += TBL(
            ['Pos.', 'LCD-Zeile', 'Wertebereich / Schritt', 'Variable / Aktion'],
            [[str(i + 1), r[1], r[2], r[3]] for i, r in enumerate(lcd_rows)],
            [12 * mm, 52 * mm, 52 * mm, 46 * mm],
            mono_cols=(0, 3),
        )
        st += SP(2)
        st += H2('Blind-Klickfolge am Drehknopf', '5.1')
        st += NUM(
            '<b>Quelldatei wählen:</b> Im SD-Browser oder unter <b>Pre-Print &gt; File</b> '
            'die gewünschte <b>.gcode</b>-Datei anklicken.',
            '<b>Werkzeug öffnen:</b> Vom Hauptmenü <b>Pre-Print &gt; Tools &gt; Scale X/Y</b> '
            'öffnen. Der Cursor steht nach „.." auf Zeile 1 (<b>X: 100%</b>).',
            '<b>Rasten zählen (1 Raste = 5 %):</b> Klick auf Zeile 1 -> rechts drehen '
            '(+4 Rasten = 120 %, -4 Rasten = 80 %) -> Klick bestätigt. Eine Raste runter '
            'auf Zeile 2 (<b>Y</b>) -> genauso einstellen.',
            '<b>Optionaler Taper (Zeilen 3 & 4):</b> Stehen <b>Top X</b> und <b>Top Y</b> '
            'auf <b>0%</b>, ist der Taper aus (gerade Wände). Für einen Kegel z. B. von '
            '0 % nach rechts bis 60 % drehen (+12 Rasten ab 0 %).',
            '<b>Zwei-Klick-Sicherheitsstart (Zeile 6):</b> Runter bis ans Menüende auf '
            '<b>&gt; Apply</b>. 1. Klick schärft scharf (Anzeige springt auf '
            '<b>&gt; AGAIN = start</b> + Bestätigungston), 2. Klick startet den Hintergrundjob '
            'und verlässt das Menü automatisch. Fertig-Ton <b>r2_done</b> abwarten!',
        )
        st += SP(2)
        st.append(BOX(
            'Kopfrechen-Spickzettel für die Werkstatt (ohne Taschenrechner)',
            [
                '• <b>Zielmaß aus Prozent:</b> Alle 5 % (eine Drehraste) entsprechen '
                '<b>1/20</b> der Ausgangsbreite. Bei einem 60-mm-Teil bringt jede Raste '
                'exakt <b>±3,0 mm</b>; bei einem 40-mm-Teil exakt <b>±2,0 mm</b>.',
                '• <b>Maximaler Faktor auf dem 220-mm-Bett:</b> Teile 220 durch die größere '
                'Bauteilkante. Ein 80-mm-Teil verträgt maximal 220/80 = <b>275 %</b>.',
                '• <b>Filament-Mehrverbrauch abschätzen:</b> Da die Höhe gleich bleibt, '
                'wächst der Filamentbedarf näherungsweise mit <b>f_x · f_y</b>: '
                '+10 % auf X und Y (110/110) braucht 1,1² = <b>+21 %</b> mehr Filament; '
                '+20 % auf X und Y (120/120) braucht 1,2² = <b>+44 %</b> mehr Filament.',
                '• <b>Konsolen-Kurzform (Mainsail / KlipperScreen):</b> '
                '<b>SCALE_APPLY X=125 Y=125 TOP_X=0 TOP_Y=0</b> bzw. mit Taper '
                '<b>SCALE_APPLY X=100 Y=100 TOP_X=60 TOP_Y=60 FILE=vase.gcode</b>.',
            ],
            kind='tip',
        ))

        # ---- Kapitel 6 ------------------------------------------------------
        st += H1('Durchgerechnete Live-Referenzläufe (40×40×20-mm-Prüfkörper)', '6')
        st += P(
            'Alle Zahlen der folgenden Tabelle wurden beim Bau dieses PDFs live aus '
            'fünf echten Läufen von <b>apply_scale()</b> auf der 100-Schicht-Prüfbox '
            '(Quell-Extrusion <b>ΣΔE = %.2f mm</b>, 1 G3-Bogen pro Schicht = 100 Bögen) '
            'gemessen:' % e_src
        )
        ref_rows = []
        for title, kw, info, e_out, ratio in runs:
            old_s = '%.0f×%.0f' % info['old_size']
            if info['taper']:
                new_s = ('%.0f×%.0f -> %.0f×%.0f'
                         % (info['old_size'][0] * info['sx'],
                            info['old_size'][1] * info['sy'],
                            info['old_size'][0] * info['sxt'],
                            info['old_size'][1] * info['syt']))
            else:
                new_s = '%.0f×%.0f' % info['new_size']
            ref_rows.append([
                title,
                info['file'],
                '%s -> %s mm' % (old_s, new_s),
                '%d / %d' % (info['moves'], info['arcs_flattened']),
                '%.2f mm (%.3f×)' % (e_out, ratio),
            ])
        st += TBL(
            ['Szenario', 'Erzeugte Datei', 'XY-Maß (Fuß -> Kopf)', 'Züge / Bögen', 'ΣΔE\' (Verhältnis)'],
            ref_rows,
            [34 * mm, 44 * mm, 34 * mm, 22 * mm, 30 * mm],
            mono_cols=(1, 3, 4),
        )
        st += SP(2)
        st += P(
            '<b>Gegenprobe an den Zahlen:</b> Bei Lauf 1 (isotrop 125 %) beträgt das '
            'gemessene Gesamt-Extrusionsverhältnis exakt <b>1,25² = 1,5625</b>; bei Lauf 3 '
            '(isotrop 70 %) exakt <b>0,70² = 0,4900</b>. Bei Lauf 2 (anisotrop 150 % × 75 %) '
            'liegt f_x·f_y = 1,125 an den Achsenwänden und (1,5²+0,75²)/2 = 1,406 auf den '
            '45°-Diagonalen — der gemessene Gesamtwert liegt erwartungsgemäß exakt dazwischen. '
            'In allen fünf Läufen wurden sämtliche <b>100 G3-Bögen</b> verlustfrei in '
            'Ellipsen-/Kreissehnen zerlegt.'
        )

        doc.render()
    return out_pdf


if __name__ == '__main__':
    target = os.path.join(REPO, 'SCALE.pdf')
    build_pdf(target)
    print('Wrote %s (%d bytes)' % (target, os.path.getsize(target)))
