# .130-ROADMAP (R173 ff.) — Wünsche aus dem .129-Feldbericht

Reihenfolge nach Nutzen/Aufwand. Alles Weitere (String-Art-Menü, R171) ist
schst im Baum und wartet auf diese Runde.

## R174-pre — Feld-Fixes aus dem 2. .129-Feldlog (EINGEBAUT, Teil von .130)

- **update.sh konnte Hotfix-Buchstaben nicht:** `.129a.zip` matchte nicht in
  den Nur-Ziffern-Parser → beim Update gewann das alte `.129.zip` aus dem
  Ordner, der Hotfix kam nie an (Feldbeweis: `build R2-2026-10-22.129`).
  Jetzt: Zahlen numerisch, Buchstaben lexikographisch (129a > 129, 130 >
  129a). Das installierte ZIP wandert danach nach `r2_backups/` — kein
  Alt-ZIP gewinnt jemals wieder ein Update-Rennen.
- **Doppelter PRINT_END** nach jedem Range-Druck (2× Banner, 2× Rate-Print-
  Frage, „layers: 0"): Re-Entry-Guard `end_guard` — eine End-Choreografie
  pro Druck, Guard wird bei jedem Druckstart scharf zurückgesetzt.
- **SD-Browser: Bild angeklickt = Druckversuch.** Bilder in Unterordnern
  werden jetzt ins Hauptverzeichnis kopiert (neuer Nonce-Kanal
  `img_pick_nonce`), Root-Bilder verweisen auf Tools > Lithophane. Der
  Litho-Bunny (Bun2.jpg) liegt im Root und war nie verloren — der Litho-Scan
  sieht nur Root-Bilder, Unterordner-Bilder sah er nicht.
- **Feature-Parked-UX (2. Feldlog, Ironing-Verwirrung):** Die Enable-Toggles
  im Features-Menü waren für nicht-in-der-Datei-Features ausgegraut, die
  Wert-Editoren daneben aber klickbar (und schalteten still ON) — „ich kann
  Werte stellen, aber nichts passiert". Jetzt: Toggles IMMER klickbar, Name
  zeigt **(parked)**, jede Aktion antwortet ehrlich („not seen in this file
  yet - value stored, it applies when the file reaches it"), und die neue
  Kopfzeile **In file: WO,SO,TP,BR** zeigt auf einen Blick, welche Features
  DIESE Datei wirklich hat. CUSTOM-Häufung: Altdateien aus dem .129er
  Postproc (vor dem R172-Typ-Fix) — Re-fix types (System > File check) heilt
  sie, künftig generiert der Postproc korrekte Tags.

## R174 — User-Presets für ALLE Generatoren (außer Range)

**Regeln (Nutzerwahl):**
- Jeder Generator (Labels, Litho, Textur, Plotter, Kabelbinder, Winkel,
  Dichtungen, Rahmen, Bricks/Kits/Figuren, ColorPic, String-Art) bekommt:
  **Save / Load / Delete** für eigene Presets.
- Ein Preset speichert ALLE Einstellungen des Generators.
- Markante Namen: bei Textur z. B. „fuzzy", „waves", „lines" — oder der
  Name des benutzten Werks-Presets (wird beim Speichern übernommen).
- **KEINE Begrenzung:** beliebig viele User-Presets, fortlaufend, keine
  Liste gekappt, kein Browser-Limit (analog SD-Menü: 40/Seite, blätterbar).

**Technik:** ein Watcher-Speicher pro Generator
(`label_user_presets`, `texture_user_presets`, … — dict in
save_variables.cfg, per JSON-String; der Watcher liest/schreibt per
nonce wie immer). LCD: Settings-Menü jedes Generators erhält drei Zeilen
(Preset: Save / Load > Nr / Del > Nr), Load/Del blättern durch alle.
Werks-Presets bleiben wie sie sind.

## R175 — Textur-Bibliothek (Muster-Generator)

Ersetzt die festen 3 Bump-Muster durch eine **Mustertextur-Engine**: jede
Textur = reine Python-Funktion `(x, y, z, scale) -> -1..+1` (Versatz quer
zur Außenwand). Damit werden alle gewünschten Muster machbar:

| Gruppe | Muster |
|---|---|
| Geflochten/umwickelt | Korbgeflecht (2/1-Zopf, diagonal versetzt), Seil umwickelt (helix mit Pressfurchen), Strick/I-cord |
| Holz/Bau | Parkett (versetzte Stäbe mit Fugen), Planken (Risse+Fugen), alte raue Bretter (Längsmaserung + Ausbrüche), Ziegel/Backstein/Mauerwerk (versetzt, Fugen), Sandstein (fein-porig), Betonplatte (grobporig + Nadelstriehen) |
| Organisch | Ton/Lehm (weiche Dellen, Fingerabdrücke = gestreckte Gaussian-Dellen), crêpe-artiges graues Papier, leicht geknittertes Papier (große weiche Falten), Stoff-Falten (parallele weiche Wellen + scatter), flauschig/plüschig (Hoch-Tief-Rauschen fein + weich) |
| Geometrisch | Hilbert-Kurve, Schachbrett, Bienenwaben (hex), Kratzspuren (gerichtete dünne Striche), Schraffuren (Kreuz/parallel, verschiedene Winkel/Dichte) |
| Spezial | Melt/Glitch: **zufälliger Schicht-Versatz** (per Seed deterministisch pro Layer: die ganze Ebene versetzt seitlich — kein reines Muster, sondern ein Layer-Hook im Textur-Tool) |
| Eigenes Bild | **Graustufen-Map wickeln:** hochgeladenes PNG/JPG wird als Höhenkarte um das Objekt gelegt (Zylinderprojektion auf die Außenwand: Winkel→U, Z→V; Grauwert = Versatz). Nutzt die bewährte _img_luma-Pipeline. |

Jedes Muster mit Vorschauname („fuzzy", „rope", „planks"…) — passt direkt
zu R174 (Preset-Name = Mustername).

## R176 — Pre-Print: Skalieren X/Y mit Flow-Neubaseline

**Nutzerwunsch:** Geometrie im G-Code auf X und Y getrennt skalieren;
E-Werte so mitskalieren, dass die skalierte Datei die „neuen 100 %" ist.

**Mathematik (pro Move, Richtung u=(ux,uy)):**
- Länge: L' = |S·u| · L mit S=diag(sx, sy)
- Breite: w' = w · |S·n| mit Quer-Richtung n=(-uy, ux)
- E' = E · (L'/L) · (w'/w) — Schichthöhe bleibt.

Damit stimmt der Materialbedarf pro Schicht exakt (%-Ersparnis wird im
Dialog angezeigt: grob ~1−sx·sy bei flächigem Infill, exakt pro Move
gerechnet und als Summe reportet).

**Einbau:** Pre-Print > File > **Scale X/Y** (Watcher-Job wie die
optimierten Kopien): schreibt eine skalierte KOPIE (V-Name, _SXXX-SYYY im
Header), wählt sie automatisch. Der Druck startet mit FLOW 100 = korrekt
für die skalierte Datei — live Tuning ganz normal obendrauf. Backup nie
nötig (Original unberührt), nie während des Drucks.

## R177 — BONUS: Kuchen-Schnitt (freie Schnittebene durchs Objekt)

**Nutzeridee:** Objekte nicht schichtweise (Z) trennen, sondern wie eine
Torte mit dem Messer von oben nach unten schneiden — mit Drehwinkel (Z),
Neigung (um Y/X) → freie Schnittebene. Optionen: eine Hälfte wegwerfen
ODER halbieren; Hälften auf die Schnittkante stellen (3 Outline-Schichten
als Boden, dann jede Hälfte für sich).

**Meine Einschätzung: machbar, aber die härteste Aufgabe bisher.** Der
Plan, den du selbst skizziert hast, ist genau richtig und so setze ich es
um:

1. **Extraktion:** Objekt per EXCLUDE_OBJECT (oder Gesamtmodell) aus dem
   G-Code lösen — relative Koordinaten um den Objekt-Schwerpunkt, eine
   Schichtliste von Polygonzügen (Moves → Polyline-Segmente, wie sie der
   Geometry-Classifier R111 schon sieht). Das Objekt liegt dann als
   „Schicht-Pfannkuchenstapel" vor — visualisierbar, wie du es beschreibst.
2. **Schnitt:** jede Extrusions-Schicht (Polygone + Schraffuren) wird mit
   der Schnittlinie (in Objektkoordinaten: Winkel + Offset) geschnitten —
   Polygon-Clipping (Even-Odd) halbiert jede Schicht in Teil A/B. Das ist
   klassische 2D-Geometrie pro Schicht, die Neigung macht die
   Schnittlinie Z-abhängig (sie wandert mit der Höhe → genau der
   „Messer"-Eindruck). Kein 3D-Mesh nötig — der G-Code IST schon
   Schicht-Polygone.
3. **Wand auf die Schnittkante:** an jeder offenen Kante eine Wandlinie
   (Außenwand + ggf. 2 Loops) entlang der Schnittkante pro Schicht — wie
   der Range-Floor, nur konturfolgend.
4. **Aufrichten:** jede Hälfte um die Schnittkante klappen (Rotation um
   die Schnittlinien-Achse; die Schichten werden zu Spalten) — NICHT
   nötig, wenn die Hälften einfach FLACH weitergedruckt werden: dann
   läuft der Druck wie gehabt und nur der „Boden" (3 Outline-Schichten
   über die Schnittfläche) ist neu. Variante „auf die Kante stellen"
   (90° gekippt) ist aufwändiger (Schichten werden zu Wänden,
   Stützflächen-Logik) — erst die Flach-Variante, dann sehen wir weiter.
5. **Positionierung:** am Ende zurück auf absolute Bett-Koordinaten,
   beide Hälften nebeneinander mit 12 mm Abstand (der bewährte Packer
   macht das Layout).

**Display-Handhabung (deine Regel: einfach):** Objekt wählen (falls
mehrere im File), dann nur **Winkel** (0–359°) und **Offset** (−50…+50 mm
relativ zur Objektmitte, 0 = mittig halbieren) — der Rechner macht den
Rest. Neigung kommt in Version 2, wenn Flach+Winkel sitzt.

**Ehrliche Risiken:** Fill-Segmente, die die Schnittlinie kreuzen, müssen
gekürzt und an der Kante verankert werden (sonst hängt Filament in der
Luft); überhängende Bereiche an der Schnittfläche drucken ohne Support.
Für „Modell aufschneiden, um reinzuschauen/inzubauen" ist die Flach-
Variante trotzdem sofort nützlich — und sie baut auf dem auf, was Range +
Texture + Classifier schon können.

## Reihenfolge

R174 (Presets) → R175 (Textur-Bibliothek) → R176 (Skalieren) → R177
(Kuchen-Schnitt Flach-Variante). Zwischendrin: String-Art-Menü (R171
aktivieren). Jede Runde batteriegesichert, Version .130 am Ende der
Feldtest-Runde.
