# Architekturstart: Offline-Golden und Ressourcenbasis

Die Architektur ist als Arbeitsgrundlage freigegeben. Dieser erste Schritt bleibt bei der im Plan vorgesehenen **nicht-invasiven Offline-Baseline**; er repariert oder aktiviert noch keinen Produktpfad. Keine Konfiguration, Makros, Watcher, Drucker, G-Code-Ausführung, G1–G5 oder das gesperrte PDF-Rückteil wurden verändert oder getestet.

## Was jetzt reproduzierbar ist

`analyse/golden_baseline.py` startet für jeden Fall einen eigenen Python-Prozess mit dem unveränderten stabilen `tools/r2_postproc.py`. Drei feste synthetische Eingaben (M83 mit Layer-Kommentaren, M82 mit Z-Hop/E0, bereits getaggt) und drei vorhandene gzip-Feldfixtures (`bigrose`, `rose`, `stringart`) werden verarbeitet. Gzip-Archive werden nur gelesen, in ein temporäres Verzeichnis entpackt und vor/nach der Verarbeitung erneut gehasht; **nur diese Arbeitskopie** wird an das bestehende in-place arbeitende `process()` übergeben. Kein Netzwerk oder Watcher wird gestartet.

Die versionierte Referenz `golden_baseline.json` enthält Engine-SHA256, feste Parameter (`dry=False`, `verbose=False`, `retract_rewrite=False`), Quellarchiv-/entpackte Eingabe- und Ausgabesha256, Dateigrößen und einen ausgewählten Summary-Ausschnitt. Sie konserviert den **Ist-Zustand**, auch bekannte Fehler: Das bedeutet **nicht**, dass die erzeugte Datei oder die Layerzählung fachlich richtig ist. Für beabsichtigte zukünftige Verhaltensänderungen muss der Delta getrennt geprüft und eine Referenzänderung begründet/freigegeben werden; die Referenz nicht automatisch aktualisieren.

Die Referenz wurde aufgezeichnet und anschließend in unabhängigen Prozessen mehrfach erfolgreich verglichen. Der Test `test_end_to_end_mutated_golden_fails` ändert in einem temporären Exemplar den erwarteten Output-Hash und prüft, dass der echte CLI-Lauf Exit 1 liefert. Weitere Tests prüfen mutierten Input-/Output-Hash, Summary, Engine-Hash, fehlende/zusätzliche Fälle/Felder sowie eine echte synthetische Ausführung. **6/6 Tests bestanden**, einschließlich des negativen End-to-End-Fixpunkts. Ein Vergleich von `next` gegen das stabile Golden bestand für dieselben sechs Fälle; er ignoriert dabei nur die andere Engine-Identität und prüft separat, dass die aktuelle Stable-Datei noch dem Golden entspricht. Das beweist keine Äquivalenz aller Funktionen oder des Watchers. Protokolle: `testprotokolle/golden_baseline_unittest.log`, `testprotokolle/golden_baseline_verify.log`, `testprotokolle/golden_baseline_next.log`.

Wiederholung im Projektroot, Python 3 (stdlib, Linux für `/proc`-I/O-Werte):

```bash
python3 analyse/test_golden_baseline.py
python3 analyse/golden_baseline.py verify
python3 analyse/golden_baseline.py verify --engine next
```

Fehlende oder veränderte Fixtures führen zu einem Fehler, nicht zu einem stillen Skip. `record` druckt einen Kandidaten auf stdout und überschreibt selbst keine Referenz; das ist keine Aufforderung, den Golden neu einzufrieren.

## Erste Ressourcenmessung und Grenzen

Auf diesem x86-64-Linux-Container, Python 3.11.2, aus `golden_baseline_verify.log`:

| Eingabe | entpackt | Prozess-Wandzeit | CPU User | Peak-RSS des gesamten Kindprozesses |
|---|---:|---:|---:|---:|
| bigrose | 12.366.187 Bytes | 3,19 s | 3,17 s | 22.872 KiB |
| rose | 5.151.986 Bytes | 1,72 s | 1,70 s | 23.200 KiB |
| stringart | 4.330.515 Bytes | 1,41 s | 1,40 s | 23.308 KiB |

Die Messung ist ein einzelner warmer Lauf **dieses Containers**, keine Pi-Zero-, Klipper-Reactor-, MCU-, SD-Karten- oder Drucklastmessung und kein Ressourcenlimit. Peak-RSS enthält Import und Entpacken und ist deshalb nicht nur `process()` zuzuschreiben. `rchar`/`wchar` zählen Prozess-I/O-Aufrufe, `read_bytes`/`write_bytes` Linux-Kernelzähler; Cache und Dateisystem beeinflussen sie, `read_bytes=0` beweist keine physisch kostenlose Speicherung. Zeiterfassung und I/O-Deltas umfassen nur den `process()`-Aufruf; Eingabe-Entpacken und abschließende SHA-Berechnung liegen außerhalb. Unterschiedliche Maschine, Last und Dateisystem können stark abweichen.

## Nachfolgender Umsetzungsstand

**Aktualisierung:** Die ursprüngliche Engine liegt hashverifiziert in `backups/r2_postproc_R2-2026-11-13.1_V1.py`. Die Golden-Prüfung verifiziert diese Referenz und vergleicht sechs Ausgaben von aktivem und Next-Pfad: fünf bleiben unverändert, für `m82_zhop` ist eine gezielt dokumentierte Änderung hinterlegt (`golden_zscan_expected.json`). Die folgende Beschreibung ist historisch; aktueller Stand in `analyse/REVIEW-BUILD-V2.md`.

Nach der späteren Präzisierung des Nutzers, mit den freigegebenen Aufgaben ohne laufende Zwischenfreigaben weiterzumachen, wurde der Bildkopierpfad in `next` abgesichert und ein isolierter Shadow-Prototyp begonnen. Einzelheiten und Grenzen stehen in `analyse/ARCHITEKTUR-UMSETZUNG-BILDSCHUTZ-UND-SHADOW.md`. Die ursprüngliche Stable-Engine wurde nicht geändert; dort bleibt das Kollisionsrisiko bestehen. Hardwareprüfung und Einspielen sind weiterhin getrennt von dieser Offline-Arbeit.
