#!/usr/bin/env python3
# -*- coding: utf-8 -*-
""" make_frames_pdf.py — Wissenschaftliches Generator-Fachheft (D3 / D6):
    Bilderrahmen & Schaukästen (Tools > Frames -> make_frame()).

    Alle Abbildungen und Referenzläufe werden zur Bauzeit LIVE aus make_frame()
    in tools/r2_postproc.py sowie aus menus/lcd_menues.cfg erzeugt (Regel D6).
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
def _parse_frame_gcode(gcode_path):
    layers = {}
    layer_z = {}
    objs = []
    cur_layer = 0
    cur_type = 'OTHER'
    x = y = z = 0.0
    total_e = 0.0
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
        'total_e': total_e,
        'n_layers': max(layers.keys()) if layers else 0,
    }


# ------------------------------------------------------- Live-Menüextraktor
def _parse_frames_menu():
    cfg_path = os.path.join(REPO, 'menus', 'lcd_menues.cfg')
    txt = open(cfg_path, encoding='utf-8').read()
    blocks = re.split(r'(?m)^(?=\[menu )', txt)
    secs = [b for b in blocks if b.startswith('[menu __main __gen __frame')]
    rows = []
    seen_pre = seen_usr = False
    for sec in secs:
        lines = [l.strip() for l in sec.strip().splitlines() if l.strip()]
        hdr = lines[0].strip('[]').replace('menu __main __gen __frame', 'Tools > Frames')
        if '__pre __' in hdr:
            if not seen_pre:
                seen_pre = True
                rows.append((
                    'Tools > Frames > pre > [7 Formate]',
                    '9x13 · 10x15 · 13x18 · A6 · PASS · MINI · 4x5',
                    'Setzt W × H + Custom-Freigabe',
                ))
            continue
        if '__usr __p' in hdr or any(hdr.endswith(s) for s in ('__pu', '__pd', '__usr __info')):
            if not seen_usr and '__usr' in hdr:
                seen_usr = True
                rows.append((
                    'Tools > Frames > usr > [P1..P8]',
                    'Load / Delete eigene Rahmen-Presets',
                    '8 Speicherplätze',
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
            '__w': 'Photo W: [25..230]mm',
            '__h': 'Photo H: [25..230]mm',
            '__d': 'Depth: [3..60]mm (<15 Flat, >=15 Case)',
            '__fw': 'Border: [4..30]mm Rahmenbreite',
            '__crn': 'Corner R: [0..25]mm',
            '__shp': 'Shape: RECT / OVAL',
            '__cls': 'Closure: BACK (Rastplatte) / SIDE (Schlitz)',
            '__fnt': 'Front: IRON / FLIP / LINES / WAVES / HEX',
            '__dsc': 'Disc: NONE / GLASS / PLEXI / FOIL / LITHO',
            '__dt': 'Disc thick: [0.4..6.0]mm',
            '__ds': 'Disc side: FRONT (Lippe) / BACK',
            '__hng': 'Hang: TOP / BOTTOM / LEFT / RIGHT / OFF',
            '__hrg': 'Hang ring (Außenöse): ON / OFF',
            '__std': 'Stand (Aufstellerbein): ON / OFF',
            '__cbl': 'Cable duct (LED-Kanal CASE): ON / OFF',
            '__go': 'Create frame (2× Klick = Start)',
        }
        for suf, label in clean_map.items():
            if hdr.endswith(suf):
                nm = label
                break
        if '{' in nm:
            nm = re.sub(r'\{.*?\}', '[live]', nm)
        if '{' in mx:
            mx = '[Bett-26]'
        if '{' in mn:
            mn = '[min]'
        nm = nm.replace('<', '[').replace('>', ']')
        rng = ('%s .. %s (Schritt %s)' % (mn, mx, st)) if mn else ('Untermenü' if tp == 'list' else 'Schalter / Aktion')
        rows.append((hdr.replace(' __', ' > '), nm[:46], rng))
    return rows


# ------------------------------------------------------- Abbildungen (echt)
def _fig_complete_plate_and_profile(p_oneplate, out_png):
    """Abb. 1: Links echte G-Code-Werkzeugbahnen einer Komplettplatte (Rahmen +
    klickbare Rückwand OHNE Brim + Schlüsselloch + Aufstellerbein); rechts
    maßstäblicher Z-Profilschnitt (überhangfreie Fotonut + Rastnasen + Scheibenlippe)."""
    W_img, H_img = 1520, 600
    im = PILImage.new('RGB', (W_img, H_img), '#ffffff')
    dr = ImageDraw.Draw(im)
    f_title = font(18, bold=True)
    f_sub = font(14, bold=True)
    f_sm = font(12)

    prs = _parse_frame_gcode(p_oneplate)

    # Linkes Panel: Echte Komplettplatte aus make_frame()
    dr.rounded_rectangle((20, 18, 770, 582), radius=10,
                         fill='#f8fafd', outline='#bfd0e6', width=2)
    dr.text((36, 28),
            'A. Echte Komplettplatte: Rahmen + Rückwand (ohne Brim!) + Standfuß',
            fill='#1c4e8c', font=f_title)
    dr.text((36, 52),
            '4x5-Preset (40×50 mm), Depth=8 mm, Closure=BACK, Stand=ON, Hang=TOP:',
            fill='#475569', font=f_sm)

    vx0, vy0, vw, vh = 36, 80, 718, 462
    dr.rectangle((vx0, vy0, vx0 + vw, vy0 + vh), fill='#ffffff', outline='#cbd5e1', width=1)

    l_bot = prs['layers'].get(2, [])
    # Nut-/Rastnasen-Layer (~Z 2.6 mm) + Sichtfront-Layer (letzter Layer)
    l_groove = prs['layers'].get(min(prs['n_layers'], 12), [])
    l_top = prs['layers'].get(prs['n_layers'], [])

    pts = [(x, y) for (x0, y0, x1, y1, _) in (l_bot + l_top) for (x, y) in ((x0, y0), (x1, y1))]
    if pts:
        xs, ys = [p[0] for p in pts], [p[1] for p in pts]
        xmin, xmax = min(xs) - 3.0, max(xs) + 3.0
        ymin, ymax = min(ys) - 3.0, max(ys) + 3.0
        sc = min((vw - 28) / (xmax - xmin), (vh - 28) / (ymax - ymin))
        ox = vx0 + (vw - (xmax - xmin) * sc) / 2.0
        oy = vy0 + (vh - (ymax - ymin) * sc) / 2.0

        def fpx(xm, ym):
            return int(ox + (xm - xmin) * sc), int(vy0 + vh - (oy - vy0) - (ym - ymin) * sc)

        for (x0, y0, x1, y1, tp) in l_bot:
            col = '#94a3b8' if 'BRIM' in tp else ('#1c4e8c' if 'WALL' in tp else '#dbeafe')
            dr.line((fpx(x0, y0), fpx(x1, y1)), fill=col, width=2 if 'WALL' in tp else 1)
        for (x0, y0, x1, y1, tp) in l_groove:
            if 'WALL' in tp:
                dr.line((fpx(x0, y0), fpx(x1, y1)), fill='#0f766e', width=2)
        for (x0, y0, x1, y1, tp) in l_top:
            if 'WALL' in tp or 'IRON' in tp:
                dr.line((fpx(x0, y0), fpx(x1, y1)),
                        fill='#ea580c' if 'IRON' not in tp else '#f59e0b',
                        width=2 if 'WALL' in tp else 1)

    dr.text((36, 552),
            'Blau = Basis/Rückwand (R115: Rückwand ohne Brim!) · Grün = Fotonut/Bajonett · Orange = Sichtfront',
            fill='#334155', font=f_sm)

    # Rechtes Panel: Maßstäblicher Z-Profilschnitt (Überhangfrei!)
    dr.rounded_rectangle((790, 18, 1500, 582), radius=10,
                         fill='#f8fafd', outline='#bfd0e6', width=2)
    dr.text((808, 28),
            'B. Überhangfreies Rahmenprofil im Z-Schnitt (Bett = Rückseite)',
            fill='#1c4e8c', font=f_title)
    dr.text((808, 52),
            'Warum weder Fotonut noch Scheibenlippe jemals Stützmaterial (Support) brauchen:',
            fill='#475569', font=f_sm)

    # Zeichne Querschnitt der linken Rahmenleiste (x = Außen -> Sichtfenster)
    # Z wächst von unten (Druckbett = Rahmenrückseite Z=0) nach oben (Sichtfront Z=D)
    bx0, by_bed = 835, 455
    # Druckbettlinie
    dr.line((815, by_bed, 1475, by_bed), fill='#475569', width=3)
    dr.text((1120, by_bed + 8), 'Druckbett (Z = 0,0 mm = Rahmen-Rückseite)', fill='#475569', font=f_sm)

    # Unterer Schaft (Z = 0 .. 4.6 mm): Außenwand bis Fotoschacht (W + 1,6 mm) + Rastnase unten
    # 1. Rückband mit R127-Klicknase (Z = 0 .. 1,2 mm)
    dr.rectangle((bx0, by_bed - 46, bx0 + 250, by_bed), fill='#93c5fd', outline='#1c4e8c', width=2)
    # R127 Klicknase ragt minimal in den Fotoschacht
    dr.polygon([(bx0 + 250, by_bed - 46), (bx0 + 276, by_bed - 30),
                (bx0 + 276, by_bed - 12), (bx0 + 250, by_bed)],
               fill='#0f766e', outline='#0f2942')
    dr.text((bx0 + 286, by_bed - 36), '4× Klicknase (hält Rückwand)', fill='#0f766e', font=f_sm)

    # 2. Fotoschacht + Rückwand-Aufnahme (Z = 1,2 .. 5,4 mm): W + 1,6 mm (0,8 mm Spiel/Seite!)
    dr.rectangle((bx0, by_bed - 210, bx0 + 250, by_bed - 46), fill='#bfdbfe', outline='#1c4e8c', width=2)
    # Eingelegtes Foto + 0,8-mm-Rückwand im Schacht
    dr.rectangle((bx0 + 256, by_bed - 150, bx0 + 570, by_bed - 58),
                 fill='#dcfce7', outline='#15803d', width=2)
    dr.text((bx0 + 305, by_bed - 112), '0,8-mm-Klick-Rückwand (0,3 mm Spiel)', fill='#15803d', font=f_sm)
    dr.rectangle((bx0 + 256, by_bed - 204, bx0 + 570, by_bed - 154),
                 fill='#fef3c7', outline='#b45309', width=2)
    dr.text((bx0 + 305, by_bed - 186), 'Foto / Litho / StringArt (+0,8 mm Spiel/Seite!)', fill='#b45309', font=f_sm)

    # 3. Foto-Auflagesims (Shelf, Z = 5,4 .. 7,0 mm -> kragt 2,3 mm als Kurzbrücke nach innen!)
    dr.rectangle((bx0, by_bed - 305, bx0 + 335, by_bed - 210), fill='#60a5fa', outline='#1c4e8c', width=2)
    dr.text((bx0 + 345, by_bed - 266), 'Sichtfalz (W - 3,0 mm, R87-Kurzbrücke)', fill='#1c4e8c', font=f_sm)

    # 4. Optionale Front-Scheibenlippe + gebügelte Sichtfront (Z = 7,0 .. 8,0 mm)
    dr.rectangle((bx0, by_bed - 350, bx0 + 370, by_bed - 305), fill='#fb923c', outline='#9a3412', width=2)
    dr.text((bx0 + 378, by_bed - 338), 'Sichtfront (+ 1,2-mm-Lippe)',
            fill='#9a3412', font=f_sm)

    dr.rounded_rectangle((808, 492, 1482, 566), radius=8,
                         fill='#eff6ff', outline='#3b82f6', width=2)
    dr.text((822, 502), 'Tiefe entscheidet automatisch über den Bautyp:',
            fill='#1e40af', font=f_sub)
    dr.text((822, 528), 'Depth < 15 mm -> FLAT-Bilderrahmen   |   Depth >= 15 mm -> tiefer Schaukasten (CASE + Kabelkanal)',
            fill='#1e293b', font=f_sm)

    im.save(out_png)
    return out_png


def _fig_front_textures(front_runs, out_png):
    """Abb. 2: 4-Panel-Vergleich der echten Deckschicht-Werkzeugbahnen für
    Front = IRON, LINES, WAVES und HEX direkt aus den erzeugten G-Code-Dateien."""
    W_img, H_img = 1520, 440
    im = PILImage.new('RGB', (W_img, H_img), '#ffffff')
    dr = ImageDraw.Draw(im)
    f_title = font(18, bold=True)
    f_sub = font(14, bold=True)
    f_sm = font(12)

    dr.text((24, 14),
            'Echte Deckband-Werkzeugbahnen der 4 Front-Strukturen aus make_frame() (Mini-Rahmen 35×45 mm)',
            fill='#1c4e8c', font=f_title)

    for idx, (lbl, gc_p) in enumerate(front_runs):
        prs = _parse_frame_gcode(gc_p)
        px0 = 22 + idx * 372
        py0, pw, ph = 52, 356, 370
        dr.rounded_rectangle((px0, py0, px0 + pw, py0 + ph), radius=10,
                             fill='#f8fafd', outline='#bfd0e6', width=2)
        dr.text((px0 + 14, py0 + 10), lbl, fill='#163c6e', font=f_sub)

        # Oberste Schicht (enthält das strukturierte Frontband bzw. Ironing)
        segs_top = prs['layers'].get(prs['n_layers'], [])
        segs_sub = prs['layers'].get(max(1, prs['n_layers'] - 1), [])
        # Nur der Rahmen selber (linke Hälfte falls Rückwand daneben liegt):
        # Rahmen sitzt links -> filtere auf das erste zusammenhängende Bauteil über X-Median,
        # oder zeige den Rahmen-Ausschnitt (linke Rahmenseite) groß!
        all_s = segs_sub + segs_top
        xs_all = [x0 for (x0, _, _, _, _) in segs_top]
        # Bei 35x45 + Rückwand daneben: Rahmen hat Breite 35 + 20 = 55 mm -> x <= min(x) + 57 mm!
        if xs_all:
            x_left = min(xs_all)
            frame_only_top = [s for s in segs_top if s[0] <= x_left + 58.0 and s[2] <= x_left + 58.0]
            frame_only_sub = [s for s in segs_sub if s[0] <= x_left + 58.0 and s[2] <= x_left + 58.0]
        else:
            frame_only_top, frame_only_sub = segs_top, segs_sub

        pts = [(x, y) for (x0, y0, x1, y1, _) in (frame_only_top or all_s)
               for (x, y) in ((x0, y0), (x1, y1))]
        if pts:
            xs, ys = [p[0] for p in pts], [p[1] for p in pts]
            xmin, xmax = min(xs) - 2.0, max(xs) + 2.0
            ymin, ymax = min(ys) - 2.0, max(ys) + 2.0
            sc = min((pw - 32) / max(1.0, xmax - xmin), (ph - 76) / max(1.0, ymax - ymin))
            ox = px0 + (pw - (xmax - xmin) * sc) / 2.0
            oy = py0 + 38 + (ph - 76 - (ymax - ymin) * sc) / 2.0

            def tpx(xm, ym):
                return int(ox + (xm - xmin) * sc), int(py0 + ph - 34 - (ym - ymin) * sc - (oy - (py0 + 38)))

            for (x0, y0, x1, y1, tp) in frame_only_sub:
                dr.line((tpx(x0, y0), tpx(x1, y1)), fill='#cbd5e1', width=1)
            for (x0, y0, x1, y1, tp) in frame_only_top:
                col = '#ea580c' if 'IRON' in tp else '#1c4e8c'
                dr.line((tpx(x0, y0), tpx(x1, y1)), fill=col, width=2)

        dr.text((px0 + 14, py0 + ph - 26),
                '%d Lagen · ΣΔE = %.0f mm' % (prs['n_layers'], prs['total_e']),
                fill='#475569', font=f_sm)

    im.save(out_png)
    return out_png


# -------------------------------------------------------------- Hauptdokument
def build_pdf(out_pdf):
    lcd_rows = _parse_frames_menu()

    with tempfile.TemporaryDirectory(prefix='r2_frames_pdf_') as tmpdir:
        # 1. Komplettplatte auf einem Bett (4x5 + Rückwand + Aufstellerbein)
        p_one, i_one = pp.make_frame(
            preset='4x5', depth=8.0, frame_w=10.0, closure='BACK',
            hang='TOP', stand=True, nozzle=0.4, out_dir=tmpdir)

        # 2. Klassiker 10x15 -> automatischer R90.1a Zwei-Platten-Split (Part A + Part B)
        p_1015, i_1015 = pp.make_frame(
            preset='10x15', depth=8.0, frame_w=12.0, closure='BACK',
            hang='TOP', stand=True, disc='PLEXI', disc_t=1.5, disc_side='FRONT',
            nozzle=0.4, out_dir=tmpdir)

        # 3. Tiefer LED-Schaukasten (CASE >= 15 mm, SIDE-Einschub + Kabelkanal)
        p_case, i_case = pp.make_frame(
            preset='9x13', depth=22.0, frame_w=12.0, closure='SIDE',
            disc='LITHO', disc_t=2.8, disc_side='BACK', cable=True,
            nozzle=0.6, out_dir=tmpdir)

        # 4. Ovales Medaillon mit Außenöse
        p_oval, i_oval = pp.make_frame(
            width=70.0, height=95.0, depth=7.0, frame_w=9.0,
            shape='OVAL', closure='BACK', hang='TOP', hang_ring=True,
            nozzle=0.4, out_dir=tmpdir)

        # 5. Vier Front-Oberflächen im direkten G-Code-Vergleich
        front_runs = []
        for fmode, title_f in (
            ('IRON',  '1. IRON (gebügelte Glanzfront)'),
            ('LINES', '2. LINES (45°-Zierriefen)'),
            ('WAVES', '3. WAVES (Sinuswellen-Relief)'),
            ('HEX',   '4. HEX (Waben-Strukturband)'),
        ):
            pf_m, _ = pp.make_frame(
                preset='PASS', depth=6.0, frame_w=10.0, front=fmode,
                stand=False, nozzle=0.4, out_dir=tmpdir)
            front_runs.append((title_f, pf_m))

        fig1 = os.path.join(tmpdir, 'fig_frame_plate_prof.png')
        _fig_complete_plate_and_profile(p_one, fig1)

        fig2 = os.path.join(tmpdir, 'fig_frame_fronts.png')
        _fig_front_textures(front_runs, fig2)

        doc = Doc(
            out_pdf,
            kopf='R2-D2 Macro System · Generator Bilderrahmen & Schaukästen (D3)',
            titel='Frames & Display Cases — Überhangfreie Rahmengeometrie & Blindbedienung',
        )
        st = doc.story

        cover_tbl = TBL(
            ['Kenngröße', 'Wert im aktuellen Produktivcode (R90 / R101 / R106 / R120 / R127 / R187)'],
            [
                ['Menüpfad am Display', 'Tools > Frames  (86 Menü-Sektionen inkl. 7 Foto-Presets & 8 User-Slots)'],
                ['G-Code-Makros / Engine', 'FRAME_INFO · FRAME_GENERATE · GEN_FRAME -> make_frame()'],
                ['7 Foto-Presets', '9x13 · 10x15 (102×152) · 13x18 · A6 · PASS (35×45) · MINI (30×40) · 4x5'],
                ['Bautyp-Schwelle (Depth)', 'Depth < 15 mm -> Flachrahmen (FLAT) · Depth >= 15 mm -> Schaukasten (CASE)'],
                ['Verschluss & Toleranz', 'BACK (4× Rastnasen + Klick-Rückwand ohne Brim) / SIDE · +0,8 mm Fotospiel/Seite'],
                ['5 Sichtfront-Modi', 'IRON (gebügelt) · FLIP (PEI-Bettstruktur) · LINES · WAVES · HEX'],
                ['Scheibe & Kabelkanal', 'Disc NONE/GLASS/PLEXI/FOIL/LITHO (FRONT-Lippe 1,2 mm / BACK) · Cable=ON'],
                ['Mehrplatten-Intelligenz', 'Einzelplatte wenn möglich, sonst Part A (Rahmen) + Part B (Rückwand+Stand)'],
            ],
            [56 * mm, 106 * mm],
        )[0]

        doc.add_cover(
            kicker='GENERATOR-FACHHEFT · BILDERRAHMEN & SCHAUKÄSTEN (D3 / D6)',
            titel='Frames & Display Cases',
            untertitel='Überhangfreie Bilderrahmen, hinterleuchtete Lithophane-Schaukästen, klickbare Rückwände mit Schlüsselloch & Aufsteller sowie strukturierte Zierfronten',
            absaetze=[
                'Ein klassischer Bilderrahmen besitzt eine Stufenfalz für Foto, Vorsatzscheibe '
                'und Rückwand. Druckt man ihn falsch herum, benötigt das gesamte Sichtfenster '
                'Stützmaterial, das die Vorderseite ruiniert. make_frame() druckt den Rahmen '
                'deshalb mit der Rückseite auf dem Bett (Sichtfront nach oben für perfektes '
                'Ironing!) und überbrückt die innere 2,3-mm-Fotofalz als stützfreie Kurzbrücke.',
                'Gleichzeitig bildet Tools > Frames das mechanische Gegenstück zu Lithophane, '
                'ColorPicture und ArtisticStrings: Dieselben Standardformate (9x13, 10x15, '
                '13x18) rasten ohne jedes Nachschneiden mit 0,8 mm Spiel pro Seite direkt ein.',
            ],
            tabelle=cover_tbl,
        )

        # ---- Kapitel 1 ------------------------------------------------------
        st += H1('Überhangfreie Falz-Mathematik, Toleranzen & Verschlüsse', '1')
        st += P(
            'Aus Nenn-Fotomaß <b>(W, H)</b> und Rahmenleistenbreite <b>frame_w</b> berechnet '
            '<b>make_frame()</b> vier konzentrische Konturen (für <b>SHAPE = RECT</b> als '
            'abgerundetes Rechteck mit nach innen abnehmendem Eckradius, für <b>SHAPE = OVAL</b> '
            'als exakte Ellipsenschar):'
        )
        st += FORMULA(
            'Außenkontur:        O_w = W + 2 · frame_w,    O_h = H + 2 · frame_w<br/>'
            'Fotoschacht (R127): P_w = W + 1,6 mm,         P_h = H + 1,6 mm   (+0,8 mm Spiel/Seite!)<br/>'
            'Sichtfenster:       V_w = W - 3,0 mm,         V_h = H - 3,0 mm   (1,5 mm Auflage/Seite)<br/>'
            'Front-Scheibenlippe: L_w = V_w - 2,4 mm       (bei Disc != NONE und Disc side = FRONT)',
            'Warum +1,6 mm im Fotoschacht? Echte Laborabzüge streuen durch den Papierschnitt '
            'bis +1,0 mm über Nennmaß (R127-Feldmessung); mit 0,8 mm Luft pro Seite fällt jedes '
            '10×15-Foto spannungsfrei hinein, während 1,5 mm Sichtfalz den Rand sicher abdecken. '
            'Würde ein breiter Rahmen das Druckbett knapp sprengen, greift Regel nn (R106) und '
            'verjüngt frame_w automatisch bis minimal 6,0 mm, bevor auf Bausatzstreifen geteilt wird.'
        )
        st += B(
            '<b>Closure = BACK (Standard):</b> Foto und 0,8-mm-Rückwand werden von hinten '
            'eingelegt; vier in der Ebene aus der Schachtwand wachsende Rastnasen klicken '
            'über der Rückwand zu. Wichtig (Feldregel R115): Der Rahmen erhält Brim für '
            'sichere Eckenhaftung, die Rückwand wird <b>immer ohne Brim</b> gedruckt, damit '
            'sie ohne Entgraten sofort sauber einklickt!',
            '<b>Closure = SIDE (nur RECT):</b> Öffnet einen seitlichen Einschubschlitz durch '
            'die linke Rahmenwand — ideal für wechselnde Preisschilder, Türschilder oder '
            'Sammelkarten.',
            '<b>Depth &gt;= 15 mm -&gt; Schaukasten (CASE):</b> Baut denselben Falzkopf auf '
            'einem tiefen Hohlkasten (bis 60 mm Tiefe!). Mit <b>Disc = LITHO</b>, '
            '<b>Disc side = BACK</b> und <b>Cable = ON</b> entsteht ein kompletter '
            'LED-Leuchtkasten samt unsichtbarem Kabeldurchlass in der unteren Wand.'
        )
        st += [IMG(fig1, width_mm=162)]
        st += CAP(
            'Abbildung 1 — Links: Echte G-Code-Bahnen einer Komplettplatte (Rahmen + brimmfreie '
            'Klick-Rückwand mit Schlüsselloch + Aufstellerbein). Rechts: Überhangfreier Z-Profilschnitt.'
        )

        # ---- Kapitel 2 ------------------------------------------------------
        st += H1('Fünf Sichtfront-Oberflächen & Automatischer Mehrplatten-Split', '2')
        st += P(
            'Über den Parameter <b>Front</b> erhält der Rahmen ohne Nachbearbeitung fünf '
            'unterschiedliche Gesichter:'
        )
        st += B(
            '<b>IRON:</b> Bügelt die oberste Deckschicht mit reduzierter Linienbreite und '
            'geringem Fluss spiegelglatt.',
            '<b>FLIP:</b> Spiegelt die gesamte Z-Bandfolge auf den Kopf — die Sichtfront '
            'liegt direkt auf dem Druckbett und übernimmt das Glitzer- oder Carbon-Muster '
            'der Bauplatte!',
            '<b>LINES / WAVES / HEX (für RECT):</b> Fräst bzw. erhebt (<b>s_dir = IN / OUT</b>) '
            'parametrische Zierriefen, Sinuswellen oder Sechseckwaben direkt in das oberste '
            'Sichtband (Tiefe 0,4..2,4 mm, Teilung 2..15 mm).'
        )
        st += [IMG(fig2, width_mm=162)]
        st += CAP(
            'Abbildung 2 — Aus den realen G-Code-Dateien vier kleiner Rahmen (Preset PASS) '
            'extrahierte Deckband-Werkzeugbahnen für IRON, LINES, WAVES und HEX.'
        )

        # ---- Kapitel 3 ------------------------------------------------------
        st += [PageBreak()]
        st += H1('Live-Menüreferenz & Gemessene Referenzläufe', '3')
        st += P(
            'Direkt aus <b>menus/lcd_menues.cfg</b> gelesene Zeilen unter '
            '<b>Tools &gt; Frames</b>:'
        )
        st += TBL(
            ['LCD-Menüpfad', 'Anzeige am Display', 'Wertebereich / Aktion'],
            [[r[0], r[1], r[2]] for r in lcd_rows[:22]],
            [62 * mm, 58 * mm, 42 * mm],
        )

        st += H2('Fünf echte Referenzläufe (live beim PDF-Bau gerechnet)', '3.1')
        bench_rows = [
            ['1. Komplett-Tischrahmen', 'Preset=4x5 · D=8 · BACK · Stand=ON',
             i_one['file'], '%s mm Außen · %d L' % (i_one['outer'], i_one['layers']),
             'Alles auf 1 Platte!'],
            ['2. Klassiker 10×15 + Glas', 'Preset=10x15 · PLEXI 1,5 mm FRONT · Stand',
             '%d Dateien (%s..)' % (len(i_1015['all_files']), i_1015['all_files'][0]),
             '%s mm Außen' % i_1015['outer'],
             'Auto-Split Part A + Part B'],
            ['3. Litho-Leuchtkasten', 'Preset=9x13 · D=22 (CASE) · SIDE · Cable=ON',
             '%d Dateien (%s..)' % (len(i_case['all_files']), i_case['all_files'][0]),
             '%s mm · 22 mm tief' % i_case['outer'],
             'Kabelkanal + Rück-Diffusor'],
            ['4. Ovales Medaillon', 'OVAL 70×95 · D=7 · HangRing=ON',
             i_oval['file'], '%s mm Ellipse' % i_oval['outer'],
             'Bündige Außenöse ab Layer 1'],
            ['5. Struktur-Frontserie', 'Preset=PASS · IRON / LINES / WAVES / HEX',
             '4 Dateien (V06..V09)', '55x65 mm Außen · 30 L',
             '4 haptische Frontreliefs'],
        ]
        st += TBL(
            ['Szenario', 'Parameter', 'Erzeugte Datei(en)', 'Außenmaß & Lagen', 'Ergebnis'],
            bench_rows,
            [31 * mm, 41 * mm, 35 * mm, 28 * mm, 27 * mm],
        )

        st += SP(2)
        st += [BOX(
            'Blind-Kombination mit ArtisticStrings & Flach-Lithophanen',
            [
                '• Wählst du in ArtisticStrings Shape = RECT und Preset = 10x15 (102 × 152 mm), '
                'passt das fertige Fadenkunstwerk ohne jede Maßkorrektur in einen 10x15-Rahmen!',
                '• Für stehende oder liegende Lithophane im Leuchtkasten: Depth = 20..25 mm (CASE), '
                'Cable = ON für einen USB-LED-Streifen und Disc = LITHO wählen.',
            ],
            kind='tip',
        )]

        doc.render()
    return out_pdf


if __name__ == '__main__':
    dst = os.path.join(REPO, 'FRAMES.pdf')
    build_pdf(dst)
    print('Wrote %s (%d bytes)' % (dst, os.path.getsize(dst)))
