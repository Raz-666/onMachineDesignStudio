#!/usr/bin/env python3
# -*- coding: utf-8 -*-
""" make_cableties_pdf.py — Wissenschaftliches Generator-Fachheft (D3 / D6):
    Kabelbinder & Perlen-Schlaufenbinder (Tools > Cable ties -> make_cable_ties()).

    Alle Abbildungen und Referenzläufe werden zur Bauzeit LIVE aus make_cable_ties()
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
    Doc, H1, H2, P, B, FORMULA, TBL, BOX, IMG, CAP, SP, PageBreak, font,
)
from r2_version import VERSION as R2VER  # noqa: E402


# ------------------------------------------------------- Echter G-Code-Parser
def _parse_gcode(gcode_path):
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
            if s == ';LAYER_CHANGE' or s.startswith(';LAYER:'):
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
                eff_l = max(1, cur_layer)
                layers.setdefault(eff_l, []).append((x, y, nx, ny, cur_type))
                layer_z.setdefault(eff_l, nz)
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
def _clean_lcd_label(nm):
    s = nm.strip().strip("'")
    if 'tie_variant' in s and 'Closure:' in s:
        return 'Closure: CLASSIC / LOOP'
    if 'tie_brim' in s or s.startswith('Brim:'):
        return 'Brim: ON / off (nur am Kopf)'
    if 'AGAIN = start' in s:
        return '> Create (2x = Start)'
    s = re.sub(r"\{[^{}]*\}", '', s)
    s = re.sub(r'\s+', ' ', s).strip(' *')
    return s or 'Auswahl'


def _parse_ties_menu():
    cfg_path = os.path.join(REPO, 'menus', 'lcd_menues.cfg')
    txt = open(cfg_path, encoding='utf-8').read()
    blocks = re.split(r'(?m)^(?=\[menu )', txt)
    secs = [b for b in blocks if b.startswith('[menu __main __gen __cable')]
    rows = []
    seen_usr = False
    for sec in secs:
        lines = [l.strip() for l in sec.strip().splitlines() if l.strip()]
        hdr = lines[0].strip('[]').replace('menu __main __gen __cable', 'Tools > Cable ties')
        if '__usr' in hdr:
            if not seen_usr:
                seen_usr = True
                rows.append((
                    'Tools > Cable ties > usr > [P1..P8]',
                    'My presets (Save / Load / Delete)',
                    'Seitenweise je 8 eigene Sätze',
                ))
            continue
        if any(hdr.endswith(suf) for suf in ('__var __cla', '__var __loo')):
            continue
        nm = mn = mx = st = tp = ''
        for ln in lines[1:]:
            if ln.startswith('type:'):
                tp = ln.split(':', 1)[1].strip()
            elif ln.startswith('name:'):
                nm = ln.split(':', 1)[1].strip()
            elif ln.startswith('input_min:'):
                mn = ln.split(':', 1)[1].strip()
            elif ln.startswith('input_max:'):
                mx = ln.split(':', 1)[1].strip()
            elif ln.startswith('input_step:'):
                st = ln.split(':', 1)[1].strip()
        label = _clean_lcd_label(nm)
        if tp == 'input' and mn and mx:
            rng = '%s..%s (Schritt %s)' % (mn, mx, st or '1')
        elif '__var' in hdr:
            rng = 'CLASSIC (Sperrklinke) · LOOP (Perlen)'
        elif '__brim' in hdr:
            rng = 'Toggle (2 Ringe nur um den Kopf)'
        elif tp == 'list':
            rng = 'Untermenü'
        else:
            rng = 'Kommando / 2-Takt-Start'
        rows.append((hdr.replace(' __', ' > '), label, rng))
    return rows


# ------------------------------------------------------- Abbildungen (D6)
def _clip_seg_rect(x0, y0, x1, y1, wx0, wy0, wx1, wy1):
    """Liang-Barsky exact segment clipping to [wx0, wx1] x [wy0, wy1]."""
    dx, dy = x1 - x0, y1 - y0
    t0, t1 = 0.0, 1.0
    for p, q in ((-dx, x0 - wx0), (dx, wx1 - x0), (-dy, y0 - wy0), (dy, wy1 - y0)):
        if abs(p) < 1e-12:
            if q < 0.0:
                return None
        else:
            r = q / p
            if p < 0.0:
                if r > t1:
                    return None
                if r > t0:
                    t0 = r
            else:
                if r < t0:
                    return None
                if r < t1:
                    t1 = r
    return (x0 + t0 * dx, y0 + t0 * dy, x0 + t1 * dx, y0 + t1 * dy)


def _draw_window_toolpath(dr, parsed, box, world_win, layer_specs, pad=16):
    """Render real gcode segments clipped strictly to world_win = (wx0, wy0, wx1, wy1)."""
    bx0, by0, bx1, by1 = box
    wx0, wy0, wx1, wy1 = world_win
    span_x = max(1.0, wx1 - wx0)
    span_y = max(1.0, wy1 - wy0)
    sc = min((bx1 - bx0 - 2 * pad) / span_x, (by1 - by0 - 2 * pad) / span_y)
    ox = (bx0 + bx1 - span_x * sc) / 2.0
    oy = (by0 + by1 + span_y * sc) / 2.0

    def tx(x, y):
        return (ox + (x - wx0) * sc, oy - (y - wy0) * sc)

    for ln, col_map, lw in layer_specs:
        for sx0, sy0, sx1, sy1, tp in parsed['layers'].get(ln, ()):
            cl = _clip_seg_rect(sx0, sy0, sx1, sy1, wx0, wy0, wx1, wy1)
            if cl is None:
                continue
            c = col_map.get(tp, col_map.get('*', (70, 95, 130)))
            dr.line([tx(cl[0], cl[1]), tx(cl[2], cl[3])], fill=c, width=lw)


def _all_bbox(parsed):
    xs, ys = [], []
    for segs in parsed['layers'].values():
        for x0, y0, x1, y1, _t in segs:
            xs.extend((x0, x1))
            ys.extend((y0, y1))
    return (min(xs), min(ys), max(xs), max(ys)) if xs else (0, 0, 100, 100)


def _render_fig1(p_cla, p_loo, out_png):
    """Abb. 1: Lupenansicht der echten G-Code-Bahnen am Verschlusskopf & Bandanfang:
    CLASSIC (Kopf-Brim, Kanal, Sperrklinke & asymmetrische 2-Lagen-Rastzähne) vs.
    LOOP (offene Rahmenschlaufe + seitliche 45°-Rastperlen) + Längsschnitt."""
    W, H = 1800, 930
    im = PILImage.new('RGB', (W, H), (250, 252, 255))
    dr = ImageDraw.Draw(im)

    # Panel A: CLASSIC head + first 38 mm of strap (real gcode zoom)
    pa = (24, 58, 882, 535)
    dr.rounded_rectangle(pa, radius=12, fill=(255, 255, 255), outline=(185, 202, 224), width=2)
    dr.text((34, 20), 'A · CLASSIC-Sperrklinke (Kopf + Sägezahn-Rastung)',
            fill=(28, 78, 140), font=font(21, bold=True))

    cx0, cy0, _cx1, cy1 = _all_bbox(p_cla)
    win_cla = (cx0 - 2.5, cy0 - 2.5, cx0 + 46.0, cy1 + 2.5)
    _draw_window_toolpath(
        dr, p_cla, (pa[0] + 16, pa[1] + 12, pa[2] - 16, pa[3] - 92), win_cla,
        [
            (1, {'BRIM': (150, 175, 205), '*': (188, 208, 232)}, 2),
            (3, {'*': (72, 118, 182), 'WALL-OUTER': (28, 78, 140), 'OUTER WALL': (28, 78, 140)}, 2),
            (4, {'*': (224, 123, 0)}, 3),   # Tooth base layer (layers+1)
            (5, {'*': (179, 38, 30)}, 3),   # Steep lock flank (+0.6 mm shifted, layers+2)
            (9, {'INNER WALL': (30, 125, 50), 'WALL-INNER': (30, 125, 50), '*': (120, 165, 210)}, 3),  # Pawl bridge!
        ],
        pad=18,
    )
    ly = pa[3] - 78
    dr.text((pa[0] + 20, ly),
            'Grau: Kopf-Brim (L1, Band gratfrei!)  |  Grün (L9): Sperrklinken-Brücke',
            fill=(35, 50, 68), font=font(16, bold=True))
    dr.text((pa[0] + 20, ly + 30),
            'Orange (L4) + Rot (L5, +0,6 mm): Asymmetrisches Sägezahnprofil',
            fill=(145, 35, 24), font=font(16, bold=True))

    # Panel B: LOOP frame + first 48 mm of beaded strap (real gcode zoom)
    pb = (906, 58, 1776, 535)
    dr.rounded_rectangle(pb, radius=12, fill=(255, 255, 255), outline=(185, 202, 224), width=2)
    dr.text((918, 20), 'B · LOOP-Mehrwegschlaufe (Rahmen + 45°-Rastperlen)',
            fill=(28, 78, 140), font=font(21, bold=True))

    lx0, ly0, _lx1, ly1 = _all_bbox(p_loo)
    win_loo = (lx0 - 2.5, ly0 - 2.5, lx0 + 52.0, ly1 + 2.5)
    _draw_window_toolpath(
        dr, p_loo, (pb[0] + 16, pb[1] + 12, pb[2] - 16, pb[3] - 92), win_loo,
        [
            (1, {'BRIM': (150, 175, 205), '*': (196, 214, 236)}, 2),
            (3, {'WALL-OUTER': (28, 78, 140), 'OUTER WALL': (28, 78, 140),
                 'WALL-INNER': (224, 123, 0), 'INNER WALL': (224, 123, 0),
                 '*': (150, 184, 222)}, 3),
            (5, {'WALL-OUTER': (0, 112, 107), 'OUTER WALL': (0, 112, 107), '*': (0, 112, 107)}, 3),
        ],
        pad=18,
    )
    dr.text((pb[0] + 20, ly),
            'Türkis (L4..5): +2 Lagen Schlaufenrahmen  |  Orange: Schlitz (w + 0,4 mm)',
            fill=(0, 92, 88), font=font(16, bold=True))
    dr.text((pb[0] + 20, ly + 30),
            'Blau (L1..3): Band mit beidseitigen 45°-Perlen (+0,5 mm je Seite)',
            fill=(28, 78, 140), font=font(16, bold=True))

    # Panel C bottom: Exact longitudinal Z-cross-section of CLASSIC head + teeth
    pc = (24, 570, 1776, 908)
    dr.rounded_rectangle(pc, radius=12, fill=(255, 255, 255), outline=(185, 202, 224), width=2)
    dr.text((44, 584),
            'C · Maßstäblicher Längsschnitt durch CLASSIC-Verschlusskopf & Sägezahn-Rastung (layers = 3 -> 10 Lagen gesamt)',
            fill=(28, 78, 140), font=font(20, bold=True))

    bz0 = 858
    dr.line([(70, bz0), (1730, bz0)], fill=(90, 95, 105), width=3)
    dr.text((78, bz0 + 10), 'Druckbett Z = 0,00 mm   (Kopf links: L1..L2 Boden · L3..L8 Kanal · L9 Sperrklinke · L10 Decke)',
            fill=(88, 89, 91), font=font(17))

    lh_p = 21
    hx0, hx1 = 120, 560
    # Head floor L1..L2
    for k in range(2):
        yb = bz0 - k * lh_p
        dr.rectangle([hx0, yb - lh_p + 2, hx1, yb], fill=(195, 214, 238), outline=(28, 78, 140), width=1)
    # Side wall background hatched lightly L3..L8 (open channel in middle)
    for k in range(2, 8):
        yb = bz0 - k * lh_p
        dr.rectangle([hx0, yb - lh_p + 2, hx1, yb], fill=(240, 246, 253), outline=(185, 204, 228), width=1)
    dr.text((hx0 + 110, bz0 - 5 * lh_p - 6), 'Offener Durchschubkanal (layers + 3)',
            fill=(75, 92, 115), font=font(16))
    # Ceiling L9: Pawl bridge at entry (hx0+45 .. hx0+165)
    yb9 = bz0 - 8 * lh_p
    dr.rectangle([hx0 + 48, yb9 - lh_p + 2, hx0 + 178, yb9], fill=(182, 230, 192), outline=(30, 125, 50), width=2)
    dr.text((hx0 + 192, yb9 - 20), 'L9: Sperrklinke (Pawl) ragt 1 Lage in den Kanal!',
            fill=(24, 108, 42), font=font(18, bold=True))
    # Ceiling L10 side frame top
    yb10 = bz0 - 9 * lh_p
    dr.rectangle([hx0, yb10 - lh_p + 2, hx1, yb10], fill=(220, 233, 248), outline=(28, 78, 140), width=1)

    # Strap L1..L3 (x = 560 .. 1690)
    sx0, sx1 = 560, 1690
    for k in range(3):
        yb = bz0 - k * lh_p
        dr.rectangle([sx0, yb - lh_p + 2, sx1, yb], fill=(182, 206, 238), outline=(28, 78, 140), width=1)
    # Asymmetric 2-layer teeth on L4 and L5 (+0.6 mm shifted right -> gentle ramp left, vertical lock right!)
    tx = sx0 + 110
    while tx + 88 < sx1 - 120:
        yb4 = bz0 - 3 * lh_p
        yb5 = bz0 - 4 * lh_p
        dr.rectangle([tx, yb4 - lh_p + 2, tx + 78, yb4], fill=(250, 206, 150), outline=(195, 98, 0), width=1)
        dr.rectangle([tx + 30, yb5 - lh_p + 2, tx + 78, yb5], fill=(244, 168, 162), outline=(165, 28, 22), width=1)
        tx += 145
    dr.text((sx0 + 115, bz0 - 6 * lh_p - 12),
            'Einschubrichtung nach links: flache Rampe gleitet unter der Klinke durch, steile Rückflanke sperrt!',
            fill=(145, 35, 24), font=font(18, bold=True))

    im.save(out_png, 'PNG')
    return out_png


def _render_fig2(p_bundle, out_png):
    """Abb. 2: Komplettplatten-Layout eines 6er-Bündels (TIE_1..TIE_6) +
    automatische Verschluss-Skalierung & Mindest-Biegeradius über Bandbreite."""
    W, H = 1800, 740
    im = PILImage.new('RGB', (W, H), (250, 252, 255))
    dr = ImageDraw.Draw(im)

    pa = (24, 58, 910, 712)
    dr.rounded_rectangle(pa, radius=12, fill=(255, 255, 255), outline=(185, 202, 224), width=2)
    dr.text((38, 18), 'A · 6er-Bündel auf einer Platte (120×6 mm CLASSIC, TIE_1..TIE_6)',
            fill=(28, 78, 140), font=font(22, bold=True))

    bx0, by0, bx1, by1 = _all_bbox(p_bundle)
    _draw_window_toolpath(
        dr, p_bundle, (pa[0] + 14, pa[1] + 12, pa[2] - 14, pa[3] - 68),
        (bx0 - 2.0, by0 - 2.0, bx1 + 2.0, by1 + 2.0),
        [
            (1, {'BRIM': (155, 180, 208), '*': (182, 204, 232)}, 2),
            (3, {'WALL-OUTER': (28, 78, 140), 'OUTER WALL': (28, 78, 140), '*': (145, 178, 218)}, 2),
            (5, {'*': (224, 123, 0)}, 2),
        ],
        pad=18,
    )
    dr.text((pa[0] + 22, pa[3] - 48),
            'Jeder Binder = eigenes EXCLUDE_OBJECT · Brim nur an den 6 Köpfen links!',
            fill=(45, 55, 68), font=font(18, bold=True))

    pb = (934, 58, 1776, 712)
    dr.rounded_rectangle(pb, radius=12, fill=(255, 255, 255), outline=(185, 202, 224), width=2)
    dr.text((946, 20), 'B · Selbstskalierende Maße über Breite (2..12 mm)',
            fill=(28, 78, 140), font=font(21, bold=True))

    gx0, gy0, gx1, gy1 = 1020, 120, 1728, 465
    dr.rectangle([gx0, gy0, gx1, gy1], fill=(247, 250, 254), outline=(170, 188, 212), width=2)
    for w_mm in range(2, 13, 2):
        xp = gx0 + (w_mm - 2.0) / 10.0 * (gx1 - gx0)
        dr.line([(xp, gy0), (xp, gy1)], fill=(226, 233, 242), width=1)
        dr.text((xp - 10, gy1 + 8), '%d' % w_mm, fill=(75, 82, 92), font=font(16))
    for v_mm in (0, 4, 8, 12, 16):
        yp = gy1 - (v_mm / 18.0) * (gy1 - gy0)
        dr.line([(gx0, yp), (gx1, yp)], fill=(226, 233, 242), width=1)
        dr.text((gx0 - 38, yp - 9), '%d' % v_mm, fill=(75, 82, 92), font=font(16))

    pts_hl = []
    pts_hw = []
    pts_bg = []
    pts_pt = []
    for w10 in range(20, 121, 2):
        wv = w10 / 10.0
        hl = max(8.0, wv + 4.5)
        hw = max(6.0, wv + 2.6)
        bg = max(3.0, wv * 0.5 + 1.5)
        pt = max(2.0, round(0.45 * wv, 1))
        xp = gx0 + (wv - 2.0) / 10.0 * (gx1 - gx0)
        pts_hl.append((xp, gy1 - (hl / 18.0) * (gy1 - gy0)))
        pts_hw.append((xp, gy1 - (hw / 18.0) * (gy1 - gy0)))
        pts_bg.append((xp, gy1 - (bg / 18.0) * (gy1 - gy0)))
        pts_pt.append((xp, gy1 - (pt / 18.0) * (gy1 - gy0)))

    dr.line(pts_hl, fill=(28, 78, 140), width=4)
    dr.line(pts_hw, fill=(0, 112, 107), width=4)
    dr.line(pts_bg, fill=(224, 123, 0), width=4)
    dr.line(pts_pt, fill=(179, 38, 30), width=4)
    dr.text((gx0 + 205, gy1 + 32), 'Bandbreite width [mm]', fill=(55, 65, 78), font=font(17, bold=True))

    ly2 = 528
    dr.text((956, ly2), 'Blau: Kopflänge HL = max(8, w+4,5)  |  Türkis: Kopfbreite HW = max(6, w+2,6)',
            fill=(28, 78, 140), font=font(16, bold=True))
    dr.text((956, ly2 + 34), 'Orange: LOOP-Perlenabstand 0,5·w+1,5  |  Rot: CLASSIC-Pitch 0,45·w',
            fill=(165, 52, 20), font=font(16, bold=True))
    dr.rounded_rectangle([952, ly2 + 74, 1756, 692], radius=8, fill=(238, 245, 253), outline=(140, 172, 210), width=2)
    dr.text((968, ly2 + 88), 'Biegedehnung im Band:  ε_max = t_strap / (2 · R_min)',
            fill=(28, 78, 140), font=font(18, bold=True))
    dr.text((968, ly2 + 120), 'PETG/TPU: R_min ab ~4 mm (enge Bäume) · PLA: R_min >= 18 mm (sanfte Bögen)',
            fill=(45, 55, 68), font=font(16))

    im.save(out_png, 'PNG')
    return out_png


# ------------------------------------------------------- PDF-Bau
def build_pdf(out_pdf):
    lcd_rows = _parse_ties_menu()

    with tempfile.TemporaryDirectory(prefix='r2_ties_pdf_') as td:
        f_cla1, i_cla1 = pp.make_cable_ties(
            count=1, length=90, width=8.0, layers=3, variant='CLASSIC',
            brim=True, nozzle=0.4, out_dir=td,
        )
        f_loo1, i_loo1 = pp.make_cable_ties(
            count=1, length=95, width=7.0, layers=3, variant='LOOP',
            brim=True, nozzle=0.4, out_dir=td,
        )
        f_bun6, i_bun6 = pp.make_cable_ties(
            count=6, length=120, width=6.0, layers=3, variant='CLASSIC',
            brim=True, nozzle=0.4, out_dir=td,
        )
        _f_mic, i_mic = pp.make_cable_ties(
            count=10, length=80, width=3.0, layers=3, variant='CLASSIC',
            brim=True, nozzle=0.4, out_dir=td,
        )
        _f_hvy, i_hvy = pp.make_cable_ties(
            count=4, length=190, width=10.0, layers=5, variant='LOOP',
            brim=False, material='PETG', nozzle=0.4, out_dir=td,
        )

        p_cla1 = _parse_gcode(f_cla1)
        p_loo1 = _parse_gcode(f_loo1)
        p_bun6 = _parse_gcode(f_bun6)

        fig1 = _render_fig1(p_cla1, p_loo1, os.path.join(td, 'ties_fig1.png'))
        fig2 = _render_fig2(p_bun6, os.path.join(td, 'ties_fig2.png'))

        doc = Doc(
            out_pdf,
            'R2-D2 · Cable Ties (make_cable_ties)',
            'Wissenschaftliche Generator-Referenz (D3 / D6)',
        )
        st = doc.story

        cover_tbl = TBL(
            ['Kenngröße', 'Wert im R2-D2-System (Code-Wahrheit aus r2_postproc.py)'],
            [
                ['LCD-Menüpfad', 'Tools &gt; Cable ties (Makros: CABLE_TIE_GENERATE · GEN_CABLE_TIES · CABLE_TIE_INFO)'],
                ['Ausgabeordner', 'gcodes/CableTies/Vnn_Ties_&lt;Len&gt;x&lt;Wid&gt;_CLA|LOO.gcode'],
                ['Zwei Verschlussarten', 'CLASSIC (Einweg-Sperrklinke, fest ziehend) · LOOP (wiederlösbare Perlen-Schlaufe)'],
                ['Maßbereich & Bündel', 'Count = 1..24 Stück · Länge = 50..300 mm · Breite = 2..12 mm · 3..6 Bandlagen'],
                ['Selbstskalierung', 'Kopfgröße, Durchsteckschlitz, Zahnteilung & Perlenabstand folgen exakt der Breite'],
                ['Selektiver Kopf-Brim', 'Brim umschließt nur den kleinen Kopf (HL×HW) — das Band bleibt zu 100 % gratfrei!'],
            ],
            [54 * mm, 108 * mm],
        )[0]

        doc.add_cover(
            kicker='GENERATOR-FACHHEFT · WERKSTATT & BEFESTIGUNG (D3 / D6)',
            titel='Cable Ties (CLASSIC & LOOP)',
            untertitel='Selbstskalierende Einweg-Rastkabelbinder und wiederverwendbare Perlen-Schlaufenbinder mit selektivem Kopf-Brim, Kanal-Fadenwächter und Einzelobjekt-Abbruch',
            absaetze=[
                'Gedruckte Kabelbinder scheitern bei herkömmlichen STL-Modellen oft am Slicer: '
                'Wird das Modell skaliert, klemmt der Durchsteckkanal zu oder die Rastzähne '
                'verschmelzen; schaltet man Brim ein, muss man anschließend 200 mm feine '
                'Zahnflanken mühsam mit dem Messer entgraten. make_cable_ties() berechnet '
                'Verschlusskopf, Spaltmaß, Zahnteilung und Perlengeometrie direkt aus der '
                'gewählten Bandbreite und legt den Brim ausschließlich um den Kopf.',
                'Zur Wahl stehen zwei kinematisch grundverschiedene Verschlüsse: CLASSIC mit '
                'überbrückter Sperrklinke und zweistufigem Sägezahnprofil für dauerhafte '
                'Montagen sowie LOOP mit offener Rahmenschlaufe und seitlichen 45°-Rastperlen, '
                'die sich beliebig oft nachspannen und zerstörungsfrei wieder öffnen lassen.',
            ],
            tabelle=cover_tbl,
        )

        # ---- Kapitel 1 ------------------------------------------------------
        st += H1('Biegemechanik dünner Bänder & Selbstskalierende Verschlüsse', '1')
        st += P(
            'Ein Kabelbinder arbeitet als dünner Biegebalken der Banddicke '
            '<b>t_strap = first_h + (layers − 1) · LH</b> (bei 3 Lagen à 0,20 mm und '
            '0,28 mm Startschicht exakt <b>0,68 mm</b>). Wird das Band um einen Kabelbaum '
            'mit Radius <b>R</b> gelegt, beträgt die Randfaserdehnung:'
        )
        st += FORMULA(
            'Randfaserdehnung:   ε_max = t_strap / (2 · R)    &lt;=&gt;    R_min = t_strap / (2 · ε_zul)<br/>'
            'CLASSIC-Kopfmaß:    HL = max(8,0, width + 4,5) mm,   HW = max(6,0, width + 2,6) mm<br/>'
            'CLASSIC-Schlitz:    slot_w = width + 0,50 mm (0,25 mm Spiel/Seite),  H_Kopf = layers + 7 Lagen<br/>'
            'Sägezahn-Rastung:   pitch = max(2,0, 0,45 · width),  L_Zahn = min(1,6, 0,55 · pitch),  Δx_Flanke = +0,6 mm<br/>'
            'LOOP-Perlenraster:  hole_w = width + 0,40 mm,  Perlen-Übermaß = width + 1,00 mm (+0,5 mm/Seite)',
            'Physikalische Materialwahl: PETG (ε_zul ~ 4..5 %) und TPU (ε_zul &gt; 20 %) erlauben '
            'bei t_strap = 0,68 mm enge Biegeradien ab 4..8 mm ohne Weißbruch. Reines PLA '
            '(ε_zul ~ 1,8 %) eignet sich nur für große Schlaufenradien ab ca. 18 mm.'
        )
        st += B(
            '<b>CLASSIC — Asymmetrischer 2-Lagen-Sägezahn + Decken-Sperrklinke:</b> Auf '
            'Schicht <b>layers + 1</b> druckt der Generator die volle Zahnbasis '
            '<b>L_Zahn</b>; auf <b>layers + 2</b> versetzt er die Zahnkuppe um '
            '<b>+0,6 mm</b> Richtung Bandspitze. Dadurch entsteht vorn eine sanfte '
            'Auflauframpe und hinten eine senkrechte Sperrflanke, in die auf der ersten '
            'Deckschicht des Kopfes (<b>cl = 1</b>) die frei über den Kanal gespannte '
            'Sperrklinke (<b>Pawl</b>) einrastet.',
            '<b>LOOP — Elastische Schnapp-Perlen (wiederverwendbar):</b> Das Band trägt '
            'beidseitig 45°-angeschrägte Perlen (Gesamtbreite <b>width + 1,0 mm</b>), '
            'während der Rahmenschlitz <b>width + 0,4 mm</b> misst. Beim Durchziehen '
            'federt jede Perle mit <b>0,6 mm</b> Übermaß hörbar durch den Rahmen, hält '
            'unter Zug formschlüssig und lässt sich seitlich jederzeit wieder ausheben.'
        )
        st += [IMG(fig1, width_mm=162)]
        st += CAP(
            'Abbildung 1 — A &amp; B: Lupenansicht der echten G-Code-Bahnen am Verschlusskopf '
            '(CLASSIC vs. LOOP). C: Maßstäblicher Längsschnitt durch Kanal, Sperrklinke und Sägezähne.'
        )

        # ---- Kapitel 2 ------------------------------------------------------
        st += H1('Selektiver Kopf-Brim, R96-Kanalwächter & Bündel-Packung', '2')
        st += P(
            'Drei fertigungstechnische Details entscheiden in der Praxis darüber, ob ein '
            'gedrucktes Kabelbinder-Bündel sofort einsatzbereit vom Druckbett kommt:'
        )
        st += B(
            '<b>Kopf-Brim statt Voll-Brim:</b> Nur der bis zu 13 Lagen hohe Verschlusskopf '
            'besitzt ein kleines Standflächen-zu-Höhe-Verhältnis; das flache Band haftet von '
            'selbst. <b>tie_brim()</b> legt die zwei Brim-Schlaufen daher ausschließlich um '
            '<b>[x0, x0 + HL] × [y0, y0 + HW]</b> — die gesamte Verzahnung bzw. Perlenkette '
            'kommt ohne jede Nacharbeit vom Bett!',
            '<b>R96-Leerfahrt-Sperrzone im Durchsteckschlitz:</b> Sobald der Kanal oberhalb '
            'des Kopfbodens offen steht, registriert <b>make_cable_ties()</b> das Schlitz-Rechteck '
            'in <b>pen.hole_polys</b>. Jede Querfahrt zieht zwingend Filament ein, damit '
            'kein Spinnfaden den Einfädelkanal zuspinnt.',
            '<b>Ehrliche Feature-Typen (R197) &amp; Einzelobjekt-Abbruch:</b> Da <b>LOOP</b> '
            'nur Wände und Infill ohne Deckflächen druckt, meldet <b>_FILE_INFO</b> exakt die '
            'tatsächlich vorhandenen Typen. Jeder Binder trägt sein eigenes '
            '<b>EXCLUDE_OBJECT_DEFINE NAME=TIE_k</b>.'
        )
        st += [IMG(fig2, width_mm=162)]
        st += CAP(
            'Abbildung 2 — A: Reales 6er-Bündel (120×6 mm CLASSIC) mit selektivem Kopf-Brim. '
            'B: Kennlinien der selbstskalierenden Kopf-, Perlen- und Zahnmaße über width = 2..12 mm.'
        )

        # ---- Kapitel 3 ------------------------------------------------------
        st += [PageBreak()]
        st += H1('Live-Menüreferenz & Gemessene Referenzläufe', '3')
        st += P(
            'Direkt aus <b>menus/lcd_menues.cfg</b> ausgelesene Menüstruktur unter '
            '<b>Tools &gt; Cable ties</b>:'
        )
        st += TBL(
            ['LCD-Menüpfad', 'Anzeige am Display', 'Wertebereich / Aktion'],
            [[r[0], r[1], r[2]] for r in lcd_rows],
            [62 * mm, 54 * mm, 46 * mm],
        )

        st += H2('Fünf echte Referenzläufe (live beim PDF-Bau gerechnet)', '3.1')
        bench_rows = [
            ['1. Standard-Werkstattbündel', '6× · 120×6 mm · 3 L · CLASSIC · Brim',
             i_bun6['file'], 'Kopf %s · Pitch %.1f mm · %d L' % (i_bun6['head'], i_bun6['pitch'], i_bun6['layers']),
             'Grid %s (6× TIE_k)' % i_bun6['grid']],
            ['2. Einzel-Kabelbinder breit', '1× · 90×8 mm · 3 L · CLASSIC · Brim',
             i_cla1['file'], 'Kopf %s · Schlitz %.2f mm' % (i_cla1['head'], i_cla1['slot']),
             'Hohe Haltekraft, Einweg'],
            ['3. Wiederlösbare Schlaufe', '1× · 95×7 mm · 3 L · LOOP · Brim',
             i_loo1['file'], 'Rahmen %s · Perlen alle %.1f mm' % (i_loo1['head'], i_loo1['pitch']),
             'Beliebig oft lösbar!'],
            ['4. Elektronik-Mikrobinder', '10× · 80×3 mm · 3 L · CLASSIC (0,4er Düse)',
             i_mic['file'], 'Kopf %s · Pitch %.1f mm · Grid %s' % (i_mic['head'], i_mic['pitch'], i_mic['grid']),
             'Feinraster + Düsenhinweis'],
            ['5. Schwerlast-Schlauchsatz', '4× · 190×10 mm · 5 L · LOOP · PETG',
             i_hvy['file'], 'Rahmen %s · %d L · Grid %s' % (i_hvy['head'], i_hvy['layers'], i_hvy['grid']),
             '5 Bandlagen (1,08 mm stark)'],
        ]
        st += TBL(
            ['Szenario', 'Parameter', 'Erzeugte Datei', 'Verschluss & Lagen', 'Ergebnis'],
            bench_rows,
            [31 * mm, 42 * mm, 33 * mm, 32 * mm, 24 * mm],
        )

        st += SP(2)
        st += [BOX(
            'Praxis-Tipps für unzerreißbare Binder direkt vom Druckbett',
            [
                '• Materialwahl: PETG für feste Einweg- und Mehrwegbinder mit hoher Zugkraft; '
                'TPU 95A für weiche, gummierte Klett-/Kabelschlaufen (besonders mit Closure = LOOP!).',
                '• Schmale Elektronikbinder unter 3,6 mm Breite drucken mit einer 0,4-mm-Düse '
                'deutlich schärfere Rastzähne als mit einer 0,6-mm-Düse (automatischer Hinweis im Log).',
                '• Immer ganze Bündel (Count = 6..12) auf Vorrat drucken: Die Aufheiz- und '
                'Startzeit fällt nur einmal an, die reine Druckzeit pro Binder liegt bei wenigen Minuten.',
            ],
            kind='tip',
        )]

        doc.render()
    return out_pdf


if __name__ == '__main__':
    dst = os.path.join(REPO, 'CABLETIES.pdf')
    build_pdf(dst)
    print('Wrote %s (%d bytes)' % (dst, os.path.getsize(dst)))
