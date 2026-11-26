#!/usr/bin/env python3
# -*- coding: utf-8 -*-
""" make_labels_pdf.py — Wissenschaftliches Generator-Fachheft (D3 / D6):
    Beschriftungsschilder, Inlay-Schilder & Text-Stempel (Tools > Labels).

    Alle Abbildungen und Referenzläufe werden zur Bauzeit LIVE aus make_labels(),
    _label_text_lines() und _stroke_offsets() in tools/r2_postproc.py sowie aus
    menus/lcd_menues.cfg erzeugt (Regel D6). Versionsstempel aus r2_version (r165).
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
def _parse_label_gcode(gcode_path):
    layers = {}
    layer_z = {}
    m600_layers = []
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
            if s.startswith('M600'):
                m600_layers.append(cur_layer)
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
        'm600_layers': m600_layers,
        'objs': objs,
        'total_e': total_e,
        'n_layers': max(layers.keys()) if layers else 0,
    }


# ------------------------------------------------------- Live-Menüextraktor
def _parse_labels_menu():
    cfg_path = os.path.join(REPO, 'menus', 'lcd_menues.cfg')
    txt = open(cfg_path, encoding='utf-8').read()
    blocks = re.split(r'(?m)^(?=\[menu )', txt)
    secs = [b for b in blocks if b.startswith('[menu __main __gen __labels')]
    rows = []
    seen_ch = False
    for sec in secs:
        lines = [l.strip() for l in sec.strip().splitlines() if l.strip()]
        hdr = lines[0].strip('[]').replace('menu __main __gen __labels', 'Tools > Labels')
        # Einzelzeichen-Untermenüs (__txt __az / __09 / __sym / __uml) bündeln
        if any(k in hdr for k in ('__txt __az __', '__txt __09 __', '__txt __sym __', '__txt __uml __')):
            if not seen_ch:
                seen_ch = True
                rows.append((
                    'Tools > Labels > txt > [A-Z/0-9/ÄÖÜ/Sym]',
                    'Drehrad-Zeichensatz (A-Z, a-z, 0-9, ÄÖÜß, Symbole)',
                    'Klick hängt Zeichen an Zeile an',
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
            '__txt __ln': 'Line: [1..3] aktive Textzeile (~)',
            '__txt __spc': 'Space (Leerzeichen anfügen)',
            '__txt __del': 'Backspace (letztes Zeichen löschen)',
            '__txt __clr': 'Clear text (Entwurf leeren)',
            '__txt __add': 'Add label to queue (in Liste legen)',
            '__fnt': 'Font: SMOOTH/MONO/COND/NARROW/CAPS/SCRIPT/HAND/PLATE',
            '__w': 'Width: [12..320]mm',
            '__h': 'Height: [10..320]mm',
            '__mod': 'Fit mode: GROW (Schild wächst) / FIXED',
            '__fsz': 'Cap height: [0=Auto .. 40]mm',
            '__str': 'Stroke width: [0=Auto .. 5]mm',
            '__shp': 'Shape: RECT / ROUND / OVAL',
            '__crn': 'Corner R: [0..12]mm (ROUND)',
            '__bw': 'Border walls: [0..4] Rahmenlinien',
            '__hol': 'Hole: OFF / LEFT / RIGHT / TOP / BOTTOM',
            '__hd': 'Hole Ø: [2.5..16]mm',
            '__rng': 'External ring: ON / OFF (Außenöse)',
            '__c2': '2-Color (M600): ON / OFF',
            '__stm': 'Stamp mode (Stempel R168): ON / OFF',
            '__hdl': 'Stamp handle: 0=Aus / 1=Mitdruck / 2=Separat / 3=Nur Griff',
            '__go': 'Create plate (2× Klick = Start)',
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
def _fig_shapes_and_fonts(p_rect, p_round, p_oval, out_png):
    """Abb. 1: Links echte G-Code-Werkzeugbahnen der drei Schildformen
    (RECT + Rahmen + Loch, ROUND + Außenöse, OVAL + SCRIPT + Purge-Tower);
    rechts echte Vektor-Schriftkarte aller 8 eingebetteten Strichschriften
    über _label_text_lines() + _stroke_offsets()."""
    W_img, H_img = 1520, 620
    im = PILImage.new('RGB', (W_img, H_img), '#ffffff')
    dr = ImageDraw.Draw(im)
    f_title = font(18, bold=True)
    f_sub = font(14, bold=True)
    f_sm = font(12)

    # Linkes Panel: 3 echte Schild-Läufe untereinander
    dr.rounded_rectangle((20, 18, 760, 602), radius=10,
                         fill='#f8fafd', outline='#bfd0e6', width=2)
    dr.text((36, 28),
            'A. Echte G-Code-Bahnen (Basis = Blau · Text/Rahmen = Orange)',
            fill='#1c4e8c', font=f_title)
    dr.text((36, 52),
            '3 reale make_labels()-Läufe (text_layers=4: 2 Lagen verankert + 2 Lagen erhaben):',
            fill='#475569', font=f_sm)

    cards = [
        (p_rect, '1. RECT (68×28 mm, Hole=LEFT Ø5, Border=2, CAPS)'),
        (p_round, '2. ROUND (R=5 mm, 2 Zeilen "~", Außenöse Ring=LEFT)'),
        (p_oval, '3. OVAL (74×34 mm, Font=SCRIPT, R183-Kollisionsschutz + Tower)'),
    ]
    for idx, (gc_p, title_c) in enumerate(cards):
        prs = _parse_label_gcode(gc_p)
        cy0 = 80 + idx * 168
        cw, ch = 708, 156
        dr.rounded_rectangle((36, cy0, 36 + cw, cy0 + ch), radius=8,
                             fill='#ffffff', outline='#cbd5e1', width=1)
        dr.text((48, cy0 + 6), title_c, fill='#163c6e', font=f_sub)

        # Basis-Layer (Layer 2) + Text-Layer (letzter Layer)
        segs_base = prs['layers'].get(2, [])
        segs_txt = prs['layers'].get(prs['n_layers'], [])
        pts = [(x, y) for (x0, y0, x1, y1, _) in (segs_base + segs_txt)
               for (x, y) in ((x0, y0), (x1, y1))]
        if pts:
            xs = [p[0] for p in pts]
            ys = [p[1] for p in pts]
            xmin, xmax = min(xs) - 1.5, max(xs) + 1.5
            ymin, ymax = min(ys) - 1.5, max(ys) + 1.5
            sc = min((cw - 32) / max(1.0, xmax - xmin), (ch - 38) / max(1.0, ymax - ymin))
            ox = 36 + (cw - (xmax - xmin) * sc) / 2.0
            oy = cy0 + 28 + (ch - 36 - (ymax - ymin) * sc) / 2.0

            def lpx(xm, ym):
                return int(ox + (xm - xmin) * sc), int(cy0 + ch - 8 - (ym - ymin) * sc - (oy - (cy0 + 28)))

            for (x0, y0, x1, y1, tp) in segs_base:
                col = '#1c4e8c' if 'WALL' in tp else ('#94a3b8' if 'PRIME' in tp else '#dbeafe')
                dr.line((lpx(x0, y0), lpx(x1, y1)), fill=col, width=2 if 'WALL' in tp else 1)
            for (x0, y0, x1, y1, tp) in segs_txt:
                col = '#ea580c' if 'PRIME' not in tp else '#f59e0b'
                dr.line((lpx(x0, y0), lpx(x1, y1)), fill=col, width=2)

    # Rechtes Panel: Live gerenderte Schriftkarte aller 8 aktiven Vektorschriften
    dr.rounded_rectangle((780, 18, 1500, 602), radius=10,
                         fill='#f8fafd', outline='#bfd0e6', width=2)
    dr.text((798, 28),
            'B. Alle 8 eingebetteten Strichschriften (_stroke_offsets)',
            fill='#1c4e8c', font=f_title)
    dr.text((798, 52),
            'Echte mehrspurige Miter-Offsetbahnen (keine brüchigen Einzellinien; inkl. ÄÖÜß!):',
            fill='#475569', font=f_sm)

    fonts_show = [
        ('SMOOTH', 'Werkstatt ÄÖÜ 42'),
        ('MONO',   'PIN-0194 B2x4'),
        ('COND',   'Schmaler Schrank 12'),
        ('NARROW', 'Kabelkanal Nord-Süd'),
        ('CAPS',   'HAUPTSCHALTER 230V'),
        ('SCRIPT', 'Küche & Kräuter'),
        ('HAND',   'Gartenhaus Süd'),
        ('PLATE',  'R2-D2 STUDIO 08'),
    ]
    for idx, (fname, sample) in enumerate(fonts_show):
        ry0 = 80 + idx * 63
        rw, rh = 684, 55
        dr.rounded_rectangle((798, ry0, 798 + rw, ry0 + rh), radius=6,
                             fill='#ffffff', outline='#cbd5e1', width=1)
        dr.text((810, ry0 + 18), fname, fill='#1c4e8c', font=f_sub)

        # Echte Vektorpfade aus r2_postproc._label_text_lines + _stroke_offsets!
        box = (0.0, 0.0, 92.0, 12.0)
        raw_strokes, cap_mm = pp._label_text_lines(
            [sample], fname, box, 92.0, 12.0, font_size=7.4, stroke_w=0.95)
        sc_f = 5.1
        ox_f = 918
        oy_f = ry0 + rh - 9
        for sk in raw_strokes:
            off_paths = pp._stroke_offsets(sk, half=0.47, step=0.38)
            for op in off_paths:
                for k in range(len(op) - 1):
                    p1 = (int(ox_f + op[k][0] * sc_f), int(oy_f - op[k][1] * sc_f))
                    p2 = (int(ox_f + op[k + 1][0] * sc_f), int(oy_f - op[k + 1][1] * sc_f))
                    dr.line((p1, p2), fill='#0f2942', width=2)

    im.save(out_png)
    return out_png


def _fig_flip_and_stamp(p_flip, p_stamp, out_png):
    """Abb. 2: Links echte G-Code-Bahnen von Flip=1 (spiegelverkehrtes Layer-1-Inlay
    auf der glatten Druckbettseite!) vs. Stamp=1 + Handle=1 (Stempel + mitgedruckter
    Rastgriff auf derselben Platte); rechts Schichtaufbau-Vergleich der 3 Modi."""
    W_img, H_img = 1520, 560
    im = PILImage.new('RGB', (W_img, H_img), '#ffffff')
    dr = ImageDraw.Draw(im)
    f_title = font(18, bold=True)
    f_sub = font(14, bold=True)
    f_sm = font(12)

    # Linkes Panel: Echter G-Code von Flip=1 (oben) und Stamp=1+Handle=1 (unten)
    dr.rounded_rectangle((20, 18, 830, 542), radius=10,
                         fill='#f8fafd', outline='#bfd0e6', width=2)
    dr.text((36, 28),
            'A. Echte G-Code-Bahnen: Flip-Inlay (L1) & Stempel + Griff (Handle=1)',
            fill='#1c4e8c', font=f_title)
    dr.text((36, 52),
            'Beide Spezialmodi spiegeln die Schrift automatisch in X — das fertige Ergebnis liest sich richtig!',
            fill='#475569', font=f_sm)

    # Oben: Flip Layer 1
    prs_fl = _parse_label_gcode(p_flip)
    dr.rounded_rectangle((36, 80, 812, 285), radius=8,
                         fill='#ffffff', outline='#cbd5e1', width=1)
    dr.text((48, 88), '1. Flip = ON (Layer 1 am Bett): Text (Orange) + ausgesparte Basis (Blau) bündig!',
            fill='#163c6e', font=f_sub)
    segs_fl1 = prs_fl['layers'].get(1, [])
    pts = [(x, y) for (x0, y0, x1, y1, _) in segs_fl1 for (x, y) in ((x0, y0), (x1, y1))]
    if pts:
        xs, ys = [p[0] for p in pts], [p[1] for p in pts]
        xmin, xmax = min(xs) - 1.5, max(xs) + 1.5
        ymin, ymax = min(ys) - 1.5, max(ys) + 1.5
        sc = min(740.0 / max(1.0, xmax - xmin), 155.0 / max(1.0, ymax - ymin))
        ox = 36 + (776 - (xmax - xmin) * sc) / 2.0
        for (x0, y0, x1, y1, tp) in segs_fl1:
            p1 = (int(ox + (x0 - xmin) * sc), int(275 - (y0 - ymin) * sc))
            p2 = (int(ox + (x1 - xmin) * sc), int(275 - (y1 - ymin) * sc))
            col = '#ea580c' if 'TOP' in tp or 'TEXT' in tp else '#3b82f6'
            dr.line((p1, p2), fill=col, width=2)

    # Unten: Stamp + Handle=1
    prs_st = _parse_label_gcode(p_stamp)
    dr.rounded_rectangle((36, 300, 812, 524), radius=8,
                         fill='#ffffff', outline='#cbd5e1', width=1)
    dr.text((48, 308), '2. Stamp = ON, Handle = 1: Spiegelschrift-Relief + Rastbuchse + Griff rechts!',
            fill='#163c6e', font=f_sub)
    # Layer 2 zeigt die Stempelbasis + _StampFit168-Rastbuchse; Z ~ 5,48 mm zeigt die erhabene Spiegelschrift!
    segs_st_b = prs_st['layers'].get(2, [])
    mid_st = min((li for li, zz in prs_st['layer_z'].items() if zz >= 5.35), default=27)
    segs_st_face = prs_st['layers'].get(mid_st, [])
    pts2 = [(x, y) for (x0, y0, x1, y1, _) in (segs_st_b + segs_st_face)
            for (x, y) in ((x0, y0), (x1, y1))]
    if pts2:
        xs, ys = [p[0] for p in pts2], [p[1] for p in pts2]
        xmin, xmax = min(xs) - 2.0, max(xs) + 2.0
        ymin, ymax = min(ys) - 2.0, max(ys) + 2.0
        sc = min(740.0 / max(1.0, xmax - xmin), 175.0 / max(1.0, ymax - ymin))
        ox = 36 + (776 - (xmax - xmin) * sc) / 2.0
        for (x0, y0, x1, y1, tp) in segs_st_b:
            p1 = (int(ox + (x0 - xmin) * sc), int(512 - (y0 - ymin) * sc))
            p2 = (int(ox + (x1 - xmin) * sc), int(512 - (y1 - ymin) * sc))
            col = '#1c4e8c' if 'WALL' in tp else '#dbeafe'
            dr.line((p1, p2), fill=col, width=2 if 'WALL' in tp else 1)
        for (x0, y0, x1, y1, tp) in segs_st_face:
            p1 = (int(ox + (x0 - xmin) * sc), int(512 - (y0 - ymin) * sc))
            p2 = (int(ox + (x1 - xmin) * sc), int(512 - (y1 - ymin) * sc))
            dr.line((p1, p2), fill='#0f766e' if x0 > (xmin + xmax) / 2 + 8 else '#ea580c', width=2)

    # Rechtes Panel: Schematischer Z-Schichtvergleich der 3 Modi
    dr.rounded_rectangle((850, 18, 1500, 542), radius=10,
                         fill='#f8fafd', outline='#bfd0e6', width=2)
    dr.text((868, 28),
            'B. Z-Aufbau der 3 Betriebsarten im Vergleich',
            fill='#1c4e8c', font=f_title)
    dr.text((868, 52),
            'Wann wählt man welchen Modus blind am Display?',
            fill='#475569', font=f_sm)

    modes_vis = [
        (92, '1. Klassisch 2-Farbig (Color2 = ON, Flip = OFF)',
         'Basis (4 Lagen + Ironing) -> 1× M600 -> erhabener Text + Rahmen (2 Lagen)',
         '#dbeafe', '#ea580c', '1× M600 · spürbares Relief (auch blind ertastbar!)'),
        (242, '2. Bettseiten-Inlay (Color2 = ON, Flip = ON)',
         'Spiegeltext liegt bündig IN Layer 1..2 auf der PEI-Platte (2× M600)',
         '#dcfce7', '#15803d', 'Spiegelglatte, abwischbare Front ohne Staubkanten!'),
        (392, '3. Stempelmodus (Stamp = ON, Handle = 0..3)',
         '5,0-mm-Sockel mit _StampFit168-Rastbuchse + X-gespiegelte Stempelschrift',
         '#fef3c7', '#b45309', 'Für Stempelkissen, Ton, Keksteig & Wachs (TPU/PLA)'),
    ]
    for ym, ttl, sub, bg_c, bd_c, foot in modes_vis:
        dr.rounded_rectangle((868, ym, 1482, ym + 128), radius=8,
                             fill=bg_c, outline=bd_c, width=2)
        dr.text((884, ym + 12), ttl, fill='#0f2942', font=f_sub)
        dr.text((884, ym + 42), sub, fill='#334155', font=f_sm)
        dr.text((884, ym + 92), 'Praxisnutzen: ' + foot, fill=bd_c, font=f_sub)

    im.save(out_png)
    return out_png


# -------------------------------------------------------------- Hauptdokument
def build_pdf(out_pdf):
    lcd_rows = _parse_labels_menu()

    with tempfile.TemporaryDirectory(prefix='r2_labels_pdf_') as tmpdir:
        # 6 echte Referenzläufe von make_labels()
        # R231: text_layers=4 = 2 verankerte Inlay-Schichten + 2 erhabene Reliefschichten!
        p_rect, i_rect = pp.make_labels(
            ['WERKSTATT'], w=68.0, h=28.0, font='CAPS', shape='RECT',
            text_layers=4, hole_side=1, hole_d=5.0, border_walls=2, color2=True,
            nozzle=0.4, out_dir=tmpdir)

        p_round, i_round = pp.make_labels(
            ['Keller~Heizung'], w=64.0, h=32.0, font='SMOOTH', shape='ROUND',
            text_layers=4, corner=5.0, hole_side=1, ring=True, ring_d=6.0, color2=True,
            nozzle=0.4, out_dir=tmpdir)

        p_oval, i_oval = pp.make_labels(
            ['Kräuterbeet'], w=74.0, h=34.0, font='SCRIPT', shape='OVAL',
            text_layers=4, color2=True, nozzle=0.4, out_dir=tmpdir)

        p_flip, i_flip = pp.make_labels(
            ['230V NETZ'], w=64.0, h=26.0, font='PLATE', shape='RECT',
            color2=True, flip=1, brim=False, nozzle=0.4, out_dir=tmpdir)

        p_stamp, i_stamp = pp.make_labels(
            ['GEPRÜFT'], w=54.0, h=24.0, font='CAPS', text_layers=4, stamp=1,
            stamp_base=5.0, handle=1, color2=False, brim=False,
            nozzle=0.4, out_dir=tmpdir)

        # Mehrplatten-Split R170 (viele große Schilder -> _T1 / _T2)
        p_multi, i_multi = pp.make_labels(
            ['SCHRANK %d' % k for k in range(1, 10)],
            w=95.0, h=42.0, font='COND', mode='fixed', color2=True,
            nozzle=0.4, out_dir=tmpdir)

        fig1 = os.path.join(tmpdir, 'fig_labels_shapes_fonts.png')
        _fig_shapes_and_fonts(p_rect, p_round, p_oval, fig1)

        fig2 = os.path.join(tmpdir, 'fig_labels_flip_stamp.png')
        _fig_flip_and_stamp(p_flip, p_stamp, fig2)

        doc = Doc(
            out_pdf,
            kopf='R2-D2 Macro System · Generator Beschriftung / Labels (D3)',
            titel='Labels & Text-Stempel — Vektortypografie, Inlay & Blindbedienung',
        )
        st = doc.story

        cover_tbl = TBL(
            ['Kenngröße', 'Wert im aktuellen Produktivcode (R72 / R80 / R99 / R119 / R170 / R183)'],
            [
                ['Menüpfad am Display', 'Tools > Labels  (183 Menü-Sektionen inkl. Drehrad-Tastatur A-Z/0-9/ÄÖÜ)'],
                ['G-Code-Makros / Engine', 'LABEL_ADD · LABEL_FIT_CALC · LABEL_GENERATE · GEN_LABELS -> make_labels()'],
                ['8 Vektor-Strichschriften', 'SMOOTH · MONO · COND · NARROW · CAPS · SCRIPT · HAND · PLATE (+ Umlaute)'],
                ['Mehrspur-Buchstaben (R72)', '_stroke_offsets() füllt [-half, +half] lückenlos mit Miter-Parallelbahnen'],
                ['Auto-Fit & Überlaufteilung', 'GROW (Schild wächst mit Text) / FIXED · R170 teilt volle Platten in _T1, _T2..'],
                ['Formen, Löcher & Ösen', 'RECT · ROUND (Corner 0..12) · OVAL · Innenloch L/R/T/B (2 mm Steg) oder Ring-Öse'],
                ['Farb- & Spezialmodi', 'Color2 (1× M600 + Tower) · Flip=ON (Bettseiten-Inlay) · Stamp=ON (R168-Stempel)'],
                ['Ausgabeordner & Dateinamen', 'gcodes/Labels/Vnn_Schild_*.gcode · Vnn_Stempel_*.gcode · Vnn_Griff_*.gcode'],
            ],
            [56 * mm, 106 * mm],
        )[0]

        doc.add_cover(
            kicker='GENERATOR-FACHHEFT · WERKSTATT- & ALLTAGSTOOLS (D3 / D6)',
            titel='Labels, Inlays & Text-Stempel',
            untertitel='Mehrspurige Vektor-Typografie in 8 Schriften, automatische Schild-Größenanpassung, bündige Bettseiten-Inlays und rastbare Textstempel ohne CAD & Slicer',
            absaetze=[
                'Ein gutes Werkstatt- oder Klingelschild scheitert im klassischen 3D-Druck fast '
                'immer an dünnen Buchstabenstrichen: Ein einzelner Extrusionsfaden löst sich ab '
                'oder verschmilzt in engen Punzen. Der R2-Label-Generator speichert deshalb acht '
                'eigene, auf die Düsenbreite abgestimmte Strichskelett-Schriften direkt im Code '
                'und verbreitert jeden Strich über _stroke_offsets() zu geschlossenen Außenwänden '
                'mit sauberer Gehrung (Miter-Cap).',
                'Ob erhabenes Zweifarbschild mit gebügelter Grundplatte, spiegelglatt in die '
                'erste Schicht eingelegtes Flip-Schild oder fertiger Bürostempel samt passendem '
                'Rastgriff: Text am Drehrad oder in der Konsole eingeben genügt — Layout, '
                'Schriftgrad, Lochfreihaltung und Plattenaufteilung übernimmt die Mathematik.',
            ],
            tabelle=cover_tbl,
        )

        # ---- Kapitel 1 ------------------------------------------------------
        st += H1('Vektor-Typografie, Miter-Strichbreite & Auto-Fit-Mathematik', '1')
        st += P(
            'Jede der acht eingebetteten Schriften in <b>_LABEL_STROKE_FONTS</b> ist exakt auf '
            'Grundlinie (<b>baseline</b>), Versalhöhe (<b>cap_units</b>), Mittellänge '
            '(<b>x_units</b>) und Unterlänge (<b>desc_bot</b>) vermessen. Damit geschwungene '
            'Schreibschriften wie <b>SCRIPT</b> und <b>HAND</b> bei Buchstabenpaaren wie '
            '„fj“ oder „ji“ niemals ineinanderdrucken, erzwingt der R183-Kollisionswächter '
            'für jedes Zeichen eine Mindest-Dickte von <b>advance &gt;= max(x_ink) + 0,15</b>.'
        )
        st += FORMULA(
            'Proportionalrand:   m = max(1,5 mm,  0,07 · min(W, H),  margin_border)<br/>'
            'Schlüsselring-Loch: Randsteg = 2,0 mm,  Sperrband = 2,0 + D_hole + max(2,0, 0,07·min(W,H))<br/>'
            'OVAL-Innenbox:      s_oval = 1 / sqrt((B_w / W)² + (B_h / H)²)  -&gt; kein Buchstabe schneidet Rand!<br/>'
            'Miter-Strichversatz: p_k(j) = p(j) + n_bisect(j) · m_cap · (edge_2 - k · step)',
            'Im Modus GROW (Standard) bleiben W und H Mindestmaße: Passt eine lange Beschriftung '
            'bei der Mindest-Versalhöhe (2,8 mm bzw. gewählte font_size) nicht in das Textfenster, '
            'vergrößert _label_grow_fit() automatisch die Schildbreite bzw. -höhe, statt '
            'unleserliche Mikroschrift zu drucken! Im Modus FIXED bleiben W × H starr und die '
            'Versalhöhe skaliert maximal in das verfügbare Fenster.'
        )
        st += P(
            'Bis zu fünf Zeilen pro Schild werden einfach durch das Tilde-Zeichen <b>~</b> '
            'getrennt (am Display über <b>Labels &gt; Text &gt; Line 1..3</b> wählbar). '
            'Übersteigt eine große Schilderserie die Druckbettfläche, bricht <b>make_labels()</b> '
            'seit R170 nicht mehr mit einem Fehler ab, sondern teilt den Auftrag per trockenem '
            'Probe-Packing automatisch in lesereihenfolgetreue Teilplatten (<b>_T1</b>, '
            '<b>_T2</b>, … — jede mit eigenem Purge-Tower!).'
        )
        st += [IMG(fig1, width_mm=162)]
        st += CAP(
            'Abbildung 1 — Links: Echte G-Code-Werkzeugbahnen für RECT, ROUND (mit Außenöse) '
            'und OVAL (in SCRIPT + Purge-Tower). Rechts: Live über _stroke_offsets() erzeugte '
            'Schriftprobe aller 8 eingebetteten Vektorschriften.'
        )

        # ---- Kapitel 2 ------------------------------------------------------
        st += H1('Zweifarb-M600, Bettseiten-Inlay (Flip) & R168-Stempel', '2')
        st += NUM(
            '<b>Verankertes Zweifarb-Inlay & Relief (Color2 = ON, Flip = OFF, R231):</b> '
            '<b>text_layers</b> (2..4) definiert die gesamte Verankerungstiefe der Schrift: '
            'Bei <b>text_layers = 2</b> liegt die Schrift bündig in den obersten zwei '
            'Decklagen; bei <b>text_layers = 3..4</b> bleibt diese 2-Lagen-Wurzel in der '
            'Grundplatte verankert (Buchstaben können nie abscheren!) und wächst zusätzlich '
            '1..2 Lagen erhaben nach oben (mit M600, Ironing & 12×12-mm-<b>PURGE_TOWER</b>).',
            '<b>Bettseiten-Inlay (Flip = ON):</b> Dreht die Geometrie auf den Kopf und spiegelt '
            'die Schrift horizontal! Auf Layer 1 und 2 druckt zuerst die Kontrastschrift direkt '
            'auf die Druckplatte, danach füllt die Grundfarbe die Zwischenräume exakt aus. '
            'Nach dem Abnehmen ist die Unterseite die fertige Front: vollkommen plan, '
            'abwischbar und mit der edlen Struktur einer texturierten PEI-Platte.',
            '<b>Stempelmodus (Stamp = ON, R168/R170):</b> Spiegelt den Text automatisch für '
            'seitenrichtigen Abdruck, baut einen 5,0-mm-Sockel mit 10 % Infill sowie die '
            'konische <b>_StampFit168</b>-Rastbuchse auf der Rückseite. Über <b>Handle = 0..3</b> '
            'wählst du frei: <b>0</b> ohne Griff, <b>1</b> Griff direkt neben dem Stempel auf '
            'derselben Platte (wird pro Schicht zuletzt angefahren!), <b>2</b> separate '
            'Griff-Datei, <b>3</b> nur Ersatzgriff drucken.'
        )
        st += [IMG(fig2, width_mm=162)]
        st += CAP(
            'Abbildung 2 — Links: Echte G-Code-Bahnen des bündigen Layer-1-Inlays (Flip=ON) '
            'und eines Komplettstempels mit mitgedrucktem Griff (Stamp=ON, Handle=1). Rechts: '
            'Entscheidungshilfe für die drei Betriebsarten.'
        )

        # ---- Kapitel 3 ------------------------------------------------------
        st += [PageBreak()]
        st += H1('Live-Menüreferenz & Gemessene Referenzläufe', '3')
        st += P(
            'Direkt aus <b>menus/lcd_menues.cfg</b> gelesene Zeilen unter '
            '<b>Tools &gt; Labels</b>:'
        )
        st += TBL(
            ['LCD-Menüpfad', 'Anzeige am Display', 'Wertebereich / Aktion'],
            [[r[0], r[1], r[2]] for r in lcd_rows[:23]],
            [62 * mm, 58 * mm, 42 * mm],
        )

        st += H2('Sechs echte Referenzläufe (live beim PDF-Bau gerechnet)', '3.1')
        bench_rows = [
            ['1. Werkstattschild', 'RECT 68×28 · CAPS · Loch L Ø5 · Border=2',
             i_rect['file'], '%.1f × %.1f mm · 6 L' % (i_rect['w'], i_rect['h']),
             '1× M600 + Ironing + Tower'],
            ['2. Schlüsselanhänger', 'ROUND R=5 · 2 Zeilen · Außenöse Ø6',
             i_round['file'], '%.1f × %.1f mm · 6 L' % (i_round['w'], i_round['h']),
             'Außenöse bündig ab Layer 1'],
            ['3. Kräuterschild Oval', 'OVAL 74×34 · SCRIPT · Color2=ON',
             i_oval['file'], '%.1f × %.1f mm · 6 L' % (i_oval['w'], i_oval['h']),
             'R183-Kollisionsschutz aktiv'],
            ['4. Schaltschrank-Inlay', 'RECT 64×26 · PLATE · Flip=ON',
             i_flip['file'], '%.1f × %.1f mm · 6 L' % (i_flip['w'], i_flip['h']),
             'Planebene PEI-Sichtseite'],
            ['5. Prüfstempel + Griff', 'CAPS 54×24 · Stamp=ON · Handle=1',
             i_stamp['file'], 'Stempel + Griff auf 1 Platte',
             '0× M600 · _StampFit168'],
            ['6. 9er-Schrankserie', '9× 95×42 mm · COND · FIXED',
             '%d Platten (%s..)' % (i_multi.get('parts', 1), i_multi['files'][0]),
             'R170 Auto-Split (_T1.._T%d)' % i_multi.get('parts', 1),
             'Jede Teilplatte mit Tower!'],
        ]
        st += TBL(
            ['Szenario', 'Parameter', 'Erzeugte Datei(en)', 'Plattenmaß', 'Besonderheit'],
            bench_rows,
            [29 * mm, 40 * mm, 36 * mm, 28 * mm, 29 * mm],
        )

        st += SP(2)
        st += [BOX(
            'Blind-Praxistipp: Vorab-Schriftgrößenprüfung ohne Druckstart',
            [
                '• Über Labels > Info bzw. LABEL_FIT_CALC berechnet der Drucker schon vor dem Generieren '
                'exakt die resultierende Buchstabenhöhe in Millimetern und zeigt sie im Display an.',
                '• Für winzige Beschriftungen unter 4 mm Versalhöhe immer COND, NARROW oder CAPS wählen — '
                'diese drei Schriften wurden speziell für maximale Innenpunzen mit 0,4-mm-Düsen entworfen.',
            ],
            kind='tip',
        )]

        doc.render()
    return out_pdf


if __name__ == '__main__':
    dst = os.path.join(REPO, 'LABELS.pdf')
    build_pdf(dst)
    print('Wrote %s (%d bytes)' % (dst, os.path.getsize(dst)))
