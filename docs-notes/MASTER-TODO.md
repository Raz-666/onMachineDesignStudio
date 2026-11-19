# MASTER-TODO — alles, was der User verlangt hat (Stand: R2-2026-11-18.2 / V3)

**Diese Datei ist ab jetzt der einzige Ort, an dem Aufgaben stehen.** Wenn etwas
nicht hier steht, existiert es für die Arbeit nicht. Jede erledigte Zeile wird
abgehakt und mit dem Commit genannt, der sie erledigt hat.

**Befund 2026-11-18 (Quellen-Ordnung, vom Nutzer geklärt):** Maßgebliche Quelle ist `R2-D2 – Gesamtbriefing für die Coding-GPT.md` (STL-Export-Ergänzung §24 + Ergänzungen 20–31), Vorgängerfassung = `R2_Vollstaendiges_Startbriefing_Coding-KI_finalizedByGemini.txt` (STL dort §5.21), Masterkonzept = Grundgedanke, „Reverse Engineering von G-Code Geometrien.md“ = Detaildokument. `Master_Spezifikation.md` liegt nicht vor. `slicer-families.md` / `Potential performance& compatibility issues.md` bleiben ungeprüfte AI-Notizen — ohne Einzelverifikation kein Beleg. Alle sechs Uploads SHA256-geprüft; Gesamtbriefing-GPT neu ins Manifest aufzunehmen (Release-/Doku-Schritt, kein Produktcode).

**Erledigt 2026-11-18 (Fortsetzung, Branch `arena/4ea70100-...`):** **Gesamtumbau-Analyse fertiggestellt und als Release `R2-2026-11-18.2` / `V3` ausgeliefert** — `tools/gcode_re.py` (Unified Masterkonzept Pass 0–11, Schema `r2-re/2`): Vektor-Pass-6 (Online-Loop-Extraktion, Nesting per Point-in-Polygon, Hatch-Spacing), Pass-8 Feature-Scores v2 (Top-3, UNKNOWN/AMBIGUOUS, `calibrated: false`), Pass-10-Konservation (Zeilen + Filament Shadow↔Tracker, Ratio 1,0 am rose-Fixture), Pass-11 atomares Sidecar (read-only Quelle, SHA-256, kein Überschreiben ohne `--force`). `tools/test_gcode_re.py` 10/10. Gates: Makro 2103/2103, megatest 190/190, review_checks PASS, r91 PASS, r81 23/23 (stamp-class, A/B), r199 12/12. Kein Eingriff in den Druckpfad; Feldabnahme steht aus (Drucker nicht testbereit). Dazu `docs-notes/PRINTER-CFG-AUDIT-2026-11-18.md` (E1/E4 zu `position_min`/Probe — NUR Vorschläge, nicht angewendet). Report: `docs/RELEASE_R2-2026-11-18.2_REPORT.md`.

**Erledigt 2026-11-18:** Release **`R2-2026-11-18.1` / `V2`** gebaut und belegt
(Nutzer-Go 18.11.): R258 Option B (Kommentarzeilen-unabhängige TOTAL_LAYERS,
gemergt `ce0015a`), Versionsstempel in Code/Makro/Web/`GENERATORS_TOOLS.pdf`,
r81-Re-Freeze (mr01–13 stamp-only A/B, pr03/pr08 je 1 Zeile), Gates grün,
ZIP nur aus getrackten Dateien (ohne `analyse/`), SHA256 + r199 12/12 —
siehe `docs/RELEASE_R2-2026-11-18.1_REPORT.md`. Feldabnahme am Drucker steht aus.

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
      **Freigegeben und ergänzt:** Kap. 14 LIVE-Lüfterbedienung. Die frühere
      Behauptung „kennt LIVE nicht“ war überholt: eine Kurzbeschreibung
      stand bereits dort. Jetzt zusätzlich zeilenweise Bedienreferenz.

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
      **Teilstand D7d (17.11.2026, späte Fortsetzung):** `GENERATORS_TOOLS.pdf` aus dem
      aktuellen Code neu gebaut — Versionskopf jetzt `R2-2026-11-13.1` (vorher
      handgepflegter Stempel `R2-2026-11-12.142j`, 12×), Textur-Zeile auf
      „27 Muster, 27 fertige Vorlagen“ (Codestand G1–G5). Inhalte/Umfänge
      unverändert (12 Seiten, 11 Generatoren, 14 Datei-Werkzeuge).
      Weiter offen: Modifier einzeln tief dokumentieren (Mathematik pro
      Modifier) — Umfang von D4, nicht mit diesem Rebuild erledigt.
      Offizieller D7d-Abschluss braucht noch die User-Durchsicht des PDFs.
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
- [x] **D5 — Kreativ-PDF „On-Machine Design Studio for Creative Freedom"** *(erledigt
      2026-11-18, Commit `9468051`)*: Titel gesetzt, neue Kapitel Modellbau
      (Toleranzen, Doppel-Durchgang ehrlich), Deko-Sets (Varianten-Strategie),
      Doppel-Durchgänge (geht / geht bewusst nicht), Fehlersuche und
      Optimierung (Symptom → Ursache → Werkzeug), plus bisherige Zwölf
      Rezepte / Material-Licht-Wandstärke / Bewusst-nicht-tut. Schlusssatz
      verbatim: *kein PC, kein 3D-Programm, keine KI — nur ein Drehrad.*
      `CREATIVE_POSSIBILITIES.pdf`, 10 Seiten (vorher 7), TOOLS_INVENTORY
      nachgezogen.
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



## I. STL-Export (Nutzer-Go 2026-11-18 — zuerst Bestandsaufnahme, dann Tests, dann Fix)

- [ ] **I1 — STL-Export funktionsfähig machen (Briefing §24).**
      Reihenfolge verbindlich: (1) Bestandsaufnahme erledigt —
      `analyse/STL-EXPORT-AUDIT.md` (Ablauf, Risiken, Testlücken,
      Orakel-Testplan Phase 2–4); (2) Phase 2: Orakel-Kit
      (`analyse/stl_oracle.py`: STL-Parser, bbox, Volumen, Winding,
      Degenerate/Duplikate, Komponenten) mit synthetischen Fixtures
      (Quader, Vase, by-layer) — **offline möglich, kein Drucker nötig**;
      (3) Phase 3: Root Cause in `_stl_export` belegen, minimale Fixes,
      Regression über `rose_215c_pla` + synthetische Fälle;
      (4) Phase 4: Feldabnahme nur mit Nutzer (2 Programme, Reimport,
      Reslice) — Ergebnis `docs/STL-EXPORT-ABNAHME.md`.
      Verboten vor Phase-3-Evidenz: Refactor/Ersatz des Exporters.
- [x] **I2 — Nahtlose Agenten-Übergabe.** `AGENTS.md` (Repo-Root) als
      verbindlicher Einstieg (Aktueller Stand, Regeln, Quellen-Hierarchie,
      Release-Prozess); `analyse/uebergabe-quellen/` mit `.gitignore`
      (Quellen lokal, nur SHA256SUMS getrackt) + Manifest aktualisiert
      (Gesamtbriefing-GPT, my_printer.cfg.txt); `UEBERGABE.md` §6 zeigt auf
      `AGENTS.md`; UEBERGABE-Historie bleibt als datierter Verlauf.
      V1-UPDATE-ZIP gefunden (Nutzer), verifiziert (167 Einträge, kein
      analyse/, interner Versionsstempel R2-2026-11-13.1) — Ablage
      `releases/klipper-e3-r2d2-UPDATE-R2-2026-11-13.1.zip` (6234496e…),
      nicht im Repo.

## G. Feld-Abnahme-Checkliste (Drucker im Umbau — bei Bereitschaft vortragen)

*(User-Direktive 2026-11-18: Punkte merken, erst liefern, wenn der Drucker
wieder bereit ist. Nichts hiervon ohne Go.)*

- [ ] **Release-Feldabnahme:** Layer-Anzeige nach Update (R258 Option B —
      kommentarlose Dateien zählen `rises + big_rises + 1 + bed_returns`;
      kommentierte Dateien behalten die Slicer-Anzahl).
- [ ] **3× Z-Homing + 1× Mesh 5×5 + SCREWS_TILT_CALCULATE** — Vorbedingung
      für E1/E4.
- [ ] **E1/E4:** `printer.cfg`-Vorschläge (`position_min = -2`,
      `G4 P750`, speed 100) NUR nach separatem Go + Test-Fenster.
- [ ] **E3 bestätigen:** LED-Stummschaltung im Sondenfenster am realen Druck.
- [ ] **Textur-Streifen** drucken (BARK / PLANKS / BRICKS / HONEYCOMB /
      27 Vorlagen) und Muster sichtbar prüfen.
- [ ] **Erster echter Cake-Schnitt** (reorient: Schnittfläche auf Bett) +
      Ausschnitt-Range-Test des Ergebnisses.
- [ ] **Live-Watcher / Feature-Erkennung** auf einer echten Datei.
- [ ] **Shutdown-Feldlog** prüfen, falls E1 sich wiederholt (.142g, 12.11.).
- [ ] G/H/C-Sektionen: alle „offline geprüft“-Vermerke am Drucker nachholen.

## F. Erledigt (mit Beleg)

- [x] **R264 — PDF-Pflege V4 (19.11.2026).** Die drei versions-/inhaltstragenden
      PDFs nachgebaut: `MANUAL.pdf` (stempelaktuell R2-2026-11-18.3, Kap. 5.21
      Toolchain drin), `GENERATORS_TOOLS.pdf` (13 Seiten, 15 File-Tools:
      Toolchain-Block neu; alle LCD-Pfade von „Mods" auf den echten
      Anzeigenamen „Tools" berichtigt — 14 Stellen), `CREATIVE_POSSIBILITIES.pdf`
      (11 Seiten, 13 Rezepte: „Die Effektkette — ein Preset, ein Guss" neu,
      V4-Stempel, 9 Pfad-Fixes). TEXTURING/FEATURE_TAGGING/DISPLAYS/CUTSPLIT
      unverändert (keine Versionsstempel, kein Inhaltsdrift). Beleg:
      Builder-Läufe `[ok] … 13 pages/11 generators/15 tools` bzw. `11 pages,
      13 recipes`; TOOLS_INVENTORY-Zeilen aktualisiert.

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

### Fortsetzungsstand: Gesamtprüfung B/C

- [ ] Gesamtbriefing §20–28 einzeln gegen Implementierung und Tests abgleichen,
      einschließlich RE-Recherchen, Slicer-Familien und Performance-Hinweisen.
      Nutzer hat diese Prüfung bereits beauftragt; keine erneute Rückfrage.
      B/C-Status aus dem Gespräch bleibt bis dahin vorläufig.
- [ ] STL: bestehende Regressionstests ausführen, Mesh-Prüfung ergänzen;
      Offline-Prüfer `tools/stl_audit.py` umgesetzt, 5 Mesh-Tests und 3
      E-State-Tests bestanden. Zwei gestapelte Bahnen reproduzieren 2 doppelte
      Flächen / 5 nichtmannigfaltige Kanten. Noch kein Exporter-Fix.
      Vorherige Aussage „keine Regression-Fixtures“ ist zu pauschal:
      `tools/test_stl_extrusion_state.py` enthält synthetische Regressionen.
- [x] Quellen-Verfügbarkeit: sieben vorliegende Originaldokumente inklusive
      printer.cfg ins Repo aufgenommen, Manifestgleichheit geprüft und nach
      Zugangsdaten-Schlüsselwörtern durchsucht (keine Zugangsdaten gefunden).
      Ältere nur im Manifest genannte, fehlende Dateien bleiben als fehlend erkennbar.

MANUAL.md aktualisiert; PDF-Ausbau zurückgestellt. r142 mit installiertem
Wörterbuch: Exit 0, 0 Verdachtsfälle. Keine neue Hardware-Abnahme.

- [x] **I1 Teilbaustein Kontur-Oberfläche:** `tools/contour_mesh.py` +
      `tools/test_contour_mesh.py` (Commit mit Betreff
      `feat: add bounded contour surface foundation with analytic mesh tests`).
      6/6 Tests; Quader, konkaves L, Orientierung, ungültige Konturen,
      Float32-Kollaps. Experimentell, kein Eingriff in aktiven Exporter.
- [ ] **I1 Integration:** wechselnde Layerkonturen und
      Linienbreitenkorrektur; erst danach G-Code-Anbindung. Nicht mit einem
      fertigen STL-Export verwechseln. Belege/Grenzen im STL-Audit.

- [x] **I1 Durchgangslöcher:** explizite, getrennte Lochkonturen im
      experimentellen Prisma-Baustein (Commit-Betreff `feat: preserve through-holes in contour surfaces`).
      Sichtbare Brücken nur zur Deckeltriangulierung, Innenwandnormalen ins
      Loch; Flächenerhaltung geprüft. 11 Konturtests inklusive drei Löchern
      in neun Parameterkombinationen, Euler-Topologie und Fehlereingaben.
      Dazu 5 Mesh- und 3 E-State-Tests bestanden. Aktiver Export unverändert.

- [x] **I1 eingeschränkter Schicht-Loft:** `loft_mesh` verbindet positiv
      gleichförmig skalierte/verschobene Konturen über 2–64 Höhen, inklusive
      Durchgangslöchern, ohne interne Deckflächen. Commit-Betreff
      `feat: loft scaled contour sections without internal caps`.
      16 Konturtests + 5 Mesh- + 3 aktive E-State-Tests bestanden.
      Kein allgemeines Layer-Matching und keine produktive G-Code-Anbindung.

- [x] **I1 normalisierte G-Code-Kandidaten:** `tools/gcode_contours.py`
      liest über `r2_shadow.Shadow`, hält Konturpunkte, Z, Quellenzeilen,
      Tool und kommandiertes Filament fest. 7 Integrationstests bestanden.
      Commit-Betreff `feat: extract provenance-bearing contour candidates from shadow moves`.
      Keine physische Kontur-/Feature-/Lochbehauptung, keine STL-Ausgabe.
- [ ] **I1 Feldintegration:** Rose liefert im strikten Parsermodus 0 Konturen
      und 148529 unbekannte Records. Gründe/Modalzustände belegen; nicht mit
      pauschalen Annahmen freischalten. Linienbreitenkorrektur und Zuordnung
      von Modell/Hilfsgeometrie weiterhin offen.

- [x] **I1 Rose-Parserdiagnose:** optionales, im Bericht ausgewiesenes
      `--klipper-passive` nutzt den bestehenden Shadow-Klipper-Modus.
      Unbekannte Records 148529 → 1 (START_PRINT); 45285 nichtplanare
      Extrusionsbewegungen, weiterhin 0 exakte Konturen. Keine Startzustände
      geraten. Feed-only/identische Positionsbefehle trennen Ketten nicht mehr.
      12 Integrationstests inklusive unveränderter Rose-Datei bestanden.
      Commit-Betreff `fix: diagnose Klipper contour state and preserve feed-only continuity`.
- [ ] **I1 nichtplanare/offene Pfade:** für Rose belegte Strategie entwickeln;
      keine stillschweigende Z-Quantisierung oder Nahtschließung.

- [x] **I1 Bahnevidenz:** begrenzter Streaming-Sammler für vollständige
      planare/nichtplanare Extrusionsketten ohne Punktwolke. Rose: 708 Pfade,
      137975 Segmente, 228 nichtplanar, 336 kleine XY-Endlücken ohne 3D-Schluss.
      5 neue Tests und 36 bestehende bestanden; reale Zahlen regressiv geprüft.
      Commit-Betreff `feat: measure nonplanar extrusion paths without geometry repair`.
- [ ] **I1 Naht-/Spiralrekonstruktion:** explizites Fehlerbudget und Herkunft
      für jede geometrische Annäherung; Brim/Support/Modell getrennt behandeln.

- [x] **I1 begrenzte planare Nahtvorschläge:** `seam_reconstruction.py`,
      CLI `--seam-gap-mm`, nur explizite Schlusskante; vorhandene Punkte
      unverändert. Nichtplanare/ungültige Pfade abgelehnt. 6 neue Tests,
      41 bestehende plus 10 RE-Tests bestanden. Rose bei 0,1 mm: 55
      Vorschläge inklusive Brim, höchstens 32 gespeichert; kein STL.
      Commit-Betreff `feat: propose planar seam closure within explicit distance budgets`.

- [x] **I1 Marker-Provenienz:** `contour_context.py`, dateilokale
      EXCLUDE_OBJECT_START/END-Zuordnung inklusive Quellenzeile. Fehler/
      unbekannte Befehle löschen Zugehörigkeit; Features nicht über Objektgrenzen
      übernehmen. Hilfsgeometrie-Hinweise ausdrücklich ausgeschlossen,
      Außenwandhinweise bleiben unverifiziert. 5 neue Tests + 57 bestehende
      lokal bestanden. Commit-Betreff `feat: retain conservative object and feature provenance for contour proposals`.

- [x] **I1 physischer Konturbaustein:** `physical_contours.py`, konvexe
      konstantbreite Konturen mit expliziter Außen-/Lochrolle. Gehrungslimit
      und Kollapsprüfung; keine stillen Konkavitäts-/Breitenannahmen.
      Stadium-Querschnittsformel getrennt von Geometrie. 7 neue Tests,
      einschließlich Offset→Loch-Prisma→STL→Volumenprüfung, plus 62 bestehende
      bestanden. Commit-Betreff `feat: add explicit bead-width and convex physical contour estimates`.
- [ ] **I1 physische Integration:** reale effektive Extrusion, Schichthöhen,
      variable/konkave Breiten, Objektgeometrie belegen; neue API bleibt
      experimentell und ersetzt keinen aktiven Export.

- [x] **I1 durchgängige Offline-Prismavorschau:** `contour_preview.py`,
      G-Code→Vorschläge→explizite Auswahl/Breite/Z→Offset→Prisma→STL-Prüfer.
      Pflicht-Provenienz .stl.json, keine Überschreibung. Hilfsgeometrie,
      unklare/abweichende Objekte, falsche Ebenen und Tools abgelehnt.
      6 neue Tests, 75 gesamt lokal bestanden. Commit-Betreff
      `feat: connect G-code contour proposals to audited experimental prism previews`.
      Nicht als automatische Modellrekonstruktion oder fertiger Export bezeichnen.

- [x] **I1 konkave topologieerhaltende Offsets:** L-/U-förmige Ringe
      zulässig, solange Gehrungslimit, Eckorientierung und einfache
      Polygonform erhalten bleiben. Zusammenfallende Kerben/Arme, Umkehr- und
      Durchdringungsfälle werden abgelehnt statt repariert. 5 neue Tests
      (analytische Flächen, L-Loch-Mesh, G-Code→Prismavorschau, CLI-lose
      Kompabilität), 80 gesamt lokal bestanden. Commit-Betreff
      `feat: support concave centreline offsets that preserve ring topology`.

- [x] **I1 Mehrfachinseln:** `prism_set_preview` + CLI `--group` für mehrere
      Ringgruppen in einer STL. Getrennte Schalen, paarweise disjunkte XY-
      Boundingboxen, Komponentenzahl = Gruppenzahl. Gruppenintern gleicher
      Objektmarker/Ebene/Tool; gruppenübergreifend verschiedene Objektnamen
      erlaubt und protokolliert. 7 neue Tests, 87 gesamt lokal bestanden.
      Commit-Betreff `feat: preview multiple disjoint prism islands from one report`.

- [x] **I1 Ebenenstapel (identische Outlines):** `stacked_prism_preview`,
      Schichten mit exakt gleichen Offsets über kontiguierliche Bänder zu
      einem Prisma über die Gesamthöhe. Quellzeilen jeder Schicht bleiben im
      Bericht. Abweichende Outlines/Lücken/Überlappungen/nicht steigende
      Ebenen/Toolwechsel abgelehnt. 5 neue Tests, 92 gesamt lokal bestanden.
      Commit-Betreff `feat: stack identical layer outlines into single prisms`.
      Weiter offen: Outline-Übergänge zwischen Schichten (Bool-Operationen),
      CLI-Stapel, reale Breiten-/Höhenherkunft.

- [x] **I1 Ebenen-/Breitenevidenz:** `plane_statistics` pro Objekt aus
      gemessenen Extrusions-Z-Ebenen (Abstände sind Evidenz, keine verifizierte
      Schichthöhe/Erste-Schicht-Versatz); `--assume-layer-height-mm` liefert
      Stadion-Breitenschätzungen mit measured=false und Rollen-Min/Max.
      Rose-Regression: 7 Ebenen je Objekt, Abstände {0,2:5, 22,8:1},
      Außenwandbreite 0,322–0,910 mm unter Annahme 0,2; Vase-Modus bestätigt.
      5 neue Tests, 97 gesamt lokal bestanden. Commit-Betreff
      `feat: measure layer plane spacing and explicit-assumption widths`.

- [x] **I1 Spiralringe (expliziter Vertrag):** `spiral_rings.py`, Ring je
      voller Umdrehung aus N Sehnenproben bei fortlaufenden Höhen; Pitch ist
      Aufruferangabe (eine volle XY-Umdrehung), Ringpunkte mischen Höhen im
      Band. Kollineare/ungültige Ringe, nichtmonotone Höhen, Budgetüberschreitung
      abgelehnt; unvollständige Schlussumdrehung wird verworfen und gezählt.
      6 neue Tests mit synthetischen Helix-Orakeln (binär-exakte Abtastung,
      Radien-/Bandprüfungen), 103 gesamt lokal bestanden. Commit-Betreff
      `feat: sample monotonic spiral walls into per-revolution rings`.
      Weiter offen: Punktretention langer realer Spiralpfade (Rose: längster
      Pfad 602 Punkte übersteigt die 257er-Nahtretention), Breitenanwendung,
      Mesh aus nichtplanaren Ringen.

- [x] **I1 nichtplanare Punktretention + Rose-Ring:** opt-in Retention
      (max 4 längste nichtplanare Pfade, je max 1024 Punkte, Eviction der
      kürzesten, Overflow-Zähler). spiral_rings erlaubt jetzt flache Segmente
      (Höhe darf nie zurückkehren, muss nicht strikt steigen). Rose-Regression:
      4 Pfade 599/599/602/602 Punkte; längster (Zeilen 39269–39869, Z 10,2→10,4,
      XY-Schlusslücke 0,036 mm) liefert mit Pitch 0,2 und 64 Proben einen Ring
      (Band [10,2; 10,396875]); 32 Proben werden als selbstschneidend
      abgelehnt — Untertastung wird nicht repariert. 4 neue Tests, 107 gesamt
      lokal bestanden. Commit-Betreff `feat: retain longest nonplanar paths and sample real rose ring`.
      Weiter offen: Ring-zu-Mesh-Vertrag, Breitenanwendung, Pitch-Verifikation.

- [x] **I1 Ring-zu-Mesh (offene Wandfläche):** `ring_wall.py`, Kontraktnähte
      aufeinanderfolgender Ringe (gleiche Probenzahl, aufsteigende, disjunkte
      Bänder, CCW normalisiert) zu einer offenen Mittellinien-Wand.\      Erwartung: genau 2N offene Randkanten, deren Richtungsdifferenz im
      Prüfer entspricht, sonst 0 Fehler, 1 Komponente. Entartete Dreiecke
      und Regelverletzungen abgelehnt. 4 neue Zylinder-/Vase-Tests,
      111 gesamt lokal bestanden. Commit-Betreff
      `feat: stitch per-revolution rings into open wall surfaces`.
      Weiter offen: Phasenfortsetzung über Pfadgrenzen (Rose: 1 Umdrehung je
      Pfad), Deckel/Breite/Festkörper, Selbstschnittprüfung der Quadrate.

- [x] **I1 Pfadfortsetzung + echte Rose-Wand:** `path_continuation.py`
      (Lagekontinuität mit explizitem Brückenbudget, Höhenmonotonie über
      Fügungen). Rose: 228 exakt fortlaufende Paare, 4 kleine Lücken
      (0,004–0,078 mm), längster Wandlauf 115 Pfade. Fenster 13350–15390
      (5 Pfade: eine 0,0769-mm-Brücke, 3 gemeinsame Punkte) → Pitch 0,2/64
      Proben → 4 Ringe → offene Wand (384 Dreiecke, 128 Randkanten, sauber).
      spiral_rings-Punktbudget 8192 (linear), Abtastung mit
      Deckungs-Sicherung. 3 neue Tests, 114 gesamt lokal bestanden.
      Commit-Betreff `feat: join continuous vase paths into real rose wall windows`.
      Weiter offen: ganze Wandläufe über Budgetfenster, Deckel/Breite,
      Selbstschnittprüfung, Slicer-Reimport.

- [x] **I1 Breite an Spiralringen:** `vertex_normal_offset` in
      `physical_contours.py` (1:1, Ecknormal, dokumentierte Abweichung) und
      `wall_surfaces.py` (offset_wall_rings/wall_surface, Außen-/Innenseite,
      gesamte Spanne oder Ablehnung). Rose-Fenster: bis 0,24 mm alle Ringe
      beidseitig topologyerhaltend; ab 0,3 mm Ablehnungen an Blütenkerben
      (0,4 mm: außen 1/4, innen 0/4). Außenfläche bei 0,24 mm: 384 Dreiecke,
      128 offene Randkanten, keine nichtmannigfaltigen Kanten.
      WICHTIG: Breite bleibt unverifiziert; Stadium-Schätzung 0,32–0,91 mm
      übersteigt die Topologieschwelle — kein Messwert, keine Abnahme.
      5 neue Tests, 119 gesamt lokal bestanden. Commit-Betreff
      `feat: apply explicit bead width to spiral wall rings`.
      Weiter offen: ganze Wandläufe, Deckel/Festkörper, Selbstschnittprüfung.

- [x] **I1 kompletter Rose-Wandlauf:** `wall_run.py` (Streaming-Sampler mit
      gleitendem 4096-Punkte-Puffer, Ring je Pitch-Band, Ablehnungen
      protokolliert, `wall_run_surface` nur ohne Ablehnung). Rose: 115 Pfade
      (114 exakte Fügungen + flacher Abschlussring Z 24,0), 62916 Punkte,
      114 Ringe über Z 1,2–24,0. Bei 96 Proben: vollständige offene Wand mit
      21696 Dreiecken, 192 Randkanten, 0 nichtmannigfaltig, 1 Komponente.
      Bei 64 Proben: 5 abgelehnte Bänder (66,68,78,82,83) — Untertastung
      wird nicht repariert. 5 neue Tests, 124 gesamt lokal bestanden.
      Commit-Betreff `feat: stream the complete rose vase wall into one mesh`.
      Weiter offen: Deckel/Boden, Breite über ganze Wand, Selbstschnitt,
      Pitch-Verifikation, Slicer-Reimport.

- [x] **I1 geschlossene Vase-Oberfläche:** `vase_closure.py` — vertikale
      Projektionsstreifen (Vertex bewegt sich nur in Z, Abweichung ≤ Pitch,
      dokumentiert) plus Ohr-Clipping-Deckel; zusammengebrochene Streifen-
      dreiecke werden gezählt. Zylinder-Orakel: Volumen = Fläche·Höhe exakt
      (Cavalieri). Rose komplett geschlossen: 22266 Dreiecke, 0 offene
      Randkanten, 0 nichtmannigfaltig, 0 Windungsfehler, 1 Komponente,
      Volumen 4810,105 mm³; Rand-Abgleich: geflätteter Ring liegt exakt auf
      der aufgezeichneten Abschlusskontur (max < 1e-9 mm, Flächendifferenz
      2,59 mm²). 4 neue Tests, 128 gesamt lokal bestanden. Commit-Betreff
      `feat: close the complete rose vase surface with documented caps`.
      Weiter offen: Breite/physikalische Außenfläche, Selbstschnittprüfung,
      Slicer-Reimport, zweites Objekt.
- [x] **I2 Selbstschnittprüfung:** `self_intersect.py` — Dreieck-Dreieck-
      Test (konservativ, Berührung zählt) für alle nicht-adjazenten Paare,
      räumlicher Hash, koplanare Fälle per Projektion; Degeneraten werden
      abgelehnt. `close_vase_surface(check_self_intersection=True)` prüft
      die verschickten float32-Dreiecke und wirft bei Durchdringung
      (Stern-Verdreh-Orakel: 8 Paare). Rose: 0 Selbstschnitte, 63194
      Paartests, 134021 adjazent übersprungen, 1,6 s — Volumen 4810,105 mm³
      ist gemessen, nicht angenommen. 15 neue Tests, 143 gesamt lokal
      bestanden. Commit `feat: audit the closed rose surface for self-
      intersection`. Weiter offen: Breite/physikalische Außenfläche,
      Slicer-Reimport, zweites Objekt.
- [x] **I3 Bead-Breite aus G-Code-Evidenz:** `bead_evidence.py` — verein-
      helligter Kollektor (`collect_chained_run`, rose_run delegiert,
      identische 115/62916-Kette verifiziert), Stadium-Breite je Pfad
      (`run_width_evidence`), Volllauf-Audit beidseitig (`wall_width_audit`).
      Rose: Wand uniform 0,6 mm (113 Pfade 0,5998–0,6001), Boden-/Randloop
      0,322/0,321, Material 3607,43 mm³. Audit: 0,6 außen 54/114, innen
      0/114; 0,02 lehnt bereits 3+2 Ringe ab (Ecken nahe 0,001° kollinear)
      → keine uniforme Breite > 0 volllauffähig; alte ≤0,24-Aussage war
      4-Ring-Fenster-Artefakt (Volllauf 86/114 bzw. 69/114). Physische
      Schale bei Evidenzbreite mit Vertex-Normal-Offset NICHT darstellbar.
      11 neue Tests, 154 gesamt lokal bestanden. Commit `feat: measure the
      rose wall bead width from g-code evidence`. Weiter offen: Schalen-
      modell (Miter mit Verschmelzung/Stadium-Sweep), Slicer-Reimport,
      zweites Objekt.
- [x] **I4 Fremd-Datei-Härtetest:** drei ältere Nutzer-Uploads (keine
      Vasen, mit Stützen/Brim) als Fixtures + `test_field_gcode.py`.
      MAN_V3 (Slice Beam 0.3.0): ;TYPE:-Rollen, 0 Unknowns mit
      assume_klipper_defaults, 5333/9190 Helper-Pfade (Support, Skirt/Brim,
      Ironing, Custom). Pumpkin (Kiri:Moto 4.3.2): kein G90 in der Datei,
      G28 W/G80-Startblock, ;feature-Grammatik, 192 nichtplanare Pfade
      (Deckenrampe), 415 Helper/6664 Modell. vwbus (Kiri:Moto 4.3.1):
      31144/39243 Pfade Support (~79 %), 8099 Modell. Fixes: G28-Semantik
      (nur Achsen invalidieren, Modi erhalten; Record-Typ ‚home‘),
      FEATURE-Regex + Kiri `; feature`, HELPER_HINTS + skirt/brim, ironing,
      custom. 10 neue Tests, 164 gesamt lokal bestanden. Commit `feat:
      ingest three foreign field files with full feature tagging`. Weiter
      offen: Modell-STL ohne Stützen/Brim aus diesen Dateien, Kiri-Objekt-
      marker, Schalenmodell, Slicer-Reimport.
- [x] **I5 Modell-STL aus Fremd-Dateien:** *(Fenster-Export erledigt, siehe unten; Fertigstellung zurückgestellt → J1)* `model_export.py` — Wand-Rollen-
      Filter (Helper/Infill/unmarkiert nie Kontur), Nahtbudget, Inseln per
      Enthaltensein, Run-Merging, Prismen über disjunkte Z-Bänder (Volumen-
      summe exakt). Orakel exakt (112/88 mm³, Helper-Ausschluss, Vertex-
      budget). Fremd-Dateien [0,4]: MAN_V3 18 Schalen/64,987 mm³, vwbus
      18/348,308, Pumpkin 21/334,337; alle Selbstschnitte nur auf Über-
      gangsebenen (0 Durchdringungen); audit == Konstruktion. Beweis-STLs
      in analyse/stl-exports/. 8 neue Tests, 172 gesamt. Commit `feat:
      export model-only shells from foreign g-code files`. Weiter offen:
      volle Spanne + Loft, Löcher-Inferenz, Kiri-Objektmarker, Breiten-
      schalenmodell, Slicer-Reimport.

## J. Vorgemerkte Aufgaben und Nutzer-Entscheidungen (Sitzung nach `bdb8b03`)

- [ ] **J1 — STL-§24-Fertigstellung ZURÜCKGESTELLT (Nutzer-Entscheidung).**
      Feldbefund des Nutzers an den Fenster-Exporten (z∈[0,4] mm): vwbus
      zeigt nur das Heckstück (Fahrzeug steht ~30–45° geneigt mit der Heck-
      stoßstange auf dem Bett), MAN nur den Anfang der Frontstoßstange
      (Stoßstange auf der Druckplatte) — beides ist die korrekte Fenster-
      Erklärung, kein Exportfehler, aber kein brauchbares Gesamtergebnis.
      Pumpkin wird vom Nutzer als unbefriedigend beschrieben: zu wenige,
      zu hohe Ringe, „platt gedrückt“, Brim-/Überhang-Verdacht, große
      flache 90°-Fläche in Brim-Größe. Diagnose-Kandidaten bei Wieder-
      aufnahme (ungeprüft): (a) interne Übergangskappen — 21 Schalen über
      18 Level mit unterschiedlichen Outlines erzeugen viele große hori-
      zontale Kapp-Ebenen (dokumentierte Grenze), (b) 50 Wand-Loops
      > 256 Vertices wurden gezählt und NICHT exportiert → feine Umrisse
      fehlen, (c) reine Fenster-Ansicht (4 mm eines hohen Körpers),
      (d) Brim-Verdacht ist unwahrscheinlich (skirt/brim-Hints sind
      gefiltert und 15 Brim-Pfade klassifiziert) — gegenprüfen.
      NEUE Nutzer-Richtung für die Rekonstruktion: statt Layer-/Prismen-
      Extraktion über **weniger Punkte eine 3D-Punktfolke** erzeugen und
      damit eine **Haut spannen** (Surface Reconstruction), um auch
      organische Formen zu erhalten. Als verbindliche Forschungsrichtung
      für §24 notiert. Bleibt zusätzlich offen: volle z-Spanne (Dreiecks-
      budget), Loft zwischen Outlines, Loch-Inferenz, Kiri-`; start object
      id:`-Marker, Breiten-Schalenmodell, Slicer-Reimport; aktiver
      Exporter (Box-Soup) unverändert defekt.
- [~] **J2 — GIESAFORMEN-GENERATOR — FREIGEGEGEBEN 19.11.2026 (vier
      Nutzer-Entscheidungen im Arena-Dialog), Bau läuft (R270+).**
      **Verbindliche Spezifikation (Lastenheft):**
      (1) **Modellquelle gestaffelt:** Häppchen 1 = Form um eine fertige
      G-Code-Datei (SD-Browser-Auswahl, Kavität aus per-Z-Band-Silhouetten,
      gefüllt + Toleranz-Aufweitung); Häppchen 2 = parametrische Grundkörper
      (Medaillon, Plaque, Bar) mit Relief-Einbettungsplatz.
      (2) **Teilung VOLL ab Tag 1 (Nutzer-Entscheidung gegen die Staffel-
      Empfehlung):** 2-teilig (Trennebene Z-Mid/Auto-Äquator/eine Z-Versatz,
      Pitch-Roll-Pläne mit der 3/4-Stufe), 3-teilig (Ebene + 1 Sektor-
      schnitt), 4-teilig (2 Sektorenschnitte). Interne Beweisstufen mit
      eigener Batterie pro Stufe, ein Release-Zyklus.
      (3) **Ausgabe-Modus am LCD wählbar:** Both / Top / Bottom / je Sektor /
      Positiv-Master (Silikon-Abform-Referenz).
      (4) **Heimat beides:** LCD-Menüzweig UND toolchain-Schritt (wie
      Stencil R267).
      **Parameter (Defaults aus der Recherche-Notiz):** Wand 3–15 mm (5) ·
      Toleranzspalt 0,05–0,30 mm (0,15) · Einguss 5–15 mm (8) + Trichter
      None/Konisch · Entlüftung 1,5–4 mm (2,5) · Passung Stifte Ø 3–8 mm (5)
      · Formschräge 0–3° (0) · Oberfläche Standard/Fein/Fuzzy (Textur-
      Anbindung später).
      **Architektur (fix):** DIREKTE G-Code-Erzeugung (Labels/Plotter/
      StringArt-Muster), KEIN trimesh-Boolean (Pi Zero 2 W) · Job über
      Makro → SAVE_VARIABLE → Watcher → `_spawn_job` · RAM-Floor 60 ·
      Web-UI-Spiegelung automatisch · Versionierung `Vnn_Form…_…`.
      **STAND R270 (19.11., Häppchen 1 Stage A FERTIG):** Engine
      `make_mold()` in r2_postproc.py — Source-Scan (G90/G91/M82/M83/
      G92, ;TYPE:-Filter mit der R253-Regel „keine TYPE-Zeilen = nichts
      ausschließen", Arkten grob gesampelt), gefüllte Silhouetten pro
      Z-Fenster, Äquator-Split (AUTO/MID/OFF), BEIDE Hälften Parting-
      Fläche-nach-oben (klassischer flat-face-up-Trick: beide Passflächen
      werden Top-Surfaces, keine Kavitätswand druckt über Leere; das
      Oberteil ist Y-gespiegelt gedruckt, der Nutzer wendet es beim
      Zusammenbau wie einen Deckel), Boden/Deckel = Wandstärke, Einguss-
      kanal + konischer Trichter + adaptive Entlüftungen (nur wo sie
      PHYSISCH passen: ≥2mm Steg zwischen Einguss und Lüfter, sonst
      ehrliche Notiz), Dübellöcher an identischen Bett-Koordinaten
      (Stencil-Registratur-Muster, auf Zellzentren gesnappt, D3-Default
      = Filamentstab, Dübel-vs-Wand-Validierung), Entlüftungsrillen auf
      BEIDEN Trennflächen, Formschräge als echte Zell-Erosion (der
      Radius-Trick wurde von der Silhouetten-Füllung geschluckt — Batterie
      bewies 3904==3904 Zellen, jetzt messbar weniger), Master (Positiv)
      mit. All-or-nothing: jede Verweigerung (Hintersneidung mit Layer-
      und Zellzahl, Bett, Draft schließt die Kavität, Dübel passt nicht)
      hinterlässt KEIN File. Batterie `r270_mold_check.py` 33/0 (dynamisch:
      Layer-Mathematik analytisch, Geometrie aus dem G-Code gemessen,
      Draft/Gap über Kavitäts-Zellzähler). Gates: macro_render 2133/2133
      (R162-Pin ehrlich auf 3 Vollumfang-Hatch-Aufrufe erweitert — der
      Pin fing vorher einen ECHTEN Nullhöhen-Bug im Mold-Fill), megatest
      224/0, systemtest 214/0, r81 23/23, r142 142/0, audit 82/0,
      toolchain OK.
      **STAND R270 STAGE B (19.11., VERDRAHTET):** LCD-Generator-Menü
      `__gen __mold` (Wand/Spalt/Einguss+Trichter/Entlüftung/Dübel/
      Formschräge + Split & part [AUTO/MID/OFF+Z, BOTH/TOP/BOTTOM,
      Master-Toggle] + 2-Druck-Build), Makros MOLD_INFO/MOLD_CREATE
      (Datei aus SD-Browser-Auswahl wie Cake, Nonce + _GEN_ARM/_GEN_GO),
      Watcher mold_nonce-Block (ValueError-Verweigerungen erreichen das
      LCD MIT Grund), GEN_SUBDIRS 'molds'->Molds + 'stencil'->Stencil
      nachgetragen (V5-Latenzbug: der R267-Watcher rief einen nie
      registrierten Key - jede Schablonen-Anfrage waere am Geraet mit
      KeyError gestorben; Batterien umgehen den Watcher, deshalb sahen
      es alle Gates gruen), Toolchain: TOOL_REGISTRY['mold'] (Ketten
      einseitig: part-Enum nur TOP/BOTTOM, BOTH lehnt Validierung UND
      Adapter ab) + Adapter + 3 neue Ketten-Tests. Daneben 2 ehrliche
      Altfund-Fixes: LCD-Anzeigebug Cake 'and 0 or'-Muster (UPPER zeigte
      BOTH an - 'True and 0' ist falsy, '0 or 2' nimmt 2; durch
      Konditionalausdruck ersetzt) und Fixture-E in test_toolchain_steps
      (konstantes E0.20 nach G90-ueber-M83 extrudiert unter Klipper nur
      den ersten Zug - E jetzt kumulativ wie bei echten Slicern).
      Pins ehrlich fortgeschrieben: NONCE_KEYS 49, Guards 9, _gensub-
      Call-Sites 23, CONFIRM-Zeilen 59, R135-Pfadliste +17, R162-Pin 3.
      Gates: r270 33/0, macro_render 2133/2133, megatest 224/0,
      systemtest 214/0, r81 23/23, r142 142/0, audit 82/0,
      test_toolchain 49 OK, test_toolchain_steps 25 OK, r165/r166 clean.
      NOCH OFFEN: 3/4-Teil-Sektorstufe + Oberflaechen-Param, dann
      Haeppchen 2 (parametrische Grundkoerper).
      **Ehrlichkeitsregeln:** Hinterschneidungs-Check pro Hälfte (Kavität
      darf zur Öffnung nicht schrumpfen — Guss löst sich nicht, Druck
      bridgt), Formschräge als Raster-Radius-Approximation (dokumentiert),
      D6: Preview nur aus echtem Code. Evidenz: `r270_mold_check` +
      Folgestufen-Batterien mit DYNAMISCHEN Pins (V5-Lektion).
      **Original-Begründung (Historie):**
      Nutzer-Ergänzung (Sitzung nach `fecf500`): nicht nur zweiteilige
      Hälften — je nach Modellkomplexität auch **Dreitelung oder Vierteilung**;
      **Negativform** ausdrücklich ebenfalls gewünscht. Recherche-Datei des
      Nutzers ingestiert: `analyse/uebergabe-quellen/Giessformen generieren.md`
      (SHA256 ff780b3e…, AI-Notiz — ungeprüft). Kernpunkte daraus:
      Parameterstruktur (Wandstärke 3–15 mm, Trennebene Z-Mid/Auto-Bounding/
      Pitch-Roll, Toleranzspalt, Einguss 5–15 mm + Trichter, Entlüftung
      1,5–4 mm, Passung Stifte/Nut&Feder/Flansch, Formschräge 0–3°, Oberfläche,
      Ausgabe Both/Top/Bottom), trimesh-Prototyp, Empfehlung zur DIREKTEN
      G-Code-Erzeugung ohne Slicer-CLI (wie Labels/Plotter/StringArt).
      Kritische Bewertung (Agent, vor jeder Umsetzung prüfen): Das
      `RUN_SHELL_COMMAND`-Beispiel der Notiz passt NICHT zur echten Job-
      Architektur (echter Weg: Makro → SAVE_VARIABLE → Watcher →
      `_spawn_job` in die bestehende Queue); trimesh + Boolean-Backends sind
      auf dem Pi Zero 2 W ein RAM-/Zeitproblem (die Notiz warnt selbst);
      Multi-Part (3/4) braucht einen allgemeinen Ebenen-/Sektor-Schnitt,
      nicht nur Z-Mid. natürliche Heimat: ein Werkzeug in der Toolchain
      (Abschnitt K). Details/Go beim Nutzer.
- [ ] **J3 — UI-/Display-Gesamtkonzept klären (Gesamtbriefing §10).**
      Ist-Stand (gebaut, zwei Feldrunden überlebt): LCD-Kern + Web-LCD-
      Brücke R196–R217 — `tools/menu_json_export.py` → `web/r2_menu.py`
      (Moonraker-Extension, Endpoints tree/status/live/pistats) →
      `web/index.html` (LCD-artige Navigation, eigener Jinja-Evaluator);
      Installation über `web/install_web.sh` als separater nginx-Port
      (Mainsail-Konfiguration unberührt), Origin/CSRF-Fix R206.
      MCU-/Host-Schonung aus der Performance-Recherche ist eingebaut:
      Live-Poll fragt nur die ~12 referenzierten Objekte ab statt ~300
      Makros (R204), pistats liest /proc statt klippy zu belasten (R216).
      iframe-in-Mainsail — Antwort präzisiert (Sitzung nach `fecf500`):
      ein Panel-iframe gibt es nicht, ABER Mainsail unterstützt offiziell
      **eigene Sidebar-Menüpunkte via `.theme/navi.json`** (Felder
      title/href/icon/target/position) — verifiziert gegen den Mainsail-
      Quelltext `src/components/mixins/navigation.ts` (mainsail-crew/
      mainsail); Quelle: Nutzer-Recherche „KI in Klipper integrieren.md"
      (Randnotiz „GEHT DAS AUCH MIT UNSERER WEBUI????") + eigene Verifikation.
      Die Web-LCD lässt sich damit als eigener Menüpunkt in Mainsail
      eintragen. Offene Entscheidung: (a) eigener Port wie heute,
      (b) Pfad (`/r2lcd/`) im Mainsail-vhost, (c) navi.json-Menüpunkt —
      kombinierbar. Wartet auf Nutzer-Entscheidung.
- [ ] **J4 — Audio-Feedback-Konzept (Gesamtbriefing §11; Nutzerideen waren
      bisher in KEINER Aufgabenliste vermerkt — jetzt nachgetragen).**
      Ist-Stand: `M300`-Makro mit Guard (`'pwm_cycle_time beeper' in
      printer`), 19 Tunes (`_SOUND_LIB`), LED/M117/RESPOND-Fallbacks,
      R95-Regel (keine Beeps während des Drucks), `TOGGLE_SOUNDS`.
      Nutzerideen (Sitzung nach bdb8b03): (a) Soundausgabe über die
      3,5-mm-Klinke eines Raspberry Pi 3B+, (b) eigenes Piezo-Element an
      Pi-GPIO-Pins — beides umgeht die Drucker-MCU komplett (kein
      M300/SET_PIN-Sturm auf die MCU, kein Beitrag zu „Timer too close“;
      die Performance-Recherche dokumentiert LED-/Sound-Traffic als
      historische MCU-Last, und das Shutdown-Register zeigt die Ursache
      in Host-Schüben). Grenzen: Der eigene Drucker läuft auf Pi Zero 2 W —
      der hat KEINE Klinke und kein Analog-Audio; Pi-Analog-Audio ist
      modellabhängig (3B+ ja, Zero 2 W nein). GPIO-Piezo braucht einen
      Treiber (Lautsprecher nie direkt an GPIO — Briefing §11).
      Optionsmenü laut Briefing §11: Board-Piezo (heute) / externer
      Buzzer / Pi-GPIO+Treiber / Pi-Analog-/HDMI-Audio / WebAudio im
      Browser / stiller Betrieb. Nichts entschieden, nichts umgesetzt.
- [ ] **J5 — Verstreute vorgemerkte Ideen einsammeln (Inventur-Befund:
      standen nur in Fachdokumenten, nicht in dieser Liste).**
      - `docs/frame_design.md`: Dreieck- + Stern-Rahmenformen sowie
        Linie/Welle/Diamant/Honigwabe als Rahmen-Oberflächenstrukturen —
        ausdrücklich „later backlog (user decision, NOT dropped)“.
      - `docs/STRINGART_DESIGN.md`: zweifarbige Stringart (Bänder 1–3
        Farbe A, 4–6 Farbe B) — zurückgestellt.
      - `docs/PORTABILITY_SOUND_DISPLAY.md` §2.4 + `WEBUI_MOONRAKER.md`:
        Browser-Sound-Spiegel (WebAudio mit identischer Tune-Tabelle) —
        Konzept, ungebaut (Teil von J4).
- [ ] **J6 — KI-3D-Generierung + Sprachsteuerung (NEU, große Nutzeridee —
      ausdrücklich für SPÄTER vorgemerkt, nicht verloren geben!).**
      Vision des Nutzers: mit dem Drucker FREI sprechen (Spracheingabe,
      im besten Fall Sprach-Feedback und Rückfragen wie „wie möchtest du
      das gerne / soll ich das noch aufteilen"); die KI erstellt oder
      wandelt 3D-Modelle (auch aus hochgeladenen Fotos), bereitet sie vor
      und macht sie zu G-Code, um sie direkt zu drucken. Nutzer-Anweisung:
      zwischendurch immer mal wieder Ideen/Informationen dazu einstreuen,
      damit die Idee auf dem Schirm bleibt. Recherche-Datei ingestiert:
      `analyse/uebergabe-quellen/KI in Klipper integrieren.md` (SHA256
      90907f56…, AI-Notiz — ungeprüft). Kernpunkte daraus: Hugging-Face-
      Spaces-API statt eigener GPU (Hunyuan3D-2/Trellis/TripoSR; Pipeline
      Text→Bild (Flux/SD) → Bild→3D), Sprache über Browser-Web-Speech
      (zuverlässig nur localhost/HTTPS) oder Whisper-Space, kleiner
      Flask-Dienst + systemd auf dem Pi, Ausgabe in den gcodes-Ordner,
      ZeroGPU-Wartezeiten 30–90 s, KI-Modelle haben oft keine flache
      Unterseite (Nachbearbeitung nötig), Mainsail-Menüpunkt via
      `.theme/navi.json`. Erste Agent-Ideen (zu prüfen, nicht Wahrheit):
      (a) KI-Brücke architektonisch als weiterer „Generator" im Toolchain-/
      Queue-Verbund (Abschnitt K) — gleiche Busy-Gates, gleiche Ausgabe-
      modi; (b) JEDES KI-Modell durchläuft vor Slicing/Druck unsere
      Prüfer (stl_audit: Topologie/Maße; Bettcheck) — die Validierungs-
      Infrastruktur existiert schon; (c) physischer Druckstart bleibt
      beim Nutzer (Gesamtbriefing §31); (d) Slicing-Engpass auf dem
      Pi Zero 2 W: Optionen externer Slicing-Dienst/zweiter Rechner/
      leichter Host-Slicer — offen; (e) TTS-Antworten können über den
      J4-Audio-Weg laufen (Pi-Klinke/GPIO-Piezo statt MCU-Beeps — Synergie);
      (f) Sprach-UI in die Web-LCD integrieren (Browser macht STT/TTS,
      ein Funktionskern bleibt). Kein Baubeginn vor ausdrücklichem Go.
- [ ] **J7 — Maschinenmodell-Kompatibilität auditieren (Gesamtbriefing §12).**
      Was ein FREMDER Drucker braucht, damit das System dort läuft: Bett/
      Grenzen, Düse, Probe, LEDs, Display-Typ, Audio-Weg, Host-Modell
      (Pi Zero 2 W vs. 3B+ vs. …). Anknüpfung: `COMPATIBILITY.md`,
      STARTBRIEFING-ABGLEICH Reihe 12 (Status P — „Konfigurations-/
      Geräteabdeckung nicht bewiesen"), Generator-Matrix r217 (Bett/Düse
      parametrisch, 1423 Checks). Offline machbar als Audit + Tests
      (synthetische Fremddrucker-Konfigurationen gegen Generatoren/
      Maschinenmodell). Nächster Kandidat nach K2 bzw. nach Nutzerpriorität.

- [~] **J8 — TEXTUREN-RUNDE II (Nutzer-Wunsch 19.11.2026, mit Lastenheft).**
      Nutzerbewertung: die zuletzt ergänzten Texturen „sehen wirklich
      schon sehr gut aus“ — GENAU in die Richtung, aber mehr Auswahl,
      mehr Variation. Verbindliche Regeln (alle aus der Nutzernachricht):
      (a) **IMMER passgenaue nahtlose endlos Texturen** (wie vorhanden);
      (b) **Name passt wirklich zum Ergebnis**; (c) **am 3D-Druck sichtbar**
      — Muster, die auf der Fläche kaum Unterschied zeigen oder bloß
      glatte Oberflächen ergeben würden, RAUS oder ersetzen
      (Kandidaten prüfen: nah beieinander liegende Rausch-Familien);
      (d) natürlich/organisch ODER akkurat/technisch, je nachdem was
      die Textur verlangt; (e) gleiche Sorgfalt wie bei der letzten Runde
      (R238: codebasiert, Matrix-Vorschau aus den echten Pattern-Funktionen,
      Kennzahlentest auf Unterscheidbarkeit, Presets 1:1 gekoppelt wie G3).
      **STAND R265 Häppchen 1 (19.11., 7 Muster FERTIG):** STONEWALL
      (8 Bettreihen, normierte Blockbreiten, Fensterung an Fugen),
      RUBBLE (gewrapptes Voronoi mit Mörtelbett), TILES (Fliese+Chamfer+
      Fuge, Ton nur auf Fliese), PARQUET (Chevron mit Spalten-Flip),
      LAMINATE (V-Fase+Längskörnung), HILBERT (NEU: ECHTE order-3-Kurve
      per Distanzfeld, ersetzt die Zickzack-Bänder), MAZE (Spannbaum-
      Irrgarten, alle Gänge verbunden, Phantom-Wand-Bug beim Grenz-Falten
      behoben). 33 Muster gesamt, je eine Vorlage (variable_texture_lib
      33 Looks). Verifiziert: r238_field_check 39/39 (neue R265-Sektion:
      Relief/Naht aller 7, Distinctness vs. 10 Klassiker, Wand-/Korridor-
      Konnektivität per Flood-Fill, STONEWALL-Bettlinien, TILES-Flächen-
      anteil, PARQUET-Flip 12/12, LAMINATE-Anisotropie, RUBBLE-Steinzahl),
      macro_render_test 2112/2112, megatest 196/0, r165 clean, r199 clean;
      textur-matrix-ist.png (32 prozedurale) + textur-matrix-soll.png
      (17 kuratierte) neu, TEXTURING.pdf 42 Seiten/33 Muster, MANUAL.md/
      MANUAL.pdf-Katalog auf 33.
      **R265.2 (Nutzer-Review 19.11., umgesetzt):** Bretter/Laminat/
      Parkett wirkten „wie quadratische Fliesen" — Formtreue-Fix:
      _build_patterns kennt jetzt **ar** (mm-Verhältnis t-Periode/
      s-Periode, aus apply_texture gereicht; Preview-Renderer
      übergeben ihr pixel-äquivalentes ar), LAMINATE = schmale
      Dielen (halbe Periodenbreite, ke=2k) über M ganze Perioden
      Länge (Zielaspekt ~1:6, M Teiler von n), PARQUET = echte
      45°-Fischgrät-Mathematik (P Stäbe/Höhe und Q Diagonal-Versatz
      ganzzahlig aus ar hergeleitet; Stäbe ~1:5, Winkel 30–75°),
      TILES bleibt bewusst quadratisch (Reihenzahl folgt ar).
      Fugen von der Körnung freigehalten (die TILES-Lektion), Preset
      Laminat auf scale 14/zsize 18. Checks: r238 **40/40** (neu:
      PARQUET Flip+Winkel+L/B per Fugen-Tracking, LAMINATE-länglich
      vs TILES-quadratisch per Fugenabstandsmessung), macro_render
      2112/2112, megatest 196/0, r165 + r199 clean.
      **OFFEN — Roadmap nach Nutzer-Wunschliste 19.11. (2. Review):**
      - **Häppchen 2 (technisch/modern):** Perforationsblech (rund +
        quadratisch versetzt — Dellen, keine echten Löcher!),
        Carbon/Twill-Gewebe, Pin-/Kugel-Matrix (halbkugelige Noppen,
        gerade + versetzt), Hexagon-/Oktagon-Zellmuster (variabler
        Zelldurchmesser), Maschendraht (Rauten-Drahtgitter),
        Netzgewebe (Fadengitter mit Knoten).
      - **Häppchen 3 (organisch/natürlich):** Holz QUER (Jahresringe)
        + Holzarten-Varianten (Eiche grob, Buche fein, astig),
        Baumrinden-Varianten (u.a. ALTER Baumstamm, rausgefressene
        Rinde, tiefe Rillen → Deep Relief, s. u.), Leder (Narben +
        gepolsterte Steppung), Orangenhaut (bewusst fein),
        Trockenrisse/Schlammplatten, grobe Knitterfalten.
      - **Häppchen 4 (Deko/Haptik/Kitsch):** Sterne, Herzen,
        Ringe/Bubbles (viele kleine Ringe AUF der Fläche, nicht um
        sie), Golfball-Dimples, Basketball (Noppen + Kanäle),
        Raufasertapete, Dachziegel (überlappend, mit Falz),
        Häkelstruktur (Strick existiert als KNIT).
      - **QUERSCHNITT DEEP RELIEF (vor Häppchen 3 bauen, Nutzer-
        Frage 19.11.):** starke Geometrie-Verformung (2–4 mm statt
        max 1 mm) für „echter alter Baumstamm". Dafür: (a) **E-
        Mitberechnung** — aktuell bleibt E je Move unverändert (nur
        X/Y der Außenwand wandern; Gesamtextrusion exakt, lokale
        Liniendichte weicht um den Pfadverlängerungsfaktor ab; bei
        sanften Texturen <5 % unsichtbar, bei tiefen Rillen relevant)
        → E_neu = E_alt · L_neu/L_alt pro Segment mit Summen-Erhalt;
        (b) **Subdivision** steiler Gradienten (Struktur auflösen,
        bevor die Düse sie glattbügelt); (c) **Steilheits-Cap**
        gegen Selbstschnitt/Löcher (Δrad ≤ Faktor × Segmentlänge);
        (d) Inner-Wall-Following + Flip-Realign greifen bereits
        (R224), für Deep-Relief erneut verifizieren.
      Vor jedem Häppchen: Nutzer-Preview/Zusage (bewährte Regel).
      **STAND R265.3 Häppchen 2 (19.11., 7 technische Muster FERTIG,
      Nutzer-Freigabe „mach weiter wie am sinnvollsten"):**
      PERFORATION (runde Dellen, versetztes Raster — bewusst keine
      Durchbrüche, Wand bleibt dicht), VENT (quadratische Aussparungen
      versetzt — Lüftungsgitter), CARBON (2/2-Köper mit diagonalem
      Glanzwechsel, Zell-/Bandperioden ×4-sicher), PINDOTS (echte
      Halbkugelkappen, Kappenprofil (1-d²)^0.62), OCTAGONS (4.3.8.4-
      Kachelung mit geseedeter Größenvariation), CHAINLINK (zwei 45°-
      Drahtfamilien, Über/Unter-Verwebung per Rauten-Parität),
      NETGRID (Fäden + Knoten + tiefe Maschen). 40 Muster gesamt,
      40 Vorlagen (bijektiv). Wrap-Sicherheit: Stagger-/Webe-Paritäten
      brauchen GERADE Periodenzahlen (rows += rows&1 etc.) — CARBON/
      NETGRID haben gewollte Zellstufen, ihr Nahtversprechen ist
      „Sprung an der Naht ≤ Sprung im Feld" (R175-Regel, so gemessen).
      Verifiziert: r238 48/48 (R265.3-Sektion: Relief+Naht fair,
      Distinctness 14 neue vs. 10 Klassiker, PERFORATION rund+versetzt
      per Richtungs-Sonden, VENT quadratisch per Sehnenmessung √2,
      CARBON Bandflip+Periodenschluss, PINDOTS Kappenprofil,
      OCTAGONS Füllfaktor ~0.53, CHAINLINK längs>quer, NETGRID
      Knoten hoch/Maschen tief), macro_render 2112/2112, megatest
      203/0, r165 + r199 clean; Matrix-Previews (39 prozedurale /
      24 kuratierte) + Nutzer-Preview + TEXTURING.pdf (49 Seiten,
      40 Muster) + MANUAL-Katalog neu.
      **STAND R266 DEEP RELIEF (19.11., IMPLEMENTIERT — Nutzer-Preview
      vorgelegt):** Tiefe jetzt 0.05–4.0 mm (BUMPS; >1.0 = Deep-Modus,
      toolchain-Range mitgezogen). (a) **E-Mitberechnung** umgesetzt:
      je Chord E_neu = E_alt·L_neu/L_alt auf relativen-E-Abschnitten
      (M83; Schreibposition wird getrackt inkl. Travels + Bett-Clamp),
      Steilheits-Clamp 0.45–1.8×, Summen-Erhalt per Restkorrektur am
      letzten Chord — gemessen am Uniform-Zylinder: rel. Fehler 4.6e-05
      (pure 5-Dezimalen-Rundung), 0 Clamp-Verletzungen; rose-Fixture:
      Quantil-Ratios 0.84–1.00. Absolut-E bleibt slicer-echt (Header
      sagt es). (b) **Subdivision** nach Steilheit: bis ~0.4 mm Höhen-
      schritt/Chord (cap 256 Teile). (c) **Steilheits-Cap** = der
      0.45–1.8×-E-Clamp (gegen Über-/Unterextrusion an Klippen);
      Wandkontinuität per Querschnitt gezeigt, Inner-Follow + Flip
      (R224) erneut verifiziert (arc_fallback 0, inner_shifted > 0).
      (d) Zwei FELDBUGS mitgefunden+gefixt: X-only-Purge-Zeilen
      („G1 X60 E9" ohne Y) ließen den Stats-Präpass crashen (vwbus-
      Fixture, TypeError ay+=None — Betrifft jede Orca/Purge-Datei!)
      und „M83 ; use relative…" (Kommentar) schaltete den E-Modus-
      Tracker nie um (rose-Fixture — betraf auch R95-Arc-Verteilung).
      Regression: Tiefe ≤1.0 mm byte-identik zum alten Motor (3
      Fixtures). Gates: macro_render **2120/2120** (+8 R266-Tests:
      Range, E-ride exakt, M83-Kommentar, Abs-E-Teilsequenz+Max,
      Purge-Überleben, Regressionswächter, 4.5mm-Refusal), megatest
      **205/0** (+2 Deep-Runs), r238 48/48, r165 clean, r199 ok.
      MANUAL 5.9 (Deep-Relief-Absatz, Depth-Range, E-Versprechen
      präzisiert, Pattern-Zeile 39+MAP/5 Seiten — war widersprüchlich),
      TEXTURING.pdf Tiefe 0.05–4. Preview: analyse/
      r266_deep_relief_preview.png (4 Panels feste mm-Skala,
      Querschnitt, E-Dichte aus echtem G-Code).
      **OFFEN: nur noch Merge-Go für PR #20 (V5 `R2-2026-11-19.1`) +
      finales ZIP aus `origin/main` + Feldabnahme. Release-Vorbereitung
      IST FERTIG (19.11.): Stempel V5 überall, r81 Stamp-Re-Freeze
      (A/B), MANUAL/TESTANLEITUNG (Kap. 33)/INSTALL/README/AGENTS/
      TOOLS_INVENTORY gepflegt, Release-Bericht
      `docs/RELEASE_R2-2026-11-19.1_REPORT.md`, V4-Engine als
      Rollback-Anchor. DREI echte Funde der kompletten Serien-Batterie:
      (a) R268 RELEASE-BLOCKER — der Update-Odometer (Git- UND ZIP-Tor)
      war datenblind: V5 (…-19.1) galt als älter als V4 (…-18.3), Update
      wäre verweigert worden; beide Tore vergleichen jetzt Datum →
      Zähler → Suffix. (b) Sieben Feldpin-Batterien (r215/r226/r234/
      r237/r240/r242/r244) waren seit V4 unsichtbar rot (verrottete
      .142-Pins/Zähler, Mock ohne _SDM, PREV_VER hartcodiert) — alle
      grün, Pins jetzt DYNAMISCH. (c) stencil_nonce + doctor_nonce nie
      geprimet/gefroren (Replay-Klasse .108), LCD-Tiefenzeile der Textur
      hing bei 1 mm (Deep Relief am Gerät unerreichbar). KOMPLETT grün:
      macro_render 2133, megatest 224/0, review_checks, r81 23/23, r91,
      audit 82/0, r110 10/10, systemtest 214/0, r142 142/0, r143 68/0,
      r197 472/0, r212 20/0, r215 20/0, r226 14/0, r228 13/0, r234 38/0,
      r237 14/0, r240 29/0, r242 20/0, r244 26/0, r238 67/0, r267 34/0,
      r165/r265 clean, r168 19/0, r218 26/26, toolchain 49+22, gcode_re
      10/10. J9 (R267) FERTIG.**
      **STAND R266.3 Häppchen 4 (19.11., 6 Deko-/Haptikmuster FERTIG,
      55 Bibliotheksmuster — Nutzer-Auswahl „sechs ohne Sterne/Ringe"):
      HEARTS (implizites Herz (x²+y²−1)³−x²y³, Stagger-Raster,
      Inhalt fern der Zeilengrenze), GOLF (dichte Halbkugel-Dimples,
      versetzt, ohne Saum, r=0.49 — Stagger-Wrap-Grenze), BASKETBALL
      (schlängelnde Kanäle + Noppengrus, Wobble nur ganzzahlig),
      RAUFASER (flache Fläche + spärliche Faser-Chips in 2 Skalen,
      15 % Chip-Anteil, KEINE tiefen Werte), ROOFTILES (Lagerfugen-
      Schattental + durchgehender Seitenfalz mit Wulst — KEIN Versatz,
      der Unterschied zu Ziegelmauer), CROCHET (Knoten + Arme + TIEFE
      Maschenaugen, 1 Auge/Stitchzelle). Registrierung komplett:
      _TX_PATTERN 55/55/55, LCD 7 Seiten (dynamischer Cap trägt das),
      toolchain kongruent, 6 neue Looks (Bibliothek 55, bijektiv —
      dabei alten Zählfehler im MANUAL gefunden: „53 Looks" war falsch,
      korrekt war 49, jetzt 55). Evidenz: r238 67/67 GRÜN (8 neue
      R266.3-Checks inkl. Stagger-Nahtgesetz, Falz-Durchlauf,
      Maschenaugen-Zählung), macro_render_test 2129/2129 (4 neue
      R266.3-Tests), megatest 220 Runs 0 FAIL, r165 clean, r199 ok,
      TEXTURING.pdf 64 Seiten regeneriert, MANUAL 5.9 (54+MAP/7 Seiten,
      55 Looks), textur-matrix-ist/soll regeneriert. Preview:
      analyse/r2663_deko_preview.png (6 Panels, echte Preset-Tiefen).
      **STAND R266.2 Häppchen 3 (19.11., 9 organische Muster FERTIG,
      49 Bibliotheksmuster):** RINGS (Jahresringe, wandernde
      Ringgrenzen), OAK (Poren-Streaks über Flammenwellen), BEECH
      (feine dichte Faser), KNOT (Torus-Knotenaugen + Gauß-Swirl),
      OLDBARK (anisotrope wrapped Voronoi, Bibliotheks-Look „Alter
      Stamm" mit amp 2.8 — der Deep-Relief-Baumstamm), LEATHER
      (45°-Steppung mm-true via ar), ORANGE (Mikro-Dellen, amp 0.18),
      CRACKS (Voronoi-Netz, Schmalkern 0.07/0.17 + weite Schulter,
      Tiefe 1.25 — druckbar ~0.4 mm Kern bei 6 mm-Zelle), WRINKLE
      (two-octave ridged, längsgestreckt). Registrierung komplett:
      _TX_PATTERN 49/49/49, LCD-Cap DYNAMISCH (war hart auf 4 Seiten/
      27 Muster kodiert — PERFORATION..NETGRID seit R265 auf dem LCD
      unerreichbar, Feldbug gefixt), toolchain 27→49 kongruent, 9 neue
      Bibliotheks-Looks (53 gesamt). Evidenz: r238 59/59 GRÜN, r165
      clean, r199 ok, megatest 214 Runs 0 FAIL, macro_render_test
      2125/2125 (inkl. 5 neuer R266.2-Tests). MANUAL 5.9 Katalog +
      48+MAP/7 Seiten, TEXTURING.pdf 58 Seiten regeneriert,
      textur-matrix-ist/soll.png regeneriert. Preview: analyse/
      r2662_organics_preview.png (9 Panels, echte Preset-Tiefen).
      **Gewünschte neue Familien (Vorschlagsliste, vor Bau mit Nutzer
      abstimmen):** Wände/Mauerwerk — Natursteinmauer, Bruchstein-
      Rhändermauer (drei Sorten Fugenversatz), Fliesen (quadratisch +
      Rechteckversatz, mit Fase), Parkett (Fischgrät + Stabparkett mit
      Nut/Feder-Kerben), Laminat-Dielen (lange Planken, HF-geprägte
      Holzstruktur); Hölzer — Längs- UND Querholz (Jahresringe
      quer), verschiedene Holzarten (Eiche grobfaserig, Buche fein, astig
      mit Ästen); Labyrinth-artiges — **HILBERT ERSETZEN: echte
      Hilbert-Kurve (Distance-Field) statt Zickzack-Bändern**
      (Nutzerbefund: „müsste eher wie ein Labyrinth aussehen“
      — soll es auch sein), plus echte Labyrinth-/Maze-Struktur;
      technische/moderne Strukturen — Hexagon-/Oktagon-Zellmuster
      (variabler Zelldurchmesser), Perforationsblech (rund + quadratisch
      versetzt), Carbon-/Twill-Gewebe, Pin-/Noppen-Matrix; organisch —
      Wellblech diagonal, Ledernarben, Orangenhaut (bewusst fein),
      Trockenrisse/Schlammplatten.
      Orientierung erlaubt: klassische 3D-Programm-Texturbibliotheken
      (prozedurale wood/stone/brick/tiles/…), aber nur fürs
      Bump-Mapping interessante Ideen übernehmen.
      Lieferumfang je Muster: Pattern-Funktion + Preset + Kennzahlentest +
      Matrix-Preview-Zelle + TEXTURING.pdf-Katalogseite + r238-artiger
      Feldcheck. **Vor Baubeginn: verbindliche Musterliste dem Nutzer zur
      Bestätigung** (Umfang klären: wie viele neu, welche raus).
- [x] **J9 — SCHABLONEN-GENERATOR (R267, umgesetzt 19.11.2026 nach
      Nutzer-Design).** Bild → **Sprüh-Schablonen-Set** — LCD `Tools >
      Stencil` (nutzt die Lithophane-Bildliste): Quantisierung in
      **2–4 Tonbänder** (`stencil_steps`), **je Band eine flache
      Platte** — Sprühreihenfolge hell→dunkel, Platten auf Passstiften
      gestapelt. Nutzer-Design umgesetzt: **Stege automatisch 3× Düse**
      (`_stencil_bridges267`: Flood-Fill-Insel suche, horizontale
      Brückenstrips, max 80 Iterationen — das O-Innenstück bleibt
      angebunden), **Rechteckplatte mit durchgehendem 8-mm-Rand + 4
      Passlöcher D4.2 mm an IDENTISCHER Position in jeder Platte**
      (Ecken (FR/2, GR−FR/2), Stack auf M4-Pins), **optionale
      Negativ-Schablone** (`stencil_negative`: Motiv steht, Hintergrund
      sprüht durch). Ehrlich statt haarfein: ein Band < 2 % der Fläche
      wird weggekürzt (Schrittzahl reduziert sich mit Notiz) —
      Flächenaufdrucke füllen oft weniger Bänder als bestellt.
      Engine `make_stencil` + Watcher + Makros STENCIL_INFO/STENCIL_CREATE
      + LCD-Menü (Settings + 10 Bild-Slots mit Stern-Arming) komplett.
      Evidenz: r267_stencil_check **34/34** (Bänder, Masken-Partition,
      Loch-Kongruenz, Brücken-Flood, G-Code-Dichte, Determinismus),
      megatest **224/224** (+4 Stencil-Runs), macro_render_test
      **2133/2133** (5 neue R267-Checks + Inventory/Counter-Pflege),
      r265 Manual-Index sauber (268 public), r218 WebUI 26/26 (JSON+
      Embed aktualisiert), MANUAL.md/MANUAL.pdf (5.6 + Index) gepflegt.

## K. Toolchain-Architektur §20 („Effektkette") — begonnen (Sitzung nach `fecf500`)

- [x] **K1 — Konzept + Preset-Vertrag Phase 1.** `analyse/TOOLCHAIN-KONZEPT.md`
      (Ist-Stand belegt: `_spawn_job` r2_postproc.py:25949, `JobRegistry`
      r2_job_service.py:406 mit ram_min_mb-Gates R223, `_GEN_OUT_SET`-
      Ausgabemodi, Vnn_/Cake-Ordnernamen, make_range:1937 als Werkzeug-
      beispiel; Phasen 2–4 + Kompatibilitäts-/Host-Schutz-Kapitel).
      `tools/toolchain.py`: Preset-Schema `r2-toolchain/1`, Registry mit
      3 quellenbelegten Ankern (range/scale/texture mit LCD-Wertebereichen),
      §20.2 ERZWUNGEN (Eingabedatei-Schluessel in jeder Ebene verboten),
      reiner Plan mit temp-/Gate-Markierung je Stufe (§20.3/§22.4),
      Multi-Output-Werkzeuge (Cake) bewusst abgelehnt statt Semantik zu
      erfinden. 21 Orakel-Tests (`tools/test_toolchain.py`). Kein
      Ausführer, kein Queue-/Watcher-/LCD-Anschluss — experimentell.
- [x] **K2a — Registry aus Menü-Daten + Ausführungs-Engine (offline):**
      `build_registry()` leitet alle 8 Mods-Werkzeuge aus web/menu_
      structure.json ab (LCD-Bereiche + SAVE_VARIABLE-Namen — Quelle der
      Wahrheit); `registry_drift()` sichert die Anker-Registry dagegen ab
      (CI-Test schlägt bei LCD-Änderungen an). Anker an Menü-Wahrheit
      korrigiert (seed 1..999, floor/top/brim 0..10, start ab 2; start/end-
      Maximum dynamisch → Fallback 9999 dokumentiert). `run_chain()` setzt
      die §21/§22-Gates physisch durch: Validierung je Stufe (§22.1:
      existiert/lesbar/nicht leer), Temp-Löschung ERST nach Übernahme
      (§22.4-Orakel: Abbruch lässt unübernommene Zwischenstände liegen),
      Zustände queued/running/success/failed/cancelled, Ausgabemodi save/
      preview/queue mit Registrierungs-Hook (Hook-Fehler = FAILED), kein
      Überschreiben, Eingabeprüfung vor Start. 18 neue Tests, 39 gesamt.
      Commit `feat: derive toolchain registry from menus and enforce chain
      gates`.
- [x] **K2b/1 — echte Werkzeuge als step_runner (offline bewiesen):**
      `tools/toolchain_steps.py` — Adapter für range (make_range:1937),
      scale (apply_scale:23861, Prozent→Faktor, Taper, Bett-Zentrierung),
      twist (apply_twist:24186), mirror (apply_mirror:24442, LCD-Index
      0=X/1=Y), texture (r2_texture.apply_texture:672, BUMPS-Modus); Engines
      schreiben in den Schritt-Workspace, Adapter überführen auf die
      Plan-Namen Vnn_ (os.replace). Lazy-Import per importlib (Muster
      v1_range_cause_check). Anker-Registry auf 5 Werkzeuge erweitert
      (twist deg -720..720, mirror Achse x/y) mit Menü-Aliasen im
      Drift-Wächter. `tools/test_toolchain_steps.py` (11 Tests): echte
      Dreierkette range→scale→twist auf markierter Synthetik-Datei (alle
      Gates, Temps nach Übernahme gelöscht), Skalier-Orakel (50 % →
      X-Spanne halbiert), Spiegel-Orakel (Spanne bleibt), Textur auf
      Außenwänden, Engine-Guard-Fehler wird nachvollziehbarer Schritt-
      Fehlschlag. NEBENERKENNTNISSE (Verhalten wie geliefert): make_range
      KLEMMT end auf die echte Schichtzahl (2..99 auf 6 Schichten druckt
      2..6; nur leeres Fenster = Fehler mit Klartext), apply_scale lehnt
      No-Op (100 %/100 %) ab. Kein Watcher/Makro/LCD geändert.
- [x] **K2b/2 — Watcher-/Makro-/LCD-Anbindung (R259, erledigt):**
      `TOOLCHAIN_APPLY`-Makro (17_generator.cfg: R160-Doppelklick, Guard-
      Kette, `_GEN_GO KEY=toolchain`, Nonce-Increment) → Watcher-Dispatch
      (`toolchain_nonce` in NONCE_KEYS + Priming + _freeze133: Ketten-
      Schreibarbeit wartet auf Idle wie jeder Generator) → EIN
      `_spawn_job('Toolchain', …)` pro Kette. Preset-Auflösung als
      testbare Funktion `load_preset_file` (tools/toolchain.py: JSON-/
      Lesefehler/Vertragsverletzungen → Klartext, Watcher meldet per
      NOTIFY). Job-Innenleben: plan_chain mit first_version=
      _next_gen_version(Toolchain/) (kein Kollidieren mit früheren
      Endausgaben, §22), run_chain + plan_step_runner (gemischte
      Ketten; laufendes r2_postproc-Modul wird als _PP injiziert — kein
      zweifaches Laden, Pi Zero 2 W), on_output-Hook für queue/preview
      (_sel_line-Registrierung), _meta_finalize(force=True) auf der
      Endausgabe. Preset-Auswahl ALS DATEI: SD-Browser-Klick auf .json
      (SDNAV_GO in 13_system.cfg; .json neu in _SD_EXT151 sichtbar),
      Beispiel-Preset presets/toolchain/scale-twist.json wird beim
      ersten Watcher-Start in den Toolchain-Ordner geseedet (gelöschtes
      Beispiel bleibt gelöscht). LCD-Menü `Pre-Print > Mods >
      Toolchain` (Preset/File/How/Apply). Grenze dokumentiert: Ketten-
      Eingabe = Datei im Gcodes-WURZEL-Ordner (§20.2). Gates: macro_
      render 2110/2110 (7 neue R259-Tests: Makro rendert+guards,
      Nonce-/Freeze-/Folder-Registrierung, .json-Pick, Beispiel
      shippt), r81 23/23 ohne Re-Freeze (keine Engine-Änderung;
      Versions-Bump + r81-Re-Freeze gehören zum Release-Schritt),
      audit_sweep 82/0, megatest 190/0, test_toolchain 45 (load_
      preset_file + first_version), test_toolchain_steps 19 (Ende-zu-
      Ende-Kette von der DATEI, Zweitlauf-Versionshebung, Verdrahtungs-
      Guards). r2_postproc_next.py als Byte-Kopie synchron gehalten
      (R252-Regel). NEBENERKENNTNIS: Klipper-Jinja kennt keinen
      `endswith`-FILTER — Methodenaufruf `.lower().endswith()` nutzen,
      und Filter+Methodenaufruf lassen sich nicht mischen (erst `set`).
- [x] **K2b/3 — Benennung & Unterordner-Eingaben (R260, Nutzer-
      Entscheidung zu OFFENE-FRAGEN #19):** Ketten-Quelle aus Unter-
      ordnern erlaubt (§20.2 → relative Pfade, `..`/absolut unmöglich);
      Umlaut-Umschrift vor dem Sanitize in Engine-_gen_stem (ALLE
      Generatoren) und Plan-Stem (`Größer Rahmen` → `Groesser_Rahmen`
      statt `Gr_er_Rahmen`), Zwillings-Maps mit Drift-Wächter;
      ENDAUSGABE trägt den Preset-Namen als Wortkette
      (`V06_Mein_Teil_ScaleUpTwist.gcode`), Temps plain; ein führendes
      V<nn>_ einer Vorgänger-Ausgabe fällt aus dem Stem; Preset-Namen
      dürfen Umlaute tragen. Gates: macro_render 2112/2112, r81 23/23,
      audit_sweep 82/0, megatest 190/0, test_toolchain 47,
      test_toolchain_steps 21. Bestätigt für den Nutzer: Unterordner
      listen im LCD-Browser schon heute NEUESTE ZUERST (R187), Root
      bleibt A–Z; Gen-files-Browser (12 neueste) existiert.
- [x] **K3 — Phase 3 Bedienoberfläche (R259/R260/R261, erledigt):** LCD-
      Menü mit R259 geliefert; Web-Spiegel über den Menü-JSON-Export
      automatisch (Toolchain-Knoten enthalten); **Fortschritt je Stufe
      (R261):** `run_chain(on_step=…)` mit Start-Semantik (feuert, BEVOR
      der Schritt läuft), der Watcher-Job schreibt `M117 Chain n/N:
      <Werkzeug>` + Journal-Zeile — Hook-Fehler sind Kosmetik und werden
      geschluckt (asymmetrisch zu on_output: Registrierung ist Gate).
      Preset-Verwaltung bleibt **bewusst dateibasiert** (Mainsail/
      Dateisystem) — kein LCD-Submenü für speichern/laden/löschen.
      Tests: test_toolchain 49 (2 neue on_step-Orakel: Reihenfolge/
      Start-Semantik, Kosmetik-Regel), test_toolchain_steps 22
      (Verdrahtungs-Guard).
- [x] **K4 — Phase 4 (R262/R263, ERFÜLLT):** §22.3 verifiziert (Kette
      unter gen_busy, alle vier Startwege verweigern, kein Deadlock);
      MANUAL Kap. 5.21 + 14 + 25; TESTANLEITUNG Kap. 32 + aktueller
      Header/Boot-Check (standen noch auf .141/.142a); TOOLS_INVENTORY
      Stand V4 + Chain-Zeilen; test_review_bundle an getrackte
      Übergabe-Quellen angepasst (13. Auftrag); Presets im Paket
      (presets/toolchain/ im ZIP, r199 12/12); Version R2-2026-11-18.3/
      V4 überall gestempelt (inkl. Web-Badge + Page-State R263, r218-Pin);
      r81 stamp-class re-frozen über den echten Toolchain-Code (A/B:
      V4-Modul mit alten Stempeln == V3-Goldens byte-identisch, alle 23;
      pr01-pr10 unverändert); backups/r2_postproc_R2-2026-11-18.2_V3.py
      als Feld-Rollback; Release-Bericht
      docs/RELEASE_R2-2026-11-18.3_REPORT.md; ZIP gebaut aus getracktem
      Baum ohne analyse/ (256 Dateien) + .sha256-Sidecar in releases/.
      Gates: macro_render 2112/2112, megatest 190/0, review_checks PASS,
      r81 23/23, r91, audit 82/0, r110 13/13, r238 30/30, r168 19/19,
      r165 clean, r218 26, toolchain 49+22, gcode_re 10/10.
