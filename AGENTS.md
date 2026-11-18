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

## Aktueller Stand (2026-11-18)

- `main` = Merge `e2b42bc` (Release **R2-2026-11-18.2 / V3**, PR #19).
- Release-Status: V1 `R2-2026-11-13.1` → V2 `R2-2026-11-18.1` → V3 `R2-2026-11-18.2`.
  Das finale V3-ZIP liegt **lokal** in `releases/` (gitignored) mit `.sha256`-Sidecar.
- Der **Drucker ist im Umbau** — keine Hardware-Tests, keine Feldabnahme,
  keine `printer.cfg`-Änderungen ohne explizites Go + Test-Fenster.
  Die dafür gesammelte **Feld-Abnahme-Checkliste** steht in
  `docs-notes/MASTER-TODO.md`, Abschnitt „G. Feld-Abnahme-Checkliste".
- Erledigt: D5 (Creative-Freedom-PDF, Titel + Kapitel + Schlusssatz,
  Commit-Serie dieser Branch). Release-Berichte unter `docs/RELEASE_*.md`.
- Offen (Hauptbaustelle): **STL-Export** (Briefing §24) — Bestandsaufnahme in
  `analyse/STL-EXPORT-AUDIT.md`; Vorgehen: Tests zuerst, dann Reparatur.
- **D3/D4** (wissenschaftliche Generator-/Modifier-PDFs): vom Nutzer
  zurückgestellt, Umfang (>15 Einzel-PDFs vs. Gesamtwerk) noch nicht final.
- **D1 ist freigegeben:** MANUAL.md aktuell halten; Kap. 14 ergänzt.
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
Nächster Schritt: physische Linienbreite und geometrische Plausibilisierung vor
Mesh-Anbindung; nichtplanare Bahnen brauchen weiterhin eine eigene Strategie.
Der Loft ist keine allgemeine Spiralrekonstruktion; aktiver Export unverändert.

## Historie

`docs-notes/UEBERGABE.md` enthält bewusst datierte Zwischenstände
(alte Commit-Hashes wie `8ea17fc`, `fab29dc`) — kein Widerspruch zu diesem
Dokument; bei Konflikten gilt: **Code > tests > diese Datei > UEBERGABE**.
