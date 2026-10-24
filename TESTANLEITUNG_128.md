# FELDTEST .128 (R169) — Testanleitung

Diese Runde bringt **„Rate print?"** (die Frage nach dem Druck), den Ordner
**`optimized/`** mit nicht-invasiven optimierten Kopien und den Zugang darauf
im Menü. Die .127-Punkte (Stempel/Konturen/Spiegel, leere Feature-Menüs)
stehen weiterhin drin (TESTANLEITUNG_127.md).

Vor dem Testen: .128-ZIP wie immer hochladen, `bash klipper-e3-r2d2/update.sh`
per SSH. Am Ende muss stehen:
`post-processor reports build 'R2-2026-10-22.128 (R169)'` UND
`Macro system OK ... (build R2-2026-10-22.128)`.

**Wichtig vorab:** einmal in Mainsail prüfen, dass ein Ordner
`optimized/` unter den G-Code-Dateien auftaucht (er entsteht beim ersten
optimierten Druck — vorher existiert er nicht, das ist ok).

---

## A) Die .127-Punkte (weiterhin gültig, unverändert)

Siehe TESTANLEITUNG_127.md — Stempel/Griff-Snap, Kontur-Modi, Mirror,
Custom/Overhang/InternalBridge/PrimeTower-Menüs.

## B) NEU: Die Frage „Rate print?"

### B1. Frage erscheint NUR bei Live-Tuning
1. Irgendein known file starten, **nichts** tunen, Druck durchlaufen lassen.
2. Nach dem Druckende: **keine** Frage, Display macht wie immer weiter
   („Done: …"), Pre-Print > Alle Werte unverändert.
   → Erwartung: kein Menüeintrag „Rate print?" auftauchen (ggf. in der
   Menüliste nachsehen — er darf nur bei getuntem Druck da sein).

### B2. JA-Weg: optimierte Kopie (der Kern-Test)
1. Druck starten und **live tunen**: z. B. PA +0.01, Flow 98 %, Outer Wall
   Speed 90 % — mind. 2 Werte ändern.
2. Druck ENDE abwarten. Nach ~12 s erscheint auf dem Display
   `Rate print? - menu 'Rate print?'` und im Menü oben der Eintrag
   **Rate print?** (mit der Zahl der getunten Werte).
3. **> YES - optimized copy** drücken.
4. Konfirmations-Sound, Display `Optimized: saved`, Konsole:
   `[opt] optimized copy saved: <name> (N values, baked: PA, flow, …)`.
5. **Beweise** (Mainsail/SSH):
   - Ordner `optimized/` enthält die Datei mit **gleichem Namen**.
   - **Original byte-identisch:** `md5sum` vor/her gleicher Wert (vor dem
     Druck notieren!) bzw. `diff` original vs. Kopie zeigt NUR die
     eingefügten Zeilen (`; R2-OPT …`, `; R2-OPT baked: …`, `_OPT_BAKED …`,
     veränderte `_FILE_INFO`-Zeile).
   - In der Kopie: `_FILE_INFO` trägt jetzt `OPT=1` und die gebackenen
     Werte (PA 0.0x, FLOW_RATIO skaliert, FS_WALL_OUTER skaliert …).
   - Zeile `; R2-OPT optimized copy - source: <pfad> - <datum> - R2 …`.
   - Zeile `_OPT_BAKED SNAP="{…}"` (Prozent-Sachen fehlen darin: flow_on
     False, kein speed_pct).
6. Pre-Print: die getunten Werte **bleiben** stehen (bei JA wird nichts
   zurückgesetzt).

### B3. NEIN-Weg: spurlos
1. Nochmal drucken (gleiche oder andere Datei), live tunen.
2. **> NO - discard** drücken.
3. Konsole: `[opt] baseline restored`, Pre-Print zeigt exakt die Werte von
   **vor** dem Druck (auch die, die man während des Drucks nicht angerührt
   hatte — Stichprobe Material, FMin/FMax).
4. Kein Ordner-Inhalt dazu, kein Job (Konsole des Postproc: kein
   `[opt] copy`).

### B4. Timeout-Weg: still wie NEIN
1. Drucken, tunen, Frage erscheinen lassen — **nichts drücken**.
2. Nach 90 s: Frage verschwindet von selbst, `[opt] timeout` in der
   Konsole, Baseline wiederhergestellt (wie B3).
3. Variante: Frage offen lassen und **neuen Druck starten** (oder neue
   Datei wählen) → Frage wird sofort aufgelöst (Timeout-Pfad), Start
   läuft normal durch.

### B5. Abbruch schreibt nie
1. Druck starten, tunen, dann **Cancel** (Pause > Cancel print).
2. Keine Frage, kein Restore-Log nötig (Baseline wird trotzdem
   zurückgestellt — Konsole kann `[opt] baseline restored (quiet)` zeigen),
   **kein** neuer Eintrag in `optimized/`.

## C) NEU: Mit der Kopie arbeiten

### C1. Datei-Info erkennt die Kopie
1. `Optimized`-Menü > Nummer wählen > Datei **START** (Startdialog wie
   immer → bestätigen).
2. Vor dem Start: Pre-Print > File info zeigt die Zeile
   **OPTIMIZED - tuned values baked** (statt der rohen Slicer-Werte),
   Werte = die gebackenen.
3. Alternative: in **Mainsail** die Datei aus `optimized/` direkt starten
   (der Ordner ist dort ganz normal sichtbar).

### C2. Replay: Kopie druckt mit den Werten
1. Kopie drucken (aus C1), dabei **nichts** tunen.
2. Während des Drucks prüfen: PA/Flow/Speed entsprechen den gebackenen
   Werten (Live-Tuning-Anzeige), NICHT nochmal Prozent obendrauf
   (Flow darf nicht 98 % × 98 % sein!).
3. Druckende: da nichts NEUES getunt wurde → **keine** neue Frage (B1).

### C3. E2: Werte ohne Druck übernehmen
1. Pre-Print > Profiles > **From optimized**: Nummer der Kopie wählen,
   Klick.
2. Konsole `[opt] values of <name> applied to Pre-Print`, Display
   `Opt values: <name>`.
3. Pre-Print zeigt die Kopie-Werte als **Ausgangslage** (weiter änderbar,
   nichts wurde in irgendeine Datei geschrieben).

### C4. Zweite Chance: Save last print
1. Einen getunten Druck mit **Timeout** laufen lassen (B4).
2. Danach (Ruhezustand): Pre-Print > Profiles > From optimized >
   **Save last print > optimized**.
3. Kopie entsteht wie in B2 (dieselbe Beweis-Liste).

## D) Randfälle

1. **Gleicher Dateiname aus anderem Unterordner:** zwei Dateien
   `Test/vase.gcode` und `vase.gcode` je optimieren → die zweite Kopie
   heißt `Test_vase.gcode` (Präfix = Unterordner), keine Überschreibung
   der falschen Datei.
2. **Erneut optimieren:** dieselbe Datei nochmal drucken, anders tunen,
   JA → Kopie wird **überschrieben** (neueste Runde gewinnt).
3. **Alte post-Profile:** eine Datei mit altem `post`-Eintrag wählen →
   Auto-load lädt nur **pre** (falls vorhanden), post bleibt über die
   Buttons ladbar/löschbar. Der Schalter „Auto-save post" ist weg.
4. **Fremd-Datei ohne _FILE_INFO:** eine solche Datei optimieren → Kopie
   bekommt eine kleine `_FILE_INFO OPT=1 …`-Zeile + Replay-Block an der
   ersten Befehlszeile.

## E) Beweis-Block (SSH, einmal pro Testrunde)

```bash
# Build-Stände
grep -o "R2-2026-10-22.128.*" ~/printer_data/logs/klippy.log | head -2
grep "post-processor reports build" ~/printer_data/logs/* -r | tail -2
# Original unangetastet (vor/nach vergleichen)
md5sum ~/printer_data/gcodes/<original>.gcode
# Kopie vs. Original: nur die eingefügten/geänderten Zeilen
diff ~/printer_data/gcodes/<original>.gcode \
     ~/printer_data/gcodes/optimized/<original>.gcode | head -20
```

Erwartung im diff: nur `_FILE_INFO`-Zeile (verändert), `; R2-OPT …` (2×),
`_OPT_BAKED …` — sonst **nichts**.
