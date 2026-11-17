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
