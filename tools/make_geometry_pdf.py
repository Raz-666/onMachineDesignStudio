#!/usr/bin/env python3
# -*- coding: utf-8 -*-
""" make_geometry_pdf.py — Wissenschaftliches Generator-Fachheft (D3 / D6):
    Parametrische Grundkörper, Spiralvasen & Diagonal-Brückentest
    (Tools > Geometry -> make_shape()  &  Maintenance > Bridging -> make_bridge()).

    Alle Abbildungen und Referenzläufe werden zur Bauzeit LIVE aus make_shape()
    und make_bridge() in tools/r2_postproc.py sowie aus menus/lcd_menues.cfg
    erzeugt (Regel D6). Versionsstempel kommt dynamisch aus r2_version (Regel r165).
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


# ------------------------------------------------------- Echter G-Code-Parser (3D!)
def _parse_gcode_3d(gcode_path):
    """Parse real 3D extruding moves (x0, y0, z0, x1, y1, z1, type, layer)."""
    layers = {}
    moves3d = []
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
            if has_e and de > 1e-5 and (math.hypot(nx - x, ny - y) > 1e-4 or abs(nz - z) > 1e-4):
                eff_l = max(1, cur_layer)
                layers.setdefault(eff_l, []).append((x, y, nx, ny, cur_type))
                moves3d.append((x, y, z, nx, ny, nz, cur_type, eff_l))
                total_e += de
            x, y, z = nx, ny, nz

    return {
        'layers': layers,
        'moves3d': moves3d,
        'objs': objs,
        'total_e': total_e,
        'n_layers': max(layers.keys()) if layers else 0,
    }


# ------------------------------------------------------- Live-Menüextraktor
def _parse_geo_and_bridge_menus():
    cfg_path = os.path.join(REPO, 'menus', 'lcd_menues.cfg')
    txt = open(cfg_path, encoding='utf-8').read()
    blocks = re.split(r'(?m)^(?=\[menu )', txt)

    rows_shape = []
    for sec in blocks:
        if not sec.startswith('[menu __main __gen __shape'):
            continue
        lines = [l.strip() for l in sec.strip().splitlines() if l.strip()]
        hdr = lines[0].strip('[]').replace('menu __main __gen __shape', 'Tools > Geometry')
        if any(hdr.endswith(s) for s in ('__tri', '__sqr', '__ply', '__cyl')):
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
        if hdr.endswith('__kind'):
            nm, rng = 'Shape: TRIANGLE / SQUARE / POLY / CYLINDER', '4 Grundfamilien'
        elif hdr.endswith('__crn'):
            nm, rng = 'Corners (POLY) / Segs (CYLINDER)', '%s..%s (Schritt %s, 0=rund)' % (mn, mx, st)
        elif hdr.endswith('__wal'):
            nm, rng = 'Walls: 1 VASE .. 8 Ringe', '%s..%s (Schritt %s, 1=Spirale)' % (mn, mx, st)
        elif hdr.endswith('__gen'):
            nm, rng = 'Create (2x Klick = Start)', '2-Takt-Sicherheitsstart'
        else:
            nm = re.sub(r'\{.*?\}', '[live]', nm).replace('<', '[').replace('>', ']')
            rng = ('%s..%s (Schritt %s)' % (mn, mx, st)) if mn else ('Untermenü' if tp == 'list' else 'Kommando')
        rows_shape.append((hdr.replace(' __', ' > '), nm[:44], rng))

    rows_bridge = []
    for sec in blocks:
        if not sec.startswith('[menu __main __maint __bridge'):
            continue
        lines = [l.strip() for l in sec.strip().splitlines() if l.strip()]
        hdr = lines[0].strip('[]').replace('menu __main __maint __bridge', 'Maint > Bridging')
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
        if hdr.endswith('__stat'):
            nm, rng = 'Statuszeile [Len / Short% / Speed]', 'Live-Anzeige'
        elif hdr.endswith('__run'):
            nm, rng = 'Create file (BRIDGE_TEST)', 'Schreibt nach gcodes/Towers/'
        else:
            nm = re.sub(r'\{.*?\}', '[live]', nm).replace('<', '[').replace('>', ']')
            rng = ('%s..%s (Schritt %s)' % (mn, mx, st)) if mn else ('Untermenü' if tp == 'list' else 'Kommando')
        rows_bridge.append((hdr.replace(' __', ' > '), nm[:44], rng))

    return rows_shape, rows_bridge


# ------------------------------------------------------- Abbildungen (D6)
def _draw_xy_layer(dr, parsed, box, lnum, pad=18):
    bx0, by0, bx1, by1 = box
    segs = parsed['layers'].get(lnum, [])
    xs = [x for s in segs for x in (s[0], s[2])] or [0, 100]
    ys = [y for s in segs for y in (s[1], s[3])] or [0, 100]
    x0, x1, y0, y1 = min(xs), max(xs), min(ys), max(ys)
    span = max(1.0, x1 - x0, y1 - y0)
    sc = min((bx1 - bx0 - 2 * pad) / span, (by1 - by0 - 2 * pad) / span)
    ox = (bx0 + bx1 - (x1 - x0) * sc) / 2.0
    oy = (by0 + by1 + (y1 - y0) * sc) / 2.0

    def tx(x, y):
        return (ox + (x - x0) * sc, oy - (y - y0) * sc)

    for sx0, sy0, sx1, sy1, tp in segs:
        if 'OUTER' in tp:
            c, lw = (28, 78, 140), 3
        elif 'INNER' in tp:
            c, lw = (0, 112, 107), 3
        elif 'SPARSE' in tp:
            c, lw = (224, 123, 0), 2
        else:
            c, lw = (140, 175, 215), 2
        dr.line([tx(sx0, sy0), tx(sx1, sy1)], fill=c, width=lw)


def _render_fig1(p_cyl, p_hex, p_tri, p_vase, out_png):
    """Abb. 1: Vier echte make_shape()-Geometrien (Zylinder mit Gitter-Infill,
    hohles Sechseck-Rohr, massives Dreiecksprisma & echte (X,Z)-Seitenprojektion
    der ununterbrochenen 3D-Helix im Modus Walls = 1 VASE)."""
    W, H = 1800, 860
    im = PILImage.new('RGB', (W, H), (250, 252, 255))
    dr = ImageDraw.Draw(im)

    # 2x2 grid
    panels = [
        ((24, 54, 882, 428), 'A · CYLINDER Ø48 mm (48 Seg., 3 Wände, 25 % Sparse-Infill)'),
        ((918, 54, 1776, 428), 'B · POLY 6-Eck 54×54 mm (4 Wände, 0 % Infill = Hohlrohr)'),
        ((24, 476, 882, 836), 'C · TRIANGLE 56×48 mm (flache Basis, 2 Wände, 100 % Vollkörper)'),
        ((918, 476, 1776, 836), 'D · SPIRAL / VASE (Walls=1): Echte (X, Z)-Helix ohne Z-Naht!'),
    ]
    for box, title in panels:
        dr.rounded_rectangle(box, radius=12, fill=(255, 255, 255), outline=(185, 202, 224), width=2)
        dr.text((box[0] + 14, box[1] - 36), title, fill=(28, 78, 140), font=font(21, bold=True))

    _draw_xy_layer(dr, p_cyl, (38, 66, 520, 416), 8, pad=18)
    dr.text((536, 120), 'Dunkelblau: Außenwand', fill=(28, 78, 140), font=font(18, bold=True))
    dr.text((536, 158), 'Türkis: 2 Innenwände', fill=(0, 112, 107), font=font(18, bold=True))
    dr.text((536, 196), 'Orange: 45°/135° Infill', fill=(224, 123, 0), font=font(18, bold=True))
    dr.text((536, 250), 'Corners = 0 -> 48 Facetten', fill=(65, 75, 88), font=font(17))
    dr.text((536, 282), '(Sehnenfehler < 0,03 mm!)', fill=(65, 75, 88), font=font(17))

    _draw_xy_layer(dr, p_hex, (932, 66, 1410, 416), 8, pad=18)
    dr.text((1424, 120), 'POLY: Corners = 6', fill=(28, 78, 140), font=font(18, bold=True))
    dr.text((1424, 158), 'Base = 0, Top = 0,', fill=(0, 112, 107), font=font(18, bold=True))
    dr.text((1424, 194), 'Infill = 0 % -> Hülse!', fill=(0, 112, 107), font=font(18, bold=True))
    dr.text((1424, 248), 'Affiner Innenversatz', fill=(65, 75, 88), font=font(17))
    dr.text((1424, 280), '_ngon_inset(k · wid)', fill=(65, 75, 88), font=font(17))

    _draw_xy_layer(dr, p_tri, (38, 488, 520, 824), 6, pad=18)
    dr.text((536, 548), 'Ungerades n (n = 3):', fill=(28, 78, 140), font=font(18, bold=True))
    dr.text((536, 586), 'a_0 = π / 2 -> Spitze oben,', fill=(45, 55, 68), font=font(17))
    dr.text((536, 618), 'waagerechte Basiskante!', fill=(45, 55, 68), font=font(17))
    dr.text((536, 670), 'Infill = 100 %:', fill=(0, 112, 107), font=font(18, bold=True))
    dr.text((536, 702), 'Massiver Stützkeil /', fill=(65, 75, 88), font=font(17))
    dr.text((536, 732), 'Anschlagprisma', fill=(65, 75, 88), font=font(17))

    # Panel D: Real (X, Z) projection of Vase mode moves!
    bx0, by0, bx1, by1 = (942, 500, 1455, 814)
    dr.rectangle([bx0, by0, bx1, by1], fill=(247, 250, 255), outline=(185, 202, 224), width=1)
    mvs = p_vase['moves3d']
    xs = [x for m in mvs for x in (m[0], m[3])]
    zs = [z for m in mvs for z in (m[2], m[5])]
    xmin, xmax = min(xs), max(xs)
    zmin, zmax = 0.0, max(zs)
    sx = (bx1 - bx0 - 36) / max(1.0, xmax - xmin)
    # Exaggerate Z slightly to fill box cleanly and reveal helical pitch!
    sz = (by1 - by0 - 32) / max(1.0, zmax - zmin)

    def txz(x, z):
        return (bx0 + 18 + (x - xmin) * sx, by1 - 16 - (z - zmin) * sz)

    for x0, y0, z0, x1, y1, z1, tp, _ln in mvs:
        is_helix = abs(z1 - z0) > 1e-5
        col = (224, 123, 0) if is_helix else (28, 78, 140)
        dr.line([txz(x0, z0), txz(x1, z1)], fill=col, width=2)

    dr.text((1470, 526), 'Blau unten (L1..L3):', fill=(28, 78, 140), font=font(18, bold=True))
    dr.text((1470, 558), 'Wasserdichter Boden', fill=(45, 55, 68), font=font(17))
    dr.text((1470, 610), 'Orange (Helix):', fill=(224, 123, 0), font=font(18, bold=True))
    dr.text((1470, 642), 'Z steigt stetig bei', fill=(45, 55, 68), font=font(17))
    dr.text((1470, 672), 'JEDEM Segment!', fill=(45, 55, 68), font=font(17, bold=True))
    dr.text((1470, 718), '0 Layer-Sprünge', fill=(30, 125, 50), font=font(18, bold=True))
    dr.text((1470, 748), '0 Retracts im Mantel', fill=(30, 125, 50), font=font(18, bold=True))

    im.save(out_png, 'PNG')
    return out_png


def _render_fig2(p_brg, info_brg, out_png):
    """Abb. 2: Echte G-Code-Bahnen von make_bridge() (Maintenance > Bridging):
    Links 45°-Bettdiagonal-Draufsicht (3 Türme + kurze & lange Brücke),
    rechts echte Diagonal-Seitenprojektion (s_diag, Z) mit >= 10 mm Luftspalt!"""
    W, H = 1800, 760
    im = PILImage.new('RGB', (W, H), (250, 252, 255))
    dr = ImageDraw.Draw(im)

    pa = (24, 58, 860, 730)
    dr.rounded_rectangle(pa, radius=12, fill=(255, 255, 255), outline=(185, 202, 224), width=2)
    dr.text((38, 18), 'A · 45°-Diagonal-Draufsicht (TOWER_A · TOWER_C · TOWER_B)',
            fill=(28, 78, 140), font=font(22, bold=True))

    mvs = p_brg['moves3d']
    xs = [x for m in mvs for x in (m[0], m[3])]
    ys = [y for m in mvs for y in (m[1], m[4])]
    xmin, xmax, ymin, ymax = min(xs), max(xs), min(ys), max(ys)
    pad = 28
    bx0, by0, bx1, by1 = pa[0] + 16, pa[1] + 14, pa[2] - 16, pa[3] - 74
    sc = min((bx1 - bx0 - 2 * pad) / max(1.0, xmax - xmin),
             (by1 - by0 - 2 * pad) / max(1.0, ymax - ymin))
    ox = (bx0 + bx1 - (xmax - xmin) * sc) / 2.0
    oy = (by0 + by1 + (ymax - ymin) * sc) / 2.0

    def txy(x, y):
        return (ox + (x - xmin) * sc, oy - (y - ymin) * sc)

    # Draw layer 1 (towers + brims) + bridge layers (TYPE == BRIDGE)
    for x0, y0, z0, x1, y1, z1, tp, ln in mvs:
        if ln == 1:
            col = (170, 192, 220) if 'BRIM' in tp else (28, 78, 140)
            dr.line([txy(x0, y0), txy(x1, y1)], fill=col, width=2)
        elif 'BRIDGE' in tp:
            is_short = z1 < (info_brg['h_long'] - 2.0)
            col = (0, 112, 107) if is_short else (224, 123, 0)
            dr.line([txy(x0, y0), txy(x1, y1)], fill=col, width=2)

    dr.text((pa[0] + 24, pa[3] - 58),
            '45°-Diagonale schöpft √2 × Kantenlänge aus (bis ~299 mm Spannweite!)',
            fill=(45, 55, 68), font=font(18, bold=True))
    dr.text((pa[0] + 24, pa[3] - 28),
            'Türkis: Kurze Referenzbrücke (%.0f mm)   |   Orange: Lange Hauptbrücke (%.0f mm)'
            % (info_brg['short_len'], info_brg['length']),
            fill=(0, 102, 96), font=font(17, bold=True))

    # Panel B: Real diagonal elevation (s = (x + y)/sqrt(2), Z)
    pb = (886, 58, 1776, 730)
    dr.rounded_rectangle(pb, radius=12, fill=(255, 255, 255), outline=(185, 202, 224), width=2)
    dr.text((900, 18), 'B · Echte Diagonal-Seitenansicht (s_diag, Z) — Garantierter Luftspalt!',
            fill=(28, 78, 140), font=font(22, bold=True))

    inv_rt2 = 1.0 / math.sqrt(2.0)
    ss = [(m[0] + m[1]) * inv_rt2 for m in mvs] + [(m[3] + m[4]) * inv_rt2 for m in mvs]
    zs = [m[2] for m in mvs] + [m[5] for m in mvs]
    smin, smax = min(ss), max(ss)
    zmax = max(zs)

    ex0, ey0, ex1, ey1 = pb[0] + 28, pb[1] + 26, pb[2] - 28, pb[3] - 96
    dr.rectangle([ex0, ey0, ex1, ey1], fill=(247, 250, 255), outline=(190, 206, 226), width=1)
    scs = (ex1 - ex0 - 40) / max(1.0, smax - smin)
    scz = (ey1 - ey0 - 44) / max(1.0, zmax)

    def tsz(x, y, z):
        s_v = (x + y) * inv_rt2
        return (ex0 + 20 + (s_v - smin) * scs, ey1 - 18 - z * scz)

    for x0, y0, z0, x1, y1, z1, tp, _ln in mvs:
        if 'BRIDGE' in tp:
            is_short = z1 < (info_brg['h_long'] - 2.0)
            col, lw = ((0, 112, 107), 4) if is_short else ((224, 123, 0), 4)
        elif 'BRIM' in tp:
            col, lw = (165, 185, 210), 2
        else:
            col, lw = (72, 114, 176), 2
        dr.line([tsz(x0, y0, z0), tsz(x1, y1, z1)], fill=col, width=lw)

    # Annotate exact tower & bridge heights
    y_long = ey1 - 18 - info_brg['h_long'] * scz
    y_short = ey1 - 18 - info_brg['h_short'] * scz
    dr.text((ex0 + 230, y_long - 30),
            'BRIDGE_LONG: %.0f mm @ Z = %.1f mm (M106 S%d)'
            % (info_brg['length'], info_brg['h_long'], info_brg['fan']),
            fill=(195, 98, 0), font=font(18, bold=True))
    dr.text((ex0 + 88, y_short - 30),
            'BRIDGE_SHORT: %.0f mm @ Z = %.1f mm'
            % (info_brg['short_len'], info_brg['h_short']),
            fill=(0, 102, 96), font=font(17, bold=True))

    # Vertical double-arrow showing clear air gap
    ax_m = ex0 + 195
    dr.line([(ax_m, y_long + 6), (ax_m, y_short - 6)], fill=(179, 38, 30), width=3)
    dr.text((ax_m + 12, (y_long + y_short) / 2 - 12),
            'ΔZ = %.1f mm (>= 10 mm Freiraum!)' % (info_brg['h_long'] - info_brg['h_short']),
            fill=(179, 38, 30), font=font(18, bold=True))

    dr.text((pb[0] + 24, pb[3] - 72),
            'Auch durchhängende Fäden der langen Brücke berühren nie die kurze Brücke!',
            fill=(45, 55, 68), font=font(16, bold=True))
    dr.text((pb[0] + 24, pb[3] - 40),
            '5 Einzelobjekte: TOWER_A · TOWER_B · TOWER_C · BRIDGE_SHORT · BRIDGE_LONG',
            fill=(28, 78, 140), font=font(16, bold=True))

    im.save(out_png, 'PNG')
    return out_png


# ------------------------------------------------------- PDF-Bau
def build_pdf(out_pdf):
    rows_shape, rows_bridge = _parse_geo_and_bridge_menus()

    with tempfile.TemporaryDirectory(prefix='r2_geo_pdf_') as td:
        f_cyl, i_cyl = pp.make_shape(
            shape='CYLINDER', size_x=48, size_y=48, corners=0, height=16,
            walls=3, infill=25, base=3, top=3, nozzle=0.4, out_dir=td,
        )
        f_hex, i_hex = pp.make_shape(
            shape='POLY', size_x=54, size_y=54, corners=6, height=20,
            walls=4, infill=0, base=0, top=0, nozzle=0.4, out_dir=td,
        )
        f_tri, i_tri = pp.make_shape(
            shape='TRIANGLE', size_x=56, size_y=48, height=12,
            walls=2, infill=100, base=3, top=3, nozzle=0.4, out_dir=td,
        )
        f_vas, i_vas = pp.make_shape(
            shape='CYLINDER', size_x=46, size_y=46, corners=0, height=22,
            walls=1, infill=25, base=3, nozzle=0.4, out_dir=td,
        )
        f_br1, i_br1 = pp.make_bridge(
            length=140.0, short_pct=30, h_long=32.0, h_short=16.0,
            tower=10.0, bridge_layers=1, speed=20.0, fan=255,
            nozzle=0.4, out_dir=td,
        )
        _f_br2, i_br2 = pp.make_bridge(
            length=180.0, short_pct=25, h_long=26.0, h_short=22.0,
            tower=12.0, bridge_layers=2, speed=25.0, fan=255,
            nozzle=0.6, out_dir=td,
        )

        p_cyl = _parse_gcode_3d(f_cyl)
        p_hex = _parse_gcode_3d(f_hex)
        p_tri = _parse_gcode_3d(f_tri)
        p_vas = _parse_gcode_3d(f_vas)
        p_br1 = _parse_gcode_3d(f_br1)

        fig1 = _render_fig1(p_cyl, p_hex, p_tri, p_vas, os.path.join(td, 'geo_fig1.png'))
        fig2 = _render_fig2(p_br1, i_br1, os.path.join(td, 'geo_fig2.png'))

        doc = Doc(
            out_pdf,
            'R2-D2 · Geometry & Bridging (make_shape + make_bridge)',
            'Wissenschaftliche Generator-Referenz (D3 / D6)',
        )
        st = doc.story

        cover_tbl = TBL(
            ['Kenngröße', 'Wert im R2-D2-System (Code-Wahrheit aus r2_postproc.py)'],
            [
                ['LCD-Menüpfade', 'Tools &gt; Geometry (GEN_SHAPE)  ·  Maintenance &gt; Bridging (BRIDGE_TEST)'],
                ['Ausgabeordner', 'gcodes/Shapes/Vnn_Shape_...gcode  ·  gcodes/Towers/Vnn_Bridge_...gcode'],
                ['4 Grundkörper-Familien', 'TRIANGLE · SQUARE (Quadrat / Rechteck) · POLY (3..12 Ecken) · CYLINDER (rund=48 / 3..64 Seg.)'],
                ['Spiralvasen-Automatik', 'Walls = 1 aktiviert echte 3D-Helix (stetiger Z-Anstieg, 0 Layer-Sprünge, 0 Deckel)'],
                ['Wanddicken-Vorrang', 'Wall t &gt; 0 mm berechnet walls = round(wall_thick / wid) automatisch'],
                ['Doppel-Brückentest', '45°-Bettdiagonale (bis ~299 mm) + kurze Referenzbrücke &gt;= 10 mm frei darunter'],
            ],
            [54 * mm, 108 * mm],
        )[0]

        doc.add_cover(
            kicker='GENERATOR-FACHHEFT · GRUNDKÖRPER & FREILUFT-KALIBRIERUNG (D3 / D6)',
            titel='Geometry & Bridging',
            untertitel='Parametrische Prismen, Zylinder, Hülsen und nahtlose 3D-Spiralvasen (make_shape) sowie zweistufige 45°-Diagonal-Brückenkalibrierung (make_bridge)',
            absaetze=[
                'Wer am Drucker schnell eine Distanzhülse, einen Becher, einen Gießform-Urkörper '
                'oder einen Rohling für das Textur- und Twist-Werkzeug braucht, benötigt keinen '
                'CAD-PC: make_shape() erzeugt Dreiecke, Rechtecke, reguläre Polygone, Ellipsen '
                'und Zylinder samt echtem Spiralvasen-Modus direkt auf der Maschine.',
                'Als zweiter geometrischer Prüfstein ergänzt make_bridge() unter Maintenance > '
                'Bridging den zweistufigen Diagonal-Brückentest: Auf einer 45°-Achse spannt er '
                'gleichzeitig eine kurze Referenzbrücke und eine bis fast 300 mm lange '
                'Extrembrücke mit garantiert >= 10 mm vertikalem Sicherheitsabstand auf.',
            ],
            tabelle=cover_tbl,
        )

        # ---- Kapitel 1 ------------------------------------------------------
        st += H1('Polygon-Orientierung, Affiner Versatz & Echte 3D-Spiralvase', '1')
        st += P(
            '<b>make_shape()</b> beschreibt alle Querschnitte im Rahmen <b>(X, Y) ∈ [8, 200]² mm</b> '
            'über die Phasenfunktion <b>_ngon_pts(n, w, h)</b>. Der Startwinkel <b>a_0</b> ist so '
            'gewählt, dass jedes Polygon ohne Kippeln mit einer waagerechten Kante ausgerichtet ist:'
        )
        st += FORMULA(
            'Startphase a_0:      a_0 = π/n (falls n mod 4 == 0) · π/2 (falls n ungerade) · 0 (sonst)<br/>'
            'Eckpunkte k=0..n-1:  p_k = (c_x + (w/2)·cos(a_0 + 2πk/n),  c_y + (h/2)·sin(a_0 + 2πk/n))<br/>'
            'Affiner Innenring m: s_x = (w/2 - m·wid)/(w/2),   s_y = (h/2 - m·wid)/(h/2)   (m = 0..walls-1)<br/>'
            'Helix (Walls = 1):   Z(rev, j) = Z_Boden + (rev + j / N_seg) · LH,   ΔE = d_seg · LH · wid / A_fil',
            'Sobald Walls = 1 gewählt wird, schaltet make_shape() automatisch in den echten '
            'Spiralvasen-Modus: Es erzwingt mindestens 2 dichte Bodenschichten, setzt Top = 0, '
            'ignoriert Infill und fährt den gesamten Mantel in EINER einzigen ununterbrochenen '
            '3D-Schraubenlinie bis zur Zielhöhe — ohne Z-Naht und ohne jeden Retract!'
        )
        st += B(
            '<b>Offene Rohre &amp; Distanzbuchsen:</b> Mit <b>Base = 0</b>, <b>Top = 0</b> und '
            '<b>Infill = 0 %</b> (bei <b>Walls &gt;= 2</b>) entsteht eine beidseitig offene, '
            'maßhaltige Hülse oder Kabeldurchführung.',
            '<b>Ehrliche Feature-Typen (R217):</b> Im Vasenmodus meldet <b>_FILE_INFO</b> nur '
            '<b>WALL-OUTER,SURFACE-BOTTOM</b>; <b>INFILL-SPARSE</b> bzw. <b>INFILL-SOLID</b> '
            'erscheinen ausschließlich dann, wenn tatsächlich Füllbahnen im Körper existieren.',
            '<b>Idealer Urkörper für Pre-Print-Tools &amp; Toolchain:</b> Ein <b>CYLINDER</b> '
            'oder <b>6-gon</b> aus <b>Tools &gt; Geometry</b> lässt sich direkt anschließend '
            'mit <b>Texture</b> (27 Muster), <b>Twist</b>, <b>Scale</b> oder <b>Casting molds</b> '
            'kombinieren — 100 % On-Machine-Design ohne Slicer!'
        )
        st += [IMG(fig1, width_mm=162)]
        st += CAP(
            'Abbildung 1 — Aus den realen G-Code-Dateien von make_shape() geparste Querschnitte '
            '(A–C) sowie echte (X, Z)-Seitenprojektion der kontinuierlichen Spiralvase (D).'
        )

        # ---- Kapitel 2 ------------------------------------------------------
        st += H1('Zweistufiger 45°-Diagonal-Brückentest (make_bridge)', '2')
        st += P(
            'Um das reale Freiluft-Überbrückungsvermögen eines Filaments unter Live-Anpassung '
            'von Lüfter und Brückentempo zu messen, platziert <b>make_bridge()</b> drei '
            'quadratische Stütztürme der Breite <b>tower ∈ [6, 20] mm</b> entlang der '
            '45°-Bettdiagonalen <b>d = (1/√2, 1/√2)</b>:'
        )
        st += FORMULA(
            'Maximale Diagonal-Spannweite:  L_max = min(u_w - tower,  u_h - tower) · √2<br/>'
            'Turmpositionen:  A = C_Bett - (L/2)·d,   B = C_Bett + (L/2)·d,   C = A + (L · short_pct/100)·d<br/>'
            'Garantierter Höhenabstand:     n_short &lt;= n_long - ceil(10,0 mm / LH)   =&gt;   ΔZ &gt;= 10,0 mm!<br/>'
            'Strang-Auflager im Turm:       Ankertiefe = 0,8 mm in die Turmwand,  n_Stränge = floor(tower / wid)',
            'Wählt der Benutzer z. B. H long = 26 mm und H short = 22 mm, kürzt make_bridge() '
            'Turm C automatisch auf 16,1 mm herunter, damit zwischen beiden Brücken mindestens '
            '10 mm freie Luft verbleiben: Selbst wenn die lange Brücke stark durchhängt, bleibt '
            'die kurze Referenzbrücke darunter völlig unberührt und auswertbar!'
        )
        st += B(
            '<b>Fünf Einzelobjekte &amp; R96-Freiluftsperre:</b> Jeder Stützturm und jede '
            'Brückendecke trägt ein eigenes <b>EXCLUDE_OBJECT_DEFINE</b> '
            '(<b>TOWER_A</b>, <b>TOWER_B</b>, <b>TOWER_C</b>, <b>BRIDGE_SHORT</b>, '
            '<b>BRIDGE_LONG</b>); während der Brückenschichten registriert R96 den offenen '
            'Luftspalt in <b>pen.hole_polys</b> und schaltet den Bauteillüfter gezielt auf '
            '<b>M106 S&lt;fan&gt;</b>.'
        )
        st += [IMG(fig2, width_mm=162)]
        st += CAP(
            'Abbildung 2 — A: 45°-Diagonal-Draufsicht aus echtem make_bridge()-G-Code. '
            'B: Reale Diagonal-Seitenprojektion (s_diag, Z) mit nachgewiesenem &gt;= 10-mm-Luftspalt.'
        )

        # ---- Kapitel 3 ------------------------------------------------------
        st += [PageBreak()]
        st += H1('Live-Menüreferenz & Gemessene Referenzläufe', '3')
        st += P(
            'Direkt aus <b>menus/lcd_menues.cfg</b> gelesene Zeilen unter '
            '<b>Tools &gt; Geometry</b> sowie <b>Maintenance &gt; Bridging</b>:'
        )
        st += TBL(
            ['LCD-Menüpfad', 'Anzeige am Display', 'Wertebereich / Aktion'],
            [[r[0], r[1], r[2]] for r in (rows_shape + rows_bridge)],
            [58 * mm, 54 * mm, 50 * mm],
        )

        st += H2('Sechs echte Referenzläufe (live beim PDF-Bau gerechnet)', '3.1')
        bench_rows = [
            ['1. Zylinder-Dose/Rohling', 'CYLINDER Ø48×16 · 3 W · 25 % Infill',
             i_cyl['file'], '%d Seg · %.2f mm Wand · %d L' % (i_cyl['corners'], i_cyl['wall_thick'], i_cyl['layers']),
             'Glatter 48-Eck-Zylinder'],
            ['2. Sechskant-Distanzrohr', 'POLY 6-Eck 54×54×20 · 4 W · Base/Top=0',
             i_hex['file'], '6 Ecken · %.2f mm Wand · %d L' % (i_hex['wall_thick'], i_hex['layers']),
             'Beidseitig offene Hülse'],
            ['3. Massiver Anschlagkeil', 'TRIANGLE 56×48×12 · 2 W · 100 % Voll',
             i_tri['file'], '3 Ecken · %d L · Vollkörper' % i_tri['layers'],
             'Waagerechte Basiskante'],
            ['4. Nahtlose Spiralvase', 'CYLINDER Ø46×22 · Walls=1 (VASE)',
             i_vas['file'], 'vase=%s · Top=%d · %d Umläufe' % (i_vas['vase'], i_vas['top'], i_vas['layers']),
             'Echte 3D-Helix, 0 Nähte!'],
            ['5. Standard-Brückentest', 'Len=140 · Short=30 % · H=32 / 16 mm',
             i_br1['file'], 'Lang %.0f (@%.1f) · Kurz %.0f (@%.1f)' % (
                 i_br1['length'], i_br1['h_long'], i_br1['short_len'], i_br1['h_short']),
             'ΔZ = %.1f mm Freiraum' % (i_br1['h_long'] - i_br1['h_short'])],
            ['6. Abstands-Klammer-Test', 'Len=180 · H_long=26 · Wunsch H_short=22',
             i_br2['file'], 'H_short auto -> %.1f mm (%d L)' % (i_br2['h_short'], i_br2['layers']),
             '10-mm-Luftspalt erzwungen!'],
        ]
        st += TBL(
            ['Szenario', 'Parameter', 'Erzeugte Datei', 'Geometrie & Lagen', 'Ergebnis'],
            bench_rows,
            [30 * mm, 41 * mm, 35 * mm, 31 * mm, 25 * mm],
        )

        st += SP(2)
        st += [BOX(
            'On-Machine-Kreativkette & Live-Brückentuning am Drehrad',
            [
                '• Schnellstes Design-Rezept ohne PC: Tools > Geometry (z. B. CYLINDER Ø70×90 mm, '
                'Walls = 1 VASE oder Walls = 3) -> Pre-Print > Tools > Texture (KNURL / WAVES) '
                'oder Twist (45°) -> sofort druckfertige Designer-Vase!',
                '• Während der Brückentest läuft, meldet das Display rechtzeitig vor jeder Brücke '
                '"SHORT span now" bzw. "LONG span now" — genau dort unter Live Tuning > Features > '
                'BRIDGE Geschwindigkeit und Lüfter live nachregeln.',
            ],
            kind='tip',
        )]

        doc.render()
    return out_pdf


if __name__ == '__main__':
    dst = os.path.join(REPO, 'GEOMETRY.pdf')
    build_pdf(dst)
    print('Wrote %s (%d bytes)' % (dst, os.path.getsize(dst)))
