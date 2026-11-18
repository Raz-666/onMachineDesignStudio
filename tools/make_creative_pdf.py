#!/usr/bin/env python3
"""CREATIVE_POSSIBILITIES.pdf - was mit diesem System MACHBAR ist.

Not a reference manual (that is GENERATORS_TOOLS.pdf) and not a settings list
(that is the MANUAL). This is the idea book: concrete combinations of the
tools that ship, written as recipes you can follow at the printer tonight.

Every recipe names the real LCD paths and the real tool names, and every
recipe ends with what it honestly costs (time, material, risk) - because a
creative idea that ruins a 6-hour print is not an idea, it is a trap.
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
from reportlab.graphics.shapes import Drawing, Rect, String, Line, Circle

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
TEAL = colors.HexColor('#00706b')

S = {
 'title': ParagraphStyle('t', fontName='DVSB', fontSize=25, leading=30,
                         textColor=BLUE, alignment=1),
 'sub': ParagraphStyle('s', fontName='DVS', fontSize=13.5, leading=19,
                       textColor=GRAY, alignment=1),
 'h1': ParagraphStyle('h1', fontName='DVSB', fontSize=19, leading=25,
                      textColor=BLUE, spaceBefore=10, spaceAfter=4,
                      keepWithNext=1),
 'h2': ParagraphStyle('h2', fontName='DVSB', fontSize=14.5, leading=20,
                      textColor=PURPLE, spaceBefore=13, spaceAfter=5,
                      keepWithNext=1),
 'p': ParagraphStyle('p', fontName='DVS', fontSize=11.6, leading=17,
                     spaceAfter=6),
 'step': ParagraphStyle('st', fontName='DVS', fontSize=11, leading=16,
                        leftIndent=10, spaceAfter=3),
 'cap': ParagraphStyle('cap', fontName='DVS', fontSize=10, leading=14,
                       textColor=GRAY, alignment=1, spaceBefore=3, spaceAfter=8),
 'ts': ParagraphStyle('ts', fontName='DVSB', fontSize=9.8, leading=13,
                      textColor=colors.white),
 'tc': ParagraphStyle('tc', fontName='DVS', fontSize=9.8, leading=13.2),
 'lbl': ParagraphStyle('lbl', fontName='DVSB', fontSize=9.6, leading=13,
                       textColor=PURPLE),
 'val': ParagraphStyle('val', fontName='DVS', fontSize=10.4, leading=14.4),
}


def H1(t): return [CondPageBreak(56*mm), Paragraph(t, S['h1'])]
def H2(t): return [CondPageBreak(42*mm), Paragraph(t, S['h2'])]
def P(t): return Paragraph(t, S['p'])
def STEPS(*items):
    return [Paragraph('%d.&nbsp; %s' % (i + 1, x), S['step'])
            for i, x in enumerate(items)]


def TBL(headers, rows, widths):
    data = [[Paragraph(x, S['ts']) for x in headers]]
    for r in rows:
        data.append([Paragraph(c, S['tc']) for c in r])
    t = Table(data, colWidths=widths, repeatRows=1)
    t.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), PURPLE),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, LGRAY]),
        ('GRID', (0, 0), (-1, -1), 0.4, colors.HexColor('#c2b3e0')),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('LEFTPADDING', (0, 0), (-1, -1), 4),
        ('RIGHTPADDING', (0, 0), (-1, -1), 4),
        ('TOPPADDING', (0, 0), (-1, -1), 3),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 3)]))
    return t


def KV(rows):
    data = [[Paragraph(a, S['lbl']), Paragraph(b, S['val'])] for a, b in rows]
    t = Table(data, colWidths=[26*mm, 150*mm])
    t.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('BACKGROUND', (0, 0), (0, -1), LGRAY),
        ('BOX', (0, 0), (-1, -1), 0.4, colors.HexColor('#d5cae8')),
        ('INNERGRID', (0, 0), (-1, -1), 0.3, colors.HexColor('#d5cae8')),
        ('LEFTPADDING', (0, 0), (-1, -1), 4),
        ('TOPPADDING', (0, 0), (-1, -1), 3),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 3)]))
    return t


class Doc(BaseDocTemplate):
    def __init__(self, fn):
        super().__init__(fn, pagesize=A4, leftMargin=17*mm, rightMargin=17*mm,
                         topMargin=16*mm, bottomMargin=16*mm,
                         title='On-Machine Design Studio for Creative Freedom',
                         author='R2-D2 Macro System')
        f = Frame(self.leftMargin, self.bottomMargin, self.width,
                  self.height, id='f')
        self.addPageTemplates([PageTemplate(id='pt', frames=[f],
                                            onPage=self._deco)])

    def _deco(self, canv, doc):
        canv.saveState()
        canv.setStrokeColor(PURPLE); canv.setLineWidth(0.7)
        canv.line(17*mm, 285*mm, 193*mm, 285*mm)
        canv.setFont('DVS', 8.2); canv.setFillColor(GRAY)
        canv.drawString(17*mm, 287.2*mm,
                        'R2-D2 Macro System · On-Machine Design Studio for Creative Freedom')
        canv.drawRightString(193*mm, 287.2*mm, _R2VER)
        canv.drawCentredString(105*mm, 9.5*mm, 'Seite %d' % doc.page)
        canv.restoreState()


def cover_drawing():
    d = Drawing(450, 132)
    d.add(Rect(6, 8, 438, 116, rx=6, ry=6, fillColor=LGRAY,
               strokeColor=PURPLE, strokeWidth=1.1))
    cols = [('OBERFLÄCHE', 'Texture · Fuzzy', BLUE),
            ('LICHT', 'Lithophane', ORANGE),
            ('FARBE', 'ColorPicture · Labels', TEAL),
            ('STRUKTUR', 'Bricks · Frames · Angles', GREEN),
            ('LINIE', 'ArtisticStrings · Plotter', PURPLE)]
    x = 16
    for head, sub, col in cols:
        d.add(Rect(x, 46, 80, 54, rx=4, ry=4, fillColor=colors.white,
                   strokeColor=col, strokeWidth=0.9))
        d.add(String(x + 40, 82, head, fontName='DVSB', fontSize=7.6,
                     textAnchor='middle', fillColor=col))
        d.add(String(x + 40, 66, sub, fontName='DVS', fontSize=6.8,
                     textAnchor='middle', fillColor=colors.black))
        x += 86
    d.add(String(225, 26, 'fünf Werkzeugfamilien - unbegrenzt kombinierbar',
                 fontName='DVS', fontSize=8.6, textAnchor='middle',
                 fillColor=GRAY))
    d.add(String(225, 14, 'jedes Rezept in diesem Heft nutzt nur, was der '
                          'Drucker heute schon kann',
                 fontName='DVS', fontSize=8.0, textAnchor='middle',
                 fillColor=GRAY))
    return d


RECIPES = [
 ('Die leuchtende Struktur — Textur trifft Durchlicht', TEAL,
  'Eine Vase oder Lampe, deren Wand geprägt ist UND Licht durchlässt. Die '
  'Textur bricht das Licht an jeder Rippe, das Motiv wirkt plastisch statt '
  'flächig.',
  ['Pre-Print &gt; Mods &gt; Texture öffnen, Datei wählen, dann Vorlagen.',
   'Eine ruhige, großflächige Vorlage nehmen (z. B. „Sanfte Duenen“ oder '
   '„Wellblech“) - feine Muster verschwinden im Streulicht.',
   'Tiefe 0,4–0,6 mm, Richtung OUT, Around/Height so, dass die Rippen größer '
   'als 3 mm werden.',
   'Generate, Ergebnis als _TX-Datei prüfen, dann drucken - in Weiß oder '
   'Natur, 0,8–1,2 mm Wandstärke.',
   'Erst ein Range-Ausschnitt von 10 Schichten als Lichttest.'],
  'Wandstärke ist hier alles: unter 0,8 mm wird die Wand löchrig, über '
  '1,5 mm bleibt vom Leuchten nichts übrig.',
  'Eine Stunde für den Test, drei für das Teil - und keine Überraschung.'),

 ('Das Foto im Relief — Bildprägung auf der Wand', BLUE,
  'Ein Foto wird als Höhenkarte auf die Außenwand geprägt (Muster MAP). Bei '
  'Streiflicht von der Seite sieht man das Motiv, bei Frontallicht eine '
  'gleichmäßige Struktur - derselbe Druck, zwei Wirkungen.',
  ['Texture öffnen, Muster MAP wählen (oder die Vorlagen „Bildpraegung fein“ '
   '/ „tief“).',
   'Img: das Bild als Quelle setzen - hell = hoch, dunkel = tief.',
   'Tiefe 0,3 mm für Streiflicht, 0,6 mm für kraftvolle Wirkung; Around/'
   'Height am Objekt ausrichten.',
   'Generate und im 3D-Betrachter prüfen, ob das Motiv nicht gespiegelt ist.',
   'Auf einem zylindrischen Teil: Around groß genug, damit das Motiv nur '
   'einmal herumläuft.'],
  'Das Bild muss kontrastreich sein - eine flaue Vorlage wird zu einer '
  'gleichmäßigen Noppe.',
  'Zuerst ein 60×60-mm-Teststück; das zeigt in 12 Minuten, ob das Motiv '
  'trägt.'),

 ('Die Lampe mit Rahmen und Stand', ORANGE,
  'Eine Lithophanie-Platte, die von selbst steht: Platte plus Rahmen plus '
  'zwei Füße - das System baut alle drei Teile mit denselben Maßen.',
  ['Pre-Print &gt; Mods &gt; Lithophane: Bild, Größe und Feinheit setzen, '
   'Seitenfüße zuschalten - Generate.',
   'Das fertige Plattenmaß notieren (steht in der Antwort des Systems).',
   'Pre-Print &gt; Mods &gt; Frames: W und H auf dieses Maß plus 0,4 mm '
   'Zugabe, Tiefe = Plattenstärke plus 1 mm, Stand einschalten.',
   'Beide Dateien drucken; die Platte wird von hinten in den Rahmen gesetzt.',
   'Für Warmlicht: Platte in Natur/Weiß, Rahmen in einer dunklen Farbe - der '
   'Rahmen schluckt Streulicht.'],
  'Rahmen und Platte müssen zusammen generiert werden; 2 mm Unterschied und '
  'die Platte fällt durch.',
  'Einmal ein Rahmenset bauen und aufheben - es passt für alle Platten '
  'gleicher Größe.'),

 ('Text trifft Struktur — beschriftete Deko', GREEN,
  'Ein Objekt mit Prägung UND eingelassenem Text: das Schild ist Teil der '
  'Oberfläche, nicht aufgeklebt.',
  ['Zuerst den Körper bauen (z. B. Geometry &gt; Zylinder oder ein eigenes '
   'Modell) und die Textur darauf prägen.',
   'Dann Pre-Print &gt; Mods &gt; Labels: 1–2 Zeilen Text, Position so, dass '
   'die Schrift auf einer ungeprägten Zone landet.',
   'Mode „flush“ (flächenbündig) wählen - der Text sitzt IN der Schicht und '
   'bleibt lesbar, auch wenn später etwas abplatzt.',
   'Schriftgröße so, dass die Strichstärke mindestens zwei Düsenbreiten hat.',
   'Beide Ausgaben getrennt drucken und erst am Ende zusammenfügen, wenn das '
   'Label auf ein separates Schild soll.'],
  'Text auf einer geprägten Fläche wird unleserlich - die Prägung muss dort '
  'aufhören, wo die Schrift anfängt.',
  'Label zuerst als 30-mm-Teststück drucken: Schriftgröße und Position '
  'stimmen selten beim ersten Mal.'),

 ('Die Wand aus Bausteinen — Struktur als Konstruktion', GREEN,
  'Klemmbausteine, Winkel und Flachverbinder sind keine Spielerei: damit '
  'lassen sich Gehäuse, Halter und Aufbauten bauen, die man wieder zerlegen '
  'kann.',
  ['Pre-Print &gt; Mods &gt; Bricks: die benötigten Teile in den Kategorien '
   'wählen, Menge setzen, Create - der Satz landet als Kit.',
   'Für die Verbindung zweier Platten: Angles+Flat &gt; Mode Flach, zwei '
   'Bohrungsreihen, Wandstärke 2,4 mm.',
   'Für lösbare Verbindungen die Rastermaße einhalten (Stein 9,6 mm, Platte '
   '3,2 mm) - nicht skalieren.',
   'Passung einmal je Material einstellen, dann gilt sie für alle Teile.'],
  'Skalierte Steine passen nicht mehr zueinander. Wenn ein Teil zu stramm '
  'sitzt, ist die Passung falsch eingestellt, nicht das Maß.',
  'Ein Testdruck aus 3 Steinen und 1 Platte (6 Minuten) klärt jede '
  'Passungsfrage.'),

 ('Das Bild aus Fäden — Fadenkunst mit Fotovorlage', PURPLE,
  'Ein Foto wird zu einer Platte mit Nagelpositionen; die Linien spannen Sie '
  'selbst. Das Ergebnis ist ein Bild, das aussieht, als wäre es von Hand '
  'gemacht - weil es das ist.',
  ['Pre-Print &gt; Mods &gt; ArtisticStrings: Format wählen (9×13 für den '
   'Anfang).',
   'Bild einsetzen, Nagelabstand und Rahmen einstellen, dann Generate.',
   'Die Platte in einer dunklen Farbe drucken - der Faden soll der hellste '
   'Teil sein.',
   'Auf Papier kontrollieren, welche Linien das System vorschlägt, bevor '
   'Nägel und Faden dran sind.'],
  'Zu feiner Nagelabstand reißt die Platte beim Spannen; zu grober Abstand '
  'zerstört feine Motive.',
  'Klein anfangen: 9×13 zeigt in 20 Minuten, ob das Motiv als Fadenkunst '
  'funktioniert.'),

 ('Variationen ohne Neuslicen — eine Datei, zehn Looks', ORANGE,
  'Dieselbe G-code-Datei wird skaliert, verwindet oder spiegelt sich - und '
  'mit einer Textur bekommt jede Variante ein eigenes Gesicht.',
  ['Eine fertige Datei wählen, Pre-Print &gt; Mods &gt; Geometry tools: '
   'Scale (Faktor), Twist (Grad über die Höhe) oder Mirror.',
   'Danach Texture auf die neue Datei anwenden - jede Variante einzeln, nie '
   'die Textur zuerst.',
   'Von jeder Variante ein Range-Ausschnitt mit 8–12 Schichten als Beleg.',
   'Die gelungenen Varianten als Optimized copy backen, damit die Werte '
   'festliegen.'],
  'Twist und Scale verändern Koordinaten, nicht die Extrusion: bei starken '
  'Änderungen passen Wandabstände und Materialmenge nicht mehr.',
  'Twist nur bis etwa 30° über die ganze Höhe - darüber wird die Wand optisch '
  'schief statt elegant.'),

 ('Zerlegen statt verzichten — große Teile druckbar machen', RED,
  'Was nicht auf die Platte passt, wird geteilt: Cake cut schneidet in '
  'Scheiben, Range schneidet Schichten heraus - und die Textur läuft über die '
  'Naht weiter.',
  ['Pre-Print &gt; Mods &gt; Cake: Teilung in Scheiben oder Hälften wählen, '
   'Verbindungsflächen einschalten, Generate.',
   'Jede Scheibe einzeln texturieren - die Musterparameter für alle Scheiben '
   'gleich halten, sonst bricht das Muster an der Klebefuge.',
   'Vor dem großen Druck je Scheibe einen Range-Ausschnitt prüfen.',
   'Beim Kleben die Ausrichtung über die Naht kontrollieren.'],
  'Die Musterphase ist an die Objektgeometrie gebunden: zwei gleich '
  'texturierte Scheiben treffen an der Naht nur dann zusammen, wenn beide mit '
  'denselben Werten erzeugt wurden.',
  'Alle Scheiben in einem Rutsch generieren - die Zahlen im Kopf zu behalten '
  'endet in einer sichtbaren Naht.'),

 ('Farbe als Fläche — ColorPicture und Labels', TEAL,
  'Farbige Bilder und beschriftete Flächen aus einer Hand: derselbe Drucker '
  'legt Farbflächen und Schrift.',
  ['Pre-Print &gt; Mods &gt; ColorPicture: Bild, Farbanzahl und Feinheit '
   'setzen, Generate.',
   'Für kleine Schriftflächen zusätzlich Labels mit passender Größe bauen.',
   'Farbanzahl an die tatsächlich bestückten Filamente anpassen - jede Farbe '
   'mehr kostet Wechsel und Abfall.',
   'Erst 60×60 mm drucken: die Farbtrennung sieht man erst im Ergebnis '
   'richtig.'],
  'Mehr Farben sind nicht mehr Qualität: ab vier Farben steigt der Abfall '
  'schneller als der Eindruck.',
  'Ein Test in Originalgröße des Motivs, nicht in Miniatur - kleine Flächen '
  'verhalten sich anders.'),

 ('Werkstatt-Teile statt Deko — Kabelbinder und Dichtungen', BLUE,
  'Die unspektakulärsten Generatoren sparen am meisten Zeit: Kabelbinder und '
  'Dichtungen in genau der Größe, die man gerade braucht.',
  ['Cable ties: Länge, Breite und Lagen setzen, einen Satz als Preset '
   'speichern, dann Generate.',
   'Gaskets: Außen-/Innendurchmesser und Höhe auf das echte Maß setzen - '
   'Ironing einschalten.',
   'Die Höhe immer in ganzen Schichten wählen, sonst stimmt die Endhöhe nicht '
   'mit der Nut überein.',
   'Beide Sätze einmal als Preset sichern: die Wiederholung ist der Nutzen.'],
  'Eine Dichtung ohne Ironing trägt nicht flächig; ein zu dünner Kabelbinder '
  'reißt beim Anziehen.',
  'Kabelbinder immer im Bündel drucken - einzelne zu drucken ist reine '
  'Verschwendung.'),

 ('Vom Druck zurück zum Modell — STL-Ausgabe', GRAY,
  'Ein gedrucktes Ergebnis lässt sich wieder als Netz ausgeben: zum '
  'Weitergeben, zum Vergleich oder um es in einem anderen Programm '
  'anzusehen.',
  ['Datei wählen, Pre-Print &gt; File &gt; STL: object only.',
   'Das Ergebnis liegt in gcodes/STL/ mit der Endung .stl.gcode - in Mainsail '
   'herunterladen und die Endung .gcode entfernen.',
   'Das Netz enthält nur das Objekt: keine Stützen, kein Brim, keine '
   'Hilfsgeometrie.',
   'Bei sehr großen Dateien wird zugunsten der Ladbarkeit in Z ausgedünnt - '
   'die Wandkontur bleibt vollständig.'],
  'Das Ergebnis ist ein Netz aus Bändern, kein glattes CAD-Modell: es ist zum '
  'Ansehen und Weitergeben, nicht zum Nachkonstruieren.',
  'Ein Objekt, das man behalten will, besser gleich als Datei sichern - der '
  'Rückweg über STL ist ein Notausgang, kein Workflow.'),

 ('Erst prüfen, dann drucken — die Werkzeuge, die Zeit sparen', RED,
  'Die unsichtbaren Helfer: File check, Segment fix, Quality fix, Flow cap. '
  'Sie entscheiden, ob ein schöner Entwurf auch ein guter Druck wird.',
  ['File check laufen lassen, wenn eine Datei „unbekannt“ wirkt - es '
   'repariert die Typ-Marker.',
   'Segment fix, wenn das System eine hohe Bewegungsdichte meldet. Er legt '
   'mit steigender Toleranz nach, bis die Dauerrate unter dem MCU-Budget '
   'liegt.',
   'Flow cap setzen, wenn ein Material an seine Grenze kommt (mm³/s).',
   'Quality fix auf Dateien mit vielen Verfahrwegen: nur Wege, die '
   'Oberfläche kreuzen, behalten Z-Hop und Retract.',
   'Range-Ausschnitt als letzten Test vor dem langen Druck.'],
  'Keines dieser Werkzeuge macht ein schlechtes Modell gut - sie verhindern '
  'nur, dass ein gutes Modell am Drucker scheitert.',
  'Bei jedem neuen Material einmal File check plus Range-Ausschnitt: das '
  'kostet 15 Minuten und spart ganze Abende.'),
]


def build(path):
    doc = Doc(path)
    f = []
    A = f.append

    A(Spacer(1, 22*mm))
    A(Paragraph('On-Machine Design Studio<br/>for Creative Freedom', S['title']))
    A(Spacer(1, 3*mm))
    A(Paragraph('Kreative Möglichkeiten am Drucker - was aus ihm wird, wenn<br/>'
                'man die Werkzeuge nicht einzeln, sondern zusammen benutzt', S['sub']))
    A(Spacer(1, 9*mm))
    A(cover_drawing())
    A(Spacer(1, 7*mm))
    A(P('Ein Drucker, der nur Modelle nachfährt, ist ein Kopierer. Dieser '
        'Drucker kann Oberflächen prägen, Licht führen, Text in die Wand '
        'lassen, Bilder in Farbe legen, aus einem Foto Fadenkunst machen und '
        'Bausteine in echten Rastermaßen bauen. Dieses Heft stellt die '
        'Kombinationen vor - jedes Rezept mit den echten Wegen im Menü und '
        'ehrlichen Kosten.'))
    A(P('Die Reihenfolge ist kein Schwierigkeitsgrad. Fangen Sie mit dem an, '
        'was Sie reizt; jedes Rezept steht für sich.'))
    A(Spacer(1, 4*mm))
    A(TBL(['Werkzeugfamilie', 'Was sie liefert', 'Werkzeug'],
          [['Oberfläche', 'Haptik, Lichtbrechung, Relief', 'Texture (21 Muster, 27 Vorlagen)'],
           ['Licht', 'Bild durch Wandstärke', 'Lithophane'],
           ['Farbe', 'Flächen und Schrift', 'ColorPicture · Labels'],
           ['Struktur', 'baubare, lösbare Körper', 'Bricks · Frames · Angles+Flat'],
           ['Linie', 'Faden, Stift, Kontur', 'ArtisticStrings · Plotter'],
           ['Wiederholung', 'Varianten und Serien', 'Scale/Twist/Mirror · Profiles'],
           ['Sicherheit', 'kein Fehldruck', 'File check · Segment fix · Range']],
          [30*mm, 62*mm, 84*mm]))
    A(PageBreak())

    A(Paragraph('Zwölf Rezepte', S['h1']))
    A(P('Jedes Rezept nennt zuerst die Idee, dann die Schritte, dann was es '
        'kostet. Die Menüwege sind die, die am Drucker wirklich existieren.'))
    for title, col, idea, steps, limit, cost in RECIPES:
        f.extend(H2(title))
        A(P('<i>%s</i>' % idea))
        f.extend(STEPS(*steps))
        A(Spacer(1, 2*mm))
        A(KV([('GRENZE', limit), ('KOSTEN', cost)]))
        A(Spacer(1, 3*mm))

    f.extend(H1('Modellbau — aus Teilen wird ein Werk'))
    A(P('Modellbau am Drucker beginnt nicht mit dem großen Körper, sondern mit '
        'dem kleinsten selbsttragenden Teil. Der Grund ist banal: ein '
        'Konstruktionsfehler in einer 2-mm-Hülse kostet 8 Minuten; derselbe '
        'Fehler in einem 8-Stunden-Gehäuse kostet den Abend.'))
    A(TBL(['Baustein', 'Rolle', 'Rezept/Werkzeug'],
          [['Bricks-Kits (Hülse + Stopfen)', 'tragende Elemente, Schraubenhalter',
            'Pre-Print > Mods > Bricks, Satz bauen'],
           ['Angles+Flat-Winkel', 'Platte-an-Platte-Verbindungen, 2,4 mm Wand',
            'Pre-Print > Mods > Angles+Flat, Mode Flach'],
           ['Frames', 'Begrenzung, Abschluss, Rahmen für Platten/Litho',
            'Pre-Print > Mods > Frames, W/H mit 0,4 mm Zugabe'],
           ['Measured part / Caliper', 'Passungen messen, bevor gebaut wird',
            'Schieblehre + Tabelle „Wandstärke“ unten']],
          [46*mm, 74*mm, 56*mm]))
    A(P('<b>Toleranzen, die sich bewähren:</b> 0,2 mm bei Steckpassungen '
        '(Hülsen auf Achsen), 0,3 mm bei Klemmpassungen (Stopfen), 0 mm bei '
        'Schraubverbindungen mit Absicht (durch-Gewinde druckt sich nicht) - '
        'Schrauben kommen immer in gedruckte Gewindelöcher, nie in gedruckte '
        'Gewinde. Richtung der Layer: tragende Teile quer zur Layer-Ebene '
        'stellen, sonst bricht die Klemmstelle an der Schichtgrenze.'))
    A(P('<b>Doppel-Durchgang (manuell, ehrlich):</b> der Drucker kennt keinen '
        'Automatik-Modus „zweimal denselben Layer“. Was geht: die Deckschicht '
        'über Ironing nachglätten, Volumen über Wandanzahl erhöhen (immer vor '
        'dem Druck, im Slicer), oder dasselbe Teil zweimal drucken und '
        'verkleben. Was nicht geht: nachträglich „mehr Material“ in einen '
        'fertigen G-code zu sprühen - der Generator erzeugt Dateien, er heilt '
        'keine Geometrie.'))
    A(Spacer(1, 4*mm))

    f.extend(H1('Deko-Sets — einmal gebaut, mehrfach variiert'))
    A(P('Ein Set wirkt nur dann als Set, wenn die Teile zusammengehören: '
        'gleiche Sprache, andere Rolle. Im System entsteht das über '
        'Wiederholung mit Variation - nicht über Nachslicen.'))
    A(TBL(['Set-Idee', 'So entsteht es', 'Werkzeug'],
          [['Litho-Trio (Hell-Mittel-Dunkel)',
            'dieselbe Vorlage mit Levels 6 / 12 / 20 generieren',
            'Lithophane > Levels'],
           ['Farb-Set mit einem Bild',
            'einmal ColorPicture generieren, Bandfarben pro Teil wechseln',
            'ColorPicture > Band colors'],
           ['Textur-Serie',
            'gleiche Vorlage, anderer Seed ODER andere Tiefe je Teil',
            'Texture > Seed / Tiefe'],
           ['Bricks-Miniserie',
            'ein Kit bauen, Teile in zwei Farben drucken',
            'Bricks > Satz + Filamentwechsel'],
           ['Frame-Serie',
            'ein Rahmen-Parametersatz, drei Größen (Scale-Modifikation)',
            'Scale > Scale %']],
          [46*mm, 78*mm, 52*mm]))
    A(P('<b>Kostenwahrheit:</b> ein Set ist 1 Prototyp + N Varianten. Den '
        'Prototyp immer als Range-Ausschnitt (5–10 Schichten) testen, bevor '
        'Sie das Set drucken - ein systematischer Fehler im Grundmodell '
        'vervielfacht sich sonst mit.'))
    A(Spacer(1, 4*mm))

    f.extend(H1('Doppel-Durchgänge — was geht, was bewusst nicht geht'))
    A(TBL(['Wunsch', 'Status im System', 'Weg'],
          [['Wand zweimal überfahren (doppelt so dicht)',
            'geht — im Slicer (Wandanzahl), nicht im Generator',
            'Slicer > Wandanzahl erhöhen'],
           ['Deckfläche nachglätten',
            'geht — als Ironing-Pass auf der obersten Schicht',
            'Pre-Print > Mods > Ironing / Flow niedrig'],
           ['Gleiches Teil mit mehr Volumen',
            'geht — über Skalierung vor dem Druck',
            'Pre-Print > Mods > Scale > Scale %'],
           ['Ein zweites Mal über ein fertiges Objekt drucken',
            'geht manuell, ohne Assistent — neues Teil wählen und drucken',
            'Datei erneut drucken; Vorgang nicht automatisiert'],
           ['Automatisches „zweite Schicht überall“',
            'geht NICHT — es gibt keinen Doppel-Extrude-Modus',
            '—']],
          [62*mm, 64*mm, 50*mm]))
    A(P('Warum diese Ehrlichkeit: ein Button „Doppel-Durchgang“, der still '
        'denselben G-code doppelt druckt, ruiniert jede Vorlage mit '
        'Kalibrierung, Retracts und Layer-Zählung. Was das System tut, tut es '
        'sichtbar: als Datei, die Sie ansehen, bevor sie gedruckt wird.'))
    A(Spacer(1, 4*mm))

    A(PageBreak())
    A(Paragraph('Material, Licht und Wandstärke', S['h1']))
    A(P('Die kreativen Rezepte scheitern selten an der Software und fast immer '
        'an zwei Zahlen: der Wandstärke und der Lichtmenge. Deshalb hier die '
        'Zusammenhänge, ohne Formelkram.'))
    A(TBL(['Ziel', 'Wandstärke', 'Warum'],
          [['Durchlicht-Litho, feine Details', '0,8–1,2 mm',
            'darunter wird die Wand löchrig, darüber verliert das Bild Kontrast'],
           ['Textur mit Tiefe 0,4–0,6 mm', 'mindestens 1,2 mm',
            'die Prägung darf die Wand nicht durchstoßen'],
           ['Textur, die man tasten soll', '1,6–2,4 mm',
            'die Rippen brauchen Material, um zu tragen'],
           ['Farbflächen (ColorPicture)', '2–4 Schichten',
            'die Farbe muss decken, ohne die Kontur zu verlieren'],
           ['Bausteine/Winkel (Passung)', '2,4 mm',
            'dünner bricht an der Klemmung, dicker verliert die Toleranz'],
           ['Fadenkunst-Platte', '3–4 mm',
            'die Platte muss den Zug der Fäden halten']],
          [56*mm, 34*mm, 86*mm]))
    A(Spacer(1, 4*mm))
    A(P('<b>Licht:</b> für Durchlicht Weiß oder Natur verwenden - eingefärbtes '
        'Material schluckt genau das, was das Bild braucht. Bei Streiflicht '
        'für Reliefs zählt die Richtung der Lichtquelle mehr als ihre '
        'Helligkeit: seitlich einfallendes Licht macht aus 0,3 mm Tiefe ein '
        'sichtbares Bild.'))

    f.extend(H1('Fehlersuche und Optimierung'))
    A(P('Reihenfolge bei jedem Problem: erst die Datei (File check), dann die '
        'Parameter, dann die Maschine. Die meisten „Druckerfehler“ sind '
        'Datei- oder Parame­terfehler - der Drucker macht nur, was im Code '
        'steht. Die Meta-Regel: ein 10-Schichten-Range-Ausschnitt desselben '
        'Modells kostet 12 Minuten und zeigt 90 % aller systematischen '
        'Fehler ohne Materialverschwendung.'))
    A(TBL(['Symptom', 'Wahrscheinliche Ursache', 'Werkzeug / Schritt'],
          [['Erste Schicht haftet nicht, Ecken rollen ab',
            'Z-Offset, Betttemperatur, Zug auf der ersten Schicht',
            'Statprobe-Druck (Messkörper) für Z-Offset; Live-Bed anpassen'],
           ['Layer-Verschiebung, Bild versetzt',
            'Kollision im Code, MAXRATE zu hoch, Schrittverlust',
            'File check; MAXRATE-Warnung beachten; Achsabstände prüfen'],
           ['Überextrusion, Blobs, Fäden',
            'Flow zu hoch, Retract zu klein, Travel-Accel zu hoch',
            'Live Tuning > Flow −; Retract-Check (Fix!); Travel Accel'],
           ['Wand bricht am Clipping-Punkt',
            'Wand zu dünn für die Düse / zu wenige Wände',
            'Wandstärke-Tabelle oben; Wandanzahl erhöhen'],
           ['Textur unsichtbar / Wellen',
            'Tiefe zu klein, Richtung falsch, Wand zu dünn',
            'Texture > Tiefe 0,4–0,6 mm, Richtung OUT, Size ≥ 3 mm Rippen'],
           ['Litho durchscheinend, Kontrast flach',
            'Wandstärke zu klein oder zu groß, Levels zu grob',
            '0,8–1,2 mm Wandstärke; Levels erhöhen; Kontrast-Preset'],
           ['Farbflächen bluten ineinander',
            'Bänder zu schmal / Kontrast zu gering / zu viele Farben',
            'ColorPicture > BandH erhöhen, Kontrast hoch, 3–4 Farben statt 6'],
           ['Drucker hängt / Shutdown',
            'Watcher-Last im Homing/Probe-Fenster oder Segmentflut',
            'Log pack (Doctor) erzeugen; Segment-Fix laufen lassen; '
            'Feldblöcke beachten, bevor gedruckt wird']],
          [52*mm, 66*mm, 58*mm]))
    A(P('<b>Optimierung (Parameter, die sich rechnen):</b> zuerst Wandstärke '
        'und Layerhöhe (Kosten und Festigkeit), dann Flow und Retract (Qualität '
        'pro Schicht), zuletzt Speed/Accel (nur wenn die ersten beiden stehen). '
        'Wer Speed zuerst dreht, sucht Gründe, die er selbst erschaffen hat.'))
    A(Spacer(1, 4*mm))

    f.extend(H1('Was dieses System bewusst nicht tut'))
    A(P('Damit die Erwartungen stimmen - die folgenden Grenzen sind Absicht, '
        'keine Lücken:'))
    A(TBL(['Nicht vorhanden', 'Der Grund'],
          [['Freies 3D-Modellieren',
            'Das System arbeitet auf G-code und auf Formen mit klaren '
            'Parametern. Freie Geometrie kommt aus dem Slicer.'],
           ['Automatisches Bemalen von Modellen',
            'Farbe entsteht als Fläche (ColorPicture) oder als Schrift '
            '(Labels), nicht als Textur-Bemalung.'],
           ['Drucken ohne Bestätigung',
            'Kein Generator startet von selbst. Jedes Ergebnis ist eine '
            'Datei, die man ansehen und dann starten kann.'],
           ['Reparatur von zerstörten Binärdaten',
            'Eine als Text überschriebene STL ist nicht wiederherstellbar - '
            'das System verhindert diesen Fehler jetzt, statt ihn zu heilen.'],
           ['Geometrie aus dem Nichts',
            'Der Segment-Fix fasst zusammen, was zu klein für die Düse ist; '
            'er erfindet keine Details.']],
          [58*mm, 118*mm]))
    A(Spacer(1, 6*mm))
    A(P('<b>Der eigentliche Punkt:</b> die interessanten Ergebnisse entstehen '
        'nicht aus einem Werkzeug, sondern aus der Reihenfolge. Erst die Form, '
        'dann die Oberfläche, dann das Licht - und vor jedem langen Druck ein '
        'Ausschnitt als Beleg.'))
    A(Spacer(1, 10*mm))
    A(Paragraph('kein PC, kein 3D-Programm, keine KI — nur ein Drehrad.',
                ParagraphStyle('closing', fontName='DVSB', fontSize=17,
                               leading=24, textColor=PURPLE, alignment=1,
                               spaceBefore=8, spaceAfter=4)))

    doc.build(f)
    return path


if __name__ == '__main__':
    out = os.path.join(REPO, 'CREATIVE_POSSIBILITIES.pdf')
    build(out)
    raw = open(out, 'rb').read()
    pages = len(re.findall(rb'/Type\s*/Page[^s]', raw))
    print('[ok] CREATIVE_POSSIBILITIES.pdf: %d pages, %d recipes'
          % (pages, len(RECIPES)))
