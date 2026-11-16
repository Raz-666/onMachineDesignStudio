# Architektur-Umsetzung: Bildschutz und Shadow-Prototyp

**Historischer Zwischenstand:** Bildschutz und Queue-Korrektur wurden inzwischen auch in den aktiven Einstieg übernommen; die frühere Engine ist hashverifiziert unter `backups/` gesichert. Der Shadow und der neue Offline-Dateidienst bleiben getrennt und experimentell. Aktueller Stand und Abnahmegrenzen: `analyse/REVIEW-BUILD-V2.md`.

Der Nutzer hat bestätigt, dass die freigegebene Reihenfolge ohne wiederkehrende Zwischenfreigaben abgearbeitet werden soll. Die Bereiche G1–G5 und das Textur-Rückteil bleiben gesperrt; keine Hardwarebewegung oder Installation wurde ausgeführt. Die folgenden Änderungen liegen im Arbeitsbranch und sind **nicht** auf einem Drucker installiert.

## 1. Bildauswahl: abgesicherter experimenteller Pfad

In `tools/r2_postproc_next.py` nutzt der Bild-Pick-Watcher jetzt `_copy_picked_image`:

- Root-Bilder werden als reguläre Datei geprüft und nicht kopiert oder überschrieben. Unterordnerbilder werden in einer temporären Datei im Root aufgebaut, vor Veröffentlichung mit `fsync` abgeschlossen und durch einen atomaren Hardlink ohne Überschreiben veröffentlicht.
- Existiert der Name bereits – auch als Symlink oder Verzeichnis –, wird `bild_1.png`, `bild_2.png` usw. verwendet. Die Erfolgsmeldung nennt den **tatsächlichen** neuen Namen. Ein fehlendes Bild, ungültiger/gefährlicher Pfad oder I/O-Fehler wird als Fehler gemeldet, nicht als erfolgreicher Pick.
- Relative Pfade werden komponentenweise ohne Symlink-Following geöffnet; `..`, Steuerzeichen, Trennzeichen-/G-Code-Injection und ungeeignete Endungen werden abgelehnt. Ein JPEG-/PNG-Suffix und reguläre Datei sind **keine vollständige Bilddekodier-/Integritätsprüfung**.
- Quelle und vorhandene Ziele bleiben erhalten; eine erkannte Änderung von Größe/mtime/Inode während des Kopierens verhindert die Veröffentlichung. Das schützt nicht gegen jeden gleichzeitig absichtlich manipulierten Dateizustand. Quelle, temporäre Datei und Ziel liegen auf demselben Dateisystem. Fehlen sichere OS-Funktionen oder unterstützt das Dateisystem keine Hardlinks, scheitert die Aktion sicher statt auf überschreibendes Kopieren zurückzufallen. Bei einem harten Prozessabbruch kann eine nicht sichtbare `.r2-img-*.tmp`-Datei übrig bleiben.
- Der Kopiervorgang läuft wie bisher im Watcher; I/O- und `fsync`-Zeit können bei großen Bildern blockieren. Ein dedizierter ressourcenbegrenzter Job, echte Bildvalidierung, zuverlässige Benachrichtigungszustellung und vollständige Registrierung sind nicht Teil dieses Schritts. Symlinks als **Bildquelle** werden nun bewusst abgelehnt; Kompatibilität mit ggf. genutzten Symlink-Bildquellen ist offen. Kein automatischer Druckstart.

**Wichtig:** Der aktive stabile `tools/r2_postproc.py` und sein in-place `process()`-Vertrag wurden **nicht** verändert. Der bisherige Bildkollisionsfehler besteht dort weiter, bis eine spätere gesondert kontrollierte Übernahme/Installation erfolgt. Auch andere Quelldatei-Schreibpfade sind damit nicht insgesamt abgesichert. `next` wird durch diese Arbeit nicht automatisch aktiviert.

`python3 tools/test_image_pick_next.py`: **13/13** synthetische Offline-Tests einschließlich Kollision, Quelle, Root-Auswahl, Traversal/Symlink/FIFO, Dateisystem-/Kopierfehler, geänderter Quelle, acht paralleler Auswahlen, tatsächlichem extrahiertem Watcherblock mit Moonraker-Stub und absichtlich destruktiver Gegenmutation (`analyse/testprotokolle/image_pick_next.log`). Kein realer Watcher, Moonraker oder Drucker. Der Testlauf fand einen Fehler beim Öffnen eines Verzeichnisses, der korrigiert und anschließend erfolgreich erneut getestet wurde.

## 2. Nichtausführender Shadow-Prototyp

`tools/r2_shadow.py` liest eine Datei und gibt pro Eingabezeile JSONL auf stdout aus. Er wird von keinem Watcher/Startpfad aufgerufen, erzeugt keine ausführbaren G-Code-Dateien, führt nichts aus und schreibt die Quelle nicht. **Ausgabe nicht per Shell-Umleitung auf die Eingabedatei richten**: eine Shell würde diese vor Programmstart selbst leeren.

Bisher implementierter begrenzter Umfang: Zeilen/Kommentare erhalten, strikt einfache numerische G0/G1-Befehle und Modalzustand, G90/G91, M82/M83, G92, G21, Feed, Toolereignis und einige explizit bekannte Nicht-Bewegungsbefehle. Logische G-Code-Koordinaten sind keine gemessenen Maschinenpositionen; das E-Delta ist befohlen und berücksichtigt nicht realen Flow/Volumen. Anfangsmodi/-positionen sind standardmäßig unbekannt; `--assume-klipper-defaults` ist eine explizite, nicht verifizierte Annahme.

Klipper-Dialekt ist Standard: G91 macht auch bei M82 E relativ; G20 wird als von Klipper abgelehnt markiert. Dies wurde gegen `klippy/extras/gcode_move.py` im Upstream-Commit `29d4ec2d6d840ee839333306003a400da186d41d` geprüft, **nicht** gegen die unbekannte Version auf dem Drucker. `--dialect generic` ist ein begrenztes anderes Modell mit unabhängigen XYZ/E-Modi und G20, keine Garantie für beliebige Firmware. Nicht unterstützte Befehle einschließlich Bögen, Homing, Tool-/unbekannte Makros, komplizierte Syntax und Zustandsunsicherheit invalidieren den Zustand; spätere Zeilen sind eine hypothetische Analyse und kein Beweis, dass Klipper nach einem Fehler noch ausgeführt hätte. Keine semantische Feature-/Pattern-, Layer- oder Objektklassifizierung ist hier bereits implementiert.

`python3 tools/test_r2_shadow.py`: **17/17** synthetische Tests inkl. G92, relativ/absolut, E, Einheiten/Dialekt, G91/M82, unbekannt, Überlauf, Rohzeilen und mutiertem Fixpunkt (`analyse/testprotokolle/r2_shadow.log`).

**Realer Korpus – derzeit ausdrücklich nicht einsatzreif:** Der lesende Lauf `analyse/shadow_field_probe.py` lieferte für alle drei gelieferten Feldfixtures **0 Bewegungsendpunkte mit vollständig bekannten XYZ**. Start-/Layer-/andere Makros invalidieren den Zustand; explizite Resynchronisation fehlt danach häufig. Beide Modi mit/ohne angenommene Startdefaults ergeben in diesen Fällen dasselbe. Das ist eine wichtige dokumentierte Grenze, keine bestandene Parser-/Feldabnahme und kein Grund, die Schutzmaßnahmen durch unbelegte Makroannahmen zu lockern. Roh-Gzip-SHA vor/nach Lauf unverändert; Zahlen in `analyse/testprotokolle/shadow_field_probe.log`.

## 3. Regression und nächster planmäßiger Ausbau

- `analyse/golden_baseline.py verify --engine next`: 6/6 Ist-Goldens weiterhin byte-/summary-identisch zu Stable; nur diese sechs `process()`-Fälle, nicht die ganze Engine oder der Watcher (`golden_baseline_next_after_image.log`).
- `tools/r110_gcode_dialects.py`: 13 synthetische Familien, 46/46 getestete Tags auf Stable; keine Aussage über alle realen Slicer.
- `tools/r257_crash_guard_check.py`: 15/15 und 7/7 Gegenmutationen; statische Sicherheitschecks, keine MCU-/Hardwareprüfung. Keine gemischte Textur-/Shape-Batterie gestartet.
- Als nächstes im Plan: verlässliche Verträge für bekannte R2-/Klipper-Ereignisse und gezielte Resynchronisation anhand der realen Makrosemantik, zusätzliche Modal-/Objekt-Fixtures und detaillierter Sidecar-Vergleich; parallel die übrigen nichtdestruktiven Datei- und Jobzustandsfälle mit Fehlerpfaden. Kein Einspielen oder automatischer Umschalter. Backlog und Originaluploads bleiben unverändert.
