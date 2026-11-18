# Toolchain-Architektur (Gesamtbriefing §20/§22) — Konzept und Phasenplan

**Status:** Phase 1 + Phase 2a umgesetzt (`tools/toolchain.py` +
`tools/test_toolchain.py`, 39 Tests). Phase 1: Preset-Vertrag. Phase 2a:
vollständige Registry aus den MENÜ-DATEN (web/menu_structure.json — Quelle
der Wahrheit) mit Drift-Wächter als CI-Test, korrigierte Anker an die
Menü-Wahrheit, und die Ausführungs-Engine `run_chain` mit den §21/§22-Gates
(Validierung je Stufe, Temp-Löschung erst nach Übernahme, Zustandsmodell,
Ausgabemodi, kein Überschreiben). Phase 2b (Anbindung der echten System-
Werkzeuge an Watcher/Queue/Makros) ist NICHT umgesetzt; nichts greift in
den Druckpfad oder r2_postproc.py ein. Dieses Dokument ist der vom
Gesamtbriefing §20.5 geforderte Architektur- und Phasenvorschlag — belegt
gegen Code, nicht gegen Doku.

---

## 1. Auftrag

Gesamtbriefing §20 („Zentrale Toolchain-Architektur"): mehrere Pre-Print-
Werkzeuge und Generatoren sollen zu einer geordneten Verarbeitungskette
kombiniert werden — jedes Werkzeug baut auf der Ausgabe des vorherigen auf
(§20.1), die Originaldatei bleibt unverändert (§20.2), Zwischenstände sind
temporär und nur so lange gültig, bis der Nachfolger sie übernommen hat
(§20.3/§22.4), Presets enthalten keine fest verdrahtete Eingabedatei (§20.2)
und werden beim Laden auf die aktuell ausgewählte Datei angewendet. Drei
Ebenen (§20.5): Tools / Toolchains / Toolchain-Presets. Die frühere UI-Demo
war ausdrücklich nur ein Interaktionsmodell (§20.4) — hier wird nichts als
fertig behauptet, was nicht existiert.

## 2. Ist-Stand im Code (das Fundament ist vorhanden)

| Baustein | Fundstelle | Bedeutung für die Toolchain |
|---|---|---|
| Trigger-Kette | LCD/Makro → `SAVE_VARIABLE` → Moonraker → Watcher-Poll in `r2_postproc.py` | Ein Toolchain-Start braucht KEINEN neuen Mechanismus — derselbe Weg wie bei jedem Generator |
| Job-Queue, ein Worker | `_spawn_job` (`r2_postproc.py:25949`), `_JOB_STATE` (Key-Dedupe, „one job at a time") | §22.2 Druckpriorität ist bereits Durchsetzung, nicht Absicht: nichts läuft parallel |
| Job-Lifecycle | `JobRegistry.enqueue(name, key, ram_min_mb=60)` (`r2_job_service.py:406`), Zustände, `outputs`/`validation`-Listen pro Job | §22.1-Zustandsmodell existiert; Success-Kriterien (Datei existiert, lesbar, geprüft, registriert) sind ansatzweise die bestehende Ausgabevalidierung |
| RAM-Gates | R223: `ram_min` 60/110 MB je Jobtyp (`.136s`-Feldlog: Photo-Build kollabierte den Host) | Toolchains dürfen die Gates nicht aushebeln — jede Stufe bleibt ein eigener gegateter Job |
| Host-Schutz | `nice`, R148-Watcher-CPU-Fix, Shutdown-Register #6 („eine Job-Queue, ein Worker") | Die historischen „Timer too close"-Fälle aus Hintergrundlast sind genau der Nicht-Verhandlungspunkt von §22.2 |
| Ausgabemodi | `_GEN_OUT_SET OUT=…` (`08_print_start_stop.cfg:718`, `12_maintenance.cfg:2175/2313`; QUEUE/PREVIEW/… via MANUAL Kap. 18) | §21-Ausgabemodi existieren je Generator; eine Toolchain braucht denselben Schalter einmal für die Kette |
| Versionierung/Ordner | `Vnn_…`-Konvention; Cake legt nach `Cake/` ab (H3) | Namensvertrag für Zwischenstände: `V01_…`, `V02_…` je Stufe, Ordner `Toolchain/` (Vorschlag) |
| Beispiel-Werkzeugvertrag | `make_range(src, start, end, floor, top, brim, …)` (`r2_postproc.py:1937`) | Zeigt die Werkzeugform: benannte Parameter, prüfbar, Ausgabe neben der Quelle |

## 3. Der Vertrag von Phase 1 (`tools/toolchain.py`)

- **Preset-Schema `r2-toolchain/1`:** `{schema, name, description?, steps:[{tool,
  params}]}`. §20.2 wird **erzwungen**: Schluessel wie `input/file/src/path`
  sind in jeder Ebene (Preset, Schritt, Parameter) kategorisch verboten —
  Orakeltest prüft genau das.
- **Tool-Registry (quellenbelegt):** `range` (make_range:1937; start/end/
  floor/top/brim, Querschnittsregel start≤end), `scale` (lcd_menues.cfg:3883:
  X/Y 25–300 %, Top 0–300 %), `texture` (17_generator.cfg:1179: 27 Muster-
  Codes; LCD-Bereiche Around 3–80, Height 0.5–200, Depth 0.05–1.0 mm,
  Richtung IN/OUT, Seed). Multi-Output-Werkzeuge (Cake `PART=BOTH` → zwei
  Dateien) werden in Ketten **abgelehnt**, bis die Verzweigungssemantik
  geklärt ist — sie wird nicht erfunden.
- **Validierung:** Typen (bool ist kein int — Python-Falle getestet), Minima/
  Maxima, Enums, Pflicht-/Optionalparameter mit Defaults, Querschnittsregeln,
  Schrittanzahl ≤ 16. Fehler sind Klartext mit Schrittbezug.
- **Plan (`r2-toolchain-plan/1`):** reine Planung — Job N bekommt die Ausgabe
  von Job N−1 als Eingabe, Ausgaben `Vnn_<stem>.gcode` im Ordner `Toolchain/`
  (Vorschlag), Zwischenstände `temp: true`, jede Folge-Stufe trägt
  `requires: validierte Ausgabe von Job N`. **Nichts wird ausgeführt, keine
  Datei geschrieben.**
- 21 Orakel-Tests Phase 1 + 18 Tests Phase 2a, komplett offline.

## 3a. Phase 2a — Menü-Registry, Drift-Wächter, Ausführungs-Engine

- **Zwei Sichten, eine Wahrheit:** `build_registry(menu_data)` leitet die
  VOLLSTÄNDIGE Werkzeugliste aus `web/menu_structure.json` ab (Baum
  `__main __preprint __mods`: range, texture, scale, cake, twist, mirror,
  offset, plot — jeweils mit LCD-input_min/max/step und SAVE_VARIABLE-
  Namen). Die Anker-Registry (semantische Parameternamen) wird durch
  `registry_drift()` GEGEN die Menü-Daten gesichert: Der CI-Test
  `test_anchor_registry_has_no_drift_against_menu` schlägt an, sobald
  jemand die LCD-Bereiche ändert — kein zweites Pflegen, kein stilles
  Auseinanderdriften. Dabei gefundene und korrigierte Abweichungen der
  Phase-1-Anker: texture seed 0..999999 → **1..999**, range floor/top/
  brim 0..50/0..50/0..20 → **0..10**, range start ab 1 → **ab 2** (alles
  Menü-Wahrheit); range_start/-end-Maximum ist im Menü dynamisch
  (total_layers-abhängig) → statischer Fallback 9999 mit dokumentierter
  Aussetzung der Bereichsprüfung.
- **Ausführungs-Engine `run_chain(plan, workspace, input_path,
  step_runner, ...)`:** führt einen Plan mit einsetzbaren Schritt-
  Funktionen aus und setzt die Briefing-Gates physisch durch —
  Validierung je Stufe (Default-§22.1: existiert, lesbar, nicht leer;
  austauschbarer Validator), Temp-Löschung des Vorgänger-Zwischenstands
  ERST nach validierter Übernahme durch den Nachfolger (§22.4 — Orakel-
  test: Abbruch nach Stufe 2 lässt V02 liegen, V01 ist weg), Zustände
  queued/running/success/failed/cancelled (§22.1), Ausgabemodi save/
  preview/queue (§21) mit Registrierungs-Hook (scheitert der Hook, ist
  die Kette FAILED — §22.1 „korrekt registriert"), kategorisches
  Nicht-Überschreiben existierender Endausgaben, Eingabeprüfung vor
  Start. Bei Fehler/Abbruch bleiben Zwischenstände zur Nachvollziehbarkeit
  liegen.
- **Bewusst offen (Phase 2b):** die step_runner für die echten System-
  Werkzeuge (make_range & Co. im Watcher-Verbund), Makro-/LCD-Anbindung,
  echte Dauer-Messung je Schritt. run_chain ist die Engine — WAS sie
  ausführt, entscheidet die Anbindung.

## 4. Phasenplan

- **Phase 1 (dieser Stand):** Vertrag + Planung als experimentelles Modul.
  Kein Anschluss an Watcher/Queue/Makros.
- **Phase 2a (erledigt):** Registry aus Menü-Daten + Drift-Wächter +
  Ausführungs-Engine `run_chain` mit §21/§22-Gates (siehe 3a).
- **Phase 2b/1 (erledigt):** die echten Werkzeuge als step_runner —
  `tools/toolchain_steps.py` wrappt make_range/apply_scale/apply_twist/
  apply_mirror/apply_texture (Fundstellen im Modulkopf), Engines schreiben
  in den Schritt-Workspace, der Adapter überführt auf die Plan-Namen Vnn_.
  Anker-Registry jetzt 5 Werkzeuge (twist/mirror inklusive), weiter vom
  Menü-Drift-Wächter gesichert. `tools/test_toolchain_steps.py` (11 Tests)
  fährt ECHTE Ketten auf markierten Synthetik-Dateien: range→scale→twist
  komplett durch alle Gates, Skalier-/Spiegel-Orakel an den Koordinaten,
  Textur auf Außenwänden, Engine-Guards (inkl. Cake-Hälften-Schutz aus H1)
  werden nachvollziehbare Schritt-Fehlschläge. Verhalten wie geliefert
  dokumentiert: make_range klemmt 'end' auf die echte Schichtzahl;
  apply_scale lehnt No-Op-Skalierung ab.
- **Phase 2b/2 (erledigt, R259) — Watcher-/Makro-/LCD-Anbindung:**
  Toolchain-Start über den bestehenden Weg: `TOOLCHAIN_APPLY`
  (macros/17_generator.cfg, R160-Doppelklick, Guards, `_GEN_GO`,
  Nonce-Increment) → SAVE_VARIABLEs → Watcher-Dispatch
  (`toolchain_nonce` in NONCE_KEYS/_prime_nonces/_freeze133 — Disk-I/O
  wartet auf Idle wie jeder Generator) → `_spawn_job('Toolchain', …)`
  mit EINEM Queue-Eintrag pro Kette. Der Job: `load_preset_file`
  (testbare Preset-Auflösung, tools/toolchain.py) → `plan_chain` mit
  `first_version=_next_gen_version(Toolchain/)` (kein zweiter Lauf
  kollidiert mit der ersten Endausgabe, §22) → `run_chain` mit
  `plan_step_runner` (gemischte Ketten, echte Engines; r2_postproc wird
  als Modul injiziert statt doppelt geladen — Pi Zero 2 W RAM) →
  Ausgabemodus queue/preview über on_output-Hook (`_sel_line`), Meta-
  Finalisierung der Endausgabe (`_meta_finalize(force=True)`).
  Preset-Auswahl als DATEI: Klick auf ein .json im SD-Browser pickt es
  (SDNAV_GO, macros/13_system.cfg; `.json` in `_SD_EXT151`), Beispiel-
  Preset `presets/toolchain/scale-twist.json` wird beim ersten Start in
  den Toolchain-Ordner geseedet. LCD: `Pre-Print > Mods > Toolchain`
  (Preset/File-Anzeige, How, Apply-Doppelklick). Eingabe = ausgewählte
  Datei im Gcodes-WURZEL-Ordner (§20.2 plain name). Gates: macro_render
  2110/2110 (7 neue R259-Tests), r81 23/23 (keine Engine-Änderung,
  kein Re-Freeze), audit_sweep 82/0, megatest 190/0,
  test_toolchain 45 + test_toolchain_steps 19.
- **Phase 2b/3 (erledigt, R260) — Benennung & Unterordner-Eingaben
  (Nutzer-Entscheidung zu OFFENE-FRAGEN #19):** Ketten-Quelle darf aus
  Unterordnern kommen (`Range/V02_x.gcode` — §20.2 erweitert auf
  relative Pfade; `..`/absolute Pfade bleiben bauartlich unmöglich,
  Macro-/Plan-Guards synchron). Stem = sanitierter BASISNAME, ein
  führendes `V<nn>_` einer Vorgänger-Ausgabe fällt weg. Umlaut-Umschrift
  (ä→ae, ö→oe, ü→ue, ß→ss) VOR dem ASCII-Sanitize — überall: Engine-
  `_gen_stem` (alle Generatoren) UND der Plan-Stem
  (`Größer Rahmen.gcode` → `Groesser_Rahmen` statt `Gr_er_Rahmen`);
  Zwillings-Maps mit Drift-Wächter (test_toolchain_steps). Die
  ENDAUSGABE trägt den Preset-Namen als Wortkette (CamelCase,
  Wortgrenzen-Schnitt bei 24 Zeichen): `V06_Mein_Teil_ScaleUpTwist.gcode`
  — Temps bleiben plain (§22.4: sie sterben ohnehin). Preset-Namen
  dürfen jetzt Umlaute tragen (Anzeige/RESPOND; der Tag transliteriert).
  Gates: macro_render 2112/2112, r81 23/23 (ASCII-Fixtures unberührt),
  audit_sweep 82/0, megatest 190/0, test_toolchain 47,
  test_toolchain_steps 21 (Unterordner-Kette Ende-zu-Ende mit echten
  Engines).
- **Phase 3 — Bedienoberfläche (erledigt, R259/R260/R261):** LCD
  `Pre-Print > Mods > Toolchain` (Preset-/File-Anzeige, How,
  Apply-Doppelkdruck — mit R259 geliefert); **Fortschritt je Stufe**
  (R261): `run_chain(on_step=…)` feuert beim START jedes Schritts,
  der Job schreibt `M117 Chain n/N: <Werkzeug>` aufs LCD + Journal-Zeile
  — Kosmetik (Hook-Fehler werden geschluckt), anders als die
  on_output-Registrierung (Gate). Web-LCD-Spiegel: der Menü-JSON-Export
  führt den Toolchain-Knoten (menu_json_export, automatic). Preset-
  Verwaltung: **bewusst DATEIBASIERT** (Nutzer-Entscheidung R260-Runde:
  Presets sind Dateien, verwaltet über Mainsail/Dateisystem — kein
  Speichern/Laden/Löschen-Submenü am LCD nachgebaut).
- **Phase 4 — Queue-Abhängigkeit & Doku:** §22.3 (Druckstart wartet auf
  Job-Fertigstellung, Nutzer sieht den wahren Zustand), MANUAL-Kapitel,
  Toolchain-Presets im Backup/Paket.

Jede Phase endet mit Commit + Tests + Bericht; kein Sprung ohne grüne Gates.

## 5. Kompatibilität und Host-Schutz (der entscheidende Rand)

- **Drucker-Unabhängigkeit:** Die Toolchain läuft vollständig auf dem Host
  (Python, keine neuen Abhängigkeiten in Phase 1). Die Werkzeuge selbst sind
  bereits maschinenparametrisch (Generator-Matrix `r217_gen_matrix.py`:
  Generator × Düse × Bett, 1423 Checks) — eine Kette erbt das.
- **Druckpriorität (§22.2) bleibt unangetastet:** eine Queue, ein Worker,
  RAM-Gates je Stufe, `nice`. Eine Toolchain verlängert die Hintergrundlast,
  sie erhöht NIEMALS die Parallelität — genau die Lehre aus dem Shutdown-
  Register („Timer too close" kam aus Host-Schüben, nie aus dem MCU).
- **Pi Zero 2 W-Budget:** Beide neuen Recherchen (Gießformen, KI-Brücke)
  warnen zu Recht vor schwerer Geometrie auf dem Host. Regel für Phase 2+:
  was auf dem Host rechnet, läuft als gegateter Queue-Job; was zu schwer ist
  (Boolean-Meshes, Slicen), gehört auf einen externen Dienst (siehe J6) oder
  bleibt außerhalb.
- **Ein Funktionskern, viele Oberflächen (§10):** die Kette wird über
  Makros/`SAVE_VARIABLE` gesteuert — LCD, Web-LCD und Konsole bedienen
  dieselbe Logik ohne zweite Geschäftslogik.

## 6. Offene Punkte (nicht erfunden, sondern benannt)

1. Multi-Output-Werkzeuge in Ketten (Cake-Verzweigung): Semantik klären —
   gilt die Folge für beide Hälften? Wahl pro Zweig?
2. Werkzeug-Kompatibilitätsregeln über Parameter hinaus (z. B. Textur nach
   Range auf Boden/Deckel): in Phase 2 aus den echten Werkzeugverträgen
   ableiten, nicht raten.
3. Abbruch semantik einer laufenden Kette (§22.1 `cancelled`): Rest-Stufen
   verwerfen, aber abgeschlossene Ausgaben behalten — UX-Entscheidung.
4. Preset-Format für die LCD-Verwaltung (Name, Beschreibung, Schrittliste
   als Klartext) — Phase 3.
