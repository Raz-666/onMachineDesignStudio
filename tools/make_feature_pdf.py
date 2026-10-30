#!/usr/bin/env python3
"""FEATURE_TAGGING.pdf — the deep-dive documentation of the R2-D2 feature
tagging system (user request, .134 round): every level from the slicer
comment to the live override, the vocabulary canon, the elimination ladder,
the geometry classifier, the CUSTOM feature, pure G-code without tags, the
slicer-family order research, and the .135 design for the remaining gaps.

Content basis: tools/r2_postproc.py (TYPE_RE/TYPE_MAP/_lookup_type/_canon_type,
_GeomScan R111/R153/R180/R181, process() APPLY_TYPE injection, _FILE_INFO),
macros/01_state.cfg + 08_print_start_stop.cfg (live side), the .133
feature-mismatch forensics, and the public slicer documentation
(CuraEngine wiki 'Generating Paths', OrcaSlicer wiki 'Walls printing order').
"""
import os

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (BaseDocTemplate, PageTemplate, Frame,
                                Paragraph, Spacer, Table, TableStyle,
                                PageBreak, CondPageBreak, KeepTogether)
from reportlab.platypus.flowables import Flowable
from reportlab.graphics.shapes import Drawing, Rect, String, Line, Polygon

FD = '/usr/share/fonts/truetype/dejavu/'
pdfmetrics.registerFont(TTFont('DVS', FD + 'DejaVuSans.ttf'))
pdfmetrics.registerFont(TTFont('DVSB', FD + 'DejaVuSans-Bold.ttf'))

BLUE = colors.HexColor('#1c4e8c'); LBLUE = colors.HexColor('#e8f0fa')
ORANGE = colors.HexColor('#e07b00'); GRAY = colors.HexColor('#58595b')
LGRAY = colors.HexColor('#f2f2f2'); GREEN = colors.HexColor('#1e7d32')
RED = colors.HexColor('#b3261e'); PURPLE = colors.HexColor('#6a3fb5')
TEAL = colors.HexColor('#00706b')

S = {
 'title': ParagraphStyle('t', fontName='DVSB', fontSize=25, leading=30, textColor=BLUE, alignment=1),
 'sub':   ParagraphStyle('s', fontName='DVS', fontSize=13.5, leading=19, textColor=GRAY, alignment=1),
 'h1':    ParagraphStyle('h1', fontName='DVSB', fontSize=20, leading=26, textColor=BLUE, spaceBefore=12, spaceAfter=2, keepWithNext=1),
 'h2':    ParagraphStyle('h2', fontName='DVSB', fontSize=15, leading=21, spaceBefore=16, spaceAfter=7, keepWithNext=1),
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
    def _tbl(h, r, w):
        data = [[Paragraph(x, S['ts']) for x in h]]
        for row in r:
            data.append([Paragraph(c, S['tc']) for c in row])
        t = Table(data, colWidths=w, repeatRows=1)
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
    return _tbl(headers, rows, widths)


def CENT(d):
    d.hAlign = 'CENTER'
    return d


def CENT_COVER():
    d = Drawing(430, 128)
    lv = [
        ('Stufe 0', 'Slicer-Vokabular (;TYPE: / ;FEATURE:)', TEAL),
        ('Stufe 1', 'Kanon + Eliminierungsleiter', BLUE),
        ('Stufe 2', 'APPLY_TYPE-Marker + Live-Interceptor', BLUE),
        ('Stufe 3', 'Geometrie-Klassifikator (ungetagte Dateien)', PURPLE),
        ('Stufe 4', 'CUSTOM-Watch: Blockgeometerieentscheidung', ORANGE),
        ('Stufe 5', 'Ausschluss-Logik + Quer-Schicht (Design .135)', RED),
    ]
    y = 112
    for tag, txt, col in lv:
        d.add(Rect(96, y, 64, 15, rx=3, ry=3, fillColor=col, strokeColor=None))
        d.add(String(128, y + 4.5, tag, fontName='DVSB', fontSize=8.4,
                     textAnchor='middle', fillColor=colors.white))
        d.add(Rect(164, y, 190, 15, rx=3, ry=3, fillColor=LGRAY,
                   strokeColor=colors.HexColor('#cccccc'), strokeWidth=0.6))
        d.add(String(175, y + 4.5, txt, fontName='DVS', fontSize=8.2,
                     fillColor=colors.black))
        y -= 19
    return d


class Doc(BaseDocTemplate):
    def __init__(self, fn):
        super().__init__(fn, pagesize=A4,
                         leftMargin=17*mm, rightMargin=17*mm,
                         topMargin=16*mm, bottomMargin=16*mm,
                         title='R2-D2 Feature-Tagging — der komplette Wahrheitspfad',
                         author='R2-D2 Macro System')
        f = Frame(self.leftMargin, self.bottomMargin, self.width, self.height, id='f')
        self.addPageTemplates([PageTemplate(id='pt', frames=[f], onPage=self._deco)])

    def _deco(self, canv, doc):
        canv.saveState()
        canv.setStrokeColor(BLUE); canv.setLineWidth(0.7)
        canv.line(17*mm, 285*mm, 193*mm, 285*mm)
        canv.setFont('DVS', 8.2); canv.setFillColor(GRAY)
        canv.drawString(17*mm, 287.2*mm, 'R2-D2 Macro System · Feature-Tagging — der komplette Wahrheitspfad')
        canv.drawRightString(193*mm, 287.2*mm, 'R2-2026-10-29.136g')
        canv.setFont('DVS', 8.6)
        canv.drawCentredString(105*mm, 9.5*mm, 'Seite %d' % doc.page)
        canv.restoreState()


# ---------------------------------------------------------------- diagrams --
def d_chain():
    """Die Datenkette: Slicer -> Watcher -> Klipper -> LCD/Live."""
    d = Drawing(460, 118)
    def box(x, y, w, h, head, body, fc=LBLUE, tc=BLUE):
        d.add(Rect(x, y, w, h, rx=4, ry=4, fillColor=fc, strokeColor=BLUE, strokeWidth=0.9))
        d.add(String(x + w/2, y + h - 11, head, fontName='DVSB', fontSize=8.4,
                     textAnchor='middle', fillColor=tc))
        for i, l in enumerate(body):
            d.add(String(x + w/2, y + h - 22 - i*9, l, fontName='DVS', fontSize=7.4,
                         textAnchor='middle', fillColor=colors.black))
    def arr(x1, y1, x2, y2, lbl=''):
        d.add(Line(x1, y1, x2, y2, strokeColor=ORANGE, strokeWidth=1.3))
        d.add(String((x1+x2)/2, (y1+y2)/2 + 3, lbl, fontName='DVS', fontSize=6.8,
                     textAnchor='middle', fillColor=ORANGE))
    box(4, 46, 96, 62, 'SLICER-FAMILIE', [';TYPE:Outer wall', ';TYPE:SKIN', ';TYPE:gap fill',
                                          'oder: NICHTS', '(purer G-Code)'])
    box(122, 46, 118, 62, 'R2-WATCHER (Python)', ['Stufe 1  canon + Leiter', 'Stufe 3  Geometrie',
                                                  'Stufe 4  CUSTOM-Watch', '-> APPLY_TYPE +',
                                                  '_FILE_INFO TYPES='])
    box(262, 46, 96, 62, 'KLIPPER (_STATE)', ['file_types =', 'TYPES= aus der Info-Zeile',
                                              'LAYER_MARK / APPLY_TYPE', 'Interceptor live'])
    box(378, 46, 78, 62, 'LCD + LIVE', ['16 Feature-Zeilen', 'Speed/PA/Flow/Accel', 'pro Feature',
                                        'NOW: Anzeige'])
    arr(100, 77, 122, 77, 'Datei')
    arr(240, 77, 262, 77, 'Push/Start')
    arr(358, 77, 378, 77, 'Render')
    d.add(String(230, 8, 'ein Fluss, fünf Auflösungs-Stufen — pro Block genau EIN Feature-Code',
                 fontName='DVS', fontSize=7.6, textAnchor='middle', fillColor=GRAY))
    return d


def d_ladder():
    """Die Auflösungsleiter eines ;TYPE:-Blocks."""
    d = Drawing(460, 150)
    steps = [
        ('1  Exakte Karte', "TYPE_MAP: 'outer wall', 'skin', 'gap fill' … 37 Schreibweisen"),
        ('2  Canon-Passthrough', 'bereits kanonische Werte (eigene Marker, vorbearbeitete Dateien)'),
        ('3  Separator-Toleranz', "'Wall outer' == 'wall-outer' == 'WALL_OUTER'  (R172)"),
        ('4  Support-Substring', "'tree support', 'support/base' -> SUPPORT"),
        ('5  Eliminierungsleiter', 'Schlüsselwort-Token: ' + "'iron', 'tower', 'brim', 'bridge' …" + ' (R180)'),
        ('6  CUSTOM-Watch', 'unbekannt geblieben: BLOCKGEOMETRIE entscheidet (R181)'),
        ('=  CUSTOM', 'Rest: eigener APPLY_TYPE-Block, Override default OFF, CUSTOMBLOCKS zählt'),
    ]
    y = 142
    for i, (h, b) in enumerate(steps):
        fc = LBLUE if i < 6 else colors.HexColor('#fdeaea')
        d.add(Rect(30, y - 16, 400, 18, rx=3, ry=3, fillColor=fc,
                   strokeColor=BLUE if i < 6 else RED, strokeWidth=0.8))
        d.add(String(38, y - 11, h, fontName='DVSB', fontSize=8.6, fillColor=BLUE if i < 6 else RED))
        d.add(String(150, y - 11, b, fontName='DVS', fontSize=7.7, fillColor=colors.black))
        y -= 20
    return d


flow = []
A = flow.append

# ============================== Cover =======================================
A(Spacer(1, 26*mm))
A(Paragraph('Feature-Tagging', S['title']))
A(Paragraph('der komplette Wahrheitspfad', S['title']))
A(Spacer(1, 6*mm))
A(Paragraph('Wie das R2-D2-System aus einer G-Code-Datei die Features liest —<br/>'
            'fünf Auflösungs-Stufen, der Geometrie-Klassifikator, das CUSTOM-Feature,<br/>'
            'purer G-Code ohne Slicer-Tags, und die Slicer-Familien im Vergleich', S['sub']))
A(Spacer(1, 10*mm))
A(CENT_COVER())
A(Spacer(1, 8*mm))
A(Paragraph('Stand: R2-2026-10-29.136g · Code-Wahrheit: tools/r2_postproc.py (TYPE_RE, TYPE_MAP, '
            '_canon_type, _GeomScan), macros/01_state.cfg + 08_print_start_stop.cfg · '
            'Slicer-Dokumentation: CuraEngine-Wiki »Generating Paths«, OrcaSlicer-Wiki '
            '»Walls printing order«', S['cap']))
A(PageBreak())

# ============================== Kap 1 =======================================
flow += H1('1  Warum Feature-Tagging?')
A(P('Das komplette Live-Tuning-System des R2-D2-Projekts hängt an einer Frage: '
    '<b>Welcher Abschnitt der Datei druckt gerade?</b> Erst die Antwort macht aus einem '
    'Global-Regler ein Werkzeug: die Außenwand langsamer und mit anderem PA drucken als den '
    'Innerwall, den Support schneller, das Ironing mit eigenem Flow, die Brücke kühl und langsam. '
    'Ohne Feature-Erkennung wäre jede Datei eine ununterscheidbare E-Wurst.'))
A(P('Daraus folgen die drei Verbraucher der Tags:'))
flow += B(
    '<b>Live > Features</b> — pro Feature Speed / Accel / PA / Flow, geführt vom jeweiligen '
    'GLOBAL-Wert; die Zeile NOW: zeigt das Feature, das gerade druckt.',
    '<b>Pre-Print > File info</b> — TYPES= entscheidet, welche der 16 Feature-Zeilen überhaupt '
    'anklickbar sind (Features, die die Datei nicht enthält, bleiben sichtbar, weigern sich aber '
    'ehrlich statt tote Schalter zu zeigen).',
    '<b>Start-Blockades</b> — dateilose Infos (Auto-Load der Datei-Parameter, _FILE_INFO-Replay '
    'beim Laden) und Range/Textur/Scale bauen auf denselben Types auf.')
A(P('Der Design-Grundsatz dabei ist <b>regelbasiert und deterministisch</b> — kein ML, kein '
    'Raten. Wenn das System eine Zuordnung nicht sicher herleiten kann, bleibt der Block CUSTOM '
    'und wird gezählt und erklärt, statt still die Einstellungen des Nachbar-Features zu erben.'))
A(CENT(d_chain()))
A(CAP('Abb. 1 — die Datenkette: vom Slicer-Kommentar bis zum Live-Regler'))

# ============================== Kap 2 =======================================
flow += H1('2  Stufe 0 — was die Slicer-Familien tatsächlich in die Datei schreiben')
A(P('Die primäre Quelle sind ;TYPE:-Kommentare (Slic3r-Erbe). Der Watcher akzeptiert '
    "'TYPE : X' und Freiform-Trenner; jede Familie schreibt ihr eigenes Vokabular:"))
A(TBL(['Slicer-Familie', 'Schreibweisen (Auswahl)', 'Kanon (R2)'], [
 ['PrusaSlicer / SuperSlicer',
  ';TYPE:Perimeter · External perimeter · Fill · Solid infill · Top solid infill · '
  'Bridge infill · Internal bridge · Gap fill · Skirt · Support material (interface) · '
  'Wipe tower · Overhang perimeter · Thin wall',
  'WALL-INNER · WALL-OUTER · INFILL-SPARSE · INFILL-SOLID · SURFACE-TOP · BRIDGE · '
  'INTERNAL-BRIDGE · GAPS · SKIRT · SUPPORT · PRIME-TOWER · OVERHANG-PERIM · WALL-INNER'],
 ['OrcaSlicer / Bambu Studio (Prusa-Ableger)',
  ';TYPE:Wall outer · Wall inner · Sparse infill · Internal solid infill · Top surface · '
  'Bottom surface · Gap fill · Ironing · Bridge · Skirt · Brim · Support (interface) · '
  'Prime tower — Klein-/Großschreibung und Trenner frei',
  'dasselbe Kanon-Set; Trenner-Toleranz (R172) fasst »Wall outer«/»wall-outer« zusammen'],
 ['UltiMaker Cura',
  ';TYPE:WALL-OUTER · WALL-INNER · SKIN / TOP-SKIN / BOTTOM-SKIN · FILL · BRIDGE · '
  'SUPPORT · SUPPORT-INTERFACE · SKIRT · RAFT',
  'SKIN-Paare -> SURFACE-TOP/BOTTOM (Cura trennt oben/unten nicht immer im Kommentar — '
  'die Position in der Schichtfolge klärt es)'],
 ['ideaMaker / Simplify3D / FlashPrint',
  'feature-lose Dateien (nur Layer-Kommentare oder gar nichts)',
  'Stufe 3: der Geometrie-Klassifikator leitet ab (DERIVED=1 CONF=0.7)'],
], [34*mm, 84*mm, 54*mm]))
A(P('Die frühere Bambu-Lücke ist <b>in .135 geschlossen</b>: TYPE_RE liest '
    '<b>;FEATURE:</b> seit R191 wie ;TYPE: — dieselbe Karte, dieselbe Leiter, unbekannte '
    'Bambu-Vokabeln fallen weiterhin ehrlich auf CUSTOM. Und Cura nennt seine Ober/Unter-'
    'Flächen gemeinsam SKIN — die Kanonisierung mappt auf SURFACE-TOP und korrigiert per '
    'Schichtposition.'))

# ============================== Kap 3 =======================================
flow += H1('3  Stufe 1 — Kanonisierung und die Eliminierungsleiter (_canon_type)')
A(P('Jeder ;TYPE:-Block durchläuft dieselbe feste Leiter (R143 Kanon, R172 Trenner-Toleranz, '
    'R180 Eliminierung, R181 Block-Watch). Die ersten Stufen sind reine Tabellen-Suche, '
    'die letzten sind deterministische Schlüsselwort- und Geometrie-Schlüsse:'))
A(CENT(d_ladder()))
A(CAP('Abb. 2 — die Auflösungsleiter: von der exakten Karte bis zum CUSTOM-Rest'))
A(P('Die Eliminierungsleiter (Stufe 5) zerlegt den unbekannten Text in Token und folgt '
    'festen Regeln — Beispiele aus dem Feld:'))
A(TBL(['Unbekannte Schreibweise', 'Token-Schluss', 'Ergebnis'], [
 ["';TYPE:Outer shell'", 'wall + outer', 'WALL-OUTER'],
 ["';TYPE:solid fill'", 'fill + solid', 'INFILL-SOLID'],
 ["';TYPE:ironing pass'", 'iron', 'IRONING'],
 ["';TYPE:purge line'", 'purge', 'SKIRT (Entsorgungsklasse)'],
 ["';TYPE:tree support (organic)'", 'Substring support', 'SUPPORT'],
 ["';TYPE:top skin layer'", 'skin + top', 'SURFACE-TOP'],
 ["';TYPE:bridge internal'", 'bridge + internal', 'INTERNAL-BRIDGE'],
], [52*mm, 52*mm, 38*mm]))
A(P('Der historische Auslöser (Feldprotokoll .129): eine Slicer-Schreibweise »Wall outer« '
    '(Leerzeichen statt Bindestrich) fiel durch die exakte Karte — komplette Wände druckten als '
    'CUSTOM mit nur PA als Regelgröße. Seither fängt die Leiter jede Vokabel-Drift ab, bevor '
    'sie die Menüs erreicht. Was gar kein bekanntes Token trägt, bleibt CUSTOM — und genau das '
    'ist der Einfallstor-Bericht: CUSTOMBLOCKS=n in _FILE_INFO, das File-info-Menü sagt, was '
    'zu tun ist (System &gt; File check &gt; Retag).'))

# ============================== Kap 4 =======================================
flow += H1('4  Stufe 2 — APPLY_TYPE-Marker und der Live-Interceptor')
A(P('Der Watcher schreibt das Kanon-Ergebnis zurück in die Datei: vor jeden Feature-Block '
    'eine Zeile <b>APPLY_TYPE TYPE=WALL-OUTER</b>, an jede Schichtgrenze ein <b>LAYER_MARK</b>. '
    'Das ist der Vertrag mit der Laufzeit:'))
A(CODE('; R2-POSTPROC v5\n'
       'LAYER_MARK\n'
       'APPLY_TYPE TYPE=WALL-OUTER\n'
       'G1 X120.4 Y88.1 E.42 F1800\n'
       'APPLY_TYPE TYPE=INFILL-SPARSE\n'
       'G1 X88.0 Y88.1 E.31 F2700'))
flow += B(
 'Der Interceptor in Klipper liest APPLY_TYPE, setzt _STATE.ftype und schaltet alle '
 'aktivierten Feature-Overrides (M204/M220-artige Werte, PA, Flow) beim Blockwechsel um — '
 'innerhalb von Millisekunden, ohne dass die Datei anhält.',
 'LAYER_MARK trägt die Schichtnummer (Layer-1-Regeln, L1/L2-Wechsel bei 2, PAUSE_AT_LAYER, '
 'sequenzielle Objekt-Erkennung).',
 'Ein <b>Retag</b> (System &gt; File check, 2×) frischt die Marker einer alten/v4-Datei auf: '
 'gleiche Marker, neue Info-Zeile, .r2bak-Backup.',
 'Der Range-Ausschnitt re-deriviert die Marker an den Schnittkanten (der Quell-Slicer spricht '
    'seine ;TYPE: oft nur einmal pro Schicht 1 — ein Ausschnitt ab Schicht 5 müsste sie sonst '
    'verlieren).')
A(P('Wichtig für die Wertigkeit: <b>getaggte Daten schlagen immer die Ableitung.</b> Die erste '
    'gefundene ;TYPE:-Zeile entwaffnet den Geometrie-Klassifikator (Stufe 3) — nie werden '
    'abgeleitete und getaggte Features in einer Datei gemischt.'))

# ============================== Kap 5 =======================================
flow += H1('5  Stufe 3 — der Geometrie-Klassifikator (Dateien ohne jedes Tag)')
A(P('Für Dateien ohne ;TYPE: (ideaMaker, Fremd-Downloads, eigene Skripte) läuft der '
    'zwei-Pass-Scanner _GeomScan: leicht überall (modale Werte, MAXRATE, SEAM), schwer nur '
    'solange die Datei ungetaggt wirkt. Er puffert die Extrusions-Polylinien einer Schicht '
    'und klassifiziert beim Schichtwechsel:'))
A(TBL(['Signal in der Schicht', 'Schluss', 'Feature'], [
 ['geschlossener Linienzug, äußerstes einer Insel (Verschachtelungs-Test)',
  'sichtbare Begrenzung', 'WALL-OUTER'],
 ['Linienzug in einer anderen verschachtelt', 'innenliegend', 'WALL-INNER'],
 ['gerade, parallele Linien, Abstand >= 3 mm', 'hatch, weit', 'INFILL-SPARSE'],
 ['parallele Linien, dichter', 'hatch, dicht', 'INFILL-SOLID'],
 ['dichter hatch auf Schicht 1', 'unten gibt es nur Boden', 'SURFACE-BOTTOM'],
 ['dichter hatch auf der LETZTEN Schicht', 'oben endet der Druck', 'SURFACE-TOP'],
 ['fast geschlossene Kurve (Gesamt-Winkel ~360°)', 'Spiralnaht-Rest, trotzdem eine Schleife', 'WALL-*'],
], [76*mm, 42*mm, 34*mm]))
A(P('<b>Das Schichtbild (R181):</b> jede Wand wird gerastert und auf <b>beiden Seiten</b> '
    'gemessen. Tinte auf einer Seite, nichts auf der anderen = sichtbare Fläche = WALL-OUTER '
    '(das Nichts kann außen ODER das Innere eines Lochs sein — beides sieht der Nutzer). '
    'Tinte auf beiden Seiten = WALL-INNER. Offene Bögen klassifizieren wie geschlossene '
    'Schleifen.'))
A(P('<b>Quer zur Schicht (R153/R181) — genau die logische Herleitung, die du beschreibst:</b>'))
flow += B(
 '<b>BRIM</b> = ein Wand-Loop der Schicht 1 <b>ohne Nachfolger</b> in den Folgeschichten '
 '(Wände wachsen nach oben, ein Brim nicht). Der Ring wird bis zu drei Schichten lang '
 'beobachtet, nur die äußerste Verschachtelungsebene zählt (ein Lochrand in Schicht 1 ist '
 'kein Brim).',
 '<b>SUPPORT</b> = eine abgetrennte Tinten-Komponente, die in der Schicht <b>zuerst</b> '
 'druckt (Slicer legen Stützmaterial vor das Modell), oberhalb der Brim-Schichten liegt und '
 'überwiegend geradlinigen hatch trägt.',
 '<b>BODEN/TOP</b> = erste/letzte Schicht des dichten hatch (s. o.).',
 '<b>Vasen-Modus</b> = durchgehender Steig-Zug nach der Basis: alles ab dort ist WALL-OUTER '
 '(eine Feature-Regel, kein Rätselraten).')
A(P('Die Ehrlichkeits-Spalte: abgeleitete Dateien tragen <b>DERIVED=1 CONF=0.7 COVER=n%</b> '
    'in der Info-Zeile — 0.7 Vertrauen fest kodiert, COVER = Anteil der Extrusionslänge, der '
    'überhaupt klassifiziert wurde. Kurze, offene, krumme Reste bleiben unklassifiziert statt '
    'geraten zu werden; <b>Brücken werden NICHT geraten</b> (braucht die Schicht darunter — '
    'dokumentierte Lücke, Kap. 7).'))

# ============================== Kap 6 =======================================
flow += H1('6  Stufe 4 — der CUSTOM-Watch: Blockgeometrie statt Kapitulation')
A(P('Bleibt eine Vokabel nach der Leiter übrig, wird ihr Block nicht einfach abgestempelt: '
    'der Watch puffert die <b>Geometrie des CUSTOM-Blocks selbst</b> und löst sie nachträglich '
    'auf (R181):'))
flow += B(
 'wandartiger Block (Schleifen/Kurven-Charakter) -> <b>WALL-OUTER</b> als Sicherheits-Default '
 '— die Nutzer-Regel: eine Wand darf niemals mit Infill-Tempo drucken.',
 'hatch-artiger Block -> INFILL-SPARSE/SOLID nach Lückenmaß.',
 'ohne jeden Wand-Charakter -> bleibt CUSTOM, CUSTOMRES/CUSTOMBLOCKS in der Info-Zeile '
 'liefern die Vorher/Nachher-Zahl fürs Menü.')
A(P('Damit ist CUSTOM kein Fehlerzustand mehr, sondern der <b>gezahlte Rest</b> nach vier '
    'Auflösungs-Stufen — und der Anlass, mit File check &gt; Retag gegen zu steuern.'))

# ============================== Kap 7 =======================================
flow += H1('7  Stufe 5 — GEBAUT in .135: Ausschluss-Logik als eigene Ebene')
A(P('Dein Vorschlag — Features über <b>Unmöglichkeiten</b> einzugrenzen — ist seit .135 '
    'eine echte Ebene im Import (R193). Zwei Hälften: der <b>Quer-Schicht-Luftscan</b> '
    'vergleicht jede dichte Hatch-Gruppe mit dem Schichtbild darunter (die Bitmap, die die '
    'Wandklassifikation ohnehin zeichnet): fast keine Tinte darunter = Druck über Luft = '
    'BRIDGE (Enden verankert, außerhalb jeder Loop) bzw. INTERNAL-BRIDGE (innerhalb des '
    'Modells oder unverankert). Dichtes Hatch über SPARSE-Infill darunter bleibt Surface/'
    'Solid — schon ~5% Tinte zählen als Material, schrittweise Infill kann also nie '
    'falsch kippen. Und der <b>Sequenz-Audit</b> (S1–S4) liest den Feature-Strom beider '
    'Welten — getaggt wie abgeleitet, nie gemischt — und zählt Verletzungen als '
    'SEQWARN=n in _FILE_INFO plus Daemon-Logzeile.'))
A(TBL(['Logische Regel (Unmöglichkeit)', 'Status .135'], [
 ['Skirt/Brim existieren nur in den ersten Schichten (Brim-Fenster 3 Layer)',
  'S3 — Audit + R153/Patiente (implizit seit R181)'],
 ['Ironing nie auf Schicht 1 und nie vor der ersten Top-Fläche DER SCHICHT',
  'S1+S2 — Audit; KORRIGIERT nach deinem Hinweis: Ironing darf auf '
  '<b>jedes</b> Top folgen (auch mitten in der Schicht), nicht nur auf das letzte'],
 ['Solid/Top-Surface auf Schicht 1 ist per Definition BOTTOM',
  'S4 — Audit + first_layer-Regel im Klassifikator'],
 ['Bridge: dichtes Hatch mit Tinte seitlich, aber Luft darunter',
  'GEBAUT: _airscan193 — r167-Kegel-Prinzip jetzt im Import (R193)'],
 ['Brim-Range wird re-taggt, aber die Buchung (TYPES=) zieht nicht mit',
  'GEFIXT (R192): _fmove192 verschiebt die fstat-Buchung mit — TYPES= '
  'verliert BRIM nie wieder (.134-Feldlücke)'],
 ['Purge-Tower der Generatoren ist ein eigenes Feature',
  'GEBAUT (R194): ;TYPE:Prime tower + APPLY_TYPE TYPE=PRIME-TOWER — '
  'Labels/Litho/Colorpic, Turmkörper EIN Feature, Turm-Brim bleibt BRIM'],
 ['Sequenz-Verstoß wird stillschweigend umgeschrieben',
  'NEIN — Bewusst: getaggte Daten herrschen. SEQWARN nennt die Regel, '
  'der Datei-Inhalt bleibt 1:1'],
], [88*mm, 54*mm]))
A(P('Ehrliche Rest-Lücken nach .135: das Stemming ist eine Whitelist (nur '
    '<b>ironing→iron</b>), kein blinder -ing-Schnitt — »missing« darf nie zu »miss« werden; '
    'der BRIDGE/INTERNAL-BRIDGE-Schluss nutzt die Loop-Schachtelung als Näherung für '
    'innen/außen; und der Audit prüft die vier harten Regeln S1–S4, weiche Ordnungen '
    '(Wand-Reihenfolge, Infill-Position) bleiben bewusst ungeprüft, weil sie reine '
    'Einstellungen sind. Alles deterministisch, alles testbar, kein ML.'))

flow += H1('8  Die Slicer-Familien: dokumentierte Reihenfolge im Druck')
A(P('Die Reihenfolge, in der Familien ihre Features abarbeiten, ist die zweite Quelle der '
    'Wahrheit. Aus der offiziellen Dokumentation (CuraEngine-Wiki »Generating Paths«, '
    'OrcaSlicer-Wiki »Walls printing order«):'))
flow += H2('8.1  CuraEngine — die dokumentierte Druckordnung pro Schicht')
A(CODE('1. Prime-Blob      (nur Schicht 1, falls angefordert)\n'
       '2. Prime-Tower     (falls Extruderwechsel anstehen)\n'
       '3. Skirt/Brim/Raft (Bettanhaftung)\n'
       '4. Ooze Shield / Draft Shield\n'
       '5. Support\n'
       '6. je Part:  Infill -> Inner Walls -> Outer Wall\n'
       '            -> Wand-Gap-Fill -> Skin -> Skin-Gap-Fill -> Ironing'))
A(P('Bemerkenswert: Cura druckt <b>Infill vor den Wänden</b> (Option »Infill Before Walls«, '
    'Standard an) — die Prusa-Sippe macht es umgekehrt. Fürs Tagging heißt das: die '
    'Schichtinterne Reihenfolge ist <b>familien- und einstellungsabhängig</b> und darf nur '
    'als weiches Signal dienen.'))
flow += H2('8.2  OrcaSlicer / Prusa-Sippe — konfigurierbare Wandordnung')
A(P('Orca dokumentiert wall_sequence = inner/outer · outer/inner · inner-outer-inner, plus '
    '»Print infill first«. Ausnahme, die die Regel bestätigt: <b>unter einem Outer/Outer-Inner- '
    'oder Leading-Edge-Brim druckt die erste Schicht die Außenwand zuerst</b>, damit der Brim '
    'nahtlos in die Wand übergeht. Seit Orca 2.4 gilt pro Objekt die Ordnung '
    '<b>Skirt → Brim → Objekt</b> (zuvor druckten alle Skirts zuerst).'))
flow += H2('8.3  Was davon hart ist — und was weich')
A(TBL(['Invariante (über Familien stabil)', 'Wert fürs Tagging'], [
 ['Skirt/Brim/Raft drucken VOR dem Objekt der Schicht', 'harts Signal — genutzt (SUPPORT-Regel nutzt das Erstsein indirekt)'],
 ['Ironing ist der LETZTE Abschnitt einer Schicht/Objekts', 'hart genug — .135-Sequenzregel'],
 ['Support druckt vor dem Modell (Cura dokumentiert, Prusa-Sippe gleich)', 'hart — R181 nutzt Erstsein + Hatch + Trennung'],
 ['Prime-Tower zuerst bei Schichten mit Toolwechsel', 'hart — .135'],
 ['Wand-Reihenfolge (innen/außen) und Infill-Position', 'WEICH (Einstellung!) — nur als Hinweis, nie als Beweis'],
 ['Top-Solid erst nach allen Wänden der Region', 'meist, aber einstellungsabhängig — weich'],
], [92*mm, 50*mm]))

# ============================== Kap 9 =======================================
flow += H1('9  Bridging, Überhänge, Support-Interface — der Quer-Schicht-Vergleich')
A(P('Du hast recht: der Postprozessor <b>sieht das komplette 3D-Objekt</b> — alle Koordinaten '
    'aller Schichten. Das Werkzeug, das daraus schon Realität ist, heißt r167-AirScan und '
    'prüft heute jede generierte Datei:'))
A(CODE('AIR SCAN (r167, für Generator-Output): jeder Extrusionspunkt ab Schicht 2\n'
       'muss in der Schicht darunter Material im 45°-Kegel (layer_h * 1.3) finden.\n'
       'Deklarierte BRIDGE-Abschnitte sind ausgenommen (die Regal-Überbrückung\n'
       'über der Rahmennut ist eine gewollte, langsame Brücke).'))
A(P('Dieselbe Prüfung, rückwärrt gelesen, ist ein <b>Bridge-Detektor</b>: Punkte, über denen '
    'in der Schicht darunter nur Luft liegt, sind Brücke oder Überhang — die Unterscheidung '
    'liegt in der Geometrie (gerade, flugbahnartige Züge mit Anker an beiden Enden = Brücke; '
    'schmale Randzüge mit Luft einseitig darunter = Overhang-Wand). Support-Interface erkennt '
    'man an dichtem hatch direkt über Support-hatch der Schicht darunter. Das ist der '
    '.135-Bauplan aus Kap. 7 — der Code-Pfad (Layer-Puffer + Bitmap) existiert bereits.'))

# ============================== Kap 10 ======================================
flow += H1('10  Das CUSTOM-Feature — was es konkret bedeutet')
A(P('CUSTOM ist im Kanon einer von 16 Codes und hat eine präzise Bedeutung: '
    '<b>ein Abschnitt, dessen Vokabel keine Stufe auflösen konnte</b>. Daraus folgt:'))
flow += B(
 'Er bekommt trotzdem einen eigenen APPLY_TYPE-Block — Feature-Overrides <b>bluten nie</b> '
 'vom vorherigen Abschnitt herüber (das war der alte Bug: unbekannte Abschnitte erbten die '
 'Geschwindigkeit des letzten bekannten Features).',
 'Sein Override steht <b>default OFF</b> — der Abschnitt druckt 1:1 wie gesliced. Erst wenn '
 'du in Live &gt; Features CU speed/PA/Flow/accel etwas setzt, greift eine Regel.',
 'CUSTOMBLOCKS=n in _FILE_INFO zählt die unverständlichen Blöcke, CUSTOMRES=n die durch die '
 'Blockgeometrie geretteten — das File-info-Menü zeigt beides und nennt den Ausweg.',
 'Ein CUSTOM-Block ist fast immer eine <b>Vokabel-Drift</b>: ein Slicer-Update hat eine '
 'Schreibweise geändert. System &gt; File check &gt; Retag (2×) frisst die Datei durch die '
 'aktuelle Leiter — nach einem .13x-Slicer-Update lohnt sich das bei Altdateien.',
 'Mit der Ausschluss-Ebene (Kap. 7) schrumpft CUSTOM weiter: Sequenz- und Quer-Schicht-'
 'Regeln werden die Restfälle weitgehend auflösen.')
A(P('Nicht verwechseln: CUSTOM ist auch das <b>Ziel für eigene Tuning-Träume</b> — '
    '»der Abschnitt, den ich selbst benenne«. Genau dafür stehen die 16 Aktivator-Zeilen '
    '(inkl. Overhang, Internal Bridge, Prime Tower, R168) in Live &gt; Features: Dateien, '
    'die das Feature tragen, zeigen es an; die Override-Werte bleiben pro Datei-Portfolio '
    'speicherbar.'))

# ============================== Kap 11 ======================================
flow += H1('11  Purer G-Code — wenn der Slicer nichts mitgeliefert hat')
A(P('Eine Datei ganz ohne ;TYPE: durchläuft die vollständige Fallback-Leiter. Konkret am '
    'Beispiel einer ideaMaker-Datei:'))
A(TBL(['Schritt', 'Was passiert'], [
 ['1  Layer-Erkennung', 'Layer-Kommentare (;LAYER_CHANGE, ;Z:) oder Z-Scan (extrudierender Zug mit absolutem Z-Wechsel = Schichtgrenze; Vasen-Steigen akkumuliert bis zur Schichthöhe)'],
 ['2  Geometrie-Klassifikator', 'pro Schicht: Schleifen/Hatch/Kurven -> WALL-OUTER/INNER, INFILL-*, BODEN/TOP; CONF=0.7, COVER=n%'],
 ['3  Marker schreiben', 'APPLY_TYPE je abgeleiteten Block + LAYER_MARK je Schicht — identisches Laufzeit-Verhalten wie getaggte Dateien'],
 ['4  Info-Zeile', '_FILE_INFO ... DERIVED=1 CONF=0.7 COVER=72 TYPES=WALL-OUTER,WALL-INNER,INFILL-SPARSE,SURFACE-BOTTOM,SURFACE-TOP'],
 ['5  Live', 'File info zeigt »abgeleitet« an (Sterne/Einblendung); die 16 Aktivator-Zeilen erscheinen für die abgeleiteten Features'],
], [34*mm, 108*mm]))
A(P('Zusätzlich die Spezialfälle: <b>Bewegungs-Dateien</b> (nichts heizt, kein Start-Makro) '
    'erkennt der Startnetz-Sondierer und versieht sie mit der vollen Infrastruktur. '
    '<b>V1/v4-Altdaten</b> werden beim ersten Kontakt auf den aktuellen Marker-Stand '
    'gebracht (Upgrade-Pfad mit Backup). Was der Klassifikator nicht sicher kann, bleibt '
    'unkenntlich — Thats kein Fehler, das ist die Nicht-Raten-Garantie.'))

# ============================== Kap 12 ======================================
flow += H1('12  Forensik: der Feature-Mismatch-Fall (.133)')
A(P('Feldmeldung: Pre-Print zeigte die Außenwand eines Textur-Ergebnisses als vorhanden, '
    'Live fehlte sie. Ergebnis der Untersuchung (kein Code-Fix, weil kein Repro):'))
flow += B(
 'Die Kette Basis → Textur → Range → Scale schreibt konsistente Header: nach der Textur '
 'bleibt TYPES=WALL-OUTER,WALL-INNER; Range/Scale ergänzen nur FS_*/TOTAL_LAYERS.',
 'Live- UND Pre-Print-Enables lesen beide TYPES= aus derselben _FILE_INFO (Quelle: der '
 '400-KB-Head-Peek bzw. das Replay beim Laden).',
 'Der Peek-Regex ist solide; der Push wird bei busy übersprungen (dann zeigt das Menü den '
 'Zustand der letzten Datei — Timing-Fenster zwischen Auswahl und Druckstart).',
 'Schluss fürs Feld: wenn Pre-Print und Live auseinanderfallen, Datei NEU auswählen — '
 'der Push holt die Werte sofort nach. Ein .135-Härtungsweg: den Peek-Push bei '
 'Dialog-Öffnung erzwingen, statt nur bei Dateiauswahl.')

# ============================== Kap 13 ======================================
flow += H1('13  Die Test-Map — welche Prüfung welche Stufe deckt')
A(TBL(['Stufe', 'Tests'], [
 ['Stufe 0/1  Vokabular + Kanon', 'r190_tag_ladder (neu, diese Runde): 37-Schreibweisen-Drill, Trenner-Varianten, Eliminierungsleiter, Familien-Synthesen; r81 goldens sichern die Marker-Bytes'],
 ['Stufe 2  Marker/Laufzeit', 'macro_render_test (1910 Checks, inkl. APPLY_TYPE-Interceptor-Renders), megatest (190 End-to-End-Läufe)'],
 ['Stufe 3  Klassifikator', 'r111_geom_test (Bögen/hops/Vasen), r190 (ungetaggte Familien-Synthesen), r81 pr03/pr08 (Z-Scan-Ableitung byte-stabil)'],
 ['Stufe 4  CUSTOM-Watch', 'r190 + r142_field_coverage ( CUSTOMRES-Anzeige)'],
 ['Stufe 5  Ausschluss-Logik', 'r167 aircheck (Quer-Schicht-Luft für Generatoren) — Import-Seite folgt in .135 mit eigenen Cases'],
 ['Feld-Bug-Regressionen', 'audit_sweep (82 Dateien), r140 stress (46.778 Checks, Parameter-Gitter), r141 journeys (2.372 Nutzerreisen), r187 matrix (1.356 Kombi-Prüfungen)'],
], [38*mm, 104*mm]))
A(P('Die Stufen 0–4 sind damit lückenlos im Batterie-Netz; Stufe 5 hat den Geometrie-Teil '
    '(Generatoren) und bekommt mit .135 die Import-Seite samt Sequenz-Regeln und eigenen '
    'Fehlschlägen.'))

# ============================== Kap 14 ======================================
flow += H1('14  Grenzen — ehrlich')
flow += B(
 'Brücken/Überhänge/Support-Interface werden beim IMPORT nicht abgeleitet (dokumentiert; '
 'r167 deckt die Generatoren-Seite).',
 'Ironing und Prime-Tower erkennt nur der Slicer-Tag — die Ableitung fehlt (Sequenzregeln '
 'erst .135).',
 'Bambu ;FEATURE:-Kommentare werden heute nicht gelesen (Lücke, .135: TYPE_RE erweitern).',
 'Die Reihenfolge der Features innerhalb einer Schicht ist einstellungsabhängig — sie taugt '
 'nur als weiches Signal (so nutzt sie der Klassifikator: Erstsein + Trennung + hatch, nie '
 'allein).',
 'CONF=0.7 ist fest kodiert — bewusst: lieber ein gemessenes mittleres Vertrauen als '
 'kompetitive Selbstüberschätzung. COVER zeigt den ehrlichen Anteil.')
A(Spacer(1, 6*mm))
A(Paragraph('Regelbasiert, deterministisch, nachvollziehbar — und dort, wo das System nicht '
            'sicher ist, sagt es das. Genau das ist der Unterschied zwischen Tagging und '
            'Raten.', S['end']))

doc = Doc(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..',
                       'FEATURE_TAGGING.pdf'))
doc.build(flow)
print('FEATURE_TAGGING.pdf built (%d flowables)' % len(flow))
