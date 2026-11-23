#!/usr/bin/env python3
# -*- coding: utf-8 -*-
""" make_plotter_pdf.py — Wissenschaftliches Generator-Fachheft (D3 / D6):
    2D-Stift- & Filament-Plotter (Tools > Plotter -> plot_convert / text_convert / make_plot_cal).

    Alle Abbildungen und Referenzläufe werden zur Bauzeit LIVE aus make_plot_cal(),
    plot_convert() und text_convert() in tools/r2_postproc.py sowie aus
    menus/lcd_menues.cfg erzeugt (Regel D6). Versionsstempel aus r2_version (r165).
"""
import math
import os
import re
import struct
import sys
import tempfile
import zlib

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


# ------------------------------------------------------- Plot-G-Code-Parser
def _parse_plot_gcode(gcode_path):
    """Liest echte Stift-/Filament-Plot-G-Codes (_PLOT_START .. _PLOT_END):
    trennt Zeichenzüge (z <= z_dn + 0.05), Stipple-Punkte (kurzer Dip ohne XY)
    und Leerfahrten (G0 auf z_up)."""
    strokes = []
    travels = []
    dots = []
    x = y = 0.0
    z = 5.0
    pen_down_xy = None
    cur_poly = []
    extrude_sum = 0.0

    with open(gcode_path, encoding='utf-8', errors='replace') as fh:
        for raw in fh:
            s = raw.split(';', 1)[0].strip()
            if not (s.startswith('G0 ') or s.startswith('G1 ')):
                continue
            cmd = s[:2]
            nx, ny, nz = x, y, z
            has_xy = False
            has_z = False
            de = 0.0
            for tok in s.split()[1:]:
                c = tok[0]
                try:
                    val = float(tok[1:])
                except ValueError:
                    continue
                if c == 'X':
                    nx = val
                    has_xy = True
                elif c == 'Y':
                    ny = val
                    has_xy = True
                elif c == 'Z':
                    nz = val
                    has_z = True
                elif c == 'E':
                    de = max(0.0, val)
            extrude_sum += de

            if has_z and not has_xy:
                if nz < 1.0 and z >= 1.0:
                    # Stift senkt sich auf Papier
                    pen_down_xy = (nx, ny)
                    cur_poly = [(nx, ny)]
                elif nz >= 1.0 and z < 1.0:
                    # Stift hebt ab
                    if len(cur_poly) >= 2:
                        strokes.append(cur_poly)
                    elif pen_down_xy is not None:
                        dots.append(pen_down_xy)
                    cur_poly = []
                    pen_down_xy = None
            elif has_xy:
                if z < 1.0 and cmd == 'G1':
                    if not cur_poly:
                        cur_poly = [(x, y)]
                    cur_poly.append((nx, ny))
                else:
                    if math.hypot(nx - x, ny - y) > 0.2:
                        travels.append(((x, y), (nx, ny)))
            x, y, z = nx, ny, nz

    if len(cur_poly) >= 2:
        strokes.append(cur_poly)
    return {
        'strokes': strokes,
        'dots': dots,
        'travels': travels,
        'extrude_sum': extrude_sum,
    }


def _make_compass_rose_png(path):
    """Zeichnet ein kontrastreiches Kompass-/Zahnrad-Motiv (160×160 px) auf
    hellem Papierhintergrund für den echten plot_convert()-Vergleich."""
    w, h = 160, 160
    im = PILImage.new('RGB', (w, h), (250, 250, 250))
    dr = ImageDraw.Draw(im)
    cx, cy = 80, 80
    dr.ellipse((18, 18, 142, 142), outline=(25, 25, 25), width=6)
    dr.ellipse((34, 34, 126, 126), outline=(95, 95, 95), width=3)
    # 4 Hauptspitzen des Kompasssterns
    pts_n = [(cx, 10), (cx + 14, cy - 14), (cx, cy), (cx - 14, cy - 14)]
    pts_s = [(cx, 150), (cx + 14, cy + 14), (cx, cy), (cx - 14, cy + 14)]
    pts_e = [(150, cy), (cx + 14, cy - 14), (cx, cy), (cx + 14, cy + 14)]
    pts_w = [(10, cy), (cx - 14, cy - 14), (cx, cy), (cx - 14, cy + 14)]
    for poly, col in ((pts_n, (20, 20, 20)), (pts_s, (80, 80, 80)),
                      (pts_e, (20, 20, 20)), (pts_w, (80, 80, 80))):
        dr.polygon(poly, fill=col)
    dr.ellipse((cx - 9, cy - 9, cx + 9, cy + 9), fill=(250, 250, 250), outline=(20, 20, 20), width=3)
    im.save(path)
    return path


def _make_sample_svg(path):
    """Kleines Vektor-SVG mit Kubik-Bezier-Blatt & Rahmen für plot_convert()."""
    svg = '''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100">
  <rect x="6" y="6" width="88" height="88" fill="none" stroke="black" stroke-width="2"/>
  <path d="M 20 80 C 20 30, 65 20, 82 18 C 80 35, 70 80, 20 80 Z" fill="none" stroke="black"/>
  <path d="M 20 80 Q 50 50 82 18" fill="none" stroke="black"/>
</svg>'''
    with open(path, 'w', encoding='utf-8') as f:
        f.write(svg)
    return path


# ------------------------------------------------------- Live-Menüextraktor
def _parse_plot_menu():
    cfg_path = os.path.join(REPO, 'menus', 'lcd_menues.cfg')
    txt = open(cfg_path, encoding='utf-8').read()
    blocks = re.split(r'(?m)^(?=\[menu )', txt)
    secs = [b for b in blocks if b.startswith('[menu __main __gen __plot')]
    rows = []
    seen_ch = False
    for sec in secs:
        lines = [l.strip() for l in sec.strip().splitlines() if l.strip()]
        hdr = lines[0].strip('[]').replace('menu __main __gen __plot', 'Tools > Plotter')
        if any(k in hdr for k in ('__tnm __az __', '__tnm __09 __', '__tnm __sym __')):
            if not seen_ch:
                seen_ch = True
                rows.append((
                    'Tools > Plotter > tnm > [A-Z/0-9]',
                    'Drehrad-Dateiname für Text-Plot (.txt)',
                    'Klick hängt Zeichen an',
                ))
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
            '__mod': 'Mode: DRAW (Linien) / STIPPLE (Punkte)',
            '__ext': 'Tool: PEN (Stift kalt) / FILAMENT (Düse)',
            '__sz': 'Plot size: [30..220]mm (lange Seite)',
            '__spd': 'Draw speed: [10..120]mm/s',
            '__trv': 'Travel speed: [20..80]mm/s (gekappt)',
            '__zdn': 'Pen Z down: [-2.0..10.0]mm',
            '__zup': 'Pen Z up (Hop): [0.5..15.0]mm',
            '__oz': 'Z offset (Feinjustage): [-5..+5]mm',
            '__ox': 'X shift (Stifthalter-Versatz): mm',
            '__oy': 'Y shift (Stifthalter-Versatz): mm',
            '__fz': 'Filament Z: [0.10..0.40]mm',
            '__ac': 'Auto-contrast (Otsu): ON / OFF',
            '__inv': 'Polarity: AUTO / NORMAL / INVERT',
            '__tsz': 'Text cap size: [6..20]mm',
            '__tfn': 'Text font: SMOOTH..PLATE (8 Schriften)',
            '__frm': 'Dry frame (PLT_FRAME zeigt Papiergrenzen)',
            '__cal': 'Calibration plot (100×140 mm Testbogen)',
            '__sts': 'Status plot (Drucker-Report zeichnen)',
        }
        for suf, label in clean_map.items():
            if hdr.endswith(suf):
                nm = label
                break
        if '{' in nm:
            nm = re.sub(r'\{.*?\}', '[live]', nm)
        nm = nm.replace('<', '[').replace('>', ']')
        rng = ('%s .. %s (Schritt %s)' % (mn, mx, st)) if mn else ('Untermenü' if tp == 'list' else 'Schalter / Aktion')
        rows.append((hdr.replace(' __', ' > '), nm[:46], rng))
    return rows


# ------------------------------------------------------- Abbildungen (echt)
def _fig_cal_and_modes(p_cal, p_draw, p_stipple, out_png):
    """Abb. 1: Links der echte 100×140-mm-Kalibrierbogen aus make_plot_cal()
    (Offset-Rahmen, 0,5-mm-Paare, konzentrische Kreise + 63 Stipple-Punkte);
    rechts echter Vergleich plot_convert() Mode=0 (Schraffur) vs. Mode=1 (Stipple)."""
    W_img, H_img = 1520, 600
    im = PILImage.new('RGB', (W_img, H_img), '#ffffff')
    dr = ImageDraw.Draw(im)
    f_title = font(18, bold=True)
    f_sub = font(14, bold=True)
    f_sm = font(12)

    # Linkes Panel: Echter Kalibrierbogen V01_PlotCal.gcode
    dr.rounded_rectangle((20, 18, 630, 582), radius=10,
                         fill='#f8fafd', outline='#bfd0e6', width=2)
    dr.text((36, 28),
            'A. Echter Kalibrierbogen (make_plot_cal, 100×140 mm)',
            fill='#1c4e8c', font=f_title)
    dr.text((36, 52),
            '27 Linien-Prüfzüge (Blau) + 63 Stipple-Punkte im 10-mm-Raster (Orange):',
            fill='#475569', font=f_sm)

    prs_c = _parse_plot_gcode(p_cal)
    cx0, cy0, cw, ch = 56, 82, 538, 462
    dr.rectangle((cx0, cy0, cx0 + cw, cy0 + ch), fill='#ffffff', outline='#cbd5e1', width=1)
    sc = min((cw - 40) / 100.0, (ch - 32) / 140.0)
    ox = cx0 + (cw - 100.0 * sc) / 2.0
    oy = cy0 + (ch - 140.0 * sc) / 2.0

    def cpx(xm, ym):
        return int(ox + xm * sc), int(cy0 + ch - (oy - cy0) - ym * sc)

    for poly in prs_c['strokes']:
        for k in range(len(poly) - 1):
            dr.line((cpx(*poly[k]), cpx(*poly[k + 1])), fill='#1c4e8c', width=2)
    for dx, dy in prs_c['dots']:
        px, py = cpx(dx, dy)
        dr.ellipse((px - 3, py - 3, px + 3, py + 3), fill='#ea580c')

    dr.text((36, 553),
            'Oben: H/V/45°, 0,5-mm-Doppelspuren & Kreise · Unten: 9×7 Stipple-Punktraster',
            fill='#334155', font=f_sm)

    # Rechtes Panel: plot_convert() Mode 0 (Draw) vs. Mode 1 (Stipple)
    dr.rounded_rectangle((650, 18, 1500, 582), radius=10,
                         fill='#f8fafd', outline='#bfd0e6', width=2)
    dr.text((668, 28),
            'B. Bild-Konverter plot_convert(): Boustrophedon-Linien vs. Stipple-Punkte',
            fill='#1c4e8c', font=f_title)
    dr.text((668, 52),
            'Otsu-Auto-Kontrast macht den Papierhintergrund reinweiß (0 Fahrten ins Leere!):',
            fill='#475569', font=f_sm)

    for idx, (gc_p, sub_t) in enumerate((
        (p_draw, 'Mode = 0 (DRAW: Boustrophedon-Schraffur)'),
        (p_stipple, 'Mode = 1 (STIPPLE: Punkt-Halbtonraster)'),
    )):
        prs_m = _parse_plot_gcode(gc_p)
        px0 = 668 + idx * 412
        py0, pw, ph = 82, 396, 462
        dr.rounded_rectangle((px0, py0, px0 + pw, py0 + ph), radius=8,
                             fill='#ffffff', outline='#cbd5e1', width=1)
        dr.text((px0 + 12, py0 + 10), sub_t, fill='#163c6e', font=f_sub)

        pts_m = ([p for poly in prs_m['strokes'] for p in poly] + list(prs_m['dots']))
        if pts_m:
            xs, ys = [p[0] for p in pts_m], [p[1] for p in pts_m]
            xmin, xmax = min(xs) - 2.0, max(xs) + 2.0
            ymin, ymax = min(ys) - 2.0, max(ys) + 2.0
            scm = min((pw - 32) / max(1.0, xmax - xmin), (ph - 76) / max(1.0, ymax - ymin))
            oxm = px0 + (pw - (xmax - xmin) * scm) / 2.0
            oym = py0 + 38 + (ph - 76 - (ymax - ymin) * scm) / 2.0

            def mpx(xm, ym):
                return int(oxm + (xm - xmin) * scm), int(py0 + ph - 34 - (ym - ymin) * scm - (oym - (py0 + 38)))

            for poly in prs_m['strokes']:
                for k in range(len(poly) - 1):
                    dr.line((mpx(*poly[k]), mpx(*poly[k + 1])), fill='#0f2942', width=2)
            for dx, dy in prs_m['dots']:
                qx, qy = mpx(dx, dy)
                dr.ellipse((qx - 2, qy - 2, qx + 2, qy + 2), fill='#0f2942')

        dr.text((px0 + 12, py0 + ph - 26),
                '%d Linienzüge · %d Stipple-Punkte' % (len(prs_m['strokes']), len(prs_m['dots'])),
                fill='#475569', font=f_sm)

    dr.text((668, 553),
            'Dateinamen-Steuerung möglich: motiv.c3.s50.png -> 3 Tonbänder, 0,50 mm Linienabstand!',
            fill='#334155', font=f_sm)

    im.save(out_png)
    return out_png


def _fig_text_and_svg_filament(p_txt, p_svg_fil, out_png):
    """Abb. 2: Links echte Text-Plot-Seite aus text_convert() (Vektorschrift +
    automatischer Seitenumbruch); rechts echter Vektor-SVG-Plot im FILAMENT-Modus
    inkl. Nahverbindungs-Regel d <= 2,2 mm."""
    W_img, H_img = 1520, 500
    im = PILImage.new('RGB', (W_img, H_img), '#ffffff')
    dr = ImageDraw.Draw(im)
    f_title = font(18, bold=True)
    f_sub = font(14, bold=True)
    f_sm = font(12)

    # Linkes Panel: text_convert() G-Code
    dr.rounded_rectangle((20, 18, 760, 482), radius=10,
                         fill='#f8fafd', outline='#bfd0e6', width=2)
    dr.text((36, 28),
            'A. Text-Plotter text_convert(): .txt -> Vektor-Buchstabenseite',
            fill='#1c4e8c', font=f_title)
    dr.text((36, 52),
            'Automatische Spalten-/Größenanpassung (_fit_text_page, >= 6,0 mm Versalhöhe):',
            fill='#475569', font=f_sm)

    prs_t = _parse_plot_gcode(p_txt)
    tx0, ty0, tw, th = 36, 80, 708, 366
    dr.rectangle((tx0, ty0, tx0 + tw, ty0 + th), fill='#ffffff', outline='#cbd5e1', width=1)
    pts_t = [p for poly in prs_t['strokes'] for p in poly]
    if pts_t:
        xs, ys = [p[0] for p in pts_t], [p[1] for p in pts_t]
        xmin, xmax = min(xs) - 2.0, max(xs) + 2.0
        ymin, ymax = min(ys) - 2.0, max(ys) + 2.0
        sct = min((tw - 32) / max(1.0, xmax - xmin), (th - 32) / max(1.0, ymax - ymin))
        oxt = tx0 + (tw - (xmax - xmin) * sct) / 2.0
        oyt = ty0 + (th - (ymax - ymin) * sct) / 2.0

        def tpx(xm, ym):
            return int(oxt + (xm - xmin) * sct), int(ty0 + th - (oyt - ty0) - (ym - ymin) * sct)

        for poly in prs_t['strokes']:
            for k in range(len(poly) - 1):
                dr.line((tpx(*poly[k]), tpx(*poly[k + 1])), fill='#1c4e8c', width=2)

    dr.text((36, 454),
            '%d Einzelstriche im G-Code · alle 8 R2-Strichschriften inkl. ÄÖÜß wählbar'
            % len(prs_t['strokes']),
            fill='#334155', font=f_sm)

    # Rechtes Panel: SVG -> FILAMENT-Plot + Kinematik-Vergleich
    dr.rounded_rectangle((780, 18, 1500, 482), radius=10,
                         fill='#f8fafd', outline='#bfd0e6', width=2)
    dr.text((798, 28),
            'B. SVG-Vektorplot im FILAMENT-Modus & Reise-Logik',
            fill='#1c4e8c', font=f_title)
    dr.text((798, 52),
            'Kein Stifthalter nötig: Extrude = 1 zeichnet hauchdünne 0,20-mm-Filamentspuren aufs warme Bett!',
            fill='#475569', font=f_sm)

    prs_s = _parse_plot_gcode(p_svg_fil)
    sx0, sy0, sw, sh = 798, 80, 330, 366
    dr.rectangle((sx0, sy0, sx0 + sw, sy0 + sh), fill='#ffffff', outline='#cbd5e1', width=1)
    pts_s = [p for poly in prs_s['strokes'] for p in poly]
    if pts_s:
        xs, ys = [p[0] for p in pts_s], [p[1] for p in pts_s]
        xmin, xmax = min(xs) - 3.0, max(xs) + 3.0
        ymin, ymax = min(ys) - 3.0, max(ys) + 3.0
        scs = min((sw - 28) / max(1.0, xmax - xmin), (sh - 48) / max(1.0, ymax - ymin))
        oxs = sx0 + (sw - (xmax - xmin) * scs) / 2.0
        oys = sy0 + 16 + (sh - 48 - (ymax - ymin) * scs) / 2.0

        def spx(xm, ym):
            return int(oxs + (xm - xmin) * scs), int(sy0 + sh - 28 - (ym - ymin) * scs - (oys - (sy0 + 16)))

        for (a, b) in prs_s['travels']:
            if (xmin <= a[0] <= xmax and ymin <= a[1] <= ymax
                    and xmin <= b[0] <= xmax and ymin <= b[1] <= ymax):
                dr.line((spx(*a), spx(*b)), fill='#fca5a5', width=1)
        for poly in prs_s['strokes']:
            for k in range(len(poly) - 1):
                dr.line((spx(*poly[k]), spx(*poly[k + 1])), fill='#0f766e', width=3)

    dr.text((sx0 + 10, sy0 + sh - 24),
            'ΣΔE = %.1f mm Filament' % prs_s['extrude_sum'],
            fill='#0f766e', font=f_sm)

    # Erklärbox rechts daneben
    rx0 = 1144
    rules = [
        ('PEN-Modus (kalt):', '#1c4e8c',
         '• Heizer bleiben komplett aus\n• Z_dn = plot_z_down + plot_off_z\n• Live-Babystepping = Stiftdruck!'),
        ('FILAMENT-Modus:', '#0f766e',
         '• Bett heizt + Purge-Linie (R149)\n• E/mm = fil_z · 0,65 / A_fil\n• d <= 2,2 mm: flach ohne Hop!\n• d > 2,2 mm: G10 + Z-Hop + G11'),
        ('Sicherheit (R75/R222):', '#b45309',
         '• R2PLOT-Polygon kapselt KAMP\n• Reisekappe <= 80 mm/s\n• _PLOT_END schaltet Heizer & M220 ab'),
    ]
    for idx, (rt, col_r, body_r) in enumerate(rules):
        ry = 80 + idx * 124
        dr.rounded_rectangle((rx0, ry, 1484, ry + 114), radius=8,
                             fill='#ffffff', outline=col_r, width=2)
        dr.text((rx0 + 10, ry + 8), rt, fill=col_r, font=f_sub)
        for li, bl in enumerate(body_r.split('\n')):
            dr.text((rx0 + 10, ry + 32 + li * 20), bl, fill='#334155', font=f_sm)

    im.save(out_png)
    return out_png


# -------------------------------------------------------------- Hauptdokument
def build_pdf(out_pdf):
    lcd_rows = _parse_plot_menu()

    with tempfile.TemporaryDirectory(prefix='r2_plotter_pdf_') as tmpdir:
        # 1. Kalibrierbogen (PEN)
        p_cal, i_cal = pp.make_plot_cal(out_dir=tmpdir)

        # 2. Rasterbild im Linienmodus (mode=0)
        rose_png = _make_compass_rose_png(os.path.join(tmpdir, 'Kompass.c2.s60.png'))
        vars_draw = os.path.join(tmpdir, 'vars_draw.cfg')
        with open(vars_draw, 'w', encoding='utf-8') as f:
            f.write("[Variables]\nplot_mode = 0\nplot_size = 110\nplot_autocontrast = 1\n")
        p_draw = os.path.join(tmpdir, 'V02_Plot_Kompass_Draw.gcode')
        n_pens_d, n_lines_d = pp.plot_convert(rose_png, var_path=vars_draw, out=p_draw)

        # 3. Rasterbild im Stipple-Punktmodus (mode=1)
        vars_stip = os.path.join(tmpdir, 'vars_stip.cfg')
        with open(vars_stip, 'w', encoding='utf-8') as f:
            f.write("[Variables]\nplot_mode = 1\nplot_size = 110\nplot_dot_gap = 2.0\nplot_autocontrast = 1\n")
        p_stip = os.path.join(tmpdir, 'V03_Plot_Kompass_Stipple.gcode')
        n_pens_s, n_lines_s = pp.plot_convert(
            rose_png.replace('.s60.', '.s180.') if False else rose_png,
            var_path=vars_stip, out=p_stip)

        # 4. Textdatei -> Vektor-Buchstabenseite
        txt_src = os.path.join(tmpdir, 'Werkstatt_Notiz.txt')
        with open(txt_src, 'w', encoding='utf-8') as f:
            f.write("R2-D2 DESIGN STUDIO\n-------------------\nStift- & Filament-Plotter\nPrueflauf mit Umlauten: ÄÖÜß\nKein PC, kein Slicer noetig!\n")
        p_txt = os.path.join(tmpdir, 'V04_Plot_Notiz.gcode')
        _, n_txt_lines, cap_sz = pp.text_convert(txt_src, out=p_txt, var_path=vars_draw)

        # 5. SVG-Vektordatei im FILAMENT-Modus (extrude=1)
        svg_src = _make_sample_svg(os.path.join(tmpdir, 'BlattLogo.svg'))
        vars_fil = os.path.join(tmpdir, 'vars_fil.cfg')
        with open(vars_fil, 'w', encoding='utf-8') as f:
            f.write("[Variables]\nplot_extrude = 1\nplot_fil_z = 0.20\nplot_size = 95\n")
        p_svg = os.path.join(tmpdir, 'V05_Plot_BlattLogo_Fil.gcode')
        _, n_lines_svg = pp.plot_convert(svg_src, var_path=vars_fil, out=p_svg)

        fig1 = os.path.join(tmpdir, 'fig_plot_cal_modes.png')
        _fig_cal_and_modes(p_cal, p_draw, p_stip, fig1)

        fig2 = os.path.join(tmpdir, 'fig_plot_txt_svg.png')
        _fig_text_and_svg_filament(p_txt, p_svg, fig2)

        doc = Doc(
            out_pdf,
            kopf='R2-D2 Macro System · Generator 2D-Stift- & Filament-Plotter (D3)',
            titel='Plotter (PEN & FILAMENT) — Bild-, Vektor-, Text- & Kalibrier-Plots',
        )
        st = doc.story

        cover_tbl = TBL(
            ['Kenngröße', 'Wert im aktuellen Produktivcode (R62 / R64 / R73 / R75 / R122 / R134 / R222)'],
            [
                ['Menüpfad am Display', 'Tools > Plotter  (163 Menü-Sektionen inkl. Live-Stiftjustage & Textname)'],
                ['G-Code-Makros / Engine', '_PLOT_START/_END · PLT_FRAME · PLOT_CAL · PLOT_TEXT · PLOT_STATUS'],
                ['Zwei Werkzeugmodi', 'PEN (kalt auf Papier, Babystep = Druck) · FILAMENT (0,20-mm-Spur auf Bett)'],
                ['Unterstützte Quelldateien', 'PNG · Baseline-JPEG · Vektor-SVG (Pfade/Bezier) · Vektor-PDF · Plain-TXT'],
                ['Bild-Intelligenz (R62/R64)', 'Rand-Polaritätserkennung (dunkles Board -> Invert) + Otsu-Weißschwelle'],
                ['Zwei Zeichenstile', 'Mode 0 = Boustrophedon-Schraffurlinien · Mode 1 = Stipple-Punktraster'],
                ['Reise- & Mesh-Schutz', 'Reisekappe 80 mm/s · Nahzug <= 2,2 mm ohne Hop · R2PLOT-Objektkapsel'],
                ['Ausgabeordner & Dateinamen', 'gcodes/Plot/Vnn_Plot_*.gcode · Vnn_PlotCal.gcode · StatusPlot'],
            ],
            [56 * mm, 106 * mm],
        )[0]

        doc.add_cover(
            kicker='GENERATOR-FACHHEFT · 2D-ZEICHEN- & PLOTSYSTEM (D3 / D6)',
            titel='Stift- & Filament-Plotter',
            untertitel='Fotos, SVGs, Vektor-PDFs, Textnotizen, Maschinen-Statusberichte und Kalibrierbögen mit Filzstift auf Papier oder als hauchfeine Filamentspur zeichnen',
            absaetze=[
                'Jeder 3D-Drucker ist zugleich ein hochpräziser XY-Zeichentisch: Mit einem '
                'angeklipsten Kugelschreiber, Fineliner oder Lackmarker zeichnet er Schaltpläne, '
                'Grußkarten, Etiketten und Kunstgrafiken auf Papier — und wer gar keinen '
                'Stifthalter besitzt, schaltet einfach auf Tool = FILAMENT um und zeichnet '
                'eine 0,20 mm feine Schmelzespur direkt auf die warme Bauplatte!',
                'Damit ein Plot niemals versehentlich wie ein 3D-Druck behandelt wird, nutzt '
                'das Plottersystem eine eigene Start-/End-Klammer (_PLOT_START / _PLOT_END), '
                'kapselt die Zeichenfläche für KAMP in das Objekt R2PLOT und stellt mit '
                'PLT_FRAME einen trockenen Rahmen-Vorlauf zum exakten Ausrichten des '
                'Papierbogens bereit.',
            ],
            tabelle=cover_tbl,
        )

        # ---- Kapitel 1 ------------------------------------------------------
        st += H1('Stift- vs. Filament-Kinematik & Otsu-Bildaufbereitung', '1')
        st += P(
            'Der gemeinsame G-Code-Schreiber <b>_plot_write()</b> und der Pfad-Emitter '
            '<b>_emit_plot()</b> trennen strikt zwischen kaltem Stiftbetrieb und '
            'heißem Filament-Zeichnen:'
        )
        st += FORMULA(
            'PEN-Zeichenhöhe:      z_dn = plot_z_down + plot_off_z   (Heizer aus, E = 0)<br/>'
            'FILAMENT-Zeichenhöhe: z_dn = plot_off_z + fil_z         (fil_z ∈ [0,10 .. 0,40] mm)<br/>'
            'FILAMENT-Extrusion:   E / mm = fil_z · 0,65 / A_fil     (≈ 0,054 mm/mm @ fil_z = 0,20)<br/>'
            'Otsu-Hintergrund:     Anteil(L &gt; T_otsu) &gt;= 55 %  -&gt;  Hintergrund wird reinweiß (255)',
            'Zwischen zwei Linienzügen prüft _travel() die Distanz d: Im FILAMENT-Modus bleibt '
            'die Düse für kurze Übergänge d &lt;= 2,2 mm (connect_mm) flach auf Zeichenhöhe ohne '
            'Retract — erst bei d &gt; 2,2 mm folgen G10, Z-Hop auf z_up, Eilgang (max. 80 mm/s) '
            'und G11. Das verhindert Fadenkleckse ebenso wie unnötige Z-Sprünge!'
        )
        st += B(
            '<b>Automatische Dunkel-Polarität (R64):</b> Bei Fotos von dunklen LCD-Schreibtafeln '
            'oder Schiefertafeln misst <b>plot_convert()</b> den Bildrand: Liegt der Rand-Mittelwert '
            'unter <b>110</b>, invertiert die Engine das Bild automatisch (helle Kreide wird zu Tinte!).',
            '<b>Dateinamen-Kurzcode ohne Menügang:</b> Wer eine Datei z. B. <b>stern.c3.s50.png</b> '
            'nennt, übergibt direkt im Namen <b>3 Tonbänder</b> (`.c3`, je eigener Stiftblock) und '
            '<b>0,50 mm Schraffurabstand</b> (`.s50`)!',
            '<b>R75-Mesh-Schutz & R222-Endabschaltung:</b> Das Objekt <b>R2PLOT</b> begrenzt ein '
            'etwaiges KAMP-Mesh strikt auf den Papierbereich (verhindert vollflächige Bett-Stalls); '
            'am Ende setzt <b>_PLOT_END</b> Heizer und Geschwindigkeitsfaktor <b>M220 S100</b> sauber zurück.'
        )
        st += [IMG(fig1, width_mm=162)]
        st += CAP(
            'Abbildung 1 — Links: Echter 100×140-mm-Kalibrierbogen aus make_plot_cal(). Rechts: '
            'Dasselbe Kompass-Motiv live durch plot_convert() im Linien-Modus (Mode 0) und '
            'Stipple-Punktmodus (Mode 1).'
        )

        # ---- Kapitel 2 ------------------------------------------------------
        st += H1('Text-Seitenlayout, Vektor-SVG/PDF & Trockenrahmen', '2')
        st += NUM(
            '<b>Text-Plotter (text_convert / PLOT_TEXT):</b> Wandelt jede <b>.txt</b>-Datei '
            '(bis 400 Zeilen) in eine sauber umbrochene Vektor-Buchstabenseite um. '
            '<b>_fit_text_page()</b> skaliert Schriftgrad (&gt;= 6,0 mm Versalhöhe) und '
            'Spaltenzahl automatisch auf die nutzbare Blattfläche; im FILAMENT-Modus werden '
            'die Striche über 0,65-mm-Parallelbahnen flächig gefüllt.',
            '<b>Vektor-Quellen (SVG & PDF):</b> <b>plot_convert()</b> versteht SVG-Grundformen '
            '(path M/L/H/V/C/S/Q/T/Z, rect, circle, ellipse, line, polyline, polygon) samt '
            'rekursiver Bezier-Glättung sowie unkomprimierte/Flate-komprimierte PDF-Vektorströme.',
            '<b>Kalibrierbogen (PLOT_CAL) & Statusbericht (PLOT_STATUS):</b> <b>PLOT_CAL</b> '
            'erzeugt den einseitigen 100×140-mm-Prüfbogen (Offset-Rahmen, 0,5-mm-Auflösungstest, '
            'Kreisrundheit, 63 Stipple-Punkte); <b>PLOT_STATUS</b> lässt den Drucker seinen '
            'eigenen Gesundheits- und Versionsbericht aufs Papier schreiben!'
        )
        st += [IMG(fig2, width_mm=162)]
        st += CAP(
            'Abbildung 2 — Links: Aus einer .txt-Notiz erzeugte Vektor-Schriftseite (text_convert). '
            'Rechts: Vektor-SVG im heißen FILAMENT-Modus samt Reisebahnen.'
        )

        # ---- Kapitel 3 ------------------------------------------------------
        st += [PageBreak()]
        st += H1('Live-Menüreferenz & Gemessene Referenzläufe', '3')
        st += P(
            'Direkt aus <b>menus/lcd_menues.cfg</b> gelesene Zeilen unter '
            '<b>Tools &gt; Plotter</b>:'
        )
        st += TBL(
            ['LCD-Menüpfad', 'Anzeige am Display', 'Wertebereich / Aktion'],
            [[r[0], r[1], r[2]] for r in lcd_rows[:22]],
            [62 * mm, 58 * mm, 42 * mm],
        )

        st += H2('Fünf echte Referenzläufe (live beim PDF-Bau gerechnet)', '3.1')
        bench_rows = [
            ['1. Kalibrierbogen', 'PLOT_CAL (PEN, 100×140 mm)',
             i_cal['file'], '%d Linien + %d Dots' % (i_cal['strokes'], i_cal['dots']),
             '%d G-Code-Zeilen' % i_cal['lines']],
            ['2. Bild -> Schraffur', 'Kompass.c2.s60.png · Mode=0 (DRAW)',
             os.path.basename(p_draw), '%d Tonbänder · 110 mm' % n_pens_d,
             '%d G-Code-Zeilen (Otsu aktiv)' % n_lines_d],
            ['3. Bild -> Stipple', 'Kompass.png · Mode=1 (STIPPLE, 2 mm)',
             os.path.basename(p_stip), '%d Punktband · 110 mm' % n_pens_s,
             '%d G-Code-Zeilen' % n_lines_s],
            ['4. Textnotiz -> Seite', 'Werkstatt_Notiz.txt · SMOOTH',
             os.path.basename(p_txt), '%d Textzeilen @ %.1f mm' % (n_txt_lines, cap_sz),
             '1 Seite inkl. ÄÖÜß'],
            ['5. SVG -> Filament-Plot', 'BlattLogo.svg · Extrude=1 · Z=0.20',
             os.path.basename(p_svg), '95 mm Vektorblatt',
             '%d Zeilen · warmes Bett + Purge' % n_lines_svg],
        ]
        st += TBL(
            ['Szenario', 'Parameter', 'Erzeugte Datei', 'Geometrie', 'Umfang / Modus'],
            bench_rows,
            [29 * mm, 41 * mm, 36 * mm, 28 * mm, 28 * mm],
        )

        st += SP(2)
        st += [BOX(
            'Blind-Workflow: In 60 Sekunden ohne Augenmaß zum perfekten Papier-Plot',
            [
                '1. Blatt mit zwei Magneten oder Malerkrepp auflegen -> Stift in Halter klemmen.',
                '2. Z-Nullung mit Papierstreifen: Pen Z down senken, bis die Spitze das Blatt gerade küsst.',
                '3. PLT_FRAME starten: Der Kopf fährt bei angehobenem Stift (z_up) einmal die 4 Ecken ab — '
                'sitzt das Rechteck mittig auf dem Blatt, Plot starten; während des Laufs regelt Live-Babystepping den Stiftdruck!',
            ],
            kind='tip',
        )]

        doc.render()
    return out_pdf


if __name__ == '__main__':
    dst = os.path.join(REPO, 'PLOTTER.pdf')
    build_pdf(dst)
    print('Wrote %s (%d bytes)' % (dst, os.path.getsize(dst)))
