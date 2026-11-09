# TESTANLEITUNG — R2-D2 Makro-System (Version .136ac)

Diese Anleitung beschreibt **nur den aktuellen Stand** (.136ac). Sie ist die
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
      (build R2-2026-11-08.136ac)`
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

## 12. Die .136w-Neuerungen (R225-Auditrunde)

- [ ] **Mainsail-Metadaten bei Generator-Dateien**: frisch generierte
      Dateien zeigen jetzt Thumbnail, Druckzeit, Filament, Schichthöhen
      in der Dateiliste (Ident-Stempel „R2-D2", Block am Dateiende,
      exakt nach Moonrakers Parser; alte Dateien heilen beim nächsten
      Watcher-Lauf selbst)
- [ ] **Web-Refresh**: Konsole > Menu refresh re-exportiert jetzt auch
      auf der Doku-Installation (`~/printer_data/config/...`) — das
      Werkzeug wird aus dem JSON-Pfad abgeleitet, install_web.sh
      schreibt `export_tool:` in die moonraker.conf
- [ ] **Stray-Tag-Schutz**: eine Datei mit nur EINEM globalen
      APPLY_TYPE/;TYPE: wird auf Geometrie-Ebene gegengeprüft —
      Wechsel gefunden → Feature-Grenzen aus der Geometrie
      (`STRAYTAG=` in der Datei-Info nennt das falsche Tag); stimmige
      Dateien (reine Vasen) bleiben unangetastet
- [ ] **Slicer-Vokabular**: Simplify3D (`; feature …` ohne Doppelpunkt),
      FlashPrint (`;structure:…`), Kiri:Moto (`; shell`), KISSlicer
      (crown/upper face/lower face), ideaMaker (Shells/Türme), Orca-
      CamelCase-Platzhalter — bisher CUSTOM, jetzt korrekt erkannt
- [ ] **Cura-Objekt-Box**: ohne ;LAYER:/;TYPE: steht die Box jetzt VOR
      dem ersten Druckbefehl (nicht mehr hinter PRINT_END) — adaptives
      Mesh/Parken greift wieder
- [ ] **update.sh** meldet „all 19 modules" (war 17, es waren immer 19)

---

## 13. Die .136x-Neuerungen (R226-Feldrunde)

- [ ] **Orca-CENTER-only-Druck startet** (der Feldlog-Krasher): Orca/
  Bambu schreiben `EXCLUDE_OBJECT_DEFINE … CENTER=x,y` ohne POLYGON —
  KAMPs SMART_PARK starb mit `'dict object' has no attribute 'polygon'`
  und riss den Druckstart mit in den Fehler. Jetzt: (a) der Watcher
  misst die Objekt-Box aus den Moves nach und ergänzt `POLYGON=` beim
  Scans (einmalig, idempotent), (b) Prime-Line/Parken/Purge vertragen
  sich mit CENTER-only (20×20-mm-Box um den Center), (c) SMART_PARK
  und adaptives Mesh werden nur mit vollständigen Polygonen gerufen —
  sonst Standard-Park + Vollbett-Mesh mit RESPOND-Hinweis
- [ ] **gen_busy lügt nie mehr nach**: blieb die Flagge=1 überstehen
  (Release im Fehlerfall verschluckt, Neustart dazwischen), blockierte
  sie JEDEN Druckstart („Wait: generating") bis zum Handeingriff.
  Jeder Watcher-Pass gleicht die Flagge mit der Realität ab — kein
  Thread, keine Queue → wird laut geräumt („stale gen_busy cleared",
  M117 „Queue free")
- [ ] **Klippy-Log-Export zeigt echtes Fenster**: der Filter erwartete
  Zeilen-Zeitstempel — klippy.log hat keine (Sektionen pro
  Klipper-Start, `Start printer at …`). Jetzt: Fenster wählt Sektionen,
  Config-Dumps fliegen raus, der aktuelle Lauf bleibt immer, leerer
  Export unmöglich (roher Tail als Fallback)

---

## 14. Die .136y-Neuerungen (R227-Hotfix)

- [ ] **Kein Reconciliation-Spam mehr**: die .136x-Feldrunde meldete
  „stale gen_busy cleared" alle ~6 s Dauerfeuer, obwohl die Flagge
  falsch (False) in der Datei stand — der Test hatte den STRING '0'
  auf Wahrheit geprüft (nicht-leerer String = wahr in Python). Jetzt
  wird der Wert echt geparst, und die Meldung kommt **einmal pro
  Vorfall** (klipper down → stille Wiederholung, keine Konsolen-
  Flut). Druckstarts waren durch den Spam nie blockiert — nur Optik
- [ ] **update.sh startet Moonraker mit neu**: der Web-Konsolen-Code
  (r2_menu.py) lädt beim Moonraker-Start — ohne Neustart lief der
  klippy.log-Tag-Export weiter auf altem Code (78-Byte-Datei), bis der
  Pi von Hand neu gestartet wurde. update.sh erledigt das jetzt selbst
- [ ] **postproc_build-Stempel sagt die Runde**: Boot zeigte
  „.136x (R223)" — der Runden-Annotat war seit R223 nicht gebumpt;
  jetzt „.136y (R227)"

---

## 15. Die .136z-Neuerungen (R228-Pausen-Sturm-Runde)

- [ ] **Kein „mode stuck in paused" mehr nach RESUME**: der State-Watcher
  konnte genau in die Lücke zwischen Modus-Wechsel (printing) und
  Klippers print_stats (zieht beim M24 erst mit) samplen und kippte den
  Modus zurück — im Feldlog nach JEDER Pause, Heilung brauchte ~10 s.
  Jetzt folgt derWatcher einem fremden Pause-Stopp erst nach 3 Runden
  (Mainsail-Pause bleibt persistend, die Resume-Lücke nie)
- [ ] **Filament-Sensor-Gnadenfenster**: Prime-Line startet 30 s, Resume
  20 s Langsamkeit-Toleranz — der Motion-Sensor meldet am Anfang gern
  „nichts gefördert", solange sich der Druck aufbaut; Geplapper wird
  gemeldet statt eine Pause zu scharf zu stellen, echte Runouts kommen
  nach dem Fenster durch
- [ ] **„Pause NOW"-Armierung läuft ab**: die Zwei-Drück-Bestätigung
  blieb sonst ewig scharf — jeder spätere Einzelklick (oder EMI-Geister-
  Klick am 12864-Encoder) pausierte. Armiert verfällt nach 5 s
- [ ] **Kein Banner-Sturm nach MCU-Shutdown**: der Daemon schiebt jetzt
  nur noch bei bereitem Klipper (jeder Schub in einen abgeschalteten
  Klipper druckte das komplette „Timer too close"-Banner neu) und max.
  1× pro 10 s

---

## 16. Die .136aa-Neuerungen (R229-Vokabular-Restliste)

- [ ] **KISSlicer-Dateien mit Seam/Destring-Markern:** `; feature Seam`
  (Nahtpunkt) und `; feature Destring` (Retract/Travel) sind
  **Bewegungs-Annotationen, keine Features** — früher wären sie CUSTOM
  geworden und hätten die Wand zerschnitten (Wand-Overrides weg auf den
  Naht-Segmenten). Jetzt bleibt der Feature-Kontext hindurch bestehen
  (auch Travel/Retract/Wipe/Tool-Change/Color-Change/Pause als Marker)
- [ ] **Purge/Prime-Strukturen sind eine Klasse:** Prime Wall, Wipe Wall
  (Korrektur: war Skirt), Prime Pillar, Wiping Tower, Purge Block/Line/
  Blob → alle PRIME-TOWER (Überschreibbar wie der Prime-Tower)
- [ ] **Rest-Zuordnungen:** Belt Lead → Skirt, Brim Ears → Brim, Painted
  Support → Support, Raft-Stapel → Bodenfläche; Infill-Muster-Namen
  (TPMS, Octet, Tetrahedral, Stars, Lateral Honeycomb, Lattice, Spiral
  Inset) → sparses Infill

---

## 17. Die .136ab-Neuerungen (R230-Komplettliste Infill-Muster)

- [ ] **Vollständige Infill-Muster-Liste:** alle 34 Sparse-Muster aller
  Slicer-Familien (Prusa/Orca/Bambu, Cura, Simplify3D — von Rectilinear
  bis TPMS-FK, Cross 3D, Fast Honeycomb) plus die Monotonic-Familie
  (Top/Bottom → solides Infill) lösen sauber auf — ein benanntes Muster
  bleibt nie mehr CUSTOM, das mehrstufige Erkennungssystem (Karte →
  Leiter → Geometrie → CUSTOM-Watch) erkennt Innenfilz damit in jeder
  Stufe. **Korrektur:** „Support Cubic" ist Prusas sparses Infill zur
  Top-Abstützung (nicht Support) — der exakte Schlüssel schlägt die
  Support-Substringsregel

## 18. Die .136ac-Neuerungen (R231/R232 — Etiketten-Einlege-Druck, Feldkorrekturen)

- [ ] **Etiketten: Schrift als FLUSH-Einlege (Inlay):** Text_layers 2–4 ist
  jetzt die GESAMT-Texttiefe — 2 = bündig mit der Oberfläche (Konturen
  werden in die Solidschicht B-1 gebrannt, Füllung bündig in die
  Deckschicht B), 3/4 = zusätzlich erhaben. Layer 1 druckt die Buchstaben
  integriert (Bottom). Druckreihenfolge: Fläche+Konturen → Buchstaben+Rand,
  minimaler Farbwechsel (1× M600)
- [ ] **Flip-Modus:** Tools > Labels > Settings > Flip — textseitig nach
  UNTEN drucken: vom Bett abgenommen LESBAR (Buildplate-Finish auf den
  Buchstaben). Ironing aus, exkludiert Stamp+Ring+2farbig
- [ ] **Range-Auszüge ehrlich:** TYPES=/FS_ der Excerpt-Datei zählt nur
  Tinte, die der Auszug WIRKLICH druckt (in-window Floor/Cap ersetzen
  Schichten — deren Marker zählen nicht mehr doppelt); generierte
  Grundgeometrie läuft 40 mm/s statt pauschal 20
- [ ] **Texturen über die GESAMTE Wand:** Musterzellen behalten ihre
  physische Breite auch auf konkaven Abschnitten (Bogen-Anker), Innenwände
  folgen der Prägung (Wandpaar bleibt zusammen)
- [ ] **Bricks-Queue löschen:** Clear all hat einen funktionierenden
  2-Press-Confirm (vorher wollte das Macro CONFIRM=1, das das LCD nie
  sendet), Del last heilt Legacy-Queue-Formate
- [ ] **Presets:** Texture-Delete kopierte die 44 Bibliotheks-Looks in
  Deinen Preset-Schrank (Schrank schrumpfte nie) — behoben + Selbstheilung
  beim nächsten Zugriff; defekter Preset-Speicher killt die Engine nicht
  mehr still
- [ ] **ArtisticStrings:** Foto-Seitenverhältnis fest verriegelbar
  (AR-Lock-Zeile: X ändern → Y folgt und zurück; Picker übernimmt das
  Bildformat); Graustufen-JPEGs dekodieren wieder (>512px crashten den
  Decoder); Rechenzeit/RAM des Foto-Baus ~3-4× geringer (separable IDCT,
  Decode-Cap 288px, zeilenweise Luma-Übergabe)
- [ ] **HOST_CHECK ehrlich:** M117 nennt den ECHTEN Grund („klippy
  stalls" statt „SWAPPING!" bei still geparktem Swap + Reactor-Blockaden)

---

**Alles grün?** Dann ist .136ac field-clear. Wenn etwas auffällt: Konsole
kopieren (RESPOND-Zeilen) + welche Datei/welcher Menüpfad — daraus wird der
nächste Feldlog-Eintrag.
