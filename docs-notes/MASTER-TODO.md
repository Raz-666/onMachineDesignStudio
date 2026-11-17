# MASTER-TODO — alles, was der User verlangt hat (Stand: R2-2026-11-13.1 / V1)

**Diese Datei ist ab jetzt der einzige Ort, an dem Aufgaben stehen.** Wenn etwas
nicht hier steht, existiert es für die Arbeit nicht. Jede erledigte Zeile wird
abgehakt und mit dem Commit genannt, der sie erledigt hat.

---

## A. Blocker (ohne die ist das System für den User unbedienbar)

- [x] **A1 — Ordner-Zugriff vom LCD.** *(erledigt R249)* Klippers `vsdlist` zeigt nur das
      gcodes-Root, flach. Beim Antippen einer Datei aus `generated/`,
      `optimized/` usw. tut sich nichts. Der User MUSS alle Dateien und Ordner
      am Drucker erreichen können (gesetzte Anforderung seit .114).
      **Lösung (entschieden):** Symlinks im gcodes-Root auf die Generator- und
      Optimized-Ausgaben → Klippers Liste zeigt sie als normale Einträge,
      antippbar und startbar. Kein Dienst-Stopp, Rückweg = Symlinks löschen.
      *(Wichtig: `.gcode`-Ziel, nicht das Verzeichnis — `get_file_list()` prüft
      die Erweiterung des Symlink-NAMENS.)*
- [x] **A2 — Ironing-Flow zeigt 100 % statt des echten Werts.** *(erledigt R249)* `IR:` liest
      `ovf_ironing_flw|default(100)`. Der User will den Wert, der bei Ironing
      tatsächlich wirkt — nicht eine 100 %, die er erst überschreiben müsste.
      Dazu: im Ironing-Untermenü stehen ZWEI Flow-Werte (einer davon sinnlos) —
      einer fliegt raus.
- [x] **A3 — Quality-Fix / Speed-Fix sind invertiert.** *(erledigt R249)*
      Richtig ist: **Quality** = Oberflächen und Außenwände NIE kreuzen,
      dort Z-Hop UND Retract, quer durch Infill ist erlaubt/nur dort kein
      Z-Hop nötig. **Speed** = Travels direkt verbinden, kein Zickzack,
      Ironing überspringen, Düse darf über alles fahren.
      Umgesetzt ist derzeit das Gegenteil (Z-Hop aus + quer über die Fläche).

## B. Menü (Anweisungen, die ich nicht ausgeführt habe)

- [x] **B1 — Die vier Schnellzugriffe (Spd/Acc/PA/Flw per feat) eine Ebene
      HOCH.** Sie liegen jetzt in `Live > Motion > Velocity` bzw. `> Extruder`.
      Der User will alle vier direkt unter `Live Tuning` übereinander sehen,
      ohne die zwei Zwischenebenen. (Bisher habe ich nur Titelzeilen
      hinzugefügt — das ist NICHT die Anweisung.)
- [x] **B2 — Live > Features ausdünnen/entfernen.** *(erledigt R250: 175 Sektionen gelöscht, alle Pfade im Inventar-Test dokumentiert; die vier Schnellzugriffe decken alles ab)* Der User benutzt es nicht
      (nur als Notgroschen für den versteckten Ironing-Wert). Inhalt in die
      Schnellzugriffe konsolidieren, dann das Menü raus. 176 Sektionen stehen
      unverändert.
- [x] **B3 — Titel in den vier Schnellzugriffen** (`== SPEED ==`, `== ACCEL ==`,
      `== PA ==`, `== FLOW ==`). Erledigt in R248.
- [x] **B4 — FeatSpd/FeatAcc-Duplikate entfernt** (Wert steht in der
      Feature-Zeile der Liste). Erledigt in R248.
- [ ] **B5 — Feature per Wert 0 abschalten:** geprüft und ABGELEHNT, weil
      `M220 S0` den Drucker anhält bzw. PA/Flow-0 Sonderfälle sind.
      Stattdessen `FeatOn` neben dem Wert. (Dem User so erklärt.)


## G. TEXTUREN — der große offene Block (User-Befund 13.11., mit Beweis)

**Der Befund des Users, wörtlich:** „fast alle Texturen, die ich durchprobiert
habe, haben mich überhaupt nicht überzeugt … es sind einfach nur waagerechte
Linien in unterschiedlichen Abständen, die teilweise nicht mal die Geometrie
richtig halten … keine einzige Variation sieht auch nur annähernd wie
Baumrinde aus oder wie Holzdiele oder Parkett … irgendwas hast du verhauen."

**Er hat recht, und hier ist der Beweis** (alles in diesem Lauf gerechnet):
- Bild `docs/textur-matrix-ist.png`: alle 26 Muster, gezeichnet aus der
  Funktion `_build_patterns()` selbst (nicht aus einer Beschreibung). Ergebnis:
  RIDGES / FLUTED / BARK / PLANKS / FABRIC sind **senkrechte Streifen**, die sich
  nur in der Amplituden-Modulation unterscheiden. WAVES / HATCH / ROPE sind
  **diagonale Streifen** — dieselbe Familie. HEX / SCALES / FACETS / MACRAME /
  HONEYCOMB / BRICKS sind **Punktgitter-Varianten**. GLITCH ist kaputt (flaue
  Fläche mit einem harten Band). BARK ist „vertikale Streifen mit Rauschen" —
  keine Rinde. PLANKS ist „vertikale Streifen mit Stufen" — keine Diele.
- Messung am echten Objekt (Achteck-Zylinder aus dem Shape-Tool, Ihr V52-Fall):
  Textur auf **8 Vertices pro Lage** (Vase-Modus) = eine Sägezahn-Welle zwischen
  den 8 Ecken. Deshalb sieht der 3D-Viewer bei allen Presets „Wellen" statt
  Material. Mit dichterer Abtastung (1-mm-Segmente, 207 Punkte/Lage) kommen die
  Muster heraus — aber sie bleiben Streifen.
- Der R238-„AUTO TILT" macht es **schlimmer**: er kippt jede Streifen-Familie um
  2° und schiebt sie damit optisch in **eine** Diagonale. Genau die Beobachtung
  „die unterscheiden sich fast gar nicht".
- R224 hat mehrere Muster umgebaut, R238 den Tilt eingeführt — das sind die
  Kandidaten für „verschlimmbessert".

> **Evidenzhinweis 17.11.2026:** Die genannten `2102/2102`, `2101/2101` und
> `190/190`-Makro-/Megatestzahlen unten stammen aus früheren Branch-Ständen.
> Nach den späteren Paketen #9/#10 bestand `run_review_checks.sh` auf
> `8ea17fc`, aber der neu gestartete vollständige Makrotest brach in R175d vor
> Abschluss ab (kein PASS). Aktueller Nachweis-/Gap-Stand: `analyse/RELEASE-GAP-MATRIX.md`.

- [x] **G1 — 10 unterscheidbare, codebasierte Materialreliefs.** BARK wurde
      zu wandernden Rindenfissuren/Rippen, PLANKS zu Längsbrettern mit
      versetzten Stoßfugen, BRICKS zu klaren Mauerfugen, HONEYCOMB zu echten
      sechseckigen Zellen überarbeitet. Die Soll-Matrix
      `docs/textur-matrix-soll.png` wird reproduzierbar aus den echten
      Pattern-Funktionen durch `tools/texture_matrix_preview.py` gerendert;
      Kennzahlentest prüft zehn Materialfelder auf Unterscheidbarkeit und
      Seams. Belege: `tools/r238_field_check.py` (30 Checks), Makro-Batterie
      (2102/2102). **Grenze:** algorithmische Vorschau/offline; noch kein
      gedruckter Musterstreifen oder Hardware-Freigabe.
- [x] **G2 — AUTO TILT aus und optional schaltbar.** *(opt-in umgesetzt)*
      Textur-Engine startet mit 0°; `tilt=True` aktiviert die expliziten
      Musterwinkel (für alle 27 Muster explizit festgelegt). LCD-Schalter
      `Tilt: OFF/ON` speichert die Wahl, der Watcher reicht sie an beide
      bytegleichen Engines durch. Beleg: `tools/r238_field_check.py` 30/30;
      Makro-Batterie 2102/2102;
      `tools/run_review_checks.sh` PASS (Offline, keine Hardwareabnahme).
- [x] **G3 — 27 Material-Presets an die 27 Muster gekoppelt.** Jeder Look
      verwendet genau ein eindeutiges `texture_pattern` mit dafür gesetzter
      Größe, Z-Teilung, Tiefe und Seed; die sechs zuletzt ergänzten Muster
      `KNIT/FLUTED/BARK/SCALES/FACETS/MACRAME` haben eigene Presets erhalten.
      Doppelte Varianten wurden entfernt; die separaten FUZZY-Festpresets
      bleiben erhalten. Beleg: Makro-Batterie (Library-Coverage-Prüfung).
- [x] **G4 — Wandabtastung verdichten.** BUMPS unterteilt lange lineare
      Außenwandzüge vor dem Versatz auf max. 1,5-mm-Schritte; relative E wird
      restfehlerfrei verteilt, absolute E endet am Originalwert. Belege:
      `tools/r238_field_check.py` G4 (M82/M83), `macro_render_test.py`
      2102/2102, `megatest.py` 190/190. Hinweis: G-code wird absichtlich länger.
- [x] **G5 — Geometrie-Generatoren regressiv geprüft.** Die vorhandene Form-
      Prüfung bestätigt die Generator-Geometrie; frische Matrix über Generator ×
      Düsengröße × Bett × Parameter: `tools/r217_gen_matrix.py` 1423 Checks,
      0 Fehler. Offline-Beleg, kein Druck auf Hardware.

## H. RANGE / CAKE (Ursache gefunden, Beweis geliefert)

- [x] **H1 — „Range error" nach dem Cake-Tool.** *(erledigt V1)* Ursache belegt:
      `r2_cake.py` baut die Datei aus Bewegungssegmenten neu zusammen, reicht
      aber alle **Nicht-Bewegungs-Zeilen** unverändert in BEIDE Hälften durch —
      auch den `;LAYER_CHANGE / LAYER_MARK / ;Z:`-Block. In der U-File des Users:
      **5 Marker**, Kopf behauptet `TOTAL_LAYERS=700`, Körper läuft bis Z=116.5.
      Der Layer-Zähler und die Range-Liste beschreiben also eine Datei, die es
      nicht mehr gibt → jeder Bereich landet außerhalb → „Range error".
      **Fix:** `make_range` liest den R177-Kopf und lehnt eine Schnitt-Hälfte mit
      Marker/Klausel-Widerspruch ab — **mit** Ursache und Abhilfe im Text.
      **Prüfung:** `tools/v1_range_cause_check.py` (8 Prüfungen, 3 Fixpunkte +
      Gegenprobe: ohne die Sperre rutscht die Cake-Hälfte durch).
- [x] **H2 — Cake-Tool erhält die Schichtstruktur.** *(umgesetzt V1; offline
      verifiziert)* Schnitt-Marker und `_FILE_INFO TOTAL_LAYERS` werden pro
      Hälfte aus positiven Extrusionsschichten neu aufgebaut; geneigte Z-Züge
      und G17-Helices werden exakt geteilt. Beleg: `tools/test_cake_layers_h2.py`
      sowie `tools/megatest.py` (190 Läufe, 0 Fehler).
- [x] **H3 — Cake-Ausgabe nach Nutzerklärung umgesetzt (offline geprüft).**
      `PART=BOTH` erzeugt zwei eigenständige G-code-Dateien im `Cake/`-Ordner:
      `*_CUT-U.gcode` und `*_CUT-L.gcode`; jede Datei enthält genau eine
      Hälfte. Die obere Hälfte wird standardmäßig mit der Schnittfläche aufs
      Bett reorientiert (`REORIENT=1` als Default, weiterhin explizit
      abschaltbar). Die untere Hälfte wird nicht transformiert und bleibt an
      ihrer ursprünglichen Position. Ausgabe bleibt atomar und überschreibt
      keine vorhandenen Dateien. Belege: `tools/test_cake_layers_h2.py`
      (7 Tests; H3 ergänzt: obere Reorientierung, untere Originalkoordinaten,
      separate U/L-Dateien) und `tools/macro_render_test.py` (2101/2101).
      Offline-Codeprüfung; keine Drucker-/Hardwareabnahme.

## C. Feature-Erkennung / Tagging (Paket 4 umgesetzt; offline geprüft)

- [x] **C1 — Getaggte Dateien werden weiter geprüft.** Die optionale Vollstrom-
      Tag-Geometrie-Prüfung vergleicht Marker und beobachtete Bewegungen ohne
      frühes `APPLY_TYPE`-Abbrechen oder Dateiänderung.
- [x] **C2 — Schicht-Folge-Audit pro Druckeinheit.** Prüft S1–S5 und vermeidet
      Fehlalarme bei mehrlagigem Brim, sequentiellen Teilen und umwandeten Tops.
- [x] **C3 — Brim/Skirt pro Einheit.** Erste Extrusionsschicht der Einheit ist
      maßgeblich; durchgehende bettverankerte Brims sind erlaubt.
- [x] **C4 — Slicer-Aliase und Ausschlüsse.** Cross-slicer-Vokabular und
      Nichtdruck-Annotationen sind in der Klassifizierung erfasst.
- [x] **C5 — Tag ↔ Geometrie-Gegenprüfung.** Audit meldet G1–G6 nicht-destruktiv;
      die drei Feld-Fixtures und Generator-Beispiele laufen ohne Fehlalarm.
      Belege: `tools/test_postproc_c1_c5_and_jobs.py`,
      `tools/test_shadow_analysis_audit_v2.py`, `tools/run_review_checks.sh`.
      Offline-Checks, keine Live-Watcher-/Hardwareabnahme.

## D. Dokumentation (Handbücher + PDFs)

- [x] **D1 — MANUAL.md gegen den CODE prüfen, nicht fortschreiben.** *(erledigt 29.08., Werkzeug + Bericht)*
      `tools/r265_manual_check.py` prüft Index/Zahlen/Menüpfade/Variablen/Befehle,
      `tools/r266_manual_index.py` baut Kap. 25 aus den .cfg-Dateien neu.
      Befund + Behebung: `docs-notes/MANUAL-CODE-ABGLEICH.md`.
      Behoben: Index war 4 Releases alt (194/239/100 → **409 Einträge, 265 + 114
      + 30 Hooks**), 3 LCD-Anzeigenamen falsch (`ColorPicture`,
      `ArtisticStrings`, `PI SHUTDOWN NOW`), 5 r165-Verstöße in meinen neuen
      PDF-Bauern (handgetippter Versionsstempel) → r165 wieder `clean`.
      **Offen und beim User:** Kap. 14 kennt die LIVE-Lüfterstufe (R175c) nicht —
      Entscheidung, ob das Handbuch sie nachzieht.

- [x] **D7 — Die vier großen PDFs auf ein gemeinsames Fundament.** *(erledigt V1, Commit folgt)*
      `tools/r2_pdf_kit.py` = ein Stilsatz für alle Hefte (DejaVu, Palette,
      `Doc` mit Versionskopf + Seitenzahl, `TBL/BOX/FORMULA/IMG`,
      `toolpath_fig/bar_fig/ladder_fig`). Darauf gebaut und **fertig**:
      - **D7a** `KALIBRIERUNG.pdf` — 14 S., 13-Sprossen-Leiter, Fehlerbudget-
        Formel, Materialtabelle aus `05_materials.cfg`, drei Wege, Prüfliste.
        `tools/make_calibration_pdf.py`. Alle Zahlen gegen den Code geprüft
        (u. a. Bett-Schrauben: Klipper-Kriterium `00:00`, **keine** eigene
        mm-Toleranz im Code → die frühere „0,1 mm"-Behauptung ist raus).
      - **D7b** `PREPRINT_LIVETUNING.pdf` — 22 S., Pre-Print (13 Zweige),
        Fixes mit Mathematik, Feature-Tagging **mit Messwerten aus einem
        echten Postprozessor-Lauf**, Live (17 Zweige), Ketten (Speed/Accel/
        Flow/PA/Lüfter/Temp), Profile, Ranking inkl. Toleranzen.
        `tools/make_preprint_pdf.py`.
      - **D7c** `POSTPROCESSING.pdf` — 15 S., Marker-Grammatik, `_FILE_INFO`,
        147 Feature-Namen, Zustandsmaschine, MCU-Budget-Mathematik,
        Fixes als Python, Nicht-Zähler-Brücke (45 Kanäle), Cake/Range-Regel,
        Messwerte. `tools/make_postproc_pdf.py`.
      - Reproduzierbarer Messkörper: `tools/samples/make_statprobe.py` →
        `statprobe.gcode` → echter Lauf → `statprobe_tagged.gcode`
        (104 Marker, 30 Schichten, MAXRATE 7,2 mm³/s).
      **Offen:** D7d = `GENERATORS_TOOLS.pdf` (jeder Modifier einzeln).
      Texturgrundlage jetzt mit G1–G5 aktualisiert; Heft selbst bleibt separat
      offen und muss gegen den aktuellen Generator-/Modifier-Code neu gebaut werden.
- [x] **D2 — Textur-PDF erneuert.** `tools/make_texture_pdf.py` wurde nach
      G1–G4 neu gebaut; `TEXTURING.pdf` enthält 35 Seiten, Vorschauen aus den
      aktuellen echten Pattern-Funktionen und 27 materialgebundene Presets.
      Vorschaubilder sind ausdrücklich als Algorithmus-Simulationen markiert,
      nicht als Druckergebnis.
- [ ] **D3 — Pro Generator eine wissenschaftliche PDF** (Vorbild:
      `TEXTURING.pdf`, `CUTSPLIT.pdf`): Funktionsweise, Parameter, Abläufe,
      Presets, Beispiel-Parametersätze mit erwartetem Ergebnis.
- [ ] **D4 — Pro Modifikator (Pre-Print-Geometrie-Tools) eine PDF** mit der
      Mathematik dahinter — so erklärt, dass man blind am Drucker arbeiten kann.
- [ ] **D5 — Kreativ-PDF „On-Machine Design Studio for Creative Freedom"**:
      Fehlersuche/Optimierung, kreative Verkettung, Deko-Sets, Modellbau,
      Doppel-Durchgänge. Schlusssatz (wörtlich gewünscht): *kein PC, kein
      3D-Programm, keine KI — nur ein Drehrad.*
- [ ] **D6 — Bilder-Regel (verbindlich):** keine Fantasie-Grafiken. Jede
      Anschauung muss aus den tatsächlichen Parametern und dem echten
      Algorithmus abgeleitet sein, Rechtschreibung im Bild korrekt.

## E. Crash / MCU-Shutdown (offen)

- [ ] **E1 — Shutdown: NEUE BEWEISE aus dem .142g-Feldlog (12.11., 01:36).**
      Der Shutdown kam diesmal **beim Homing des Print-Starts**, nicht am
      PRINT_END: `G28` → Z-Homing über den Probe → **4× „No trigger on probe
      after full movement"** (Probe hat NICHT ausgelöst, Düse lief auf Z=-6.0
      — Position steht im Log) → 0,47 s Reactor-Block (Stack: led_effect
      `_pollProgress`/`_getFrames`, Menu-Dispatch, TMC-Enable, delayed_gcode)
      → `MCU 'mcu' shutdown: Timer too close`. Der MCU war dabei **nicht**
      ausgelastet (`mcu_awake=0.015`, `sysload≈0.5`) — der Host hat in
      Schüben gequeued (`buffer_time` bis 3,667 s). Zwei getrennte Baustellen:
      (a) **Probe/Hardware** (PC14 mit `^!`, Deploy über PA1 + `G4 P750`) —
      ohne Trigger ist kein Druckstart möglich; (b) die Host-Seite
      (led_effect + Menü im selben Fenster). Auto-Recovery hat gegriffen
      (94 s). Nächstes: Probe-Zweig im Print-Start sauber abbrechen und die
      led_effect-Last während Homing weiter senken.
- [x] **E2 — Input Shaper ohne Beschleunigungssensor.** *(erledigt R251)*
      `CALIBRATE_SHAPER` verlangt `[resonance_tester]` + Sensor; `[input_shaper]`
      allein reicht nicht. Der manuelle Override (`ishaper_ov_*`, überlebt
      Neustarts) hatte KEINE Menüzeile → für den User unerreichbar.
      **Gelöst:** Maintenance > Vibration Cal. > **Manual** — Statuszeile (was
      Klipper JETZT fährt + Override-Zustand), pro Achse `Override: ON/off`,
      `Shaper` (ZV/MZV/EI/2HUMP_EI/3HUMP_EI oder `printer.cfg`), `Freq`
      (5–200 Hz, Schritt 0,5). Neues Makro `SHAPER_MANUAL` (live setzen +
      Boot-Override speichern, `TYPE=CONFIG` holt Typ+Freq+Damping aus
      printer.cfg zurück, `ON=0` = Override aus, ohne `[input_shaper]` klare
      Meldung). Dazu **ShpOff** wieder am LCD: Live Tuning > Spd per feat,
      Zeile direkt unter FeatOn — schaltet den Shaper für das Feature, das
      GERADE druckt (B2 hatte dem Schalter das Zuhause genommen).

- [x] **E3 — LED-Stummschaltung im Sondenfenster.** *(erledigt V1/`.142m`-Code)*
      6 von 8 Shutdowns lagen auf dem `[safe_z_home]`-XY (115,115) mitten in der
      Sondenabfahrt; im Send-Queue-Dump derselben Sekunde `neopixel_send` 3x in
      12 ms, dazu `tmcuart` und `st7920`; davor `Neopixel update did not
      succeed`, `bytes_retransmit=85`, `buffer_time=0`. `_LED_QUIET` schaltet die
      Animation für die Dauer der Bewegung stumm (G28, Mesh, Schrauben,
      PROBE_CALIBRATE), `_STATE_WATCHER` heilt eine hängende Stummschaltung.
      Prüfung: `tools/r257_crash_guard_check.py` (15 + 7 Gegenproben) und
      7 Funktionstests in der Batterie. **Am Drucker noch nicht bestätigt.**
- [ ] **E4 — Sonde löst nicht aus, Düse fährt auf Z = −6.** `[stepper_z]
      position_min = -6` in der Feld-`printer.cfg`; Vorschlag `-2`. Nicht ohne
      den User geändert (seine Datei).

## F. Erledigt (mit Beleg)

- [x] **R252 (.142h) — Postprozessor-Umschalter + Log-Paket.** Auf Anweisung:
      den laufenden Postprozessor NICHT umbauen, sondern kopieren
      (`tools/r2_postproc_next.py`, byte-gleich) und einen Schalter ins
      Systemmenü (`System > PP engine`, `pp_engine` in der variables-DATEI,
      Handover über runpy, Fallback + 15-min-Bremse, `--engine=stable`).
      Dazu `tools/r2_collect.py` (Beweispaket) mit LCD-Zeile
      `System > Diagnostics > Log pack`, Ablage in `crash_archive/` als
      `.txt` + `.txt.gcode` (Mainsail listet nur „druckbare" Dateien),
      Scan-Guard im Postprozessor, Doku (Symlink-Kapitel, 19a2, 19a3).

- [x] SD-Browser geparkt (`SD_BROWSER_ON = False`), Klippers `vsdlist` zurück;
      live geprüft: 0 `_SDM`-Queries, 0 `sd_*`-Pushes. → **aber A1/A2 offen,
      die Ersatzlösung ist noch nicht bedienbar.**
- [x] Optimized + Generated als Untermenüs unter SD Card.
- [x] B3, B4 (Titel + Duplikate).
- [x] Gates: macro_render 2052/2052, r166 OK, r142 142/0, r165 clean,
      r81 23/23, r199 18/0.
- [x] R250: Gates macro_render 2070/2070, r166 OK, r142 142/0, r165 clean,
      r81 23/23 (neu gefroren), r199 30/0.
- [x] R251: Gates macro_render 2080/2080, r166 OK (2722 Sektionen), r142 142/0,
      r165 clean, r81 23/23 (neu gefroren).
- [x] R252: Gates macro_render 2092/2092, r166 OK (2732 Sektionen), r142 142/0,
      r165 clean, r81 23/23 (neu gefroren, A/B bewiesen).
