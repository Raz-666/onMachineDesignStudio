# AGENTS.md — Einstieg für Coding-Agenten (Codex, Claude, …)

Dieses Repo ist das **R2-D2 Ender-3 Klipper-Makrosystem** des Nutzers
(Modded Ender-3: SKR Mini E3 V3.0, Linear Rails, Dual-Z parallel, 5 NeoPixel,
BMG Direct Drive, MicroProbe, 12864-LCD, Mainsail). Sprache des Projekts ist
**Deutsch** (Doku, Menüs, Meldungen) – Antworten an den Nutzer auf Deutsch,
du-Anrede, technisch präzise, ohne Fülltext.

**Wenn der Nutzer „mach einfach weiter" sagt:** lies der Reihe nach
1. zuerst dieses Dokument (Aktueller Stand, Regeln),
2. `git status --short --branch` + `git log --oneline -3`,
3. `docs-notes/MASTER-TODO.md` (die **einzige** Aufgabenliste),
4. `docs-notes/OFFENE-FRAGEN.md` (Entscheidungen, die auf den Nutzer warten),
5. `docs-notes/UEBERGABE.md` §6 (Erste Schritte).

---

## Aktueller Stand (2026-11-25)

- Release-Stand: **V7 (`R2-2026-11-19.3`, Build `R285`)** — gemergt auf `main`
  über **PR #26** (Merge-Commit `0772a15`). Inhalt dieser Runde: Setup-Retry-Pfad
  (R284), Toolchain-Jobliste als LCD-State (R285, kein Preset-File mehr), Feldreport
  17.11. (Textur-Label, Vase-E, Brick-Öffnungen, R286–R288), Brick-Katalog-Wachstum
  auf **90 Codes** (Baseplates BP, Gears G12–G40, Achsen AX2/AX4/AX6/AH2x2, Dome D2x2,
  R289) und vertikale Standing-Molds mit Auto-Split (R290). Engine = volle
  `r2_postproc.py` R2.85; `r2_postproc_next.py` ist die experimentelle Kopie mit
  R252-Handover. Checks dieser Runde: `r288_brick_openings_check.py`,
  `r289_brick_families_check.py`, `r290_vsplit_check.py`; macro_render 2141/2141,
  r81 23/23 (V7-Re-Freeze, A/B bewiesen), r276–279 22/22/25/25/25, r234 38/0.
- Vorgänger-Stand: **V6 (`R2-2026-11-19.2`)** (PR #22 → `main`): Gießformen-Generator **J2** (R270–R273), Fremddrucker-Audit **J7** (R274), M82-Bogen-Extrusionsfix in `Twist`/`Mirror` (R276), **Sektion D komplett** (alle 13/13 D3-Generator-PDFs + alle 7/7 D4-Modifikator-PDFs = 28 Root-PDFs, R275–R279) sowie **Gesamtbriefing-Abgleich §§ 20–28** (`analyse/GESAMTBRIEFING-ABGLEICH-20-28.md`, R280).
- Release-Historie: V1 `R2-2026-11-13.1` → V2 `R2-2026-11-18.1` → V3 `R2-2026-11-18.2` → V4 `R2-2026-11-18.3` → V5 `R2-2026-11-19.1` → V6 `R2-2026-11-19.2` → **V7 `R2-2026-11-19.3`**.
  Das finale V7-ZIP liegt nach Merge in `releases/` (gitignored) mit `.sha256`-Sidecar (aus `origin/main` ohne `analyse/` gebaut und per `r199_zip_check.py` geprüft).
- Der **Drucker ist im Umbau** — keine Hardware-Tests, keine Feldabnahme,
  keine `printer.cfg`-Änderungen ohne explizites Go + Test-Fenster.
  Die dafür gesammelte **Feld-Abnahme-Checkliste** steht in
  `docs-notes/MASTER-TODO.md`, Abschnitt „G. Feld-Abnahme-Checkliste".
- Erledigt: D5 (Creative-Freedom-PDF, Titel + Kapitel + Schlusssatz,
  Commit-Serie dieser Branch). Release-Berichte unter `docs/RELEASE_*.md`.
- **STL-Export ENTFERNT (R2.14, Nutzer-Entscheidung):** Der OBJ-Export ist
  zuverlässig (R286, gleiche Triangle-Pipeline, vertex-deduped) → der STL-Export
  wurde vollständig entfernt. `_stl_export` → `_obj_export` (OBJ-only), `STL_EXPORT`
  -Makro + `__stl`-Menü entfernt, `--stl` → `--obj`, Skip-Logik erweitert auf
  `.obj.gcode`. Bestandsaufnahme bleibt in `analyse/STL-EXPORT-AUDIT.md`.
- **D1 ist freigegeben:** MANUAL.md aktuell halten; Kap. 14 ergänzt.
- **D3/D4 sind ERLEDIGT** (28/28 Root-PDFs, R275–R279 — siehe V6-Stand oben).
- **Gesamtprüfung ist beauftragt:** Punkte B/C aus dem Gespräch gegen Code,
  Tests und alle bereitgestellten Recherchen prüfen. Keine erneute Rückfrage
  zur bereits beauftragten Einzelprüfung. Noch keine Gesamt-Abnahme. Der Nutzer hat nun die Umsetzung des Gesamtumbaus
  beauftragt; schrittweise implementieren und prüfen, nicht erneut dieselbe
  Freigabe erfragen. Hardware-Grenzen bleiben bestehen.

Nach jeder größeren abgeschlossenen Arbeit: Übergabestand aktualisieren,
auf dem aktuellen Session-Branch committen und genau diesen Branch pushen.
Bestehenden PR ergänzen; nicht ohne Freigabe mergen.

## Bindende Regeln (nicht verhandelbar)

1. **Evidenz vor Behauptungen.** Jede Aussage mit Code-, Test- oder
   Log-Fundstelle. Ungeprüfte KI-Texte sind kein Beleg.
2. **`docs-notes/MASTER-TODO.md` ist die einzige Aufgabenliste.** Erledigt
   wird abgehakt + mit Commit genannt. **`OFFENE-FRAGEN.md`** listet nur,
   was auf eine Nutzer-Entscheidung wartet.
3. **Kein Hardware-Anspruch ohne Feldnachweis.** „Am Drucker getestet"
   nur, wenn der Nutzer es bestätigt hat. Sonst: „offline geprüft".
4. **Originalschutz.** Nutzer-Dateien (`printer.cfg`, Quell-G-Code) nie
   ungefragt ändern; `printer.cfg` nur Vorschläge, nie anwenden ohne Go.
5. **Paket ohne `analyse/`.** Release-ZIPs enthalten nur getrackte
   Produktdateien (`git archive`), Präfix `klipper-e3-r2d2/`. Nach einem
   Merge `git fetch origin main` + ZIP aus `origin/main` neu bauen.
   SHA256 gehört in die `.sha256`-Sidecar und den PR-Kommentar, **nicht**
   in committed Doku.
6. **Nie direkt auf `main` pushen.** Arbeit auf dem Session-Branch,
   danach PR. Merge erst nach grünem CI + Nutzer-Go (Nutzer noch nicht
   final entschieden: OFFENE-FRAGEN, Frage 8).
7. **Offline arbeiten.** Keine Hardware-/Netzwerk-Kommandos gegen den
   Drucker; keine echten Geräteaktionen.
8. **Keine Fantasie-Grafiken** (D6): jede Abbildung aus echten Algorithmen/
   Parametern abgeleitet; Rechtschreibung im Bild korrekt.
9. **TESTANLEITUNG/Makros:** vor Release serielle Vollbatterie fahren
   (siehe unten) und Ergebnis mit Commit dokumentieren.

## Das ist das Projekt (Kurzkarte)

| Bereich | Inhalt |
|---|---|
| `macros/` | Klipper-Makros (01_state, 07_start_confirm, 08_print_start_stop, 10_live_tuning, 12_maintenance, 17_generator, …). `01_state.cfg` trägt `variable_version`. |
| `menus/lcd_menues.cfg` | Das LCD-Menü (Pre-Print, Live Tuning, Generators, Maintenance, System). GENERATORS_TOOLS.pdf liest die Zeilen daraus. |
| `web/` | WebUI-Komponente (r2_menu.py etc.). |
| `tools/` | ~130 Python-Module: Generator-/Postprozessor-Engine (`r2_postproc.py`, Kernfunktion `process`), RE-Analyse (`gcode_re.py`), Tests (`test_*.py`, `r*.py`-Checks), PDF-Builder (`make_*_pdf.py`). |
| `tools/r2_postproc_next.py` | Eingefrorene Vorgängerversion (byte-gleich zur Stable beim Kopieren); Guard-Tests. |
| `presets/toolchain/` | Beispiel-Toolchain-Presets (R259): der Watcher seedy `scale-twist.json` beim ersten Start in den Gcodes-`Toolchain/`-Ordner; Nutzer-Presets sind gewöhnliche JSON-Dateien (SD-Browser-Pick). |
| `testfixtures/` | `.gcode.gz`-Fixtures: `rose_215c_pla` (5 MB Orca), `bigrose_020mm`, `stringart3d_generic`. Golden Master. |
| `slicer/` | CURA/ORCA Feature-Listen + Parser (Referenz für Feature-Tags). |
| `docs/` | Freigabedokumente: RELEASE_*_REPORT, TOOLS_INVENTORY, FEATURE_TAGGING.md, SHUTDOWN_REGISTER, LCD_MENU_PORTABILITY, WEBUI_MOONRAKER, STRINGART_DESIGN, frame_design. |
| `docs-notes/` | Internes: MASTER-TODO, OFFENE-FRAGEN, UEBERGABE, PRINTER-CFG-AUDIT, MANUAL-CODE-ABGLEICH. |
| `analyse/` | **137 git-getrackte** Dateien: Abgleich/Crosswalk/Disposition, TSVs, Evidence-Logs, Probe-Scripts. **Im Release-ZIP bewusst NICHT enthalten** (Paket ohne analyse/). Bleibt für Agenten im Repo verfügbar. |
| `analyse/uebergabe-quellen/` | Bereitgestellte Quelldokumente und SHA256SUMS sind getrackt und stehen nach einem Clone zur Verfügung. |
| `backups/` | `r2_postproc_R2-2026-11-13.1_V1.py` (Notfall-Referenz) + SHA256SUMS. |
| `printer.cfg.example` | Vorlage; die echte `printer.cfg` ist ein Nutzerartefakt (Felddatei). |
| `releases/` | Nur lokale Artefakte (gitignored): finale Update-ZIPs + `.sha256`. |
| Root-PDFs | Geshipped Docs (MANUAL, FEATURE_TAGGING, TEXTURING, GENERATORS_TOOLS, CUTSPLIT, CREATIVE_POSSIBILITIES, …). |

## Quellen-Hierarchie (geklärt mit dem Nutzer, 2026-11-18)

Maßgeblich ist **`R2-D2 – Gesamtbriefing für die Coding-GPT.md`**
(im Repository unter `analyse/uebergabe-quellen/`).

| Datei | Rolle |
|---|---|
| Gesamtbriefing (Coding-GPT) | **Maßgeblich.** Enthält alle Ergänzungen 20–31 (Toolchain, Ausgabemodi, Queue, Objektmodell, STL-Export §24, Extrusionskompensation §25, Texture-Innenwand §26, Range §27, RE-Strategie §28, Migrationsdisposition §29, Prioritäten §30). |
| `R2_Vollstaendiges_Startbriefing_Coding-KI_finalizedByGemini.txt` | Frühere Fassung desselben Dokuments (STL dort §5.21). Nur Referenz. `766a0bc…` |
| `GCode_Reverse_Engineering_Masterkonzept.md` | Der Grundgedanke (Konzept), nicht der Implementierungsplan. `c5a1400…` |
| `Reverse Engineering von G-Code Geometrien.md` | Detaildokument. `8db2965…` |
| `slicer-families.md` | Nutzer-Recherche, absichtlich umfassend (Feature-/Musterlisten + Mathematik) — **ungeprüft**, als Ideenquelle nutzen, jede Behauptung vor Verwendung verifizieren. `aa1aece…` |
| `Giessformen generieren.md` | Nutzer-Recherche (AI-Notiz) zum Gießformen-Generator — **ungeprüfte Ideenquelle** für MASTER-TODO J2 (Multi-Part-Teilung, Negativform, Parameterstruktur, direkte G-Code-Erzeugung). `ff780b3e…` |
| `KI in Klipper integrieren.md` | Nutzer-Recherche (AI-Notiz) zur 3D-KI-Brücke (HF-Spaces-API, Spracheingabe, Mainsail-navi.json) — **ungeprüfte Ideenquelle** für MASTER-TODO J6. `90907f56…` |
| `Potential performance& compatibility issues.md` | Nutzer-Analyse zu Risiken (MCU-Shutdowns, Kompatibilität, Ressourcen) — **ungeprüft**, Hinweise kein Auftrag. `9eeb66f…` |
| `my_printer.cfg.txt` | **Die echte printer.cfg des Nutzers** (SKR Mini E3 V3.0 etc.) — für Audits/Tests lesend nutzen, nie ändern ohne Go. `f3b6e3d…` |
| `GCode_Reverse_Engineering_Master_Spezifikation.md` | **Existiert nicht** (nie bereitgestellt). Nicht annehmen, nicht suchen, nicht ersetzen. |

Fehlende Quelldokumete sind im Manifest **nicht** ersetzt: SHA256SUMS listet
was vorlag; alles mit Datei im selben Ordner ist byte-geprüft.

## Release-Prozess (Kurzform)

1. Änderungen auf dem Session-Branch; serielle Gates fahren:
   `python3 tools/macro_render_test.py` (aktuell 2103/2103),
   `python3 tools/r81_golden_check.py`, `python3 tools/r199_zip_check.py <zip>`,
   `tools/r165_doc_check.py`, `tools/r166_template_check.py`,
   `tools/r142_spell_lint.py`, `tools/r197_gen_sweep.py`,
   `tools/r232_preset_audit.py` — alles grün oder nichts mergen.
2. Doku: Release-Bericht `docs/RELEASE_<version>_REPORT.md`
   (explizite **Nicht-Behauptungen** festhalten), `TOOLS_INVENTORY`,
   MASTER-TODO abhaken.
3. Commit → Push → PR (`gh pr create`) → CI abwarten (grüner Status
   erforderlich) → Merge mit Nutzer-Go.
4. **Danach** `git fetch origin main` und das finale ZIP aus `origin/main`
   neu bauen (`git archive`), r199-Check, `releases/` ablegen +
   `sha256sum` in `.sha256` schreiben + im PR-Kommentar nachreichen.
5. Fertiges ZIP mit `present_file` an den Nutzer übergeben, niemals im
   Repo committen.

## Umgebung & Werkzeuge

- Python-PDF-Toolchain: `reportlab`, `pypdf`, `Pillow`
  (ggf. `pip install --break-system-packages …`; DejaVu-Fonts unter
  `/usr/share/fonts/truetype/dejavu/`).
- PDFs neu bauen: `python3 tools/make_<name>_pdf.py` — jede PDF-Datei im
  Repo ist gebaut, nicht gemalt (D6).
- Das 5-MB-Fixture `testfixtures/rose_215c_pla.gcode.gz` ist der
  Standard-Ground-Truth für Geometrie-/RE-Arbeit.
- Keine Netzwerkzugriffe auf den Drucker; GitHub nur über `git`/`gh`.
- `releases/` und `SESSION_STATE.md` sind gitignored — keine
  Zwischenstände committen.

## Entscheidungen und nächster Einstieg

D1: Ja. Gesamtprüfung: beauftragt. Alle Uploads einschließlich RE-Recherche,
Slicer-Familien und Performance-Hinweisen berücksichtigen; Hinweise vor
Übernahme prüfen, nicht ignorieren. printer.cfg lesend für Offline-Tests erlaubt.
PDF-Ausbau zurückgestellt. Druckertests bleiben bis zur Bereitschaft gesperrt.
Nächster Arbeitsschritt: Gesamtbriefing-spezifische Anforderungen mit dem
bestehenden Abgleich zusammenführen, anschließend STL-Testlücken bearbeiten.
Die bisherige B/C-Einteilung ist vorläufig, nicht einzeln vollständig belegt.
STL-Prüfer `tools/stl_audit.py` und 5 Mesh-Tests sind implementiert;
3 vorhandene E-State-Tests bestehen ebenfalls. Zwei gestapelte Bahnen
reproduzieren doppelte Grenzflächen (2) und nichtmannigfaltige Kanten (5).
Erster neuer Oberflächenbaustein: `tools/contour_mesh.py` (gerades Prisma mit
konkaver Außenkontur und expliziten Durchgangslöchern), plus `loft_mesh` für
positive gleichförmige Skalierung und Verschiebung über mehrere Höhen;
16/16 analytische Tests. Kein Anschluss
an den aktiven Exporter. Details/Grenzen in `analyse/STL-EXPORT-AUDIT.md`.
Read-only Anbindung: `tools/gcode_contours.py` nutzt den bestehenden Shadow-Parser
für exakte geschlossene planare Bahnen samt Zeilen-/E-/Tool-Herkunft (7 Tests).
Rose-Felddatei: strikt 0 Konturen/148529 unbekannte Records; mit explizitem
`--klipper-passive` nur START_PRINT (Zeile 95) unbekannt, aber weiter 0 Konturen.
45285 nichtplanare Extrusionsbewegungen werden erkannt; 4 Bewegungen haben
noch unbekannte Koordinaten. 12 Integrationstests inklusive Rose bestanden.
Kein geratenes START_PRINT-Endergebnis: Modus/Position erholen sich nur durch
nachfolgende Dateibefehle. Parseroptionen stehen im Bericht.
Neue Bahnevidenz: `tools/path_evidence.py`, in `gcode_contours` integriert.
Rose: 708 zusammenhängende Extrusionspfade, 137975 Segmente; 480 planar,
228 nichtplanar, 336 XY-Endabstände <=0,1 mm ohne exakten 3D-Schluss.
Längste Bahn Z10,2→10,4, Zeilen 39269–39869, 601 Segmente, XY-Lücke 0,03585 mm.
5 neue Tests plus 36 bestehende lokal grün; Rose-Zahlen als Regression gesichert.
Opt-in `--seam-gap-mm` erzeugt jetzt explizite planare Nahtvorschläge:
`tools/seam_reconstruction.py`, vorhandene Punkte unverändert, nur neue
Schlusskante mit gemessener Länge. Keine Z-Projektion; kein STL.
Rose bei 0,1 mm: 55 Vorschläge, maximal 32 gespeichert; darunter Brim!
Diese Zahl ist KEINE Modell-/Exportabnahme. 6 neue Tests bestanden.
Marker-Provenienz ergänzt (`contour_context.py`): dateilokaler Objektname
und START-Zeile an Pfaden/Nahtvorschlägen; ungültige Marker löschen Zugehörigkeit.
Feature-Rollen bleiben Hinweise: Hilfsgeometrie ausgeschlossen, Außenwand
unverifiziert. Rose: 22 Hilfs-, 76 Außenwandhinweise, 610 unklassifiziert.
5 neue Tests + bisherige 57 bestanden. Keine geometrische Objektvalidierung.
Physischer Konturbaustein: `physical_contours.py` (explizite konstante Breite,
konvexe Ringe, Gehrungsecken; außen +w/2, Loch -w/2). 7 neue analytische Tests,
insgesamt 69 lokal bestanden. Konkave/variable Breiten bleiben abgelehnt.
Stadium-Breitenformel nur mit bekannten effektiven E-mm/Schichthöhe, kein Messwert.
Offline-Vorschau jetzt durchgängig: `tools/contour_preview.py` liest G-Code,
wählt explizite Vorschlagsindizes und baut ein konstantes konvexes Prisma mit
Loch, expliziter Breite/Z-Grenzen, STL-Prüfung und .stl.json-Provenienz.
Kein Überschreiben, kein automatischer Höhenbeweis, kein aktiver Exportwechsel.
6 neue Tests (inkl. kompletter G-Code→STL-Kette), insgesamt 75 lokal bestanden.
Konkave Ringe ergänzt: `offset_simple_centerline` erhält L-/U-Formen nur bei
bewahrter Topologie (Gehrungsecken, gleiche Eckorientierung, keine
Selbstdurchdringung/Umkehr). Kerben-/Armzusammenfall wird abgelehnt.
Vorschau nutzt jetzt den allgemeinen Weg; `offset_convex_centerline` bleibt.
5 neue Tests, insgesamt 80 lokal bestanden.
Mehrere Inseln/Flächen: `prism_set_preview`/`--group OUTER[:HOLE,...]` bauen
mehrere getrennte, paarweise boundingbox-disjunkte Schalen in eine STL;
Komponentenzahl muss Gruppenzahl entsprechen. Innerhalb einer Gruppe gelten
gemeinsamer Objektmarker, Ebene und Tool; zwischen Gruppen dürfen Objektnamen
abweichen (Mehrobjektdruck, wird protokolliert). 7 neue Tests, 87 gesamt.
Ebenenstapel ergänzt: `stacked_prism_preview`/`stacked_preview_from_report`
verbinden Schichten mit EXAKT identischen Outlines über lückenlos vorgegebene
Höhenbänder zu einem Prisma über Gesamthöhe (eine Schale pro Insel).
Abweichende Outlines, Lücken/Überlappung, nicht steigende Ebenen, Toolwechsel
werden abgelehnt; Provenienz jeder Schicht bleibt erhalten. 5 neue Tests,
92 gesamt lokal bestanden. Kein CLI für Stapel, keine Flächenvereinigung.
Reale Höhen-/Breitenevidenz: `plane_statistics` misst Z-Ebenenabstände pro
Objekt (Rose: 7 planare Ebenen .2→24,0, fünf 0,2-Schritte, dann Sprung 22,8 —
Vase-Modus, Spiralwände sind nichtplanar und fehlen bewusst als Ebenen).
`--assume-layer-height-mm` ergänzt Stadion-Breitenschätzungen unter expliziter
unverifizierter Annahme (Rose bei 0,2: Außenwandhinweise 0,322–0,910 mm,
Brim ~0,6, 108 unstützbare Querschnitte). 5 neue Tests, 97 gesamt.
Nichtplanare Spiralbahn: `spiral_rings.py` tastet monotone Vase-Wände mit
explizitem Pitch (Höhe je Umdrehung, Aufruferangabe) und N Proben je Umdrehung
ab; Ringe mischen Höhen innerhalb des Bandes, Sehneninterpolation, Mittellinie
ohne Breite, nie exportfertig. Anfangs falscher Ansatz (Höhenschnitt) verworfen:
eine monotone Spirale schneidet jede Höhe genau EINMAL. 6 neue Tests, 103 gesamt.
Punktretention für nichtplanare Pfade: opt-in `--retain-nonplanar-points`
behält maximal 4 längste Pfade mit je höchstens 1024 Punkten (Eviction der
kürzesten). Rose: 4 Pfade (599/599/602/602 Punkte), längster Zeilen 39269–39869
Z10,2→10,4. Erste echte Ringprobe: Pitch 0,2, 64 Proben → 1 Ring (Band bis
10,396875), 32 Proben werden als selbstschneidend abgelehnt (Untertastung).
Kein Breiten-/Mesh-Schritt. 4 neue Tests, 107 gesamt lokal bestanden.
Ring-zu-Mesh: `ring_wall.py` näht aufeinanderfolgende Ringe gleicher
Probenzahl zu einer OFFENEN Wandfläche (Vierecke je Probenpaar, Außenrichtung
normalisiert, entartete Dreiecke abgelehnt). Offen nur am ersten/letzten Ring:
erwartete 2N Randkanten, keine nichtmannigfaltigen Kanten, Richtungsungleich-
gewicht genau am Rand. Keine Deckel, keine Breite, kein Festkörper,
Selbstdurchdringung ungeprüft. 4 neue Tests, 111 gesamt lokal bestanden.
Pfadfortsetzung: `path_continuation.py` verbindet lagekontinuierliche Pfade
(exakt geteilter Punkt oder gemessene Geraden-Brücke innerhalb expliziten
Budgets; Höhe darf nie zurückkehren). Rose-Evidenz: 228 exakt fortlaufende
Paare, längster zusammenhängender Wandlauf 115 Pfade (Zeilen 13404–78198).
Erste echte Rose-Wandfläche: Fenster Zeilen 13350–15390, 5 Pfade (1 Brücke
0,0769 mm + 3 gemeinsame Punkte), Pitch 0,2, 64 Proben → 4 Ringe → vernähte
offene Wand (384 Dreiecke, 128 offene Randkanten, keine nichtmannigfaltigen
Kanten). Punktbudget spiral_rings auf 8192 (linearer Scan) angehoben.
3 neue Tests, 114 gesamt lokal bestanden. Kein Deckel/Breite/Festkörper.
Breite an Ringen: `vertex_normal_offset` (1:1-Ecknormal-Verschiebung, exakt
auf Kreisen, Eckabweichung begrenzt dokumentiert) und `wall_surfaces.py`
(Außen-/Innenfläche mit expliziter Breite; Fläche nur, wenn JEDE Ring die
Breite topologieerhaltend annimmt). Rose-Messung: bis 0,24 mm bestehen alle
4 Ringe beidseitig, ab 0,3 mm kippen Blütenkerben (0,4: außen 1/4, innen 0/4)
— die Stadion-Schätzung 0,32–0,91 mm LIEGT darüber: physikalische Breite ist
mit strenger Topologie hier NICHT anwendbar; 0,24 ist ausdrückliche Unter-
Breiten-Annahme, kein Messwert. Erste Außenfläche der Rose: 384 Dreiecke,
128 offene Randkanten, sauber. 5 neue Tests, 119 gesamt lokal bestanden.
GANZE ROSE-WAND: `wall_run.py` streamt lagekontinuierliche Wandläufe mit
gleitendem Punktpuffer (4096) in Ringe je Pitch-Band; ungültige Ringe werden
protokolliert, nicht repariert; Wandfläche nur ohne jede Ablehnung.
Rose-Komplettlauf: 115 Pfade (114 steigend + 1 flacher Rand bei Z 24,0),
62916 Punkte, 114 exakte Fügungen, 114 Ringe Z 1,2→24,0 — bei 96 Proben
VOLLE Wand: 21696 Dreiecke, 192 offene Randkanten, 0 nichtmannigfaltig,
1 Komponente. Bei 64 Proben werden 5 Bänder abgelehnt (66/68/78/82/83).
5 neue Tests, 124 gesamt lokal bestanden. Offenflächen-Mittellinie: kein
Deckel, keine Breite, kein Festkörper, Pitch unverifiziert.
GESCHLOSSENE Vase-Oberfläche: `vase_closure.py` schließt die Wand über
vertikale Projektionsstreifen (jeder Randvertex wandert NUR in Z) und
Ohr-Clipping-Deckel; Abweichung pro Deckel dokumentiert (Rose: unten
0,198 / oben 0,2 mm ≤ Pitch). Rose KOMPLETT GESCHLOSSEN: 22266 Dreiecke,
0 Randkanten, 0 nichtmannigfaltig, 0 Windungsfehler, 1 Komponente,
Volumen 4810,105 mm³. Rand-Abgleich: geflätteter Abschlussring liegt
EXAKT auf der aufgezeichneten Abschlusskontur (max. Abstand < 1e-9,
Flächendifferenz 2,59 mm² durch Sehnenabtastung). 4 neue Tests,
128 gesamt lokal bestanden. Zentrum: Mittellinie ohne Breite;
Volumen setzt nicht-selbstüberschneidende Schale voraus (ungeprüft).
Selbstschnittprüfung: `self_intersect.py` testet alle NICHT-
adjazenten Dreieckspaare (exakte Vertex-Gleichheit wie stl_audit,
Berührung zählt, koplanare Überlappung per Achsenprojektion, räumlicher
Hash mit Median-Zellgröße; input-degeneriert wird abgelehnt).
`close_vase_surface(..., check_self_intersection=True)` auditiert die
VERSCHICKTEN float32-Dreiecke und wirft bei Durchdringung. Rose-Fläche:
0 Selbstschnitte bei 22266 Dreiecken (63194 Paartests nach Pruning,
134021 adjazent übersprungen, 1,6 s) — Volumen 4810,105 mm³ ist damit
GEMESSEN, nicht angenommen. Scope: Falten durch gemeinsame Vertices
werden nicht klassifiziert. 15 neue Tests, 143 gesamt lokal bestanden.
Bead-Breite aus G-Code-Evidenz: `bead_evidence.py` —
`collect_chained_run` (EIN Kollektor, rose_run delegiert), `run_width_evidence`
(Stadium-Schätzung je Pfad), `wall_width_audit` (uniforme Breite an allen
Ringen beidseitig, Ablehnungen sind Ergebnisse). Rose-Befund: Wand = uniform
0,6 mm Einzelwand (113 Pfade 0,5998–0,6001; Bodenloop 0,3222, Randloop 0,3209;
1499,79 mm Filament = 3607,43 mm³). Bei 0,6: außen 54/114 akzeptiert,
innen 0/114 (Blütenkerben enger als der Strang). Schon bei 0,02 lehnen
Ringe 106/109/110 (außen) und 37/88 (innen) ab → KEINE uniforme Breite > 0
volllauffähig; „≤0,24 alle OK" war Fenster-Artefakt (Volllauf: außen 86/114,
innen 69/114). Physische Schale braucht besseres Modell (Miter mit
Verschmelzung/überstrichene Stadium-Fläche). 11 neue Tests, 154 gesamt.
Fremd-Datei-Härtetest (Nutzer-Uploads, älter, mit Stützen/Brim,
KEINE Spiral-Vasen): `testfixtures/{MAN_V3,Pumpkin_Scream_MULTI-011,
vwbus}.gcode.gz` (SHA256 in test_field_gcode verankert). Alle drei parsen
jetzt mit 0 Unknown-Records und vollständiger Feature-Klassifikation:
MAN_V3 = Slice Beam 0.3.0 (PrusaSlicer-Familie, ;TYPE:-Rollen; 9190 Pfade,
5333 Helper: Support 5008, Skirt/Brim 144, Ironing 179, Custom 2; erster
Startblock ohne G21 → konservativ 9 Unknowns nur dort, mit
assume_klipper_defaults vollständig). Pumpkin = Kiri:Moto 4.3.2 (setzt KEIN
G90! G28 W + G80 Marlin-Startblock; ;feature-Grammatik; 192 nichtplanare
Pfade durch Deckenrampe; 415 Helper/6664 Modell). vwbus = Kiri:Moto 4.3.1
(39243 Pfade, davon 31144 Support ≈ 79 %; 8099 Modell). Dafür: G28-Semantik
in r2_shadow korrigiert (homed nur Achsen-Koordinaten, Modi/E/Einheiten
erhalten — vorher Total-Invalidate, machte Kiri:Moto unlesbar; neuer
Record-Typ ‚home‘), FEATURE-Regex erkennt Kiri `; feature <name>`,
HELPER_HINTS += skirt/brim, ironing, custom (Rose: +108 Ironing-Helper
korrigiert, waren unclassified). Kiri `; start object id:`-Marker gefunden,
noch nicht modelliert. 10 neue Tests, 164 gesamt.
Modell-STL aus Fremd-Dateien: `model_export.py::model_shells()` —
nur Wand-Rollen-Hinweise (external/overhang perimeter, perimeter, shells)
werden Kontur; Support/Brim/Ironing/Custom/Infill/unmarkiert nie. Naht-
verschluss nur im expliziten Budget (zugefügte Kante berichtet), Inseln
per Enthaltensein, innere Wandläufe verworfen (Löcher werden NICHT
inferiert), byte-identische Layer mergen zu Prismen-Runs, eine geschlossene
Prismenschale pro Insel/Run über DISJUNKTE Z-Bänder → Summe der Schalen-
volumen ist EXAKT (Cavalieri). Interne Übergangskappen bleiben (dokumentiert).
Orakel: 3 identische Layer → 1 Prisma exakt; Outline-Wechsel → 82 mm³ exakt
als 80+8; Helper tragen nie bei. Fremd-Dateien z∈[0,4]: MAN_V3 18 Schalen/
64,987 mm³/3676 Dreiecke; vwbus 18/348,308/3332; Pumpkin 21/334,337/4236
(50 Loops >256 Vertices ehrlich gezählt). Selbstschnitt-Charakterisierung:
ALLE Paare (6244/12564/22321) liegen NUR auf dokumentierten Übergangs-
ebenen — null echte Wanddurchdringungen; audit-Volumen == Konstruktions-
volumen (float32). Beweis-STLs: analyse/stl-exports/ (+MANIFEST.json).
8 neue Tests, 172 gesamt lokal bestanden.
Stand (Sitzung nach `31b3df8`): STL-§24-Fertigstellung bleibt ZURÜCKGESTELLT
(J1, Richtung „Punktfolke + Haut"). **Toolchain §20: K1 + K2a + K2b/1
erledigt** — `tools/toolchain.py` (39 Tests: Preset-Vertrag, Menü-Registry
mit Drift-Wächter, run_chain-Engine mit §21/§22-Gates) UND
`tools/toolchain_steps.py` (11 Tests): die ECHTEN Engines (make_range/
apply_scale/apply_twist/apply_mirror/apply_texture) als step_runner —
echte Dreierketten laufen offline durch alle Gates, Skalier-/Spiegel-
Orakel an Koordinaten, Engine-Guards werden nachvollziehbare Fehlschläge.
Anker-Registry 5 Werkzeuge (twist/mirror neu), menü-gesichert. r2_postproc/
Makros/LCD UNVERÄNDERT. Offen: K2b/2 Watcher-/Makro-/LCD-Anbindung
(macro_render/r81-Gates), K3 UI, K4 Queue-Abhängigkeit. Danach: J7
Maschinenmodell-Audit (§12), J2 Gießformen (Zuweisung ausstehend),
J6 KI-Vision, J3 UI (navi.json verifiziert), J4 Audio. OFFENE-FRAGEN 15–18.
Der Loft ist keine allgemeine Spiralrekonstruktion; aktiver Export unverändert.

## Aktueller Branch-Status (arena/6ce4402e, R286-Runde, 2026-11-25)

Diese Branch führt die **R286-Feld-Korrekturen** auf V7 (`R2-2026-11-19.3`):

- **Range-Tool (L11):** `make_range` akzeptiert beliebig hohe Schichten;
  der R283-Pre-Scan-Clamp war **tott** (offene `sp`-Referenz -> NameError
  stillschweigend gefangen). Fix: `sp` -> `src_path` in **beiden** Engines,
  Duplizierung des Clamp-Blocks in `r2_postproc_next.py` entfernt. Start-Clamp
  `max(1, ...)` (Commit `531f101`). LCD `__from` min=1 / `__to` min=2,
  Toolchain-Schema synchron.
- **Velocity Live-Tuning:** `SET_LIVE_VELOCITY` nutzt jetzt `SPEED_SCALE`
  (Prozent, 100=normal) - die Anderung wirkt **sichtbar** am Druck, nicht nur
  als Kap. LCD-Menü auf Prozent-Semantik (Bereich 50-300).
- **PP_ENGINE_INFO entfernt** (reines Read-only-Info-Makro, "nix auswählbar").
  Der PP-Engine-Toggle bleibt.
- **Top/Bridge-Logik (User-Korrektur):** belegt via
  `tools/test_r286_topbridge_logic.py` (3/3) - die Engine enthält die
  Korrektur bereits: Top auf Sparse-Infill wird **nie** als Bridge
  klassifiziert; solid+Top+Ironing ist support-getragen.
- **L10:** `crash_archive`-Ordner aus dem Wurzel-Scan/Link-Sync ausgeschlossen.
- **L9 (Engine-Teil):** Scale+Range-Chain offline verifiziert (success,
  Output non-leer, valid) - kein Absturz vom Engine-Code.
- **Textur-Presets auf 95 erweitert (R286, User-Anforderung):**
  `PATTERN_NAMES` (`tools/r2_texture.py`) = **95 Muster** = **95 Presets** in
  `variable_texture_lib` + `tx_codes` + `tx_names` + `tx_descs`
  (`macros/17_generator.cfg`), Parität 95/95/95. **30 neue decorative
  plastische 3D-Druck-Texturen** (PETAL, LOTUS, PEBBLE, GALAXY, BRAID, QUILT,
  GEMSTONE, SHELL, CORAL, MOSAIC, PEARL, VELVET, STRATA, BASALT, MARBL,
  GRANIET, TERRA, WALNUT, MAPLE, ZEBRA, LEOPARD, PYTHON, LAVA, ICE, MOSS,
  FEATHER ...) + 13 Kernfamilien mit `_V2`-Varianten (>=2 Presets pro Typ).
  **Alle nahtlos/endlos** (MAP bildbasiert ausgenommen). Vorschau:
  `docs/textur-matrix-ist.png` (alle 94) + `docs/textur-matrix-soll.png`.
- **ScaleXY-Mittel-Skalierung (R286):** `apply_texture` + Caller
  (`r2_postproc(_next).py`) + LCD-Menüs `__sxymid`/`__sxypos`/`__sxycurve`.
  Mittlere Skalierung in 1%-Schritten, Z-Position in %, aktiv 5%<pos<95%,
  linear/Bezier-Ubergang bottom->middle->top. Skaliert das Relief, Periode
  bleibt integer -> nahtlos. Beleg: `tools/r286_scalexy_texture_check.py`
  **17/17**.
- **Konsolen-Spam reduziert (DOCTOR-Pack 19.3):** LED-Animationen wurden
  (LEDs sind in 26.20 komplett entfernt) mit dem LED-System ausgebaut.
- **L7 Generator-Audit UMSETZT:** `tools/r286_generator_audit.py` **15/15**
  (alle 19 Generator-Makros, Valid Shapes, Parameter, Toolchain-Vertrag).
- **L3/L5/L6 Label-Render-Audit UMSETZT:**
  `tools/r286_label_render_audit.py` **10/10** (Grundlinie/Cap-Height,
  Uniform-Scale, Kleinbuchstaben-Konformität, grow/fixed, stamp+Spiegelung).
- **L8 Watcher-Speicher-Audit UMSETZT:**
  `tools/r286_watcher_mem_audit.py` **10/10** (Caches bounded, Messmethodik;
  RAM-Messung am Drucker bleibt Field-Check).
- **J4 / L1 — ECHTE Audio-Ausgabe auf dem Raspberry (R286, User-Anforderung):**
  Die `klinke`/`hdmi`-Audio-Quelle spielt **REALE 8-bit-Audio**, nicht mehr
  Pulsmodulation/Beep/Konsolentext. Neues `tools/r2_audio_play.sh` synthetisiert
  ein **8-bit-WAV** (quadratische Welle + Envelope, mono, 22 050 Hz) und spielt
  via `aplay`/`paplay`/`ffplay`. Das `M300`-Makro routet `klinke`/`hdmi` zu
  `RUN_SHELL_COMMAND CMD=R2_AUDIO_PLAY`; der Befehl ist als
  `[gcode_shell_command R2_AUDIO_PLAY]` in `r2_setup_lib.sh` registriert
  (R2_PERSIST-Konvention). **Dieselben Töne (_SOUND_LIB) bleiben erhalten** —
  nur die Wiedergabe ist jetzt echte Audio-Ausgabe. Audit:
  `tools/r286_audio_real_check.py` **9/9**. Der `beep`-MCU-Piezo-Pfad ist
  unverändert.
- **L4 Label-Engine / L13 Textur-Träger-Geometrie (Engine-Verifikation):**
  `tools/r286_label_texture_geometry_check.py` → **4/4** (L4: 5/5 Label-Zeilen
  gerendert, 49 Pfade; L13: alle 4 `make_shape`-Generatoren TRIANGLE/SQUARE/
  POLY/CYLINDER mit Textur-Anwendung, je 200 outer-wall-Blöcke). Field-Check am
  Drucker bleibt (visibles Druckergebnis).
- **L12 Dokumentation UMSETZT:** AGENTS.md auf vollem Stand,
  `docs-notes/MASTER-TODO.md` vollständig aktualisiert (alle J3/J4/J5/L4/L13/
  L9–L12/L14/L16 auf umgesetzt; E1/E4 Code-Maßnahmen geliefert).
- **J3 UI-/Display-Konzept geschlossen:** Kombination eigener Port +
  Mainsail `.theme/navi.json`-Sidebar-Menüpunkt (Mainsail-Quelltext verifiziert).

Feld-Checks am Drucker (RAM-Messung L8, Display-Angaben L9, **Hören der
Audio-Töne L1**, Label-Ausbringung L3-L6, L4-Label-L2, Textur-Sichtbarkeit
L13) sind in `docs-notes/MASTER-TODO.md` §L verzeichnet. `TEXTURING.pdf`
(95 Presets) + `LABELS.pdf` neu gerendert.

## Historie

`docs-notes/UEBERGABE.md` enthält bewusst datierte Zwischenstände
(alte Commit-Hashes wie `8ea17fc`, `fab29dc`) — kein Widerspruch zu diesem
Dokument; bei Konflikten gilt: **Code > tests > diese Datei > UEBERGABE**.
