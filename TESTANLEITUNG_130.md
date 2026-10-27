# FELDTEST .130 (R174 – R177) — Testanleitung

Diese Runde bringt **sechs Pakete**: **R174 — Eigene Presets für JEDEN
Generator**, **R175 — die nahtlose Textur-Bibliothek**, **R175b — der
Menü-Umbau** (deine Reihenfolge), **R175c — die neue Fan-Logik** (ein
Drehregler, eine Kette, angezeigt), **R175d — Löschen im SD-Browser**,
**R176 — Skalieren X/Y mit ehrlichem Flow** und **R177 — der
Kuchen-Schnitt**. Außerdem: der Range-Done-Sound (aus .129 nachgeliefert)
und nummerierte Optimized-Kopien (nichts wird mehr still überschrieben).

Vor dem Testen: .130-ZIP wie immer hochladen, `bash klipper-e3-r2d2/update.sh`
per SSH. Am Ende muss stehen:
`post-processor reports build 'R2-2026-10-24.130 (R177)'` UND
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

## 5) R175b: Der Menü-Umbau — deine Reihenfolge

**Pre-Print** heißt jetzt oben: **1.** Datei-Info, **2.** Fixes (inkl. File
check/Retagging und „Why segments?"-Erklärzeile), **3.** Werkzeuge
(Offset/Textur/Range/**Scale**/**Kuchen**/Plotter — der Plotter erscheint
weiterhin nur im Plot-Modus), **4.** Temperaturen (Material/Filament),
**5.** Motion (Velocity/Extrusion/Retraction als Untermenüs), **6.**
Features, **7.** Utilities (Preheat/Mesh/Confirm/Overwrites), **8.**
Profile. Die einzelne Defaults-Zeile ist weg — sie verdoppelte Profile >
Defaults. **Live-Tuning:** Temps & Fan zuerst, Z-Hopping als Untermenü,
Z-Offset + Babysteps als direkt bedienbare Zeilen, Exclude/Pause ganz hinten.

**Test:** einmal komplett durchklicken (Pre-Print UND Live-Tuning) — jede
Funktion muss erreichbar sein, keine Doppeltür mehr. Falls dir eine Tür
fehlt: Menüpfad notieren (der Inventar-Check im Labor sagt „nichts verloren",
aber das Auge auf dem echten Display zählt).

## 6) R175c: Fan-Logik — ein Drehregler, eine Kette

**Aus .129 bekannt:** für volle Power brauchte es DREI Knöpfe (Hold 100% +
Clamp aus + Fan 150%), weil ein Skalierungsfaktor sich als Fan-Wert
verkleidete. **Jetzt:** Live-Tuning → Temps & Fan → **`Fan: NN% (LIVE)`**.
Der LIVE-Wert ist deine absolute Drehzahl und schlägt ALLES — Hold, Scale,
Clamp und die Layer-1-Regel. Die Zeile darunter schaltet LIVE an/aus (aus =
der Drucker steuert wieder selbst), und **`How? (fan math)`** druckt die
ganze Kette mit den aktuellen Zahlen, z. B.
`file 40% x scale 120% -> clamp 10-90% = 48%`.

**Kette (stärkstes zuerst):** LIVE > Layer-1-aus > HOLD > SCALE > CLAMP.

**Test:** während eines Drucks in Layer 1 den Regler auf 100% LIVE stellen —
der Lüfter muss sofort voll drehen (vorher hätte die Layer-1-Regel ihn
ausgehalten). Dann LIVE aus → ab dem nächsten Fan-Befehl gilt wieder die
Datei. Jede Änderung quittiert M106 mit der Rechnung, die dazu führte.

## 7) R175d: Löschen im SD-Browser

**Wo:** SD Card → **Del**-Zeile. Erster Druck schaltet den Del-Modus ein
(`DEL ON: 2x press`), dann gilt für JEDE Datei und JEDEM Ordner: erster
Klick **armiert** (Zeile zeigt `> AGAIN = delete`), zweiter Klick **löscht**.
Ordner gehen mit allem Inhalt. Gelöscht wird NUR unterhalb des G-Codes-Root
— Fluchtversuche wie `../../` werden verweigert, und während eines Drucks
ist grundsätzlich Feuerpause.

**Test:** einen Testordner mit einer Datei anlegen, über den Browser
löschen (2× drücken) — Ordner UND Datei müssen weg sein. Während eines
Drucks probieren: muss verweigert werden (Meldung auf dem Display).

## 8) R176: Skalieren X/Y mit ehrlichem Flow

**Wo:** Pre-Print → Werkzeuge → **Scale X/Y**. X und Y je **25–300 %**
(Step 5), `How? (E/flow)` erklärt die Mathematik, `> Apply` startet per
Doppelklick (erster Druck armiert).

**Was passiert:** die Datei wird verzerrungsfrei skaliert, auf die
Bettmitte zentriert, Bögen werden zu Sehnen — und **E wird pro Zug
nachgerechnet**: (L'/L)·(w'/w). Achszüge skalieren mit X·Y, 45°-Züge mit
(X²+Y²)/2, uniform mit X². Damit bleibt dein Flow 100% UND stimmt — und
die **neue 100 %-Basis ist die neue Datei** (Live-Tuning bezieht sich
danach auf sie). Die Schichthöhe bleibt unberührt.

**Test:**
1. Kleines Teil wählen, X 150 / Y 150 → Apply. Im Chat kommt
   `Scale: name -> name_S150-150.gcode (… 40.0 x 40.0 -> 60.0 x 60.0 mm,
   centered on the bed …)`. Die Datei liegt im Ordner **Scale/**.
2. Die skalierte Datei drucken und mit dem Original vergleichen —
   Proportionen und Oberfläche müssen identisch wirken (kein Über-/Unter-
   Extrudieren).
3. Nochmal Apply auf dieselbe Datei → `name_S150-150_2.gcode` (nie
   Überschreiben).
4. X 300 auf einem Teil, das größer als ~73mm ist → klare Ablehnung mit
   der benötigten Bettgröße in der Meldung.

## 9) R177: Der Kuchen-Schnitt

**Wo:** Pre-Print → Werkzeuge → **Cake cut**. Die Schnittebene hat
**Yaw / Pitch / Roll** (je 0,5°-Raster; Yaw = wohin die Kippung zeigt,
Pitch = vor/zurück, Roll = links/rechts) und **Z plane** (Höhe der Ebene
über der Bettmitte). **Part** wählt UPPER / LOWER / BOTH, **Reorient**
ON = die Schnittfläche des Oberteils wird flach aufs Bett gelegt (so
druckt sich ein Deckel natürlich), OFF = das Oberteil behält seine
Haltung und rückt nur auf Erstschichthöhe. `> Cut now` per Doppelklick.

**Was passiert:** JEDER Zug wird exakt an der Ebene getrennt, E teilt sich
nach Längenanteil, Bögen werden zu Sehnen. Das Unterteil behält seinen Ort
(es steht ja schon), das Oberteil wird eine eigene, sofort druckbare Datei.
Beide landen im Ordner **Cake/** als `name_CUT-U.gcode` / `name_CUT-L.gcode`.

**Test:**
1. Einen Würfel/eine Box bei halber Höhe schneiden (alle Winkel 0, Z plane
   = halbe Höhe, BOTH) → zwei Dateien, beide drucken; zusammengehalten
   muss wieder der Würfel entstehen.
2. Gleiche Box mit Pitch 15° und Reorient ON → das Oberteil steht jetzt
   AUF DER SCHNITTTFLÄCHE (die schräge Fläche liegt unten auf dem Bett).
3. Part LOWER only → nur die Unterteil-Datei. Z plane über der Objekthöhe
   → klare Ablehnung („no UPPER part …").

## 10) Was noch offen ist

Die .130-Wunschliste ist damit **vollständig** (Menü-Umbau, Fan-Logik,
Löschen, Skalieren, Kuchen-Schnitt — alles drin). Aus der Roadmap bleibt
als einzige Nachzügler-Idee das **String-Art-Menü** (R171 aktivieren) —
ob das diese Runde noch kommt, entscheidet dein Feedback zum Rest.

---

**Rückmeldung wie immer:** was auffällt, gerne mit Display-Foto. Bei
Naht-Brüchen: Muster + Werte + Objekt (Vase/Würfel/Litho) notieren. Beim
Kuchen-Schnitt: die gewählten Winkel + Z plane und was dabei rauskam.
