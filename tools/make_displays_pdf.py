#!/usr/bin/env python3
"""DISPLAYS_WEB_UI.pdf — the .135 overview round (user request): how the
system behaves with OTHER DISPLAYS, the honest assessment + IMPLEMENTATION
of the web-UI-as-LCD-companion, Klipper-capable printers (incl. CoreXY),
build volumes, and the nozzle matrix 0.2-1.0 — plus the test tiers and the
field-bug classes. Content basis: DISPLAYS_DRUCKER_TESTS.md (.134 version,
updated), web/ (r2_menu.py, index.html, menu_structure.json),
tools/menu_json_export.py, tools/r197_gen_sweep.py, tools/r198_tier_report.py,
macros (SYNC_GANTRY, _bed_limits, _nozzle_diameter), R106 minimal-printer
sweep."""
import os

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
    data = [[Paragraph(h, S['ts']) for h in headers]]
    for r in rows:
        data.append([Paragraph(c, S['tc']) for c in r])
    t = Table(data, colWidths=widths, repeatRows=1)
    t.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), BLUE),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, LBLUE]),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#b9c6d8')),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('LEFTPADDING', (0, 0), (-1, -1), 5),
        ('RIGHTPADDING', (0, 0), (-1, -1), 5),
        ('TOPPADDING', (0, 0), (-1, -1), 3.5),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 3.5),
    ]))
    return t


def d_webui():
    d = Drawing(430, 168)
    def box(x, y, w, h, head, body, fc=LBLUE, tc=BLUE):
        d.add(Rect(x, y, w, h, rx=4, ry=4, fillColor=fc,
                   strokeColor=tc, strokeWidth=1))
        d.add(String(x + w / 2, y + h - 13, head, fontName='DVSB',
                     fontSize=8.6, textAnchor='middle', fillColor=tc))
        for i, ln in enumerate(body):
            d.add(String(x + w / 2, y + h - 25 - i * 10.5, ln, fontName='DVS',
                         fontSize=7.8, textAnchor='middle', fillColor=colors.black))
    def arr(x1, y1, x2, y2, lbl=''):
        d.add(Line(x1, y1, x2, y2, strokeColor=GRAY, strokeWidth=1.2))
        if lbl:
            d.add(String((x1 + x2) / 2, (y1 + y2) / 2 + 4, lbl, fontName='DVS',
                         fontSize=7.4, fillColor=GRAY))
    box(20, 108, 120, 52, 'lcd_menues.cfg', ['2.272 Sektionen', 'EINE Wahrheit', '1.910 Render-Tests'], LGRAY, GRAY)
    box(170, 108, 120, 52, 'menu_json_export.py', ['parsen → Baum → JSON', '2272 Knoten, sha256', '--embed für die Seite'], LBLUE, BLUE)
    box(320, 108, 96, 52, 'menu_structure.json', ['Struktur + Meta', '(web/)'], LGRAY, GRAY)
    box(320, 34, 96, 52, 'r2_menu.py', ['Moonraker-Extension', '/server/r2_menu/', 'tree · status · live'], LBLUE, TEAL)
    box(120, 34, 150, 52, 'web/index.html', ['LCD-artige Navigation', 'embedded JSON fallback', 'live: fetch() zum Host'], LBLUE, PURPLE)
    box(20, 34, 70, 52, 'Browser', ['Handy / PC /', 'Tablet'], LGRAY, GRAY)
    arr(140, 134, 170, 134)
    arr(290, 134, 320, 134)
    arr(368, 108, 368, 86, 'serve')
    arr(320, 60, 270, 60, 'fetch /script')
    arr(120, 60, 90, 60, 'HTML')
    return d


class Doc(BaseDocTemplate):
    def __init__(self, fn):
        super().__init__(fn, pagesize=A4,
                         leftMargin=17*mm, rightMargin=17*mm,
                         topMargin=16*mm, bottomMargin=16*mm,
                         title='R2-D2 Displays, Web-UI, Drucker, Nozzles — die .135-Übersicht',
                         author='R2-D2 Macro System')
        f = Frame(self.leftMargin, self.bottomMargin, self.width, self.height, id='f')
        self.addPageTemplates([PageTemplate(id='pt', frames=[f], onPage=self._deco)])

    def _deco(self, canv, doc):
        canv.saveState()
        canv.setStrokeColor(BLUE); canv.setLineWidth(0.7)
        canv.line(17*mm, 285*mm, 193*mm, 285*mm)
        canv.setFont('DVS', 8.2); canv.setFillColor(GRAY)
        canv.drawString(17*mm, 287.2*mm, 'R2-D2 Macro System · Displays · Web-UI · Drucker · Nozzles · Test-Stufen')
        canv.drawRightString(193*mm, 287.2*mm, 'R2-2026-11-09.136ai')
        canv.setFont('DVS', 8.6)
        canv.drawCentredString(105*mm, 9.5*mm, 'Seite %d' % doc.page)
        canv.restoreState()


OUT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                   'DISPLAYS_WEB_UI.pdf')
doc = Doc(OUT)
flow = []
A = flow.append

# ================================ cover =====================================
A(Spacer(1, 24*mm))
A(Paragraph('Displays, Web-UI, Drucker, Nozzles', S['title']))
A(Spacer(1, 5*mm))
A(Paragraph('die ausführliche Übersicht der .135-Runde —<br/>'
            'inklusive der gebauten Web-UI-Empfehlung und der Test-Stufen', S['sub']))
A(Spacer(1, 8*mm))
A(Spacer(1, 1))
A(Spacer(1, 6*mm))
A(Paragraph('Stand: R2-2026-11-09.136ai · Grundlagen: menus/lcd_menues.cfg, web/ (r2_menu.py, '
            'index.html, menu_structure.json), tools/menu_json_export.py · r197_gen_sweep.py · '
            'r198_tier_report.py', S['cap']))
A(PageBreak())

# ================================ Kap 1 =====================================
flow += H1('1  Andere Displays — die Lage')
A(P('Die komplette R2-Menüstruktur lebt in der Klipper-Menü-Engine: <b>menus/lcd_menues.cfg</b>, '
    '2.272 Sektionen (303 Listen, 1.373 Befehle, 596 Eingaben), Jinja-gerendert, von 1.910 '
    'Render-Tests abgesichert. Nur Displays, die diese Engine ansprechen, zeigen die Struktur 1:1:'))
A(TBL(['Display', 'Technik', 'R2-Menüs', 'Rolle'], [
 ['<b>12864-LCD</b> (ST7920/UC1701, verbaut)', 'Klipper [display] + [menu]', '<b>vollständig</b> — alle Punkte live', 'Primärsteuerung am Gerät'],
 ['<b>Mainsail / Fluidd</b> (Browser)', 'Moonraker', 'nein (eigene UI) — jeder R2-Befehl ist Makro-tauglich', 'Zweitdisplay, Dateien, Konsole'],
 ['<b>KlipperScreen</b> (Touch)', 'eigene UI-Schicht', 'nein — rendert keine [menu]-Sektionen; Items kuratierbar', 'nur mit Auswahl sinnvoll'],
 ['<b>Web-LCD</b> (diese Runde, web/index.html)', 'Moonraker + JSON-Export', '<b>Menü-Baum 1:1</b> (Struktur; Befehle sendbar)', 'Zweitdisplay im LCD-Look'],
 ['HDMI + OctoPrint o. ä.', 'fremde Stacks', 'nein', 'nicht empfohlen'],
], [40*mm, 32*mm, 56*mm, 42*mm]))
A(P('Der entscheidende Fakt: Mainsail/Fluidd und KlipperScreen <i>können</i> alle Makros '
    'aufrufen (jedes trägt description:), aber sie <i>bauen</i> die Menüs nicht nach. Genau '
    'diese Lücke schließt der Web-LCD-Weg — ohne einen zweiten Menü-Stack zu erschaffen.'))

flow += H2('1.1  Display-Parität im Alltag')
A(TBL(['Aufgabe', 'LCD', 'Mainsail', 'Web-LCD'], [
 ['Druck starten (AS SLICED / AS LEGACY)', 'Start-Menü', 'Makro-Knopf', 'Start-Menü (sendbar)'],
 ['Pre-Print-Overrides setzen', 'voll', 'Konsole/Makros', 'Struktur sichtbar, Werte live im LCD'],
 ['Live-Tuning während des Drucks', 'voll', 'Makros', 'Struktur sichtbar, Befehle sendbar'],
 ['Generatoren starten', 'voll', 'Makros', 'Struktur sichtbar, Befehle sendbar'],
 ['Dateien verwalten / G-Code-Viewer', '—', '<b>gewonnen</b>', '— (Mainsail-Aufgabe)'],
], [58*mm, 26*mm, 36*mm, 50*mm]))
A(P('Faustregel: Das LCD bleibt die Primärsteuerung mit echten Live-Werten. Mainsail gewinnt '
    'bei Dateien, Viewer und Fernzugriff. Das Web-LCD ist die Brücke: derselbe Baum, '
    'LCD-artige Navigation, vom Couch-Tisch.'))

# ================================ Kap 2 =====================================
flow += H1('2  Die Web-UI-Empfehlung — jetzt GEBAUT')
A(P('Meine Einschätzung aus der .134-Runde war eindeutig: <b>keinen eigenen Web-UI-Stack '
    'bauen</b> (Mainsail existiert und gewinnt durch Existenz), stattdessen der Mittelweg — '
    'eine Moonraker-Extension, die die Menüstruktur als JSON exponiert. .135 setzt genau '
    'das um (R196):'))
A(d_webui())
A(CAP('Abb. 1 — die Web-UI-Architektur: eine Wahrheit (lcd_menues.cfg), ein Export, ein Endpunkt'))
A(TBL(['Baustein', 'Datei', 'Was er tut'], [
 ['Exporter', 'tools/menu_json_export.py', 'lcd_menues.cfg → menu_structure.json (Baum, Typen, rohe Jinja-Templates, G-Codes, input-Bereiche, sha256); --embed injiziert das JSON in die Seite'],
 ['Extension', 'web/r2_menu.py', 'Moonraker-Komponente: GET /server/r2_menu/tree · /status · /live (gefilterter Drucker-Snapshot, 1 s Cache) · POST /refresh; mtime-frisch, Deadlock-frei (R197-Fix)'],
 ['Seite', 'web/index.html', 'LCD-artige Navigation (Breadcrumb, Untermenüs, Detail-Panel); wertet seit .136 die Templates LIVE aus (eigener Jinja-Evaluator im Single-Brace-Dialekt, 3 s Poll gegen /live, Enable-Conditions blenden Zeilen aus wie das LCD); fällt auf das eingebettete JSON zurück; Befehle gehen an /printer/gcode/script'],
 ['Test', 'tools/r197_gen_sweep.py (T1-T5)', 'Baumvollständigkeit, Embed-Roundtrip, Fake-Moonraker-Endpoint-Tests, Dialog-Peek-Anker, .135-Code-Anker'],
], [22*mm, 44*mm, 100*mm]))
flow += H2('2.1  Installation (einmalig)')
A(CODE('cp web/r2_menu.py ~/moonraker/moonraker/components/r2_menu.py\n'
       '# moonraker.conf ergänzen:\n'
       '[r2_menu]\n'
       'path: ~/klipper-e3-r2d2/web/menu_structure.json\n'
       'sudo systemctl restart moonraker\n'
       '# Export aktualisieren nach Menü-Änderungen:\n'
       'python3 tools/menu_json_export.py            # + --embed web/index.html'))
flow += H2('2.2  Meine ehrliche Einschätzung des Ergebnisses')
flow.extend(B(
 '<b>Was gut ist:</b> die Menü-Wahrheit bleibt EINMAL vorhanden (lcd_menues.cfg + 1.910 '
 'Render-Tests). Der Export ist deterministisch, ~100 Zeilen Extension, kein eigener '
 'Polling-Stack, keine zweite Zustandshaltung — Drift ist konstruktiv ausgeschlossen.',
 '<b>Was die Seite heute kann:</b> den kompletten Baum navigieren (genau wie am 12864: '
 'eine Ebene, Breadcrumb, Typenkennung), Details je Eintrag (Name/Enable/G-Code/Input-'
 'Bereich als rohe Templates), und auf dem Drucker-Host Befehle direkt senden '
 '(Moonrakers eigene /printer/gcode/script-Schnittstelle).',
 '<b>Was seit .136 dazugekommen ist:</b> die Seite wertet die Jinja-Templates selbst '
 'aus — ein eigener Evaluator im exakten LCD-Dialekt (Single-Brace, Python-Semantik: '
 'and/or liefern Operanden, negative Indizes, Slices, Tupel, %-Format, Float-Darstellung '
 '0.0), gespeist aus dem neuen /server/r2_menu/live-Snapshot (alle gcode_macro-Objekte + '
 'save_variables, fette Listen wie der SD-Baum werden abgeschnitten und benannt — Bytes '
 'statt Kilobytes pro Poll auf dem Pi Zero). Der Kreuzcheck: 209 dynamische Menünamen + '
 '120 Enable-Bedingungen, gerendert vom ECHTEN ausgelieferten JavaScript (node) und von '
 'jinja2 — 100% Übereinstimmung mit der LCD-Wahrheit. Was bewusst fehlt: kein Websocket-'
 'Strom (3 s Poll reicht), keine Datei-Verwaltung (Mainsails Job). Sie ist ein Spiegel, '
 'kein zweites Gehirn.',
 '<b>Einordnung:</b> als Zweitdisplay neben dem LCD ist sie sofort nützlich (vom Tisch '
 'durch die Menüs, Befehle absetzen). Als Mainsail-Ersatz ist sie nicht gedacht — Datei-'
 'Verwaltung, Viewer und Heizungs-Kacheln bleiben Mainsails Job. Genau das war der Plan: '
 'Brücke, kein Duopol.',
))
A(P('Und der Nebeneffekt lohnt allein: der JSON-Export ist jetzt ein <b>strukturtest</b>. '
    'Der Sweep prüft Baumvollständigkeit und Waisen — und genau dabei fiel der Menü-Bug '
    'dieser Runde auf (Kap. 8).'))

# ================================ Kap 3 =====================================
flow += H1('3  Andere Drucker — Portabilität und CoreXY')
A(P('Das System ist Makro- und Config-getrieben; transportabel über Werte, nicht über Code:'))
A(TBL(['Was', 'Wo konfiguriert', 'Wirkung'], [
 ['Bett/Bauraum', '_bed_limits / _R2_CONFIG (01_state.cfg)', 'Generatoren platzieren + passen alles ins Bett; Warntexte rechnen mit den echten Grenzen'],
 ['Düse', '_nozzle_diameter aus printer.cfg', 'EINE Wahrheit für alle Generatoren: Linienbreite, E-Mengen, Hatch-Abstände skalieren mit'],
 ['Kinematik', 'printer.cfg ([printer] kinematics)', 'Makros sind kinematik-agnostisch; CoreXY: SYNC_GANTRY bleibt unangetastet, ISHAPER A/B-Profile'],
 ['Filament/Presets', '05_materials.cfg', 'unverändert portabel'],
 ['R106-Minimal-Drucker-Sweep', 'tools/r140_stress (Szenarien)', '1.690 Expressions / 315 Makros auf einem Minimal-Drucker ohne Extruder-Objekt = Portabilitätsbeweis'],
], [34*mm, 52*mm, 80*mm]))
A(P('<b>CoreXY</b> braucht keine Sonderbehandlung: die Makros fahren G0/G1, nie Gcode-'
    'Kinematik-Annahmen; SYNC_GANTRY (Gleichlauf der beiden Z-Motoren) wird vom System '
    'nicht umgangen; ISHAPER-Profile A/B (Runden/Ausgleich) lassen sich wie am Ender '
    'schalten. <b>Bauraum:</b> alles, was die Generatoren tun, läuft über _bed_limits — '
    'ein 300×300×350-Kernxy nimmt die gleichen Dateien, nur die Platzierung rechnet anders.'))

flow += H2('3.1  Nozzle-Matrix (0.2 / 0.4 / 0.6 / 0.8 / 1.0)')
A(TBL(['Düse', 'Linienbreite (×1.08)', 'Generatoren verhalten sich', 'Wächter'], [
 ['0.2', '0.22 mm', 'feinste Struktur; Hatch-Abstände schrumpfen mit', 'MAXRATE-Wächter warnt bei Mikro-Segmenten'],
 ['0.4', '0.43 mm', 'Standardklasse', '—'],
 ['0.6 (verbaut)', '0.65 mm', 'Referenzkonfiguration — alle Goldens hier', '—'],
 ['0.8', '0.86 mm', 'breite Linien, schnellere Böden', '—'],
 ['1.0', '1.08 mm', 'dickste Struktur; E-Volumina steigen, Fahrwege bleiben', 'MAXRATE + Serial-Budget (r164) im Blick'],
], [22*mm, 32*mm, 64*mm, 48*mm]))
A(P('Der Düsenwert ist EIN Feld in printer.cfg — Linienbreite, Extrusionsvolumen, Hatch-'
    'Dichte und Turmgrößen folgen deterministisch daraus (wid = max(0.4, nozzle × 1.08) in '
    'jedem Generator). Die Testseite r197_gen_sweep fährt die Generatorfamilie mit '
    'Parametervariationen inklusive Ungültigwerten (negativ, außerhalb) — Klemmen oder '
    'saubere ValueError, nie korrupte Dateien.'))

# ================================ Kap 4 =====================================
flow += H1('4  Die Test-Stufen (r198_tier_report.py)')
A(P('Ein Befehl, eine Tabelle pro Stufe — nichts wird still übersprungen:'))
A(CODE('python3 tools/r198_tier_report.py            # alles\n'
       'python3 tools/r198_tier_report.py --tier hardcore'))
A(TBL(['Stufe', 'Batterien', 'Ziel'], [
 ['<b>normal</b>', 'r141 journeys · systemtest · validator · r165 doc', 'was ein normaler Anwender anfasst'],
 ['<b>power</b>', 'megatest · r110 setup · r142 field · r143 audit · r166 templates · r168 stamps · r164 serial', 'Feld- und Setup-Sicherheit'],
 ['<b>developer</b>', 'macro_render (1.910) · r81 goldens · r111 geom · r167 air', 'Ausgabe-Stabilität'],
 ['<b>hardcore</b>', 'r190 tag ladder · r197 gen sweep (446) · r212 ultimate sweep (19: Compiler/Strings/Dead/Chains/Preprint) · r199 zip check · audit_sweep', 'Tiefentest Tagging + Generatoren/Tools + Release-Artefakt'],
 ['<b>stress</b>', 'r140 (46.757 Checks)', 'Ausdauer'],
 ['<b>function</b>', 'r187 matrix · systemtest', 'End-to-End-Verhalten'],
], [24*mm, 82*mm, 60*mm]))
A(P('.136-Gesamtergebnis: <b>22/22 Batterien grün im Tier-Lauf</b> (r197 wuchs auf 413 ' 
    'Checks: +5 Watcher-Single-Instance-Tests mit ECHTEN Daemon-Prozessen, +5 Live-Endpoint-'
    'und Evaluator-Kreuzchecks). Zwei Re-Freezes waren nötig und wurden per Alt/Neu-Diff '
    'verifiziert, bevor eingefroren wurde. '
    'waren nötig und wurden per Alt/Neu-Diff verifiziert, bevor eingefroren wurde (r81: '
    'Core-Stempel; macro_render: Labels-Goldens nach R194). Nebenbei fing der R185-Wächter '
    'eine Ära-Annotation, die ich selbst ins Manual geschrieben hatte — die Abdeckung '
    'beißt jetzt in beide Richtungen. Summe: macro_render 1.910, r140 46.757, r141 2.372, '
    'r187 1.356, r190 32, r197 403, r199 30, systemtest 214, megatest 190/194, '
    'audit_sweep 82, validator clean, r110 inkl. Flat-Zip-Ablehnung.'))

# ================================ Kap 5 =====================================
flow += H1('5  Feld-Bug-Klassen (1)–(18) — was das Feld fand')
A(TBL(['Klasse', 'Beispiel aus dem Feld', 'Abdeckung'], [
 ['(1) Parser-Ebenen unter dem Render', '.133 Preset-SAVE: shlex frisst die Quotes', 'R188-Roundtrip; r197 sweep-invalid'],
 ['(2) Zustands-Lebensdauer über Druckgrenzen', '.134 Pause-Register überlebte das Druckende', 'r141 + r187 Matrix'],
 ['(3) Verkettungs-Glieder (Textur/Cake/Scale)', '.134 Texture-Push mit leerem _PREVIEW.name', 'r197 sweep (texture/cake chains)'],
 ['(4) Engine-Eigenschaften außerhalb des Mocks', 'Klipper friert enable-Listen beim Menü-Eintritt ein', 'R188 live-Slots; r197 Export-Struktur'],
 ['<b>NEU (5): TYPES= lügt</b>', 'Labels mit geklemmten base_layers behaupteten INFILL-SOLID; Ties-LOOP behauptete Surfaces; Litho-Flat/Colorpic behaupteten WALL-INNER', 'r197 G3/G7 — alle drei gefixt (R197)'],
 ['<b>NEU (6): Copy-Paste-Sektions-Zombies</b>', '4× [menu … __feat __ow]-Zombies: der Live-Punkt „Outer Wall" hieß im LCD „Custom Code" (Klippers Merge: letzte Deklaration gewinnt)', 'r197 T1 (Baum/Duplikate) — Zombies entfernt (R197b)'],
 ['<b>NEU (7): Async-Reentranz</b>', 'r2_menu refresh: Lock im Lock = Deadlock am Endpunkt', 'Fake-Moonraker-Test im Sweep (gefixt)'],
 ['<b>NEU (8): Release-Artefakte</b>', 'das .134-Update-Zip war flach gebaut (kein klipper-e3-r2d2/-Ordner): update.sh streute macros/, tools/ ... neben die printer.cfg, das Paket blieb .133 — „nach dem Update noch .133"', 'r199_zip_check (Layout + Versionen) + r110-Ablehn-Szenario + update.sh-Verweigerung (R199, Feldmeldung dieser Runde)'],
 ['<b>NEU (9): Prozess-Duplizierung</b>', '.136-Feldlog: JEDER Watcher-Push lief doppelt (jede SAVE_VARIABLE 2×, Litho-RESPOND 2×, opt_list/sd_tree 3×) — ein alter Watcher lief neben dem neuen (PID-Datei in /tmp war gealtert/leer)', 'R200: Startup-/proc-Scan + Kernel-flock (watcher.lock im Paket-Root) + --once schont den Daemon + HOST_CHECK nennt Duplikat-PIDs mit Fix-Befehl; r197 T6 testet mit echten Daemon-Prozessen'],
 ['<b>NEU (10): Watcher-Boot-Doppelung + stilles klippy-down</b>', '.136a-Feldlog: beim Boot startete ein echter zweiter Watcher mit („Twin“); und der Watcher versuchte den postproc_build-Push endlos still weiter, während das Display „host ok“ sagte', 'R202: breiterer Startup-Matcher (r2_postproc_old.py zählt, r2_menu.py nicht), cgroup-unit reader, Flat-Stray-Warnungen; der Watcher sagt laut, was zu tun ist (FIRMWARE_RESTART, sonst Power OFF 10 s); r197 T6d'],
 ['<b>NEU (11): Live-Endpoint-Last</b>', '.136c-Feldlog: JEDER Web-LCD-Poll blockierte Klippy 0,7 s (QueryStatusHelper) → „Neopixel update did not succeed“; der Endpoint fragte ~300 Makro-Objekte ab statt der 12 referenzierten', 'R204: live_objects im Export (exakt die referenzierten Objekte), Slim-Query + 2,5-s-Cache, max. 1 echte Abfrage pro Poll; r197-Regression mit 300 Junk-Makros'],
 ['<b>NEU (20): Command-mit-Kindern (LCD-tot)</b>', 'R212-Feldbericht: FILE_CHECK/RETAG unter Pre-Print>Fixes als COMMAND mit Kindern deklariert - Klippers Display-Men\u00f6 \u00f6ffnet die Kinder eines Commands NIE, Retag war am Display unerreichbar (nur die WebUI zeigte es - deshalb gr\u00fcnten alle Web-Tests)', 'R212: zur\u00fcck als LISTE unter System > File check (Scan now, How it works, Retag 2x, Re-fix 2x); r212-DEAD-Scan + macro_render pinnen die Erreichbarkeit'],
 ['<b>NEU (19): Wert-lose Schnappsch\u00fcsse</b>', 'R212-Feldbericht: Tools-Men\u00fc + SD-Liste leer, obwohl live=ok - der Status-Schnappschuss tr\u00e4gt Objekte OHNE Werte, Existenztests antworteten Nein und blendeten aus', 'R212: Live-Antwort tr\u00e4gt available (Namen), die Seite materialisiert leere Objekte; r197 T8-availability pinnt es'],
 ['<b>NEU (18): Mock-Drift (Fake reicher als die Realit\u00e4t)</b>', '.136i-Feldlog: Badge nannte den Grund - lookup_object existiert auf dem Moonraker-Server nicht (API: lookup_component); der Offline-Fake hatte die falsche Methode implementiert, jeder Test gr\u00fcn, der Pi warf AttributeError; /live scheiterte seit R201', 'R211: lookup_component + Fallback; der Fake spiegelt NUR die echte Moonraker-API-Oberfl\u00e4che; neuer T2d pinnt den Drift'],
 ['<b>NEU (17): Rohbetrieb (UI ohne Daten/Auswertung)</b>', '.136h-Feldlog: Seite lebte, war aber nicht bedienbar - rohe Jinja-Labels, vom LCD ausgeblendete Men\u00fc sichtbar, kein Zur\u00fcck; der Live-Schnappschuss scheiterte und der GRUND wurde weggeworfen; Enable-Strings kamen MIT Klammern (als Dict-Literal gepars-t, nie versteckt); der Sender h\u00e4tte rohe Templates gepostet (968/1964)', 'R210: Grund immer im Badge sichtbar, Per-Objekt-Retry, Enables durch ihre Klammern ausgewertet (Per-ID-Parit\u00e4t vs Display), jeder Befehl vor dem Senden gerendert (Parit\u00e4t vs jinja2), Zur\u00fcck-Navigation, Dashboard + Benachrichtigungen + Konsole'],
 ['<b>NEU (16): Schnittstellen-Vertragsbruch (Seite \u00d7 Endpoint)</b>', '.136g-Feldlog: Seite lud, aber kein Klick („main_") — der JSON-Embed lie\u00df ein verwaistes null: Syntaxfehler, das Seiten-JS lief seit R201 NIE; dazu wurde Moonrakers {"result":…}-Envelope nicht ausgepackt und pollLive startete vor loadDoc', 'R209: Embed geh\u00e4rtet, Envelope-Unwrap + Form-Check, pollLive nach loadDoc; T8 f\u00fchrt die KOMPLETTE echte Seite in node gegen die echte Komponenten-Antwort aus'],
 ['<b>NEU (15): Serve-Path-Dateirechte</b>', '.136f-Feldlog: 403 schon beim Öffnen der Seite (auch Inkognito) — nginx läuft als www-data und konnte die Seite unter /home/pi nicht lesen; die API-Pfade liefen weiter, weshalb jeder Proxy-Test grün war', 'R208: Seite in /var/www/r2lcd (welt-lesbar, außerhalb jedes Home-Dirs), Sync bei jedem Update, Selbsttest prüft auch die Seite per GET; E2E mit home=750'],
 ['<b>NEU (14): Geschriebene Konfiguration ≠ aktive Konfiguration</b>', '.136e-Feldlog: 403 trotz R206-Fix — der nginx-Reload schlug still fehl (Seite lief, jeder Befehl 403) und/oder der case-sensitive Origin==Host-Vergleich strauchelte über ein gemischt geschriebenes Lesezeichen', 'R207: Case-insensitive Map, Installer SELBST-TESTET die aktive Guard nach jedem Reload (fremder Origin muss 403 am Proxy bleiben — Retry + klare Ansage), E2E mit echtem nginx'],
 ['<b>NEU (13): Proxy-Auth zwischen nginx und Moonraker</b>', '.136d-Feldlog: „web ui sagt 403 forbidden“ — Moonraker lehnt jede Anfrage mit unbekanntem Origin-Header ab; Browser senden Origin bei JEDEM Befehl-POST (GETs ohne) → Live-Werte kamen, jeder Button starb seit .136b. Und: update.sh syncte die Extension nie — der R204-Fix erreichte den Pi gar nicht', 'R206: Origin-Strip am Proxy + eigener CSRF-Wächter in der nginx-Site (fremde Origins → 403 von nginx), --update-only hält die Web-LCD ab jedem Update aktuell; E2E mit echtem nginx + Fake-Moonraker bewiesen'],
 ['<b>NEU (12): Messartefakte</b>', '.136d-Feldlog: der Watcher-Check unter sudo listete 2 zusätzliche „Prozesse“ — das sudo+pgrep-Pärchen selbst; gelesen als versteckte Watcher, obwohl genau einer lief', 'R205: [r]-Bracket-Form überall (Daemon-Hint, update.sh, Root-pkill), update.sh sagt den Census selbst („exactly 1 watcher (PID …)“), r142-Lint verbietet unklammerte Watcher-Muster repo-weit'],
], [40*mm, 66*mm, 60*mm]))
A(P('Klassen 5–7 sind genau die Sorte, die du immer gemeldet hast und die in klassischen '
    'Tests nie auftaucht: sie brauchen entweder Parameter-Grenzlagen (Klemmung), '
    'Konfigurations-Duplikate (die ein Baum-Test findet, ein Render aber nicht) oder '
    'Nebenläufigkeit (die ein Mock nur mit echtem await-Deadlock sieht). Die Sweep-'
    'Struktur-G7-Prüfung („TYPES= darf nur behaupten, was APPLY_TYPE wirklich setzt") '
    'wird ab jetzt jede Generator-Änderung an dieser Front bewachen.'))

# ================================ Kap 6 =====================================
flow += H1('6  Was .135 alles geändert hat (R191–R197)')
A(TBL(['Runde', 'Änderung'], [
 ['R191', 'TYPE_RE liest ;FEATURE: (Bambu Studio) + Stemming-Whitelist ironing→iron'],
 ['R192', '_fmove192: die BRIM-fstat-Buchung zieht beim Re-Tag mit — TYPES= verliert BRIM nie wieder (.134-Feldlücke)'],
 ['R193', 'Stufe 5 GEBAUT: Quer-Schicht-Luftscan (_airscan193 → BRIDGE / INTERNAL-BRIDGE) + Sequenz-Audit S1–S4 (SEQWARN, Flag-only) — Ironing-Regel nach deiner Korrektur: JEDES Top darf Ironing tragen'],
 ['R194', 'Purge-Tower-Tagging: Labels/Litho/Colorpic drucken den Turm als EIN PRIME-TOWER-Feature (Turm-Brim bleibt BRIM), TYPES= ehrlich'],
 ['R195', '_DIALOG_PEEK: Dialog-Öffnung erzwingt frischen Peek-Push (schließt die Auswahl→Dialog-Timing-Lücke der .134-Forensik)'],
 ['R196', 'Web-UI: menu_json_export + r2_menu-Extension + Demo-Seite (dieses Kapitel 2)'],
 ['R197', 'TYPES-Ehrlichkeit (Labels-Klemmung, Ties-LOOP, Litho-Flat, Colorpic) + 4 Menü-Zombies entfernt + r2_menu-Deadlock + Testwerkzeuge r197/r198 + Goldens re-gefriert (verifiziert: .134≡.135 auf ehrlichen Fixtures)'],
 ['R199', 'Feldfix „.134 zeigt nach dem Update noch .133": flache Update-Zips werden VOR dem Entpacken abgelehnt, Leichen-Warnung mit Aufräum-Liste, .134-Zip korrekt neu gebaut; r199_zip_check prüft das Release-Artefakt + Repo-Stempel; r110-Ablehn-Szenario'],
 ['R200', 'Feldfix „.135: jeder Push doppelt" (.136-Log-Analyse): Watcher-Single-Instance hart gemacht — Startup-Scan über /proc nimmt von JEDEM lebenden Watcher über, Kernel-flock verhindert jede Überlappung, --once mordet nie den Daemon, HOST_CHECK zeigt Duplikate'],
 ['R201', 'Web-LCD LIVE: /server/r2_menu/live (geschnittener Drucker-Snapshot), Seiten-Evaluator im LCD-Jinja-Dialekt (209 Namen + 120 Enables == jinja-Wahrheit), Exporter strippt die Quote-Ebene aus name/enable'],
], [18*mm, 132*mm]))
A(Spacer(1, 4*mm))
A(Paragraph('Ende der Übersicht — Code-Wahrheit: web/, tools/r2_postproc.py, '
            'tools/menu_json_export.py, tools/r197_gen_sweep.py, tools/r198_tier_report.py', S['end']))

doc.build(flow)
print('DISPLAYS_WEB_UI.pdf built (%d flowables)' % len(flow))
