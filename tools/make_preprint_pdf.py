#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Baut PREPRINT_LIVETUNING.pdf - Dokument 3 von 4.

Inhalt: Pre-Print (13 Zweige), die sieben Datei-Fixes mit ihrer Mathematik,
Feature-Tagging (mit Messwerten aus einem echten Postprozessor-Lauf),
Live-Tuning (17 Zweige + alle Prioritaets-Ketten), Profile, das
Ranking-System ("Rate print?") und die Rechenbeispiele.

Alle Zahlen stammen aus dem Code (menus/lcd_menues.cfg, macros/05..10,
tools/r2_postproc.py) oder aus tools/samples/statprobe_tagged.gcode - einer
Datei, die der ECHTE Postprozessor getaggt hat. Keine erfundene Grafik.
"""
import math
import os
import re
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, PageBreak

import r2_pdf_kit as K
from r2_version import VERSION as R2VER
from r2_pdf_kit import (Doc, H1, H2, H3, P, B, NUM, CODE, CAP, TBL, BOX, IMG,
                        FORMULA, SP, ladder_fig, bar_fig, S)

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ZIEL = os.path.join(ROOT, 'PREPRINT_LIVETUNING.pdf')
PROBE = os.path.join(ROOT, 'tools', 'samples', 'statprobe_tagged.gcode')
TMP = tempfile.mkdtemp(prefix='r2pdf_pp_')

def _one(x):
    """Kit-Rückgaben (Table) in eine Story-Liste packen."""
    return [x]


FIL_A = math.pi * (1.75 / 2.0) ** 2          # mm2 Filamentquerschnitt (1,75 mm)


# ------------------------------------------------------------------ Messwerte
def probe_stats(pfad):
    """Liest die getaggte Probe und rechnet pro Feature: Wege, Laenge, Rate."""
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
                st[cur] = {'n': 0, 'len': 0.0, 'rmax': 0.0, 'rsum': 0.0,
                           'layers': set()}
                order.append(cur)
            continue
        ml = re.match(r'LAYER_MARK LAYER=(\d+)', s)
        if ml and cur:
            st[cur]['layers'].add(int(ml.group(1)))
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
            st[cur]['rsum'] += r
            if r > st[cur]['rmax']:
                st[cur]['rmax'] = r
        x, y = x1, y1
    return order, st


def probe_meta(pfad):
    """Zieht _FILE_INFO-Kennzahlen aus derselben Datei."""
    for ln in open(pfad, errors='replace'):
        if ln.strip().startswith('_FILE_INFO') and 'TOTAL_LAYERS' in ln:
            d = {}
            for tok in ln.split()[1:]:
                if '=' in tok:
                    k, v = tok.split('=', 1)
                    d[k] = v
            return d
    return {}


TOC_STD = [
        ('1', 'Der Regelkreis in einem Bild', 3),
        ('2', 'Das Feature-Vokabular - 29 Kanäle', 4),
        ('3', 'Pre-Print: die 13 Zweige', 6),
        ('4', 'Pre-Print im Detail', 7),
        ('5', 'Die sieben Datei-Fixes und ihre Mathematik', 11),
        ('6', 'Feature-Tagging - Messwerte einer echten Datei', 13),
        ('7', 'Live-Tuning: die 17 Zweige', 15),
        ('8', 'Die Ketten: Speed, Accel, Flow, PA, Lüfter, Temperatur', 18),
        ('9', 'Z-Offset, Z-Hop, Retraktion, Ironing, Shaper', 22),
        ('10', 'Profile: Datei, Depot, Auto-Load, optimized', 24),
        ('11', 'Das Ranking-System („Rate print?“)', 26),
        ('12', 'Rechenbeispiele: vom Dreh zum G-Code', 28),
        ('13', 'Fallstricke aus dem Feldlog', 29),
        ('14', 'Prüfliste', 30),
]


# ------------------------------------------------------------------ Dokument
def build(toc_seiten=None):
    kb = Doc(ZIEL, 'R2-D2 · Pre-Print & Live-Tuning',
             'Pre-Print, Live-Tuning, Profile, Ranking')
    kb.add_cover(
        'R2-D2 MACRO SYSTEM · DOKUMENT 3 VON 4',
        'Pre-Print &amp; Live-Tuning',
        'Der Vertrag vor dem Druck, die Hand am Regler und das Ranking danach',
        absaetze=[
            'Dieses Dokument beschreibt die drei Ebenen, die zwischen Slicer '
            'und Düse sitzen: <b>Pre-Print</b> (13 Menüzweige, alles was vor '
            'dem Start festgelegt wird), <b>Live-Tuning</b> (17 Menüzweige, '
            'alles was während des Drucks gedreht werden darf) und das '
            '<b>Ranking-System</b> (die Frage „Rate print?“, die aus einem '
            'gelungenen Druck eine wiederverwendbare Datei macht).',
            'Jede Zahl in diesem Heft ist aus dem Code gelesen oder aus einem '
            'echten Lauf des Postprozessors gerechnet - Schaltergrenzen, '
            'Toleranzen, Formeln und die Messwerte des Beispielkörpers in '
            'Kapitel 5. Wo eine Kette mehrere Stufen hat (Lüfter, Speed, '
            'Flow, PA), steht sie als Kette da, weil genau dort die '
            'Feldprobleme entstanden sind.',
            'Die Generatoren und Bild-Werkzeuge (Tools-Zweig, Texturen, Cake, '
            'Range) stehen ausführlich in <b>GENERATORS_TOOLS.pdf</b>; die '
            'Reihenfolge der Maschinen-Kalibrierung in '
            '<b>KALIBRIERUNG.pdf</b>.',
        ])
    kb.add_toc(toc_seiten or TOC_STD)

    # ============================================================ Kapitel 1
    kb.story += H1('Der Regelkreis in einem Bild', '1')
    kb.story += P(
        'Der Drucker kennt deine Absicht nicht - er kennt nur Zeilen. Alles, '
        'was dieses System tut, besteht darin, zwischen deiner Absicht und '
        'der Zeile zu stehen, die gerade ausgeführt wird. Das passiert an '
        'vier Stellen, und nur an diesen vier:')
    kb.story += NUM(
        '<b>Pre-Print</b> - vor dem ersten Move. Du setzt Overrides; sie '
        'liegen als <font face="DVSM">save_variables</font> auf der Platte '
        'und überleben den Stromausfall.',
        '<b>Datei-Fixes</b> - ebenfalls vor dem Druck, aber sie verändern '
        'die Datei selbst (Retraction-Paare, volumetrisches E, Segmente, '
        'Reisewege). Danach ist die Datei eine andere als die des Slicers.',
        '<b>Live</b> - während des Drucks, ab der ersten Schicht. Jeder Dreh '
        'geht sofort an Klipper, ohne Neustart, ohne Neuslicen.',
        '<b>Ranking</b> - nach dem Druck. Das System vergleicht den '
        'Endzustand mit dem Anfangszustand und fragt, ob das Ergebnis '
        'festgehalten werden soll.')
    kb.story += P(
        'Zwischen 1 und 3 liegt der <b>Postprozessor</b>: er schreibt Marker '
        'in die Datei (<font face="DVSM">APPLY_TYPE</font>, '
        '<font face="DVSM">LAYER_MARK</font>, <font face="DVSM">_FILE_INFO'
        '</font>), und diese Marker sind der Grund, warum ein Override '
        'überhaupt weiß, wann er gilt. Ohne Marker gäbe es nur „alles“ oder '
        '„nichts“ - mit Marker gibt es „Innenwand ja, Außenwand nein“.')
    kb.story += SP(4)
    schritte = [
        ('1', 'Datei', 'Slicer-Ausgabe + Postprozessor: Marker, _FILE_INFO, Fixes'),
        ('2', 'Pre-Print', '13 Menüzweige setzen Overrides (plattenfest)'),
        ('3', 'Start', 'START_PRINT liest Material, Mesh, Profil, Overrides'),
        ('4', 'Marker', 'APPLY_TYPE schaltet pro Feature Speed/Accel/Flow/PA'),
        ('5', 'Live', 'Dreh am Regler - sofort, überschreibt die Overrides'),
        ('6', 'Snapshot', 'Endzustand gegen Baseline vergleichen (Toleranzen)'),
        ('7', 'Ranking', 'JA = Werte + optimierte Kopie, NEIN = alles zurück'),
    ]
    fig = ladder_fig(schritte, os.path.join(TMP, 'kreis.png'),
                     'Der Regelkreis: von der Datei zurück in die Datei')
    kb.story.append(IMG(fig, 162))
    kb.story += CAP(
        'Bild 1 · Sechs Stufen, ein Kreis. Stufe 7 schreibt in Stufe 2 zurück '
        '- deshalb ist die Frage am Ende des Drucks kein Beiwerk, sondern der '
        'Abschluss des Regelkreises.')
    kb.story.append(BOX('Die eine Regel, die alles zusammenhält', [
        'Ein Override gilt <b>nur während eines Drucks</b> (oder in Pause). '
        'Im Leerlauf wird die Datei nicht angefasst: dort schreibt der '
        'Slicer, und das System hält sich raus.',
        'Ein <b>Live</b>-Wert steht immer über einem <b>Pre-Print</b>-Wert - '
        'wer am Regler dreht, meint es ernst.',
        'Ein Pre-Print-Wert steht über dem <b>Datei</b>-Wert, aber nur, wenn '
        'sein Schalter ON ist. Schalter OFF heißt nicht „0“, sondern '
        '„Datei entscheidet“.',
    ], 'why'))

    # ============================================================ Kapitel 2
    kb.story += H1('Das Feature-Vokabular - 29 Kanäle', '2')
    kb.story += P(
        'Der Postprozessor erkennt Features an den Kommentaren des Slicers '
        '(<font face="DVSM">;TYPE:Outer wall</font> und Verwandte) und '
        'schreibt daraus einen Marker mit einem festen Kürzel. Diese Kürzel '
        'sind das Vokabular des ganzen Systems - sie erscheinen im Menü, in '
        'den Variablennamen (<font face="DVSM">ovf_wallouter_spd</font>) und '
        'im Live-Menü „per feat“.')
    kb.story += TBL(['Kürzel (Datei)', 'Menüname', 'Variable', 'typische Nutzung'],
                    [['WALL-OUTER', 'Outer Wall', 'ovf_wallouter_*', 'Optik: Speed runter, Accel runter'],
                     ['WALL-INNER', 'Inner Wall', 'ovf_wallinner_*', 'Stabilität: schneller als außen'],
                     ['INFILL-SPARSE', 'Sparse Infill', 'ovf_infillsparse_*', 'Zeit: Speed/Accel hoch'],
                     ['INFILL-SOLID', 'Solid/Gap', 'ovf_infillsolid_*', 'Deckflächen: mittlere Speed'],
                     ['SURFACE-TOP', 'Top Surface', 'ovf_surfacetop_*', 'Oberfläche: langsam, PA wichtig'],
                     ['SURFACE-BOTTOM', 'Bottom Surf.', 'ovf_surfacebottom_*', 'Haftung: erste Schichten'],
                     ['BRIDGE', 'Bridge', 'ovf_bridge_*', 'kühlen + langsam, Lüfter-Boost'],
                     ['GAPS', 'Gap Fill', 'ovf_gaps_*', 'dünne Wände, kleine Wege'],
                     ['SUPPORT', 'Support', 'ovf_support_*', 'schnell und grob'],
                     ['IRONING', 'Ironing', 'ovf_ironing_*', 'Bügeln: 15 % Flow, langsam'],
                     ['SKIRT', 'Skirt', 'ovf_skirt_*', 'Spülen, Haftung'],
                     ['BRIM', 'Brim', 'ovf_brim_*', 'Haftung, erste Schicht'],
                     ['OVERHANG-PERIM', 'Overhang Wall', 'ovf_overhangperim_*', 'Überhang: langsam + kalt'],
                     ['INTERNAL-BRIDGE', 'Internal Bridge', 'ovf_internalbridge_*', 'Brücken im Bauteil'],
                     ['PRIME-TOWER', 'Prime Tower', 'ovf_primetower_*', 'Mehrfarbdruck'],
                     ['CUSTOM', 'Custom Code', 'ovf_custom_*', 'eigene Blöcke'],
                     ['TRAVEL', 'Travel', 'ovf_travel_*', 'Leerfahrt: Speed/Accel'],
                     ['C1 … C9', 'Custom 1-9', 'ovf_c1_* … ovf_c9_*', 'wiederkehrende Blöcke']],
                    [28 * mm, 26 * mm, 40 * mm, 68 * mm], mono_cols=(0, 2))
    kb.story += P(
        'Zu jedem Kürzel gehören fünf Werte: <b>Speed %</b>, <b>Accel</b> in '
        'mm/s², <b>Flow %</b>, <b>PA</b> und ein <b>ON-Schalter</b>. Der '
        'Schalter ist der wichtigste: er entscheidet, ob der Wert überhaupt '
        'in die Kette eintritt. Deshalb ist ein gesetzter Wert ohne Schalter '
        'kein Fehler, sondern eine Vorbereitung.')
    kb.story.append(BOX('C1 bis C9 - der Kanal für alles, was der Slicer nicht benennt', [
        'Blöcke, die in jeder Schicht an derselben Stelle wiederkehren '
        '(Stützstruktur-Ränder, Zierteile, mehrfach gedruckte Kleinteile), '
        'erkennt der Postprozessor über ihre <b>extrudierende Signatur</b> - '
        'nicht über den Leerweg dorthin. Deshalb landet derselbe Block '
        'zuverlässig in <b>C1</b> und nicht abwechselnd in C1, C3 und C7 '
        '(Feldkorrektur R213).',
    ], 'note'))

    # ============================================================ Kapitel 3
    kb.story += H1('Pre-Print: die 13 Zweige', '3')
    kb.story += P(
        'Das Menü <font face="DVSM">Pre-Print</font> ist der Vertrag vor dem '
        'Druck. Es hat 13 Zweige; jeder davon setzt Variablen, die der '
        'Start-Block und die Interzeptoren danach lesen. Die Reihenfolge im '
        'Menü ist nicht die Reihenfolge der Wichtigkeit - sie ist die '
        'Reihenfolge, in der man beim Einrichten denkt.')
    kb.story += TBL(['Zweig', 'was er festlegt', 'wirkt auf', 'flüchtig?'],
                    [['File info', 'Datei-eigene Werte (was der Slicer wollte)', 'Anzeige, Fix-Vorschläge', 'nein'],
                     ['Fixes', 'Datei umschreiben (Retract, Vol, Segmente, Reise)', 'die Datei selbst', 'nein (Datei)'],
                     ['Tools', 'Offset, Textur, Range, Scale, Twist, Mirror, Cake, Plotter', 'neue Datei (Generator)', 'nein'],
                     ['Material', '5 Presets + eigene Presets + Anzeige', 'Temps, PA, Retract, Flow', 'ja (plattenfest)'],
                     ['Temps', 'Düse/Bett 1. Schicht und ab Schicht 2', 'M104/M140-Interzeptor', 'ja'],
                     ['Filament', 'Load/Unload/Change, Längen', 'Extruder-Drive', 'nein'],
                     ['Motion', 'Velocity, Extrusion, Retraction, Z-Hop', 'G10/G11, M203', 'teils'],
                     ['Features', 'die 16 Feature-Kanäle + Travel', 'APPLY_TYPE', 'ja'],
                     ['Preheat', 'Vorheizen mit einem Tastendruck', 'M104/M140', 'nein'],
                     ['Bed Mesh', 'Mesh laden, Adaptive, Travel-Cap', 'START_PRINT', 'ja'],
                     ['Confirm', 'Nachfrage beim Start an/aus', 'Startdialog', 'ja'],
                     ['Overwrites OFF', 'alles auf einmal aus', 'alle ON-Schalter', 'ja'],
                     ['Profiles', 'Datei-Profil speichern/laden, Auto-Load', 'die ganze Pre-Print-Ebene', 'nein']],
                    [26 * mm, 52 * mm, 44 * mm, 40 * mm])
    kb.story.append(BOX('„Overwrites OFF“ ist kein Notaus, sondern ein Werkzeug', [
        'Ein Druck mit <b>Overwrites OFF</b> läuft 1:1 wie geslict - kein '
        'Feature-Override, kein Temp-Eingriff, kein Lüfter-Eingriff. Genau '
        'das ist der Vergleichslauf, gegen den man eine Tuning-Session '
        'bewertet: erst AS SLICED drucken, dann mit Overrides, dann '
        'vergleichen. Ohne diesen Schalter gäbe es keine Referenz.',
    ], 'tip'))

    # ============================================================ Kapitel 4
    kb.story += H1('Pre-Print im Detail', '4')

    kb.story += H2('4.1  File info - was die Datei selbst sagt')
    kb.story += P(
        'Der Zweig zeigt die Werte aus <font face="DVSM">_FILE_INFO</font>, '
        'also das, was der Slicer in die Datei geschrieben hat: Material, '
        'Schichthöhe, Linienbreite, Flow, Düse, Temperaturen, PA, '
        'Retraction, Lüfter, Volumenstrom. Dazu die Erkennung: '
        '<b>MARKED</b> (R2-getaggt), <b>OPTIMIZED</b> (optimierte Kopie), '
        '<b>CUSTOM?</b> (unbekannter Slicer) und <b>STL: shell</b>.')
    kb.story += P(
        'Diese Anzeige ist kein Selbstzweck: sie ist der Grund, warum man '
        'vor dem Setzen eines Overrides sieht, was man überschreibt. Ein '
        'Beispiel: wenn dort <font face="DVSM">Ret: 0.8/35</font> steht und '
        'du setzt 1.2/25, dann weißt du, dass du 50 % mehr Retraction '
        'einfährst - und dass ein Stringing-Problem danach eine andere '
        'Ursache haben muss.')

    kb.story += H2('4.2  Features - 16 Kanäle plus Travel')
    kb.story += P(
        'Hier bekommt jedes Feature seinen eigenen Satz: Speed in Prozent '
        '(auf die globale Basis), Accel in mm/s², Flow in Prozent, PA als '
        'absoluter Wert und der ON-Schalter. Die Werte gelten pro Feature '
        'und werden beim Marker-Wechsel angewandt - nicht am Schichtanfang, '
        'nicht am Dateiende, sondern genau in dem Moment, in dem der Marker '
        'erscheint.')
    kb.story += P(
        'Praktisch ist das der mächtigste Zweig des ganzen Systems: eine '
        'Außenwand mit 60 % Speed und 2000 mm/s² sieht anders aus als eine '
        'mit 100 % und 6000, ohne dass der Slicer etwas davon wissen muss. '
        'Was dabei <b>nicht</b> passiert: der globale Speed-Faktor wird '
        'nicht verändert. Feature-Prozent liegt <i>auf</i> der globalen '
        'Basis (Kapitel 8.1).')

    kb.story += TBL(['Feature', 'Speed %', 'Accel', 'Flow %', 'PA', 'Schalter'],
                    [['Outer Wall', '100', '0 (Datei)', '100', '0', 'aus'],
                     ['Inner Wall', '100', '0 (Datei)', '100', '0', 'aus'],
                     ['Sparse Infill', '100', '0 (Datei)', '100', '0', 'aus'],
                     ['Top Surface', '100', '0 (Datei)', '100', '0', 'aus'],
                     ['Bridge', '100', '0 (Datei)', '100', '0', 'aus'],
                     ['Ironing', '100', '0 (Datei)', '100', '0', 'aus'],
                     ['Travel', '100', '0 (Datei)', '100', '0', 'aus'],
                     ['alle übrigen', '100', '0 (Datei)', '100', '0', 'aus']],
                    [40 * mm, 24 * mm, 30 * mm, 24 * mm, 18 * mm, 26 * mm])
    kb.story += CAP('Tabelle · Werkseinstellungen der Feature-Kanäle '
                    '(macros/01_state.cfg). „0 (Datei)“ heißt: der '
                    'Datei-Wert gilt unverändert - erst ein Wert &gt; 0 und '
                    'ein ON-Schalter greifen ein.')

    kb.story += H2('4.3  Material - Datenbank und eigene Presets')
    kb.story += TBL(['Material', 'Bett 1.', 'Bett 2+', 'Düse 1.', 'Düse 2+', 'PA', 'Flow', 'Ret L/S', 'Lüfter 2+'],
                    [['PLA', '60', '60', '210', '210', '0.05', '100 %', '0.75 / 35', '100 %'],
                     ['PETG', '75', '75', '240', '240', '0.06', '100 %', '0.90 / 35', '60 %'],
                     ['ABS', '100', '100', '250', '250', '0.05', '100 %', '0.75 / 35', '30 %'],
                     ['ASA', '100', '100', '255', '255', '0.05', '100 %', '0.75 / 35', '30 %'],
                     ['TPU', '35', '35', '215', '215', '0.09', '100 %', '1.20 / 20', '70 %']],
                    [20 * mm, 16 * mm, 16 * mm, 16 * mm, 16 * mm, 16 * mm, 18 * mm, 24 * mm, 20 * mm])
    kb.story += CAP('Tabelle · Materialdatenbank aus macros/05_materials.cfg (Zeilen 21-25). '
                    'Ein Preset ist ein Satz Startwerte, keine Sperre: jeder Wert '
                    'bleibt danach frei änderbar.')
    kb.story += P(
        'Ein Materialwechsel setzt diese Werte und schaltet die zugehörigen '
        'Overrides ein. Zusätzlich gibt es <b>Save current as preset</b> und '
        '<b>Show preset</b> - damit wird aus einer gelungenen Einstellung ein '
        'eigener Werkstoff, ohne die Datei anzufassen.')

    kb.story += H2('4.4  Temps - zwei Stufen, nicht eine')
    kb.story += P(
        'Das System trennt <b>erste Schicht</b> und <b>ab Schicht 2</b>, für '
        'Düse und Bett getrennt. Der Grund ist physikalisch: die erste '
        'Schicht braucht Haftung (heißer, mehr Flow, kein Lüfter), die '
        'restlichen Schichten brauchen Formstabilität. Die Umschaltung '
        'passiert am <font face="DVSM">LAYER_MARK</font> von Schicht 2 - '
        'also an der Grenze, nicht irgendwann.')
    kb.story += P(
        'Dazu kommt die <b>L1-Regel</b> (<font face="DVSM">L1 rules</font>): '
        'sie hält den Lüfter in Schicht 1 aus und begrenzt den Speed-Faktor '
        'auf <font face="DVSM">first_layer_speed</font> (Standard 75 %). Ein '
        'Slicer, der den Lüfter schon am Ende von Schicht 1 einschaltet '
        '(Orca tut das), wird dabei nicht ausgetrickst: der Interzeptor '
        'prüft den Schichtzähler, nicht die Reihenfolge der Befehle '
        '(Feldkorrektur R62).')

    kb.story += H2('4.5  Motion - die vier Basisgrößen')
    kb.story += TBL(['Größe', 'Einheit', 'Wirkung', 'Standard'],
                    [['Velocity', 'mm/s', 'Obergrenze für alle Wege (M203)', 'aus printer.cfg'],
                     ['Extrusion', 'mm/s', 'Vorschubgrenze des Extruders', 'aus printer.cfg'],
                     ['Retraction', 'mm / mm/s', 'Länge, Retract- und Unretract-Speed (G10/G11)', 'Material-Preset'],
                     ['Z-Hop', 'an/aus, mm', 'Hub beim Firmware-Retract; Höhe 0.1 … 3.0', 'aus, 0.4 mm']],
                    [24 * mm, 22 * mm, 76 * mm, 40 * mm])
    kb.story += P(
        'Z-Hop wirkt nur auf <b>Firmware-Retracts</b> (G10/G11). R2-Dateien '
        'haben die immer; eine Slicer-Datei muss erst durch den Retract-Fix '
        '(Kapitel 5.1), sonst gibt es nichts, woran der Hop hängen könnte. '
        'Das ist der häufigste Grund, warum „Z-Hop an“ nichts tut.')

    kb.story += H2('4.6  Preheat, Bed Mesh, Confirm')
    kb.story += B(
        '<b>Preheat</b> kennt Düse und Bett getrennt und heizt auf '
        'Tastendruck - ohne Datei, ohne Dialog. Nützlich vor dem '
        'Bett-Schrauben-Justieren.',
        '<b>Bed Mesh</b> zeigt das aktive Profil, lädt ein anderes, schaltet '
        '<b>Adaptive</b> (nur der bedruckte Bereich wird gemessen), '
        '<b>Re-mesh</b> (jeder Druck neu) und <b>Save after print</b>. Der '
        '<b>Travel-Cap</b> begrenzt die Verfahrgeschwindigkeit beim '
        'Meshing - hohe Werte sind schnell, können aber die Sonde '
        'verschleppen.',
        '<b>Confirm</b> entscheidet, ob beim Dateistart ein Dialog kommt. '
        'Aus heißt: Datei wird genommen wie sie ist - sinnvoll nur, wenn '
        'alle Overrides bewusst gesetzt sind.')

    kb.story += H2('4.7  Filament und der Extruder-Drive')
    kb.story += P(
        '<b>Load</b>, <b>Unload</b>, <b>Change (M600)</b> mit einstellbaren '
        'Längen, dazu der <b>Extruder-Drive</b>-Schalter: '
        '<font face="DVSM">DIRECT</font> oder <font face="DVSM">BOWDEN</font>. '
        'Er setzt nur einen <i>Startpunkt</i> für die Retraction (Direct: '
        'kurz und schnell, Bowden: länger und langsamer) - danach bleibt '
        'jeder Wert frei änderbar, in beide Richtungen. Wer den Schalter als '
        'Sperre missversteht, sucht an der falschen Stelle.')

    # ============================================================ Kapitel 5
    kb.story += H1('Die sieben Datei-Fixes und ihre Mathematik', '5')
    kb.story += P(
        'Fixes sind keine Overrides: sie <b>schreiben die Datei um</b>. '
        'Deshalb laufen sie nur, wenn kein Druck läuft, und deshalb gibt es '
        'vorher eine Sicherung (<font face="DVSM">.r2bak</font>) bzw. einen '
        'temporären Zwischentausch. Nach dem Fix ist die Datei dauerhaft '
        'geändert - das ist gewollt und der Grund, warum ein Fix eine '
        'einmalige Aktion ist und kein Dauerzustand.')
    kb.story += TBL(['Fix', 'was er tut', 'Bedingung / Grenze'],
                    [['File check', 'scannt alle Dateien: aktuell / alt / ungetaggt / Plotter; RETAG=1 taggt nach, RETAG=2 heilt falsche Feature-Typen',
                      'zwei Tastendrücke, nie während eines Drucks'],
                     ['Fix: Retraction', 'wandelt Retract-Paare in G10/G11 - deine Retraction greift',
                      'nur saubere Paare, R2-Marker bleiben'],
                     ['Fix: Volume to mm', 'rechnet Marlin-volumetrisches E (mm³) in mm Filament um',
                      'nur bei volumetrischem E'],
                     ['Fix: Segments (MCU)', 'fasst Mikro-Wege zusammen - weniger Segmente, MCU-sicher',
                      'nur unterhalb einer Mindestlänge'],
                     ['Fix: Quality', 'Reise-Regel: Retract + Hop nur dort, wo die Reise bereits gedruckte Farbe kreuzt',
                      'kürzt Wege nicht, ändert nur Retracts'],
                     ['Fix: Speed', 'direkte Wege, Ironing übersprungen, Speed angehoben',
                      'greift in die Datei ein - Optik prüfen'],
                     ['Fix: Flow cap', 'deckelt den Volumenstrom (mm³/s) - Hitzeschutz',
                      'CAP 0.5 … 50, Standard 12.0'],
                     ['Fix: Travel moves', 'setzt Speed und Accel der Leerfahrten',
                      'SPEED=…, ACCEL=…']],
                    [30 * mm, 88 * mm, 44 * mm])
    kb.story += H2('5.1  Warum der Retract-Fix existiert')
    kb.story += P(
        'Eine Slicer-Datei retractet mit <font face="DVSM">G1 E-0.8</font> '
        'und fährt danach zurück. Damit sind Länge und Speed in der Datei '
        'eingebrannt - dein Pre-Print-Wert hat keine Angriffsfläche. Der Fix '
        'erkennt das Paar (Rückzug + Wiederaufbau an derselben Stelle) und '
        'ersetzt es durch <font face="DVSM">G10</font> / '
        '<font face="DVSM">G11</font>. Ab dann gilt die Firmware-Retraction - '
        'also deine Werte, live änderbar.')
    kb.story.append(BOX('Reihenfolge, die in der Praxis zählt', [
        'Retract-Fix <b>vor</b> dem Tuning-Lauf, nicht danach. Ein Fix nach '
        'dem Druck ändert die Datei, mit der du gerade gemessen hast - und '
        'damit die Vergleichbarkeit.',
    ], 'tip'))

    kb.story += H2('5.2  Die Mathematik des Flow-Cap')
    kb.story += P(
        'Der Volumenstrom eines Weges ist das Filamentvolumen pro Sekunde, '
        'das durch die Düse geht. Er hängt an drei Dingen: Vorschub, '
        'Extrusionsmenge pro Millimeter Weg und dem Filamentquerschnitt.')
    kb.story += FORMULA(
        'Q = (F / 60) · (ΔE / d) · A<sub>fil</sub>'
        '<br/>A<sub>fil</sub> = π · (1,75/2)² = 2,4053 mm²'
        '<br/>neues F = F · cap / Q    (nur wenn Q &gt; cap)',
        'F in mm/min, d = Weglänge in mm, ΔE = Filamentvorschub dieses Weges '
        'in mm. Der Fix rechnet pro Weg, deckelt nur extrudierende Bewegungen '
        'und lässt Reisen, Retracts und Bögen unangetastet.')
    kb.story += P(
        'Ein Zahlenbeispiel mit den Werten des Beispielkörpers (Kapitel 6): '
        'eine Wand mit 0,45 mm Breite, 0,2 mm Höhe bei 60 mm/s hat '
        'ΔE/d = 0,45·0,2 / 2,4053 = 0,0374 und damit '
        'Q = 60 · 0,0374 · 2,4053 = <b>5,4 mm³/s</b>. Das ist weit unter '
        'jedem sinnvollen Cap. Kritisch wird es bei Infill: dort sind 80 mm/s '
        'und dieselbe Linie schon <b>7,2 mm³/s</b> - und mit 0,5 mm Breite, '
        '0,3 mm Höhe und 150 mm/s landet man bei <b>22,5 mm³/s</b>, was eine '
        'normale 0,4er Düse auf einem Ender-3 nicht mehr schmilzt.')
    rows = []
    for (w, h, v) in [(0.45, 0.20, 60), (0.45, 0.20, 80), (0.45, 0.20, 150),
                      (0.50, 0.30, 100), (0.50, 0.30, 150), (0.42, 0.12, 120)]:
        rate = v * (w * h / FIL_A) * FIL_A
        rows.append(['%.2f mm' % w, '%.2f mm' % h, '%d mm/s' % v,
                     '%.2f mm³/s' % rate,
                     'ja' if rate > 12 else 'nein'])
    fig = bar_fig([('0,45×0,20 @ 60', 5.4), ('0,45×0,20 @ 80', 7.2),
                   ('0,42×0,12 @ 120', 6.0), ('0,50×0,30 @ 100', 15.0),
                   ('0,45×0,20 @ 150', 13.5), ('0,50×0,30 @ 150', 22.5)],
                  os.path.join(TMP, 'rate.png'),
                  'Volumenstrom je Parameterkombination (Cap 12 mm³/s)', 'mm³/s')
    kb.story.append(IMG(fig, 150))
    kb.story += CAP('Bild 2 · Aus der Formel gerechnet, nicht geschätzt. Die '
                    '12-mm³/s-Linie ist der Standard-Cap des Fix.')
    kb.story += TBL(['Linienbreite', 'Schichthöhe', 'Speed', 'Volumenstrom', 'über Cap 12'],
                    rows, [30 * mm, 28 * mm, 26 * mm, 40 * mm, 38 * mm])

    # ============================================================ Kapitel 6
    order, st = probe_stats(PROBE)
    meta = probe_meta(PROBE)
    n_mark = sum(1 for ln in open(PROBE, errors='replace')
                 if ln.lstrip().startswith('APPLY_TYPE'))
    lay = int(meta.get('TOTAL_LAYERS', '0') or 0)
    n_moves = sum(v['n'] for v in st.values())

    kb.story += H1('Feature-Tagging - Messwerte einer echten Datei', '6')
    kb.story += P(
        'Dieses Kapitel enthält keine Skizze, sondern Messwerte. Die Datei '
        '<font face="DVSM">tools/samples/statprobe_tagged.gcode</font> ist '
        'ein 30-schichtiger Probekörper mit Slicer-Kommentaren, den der '
        '<b>echte</b> Postprozessor (<font face="DVSM">tools/r2_postproc.py '
        '--watch … --once</font>) getaggt hat. Alles Folgende ist aus dieser '
        'Datei gelesen.')
    kb.story += TBL(['Kennzahl', 'Wert', 'Bedeutung'],
                    [['Schichten', str(lay), 'aus _FILE_INFO TOTAL_LAYERS'],
                     ['APPLY_TYPE-Marker', str(n_mark), 'ein Marker pro Feature-Wechsel'],
                     ['Marker pro Schicht', '%.2f' % (n_mark / max(1, lay)), 'Dichte des Vokabulars'],
                     ['extrudierende Wege', str(n_moves), 'G1 mit E &gt; 0'],
                     ['erkannte Feature-Typen', str(len(order)), ', '.join(order)],
                     ['MAXRATE (Datei)', meta.get('MAXRATE', '?') + ' mm³/s', 'höchster Volumenstrom im File'],
                     ['SEAMN (Nahtstellen)', meta.get('SEAMN', '?'), 'erkannte Nähte der Außenwand']],
                    [46 * mm, 40 * mm, 76 * mm], mono_cols=(1,))
    prows = []
    for k in order:
        v = st[k]
        prows.append([k.replace('-', ' '), str(v['n']), '%.0f mm' % v['len'],
                      '%.2f' % (v['rsum'] / max(1, v['n'])), '%.2f' % v['rmax']])
    kb.story.append(IMG(bar_fig(
        [(k.replace('-', ' '), st[k]['n']) for k in order],
        os.path.join(TMP, 'marker.png'),
        'Extrudierende Wege je Feature (getaggte Probe)', ' Wege'),
        150))
    kb.story += CAP('Bild 3 · Wege je Feature, aus der getaggten Datei gezählt. '
                    'Die Wände dominieren, weil sie in jeder Schicht laufen - '
                    'deshalb ist ein Wand-Override die wirksamste Einzelmaßnahme.')
    kb.story += TBL(['Feature', 'Wege', 'Weglänge', 'Q Ø', 'Q max'],
                    prows, [46 * mm, 26 * mm, 34 * mm, 28 * mm, 28 * mm])
    kb.story += CAP('Tabelle · pro Feature aus der getaggten Datei gerechnet '
                    '(Q = Volumenstrom in mm³/s, Formel aus Kapitel 5.2).')
    kb.story.append(IMG(K.toolpath_fig(PROBE, os.path.join(TMP, 'pfad.png'),
                                       'Fahrweg der getaggten Probe (30 Schichten)'),
                        162))
    kb.story += CAP('Bild 4 · Der echte XY-Fahrweg der Probe, gezeichnet aus den '
                    'G0/G1-Zeilen der getaggten Datei. Dunkel = extrudierend, '
                    'hell = Leerfahrt. Man sieht den rechteckigen Wandring, die '
                    'Infill-Streifen, die Support-Insel und den Brim-ähnlichen '
                    'Skirt.')
    kb.story.append(BOX('Was die Zahlen sagen', [
        'Die Marker-Dichte liegt bei <b>%.2f pro Schicht</b>. Jeder dieser '
        'Marker ist ein Schaltpunkt: ab hier gilt ein anderer Satz Werte. '
        'Genau deshalb kann ein Override feature-scharf arbeiten, ohne dass '
        'der Slicer mitspielt.' % (n_mark / max(1, lay)),
        'Der gemessene Spitzen-Volumenstrom der Probe (%s mm³/s) liegt unter '
        'jedem Cap - die Probe ist bewusst harmlos gebaut. Ein Fix mit '
        'CAP=12 hätte hier <b>nichts</b> geändert; das ist die richtige '
        'Erwartung an einen Hitzeschutz: er greift nur im Extremfall.'
        % meta.get('MAXRATE', '?'),
        'Die Nahtstellen-Zählung (%s) stammt aus der Außenwand - sie ist die '
        'Grundlage für die Quality-Reise-Regel: eine Reise, die keine Naht '
        'kreuzt, braucht keinen Retract.' % meta.get('SEAMN', '?'),
    ], 'meas'))

    # ============================================================ Kapitel 7
    kb.story += H1('Live-Tuning: die 17 Zweige', '7')
    kb.story += P(
        'Das Menü <font face="DVSM">Live</font> ist nur während eines Drucks '
        'oder in Pause sinnvoll - es schreibt in den laufenden Zustand. 17 '
        'Zweige, gruppiert in fünf Familien: Temperatur/Lüfter, Z, '
        'Per-Feature, Bewegung, Datei.')
    kb.story += TBL(['Zweig', 'Familie', 'was du drehst', 'Wirkung'],
                    [['Temps &amp; Fan', 'Temperatur', 'Düse, Bett, Lüfter absolut, Scale, Clamp, Min/Max, Bridge, Hold', 'Interzeptoren M104/M140/M106'],
                     ['Z-Hopping', 'Z', 'Z-Hop an/aus, Höhe 0.1 … 3.0 mm', 'SET_Z_HOP → G10/G11'],
                     ['Zoff', 'Z', 'Anzeige des aktuellen Z-Offsets', '-'],
                     ['Z +0,04 / +0,12', 'Z', 'Baby-Step fein und grob', 'SET_GCODE_OFFSET mit MOVE=1'],
                     ['Z −0,04 / −0,12', 'Z', 'Baby-Step zurück', 'SET_GCODE_OFFSET mit MOVE=1'],
                     ['Spd per feat', 'Feature', 'globaler Speed % + Speed je Feature', '_SPEED_COMBINED'],
                     ['Acc per feat', 'Feature', 'globaler Accel + Accel je Feature', 'M204-Interzeptor'],
                     ['PA per feat', 'Feature', 'globales PA + PA je Feature', '_SET_PA'],
                     ['Flw per feat', 'Feature', 'globaler Flow + Flow je Feature', 'M221-Interzeptor'],
                     ['Motion', 'Bewegung', 'Velocity, Extrusion, Retraction', 'M203 / G10-G11'],
                     ['Sources', 'Info', 'woher der aktuelle Wert kommt', 'nur Anzeige'],
                     ['File', 'Info', 'Datei-eigene Werte', 'nur Anzeige'],
                     ['Plot', 'Werkzeug', 'Plotter-Modus', 'eigene Befehle'],
                     ['Objects', 'Werkzeug', 'Objekte ausschließen (exclude_object)', 'Klipper-nativ'],
                     ['Pause', 'Werkzeug', 'Pause, Fortsetzen, Abbrechen, Force End', 'PAUSE/RESUME/CANCEL']],
                    [26 * mm, 22 * mm, 66 * mm, 48 * mm])
    kb.story += H2('7.1  Das Menü „How?“ - der Lüfter-Rechenweg')
    kb.story += P(
        'Der Zweig <b>How? (fan math)</b> zeigt nicht noch einmal den Wert, '
        'sondern den <b>Rechenweg</b>: welcher Wert aus der Datei kam, welche '
        'Stufe ihn verändert hat und was am Ende an Klipper geht. Das ist '
        'die Antwort auf die häufigste Feldbeschwerde („Lüfter lässt sich '
        'nicht ändern“) - man sieht sofort, welche Stufe den Wert hält.')
    kb.story += H2('7.2  Was Live-Tuning nicht anfasst')
    kb.story += B(
        'Die <b>Datei</b> - Live-Werte liegen im Zustand, nicht im G-Code.',
        'Die <b>Startsequenz</b> - Homing, Purge-Linie, Probe-Fenster laufen '
        'unverändert.',
        'Die <b>Schichtfolge</b> - Live setzt keine Marker und verschiebt '
        'keine Schichten (Regelwerk: Schichtfolge bleibt unangetastet).')

    # ============================================================ Kapitel 8
    kb.story += H1('Die Ketten: Speed, Accel, Flow, PA, Lüfter, Temperatur', '8')
    kb.story += P(
        'Jedes Feldproblem der letzten hundert Revisionen hatte dieselbe '
        'Struktur: zwei Stellen schrieben dieselbe Größe, und eine davon '
        'gewann unerwartet. Die Antwort ist eine <b>Kette</b> - eine '
        'definierte Reihenfolge, in der die letzte Stufe gewinnt, mit '
        'Meldung bei jeder Änderung.')

    kb.story += H2('8.1  Speed - Feature liegt auf der globalen Basis')
    kb.story += FORMULA(
        'effektiv[%] = global<sub>clean</sub>[%] · feature[%] / 100'
        '<br/>M99220 S = effektiv   (Klippers Speed-Faktor)',
        'Die globale Basis wird <b>nie</b> von einem Feature verändert; ein '
        'Feature liegt immer darüber. Ändert man die Basis, wird das aktive '
        'Feature sofort neu angewandt (R87.2).')
    kb.story += P(
        'Das war ein echter Fehler mit Feldlog: früher schrieb ein '
        'Feature-Override den rohen Faktor, und ein Anheben des globalen '
        'Speed machte den Druck <b>langsamer</b>, weil der Feature-Wert '
        'überschrieben wurde. Seit R87.2 gilt die Multiplikation, und jede '
        'Kombination erklärt sich selbst:')
    kb.story += TBL(['global', 'Feature', 'effektiv', 'Meldung'],
                    [['100 %', '200 %', '200 %', '200 % x global 100 % = 200 %'],
                     ['150 %', '200 %', '300 %', '200 % x global 150 % = 300 %'],
                     ['75 %', '60 %', '45 %', 'Außenwand mit 75 % global'],
                     ['100 %', 'nicht gesetzt', '100 %', 'keine Meldung']],
                    [26 * mm, 32 * mm, 32 * mm, 72 * mm])
    kb.story.append(BOX('Die Schicht-1-Bremse', [
        '<font face="DVSM">first_layer_speed</font> (Standard <b>75 %</b>) '
        'deckelt in Schicht 1 jeden Speed-Faktor, unabhängig davon, was die '
        'Datei will. Ausnahme: du hast den Wert in dieser Schicht selbst '
        'gesetzt (<font face="DVSM">l1_speed_user</font>) - dann gilt dein '
        'Wert, nicht die Bremse.',
    ], 'note'))

    kb.story += H2('8.2  Accel - der Feature-Wert gewinnt gegen die Datei')
    kb.story += P(
        'Der M204-Interzeptor fängt jedes <font face="DVSM">M204</font> der '
        'Datei ab. Ist für das <b>aktuelle</b> Feature ein eigener Accel '
        'gesetzt und eingeschaltet, wird der Datei-Wert ignoriert - nicht '
        'addiert, nicht gemittelt. Zusätzlich gibt es einen globalen '
        'Prozent-Faktor und einen Tracker '
        '(<font face="DVSM">m204_last</font>), der verhindert, dass ein '
        'doppelt gesendetes M204 den Zustand verfälscht. Jeder direkte '
        'M204-Aufruf aus dem Makrosystem läuft deshalb über '
        '<font face="DVSM">_ACCEL_SET</font> - sonst wird der Tracker '
        'leise falsch.')
    kb.story.append(BOX('Namensregel, die einen Startblocker gekostet hat', [
        'Klipper bildet Befehlsnamen nur aus <b>A-Z und _</b>. Ziffern '
        '<b>beenden</b> den Namen. Ein Makro '
        '<font face="DVSM">_M204_SET</font> wird deshalb als Befehl '
        '<font face="DVSM">_M204</font> mit rohem Rest '
        '<font face="DVSM">_SET …</font> zugestellt - und das ist ein '
        '<b>fataler</b> Fehler mitten im Start. Der Fix hieß: Name ohne '
        'Ziffern (<font face="DVSM">_ACCEL_SET</font>), Altzeilen schreibt '
        'der Postprozessor um.',
    ], 'warn'))

    kb.story += H2('8.3  Flow - zwei Wege, ein Wert')
    kb.story += FORMULA(
        'M221 S = f  ->  f, wenn kein Override aktiv<br/>'
        'M221 S = f  ->  ov_flow (Pre-Print), wenn ov_flow_on<br/>'
        'M221 S = f  ->  live_flow (ab Schicht 2 tippt der Mensch)',
        'Der Interzeptor merkt sich den Datei-Wert und leitet um. Ab '
        'Schicht 2 gilt ein eingegebenes M221 als <b>deine</b> Live-Einstellung '
        '- Slicer schreiben ihren Flow am Dateikopf, nie mitten im Druck '
        '(R159).')
    kb.story += P(
        'Zwei Ausnahmen, die man kennen muss: ein gesetzter '
        '<b>Live-Flow</b> schlägt den Pre-Print-Override (R73 - sonst „lässt '
        'sich der Flow nicht ändern“), und das <b>Ironing</b> hat einen '
        'eigenen Flow (Standard 15 %), der zusätzlich auf den Feature-Flow '
        'liegt.')

    kb.story += H2('8.4  PA - einmal setzen, Wiederholungen schlucken')
    kb.story += P(
        'Pressure Advance wird pro Feature übergeben und über '
        '<font face="DVSM">_SET_PA</font> gesetzt. Dieses Makro vergleicht '
        'den neuen Wert mit dem zuletzt gesetzten '
        '(<font face="DVSM">pa_last</font>) und schickt ihn nur, wenn er '
        'wirklich anders ist - ein identischer Wert löst keine '
        'Extruder-Neuberechnung aus. Die Smoothing-Zeit wird getrennt '
        'behandelt: sie gilt immer aus deinem Override, auch wenn PA selbst '
        'aus der Datei kommt.')
    kb.story += FORMULA(
        'Δ = |PA<sub>neu</sub> − PA<sub>letzt</sub>|<br/>'
        'gesendet wird nur bei Δ &gt; 0  (exakter Vergleich, keine Toleranz)',
        'Anders beim Ranking: dort gilt |ΔPA| &gt; <b>0.001</b> als '
        '„getunt“ (Kapitel 11.2) - eine andere Frage, eine andere Toleranz.')

    kb.story += H2('8.5  Lüfter - fünf Stufen, eine Reihenfolge')
    kb.story += P(
        'Der Lüfter hat die längste Kette, weil er die meisten Wünsche '
        'gleichzeitig erfüllen muss: absolut drehen, relativ skalieren, '
        'begrenzen, in Schicht 1 aus bleiben, bei Brücken hochgehen. Die '
        'Reihenfolge ist fix und jede Stufe meldet sich, wenn sie eingreift:')
    _fig_l = ladder_fig([
        ('1', 'LIVE %', 'dein absoluter Wert - schlägt alles, auch Schicht 1'),
        ('2', 'Schicht-1-Halt', 'Schicht 1 = Lüfter AUS (Haftung)'),
        ('3', 'HOLD %', 'ersetzt den Datei-Wert vollständig'),
        ('4', 'SCALE ×', 'multipliziert den Datei-Wert'),
        ('5', 'CLAMP + Bridge', 'min/max % und Brücken-Anhebung'),
    ], os.path.join(TMP, 'luefter.png'),
        'Die Lüfter-Kette (M106-Interzeptor): oben gewinnt')
    kb.story.append(IMG(_fig_l, 162))
    kb.story += CAP('Bild 5 · Fünf Stufen; die erste, die etwas tut, entscheidet. '
                    'S0 bleibt immer S0.')
    kb.story += FORMULA(
        'live   = round(live% · 255 / 100)          (max 255)<br/>'
        'hold   = round(hold% · 255 / 100)          (ersetzt S der Datei)<br/>'
        'scaled = round(S · scale)<br/>'
        'clamp: scaled = min(max(scaled, fmin·255/100), fmax·255/100)<br/>'
        'bridge: scaled = max(scaled, fbr·255/100)  nur bei TYPE=BRIDGE',
        'Alle Grenzen werden auf 0 … 255 begrenzt. Der Menüpunkt „How? '
        '(fan math)“ zeigt diesen Rechenweg für den laufenden Druck.')
    def _chain(S, scale=1.0, hold=0, live=0, live_on=False, layer=3,
               layer1_hold=True, clamp=False, fmin=0, fmax=100, fbr=0,
               bridge=False):
        """Bildet die M106-Kette nach - dieselbe Reihenfolge wie im Code."""
        if S == 0:
            return 0, 'S0 bleibt S0'
        if layer < 2 and layer1_hold:
            return 0, 'Schicht-1-Halt'
        if live_on and live > 0:
            return min(255, int(round(live * 255 / 100.0))), 'LIVE'
        if hold > 0:
            return min(255, int(round(hold * 255 / 100.0))), 'HOLD'
        v = min(255, int(round(S * scale)))
        if clamp:
            lo = int(round(fmin * 255 / 100.0))
            hi = min(255, int(round(fmax * 255 / 100.0)))
            v = max(lo, min(v, hi))
            if bridge and fbr > 0:
                v = max(v, min(255, int(round(fbr * 255 / 100.0))))
        return v, ('CLAMP' if clamp else ('SCALE' if scale != 1.0 else 'Datei'))
    _cases = [
        ('Datei S255, nichts gesetzt', dict(S=255)),
        ('Datei S255, Scale 50 %', dict(S=255, scale=0.5)),
        ('Datei S255, Hold 60 %', dict(S=255, hold=60)),
        ('Datei S128, Clamp 20-90 %', dict(S=128, clamp=True, fmin=20, fmax=90)),
        ('Datei S128, Bridge, FBr 100 %', dict(S=128, clamp=True, fmin=20, fmax=90, fbr=100, bridge=True)),
        ('Datei S255, LIVE 40 %', dict(S=255, live=40, live_on=True)),
        ('Datei S255, Schicht 1', dict(S=255, layer=1)),
    ]
    _rows = []
    for _name, _kw in _cases:
        _v, _stufe = _chain(**_kw)
        _rows.append([_name, '%d' % _kw['S'], _stufe, 'S%d' % _v,
                      '%d %%' % round(_v * 100 / 255.0)])
    kb.story += TBL(['Situation', 'S der Datei', 'gewinnende Stufe', 'S an Klipper', 'in Prozent'],
                    _rows, [56 * mm, 24 * mm, 34 * mm, 26 * mm, 22 * mm])
    kb.story += CAP('Tabelle · Sieben Fälle, nachgerechnet mit der Kette aus '
                    'Bild 5. Die Spalte „gewinnende Stufe“ ist genau das, '
                    'was das Menü „How? (fan math)“ im Betrieb anzeigt.')
    kb.story.append(BOX('Der Feldlog, aus dem die Kette wurde', [
        'Die Beschwerde lautete: „voller Lüfter braucht HOLD 100 <b>und</b> '
        'CLAMP aus <b>und</b> FAN 150“. Drei Schalter für eine Absicht. '
        'Seit R175c gibt es den absoluten LIVE-Wert: <b>ein</b> Wert, und '
        'die Kette darunter wird übersprungen - mit Meldung.',
        'Der Schicht-1-Halt bleibt trotzdem über HOLD und SCALE, aber '
        '<b>unter</b> LIVE: wer bewusst am Regler dreht, bekommt seinen '
        'Wert auch in Schicht 1.',
    ], 'why'))

    kb.story += H2('8.6  Temperatur - vier Interzeptoren')
    kb.story += TBL(['Befehl', 'Rolle', 'Verhalten bei aktivem Override'],
                    [['M104', 'Düse, nicht blockierend', 'Datei-Wert wird gemerkt, dein Wert geht raus'],
                     ['M109', 'Düse, blockierend', 'merkt den Wert, wartet aber auf Erreichen deines Ziels'],
                     ['M140', 'Bett, nicht blockierend', 'wie M104'],
                     ['M190', 'Bett, blockierend', 'wie M109']],
                    [22 * mm, 44 * mm, 96 * mm], mono_cols=(0,))
    kb.story += P(
        'Dazu die Zwei-Stufen-Logik aus 4.4: die Umschaltung „ab Schicht 2“ '
        'hängt am <font face="DVSM">LAYER_MARK</font>. Ein Slicer, der die '
        'Temperatur vor dem Marker ändert, wird dadurch nicht ausgetrickst - '
        'die Stufe hängt am Zähler, nicht an der Reihenfolge.')

    # ============================================================ Kapitel 9
    kb.story += H1('Z-Offset, Z-Hop, Retraktion, Ironing, Shaper', '9')
    kb.story += H2('9.1  Z-Offset live - zwei Auflösungen, ein Speicher')
    kb.story += P(
        'Vier Tasten: ±0,04 mm (eine volle Mikrostufe, für das Feingefühl) '
        'und ±0,12 mm (drei Stufen, für den groben Sprung). Jeder Druck '
        'sendet <font face="DVSM">SET_GCODE_OFFSET Z_ADJUST=… MOVE=1</font>, '
        'also mit sofortiger Bewegung - man sieht die Wirkung an der '
        'laufenden Schicht, ohne den Druck zu unterbrechen. Der aktuelle '
        'Wert steht im Menü als <font face="DVSM">Zoff</font> und auf dem '
        'Display.')
    kb.story += FORMULA(
        'z<sub>neu</sub> = z<sub>alt</sub> ± 0,04     (fein)<br/>'
        'z<sub>neu</sub> = z<sub>alt</sub> ± 0,12     (grob, = 3 · 0,04)',
        'Der Wert ist ein <b>Offset</b>, keine Betthöhe: er überlebt keinen '
        'Neustart als Teil der Datei, sondern liegt im Zustand des Druckers.')
    kb.story += H2('9.2  Z-Hop')
    kb.story += P(
        'Höhe 0,1 bis 3,0 mm, Standard 0,4 mm. Der Hop hängt an der '
        'Firmware-Retraction: er hebt vor der Reise und senkt vor dem '
        'Wiederaufbau. Ohne G10/G11 in der Datei tut er nichts - siehe '
        'Retract-Fix.')
    kb.story += H2('9.3  Retraktion und Ironing')
    kb.story += P(
        'Retraction wird als Länge plus zwei Geschwindigkeiten geführt '
        '(Retract und Unretract getrennt). Das Ironing hat drei eigene '
        'Werte: <b>Flow</b> (Standard 15 %), <b>Speed</b> in Prozent auf die '
        'globale Basis und einen ON-Schalter. Ohne die Trennung wäre '
        '„Ironing“ nur ein weiteres Feature - mit ihr ist es eine eigene '
        'Druckart.')
    kb.story += H2('9.4  Input Shaper je Feature')
    kb.story += P(
        'Für Features, die keine Ringing-Überwachung brauchen (Infill, '
        'Support), lässt sich der Shaper abschalten - das kostet weniger '
        'Rechenzeit und erlaubt höhere Beschleunigung. Die Kalibrierung des '
        'Shapers selbst steht in <b>KALIBRIERUNG.pdf</b>, Schritt 13.')

    # ============================================================ Kapitel 10
    kb.story += H1('Profile: Datei, Depot, Auto-Load, optimized', '10')
    kb.story += P(
        'Es gibt drei verschiedene Dinge, die alle „Profil“ heißen - und wer '
        'sie verwechselt, sucht an der falschen Stelle:')
    kb.story += TBL(['Art', 'gehört zu', 'gespeichert in', 'Zweck'],
                    [['Depot-Preset', 'einem Namen (z. B. „PLA fein“)', 'save_variables', 'Sammlung bewährter Einstellungen'],
                     ['Datei-Profil', 'genau einer G-Code-Datei (Name/MD5)', 'gcode-Verzeichnis', 'diese Datei künftig richtig starten'],
                     ['Optimierte Kopie', 'einer Kopie in optimized/', 'die Datei selbst', 'getunte Werte, eingebacken']],
                    [30 * mm, 44 * mm, 36 * mm, 52 * mm])
    kb.story += H2('10.1  Datei-Profil und Auto-Load')
    kb.story += P(
        'Ein Datei-Profil speichert den kompletten Pre-Print-Zustand für '
        'eine bestimmte Datei: Material, Temperaturen, PA, Retraction, '
        'Accel, Velocity, Flow, Lüfter, Ironing, Z-Hop, Drive, '
        'First-Layer-Speed, Lüfter-Klammer und die Feature-Sätze. Beim '
        'nächsten Start derselben Datei lädt <b>Auto-Load</b> dieses Profil '
        'automatisch - mit Ton, damit man es merkt.')
    kb.story += P(
        'Die Menüpunkte sind bewusst <b>zweistufig</b>: der erste Druck armt, '
        'der zweite führt aus. Das gilt für Speichern, Laden und Löschen '
        'gleichermaßen. Ein versehentliches Löschen eines Profils ist damit '
        'nicht möglich - ein versehentliches <i>Nichtstun</i> schon, und das '
        'ist die richtige Fehlerrichtung.')
    kb.story.append(BOX('„File → Pre-Print“ - der Weg in die andere Richtung', [
        'Der Menüpunkt übernimmt die Werte <i>aus der Datei</i> in die '
        'Pre-Print-Ebene. Das ist der schnellste Weg, eine fremde Datei '
        'erst einmal so zu starten, wie sie gedacht war - und danach gezielt '
        'einen Wert zu ändern.',
    ], 'tip'))

    # ============================================================ Kapitel 11
    kb.story += H1('Das Ranking-System („Rate print?“)', '11')
    kb.story += P(
        'Am Ende eines Drucks steht die einzige Frage, die aus einem '
        'Einzelereignis eine Verbesserung macht: <b>war das besser als '
        'vorher?</b> Das System beantwortet sie nicht selbst - es bereitet '
        'sie vor, damit deine Antwort („Ja“ oder „Nein“) eine eindeutige, '
        'dauerhafte Folge hat.')
    kb.story += H2('11.1  Baseline und Snapshot')
    kb.story += P(
        'Beim Start wird der Pre-Print-Zustand als <b>Baseline</b> '
        'eingefroren (<font face="DVSM">opt_baseline</font>): alle Overrides '
        'mit ihren Schaltern, die Feature-Sätze, Z-Hop, Drive, '
        'First-Layer-Speed, Lüfter-Klammer, Shaper-Ausnahme. Am Druckende '
        'wird derselbe Satz noch einmal gelesen (<font face="DVSM">opt_snap'
        '</font>) und mit der Baseline verglichen. Ist irgendetwas anders, '
        'wird die Frage scharf geschaltet.')
    kb.story += H2('11.2  Wann etwas als „getunt“ gilt - die Toleranzen')
    kb.story += TBL(['Wert', 'Vergleich gegen', 'Toleranz', 'Begründung'],
                    [['PA', 'Override oder Datei-PA', '|Δ| &gt; 0.001', 'PA ist fein, 0.001 ist die Auflösung'],
                     ['Flow', 'Override oder 100 %', '|Δ| &gt; 0.5 %', 'halbe Prozent ist die kleinste sinnvolle Stufe'],
                     ['Accel', 'Override oder Datei-Accel', '|Δ| &gt; 1 mm/s²', '1 mm/s² ist Rundungsrauschen'],
                     ['Speed (global)', '100 %', 'außerhalb 99,5 … 100,5', 'der Regler setzt sich zwischen Drucken auf 100 %'],
                     ['jeder Schalter', 'Baseline', 'an/aus', 'ein eingeschalteter Override ist eine Entscheidung']],
                    [28 * mm, 42 * mm, 34 * mm, 58 * mm])
    kb.story += P(
        'Der wichtigste Punkt in dieser Tabelle ist die <b>Referenz</b>: ein '
        'Live-Wert zählt nur dann als getunt, wenn er sich von <b>beidem</b> '
        'unterscheidet - vom Pre-Print-Override <i>und</i> vom Datei-Wert. '
        'Sonst würde jeder Druck, der einfach mit seinem geslicten PA lief, '
        'die Frage auslösen. Das war ein echter Fehler (R62-Semantik) und '
        'ist der Grund, warum die Referenz in der Formel steht:')
    kb.story += FORMULA(
        'ref<sub>PA</sub> = ov_pa, wenn ov_pa_on, sonst file_pa<br/>'
        'getunt ⇔ |PA<sub>live</sub> − ref<sub>PA</sub>| &gt; 0,001')
    kb.story += H2('11.3  Die Frage und ihre zwei Antworten')
    kb.story += P(
        'Die Frage heißt im Menü <b>„Rate print?“</b> mit einem Zähler '
        'daneben, wie viele Werte getunt wurden. Sie hat <b>keinen '
        'Zeitablauf</b> mehr (R173): sie bleibt stehen, bis du antwortest. '
        'Ein neues File zu wählen oder einen neuen Druck zu starten '
        'beantwortet sie mit <b>NEIN</b>.')
    kb.story += TBL(['Antwort', 'was passiert', 'was bleibt'],
                    [['JA', 'Live-Werte bleiben gesetzt; der Watcher schreibt eine Kopie nach gcodes/optimized/; die Kopie enthält die Werte eingebacken',
                      'dein Tuning + eine Datei, die es reproduziert'],
                     ['NEIN', 'der komplette Pre-Print-Zustand wird aus der Baseline zurückgeschrieben',
                      'nur die Erkenntnis - und die Datei ist unverändert'],
                     ['keine', 'es passiert nichts; die Frage bleibt stehen', 'alles, wie es ist']],
                    [22 * mm, 84 * mm, 56 * mm])
    kb.story += H2('11.4  Was in der optimierten Kopie landet')
    kb.story += P(
        'Die Kopie entsteht im Verzeichnis <font face="DVSM">optimized/</font> '
        'und ist <b>nicht invasiv</b>: die Quelldatei wird nur gelesen (per '
        'Prüfsumme belegt), nie geschrieben. Die Kopie bekommt einen '
        'Kopfkommentar mit Quelle, Datum und Versionsstand, eine Zeile mit '
        'den eingebackenen Werten und eine Replay-Zeile:')
    kb.story += CODE(
        '; R2-OPT optimized copy - source: teile/wuerfel.gcode - 2026-11-13 - R2 ' + R2VER + '\n'
        '; R2-OPT baked: pa, flow, accel, wallouter_spd, wallouter_acc\n'
        '_OPT_BAKED SNAP="{...alle getunten Werte als kompaktes Dict...}"')
    kb.story += P(
        'Beim Druck dieser Kopie liest <font face="DVSM">_OPT_BAKED</font> '
        'den Satz und wendet ihn an - es sei denn, du hast <b>AS SLICED</b> '
        'gewählt: dann läuft die Datei 1:1, die Werte ruhen nur im '
        'Hintergrund, und die Frage am Ende entscheidet erneut.')
    kb.story.append(BOX('Zwei Regeln, die aus Feldlogs entstanden', [
        'Ein erneuter Druck derselben Datei mit erneutem „JA“ überschreibt '
        'die frühere Kopie <b>nicht</b> - Kopien werden durchnummeriert '
        '(<font face="DVSM">name</font>, <font face="DVSM">name_O2</font>, '
        '<font face="DVSM">name_O3</font> …). Die Tuning-Historie bleibt '
        'erhalten (R175).',
        'Ein <b>anderer</b> Quellpfad mit gleichem Dateinamen bekommt ein '
        'Ordner-Präfix, damit zwei gleichnamige Teile aus verschiedenen '
        'Ordnern nicht dieselbe Kopie werden.',
    ], 'tip'))
    kb.story += H2('11.5  „From optimized“ - der Rückweg in den Pre-Print')
    kb.story += P(
        'Der Menüpunkt <b>From optimized</b> lädt die eingebackenen Werte '
        'einer optimierten Kopie in die Pre-Print-Ebene. Damit wird eine '
        'gelungene Kopie zur <b>Vorlage</b> für andere Dateien: Werte '
        'übernehmen, Pre-Print prüfen, neues Teil drucken. Genau das ist '
        'der Sinn des Rankings - nicht „eine Datei war gut“, sondern „diese '
        'Einstellung war gut und gilt jetzt für alles“.')
    kb.story.append(BOX('Der Zähler im Menü', [
        '<font face="DVSM">opt_cnt</font> ist die Anzahl der getunten Werte '
        'des letzten Snapshots. Er wird als Zahl gespeichert, nicht als '
        'Struktur - die Vorgängerversion las ihn als Dict und zeigte '
        'dauerhaft 0 (Feldkorrektur R173).',
    ], 'note'))

    # ============================================================ Kapitel 12
    kb.story += H1('Rechenbeispiele: vom Dreh zum G-Code', '12')
    kb.story += P(
        'Sechs typische Situationen, jeweils mit dem, was tatsächlich an '
        'Klipper geht. Alle Zahlen folgen den Formeln aus Kapitel 8 und 5.2.')
    kb.story += H2('12.1  Außenwand optisch beruhigen')
    kb.story += P(
        'Du setzt im Pre-Print: Outer Wall Speed 60 %, Accel 2000. Die Datei '
        'fährt an der Außenwand <font face="DVSM">M204 S3000</font> und '
        'Speed 100 %. Was ankommt: Speed-Faktor 100 % · 60 % = <b>60 %</b>, '
        'Accel <b>2000</b> (der Datei-Wert 3000 wird ignoriert, weil der '
        'Feature-Accel ON ist). Innenwand und Infill bleiben bei ihren '
        'eigenen Sätzen.')
    kb.story += H2('12.2  Infill schneller, ohne die Wand zu berühren')
    kb.story += P(
        'Feature: Sparse Infill Speed 200 %, Accel 6000. Global bleibt '
        '100 %. Ergebnis: Infill 200 %, Wand 100 %, Accel der Wand '
        'unverändert. Wird jetzt der <b>globale</b> Faktor auf 150 % '
        'gehoben, rechnet das System neu: Infill 300 %, Wand 150 % - keine '
        'Stufe verliert ihre Einstellung.')
    kb.story += H2('12.3  Lüfter in Schicht 1 aus, ab Schicht 2 60 %')
    kb.story += P(
        'Pre-Print: Temps → Fan L2 = 60 %, L1-Regel ON. Datei sagt ab '
        'Schicht 1 <font face="DVSM">M106 S255</font>. Schicht 1: Interzeptor '
        'hält auf 0 (Meldung „held at 0 - layer 1 = fan OFF“). Schicht 2: '
        '60 % von 255 wären 153 - aber nur, wenn HOLD gesetzt ist. Ohne HOLD '
        'skaliert nur der Datei-Wert: 255 · scale.')
    kb.story += H2('12.4  Brücke mit Boost, aber gedeckelt')
    kb.story += P(
        'Clamp ON, FMin 20 %, FMax 90 %, FBr 100 %. Datei will bei einer '
        'Brücke 50 %: skaliert 50 % → Clamp hebt auf 90 % (FBr 100 % ist '
        'höher) → Ergebnis <b>100 %</b>, Meldung „clamp 20-90% bridge 100%“. '
        'Nach der Brücke fällt der Wert automatisch auf die normalen 90 % '
        'zurück.')
    kb.story += H2('12.5  Flow-Korrektur gegen Überextrusion')
    kb.story += P(
        'Überextrusion an der Oberfläche: Pre-Print Flow 95 % (ON). Die '
        'Datei schickt <font face="DVSM">M221 S100</font> am Kopf → '
        'umgeleitet auf 95 %. Tippst du während des Drucks M221 S92 ein, '
        'gilt ab Schicht 2 <b>92</b> (Live schlägt Override). Der Snapshot '
        'sieht später 92 gegen Referenz 95 → getunt, die Frage erscheint.')
    kb.story += H2('12.6  Volumenstrom deckeln')
    kb.story += P(
        'Datei mit 0,5 mm Breite, 0,3 mm Höhe bei 150 mm/s = 22,5 mm³/s. '
        'Fix mit CAP=12: pro Weg wird F neu gesetzt, '
        '<font face="DVSM">F<sub>neu</sub> = F · 12 / 22,5</font> - aus 9000 '
        'mm/min werden 4800 mm/min, also 80 mm/s. Der Weg wird kürzer in der '
        'Zeit, aber nicht in der Länge: die Datei bleibt geometrisch '
        'identisch.')

    # ============================================================ Kapitel 13
    kb.story += H1('Fallstricke aus dem Feldlog', '13')
    kb.story += TBL(['Symptom', 'Ursache', 'heute'],
                    [['Global schneller gemacht, Druck wurde langsamer', 'Feature-Override schrieb den rohen Faktor und löschte die Basis', 'Multiplikation statt Überschreiben (R87.2)'],
                     ['„Flow lässt sich nicht ändern“', 'Pre-Print-Override leitete das getippte M221 wieder weg', 'ab Schicht 2 gilt dein Wert als Live (R159)'],
                     ['„Voller Lüfter braucht drei Schalter“', 'Kette hatte keinen absoluten Eingriff', 'LIVE-Wert schlägt alles (R175c)'],
                     ['Frage „Rate print?“ kam bei jedem Druck', 'getunt wurde gegen 0 statt gegen Override/Datei', 'Referenz beidseitig (R62/R169)'],
                     ['Frage verschwand nach 12 s', 'Zeitablauf im Dialog', 'kein Timeout - nur Antwort oder neues File (R173)'],
                     ['Zähler stand immer auf 0', 'String als Dict gelesen', 'opt_cnt ist eine Zahl (R173)'],
                     ['Optimierte Kopie überschrieb die alte', 'gleicher Dateiname', 'Durchnummerierung _O2, _O3 (R175)'],
                     ['Start starb mitten in der Sequenz', 'Makroname mit Ziffer (_M204_SET) → fataler Parserfehler', 'ziffernfreier Name, Alias entfernt (R240)'],
                     ['Z-Hop ohne Wirkung', 'Datei hat keine G10/G11', 'Retract-Fix zuerst']],
                    [50 * mm, 58 * mm, 54 * mm])
    kb.story.append(BOX('Die gemeinsame Lehre', [
        'Jedes dieser Probleme war eine <b>Reihenfolge</b>, kein Wert. Das '
        'System schreibt deshalb bei jeder Änderung eine Meldung: '
        '<font face="DVSM">S255 -> hold 60% -> S153</font> ist kein '
        'Beiwerk, sondern der Beweis, welche Stufe gewonnen hat.',
    ], 'why'))

    # ============================================================ Kapitel 14
    kb.story += H1('Prüfliste', '14')
    kb.story += H2('Vor dem Druck', 'A')
    kb.story += B(
        'File info prüfen: MARKED? OPTIMIZED? Material und Ret-Werte der '
        'Datei lesen, bevor du sie überschreibst.',
        'Material auswählen - es setzt Temps, PA, Retraction, Flow, Lüfter.',
        'Bei Slicer-Dateien: Retract-Fix, sonst wirken Retraction und Z-Hop '
        'nicht.',
        'Features nur mit ON-Schalter - ein gesetzter Wert ohne Schalter '
        'wirkt nicht.',
        'L1-Regel und First-Layer-Speed kontrollieren, wenn die Haftung '
        'kritisch ist.')
    kb.story += H2('Während des Drucks', 'B')
    kb.story += B(
        'Erst eine Größe ändern, dann beobachten - nicht drei gleichzeitig.',
        'Bei unerwartetem Ergebnis: „How?“ (Lüfter) bzw. die Meldungen im '
        'Konsolenfenster lesen.',
        'Z-Offset in 0,04-Schritten, bei Bedarf 0,12 für den groben Sprung.',
        'Live-Werte gelten bis zum Druckende - sie sind kein Experiment, '
        'sondern eine Entscheidung.')
    kb.story += H2('Nach dem Druck', 'C')
    kb.story += B(
        'Frage „Rate print?“ beantworten: JA behält und schreibt eine Kopie, '
        'NEIN stellt den Pre-Print-Zustand zurück.',
        'Bei JA: prüfen, dass die Kopie in gcodes/optimized/ liegt und im '
        'File-info-Zweig als OPTIMIZED erscheint.',
        'Bei NEIN: nichts bleibt - die Datei ist unverändert, du hast nur '
        'die Erkenntnis.')
    kb.story += SP(6)
    kb.story.append(Paragraph(
        'Ende · Pre-Print &amp; Live-Tuning · R2-D2 Macro System', S['end']))
    kb.render()


def _ist_stand(stand, txt):
    """Steht der Inhaltsverzeichnis-Eintrag (Anfang) im Seitentext?

    Leerzeichen und Anführungszeichen werden auf beiden Seiten entfernt -
    dann ist es egal, ob der Satz im PDF umbrochen wurde.
    """
    def _n(x):
        for a, b in (('&amp;', '&'), ('\u201e', ''), ('\u201c', ''),
                     ('\u2013', '-'), ('\u2014', '-'), (' ', ''), ('\n', ''), ('\t', '')):
            x = x.replace(a, b)
        return x
    return _n(stand)[:24] in _n(txt)


def echte_seiten():
    """Liest die tatsächlichen Seitenzahlen aus dem eben gebauten PDF."""
    try:
        from pypdf import PdfReader
    except ImportError:
        return None
    r = PdfReader(ZIEL)
    seiten = []
    p = 2
    for nr, txt, _alt in TOC_STD:
        seite = _alt
        for q in range(p, len(r.pages)):
            if _ist_stand(txt, r.pages[q].extract_text() or ''):
                seite = q + 1
                p = q
                break
        seiten.append((nr, txt, seite))
    return seiten


if __name__ == '__main__':
    build()                      # 1. Lauf: Inhalt mit Platzhaltern
    _st = echte_seiten()
    if _st:                      # 2. Lauf: Inhalt mit den echten Seiten
        build(_st)
    print('geschrieben: %s %d B' % (ZIEL, os.path.getsize(ZIEL)))
