#!/usr/bin/env python3
# -*- coding: utf-8 -*-
""" make_gaskets_pdf.py — Wissenschaftliches Generator-Fachheft (D3 / D6):
    Nahtlose Spiral-Flanschdichtungen (Tools > Gaskets -> make_seal()).

    Alle Abbildungen und Referenzläufe werden zur Bauzeit LIVE aus make_seal()
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
        'total_e': total_e,
        'n_layers': max(layers.keys()) if layers else 0,
    }


# ------------------------------------------------------- Live-Menüextraktor
def _clean_lcd_label(nm):
    s = nm.strip().strip("'")
    if 'seal_profile' in s and 'Face:' in s:
        return 'Face: FLAT / NUT'
    if 'seal_ironing' in s or s.startswith('Ironing:'):
        return 'Ironing: ON / off (Spiral-Glättpass)'
    if 'AGAIN = start' in s:
        return '> Create (2x = Start)'
    s = re.sub(r"\{[^{}]*\}", '', s)
    s = re.sub(r'\s+', ' ', s).strip(' *')
    return s or 'Auswahl'


def _parse_seal_menu():
    cfg_path = os.path.join(REPO, 'menus', 'lcd_menues.cfg')
    txt = open(cfg_path, encoding='utf-8').read()
    blocks = re.split(r'(?m)^(?=\[menu )', txt)
    secs = [b for b in blocks if b.startswith('[menu __main __gen __seal')]
    rows = []
    seen_usr = False
    for sec in secs:
        lines = [l.strip() for l in sec.strip().splitlines() if l.strip()]
        hdr = lines[0].strip('[]').replace('menu __main __gen __seal', 'Tools > Gaskets')
        if '__usr' in hdr:
            if not seen_usr:
                seen_usr = True
                rows.append((
                    'Tools > Gaskets > usr > [P1..P8]',
                    'My presets (Save S&lt;ID&gt; / Load / Delete)',
                    'Seitenweise je 8 Dichtungsgrößen',
                ))
            continue
        if any(hdr.endswith(suf) for suf in ('__pro __fla', '__pro __nut')):
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
        elif '__pro' in hdr:
            rng = 'FLAT (vollflächig) · NUT (2 Dichtlippen)'
        elif '__iro' in hdr:
            rng = 'Toggle (15 % Fluss-Spiralglättung)'
        elif tp == 'list':
            rng = 'Untermenü'
        else:
            rng = 'Kommando / 2-Takt-Start'
        rows.append((hdr.replace(' __', ' > '), label, rng))
    return rows


# ------------------------------------------------------- Abbildungen (D6)
def _all_bbox(parsed):
    xs, ys = [], []
    for segs in parsed['layers'].values():
        for x0, y0, x1, y1, _t in segs:
            xs.extend((x0, x1))
            ys.extend((y0, y1))
    return (min(xs), min(ys), max(xs), max(ys)) if xs else (0, 0, 100, 100)


def _clip_seg_rect(x0, y0, x1, y1, wx0, wy0, wx1, wy1):
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


def _draw_window_toolpath(dr, parsed, box, world_win, layer_specs, pad=14):
    bx0, by0, bx1, by1 = box
    wx0, wy0, wx1, wy1 = world_win
    span_x = max(0.5, wx1 - wx0)
    span_y = max(0.5, wy1 - wy0)
    sc = min((bx1 - bx0 - 2 * pad) / span_x, (by1 - by0 - 2 * pad) / span_y)
    ox = (bx0 + bx1 - span_x * sc) / 2.0
    oy = (by0 + by1 + span_y * sc) / 2.0

    def tx(x, y):
        return (ox + (x - wx0) * sc, oy - (y - wy0) * sc)

    for ln, col_map, lw, skip_types in layer_specs:
        for sx0, sy0, sx1, sy1, tp in parsed['layers'].get(ln, ()):
            if skip_types and tp in skip_types:
                continue
            cl = _clip_seg_rect(sx0, sy0, sx1, sy1, wx0, wy0, wx1, wy1)
            if cl is None:
                continue
            c = col_map.get(tp, col_map.get('*', (28, 78, 140)))
            dr.line([tx(cl[0], cl[1]), tx(cl[2], cl[3])], fill=c, width=lw)


def _render_fig1(p_flat, p_nut, out_png):
    """Abb. 1: Nahtlose archimedische Spirale (FLAT inkl. 4×-Lupe auf den
    Spiral-Übergang ohne Radialnaht) vs. Doppellippen-Dichtung NUT (Decklage
    mit freier Mittelnut) + maßstäblicher Radialschnitt."""
    W, H = 1800, 920
    im = PILImage.new('RGB', (W, H), (250, 252, 255))
    dr = ImageDraw.Draw(im)

    # Panel A: FLAT spiral gasket + 4x zoom inset on upper quadrant
    pa = (24, 58, 882, 540)
    dr.rounded_rectangle(pa, radius=12, fill=(255, 255, 255), outline=(185, 202, 224), width=2)
    dr.text((38, 18), 'A · FLAT-Spiraldichtung (OD 34 / ID 18 mm — 0 Radialnähte!)',
            fill=(28, 78, 140), font=font(22, bold=True))

    fx0, fy0, fx1, fy1 = _all_bbox(p_flat)
    _draw_window_toolpath(
        dr, p_flat, (pa[0] + 12, pa[1] + 12, pa[0] + 430, pa[3] - 64),
        (fx0 - 0.8, fy0 - 0.8, fx1 + 0.8, fy1 + 0.8),
        [(1, {'*': (28, 78, 140)}, 2, None)],
        pad=14,
    )
    # 4x zoom box on right half of Panel A showing continuous spiral turns at theta=0
    zbox = (pa[0] + 448, pa[1] + 20, pa[2] - 20, pa[3] - 68)
    dr.rounded_rectangle(zbox, radius=8, fill=(246, 250, 255), outline=(224, 123, 0), width=2)
    fcx = (fx0 + fx1) / 2.0
    fcy = (fy0 + fy1) / 2.0
    # Zoom onto right annulus sector strictly inside inner sub-box (away from header/footer text!)
    _draw_window_toolpath(
        dr, p_flat, (zbox[0] + 8, zbox[1] + 38, zbox[2] - 8, zbox[3] - 36),
        (fcx + 7.8, fcy - 4.8, fx1 + 0.4, fcy + 4.8),
        [(1, {'*': (28, 78, 140)}, 3, None)],
        pad=8,
    )
    dr.text((zbox[0] + 14, zbox[1] + 8), 'Lupe auf θ = 0° (Start/Ende):',
            fill=(195, 98, 0), font=font(17, bold=True))
    dr.text((zbox[0] + 14, zbox[3] - 30), 'Δr = 0,95 · wid (keine Z-Naht!)',
            fill=(195, 98, 0), font=font(17, bold=True))
    dr.text((pa[0] + 20, pa[3] - 46),
            'Eine ununterbrochene archimedische Spirale innen -> außen (0 Leckkanäle!)',
            fill=(45, 55, 68), font=font(16, bold=True))

    # Panel B: NUT / GROOVE dual-lip gasket (top groove layer over base body)
    pb = (906, 58, 1776, 540)
    dr.rounded_rectangle(pb, radius=12, fill=(255, 255, 255), outline=(185, 202, 224), width=2)
    dr.text((920, 18), 'B · NUT-Doppellippendichtung (OD 48 / ID 24 × 2,0 mm + Ironing)',
            fill=(28, 78, 140), font=font(21, bold=True))

    nx0, ny0, nx1, ny1 = _all_bbox(p_nut)
    top_l = p_nut['n_layers']
    # Base spiral faint light-blue, top dual-lip layer bold blue + orange ironing
    _draw_window_toolpath(
        dr, p_nut, (pb[0] + 12, pb[1] + 12, pb[0] + 430, pb[3] - 64),
        (nx0 - 0.8, ny0 - 0.8, nx1 + 0.8, ny1 + 0.8),
        [
            (1, {'*': (208, 222, 240)}, 2, None),
            (top_l, {'*': (28, 78, 140)}, 2, {'IRONING'}),
        ],
        pad=14,
    )
    zbox2 = (pb[0] + 448, pb[1] + 20, pb[2] - 20, pb[3] - 68)
    dr.rounded_rectangle(zbox2, radius=8, fill=(246, 250, 255), outline=(0, 112, 107), width=2)
    ncx = (nx0 + nx1) / 2.0
    ncy = (ny0 + ny1) / 2.0
    _draw_window_toolpath(
        dr, p_nut, (zbox2[0] + 8, zbox2[1] + 38, zbox2[2] - 8, zbox2[3] - 36),
        (ncx + 10.8, ncy - 6.0, nx1 + 0.4, ncy + 6.0),
        [
            (1, {'*': (212, 224, 240)}, 2, None),
            (top_l, {'SURFACE-TOP': (28, 78, 140), 'TOP SURFACE': (28, 78, 140),
                     'IRONING': (224, 123, 0), '*': (28, 78, 140)}, 3, None),
        ],
        pad=8,
    )
    dr.text((zbox2[0] + 14, zbox2[1] + 8), 'Lupe Decklage L10 (NUT):',
            fill=(0, 102, 96), font=font(17, bold=True))
    dr.text((zbox2[0] + 14, zbox2[3] - 30), '2 Lippen (je 30 %) + 40 % Nut',
            fill=(0, 102, 96), font=font(17, bold=True))
    dr.text((pb[0] + 20, pb[3] - 46),
            'Hellblau: Körper L1..7  |  Dunkelblau + Orange: 2 Lippen + Spiral-Ironing',
            fill=(45, 55, 68), font=font(16, bold=True))

    # Panel C bottom: Radial cross-section showing flange contact pressure physics
    pc = (24, 575, 1776, 898)
    dr.rounded_rectangle(pc, radius=12, fill=(255, 255, 255), outline=(185, 202, 224), width=2)
    dr.text((44, 590),
            'C · Maßstäblicher Radialschnitt durch eine NUT-Dichtung (w_r = 12,0 mm, H = 2,0 mm -> 7 Basislagen + 3 Lippenlagen)',
            fill=(28, 78, 140), font=font(20, bold=True))

    bz0 = 845
    dr.line([(90, bz0), (1710, bz0)], fill=(90, 95, 105), width=3)
    dr.text((100, bz0 + 10), 'Unterer Flansch / Druckbett Z = 0,00 mm   |   Zentrum links (r = 0) -> Innenbohrung r_in = 12 mm -> Außenrand r_out = 24 mm',
            fill=(88, 89, 91), font=font(17))

    # Center axis on left + cross section of right ring wall (x = 485 .. 1185)
    dr.line([(160, 640), (160, bz0 + 6)], fill=(179, 38, 30), width=2)
    dr.text((172, 706), 'Symmetrieachse', fill=(179, 38, 30), font=font(17, bold=True))
    dr.text((172, 732), '(ID = 24 mm)', fill=(179, 38, 30), font=font(17))

    rx0, rx1 = 480, 1180      # wr = 700 px -> 12.0 mm
    lip_px = int(0.30 * (rx1 - rx0))
    lh_p = 18
    # L1..L7 solid base
    for k in range(7):
        yb = bz0 - k * lh_p
        dr.rectangle([rx0, yb - lh_p + 2, rx1, yb], fill=(196, 216, 240), outline=(28, 78, 140), width=1)
    # L8..L10 two raised lips (30% inner, 40% open groove, 30% outer)
    for k in range(7, 10):
        yb = bz0 - k * lh_p
        dr.rectangle([rx0, yb - lh_p + 2, rx0 + lip_px, yb], fill=(154, 190, 234), outline=(28, 78, 140), width=1)
        dr.rectangle([rx1 - lip_px, yb - lh_p + 2, rx1, yb], fill=(154, 190, 234), outline=(28, 78, 140), width=1)
    # Ironing cap highlight on both lips
    y_top = bz0 - 10 * lh_p
    dr.line([(rx0 + 4, y_top), (rx0 + lip_px - 4, y_top)], fill=(224, 123, 0), width=4)
    dr.line([(rx1 - lip_px + 4, y_top), (rx1 - 4, y_top)], fill=(224, 123, 0), width=4)

    dr.text((rx0 + 12, y_top - 28), 'Innenlippe (0,30·w_r)', fill=(28, 78, 140), font=font(17, bold=True))
    dr.text((rx0 + lip_px + 32, y_top + 10), 'Nut (0,40·w_r × 0,6 mm)', fill=(165, 35, 24), font=font(17, bold=True))
    dr.text((rx1 - lip_px + 10, y_top - 28), 'Außenlippe (0,30·w_r)', fill=(28, 78, 140), font=font(17, bold=True))

    # Formula callout box on right of Panel C
    dr.rounded_rectangle([1230, 642, 1742, 828], radius=10, fill=(238, 245, 253), outline=(135, 168, 208), width=2)
    dr.text((1250, 658), 'Flächenpressungs-Gewinn (NUT):', fill=(28, 78, 140), font=font(19, bold=True))
    dr.text((1250, 694), 'A_NUT / A_FLAT = 0,60  (für r_in ~ r_out)', fill=(35, 45, 58), font=font(18))
    dr.text((1250, 728), '=> p_NUT = F_Schraube / A_NUT = 1,67 × p_FLAT!', fill=(0, 102, 96), font=font(18, bold=True))
    dr.text((1250, 764), 'Dichtet unebene Guss-/Rohrflansche schon', fill=(55, 65, 78), font=font(17))
    dr.text((1250, 790), 'bei moderatem Anzugsmoment zuverlässig ab.', fill=(55, 65, 78), font=font(17))

    im.save(out_png, 'PNG')
    return out_png


def _render_fig2(info_fb, out_png):
    """Abb. 2: Gültigkeitsbereiche der Ringstegbreite w_r = (OD - ID)/2
    (Verweigerungsgrenze vs. automatischer NUT->FLAT-Fallback vs. Doppellippe)
    sowie exakt berechneter Anpressdruck-Faktor über Ringgeometrie."""
    W, H = 1800, 680
    im = PILImage.new('RGB', (W, H), (250, 252, 255))
    dr = ImageDraw.Draw(im)

    pa = (24, 58, 920, 650)
    dr.rounded_rectangle(pa, radius=12, fill=(255, 255, 255), outline=(185, 202, 224), width=2)
    dr.text((38, 18), 'A · Stegbreiten-Wächter w_r = (OD − ID)/2 in Abhängigkeit der Düse',
            fill=(28, 78, 140), font=font(22, bold=True))

    gx0, gy0, gx1, gy1 = 115, 118, 882, 465
    dr.rectangle([gx0, gy0, gx1, gy1], fill=(248, 250, 254), outline=(170, 188, 212), width=2)
    # X = nozzle 0.25 .. 0.85 mm, Y = radial width wr 0 .. 4.5 mm
    pts_ref = []
    pts_nut = []
    for n100 in range(25, 86, 2):
        nz = n100 / 100.0
        wid = max(0.4, nz * 1.08)
        wr_min = 2.0 * wid + 0.4
        wr_nut = 3.0 * wid + 0.8
        xp = gx0 + (nz - 0.25) / 0.60 * (gx1 - gx0)
        pts_ref.append((xp, gy1 - (wr_min / 4.5) * (gy1 - gy0)))
        pts_nut.append((xp, gy1 - (wr_nut / 4.5) * (gy1 - gy0)))

    # Shade zones via vertical bars
    for i in range(len(pts_ref) - 1):
        x_a = pts_ref[i][0]
        x_b = pts_ref[i + 1][0]
        dr.rectangle([x_a, pts_ref[i][1], x_b + 1, gy1], fill=(252, 226, 224))
        dr.rectangle([x_a, pts_nut[i][1], x_b + 1, pts_ref[i][1]], fill=(254, 240, 212))
        dr.rectangle([x_a, gy0 + 2, x_b + 1, pts_nut[i][1]], fill=(224, 244, 230))

    for nz_lbl in (0.3, 0.4, 0.5, 0.6, 0.8):
        xp = gx0 + (nz_lbl - 0.25) / 0.60 * (gx1 - gx0)
        dr.line([(xp, gy0), (xp, gy1)], fill=(210, 220, 232), width=1)
        dr.text((xp - 16, gy1 + 8), '%.1f' % nz_lbl, fill=(65, 75, 88), font=font(16))
    for wr_lbl in (0, 1, 2, 3, 4):
        yp = gy1 - (wr_lbl / 4.5) * (gy1 - gy0)
        dr.line([(gx0, yp), (gx1, yp)], fill=(210, 220, 232), width=1)
        dr.text((gx0 - 44, yp - 9), '%d mm' % wr_lbl, fill=(65, 75, 88), font=font(16))

    dr.line(pts_ref, fill=(179, 38, 30), width=4)
    dr.line(pts_nut, fill=(224, 123, 0), width=4)
    dr.text((gx0 + 18, gy0 + 18), 'GRÜN: Volles NUT-Profil (2 Dichtlippen + Mittelnut)',
            fill=(24, 108, 42), font=font(17, bold=True))
    dr.text((gx0 + 365, gy0 + 158), 'GELB: Auto-Fallback FLAT',
            fill=(155, 82, 0), font=font(17, bold=True))
    dr.text((gx0 + 365, gy0 + 184), '(w_r < 3·wid + 0,8 mm)',
            fill=(155, 82, 0), font=font(16))
    dr.text((gx0 + 18, gy1 - 38), 'ROT: w_r < 2·wid + 0,4 -> Abbruch ohne halbe Datei',
            fill=(165, 28, 22), font=font(17, bold=True))
    dr.text((gx0 + 240, gy1 + 32), 'Düsendurchmesser nozzle [mm]', fill=(45, 55, 68), font=font(17, bold=True))

    dr.text((44, 535), 'Live-Nachweis Schmalring (OD=24, ID=20,4 -> w_r=1,8 mm, Wunsch=NUT):',
            fill=(28, 78, 140), font=font(17, bold=True))
    dr.text((44, 568), '• Profil: %s  |  Log: "%s"'
            % (info_fb['profile'], info_fb['notes'][0][:54]),
            fill=(55, 65, 78), font=font(16))
    dr.text((44, 600), '• 0,6-mm-Standarddüse: FLAT ab OD−ID >= 3,4 mm, NUT ab OD−ID >= 5,5 mm.',
            fill=(55, 65, 78), font=font(16))

    # Panel B right: Exact contact area & pressure ratio across aspect ratios ID/OD
    pb = (946, 58, 1776, 650)
    dr.rounded_rectangle(pb, radius=12, fill=(255, 255, 255), outline=(185, 202, 224), width=2)
    dr.text((962, 18), 'B · Exakte Kontaktfläche A_NUT / A_FLAT & Druckfaktor',
            fill=(28, 78, 140), font=font(22, bold=True))

    # Exact formula proof: A_inner = pi*((r_in+0.3*wr)^2 - r_in^2), A_outer = pi*(r_out^2 - (r_out-0.3*wr)^2)
    # Sum = pi * [0.6*wr*(r_in + r_out)] = 0.60 * pi * (r_out^2 - r_in^2) IDENTICALLY for ALL r_in, r_out!
    dr.rounded_rectangle([976, 92, 1746, 375], radius=10, fill=(238, 245, 253), outline=(135, 168, 208), width=2)
    dr.text((998, 110), 'Exakte Invarianz für JEDES Radienpaar (r_in, r_out):',
            fill=(28, 78, 140), font=font(20, bold=True))
    dr.text((998, 152), 'A_innen = π · [(r_in + 0,3·w_r)² − r_in²]', fill=(35, 45, 58), font=font(18))
    dr.text((998, 186), 'A_außen = π · [r_out² − (r_out − 0,3·w_r)²]', fill=(35, 45, 58), font=font(18))
    dr.text((998, 224), 'A_NUT = A_innen + A_außen = π · 0,6·w_r · (r_in + r_out)', fill=(0, 102, 96), font=font(18, bold=True))
    dr.text((998, 260), '      = 0,60 · π · (r_out² − r_in²) = 0,60 · A_FLAT  (exakt!)', fill=(0, 102, 96), font=font(18, bold=True))
    dr.text((998, 304), 'Weil sich die quadratischen Terme ±0,09·w_r² exakt wegheben,',
            fill=(55, 65, 78), font=font(17))
    dr.text((998, 332), 'steigt die Flächenpressung unabhängig vom Durchmesser um +66,7 %!',
            fill=(55, 65, 78), font=font(17, bold=True))

    # Material & R96 summary card
    dr.rounded_rectangle([976, 402, 1746, 622], radius=10, fill=(248, 251, 255), outline=(180, 198, 220), width=2)
    dr.text((998, 418), 'R96-Dichtheitswächter in den Nut-Schichten:', fill=(28, 78, 140), font=font(19, bold=True))
    dr.text((998, 456), '• In allen Schichten ist r_in als Sperrkreis registriert.', fill=(45, 55, 68), font=font(17))
    dr.text((998, 488), '• Sobald die Nut beginnt (li > layers − g_lay), wird der gesamte', fill=(45, 55, 68), font=font(17))
    dr.text((998, 516), '  Nutring bis r_out − wid/2 gesperrt: Der Sprung von Innen- zu', fill=(45, 55, 68), font=font(17))
    dr.text((998, 544), '  Außenlippe zieht sauber ein und hinterlässt keinen Leckfaden!', fill=(45, 55, 68), font=font(17))
    dr.text((998, 580), '• Drucktempo ab Werk auf 10 mm/s (L1) / 15 mm/s für TPU gedrosselt.', fill=(0, 102, 96), font=font(17, bold=True))

    im.save(out_png, 'PNG')
    return out_png


# ------------------------------------------------------- PDF-Bau
def build_pdf(out_pdf):
    lcd_rows = _parse_seal_menu()

    with tempfile.TemporaryDirectory(prefix='r2_seal_pdf_') as td:
        f_flat, i_flat = pp.make_seal(
            od=34.0, id_=18.0, height=1.6, profile='FLAT', ironing=False,
            layer_h=0.2, nozzle=0.4, out_dir=td,
        )
        f_nut, i_nut = pp.make_seal(
            od=48.0, id_=24.0, height=2.0, profile='NUT', ironing=True,
            layer_h=0.2, nozzle=0.4, out_dir=td,
        )
        _f_fb, i_fb = pp.make_seal(
            od=24.0, id_=20.4, height=1.2, profile='NUT', ironing=True,
            layer_h=0.2, nozzle=0.4, out_dir=td,
        )
        _f_g34, i_g34 = pp.make_seal(
            od=24.0, id_=16.0, height=2.0, profile='FLAT', ironing=True,
            layer_h=0.2, nozzle=0.4, out_dir=td,
        )
        _f_lrg, i_lrg = pp.make_seal(
            od=110.0, id_=90.0, height=2.4, profile='NUT', ironing=True,
            layer_h=0.2, material='TPU', nozzle=0.6, out_dir=td,
        )

        p_flat = _parse_gcode(f_flat)
        p_nut = _parse_gcode(f_nut)

        fig1 = _render_fig1(p_flat, p_nut, os.path.join(td, 'seal_fig1.png'))
        fig2 = _render_fig2(i_fb, os.path.join(td, 'seal_fig2.png'))

        doc = Doc(
            out_pdf,
            'R2-D2 · Gaskets & Seals (make_seal)',
            'Wissenschaftliche Generator-Referenz (D3 / D6)',
        )
        st = doc.story

        cover_tbl = TBL(
            ['Kenngröße', 'Wert im R2-D2-System (Code-Wahrheit aus r2_postproc.py)'],
            [
                ['LCD-Menüpfad', 'Tools &gt; Gaskets (Makros: SEAL_GENERATE · GEN_SEAL · SEAL_INFO)'],
                ['Ausgabeordner', 'gcodes/Gaskets/Vnn_Seal_&lt;OD&gt;x&lt;ID&gt;x&lt;H&gt;.gcode'],
                ['Durchmesser & Höhe', 'OD = 12..200 mm · ID = 6..190 mm · Höhe = 0,4..6,0 mm (LH 0,12..0,32 mm)'],
                ['Zwei Dichtflächen', 'FLAT (vollflächig) · NUT / GROOVE (2 erhabene Lippen à 30 % + 40 % Mittelnut)'],
                ['Nahtfreie Bahnführung', 'Eine durchgehende archimedische Spirale pro Band (Δr = 0,95·wid, 0 Radialnähte!)'],
                ['TPU-Profil & Presets', '10/15 mm/s Schleichgang · Spiral-Ironing (15 % Fluss) · My presets (S&lt;ID&gt;)'],
            ],
            [54 * mm, 108 * mm],
        )[0]

        doc.add_cover(
            kicker='GENERATOR-FACHHEFT · DICHTUNGSTECHNIK & WERKSTATT (D3 / D6)',
            titel='Gaskets & Flange Seals',
            untertitel='Nahtlose archimedische Spiraldichtungen in TPU und PETG mit vollflächiger Auflage (FLAT) oder druckverstärkender Doppellippen-Geometrie (NUT) und Spiral-Ironing',
            absaetze=[
                'Wenn eine herkömmliche Slicer-Ringdichtung unter Wasserdruck tropft, liegt die '
                'Ursache fast nie am Material, sondern an der Bahnführung: Konzentrische Wandringe '
                'erzeugen an jedem Rundenende einen Start-/Stopp-Punkt — quer über die Dichtfläche '
                'entsteht eine durchgehende radiale Z-Naht, die wie eine Kapillarrinne wirkt.',
                'make_seal() ersetzt konzentrische Ringe durch eine einzige stetige archimedische '
                'Spirale mit 5 % Spurüberlappung und alternierender Laufrichtung je Schicht. '
                'Wahlweise fräst das Profil NUT in die oberen Lagen eine zentrale Entlastungsnut, '
                'sodass zwei schmale Dichtlippen die Flächenpressung exakt um +66,7 % steigern.',
            ],
            tabelle=cover_tbl,
        )

        # ---- Kapitel 1 ------------------------------------------------------
        st += H1('Nahtlose Archimedische Spirale & Doppellippen-Physik', '1')
        st += P(
            'Zwischen Innenradius <b>r_in = ID / 2</b> und Außenradius <b>r_out = OD / 2</b> '
            '(radiale Stegbreite <b>w_r = r_out − r_in</b>) parametrisiert <b>band_pts()</b> '
            'eine glatte archimedische Spirale mit 56 Stützpunkten pro Umlauf:'
        )
        st += FORMULA(
            'Spiralwindungen:    N_turns = ceil((r_1 - r_0) / (0,95 · wid))   (5 % radiale Überlappung!)<br/>'
            'Bahnkurve u ∈ [0,1]: r(u) = r_0 + (r_1 - r_0) · u,    θ(u) = 2π · N_turns · u<br/>'
            'Alternierender Aufstieg: ungerade Layer innen -&gt; außen, gerade Layer außen -&gt; innen<br/>'
            'Doppellippe (NUT):  lip = 0,30 · w_r,   g_depth = clamp(0,4 · H, LH, 0,6 mm)<br/>'
            'Exakter Pressungsgewinn: A_NUT = π·0,6·w_r·(r_in + r_out) = 0,60·A_FLAT  =&gt;  p_NUT = 1,67 · p_FLAT',
            'Durch den Richtungswechsel (flip = (li % 2 == 0)) steigt die Düse am Ende einer '
            'Schicht exakt an derselben Außen- bzw. Innenkante um +LH auf und spiralt sofort '
            'zurück — es gibt im gesamten Vollkörper keine einzige Leerfahrt über die Dichtfläche!'
        )
        st += B(
            '<b>Face = FLAT:</b> Durchgehende ebene Spirale für glatte Verschraubungen '
            '(z. B. 3/4-Zoll-Schlauchkupplungen, Schraubdeckel, Kabelverschraubungen).',
            '<b>Face = NUT (GROOVE):</b> Lässt in den obersten <b>g_lay</b> Schichten die '
            'mittleren 40 % der Ringbreite frei. Die beiden 30-%-Lippen verformen sich schon '
            'unter geringem Anzugsmoment elastisch und dichten selbst leicht verzogene '
            'Kunststoff- oder Gussflansche sicher ab.',
            '<b>Spiral-Ironing (Ironing = ON):</b> Fährt die oberste Dichtfläche (bei NUT '
            'beide Lippen getrennt!) noch einmal spiralförmig mit <b>15 % Fluss</b> ab, um '
            'die feinen Extrusionsrillen auf der Oberseite einzuebnen.'
        )
        st += [IMG(fig1, width_mm=162)]
        st += CAP(
            'Abbildung 1 — A: Echte Spiralbahn einer FLAT-Dichtung inkl. 4×-Lupe auf den nahtfreien '
            'Übergang. B: NUT-Doppellippendichtung mit Spiral-Ironing. C: Maßstäblicher Radialschnitt.'
        )

        # ---- Kapitel 2 ------------------------------------------------------
        st += H1('Stegbreiten-Wächter, R96-Nutschutz & Elastomer-Parameter', '2')
        st += P(
            'Sehr schmale O-Ring-Stege lassen keine getrennte Innen- und Außenlippe mehr zu. '
            '<b>make_seal()</b> prüft deshalb vor dem Start zwei scharfe geometrische Schranken:'
        )
        st += B(
            '<b>Mindest-Stegbreite (FLAT):</b> <b>w_r &gt;= 2 · wid + 0,4 mm</b> (am LCD '
            'zusätzlich <b>OD − ID &gt;= 2,4 mm</b>). Darunter verweigert der Generator sauber '
            'mit Klartextmeldung statt einen undichten Einzelfaden zu drucken.',
            '<b>Mindest-Stegbreite (NUT):</b> <b>w_r &gt;= 3 · wid + 0,8 mm</b>. Ist ein '
            'gewählter Ring für zwei Lippen zu schmal, fällt <b>make_seal()</b> automatisch '
            'auf <b>FLAT</b> zurück und dokumentiert den Grund in der Rückmeldung.',
            '<b>R96-Anti-Leckfaden-Schutz:</b> In den oberen Nut-Schichten wird die gesamte '
            'offene Nutscheibe bis <b>r_out − wid/2</b> als Sperrkreis eingetragen, sodass '
            'der Wechsel von der Innen- zur Außenlippe zwingend einzieht.'
        )
        st += [IMG(fig2, width_mm=162)]
        st += CAP(
            'Abbildung 2 — A: Zulässige Stegbreiten-Zonen über dem Düsendurchmesser samt Live-Nachweis '
            'des NUT-&gt;FLAT-Fallbacks. B: Mathematischer Beweis des konstanten 1,67×-Anpressdruckfaktors.'
        )

        # ---- Kapitel 3 ------------------------------------------------------
        st += [PageBreak()]
        st += H1('Live-Menüreferenz & Gemessene Referenzläufe', '3')
        st += P(
            'Direkt aus <b>menus/lcd_menues.cfg</b> ausgelesene Menüzeilen unter '
            '<b>Tools &gt; Gaskets</b>:'
        )
        st += TBL(
            ['LCD-Menüpfad', 'Anzeige am Display', 'Wertebereich / Aktion'],
            [[r[0], r[1], r[2]] for r in lcd_rows],
            [62 * mm, 54 * mm, 46 * mm],
        )

        st += H2('Fünf echte Referenzläufe (live beim PDF-Bau gerechnet)', '3.1')
        bench_rows = [
            ['1. 3/4"-Schlauchdichtung', 'OD=24 · ID=16 · H=2,0 · FLAT · Iron=ON',
             i_g34['file'], '%.1f mm (%d L) · %s' % (i_g34['height'], i_g34['layers'], i_g34['profile']),
             'Klassischer Flachring geglättet'],
            ['2. Mittlerer Flanschring', 'OD=34 · ID=18 · H=1,6 · FLAT · Iron=off',
             i_flat['file'], '%.1f mm (%d L) · %s' % (i_flat['height'], i_flat['layers'], i_flat['profile']),
             'Nahtlose Vollspirale'],
            ['3. Gehäuse-Doppellippe', 'OD=48 · ID=24 · H=2,0 · NUT · Iron=ON',
             i_nut['file'], '%.1f mm (%d L) · %s' % (i_nut['height'], i_nut['layers'], i_nut['profile']),
             '2× 3,6-mm-Lippe + 0,6-mm-Nut'],
            ['4. Schmalsteg-Fallback', 'OD=24 · ID=20,4 · H=1,2 · Wunsch: NUT',
             i_fb['file'], '%.1f mm (%d L) -&gt; %s' % (i_fb['height'], i_fb['layers'], i_fb['profile']),
             'Ehrlicher Auto-Fallback FLAT'],
            ['5. Großer Wartungsdeckel', 'OD=110 · ID=90 · H=2,4 · NUT · 0,6er TPU',
             i_lrg['file'], '%.1f mm (%d L) · %s' % (i_lrg['height'], i_lrg['layers'], i_lrg['profile']),
             '2× 3,0-mm-Lippe, 1,67× Pressung'],
        ]
        st += TBL(
            ['Szenario', 'Parameter', 'Erzeugte Datei', 'Reale Höhe & Profil', 'Ergebnis'],
            bench_rows,
            [31 * mm, 42 * mm, 33 * mm, 30 * mm, 26 * mm],
        )

        st += SP(2)
        st += [BOX(
            'Dichtungspraxis am Drucker (Unterseite vs. Oberseite nutzen!)',
            [
                '• Trick für Hochglanz-Flansche: Bei Face = FLAT wird die Unterseite auf einer '
                'glatten PEI-Platte spiegelblank abgeformt; mit Ironing = ON wird auch die '
                'Oberseite geglättet, sodass beide Seiten flächig dichten.',
                '• Höhe immer als ganzzahliges Vielfaches der Schichthöhe LH wählen (z. B. '
                '1,2 / 1,6 / 2,0 mm bei LH = 0,20 mm), damit die Endhöhe auf 0,01 mm stimmt.',
                '• Feuchtes TPU schäumt mikroporös auf und verliert seine Gasdichtheit — vor '
                'Druckdichtungen TPU trocknen; gängige Normmaße unter My presets speichern!',
            ],
            kind='tip',
        )]

        doc.render()
    return out_pdf


if __name__ == '__main__':
    dst = os.path.join(REPO, 'GASKETS.pdf')
    build_pdf(dst)
    print('Wrote %s (%d bytes)' % (dst, os.path.getsize(dst)))
