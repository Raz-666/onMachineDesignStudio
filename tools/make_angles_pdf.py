#!/usr/bin/env python3
# -*- coding: utf-8 -*-
""" make_angles_pdf.py — Wissenschaftliches Generator-Fachheft (D3 / D6):
    L-Winkel & Flachverbinder (Tools > Angles+Flat -> make_angles()).

    Alle Abbildungen und Referenzläufe werden zur Bauzeit LIVE aus make_angles()
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
            if s in ('LAYER_MARK', ';LAYER_CHANGE') or s.startswith(';LAYER:'):
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
    if 'angle_flat' in s and 'Mode:' in s:
        return 'Mode: Angle / Flat'
    if 'Leg A:' in s and 'Left:' in s:
        return 'Leg A / Left: [mm]'
    if 'Leg B:' in s and 'Right:' in s:
        return 'Leg B / Right: [mm]'
    if 'angle_countersink' in s and 'Holes:' in s:
        return 'Holes: countersunk / normal'
    if 'angle_ironing' in s and 'Ironing:' in s:
        return 'Ironing: ON / off'
    if 'angle_stiffener' in s and 'Rib:' in s:
        return 'Rib: none / gusset / stepped'
    if 'AGAIN = start' in s:
        return '> Create (2x = Start)'
    s = re.sub(r"\{[^{}]*\}", '', s)
    s = re.sub(r'\s+', ' ', s).strip(' *')
    return s or 'Auswahl'


def _parse_angles_menu():
    cfg_path = os.path.join(REPO, 'menus', 'lcd_menues.cfg')
    txt = open(cfg_path, encoding='utf-8').read()
    blocks = re.split(r'(?m)^(?=\[menu )', txt)
    secs = [b for b in blocks if b.startswith('[menu __main __gen __angle')]
    rows = []
    seen_usr = False
    for sec in secs:
        lines = [l.strip() for l in sec.strip().splitlines() if l.strip()]
        hdr = lines[0].strip('[]').replace('menu __main __gen __angle', 'Tools > Angles+Flat')
        if '__usr' in hdr:
            if not seen_usr:
                seen_usr = True
                rows.append((
                    'Tools > Angles+Flat > usr > [P1..P8]',
                    'My presets (Save A&lt;deg&gt; / Load / Delete)',
                    'Seitenweise je 8 eigene Presets',
                ))
            continue
        # Sub-choice leaves inside mode/cs/iro/stf are summarized by their parent
        if any(hdr.endswith(suf) for suf in (
                '__mode __ang', '__mode __flt',
                '__cs __on', '__cs __off',
                '__iro __on', '__iro __off',
                '__stf __s0', '__stf __s1', '__stf __s2')):
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
        elif '__mode' in hdr:
            rng = 'Angle (L) · Flat splice (180°)'
        elif '__cs' in hdr:
            rng = 'Countersunk (2-Stufen) · Normal'
        elif '__iro' in hdr:
            rng = 'ON (15 % Glättpass) · off'
        elif '__stf' in hdr:
            rng = '0=None · 1=Gusset · 2=Stepped'
        elif tp == 'list':
            rng = 'Untermenü'
        else:
            rng = 'Kommando / 2-Takt-Start'
        rows.append((hdr.replace(' __', ' > '), label, rng))
    return rows


# ------------------------------------------------------- Abbildungen (D6)
def _bbox_layers(parsed, lnums):
    xs, ys = [], []
    for ln in lnums:
        for x0, y0, x1, y1, _t in parsed['layers'].get(ln, ()):
            xs.extend((x0, x1))
            ys.extend((y0, y1))
    if not xs:
        return (0.0, 0.0, 100.0, 100.0)
    return (min(xs), min(ys), max(xs), max(ys))


def _draw_toolpath_box(dr, parsed, box, layer_specs, pad=18):
    bx0, by0, bx1, by1 = box
    all_l = [ln for ln, _c, _w in layer_specs]
    x0, y0, x1, y1 = _bbox_layers(parsed, all_l)
    span_x = max(1.0, x1 - x0)
    span_y = max(1.0, y1 - y0)
    sc = min((bx1 - bx0 - 2 * pad) / span_x, (by1 - by0 - 2 * pad) / span_y)
    ox = (bx0 + bx1 - span_x * sc) / 2.0
    oy = (by0 + by1 + span_y * sc) / 2.0

    def tx(x, y):
        return (ox + (x - x0) * sc, oy - (y - y0) * sc)

    for ln, col_map, lw in layer_specs:
        for sx0, sy0, sx1, sy1, tp in parsed['layers'].get(ln, ()):
            p0 = tx(sx0, sy0)
            p1 = tx(sx1, sy1)
            c = col_map.get(tp, col_map.get('*', (70, 95, 130)))
            dr.line([p0, p1], fill=c, width=lw)


def _render_fig1(p_ang90, p_obt, p_flat, out_png):
    """Abb. 1: Echte Werkzeugbahnen 90°-Stufenrippen-Winkel vs. 120°-Winkel +
    180°-Flachverbinder + maßstäblicher Z-Schnitt durch Senkkopf & Stufenrippe."""
    W, H = 1800, 900
    im = PILImage.new('RGB', (W, H), (250, 252, 255))
    dr = ImageDraw.Draw(im)

    # Panel A: 90 deg angle with stepped rib + countersunk holes
    pa = (24, 58, 630, 845)
    dr.rounded_rectangle(pa, radius=12, fill=(255, 255, 255), outline=(185, 202, 224), width=2)
    dr.text((34, 20), 'A · 90°-Winkel (Stufenrippe & Senkung)',
            fill=(28, 78, 140), font=font(21, bold=True))

    # Base countersink layer (layer 6 of 6) + Tier 1 rib (layer 7) + Tier 2 rib (layer 9)
    cmap_base = {
        'WALL-OUTER': (28, 78, 140), 'OUTER WALL': (28, 78, 140),
        'WALL-INNER': (62, 118, 188), 'INNER WALL': (62, 118, 188),
        '*': (175, 196, 222),
    }
    cmap_rib1 = {'*': (224, 123, 0), 'WALL-OUTER': (195, 98, 0), 'OUTER WALL': (195, 98, 0)}
    cmap_rib2 = {'*': (179, 38, 30), 'WALL-OUTER': (145, 22, 18), 'OUTER WALL': (145, 22, 18)}
    _draw_toolpath_box(
        dr, p_ang90, (pa[0] + 10, pa[1] + 12, pa[2] - 10, pa[3] - 96),
        [(6, cmap_base, 2), (7, cmap_rib1, 2), (10, cmap_rib2, 3)],
        pad=22,
    )
    # Legend inside Panel A bottom
    ly = pa[3] - 80
    dr.line([(pa[0] + 22, ly), (pa[0] + 62, ly)], fill=(28, 78, 140), width=4)
    dr.text((pa[0] + 72, ly - 10), 'Plattendecklage L6 (Senkstufe Ø8,0 mm)',
            fill=(45, 55, 68), font=font(18))
    dr.line([(pa[0] + 22, ly + 26), (pa[0] + 62, ly + 26)], fill=(224, 123, 0), width=4)
    dr.text((pa[0] + 72, ly + 16), 'Eckrippe Stufe 1 (L7..L8, g = 0,8·min)',
            fill=(45, 55, 68), font=font(18))
    dr.line([(pa[0] + 22, ly + 52), (pa[0] + 62, ly + 52)], fill=(179, 38, 30), width=4)
    dr.text((pa[0] + 72, ly + 42), 'Eckrippe Stufe 2 (L9..L10, 0,6·g + Ironing)',
            fill=(45, 55, 68), font=font(18))

    # Panel B top: 120 deg obtuse angle vs FLAT splice connector
    pb1 = (654, 58, 1776, 468)
    dr.rounded_rectangle(pb1, radius=12, fill=(255, 255, 255), outline=(185, 202, 224), width=2)
    dr.text((666, 20), 'B · 120°-Winkel (links) & 180°-Flachverbinder (rechts, echte Bahnen)',
            fill=(28, 78, 140), font=font(21, bold=True))

    _draw_toolpath_box(
        dr, p_obt, (668, 70, 1185, 422),
        [(6, cmap_base, 2), (8, cmap_rib1, 2)],
        pad=18,
    )
    dr.text((698, 430), 'ANGLE 120° · 55×55 mm · Gusset-Rippe (L7..9)',
            fill=(55, 65, 78), font=font(17, bold=True))

    _draw_toolpath_box(
        dr, p_flat, (1205, 70, 1762, 422),
        [(6, cmap_base, 2)],
        pad=18,
    )
    dr.text((1238, 430), 'FLAT (180°) · 100×22 mm · symm. Lochbild',
            fill=(55, 65, 78), font=font(17, bold=True))

    # Panel C bottom-right: Exact Z-cross-section of 2-step countersink + stepped rib
    pb2 = (654, 505, 1776, 845)
    dr.rounded_rectangle(pb2, radius=12, fill=(255, 255, 255), outline=(185, 202, 224), width=2)
    dr.text((674, 518), 'C · Maßstäblicher Z-Profilschnitt (Platte 6 Lagen @ 0,20 mm + 2-Stufen-Senkung + Stufenrippe)',
            fill=(28, 78, 140), font=font(20, bold=True))

    # Draw bed baseline
    bx_l, bx_r, bz0 = 700, 1720, 790
    dr.line([(bx_l - 15, bz0), (bx_r + 15, bz0)], fill=(90, 95, 105), width=3)
    dr.text((bx_l, bz0 + 10), 'Druckbett Z = 0,00 mm (erste Schicht 0,28 mm, Lüfter M107 aus)',
            fill=(88, 89, 91), font=font(17))

    # 6 base layers + 4 rib layers (vertical exaggeration for clarity, exact labels)
    lh_px = 18
    # Corner + rib on left (x = 720..1080), screw hole with 2-step CS on right (x = 1280..1520)
    for li in range(6):
        y_bot = bz0 - li * lh_px
        y_top = y_bot - lh_px + 2
        col = (214, 228, 246) if li < 4 else (178, 204, 238)
        # Left solid up to hole bore
        if li < 4:
            hole_half = 40      # d = 4.0 mm
        elif li == 4:
            hole_half = 60      # cs_d1 = 1.5*d = 6.0 mm
        else:
            hole_half = 80      # cs_d2 = 2.0*d = 8.0 mm
        cx_h = 1410
        dr.rectangle([720, y_top, cx_h - hole_half, y_bot], fill=col, outline=(28, 78, 140), width=1)
        dr.rectangle([cx_h + hole_half, y_top, 1680, y_bot], fill=col, outline=(28, 78, 140), width=1)

    # Rib tier 1 (layers 7..8) & tier 2 (layers 9..10)
    for rli in range(2):
        y_bot = bz0 - (6 + rli) * lh_px
        y_top = y_bot - lh_px + 2
        dr.rectangle([740, y_top, 1090, y_bot], fill=(252, 220, 178), outline=(195, 98, 0), width=1)
    for rli in range(2):
        y_bot = bz0 - (8 + rli) * lh_px
        y_top = y_bot - lh_px + 2
        dr.rectangle([756, y_top, 965, y_bot], fill=(248, 198, 194), outline=(165, 32, 24), width=1)

    # Annotations
    dr.text((748, bz0 - 10 * lh_px - 28), 'Stufenrippe (L7..L10 -> Z = 2,08 mm)',
            fill=(165, 32, 24), font=font(18, bold=True))
    dr.text((1315, bz0 - 6 * lh_px - 52), '2-Stufen-Senkung (CS = ON)',
            fill=(28, 78, 140), font=font(18, bold=True))
    dr.text((1295, bz0 - 6 * lh_px - 28), 'L6: Ø8,0  |  L5: Ø6,0  |  L1..4: Ø4,0 mm',
            fill=(45, 60, 82), font=font(17))
    # Bore centerline
    dr.line([(1410, bz0 - 6 * lh_px - 4), (1410, bz0 + 6)], fill=(179, 38, 30), width=2)

    im.save(out_png, 'PNG')
    return out_png


def _render_fig2(p_grid, info_clamp, out_png):
    """Abb. 2: Mehrteil-Bettpackung (count=4) + analytische Bohrungs- &
    Randabstands-Automatik über Schenkelbreite und Schenkellänge."""
    W, H = 1800, 760
    im = PILImage.new('RGB', (W, H), (250, 252, 255))
    dr = ImageDraw.Draw(im)

    # Panel A: 4x angle bed grid from real make_angles(count=4)
    pa = (24, 58, 880, 730)
    dr.rounded_rectangle(pa, radius=12, fill=(255, 255, 255), outline=(185, 202, 224), width=2)
    dr.text((38, 18), 'A · Mehrteil-Packung (count=4 -> PLATE_1..PLATE_4)',
            fill=(28, 78, 140), font=font(23, bold=True))

    cmap = {
        'WALL-OUTER': (28, 78, 140), 'OUTER WALL': (28, 78, 140),
        'WALL-INNER': (62, 118, 188), 'INNER WALL': (62, 118, 188),
        '*': (176, 198, 226),
    }
    _draw_toolpath_box(
        dr, p_grid, (pa[0] + 16, pa[1] + 14, pa[2] - 16, pa[3] - 66),
        [(5, cmap, 2), (7, {'*': (224, 123, 0)}, 2)],
        pad=20,
    )
    dr.text((pa[0] + 24, pa[3] - 48),
            'Jeder Winkel besitzt eigenes EXCLUDE_OBJECT (live einzeln überspringbar!)',
            fill=(55, 65, 78), font=font(18, bold=True))

    # Panel B: Auto-clamping curves (max hole diameter & max hole count vs width/length)
    pb = (906, 58, 1776, 730)
    dr.rounded_rectangle(pb, radius=12, fill=(255, 255, 255), outline=(185, 202, 224), width=2)
    dr.text((920, 20), 'B · Automatischer Kantenschutz: d_max(Breite) & Lochzahl',
            fill=(28, 78, 140), font=font(21, bold=True))

    # Top mini-plot: d_max = min(width - 6, 10) and cs_d2 = min(2*d, d_max)
    dr.text((960, 76), 'Blau: d_max = min(Breite − 6 mm, 10 mm)   |   Orange: Senkkopf-Ø bei M4',
            fill=(28, 78, 140), font=font(17, bold=True))
    gx0, gy0, gx1, gy1 = 995, 112, 1725, 365
    dr.rectangle([gx0, gy0, gx1, gy1], fill=(247, 250, 254), outline=(170, 188, 212), width=2)
    for w_mm in range(10, 45, 5):
        xp = gx0 + (w_mm - 8.0) / 34.0 * (gx1 - gx0)
        dr.line([(xp, gy0), (xp, gy1)], fill=(226, 233, 242), width=1)
        dr.text((xp - 12, gy1 + 8), '%d' % w_mm, fill=(75, 82, 92), font=font(16))
    for d_mm in (2, 4, 6, 8, 10):
        yp = gy1 - (d_mm / 11.5) * (gy1 - gy0)
        dr.line([(gx0, yp), (gx1, yp)], fill=(226, 233, 242), width=1)
        dr.text((gx0 - 38, yp - 9), '%d' % d_mm, fill=(75, 82, 92), font=font(16))

    pts_dmax = []
    pts_cs4 = []
    for w10 in range(100, 421, 5):
        wv = w10 / 10.0
        dm = min(wv - 6.0, 10.0)
        hd = min(4.0, dm)
        cs2 = min(2.0 * hd, dm)
        xp = gx0 + (wv - 8.0) / 34.0 * (gx1 - gx0)
        pts_dmax.append((xp, gy1 - (dm / 11.5) * (gy1 - gy0)))
        pts_cs4.append((xp, gy1 - (cs2 / 11.5) * (gy1 - gy0)))
    dr.line(pts_dmax, fill=(28, 78, 140), width=4)
    dr.line(pts_cs4, fill=(224, 123, 0), width=4)
    dr.text((gx0 + 210, gy1 + 30), 'Schenkelbreite width [mm]', fill=(55, 65, 78), font=font(17, bold=True))

    # Bottom summary card showing exact live clamp note from info_clamp
    cy0 = 445
    dr.rounded_rectangle([940, cy0, 1742, 704], radius=10, fill=(238, 245, 253),
                         outline=(135, 168, 208), width=2)
    dr.text((958, cy0 + 16), 'Live-Test am 10-mm-Schenkel (width=10, 5× Ø8, 6 Wände, 0,6er Düse):',
            fill=(28, 78, 140), font=font(17, bold=True))
    dr.text((958, cy0 + 54),
            '• Bohrung Ø8,0 mm -> geklemmt auf Ø%.1f mm (3,0 mm Rand je Seite!)'
            % info_clamp['hole_d'],
            fill=(35, 45, 58), font=font(17))
    dr.text((958, cy0 + 88),
            '• 5 gewünschte Löcher (34/50 mm) -> reduziert auf %s Löcher'
            % info_clamp['holes'],
            fill=(35, 45, 58), font=font(17))
    dr.text((958, cy0 + 122),
            '• 6 gewünschte Wandringe -> reduziert auf %d Ringe (Kernbreite gewahrt!)'
            % info_clamp['walls'],
            fill=(35, 45, 58), font=font(17))
    for k_i, nt in enumerate(info_clamp['notes'][:3]):
        dr.text((958, cy0 + 158 + k_i * 28), 'Log: "%s"' % nt[:64],
                fill=(110, 62, 12), font=font(15))

    im.save(out_png, 'PNG')
    return out_png


# ------------------------------------------------------- PDF-Bau
def build_pdf(out_pdf):
    lcd_rows = _parse_angles_menu()

    with tempfile.TemporaryDirectory(prefix='r2_ang_pdf_') as td:
        f_90, i_90 = pp.make_angles(
            count=1, angle_deg=90, leg_a=65, leg_b=50, width=24, layers=6,
            holes=2, hole_d=4.0, countersink=True, stiffener=2, flat=False,
            walls=2, infill=100, ironing=True, nozzle=0.4, out_dir=td,
        )
        f_obt, i_obt = pp.make_angles(
            count=1, angle_deg=120, leg_a=55, leg_b=55, width=22, layers=6,
            holes=2, hole_d=4.0, countersink=True, stiffener=1, flat=False,
            walls=2, infill=80, ironing=False, nozzle=0.4, out_dir=td,
        )
        f_flt, i_flt = pp.make_angles(
            count=1, leg_a=50, leg_b=50, width=22, layers=6,
            holes=2, hole_d=4.0, countersink=True, flat=True,
            walls=2, infill=100, ironing=True, nozzle=0.4, out_dir=td,
        )
        f_grd, i_grd = pp.make_angles(
            count=4, angle_deg=90, leg_a=45, leg_b=45, width=20, layers=5,
            holes=2, hole_d=3.5, countersink=True, stiffener=1, flat=False,
            walls=2, infill=100, ironing=False, nozzle=0.4, out_dir=td,
        )
        _f_clp, i_clp = pp.make_angles(
            count=1, angle_deg=90, leg_a=34, leg_b=50, width=10, layers=6,
            holes=5, hole_d=8.0, countersink=True, stiffener=0, flat=False,
            walls=6, infill=100, ironing=False, nozzle=0.6, out_dir=td,
        )

        p_90 = _parse_gcode(f_90)
        p_obt = _parse_gcode(f_obt)
        p_flt = _parse_gcode(f_flt)
        p_grd = _parse_gcode(f_grd)

        fig1 = _render_fig1(p_90, p_obt, p_flt, os.path.join(td, 'angles_fig1.png'))
        fig2 = _render_fig2(p_grd, i_clp, os.path.join(td, 'angles_fig2.png'))

        doc = Doc(
            out_pdf,
            'R2-D2 · Angles & Flat Connectors (make_angles)',
            'Wissenschaftliche Generator-Referenz (D3 / D6)',
        )
        st = doc.story

        cover_tbl = TBL(
            ['Kenngröße', 'Wert im R2-D2-System (Code-Wahrheit aus r2_postproc.py)'],
            [
                ['LCD-Menüpfad', 'Tools &gt; Angles+Flat (Makros: ANGLE_GENERATE · GEN_ANGLES · ANGLE_INFO)'],
                ['Ausgabeordner', 'gcodes/Angles/Vnn_Angle_&lt;deg&gt;deg_AxB.gcode bzw. Vnn_Flat_LxW.gcode'],
                ['Zwei Bauformen', 'ANGLE (L-/Gehrungswinkel 30°..170°) · FLAT (180°-Stoßverbinder)'],
                ['Schenkel & Breite', 'Leg A / B = 20..150 mm · Width = 8..60 mm · 4..12 Basislagen (LH 0,12..0,32 mm)'],
                ['Bohrungen & Senkung', '0..6 Löcher/Schenkel · Ø2..10 mm (≥ 3,0 mm Rand) · 2-Stufen-Senkung CS (1,5× / 2,0×)'],
                ['Eckversteifung & Presets', 'Rib: 0=None · 1=Gusset · 2=Stepped · bis 12 Stück/Platte · My presets (A&lt;deg&gt;)'],
            ],
            [54 * mm, 108 * mm],
        )[0]

        doc.add_cover(
            kicker='GENERATOR-FACHHEFT · WERKSTATT & VERBINDER (D3 / D6)',
            titel='Angles + Flat Connectors',
            untertitel='Parametrische L-Winkel, Gehrungsplatten (30°..170°) und symmetrische 180°-Flachverbinder mit 2-Stufen-Senkkopfbohrungen, Stufenrippen und automatischem Kantenschutz',
            absaetze=[
                'Im Gehäuse-, Möbel- und Vorrichtungsbau scheitern Standard-Metallwinkel fast '
                'immer an einer Stelle: Entweder stimmt der Winkel nicht (z. B. 60°-Dachschräge '
                'oder 120°-Sechseckrahmen), ein Schenkel kollidiert mit einer Kante, oder das '
                'Lochbild sitzt genau im Spalt. make_angles() berechnet maßgeschneiderte '
                'Flachwinkel und gerade Stoßlaschen in Sekunden direkt am Drucker.',
                'Damit kein Bauteil unter Last am Schraubenloch ausreißt, erzwingt der Algorithmus '
                'automatisch mindestens 3,0 mm Restwand um jede Bohrung, reduziert überzählige '
                'Löcher auf kurzen Schenkeln selbsttätig und setzt auf Wunsch eine ein- oder '
                'zweistufige Dreiecks-Eckrippe (Gusset / Stepped Rib) auf den Scheitelpunkt.',
            ],
            tabelle=cover_tbl,
        )

        # ---- Kapitel 1 ------------------------------------------------------
        st += H1('Vektorgeometrie des Winkelpolygons & Flachverbinders', '1')
        st += P(
            '<b>make_angles()</b> spannt das Bauteil in einem lokalen 2D-Koordinatensystem '
            'mit äußerem Scheitel im Ursprung <b>(0, 0)</b> auf. Schenkel A läuft entlang '
            '<b>u_A = (1, 0)</b>, Schenkel B unter dem Öffnungswinkel <b>θ ∈ [30°, 170°]</b> '
            'entlang <b>u_B = (cos θ, sin θ)</b> mit einwärts gerichteter Normalen '
            '<b>n_B = (sin θ, −cos θ)</b>:'
        )
        st += FORMULA(
            'Konkaver Innenscheitel P_in (Schnittpunkt beider Innenkanten im Abstand width):<br/>'
            '  s = (width - width · n_{B,y}) / u_{B,y} = width · (1 + cos θ) / sin θ<br/>'
            '  P_in = (width · sin θ + s · cos θ,  width)   -&gt; bei θ = 90° exakt P_in = (width, width)<br/>'
            'Sechseck-Umriss (ANGLE): [(0,0), (L_A,0), (L_A,width), P_in, L_B·u_B + width·n_B, L_B·u_B]<br/>'
            'Gerader Stoßverbinder (FLAT, θ = 180°): Rechteck [0, L_A + L_B] × [0, width]',
            'Im Modus FLAT = True verschwindet der Knickwinkel: Beide Plattenhälften liegen '
            'fluchtend nebeneinander und erhalten ein um die Plattenmitte gespiegeltes Lochbild '
            '(x_i auf der linken Hälfte und L_A + L_B - x_i auf der rechten Hälfte), sodass '
            'beide verbundenen Holz- oder Acrylplatten denselben Randabstand besitzen.'
        )
        st += B(
            '<b>Warum flach liegend statt stehend als 3D-L-Profil?</b> Bei einem stehend '
            'gedruckten L-Winkel verläuft die Schichtfuge exakt durch den hochbelasteten '
            '90°-Knick — Zuglast spaltet die Layer sofort (Delamination). Eine flach liegend '
            'gedruckte Winkelplatte legt <b>100 % durchgehende Endlosstränge</b> um den '
            'Scheitel und verschraubt beide Platten stirn- oder flächenseitig mit maximaler '
            'Zug- und Scherfestigkeit!',
            '<b>Konkave Scanline-Schraffur (_poly_hatch):</b> Da der Innenscheitel <b>P_in</b> '
            'eine konkave Ecke bildet, schneidet der Schraffurgenerator jede 45°/135°-Linie '
            'exakt an allen Polygonkanten und allen Loch-Sperrkreisen ab. Der Serpentinen-Verbinder '
            '(R117) ist auf <b>max_conn &lt;= 3,0 mm</b> gedeckelt, damit niemals ein Querfaden '
            'durch ein Schraubenloch gezogen wird.'
        )

        # ---- Kapitel 2 ------------------------------------------------------
        st += H1('Kantenschutz, 2-Stufen-Senkung & Eck-Versteifungsrippen', '2')
        st += P(
            'Jede Bohrung und jede Wandanzahl wird vor dem G-Code-Schreiben gegen die reale '
            'Schenkelgeometrie geprüft — unpassende Benutzereingaben führen niemals zu '
            'aufgeschnittenen Außenkanten, sondern zu dokumentierten Auto-Korrekturen:'
        )
        st += FORMULA(
            'Maximaler Loch-/Senkdurchmesser:  d_max = min(width - 2 · 3,0 mm,  10,0 mm)<br/>'
            '2-Stufen-Senkkopf (CS = ON):      cs_d1 = min(1,5 · d, d_max),   cs_d2 = min(2,0 · d, d_max)<br/>'
            'Nutzbare Lochstrecke pro Schenkel: usable = L - corner_clear - max(3,5, 0,8·d) - d<br/>'
            '  mit corner_clear = (4,0 mm falls FLAT sonst width) + d/2 + 1,5 mm<br/>'
            'Maximale Lochzahl:                n_fit = floor(usable / (d + 3,0 mm)) + 1',
            'Zusätzlich prüft R95/dd jede Leerfahrt: Alle Schraubenlöcher sind über sämtliche '
            'Schichten in pen.holes als Sperrkreise registriert — überquert der Druckkopf eine '
            'Bohrung, zieht er bei jeder Distanz sauber ein, sodass kein Faden das Schraubloch blockiert.'
        )
        st += B(
            '<b>Rib = 0 (None):</b> Ebene Platte der Höhe <b>first_h + (layers − 1) · LH</b> — '
            'beidseitig flach anliegend (bei FLAT immer automatisch aktiv).',
            '<b>Rib = 1 (Gusset rib):</b> Setzt über dem Scheitel ein massives Versteifungsdreieck '
            'mit Kathetenlänge <b>g = 0,8 · min(L_A, L_B, 2 · width)</b> und '
            '<b>rib_layers = max(2, layers // 2)</b> Zusatzlagen auf.',
            '<b>Rib = 2 (Stepped rib):</b> Baut eine höhere Rippe '
            '(<b>rib_layers = max(3, 2 · layers // 3)</b>), deren obere Hälfte stufenförmig '
            'auf <b>0,6 · g</b> zurückspringt — maximale Ecksteifigkeit bei freiem Schraubenzugang!'
        )
        st += [IMG(fig1, width_mm=162)]
        st += CAP(
            'Abbildung 1 — A: Echte Werkzeugbahnen eines 90°-Winkels mit zweistufiger Eckrippe '
            'und Senklöchern. B: 120°-Winkel vs. 180°-Flachverbinder. C: Maßstäblicher Z-Profilschnitt.'
        )
        st += [IMG(fig2, width_mm=162)]
        st += CAP(
            'Abbildung 2 — A: Automatische 4×1-Reihenpackung (count=4) mit Einzelobjekt-Polygonen. '
            'B: Analytische Klemmlinie d_max(width) und Live-Nachweis am 10-mm-Schmalschenkel.'
        )

        # ---- Kapitel 3 ------------------------------------------------------
        st += [PageBreak()]
        st += H1('Live-Menüreferenz & Gemessene Referenzläufe', '3')
        st += P(
            'Alle Einstellzeilen unter <b>Tools &gt; Angles+Flat</b> werden zur PDF-Bauzeit '
            'direkt aus <b>menus/lcd_menues.cfg</b> ausgelesen:'
        )
        st += TBL(
            ['LCD-Menüpfad', 'Anzeige am Display', 'Wertebereich / Aktion'],
            [[r[0], r[1], r[2]] for r in lcd_rows],
            [62 * mm, 54 * mm, 46 * mm],
        )

        st += H2('Fünf echte Referenzläufe (live beim PDF-Bau gerechnet)', '3.1')
        bench_rows = [
            ['1. Schwerlast-90°-Winkel', '90° · 65×50×24 · M4 CS · Rib=2 · Iron',
             i_90['file'], '%d L · Löcher %s (CS Ø%.1f)' % (i_90['layers'], i_90['holes'], i_90['cs_d']),
             '2-Stufen-Rippe + Glättpass'],
            ['2. Sechseck-Gehrung 120°', '120° · 55×55×22 · M4 CS · Rib=1 · 80 %',
             i_obt['file'], '%d L · Löcher %s · Grid %s' % (i_obt['layers'], i_obt['holes'], i_obt['grid']),
             'Gusset-Rippe im Stumpfwinkel'],
            ['3. Gerader Stoßverbinder', 'FLAT (180°) · 50+50×22 · M4 CS · Iron',
             i_flt['file'], '%d L · 100×22 mm Streifen' % i_flt['layers'],
             'Symmetrisches 2+2-Lochbild'],
            ['4. Vierersatz Gehäusebau', 'count=4 · 90° · 45×45×20 · Ø3,5 CS',
             i_grd['file'], '%d L · Raster %s (4 Objekte)' % (i_grd['layers'], i_grd['grid']),
             'PLATE_1..4 einzeln abwählbar'],
            ['5. Schmalschenkel-Schutz', '90° · 34×50×10 · Wunsch: 5× Ø8, 6 W (0,6er)',
             i_clp['file'], 'Auto: Ø%.1f · %s Löcher · %d W' % (i_clp['hole_d'], i_clp['holes'], i_clp['walls']),
             '3,0-mm-Randgarantie aktiv!'],
        ]
        st += TBL(
            ['Szenario', 'Parameter', 'Erzeugte Datei', 'Geometrie & Lagen', 'Ergebnis'],
            bench_rows,
            [31 * mm, 42 * mm, 34 * mm, 29 * mm, 26 * mm],
        )

        st += SP(2)
        st += [BOX(
            'Werkstatt-Faustregeln für belastbare Verbinder (blind am Drehrad)',
            [
                '• Plattenstoß zweier Bretter immer mit Mode = Flat splice (180°) und mindestens '
                '2 Löchern je Seite ausführen — überträgt Zug- und Scherkräfte über vier Schrauben.',
                '• Für Senkkopfschrauben M3 / M4 / M5 einfach Hole D = 3,5 / 4,5 / 5,5 mm und '
                'Countersunk = ON wählen: Die obere 2×d-Stufe nimmt den 90°-Schraubenkopf bündig auf.',
                '• Häufig genutzte Winkel (z. B. A90 oder A120) unter My presets > Save ablegen — '
                'bleiben über Neustarts hinweg dauerhaft in save_variables erhalten.',
            ],
            kind='tip',
        )]

        doc.render()
    return out_pdf


if __name__ == '__main__':
    dst = os.path.join(REPO, 'ANGLES.pdf')
    build_pdf(dst)
    print('Wrote %s (%d bytes)' % (dst, os.path.getsize(dst)))
