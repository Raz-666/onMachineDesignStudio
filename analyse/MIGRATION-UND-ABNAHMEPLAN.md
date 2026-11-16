# Zielarchitektur, Migration und Abnahme – Freigabevorlage

Dieser Plan ist **kein Implementierungsauftrag**. Das stabile System und alle vorhandenen Funktionen/Timer bleiben erhalten, bis Ersatz und Regression nachgewiesen und die jeweilige Änderung freigegeben sind. Übergabe verlangt Arbeit am experimentellen `tools/r2_postproc_next.py` statt direkt am stabilen Pfad; das allein ist keine Freigabe. Es gibt keinen unbelegten Anspruch auf exakte Semantik beliebiger G-Codes.

## 1. Zielverträge und Grenzen

- **Maschinenprofil**: getrennte mechanische Grenzen, druckbare Bettfläche, Probe-Reichweite/Offset, Generatorfläche und Park-/Wipe-Bereiche, Düse/Extruder, Kinematik, optionale Sensoren/Displays/LEDs. Herkunft, Messstand, Version und unbekannte Werte speichern; weder Bett noch Probe einfach aus Axis-Max ableiten. Nicht erkannte Hardware: explizites Fallback oder Verweigerung, nie still bewegen.
- **File/Image Service**: immutable Quelle mit Hash, Pfadidentität und Rechteprüfung; Auswahl und Kopie mit kollisionssicheren Namen; atomare Ausgabe, Validierung, Registrierung und Herkunftsmanifest (Quelle, Tool, Version, Parameter, Profil, Schritte). Bestehende Root-Symlinks und Toolkonventionen via Adapter erhalten. Keine gesicherten Originale überschreiben.
- **Job Service**: eindeutige IDs, Queue-, Warte-, Lauf-, Fehler-, Abbruch-, Validierungs-, Registrierungs- und Endzustände, Wiederanlauf/Timeout, Ressourcenlimits und im Fehlerfall eindeutig abrufbare Meldung. Off-thread/-process; Druck und Homing haben Vorrang. Benachrichtigungen/Sound zentral und austauschbar; fehlende Hardware darf nicht nichtkritische Vorgänge stoppen. Prozessisolation als Option, nicht bereits gemessenes Leistungsversprechen.
- **Parser/State**: verlustfreie Rohzeilen mit Position, Befehl/Parametern und unbekannten Events; modal normalisierte Moves (absolute XYZ, E-Delta, Feed, Einheiten, Tool, G92/Offsets, Anfangszustand, arcs, Extrusionsmodus und Unsicherheit). Kein automatisches Umetikettieren unbekannter/mehrdeutiger Syntax.
- **Objekt/Layer**: stabile Objekt-ID mit Herkunft/Confidence, Instanzen/Islands und Hilfsgeometrie getrennt; Schichten/Ereignisse einschließlich Z-Hop, variable Höhen, Vase, layer-by-layer/object-by-object. Nutzer muss gezielt ein/mehrere/alle Objekte auswählen können, bei unklaren Grenzen Warnung. IDs über Bearbeitungsstufen erhalten oder Abbildung dokumentieren.
- **Geometrie/Evidenz**: Paths/Loops/Holes/Footprints und Nachbarschichten getrennt von Feature-Rolle und Pattern; Quell-Tags als Belege, nicht unhinterfragbare Wahrheit. Evidence-Provenienz, Alternativen, UNKNOWN/AMBIGUOUS und Kalibrierung an versionierter Ground Truth. C1–C9 nur als Bestand/Kompatibilität mit nachvollziehbarer Einordnung.
- **Ausgabe/Adapter**: zuerst Analyse-Sidecar, keine veränderten Befehle; danach nur separat freigegebene abgeleitete Kopien. `APPLY_TYPE`, `_FILE_INFO`, `LAYER_MARK`, Live-/Preprint-/LCD-/Web- und Timerverträge durch Adapter erhalten. AS SLICED und LEGACY als getrennte, tatsächlich getestete Verhaltensverträge, nicht nur Labels. Explizite Benutzerwahl, keine stillen Parameteränderungen.

## 2. Masterkonzept Pass 0–11

Diese Reihenfolge folgt `analyse/uebergabe-quellen/GCode_Reverse_Engineering_Masterkonzept.md:755–824`; Zuordnung ist Soll zu vorhandenem Anknüpfungspunkt, **keine Behauptung**, dass die Pässe im Bestand vollständig existieren.

| Pass | Ziel | Anschluss im Bestand / wichtigste Lücke |
|---|---|---|
| 0 Rohdaten/Kommentare | Quelle erfassen und Herkunft sichern | `process:19718` liest; verändert später Datei. Hash/sidecar fehlen als einheitlicher Vertrag. |
| 1 Syntax/Zustand | Modi, Einheiten, Extruder, Unbekanntes | separate Parser; G92/relatives XYZ nicht einheitlich (`rekonstruktionsproben.log`). |
| 2 Bewegungen | normalisierte Start-/Endpunkte, Länge, Delta E | Scanner vorhanden; Vergleich je Zeile und Arc/Tool-Abdeckung offen. |
| 3 Layer/Z | Ebenen/Hops/Vase | `_ZScan:20246` E-Wort-Probe erzeugt Hop-Fehlmarker; Positionen und Verbraucher testen. |
| 4 Extrusion/Kinematik | E-/F-/Volumenprofile und Limits | `_GeomScan`/MAXRATE; fehlende vollständige Modal-/Hardwarebelege. |
| 5 Pfade/Komponenten | geordnete Pfade, Objektgrenzen/Instanzen | GeomScan/EXCLUDE_OBJECT; universelle ID-/Inselzuordnung nicht nachgewiesen. |
| 6 2D | Konturen/Loch/Footprint/Umriss | `_LayerBitmap:20322`; allgemeiner Geometrievertrag nicht belegt. |
| 7 3D/Inter-Layer | Kontakt, Stützen, Überhänge | `_airscan193:21158`; Ground Truth und Mehrfachobjekte fehlen. |
| 8 Feature | mehrere Belege, Alternativen, Unsicherheit | TYPE_MAP und `_resolve_block:21359`; fixer Wert 0,7 keine kalibrierte Wahrscheinlichkeit. |
| 9 Pattern | Muster unabhängig von Rolle | Alias-Zuordnungen vorhanden; allgemeine unabhängige Mustererkennung nicht belegt. |
| 10 Konsistenz | Tag/Geometrie/Layer/Objekt-Konflikt | `_sequence_audit193:508`; sequentielle Objekte als Gegenfall. |
| 11 Ausgabe | nichtdestruktives Sidecar, später optional R2-Kopie | vorhandene `_FILE_INFO`/Marker und `process`; Originalschutz und explizite Outputwahl fehlen als Gesamtvertrag. |

Abschnittsweise Details und Quelldifferenzen: `MASTERKONZEPT-ABSCHNITTSABGLEICH.md`; Slicer-Alias-Herkunft: `ALIASE-QUELLEN-CODE.tsv`.

## 3. Reihenfolge und Rückweg

0. **Jetzt:** Freigabestopp, Nachweise und offene Risiken übergeben. Keine Konfig, G-Code-Ausführung, Veröffentlichung oder TODO-Änderung.
1. Nach Architektur-Go: reproduzierbare Bestands-Goldens und Testkorpus mit sicheren temporären Kopien, Quellhashes, gespeicherten Parametern, Baseline für RAM/CPU/I/O/Timing; nur nicht-invasive Offlinearbeit. Separate Entscheidung über neue Fehlerbehebungen.
2. Je konkreter Freigabe zuerst Original-/Bildschutz und Job-Zustandsvertrag isoliert absichern; feste Testfälle für Kollision, Symlink, Abbruch, Timeout, fehlende/kaputte Ausgabe, Registrierung und Benachrichtigung. Keine UI- oder Drucksemantik nebenbei ändern.
3. `next` als Shadow: Parser/Modalmodell (Pässe 0–2), dann Layer/E/Objekt (3–5), dann Geometrie/Topologie/Features (6–10), schließlich Sidecar (11). Stable liefert weiterhin Ausgabe; Shadow darf keine ausführbaren Bewegungen erzeugen. Pro Schritt Versionsschema, begrenzter Ressourceneinsatz und Abweichungsbericht.
4. Erst nach bestandenen Offline-Gates und eigenem Go Adapter für eine kleine Funktionsfamilie, AS SLICED/LEGACY, Live-/Timer und Datei-/Queue-Flüsse vergleichen. A/B, Migrationsprotokoll und ein Schalter mit Rückfall auf den unveränderten Stable-Pfad. Kein automatischer Commit/Tausch.
5. Simulation gegen passende Klipper-/Moonraker-Version mit gefakter Hardware, anschließend **nur nach separater Maschinenfreigabe** ein beaufsichtigter Testplan mit Not-Aus, sicherer Temperatur/Geometrie und Rollback/Backups; kein Test für Sonde/Gantry durch bloßes Architektur-Go.
6. Dokumentation und Backlog-Disposition nach geprüfter Funktion gesondert freigeben. G1–G5 und Textur-Rückteil bleiben bis spezifischer Freigabe ausgespart.

Aufwand: Größenordnung und Dauer sind **noch nicht belastbar**; zuerst Korpus, Zielplattform und messbares Ressourcenbudget festlegen. P0-Dateischutz/Probe sind priorisiert, aber deren tatsächliche Änderungen erfordern gesonderte Zustimmung. Kein Zeitversprechen.

## 4. Testmatrix und Abnahmestufen

| Klasse | Konkrete Mindestfälle / Auswertung |
|---|---|
| Parser | G90/G91, M82/M83, G92, G20/G21, G2/G3, Tn, nicht unterstützte/kaputte Eingabe, Modal-Feed, E-only/Retract; Zeilenorakel und unbekannte Events. |
| Layer | kommentiert/ohne Kommentare, 1. Ebene, Z-Hop mit E fehlt/E0/E-negativ/E-positiv, Variable Layer, Vase, Objekte sequentiell; Markerposition und Current/Total sowie Pause/Stop separat. |
| Objekt/Geometrie | ein/zwei Objekte, by-layer/by-object, mehrere Instanzen, mehrere Islands in einem Objekt, Support/Brim, Objektzentrum Twist/Scale, unklare Grenzen, aufeinanderfolgende Stufen; Extrusionsvolumen, G92, Löcher/Wandstärke/Innen-/Außenkontur. |
| Feature/Pattern | versionierte reale Slicer-Ausgaben + synthetische Negativfälle; Präzision/Recall je Feature, Verwechslungsmatrix, UNKNOWN-Quote, Konfliktgründe und unabhängige Quellen. Keine pauschale 100-%-Zusage. |
| Original/Datei | Vorher-/Nachher-SHA aller Eingaben; basename-Kollision, root/subfolder, Sonderzeichen, Traversal/Symlink, bestehende Ziele, Abbruch bei voller Platte/Fehlern, Registrierung, Endstatus, Nebenwirkungen. |
| Queue/UI | warten/running/cancel/kill/timeout/zombie, Neustart; angezeigte Liste/Job-ID/Ausgabe/Meldung, keine Phantom-Erfolge; LCD/Web-Äquivalenz, Offline-Fallback und Version. |
| R2-Verträge | Golden-Dateien, Markerreihenfolge, `_FILE_INFO`, CUSTOM, AS SLICED vs LEGACY, Live-Overrides/Fan/PA, Start-/Ende-/Purge-/Pause-Sequenzen und alle Delayed-Gcodes. Statische Tests plus Stub-Dispatch; reale zeitliche Erreichbarkeit getrennt. |
| STL/OBJ | M82/M83 mit G92/Supportfilter, E/Width, Löcher/mehrere Komponenten, Meshqualität, Einheiten und Reimport in realen Slicer; bekannte historische Fehl-Exporte sobald bereitgestellt. |
| Hardware/Last | Ohne/mit Beeper/LED/Plugin/Sensor; Display/Encoder; Cartesian/CoreXY je konkretem Gerät, Probe/Dual-Z; echte CPU/RSS, I/O, Reactor-Latenz, MCU-Queue; keine Hardwarefahrt vor separatem Go. |

Abnahme ist gestuft: A Offline-Unit/Mutation + Goldens; B Integrations-/Fehlerfälle mit passender Softwareversion; C nichtbewegte Konfigurations-/Ressourcenmessung; D beaufsichtigte Hardware. Jede Stufe dokumentiert **Messung, Grenzen und Rollback**. Ein grüner Renderer oder synthetischer Test ist kein Nachweis für B–D.
