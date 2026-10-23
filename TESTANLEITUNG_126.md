# FELDTEST .126 (R167) — Testanleitung

Diese Version ändert Dinge, die man nur am Drucker wirklich beweisen kann.
Die Checkliste sagt dir bei jedem Punkt: **was du tust, was passieren muss,
und welche Datei ich brauche, wenn es nicht passt.**

Vor dem Testen: .126-ZIP wie immer in den Config-Ordner hochladen,
`bash klipper-e3-r2d2/update.sh` per SSH laufen lassen. Am Ende muss stehen:
`post-processor reports build 'R2-2026-10-22.126 (R167)'` UND
`Macro system OK ... (build R2-2026-10-22.126)`.

---

## 1) Rückwand-Passung (der Hauptpunkt)

1. Einen Bilderrahmen generieren (z. B. 10x15, wie immer).
2. Rahmen **und** Rückwand drucken (bei 10x15: Datei A und Datei B).
3. Foto einlegen, Rückwand in die hintere Öffnung legen und **mit einem
   Finger** andrücken.

**Passiert sein muss:** die Platte fällt von selbst fast durch, leichtes
Widerstehen an den 4 Nubs, und mit sanftem Druck **klickt** sie hinter den
Nubs ein. Keine Kraft, der Rahmen darf sich nicht wölben. Sie darf nicht
von selbst herausfallen (Kopfüber-test über dem Bett).

**Wenn sie durchfällt oder klemmt:** Maßnahme mit dem Lineal nehmen —
wie weit die Platte in X und Y in die Öffnung eingelassen sitzt (wieviel
Luft sieht man an einer Seite), und mir sagen. Die Geometrie ist jetzt
0,35 mm/Side Spiel — wenn dein Drucker anders extrudiert (Überextrusion),
sage ich das Spiel auf deinen gemessenen Wert.

## 2) Lithophane-Stufenkanten

1. Litho FLAT neu generieren (V-Nummer steigt), drucken.
2. Ab Stufe 2 (zweite Graustufe) müssen die Stufenflächen eine **saubere
   Umrandung** haben — keine ausgefransten Hatch-Enden mehr.

**Wenn fringe:** Foto des Drucks aus 45° von schräg oben.

## 3) MCU-Shutdowns (Druck-Ende und Schicht 2)

1. Den Litho-Testdruck komplett durchlaufen lassen — **besonders die
   letzten 30 Sekunden und den Moment nach „Done“** beobachten.
2. Danach einen Bilderrahmen drucken,ebenfalls bis zum Ende.

**Passiert sein muss:** kein einziger Timer-too-close, auch nicht beim
Beenden. Die Konsole darf während des Drucks **keine M204-Spam-Zeilen**
mehr zeigen (nur noch vereinzelt welche bei Feature-Wechseln).

**Wenn trotzdem ein Shutdown kommt**, brauche ich GENAU diese drei Dinge:

```
ssh pi@<drucker-ip>
sudo cp ~/printer_data/logs/klippy.log ~/klippy_copy.log && sudo chmod 644 ~/klippy_copy.log
journalctl -u r2-postproc -n 300 --no-pager > ~/watcher_log.txt
top -b -n 1 > ~/top_snapshot.txt
```
Diese drei Dateien (klippy_copy.log, watcher_log.txt, top_snapshot.txt)
hochladen. Im klippy.log steht die Send-Queue zum Shutdown-Zeitpunkt —
das ist der Fingerabdruck der Ursache.

## 4) Lüfter live (Live Tuning > Temps & Fan)

Während eines Drucks (ab Schicht 2), der Lüfter läuft:

1. `FMin` auf 60 stellen → **sofort** muss der Lüfter hochgehen (nicht erst
   bei der nächsten Schicht).
2. `FMax` auf 30 stellen → sofort runter.
3. `FBrdg` auf 100 stellen → beim nächsten Bridge-Abschnitt (oder einer
   Druckdatei mit Bridges) springt der Lüfter beim Bridge-Start hoch und
   am Bridge-Ende zurück auf den Dateiwert — Meldung „[Fan] BRIDGE boost“.
4. `Fan %` (Skalierung) ändert den Dateiwert anteilig — sofort.

**Wenn nichts passiert:** die Konsolen-Meldung notieren, die beim Einstellen
kommt, plus `PARAM_SOURCES` in der Konsole ausführen und mir den Output
geben.

## 5) Retraction (Pre-Print > Velocity > Retraction)

1. Bei laufendem Druck (G10/G11-Datei, also Litho/Frame/Labels):
   retract length z. B. auf 1,5 stellen → **sofort** müssen sich die
   weiteren Retracts ändern (hörbar/konsole: `SET_RETRACTION from file`
   gibt es bei generierten Dateien nicht mehr — der Wert greift direkt).
2. Stringing-Vergleich: gleiche Datei zweimal, einmal 0,4 mm, einmal
   2,5 mm retract — der Unterschied muss sichtbar sein.

**Wenn nicht:** `SET_LIVE_RETRACTION`-Echo + die Werte aus
`PARAM_SOURCES` schicken.

## 6) Düsenreinigung

Beim nächsten Druckstart: Der Wipe-Zickzack auf dem Pad muss **schnell und
knackig** sein (gleichbleibend, egal was der Druck davor hinterlassen hat).

## 7) LED beim Druck

Langsames blaues Atmen (4 s Periode) — bewusst langsam. Das ist das
Serial-Budget (5 msg/s ≈ 1 %). Wenn du es schneller willst, sagen —
mehr ist Budget-mäßig drin, aber jede Erhöhung kostet headroom.

---

## Was ich im Zweifel immer brauche

- `klippy.log` (nach einem Shutdown, Pfad s. oben)
- `journalctl -u r2-postproc -n 300 --no-pager`
- Die ersten **5 Zeilen** der problematischen G-Code-Datei
  (steht der `core R2-2026-10-22.126 (R167)`-Stempel drin?)
- Konsolen-Verlauf (copy & paste des Zeitfensters)
- Ein Foto vom Ergebnis (Platte/Stufen/etc.)

Mit diesen Daten kann ich jedes noch offene Problem eingrenzen, ohne
im Dunkeln zu raten.
