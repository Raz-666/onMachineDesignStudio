#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""make_colorpic_pdf.py — Wissenschaftliche Methodik-, Farbpaletten- &
Blindbedienungs-PDF für den ColorPicture-Generator (MASTER-TODO D3 + D6,
R120 / R128 / R149 / R194, Tools > ColorPicture).

Verbindliche D6-Wahrheitsregel:
  * KEINE Fantasie-Grafiken. Jede Abbildung, jede Farbrampe und jede Filament-
    Kennzahl in diesem Heft wird zur Bauzeit aus echten Läufen von
    `r2_postproc.make_colorpic()` sowie aus `COLORPIC_PALETTE` und
    `COLORPIC_DEFAULTS` berechnet.
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


# ------------------------------------------------ Synthetisches 5-Ton-Motiv
def _make_poster_scene_png(path):
    """5-stufiges Poster-Motiv (Sonne/Wolke, Himmel, Berge, See, dunkle Tannen
    im Vordergrund) — ideal zur Messung geschachtelter Ω_k-Plateaus."""
    w, h = 200, 150
    im = PILImage.new('L', (w, h), 248)
    px = im.load()
    for y in range(h):
        for x in range(w):
            d_sun = math.hypot(x - 148, y - 36)
            if d_sun <= 20:
                px[x, y] = 250  # Band 0: gleißend weiß/gelb
            elif y < 56 + int(8 * math.sin(x / 24.0)):
                px[x, y] = 192  # Band 1: heller Himmel
            elif y < 92 - int(22 * abs(math.sin((x - 20) / 48.0))):
                px[x, y] = 132  # Band 2: Gebirgskette
            elif y < 118:
                px[x, y] = 78   # Band 3: dunkler Bergsee
            else:
                px[x, y] = 18   # Band 4: Silhouetten-Vordergrund
    # Markante Tannen-Spitzen im Vordergrund
    dr = ImageDraw.Draw(im)
    for tx in (34, 72, 166):
        dr.polygon([(tx, 76), (tx - 16, 146), (tx + 16, 146)], fill=16)
    im.save(path)
    return path


# ----------------------------------------- Echter G-Code-Parser für ColorPic
def _analyze_colorpic_gcode(gcode_path, n_bands, n_band_layers):
    """Parst ein erzeugtes ColorPic-G-Code-File schichtgenau:
      - XY-Segmente pro Band-Deckschicht (für echte Topographie-Zeichnung),
      - exakte Filamentlänge (mm) pro Farbrolle k,
      - M600-Positionen, Z-Werte nach M600 und Ironing-Schichten."""
    cap_layers = {(k + 1) * n_band_layers: k for k in range(n_bands)}
    band_segs = {k: [] for k in range(n_bands)}
    tower_segs = []
    brim_segs = []
    band_e_mm = [0.0] * n_bands
    m600_layers = []
    iron_layers = set()
    layer_z = {}

    cur_layer = 0
    cur_type = 'OTHER'
    cur_obj = ''
    x = y = z = e = 0.0
    erel = True

    with open(gcode_path, encoding='utf-8', errors='replace') as fh:
        for raw in fh:
            s = raw.strip()
            if s == 'LAYER_MARK':
                cur_layer += 1
                continue
            if s == 'M600' or s.startswith('M600 '):
                m600_layers.append(cur_layer)
                continue
            if s.startswith('APPLY_TYPE TYPE='):
                cur_type = s.split('TYPE=', 1)[1].split()[0].strip('"\'')
                if cur_type == 'IRONING':
                    iron_layers.add(cur_layer)
                continue
            if s.startswith('EXCLUDE_OBJECT_START NAME='):
                cur_obj = s.split('NAME=', 1)[1].split()[0].strip()
                continue
            if s.startswith('EXCLUDE_OBJECT_END'):
                cur_obj = ''
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
            nx, ny, nz = x, y, z
            ne = None
            for tok in code.split()[1:]:
                c = tok[:1]
                if c in 'XYZE':
                    try:
                        v = float(tok[1:])
                    except ValueError:
                        continue
                    if c == 'X':
                        nx = v
                    elif c == 'Y':
                        ny = v
                    elif c == 'Z':
                        nz = v
                    elif c == 'E':
                        ne = v
            if cur_layer >= 1 and abs(nz - z) > 1e-6:
                layer_z[cur_layer] = nz
            elif cur_layer >= 1 and cur_layer not in layer_z and nz > 0:
                layer_z[cur_layer] = nz

            de = 0.0
            if ne is not None:
                de = ne if erel else (ne - e)
                e = (e + ne) if erel else ne

            if de > 1e-6 and cur_layer >= 1:
                k_band = min(n_bands - 1, (cur_layer - 1) // max(1, n_band_layers))
                band_e_mm[k_band] += de
                if math.hypot(nx - x, ny - y) > 1e-6:
                    if cur_layer == 1 and cur_type == 'BRIM':
                        brim_segs.append((x, y, nx, ny))
                    elif cur_obj == 'PURGE_TOWER' and cur_layer == 2:
                        tower_segs.append((x, y, nx, ny))
                    elif cur_obj == 'COLORPIC' and cur_layer in cap_layers and cur_type != 'IRONING':
                        band_segs[cap_layers[cur_layer]].append((x, y, nx, ny, cur_type))
            x, y, z = nx, ny, nz

    return {
        'band_segs': band_segs,
        'tower_segs': tower_segs,
        'brim_segs': brim_segs,
        'band_e_mm': band_e_mm,
        'm600_layers': m600_layers,
        'iron_layers': sorted(iron_layers),
        'layer_z': layer_z,
    }


# -------------------------------------------------------- Live-LCD-Menüparser
def _parse_colorpic_menu():
    cfg_path = os.path.join(REPO, 'menus', 'lcd_menues.cfg')
    txt = open(cfg_path, encoding='utf-8').read()
    blocks = re.split(r'(?m)^(?=\[menu )', txt)
    secs = [b for b in blocks if b.startswith('[menu __main __gen __cpic')]
    rows = []
    seen_img = seen_pal = seen_usr = False
    for sec in secs:
        lines = [l.strip() for l in sec.strip().splitlines() if l.strip()]
        hdr = lines[0].strip('[]').replace('menu __main __gen __cpic', 'ColorPic')
        if re.search(r'__img __s\d+$', hdr):
            if not seen_img:
                seen_img = True
                rows.append(('ColorPic > Images > 1..10', '1*..10* [Bilddatei]', '2× Klick Start'))
            continue
        if '__set __clrs __' in hdr and not any(hdr.endswith(s) for s in ('__cur', '__band', '__rst')):
            if not seen_pal:
                seen_pal = True
                rows.append(('ColorPic > Band colors > [Farbe]', 'White .. Silver (14 Codes)', 'Setzt Farbe für Band #'))
            continue
        if '__usr __p' in hdr:
            if not seen_usr:
                seen_usr = True
                rows.append(('ColorPic > My presets > P1..P8', 'Load / Delete Preset', '8 Speicherplätze'))
            continue
        if any(hdr.endswith(suf) for suf in ('__pgi', '__pgp', '__pgn', '__pu', '__pd', '__usr __info')):
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
            '__set __wid': 'Width: [25..230]mm',
            '__set __bnd': 'Colors: [2..8] Bänder',
            '__set __bh': 'BandH: [0.4..3.0]mm',
            '__set __lh': 'Layer: [0.08..0.30]mm',
            '__set __clrs __cur': 'Now: [aktive CSV-Rampe]',
            '__set __clrs __band': 'Band #: [1..8] wählen',
            '__set __swp': 'Swap: ON (M600) / OFF',
            '__set __con': 'Contrast: ON / OFF',
            '__set __iro': 'Ironing: ON / OFF',
            '__set __brm': 'Brim: [0..10]x',
            '__usr __save': 'Save: P[n] speichern',
        }
        for suf, label in clean_map.items():
            if hdr.endswith(suf):
                nm = label
                break
        rng = ('%s .. %s (Schritt %s)' % (mn, mx, st)) if mn else ('Untermenü' if tp == 'list' else 'Schalter / Aktion')
        rows.append((hdr.replace(' __', ' > '), nm[:42], rng))
    return rows


def _rgb_hex(code, darken=1.0):
    _, r, g, b = pp.COLORPIC_PALETTE[code]
    ri = max(0, min(255, int(round(r * 255 * darken))))
    gi = max(0, min(255, int(round(g * 255 * darken))))
    bi = max(0, min(255, int(round(b * 255 * darken))))
    return '#%02x%02x%02x' % (ri, gi, bi)


# --------------------------------------------------------- D6-Echtlauf-Grafiken
def _fig_topography_and_timeline(info_4, parsed_4, out_png):
    """Abb. 1: Links echte übereinander gedruckte Werkzeugbahnen von Band 0..3
    (`WHT, CYA, BLU, BLK`) + `12×12-mm-PURGE_TOWER` + Brim; rechts gemessener
    16-Lagen-Z-Aufbau mit den 3 M600-Punkten, Ironing-Decklagen und Spulenbedarf."""
    W_img, H_img = 1520, 620
    im = PILImage.new('RGB', (W_img, H_img), '#ffffff')
    dr = ImageDraw.Draw(im)
    f_title = font(18, bold=True)
    f_sub = font(15, bold=True)
    f_lbl = font(14)
    f_sm = font(13)

    # Linkes Panel: Echte XY-Draufsicht (Auflicht-Topographie + Purge-Tower)
    dr.rounded_rectangle((22, 18, 790, 602), radius=10,
                         fill='#f8fafd', outline='#bfd0e6', width=2)
    dr.text((38, 30),
            'A. Echte XY-Bahnen (4 Bänder + Purge-Tower): Ω_0 ⊇ Ω_1 ⊇ Ω_2 ⊇ Ω_3',
            fill='#1c4e8c', font=f_title)
    dr.text((40, 58),
            'Jedes dunklere Band liegt zu 100 % auf dem darunterliegenden helleren Plateau (kein Druck in Luft!)',
            fill='#58595b', font=f_sm)

    all_pts = []
    for segs in parsed_4['band_segs'].values():
        for x1, y1, x2, y2, _ in segs:
            all_pts.extend([(x1, y1), (x2, y2)])
    for x1, y1, x2, y2 in parsed_4['tower_segs'] + parsed_4['brim_segs']:
        all_pts.extend([(x1, y1), (x2, y2)])
    xmin = min(p[0] for p in all_pts)
    xmax = max(p[0] for p in all_pts)
    ymin = min(p[1] for p in all_pts)
    ymax = max(p[1] for p in all_pts)

    avail_w, avail_h = 716, 456
    sc = min(avail_w / max(1e-6, xmax - xmin), avail_h / max(1e-6, ymax - ymin))
    ox = 48 + (avail_w - (xmax - xmin) * sc) / 2.0
    oy = 94 + (avail_h - (ymax - ymin) * sc) / 2.0

    def to_p(xm, ym):
        return (ox + (xm - xmin) * sc, oy + (ymax - ym) * sc)

    # Dunkler Bett-Kontrasthintergrund, damit Band 0 (WHT) klar sichtbar ist
    dr.rounded_rectangle((ox - 12, oy - 12,
                          ox + (xmax - xmin) * sc + 12,
                          oy + (ymax - ymin) * sc + 12),
                         radius=6, fill='#334155')

    # Brim
    for x1, y1, x2, y2 in parsed_4['brim_segs']:
        pa, pb = to_p(x1, y1), to_p(x2, y2)
        dr.line((pa[0], pa[1], pb[0], pb[1]), fill='#94a3b8', width=1)

    # Bänder 0 -> 3 von unten nach oben in ihren echten Palettenfarben
    cols4 = info_4['colors']
    for k in range(info_4['bands']):
        c_fill = _rgb_hex(cols4[k], darken=0.96)
        c_wall = _rgb_hex(cols4[k], darken=0.72) if cols4[k] != 'BLK' else '#050505'
        for x1, y1, x2, y2, tp in parsed_4['band_segs'][k]:
            pa, pb = to_p(x1, y1), to_p(x2, y2)
            dr.line((pa[0], pa[1], pb[0], pb[1]),
                    fill=c_wall if tp == 'WALL-OUTER' else c_fill,
                    width=2 if tp == 'WALL-OUTER' else 2)

    # Purge-Tower (12×12 mm, 15 mm Abstand)
    for x1, y1, x2, y2 in parsed_4['tower_segs']:
        pa, pb = to_p(x1, y1), to_p(x2, y2)
        dr.line((pa[0], pa[1], pb[0], pb[1]), fill='#fb923c', width=2)
    if parsed_4['tower_segs']:
        tx_m = min(s[0] for s in parsed_4['tower_segs'])
        ty_m = max(s[1] for s in parsed_4['tower_segs'])
        tp_lbl = to_p(tx_m, ty_m)
        dr.text((tp_lbl[0] - 32, tp_lbl[1] - 42), 'PURGE_TOWER\n12×12 (+15 mm)',
                fill='#fed7aa', font=f_sm)

    dr.text((42, 568),
            'Grau = 3× Brim · Rechts = automatischer 12×12-mm-Purge-Tower mit 15 mm Sonden-Freiraum',
            fill='#475569', font=f_sm)

    # Rechtes Panel: Schichtleiter, M600 + pen.set_z(z) & Filament pro Spule
    dr.rounded_rectangle((812, 18, 1498, 602), radius=10,
                         fill='#f8fafd', outline='#bfd0e6', width=2)
    dr.text((830, 30), 'B. 16-Lagen-Leiter, M600-Punkte & Spulenbedarf',
            fill='#1c4e8c', font=f_title)
    dr.text((832, 58),
            '4 Bänder × 4 Schichten @ 0,20 mm = 3,20 mm Gesamthöhe · 3× LED-geführter M600-Wechsel',
            fill='#58595b', font=f_sm)

    n_tot = info_4['layers']
    nb = info_4['band_layers']
    lx0, lx1 = 910, 1285
    y_bot, y_top = 450, 114
    lh_px = (y_bot - y_top) / float(n_tot)

    for li in range(1, n_tot + 1):
        k = (li - 1) // nb
        c_code = cols4[k]
        ya = y_bot - li * lh_px
        yb = y_bot - (li - 1) * lh_px
        # Geschachtelte Breite symbolisch proportional zum echten Band-E
        e_ratio = parsed_4['band_e_mm'][k] / max(1e-6, parsed_4['band_e_mm'][0])
        w_cur = int((lx1 - lx0) * (0.32 + 0.68 * e_ratio))
        xc = (lx0 + lx1) // 2
        dr.rectangle((xc - w_cur // 2, ya + 1, xc + w_cur // 2, yb - 1),
                     fill=_rgb_hex(c_code, 0.94), outline='#334155', width=1)
        if li in parsed_4['iron_layers']:
            dr.line((xc - w_cur // 2, ya + 1, xc + w_cur // 2, ya + 1),
                    fill='#e07b00', width=3)
        if li in parsed_4['m600_layers']:
            dr.line((836, yb, 1476, yb), fill='#c62828', width=2)
            dr.text((1296, yb - 17),
                    'L%d: M600 -> %s (Z=%.1f)' % (li, c_code, parsed_4['layer_z'].get(li, li * 0.2)),
                    fill='#c62828', font=f_sm)

    dr.text((836, 90), 'Z = 3,2 mm · Orange Oberkante = IRONING (15 % Fluss @ 0,45 mm)',
            fill='#b35c00', font=f_sm)

    # Spulen-Verbrauchstabelle unten rechts (echte mm + Gramm PLA @ 1,24 g/cm³)
    dr.text((836, 466), 'Echter Filamentbedarf je Farbrolle (1,75 mm PLA, ρ = 1,24 g/cm³):',
            fill='#163c6e', font=f_sub)
    fil_area_cm2 = math.pi * (0.175 / 2.0) ** 2  # ~0.02405 cm²
    for k, c_code in enumerate(cols4):
        yk = 496 + k * 24
        mm_used = parsed_4['band_e_mm'][k]
        grams = (mm_used / 10.0) * fil_area_cm2 * 1.24
        dr.rectangle((840, yk + 2, 864, yk + 18),
                     fill=_rgb_hex(c_code, 0.95), outline='#334155', width=1)
        dr.text((874, yk),
                'Band %d · %s (%-6s):  %6.1f mm Filament  (≈ %.2f g)'
                % (k + 1, c_code, pp.COLORPIC_PALETTE[c_code][0], mm_used, grams),
                fill='#222222', font=f_sm)

    im.save(out_png)
    return out_png


def _fig_palettes_and_ramps(out_png):
    """Abb. 2: Vollständige 14er-Farbpalette `COLORPIC_PALETTE` samt LED-RGB-Werten
    und allen 7 eingebauten Auto-Rampen `COLORPIC_DEFAULTS[2..8]` direkt aus
    `r2_postproc.py` gezeichnet."""
    W_img, H_img = 1520, 520
    im = PILImage.new('RGB', (W_img, H_img), '#ffffff')
    dr = ImageDraw.Draw(im)
    f_title = font(18, bold=True)
    f_sub = font(15, bold=True)
    f_lbl = font(14, bold=True)
    f_sm = font(13)

    # Linke Hälfte: 14 Palettencodes
    dr.rounded_rectangle((22, 18, 748, 502), radius=10,
                         fill='#f8fafd', outline='#bfd0e6', width=2)
    dr.text((38, 30), 'A. Die 14 Paletten-Codes (COLORPIC_PALETTE + LED-RGB)',
            fill='#1c4e8c', font=f_title)
    dr.text((40, 58),
            'Beim Wechsel blinkt die Hotend-LED abwechselnd in alter und neuer RGB-Farbe:',
            fill='#58595b', font=f_sm)

    codes = list(pp.COLORPIC_PALETTE.keys())
    for idx, code in enumerate(codes):
        col_i = idx % 2
        row_i = idx // 2
        bx = 42 + col_i * 346
        by = 92 + row_i * 56
        name, r, g, b = pp.COLORPIC_PALETTE[code]
        dr.rounded_rectangle((bx, by, bx + 54, by + 40), radius=6,
                             fill=_rgb_hex(code), outline='#334155', width=2)
        dr.text((bx + 66, by + 2), '%s — %s' % (code, name), fill='#163c6e', font=f_lbl)
        dr.text((bx + 66, by + 22), 'LED RGB (%.2f, %.2f, %.2f)' % (r, g, b),
                fill='#58595b', font=f_sm)

    # Rechte Hälfte: Die 7 Standard-Rampen für 2..8 Farben
    dr.rounded_rectangle((772, 18, 1498, 502), radius=10,
                         fill='#f8fafd', outline='#bfd0e6', width=2)
    dr.text((792, 30), 'B. Eingebaute Standard-Rampen COLORPIC_DEFAULTS[2..8]',
            fill='#1c4e8c', font=f_title)
    dr.text((792, 58),
            'Immer streng HELL -> DUNKEL geordnet (Band 1 = Grundplatte, letztes Band = Kontur):',
            fill='#58595b', font=f_sm)

    for idx, nb in enumerate(sorted(pp.COLORPIC_DEFAULTS.keys())):
        ry = 94 + idx * 56
        ramp = pp.COLORPIC_DEFAULTS[nb].split(',')
        dr.text((792, ry + 10), '%d Farben:' % nb, fill='#163c6e', font=f_sub)
        sx = 900
        sw = int(568 / len(ramp)) - 6
        for j, c_code in enumerate(ramp):
            xx = sx + j * (sw + 6)
            dr.rounded_rectangle((xx, ry, xx + sw, ry + 40), radius=6,
                                 fill=_rgb_hex(c_code), outline='#334155', width=2)
            txt_col = '#ffffff' if c_code in ('BLK', 'BLU', 'PUR', 'BRN', 'RED') else '#111111'
            dr.text((xx + max(6, sw // 2 - 18), ry + 11), c_code, fill=txt_col, font=f_lbl)

    im.save(out_png)
    return out_png


# -------------------------------------------------------------- Hauptdokument
def build_pdf(out_pdf):
    lcd_rows = _parse_colorpic_menu()

    with tempfile.TemporaryDirectory(prefix='r2_colorpic_pdf_') as tmpdir:
        src_img = _make_poster_scene_png(os.path.join(tmpdir, 'AlpenSee.png'))

        # 5 echte Referenzläufe von make_colorpic()
        p_4, i_4 = pp.make_colorpic(
            src_img, width_mm=80.0, layer_h=0.2, bands=4, band_h=0.8,
            ironing=True, swap=True, nozzle=0.4, out_dir=tmpdir)
        parsed_4 = _analyze_colorpic_gcode(p_4, n_bands=4, n_band_layers=4)

        p_2, i_2 = pp.make_colorpic(
            src_img, width_mm=90.0, layer_h=0.2, bands=2, band_h=0.6,
            colors='WHT,BLK', ironing=True, swap=True, nozzle=0.4, out_dir=tmpdir)
        parsed_2 = _analyze_colorpic_gcode(p_2, n_bands=2, n_band_layers=3)

        p_6, i_6 = pp.make_colorpic(
            src_img, width_mm=110.0, layer_h=0.2, bands=6, band_h=0.6,
            ironing=True, swap=True, nozzle=0.4, out_dir=tmpdir)
        parsed_6 = _analyze_colorpic_gcode(p_6, n_bands=6, n_band_layers=3)

        p_noswap, i_noswap = pp.make_colorpic(
            src_img, width_mm=80.0, layer_h=0.2, bands=4, band_h=0.8,
            ironing=False, swap=False, nozzle=0.4, out_dir=tmpdir)
        parsed_ns = _analyze_colorpic_gcode(p_noswap, n_bands=4, n_band_layers=4)

        p_warm, i_warm = pp.make_colorpic(
            src_img, width_mm=100.0, layer_h=0.16, bands=5, band_h=0.64,
            colors='WHT,GLD,ORG,BRN,BLK', ironing=True, swap=True,
            nozzle=0.4, out_dir=tmpdir)
        parsed_w = _analyze_colorpic_gcode(p_warm, n_bands=5, n_band_layers=4)

        fig1 = os.path.join(tmpdir, 'fig_cpic_topo.png')
        _fig_topography_and_timeline(i_4, parsed_4, fig1)

        fig2 = os.path.join(tmpdir, 'fig_cpic_palettes.png')
        _fig_palettes_and_ramps(fig2)

        doc = Doc(
            out_pdf,
            kopf='R2-D2 Macro System · Generator ColorPicture / Farbbild (D3)',
            titel='ColorPicture — Mehrfarbige Auflicht-Poster mit einem Extruder',
        )
        st = doc.story

        cover_tbl = TBL(
            ['Kenngröße', 'Wert im aktuellen Produktivcode (R120 / R128 / R149 / R194)'],
            [
                ['Menüpfad am Display', 'Tools > ColorPicture  (72 Menü-Sektionen inkl. 8 Presets P1..P8)'],
                ['G-Code-Makros / Engine', 'COLORPIC_CREATE · COLORPIC_SET_COLOR · GEN_COLORPIC -> make_colorpic()'],
                ['Farbbänder & Bandhöhe', 'Colors = 2 .. 8 Bänder (Default 4) · BandH = 0,4 .. 3,0 mm (Default 0,8 mm)'],
                ['Bildbreite & Spurgeometrie', 'Width = 25 .. 230 mm (Höhe folgt Seitenverhältnis) · wid = max(0,4, 1,08·Düse)'],
                ['Farbpalette & Auto-Rampen', '14 Drei-Buchstaben-Codes (WHT..SIL) + 7 fertige Rampen für 2..8 Farben'],
                ['Spulenwechsel & LED-Führung', '_COLORPIC_SWAP blinkt Alt->Neu-RGB + M600 + pen.set_z(z) + 12×12-Purge-Tower'],
                ['Decklagen-Veredelung', 'Ironing = ON bügelt jede Band-Deckschicht (cap) mit 15 % Fluss @ 0,45 mm'],
                ['Ausgabeordner & Dateiname', 'gcodes/ColorPic/Vnn_ColorPic_<Stamm>.gcode'],
            ],
            [56 * mm, 106 * mm],
        )[0]

        doc.add_cover(
            kicker='GENERATOR-FACHHEFT · BILD-ZU-GEOMETRIE-FAMILIE (D3 / D6)',
            titel='ColorPicture (Farbbild)',
            untertitel='Mehrfarbiger Auflicht-Posterdruck auf jedem Ein-Extruder-Drucker durch streng geschachtelte Luminanz-Plateaus, LED-geführte M600-Wechsel und Purge-Tower',
            absaetze=[
                'Während ein Lithophane erst vor einer Lichtquelle zum Leben erwacht, ist ein '
                'ColorPicture ein echtes, opakes Wandbild oder Schild im normalen Raumlicht — '
                'und zwar ohne MMU, ohne AMS und ohne Slicer auf einem ganz normalen '
                'Ein-Düsen-Drucker mit nur 1 bis 7 manuellen Spulenwechseln!',
                'Das Geheimnis hinter make_colorpic() (R120) ist eine topologische Teilmengen-'
                'Garantie: Das Bild wird in 2 bis 8 Helligkeitsbänder quantisiert und streng von '
                'HELL nach DUNKEL gestapelt. Da jedes dunklere Band eine echte Teilmenge aller '
                'darunterliegenden Bänder bildet, druckt niemals eine Bahn in die Luft, und an '
                'jedem Punkt (x, y) zeigt die oberste geglättete Deckschicht exakt ihre Zielfarbe.',
            ],
            tabelle=cover_tbl,
        )

        # ---- Kapitel 1 ------------------------------------------------------
        st += H1('Mathematik der geschachtelten Luminanz-Plateaus', '1')
        st += P(
            '<b>make_colorpic()</b> projiziert das Eingangsbild (PNG/JPG, RAM-sicher bis '
            '<b>max_dim = 768 px</b>) auf ein Zellgitter der Spurbreite '
            '<b>wid = max(0.40, nozzle · 1.08)</b> in Draufsicht-Orientierung '
            '(<b>mirror = False</b>, Bildoberkante hinten am Bett):'
        )
        st += FORMULA(
            'cols    = round(width_mm / wid),         rows = round(cols · h / w)<br/>'
            'LV[r,c] = min(B - 1, int(grid[r,c] · B + 0.5))   mit k ∈ {0..B-1}<br/>'
            'Ω_k     = {(r, c) | LV[r,c] &gt;= k}   =&gt;   Ω_0 ⊇ Ω_1 ⊇ ... ⊇ Ω_{B-1}<br/>'
            'n_band  = max(1, round(band_h / layer_h)),  TOTAL_LAYERS = B · n_band',
            'Teilmengen-Beweis: Da LV[r,c] >= 0 für jede Zelle gilt, ist Ω_0 die lückenlose '
            'Rechteck-Grundplatte. Für jedes k >= 1 gilt aus LV[r,c] >= k zwingend LV[r,c] >= k-1, '
            'also Ω_k ⊆ Ω_{k-1}: Jede einzelne Zelle von Band k ruht vollflächig auf Band k-1!'
        )
        st += SP(2)
        st += H2('RLE-Rechteckverschmelzung _blocks120(k) & Cap-Ironing', '1.1')
        st += P(
            'Würde man ein 200×150-Zellen-Raster Zelle für Zelle abfahren, entstünden zehntausende '
            'Mikro-Segmente, die die MCU in einen „Timer too close"-Engpass treiben. '
            'Deshalb zerlegt <b>_runs120(row)</b> jede Zeile von <b>Ω_k</b> in zusammenhängende '
            ' Horizontal-Intervalle <b>(c_a, c_b)</b>, und <b>_blocks120(k)</b> verschmilzt '
            'aufeinanderfolgende Zeilen mit identischem Run-Tupel zu maximalen Rechteckblöcken '
            '<b>(r_a, r_b, runs)</b>:'
        )
        st += B(
            'Jeder Rechteckblock erhält zuerst eine saubere <b>WALL-OUTER</b>-Umrissbahn '
            'und anschließend einen <b>45°/135°</b>-Vollhatch (<b>SURFACE-BOTTOM</b> auf Layer 1, '
            '<b>INFILL-SOLID</b> im Bandkern, <b>SURFACE-TOP</b> auf der jeweiligen Band-Deckschicht '
            '<b>j == n_band - 1</b>).',
            '<b>Decklagen-Glättung (Ironing = ON):</b> Auf der jeweils obersten Schicht jedes '
            'Farbbands (<b>cap == True</b>) fährt die Düse alle Blöcke noch einmal im '
            '<b>0,45-mm-Feinraster</b> mit nur <b>15 % Extrusionsfluss</b> ab — da Teile von '
            'Band k im fertigen Bild dauerhaft sichtbar bleiben, glänzt so jede einzelne Farbstufe '
            'wie gedruckter Siebdruck.',
            '<b>Warum BandH = 0,8 mm (4 Lagen @ 0,20 mm) der Sweet-Spot ist:</b> Dünnes gelbes, '
            'weißes oder rotes PLA ist auf einer einzelnen 0,20-mm-Lage noch halbtransparent; '
            'nach 3 bis 4 Lagen (0,6..0,8 mm) deckt selbst helles Pigment auf dunklerem Umfeld '
            'vollständig opak (und wer bewusst HueForge-artige Farbmischungen will, senkt '
            '<b>BandH = 0,4 mm</b> bei <b>Layer = 0,10..0,12 mm</b>!).'
        )

        st += SP(2)
        st += [IMG(fig1, width_mm=162)]
        st += CAP(
            'Abbildung 1 — Links: Echte aus %s geparste XY-Werkzeugbahnen aller 4 Bänder '
            '(WHT -> CYA -> BLU -> BLK) samt 12×12-mm-Purge-Tower. Rechts: Gemessener 16-Lagen-'
            'Aufbau, exakte M600-Positionen (L5, L9, L13) und realer Filamentbedarf pro Spule.'
            % i_4['file']
        )

        # ---- Kapitel 2 ------------------------------------------------------
        st += H1('14er-Farbpalette, LED-Führung & der R149-Z-Reset', '2')
        st += P(
            'Unter <b>macros/18_colorpic.cfg</b> und <b>make_colorpic()</b> arbeitet das '
            'Farbsystem komplett blind-tauglich: An jeder Bandgrenze (<b>li &gt; 1</b> und '
            '<b>j == 0</b> bei <b>Swap = ON</b>) schreibt der Generator exakt vier Sicherheits-'
            'schritte in den G-Code:'
        )
        st += NUM(
            '<b>_COLORPIC_SWAP:</b> Speichert bisherigen und nächsten RGB-Wert und lässt die '
            'Düsen-Beleuchtung im Sekundentakt von der <i>alten</i> zur <i>neuen</i> Zielfarbe '
            'blinken — man sieht schon aus 3 Metern Entfernung im Raum, welche Spule als '
            'Nächstes eingelegt werden muss!',
            '<b>M600 + _COLORPIC_DONE:</b> Parkt den Druckkopf sicher, wirft das alte Filament '
            'aus, wartet auf den Spulenwechsel und schaltet die LED nach RESUME wieder ruhig.',
            '<b>Der lebenswichtige R149-Fix — pen.set_z(z) direkt nach M600:</b> Beim Parken und '
            'Spülen hebt <b>M600</b> die Z-Achse um ~10 mm an. Ohne explizite Z-Rückstellung '
            'würde das nächste Band in der Luft drucken — deshalb erzwingt <b>pen.set_z(z)</b> '
            'unmittelbar vor dem ersten Zug jedes Layers die exakte geometrische Schichthöhe!',
            '<b>PURGE_TOWER (12 × 12 mm, 15 mm Sicherheitsabstand):</b> Bevor die Düse das '
            'eigentliche Kunstwerk berührt, drückt sie auf dem separaten Turm 4,0 mm Schmelze '
            'durch und streift sie auf einer Doppelbahn sauber ab (tagged als <b>PRIME-TOWER</b>).'
        )

        st += SP(2)
        st += [IMG(fig2, width_mm=162)]
        st += CAP(
            'Abbildung 2 — Live aus r2_postproc.COLORPIC_PALETTE und COLORPIC_DEFAULTS gerenderte '
            'Referenzkarte aller 14 Farb-Codes und der 7 automatischen Hell-nach-Dunkel-Rampen.'
        )

        # ---- Kapitel 3 ------------------------------------------------------
        st += H1('Live-Menüreferenz & Gemessene Referenzläufe', '3')
        st += P(
            'Direkt aus <b>menus/lcd_menues.cfg</b> gelesene Zeilen unter '
            '<b>Tools &gt; ColorPicture</b>:'
        )
        st += TBL(
            ['LCD-Menüpfad', 'Anzeige am Display', 'Wertebereich / Funktion'],
            [[a, b, c] for (a, b, c) in lcd_rows],
            [64 * mm, 52 * mm, 46 * mm],
            mono_cols=(1,),
        )
        st += SP(2)
        st += P(
            '<b>Konsolen-Schnellstart:</b> '
            '<b>GEN_COLORPIC SRC=foto.png WIDTH=120 BANDS=4 BANDH=0.8 COLORS=WHT,YEL,RED,BLK</b> '
            'setzt alle Variablen in einem Aufruf und startet sofort den Hintergrund-Build.'
        )
        st += SP(2)
        ref_rows = []
        for lbl, p_str, inf, prs in [
            ('1. 4-Farb-Standardposter', 'W=80, B=4×0.8, Auto WHT..BLK', i_4, parsed_4),
            ('2. 2-Farb-Piktogramm S/W', 'W=90, B=2×0.6, WHT,BLK', i_2, parsed_2),
            ('3. 6-Farb-Kunstdruck', 'W=110, B=6×0.6, Auto 6er-Rampe', i_6, parsed_6),
            ('4. Einfarb-Tastrelief', 'W=80, B=4×0.8, Swap=OFF', i_noswap, parsed_ns),
            ('5. Warmton-Holzschnitt', 'W=100, lh=0.16, WHT,GLD,ORG,BRN,BLK', i_warm, parsed_w),
        ]:
            tot_mm = sum(prs['band_e_mm'])
            ref_rows.append([
                lbl,
                p_str,
                '%.0f×%.0f × %.1f mm (%d L)' % (inf['width'], inf['height'], inf['thickness'], inf['layers']),
                ','.join(inf['colors']),
                '%.0f mm / %d×M600' % (tot_mm, len(prs['m600_layers'])),
            ])
        st += TBL(
            ['Szenario', 'Parameter', 'Maße & Lagen', 'Aktive Rampe', 'ΣΔE / Wechsel'],
            ref_rows,
            [34 * mm, 40 * mm, 34 * mm, 28 * mm, 26 * mm],
            mono_cols=(2, 3, 4),
        )

        # ---- Kapitel 4 ------------------------------------------------------
        st += H1('Blind-Spulenwechsel & kreative Farbtricks', '4')
        st += [BOX(
            'Blind-Regel: Du musst dem Drucker NICHT die echten Farben verraten!',
            [
                '• Die Codes <b>WHT, CYA, BLU, BLK</b> steuern die LED-Erinnerung und den '
                'Header-Kommentar — physikalisch entscheidet allein, <b>welche Spule du beim '
                'Piepen tatsächlich einlegst</b>!',
                '• <b>Einzige Pflichtregel für fotorealistische Motive:</b> Lege als <b>erste</b> '
                'Spule immer dein <b>hellstes</b> Filament ein (Weiß, Elfenbein, Silber, Gelb) '
                'und werde mit jedem <b>M600</b>-Piep dunkler bis zu Dunkelblau, Braun oder Schwarz '
                'am Schluss. Vertauscht man Hell und Dunkel, entsteht ein spannender Solarisations-/'
                'Negativ-Pop-Art-Effekt!',
                '• <b>Kein Platz für den Purge-Tower bei riesigen Bildern (Width &gt; 195 mm)?</b> '
                '<b>make_colorpic()</b> prüft alle vier Seiten auf 15 mm Sonden-Abstand. Passt '
                'der 12×12-mm-Turm nirgends mehr hin, lässt die Engine ihn sauber weg (kein '
                'Bett-Crash!) und vermerkt im Header, dass die Spülung in der M600-Parkposition '
                'erfolgt.'
            ],
            kind='tip',
        )]

        doc.render()
    return out_pdf


if __name__ == '__main__':
    target = os.path.join(REPO, 'COLORPIC.pdf')
    build_pdf(target)
    print('Wrote %s (%d bytes)' % (target, os.path.getsize(target)))
