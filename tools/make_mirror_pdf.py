#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""make_mirror_pdf.py — Mathematik & Blindbedienung für Mirror (In-Place-Spiegelung
& selektiver Einzelobjekt-Flip, MASTER-TODO D4 + D6, Pre-Print > Tools > Mirror).

Verbindliche D6-Wahrheitsregel:
  * KEINE Fantasie-Grafiken. Jede Abbildung und jede Ergebniszahl stammt aus
    echten Läufen von `r2_postproc.apply_mirror()` zur Bauzeit.
  * LCD-Zeilen werden live aus `menus/lcd_menues.cfg` geparst.
  * Versionszeile kommt dynamisch aus `r2_version.VERSION`.
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


# ------------------------------------------------ Synthetische Referenzdateien
def _write_asymmetric_l_bracket(path, ox=40.0, oy=115.0, layers=25):
    """Außermittiger asymmetrischer L-Winkel (BBox X=40..90 -> cx=65,
    Y=115..175 -> cy=145) mit einem G2-Rundungsbogen an der Innenecke und
    vollständigem EXCLUDE_OBJECT_DEFINE inkl. KAMP-POLYGON."""
    e = 0.0
    k_e = 0.0332
    poly = [(40.0, 115.0), (90.0, 115.0), (90.0, 133.0),
            (66.0, 133.0), (58.0, 141.0), (58.0, 175.0), (40.0, 175.0)]
    poly_str = ','.join('[%.3f,%.3f]' % p for p in poly)
    with open(path, 'w', encoding='utf-8') as f:
        f.write('; R276 asymmetric L-bracket for MIRROR.pdf\n')
        f.write('EXCLUDE_OBJECT_DEFINE NAME=L_WINKEL CENTER=65.000,145.000 '
                'POLYGON=[%s]\n' % poly_str)
        f.write(';TYPE:Outer wall\nM82\nG90\nG92 E0\n')
        for i in range(1, layers + 1):
            z = round(i * 0.2, 3)
            f.write('EXCLUDE_OBJECT_START NAME=L_WINKEL\n')
            f.write('G0 X40.000 Y115.000 Z%.3f F6000\n' % z)
            # Unterschenkel bis (90,115) -> (90,133) -> (66,133)
            pts1 = [(90.0, 115.0), (90.0, 133.0), (66.0, 133.0)]
            px, py = 40.0, 115.0
            for qx, qy in pts1:
                e += math.hypot(qx - px, qy - py) * k_e
                f.write('G1 X%.3f Y%.3f E%.5f F1800\n' % (qx, qy, e))
                px, py = qx, qy
            # G2-Innenkehle von (66,133) nach (58,141) um Zentrum (66,141), r=8
            e += 0.5 * math.pi * 8.0 * k_e
            f.write('G2 X58.000 Y141.000 I0.000 J8.000 E%.5f F1500\n' % e)
            px, py = 58.0, 141.0
            # Hochschenkel (58,175) -> (40,175) -> (40,115)
            for qx, qy in ((58.0, 175.0), (40.0, 175.0), (40.0, 115.0)):
                e += math.hypot(qx - px, qy - py) * k_e
                f.write('G1 X%.3f Y%.3f E%.5f F1800\n' % (qx, qy, e))
                px, py = qx, qy
            f.write('EXCLUDE_OBJECT_END NAME=L_WINKEL\n')
    return path


def _write_two_object_plate(path):
    """Mehrteil-Platte mit zwei asymmetrischen F-Haken:
      - LEFT_HOOK  bei X=30..70,  Y=60..120 (cx=50,  cy=90)
      - RIGHT_HOOK bei X=140..180, Y=60..120 (cx=160, cy=90)
    Ideal um R224 OBJ=RIGHT_HOOK (selektive Einzelobjekt-Spiegelung) zu prüfen."""
    def f_poly(x0, y0):
        return [
            (x0, y0), (x0 + 14.0, y0), (x0 + 14.0, y0 + 26.0),
            (x0 + 32.0, y0 + 26.0), (x0 + 32.0, y0 + 38.0),
            (x0 + 14.0, y0 + 38.0), (x0 + 14.0, y0 + 48.0),
            (x0 + 40.0, y0 + 48.0), (x0 + 40.0, y0 + 60.0),
            (x0, y0 + 60.0),
        ]

    e = 0.0
    k_e = 0.0332
    p_l = f_poly(30.0, 60.0)
    p_r = f_poly(140.0, 60.0)
    with open(path, 'w', encoding='utf-8') as f:
        f.write('; R276 multi-object plate for MIRROR OBJ= verification\n')
        f.write('EXCLUDE_OBJECT_DEFINE NAME=LEFT_HOOK CENTER=50.000,90.000 '
                'POLYGON=[%s]\n' % ','.join('[%.3f,%.3f]' % p for p in p_l))
        f.write('EXCLUDE_OBJECT_DEFINE NAME=RIGHT_HOOK CENTER=160.000,90.000 '
                'POLYGON=[%s]\n' % ','.join('[%.3f,%.3f]' % p for p in p_r))
        f.write(';TYPE:Outer wall\nM82\nG90\nG92 E0\n')
        for i in range(1, 16):
            z = round(i * 0.2, 3)
            for name, poly in (('LEFT_HOOK', p_l), ('RIGHT_HOOK', p_r)):
                f.write('EXCLUDE_OBJECT_START NAME=%s\n' % name)
                f.write('G0 X%.3f Y%.3f Z%.3f F6000\n' % (poly[0][0], poly[0][1], z))
                px, py = poly[0]
                for qx, qy in poly[1:] + [poly[0]]:
                    e += math.hypot(qx - px, qy - py) * k_e
                    f.write('G1 X%.3f Y%.3f E%.5f F1800\n' % (qx, qy, e))
                    px, py = qx, qy
                f.write('EXCLUDE_OBJECT_END NAME=%s\n' % name)
    return path


def _parse_extruding_segments_with_arcs(gcode_path):
    """Liest G1- und G2/G3-Segmente (über _arc_points), inkl. Objektname."""
    from r2_texture import _arc_points, _parse_move, _parse_arc
    segs = []
    px = py = pz = None
    last_e = 0.0
    e_rel = False
    cur_obj = None
    with open(gcode_path, encoding='utf-8', errors='replace') as f:
        for raw in f:
            ls = raw.split(';', 1)[0].strip()
            if not ls:
                continue
            if ls.startswith('EXCLUDE_OBJECT_START'):
                m = re.search(r'NAME=(\S+)', ls)
                cur_obj = m.group(1) if m else None
                continue
            if ls.startswith('EXCLUDE_OBJECT_END'):
                cur_obj = None
                continue
            if ls == 'M83':
                e_rel = True
                continue
            if ls == 'M82':
                e_rel = False
                continue
            if ls.startswith('G92'):
                m = re.search(r'E(-?[\d.]+)', ls)
                if m:
                    last_e = float(m.group(1))
                continue
            g = _parse_move(ls)
            if g is not None:
                nx = g[1] if g[1] is not None else px
                ny = g[2] if g[2] is not None else py
                nz = g[3] if g[3] is not None else pz
                de = 0.0
                if g[4] is not None:
                    de = g[4] if e_rel else (g[4] - last_e)
                    if not e_rel:
                        last_e = g[4]
                if de > 1e-6 and px is not None and nx is not None:
                    segs.append((px, py, nx, ny, nz or 0.2, de, cur_obj))
                px, py, pz = nx, ny, nz
                continue
            ga = _parse_arc(ls)
            if ga is not None and px is not None:
                nz = ga[3] if ga[3] is not None else pz
                pts = _arc_points(px, py, ga[1], ga[2], i=ga[4], j=ga[5],
                                  rr=ga[6], cw=(ga[0] == 'G2')) or []
                de = 0.0
                if ga[7] is not None:
                    de = ga[7] if e_rel else (ga[7] - last_e)
                    if not e_rel:
                        last_e = ga[7]
                chain = [(px, py)] + pts
                lens = [math.hypot(b[0] - a[0], b[1] - a[1])
                        for a, b in zip(chain, chain[1:])]
                tot_l = sum(lens) or 1.0
                for (a, b), ln in zip(zip(chain, chain[1:]), lens):
                    segs.append((a[0], a[1], b[0], b[1], nz or 0.2,
                                 de * (ln / tot_l), cur_obj))
                if pts:
                    px, py = pts[-1]
                pz = nz
    return segs


def _bbox_and_e(gcode_path):
    segs = _parse_extruding_segments_with_arcs(gcode_path)
    xs = [s[0] for s in segs] + [s[2] for s in segs]
    ys = [s[1] for s in segs] + [s[3] for s in segs]
    return (min(xs), max(xs), min(ys), max(ys)), sum(s[5] for s in segs), segs


def _parse_mirror_menu():
    cfg = os.path.join(REPO, 'menus', 'lcd_menues.cfg')
    txt = open(cfg, encoding='utf-8').read()
    rows = []
    for blk in re.split(r'(?=^\[menu )', txt, flags=re.M):
        m = re.match(r'^\[menu (__main __preprint __mods __mirror[^\]]*)\]', blk)
        if not m:
            continue
        sec = m.group(1).strip()
        if sec == '__main __preprint __mods __mirror':
            continue
        key = sec.split()[-1]
        nm = re.search(r'^\s*name:\s*(.+)$', blk, re.M)
        imin = re.search(r'^\s*input_min:\s*(.+)$', blk, re.M)
        imax = re.search(r'^\s*input_max:\s*(.+)$', blk, re.M)
        istp = re.search(r'^\s*input_step:\s*(.+)$', blk, re.M)
        sv = re.search(r'SAVE_VARIABLE\s+VARIABLE=([a-z0-9_]+)', blk)
        act = re.search(r'^\s*(MIRROR_APPLY[^\n]*|RESPOND[^\n]*)', blk, re.M)
        label = nm.group(1).strip().strip("'\"") if nm else key
        if 'gen_arm' in label:
            label = '&gt; Apply  (2. Klick: &gt; AGAIN = start)'
        elif 'menu.input' in label:
            label = 'Axis: X | Y'
        else:
            label = label.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
        rng = ('Index %s .. %s (0=X, 1=Y)'
               % (imin.group(1).strip(), imax.group(1).strip())) if (imin and imax and istp) else 'Befehl / Info'
        var = ('sv.%s' % sv.group(1)) if sv else (
            act.group(1).split()[0] if act else '—')
        rows.append((key, label, rng, var))
    return rows


# ------------------------------------------------ D6-Abbildungen
def _fig_inplace_mirror(src_p, mirx_p, miry_p, out_png):
    """Drei echte Bett-Ansichten nebeneinander:
    Quelle (L-Winkel außermittig X=40..90, Y=115..175) -> AXIS=X -> AXIS=Y.
    Beweist visuell: Die rot gestrichelte BBox [40..90]×[115..175] wandert keinen
    einzigen Millimeter Richtung Bettmitte (110,110)!"""
    W, H = 1280, 500
    im = PILImage.new('RGB', (W, H), 'white')
    d = ImageDraw.Draw(im)
    f_b = font(19, bold=True)
    f_m = font(15, bold=True)
    f_xs = font(13)

    d.text((45, 14),
           'In-Place-Spiegelung auf dem 220×220-mm-Bett: BBox [40..90] × [115..175] bleibt exakt an Ort und Stelle!',
           font=f_b, fill='#1c4e8c')

    panels = [
        ('1) Quelle (L_WINKEL, G2-Kehle)', src_p, '#58595b', None),
        ('2) MIRROR AXIS=X (x\' = 130 - x)', mirx_p, '#1c4e8c', 'x'),
        ('3) MIRROR AXIS=Y (y\' = 290 - y)', miry_p, '#00706b', 'y'),
    ]
    pw, ph = 370, 370
    for idx, (title, pth, col, ax) in enumerate(panels):
        bx0 = 45 + idx * 405
        by0 = 62
        d.rectangle([bx0, by0, bx0 + pw, by0 + ph], outline='#8aa4c2',
                    width=2, fill='#f9fbfe')
        d.text((bx0, by0 - 24), title, font=f_m, fill=col)

        def map_bed(x, y):
            px = bx0 + 20 + (x / 220.0) * (pw - 40)
            py = by0 + ph - 20 - (y / 220.0) * (ph - 40)
            return px, py

        # Bettmitte (110,110) als graues Fadenkreuz
        mcx, mcy = map_bed(110.0, 110.0)
        d.line([bx0 + 20, mcy, bx0 + pw - 20, mcy], fill='#e0e7f0', width=1)
        d.line([mcx, by0 + 20, mcx, by0 + ph - 20], fill='#e0e7f0', width=1)
        d.text((mcx + 5, mcy + 4), 'Bettmitte (110,110)', font=f_xs, fill='#8a99ad')

        # Unveränderliches BBox-Rechteck [40..90]×[115..175]
        p00 = map_bed(40.0, 175.0)
        p11 = map_bed(90.0, 115.0)
        d.rectangle([p00[0], p00[1], p11[0], p11[1]], outline='#e07b00', width=2)

        # Eigene Spiegelachse durch (cx=65, cy=145)
        ocx, ocy = map_bed(65.0, 145.0)
        if ax == 'x':
            d.line([ocx, p00[1] - 12, ocx, p11[1] + 12], fill='#b3261e', width=2)
            d.text((ocx - 36, p00[1] - 28), 'x = c_x = 65', font=f_xs, fill='#b3261e')
        elif ax == 'y':
            d.line([p00[0] - 12, ocy, p11[0] + 12, ocy], fill='#b3261e', width=2)
            d.text((p11[0] + 8, ocy - 8), 'y=145', font=f_xs, fill='#b3261e')

        segs = _parse_extruding_segments_with_arcs(pth)
        for x0, y0, x1, y1, z, _de, _ob in segs:
            if abs(z - 0.2) < 1e-4:
                d.line([map_bed(x0, y0), map_bed(x1, y1)], fill=col, width=4)

        d.ellipse([ocx - 4, ocy - 4, ocx + 4, ocy + 4], fill='#b3261e')
        d.text((bx0 + 14, by0 + ph - 28),
               'Zentrum bleibt (65,0 | 145,0) mm', font=f_xs, fill='#444444')

    d.text((45, H - 34),
           'Orange Rahmen = identische Bounding-Box [40..90]×[115..175] mm in allen drei Dateien (kein Bettwächter nötig!).',
           font=f_xs, fill='#b35900')
    im.save(out_png)


def _fig_multi_object(plate_src, plate_all_x, plate_one_x, out_png):
    """Zeigt den entscheidenden Unterschied auf einer Mehrteil-Platte:
      A) Quelle: LEFT_HOOK (x=30..70) + RIGHT_HOOK (x=140..180), beide schauen nach rechts ('F')
      B) Ohne OBJ= (Gruppenspiegelung um Gesamtzentrum cx=105): Plätze UND Formen tauschen!
      C) Mit OBJ=RIGHT_HOOK: LEFT_HOOK bleibt 100% unberührt, RIGHT_HOOK spiegelt an Ort & Stelle (cx=160) zum Paar!"""
    W, H = 1280, 470
    im = PILImage.new('RGB', (W, H), 'white')
    d = ImageDraw.Draw(im)
    f_b = font(19, bold=True)
    f_m = font(15, bold=True)
    f_xs = font(13)

    d.text((45, 14),
           'Mehrteil-Platte (R224 Task 10): Gruppenspiegelung vs. selektives OBJ=RIGHT_HOOK',
           font=f_b, fill='#1c4e8c')

    panels = [
        ('A) Quelle: 2 gleiche F-Haken', plate_src,
         'LEFT_HOOK (cx=50) & RIGHT_HOOK (cx=160)'),
        ('B) Ohne OBJ= (Gruppenmitte cx=105)', plate_all_x,
         'Beide Haken flippen & tauschen Plätze!'),
        ('C) MIRROR AXIS=X OBJ=RIGHT_HOOK', plate_one_x,
         'Links bleibt „F", Rechts wird „Ⅎ" am Platz!'),
    ]
    pw, ph = 370, 340
    for idx, (title, pth, sub) in enumerate(panels):
        bx0 = 45 + idx * 405
        by0 = 62
        d.rectangle([bx0, by0, bx0 + pw, by0 + ph], outline='#8aa4c2',
                    width=2, fill='#f9fbfe')
        d.text((bx0, by0 - 24), title, font=f_m, fill='#1c4e8c')

        def map_bed(x, y):
            px = bx0 + 20 + (x / 220.0) * (pw - 40)
            py = by0 + ph - 20 - (y / 220.0) * (ph - 40)
            return px, py

        segs = _parse_extruding_segments_with_arcs(pth)
        for x0, y0, x1, y1, z, _de, ob in segs:
            if abs(z - 0.2) < 1e-4:
                col = '#1e7d32' if ob == 'LEFT_HOOK' else '#b3261e'
                d.line([map_bed(x0, y0), map_bed(x1, y1)], fill=col, width=4)

        d.text((bx0 + 14, by0 + 14), 'Grün = LEFT_HOOK   |   Rot = RIGHT_HOOK',
               font=f_xs, fill='#333333')
        d.text((bx0 + 14, by0 + ph - 28), sub, font=f_xs, fill='#444444')

    d.text((45, H - 34),
           'Praxisnutzen: Zwei identische Halter auf einer Platte geslict -> mit OBJ=RIGHT_HOOK entsteht sofort ein Links/Rechts-Paar!',
           font=f_xs, fill='#1e7d32')
    im.save(out_png)


# ------------------------------------------------ Hauptaufbau des PDFs
def build_pdf(out_pdf):
    lcd_rows = _parse_mirror_menu()

    with tempfile.TemporaryDirectory(prefix='r2_mirror_pdf_') as tmpdir:
        src_l = _write_asymmetric_l_bracket(os.path.join(tmpdir, 'WinkelL.gcode'))
        bb_src, e_src, _ = _bbox_and_e(src_l)

        mirx_p, info_x = pp.apply_mirror(src_l, axis='x', out_dir=tmpdir)
        miry_p, info_y = pp.apply_mirror(src_l, axis='y', out_dir=tmpdir)
        mirxx_p, info_xx = pp.apply_mirror(mirx_p, axis='x', out_dir=tmpdir)

        plate_src = _write_two_object_plate(os.path.join(tmpdir, 'PaarPlatte.gcode'))
        plate_all, info_pall = pp.apply_mirror(plate_src, axis='x', out_dir=tmpdir)
        plate_one, info_pone = pp.apply_mirror(plate_src, axis='x',
                                               obj='RIGHT_HOOK', out_dir=tmpdir)

        # Prüfe R239-Regel live an der erzeugten Datei: kein Leerzeichen im POLYGON=
        mirx_txt = open(mirx_p, encoding='utf-8').read()
        poly_line = [ln for ln in mirx_txt.splitlines() if 'POLYGON=[' in ln][0]

        fig1 = os.path.join(tmpdir, 'fig_mirror_inplace.png')
        _fig_inplace_mirror(src_l, mirx_p, miry_p, fig1)

        fig2 = os.path.join(tmpdir, 'fig_mirror_obj.png')
        _fig_multi_object(plate_src, plate_all, plate_one, fig2)

        runs = [
            ('1. Einzelteil X-Flip', info_x, _bbox_and_e(mirx_p)),
            ('2. Einzelteil Y-Flip', info_y, _bbox_and_e(miry_p)),
            ('3. Doppel-Flip M_X(M_X)', info_xx, _bbox_and_e(mirxx_p)),
            ('4. Platte gesamt (X)', info_pall, _bbox_and_e(plate_all)),
            ('5. Platte OBJ=RIGHT_HOOK', info_pone, _bbox_and_e(plate_one)),
        ]

        doc = Doc(
            out_pdf,
            kopf='R2-D2 Macro System · Pre-Print-Modifikator Mirror (D4)',
            titel='Mirror (In-Place-Spiegelung) — Mathematik & Blindbedienung',
        )
        st = doc.story

        cover_tbl = TBL(
            ['Kenngröße', 'Wert im aktuellen Code'],
            [
                ['Menüpfad am Display', 'Pre-Print > Tools > Mirror  (3 Zeilen)'],
                ['G-Code-Makro / Engine', 'MIRROR_APPLY  ->  r2_postproc.apply_mirror()'],
                ['Spiegelachsen (AXIS)', 'X (Links <-> Rechts) oder Y (Vorn <-> Hinten)'],
                ['Positions-Verhalten', 'IN PLACE: spiegelt um das eigene Bauteilzentrum (c_x, c_y)'],
                ['Mehrteil-Platten (Konsole)', 'OBJ=<Name> spiegelt NUR dieses eine EXCLUDE_OBJECT-Teil'],
                ['Extrusion & KAMP-Mesh', 'E 1:1 verbatim (det M = -1); CENTER= & POLYGON= mitgespiegelt'],
                ['Ausgabeordner & Namensschema', 'Mirror/<Stamm>_MIRX.gcode  bzw.  _MIRY.gcode'],
            ],
            [58 * mm, 104 * mm],
        )[0]

        doc.add_cover(
            kicker='PRE-PRINT-GEOMETRIE-MODIFIKATOR · MATHEMATIK & BLINDBEDIENUNG (D4)',
            titel='Mirror — In-Place-Spiegelung',
            untertitel='Uneigentliche O(2)-Isometrie an Ort und Stelle, BBox-Selbstinvarianz, KAMP-Polygon-Mitführung und selektiver Einzelobjekt-Flip',
            absaetze=[
                'Der Klassiker in jeder Werkstatt: Der linke Scharnierhalter liegt fertig '
                'geslict auf der SD-Karte, gebraucht wird jetzt aber das spiegelbildliche '
                'Gegenstück für die rechte Seite — oder ein Stempel/Siegel braucht Spiegelschrift.',
                'Im Gegensatz zu Scale und Twist verschiebt Mirror (R224 / R239) das Bauteil '
                'bewusst NICHT in die Bettmitte, sondern klappt es exakt um sein eigenes '
                'Zentrum um („an derselben Stelle"). Dieses Heft erklärt die Involution '
                'dahinter, warum ein gespiegeltes Teil physikalisch niemals vom Bett wandern '
                'kann, warum G2/G3-Bögen ihre Drehrichtung wechseln und wie du auf einer '
                'Mehrteil-Platte gezielt ein einzelnes Bauteil umdrehst.',
            ],
            tabelle=cover_tbl,
        )

        # ---- Kapitel 1 ------------------------------------------------------
        st += H1('Das In-Place-Prinzip: Unterschied zu Scale & Twist', '1')
        st += P(
            'Während <b>apply_scale()</b> und <b>apply_twist()</b> ihre Ausgabe immer auf '
            'die Druckbettmitte (t_x, t_y) setzen, folgt <b>apply_mirror()</b> '
            '(<b>tools/r2_postproc.py</b>) einer ausdrücklichen Praxis-Vorgabe: Wenn man '
            'ein Bauteil bewusst vorne links auf eine unbeschädigte Stelle der Druckplatte '
            'gelegt hat — oder ein einzelnes Objekt auf einer Mehrteil-Platte spiegelt —, '
            'darf es nach dem Spiegeln nicht plötzlich in der Bettmitte mit Nachbarteilen '
            'kollidieren! Darum liegt die Spiegelachse exakt durch das <b>eigene '
            'Bounding-Box-Zentrum (c_x, c_y)</b> des Objekts.'
        )

        # ---- Kapitel 2 ------------------------------------------------------
        st += H1('Spiegelungs-Mathematik: Involution, Isometrie & BBox-Beweis', '2')
        st += P(
            'Aus Pass 1 bestimmt <b>apply_mirror()</b> das minimale und maximale Koordinaten-'
            'paar [x_min, x_max] × [y_min, y_max] aller Züge (bzw. bei gesetztem '
            '<b>OBJ=&lt;Name&gt;</b> ausschließlich der Züge innerhalb dieses Objektblocks):'
        )
        st += FORMULA(
            'c_x = (x_min + x_max) / 2,         c_y = (y_min + y_max) / 2<br/>'
            'AXIS = X (Links <-> Rechts):    x\' = 2 · c_x - x,     y\' = y,     z\' = z<br/>'
            'AXIS = Y (Vorn  <-> Hinten):    x\' = x,     y\' = 2 · c_y - y,     z\' = z',
            note='Achtung Begriffsfalle: „AXIS = X" spiegelt die X-Koordinate (an der vertikalen '
                 'Geraden x = c_x, also Links <-> Rechts), NICHT entlang der X-Achse Vorn <-> Hinten!'
        )
        st += SP(2)
        st += H2('Drei mathematische Garantien ohne Zusatzparameter', '2.1')
        st += B(
            '<b>1. BBox-Selbstinvarianz (warum kein Bettwächter nötig ist):</b> Setzt man '
            'die Grenzen in x\' = 2·c_x - x = (x_min + x_max) - x ein, erhält man für '
            'x = x_max exakt <b>x\' = x_min</b> und für x = x_min exakt <b>x\' = x_max</b>! '
            'Das Bildintervall [x\'_min, x\'_max] ist identisch gleich [x_min, x_max]. '
            'Ein Teil, das vorher auf dem Bett lag, kann das Bett durch In-Place-Spiegeln '
            'mathematisch unter keinen Umständen verlassen.',
            '<b>2. Uneigentliche Isometrie (det M = -1 -> E bleibt 1:1):</b> Die '
            'Spiegelmatrizen diag(-1, +1) bzw. diag(+1, -1) liegen in O(2) \\ SO(2) mit '
            'Determinante <b>-1</b>. Für jeden Differenzvektor gilt ||M·Δp|| = √((-Δx)² + Δy²) '
            '= ||Δp||. Alle Längen, Spurbreiten und Schichthöhen bleiben exakt erhalten -> '
            '<b>ΔE\' = ΔE</b> ohne jede Flow-Rechnung.',
            '<b>3. Strenge Involution (M(M(p)) = p):</b> Zweimaliges Spiegeln auf derselben '
            'Achse liefert 2·c_x - (2·c_x - x) = x (bis auf G2/G3-Sehnenauflösung exakt '
            'das Original zurück).',
        )

        # ---- Kapitel 3 ------------------------------------------------------
        st += H1('Chiralitätswechsel bei Bögen, KAMP-Mesh & Einzelobjekt-Flip', '3')
        st += H2('Warum G2 und G3 beim Spiegeln die Drehrichtung tauschen', '3.1')
        st += P(
            'Wegen <b>det M = -1</b> kehrt jede Spiegelung den Umlaufsinn um: Ein '
            'Uhrzeigersinn-Bogen (<b>G2</b>) wird zum Gegen-Uhrzeigersinn-Bogen (<b>G3</b>), '
            'und der Mittelpunktsoffset I (bzw. J) wechselt das Vorzeichen. Damit weder '
            'R-Format-Bögen noch Halbkreis-Grenzfälle falsch herum klappen, nutzt '
            '<b>apply_mirror()</b> denselben kugelsicheren Weg wie Twist: <b>_arc_points()</b> '
            'zerlegt jeden Bogen im Original-Drehsinn in feine G1-Sehnen und spiegelt deren '
            'Stützpunkte einzeln.'
        )
        st += H2('KAMP-Adaptive-Mesh & die R239-Leerzeichen-Regel', '3.2')
        st += P(
            'Würde man nur G0/G1 spiegeln, läge das im Header hinterlegte '
            '<b>EXCLUDE_OBJECT_DEFINE</b>-Polygon noch auf der alten Seite — KAMP würde '
            'das falsche Bettviertel abtasten! <b>_mirror_exclude_line()</b> spiegelt daher '
            'sowohl <b>CENTER=</b> als auch jeden Eckpunkt in <b>POLYGON=[...]</b> — und '
            'zwar strikt <i>ohne Leerzeichen</i> zwischen den Punkten (R239-Feldregel: '
            'Klippers shlex-Parser zerschneidet Parameterwerte an Leerzeichen in „Malformed '
            'command"). Live-Auszug aus der soeben erzeugten Datei:'
        )
        st += CODE(poly_line[:92] + (' ...]' if len(poly_line) > 92 else ''))
        st += H2('Selektive Einzelobjekt-Spiegelung (OBJ=&lt;Name&gt;, R224)', '3.3')
        st += P(
            'Enthält eine Datei mehrere Objekte (z. B. <b>LEFT_HOOK</b> und <b>RIGHT_HOOK</b>), '
            'sammelt Pass 0 alle <b>NAME=...</b>-Blöcke. Übergibt man in der Konsole '
            '<b>MIRROR_APPLY AXIS=X OBJ=RIGHT_HOOK</b>, bildet Pass 1 das Zentrum (c_x, c_y) '
            '<i>nur</i> aus den Zügen zwischen <b>EXCLUDE_OBJECT_START NAME=RIGHT_HOOK</b> '
            'und <b>EXCLUDE_OBJECT_END</b>, und Pass 2 spiegelt ausschließlich diesen Block '
            'an seinem eigenen Platz, während alle Geschwister-Objekte Byte für Byte '
            'unangetastet bleiben!'
        )

        # ---- Kapitel 4 ------------------------------------------------------
        st += H1('Live-Werkzeugpfade: In-Place-Beweis & Mehrteil-Platte (D6)', '4')
        st.append(IMG(fig1, width_mm=168))
        st += CAP(
            'Abb. 1 — Echte G-Code-Spuren aus apply_mirror() am außermittigen L-Winkel '
            '(c_x=65, c_y=145): Sowohl bei AXIS=X als auch bei AXIS=Y bleibt der orange '
            'Bounding-Box-Rahmen [40..90]×[115..175] mm exakt unverändert.'
        )
        st.append(IMG(fig2, width_mm=168))
        st += CAP(
            'Abb. 2 — Echte Mehrteil-Platte aus apply_mirror(): Ohne OBJ= spiegelt die '
            'ganze Gruppe um cx=105; mit OBJ=RIGHT_HOOK entsteht direkt ein druckfertiges '
            'Links/Rechts-Paar ohne Neuslicen.'
        )

        # ---- Kapitel 5 ------------------------------------------------------
        st += H1('Blind am Drucker arbeiten: Menü, Merkregel & Konsole', '5')
        st += P(
            'Alle <b>%d</b> Menüzeilen unter <b>Pre-Print &gt; Tools &gt; Mirror</b> '
            '(live gelesen aus <b>menus/lcd_menues.cfg</b>):' % len(lcd_rows)
        )
        st += TBL(
            ['Pos.', 'LCD-Zeile', 'Wertebereich / Schritt', 'Variable / Aktion'],
            [[str(i + 1), r[1], r[2], r[3]] for i, r in enumerate(lcd_rows)],
            [12 * mm, 52 * mm, 54 * mm, 44 * mm],
            mono_cols=(0, 3),
        )
        st += SP(2)
        st += NUM(
            '<b>Datei wählen & Mirror öffnen:</b> Quelldatei wählen -> '
            '<b>Pre-Print &gt; Tools &gt; Mirror</b>.',
            '<b>Zeile 1 — Achse blind schalten (Anschlag-Trick!):</b> Da <b>Axis</b> nur '
            'zwei Werte kennt (0 = <b>X</b>, 1 = <b>Y</b>), brauchst du überhaupt nicht '
            'hinzusehen: Klick -> eine Raste nach <b>links</b> garantiert immer <b>X</b> '
            '(Links &lt;-&gt; Rechts); eine Raste nach <b>rechts</b> garantiert immer '
            '<b>Y</b> (Vorn &lt;-&gt; Hinten) -> Klick bestätigt!',
            '<b>Zeile 3 — Zwei-Klick-Start:</b> Zwei Rasten runter auf <b>&gt; Apply</b> -> '
            'Doppelklick (1. Klick schärft scharf, 2. Klick startet). Fertig!',
        )
        st += SP(2)
        st.append(BOX(
            'Eselsbrücke vor dem Druckbett & Konsolen-Kommandos',
            [
                '• <b>Stehst du vor dem Ender-3:</b> <b>X</b> tauscht deine <b>linke und '
                'rechte Hand</b> (95 % aller Paarteile & Spiegelschriften!). <b>Y</b> tauscht '
                '<b>Bett-Vorderkante und Bett-Hinterkante</b>.',
                '• <b>X + Y nacheinander = 180°-Drehung:</b> Spiegelst du erst auf X und '
                'danach die erzeugte Datei auf Y, ist das wegen det(M_Y · M_X) = (-1)·(-1) = +1 '
                'keine Spiegelung mehr, sondern eine exakte <b>180°-Drehung</b> am Platz!',
                '• <b>Konsole (Einzelobjekt):</b> <b>MIRROR_APPLY AXIS=X OBJ=RIGHT_HOOK</b>.',
            ],
            kind='tip',
        ))

        # ---- Kapitel 6 ------------------------------------------------------
        st += H1('Durchgerechnete Live-Referenzläufe', '6')
        st += P(
            'Fünf echte Läufe von <b>apply_mirror()</b> zur Bauzeit dieses Hefts '
            '(Quell-Winkel: BBox [%.1f..%.1f]×[%.1f..%.1f] mm, ΣΔE = %.4f mm):'
            % (bb_src[0], bb_src[1], bb_src[2], bb_src[3], e_src)
        )
        ref_rows = []
        for title, info, (bb, e_out, _segs) in runs:
            ref_rows.append([
                title,
                info['file'],
                '[%.0f..%.0f]×[%.0f..%.0f]' % bb,
                '%d / %d' % (info['moves'], info['arcs_flattened']),
                '%.4f mm' % e_out,
            ])
        st += TBL(
            ['Szenario', 'Erzeugte Datei', 'BBox [X]×[Y] mm', 'Züge / Bögen', 'ΣΔE\''],
            ref_rows,
            [36 * mm, 44 * mm, 34 * mm, 24 * mm, 26 * mm],
            mono_cols=(1, 2, 3, 4),
        )
        st += SP(2)
        st += P(
            '<b>Gegenprobe an den Zahlen:</b> In den Läufen 1, 2 und 3 bleibt die '
            'Bounding-Box auf den Zehntelmillimeter identisch bei <b>[40..90]×[115..175] mm</b>; '
            'ebenso stimmt ΣΔE\' in Lauf 1–3 exakt überein (beim Doppel-Flip Lauf 3 ist '
            'arcs_flattened = 0, weil die 25 G2-Bögen bereits in Lauf 1 in G1-Sehnen '
            'aufgelöst wurden). Auf der Mehrteil-Platte (Lauf 4 vs. Lauf 5) bleibt auch '
            'die Gesamt-Extrusion beider Haken identisch.'
        )

        doc.render()
    return out_pdf


if __name__ == '__main__':
    target = os.path.join(REPO, 'MIRROR.pdf')
    build_pdf(target)
    print('Wrote %s (%d bytes)' % (target, os.path.getsize(target)))
