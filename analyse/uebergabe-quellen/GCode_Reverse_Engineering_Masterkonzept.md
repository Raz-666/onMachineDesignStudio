# Technisches Masterkonzept
## G-Code Reverse Engineering und geometrische Feature-Erkennung per Post-Processing

**Zielgruppe:** Coding-KI / Softwareentwickler  
**Ziel:** Eine robuste, slicer-unabhängige Analyse-Engine, die aus G-Code Bewegungen, Extrusionen, Layern, Pfadgruppen, Geometrien und wahrscheinlichen Druck-Features rekonstruiert – auch wenn Kommentare und Feature-Tags vollständig fehlen.

---

# 0. Verbindliche technische Leitplanken

## 0.1 Was das System leisten soll

Das System darf nicht bloß nach Kommentaren wie `;TYPE:WALL-OUTER`, `;TYPE:INFILL` oder `;LAYER_CHANGE` suchen. Es muss den G-Code zunächst semantisch korrekt interpretieren und anschließend die resultierenden Bewegungen geometrisch, topologisch, kinetisch und statistisch analysieren.

Es soll mindestens:

1. G-Code unterschiedlicher FDM/FFF-Slicer-Familien einlesen.
2. Modalzustände und Koordinaten korrekt nachführen.
3. Extrusions- und Travel-Bewegungen rekonstruieren.
4. Layer auch ohne Layer-Marker ableiten.
5. Bewegungen zu Segmenten, Pfaden und räumlichen Komponenten gruppieren.
6. Linienbreite, Layerhöhe, Flow und weitere Parameter soweit möglich schätzen.
7. 2D-Geometrie pro Layer und 3D-Beziehungen zwischen Layern rekonstruieren.
8. Feature-Rollen und Infill-/Oberflächenmuster klassifizieren.
9. Jede Zuordnung mit Belegen, Konfidenz und Alternativhypothesen versehen.
10. Nicht eindeutig lösbare Fälle als `UNKNOWN` oder `AMBIGUOUS` ausgeben, statt eine falsche Sicherheit vorzutäuschen.
11. Optional Kommentare/Tags in einer Kopie des G-Codes ergänzen, ohne die ursprünglichen Bewegungen zu verändern.
12. Eine maschinenlesbare Analyseausgabe (JSON) und einen nachvollziehbaren Diagnosebericht erzeugen.

## 0.2 Unmögliche Garantie: 100 % semantische Rekonstruktion

Eine absolute 100-%-Erkennung aller ursprünglichen Slicer-Feature-Rollen ist aus reinem G-Code prinzipiell nicht garantierbar.

Begründung: G-Code beschreibt primär Maschinenbewegungen und Zustandsänderungen, nicht zwingend die semantische Absicht des Slicers. Zwei unterschiedliche Feature-Rollen können dieselbe Bahn, dieselbe Geschwindigkeit und dieselbe Extrusionsmenge besitzen. Beispielsweise können eine Support-Linie und eine interne Modelllinie geometrisch identisch sein. Ebenso können ein Brim und eine erste Modellkontur in Grenzfällen dieselbe Geometrie haben.

Daher muss die Engine zwei getrennte Ergebnisse liefern:

- **Geometrisch sicher rekonstruierbar:** Position, Bewegung, Extrusionsänderung, Layer-Zuordnung (soweit ableitbar), Pfadverlauf, geschlossene Konturen, räumliche Lage.
- **Semantisch inferiert:** Outer Wall, Support, Top Surface, Bridge, Sparse Infill usw. Diese Zuordnung ist eine Hypothese mit Konfidenz und Begründung.

Niemals `100 % sicher` ausgeben, wenn die Datenlage das nicht trägt. Die Engine soll maximal zuverlässig sein, nicht maximal selbstsicher.

## 0.3 Analyseebenen strikt trennen

Nicht vermischen:

- **G-Code-Befehl:** Was wurde befohlen?
- **Maschinenbewegung:** Welche räumliche Bewegung ergibt sich daraus?
- **Extrusionsereignis:** Wurde Filament vorwärts, rückwärts oder gar nicht bewegt?
- **Geometrischer Pfad:** Welche Bahn wurde abgefahren?
- **Druckregion:** Welche räumliche Fläche/Volumenregion wird dadurch aufgebaut?
- **Feature-Rolle:** Welche Druckfunktion erfüllt die Region vermutlich?
- **Pattern:** Welches Linien-/Flächenmuster wurde verwendet?
- **Viewer-Event:** Retract, Toolchange, Pause, Seam usw.

Ein `Travel` ist beispielsweise eine Bewegungsrolle, kein Modellfeature. `Gyroid` ist ein Muster, keine Feature-Rolle. `Top Surface` ist eine Feature-Rolle, die mit einem Rectilinear- oder Concentric-Muster gedruckt werden kann.

---

# 1. Ziel-Taxonomie

Die Klassifikation muss eine kanonische interne Taxonomie verwenden. Slicer-spezifische Namen werden auf diese kanonischen Rollen normalisiert. Unbekannte Namen bleiben als Originalstring erhalten.

## 1.1 Modellwände und Konturen

- `OUTER_WALL` / External Perimeter / Outer Shell / WALL-OUTER
- `INNER_WALL` / Perimeter / Internal Perimeter / Inner Shell / WALL-INNER
- `OVERHANG_WALL`
- `THIN_WALL`
- `SINGLE_EXTRUSION_WALL`
- `HOLE_WALL`
- `GAP_FILL`
- `GENERIC_WALL`
- `UNKNOWN_WALL`

Interne Loop-Merkmale separat speichern: Hole, Second Perimeter, Contour Internal Perimeter, Floating Vertical Shell, Skirt Loop usw. Diese sind nicht zwingend eigenständige Feature-Rollen.

## 1.2 Flächen und Infill

- `SPARSE_INFILL`
- `SOLID_INFILL`
- `INTERNAL_SOLID_INFILL`
- `TOP_SURFACE`
- `BOTTOM_SURFACE`
- `SKIN`
- `BRIDGE_INFILL`
- `INTERNAL_BRIDGE`
- `IRONING`
- `SURFACE_MODE`
- `INFILL_OVER_BRIDGE`
- `GENERIC_INFILL`

Muster unabhängig von der Rolle speichern, z. B.:

- Rectilinear / Lines / Aligned Rectilinear
- Grid
- Triangles / Tri-Hexagon / Stars
- Cubic / Adaptive Cubic / Support Cubic / Quarter Cubic / Octet
- Gyroid
- Honeycomb / 3D Honeycomb
- Concentric
- Cross / Cross 3D
- Zig-Zag
- Lightning
- Hilbert Curve
- Archimedean Chords / Octagram Spiral
- Monotonic / Monotonic Lines
- Snug
- Progressive / Adaptive Infill
- Unknown Pattern

Mustererkennung ist eine separate, nachgelagerte Klassifikation. Ein Muster darf nicht allein die Feature-Rolle bestimmen.

## 1.3 Support

- `SUPPORT_BASE`
- `SUPPORT_INFILL`
- `SUPPORT_WALL`
- `SUPPORT_INTERFACE`
- `SUPPORT_ROOF`
- `SUPPORT_FLOOR`
- `SUPPORT_TRANSITION`
- `TREE_SUPPORT`
- `PILLAR_SUPPORT`
- `SOFT_SUPPORT`
- `SUPPORT_BRIM`
- `GENERIC_SUPPORT`

Tree/Organic/Pillar beschreiben zusätzlich die Strukturform. Sie können zugleich `SUPPORT_BASE` oder `SUPPORT_INTERFACE` sein.

## 1.4 Bettadhäsion und Hilfsstrukturen

- `SKIRT`
- `BRIM`
- `BRIM_EAR` / Mouse Ear
- `RAFT_BASE`
- `RAFT_MIDDLE`
- `RAFT_INTERFACE`
- `RAFT_TOP`
- `RAFT_SURFACE`
- `PRIME_LINE`
- `PURGE_LINE`
- `PRIME_BLOB`
- `PRIME_TOWER` / Wipe Tower / Wiping Tower / Tip Tower / Prime Pillar
- `OOZE_SHIELD`
- `WIPE_WALL`
- `DRAFT_SHIELD`
- `CUSTOM_HELPER`
- `UNKNOWN_HELPER`

## 1.5 Bewegungs- und Ereignistypen

Als unabhängige Event-Klasse führen:

- `TRAVEL`
- `RETRACT`
- `UNRETRACT`
- `WIPE_MOVE`
- `SEAM_EVENT` (nur inferiert, wenn keine Marker existieren)
- `TOOL_CHANGE`
- `COLOR_CHANGE`
- `PAUSE`
- `CUSTOM_GCODE`
- `LAYER_CHANGE`
- `OBJECT_START`
- `OBJECT_END`
- `FAN_CHANGE`
- `TEMPERATURE_CHANGE`
- `UNKNOWN_EVENT`

`CUSTOM`, `MIXED`, `MULTIPLE`, `UNKNOWN`, `UNDEFINED`, `NONE`, `OTHER` und `NOOP` als generische/Meta-Kategorien unterstützen.

## 1.6 Slicer- und Kommentar-Aliase

Mindestens folgende Familien berücksichtigen:

- Slic3r / PrusaSlicer / SuperSlicer
- OrcaSlicer / Bambu Studio und darauf basierende Slicer
- Cura / CuraEngine und Cura-basierte ältere Slicer
- Simplify3D
- FlashPrint
- ideaMaker
- Kiri:Moto
- KISSlicer
- CraftWare
- MatterSlice / MatterControl
- IceSL
- AstroPrint (Backend kann Cura oder Slic3r/Prusa-artig sein)

Wichtige Kommentarformen und Aliase sind unter anderem:

- Cura: `;TYPE:WALL-OUTER`, `WALL-INNER`, `SKIN`, `SKIRT`, `SUPPORT`, `FILL`, `SUPPORT-INTERFACE`, `PRIME-TOWER`, `;LAYER:n`, `;LAYER_COUNT:n`, `;MESH:...`
- Prusa/Slic3r/Orca-artig: `;TYPE:External perimeter`, `Perimeter`, `Overhang perimeter`, `Internal infill`, `Solid infill`, `Top solid infill`, `Ironing`, `Bridge infill`, `Gap fill`, `Skirt`, `Support material`, `Support material interface`, `Wipe tower`, `Custom`, `;LAYER_CHANGE`, `;Z:...`
- Orca/Bambu-Erweiterungen: `Bottom surface`, `Internal bridge infill`, `Support transition`, `Support ironing`, `Flush`, `FloatingVerticalShell` und Loop-Flags wie `Hole`, `PerimeterHole`, `SecondPerimeter`
- Simplify3D: `; feature outer perimeter`, `inner perimeter`, `solid layer`, `infill`, `support`, `dense support`, `bridge`, `skirt`, `prime pillar`, `ooze shield`, `raft`
- Weitere Preview-Begriffe: `Inner Shell`, `Outer Shell`, `Solid Fill`, `Wiping Tower`, `Wipe Wall`, `Dense Support`, `SoftSupport`, `OuterHair`, `InnerHair`, `Pillar Path`, `Crown Path`, `Stacked Sparse Infill Path`

Diese Taxonomie ist eine Normalisierungsliste, keine Behauptung, dass jeder Name in jeder G-Code-Datei als Kommentar vorkommt.

---

# 2. Architektur der Software

Die Implementierung modular aufbauen. Keine einzige riesige Regex oder monolithische Klassifikationsfunktion.

## Modul A – Input, Normalisierung und Parser

Verantwortlich für Dateieinlesen, Zeilen-Tokenisierung, Kommentare, Parameter, Befehle, Fehlerdiagnose und G-Code-Zustand.

## Modul B – Modal State Machine

Hält den vollständigen Zustand des Druckers während der Interpretation. Jede Bewegung muss aus dem Zustand vor dem Befehl berechnet werden.

## Modul C – Bewegungsrekonstruktion

Erzeugt normalisierte Move-Objekte aus G0/G1/G2/G3 und unterstützten Bewegungsbefehlen.

## Modul D – Extrusions- und Kinematik-Analyse

Berechnet XY-/XYZ-Distanz, E-Differenz, Filamentvolumen, Volumen pro Weg, Geschwindigkeit, Beschleunigungsindikatoren soweit verfügbar, Retracts und Flow-Signaturen.

## Modul E – Layer-Rekonstruktion

Erkennt planare Layer, variable Layerhöhen, Z-Hops, nicht-planare Segmente und unsichere Z-Zuordnungen.

## Modul F – Pfad- und Graph-Rekonstruktion

Verbindet aufeinanderfolgende Moves zu Extrusionspfaden, Konturen, Segmenten und räumlichen Komponenten.

## Modul G – Geometrie-Engine

Erzeugt 2D-Querschnitte, Linienkorridore, Polygone, Offsets, Abstände, Schnittmengen und Boolesche Differenzen.

## Modul H – 3D-/Inter-Layer-Topologie

Vergleicht benachbarte Layer/Regionen, erkennt Überhänge, Top-/Bottom-Flächen, Stützbeziehungen und Hilfsstrukturen.

## Modul I – Feature- und Pattern-Klassifikator

Kombiniert geometrische, topologische, kinetische und statistische Evidenz. Liefert Klasse, Konfidenz, Begründung und Alternativen.

## Modul J – Output / Post-Processing

Erzeugt JSON, Diagnosebericht, optional annotierten G-Code und einen Audit-Trail. Originalbewegungen dürfen nicht verändert werden.

---

# 3. G-Code korrekt parsen: Zustandsmaschine ist Pflicht

Eine naive Zeilenanalyse ist unzureichend. G-Code ist modal: Befehle können den Zustand ändern und nachfolgende Zeilen beeinflussen.

## 3.1 Mindestens zu unterstützende Befehle

Bewegungen:
- `G0`, `G1`
- `G2`, `G3` (Arcs, sofern im Ziel-Firmware-Dialekt vorhanden)
- optional `G5` (Spline, firmwareabhängig)

Koordinaten-/Modussteuerung:
- `G90`, `G91` – absolute/relative XYZ-Koordinaten
- `M82`, `M83` – absolute/relative Extrusion
- `G92` – Koordinaten-/Extruderposition setzen
- `G20`, `G21` – Zoll/mm
- `G28` – Homing-Event; nicht als normale Druckbewegung behandeln
- `G53` – Maschinenkoordinaten, falls unterstützt
- `G54` bis `G59` – Work Coordinate Systems, falls unterstützt

Extruder-/Toolzustand:
- `T0`, `T1`, ... – Werkzeugwechsel
- `M200` – volumetrische Extrusion, sofern Firmware-Dialekt
- `M221` – Flow-Faktor
- `M207`, `M208`, `G10`, `G11` – Firmware-Retract je nach Firmware
- `M605` und weitere Multi-Extruder-Modi nur soweit im Dialekt relevant

Druckzustand:
- `M104`, `M109` – Hotend-Temperatur
- `M140`, `M190` – Bett-Temperatur
- `M106`, `M107` – Lüfter
- `M204`, `M205` – Beschleunigungs-/Jerk-Parameter, firmwareabhängig
- `M220` – Feedrate-Faktor
- `M600`, `M0`, `M1`, `M25` – Pause/Filamentwechsel, firmwareabhängig
- `M117`, `M118` – Meldungen, nicht geometrisch

Parser soll unbekannte Befehle nicht abbrechen lassen. Unbekannte Befehle als Event mit Originaltext protokollieren.

## 3.2 Zustandsvariablen

Mindestens:

- aktuelle Maschinen-/Arbeitsposition X, Y, Z
- aktuelle E-Position je Extruder
- XYZ-Absolut-/Relativmodus
- E-Absolut-/Relativmodus
- aktuelle Einheit (mm/inch)
- aktive Toolnummer
- aktive Work-Coordinate-System-/Offset-Information, falls vorhanden
- aktive Tool-Offsets, soweit ableitbar
- aktive Feedrate F
- aktive Flow-Multiplikatoren
- Filamentdurchmesser je Tool, falls bekannt
- volumetrischer Extrusionsmodus
- aktuelle Layer-/Z-Hypothese
- aktuelle Lüfter-, Temperatur- und Bewegungsparameter
- Firmware-Retract-Zustand
- aktueller Druck-/Pause-/Toolchange-Event-Zustand

Jede Zeile erhält optional einen Snapshot des Zustands vor und nach dem Befehl.

## 3.3 Parserregeln

- Parameter können in beliebiger Reihenfolge stehen.
- Nicht jede Zeile enthält alle Achsen. Nicht angegebene Achsen behalten ihren vorherigen Wert (außer ein Dialekt definiert anderes).
- Feedrate F bleibt modal aktiv, bis sie geändert wird.
- Kommentare können hinter Befehlen stehen; Inline-Kommentare sauber trennen.
- Prüfsummen und Zeilennummern (z. B. `N123 ... *checksum`) berücksichtigen.
- Groß-/Kleinschreibung normalisieren, Originaltext dennoch erhalten.
- Exponentialnotation und Vorzeichen korrekt parsen.
- Leere Zeilen, reine Kommentare und unbekannte Syntax robust behandeln.
- `G92 E0` ist eine Positions-Neunullung, keine reale Extrusion.
- Ein negatives ΔE ist nicht automatisch eine Druckbewegung; es ist in der Regel Retract oder E-Neusetzung, abhängig vom Befehl und Zustand.
- Bei Toolwechseln E-Positionen pro Tool verwalten, nicht global vermischen.
- Relative E-Bewegung darf nicht wie absolute E interpretiert werden und umgekehrt.

## 3.4 Parser-Ausgabe

Ein normalisiertes Move-Objekt sollte mindestens enthalten:

```json
{
  "line_start": 120,
  "line_end": 120,
  "command": "G1",
  "tool": 0,
  "start": {"x": 10.0, "y": 20.0, "z": 0.2},
  "end": {"x": 30.0, "y": 20.0, "z": 0.2},
  "e_start": 4.2,
  "e_end": 5.1,
  "delta_e": 0.9,
  "feedrate_mm_min": 1800,
  "is_extrusion_candidate": true,
  "is_travel_candidate": false,
  "state_confidence": 1.0
}
```

Werte sind Beispiele. Zusätzlich Rohzeile, erkannte Parameter, aktive Modi und Warnungen speichern.

---

# 4. Bewegungs- und Extrusionsmathematik

## 4.1 Weglänge

Für lineare Bewegungen:

- XY-Distanz: `d_xy = sqrt(dx² + dy²)`
- XYZ-Distanz: `d_xyz = sqrt(dx² + dy² + dz²)`

Für normale planare Druckbewegungen ist `d_xy` maßgeblich. Für schräge oder nicht-planare Bewegungen muss die tatsächliche Bahn-/XYZ-Länge verwendet werden. Für G2/G3 ist die Bogenlänge zu berechnen, nicht die Sehne zwischen Start und Ende.

## 4.2 Extrusion

`delta_e` muss erst nach korrekter Auflösung von M82/M83, G92 und Toolwechsel berechnet werden.

Bei Filamentlängen-Extrusion:

`V_filament = delta_e * pi * (filament_diameter / 2)^2`

Das tatsächliche Materialvolumen kann durch Flow-Multiplikatoren, volumetrischen Modus, Firmware-Einstellungen und unbekannte Filamentparameter abweichen.

Volumen pro Weg:

`A_effective = V_filament / path_length`

Das ist eine effektive Querschnittsfläche. Sie ist nicht automatisch die reale Linienbreite mal Layerhöhe, weil die Linienform, Überlappung, Druckkompensation, Bridge-Flow und Slicer-Flow-Einstellungen variieren.

## 4.3 Linienbreite und Layerhöhe schätzen

Wenn keine WIDTH-/HEIGHT-Kommentare vorhanden sind:

- Cluster von `A_effective` für normale Extrusionsbewegungen bilden.
- Layerhöhe aus stabilen Z-Abständen wiederkehrender planarer Layer schätzen.
- Linienbreite nur zusammen mit Layerhöhe und einem Extrusions-/Querschnittsmodell schätzen.
- Parameter als Bereiche mit Unsicherheit speichern, nicht als scheinbar exakte Einzelwerte.
- Verschiedene Tools/Filamente und unterschiedliche Flow-Modi getrennt behandeln.

## 4.4 Travel, Extrusion und Retract

- `delta_e ≈ 0` plus XY-Bewegung: Travel-Kandidat.
- `delta_e > 0` plus räumliche Bewegung: Extrusionskandidat.
- `delta_e < 0` ohne relevante XY-Bewegung: Retract-Kandidat.
- `delta_e > 0` ohne relevante XY-Bewegung: Unretract/Prime-Kandidat.
- Firmware-Retract-Befehle können E-Bewegungen verbergen; daher G10/G11 bzw. Dialektregeln berücksichtigen.
- Wipe-Moves können gleichzeitig XY-Bewegung und Retract enthalten. Als zusammengesetztes Event speichern, nicht zwangsläufig als normales Travel klassifizieren.

Nicht mit festen universellen Grenzwerten arbeiten. Toleranzen anhand der Einheit, Rundung, Druckerauflösung und lokalen Daten adaptiv wählen.

---

# 5. Layer-Rekonstruktion ohne Kommentare

Eine Layergrenze darf nicht allein aus jedem Z-Wechsel abgeleitet werden: Z-Hop, Z-Offset, Homing, variable Layerhöhe, Spiral-Vase, nicht-planare Bahnen und Z-Kompensation können Z ändern, ohne einen neuen Layer zu beginnen.

## 5.1 Verfahren

1. Alle Z-Bewegungen und Z-Werte nach Parser-Normalisierung erfassen.
2. Z-Hops erkennen: kurzfristiges Anheben und Rückkehr auf vorheriges Druckniveau, meist im Kontext von Travel/Retract.
3. Wiederkehrende stabile Z-Niveaus und Extrusionsbewegungen clustern.
4. Z-Niveaus als Layer-Kandidaten gruppieren.
5. Layerhöhe aus Differenzen aufeinanderfolgender stabiler Niveaus schätzen.
6. Variable Layerhöhe zulassen; keine globale konstante Layerhöhe erzwingen.
7. Planare Layer, Spiral-Vase und nicht-planare Abschnitte getrennt kennzeichnen.
8. Layerwechsel-Konfidenz berechnen und bei widersprüchlicher Evidenz `UNKNOWN_LAYER_BOUNDARY` ausgeben.

## 5.2 Sonderfälle

- Erste Schicht kann eine andere Höhe besitzen.
- Raft kann eigene Layer vor dem Modell erzeugen.
- Support kann auf anderen Z-Niveaus oder mit Z-Gap zum Modell enden.
- Z-Hop darf keine künstliche Layer-ID erzeugen.
- Spiral-Vase: kontinuierlich ansteigendes Z während einer kontinuierlichen Wandbahn; keine normalen diskreten Layer erzwingen.
- Nicht-planare Druckpfade: klassische 2D-Layeranalyse ist nur eingeschränkt gültig.
- Mehrere Objekte können auf denselben Layern gedruckt werden; Layer und Objektkomponente sind getrennte Dimensionen.

---

# 6. Pfad-, Kontur- und Objekt-Rekonstruktion

## 6.1 Von Moves zu Pfaden

Extrusionsbewegungen zu Pfadsequenzen gruppieren. Ein neuer Pfad kann beginnen bei:

- Travel-Unterbrechung,
- Retract/Unretract,
- Toolchange,
- deutlichem räumlichem Sprung,
- Layerwechsel,
- Änderung der Extrusions-/Geometriecharakteristik.

Kurze Lücken und Rundungsfehler tolerieren. Nicht jede einzelne G1-Zeile ist ein eigenständiger Pfad.

## 6.2 Graph-Modell

Jede Bewegung ist eine gerichtete Kante zwischen Start- und Endpunkt. Endpunkte innerhalb einer geometrisch begründeten Toleranz können zu Knoten zusammengeführt werden.

Graphen verwenden für:

- zusammenhängende Pfade,
- geschlossene Loops,
- Verzweigungen,
- offene Linien,
- Inseln/Komponenten,
- Kreuzungen und Überlagerungen.

Nicht nur identische Endkoordinaten prüfen: Slicer können Koordinaten runden, Bögen approximieren oder Pfade mit kleinen Abständen erzeugen.

## 6.3 Loop-Erkennung

Ein Loop-Kandidat liegt vor, wenn ein zusammenhängender Extrusionspfad innerhalb einer Toleranz zum Startpunkt zurückkehrt.

Zusätzlich prüfen:

- Selbstüberschneidungen,
- Polygonfläche,
- Orientierung,
- Umfang,
- Abstand zu anderen Loops,
- Offset-Beziehungen,
- Zugehörigkeit zu einer Modellkomponente,
- Lage innerhalb/außerhalb anderer Konturen.

Ein geschlossener Loop ist nicht automatisch eine Außenwand. Er kann Lochwand, Innenwand, Skirt, Brim, Ooze Shield, Prime Tower oder eine geschlossene Infill-Struktur sein.

## 6.4 Konturhierarchie

Loops je Layer räumlich verschachteln und über Polygoncontainment/Topologie klassifizieren.

- Äußerster modellbegrenzender Loop: Outer-Wall-Kandidat.
- Verschachtelte modellinterne Loops: Inner-Wall-/Hole-Kandidaten.
- Isolierte externe Loops: Helper-/Skirt-/Shield-/Tower-Kandidaten.
- Konzentrische Loops allein beweisen keine Wandrolle.

Druckreihenfolge allein ist kein zuverlässiger Beweis für Outer/Inner Wall.

---

# 7. Geometrie-Engine und Layer-Topologie

## 7.1 Geometrische Repräsentation

Für jede Extrusionsbahn einen Linienkorridor bzw. ein geometrisches Footprint-Modell aufbauen. Die Bahn als reine Mittellinie zu betrachten reicht für Flächendichte und Überlappung nicht aus.

Die Geometrie soll mindestens unterstützen:

- Polygonisierung geschlossener Pfade,
- Buffer/Offset um Linien mit geschätzter Breite,
- Union, Intersection, Difference,
- Abstand zwischen Geometrien,
- Punkt-in-Polygon,
- Konturverschachtelung,
- Raster-/Voxel-Repräsentation als alternative Näherung.

2D-Vektor-Geometrie ist für planare Layer vorzuziehen. Voxelisierung kann ergänzend für komplexe 3D-Beziehungen verwendet werden.

## 7.2 Materialfläche vs. Toolpath-Footprint

Die aus den Mittellinien erzeugte Fläche ist nur eine Näherung des tatsächlich abgelegten Materials. Linienbreite, Layerhöhe, Querschnitt, Überlappung und Materialverformung beeinflussen den realen Footprint.

Speichere deshalb:
- Mittellinien-Geometrie,
- geschätzte Footprint-Geometrie,
- Unsicherheits-/Toleranzbereich.

## 7.3 Inter-Layer-Vergleich

Für Layer `n`:

- `A_n`: geschätzte Material-/Footprint-Fläche des aktuellen Layers.
- `A_(n-1)`: Fläche des darunterliegenden Layers.
- `A_(n+1)`: Fläche des darüberliegenden Layers.

Wichtige Differenzen:

- `A_n - A_(n+1)`: Top-Surface-Kandidaten (mit räumlicher Toleranz und nur bei gültiger Layerstruktur).
- `A_n - A_(n-1)`: nicht oder weniger gestützte Bereiche; Kandidaten für Bottom-/Overhang-/Bridge-Geometrie.
- `A_n ∩ A_(n-1)`: gestützte Fläche.
- `A_n ∩ A_(n+1)`: nach oben fortgesetzte Modellregion.

Boolesche Differenzen nicht als alleinigen Beweis verwenden. Überhänge können teilweise gestützt sein; Drucker überbrücken definierte Distanzen; Support kann die Fläche stützen; Layerhöhen können variieren.

---

# 8. Feature-Klassifikation: Evidenz kombinieren

Jeder Kandidat soll ein Evidenzprofil besitzen. Keine einzelne Heuristik darf allein entscheiden, wenn sie nicht wirklich definierend ist.

## 8.1 Feature-Scoring

Für jede Kandidatenklasse Merkmale erfassen, zum Beispiel:

- `geometry_score`
- `topology_score`
- `kinematic_score`
- `extrusion_score`
- `temporal_score`
- `pattern_score`
- `context_score`

Gewichte müssen konfigurierbar und später anhand gelabelter Testdaten kalibrierbar sein. Scores sind keine statistisch kalibrierten Wahrscheinlichkeiten, solange sie nicht auf Testdaten kalibriert wurden. In der Ausgabe klar zwischen `score` und `probability` unterscheiden.

Beispielhafte Entscheidungslogik:

- mehrere unabhängige starke Hinweise → hohe Konfidenz
- ein starker und mehrere schwache Hinweise → mittlere Konfidenz
- widersprüchliche Hinweise → niedrige Konfidenz / `AMBIGUOUS`
- zu wenig Daten → `UNKNOWN`

Klassifikator soll Top-3-Hypothesen mit Begründungen ausgeben können.

## 8.2 Outer Wall

Evidenz:
- äußerste modellbegrenzende Kontur eines Layer-/Objektquerschnitts,
- eine Seite grenzt an Außenraum, andere an Modellinneres,
- Kontur setzt sich über Layer konsistent als Modellgrenze fort,
- geschlossener Loop oder plausibler Teilpfad,
- geschätzte Linienbreite passt zur Wandstruktur.

Geschwindigkeit und Druckreihenfolge nur unterstützend verwenden. Langsam bedeutet nicht automatisch Outer Wall.

## 8.3 Inner Wall

Evidenz:
- liegt innerhalb der äußeren Modellkontur,
- ist Teil der verschachtelten Wandstruktur,
- Offset-Abstand ist plausibel im Verhältnis zur geschätzten Linienbreite,
- wiederholt sich über Layer konsistent.

Hole-Walls und Innenwände getrennt als Subtyp/Attribut führen, wenn die Geometrie dies zulässt.

## 8.4 Overhang Wall

Evidenz:
- Wandbahn liegt teilweise außerhalb der gestützten Fläche des vorherigen Layers,
- lokale Überhangdistanz/-fläche ist signifikant,
- Geometrie gehört weiterhin zur Modellgrenze,
- gegebenenfalls geänderte Geschwindigkeit oder Lüftersteuerung als Zusatzhinweis.

Nicht pauschal fordern, dass die gesamte Bahn ungestützt ist. Überhang ist lokal und kann segmentweise auftreten.

## 8.5 Top Surface

Evidenz:
- Region gehört zur Modellfläche,
- in höheren Modell-Layern wird sie nicht weiter überdeckt,
- typischerweise dichte parallele oder konzentrische Bahnen,
- Lage an der oberen Außenhaut eines Objekts.

Achtung: Ein einzelner nächster Layer ohne Überdeckung reicht nicht, wenn variable Layerhöhen, Inseln oder nicht-planare Bahnen vorkommen. Über mehrere obere Layer und räumliche Toleranzen prüfen.

## 8.6 Bottom Surface

Evidenz:
- Region ist Modellunterseite bzw. erste Modelloberfläche,
- liegt auf Bett/Raft oder über einer Support-Struktur,
- darunter existiert keine Modellfortsetzung,
- typischerweise dichtes Oberflächenmuster.

Bottom Surface und Support Interface dürfen nicht verwechselt werden. Die Rollen können direkt benachbart sein.

## 8.7 Solid Infill vs. Sparse Infill

- Linienabstand und Footprint-Breite vergleichen.
- Hohe Flächenabdeckung deutet auf Solid Infill.
- Deutlich größere Abstände deuten auf Sparse Infill.
- Muster über mehrere Pfade/Regionen statistisch bewerten.
- Interne Solid Layers können zwischen Sparse Infill und Top/Bottom liegen.

Keine universellen Schwellen wie `D == w` oder `D == 5w` als harte Regel verwenden. Überlappung, Linienform, Flow und Geometrie verändern die effektive Abdeckung.

## 8.8 Bridge / Internal Bridge

Evidenz:
- Extrusionspfad über einer lokal ungestützten Region,
- Enden/Teilabschnitte sind an tragfähigen Bereichen verankert,
- meist lineare oder parallele Bahnen,
- lokaler Vergleich zum darunterliegenden Layer zeigt fehlende Stützung,
- Flow, Geschwindigkeit und Lüfter können abweichend sein.

Eine Bridge kann nicht allein aus erhöhtem Flow oder `M106 S255` bewiesen werden. Lüftersteuerung ist nur Kontext. Interne Bridges können über Infill-/Hohlräumen liegen und sind nicht zwingend über vollständig leerem Raum.

## 8.9 Gap Fill

Evidenz:
- kurze, oft variable Extrusionssegmente,
- räumlich in schmalen Restlücken zwischen Wänden,
- lokale Lückenbreite ist kleiner als eine reguläre Linienbreite bzw. passt nicht zu normalem Infill,
- Flow/Breite kann dynamisch variieren.

Kurze Segmente allein beweisen kein Gap Fill.

## 8.10 Ironing

Evidenz:
- sehr geringer Extrusionsfluss im Verhältnis zur Weglänge,
- sehr dichtes, flächiges Muster,
- liegt auf einer bereits gedruckten Top-Surface,
- meist langsame Bewegung.

`E ≈ 0` ist kein alleiniger Beweis. Auch Travel, Wipe und andere Sonderbewegungen können geringe oder keine Extrusion besitzen.

## 8.11 Support Base / Interface / Transition

Support ist nicht einfach „alles außerhalb der Modell-Bounding-Box“.

Evidenz für Support:
- Region ist nicht Teil der fortgesetzten Modellkontur,
- liegt unter zukünftigen Modellüberhängen,
- räumliche Stützbeziehung zum Modell ist plausibel,
- besitzt eigene Komponenten/Footprints und oft eigenes Muster,
- endet oder verändert sich in der Nähe des zu stützenden Modellbereichs.

Support Interface:
- dichte Zone an der Kontaktseite zum Modell,
- unmittelbar unter/über der zu stützenden Modellfläche,
- oft nur wenige Layer tief,
- Übergang von lockerer Support Base zu dichter Interface-Zone.

Support Transition:
- graduelle oder stufenartige Änderung zwischen Support Base und Interface.

Support kann innerhalb der XY-Projektion des Modells liegen. Daher nicht nur auf „außerhalb der Modell-Bounding-Box“ prüfen.

## 8.12 Skirt / Brim / Raft

Skirt:
- frühe Layerbewegung,
- isolierte geschlossene oder offene Priming-Kontur,
- außerhalb der Modellkontur,
- kein Kontakt zum Modell.

Brim:
- erste Layer,
- an Modell- oder Support-Fußkontur angrenzende, meist konzentrische Linien,
- vergrößert die Kontaktfläche.

Raft:
- mehrlagige Hilfsstruktur unter dem Modell,
- eigene Geometrie/Layerfolge,
- Modell beginnt oberhalb bzw. auf einer Raft-Oberfläche,
- Z-Gap und Schichtstruktur als Hinweise.

Mouse Ears:
- lokale, begrenzte Haftungsinseln an ausgewählten Ecken/Randbereichen.

Erste Schicht plus geschlossener Loop ist allein keine ausreichende Klassifikation.

## 8.13 Prime Tower / Wipe Tower / Ooze Shield

Prime/Wipe Tower:
- isolierte, meist kompakte Komponente,
- wiederholt über viele Layer,
- Toolchange-/Materialwechsel-Ereignisse können zeitlich damit korrelieren,
- geometrisch nicht Teil des Modells.

Ooze Shield / Wipe Wall:
- separate Wand um das Modell oder bestimmte Komponenten,
- über mehrere Layer fortgesetzt,
- Abstand zur Modellkontur,
- kann dünnwandig und offen/geschlossen sein.

Ein isolierter Turm ist nicht automatisch ein Prime Tower. Ohne Toolchange-/Purge-Kontext nur `AUXILIARY_TOWER_CANDIDATE`.

---

# 9. Infill- und Oberflächenmuster erkennen

Pattern-Erkennung nach Pfadrekonstruktion und Feature-Regionierung durchführen.

## 9.1 Lineare Muster

- Rectilinear / Lines: parallele Linien mit annähernd konstantem Abstand.
- Aligned Rectilinear: ähnliche Orientierung über Layer hinweg.
- Grid: zwei sich kreuzende Richtungsfamilien im selben Layer.
- Triangles / Tri-Hexagon: drei Richtungsfamilien, typischerweise mit 60°/120° Beziehungen.
- Zig-Zag: zusammenhängender Mäander mit Richtungswechseln.
- Cross / Cross 3D: sich kreuzende bzw. über Layer variierende Linienstruktur.

## 9.2 Räumlich variierende Muster

- Cubic / Adaptive Cubic / Support Cubic / Quarter Cubic / Octet: Layer-zu-Layer-Verschiebungen und wechselnde Richtungs-/Schnittstrukturen untersuchen.
- Gyroid: kontinuierliche gekrümmte Pfade und periodische räumliche Phasenänderung; nicht nur „keine scharfen Winkel“ als Kriterium verwenden.
- Honeycomb / 3D Honeycomb: hexagonale Zellen und 60°/120°-Geometrie.
- Lightning: baumartige, verzweigte Strukturen, deren Äste Modellbereiche/Topflächen stützen.
- Organic/Tree: verzweigte, verjüngte Stützstrukturen; als Support-Form klassifizieren.

## 9.3 Concentric und Spiral

- Concentric: verschachtelte Konturen/Offsets, die der Region folgen.
- Archimedean Chords / Octagram Spiral: spiralige oder stern-/bogenartige Sequenzen.
- Hilbert Curve: rekursive/fraktale, oft orthogonale Kurzsegmentstruktur.

## 9.4 Top-/Bottom-/Solid-Muster

- Rectilinear
- Monotonic / Monotonic Lines
- Concentric
- Hilbert Curve
- Archimedean/Spiral

Das Muster ist nicht gleich der Feature-Rolle: Rectilinear kann Sparse Infill, Solid Infill, Top Surface, Bottom Surface oder Support Interface sein.

---

# 10. Multi-Pass-Analyse – verbindliche Ausführungsreihenfolge

Die Analyse muss vollständig sein, bevor endgültige Feature-Tags vergeben werden.

### Pass 0 – Rohdaten und Kommentar-Extraktion
- Originaldatei unverändert sichern.
- Kommentare/Tags extrahieren.
- Erkannte Slicer-Marker und Aliase normalisieren.
- Kommentar-Evidenz getrennt von Geometrie-Evidenz speichern.
- Kommentare können fehlen, unvollständig oder falsch sein; sie sind Evidenz, kein Ersatz für Parserzustand.

### Pass 1 – Syntax- und Zustandsrekonstruktion
- Jede Zeile tokenisieren.
- Modalzustand aktualisieren.
- Koordinaten, Tools, E-Modi, Einheiten, Offsets und Feedrate auflösen.
- Warnungen und unbekannte Befehle protokollieren.

### Pass 2 – Bewegungsrekonstruktion
- G0/G1/G2/G3 in normalisierte Moves überführen.
- Bogenlängen berechnen.
- Extrusion, Retract, Unretract, Travel, Wipe und Sonderereignisse trennen.

### Pass 3 – Layer- und Z-Struktur
- Layerkandidaten und Z-Niveaus clustern.
- Z-Hops, variable Layerhöhe, Raft, Spiral-Vase und nicht-planare Bereiche berücksichtigen.
- Unsichere Layergrenzen markieren.

### Pass 4 – Extrusions- und Kinematikprofile
- Feedrate, Weglänge, E-/Volumenänderung, Flow-Fläche, Tool und Lüfterkontext erfassen.
- Cluster pro Tool, Layer und Bewegungstyp bilden.
- Relative Profile statt globaler fixer Grenzwerte nutzen.

### Pass 5 – Pfad- und Komponentenbildung
- Moves zu Pfaden zusammenfassen.
- Loops, offene Pfade, Inseln, Verzweigungen und zusammenhängende Komponenten erkennen.
- Travel-Verbindungen und Toolchange-Unterbrechungen beachten.

### Pass 6 – 2D-Geometrie je Layer
- Footprints schätzen.
- Polygone, Offsets, Verschachtelungen, Abstände und Dichtekarten bilden.
- Modellgrenzen und externe Hilfsstrukturen als Hypothesen trennen.

### Pass 7 – Inter-Layer-/3D-Topologie
- Gestützte und ungestützte Bereiche berechnen.
- Top-/Bottom-/Overhang-/Bridge-/Support-Beziehungen ermitteln.
- Über mehrere Layer hinweg verfolgen.

### Pass 8 – Feature-Klassifikation
- Feature-Scoring aus allen Evidenzarten.
- Top-3-Hypothesen und Konflikte ausgeben.
- `UNKNOWN`/`AMBIGUOUS` zulassen.

### Pass 9 – Pattern-Erkennung
- Linienfamilien, Winkelverteilungen, Periodizität, Kreuzungen, Kurven und Layer-Phasen analysieren.
- Muster unabhängig von Feature-Rolle ausgeben.

### Pass 10 – Konsistenzprüfung
- Prüfen, ob Klassifikationen über Layer hinweg plausibel fortgesetzt werden.
- Widersprüche erkennen.
- Geometrie- und Extrusionssummen gegen die ursprünglichen Moves validieren.
- Keine Bewegung darf verloren gehen oder doppelt gezählt werden.

### Pass 11 – Ausgabe / Post-Processing
- JSON und Bericht erzeugen.
- Optional kommentierte G-Code-Kopie erstellen.
- Originaldatei nicht überschreiben.
- Neu eingefügte Kommentare müssen eindeutig als Analyse-Kommentare gekennzeichnet sein.

---

# 11. Datenmodell und Ausgabeformat

## 11.1 Jede Bewegung behält Rohdaten und Analyse

Empfohlene Felder:

- `id`, `source_line_start`, `source_line_end`, `raw_gcode`
- `command`, `tool_id`
- `start_xyz`, `end_xyz`
- `e_start`, `e_end`, `delta_e`
- `feedrate`, `units`, `coordinate_mode`, `extrusion_mode`
- `path_length_xy`, `path_length_xyz`, `arc_length`
- `extrusion_volume_estimate`, `effective_cross_section`
- `layer_id`, `layer_confidence`
- `path_id`, `component_id`, `object_candidate_id`
- `motion_type`
- `feature_primary`, `feature_alternatives`
- `pattern_type`
- `confidence_score`, `confidence_level`
- `evidence[]`, `warnings[]`

## 11.2 Beispiel für Feature-Ergebnis

```json
{
  "entity_id": "path_00421",
  "feature_primary": "TOP_SURFACE",
  "feature_alternatives": [
    {"feature": "SOLID_INFILL", "score": 0.22},
    {"feature": "SUPPORT_INTERFACE", "score": 0.04}
  ],
  "pattern": "RECTILINEAR",
  "confidence": {
    "score": 0.91,
    "level": "HIGH",
    "calibrated_probability": null
  },
  "evidence": [
    "dense_parallel_paths",
    "region_is_not_covered_by_higher_model_layers",
    "region_belongs_to_model_boundary"
  ],
  "uncertainties": [
    "original_slicer_role_not_observable"
  ]
}
```

Scores im Beispiel sind illustrativ, nicht vorab festgelegte Wahrheiten.

## 11.3 Aggregierte Layer-/Objektausgabe

Je Layer ausgeben:
- Z-Niveau / Layerhöhe / Layer-Konfidenz
- Bounding Box
- geschätzte Modellkomponenten
- Flächenanteile nach Feature
- Pfadanzahl und Extrusionsvolumen je Feature
- erkannte Muster
- Unsicherheitsregionen

Je Objektkandidat:
- räumliche Bounding Box
- Layerbereich
- Kontur-/Komponentenverlauf
- getrennte Hilfsstrukturen
- Feature-Verteilung

---

# 12. Post-Processing-Regeln

Wenn die Engine den G-Code annotiert:

1. Niemals Bewegungsbefehle, Koordinaten, E-Werte, F-Werte oder Reihenfolge verändern.
2. Originaldatei unverändert lassen und neue Datei erzeugen.
3. Kommentare nur an sicheren Segmentgrenzen einfügen.
4. Bei Segmenten mit gemischten Rollen keine falsche Einzelrolle erzwingen.
5. `UNKNOWN` und `AMBIGUOUS` explizit erhalten.
6. Slicer-Originalkommentare nicht löschen.
7. Analyse-Kommentare mit eigenem Namespace kennzeichnen, z. B. `;RE_ANALYSIS:FEATURE=TOP_SURFACE;CONF=0.91`.
8. Sicherstellen, dass Kommentare für Ziel-Firmware und G-Code-Viewer unkritisch sind.
9. Vorher-/Nachher-Prüfung: Alle nicht-kommentarbezogenen G-Code-Befehle müssen identisch bleiben.
10. Optional getrennte Sidecar-Datei statt G-Code-Kommentaren bevorzugen.

---

# 13. Validierung und Teststrategie

Ohne ein belastbares Testsystem ist die Engine nicht vertrauenswürdig.

## 13.1 Testdatensatz

G-Code-Dateien aus unterschiedlichen Slicer-Familien und Profilen sammeln:

- Cura
- PrusaSlicer
- OrcaSlicer
- Bambu Studio
- SuperSlicer
- Simplify3D
- FlashPrint
- ideaMaker
- Kiri:Moto
- KISSlicer
- MatterSlice/MatterControl
- weitere verfügbare Dialekte

Für jeden Slicer sowohl kommentierte als auch vollständig entkommentierte Varianten verwenden. Entkommentierung darf nur Kommentartext entfernen, nicht Befehle verändern.

## 13.2 Feature-Testfälle

Mindestens:
- einfache Würfel ohne Support
- mehrere Wände und Lochgeometrien
- dünne Wände / Single Extrusion
- Gap Fill
- Top/Bottom/Solid/Sparse Infill
- Grid, Gyroid, Honeycomb, Cubic, Concentric, Lightning
- Bridge und Internal Bridge
- Overhang
- normaler Support, Interface, Roof/Floor, Tree Support
- Skirt, Brim, Mouse Ears
- Raft mit mehreren Raft-Layern
- Prime/Wipe Tower
- Ooze Shield / Wipe Wall
- Multi-Tool / Farbwechsel / Flush
- Z-Hop und Firmware-Retract
- variable Layerhöhe
- Spiral-Vase
- Arc-Moves
- G-Code mit G92, M82/M83 und Toolwechseln
- ungewöhnliche Start-/End-G-Code-Blöcke

## 13.3 Testmetriken

Nicht nur Gesamtgenauigkeit messen. Pro Feature:
- Precision
- Recall
- F1-Score
- Confusion Matrix
- Anteil `UNKNOWN`
- Anteil `AMBIGUOUS`
- Konfidenzkalibrierung
- Layer-Rekonstruktionsfehler
- Geometrische Abweichung (z. B. Hausdorff-Distanz)
- Volumen-/Extrusionssummen-Abweichung
- Laufzeit und Speicherbedarf

Wichtig: Die Ground Truth muss aus den ursprünglichen Feature-Kommentaren, Slicer-Projektdaten oder einer verlässlichen Referenz stammen. Bei kommentarlosen Dateien allein kann keine unabhängige Ground Truth für die ursprüngliche semantische Absicht entstehen.

## 13.4 Ablation Tests

Jeweils einen Evidenzkanal deaktivieren und messen:
- ohne Kinematik
- ohne Flow
- ohne Inter-Layer-Topologie
- ohne Pfadgraph
- ohne Musteranalyse
- ohne Kommentare

So lässt sich feststellen, welche Verfahren tatsächlich helfen und welche nur scheinbar nützlich sind.

## 13.5 Regressionstests

Jede Parser- oder Klassifikationsänderung muss gegen einen festen Korpus laufen. Bewegungsrekonstruktion muss deterministisch bleiben. Fehlerhafte oder unbekannte G-Code-Zeilen dürfen nicht stillschweigend ignoriert werden.

---

# 14. Häufige Fehlannahmen, die ausdrücklich vermieden werden müssen

1. `E > 0` ist nicht universell gleich Extrusion: absolute/relative Modi, G92, Toolwechsel, Firmware-Retract und volumetrische Modi beachten.
2. `E <= 0` ist nicht automatisch Travel.
3. Jede Z-Änderung ist kein Layerwechsel.
4. Jede geschlossene Kontur ist keine Außenwand.
5. Der äußerste Loop einer gesamten Layer-Bounding-Box ist nicht zwingend die Außenwand eines Modells; mehrere Objekte und Hilfsstrukturen können vorhanden sein.
6. Support liegt nicht immer außerhalb der Modell-Bounding-Box.
7. Hoher Lüfterwert beweist keine Bridge.
8. Hoher Flow beweist keine Bridge.
9. Sehr geringer Flow beweist kein Ironing.
10. Hohe Linien-Dichte beweist allein keine Top Surface.
11. Fehlende Überdeckung im direkt nächsten Layer beweist nicht immer Top Surface.
12. Fehlende Stützung im vorherigen Layer beweist nicht immer Bridge; es kann Overhang, Support-Gap oder eine andere Geometrie sein.
13. Druckreihenfolge beweist keine Feature-Rolle.
14. Geschwindigkeit ist profilabhängig und darf nicht als universeller Klassifikator verwendet werden.
15. Feature-Rolle und Infill-Muster sind getrennte Dimensionen.
16. Kommentare können fehlen oder falsch sein; sie sind eine Evidenzquelle, keine absolute Wahrheit.
17. Slicer-interne Preview-Klassen sind nicht zwingend als G-Code-Kommentar serialisiert.
18. Eine vollständig rekonstruierte Werkzeugbahn ist nicht dasselbe wie die ursprüngliche CAD-Geometrie oder die ursprüngliche Slicer-Absicht.

---

# 15. Implementierungsreihenfolge für die Coding-KI

Nicht alles gleichzeitig implementieren. In dieser Reihenfolge vorgehen:

**Phase 1 – zuverlässiger G-Code-Parser**
- Tokenizer
- Modal State Machine
- G0/G1
- M82/M83/G90/G91/G92/G20/G21
- Toolwechsel
- Move-Normalisierung
- Parser-Tests

**Phase 2 – Extrusion und Layer**
- ΔE / Retract / Unretract
- Weglänge und Volumenschätzung
- Z-Hop-Erkennung
- Layer-Clustering
- variable Layerhöhen

**Phase 3 – Pfade und 2D-Geometrie**
- Pfadgruppen
- Loop-Erkennung
- Komponenten
- Polygon-/Buffer-/Boolean-Operationen
- Konturhierarchie

**Phase 4 – 3D-Topologie**
- Layervergleich
- Top/Bottom/Overhang
- Bridge-Kandidaten
- Support-Beziehungen

**Phase 5 – Feature-Klassifikation**
- regelbasierte Evidenz
- Score/Alternativen/Unknown
- Feature-Matrix
- Pattern-Erkennung

**Phase 6 – Ausgabe und Post-Processing**
- JSON
- Diagnosebericht
- optionale G-Code-Kommentare
- unveränderte Bewegungsprüfung

**Phase 7 – Kalibrierung**
- diverse Slicer-Testdaten
- gelabelte Referenzen
- Konfidenzkalibrierung
- Regression und Performance

---

# 16. Abnahmekriterien

Die Implementierung ist erst dann als belastbar anzusehen, wenn:

- Parser-Modi für absolute/relative Koordinaten und Extrusion nachweislich korrekt funktionieren.
- `G92` nicht als Bewegung fehlinterpretiert wird.
- Toolwechsel die E-Zustände korrekt behandeln.
- G2/G3-Bögen korrekt vermessen werden, wenn sie vorkommen.
- Z-Hop nicht als Layerwechsel gezählt wird.
- variable Layerhöhe unterstützt wird.
- Bewegungen weder verloren noch doppelt gezählt werden.
- Layer-/Pfad-/Komponenten-IDs reproduzierbar sind.
- Feature-Klassen unabhängig vom Infill-Muster ausgegeben werden.
- jede Klassifikation Evidenz und Unsicherheit enthält.
- `UNKNOWN` nicht als Fehler, sondern als notwendiger korrekter Ausgang unterstützt wird.
- Post-Processing keine Bewegungsdaten verändert.
- Testmetriken pro Slicer und Feature dokumentiert sind.

---

# 17. Arbeitsauftrag an die Coding-KI

Implementiere eine modulare, testbare G-Code-Reverse-Engineering-Engine gemäß diesem Dokument.

**Priorität 1 ist die semantisch korrekte Rekonstruktion der Maschinenbewegungen.** Erst wenn Parser und Modalzustand korrekt sind, darf Geometrie analysiert werden. Baue keine Feature-Heuristiken auf unzuverlässig geparsten Rohzeilen auf.

Arbeite inkrementell. Liefere für jede Phase:
1. Architektur und Datenmodelle,
2. Implementierung,
3. automatisierte Tests,
4. bekannte Grenzen,
5. messbare Ergebnisse auf Testdateien.

Nutze keine pauschalen festen Grenzwerte, wenn sie aus den Daten adaptiv geschätzt werden können. Trenne harte Fakten von Hypothesen. Bei nicht unterscheidbaren Fällen muss die Engine `UNKNOWN` oder `AMBIGUOUS` melden und die konkurrierenden Interpretationen benennen.

**Das Endziel ist maximale nachweisbare Rekonstruktionsqualität bei vollständiger Transparenz über Unsicherheiten – nicht eine künstlich erzwungene 100-%-Klassifikation.**
