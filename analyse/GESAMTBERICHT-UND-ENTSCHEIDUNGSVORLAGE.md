# Gesamtbericht und Entscheidungsvorlage

> **Historischer Snapshot:** Dieser Bericht beschreibt Branch `arena/c7804d42-onmachinedesignstudio`, Produkt-HEAD `ce29e2ac611a50bf8a1bf43e345ad0fab2eaab82`, Version `R2-2026-11-13.1` / V1. Er wurde vor den späteren Merge-PRs #7–#10 geschrieben; sein Wortlaut und seine alten offenen Stati sind nicht der heutige Implementierungsstand. Für den Vergleich mit aktuellem `main` (`8ea17fc`), PR-Nachweisen, aktuellem Makrotest-Abbruch und verbleibenden Releases-Gaps gilt jetzt `analyse/RELEASE-GAP-MATRIX.md`. Die historische Analyse bleibt als Beleg der früheren Befunde erhalten; keine pauschale Implementierungs-, Veröffentlichungs- oder Hardwarefreigabe folgt daraus.

**Stand des historischen Berichts:** Branch `arena/c7804d42-onmachinedesignstudio`, Produkt-HEAD `ce29e2ac611a50bf8a1bf43e345ad0fab2eaab82`, Version `R2-2026-11-13.1` / V1. **Nur Analyse – kein Implementierungs-, Backlog-, Veröffentlichungs- oder Hardware-Go.** Dieser Bericht bündelt die abgeschlossene zusammenhängende Bestandsaufnahme des verfügbaren Materials und ersetzt als Einstieg die als Zwischenstände bezeichneten Einzelberichte. Er legt zugleich offen, wo die gewünschte vollständige Einzelprüfung noch nicht nachgewiesen oder ohne fehlende Quellen/Maschine nicht möglich ist. Er ist keine Produktabnahme.

## 1. Ergebnis auf einen Blick

Das Projekt ist kein Neubau: Makros, LCD, Web, Generatoren, Queue, stabiler und experimenteller Postprozessor sowie umfangreiche Tests sind vorhanden. Die Wiederherstellung ist für den gelieferten Snapshot nachgewiesen. **Die wichtigsten Risiken liegen nicht in fehlendem Code, sondern in Verträgen zwischen Datei, Parser, Layer-/Objektzustand, Overrides, UI und Hardware.** Mehrere konkrete Gegenproben widersprechen allgemeinen Funktions- oder Schutzbehauptungen:

1. **Original-Bild kann überschrieben werden:** Der Bild-Pick-Zweig kopiert eine Datei aus einem Unterordner auf den gleichen Basenamen im Root. Bei vorhandener Rootdatei überschreibt er diese und meldet Erfolg. Aus dem Originalzweig reproduziert, ausschließlich mit temporären Dateien und Stub. `DATEI-JOBS-HARDWARE-UND-DOKU.md` §1; `image_pick_collision_probe.log`. Auch `process(path)` ersetzt die übergebene Datei; ob alle realen Einstiegspfade vorher kopieren, ist nicht allgemein geklärt.
2. **Sicherheitsbereich Probe/MCU ungelöst:** E1/E4 und historisch dokumentierte Sondenfehler sind nicht auf dieser Maschine nachgetestet; vorhandene LED-/Homing-Gates sind Offline-Nachweise, keine physische Sicherheitsfreigabe. Keine Änderung des Z-Limits, kein Homing-/Gantry-/Wipe-Versuch ohne separates Go und konkreten Sicherheitsplan.
3. **Layer-/Objektinterpretation kann abweichen:** M82/M83-E0 bzw. Rückzug im Z-Hop erzeugen in der Probe einen falsch platzierten Layer-Marker. Bei gleicher Bewegung unterscheidet sich mit/ohne Kommentar die ausgegebene Layerzahl und SKIN-Rolle. Die Wechselwirkungen mit Pause/Stop und Starttotal sind mit gerenderten Makros/Stub-Modellen demonstriert, aber nicht auf realem Klipper zeitlich bewiesen. Ein sequentielles Objekt erhält im gelieferten Rose-Fixture eine irreführende Brim-Warnung.
4. **Overrides und Kalibrierung:** In 16 skalaren Zweigen von `SET_OVERRIDE_VALUE` steht das ON-Flag hinter `;` auf derselben Zeile; der gepinnte Klipper-Parser verwirft diesen Teil. Wert und Flag können auseinanderlaufen; Wirkung hängt vom Vorzustand ab. Die Flow-LCD-Kalibrierung übergibt im getesteten Pfad das gesetzte Ziel nicht. Die Ironing-Kalibrierung reicht in der Offline-Probe mm/s als Prozent-Feature-Speed weiter und verwirft explizite Kartenwerte. Die Gantry-PDF widerspricht der Makroguard-Bedingung.
5. **Geometrie und Export:** `_GeomScan` zeigt in kleinen Proben Unterschiede bei G92 und relativer X-Position. Der STL-Export liefert nach ausgefiltertem Support für äquivalente M82/M83-Bewegungen unterschiedliche Wandbandbreiten; ein echter Slicer-Reimport und historische Fehl-STLs fehlen. Ergebnisse sind konkrete Gegenfälle, keine pauschale Fehlerquote.
6. **UI-/Job-Risiken:** `r218` 23/25: eingebetteter Web-Menüfallback veraltet und Versionsbadge weicht ab; der zweite Test nutzt eine alte Versionsformatannahme. Ein künstlich injiziertes Queue-Kill zeigt `UnboundLocalError`; reguläre Erreichbarkeit bleibt offen. Job-Erfolg inkl. geprüfter Datei, Registrierung und Meldung ist nicht als einheitlicher End-to-End-Vertrag nachgewiesen.

## 2. Quellen, Zustand, was nicht vorliegt

- Snapshot `repo-tree-019f0a4.tar.xz`: **172/172 getrackte Dateien identisch**, 0 fehlende/abweichende bei der Rekonstruktion. Alle elf bereitgestellten Quelldateien unter `analyse/uebergabe-quellen/` ergeben `SHA256SUMS` 11/11. Sie sind nicht zur Veröffentlichung freigegeben. Git-Diff der getrackten Dateien ist leer; nur `analyse/` ist untracked. Restore/Merge liegt bereits im Master-Merge-Commit; hier wurde kein weiterer Commit/Push vorgenommen.
- Verfügbar: vollständiges Startbriefing, Masterkonzept, Feature-Union, Geometrieausarbeitung, Postprozessor-Briefings, Übergabe, zwei MCU-PDFs, Projekt-PDFs und drei komprimierte Repo-G-Code-Fixtures. Einzelne Quelldokumente beschreiben Sollvorstellungen oder historische Diagnosen, nicht notwendigerweise Ist-Funktion.
- Nicht in den bereitgestellten Uploads gefunden: `slicer-families.md`, separat benannte `GCode_Reverse_Engineering_Master_Spezifikation.md`, V1-Update-ZIP, originale historische Diagnoselogs und fehlerhafte STL-Exporte. Maschinenkonfiguration, installierte Klipper-/Moonraker-Version und Hardwarezustand sind hier nicht bekannt. Der Name `r2_hardware.cfg` bezeichnet ein durch Setup erzeugtes Maschinenartefakt; ein reales Nutzerexemplar liegt nicht vor.
- `STARTBRIEFING-QUELLENINDEX.tsv` bewahrt 521 indexierte Einzelpunkte; `STARTBRIEFING-ANFORDERUNGSABGLEICH.md` ordnet sie gruppiert zu. **Nicht alle 521 Punkte sind einzeln mit Funktionstests abgezeichnet.** `MASTERKONZEPT-ABSCHNITTSABGLEICH.md` deckt Abschnitte 0–17 thematisch ab, ebenfalls ohne Anspruch auf jeden Einzelpfad. Dies bleibt die wichtigste Grenze gegenüber dem Wunsch nach vollständiger Einzelabnahme.

## 3. Ist-Architektur und Funktionsinventar

- `tools/r2_postproc.py` verbindet Parser, Layer-/Geometrie-/Featureanalyse, Dateiverarbeitung, Generatoren und Watcher. `r2_postproc_next.py` ist die für späteren Umbau vorgesehene Variante; bestehendes Handover/Stable-Fallback bewahren. `_FILE_INFO`, `LAYER_MARK`, `APPLY_TYPE`, CUSTOM, bestehende Profile und Datenflüsse sind Kompatibilitätsverträge, keine austauschbare Dekoration.
- 21 CFG-Dateien enthalten Zustands-, Start-/Pause-/Live-/Kalibrier-/Hardware- und Generatormakros. `menus/lcd_menues.cfg` ist die LCD-Baumquelle; Web verwendet exportierten Baum und Moonraker-Komponente. AS SLICED und AS LEGACY sind bestehende unterschiedliche Pfade, die vollständige Nichtbeeinflussung von Slicerparametern ist nicht belegt.
- Datei-/Bildliste und Queue haben existierende Implementierungen, aber keinen für sämtliche Wege nachgewiesenen gemeinsamen Vertrag für Quelle, Ausgabe, Registrierung, Validierung, Abbruch und Meldung. Im Bildbrowser werden Rootbilder auf 60 begrenzt, seitenweise zu 10 ausgegeben; ausgewählte Unterordnerbilder werden ins Root kopiert. `_job_worker` serialisiert und wartet bei Busy/RAM, kooperative Pausen und ein Hängerschutz sind vorhanden. Einzelheiten und Familieninventar: `DATEI-JOBS-HARDWARE-UND-DOKU.md`.
- Kalibrierungsleiter: 13 Schritte zu Makros, Menüpfaden und Bedingungen zugeordnet in `KALIBRIERUNG-ABGLEICH.md`; Override-/Material-/Ironingpfade separat geprüft. Keine vollständige reale LCD-/Web-/Hardwareabnahme.
- Hardware: dynamische und konfigurierte Bounds, Düse, optionale LED-/Sensorschnittstellen und Wipe existieren; reale mechanische, Probe-, Bett-, Nutz- und Parkbereiche müssen getrennt geprüft werden. Cartesian/CoreXY sind Ziele, keine für beliebige Geräte nachgewiesene Vollunterstützung; Delta ist eingeschränkt. `M300` nutzt direkt `beeper` ohne Guard; die Bibliothek enthält 20 statt der im Briefing vermuteten 19 Tunes. LED-Quiet hat Tests, Plugin-/Konfigurationsvoraussetzungen bleiben. 30 Delayed-Gcode-Definitionen und 62 statische Textreferenzen inventarisiert; keine werden still entfernt, tatsächliche I/O-/Reactor-Last ist ungemessen.

## 4. Postprozessor und Reverse Engineering

Parser, `_ZScan`, `_GeomScan`, `_LayerBitmap`, TYPE_MAP, Layer-/Objektmarker und geometrische Zweitpässe sind Bestand und bleiben zu erhalten. 146 wirksame TYPE_MAP-Einträge und 377 Quellbelege sind indexiert; Quellrolle, tatsächlicher Slicerkommentar und interne Rolle sind nicht gleichzusetzen. Ein doppelter `wipe wall`-Eintrag wird durch die spätere Zuordnung überschrieben. Der heuristische Wert `CONF=0.7` ist kein kalibrierter Wahrscheinlichkeitsnachweis. Muster und Feature-Rolle sind nicht allgemein getrennt nachgewiesen; unbekannte Syntax/semantische Mehrdeutigkeit muss als solche sichtbar bleiben.

Die verbindliche Ziel-Pipeline Pass 0–11 (Rohdaten, Zustand, Moves, Layer, Extrusion, Pfade, 2D, 3D, Feature, Pattern, Konsistenz, Ausgabe) ist mit Bestand und Gaps in `MIGRATION-UND-ABNAHMEPLAN.md` §2 verbunden. Die vorhandenen Streaming-Pässe sind nicht gleichbedeutend mit zwölf vollständigen Sollpässen. Testkorpus: aktuelle Goldens, drei Feldfixtures und synthetische Dialekte; vollständige versionierte reale Slicer-Ground-Truth, Metriken und unabhängiger Reimport fehlen.

## 5. Testbilanz – tatsächlich gelaufen, keine Hardware

| Prüfung | Ergebnis | Aussagegrenze |
|---|---|---|
| Makro-/Renderbatterie `macro_render_test.py` | **2100/2100, Exit 0**, `macro_render_current.log` | Renderer/simulierte Abläufe, kein Drucker. Die Batterie enthält auch vorhandene Texture-/Shape-Tests; sie wurde als allgemeines Gate gestartet, obwohl G1–G5 gesperrt sind. Das hätte ich vor dem Start prüfen müssen. Es wurden keine Produkt- oder Texturdateien geändert. |
| `r81` | 23/23 byteidentisch | Referenztreue, nicht fachliche Korrektheit. |
| `r110` | 13 synthetische Familien, 46/46 untersuchte Tags | keine reale Markt-/Dialektabdeckung. |
| `r166` | 21 CFG, 2736 Sektionen, 409 Templates kompiliert | kein tatsächliches Laden der Maschinenkonfiguration. |
| `r255` / `r257` | 19/19; 15/15 plus 7/7 Mutationen | Offline-/Guard-Tests, keine MCU-/Homing-Messung. |
| V1 Range | 8/8 inkl. Gegenprobe | Guard für Testfälle; H2-Strukturproblem bleibt. |
| `r218` Web | **23/25**, Exit 1 | konkrete Fallback-/Versionsabweichung; keine reale Geräteinstallation. |
| Synthetische Proben | Layer/Modal/STL/Overrides/Queue und Bild-Kollision reproduziert | Nur dokumentierte Voraussetzungen; Queue-Kill und Layerzeitablauf sind Modelle. |
| `r217` gemischte Generatorprüfung | **abgebrochen, kein Ergebnis** | Nach Start erkannt, dass G5-Shape-Fälle enthalten sind; Log gepuffert und leer, ob diese Fälle schon liefen, ist unbekannt. Dies war ebenfalls nicht sauber gegenüber der Sperre. Keine Produktänderung. |

Weitere protokollierte Proben und ihre genauen Vorbedingungen: `analyse/testprotokolle/`, `BESTANDSAUFNAHME-UND-ARCHITEKTUR.md`, `SCHICHTANALYSE-UND-PRUEFPLAN.md`, `START-UND-PREVIEW-ABGLEICH.md` und die beiden Override-Berichte. Historisch erwähnte Testzahlen ohne eigenen aktuellen Log sind keine neue Messung.

## 6. Backlog und Zielarchitektur

`BACKLOG-DISPOSITION.tsv` enthält **alle 32 expliziten IDs** aus dem einzigen `docs-notes/MASTER-TODO.md` mit Originaltext, Quelle, Ist, Priorität, Abhängigkeit, Empfehlung, Erhaltung und Test-/Abnahmekriterium. `BACKLOG-DISPOSITION-ERLAEUTERUNG.md` erfasst D7a–d und Abschnitt F gesondert. Keine Zeile wurde verändert. H1: Guard offline bestanden, H2/H3 offen. C1–C5 sind zu erhalten und in das Parser-/Objekt-/Evidenzmodell einzuordnen. D1-LIVE-Lüfterdokumentation benötigt Entscheidung; D7d und G1–G5 bleiben gesperrt.

**Vorschlag, nicht beschlossen:** Dateien/Bilder und Jobstatus als sichere gemeinsame Dienste; Maschinenprofil mit getrennten Bereichen; verlustfreier Parser und Modalzustand; normalisierte Bewegungen → Layer/Objekte/Pfade → Geometrie/Topologie → Feature und separat Pattern → evidenzbasierte Diagnose → nichtdestruktives Sidecar; bestehende R2-Befehle und LCD/Web über Adapter. Nichts still entfernen. Das ist ein Migrationsziel, keine Aussage über bereits implementierte Module.

## 7. Reihenfolge, Rückweg und Abnahme

1. Freigabeentscheidung und ggf. fehlende Quellen; keine Bewegung oder Produktänderung.
2. Nach Architektur-Go zuerst Goldens, sichere Kopien/Hashes und Ressourcenbasis; für jede Fehlerbehebung gesondertes Arbeits-Go. **Priorität:** Schutz vor Dateiüberschreiben und Probe-Sicherheitsklärung, dann Modal-/Layer-/Override-/Job-Verträge.
3. Neuer Parser und Pässe nur als **nicht ausführende Shadow-Analyse** neben Stable; Vergleich von Move-/E-Deltas, Layern, Objekten und Evidenz. UNKNOWN statt künstlicher Gewissheit. Bei Abweichungen kein automatischer Austausch.
4. Stückweise Adapter/A-B-Tests in `next`; Originaldatei unverändert, abgeleitete Kopien atomar, keine unbeabsichtigten G-Code-Befehle. Pro Schritt Golden-/Fehler-/Mutationstests und Rückschalter auf unverändertes Stable.
5. Erst danach, und nur mit eigenem Go, Klipper-/Moonraker-Integration und beaufsichtigte Hardwaretests mit konkretem Not-Aus-/Sicherheits-/Rollbackplan. Homing, Probe, Purge, Start/Ende, Menü-Exit, UART und bestehende Delayed-Gcodes besonders schützen.

Die konkrete Matrix für Modalität, Layer, Multiobjekt, Datei, Queue, STL, UI, Hardware und Ressourcen steht in `MIGRATION-UND-ABNAHMEPLAN.md`. Zeit- und Kostenschätzungen sind mangels Plattform- und Korpusdaten noch nicht belastbar.

## 8. Entscheidungen und offene Informationen

1. **Architekturfreigabe:** Soll die vorgeschlagene Zielarchitektur und Reihenfolge als Arbeitsgrundlage dienen? Dies allein autorisiert weder Produktcode noch Backlogänderung, Veröffentlichung oder Maschine.
2. **Erstes gesondertes Arbeitspaket:** Soll zunächst ausschließlich eine offline testbare Lösung für Bild-/Originaldateischutz samt Regression ausgearbeitet werden? Verhaltensänderung, Ausführung und späteres Einspielen jeweils nur nach eigenem Go.
3. **Quellen/Dokumentation:** Falls vorhanden, bitte die oben fehlenden drei Dokumente/Archive und für E1/E4 relevante Feldlogs/aktuelle Konfiguration sowie historische Fehl-STLs bereitstellen. D1: Soll die belegte LIVE-Lüfterstufe später ins Handbuch aufgenommen werden? H3: erwartete Cake-Platten, Reorientierung und Restmaterial anhand eines Beispiels klären.

**Stopp:** Keine Produktarbeit ohne ausdrückliche passende Freigabe. G1–G5 und das Textur-Rückteil von `GENERATORS_TOOLS.pdf` bleiben gesperrt; die oben offengelegten unbeabsichtigten Tests sind keine Freigabe und begründen keine weitere G-Arbeit. Keine Dateien löschen oder veröffentlichen, keine Maschine bewegen.
