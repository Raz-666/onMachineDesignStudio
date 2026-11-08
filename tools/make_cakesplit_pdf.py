#!/usr/bin/env python3
"""CUTSPLIT.pdf — the methodology documentation of Cut & Split (user
request, .136v round / task 12): the plane mathematics, the two-pass
architecture, the EXACT segment splitting (t-interpolation, E shares),
stream separation with per-stream position tracking, the UPPER placement
(Rodrigues reorientation), and a fully worked example whose numbers come
from a REAL cut_cake run on a synthetic file (not hand-computed — the
tables are the code output, same truth rule as TEXTURING.pdf).

Content basis: tools/r2_cake.py (cut_cake, _normal, _rot_about, seg,
emit), tools/r2_postproc.py (the cake watcher job, R224: yaw forced to
0 - the LCD no longer sets it), menus/lcd_menues.cfg (Pre-Print > Mods >
Cut & Split), macros/17_generator.cfg (CAKE_APPLY).
"""
import io
import math
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (BaseDocTemplate, PageTemplate, Frame,
                                Paragraph, Spacer, Table, TableStyle,
                                CondPageBreak, Image)
from PIL import Image as PILImage, ImageDraw, ImageFont

from r2_cake import cut_cake, _normal

# ---------------------------------------------------------------- fonts ----
FD = '/usr/share/fonts/truetype/dejavu/'
pdfmetrics.registerFont(TTFont('DVS', FD + 'DejaVuSans.ttf'))
pdfmetrics.registerFont(TTFont('DVSB', FD + 'DejaVuSans-Bold.ttf'))


def _font(sz, bold=False):
    return ImageFont.truetype(FD + ('DejaVuSans-Bold.ttf' if bold
                                    else 'DejaVuSans.ttf'), sz)


BLUE = colors.HexColor('#1c4e8c'); LBLUE = colors.HexColor('#e8f0fa')
ORANGE = colors.HexColor('#e07b00'); GRAY = colors.HexColor('#58595b')
LGRAY = colors.HexColor('#f2f2f2'); GREEN = colors.HexColor('#1e7d32')
RED = colors.HexColor('#b3261e'); PURPLE = colors.HexColor('#6a3fb5')
TEAL = colors.HexColor('#00706b')

S = {
 'title': ParagraphStyle('t', fontName='DVSB', fontSize=25, leading=30, textColor=BLUE, alignment=1),
 'sub':   ParagraphStyle('s', fontName='DVS', fontSize=13.5, leading=19, textColor=GRAY, alignment=1),
 'h1':    ParagraphStyle('h1', fontName='DVSB', fontSize=20, leading=26, textColor=BLUE, spaceBefore=12, spaceAfter=2, keepWithNext=1),
 'h2':    ParagraphStyle('h2', fontName='DVSB', fontSize=15, leading=21, textColor=BLUE, spaceBefore=16, spaceAfter=7, keepWithNext=1),
 'p':     ParagraphStyle('p', fontName='DVS', fontSize=12, leading=18, spaceAfter=7, allowWidows=0, allowOrphans=0),
 'b':     ParagraphStyle('b', fontName='DVS', fontSize=12, leading=17.5, leftIndent=12, spaceAfter=5, allowWidows=0, allowOrphans=0),
 'code':  ParagraphStyle('c', fontName='DVS', fontSize=10.6, leading=15.4, backColor=LGRAY, borderPadding=5, leftIndent=6, spaceAfter=8),
 'cap':   ParagraphStyle('cap', fontName='DVS', fontSize=10.3, leading=14.6, textColor=GRAY, alignment=1, spaceBefore=3, spaceAfter=8),
 'ts':    ParagraphStyle('ts', fontName='DVSB', fontSize=10.2, leading=13.8, textColor=colors.white),
 'tc':    ParagraphStyle('tc', fontName='DVS', fontSize=10.2, leading=13.8),
 'end':   ParagraphStyle('end', fontName='DVSB', fontSize=13, leading=18, textColor=BLUE, alignment=1),
}

def H1(t): return [CondPageBreak(60*mm), Paragraph(t, S['h1'])]
def H2(t): return [CondPageBreak(46*mm), Paragraph(t, S['h2'])]
def P(t):  return Paragraph(t, S['p'])
def B(*items): return [Paragraph('•&nbsp; ' + i, S['b']) for i in items]
def CODE(t): return Paragraph(t.replace('\n', '<br/>').replace(' ', '&nbsp;'), S['code'])
def CAP(t): return Paragraph(t, S['cap'])

def TBL(headers, rows, widths):
    data = [[Paragraph(x, S['ts']) for x in headers]]
    for row in rows:
        data.append([Paragraph(c, S['tc']) for c in row])
    t = Table(data, colWidths=widths, repeatRows=1)
    t.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), BLUE),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, LBLUE]),
        ('GRID', (0, 0), (-1, -1), 0.4, colors.HexColor('#9db3cc')),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('LEFTPADDING', (0, 0), (-1, -1), 4),
        ('RIGHTPADDING', (0, 0), (-1, -1), 4),
        ('TOPPADDING', (0, 0), (-1, -1), 3),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
    ]))
    return t


class Doc(BaseDocTemplate):
    def __init__(self, fn):
        super().__init__(fn, pagesize=A4,
                         leftMargin=17*mm, rightMargin=17*mm,
                         topMargin=16*mm, bottomMargin=16*mm,
                         title='R2-D2 Cut & Split — Methodik',
                         author='R2-D2 Macro System')
        f = Frame(self.leftMargin, self.bottomMargin, self.width, self.height, id='f')
        self.addPageTemplates([PageTemplate(id='pt', frames=[f], onPage=self._deco)])

    def _deco(self, canv, doc):
        canv.saveState()
        canv.setStrokeColor(BLUE); canv.setLineWidth(0.7)
        canv.line(17*mm, 285*mm, 193*mm, 285*mm)
        canv.setFont('DVS', 8.2); canv.setFillColor(GRAY)
        canv.drawString(17*mm, 287.2*mm, 'R2-D2 Macro System · Cut & Split — Methodik')
        canv.drawRightString(193*mm, 287.2*mm, 'R2-2026-11-08.136x')
        canv.setFont('DVS', 8.6)
        canv.drawCentredString(105*mm, 9.5*mm, 'Seite %d' % doc.page)
        canv.restoreState()


# ---------------------------------------------------------------- figures ---
def fig_plane(pitch_deg, z_mm, width_mm=150):
    """Side view (X/Z): object silhouette, tilted plane, UPPER/LOWER."""
    W, H = 640, 420
    im = PILImage.new('RGB', (W, H), 'white')
    d = ImageDraw.Draw(im)
    # coordinate window: x -25..45 mm, z -2..32 mm -> pixels
    x0, x1, z0, z1 = -25.0, 45.0, -2.0, 32.0

    def px(x, z):
        return (int((x - x0) / (x1 - x0) * (W - 40) + 20),
                int(H - 24 - (z - z0) / (z1 - z0) * (H - 44)))

    # bed
    d.line([px(x0, 0), px(x1, 0)], fill=(90, 90, 91), width=4)
    for hx in range(int(x0), int(x1) + 1, 10):
        a, b_ = px(hx, 0), px(hx, -1.2)
        d.line([a, b_], fill=(150, 150, 150), width=2)
    # object: bell 10..30 mm wide, 0..26 tall
    obj = []
    for i in range(65):
        t = i / 64.0
        zz = 26.0 * t
        rr = 10.0 - 6.5 * t + 1.2 * math.sin(3.1 * t)
        obj.append((10.0 - rr, zz))
    for i in range(65):
        t = 1 - i / 64.0
        zz = 26.0 * t
        rr = 10.0 - 6.5 * t + 1.2 * math.sin(3.1 * t)
        obj.append((10.0 + rr, zz))
    obj.append(obj[0])
    d.polygon([px(x, z) for x, z in obj], fill=(232, 240, 250),
              outline=(28, 78, 140))
    # plane through (bed center x=10? use 10 for the picture) at z_mm, tilt
    bcx = 10.0
    p = math.radians(pitch_deg)
    n = (math.sin(p), math.cos(p))          # 2D (x,z) normal, yaw=roll=0
    a = px(-25.0, z_mm + n[0] * (-25.0 - bcx) / max(1e-9, -n[1]))
    # simpler: plane z = z_mm + tan(-pitch)*(x - bcx)  (n . (P-p0)=0)
    tp = math.tan(math.radians(-pitch_deg))
    d.line([px(x0, z_mm + tp * (x0 - bcx)), px(x1, z_mm + tp * (x1 - bcx))],
           fill=(227, 123, 0), width=5)
    # UPPER / LOWER labels
    up = px(31, 20); lo = px(-12, 6)
    d.text((up[0] - 34, up[1] - 10), 'UPPER', fill=(30, 125, 50),
           font=_font(26, bold=True))
    d.text((lo[0] - 30, lo[1] - 10), 'LOWER', fill=(179, 38, 30),
           font=_font(26, bold=True))
    # normal arrow at the plane center
    c0 = px(bcx, z_mm)
    c1 = px(bcx + n[0] * 9, z_mm + n[1] * 9)
    d.line([c0, c1], fill=(28, 78, 140), width=4)
    d.polygon([(c1[0] + 7, c1[1]), (c1[0] - 4, c1[1] + 5),
               (c1[0] - 4, c1[1] - 5)], fill=(28, 78, 140))
    d.text((c1[0] + 10, c1[1] - 26), 'n', fill=(28, 78, 140),
           font=_font(24, bold=True))
    d.text((px(bcx, 0)[0] - 30, H - 20), 'Bett', fill=(90, 90, 91),
           font=_font(18))
    d.text((20, 16), 'Z', fill=(90, 90, 91), font=_font(20))
    d.text((W - 34, px(0, 0)[1] - 24), 'X', fill=(90, 90, 91), font=_font(20))
    buf = io.BytesIO(); im.save(buf, format='PNG'); buf.seek(0)
    img = Image(buf, width=width_mm*mm, height=width_mm*mm*H/float(W))
    img.hAlign = 'CENTER'
    return img


def fig_split(width_mm=150):
    """One segment crossing the plane: A - S - B with w0/w1, t, E shares."""
    W, H = 640, 300
    im = PILImage.new('RGB', (W, H), 'white')
    d = ImageDraw.Draw(im)
    f = _font(19); fb = _font(20, bold=True)
    # plane (diagonal), segment A->B crossing it
    d.line([(60, 40), (600, 250)], fill=(227, 123, 0), width=5)
    d.text((560, 258), 'Schnittebene', fill=(227, 123, 0), font=f)
    A = (120, 250); B_ = (540, 60)
    S = (330, 157)                      # crossing point (visual)
    d.line([A, S], fill=(30, 125, 50), width=6)
    d.line([S, B_], fill=(179, 38, 30), width=6)
    for pt, lab, col in ((A, 'A  w(A) = w0 < 0', (179, 38, 30)),
                         (B_, 'B  w(B) = w1 > 0', (30, 125, 50))):
        d.ellipse([pt[0]-8, pt[1]-8, pt[0]+8, pt[1]+8], fill=col)
    d.text((A[0]-38, A[1]+14), 'A', fill=(90, 90, 91), font=fb)
    d.text((B_[0]+12, B_[1]-30), 'B', fill=(90, 90, 91), font=fb)
    d.ellipse([S[0]-7, S[1]-7, S[0]+7, S[1]+7], fill=(227, 123, 0))
    d.text((S[0]+12, S[1]+8), 'S = A + t·(B-A)', fill=(227, 123, 0), font=fb)
    d.text((140, 268), 'LOWER-Anteil: E·t', fill=(179, 38, 30), font=f)
    d.text((420, 40), 'UPPER-Anteil: E·(1-t)', fill=(30, 125, 50), font=f)
    d.text((150, 30), 't = w0 / (w0 - w1)', fill=(28, 78, 140), font=fb)
    buf = io.BytesIO(); im.save(buf, format='PNG'); buf.seek(0)
    img = Image(buf, width=width_mm*mm, height=width_mm*mm*H/float(W))
    img.hAlign = 'CENTER'
    return img


# ------------------------------------------------- the worked real example --
def worked_example():
    """Run cut_cake on a synthetic file; return (info, rows for the table).

    The numbers printed in the PDF come from THIS run (and from the same
    _normal the tool uses) - nothing hand-computed."""
    d = tempfile.mkdtemp()
    src = os.path.join(d, 'sample.gcode')
    pitch, zoff = 10.0, 6.0
    with open(src, 'w') as f:
        f.write('; sample for the CUTSPLIT methodology PDF\nM83\n')
        e = 0.0
        for lay in range(30):
            z = 0.2 + 0.2 * lay
            f.write(';LAYER_CHANGE\nG1 Z%.3f F600\n' % z)
            f.write(';TYPE:Outer wall\n')
            for j in range(24):
                a = 2 * math.pi * j / 24
                r = 12.0 + 0.5 * math.sin(3 * a)
                x, y = 110 + r * math.cos(a), 110 + r * math.sin(a)
                e += 0.05
                f.write('G1 X%.3f Y%.3f E%.5f F2700\n' % (x, y, e))
    paths, info = cut_cake(src, out_dir=d, pitch=pitch, roll=0.0,
                           z_offset=zoff, part='BOTH', reorient=True,
                           bed=(0.0, 0.0, 220.0, 220.0))
    # one crossing segment, recomputed with the tool's own plane math
    n = _normal(0.0, pitch, 0.0)
    bcx = bcy = 110.0

    def w(x, y, z):
        return (n[0]*(x-bcx) + n[1]*(y-bcy) + n[2]*(z-zoff))

    segs = []
    px_ = py_ = None
    cur_z = None
    last_e = 0.0
    for ln in open(src):
        ls = ln.split(';', 1)[0].strip()
        if ls.startswith('G1 Z'):
            cur_z = float(ls.split()[1][1:])
            continue
        if not ls.startswith('G1 X'):
            continue
        pr = ls.split()
        x = float(pr[1][1:]); y = float(pr[2][1:])
        e = float(pr[3][1:]) if len(pr) > 3 and pr[3].startswith('E') else None
        z = cur_z or 0.0
        if px_ is not None and e is not None:
            w0, w1 = w(px_, py_, z), w(x, y, z)
            if (w0 < 0) != (w1 < 0) and abs(w0 - w1) > 1e-9:
                t = w0 / (w0 - w1)
                segs.append(dict(x0=px_, y0=py_, z0=z, x1=x, y1=y, z1=z,
                                 w0=w0, w1=w1, t=t, de=e - last_e,
                                 sx=px_ + (x-px_)*t, sy=py_ + (y-py_)*t))
        px_, py_ = x, y
        if e is not None:
            last_e = e
    ex = segs[len(segs)//2] if segs else None
    return info, n, ex, paths


def main():
    flow = []
    A = flow.append

    info, nvec, ex, paths = worked_example()

    # ------------------------------------------------------------- cover --
    A(Spacer(1, 10*mm))
    A(Paragraph('R2-D2 Cut &amp; Split', S['title']))
    A(Paragraph('Methodik: ein Druck, eine Ebene, zwei eigenständige Hälften', S['sub']))
    A(Spacer(1, 6*mm))
    A(P('Dieses Handbuch dokumentiert das Cut-&amp;-Split-Werkzeug (Pre-Print '
        '&gt; Mods &gt; Cut &amp; Split, Menüpunkt Cake): die Mathematik der '
        'Schnittebene, die Zwei-Durchlauf-Architektur, das EXAKTE Teilen '
        'jeder Bewegung an der Ebene (t-Interpolation, E-Anteile), die '
        'Trennung in zwei Ströme mit Positions-Tracking, die Platzierung '
        'der oberen Hälfte (Rodrigues-Drehung der Schnittfläche aufs '
        'Bett) — und ein vollständig durchgerechnetes Beispiel, dessen '
        'Zahlen aus einem echten Lauf des Werkzeugs stammen.'))
    A(Spacer(1, 3*mm))
    A(TBL(['Ebene', 'Was'], [
        ['Schnittebene', 'Eine Ebene (Pitch/Roll in 0,5°-Schritten, Z-Höhe '
         'am Bettzentrum) durchschneidet den Druck. Die Normale zeigt '
         'zur UPPER-Seite.'],
        ['Segment-Split', 'Jede Bewegung wird exakt an der Ebene geteilt: '
         't = w0/(w0−w1) aus dem linearen Verlauf der Distanz, E teilt '
         'im gleichen Verhältnis.'],
        ['Zwei Ströme', 'LOWER und UPPER bekommen je eine eigene Datei mit '
         'eigenem E-Basiswert; Nicht-Bewegungszeilen (Temperaturen, '
         'PRINT_END) gehen in beide.'],
        ['Platzierung', 'LOWER bleibt stehen. UPPER wird zentriert und auf '
         'die erste Schichthöhe gesetzt — oder mit Reorient so gedreht, '
         'dass die Schnittfläche flach auf dem Bett liegt.'],
        ['BOTH (R224)', 'Zwei separate Dateien (Lower + Upper), jede druckt '
         'eigenständig — die 100%-Flow-Baseline startet mit ihnen neu.'],
    ], [38*mm, 138*mm]))
    A(Spacer(1, 4*mm))

    # ------------------------------------------------------------ 1 Idee --
    flow.extend(H1('1 · Idee und Überblick'))
    A(P('Viele Drucke sind zu hoch für den Bauraum, brauchen einen abnehmbaren '
        'Deckel, oder ein Teil soll nachträglich repariert werden. Cut &amp; '
        'Split löst das auf G-Code-Ebene: <b>kein Neu-Slicen, kein '
        'Re-Parameterisieren</b> — die bestehende Druckdatei wird an einer '
        'Ebene in zwei Hälften geteilt, und beide Hälften sind sofort '
        'druckbar (R177, Wunschliste .130).'))
    A(P('Die R224-Feldrunde hat two Dinge geschärft: <b>Yaw ist gestrichen</b> '
        '(die Drehung um Z gab nur an, wohin die Neigung zeigt — Pitch und '
        'Roll sagen das allein; der Watcher erzwingt Yaw = 0), und '
        '<b>BOTH liefert jetzt zwei separate Dateien</b> (Lower &amp; '
        'Upper), jede mit vollständigem Header und eigenständigem '
        'Extrusions-Zähler — kein gemeinsamer E-Basiswert mehr, der beim '
        'zweiten Druck ins Leere läuft.'))
    A(P('Das Werkzeug arbeitet rein auf Bewegungsgeometrie: Positionen, '
        'Extrusion, Vorschub. <b>Was keine Bewegung ist</b> — Header, '
        'Temperaturbefehle, ;TYPE-Marker, PRINT_END — <b>geht unverändert '
        'in beide Dateien</b>.'))
    A(fig_plane(10.0, 6.0))
    A(CAP('Seitenansicht (X/Z): die geneigte Ebene durchschneidet das Objekt. '
          'Die Normale n zeigt zur UPPER-Seite (grün); LOWER (rot) bleibt '
          'stehen. Pitch = +10°, Ebenenhöhe 6 mm am Bettzentrum.'))

    # ---------------------------------------------------- 2 Schnittebene --
    flow.extend(H1('2 · Die Schnittebene'))
    A(P('Die Ebene wird durch ihre <b>Normale</b> und einen <b>Punkt</b> '
        'beschrieben. Die Normale entsteht aus der Grundrichtung (0,0,1) '
        'durch die drei Klipper-üblichen Rotationen:'))
    A(CODE('n = Rz(yaw) · Ry(pitch) · Rx(roll) · (0, 0, 1)'))
    A(P('mit dem Anchor-Punkt p0 = (Bettmitte-X, Bettmitte-Y, Z-Höhe). '
        'Da Yaw seit R224 stets 0 ist, vereinfacht sich die Normale zu '
        '(übrig bleibt die reine Pitch/Roll-Neigung):'))
    A(CODE('n = ( sin(pitch)·cos(roll),  −sin(roll),  cos(pitch)·cos(roll) )'))
    A(P('Für das Beispiel dieser Dokumentation (Pitch = 10°, Roll = 0°) '
        'berechnet das Werkzeug mit exakt dieser Formel:'))
    A(CODE('n = (%.4f, %.4f, %.4f)' % (nvec[0], nvec[1], nvec[2])))
    A(P('Jeder Punkt P = (x, y, z) bekommt eine <b>signierte Distanz</b> '
        'zur Ebene:'))
    A(CODE('w(P) = n · (P − p0) = n_x·(x−p0_x) + n_y·(y−p0_y) + n_z·(z−p0_z)'))
    flow.extend(B('<b>w &gt; 0</b>: Punkt liegt auf der UPPER-Seite (dorthin zeigt die Normale),',
        '<b>w &lt; 0</b>: LOWER-Seite,',
        '<b>w = 0</b>: Punkt liegt AUF der Ebene (zählt zu UPPER, w ≥ 0).'))
    A(P('Wichtig: w ist <b>nicht</b> der euklidische Abstand (der wäre '
        '|w| · |n|), sondern das skalierte Vorzeichen-Maß. Für das Teilen '
        'ist das egal — es geht nur um das Vorzeichen und den '
        'Durchstichpunkt, und beide skalieren linear mit. Die LCD-Eingabe '
        'rundet alle Winkel auf das 0,5°-Raster (round(v·2)/2), genau wie '
        'das Werkzeug selbst.'))

    # ----------------------------------------------------- 3 Algorithmus --
    flow.extend(H1('3 · Der Algorithmus'))
    flow.extend(H2('3.1 Erster Durchlauf: Bounding-Boxen und Plausibilität'))
    A(P('Pass 1 liest die Datei einmal komplett und sammelt die Bounding-Box '
        'von (a) allem, (b) allen UPPER-Punkten (w ≥ 0), (c) allen '
        'LOWER-Punkten. Bögen (G2/G3) werden vorher in 0,35-mm-Sehnen '
        'zerlegt — dieselbe Abflachung, die auch das Textur- und das '
        'Scale-Werkzeug verwenden, eine gemeinsame Wahrheit. Daraus '
        'erwachsen die drei Härtefehler: keine X/Y-Bewegung, Ebene '
        'komplett unter dem Objekt (kein UPPER), Ebene komplett darüber '
        '(kein LOWER).'))
    flow.extend(H2('3.2 Zweiter Durchlauf: jede Bewegung, drei Fälle'))
    A(P('Pass 2 streamt die Datei nochmals und bewertet <b>jedes Segment</b> '
        'A→B anhand w(A) = w0 und w(B) = w1:'))
    flow.extend(B('w0 ≥ 0 und w1 ≥ 0 → komplett nach UPPER,',
        'w0 &lt; 0 und w1 &lt; 0 → komplett nach LOWER,',
        'Vorzeichenwechsel → das Segment wird GENAU an der Ebene geteilt.'))
    A(P('Im dritten Fall liefert der lineare Verlauf von w auf dem Segment '
        '(G1-Bewegungen sind geradlinig, also ist der Parameteranteil '
        'zugleich der Längenanteil) den Durchstichpunkt:'))
    A(CODE('t = w0 / (w0 − w1)\n'
           'S = A + t · (B − A)\n'
           'E_UPPER = ΔE · (1 − t)   bzw. nach Seite: der A-nächste Teil\n'
           'E_LOWER = ΔE · t'))
    A(fig_split())
    A(CAP('Der Vorzeichenwechsel: das Segment A→B kreuzt die Ebene. Der '
          'Schnittpunkt S liegt bei Parameter t; die Extrusion ΔE teilt '
          'im selben Verhältnis (Längenanteil = Parameteranteil auf '
          'geraden Segmenten).'))
    A(P('Startet das Segment auf der LOWER-Seite (w0 &lt; 0), gehört der '
        'A-nahe Teil (Länge t) zu LOWER und der B-nahe Teil (1−t) zu '
        'UPPER — umgekehrt entsprechend. Beide Teilstrecken behalten '
        'ihren Vorschub F.'))
    flow.extend(H2('3.3 Zwei Ströme mit Positions-Gedächtnis'))
    A(P('Jeder Ausgabestrom merkt sich seine letzte Position (up_pos, '
        'lo_pos). Springt der Eingang über die Ebene (ein Travel, der von '
        'der oberen in die untere Region führt), schreibt der Ziel-Strom '
        'ein <b>explizites G0</b> an die neue Startposition — es entstehen '
        'keine Fantasie-Wege und keine gesliceerten Sprünge. Die '
        'Extrusion wird pro Strom absolut weitergezählt (e_up, e_lo): die '
        'beiden Dateien starten bei 0 (bzw. beim letzten G92-E-Wert) und '
        'sind dadurch <b>jeweils eigenständig druckbar</b> — genau das '
        'ist die R224-BOTH-Semantik. G92 E… synchronisiert beide Zähler, '
        'M83/M82 (relativ/absolut) wird in beide Dateien durchgereicht.'))
    flow.extend(H2('3.4 Was die Ebene NICHT berührt'))
    flow.extend(B('Kopfzeilen, ;TYPE:-Marker, EXCLUDE_OBJECT, APPLY_TYPE/LAYER_MARK,',
        'Temperatur- und Lüfterbefehle, PRINT_START/PRINT_END,',
        'alles, was keine X/Y/Z-Bewegung trägt: <b>byte-identisch in beide '
        'Dateien</b>.'))

    # ---------------------------------------------------- 4 Platzierung --
    flow.extend(H1('4 · Die Platzierung der Hälften'))
    A(P('<b>LOWER bleibt, wo es ist</b> — die Hälfte steht ohnehin auf dem '
        'Bett, keine Koordinate ändert sich.'))
    A(P('<b>UPPER</b> wird verschoben: der tiefste Punkt der (ggf. '
        'gedrehten) Hälfte landet auf der <b>eigenen ersten Schichthöhe '
        'der Datei</b> (z_first = max(min_Z, 0) — nicht stur auf 0,2 mm), '
        'und die Hälfte wird auf dem Bett zentriert.'))
    flow.extend(H2('4.1 Reorient: die Schnittfläche flach aufs Bett'))
    A(P('Ohne Reorient behält die obere Hälfte ihre Orientierung — sie '
        'steht dann auf dem Schnitt-Rand, was bei dünnen Deckeln wackelig '
        'werden kann. Mit <b>Reorient = ON</b> wird die Hälfte so gedreht, '
        'dass die Schnittflächennormale auf −Z zeigt (die Schnittfläche '
        'liegt flach auf dem Bett — die natürliche Art, ein Oberteil zu '
        'drucken). Die Drehung ist eine Rodrigues-Rotation um die Achse'))
    A(CODE('achse = n × (0, 0, −1)   (normiert)\n'
           "v' = v·cos θ + (achse × v)·sin θ + achse·(achse·v)·(1 − cos θ)"))
    A(P('mit θ als Winkel zwischen n und (0,0,−1). Danach werden '
        'Zentrierung und Absenkung wie oben angewendet. Vor dem Schreiben '
        'prüft das Werkzeug die transformierte Grundfläche gegen das '
        'Bettmaß — zu groß heißt eine klare Fehlermeldung mit beiden '
        'Zahlen, kein Clippen ins Nirgendwo.'))

    # ------------------------------------------------- 5 Durchrechnung --
    flow.extend(H1('5 · Durchgerechnet: ein echter Lauf'))
    A(P('Die folgende Tabelle stammt aus einem <b>echten Lauf</b> des '
        'Werkzeugs auf einer synthetischen Probendatei (Zylinder, 30 '
        'Schichten, 24 Segmente pro Wand) mit Pitch = 10°, Roll = 0°, '
        'Ebenenhöhe 6 mm, PART = BOTH, Reorient = ON. Nichts davon ist '
        'handgerechnet: Normale, Segmentzahlen und der Durchstichpunkt '
        'liest das PDF aus dem Lauf aus.'))
    A(TBL(['Größe', 'Wert'], [
        ['Normale n (Pitch 10°, Roll 0°)',
         '(%.4f, %.4f, %.4f)' % (nvec[0], nvec[1], nvec[2])],
        ['Erste Schichthöhe z_first', '%.3f mm' % info['first_layer_z']],
        ['Segmente UPPER', '%d' % info['segments_upper']],
        ['Segmente LOWER', '%d' % info['segments_lower']],
        ['UPPER-Abmessungen (X/Y/Z)', '%.1f × %.1f × %.1f mm'
         % info['upper_size']],
        ['LOWER-Abmessungen (X/Y/Z)', '%.1f × %.1f × %.1f mm'
         % info['lower_size']],
        ['Ausgabedateien', ', '.join(info['file'])],
    ], [75*mm, 101*mm]))
    A(Spacer(1, 3*mm))
    if ex:
        A(P('Ein kreuzendes Segment aus diesem Lauf (Schichtwand, Start A, '
            'Ziel B):'))
        A(TBL(['Größe', 'Wert'], [
            ['A (x, y, z)', '(%.3f, %.3f, %.3f) mm' % (ex['x0'], ex['y0'], ex['z0'])],
            ['B (x, y, z)', '(%.3f, %.3f, %.3f) mm' % (ex['x1'], ex['y1'], ex['z1'])],
            ['w(A) = w0', '%.4f mm' % ex['w0']],
            ['w(B) = w1', '%.4f mm' % ex['w1']],
            ['t = w0/(w0−w1)', '%.4f' % ex['t']],
            ['S = A + t·(B−A)', '(%.3f, %.3f)' % (ex['sx'], ex['sy'])],
            ['ΔE des Segments', '%.5f' % ex['de']],
            ['E-Anteil A→S (t)', '%.5f' % (ex['de'] * ex['t'])],
            ['E-Anteil S→B (1−t)', '%.5f' % (ex['de'] * (1 - ex['t']))],
        ], [75*mm, 101*mm]))
    A(Spacer(1, 3*mm))
    A(P('Zur Kontrolle: die aufsummierten E-Anteile ergeben exakt ΔE, und '
        'S liegt mit w(S) = 0 exakt auf der Ebene — beides folgt direkt '
        'aus der Linearität von w auf dem Segment.'))

    # ------------------------------------------------------ 6 Fehler ----
    flow.extend(H1('6 · Fehlermeldungen (alles ValueErrors)'))
    A(TBL(['Meldung (Kern)', 'Bedeutung / Abhilfe'], [
        ['a plane at z=0 with no tilt cuts nothing',
         'Alle Winkel 0 UND Z-Höhe 0: die Ebene ist das Bett selbst. '
         'Winkel oder Höhe setzen.'],
        ['the plane is below the whole object',
         'Kein Punkt hat w ≥ 0 — es gibt kein UPPER. Z-Höhe erhöhen oder '
         'entgegen neigen.'],
        ['the plane is above the whole object',
         'Kein Punkt hat w &lt; 0 — es gibt kein LOWER. Z-Höhe senken.'],
        ['no moves with X/Y',
         'Die Datei trägt keine X/Y-Geometrie (z. B. nur Aufheizzyklen) — '
         'nichts zu schneiden.'],
        ['the UPPER part needs X × Y mm … the bed has …',
         'Die (ggf. gedrehte) obere Hälfte ist breiter als das Bett. '
         'Ohne Reorient versuchen oder an anderer Stelle schneiden.'],
        ['angles: yaw −180..180, pitch/roll −90..90',
         'Winkel außerhalb des Bereichs (oder nicht im 0,5°-Raster '
         'möglich).'],
    ], [75*mm, 101*mm]))

    # -------------------------------------------------- 7 Arbeitsablauf --
    flow.extend(H1('7 · Arbeitsablauf am LCD'))
    flow.extend(B('Datei wie immer auswählen (Dateiliste — die Auswahl ist das Ziel),',
        'Pre-Print &gt; Mods &gt; Cut &amp; Split: <b>Pitch</b> (−90..90, '
        '0,5°-Schritte, Vorne/Hinten-Neigung), <b>Roll</b> (−90..90, '
        'links/rechts), <b>Z plane</b> (Höhe der Ebene am Bettzentrum), '
        '<b>Part</b> (UPPER / LOWER / BOTH = 2 Dateien), <b>Reorient</b> '
        '(ON: Schnittfläche flach aufs Bett),',
        '<b>&gt; Cut now</b> — zweimal drücken (Bestätigungs-Disziplin '
        'wie bei jedem Generator), der Watcher schneidet im Hintergrund,',
        'die Hälften landen als &lt;name&gt;_CUT-L.gcode und '
        '&lt;name&gt;_CUT-U.gcode im Cake-Ordner (Zähler bei Kollision),',
        'BOTH: <b>zwei separate Drucke</b> — jede Hälfte druckt '
        'eigenständig, die 100%-Flow-Baseline startet mit ihnen neu; '
        'danach kleben/verschweißen.',
        '„How does it cut?“ zeigt die Kurzform dieser Methodik auf dem '
        'Display.'))
    A(Spacer(1, 3*mm))
    A(P('Kombination mit anderen Werkzeugen: Eine Cake-Hälfte mit '
        'Z-Offset kann per <b>Range</b> (Schichtfenster, bottom/top '
        'zählen INSIDE) weiter zerlegt werden; die Kette Cake → Range '
        'erkennt das System und reiht sie sauber hintereinander.'))

    # ------------------------------------------------------- 8 Genauigk. --
    flow.extend(H1('8 · Genauigkeit und Grenzen'))
    flow.extend(B('Positionen werden auf %.3f mm, E auf %.5f gerundet — die '
        'Split-Punkte selbst sind exakt (t aus der Ebene, nicht gesucht '
        'oder genähert).' % (0.001, 0.00001),
        'E teilt LINEAR nach Längenanteil — auf geraden G1-Segmenten '
        'exakt; Bögen werden vorher in 0,35-mm-Sehnen zerlegt, jede '
        'Sehne trägt ihren exakten E-Anteil (die Summe pro Bogen bleibt).',
        'Die Schnittfläche ist eine exakte Ebene — gekrümmte Schnitte '
        '(Zylinder-, Kugelschnitte) sind nicht Gegenstand des Werkzeugs.',
        'Stacking: Die beiden Hälften passen an der Schnittkante '
        'werkstoffbedingt nur näherungsweise zusammen (Linienbreite, '
        'Überschuss); für passgenaue Verbindungen Fügegeometrie im '
        'CAD vorsehen.',
        'Alles, was keine Bewegung ist, bleibt byte-identisch — auch '
        'der Datei-Header, nur die Cut-Zeilen kommen dazu.'))

    A(Spacer(1, 8*mm))
    A(Paragraph('Ende · R2-D2 Cut &amp; Split · Stand .136x (R226)', S['end']))

    out = os.path.join(os.path.dirname(os.path.dirname(
        os.path.abspath(__file__))), 'CUTSPLIT.pdf')
    Doc(out).build(flow)
    print('written %s (%d bytes)' % (out, os.path.getsize(out)))


if __name__ == '__main__':
    main()
