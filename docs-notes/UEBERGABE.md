# ÜBERGABE — Stand, Regeln, offene Arbeit

**Diese Datei ist für den nächsten Agenten (oder mich nach einem Chatwechsel).**
Wer sie liest, weiß, wo die Arbeit steht, was der User verlangt hat und was
tabu ist. Alles andere steht im Code; diese Datei ersetzt kein Lesen, sie
verhindert nur, dass jemand von vorn anfängt.

Stand dieses Abgleichs: `origin/main` **`0535848`** (Merge PR #18, 18.11.2026, Release **`R2-2026-11-18.1` / `V2`**). Neuer Stand auf diesem Branch: **`R2-2026-11-18.2` / `V3`** — Release `klipper-e3-r2d2-UPDATE-R2-2026-11-18.2.zip` wird aus diesem Branch gebaut (SHA256 siehe `releases/…zip.sha256` und dem PR dieses Branches `arena/4ea70100-onmachinedesignstudio`, nur getrackte Dateien, `analyse/` ausgeschlossen). Belege und Explizit-nicht-behauptet-Liste: `docs/RELEASE_R2-2026-11-18.2_REPORT.md`.

**Aktualisierung 18.11.2026 (Branch `arena/4ea70100-onmachinedesignstudio`):**
Der Nutzer kann das Release gerade NICHT am Drucker testen — statt Stillstand: der angekündigte **Gesamtumbau anhand des Masterkonzepts** wurde als analysierender Teil fertiggestellt. Neu: `tools/gcode_re.py` (Unified Pass-0-11-Pipeline, Schema `r2-re/2`): Pass 0–2 über den verifizierten Shadow-Parser (fail-closed), Pass 3–10 über den Tracker, neu **echte Vektor-Pass-6-Geometrie** (Z-Ebenen-Buckets mit 0,05-mm-Clustering, endpoint-tolerante **Online-Loop-Extraktion** — Ringe werden mitten in der Kette emittiert, sodass Abzweigungen an Verbindungsstellen den Ring nicht zerreißen — Shoelace-Fläche, Verschachtelungstiefe per Ray-Cast-Point-in-Polygon, Open-Hatch-Richtungsstatistik + Median-Gap-Spacing) und **Pass-8 Feature Scoring v2** (Top-3-Hypothesen, explizites UNKNOWN/AMBIGUOUS, `calibrated: false`, gewichte aus einer dokumentierten Tabelle, nie Wahrscheinlichkeiten). Pass 10 Konservations-Audit (Zeilenzählung, Extrusionsfilament Shadow↔Tracker) und Pass 11 atomares Sidecar (existierendes Ziel wird ohne `--force` verweigert, Quelle read-only, SHA-256 im Provenance-Block). `tools/test_gcode_re.py` 10/10. Am 5-MB-OrcaSlicer-Fixture `rose_215c_pla` verifiziert: 156 948 Zeilen → 156 948 Records, Shadow↔Tracker-Extrusionsverhältnis **1,0**, 480 Ringe, ~25 s. Kein Eingriff in den Druckpfad; keine Hardware-/Feldabnahme behauptet. Dazu: `docs-notes/PRINTER-CFG-AUDIT-2026-11-18.md` (E1/E4-Analyse der hochgeladenen `printer.cfg` — Vorschläge, NICHT angewendet) und lokale Ablage der hochgeladenen Quelldokumente unter `analyse/uebergabe-quellen/` (SHA-256-geprüft gegen das Manifest). Gates und Report: siehe Release-Bericht.

**Aktualisierung 18.11.2026 (Branch `arena/fa800e48-onmachinedesignstudio`):**
PR #17 (R258 Option B, Kommentarzeilen-unabhängige TOTAL_LAYERS-Physik, marker-byte-stabil) wurde nach grüner CI gemerged (`ce0015a`); der Release `R2-2026-11-18.1`/`V2` wurde daraus gebaut — Versionsstempel in Code/Makro/Web/PDF, r81-Re-Freeze (mr01–13 stamp-only, A/B-bewiesen; pr03/pr08 je 1 Zeile), `golden_r258_expected.json`, Makro 2103/2103, review_checks PASS, r199 ZIP 12/12, SHA256 im Release-Bericht. Offene Feldabnahme: Layer-Anzeige auf dem Drucker nach dem Update. Frühere abgeschlossene Arbeiten unverändert dokumentiert in den Folgeabschnitten.

**Aktualisierung 17.11.2026 (späte Fortsetzung, Branch `arena/dd5058ac-onmachinedesignstudio`):**
Auf diesem HEAD liefen auf dem synchronisierten Basis-Commit seriell: `tools/run_review_checks.sh` **PASS** (`analyse/testprotokolle/review_checks_dd5058ac_baseline_20261117.log`) und `tools/macro_render_test.py` **2103/2103 PASS** (`analyse/testprotokolle/macro_render_dd5058ac_baseline_20261117.log`). Neu: Pass-11-Sidecar-Writer `tools/r2_sidecar.py` (Schema `r2-sidecar/1`, nicht-destruktiv, `tools/test_r2_sidecar.py` 9/9) und Zeilen-Crosswalk `analyse/STARTBRIEFING-CROSSWALK.tsv` (521/521 Zeilen, geerbte Disposition, nicht einzeln verifiziert). Details: `analyse/STARTBRIEFING-CROSSWALK.md`.

**GitHub (Quelle der Wahrheit):** `https://github.com/Raz-666/onMachineDesignStudio`, Branch `main`. Diese Sitzung arbeitet ausschließlich auf ihrem Arena-Branch; nicht direkt nach `main` pushen und den Branch nicht umbenennen. Diese Übergabe und die Release-Gap-Matrix enthalten noch lokale Änderungen, bis der zugehörige PR gemerged ist.

---

## 1. Wo die Arbeit steht

### Fertig und belegt

| Was | Beleg |
|---|---|
| V1 = `R2-2026-11-13.1` | `macros/01_state.cfg` Z. 535, `tools/r2_postproc*.py` Z. 80/81 |
| Makro-Batterie | `fab29dc`: **2103/2103 PASS** (sauberer Worktree, `analyse/testprotokolle/macro_render_main_fab29dc_20261117.log`); auf `846b1e7` erneut **2103/2103 PASS** (`analyse/testprotokolle/macro_render_dd5058ac_baseline_20261117.log`). Historisch: 2102/2102 im Textur-Branch; der Lauf auf `8ea17fc` brach in R175d ab — überholt durch die beiden grünen Läufe. |
| Einzeltests | `r81` 23/23 · `r199` 42/0 · `r257` 15/0 + 7/7 · `v1_range_cause_check` 8/0 |
| Historische Auslieferung V1 | Übergabebericht referenziert `releases/klipper-e3-r2d2-UPDATE-R2-2026-11-13.1.zip` (5 782 002 B, md5 `a63f9842d411834b9fe53a2588387983`); dieses ZIP ist kein neuer Build aus `8ea17fc` und im aktuellen Git-Tree nicht enthalten. |
| PDF-Fundament | `tools/r2_pdf_kit.py` (ein Stilsatz, `Doc` mit Versionskopf, `TBL/BOX/FORMULA/IMG`, `toolpath_fig/bar_fig/ladder_fig` aus echten Daten) |
| Dokument 2 | `KALIBRIERUNG.pdf` (14 S.) ← `tools/make_calibration_pdf.py` |
| Dokument 3 | `PREPRINT_LIVETUNING.pdf` (22 S.) ← `tools/make_preprint_pdf.py` |
| Dokument 4 | `POSTPROCESSING.pdf` (15 S.) ← `tools/make_postproc_pdf.py` |
| Messkörper | `tools/samples/make_statprobe.py` → `statprobe.gcode` → echter Lauf → `statprobe_tagged.gcode` (104 Marker, 30 Schichten, MAXRATE 7,2 mm³/s) |

### Erledigt in der Fortsetzung 17.11.2026

- **G1–G5** im Texturblock umgesetzt und offline gegengeprüft: Materialreliefs
  (inkl. BARK/PLANKS/BRICKS/HONEYCOMB), 0°-Tilt-Standard mit LCD-Opt-in,
  27 eindeutige Muster-Presets, 1.5-mm-BUMPS-Abtastung mit E-Erhalt sowie
  Generator-Matrix **1423/1423**. Bildbelege: `docs/textur-matrix-soll.png`
  (codebasierte Simulation, kein Druckbild) und `tools/r238_field_check.py`.
- **D2** Textur-PDF neu gebaut: `TEXTURING.pdf`, 35 Seiten, 27 Muster +
  27 zugeordnete Presets.
- **C1–C5, H2** bereits in Paket 4/V1 umgesetzt; Checkboxen und Belege in
  `docs-notes/MASTER-TODO.md` synchronisiert.

### Erledigt in der späten Fortsetzung 17.11.2026 (Branch `arena/dd5058ac-onmachinedesignstudio`, Basis `846b1e7`)

- **Pass 11 Sidecar**: `tools/r2_sidecar.py` schreibt ein `r2-sidecar/1`-Dokument
  (Herkunft: Source-SHA-256, Tool/Version aus dem Code, Trace-Optionen, volles
  Pass-3–10-Evidenz, optional pro Move/Arc-Records mit `--moves`, Cap +
  Truncation-Flag, `payload_sha256` über alle übrigen Felder). Quelle bleibt
  byte-identisch; Veröffentlichung atomar, ohne Überschreiben;
  `verify_sidecar()` erkennt Manipulation. `tools/test_r2_sidecar.py` 9/9;
  in `tools/run_review_checks.sh` eingebunden. Gap aus
  `analyse/RELEASE-GAP-MATRIX.md` („Pass 11 Ausgabe“ / kein einheitliches
  Move-/Objekt-/Evidenz-JSON) damit offline geschlossen — **kein**
  Druckbeleg, keine Release-Freigabe.
- **521-Zeilen-Crosswalk**: `analyse/STARTBRIEFING-CROSSWALK.tsv` (mit
  `analyse/crosswalk_disposition.py` regenerierbar); jede Zeile geerbt
  disponiert, alle 521 Zeilen abgedeckt, keine Lücken, keine
  Einzelverifikation behauptet. Details/Grenzen: `analyse/STARTBRIEFING-CROSSWALK.md`.
- `tools/r2_offline.py`: optionaler `move_sink`-Parameter (rückwärtskompatibel;
  Default unverändert), treibt den Sidecar-Move-Export.
- Gates auf dieser Basis: Review-Checks **PASS**, Makro-Batterie **2103/2103**.

### Offen

1. **Release-Gap-Matrix / Anforderungsabgleich:** `analyse/RELEASE-GAP-MATRIX.md`
   ist die aktuelle Übersicht. Der 521-Zeilen-`STARTBRIEFING-QUELLENINDEX.tsv`
   hat jetzt je Zeile eine geerbte Disposition in `analyse/STARTBRIEFING-CROSSWALK.tsv`
   (Vorsortierung, ausdrücklich **nicht** einzeln verifiziert, Lücken: keine).
   Für ein Release bleiben Einzelzuordnung, Belege und Entscheidungen offen;
   der Makro-Volltest ist auf `fab29dc` und auf `846b1e7` grün protokolliert.
2. **D7d `GENERATORS_TOOLS.pdf`**: veraltetes Heft (12 S., Stand `.142j`),
   Modifier einzeln dokumentieren. Texturgrundlage ist aktualisiert; das Heft
   selbst ist separat offen.
3. **D3–D6**: weitere Generator-/Modifikator-/Kreativ-Dokumente laut
   `MASTER-TODO.md`.
4. **E1/E4 und Hardware:** neue Feldbelege/aktuelle Maschinenkonfiguration,
   Achsgrenzen-/Probe-/MCU-Abnahme; Offline-Guards sind keine Hardwarefreigabe.
5. **D1:** Code-Abgleich erledigt; Entscheidung zur LIVE-Lüfterstufe laut
   MASTER-TODO offen.
6. **H3 / G1–G5:** funktional auf `main` offline umgesetzt, aber nicht gedruckt;
   die historischen Berichte unten sind datiert und nicht als aktueller
   Aufgabenstatus zu lesen.

---

## 2. Was der User verlangt hat — die Regeln, die gelten

**Anrede immer „du"** — „Sie" wird abgelehnt.

**Nummerierung:** `R2-<Datum>.<Zähler>`, Build-Tags `V1`, `V2` … —
**keine `.142x`-Buchstaben mehr**.

**Beweise statt Behauptungen:**
- Keine Behauptung ohne belegten Test. „Alles grün" ohne echten Lauf ist verboten.
- Tests brauchen einen Fixpunkt (Mutations-Gegentest).
- Bilder und Zahlen in Doku/PDF aus **echten** Code-Läufen — keine Fantasie-Grafiken.
- Feldbeobachtungen des Users nie ohne Beweis abweisen.
- Doku gegen den Code prüfen; bei Abweichung **melden**.

**Nichts zerstören:**
- Beim Fixen dürfen Homing, Probe-Fenster, Purge-Linie, Start/Ende und das
  Verlassen des Menüs nicht kaputtgehen.
- Der laufende Postprozessor wird **nicht direkt umgebaut**: Änderung in
  `tools/r2_postproc_next.py` (byte-gleich bis auf 3 Kopfzeilen), Test, dann
  Tausch. UART nicht antasten. Fixes minimal-invasiv.
- Beim Aufräumen nichts verlieren — auch keine offenen früheren Aufgaben.

**Arbeitsweise:**
- Ergebnisse statt Erklärungen. Keine Selbstanklage, kein „Honig ums Maul".
- Mängellisten sind **kein** automatisches Go — bei Unklarheit vorher fragen.
- Anweisungen **wörtlich** befolgen; das Gegenteil der Anweisung ist ein Fehler.
- Einmal zugesagte Features dürfen nicht stillschweigend verschwinden.
- Quality-Fix ≠ Speed-Fix (Quality: Oberflächen/Außenwände nie kreuzen, dort
  Z-Hop **und** Retract; Speed: Travels direkt, Ironing überspringen).
- Feature-Erkennung darf nie beim ersten `APPLY_TYPE` aufhören.
- Schichtfolge-Regelwerk gilt; Brim/Skirt ab der ersten Schicht;
  Ironing-Flow muss real wirken; voller Ordnerzugriff am LCD.
- Testaufwand beim User: 1–2 Befehle, nicht mehr.

`docs-notes/MASTER-TODO.md` ist die **einzige** Aufgabenliste.

---

## 3.0 Historischer Prüfstand: warum 2100 und warum manchmal 2086

Die Zahlen in diesem Abschnitt beziehen sich auf den alten Commit `7b10170`, nicht auf `origin/main` `8ea17fc`. Für den aktuellen Teststand siehe die Tabelle oben und `analyse/RELEASE-GAP-MATRIX.md`; der letzte Makro-Volltest auf `8ea17fc` brach vor Abschluss in R175d mit einem temporären `variables.cfg.tmp`-Fehler ab.

Die Batterie hängt an drei echten Felddateien, die **nicht im Repo** liegen:
`/home/user/testfixtures/{rose_215c_pla,stringart3d_generic,bigrose_020mm}.gcode.gz`
(4,8 MB zusammen). Der Testcode sagt das selbst (Z. 2676 ff.): ohne diese
Dateien bleiben die Postprozessor-Tests der Gruppe **R56–R60** weg.

**Gemessen (nicht behauptet), dreimal dieselbe Datei `7b10170`:**

| Umgebung | Ergebnis |
|---|---|
| Repo mit `testfixtures/` | **2100/2100 passed** |
| frischer Klon **ohne** `testfixtures/` | **2086/2086 passed** |
| zwei Batterien **parallel** gestartet | 2097/2100 — die 3 Fehler sind Lock-Artefakte (`[lock] a live watcher already watches the folder`) |

Die 14 fehlenden Tests im frischen Klon sind genau:
`R56 postproc rose/stringart/bigrose/idempotent`, `R57 --once (3)`,
`R58 _FILE_INFO`, `R58b (2)`, `R59 (3)`, `R60`.
**2086 ist also kein Regressionsbefund, sondern der dokumentierte Guard.**
Wer die vollen 2100 braucht: Fixtures ins Verzeichnis legen (oder
`_FIXDIR`/`_updir` im Testcode auf den eigenen Pfad zeigen lassen).

**Zwei Regeln daraus:**
1. **Nie zwei Batterien gleichzeitig laufen lassen** — der Postprozessor-Lock
   lässt R56/R57 fehlschlagen und man hält es für einen Codefehler.
2. Nach jedem Lauf prüfen, welche Zahl kam, und **die Umgebung mitnennen**:
   „2100/2100 (mit Fixtures)" bzw. „2086/2086 (frischer Klon)".

## 3. Wie man die PDFs baut

```bash
pip install reportlab pypdf          # pypdf nur fuers Inhaltsverzeichnis
python3 tools/make_calibration_pdf.py     # -> KALIBRIERUNG.pdf
python3 tools/make_preprint_pdf.py        # -> PREPRINT_LIVETUNING.pdf
python3 tools/make_postproc_pdf.py        # -> POSTPROCESSING.pdf
```
Jeder Bauer rendert **zweimal**: erst mit Platzhalter-Seiten im Inhalt, dann
werden die echten Seitenzahlen aus dem PDF zurückgelesen und neu gesetzt.

Messkörper für echte Zahlen (nicht schätzen):
```bash
python3 tools/samples/make_statprobe.py
python3 tools/r2_postproc.py --watch tools/samples --once
```

Kit-Fallen, die schon zugeschlagen haben:
- `Doc.render()` heißt **nicht** `build()` — `build` ist bei `BaseDocTemplate` belegt.
- `TBL()` und `FORMULA()` geben **Listen** zurück (`story += TBL(...)`),
  `BOX()` gibt ein **Table** zurück (`story.append(BOX(...))`).
- Formel-Zeichen: kein `Ṽ` (kombinierende Tilde verschwindet im PDF) → `Q`.
- `toolpath_fig(..., bed=None)` zoomt selbst auf den Fahrweg; mit festem Bett
  war ein 40-mm-Teil ein Briefmarken-Fleck.

---

## 4. Feldbeweise und Archive (außerhalb des Repos, im Workspace)

| Weg | Inhalt |
|---|---|
| `uploads/FELDBEWEISE-2026-11-12.tar.xz` (9,3 MB) | R2-DOCTOR-Pakete, `LampOpenE27.gcode`, **Cake-Cut-Hälfte = Beweis der Range-Ursache**, STL-Fall, Verzeichnisliste, MCU-PDF |
| `uploads/klippy.log.txt.gz` | der Feld-Log |
| `releases/ALT-PAKETE-bis-142l.tar.xz` | die Zips .142i/.142j/.142k |
| `releases/*.zip` | .142l und V1 (UPDATE-Pakete) |
| `releases/RELEASE-REPORT-*.md` | Release-Berichte |
| `analyse/`, `work/`, `testfixtures/` | Auswertungen, Logs/STL, Testdateien |

**Range-Ursache (belegt):** die Cut-Hälfte hat **5** `LAYER_MARK`, Z bis
**116,5 mm**, der Kopf behauptet `TOTAL_LAYERS=700`. Regel: nur bei
`cake cut`-Header **und** `claim > 4 × marker` ablehnen; Spiral-Vase bleibt erlaubt.

---

## 5. Wichtig: Workspace-Größe (ein echter Vorfall, 29.08.)

Der Workspace-Snapshot ist auf **~128 MB** begrenzt. War er größer, kam beim
nächsten Turn ein **älterer/partieller Stand zurück** — `.git` fiel auf `a8217a0`
(R253) zurück, obwohl die Arbeitsdateien aktuell waren. Reparatur war möglich,
weil das Git-Bundle den Commit `d417be4` enthielt (`git fetch <bundle>` und
dann `git reset --hard`).

**Konsequenz für jede Sitzung:**
1. Workspace klein halten (`du -sh --apparent-size /home/user`, Ziel < 110 MB).
   Ein 37-MB-Bundle **plus** ein 47-MB-Repo sprengt die Grenze schon.
2. **Sicherung als Patch-Serie statt Bundle** (12 MB statt 37 MB, geprüft):
   ```bash
   cd klipper-e3-r2d2
   git format-patch --binary a8217a0..HEAD -o ../releases/patches
   ```
   Rückweg, falls `.git` zurückfällt — im Sandkasten getestet, byte-gleich:
   ```bash
   git reset --hard a8217a0 && git clean -fd
   git am --binary /home/user/releases/patches/*.patch
   git diff --stat origin/main     # muss leer sein
   ```
   Deshalb seit D1 die `.gitattributes` (`*.pdf -diff`): **ohne** sie kamen
   zwei PDFs nach `git am` nicht byte-gleich zurück — gemessen, nicht vermutet.
3. Nach dem Turn prüfen: `git log --oneline -1` muss den erwarteten Commit zeigen.
4. Große Archive als `.tar.xz`, nicht `.tar.gz`.

---

## 6. Erste Schritte für den nächsten Agenten

**Seit 2026-11-18 gilt `AGENTS.md` (Repo-Root) als der verbindliche Einstieg** —
es ersetzt diese Sektion inhaltlich und hält Aktueller Stand, Regeln,
Quellen-Hierarchie und Release-Prozess gepflegt aktuell. Diese Übergabe
und die Commit-Hashes darin (u. a. `8ea17fc`, `fab29dc`) sind datierte
Zwischenstände, kein Status. Bei Widersprüchen gilt: Code > Tests > `AGENTS.md`
> diese Übergabe.

1. `AGENTS.md` lesen, dann `git status --short --branch` und `git log --oneline -3` prüfen.
2. `docs-notes/MASTER-TODO.md` (Aufgaben) und `docs-notes/OFFENE-FRAGEN.md` (Nutzer-Entscheidungen) lesen.
3. Vor Release den vollständigen Makro-Volltest seriell auf dem finalen Release-Commit protokollieren und alle Gates darauf erneut fahren (V2/V3: 2103/2103).
4. Keine Hardware-Abnahme ohne aktuelle Konfiguration, Feldlogs und separates Nutzer-Go. Drucker war am 2026-11-18 im Umbau — Feldtests aus dem Abschnitt „G. Feld-Abnahme-Checkliste“ in `MASTER-TODO.md` erst bei Bereitschaft.
5. Bei Widersprüchen zwischen Doku und Code: Code gilt, Abweichung melden und Doku nach belegtem Stand korrigieren.
