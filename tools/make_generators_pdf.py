#!/usr/bin/env python3
"""GENERATORS_TOOLS.pdf - every generator and every file tool in one place.

The reader this is for: someone standing at the printer who knows the machine
prints well and now wants to KNOW what else it can produce. So the layout is
one block per generator, always the same five lines:

  WOHIN   the exact LCD path
  WAS     what comes out (file, folder, naming)
  WIE     the real setting rows, READ FROM menus/lcd_menues.cfg - never typed
          by hand, so the page cannot drift away from the printer
  GRENZEN what it honestly does not do
  TIPP    the one thing that saves time

The second half documents the FILE TOOLS (range, texture, scale/twist/mirror,
cake cut, segment fix, retract fix, flow cap, travel accel, quality fix,
file check, optimized copy, STL export, log pack, engine switch).

Everything is derived from the code that ships:
tools/r2_postproc.py (generator bodies, GEN_SUBDIRS), menus/lcd_menues.cfg
(the rows), macros/17_generator.cfg (presets).
"""
import os
import re

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (BaseDocTemplate, PageTemplate, Frame,
                                Paragraph, Spacer, Table, TableStyle,
                                PageBreak, CondPageBreak)
from reportlab.graphics.shapes import Drawing, Rect, String, Line

from r2_version import VERSION as _R2VER

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
FD = '/usr/share/fonts/truetype/dejavu/'
pdfmetrics.registerFont(TTFont('DVS', FD + 'DejaVuSans.ttf'))
pdfmetrics.registerFont(TTFont('DVSB', FD + 'DejaVuSans-Bold.ttf'))

BLUE = colors.HexColor('#1c4e8c'); LBLUE = colors.HexColor('#e8f0fa')
ORANGE = colors.HexColor('#e07b00'); GRAY = colors.HexColor('#58595b')
LGRAY = colors.HexColor('#f2f2f2'); GREEN = colors.HexColor('#1e7d32')
RED = colors.HexColor('#b3261e'); PURPLE = colors.HexColor('#6a3fb5')

S = {
 'title': ParagraphStyle('t', fontName='DVSB', fontSize=25, leading=30,
                         textColor=BLUE, alignment=1),
 'sub': ParagraphStyle('s', fontName='DVS', fontSize=13.5, leading=19,
                       textColor=GRAY, alignment=1),
 'h1': ParagraphStyle('h1', fontName='DVSB', fontSize=19, leading=25,
                      textColor=BLUE, spaceBefore=10, spaceAfter=3,
                      keepWithNext=1),
 'h2': ParagraphStyle('h2', fontName='DVSB', fontSize=14.5, leading=20,
                      spaceBefore=14, spaceAfter=6, keepWithNext=1),
 'p': ParagraphStyle('p', fontName='DVS', fontSize=11.6, leading=17,
                     spaceAfter=6),
 'lbl': ParagraphStyle('lbl', fontName='DVSB', fontSize=9.6, leading=13,
                       textColor=BLUE),
 'val': ParagraphStyle('val', fontName='DVS', fontSize=10.4, leading=14.4),
 'cap': ParagraphStyle('cap', fontName='DVS', fontSize=10, leading=14,
                       textColor=GRAY, alignment=1, spaceBefore=3, spaceAfter=8),
 'ts': ParagraphStyle('ts', fontName='DVSB', fontSize=9.8, leading=13,
                      textColor=colors.white),
 'tc': ParagraphStyle('tc', fontName='DVS', fontSize=9.8, leading=13.2),
}


def H1(t): return [CondPageBreak(58*mm), Paragraph(t, S['h1'])]
def H2(t): return [CondPageBreak(44*mm), Paragraph(t, S['h2'])]
def P(t): return Paragraph(t, S['p'])
def CAP(t): return Paragraph(t, S['cap'])


def TBL(headers, rows, widths):
    data = [[Paragraph(x, S['ts']) for x in headers]]
    for r in rows:
        data.append([Paragraph(c, S['tc']) for c in r])
    t = Table(data, colWidths=widths, repeatRows=1)
    t.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), BLUE),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, LBLUE]),
        ('GRID', (0, 0), (-1, -1), 0.4, colors.HexColor('#9db3cc')),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('LEFTPADDING', (0, 0), (-1, -1), 4),
        ('RIGHTPADDING', (0, 0), (-1, -1), 4),
        ('TOPPADDING', (0, 0), (-1, -1), 3),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 3)]))
    return t


def KV(rows):
    """the five-line block: label | text"""
    data = [[Paragraph(a, S['lbl']), Paragraph(b, S['val'])] for a, b in rows]
    t = Table(data, colWidths=[24*mm, 152*mm])
    t.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('BACKGROUND', (0, 0), (0, -1), LGRAY),
        ('BOX', (0, 0), (-1, -1), 0.4, colors.HexColor('#c9d6e4')),
        ('INNERGRID', (0, 0), (-1, -1), 0.3, colors.HexColor('#c9d6e4')),
        ('LEFTPADDING', (0, 0), (-1, -1), 4),
        ('TOPPADDING', (0, 0), (-1, -1), 3),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 3)]))
    return t


# ---------------------------------------------------------------- menu rows --
def _clean_name(t):
    t = t.strip().strip("'")
    if t.startswith('{') and t.endswith('}'):
        return ''
    t = re.sub(r'\{[^{}]*(\{[^{}]*\}[^{}]*)*\}', ' ', t)
    if '{' in t or '}' in t or 'printer[' in t or 'params.' in t:
        return ''                     # live template - not a setting label
    t = re.sub(r'\s+', ' ', t).strip(' :|-')
    if not t or t == '?':
        return ''
    return t[:42]


def menu_rows(branch, max_n=14):
    """the real LCD rows of one generator branch, read from the menu file"""
    src = open(os.path.join(REPO, 'menus', 'lcd_menues.cfg'),
               encoding='utf-8').read()
    out = []
    for blk in re.split(r'^\[menu ', src, flags=re.M)[1:]:
        path = blk.split(']')[0].split()
        if len(path) != 5 or path[2] != branch:
            continue
        head = blk.split('\n\n')[0]
        m = re.search(r'^name: (.+)$', head, re.M)
        if not m:
            continue
        nm = _clean_name(m.group(1))
        if not nm:
            continue
        out.append((path[4].lstrip('_'), nm))
        if len(out) >= max_n:
            break
    return out


class Doc(BaseDocTemplate):
    def __init__(self, fn):
        super().__init__(fn, pagesize=A4, leftMargin=17*mm, rightMargin=17*mm,
                         topMargin=16*mm, bottomMargin=16*mm,
                         title='R2-D2 Generatoren & Werkzeuge',
                         author='R2-D2 Macro System')
        f = Frame(self.leftMargin, self.bottomMargin, self.width,
                  self.height, id='f')
        self.addPageTemplates([PageTemplate(id='pt', frames=[f],
                                            onPage=self._deco)])

    def _deco(self, canv, doc):
        canv.saveState()
        canv.setStrokeColor(BLUE); canv.setLineWidth(0.7)
        canv.line(17*mm, 285*mm, 193*mm, 285*mm)
        canv.setFont('DVS', 8.2); canv.setFillColor(GRAY)
        canv.drawString(17*mm, 287.2*mm,
                        'R2-D2 Macro System · Generatoren & Werkzeuge')
        canv.drawRightString(193*mm, 287.2*mm, _R2VER)
        canv.drawCentredString(105*mm, 9.5*mm, 'Seite %d' % doc.page)
        canv.restoreState()


def cover_drawing():
    d = Drawing(450, 120)
    box = [('DATEI-WERKZEUGE', 'schneiden, prüfen,\nreparieren, ausgeben', BLUE),
           ('GENERATOREN', 'erzeugen Neues\naus einer Vorlage', PURPLE),
           ('KREATIV', 'kombinieren\n(siehe eigene PDF)', ORANGE)]
    x = 8
    for head, body, col in box:
        d.add(Rect(x, 30, 138, 70, rx=5, ry=5, fillColor=LGRAY,
                   strokeColor=col, strokeWidth=1.1))
        d.add(String(x + 69, 84, head, fontName='DVSB', fontSize=9.6,
                     textAnchor='middle', fillColor=col))
        for i, ln in enumerate(body.split('\n')):
            d.add(String(x + 69, 66 - i*11, ln, fontName='DVS', fontSize=8,
                         textAnchor='middle', fillColor=colors.black))
        x += 147
    d.add(Line(8, 20, 442, 20, strokeColor=GRAY, strokeWidth=0.6))
    d.add(String(225, 10, 'ein Drucker, ein Menü — alles unter Pre-Print > Mods',
                 fontName='DVS', fontSize=8.2, textAnchor='middle',
                 fillColor=GRAY))
    return d


# ------------------------------------------------------------------ content --
GEN = [
 ('__litho', 'Lithophane', 'Pre-Print &gt; Tools &gt; Lithophane',
  'Ein Bild wird zu einer Lichtplatte: die Helligkeit jedes Pixels bestimmt die '
  'Wandstärke. Gegen Licht gehalten erscheint das Foto. Ausgabe nach '
  '<b>gcodes/Litho/</b>, Name <b>Vnn_…gcode</b>.',
  'Bild wählen (Img), Größe/Feinheit einstellen, Generate. Der Rahmen und die '
  'beiden Seitenfüße sind optional zuschaltbar - die Füße greifen hinten an, '
  'damit die Platte steht, ohne dass Licht verloren geht.',
  'Nur ein Bild pro Lauf. Sehr helle Motive brauchen mehr Tiefe, sehr dunkle '
  'weniger - sonst wird die Platte ungleichmäßig durchleuchtet.',
  'Für Durchlicht PLA (oder weiß) nehmen und mit 0,8–1,2 mm Wandstärke '
  'arbeiten; das Bild nachträglich zu ändern heißt: neu generieren, nicht '
  'nachbearbeiten.'),
 ('__cpic', 'ColorPicture', 'Pre-Print &gt; Tools &gt; ColorPicture',
  'Farbige Bilder als flächiger Druck: das Motiv wird in Farbflächen zerlegt '
  'und mit den vorhandenen Filamenten gedruckt. Ausgabe nach '
  '<b>gcodes/ColorPic/</b>.',
  'Bild wählen, Farbanzahl und Feinheit setzen, Generate. Die Vorschau zeigt '
  'die Zerlegung, bevor gedruckt wird.',
  'Die Zahl der Farben ist durch die bestückten Filamente begrenzt; mehr '
  'Farben heißt mehr Wechsel und damit mehr Zeit und Abfall.',
  'Erst eine kleine Größe generieren und drucken - die Farbtrennung sieht man '
  'erst im Ergebnis richtig.'),
 ('__bricks', 'Bricks (Klemmbausteine)', 'Pre-Print &gt; Tools &gt; Bricks',
  'Konstruiert Klemmbausteine und Baugruppen in echten Rastermaßen: Steine '
  '(9,6 mm), Platten (3,2 mm), Fliesen, Schrägen, Bögen, Technik-Löcher, Runde '
  'Teile. Ausgabe nach <b>gcodes/Bricks/</b>, dazu Figuren und Kits.',
  'Teile in den Kategorien wählen (jede Wahl legt ein Teil in den Baukasten), '
  'Menge/Skalierung setzen, Create. Fertige Sätze liegen unter Kit.',
  'Toleranzen sind drucker- und materialabhängig: zu stramm = nicht steckbar, '
  'zu locker = hält nicht. Die Rastermaße sind korrekt, die Passung muss man '
  'einmal je Material einstellen.',
  'Ein Probedruck mit 3 Steinen und 1 Platte klärt die Passung schneller als '
  'jede Rechnung.'),
 ('__labels', 'Labels', 'Pre-Print &gt; Tools &gt; Labels',
  'Textschilder bis 5 Zeilen mit einstellbarer Position, Zeichenabstand, '
  'Schriftart und Größe. Der Text kann erhaben oder flächenbündig eingelassen '
  'gedruckt werden.',
  'Text tippen (Ln1…Ln5), Position/Zeichenabstand/Größe setzen, Job starten. '
  'Ausgabe nach <b>gcodes/Labels/</b>.',
  'Sehr feine Schriften und kleine Größen laufen bei 0,4-mm-Düsen zu - die '
  'Vorschau zeigt die Strichstärke, nicht die Druckbarkeit.',
  'Flächenbündig (flush) gedruckt bleibt der Text auch dann lesbar, wenn die '
  'oberste Schicht später abplatzt - die Kontur sitzt in der Schicht darunter.'),
 ('__plot', 'Plotter', 'Pre-Print &gt; Tools &gt; Plotter',
  'Zeichnet Motive mit dem Drucker als Stiftplotter: SVG, PNG/JPG, PDF oder '
  'Text werden zu Bewegungen. Ausgabe nach <b>gcodes/Plot/</b>.',
  'Modus wählen (Zeichnen/Positionieren), Seite/Nullpunkt setzen, Stift '
  'auf/ab, Geschwindigkeit, dann Start. Der Kalibrierlauf (Cal) richtet den '
  'Stift ein.',
  'Der Stift muss mechanisch montiert sein; ohne Stifthalter ist der Plotter '
  'nur eine Bewegungsvorschau.',
  'Erst Cal fahren, dann ein kleines Motiv - die Papierlage verschiebt sich '
  'sonst um Millimeter.'),
 ('__stringart', 'ArtisticStrings', 'Pre-Print &gt; Tools &gt; ArtisticStrings',
  'Fadenkunst aus Nägeln und Linien: ein Bild oder Muster wird in gerade '
  'Fadenzüge zerlegt, gedruckt wird die Platte mit den Nadelpositionen. '
  'Ausgabe nach <b>gcodes/StringArt/</b>.',
  'Format wählen (9×13 bis 18×24 oder frei), Muster oder Bild, Nagelabstand, '
  'Rahmen, Anker - dann Generate.',
  'Die Linienzahl bestimmt Druckzeit und Stabilität; ein zu grobes Raster '
  'zerstört feine Motive.',
  'Ein Foto-Motiv zuerst klein (9×13) bauen und auf Papier kontrollieren, '
  'bevor die große Platte läuft.'),
 ('__frame', 'Frames', 'Pre-Print &gt; Tools &gt; Frames',
  'Rahmen mit einstellbaren Maßen, Wandstärke, Tiefe, Rand, Eckradius, '
  'Aufhängung und Stand. Ausgabe nach <b>gcodes/Frames/</b>.',
  'W/H, Wandstärke, Tiefe, Rand und Eckradius setzen, Stand/Aufhängung '
  'zuschalten, Generate.',
  'Ein Rahmen ist ein Umriss, kein Behälter: Tiefe und Rand müssen zum '
  'Inhalt (z. B. einer Litho-Platte) passen.',
  'Für Lithos: Plattenmaß zuerst festlegen, dann den Rahmen mit 0,4 mm '
  'Zugabe auf das echte Maß bauen.'),
 ('__angle', 'Angles + Flat', 'Pre-Print &gt; Tools &gt; Angles+Flat',
  'Winkel und Flachverbinder für Platten- und Gehäusebau: Schenkelmaße, '
  'Winkelgrad, Bohrungen, Wandstärke, Infill, Ironing, Steifigkeit, Stückzahl. '
  'Ausgabe nach <b>gcodes/Angles/</b>.',
  'Mode (Winkel / Flach), Schenkellängen, Grad, Bohrungen und Wandstärke '
  'setzen, Generate.',
  'Die Bohrungen sind Durchgangslöcher, keine Gewinde; für Schrauben mit Kopf '
  'muss die Kopfsenkung mitgedacht werden.',
  'Flachverbinder mit zwei Bohrungsreihen sind die stabilste Verbindung zweier '
  'Platten - ein Winkel überträgt die Last nur an der Kante.'),
 ('__cable', 'Cable ties', 'Pre-Print &gt; Tools &gt; Cable ties',
  'Kabelbinder in parametrischer Länge und Breite, mehrlagig, mit '
  'Brim-Option; gespeicherte Sätze als Presets. Ausgabe nach '
  '<b>gcodes/CableTies/</b>.',
  'Count, Länge, Breite, Lagen, Schichthöhe, Variante und Brim setzen, Save '
  'als Preset oder direkt Generate.',
  'Die Zugfestigkeit hängt am Material und an der Lagezahl, nicht an der '
  'Länge - zu dünn gesetzt reißen sie beim Anziehen.',
  'Immer ein Bündel drucken: eine Stange Kabelbinder kostet Minuten, einzelne '
  'sind Verschwendung.'),
 ('__seal', 'Gaskets', 'Pre-Print &gt; Tools &gt; Gaskets',
  'Dichtungen als Ring: Außendurchmesser, Innendurchmesser, Höhe, Profil, '
  'Ironing und Schichthöhe. Ausgabe nach <b>gcodes/Gaskets/</b>.',
  'OD/ID/Höhe und Profil setzen, Ironing zuschalten, Save oder Generate.',
  'Eine Dichtung ist nur so dicht wie ihre Oberfläche: ohne Ironing bleibt die '
  'Oberkante rau und trägt nicht flächig.',
  'Ironing an und die Höhe in ganzen Schichten wählen - sonst stimmt die '
  'Endhöhe nicht mit der Nut überein.'),
 ('__shape', 'Geometry (Formen)', 'Pre-Print &gt; Tools &gt; Geometry',
  'Grundkörper und Sonderformen: Würfel, Zylinder, Konus, Rohr, Ring, '
  'Prisma, Stern, Pyramide und weitere - als Ausgangspunkt für eigene Teile.',
  'Form wählen, Maße, Wandstärke und Infill setzen, Generate. Ausgabe nach '
  '<b>gcodes/Shapes/</b>.',
  'Die Formen sind Volumenkörper mit gleichmäßigen Wänden, keine '
  'Freiform-Modellierung.',
  'Ein Grundkörper plus Texture ist oft schneller ein „fertiges“ Dekoteil als '
  'jeder Modell-Import.'),
]

TOOLS = [
 ('Range (Ausschnitt)', 'Pre-Print &gt; File &gt; Range',
  'Schneidet aus einer großen Datei einen Schichtbereich heraus - als '
  'eigenständiger Druck mit Sockel, Brim und sauberem Ende. Ideal für '
  'Materialproben und Passungstests, ohne 6 Stunden zu drucken.',
  'Ein Ausschnitt ist ein neues Bauteil: der Sockel und die Kappschichten '
  'kosten Material, die Kontur ist an der Schnittkante nicht die des '
  'Originalteils.'),
 ('Texture', 'Pre-Print &gt; Tools &gt; Texture',
  'Prägt eine Struktur auf die Außenwand: 27 Muster, 27 fertige Vorlagen, '
  'Fuzzy-Skin, Tiefe in mm, Richtung innen/außen, Seed. Schreibt eine neue '
  '_TX-Datei, startet nie von selbst.',
  'Textur lebt von der Wandstärke: bei sehr dünnen Wänden frisst die Tiefe die '
  'Wand, bei sehr dicken sieht man sie kaum.'),
 ('Scale / Twist / Mirror', 'Pre-Print &gt; Tools &gt; Geometry tools',
  'Skalieren, Verwinden und Spiegeln einer fertigen G-code-Datei. Aus einer '
  'Vorlage werden Varianten, ohne neu zu slicen.',
  'Alle drei arbeiten auf Koordinaten: bei sehr großen Änderungen passen '
  'Extrusionsmengen und Wandabstände nicht mehr zueinander.'),
 ('Toolchain (Effektkette)', 'Pre-Print &gt; Tools &gt; Toolchain',
  'Kettet Werkzeuge zu einem Ablauf: ein JSON-Preset (das Beispiel '
  'scale-twist.json liegt im Ordner Toolchain/) beschreibt die Schritte - '
  'jedes Werkzeug füttert das nächste, alles läuft als EIN Hintergrundjob, '
  'am Ende bleibt nur die letzte Ausgabe: '
  'V&lt;nn&gt;_&lt;Name&gt;_&lt;PresetTag&gt;.gcode im Ordner Toolchain/. '
  'Preset im SD-Browser anklicken, Apply 2x drücken - der Fortschritt läuft '
  'als Chain n/N &lt;Werkzeug&gt; über das Display.',
  'Kettbar sind Range, Scale, Texture, Twist und Mirror - Cake cut nicht '
  '(zwei Ausgabedateien, Hand-Ubergabe). Presets entstehen am PC/Mainsail '
  'als .json; am Display kann man sie nur laden und löschen. Während der '
  'Kette verweigert jeder Druckstart (Wait: generating).'),
 ('Cake cut', 'Pre-Print &gt; Tools &gt; Cake',
  'Zerteilt ein Modell in druckbare Scheiben oder Hälften mit '
  'Verbindungsflächen, damit große Teile auf den Druckraum passen.',
  'Schnittflächen sind eben; Hinterschneidungen am Schnitt bleiben Sache des '
  'Modells.'),
 ('Segment fix', 'Pre-Print &gt; File &gt; Segment fix',
  'Verschmilzt Mikro-Segmente, die die MCU-Zeitplanung überlasten können. '
  'Arbeitet mit einer Chord-Toleranz (0,12 bis 0,50 mm) und legt so lange '
  'nach, bis die <b>Dauerrate</b> unter dem MCU-Budget von ~450 moves/s liegt. '
  'R253: der Parser liest Tokens in beliebiger Reihenfolge - die '
  'Spiralvasen-Schreibweise (Z zuerst) wird jetzt erkannt.',
  'Er ersetzt keine Geometrie: was zu klein für die Düse ist, wird '
  'zusammengefasst; echte Details bleiben stehen, wenn sie größer als die '
  'Toleranz sind.'),
 ('Retract fix', 'Pre-Print &gt; File &gt; Retract fix',
  'Schreibt Retract-Paare auf G10/G11 um, damit die aktuellen '
  'Rückzugs-Einstellungen greifen.',
  'Nur saubere Paare werden umgeschrieben - Wischbewegungen bleiben '
  'unangetastet.'),
 ('Flow cap', 'Pre-Print &gt; File &gt; Flow cap',
  'Begrenzt Moves auf einen volumetrischen Grenzwert (mm³/s), damit die '
  'Hotend-Grenze nicht überschritten wird.',
  'Es kappt nach oben; zu kalt oder zu schnell bleibt trotzdem schlecht '
  'druckbar.'),
 ('Travel accel', 'Pre-Print &gt; File &gt; Travel accel',
  'Setzt eigene Beschleunigung und Geschwindigkeit für Verfahrwege - '
  'Druck-Accel bleibt unberührt.',
  'Sehr hohe Werte übertragen Riemen und Rahmen: es ist eine '
  'Zeitoptimierung, keine Qualitätsverbesserung.'),
 ('Quality fix', 'Pre-Print &gt; File &gt; Quality fix',
  'Setzt die Quality-Regel durch: nur Verfahrwege, die gedruckte Oberfläche '
  'KREUZEN, behalten Z-Hop und Retract; durch Infill darf direkt verbunden '
  'werden.',
  'Es arbeitet auf markierten Dateien; ohne Feature-Marker bleibt es '
  'konservativ.'),
 ('File check / RETAG', 'System &gt; File check',
  'Prüft Dateien auf fehlende oder falsche Typ-Marker und schreibt sie neu - '
  'die Grundlage dafür, dass Overrides und Werkzeuge die Datei verstehen.',
  'Ein RETAG ändert nur Kommentare, nie Bewegungen.'),
 ('Optimized copy', 'Pre-Print &gt; File &gt; Optimized',
  'Erzeugt eine Tuning-Kopie einer Datei mit gebackenen Einstellungen '
  '(Geschwindigkeit, Fluss, Beschleunigung), ohne das Original anzufassen.',
  'Eine Kopie ist ein Stand: spätere Änderungen an den Pre-Print-Werten '
  'wirken nicht in die Kopie hinein.'),
 ('STL-Export', 'Pre-Print &gt; File &gt; STL: object only',
  'Baut aus einer gedruckten Datei wieder ein Netz: nur das Objekt, ohne '
  'Stützen, Skirt, Brim, Turm und Hilfsgeometrie. Praktisch, um ein Ergebnis '
  'weiterzugeben oder in einem anderen Programm zu prüfen.',
  'Das Ergebnis ist ein Netz aus Bändern, kein glattes CAD-Modell. Ist die '
  'Datei sehr komplex, wird zugunsten der Viewer-Ladbarkeit in Z ausgedünnt.'),
 ('LOG PACK', 'System &gt; Diagnostics &gt; Log pack',
  'Sammelt Versionen, Dienst-Status, die Klipper-Vorfälle und die letzten '
  'Log-Megabyte in EINE Datei - ohne SSH, direkt aus dem Menü.',
  'Es schreibt nur, solange nicht gedruckt wird.'),
 ('Post-Processor-Schalter', 'System &gt; Post-Processor',
  'Schaltet zwischen dem stabilen und dem experimentellen Postprozessor um, '
  'mit sofortigem Rückweg. Der Rückweg bleibt immer möglich.',
  'Der Schalter gilt ab dem nächsten Start; ein kaputter Experimentalstand '
  'hält den stabilen nicht auf.'),
]


def build(path):
    doc = Doc(path)
    f = []
    A = f.append

    # ---- cover ------------------------------------------------------------
    A(Spacer(1, 24*mm))
    A(Paragraph('Generatoren &amp; Werkzeuge', S['title']))
    A(Spacer(1, 4*mm))
    A(Paragraph('Was dieser Drucker außer Drucken noch kann -<br/>'
                'jedes Werkzeug an seinem Platz, mit seinen echten Werten',
                S['sub']))
    A(Spacer(1, 10*mm))
    A(cover_drawing())
    A(Spacer(1, 8*mm))
    A(P('Dieses Heft beantwortet zwei Fragen: <b>„Wie mache ich X?“</b> und '
        '<b>„Was kann das System überhaupt?“</b> Der erste Teil führt durch '
        'alle Generatoren - Werkzeuge, die aus einer Vorlage etwas NEUES '
        'bauen. Der zweite Teil durch die Datei-Werkzeuge, die vorhandene '
        'G-codes prüfen, reparieren, zerteilen oder ausgeben.'))
    A(P('Die Einstellungstabellen sind aus dem Menü des Druckers gelesen, '
        'nicht abgetippt: was hier steht, ist die Zeile, die Sie am LCD '
        'sehen. Die kreativen Kombinationen dieser Werkzeuge stehen im '
        'Schwesterheft <b>Kreative Möglichkeiten</b>.'))
    A(Spacer(1, 5*mm))
    A(TBL(['Wohin die Ergebnisse gehen', 'Ordner'],
          [['Alle generierten Dateien', 'gcodes/&lt;Werkzeug&gt;/ · Name Vnn_…gcode'],
           ['Bereichs-Ausschnitte', 'gcodes/Range/'],
           ['Texturen', 'gcodes/Texture/'],
           ['STL-Ausgaben', 'gcodes/STL/ · Endung .stl.gcode (nur zum Herunterladen)'],
           ['Optimierte Kopien', 'gcodes/optimized/'],
           ['Log-Pakete', 'gcodes/crash_archive/R2-DOCTOR-…']],
          [70*mm, 106*mm]))
    A(PageBreak())

    # ---- generators -------------------------------------------------------
    A(Paragraph('Teil 1 · Die Generatoren', S['h1']))
    A(P('Elf Generatoren unter <b>Pre-Print &gt; Mods</b> (dazu die '
        'Dateiliste „Gen files“, die zeigt, was gebaut wurde). Jeder Eintrag ist '
        'gleich aufgebaut: wohin, was herauskommt, welche Zeilen Sie am LCD '
        'wirklich sehen, wo die Grenzen liegen und der eine Tipp, der Zeit '
        'spart.'))
    for key, name, path_, what, how, limits, tip in GEN:
        f.extend(H2(name))
        A(KV([('WOHIN', path_),
              ('WAS', what),
              ('WIE', how)]))
        rows = menu_rows(key, max_n=10)
        if rows:
            A(Spacer(1, 3*mm))
            A(TBL(['LCD-Zeile', 'Beschriftung am Drucker'],
                  [[k, v] for k, v in rows], [26*mm, 150*mm]))
        A(Spacer(1, 2*mm))
        A(KV([('GRENZEN', limits), ('TIPP', tip)]))
        A(Spacer(1, 4*mm))

    A(PageBreak())
    # ---- tools ------------------------------------------------------------
    A(Paragraph('Teil 2 · Die Datei-Werkzeuge', S['h1']))
    A(P('Diese Werkzeuge bauen nichts Neues aus einer Vorlage - sie arbeiten '
        'an einer vorhandenen G-code-Datei: prüfen, reparieren, zerteilen, '
        'verändern, ausgeben. Alle sind minimal-invasiv: die Quelldatei wird '
        'gelesen, das Ergebnis ist eine neue Datei oder eine Kopie mit '
        'Kennzeichnung.'))
    for name, where, what, limits in TOOLS:
        f.extend(H2(name))
        A(KV([('WOHIN', where), ('WAS', what), ('GRENZEN', limits)]))
        A(Spacer(1, 3*mm))

    A(PageBreak())
    # ---- appendix ---------------------------------------------------------
    A(Paragraph('Anhang · Was Sie beim Suchen und Wiederfinden wissen müssen',
                S['h1']))
    f.extend(H2('Dateinamen'))
    A(P('Jede erzeugte Datei beginnt mit einer laufenden Nummer: '
        '<b>V33_LampOpenE27_TX.gcode</b> heißt Version 33. Die Nummer ist '
        'kein Datum, sondern ein Zähler - die höchste Nummer ist die jüngste '
        'Version desselben Motivs.'))
    f.extend(H2('Ordner am LCD'))
    A(P('Klipper zeigt am LCD nur den Wurzelordner der G-codes. Damit die '
        'Unterordner trotzdem erreichbar sind, legt das System <b>Links im '
        'Wurzelordner</b> an - ein Tippen auf den Link führt in den Ordner. '
        'Die Links sind reine Zeiger: sie werden nie mitgedruckt und nie '
        'bearbeitet.'))
    f.extend(H2('Warteschlange'))
    A(P('Generatoren laufen im Hintergrund. Die Warteschlange steht im '
        'Hauptmenü („Gen queue: N waiting“), jede fertige Datei erscheint '
        'sofort in ihrem Ordner, und ein laufender Druck hat immer Vorrang '
        'vor einem Generator.'))
    f.extend(H2('Warum manche Werkzeuge warnen'))
    A(P('Ein Werkzeug, das eine Datei nicht versteht, sagt das - es rät nicht. '
        'Die häufigsten drei Meldungen und was sie bedeuten:'))
    A(TBL(['Meldung', 'Bedeutung'],
          [['„no object extrusion found“',
            'Die Datei enthält keine als Objekt erkannte Wand (nur Stützen, '
            'Brim oder ungetaggte Blöcke). Erst File check laufen lassen.'],
           ['„still carries N moves/s“',
            'Der Segment-Fix konnte nicht weiter zusammenfassen - die kurzen '
            'Moves liegen nicht nebeneinander. Geschwindigkeit senken.'],
           ['„only while idle“',
            'Das Werkzeug schreibt auf die SD-Karte und läuft deshalb nur, '
            'wenn nicht gedruckt wird.']],
          [58*mm, 118*mm]))
    A(Spacer(1, 6*mm))
    A(P('<b>Ein Satz zum Schluss:</b> kein Generator startet von selbst. '
        'Jedes Ergebnis ist eine Datei, die Sie ansehen und dann bewusst '
        'starten können.'))
    doc.build(f)
    return path


if __name__ == '__main__':
    out = os.path.join(REPO, 'GENERATORS_TOOLS.pdf')
    build(out)
    from reportlab.pdfgen import canvas  # noqa: F401  (page count via reader)
    import re as _re
    raw = open(out, 'rb').read()
    pages = len(_re.findall(rb'/Type\s*/Page[^s]', raw))
    print('[ok] GENERATORS_TOOLS.pdf: %d pages, %d generators, %d tools'
          % (pages, len(GEN), len(TOOLS)))
