# Override-Bedienpfade und Ironing: vertiefte Offline-Prüfung

Stand 15.11.2026, Produktstand `ce29e2a`. Ergänzung zu `analyse/KALIBRIERUNG-ERGEBNISSE-UND-OVERRIDES.md`. **Keine Maschinenanweisungen, Produktänderungen oder Backlog-Disposition.**

## 1. Umfang des Setter-Befunds

Die statische, lesende Textinventur `analyse/override_aufruf_inventur.py` erfasst `macros/*.cfg` und `menus/*.cfg`: 20 Dateien, 475 Textstellen, davon 96 mit einem der 16 skalaren Namen, 376 Feature-/Aliasstellen, zwei dynamische Namen und eine sonstige Stelle (die ist ein Hilfetext, kein Aufruf). Vollständige Fundstellen mit Sektion und Zeile: `analyse/OVERRIDE-AUFRUFE.tsv`; Log `analyse/testprotokolle/override_aufruf_inventur.log`, Exit 0.

Diese Zahlen sind **Textstellen, keine ausgeführten Aktionen, erreichbaren Menüs, unabhängigen Fehler oder betroffenen Maschinen**. Nicht untersucht: andere Dateitypen, Web-/Python-generierte Befehle, Includes, konkrete Sichtbarkeit und alle weiteren Befehle im jeweiligen Menü. In Material-Untermenüs wird z. B. zuerst ein Materialwert gespeichert und der Setter nur bei passendem ausgewähltem Material aufgerufen. Feature-Zweige und Aliase dürfen nicht als die 16 skalaren Semikolon-Zweige gezählt werden.

Die Wurzel bleibt `macros/07_start_confirm.cfg:316–335`: Bei skalaren Namen steht das `_on`-Schreiben hinter `;` in derselben Zeile. Der Referenz-Klipper-Parser und die Grenzen des Nachweises stehen im Vorgängerbericht. Die Version einer realen Klipper-Installation ist nicht bekannt.

## 2. Reproduzierte Bedienpfade – alles offline

`analyse/override_bedienpfade_probe.py`, Log `analyse/testprotokolle/override_bedienpfade_probe.log`, Exit 0: Original-Jinja für ausgewählte Menüs/Makros; gepinnter Upstream-Parser; `SAVE_VARIABLE` nur in einem Python-Dict; andere Aktionen Stubs. Verschachtelte Setteraufrufe werden explizit im Modell aufgefaltet. Das Modell nimmt erfolgreiches synchrones Speichern und erneutes Rendern pro Aufruf an. Es führt weder eine echte Menüsitzung, Klipper noch Motoren/Heizer aus.

| Pfad | Ausgang / Ergebnis im Modell | Einordnung |
|---|---|---|
| Pre-Print Flow-Wert | Original-LCD `menus/lcd_menues.cfg:6212–6225`: Wert 90 bei Flag vorher `False` → Wert 90, Flag `False`; bei vorher `True` bleibt es `True`. | Ein separater `TOGGLE_OVERRIDE` kehrt den jeweiligen Vorzustand um (`macros/07_start_confirm.cfg:352–366`): aus→an, an→aus. Dies ist eine Zustandsbeobachtung, **keine Bedienempfehlung**. |
| Datei → Pre-Print | Menü `menus/lcd_menues.cfg:8331–8336`, Makro `macros/08_print_start_stop.cfg:587–615`. Synthetische Preview mit Bett, Düse, Lüfter, PA und Flow erzeugt sieben Setteraufrufe; bei sieben zuvor ausgeschalteten Flags bleiben alle sieben aus, bei sieben zuvor eingeschalteten alle an. | Werte werden im Modell gespeichert; Meldung und Beep sagen nichts über Aktivierung. Vorliegende Preview-Werte, Menüerreichbarkeit und echter Start wurden nicht geprüft. |
| PLA-Material-Flow | Menü `menus/lcd_menues.cfg:4229–4240`: 92 wird als `mat_pla_flow` gespeichert. Bei ausgewähltem PLA folgt der Setter und `ov_flow` wird 92, Flag bleibt aus; bei ausgewähltem PETG bleibt `ov_flow` im Modell 100. | Späteres Laden des Materialpresets ist ein anderer Pfad und kann Flags setzen; siehe Vorgängerbericht. |
| Ironing-Guard | Bei synthetischem `mode=printing` rendert `IRONING_CAL` `RESPOND ...; M117 ...` (`macros/12_maintenance.cfg:1800–1801`). Der Referenzparser dispatcht nur RESPOND, kein separates M117. | Der Busy-Guard selbst bleibt im gerenderten Zweig erhalten. Dies belegt weder ein Ausbleiben anderer Warnungen noch eine Druckerbewegung. Weitere solche Meldungszeilen stehen `:1623,1827–1835` und sind hier nicht einzeln ausgeführt. |

Der bisherige Test `tools/macro_render_test.py:3336–3344` für `FILE_AS_PRESET` prüft nur das Vorhandensein der **Setter-Aufruftexte** und des Beeps. Sein PASS-Name spricht von „overrides ON“, der Test verfolgt aber die verschachtelte Setterausführung und Flags nicht (`analyse/testprotokolle/macro_render_test.log`: R62). Das widerspricht nicht der gezählten 2100/2100-Renderergebniszahl; es begrenzt, was sie beweist.

## 3. Ironing-Karte: mm/s werden als Prozentfaktor übernommen

Das ist eine **andere** Abweichung als der Semikolon-Flagfehler:

1. `IRONING_CAL` druckt Karten mit `Ss` als absolute Geschwindigkeit in mm/s (`macros/12_maintenance.cfg:1819–1821,1857,1868–1872,1883–1887`). Im isolierten Originaltemplate meldet Karte 2 **30 mm/s** und rendert G1 mit `F1800.0` mm/min.
2. `IRONING_RESULT` übergibt denselben Zahlenwert 30 an `SET_OVERRIDE_VALUE NAME=feat_spd_ironing` und meldet ihn weiter als mm/s (`:1902–1916`).
3. Dieser Feature-Speed wird von `APPLY_TYPE` jedoch als **Prozent** auf den globalen Geschwindigkeitsfaktor multipliziert (`macros/10_live_tuning.cfg:191–198,216–224`); auch das LCD bezeichnet ihn als `%` (`menus/lcd_menues.cfg:7327–7336`).
4. Gegenprobe mit ausdrücklich angenommenem synchronisiertem Feature-Spiegel `(on, speed=30, accel=0, flow=100, PA=0)`, `g_speed_clean=100`, aktivem IRONING-Feature und Druckmodus: Original-`APPLY_TYPE` rendert `M99220 S30.0`. Das ist ein 30-%-Faktor, keine Anweisung für eine absolute Sollgeschwindigkeit von 30 mm/s. Bei einem rein rechnerischen Datei-Soll von 60 mm/s und sonst unverändertem Faktor ergäbe das 18 mm/s; tatsächliche Geschwindigkeit, Datei-F-Werte und Maschinenlimits wurden nicht ausgeführt oder gemessen.
5. Bei angenommenem `fova_iron_flow=15` erzeugt das gleiche Template mit ausgeschaltetem Flow-Flag `M99221 S100`, mit eingeschaltetem Flag `M99221 S15`. Gültig nur für die getesteten Bedingungen: Feature aktiv, neutraler Feature-Flow 100, keine anderen Live-/globalen Faktoren, synchronisierte Spiegel. Der reale Extrusionsbetrag hängt auch vom G-Code selbst ab; aus diesem Test folgt kein Nachweis der tatsächlich aufgetragenen Materialmenge.

Die Semikolon-Schwäche und die Einheitenabweichung wirken hier unabhängig: Der Feature-Speed-Zweig aktiviert sein Feature auf separater Zeile; der skalare Ironing-Flow-Zweig aktiviert ein vorher ausgeschaltetes Flag nicht.

## 4. Individuelle Kartenparameter werden bei der Ergebnisauswahl nicht rekonstruiert

`IRONING_CAL` akzeptiert `F1..F6` und `S1..S6` (`12_maintenance.cfg:1816–1821`), speichert in diesem Makro aber nur Temperatur, Kartenanzahl, Start-Layer und Layerhöhe (`:1822–1825`); `IRONING_RESULT` nimmt für Karten 1–3 gespeicherte `iron_cal_f/s*` oder Defaults und für Karten 4–6 feste Werte (`:1911–1914`). Das Menü erwähnt Karten 4–6 über Konsolenparameter (`menus/lcd_menues.cfg:16040–16044`).

Isolierte Fälle ohne vorher gespeicherte Kartenparameter: `IRONING_CAL` rendert bei explizitem `F2=17 S2=37` bzw. `F4=17 S4=37` jeweils die gewählte Karte mit 17 % / 37 mm/s. Nach ausschließlich den im Makro ausgegebenen und im Dict angenommenen Saves rendert `IRONING_RESULT` für Karte 2 stattdessen Setterwerte **15 / 30**, für Karte 4 **25 / 50**. Ein tatsächlicher Ausdruck, erfolgreiche Auswahl oder Firmwareablauf ist damit nicht belegt. Bereits vorhandene gespeicherte Werte können für Karten 1–3 andere Resultate ergeben; das ist gesondert zu berücksichtigen.

## 5. Offene Nachweise und Stopp

- Weitere mögliche Aufrufpfade, andere Klipper-Versionen, UI-Sichtbarkeit, Speicher-/Neustartfehler, konkurrierende Ereignisse und reale Dateien nicht vollständig geprüft.
- Vorschlag für eine spätere Freigabeprüfung: Testmatrix aus OFF/ON-Vorbedingungen, Parserausgabe, gespeicherten Werten, User-Rückmeldung, Material-/Datei-Preset, Feature-Spiegel und tatsächlicher Einheit; für Ironing auch Kartenparameter 1–6 und unterschiedliche Dateigeschwindigkeiten. Das ist keine Implementierungsfreigabe.
- Kein Produktcode, keine TODOs, keine Texturthemen und keine Maschine wurden geändert. Der Hauptbericht und Kalibrierungsbericht sind um den Befund ergänzt.
