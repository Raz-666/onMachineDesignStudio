# R90 Design — Picture frame / display case generator (Bilderrahmen/Schaukasten)

Stand: Entwurf, noch nichts implementiert. Ziel: LCD Tools > Frames — wie
immer ohne Slicer, vom Bett bis zur fertigen Wand.

## DerKern-Bauräume (E3: Bett 244×241 mm, Z ~250 mm)

## Lösung 1 — Konstruktion & Bildwechsel (Bilderrahmen, flach)

| Variante | Aufbau | Bildwechsel | Bewertung |
|---|---|---|---|
| **A. Rückwand + Rastung** (empfohlen) | Front-Rahmen mit Bild-Nut (Falz) + separate Rückwand. Rückwand rastet mit 4 gedruckten Nasen (Bajonett: einstecken, 5 mm schieben) hinter dem Rahmen ein | von hinten, Sekunden, mehrfach | robust, Foto bleibt flach, Rückwand = eigenes Teil (Bausatz auf dem Bett daneben) |
| **B. Seitlicher Einschub** | Rahmen mit durchgehender Nut hinten, Front geschlossen. Foto + Deckkarton schieben von der Seite rein | seitlich einschieben | 1 Teil weniger, aber: Öffnungs-Schlitz braucht exakte Nutbreite, nur für dünne Fotos, Bild muss passgenau |
| **C. Beides wählbar** | A als Default, B als Option `Closure=SIDE` | — | maximal flexibel, doppelter Testaufwand |

## Lösung 2 — Schaukasten (tief)

| Variante | Aufbau | Druck | Bewertung |
|---|---|---|---|
| **A. Box in einem Stück** (empfohlen) | Front-Rahmen + 4 Wände + integrierte Bild-Nut vorne, hinten offen. Rückwand separat (wie Rahmen A) oder Klemmleiste | liegend, Front OBEN (Opening unten): Wände mit 40° Innen-Kehle → Öffnungsränder druckbar ohne Support; ODER stehend wenn das Maß flach nicht mehr passt | Front-Finish perfekt (Ironing oben), Tiefe 15–60 mm; Bauraum-Check: Fläche = Rahmenmaß, Höhe = Tiefe |
| **B. Bausatz: Front + Box getrennt** | Front-Rahmen flach (Front oben, perfekt finish) + Box-Körper als 2. Teil mit Nut, beide werden zusammengesteckt/geklebt | alles flach auf dem Bett | auch für RIESIGE Kästen (Teile einzeln < Bauraum), aber Kleben nötig |
| **C. Steck-System** | Front + 4 Wandstreifen + Rückwand als Steckkonstruktion (Nut+Feder) | flach, 6+ Teile | kein Kleber, aber viele Teile, Fugen sichtbar |

## Lösung 3 — Formen (Shape)

| Form | Parameter | Innenausschnitt |
|---|---|---|
| **RECT** (Default) | W × H, Eckradius 0–20 mm einstellbar | folgt mit Rahmenbreite |
| **OVAL** | Durchmesser X × Y (gleich = Kreis, verschieden = Ellipse/Oval) | konzentrisch |
| **TRIANGLE** | Breite, Höhe folgt (gleichseitig) oder frei | innenparallel |
| **STAR** | Zackenzahl 5/6/8, Spitzentiefe einstellbar | innenparallel |
| **HEX** (fach) | Schlüsselweite | innenparallel |

Erster Wurf: RECT + OVAL + TRIANGLE + STAR (HEX nur wenn du ihn willst).

## Lösung 4 — Oberflächen-Struktur der Front (liegend gedruckt = oberste Layer)

| Struktur | Optik | Aufwand |
|---|---|---|
| **Smooth** (Default, + Ironing) | einheitlich matt-glatt | niedrig |
| **Lines** | horizontale/vertikale Feinlinien (0.4 mm Raster) | niedrig |
| **Waves** | sanfte Sinus-Wellen | mittel |
| **Diamond** | 45°-Rauten | mittel |
| **Cells** | Waben-/Zellmuster | mittel |

Umsetzung: Höhenmodulation der obersten 1–2 Layer der Front-Fläche
(Muster-Bahnen), Struktur wirkt nur auf die sichtbare Front, Seiten glatt.

## Lösung 5 — Aufhängen & Aufstellen

- **Verdeckte Haken-Ösen**: Dreiecks-Schlitz + Rundloch-Kombi in der
  RÜCKKANTE (klassischer Draht-/Nagel-Haken), von vorn UNSICHTBAR.
  Position wählbar: Oben / Unten / Links / Rechts (für Hoch-/Querformat).
  Ab 8 mm Rückkante möglich.
- **Ständer**: Aufstell-Fuß (Dreieck-Streben) als zusätzliches Teil im
  Bausatz-Satz (steckt in Rückwand-Nuten), Winkel ~15–30°.
- **Beides gleichzeitig** geht (Öse + Ständer).

## Lösung 6 — Maße & Presets

- **Foto-Presets** (Innenmaß = Foto + 0.5 mm Spiel, Sichtausschnitt =
  Foto − 1.5 mm Überlappung je Seite): 9×13 · 10×15 · 13×18 · 15×21 ·
  20×30 · 30×40 · A6 · A5 · A4 · A3 · Custom (W×H frei)
- **Tiefe**: 3 mm (Foto-Rahmen) bis 60 mm (Schaukasten) — ab ~15 mm
  schlägt der Generator den Schaukasten-Modus vor (Box-Konstruktion)
- **Rahmenbreite** (Sichtrand): 4–30 mm
- **Wandstärke**: 0.8–3 mm (Wandstärke = Wände des Kastens)
- **Infill**: 20–100 % (Wände ohnehin massiv gespiralt)
- **Ironing**: ON/OFF (Default ON für Smooth)

## Druck-Anordnung im Bausatz

Alle Teile EINER Job-Datei, korrekt auf dem Bett platziert (wie Ties):
Front-Rahmen, Rückwand, Ständer (optional) — jedes Teil ein
EXCLUDE-Objekt (Frame_front, Frame_back, Frame_stand).
Bauraum-Limits automatisch geprüft; wenn flach zu groß → Vorschlag
stehend oder Bausatz-Aufteilung per Hinweis.

## Offene Entscheidungen (ask_user)

1. Verschluss Bilderrahmen: A (Rückwand-Rastung) / B (seitlich) / C (beides)
2. Schaukasten: A (Box ein Stück, liegend Front oben) / B (Bausatz Front+Box) / C (Stecksystem)
3. Formen-Umfang erster Wurf: alle 4+ / nur RECT+OVAL zuerst
4. Strukturen: alle 5 / nur Smooth+Lines+Waves zuerst


---

## Implementation status (R90, first release)

Built exactly per the four decisions (ask_user): Closure **C** (BACK + SIDE),
box **Auto** (one piece / multi-plate / split kit), shapes **RECT (corner
radius) + OVAL**, surface **Smooth + Ironing**.

**What shipped (R90.1b additions)**

- Surface select (Front): Ironed / Bed texture (FLIP - the front prints against
  the bed, band order mirrored) / Lines / Waves / Honeycomb structures
  (depth/spacing/angle/amplitude/cell size, IN grooves or OUT ridges, RECT
  only, replaces ironing) - LCD submenu "Surf".
- Disc insert GLASS/PLEXI/FOIL/LITHO, FRONT (captured by a 1.2mm lip in the
  front band) or BACK (behind the photo on the back band, backlit; the
  backplate rim clamps it, nubs ride higher) - groove grows by disc+0.2mm.
- Hidden cable duct (CASE only): 6mm slot through the bottom bar opening
  2.5mm behind the back face straight into the interior.
- AUDIT FIXES: _rr_pts corner order (the contour was a self-intersecting
  4-pointed star -> bowtie walls) and _convex_intervals sign error (the ray
  ran backwards -> zero hatch: R90 frames printed naked walls with no photo
  shelf). Both verified with segment-level geometry tests.

**Earlier (R90/R90.1a)**

- `make_frame()` in tools/r2_postproc.py: one-piece frame + backplate (+ stand);
  R90.1a **multi-plate before kit**: when frame + plate don't fit side by side
  it writes TWO files (Part A = frame, Part B = backplate + stand, end-of-plate
  hint + beeps in the file, no auto-start); the 4-strip glue kit only when even
  the frame alone overflows the bed; OVAL with a clear error instead of a kit.
  Presets sized for the REAL 220x220 bed: 9x13 / 10x15 / 13x18 / A6 (15x21,
  A5, A4, 20x30 overflow the bed even as strips - custom W/H up to 230 says
  so clearly).
- Zero-overhang profile, front up: back band -> groove (photo + 0.8mm plate +
  closure nubs) -> bridge shelf -> ironed front with the view opening.
- Closure BACK = bayonet: 2 nubs 1mm over the plate, plate edge notches
  (asymmetric y-ranges), drop in straight + slide 2.5mm = locked both ways,
  zero flex. Closure SIDE = full-height slot in the left wall, photo +
  cover plate slide in together.
- Hidden hang keyhole in the BACKPLATE (TOP/BOTTOM/LEFT/RIGHT/OFF - never
  visible from the front), easel stand with 2 studs plugging into D2.7 plate
  holes 24mm apart. Stand auto-drops with a note when the bed is full.
- Watcher frame_nonce (17 channels), FRAME_INFO / FRAME_GENERATE / GEN_FRAME,
  LCD Tools > Frames (English), MANUAL ch. 5.8 + PDF illustration.

**Explicit later backlog (user decision, NOT dropped):** triangle + star
shapes; line/wave/diamond/honeycomb surface structures. Ovals are limited to
~100mm photo width on this bed (no kit split possible for curved outlines).
