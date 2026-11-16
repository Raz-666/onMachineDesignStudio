# ÜBERGABE — Stand, Regeln, offene Arbeit

**Diese Datei ist für den nächsten Agenten (oder mich nach einem Chatwechsel).**
Wer sie liest, weiß, wo die Arbeit steht, was der User verlangt hat und was
tabu ist. Alles andere steht im Code; diese Datei ersetzt kein Lesen, sie
verhindert nur, dass jemand von vorn anfängt.

Stand: **`dae3e1d`** + `gitattributes` · Version
**`R2-2026-11-13.1` / Build `V1`**

**GitHub (Quelle der Wahrheit):** `https://github.com/Raz-666/onMachineDesignStudio`,
Branch **`main`**. Der Klon auf GitHub steht auf `d417be4` — die drei
PDF-Hefte sind dort, diese Datei ist der nächste Commit.
Achtung: in manchen Workspaces heißt der lokale Branch `master`, auf GitHub
`main` — dann `git push origin HEAD:main` (oder vorher `git branch -m master main`).

---

## 1. Wo die Arbeit steht

### Fertig und belegt

| Was | Beleg |
|---|---|
| V1 = `R2-2026-11-13.1` | `macros/01_state.cfg` Z. 535, `tools/r2_postproc*.py` Z. 80/81 |
| Makro-Batterie | **2100/2100** (`python3 tools/macro_render_test.py`) — **nur mit den Feld-Fixtures**, siehe §3.0 |
| Einzeltests | `r81` 23/23 · `r199` 42/0 · `r257` 15/0 + 7/7 · `v1_range_cause_check` 8/0 |
| Auslieferung V1 | `releases/klipper-e3-r2d2-UPDATE-R2-2026-11-13.1.zip` (5 782 002 B, md5 `a63f9842d411834b9fe53a2588387983`) — **vom User noch nicht eingespielt** |
| PDF-Fundament | `tools/r2_pdf_kit.py` (ein Stilsatz, `Doc` mit Versionskopf, `TBL/BOX/FORMULA/IMG`, `toolpath_fig/bar_fig/ladder_fig` aus echten Daten) |
| Dokument 2 | `KALIBRIERUNG.pdf` (14 S.) ← `tools/make_calibration_pdf.py` |
| Dokument 3 | `PREPRINT_LIVETUNING.pdf` (22 S.) ← `tools/make_preprint_pdf.py` |
| Dokument 4 | `POSTPROCESSING.pdf` (15 S.) ← `tools/make_postproc_pdf.py` |
| Messkörper | `tools/samples/make_statprobe.py` → `statprobe.gcode` → echter Lauf → `statprobe_tagged.gcode` (104 Marker, 30 Schichten, MAXRATE 7,2 mm³/s) |

### Offen (in dieser Reihenfolge)

1. **Dokument 1: `GENERATORS_TOOLS.pdf` neu bauen** — jeder Modifier einzeln.
   Das alte Heft (12 S., Stand `.142j`) ist veraltet. **Wartet auf Freigabe des
   Users**, weil dort die Texturen drin sind (siehe Punkt 2).
2. **Textur-Block G1–G5** (`docs-notes/MASTER-TODO.md`, Block G) — der User hat
   ausdrücklich gesagt: **erst wenn er wieder da ist**. Befund liegt vor:
   RIDGES/FLUTED/BARK/PLANKS/FABRIC = senkrechte Streifen, WAVES/HATCH/ROPE =
   diagonal, HEX/SCALES/FACETS/MACRAME/HONEYCOMB/BRICKS = Punktgitter, GLITCH
   kaputt, `PATTERN_TILT` kippt alle Streifen; auf 1-Wand-Achteck nur 8
   Vertices/Lage. Beleg: `docs/textur-matrix-ist.png`.
3. **D2** — Textur-PDF: alte Vorschaubilder, alte Preset-Zahl (27 Presets
   müssen mit Bildern und Parametern drin sein).
4. **D1** — `MANUAL.md` gegen den CODE prüfen (nicht fortschreiben). Bei
   Abweichung **melden**, nicht stillschweigend die Doku anpassen.
5. **E4** — Crash/MCU-Shutdown (Block E); E3 ist erledigt.
6. **H2/H3** — Range/Cake-Rest (H1 ist erledigt, Ursache belegt).

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

## 3.0 Prüfstand: warum 2100 und warum manchmal 2086

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

1. `git log --oneline -3 && git status --short` — steht `7b10170` (oder
   `d417be4` + diese Datei) oben? Ist der Baum sauber?
2. `docs-notes/MASTER-TODO.md` lesen (einzige Aufgabenliste, Blöcke A–H).
3. `python3 tools/macro_render_test.py` einmal laufen lassen (dauert ~8 min,
   muss **2100/2100** sagen).
4. **Nichts anfangen, was auf die Freigabe des Users wartet** (Texturen G1–G5,
   GENERATORS_TOOLS-Rückteil mit Texturen).
5. Bei Widersprüchen zwischen Doku und Code: Code gilt, Abweichung melden.
