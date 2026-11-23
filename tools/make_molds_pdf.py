#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""make_molds_pdf.py — wissenschaftliche Methodik- & Parameter-PDF für den
Gießformen-Generator (MASTER-TODO D3 + D6, R270–R273 / J2).

Vorbild: CUTSPLIT.pdf & TEXTURING.pdf, gebaut auf tools/r2_pdf_kit.py.
Verbindliche D6-Wahrheitsregel:
  * KEINE Fantasie-Grafiken. Jede Abbildung und jede Ergebniszahl in diesem
    Heft stammt aus echten Läufen von `r2_postproc.make_mold()` und
    `r2_postproc.make_mold_blank()` zur Bauzeit (in einem temporären Ordner).
  * LCD-Zeilen werden direkt aus `menus/lcd_menues.cfg` gelesen.
  * Versionskopf kommt dynamisch aus `r2_version.VERSION`.
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
    Doc, H1, H2, P, B, NUM, CODE, CAP, SP, TBL, BOX, FORMULA, IMG,
    toolpath_fig, font,
)


# --------------------------------------------------------- Synthetische Körper
def _write_bipyramid_gcode(path, r_foot=11.0, r_eq=18.0, r_top=10.0,
                           z_eq=7.0, height=14.0, layer_h=0.2, n_sides=48):
    """Doppelkegelstumpf (Äquator bei z_eq breiter als Fuß und Kopf) — oder
    gerader Zylinder bei r_foot == r_eq == r_top."""
    cx, cy = 110.0, 110.0
    nl = int(round(height / layer_h))
    e = 0.0
    with open(path, 'w', encoding='utf-8') as f:
        f.write('; R275 reference body\n')
        f.write(';TYPE:Outer wall\nM82\nG90\n')
        for i in range(1, nl + 1):
            z = round(i * layer_h, 3)
            if z <= z_eq:
                t = z / max(layer_h, z_eq)
                r = r_foot + (r_eq - r_foot) * t
            else:
                t = (z - z_eq) / max(layer_h, height - z_eq)
                r = r_eq + (r_top - r_eq) * t
            pts = [(cx + r * math.cos(2.0 * math.pi * k / n_sides),
                    cy + r * math.sin(2.0 * math.pi * k / n_sides))
                   for k in range(n_sides)]
            f.write('G0 X%.3f Y%.3f Z%.3f F6000\n' % (pts[0][0], pts[0][1], z))
            for k in range(1, n_sides + 1):
                px, py = pts[k - 1]
                qx, qy = pts[k % n_sides]
                e += math.hypot(qx - px, qy - py) * 0.033
                f.write('G1 X%.3f Y%.3f E%.4f F1800\n' % (qx, qy, e))
    return path


def _write_t_amboss_gcode(path, lx_stem=24.0, lx_head=40.0, wy=22.0,
                          height=11.0, layer_h=0.2):
    """T-Amboss-Profil (Schaft 24×22 mm unten, Hammerkopf 40×22 mm oben):
    2-teilig unmöglich (8 mm Überhang links/rechts in X), 4-teilig (`sectors=2`)
    ideal: S1/S3 gleiten entlang ±X ab, das Mitteldrittel S2 (13,3 mm <= 24 mm)
    hebt senkrecht ohne Hinterschnitt ab."""
    cx, cy = 110.0, 110.0
    nl = int(round(height / layer_h))
    e = 0.0
    with open(path, 'w', encoding='utf-8') as f:
        f.write('; R275 reference body: T-anvil for 4-part sector mold\n')
        f.write(';TYPE:Outer wall\nM82\nG90\n')
        for i in range(1, nl + 1):
            z = round(i * layer_h, 3)
            if z <= 5.0:
                lx = lx_stem
            elif z <= 7.0:
                lx = lx_stem + (lx_head - lx_stem) * ((z - 5.0) / 2.0)
            else:
                lx = lx_head
            hx, hy = lx / 2.0, wy / 2.0
            pts = [(cx - hx, cy - hy), (cx + hx, cy - hy),
                   (cx + hx, cy + hy), (cx - hx, cy + hy)]
            f.write('G0 X%.3f Y%.3f Z%.3f F6000\n' % (pts[0][0], pts[0][1], z))
            for k in range(1, 5):
                px, py = pts[k - 1]
                qx, qy = pts[k % 4]
                e += math.hypot(qx - px, qy - py) * 0.033
                f.write('G1 X%.3f Y%.3f E%.4f F1800\n' % (qx, qy, e))
    return path


# --------------------------------------------- Echte Figuren aus Engine-Läufen
def _parse_layer_xy_by_type(gcode_path, z_pick=None):
    """Liest echte Extrusionssegmente (x0, y0, x1, y1, ftype, z) aus einer
    erzeugten Formdatei. Wenn z_pick gesetzt ist, nur die nächstliegende Z-Lage."""
    segs = []
    zs = set()
    x = y = z = e = 0.0
    erel = False
    ft = 'OTHER'
    with open(gcode_path, encoding='utf-8', errors='replace') as fh:
        for ln in fh:
            s = ln.strip()
            if s.startswith('APPLY_TYPE TYPE='):
                ft = s.split('TYPE=', 1)[1].split()[0].strip('"\'')
                continue
            if s.startswith(';TYPE:'):
                ft = s.split(':', 1)[1].strip().upper()
                continue
            code = s.split(';', 1)[0].strip()
            if not code:
                continue
            if code.startswith('M83'):
                erel = True
                continue
            if code.startswith('M82'):
                erel = False
                continue
            if code.startswith('G92'):
                for tok in code.split()[1:]:
                    if tok[:1] == 'E':
                        try:
                            e = float(tok[1:])
                        except ValueError:
                            pass
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
            de = 0.0
            if ne is not None:
                de = ne if erel else (ne - e)
                e = (e + ne) if erel else ne
            if de > 1e-6 and (abs(nx - x) + abs(ny - y)) > 1e-6:
                zk = round(nz, 3)
                zs.add(zk)
                segs.append((x, y, nx, ny, ft, zk))
            x, y, z = nx, ny, nz
    if z_pick is not None and zs:
        best_z = min(zs, key=lambda zz: abs(zz - z_pick))
        segs = [sg for sg in segs if abs(sg[5] - best_z) < 1e-4]
        return segs, best_z
    return segs, (max(zs) if zs else 0.0)


def fig_mold_anatomy(bot_gcode, top_gcode, info, out_png):
    """D6-konforme Doppel-Abbildung aus ECHTEM make_mold-Lauf:
    Links: Druckquerschnitt XZ (2,5× Z-Überhöhung zur klaren Darstellung von
    Bodenstärke, Kavitätsflanken, Passlöchern und konischem Trichter).
    Rechts: echter XY-Fahrweg von FormOben nahe der Trennebene."""
    W, H = 1160, 500
    im = PILImage.new('RGB', (W, H), 'white')
    d = ImageDraw.Draw(im)

    # ---- Linkes Panel: XZ-Schnitt beider Druckblöcke (Trennebene OBEN!) ----
    d.text((28, 12), 'A · XZ-Drucklage beider Blöcke (Z 2,5× überhöht)',
           font=font(16, bold=True), fill='#1c4e8c')
    bw, bh = info['block']
    wall = info['wall']
    lh = 0.2
    z_bot_h = info['layers_bot'] * lh
    z_top_h = info['layers_top'] * lh
    z_exag = 2.5

    tot_x = 2.0 * bw + 14.0
    max_z = max(z_bot_h, z_top_h) * z_exag + 6.0
    px0, py0, pw, ph = 28, 48, 530, 392
    sc = min(pw / (tot_x + 8.0), (ph - 52) / max_z)

    def xz(xm, zm):
        return (int(px0 + (xm + 4.0) * sc),
                int(py0 + ph - 52 - zm * z_exag * sc))

    d.rectangle([px0, py0, px0 + pw, py0 + ph], outline='#d4dfec')
    d.line([xz(-2, 0), xz(tot_x + 2, 0)], fill='#58595b', width=3)

    gap = info['gap']
    r_f = 11.0 + gap
    r_e = 18.0 + gap
    r_t = 10.0 + gap
    c1 = bw / 2.0
    b_poly = [xz(0, 0), xz(bw, 0), xz(bw, z_bot_h),
              xz(c1 + r_e, z_bot_h), xz(c1 + r_f, wall),
              xz(c1 - r_f, wall), xz(c1 - r_e, z_bot_h), xz(0, z_bot_h)]
    d.polygon(b_poly, fill='#dce8f8', outline='#1c4e8c')
    d.line([xz(0, z_bot_h), xz(c1 - r_e, z_bot_h)], fill='#1e7d32', width=4)
    d.line([xz(c1 + r_e, z_bot_h), xz(bw, z_bot_h)], fill='#1e7d32', width=4)
    pin_r = info['pin_d'] / 2.0 + 0.3
    pin_off = wall / 2.0
    pin_depth = min(z_bot_h - 1.2, max(6.0, 1.5 * info['pin_d']))
    for px_c in (pin_off, bw - pin_off):
        a = xz(px_c - pin_r, z_bot_h)
        b = xz(px_c + pin_r, z_bot_h - pin_depth)
        d.rectangle([min(a[0], b[0]), min(a[1], b[1]),
                     max(a[0], b[0]), max(a[1], b[1])],
                    fill='white', outline='#6a3fb5', width=2)
    d.text((xz(1, z_bot_h)[0], xz(0, z_bot_h)[1] - 22),
           'FormUnten (%.0f×%.0f×%.1f mm)' % (bw, bh, z_bot_h),
           font=font(13, bold=True), fill='#1c4e8c')
    d.text((xz(c1 - 7, z_bot_h - 3.2)[0], xz(0, z_bot_h - 3.2)[1]),
           'Kavität', font=font(12.5, bold=True), fill='#1c4e8c')

    ox = bw + 14.0
    c2 = ox + bw / 2.0
    pr = info['pour_d'] / 2.0
    fr = pr + 3.0
    t_left = [xz(ox, 0), xz(c2 - fr, 0), xz(c2 - pr, 2.4),
              xz(c2 - pr, wall), xz(c2 - r_t, wall),
              xz(c2 - r_e, z_top_h), xz(ox, z_top_h)]
    t_right = [xz(c2 + fr, 0), xz(ox + bw, 0), xz(ox + bw, z_top_h),
               xz(c2 + r_e, z_top_h), xz(c2 + r_t, wall),
               xz(c2 + pr, wall), xz(c2 + pr, 2.4)]
    d.polygon(t_left, fill='#e8f4f3', outline='#00706b')
    d.polygon(t_right, fill='#e8f4f3', outline='#00706b')
    d.line([xz(ox, z_top_h), xz(c2 - r_e, z_top_h)], fill='#1e7d32', width=4)
    d.line([xz(c2 + r_e, z_top_h), xz(ox + bw, z_top_h)], fill='#1e7d32', width=4)
    for px_c in (ox + pin_off, ox + bw - pin_off):
        a = xz(px_c - pin_r, z_top_h)
        b = xz(px_c + pin_r, z_top_h - pin_depth)
        d.rectangle([min(a[0], b[0]), min(a[1], b[1]),
                     max(a[0], b[0]), max(a[1], b[1])],
                    fill='white', outline='#6a3fb5', width=2)
    d.text((xz(ox + 1, z_top_h)[0], xz(0, z_top_h)[1] - 22),
           'FormOben (Y-gesp., +Einguss D%.0f)' % info['pour_d'],
           font=font(13, bold=True), fill='#00706b')
    d.text((px0 + 10, py0 + ph - 42),
           'Druckbett (Z = 0 mm) — beide Trennebenen (grün) liegen OBEN',
           font=font(11.5), fill='#58595b')
    d.text((px0 + 10, py0 + ph - 22),
           'violett = 4× Passloch D%.1f mm · Mitte rechts = Trichter + Einguss'
           % (info['pin_d'] + 0.6), font=font(11.5), fill='#58595b')

    # ---- Rechtes Panel: echter XY-Fahrweg einer oberen Schicht von FormOben --
    d.text((596, 12), 'B · Echter XY-Fahrweg FormOben nahe Trennebene',
           font=font(16, bold=True), fill='#1c4e8c')
    segs, z_used = _parse_layer_xy_by_type(top_gcode, z_pick=z_top_h - 0.8)
    xs = [s[0] for s in segs] + [s[2] for s in segs]
    ys = [s[1] for s in segs] + [s[3] for s in segs]
    x0, x1 = min(xs) - 3.0, max(xs) + 3.0
    y0, y1 = min(ys) - 3.0, max(ys) + 3.0
    rx0, ry0, rw, rh = 596, 48, 536, 392
    rsc = min(rw / (x1 - x0), rh / (y1 - y0))

    def xy_px(x, y):
        return (int(rx0 + (x - x0) * rsc),
                int(ry0 + rh - (y - y0) * rsc))

    d.rectangle([rx0, ry0, rx0 + int((x1 - x0) * rsc), ry0 + int((y1 - y0) * rsc)],
                outline='#d4dfec')
    cmap = {
        'WALL-OUTER': '#1c4e8c',
        'WALL-INNER': '#4a7bc7',
        'INFILL-SPARSE': '#b8c7db',
        'INFILL-SOLID': '#8aa8cc',
        'SURFACE-TOP': '#1e7d32',
        'SURFACE-BOTTOM': '#8aa8cc',
        'IRONING': '#e07b00',
    }
    for (ax, ay, bx, by, ft, _zk) in segs:
        d.line([xy_px(ax, ay), xy_px(bx, by)],
               fill=cmap.get(ft, '#1c4e8c'),
               width=2 if 'WALL' in ft else 1)
    for (px_m, py_m) in info['pins']:
        cxp, cyp = xy_px(px_m, py_m)
        rr = max(3, int((info['pin_d'] / 2.0 + 0.3) * rsc))
        d.ellipse([cxp - rr, cyp - rr, cxp + rr, cyp + rr], outline='#b3261e', width=2)
    d.text((596, 452),
           'Z = %.2f mm (%d Druckzüge) · dunkelblau = Wand · grau = Infill · rot = 4 Passlöcher'
           % (z_used, len(segs)), font=font(11.5), fill='#58595b')
    im.save(out_png)
    return out_png


def fig_draft_bars(draft_rows, out_png):
    """D6-konformes Balkenbild mit reichlich rechtem Rand (kein Text-Clip!)
    und expliziter Differenzanzeige Δ Zellen gegenüber 0,0°."""
    W = 1080
    row_h = 34
    H = 68 + row_h * len(draft_rows) + 22
    im = PILImage.new('RGB', (W, H), 'white')
    d = ImageDraw.Draw(im)
    d.text((26, 14),
           'Gemessene Kavitätszellen eines 28-mm-Zylinders (D30) über Draft-Winkel (0° bis 3°)',
           font=font(16, bold=True), fill='#1c4e8c')
    v0 = draft_rows[0][1]
    vmax = max(v for _, v in draft_rows) or 1
    bar_max_w = W - 470
    for i, (lab, v) in enumerate(draft_rows):
        yy = 56 + i * row_h
        d.text((26, yy + 4), lab, font=font(13, bold=True), fill='#222222')
        bw = int(bar_max_w * v / float(vmax))
        d.rectangle([165, yy + 3, 165 + max(4, bw), yy + row_h - 7],
                    fill='#1c4e8c' if i == 0 else '#00706b')
        diff = v - v0
        pct = (100.0 * diff / float(v0)) if v0 else 0.0
        txt = ('%d Zellen  (Basis)' % v) if i == 0 else (
            '%d Zellen  (%d / %.1f %%)' % (v, diff, pct))
        d.text((175 + max(4, bw), yy + 4), txt, font=font(12.5), fill='#58595b')
    im.save(out_png)
    return out_png


def fig_blanks_trio(med_gc, plq_gc, bar_gc, med_info, plq_info, bar_info, out_png):
    """D6-konforme 3er-Tafel: echte XY-Fahrwege der drei parametrischen
    Rohlinge (MEDALLION, PLAQUE, BAR) inkl. Relief-Einbettungssitz (Boss)."""
    W, H = 1160, 430
    im = PILImage.new('RGB', (W, H), 'white')
    d = ImageDraw.Draw(im)
    d.text((28, 10),
           'Echte XY-Fahrwege der drei parametrischen Rohlinge mit Relief-Sitz (make_mold_blank, R273)',
           font=font(16, bold=True), fill='#1c4e8c')

    items = [
        ('MEDALLION D50×10 · Sitz D40×2', med_gc, med_info, 28),
        ('PLAQUE 64×44×10 (R5) · Sitz 52×32×2', plq_gc, plq_info, 408),
        ('BAR 84×42×22 (Taper 0,85) · Sitz 68×23×2', bar_gc, bar_info, 788),
    ]
    for title, gc, inf, ox in items:
        z_boss = inf['wall'] + 1.0
        segs, z_u = _parse_layer_xy_by_type(gc, z_pick=z_boss)
        xs = [s[0] for s in segs] + [s[2] for s in segs]
        ys = [s[1] for s in segs] + [s[3] for s in segs]
        x0, x1 = min(xs) - 3.0, max(xs) + 3.0
        y0, y1 = min(ys) - 3.0, max(ys) + 3.0
        pw, ph = 344, 320
        sc = min(pw / (x1 - x0), ph / (y1 - y0))

        def pxy(x, y):
            return (int(ox + (x - x0) * sc),
                    int(48 + ph - (y - y0) * sc))

        d.text((ox, 32), title, font=font(12.5, bold=True), fill='#00706b')
        d.rectangle([ox, 52, ox + pw, 52 + ph], outline='#d4dfec')
        for (ax, ay, bx, by, ft, _zk) in segs:
            col = '#1c4e8c' if 'WALL' in ft else '#b8c7db'
            d.line([pxy(ax, ay), pxy(bx, by)], fill=col,
                   width=2 if 'WALL' in ft else 1)
        d.text((ox, 382),
               'Block %.0f×%.0f mm · Schnitt Z=%.1f mm (%d Züge)'
               % (inf['block'][0], inf['block'][1], z_u, len(segs)),
               font=font(11), fill='#58595b')
    d.text((28, 404),
           'Außenring = Formrahmen · freier Spalt = Gießkavität (Rand >= 4 mm) · Inneninsel = Boss für bündigen Relief-Einleger',
           font=font(11.5), fill='#58595b')
    im.save(out_png)
    return out_png


def _read_mold_lcd_rows():
    """Liest alle echten LCD-Zeilen unter `__main __gen __mold` aus lcd_menues.cfg."""
    src = open(os.path.join(REPO, 'menus', 'lcd_menues.cfg'),
               encoding='utf-8').read()
    rows = []
    for blk in re.split(r'^\[menu ', src, flags=re.M)[1:]:
        p = blk.split(']')[0].split()
        if len(p) < 4 or p[1] != '__gen' or p[2] != '__mold':
            continue
        m = re.search(r'^name:\s*(.+)$', blk, re.M)
        if not m:
            continue
        raw = m.group(1).strip().strip("'")
        sub = ' / '.join(s.lstrip('_') for s in p[3:])
        disp = raw
        m_fmt = re.match(r"^\{['\"]([^'\"]+)['\"]\s*%\s*menu\.input\}$", raw)
        if m_fmt:
            disp = m_fmt.group(1)
        elif '~' in raw:
            pre = raw.split('~', 1)[0].strip("{ '\"}").rstrip(':') + ': '
            opts = re.findall(r"['\"]([A-Za-z0-9 ()+-]{2,})['\"]",
                              raw.split('~', 1)[1])
            disp = pre + (' / '.join(opts) if opts else '…')
        elif 'AGAIN =' in raw:
            opts = re.findall(r"['\"](> [^'\"]+)['\"]", raw)
            disp = ' → '.join(reversed(opts)) if opts else raw
        rows.append((sub, disp))
    return rows


# --------------------------------------------------------------- PDF-Aufbau
def build(out_pdf):
    with tempfile.TemporaryDirectory() as td:
        def _sub(nm):
            p = os.path.join(td, nm)
            os.makedirs(p, exist_ok=True)
            return p

        # 1) Echter 2-Teile-Lauf (Bipyramide, FINE)
        bipy_src = _write_bipyramid_gcode(os.path.join(td, 'bipyramid.gcode'))
        _, info_2p = pp.make_mold(
            bipy_src, wall=5.0, gap=0.15, pour_d=8.0, funnel='CONICAL',
            vent_d=2.5, pin_d=3.0, draft=0.0, surface='FINE',
            part='BOTH', plane='AUTO', master=True, out_dir=td)
        bot_gc = [os.path.join(td, f) for f in info_2p['files']
                  if 'FormUnten' in f][0]
        top_gc = [os.path.join(td, f) for f in info_2p['files']
                  if 'FormOben' in f][0]

        # 2) Echter Draft-Sweep (0, 1, 2, 3 Grad) an einem 28-mm-Zylinder D30
        cyl_src = _write_bipyramid_gcode(
            os.path.join(td, 'zylinder28.gcode'),
            r_foot=15.0, r_eq=15.0, r_top=15.0, z_eq=0.2, height=28.0)
        draft_rows = []
        for d_deg in (0.0, 1.0, 2.0, 3.0):
            _, inf_d = pp.make_mold(
                cyl_src, wall=5.0, gap=0.15, draft=d_deg,
                part='TOP', plane='OFF', z_off=0.0,
                out_dir=_sub('d_%d' % int(d_deg)))
            draft_rows.append(('Draft %.1f°' % d_deg, inf_d['cells_top']))

        # 3) Echter 4-Teile-Sektor-Lauf am T-Amboss (2-teilig unmöglich!)
        anvil_src = _write_t_amboss_gcode(os.path.join(td, 't_amboss.gcode'))
        refused_2p_msg = ''
        try:
            pp.make_mold(anvil_src, wall=5.0, part='BOTH', plane='OFF',
                         z_off=1.0, sectors=0,
                         out_dir=_sub('sp_fail'))
        except ValueError as exc:
            refused_2p_msg = str(exc)
        _, info_4p = pp.make_mold(
            anvil_src, wall=5.0, part='BOTH', plane='OFF', z_off=1.0,
            sectors=2, sec_half='TOP', surface='STANDARD',
            out_dir=_sub('sp_4p'))
        sec_gc = [os.path.join(td, 'sp_4p', f) for f in info_4p['files']
                  if '_S1' in f][0]

        # 4) Echte Läufe aller drei Rohlinge (MEDALLION, PLAQUE, BAR) mit Relief-Sitz
        med_gc, info_med = pp.make_mold_blank(
            shape='MEDALLION', dia=50.0, thick=10.0, pocket_t=2.0,
            wall=5.0, surface='FINE', part='TOP',
            out_dir=_sub('bl_med'))
        plq_gc, info_plq = pp.make_mold_blank(
            shape='PLAQUE', width=64.0, height=44.0, thick=10.0,
            corner=5.0, pocket_t=2.0, wall=5.0, surface='STANDARD',
            part='TOP', out_dir=_sub('bl_plq'))
        bar_gc, info_bar = pp.make_mold_blank(
            shape='BAR', length=84.0, bar_w=42.0, bar_h=22.0,
            taper=0.85, pocket_t=2.0, wall=5.0, surface='FUZZY',
            part='TOP', out_dir=_sub('bl_bar'))

        # Figuren rendern (alle im Tempdir, bevor Doc.render() läuft)
        p_anat = fig_mold_anatomy(bot_gc, top_gc, info_2p,
                                  os.path.join(td, 'fig1_anatomy.png'))
        p_draft = fig_draft_bars(draft_rows, os.path.join(td, 'fig2_draft.png'))
        p_sec = toolpath_fig(
            sec_gc, os.path.join(td, 'fig3_sector.png'),
            titel='Echter XY-Fahrweg eines 4-Teile-Sektorstücks (%s)'
                  % os.path.basename(sec_gc))
        p_blanks = fig_blanks_trio(
            med_gc, plq_gc, bar_gc, info_med, info_plq, info_bar,
            os.path.join(td, 'fig4_blanks.png'))

        lcd_rows = _read_mold_lcd_rows()

        # ---------------- Dokument zusammensetzen --------------------------
        doc = Doc(
            out_pdf,
            'R2-D2 Macro System · Gießformen-Generator (Methodik & Parameter)',
            titel='Gießformen-Generator — Wissenschaftliche Methodik & Referenz')

        doc.add_cover(
            'ON-MACHINE DESIGN STUDIO · GENERATOR-FACHHEFT (D3)',
            'Gießformen-Generator',
            '2-, 3- und 4-teilige Negativformen aus G-Code sowie parametrische '
            'Rohlinge mit bündigem Relief-Einbettungssitz (R270–R273)',
            absaetze=[
                'Dieses Fachheft dokumentiert die vollständige Mathematik, '
                'Geometrie-Pipeline, Sicherheitsgrenzen und Bedienparameter '
                'von <b>make_mold()</b> und <b>make_mold_blank()</b> direkt '
                'aus dem ausgelieferten Code — so geschrieben, dass man '
                'sowohl die Gleichungen prüfen als auch blind am Drehrad '
                'arbeiten kann.',
                '<b>Wahrheitsregel (D6):</b> Jede Grafik und jede Ergebniszahl '
                'in diesem Dokument wurde beim Bauen der PDF live durch echte '
                'Generator-Läufe erzeugt — keine Skizzen, keine geschätzten '
                'Tabellenwerte.'])

        st = doc.story

        # ========================================================= KAPITEL 1
        st += H1('Kapitel 1 · Prinzip & Geometrie-Pipeline (R270)')
        st += P(
            'Auf einem Raspberry Pi Zero 2 W verbietet sich jede 3D-Boolesche '
            'Netzoperation (trimesh/CGAL): sie sprengt RAM und Laufzeit und '
            'scheitert an nicht-mannigfaltigen Slicer-Exporten. Der R2-Generator '
            'arbeitet deshalb wie der STL-Exporter unmittelbar auf der '
            '<b>fertigen G-Code-Wahrheit</b> — schichtweise gestreamt in einem '
            'diskreten 2D-Zellgitter der Spurbreite <b>wid</b>.')
        st += FORMULA(
            'wid = max(0,40 mm,  nozzle · 1,08)<br/>'
            'W   = ceil(((x_max − x_min) + 2 · wall) / wid) · wid<br/>'
            'H   = ceil(((y_max − y_min) + 2 · wall) / wid) · wid<br/>'
            'r_max = wid / 2 + gap      (Stempelradius je Extrusionssegment)',
            'Alle Blockmaße rasten ganzzahlig auf wid ein; der Block wird '
            'innerhalb des nutzbaren Betts [bx0 + 6, bx1 − 6] × [by0 + 6, '
            'by1 − 6] mm zentriert. Reicht das Bett nicht, bricht der '
            'Generator vor dem ersten Schreibbyte mit Maßangabe ab.')

        st += H2('1.1 Pass 1 — Spurfilter & Silhouetten-Füllung')
        st += NUM(
            '<b>Spur-Scan:</b> G0/G1- und G2/G3-Bewegungen (Bögen mit 0,6 rad '
            'Sehnenabtastung) werden unter voller Beachtung von G90/G91 '
            '(inkl. Klipper-Relativ-E in G91), M82/M83 und G92 in Z-Bänder '
            'einsortiert. Nicht-Objekt-Features (<i>SUPPORT, SKIRT, BRIM, '
            'PRIME-TOWER, CUSTOM, IRONING, TRAVEL</i>) entfallen automatisch; '
            'komplett ungetaggte Altdateien behalten alle positiven Extrusionen '
            '(R253-Regel).',
            '<b>Äquator-/Trennebenen-Wahl:</b> <i>AUTO</i> wählt das Z-Band '
            'mit der größten Spur-Längensumme ∑(|Δx|+|Δy|) als Äquator '
            '<b>z_p</b>; <i>MID</i> teilt bei Band N/2; <i>OFF</i> legt '
            '<b>z_p = z_min + z_off</b> fest (stets so geklemmt, dass der '
            'Oberhälfte mindestens ein Band bleibt).',
            '<b>Rand-Flood-Fill (Silhouetten-Regel):</b> Pro Formschicht wird '
            'jedes Spursegment mit Schrittweite 0,5·wid und Radius r_max ins '
            'Gitter gestempelt. Danach flutet ein 4-Nachbar-Flood-Fill vom '
            'Blockrand aus das Äußere; jede innen eingeschlossene Leerzelle '
            'wird als Silhouette gefüllt und mit exakter Zellzahl im '
            'Konsolenbericht vermerkt (Durchgangslöcher werden voll gegossen).')

        st += H2('1.2 Warum beide Hälften mit der Trennebene NACH OBEN drucken')
        st += P(
            'Läge die Trennebene auf dem Druckbett, müsste die Kavitätsdecke '
            'über dem Hohlraum in der Luft schließen. Stattdessen drucken '
            '<b>beide Formhälften mit der Trennebene als oberster Deckfläche</b>: '
            'jede Kavitätswand steht vom massiven Boden (<i>wall</i> mm) an '
            'auf tragendem Material, und beide Dichtflächen sind glatte '
            'Top-Surfaces. Da die Oberhälfte bei der Montage wie ein Buchdeckel '
            'um die X-Achse auf die Unterhälfte geklappt wird, spiegelt der '
            'Generator die Oberhälfte beim Druck exakt in Y:')
        st += FORMULA(
            'r_top(y) = (rows − 1) − floor((y − y_0) / wid)<br/>'
            'r_pin    = pin_d / 2 + 0,30 mm        (Passloch mit 0,30 mm Spiel)<br/>'
            'Bedingung:  pin_d + 0,30 + 1,20 &lt;= wall   ⇔   wall &gt;= pin_d + 1,50 mm',
            'Die vier Passlöcher sitzen auf Zellmitten im Eck-Randband beider '
            'Hälften identisch und fluchten nach dem Zuklappen ohne Versatz.')

        st += SP(2)
        st.append(IMG(p_anat, width_mm=162))
        st += CAP(
            'Abb. 1 (live berechnet aus Lauf #1, Bipyramide D36×14 mm): '
            'Links der Druck-Querschnitt beider Blöcke (%.0f×%.0f mm, '
            '%d bzw. %d Schichten); rechts der echte XY-Fahrweg von %s.'
            % (info_2p['block'][0], info_2p['block'][1],
               info_2p['layers_bot'], info_2p['layers_top'],
               os.path.basename(top_gc)))

        # ========================================================= KAPITEL 2
        st += H1('Kapitel 2 · Hinterschnitt-Beweis, Draft & Sektorformen (R271)')
        st += H2('2.1 Streaming-Hinterschnittprüfung (2-teilig)')
        st += P(
            'Nummeriert man die Kavitätslagen je Hälfte von der Trennebene '
            '(<b>k = 1</b>, Öffnung) bis zum Kavitätsgrund (<b>k = K</b>, am '
            'Bodenblock), wird der Block in Druckrichtung von <b>k = K</b> '
            'hinab zu <b>k = 1</b> aufgebaut. Eine starre 2-teilige Form ist '
            'genau dann entformbar <i>und</i> ohne Luft-Überhang druckbar, '
            'wenn die Kavität zur Trennebene hin niemals schrumpft:')
        st += FORMULA(
            'Entformbarkeits-Invariante (2-teilig):   C(k)  ⊆  C(k − 1)    für alle k = K … 2',
            'Verletzt auch nur eine Zelle diese Inklusion (prev[i] = 1 und '
            'cav[i] = 0), bricht make_mold() atomar ab (keine angefangene '
            'Ausgabedatei) und nennt Hälfte, Schicht und Zellanzahl. '
            'Sub-Millimeter-Rauigkeiten bis gap (Standard 0,15 mm) fängt '
            'bereits der Stempelradius r_max auf.')

        st += H2('2.2 Zellquantisierte Entformungsschräge (Draft)')
        st += P(
            'Bei senkrechten Objektflanken reduziert eine Entformungsschräge '
            '<b>draft</b> (0,0° bis 3,0°) die Reibung beim Ziehen des Gusses. '
            'Eine bloße Verkleinerung des Stempelradius würde vom Silhouetten-'
            'Flood-Fill geschluckt; deshalb führt der Generator in Tiefe '
            '<b>depth = (k − 0,5)·layer_h</b> genau <b>k_e</b> Runden echter '
            '4-Nachbar-Erosion der Kavitätsmaske aus:')
        st += FORMULA(
            'k_e(depth) = floor( tan(draft) · depth / wid )<br/>'
            '1 Zelle Einzug je  Δz = wid / tan(draft)   (bei wid = 0,432 mm, 2°: alle 12,4 mm)',
            'Würde die Erosion einen dünnen Steg komplett schließen '
            '(any(g) == False), verweigert der Generator statt den Guss '
            'stillschweigend abzuschnüren.')
        st += SP(2)
        st.append(IMG(p_draft, width_mm=160))
        st += CAP(
            'Abb. 2 (echter 4-fach-Lauf am 28-mm-Zylinder D30 über draft = 0°…3°): '
            'Gemessene Kavitätszellen sinken streng monoton von %d auf %d Zellen.'
            % (draft_rows[0][1], draft_rows[-1][1]))

        st += H2('2.3 3- und 4-teilige Sektorformen für Seiten-Hinterschnitte (R271)')
        st += P(
            'Hat eine Hälfte seitliche Hinterschnitte — im Testlauf dieser PDF '
            'ein T-Amboss-Profil (Schaft 24×22 mm, Kopf 40×22 mm), das 2-teilig '
            'mit der ehrlichen Meldung <i>„%s…“</i> ablehnt — teilt '
            '<b>sectors = 1</b> (3-teilig) bzw. <b>sectors = 2</b> (4-teilig) '
            'die betroffene Hälfte durch vertikale Schnittebenen entlang der '
            'längeren Kavitätsachse (Drittel-Teilung). Statt des vertikalen '
            'Hub-Tests prüft der Generator nun pro Sektorstück den '
            '<b>realen Entformungsweg</b>:'
            % refused_2p_msg[:88])
        st += B(
            '<b>Außenstücke (seitliches Abschieben):</b> Entlang jeder '
            'Gitterzeile senkrecht zur Schnittebene muss die Kavität lückenlos '
            'an der Schnittfläche anliegen — ein eingehakter Hinterschnitt im '
            'Außenstück wird sofort verweigert.',
            '<b>Mittelstück bei 4-teiliger Form (vertikaler Hub):</b> Nachdem '
            'beide Außenstücke abgezogen sind, gilt im mittleren Drittel '
            'wieder C_mid(k) ⊆ C_mid(k − 1).',
            '<b>Ehrlicher Preis (Deckenbrücke & Tunnel):</b> Wo die Kavität '
            'zur Trennebene schmaler wird, überbrückt das Sektorstück den '
            'Rücksprung; die maximale Spannweite wird in mm gemessen und über '
            '<b>25,0 mm</b> verweigert (im Testlauf unten gemessen: '
            '<b>%.2f mm</b> max. Brücke, %d Brückenzellen). Zwei horizontale '
            'Passstift-Tunnel je Schnittfläche registrieren die Backen.'
            % (info_4p['bridges']['max_mm'], info_4p['bridges']['cells']))
        st += SP(2)
        st.append(IMG(p_sec, width_mm=154))
        st += CAP(
            'Abb. 3 (echter 4-Teile-Sektor-Lauf am T-Amboss-Profil): '
            'XY-Fahrweg der linken Außenbacke (%s), Schnittachse %s.'
            % (os.path.basename(sec_gc), info_4p['sec_axis']))

        # ========================================================= KAPITEL 3
        st += H1('Kapitel 3 · Oberflächen-Physik (R272) & Rohlinge mit Sitz (R273)')
        st += H2('3.1 Die drei Oberflächen-Modi: STANDARD, FINE, FUZZY')
        st += TBL(
            ['Modus', 'Tempo', 'Technischer Eingriff im G-Code', 'Wirkung am Guss'],
            [['STANDARD', '60 mm/s',
              'Reguläre Kontur- und Deckflächenbahnen ohne Glättungsversatz.',
              'Schnellster Formdruck; normale FDM-Schichtzeichnung.'],
             ['FINE', '20 mm/s',
              'Trennebene erhält dichte IRONING-Glättungszüge mit 15 % Fluss; '
              'SPEED_PRINT im gesamten File auf 20 mm/s abgesenkt.',
              'Spiegelglatte Dichtfläche (kein Harz-/Silikongrat an der Naht) '
              'und ruhige Innenwände.'],
             ['FUZZY', '60 mm/s',
              'Deterministischer Hash-Versatz der Kavitäts-Wandkontur um bis zu '
              '0,12 mm AUSSCHLIESSLICH ins Formmaterial hinein (Zellmaske '
              'bleibt identisch zu STANDARD).',
              'Edelmatte Gussoberfläche; bricht Vakuumhaftung beim Entformen, '
              'erzeugt garantiert keinen Hinterschnitt.']],
            [26 * mm, 24 * mm, 62 * mm, 50 * mm], mono_cols=(0,))

        st += H2('3.2 Parametrische Rohlinge ohne Quelldatei (make_mold_blank)')
        st += P(
            'Für Seifen, Wachsbarren, Plaketten oder Silikon-Untersetzer '
            'braucht man kein geslictes 3D-Modell: <b>make_mold_blank()</b> '
            'erzeugt eine exakte Kontur-Referenz und schickt sie durch '
            'denselben <b>make_mold()</b>-Kern (inkl. Passlöchern, Einguss, '
            'Oberflächenwahl). Standardmäßig ist <b>part = TOP</b> und '
            '<b>plane = OFF (z_off = 0)</b>, sodass eine einteilige offene '
            'Gießwanne entsteht; mit <b>part = BOTH</b> kommt ein planer '
            'Gegenblock mit Passlöchern hinzu.')
        st += TBL(
            ['Rohling (SHAPE)', 'Geometrie & Gleichung', 'Maßgrenzen (hart geklemmt)', 'Standard-Tasche (bei pocket_t > 0)'],
            [['MEDALLION',
              'Kreisscheibe mit Radius R = dia / 2 (72-Eck-Kontur).',
              'dia: 15…100 mm<br/>thick: 4…25 mm',
              'Runde Tasche:<br/>pocket_d = dia − 10 mm<br/>(5 mm umlaufender Rand)'],
             ['PLAQUE',
              'Rechteck width × height mit Viertelkreis-Eckenradius corner.',
              'width, height: 20…150 mm<br/>thick: 4…25 mm<br/>corner: 0…min(12, min/2)',
              'Rechteck-Tasche:<br/>(width − 12) × (height − 12) mm<br/>(6 mm Rand)'],
             ['BAR',
              'Trapez-Barren: Fußbreite bar_w verjüngt sich nach oben linear auf '
              'w(z) = bar_w · (1 − (1 − taper)·z/bar_h).',
              'length: 30…180 mm<br/>bar_w: 15…90 mm<br/>bar_h: 10…60 mm<br/>taper: 0,50…1,00',
              'Rechteck-Tasche oben:<br/>(length − 16) ×<br/>(bar_w·taper − 12) mm']],
            [28 * mm, 50 * mm, 42 * mm, 42 * mm], mono_cols=(0,))

        st += H2('3.3 Der bündige Relief-Einbettungssitz (Boss-Mathematik)')
        st += P(
            'Ein gedrucktes Lithophan-, ColorPicture- oder StringArt-Plättchen '
            'lässt sich direkt in die Gussoberseite eingießen: Bei '
            '<b>pocket_t &gt; 0</b> bleibt auf dem Boden der TOP-Kavität ein '
            'erhabener Sockel (<b>Boss</b>) mit exakt senkrechten Wänden stehen '
            '(er wird <i>nach</i> der Draft-Erosion gestempelt). Vor dem '
            'Abgießen legt man das Relief mit der Motivseite nach oben auf den '
            'Boss — nach dem Entformen sitzt es flächenbündig im Gussstück. '
            'Drei harte Geometriebedingungen verhindern Ausschuss:')
        st += FORMULA(
            '1) Umlaufender Gussrand:  dia − pocket_d &gt;= 8 mm  bzw.  W − pocket_w &gt;= 8 mm  (je Seite &gt;= 4 mm)<br/>'
            '2) Tragender Gussboden:   thick − pocket_t &gt;= 2,0 mm   (und &gt;= 2 Dichtschichten über z_p)<br/>'
            '3) Kavitäts-Freiraum:     Boss + 2 Gitterzellen (2 · wid) liegt auf JEDER Boss-Lage in C_top(k)',
            'Wird eine der drei Schranken verletzt, lehnt der Generator vor '
            'dem Schreiben mit konkreter Millimeter-Angabe ab.')
        st += SP(2)
        st.append(IMG(p_blanks, width_mm=162))
        st += CAP(
            'Abb. 4 (drei echte make_mold_blank-Läufe): MEDALLION, PLAQUE und '
            'BAR jeweils geschnitten auf halber Boss-Höhe — die mittlere '
            'Insel erzeugt den bündigen Relief-Sitz im fertigen Guss.')

        # ========================================================= KAPITEL 4
        st += H1('Kapitel 4 · Vollständige Parameter-, LCD- & Makro-Referenz')
        st += H2('4.1 Engine- & Makro-Parameter (make_mold / MOLD_CREATE)')
        st += TBL(
            ['Parameter (Python / Makro)', 'Standard', 'Klemmbereich / Werte', 'Technische Bedeutung'],
            [['wall (mold_wall)', '5,0 mm', '3,0 … 15,0 mm',
              'Wand- und Bodenstärke des Formblocks; muss &gt;= pin_d + 1,5 mm sein.'],
             ['gap (mold_gap)', '0,15 mm', '0,05 … 0,30 mm',
              'Radialer Kavitäts-Zuschlag (Toleranzspalt &amp; Sub-Gap-Hinterschnittpuffer).'],
             ['pour_d (mold_pour)', '8,0 mm', '5,0 … 15,0 mm',
              'Durchmesser des Eingusskanals durch den Rücken der Oberhälfte.'],
             ['funnel (mold_funnel)', 'CONICAL', 'CONICAL / NONE',
              'Konischer Eingusstrichter an der Außenfläche (+3 mm Radiusöffnung).'],
             ['vent_d (mold_vent)', '2,5 mm', '1,5 … 4,0 mm',
              'Entlüftungsbohrungen an Hochpunkten + Entlüftungsrillen in der Trennebene.'],
             ['pin_d (mold_pin)', '3,0 mm', '3,0 … 8,0 mm',
              'Nenndurchmesser der 4 Passstifte; Bohrung wird mit pin_d + 0,60 mm gefertigt.'],
             ['draft (mold_draft)', '0,0°', '0,0° … 3,0°',
              'Entformungsschräge als 4-Nachbar-Zellerosion je Tiefe wid/tan(draft).'],
             ['surface / SURFACE', 'STANDARD', 'STANDARD / FINE / FUZZY',
              '60 mm/s Standard · FINE (20 mm/s + 15 % Ironing) · FUZZY (matt, &lt;=0,12 mm).'],
             ['plane / PLANE', 'AUTO', 'AUTO / MID / OFF',
              'Trennebene: Äquator maximaler Spurfläche, Z-Mitte oder z_min + z_off.'],
             ['z_off (mold_zoff)', '0,0 mm', 'frei (geklemmt auf Objekt)',
              'Schnitthöhe über Objektfuß bei PLANE=OFF.'],
             ['part / PART', 'BOTH', 'BOTH / TOP / BOTTOM',
              'Beide Hälften drucken oder gezielt nur eine Hälfte ausgeben.'],
             ['sectors / SECTORS', '0', '0 / 1 / 2',
              '0 = 2-teilig · 1 = 3-teilig (1 Schnitt) · 2 = 4-teilig (2 Drittelschnitte).'],
             ['sec_half / HALF', 'AUTO', 'AUTO / TOP / BOTTOM',
              'Welche Hälfte die Sektorschnitte erhält (AUTO wählt die hinterschnittene).'],
             ['master (mold_master)', 'False', 'True / False',
              'Erzeugt zusätzlich das volle Silhouetten-Positiv (Vnn_Master_…).']],
            [42 * mm, 20 * mm, 36 * mm, 64 * mm], mono_cols=(0,))

        st += H2('4.2 Echte LCD-Menüstruktur (live aus menus/lcd_menues.cfg gelesen)')
        st += P(
            'Wurzelpfad am Drehrad und in der Web-LCD: <b>Tools &gt; Casting molds</b>. '
            'Alle aktiven Bau-Aktionen verwenden die 2-Tasten-Sicherung '
            '(1. Druck schärft <i>AGAIN = build</i>, 2. Druck reiht den '
            'Hintergrundauftrag in <i>gcodes/Molds/</i> ein):')
        st += TBL(
            ['Menüzweig unter __mold', 'Anzeige am Display'],
            [[k, v] for k, v in lcd_rows],
            [52 * mm, 110 * mm], mono_cols=(0,))

        st += H2('4.3 Konsole & Effektketten (Toolchain)')
        st += CODE(
            '# Dateiform (nutzt die in Pre-Print > File gewählte Datei oder FILE=...):\n'
            'MOLD_INFO\n'
            'MOLD_CREATE PART=BOTH PLANE=AUTO SURFACE=FINE\n'
            'MOLD_CREATE FILE=vase.gcode PART=BOTH SECTORS=2 HALF=AUTO\n\n'
            '# Parametrischer Rohling ohne Quelldatei:\n'
            'MOLD_BLANK_INFO\n'
            'MOLD_BLANK_CREATE SHAPE=MEDALLION DIA=50 THICK=10 POCKET_T=2 SURFACE=FINE\n'
            'MOLD_BLANK_CREATE SHAPE=BAR LENGTH=90 BARW=40 BARH=25 TAPER=0.85 POCKET_T=2')
        st.append(BOX(
            'Gießformen in JSON-Effektketten (Pre-Print > Tools > Toolchain)',
            ['Die Schritte <b>"tool": "mold"</b> und <b>"tool": "mold_blank"</b> '
             'sind voll kettbar (z. B. <i>Scale → Twist → Mold TOP</i> oder '
             '<i>Mold Blank → Texture auf Außenrahmen</i>), sofern '
             'genau EINE Ausgabedatei entsteht: <b>part = TOP</b> oder '
             '<b>BOTTOM</b> und <b>sectors = 0</b>. Mehrdateien-Jobs '
             '(<i>part = BOTH</i> oder <i>sectors &gt; 0</i>) gehören ins '
             'Generator-Menü und werden vom Preset-Prüfer vorab mit Klartext '
             'abgelehnt.'],
            kind='note'))

        # ========================================================= KAPITEL 5
        st += H1('Kapitel 5 · Gemessene Beispiel-Sätze & Fehlerdiagnose')
        st += P(
            'Die folgende Tabelle zeigt fünf vollständige Referenz-Parametersätze '
            'für typische Gießmaterialien — alle fünf wurden beim Bau dieses '
            'PDFs tatsächlich durch <b>make_mold()</b> bzw. '
            '<b>make_mold_blank()</b> gerechnet; Blockmaße, Schichtzahlen, '
            'Kavitätszellen und Dateinamen sind die realen Rückgabewerte:')

        ex_rows = [
            ['1 · Silikon-/Harz-<br/>Abguss (2-teilig,<br/>FINE + Master)',
             'wall=5, gap=0,15,<br/>pin_d=3, pour_d=8,<br/>plane=AUTO, FINE,<br/>master=1',
             '%.0f × %.0f mm<br/>(%d×%d Zellen)'
             % (info_2p['block'][0], info_2p['block'][1],
                info_2p['grid'][0], info_2p['grid'][1]),
             'B: %d Lagen (%d Z.)<br/>T: %d Lagen (%d Z.)<br/>%d Dateien (+Master)'
             % (info_2p['layers_bot'], info_2p['cells_bot'],
                info_2p['layers_top'], info_2p['cells_top'],
                len(info_2p['files']))],
            ['2 · T-Amboss mit<br/>Überhang (4-teilige<br/>Sektorform)',
             'wall=5, plane=OFF<br/>(z=1), sectors=2,<br/>sec_half=TOP,<br/>surface=STANDARD',
             '%.0f × %.0f mm<br/>Schnittachse %s'
             % (info_4p['block'][0], info_4p['block'][1], info_4p['sec_axis']),
             '%d Dateien (1 Basis +<br/>3 Sektorbacken), max.<br/>Brücke %.2f mm'
             % (len(info_4p['files']), info_4p['bridges']['max_mm'])],
            ['3 · Gips-/Harz-<br/>Medaillon mit<br/>rundem Litho-Sitz',
             'SHAPE=MEDALLION,<br/>dia=50, thick=10,<br/>pocket_t=2 (D40),<br/>surface=FINE',
             '%.0f × %.0f mm<br/>Rand 5,0 mm'
             % (info_med['block'][0], info_med['block'][1]),
             'T: %d Lagen, Sitz<br/>D%.0f × %.1f mm<br/>(%d Lagen)'
             % (info_med['layers_top'], info_med['pocket']['d'],
                info_med['pocket']['t_mm'], info_med['pocket']['layers'])],
            ['4 · Schild-Plakette<br/>mit abgerundeten<br/>Ecken (R5)',
             'SHAPE=PLAQUE,<br/>64×44×10, corner=5,<br/>pocket_t=2 (52×32),<br/>STANDARD',
             '%.0f × %.0f mm<br/>Rand 6,0 mm'
             % (info_plq['block'][0], info_plq['block'][1]),
             'T: %d Lagen, Sitz<br/>%.0f × %.0f × %.1f mm'
             % (info_plq['layers_top'], info_plq['pocket']['w'],
                info_plq['pocket']['h'], info_plq['pocket']['t_mm'])],
            ['5 · Seifen-/Wachs-<br/>barren mit Taper &amp;<br/>FUZZY-Mattung',
             'SHAPE=BAR, 84×42×22,<br/>taper=0,85, pocket_t=2,<br/>surface=FUZZY',
             '%.0f × %.0f mm<br/>Top-Breite 35,7 mm'
             % (info_bar['block'][0], info_bar['block'][1]),
             'T: %d Lagen, Sitz<br/>%.0f × %.1f × %.1f mm,<br/>matt'
             % (info_bar['layers_top'], info_bar['pocket']['w'],
                info_bar['pocket']['h'], info_bar['pocket']['t_mm'])],
        ]
        st += TBL(
            ['Anwendungsfall', 'Parametersatz', 'Gemessener Block', 'Gemessenes Ergebnis'],
            ex_rows, [39 * mm, 45 * mm, 34 * mm, 44 * mm])

        st += H2('5.1 Ehrliche Schutzgrenzen — Symptom, Ursache, Abhilfe')
        st += TBL(
            ['Ablehnungsmeldung (Auszug)', 'Physikalische Ursache', 'Sofortige Abhilfe am Drehrad'],
            [['„undercut in the … half at layer …“',
              'Kavität verengt sich zur Trennebene hin (Guss klemmt + Druck über Luft).',
              'Plane auf AUTO/OFF verschieben, weiches Silikon wählen oder Sectors auf 1/2 stellen.'],
             ['„dowel holes do not fit the wall“',
              'pin_d + 0,3 mm Spiel + 1,2 mm Mindeststeg &gt; wall.',
              'Wall auf mindestens pin_d + 1,5 mm erhöhen (bei D3: Wall &gt;= 4,5 mm) oder Pin D senken.'],
             ['„would bridge … over the cavity … beyond 25mm“',
              'Seitlicher Hinterschnitt im Sektorstück verlangt &gt; 25 mm freitragende Decke.',
              'Schnittebene (Plane/Z offset) näher an die Einschnürung legen oder Modell teilen.'],
             ['„leaves no rim / needs a floor / 2 cells of clearance“',
              'Relief-Sitz (Boss) lässt &lt; 4 mm Rand, &lt; 2 mm Boden oder berührt die Kavitätswand.',
              'Seat depth (pocket_t) verringern oder Rohlingsmaß (Diameter / Width / Bar W / Taper) erhöhen.'],
             ['„mold block needs … bed offers …“',
              'Objekt-BBox + 2·wall überschreitet das nutzbare Druckbett (Bett − 2×6 mm Rand).',
              'Wall reduzieren oder Quelldatei vorab mit Scale X/Y verkleinern.']],
            [52 * mm, 54 * mm, 56 * mm])

        st += SP(4)
        st.append(BOX(
            'Werkstatt-Merksatz für den ersten Abguss',
            ['<b>Starre Form (PLA/PETG) → weicher Guss</b> (Silikon, Wachs, '
             'Glyzerinseife) funktioniert ab 0°–1° Draft direkt. '
             '<b>Starrer Guss</b> (Epoxidharz, Gips, Beton) braucht entweder '
             '<b>Draft 2°–3° + Trennmittel + FUZZY/FINE</b>, eine 3-/4-teilige '
             'Sektorform — oder man gießt in der gedruckten Form zuerst eine '
             'weiche Silikon-Negativform um das mitgedruckte '
             '<b>Master</b>-Positiv.'],
            kind='tip'))

        doc.render()

    raw = open(out_pdf, 'rb').read()
    pages = len(re.findall(rb'/Type\s*/Page[^s]', raw))
    print('[ok] MOLDS.pdf: %d pages, version %s, %d LCD rows, 5 live runs'
          % (pages, R2VER, len(lcd_rows)))
    return pages


if __name__ == '__main__':
    build(os.path.join(REPO, 'MOLDS.pdf'))
