# System-Audit 2026-10 (R90.1b-Stand, Commit-Umfeld: dd2594d → R90.1b)

Auftrag: einmal als Nutzer über alles drübergehen — Einstellmöglichkeiten,
Wechselwirkungen, Absturz-/Abbruchrisiken, Sicherheit bei Fehlfunktion,
Befehlsfluten/MCU-Last, LCD-Bedienbarkeit. Ergebnis: **4 echte Bugs gefunden
und gefixt** (2 davon druckkritisch), 1 Menü-Umbau, 1 neues Dauer-Simulations-
werkzeug, sonst grün.

## A. Gefundene & gefixte Bugs (nach Schwere)

| # | Schwere | Fund | Wirkung ohne Fix | Fix |
|---|---------|------|------------------|-----|
| 1 | **KRITISCH** | `_rr_pts`: Eck-Reihenfolge TR→BR→BL→TL statt TR→TL→BL→BR | JEDER R90-Rahmen (und Kit-Streifen) hätte als selbst-schneidender 4-zackiger Stern gedruckt — Bowtie-Wände, unbrauchbare Teile | Reihenfolge korrigiert, Kettentest (max. Kante = Seitenlänge, kein Diagonal-Sprung) |
| 2 | **KRITISCH** | `_convex_intervals`: Vorzeichenfehler — Strahl lief rückwärts, alle Konturschnitte wurden weggefiltert | `_ring_hatch` lieferte 0 Segmente: Rahmen-Ring OHNE Infill, OHNE Regal (Photo fällt durch!), Ironing leer | Formel korrigiert; Ring-Hatch jetzt 298 Segmente, 0 Verletzer in der Photo-Öffnung |
| 3 | hoch | `make_frame`: kein `PRINT_END` am Dateiende | Frame-Dateien ohne End-Choreografie (State blieb 'printing', keine Stats/LEDs/Cooldown) | R90.1a: M107 + PRINT_END pro Plate |
| 4 | mittel | `TYPE_MAP` fehlte `top surface infill` | R90.1b-Struktur-Layer (Lines/Waves/Hex) liefen als CUSTOM statt SURFACE-TOP — Live-Tuning-Overrides griffen nicht | Key ergänzt → APPLY_TYPE TYPE=SURFACE-TOP |

Beide kritischen Bugs lingen seit R90-Release unbemerkt, weil die Tests nur
Tags/Struktur prüften, nicht die Geometrie selbst. Neu: segmentlevel-Tests in
der Suite (Lip/Flip/Kabel/Struktur/Photo-frei) + `tools/audit_sweep.py`.

## B. Simulation aller Generatoren (neu: tools/audit_sweep.py)

59 Dateien über die komplette Parameter-Matrix (Frames: 4 Presets × FLAT/CASE
× 5 Front-Oberflächen × 3 Disc-Varianten × Cable × Closure × Shape × Kit;
Ties/Angles/Seal/Bridge/Labels/Range/Litho mit synthetischem PNG). Pro Datei
werden geprüft: Bettgrenzen (Realbett 220×220), Z-Monotonie, EXCLUDE-START/END-
Balance + DEFINE davor, bekannte ;TYPE:-Tags + APPLY_TYPE-Vollständigkeit,
PRINT_START vor erster Bewegung, nach PRINT_END nur Trailer-Zeilen
(RESPOND/M117/M300/G4), Layerzahl == Info, keine Wahnsinns-Koordinaten,
Move-Rate. **Ergebnis: 0 FAIL.** Das Script bleibt im Repo — vor jedem Release
laufen lassen (`python3 tools/audit_sweep.py`).

## C. Befehlsfluten / MCU-Last (Timer-too-close-Prävention)

- `_PACE` (100 ms Mikropause, nur idle — nie im Druck) ist flächendeckend
  im Einsatz: 01_state (4×), 05_materials (53×), 08_start_stop (17×),
  17_generator (27×, inkl. des neuen GEN_FRAME mit 5 PACE-Blöcken).
- Gemessene Worst-Case Move-Raten (Seriell-Budget 8-Bit-MCU ≈ 450 Moves/s):
  Labels 373/s (historisch, feldbewährt), Frames max. 322/s momentan
  (Bögen des 0,4-mm-Eckenradius bei F2400 — nur wenige Dutzend Hops pro Layer),
  Litho 39/s, alles andere < 140/s. **Keine Flutquelle, kein Shutdown-Risiko.**
- Watcher-Loop: genau ein `time.sleep(interval)` pro Runde, keine Poll-Wüste.

## D. LCD-Struktur (Bedienbarkeit)

Live Tuning war gewachsen statt geordnet — jetzt thematisch gruppiert
(Babysteps ↔ Z-Offset-Name direkt beieinander, Thermik an einem Ort,
Info-Listen ans Ende):

| alt (Ausschnitt) | neu |
|---|---|
| Z±, Plotter, Sources, File(30!), Hot/Bed/Fan, **Zoff**, Speed, Accel, Vel, Features, Extr, Temps&Fan, Pause, Objects | **Z±, Zoff**, Speed, Accel, Vel, Extr, Features, **Hot/Bed/Fan, Temps&Fan**, Pause, Objects, Plotter, Sources, File |

Vorher: nach dem Babystepen 15 Punkte durchscrollen, um den Offset zu sehen
(genau das User-Beispiel). Vorher lag auch die 30-Punkte-Datei-Info-Liste vor
den Aktionsmenüs (Pause/Objects) — jetzt am Ende. Alle Untermenüs unangetastet,
nur Reihenfolge; Suite (inkl. aller Menü-Strukturtests) 1100/1100 grün.

Weiterhin bestätigt (unverändert gut): Maintenance = Kalibrier-Reihenfolge,
Pre-Print folgt dem Druck-Workflow, Tools-Generatoren alle nach demselben
Muster Info→Settings→Create→How, System-Menü konsequent 2-stufig bestätigt.

## E. Sicherheit (technische/elektrische Fehlfunktion)

- PRINT_END-Choreografie jetzt in JEDEM Generatorfile (war #3 oben): State
  'finished', Stats, LED-Endzustand mit Rückkehr zu Idle (R46), Lüfter-
  Cooldown via UPDATE_DELAYED_GCODE.
- Nach PRINT_END stehen nur noch harmlose Trailer-Kommandos (per Sweep-
  Invariante erzwungen) — nichts kann den Endzustand stören.
- Heizer/Netzrelais/Power-Hold-Templates unverändert (printer.cfg.example,
  Suite-testbar: shutdown_value: 0 etc.).
- Guards feuern VOR dem Datei-Write (Kit-Platte, Backplate-zu-groß,
  OVAL+Struktur, Cable ohne CASE) — keine halben Dateien auf der Karte.
- Neue Druckbarkeits-Risiken bewertet: Kabel-Slot = 6-mm-Brücke über der
  Öffnung (Layer 13+, mit Lüfter ab Layer 2 unkritisch, im File notiert),
  Struktur-Grate/Furchen ohne Überschhang, Kit-Bridge-Streifen unverändert.

## F. Beobachtungen ohne Änderung (Backlog)

1. Pre-Print > File (G-code) mischt die Plotter-Start-Overrides unter die
   Datei-Infos — kosmetisch, selten benutzt.
2. Labels-Move-Rate 373/s liegt nahe der 400er-Warnschwelle — feldbewährt,
   nur beobachten.
3. Schnellzugriff Hot/Bed/Fan + Temps&Fan-Submenü sind redundant (jetzt
   wenigstens gruppiert); bei Gelegenheit zusammenfassen.
4. Die übrigen Generatoren haben noch den 244-mm-Bett-Default (Produktion
   unberührt — der Watcher übergibt immer das Realbett); nur bei direkter
   CLI-Nutzung relevant.
