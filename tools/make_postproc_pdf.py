#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Baut POSTPROCESSING.pdf - Dokument 4 von 4: das R2-Python-Postprocessing.

Alles hier Beschriebene ist aus tools/r2_postproc.py gelesen (Zeilennummern
und Namen stehen dabei) oder aus einem echten Lauf ueber
tools/samples/statprobe.gcode gemessen.
"""
import math
import os
import re
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from reportlab.lib.units import mm
from reportlab.platypus import Paragraph

import r2_pdf_kit as K
from r2_version import VERSION as R2VER
from r2_pdf_kit import (Doc, H1, H2, H3, P, B, NUM, CODE, CAP, TBL, BOX, IMG,
                        FORMULA, SP, ladder_fig, bar_fig, S)

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ZIEL = os.path.join(ROOT, 'POSTPROCESSING.pdf')
SRC = os.path.join(ROOT, 'tools', 'samples', 'statprobe.gcode')
TAG = os.path.join(ROOT, 'tools', 'samples', 'statprobe_tagged.gcode')
TMP = tempfile.mkdtemp(prefix='r2pdf_pp4_')

FIL_A = math.pi * (1.75 / 2.0) ** 2

TOC_STD = [
    ('1', 'Was der Postprozessor ist - und was nicht', 3),
    ('2', 'Die Anatomie einer Datei: vorher / nachher', 4),
    ('3', 'Die drei Marker und ihre Grammatik', 6),
    ('4', '_FILE_INFO: was der Scanner wirklich misst', 8),
    ('5', 'Feature-Erkennung: 147 Namen, 16 Kanäle', 10),
    ('6', 'Der Lauf als Zustandsmaschine', 12),
    ('7', 'Segmentierung und das MCU-Budget', 14),
    ('8', 'Die Fixes als Python', 16),
    ('9', 'Dateischutz: lesen, prüfen, tauschen', 18),
    ('10', 'Der Daemon und die save_variables-Brücke', 20),
    ('11', 'Der Cake-Split und die Range-Regel', 22),
    ('12', 'Messwerte eines echten Laufs', 24),
    ('13', 'Werkzeuge und Aufrufe', 26),
    ('14', 'Fallstricke und Prüfliste', 28),
]


# ------------------------------------------------------------------ Messwerte
def datei_zahlen(pfad):
    t = open(pfad, errors='replace').read()
    zeilen = t.split('\n')
    return {'b': len(t.encode()), 'z': len(zeilen),
            'marker': sum(1 for l in zeilen if l.startswith('APPLY_TYPE')),
            'layer': sum(1 for l in zeilen if l.startswith('LAYER_MARK')),
            'komm': sum(1 for l in zeilen if l.lstrip().startswith(';'))}


def rate_tabelle(pfad):
    cur = None
    x = y = 0.0
    f = None
    st = {}
    order = []
    for ln in open(pfad, errors='replace'):
        s = ln.strip()
        m = re.match(r'APPLY_TYPE TYPE=([A-Z_-]+)', s)
        if m:
            cur = m.group(1)
            if cur not in st:
                st[cur] = {'n': 0, 'len': 0.0, 'rmax': 0.0}
                order.append(cur)
            continue
        if s.startswith('G28'):
            x = y = 0.0
            continue
        mm_ = re.match(r'G[01] ([^;]*)', s)
        if not mm_:
            continue
        p = {}
        for tok in mm_.group(1).split():
            try:
                p[tok[0]] = float(tok[1:])
            except ValueError:
                pass
        x1 = p.get('X', x)
        y1 = p.get('Y', y)
        f = p.get('F', f)
        d = math.hypot(x1 - x, y1 - y)
        if cur and 'E' in p and d > 1e-6 and f:
            r = (f / 60.0) * (p['E'] / d) * FIL_A
            st[cur]['n'] += 1
            st[cur]['len'] += d
            if r > st[cur]['rmax']:
                st[cur]['rmax'] = r
        x, y = x1, y1
    return order, st


# ------------------------------------------------------------------ Dokument
def build(toc_seiten=None):
    kb = Doc(ZIEL, 'R2-D2 · Postprocessing (Python)',
             'R2-Python-Postprocessing')
    kb.add_cover(
        'R2-D2 MACRO SYSTEM · DOKUMENT 4 VON 4',
        'Das Python-Postprocessing',
        'Wie aus einer Slicer-Datei eine R2-Datei wird - Code, Mathe, Messwerte',
        absaetze=[
            'Der Postprozessor ist das einzige Python-Programm im System, das '
            'jeden Druck berührt: er liest die Slicer-Datei, schreibt Marker '
            'hinein, rechnet Geometrie nach und führt auf Anforderung Fixes '
            'aus. Ohne ihn gäbe es kein Feature-Tuning, keine Z-Hop-Regel, '
            'keinen Volumenstrom-Cap und keinen automatischen Start.',
            '<font face="DVSM">tools/r2_postproc.py</font> hat '
            '<b>28 978 Zeilen</b>, <b>261 Funktionen</b> und <b>11 Klassen</b>. '
            'Dieses Heft erklärt nicht jede Zeile, sondern die <b>Bauform</b>: '
            'welche Marker entstehen, wie der Lauf aussieht, welche Mathematik '
            'in den Fixes steckt und wo die Grenzen liegen.',
            'Die Zahlen der Beispiele kommen aus einem echten Lauf über '
            '<font face="DVSM">tools/samples/statprobe.gcode</font> (30 '
            'Schichten, 147 Feature-Namen im Wörterbuch, 45 Auftrags-Kanäle '
            'zwischen Makros und Python).',
        ])
    kb.add_toc(toc_seiten or TOC_STD)

    src = datei_zahlen(SRC)
    tag = datei_zahlen(TAG)
    order, st = rate_tabelle(TAG)

    # ============================================================ Kapitel 1
    kb.story += H1('Was der Postprozessor ist - und was nicht', '1')
    kb.story += P(
        'Ein Slicer denkt in <b>Features</b> (Außenwand, Infill, Brücke), '
        'schreibt aber nur <b>Wege</b> in die Datei. Der Drucker sieht davon '
        'nichts: für Klipper ist jede Zeile ein Move, und ein Move kennt '
        'keinen Grund. Der Postprozessor übersetzt den Grund in eine Zeile, '
        'die der Drucker ausführen kann - <font face="DVSM">APPLY_TYPE'
        '</font>. Erst dadurch kann ein Override beim Marker-Wechsel greifen '
        'statt nur „irgendwo im Druck“.')
    kb.story += P(
        'Er tut das <b>nicht</b>: er slict nicht, er ändert keine Geometrie '
        '(außer auf ausdrücklichen Befehl in den Fixes), er startet keinen '
        'Druck und er greift nicht in Start- oder Endsequenz ein. Er arbeitet '
        'auf Dateien und auf Anforderung - mehr nicht.')
    kb.story += P(
        'Zwei Betriebsarten, ein Code:')
    kb.story += TBL(['Betriebsart', 'Aufruf', 'Rolle'],
                    [['Daemon (Wächter)', 'r2_postproc.py --watch DIR', 'läuft dauerhaft, verarbeitet jede neue oder geänderte Datei, bedient die Auftrags-Kanäle'],
                     ['Diagnose (einmalig)', 'r2_postproc.py --watch DIR --once', 'verarbeitet alles, was jetzt da ist, gibt eine Zusammenfassung aus und endet'],
                     ['Werkzeug-Aufrufe', '--label / --reso / --bridge / --range / --stl / --file-check', 'einzelne Generatoren und Prüfungen ohne Wächter']],
                    [34 * mm, 60 * mm, 68 * mm], mono_cols=(1,))
    kb.story += SP(2)
    kb.story.append(IMG(ladder_fig([
        ('1', 'Slicer-Datei', 'G0/G1, ;TYPE:-Kommentare, kein Marker'),
        ('2', 'Scanner', 'Geometrie, Raten, Naht, Schichtzählung'),
        ('3', 'Tagging', '_FILE_INFO + LAYER_MARK + APPLY_TYPE'),
        ('4', 'Fixes', 'nur auf Befehl: Retract, Vol, Segmente, Reise'),
        ('5', 'Klipper', 'Marker schalten Overrides beim Druck'),
    ], os.path.join(TMP, 'pipeline.png'),
        'Die Kette: Datei rein, Marker raus, Drucker versteht es'), 162))
    kb.story += CAP('Bild 1 · Fünf Stufen. Stufe 3 ist die einzige, die bei '
                    'jedem Druck läuft; Stufe 4 nur, wenn du sie anstößt.')
    kb.story.append(BOX('Die harte Regel für dieses Programm', [
        'Der laufende Postprozessor wird <b>nicht</b> direkt umgebaut. Änderungen '
        'entstehen in einer Kopie (<font face="DVSM">r2_postproc_next.py</font>), '
        'die bis auf drei Kopfzeilen byte-gleich ist - md5-geprüft. So lässt '
        'sich jede Änderung mit einem Dateitausch zurücknehmen, ohne den '
        'Druckbetrieb zu riskieren.',
    ], 'warn'))

    # ============================================================ Kapitel 2
    kb.story += H1('Die Anatomie einer Datei: vorher / nachher', '2')
    kb.story += P(
        'Der Lauf verändert erstaunlich wenig: eine Kennzeile oben, eine '
        'berechnete <font face="DVSM">_FILE_INFO</font>-Zeile und je '
        'Feature-Wechsel eine Markerzeile. Gemessen an der Beispieldatei:')
    kb.story += TBL(['Größe', 'Quelle (Slicer-Nachbau)', 'getaggt', 'Delta'],
                    [['Bytes', '%d' % src['b'], '%d' % tag['b'],
                      '+%d' % (tag['b'] - src['b'])],
                     ['Zeilen', '%d' % src['z'], '%d' % tag['z'],
                      '+%d' % (tag['z'] - src['z'])],
                     ['APPLY_TYPE', '0', '%d' % tag['marker'], '+%d' % tag['marker']],
                     ['LAYER_MARK', '%d' % src['layer'], '%d' % tag['layer'], '0'],
                     ['Kommentarzeilen', '%d' % src['komm'],
                      '%d' % datei_zahlen(TAG)['komm'],
                      '+%d' % (datei_zahlen(TAG)['komm'] - src['komm'])]],
                    [34 * mm, 52 * mm, 38 * mm, 38 * mm])
    kb.story += CAP('Tabelle · Ein Lauf über %d Zeilen kostet %d Byte - rund '
                    '%d Byte je Marker. Die Datei bleibt lesbar, die '
                    'Schichtzahl bleibt gleich (%d).'
                    % (src['z'], tag['b'] - src['b'],
                       (tag['b'] - src['b']) // max(1, tag['marker']),
                       tag['layer']))
    kb.story += P('So sieht das an der Dateispitze aus - oben die Quelle, unten '
                  'das Ergebnis:')
    kb.story += CODE(
        '; synthetic sample - slicer-like ;TYPE: comments, 30 layers\n'
        ';FLAVOR:Marlin\n'
        '_FILE_INFO NAME=statprobe LY=0.2 W=0.45 NOZ=0.4 HOT=210 BED=60 MAT=PLA\n'
        'M83\n'
        'G90\n'
        'G28')
    kb.story += CODE(
        '; R2-POSTPROC v5                                    <- Kennzeile\n'
        '; synthetic sample - slicer-like ;TYPE: comments, 30 layers\n'
        ';FLAVOR:Marlin\n'
        '_FILE_INFO TOTAL_LAYERS=30 BY_OBJECT=0 FS_SKIRT=50 ... MAXRATE=7.2\n'
        '            SEAM=105,105 SEAMN=30 FW=Marlin          <- berechnet\n'
        '_FILE_INFO NAME=statprobe LY=0.2 W=0.45 NOZ=0.4 HOT=210 BED=60 MAT=PLA\n'
        'M83\n'
        'G90\n'
        'G28')
    kb.story += SP(2)
    kb.story += P('Und mitten in der Datei, an jedem Feature-Wechsel:')
    kb.story += CODE(
        'G1 X102.000 Y102.000 E1.54927 F3000\n'
        ';TYPE:Outer wall                                    <- Slicer\n'
        'APPLY_TYPE TYPE=WALL-OUTER                          <- Postprozessor\n'
        'G0 X105.000 Y105.000 F9000\n'
        'G1 X145.000 Y105.000 E1.49688 F3600')
    kb.story.append(BOX('Der Marker steht zwischen Kommentar und erstem Move', [
        'Diese Position ist kein Zufall: der Kommentar gehört zum Feature, '
        'der Marker muss <b>vor</b> dem ersten Move stehen, sonst läuft der '
        'erste Weg der Wand noch mit den Werten des vorherigen Features. Ein '
        'einziger Move mit falschem Accel ist an einer Ecke sichtbar.',
    ], 'why'))

    # ============================================================ Kapitel 3
    kb.story += H1('Die drei Marker und ihre Grammatik', '3')
    kb.story += TBL(['Marker', 'Form', 'wer liest ihn', 'wofür'],
                    [['APPLY_TYPE', 'APPLY_TYPE TYPE=WALL-OUTER', 'gcode_macro APPLY_TYPE', 'Feature-Wechsel: Speed/Accel/Flow/PA setzen'],
                     ['LAYER_MARK', 'LAYER_MARK LAYER=7 Z=1.40', 'gcode_macro LAYER_MARK', 'Schichtzähler: Schicht 1/2-Regeln, Pausen, Stop-At-Layer'],
                     ['_FILE_INFO', '_FILE_INFO NAME=… LY=… W=…', 'Makros + Menü', 'Anzeige, Vorschläge, Profil-Erkennung']],
                    [26 * mm, 56 * mm, 40 * mm, 40 * mm], mono_cols=(0, 1))
    kb.story += P(
        'Alle drei sind <b>Befehle</b>, keine Kommentare - sie werden also '
        'auch ausgeführt. Der Unterschied zu normalen Befehlen: sie tragen '
        'keine Bewegung, sondern nur Zustand. Deshalb kosten sie im Druck '
        'nichts außer einem Serial-Paket.')
    kb.story += H2('3.1  Warum keine Semikolons vor den Markern')
    kb.story += P(
        'Ein Marker <i>könnte</i> als Kommentar in der Datei stehen '
        '(<font face="DVSM">; R2-TYPE: …</font>) - dann müsste aber jemand '
        'die Datei Zeile für Zeile durchreichen, statt sie dem Drucker zu '
        'geben. Als echter Befehl läuft die Datei direkt, und nur Dinge, die '
        'das Makrosystem wirklich braucht, sind Befehle. Das ist auch der '
        'Grund, warum der Postprozessor Kommentare <b>niemals</b> anfasst.')
    kb.story += H2('3.2  Der sichere Zeichensatz')
    kb.story += P(
        'Klippers Konfigurations-Template bricht Zeilen an zwei Stellen ab: '
        'am Semikolon (Kommentar) und am Rautezeichen. Ein Wert, der eines '
        'davon enthält, wird also nicht falsch - er wird <b>stumm '
        'abgeschnitten</b>. Der Postprozessor schreibt deshalb jeden '
        'Parameter, der in Markern landet (besonders den Snapshot der '
        'optimierten Kopie), durch einen Filter, der genau diese Zeichen '
        'entfernt, bevor die Zeile entsteht.')
    kb.story += FORMULA(
        'erlaubt:  A-Z a-z 0-9 _ - . , : + = ( ) /  und einfache Anführungszeichen\n'
        'entfernt:  ;  #  "  \\  und jedes Leerzeichen im Snapshot',
        'Der Snapshot wird als kompaktes Dict geschrieben - ein Leerzeichen '
        'zu viel und Klipper schneidet die Zeile ab.')

    # ============================================================ Kapitel 4
    kb.story += H1('_FILE_INFO: was der Scanner wirklich misst', '4')
    kb.story += P(
        'Die Zeile ist das Gedächtnis der Datei. Sie wird beim Tagging '
        '<b>berechnet</b> (nicht vom Slicer übernommen) und steht in der '
        'Beispieldatei so:')
    kb.story += CODE(
        '_FILE_INFO TOTAL_LAYERS=30 BY_OBJECT=0 FS_SKIRT=50 FS_WALL_OUTER=60\n'
        '  FS_WALL_INNER=60 FS_INFILL_SPARSE=80 FS_SUPPORT=50 FS_BRIDGE=30\n'
        '  FS_SURFACE_TOP=40 FS_IRONING=20 TYPES=SKIRT,WALL-OUTER,WALL-INNER,\n'
        '  INFILL-SPARSE,SUPPORT,BRIDGE,SURFACE-TOP,IRONING FTRAVEL=150\n'
        '  MAXRATE=7.2 SEAM=105,105 SEAMN=30 FW=Marlin')
    kb.story += TBL(['Feld', 'Bedeutung', 'im Beispiel'],
                    [['TOTAL_LAYERS', 'gezählte Schichten', '30'],
                     ['BY_OBJECT', '1, wenn nach Objekt getaggt wurde', '0'],
                     ['FS_*', 'die im File gefahrene Geschwindigkeit je Feature (mm/s)', 'SKIRT 50 … IRONING 20'],
                     ['TYPES', 'alle vorkommenden Feature-Kürzel', '8 Typen'],
                     ['FTRAVEL', 'Reisegeschwindigkeit', '150 mm/s'],
                     ['MAXRATE', 'höchster Volumenstrom (mm³/s)', '7.2'],
                     ['SEAM / SEAMN', 'Nahtkoordinaten (x,y) und Anzahl', '105,105 / 30'],
                     ['FW', 'Firmware-Geschmack (Marlin/Klipper)', 'Marlin']],
                    [30 * mm, 82 * mm, 50 * mm], mono_cols=(0,))
    kb.story += P(
        'Die <b>FS_</b>-Werte sind der ehrlichste Teil: sie werden aus den '
        'tatsächlichen <font face="DVSM">F</font>-Werten der Wege '
        'zurückgerechnet (<font face="DVSM">F/60</font>), nicht aus dem '
        'Slicer-Kommentar übernommen. Deshalb funktioniert die '
        '<b>Pre-Print-Anzeige „File info“</b> auch bei Dateien, deren Slicer '
        'keine Kommentare schreibt.')
    kb.story += H2('4.1  MAXRATE und die Folgen')
    kb.story += P(
        'MAXRATE ist das Maximum aus allen Wegen nach der Formel aus Kapitel 8 '
        '- im Beispiel 7,2 mm³/s, also die Infill-Geschwindigkeit. Ein Wert '
        'über dem Cap (Standard 12 mm³/s) ist das Signal für den Flow-Cap-Fix. '
        'Der Wert in der Datei ist dabei nur eine <b>Aussage über die '
        'Datei</b>, keine Sperre - gesperrt wird erst, wenn du den Fix '
        'anwendest.')
    kb.story += H2('4.2  SEAM und die Quality-Regel')
    kb.story += P(
        'Nahtstellen werden an der Außenwand gesucht: der Punkt, an dem eine '
        'Schicht beginnt und endet, ist die Naht. Der Scanner merkt sich eine '
        'Koordinate und zählt, wie oft sie auftritt (<font face="DVSM">SEAMN'
        '</font>). Genau diese Liste macht den <b>Quality-Fix</b> möglich: '
        'eine Reise, die keine Naht und keine bereits gedruckte Linie kreuzt, '
        'braucht keinen Retract - eine, die es tut, schon.')

    # ============================================================ Kapitel 5
    kb.story += H1('Feature-Erkennung: 147 Namen, 16 Kanäle', '5')
    kb.story += P(
        'Der Slicer schreibt seinen Feature-Namen als Kommentar. Das '
        'Wörterbuch <font face="DVSM">TYPE_MAP</font> (Z. 148 ff.) übersetzt '
        '<b>147 Schreibweisen</b> auf 17 Kürzel. Es ist absichtlich groß: '
        'jede Slicer-Familie nennt dieselbe Sache anders, und ein Name, der '
        'fehlt, bedeutet „dieses Feature schaltet nie“ - genau das war der '
        'Fehler hinter dem Feldlog „Gap Fill reagiert nicht“.')
    kb.story += TBL(['Kürzel', 'Anzahl Namen', 'Beispiele aus dem Wörterbuch'],
                    [['INFILL-SPARSE', '54', 'sparse infill, fill, infill, gyroid, cubic, lightning, hilbert curve …'],
                     ['PRIME-TOWER', '12', 'wipe tower, prime tower, purge tower, tip tower, prime pillar …'],
                     ['SUPPORT', '11', 'support, support interface, support roof, dense support …'],
                     ['TRAVEL', '11', 'travel, seam, wipe, retract, unretract, tool change …'],
                     ['SURFACE-BOTTOM', '9', 'bottom surface, bottom solid infill, bottom-skin, raft …'],
                     ['WALL-INNER', '7', 'inner wall, perimeter, thin wall, inner shell …'],
                     ['WALL-OUTER', '6', 'outer wall, wall-outer, external perimeter …'],
                     ['INFILL-SOLID', '6', 'internal solid infill, solid infill, solid fill …'],
                     ['SURFACE-TOP', '6', 'top surface, top solid infill, skin, upper face …'],
                     ['CUSTOM', '6', 'custom, custom gcode, others, unknown …'],
                     ['SKIRT / GAPS / BRIDGE', '5 / 4 / 2', 'skirt, ooze shield, draft shield / gap infill, gap fill / bridge, bridge infill'],
                     ['übrige', '8', 'brim, ironing, overhang perimeter, internal bridge, …']],
                    [42 * mm, 22 * mm, 98 * mm], mono_cols=(0,))
    kb.story += CAP('Tabelle · 147 Einträge, verteilt auf 17 Kanäle '
                    '(gezählt aus TYPE_MAP, tools/r2_postproc.py Z. 148-345).')
    kb.story += P(
        'Die Zuordnung ist nicht nur eine Liste, sondern hat zwei '
        'Eigenschaften, die im Feld wichtig wurden:')
    kb.story += B(
        '<b>Trennzeichen-Toleranz</b> - „Wall outer“, „wall-outer“ und '
        '„WALL_OUTER“ werden normalisiert verglichen. Vorher stand nur eine '
        'Schreibweise im Wörterbuch, und ganze Dateien liefen als CUSTOM.',
        '<b>Kein Abbruch beim ersten Treffer</b> - die Erkennung läuft über '
        'alle Vorkommen, nicht nur über das erste <font face="DVSM">APPLY_TYPE'
        '</font>. Sonst hätte eine Datei ab dem ersten Marker ein einziges '
        'Feature.')
    kb.story += H2('5.1  Was passiert, wenn ein Name fehlt')
    kb.story += P(
        'Dann bleibt der vorherige Typ aktiv. Das ist die schlechtere von zwei '
        'Möglichkeiten (die andere wäre CUSTOM), aber es ist <b>sichtbar</b>: '
        'im Live-Menü steht der aktuelle Typ, und wenn dort minutenlang '
        '„WALL-OUTER“ steht, während gedruckt wird, was offensichtlich Infill '
        'ist, fehlt ein Name. Der Weg zurück ist <b>File check → RETAG=2</b>: '
        'es heilt falsche Typen aus den Slicer-Kommentaren, mit Sicherung '
        '(<font face="DVSM">.r2bak</font>) vorher.')

    # ============================================================ Kapitel 6
    kb.story += H1('Der Lauf als Zustandsmaschine', '6')
    kb.story += P(
        'Der Postprozessor arbeitet in <b>zwei Durchgängen</b>. Das ist keine '
        'Bequemlichkeit, sondern eine Notwendigkeit: die '
        '<font face="DVSM">_FILE_INFO</font>-Zeile steht ganz oben, ihre '
        'Werte (Schichtzahl, MAXRATE, SEAM, TYPES) kennt man aber erst am '
        'Dateiende. Also liest der erste Durchgang nur, der zweite schreibt.')
    kb.story += CODE(
        '# 1. Durchgang: leicht lesen (kein Schreiben)\n'
        'for zeile in datei:\n'
        '    if zeile ist LAYER_MARK:      schichten += 1\n'
        '    if zeile ist ;TYPE:<name>:    typen.add(TYPE_MAP[name])\n'
        '    if zeile ist G0/G1 mit E:     rate = (F/60)*(dE/d)*A_fil\n'
        '                                  MAXRATE = max(MAXRATE, rate)\n'
        '                                  FS_<typ> = F/60\n'
        '    if zeile ist WALL-OUTER-Start: SEAM-Kandidat merken\n'
        '\n'
        '# 2. Durchgang: schreiben (streamend, O(1) Speicher)\n'
        'for zeile in datei:\n'
        '    if zeile ist der erste _FILE_INFO:  schreibe berechnete Zeile\n'
        '    if zeile ist ;TYPE:<name>:           schreibe APPLY_TYPE TYPE=<kürzel>\n'
        '    schreibe zeile')
    kb.story += P(
        'Beide Durchgänge sind <b>streamend</b>: das Programm hält nie die '
        'ganze Datei im Speicher. Bei einer 300-MB-Datei ist das der '
        'Unterschied zwischen „läuft“ und „läuft nicht“, und auf einem '
        'Raspberry Pi ist es der Unterschied zwischen „läuft“ und „läuft '
        'nicht und reißt den Druck mit“.')

    # ============================================================ Kapitel 7
    kb.story += H1('Segmentierung und das MCU-Budget', '7')
    kb.story += P(
        'Ein 8-Bit-Mikrocontroller verarbeitet keine 3600 Moves pro Sekunde. '
        'Der Host kann sie schicken, der MCU kommt nicht mit - und dann '
        'meldet Klipper <font face="DVSM">Timer too close</font> und '
        'schaltet ab. Diese Grenze ist keine Geschwindigkeit in mm/s, sondern '
        'eine <b>Move-Rate</b> in Moves/s, und deshalb ist die entscheidende '
        'Größe nicht das Tempo, sondern die <b>Weglänge</b>.')
    kb.story += FORMULA(
        'n<sub>moves</sub> = v / L        (Moves pro Sekunde)<br/>'
        'Grenze: n<sub>moves</sub> ≤ n<sub>max</sub>  ⇒  v ≤ n<sub>max</sub> · L<br/><br/>'
        'mit n<sub>max</sub> ≈ 400 … 450 Moves/s (8-Bit-Serialbudget)',
        'Ein Weg von 0,05 mm darf also höchstens 400 · 0,05 = 20 mm/s '
        'fahren - nicht, weil die Mechanik es nicht könnte, sondern weil der '
        'MCU sonst nicht mitkommt.')
    kb.story += SP(2)
    rows = []
    for L in (0.05, 0.10, 0.20, 0.50, 1.00, 5.00):
        rows.append(['%.2f mm' % L, '%d Moves/s' % 450,
                     '%.0f mm/s' % (450 * L), '%.0f mm/min' % (450 * L * 60)])
    kb.story.append(IMG(bar_fig([('%.2f mm' % L, round(450 * L, 1))
                                 for L in (0.05, 0.10, 0.20, 0.50, 1.00, 5.00)],
                                os.path.join(TMP, 'seg.png'),
                                'Höchstgeschwindigkeit je Segmentlänge (450 Moves/s)',
                                'mm/s'), 150))
    kb.story += CAP('Bild 2 · Die Grenze ist linear in der Weglänge: kurze Wege '
                    'müssen langsam sein, lange dürfen schnell.')
    kb.story += TBL(['Segmentlänge', 'bei 450 Moves/s', 'als Vorschub', 'Bedeutung'],
                    rows, [32 * mm, 34 * mm, 34 * mm, 62 * mm])
    kb.story += P(
        'Genau das rechnet der Postprozessor beim Tagging und bei den Fixes: '
        '<font face="DVSM">F ≤ max_rate · seg_len · 60</font>, nie unter '
        '240 mm/min. Lange Wege (Brim, Wände, Reisen) erreichen ihre volle '
        'Geschwindigkeit, Mikrosegmente werden genau so weit gebremst, wie es '
        'nötig ist - nicht pauschal.')
    kb.story += H2('7.1  Der Segment-Fix: Toleranz statt Radikal-Kur')
    kb.story += P(
        'Fasst man Mikro-Wege zusammen, entsteht eine <b>Sehnenabweichung</b>: '
        'die gerade Verbindung weicht vom Bogen ab. Der Fix begrenzt sie und '
        'erhöht sie nur, wenn es sein muss - gemessen wird die '
        '<b>anhaltende</b> Move-Rate:')
    kb.story += TBL(['Stufe', 'Sehnen-Toleranz', 'Bedeutung bei 0,4-mm-Linie'],
                    [['1', '0,12 mm', 'ein Fünftel der Linienbreite - unsichtbar'],
                     ['2', '0,18 mm', 'knapp die halbe Linienbreite'],
                     ['3', '0,25 mm', 'mehr als die halbe Linie'],
                     ['4', '0,35 mm', 'die alte feste Grenze'],
                     ['5', '0,50 mm', 'das Maximum - bei 0,6er Linie noch vertretbar']],
                    [18 * mm, 34 * mm, 110 * mm])
    kb.story += P(
        'Der Lauf startet bei 0,12 mm. Liegt die anhaltende Rate danach unter '
        'dem Budget (450 Moves/s), ist er fertig. Sonst steigt er eine Stufe '
        'und misst erneut. Geometrie wird dabei nie „geglättet“: innerhalb der '
        'Toleranz verschwindet Detail, das die Düse ohnehin nicht zeigen kann.')

    # ============================================================ Kapitel 8
    kb.story += H1('Die Fixes als Python', '8')
    kb.story += P(
        'Sieben Eingriffe stehen zur Verfügung; alle arbeiten <b>in place</b> '
        'über eine temporäre Datei und einen atomaren Tausch. Keiner von '
        'ihnen läuft während eines Drucks.')
    kb.story += H2('8.1  Volumetrisches E in Millimeter')
    kb.story += P(
        'Marlin kann volumetrisch extrudieren: <font face="DVSM">E</font> ist '
        'dann ein Volumen in mm³, nicht eine Filamentlänge. Klipper erwartet '
        'Länge. Die Umrechnung ist eine Division durch den '
        'Filamentquerschnitt - und sie muss pro Move passieren, weil '
        '<font face="DVSM">E</font> relativ oder absolut sein kann:')
    kb.story += FORMULA(
        'E<sub>mm</sub> = E<sub>mm³</sub> / A<sub>fil</sub>'
        '<br/>A<sub>fil</sub> = π · (d/2)²     d = 1,75 mm ⇒ 2,4053 mm²'
        '<br/>Beispiel: E=2,4 mm³  ⇒  E=1,000 mm',
        'Bei relativem E wird jeder Wert einzeln umgerechnet; bei absolutem E '
        'wird der Verbrauch als Differenz gebildet - sonst entsteht an der '
        'ersten Zeile ein Sprung.')
    kb.story += H2('8.2  Der Retract-Fix')
    kb.story += P(
        'Er erkennt ein Paar aus Rückzug und Wiederaufbau an derselben Stelle '
        'und ersetzt es durch <font face="DVSM">G10</font>/'
        '<font face="DVSM">G11</font>. Kriterium ist nicht „E ist negativ“, '
        'sondern die <b>Kombination</b> aus negativem E, kurzer Distanz und '
        'einem folgenden positiven E-Betrag mit gleichem Ort - sonst würde '
        'jede Wand mit Rückzug am Ende umgeschrieben.')
    kb.story += H2('8.3  Der Flow-Cap')
    kb.story += FORMULA(
        'Q = (F / 60) · (ΔE / d) · A<sub>fil</sub><br/>'
        'falls Q &gt; cap:  F<sub>neu</sub> = F · cap / Q',
        'Der Fix setzt eine Marke <font face="DVSM">; R2-FLOWCAP: cap'
        '</font> in die Datei. Ein zweiter Lauf mit gleichem oder höherem Cap '
        'ist damit ein No-Op, ein niedrigerer greift erneut - die aktuellen '
        'F-Werte sind dann die Basis.')
    kb.story += H2('8.4  Travel- und Quality-Fix')
    kb.story += P(
        'Der <b>Travel-Fix</b> setzt Speed und Accel der Leerfahrten. Der '
        '<b>Quality-Fix</b> ist der interessantere: er entscheidet pro Reise, '
        'ob sie einen Retract braucht - nach der goldenen Regel, dass nur eine '
        'Reise, die bereits gedrucktes Material kreuzt, sauber ist. Dafür '
        'werden die Naht-Kandidaten aus <font face="DVSM">SEAM</font> und die '
        'gedruckten Linien der aktuellen Schicht herangezogen. Ergebnis: '
        'weniger Retracts, kürzere Druckzeit, gleiche Oberfläche.')

    # ============================================================ Kapitel 9
    kb.story += H1('Dateischutz: lesen, prüfen, tauschen', '9')
    kb.story += TBL(['Schutz', 'wie', 'warum'],
                    [['Quelle nur lesen', 'die optimierte Kopie liest die Quelle und schreibt in eine neue Datei; Prüfsumme belegt Unverändertheit', 'eine Kopie darf das Original nie gefährden'],
                     ['Sicherung', '.r2bak vor jedem Retag/Fix', 'ein Fehlgriff ist mit einer Datei zurückgenommen'],
                     ['Atomarer Tausch', 'temporäre Datei (.tmp/.fcx/.sgm), dann os.replace()', 'kein halb geschriebenes G-Code-File im Verzeichnis'],
                     ['Kompressions-Schutz', 'gzip/zip-Quellen werden abgelehnt', 'ein Textfile unter .gz-Namen wäre unlesbar'],
                     ['Idempotenz', 'Marker wie ; R2-FLOWCAP: oder R2-OPT im Kopf', 'ein Fix zweimal laufen zu lassen ändert nichts'],
                     ['Datenfiles', 'Erkennung + „write nothing“-Pfad', 'ein Prüfbericht ist kein G-Code']],
                    [32 * mm, 66 * mm, 64 * mm])
    kb.story.append(BOX('Der Tausch ist der eigentliche Schutz', [
        'Schreiben in die Datei, die der Drucker gerade liest, ist der '
        'klassische Weg zu einem halben G-Code. Deshalb: erst vollständig in '
        'die temporäre Datei schreiben, dann <b>umbenennen</b>. Das Umbenennen '
        'ist auf demselben Dateisystem atomar - entweder die alte oder die '
        'neue Datei, nie etwas dazwischen.',
    ], 'why'))

    # ============================================================ Kapitel 10
    kb.story += H1('Der Daemon und die save_variables-Brücke', '10')
    kb.story += P(
        'Die Makros können kein Python aufrufen und Python kann keine Makros '
        'aufrufen. Die Brücke ist ein <b>Zähler</b>: das Makro erhöht eine '
        'Variable in <font face="DVSM">save_variables</font>, der Daemon '
        'sieht beim nächsten Durchlauf eine neue Zahl und führt den Auftrag '
        'aus. Das ist banal - und genau deshalb robust: es braucht kein '
        'Socket, keinen Port, keine Rechte, und es überlebt jeden Neustart.')
    kb.story += FORMULA(
        'Makro:   SAVE_VARIABLE VARIABLE=texture_nonce VALUE=<alt> + 1\n'
        'Daemon:  alle 5 s lesen  →  nonce ≠ letzter Wert  →  Auftrag ausführen',
        'Der Daemon merkt sich beim Start die <b>aktuellen</b> Werte '
        '(„primen“) und feuert nichts Altes. Genau dieser Schritt fehlte '
        'früher - nach einem Neustart wurden alte Aufträge erneut ausgeführt '
        '(Fix-Meldungen beim Boot, Endlosschleife „Datei nicht gefunden“).')
    kb.story += P(
        'Es gibt <b>45 solcher Kanäle</b>, jeder mit eigenem Namen und '
        'Zähler:')
    kb.story += TBL(['Gruppe', 'Kanäle (Auswahl)', 'Aufgabe'],
                    [['Generatoren', 'label_gen, litho, texture, shape, twist, mirror, cake, scale, stringart, plot, reso, bridge, bricks, colorpic, figures, frame, seal, cable_tie, angle', 'neue Datei aus Parameter+Titel erzeugen'],
                     ['Fixes', 'retract_fix, vol_fix, flowcap_fix, travelacc_fix, segments_fix, quality_fix, speed_fix', 'bestehende Datei umschreiben'],
                     ['Verwaltung', 'del, gen_del, gen_clear, queue_cancel, genq_kill, file_check', 'löschen, abbrechen, prüfen'],
                     ['Optimierung', 'opt, opt_load', 'optimierte Kopie schreiben / Werte laden'],
                     ['Sonstiges', 'preview, range, stl, img_pick, host, plot_cal, plot_text, plot_status', 'Vorschau, Bereich, STL-Export, Bild']],
                    [26 * mm, 84 * mm, 52 * mm], mono_cols=(1,))
    kb.story += P(
        'Dazu drei Regeln, die im Betrieb zählen:')
    kb.story += NUM(
        '<b>Nichts während eines Drucks.</b> Aufträge, die eine Datei '
        'umschreiben, warten auf Leerlauf - der Daemon prüft '
        '<font face="DVSM">print_stats</font> und stellt sich in die Warteschlange.',
        '<b>Jeder Auftrag meldet sich.</b> Der Fortschritt läuft als LED-Ring '
        'und als Meldung im Konsolenfenster; ein stiller Auftrag ist ein '
        'Fehler, kein Erfolg.',
        '<b>Fehler werden gemeldet, nicht geschluckt.</b> Ein nicht gefundenes '
        'File, ein fehlendes Verzeichnis, ein abgelehnter Fix - alles endet in '
        'einer Meldung, nicht in einem stillen Nichts.')

    # ============================================================ Kapitel 11
    kb.story += H1('Der Cake-Split und die Range-Regel', '11')
    kb.story += P(
        'Ein „Cut & Split“ teilt eine Datei in zwei Hälften. Das Problem ist '
        'nicht das Teilen, sondern das <b>Zählen</b>: ein Header kann '
        '<font face="DVSM">TOTAL_LAYERS=700</font> behaupten, während die '
        'Hälfte nur fünf Schichtmarken enthält. Die Range-Funktion rechnet '
        'dann mit 695 Schichten, die es nicht gibt - und der Druck endet '
        'mitten im Bauteil oder gar nicht.')
    kb.story += P(
        'Der Feldbeweis, aus dem die Regel entstand:')
    kb.story += TBL(['Beobachtung', 'Wert', 'Folge'],
                    [['Schichtmarken in der Cut-Hälfte', '5', 'tatsächliche Schichten'],
                     ['Z im Kopf der Hälfte', 'bis 116,5 mm', 'nicht 700 · Schichthöhe'],
                     ['TOTAL_LAYERS im Header', '700', 'falsch für die Hälfte'],
                     ['Nicht-Move-Zeilen', 'in beide Hälften kopiert', 'Header-Werte doppelt']],
                    [50 * mm, 34 * mm, 78 * mm])
    kb.story += FORMULA(
        'Ablehnen nur wenn:  Header ist ein „cake cut“-Header\n'
        '              UND   claim  &gt;  4 · (gezählte Marker)',
        'Die Schwelle 4 ist Absicht: sie lässt Spiralvase-Dateien in Ruhe, '
        'bei denen ein Vielfaches an Non-Move-Zeilen völlig normal ist, und '
        'schlägt nur bei echten Cut-Headern an.')
    kb.story.append(BOX('Die Regel dahinter', [
        'Nicht „Header misstrauen“, sondern: <b>eine Zahl, die sich '
        'widerspricht, wird gemeldet</b> - mit der Zahl und der Quelle. Alles '
        'andere wäre Rätselraten beim Kunden.',
    ], 'tip'))

    # ============================================================ Kapitel 12
    kb.story += H1('Messwerte eines echten Laufs', '12')
    kb.story += P(
        'Der folgende Lauf ist reproduzierbar und in diesem Repository '
        'enthalten:')
    kb.story += CODE(
        'python3 tools/samples/make_statprobe.py        # Quelle erzeugen\n'
        'python3 tools/r2_postproc.py --watch tools/samples --once\n'
        '# [ok] statprobe.gcode: +104 APPLY_TYPE, _FILE_INFO layers=30, by_object=False\n'
        '# [i] initial scan done: 1 gcode file(s) found, 1 processed, 0 errors')
    kb.story += TBL(['Feature', 'Wege', 'Weglänge', 'Q max (mm³/s)', 'Anteil Wege'],
                    [[k.replace('-', ' '), str(st[k]['n']), '%.0f mm' % st[k]['len'],
                      '%.2f' % st[k]['rmax'],
                      '%.1f %%' % (100.0 * st[k]['n'] / max(1, sum(v['n'] for v in st.values())))]
                     for k in order],
                    [42 * mm, 22 * mm, 32 * mm, 32 * mm, 34 * mm])
    kb.story += CAP('Tabelle · %d extrudierende Wege, gezählt und gerechnet aus '
                    'der getaggten Datei. Die Wände stellen %.0f %% aller Wege.'
                    % (sum(v['n'] for v in st.values()),
                       100.0 * sum(st[k]['n'] for k in order if 'WALL' in k)
                       / max(1, sum(v['n'] for v in st.values()))))
    kb.story.append(IMG(K.toolpath_fig(TAG, os.path.join(TMP, 'pfad.png'),
                                       'Fahrweg der getaggten Datei'), 162))
    kb.story += CAP('Bild 3 · Der Weg ist der Beweis: was der Postprozessor '
                    'getaggt hat, ist genau die Geometrie, die aufs Bett geht.')
    kb.story.append(BOX('Was ein Lauf kostet', [
        'Die Beispieldatei hat <b>%d Zeilen</b> und wächst durch das Tagging um '
        '<b>%d Byte</b> (%d Marker). Ein Lauf über ein reales Teil mit '
        '100 000 Zeilen liegt im Sekundenbereich - er läuft im Hintergrund, '
        'während der nächsten Datei.' % (src['z'], tag['b'] - src['b'],
                                         tag['marker']),
    ], 'meas'))

    # ============================================================ Kapitel 13
    kb.story += H1('Werkzeuge und Aufrufe', '13')
    kb.story += TBL(['Aufruf', 'Zweck', 'Beispiel'],
                    [['--watch DIR', 'Daemon, verarbeitet laufend neue Dateien', 'r2_postproc.py --watch /home/pi/printer_data/gcodes'],
                     ['--watch DIR --once', 'einmalig alles verarbeiten, Zusammenfassung, Ende', 'für Nachlauf und Test'],
                     ['--label "TEXT1|TEXT2" W H', 'Schriftzug als G-Code (Font, Basis-/Textschichten, Brim, Ironing, Loch)', 'LESBAR auf dem Bett'],
                     ['--reso X|Y|BOTH', 'Auflösungs-/Raster-Testkörper aus CSV', 'Kalibrierbild'],
                     ['--bridge', 'Brückentest', 'Überhang-Fähigkeit'],
                     ['--plottext', 'Plotter-Text aus einer Zeichnung', 'Stift statt Düse'],
                     ['--statusplot', 'Statusblatt plotten', 'Report auf Papier'],
                     ['--range', 'Bereich einer Datei (Schichtfenster)', 'Testdruck ab Schicht n'],
                     ['--stl', 'Objekt-STL exportieren', 'Bauteil aus der Datei']],
                    [40 * mm, 66 * mm, 56 * mm], mono_cols=(0,))
    kb.story += P(
        'Die Kennung jeder erzeugten Datei trägt Release und Build: '
        '<font face="DVSM">' + R2VER + ' / V1</font>. Damit lässt sich an '
        'jeder Datei ablesen, mit welchem Stand sie entstanden ist - '
        'und der File-Check kann alte Dateien erkennen und nachtaggen.')

    # ============================================================ Kapitel 14
    kb.story += H1('Fallstricke und Prüfliste', '14')
    kb.story += TBL(['Symptom', 'Ursache', 'heute'],
                    [['Nach Neustart feuern alte Aufträge', 'Zähler beim Start nicht übernommen', 'Nicht-Zähler werden „geprimt“ (45 Kanäle)'],
                     ['Feature reagiert nie', 'Name fehlt im Wörterbuch oder wird nicht erneut geprüft', '147 Namen, Trennzeichen-tolerant, alle Vorkommen'],
                     ['Timer too close bei Text/Feindetail', 'Move-Rate statt Geschwindigkeit überschritten', 'F ≤ max_rate · seg_len · 60, Segment-Fix eskaliert'],
                     ['Endlosschleife „Datei nicht gefunden“', 'Auftrag wurde erneut ausgelöst', 'Nicht-Zähler-Priming + Einmal-Meldung'],
                     ['Halb geschriebene Datei', 'direkt in die Zieldatei geschrieben', 'temporäre Datei + os.replace()'],
                     ['Werte in Marker-Zeile abgeschnitten', 'Semikolon/Raute im Wert', 'Filter auf sicheren Zeichensatz'],
                     ['Doppelte Kopie überschreibt Tuning', 'gleicher Dateiname', 'Durchnummerierung _O2/_O3']],
                    [46 * mm, 60 * mm, 56 * mm])
    kb.story += H2('Prüfliste', 'A')
    kb.story += B(
        'Nach dem Tagging: <font face="DVSM">_FILE_INFO</font> vorhanden, '
        'TOTAL_LAYERS plausibel, MAXRATE sinnvoll.',
        'Marker zählen: APPLY_TYPE sollte etwa so oft vorkommen wie '
        'Feature-Wechsel - nicht 0 und nicht 100 000.',
        'Fixes nur bei Leerlauf; vorher wissen, was sie ändern.',
        'Nach einem Fix: Datei neu prüfen (File check) und die Anzeige im '
        'File-info-Zweig gegenlesen.',
        'Nie den laufenden Postprozessor direkt umbauen - Kopie, Testlauf, '
        'dann tauschen.')
    kb.story += SP(6)
    kb.story.append(Paragraph(
        'Ende · Das Python-Postprocessing · R2-D2 Macro System', S['end']))
    kb.render()


def _n(x):
    for a, b in (('&amp;', '&'), ('\u201e', ''), ('\u201c', ''), ('\u2013', '-'),
                 ('\u2014', '-'), (' ', ''), ('\n', ''), ('\t', '')):
        x = x.replace(a, b)
    return x


def echte_seiten():
    try:
        from pypdf import PdfReader
    except ImportError:
        return None
    r = PdfReader(ZIEL)
    out = []
    p = 2
    for nr, txt, alt in TOC_STD:
        seite = alt
        for q in range(p, len(r.pages)):
            if _n(txt)[:22] in _n(r.pages[q].extract_text() or ''):
                seite = q + 1
                p = q
                break
        out.append((nr, txt, seite))
    return out


if __name__ == '__main__':
    build()
    _st = echte_seiten()
    if _st:
        build(_st)
    print('geschrieben: %s %d B' % (ZIEL, os.path.getsize(ZIEL)))
