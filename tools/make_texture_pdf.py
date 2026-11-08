#!/usr/bin/env python3
"""TEXTURING.pdf — the documentation of the R2-D2 texture tool (user
request, .136m round): how the wall displacement works, the EXACT mapping
of every setting, all 21 patterns with previews sampled from the REAL
pattern functions (tools/r2_texture.py _build_patterns - not redrawn,
the images ARE the code output), and the 44 library presets listed per
pattern.

Content basis: tools/r2_texture.py (_build_patterns, apply_texture,
pattern() cylinder mapping, fuzzy disc), macros/17_generator.cfg
(_GEN_PRESET + variable_texture_lib - the preset values are READ from
the config, one truth), macros/12_maintenance.cfg (TEXTURE_APPLY),
menus/lcd_menues.cfg (Pre-Print > Mods > Texture).
"""
import ast
import math
import os
import re
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
                                PageBreak, CondPageBreak, KeepTogether)
from reportlab.platypus.flowables import Flowable, Image
from reportlab.lib.utils import ImageReader
from PIL import Image as PILImage, ImageDraw, ImageFont

# ---------------------------------------------------------------- fonts ----
FD = '/usr/share/fonts/truetype/dejavu/'
pdfmetrics.registerFont(TTFont('DVS', FD + 'DejaVuSans.ttf'))
pdfmetrics.registerFont(TTFont('DVSB', FD + 'DejaVuSans-Bold.ttf'))


def _tfont(sz, bold=False):
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
                         title='R2-D2 Texturing — Struktur-Prägung auf der Objektwand',
                         author='R2-D2 Macro System')
        f = Frame(self.leftMargin, self.bottomMargin, self.width, self.height, id='f')
        self.addPageTemplates([PageTemplate(id='pt', frames=[f], onPage=self._deco)])

    def _deco(self, canv, doc):
        canv.saveState()
        canv.setStrokeColor(BLUE); canv.setLineWidth(0.7)
        canv.line(17*mm, 285*mm, 193*mm, 285*mm)
        canv.setFont('DVS', 8.2); canv.setFillColor(GRAY)
        canv.drawString(17*mm, 287.2*mm, 'R2-D2 Macro System · Texturing — Struktur-Prägung auf der Objektwand')
        canv.drawRightString(193*mm, 287.2*mm, 'R2-2026-11-08.136w')
        canv.setFont('DVS', 8.6)
        canv.drawCentredString(105*mm, 9.5*mm, 'Seite %d' % doc.page)
        canv.restoreState()


# ------------------------------------------------- the REAL pattern code ---
import r2_texture

# the 44 library presets, read from the ONE truth (macros/17_generator.cfg)
_here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_cfg = open(os.path.join(_here, 'macros', '17_generator.cfg'),
            encoding='utf-8').read()
_m = re.search(r'^variable_texture_lib: (.+)$', _cfg, re.M)
LIB = ast.literal_eval(_m.group(1))

EXAMPLE_R = 30.0      # preview object: cylinder radius 30mm ...
EXAMPLE_H = 60.0      # ... and 60mm tall (stated in every caption)
CIRC = 2.0 * math.pi * EXAMPLE_R

def k_n_for(preset):
    """the exact k/n computation from apply_texture for the preset values"""
    k = max(1, min(240, int(round(CIRC / float(preset['texture_scale'])))))
    n = max(1, min(400, int(round(EXAMPLE_H / float(preset['texture_zsize'])))))
    return k, n

def _map_img():
    """a demo image for the MAP pattern (gradient + ring + lettering)"""
    im = PILImage.new('L', (220, 150), 128)
    dr = ImageDraw.Draw(im)
    for x in range(220):
        dr.line([(x, 0), (x, 150)], fill=int(70 + 120 * x / 220.0))
    for r in range(56, 20, -4):
        dr.ellipse([110 - r, 80 - r, 110 + r, 80 + r],
                   outline=int(30 + r * 2))
    try:
        fnt = ImageFont.truetype(FD + 'DejaVuSans-Bold.ttf', 40)
        dr.text((58, 96), 'R2', fill=240, font=fnt)
    except Exception:                                   # noqa: BLE001
        dr.text((70, 100), 'R2', fill=240)
    return im

def render_pattern(name, preset):
    """sample the REAL _build_patterns function of this preset into a
    shaded preview (light from top-left, dark = deep, bright = raised)"""
    k, n = k_n_for(preset)
    img = _map_img() if name == 'MAP' else None
    pats = r2_texture._build_patterns(k, n, int(preset['texture_seed']), img)
    fn = pats[name]
    W, H = 330, 220
    hm = [[0.0] * W for _ in range(H)]
    for py in range(H):
        t = 1.0 - py / float(H - 1)          # image top = pattern top
        for px in range(W):
            s = px / float(W - 1)
            hm[py][px] = max(-1.0, min(1.0, fn(s, t)))
    im = PILImage.new('L', (W, H))
    px_ = im.load()
    for y in range(H):
        for x in range(W):
            v = hm[y][x]
            # relief shading: base gray from the height, slope light
            dx = (hm[y][min(W - 1, x + 1)] - hm[y][max(0, x - 1)]) * 0.5
            dy = (hm[min(H - 1, y + 1)][x] - hm[max(0, y - 1)][x]) * 0.5
            g = 0.52 + 0.42 * v + 0.55 * dx + 0.55 * dy
            px_[x, y] = max(0, min(255, int(g * 255.0)))
    return im

def pat_img(name, preset, width_mm=118):
    import io
    im = render_pattern(name, preset)
    buf = io.BytesIO()
    im.save(buf, format='PNG')
    buf.seek(0)
    aspect = im.size[1] / float(im.size[0])
    img = Image(buf, width=width_mm * mm, height=width_mm * mm * aspect)
    img.hAlign = 'CENTER'
    return img


# ----------------------------------------------------- pattern texts ------
PAT_TXT = {
 'RIDGES': 'Vertikale Rippen um den Umfang, deren Tiefe sanft mit der Höhe '
   'atmet (zwei Wellen über die Objekthöhe). <b>k</b> Rippen exakt verteilt, '
   'nahtlos am Umfang. Der Klassiker für Lampenschirme und Vasen.',
 'WAVES': 'Schräge Wellen: Sinus über (s·k + t·n) - die Wellen laufen spiralförmig '
   'um das Objekt, überlagert von einer breiten Grundwelle in Z. Organisch, '
   'wie Wasser am Zylinder.',
 'GRID': 'Kreuzgitter: Sinus in s × Sinus in t - erhabene Kreuzpunkte mit '
   'tiefen Feldern dazwischen. Regelmäßige Polster-Optik.',
 'HATCH': 'Diagonale Schraffur (Dreieckwelle, weich geklemmt), Richtung k/n - '
   'Strichbündel in einer Ebene, leicht moduliert über die Höhe.',
 'CHECKER': 'Weichkantiges Schachbrett: 2k × 2n Zellen, Parität entscheidet '
   'hoch/tief, Kanten per Smoothstep in BEIDEN Achsen (druckbar - keine '
   'harten Stufen). Der Umfangs-Versatz trifft genau eine Zellgrenze.',
 'HEX': 'Überlagerte Sinusse in s und t (t mit Kosinus-Versatz) - ein '
   'fließendes, wabenartiges Moiré ohne harte Kanten.',
 'HONEYCOMB': 'Echtes Sechseck-Gitter auf der abgewickelten Ebene: Zeilen um '
   'eine halbe Zelle versetzt, Kantendistanz über drei Achsen, außen erhaben, '
   'innen tief. Nahtlos, weil k und die Zeilenzahl ganzzahlig sind.',
 'BASKET': 'Geflochtenes Muster: Zellparität (Zelle in s + Zelle in t) '
   'entscheidet über/unter, Kanten ausgeprägt - Korboptik mit sichtbarem '
   'Kreuz der Latten.',
 'ROPE': 'Gedrehtes Seil: strands = max(2, k/2) Stränge, twist = n Umläufe '
   'über die Höhe. Der Betrag-Lifting (|v|^0.6) macht runde, wulstige Stränge.',
 'PLANKS': 'Bretter: n Reihen, je Reihe ein geseedeter Versatz der '
   'Stoßfugen (Stagger), Brettkontur mit weichem Rand, Fugen tief, plus '
   'feine Maserung (Noise).',
 'BRICKS': 'Ziegel: 2n Reihen, gerader und versetzter Verband im Wechsel, '
   'Steinfläche erhaben, Fugen tief, plus raue Noise-Textur pro Stein.',
 'SANDSTONE': 'Geschichteter Sandstein: zwei überlagerte, geseedete Noise-'
   'Bänder (grob k×n + fein 5k×5n). Körnig, mineralisch, reproduzierbar '
   '(gleicher Seed = gleiches Bild).',
 'CONCRETE': 'Sichtbeton: Grundrauschen plus Poren-Noise - Werte über 0.86 '
   'stanzen Löcher in die Fläche (Auswaschungen).',
 'CLAY': 'Handgeformte Tonerde: drei breite, weiche Dellen (Gauß-Kreise) auf '
   'dem periodischen Gitter - die Dellen schließen über die Naht, plus '
   'Grundversatz.',
 'CREPE': 'Crepe-Papier: feines Noise (4k×4n), amplitude moduliert mit der '
   'Diagonalwelle - körniger Griff mit Richtung.',
 'FABRIC': 'Gewebe: Sinus hoch 3 (scharfkantige Rillen) in s, plus 15 % '
   'Noise-Aufrauung - Leinen-/Köperstruktur in Umfangsrichtung.',
 'PLUSH': 'Plüsch: feines, hochfrequentes Noise (5k×5n, mindestens 6) um den '
   'Neutralpunkt 0.42 - dichtes, kurzfloriges Pelz-Muster.',
 'HILBERT': 'Raumfüllende Zickzack-Bänder: Dreieckwelle in s, pro Reihe um '
   'eine halbe Periode versetzt, amplitude zur Bandmitte hin betont - '
   'Labyrinth-/Mäanderoptik.',
 'SCRATCH': 'Anisotrope Kratzer: gestrecktes grobes Noise quer + feines '
   'Noise längs (k/2 × 4n und 2k × 6n) - gebürstetes, verkratztes Metall.',
 'GLITCH': 'Digitale Fehler: pro Band (Zeile) ein geseedeter KONSTANTER '
   'Versatz - ganze Schichten stehen versetzt („geschmolzene" Layer). '
   'Bänder ohne Fehler (r2 &gt; 0.45) bleiben glatt.',
 'MAP': 'Bildprägung: das gewählte Foto wird als Höhenkarte um die Wand '
   'gelegt - hin UND gespiegelt zurück über EINEN Umfang (Naht trifft '
   'Pixel 0 auf Pixel 0, oben bündig). Hell = erhaben. Das Bild wird im '
   'Texture-Menü unter „Bild" gewählt.',
}
PAT_ORDER = ['RIDGES', 'WAVES', 'GRID', 'HATCH', 'CHECKER', 'HEX',
             'HONEYCOMB', 'BASKET', 'ROPE', 'PLANKS', 'BRICKS', 'SANDSTONE',
             'CONCRETE', 'CLAY', 'CREPE', 'FABRIC', 'PLUSH', 'HILBERT',
             'SCRATCH', 'GLITCH', 'MAP']


def presets_for(pattern):
    out = []
    for name in sorted(LIB):
        d = LIB[name]
        if d['texture_pattern'] == pattern and d['texture_mode'] == 'BUMPS':
            out.append((name, d))
    return out


def main():
    flow = []
    A = flow.append

    # ------------------------------------------------------------- cover --
    A(Spacer(1, 10*mm))
    A(Paragraph('R2-D2 Texturing', S['title']))
    A(Paragraph('Struktur-Prägung auf der Objektwand', S['sub']))
    A(Spacer(1, 6*mm))
    A(P('Dieses Handbuch dokumentiert das Texture-Werkzeug (Pre-Print &gt; '
        'Mods &gt; Texture): wie die Wandverschiebung arbeitet, das EXAKTE '
        'Mapping jedes Parameters, alle 21 Muster mit Vorschaubildern - '
        'die Bilder sind direkt aus den echten Musterfunktionen gesampelt, '
        'nicht neu gezeichnet - und die 44 fertigen Vorlagen-Presets.'))
    A(Spacer(1, 3*mm))
    A(TBL(['Ebene', 'Was'], [
        ['Modus FUZZY', 'Zufällige Wandverformung (Fuzzy-Skin): jeder '
         'Außenwand-Vertex wandert mit Wahrscheinlichkeit Dichte um bis zu '
         'Dicke in eine Zufallsrichtung. Kein Muster, reines Rauschen.'],
        ['Modus BUMPS', 'Deterministische Musterfunktion verschiebt die '
         'Außenwand radial - 21 Muster, gesteuert durch SIZE/ZSIZE/DEPTH/DIR/SEED.'],
        ['21 Muster', 'Trigonometrie (Ridges, Waves, Grid, Hatch, Checker, '
         'Hex), Geflechte (Honeycomb, Basket, Rope), Beplankung (Planks, '
         'Bricks), Noise-Familien (Sandstone, Concrete, Clay, Crepe, Fabric, '
         'Plush), Kurven (Hilbert) und Oberflächen (Scratch, Glitch, Map).'],
        ['44 Vorlagen', 'Fertige Looks unter Vorlagen im Texture-Menü - '
         'Namen nach der OPTIK (Rattan, Sandstein, Seil, Ziegelmauer ...), '
         'jeder Eintrag trägt ALLE neun Settings.'],
    ], [30*mm, 126*mm]))
    A(Spacer(1, 4*mm))
    A(P('<b>Wo:</b> LCD Pre-Print &gt; Mods &gt; Texture (und der Web-LCD '
        'Spiegel). <b>Wann:</b> vor dem Slicen bzw. auf der fertigen, '
        'ungetaggten oder getaggten G-Code-Datei - das Werkzeug schreibt '
        'eine eigene Datei mit dem Zusatz des Musters und bleibt '
        'idempotent (erneutes Anwenden mit anderen Werten ersetzt die '
        'vorherige Prägung dieser Quelle).'))

    # ------------------------------------------------- how it works ------
    flow.extend(H1('1 · Wie die Prägung arbeitet'))
    A(P('Das Werkzeug läuft als Nachbearbeitung auf der G-Code-Datei. '
        'Grundprinzip in BUMPS: jeder Vertex der <b>Außenwand</b> wird '
        'entlang der Bewegungs-Normalen verschoben -'))
    A(CODE('nx = ox · pattern(x, y, z) · sign(amp)\n'
           'ny = oy · pattern(x, y, z) · sign(amp)'))
    A(P('mit (ox, oy) = Normale des jeweiligen Bewegungssegments. Das '
        'Muster wird in <b>Zylinderkoordinaten um das Objekt</b> '
        'ausgewertet:'))
    A(CODE('s = atan2(y - cy, x - cx) / 2pi      (Umfang 0..1)\n'
           't = (z - minz) · n / hoehe           (Hoehe 0..1)\n'
           'pattern(s, t)  ->  -1 .. +1'))
    A(P('(cx, cy) ist das Ausschluss-Objektzentrum (exclude-object center) '
        'oder der Wand-Schwerpunkt. Weil s und t normiert sind und die '
        'Musterfunktionen periodisch in beiden Achsen sind, ist die Prägung '
        '<b>nahtlos am Umfang</b> und <b>bündig an der Oberkante</b>.'))
    A(P('Verschoben werden NUR Außenwand-Züge (Outer wall und alle Aliase - '
        'Perimeter, External perimeter, Wall-outer). Innenwände, Infill und '
        'Flächen bleiben unberührt: die Textur ist eine reine Prägung der '
        'sichtbaren Wand. Der Bettbereich klemmt alle verschobenen Punkte '
        '(clamped, wird gezählt und gemeldet).'))
    A(P('In FUZZY entscheidet ein geseedeter Zufallsgenerator pro Vertex: '
        'mit Wahrscheinlichkeit Dichte (% ) wandert der Punkt um bis zu '
        'Dicke (mm) in eine Zufallsrichtung innerhalb eines Kreises um die '
        'Originalposition. FUZZY braucht keine Z-Information, BUMPS '
        'erfordert Z-Bewegungen in der Datei (ehrliche Fehlermeldung '
        'sonst).'))

    # ------------------------------------------------------- mapping -----
    flow.extend(H1('2 · Das exakte Mapping der Einstellungen'))
    A(P('Umfang und Höhe des OBJEKTS werden gemessen: Umfang = mittlere '
        'Sehnenlänge der Außenwand-Züge (Summe der Sehnen geteilt durch die '
        'Zug-Zahl; Fallback 2·pi·8 mm wenn nichts Messbares da ist), Höhe = '
        'Z-Spanne. Daraus und aus den vier Muster-Parametern folgen die '
        'Gittergrößen:'))
    A(CODE('k = clamp(round(Umfang / SIZE),     1, 240)   Rippen am Umfang\n'
           'n = clamp(round(Hoehe  / ZSIZE),    1, 400)   Wiederholungen in Z\n'
           'effektive Groesse = Umfang / k      (mm pro Rippe)\n'
           'effektive Hoehe   = Hoehe  / n      (mm pro Wiederholung)'))
    A(P('SIZE und ZSIZE sind Richtwerte: das Werkzeug setzt IMMER ganze '
        'Rippen bzw. Wiederholungen (deshalb nahtlos) und meldet die '
        'effektiven Größen im Abschlussbericht.'))
    A(Spacer(1, 2*mm))
    A(TBL(['Parameter (LCD)', 'Bereich', 'Wirkung'], [
        ['Modus', 'FUZZY / BUMPS', 'Zufallstextur oder Musterfunktion (Kap. 3/4)'],
        ['Dicke (FUZZY)', '0.1-1.0 mm', 'Maximaler Zufallsversatz pro Vertex'],
        ['Dichte (FUZZY)', '10-100 %', 'Anteil der verschobenen Vertices'],
        ['Muster (BUMPS)', '21 Muster', 'Die Musterfunktion (Kapitel 3)'],
        ['Around (SIZE)', '3-80 mm', 'Richtwert Umfang -> k Rippen (ganz)'],
        ['Height (ZSIZE)', '0.5-200 mm', 'Richtwert Höhe -> n Wiederholungen (ganz, oben bündig)'],
        ['Depth (DEPTH)', '0.05-1.0 mm', 'Verschiebetiefe = Amplitude der Prägung'],
        ['Richtung (DIR)', 'IN / OUT', 'Vorzeichen: erhaben nach außen oder eingezogen'],
        ['Seed', '1-999', 'Zufallsbasis: Noise-Muster, Fugen-Versatz (Planks/Bricks), Glitch-Bänder. Gleicher Seed = gleiches Bild'],
        ['Bild (MAP)', 'Auswahl', 'Quellfoto für die Bildprägung (hell = erhaben)'],
    ], [34*mm, 24*mm, 98*mm]))
    A(Spacer(1, 2*mm))
    A(P('<b>Depth in der Praxis:</b> 0.15-0.30 mm für feine Struktur, '
        '0.35-0.50 mm für markante Optik, darüber wird die Wand bei '
        'kleinen Radien wellig. Die erste Lage bleibt unberührt '
        '(Haftung), Travels werden nicht geprägt.'))

    # ------------------------------------------------------- catalogue ---
    flow.extend(H1('3 · Muster-Katalog mit echten Vorschauen'))
    A(P('Jedes Vorschaubild ist mit der Original-Musterfunktion des '
        'Werkzeugs erzeugt - Beispielobjekt Zylinder Ø 60 × 60 mm '
        '(Umfang %.1f mm), die Parameter des jeweils ERSTEN gelisteten '
        'Vorlagen-Presets, Schräglicht von links oben (hell = erhaben, '
        'dunkel = vertieft). Was das Bild zeigt, druckt das Werkzeug.'
        % CIRC))
    A(Spacer(1, 2*mm))
    for pname in PAT_ORDER:
        ps = presets_for(pname)
        if not ps:
            continue
        first, fd = ps[0]
        k, n = k_n_for(fd)
        block = []
        block += H2('%s  ·  z. B. „%s"' % (pname, first))
        block.append(pat_img(pname, fd))
        block.append(CAP('„%s": SIZE %.1f / ZSIZE %.1f / DEPTH %.2f / SEED %d '
                         '-&gt; k=%d Rippen, n=%d Wiederholungen am Beispiel'
                         ' (effektiv %.1f × %.1f mm)'
                         % (first, fd['texture_scale'], fd['texture_zsize'],
                            fd['texture_amp'], fd['texture_seed'], k, n,
                            CIRC / k, EXAMPLE_H / n)))
        block.append(P(PAT_TXT[pname]))
        rows = [[nm, '%.1f' % d['texture_scale'], '%.1f' % d['texture_zsize'],
                 '%.2f' % d['texture_amp'], str(d['texture_seed'])]
                for (nm, d) in ps]
        block.append(TBL(['Vorlage', 'SIZE', 'ZSIZE', 'DEPTH', 'SEED'], rows,
                         [52*mm, 22*mm, 22*mm, 22*mm, 20*mm]))
        A(KeepTogether(block))

    # --------------------------------------------------------- presets ---
    A(PageBreak())
    flow.extend(H1('4 · Die Vorlagen-Bibliothek (44 Looks)'))
    A(P('Texture-Menü &gt; Vorlagen: 44 fertige Looks, benannt nach dem '
        '<b>optischen Erscheinungsbild</b> (der Name sagt, was man sieht - '
        '„Rattan", nicht „BASKET 6/6"). Vorlagen sind schreibgeschützt: '
        'Laden geht, Löschen nicht; speichert man unter einem '
        'Vorlagen-Namen, wird der eigene Entwurf durchnummeriert.'))
    flow.extend(B('<b>Laden passt die Settings an und zeigt sie:</b> der Ladevorgang '
        'schreibt alle neun Werte (Modus, Dicke, Dichte, Muster, Around, '
        'Height, Depth, Richtung, Seed) und antwortet mit einer '
        'Kurzfassung - z. B. „Rattan (library) loaded: mode=BUMPS, '
        'pattern=BASKET, scale=6.0, zsize=6.0, amp=0.30, dir=OUT".',
        '<b>Ältere eigene Presets</b> aus Zeiten vor neueren Settings '
        'kennen deren Schlüssel nicht - sie laden ihre Werte und der '
        'Abschluss nennt ehrlich, wie viele Settings unverändert blieben '
        '(„6 setting(s) not in this preset (older save - kept as-is)"). '
        'Das ist die Antwort auf den Bilderrahmen-Fall: das alte Preset '
        'enthielt die Maße schlicht nicht.',
        '<b>Eigene Presets</b> speichert man im selben Menü (Presets &gt; '
        'Save) - eigene und Vorlagen teilen sich die Liste, eigene '
        'gewinnen bei Namensgleichheit.'))
    A(Spacer(1, 2*mm))
    rows = []
    for nm in sorted(LIB):
        d = LIB[nm]
        rows.append([nm,
                     d['texture_mode'],
                     d['texture_pattern'] if d['texture_mode'] == 'BUMPS' else '-',
                     '%.1f' % d['texture_scale'],
                     '%.1f' % d['texture_zsize'],
                     '%.2f' % d['texture_amp'],
                     str(d['texture_seed'])])
    A(TBL(['Vorlage', 'Modus', 'Muster', 'SIZE', 'ZSIZE', 'DEPTH', 'SEED'],
          rows, [46*mm, 18*mm, 30*mm, 17*mm, 17*mm, 17*mm, 15*mm]))

    # ---------------------------------------------------------- fuzzy ----
    flow.extend(H1('5 · Die FUZZY-Modi (Zufallstextur)'))
    A(P('Zwei Vorlagen arbeiten im FUZZY-Modus ohne Musterfunktion: '
        '<b>„Pfirsichhaut"</b> (Dicke 0.15 mm, Dichte 60 %) für eine feine, '
        'seidige Außenhaut und <b>„Filz grob"</b> (Dicke 0.35 mm, Dichte '
        '100 %) für eine grob-raue Filz-Optik. Die Dichte bestimmt, wie '
        'viele Wandpunkte wandern - niedrige Dichte wirkt wie punktueller '
        'Griff, hohe Dichte wie geschlossener Filz. Der Zufallsgenerator '
        'ist nicht geseedet pro Punkt - jede Anwendung erzeugt ein neues '
        'Bild (das ist bei Fuzzy gewollt).'))

    # ------------------------------------------- 6 complex geometry (R224) --
    flow.extend(H1('6 · Komplexe Geometrie'))

    def fig_square(preset_seed=23):
        """A SQUARE cross-section textured by the REAL rope pattern: the
        angle-based mapping works for any outline, not just circles."""
        import io
        import math as _m
        W, H = 620, 430
        im = PILImage.new('RGB', (W, H), 'white')
        d = ImageDraw.Draw(im)
        cx, cy, half = W // 2, H // 2, 130
        pats = r2_texture._build_patterns(12, 1, preset_seed, None)
        fn = pats['ROPE']
        amp = 16.0

        def outline(displace):
            pts = []
            for i in range(4 * 48):
                # walk the square perimeter: side + position on side
                side, u = i // 48, (i % 48) / 48.0
                if side == 0:
                    x, y = -1 + 2 * u, -1
                    nx_, ny_ = 0.0, -1.0
                elif side == 1:
                    x, y = 1, -1 + 2 * u
                    nx_, ny_ = 1.0, 0.0
                elif side == 2:
                    x, y = 1 - 2 * u, 1
                    nx_, ny_ = 0.0, 1.0
                else:
                    x, y = -1, 1 - 2 * u
                    nx_, ny_ = -1.0, 0.0
                th = _m.atan2(y, x)
                s = (th / (2 * _m.pi)) % 1.0
                v = fn(s, 0.35) if displace else 0.0
                pts.append((cx + (x + nx_ * v * 0.09) * half,
                            cy + (y + ny_ * v * 0.09) * half))
            return pts

        # angle rays every 30 degrees, labeled with s
        for deg in range(0, 360, 30):
            a = _m.radians(deg)
            x2, y2 = cx + _m.cos(a) * (half + 62), cy + _m.sin(a) * (half + 62)
            d.line([(cx, cy), (int(x2), int(y2))],
                   fill=(214, 222, 235), width=1)
            lx = cx + _m.cos(a) * (half + 84)
            ly = cy + _m.sin(a) * (half + 84)
            d.text((lx - 16, ly - 9), '%d°' % deg, fill=(150, 150, 150),
                   font=_tfont(16))
        # original outline (gray, dashed feel: thin)
        d.line(outline(False), fill=(170, 170, 170), width=2)
        # textured outline (blue, thick)
        d.line(outline(True), fill=(28, 78, 140), width=5)
        # center + label
        d.ellipse([cx - 4, cy - 4, cx + 4, cy + 4], fill=(227, 123, 0))
        d.text((cx + 9, cy + 7), 'Zentrum (cy)', fill=(227, 123, 0),
               font=_tfont(17))
        d.text((cx + 9, cy + 28), 's = atan2(y−cy, x−cx)/2π',
               fill=(28, 78, 140), font=_tfont(18, True))
        buf = io.BytesIO(); im.save(buf, format='PNG'); buf.seek(0)
        img = Image(buf, width=140*mm, height=140*mm*H/float(W))
        img.hAlign = 'CENTER'
        return img

    def fig_stack():
        """Outer + inner wall: the SAME displacement vector at the same
        angle keeps the gap at one line width (R224 task 15)."""
        import io
        W, H = 620, 330
        im = PILImage.new('RGB', (W, H), 'white')
        d = ImageDraw.Draw(im)
        f = _tfont(18); fb = _tfont(19, True)
        # top: original stack (two parallel lines, gap)
        y0, y1, x0, x1 = 70, 106, 70, 400
        d.line([(x0, y0), (x1, y0)], fill=(28, 78, 140), width=5)
        d.line([(x0, y1), (x1, y1)], fill=(106, 63, 181), width=5)
        d.text((x1 + 14, y0 - 10), 'Außenwand', fill=(28, 78, 140), font=f)
        d.text((x1 + 14, y1 - 10), 'Innenwand', fill=(106, 63, 181), font=f)
        d.text((x0, y1 + 16), 'Abstand = eine Linienbreite', fill=(90, 90, 91),
               font=f)
        # displacement arrows (same vector at the same angle)
        for xa in (140, 230, 320):
            d.line([(xa, y0), (xa, y0 - 40)], fill=(30, 125, 50), width=4)
            d.polygon([(xa, y0 - 50), (xa - 6, y0 - 36), (xa + 6, y0 - 36)],
                      fill=(30, 125, 50))
            d.line([(xa, y1), (xa, y1 - 40)], fill=(30, 125, 50), width=4)
            d.polygon([(xa, y1 - 50), (xa - 6, y1 - 36), (xa + 6, y1 - 36)],
                      fill=(30, 125, 50))
        d.text((150, 8), 'gleicher Winkel ⇒ gleicher Musterwert ⇒ '
               'gleicher Verschiebevektor', fill=(30, 125, 50), font=fb)
        # bottom: both shifted (parallel again, gap kept)
        y0b, y1b = 240, 276
        d.line([(x0, y0b), (x1, y0b)], fill=(28, 78, 140), width=5)
        d.line([(x0, y1b), (x1, y1b)], fill=(106, 63, 181), width=5)
        d.text((x0, y1b + 16), 'Abstand bleibt: eine Linienbreite (gemessen, '
               'nicht behauptet)', fill=(90, 90, 91), font=f)
        # gap arrows
        for xb in (110, 250, 380):
            d.line([(xb, y0b), (xb, y1b)], fill=(227, 123, 0), width=3)
        buf = io.BytesIO(); im.save(buf, format='PNG'); buf.seek(0)
        img = Image(buf, width=140*mm, height=140*mm*H/float(W))
        img.hAlign = 'CENTER'
        return img

    A(P('Die Muster-Bibliothek wirkt, als wäre sie für Rundkörper gemacht - '
        'Rillen, Seil, Waben um einen Zylinder. Tatsächlich arbeitet das '
        'Mapping <b>winkelbasiert um das Objekt</b>, nicht '
        'bogenlängenbasiert oder gar kreisspezifisch. Dieses Kapitel '
        'dokumentiert, was daraus für komplexe Geometrie folgt - und wo '
        'die Grenzen liegen.'))
    A(fig_square())
    A(CAP('Ein QUADRATISCHER Querschnitt, geprägt mit der echten ROPE-'
          'Funktion (3 Stränge, 1 Verdrehung): der Musterwert hängt nur vom Winkel um das '
          'Zentrum ab - grau die Originalkontur, blau die verschobene. '
          'Eckige, konvexe und konkave Querschnitte arbeiten alle '
          'gleich, weil s = Winkel/2π auf jeder Kontur definiert ist.'))
    flow.extend(H2('6.1 Zylinderkoordinaten um das Objekt'))
    A(P('Jeder Wandpunkt (x, y, z) wird in Zylinderkoordinaten um das '
        'Objektzentrum (cx, cy) gelegt: s = atan2(y−cy, x−cx)/2π (0..1 '
        'umlaufend) und t = (z−z_min)·n/H (0..1 über die Höhe). Das '
        'Muster ist eine Funktion f(s, t) - der Winkel sagt, <b>wo um '
        'den Körper</b> der Punkt liegt, die Höhe sagt, <b>wo im '
        'Wiederholungszyklus</b>. Ein Quadrat mit gleichem Winkelintervall '
        'bekommt dieselbe Musterphase wie ein Kreis - nur eben auf '
        'abgewinkelten Kanten auseinandergezogen.'))
    flow.extend(H2('6.2 Ganze Wiederholungen: die Naht-freiheit'))
    A(P('k (Rillen umlaufend) und n (Wiederholungen in Z) sind <b>ganze '
        'Zahlen</b>: k = round(Umfang/Size) im Bereich 1..240, n = '
        'round(Höhe/ZSize) im Bereich 1..400. Der_mm-Wert ist eine '
        'Richtlinie - das Werkzeug snappt auf ganze Wiederholungen und '
        'meldet die effektive Größe („seamless: 9 ridges × 2 Z-repeats '
        '(eff. 8.4mm × 2.9mm)“). Genau das macht die Textur nahtfrei: '
        'der Umfang schließt nach k ganzen Perioden, die Höhe endet '
        'nach n ganzen Perioden - keine halben Rillen, kein Versatz am '
        'Schluss.'))
    flow.extend(H2('6.3 Das Zentrum: zwei Quellen'))
    A(P('Das Drehzentrum (cx, cy) kommt aus der besten verfügbaren Quelle: '
        '<b>EXCLUDE_OBJECT_DEFINE CENTER</b>-Zeilen (vom Slicer '
        'geschrieben, die genaueste Wahl) - sonst aus dem '
        '<b>Außenwand-Vertex-Schwerpunkt</b> der Datei. Bei mehreren '
        'Objekten zählt das erste Zentrum; ein drastisch '
        'asymmetrisches Teil verschiebt die Musterphase, aber nie die '
        'Naht-freiheit (k bleibt ganz).'))
    flow.extend(H2('6.4 Bögen: 0,35-mm-Sehnen mit exaktem E'))
    A(P('Slicer-Dateien mit <b>Bogenanpassung</b> (G2/G3 - Vasen, '
        'Zylinder) tragen die Außenwand als wenige Bögen statt vieler '
        'G1-Punkte. Das Werkzeug zerlegt Außenwand-Bögen in 0,35-mm-'
        'Sehnen - dieselbe Abflachung wie das Cut-&amp;-Split- und das '
        'Scale-Werkzeug - und verteilt die Extrusion des Bogens exakt '
        'nach Sehnenlänge (relative E) bzw. interpoliert vom letzten '
        'Wert (absolute E). Die Textur umläuft danach den GANZEN Körper '
        '(Feldlog .74: vorher „nur die Ecken").'))
    flow.extend(H2('6.5 Dialekte: Vase, Cura, Prusa (R152)'))
    A(P('Orca/Elegoo schreiben im Normalmodus „;TYPE:Outer wall", im '
        '<b>Vasen-/Spiralmodus</b> aber „;TYPE:Wall outer" - beides wird '
        'erkannt, ebenso Cura WALL-OUTER (über das kanonische '
        'APPLY_TYPE) und PrusaSlicers „External perimeter". Eine '
        'Spiral-Vase bekommt ihre Textur dadurch durchgehend entlang '
        'der Spiralwand, nicht nur in den Rest-Ebenen.'))
    flow.extend(H2('6.6 Ohne jede Markierung: der Lithophan-Fallback'))
    A(P('Dateien ganz ohne Wand-Marker (Lithophane, rohe '
        'Extrusions-Kunst) laufen im R175-Fallback: <b>jeder Pfad ist '
        'die Geometrie</b> - Umfang, Höhe und Zentrum werden über ALLE '
        'Extrusionsbewegungen gemessen, und die Textur prägt jeden '
        'Pfad. Die Datei-Kopfzeile sagt es, damit niemand rätselt, warum '
        'auch die Füllung Muster trägt.'))
    flow.extend(H2('6.7 Z-Verfolgung: Muster leben von der Höhe (R186)'))
    A(P('Ein BUMP-Muster ist nach Höhe platziert - aber Slicer-Dateien '
        'tragen Z nur am Schichtwechsel, nicht auf jedem Wandpunkt. Das '
        'Werkzeug erbt deshalb die letzte gesehene Höhe (cur_z_e): '
        'jede Bewegung mit Z aktualisiert sie, jeder Wandpunkt wertet '
        'seine Musterfunktion mit dieser Höhe aus. Vor R186 wertete der '
        'ganze Text den Wert 0 aus - ein fester Ring statt '
        'Höhenvariation; Dateien ganz ohne Z verweigern BUMPS '
        'aufrichtig („needs the layer heights"), FUZZY geht weiter '
        '(braucht keine Höhe).'))
    flow.extend(H2('6.8 Innenwände folgen der Prägung (.136v, R224)'))
    A(P('Eine unberührte Innenwand liegt eine Linienbreite hinter der '
        'Oberfläche - und <b>kappt die Täler</b> einer tiefen DIR=IN-'
        'Textur: das Muster wirkt ausgewaschen, weil die glatte '
        'Innenwand durch die Senken scheint. Seit .136v <b>folgen die '
        'Innenwände der Prägung</b>: derselbe Winkel ergibt denselben '
        'Musterwert, und die Verschiebung läuft entlang derselben '
        'Segment-Normale - der Wandstapel bewegt sich als <b>ein '
        'Körper</b>. Der Punkt-zu-Punkt-Abstand bleibt exakt eine '
        'Linienbreite (messtechnisch verifiziert, nicht angenommen), '
        'die Täler werden voll ausgeprägt, und der Wandkontakt bleibt '
        'gehalten. Läuft der Slicer eine Innenkontur entgegengesetzt '
        'zur Außenkontur (eine Festigkeits-Option mancher Slicer), '
        'erkennt das Werkzeug die Windung pro Schicht und dreht die '
        'Folge-Verschiebung zurück - ohne diesen Ausgleich würde die '
        'Innenwand WEG von der Außenwand wandern.'))
    A(fig_stack())
    A(CAP('Wandstapel-Following: derselbe Verschiebevektor (grün) trifft '
          'Außenwand und Innenwand im selben Winkel - der Abstand bleibt '
          'eine Linienbreite (orange), der Stapel bewegt sich als ein '
          'Körper. FUZZY bleibt dagegen Orca-treu: nur die Außenwand '
          'zittert, exakt wie Orcas Fuzzy Skin.'))
    flow.extend(H2('6.9 Richtung, Anfahrt und Grenzen'))
    A(P('Die Verschiebung läuft entlang der <b>linken Normale der '
        'Bewegungsrichtung</b> - lokal, pro Segment, ohne globale '
        'Richtungskorrektur. DIR=OUT/IN kehrt das Vorzeichen. Der erste '
        'Vertex einer Kontur und Nulllängen-Neustarts bleiben unversetzt '
        '(keine Anfahrt = keine Richtung, nichts wird erfunden). Punkte, '
        'die durch die Verschiebung außerhalb des Betts lägen, werden an '
        'die Bettgrenze geklemmt und gezählt (clamped). Alles, was '
        'keine Außenwand (bzw. folgende Innenwand) ist - Füllung, '
        'Ironing, Stützen - druckt exakt wie vom Slicer gekommen.'))
    flow.extend(H2('6.10 Die drei Namens-Presets (R224)'))
    A(P('Die Feldrunde .136v hat außerdem die Muster-Namentreue '
        'geschärft: <b>ROPE</b> ist jetzt ein echtes Drehtampen-Seil '
        '(drei Stränge, flache Rücken, runde Furchen - vorher waren es '
        'bis zu zehn diagonale Rillen), <b>BASKET</b> ein echtes '
        'Geflecht (durchgehende Bänder mit Über/Unter-Verschränkung - '
        'vorher punktförmige Erhebungen) und <b>CHECKER</b> ein echtes '
        'Schachbrett (Zellen wechselnd mit weichen Kanten an JEDER '
        'Grenze - vorher stufenartig und mit Höckern an den Ecken). '
        'Dazu gibt es drei feste Presets im LCD (Fixed presets &gt; '
        'Rope / Basket / Chess), die den BUMPS-Modus mit dem kompletten '
        'Parametersatz setzen - dieselbe Disziplin wie die '
        'Vorlagen-Bibliothek.'))

    # ------------------------------------------------------------ end ----
    A(Spacer(1, 6*mm))
    A(Paragraph('Ende · R2-D2 Texturing · Stand .136w (R225)', S['end']))

    doc = Doc(os.path.join(_here, 'TEXTURING.pdf'))
    doc.build(flow)
    print('[ok] TEXTURING.pdf: %d pages, %d patterns, %d presets'
          % (doc.page, len(PAT_ORDER), len(LIB)))


if __name__ == '__main__':
    main()
