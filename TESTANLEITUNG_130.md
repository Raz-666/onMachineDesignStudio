# FELDTEST .130 (R174 + R175) — Testanleitung

Diese Runde bringt zwei Pakete: **R174 — Eigene Presets für JEDESEN
Generator** und **R175 — die nahtlose Textur-Bibliothek** (dein
.130-Wunsch: „User-Einstellungen sind Richtlinien, die Textur muss immer
passen, auch in Z bündig"). Außerdem: der Range-Done-Sound (aus .129
nachgeliefert) und nummerierte Optimized-Kopien (nichts wird mehr
still überschrieben).

Vor dem Testen: .130-ZIP wie immer hochladen, `bash klipper-e3-r2d2/update.sh`
per SSH. Am Ende muss stehen:
`post-processor reports build 'R2-2026-10-24.130 (R175)'` UND
`Macro system OK ... (build R2-2026-10-24.130)`.

---

## 1) R175: Die Textur-Bibliothek (21 Muster, immer nahtlos)

**Wo:** Pre-Print → Textur → Pattern. Die 3 alten Festknöpfe (Grid/Waves/Hex)
sind jetzt eine **Bibliothek aus 21 Mustern auf 3 Seiten** (Ridges, Waves,
Grid, Hatch, Checker, Hex, Honeycomb, Basket, Rope, Planks, Bricks,
Sandstone, Concrete, Clay, Crepe, Fabric, Plush, Hilbert, Scratch, Glitch
und MAP = eigenes Bild).

**So testest du:**

1. Eine Zylinder-Vase (oder jedes runde Teil) slicen, im Pre-Print wählen.
2. Pattern **Bricks**, *Around:* 8mm, *Height:* 3mm, *Depth:* 0.3mm, Seed 5.
3. Apply → im Chat/Display kommt die Antwort der Form
   `[seamless: 9 ridges x 2 Z-repeats (eff. 8.4mm x 2.9mm)]`.
4. **Der Beweis:** Druck ansehen — die Nahtstelle (wo der Umfang schließt)
   muss das Muster OHNE Sprung fortsetzen, und die Oberkante muss bündig
   aufhören (kein halber Ziegel oben). Deine mm-Werte sind Richtlinien —
   das Werkzeug rechnet GANZE Rillen um den Umfang und GANZE Wiederholungen
   in Z hinein und meldet die effektive Größe.
5. **Seed:** gleicher Seed = gleiches Bild (wichtig für Sandstone/Glitch).
   Seed ändern → anderes Aussehen, aber weiterhin nahtlos.
6. **MAP (eigenes Bild):** Pattern auf MAP stellen → Zeile *Img:* erscheint.
   Im SD-Browser ein Bild antippen (wird in den Hauptordner kopiert),
   zurück zur Textur → *Img:* antippen übernimmt es. Ein Graustufen-Bild
   wird um das Objekt gewickelt (Spiegelnähte = garantiert nahtlos).
7. **Lithophanie + Textur:** Litho hat keine „Wand"-Marker — bisher kam da
   still NICHTS. Jetzt: Fallback „alle Bahnen sind die Geometrie", im
   Dateikopf steht `R175 fallback: ... lithophane mode`.

**Erwartung:** 21/21 Muster nahtlos. Wenn du an IRGENDEINER Stelle einen
Sprung in der Naht siehst: Muster + Around/Height notieren, das wäre ein
Bug-Beweis.

## 2) R174: Eigene Presets für jeden Generator

Jeder Generator (Textur, Litho, Label, Rahmen, Plot) hat jetzt
**„My presets"** mit 8 Slots: Werte einstellen → Save → Name kommt aus der
aktuellen Wahl. Laden/Delten über den Slot. Presets überleben Reboots.
**Test:** pro Generator 1 Slot speichern, Drucker neu starten, Slot laden —
Werte müssen identisch zurückkommen.

## 3) Optimized-Kopien: nie wieder überschrieben

**Aus .129 bekannt:** YES auf „Rate print?" legte die getunte Kopie in
`optimized/`. Wenn du DIESELBE Datei nochmal druckst und wieder YES sagst,
hieß die neue Kopie wie die alte — **still überschrieben, deine
Tuning-Historie weg.**

**Jetzt:** gleiche Datei + YES → `name.gcode`, nochmal + YES →
`name_O2.gcode`, dann `_O3`, `_O4` … **Test:** eine kleine Datei 2× drucken
(oder Rate-Test 2×), beide Male YES — im Ordner `optimized/` müssen beide
Versionen liegen.

## 4) Range-Done-Sound nachgeliefert

In .129 piepte der Textur-Job am Ende, der **Range**-Job (Schichten-Ausschnitt)
aber nicht. Jetzt: Range fertig → **M117 „Range ready" + Bestätigungspiep**.
**Test:** einen Range-Ausschnitt bauen lassen — am Ende muss Piep + Display
„Range ready" kommen (wie bei Textur).

## 5) Was (noch) NICHT drin ist — nächste Runden

- Menü-Umbau Pre-Print / Live-Tuning (Reihenfolge wie besprochen)
- Fan-Logik (hold/clamp/150% entschaukeln)
- SD-Browser Löschen-Funktion
- X/Y-Skalier-Werkzeug inkl. Flow-Neurechnung
- Kuchen-Schnitt mit 0,5°-Winkeln in allen Achsen

Die Reihenfolge steht in `docs/ROADMAP_130.md`.

---

**Rückmeldung wie immer:** was auffällt, gerne mit Display-Foto. Bei
Naht-Brüchen: Muster + Werte + Objekt (Vase/Würfel/Litho) notieren.
