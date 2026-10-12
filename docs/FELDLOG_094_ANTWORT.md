# Feldlog .94 — Antwort und was daraus wurde (Version .94 / R133)

**Stand:** alle echten Bugs aus dem Feldlog sind behoben, die Figuren und der
Bausatz sind komplett neu gebaut, die Testbatterie ist grün.
Commit `e87ee84`, Bundle `klipper_e3_r2d2_V094.zip` (74 Dateien).

---

## 1. Die gemeldeten Bugs — Ursache und Fix

### 1.1 CAPS-Schrift: Endlosschleife über dem „O" (Klumpen-Extrusion)
**Ursache:** In `FONT_CAPS` waren 5 Glyphen korrupt — `O`, `0`, `Ö`, `o`, `ö`
(each ~11.400 Zeichen Pfad; derselbe Subpath Dutzende Male wiederholt, statt
~200 Zeichen). Der Drucker fuhr die Punkte immer wieder ab und extrudierte
dabei real Material — deshalb der Kreis über dem „O".
**Fix:** Neue, saubere Glyphen (Oval mit Innenkontur, Ö mit Diakritika wie das
saubere Ü). Alle 9 Schrifttabellen geprüft: größte Glyphe jetzt 584 Zeichen.
**Test:** `r142_field_coverage` prüft jede Glyphe jeder Schrift (<700) — das
kann nie wieder unbemerkt passieren.

### 1.2 „Flow cap started / Travel fix started" — aber nichts passierte
**Ursache:** Der Watcher hatte für `retract_fix` und `vol_fix` Laufzeit-Blöcke,
für **flowcap und travelacc aber keine** — die Nonces wurden nur einmal beim
Start gelesen. `FIX_DONE` blieb leer, egal wie oft das Makro meldete.
**Fix:** Beide Runtime-Blöcke in `watch()` ergänzt (gleiche Struktur wie
retract/vol). Damit funktioniert auch die automatische Neu-Auswahl nach dem Fix.

### 1.3 Start-Auswahl reagierte nicht mehr (fix_reselect löschte sich selbst)
**Ursache:** Folgefehler von 1.2: weil kein Fix je in `FIX_DONE` einlief,
hielt der Watcher die Anforderung sofort für „veraltet" und löschte sie
(Feldlog 05:57:16: `SAVE_VARIABLE VARIABLE=fix_reselect VALUE='""'`).
**Fix:** Geduldsfenster — erst nach **12 Durchläufen (~1 Minute)** ohne
abgeschlossenen Fix wird gelöscht; sonst wartet der Watcher.

### 1.4 Label im FIXED-Modus: „Label error"
**Ursache:** Bei mehreren Labels mit Einzeleinstellungen (LCD-Jobs) setzte der
Code das Flag `grown` nur für wachsende Labels — FIXED-Jobs hatten das Flag
gar nicht, die Info-Zeile stürzte mit `KeyError: 'grown'` ab. Jede Erstellung
im FIXED-Modus über das Menü war betroffen.
**Fix:** FIXED-Jobs bekommen `grown = False`; FIXED- und GROW-Labels können
jetzt gemischt auf eine Platte.

### 1.5 MCU-Shutdown „Timer too close" (70 s nach Druckstart)
**Ursache:** Host-Überlastung während des Drucks. Der Watcher lief mit vollem
Auftrag weiter: kompletter Verzeichnis-Scan alle 5 s, Generator-Jobs (Figuren,
Kit, Litho, …) konnten mitten im Druck losrennen — dazu hatte der alte
Figuren-Code winzige Segmente, die allein 3.600+ Bewegungen/s erzeugen
können (8-Bit-MCU-Seriell-Budget: ~450/s).
**Fix (dreifach):**
- `_printer_busy()`-Abfrage pro Durchlauf: **während des Drucks kein Scan,
  keine Generator-Jobs** (die Nonces „frieren" ein und laufen im ersten
  ruhenden Durchlauf — nichts geht verloren), Abfrage-Takt 12 s statt 5 s.
- `_emit_loop` verschmilzt Stützpunkte unter 0,1 mm — die schlimmste
  generierte Datei liegt jetzt bei 393 Bewegungen/s (Budget 400).
- Der Audit prüft jede generierte Datei auf dieses Budget („move rate").

### 1.6 Kalibrier-Türme mit LAYER=0/WIDTH=0 → Jinja-Absturz statt Fehler
**Ursache:** FLOW_TEST, IRONING_CAL, RETRACT_TOWER, TEMP_TOWER_GEN, PA-CAL
lasen LAYER/WIDTH/LINES ohne Prüfung — `LAYER=abc` ergab 0 und Teilung durch
null bzw. leere Geometrie. Im PA_SMOOTH teilte zusätzlich schon die
**Fehlermeldung** durch `round(0.001) = 0`.
**Fix:** Guard-Zeilen unter jedem Paramater-Leser (Wert ≤ Minimum → sinnvoller
Standard + RESPOND-Hinweis). Der PA_SMOOTH-Meldungsfehler ist korrekt
gekammert. Die Journeys-Storms werfen weiterhin `''`/`0`/`-1`/`999`/`abc`
auf alle Parameter — kein Absturz mehr.

---

## 2. GEN_FIGURES — komplett neu: originale Proportionen

Die Kritik war berechtigt: Beine waren 15,8 mm **tief** statt 7,84 (wirken
doppelt so breit), der Torso ein konstanter Kasten statt trapezförmig, der
Kopf zu hoch, der Arm ein 2×1-Balken mit Löchern.

**Jetzt: Messwerte wie das Original (100 %):**

| Teil | Maß |
|---|---|
| Füße | 2 × 7,2 breit × 7,8 tief, Gesamt 15,4, Lücke 1,0, Sohle 3,2 |
| Beine gesamt | 14,87 hoch, Schäfte 7,2 × 6,6 |
| Hüftgelenk | Halbzylinder Ø 4,4 quer zur Tiefe — schwenkt in der Torso-Kammer |
| Torso | Trapez 15,43 (Taille) → 10,59 (Schultern), 7,84 tief, 12,82 hoch |
| Armgelenk | Bohrung Ø 4,0, Zapfen Ø 3,94 — Arme schwenken vor/zurück |
| Hand | Hohler Griff Ø 2,4 (steckt auf Ø-2,4-Stiften/Barren) |
| Kopf | Zylinder Ø 10,2 × 8,5, unten Halsaufnahme Ø 5,2, oben hohle Noppe Ø 4,89 |
| Zusammengebaut | ~35 mm (wie das Original ohne Hut) |

**Gelenke wie beim Original:** Beine schwenken (Hüftpivot in der
Torso-Kammer), Arme klicken in die Schultertaschen und schwenken, Kopf
sitzt auf dem Halsstummel und **dreht** sich, Noppe nimmt Hüte.

**Druckstrategie:** Beine/Torso/Kopf aufrecht (Kammer- und Sockeldeckel als
Brückenstäbe mit Anker an den Ringwänden), **Arm in Rückenlage** (gebogene
Silhouette, Zapfen steht senkrecht auf, beide Rohre druckrein). Überall
**2 Wände, nie Vasenmodus**, Brim pro Teil, Support ist nicht nötig — alle
Überhänge sind 45°-fähig konstruiert.

## 3. GEN_BRICKKIT — „wie würde ich das Modell bauen"

- **AUTO wählt jetzt das feine Platten-Raster für kleine Modelle** (vorher:
  3–4 Klötzer; eine kleine Figur liefert jetzt z. B. 14 Teile auf 12 Bändern).
- **Slope-Steine an jeder Stufenkante** (Zelle unten besetzt, nebenan frei,
  oben frei): der Übergang fällt ab wie bei einem Speed-Modell — Nase,
  Spoiler, Kotflügel. Slopes drucken mit abgeschrägtem Körper, **ohne Studs
  auf der Schräge**.
- Nach wie vor echte Kataloggrößen (2×8 … 1×1), Platten-/Stein-Bänder,
  Schalen-Erkennung (Vasen → Ringwände).

## 4. Testbatterie (.94)

| Suite | Ergebnis |
|---|---|
| Megatest (inkl. rule-ll-Brückenprüfung) | 157 Läufe / 163 Dateien / **0 FAIL** |
| Makro-Render-Suite | **1601/1601** |
| Systemtest | **221/0** |
| R140 Stress | **46.589/0** |
| R141 Journeys (inkl. 2.460 Parameter-Fuzz-Renders) | **1.801/0** |
| R142 Feld-Abdeckung (NEU: pinnt jeden Feld-Bug) | **31/0** |
| R142 Rechtschreib-Lint (NEU: 1.489 Meldungstexte) | **0 Verdächtige** |
| Audit-Sweep (u. a. Bewegungsraten-Budget) | **77/0** |
| Config-Validator | **sauber** |

Darin eingearbeitet: **jede Bug-Klasse aus dem Feldlog** hat jetzt einen
eigenen Check (r142_field_coverage) — auch die, die in keiner Suite auftauchte.

## 5. Displays & Web-UI (Kurzfassung der Analyse)

- **LCD-Menüs:** voll portabel auf allen Klipper-`lcd_types` (nur der
  `[display]`-Pinblock ist Drucker-spezifisch, ~15 min Anpassung).
  Touch-Panels/Vendor-Displays bleiben außen vor → dort führt kein Weg an
  einer Web-UI vorbei.
- **Sound:** aktuell der M300-Weg; portabler wird es über den Guard
  `'pwm_cycle_time beeper' in printer.configfile.settings` (Option A,
  ~30 min — noch nicht umgesetzt, in docs/ dokumentiert).
- **Web-UI (Empfehlung):** Machbarkeit ist gegeben (~2 Tage): statisches
  SPA (Vanilla JS) + cfg→JSON-Menü-Compiler + Moonraker-WebSocket
  (`printer.gcode.script`, Objekt-Abos auf `_STATE`/`save_variables`),
  Auslieferung über den bestehenden nginx als `/r2/`-Location — kein
  zusätzlicher Dienst, Moonraker selbst serviert seit 2020 keine statischen
  Dateien mehr. Details: `docs/WEBUI_MOONRAKER.md`.

## 6. Einspielen von .94

Bundle `klipper_e3_r2d2_V094.zip` entpacken, Inhalt über das bestehende
Verzeichnis legen (wie gewohnt). Danach einmal Firmware-Neustart; der Watcher
holt sich den neuen Code beim nächsten Start selbst.
