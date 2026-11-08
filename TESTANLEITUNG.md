# TESTANLEITUNG — R2-D2 Makro-System (Version .136v)

Diese Anleitung beschreibt **nur den aktuellen Stand** (.136v). Sie ist die
komplette Feld-Checkliste nach dem Einspielen eines Updates — von Boot bis
Druckergebnis. Die Historie der Änderungen steht in README.md.

---

## 1. Update einspielen

1. ZIP in Mainsail in den **config-Ordner** hochladen (neben den
   `klipper-e3-r2d2`-Ordner, nicht hinein).
2. SSH: `bash ~/printer_data/config/klipper-e3-r2d2/update.sh`
   — findet das neueste ZIP, entpackt, prüft Includes + `#`-Blocker,
   startet Klipper und r2-postproc neu.
3. Einstellungen bleiben erhalten (variables.cfg wird nie angetastet).

## 2. Boot-Check (Pflicht, 1 Minute)

- [ ] Konsole: `Macro system OK: all 19 modules loaded and current
      (build R2-2026-11-08.136v)`
- [ ] ~10 s nach dem Boot: Boot-Sound + LED-Animation
- [ ] `SHOW_STATUS` antwortet mit Modus/Material/Overrides
- [ ] Kein Eintrag fehlt: sonst meldet sich `_CHECK_INSTALL` laut mit
      Dateiname

## 3. Menü & Dateien (5 Minuten)

- [ ] LCD-Hauptstruktur: Start Print? · Live Tuning · Pre-Print · Quick
      Macros · Tools · Maintenance · System (Klipper-Stock-Menüs
      OctoPrint/Temperature/Setup bleiben versteckt)
- [ ] Eine geslicte Datei wählen → **File info** zeigt Slicer-Zusammenfassung
      + gemessene Werte + 16 Feature-Zeilen sofort an
- [ ] **Start-Dialog** erscheint, Start erst nach Bestätigung
- [ ] SD-Browser: **Del**-Zeile löscht mit Doppelklick (nur G-Codes-Root,
      nie während eines Drucks)
- [ ] **System > File check** (.136k: zurück aus Pre-Print > Fixes — dort
      war es im LCD unerreichbar): Scan now listet, Retag old nur 2×-gedrückt
- [ ] **Mainsail-Metadaten** (.136k): eine generierte Datei (z. B. Labels)
      zeigt im Datei-Browser Thumbnail + Druckzeit + Filament; ein
      Range-Auszug zeigt das THUMBNAIL DER QUELLE; Slicer-Dateien bleiben
      unverändert

## 4. Labels (der Alltags-Test)

- [ ] Tools > Labels: Text eingeben, **Größe AUTO** wächst statt zu meckern
- [ ] **Neun Fonts** wählbar: SMOOTH · MONO · COND · NARROW · CAPS ·
      SCRIPT · HAND · PLATE · PIXEL
- [ ] **Preview fit?** antwortet mit echten Zahlen (Endgröße inkl. Wachstum)
- [ ] **Nach jedem Settings-Wechsel** (auch nach dem ersten ADD):
      Bestätigungs-Beep + Editor-Zeilen-Vorschau
- [ ] Druck: **Brim löst sich sauber vom Label** (~0,35 mm Luftspalt zur
      Wand-Tinte — auch am Purge-Turm), Schrift ohne Kollisionen
      (SCRIPT/HAND-Schwünge drucken getrennt)

## 5. Brim-Luftspalt bei allen Generatoren

Der Brim darf **nie** mit dem Objekt verschmelzen — er hält am Bett, nicht
am Teil (Ausnahme: der Range-Brim als Anker für Schnitt-Teile bleibt
bewusst angeschweißt). Je ein Probedruck:

- [ ] **Rahmen** (Tools > Frames): Brim nach dem Druck abnehmbar
- [ ] **Kabelbinder**: Brim löst sich
- [ ] **Litho FLAT**: Brim löst sich (auch am Bildrand)
- [ ] **Labels** inkl. Purge-Turm: siehe 4.

## 6. Echo-Ruhe & Performance

- [ ] Identische Feature-Blöcke fluten die Konsole NICHT (Echo-Gate)
- [ ] M204-Stürme bleiben aus (Litho/Frame-Dateien drucken durch, kein
      „Timer too close")
- [ ] LED-Druckzustand: ruhiges blaues Atmen (4 s Takt), kein Flackern

## 7. Gemischte Jobs & weitere Generatoren

- [ ] Labels-Queue mit **verschiedenen Fonts + Größen** (GROW und FIXED
      gemischt): mind. 25 mm Objektabstand, keine Überschneidung
- [ ] **String Art** (Tools > String art, SPIRAL oder PHOTO): Ankerring
      druckt zuerst, Stränge in Z-Bändern darüber
- [ ] **Plotter**: Bild/Text wählen → Pen-Modus ungeheizt, `00_Plot_*`
      entsteht erst bei Auswahl (keine Zwillinge mehr)
- [ ] **Bricks/Bausatz/Figuren** nach Bedarf: Noppen klemmen an Originalen
- [ ] **File-Check an beiden Orten (.136m)**: System > File check UND
      Pre-Print > Fixes > File check — dieselbe Liste (Scan now, How it
      works, Retag 2-Press, RETAG OLD NOW, Re-fix, RE-FIX TYPES NOW)

## 8. Live-Tuning & Profil

- [ ] Live: Speed/Flow/Accel/PA pro Feature, Fan LIVE schlägt alles
- [ ] **Custom-Code-Slots (.136l)**: eine Datei mit unbekanntem
      `;TYPE:`-Block drucken (z. B. Textur-Reste oder
      Slicer-Dialekt) → Pre-Print > Features > Custom Code zeigt
      **C1, C2, … nur die Gruppen, die die Datei wirklich trägt**
      (kein Sicherheits-Fallback auf Außenwand mehr!) — je Slot:
      On/Spd/Acc/Flw/PA; Live > Features > Custom Code genauso,
      Änderung greift sofort wenn genau dieser Block druckt
- [ ] **Textur-Preset-Nummerierung (.136l)**: Pre-Print > Texture >
      My presets → Save speichert als **grid01, wave01, …**
      (Texturname + fortlaufende Nummer, nie Überschreiben); ein
      zweites Save unter gleichem Namen ergibt grid02
- [ ] **Textur-Vorlagen (.136m)**: Pre-Print > Texture > Vorlagen →
      44 Looks nach Optik (Rattan, Sandstein, Seil, …), 6 Seiten;
      ein Druck LÄDT alle Settings und die Antwort nennt sie
      (pattern, scale, zsize, amp, dir); Löschen verweigert
      (schreibgeschützt); eigener Save unter Vorlagen-Namen nummeriert
      sich selbst; TEXTURING.pdf im Repo zeigt alle 21 Muster mit
      echten Vorschauen
- [ ] **STL-Export (.136m)**: Datei wählen → Pre-Print > File info >
      `STL: object only` → `gcodes/stl/<name>_object.stl` entsteht
      (nur Objekt, ohne Supports/Skirt/Brim/Tower/Custom/Ironing;
      Zusammenfassung nennt Rippen/Layer/Dreiecke und was draußen
      blieb); nur im Leerlauf (während des Drucks abgewiesen)
- [ ] **Litho-Aufrechtdruck-Stützen (.136m)**: Litho > Settings >
      Side stands ON → Datei hat **LITHO_STAND_L/R**-Objekte;
      dreieckige Flossen links+rechts, ~5-mm-Perforation,
      1,2-mm-Bruchnaht; Frame OFF → Stützen ehrlich aus + Hinweis
- [ ] **Label-Einprägung (.136m)**: Label mit 2 Textschichten →
      Gesamthöhe = naive Summe MINUS 1 Lage (erste Textschicht
      druckt IN der letzten Basisschicht — Konturen bleiben im
      Plastik erkennbar, selbst wenn obere Schichten abplatzen)
- [ ] Nach Druckende: **Rate print?** bleibt bis zur Antwort im Menü
      (kein Timeout), YES schreibt `optimized/`-Kopie, NO stellt den
      Pre-Print-Zustand exakt wieder her
- [ ] Pause/Fortsetzen/Objekt ausschließen je einmal testen

## 9. Web-LCD im Browser (.136m-Checks)

- [ ] Seite öffnen: **die Seite scrollt NIE** (.136l: `100dvh`-Layout,
      nichts ragt heraus) — nur die Konsole scrollt INNERHALB ihres
      Kastens, und die **Eingabezeile steht OBEN** bei den
      Konsolen-Buttons (immer sichtbar, ohne Hinscrollen)
- [ ] **A+ / A− oben in der Ecke**: globale Schriftgröße 11–24 px in
      0,5er-Schritten, der Browser merkt sich die Wahl
- [ ] **Getrennte Schriftgrößen** für Benachrichtigungen, Dateibrowser +
      Senden-Menü und Konsole (je −5…+8 px um den Basiswert, gemerkt)
- [ ] **LCD-Benachrichtigungen 3–4 Nummern größer**, Detail-Text im Feld
      darüber 2 Nummern, Dateibrowser 1 Nummer größer als vorher
- [ ] **Live-Bereich gestapelt (.136m)**: Spalten übereinander —
      Modus+Datei, Temperaturen (Düse/Bett/Lüfter), Speed-Zeug
      (Feed/Accel), Flow+PA, Zeiten (Fortschritt %, Laufzeit, Rest) —
      und **Layer + Feature in EINER Zeile GANZ UNTEN** unter allen
      Werten (gleicher Poll wie vorher, keine zusätzlichen Abfragen)
- [ ] Konsole-Toolbar: **Leeren** leert, **Suchfeld** filtert die Historie,
      Autoscroll-Knopf schaltet
- [ ] **Tools-Menü + SD-Liste gefüllt** (der .136k-Fix: wert-lose
      Schnappschüsse dürfen nichts mehr ausblenden — wenn die Konsole
      live=ok sagt, müssen die Zeilen da sein)
- [ ] Menü-Baum blendet wie das LCD aus (OctoPrint/Temperatur unsichtbar),
      Breadcrumb/↑ zurück funktioniert, Befehle senden GERENDERten G-Code
- [ ] Untermenüs durchklicken: **keine kryptischen Bezeichnungen** mehr
      (der .136l-Volltest: jede dynamische Zeile rendert, auch bei
      C-Slots, Input-Werten und enable-Bedingungen)

## 10. Wartung & Sound

- [ ] Maintenance > Tests: Selbsttest + Demos
- [ ] Sounds: Bestätigung/Fehler/Laufzeit unterscheidbar (Fit-Beep =
      Bestätigung, nicht Fehler-Beep)
- [ ] `HOST_CHECK`: Pi-Gesundheitsbericht ohne falsche Warnungen
- [ ] `HOST_CHECK` **zeigt jetzt auch klippys eigene Last** (R215): die
      Zeile „Reactor: … stalls … failed LED updates“ — nach dem Update
      sollte sie „clean – no stalls“ sagen; stehen dort viele Stalls,
      ist der Host zu beschäftigt für die Homing-Phase
- [ ] **Druckstart ohne MCU-Shutdown** (R215, der .136l-Kettenfix):
      Datei auswählen → Start → Homing muss durchlaufen, ohne dass
      „Timer too close“ die Steuerung abschaltet — Watcher schreibt
      jetzt nicht mehr bei jedem Durchlauf alle Dateien neu, die
      gen_files-Liste darf sich nicht mehr alle paar Sekunden neu
      sortieren (Konsole beobachten) und die Weboberfläche hält nach
      einem Start-Befehl 25 s mit dem Live-Poll still (Konsole läuft
      weiter)
- [ ] **Keine „Unknown gcode_macro variable fecho_c1/fov_c1“** mehr in
      der Konsole (R213-Restfehler: die C-Slots wurden gesetzt, aber
      nie deklariert)

## 11. Die .136v-Neuerungen (R224-Feldrunde)

- [ ] **Spiegel-Tool**: Pre-Print > Mods > Mirror — Achse X/Y, „How?"
      erklärt, Apply (2×) spiegelt die gewählte Datei (auch OBJ-Modus);
      es entsteht eine NEUE Datei, die Quelle bleibt
- [ ] **Cut & Split ohne Yaw**: nur noch Pitch / Roll / Z-Plane;
      **Part BOTH = ZWEI Dateien** (`…_CUT-L` + `…_CUT-U` im
      Cake-Ordner), jede druckt eigenständig mit eigenem E-Basiswert
- [ ] **Range stapelbar**: Range mit Floor/Cap → der Auszug ist exakt
      so hoch wie das Fenster (Kopfzeile sagt „floor 2 INSIDE the
      window" — vorher saß der Floor als Floß UNTER dem Fenster);
      Methodik: CUTSPLIT.pdf + Kapitel 6 TEXTURING.pdf
- [ ] **Labels**: Walls-Knopf 1–4 (Strichstärke = Wände × Linienbreite,
      Preview == Druck), der **Stempel spiegelt den Text automatisch**
      (die Spiegel-Zeilen sind aus dem Label-Menü entfernt), Glyphen
      sitzen zentriert
- [ ] **Textur-Namentreue**: Rope = 3-Strang-Drehtampen, Basket = echtes
      Geflecht, Checker = Schachbrett mit weichen Kanten;
      **Fixed presets** jetzt 7 Einträge (Orca / Hide layers / Subtle /
      Grip / **Rope / Basket / Chess**)
- [ ] **Textur-Innenwände folgen**: BUMPS mit tiefem DIR=IN drucken —
      die Täler sind voll ausgeprägt (Innenwand folgt der Prägung,
      Wandabstand bleibt eine Linienbreite); FUZZY unverändert
      (nur die Außenwand zittert, wie bei Orca)
- [ ] **Systemmenü**: Sound + LED-Farben unter System > LED config;
      die WebUI zeigt denselben Menübaum wie das LCD (Embed aktuell,
      2480 Sektionen)
- [ ] **Gen jobs**: Clear Queue hält die Flags, solange der Thread lebt
      (kein Zombie-gen_busy blockiert einen Druckstart mehr); ein
      laufender Build bleibt beim Clear am Leben
- [ ] **Slicer-Dateien**: Orca- UND Cura-Dateien bekommen TYPE=
      (Feature-Übersetzung in der Datei-Info); die Cura-Startbox
      läuft ohne G28-Störung

---

**Alles grün?** Dann ist .136v field-clear. Wenn etwas auffällt: Konsole
kopieren (RESPOND-Zeilen) + welche Datei/welcher Menüpfad — daraus wird der
nächste Feldlog-Eintrag.
