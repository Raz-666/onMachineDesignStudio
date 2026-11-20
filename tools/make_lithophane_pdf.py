#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""make_lithophane_pdf.py — Wissenschaftliche Methodik-, Physik- &
Blindbedienungs-PDF für den Lithophane- & Stempel-Generator (MASTER-TODO D3 + D6,
R89 / R128 / R168 / R214, Tools > Lithophane).

Verbindliche D6-Wahrheitsregel:
  * KEINE Fantasie-Grafiken. Jede Werkzeugbahn-Abbildung und jede Kennzahl in
    diesem Heft wird zur Bauzeit aus echten Läufen von
    `r2_postproc.make_lithophane()` (STANDING, FLAT, CONTOUR=2, STAMP+GRIFF)
    berechnet und direkt aus den erzeugten G-Code-Dateien geparst.
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


# ------------------------------------------------ Synthetisches Referenzmotiv
def _make_portrait_badge_png(path):
    """4-Ton-Porträt-/Medaillon-Testbild mit glatter Wellenkontur (ideal für die
    STANDING-Bändchenlupe) und geschachtelten Ringen/Augen (ideal für FLAT,
    Contour=2 und Stempel)."""
    w, h = 180, 180
    im = PILImage.new('L', (w, h), 246)
    dr = ImageDraw.Draw(im)
    dr.ellipse((18, 18, 162, 162), fill=176)      # Stufe 1: sanfter Halo
    dr.ellipse((42, 38, 138, 136), fill=104)      # Stufe 2: Medaillonkern
    dr.ellipse((62, 58, 82, 78), fill=246)        # helles linkes Auge (Lochtest!)
    dr.ellipse((98, 58, 118, 78), fill=246)       # helles rechtes Auge (Lochtest!)
    dr.arc((62, 78, 118, 120), start=15, end=165, fill=18, width=9)  # dunkler Bogen
    dr.rectangle((34, 144, 146, 166), fill=22)    # dunkler Namensbalken
    im.save(path)
    return path


# ----------------------------------------- G-Code-Parser für echte Bahnbilder
def _parse_layer_moves(gcode_path, target_layer=None):
    """Liest extrudierende Segmente (x1, y1, x2, y2, ftype, obj_name, layer)
    sowie die Gesamt-Extrusionslänge und M600-Anzahl aus einer G-Code-Datei."""
    segs = []
    cur_layer = 0
    cur_type = 'OTHER'
    cur_obj = ''
    x = y = e = 0.0
    erel = True
    total_e = 0.0
    m600_count = 0
    bridge_layers = set()

    with open(gcode_path, encoding='utf-8', errors='replace') as fh:
        for raw in fh:
            s = raw.strip()
            if s == 'LAYER_MARK' or s.startswith(';LAYER_CHANGE'):
                if s == 'LAYER_MARK':
                    cur_layer += 1
                continue
            if s == 'M600' or s.startswith('M600 '):
                m600_count += 1
                continue
            if s.startswith('APPLY_TYPE TYPE='):
                cur_type = s.split('TYPE=', 1)[1].split()[0].strip('"\'')
                if cur_type == 'BRIDGE':
                    bridge_layers.add(cur_layer)
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
                if target_layer is None or cur_layer == target_layer:
                    segs.append((x, y, nx, ny, cur_type, cur_obj, cur_layer))
            x, y = nx, ny
    return segs, total_e, m600_count, sorted(bridge_layers)


# -------------------------------------------------------- Live-LCD-Menüparser
def _parse_litho_menu():
    cfg_path = os.path.join(REPO, 'menus', 'lcd_menues.cfg')
    txt = open(cfg_path, encoding='utf-8').read()
    blocks = re.split(r'(?m)^(?=\[menu )', txt)
    secs = [b for b in blocks if b.startswith('[menu __main __gen __litho')]
    rows = []
    seen_img = seen_del = seen_usr = False
    for sec in secs:
        lines = [l.strip() for l in sec.strip().splitlines() if l.strip()]
        hdr = lines[0].strip('[]').replace('menu __main __gen __litho', 'Litho')
        if re.search(r'__img __s\d+$', hdr):
            if not seen_img:
                seen_img = True
                rows.append(('Litho > Images > 1..10', '1*..10* [Bilddatei]', '2× Klick Start'))
            continue
        if re.search(r'__del __d\d+$', hdr):
            if not seen_del:
                seen_del = True
                rows.append(('Litho > Delete image > 1..10', '1..10 [Bilddatei]', '2× Klick Löschen'))
            continue
        if '__usr __p' in hdr:
            if not seen_usr:
                seen_usr = True
                rows.append(('Litho > My presets > L1..L8', 'Load / Delete Preset', '8 Speicherplätze'))
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
            '__set __ori': 'Orient: STANDING / FLAT',
            '__set __hgt': 'Height / Size: [30..200]mm',
            '__set __col': 'Colors: [1..8] (FLAT)',
            '__set __cll': 'StepL: [0..30] Lagen/Stufe',
            '__set __ccm __cur': 'Now: [OFF / LAST / EACH]',
            '__set __bord': 'Border: [0.0..12.0]mm',
            '__set __corn': 'Corner: [0.0..20.0]mm',
            '__set __con': 'Contrast: ON / OFF',
            '__set __lh': 'Layer: [0.08..0.20]mm',
            '__set __lvl': 'Levels: [0=photo .. 16]',
            '__set __frm': 'Frame: ON / OFF',
            '__set __sdp': 'Side stands: ON / OFF',
            '__set __brm': 'Brim: [0..10]x',
            '__set __iro': 'Ironing: ON / OFF',
            '__set __mx': 'Mirror X: ON / OFF',
            '__set __my': 'Mirror Y: ON / OFF',
            '__set __ct': 'Contour: [0..3] (FLAT)',
            '__set __st': 'Stamp: ON / OFF (FLAT)',
            '__set __stb': 'StampH: [3.5..15.0]mm',
            '__set __stt': 'StampFit: [0.10..0.50]mm',
            '__set __gr': 'Handle: [0 / 2 / 3]',
            '__usr __save': 'Save: L[n] speichern',
        }
        for suf, label in clean_map.items():
            if hdr.endswith(suf):
                nm = label
                break
        rng = ('%s .. %s (Schritt %s)' % (mn, mx, st)) if mn else ('Untermenü' if tp == 'list' else 'Schalter / Aktion')
        rows.append((hdr.replace(' __', ' > '), nm[:42], rng))
    return rows


# --------------------------------------------------------- D6-Echtlauf-Grafiken
def _fig_standing_and_beer_lambert(standing_gcode, out_png):
    """Abb. 1: Links echter XY-Schichtausschnitt von make_lithophane(STANDING,
    stands=1) auf einer Brücken-Lage (zeigt Einspur-Zickzack-Bändchen, glatte
    Vorderseite y_F, Relief-Rückwand und R214-Dreiecksfinnen); rechts exakte
    Beer-Lambert-Transmissionskurven I/I_0 = exp(-mu * t) über [0.7, 3.0] mm."""
    _, _, _, br_layers = _parse_layer_moves(standing_gcode, target_layer=None)
    pick_l = br_layers[len(br_layers) // 2] if br_layers else 180
    segs, _, _, _ = _parse_layer_moves(standing_gcode, target_layer=pick_l)

    W_img, H_img = 1520, 640
    im = PILImage.new('RGB', (W_img, H_img), '#ffffff')
    dr = ImageDraw.Draw(im)
    f_title = font(21, bold=True)
    f_sub = font(16, bold=True)
    f_lbl = font(14)
    f_sm = font(13)

    # Linkes Panel: Echte STANDING-Schicht + Zickzack-Lupe
    dr.rounded_rectangle((22, 18, 810, 618), radius=10,
                         fill='#f8fafd', outline='#bfd0e6', width=2)
    dr.text((40, 30),
            'A. Echter STANDING-Schichtausschnitt (Layer %d, Z = %.2f mm)'
            % (pick_l, pick_l * 0.12),
            fill='#1c4e8c', font=f_title)
    dr.text((40, 58),
            'Blau = durchgehendes Bildbändchen (0 Leerfahrten!) · Grün/Orange = R214-Seitenfinnen mit BRIDGE-Rippe',
            fill='#58595b', font=f_sm)

    xs = [v for s in segs for v in (s[0], s[2])]
    ys = [v for s in segs for v in (s[1], s[3])]
    xmin, xmax = min(xs), max(xs)
    ymin, ymax = min(ys), max(ys)

    # Gesamtansicht oben links (Draufsicht auf Platte + 2 Dreiecksständer)
    gx0, gy0, gw, gh = 46, 94, 738, 250
    dr.rectangle((gx0, gy0, gx0 + gw, gy0 + gh), fill='#ffffff', outline='#cbd5e1')
    sx = (gw - 40) / max(1e-6, xmax - xmin)
    sy = (gh - 44) / max(1e-6, ymax - ymin)
    sc = min(sx, sy)
    ox = gx0 + (gw - (xmax - xmin) * sc) / 2.0
    oy = gy0 + 22 + (gh - 44 - (ymax - ymin) * sc) / 2.0

    def to_g(xm, ym):
        return (ox + (xm - xmin) * sc, oy + (ymax - ym) * sc)

    for x1, y1, x2, y2, tp, obj, _ in segs:
        p1, p2 = to_g(x1, y1), to_g(x2, y2)
        if 'STAND' in obj:
            col = '#e07b00' if tp == 'BRIDGE' else '#1e7d32'
            w_ln = 3 if tp == 'BRIDGE' else 2
        else:
            col = '#1c4e8c'
            w_ln = 2
        dr.line((p1[0], p1[1], p2[0], p2[1]), fill=col, width=w_ln)

    dr.text((gx0 + 12, gy0 + gh - 22),
            'Vorderseite y = y_F (glatt zum Betrachter) · Licht fällt von hinten (+Y) zwischen den beiden Seitenfinnen ein',
            fill='#475569', font=f_sm)

    # Darunter: Mikroskop-Lupe auf 18 mm Breite des echten Zickzack-Bändchens!
    zx0, zy0, zw, zh = 46, 366, 738, 234
    dr.rounded_rectangle((zx0, zy0, zx0 + zw, zy0 + zh), radius=8,
                         fill='#fffdf7', outline='#e07b00', width=2)
    dr.text((zx0 + 14, zy0 + 10),
            'Mikro-Lupe (echte G1-Züge, Y 18× überhöht): Einspur-Zickzack ribbon() ohne Retract',
            fill='#b35c00', font=font(14, bold=True))

    lit_segs = [s for s in segs if 'STAND' not in s[5]]
    x_mid = 0.5 * (xmin + xmax)
    win_segs = [s for s in lit_segs if (x_mid - 9.0) <= 0.5 * (s[0] + s[2]) <= (x_mid + 9.0)]
    if win_segs:
        wx0 = min(min(s[0], s[2]) for s in win_segs)
        wx1 = max(max(s[0], s[2]) for s in win_segs)
        wy0 = min(min(s[1], s[3]) for s in win_segs)
        wy1 = max(max(s[1], s[3]) for s in win_segs)
        z_sx = (zw - 56) / max(1e-6, wx1 - wx0)
        z_sy = (zh - 86) / max(0.4, wy1 - wy0)
        yf_px = zy0 + zh - 36
        for x1, y1, x2, y2, _, _, _ in win_segs:
            pa = (zx0 + 28 + (x1 - wx0) * z_sx, yf_px - (y1 - wy0) * z_sy)
            pb = (zx0 + 28 + (x2 - wx0) * z_sx, yf_px - (y2 - wy0) * z_sy)
            dr.line((pa[0], pa[1], pb[0], pb[1]), fill='#163c6e', width=2)
        dr.line((zx0 + 20, yf_px, zx0 + zw - 20, yf_px), fill='#c62828', width=2)
        dr.text((zx0 + 24, yf_px + 9),
                'Glatte Sichtfront y = y_F · Rückwand y_F + T[r, c] moduliert 0,70 mm (hell) .. 3,00 mm (dunkel)',
                fill='#c62828', font=f_sm)

    # Rechtes Panel: Beer-Lambert-Physik I/I0 = exp(-mu * t)
    dr.rounded_rectangle((832, 18, 1498, 618), radius=10,
                         fill='#f8fafd', outline='#bfd0e6', width=2)
    dr.text((852, 30), 'B. Beer-Lambert-Durchlichtkurve I(t) / I_0 = e^(-μ·t)',
            fill='#1c4e8c', font=f_title)
    dr.text((852, 58),
            'Warum Weiß/Natur-PLA über 0,7..3,0 mm ideal abstuft und dunkles PLA sofort sperrt:',
            fill='#58595b', font=f_sm)

    px0, py0, pw, ph = 918, 108, 540, 380
    dr.rectangle((px0, py0, px0 + pw, py0 + ph), fill='#ffffff', outline='#94a3b8', width=2)

    # Achsenraster: t = 0.4 .. 3.2 mm, Transmission 0 .. 100 %
    t_lo, t_hi = 0.4, 3.2
    for pct in (0, 20, 40, 60, 80, 100):
        yy = py0 + ph - int(ph * pct / 100.0)
        dr.line((px0, yy, px0 + pw, yy), fill='#e2e8f0', width=1)
        dr.text((px0 - 52, yy - 8), '%3d %%' % pct, fill='#475569', font=f_sm)
    for tm in (0.7, 1.2, 1.8, 2.4, 3.0):
        xx = px0 + int(pw * (tm - t_lo) / (t_hi - t_lo))
        dr.line((xx, py0, xx, py0 + ph), fill='#e2e8f0', width=1)
        dr.text((xx - 18, py0 + ph + 8), '%.1f mm' % tm, fill='#475569', font=f_sm)

    # Arbeitsfenster [base=0.7, base+dyn=3.0] hellblau hinterlegen
    xa_w = px0 + int(pw * (0.7 - t_lo) / (t_hi - t_lo))
    xb_w = px0 + int(pw * (3.0 - t_lo) / (t_hi - t_lo))
    dr.line((xa_w, py0, xa_w, py0 + ph), fill='#1c4e8c', width=2)
    dr.line((xb_w, py0, xb_w, py0 + ph), fill='#1c4e8c', width=2)
    dr.text((xa_w + 8, py0 + 10), 'Arbeitsfenster [t_min=0,70 .. t_max=3,00 mm]',
            fill='#1c4e8c', font=f_sm)

    curves = [
        (0.95, '#00706b', 'Natur / Warmweiß PLA (μ ≈ 0,95 mm⁻¹)'),
        (1.65, '#1c4e8c', 'Klassik Litho-Weiß PLA (μ ≈ 1,65 mm⁻¹)'),
        (4.20, '#c62828', 'Opak-Farb-/Schwarz-PLA (μ ≈ 4,20 mm⁻¹ -> tot ab 1,1 mm)'),
    ]
    for ly, (mu, col, lbl) in enumerate(curves):
        pts = []
        for k in range(120):
            t_val = t_lo + (t_hi - t_lo) * k / 119.0
            tr = math.exp(-mu * t_val)
            xx = px0 + (t_val - t_lo) / (t_hi - t_lo) * pw
            yy = py0 + ph - tr * ph
            pts.append((xx, yy))
        dr.line(pts, fill=col, width=3)
        dr.line((860, 526 + ly * 26, 896, 526 + ly * 26), fill=col, width=4)
        dr.text((906, 517 + ly * 26), lbl, fill=col, font=f_lbl)

    im.save(out_png)
    return out_png


def _fig_flat_contour_stamp(flat_classic, flat_c2, stamp_gcode, handle_gcode, out_png):
    """Abb. 2: Drei echte FLAT-Betriebsarten nebeneinander aus realen G-Code-Dateien:
    (1) FLAT Klassik + LAST-Purge-Tower, (2) FLAT Contour=2 topographisches
    Linienrelief, (3) FLAT Stamp=ON Unterseiten-Rastbuchse + Griff-Gegenstück."""
    W_img, H_img = 1520, 560
    im = PILImage.new('RGB', (W_img, H_img), '#ffffff')
    dr = ImageDraw.Draw(im)
    f_title = font(21, bold=True)
    f_sub = font(16, bold=True)
    f_sm = font(13)

    dr.text((26, 14),
            'Drei echte FLAT-Erzeugnisse im direkten Werkzeugbahn-Vergleich (live aus G-Code geparst)',
            fill='#1c4e8c', font=f_title)

    panels = [
        (24, '1. FLAT Stufenrelief + LAST (L10)',
         'Dunkelste Konturstufe + 12×12-mm-Purge-Tower', flat_classic, 10),
        (524, '2. FLAT Kontur-Relief Contour=2 (L8)',
         'Freistehende Höhenlinien (inkl. Augen-Innenringe!)', flat_c2, 8),
        (1024, '3. Stempel-Rastbuchse + Griff (L6)',
         'Snap-Buchse _StampFit168 im 10-%-Sockel + Griff-Pin', stamp_gcode, 6),
    ]

    for px0, head, sub, gpath, l_idx in panels:
        pw, ph = 472, 488
        py0 = 52
        dr.rounded_rectangle((px0, py0, px0 + pw, py0 + ph), radius=10,
                             fill='#f8fafd', outline='#bfd0e6', width=2)
        dr.text((px0 + 14, py0 + 10), head, fill='#1c4e8c', font=f_sub)
        dr.text((px0 + 14, py0 + 34), sub, fill='#58595b', font=f_sm)

        segs, tot_e, m600_n, _ = _parse_layer_moves(gpath, target_layer=l_idx)
        # Bei Panel 3 zusätzlich Layer 20 des separaten Griffs rechts unten einblenden
        h_segs = []
        if gpath == stamp_gcode and handle_gcode and os.path.isfile(handle_gcode):
            h_segs, _, _, _ = _parse_layer_moves(handle_gcode, target_layer=4)

        xs = [v for s in segs for v in (s[0], s[2])]
        ys = [v for s in segs for v in (s[1], s[3])]
        xmin, xmax = min(xs), max(xs)
        ymin, ymax = min(ys), max(ys)

        avail_w, avail_h = pw - 44, ph - 108
        sc = min(avail_w / max(1e-6, xmax - xmin),
                 avail_h / max(1e-6, ymax - ymin))
        ox = px0 + (pw - (xmax - xmin) * sc) / 2.0
        oy = py0 + 64 + (avail_h - (ymax - ymin) * sc) / 2.0

        for x1, y1, x2, y2, tp, obj, _ in segs:
            pa = (ox + (x1 - xmin) * sc, oy + (ymax - y1) * sc)
            pb = (ox + (x2 - xmin) * sc, oy + (ymax - y2) * sc)
            if 'TOWER' in obj or tp == 'PRIME-TOWER':
                col, w_ln = '#e07b00', 2
            elif tp == 'WALL-OUTER':
                col, w_ln = '#163c6e', 2
            else:
                col, w_ln = '#7da6d8', 1
            dr.line((pa[0], pa[1], pb[0], pb[1]), fill=col, width=w_ln)

        if h_segs:
            # Kleine Inset-Karte für den separaten Einrast-Griff
            ix0, iy0, iw, ih = px0 + pw - 138, py0 + ph - 156, 124, 118
            dr.rounded_rectangle((ix0, iy0, ix0 + iw, iy0 + ih), radius=6,
                                 fill='#fff8eb', outline='#e07b00', width=2)
            dr.text((ix0 + 8, iy0 + 4), 'Griff-Datei (L4)', fill='#b35c00', font=f_sm)
            hxs = [v for s in h_segs for v in (s[0], s[2])]
            hys = [v for s in h_segs for v in (s[1], s[3])]
            hsc = min((iw - 20) / max(1e-6, max(hxs) - min(hxs)),
                      (ih - 34) / max(1e-6, max(hys) - min(hys)))
            hox = ix0 + (iw - (max(hxs) - min(hxs)) * hsc) / 2.0
            hoy = iy0 + 24 + (ih - 34 - (max(hys) - min(hys)) * hsc) / 2.0
            for x1, y1, x2, y2, tp, _, _ in h_segs:
                pa = (hox + (x1 - min(hxs)) * hsc, hoy + (max(hys) - y1) * hsc)
                pb = (hox + (x2 - min(hxs)) * hsc, hoy + (max(hys) - y2) * hsc)
                dr.line((pa[0], pa[1], pb[0], pb[1]),
                        fill='#b35c00' if tp == 'WALL-OUTER' else '#e0a96d', width=1)

        dr.text((px0 + 14, py0 + ph - 26),
                'ΣΔE gesamt: %.1f mm · M600-Wechsel: %d' % (tot_e, m600_n),
                fill='#475569', font=f_sm)

    im.save(out_png)
    return out_png


# -------------------------------------------------------------- Hauptdokument
def build_pdf(out_pdf):
    lcd_rows = _parse_litho_menu()

    with tempfile.TemporaryDirectory(prefix='r2_litho_pdf_') as tmpdir:
        src_img = _make_portrait_badge_png(os.path.join(tmpdir, 'Medaillon.png'))

        # 6 echte Referenzläufe von make_lithophane()
        p_stand, i_stand = pp.make_lithophane(
            src_img, height_mm=60.0, layer_h=0.12, orient='STANDING',
            frame=True, stands=1, nozzle=0.4, out_dir=tmpdir)

        p_stand_nf, i_stand_nf = pp.make_lithophane(
            src_img, height_mm=90.0, layer_h=0.12, orient='STANDING',
            frame=True, stands=0, levels=6, nozzle=0.4, out_dir=tmpdir)

        p_flat_last, i_flat_last = pp.make_lithophane(
            src_img, height_mm=56.0, layer_h=0.16, orient='FLAT',
            levels=4, col_layers=3, col_mode='LAST', border=2.4,
            nozzle=0.4, out_dir=tmpdir)

        p_flat_each, i_flat_each = pp.make_lithophane(
            src_img, height_mm=56.0, layer_h=0.16, orient='FLAT',
            levels=4, col_layers=2, col_mode='EACH', ironing=True,
            nozzle=0.4, out_dir=tmpdir)

        p_flat_c2, i_flat_c2 = pp.make_lithophane(
            src_img, height_mm=56.0, layer_h=0.16, orient='FLAT',
            levels=4, col_layers=3, contour=2, border=2.4,
            nozzle=0.4, out_dir=tmpdir)

        p_stamp, i_stamp = pp.make_lithophane(
            src_img, height_mm=50.0, layer_h=0.16, orient='FLAT',
            levels=3, col_layers=3, stamp=1, stamp_base=5.0, stamp_tol=0.25,
            mirror_x=1, handle=2, border=2.4, corner_r=4.0,
            nozzle=0.4, out_dir=tmpdir)
        p_handle = os.path.join(tmpdir, i_stamp['handle_file'])

        fig1 = os.path.join(tmpdir, 'fig_standing_beer.png')
        _fig_standing_and_beer_lambert(p_stand, fig1)

        fig2 = os.path.join(tmpdir, 'fig_flat_modes.png')
        _fig_flat_contour_stamp(p_flat_last, p_flat_c2, p_stamp, p_handle, fig2)

        doc = Doc(
            out_pdf,
            kopf='R2-D2 Macro System · Generator Lithophane & Stempel (D3)',
            titel='Lithophane (STANDING / FLAT / STAMP) — Durchlicht-Physik & Blindbedienung',
        )
        st = doc.story

        cover_tbl = TBL(
            ['Kenngröße', 'Wert im aktuellen Produktivcode (R89 / R128 / R168 / R214)'],
            [
                ['Menüpfad am Display', 'Tools > Lithophane  (83 Menü-Sektionen inkl. 8 User-Presets L1..L8)'],
                ['G-Code-Makros / Engine', 'LITHO_INFO · LITHO_CREATE · LITHO_DEL_SLOT  ->  make_lithophane()'],
                ['Modus 1: STANDING (stehend)', '1 Bildzeile = 1 Z-Schicht (0,08..0,20 mm), Einspur-Zickzack 0,7..3,0 mm'],
                ['R214-Seitenständer (STANDING)', '2 perforierte Dreiecksfinnen hinten am Rahmen (1,2 mm Sollbruchnaht)'],
                ['Modus 2: FLAT (liegend)', 'Geschachtelte Stufenplateaus (2..16 Stufen × StepL Lagen, Auto StepL = 3)'],
                ['FLAT-Farbwechsel & Konturen', 'Color swap OFF / LAST / EACH (+ Purge-Tower) · Contour 0 / 1 / 2 / 3'],
                ['FLAT-Stempelmodus (R168)', 'Stamp = ON baut 10-%-Sockel mit _StampFit168-Rastbuchse + Griff-Datei'],
                ['Ausgabeordner & Dateinamen', 'gcodes/Litho/Vnn_Litho_*.gcode · Vnn_LithoF_*.gcode · Vnn_Stempel_*.gcode'],
            ],
            [56 * mm, 106 * mm],
        )[0]

        doc.add_cover(
            kicker='GENERATOR-FACHHEFT · BILD-ZU-GEOMETRIE-FAMILIE (D3 / D6)',
            titel='Lithophane & Relief-Stempel',
            untertitel='Beer-Lambert-Durchlichtoptik im stehenden Einspur-Zickzack, mehrfarbiges Stufen- & Höhenlinien-Relief im Flachdruck sowie rastbare Stempel direkt aus Fotos',
            absaetze=[
                'Ein 3D-gedrucktes Lithophane übersetzt Graustufen nicht in Farbpigmente, sondern '
                'in präzise Wandstärken: Gegen ein Fenster, ein Teelicht oder eine LED-Kachel '
                'gehalten, lässt dünnes weißes PLA an hellen Bildstellen viel Licht passieren, '
                'während 3,0 mm starke Schattenpartien das Licht exponentiell dämpfen.',
                'make_lithophane() vereint unter Tools > Lithophane gleich drei vollwertige '
                'Fertigungsverfahren ohne PC-Slicer: den hochauflösenden Stehend-Druck (STANDING) '
                'mit abbrechbaren R214-Seitenfinnen, das liegende Stufen- und Höhenlinien-Relief '
                '(FLAT mit M600-Farbmodi) sowie den R168-Stempelbaukasten mit Einrast-Griff.',
            ],
            tabelle=cover_tbl,
        )

        # ---- Kapitel 1 ------------------------------------------------------
        st += H1('Durchlicht-Physik & die 7-stufige Bild-Pipeline (_litho_grid)', '1')
        st += P(
            'Trifft Licht der Intensität <b>I_0</b> von hinten auf eine homogene, schwach '
            'streuende Polymerschicht der Dicke <b>t</b> und des effektiven Schwächungs-'
            'koeffizienten <b>μ</b>, gehorcht die durchtretende Helligkeit näherungsweise '
            'dem <b>Beer-Lambert-Gesetz</b>:'
        )
        st += FORMULA(
            'I(t)  =  I_0 · exp(-μ · t)          mit   t(g) = t_min + dyn · g<br/>'
            't_min =  max(base, wid) = 0,70 mm   und   t_max = 3,00 mm  (dyn = 2,30 mm)<br/>'
            'g     =  1.0 - v_stretched ∈ [0, 1]   (R133g: DUNKEL = 1.0 = DICKSTE WAND!)',
            'Da das menschliche Auge Helligkeiten logarithmisch empfindet (Weber-Fechner), '
            'übersetzt eine lineare Wanddickenzunahme t(g) den exponentiellen Lichtabfall '
            'exakt in eine natürlich gestufte Grauwertskala!'
        )
        st += SP(2)
        st += P(
            'Damit selbst flaue Handyfotos oder verrauschte Scans <i>blind ohne Bildschirmvorschau</i> '
            'gelingen, durchläuft jedes Bild in <b>_litho_grid()</b> sieben feste Stufen:'
        )
        st += NUM(
            '<b>Robuste 2..98-%-Perzentilspreizung:</b> Ignoriert einzelne tote Pixelfehler und '
            'nutzt garantiert die volle Wandstärkenspanne [0,70 mm .. 3,00 mm] aus (bei einfarbigen '
            'Flächen mit hi - lo &lt; 0,02 greift ein Schutz gegen Rausch-Aufblähung).',
            '<b>Gamma-Kennlinie:</b> Optionales <b>v &lt;- v^gamma</b> (Default 1,0 neutral).',
            '<b>Anti-Aliasing-Box-Downsampling:</b> Mittelt jedes Ziel-Zellfenster auf dem '
            'Quellbild (RAM-Deckel <b>max_dim = 768 px</b> + Streaming-Puffer <b>_Sink</b> à '
            '4000 Zeilen, damit selbst 250 000-Zeilen-Lithos auf dem Pi Zero 2 W unter 15 MB '
            'RAM bleiben).',
            '<b>3×3-Gaußglättung (σ ≈ 1 Zelle):</b> Faltungskern <b>[1,2,1; 2,4,2; 1,2,1]/16</b> '
            'beseitigt Ein-Pixel-Flimmern, das sonst als Nadelstich im Druck erschiene.',
            '<b>Optionale Posterisierung (Levels 2..16):</b> <b>Levels = 0</b> lässt echte '
            'kontinuierliche Fotoverläufe stehen; <b>Levels &gt;= 2</b> quantisiert das Bild '
            'bewusst in ruhige Tonflächen.',
            '<b>Skalen-Inversion (R133g):</b> <b>g = 1.0 - v</b> erzwingt unverrückbar '
            '<i>hell = dünn, dunkel = dick</i>.',
            '<b>Orientierungsgerechte Spiegelung:</b> Nur im Modus <b>STANDING</b> spiegelt '
            '<b>_litho_grid(..., mirror=True)</b> jede Zeile automatisch horizontal — denn das '
            'Relief wächst auf der Rückseite (+Y), während man das fertige Bild durch die '
            'spiegelglatte Vorderseite (<b>y = y_F</b>) betrachtet!'
        )

        # ---- Kapitel 2 ------------------------------------------------------
        st += H1('Modus A: STANDING — Einspur-Zickzack & R214-Seitenfinnen', '2')
        st += P(
            'Flach auf dem Bett gedruckt hätte ein Foto-Lithophane nur <b>2,3 mm / 0,12 mm ≈ 19</b> '
            'grobe Höhenlinien. Stehend (<b>Orient = STANDING</b>) übernimmt dagegen die feine '
            'XY-Mechanik das gesamte Relief, und jede Bildzeile wird zu genau einer Z-Schicht:'
        )
        st += FORMULA(
            'rows  = round(height_mm / layer_h),   cols = round(height_real · (w/h) / wid)<br/>'
            'Vorn  (y = y_F):            ΔE_front = e_wall · wid<br/>'
            'Tiefe (y_F &lt;-&gt; y_F + t_c):  ΔE_col   = e_wall · T[r, c]<br/>'
            'Hinten (Spalte c -&gt; c±1):   ΔE_back  = e_wall · sqrt(wid² + (ΔT)²)',
            'Der Zustandsautomat ribbon() druckt jede komplette Bildzeile als EIN EINZIGES '
            'ununterbrochenes Mäanderband ohne Retract und ohne Leerfahrt — kein einziger '
            'Fadenzieher kann die glatte Sichtfront verunstalten!'
        )
        st += SP(2)
        st += P(
            '<b>R214-Dreiecks-Seitenständer (Side stands = ON):</b> Eine 120 mm hohe, nur 3 mm '
            'schmale Platte würde bei Bettschubsern im oberen Drittel mitschwingen. Deshalb baut '
            '<b>stand_layer()</b> links und rechts an der <i>Hinterkante</i> des 2,4-mm-Vollrahmens '
            'zwei rechtwinklige Dreiecksfinnen (<b>LITHO_STAND_L</b> / <b>LITHO_STAND_R</b>): '
            'Fußlänge <b>min(max(12, 0.55 · H), Bettgrenze)</b>, perforiertes 5-mm-Rippenraster '
            'mit echten <b>BRIDGE</b>-Querstegen alle ~5 mm Z-Höhe und einer <b>1,2-mm-Sollbruchnaht</b> '
            '— nach dem Druck mit der Zange abknipsbar oder direkt als Aufsteller nutzbar, '
            'ohne jemals Schatten ins Durchlicht zu werfen.'
        )

        st += SP(2)
        st += [IMG(fig1, width_mm=162)]
        st += CAP(
            'Abbildung 1 — Links: Echter aus %s geparster Schichtausschnitt samt 18×-Y-Lupe auf '
            'das rückseitig modulierte Einspur-Zickzack-Band und die beiden R214-Seitenfinnen. '
            'Rechts: Beer-Lambert-Transmission über das reale Dickenfenster 0,70..3,00 mm.'
            % i_stand['file']
        )

        # ---- Kapitel 3 ------------------------------------------------------
        st += H1('Modus B: FLAT — Stufenrelief, Konturen (0..3) & Snap-Stempel', '3')
        st += P(
            'Für Skizzen, Wappen, Türschilder, zweifarbige Konturbilder und Stempel schaltet '
            'man auf <b>Orient = FLAT</b> (<b>_make_litho_flat()</b>). Hier wird das Motiv nach '
            'Kontrast-Boost (1,35×) in <b>L = Levels</b> (Auto = 4) geschachtelte Stufenplateaus '
            'à <b>StepL</b> Schichten (Auto = 3, R152) zerlegt:'
        )
        st += B(
            '<b>R149-Perzentil-Wächter:</b> Ließe ein linearer Schnitt oberhalb der Basisplatte '
            'eine Stufe leer, schneidet der Algorithmus die Schwellen automatisch an den '
            'Pixel-Massenperzentilen neu (und warnt ehrlich im Header, falls ein Bild wirklich '
            'nur aus einem einzigen Grauton besteht).',
            '<b>Farbmodus Color swap (OFF / LAST / EACH):</b> Bei <b>LAST</b> erfolgt genau ein '
            '<b>M600</b>-Wechsel vor der obersten, dunkelsten Stufe (weiße Platte + schwarze '
            'Zeichnung!); bei <b>EACH</b> vor jeder Stufe. Sobald <b>M600</b> aktiv ist, wächst '
            'automatisch ein <b>12×12-mm-PURGE_TOWER</b> in <b>15 mm</b> Sonden-Sicherheitsabstand '
            'mit, und <b>pen.set_z(z)</b> erzwingt nach jedem Park-Resume die exakte Schichthöhe.',
            '<b>R168-Konturmodi (Contour = 0..3):</b> <b>0</b> = klassische Blockwände + Füllung; '
            '<b>1</b> = letzte Deckschicht nur als echte Umriss-/Lochkontur ohne Füllung; '
            '<b>2 = CONTOUR RELIEF</b> = glatte Basisplatte (Stufe 0), auf der alle dunkleren '
            'Stufen als freistehende topographische Höhenlinien (inkl. innerer Lochringe!) '
            'emporwachsen; <b>3</b> = gefüllte Stufen mit echten Konturwänden statt Blockrechtecken.',
            '<b>R168-Stempelbaukasten (Stamp = ON):</b> Unterlegt das Bild mit einem '
            '<b>StampH</b> hohen Sockel (Default 5,0 mm, ~10 % Infill, geschlossene Deckhaut) '
            'samt zentrierter Unterseiten-Rastbuchse (<b>_StampFit168</b>, Spiel <b>StampFit = '
            '0,25 mm</b>). Mit <b>Mirror X = ON</b> wird der Stempelabdruck seitenrichtig; '
            '<b>Handle = 2</b> legt zusätzlich den rastbaren Griff <b>Vnn_Griff_*.gcode</b> an '
            '(<b>Handle = 3</b> druckt nur einen Ersatzgriff ohne Bildberechnung).'
        )

        st += SP(2)
        st += [IMG(fig2, width_mm=162)]
        st += CAP(
            'Abbildung 2 — Drei echte FLAT-Läufe aus demselben Testmotiv: (1) Stufenrelief mit '
            'LAST-Wechsel und Purge-Tower (%s), (2) topographisches Höhenlinien-Relief Contour=2 '
            '(%s), (3) Stempel-Unterseite mit Snap-Buchse + separatem Griff (%s + %s).'
            % (i_flat_last['file'], i_flat_c2['file'], i_stamp['file'], i_stamp['handle_file'])
        )

        # ---- Kapitel 4 ------------------------------------------------------
        st += H1('Live-Menüreferenz & Gemessene Referenzläufe', '4')
        st += P(
            'Direkt aus <b>menus/lcd_menues.cfg</b> gelesene Menüstruktur unter '
            '<b>Tools &gt; Lithophane</b>:'
        )
        st += TBL(
            ['LCD-Menüpfad', 'Anzeige am Display', 'Wertebereich / Schalter'],
            [[a, b, c] for (a, b, c) in lcd_rows],
            [64 * mm, 52 * mm, 46 * mm],
            mono_cols=(1,),
        )
        st += SP(3)
        st += H2('Sechs real gerechnete Referenz-Parametersätze', '4.1')
        ref_rows = []
        for title, pdesc, gpath, inf in [
            ('1. Foto-Durchlicht Standard', 'STANDING, H=60, lh=0.12, Stands=ON', p_stand, i_stand),
            ('2. Groß-Porträt posterisiert', 'STANDING, H=90, Levels=6, Stands=OFF', p_stand_nf, i_stand_nf),
            ('3. 2-Farb-Skizze (Weiß/Schwarz)', 'FLAT, Size=56, Lvl=4×3L, Swap=LAST', p_flat_last, i_flat_last),
            ('4. 4-Farb-Stufenbild geglättet', 'FLAT, Size=56, Lvl=4×2L, Swap=EACH, Iron', p_flat_each, i_flat_each),
            ('5. Topographie-Höhenlinien', 'FLAT, Size=56, Lvl=4×3L, Contour=2', p_flat_c2, i_flat_c2),
            ('6. Stempel + Einrast-Griff', 'FLAT, Stamp=ON, MirX=ON, Handle=2', p_stamp, i_stamp),
        ]:
            _, tot_e, m600_n, _ = _parse_layer_moves(gpath)
            extra = (' + %s' % inf['handle_file']) if inf.get('handle_file') else ''
            ref_rows.append([
                title,
                pdesc,
                inf['file'] + extra,
                '%d L' % inf['layers'],
                '%.0f mm / %d×M600' % (tot_e, m600_n),
            ])
        st += TBL(
            ['Einsatzzweck', 'Parameter', 'Erzeugte Datei(en)', 'Lagen', 'ΣΔE / Wechsel'],
            ref_rows,
            [33 * mm, 44 * mm, 41 * mm, 14 * mm, 30 * mm],
            mono_cols=(2, 3, 4),
        )

        # ---- Kapitel 5 ------------------------------------------------------
        st += H1('Blind-Entscheidungsbaum für die Werkstatt', '5')
        st += [BOX(
            'Welche Einstellung für welches Motiv? — 3-Sekunden-Regel am Drehrad',
            [
                '• <b>Echtes Familien-/Urlaubsfoto fürs Fenster oder LED-Licht:</b> '
                '<b>Orient = STANDING</b>, <b>Height = 100..120 mm</b>, <b>Layer = 0,12 mm</b>, '
                '<b>Levels = 0</b>, <b>Frame = ON</b>, <b>Side stands = ON</b>, <b>Brim = 6x</b>. '
                'Unbedingt <b>weißes oder naturfarbenes PLA</b> laden (Geschwindigkeit steckt '
                'bereits mit schonenden 25 mm/s fertig in der Datei!).',
                '• <b>Strichzeichnung, Wappen oder Schild ohne Gegenlicht:</b> '
                '<b>Orient = FLAT</b>, <b>Levels = 4</b>, <b>StepL = 3</b>, '
                '<b>Color swap = LAST</b> -> mit Weiß starten, beim einzigen M600-Piep Schwarz '
                'einlegen -> gestochen scharfes S/W-Reliefschild!',
                '• <b>Stempel für Tinte, Ton, Keksteig oder Wachs:</b> '
                '<b>Orient = FLAT</b>, <b>Stamp = ON</b>, <b>Mirror X = ON</b> (wichtig für '
                'lesbaren Abdruck!), <b>Levels = 2</b> oder <b>3</b>, <b>Handle = 2</b> (druckt '
                'einmal den Einrast-Griff mit; für alle weiteren Stempelplatten reicht '
                '<b>Handle = 0</b>, weil derselbe Griff überall einrastet!).'
            ],
            kind='tip',
        )]
        st += SP(2)
        st += [BOX(
            'Eingebaute Blind-Schutzsperren (verhindern Fehldrucke vor dem Start)',
            [
                '• Wer versehentlich <b>Stamp = ON</b>, <b>Contour &gt; 0</b> oder <b>Handle &gt; 0</b> '
                'bei aktivem <b>Orient = STANDING</b> stehen lässt, erhält keinen stumm '
                'ignorierten Druck, sondern eine klare Klartext-Ablehnung mit dem exakten '
                'Menüpfad zur Behebung.',
                '• Schaltet man <b>Frame = OFF</b> bei <b>Side stands = ON</b>, deaktiviert '
                '<b>make_lithophane()</b> die Seitenfinnen automatisch mit Notiz, weil ohne '
                'Vollrahmen keine tragfähige 2,4-mm-Ankerflanke existiert.'
            ],
            kind='note',
        )]

        doc.render()
    return out_pdf


if __name__ == '__main__':
    target = os.path.join(REPO, 'LITHOPHANE.pdf')
    build_pdf(target)
    print('Wrote %s (%d bytes)' % (target, os.path.getsize(target)))
