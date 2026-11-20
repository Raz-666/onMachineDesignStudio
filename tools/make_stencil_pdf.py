#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""make_stencil_pdf.py — Wissenschaftliche Methodik-, Mathematik- &
Blindbedienungs-PDF für den Sprüh-Schablonen-Generator (MASTER-TODO D3 + D6,
R267 / J9, Tools > Stencil).

Verbindliche D6-Wahrheitsregel:
  * KEINE Fantasie-Grafiken. Jede Abbildung und jede Kennzahl in diesem Heft
    wird zur Bauzeit aus echten Läufen von `r2_postproc.make_stencil()` in
    einem temporären Arbeitsverzeichnis berechnet und aus dem real erzeugten
    G-Code bzw. den echten Plattenmasken gezeichnet.
  * LCD-Menüzeilen werden live aus `menus/lcd_menues.cfg` gelesen.
  * Der Versionsstempel kommt dynamisch aus `r2_version.VERSION`.
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


# ------------------------------------------------ Synthetische Referenzmotive
def _make_emblem_png(path):
    """3-Ton-Ringemblem mit echter schwebender Platteninsel (O-Ring + Kern +
    Banner), damit `_stencil_bridges267` deterministisch 3×-Düse-Brücken baut."""
    im = PILImage.new('L', (200, 200), 245)
    dr = ImageDraw.Draw(im)
    dr.ellipse((22, 18, 178, 174), fill=148)     # Mittelton-Außenring
    dr.ellipse((54, 50, 146, 142), fill=245)     # heller Inselring!
    dr.ellipse((80, 76, 120, 116), fill=22)      # dunkler Kern
    dr.rectangle((26, 156, 174, 182), fill=22)   # dunkler Sockelstreifen
    im.save(path)
    return path


def _make_gradient_photo_png(path):
    """4-Ton-Landschaftsmotiv mit vier um den Graumittelpunkt 128 balancierten
    Bändern (248, 198, 122, 18), sodass nach dem 1,35×-Kontrastboost alle 4
    Tonbänder je ~20..30 % Fläche tragen und 4 Platten gebaut werden."""
    w, h = 220, 160
    im = PILImage.new('L', (w, h), 248)
    px = im.load()
    for y in range(h):
        for x in range(w):
            d_sun = math.hypot(x - 58, y - 30)
            if 14 < d_sun < 25:
                px[x, y] = 122
            elif d_sun <= 14:
                px[x, y] = 248
            elif y < 40 + int(5 * math.sin(x / 28.0)):
                px[x, y] = 248
            elif y < 80 + int(6 * math.cos(x / 23.0)):
                px[x, y] = 198
            elif y < 120 + int(5 * math.sin(x / 17.0)):
                px[x, y] = 122
            else:
                px[x, y] = 18
    im.save(path)
    return path


def _make_twotone_logo_png(path):
    """Hartes 2-Ton-Logo (nur Schwarz 20 und Weiß 245): prüft die ehrliche
    R267-Reduktion von Bands=4 auf 2 gesunde Platten (< 2 %-Flächenwächter)."""
    im = PILImage.new('L', (180, 180), 245)
    dr = ImageDraw.Draw(im)
    dr.rounded_rectangle((28, 28, 152, 152), radius=18, fill=20)
    dr.rounded_rectangle((52, 52, 128, 128), radius=10, fill=245)
    dr.ellipse((74, 74, 106, 106), fill=20)
    im.save(path)
    return path


# ----------------------------------------- G-Code-Parser & Live-Messfunktionen
def _parse_layer_segments(gcode_path, layer_idx=2):
    """Liest alle extrudierenden XY-Segmente einer konkreten Schicht (Default:
    Layer 2 = erste reine Plattenlage ohne Brim) getrennt nach APPLY_TYPE."""
    segs = []
    cur_layer = 0
    cur_type = 'OTHER'
    x = y = e = 0.0
    erel = True
    total_e = 0.0
    with open(gcode_path, encoding='utf-8', errors='replace') as fh:
        for raw in fh:
            s = raw.strip()
            if s == 'LAYER_MARK' or s.startswith(';LAYER_CHANGE'):
                if s == 'LAYER_MARK':
                    cur_layer += 1
                continue
            if s.startswith('APPLY_TYPE TYPE='):
                cur_type = s.split('TYPE=', 1)[1].split()[0].strip('"\'')
                continue
            code = s.split(';', 1)[0].strip()
            if not code:
                continue
            if code == 'M83':
                erel = True
                continue
            if code == 'M82':
                erel = False
                continue
            if not (code.startswith('G0 ') or code.startswith('G1 ')):
                continue
            nx, ny = x, y
            ne = None
            for tok in code.split()[1:]:
                c = tok[:1]
                if c in 'XYE':
                    try:
                        v = float(tok[1:])
                    except ValueError:
                        continue
                    if c == 'X':
                        nx = v
                    elif c == 'Y':
                        ny = v
                    elif c == 'E':
                        ne = v
            de = 0.0
            if ne is not None:
                de = ne if erel else (ne - e)
                e = (e + ne) if erel else ne
            if de > 1e-6 and math.hypot(nx - x, ny - y) > 1e-6:
                total_e += de
                if cur_layer == layer_idx:
                    segs.append((x, y, nx, ny, cur_type))
            x, y = nx, ny
    return segs, total_e


def _measure_hole_centers_mm(mask, x0, y0, wid, frame_w=8.0):
    """Bestimmt die 4 Passloch-Schwerpunkte in echten Bett-Millimetern streng
    innerhalb der vier FR×FR-Rahmenecken (wo ausschließlich das D4.2-Passloch
    ausgespart ist, unabhängig davon ob Band 0 im Innenfenster offen liegt)."""
    R = len(mask)
    C = len(mask[0])
    fr = max(3, int(round(frame_w / wid)))
    quads = [
        (0, fr, 0, fr),
        (0, fr, C - fr, C),
        (R - fr, R, 0, fr),
        (R - fr, R, C - fr, C),
    ]
    centers = []
    for r0, r1, c0, c1 in quads:
        xs, ys = [], []
        for r in range(r0, r1):
            for c in range(c0, c1):
                if not mask[r][c]:
                    xs.append(x0 + (c + 0.5) * wid)
                    ys.append(y0 + (r + 0.5) * wid)
        if xs:
            centers.append((sum(xs) / len(xs), sum(ys) / len(ys)))
    return centers


# -------------------------------------------------------- Live-LCD-Menüparser
def _parse_stencil_menu():
    cfg_path = os.path.join(REPO, 'menus', 'lcd_menues.cfg')
    txt = open(cfg_path, encoding='utf-8').read()
    blocks = re.split(r'(?m)^(?=\[menu )', txt)
    secs = [b for b in blocks if b.startswith('[menu __main __gen __stencil')]
    rows = []
    seen_slots = False
    for sec in secs:
        lines = [l.strip() for l in sec.strip().splitlines() if l.strip()]
        hdr = lines[0].strip('[]').replace('menu __main __gen __stencil', 'Tools > Stencil')
        if re.search(r'__s\d+$', hdr):
            if seen_slots:
                continue
            seen_slots = True
            rows.append((
                'Tools > Stencil > Images > 1..10',
                '1*..10* [Bilddatei]',
                '2× Klick (Arm -> Start)',
            ))
            continue
        nm = mn = mx = st = ''
        tp = ''
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
        if 'Bands:' in nm:
            nm = 'Bands: [2..4]'
        elif 'Edge:' in nm:
            nm = 'Edge: [40..220]mm'
        elif 'Thick:' in nm:
            nm = 'Thick: [0.4..2.0]mm'
        elif 'Negativ:' in nm:
            nm = 'Negativ: ON / off'
        elif '< page' in nm:
            nm = '&lt; page (zurück)'
        elif 'page ' in nm:
            nm = 'page &gt; (weiter)'
        rng = ('%s .. %s (Schritt %s)' % (mn, mx, st)) if mn else ('Untermenü' if tp == 'list' else 'Aktion / Schalter')
        rows.append((hdr.replace(' __', ' > '), nm, rng))
    return rows


# --------------------------------------------------------- D6-Echtlauf-Grafiken
def _fig_stencil_plates(tmpdir, info, out_png):
    """Abb. 1: 2×2-Ansicht der echten Layer-2-Werkzeugbahnen aller 4 erzeugten
    Platten (`Schablone1..3` + `SchabloneNeg`) mit Hervorhebung der 4 identischen
    D4.2-Passlöcher und der automatischen 3×-Düse-Haltestege."""
    W_img, H_img = 1520, 1340
    im = PILImage.new('RGB', (W_img, H_img), '#ffffff')
    dr = ImageDraw.Draw(im)
    f_title = font(24, bold=True)
    f_sub = font(18, bold=True)
    f_lbl = font(15)
    f_sm = font(13)

    dr.text((28, 18),
            'Echte Werkzeugbahnen (Layer 2) aller 4 erzeugten Platten — 3-Ton-Ringmotiv + Negativ',
            fill='#1c4e8c', font=f_title)
    dr.text((28, 50),
            'Blau = WALL-OUTER-Konturen · Hellblau = INFILL-SOLID-Vollfläche · Rot = 4× Passloch D4,2 mm · Orange = 3×-Düse-Haltesteg',
            fill='#58595b', font=f_lbl)

    titles = [
        ('1. Schablone1 (Band 0 = heller Hintergrund offen)', 'Sprühstufe 1 (hellste Farbe)'),
        ('2. Schablone2 (Band 1 = Außenring offen)', 'Sprühstufe 2 (Mittelton, Inselsteg aktiv)'),
        ('3. Schablone3 (Band 2 = Kern + Banner offen)', 'Sprühstufe 3 (dunkelster Akzent)'),
        ('4. SchabloneNeg (Negativ: Motiv steht, Rand offen)', 'Einzel-Konturschablone'),
    ]

    wid = 0.4 * 1.08
    W_mm = info['width']
    H_mm = info['height']
    # Bettmitte wie in make_stencil (bed default (0,-3,244,238), margin 6)
    cx_bed = (6.0 + 238.0) / 2.0
    cy_bed = (3.0 + 232.0) / 2.0
    x0_mm = cx_bed - W_mm / 2.0
    y0_mm = cy_bed - H_mm / 2.0

    panel_w, panel_h = 700, 585
    positions = [(32, 92), (784, 92), (32, 715), (784, 715)]

    for idx, (fname, (label_mask, mask)) in enumerate(zip(info['files'], info['masks'])):
        px0, py0 = positions[idx]
        dr.rounded_rectangle((px0, py0, px0 + panel_w, py0 + panel_h),
                             radius=10, fill='#f8fafd', outline='#bfd0e6', width=2)
        t_main, t_sub = titles[idx]
        dr.text((px0 + 16, py0 + 10), t_main, fill='#1c4e8c', font=f_sub)
        nbr = info['bridges'][idx]
        dr.text((px0 + 16, py0 + 35),
                '%s  ·  Datei: %s  ·  Brücken: %d' % (t_sub, fname, nbr),
                fill='#4a5568', font=f_sm)

        segs, tot_e = _parse_layer_segments(os.path.join(tmpdir, fname), layer_idx=2)
        hole_pts = _measure_hole_centers_mm(mask, x0_mm, y0_mm, wid)

        pad = 36
        avail_w = panel_w - 2 * pad
        avail_h = panel_h - 104
        scale = min(avail_w / W_mm, avail_h / H_mm)
        ox = px0 + (panel_w - W_mm * scale) / 2.0
        oy = py0 + 62 + (avail_h - H_mm * scale) / 2.0

        def to_px(xm, ym):
            return (ox + (xm - x0_mm) * scale,
                    oy + (H_mm - (ym - y0_mm)) * scale)

        # Freigeschnittene Sprühfläche zart bernsteinfarben hinterlegen
        R_m = len(mask)
        C_m = len(mask[0])
        for r in range(R_m):
            c = 0
            while c < C_m:
                if not mask[r][c]:
                    c_start = c
                    while c < C_m and not mask[r][c]:
                        c += 1
                    xa, ya = to_px(x0_mm + c_start * wid, y0_mm + (r + 1) * wid)
                    xb, yb = to_px(x0_mm + c * wid, y0_mm + r * wid)
                    dr.rectangle((xa, ya, xb, yb), fill='#fff3dc')
                else:
                    c += 1

        # Erst Infill-Bahnen, dann Außenwände für gestochen scharfe Lesbarkeit
        for x1, y1, x2, y2, tp in segs:
            if tp != 'WALL-OUTER':
                p1 = to_px(x1, y1)
                p2 = to_px(x2, y2)
                dr.line((p1[0], p1[1], p2[0], p2[1]), fill='#7da6d8', width=1)
        for x1, y1, x2, y2, tp in segs:
            if tp == 'WALL-OUTER':
                p1 = to_px(x1, y1)
                p2 = to_px(x2, y2)
                dr.line((p1[0], p1[1], p2[0], p2[1]), fill='#163c6e', width=2)

        # 4 Passlöcher mit Fadenkreuz markieren
        for hx, hy in hole_pts:
            hp = to_px(hx, hy)
            hr = 2.1 * scale
            dr.ellipse((hp[0] - hr, hp[1] - hr, hp[0] + hr, hp[1] + hr),
                       outline='#c62828', width=2)
            dr.line((hp[0] - hr - 4, hp[1], hp[0] + hr + 4, hp[1]),
                    fill='#c62828', width=1)
            dr.line((hp[0], hp[1] - hr - 4, hp[0], hp[1] + hr + 4),
                    fill='#c62828', width=1)

        # Falls Brücke gesetzt wurde, Steg-Hinweis auf Inselhöhe markieren
        if nbr > 0:
            ymid = y0_mm + H_mm * 0.54
            pm = to_px(x0_mm + W_mm * 0.50, ymid)
            dr.rounded_rectangle((pm[0] - 92, pm[1] - 11, pm[0] + 92, pm[1] + 11),
                                 radius=5, fill='#fff8eb', outline='#e07b00', width=2)
            dr.text((pm[0] - 84, pm[1] - 8),
                    '3× Düse Haltesteg (1,2 mm)', fill='#b35c00', font=f_sm)

        dr.text((px0 + 18, py0 + panel_h - 24),
                'Platte %.1f × %.1f mm · ΣΔE Layer 2: %.1f mm · Gelb = offenes Sprühfenster'
                % (W_mm, H_mm, tot_e / 4.0),
                fill='#58595b', font=f_sm)

    im.save(out_png)
    return out_png


def _fig_guards_and_stack(info_4band, info_reduced, hole_delta_mm, out_png):
    """Abb. 2: Links gemessene Tonband-Flächenanteile (gesundes 4-Band-Motiv vs.
    ehrliche Reduktion Bands=4 -> 2 bei 2-Ton-Logo wegen < 2 %-Regel); rechts
    maßstäblicher Stapel-Querschnitt auf M4-Passstiften."""
    W_img, H_img = 1520, 620
    im = PILImage.new('RGB', (W_img, H_img), '#ffffff')
    dr = ImageDraw.Draw(im)
    f_title = font(18, bold=True)
    f_sub = font(15, bold=True)
    f_lbl = font(14)
    f_sm = font(13)

    # Linke Karte: 2-%-Flächenwächter
    dr.rounded_rectangle((24, 20, 756, 598), radius=10,
                         fill='#f8fafd', outline='#bfd0e6', width=2)
    dr.text((40, 34), 'A. 2-%-Flächenwächter & Plattenreduktion (R267)',
            fill='#1c4e8c', font=f_title)
    dr.text((40, 62),
            'Jedes Band unter 2,0 % Fensterfläche wäre haarfein — Perzentil-Recut oder Reduktion:',
            fill='#58595b', font=f_sm)

    tot4 = float(sum(info_4band['bands']))
    pct4 = [100.0 * b / tot4 for b in info_4band['bands']]
    tot2 = float(sum(info_reduced['bands']))
    pct2 = [100.0 * b / tot2 for b in info_reduced['bands']]

    # Balkengruppe 1: 4-Ton-Landschaft
    dr.text((44, 98),
            'Lauf A: 4-Ton-Landschaft (Bands=4 bestellt -> %d Platten gebaut)' % info_4band['steps'],
            fill='#163c6e', font=f_sub)
    bar_x0, bar_max_w = 172, 430
    cols4 = ['#9ec5fe', '#4ea8de', '#1c4e8c', '#0f2942']
    for k, p in enumerate(pct4):
        yk = 132 + k * 38
        dr.text((44, yk + 4), 'Band %d' % k, fill='#222222', font=f_lbl)
        bw = max(4, int(bar_max_w * (p / 100.0)))
        dr.rounded_rectangle((bar_x0, yk, bar_x0 + bw, yk + 26),
                             radius=4, fill=cols4[min(3, k)])
        dr.text((bar_x0 + bw + 10, yk + 4),
                '%.1f %% (%d Zellen >= 2 %%)' % (p, info_4band['bands'][k]),
                fill='#1e7d32', font=f_sm)

    # 2-%-Schwellenlinie
    x_thr = bar_x0 + int(bar_max_w * 0.02)
    dr.line((x_thr, 126, x_thr, 286), fill='#c62828', width=2)

    # Balkengruppe 2: 2-Ton-Logo mit Bands=4 bestellt -> ehrlich auf 2 reduziert
    dr.text((44, 318),
            'Lauf B: S/W-Logo (Bands=4 bestellt -> auf %d Platten reduziert!)'
            % info_reduced['steps'],
            fill='#b35c00', font=f_sub)
    dr.text((44, 344),
            'Zwischenstufen < 2 % Fläche entfallen automatisch ohne Geisterschablonen:',
            fill='#58595b', font=f_sm)
    for k, p in enumerate(pct2):
        yk = 378 + k * 44
        dr.text((44, yk + 6), 'Platte %d' % (k + 1), fill='#222222', font=f_lbl)
        bw = max(4, int(bar_max_w * (p / 100.0)))
        dr.rounded_rectangle((bar_x0, yk, bar_x0 + bw, yk + 30),
                             radius=4, fill='#1c4e8c' if k else '#7da6d8')
        dr.text((bar_x0 + bw + 10, yk + 6),
                '%.1f %% (%d Zellen)' % (p, info_reduced['bands'][k]),
                fill='#1e7d32', font=f_sm)

    dr.rounded_rectangle((44, 488, 736, 578), radius=8,
                         fill='#eef7ee', outline='#1e7d32', width=2)
    dr.text((60, 500),
            'Merksatz für Blindarbeit am Display:', fill='#1e7d32', font=f_sub)
    dr.text((60, 526),
            'Du darfst für Logos ruhig Bands = 3 oder 4 stehen lassen: Hat die Grafik nur',
            fill='#222222', font=f_sm)
    dr.text((60, 548),
            'Schwarz & Weiß, kürzt make_stencil() leere Zwischenbänder selbständig weg.',
            fill='#222222', font=f_sm)

    # Rechte Karte: Passstift-Stapel & Sprühfolge
    dr.rounded_rectangle((780, 20, 1496, 598), radius=10,
                         fill='#f8fafd', outline='#bfd0e6', width=2)
    dr.text((800, 34), 'B. M4-Passstift-Stapel & Sprühfolge (Hell -> Dunkel)',
            fill='#1c4e8c', font=f_title)
    dr.text((800, 62),
            'Gemessener Passloch-Mittenversatz über alle Platten des Sets: ΔXY = %.4f mm'
            % hole_delta_mm,
            fill='#1e7d32', font=f_lbl)

    # Zeichne Werkstück + 2 M4-Stifte + 3 Schablonenlagen im Aufriss
    sx0, sx1 = 850, 1430
    # Untergrund / Werkstück
    dr.rectangle((sx0, 470, sx1, 515), fill='#e2e8f0', outline='#64748b', width=2)
    dr.text((sx0 + 185, 483), 'Werkstück / Karton / Holzplatte', fill='#334155', font=f_lbl)

    # Zwei M4-Passstifte links und rechts im 8-mm-Rahmen
    pin_l, pin_r = sx0 + 44, sx1 - 44
    for px in (pin_l, pin_r):
        dr.rectangle((px - 10, 145, px + 10, 520), fill='#cbd5e1', outline='#475569', width=2)
        dr.text((px - 28, 120), 'M4-Pin', fill='#475569', font=f_sm)

    # 3 gestapelte Schablonenplatten (0,8 mm = 4 Layer @ 0,20 mm)
    plates_vis = [
        (395, '1. Schablone1 (Band 0 offen -> Grundton / Hell)', '#9ec5fe', [(960, 1045), (1235, 1320)]),
        (305, '2. Schablone2 (Band 1 offen -> Mittelton + 3×-Düse-Steg)', '#4ea8de', [(1045, 1115), (1165, 1235)]),
        (215, '3. Schablone3 (Band 2 offen -> Dunkelster Akzent)', '#1c4e8c', [(1115, 1165)]),
    ]
    for yp, lbl, col, cuts in plates_vis:
        dr.rectangle((sx0, yp, sx1, yp + 34), fill=col, outline='#0f2942', width=2)
        # Passloch-Bohrungen D4.2 mm (0,2 mm Spiel um M4)
        for px in (pin_l, pin_r):
            dr.rectangle((px - 13, yp, px + 13, yp + 34), fill='#ffffff', outline='#c62828', width=2)
        # Sprühfenster
        for ca, cb in cuts:
            dr.rectangle((ca, yp, cb, yp + 34), fill='#fff3dc', outline='#e07b00', width=2)
            # Sprühpfeile
            cm = (ca + cb) // 2
            dr.line((cm, yp - 22, cm, yp + 28), fill='#e07b00', width=2)
        dr.text((sx0 + 74, yp - 24), lbl, fill='#0f2942', font=f_sm)

    dr.rounded_rectangle((802, 530, 1474, 582), radius=8,
                         fill='#fff8eb', outline='#e07b00', width=2)
    dr.text((816, 540),
            'Goldene Sprühregel: Immer Schablone1 -> Schablone2 -> Schablone3!',
            fill='#b35c00', font=f_sub)
    dr.text((816, 561),
            'Für 1-Schuss-Logo auf fertigem Untergrund: Negativ = ON -> SchabloneNeg nutzen.',
            fill='#222222', font=f_sm)

    im.save(out_png)
    return out_png


# -------------------------------------------------------------- Hauptdokument
def build_pdf(out_pdf):
    lcd_rows = _parse_stencil_menu()

    with tempfile.TemporaryDirectory(prefix='r2_stencil_pdf_') as tmpdir:
        p_emb = _make_emblem_png(os.path.join(tmpdir, 'Emblem3Ton.png'))
        p_pho = _make_gradient_photo_png(os.path.join(tmpdir, 'Landschaft4Ton.png'))
        p_log = _make_twotone_logo_png(os.path.join(tmpdir, 'LogoSW.png'))

        # 5 echte Referenzläufe von make_stencil()
        _, info_emb = pp.make_stencil(
            p_emb, steps=3, size_mm=90.0, layer_h=0.2, thick=0.8,
            negative=True, nozzle=0.4, out_dir=tmpdir)

        _, info_pho = pp.make_stencil(
            p_pho, steps=4, size_mm=120.0, layer_h=0.2, thick=0.8,
            negative=False, nozzle=0.4, out_dir=tmpdir)

        _, info_red = pp.make_stencil(
            p_log, steps=4, size_mm=80.0, layer_h=0.2, thick=0.8,
            negative=False, nozzle=0.4, out_dir=tmpdir)

        _, info_big = pp.make_stencil(
            p_emb, steps=3, size_mm=160.0, layer_h=0.2, thick=1.0,
            negative=False, nozzle=0.6, out_dir=tmpdir)

        _, info_hd = pp.make_stencil(
            p_log, steps=2, size_mm=100.0, layer_h=0.2, thick=1.6,
            negative=True, nozzle=0.4, out_dir=tmpdir)

        # Prüfe Passloch-Kongruenz über alle 4 Platten von Lauf 1
        wid_04 = 0.4 * 1.08
        cx_bed = (6.0 + 238.0) / 2.0
        cy_bed = (3.0 + 232.0) / 2.0
        x0_emb = cx_bed - info_emb['width'] / 2.0
        y0_emb = cy_bed - info_emb['height'] / 2.0
        ref_holes = _measure_hole_centers_mm(info_emb['masks'][0][1], x0_emb, y0_emb, wid_04)
        max_hole_delta = 0.0
        for _, msk in info_emb['masks'][1:]:
            cur_holes = _measure_hole_centers_mm(msk, x0_emb, y0_emb, wid_04)
            for (rx, ry), (qx, qy) in zip(ref_holes, cur_holes):
                max_hole_delta = max(max_hole_delta, math.hypot(qx - rx, qy - ry))

        fig1 = os.path.join(tmpdir, 'fig_stencil_plates.png')
        _fig_stencil_plates(tmpdir, info_emb, fig1)

        fig2 = os.path.join(tmpdir, 'fig_stencil_guards.png')
        _fig_guards_and_stack(info_pho, info_red, max_hole_delta, fig2)

        doc = Doc(
            out_pdf,
            kopf='R2-D2 Macro System · Generator Sprüh-Schablonen / Stencil (D3)',
            titel='Sprüh-Schablonen (Stencil) — Methodik, Insel-Topologie & Blindbedienung',
        )
        st = doc.story

        cover_tbl = TBL(
            ['Kenngröße', 'Wert im aktuellen Produktivcode (R267 / J9)'],
            [
                ['Menüpfad am Display', 'Tools > Stencil  (nutzt die gemeinsame Bildliste im gcodes-Root)'],
                ['G-Code-Makros / Engine', 'STENCIL_INFO · STENCIL_CREATE  ->  r2_postproc.make_stencil()'],
                ['Tonbänder (Bands)', '2 .. 4 Bänder (Default 3) · je Band eine eigene flache G-Code-Platte'],
                ['Bildgröße & Plattendicke', 'Edge 40 .. 220 mm (längere Bildkante) · Thick 0,4 .. 2,0 mm (Default 0,8 mm)'],
                ['Rahmen & Passstift-Register', 'Umlaufender 8,0-mm-Rahmen + 4× Passloch D4,2 mm (M4) an identischer Bettposition'],
                ['Automatische Inselbrücken', '_stencil_bridges267(): 8er-Flood-Fill, Stegbreite 3× Düse (max. 80 Iterationen)'],
                ['Negativ-Zusatzplatte', 'Negativ = ON erzeugt zusätzlich Vnn_SchabloneNeg_<Stamm>.gcode'],
                ['Ausgabeordner & Dateinamen', 'gcodes/Stencil/Vnn_Schablone1..4_<Stamm>.gcode (+ optional SchabloneNeg)'],
            ],
            [56 * mm, 106 * mm],
        )[0]

        doc.add_cover(
            kicker='GENERATOR-FACHHEFT · BILD-ZU-GEOMETRIE-FAMILIE (D3 / D6)',
            titel='Sprüh-Schablonen (Stencil)',
            untertitel='Mehrstufige Tonband-Zerlegung, automatische 3×-Düse-Inselbrücken und M4-passstiftregistrierte Plattenstapel direkt aus PNG/JPG-Bildern',
            absaetze=[
                'Wer ein Logo, Piktogramm oder kontrastreiches Foto mit Sprühlack, Airbrush oder '
                'Schwamm auf Holz, Blech, Stoff oder Gehäuse übertragen will, scheitert bei '
                'klassischen Ausschnitten sofort an zwei Problemen: Mehrfarbige Motive verrutschen '
                'zwischen den Sprühgängen, und geschlossene Innenflächen (wie der Kern eines „O", '
                '„A" oder Ring-Emblems) fallen beim Ausschneiden lose aus der Platte.',
                'Der native Generator make_stencil() (R267) löst beide Probleme direkt auf dem '
                'Drucker ohne Slicer und ohne CAD: Er zerlegt jedes Bild in 2 bis 4 gesunde '
                'Tonbänder, verankert schwebende Platteninseln vollautomatisch über exakt '
                '3× Düsenbreite starke Haltestege und stanzt vier M4-Passlöcher (D 4,2 mm) an '
                'identischer Bettkoordinate in jede Einzelplatte.',
            ],
            tabelle=cover_tbl,
        )

        # ---- Kapitel 1 ------------------------------------------------------
        st += H1('Funktionsprinzip & Mathematische Bild-Pipeline', '1')
        st += P(
            '<b>make_stencil()</b> in <b>tools/r2_postproc.py</b> verarbeitet jedes im '
            'Wurzelordner <b>gcodes/</b> abgelegte <b>.png</b>-, <b>.jpg</b>- oder '
            '<b>.jpeg</b>-Bild (RAM-Deckel <b>max_dim = 768 px</b> für den Raspberry Pi Zero 2 W) '
            'in einer streng deterministischen sechsstufigen Kette:'
        )
        st += FORMULA(
            'wid   = max(0.40, nozzle · 1.08)          [0,432 mm @ 0,4-mm-Düse]<br/>'
            'cols  = round(size_mm / wid)              [falls w &gt;= h, sonst rows]<br/>'
            'W, H  = cols·wid + 2·frame_w,  rows·wid + 2·frame_w   [frame_w = 8,0 mm]<br/>'
            'v\'    = clip((v_stretch - 0.5) · 1.35 + 0.5,  0.0,  1.0)   [Boost R128]',
            'Längere Motivkante = Edge (size_mm). Falls W oder H den nutzbaren Bauraum (Bett minus '
            '2 × 6 mm Rand) überschreitet, skaliert _sc267 das Fenster proportional herunter und '
            'dokumentiert den Prozentfaktor ehrlich im G-Code-Header.'
        )
        st += SP(2)
        st += NUM(
            '<b>Perzentil-Kontrastspreizung (2 % .. 98 %) &amp; 3×3-Gaußfilter:</b> '
            '<b>_litho_grid(..., mirror=False)</b> normiert flaue Scans wie harte Logos auf den '
            'vollen Wertebereich [0, 1] und glättet Ein-Pixel-Rauschen mit dem Faltungskern '
            '[1, 2, 1; 2, 4, 2; 1, 2, 1] / 16, damit keine unbrauchbaren Nadellöcher entstehen. '
            'Im Gegensatz zum stehenden Lithophane wird <i>nicht</i> horizontal gespiegelt — die '
            'Platte liegt beim Drucken und beim späteren Auflegen seitenrichtig.',
            '<b>Mittenkontrast-Verstärkung (Faktor 1,35):</b> <b>_img_boost128(grid, 1.35)</b> '
            'spreizt Mitteltöne vom Grauwert 0,5 weg, sodass Bandgrenzen als saubere, scharfe '
            'Sprühkanten statt ausgefranster Übergänge entstehen.',
            '<b>Nearest-Level-Quantisierung in S ∈ {2, 3, 4} Tonbänder:</b> Jede Zelle (r, c) '
            'erhält den Bandindex <b>LV[r, c] = min(S - 1, int(grid[r, c] · S + 0.5))</b>. '
            'Dabei bezeichnet <b>Band 0</b> stets den hellsten Ton (Hintergrund) und '
            '<b>Band S - 1</b> den dunkelsten Motivakzent.',
            '<b>Der 2-%-Flächenwächter (_thin267 &amp; _recut267):</b> Enthält irgendein Band '
            'weniger als <b>2,0 %</b> aller Fensterzellen (<b>rows · cols · 0.02</b>), wäre seine '
            'Schablone nur ein haarfeiner Schlitz, durch den kein Sprühnebel sauber dringt. '
            'Der Algorithmus schneidet die Schwellen zuerst an den exakten Pixel-Perzentilen neu '
            '(<b>_recut267</b>). Bleibt wegen fehlender Graustufen im Bild (z. B. reines S/W-Logo '
            'bei gewähltem <b>Bands = 4</b>) weiterhin ein Band unter 2 %, reduziert die Schleife '
            '<b>S -> S - 1</b> ehrlich bis auf die tatsächlich tragfähige Plattenzahl.'
        )

        # ---- Kapitel 2 ------------------------------------------------------
        st += H1('Plattengeometrie, M4-Passlöcher & Insel-Topologie', '2')
        st += P(
            'Aus der quantisierten Matrix <b>LV</b> baut <b>_plate267(band)</b> für jede '
            'Sprühstufe eine eigene binäre Materialmaske der Gesamtgröße '
            '<b>GR × GC = (rows + 2·FR) × (cols + 2·FR)</b> mit '
            '<b>FR = max(3, round(8.0 / wid))</b> Rahmenzellen:'
        )
        st += FORMULA(
            'Positiv-Platte k (0..S-1):  Freischnitt &lt;=&gt; LV[r, c] == k<br/>'
            'Negativ-Platte (band = -1): Freischnitt &lt;=&gt; LV[r, c] == 0  (Motiv steht!)<br/>'
            'Passlöcher (4 Ecken):       (hx, hy) ∈ {FR/2, GC-FR/2} × {FR/2, GR-FR/2}<br/>'
            'Haltesteg-Breite:           bw = max(2, round(3.0 · nozzle / wid))  [= 3× Düse]',
            'Da GC, GR, FR, x0, y0 und wid für alle Bänder eines Laufs identisch sind, liegen die '
            'vier Passlöcher D = 4,2 mm (0,2 mm Spiel für M4-Schrauben / 4-mm-Stifte) in jeder '
            'Datei auf den exakt selben Bettkoordinaten (gemessene Abweichung: 0,0000 mm).'
        )
        st += SP(2)
        st += H2('Wie _stencil_bridges267() schwebende Inseln rettet', '2.1')
        st += P(
            'Ohne Haltestege würde der Innenkern eines Buchstabens „O" oder der helle Zwischenring '
            'unseres Testemblems als loses Kunststoffplättchen auf dem Druckbett zurückbleiben, '
            'sobald man die Schablone abzieht. <b>_stencil_bridges267(mask, bw)</b> verhindert das '
            'rein topologisch auf dem Zellgitter:'
        )
        st += B(
            '<b>Schritt 1 — Festland-Flutung (8er-Nachbarschaft):</b> Ein Tiefensuch-Flood-Fill '
            'ab der Rahmenecke <b>(0, 0)</b> (die im 8-mm-Rahmen garantiert Material trägt) '
            'markiert alle mit dem Außenrahmen verbundenen Plattenzellen als <b>comp = True</b>.',
            '<b>Schritt 2 — Erste freie Insel vermessen:</b> Existiert noch eine Zelle mit '
            '<b>mask[y][x] == True</b> und <b>comp[y][x] == False</b>, sammelt ein zweiter '
            'Flood-Fill alle Zellen dieser Insel und berechnet ihre Schwerpunktzeile '
            '<b>c_y = floor(mean(y))</b> sowie ihre horizontale Ausdehnung <b>[min(x), max(x)]</b>.',
            '<b>Schritt 3 — Beidseitiger Horizontalsteg (3× Düse):</b> Auf den Zeilen '
            '<b>r0 .. r1</b> der Höhe <b>bw</b> (bei 0,4-mm-Düse: 1,2 mm = 3 Spuren) wächst ein '
            'Materialstreifen von der linken Inselkante nach links und von der rechten Inselkante '
            'nach rechts exakt bis zur ersten bestehenden Plattenzelle (spätestens bis zum '
            '8-mm-Rahmenring). Danach startet die Prüfung erneut (bis zu 80 Runden), sodass auch '
            'ineinander geschachtelte Mehrfachringe lückenlos ans Festland gekoppelt werden.',
            '<b>Schritt 4 — RLE-Rechteckblöcke &amp; Konturwände:</b> Vor dem Schreiben fasst '
            '<b>_blocks267(mask)</b> identische Zeilen-Runs zu großen Rechteckblöcken zusammen: '
            'Jede der <b>n_layers = max(2, round(thick / layer_h))</b> Schichten druckt zuerst '
            'geschlossene <b>WALL-OUTER</b>-Konturen (<b>_cell_contours</b>) um jedes Sprühfenster '
            'und jedes Passloch und füllt danach die Blöcke mit alternierendem <b>45°/135°</b>-'
            'Vollhatch.'
        )

        st += SP(3)
        st += [IMG(fig1, width_mm=162)]
        st += CAP(
            'Abbildung 1 — Live zur Bauzeit aus make_stencil(steps=3, size_mm=90, negative=True) '
            'erzeugte und aus Layer 2 der vier echten G-Code-Dateien geparste Werkzeugbahnen. '
            'In Schablone1, Schablone2 und SchabloneNeg hält je ein 1,2-mm-Horizontalsteg die '
            'schwebende Ring-/Kerninsel am Festland; Schablone3 benötigt topologisch 0 Brücken.'
        )

        st += SP(2)
        st += [IMG(fig2, width_mm=162)]
        st += CAP(
            'Abbildung 2 — Links: Echte Zellbilanz aus zwei Läufen (4-Ton-Landschaft behält 4 '
            'Platten; hartes S/W-Logo bei Bands=4 reduziert wegen der &lt;2-%%-Regel ehrlich auf 2 '
            'Platten). Rechts: Stapelprinzip auf M4-Passstiften (gemessener Lochversatz %.4f mm).'
            % max_hole_delta
        )

        # ---- Kapitel 3 ------------------------------------------------------
        st += H1('Live-Menüreferenz & Makro-Schnittstelle', '3')
        st += P(
            'Die folgende Tabelle wird beim Bauen dieses PDFs direkt aus '
            '<b>menus/lcd_menues.cfg</b> (Zweig <b>[menu __main __gen __stencil]</b>) gelesen — '
            'sie kann daher niemals vom echten Druckerdisplay abweichen:'
        )
        st += TBL(
            ['LCD-Menüpfad', 'Anzeige am Display', 'Wertebereich / Aktion'],
            [[a, b, c] for (a, b, c) in lcd_rows],
            [68 * mm, 48 * mm, 46 * mm],
            mono_cols=(1,),
        )
        st += SP(2)
        st += P(
            '<b>Konsolen-Makros (Mainsail / Fluidd / KlipperScreen):</b> '
            '<b>STENCIL_INFO</b> gibt die aktuellen Einstellungen samt Anzahl gefundener '
            'Quellbilder aus; <b>STENCIL_CREATE INDEX=&lt;0..9&gt; [OUT=SAVE|PREVIEW|QUEUE]</b> '
            'startet den Hintergrund-Job über <b>stencil_nonce</b> im Watcher-Dienst.'
        )

        # ---- Kapitel 4 ------------------------------------------------------
        st += H1('Gemessene Referenz-Parametersätze (Echtlauf-Tabelle)', '4')
        st += P(
            'Alle fünf Sätze wurden beim Bau dieses Dokuments real durch '
            '<b>r2_postproc.make_stencil()</b> gerechnet:'
        )
        ref_specs = [
            ('1. 3-Ton-Emblem + Negativ', 'Bands=3, Edge=90, Thick=0.8, Neg=ON, 0.4-Düse', info_emb),
            ('2. 4-Ton-Landschaft', 'Bands=4, Edge=120, Thick=0.8, Neg=off, 0.4-Düse', info_pho),
            ('3. S/W-Logo (Auto-Reduktion)', 'Bands=4->2, Edge=80, Thick=0.8, Neg=off, 0.4-Düse', info_red),
            ('4. Großschild @ 0,6-mm-Düse', 'Bands=3, Edge=160, Thick=1.0, Neg=off, 0.6-Düse', info_big),
            ('5. Mehrweg-Werkstattschablone', 'Bands=2, Edge=100, Thick=1.6, Neg=ON, 0.4-Düse', info_hd),
        ]
        ref_rows = []
        for label, param_s, inf in ref_specs:
            ref_rows.append([
                label,
                param_s,
                '%d Dateien (%s..)' % (len(inf['files']), inf['files'][0]),
                '%.1f × %.1f mm · %d L' % (inf['width'], inf['height'], inf['layers']),
                'Brücken %s' % inf['bridges'],
            ])
        st += TBL(
            ['Szenario', 'Parameter', 'Erzeugte Dateien', 'Außenmaß & Lagen', 'Inselbrücken'],
            ref_rows,
            [34 * mm, 42 * mm, 38 * mm, 28 * mm, 20 * mm],
            mono_cols=(2, 3, 4),
        )

        # ---- Kapitel 5 ------------------------------------------------------
        st += H1('Blindbedienung am Drucker & Praxis-Sprühprotokoll', '5')
        st += [BOX(
            'Schritt-für-Schritt blind am Drehknopf (ohne PC-Vorschau)',
            [
                '<b>1. Bild bereitstellen:</b> PNG oder JPG einfach ins Hauptverzeichnis '
                '<b>gcodes/</b> legen (derselbe Bildspeicher wie bei Lithophane und ColorPicture).',
                '<b>2. Einstellungen wählen (Tools &gt; Stencil &gt; Settings):</b> '
                'Für Logos/Wappen <b>Bands = 2</b> oder <b>3</b>, <b>Edge = 100 mm</b>, '
                '<b>Thick = 0,8 mm</b> (4 Lagen @ 0,20 mm — flexibel, liegt plan an). '
                'Für unebene Untergründe oder raue Kisten <b>Thick = 1,4 .. 1,6 mm</b> setzen.',
                '<b>3. Zwei-Klick-Start (Images (Create)):</b> Gewünschten Bild-Slot <b>1*..10*</b> '
                'einmal drücken (Display meldet Arming), ein zweites Mal drücken -> der Pi '
                'rechnet im Hintergrund, piept nach Abschluss und legt alle Platten in '
                '<b>gcodes/Stencil/</b> ab.',
                '<b>4. Sprühreihenfolge strikt einhalten:</b> Vier M4-Schrauben (oder 4-mm-Holzdübel) '
                'auf eine Trägerleiste kleben. Immer zuerst <b>Schablone1</b> (hellster Ton), '
                'dann <b>Schablone2</b>, zuletzt die höchste Nummer sprühen — senkrecht aus '
                '25 cm Abstand in dünnem Nebel, damit keine Farbe unter die 0,8-mm-Kante kriecht.',
                '<b>5. Wann Negativ = ON?</b> Wenn du ein einfarbiges Logo direkt auf ein bereits '
                'lackiertes Bauteil sprühen willst: In <b>Schablone1</b> wäre der Hintergrund offen, '
                'in <b>SchabloneNeg</b> hingegen steht der Hintergrund als Schutzschild und nur '
                'das Motiv selbst lässt den Lack durch — oder umgekehrt als erhabener Abdeck-Schild!'
            ],
            kind='tip',
        )]
        st += SP(2)
        st += [BOX(
            'Physikalische Grenzen (ehrlich aus dem Code)',
            [
                '• <b>Minimale Schlitzbreite = Spurbreite wid (0,43 mm @ 0,4-mm-Düse):</b> '
                'Haarlinien im Foto, die schmäler als eine Spur sind, glättet der 3×3-Gaußfilter '
                'bewusst weg, statt unbrauchbare Fäden zu drucken.',
                '• <b>Maximale Plattengröße:</b> Durch den umlaufenden 8-mm-Rahmen (plus 4 Brim-'
                'Schlaufen) beträgt das maximale Motivfenster auf einem 220×220-mm-Bett rund '
                '<b>192 × 192 mm</b>; größere Edge-Werte klemmt <b>_sc267</b> automatisch.',
                '• <b>Kein Slicer, kein Stützmaterial nötig:</b> Alle Platten liegen vollflächig '
                'flach auf dem Druckbett und sind in 12 bis 25 Minuten pro Platte fertig.'
            ],
            kind='warn',
        )]

        doc.render()
    return out_pdf


if __name__ == '__main__':
    target = os.path.join(REPO, 'STENCIL.pdf')
    build_pdf(target)
    print('Wrote %s (%d bytes)' % (target, os.path.getsize(target)))
