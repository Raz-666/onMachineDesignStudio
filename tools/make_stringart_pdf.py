#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""make_stringart_pdf.py — Wissenschaftliche Methodik-, Sehnenplanungs- &
Freiflugphysik-PDF für ArtisticStrings (MASTER-TODO D3 + D6,
R171 / R178 / R216 / R232, Tools > ArtisticStrings).

Verbindliche D6-Wahrheitsregel:
  * KEINE Fantasie-Grafiken. Jede Fadennetz-Ansicht, jede Z-Bogenkurve und
    jede Anker-Wickelcurl-Lupe stammt aus echten Läufen von
    `r2_postproc.make_string_art()` zur Bauzeit und wird direkt aus den
    erzeugten G-Code-Dateien geparst.
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


# ------------------------------------------------ Synthetisches Hochkontrast-Motiv
def _make_moon_emblem_png(path):
    """Kontrastreiches Sichelmond- & Ringmotiv auf hellem Grund: zeigt die
    gerichtete Verdichtung des Greedy-Planers _string_art_plan() glasklar."""
    w, h = 200, 200
    im = PILImage.new('L', (w, h), 248)
    dr = ImageDraw.Draw(im)
    # Dunkler Vollkreis + versetzter weißer Ausschnitt = kräftige Sichel
    dr.ellipse((34, 28, 166, 160), fill=14)
    dr.ellipse((68, 24, 180, 136), fill=248)
    # Dunkler Gegengewichts-Sternpunkt + Basisbogen
    dr.ellipse((112, 66, 144, 98), fill=16)
    dr.rectangle((46, 166, 154, 182), fill=20)
    im.save(path)
    return path


# ----------------------------------------- G-Code-Parser für StringArt-Bahnen
def _parse_stringart_gcode(gcode_path):
    """Liest aus einem erzeugten StringArt-G-Code-File:
      - Ring-Wände (Layer 2) und Brücken-Fäden (alle 6 Z-Bänder),
      - 3D-(s, z)-Trajektorien repräsentativer Fäden je Band + Travel-Hops,
      - echte 6-Segment-Wickelcurl-Punkte am ersten Fadenstart,
      - Gesamt-Extrusionslänge ΣΔE (in echten Filament-mm)."""
    ring_segs = []
    bridge_segs = []       # (x1, y1, x2, y2, band_idx)
    bow_profiles = {}      # band_idx -> list of (s_norm, z) along first long chord
    hop_z_by_band = {}     # band_idx -> max travel Z
    first_curl_pts = []

    cur_layer = 0
    cur_type = 'OTHER'
    bridge_band = -1
    x = y = z = 0.0
    total_e = 0.0

    # Für Bogen-Profil & Curl-Extraktion innerhalb eines Bands
    cur_strand_pts = []    # [(x, y, z)]
    in_bridge = False

    def _flush_strand(b_idx, pts):
        if len(pts) < 16:
            return
        # Erste 7 Punkte = Startanker + 6 Wickelcurl-Segmente
        if not first_curl_pts and b_idx == 0:
            first_curl_pts.extend([(p[0], p[1]) for p in pts[:8]])
        # Mittlerer Sehnenabschnitt (ohne die 6 Start- und 6 End-Curlpunkte)
        core = pts[6:-6]
        if len(core) >= 5 and b_idx not in bow_profiles:
            xa, ya, _ = core[0]
            xb, yb, _ = core[-1]
            span = math.hypot(xb - xa, yb - ya)
            if span > 45.0:
                prof = []
                for px, py, pz in core:
                    u = math.hypot(px - xa, py - ya) / span
                    prof.append((max(0.0, min(1.0, u)), pz))
                bow_profiles[b_idx] = prof

    with open(gcode_path, encoding='utf-8', errors='replace') as fh:
        for raw in fh:
            s = raw.strip()
            if s == 'LAYER_MARK':
                if in_bridge and cur_strand_pts:
                    _flush_strand(bridge_band, cur_strand_pts)
                    cur_strand_pts = []
                cur_layer += 1
                cur_type = 'OTHER'
                in_bridge = False
                continue
            if s.startswith('APPLY_TYPE TYPE='):
                tp_new = s.split('TYPE=', 1)[1].split()[0].strip('"\'')
                if tp_new == 'BRIDGE' and cur_type != 'BRIDGE':
                    bridge_band += 1
                    in_bridge = True
                elif tp_new != 'BRIDGE':
                    if in_bridge and cur_strand_pts:
                        _flush_strand(bridge_band, cur_strand_pts)
                        cur_strand_pts = []
                    in_bridge = False
                cur_type = tp_new
                continue
            code = s.split(';', 1)[0].strip()
            if not code:
                continue
            if code in ('G10', 'G11'):
                if code == 'G10' and in_bridge and cur_strand_pts:
                    _flush_strand(bridge_band, cur_strand_pts)
                    cur_strand_pts = []
                continue
            if not (code.startswith('G0 ') or code.startswith('G1 ')):
                continue
            is_g0 = code.startswith('G0 ')
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
            if is_g0 and in_bridge and bridge_band >= 0:
                hop_z_by_band[bridge_band] = max(hop_z_by_band.get(bridge_band, 0.0), nz)
            if ne is not None and ne > 1e-7:
                total_e += ne
                if cur_layer == 2 and cur_type in ('WALL-OUTER', 'WALL-INNER'):
                    ring_segs.append((x, y, nx, ny))
                elif cur_type == 'BRIDGE':
                    if not cur_strand_pts:
                        cur_strand_pts.append((x, y, z))
                    cur_strand_pts.append((nx, ny, nz))
                    if math.hypot(nx - x, ny - y) > 1.2:
                        bridge_segs.append((x, y, nx, ny, max(0, bridge_band)))
            x, y, z = nx, ny, nz

    if in_bridge and cur_strand_pts:
        _flush_strand(bridge_band, cur_strand_pts)

    return {
        'ring_segs': ring_segs,
        'bridge_segs': bridge_segs,
        'bow_profiles': bow_profiles,
        'hop_z': hop_z_by_band,
        'curl_pts': first_curl_pts,
        'total_e': total_e,
    }


# -------------------------------------------------------- Live-LCD-Menüparser
def _parse_stringart_menu():
    cfg_path = os.path.join(REPO, 'menus', 'lcd_menues.cfg')
    txt = open(cfg_path, encoding='utf-8').read()
    blocks = re.split(r'(?m)^(?=\[menu )', txt)
    secs = [b for b in blocks if b.startswith('[menu __main __gen __stringart')]
    rows = []
    seen_pre = seen_usr = False
    for sec in secs:
        lines = [l.strip() for l in sec.strip().splitlines() if l.strip()]
        hdr = lines[0].strip('[]').replace('menu __main __gen __stringart', 'ArtisticStrings')
        if '__pre __p' in hdr or hdr.endswith('__pre __off'):
            if not seen_pre:
                seen_pre = True
                rows.append((
                    'ArtisticStrings > Preset > ...',
                    '9x13 · 10x15 · 13x18 · 15x20 · 18x24 · Custom',
                    'Passgenau für Tools > Frames!',
                ))
            continue
        if re.search(r'__img __s\d+$', hdr) or any(hdr.endswith(s) for s in ('__pgi', '__pgp', '__pgn')):
            continue
        if '__usr __p' in hdr or any(hdr.endswith(s) for s in ('__pu', '__pd', '__usr __info')):
            if not seen_usr and '__usr' in hdr:
                seen_usr = True
                rows.append(('ArtisticStrings > My presets > 1..8', 'Load / Delete Preset', '8 Speicherplätze'))
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
            '__pat': 'Pattern: PHOTO / SPIRAL',
            '__dia': 'Ring: [60..400]mm (ROUND)',
            '__shp': 'Shape: ROUND / RECT',
            '__pre': 'Preset: [Fotoformat]',
            '__w': 'W: [60..400]mm (RECT)',
            '__h': 'H: [60..400]mm (RECT)',
            '__arl': 'AR lock ON / OFF',
            '__rh': 'RingH: [1.2..6.0]mm',
            '__arc': 'Bow: [0.0..4.0]mm Z-Bogen',
            '__anc': 'Anchors: [24..720] Pins',
            '__lin': 'Strands: [50..4000] Fäden',
            '__img': 'Img: [Quellbild wählen]',
            '__usr __save': 'Save: Preset speichern',
            '__go': 'Weave (2× Klick = Start)',
        }
        for suf, label in clean_map.items():
            if hdr.endswith(suf):
                nm = label
                break
        rng = ('%s .. %s (Schritt %s)' % (mn, mx, st)) if mn else ('Untermenü' if tp == 'list' else 'Schalter / Aktion')
        rows.append((hdr.replace(' __', ' > '), nm[:44], rng))
    return rows


# --------------------------------------------------------- D6-Echtlauf-Grafiken
def _fig_stringart_gallery(p_spiral, i_spiral, p_photo, i_photo, p_rect, i_rect, out_png):
    """Abb. 1: Drei echte aus erzeugten G-Code-Dateien gelesene Fadennetze:
    (1) ROUND SPIRAL (kaustische Hüllkurve r = R/2), (2) ROUND PHOTO (Greedy-
    Planer auf Sichelmond-Motiv), (3) RECT PHOTO 10×15 (102×152-mm-Rahmen)."""
    W_img, H_img = 1520, 560
    im = PILImage.new('RGB', (W_img, H_img), '#ffffff')
    dr = ImageDraw.Draw(im)
    f_title = font(21, bold=True)
    f_sub = font(16, bold=True)
    f_sm = font(13)

    dr.text((26, 14),
            'Drei echte aus erzeugtem G-Code gelesene Fadennetze — SPIRAL vs. PHOTO (ROUND & RECT)',
            fill='#1c4e8c', font=f_title)

    specs = [
        (24, '1. ROUND · SPIRAL (ohne Bild)',
         'D=120 mm, N=180, L=240 -> Kaustik r = R·cos(60°)', p_spiral, i_spiral),
        (524, '2. ROUND · PHOTO (Greedy-Radon)',
         'D=120 mm, N=180, L=520 -> Sichelmond-Verdichtung', p_photo, i_photo),
        (1024, '3. RECT 10×15 · PHOTO (Rahmenmaß)',
         '102×152 mm, N=200, L=520 -> passt in Frames 10×15', p_rect, i_rect),
    ]

    for px0, head, sub, gpath, inf in specs:
        pw, ph = 472, 490
        py0 = 52
        dr.rounded_rectangle((px0, py0, px0 + pw, py0 + ph), radius=10,
                             fill='#f8fafd', outline='#bfd0e6', width=2)
        dr.text((px0 + 14, py0 + 10), head, fill='#1c4e8c', font=f_sub)
        dr.text((px0 + 14, py0 + 34), sub, fill='#58595b', font=f_sm)

        prs = _parse_stringart_gcode(gpath)
        pts = [(s[0], s[1]) for s in prs['ring_segs']] + [(s[2], s[3]) for s in prs['ring_segs']]
        xmin = min(p[0] for p in pts)
        xmax = max(p[0] for p in pts)
        ymin = min(p[1] for p in pts)
        ymax = max(p[1] for p in pts)

        avail_w, avail_h = pw - 44, ph - 108
        sc = min(avail_w / max(1e-6, xmax - xmin), avail_h / max(1e-6, ymax - ymin))
        ox = px0 + (pw - (xmax - xmin) * sc) / 2.0
        oy = py0 + 64 + (avail_h - (ymax - ymin) * sc) / 2.0

        # Heller Leinwandhintergrund, feine Fäden nach Z-Band abgetönt
        band_cols = ['#64748b', '#475569', '#334155', '#1e3a8a', '#1c4e8c', '#0f172a']
        for x1, y1, x2, y2, bi in prs['bridge_segs']:
            pa = (ox + (x1 - xmin) * sc, oy + (ymax - y1) * sc)
            pb = (ox + (x2 - xmin) * sc, oy + (ymax - y2) * sc)
            dr.line((pa[0], pa[1], pb[0], pb[1]),
                    fill=band_cols[min(5, bi)], width=1)

        # Ankerring-Wände kräftig darüber
        for x1, y1, x2, y2 in prs['ring_segs']:
            pa = (ox + (x1 - xmin) * sc, oy + (ymax - y1) * sc)
            pb = (ox + (x2 - xmin) * sc, oy + (ymax - y2) * sc)
            dr.line((pa[0], pa[1], pb[0], pb[1]), fill='#e07b00', width=2)

        dr.text((px0 + 12, py0 + ph - 25),
                '%s · %d Fäden · ΣΔE=%.0f mm'
                % (inf['file'], inf['lines'], prs['total_e']),
                fill='#475569', font=font(12))

    im.save(out_png)
    return out_png


def _fig_zbow_and_curl(prs_photo, info_photo, out_png):
    """Abb. 2: Links echter Z-Seitenaufriss der 6-stufigen Fadenleiter samt
    2,0-mm-Sinusbögen z_band + arc·sin(pi*t), Safe-Travel-Hops und 3 Klemmringen;
    rechts 40×-Mikroskop-Lupe des echten 6-Punkt-Anker-Wickelcurls (r = 0,30 mm)."""
    W_img, H_img = 1520, 580
    im = PILImage.new('RGB', (W_img, H_img), '#ffffff')
    dr = ImageDraw.Draw(im)
    f_title = font(18, bold=True)
    f_sub = font(15, bold=True)
    f_lbl = font(14)
    f_sm = font(13)

    # Linkes Panel: Echter (u, Z)-Aufriss der 6-Band-Leiter + 2,0-mm-Sinusbögen
    dr.rounded_rectangle((22, 18, 930, 562), radius=10,
                         fill='#f8fafd', outline='#bfd0e6', width=2)
    dr.text((38, 30),
            'A. Z-Aufriss aus G-Code: 6-Band-Leiter + 2,0-mm-Sinusbögen (Bow)',
            fill='#1c4e8c', font=f_title)
    dr.text((40, 58),
            'Jeder Faden wölbt sich um arc·sin(π·t) über bereits gespannte Bänder — die Düse kämmt nie durchs Netz!',
            fill='#58595b', font=f_sm)

    gx0, gy0, gw, gh = 110, 98, 780, 412
    dr.rectangle((gx0, gy0, gx0 + gw, gy0 + gh), fill='#ffffff', outline='#94a3b8', width=2)

    z_min_plot, z_max_plot = 0.0, 6.2
    def to_uz(u_norm, z_mm):
        return (gx0 + 48 + u_norm * (gw - 96),
                gy0 + gh - (z_mm - z_min_plot) / (z_max_plot - z_min_plot) * gh)

    # Z-Gitterlinien
    for zv in (0.0, 1.0, 2.0, 2.48, 3.0, 4.0, 5.0, 6.0):
        _, yy = to_uz(0.0, zv)
        dr.line((gx0, yy, gx0 + gw, yy), fill='#e2e8f0', width=1)
        dr.text((gx0 - 68, yy - 8), '%.2f mm' % zv, fill='#475569', font=f_sm)

    # Links und rechts den Ankerring (0 .. ring_top = 2.48 mm) + 3 Klemmringe zeichnen
    ring_top = 2.48
    _, y_z0 = to_uz(0.0, 0.0)
    _, y_rt = to_uz(0.0, ring_top)
    dr.rectangle((gx0 + 10, y_rt, gx0 + 54, y_z0), fill='#cbd5e1', outline='#475569', width=2)
    dr.rectangle((gx0 + gw - 54, y_rt, gx0 + gw - 10, y_z0), fill='#cbd5e1', outline='#475569', width=2)
    dr.text((gx0 + 62, y_rt + 18), 'Ankerring 0..2,48 mm\n(2 Wände + 5 % Infill)', fill='#334155', font=f_sm)

    # 3 Abschluss-Klemmringe (+1.05, +1.25, +1.45 mm über ring_top)
    for fz_off in (1.05, 1.25, 1.45):
        _, yf = to_uz(0.0, ring_top + fz_off)
        dr.rectangle((gx0 + 12, yf - 3, gx0 + 52, yf + 3), fill='#e07b00', outline='#b35c00')
        dr.rectangle((gx0 + gw - 52, yf - 3, gx0 + gw - 12, yf + 3), fill='#e07b00', outline='#b35c00')
    _, yf_top = to_uz(0.0, ring_top + 1.45)
    dr.text((gx0 + gw - 262, y_rt + 18), '3 Klemmringe\n(+1,05..+1,45 mm)', fill='#b35c00', font=f_sm)

    # Alle 6 echten Bogenprofile aus dem G-Code plotten
    b_cols = ['#93c5fd', '#60a5fa', '#3b82f6', '#2563eb', '#1d4ed8', '#1e3a8a']
    for bi in sorted(prs_photo['bow_profiles'].keys()):
        prof = prs_photo['bow_profiles'][bi]
        pts_px = [to_uz(u, zv) for (u, zv) in prof]
        if len(pts_px) >= 2:
            dr.line(pts_px, fill=b_cols[min(5, bi)], width=3)

    # Oberster Safe-Z-Hop (G0 Z = z_band_6 + arc + 0.5) rot gestrichelt einzeichnen
    if prs_photo['hop_z']:
        zh_max = max(prs_photo['hop_z'].values())
        pa_h = to_uz(0.04, zh_max)
        pb_h = to_uz(0.96, zh_max)
        for k in range(0, 36, 2):
            xa = pa_h[0] + (pb_h[0] - pa_h[0]) * (k / 36.0)
            xb = pa_h[0] + (pb_h[0] - pa_h[0]) * ((k + 1) / 36.0)
            dr.line((xa, pa_h[1], xb, pa_h[1]), fill='#c62828', width=2)
        dr.text((gx0 + 180, pa_h[1] - 22),
                'G0 Leerfahrt-Sprung Z_hop = z_band + Bow + 0,50 mm (max. %.2f mm) — kollisionsfrei!'
                % zh_max,
                fill='#c62828', font=f_sm)

    dr.text((42, 526),
            'Lüfterrampe über die 6 Bänder: M106 S60 (24 %) -> S100 -> S140 -> S180 -> S220 -> S255 (100 %)',
            fill='#163c6e', font=f_lbl)

    # Rechtes Panel: Echte 40×-Mikroskop-Lupe des Anker-Wickelcurls (r = 0,30 mm)
    dr.rounded_rectangle((954, 18, 1498, 562), radius=10,
                         fill='#f8fafd', outline='#bfd0e6', width=2)
    dr.text((974, 30), 'B. 40×-Lupe: Anker-Wickelcurl (r = 0,30 mm)',
            fill='#1c4e8c', font=f_title)
    dr.text((974, 58),
            'Echte G1-Punkte am Fadenstart: „um den Nagel gewickelt"',
            fill='#58595b', font=f_sm)

    cx0, cy0, cw, ch = 984, 98, 484, 316
    dr.rectangle((cx0, cy0, cx0 + cw, cy0 + ch), fill='#fffdf7', outline='#e07b00', width=2)

    cpts = prs_photo['curl_pts']
    if len(cpts) >= 7:
        ax0, ay0 = cpts[0]
        # Fenster +-0.75 mm um den Ankerpunkt
        span_mm = 1.45
        csc = min(cw, ch) / span_mm
        cox = cx0 + cw * 0.44
        coy = cy0 + ch * 0.54

        def to_c(xm, ym):
            return (cox + (xm - ax0) * csc, coy - (ym - ay0) * csc)

        # Ringoberfläche schraffiert andeuten
        dr.ellipse((cox - 0.30 * csc, coy - 0.30 * csc,
                    cox + 0.30 * csc, coy + 0.30 * csc),
                   outline='#cbd5e1', width=2)
        curl_px = [to_c(px, py) for (px, py) in cpts[:7]]
        dr.line(curl_px, fill='#1c4e8c', width=4)
        for idx_p, (qx, qy) in enumerate(curl_px):
            dr.ellipse((qx - 5, qy - 5, qx + 5, qy + 5), fill='#e07b00', outline='#163c6e')
            dr.text((qx + 7, qy - 8), 'P%d' % idx_p, fill='#334155', font=f_sm)
        # Abgehender Brückenfaden zum Zielanker
        p_exit = to_c(cpts[7][0], cpts[7][1])
        # Kappe auf Boxrand, falls der erste 5-mm-Schritt weit hinausläuft
        dx_e, dy_e = p_exit[0] - curl_px[-1][0], p_exit[1] - curl_px[-1][1]
        nrm = max(1e-6, math.hypot(dx_e, dy_e))
        p_arrow = (curl_px[-1][0] + dx_e / nrm * 150, curl_px[-1][1] + dy_e / nrm * 150)
        dr.line((curl_px[-1][0], curl_px[-1][1], p_arrow[0], p_arrow[1]),
                fill='#00706b', width=4)
        dr.text((cx0 + 12, cy0 + ch - 26),
                'P0..P6 = 6-Ecken-Öhr Ø 0,60 mm · Grün = Abflug',
                fill='#00706b', font=font(12))

    # Darunter Merkkasten zur R216-Thermospreizung & Fadenquerschnitt
    dr.rounded_rectangle((984, 430, 1468, 544), radius=8,
                         fill='#eef7ee', outline='#1e7d32', width=2)
    dr.text((1000, 442), 'R216-Feldphysik (warum der Ring stabil bleibt):',
            fill='#1e7d32', font=f_sub)
    dr.text((1000, 468),
            '• Startspreizung >= 15° (_spread_starts) + Richtungswechsel',
            fill='#222222', font=f_sm)
    dr.text((1000, 490),
            '• E/mm = wid·0,068 / A_fil ≈ 0,0141 mm/mm (echter 0,07-mm-Faden)',
            fill='#222222', font=f_sm)
    dr.text((1000, 512),
            '• 3 Deckringe klemmen alle %d Fadenenden unlösbar fest.' % info_photo['lines'],
            fill='#222222', font=f_sm)

    im.save(out_png)
    return out_png


# -------------------------------------------------------------- Hauptdokument
def build_pdf(out_pdf):
    lcd_rows = _parse_stringart_menu()

    with tempfile.TemporaryDirectory(prefix='r2_stringart_pdf_') as tmpdir:
        src_img = _make_moon_emblem_png(os.path.join(tmpdir, 'Sichelmond.png'))

        # 5 echte Referenzläufe von make_string_art()
        p_spi, i_spi = pp.make_string_art(
            None, pattern='SPIRAL', shape='ROUND', diameter=120.0,
            anchors=180, lines=240, arc=2.0, nozzle=0.6, out_dir=tmpdir)

        p_pho, i_pho = pp.make_string_art(
            src_img, pattern='PHOTO', shape='ROUND', diameter=120.0,
            anchors=180, lines=520, arc=2.0, nozzle=0.6, out_dir=tmpdir)

        p_rec, i_rec = pp.make_string_art(
            src_img, pattern='PHOTO', shape='RECT', size_w=102.0, size_h=152.0,
            anchors=200, lines=520, arc=2.0, nozzle=0.6, out_dir=tmpdir)

        p_por, i_por = pp.make_string_art(
            src_img, pattern='PHOTO', shape='ROUND', diameter=180.0,
            anchors=300, lines=1200, arc=2.0, nozzle=0.4, out_dir=tmpdir)

        p_flt, i_flt = pp.make_string_art(
            None, pattern='SPIRAL', shape='RECT', size_w=90.0, size_h=130.0,
            anchors=144, lines=200, arc=0.0, nozzle=0.4, out_dir=tmpdir)

        prs_pho = _parse_stringart_gcode(p_pho)

        fig1 = os.path.join(tmpdir, 'fig_sa_gallery.png')
        _fig_stringart_gallery(p_spi, i_spi, p_pho, i_pho, p_rec, i_rec, fig1)

        fig2 = os.path.join(tmpdir, 'fig_sa_zbow.png')
        _fig_zbow_and_curl(prs_pho, i_pho, fig2)

        doc = Doc(
            out_pdf,
            kopf='R2-D2 Macro System · Generator ArtisticStrings / Fadenkunst (D3)',
            titel='ArtisticStrings — Greedy-Sehnenplanung, 6-Band-Z-Leiter & Freiflugphysik',
        )
        st = doc.story

        cover_tbl = TBL(
            ['Kenngröße', 'Wert im aktuellen Produktivcode (R171 / R178 / R216 / R232)'],
            [
                ['Menüpfad am Display', 'Tools > ArtisticStrings  (63 Menü-Sektionen inkl. Foto-Presets & 8 User-Slots)'],
                ['G-Code-Makros / Engine', 'STRINGART_APPLY · STRINGART_PICK · STRINGART_IMG -> make_string_art()'],
                ['Muster & Rahmenformen', 'Pattern = PHOTO / SPIRAL · Shape = ROUND (Ø 60..400) / RECT (60..400 mm)'],
                ['Fotoformat-Presets (RECT)', '9×13 (90×130) · 10×15 (102×152) · 13×18 · 15×20 · 18×24 — passend zu Frames!'],
                ['Anker & Fadenzahl', 'Anchors = 24 .. 720 (Default 300) · Strands = 50 .. 4000 (Default 1700)'],
                ['6-Band-Z-Leiter & Parabelbogen', 'LADDER = +0,20 .. +0,95 mm über Ring · Bow = 0,0 .. 4,0 mm (Default 2,0 mm)'],
                ['Thermoschutz & Fadenfluss', '_spread_starts >= 15° + Richtungswechsel · E/mm = wid · 0,068 / A_fil'],
                ['Ausgabeordner & Dateiname', 'gcodes/StringArt/Vnn_StringArt_<Stamm>[_<W>x<H>].gcode'],
            ],
            [56 * mm, 106 * mm],
        )[0]

        doc.add_cover(
            kicker='GENERATOR-FACHHEFT · BILD-ZU-GEOMETRIE-FAMILIE (D3 / D6)',
            titel='ArtisticStrings (3D-Fadenkunst)',
            untertitel='Diskrete inverse Radon-Sehnenplanung aus Fotos, kaustische Spiralgeometrie und kollisionsfreier Freiflug hauchdünner 0,07-mm-Filamentsaiten',
            absaetze=[
                'Bei klassischer Fadenkunst spannt man hunderte Meter Nähgarn von Nagel zu Nagel '
                'um einen Holzring, bis sich aus lauter geraden Sehnen ein Porträt abzeichnet. '
                'make_string_art() (R171 / R216) überträgt diese Kunstform nativ auf den '
                '3D-Drucker: Die Düse selbst zieht hauchfeine, frei gespannte Kunststofffäden '
                'quer durch die Luft von Ankerpunkt zu Ankerpunkt!',
                'Damit 1700 kreuzende Einzelfäden weder die Düse verkleben noch den Ankerring '
                'weichziehen oder den Raspberry Pi Zero 2 W in die Knie zwingen, kombiniert die '
                'Engine einen stochastischen Greedy-Linienintegral-Planer mit einer 6-stufigen '
                'Z-Kühlleiter, 2-mm-Sinusbögen im Raum und einer 15°-Startwinkelspreizung.',
            ],
            tabelle=cover_tbl,
        )

        # ---- Kapitel 1 ------------------------------------------------------
        st += H1('Mathematik der Sehnenplanung (SPIRAL & PHOTO)', '1')
        st += P(
            'Zuerst verteilt <b>_sa_anchor_pts(shape, hx, hy, N)</b> genau <b>N</b> virtuelle '
            'Nägel längentreu (konstante Bogenlänge <b>Δs = Umfang / N</b>) auf der Mittellinie '
            'des Ankerrings — wahlweise auf dem Kreis vom Radius <b>R - ring_w / 2</b> oder '
            'auf dem Rechteck der Halbachsen <b>(W/2 - ring_w/2, H/2 - ring_w/2)</b>:'
        )
        st += FORMULA(
            'SPIRAL-Gesetz:   j(k)  = (k + max(3, floor(N / 3))) mod N<br/>'
            'Kaustik-Inkreis: r_env = R_anchor · cos(π · step / N) ≈ 0,50 · R_anchor<br/>'
            'PHOTO-Sehnenmaß: Score(i,j) = Σ_{m=0..n_st} tgt[p_i + (m/n_st)·(p_j-p_i)]<br/>'
            'Mindest-Sehne:   |i - j|_ring &gt;= max(3, int(0.18·N))  (&gt;= 64,8° am Ring)',
            'Im PHOTO-Modus initialisiert _string_art_plan() das Zielgitter tgt = 1 - lum auf '
            'G × G = 100 × 100 Zellen. Jede gewählte Gewinnersehne reduziert alle getroffenen '
            'Gitterzellen um thread_dark = 0,10 — eine schnelle diskrete Greedy-Approximation '
            'der inversen Radon-Transformation.'
        )
        st += SP(2)
        st += H2('Pi-Zero-2-W-Speicherschutz (R223 / R232) & 15°-Thermospreizung', '1.1')
        st += B(
            '<b>Stochastische Kandidatenstichprobe (n_cand = 240):</b> Bei N = 600 Ankern gäbe '
            'es 179 700 Sehnenpaare pro Faden — mal 1700 Fäden wären das über 300 Millionen '
            'Linienintegrale. Die geseedete Zufallsstichprobe von <b>240 Kandidaten je Runde</b> '
            '(<b>seed = 170</b>, 100 % reproduzierbar!) konvergiert optisch ununterscheidbar in '
            'wenigen Sekunden.',
            '<b>Doppelter RAM-Schutz (R232 + R223):</b> Das Quellbild wird zeilenweise auf '
            '<b>max_dim = 288 px</b> dekodiert (mehr sieht das 100×100-Planergitter ohnehin '
            'nicht), und alle 200 Fäden prüft <b>_mem_available_mb() &lt; 30</b> den freien '
            'Host-RAM, um niemals durch Swap-Thrashing einen laufenden Klipper-Reaktor zu stören.',
            '<b>R216-Startwinkelspreizung _spread_starts(plan, N, 15°):</b> Würden zehn Fäden '
            'kurz nacheinander an benachbarten Ankern starten, bliebe der Ring dort heiß und '
            'verformte sich nach innen. <b>_spread_starts()</b> sortiert die fertige Sehnenliste '
            'verlustfrei so um, dass jeder Folgefaden mindestens <b>ceil(N · 15 / 360)</b> Anker '
            'weiter im Ring ansetzt — plus Richtungswechsel (<b>a -> b</b>, dann <b>b -> a</b>) '
            'auf jedem zweiten Faden!'
        )

        st += SP(2)
        st += [IMG(fig1, width_mm=162)]
        st += CAP(
            'Abbildung 1 — Live aus drei echten Läufen geparste Fadennetze: (1) ROUND SPIRAL '
            '(%s), (2) ROUND PHOTO auf dem Sichelmond-Motiv (%s), (3) RECT PHOTO im 10×15-'
            'Rahmenpreset 102×152 mm (%s).' % (i_spi['file'], i_pho['file'], i_rec['file'])
        )

        # ---- Kapitel 2 ------------------------------------------------------
        st += H1('Freiflugphysik: Fadenquerschnitt, 6-Band-Leiter & Z-Bow', '2')
        st += P(
            'Ein freifliegender Faden gehorcht völlig anderen Gesetzen als eine auf dem Bett '
            'abgelegte Wandspur: Er muss leicht unter Zug stehen, sofort im Luftstrom erstarren, '
            'darf bereits gespannte Nachbarfäden nicht durchpflügen und muss an beiden Enden '
            'mechanisch auf dem Ring verankert sein:'
        )
        st += FORMULA(
            'Ring-Aufbau:     Z = 0..ring_h (2,4 mm): 2 Wände + 3 Boden/Deck + 5 % Infill<br/>'
            '6-Band-Leiter:   z_band = ring_top + {+0,20, +0,40, +0,55, +0,60, +0,75, +0,95}<br/>'
            'Raum-Sinusbogen: z(t)   = z_band + Bow · sin(π · t)   für t ∈ [0, 1]<br/>'
            'Faden-Extrusion: E_seg  = sqrt(dx² + dy² + dz²) · (wid · 0,068 / A_fil)',
            'Bei wid = 0,50 mm und 1,75-mm-Filament (A_fil = 2,405 mm²) beträgt E/mm exakt '
            '0,01414 mm Filament pro mm Flugbahn — das ergibt eine hauchfeine, straff '
            'gespannte 0,50 × 0,068-mm-Saite (R216-Korrektur des früheren '
            'Volumenskalierungs-Fehlers).'
        )
        st += SP(2)
        st += NUM(
            '<b>Kollisionsfreier Leerfahrt-Hop (_sa_travel):</b> Vor jedem Faden zieht <b>G10</b> '
            'ein, hebt auf <b>z_band + Bow + 0,50 mm</b> (über den Scheitel aller bisherigen '
            'Bögen!), fährt mit F8000 zum Startanker, senkt auf <b>z_band</b> ab und entsichert '
            'mit <b>G11</b>.',
            '<b>Anker-Wickelcurl (Start &amp; Ende):</b> An beiden Enden fährt die Düse auf der '
            'Ringoberfläche ein sechseckiges Klebe-Öhr vom Radius <b>r = 0,30 mm</b> — exakt wie '
            'ein um einen echten Nagel geschlungener Faden.',
            '<b>Lüfterrampe &amp; 3 Klemmringe:</b> Der Bauteillüfter steigt über die 6 Bänder '
            'von <b>M106 S60 (24 %)</b> bis <b>S255 (100 %)</b>; zum Schluss verschweißen drei '
            'Deckschleifen (<b>Finishing 1/2 + Cover Ring</b> bei <b>+1,05 / +1,25 / +1,45 mm</b>) '
            'sämtliche Fadenenden dauerhaft auf dem Ring.'
        )

        st += SP(2)
        st += [IMG(fig2, width_mm=162)]
        st += CAP(
            'Abbildung 2 — Links: Echte aus %s extrahierte (u, Z)-Flugbahnen aller 6 Bänder samt '
            'Safe-Hop-Ebene und Klemmringen. Rechts: 40×-Lupe auf die realen G1-Punkte P0..P6 '
            'des 0,30-mm-Anker-Wickelcurls.' % i_pho['file']
        )

        # ---- Kapitel 3 ------------------------------------------------------
        st += H1('Live-Menüreferenz & Gemessene Referenzläufe', '3')
        st += TBL(
            ['LCD-Menüpfad', 'Anzeige am Display', 'Wertebereich / Funktion'],
            [[a, b, c] for (a, b, c) in lcd_rows],
            [62 * mm, 54 * mm, 46 * mm],
            mono_cols=(1,),
        )
        st += SP(3)
        ref_rows = []
        for lbl, pdesc, gp, inf in [
            ('1. Schneller Kalibrier-Spiralring', 'SPIRAL, ROUND Ø120, N=180, L=240', p_spi, i_spi),
            ('2. Kompakt-Fotomedaillon', 'PHOTO, ROUND Ø120, N=180, L=520', p_pho, i_pho),
            ('3. Rahmenbild 10×15 cm', 'PHOTO, RECT 102×152, N=200, L=520', p_rec, i_rec),
            ('4. Großes Porträt Ø180 mm', 'PHOTO, ROUND Ø180, N=300, L=1200', p_por, i_por),
            ('5. Flaches Spiral-Rechteck 9×13', 'SPIRAL, RECT 90×130, Bow=0.0', p_flt, i_flt),
        ]:
            prs = _parse_stringart_gcode(gp)
            ref_rows.append([
                lbl,
                pdesc,
                inf['file'],
                '%.2f mm' % inf['height'],
                '%d / %.0f mm' % (inf['lines'], prs['total_e']),
            ])
        st += TBL(
            ['Szenario', 'Parameter', 'Erzeugte Datei', 'Endhöhe', 'Fäden / ΣΔE'],
            ref_rows,
            [36 * mm, 44 * mm, 40 * mm, 16 * mm, 26 * mm],
            mono_cols=(2, 3, 4),
        )

        # ---- Kapitel 4 ------------------------------------------------------
        st += H1('Blindbedienung & Kombination mit Tools > Frames', '4')
        st += [BOX(
            'Praxis-Rezept für perfekte Fadenporträts beim ersten Versuch',
            [
                '• <b>Erster Test ohne Bild in 20 Minuten:</b> <b>Pattern = SPIRAL</b>, '
                '<b>Shape = ROUND</b>, <b>Ring = 100 mm</b>, <b>Strands = 250</b>, '
                '<b>Bow = 2,0 mm</b> -> prüft Retract, Bauteilkühlung und Fadenspannung.',
                '• <b>Porträtfoto wählen:</b> Dunkles Motiv vor hellem Hintergrund funktioniert '
                'direkt (dunkel = viele Fäden, weiß = freies Licht!). Für <b>Ø 180 mm</b> sind '
                '<b>Anchors = 300</b> und <b>Strands = 1500..2000</b> das feldbewiesene Optimum; '
                'dunkles PLA (Schwarz, Anthrazit, Dunkelblau) vor weißer Wand ergibt maximalen '
                'Kontrast.',
                '• <b>Direkt passend in Bilderrahmen einsetzen:</b> Unter <b>Shape = RECT</b> '
                'einfach <b>Preset = 10x15 (102x152)</b> oder <b>13x18 (130x180)</b> wählen — '
                'das gedruckte Fadengitter rastet ohne Nacharbeit exakt in den gleichnamigen '
                'Rahmen aus <b>Tools &gt; Frames</b> ein!'
            ],
            kind='tip',
        )]

        doc.render()
    return out_pdf


if __name__ == '__main__':
    target = os.path.join(REPO, 'STRINGART.pdf')
    build_pdf(target)
    print('Wrote %s (%d bytes)' % (target, os.path.getsize(target)))
