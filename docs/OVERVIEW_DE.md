# R2-D2 / onMachineDesignStudio — Systemüberblick

**Stand der Beschreibung:** Repository-Stand `main` vom 18. November 2026 (Build-Angabe im Quellcode: R2-2026-11-18.2). Diese Übersicht beschreibt dokumentierte Fähigkeiten und Architektur. Sie ist keine unabhängige Sicherheitszertifizierung und keine Garantie, dass jede Funktion auf jeder Hardware aktiv ist.

## Kurzbeschreibung

R2-D2 ist eine umfangreiche, offene Steuerungs- und Kreativ-Erweiterung für Klipper-basierte FDM-Drucker. Sie verbindet G-Code-Makros, LCD-Menüs, Moonraker/Mainsail, einen Python-Datei-Watcher, Druckdatei-Analyse und zahlreiche Generatoren. Der Schwerpunkt liegt darauf, Druckdateien nicht nur auszuführen, sondern ihre Layer, Features und Parameter zu erfassen und dem Benutzer vor und während des Drucks gezielte Entscheidungen und Eingriffe zu ermöglichen.

Das Referenzgerät ist ein modifizierter Ender-3 mit Klipper, Moonraker, Mainsail, SKR Mini E3 V3 und 12864-LCD. Laut `COMPATIBILITY.md` sind kartesische und CoreXY-FDM-Drucker Zielplattformen. Delta, Belt-Drucker und Resin sind nicht im vorgesehenen Kompatibilitätsumfang.

## Wie das System aufgebaut ist

```text
Orca/Cura/andere G-Code-Quelle
            │
            ├─ Slicer-Skripte (optional): Feature-, Layer- und Objektmarker
            ▼
G-Code-Verzeichnis auf dem Klipper-Host
            │
            ├─ systemd: tools/r2_postproc.py
            │     analysiert/metadatiert Dateien, erzeugt Dateien und Vorschauen
            ├─ tools/r2_job_service.py
            │     Jobzustände, Originalarchivierung, Ausgabevalidierung
            ▼
Klipper-Makros und _STATE
            ├─ PRINT_START / PRINT_END, Interceptors, Layer- und Featurelogik
            ├─ LCD-Menü: menus/lcd_menues.cfg
            └─ Moonraker/Web-LCD: web/r2_menu.py + web/index.html
            ▼
Klipper-Host → MCU → Druckerhardware
```

`macros/01_state.cfg` trennt persistente Einstellungen in `save_variables` von flüchtigem Laufzeitzustand in `_STATE`. Die Makros treffen Entscheidungen während des Drucks. Rechenintensive G-Code-Verarbeitung und Generierung sollen dagegen auf dem Host-Watcher laufen und nicht in Jinja-Makros des Klipper-Reaktors.

## Funktionsübersicht

### Druckstart, Material und Dateiverständnis

- Startdialog mit den Modi **AS SLICED** (Datei möglichst unverändert gemäß vorgesehener Regel) und **AS LEGACY** (R2-Übersteuerungen und -Vorbereitung aktiv), plus Abbruch.
- Druckstart-Choreografie mit Homing, optionaler Gantry-Synchronisierung, Bett- und Hotend-Aufheizen, Mesh-Entscheidung und Prime/Purge.
- Prioritätsmodell für viele Einstellungen: aktivierter Benutzer-Override, danach Dateiwert, danach Materialpreset.
- Materialprofile für PLA, PETG, ABS, ASA und TPU; speicher- und ladbare Presets und optional dateibezogene Profile.
- Layer-1-/Layer-2-Temperaturen und -Regeln für Lüfter und Geschwindigkeit; Z-Tracking als Rückfall, wenn Layer-Marker fehlen.
- Erkennung bzw. Behandlung älterer G-Code-Dateien, die `PRINT_START`, `LAYER_MARK` oder Featuremarker nicht enthalten. Die Verfügbarkeit und Vollständigkeit hängt von der Datei ab.
- Datei-Vorschau und `_FILE_INFO`: unter anderem Slicer-/Firmwarehinweise, Temperaturen, Layerhöhe, Material, Features, gemessene Feature-Geschwindigkeiten und -Beschleunigungen.

### Live-Tuning und Feature-Erkennung

- Globale und featurebezogene Geschwindigkeit, Beschleunigung, Flow und Pressure Advance (PA); zusätzlich PA-Smoothing und live einstellbare Retraktion, soweit Firmware-Rektraktion eingerichtet ist.
- Lüftersteuerung mit Live-Wert, Skalierung, Hold/Clamp und Layer-1-Regeln; weitere Regelungen etwa für Brücken.
- Live-Temperaturen, Z-Babystepping, Bewegungsgrenzen und Parameter wie max. Geschwindigkeit, Mindest-Cruise-Ratio und Square-Corner-Velocity.
- Feature-Kategorien umfassen unter anderem Außen-/Innenwand, Sparse-/Solid-Infill, obere/untere Oberfläche, Bridge, Internal Bridge, Gap, Support, Ironing, Skirt, Brim, Prime Tower, Overhang und Custom. Für unbekannte Featureformen sind begrenzte nummerierte C1–C9-Slots dokumentiert.
- `APPLY_TYPE` schaltet an Featuregrenzen um; `LAYER_MARK` markiert Layergrenzen. Slicer-Postprozessoren und der Host-Watcher können die nötigen Marker liefern.
- Der Featureparser normalisiert mehrere Slicer-Vokabulare. Unbekannte Formen sollen nicht stillschweigend die Overrides des vorherigen Features erben, sondern als Custom sichtbar bleiben.

### Pause, Filament und Objektkontrolle

- Pause, Resume, geplanter Pausepunkt, Pause bei Layer N, geplanter normaler Druckstopp bei Layer N und zweistufige Abbruchbestätigung.
- Filament laden/entladen, M600-Filamentwechsel, Runout-Reaktion und Purge beim Fortsetzen; Sensorfunktionen benötigen passende Hardwarekonfiguration.
- Parken mit Z-Lift, Retraktion, Objekt-/Bettbezug und Resume-Ablauf; konkrete Sicherheit hängt von korrekt gesetzten Bett-, Achs- und Probeparametern ab.
- Einzelobjekte in Mehrfachdrucken überspringen, wenn die Datei Klippers Objektinformationen enthält.
- Z-Hop über Firmware-Retraktion als optionale Funktion.

### Mesh, Wartung und Kalibrierung

- Bed-Mesh-Strategien ON/AUTO/OFF, Profilverwaltung und adaptive Kalibrierung über KAMP oder Klippers native Möglichkeiten, abhängig von Installation und Objektinformationen.
- Leveling, Schraubenneigung, Probe-Z-Offset, Extruder-Kalibrierung und PID-Tuning für Hotend und Bett.
- Input-Shaper-Messung mit geeignetem Beschleunigungssensor; außerdem dokumentierte manuelle Shaper-Einstellungen ohne Messsensor.
- Kalibrierungsgeneratoren für Temperaturturm, PA/PA-Smoothing, Flow, Retraktion, Brücken und Ironing.
- Düsenreinigung, Filamentpflege/Kaltzug, Host-/Firmware-Neustart, Status- und Selbsttests.

### Generatoren und kreative Dateiverarbeitung

Die Tools-Menüs und der Postprozessor können laut Projektunterlagen G-Code für folgende Anwendungsfälle erzeugen oder umarbeiten:

- **Layer-Range:** Ausschnitt eines bestehenden Drucks; optionale Boden-/Deckschichten, Brim und zentrierte Löcher.
- **Labels:** Textplatten, mehrere Schriftstile, Loch-/Layoutoptionen und optionaler Farbwechsel.
- **Plotter:** PNG/JPEG/SVG/Vektor-PDF/TXT in Stift-G-Code; Zeichen-/Punktmodi, Skalierung, Position und Stiftversatz.
- **Lithophane** und **ColorPic:** Bild-zu-Relief bzw. mehrfarbige gestufte Bildausgabe mit dazugehörigen Druckabläufen.
- **Frames/Display Cases:** Rahmen, Rückplatte, Stand, Aufhängung und unterschiedliche Verschlüsse.
- **Kabelbinder:** klassische Einweg- und wiederverwendbare LOOP-Varianten.
- **Winkel- und Flachverbinder:** parametrisierte Platten, Bohrungen, Senkungen und Versteifungen.
- **Dichtungen:** flache oder profilierte Ringe.
- **Sprayschablonen:** Tonbänder eines Bildes als Platten mit automatischen Stegen und Passloch-Registrierung.
- **Gießformen:** zweiteilige Formen um einen fertigen Druck (Äquator-Teilung, Einguss mit Trichter, Entlüftungen, Dübel-Registrierung) sowie Positiv-Master; über das Generatoren-Menü und als Toolchain-Schritt.
- **Bricks/Kits/Figures:** Systembausteine, aus einem G-Code abgeleitete Bausätze sowie zusammensteckbare Figuren.
- **String Art:** Bild-/Spiralstrukturen mit Ankerrahmen und gestaffelten Strängen.
- **Texturierung:** vorhandene Datei (insbesondere Außenwände) mit reproduzierbarer Fuzzy-, Muster- oder Bildtextur versehen.
- **Dateiwerkzeuge:** unter anderem Skalieren, Ebenen schneiden/teilen, G-Code korrigieren, Retraktion/volumetrische E-Werte behandeln und ausgewählte Ausschnitte erstellen.

Generatoren erzeugen Dateien, keine zertifizierten Bauteile. Passung, Festigkeit, Werkstoff, elektrische/thermische Belastbarkeit und Eignung für sicherheitskritische Anwendungen müssen separat geprüft werden.

### Web-Oberfläche, Betrieb und Diagnose

- `web/index.html` ist eine separate Browseroberfläche, die das LCD-Menü spiegelt und Dashboard, G-Code-Eingabe, Status, Benachrichtigungen und Konsole kombiniert.
- `web/r2_menu.py` stellt Moonraker-Endpunkte für Menü-/Druckerstatus und Hostinformationen bereit; Caching und Datenreduktion sollen die Hostlast begrenzen.
- `setup.sh` und `update.sh` unterstützen Setup/Update, Checks, Backups und optionale Integration. Ein Update muss trotzdem zur lokalen Druckerkonfiguration passen.
- `HOST_CHECK`, Datei-/Installationsprüfungen, Log-/Diagnosepakete und Notfall-/Triage-Werkzeuge unterstützen die Fehlersuche.
- Tests und Audits umfassen Makro-Rendering, Generatorparameter, G-Code-Invarianten, Regressionen, Streaming- und Installationschecks. Die CI-Workflowdatei nennt Jinja2 und Pillow als externe Testabhängigkeiten.

## Was daran besonders ist

Die Besonderheit liegt nicht in einem einzelnen Druckmakro, sondern in der Integration von **Drucksteuerung + Dateiverständnis + Erzeugung + Bedienoberflächen**:

1. Ein Host-Watcher ergänzt Dateien mit Layer-/Feature-/Parameterinformationen, statt alle Funktionen ausschließlich von slicerseitigen Skripten abhängig zu machen.
2. Dieselben Dateimerkmalen sollen Dateiübersicht, Startdialog, Layerlogik und Live-Feature-Overrides antreiben.
3. Die LCD-Menüs sind eine zentrale Bedienstruktur; die Web-LCD soll sie spiegeln, statt ein völlig separates Menüsystem einzuführen.
4. Viele Generatoren sind direkt über Druckermenüs erreichbar. Das verwandelt den Drucker in eine kleine, lokal bedienbare Fertigungsstation und nicht nur in einen G-Code-Abspieler.
5. Das System kombiniert Nutzerentscheidungen („wie soll diese Datei laufen?“) mit Automatisierung, File-Checks und Diagnosewerkzeugen.
6. Die Tests zielen auf konkrete Klipper-/G-Code-/Host-Fehlerklassen; `docs/SHUTDOWN_REGISTER.md` dokumentiert zum Beispiel historische Hostlast-/Timingprobleme und Gegenmaßnahmen.

Das ist eine Aussage über Projektumfang und Architektur, kein belegter Branchenrekord. Die meisten zugrunde liegenden Bausteine — Klipper-Makros, Postprozessoren, adaptive Meshes, Web-Dashboards und Generatoren — existieren auch im Klipper- und Maker-Umfeld separat.

## Vergleich mit anderen Lösungsarten

| Ansatz | Typischer Schwerpunkt | Abgrenzung von R2-D2 |
|---|---|---|
| Herstellerintegrierte Druckerökosysteme | Einfacher Start, abgestimmte Hardware-/Slicer-/App-Erfahrung und herstellerseitige Wartung | R2-D2 bietet mehr direkte Änderbarkeit in Makros und Hostskripten, verlangt dafür mehr Einrichtung, Prüfung und Pflege durch den Betreiber. Unterschiede sind modell- und firmwareabhängig. |
| Übliche Klipper-Community-Konfiguration | Klipper + Moonraker/Mainsail oder Fluidd, Makros und ausgewählte Zusatzprojekte | R2-D2 bündelt viele Bereiche in einer umfangreichen Konfiguration: Start/Live-Tuning, LCD-Menü, File-Watcher, Web-LCD, Generatoren und Diagnose. Eine schlankere Community-Konfiguration kann leichter zu verstehen und zu warten sein. |
| OctoPrint-orientierte Installation | Host-Weboberfläche und Plugin-/Slicer-Integration; Funktionstiefe hängt von Druckerfirmware und Plugins ab | R2-D2 ist eng an Klipper-Objekte, Klipper-Jinja-Makros und Klipper-Motionsteuerung angebunden. OctoPrint ist nicht ein einzelnes Firmwaremodell und ein fairer Funktionsvergleich muss die konkrete Firmware und Plugins nennen. |
| Wissenschaftliche/industrielle Systeme | Definierte Messmethoden, Prozesskontrolle, Dokumentation, Validierung und ggf. Zertifizierung | R2-D2 enthält nützliche Kalibrierungs-, Analyse- und Auditwerkzeuge, aber das Repository weist keine formale metrologische Rückführbarkeit, industrielle Prozessqualifizierung oder unabhängige Bauteilzertifizierung nach. Es ist ein Community-Werkzeug, kein validiertes Labor- oder Produktionssystem. |

## Performance: wichtige Kostenstellen und Grenzen

Die Maschine ist durch Klipper-Hostreaktor, MCU-Kommunikation, Speicher, SD-Karte und verfügbare Druckzeit begrenzt. Potenzielle Hotspots sind:

- **Umfangreiche Klipper-Menüs und Jinja:** `menus/lcd_menues.cfg` ist groß und enthält viele dynamische Menüeinträge. Das Inventardokument hebt hervor, dass Klipper die dynamischen Menütexte im Reaktor rendert. Menü-/Statusaufrufe können daher zur Last beitragen.
- **Featuregrenzen und Befehlsfrequenz:** `APPLY_TYPE`, Layer-Marker, Statusmeldungen, Lüfter-/PA-/Beschleunigungswechsel und LED-Aktualisierungen erzeugen Arbeit bzw. Kommunikation. Häufige Wechsel oder sehr kleinteilige G-Code-Segmente können das verstärken.
- **Datei- und Geometrieanalyse:** G-Code-Streaming ist auf Speicherverbrauch hin getestet, aber Geometrie-Rasterung, Bildverarbeitung, STL-Export, große Dateien und umfangreiche Audits kosten CPU, RAM und I/O.
- **Generatorjobs:** Lithophanes, ColorPic, String Art und kitbasierte Rasterung können auf einem Pi Zero 2 deutlich länger dauern als kleine Label- oder Verbinderjobs. Job-Queue, Hintergrundverarbeitung, RAM-Gates und `nice` mindern Risiken, beseitigen sie nicht.
- **Datei-Watcher und viele Dateien:** Große G-Code-Verzeichnisse, Metadaten-/Symlinkverwaltung, Re-Scans und Archivwachstum können I/O und Laufzeit erhöhen.
- **Live-Webabfragen:** Das Web-LCD fragt Statusdaten ab. Caches, Objektfilterung und „quiet windows“ reduzieren laut Implementierung die Abfragen, aber mehrere Clients, Logs oder ungünstiges Timing können weiter Hostlast erzeugen.
- **LEDs und Sondieren/Homing:** LED-Ausgaben teilen sich je nach Hardware den Kommunikationspfad mit Druckbewegungen. Die Projektdateien dokumentieren deshalb LED-Ruhe während Homing/Probephasen und weitere Schutzmaßnahmen gegen „Timer too close“.
- **Persistente Schreibvorgänge:** Häufiges Schreiben großer Zustände auf SD-Karte kann den Host blockieren bzw. die Karte belasten. Das Projekt verschiebt große, neu erzeugbare Listen in RAM und spiegelt Hot-Path-Werte in `_STATE`; persistente Änderungen bleiben trotzdem I/O.
- **Zusammenfassung:** Für einen Raspberry Pi mit knappen Ressourcen sollte man Generatoren und große Audits nicht während zeitkritischer Druckphasen ausführen, Objektverarbeitung und optionale Dienste bewusst konfigurieren und reale Drucke mit Host-/Klipperlogs beobachten.

## Kompatibilität und Voraussetzungen

### Plattform und Integrationen

- Klipper + Moonraker; Mainsail ist die dokumentierte Referenzoberfläche. Das Projekt verwendet Klipper-Jinja-Makros, Klipper-Statusobjekte, `save_variables`, delayed G-code und umbenannte Befehle.
- Kartesische und CoreXY-FDM-Drucker sind laut Kompatibilitätsdokument im Umfang. Delta und Belt sind wegen rechteckiger Bettannahmen/Platzierung nicht empfohlen.
- KAMP ist optional; native adaptive Mesh-Funktionen dienen als Rückfall, sofern die erforderlichen Klipper-Funktionen und Objektinformationen verfügbar sind.
- OrcaSlicer- und Cura-Anleitungen sowie mehrere weitere Slicer-Vokabulare sind dokumentiert. Exotische Makros, Firmwarebefehle und unbekannte Featuresemantik lassen sich nicht zwangsläufig übersetzen.

### Hardware- und Konfigurationsabhängigkeiten

- **Bettbereich:** Für andere Drucker muss der echte nutzbare Bereich in der Hardwarekonfiguration (`_R2_CONFIG`/`r2_hardware.cfg`) korrekt gesetzt werden. Achsgrenzen und nutzbare Bettfläche sind nicht immer identisch.
- **Probe:** Probe-Offsets, erreichbare Fläche, Parken und Prime-Linie müssen zur realen Hardware passen. Beim ersten Druck beaufsichtigen.
- **LEDs/Sounds:** LED-Effekte benötigen `klipper-led_effect` sowie passende `[neopixel]`/`[dotstar]`-Konfiguration; Sound erfordert passenden Beeper. Fehlt optionale Hardware, können diese Funktionen ausfallen oder müssen deaktiviert werden.
- **Runout/Filament:** Filamentsensor und exakte Abschnittsnamen der Konfiguration sind erforderlich. Ohne Sensor gibt es keine automatische Runout-Erkennung.
- **Live-Retraktion:** Benötigt Klipper-Firmware-Retraktion und eine passende Slicer-/G-Codekonfiguration. Ohne diese ist die Live-Wirkung eingeschränkt.
- **Gantry-Sync:** `SYNC_GANTRY` ist für den dokumentierten parallel verdrahteten Dual-Z-Aufbau; unabhängige Z-Motoren sollten die passende Klipper-Nivellierung wie Z-Tilt/QGL verwenden.
- **Optionale Drucker-/Host-Features:** Input Shaper braucht Messhardware für Messungen; LCD-/Web-LCD und LED-Persistenz können optionale Komponenten oder Erweiterungen benötigen.
- **G-Code-Interpretation:** Die Konvertierung ist parser- und dialectabhängig. Fehlerhafte, ungewöhnliche oder proprietäre G-Code-Makros sowie nicht erkannte Bewegungsmodi können Analyse und Transformation begrenzen.

## Grenzen und verantwortungsvolle Nutzung

- „AS SLICED“ beschreibt eine Laufoption; es bedeutet nicht automatisch, dass der Drucker keine Startsequenz ausführt. `PRINT_START` kann weiterhin Homing, Heizen, Mesh und Purge übernehmen.
- Eine automatisch abgeleitete Featureklassifikation ist eine Heuristik. Das Projekt signalisiert abgeleitete Daten als solche; Geometrieklassifikation ersetzt keine vollständige Slicer-Semantik.
- Generatoren erzeugen keine geprüften Tragwerke, elektrischen Teile oder zertifizierten Sicherheitskomponenten. Für mechanische Last, Temperatur, Lebensmittelkontakt, Netzspannung oder andere sicherheitskritische Zwecke sind unabhängige Konstruktion und Prüfung nötig.
- Der Betrieb setzt korrekte Hardwareverkabelung, Firmwarekonfiguration, mechanische Grenzen und Beaufsichtigung voraus. Makros ersetzen keine Thermosicherung, Rauchmelder, korrekt dimensionierte Stromversorgung oder elektrische Sicherheitsprüfung.
- Die Repository-Dokumentation selbst weist auf mögliche Versionsabweichungen hin; unter anderem ist der Abgleich zwischen `MANUAL.md` und `MANUAL.pdf` als offener Punkt aufgeführt. Aktuelle Quelldateien und Installationshinweise vor dem Einsatz abgleichen.

## Fazit

R2-D2 ist ein **integriertes Klipper-Bedien-, Analyse- und Generatorsystem** für fortgeschrittene Maker. Es hebt sich durch die Verbindung aus G-Code-Erkennung, manuell steuerbaren Layer-/Feature-Regeln, LCD/Web-Bedienung, Hostverarbeitung und direkt am Drucker verfügbaren Generatoren ab. Die Kehrseite ist erhebliche Komplexität und eine starke Abhängigkeit von passender Hardwarekonfiguration, Klipper/Moonraker-Kompatibilität und verfügbarer Hostleistung.

### Repository-Quellen

- `README.md` — Funktionskatalog und Systemprinzip
- `INSTALL.md` — Installation, Slicer-, Watcher- und Integrationseinrichtung
- `COMPATIBILITY.md` — dokumentierter Portierungsumfang und Hardwareabhängigkeiten (älterer Versionsstatus beachten)
- `DEVELOPMENT.md` — Entwicklungs- und Testansatz
- `docs/TOOLS_INVENTORY.md` — Runtime, Generatoren, Test- und Diagnosewerkzeuge
- `docs/SHUTDOWN_REGISTER.md` — dokumentierte Timing-/Hostlast-Vorfälle und Schutzmaßnahmen
- `macros/08_print_start_stop.cfg`, `macros/10_live_tuning.cfg`, `macros/01_state.cfg`
- `tools/r2_postproc.py`, `tools/r2_job_service.py`, `web/r2_menu.py`, `web/index.html`
- `slicer/ORCA.md`, `slicer/CURA.md`, `slicer/cura_KlipperFeatureTypes.py`
