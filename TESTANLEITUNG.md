# TESTANLEITUNG — R2-D2 Makro-System (Version .141)

Diese Anleitung beschreibt **nur den aktuellen Stand** (.141). Sie ist die
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
      (build R2-2026-11-09.142a)`
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

## 19. Die .136ad-Neuerungen (R233 — Update-Ablauf repariert)

**Was war kaputt (Dein Feldbericht):** seit .136z kam kein Update mehr an —
„er macht immer wieder nur Z draus, obwohl die anderen Version alle
hochgeladen sind". Grund: der Buchstaben-Anhang der Hotfix-Versionen ist ein
**Zähler** (.136z → .136aa → .136ab → .136ac …), update.sh verglich ihn aber
als **String** — und `'ac' < 'z'` ist lexikographisch WAHR. Jede Version
nach .136z galt als „ÄLTER" und wurde abgelehnt; das .136ac-Zip lag
hochgeladen neben der Config und wurde nie entpackt.

**Der Fix:** update.sh zählt den Anhang jetzt arithmetisch
(`''`=0, a…z=1…26, aa=27, ab=28 … az=52, ba=53 …) — an beiden Stellen,
sowohl bei der „neuestes Zip"-Auswahl als auch beim Downgrade-Schutz. Die
Zahlen dominieren weiter (130 > 129a > 129). Nebenbei behoben: der Web-LCD-
Refresh quittierte seit R225 jede Runde mit `sed: unknown option to 's'`
(Pfad im s///-Ersatz) — das neue awk hängt `export_tool` nur hinter eine
`path:`-Zeile INNERHALB der `[r2_menu]`-Sektion (und nie in eine fremde
Sektion wie `[update_manager]`).

### Einspielen von .136z aus — EINMAL --force

Das auf dem Drucker liegende update.sh ist ja gerade das mit dem kaputten
Vergleich — es kann es selbst nicht wissen. Deshalb **ein einziges Mal**
mit `--force` (kein echtes Downgrade — .136ad ist wirklich neuer):

```bash
bash ~/printer_data/config/klipper-e3-r2d2/update.sh --force
```

Danach gelten alle künftigen Updates wieder normal (ohne --force). Das alte
.136ac-Zip darf liegen bleiben (verliert die Auswahl gegen .136ad) —
aufräumen schadet nicht.

### Feld-Checkliste .136ad

- [ ] Update-Lauf zeigt: `uploaded update zip found:
      klipper-e3-r2d2-UPDATE-R2-2026-11-09.136ad.zip` und KEIN
      „that zip is OLDER" mehr
- [ ] `package version: R2-2026-11-09.136ad`
- [ ] Konsole nach Boot: `Macro system OK: all 19 modules loaded and
      current (build R2-2026-11-09.136ad)`
- [ ] Web-LCD-Refresh im Update-Log OHNE `sed:`-Fehlerzeile
- [ ] Gegenprobe Downgrade-Schutz: ein älteres Zip (z. B. .136ac aus
      r2_backups zurück in den Config-Ordner kopiert) wird mit „OLDER"
      abgelehnt — und zwar zu Recht

**Alles grün?** Dann ist .136ad field-clear — ab jetzt kommen Updates
wieder von selbst an. Wenn etwas auffällt: Konsole kopieren (update.sh-
Ausgabe komplett) — daraus wird der nächste Feldlog-Eintrag.

## 20. Die .136ae-Neuerungen (R234 — Feldlog + GitHub-Updates)

**Feldlog 09.11. (auf .136ad):** jeder Foto-Pick meldete
`!! Malformed command 'SAVE_VARIABLE VARIABLE=stringart_imgwh …'` — das
Conditional `if dim != '' else '""'` stand als **Text** hinter dem VALUE
(Klipper lehnte ab, `stringart_imgwh` wurde nie gespeichert). Zweites:
`[queue] StringArt waits: only 88MB RAM free, image builds want 110MB` —
die RAM-Schwelle war noch vom alten Decoder; der R232-Planner peakt bei
**~37 MB**, wartet jetzt ab **64 MB** frei (Litho/ColorPic behalten 110).

**Neu: `update.sh --git`** — Updates direkt aus Deinem GitHub-Clone, ohne
Zip-Download. Einmalige Einrichtung (Bundle → GitHub → Clone auf dem Pi):
siehe **GITHUB.md**. Danach ist ein Update ein Befehl:

```bash
bash ~/printer_data/config/klipper-e3-r2d2/update.sh --git
```

### Feld-Checkliste .136ae

- [ ] Foto-Pick (ArtisticStrings > PHOTO > Bild wählen): Konsole zeigt
      KEIN „Malformed command" mehr; AR-Lock-Zeile zeigt die px-Maße statt
      „(no img)"
- [ ] StringArt-Fotobau startet bei ~88 MB freiem RAM OHNE Pi-Neustart
      (Wartemeldung nennt jetzt „want 64MB")
- [ ] `Macro system OK: all 19 modules loaded and current
      (build R2-2026-11-09.136ae)`
- [ ] (Wenn auf Git umgestellt) `update.sh --git` läuft durch:
      fetch → ggf. „updating <alt> -> <neu>" → komplette Choreographie
      bis „== done. Happy printing! =="

**Alles grün?** Dann ist .136ae field-clear. Wenn etwas auffällt: Konsole
kopieren (RESPOND-/!!-Zeilen) — daraus wird der nächste Feldlog-Eintrag.

## 21. Die .136af-Neuerungen (R235 — Timer-too-close-Feldlog)

**Feldlog 09.11. (Textur-Druck V04_BigRose_020mm_TX.gcode, 6000 moves/s):**
zwei „Timer too close"-Cluster — eines **vor** dem Druck (Reactor 0,46 s
blockiert: LCD-Menü + Webhook-Polls + DelayedGcode bei `gcodein=0`, der
Host war schon angespannt: Watcher 27 % CPU, 11 Reactor-Stalls), eines
96 s **in** den Druck (Reactor 0,48/0,99 s: Filament-Sensor + Webhooks —
bei Mikro-Zügen puffert die Move-Queue nur Millisekunden). Die Warnung
„up to 6000 moves/s …" kam zur **Dateiauswahl**, war aber im
Entscheidungsdialog (Minuten später) weg gescrollt — gedruckt wurde
trotzdem ungemergt.

**Der Fix:** das Risiko reist mit der Vorschau-Karte (`_PREVIEW.moverate`,
gestempelt vom Watcher als MOVERATE) — und der **Start-Dialog wiederholt
es zur Entscheidungszeit**: beide Fang-Stellen zeigen ab >400 moves/s
eine `[!]`-Zeile mit dem SegFix-Weg, und solange der Dialog wartet,
zeigt das LCD `M117 SegFix first! Start?` statt „Changes?".

**Diagnose aus dem Log (fürs Feld):** die Konsolen-Meldungen waren NICHT
die Ursache (~0,2 Zeilen/s; die Reactor-Spuren nennen Menü, Webhooks,
Sensor — nie Meldungsverarbeitung). `_M204` (2× „Unknown command")
stammt aus Deiner eigenen printer.cfg, nicht aus dem Paket.

### Feld-Checkliste .136af

- [ ] Riskante Datei (Textur mit >400 moves/s) auswählen → Start-Dialog
      zeigt jetzt AUCH im Dialog die `[!] … moves/s … Segment fix FIRST`-
      Zeile; LCD zeigt während des Wartens `SegFix first! Start?`
- [ ] **Vor dem Textur-Druck: Pre-Print > File > Segment fix ausführen**
      (der eigentliche Hebel — verschmilzt die Mikro-Züge auf ~450/s)
- [ ] Normale Datei: Dialog unverändert („Changes? -> menu Start?",
      keine `[!]`-Zeile)
- [ ] `Macro system OK: all 19 modules loaded and current
      (build R2-2026-11-09.136af)`

**Alles grün?** Dann ist .136af field-clear. Wenn etwas auffällt: Konsole
kopieren — daraus wird der nächste Feldlog-Eintrag.

## 22. Die .136ag-Neuerungen (R236 — die Abendrunde: 6 Feldberichte)

**1) Mirror Y speicherte nie.** Die Achsen-Auswahl schrieb
`SAVE_VARIABLE ... VALUE="y"` — ein nackter String. Klippers
save_variables parst mit `ast.literal_eval`, und `y` ist kein
Python-Literal: der Befehl starb still, die Achse blieb für immer `x`
(deshalb gab es im Mirror-Ordner nur _MIRX-Dateien). Gleiches galt für
**Textur-Richtung IN** und **Cut&Split-Teil** (UPPER/LOWER/BOTH) — alle
drei speichern jetzt das korrekt gequote Python-String-Muster.

**2) Die Textur verschwand auf der Rückseite.** Die Umfangsmessung
(`chord / layers_seen`) bricht auf **Spiral-Vasen**: dort steigt Z mit
jedem Zug minimal, also zählte `layers_seen` ZÜGE (Deine Rose: 45.292
statt 242 Layer) — der „Umfang“ degenerierte zur mittleren
Segmentlänge (2,9 mm). Damit war `k=1` für JEDES Preset: **eine einzige
Musterwelle um das ganze Objekt** — vorne der Berg, hinten das Tal, das
wie Original-Oberfläche aussieht. Jetzt ist der Umfang der **Median der
real gemessenen Wand-Loops** (Beweis: Testvase Umfang 1,5→188,6 mm =
2πr exakt, ridges 1→8 bei 24 mm-Vorgabe; Deine Rose: ridges 1→11,
effektive Ridges-Größe 23,3 mm ≈ Vorgabe).

**3) Neue Dateien erschienen nicht im Ordner.** Der Baum-Push pausierte,
solange die Warteschlange arbeitete — 24 Texture-Jobs = 30 min alte
Liste. Jetzt pusht **jeder fertige Job sofort** (Druck gewinnt weiter),
und moonraker bekommt explizit einen filelist-notify für das Web-UI.

**4) Die Warteschlange zeigt sich.** `Gen queue: N waiting` steht jetzt
**im Hauptmenü direkt über der SD-Karte** (nur sichtbar, wenn etwas
wartet oder baut), die Zahl fällt mit jedem erledigten Job. „building
now - 5 waiting“ in der Konsole, „X done - 4 job(s) still waiting“ nach
jedem Job, Clear wie gehabt.

**5) Profil-Laden antwortet.** Defaults 1–8 und This-file pre/post:
Klick → **raus aus dem Menü**, Display „Loading profile“ + Start-Beep,
nach der Werteflut der Done-Beep + „Loaded: N on“. Automatische Lade-
Pfade (Dateiauswahl) bleiben leise + eine Konsolenzeile.

**6) Keine LED-/Beep-Bursts mehr im Bewegungsmoment.** Homing, Druck-
start (M24/Layer 1), PAUSE, Filament leer, RESUME: LED-Wechsel + Beep
kommen jetzt **1–1,5 s später** (modus-geprüft — ein Cancel dazwischen
killt sie still). Die Aktion selbst bleibt sofort.

**Zusätzlich:** Die „IDLE SPIN detected“-Meldung nach Deiner Job-Serie
war ein Messfehler (das 5-Min-Fenster enthielt die Generator-Arbeit) —
kontaminierte Fenster werden verworfen.

### Feld-Checkliste .136ag

- [ ] Mirror: Achse auf Y drehen → bestätigen → beim Wiedereintritt
      steht `Axis: Y`; ein Mirror-Lauf erzeugt eine **_MIRY**-Datei
- [ ] Textur auf eine Testrose (z. B. „Sanfte Duenen“, 24 mm) → die
      Meldung meldet jetzt `N ridges` (nicht mehr `1 ridges`), effektive
      Größe ≈ Vorgabe → Druck: Textur komplett rundum inkl. Rückseite
- [ ] Mehrere Jobs in die Warteschlange legen → Hauptmenü zeigt
      `Gen queue: N waiting` über der SD-Karte, Zahl fällt pro Beep
- [ ] Neue Datei erscheint nach Job-Ende im LCD-Ordner UND im Web-UI
- [ ] Defaults > Load 1 → Display „Loading profile“ → Beep → „Loaded“
- [ ] `Macro system OK: all 19 modules loaded and current
      (build R2-2026-11-09.142a)`

**Alles grün?** Dann ist .136ag field-clear. Wenn etwas auffällt: Konsole
kopieren — daraus wird der nächste Feldlog-Eintrag.

## 23. Die .136ah-Neuerungen (R237 — MAP-Bilder laden, _M204 gefangen)

**1) Textur-MAP: Bilder lassen sich endlich laden.** Drei Brüche
wirkten zusammen:

- Ein **Root-Bild** (Mainsail drag&drop in den G-Codes-Ordner) setzte
  den Pick NIE — der SD-Browser redete nur („use Tools >
  Lithophane“), gepickt haben nur Subfolder-Klicks. Jetzt pickt der
  Root-Klick auch („picked - ready for Texture MAP“).
- Der Watcher hätte einen Root-Pick auf sich selbst kopiert
  (SameFileError, wäre ohne Feedback gestorben) — gleiche Datei =
  kein Copy, nur Bestätigung.
- `texture_map` ist ein relativer Name, der gegen den Ordner der
  QUELLE aufgelöst wurde — Dateien aus Texture/, Labels/ … fanden
  ihr Bild nie. Der Watcher übergibt jetzt einen ABSOLUTEN Pfad
  (Subfolder-Pick zuerst, dann dessen Root-Kopie); das Skript selbst
  probiert den literalen relativen Pfad und dann den Basename neben
  der Quelle (eine fehlende Datei nennt jeden versuchten Pfad).
- Zusätzlich: TEXTURE_APPLY meckert SOFORT („MAP needs an image“),
  wenn gar kein Bild existiert — statt generisch in der
  Warteschlange zu sterben.

**2) `_M204` ist gefangen.** Zweimal „Unknown command“ pro Druck —
das Feldlog beweist: die Aufrufe kommen AUS DER DATEI (virtual-SD,
Startblock direkt hinter den Thumbnails, unmittelbar nach
PRINT_STARTs Post-Heat-Settings; gcodein=0). Kein Absender im Paket
(nur `_M204_SET` — per git log -S über die gesamte Historie bewiesen)
und keiner in Deinen printer_data-Configs; die Zeilen reiten im
Start-G-Code des Slicer-Profils mit (deshalb fand Dein grep nichts:
grep schweigt bei 0 Treffern — das Schweigen WAR das Ergebnis).
Drei Antworten:

- **Alias:** `_M204` leitet den Rohtext an den M204-Interceptor
  weiter (Feature-Beschleunigung, globale Überschreibung, Live-Cap,
  ehrlicher Tracker) — keine Unknown-command-Meldung mehr, auch bei
  Dateien, die nie ein Tool angefasst hat.
- **Scrub:** Textur-Tool und Segment-Fix schreiben legacy
  `_M204`-Zeilen beim Bearbeiten in place zu `M204` um (Fertig-
  Meldung: „[legacy _M204 renamed: N]“; `_M204_SET` bleibt
  unberührt — auch der Früh-Ausstieg des Segment-Fix wirft die
  Umbenennungen nicht mehr weg).
- **Nie emittiert:** die Generatoren haben `_M204` nie erzeugt.

### Feld-Checkliste .136ah

- [ ] Ein Bild per Mainsail in den G-Codes-Ordner ziehen → im
      LCD-Browser anklicken → „picked - ready for Texture MAP“
- [ ] Pre-Print > Texture > Pattern Map → Img: zeigt den Namen →
      Apply → „Texture ready“ mit ridges-Angabe → der Druck zeigt
      das Bild als Relieftextur (rundum)
- [ ] Ein V-File drucken → Konsole: KEIN „Unknown command _M204“
      mehr (auch alte, ungefixte Dateien: der Alias schluckt sie)
- [ ] `TEXTURE_APPLY PATTERN=MAP` ohne jedes Bild → sofort
      „MAP needs an image“ + Error-Beep (nicht erst in der Queue)
- [ ] `Macro system OK: all 19 modules loaded and current
      (build R2-2026-11-09.142a)`

**Alles grün?** Dann ist .136ah field-clear. Wenn etwas auffällt:
Konsole kopieren — daraus wird der nächste Feldlog-Eintrag.

## 24. Die .136ai-Neuerungen (R238 — Master-Prompt-Runde)

**1) Generierter G-Code ist jetzt VON SELBST MCU-sicher.** Der Job-Worker
misst nach jedem Generator-Lauf die schlimmste Move-Rate und fährt den
Segment-Fix AUTOMATISCH, wenn sie über 400 Moves/s liegt (die Schwelle
aus der Start-Dialog-Warnung): „[queue] … AUTO segment fix — N micro
move(s) merged, worst rate … -> …/s". Der manuelle Menü-Weg bleibt für
alte Uploads. Nach dem Generieren ist also KEIN separater Segment-Fix
mehr nötig.

**2) Die Warteschlange lässt sich STEUERN.** Hauptmenü, direkt über der
SD-Karte (heiß jetzt „Gen queue", nicht mehr unten):
- **Skip job -> next** — beendet den LAUFENDEN Job (Teil-Datei wird
  gelöscht), der nächste startet.
- **Stop: job + queue** — beendet den laufenden Job UND leert die
  Warteschlange (Doppelklick-Schutz).
- **Clear waiting queue** — wie gehabt: nur die Wartenden weg.
Der Abbruch trifft den Job an einem sicheren Punkt im Generator (nie
mitten in einem Schreibvorgang). Auch Mainsail/Konsole:
`_GEN_QUEUE_SKIP` bzw. `_GEN_QUEUE_STOP CONFIRM=1`.

**3) STL-Export ist in Mainsail sichtbar.** Ergebnisse liegen jetzt im
Ordner **STL** als `name_object.stl.gcode` — Mainsail zeigt sie, ein
Klick lädt sie herunter, Endung `.gcode` entfernen, fertig (der Watcher
behandelt sie als Daten, nicht als G-Code; im LCD-Browser erklärt der
Klick den Weg statt zu drucken).

**4) Texturen hören auf, Streifen zu sein (Master-Prompt).**
- **Auto-Neigung:** Jedes Muster läuft um ~2° schräg zu den Schichten
  (helische Verschiebung — Naht bleibt perfekt, oben schließt es).
  Gerichtete Muster haben ihren eigenen Winkel (Korb 30°, Strick 3°);
  Seil/Riffel/Rinde/Facetten/Makramee/Planken richten sich selbst aus.
  Die Fertigmeldung sagt es: „[auto-tilt 2.0 deg]".
- **6 neue Muster (27 gesamt, Seite 4):** Strick (V-Maschen), Riffel
  (vertikal — killt Z-Banding), Rinde (vertikale Risse), Schuppen
  (dachziegelartig), Facetten (Rauten-Relief), Makramee (kreuzende
  Schnüre). **Planken laufen jetzt VERTIKAL.**
- **Bild als MAP:** Der Hintergrund wird erkannt (Otsu) und wie ein
  Alphakanal behandelt — dort GAR KEINE Verformung, weiche Übergänge
  (Haftung bleibt). Neu: **ONCE** = einmal komplett herum, seiten-
  verhältnis-echt, Position oben/mitten/unten (der freigestellte
  Hintergrund macht die Naht unsichtbar); **TILE** = endlos wie bisher.
- **Menü aufgeräumt:** Fuzzy-Zeilen nur im Fuzzy-Modus, Muster-Zeilen
  nur im Bumps-Modus.

**5) Zur Temp-Flut in der WebUI:** Im Paket existiert KEIN Absender
(komplette Prüfung: kein Loop druckt Temperaturen, M105/M155 kommen
nicht vor, im ganzen 3-h-Log war gcodein=0). Das klassische Bild ist
ein externer Dienst, der M105 pollt (z. B. ein alter OctoPrint im
Hinterstand — dann flutet es die Konsole mit T:-Zeilen). Prüfen mit
`sudo systemctl list-units --type=service | grep -i octo`. Wichtig:
Konsolen-Meldungen belasten die MCU NICHT (R235-Beweis) — es ist
nur Optik.

**6) R239 — „Druck lässt sich nicht starten" (Feldlog 2).** Fünfmal
`Malformed command 'EXCLUDE_OBJECT_DEFINE … POLYGON=[[137.3,111.5],
[137.3,110.9], …]'` — **Leerzeichen nach den Kommas** im Polygon.
Klippers Parameter-Parser (shlex) zerschneidet den Wert an
Leerzeichen → die Zeile stirbt als „Malformed" → Klippy landet im
Error-State → JEDER Start solcher Dateien schlägt fehl (und jede
Auswahl, weil der Watcher die Zeile zur Mesh-Vorbereitung nochmal
pusht). **Ursache: der MIRROR-Tool** hat das gespiegelte Polygon mit
`, `-Trennern neu geschrieben (Dein Verdacht war richtig!) — die
Textur-Dateien (BigRosMIR*) haben die Zeile geerbt. Drei Fixes:

- **Mirror schreibt kompakt** (die R87.2-Regel, die alle anderen
  Emitter schon einhielten).
- **Jeder Umschreiber heilt Alt-Dateien:** Segment-Fix, Textur,
  Auswahl-Replay und Range-Auszüge komprimieren `], [` → `],[`
  während sie die Datei ohnehin streamen.
- **Segment-Fix wird bei Spiral-Vasen wirksam:** Die alten Regex
  sah Z-tragende G1-Züge (Vasenmodus!) nicht und die 0,35-mm-Kette
  war zu kurz — 18 000 Moves/s blieben 18 000 (113 von einer halben
  Million Zügen gemerged). Jetzt: Z reitet mit, Ketten bis 128 Züge,
  begrenzt durch die **Sehnen-Abweichung ≤ 0,12 mm** (ein Fünftel
  der Linienbreite — flache Fluten mergen frei, wandernde Pfade
  stoppen).

**WICHTIG für bestehende Dateien:** Einmal **Segment fix** über jede
Mirror-/Textur-Datei laufen lassen (Pre-Print > File > Segment fix) —
das heilt das Polygon UND mergt die Mikrozüge. Danach startet der
Druck normal.

### Feld-Checkliste .136ai

- [ ] Eine alte Mirror-/Textur-Datei (z. B. BigRosMIR*) → Pre-Print >
      File > Segment fix → KEIN „Malformed command" mehr in der Konsole
      bei Auswahl UND beim Start → Druck beginnt normal
- [ ] Irgendeinen Generator laufen lassen → Konsole meldet bei riskantem
      Output „AUTO segment fix … merged" → Datei startet OHNE
      SegFix-Warnung im Dialog
- [ ] 2+ Jobs in die Queue → Hauptmenü über der SD-Karte:
      „Gen queue: 2 waiting" → „Skip job -> next" beendet den laufenden,
      der nächste beginnt; „Stop" räumt alles weg
- [ ] Pre-Print > File > STL → Ergebnis im Ordner STL als .stl.gcode →
      in Mainsail sichtbar + downloadbar, LCD-Klick erklärt
- [ ] Textur Korb/Strick/Seil auf eine Testvase → Muster läuft SCHÄG
      bzw. gedreht (nicht mehr schichtparallel), Fertigmeldung nennt
      „[auto-tilt … deg]"
- [ ] Textur Riffel/Rinde/Planken → Struktur läuft VERTIKAL
- [ ] Ein Logo (heller Hintergrund) als MAP → ONCE + Pos: top → Logo
      einmal herum oben, Hintergrund unangetastet, Naht unsichtbar
- [ ] `Macro system OK: all 19 modules loaded and current
      (build R2-2026-11-09.142a)`

**Alles grün?** Dann ist .136ai field-clear. Wenn etwas auffällt:
Konsole kopieren — daraus wird der nächste Feldlog-Eintrag.


## 25. Die .136aj-Neuerungen (R240 — Start-Blocker + Profil-Master-Runde)

**1) DER Start-Blocker ist gelöst.** Das .136ai-Feldlog zeigte 6×
`Malformed command '_M204_SET VALUE=8000'` direkt nach der Prime-Line —
danach „Printer reported an ERROR", kein Druck startete. Ursache bis auf
Klippy-Quellcode-Ebene: Der Dispatcher baut Befehlsnamen NUR aus [A-Z_] —
**Ziffern beenden einen Namen**. Unser eigener Makro-Name `_M204_SET`
(R167) wurde also als Befehl `_M204` mit Parametern `_SET VALUE=8000`
geparst; der R237-`_M204`-Alias fing ihn ab, shlex stolperte über das
Token `_SET` ohne `=` — fataler Fehler, pro Makro-Ebene einmal gemeldet
(6 Ebenen = 6 Zeilen). Vor R237 war dieselbe Zeile ein harmloses
„Unknown command". Jetzt: Makro heißt `_ACCEL_SET`, der Alias ist weg,
und beide Tools schreiben `_M204_SET VALUE=x`-Zeilen in alten Dateien zu
`M204 Sx` um. Die neue Batterie `r240_field_check.py` simuliert den
Klipper-Tokenizer über ALLE Makro-Namen — diese Fehlerklasse kann nicht
mehr einschleichen.

**2) EIN Depot-Profil, EIN Profil pro Datei.** Pre-Print > Profiles:
- **> Save > Depot** (Doppelklick) — speichert ALLE Pre-Print-Werte als
  das EINE zentrale Depot: Temperaturen, Retraction (Länge/Rück-/Vorschub),
  PA + Smooth-Time, Accel, Velocity, Min-Cruise + Square-Corner, Flow,
  Fan (inkl. min/max/bridge/clamp), Ironing-Flow, ALLE 25 Feature-Slots
  (Speed/Accel/Flow/PA), Shaper-off, Erstschicht-Tempo — und jetzt auch
  **Z-Hop (an/aus + Höhe) und den Extruder-Drive**. Werte UND Schalter,
  egal ob an oder aus.
- **> Save > file** — dasselbe komplette Snapshot als 'pre'-Profil der
  ausgewählten Datei (max. EINS pro Datei).
- **Load Depot / Load file-pre / Del Depot? / Del file-pre?** — alles
  Doppelklick mit Ton, die Zeile springt zurück, das Display zeigt das
  Ergebnis.
- Die 8 Default-Slots und die Material-Mini-Presets sind aus dem Menü
  Raus (Konsole bleibt: `LOAD_DEFAULT_PRESET N=1..8`); die Material-
  Schnellvorlagen (Laden/Speichern/Zurücksetzen) leben jetzt in
  **Pre-Print > Material**.
- Beim Datei-Auswählen mit Auto-Load ON: Bestätigungston + „Profile:
  loaded" — alle Werte stehen im Pre-Print-Menü.

**3) Der Optimierte-Fluss (Ranking-JA).** „Rate print?" -> JA:
wie gehabt Kopie in `optimized/` mit eingebackenen Werten — UND die
getunten Werte werden jetzt als **eigenes pre-Print-Profil der Kopie**
registriert (das neutralisierte Replay-Set: Prozente leben in der Datei,
Absolute bleiben). Die Kopie später auswählen = Auto-Load + Ton. Die
ORIGINAL-Datei behält ihr eigenes Profil: Vorher UND Nachher existieren
getrennt, nichts geht verloren, nichts wird ohne Dein JA gespeichert.

**4) Ironing-Schnellzugriff ist jetzt der FLOW.** Die starre 100-%-
Zeile wurde durch den echten Ironing-FLOW ersetzt (Default 15 %, Bereich
5–100 % — typisch 15–20 %), direkt steuerbar in Live > Motion >
Velocity > Spd/feat. Alle vier Ironing-Flow-Zeilen zeigen jetzt 15.

**5) Live spiegelt Pre-Print > Motion.** Die vier Schnelllisten
(Speed/Accel/PA/Flow je Feature) sitzen nicht mehr lose im Live-Menü,
sondern IN Live > Motion: Velocity (inkl. Feature-Geschwindigkeiten und
-Beschleunigungen), Extrusion (inkl. Feature-PA und -Flow), Retraction.
Die 32 Feature-Toggles wanderten aus der Datei-Info in ihre Feature-
Untermenüs (Pre-Print: Datei-Filter; Live: immer klickbar mit
„(parked)"). Z-Hop bleibt direkt über den Babysteps.

**6) LED-Fortschrittsbalken PRO Job.** Solange ein Watcher-Job arbeitet
(Generierung, Textur, Segment-Fix, optimierte Kopie), zeigen die Status-
LEDs einen grünen Balken für DIESEN Job — der nächste Job startet bei 0
(ein Gesamt-Queue-Balken würde lügen, sobald während des Laufens Jobs
dazukommen). Nach Job-Ende stellen sich die Status-LEDs wieder her
(idle/Printing wie zuvor). Gedrosselt auf ~1 Push/1,2 s, respektiert den
LED-Hauptschalter und die 0,5-Power-Cap-Regel.

### Field-Check .136aj

- [ ] Druck starten (eine normale Datei) → **kein** „Malformed command"
      mehr, Prime-Line kommt, Druck läuft an
- [ ] Pre-Print > Profiles > Save > Depot (2× drücken) → Ton, Anzeige,
      `DEPOT_INFO` in der Konsole listet Z-Hop + Drive
- [ ] Pre-Print > Profiles > Save > file → gleiche Zeremonie für die
      Datei; Datei abwählen/neu wählen → Auto-Load lädt mit Ton
- [ ] Z-Hop und Drive verstellen → Depot speichern → Depot laden →
      beide Werte sind zurück
- [ ] Ranking mit JA beantworten → Kopie in optimized/ + Konsole:
      „now has its own pre-print profile" → Kopie auswählen → Werte
      kommen mit Ton
- [ ] Live > Motion > Velocity > IR-Zeile: „IR fl: 15%" — drehen ändert
      den Ironing-Flow (nicht mehr die Speed)
- [ ] Einen Generator-Job starten (z. B. Kabelbinder) → LED-Balken
      füllt sich grün, am Ende stellen sich die Status-LEDs zurück
- [ ] Gen queue > Stop (2× drücken!) → diesmal REALLY Doppelklick:
      erster Druck „Gen: stop?", zweiter beendet
- [ ] `Macro system OK: all 19 modules loaded and current
      (build R2-2026-11-09.142a)`

**Alles grün?** Dann ist .136aj field-clear. Wenn etwas auffällt:
Konsole kopieren — daraus wird der nächste Feldlog-Eintrag.

## 26. Die .137 (R241) — die saubere Versionsnummer

**.137 ist .136aj — nur die Nummer ist neu.** Gleicher Code, gleiche
Funktionen, gleiche Menüs: Die Buchstaben-Kette .136a… .136aj war im
Feld verwirrend („welche Version ist denn JETZT die aktuelle?"), also
startet hier die nackte Zahl. Der Update-Zähler (Odometer) ordnet sie
korrekt ein: **137 > 136aj** — die Zahl schlägt jeden Buchstaben, ein
Update von .136ai ODER .136aj auf .137 zieht ganz normal.

Was sich in .137 Wirklich ändert:

- **Versions-Strings:** State, Postproc-Kern (`core R2-2026-11-09.142a
  (R241)`), Manual, Web-UI-Badge (der zeigte lange .136ab — jetzt .137).
- **Batterie-Reparaturen für nackte Nummern:** r227/r234/r217/r218
  verlangten noch einen Buchstaben hinter der Zahl — seit .137 ist der
  Suffix optional (immer war er nur ein Add-on).
- **Web-UI:** Badge und State-ver (R241) wieder aktuell.

### Field-Check .137

- [ ] Update mit dem .137-Zip einspielen (über .136ai/.136aj: normal,
      ohne --force — der Zähler weiß, dass 137 > 136aj)
- [ ] `Macro system OK: all 19 modules loaded and current
      (build R2-2026-11-09.142a)`
- [ ] Web-UI öffnen: das Version-Kästchen oben zeigt **.137**
- [ ] Ein Druck starten → läuft an wie unter .136aj (Kapitel 25, Punkt 1)

**Alles grün?** Dann ist .137 field-clear. Wenn etwas auffällt:
Konsole kopieren — daraus wird der nächste Feldlog-Eintrag.

## 27. Die .138-Neuerungen (R242 — die Start-Fenster-Diät)

**Feldlog .137:** zweimal `MCU 'mcu' shutdown: Timer too close` — beide
Male mitten im **Homing** nach Datei-Auswahl, bei sauberen Dateien
(MAXRATE 12, gcodein=0). Das Klippy-Log zeigte die Ursache: Der Reactor
stand 0,54 s still (`Reactor busy for 0.541`), aufgebaut aus genau den
Lasten, die unser eigener Start-Window erzeugt:

1. **Der doppelte Preview-Push.** Jede Datei-Auswahl bumpte die
   `preview_nonce` zweimal (R62-Auswahl + R195-Dialog-Re-Peek) — der
   Watcher schickte das ~20-kB-Skript (zwei Riesen-Polygone + rohe
   `_FILE_INFO`) **zweimal** durch moonraker→webhooks→klippy, exakt
   während das Homing Moves plant. **Fix:** Der zweite Push wird
   übersprungen, wenn er nichts ändern kann — gleiche Datei, gleiche
   Größe+mtime, vorheriger Push bestätigt, und klippy hält die Werte
   noch (`_PREVIEW.name` = Datei — ein Neustart resettet das und der
   Push läuft wieder).
2. **Der fette Web-Poll.** Die Web-UI holte alle 3 s ~17 Objekte, darunter
   `save_variables` — das klippy als GANZES Variablen-Dict serialisiert
   (sd_tree, gen_files, Profile, Depot: 10–30 kB JSON pro Poll). **Fix:**
   10-s-Tier für save_variables + eine **Server-seitige Start-Diät**: ein
   Mini-Precheck (print_stats + _STATE) erkennt `waiting`/`starting` und
   fragt dann NUR die leichten Objekte (Temperaturen, Modus, Fortschritt)
   ab — der Rest kommt aus dem letzten Voll-Snapshot. Gilt jetzt auch für
   LCD-Starts (die R215-Ruhe der Web-Seite armierte nur bei ihren eigenen
   Befehlen).
3. **LED-Frames.** Die animierten Effekte liefen mit 6 fps = sechs
   Neopixel-Transfers pro Sekunde auf einer Leitung, die schon im Leerlauf
   Updates verliert (`Neopixel update did not succeed` — jede_FAILURE wird
   von klippy sofort retried = Reactor-Churn). Dauerlauf-Effekte jetzt
   3 fps (Boot bleibt 6, Drucken bleibt 5 — r164 bewacht das).
4. **Watchdog-Kadenz.** Der _WATCHDOG re-armte den _STATE_WATCHER alle 5 s
   auf 0,5 s — der Ticker lief dadurch ~20 % öfter als geplant. Jetzt
   konsistent 1 s.

**Was das NICHT heilt — die Seriell-Schicht ist Hardware:** Das Log zeigt
`bytes_retransmit` (verlorene Bytes Pi↔Board, auch bei kalten Heizern im
Leerlauf!) und einmal einen **Pi-Neustart um 09:22**. Bitte prüfen:

- [ ] USB-Kabel Pi↔Board: kurz, geschirmt, ggf. anderes Kabel + Ferrit
- [ ] Pi-Stromversorgung: kräftiges 5V-Netzteil; auf dem Pi:
      `vcgencmd get_throttled` (muss `0` sein) und `dmesg | grep -i usb`
- [ ] LED-Datenleitung: 330-Ω-Widerstand in Reihe, gemeinsame Masse
- [ ] Beim Drucker war um 09:22 ein Neustart des Pi — war der von Dir
      (Stecker/powercycle) oder kam er von allein? (Von allein = Strom)
- [ ] Alte Textur-/Mirror-Dateien (V04 hatte 6000 Moves/s!) vor dem Druck
      einmal durch **Segment fix** schicken — das ist die ANDERE
      Timer-too-close-Klasse ( Moves-Flut, Feldlog vom Vortag)

### Field-Check .138

- [ ] Datei am LCD auswählen → Konsole zeigt beim Dialog-Öffnen
      `[preview] …: identical re-peek within 120s - heavy push skipped`
      (einmalig, danach Ruhe) — statt zweier voller Pushes
- [ ] Druck starten (Homing) → **kein** `Timer too close` mehr; Web-UI
      darf dabei offen sein (Temperaturen im Dialog klettern live)
- [ ] `Macro system OK: all 19 modules loaded and current
      (build R2-2026-11-09.138)`
- [ ] LED-Atmung im Leerlauf läuft (etwas ruhiger als vorher, 3 fps)
- [ ] Web-UI-Badge zeigt `.138`

**Alles grün?** Dann ist .138 field-clear. Wenn trotzdem wieder ein
`Timer too close` kommt: sofort die Konsole + `klippy.log` sichern — dann
ist die Seriell-/Strom-Schicht der nächste Verdächtige (Checkliste oben).

## 28. Die .139-Neuerungen (R243 — der LED-Ready-Crash)

**Feldlog .138:** Nach dem Einspielen wurde der Drucker **nie wieder
bereit** — jede Klippy-Runde starb beim Aufwachen mit

```
Internal error during ready callback: division by zero
```

**Ursache (Traceback Zeile 111–123):** Die LED-Bibliothek baut jeden
Cylon-Sweep als `frames = int(Dauer × frame_rate)` Frames und
interpoliert sie mit `pct = frame / (frames − 1)` — die **einzige**
solche Division in der ganzen Bibliothek. Die R242-Diät senkte die
Dauerlauf-Raten von 6 auf 3 fps — dadurch schrumpfte
`r2_leveling`'s `cylon 0.6` von 3 Frames auf **eines**: `pct = 0/0` →
ZeroDivisionError im Ready-Callback → Klippy tot, bei jedem Start.

**Wichtig fürs Verständnis der Konsole:** Das 5–6-s-„Loop" im
Konsolenfenster war **kein** Klippy-Neustart-Loop (nur 2×
`Start printer` im Log). Es war der Postproc-Daemon, der seinen
sd_tree/gen_files-Boot-Push solange wiederholt, wie Klippy die
SAVE_VARIABLEs ablehnt — gewolltes Retry („push failed - retrying next
cycle"), das sich selbst heilt, sobald Klippy wieder bereit ist.

**Fix (nur Konfiguration, der Daemon ist unberührt):**

1. Beide Cylon-Layer auf **1.0 s**: 3 Frames bei 3 fps — über der
   Crash-Grenze UND ein sichtbarer Sweep (Scanner bleibt Scanner).
   `r2_homing` 0.8 s → 1.0 s, `r2_leveling` 0.6 s → 1.0 s.
2. Die .138-Seriell-Diät bleibt komplett erhalten (idle/waiting/heating/
   homing/leveling/pid 3 fps, Boot 6, Drucken 5).
3. **Neue Wache:** `r243_field_check.py` simuliert die Frame-Mathematik
   für **jeden Layer jedes Effekts** (`int(Dauer × rate) ≥ 2`, bewegte
   Layer ≥ 3) und reproduziert den Feld-Crash als Negativtest
   (`cylon 0.6 @ 3` **muss** raisen — sonst wäre die Wache blind).

### Field-Check .139

- [ ] Nach dem Flash: Drucker wird **bereit** (kein
      `division by zero`, LEDs zeigen die Idle-Atmung)
- [ ] Boot-Pushes des Daemons landen wieder (Konsole: `sd_tree`/`gen_files`
      nur einmalig, dann Ruhe — kein 5-s-Retry mehr)
- [ ] `Macro system OK: all 19 modules loaded and current
      (build R2-2026-11-09.139)`
- [ ] Homing → Cyan-Sweep sichtbar (1 s pro Durchlauf, 3 Stufen)
- [ ] Bed-Mesh/Leveling → Magenta-Scanner sichtbar (1 s pro Durchlauf)
- [ ] Web-UI-Badge zeigt `.139`
- [ ] Danach: die offenen Feldfragen aus Kapitel 27 (Pi-Neustart 09:22,
      Hardware-Checkliste, Segment-Fix für alte Textur-Dateien)

**Alles grün?** Dann ist .139 field-clear und die .138-Diät endlich im
Feld gültig. Wenn wieder etwas stirbt: Konsole + `klippy.log` sichern.

## 29. Die .140-Neuerungen (R244 — Auto-Recovery)

**Anlass (.139-Feldlog, 10. Nov 15:12):** Wieder `MCU 'mcu' shutdown:
Timer too close` am Homing-Ende nach Datei-Auswahl — diesmal eine
Textur-Datei mit **14746 Moves/s** (die markierte SegFix-Klasse; das
System hatte bei der Auswahl gewarnt: `MCU risk - SegFix!`).

**Dein Wunsch:** „Wenn ich den Drucker immer über die Klipper-Oberfläche
neu starten kann, musst DU den MCU-Shutdown auch erkennen können —
erst die Firmware resetten, dann notfalls das ganze System neu starten."

**Die Antwort ist der Watcher:** Klippy kann sich nicht selbst heilen
(es IST der Patient) und Moonraker startet einen abgeschalteten Klippy
bewusst nie neu. Aber der Watcher ist ein unabhängiger Prozess mit
exakt derselben Moonraker-API, die auch die UI-Buttons nutzen.

### Die Eskalationsleiter (alles im Watcher, `_recovery_tick`)

| Stufe | Wann | Aktion |
|---|---|---|
| **L1** | 10 s nach erkanntem Shutdown (2 Versuche) | `FIRMWARE_RESTART` — wie der UI-Button: MCU-Reset + Config-Reload |
| **L2** | nach 90 s tot | Klipper-Dienst-Neustart über Moonraker (`/machine/services/restart`) |
| **L3** | nach 210 s tot — oder sofort ab der 3. Wiederholung in 15 min | **Kompletter Pi-Reboot** über Moonraker (`/machine/reboot`), max. 1×/Stunde |

**Sicherheiten:**
- Nur **`Timer too close` / Kommunikationsverlust / Missed-scheduling**-
  Klassen werden automatisch geheilt (Host- und Link-Probleme; die
  Heißungen sind im MCU-Shutdown ohnehin aus). Heizungs-/Thermal-/
  Config-Shutdowns bleiben bewusst unten — die brauchen Augen, keine
  Restart-Schleife.
- Der L3-Reboot-Zähler steht in `watcher_recovery.json` (überlebt den
  Reboot selbst) — ein Crash-Reboot-Crash-Loop bremst sich so selbst.
- **Vor** dem ersten Restart wird `klippy.log` nach
  `crash_archive/` gesichert (max. 7 Snapshots, älteste fliegen raus)
  — die Beweise überleben jede Rotation und sind im SD-Browser sichtbar.
- Nach erfolgreicher Heilung: `RESPOND MSG="[i] R2 auto-recovery:
  printer back after Xs …"` in der Konsole.

**Schalter:** `SET_RECOVERY MODE=on|off` oder am LCD
**System > MCU Recovery** (Standard: AN). Der Watcher liest die Flagge
aus der Variablen-**Datei** — kein Makro kann laufen, während Klippy
tot ist.

### Field-Check .140

- [ ] Boot: `Macro system OK: all 19 modules loaded and current
      (build R2-2026-11-09.140)`
- [ ] Konsole: `SET_RECOVERY` (ohne MODE) zeigt den aktuellen Modus
- [ ] LCD: System > MCU Recovery zeigt `ON`, Toggle auf `OFF` und
      zurück funktioniert (Konsole bestätigt jeweils)
- [ ] Web-UI-Badge zeigt `.140`
- [ ] (Nur wenn es erneut kracht:) Konsole zeigt
      `[recovery] klippy SHUTDOWN detected …`,
      `[recovery] klippy.log snapshot -> …/crash_archive/…`,
      `[recovery] L1: sending FIRMWARE_RESTART` — und danach
      `[i] R2 auto-recovery: printer back after …s`
- [ ] `crash_archive/` im SD-Browser: nach einem Vorfall liegt dort
      das Log des Absturzes

**Alles grün?** Dann ist .140 field-clear. Und weiterhin offen aus
Kapitel 27/28: Pi-Neustart 09:22 (Strom?), Hardware-Checkliste, und
**Segment fix vor dem Druck** für die alten Textur-Dateien
(BigRosMIRmyChecker3 hatte 14746 Moves/s — 33× über dem MCU-Budget von
~450/s; das System warnt davor, aber drucken solltest Du erst nach
SegFix).

## 30. Die .141-Neuerungen (R245 — erst parken, dann feiern)

**Feldlog .140 (10. Nov, 18:14):** Der 1h15m-Texturdruck lief durch — und
eine Sekunde nach `PRINT DONE` starb der MCU an `Timer too close`. Die
Fertig-Melodie brach nach dem ersten Ton ab, und die Düse stand noch auf
dem Teil. (.140s Auto-Recovery hat den Drucker nach 100 s zurückgebracht —
erste produktive Rettung, Snapshot liegt in `crash_archive/`.)

**Ursache (zwei Schichten):**
1. **Falsche Reihenfolge:** `PRINT_END` lief Stats → LED → Melodie →
   Lüfter → Heater → Cleanup — und parkte den Kopf **zuletzt**. Die Düse
   saß die ganze End-Choreografie über auf dem fertigen Teil.
2. **Der Stall-Treiber im selben Fenster:** `_OPT_END_CAPTURE` lief als
   ERSTES — seine `SAVE_VARIABLE`s sind synchrone SD-Schreibvorgänge auf
   die variables.cfg, mitten im Klippy-Reactor (R216b-Klasse, bis 1,9 s
   Stillstand pro Schreibvorgang), während die letzten Moves der
   14746-Moves/s-Datei noch ausliefen.

**Fix — die neue PRINT_END-Reihenfolge:**

1. Sicherheits-Restores (PA/Shaper, rein In-Memory)
2. State-Cleanup (In-Memory; der R160b-Schutz „verweigerte Fahrt kann
   nichts verkeilen" bleibt erhalten)
3. **Präsentationsfahrt: Z+15 mm, Kopf zur Seite** — die Düse verlässt
   das Teil als erstes
4. Stats → Opt-Capture (SD-Schreibvorgänge) → LED → **Melodie** →
   Lüfter/Heater → Motoren aus (verzögert) → Mesh-Persistenz

Ab Schritt 3 ist die Move-Queue leer — jeder spätere Reactor-Stall
(auch die SD-Schreibvorgänge) kann dem MCU nichts mehr anhaben. Die
Fertig-Melodie spielt nur noch für ein **präsentiertes** Teil.

**Gleich mitgefangen (Review-Fund):** `_PRINT_CLEANUP` resettet `layer`
— die Stats hätten danach „layers: 0" gedruckt. Der Layer-Zähler wird
jetzt vor dem Cleanup eingefangen (R174-Klasse bleibt tot).

### Field-Check .141

- [ ] Boot: `Macro system OK: all 19 modules loaded and current
      (build R2-2026-11-09.142a)`
- [ ] Druck enden lassen → **zuerst** fährt der Kopf hoch/zur Seite,
      **dann** kommt die Melodie — die Düse steht nie auf dem Teil
- [ ] `Duration: … | layers: NNN` zeigt die echte Layer-Zahl (nicht 0)
- [ ] Kein `Timer too close` im Endfenster; Web-Badge `.142`
- [ ] Wenn doch mal ein Vorfall: `crash_archive/` füllt sich, die
      Auto-Recovery meldet sich (Kap. 29)

**Offen (nächstes Kapitel der Ursachenjagd):** Das `crash_archive/`-Log
des 18:14-Vorfalls (SD-Browser → crash_archive → mcu-*.log oder 3-h-
Export) zeigt die exakte Stall-Komposition — bitte mitschicken.

## 31. Die .142-Neuerungen (R246 — Shutdowns endgültig beseitigen: der RAM-Spiegel)

**Diagnose des Nutzers, bestätigt:** Die drei Shutdowns vom 10. Nov
(18:14 Druckende, 18:57 Datei-Auswahl, 19:52 Druckstart-Klick) lagen an
Dateien, die immer einwandfrei druckten — der gemeinsame Faktor war der
**Host**: 17:19 „host memory low (49MB free) … RESTART OF THE PI frees
swap". Jeder der drei Momente saß auf einem synchronen `SAVE_VARIABLE`,
das die GESAMTE variables.cfg in klippys Reactor neu schreibt — und
unsere trug die rekonstruierbaren Riesen (sd_tree ~200 Einträge,
sd_view, gen_files, opt_list, litho_*). `.141` hat nur das Endfenster
gefixt — `.142` nimmt die Last komplett raus.

**Der Umbau (vom Nutzer bestellt):** Alle Spiegel-Daten wohnen jetzt in
einem eigenen Makro `_SDM` (01_state.cfg) — `SET_GCODE_VARIABLE`
schreibt in RAM, nie auf Disk. Der Watcher liest Pfad/Seite LIVE aus
dem Objekt (eine Moonraker-Query, Datei nur als Fallback), pusht
sd_tree/sd_view/gen_files/opt_list/litho_* dorthin — die variables.cfg
schrumpft auf echte Persistenz (Profile, Schalter, Einstellungen).
Menüs lesen `printer['gcode_macro _SDM'].…` statt
`printer['save_variables'].variables.…` (619 Stellen umgezogen).

**Weiter in der Runde:**

- **crash_archive raus aus dem LCD-Browser** (leerer Forensik-Ordner,
  der die Navigation festsetzte) — die WebUI bekommt dafür den
  **`crash`-Knopf** neben `klippy.log`: neuester mcu-Snapshot als .txt
  per Klick (Endpoint `/server/r2_menu/crashreport`).
- **Ambient-LED-Rahmen** um die WebUI-Seite: zeigt ungefähr die
  LED-Stimmung des Druckers als sanften Leuchtrahmen — bewusst
  verzögert aus dem Status-Poll, NICHT synchron.
- **Laden sichtbar:** Der SD-Index-Scan meldet sich einmal pro
  Baum-Änderung: „SD index ready: N entries in X.Xs".
- **Die Paging-KLASSE gefixt:** Klippers Menü wertet enable-Templates
  nur beim (Neu-)Betreten eines Containers aus — Namen rendert es
  live in jedem Frame. Die 27 Textur-Pattern-Slots (je Seite per
  enable eingefroren) wurden zu 8 Zeilen, die die Liste live im Namen
  slicen (neues Makro `_TX_PATTERN`: Seiten-Mathe + Speichern + die 27
  Info-Texte an einem Ort). Die 6 litho-Page-Turner verloren ihre
  enable-Zeilen (ihre Namen zeigen den Zustand schon live). Batterie-
  Schutz: JEDE enable-Zeile, die an einer `*_page`-Variablen hängt,
  lässt den Rendertest jetzt scheitern.

### Hotfix .142a (R246b — das Feldlog vom ersten Abend)

**Was passierte (10. Nov, abends):** Beim Start des Bilderrahmens
starb der MCU nach dem Homen an `Missed scheduling of next digital
out event` — und zeitgleich war der klippy.log-Download über die
WebUI angeklickt worden. Der Export las die GESAMTE klippy.log in
den RAM (mittlerweile 20+ MB — pro Neustart ein kompletter
Config-Dump) — auf einem Pi im Swap eine **RAM-Bombe**: Der Host
fror komplett ein (beide WebUIs weg, LCD weg), und der stehende
Host lieferte die Probe-Enable-Pin-Events nicht mehr → Shutdown.
Die Auto-Recovery holte den Drucker nach 178 s zurück (zweite
produktive Rettung).

**Drei Fixes in .142a:**

1. **klippy.log-Export liest nur noch die letzten 6 MB** — die
   Beweise (Fehler, Shutdowns) stehen immer am Dateiende, der
   Anfang ist ohnehin Config-Geschichte. Der Download kann den
   Host nicht mehr in den Swap treiben.
2. **crash-Export liest die letzten 3 MB statt der ersten** — die
   beiden heruntergeladenen Snapshots waren byte-identisch
   (gleiche md5!), weil der alte Cap den historischen Präfix
   lieferte und die Absturz-Beweise abschnitt.
3. **LCD-Spiegel-Refill nach Klippy-Restart** — nach der Recovery
   zeigte der SD-Browser dauerhaft `(0 entries in /)`: Der `_SDM`-
   Spiegel ist RAM und starb mit Klippy mit, während die Daemon-
   Push-Caches noch glaubten, schon gepusht zu haben. Der Watcher
   erkennt jetzt den leeren Live-Spiegel (eine Flagge in der
   ohnehin laufenden Query), verwirft alle Spiegel-Caches und
   füllt innerhalb eines Scandurchlaufs wieder auf.

- [ ] klippy.log-Download klappt auch bei großem Log schnell (kein
      Einfrieren des Hosts mehr)
- [ ] Nach einem Absturz + Auto-Recovery: SD-Browser füllt sich von
      allein wieder (kein „0 entries")
- [ ] crash-Download zeigt den NEUESTEN Vorfall am Dateiende
      („Transition to shutdown" sichtbar)

### Field-Check .142

- [ ] Boot: `Macro system OK: all 19 modules loaded and current
      (build R2-2026-11-09.142a)`
- [ ] Nach dem Boot: Konsole zeigt `SD index ready: N entries in X.Xs`,
      der LCD-SD-Browser füllt sich von allein
- [ ] **variables.cfg bleibt klein** — beim Ordner-Umräumen/Blättern
      wächst sie NICHT mehr (vorher: jeder Klick schrieb den Baum)
- [ ] Textur → Pattern: `Page >` blättert und die Zeilen wechseln
      SOFORT (ohne raus+rein); `*` markiert das gewählte Pattern
- [ ] Lithophane-Bilder: `<< / >>` blättern sofort, „(first page)"/
      „(last page)" erscheint live
- [ ] crash_archive erscheint NICHT mehr im LCD-Browser; WebUI-Knopf
      `crash` lädt den neuesten Snapshot als .txt
- [ ] LED-Rahmen der WebUI folgt grob dem Drucker (Druck = blauer
      Puls, Heizung = orange, fertig = grün, Alarm = rot)
- [ ] Ausgewählte Datei drucken → Druck startet ohne `Timer too close`
      (der Startklick schreibt keinen Baum mehr auf Disk)
- [ ] Shutdown-Freundesdienst: sollte doch mal einer passieren —
      Snapshot + Auto-Recovery wie in Kap. 29, und der `crash`-Knopf
      hat den Bericht parat
