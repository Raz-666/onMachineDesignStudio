# Schichterkennung und Layer-Verbraucher – Vertiefung

**Status:** Analyse auf `ce29e2a`, keine Produktänderung und keine Freigabe zur Implementierung. Die hier untersuchten Dateien sind temporäre synthetische G-Codes; kein Klipper-System und kein Drucker wurde angesprochen. `MASTER-TODO.md` bleibt unverändert die einzige Aufgabenliste.

## 1. Was das System heute nachweislich macht

1. `process()` sammelt Layer-Kommentare und beobachtet parallel die Bewegungen (`tools/r2_postproc.py:19724–19820`). Existieren schon `LAYER_MARK`, werden sie erhalten; andernfalls werden Layer-Kommentare bevorzugt und nur bei deren Fehlen die `_ZScan`-Ergebnisse verwendet (`:19925–19949`).
2. `_ZScan` speichert den zuletzt angegebenen absoluten Z-Wert auch bei Travel. Er wertet eine Zeile als „extruding“, wenn ein E-Parameter und X oder Y vorhanden sind (`:20267–20284`). Es wird in diesem Zweig nicht geprüft, ob das E-Delta positiv, null oder negativ ist. Der erste Z-Wert ist Startwert; danach werden Höhenänderungen als Marker erfasst (`:20286–20307`).
3. Die Zahl dieser eingefügten Marker wird als `summary['layers']` und – wenn nicht bereits aus Konfiguration gesetzt – in `_FILE_INFO TOTAL_LAYERS` verwendet (`:19945,19964–19970`). `r110_gcode_dialects.py:213–222` testet für den Z-Scan ausdrücklich die Zahl der **Wechsel**, nicht die Gesamtzahl physischer Ebenen. Das ist wichtig für die Bedeutung der Zahl; die Konsequenzen für reale Laufzeit sind separat zu testen.
4. Die `SKIN`-Sonderregel nutzt die Zahl bisher gefundener Layer-Kommentare (`:19854–19864`) und nicht das später ermittelte Z-Scan-Ergebnis. In der dokumentierten Approximation wird erstes SKIN zu BOTTOM, späteres zu TOP; höhere echte Bottom-Skins sind laut Kommentar bereits eine bekannte Einschränkung.
5. `macros/06_temp_controls.cfg:538–557` verarbeitet `LAYER_MARK`: im Druckmodus wird `s.layer + 1` gesetzt und `layer_marks=True`. Bei `n == 2` können unter anderem Speed, Temperatur und Lüfter betroffen sein (`:562–625`); bei aktivem Stop-at-Layer kann `_END_AT_LAYER` gerendert werden (`:635–638`). Solange keine Marker erkannt wurden, kann der verzögerte `_STATE_WATCHER` Z-basiert zählen (`macros/01_state.cfg:814–846`). Das reale Timing ist asynchron und hier nicht bestimmt.

## 2. Reproduzierbare Gegenproben

### A. Kommentarabhängige Schichtzahl und SKIN

`python3 analyse/layer_comment_probe.py` erzeugt zwei dreischichtige synthetische Dateien mit exakt gleichen Bewegungs- und Typzeilen; nur `;LAYER_CHANGE` wird entfernt:

| Variante | Erkennung | `TOTAL_LAYERS` | `APPLY_TYPE` nach den drei SKIN-Kommentaren |
|---|---|---:|---|
| mit Kommentaren | Layer-Kommentare | 3 | BOTTOM, TOP, TOP |
| ohne Kommentare | Z-Scan | 2 | BOTTOM, BOTTOM, BOTTOM |

Das zeigt unterschiedliche Ausgabe für gleiche Bewegungen. **Nicht** bewiesen: welche SKIN-Rolle für diese künstlichen Flächen geometrisch oder slicerbedingt „richtig“ ist. Die konkrete Wahl von TOP/BOTTOM ist in der Quelle eine dokumentierte Näherung; sie kann aus den hier gegebenen Daten nicht als Ground Truth gelten. Das Entfernen von Kommentaren darf jedoch keine unbegründete Sicherheit vorgaukeln.

### B. Z-Hop und E-Null/Rückzug

`python3 analyse/zhop_eprobe.py` untersucht M83 und M82: Auf Z 0,2 wird gedruckt, auf Z 0,4 hochgefahren, eine XY-Bewegung vorgenommen, auf Z 0,2 zurückgefahren und dort weitergedruckt. Erst danach beginnt die nächste Druckhöhe Z 0,4. Für die Zwischenbewegung:

| XY-Bewegung während Hop | M83 | M82 | Ergebnis |
|---|---|---|---|
| ohne E-Parameter | `G1 X12 Y0` | gleich | kein Layer-Marker vor der Hop-Bewegung |
| E-Delta null | `G1 X12 Y0 E0` | `G1 X12 Y0 E1` bei vorigem E1 | **zusätzlicher Marker direkt vor der Hop-Bewegung** |
| E-Delta negativ | `G1 X12 Y0 E-0.2` | `G1 X12 Y0 E0.8` bei vorigem E1 | **zusätzlicher Marker direkt vor der Hop-Bewegung** |

Alle Varianten bekommen später einen Marker vor der echten Z-0,4-Druckbewegung. Das Vorhandensein eines E-Parameters ohne positive Extrusion löst im Hop also einen zusätzlichen Marker aus. Im Beispiel stehen ohne den zusätzlichen Marker `TOTAL_LAYERS=1`, mit ihm `TOTAL_LAYERS=2`; die zweite Zahl entspricht zufällig der Zahl der beiden Ebenen, aber einer der beiden Marker sitzt an der falschen Bewegung. Eine vermeintlich passende Gesamtzahl ist hier kein Lagebeweis.

`analyse/zhop_mutation_probe.py` führt den aus dem Code extrahierten `_ZScan` isoliert aus und verändert testweise **nur** die E0-Bedingung im Speicher. Die Kontrollmutation entfernt den E0-Fehlmarker, lässt den Rückzugsfall aber falsch. Sie ist absichtlich unvollständig, behandelt insbesondere M82 nicht korrekt und ist **kein Fixvorschlag**. Sie isoliert lediglich, dass die bloße Existenz des E-Worts zum E0-Befund beiträgt.

`tools/r111_geom_test.py:189–205` prüft Z-Hop am anderen Objekt `_GeomScan` mit Travel hoch/runter, nicht `_ZScan` mit E0 oder XY-Rückzug. Der grüne Test widerspricht dieser Gegenprobe daher nicht.

### C. Was ein eingefügter Marker im Template auslösen kann

`analyse/zhop_stop_render_probe.py` rendert den unveränderten Text des Klipper-Makros `LAYER_MARK` mit Jinja2, ohne die gerenderten Befehle auszuführen. Für explizit vorgegebene Zustände:

| Vorher `s.layer` | `stop_at_layer` | Gerenderte Aktion |
|---:|---:|---|
| 0 | 0 | kein `_END_AT_LAYER` |
| 0 | 1 | `_END_AT_LAYER LAYER=1` |
| 1 | 2 | `_END_AT_LAYER LAYER=2` |
| 1 | 3 | kein `_END_AT_LAYER` |

Ein fehlplatzierter Marker **kann unter den genannten Vorbedingungen** also eine eigentlich an eine Schicht gebundene Aktion rendern. Analog kann bei `n=2` im getesteten Zustand `M220 S100` erscheinen (`analyse/layer_mark_render_probe.py`). Dies ist ein konditionaler Template-Nachweis, **keine** Simulation der Klipper-Ereignisreihenfolge, kein ausgeführter Stop und kein Beweis für ein reales Druckerereignis. Ob `_STATE_WATCHER` vorher eine Schicht gezählt hat, muss durch einen kontrollierten Integrations-/Hardwaretest geprüft werden.

### D. Initialisierung und mögliche Reihenfolgen des Zählers

`PRINT_START` setzt im normalen Startzweig `layer=0`, `layer_z_max=0` und `total_layers` aus dem Parameter, gefolgt von `_LIVE_RESET` (`macros/08_print_start_stop.cfg:66–112`). `_LIVE_RESET` setzt seinerseits `layer=0`, `layer_marks=False` und `layer_z_max=0` (`macros/10_live_tuning.cfg:61–67`). Auch der Legacy-Erkennungszweig im Watcher initialisiert diese Layer-Werte (`macros/01_state.cfg:675–689`); der Watcher plant sich mit `DURATION=1` erneut ein (`:1038`), was keine Garantie für einen bestimmten Tickzeitpunkt ist.

`analyse/layer_order_probe.py` kombiniert den **isoliert gerenderten Z-Tracking-Zweig** des unveränderten Watchers und das unveränderte `LAYER_MARK`-Template in einem minimalen Speichermodell. Vorgaben: Druckmodus, Layer 0, Z-Maximum 0, keine Marker, `stop_at_layer=2`. Es werden nur die ausgegebenen Zustandszuweisungen für Layer/Marker/Z im Modell angewandt:

| Angenommene Reihenfolge | Beobachtete Template-Ausgabe |
|---|---|
| Watcher bei Z=0,2 → Marker bei Z=0,4 | Watcher zählt 1; Marker zählt 2, rendert `M220 S100` und `_END_AT_LAYER LAYER=2`. |
| Marker bei Z=0,4 → Watcher bei Z=0,4 | Marker zählt 1 und setzt `layer_marks=True`; der isolierte Watcher-Zweig zählt nicht. |

Das zeigt **Reihenfolgeabhängigkeit unter expliziten Annahmen**, nicht dass diese Reihenfolgen bei einem konkreten Druck tatsächlich eintreten. Höher priorisierte `elif`-Zweige des Watchers, Start-/Pausenablauf, Planner, Timer und die Ausführung der ausgegebenen Befehle sind in dieser Probe nicht simuliert. Insbesondere wurde kein Stop ausgeführt. Klipper-Integration und zeitliche Erreichbarkeit bleiben offen.

### E. `TOTAL_LAYERS` im Startpfad

`analyse/start_layer_total_probe.py` rendert die unveränderten Templates für einen synthetischen Start mit `TOTAL_LAYERS=30`, `mode=idle`, ohne Startdialog. Der normale Zweig gibt zuerst `SET_GCODE_VARIABLE ... total_layers VALUE=30` aus und anschließend `_LIVE_RESET`. Das separat gerenderte Reset-Template enthält `SET_GCODE_VARIABLE ... total_layers VALUE=0`. In einer **ausschließlich auf diese ausgegebenen Zuweisungen beschränkten** Entfaltung ist der letzte Wert 0 (`macros/08_print_start_stop.cfg:107–112`, `macros/10_live_tuning.cfg:61–63`).

Die Probe verarbeitet außerdem eine temporäre synthetische Datei mit 30 Layer-Kommentaren: `process()` setzt `_FILE_INFO TOTAL_LAYERS=30` **vor** `PRINT_START TOTAL_LAYERS=30`. `_FILE_INFO` selbst setzt die Statusvariable bei positivem Wert (`macros/08_print_start_stop.cfg:938–940`), aber diese frühere Zuweisung würde in der betrachteten Folge ebenfalls vor dem Reset liegen. Spätere Setzer, alternative Startpfade und ein tatsächlicher Klipperzustand wurden nicht durchgespielt. Der Marker zeigt einen Nenner nur bei `s.total_layers > 0` (`macros/06_temp_controls.cfg:557–558`); keine weitergehende Druck- oder UI-Wirkung behaupten.

### F. Geplante Pausen – zwei konditionale Randfälle

`analyse/layer_pause_probe.py` rendert `PAUSE_AT_LAYER` und `LAYER_MARK` ohne Ausführung:

1. `PAUSE_AT_LAYER LAYER=1` gibt `SAVE_VARIABLE ... pause_at_layer VALUE=1` aus (`macros/06_temp_controls.cfg:782–790`); die Markerbedingung verlangt aber zugleich `n > 1` (`:632–634`). Renderproben für Marker 1 und 2 liefern keine geplante Pause. Der Z-Tracking-Zweig enthält dieselbe Bedingung (`macros/01_state.cfg:902–907`). Eine ausgelöste oder versäumte reale Pause ist damit nicht getestet.
2. Stehen synthetisch `pause_next_layer=True` **und** `pause_at_layer=2` bei Marker 2 an, gewinnt der `if`-Zweig für „nächste Schicht“; er setzt nur `pause_next_layer` zurück. Der `elif`-Zweig für Layer 2 läuft nicht (`macros/06_temp_controls.cfg:628–634`; gleiche Priorität im Watcher `macros/01_state.cfg:902–907`). Wenn nach einem angenommenen Resume keine anderen Zustandsänderungen stattfinden, liefert Marker 3 keine Pause und `pause_at_layer=2` bleibt im Modell stehen. Ein tatsächlicher Pause-/Resume-Ablauf, weitere Rücksetzpfade und praktische Häufigkeit wurden nicht getestet.

Diese Befunde sind unabhängig davon, ob der unter B gezeigte Z-Hop in der Praxis einen Marker auslöst. Sie rechtfertigen eigene Regressionstests und keine spontane Änderung an Pause-, Start- oder Stop-Choreografie.

## 3. Testlücken und risikogerechte Abnahme

Die Punkte unten sind **Vorschläge**, keine Implementierungsfreigabe:

- Für Z-Hop: M82/M83, E-Wort fehlt/0/positiv/negativ, G92 direkt davor, XY+E-Wipe, E-only-Retract, Modal-Z und G90/G91 gegeneinander. Markerpositionen und Bewegungs-/E-Deltas zeilenweise prüfen, nicht nur eine globale Anzahl.
- Für Marker und Zählung: erste reale Druckschicht, gefolgte Wechsel, unregelmäßige Höhen, Z-Hop, kommentarlos vs. kommentiert, Vase und sequentielle Objekte. `TOTAL_LAYERS`, Anzahl und Position aller `LAYER_MARK`, `_FILE_INFO` und `SKIN` getrennt vergleichen.
- Für Verbraucher: Stub-Zustände und gezielte Watcher-Reihenfolgen, danach Klipper-Simulation; `layer_marks`, Current/Total, Layer-2-Speed/Fan/Temperatur, Pause-at-Layer und Stop-at-Layer untersuchen. Ein echtes Gerät nur nach ausdrücklicher Freigabe und sicherem Testplan.
- Zusätzlich Golden-Master-Prüfung von AS SLICED/LEGACY, Homing, Probe, Purge, Start/Ende und Menü-Exit; Originaldateien dürfen in künftigen Diagnosepfaden nicht verändert werden. Vor jeder produktiven Änderung Übergabe-Regel `next` beachten und separate Freigabe einholen.
- Bei fehlender geometrischer Ground Truth Rollen als unklar dokumentieren, statt aus Testdaten eine willkürliche TOP-/BOTTOM-Wahrheit zu erfinden.

Belege: `analyse/testprotokolle/layer_comment_probe.log`, `zhop_eprobe.log`, `zhop_mutation_probe.log`, `zhop_stop_render_probe.log`, `layer_mark_render_probe.log`, `layer_order_probe.log`, `start_layer_total_probe.log`, `layer_pause_probe.log`. Hauptbericht: `analyse/BESTANDSAUFNAHME-UND-ARCHITEKTUR.md`.
