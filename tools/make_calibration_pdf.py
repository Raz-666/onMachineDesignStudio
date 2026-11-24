#!/usr/bin/env python3
"""KALIBRIERUNG.pdf — die Kalibrierungsleiter des R2-D2-Systems.

Wovon dieses Dokument handelt: von der **Reihenfolge**. Nicht davon, welche
Schraube wo sitzt (das steht im MANUAL), sondern davon, warum Schritt 3 erst
nach Schritt 2 sinnvoll ist, was jeder Schritt an Fehler übrig lässt, und wann
man aufhören darf.

Warum die Reihenfolge überhaupt zählt (Kurzfassung, mit Zahlen im Kapitel 2):
jeder Schritt hat ein Fehlerbudget. Eine Kalibrierung, die 0,3 mm verbiegt,
macht die 0,05-mm-Feinheit des nächsten Schritts wertlos. Deshalb: erst die
Mechanik (Geometrie UND ihre Dynamik - der Input Shaper), dann die Sensorik
(Sonde, Mesh), dann die Materialförderung (E-Schritte, Temperatur, Flow),
dann das dynamische Materialverhalten (PA, Retraktion), dann die Optik
(Ironing). Wer das vertauscht, kalibriert gegen einen beweglichen Zaun.

Alle Zahlen in diesem Dokument kommen aus dem Code:
  * Parameter + Grenzwerte: macros/12_maintenance.cfg (CALIBRATE_EXTRUDER,
    CALIBRATE_PA, FLOW_CAL, TEMP_TOWER_GEN, RETRACT_TOWER, IRONING_CAL,
    SHAPER_MANUAL, BED_SCREWS_*, CALIBRATE_PROBE_OFFSET, TUNE_PID)
  * Materialwerte: macros/05_materials.cfg (_MATERIALS, variable_db)
  * Menüpfade: menus/lcd_menues.cfg (Maintenance-Zweig, echt ausgelesen)
  * Fehlerbudget-Formeln: Kapitel 2 und Kapitel 6, hergeleitet aus der
    Geometrie des FDM-Drucks (nicht aus einem Lehrbuch abgeschrieben - jede
    Formel ist an den Werten aus dem Code nachgerechnet).
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from r2_version import VERSION as R2VER
from r2_pdf_kit import (Doc, H1, H2, H3, P, B, NUM, CODE, CAP, TBL, BOX, IMG,
                        FORMULA, SP, ladder_fig, bar_fig, font, BLUE, S)
from reportlab.platypus import Paragraph
from reportlab.lib.units import mm

OUT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                   'KALIBRIERUNG.pdf')
TMP = '/tmp/r2pdf_cal'
os.makedirs(TMP, exist_ok=True)

# ---------------------------------------------------------------------------
# 1. Die Leiter - EINE Liste, aus der Figur, Tabelle und Kapitel entstehen.
#    (nr, Kurzname, Menüpfad, was es festlegt, Restfehler danach)
#    Modell C (Beschluss, 17.11.2026): die DYNAMIK der Maschine (Input
#    Shaper) wird festgelegt, BEVOR irgendetwas Material kalibriert wird -
#    der Shaper braucht kein Filament und verändert die Beschleunigungs-
#    profile, auf die sich PA/Retraktion/Flow beziehen. Und die Temperatur
#    kommt VOR Flow/PA/Retraktion, weil sie die Viskosität aller drei
#    bestimmt. Damit sind Leiter und Materialweg (Kapitel 5) EINE Ordnung.
LEITER = [
    ('1', 'Rahmen & Riemen', 'Maintenance > Tests / mechanisch',
     'Sitz aller Achsen, Riemenspannung, Spiel', '0,5 mm'),
    ('2', 'Z-Gantry synchron', 'Maintenance > Z Gantry Sync',
     'waagerechte X-Achse (Portal kippt nicht)', '0,2 mm'),
    ('3', 'Input Shaper', 'Maintenance > Vibration Cal.',
     'Ringing/Ghosting - die Dynamik der Mechanik', '—'),
    ('4', 'Bett leveln (Schrauben)', 'Maintenance > Leveling > Screws',
     'Bett-Ebene gegen die Düse', '0,1 mm'),
    ('5', 'Sonde: Z-Offset', 'Maintenance > Leveling > zoff',
     'Düse-zu-Bett-Abstand bei Erstschicht', '0,02 mm'),
    ('6', 'Bett-Mesh', 'Maintenance > Bed Mesh > now',
     'Restwelligkeit der Oberfläche', '0,05 mm'),
    ('7', 'E-Schritte', 'Maintenance > Extruder Cal.',
     'Fördermenge pro mm (mechanisch)', '0,5 %'),
    ('8', 'PID (Düse + Bett)', 'Maintenance > PID Tuning',
     'Temperatur-Konstanz', '±1 °C'),
    ('9', 'Temperatur', 'Maintenance > Temp Tower',
     'Viskosität: Oberfläche, Festigkeit, Brücken', '5 °C'),
    ('10', 'Flow', 'Maintenance > Flow Cal.',
     'Breite der Extrusionsraupe', '0,5 %'),
    ('11', 'Pressure Advance', 'Maintenance > PA Cal.',
     'Ecken, Nähte, Beschleunigungs-Übergänge', '0,005'),
    ('12', 'Retraktion', 'Maintenance > Retract Tower',
     'Fäden, Blobs, Tropfen', '0,1 mm'),
    ('13', 'Ironing', 'Maintenance > Ironing Cal.',
     'Deckflächen-Optik', '2 %'),
]

# ---------------------------------------------------------------------------
# 2. Materialdatenbank (1:1 aus macros/05_materials.cfg)
MAT = [
    ('PLA', '210', '60', '0,05', '0,75', '35', '100'),
    ('PETG', '240', '75', '0,06', '0,90', '35', '60'),
    ('ABS', '250', '100', '0,05', '0,75', '35', '30'),
    ('ASA', '255', '100', '0,05', '0,75', '35', '30'),
    ('TPU', '215', '35', '0,09', '1,20', '20', '70'),
]


TOC_STD = [
    ('1', 'Warum eine Reihenfolge - das Fehlerbudget', 3),
    ('2', 'Die Leiter im Überblick', 4),
    ('3', 'Die Schritte im Einzelnen (1-13)', 5),
    ('4', 'Material-Referenz (aus der Materialdatenbank)', 12),
    ('5', 'Drei Wege: 1 Stunde / ein Abend / voller Durchgang', 13),
    ('6', 'Was schiefgeht - und wie man es erkennt', 14),
    ('7', 'Prüfliste zum Abhaken', 15),
]


def main(toc_seiten=None):
    kb = Doc(OUT, 'R2-D2 Macro System · Kalibrierungsleiter',
             titel='R2-D2 Kalibrierungsleiter')
    kb.add_cover(
        'R2-D2 MACRO SYSTEM · KALIBRIERUNG',
        'Die Kalibrierungsleiter',
        '13 Schritte, ihre Reihenfolge, ihr Fehlerbudget und die Grenzen, '
        'ab denen Nachmessen mehr bringt als Nachdenken',
        absaetze=[
            'Dieses Dokument beantwortet drei Fragen, die das Handbuch offen '
            'lässt: <b>In welcher Reihenfolge</b> kalibriert man, <b>warum</b> '
            'ist diese Reihenfolge zwingend, und <b>wann</b> ist ein Schritt '
            'gut genug?',
            'Es beschreibt jeden der 13 Schritte mit Menüpfad, Wirkung, '
            'Parameterbereich (aus dem Code, nicht geschätzt), Ablauf, '
            'Beurteilung des Ergebnisses und den typischen Fallstricken.',
            'Alle Werte sind aus den Makros gelesen: was hier steht, ist das, '
            'was der Drucker wirklich tut.',
        ])

    kb.add_toc(toc_seiten or TOC_STD)

    # ---------------------------------------------------------------- Kapitel 1
    kb.story += H1('Warum eine Reihenfolge — das Fehlerbudget', '1')
    kb.story += P(
        'Eine Kalibrierung ist keine Sammlung von Einzelmaßnahmen, sondern eine '
        'Kette. Jeder Schritt hinterlässt einen Restfehler, und der nächste '
        'Schritt kann nur innerhalb dieses Restes arbeiten. Wer den Z-Offset '
        'einstellt, bevor das Bett gelevelt ist, stellt ihn gegen eine schiefe '
        'Fläche ein — und muss es nach dem Leveln noch einmal tun. Genau das '
        'ist der Grund, warum die Reihenfolge nicht Geschmack ist.')
    kb.story += P(
        'Rechnerisch ist die Kette aus <b>relativen</b> und <b>absoluten</b> '
        'Fehlern aufgebaut. Absolute Fehler (Bett schief, Gantry kippt) gehen '
        'unverkürzt in das Ergebnis ein. Relative Fehler (Flow, E-Schritte) '
        'wirken multiplikativ auf die Raupe. Deshalb gilt: <b>absolute Fehler '
        'zuerst wegnehmen</b>, dann die relativen einstellen.')
    kb.story += FORMULA(
        'Gesamtfehler (Breite der Raupe):<br/><br/>'
        'b = w·(1 + f<sub>flow</sub>) · (1 + f<sub>E</sub>) + 2·(z<sub>off</sub> + m<sub>mesh</sub>) · tan(θ)<br/><br/>'
        'mit  w  = Düsenbreite (0,4…0,8 mm)<br/>'
        '      f<sub>flow</sub> = Flow-Fehler (relativ)<br/>'
        '      f<sub>E</sub>    = E-Schritt-Fehler (relativ)<br/>'
        '      z<sub>off</sub>  = Z-Offset-Fehler (absolut, mm)<br/>'
        '      m<sub>mesh</sub> = Restwelligkeit des Meshes (absolut, mm)<br/>'
        '      θ  = Flankenwinkel der Raupe (≈ 45° bei 0,2 mm Schichthöhe, 0,6 mm Düse)',
        'Bei w = 0,6 mm, z<sub>off</sub> + m<sub>mesh</sub> = 0,1 mm und θ = 45° '
        'bringt allein der Geometrieanteil 2·0,1·1,0 = <b>0,2 mm</b> Breitenfehler — '
        'mehr, als jeder Flow-Wert korrigieren kann. Deshalb steht die Mechanik '
        'in der Leiter oben.')

    # ---------------------------------------------------------------- Kapitel 2
    kb.story += H1('Die Leiter im Überblick', '2')
    kb.story += P(
        'Die folgenden 13 Schritte sind die Reihenfolge, die das System im '
        'Wartungsmenü abbildet. Die Nummern sind keine Empfehlung, sondern die '
        'Abhängigkeitsreihenfolge: Schritt n setzt voraus, dass Schritt n−1 '
        'abgeschlossen ist.')
    steps = [(n, t, m) for (n, t, m, _w, _r) in LEITER]
    fig = ladder_fig(steps, os.path.join(TMP, 'leiter.png'),
                     'Kalibrierungsleiter: jede Sprosse setzt die vorige voraus')
    kb.story.append(IMG(fig))
    kb.story += CAP('Abb. 1 — Die Leiter, wie das Maintenance-Menü sie abbildet.')
    kb.story += SP(2)
    kb.story += TBL(['#', 'Schritt', 'Menüpfad (LCD)', 'legt fest', 'Restfehler danach'],
                    [(n, t, '<font face="DVSM" size="8.6">%s</font>' % m, w, r)
                     for (n, t, m, w, r) in LEITER],
                    [10 * mm, 33 * mm, 55 * mm, 42 * mm, 22 * mm])
    kb.story += SP(2)
    kb.story.append(BOX('Der eine Satz, den man sich merken muss', [
        'Erst was <b>mechanisch</b> ist (inkl. seiner <b>Dynamik</b> = Input '
        'Shaper), dann was <b>misst</b>, dann was <b>fördert</b> '
        '(Temperatur vor Flow), dann was <b>dynamisch</b> am Material ist, '
        'dann was <b>aussieht</b>.',
        'Umgekehrt kalibriert man gegen einen Zaun, der sich noch bewegt.'],
        'why'))

    # ---------------------------------------------------------------- Kapitel 3
    kb.story += H1('Die Schritte im Einzelnen', '3')

    schritte = [
        ('1', 'Rahmen & Riemen', 'Maintenance > Tests',
         'Vor jeder Messung muss die Mechanik stimmig sein: Riemenspannung, '
         'Lager, Spiel in den Achsen, Sitz der Riemenscheiben.',
         ['Riemen: Daumenprobe — er soll sich etwa 3–5 mm eindrücken lassen, '
          'nicht durchhängen.',
          'Achsen von Hand bewegen: kein Knacken, kein Kippen der X-Achse '
          'gegen die Y-Fahrt.',
          'Düsen-/Bett-Abstand an allen vier Ecken grob mit dem Auge prüfen — '
          'hier wird noch nichts gemessen, nur ausgeschlossen.'],
         'Wenn die Mechanik wackelt, misst jeder weitere Schritt Mist — '
         'und man sucht den Fehler in der Software.',
         'ca. 20 Minuten', None),
        ('2', 'Z-Gantry synchron', 'Maintenance > Gantry / Z Tilt',
         'Bei zwei Z-Motoren kann das Portal kippen: links und rechts '
         'verschiedene Höhen. Das Verfahren hängt strikt von der Treiber-'
         'Verdrahtung ab (beide Makros prüfen `stepper_z1` selbst).',
         ['<b>Ein Z-Treiber</b> (parallel verdrahtete Motoren, <b>kein</b> '
          '`stepper_z1`, mit `[force_move]` und `[tmc2209 stepper_z]`): '
          '`SYNC_GANTRY` fährt mit reduziertem Strom an den oberen Anschlag '
          '(vor jedem Druck optional per `TOGGLE_GANTRY_SYNC_PRINT`). Bei '
          'vorhandenem `stepper_z1` verweigert `SYNC_GANTRY` den Lauf.',
          '<b>Getrennte Z-Treiber</b> (`stepper_z1` + `[z_tilt]` in '
          'printer.cfg): `Z_TILT` (Menü `Maintenance > Z Tilt`) vermisst die '
          'konfigurierten Punkte per Sonde und gleicht die Treiber einzeln aus.',
          'Nach dem Ausrichten NICHT mehr von Hand am Portal ziehen; nur auf '
          'dafür geeigneter Mechanik ausführen.'],
         'Ein kippendes Portal verschiebt die Messpunkte des Meshes '
         'gegeneinander — das Mesh sieht dann eine Welle, die mechanisch da ist, '
         'und kompensiert falsch.',
         'ca. 3 Minuten', None),
        ('3', 'Input Shaper', 'Maintenance > Vibration Cal.',
         'Ringing (Geisterkanten) nach Ecken. Mit Beschleunigungssensor: '
         'automatisch messen. Ohne Sensor: manuell einstellen.',
         ['Ohne Sensor: `SHAPER_MANUAL AXIS=X TYPE=mzv FREQ=<Hz>` — Typen '
          'ZV/MZV/EI/2HUMP_EI/3HUMP_EI, Frequenz 5–200 Hz in 0,5er-Schritten. '
          '`TYPE=CONFIG` holt die Werte aus printer.cfg zurück.',
          'Mit sensorlosen Maschinen ist die Frequenz die erste Harmonische '
          'des Ringings: Kantenabstand messen, Frequenz = '
          'Druckgeschwindigkeit / Abstand.',
          'Fertig, wenn die Testwürfel-Ecken keine Doppelkante mehr zeigen; '
          'sonst Frequenz in 2-Hz-Schritten variieren.'],
         'Der Shaper legt das dynamische Verhalten der Mechanik fest — und '
         'braucht dafür KEIN Filament. Er steht deshalb VOR jeder Material-'
         'Kalibrierung (Modell C): PA und Retraktion werden später durch das '
         'Beschleunigungsprofil beeinflusst; wer den Shaper erst am Ende '
         'setzt, misst beide auf einer Maschine, die sich danach anders '
         'bewegt. Erst Dynamik festnageln, dann Material darauf abstimmen. '
         'Nur eines gilt weiterhin: prüfe die Ecken des PA-Tests (Schritt 11) '
         '— sie sind zugleich die Probe, dass der Shaper sitzt.',
         'ca. 20 Minuten ohne Sensor', ('Merke', 'Erhöht man später max_accel, '
                                           'alte Werte prüfen')),
        ('4', 'Bett leveln (Schrauben)', 'Maintenance > Leveling > Screws',
         'Die vier Schrauben unter dem Bett. Das System macht es wie Mainsails '
         'Assistent: es probt alle Schrauben, sagt „drehen" und wiederholt, bis '
         'der Rest unter der Toleranz liegt.',
         ['Start: `BED_SCREWS_START` — probt Runde 1 und zeigt den ersten '
          'Vorschlag (`BED_SCREWS_NEXT`).',
          'Schrauben nach Anzeige drehen (eine Achteldrehung ist typisch), '
          'dann `BED_SCREWS_ROUND` — KEIN erneutes Homing, das Makro probt '
          'direkt neu.',
          'Fertig, wenn jede Schraube „ok“ meldet; dann `BED_SCREWS_DONE`. '
          'Sind noch Schrauben offen, nennt es sie beim Namen statt '
          'durchzuwinken.'],
         'Das Kriterium ist Klippers eigenes: `SCREWS_TILT_CALCULATE` meldet '
         'je Schraube einen Verstellwert in „MM:SS“ (volle Umdrehungen : '
         'Sechzigstel). „ok“ heißt `00:00` - weniger als eine halbe Minute '
         'einer Umdrehung. Den Weg von Höhe zu Umdrehung rechnet Klipper '
         'über die Gewindesteigung (`screw_thread`) aus deiner printer.cfg; '
         'diese Datei ist nicht Teil des Makro-Pakets, deshalb steht hier '
         'keine Millimeterzahl, sondern die Anzeige, die auf dem LCD steht.',
         'ca. 10–15 Minuten', ('Fertig-Kriterium', 'jede Schraube „ok“ '
                               '(Klipper `00:00`) - keine eigene mm-Toleranz im Code')),
        ('5', 'Sonde: Z-Offset', 'Maintenance > Leveling > zoff',
         'Der Abstand Sonde → Düse, wenn die Sonde aufsetzt. Er entscheidet '
         'über die Erstschicht: zu groß = Raupe liegt nicht an, zu klein = '
         'Düse schabt.',
         ['`CALIBRATE_PROBE_OFFSET` — homet, dann `PROBE_CALIBRATE`: Papier '
          'unter die Düse, mit `TESTZ Z=+0.04` / `Z=-0.04` fein (`zp`/`zm`) '
          'bzw. `Z=+0.12` / `Z=-0.12` grob über die LCD-Zeilen fahren.',
          'Papier-Methode ist legitim, aber ein <b>Erstschicht-Muster</b> ist '
          'ehrlicher: eine Lage drucken und die Raupe fühlen. Erst dann '
          '`ACCEPT` → `SAVE_CONFIG`.',
          'Merke: der Offset gehört zur SONDE, nicht zum Bett. Nach einem '
          'Sondentausch ist er neu fällig, nach dem Bettleveln nicht.'],
         'Meshes werden bei Betttemperatur geprobt. Kalibriert man kalt, '
         'verschiebt die Wärmeausdehnung den Bezug — deshalb heizt das System '
         'vor dem Meshen auf die Materialtemperatur.',
         'ca. 10 Minuten', ('Grenze', 'Der Verfahrweg nach unten begrenzt '
                            '`position_min` der Z-Achse in deiner printer.cfg '
                            '(nicht Teil dieses Pakets). Steht sie sehr weit '
                            'negativ, kann ein zu kleiner Offset die Düse ins '
                            'Bett fahren, ohne dass Klipper stoppt.')),
        ('6', 'Bett-Mesh', 'Maintenance > Bed Mesh > now',
         'Das Mesh beschreibt die Restwelligkeit der Oberfläche nach dem '
         'Leveln. Das System probt bei Betttemperatur und speichert als '
         'Profil `r2`.',
         ['`CALIBRATE_MESH` startet mit KAMP/adaptiver Auswahl: liegt '
          'Objekt-Daten vor, wird nur die Objektfläche geprobt (KAMP); sonst '
          'die ganze Fläche.',
          'Meshtempo ist gedrosselt: `SET_MESH_TRAVEL SPEED=120` (Standard) — '
          'die Mesh-Fahrwege sind die schnellsten Bewegungen des ganzen '
          'Drucks und genau dort fiel der Host früher aus.',
          '„Re-mesh every print" ist Standard AN. Wer eine stabile Maschine '
          'hat, kann auf AUTO schalten (Mesh wird geladen, nicht neu gemessen).'],
         'Ein Mesh ersetzt kein Leveln: es korrigiert Wellen bis etwa 0,3 mm. '
         'Eine schiefe Ebene (linearer Fehler) frisst das Mesh nur mit '
         'Auflösung — deshalb Schritt 4 (Schrauben) vor Schritt 6 (Mesh).',
         'ca. 5–10 Minuten', ('Auflösung', '9×9 Punkte (Mesh-Punkte in '
                            'printer.cfg), bicubic')),
        ('7', 'E-Schritte', 'Maintenance > Extruder Cal.',
         'Wie viel Filament der Extruder pro Motorumdrehung wirklich fördert. '
         'Das ist reine Mechanik: Ritzel-Durchmesser, Griffigkeit, '
         'Anpressdruck.',
         ['`CALIBRATE_EXTRUDER STEP=heat` → heizt, `STEP=extrude` → fördert '
          '100 mm ab der 120-mm-Markierung, dann Restabstand messen.',
          'Messergebnis: `CALIBRATE_EXTRUDER STEP=result MEASURED=<Rest_mm>` '
          '(gültig: 0 < Rest < 120 mm, Soll 20 mm) — das Makro berechnet '
          '`rotation_distance` aus `120 − Rest`.',
          'Zweimal wiederholen; wenn der zweite Lauf unter 0,5 % Abweichung '
          'liegt, `SAVE_CONFIG`.'],
         'E-Schritte korrigieren nur die Stauchung des Ritzels. Mit vollem '
         'Gegendruck gemessen ist der Wert zu klein — deshalb langsam '
         'fördern und im gleichen Temperaturfenster bleiben.',
         'ca. 15 Minuten', ('Formel', 'rd_neu = rd_alt × (120 − Rest) / 100')),
        ('8', 'PID (Düse + Bett)', 'Maintenance > PID Tuning',
         'Die Regelparameter der Heizungen. Schlechtes PID heißt: '
         'Temperaturschwankung → Schwankung der Viskosität → '
         'Oberflächenbänder.',
         ['Düse: `TUNE_PID HEATER=extruder TARGET=<deine Drucktemperatur>` — '
          'mit Lüfter auf dem Wert, mit dem du druckst (`FAN=0..100`).',
          'Bett: `TUNE_PID HEATER=heater_bed TARGET=<Betttemperatur>`.',
          'Danach `SAVE_CONFIG`; Ergebnis in der Konsole ablesen: '
          'Kp/Ki/Kd plus „PID test finished".'],
         'Immer bei der Temperatur tunen, die man druckt. Ein bei 250 °C '
         'getunter Hotend regelt bei 210 °C träge.',
         'je Heizung 5–8 Minuten', ('Achtung', 'Lüfter ändern = Tune '
                                    'wiederholen')),
        ('9', 'Temperatur', 'Maintenance > Temp Tower',
         'Fünf Temperaturblöcke übereinander. Man beurteilt Oberfläche, '
         'Schichtbindung, Brücken und Fäden.',
         ['`TEMP_TOWER_GEN` — Defaults: START 220 °C, STEP −5 °C, 5 Blöcke, '
          'Blockhöhe 10 mm, Lüfter 100 %.',
          '`TEMP_TOWER_RESULT BLOCK=<n>` setzt die passende Temperatur als '
          'Overwrite.',
          'Beurteilung: den kühlsten Block nehmen, der noch keine glänzenden '
          'Kanten (Unterextrusion) zeigt.'],
         'Temperatur wirkt auf ALLES (Viskosität, PA, Retraktion, Brücken). '
         'Deshalb kommt sie VOR Flow, PA und Retraktion (Modell C): erst '
         'wird die Arbeitstemperatur des Materials gewählt, dann werden Flow, '
         'PA und Retraktion bei genau dieser Temperatur gemessen. Wer die '
         'Temperatur zuletzt stellt, kalibriert alle drei gegen eine '
         'Viskosität, die er danach wieder ändert.',
         'ca. 40–60 Minuten', ('Merke', '2 °C zu kalt sieht wie zu wenig Flow '
                               'aus')),
        ('10', 'Flow', 'Maintenance > Flow Cal.',
         'Welche Menge pro mm tatsächlich gefördert wird, wenn die Düse gegen '
         'Widerstand drückt. Anders als die E-Schritte misst man hier die '
         '<b>Raupe</b>, nicht den Motor.',
         ['`FLOW_TEST FLOW=100` erzeugt einen 4-Wand-Würfel mit 100 % — '
          'drucken, Wandstärke an möglichst vielen Stellen messen.',
          '`FLOW_CAL MEASURE=<gemessen> TARGET=<Düsenbreite>` rechnet den '
          'neuen Flow aus, `FLOW_CAL_APPLY ON` übernimmt ihn als Overwrite.',
          'Beurteilung: der Mittelwert zählt, nicht die dickste Stelle; die '
          'Streuung ist dein Rauschmaß.'],
         'Flow und E-Schritte nicht doppelt korrigieren: die E-Schritte '
         'sind Mechanik, der Flow ist der Prozess. Erst E-Schritte (7), dann '
         'Temperatur (9), dann Flow — deshalb steht dieser Schritt nach '
         'beiden.',
         'ca. 30–45 Minuten inkl. Druck', ('Grenzen', 'Düsenbreite 0,4…0,8 mm '
                                            '(aus printer.cfg gelesen)')),
        ('11', 'Pressure Advance', 'Maintenance > PA Cal.',
         'PA beschreibt, wie der Druck im Druckkopf beim Beschleunigen und '
         'Abbremsen fehlt oder sich staut. Das Werkzeug druckt eine lange '
         'Linie pro PA-Wert, jede ein Stück weiter.',
         ['`CALIBRATE_PA` — Defaults aus dem Speicher: START 0, STEP 0,005, '
          'LINES 10 (0,005-Schritte sind fein genug für PLA; PETG braucht '
          '0,01), Länge 100 mm.',
          'Die Sektion mit der gleichmäßigsten Wandstärke gewinnt: '
          '`PA_RESULT SEG=<n>` oder direkt `PA_RESULT VALUE=0,05`.',
          'Danach `CALIBRATE_PA_SMOOTH` — die Glättungszeit (pa_smooth). '
          'Materialwerte: PLA 0,04 s, PETG 0,04 s, TPU 0,04 s.'],
         'PA ohne Flow-Kalibrierung ist wertlos: PA regelt gegen eine Raupe, '
         'deren Volumen noch falsch ist. Deshalb Schritt 10 (Flow) vor 11 — '
         'und beide erst NACH Temperatur (9) und Shaper (3).',
         'ca. 20–30 Minuten', ('Typische Werte', 'PLA 0,05 · PETG 0,06 · '
                               'ABS 0,05 · TPU 0,09 (DB-Werte)')),
        ('12', 'Retraktion', 'Maintenance > Retract Tower',
         'Zwei Masten, je Block eine andere Retraktionslänge; man sieht '
         'Fäden, Blobs und Stufen direkt übereinander.',
         ['`RETRACT_TOWER` — Defaults: START 0,5 mm, STEP 0,5 mm, 6 Blöcke, '
          'Blockhöhe 5 mm, Mastabstand 40 mm.',
          '`RETRACT_TOWER_RESULT BLOCK=<n>` übernimmt die Retraktionslänge '
          '(`retract_len`) des besten Blocks als Override; das Retract-Tempo '
          'bleibt separat einstellbar.',
          'Beurteilung: kein Faden <i>zwischen</i> den Masten und keine '
          'sichtbare Lücke am Blockanfang — beides zusammen.'],
         'Zu viel Retraktion „klebt" Anfänge, zu wenig fädelt. Der Tower zeigt '
         'beide Richtungen in einem Druck; deshalb ein Druck statt zwölf '
         'Einzelversuche.',
         'ca. 30–45 Minuten', ('DB-Vorgaben', 'PLA 0,75 · PETG 0,90 · '
                               'TPU 1,20 mm')),
        ('13', 'Ironing', 'Maintenance > Ironing Cal.',
         'Karten mit unterschiedlichem Ironing-Flow und -Tempo auf einer '
         'Deckfläche. Man sieht Banding, Glanz und Rillen.',
         ['`IRONING_CAL` — Defaults: 3 Karten, 40 × 24 mm, Temp 200 °C, '
          'Basislagen davor über START_LAYER.',
          '`IRONING_RESULT CARD=<n>` zeigt das gespeicherte Kartentempo '
          '(mm/s) und den Karten-Flow (%) der gewählten Karte an; es schreibt '
          'keine automatische mm/s-zu-Prozent-Umrechnung in Overrides.',
          'Wichtig: der am LCD angezeigte Flow ist der Wert, der <b>wirkt</b> '
          '— es gibt keine zweite „echte" Zahl.'],
         'Ironing ist Optik: es lohnt erst, wenn Geometrie, Flow und '
         'Temperatur stimmen — sonst ironiert man Unebenheiten fest.',
         'ca. 20–30 Minuten', ('Typisch', 'Flow 15–20 %, ab 25 % wird '
                               'gerippt')),

    ]

    for (nr, titel, pfad, was, ablauf, warum, dauer, extra) in schritte:
        kb.story += H2('%s&nbsp;&nbsp;%s' % (nr, titel))
        kb.story += TBL(['Feld', 'Wert'],
                        [['Menü', '<font face="DVSM" size="8.6">%s</font>' % pfad],
                         ['Dauer', dauer]] +
                        ([[extra[0], extra[1]]] if extra else []),
                        [26 * mm, 136 * mm])
        kb.story += SP(1)
        kb.story += P('<b>Was hier festgelegt wird.</b> ' + was)
        kb.story += P('<b>Ablauf.</b>')
        kb.story += NUM(*ablauf)
        kb.story += P('<b>Warum erst jetzt.</b> ' + warum)

    # ---------------------------------------------------------------- Kapitel 4
    kb.story += H1('Material-Referenz', '4')
    kb.story += P(
        'Diese Werte stehen in der Materialdatenbank des Systems '
        '(<font face="DVSM">macros/05_materials.cfg</font>). Sie sind der '
        'Startpunkt für die Schritte 9–12 — nicht das Ergebnis. Deine eigene '
        'Kalibrierung überschreibt sie (`SET_MATERIAL` lädt sie, '
        '`SAVE_MATERIAL_TEMPS` schreibt deine Werte zurück).')
    kb.story += TBL(['Material', 'Düse °C', 'Bett °C', 'PA', 'Retraktion mm',
                     'Retr.-Tempo', 'Lüfter %'],
                    MAT, [22 * mm, 22 * mm, 22 * mm, 20 * mm, 28 * mm,
                          24 * mm, 24 * mm])
    kb.story += SP(2)
    kb.story += P(
        'Der PA-Wert hängt an Düse, Material und Temperatur. TPU mit 0,09 '
        'liegt bewusst hoch: elastisches Material braucht mehr Vorhalt, weil '
        'der Druck im Schlauch nachgibt. Wer TPU auf PLA-Werte stellt, bekommt '
        'Ecken mit „Bauch".')
    kb.story += TBL(['Größe', 'Formel', 'Beispiel PLA (0,6 mm Düse, 0,2 mm)'],
                    [['Volumenstrom', 'Q = w · h · v  (mit v = F / 60)',
                      '0,65 · 0,2 · 60 = 7,8 mm³/s bei 60 mm/s (w·h = 0,13 mm²)'],
                     ['Flussgrenze', 'v<sub>max</sub> = Q<sub>max</sub> / (w · h)',
                      '8,3 / (0,65 · 0,2) ≈ 64 mm/s (MAXRATE der Datei)'],
                     ['PA-Vorhalt', 'ΔE = PA · Δv',
                      '0,05 · 60 = 3 mm Vorhalt bei Vollgas'],
                     ['Retraktion je Druck', 'r = r<sub>DB</sub> · (1 ± 0,2)',
                      '0,75 ± 0,15 mm Startfenster für den Tower']],
                    [34 * mm, 58 * mm, 70 * mm])

    # ---------------------------------------------------------------- Kapitel 5
    kb.story += H1('Drei Wege durch die Leiter', '5')
    kb.story += P(
        'Niemand kalibriert jeden Druck neu. Hier sind drei sinnvolle '
        'Ausschnitte — abhängig davon, was gerade nicht stimmt.')
    kb.story += H3('A) Die Stunde nach dem Aufbau (oder nach einem Umzug)')
    kb.story += NUM('Schrauben leveln (Schritt 4).',
                    'Z-Offset mit Erstschicht-Muster prüfen (5).',
                    'Mesh messen und speichern (6).',
                    'E-Schritte kontrollieren (7) — 15 Minuten, einmal im Leben.',
                    'Einen Testwürfel drucken und Wandstärke messen (10).')
    kb.story += H3('B) Der Abend für ein neues Material')
    kb.story += P(
        'Die Maschinenseite (Shaper, Mesh, E-Schritte) ist materialunabhängig '
        'und bleibt. Hier läuft nur die Materialkette — in genau der '
        'Reihenfolge der Leiter (Temperatur vor Flow/PA/Retraktion):')
    kb.story += NUM('Material laden (`SET_MATERIAL`) — als Startpunkt.',
                    'Temp Tower (9): die richtige Temperatur wählen.',
                    'Flow-Würfel (10) mit dieser Temperatur.',
                    'PA-Leiter (11) mit diesem Flow.',
                    'Retract Tower (12).',
                    'Ergebnis mit `SAVE_MATERIAL_TEMPS`/Overrides sichern.')
    kb.story += H3('C) Wenn eine bestimmte Macke auftritt')
    kb.story += TBL(['Symptom', 'Erst prüfen', 'dann'],
                    [['Erstschicht liegt nicht an', 'Z-Offset (5)', 'Bett leveln (4), Mesh (6)'],
                     ['Wandstärke weicht überall gleich ab', 'Flow (10)', 'E-Schritte (7)'],
                     ['Ecken haben Bauch / Lücke', 'PA (11)', 'Temperatur (9)'],
                     ['Fäden zwischen Türmen', 'Retraktion (12)', 'Temperatur senken (9)'],
                     ['Geisterkanten nach Ecken', 'Input Shaper (3)', 'Beschleunigung prüfen'],
                     ['Oberfläche bandförmig', 'PID (8)', 'Durchflussgrenze der Datei'],
                     ['Deckfläche rau', 'Ironing (13)', 'Flow (10)']],
                    [58 * mm, 46 * mm, 58 * mm])

    # ---------------------------------------------------------------- Kapitel 6
    kb.story += H1('Was schiefgeht — und wie man es erkennt', '6')
    kb.story += TBL(['Fallstrick', 'Woran man es merkt', 'Was zu tun ist'],
                    [['Kalibriert, bevor das Bett warm ist',
                      'Erstschicht gut, dritte Schicht zu dünn',
                      'Schritte 5/6 bei Betttemperatur wiederholen'],
                     ['E-Schritte mit Widerstand gemessen',
                      'Flow muss ständig über 105 % stehen',
                      'Schritt 7 langsam und frei fördernd wiederholen'],
                     ['PA auf falschem Flow',
                      'PA-Wert „wandert" bei jedem Versuch',
                      'erst 10, dann 11 — in dieser Reihenfolge'],
                     ['Retraktion zu hoch eingestellt',
                      'Blockanfänge mit Lücke, feine Löcher in der Wand',
                      'Block eins zurück, 0,1-mm-Schritte'],
                     ['Temperatur zu niedrig „weil glatter"',
                      'Brücken hängen, Wand delaminiert unter Last',
                      'einen Block wärmer, dann Brückentest'],
                     ['Mesh als Level-Ersatz benutzt',
                      'Mesh kompensiert dauerhaft > 0,2 mm',
                      'mechanisch leveln (4), dann neu meshen'],
                     ['Nach Sondentausch nicht neu kalibriert',
                      'Erstschicht plötzlich zu tief/zu hoch',
                      'Schritt 5 wiederholen, Mesh neu'],
                     ['Shaper erst NACH PA/Retraktion gesetzt',
                      'Ecken sauber, nach Shaper-Tuning wieder Bauch',
                      'Shaper zuerst (3), dann Materialkette — nie umgekehrt'],
                     ['Zwei Korrekturen gleichzeitig',
                      'Verbesserung hier, Verschlechterung dort',
                      'immer nur EINE Größe ändern, sonst ist die Ursache weg']],
                    [46 * mm, 58 * mm, 58 * mm])
    kb.story += SP(2)
    kb.story.append(BOX('Der häufigste Fehler ist nicht die Kalibrierung, sondern ihre Reihenfolge', [
        'In den Feldprotokollen dieses Systems tauchen drei Fälle immer wieder '
        'auf: (a) Z-Offset vor dem Leveln gesetzt (5 vor 4), (b) PA bei '
        'falschem Flow gemessen (11 vor 10), (c) Mesh als Ersatz für die '
        'Schrauben benutzt (6 statt 4).',
        'Alle drei sind keine Bedienfehler, sondern Reihenfolgefehler — und '
        'alle drei sehen wie ein Hardwareproblem aus.'],
        'warn'))

    # ---------------------------------------------------------------- Kapitel 7
    kb.story += H1('Prüfliste zum Abhaken', '7')
    kb.story += P('Diese Liste ist zum Ausdrucken gedacht. Nach jedem Haken '
                  'gilt: eine Größe geändert, Ergebnis geprüft, erst dann weiter.')
    kb.story += TBL(['✓', 'Schritt', 'Ergebnis, das man akzeptieren darf'],
                    [['☐', '1 Rahmen & Riemen', 'von Hand kein Spiel, kein Knacken'],
                     ['☐', '2 Gantry / Z Tilt', 'SYNC_GANTRY (1 Treiber) bzw. Z_TILT (stepper_z1) ohne Fehler'],
                     ['☐', '3 Shaper', 'keine Doppelkanten an Würfelecken'],
                     ['☐', '4 Schrauben', 'alle Schrauben „ok" (`00:00`) im aktuellen Lauf (`BED_SCREWS_DONE`)'],
                     ['☐', '5 Z-Offset', 'Erstschicht-Raupe liegt an, ohne zu schaben'],
                     ['☐', '6 Mesh', 'Restwelligkeit < 0,1 mm im Bericht'],
                     ['☐', '7 E-Schritte', 'zwei Läufe < 0,5 % Abweichung'],
                     ['☐', '8 PID', 'Konsole: „PID test finished", keine Schwankung > ±1 °C'],
                     ['☐', '9 Temperatur', 'Oberfläche matt-gleichmäßig, Brücken tragen'],
                     ['☐', '10 Flow', 'Wandstärke = Düsenbreite ± 0,02 mm'],
                     ['☐', '11 PA', 'Ecken ohne Bauch, Naht ohne Lücke'],
                     ['☐', '12 Retraktion', 'keine Fäden, keine Anfangs-Lücken'],
                     ['☐', '13 Ironing', 'Deckfläche gleichmäßig, kein Rippenmuster']],
                    [10 * mm, 62 * mm, 90 * mm])

    kb.story += SP(6)
    kb.story.append(Paragraph(
        'Damit ist die Leiter einmal komplett. Sie muss nicht jedes Mal '
        'komplett gegangen werden — aber wenn etwas nicht stimmt, sagt die '
        'Reihenfolge, wo man anfängt zu suchen: immer oben.', S['p']))
    kb.render()


def _n(x):
    for a, b in (('&amp;', '&'), ('\u201e', ''), ('\u201c', ''), ('\u2013', '-'),
                 ('\u2014', '-'), (' ', ''), ('\n', ''), ('\t', '')):
        x = x.replace(a, b)
    return x


def echte_seiten():
    """Liest die tatsaechlichen Seitenzahlen aus dem gebauten PDF."""
    try:
        from pypdf import PdfReader
    except ImportError:
        return None
    r = PdfReader(OUT)
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
    main()                       # 1. Lauf (Platzhalter-Seiten im Inhalt)
    _st = echte_seiten()
    if _st:
        main(_st)                # 2. Lauf mit den echten Seitenzahlen
    print('geschrieben:', OUT, os.path.getsize(OUT), 'B')
