# Shutdown-Register — jede Absturzstelle, ihre Ursache, ihr Fix, ihr Prüfsatz

**Warum dieses Dokument existiert.** Die Abstürze kamen über Wochen an immer
wieder denselben Stellen, jeder wurde einzeln repariert — und weil die Fixes
nirgends zusammenstanden, sah jeder neue Vorfall wie ein Rückfall aus. Hier
steht **eine** Tabelle: Stelle → Ursache → Fix → der Test, der den Fix hält.
Der Stand ist `R2-2026-11-18.1` (V2).

**Die gemeinsame Ursache aller „Timer too close"-Abstürze:** Der MCU ist nie
überlastet (im Feld-Log: `mcu_awake=0.014`, `mcu_task_avg=0.000047` — also
weit unter 1 %). Der **Host** liefert die nächste Bewegung zu spät. Klipper
bricht ab, sobald ein Befehl mit einer Zeitmarke ankommt, die auf dem MCU
schon vorbei ist. Jede Zeile unten ist deshalb ein Stück
**Host-Beschäftigung im falschen Moment** — nicht ein Datei- oder
Druckproblem.

---

## 1. Die Stellen im Überblick

| # | Wo es starb | Feldbeleg | Ursache | Fix | Prüfsatz |
|---|---|---|---|---|---|
| 1 | **Homing / Probe, 2. Kontakt, 1-cm-Hub** (3 Sitzungen, 12.11.) | `toolhead (115,115,10)`, Reactor 0.633 s, 20 offene API-Anfragen, `buffer_time=0` in 63–70 % | Start-Dialog bog mit `mode='idle'` ab → **jede** „bewegt sich was?"-Sperre des Watchers blind; der Auswahl-Preview-Push hatte **gar keine** Sperre und schickte 4 KB (inkl. `EXCLUDE_OBJECT`-Polygon) mitten in `G28`; zusätzlich hoben sich zwei Sperren gegenseitig auf (ein gemeinsamer `print_time`-Speicher) | **R255**: `G28`-Wrapper setzt `mode='homing'` (22 Aufrufstellen, einmal zentral) + 2-s-Nachlauf + eigener Sample-Slot je Sperre + Auswahl-Push wartet + Polygon-Obergrenze 1200 Zeichen + `SAVE_VARIABLE` aus dem Homing-Block | `r255_homing_guard_check.py` (18) |
| 2 | Druckstart beim Aufheizen | .96 | Watcher scannte/generierte während `standby` | `_printer_busy` kennt Startphase | `macro_render` R133 |
| 3 | Druckstart, Previews während Homing | .142b (04:04) | `_STATE`=idle **und** `print_stats`=idle | `_motion_active246d` (print_time-Wahrheit) | `macro_render` R246d |
| 4 | Druckende / `PRINT_END` | .125 | End-Choreografie + Watcher-Push `sd_tree` gleichzeitig | 8-s-Nachlauf nach busy→idle | `macro_render` R167 |
| 5 | Nach dem 2. Push pro Dateiauswahl | .137 | Dialog-Re-Peek schickte 20 KB erneut | Dedupe-Fenster 120 s | `macro_render` R242 |
| 6 | Während eines Generator-Jobs | .95/.136s | elf Litho-Threads gleichzeitig, Swap | eine Job-Queue, ein Worker, `nice`, RAM-Gate | `macro_render` R133b/R223 |
| 7 | Beim Laden der SD-Liste | .142 (23:35) | 306 Reactor-Stalls in 7 min: der größte Script des Daemons, 3× wiederholt | ein Versuch, 20 s Timeout, Backoff nach 3 Fehlschlägen | `macro_render` R246c |
| 8 | Beim Umschalten von LED-Effekten | .136m | unveränderter Zustand schrieb die Kette neu | `SET_LED_STATE`-Frühausstieg | `macro_render` R246d |
| 9 | Bei jedem Datei-Scan | .136l | Metadaten ohne Änderungsprüfung neu geschrieben (SD-Karte dauerhaft beschrieben) | `R2-META`-Signatur, `same`-Kurzschluss | `r81` + `macro_render` R215 |
| 10 | Startphase nach Klipper-Neustart | .142a | `_SDM`-Spiegel im RAM starb mit klippy | Nachfüllen des Spiegels erzwungen | `r142_field_coverage` 142 |
| 11 | Pause / Filamentwechsel | .136s | `UNLOAD_FILAMENT` heizte, während ein Bild-Job rechnete | RAM-Gate 110 MB für Bildjobs | `macro_render` R223 |
| 12 | Während `RANGE` erzeugt wurde | 02:18:56 | Generator lief in die Startphase | Job-Queue + busy-Gate | `macro_render` R133 |
| 13 | Beim Full-Bed-Mesh | .58 | Mesh-Fahrwege + Host-Last | KAMP/adaptives Mesh statt Full-Bed | `macro_render` R70 |
| 14 | Beim Booten (kein MCU, aber Stillstand) | .142h/…i | `R2_DOCTOR`: Ziffer an Position 2 → Klipper verweigert den Namen → `Printer is halted`, Endlos-Wiederholung | umbenannt auf `DOCTOR_PACK`, Weiterleitung, Prüfung **aller** Makronamen | `macro_render` R253 |
| 15 | **Boot-Stillstand nach .142k** (12.11. abends, 19:30) | Konsole: `G-Code macro rename of different types ('G28' vs '_G28_RAW')` | R255 hängte dem eingebauten `G28` einen **Alias falschen Typs** an. Klipper verlangt, dass alter und neuer Name denselben Typ haben: „traditional g-code" = Buchstabe + Ziffer (G28, M104, M99110); `_G28_RAW` ist keiner | Alias auf **M99110** - dasselbe Muster wie die Temperatur-Wrapper M99104/M99109 seit R1. **Neue Prüfung in `r166_template_check.py`: jedes `rename_existing`-Paar muss typgleich sein und darf nur einmal vergeben werden** | `r166` (fängt `_G28_RAW` jetzt ab, mit Gegenprobe belegt) + `r255` (19) |
| 16 | **Probe-Abfahrt bei `G28`/Meshing** (drei DOCTOR-Packs 12.11., 22:11/22:13/22:19) | **6 von 8** Shutdowns mit `Requested toolhead position: (115.0, 115.0, Z)` - Z = 4.76 / 5.13 / 8.67 / 9.91 / 10.0 / 10.0. `115,115` ist die `[safe_z_home] home_xy_position` des Feld-`printer.cfg`, `z_hop = 10`: Z zwischen 4.76 und 10.0 ist die **Abfahrt des Sondenstifts**. Im Send-Queue-Dump derselben Sekunde: `queue_step oid=11 interval=64000 count=50` (1-ms-Schritt), dazwischen `neopixel_send` (3× in 12 ms), `tmcuart_send`, `st7920_send_data`; vorher `Neopixel update did not succeed`, `bytes_retransmit=85`, `buffer_time=0.000`, und die Clock-Schätzung lag 191 ppm daneben (`clock_est` 63998744.721 statt 64000000) | **R257**: LED-Kette wird für die Dauer der Bewegung stummgeschaltet (`_LED_QUIET`), nicht nur entprellt. Eine Zustandsänderung schreibt den Streifen 2-4× hintereinander (STOP_LED_EFFECTS, SET_LED_EFFECT, Nozzle, Bedlight); die WS2812-Ausgabe bit-bangt der MCU mit abgeschalteten Interrupts, und ein fehlgeschlagener Transfer blockiert den **Host** bis zum Serial-Timeout. `G28`, `_CALIBRATE_MESH_PROFILE`, `SCREWS_TILT_CALCULATE` und `PROBE_CALIBRATE` klammern die Bewegung jetzt mit `_LED_QUIET ON=1` / `ON=0`; der Watcher heilt eine hängengebliebene Stummschaltung | `r257_crash_guard_check.py` (15 Prüfungen + 7 Gegenproben) + `macro_render` R257 (7 Funktionstests) |

---

## 2. Was am 12.11. tatsächlich im Log stand (Zahlen, nicht Vermutungen)

Aus `klippy.log` des Nutzers, die drei Sitzungen nach dem Update auf `.142j`:

* **Position beim Shutdown:** `(115.0, 115.0, 10.0)` und `(115.0, 115.0, 5.13)`
  — Bettmitte, nach der zweiten Probe, auf dem Hub. Genau die Stelle, die der
  Nutzer beschreibt.
* **Reactor-Stalls:** 0.361 s und **0.633 s**, immer mit
  `SelectReactor._got_pipe_signal` + `ClientConnection.process_received`
  (also Moonraker-Anfragen, die klippy im Reactor abarbeitet), dazu
  `DelayedGcode`, `TMCErrorCheck`, `LEDHelper`.
* **`Dumping 20 requests for client …`** — zwanzig API-Anfragen lagen noch in
  der Warteschlange, als der MCU aufgab.
* **`buffer_time=0.000` in 63–70 %** aller `Stats`-Zeilen davor: der Host hatte
  nie einen Bewegungsvorrat, jeder Stall schlägt direkt auf die nächste
  Zeitmarke durch.
* **`bytes_retransmit` 9 → 13** und `Dumping receive queue 100 messages`:
  der serielle Pfad war zusätzlich verstopft — Folge der Befehlslawine, nicht
  ihre Ursache (MCU-Auslastung dabei < 1 %).
* **Unser eigener Beitrag:** um 597.375 s zwei **identische** `gcode/script`-
  Aufrufe mit `_PREVIEW_SET` + `_FILE_INFO` + `_PREVIEW_TEMPS` + dem
  **kompletten `EXCLUDE_OBJECT`-Polygon** (mehrere KB) — während `G28` lief.
* **Der `R2_DOCTOR`-Fehler** in der Konsole stammt aus der Zeit **vor** dem
  Update (11:51). Die drei Boots danach laden `DOCTOR_PACK` — die Umbenennung
  greift.


## 2a. Was diese Runde über UNSERE Fehler sagt (R255 → .142k → .142l)

R255 hat den Homing-Absturz an der richtigen Stelle gepackt (unser Host-Werk im
Probe-Fenster) und dabei **zwei** neue Boot-Stillstände erzeugt — beide von
genau der Klasse, die Priorität 1 verbietet („der Drucker muss bedienbar
bleiben"):

1. `description:` in einer `[delayed_gcode]`-Sektion → Klipper verweigert den
   Boot. Gefunden von `r166`, behoben vor der Auslieferung.
2. `rename_existing: _G28_RAW` → Alias falschen Namenstyps → `Printer is
   halted`. Gefunden vom **Feld**, nicht von uns — deshalb existiert die
   Prüfung jetzt (`r166` prüft alle Paare, inklusive Doppelvergabe).

**Die Lehre, festgeschrieben:** jede neue Klipper-Sektion und jedes
`rename_existing` muss durch `r166_template_check.py` **und** durch die
Typregel — ein grüner Jinja-Compile beweist nicht, dass Klipper die Config
lädt. Seit `.142l` prüft die Batterie beides statisch, mit Gegenprobe.

## 3. Was der Nutzer daraus folgern muss

* **Die Datei ist in Ordnung — und die Segmentfix-Diagnose war ein Irrweg.**
  Der Absturz passiert **vor** dem Druckstart, in der Homing-Sequenz, also
  bevor irgendeine Bewegung aus der Datei gelaufen ist. `MOVERATE=5372` ist
  ein echtes Risiko für *später*, aber nicht die Ursache dieses Shutdowns.
* **Es gibt keinen Befehl, den man vorher tippen müsste.** Der Fix liegt im
  Postprozessor und in den Makros; nach dem Update ist die Homing-Phase für
  den Watcher „unsichtbar" — er schweigt dort vollständig.

## 4. Was bewusst NICHT angefasst wurde

* **UART** (`/dev/ttyAMA0`, 250 kHz): unverändert. Die Retransmits sind Folge
  der Lawine; ein Baud-/Timing-Eingriff würde das Fehlerbild nur verschieben.
* **`max_z_velocity` / `max_z_accel`** (20 / 50): unverändert — Bewegungsgrenzen
  sind Nutzer-Setting, kein Fix-Werkzeug.
* **`samples: 2`** (jede Stelle zweimal beprobt): bleibt, ist Nutzerregel.
* **Der stabile Postprozessor** bleibt der Einstiegspunkt; die experimentelle
  Kopie ist byte-gleich (Prüfsatz R252).

## 5. Prüfstand, der zu diesem Register gehört

```
python3 tools/r255_homing_guard_check.py   # 18 - dieser Fix
python3 tools/macro_render_test.py         # 2093
python3 tools/r81_golden_check.py          # 23
python3 tools/r197_gen_sweep.py            # 472
python3 tools/r142_field_coverage.py       # 142
python3 tools/r142_spell_lint.py           # 0 Verdacht
python3 tools/r166_template_check.py       # alle Templates kompilieren
python3 tools/r232_preset_audit.py         # 58
python3 tools/r165_doc_check.py            # Doku == Code
python3 tools/r199_zip_check.py            # 18
```
