#!/usr/bin/env python3
"""r2_pdf_kit.py — gemeinsames Handwerkszeug für alle R2-D2-PDFs.

Warum eine eigene Datei: bisher hatte jeder PDF-Bauer seine eigenen Farben,
eigenen Stil-Tabellen und eigene Seiten-Dekorationen. Mit sechs neuen PDFs
wird das zur Fehlerquelle (ein Handbuch sieht anders aus als das nächste).
Hier steht **ein** Satz Stile, **ein** Seitenkopf, **eine** Tabellenfunktion -
und die drei Regeln, die für jedes Dokument gelten:

  1. **Keine Fantasie-Grafiken.** Jede Zahl und jedes Bild kommt aus dem Code:
     aus der Signatur, aus den Grenzwerten (`raise ValueError`), aus dem
     Preset-Speicher der Makros - oder aus einem Beispiel, das WIRKLICH
     gerechnet wurde. `toolpath_fig()` zeichnet den echten Fahrweg einer
     erzeugten Datei, nicht eine Skizze davon.
  2. **Rechtschreibung im Bild.** Alle Beschriftungen laufen über
     `label()`/`DejaVu`, keine kaputten Umlaute.
  3. **Die Versionszeile kommt aus `r2_version`** - nie getippt.

Benutzung (Muster: tools/make_cakesplit_pdf.py):
    from r2_pdf_kit import Doc, H1, H2, P, B, CODE, CAP, TBL, IMG, ...
    kb = Doc('DATEI.pdf', 'Titel für Kopf und Fuß', 'Untertitel des Deckblatts')
    kb.add_cover(kicker, titel, untertitel, absaetze=[...])
    kb.story += H1('1 Einleitung') + P('...') + TBL([...],[...],[...])
    kb.build()
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (BaseDocTemplate, PageTemplate, Frame,
                                Paragraph, Spacer, Table, TableStyle,
                                CondPageBreak, Image, PageBreak)
from PIL import Image as PILImage, ImageDraw, ImageFont

try:
    from r2_version import VERSION as R2VER
except Exception:                                    # pragma: no cover
    R2VER = 'unbekannt'

# ------------------------------------------------------------------ Schriften
FD = '/usr/share/fonts/truetype/dejavu/'
for _n, _f in (('DVS', 'DejaVuSans.ttf'), ('DVSB', 'DejaVuSans-Bold.ttf'),
               ('DVSI', 'DejaVuSans-Oblique.ttf'),
               ('DVSM', 'DejaVuSansMono.ttf')):
    try:
        pdfmetrics.registerFont(TTFont(_n, FD + _f))
    except Exception:
        pass                                            # fehlende Datei: egal


def font(sz, bold=False, italic=False):
    name = ('DejaVuSans-Bold.ttf' if bold else
            ('DejaVuSans-Oblique.ttf' if italic else 'DejaVuSans.ttf'))
    return ImageFont.truetype(FD + name, sz)


def mono(sz):
    return ImageFont.truetype(FD + 'DejaVuSansMono.ttf', sz)


# --------------------------------------------------------------------- Farben
BLUE = colors.HexColor('#1c4e8c'); LBLUE = colors.HexColor('#e8f0fa')
ORANGE = colors.HexColor('#e07b00'); GRAY = colors.HexColor('#58595b')
LGRAY = colors.HexColor('#f2f2f2'); GREEN = colors.HexColor('#1e7d32')
RED = colors.HexColor('#b3261e'); PURPLE = colors.HexColor('#6a3fb5')
TEAL = colors.HexColor('#00706b')
INK = '#222222'

S = {
    'title': ParagraphStyle('t', fontName='DVSB', fontSize=26, leading=31,
                            textColor=BLUE, alignment=1),
    'kicker': ParagraphStyle('k', fontName='DVSB', fontSize=11, leading=15,
                             textColor=ORANGE, alignment=1),
    'sub': ParagraphStyle('s', fontName='DVS', fontSize=13.5, leading=19,
                          textColor=GRAY, alignment=1),
    'h1': ParagraphStyle('h1', fontName='DVSB', fontSize=19, leading=25,
                         textColor=BLUE, spaceBefore=10, spaceAfter=3,
                         keepWithNext=1),
    'h2': ParagraphStyle('h2', fontName='DVSB', fontSize=14, leading=20,
                         textColor=BLUE, spaceBefore=13, spaceAfter=6,
                         keepWithNext=1),
    'h3': ParagraphStyle('h3', fontName='DVSB', fontSize=12.2, leading=17,
                         textColor=TEAL, spaceBefore=9, spaceAfter=3,
                         keepWithNext=1),
    'p': ParagraphStyle('p', fontName='DVS', fontSize=11.6, leading=17.4,
                        spaceAfter=6.5, allowWidows=0, allowOrphans=0),
    'b': ParagraphStyle('b', fontName='DVS', fontSize=11.5, leading=16.8,
                        leftIndent=12, bulletIndent=2, spaceAfter=4.4,
                        allowWidows=0, allowOrphans=0),
    'code': ParagraphStyle('c', fontName='DVSM', fontSize=10.2, leading=14.6,
                           backColor=LGRAY, borderPadding=5, leftIndent=4,
                           spaceAfter=7),
    'cap': ParagraphStyle('cap', fontName='DVS', fontSize=10.2, leading=14.4,
                          textColor=GRAY, alignment=1, spaceBefore=3,
                          spaceAfter=8),
    'ts': ParagraphStyle('ts', fontName='DVSB', fontSize=10.0, leading=13.4,
                         textColor=colors.white),
    'tc': ParagraphStyle('tc', fontName='DVS', fontSize=10.0, leading=13.4),
    'tcm': ParagraphStyle('tcm', fontName='DVSM', fontSize=9.4, leading=12.8),
    'note': ParagraphStyle('note', fontName='DVS', fontSize=11.0, leading=16.2),
    'end': ParagraphStyle('end', fontName='DVSB', fontSize=12.5, leading=18,
                          textColor=BLUE, alignment=1),
}


# ------------------------------------------------------------------ Bausteine
def H1(t, nr=None):
    txt = ('%s&nbsp;&nbsp;%s' % (nr, t)) if nr else t
    return [CondPageBreak(58 * mm), Paragraph(txt, S['h1'])]


def H2(t, nr=None):
    txt = ('%s&nbsp;&nbsp;%s' % (nr, t)) if nr else t
    return [CondPageBreak(44 * mm), Paragraph(txt, S['h2'])]


def H3(t):
    return [CondPageBreak(34 * mm), Paragraph(t, S['h3'])]


def P(t):
    return [Paragraph(t, S['p'])]


def B(*items):
    return [Paragraph('•&nbsp;&nbsp;' + i, S['b']) for i in items]


def NUM(*items):
    out = []
    for i, txt in enumerate(items, 1):
        out.append(Paragraph('<b>%d.</b>&nbsp;&nbsp;%s' % (i, txt), S['b']))
    return out


def CODE(t):
    return [Paragraph(t.replace('&', '&amp;').replace('<', '&lt;')
                      .replace('>', '&gt;').replace('\n', '<br/>')
                      .replace(' ', '&nbsp;'), S['code'])]


def CAP(t):
    return [Paragraph(t, S['cap'])]


def SP(h=3):
    return [Spacer(1, h * mm)]


def TBL(headers, rows, widths, mono_cols=(), align_left=True):
    """Tabelle mit Kopfzeile, Zebra-Streifen - und Monospace für Code-Spalten."""
    data = [[Paragraph(str(x), S['ts']) for x in headers]]
    for row in rows:
        data.append([Paragraph(str(c), S['tcm'] if i in mono_cols else S['tc'])
                     for i, c in enumerate(row)])
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
    # Liste zurückgeben, damit `story += TBL(...)` genauso funktioniert wie
    # `story += H1(...)` - zwei Schreibweisen für dieselbe Sache sind eine
    # Fehlerquelle (genau daran ist der erste Lauf dieses Bauers gescheitert).
    return [t]


def BOX(title, lines, kind='note'):
    """Farbiger Kasten: note (blau) / tip (grün) / warn (rot) / why (violett)."""
    col, bg = {'note': (BLUE, colors.HexColor('#eef4fb')),
               'tip': (GREEN, colors.HexColor('#eef7ee')),
               'warn': (RED, colors.HexColor('#fbeeee')),
               'why': (PURPLE, colors.HexColor('#f3eefb')),
               'meas': (TEAL, colors.HexColor('#e8f4f3'))}[kind]
    inner = [Paragraph('<b>%s</b>' % title,
                       ParagraphStyle('bt', parent=S['note'], fontName='DVSB',
                                      textColor=col))]
    for ln in lines:
        inner.append(Paragraph(ln, S['note']))
        inner.append(Spacer(1, 2))
    t = Table([[inner]], colWidths=[162 * mm])
    t.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), bg),
        ('BOX', (0, 0), (-1, -1), 0.7, col),
        ('LINEBEFORE', (0, 0), (0, -1), 3.2, col),
        ('LEFTPADDING', (0, 0), (-1, -1), 8),
        ('RIGHTPADDING', (0, 0), (-1, -1), 8),
        ('TOPPADDING', (0, 0), (-1, -1), 6),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
    ]))
    return t


def IMG(path, width_mm=162):
    from PIL import Image as _I
    w, h = _I.open(path).size
    return Image(path, width=width_mm * mm, height=width_mm * mm * h / w)


def FORMULA(txt, note=''):
    """Mathe-Block: Formel(n) + optionaler Erläuterungssatz darunter."""
    inner = [Paragraph(txt, ParagraphStyle('f', fontName='DVSM', fontSize=11.4,
                                           leading=17, textColor=colors.HexColor(INK)))]
    if note:
        inner.append(Spacer(1, 1.6))
        inner.append(Paragraph(note, ParagraphStyle('fn', fontName='DVS',
                                                    fontSize=10.2, leading=14,
                                                    textColor=GRAY)))
    t = Table([[inner]], colWidths=[162 * mm])
    t.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#f7f9fc')),
        ('BOX', (0, 0), (-1, -1), 0.6, colors.HexColor('#b9c9dd')),
        ('LEFTPADDING', (0, 0), (-1, -1), 9),
        ('TOPPADDING', (0, 0), (-1, -1), 6),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
    ]))
    return [t]


class Doc(BaseDocTemplate):
    """A4-Dokument mit Kopfzeile (Titel links, Version rechts) und Seitenzahl."""

    def __init__(self, filename, kopf, titel='', autor='R2-D2 Macro System',
                 unterschrift=''):
        super().__init__(filename, pagesize=A4,
                         leftMargin=17 * mm, rightMargin=17 * mm,
                         topMargin=16 * mm, bottomMargin=15 * mm,
                         title=titel or kopf, author=autor)
        self.kopf = kopf
        f = Frame(self.leftMargin, self.bottomMargin, self.width, self.height,
                  id='f')
        self.addPageTemplates([PageTemplate(id='pt', frames=[f],
                                            onPage=self._deco)])
        self.story = []
        self._toc = []

    # ---------------------------------------------------------- Dekoration
    def _deco(self, canv, doc):
        canv.saveState()
        canv.setStrokeColor(BLUE)
        canv.setLineWidth(0.7)
        canv.line(17 * mm, 286 * mm, 193 * mm, 286 * mm)
        canv.setFont('DVS', 8.2)
        canv.setFillColor(GRAY)
        canv.drawString(17 * mm, 287.8 * mm, self.kopf)
        canv.drawRightString(193 * mm, 287.8 * mm, R2VER)
        canv.setStrokeColor(colors.HexColor('#c9d6e6'))
        canv.setLineWidth(0.5)
        canv.line(17 * mm, 13 * mm, 193 * mm, 13 * mm)
        canv.setFont('DVS', 8.4)
        canv.setFillColor(GRAY)
        canv.drawCentredString(105 * mm, 9.2 * mm, 'Seite %d' % doc.page)
        canv.drawString(17 * mm, 9.2 * mm, 'R2-D2 · Ender-3')
        canv.restoreState()

    # -------------------------------------------------------------- Deckblatt
    def add_cover(self, kicker, titel, untertitel, absaetze=(), tabelle=None,
                  farbe=BLUE):
        st = self.story
        st.append(Spacer(1, 26 * mm))
        st.append(Paragraph(kicker, S['kicker']))
        st.append(Spacer(1, 4 * mm))
        st.append(Paragraph(titel, S['title']))
        st.append(Spacer(1, 4 * mm))
        st.append(Paragraph(untertitel, S['sub']))
        st.append(Spacer(1, 7 * mm))
        if absaetze:
            box = []
            for a in absaetze:
                if box:
                    box.append(Spacer(1, 4 * mm))     # Absätze trennen, nicht stapeln
                box.append(Paragraph(a, ParagraphStyle('cv', fontName='DVS',
                                                       fontSize=11.4, leading=17)))
            t = Table([[box]], colWidths=[162 * mm])
            t.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#f7f9fc')),
                ('BOX', (0, 0), (-1, -1), 0.8, farbe),
                ('LEFTPADDING', (0, 0), (-1, -1), 10),
                ('RIGHTPADDING', (0, 0), (-1, -1), 10),
                ('TOPPADDING', (0, 0), (-1, -1), 8),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
            ]))
            st.append(t)
        if tabelle:
            st.append(Spacer(1, 6 * mm))
            st.append(tabelle)
        st.append(PageBreak())

    # ------------------------------------------------------------- Inhaltsv.
    def add_toc(self, eintraege, titel='Inhalt'):
        st = self.story
        st.append(Paragraph(titel, S['h1']))
        st.append(Spacer(1, 2 * mm))
        rows = []
        for nr, txt, seite in eintraege:
            rows.append([nr, txt, str(seite)])
        t = Table([[Paragraph(a, S['tc']) for a in r] for r in rows],
                  colWidths=[16 * mm, 138 * mm, 8 * mm])
        t.setStyle(TableStyle([
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('LEFTPADDING', (0, 0), (-1, -1), 2),
            ('TOPPADDING', (0, 0), (-1, -1), 2.5),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 2.5),
            ('LINEBELOW', (0, 0), (-1, -1), 0.25,
             colors.HexColor('#dde5ef')),
        ]))
        st.append(t)
        st.append(PageBreak())

    def render(self):
        """Baut das PDF. ACHTUNG: 'build' ist bei BaseDocTemplate schon
        vergeben (build(story)) - deshalb heisst die Methode hier render()."""
        self.build(self.story)


# ------------------------------------------------------------- Figuren-Helfer
def toolpath_fig(gcode_path, out_png, titel='', max_moves=60000,
                 width_px=1100, height_px=560, bed=(0, 0, 235, 235)):
    """Zeichnet den ECHTEN XY-Fahrweg einer erzeugten G-Code-Datei.

    Keine Skizze: gelesen werden G0/G1-Zeilen mit X/Y, aufgeteilt in
    Extrusion (dunkel) und Leerfahrt (hell). Damit sieht man am Bild, was der
    Generator wirklich aufs Bett legt.
    """
    x0, y0, x1, y1 = bed
    im = PILImage.new('RGB', (width_px, height_px), 'white')
    d = ImageDraw.Draw(im)
    pad = 34
    sx = (width_px - 2 * pad) / float(x1 - x0)
    sy = (height_px - 2 * pad) / float(y1 - y0)
    sc = min(sx, sy)

    def px(x, y):
        return (pad + (x - x0) * sc, height_px - pad - (y - y0) * sc)

    # Bettrahmen + Gitter (PIL will zwei Ecken in aufsteigender Ordnung:
    # die y-Achse ist hier gespiegelt, deshalb min/max statt Ecke/Ecke)
    _a = px(x0, y0)
    _b = px(x1, y1)
    d.rectangle([min(_a[0], _b[0]), min(_a[1], _b[1]),
                 max(_a[0], _b[0]), max(_a[1], _b[1])], outline='#c9d6e6')
    for g in range(50, int(x1), 50):
        d.line([px(g, y0), px(g, y1)], fill='#eef2f7')
        d.line([px(x0, g), px(x1, g)], fill='#eef2f7')
    n_move = n_ext = 0
    cur = None
    with open(gcode_path, errors='replace') as fh:
        for line in fh:
            s = line.split(';', 1)[0].strip()
            if not (s.startswith('G1 ') or s.startswith('G0 ')):
                continue
            kv = {}
            for tok in s.split()[1:]:
                if tok[:1] in 'XYZE':
                    try:
                        kv[tok[0]] = float(tok[1:])
                    except ValueError:
                        pass
            if 'X' not in kv or 'Y' not in kv:
                continue
            nxt = (kv['X'], kv['Y'])
            if cur is not None:
                ext = kv.get('E', 0) > 0
                if ext:
                    n_ext += 1
                    d.line([px(*cur), px(*nxt)], fill='#1c4e8c')
                else:
                    n_move += 1
                    if n_move < max_moves // 3:
                        d.line([px(*cur), px(*nxt)], fill='#cfd8e3')
            cur = nxt
            if n_ext + n_move > max_moves:
                break
    # Maßstab
    d.line([pad, height_px - 18, pad + 20 * sc, height_px - 18], fill='#58595b', width=2)
    d.text((pad + 3, height_px - 34), '20 mm', font=font(13), fill='#58595b')
    if titel:
        d.text((pad, 8), titel, font=font(17, bold=True), fill='#1c4e8c')
    d.text((width_px - 330, height_px - 30),
           'dunkel = Extrusion (%d) · hell = Leerfahrt (%d)' % (n_ext, n_move),
           font=font(12), fill='#58595b')
    im.save(out_png)
    return out_png


def bar_fig(rows, out_png, titel='', einheit='', width_px=1000, row_h=30,
            farbe='#1c4e8c'):
    """Balkenbild aus echten Zahlen: rows = [(Label, Wert), ...]."""
    h = 60 + row_h * len(rows) + 30
    im = PILImage.new('RGB', (width_px, h), 'white')
    d = ImageDraw.Draw(im)
    d.text((30, 16), titel, font=font(17, bold=True), fill='#1c4e8c')
    vmax = max([abs(v) for _, v in rows] or [1]) or 1
    for i, (lab, v) in enumerate(rows):
        yy = 56 + i * row_h
        d.text((30, yy + 4), str(lab), font=font(13), fill='#222222')
        w = int((width_px - 320) * abs(v) / vmax)
        d.rectangle([250, yy + 2, 250 + max(2, w), yy + row_h - 8], fill=farbe)
        d.text((256 + max(2, w), yy + 4), ('%g %s' % (v, einheit)).strip(),
               font=font(12), fill='#58595b')
    im.save(out_png)
    return out_png


def ladder_fig(steps, out_png, titel='', width_px=1000):
    """Treppenbild für Reihenfolgen: steps = [(Nr, Titel, Unterzeile), ...]."""
    row_h = 44
    h = 70 + row_h * len(steps)
    im = PILImage.new('RGB', (width_px, h), 'white')
    d = ImageDraw.Draw(im)
    d.text((30, 18), titel, font=font(17, bold=True), fill='#1c4e8c')
    for i, (nr, t, u) in enumerate(steps):
        yy = 58 + i * row_h
        x = 40 + i * 14
        d.rectangle([x, yy, width_px - 60 - i * 6, yy + row_h - 8],
                    fill='#e8f0fa' if i % 2 == 0 else '#f7f9fc',
                    outline='#1c4e8c')
        d.text((x + 10, yy + 5), '%s  %s' % (nr, t), font=font(14, bold=True),
               fill='#1c4e8c')
        d.text((x + 10, yy + 22), u, font=font(12), fill='#58595b')
        if i < len(steps) - 1:
            d.line([x + 20, yy + row_h - 8, x + 34, yy + row_h],
                   fill='#1c4e8c', width=2)
    im.save(out_png)
    return out_png
