# Kalibrierergebnisse: Overrides, Material und Verbraucher

Stand 15.11.2026, Produktstand `ce29e2a`. Offline-Bestandsaufnahme, **keine Bedienanleitung und keine Freigabe für Produktänderungen oder Maschinenbewegungen**. Ergänzt und präzisiert `analyse/KALIBRIERUNG-ABGLEICH.md`. Weiterführend: `analyse/OVERRIDE-BEDIENPFADE-UND-IRONING.md` mit LCD-/Datei-Preset-Proben, statischem Aufrufindex und Ironing-Einheiten-/Kartenparameterabgleich.

## Wichtigster Befund: Aktivierung hinter G-Code-Kommentar

`SET_OVERRIDE_VALUE` verspricht „switch it ON“ (`macros/07_start_confirm.cfg:266–267`). Bei 16 skalaren Zweigen stehen aber Wert und Aktivierung in **einer Zeile**, getrennt durch `;` (`:316–335`). Beispielsweise wird bei `NAME=flow` ausgegeben:

```text
SAVE_VARIABLE VARIABLE=ov_flow VALUE=90.0 ; SAVE_VARIABLE VARIABLE=ov_flow_on VALUE=True
```

Der geprüfte Klipper-Referenzparser behandelt `;` als Kommentar, nicht als Trenner zweier Befehle: `GCodeDispatch._process_commands` schneidet die Zeile an `;` ab, und `_get_extended_params` verwendet `#;` als `shlex`-Kommentarzeichen. Der zweite `SAVE_VARIABLE` wird so nicht als eigener Befehl dispatcht. Die Referenz ist Klipper-Upstream `29d4ec2d6d840ee839333306003a400da186d41d`, Datei [klippy/gcode.py](https://github.com/Klipper3d/klipper/blob/29d4ec2d6d840ee839333306003a400da186d41d/klippy/gcode.py#L202-L216) und [Parameterparser](https://github.com/Klipper3d/klipper/blob/29d4ec2d6d840ee839333306003a400da186d41d/klippy/gcode.py#L266-L280); Kopie `analyse/klipper-referenz/gcode.py`, SHA-256 `a2bcd6949b4263f608eaa71ba1cdfb713553542b7b90de739241b624f06415ae`. **Die Version einer real installierten Klipper-Instanz ist unbekannt.** Repo-intern bestätigt ein älterer Kommentar dieselbe Semikolon-Problematik für einen anderen Pfad (`macros/05_materials.cfg:296–300`).

Die Probe `analyse/override_material_probe.py` rendert reale R2-Templates und gibt Zeilen an diesen echten, gepinnten Parser. Nur `SAVE_VARIABLE` wird durch einen stark vereinfachten In-Memory-Dict-Handler ersetzt; alle anderen Handler sind Stubs. Sie erzeugt und dispatcht **keine Maschinenbefehle**, schreibt keine Klipper-Dateien und ersetzt keinen realen Runtime-Test. Log `analyse/testprotokolle/override_material_probe.log`, Exit 0.

- **16/16 skalare Setterzweige:** Ausgehend von jeweils `*_on=False` wird der Wert im Modell geschrieben, aber das Flag bleibt `False`. Das ist ein synthetischer Parser-/Template-Nachweis, keine Zahl betroffener Maschinen. Bei bereits `True` bleibt das Flag `True`; die Wirkung hängt also vom vorherigen Zustand ab.
- Im Modell ruft `FLOW_CAL_APPLY` den betroffenen Setter auf: Wert 90, Flag zuvor aus → 90 gespeichert, Flag weiter aus; zuvor an → Flag weiter an. Meldungen mit „ON“ im Template sind deshalb kein Zustandsnachweis (`07_start_confirm.cfg:339–345`, `12_maintenance.cfg:1365–1374`).
- `TEMP_TOWER_RESULT` setzt im Modell beide Temperaturwerte, aber aktiviert keine zuvor ausgeschalteten First-/After-Flags. `RETRACT_TOWER_RESULT` setzt entsprechend die Länge, nicht das zuvor ausgeschaltete Flag. `IRONING_RESULT` setzt den Feature-Speed über **separate Zeilen** inklusive Feature-Flag, während der separate Ironing-Flow-Flag aus bleibt. Die Resultmakros selbst liegen in `macros/12_maintenance.cfg:1486–1499,1778–1790,1902–1917`.
- Vergleichspfad: `PA_RESULT` schreibt `ov_pa` und `ov_pa_on` auf **getrennten Zeilen** (`12_maintenance.cfg:805–830`); dieser konkrete Fehler darf nicht pauschal allen Resultmakros zugeschrieben werden. Auch die Feature-Speed-Zweige stehen getrennt (`07_start_confirm.cfg:309–314`).
- Weitere direkte LCD-Aufrufstellen existieren, z. B. `menus/lcd_menues.cfg:6225,6417,6556`; einzelne Menüs können davor oder danach noch anderes tun. Die globale Auswirkung aller Journeys ist nicht vollständig getestet.

### Warum der bisherige Test das nicht ausschließt

`tools/macro_render_test.py:443–446` prüft beim Velocity-Zweig das bloße Vorkommen beider Textfragmente im gerenderten Text. Sie stehen zwar dort, das zweite ist aber im Kommentar. Der Log verzeichnet diesen Check als PASS (`analyse/testprotokolle/macro_render_test.log`). **2100/2100 ist weiterhin das dokumentierte Renderergebnis**, aber nicht der Nachweis, dass Klipper jede behauptete Aktivierung tatsächlich ausführt. Eine spätere Regression muss den Parser und den tatsächlichen Vorzustand einbeziehen; der bestehende Test wurde nicht verändert.

## Verbrauch und Grenzen

| Wert | Pfad / Gegenprobe | Reichweite |
|---|---|---|
| Flow | `_RUN_PRINT_START` wählt bei `apply` nur mit `ov_flow_on` den Override, sonst 100 (`macros/08_print_start_stop.cfg:326–351`). Der isolierte Originalausschnitt ergibt bei Wert 90: Flag aus → 100; Flag an → 90. | Keine vollständige Drucksequenz: `M221` wird durch `macros/06_temp_controls.cfg:737–770` interceptiert und kann im laufenden Druck von Live-Zustand und Layer abhängen. |
| Retraktion | `_APPLY_OV_RETRACT` wählt jeden Parameter anhand des jeweiligen Flags (`macros/10_live_tuning.cfg:734–757`). Isoliert gerendert: Länge 1,5 und Flag aus → aktuelle Firmwarelänge 0,75; Flag an → 1,5. | Es wurde nur das Template gerendert; Firmware-Retraktion, Datei-G10/G11 und Slicer-E-Bewegungen wurden nicht ausgeführt. Ohne `[firmware_retraction]` weist der Makrotext auf einen anderen Dateifix-Pfad hin; seine Wirksamkeit hängt vom tatsächlichen Dateipfad ab. |
| Temperatur | Startauswahl setzt Override-Temperaturen nur bei `apply` und jeweiligem Flag ein; sonst Dateiwert oder Material-DB (`08_print_start_stop.cfg:216–232`). | Weitere Temperaturintercepts und Erstschichtregeln können später wirken. Kein Heizlauf. |
| Ironing | `_SYNC_OV_FEAT` spiegelt Ironing-Flow-Wert und Schalter getrennt (`10_live_tuning.cfg:93–109`); `APPLY_TYPE` nutzt den Flow unter bestimmten Bedingungen und bei gesetztem Flag (`:250–253`). | Das ist eine bedingte Codeverfolgung, keine Aussage, dass jedes Druckformat Feature-Marker enthält oder welcher Wert letztlich am Drucker ankommt. |
| PA | `PA_RESULT` schreibt Wert/Flag getrennt und gibt zusätzlich einen Live-Setter aus (`12_maintenance.cfg:805–830`). Bei Start entscheidet der jeweilige Flag (`08_print_start_stop.cfg:331,340`). | Intercepts, Startwahl und tatsächliche Persistenz sind nicht durch diese Aussage vollständig abgenommen. |

## Materialwerte sind ein eigener, zustandsabhängiger Weg

`SAVE_MATERIAL_TEMPS` liest die gespeicherten Override-**Werte**, ohne deren `*_on`-Flags zu prüfen, und gibt `SAVE_VARIABLE` für Materialtemperaturen, PA, Flow, Retraktion, Smooth, Unretract und Lüfter aus (`macros/05_materials.cfg:116–145`). Ein vorher ausgeschalteter Wert kann also in das Materialpreset eingehen. `SET_MATERIAL` mit Standard `APPLY_PRESET=1` verwendet gespeicherte materialbezogene Werte vor Datenbankdefaults und schreibt Werte und Flags auf getrennten Zeilen (`:36–105`); bei `APPLY_PRESET=0` wird nur die Materialauswahl gerendert (`:107–109`). Der Kommentar `:32–34` zur impliziten Voreinstellung widerspricht dem tatsächlichen Default in Zeile 42.

Isolierter synthetischer Rundlauf mit dem gleichen Parser und In-Memory-Save-Stub: Flow 83, PA 0,123 und Hotend 222 bei **ausgeschalteten** Flags → Save schreibt diese Materialwerte → nach `SET_MATERIAL MATERIAL=PLA` mit Default-Auswahl werden diese Werte und ON-Flags im Modell gesetzt. Bei explizitem `APPLY_PRESET=0` bleibt der vorherige Flow samt Flag dagegen unverändert. Das modelliert keine Schreibfehler, keinen Neustart, keine Interaktion konkurrierender Aufrufe und keine reale Materialgüte. Es ist kein Rat, Werte dadurch zu aktivieren; welche Übernahme erwünscht ist, bleibt fachlich zu entscheiden.

## PA-Test: alter und neue Retraktionsschalter

`CALIBRATE_PA` prüft zunächst die **separaten** Flags und rendert gegebenenfalls `SET_RETRACTION` (`macros/12_maintenance.cfg:633–634`), nutzt für anschließend erzeugte explizite E-Retraktionsbewegungen aber den alten gemeinsamen `ov_retract_on` (`:646–648,690–695,755–765`). `macros/01_state.cfg:444–446,474` migriert separate Flags aus diesem alten Flag nur, falls sie noch fehlen; der alte Eintrag wird separat initialisiert. Die isolierte Renderprobe mit separaten Flags an und Werten 1,5/20 ergibt bei altem Flag aus die Config-Werte 0,75/35, bei altem Flag an 1,5/20. Der tatsächliche gespeicherte Zustand ist unbekannt; ob und wie ein realer PA-Test betroffen wäre, ist nicht bewiesen. Keine Bewegungen ausgeführt.

## Nächste Absicherung – nur als Vorschlag

1. Vor Änderungen für alle Setterpfade ON/OFF-Vorzustände, tatsächliche dispatchbare Befehle, Rückmeldungen und Folgeaufrufe als Regression absichern; Klipper-Referenzversion und Maschinenversion unterscheiden.
2. Ergebnispfade einschließlich Temperatur, Flow, Retraktion und Ironing gegen Startentscheidung, Override-Spiegel, Material-Save/Reload und Restart getrennt testen. Feature- und Einzelwerte nicht als denselben Mechanismus behandeln.
3. Altes/neues Retraktionsflag und Konfigurationsmigration mit echten historischen Zuständen prüfen, bevor eine Disposition vorgeschlagen wird.
4. Kein Hardwaretest oder Produkt-/Dokument-/Backlog-Fix ohne ausdrückliche Freigabe. Die Befunde sind Hinweise auf Zuverlässigkeits- und potenziell sicherheitsrelevante Bedienrisiken, keine validierten Druckparameter.
