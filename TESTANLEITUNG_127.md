# FELDTEST .127 (R168) — Testanleitung

Diese Runde bringt **Stempel-Modus, Konturen, Spiegel** (Litho + Labels) und
füllt die vier leeren Feature-Untermenüs. Die .126-Punkte stehen weiterhin
drin (unverändert), die neuen Punkte dazu.

Vor dem Testen: .127-ZIP wie immer hochladen, `bash klipper-e3-r2d2/update.sh`
per SSH. Am Ende muss stehen:
`post-processor reports build 'R2-2026-10-22.127 (R168)'` UND
`Macro system OK ... (build R2-2026-10-22.127)`.

---

## A) Die .126-Punkte (weiterhin gültig, unverändert)

1. **Rückwand-Klick-Test** — ein Finger, kein Wölben, Kopfüber-Haltetest
   (Details: TESTANLEITUNG_126.md Punkt 1).
2. **Litho-Stufenkanten sauber** (Punkt 2 dort).
3. **Keine Shutdowns** am Ende + Schicht 2, keine M204-Flut (Punkt 3 dort).
4. **Fan live** (FMin/FMax sofort, FBrdg an Bridge-Grenze) (Punkt 4).
5. **Retract live sichtbar**, **Wipe knackig** (Punkte 5–6 dort).

## B) NEU: Stempel (Litho FLAT)

1. `Tools > Lithophane`: ein Foto wählen, **Orient FLAT**, **Stamp ON**,
   **Mirror X ON**, **Handle 1**. Generieren (2× drücken).
2. Es entstehen **zwei Dateien**: `Vnn_Stempel_<name>.gcode` (wird
   automatisch ausgewählt) und `Vnn_Griff_<name>.gcode`.
3. Beide drucken (PLA ist ok; der Griff braucht keine Sonderbehandlung).

**Passiert sein muss:**
- Im Stempel-Boden sitzt eine runde Öffnung mit einem kleinen Ring
  (die Lippe) — sauber gedruckt, kein Sagging an der Deckel-Brücke.
- Der Griff-Schaft (Hülse mit Nut) druckt gerade, der Knauf ist gefüllt.
- **Passung:** Griff von unten in den Sockel drücken → er rastet hörbar/
  fühlbar ein (Snap), sitzt fest, wackelt nicht, lässt sich mit Absicht
  aber wieder herausziehen. Beim Stempeln (fest aufdrücken auf Knet/Kaugummi/
  Seife) darf sich nichts lösen.
- Der Abdruck liest sich **richtig herum** (deshalb Mirror X).

**Wenn er klemmt oder durchfällt:** nicht feilen! Mir sagen wie stark
(leichtes Klemmen / gar nicht rein / fällt von selbst raus) — der Wert
`StampFit` (LCD) verstellt das Spiel gezielt (0.10–0.50 mm), und die Geometrie
wird vom Generator gemessen, ich kann sie also exakt auf deinen Drucker
verschieben. Falls etwas ganz daneben ist: die **ersten 40 Zeilen** beider
Dateien hochladen (da stehen die FIT-Kommentarzeilen drin).

## C) NEU: Konturen (Litho FLAT)

1. `Contour 2` (Kontur-Relief) auf ein Foto mit klaren Kanten (z. B. Ring/
   Logo): Generieren, drucken.
2. `Contour 1` (letzte Schicht nur Kontur): Generieren, drucken.

**Passiert sein muss:**
- Kontur-Relief: eine **geschlossene Grundplatte**, darauf die Umrisse der
  Stufen als erhöhte Linien — je dunkler, desto höher. Bei einem Ring muss
  **auch die Innenseite** eine Kontur haben (außenrum UND innenrum, genau
  wie besprochen).
- Letzte-Schicht-Modus: die oberste Schicht zeigt nur noch die Konturlinien
  der dunkelsten Stufe, keine Füllfläche.

**Wenn Konturen fehlen oder überlappen:** Foto des Drucks von oben.

## D) NEU: Labels spiegeln / Label-Stempel

1. `Labels > Settings > Mirror X ON`, ein kurzes Wort (z. B. STEMPEL),
   generieren, drucken → das Textbild muss **seitenverkehrt** sein.
2. `Stamp ON` + `Handle 1` (genau EIN Label im Job, Loch aus) → Label-Stempel
   mit Sockel + Griff-Datei. Gleicher Snap-Test wie B.

## E) NEU: Features-Untermenüs (der .126-Fehlerbericht)

Während eines beliebigen Drucks: `Live Tuning > Features > Custom Code` —
vorher stand da **nichts drin**, jetzt müssen die sechs Punkte
(On / File / Spd / Flow / Acc / PA) drinstehen, genau wie bei Outer Wall.
Gleiches gilt für **Overhang Wall, Internal Bridge, Prime Tower**.

## F) Dein .126-Fehlerbericht: Aussenwand = CUSTOM (Textur → Range → Floor)

Ich konnte die Kette in der Sandbox **nicht** reproduzieren — alle 13
Slicer-Dialekte, mit und ohne Textur, mit und ohne Travel-Fix, bleiben
sauber (WALL-OUTER bleibt WALL-OUTER). Bewiesen ist schon: das Texturing-Tool
fasst `;TYPE:`/`APPLY_TYPE` nie an, und das leere Custom-Untermenü ist gefixt
(E). Was fehlt, ist die **Schreibweise deines Slicers** — wenn dein
trash.g-code eine `;TYPE:`-Schreibweise für die Aussenwand benutzt, die ich
nicht kenne, wird sie auf CUSTOM abgebildet (nicht verstellbar als Wand).

**Ich brauche vom Drucker (SSH, komplett einfügen):**

```
ssh pi@<drucker-ip>
grep -m3 -i ";TYPE" gcodes/trash.gcode
head -3 gcodes/trash.gcode
ls -t gcodes/Range/*.gcode | head -3
grep -m1 "_FILE_INFO" $(ls -t gcodes/Range/*.gcode | head -1)
grep -m3 -i ";TYPE" $(ls -t gcodes/Texture/*_TX.gcode | head -1)
```

(Pfade notfalls anpassen — wichtig sind: die ersten `;TYPE:`-Zeilen der
ORIGINAL-Datei und die `_FILE_INFO`-Zeile des Excerpts.) Damit wird die
Schreibweise zu einem gemappten Feature und die Aussenwand ist wieder
verstellbar — gemessen, nicht geraten.

---

**Reihenfolgeempfehlung:** B (Stempel) ist der Hauptpunkt dieser Runde,
danach C, D, E; A läuft mit jedem der Drucke automatisch mit. Bei
Auffälligkeiten gelten die alten Sammel-Regeln: klippy.log + 300 Zeilen
watcher + top-Snapshot, plus diesmal ggf. die Datei-Köpfe aus B.
