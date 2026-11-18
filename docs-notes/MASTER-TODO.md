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
