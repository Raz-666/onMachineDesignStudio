# Layer-Zählung: kommentiert vs. Z-Scan — Divergenz und Entscheidungsvorlage

**Status:** Vorschlag zur Entscheidung des Nutzers. **Keine Codeänderung in diesem Schritt.**
Grundlage: `analyse/SCHICHTANALYSE-UND-PRUEFPLAN.md`, `analyse/layer_comment_probe.py`
sowie die dort hinterlegten Protokolle; Zeilenangaben des Postprozessors auf Stand `ce29e2a`
(Verweis/Lesehilfe, kein Abnahmeargument). Offline-Proben, kein Klipper, kein Drucker.

Release-Relevanz: `analyse/RELEASE-GAP-MATRIX.md` führt denselben Fall als
„RELEASE-BLOCKER für konsistente Layer-/Reverse-Engineering-Claims“.

## 1. Reproduzierbarer Befund

`python3 analyse/layer_comment_probe.py` erzeugt zwei synthetische Dateien mit
exakt denselben Bewegungs- und Typzeilen; nur `;LAYER_CHANGE` fehlt in der einen:

| Variante | Erkennung | `_FILE_INFO TOTAL_LAYERS` | `APPLY_TYPE` nach den drei SKIN-Kommentaren |
|---|---|---:|---|
| mit Kommentaren (`LAYER_CHANGE`) | Layer-Kommentare | 3 | `SURFACE-BOTTOM`, `SURFACE-TOP`, `SURFACE-TOP` |
| ohne Kommentare | Z-Scan (`_ZScan`) | 2 | `SURFACE-BOTTOM`, `SURFACE-BOTTOM`, `SURFACE-BOTTOM` |

PROTOKOLL: `analyse/testprotokolle/layer_comment_probe.log`
(beide Läufe: `physical_z_levels=[0.2,0.4,0.6]`).

Zwei Trenner sind zu unterscheiden:

1. **Layer-Quelle.** `process()` bevorzugt `LAYER_CHANGE`/`LAYER_MARK`-Kommentare
   und springt nur ohne deren Vorhandensein auf `_ZScan` um (`:19925–19949`).
   Der Kommentar-Zweig zählt kommentierte Wechsel; der Z-Scan zählt Z-*Wechsel*
   ab der ersten Extrusions-Z (`:20246–20309`), nie die Gesamtzahl physischer
   Ebenen. Die r110-Dialektkorpus prüft ausdrücklich die Wechselzahl, nicht die
   Ebenenzahl (`tools/r110_gcode_dialects.py:213–222`).
2. **SKIN-Rolle.** Die SKIN-Sonderregel liest die bisher gefundenen
   *Layer-Kommentare* (`:19854–19864`), nicht das Z-Scan-Ergebnis. Erste SKIN →
   `SURFACE-BOTTOM`, spätere → `SURFACE-TOP`. Ohne Kommentare entscheidet der
   Näherungs-Default und alle drei Flächen werden `SURFACE-BOTTOM`.

## 2. Weitere belegte Reibungspunkte am selben Vertrag

- **Z-Hop mit E0/Rückzug** (`analyse/zhop_eprobe.py`, `zhop_mutation_probe.py`):
  `_ZScan` prüft nur auf Vorhandensein eines E-Worts neben X/Y, nicht auf
  positives Delta (`:20267–20284`). E0/negative E neben X/Y-Bewegung im Hop
  erzeugt einen zusätzlichen Marker vor der falschen Bewegung.
- **Marker-Ansicht** `LAYER_MARK` bekommt `s.layer+1` (`macros/06_temp_controls.cfg:538–557`);
  ohne Marker zählt der `_STATE_WATCHER` Z-basiert auf demselben Zählerbahnen-Kontext
  (`macros/01_state.cfg:814–846`). Reihenfolge Watcher↔Marker ist asynchron und
  nicht nachgewiesen (Probe `layer_order_probe.py`, Modellannahmen A/B).
- **Startzustand** `PRINT_START` setzt `total_layers` und ruft direkt danach
  `_LIVE_RESET`, das `total_layers` wieder auf 0 setzt
  (`macros/08_print_start_stop.cfg:107–112`, `macros/10_live_tuning.cfg:61–67`).

## 3. Verbraucher — wen eine geänderte Zählweise betrifft

Marker/Zähler werden u. a. konsumiert von: `_FILE_INFO TOTAL_LAYERS`,
`LAYER_MARK`-Template (`CURRENT/TOTAL`, `M220 S100` bei n == 2,
`_END_AT_LAYER` bei aktivem Stop-at-Layer), Live-Tuning-Anzeige
(`Ly: 0.2x?` bzw. `Ly: 0.2x251`), `SET_LAYER_RANGE`-Vorbelegung,
`PAUSE_AT_LAYER`, `_STATE_WATCHER`, Range-Tool (`make_range`) und den
Generator-/Cutter-Ausgaben, die `LAYER_MARK`/`_FILE_INFO` selbst schreiben.
Eine Umstellung der Zählkonvention ohne vollständige Migrationsprüfung
aller dieser Pfade verletzt `docs-notes/MASTER-TODO.md` (keine
Zählkonventionsänderung ohne Migration) und die Übergabe-Regeln.

## 4. Optionen (zur Entscheidung)

- **Option A — Vertrag ausdrücklich so dokumentieren (Status quo + Doku).**
  Kommandiertes Verhalten: Kommentare schlagen Z-Scan; Z-Scan zählt Wechsel,
  erste Ebene nicht enthalten; SKIN-Rollen sind Näherungen ohne Ground Truth.
  Vorteil: kein Risiko für bestehende Verbraucher, schnell, ehrlich.
  Nachteil: Nutzer kann sich auf keine Ebenenzahl verlassen, wenn Kommentare
  fehlen/fehlerhaft sind; SKIN-Rollen bleiben heuristisch.
  Aufwand: Doku + Tooltip/Menühinweis (`Ly:` Zeile) + Tests fixieren.

- **Option B — Z-Scan auf positive Extrusion einschränken + SKIN aus physischen
  Extrusionsschichten.** E0/negative E im Hop erzeugen keinen Marker; `SKIN`
  nutzt Z-Scan-Ebenen statt Kommentaranzahl; `TOTAL_LAYERS` = positive
  Extrusionsschichten (ggf. + 1, wenn die erste Ebene als „noch nicht
  gedruckt“ geführt werden soll — Zählperiode festlegen).
  Vorteil: kommentiert/kommentar-los konsistente Zahlen, Hop-Fehlmarker weg.
  Risiken: `LAYER_MARK`-Reihenfolge/`_STATE_WATCHER` müssen gegengeprüft werden;
  `r110`-Erwartung (Wechselzahl) ändert sich bewusst; Golden-Dateien müssen
  neu eingefroren werden (mit dokumentierter Begründung); H3/Range-Tool und
  Live-Tuning sind mitzutesten.
  Aufwand: mehrere belegte Testläufe + Changelog + Nutzer-Go.

- **Option C — Fail-closed: ohne Layer-Kommentare kein `LAYER_MARK`/`TOTAL_LAYERS`-Anspruch.**
  Kommentarlose Dateien werden als „Schichten unbekannt“ geliefert (z. B.
  `_FILE_INFO TOTAL_LAYERS=0` + sichtbarer Hinweis).
  Vorteil: keinerlei falsche Zahl mehr. Nachteil: reale Werkzeuge/Slicer ohne
  Kommentare verlieren Ebene/Range-Funktionen komplett; große UX-Regression.

**Empfehlung des Analysestands:** Option A kurzfristig (Dokumentation + Tests),
Option B als eigener, freigegebener Umbau mit Migrationsprüfung; Option C nicht.

## 5. Abnahme, wenn Option B freigegeben würde

1. Synthetische Gegenproben: kommentiert/kommentar-los Byte-Parität der
   Bewegungs-Ausgabe; TOTAL_LAYERS identisch; Hop mit E0/negativ/positiv;
   Vase/Spiral; variable Layerhöhen; erste/letzte Ebene; leere SKIN-Schichten.
2. Verbraucher-Renderer: `LAYER_MARK`-Template, `_STATE_WATCHER`,
   `SET_LAYER_RANGE`, `PAUSE_AT_LAYER` bei geänderter Zählperiode.
3. Goldens neu einfrieren mit dokumentierter Delta-Begründung; r110 Erwartung
   anpassen; `r81` byteidentisch nur falls Moves unverändert bleiben (muss
   bytegleich belegt sein, sonst Gegenbegründung).
4. Feld-Fixtures (`rose`, `bigrose`, `stringart`) ohne Fehlalarme laufen lassen.

## 6. Grenze dieser Vorlage

Keine Ausführung auf einem Drucker; SKIN-Rollen sind weiterhin keine
Ground-Truth-Aussage. Die Entscheidung (A/B/C, inkl. Zählperiode bei B) trifft
der Nutzer; danach Erstumsetzung in `tools/r2_postproc_next.py` mit
Byte-Parität-Check, Tests, dann kontrollierter Tausch — nicht am laufenden
Postprozessor direkt.

---

## 7. Umsetzung (R258, Option B) — Stand 2026-11-18

Nutzer-Entscheidung vom 2026-11-18: **Option B** (nach Erklärung in Alltagsdeutsch),
Release-Freigabe und Paketumfang (ohne `analyse/`) separat erteilt. Umsetzung auf dem
Arena-Branch `arena/fa800e48-onmachinedesignstudio`, nicht am laufenden Postprozessor
direkt: `tools/r2_postproc.py` und `tools/r2_postproc_next.py` (Byte-Parität ab Zeile 4,
durch `tools/run_review_checks.sh` erzwungen).

### 7.1 Was geändert wurde

1. `_ZScan` führt jetzt `rises` (in den bestehenden Marker-Pfad einspeisend),
   `big_rises` (Extrusions-Z-Sprünge > 0,35 mm — werden **nie** Marker, damit die
   Marker-Ausgabe byte-stabil bleibt) und `bed_returns` (Fall ≥ 1 mm, der auf die
   Bett-Höhe der ersten Schicht zurückkehrt = sequentieller Neustart; Rückzug auf
   Zwischenhöhen zählt nicht — Befund: `stringart3d_generic` hat 1700 Stürze, davon
   **0** Bett-Rückkehrer).
2. `Zählperiode`: **Gesamtschichten inkl. erster Schicht** (Kommentarwechseldateien
   melden heute `TOTAL_LAYERS=3` für drei Schichten; eine andere Periode wäre mit dem
   kommentierten Pfad inkonsistent).
3. `TOTAL_LAYERS`: kommentierte Dateien behalten die Slicer-Kommentaranzahl
   (Begründung siehe 7.3); kommentarlose Dateien melden
   `rises + big_rises + 1 + bed_returns` statt der bisherigen bloßen Wechselzahl
   (erste Schicht fehlte). Bereits getaggte Dateien behalten `count_marks`.
   SKIN-Rollen und Marker-Positionen unverändert (SKIN war nach dem R246-Stand
   bereits kommentiert/kommentarlos konsistent: BOTTOM/TOP/TOP in beiden Welten).
4. Die E>0-Bedingung der Z-Scan-Extrusionserkennung war im aktuellen Code bereits
   wirksam (`e_delta > 0`); die Z-Hop-Probe bestätigt das jetzt für alle sechs
   Fälle (M83/M82 × ohne E / E0 / Rückzug). Die Probe enthielt noch die alte
   Gegenbehauptung und wurde korrigiert.

### 7.2 Abnahme gegen Abschnitt 5 — Belegstand

| Abnahmekriterium (§5) | Beleg |
|---|---|
| Kommentiert/kommentarlos Byte-Parität der Bewegungsausgabe | `analyse/layer_comment_probe.py` (um Paritäts-Assertion erweitert): GLEICH — einzige Unterschiede sind `;LAYER_CHANGE`/`LAYER_MARK`/`_FILE_INFO`; `analyse/testprotokolle/layer_comment_probe_r258_20261118.log` |
| `TOTAL_LAYERS` identisch | selbe Probe: 3 == 3 (beide Varianten) |
| Hop mit E0/negativ/positiv | `analyse/zhop_eprobe.py` (reparierte Erwartung): 6/6 ohne Fehlmarker, `TOTAL_LAYERS=2`; `analyse/testprotokolle/zhop_eprobe_r258_20261118.log` |
| Variable Layerhöhen; erste/letzte Ebene | `analyse/testprotokolle/layer_comment_probe_r258_20261118.log` + zusätzliche Synthetik-Probe (dz 0,3/0,25/1,2/0,2/0,15/0,4): `TOTAL_LAYERS=6` exakt; Marker-Logik unverändert (Sprünge >0,35 mm ohne Marker — bewusste Grenze) |
| Vase/Spiral | Fixtures: kontinuierliche Spiralsteigung über die 0,18-mm-Akkumulation → **Näherung, nicht exakt** (siehe 7.4); diese Dateien tragen in allen drei Feld-Fixtures Layer-Kommentare und behalten deren Anzahl |
| Goldens neu eingefroren mit Begründung | `analyse/golden_r258_expected.json` (neu, m82_zhop `layers 1→2`, −0 Bytes, 1 Ziffer); `tools/r81_golden_check.py`: pr03/pr08 neu eingefroren, A/B-Diff gegen git HEAD = **exakt 1 Zeile je Fall** (`TOTAL_LAYERS=8→9`); mr01–13 unverändert |
| r110-Erwartung angepasst | `tools/r110_gcode_dialects.py`: Z-Scan-Dialekte erwarten jetzt `layers == truth_layers` (13/13 Familien grün) |
| Feld-Fixtures ohne Fehlalarme | `analyse/golden_baseline.py verify`: bigrose 251 / rose 242 / stringart 15 **unverändert** (Byte-identisch); m82_zhop dokumentiert geändert |

### 7.3 Bewusste Abweichung von §4 (Option B wie ursprünglich skizziert)

Der Skizzen-Stand sah vor, den physikalischen Zähler auch bei kommentierten Dateien
vorrangig zu verwenden. Das ist **verworfen**: Die Feld-Fixtures belegen, dass der
Scan dort überzählt (bigrose 251→275; rose 242→264; stringart 15→1717 — 1700 Stürze
der String-Verdrahtung wurden als Objekt-Neustarts gelesen, bevor `bed_returns`
eingeführt wurde; selbst danach bliebe die Spiral-Akkumulation unscharf). Die
Slicer-Kommentare sind für kommentierte Dateien die bessere Quelle; der Scan ist der
Fallback. Kommentarlos bleibt damit exakt bei Treppenprofilen und approximativ bei
Spiralen.

### 7.4 Restrisiken / Grenzen

- Kommentarlose Spiral-/Vase-Dateien: `TOTAL_LAYERS` ist eine Näherung (Akkumulator
  statt `layer_height`); keine Slicer-seitige Ebeneninformation, keine sichere Zahl.
- Sequenzieller Druck: Erkennung nur über Bett-Rückkehr (≥1 mm Fall, Rückkehr auf
  erste Schicht + 0,4 mm). Objekt-Übergaben auf Zwischenhöhen sind nicht erfasst.
- Layer > 0,35 mm tragen keinen `LAYER_MARK` (Marker-Cap unverändert, Byte-Parität).
- SKIN-Rollen bleiben Heuristik (BOTTOM/TOP), keine Ground-Truth-Aussage.
- `LAYER_MARK`-Periode kommentierter Dateien (eine Markierung je Kommentar) ist
  unverändert; Verbraucher (`PAUSE_AT_LAYER`, `SET_LAYER_RANGE`, Live-Tuning) sind
  davon nicht betroffen.
- Keine Drucker-Abnahme: alles offline. Feldabnahme (Layer-Anzeige live) steht aus.
