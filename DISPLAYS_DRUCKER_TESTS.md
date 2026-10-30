# R2-D2 rundum: Displays, Drucker, Nozzles — und die Test-Stufen

Stand: R2-2026-10-29.136h — **alles aus Abschnitt E ist GEBAUT** (R191–R197). Die
ausführliche, grafische Fassung dieser Übersicht ist jetzt **DISPLAYS_WEB_UI.pdf**
(built by tools/make_displays_pdf.py); diese MD bleibt die Arbeits-Kurzfassung.

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

**Update .135: der Mittel-Weg ist GEBAUT (R196)** - menu_json_export.py +
web/r2_menu.py + web/index.html. Die Empfehlung selbst gilt unverändert: kein eigener
Web-UI-Stack neben Mainsail, sondern die Menuestruktur als JSON exponieren und mit
einer duennen LCD-artigen Seite navigieren. Installation und Grenzen:
DISPLAYS_WEB_UI.pdf Kap. 2. - Die Liste von damals:

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

*(.135-Update: die Stufen laufen jetzt gebündelt über **tools/r198_tier_report.py**
— ein Befehl, eine Tabelle pro Stufe, Exit-Code ist das Verdikt. .135-Gesamtbild:
macro_render 1.910/1.910 · r140 46.757/0 · r141 2.372/0 · r187 1.356/0 · r190 32/0 ·
r197_gen_sweep 403/0 · r81 23/23 (re-frozen auf ehrlichen Fixtures, .134≡.135
byte-identisch verifiziert) · systemtest 214/0 · megatest 190/194/0 · audit_sweep
82/0 · validator clean · r197b Menü-Export: 2.272 Sektionen, 0 Duplikate, 0 Waisen.)*

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

## E  Die .135-Liste — ERLEDIGT (R191–R197)

1. **BRIM-fstat-Fix** — GEBAUT (R192): `_fmove192` verschiebt die fstat-Buchung mit,
   wenn `_brim153` re-taggt (WALL-OUTER → BRIM und die WALL-INNER → WALL-OUTER-
   Promotion). r190-GAP-Check geflippt: TYPES= trägt BRIM, LCD-Zeilen aktivieren.
2. **Bambu `;FEATURE:`** — GEBAUT (R191): TYPE_RE liest beide Schreibweisen; die
   Leiter versteht den Inhalt sofort; unbekannte Vokabeln bleiben ehrlich CUSTOM.
3. **Ladder-Stemming** — GEBAUT (R191): Whitelist `ironing` → `iron` (kein blinder
   -ing-Schnitt: „missing" wird nie zu „miss").
4. **Stufe 5** — GEBAUT (R193): Quer-Schicht-Luftscan `_airscan193` (dichtes Hatch
   über Leertrum → BRIDGE/INTERNAL-BRIDGE; dicht über SPARSE bleibt Surface/Solid) +
   Sequenz-Audit S1–S4 als SEQWARN (Flag-only — getaggte Daten herrschen). Ironing-
   Regel nach Nutzerkorrektur: Ironing darf auf JEDES Top folgen, nicht nur das letzte.
5. **Peek-Härtung** — GEBAUT (R195): `_DIALOG_PEEK` an allen 4 Dialog-Öffnern — der
   Dialog selbst erzwingt den frischen Peek-Push (Nonce über den bestehenden Watcher).
6. **Purge-Tower-Tagging** — GEBAUT (R194, Nutzerwunsch): Labels/Litho/Colorpic
   drucken den Turm als EIN PRIME-TOWER-Feature (Turm-Brim bleibt BRIM), TYPES=
   ehrlich mit/ohne PRIME-TOWER.
7. **Web-UI** — GEBAUT (R196): tools/menu_json_export.py + web/r2_menu.py (Moonraker:
   /server/r2_menu/tree|status|refresh) + web/index.html (LCD-Navigation, eingebettetes
   JSON als Fallback). Details + Installation: DISPLAYS_WEB_UI.pdf Kap. 2.

**R209 (.136h):** Feldlog .136g: Seite lädt, aber „main_" im Menübaum und
jeder Klick tot. DREI gestapelte Seiten-Bugs, alle von dem neuen
Integrationstest T8 gefunden (echte Seite × echte Endpoint-Antwort):
(1) UR-BUG seit R201: der JSON-Embed ersetzte nur den Marker, ließ aber
das ` null;` der Platzhalterzeile stehen → `EMBEDDED_MENU_JSON = {...}
null;` = JavaScript-SYNTAXFEHLER → das Seiten-Skript lief in KEINEM
Browser je (kein Handler, kein Render, kein Fallback); (2) Moonrakers
`{"result":…}`-Envelope wurde nie ausgepackt → DOC.tree undefined;
(3) pollLive() startete synchron vor loadDoc() → LIVE noch false →
Live-Werte fragten NIE ab. Fixes: Embed härtet beide Zweige (frisst das
verwaiste null), Seite packt den Envelope aus + Form-Check, pollLive
startet nach erfolgreichem loadDoc. T8 parst und führt fortan die KOMPLETTE
ausgelieferte Seite in node aus (DOM-/fetch-Stubs, Envelope inklusive)
— gegen die echte Komponenten-Antwort und den Embedded-Fallback.
Feld-Bug-Klasse #16: Schnittstellen-Vertragsbruch — jede Seite grün
gegen ihre eigenen Mocks, nur das Paar wurde nie zusammen getestet.

**R208 (.136g):** Feldlog .136f: „schon beim Öffnen der Seite" 403, auch
Inkognito — nginx (www-data) konnte die Seite unter /home/pi NICHT LESEN
(Serve-Path-Rechte kippen bei jedem Update; die API-Proxy-Pfade liefen
weiter — deshalb waren alle Proxy-Tests grün, während die Seite nicht
einmal lud). Diagnose per `sudo -u www-data head … index.html`. Fix: die
Seite liegt jetzt in /var/www/r2lcd (welt-lesbar, außerhalb jedes
Home-Verzeichnisses), wird bei jeder Paket-Aktualisierung synchronisiert
(--update-only), und der Installer-Selbsttest prüft ab sofort auch die
Seite selbst per GET (ein nicht lesbarer Serve-Pfad kann nie wieder
still durchgehen). E2E mit echtem nginx + home=750 bewiesen.
Feld-Bug-Klasse #15: Serve-Path-Dateirechte (statisch, außerhalb jeder
Code-Test-Pyramide).

**R207 (.136f):** Feldlog .136e: „jetzt kommt wieder 403" trotz R206-Fix.
Zwei Erkenntnisse: (1) eine GESCHRIEBENE Site-Datei ist noch keine AKTIVE
Konfiguration — schlägt der nginx-Reload still fehl, serviert nginx das
ALTE Layout weiter (Seite läuft, jeder Befehl 403); (2) der Origin==Host-
Vergleich war case-sensitiv — der Browser kleinschreibt den Origin, den
Host sendet er wie getippt (gemischtes Lesezeichen = 403). Fixes:
Case-insensitive Map (~*), Host wieder ohne Port an Moonraker (Auth liest
nicht Host — Quellcode verifiziert), und der Installer SELBST-TESTET die
aktive Guard nach jedem Reload (fremder Origin muss am Proxy 403 bleiben,
Retry + klare Ansage bei Fehlschlag). Zusätzlich: der Watcher-Matcher
trifft jetzt nur noch AUSGEFÜHRTE Prozesse (python + r2_postproc*.py als
Argument) — vorher matchte jede Erwähnung (grep/nano/pgrep) und der
Runtime-Sweep hätte sie getötet; der Sweep nennt jetzt den Pfad des
Rivalen, update.sh zählt beim Finale noch einmal (klippy oben) und das
r142-Lint liest jetzt ast-Joins (Split-Strings können nicht mehr
entkommen). E2E mit echtem nginx 1.26: volle Matrix + Fallgruben-Test +
Selbsttest-Retry-Pfad. Feld-Bug-Klasse #14: geschriebene Konfiguration ≠
aktive Konfiguration.

**R206 (.136e):** Feldlog .136d: „web ui sagt 403 forbidden" — Moonraker
lehnt jede Anfrage mit unbekanntem Origin-Header ab; Browser senden bei
JEDEM Befehl-POST einen Origin (GETs keinen) → Live-Werte kamen an, aber
jeder Button starb (schon das „kann da nix weiter machen" von .136b).
Zusätzlich: update.sh syncte die Moonraker-Extension nie — der R204-Fix
erreichte den Pi gar nicht. Fixes: Origin-Strip am nginx-Proxy + eigener
CSRF-Wächter in der Site-Datei (fremde Origins → 403 von nginx, bevor sie
den Drucker erreichen), install_web.sh --update-only (update.sh hält die
Web-LCD ab jetzt bei jedem Update aktuell, NO-OP wenn nicht installiert),
sudo-fähiges Schreiben der Site (644). End-to-End mit echtem nginx 1.26 +
Fake-Moonraker bewiesen. Feld-Bug-Klasse #13: Auth-Schicht zwischen Proxy
und API (+: Code im Zip ist noch lange nicht Code auf dem Pi).

**R205 (.136d):** Feldlog .136c: der Watcher-Check unter sudo zeigte zwei
zusätzliche „Prozesse“ — das war das sudo+pgrep-Pärchen selbst (pgrep -f
matcht die ganze Kommandozeile, und das sudo-Pärchen trägt das Muster mit).
Es lief genau EIN Watcher. Fixes: [r]-Bracket-Form für jedes ausgelieferte
pgrep/pkill auf den Watcher (Daemon-Hint + update.sh inkl. Root-pkill),
update.sh sagt den Census jetzt laut („exactly 1 r2-postproc watcher
(PID …)“), r142-Lint verbietet die unklammerte Form repo-weit.
Feld-Bug-Klasse #12: Messartefakte.

**R204 (.136c):** Feldlog-Analyse des Klippy-Logs: jeder Live-Poll des Web-LCD
blockierte Klippy 0,7 s (QueryStatusHelper) → „Neopixel update did not succeed".
Ursache: der Live-Endpoint fragte JEDES Makro-Objekt ab (~300). Fix: der Exporter
extrahiert `live_objects` (die exakt referenzierten 12 Objekte), der Endpoint fragt nur
diese ab (2,5 s Cache). Regressionstest mit 300 Junk-Makros in r197 (424 Checks).

**R203 (.136b):** Web-LCD-Installation ist jetzt EIN Befehl
(`web/install_web.sh`) — kopiert die Extension, setzt die moonraker.conf-Sektion
(mit Backup) und legt einen eigenen nginx-Site auf freiem Port an (Mainsail-
Config bleibt unberührt, `--uninstall` räumt alles weg; r197 T7 testet das
echte Skript mit Shim-Binaries). Der manuelle 3-Schritte-Weg ist damit Geschichte.

**R202 (.136a):** Feldlog des sauberen Neustarts: .136 gesund, aber beim Boot
spawnt noch immer ein Zweit-Watcher (gleiche-Sekunde-Doppel-Pushes, dann single —
der .136-Sweep tötet ihn). Diagnose-Ausbau: breiterer /proc-Scan, jede Meldung nennt
das besitzende systemd-Unit (cgroup), Respawn-Duell-Erkennung mit disable-Befehl,
HOST_CHECK flaggt die flach-.134-Stray-Kopie, und bei klippy-down sagt der Watcher
jetzt was zu tun ist (FIRMWARE_RESTART → sonst Power-Cycle).

**R200/R201 (.136):** Feldlog-Analyse „jeder Push doppelt" — Watcher-Single-Instance
hart gemacht (/proc-Startup-Scan + Kernel-flock `watcher.lock`, HOST_CHECK zeigt
Duplikat-PIDs), und das Web-LCD wertet die Menü-Templates jetzt **live** aus
(`/server/r2_menu/live`, eigener Jinja-Evaluator, 209 Namen + 120 Enables ==
LCD-Wahrheit; r197 T6 + T-live, jetzt 413 Checks).

**R199 (Feldmeldung dieser Runde):** „die .134 wird nach dem Update nur als .133
angezeigt" — das .134-Zip war flach gebaut (kein `klipper-e3-r2d2/`-Ordner),
`update.sh` entpackte es neben die printer.cfg, das Paket blieb .133. update.sh
lehnt flache Zips jetzt VOR dem Entpacken ab, warnt mit Aufräum-Liste vor den
Leichen, das .134-Zip wurde korrekt neu gebaut, und **r199_zip_check** prüft
das Release-Artefakt selbst (Layout + Versionen) — plus Ablehn-Szenario in r110.

**Dazu aus dem Sweep gefallen (R197):** TYPES=-Ehrlichkeit unter Klemmung (Labels
base_layers<3), Ties-LOOP ohne Surfaces, Litho-Flat/Colorpic ohne WALL-INNER — alle
gefixt; **4 Menü-Zombies** `[menu __main __live __feat __ow]` entfernt (Kopierfehler:
der Live-Punkt „Outer Wall" hieß im LCD „Custom Code"); r2_menu-Refresh-Deadlock
(Lock im Lock) behoben. Neue Testwerkzeuge: **r197_gen_sweep.py** (403 Checks:
alle Generatoren × Parameter + Tool-Oberfläche) und **r198_tier_report.py**
(Stufen-Runner normal/power/developer/hardcore/stress/function).
