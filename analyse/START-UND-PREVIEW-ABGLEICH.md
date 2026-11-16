# Start, Schichtzahl und Preview: gezielter Bestandsabgleich

**Status:** nicht-invasive Analyse auf Produktstand `ce29e2a`; keine Implementierungsfreigabe. Es wurden keine generierten Befehle ausgeführt und keine Drucker, Klipper- oder Moonraker-Dienste kontaktiert. `process()` lief ausschließlich auf temporären Kopien. Original-Fixtures und getrackte Dateien blieben unverändert. Render- und Status-Stubs ersetzen keine zeitliche Integration.

## 1. Tatsächliche Repo-Fixtures und Startreihenfolge

`analyse/fixture_start_preview_probe.py` entpackt die drei vorhandenen `testfixtures/*.gcode.gz` nur in ein TemporaryDirectory, prüft den SHA-256 der Originalarchive vor und nach der Analyse und verwendet `process()` ausschließlich auf den entpackten Kopien. Ergebnisse, Zahlen und Hashes stehen in `analyse/testprotokolle/fixture_start_preview_probe.log`.

| Fixture | Vor Verarbeitung | Nach Verarbeitung auf Temp-Kopie |
|---|---|---|
| `bigrose_020mm` | `PRINT_START ... TOTAL_LAYERS=250` in Quellzeile 173; 251 `LAYER_MARK`; Header meldet 251 | `_FILE_INFO TOTAL_LAYERS=251` in Ausgabezeile 171 vor `PRINT_START ... TOTAL_LAYERS=250` in Ausgabezeile 176; 251 vorhandene Marker, keine neu eingefügt |
| `rose_215c_pla` | `START_PRINT` in Zeile 95; kein `PRINT_START` und kein `LAYER_MARK` | `_FILE_INFO TOTAL_LAYERS=242`, dann `START_PRINT`; 242 Marker aus Layer-Kommentaren eingefügt |
| `stringart3d_generic` | weder `PRINT_START`, `START_PRINT`, `_FILE_INFO` noch `LAYER_MARK` | `_FILE_INFO TOTAL_LAYERS=15`; 15 Marker aus Layer-Kommentaren eingefügt |

Für Bigrose ist die Reihenfolge aus der echten Repo-Fixture nach Verarbeitung ihrer temporären Kopie belegt. **250 gegen 251** ist eine beobachtete Diskrepanz zwischen dem vorhandenen Startparameter und Markern/Header, keine Feststellung, welche Konvention semantisch korrekt ist. Die beiden anderen Beispiele benutzen nicht denselben `PRINT_START`-Pfad und sind ausdrücklich keine Bestätigung des Start-Reset-Befunds. Drei Fixtures sind keine repräsentative Marktstichprobe.

Die ergänzende lesende Probe `analyse/bigrose_layer_boundary_probe.py` zählt in der Originaldatei jeweils 251 `;LAYER_CHANGE`, `;Z:` und `LAYER_MARK`. Vor Markern 250 und 251 steht jeweils `;Z:50.0042` (Quellzeilen um 254086 und 255008); zwischen Marker 250 und 251 enthalten 905 G0/G1-Zeilen ein Z-Wort mit Werten von 49,803 bis 50,004. Der Abschnitt **nach** Marker 251 enthält 905 G0/G1-Zeilen mit XY- und E-Wort, aber keine mit Z-Wort. Die Zählung betrachtet geschriebene Parameter bis zum nächsten Marker, bei Abschnitt 251 bis Dateiende, nicht aufgelöste Extrusion oder die ursprüngliche Slicerabsicht. Die Probe zeigt damit zusätzlichen Kontext für die Abweichung, erklärt aber nicht beweiskräftig die 250/251-Konvention.

## 2. PRINT_START, Reset und alternative Wege

`macros/08_print_start_stop.cfg:107–112` gibt im normalen Zweig zuerst `SET_GCODE_VARIABLE ... total_layers VALUE={params.TOTAL_LAYERS...}` und danach `_LIVE_RESET` aus. Dessen Originaltemplate setzt `total_layers=0` (`macros/10_live_tuning.cfg:61–63`). `analyse/start_layer_total_probe.py` rendert beide Templates und entfaltet nur diese Zustandszuweisungen als Modell. Ausgaben mit `TOTAL_LAYERS=30`:

| Synthetischer Vorzustand | Ausgabe |
|---|---|
| ohne Startdialog | Setzen auf 30, danach `_LIVE_RESET` mit Setzen auf 0 |
| Startdialog aktiviert | gleiche Setzfolge, außerdem `_DIALOG_PEEK` |
| vorgemerkte Entscheidung `as_sliced` | gleiche Setzfolge, `_RUN_PRINT_START` statt `_DIALOG_PEEK` im `PRINT_START`-Template |
| Schutz verweigert doppelten Start | weder Setzer noch `_LIVE_RESET` aus diesem Zweig |

Zusätzliche Einzel-Setzer sind u. a. `_FILE_INFO` bei `TOTAL_LAYERS>0` (`macros/08_print_start_stop.cfg:938–940`) und `_FILE_INFO_RESET` bei Auswahl (`:1423–1449`). Die Beobachtung belegt **nicht**, dass die Schichtzahl während eines realen Drucks dauerhaft null bleibt. Zum Beispiel kann eine spätere Preview `_FILE_INFO` erneut liefern. Keine vollständige Sequenz aus `SDCARD_PRINT_FILE`, Startdialog, Watcher, Klipper und Moonraker wurde ausgeführt.

## 3. Preview und Deduplizierung können die spätere Wiederherstellung beeinflussen

- `_DIALOG_PEEK` kann bei `mode=waiting` und Dateiname einen erneuten Preview-Nonce anstoßen (`macros/08_print_start_stop.cfg:1505–1523`); der direkte `start_pending`-Zweig in `PRINT_START` ruft ihn dort nicht auf (`:124–135`).
- `_preview_script` hängt die originale `_FILE_INFO` nur an, wenn `busy` nicht zutrifft; `busy` ist abhängig von `print_stats` und R2-Modus (`tools/r2_postproc.py:22518–22529,22541–22559`). Offline-Status-Stubs mit der postprozessierten Bigrose-Kopie ergeben `_FILE_INFO` bei `printing/waiting` und `standby/idle`, aber nicht bei `printing/printing`. `_PREVIEW_SET` und `_STATE` sind getrennte Statusobjekte (`:22541`, `macros/08_print_start_stop.cfg:430–443,508–509`).
- Der Nonce-Pfad kann den Re-Peek vor `_preview_script` deduplizieren (`tools/r2_postproc.py:25148–25178`). `_preview_dup_skip` prüft Dateikey, bestätigten Push, Zeitfenster und `_PREVIEW.name`, aber nicht `_STATE.total_layers` (`:22462–22489`). Im Stubtest liefert gleicher ACK-Dateikey, Name und Alter 1 s selbst bei vorgegebenem `_STATE.total_layers=0` **skip=True**; ein anderer Preview-Name liefert **False**. Das ist ein konditionaler Test der Funktion, kein Nachweis, dass der Ereignisablauf im Feld genau so ablief. `fixture_start_preview_probe.py` stubbt `_moonraker_status`; kein Netzwerkaufruf erfolgt.

Reihenfolge, ACK, Dedupe-Fenster, eventuelle Wiederholung, Modus und tatsächliches Vorhandensein von `_FILE_INFO` sind für einen End-to-End-Nachweis maßgeblich. Der Schutz gegen schwere Preview-Pushes während Bewegung hat einen dokumentierten Sicherheitszweck (`tools/r2_postproc.py:25154–25175`): Ein späterer Fix darf ihn nicht ungeprüft aufheben.

### Partielle Ereignismodellierung mit Gegenfällen

`analyse/preview_sequence_model.py` verknüpft unter **fest vorgegebenen Ereignissen** echte Templates von `_PREVIEW_SET`, `_FILE_INFO`, `PRINT_START`, `_LIVE_RESET`, `_DIALOG_PEEK` mit den echten Python-Funktionen `_preview_script` und `_preview_dup_skip`. Die Bigrose-Fixture wird nur temporär verarbeitet. Ein kleines In-Memory-Modell übernimmt ausschließlich `_STATE.mode`, `_STATE.total_layers` und `_PREVIEW.name`/`total_layers`; alle anderen Befehle werden ignoriert, die `DIALOG_PEEK`-Nonce wird nur im Rendertext geprüft. Moonraker-Status, ACK, Statuswechsel, Bearbeitung einer ausstehenden Nonce und offenes Motion-Gate sind Annahmen. Es ist **keine** Klipper-/Moonraker-Integration und kein vollständiges Ablaufmodell.

Für den Modellpfad wird eine Preview **vor** dem Dateistart zugestellt, dann führt die Dateifolge `_FILE_INFO` und `PRINT_START` aus; anschließend wird die angenommene Dialog-Nonce bearbeitet. Nur im fehlgeschlagenen ACK-Fall nimmt das Modell ausdrücklich an, dass der erste Push nicht zugestellt wurde – ein realer Fehler kann auch mehrdeutig sein.

| Anzunehmende Folge nach dem Reset | `_preview_dup_skip` | `_STATE.total_layers` danach | `_PREVIEW.total_layers` danach |
|---|---:|---:|---:|
| ACK, Dateikey/Name gleich, Alter 1 s, noch waiting | True | 0 | 251 |
| erster ACK fehlte, keine erste Zustellung, waiting | False | 251 | 251 |
| ACK, Alter 121 s, waiting | False | 251 | 251 |
| ACK, anderer Preview-Name, waiting | False | 251 | 251 |
| ACK, temporäre Datei nach ACK geändert, waiting | False | 251 | 251 |
| ACK, Alter 121 s, inzwischen printing | False | 0 | 251 |

Im letzten Fall verhindert nicht der Dedupe-Check, sondern die `busy`-Bedingung im Preview-Script den `_FILE_INFO`-Replay. Die Ergebnisse zeigen, dass der gleiche Reset je nach **angenommener** Reihenfolge und Status sowohl durch Replay überdeckt werden kann als auch im Modell bestehen bleibt. Sie belegen weder, dass diese Folgen im normalen Startpfad erreichbar sind, noch die Zustände eines realen Druckers. Insbesondere werden Universal-Intercept, `PAUSE_BASE`, Dateileser, konkurrierende Nonces, `_printer_moving()` und Netzwerk nicht simuliert.

## 4. Nachgewiesene Verbraucher bei explizitem Zustand

`analyse/layer_total_consumers_probe.py` rendert Originaltemplates und eine LCD-Menüzeile:

| Vorgegebenes `_STATE.total_layers` | Live-File-Menü | `LAYER_MARK` mit Vorzustand Layer 0 |
|---:|---|---|
| 0 | `Ly: 0.2x?` | `M117 Layer 1 | WALL-OUTER` |
| 251 | `Ly: 0.2x251` | `M117 Layer 1/251 | WALL-OUTER` |

Quellen: `menus/lcd_menues.cfg:2263–2268`, `macros/06_temp_controls.cfg:551–558`. Weitere Anzeigen in `menus/lcd_menues.cfg:45,2762` und `macros/04_notify.cfg:51` lesen `_STATE.total_layers`; eine Vorschauanzeige verwendet dagegen `_PREVIEW.total_layers` (`menus/lcd_menues.cfg:2726`). Unterschiedliche Statusobjekte nicht gleichsetzen.

Die Range-Eingrenzung ist ein weiterer **bedingter** Verbraucher: Das Template `SET_LAYER_RANGE` klemmt `END` nur bei `tl>0` (`macros/08_print_start_stop.cfg:648–679`). Im gerenderten Zustand `mode=waiting`, `START=10 END=300` wird mit `total_layers=251` `range_end=251`, mit `total_layers=0` dagegen `range_end=300` ausgegeben. Bei `mode=printing` verweigert das Template den Auftrag. Die Range-Erstellung wurde **nicht** ausgelöst; das Backend bestimmt die tatsächlich verfügbaren Marker selbst und besitzt weitere Prüfungen (`tools/r2_postproc.py:1651–1688`). Aus der Renderprobe folgt nicht, dass eine unzulässige Range-Datei entsteht oder ein Druck gefährdet ist.

## 5. Prüfplan ohne Produktänderung

1. Eine echte Klipper-/Moonraker-Integrationssimulation aufbauen, bevor irgendwelche physischen Tests vorgeschlagen werden: Auswahl-Push ACK/Fehler, identische Datei innerhalb/außerhalb des Dedupe-Fensters, geänderte Datei und Restart; Zustände `_PREVIEW.name` **und** `_STATE.total_layers` nach jedem Ereignis erfassen.
2. Startpfade mit und ohne Dialog, vorgemerkte Entscheidung, gestoppter/verspäteter Preview-Push und Bewegungs-Gate separat prüfen. Nur kontrollierte Stubs/Testumgebung; keine Befehle an die Maschine.
3. Bigrose-Startparameter 250 und Header/Marker 251 mit dem konkreten Slicerprofil und Layer-Konventionen abgleichen, bevor eine Sollzahl festgelegt wird.
4. UI-Anzeige, `_STATE`, `_PREVIEW`, `SET_PRINT_STATS_INFO`, Range-Eingrenzung und Backend-Ergebnis getrennt testen. Keine Aussage über Range-Erstellung allein aus der Frontend-Ausgabe ableiten.
5. Vor einem eventuell freigegebenen Eingriff Rückwärtskompatibilität, Golden-/Makrotest 2100/2100, Preview-Motion-Gate, Homing/Probe/Purge und Start/Ende gesondert absichern. Änderungen im Produkt oder im Backlog sind hier nicht freigegeben.

Belege: `analyse/testprotokolle/fixture_start_preview_probe.log`, `bigrose_layer_boundary_probe.log`, `start_layer_total_probe.log`, `layer_total_consumers_probe.log`, `preview_sequence_model.log`; Hauptbericht `analyse/BESTANDSAUFNAHME-UND-ARCHITEKTUR.md`.
