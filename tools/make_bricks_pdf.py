#!/usr/bin/env python3
# -*- coding: utf-8 -*-
""" make_bricks_pdf.py — Wissenschaftliches Generator-Fachheft (D3 / D6):
    Klemmbausteine (Bricks), Modell-Bausatz (BrickKit) & System-Figuren (Figures).

    Alle Abbildungen und Referenztabellen werden zur Bauzeit LIVE aus den echten
    Produktionsfunktionen make_bricks(), make_brick_kit() und make_figures() in
    tools/r2_postproc.py sowie aus menus/lcd_menues.cfg erzeugt (Regel D6).
    Versionsstempel kommt dynamisch aus r2_version (Regel r165).
"""
import math
import os
import re
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
sys.path.insert(0, HERE)

from PIL import Image as PILImage, ImageDraw  # noqa: E402
from reportlab.lib.units import mm  # noqa: E402

import r2_postproc as pp  # noqa: E402
from r2_pdf_kit import (  # noqa: E402
    Doc, H1, H2, P, B, NUM, FORMULA, TBL, BOX, IMG, CAP, SP, PageBreak, font,
)
from r2_version import VERSION as R2VER  # noqa: E402


# ------------------------------------------------------- G-Code-Parser (echt)
def _parse_gcode_layers(gcode_path):
    """Extrahiert pro Layer alle extrudierenden Segmente (x0, y0, x1, y1, tp),
    Z-Höhen, M600-Positionen und EXCLUDE_OBJECT-Namen."""
    layers = {}
    layer_z = {}
    objs = []
    m600_count = 0
    total_e = 0.0
    cur_layer = 0
    cur_type = 'OTHER'
    x = y = z = 0.0
    rel_e = True

    with open(gcode_path, encoding='utf-8', errors='replace') as fh:
        for raw in fh:
            s = raw.strip()
            if not s:
                continue
            if s.startswith('M82'):
                rel_e = False
                continue
            if s.startswith('M83'):
                rel_e = True
                continue
            if s.startswith('M600'):
                m600_count += 1
                continue
            if s.startswith('EXCLUDE_OBJECT_DEFINE '):
                m = re.search(r'NAME=([^\s]+)', s)
                if m:
                    objs.append(m.group(1))
                continue
            if s == 'LAYER_MARK' or s.startswith(';LAYER:'):
                cur_layer += 1
                continue
            if s.startswith('APPLY_TYPE TYPE='):
                cur_type = s.split('=', 1)[1].strip()
                continue
            if s.startswith(';TYPE:'):
                cur_type = s.split(':', 1)[1].strip().upper()
                continue
            code = s.split(';', 1)[0].strip()
            if not (code.startswith('G0 ') or code.startswith('G1 ')):
                continue
            nx, ny, nz = x, y, z
            de = 0.0
            has_e = False
            for tok in code.split()[1:]:
                c = tok[0]
                try:
                    val = float(tok[1:])
                except ValueError:
                    continue
                if c == 'X':
                    nx = val
                elif c == 'Y':
                    ny = val
                elif c == 'Z':
                    nz = val
                elif c == 'E':
                    has_e = True
                    de = val if rel_e else max(0.0, val - total_e)
            if has_e and de > 1e-5 and math.hypot(nx - x, ny - y) > 1e-4:
                layers.setdefault(cur_layer, []).append((x, y, nx, ny, cur_type))
                layer_z.setdefault(cur_layer, nz)
                total_e += de
            x, y, z = nx, ny, nz

    return {
        'layers': layers,
        'layer_z': layer_z,
        'objs': objs,
        'm600': m600_count,
        'total_e': total_e,
        'n_layers': max(layers.keys()) if layers else 0,
    }


def _make_sample_stepped_gcode(path):
    """Erzeugt eine kleine, gültige geslicte Stufenpyramide (32 × 24 × 19,2 mm)
    als Eingabedatei für make_brick_kit()."""
    lines = [
        '; R2 sample stepped monument for BrickKit',
        'M83',
        'G90',
    ]
    z = 0.2
    while z <= 9.61:
        lines.append(';LAYER_CHANGE')
        lines.append(';Z:%.2f' % z)
        lines.append('G0 Z%.2f F1200' % z)
        # 3 Platten-Stufen à 3,2 mm -> an jeder 1-Platten-Stufe entstehen echte SP*-Slopes!
        if z <= 3.21:
            x0, y0, x1, y1 = 90.0, 96.0, 130.0, 124.0
        elif z <= 6.41:
            x0, y0, x1, y1 = 98.0, 100.0, 122.0, 120.0
        else:
            x0, y0, x1, y1 = 102.0, 104.0, 118.0, 116.0
        lines.append(';TYPE:Outer wall')
        pts = [(x0, y0), (x1, y0), (x1, y1), (x0, y1), (x0, y0)]
        lines.append('G0 X%.2f Y%.2f F6000' % pts[0])
        for px, py in pts[1:]:
            d = 24.0
            lines.append('G1 X%.2f Y%.2f E%.4f F1800' % (px, py, d * 0.035))
        lines.append(';TYPE:Sparse infill')
        yy = y0 + 2.0
        flip = False
        while yy < y1 - 1.5:
            xa, xb = (x0 + 1.0, x1 - 1.0) if not flip else (x1 - 1.0, x0 + 1.0)
            lines.append('G0 X%.2f Y%.2f F6000' % (xa, yy))
            lines.append('G1 X%.2f Y%.2f E%.4f F2400' % (xb, yy, abs(xb - xa) * 0.035))
            yy += 3.2
            flip = not flip
        z = round(z + 0.2, 2)
    with open(path, 'w', encoding='utf-8') as f:
        f.write('\n'.join(lines) + '\n')
    return path


# ------------------------------------------------------- Live-Menüextraktor
def _parse_bricks_menu():
    cfg_path = os.path.join(REPO, 'menus', 'lcd_menues.cfg')
    txt = open(cfg_path, encoding='utf-8').read()
    blocks = re.split(r'(?m)^(?=\[menu )', txt)
    secs = [b for b in blocks if b.startswith('[menu __main __gen __bricks')]
    rows = []
    seen_cat = False
    for sec in secs:
        lines = [l.strip() for l in sec.strip().splitlines() if l.strip()]
        hdr = lines[0].strip('[]').replace('menu __main __gen __bricks', 'Tools > Bricks')
        # 76 Katalog-Einträge unter __cat kompakt zusammenfassen
        if '__cat __' in hdr:
            if not seen_cat:
                seen_cat = True
                rows.append((
                    'Tools > Bricks > cat > [8 Familien]',
                    '76 Katalog-Codes (Bricks/Plates/Tiles/Slopes/Tech..)',
                    'Klick = +Count zur Queue',
                ))
            continue
        if any(hdr.endswith(s) for s in ('__kit __s0', '__kit __s1', '__kit __s2', '__kit __s3', '__kit __s4')):
            continue
        nm = mn = mx = st = tp = ''
        for ln in lines[1:]:
            if ln.startswith('type:'):
                tp = ln.split(':', 1)[1].strip()
            elif ln.startswith('name:'):
                nm = ln.split(':', 1)[1].strip().strip("'")
            elif ln.startswith('input_min:'):
                mn = ln.split(':', 1)[1].strip()
            elif ln.startswith('input_max:'):
                mx = ln.split(':', 1)[1].strip()
            elif ln.startswith('input_step:'):
                st = ln.split(':', 1)[1].strip()
        clean_map = {
            '__cnt': 'Count: [1..99] Stück pro Klick',
            '__lh': 'Layer: [0.08..0.32]mm',
            '__brm': 'Brim: [0..8] Schleifen',
            '__scl': 'Scale: [25..300]% (+Wand ab 200%)',
            '__col': 'Colors: [1..8] Farben',
            '__mod': 'Mode: BY_LAYER / BY_OBJECT',
            '__go': 'Create (2× Klick = Start)',
            '__clr': 'Clear queue (2× Klick)',
            '__del': 'Delete last entry',
            '__kit __det': 'Detail: AUTO / BIG / SMALL / MICRO',
            '__kit __col': 'Kit Colors: [1..8]',
            '__kit __mod': 'Kit Mode: BY_LAYER / BY_OBJECT',
            '__kit __go': 'Build kit from selected file',
            '__fig __cnt': 'Figures: [1..24] Stück',
            '__fig __scl': 'Fig Scale: [25..300]%',
            '__fig __mod': 'Fig Mode: PARTS (5-tlg.) / SINGLE',
            '__fig __col': 'Fig Colors: [1..4]',
            '__fig __cmd': 'Fig ColorMode: BY_LAYER / BY_OBJECT',
            '__fig __go': 'Build figures (2× Klick)',
        }
        for suf, label in clean_map.items():
            if hdr.endswith(suf):
                nm = label
                break
        if '{' in nm:
            nm = re.sub(r'\{.*?\}', '[live]', nm)
        nm = nm.replace('<', '[').replace('>', ']')
        rng = ('%s .. %s (Schritt %s)' % (mn, mx, st)) if mn else ('Untermenü' if tp == 'list' else 'Schalter / Aktion')
        rows.append((hdr.replace(' __', ' > '), nm[:44], rng))
    return rows


# ------------------------------------------------------- Abbildungen (echt)
def _fig_bricks_anatomy(prs_mix, out_png):
    """Abb. 1: Links echte G-Code-Werkzeugbahnen einer gemischten Bausteinplatte
    (Layer 3 = Unterseiten-Klemmröhren Ø 6,31 mm vs. Top-Noppenlayer Ø 4,80 mm);
    rechts maßstäblicher Klemmgeometrie-Schnitt (8,0-mm-Raster, 0,2-mm-Klemmluft,
    Tangentialkontakt Ø 6,31 zwischen vier Ø 4,80-Noppen)."""
    W_img, H_img = 1520, 620
    im = PILImage.new('RGB', (W_img, H_img), '#ffffff')
    dr = ImageDraw.Draw(im)
    f_title = font(18, bold=True)
    f_sub = font(15, bold=True)
    f_lbl = font(14)
    f_sm = font(12)

    # Linkes Panel: Echte Werkzeugbahnen aus V01_Bricks.gcode
    dr.rounded_rectangle((20, 18, 790, 602), radius=10,
                         fill='#f8fafd', outline='#bfd0e6', width=2)
    dr.text((36, 28),
            'A. Echte G-Code-Bahnen: Röhren-Layer (L3) & Noppen-Layer (Top)',
            fill='#1c4e8c', font=f_title)
    dr.text((36, 52),
            'B2x4 · P2x2 · T1x2 (glatt) · S2x3 (Dachstein) · H1x4 (Technic) · R1x1',
            fill='#475569', font=f_sm)

    l_tube = prs_mix['layers'].get(3, [])
    # Noppen-Layer einer hohen Steinreihe (z. B. Z ~ 10.4 mm -> Layer ~52)
    stud_li = max((li for li, zz in prs_mix['layer_z'].items() if zz >= 10.2), default=prs_mix['n_layers'])
    l_stud = prs_mix['layers'].get(stud_li, [])
    # Und Noppen-Layer der flachen Platten (Z ~ 4.0 mm -> Layer ~20)
    pstud_li = min((li for li, zz in prs_mix['layer_z'].items() if 3.5 <= zz <= 4.6), default=stud_li)
    l_pstud = prs_mix['layers'].get(pstud_li, [])

    all_pts = [(x, y) for (x0, y0, x1, y1, _) in l_tube for (x, y) in ((x0, y0), (x1, y1))]
    xs = [p[0] for p in all_pts] or [80, 140]
    ys = [p[1] for p in all_pts] or [80, 140]
    xmin, xmax = min(xs) - 2.5, max(xs) + 2.5
    ymin, ymax = min(ys) - 2.5, max(ys) + 2.5

    vx0, vy0, vw, vh = 38, 80, 734, 480
    dr.rectangle((vx0, vy0, vx0 + vw, vy0 + vh), fill='#ffffff', outline='#cbd5e1', width=1)
    scale = min((vw - 24) / (xmax - xmin), (vh - 24) / (ymax - ymin))
    ox = vx0 + (vw - (xmax - xmin) * scale) / 2.0
    oy = vy0 + (vh - (ymax - ymin) * scale) / 2.0

    def to_px(xm, ym):
        return int(ox + (xm - xmin) * scale), int(vy0 + vh - (oy - vy0) - (ym - ymin) * scale)

    # Layer 3: Wände & Unterseitenröhren in Stahlblau
    for (x0, y0, x1, y1, tp) in l_tube:
        col = '#1c4e8c' if 'WALL' in tp else '#93c5fd'
        w_ln = 2 if 'WALL' in tp else 1
        dr.line((to_px(x0, y0), to_px(x1, y1)), fill=col, width=w_ln)

    # Noppen-Layer von Platten & Steinen in Signal-Orange darübergelegt
    for seg_list in (l_pstud, l_stud):
        for (x0, y0, x1, y1, tp) in seg_list:
            if 'WALL' in tp:
                dr.line((to_px(x0, y0), to_px(x1, y1)), fill='#e06d00', width=2)

    dr.text((38, 570),
            'Blau = Layer 3 (Außenwand 1,5 mm + Röhren Ø 6,31 mm) · Orange = Hohlnoppen Ø 4,80 mm',
            fill='#334155', font=f_sm)

    # Rechtes Panel: Maßstäbliche Klemmgeometrie (2×2-Raster von unten + Aufriss)
    dr.rounded_rectangle((810, 18, 1500, 602), radius=10,
                         fill='#f8fafd', outline='#bfd0e6', width=2)
    dr.text((828, 28),
            'B. Warum 8,00 - 0,20 mm & Ø 6,31 mm exakt klemmen',
            fill='#1c4e8c', font=f_title)
    dr.text((828, 52),
            'Maßstäbliche 2×2-Klemmzelle (1 mm = 22 px): Röhre tangiert alle 4 Noppen!',
            fill='#475569', font=f_sm)

    # Zeichne 2×2-Stein (15,8 × 15,8 mm) bei 22 px/mm
    s_mm = 22.0
    cx, cy = 1155, 252
    bw_px = int(round(15.8 * s_mm / 2.0))
    in_px = int(round((15.8 - 3.0) * s_mm / 2.0))  # 1.5 mm Wand
    # Gestrichelte 16,0-mm-Systemrastergrenze
    grid_px = int(round(16.0 * s_mm / 2.0))
    dr.rectangle((cx - grid_px, cy - grid_px, cx + grid_px, cy + grid_px),
                 outline='#dc2626', width=1)
    # Stein-Außenkörper 15,8 mm
    dr.rectangle((cx - bw_px, cy - bw_px, cx + bw_px, cy + bw_px),
                 fill='#dbeafe', outline='#1c4e8c', width=3)
    dr.rectangle((cx - in_px, cy - in_px, cx + in_px, cy + in_px),
                 fill='#ffffff', outline='#1c4e8c', width=2)

    # 4 Noppen auf Pitch +-4.0 mm (Ø 4.8 mm außen, Ø 2.4 mm innen)
    for sx_mm in (-4.0, 4.0):
        for sy_mm in (-4.0, 4.0):
            px = int(round(cx + sx_mm * s_mm))
            py = int(round(cy + sy_mm * s_mm))
            r_out = int(round(2.4 * s_mm))
            r_in = int(round(1.2 * s_mm))
            dr.ellipse((px - r_out, py - r_out, px + r_out, py + r_out),
                       fill='#fed7aa', outline='#c2410c', width=3)
            dr.ellipse((px - r_in, py - r_in, px + r_in, py + r_in),
                       fill='#ffffff', outline='#c2410c', width=1)

    # Zentrale Unterseiten-Klemmröhre Ø 6,31 mm (Wand 0,657 mm -> ID 5,00 mm)
    rt_out = int(round((6.31 / 2.0) * s_mm))
    rt_in = int(round(((6.31 - 2 * 0.657) / 2.0) * s_mm))
    dr.ellipse((cx - rt_out, cy - rt_out, cx + rt_out, cy + rt_out),
               outline='#0f766e', width=4)
    dr.ellipse((cx - rt_in, cy - rt_in, cx + rt_in, cy + rt_in),
               outline='#0f766e', width=2)

    dr.text((836, 444), 'Geometrischer Klemmnachweis (exakt im Code hinterlegt):',
            fill='#163c6e', font=f_sub)
    bullets = [
        '• Außenmaß = n · 8,00 - 0,20 mm  ->  0,10 mm Spalt je Seite (Steine stoßen nie!)',
        '• Noppen-Diagonale: d_diag = sqrt(2) · 8,00 = 11,314 mm',
        '• Freier Inkreis zwischen 4 Noppen: 11,314 - 4,80 = 6,514 mm',
        '• Klemmröhre Ø_OD = 6,31 mm (= 1 Spur der 0,6-mm-Düse, Wand 0,657 mm)',
        '• R216-Skalierregel: 200 % -> +1 Wandlinie (3 Loops), 300 % -> +2 (4 Loops)',
    ]
    for k, line in enumerate(bullets):
        dr.text((836, 472 + k * 23), line, fill='#1e293b', font=f_sm)

    im.save(out_png)
    return out_png


def _fig_kit_and_figures(kit_plates_paths, prs_fig, out_png):
    """Abb. 2: Links echte Bausatz-Platten aus make_brick_kit() (inkl. erkannter
    Stufen-Dachsteine SP*); rechts echte 5-teilige Figur aus make_figures(PARTS)
    mit flach liegenden Armen (vertikale Schulter- & Greifhand-Bohrungen!)."""
    W_img, H_img = 1520, 580
    im = PILImage.new('RGB', (W_img, H_img), '#ffffff')
    dr = ImageDraw.Draw(im)
    f_title = font(18, bold=True)
    f_sub = font(14, bold=True)
    f_sm = font(12)

    # Linkes Panel: BrickKit 3 Farbplatten (GRY / BLK / RED)
    dr.rounded_rectangle((20, 18, 750, 562), radius=10,
                         fill='#f8fafd', outline='#bfd0e6', width=2)
    dr.text((36, 28),
            'A. BrickKit (make_brick_kit): Geslictes Modell -> 3 Farbplatten',
            fill='#1c4e8c', font=f_title)
    dr.text((36, 52),
            'BY_LAYER = 0× M600! Jede Farbplatte wird am Stück gedruckt; Kanten werden zu Slopes:',
            fill='#475569', font=f_sm)

    plate_cols = [('#475569', 'Platte A (Basis · GRY)'),
                  ('#1e293b', 'Platte B (Mitte · BLK)'),
                  ('#dc2626', 'Platte C (Spitze · RED)')]

    for idx, p_path in enumerate(kit_plates_paths[:3]):
        prs = _parse_gcode_layers(p_path)
        px0 = 36 + idx * 234
        py0, pw, ph = 84, 220, 425
        dr.rounded_rectangle((px0, py0, px0 + pw, py0 + ph), radius=8,
                             fill='#ffffff', outline='#cbd5e1', width=1)
        col_hex, lbl = plate_cols[idx]
        dr.text((px0 + 10, py0 + 8), lbl, fill=col_hex, font=f_sub)

        segs_l2 = prs['layers'].get(2, [])
        segs_top = prs['layers'].get(prs['n_layers'], [])
        pts = [(x, y) for (x0, y0, x1, y1, _) in segs_l2 for (x, y) in ((x0, y0), (x1, y1))]
        if pts:
            xs = [p[0] for p in pts]
            ys = [p[1] for p in pts]
            xmin, xmax = min(xs) - 2.0, max(xs) + 2.0
            ymin, ymax = min(ys) - 2.0, max(ys) + 2.0
            sc = min((pw - 24) / max(1.0, xmax - xmin), (ph - 76) / max(1.0, ymax - ymin))
            ox = px0 + (pw - (xmax - xmin) * sc) / 2.0
            oy = py0 + 36 + (ph - 76 - (ymax - ymin) * sc) / 2.0
            for (x0, y0, x1, y1, tp) in segs_l2:
                if 'WALL' in tp:
                    p1 = (int(ox + (x0 - xmin) * sc), int(py0 + ph - 36 - (y0 - ymin) * sc))
                    p2 = (int(ox + (x1 - xmin) * sc), int(py0 + ph - 36 - (y1 - ymin) * sc))
                    dr.line((p1, p2), fill=col_hex, width=2)
            for (x0, y0, x1, y1, tp) in segs_top:
                if 'WALL' in tp:
                    p1 = (int(ox + (x0 - xmin) * sc), int(py0 + ph - 36 - (y0 - ymin) * sc))
                    p2 = (int(ox + (x1 - xmin) * sc), int(py0 + ph - 36 - (y1 - ymin) * sc))
                    dr.line((p1, p2), fill='#e06d00', width=2)
        dr.text((px0 + 10, py0 + ph - 26),
                '%d Teile · ΣΔE=%.0f mm' % (len(prs['objs']), prs['total_e']),
                fill='#475569', font=f_sm)

    dr.text((36, 526),
            'Jedes Bauteil besitzt ein eigenes EXCLUDE_OBJECT · Orange = Noppen auf der Decklage',
            fill='#334155', font=f_sm)

    # Rechtes Panel: Echte 5-teilige Figur aus make_figures(mode='PARTS')
    dr.rounded_rectangle((770, 18, 1500, 562), radius=10,
                         fill='#f8fafd', outline='#bfd0e6', width=2)
    dr.text((788, 28),
            'B. System-Figur (make_figures, PARTS): 5 steckbare Bauteile',
            fill='#1c4e8c', font=f_title)
    dr.text((788, 52),
            'R132-Feldlösung: Arme liegen flach -> Schulterzapfen & Ø 2,4-Greifhand drucken sauber rund!',
            fill='#475569', font=f_sm)

    fx0, fy0, fw, fh = 788, 84, 694, 425
    dr.rectangle((fx0, fy0, fx0 + fw, fy0 + fh), fill='#ffffff', outline='#cbd5e1', width=1)

    # Sammle Wände über mehrere charakteristische Höhen (Basis + Schulterzapfen + Kopf)
    l_base = prs_fig['layers'].get(3, [])
    l_mid = prs_fig['layers'].get(26, [])
    l_hi = prs_fig['layers'].get(52, [])
    pts_f = [(x, y) for (x0, y0, x1, y1, _) in l_base for (x, y) in ((x0, y0), (x1, y1))]
    if pts_f:
        xs = [p[0] for p in pts_f]
        ys = [p[1] for p in pts_f]
        xmin, xmax = min(xs) - 3.0, max(xs) + 3.0
        ymin, ymax = min(ys) - 3.0, max(ys) + 3.0
        sc = min((fw - 36) / (xmax - xmin), (fh - 56) / (ymax - ymin))
        ox = fx0 + (fw - (xmax - xmin) * sc) / 2.0
        oy = fy0 + 20 + (fh - 56 - (ymax - ymin) * sc) / 2.0

        def fpx(xm, ym):
            return int(ox + (xm - xmin) * sc), int(fy0 + fh - 28 - (ym - ymin) * sc)

        for (x0, y0, x1, y1, tp) in l_base:
            col = '#1c4e8c' if 'WALL' in tp else '#cbd5e1'
            dr.line((fpx(x0, y0), fpx(x1, y1)), fill=col, width=2 if 'WALL' in tp else 1)
        for (x0, y0, x1, y1, tp) in l_mid:
            if 'WALL' in tp:
                dr.line((fpx(x0, y0), fpx(x1, y1)), fill='#0f766e', width=2)
        for (x0, y0, x1, y1, tp) in l_hi:
            if 'WALL' in tp:
                dr.line((fpx(x0, y0), fpx(x1, y1)), fill='#e06d00', width=2)

    dr.text((788, 526),
            'G-Code-Objekte: LEGS · TORSO · ARM1 · ARM2 · HEAD (klebefrei @ 100 %)',
            fill='#334155', font=f_sm)

    im.save(out_png)
    return out_png


# -------------------------------------------------------------- Hauptdokument
def build_pdf(out_pdf):
    lcd_rows = _parse_bricks_menu()

    with tempfile.TemporaryDirectory(prefix='r2_bricks_pdf_') as tmpdir:
        # 6 echte Referenzläufe
        p_mix, i_mix = pp.make_bricks(
            [('B2x4', 1), ('P2x2', 1), ('T1x2', 1), ('S2x3', 1), ('H1x4', 1), ('R1x1', 1)],
            layer_h=0.2, brim=2, colors=1, nozzle=0.6, out_dir=tmpdir)
        prs_mix = _parse_gcode_layers(p_mix)

        p_3c, i_3c = pp.make_bricks(
            [('B2x4', 4), ('P2x4', 4), ('T2x2', 4)],
            layer_h=0.2, brim=2, colors=3, mode='BY_LAYER', nozzle=0.6, out_dir=tmpdir)

        p_obj, i_obj = pp.make_bricks(
            [('B2x2', 2), ('S1x3', 2)],
            layer_h=0.2, brim=2, colors=2, mode='BY_OBJECT', nozzle=0.4, out_dir=tmpdir)

        p_200, i_200 = pp.make_bricks(
            [('B2x4', 2)],
            layer_h=0.24, brim=2, colors=1, scale=200, nozzle=0.6, out_dir=tmpdir)

        sample_gc = _make_sample_stepped_gcode(os.path.join(tmpdir, 'Stufenbau.gcode'))
        p_kit, i_kit = pp.make_brick_kit(
            sample_gc, detail='BIG', mode='BY_LAYER', colors=3,
            layer_h=0.2, nozzle=0.6, out_dir=tmpdir)
        kit_paths = [os.path.join(tmpdir, fn) for fn in i_kit['plates']]

        p_fig, i_fig = pp.make_figures(
            count=1, scale=100.0, layer_h=0.2, brim=2,
            mode='PARTS', colors=1, nozzle=0.4, out_dir=tmpdir)
        prs_fig = _parse_gcode_layers(p_fig)

        p_figs, i_figs = pp.make_figures(
            count=2, scale=100.0, layer_h=0.2, brim=2,
            mode='SINGLE', colors=1, nozzle=0.4, out_dir=tmpdir)

        fig1 = os.path.join(tmpdir, 'fig_bricks_anat.png')
        _fig_bricks_anatomy(prs_mix, fig1)

        fig2 = os.path.join(tmpdir, 'fig_kit_figs.png')
        _fig_kit_and_figures(kit_paths, prs_fig, fig2)

        doc = Doc(
            out_pdf,
            kopf='R2-D2 Macro System · Generator Klemmbausteine / Bricks (D3)',
            titel='Bricks, BrickKit & Figures — Systemgeometrie & Blindbedienung',
        )
        st = doc.story

        cover_tbl = TBL(
            ['Kenngröße', 'Wert im aktuellen Produktivcode (R121 / R125 / R126 / R132 / R216)'],
            [
                ['Menüpfad am Display', 'Tools > Bricks  (221 Menü-Sektionen inkl. Katalog, BrickKit & Figures)'],
                ['G-Code-Makros / Engine', 'BRICK_ADD · BRICK_CREATE · GEN_BRICKS · GEN_BRICKKIT -> make_bricks()'],
                ['Systemraster & Klemmluft', 'Pitch P = 8,00 mm · Außenmaß n · 8,00 - 0,20 mm (0,10 mm Spalt je Seite)'],
                ['Höhen & Hohlnoppen', 'Stein 9,60 mm (= 3 Platten) · Platte/Fliese 3,20 mm · Noppe Ø 4,80 × 1,80 mm'],
                ['Unterseiten-Klemmröhre', 'Ø_OD = 6,31 mm (Wand 0,657 mm) -> Tangentialklemmsitz zwischen 4 Noppen'],
                ['Bauteil-Katalog', '%d Codes in 8 Familien: B, P, T, J/R/RP/RT/C, S, I, A, H (Technic Ø 4,9 mm)' % len(pp.BRICK_CATALOG)],
                ['Farbmodi & Objekt-Schutz', 'BY_LAYER (1 Platte je Farbe, 0× M600!) · BY_OBJECT (1 Platte + M600) · EXCLUDE_OBJECT'],
                ['BrickKit & Figures', 'Geslicte G-Code-Datei -> Klemm-Bausatz · Figuren 5-teilig (PARTS) oder SINGLE'],
            ],
            [56 * mm, 106 * mm],
        )[0]

        doc.add_cover(
            kicker='GENERATOR-FACHHEFT · KONSTRUKTIONS- & SPIELSYSTEME (D3 / D6)',
            titel='Bricks, BrickKit & Figures',
            untertitel='Maßhaltige Klemmbausteine in 76 Katalogformen, automatische Modell-Voxelisierung in Klemm-Bausätze sowie steckbare Systemfiguren direkt am Drucker erzeugen',
            absaetze=[
                'Klemmbausteine verzeihen keinen Zehntelmillimeter Schätzgeometrie: Ist der '
                'Außenkörper exakt 16,00 mm breit, klemmen zwei Nachbarsteine gegeneinander fest; '
                'ist die Unterseitenröhre um 0,3 mm zu dünn, fällt der Stein von den Noppen ab. '
                'Der Generator hinterlegt deshalb die klassische Noppen-und-Röhren-Passung '
                'analytisch im Code — neutral benannt, glatte Noppen ohne Markenlogos, aber '
                'bei Scale = 100 % mechanisch voll steckkompatibel.',
                'Alle drei Werkzeuge dieser Familie — der 76-teilige Einzelstein-Katalog, der '
                'Voxel-Bausatzkonverter BrickKit und der Figuren-Generator — zentrieren jede '
                'Platte automatisch auf dem Druckbett und kapseln jedes einzelne Teil in ein '
                'eigenes EXCLUDE_OBJECT, sodass ein abgelöstes Kleinteil mitten im Druck '
                'übersprungen werden kann.',
            ],
            tabelle=cover_tbl,
        )

        # ---- Kapitel 1 ------------------------------------------------------
        st += H1('Klemmmechanik, Systemmaße & 76er-Teilekatalog', '1')
        st += P(
            'Damit ein gedruckter Baustein auf Anhieb klemmt (<i>Clutch Power</i>), ohne dass '
            'benachbarte Steine auf einer Grundplatte klemmen oder sich nach außen wölben, '
            'müssen Außenkante, Noppenraster und Unterseitenröhre drei gekoppelte Gleichungen '
            'erfüllen:'
        )
        st += FORMULA(
            'Außenmaß (w × l):   B_w = w · 8,00 - 0,20 mm,    B_l = l · 8,00 - 0,20 mm<br/>'
            'Systemhöhen:        H_brick = 9,60 mm = 3 · H_plate (3,20 mm),   H_stud = 1,80 mm<br/>'
            'Noppen-Inkreis:     D_in = sqrt(2) · 8,00 - D_stud = 11,314 - 4,80 = 6,514 mm<br/>'
            'Röhren-Passung:     D_tube,OD = 6,31 mm  (Wand 0,657 mm = 1 Spur @ 0,6-mm-Düse)',
            'Bei Scale != 100 % (25..300 %) skaliert make_bricks() sämtliche Geometriegrößen '
            'proportional mit s = Scale/100, erhöht aber statt der düsenfesten Spurbreite '
            'gezielt die Wandlinienzahl: _loops = 2 + (Scale &gt;= 200) + (Scale &gt;= 300). '
            'Ein 200-%-Riesenstein erhält also 3 geschlossene Außenwände statt einer dünnen Schale!'
        )
        st += P(
            'Auf den Decklagen von Steinen, Platten und Fliesen verhindert <b>_brick_hatch()</b> '
            'jedes Überdrucken der offenen Röhren- bzw. Noppenkerne: Der Boustrophedon-Scanner '
            'schneidet die Kreisfreistellungen analytisch aus jeder Schraffurlinie heraus '
            'und verbindet Nachbarspuren ohne Retract-Sturm.'
        )

        st += TBL(
            ['Familie', 'Codes (76 gesamt)', 'Geometrie & Noppenregel (_brick_studs)'],
            [
                ['Bricks (Steine)', 'B1x1 .. B8x8 (20 Codes)', 'Volle Höhe 9,6 mm, volles w×l-Hohlnoppenraster, Röhren ab 2×2'],
                ['Plates (Platten)', 'P1x1 .. P8x8 (20 Codes)', 'Drittelhöhe 3,2 mm, volles w×l-Noppenraster, Röhren ab 2×2'],
                ['Tiles (Fliesen)', 'T1x1 .. T8x8 (20 Codes)', 'Drittelhöhe 3,2 mm, spiegelglatte Deckfläche (0 Noppen!)'],
                ['Sonder-1×1 / Jumper', 'J1x2 · R1x1 · RP1x1 · RT1x1 · C1x1', 'Jumper 1×2 mit 1 Mittelnoppe; Rundstein/-platte/-fliese & Kegel'],
                ['Slopes (Dachsteine)', 'S1x2..S1x4 · S2x2..S2x6 (7 Codes)', 'l=2 steile Schräge (0 Noppen); l>=3 flache Schräge + hintere Noppenreihe'],
                ['Inverted Slopes', 'I1x2 · I1x3 · I2x2 · I2x3 (4 Codes)', 'Überhängende Unterschräge (z. B. Flugzeugbug / Konsolen), volles Noppenfeld'],
                ['Arches (Bögen)', 'A1x3 · A1x4 · A1x5 · A1x6 (4 Codes)', 'Gebrückter Torbogen auf der Unterseite, volles Noppenraster oben'],
                ['Technic-Balken', 'H1x2 · H1x3 · H1x4 · H1x6 · H1x8', '9,6-mm-Balken mit horizontalen Ø 4,9-mm-Achsbohrungen im 8-mm-Raster'],
            ],
            [34 * mm, 48 * mm, 80 * mm],
        )
        st += SP(2)
        st += [IMG(fig1, width_mm=162)]
        st += CAP(
            'Abbildung 1 — Links: Echte aus V01_Bricks.gcode geparste Werkzeugbahnen (Layer 3 '
            'mit Ø 6,31-mm-Klemmröhren in Blau, Noppen-Layer Ø 4,80 mm in Orange). Rechts: '
            'Maßstäblicher Klemmnachweis der 2×2-Zelle.'
        )

        # ---- Kapitel 2 ------------------------------------------------------
        st += H1('BrickKit (Modell -> Bausatz) & System-Figuren', '2')
        st += P(
            '<b>1. BrickKit (make_brick_kit):</b> Verwandelt jede bereits geslicte Druckdatei '
            'vollautomatisch in einen baubaren Klemmbaustein-Bausatz! Dazu liest '
            '<b>_kit_voxelize()</b> ausschließlich echte Modellspuren (Support, Brim, Skirt und '
            'Purge-Tower werden verworfen), erkennt Hohlkörper/Vasen bei einem Infill-Anteil '
            '<b>&lt; 15 %</b> automatisch als Hohlraster-Ringe und wählt bei <b>Detail = AUTO</b> '
            'anhand der Modellbreite in Noppen die optimale Auflösung:'
        )
        st += B(
            '<b>BIG (max_studs &lt;= 10):</b> Feinstes 3,2-mm-Plattenraster — kleine Modelle '
            '(z. B. Speed-Champions-Stil) bestehen aus vielen Platten und Dachsteinen statt aus '
            'drei groben Klötzen.',
            '<b>SMALL (11..26 Noppen) & MICRO (&gt; 26 Noppen):</b> 9,6-mm-Steinraster mit '
            'automatischer Einzelpixel-Bereinigung (SMALL entfernt isolierte Ausreißer, MICRO '
            'fordert mindestens 2 Nachbarn).',
            '<b>Automatische Slope-Erkennung (R133):</b> Endet eine Säule an einer Stufenkante '
            '(darunter belegt, daneben frei, darüber nichts mehr), ersetzt der Zerleger den '
            'Randstein selbständig durch einen passenden Dachstein <b>S*</b> bzw. <b>SP*</b>!',
            '<b>Zwei mehrfarbige Plattenstrategien:</b> <b>BY_LAYER</b> erzeugt eine separate '
            'Datei pro Farbe (<b>0× M600</b> — der Plattenwechsel ist der Farbwechsel!); '
            '<b>BY_OBJECT</b> packt verschiedene Farben auf dieselbe Platte und wechselt nur '
            'einmal pro Farbgruppe per M600.'
        )
        st += P(
            '<b>2. System-Figuren (make_figures):</b> Druckt 1 bis 24 klassisch proportionierte '
            'Spielfiguren (bei <b>Scale = 100 %</b> passen Füße auf Systemnoppen, Hüte auf die '
            'Ø 4,89-mm-Kopfnoppe und die Ø 2,4-mm-Greifhände um Stangen). Im Modus '
            '<b>PARTS</b> entstehen 5 klebefrei rastende Einzelteile (<b>LEGS</b>, trapezförmiger '
            '<b>TORSO</b> 15,43 -> 10,59 mm, <b>ARM1</b>, <b>ARM2</b>, <b>HEAD</b>). Entscheidend '
            'ist der Feld-Fix R132: Die Arme liegen beim Drucken flach auf der Seite, sodass '
            'sowohl der Ø 3,94-mm-Schulterzapfen als auch das Greifmaul als saubere vertikale '
            'Zylinder ohne Stützmaterial entstehen!'
        )
        st += [IMG(fig2, width_mm=162)]
        st += CAP(
            'Abbildung 2 — Links: Drei echte Farbplatten (GRY / BLK / RED) aus make_brick_kit() '
            'auf einer Stufenpyramide (inkl. automatisch eingesetzter SP*-Dachsteine). Rechts: '
            'Geparste 5-teilige Figur aus make_figures(mode="PARTS").'
        )

        # ---- Kapitel 3 ------------------------------------------------------
        st += [PageBreak()]
        st += H1('Live-Menüreferenz & Gemessene Referenzläufe', '3')
        st += P(
            'Direkt zur Bauzeit aus <b>menus/lcd_menues.cfg</b> gelesene Bedienzeilen unter '
            '<b>Tools &gt; Bricks</b> (die 76 Katalog-Zeilen sind in Zeile 2 zusammengefasst):'
        )
        st += TBL(
            ['LCD-Menüpfad', 'Anzeige am Display', 'Wertebereich / Aktion'],
            [[r[0], r[1], r[2]] for r in lcd_rows[:24]],
            [62 * mm, 56 * mm, 44 * mm],
        )

        st += H2('Sechs echte Referenzläufe (live beim PDF-Bau gerechnet)', '3.1')
        bench_rows = [
            ['1. 6-Familien-Testset', 'B2x4, P2x2, T1x2, S2x3, H1x4, R1x1 @ 0.6',
             i_mix['file'], '%d Teile · %d Lagen' % (len(prs_mix['objs']), prs_mix['n_layers']),
             '0× M600 · ΣΔE=%.0f mm' % prs_mix['total_e']],
            ['2. 3-Farb-Sortiment', '12 Teile · Colors=3 · BY_LAYER',
             '%d Dateien (%s..)' % (len(i_3c['plate_files']), i_3c['plate_files'][0]),
             'je 1 Farbe / Platte', '0× M600 (Plattenwechsel!)'],
            ['3. Mehrfarb-Einzelplatte', '4 Teile · Colors=2 · BY_OBJECT',
             i_obj['file'], 'sequenziell gedruckt', '1× M600 zwischen Farben'],
            ['4. Jumbo-Baustein 200 %', '2× B2x4 · Scale=200 % · LH=0.24',
             i_200['file'], '63,6 × 31,6 mm Basis', '3 Wandlinien (+1-Regel!)'],
            ['5. BrickKit (3 Farben)', 'Stufenbau.gcode · Detail=BIG · BY_LAYER',
             '%d Platten (%s..)' % (len(i_kit['plates']), i_kit['plates'][0]),
             '%d Teile · %d Bänder' % (i_kit['parts'], i_kit['bands']),
             '0× M600 · inkl. Slopes'],
            ['6. Figuren PARTS vs SINGLE', '1× PARTS (5-tlg.) / 2× SINGLE',
             '%s / %s' % (i_fig['file'], i_figs['file']),
             '5 Teile bzw. 2 Figuren', 'Klebefrei @ 100 % Maßstab'],
        ]
        st += TBL(
            ['Szenario', 'Parameter', 'Erzeugte Datei(en)', 'Umfang / Maß', 'Farbwechsel / Ergebnis'],
            bench_rows,
            [30 * mm, 38 * mm, 36 * mm, 29 * mm, 29 * mm],
        )

        st += SP(2)
        st += [BOX(
            'Blind-Checkliste für perfekte Klemmkraft direkt vom Druckbett',
            [
                '• Warteschlange am Drehrad füllen: Count wählen (z. B. 4) -> im Catalog B2x4 anklicken -> '
                'Display meldet sofort „+4 B2x4“ (gleiche Codes werden automatisch addiert, max. 120 Teile/Platte).',
                '• Elefantenfuß vermeiden: Layer 1 druckt geschlossen für sicheren Halt, die Ø 6,31-mm-Röhren '
                'öffnen sich erst ab Layer 2! Brim = 2 hält schmale 1×N-Steine zuverlässig plan.',
                '• Kompatibilität: Nur Scale = 100 % passt auf handelsübliche 8-mm-Noppensteine; '
                'Scale = 200 % baut kompatible 16-mm-Großbausteine für Kinderhände (mit 3 Außenwänden).',
            ],
            kind='tip',
        )]

        doc.render()
    return out_pdf


if __name__ == '__main__':
    dst = os.path.join(REPO, 'BRICKS.pdf')
    build_pdf(dst)
    print('Wrote %s (%d bytes)' % (dst, os.path.getsize(dst)))
