# FELDTEST .129 (R170) — Testanleitung

> **⚠ HOTFIX .129a (24.10.) — zuerst lesen:**
> Dein Bericht hat drei echte Bugs gefunden, alle gefixt:
>
> 1. **„Rate print?" — YES ging nicht:** Alle Antwort-Makros nutzten
>    `UPDATE_DELAYED_GCODE NAME=` (Klipper verlangt `ID=`). Der YES-Druck
>    brach nach dem Fehler-Piep ab, die Kopie wurde nie erzeugt — und
>    weitere Presses trafen auf „No rate-print question pending", was wie
>    „mit Nein beantwortet" aussieht. **Jetzt:** YES → Kopie landet in
>    `optimized/`, taucht in Mainsail UND im LCD-Hauptmenü „Optimized" auf.
>    (Generator-Dateien und LEGACY-Druck waren NICHT die Ursache.)
> 2. **Die Frage bleibt jetzt stehen** (kein 90-s-Timeout mehr): Sie
>    verschwindet erst durch YES/NO — oder automatisch mit NO, sobald du
>    eine NEUE Datei auswählst/startest.
> 3. **SD-Karten-Menü:** Die toden Stock-Einträge (Start printing / Resume /
>    Pause / Cancel) sind komplett entfernt. **40 Einträge pro Seite**
>    (statt 20), Ordnerbaum jetzt **vollständig rekursiv** (auch tiefe
>    Unterordner). Das „in der Mitte landen" beim Ordner-Eintritt ist ein
>    Klipper-Cursor-Verhalten (kein G-Code kann den Cursor setzen) — mit 40
>    Einträgen pro Seite passiert es kaum noch.
>
> Außerdem dabei: **System > File check > Re-fix types** heilt deine
> trash.gcode-Kette (falsche CUSTOM-Marker, R172), Mandelbrot-Textur ist
> raus. Erneut flashen: ZIP `…-2026-10-24.129a.zip`, danach muss stehen:
> `post-processor reports build 'R2-2026-10-24.129a (R170a)'` UND
> `Macro system OK ... (build R2-2026-10-24.129a)`.

Diese Runde ist die **Label/Stempel-Feldrunde** (Feldbericht .128): keine
überdruckten Labels mehr, Live-Größenanzeige statt Fit-Button,
Automatisch-Aufteilen bei Überlauf, Stempelgriff in 4 Modi, klare Fehler
auf dem Display — und der **MCU-Shutdown-Wachhund** mit Beweisspur.

Vor dem Testen: .129-ZIP wie immer hochladen, `bash klipper-e3-r2d2/update.sh`
per SSH. Am Ende muss stehen:
`post-processor reports build 'R2-2026-10-22.129 (R170)'` UND
`Macro system OK ... (build R2-2026-10-22.129)`.

---

## A) Die .127/.128-Punkte (weiterhin gültig, unverändert)

Siehe TESTANLEITUNG_127.md (Stempel-Snap, Konturen, Mirror) und
TESTANLEITUNG_128.md (Rate print?, optimized/). Nichts davon hat sich
geändert — Stichproben reichen.

## B) KERN-TEST: Labels drucken nicht mehr übereinander

Der .128-Bug: gewachsene/per-Job-Labels behielten ihre Shelf-Position, aber
das gemeinsame Uniform-Grid überschrieb sie → Labels IM Nachbar
(94-mm-Label lag 21,6 mm im nächsten).

1. **Queue mischen** (Tools > Labels): `KUEHLSCHRANK` mit Size 6 (wächst auf
   ~94 mm), dazu 5–8 normale 60×30-Labels (unterschiedliche Löcher).
2. Queue-Zeile beachten: `Queue: 9/24 …` — dahinter steht jetzt LIVE der
   Bett-Fit (`9 fit` oder `9 -> 2 files`).
3. **Create** drücken.
4. **Beweis** (Mainsail 3D-Vorschau oder Druck):
   - Kein Label überlappt ein anderes, **mind. 10 mm Luft** in alle
     Richtungen (auch bei gemischten Größen).
   - Purge-Turm frei (15 mm Abstand wie gehabt).
5. Abwandlung: **Gap auf 10 mm lassen** (Minimum — der Wert geht nicht
   niedriger, das ist Absicht: deine 1-cm-Regel).

## C) NEU: Überlauf teilt automatisch in mehrere Dateien

1. Queue mit **14 Labels à 90×40 mm** (FIXED, Mode: Fixed) füllen.
2. Queue-Zeile zeigt live: `14/24 14 -> 2 files` (aktualisiert ~3 s nach
   jeder Änderung).
3. **Create**: keine Fehlermeldung! Stattdessen Job-Meldung mit
   `2 PARTS: <Datei1>, <Datei2>` (Namen enden auf `_T1`/`_T2`).
4. **Beweis** (SSH/Mainsail): genau die 2 Teile-Dateien im Ordner, **keine
   weiteren** neuen Dateien (die Trockenläufe der Aufteilung schreiben
   nichts mehr — der .128-Leak ist weg). Jede Teil-Datei hat eigenen
   PRINT_START + eigenen Purge-Turm und druckt für sich.

## D) NEU: Live-Größe statt Fit-Button

1. Tools > Labels > **Settings**: ganz oben steht jetzt `Now: 60x30mm
   Caps 5.2`.
2. Text ändern (z. B. langes Wort eintippen) → **~2 s später** wandert die
   Zeile selbst (GROW: größeres Label inkl. Loch; `+` zeigt gewachsen).
3. Mode auf **FIXED** → `Now:` zeigt W×H fest, Caps = die eingepasste
   Schrift (wächst mit weniger Zeichen).
4. **H jetzt bis 10 mm wählbar** (Eingabe akzeptiert 10; W bis 12). Die
   Untergrenzen in W/H folgen live dem, was dein Text braucht.
5. Der alte `Calc fit`-Eintrag ist weg — es gibt nichts mehr zu drücken.

## E) NEU: Stempelgriff Handle 0–3 (Labels UND Litho gleich gezählt)

| Wert | Bedeutung |
|---|---|
| 0 | kein Griff |
| 1 | **mit auf der Platte** — druckt als LETZTES Objekt jeder Schicht |
| 2 | separate Griff-Datei (wie .127) |
| 3 | **nur Griff** (Ersatzdruck) |

### E1. Handle=1 (auf der Platte) — der Haupt-Test
1. EIN Label (Stamp an, Mirror X an), Handle=1, Create.
2. **Beweis in der Datei** (Mainsail-Vorschau/SSH):
   - Griff steht mit **≥ 12 mm Abstand** neben dem Label.
   - `EXCLUDE_OBJECT_DEFINE NAME=GRIFF …` vorhanden → im Druck unter
     Objects taucht **GRIFF** auf und kann ausgelassen werden.
   - Datei ist **höher** als das Label allein (Griff ~33 mm) — die Schichten
     über dem Label enthalten NUR noch den Griff.
3. **Beweis im Druck** (Drehrichtung): der Griff kommt in jeder Schicht
   NACH dem Label (nie zuletzt am Label entlangfahren → nichts reißt ab).

### E2. Handle=2 und Handle=3
1. Handle=2 → wie .127: Stampel-Datei + separate Griff-Datei.
2. Handle=3 → NUR die Griff-Datei, keine Platte (Meldung `handle file only`).

### E3. Litho zählt jetzt gleich
1. Litho > Settings > Handle: **2 = separate Datei, 3 = nur Griff** (wie
   Labels). **1 wird abgelehnt** mit klarem Text (Platte-Griff gibt es nur
   bei den Label-Stempeln).

### E4. Griff ohne Stempel
1. Labels: Stamp AUS, Handle=1 → klare Fehlermeldung (Griff braucht den
   Stempel-Socket), nichts wird erzeugt.

## F) NEU: Fehler reden Klartext auf dem Display

1. Stamp AN, **2 Labels** in die Queue → im Job-Menü erscheint die Zeile
   `! Stamp needs 1 label` (solange die Regel verletzt ist).
2. Trotzdem Create → `M117 Err: Stamp = exactly ONE label …` auf dem
   Display (Grund sichtbar, nicht nur Konsole) + Fehler-Sound.
3. Del bis eins übrig → Zeile verschwindet, Create geht durch.

## G) NEU: MCU-Shutdown-Wachhund (Beweisspur + Auto-Restart)

**Nicht absichtlich provozieren** — der Test ist passiv: er greift, wenn
das nächste Mal ein echter Shutdown passiert (Probe-Fehler o. ä.).

1. Passiert ein Shutdown, öffnet der Watcher automatisch ein
   **10-Minuten-Fenster** und schreibt alle 5 s Bett+Hotend-Soll/Ist in
   `logs/r2_shutdown_watchdog.log` (SSH: `tail -f ~/printer_data/logs/
   r2_shutdown_watchdog.log`).
2. **Nach 5 Minuten** Shutdown: automatischer `FIRMWARE_RESTART` (max. 2×
   pro Watchdog-Lauf, mind. 1 h Abstand — kein Restart-Loop).
3. **Die Beweisfrage .128** („bleibt das Bett an?"): sinkt die
   Bettkurve im Log → Power war AUS (Klipper schaltet Heater by design ab,
   3-s-Bestätigung + shutdown_value 0 — dein 24-V-Brett ist sicher).
   Bliebe sie AM SOLL → Strom fließt trotzdem → Verdrahtung/SSR prüfen
   (genau dafür ist die Spur da).
4. Kontrollzeilen im Log: `SHUTDOWN no.N detected`, Temperaturzeilen
   `t+Ns bed X/Y C hotend …`, `auto FIRMWARE_RESTART after 5min`,
   `evidence window closed`.

## H) Schnell-Regression

- Ein ganz normaler 60×30-Label-Job (2–3 Labels) → Layout wie immer,
  Abstände ≥ 10 mm, Druck i. O.
- Litho FLAT mit Stempel+Griff=2 → wie .127 (Snap unverändert).
- Ein optimized-Druck (.128) → Frage „Rate print?" kommt wie gehabt.

---

**Rückmeldung wie immer:** was auffällt (Display-Texte, Abstände,
Teil-Dateien, Watchdog-Log), am besten mit Foto/Konsolenauszug.
