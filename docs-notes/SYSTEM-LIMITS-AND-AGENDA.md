# R2-D2 — Systemgrenzen, Agenda & Klipper-Anpassungsbedarf

**Stand:** R2-2026-11-26.14 (nach CALIBRATE_BELT-Neubau, Audit-P1-02).
**Quellen:** `docs/OVERVIEW_DE/EN.md`, `MANUAL.md` §23, `COMPATIBILITY.md`,
`docs/SHUTDOWN_REGISTER.md`, `docs-notes/MASTER-TODO.md`,
`docs/PORTABILITY_SOUND_DISPLAY.md`, `docs/LCD_MENU_PORTABILITY.md`,
`docs/WEBUI_MOONRAKER.md`, `docs/STRINGART_DESIGN.md`, `docs/frame_design.md`,
Klipper-Config-Changes (klipper3d.org), Audit-Bericht 2026-11-28,
ChatGPT-Bewertung v26.10.

Dieses Dokument ist eine **inventurartige Zusammenfassung** — keine
Richtlinie. Feldabnahme am Drucker bleibt exklusiv beim User.

---

## 1. Bekannte Grenzen des Systems

### 1.1 Hardware / Plattform (OVERVIEW, COMPATIBILITY, Audit)

- **Zielkinematiken:** kartesische + CoreXY sind im Umfang. **Delta und
  Belt-Drucker werden nicht empfohlen** (rechteckige Bettannahmen,
  Platzierungsannahmen). Referenzplattform: modifizierter Ender-3,
  SKR Mini E3 V3.0.
- **Bettbereich:** Achsgrenzen ≠ nutzbare Bettfläche. Der echte nutzbare
  Bereich muss in `_R2_CONFIG`/`r2_hardware.cfg` gesetzt sein; ohne
  Profil fallback Ender-3 220×220 (x 0..220, y −3..217).
- **Probe:** Offsets, erreichbare Fläche, Parken und Prime-Linie müssen
  zur realen Hardware passen. Probe-Z-Qualität ist Feldabnahme.
- **LEDs:**Effekte brauchen `klipper-led_effect` + passendes
  `[neopixel]`/`[dotstar]`. Ohne optionale Hardware fallen Funktionen
  aus oder müssen abgeschaltet werden.
- **Sound:** Benötigt passenden Beeper; ohne ihn spielt M300 stumm
  (Guard, kein Fehler). Pi Zero 2 W hat **keine** Klinke/Analog-Audio
  (klinke/hdmi nur auf 3B+).
- **Runout:** Filamentsensor + exakte Abschnittsnamen nötig; ohne
  Sensor keine automatische Runout-Erkennung.
- **Live-Retraktion:** Benötigt Klipper-Firmware-Retraktion + passende
  Slicer-/G-Code-Konfiguration; ohne sie ist die Live-Wirkung
  eingeschränkt.
- **Gantry-Sync:** `SYNC_GANTRY` ist für den parallelen Dual-Z-Aufbau;
  unabhängige Z-Motoren brauchen Z-Tilt/QGL.
- **Input Shaper:** Messung braucht ADXL/`[resonance_tester]`; ohne
  Sensor nur der manuelle Override (`SHAPER_MANUAL`, E2-erledigt).
- **LCD:** Zeichensätze variieren (ST7920/UC1701/SSD1306/HD44780);
  Umlaute/Sonderzeichen im Menü können gartigel ausgegeben werden.

### 1.2 Performance / Ressourcen (OVERVIEW §Performance, SHUTDOWN_REGISTER)

- **Maschine begrenzt durch:** Klipper-Hostreaktor, MCU-Kommunikation,
  RAM, SD-Karte, Druckzeit.
- **Hotspots:** großes `menus/lcd_menues.cfg` (dynamische Menütexte im
  Reaktor gerendert); **Featuregrenzen & Befehlsfrequenz** (`APPLY_TYPE`,
  Layer-Marker, Statusmeldungen, Lüfter/PA/Accel-Wechsel, LED-Updates);
  Datei-/Geometrieanalyse (Streaming RAM-getestet, aber Rasterung/STL-
  Export/große Audits kosten CPU/RAM/I/O); **Generator-Jobs** (Litho,
  ColorPic, StringArt deutlich länger auf Pi Zero 2); **Watcher + viele
  Dateien**; **Live-Webabfragen** (Caches reduzieren, mehr Clients =
  mehr Last); **LEDs + Sondieren/Homing** (teilen den Kommunikkanal mit
  Bewegungen → LED-Ruhephasen, Timer-too-close-Schutz); **persistierende
  Schreibvorgänge** (große neu erzeugbare Listen in RAM, Hot-Path in
  `_STATE` gespiegelt).
- **MCU ist selten die Ursache:** Im Feld-Log `mcu_awake=0.014`,
  `mcu_task_avg=0.000047` (≪1 %). **Alle 16 Shutdown-Stellen**
  (SHUTDOWN_REGISTER) sind **Host-Aktivität im falschen Moment** —
  behoben mit Bewegungs-Sperren, `_LED_QUIET`, Job-Queues, Dedupe-
  Fenstern, RAM-Gates. Siehe auch §5.

### 1.3 Honest functional limits (MANUAL §23)

- **nozzle_diameter = printer.cfg-Wahrheit:** alle Generatoren lesen
  `[extruder] nozzle_diameter` (Fallback 0.6, Konsolenhinweis).
- **Texture:** erste Außenwand-Vertex und Nulllängen-Restarts bleiben
  untexturiert (kein Annäherungsvektor); Dateien ohne Außenwände
  bekommen Null-Shift; V99-Vollversion verweigert mit Aufräum-Hinweis.
- **Sequential-Erkennung** braucht vorheriges Objekt ≥1.6 mm hoch.
- **Legacy-Dateien** (ohne APPLY_TYPE): Feature-Faktoren sofort, aber
  nur der GLOBAL-Faktor wird ab Layer 2 / nach Resume neu angewandt.
- **AS SLICED** = keine Injektionen, aber Homing/Mesh/Purge laufen
  VORN dem File.
- **Unbekannte M-Codes** stoppen den Druck (Klipper errort); exotic
  Marlin-Toolchanges → in Makros verlagern.
- **Geschwindigkeiten/Accel** des Files werden an OUR limits geklemmt
  (Sicherheitsfeature, kein Bug).
- **`[r2_postproc]`-Rollabschnitt verboten** (Klipper verweigert
  unbekannte Sections → Halt-Loop); nur Settings-Makros (wie
  `_R2_CONFIG`) sind gültige Träger.

### 1.4 STL-/Export-Grenzen (MASTER-TODO I/J1)

- Aktiver Exporter (Box-Soup) **defekt**; Fenster-Export (z∈[0,4] mm)
  nur Teilflächen (vwbus=Heck, MAN=Frontstoßstange, Pumpkin
  unbefriedigend). Statt Layer/Prismen-Extraktion: neue Richtung
  **Punktwolke + Haut spannen** (Surface Reconstruction).
- Offene Teilblöcke (experimentell, keine produktive Anbindung):
  Konturen, Löcher, Loft, Naht-Rekonstruktion, Breite/Schalenmodell,
  Slicer-Reimport.

---

## 2. Aufgaben, die „abgehakt" waren, aber nie gebaut waren

**Die CALIBRATE_BELT-Klasse:** Punkte, die in Audit/Dokumentation als
„existierend/beHefbar" behandelt wurden, tatsächlich aber **nicht im
Repo existierten**.

- **P1-02 `CALIBRATE_BELT`** — *NEU GEBAULT (Release 26.14).* Der
  Audit-Bericht (geprüft am 26.10-ZIP) listete das Makro mit
  `HOMING_VECTOR`-Fehler + unsicheren Festkoordinaten (Y=-200) als
  P1-Fehler. **Im Repo existierte es nie** (keine Spur in Git-History,
  nicht in `macros/`). → In 26.14 korrekt neu gebaut (G28, `_R2_CONFIG`-
  Limits, lineares Scale-Modell, deklarierte `_STATE`-Vars).
  **Beispiel für die Systematik:** der Audit setzte einen eingebildeten
  Bestand gegen den falschen Snapshot.

**Systematische Makro-Prüfung (diese Runde):** alle `[gcode_macro X]`
in Doku/MANUAL gegen die tatsächlichen Definitionen in `macros/` —
**keine weiteren dokumentiert-aber-fehlenden Makros.**
(`_R2_CONFIG` lebt korrekt in `r2_hardware.cfg`; `X` war ein
Falschpositiv.) → **Bisher ein einziger realer Fall (CALIBRATE_BELT).**

**Kategorie-Hinweis:** Die MASTER-TODO-Liste ist ansonsten **ehrlich**
bemarkt — offene Punkte sind als `[ ]`/`[~]` erkennbar, nicht als
erledigt getarnt. Versteckte „abgehakt-aber-nie-gebaut"-Fälle sind
hier durch die systematische Makro-/Inventar-Prüfung **ausgeschlossen**.

---

## 3. Ideen / Agenda (offene Agenda-Punkte)

Quelle: `docs-notes/MASTER-TODO.md` (Abschnitt J, G, I) + Fachdokumente.

### 3.1 Große, ausdrücklich vorgemerkte Vision

- **J6 — KI-3D-Generierung + Sprachsteuerung** (große User-Idee,
  ausdrücklich für SPÄTER, kein Go). Vision: mit dem Drucker sprechen,
  KI baut/wandelt 3D-Modelle (auch aus Fotos), bereitet G-Code.
  Architektur-Ideen: KI-Brücke als weiterer Toolchain-Generator,
  jedes Modell durch unsere Prüfer (stl_audit/Bettcheck), physischer
  Druckstart beim User, Slicing-Engpass auf Pi Zero 2 offen, TTS via
  J4-Audio. **Kein Baubeginn ohne ausdrückliches Go.**
- **J1 — STL-§24-Fertigstellung (RICHTUNG WECHSEL).** Statt
  Layer/Prismen-Extraktion: **3D-Punktwolke + Haut spannen**
  (Surface Reconstruction) für organische Formen. Offen: volle z-Spanne,
  Loft, Loch-Inferenz, Kiri-Marker, Breite/Schalenmodell, Slicer-Reimport.

### 3.2 Zurückgestellte / backlog Ideen (User-Entscheidung)

- **J8 — TEXTUREN-RUNDE II (offene Roadmap nach User-Wunschliste):**
  Tiefen-Relief **erledigt** (0.05–4 mm). Offene Familien:
  *technisch/modern:* Perforationsblech, Carbon/Twill, Pin/Kugel-Matrix,
  Hexagon/Oktagon-Zellen, Maschendraht, Netzgewebe (**meist erledigt**
  R265.3); *organisch:* Holz QUER + Holzarten, Baumrinden-Varianten,
  Leder, Orangenhaut, Trockenrisse (**erledigt** R266.2); *Deko/Haptik:*
  Sterne, Herzen, Ringe, Golf, Basketball, Raufasertapete,
  Dachziegel, Häkel (**erledigt** R266.3 — 55 Muster/Bijektiv).
  **Offen:** weitere Wunsch-Familien nach User-Kuriosität.
- **Frames (`docs/frame_design.md`):** Dreieck-/Stern-Rahmenformen
  sowie Line/Wave/Diamond/Honigwabe als Rahmen-Oberflächenstrukturen —
  „later backlog (user decision, NOT dropped)".
- **Stringart (`docs/STRINGART_DESIGN.md`):** zweifarbig (Bänder 1–3
  Farbe A, 4–6 Farbe B) — **zurückgestellt**; Ankerzahl 600 vs. 300
  Default bis Feldmessung; keine Purge-Turm-Variante.
- **Browser-Sound-Spiegel** (WebAudio, identische Tune-Tabelle,
  PORTABILITY §2.4 / WEBUI) — Konzept; mit R286-Audio (Host-Audio
  läuft) **optional**, nicht priorit.

### 3.3 Ausbau-Ideen (LOW/LANGFRISTIG, ChatGPT-Priorität 4)

- Automatisches Hardwareprofil / Self-Diagnosis bei Klipper-Start.
- Kompatibilitätsbericht im LCD + Webinterface.
- Automatisierte Regressionstests für alle Generatoren.
- Abhängigkeitsdatei + Versionsmatrix.
- Web-API-/Berechtigungsprüfungen (J3-WebUI bereits großenteils).

---

## 4. Versteckte Aufgaben in Dokumentationen („lauernde" Punkte)

Die MASTER-TODO ist der **einzige offizielle Ort** („Wenn etwas nicht
hier steht, existiert es für die Arbeit nicht"). Versteckte Aufgaben
stehen aber in Fachdokumenten als **„Weiter offen"**-Notizen:

- **J5-Sammlung (umgesetzt):** Ideen, die nur in Fachdokumenten standen
  (Frame-Oberflächenstrukturen, zweifarbig Stringart, Browser-Sound) —
  alle erfasst und eingeordnet.
- **I1-Teilblöcke (STL):** jedes Experiment trägt eine
  „Weiter offen:"-Notiz (Konturen, Naht-Rekonstruktion, Breite/
  Schalenmodell, Slicer-Reimport, Phasenfortsetzung, Deckel/Festkörper,
  Selbstschnittprüfung) — **managbar, aber zahlreich**.
- **D7d — Modifier-Tiefdokumentation:** Mathematik pro Modifikator
  (Scale/Twist/Mirror/Range/Toolchain) als Umfang von D4 — **nicht
  mit dem PDF-Rebuild erledigt**; offizieller Abschluss braucht
  **User-Durchsicht der PDFs**.
- **E1/E4 — Feld-Check bleibt:** Probe-Guard + `_LED_QUIET` am Drucker
  bestätigen; `printer.cfg`-Vorschläge (`position_min=-2`, `G4 P750`)
  nur nach separatem Go.
- **G/H/C „offline geprüft"-Vermerke:** alle Offline-Gates am Drucker
  nachholen (Field-Checkliste, MASTER-TODO-Sektion G).
- **Textur-Streifen drucken + sichtbar prüfen** (BARK/PLANKS/BRICKS/
  HONEYCOMB/27 Vorlagen) — Field-Check.
- **Cake-Erster-Schnitt** (reorient + Range-Test) — Field-Check.
- **L2/L4/L5/L13/L8** Field-Checks (Label-Druck sichtbar, Watcher-RAM
  am Drucker mit korrigiertem `--watch`-Befehl).

---

## 5. Klipper Config-Changes — Anpassungsbedarf

**Quelle:** https://www.klipper3d.org/Config_Changes.html (Stand
Einblick 2026). **Überprüfung unseres Trees:** wir nutzen **keine**
abgeschafften Features (keine `max_accel_to_decel`, `shared_heater`,
`step_distance`, `default_parameter_`, raw `[r2_postproc]`-Section,
`M206`, `.e`-Accessor). Derische Anpassung konzentriert sich auf
**Befehlsfluten, MCU-Shutdown-Timing und Status-Accessoren**.

### 5.1 Befehlsfluten (command floods) — die zentrale Anpassung

- **20240912 — `SET_PIN`, `SET_SERVO`, `SET_FAN_SPEED`, `M106`, `M107`
  werden jetzt COLLATED.** Rapid successive updates zum **gleichen
  Ziel** werden zusammengeführt: nur der **letzte** Request wird
  angewendet; Zwischenzustände gehen verloren.
  **Relevanz für uns:** `03_leds.cfg` (13× SET_PIN/M106/SET_LED_STATE)
  und Sound/LED-Makros erzeugen schnelle Pin/Lüfter-Updates.
  **Anpassungsbedarf:**
  - Unsere Zustandsmaschine darf **nicht von Zwischenzuständen
    abhängig** sein, die Klipper jetzt wegkollabieren könnte.
  - `SET_LED_STATE`/`SET_PIN`-Ketten, die schrittweise denselben Pin
    ändern, sind kollabiering-sicher (letzter Wert gewinnt) — das
    reduziert MCU-Last (gut). Aber jede **beabsichtigte** Zwischenänderung
    braucht ein explizites `G4` (Klipper-Empfehlung).
  - **Maßnahme:** Audit der LED/Sound-Hot-Paths; dort, wo ein
    gezielter Zwischenzustand nötig ist, `G4` einfügen.
- **20251010 — Command-Processing nur noch 1 s ahead** (war 2 s).
  **Der Host hat jetzt nur noch ein Sekundenfenster.** Jedes Host-
  Staupen (Reactor-Stall, großes Push, Generator-Job) rückt näher an
  das „Timer too close"-Risiko.
  **Relevanz:** Unsere 16 Shutdown-Fixes (SHUTDOWN_REGISTER:
  Bewegungs-Sperren, `_LED_QUIET`, Job-Queue, Dedupe, RAM-Gates) sind
  **genau gegen diese Last** — sie müssen das jetzt **engere**
  Fenster halten.
  **Anpassungsbedarf:** Buffer_time-Margen überprüfen; keine
  Host-lastigen Operationen (Generatoren/Audits) in kritischen
  Druckphasen; Live-Poll-Reduktion (R204) beibehalten.

### 5.2 MCU-Shutdown-Relevanz

- **20210227 — TMC-Stepper werden aktiviert 1×/s abgefragt;
  Kontaktverlust → Shutdown.** Relevant für Stepper-Gesundheit;
  unser `R2-DOCTOR`/Diagnose-Pakete sollten TMC-Fehler im Blick haben.
- **20250417 — Software-SPI jetzt rate-limited** (war nur
  Verarbeitungsgeschwindigkeit). Wenn wir Software-SPI-Displays
  nutzen, ist die tatsächliche Geschwindigkeit jetzt konfiguriert
  (`spi_speed`) — Display-Updates während Bewegung können langsamer
  sein.
- **20250428 — `pwm_cycle_time`-Max 3 s** (war 5 s). Unser Beeper
  (`CYCLE_TIME={1.0/S}`) bleibt im Bereich (Tone ≥ ~0.3 Hz → ≤3 s);
  keine Konflikt. LED-PWM-Konfigs prüfen, falls custom cycle_time >3 s.
- **Gemeinsame Ursache (SHUTDOWN_REGISTER):** MCU-Überlastung ist **nicht**
  das Problem (mcu_awake ≪1 %). Es sind **Host-Schübe im falschen
  Moment**. Die Klipper-Änderungen (1 s-ahead, Collapsing) **verschärfen
  das Timing** → unsere Guards sind das Abwehrsystem. **Feldabtnahme
  mit Logs (buffer_time, Reactor-Stalls) bleibt der Beweis.**

### 5.3 Status-Accessoren & Empfehlungen (proaktiv)

- **20251106 — Koordinaten-Statusfelder** (`toolhead.position`,
  `gcode_move.position`, `gcode_position`, `motion_report.live_position`)
  können jetzt **mehr Komponenten** haben; `.e`-Accessor **deprecated**.
  → In future Klipper-Versionen: Zugriffe als
  `printer.toolhead.position[printer.gcode_move.axis_map.E]` umstellen.
  **Aktuell:** kein `.e`-Accessor im Tree (clean).
- **20260109 — Probe-Status:** `last_z_result` → `last_probe_position`;
  `PROBE`-Console-Z mit jetzt relativen Z-Höhen + angewandten Offsets.
  → Makros, die Probe-Werte lesen, auf neue Felder prüfen.
- **20250916 — EI/2HUMP/3HUMP-Shaper-Definitionen aktualisiert** →
  **Empfohlen: Input-Shaper neu kalibrieren.** `CALIBRATE_SHAPER`/
  `SHAPER_MANUAL`-Fluss sollte dies im Handbuch erwähnen.
- **20261018 — PID_CALIBRATE-Berechnung korrigiert** (fehlerhafte
  2×-Empfehlungen) → bei persistenten Schwingungen `PID_CALIBRATE`
  neu laufen; unser `TUNE_PID`-Fluss erwähnen.
- **20250308 — `AXIS_TWIST_COMPENSATION_CALIBRATE AUTO` entfernt** →
  nicht relevant (wir nutzen eigene Twist-Modifikation, kein
  axis_twist).

### 5.4 Zusammenfassung Klipper-Anpassung

| Klipper-Änderung | Status bei uns | Handlung |
|---|---|---|
| SET_PIN/M106 Collapsing (20240912) | Hot-Path existiert | LED/Sound-Hot-Paths auditieren; beabsichtigte Zwischenzustände mit `G4` schützen |
| 1 s-ahead (20251010) | 16 Guards vorhanden | Buffer_time-Margen prüfen; keine Hostlast in Druckphasen |
| TMC 1×/s-Abfrage (20210227) | Diagnose-Pakete vorhanden | TMC-Fehler in DOCTOR-Paketen berücksichtigen |
| Software-SPI rate-limited (20250417) | hardwareabhängig | Display-Updates bei Movement im Feld prüfen |
| pwm_cycle_time ≤3 s (20250428) | OK (Beeper ≤3 s) | LED-PWM-Konfigs prüfen |
| Koordinaten-Accessoren (20251106) | aktuell clean | bei Klipper-Upgrade proaktiv prüfen |
| Probe-Status (20260109) | aktuell clean | bei Klipper-Upgrade proaktiv prüfen |
| Shaper-Recal (20250916) | Flow existiert | Handbuch: neu kalibrieren empfehlen |
| PID_CALIBRATE-Fix (20261018) | Flow existiert | Handbuch: bei Schwingungen neu laufen |
| **Abgeschaffte Features** | **keine im Tree** | **keine Aktion** |

**Fazit:** Der main Handlungsbedarf ist **begrenzt** — wir sind
clipper-konform. Die **wichtigen Optimierungen** sind (a) die
LED/Sound-Befehlsfluten auf Collapsing-Kompatibilität prüfen und
(b) das **1-Sekunden-Fenster** im Blick behalten (Guards + Feldlogs).
Beides ist **Field-Check + proaktives Audit**, kein Code-Rework.
