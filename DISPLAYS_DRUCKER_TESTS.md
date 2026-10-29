# R2-D2 rundum: Displays, Drucker, Nozzles — und die Test-Stufen

Stand: R2-2026-10-28.134 (Produktivcode unverändert seit dem Release-Commit 6af95c;
dieser Bericht gehört zur Feature-Tagging-Runde — siehe **FEATURE_TAGGING.pdf** und
**tools/r190_tag_ladder.py**).

---

## A  Andere Displays — und die Web-UI-Frage

### A.1  Was heute existiert

| Display | Technik | R2-Menüs | Rolle |
|---|---|---|---|
| **12864-LCD** (ST7920/UC1701, wie verbaut) | Klipper `[display]` + `[menu]`-Engine | **vollständig** — alle ~460 Menü-Punkte aus `menus/lcd_menues.cfg` | Primärsteuerung am Gerät |
| **Mainsail / Fluidd** (Browser, Handy, Tablet, PC) | Moonraker | nein (eigene UI) — aber **jeder** R2-Befehl ist Konsolen-/Makro-tauglich | Zweitdisplay, Datei-Verwaltung, Konsole |
| **KlipperScreen** (Touch) | eigene UI-Schicht | **nein** — rendert keine Klipper-`[menu]`-Sektionen; eigene Items konfigurierbar | nur mit Kuratierung sinnvoll |
| HDMI-Display + OctoPrint o. ä. | fremde Stacks | nein | nicht empfohlen |

Der entscheidende technische Fakt: **die komplette R2-Menüstruktur lebt in der
Klipper-Menü-Engine** (`lcd_menues.cfg`, ~200 Sektionen, Jinja-Render). Nur Displays,
die diese Engine ansprechen (12864-Klasse), zeigen sie 1:1. Mainsail/Fluidd und
KlipperScreen haben eigene UI-Schichten — sie *können* unsere Makros aufrufen (alle
Makros tragen `description:` und erscheinen damit in den Makro-Listen), aber sie
*bauen* unsere Menüs nicht nach.

### A.2  Meine Einschätzung zum Web-UI-Vorschlag

**Klare Empfehlung: keinen eigenen Web-UI-Stack bauen.** Begründung:

1. **Es gibt ihn schon.** Mainsail ist die Web-UI des Moonraker-Ökosystems —
   gewartet, aktualisiert, Multidrucker-fähig, Handy-tauglich. Eine zweite,
   eigene UI dupliziert genau das.
2. **Single Source of Truth.** Die Menü-Logik (Wächter, Sortierungen, 40-Slot-
   Listen, Doppelklick-Arming) ist einmal in `lcd_menues.cfg` kodiert und von
   1.910 Render-Tests abgesichert. Ein Web-Frontend hieße: dieselbe Logik in
   HTML/JS ein zweites Mal — jede Änderung doppelt, jede Drift ein Feldbug
   der Kategorie „Pre-Print sagt A, Live sagt B".
3. **Der Umfang ist das Argument, nicht die Technik.** 200+ Menü-Punkte mit
   Live-Jinja nachzubauen ist kein Wochenendprojekt — und die Nutzenseite ist
   dünn: Am Drucker steht das LCD, von der Couch steuert Mainsail.

**Was stattdessen Sinn macht (.135+-Ideen, sortiert nach Aufwand):**

- **Jetzt gleich, kostenlos:** in Mainsail die Makro-Sidebar kuratieren — die
  wichtigsten R2-Befehle (alle Generatoren, RetFix, SHOW_STATUS, PLOT_CAL …)
  sind bereits konsolenfähig und dokumentiert (Manual Kap. 18 listet sie alle).
- **Klein:** ein Booklet „Mainsail-Schnellzugriff" in der TESTANLEITUNG — welche
  20 Konsolenbefehle das LCD 1:1 ersetzen.
- **Mittel (der elegante Kompromiss):** eine kleine Moonraker-Extension, die die
  **Menüstruktur aus `lcd_menues.cfg` als JSON exponiert** (Name, Pfad, Guard,
  Konsolen-Äquivalent). Jedes Frontend könnte sie rendern, ohne dass wir ein
  Frontend bauen. Das wäre die Brücke „ein Menü, viele Displays".
- **Wenn Touch gewünscht:** KlipperScreen + 10–15 handverlesene Favoriten
  (Start, Pause, Generatoren-Start, Fixes) statt der Vollstruktur.

### A.3  Display-Parität im Alltag

| Aufgabe | LCD | Mainsail |
|---|---|---|
| Datei wählen + starten | SD-Browser (40/Seite, Live) | nativ inkl. Unterordner |
| Generatoren starten | Doppelklick + Start-Sound | Konsole (gleiche Makros) |
| Live-Tuning pro Feature | Live-Menüs | Konsole (Kap. 18) |
| Presets/Profile | Menüs | Konsole |
| Konsolen-Meldungen | kurz (M117) | voll (RESPOND-Log) |

---

## B  Andere Drucker, andere Bauraume, andere Nozzles

### B.1  Was drucker-spezifisch ist — und was nicht

| Baustein | Portabel? | Mechanismus |
|---|---|---|
| **Bettmaße** | ja | `_bed_limits` liest `[gcode_macro _R2_CONFIG]` (variable_bed_min_x/max_x/min_y/max_y), Fallback Ender-3 220×220. Jeder Generator (Range, Scale, Labels-Fit, Texture, Cake, StringArt) rechnet mit diesen Grenzen — der Bett-Wächter nennt die nötige Größe, wenn es nicht passt |
| **Nozzledurchmesser** | ja | `_nozzle_diameter` liest `nozzle_diameter` aus printer.cfg — EINE Wahrheit für alle Generatoren (Linienbreiten, E je mm, Stroke-Auto). `file_nozzle` zusätzlich aus `_FILE_INFO` für die Live-Seite |
| **Kinematik** | ja | Makros sprechen nur G28/G90/M204/M220 — kinematik-agnostic. **CoreXY**: kein Z-Tilt nötig; `SYNC_GANTRY` (11_gantry_sync, Bettschlepper-Dual-Z) einfach ungenutzt lassen — es feuert nur bei LCD-Aufruf/Boot-Toggle |
| **Input Shaper** | ja | ISHAPER-Anleitung; CoreXY misst A/B statt X/Y — von Klipper-Seite identisch |
| **Purge-Line** | ja | Positioniert aus den Bett-Grenzen, nicht hartkodiert |
| **MCU-Watchdog, LEDs, Watcher** | ja | reine Host-/Pi-Seite, druckerunabhängig |
| **Volumenstrom-Wächter** | ja | hotend-, nicht druckerabhängig (MAXRATE aus der Datei gemessen) |
| **Standardwerte** | Erfahrungswerte Ender-3-Klasse | first_layer_speed, Accel-Defaults etc. — alles per Override einstellbar; ein CoreXY druckt danach einfach schneller, sobald du die Werte hochsetzt |

### B.2  Nozzle-Matrix (0.2 / 0.4 / 0.6 / 0.8 / 1.0)

| Nozzle | Generatoren | Live/Tuning | Anmerkungen |
|---|---|---|---|
| **0.2** | Linienbreiten skalieren mit; feine Details (Litho 0.08 Layer) entfalten sich | MAXRATE-Guard wichtiger denn je ( kleine Düse ≈ 8–10 mm³/s Decke) | Labels-Stroke-Auto folgt der Düse |
| **0.4** | wie 0.2 | Standard | der übliche Fall |
| **0.6** (verbaut) | alle Defaults hierauf abgestimmt | — | Referenz |
| **0.8 / 1.0** | Linienbreite/E-mm folgen; Brim/Walls automatisch breiter | Volumetrische Grenze liegt beim Hotend — der MAXRATE-Wächter warnt bei Dateien, die mehr verlangen | Retract-Tower/PA-Cal nutzen die Düse für die Linienbreite — korrekt skaliert |

Der Design-Grundsatz: **kein Generator rechnet eine hartkodierte Düse.** Die
Nozzle-Größe kommt aus printer.cfg (Generatoren) bzw. `_FILE_INFO` (Live) — ein
Düsenwechsel ist ein Einzeiler in printer.cfg plus Neustart, danach rechnen alle
Generatoren, Wächter und Anzeigen um.

### B.3  Bauraum-Matrix

- **Kleiner als 220×220:** Generatoren verweigern ehrlich mit der nötigen Größe
  (Bett-Wächter), Scale rechnet die Prozent-Grenze exakt aus.
- **Größer (z. B. 300×300, 350×350 CoreXY):** `_R2_CONFIG`-Werte setzen —
  Labels-Fit nutzt die Fläche, Range/Cake/Scale zentrieren auf die neue Mitte,
  die Purge-Line wandert an die neue Kante.
- **Hoch-Z (CoreXY 400er):** keine Annahmen über Z in den Makros — nur
  Schichthöhen-Arithmetik.

### B.4  Was beim Portieren wirklich zu tun ist

1. `printer.cfg`: 17 Include-Zeilen + `[gcode_macro _R2_CONFIG]` mit Bett-/Düsenwerten
   (setup.sh migriert/prüft das, r110 simuliert 10 Szenarien).
2. KAMP/moonraker wie gehabt; Object Processing nach Host-Stärke (Kap. 19b).
3. Führende Werte (Accel, Speeds) einmalig per Pre-Print/Overrides hochziehen —
   die Logik (L1/L2, Feature-Overrides, Wächter) ist unverändert.

**Beweis der Portabilität im Test-Netz:** der R106-Kompatibilitäts-Sweep rendet alle
1.690 Menü-Ausdrücke + 315 Makro-Körper auf einem **Minimal-Drucker** (eine Z-Achse,
kein Mesh/Shaper/Probe/TMC/LEDs) — wenn etwas drucker-spezifisch
voraussetzen würde, fiele er um. r140/r141/r187 rechnen Generator-Geometrien über
Bett-/Düsen-Kombinationen.

---

## C  Die Test-Stufen dieser Runde

| Stufe | Wer/Was | Batterie-Glieder | Ergebnis |
|---|---|---|---|
| **Normaler Anwender** | „installieren und drucken" | systemtest (214 Checks: Verkabelung, Module, Validator) · config_validator | 0 FAIL |
| **Power User** | alle Menüs, Presets, Fixes, Generatoren | megatest (190 End-to-End-Läufe, 194 Dateien) · r142 field coverage (129) · r142 spell (1.661) · audit_sweep (82 Dateien) | 0 FAIL |
| **Developer** | Makro-Renders, Konsolen-Äquivalente | macro_render_test (1.910 Checks: jede Menü-Zeile, jeder Makro-Pfad, Mock-Drucker) · r81 goldens (23 byte-identisch) | 0 FAIL |
| **Hardcore-Tiefentest** | das Tagging selbst | **r190_tag_ladder (NEU, 22 Checks)**: Vokabular-Drill (42 Schreibweisen), Trenner-Toleranz, Eliminierungsleiter, Familien-Synthesen (Prusa/Cura/ungetaggt), Brim-/Support-/Boden/Top-Ableitung, CUSTOM-Watch, Positions-Logik über Generator-Output, dokumentierte Lücken | 0 FAIL |
| **Stress + Funktion** | Parameter-Gitter, Dauerschleifen | r140 stress (46.778 Checks über Generator-Parameter) · r141 journeys (2.372 Nutzerreisen) · r187 matrix (1.356 Kombinationen) | 0 FAIL |
| **Generatoren & Tools, sämtliche Variationen** | jede Parameterecke | in r140/r141/r187/megatest enthalten (Vollgitter) + r190-Generator-Audit (Sequenz-Regeln) + r91 (Textur-Sonderfälle: Vase, CRLF, M82, E-only, Kanten) + r110 (10 Installations-Szenarien) | 0 FAIL |
| **Geometrie-Realität** | misst statt glaubt | r167 aircheck (Bett-45°-Kegel, Frame-Passung) · r168 stampcheck (19) · r111 geom (Bögen/Hops/Vasen) | 0 FAIL |

*(Die Werte stammen aus der .134-Freigabe-Batterie; der Produktivcode ist seit dem
Release-Commit unverändert — `git status` belegt es. Neu in dieser Runde: r190 + die
beiden Dokumente.)*

---

## D  Feld-Bugs, die in den Tests nie auftauchten — und warum

Die Frage war: welche gemeldeten Bugs haben die Tests nie abgedeckt, und was deckt sie
jetzt? Die Musteranalyse:

| Feldbug | Warum ihn kein Test sah | Abdeckung heute |
|---|---|---|
| **MCU-Shutdown beim Homing nach Label-Generator** (.104-Ära) | Hardware-Timing: Pi-Zero-RAM + Timer-too-close ist im Sandbox-Batterie-Netz nicht simulierbar | R75 (null Disk-Schreibzyklen während Bewegung), R133b (Queue + Busy-Probe), R162 (RAM-Schwelle 60 MB), .134: gen_busy-Startblockade + 10-s-Wartegrund. Restrisiko ehrlich: nur am Gerät beweisbar |
| **Preset-Speichern tat nichts** (.133) | Der Test prüfte den *Render*, nie die **shlex/literal_eval-Kette** — der Fehler lag im Klipper-Parser, eine Ebene unter allem, was wir testeten | R188-Roundtrip-Test: jede SAVE_VARIABLE-Zeile durchläuft den ECHTEN Parser (shlex posix + literal_eval) |
| **Pause direkt nach der Purge-Linie** | Render-Tests prüfen Makros isoliert — **Zustands-Leck über Druckende hinweg** war nie im Modell (kein „zweiter Druck" existierte in der Batterie) | R188-Hyggiene-Test (PRINT_START räumt) + die Lektion: künftige Zustands-Tests denken in Druck-Paaren |
| **Textur/Scale/Cake bauten nicht** | Die Batterie testete Engine und Makro getrennt — die **Verkettung** (Dateiwahl → Variable → Watcher → Ordner) hatte kein Glied | .134: Fake-Moonraker-End-to-End (Cake bewiesen), R189 tf-Kette + Test, R189b _GEN_GO-Konsistenz |
| **Feature-Mismatch Pre-Print vs. Live** (Außenwand, .133) | Fixtures nutzten immer **bekannte** Schreibweisen; der Peek/Push lief im Test immer im Leerlauf (nie „busy übersprungen den Push") | Kein Repro gefunden (Timing); **aber r190 fand denselben Bug-Typ strukturell**: `_brim153` re-taggt die Marker, nicht die TYPES-Zeile → Live schaltet auf BRIM, die Menü-Zeile aktiviert nicht. Der .135-Fix ist eine Zeile (fstat in _brim153 mitpflegen) — genau die Klasse, die jetzt im Netz ist |
| **Optimized/Browser-Leichen** (eingefrorene Enables) | Klipper-Engine-Verhalten (Enable-Filter friert beim Menü-Eintritt ein) war außerhalb unseres Jinja-Mocks | R188-Tests prüfen jetzt die Engine-Eigenschaft (keine Enables auf Live-Slots, `menu.exit`-Kicks) |
| **Backplate passte nie** (.125) | Der Code-Kommentar *behauptete* 0.3 mm Spiel — Tests glaubten Kommentare | r167 misst aus dem G-Code (Kaliper-Prinzip): Passung, Luftscan, M204-Sparsamkeit |

**Die Lehre, kodiert:** vier Lücken-Klassen — (1) Parser-Ebenen unter dem Render,
(2) Zustands-Lebensdauer über Druckgrenzen, (3) Verkettungs-Glieder zwischen
Bausteinen, (4) Engine-Eigenschaften außerhalb des Mocks. r188–r190 adressieren
alle vier; r190 drillt zusätzlich **unbekannte Vokabeln** (die bisherigen Fixtures
sprachen immer perfekt Klipper-Deutsch).

---

## E  Offene Punkte für .135 (aus dieser Runde mitgebracht)

1. **BRIM-fstat-Fix** — `_brim153` (r2_postproc.py, ~:17789): beim Re-Taggen auch
   `fstat` pflegen (WALL-OUTER → BRIM; bei der Promotion WALL-INNER → WALL-OUTER
   dito), sonst fehlt BRIM in TYPES= für abgeleitete Dateien. Goldens prüfen.
2. **Bambu `;FEATURE:`** — TYPE_RE um `;FEATURE:` erweitern (Ort: r2_postproc.py
   :116). Die Eliminierungsleiter versteht den Inhalt sofort.
3. **Ladder-Stemming** — Token `ironing` → `iron` (r190-GAP-Check deckt es).
4. **Stufe 5 bauen** — Quer-Schicht-Luftscan im Import-Klassifikator (der
   r167-Kegel existiert schon für Generatoren) + Sequenz-Regeln (Ironing nie
   Schicht 1, nach Top kein Solid, Interface über Support-Körper, Prime-Tower
   zuerst bei Toolwechsel). Der Layer-Puffer ist bereits da.
5. **Peek-Härtung** — Pre-Print-Push bei Dialog-Öffnung erzwingen (Feature-
   Mismatch-Forensik, Kap. 12 der FEATURE_TAGGING.pdf).
