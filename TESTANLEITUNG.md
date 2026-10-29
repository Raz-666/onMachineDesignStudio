# TESTANLEITUNG — R2-D2 Makro-System (Version .134)

Diese Anleitung beschreibt **nur den aktuellen Stand** (.134). Sie ist die
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
      (build R2-2026-10-29.136a)`
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

## 8. Live-Tuning & Profil

- [ ] Live: Speed/Flow/Accel/PA pro Feature, Fan LIVE schlägt alles
- [ ] Nach Druckende: **Rate print?** bleibt bis zur Antwort im Menü
      (kein Timeout), YES schreibt `optimized/`-Kopie, NO stellt den
      Pre-Print-Zustand exakt wieder her
- [ ] Pause/Fortsetzen/Objekt ausschließen je einmal testen

## 9. Wartung & Sound

- [ ] Maintenance > Tests: Selbsttest + Demos
- [ ] Sounds: Bestätigung/Fehler/Laufzeit unterscheidbar (Fit-Beep =
      Bestätigung, nicht Fehler-Beep)
- [ ] `HOST_CHECK`: Pi-Gesundheitsbericht ohne falsche Warnungen

---

**Alles grün?** Dann ist .134 field-clear. Wenn etwas auffällt: Konsole
kopieren (RESPOND-Zeilen) + welche Datei/welcher Menüpfad — daraus wird der
nächste Feldlog-Eintrag.
