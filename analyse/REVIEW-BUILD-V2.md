# R2-2026-11-15.1 V2 – lokaler Review-Build

**Status: nicht vollständig, nicht installations- oder druckfreigegeben.** Dies ist ein lokaler Quell-/Review-Build, kein veröffentlichtes GitHub-Release und kein Update-ZIP. Er enthält den bestehenden Projektbestand und die neuen Arbeiten, ersetzt aber weder die geforderte Gesamtarchitektur noch die fehlenden Software-/Hardware-Abnahmen. G1–G5 und das Textur-Rückteil bleiben gesperrt. Keine Hardware wurde bewegt, keine Installation oder Veröffentlichung vorgenommen. Die Core-Versionsstempel bleiben deshalb bewusst auf dem bisherigen V1-Stand; ein Archivname ist kein Beleg für einen produktiven V2.

## In diesem Stand

1. **Bestand und Rückweg:** `backups/r2_postproc_R2-2026-11-13.1_V1.py` ist bytegleich mit der ursprünglichen aktiven Engine, SHA-256 `5e7639d7dd1fea04642fc5fd5286e0ad529a0f27055042b0bf3e1f5b33593c63`; `sha256sum -c backups/SHA256SUMS` prüft sie. Die Kopie ist ein Backup, kein getesteter automatischer Umschalter. Die sechs Goldens prüfen nun das Backup als historische Referenz: fünf Kandidatenausgaben bleiben unverändert; die eine gewollte Änderung für `m82_zhop` ist in `golden_zscan_expected.json` separat und mit altem/neuem Hash festgehalten. Keine Aussage über alle Funktionen.
2. **Aktive Engine und Next:** Bildauswahl kopiert Unterordnerbilder kollisionssicher statt das Root-Original zu überschreiben. Die Queue entpackt den Auftrag vor einer Abbruchprüfung, gibt bei STOP die tatsächlich wartenden Schlüssel frei und bewahrt einen laufenden bzw. noch lebenden Zombie-Schlüssel. Ein übersprungener getaggter oder Plotter-Job wird nicht vor dem Skip durch die optionale Retract-Umschreibung verändert. Der Z-Scan prüft positive E-Deltas statt nur das Vorhandensein eines E-Worts (M82/M83/G92 und Klipper-G91-Modell); er beginnt weiter mit der Dateiannahme E=0 und ist kein allgemeiner Interpreter für unbekannte Makros, Koordinaten-Resets und alle Dialekte. Der STL-Export aktualisiert das E-Register auch für weggefilterte Segmente; das belegt keine korrekte Gesamtgeometrie. Die CENTER-only-Polygon-Näherung berücksichtigt E-Deltas, G92 E und relative XY; bei G92 X/Y, G20 und Bögen wird sie nicht angewandt. Sie ist weiterhin nur eine begrenzte Bounding-Box-Schätzung, kein nachgewiesener Objektumriss; unbekannte Makros und andere Zustandsänderungen sind nicht vollständig modelliert. Diese Änderungen liegen in beiden Engine-Dateien. Die anderen ursprünglichen Watcher-/In-place-Verträge bleiben bestehen, insbesondere wird unmarkiertes G-Code im herkömmlichen Watcher weiterhin in-place bearbeitet. **Kein allgemeiner Originalschutz im aktiven Watcher.**
3. **Neuer Offline-Dienst:** `tools/r2_offline.py report quelle.gcode bericht.json` analysiert einen privaten Snapshot, schreibt eine JSON-Evidenzdatei nur unter neuem Namen und überschreibt keine vorhandene Datei. `derive quelle.gcode neue-datei.gcode` wendet die bestehende Next-Engine auf einen privaten Snapshot an und veröffentlicht eine separate Kopie; Retract-Rewrite ist aus. Der JSON-Bericht auf stdout enthält Input-/Output-Hashes und Engine-Identität. Die Ausgabe ist **nicht druckzertifiziert** und die Produktsemantik der alten Engine ist dadurch nicht neu bewiesen. Quellenänderungen werden vor Veröffentlichung auf Dateimetadaten, Identität und SHA geprüft; kein Schutz gegen jeden mutwilligen Race oder Änderungen nach der letzten Prüfung. Hardlink-unfähige Dateisysteme scheitern statt zu überschreiben. Nach einem Prozessabbruch kann ein temporäres Verzeichnis zurückbleiben; bei einem Verzeichnis-fsync-Fehler kann die Ausgabe bereits existieren, obwohl die Dauerhaftigkeit nicht bestätigt wurde. Der Dienst ist noch nicht mit Watcher, Job-UI, Moonraker-Registrierung oder Drucker verbunden.
4. **Shadow/Report:** Ohne Annahmen sind für die drei Feldfixtures weiterhin **0 vollständig bekannte XYZ-Endpunkte** nachgewiesen. `--assume-passive COMMAND` ist ausschließlich eine ausdrücklich ausgewiesene hypothetische Analyseannahme; keine automatische Aussage über Makros, G28, Retracts oder Toolwechsel. Unter den in `analyse/offline_field_probe.py` gelisteten bewusst unbewiesenen Annahmen ergeben sich Bigrose 250.058, Rose 147.796 und Stringart 114.326 rechnerisch bekannte Endpunkte. Diese Zahlen sind **keine** validierten physischen Positionen, keine Bewegungs-/Druckfreigabe und kein bestandener Feldtest der Makrosemantik. Details und unveränderte Archivhashes: `analyse/testprotokolle/offline_field_probe.log`. Rohkommentare/Objektbefehle sind Evidenz, keine allgemein korrekte Objekt-, Geometrie-, Pattern- oder Featureklassifizierung.
5. **Makros:** Skalare Override-Aktivierung, Flow-Ziel und PA-Retractauswahl korrigiert; Ironing-Ergebnis zeigt den gespeicherten Kartenwert ohne unsichere automatische Umrechnung mm/s in Prozent; Details und Verhaltensänderungen in `UMSETZUNG-OVERRIDE-UND-KALIBRIERUNG.md`. `PRINT_START` behält die übergebene Layerzahl nach dem Live-Reset; Layer-1-Pause wird ausdrücklich abgelehnt statt wirkungslos vorgemerkt. Optionaler kompatibler Beeper wird vor `SET_PIN` geprüft. Kein vollständiger Klipper-/Moonraker- oder Druckertest.

## Bekannte Abnahmeblocker

- Die vollständigen Masterkonzept-Pässe 0–11, zuverlässige Makro-/Arc-Semantik, Objekt-/Layer-Identität, Geometrie/Topologie und validierte Feature-/Pattern-Erkennung sind nicht fertig. Ground-Truth-Daten und einige Original-Spezifikationen fehlen weiterhin.
- Originalschutz, Jobzustände und Fehlerbehandlung sind nicht durchgängig in alle bestehenden Watcher-/Generator-/Dateipfade integriert. Die Queueprüfung ist fokussiert und keine vollständige konkurrierende End-to-End-Simulation. Der Offline-Dienst liefert bei `derive` keinen Moonraker-Registrierungsnachweis und keine Maschinenfreigabe.
- STL-/OBJ-Richtigkeit und Slicer-Reimport, Cake H2/H3, Layer-Z-Hop-/Objektfolgen, AS-SLICED-/LEGACY-Non-Interference, Timer, Web-Fallback-Gesamtabgleich, Konfigurationskompatibilität und konkrete Hardware-/Ressourcengrenzen sind nicht vollständig abgeschlossen. Einige davon benötigen fehlende Daten bzw. eine separat freizugebende Hardwareprüfung.
- Sicherheitsrelevante Änderungen an Overrides, PA und Start haben ausschließlich begrenzte Offline-Render-/Parser-Tests; sie dürfen nicht als reale Installationsfreigabe interpretiert werden. Das Projekt-Backlog wurde nicht geändert.

## Offline-Checks

Der Sammellauf `analyse/testprotokolle/review_v2_checks.log` endete mit Exit 0: 123 Unit-Testmethoden über beide Engines und die Offline-/Makro-/Bundle-Tests, sechs Golden-Fälle je Engine (davon eine ausdrücklich geänderte Erwartung), 13 synthetische Dialektfamilien/46 Tag-Treffer sowie 15 statische Crash-Guards und sieben Gegenmutationen. Die Z-Scan-Korrektur legte offen, dass der alte `r110`-Generator für M82 wiederholt E0 statt zunehmender absoluter E-Werte ausgab; die Testdaten wurden für M82 auf realen positiven E-Zuwachs korrigiert, bevor der Lauf erneut bestand. Diese Zahlen sind kein Nachweis einer vollständigen Integration. Tests der gesperrten Familien wurden nicht gestartet. Jinja2 und der nicht mitgelieferte, hashgeprüfte Upstream-Klipper-Parser werden für die Makroregressionen benötigt; ohne Parser überspringt die Testsuite explizit vier Fälle. Das Sammelskript verweigert in diesem Fall den Lauf. Der Node-basierte Web-Ausdruckstest überspringt ohne Node; das Sammelskript verlangt Node. Keine der Tests verbindet sich mit einem Drucker.

```text
python3 tools/test_r2_offline.py
python3 tools/test_r2_shadow.py
R2_TEST_ENGINE=active python3 tools/test_image_pick_next.py
R2_TEST_ENGINE=active python3 tools/test_queue_next.py
R2_TEST_ENGINE=active python3 tools/test_process_guards.py
R2_TEST_ENGINE=active python3 tools/test_zscan_modes.py
R2_TEST_ENGINE=active python3 tools/test_stl_extrusion_state.py
R2_TEST_ENGINE=active python3 tools/test_object_bbox_modes.py
python3 tools/test_image_pick_next.py
python3 tools/test_queue_next.py
python3 tools/test_process_guards.py
python3 tools/test_zscan_modes.py
python3 tools/test_stl_extrusion_state.py
python3 tools/test_object_bbox_modes.py
python3 tools/test_review_bundle.py
python3 analyse/test_golden_baseline.py
python3 analyse/golden_baseline.py verify --engine stable
python3 analyse/golden_baseline.py verify --engine next
python3 tools/test_override_flow_regressions.py
sha256sum -c backups/SHA256SUMS
```

Das Review-Archiv wird durch `tools/build_review_bundle.py` reproduzierbar mit Inhaltsmanifest gebaut und validiert. Es ist absichtlich kein `klipper-e3-r2d2-UPDATE-*.zip` und nicht zur Installation gedacht.
