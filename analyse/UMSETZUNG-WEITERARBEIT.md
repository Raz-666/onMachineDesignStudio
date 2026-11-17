# Umsetzung & Verifikation der Weiterarbeit (Pakete 1–7)

- **Stand:** 2026-11-17 (Basis-Commit `e9bf628984550fa6a48f80890396020f515e6d0f`, Core-Version `R2-2026-11-13.1`)
- **Prüfprotokoll:** `analyse/testprotokolle/weiterarbeit_checks.log`
- **Geltungsbereich:** vollständige Offline-Umsetzung, Regressions- und Gegenmutationsprüfung; **keine** Live-Drucker-, Moonraker-, UART- oder Hardware-Abnahme.

---

## 1. Übersicht der abgeschlossenen Arbeitspakete

### Paket 1 — Web-UI-Parität & R114-Synchronisation
- **Dateien:** `web/menu_structure.json`, `web/index.html`, `menus/lcd_menues.cfg`, `tools/r218_webui_check.py`
- **Änderungen:**
  - `web/menu_structure.json` und eingebettetes Fallback-JSON in `web/index.html` mit `tools/menu_json_export.py --embed web/index.html` auf exakt 2295 Sektionen synchronisiert (`sha256`-Kurzprüfsumme `f16aadd991a3bd00`).
  - Versions-Badge `#ver` in `web/index.html` auf `R2-2026-11-13.1` synchronisiert (Parität zu `macros/01_state.cfg`).
  - `tools/r218_webui_check.py` prüft zusätzlich die exakte Übereinstimmung von `web/menu_structure.json` mit `menus/lcd_menues.cfg` (26/26 Checks grün).
  - R114-Semikolon im Hilfetext von `menus/lcd_menues.cfg` (`__main __maint __iron __how`) durch ` - ` ersetzt, sodass kein doppeltes Anführungszeichen im gesamten `.cfg`-Bestand ein `;` enthält.

### Paket 2 — Makro-/Kalibrierungs-/Pausen-Guards & `KALIBRIERUNG.pdf`
- **Dateien:** `macros/{01_state,06_temp_controls,08_print_start_stop,11_gantry_sync,12_maintenance}.cfg`, `tools/r257_crash_guard_check.py`, `tools/make_calibration_pdf.py`, `KALIBRIERUNG.pdf`, `tools/test_calibration_and_pause_guards.py`
- **Änderungen:**
  - Pausen-, Homing-, Gantry-Sync- und Kalibrierungs-Guards gehärtet; `Z_TILT`-Probe-Fenster in `tools/r257_crash_guard_check.py` abgesichert (17/17 Checks, 8/8 Gegenmutationen gefangen).
  - R114-Semikolons innerhalb doppelt gequoteter `RESPOND`/`NOTIFY`-Strings in `macros/06_temp_controls.cfg` (`PAUSE_AT_LAYER`) und `macros/12_maintenance.cfg` (`IRONING_CAL`/`IRONING_RESULT`) bereinigt.
  - `tools/make_calibration_pdf.py` und `KALIBRIERUNG.pdf` aktualisiert und verifiziert (153 800 Bytes, 14 Seiten, SHA-256 `f15b633d9ad3caab178ce1d859100cbb1377133469cc7e0cc4a9cd6ec15c81bc`).
  - Alle 30 `[delayed_gcode ...]`-Timer sowie Homing-, Probe-, Purge-, Start-, End- und Menü-Exit-Verträge unverändert erhalten.
  - **Bewusst offen belassen:** `D1` (entsprechend Backlog-Disposition), `E4` (`position_min` / Hardware-Achsengrenzen).

### Paket 3 — `H2` Cake-Split-Engine & `CUTSPLIT.pdf`
- **Dateien:** `tools/r2_cake.py`, `tools/test_cake_layers_h2.py`, `tools/make_cakesplit_pdf.py`, `CUTSPLIT.pdf`, `tools/megatest.py`, `tools/macro_render_test.py`
- **Änderungen:**
  - Exakter Ebenenschnitt für lineare Züge (inkl. geneigter Z-Segmente) und G17-XY-Bögen (`G2`/`G3`, inkl. Helix-Z) unter Beachtung der Klipper-Modalregeln (`G90`/`G91` erzwingt relatives E auch unter `M82`; `G90` nach `M83` hält E relativ; `G92 X/Y/Z/E`).
  - Sauberer Neuaufbau von `;LAYER_CHANGE`, `;Z:`, `LAYER_MARK` und `_FILE_INFO TOTAL_LAYERS=` getrennt pro Hälfte (`UPPER`/`LOWER`) anhand realer positiver Extrusionsschichten — beide Hälften sind direkt in `make_range` (Layer Range) weiterverwendbar.
  - Korrigierte `reorient=True`-Rodrigues-Rotation (`+n -> (0, 0, +1)`, äußere Schnittflächennormale `-n -> (0, 0, -1)`): die Schnittfläche liegt flach bei `z_first` auf dem Bett, Z wächst streng monoton nach oben.
  - Balancierte Retract-/Modalzustände und atomare `mkstemp` + `fsync` + `os.replace`-Ausgabe.
  - `tools/make_cakesplit_pdf.py` und `CUTSPLIT.pdf` (83 369 Bytes, 7 Seiten, SHA-256 `125b2dd3509f438b4d344444b1155e0b020703f499f8921823c70629f90f86aa`) mit echtem Lauf und Schichtzahlen aktualisiert.
  - **Bewusst offen belassen:** `H3` (entsprechend Vorgabe).

### Paket 4 — Postprozessor (`C1–C5`), Preview-Guard, STL-Export & File/Job-Service
- **Dateien:** `tools/r2_postproc.py`, `tools/r2_postproc_next.py` (strikte Byte-Parität ab Zeile 4, 30 077 Zeilen), `tools/r2_job_service.py`, `tools/test_postproc_c1_c5_and_jobs.py`, `analyse/golden_seq_expected.json`, `analyse/golden_baseline.py`, `analyse/test_golden_baseline.py`
- **Änderungen:**
  - **4a (`_preview_dup_skip`):** Kein Überspringen eines Re-Peeks, wenn `_PREVIEW.total_layers > 0`, aber `_STATE.total_layers <= 0` (z. B. nach `_LIVE_RESET`).
  - **4b (`_GeomScan`):** Vollständige Klipper-Modalbehandlung (`G90`/`G91`, `M82`/`M83`, `eff_erel = e_rel or xyz_rel`, kommentarbereinigt), `G92 X/Y/Z/E`, `math.isfinite` und `last_extruding`.
  - **4c (`_stl_export`):** `_kinds214` zählt nur bei nachgewiesener positiver XY-Extrusion (reine Tag-Dateien ohne Extrusion schlagen kontrolliert fehl); `G90`/`G91` + Klipper-E-Relativregel + `G92` + Endlichkeitsprüfung; Verwerfen degenerierter Nullflächen-Dreiecke; atomare `mkstemp`/`fsync`/`os.replace`-Schreibung mit garantiertem Aufräumen bei Fehlern.
  - **4d (`C4` Vokabular & Nicht-Druck-Annotationen):** Doppelten Schlüssel `'wipe wall'` in `TYPE_MAP` beseitigt (AST-geprüft: 0 Duplikate, eindeutig `PRIME-TOWER`); verifizierte Cross-Slicer-Aliase ergänzt (`Gaps in walls`, `Crown Path`, `Top/Bottom Solid Fill`, `Perimeter Path`, `Hole`, `HShell`, `Pillar Path`, `Prime Pillar Path`, `Wipe pillar`, `Flush`, `None`, `Other`); Nicht-Druck-Marker (`Seams`, `Destring/Wipe/Jump Path`, `Combing travel`, `Retraction`, `Unretraction`, `Deretract`, `Non-print move`, `ToolChanges`, `ColorChanges`, `Custom G-code`) bleiben in `TYPE_RE` inert und fallen in `_canon_type()` auf `TRAVEL`; Rangfolge in `_canon_type()` geschärft (`flush`/Wipe-Pillar -> `PRIME-TOWER`, `gap`/`crown` vor `wall`, einseitiges `top/bottom solid` vor `shell`/`solid`).
  - **4e (`C2`/`C3` Sequenz- & Einheitenlogik):** `_sequence_audit193` arbeitet pro sequentieller Druckeinheit (`unit_id`), erlaubt durchgehend bettverankerte mehrlagige Brims (`1..k`, `k <= 12`), erkennt weiterhin `S1`–`S4` pro Einheit und ergänzt `S5 stacked unenclosed top surface` (ohne Fehlalarm bei umwandeten Multi-Top-Deckschichten). `process()` trennt sequentielle By-Object-Neustarts am Bett sauber von 3D-/Non-Planar-Z-Bewegungen innerhalb einer Schicht und klassifiziert Cura-`;TYPE:SKIN` metamorph identisch mit und ohne `;LAYER:`-Kommentare (`layer_comment_probe.py`).
  - **Dokumentierte Golden-Delta (`analyse/golden_seq_expected.json`):** `analyse/golden_baseline.json`, `analyse/golden_zscan_expected.json`, `backups/` und `testfixtures/` bleiben bit-identisch unverändert. Auf `rose_215c_pla.gcode.gz` entfällt ausschließlich das falsche `' SEQWARN=1'` (exakt −10 Bytes: `5 156 482 -> 5 156 472`, SHA-256 `a0d1eb21bbd47c648de465d68d101f11f95d8b3425b5e72a0e6e70fd049639fe`) für den Brim der zweiten sequentiellen Rose bei `Z=0.2`; alle übrigen 5 Golden-Fälle (`m83_comments`, `m82_zhop`, `tagged`, `bigrose`, `stringart`) sind byte-identisch.
  - **4f (`C1`/`C5` Vollstrom-Tag-vs.-Geometrie-Audit):** `audit_tag_geometry()` (streaming, O(1 Schicht) RAM, ohne 5000-Move-Deckel, nicht-destruktiv) und opt-in `process(..., verify_tagged=True)` erkennen `G1_FLOATING_ADHESION`, `G2_IRONING_HIGH_FLOW`, `G3_IRONING_UNSUPPORTED`, `G4_STACKED_EXPLICIT_TOP`, `G5_UNANCHORED_BRIDGE` und `G6_OPEN_HATCH_AS_OUTER_WALL` bei **0 Fehlalarmen** auf allen drei Feld-Fixtures (`bigrose`: 1 Einheit/251 Schichten, `rose`: 2 Einheiten/242 Schichten, `stringart3d`: 1 Einheit/15 Schichten) sowie auf R2-Generatoren (`labels`, `frame`, `bridge`).
  - **4g (`tools/r2_job_service.py`):** Nicht-destruktives `OriginalArchive` (`.r2_originals/` mit SHA-256-Manifest, atomarem `fsync`, Erst-Original-Bewahrung, `restore()`, `verify()`, Symlink-/Traversal-Abwehr und striktem Bildschutz), `validate_job_output()` (Binär-STL-Layout/Endlichkeit/Nullflächen, G-Code NUL/`NaN`/`Inf`-Freiheit, `EXCLUDE_OBJECT`-Balance) und thread-sichere `JobRegistry` (`queued -> running -> validating -> succeeded | failed | cancelled | stuck`) inkl. Einbindung in `process(..., preserve_original=...)` und `_job_worker`/`_spawn_job`.

### Paket 5 — Shadow-Interpreter, Pass 3–10 Evidenz-Pipeline & Offline-Audit
- **Dateien:** `tools/r2_shadow.py`, `tools/r2_analysis.py`, `tools/r2_offline.py`, `tools/test_shadow_analysis_audit_v2.py`
- **Änderungen:**
  - `r2_shadow.py`: strikt rückwärtskompatible Fail-Closed-Defaults; opt-in G17-XY-`G2`/`G3`-Bogenmodell (`--enable-arcs`) mit exakter Bogenlänge, Helix-Z, kardinalen Bounding-Box-Extrema, Klipper-E-Relativregel und Fail-Closed bei `G18`/`G19`, `R`-Bögen, Nullradius oder Radiusabweichung; `M84`/`M18` (partielle/volle Achsen-Invalidierung inkl. Flag-Syntax `M84 X`); erweiterte passive G/M-Codes (`M73`, `M105`, `M201`, `M203`, `M205`, `M572`, `M900` u. a.); explizit ausgewiesene opt-in Flags `--firmware-retract`, `--klipper-passive`, `--verified-r2-passive`.
  - `r2_analysis.py`: Schema `r2-evidence/1` vollständig abwärtskompatibel erhalten und um speicherbeschränkte Pass-3–10-Auswertungen erweitert: `units_and_layers` (sequentielle Einheiten, physische Extrusionsschichten, Z-Hop-Zählung ohne falsche Schichten, Vase-/Spiral- und Non-Planar-Erkennung), `kinematics` (Linear-/Bogen-/Travel-/Retract-/Geschwindigkeits-/Volumenstrom-Kennzahlen), `object_footprints` (exakte Extrusions-BBox inkl. Bogen-Ausbauchung), `topology_2d` (orientierte geschlossene Außen-/Innenkonturen, parallele offene Schraffuren), `support_3d` (vertikale Rasterabstützung) und `sequence_and_tag_audit` (`S1`–`S5` + `G1`–`G6`).
  - `r2_offline.py`: neuer nicht-destruktiver Modus `audit` (Snapshot-Prüfung, atomarer Hardlink ohne Überschreiben, kombinierte Shadow-/Pass-3–10-/Vollstrom-Tag-Geometrie-Prüfung und optionaler `--machine-config`-Abgleich); alle Analyse-Optionen bleiben für `derive` gesperrt und werden in `trace_options` transparent protokolliert.

### Paket 6 — Read-Only Maschinenprofil & Konfigurationsprüfer
- **Dateien:** `tools/r2_machine.py`, `tools/test_r2_machine.py`
- **Änderungen:**
  - Rein lesender Klipper-Config-Parser (`r2-machine-profile/1`) mit Root-gebundener `[include ...]`-Auflösung (Abwehr von Pfad-Traversal, Symlinks, Zyklen und Größenüberschreitung) sowie `#*# SAVE_CONFIG`-Herkunftsnachweis.
  - Statische Konfigurationsdiagnose (Achsenbereiche, Probe-Offset-korrigierte `bed_mesh`-Düsenreichweite, Düsen-/Filamentdurchmesser, Temperaturgrenzen, `[z_tilt]` ohne `[stepper_z1]`, R2-Studio-Pflichtsektionen).
  - `check_evidence_against_profile()` (`r2-machine-check/1`) prüft Extrusions-Footprints (inkl. Bogen-Extrema) gegen Bauraumgrenzen, `[gcode_arcs]`, `[firmware_retraction]`, `[exclude_object]`, Filamentdurchmesser und `max_velocity`.

### Paket 7 — Abnahme-Skript & Gesamtverifikation
- **Dateien:** `tools/run_review_checks.sh`, `analyse/testprotokolle/weiterarbeit_checks.log`, `analyse/UMSETZUNG-WEITERARBEIT.md`
- **Ergebnisse (alle Läufe seriell, 0 Fehler):**
  - `bash tools/run_review_checks.sh`: **PASS** (inkl. SHA-256-Prüfung von `backups/SHA256SUMS` und `analyse/klipper-referenz/gcode.py`, `py_compile` aller Kernmodule, Byte-Parität `r2_postproc.py`/`r2_postproc_next.py`, 7 Dual-Engine-Suiten × 2 Engines, 9 Einzel-/Gegenmutations-Suiten, Golden-Baseline auf `stable` & `next`, `r81` 23/23, `v1_range` 8/8, `r110` 13/13 Familien & 46/46 Features, `r190` 36/36, `r225` 24/24, `r229` 46/46, `r230` 46/46, `r165`, `r166` 2736 Sektionen/409 Templates, `r218` 26/26, `r255` 19/19, `r257` 17/17 + 8/8 Mutationen, `git diff --check`).
  - `python3 tools/r197_gen_sweep.py`: **472/472 PASS, 0 FAIL**.
  - `python3 tools/megatest.py`: **0 FAIL** (alle Generator-/Tool-/Cake-Läufe grün).
  - `python3 tools/macro_render_test.py`: **2100/2100 PASS, 0 FAIL**.

---

## 2. Unangetastete Sperrbereiche & offene Punkte

- **Unverändert (0 Diff-Zeilen):** `tools/r2_texture.py` (`G1–G5`, `D2`, `D7d`), `GENERATORS_TOOLS.pdf`, `TEXTURING.pdf`, `analyse/golden_baseline.json`, `analyse/golden_zscan_expected.json`, `backups/*`, `testfixtures/*`.
- **Bewusst offen für spätere Hardware-/Design-Entscheidung:** `D1`, `H3`, `E4` (`position_min` / reale Maschinengrenzen), Live-Abnahme auf Zielhardware (Pi Zero 2 W / Klipper / Moonraker / Display / Probe / Endstops).

## 3. Reproduzierbarer Prüflauf

```bash
bash tools/run_review_checks.sh
python3 tools/r197_gen_sweep.py
python3 tools/megatest.py
python3 tools/macro_render_test.py
```
