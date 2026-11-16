# Datei-, Job-, Bedienungs-, Hardware- und Dokumentationsabgleich

Stand: restaurierter Produktbaum `ce29e2a`. Dies ist eine quellengestützte Bestandsaufnahme, **keine End-to-End-, Maschinen- oder vollständige Einzelpfadabnahme**. Keine Produktdateien wurden geändert.

## 1. Datei- und Bildauswahl

- Generatoren haben `OUT=QUEUE` (Datei auswählen/Quellenauswahl ersetzen) und `OUT=PREVIEW` (nur Dateiliste); das ist laut `macros/17_generator.cfg:41–65` nicht gleichbedeutend mit automatischem Druckstart. Ob Auswahl, Dialog, registrierte Ausgabe und angezeigte Queue bei allen Familien zuverlässig zusammenspielen, wurde nicht insgesamt nachgewiesen.
- `tools/r2_postproc.py:26440–26501` listet nur rootständige PNG/JPG/JPEG, nach Änderungszeit, maximal **60**, auf Seiten zu 10; Push nur bei bestätigt inaktivem Drucker. `:25897–25942` kopiert eine in einem Unterordner ausgewählte Bilddatei unter ihrem **Basenamen** ins Root. `STRINGART_IMG` benutzt die gemeinsame sichtbare `litho_files`-Seite, aber eigenen `stringart_src`/Index (`macros/17_generator.cfg:1143–1162`). Die Liste ist eine gemeinsame Datenquelle, kein nachgewiesener gemeinsamer Bildauswahlvertrag mit zuverlässigem Wechsel/Reset für jedes Tool.
- **Konkreter Originalschutz-Befund:** Existieren `photo.png` im Root und `sub/photo.png` mit unterschiedlichem Inhalt, schreibt der extrahierte Original-Watcherzweig mit `shutil.copy2` die Rootdatei mit dem Unterordnerbild über; anschließend meldet er Erfolg. `python analyse/image_pick_collision_probe.py`, `analyse/testprotokolle/image_pick_collision_probe.log`. Beide Dateien lagen in einem temporären Verzeichnis, Moonraker war ein Stub. Der reale UI-/Nonce-Weg und Symlink-Randfälle wurden dabei nicht geprüft. Das ist trotzdem ein nachweisbarer gefährlicher Zweig und kein bloßer Designverdacht; aus dem Stub folgt keine allgemeine Aussage, wie oft er in der Praxis erreicht wird.
- `process(path)` ersetzt die übergebene ungetaggte Datei (`tools/r2_postproc.py:19694,20238`), und optionaler Retract-Rewrite läuft vor der TAG-Prüfung (`:19710–19716`). Siehe `rekonstruktionsproben.log`. Ob ein konkreter Watcher-Einstieg immer zuerst eine Kopie anlegt, ist damit nicht beantwortet. Ziel: pro Einstieg eindeutiger Quell-/Zielvertrag, collision-safe Namen, atomare Publikation, Inhalts-Hash, Symlink-/Traversal- und Rechteprüfungen.
- Der SD-Browser hat unterschiedliche historische Pfade; `SD_BROWSER_ON=False` und Symlink-Konzept sind laut Übergabe/Backlog vorhanden. Eine komplette Benutzerführung an echtem LCD und Moonraker wurde nicht getestet.

## 2. Queue und Generatoren

`_JOB_STATE` und `_job_worker` bilden eine lokale Queue (`tools/r2_postproc.py:8796,24424`); ein Jobthread und Busy-/RAM-Gates sowie kooperatives Yielding (`:8856`) sind vorhanden. Hängende Threads werden gemeldet und können weitere Jobs blockieren (`:24431–24480`), sind also nicht mit hartem Prozessabbruch gleichzusetzen. Im isolierten Worker-AST erzeugt injiziertes `kill=SKIP` vor Entpacken von `item` einen `UnboundLocalError` auf `key` (`:24490–24512`, `rekonstruktionsproben.log`); tatsächliche Erreichbarkeit und Auswirkungen bleiben offen.

Output-Pfade/Notifier: `_gen_out` `:22237`, `_meta_finalize` `:22258`, `_moonraker_filelist_notify` `:8841`; nicht für jeden Aufrufer sind Existenz, Validität, Registrierung, tatsächliche Benachrichtigungszustellung und Statusübergänge als atomarer Vertrag belegt. Beispielhafte Zielzustände: `queued → waiting → running → validated → registered → succeeded`; daneben `failed`, `cancelled`, `timed_out` mit eindeutiger Job-ID, Ausgabe und Fehlergrund. Registrierung und Meldung fehlgeschlagen dürfen nicht still als Erfolg gelten. Bestehende LCD-/Web-Wirkung erhalten.

### Familieninventar mit belastbarer Aussagegrenze

| Familie / Werkzeug | Bestand/Codeanker | Stand / Nachweisgrenze |
|---|---|---|
| Labels | `make_labels:6026` | Parameter-/Ausgabe-Tests im Repo; nicht alle Kombinationswege und UI-Abnahme. |
| Lithophane/ColorPicture/ArtisticStrings | `make_lithophane:14239`, `make_colorpic:17102`, `make_string_art:10353` | Bilddecoder/Picker vorhanden; Kollisionsfall oben; reale Bildwechsel und Ausgabevalidierung offen. |
| Bricks/Kit/Figures | `make_bricks:14864`, `make_brick_kit:15657`, `make_figures:16128` | Queue/Objektbezogenheit differenziert prüfen; keine universelle Objektselektion nachgewiesen. |
| Frame/Angles/Ties/Seal/Shape | `make_frame:11286`, `make_angles:12810`, `make_cable_ties:10703`, `make_seal:17432`, `make_shape:13175` | Funktionseinstiege vorhanden; G5/Shape-Regression bleibt gesperrt. |
| Plotter/Bridge/Resonance | `make_plot_cal:14658`, `make_bridge:9813`, `make_resonance:8112` | Geräte- und Positionsannahmen sowie End-to-End noch nicht abgenommen. |
| Range/Cake | `make_range:1300`, `tools/r2_cake.py` | H1 Guard synthetisch 8/8; H2/H3 offen; Guard repariert keine Schichtstruktur. |
| Scale/Twist/Mirror, Fixes/RETAG, STL | Watcher/Transformer in `tools/r2_postproc.py`, `_stl_export:17967` | Einzelne Regressionen existieren; M82-/M83-Exportgegenprobe abweichend, Objektselektor und Bewegungs-/E-Invarianz nicht generell belegt. |
| Texture | `tools/r2_texture.py` und `macros/17_generator.cfg:743` | Vorliegende Übergabebefunde nur referenziert; G1–G5 und Textur-Rückteil bleiben gesperrt. |

**Hinweis zum gemischten Testlauf:** `r217_gen_matrix.py` wurde für die allgemeine Generator-Kompatibilität gestartet und nach Entdeckung, dass er auch G5-Shape-Testfälle enthält, gestoppt. Sein gepufferter Log ist leer; es ist nicht feststellbar, ob der Prozess diese Fälle bereits erreichte. Es liegt **kein verwertbares Ergebnis** und keine G5-Freigabe vor. Produktdateien wurden dabei nicht geändert.

## 3. LCD, Web, Sound und LED

- `menus/lcd_menues.cfg` definiert das Menü, `tools/menu_json_export.py` exportiert den Baum; `web/r2_menu.py:105–194,266–476` bietet Tree/Live/Refresh usw.; `web/index.html` rendert und bedient. `r218` **23/25**, zwei Fehlschläge: Embedded-Fallback 2423 vs. Export 2295, Versionsbadge `.142c` statt Stand V1. Das ist ein konkreter Fallback-/Doku-Mismatch, nicht der Nachweis, dass der reguläre Webbaum immer ausfällt. LCD-/Web-Aktionsgleichheit, Auth und Fehlerzustände sind nicht komplett durchgespielt.
- `M300` emittiert `SET_PIN PIN=beeper ... CYCLE_TIME` ohne Hardwareguard (`macros/02_sounds.cfg:23–32`). `sound_on` wird in `_SOUND_LIB` berücksichtigt, standardmäßig True (`:81–93`); direkter `M300` bleibt ein eigener Pfad. 20 benannte Tunes stehen in `variable_tunes` und der Liste `PLAY_SOUND` (`:39–60,97–102`), nicht 19 wie das Briefing als frühere Vermutung nennt. `G4` ist ein Wartebefehl; genaue Host-/MCU-Wirkung und No-Beeper-Verhalten wurden nicht am System gemessen. Kein stummes Fallback für jede Konfiguration behaupten.
- `SET_LED_STATE` prüft `leds_on` und `led_effect r2_idle`; `_LED_QUIET` setzt Flag und stoppt vorhandene Effekte (`macros/03_leds.cfg:218–250,316–333`); `r257` prüft 15 Regeln und 7 Mutationen. Das ist nicht gleichbedeutend mit erfolgreichem Start ohne LED-Plugin, weil aktive `[led_effect]`-Sektionen bereits beim Laden relevant sind (`:74 ff.`, `COMPATIBILITY.md` §4). Layout nennt NeoPixel/DotStar und optionale EBB/CAN-Aufteilung, tatsächliche Installation/Verkabelung unbekannt.
- Klipper-LCD-Display/Encoder hängt von Treiber, Pins, Spalten und Menüstatus ab. Dokument `docs/LCD_MENU_PORTABILITY.md` ist eine Portierungsanleitung, kein Test aller LCDs; Touch/KlipperScreen nutzen eigene Oberflächen. Es gibt keine bestätigte physische Displaymatrix.

## 4. Maschinenmodell und Sicherheit

| Bereich | Ist und Fundstelle | Einstufung / fehlende Abnahme |
|---|---|---|
| Bett / Generatorbereich | `_bed_limits:5373`, `_R2_CONFIG`; Default-Maße möglich | konfigurationsabhängig; Default ist nicht Nachweis des real bedruckbaren Betts. |
| Mechanik / Probe | Achsgrenzen und Probe-Offsets werden in verschiedenen Makros genutzt | mechanische, bedruckbare und Probe-Bereiche explizit getrennt prüfen; reale Geometrie/Kollision unbekannt. |
| Düse | `_nozzle_diameter:5453`, `_gen_nozzle:5487` | vorhanden; kein neuer Gesamtbeweis, dass jeder Generator/jeder innere Pfad die Düse richtig verwendet. |
| Wipe | `_NOZZLE_WIPE` `macros/12_maintenance.cfg:1927–1981`: Anker gegen Achsgrenzen, 13×13, fährt Z4, erhitzt und kann homen | konfigurationsabhängig, nur X/Y-Reichweite geprüft; tatsächliche Wipe-Höhe, Pad und Kollision nicht belegt. Kein Aufruf am Drucker. |
| Dual-Z / Gantry | `SYNC_GANTRY`, `Z_TILT` in `macros/11_gantry_sync.cfg` | paralleler vs. unabhängiger Antrieb unterscheiden; Widerspruch zur Kalibrierungs-PDF im Kalibrierbericht, keine Bewegung freigegeben. |
| Sensoren | `macros/09_pause_filament.cfg:75,280,412` prüft benannten `filament_motion_sensor encoder_sensor` | andere Namen/Hardware und Runout/Jam-Fallback nicht universell getestet. |
| Kinematik | `COMPATIBILITY.md`: Cartesian/CoreXY, Delta eingeschränkt | generische Behauptung „full support“ ist hier **nicht** auf realen Geräten belegt; Delta/Belt nicht ohne eigene Geometrie annehmen. |
| Konfig/Persistenz | `tools/r2_setup_lib.sh:468–548` erzeugt separates `r2_hardware.cfg`; `[save_variables]` bleiben eigene Datei | im Checkout ist dies ein vom Setup erzeugtes Maschinenartefakt, keine echte Feldkonfiguration. Keinerlei Rückschluss auf Nutzerwerte; Schreiben/Last ungemessen. |

`docs/SHUTDOWN_REGISTER.md` ist das Quellenregister mit 16 historischen Klassen, nicht der unabhängige Nachweis universeller Ursachen. E1/E4: dokumentierter Probe-Fehler und Host-Reactor-Verdacht als getrennte Hypothesen; Feldlog und konkrete Konfiguration fehlen. Keinen Z-Wert herabsetzen und keine Homing-, Probe-, Heat-, Wipe-, Gantry- oder sonstige Maschinenbewegung ohne eigenes Go. `r255` und `r257` sind Offline-Tests, keine Messung des Druckers.

## 5. Dokumentation und Quellenkonflikte

`r165` prüft gezielt Makronamen, Pfade, Parameter und Textregeln; `r265` Index und weitere mechanische Aspekte. Beide beweisen nicht, dass sämtliche fachlichen Aussagen, PDFs oder physische Abläufe korrekt sind. Der konkrete Gantry-PDF-Widerspruch, Flow-Target und Override-/Ironing-Befunde stehen in den Kalibrierungsberichten; `MANUAL.md` Kapitel 14 zur LIVE-Lüfterstufe bleibt Entscheidung D1. Alte `INSTALL.md`-Passagen empfehlen Löschen von Verzeichnissen bzw. `variables.cfg`; sie sind historische Anweisungen und **nicht ausführen**. Maßgeblich sind aktuelle Schutz- und Freigaberegeln.

Quellenliste, SHA und Fehlstellen siehe Hauptbericht und `uebergabe-quellen/SHA256SUMS`; insbesondere fehlen `slicer-families.md`, `GCode_Reverse_Engineering_Master_Spezifikation.md`, das V1-Update-ZIP sowie originale Feldlogs/Fehlexporte. Das vorliegende Masterkonzept und `FeatureErkennung.md` sind nützlich, aber nicht stillschweigend Ersatz für fehlende Dokumente.
