von Grok:


Ich hole die aktuellen, offiziellen Listen der Feature-Kommentare (Extrusion Roles) und aller Infill-Muster aus den wichtigsten Slicer-Familien, damit die Definitionen eindeutig und vollständig sind.Ich hole die genauen String-Definitionen und vollständigen Infill-Listen aus den Quellcodes und Docs.Noch ein paar präzise Quellen für die exakten Kommentar-Strings und Infill-Listen.**Vollständige und eindeutig definierte Feature-Kommentare + alle Infill-Muster**

Hier die klare, eindeutige Definition aller relevanten Feature-/Extrusion-Role-Kommentare und der Infill-Muster der großen Slicer-Familien. Die Kommentare erscheinen nur, wenn „Verbose G-code“ / „G-code comments“ / Feature-Tags aktiviert sind. Schreibweise kann je nach Version leicht variieren (Leerzeichen, Groß-/Kleinschreibung, Übersetzungen).

---

### 1. Feature-Kommentare (Extrusion Roles / Line Types) – eindeutig definiert

#### A. PrusaSlicer-Familie  
(PrusaSlicer, SuperSlicer, **OrcaSlicer**, Bambu Studio)

Format: `;TYPE:XXX` (manchmal mit Leerzeichen oder Unterstrich-Varianten in Custom-G-Code-Platzhaltern wie `{extrusion_role}`).

| Kommentar (`;TYPE:`)              | Eindeutige Definition |
|-----------------------------------|-----------------------|
| **Perimeter** / Internal perimeter | Innere Wände / Shells (nicht die äußerste sichtbare Wand) |
| **External perimeter**            | Äußerste sichtbare Wand / Outer Wall (Oberfläche) |
| **Overhang perimeter**            | Perimeter an Überhängen (meist mit Bridge-Flow/Speed) |
| **Internal infill**               | Sparse/Internal Infill (niedrige Dichte, Muster) |
| **Solid infill**                  | Solides Innen-Infill (z. B. zwischen Top/Bottom und Sparse) |
| **Top solid infill**              | Oberste solide Schichten (Top Surface) |
| **Bottom surface** / Bottom solid infill | Untere solide Schichten (Bottom Surface) – stark in Orca/Bambu |
| **Ironing**                       | Ironing-Pass (glättende Überfahrt über Top-Surfaces) |
| **Bridge infill**                 | Brücken (über freiem Raum, meist 100 % und spezieller Flow) |
| **Internal Bridge Infill**        | Interne Brücken (Orca) |
| **Gap fill**                      | Füllen von kleinen Lücken zwischen Perimetern/Infill |
| **Skirt**                         | Skirt (Umriss um das Objekt, oft ohne Haftung) |
| **Brim**                          | Brim (Haftungs-Rand am Objekt) |
| **Support material**              | Normaler Support / Stützen |
| **Support material interface**    | Support-Interface (dichte Schicht zum Modell) |
| **Support Transition**            | Übergangszone Support → Interface (Orca) |
| **Wipe tower** / Prime tower      | Wipe-/Prime-Tower (Multi-Material) |
| **Custom**                        | Manuell eingefügter Custom-G-Code |
| **Mixed**                         | Sammlung mit mehreren Rollen |
| **None** / Unknown                | Keine / unbekannte Rolle |

Zusätzliche Layer-Marker: `;LAYER_CHANGE`, `;HEIGHT:x.xx`, `;BEFORE_LAYER_CHANGE`, `;AFTER_LAYER_CHANGE`, `;COLOR_CHANGE`, `;PAUSE_PRINT` usw.

#### B. Cura-Familie (Ultimaker Cura + Ableger)

Format: `;TYPE:XXX`

| Kommentar (`;TYPE:`)       | Eindeutige Definition |
|----------------------------|-----------------------|
| **WALL-OUTER**             | Äußere Wand (Outer Wall) |
| **WALL-INNER**             | Innere Wände (Inner Walls) |
| **SKIN**                   | Top- und Bottom-Surfaces (solide Haut) |
| **FILL**                   | Sparse Infill |
| **SKIRT**                  | Skirt |
| **BRIM**                   | Brim (in neueren Versionen) |
| **SUPPORT**                | Support |
| **SUPPORT-INTERFACE**      | Support-Interface / Roof/Floor |
| **PRIME-TOWER** / Wipe tower | Prime Tower |
| **RAFT** (ggf. RAFTBASE, RAFTINTERFACE, RAFTSURFACE) | Raft-Teile |
| **IRONING**                | Ironing (neuere Versionen) |

Weitere: `;MESH:Dateiname`, `;LAYER:n`, `;LAYER_COUNT:`, `;TIME_ELAPSED:`.

Travels werden meist **nicht** explizit getaggt (erkennbar am fehlenden oder negativen E-Wert).

#### C. Simplify3D

Format: `; feature XXX` (klein geschrieben, mit Leerzeichen)

| Kommentar (`; feature ...`)          | Eindeutige Definition |
|--------------------------------------|-----------------------|
| **outer perimeter**                  | Äußere Perimeter |
| **inner perimeter**                  | Innere Perimeter |
| **solid layer**                      | Solide Top/Bottom-Schichten |
| **infill**                           | Sparse Infill |
| **support**                          | Support |
| **dense support**                    | Dichter Support / Interface |
| **skirt**                            | Skirt |
| **brim**                             | Brim (oft unter skirt oder separat) |
| **bridge**                           | Brücken |
| **gap fill**                         | Gap Fill |
| **ooze shield**                      | Ooze Shield (Multi-Extruder) |
| **prime pillar**                     | Prime Pillar / Tower |
| **raft**                             | Raft |
| **ironing**                          | Ironing |
| **external single extrusion**        | Dünne äußere Single-Extrusion-Wände |
| **internal single extrusion**        | Dünne innere Single-Extrusion-Wände |

Layer-Marker: `; layer N, Z = x.xxx` + oft `; tool H0.xxx W0.xxx`.

#### D. Weitere (kurz)

- **ideaMaker**: Eher sparsam oder custom; oft über Layer-Change-G-Code erzwungen.
- **Original Slic3r**: Sehr ähnlich Prusa (`;TYPE:Perimeter` etc.).

---

### 2. Alle Infill-Muster inkl. Definition (pro Familie)

Infill-Muster steuern die interne Struktur bei < 100 % Dichte. Top/Bottom haben oft separate Muster (Solid Infill / Surface Pattern).

#### A. PrusaSlicer / OrcaSlicer / Bambu (umfangreichste Liste)

**Sparse Infill (fill_pattern / sparse_infill_pattern):**

| Muster                  | Definition / Eigenschaften |
|-------------------------|----------------------------|
| **Rectilinear**         | Parallele Linien, Richtung wechselt pro Layer (0°/90°). Schnell, einfach, schwächer in Z. |
| **Aligned Rectilinear** | Alle Linien in gleicher Richtung ausgerichtet. |
| **Grid**                | Kreuzendes Gitter (Linien kreuzen sich). Stark in XY, mehr Material an Kreuzungen. |
| **Triangles**           | Dreiecksnetz. Sehr steif in XY. |
| **Stars** / **Tri-hexagon** | Sterne bzw. Dreiecke + Hexagone. Gute allseitige Steifigkeit. |
| **Cubic**               | 3D-Würfel (Ecke nach unten). Isotrop, gute Festigkeit in allen Richtungen. |
| **Adaptive Cubic**      | Cubic, dichter nah an den Wänden, spärlicher innen → Materialersparnis. |
| **Support Cubic**       | Leichte Cubic-Variante, vor allem zur Stützung der Top-Schichten. |
| **Quarter Cubic**       | Abgewandelte Cubic-Struktur. |
| **Line**                | Einzelne parallele Linien (sehr spärlich). Sehr schnell, wenig Material. |
| **Concentric**          | Konzentrische Ringe von außen nach innen. Gut für flexible Teile / 100 %. |
| **Honeycomb**           | 2D-Waben. Sehr starkes Gewicht/Festigkeit-Verhältnis, langsam. |
| **3D Honeycomb**        | 3D-Wabenstruktur. |
| **Gyroid**              | Wellenförmige TPMS-Struktur. Isotrop, keine Selbstüberschneidungen, schnell, schön, flüssigkeitsdurchlässig möglich. **Meist empfohlener Allrounder**. |
| **Hilbert Curve**       | Raumfüllende Hilbert-Kurve. Kontinuierlich, wenig Retracts. |
| **Archimedean Chords**  | Archimedische Spiralen/Sehnen. |
| **Octagram Spiral**     | Oktagramm-Spiralen. |
| **Lightning**           | Extrem spärlich – nur Stützbäume für die Top-Surface. Minimaler Material- & Zeitverbrauch (nur für Optik). |
| **Zig Zag**             | Durchgehende Zickzack-Linien (Orca). |
| **Cross Zag / Locked Zag** | Varianten von Zickzack mit Verriegelung. |
| **Cross Hatch**         | Kreuzschraffur. |
| **TPMS-D / TPMS-FK**     | Weitere Triply Periodic Minimal Surfaces (Orca). |
| **Lateral Honeycomb / Lattice** | Seitliche Waben/Gitter (Orca). |
| **Spiral Inset**        | Spiralförmig einwärts. |
| **Monotonic / Monotonic Lines** | Für Solid/Top/Bottom: gleichmäßige Richtung ohne Richtungswechsel-Artefakte (glattere Oberflächen). |

**Top/Bottom/Solid-Infill** haben oft eigene Auswahl (Rectilinear, Monotonic, Concentric, Hilbert etc.).

#### B. Cura-Familie

Standard-Liste (ca. 14 + Plugins):

| Muster                  | Definition / Eigenschaften |
|-------------------------|----------------------------|
| **Grid**                | Kreuzendes Gitter. Schnell, gut für Standard. |
| **Lines**               | Parallele Linien (wechselt Richtung). Sehr schnell, wenig Material. |
| **Triangles**           | Dreiecksnetz. Stark in XY. |
| **Tri-Hexagon**         | Dreiecke + Hexagone. Sehr gute allseitige Steifigkeit. |
| **Cubic**               | 3D-Würfel. Isotrop. |
| **Cubic Subdivision**   | Adaptive Cubic-Variante (weniger Material). |
| **Octet**               | Tetraeder-/Oktaeder-Struktur. |
| **Quarter Cubic**       | Abgewandelte Cubic. |
| **Concentric**          | Konzentrische Ringe. Gut flexibel / 100 %. |
| **Zig Zag**             | Durchgehender Zickzack. |
| **Cross**               | 2D-Kreuzmuster. |
| **Cross 3D**            | 3D-Kreuz. Flexibler. |
| **Gyroid**              | Wellenförmig, isotrop, stark & schnell. |
| **Lightning**           | Extrem spärliche Stützstruktur nur für Tops. |

**Plugins** (Tiled Infill etc.): Honeycomb und Custom-Muster (WKT).

#### C. Simplify3D

Weniger Auswahl, klassisch:

- **Rectilinear** (Standard)
- **Grid**
- Weitere je nach Version: Concentric, Honeycomb-ähnliche, Fast Honeycomb etc.  
  (Hauptsächlich über „External Infill Pattern“ und Winkel steuerbar). Top/Bottom oft Rectilinear/Monotonic-ähnlich.

---

### Praktische Hinweise

- **Empfehlungen**:  
  – Allgemein / funktional: **Gyroid** 15–25 %  
  – Schnell/Prototyp: Lines / Rectilinear / Lightning  
  – Max. Steifigkeit XY: Triangles / Tri-Hexagon / Grid  
  – Isotrop + stark: Cubic / Gyroid  
  – Material sparen bei großen Teilen: Adaptive Cubic / Lightning / Support Cubic  

- Feature-Kommentare sind ideal für Post-Processing (z. B. unterschiedliche PA, Flow, Fan, Acceleration pro Rolle via `{REPLACE}` oder Change-Extrusion-Role-G-Code).

- Die genauen Strings können in Nightlies leicht abweichen; prüfe bei Bedarf mit einem kleinen Test-G-Code.

Falls du eine **Tabelle als CSV/Markdown zum Kopieren**, nur eine Familie detaillierter, Top/Bottom-Muster separat oder Beispiele aus realem G-Code brauchst, sag einfach Bescheid!


Das ist eine exzellente und tiefe Frage. Um ein 3D-Modell in G-Code zu übersetzen, nutzt ein Slicer im Hintergrund **Boolesche Geometrie** (Schnittmengen, Vereinigungen, Differenzen) und **Polygon-Offsets** (2D-Versatz). 

Im Folgenden definiere ich jedes Feature so exakt und „mathematisch“ wie möglich. Danach zeige ich, wie sich die Slicer-Familien aufteilen (inklusive der Exoten), und erkläre ausführlich das mächtige Werkzeug des Post-Processings.

---

### TEIL 1: Die „mathematische“ Definition aller Slicer-Features

Stell dir vor, das 3D-Modell wird in horizontale Scheiben (Layer) geschnitten. Jeder Layer $L_n$ ist ein 2D-Polygon (oder eine Menge von Polygonen). Die Linienbreite der Düse sei $w$.

#### 1. Wände / Perimeter
*   **Außenwand (Outer Wall / External Perimeter):** 
    *   **Definition:** Die Menge der Werkzeugbahnen, die exakt durch einen inneren Offset der Modell-Außenkante um $w/2$ entsteht. Ihre Normalenvektoren (Senkrechten) zeigen direkt in den leeren Raum außerhalb des Modells. Sie ist die physikalische Grenze des Bauteils.
*   **Innenwand (Inner Wall / Internal Perimeter):** 
    *   **Definition:** Iterative innere Offsets der Außenwand um jeweils $w$. Sie liegen vollständig innerhalb des Bauteils und haben direkten Kontakt zu einer Außen- oder weiteren Innenwand, aber **nicht** zur Umgebungsluft.
*   **Überhang-Perimeter (Overhang Perimeter):**
    *   **Definition:** Der Teil einer Außen- oder Innenwand im Layer $L_n$, der bei einer geometrischen Projektion nach unten auf den vorherigen Layer $L_{n-1}$ **keine** Schnittmenge (Kollision) mit dem dortigen Material hat (oder nur zu einem Anteil < $x\%$, entsprechend einem Schwellenwinkel). Er „hängt in der Luft“.

#### 2. Oberflächen & Füllung (Infill)
Das Innere des Polygons abzüglich der Wände nennen wir den *Kern-Bereich (Core)*.
*   **Top Surface / Top Solid Infill (Oberste Schicht):**
    *   **Definition:** Die Boolesche Differenz aus dem Polygon von Layer $L_n$ minus dem Polygon des darüberliegenden Layers $L_{n+1}$. Es ist der Bereich, über dem „Nichts“ mehr vom Modell kommt. Er wird mit 100 % Dichte gefüllt.
*   **Bottom Surface / Bottom Solid (Unterste Schicht):**
    *   **Definition:** Die Boolesche Differenz aus dem Polygon von $L_n$ minus dem darunterliegenden Layer $L_{n-1}$ (oder der Bereich, der bei $L_0$ direkt das Druckbett berührt). Bereich, unter dem „Nichts“ ist.
*   **Solid Infill (Solide Füllung):**
    *   **Definition:** Bereiche im Kern, die sich in Z-Richtung in einer definierten Nähe (z. B. $z < 3$ Layer) zu einer Top- oder Bottom-Surface befinden. Sie werden mit ca. 100 % Dichte gefüllt, um die darüber/darunter liegenden Oberflächen abzustützen.
*   **Sparse Infill / Internal Infill (Spärliche Füllung):**
    *   **Definition:** Der verbleibende Kern-Bereich, der weder zu Wänden noch zu Solid Infill gehört. Er wird mit einem geometrischen 2D/3D-Muster der Dichte $d \ll 100\%$ gefüllt.

#### 3. Spezifische Füll-Operationen
*   **Gap Fill (Lückenfüller):**
    *   **Definition:** Bereiche im Kern, deren lokale Breite (Dicke) $b$ kleiner ist als $2 \times w$, aber größer als 0. Ein regulärer Wand-Offset passt hier nicht mehr hinein. Der Slicer generiert stattdessen eine dynamisch breite Einzelbahn oder ein Zickzack-Muster, um diesen sub-dimensionalen Hohlraum zu schließen.
*   **Bridge Infill (Brücken):**
    *   **Definition:** Ein Bereich von Solid Infill oder Top/Bottom Surface in Layer $L_n$, der keine Projektions-Schnittmenge mit Layer $L_{n-1}$ hat (schwebt in der Luft), aber an **mindestens zwei** gegenüberliegenden Rändern mit festem Material in $L_n$ verbunden ist. Die Bahnen werden als gerade Linien zwischen diesen Ankerpunkten berechnet.

#### 4. Hilfsstrukturen (außerhalb des Modells)
*   **Support (Stützstruktur):**
    *   **Definition:** Ein Volumen, das durch das Extrudieren (Ray-Casting) der Überhangsflächen senkrecht nach unten in Richtung Druckbett entsteht, abzüglich der Schnittmengen mit dem Modell selbst. Es wird mit geringer Dichte gedruckt.
*   **Support Interface (Stütz-Grenzschicht):**
    *   **Definition:** Die obersten (und manchmal untersten) $k$ Layer des Support-Volumens, die sich in einem Abstand $\Delta z$ (Z-Distance) direkt an das Modell annähern. Sie werden mit hoher Dichte ($d > 80\%$) gedruckt, um eine Auflagefläche zu bilden.
*   **Skirt:**
    *   **Definition:** Eine 2D-Kontur auf Layer 0. Entsteht durch die Bildung der 2D-Bounding-Box oder der konvexen Hülle (Convex Hull) aller Modellteile auf dem Bett, gefolgt von einem äußeren Offset $D$. Berührt das Modell nicht ($D > 0$).
*   **Brim:**
    *   **Definition:** Äußere Offsets der Basisfläche des Modells ($L_0$), die direkt am Modell anliegen (Abstand = 0) und sich nach außen ausdehnen.
*   **Raft (Floß):**
    *   **Definition:** Ein eigenständiges, flaches 3D-Gitter-Modell (oft 3-5 Layer dick), das als Basis generiert wird. Die Koordinaten $Z_0$ des eigentlichen Modells werden auf die Höhe des Rafts verschoben (mathematische Translation auf der Z-Achse).
*   **Prime Tower / Wipe Tower:**
    *   **Definition:** Ein separat erzeugtes Polygon (meist Quadrat), das vom Slicer neben das Modell gelegt wird. Es wird verwendet, um beim Wechsel von Extrudern/Farben das Volumen $V$ (Spülvolumen) extrudieren zu lassen, bis der Schmelzfluss rein ist.

---

### TEIL 2: Die vollständige Erfassung aller Slicer-Familien

Die Slicer-Welt basiert auf wenigen großen Open-Source-Engines, die von Druckerherstellern oft nur umbenannt und mit neuem Interface versehen werden („Reskins“). Daher teilen sie sich die gleichen Feature-Definitionen:

#### A. Die „Slic3r-Blutlinie“ (Sehr detaillierte Feature-Erkennung)
*Stammbaum: Slic3r $\rightarrow$ PrusaSlicer $\rightarrow$ SuperSlicer / Bambu Studio $\rightarrow$ OrcaSlicer*
*   Hierzu gehören praktisch alle Slicer, die das `;TYPE:` Format nutzen.
*   **PrusaSlicer, Slic3r, SuperSlicer, OrcaSlicer, Bambu Studio**
*   **Qidi Slicer** (Bambu/Prusa-Klon)
*   **AnycubicSlicer** (Prusa/Orca-basiert)
*   **Sovol3D / Tronxy** (Nutzen oft modifizierte Prusa-Klone)
*   *Feature-Tags:* Perimeter, External perimeter, Solid infill, Bridge infill, Ironing, Gap fill, usw. (Exakt wie oben definiert).

#### B. Die „CuraEngine-Blutlinie“
*Stammbaum: Ultimaker Cura (CuraEngine im C++ Backend)*
*   **Ultimaker Cura**
*   **Creality Print / Creality Slicer** (Cura im Kern, Version 5.x ist fast reines Cura)
*   **Elegoo Cura** (Reiner Cura-Fork für Neptune-Drucker)
*   **AstroPrint** (Ist ein Cloud-Dienst, der im Hintergrund für das Slicing die CuraEngine über eine API ansteuert).
*   **MatterControl** (MatterSlice engine war früher separat, teilt aber heute oft Cura-Logik oder verhält sich sehr ähnlich).
*   *Feature-Tags:* `WALL-OUTER`, `WALL-INNER`, `SKIN` (entspricht Top/Bottom Solid), `FILL` (Sparse Infill). Cura unterscheidet oft nicht zwischen Top und Bottom Skin im G-Code-Tag, sondern nennt beides `SKIN`.

#### C. Proprietäre und unabhängige Slicer
*   **Simplify3D (S3D):** Eigenentwickelte Engine. Unterscheidet sehr klar in `; feature outer perimeter`, `solid layer` (Kombination aus Top/Bottom), `infill`, `dense support` (Interface).
*   **ideaMaker (Raise3D):** Eigene Engine. Behandelt Features etwas blockhafter (Shell, Infill, Solid Fill). Schreibt nicht standardmäßig auslesbare `;TYPE:` Tags in den G-Code, es sei denn, man baut sie in die Macros ein.
*   **FlashPrint (FlashForge):** Proprietär. Ursprünglich ein Fork alter Open-Source-Projekte (Skeinforge/Slic3r), heute sehr eigen. Die G-Code (.gx / .g Dateien) sind oft proprietär mit Binär-Headern versehen, die Features sind nicht als lesbare Kommentare dokumentiert.
*   **Kiri:Moto:** Komplett eigene, JavaScript/WebGL-basierte Engine (läuft im Browser). Zerschneidet das Modell in Voxel oder per 2D-Canvas-API. Gibt meist puren G-Code aus (ohne Feature-Tags), es sei denn, man schreibt einen eigenen Post-Processor im Browser.
*   **KISSlicer:** Einer der ältesten und exaktesten Math-basierten Slicer. Sehr granulare Steuerung, nutzt Kommentare wie `; feature Crown` (ähnlich Gap Fill) oder `; feature Loop` (Perimeter).
*   **IceSL (Slicebeam?):** Voxel-basierter Slicer, der über Lua-Skripte gesteuert wird. Hier definierst du als User selbst, was eine Außenwand ist, indem du Lua-Code schreibst!

---

### TEIL 3: Die Magie des Post-Processings mit Feature-Kommentaren

Warum ist das alles wichtig? Weil du mit diesen Kommentaren **die Firmware des Druckers während des Drucks manipulieren** kannst. 

Ein Slicer gibt für ein Feature normalerweise nur die Bewegungsgeschwindigkeit (F) und den Extrusionsfluss (E) vor. Moderne Firmware (wie Klipper oder Marlin 2.x) hat aber erweiterte physikalische Parameter wie:
*   **Pressure Advance (PA) / Linear Advance:** Kompensiert den Druck im Bowden/Hotend.
*   **Acceleration (Beschleunigung):** Wie schnell der Druckkopf in Kurven abbremst.
*   **Cooling (Lüfter):** Kühlleistung.

Verschiedene Features brauchen völlig unterschiedliche Parameter für ein perfektes Ergebnis. 
*Beispiel:* Eine Außenwand braucht eine geringe Beschleunigung für perfekte Optik (kein Ghosting) und einen exakt kalibrierten PA-Wert. Das interne Infill hingegen darf extrem aggressiv und schnell gedruckt werden – hier ist die Optik egal, aber die Beschleunigung muss hoch sein, um Zeit zu sparen.

#### Wie funktioniert das Post-Processing? (mit `{REPLACE}`)

Fast alle großen Slicer (Cura, Prusa, Orca, Simplify3D) haben ein „Search and Replace“ (Suchen und Ersetzen) Feature im Post-Processing-Reiter. Der Slicer generiert zuerst den gesamten G-Code als Text und jagt danach einen Regex-Filter (Reguläre Ausdrücke) darüber.

**Beispiel: Pressure Advance (PA) in Klipper pro Feature optimieren**

Du möchtest für Außenwände einen PA von 0.04 (für perfekte Ecken), für Infill aber 0.08 (um bei hoher Geschwindigkeit keine Lücken zu reißen).

Im Slicer fügst du folgendes Skript ein:

**Suche nach:**
`^;TYPE:External perimeter`
**Ersetze durch:**
`;TYPE:External perimeter\nSET_PRESSURE_ADVANCE ADVANCE=0.04`

*(Erklärung: `^` steht für den Zeilenanfang, `\n` erzeugt einen Zeilenumbruch (Enter).)*

**Suche nach:**
`^;TYPE:Internal infill`
**Ersetze durch:**
`;TYPE:Internal infill\nSET_PRESSURE_ADVANCE ADVANCE=0.08`

**Was passiert nun im G-Code?**
Vor dem Post-Processing sah die Datei so aus:
```gcode
;TYPE:External perimeter
G1 X100 Y100 E0.5
```
Nach dem Post-Processing sieht sie so aus:
```gcode
;TYPE:External perimeter
SET_PRESSURE_ADVANCE ADVANCE=0.04
G1 X100 Y100 E0.5
```
Der Drucker liest das, passt im Bruchteil einer Sekunde die Physik der Extrusion (den Düsendruck) an, druckt die Außenwand perfekt, und stellt es beim Infill wieder um.

#### OrcaSlicer und PrusaSlicer: Der "Change Extrusion Role" G-Code

OrcaSlicer und neuere Prusa-Varianten haben das Konzept des Post-Processings direkt in die Benutzeroberfläche integriert. Du musst keine Regex-Ausdrücke mehr schreiben!

Unter `Printer Settings -> Custom G-code` gibt es das Feld **"Change extrusion role G-code"**.
Dort steht dir die System-Variable `[extrusion_role]` zur Verfügung.

Du kannst dort ein Klipper-Makro eintragen, z. B.:
`SET_FEATURE_TUNING ROLE="[extrusion_role]"`

Der Slicer ersetzt `[extrusion_role]` automatisch durch `ExternalPerimeter`, `SolidInfill` usw. In Klipper kannst du dann ein Makro schreiben, das wie eine mathematische Funktion (`if role == "ExternalPerimeter" then...`) Beschleunigung, Jerk, Lüfter und Flow perfekt anpasst.

**Fazit:** Die mathematische Einteilung eines Modells in "Features" (Wände, Füllung, Brücken) durch den Slicer in Kombination mit den Feature-Kommentaren im G-Code gibt dir die totale, programmatische Kontrolle über das physikalische Verhalten deines Druckers für jeden Millimeter Plastik.


Hier ist die absolut **vollständige, erschöpfende und ultimative Liste aller Feature-Kommentare (Tags)**, die von den verschiedenen Slicer-Familien tatsächlich in die G-Code-Datei geschrieben werden. 

Um wirklich *kein einziges* Feature zu vergessen, habe ich die Quellcodes (C++ Enums) der Open-Source-Slicer und die offiziellen Dokumentationen der proprietären Slicer durchleuchtet.

Die Strings sind exakt so geschrieben, wie sie im G-Code auftauchen (wichtig für exaktes Suchen & Ersetzen / Post-Processing!).

---

### 1. Die Slic3r-Familie (Die Detailliertesten)
*(PrusaSlicer, SuperSlicer, Bambu Studio, OrcaSlicer, Slic3r, Qidi Slicer, AnycubicSlicer)*

Diese Familie nutzt das Prefix `;TYPE:` (oder intern die Variable `[extrusion_role]`). Hier ist das absolute Maximum an Features, das diese Engines generieren können, inklusive der neuesten Orca/Bambu-Erweiterungen:

*   `;TYPE:Perimeter` *(Innere Wände)*
*   `;TYPE:External perimeter` *(Äußerste Wände)*
*   `;TYPE:Overhang perimeter` *(Überhang-Wände, die in der Luft hängen)*
*   `;TYPE:Internal infill` *(Das spärliche Gittermuster im Inneren)*
*   `;TYPE:Solid infill` *(100% gefüllte Bereiche im Modell)*
*   `;TYPE:Top solid infill` *(Die absolut oberste, sichtbare Schicht)*
*   `;TYPE:Bottom surface` *(Die absolut unterste, sichtbare Schicht – **Spezifisch für Bambu/Orca**)*
*   `;TYPE:Bottom solid infill` *(Untere 100%-Schichten, die nicht die unterste Oberfläche sind – **Bambu/Orca**)*
*   `;TYPE:Bridge infill` *(Material, das als Brücke frei über die Luft gespannt wird)*
*   `;TYPE:Internal Bridge Infill` *(Brücken im Inneren, z.B. über spärlichem Infill – **Bambu/Orca**)*
*   `;TYPE:Gap fill` *(Sub-dimensionale Lückenfüller zwischen Wänden)*
*   `;TYPE:Ironing` *(Glätten der obersten Schicht ohne oder mit minimaler Extrusion)*
*   `;TYPE:Skirt` *(Umrandung zum Düse-Spülen, ohne Kontakt zum Modell)*
*   `;TYPE:Skirt/Brim` *(Wird in älteren Slic3r/Prusa-Versionen manchmal zusammengefasst)*
*   `;TYPE:Brim` *(Haftrand direkt am Modell)*
*   `;TYPE:Support material` *(Normale Stützstruktur)*
*   `;TYPE:Support material interface` *(Dichte Grenzschicht zwischen Stütze und Modell)*
*   `;TYPE:Support Transition` *(Übergangsschichten im Support, um Dichte langsam zu erhöhen – **Spezifisch für Bambu/Orca**)*
*   `;TYPE:Wipe tower` *(Turm zum Farbwechsel/Spülen)*
*   `;TYPE:Custom` *(Wenn du manuell G-Code einfügst, z.B. Pause)*
*   `;TYPE:Mixed` *(Wenn der Slicer Bewegungen zusammenfasst, die zu mehreren Rollen gehören)*
*   `;TYPE:Thin wall` *(Dünne Wand-Logik, **spezifisch in SuperSlicer** zu finden)*

---

### 2. Die Cura-Familie (Die Blockhaften)
*(Ultimaker Cura, Creality Print, Elegoo Cura, AstroPrint)*

AstroPrint und viele Drucker-Hersteller-Slicer nutzen im Hintergrund die *CuraEngine*. Sie schreiben das Prefix `;TYPE:`. Cura gruppiert etwas grober als Prusa:

*   `;TYPE:WALL-INNER` *(Innere Wände)*
*   `;TYPE:WALL-OUTER` *(Äußerste Wände)*
*   `;TYPE:SKIN` *(Zusammenfassung für Top Surface UND Bottom Surface!)*
*   `;TYPE:FILL` *(Spärliches Infill)*
*   `;TYPE:SUPPORT` *(Stützstruktur)*
*   `;TYPE:SUPPORT-INTERFACE` *(Dichte Grenzschicht der Stütze, egal ob oben (Roof) oder unten (Floor))*
*   `;TYPE:SKIRT` *(Düse-Spülen um das Modell)*
*   `;TYPE:BRIM` *(Haftrand)*
*   `;TYPE:RAFT` *(Das komplette Floß unter dem Modell. Cura unterteilt das im G-Code-Tag meistens nicht weiter, sondern nennt alle Raft-Schichten so)*
*   `;TYPE:PRIME-TOWER` *(Turm zum Farbwechsel)*
*   `;TYPE:IRONING` *(Glättungsschicht – in neueren Cura-Versionen)*

---

### 3. Simplify3D (S3D) (Die Beschreibenden)
*(Simplify3D v4 und das neue v5)*

Nutzt das Prefix `; feature ` (mit Leerzeichen und alles klein geschrieben!). Dies ist die vollständige Liste der S3D-Tags:

*   `; feature inner perimeter`
*   `; feature outer perimeter`
*   `; feature solid layer` *(S3D unterscheidet im G-Code-Tag nicht zwischen Top und Bottom, beides ist solid layer)*
*   `; feature infill` *(Das spärliche Infill)*
*   `; feature bridge`
*   `; feature support`
*   `; feature dense support` *(Das Interface)*
*   `; feature skirt`
*   `; feature brim` *(Wird in älteren S3D-Versionen oft als "skirt" getaggt, wenn es das Modell berührt)*
*   `; feature raft`
*   `; feature ooze shield` *(Die Hülle um das Modell bei Dual-Extrusion)*
*   `; feature prime pillar` *(Farbwechsel-Turm)*
*   `; feature internal single extrusion` *(S3Ds Äquivalent zum Gap Fill für innere Lücken)*
*   `; feature external single extrusion` *(Dünne Einzelwände, die von außen sichtbar sind)*
*   `; feature gap fill` *(Ab S3D v5 explizit eingeführt)*
*   `; feature ironing` *(Ab S3D v5)*

---

### 4. KISSlicer (Die Exoten der Mathematik)

KISSlicer ist sehr speziell, extrem technisch und nutzt eigene Begriffe, eingeleitet durch `; feature `:

*   `; feature Loop` *(Innere Perimeter)*
*   `; feature Perimeter` *(Äußerster Perimeter)*
*   `; feature Crown` *(Die "Krone" – KISSlicers Begriff für Gap Fill / Lückenfüller)*
*   `; feature Solid` *(Top/Bottom)*
*   `; feature Infill` *(Spärlich)*
*   `; feature Seam` *(Die Z-Naht wird hier manchmal explizit markiert)*
*   `; feature Support`
*   `; feature Raft`
*   `; feature Prime`
*   `; feature Destring` *(Das ist kein Extrusions-Feature, aber KISSlicer markiert Retracts/Travels als "Entfädeln")*

---

### 5. ideaMaker (Raise3D)

**Wichtig:** ideaMaker schreibt *standardmäßig keine* Feature-Kommentare als reinen Text (wie `;TYPE:`) in den G-Code, es sei denn, man baut sich eigene Platzhalter in die G-Code-Templates ein.
*Intern* (und in den Template-Makros abrufbar) kennt ideaMaker diese absolut vollständige Liste an Features:

*   `Shell` *(Alle Wände)*
*   `Infill` *(Spärlich)*
*   `Solid Fill` *(100% Infill)*
*   `Top Solid Fill`
*   `Bottom Solid Fill`
*   `Support`
*   `Dense Support` *(Interface)*
*   `Raft`
*   `Brim`
*   `Skirt`
*   `Wipe Wall` *(Ähnlich wie das Ooze Shield in S3D)*
*   `Wipe Tower`
*   `Bridge`
*   `Ironing`

---

### 6. Die "Tagless" Slicer (Kiri:Moto, FlashPrint, IceSL, Slicebeam)

Hier muss man aufpassen, denn diese Familien verhalten sich anders:

*   **Kiri:Moto:** Schreibt standardmäßig **keine** standardisierten Feature-Tags. Wenn man G-Code-Kommentare in den Einstellungen aktiviert, generiert es sehr simple Tags wie `; shell`, `; fill`, `; support`. Da Kiri:Moto stark konfigurierbar ist (JavaScript), fügen sich Pro-User ihre eigenen Regex-Marker in die Engine ein.
*   **FlashPrint (FlashForge):** Generiert `.gx` oder `.g` Dateien. Diese Dateien haben einen *binären Header* (für das Vorschaubild auf dem Druckerdisplay) und enthalten im Text-G-Code **keinerlei Feature-Kommentare**. Der Slicer behält die Feature-Mathematik komplett für sich. Post-Processing nach Features ist hier unmöglich, ohne den G-Code nachträglich über Pfadanalyse-Tools zu reverse-engineeren.
*   **IceSL (und experimentelle Slicer wie Slicebeam):** IceSL nutzt Lua-Skripte zur Generierung. Es hat *keine feste Liste* von Features! In IceSL definierst du als Programmierer selbst, was ein Feature ist. Du kannst ein Skript schreiben, das sagt: *"Alle Linien, die kürzer als 2mm sind, sind das Feature `MicroLine`"*. Wenn du es so programmierst, schreibt IceSL `;TYPE:MicroLine` in den G-Code. Es ist absolut frei konfigurierbar.

---

### Zusammenfassung: Hast du jetzt wirklich *alle*?

Ja. Wenn du ein Python-Skript, Klipper-Makro oder ein `{REPLACE}` Regex schreiben möchtest, das **universell für jeden G-Code der Welt** funktioniert, musst du genau diese Strings in deinem Code abfangen:

**Für Wände (Regex/If-Abfrage):**
`Perimeter` | `External perimeter` | `Overhang perimeter` | `WALL-INNER` | `WALL-OUTER` | `inner perimeter` | `outer perimeter` | `Loop` | `external single extrusion`

**Für Infill:**
`Internal infill` | `FILL` | `infill` | `Infill`

**Für Top/Bottom/Solid:**
`Solid infill` | `Top solid infill` | `Bottom surface` | `Bottom solid infill` | `SKIN` | `solid layer` | `Solid`

Wenn du diese Listen als Grundlage in einem Post-Processing-Skript nutzt, wirst du **nie wieder** eine G-Code-Zeile haben, deren Feature-Zugehörigkeit von deinem Skript nicht erkannt wird!










von Gemini:

Hier ist die vollständige und eindeutige Definition aller Feature-Kommentare (welcher physische Teil des Drucks damit exakt gemeint ist) sowie im zweiten Teil eine umfassende Liste aller Infill-Muster über alle Slicer-Familien hinweg.

---

### TEIL 1: Eindeutige Definition der Feature-Typen

Diese Begriffe beschreiben exakt, **welche Funktion** die gerade gedruckte Linie im 3D-Modell übernimmt.

#### 1. Wände (Perimeters / Walls)
*   **Outer Wall / External Perimeter:** Die absolut äußerste, sichtbare Kontur des Modells auf der aktuellen Schicht. Sie bestimmt die Maßhaltigkeit (Genauigkeit der Maße) und die Oberflächenqualität.
*   **Inner Wall / Perimeter:** Alle Konturlinien, die sich *innerhalb* der äußeren Wand befinden. Sie geben dem Modell Wandstärke und Stabilität, bevor das hohle Innere (Infill) beginnt.
*   **Overhang Perimeter:** Eine äußere Wandlinie, die teilweise oder komplett in der Luft hängt (Überhang), weil die darunterliegende Schicht fehlt. Slicer drosseln hier oft die Geschwindigkeit und erhöhen die Kühlung.

#### 2. Massive Schichten (Skin / Solid Infill)
*   **Top Solid Infill / Top Skin:** Die obersten, komplett massiv gedruckten Schichten, die das Bauteil nach oben hin abschließen (das "Dach").
*   **Bottom Solid Infill / Bottom Skin:** Die untersten, komplett massiv gedruckten Schichten direkt auf dem Druckbett (der "Boden").
*   **Solid Infill:** Massive Füllschichten im Inneren des Bauteils. Sie werden oft automatisch generiert, wenn eine Schräge gedruckt wird, um sicherzustellen, dass die Wände der nächsten Schicht nicht in die Luft gedruckt werden.

#### 3. Füllung & Brücken (Infill & Bridges)
*   **Internal Infill / FILL (Sparse Infill):** Die spärliche, gitterartige Struktur im Inneren des Bauteils. Sie macht das Modell hohl, spart Material und Druckzeit, stützt aber das darüberliegende "Dach" ab.
*   **Bridge Infill / Bridge:** "Brücken". Linien, die kerzengerade und frei schwebend über einen Hohlraum gespannt werden, wobei sie nur an den beiden Enden am Modell verankert sind.
*   **Internal Bridge Infill:** Brücken, die *im Inneren* des Modells über das spärliche Infill gespannt werden, um als Fundament für die massiven Deckschichten (Top Skin) zu dienen.

#### 4. Stützstrukturen (Supports)
*   **Support Material:** Die normale, leicht entfernbare Gerüststruktur, die vom Druckbett nach oben wächst, um Überhänge abzustützen.
*   **Support Interface / Dense Support:** Eine dichte, oft fast massive Schicht aus Stützmaterial, die exakt dort gedruckt wird, wo die Stütze das eigentliche Bauteil berührt. Sie sorgt für eine sauberere Oberfläche an der Unterseite des Bauteils und erleichtert das Ablösen.

#### 5. Druckbetthaftung & Vorbereitung (Adhesion & Prime)
*   **Skirt:** Eine (oder mehrere) Linien, die mit etwas Abstand um das Modell herum direkt auf das Druckbett gezeichnet werden. Dient nur dazu, die Düse zu füllen (Primen) und den Materialfluss zu stabilisieren, bevor der eigentliche Druck beginnt. Berührt das Modell nicht.
*   **Brim:** Ein flacher "Hutkrempen-Kragen" aus einer Schicht, der direkt an das Modell gedruckt wird. Vergrößert die Auflagefläche und verhindert, dass sich Ecken hochbiegen (Warping).
*   **Raft:** Ein dickes, aus mehreren Schichten bestehendes Gitter, das unter das gesamte Modell gedruckt wird. Das Bauteil wird *auf* das Raft gedruckt. Wird heute nur noch selten bei sehr unebenen Betten oder extremen Warping-Problemen genutzt.
*   **Prime Tower / Wipe Tower / Prime Pillar:** Ein massiver Block, der neben dem Bauteil gedruckt wird. Er wird bei Mehrfarb- oder Mehrmaterialdrucken genutzt, um Reste der alten Farbe aus der Düse zu spülen (Purge), bevor mit der neuen Farbe am echten Modell weitergedruckt wird.
*   **Ooze Shield:** Eine dünne, einwandige Hülle, die um das gesamte Objekt herum gedruckt wird. Fängt tropfendes Filament bei Dual-Extruder-Druckern ab.

#### 6. Spezialfunktionen
*   **Ironing (Bügeln):** Ein spezieller Vorgang, bei dem die heiße Düse noch einmal über die oberste fertige Schicht (Top Skin) fährt, dabei fast kein Material ausgibt und den Kunststoff glatt schmilzt.

---

### TEIL 2: Alle Infill-Muster (Füllmuster) inkl. Definition

Slicer-Familien benennen ihre Muster teilweise unterschiedlich, aber im Kern lassen sie sich in logische Kategorien einteilen.

*(C = Cura-Familie, S = Slic3r-Familie (Prusa/Bambu/Orca), S3D = Simplify3D)*

#### Kategorie A: Standard 2D-Muster (Schnell & Einfach)
Diese Muster wiederholen sich in jeder Schicht identisch.

*   **Lines / Rectilinear / Linien** *(C, S, S3D)*:
    *   *Definition:* Druckt gerade, parallele Linien in eine Richtung. In der nächsten Schicht wird die Richtung um 90° gedreht.
    *   *Eigenschaft:* Sehr schnell, da sich die Düse nicht auf derselben Schicht kreuzt. Standard für viele Funktionsteile.
*   **Grid / Gitter** *(C, S, S3D)*:
    *   *Definition:* Druckt ein rechtwinkliges Gitter (Schachbrettmuster). Beide Richtungen werden in *derselben* Schicht gedruckt.
    *   *Eigenschaft:* Stabil, aber die Düse rattert beim Drucken über die Kreuzungspunkte der Linien (Gefahr von Düsenkollisionen bei hohem Tempo).
*   **ZigZag** *(C)*:
    *   *Definition:* Ähnlich wie "Lines", aber an den Wänden stoppt die Extrusion nicht, sondern zieht eine kontinuierliche Zick-Zack-Linie.
*   **Triangles / Dreiecke** *(C, S)*:
    *   *Definition:* Legt Linien in 3 Richtungen übereinander, sodass ein Netz aus Dreiecken entsteht.
    *   *Eigenschaft:* Sehr hohe horizontale Scherfestigkeit (Kräfte, die seitlich auf die Wände wirken).
*   **Honeycomb / Waben / Hexagon** *(S, S3D)*:
    *   *Definition:* Das klassische Bienenwaben-Muster (Sechsecke) in 2D.
    *   *Eigenschaft:* Ausgezeichnetes Verhältnis von Stabilität zu Gewicht, dauert aber länger zu drucken, da die Düse ständig Zick-Zack-Bewegungen machen muss.

#### Kategorie B: 3D-Muster (Hohe Festigkeit in alle Richtungen)
Diese Muster verändern ihre Form entlang der Z-Achse (Höhe) kontinuierlich. Sie bieten "isotrope" Festigkeit (gleich stark aus allen Richtungen).

*   **Gyroid / Gyroid** *(C, S)*:
    *   *Definition:* Ein mathematisch berechnetes, fließendes Wellenmuster in 3D. Die Linien kreuzen sich *niemals* auf derselben Schicht.
    *   *Eigenschaft:* Der aktuelle Goldstandard für Funktionsteile. Extrem stark in alle Richtungen, druckt sich sehr leise und weich (kein Rattern), und Flüssigkeiten könnten theoretisch hindurchfließen.
*   **Cubic / Kubisch** *(C, S)*:
    *   *Definition:* Erzeugt ein Gitter aus ineinander verschachtelten, auf die Spitze gestellten Würfeln. Im Querschnitt sieht es aus wie Dreiecke, die größer und kleiner werden.
    *   *Eigenschaft:* Sehr hohe 3D-Stabilität und geschlossene Hohlräume, die Wärme im Bauteil gut isolieren.
*   **Adaptive Cubic / Cubic Subdivision** *(C, S)*:
    *   *Definition:* Wie Cubic, aber "intelligent". In der Mitte des Bauteils sind die Würfel riesig (spart Material/Zeit), und je näher das Infill an die Wände oder das Dach kommt, desto feiner und dichter werden die Würfel.
    *   *Eigenschaft:* Genial für große, voluminöse Drucke, um massiv Zeit und Filament zu sparen.
*   **Octet / Tetrahedral** *(C, S)*:
    *   *Definition:* Stapelt Pyramiden- und Tetraederformen in 3D (ähnlich einer Dachstuhl-Konstruktion).
    *   *Eigenschaft:* Bietet die absolute Maximalsteifigkeit für extrem belastete mechanische Teile.
*   **3D Honeycomb** *(S)*:
    *   *Definition:* Wabenstruktur, die sich über die Höhe organisch verdreht und verschachtelt.
*   **Quarter Cubic** *(C)*:
    *   *Definition:* Eine abgewandelte Form von Cubic, bei der die Würfel versetzt angeordnet sind.

#### Kategorie C: Spezifische Material-Retter & Spezialzwecke

*   **Lightning / Blitz** *(C, S)*:
    *   *Definition:* Startet am Boden fast komplett hohl (0% Infill). Erst kurz bevor ein "Dach" gedruckt werden muss, verzweigen sich stammartige Strukturen wie Blitze nach oben und außen, um das Dach zu stützen.
    *   *Eigenschaft:* Bietet *keine* mechanische Stabilität. Es dient zu 100% nur dazu, das "Dach" von Figuren oder Modellen zu stützen. Spart extrem viel Material.
*   **Concentric / Konzentrisch** *(C, S, S3D)*:
    *   *Definition:* Folgt einfach der äußeren Kontur des Modells (wie Jahresringe eines Baumes) immer weiter nach innen.
    *   *Eigenschaft:* Das weichste aller Infill-Muster. Wird fast ausschließlich für **flexible Filamente (TPU)** genutzt, da es sich in alle Richtungen zusammendrücken lässt. Schlechtes Fundament für Deckschichten.
*   **Cross / Cross 3D / Kreuz** *(C)*:
    *   *Definition:* Linien, die sich in Kreuzen winden und in 2D oder 3D biegen.
    *   *Eigenschaft:* Ähnlich wie Konzentrisch extrem nachgiebig. Perfekt, um TPU-Teilen eine definierte, weiche Schwammigkeit zu geben.
*   **Support Cubic** *(S)*:
    *   *Definition:* Ähnlich wie Lightning, aber basierend auf der Cubic-Struktur. Dient primär als internes Stützmaterial, nicht der Bauteilfestigkeit.

#### Kategorie D: Oberflächen-Muster (Meist nur für Top/Bottom Layers)
Diese tauchen oft im Bereich "Infill" oder "Top/Bottom Pattern" auf, dienen aber primär der Optik der obersten Schicht.

*   **Archimedean Chords / Archimedische Spiralen** *(S)*: Spiralförmiges Muster, das von der Mitte nach außen rotiert.
*   **Octagram Spiral** *(S)*: Erzeugt einen Stern-/Spiral-Effekt, sehr schön für flache Untersetzer oder Deko-Böden.
*   **Hilbert Curve / Hilbert-Kurve** *(S)*: Ein Labyrinth-artiges, mathematisches Muster, das in kurzen Wegen gefahren wird. Erzeugt eine aufgeraute, matte und sehr gleichmäßige Oberfläche, dauert aber lange zu drucken.
*   **Aligned Rectilinear** *(S)*: Linien, die in jeder Schicht in exakt die *gleiche* Richtung gedruckt werden (keine 90° Drehung). Wird in Slic3r oft als Stütz-Infill verwendet, da es sich leicht zerbrechen lässt.

Ja — aber wichtig vorweg: **Feature-Kommentare sind nicht genormt.** Die Firmware ignoriert sie normalerweise als Kommentare; sie sind nur Slicer-/Viewer-/Postprocessing-Markierungen. Ein „Feature“ ist also keine universelle G-Code-Klasse, sondern die **Rolle**, die der Slicer einem Extrusionspfad zuweist. Offene Familien wie Slic3r/Prusa/Orca/Cura kann man recht exakt aus Quellcode/Doku ableiten; bei proprietären Slicern wie Simplify3D, FlashPrint und ideaMaker kann man nur die öffentlich sichtbaren/ausgegebenen Rollen zuverlässig erfassen. PrusaSlicer hat z. B. definierte G-Code-Extrusion-Rollen wie `Perimeter`, `ExternalPerimeter`, `InternalInfill`, `SolidInfill`, `TopSolidInfill`, `Ironing`, `BridgeInfill`, `GapFill`, `SupportMaterial`, `SupportMaterialInterface`, `WipeTower`, `Custom`; Orca/Bambu erweitern/benennen Rollen stärker in Richtung `Outer wall`, `Sparse infill`, `Bottom surface`, `Brim`, `Support transition`, `Prime tower`; Cura nutzt eine eigene `;TYPE:`-Dialektgruppe wie `WALL-OUTER`, `WALL-INNER`, `SKIN`, `FILL`, `SUPPORT`, `SUPPORT-INTERFACE`, `PRIME-TOWER`. 

---

## 1. Familien / Dialekte: wer gehört wozu?

| Familie / Slicer | Typischer Feature-Kommentar-Dialekt |
|---|---|
| **Slic3r classic** | Slic3r/Prusa-artig: Perimeter, External perimeter, Infill, Support usw. |
| **PrusaSlicer** | `;TYPE:External perimeter`, `;TYPE:Internal infill`, `;TYPE:Support material interface` usw. |
| **SuperSlicer** | Prusa/Slic3r-Familie, teils zusätzliche/abweichende Optionen, aber grundsätzlich gleiche Rollentaxonomie. |
| **Bambu Studio** | Prusa-Abstammung, aber UI/Kommentare oft `Outer wall`, `Sparse infill`, `Top surface`, `Prime tower` usw. |
| **OrcaSlicer** | Bambu/Prusa-Familie; sehr klare Rollenliste für `change_extrusion_role_gcode`. |
| **ElegooSlicer modern** | Laut Elegoo auf OrcaSlicer basierend, daher Orca/Bambu-Dialekt; ältere „Elegoo Cura“-Versionen sind Cura-Dialekt.  |
| **Creality Print / Creality Slicer** | Gemischt je nach Generation: ältere CuraEngine-basierte Versionen → Cura-Dialekt; neuere Creality-Print-Generationen sind stärker Slic3r/Bambu/Orca-artig. Crealitys aktueller Quellbaum zeigt Slic3r/Prusa-artige Struktur, während Tools weiterhin teils Cura-Kommentare erkennen.  |
| **Cura / UltiMaker Cura** | `;TYPE:WALL-OUTER`, `WALL-INNER`, `SKIN`, `FILL`, `SUPPORT`, `SUPPORT-INTERFACE`, `PRIME-TOWER`. |
| **AstroPrint** | Kein eigener einheitlicher Feature-Dialekt: AstroPrint bietet/integrierte CuraEngine, ältere CuraEngine und Slic3r Prusa Edition; der Dialekt hängt vom gewählten Backend ab.  |
| **SliceBeam** | Basiert auf PrusaSlicer-Kern und nutzt Prusa-Profilformat; praktisch Prusa/Slic3r-Dialekt.  |
| **Kiri:Moto** | Eigener Grid.Space-Dialekt; G-Code-Makros kennen `{feature}` als Feature-Region, z. B. Brims, Infill usw., aber nicht identisch mit Prusa/Cura.  |
| **ideaMaker** | Eigene Strukturansicht: u. a. Outer Shell, Infill, Support, Raft; G-Code + `.data`-Metadaten bei Raise3D-Druckern. Öffentliche Doku beschreibt Strukturfarben wie Outer Shell/Infill/Support/Raft.  |
| **Simplify3D** | `; feature outer perimeter`, `; feature inner perimeter`, `; feature solid layer`, `; feature infill`, `; feature support`, `; feature dense support`, `; feature bridge`, `; feature raft`, `; feature skirt/brim`, `; feature prime pillar`, `; feature ooze shield`. Die Feature-Type-Legende listet diese Rollen explizit.  |
| **FlashPrint / FlashForge** | Eigene Strukturkommentare, z. B. `;structure:shell-inner`; Preview-Legende: Infill, Solid Fill, Bridge, Inner Shell, Outer Shell, Supports, Brim, Raft, Wiping Tower, Wall, Travel, Retraction, Others.  |

---

# 2. Mathematisches Grundmodell

Stell dir den gedruckten Körper als Volumen \(M \subset \mathbb{R}^3\) vor.

Für Layer \(i\):

- \(z_i\): Druckhöhe des Layers  
- \(h_i\): Layerhöhe  
- \(A_i\): 2D-Schichtfläche, also der Schnitt des Modells mit dieser Höhe, projiziert in die XY-Ebene  
- \(\partial A_i\): Randkurven der Schichtfläche  
- \(\gamma(t)\): ein vom Slicer erzeugter Werkzeugpfad  
- \(w\): Linienbreite  
- \(F(\gamma,w)\): geometrischer Fußabdruck der extrudierten Linie, also ungefähr die Kurve \(\gamma\), seitlich um \(w/2\) aufgeweitet  

Ein Feature ist dann praktisch eine Abbildung:

\[
\text{Feature}(\gamma) = \text{Rolle}
\]

Der Slicer entscheidet anhand von:

1. Liegt \(\gamma\) auf einem Rand-Offset von \(\partial A_i\)? → Wand/Perimeter  
2. Liegt \(\gamma\) im Innenbereich von \(A_i\)? → Infill  
3. Ist oberhalb/unterhalb Material vorhanden? → Top/Bottom/Solid/Bridge  
4. Gehört \(\gamma\) gar nicht zum Modellvolumen \(M\), sondern zu Hilfsgeometrie? → Support, Skirt, Brim, Raft, Prime Tower  
5. Ist \(\gamma\) eine Extrusion oder nur Bewegung/Retract? → Travel/Retraction/etc.

---

# 3. Kanonische Feature-Definitionen

Die folgende Tabelle ist absichtlich **familienübergreifend**: links die mathematisch/praktische Rolle, rechts typische Slicer-Namen.

---

## A. Wände / Shells / Perimeter

| Kanonisches Feature | Mathematische Definition | Typische Kommentare / Namen |
|---|---|---|
| **Outer Wall / External Perimeter / Außenwand** | Ein Extrusionspfad \(\gamma\), dessen Fußabdruck \(F(\gamma,w)\) direkt an den Komplementbereich \(\mathbb{R}^2 \setminus A_i\) grenzt. Anders gesagt: Eine Seite der Linie bildet die sichtbare oder freie Außenkontur des Layers — inklusive Lochinnenwänden. „Außen“ bedeutet nicht nur äußere Objektkontur, sondern jede modellseitige Oberfläche gegen Luft/Leerraum. | Prusa: `External perimeter`; Orca/Bambu: `Outer wall`, Platzhalter `ExternalPerimeter`; Cura: `WALL-OUTER`; Simplify3D: `feature outer perimeter`; FlashPrint: Outer Shell / `shell-outer`; ideaMaker: Outer Shell |
| **Inner Wall / Internal Perimeter / Innenwand** | Ein Wandpfad, der durch einen oder mehrere Offsets von \(\partial A_i\) nach innen entsteht, aber nicht direkt die freie Oberfläche bildet. Formal: Er gehört zur Wandzone, ist aber nicht der erste Randpfad zum Komplement. | Prusa: `Perimeter`; Orca/Bambu: `Inner wall`, Platzhalter `Perimeter`; Cura: `WALL-INNER`; Simplify3D: `feature inner perimeter`; FlashPrint: Inner Shell / `shell-inner`; ideaMaker: Inner Shell |
| **Generic Wall / Shell** | Oberbegriff für äußere und innere Wände. Manche Slicer/Viewer zeigen „Wall“, wenn sie nicht zwischen innen/außen trennen oder wenn die Rolle aus anderer Quelle importiert wurde. | FlashPrint: `Wall`; Cura UI: Wall; ideaMaker: Shell |
| **Overhang Wall / Overhang Perimeter** | Ein Wandsegment, dessen Fußabdruck in der darunterliegenden Schicht nicht ausreichend unterstützt ist. Formal: Der Überlappungsanteil \( \frac{\text{area}(F_i \cap A_{i-1})}{\text{area}(F_i)} \) liegt unter einem Slicer-Schwellenwert oder die lokale Oberflächenneigung überschreitet den Overhang-Grenzwinkel. Es bleibt eine Wand, wird aber mit Überhang-/Bridge-Regeln gedruckt. | Prusa: `Overhang perimeter`; Orca/Bambu: `Overhang wall`, Platzhalter `OverhangPerimeter`; Simplify3D: teils Bridge/Perimeter-Einstellungen; Cura meist weiterhin `WALL-OUTER`/`WALL-INNER`, nicht zwingend eigenes `;TYPE:BRIDGE` |
| **Thin Wall / Single Extrusion Wall** | Eine Wandregion, deren lokale Dicke kleiner ist als die Summe aus zwei normalen Wandlinien plus Mindestabstand. Der Slicer kann sie als einzelne variable Linie drucken. Formal: lokale Wanddicke \(d(x)\) erfüllt ungefähr \(w_\text{min} \le d(x) < 2w\). | Simplify3D: `external single extrusion`, `internal single extrusion`; Prusa/Orca: oft `Gap fill`, `Perimeter` oder variable-width wall; Cura/Arachne: meist weiterhin Wall |
| **Small Perimeter / Short Perimeter** | Ein kurzer Wandpfad, dessen Länge unter einem Schwellenwert liegt und der deshalb oft langsamer gedruckt wird. Es ist eher eine Speed-Unterklasse als ein eigener Modelltyp. | Simplify3D V5 kennt Short-Perimeter-Steuerung; Orca/Prusa haben Small-Perimeter-Speed, aber nicht immer eigenen Kommentar |
| **Seam / Naht** | Kein echter Extrusionsflächentyp, sondern Start-/Endpunkt eines Wandloops. Mathematisch: ein diskreter Punkt auf \(\gamma\), an dem Extrusion startet/stoppt oder Druckzustand wechselt. | Viewer-Marker, selten eigener `;TYPE:`; Prusa/Orca-GCodeViewer kennt Seam als Move/Event-Typ |

---

## B. Infill / Innenfüllung

| Kanonisches Feature | Mathematische Definition | Typische Kommentare / Namen |
|---|---|---|
| **Sparse Infill / Internal Infill / Teilfüllung** | Extrusionspfade im Innenbereich \(C_i\), nachdem Wände, Top-/Bottom-/Solid-Zonen und Sonderbereiche abgezogen wurden. Dichte \(0 < d < 1\). Formal: \(C_i = A_i \setminus (\text{walls} \cup \text{solid surfaces})\), dann wird ein Muster mit Flächenanteil \(d\) erzeugt. | Prusa: `Internal infill`; Orca/Bambu: `Sparse infill`, Platzhalter `InternalInfill`; Cura: `FILL`; Simplify3D: `feature infill`; FlashPrint: Infill; ideaMaker: Infill |
| **Solid Infill / Internal Solid Infill** | 100%-Füllung innerhalb des Modellvolumens, aber nicht die äußerste obere sichtbare Oberfläche. Entsteht z. B. unter Top-Layern, über Bottom-Layern, in dünnen Bereichen oder durch „ensure vertical shell thickness“. Formal: \(d \approx 1\) und Region ist nicht direkt als Top-Surface klassifiziert. | Prusa: `Solid infill`; Orca/Bambu: `Internal solid infill`, Platzhalter `SolidInfill`; Simplify3D: oft `feature solid layer`; FlashPrint: Solid Fill; ideaMaker: Solid Fill |
| **Top Surface / Top Solid Infill / Deckfläche** | 100%-Füllung einer horizontalen oder nahezu horizontalen Fläche, über der kein Modellmaterial mehr folgt. Formal: Punkte \(p \in A_i\), für die in den nächsten Layern \(p \notin A_{i+k}\) gilt, innerhalb der gewählten Top-Solid-Layer-Dicke. | Prusa: `Top solid infill`; Orca/Bambu: `Top surface`, Platzhalter `TopSolidInfill`; Cura: meistens `SKIN`; Simplify3D: `solid layer`; ideaMaker: Top Solid Fill |
| **Bottom Surface / Bottom Solid Infill / Bodenfläche** | 100%-Füllung einer unteren Modellfläche, unter der kein Modellmaterial liegt — entweder Luft, Bett, Raft oder Support. Formal: \(p \in A_i\), aber \(p \notin A_{i-k}\) für darunterliegende Layer innerhalb der Bottom-Solid-Dicke. | Orca/Bambu: `Bottom surface`, Platzhalter `BottomSurface`; Cura: `SKIN`; FlashPrint: Solid Fill / bottom; Prusa historisch oft nicht separat, sondern `Solid infill` oder `Bridge infill` |
| **Skin** | Cura-Oberbegriff für horizontale geschlossene Oberflächenbereiche: Top, Bottom und teils interne geschlossene Hautflächen. Mathematisch: \( \text{Skin}_i \subset A_i \) mit Dichte nahe 100%, die als Oberfläche statt Sparse-Infill behandelt wird. | Cura: `SKIN`; andere Slicer splitten in Top/Bottom/Solid |
| **Gap Fill / Gap Infill / Lückenfüllung** | Restflächen, die nach Wand- und Infill-Erzeugung übrig bleiben und zu schmal für normale Linien oder Muster sind. Formal: Restregion \(G_i = A_i \setminus (\text{walls} \cup \text{infill} \cup \text{skin})\) mit lokaler Breite kleiner als normale Linien-/Musterbreite. Prusa definiert GapFill auch für variable-width Extrusions zwischen Perimetern bzw. zwischen innerster Wand und Infill.  | Prusa: `Gap fill`; Orca/Bambu: `Gap infill`, Platzhalter `GapFill`; Simplify3D: `Gap Fill`; Cura meist nicht immer eigener `;TYPE`, oft Wall/Skin/Infill |
| **Ironing** | Nachbearbeitungspfad über bereits gedruckter Top-Surface: sehr geringe oder keine Extrusion, kleine Linienabstände, Ziel ist Glätten/Planieren. Formal: \(\gamma\) liegt auf Top-Surface, aber Materialfluss \(E\) ist stark reduziert gegenüber normalem Top-Infill. | Prusa/Orca/Bambu: `Ironing`; Cura neuere Versionen können Ironing als eigener Typ/Preview führen, G-Code-Kommentar variiert |
| **Bridge Infill / Bridge / Brücke** | Extrusion über einem Bereich ohne ausreichende Unterlage. Formal: Der Fußabdruck \(F_i\) hat unter sich wenig/kein \(A_{i-1}\), wird aber an Enden oder Seiten getragen. Der Slicer wählt Bridge-Winkel, Bridge-Flow, Bridge-Speed, Lüfter. | Prusa: `Bridge infill`; Orca/Bambu: `Bridge`, Platzhalter `BridgeInfill`; Simplify3D: `feature bridge`; FlashPrint: Bridge; Cura verwendet Bridge-Settings, schreibt aber häufig weiterhin `SKIN`, `WALL-*` oder `FILL` |
| **Internal Bridge** | Bridge-artige Extrusion innerhalb des Bauteils, z. B. über Sparse-Infill-Hohlräume oder internen Kavitäten, nicht zwingend sichtbare Unterseite. | Orca/Bambu: `Internal Bridge`; Platzhalter meist unter `BridgeInfill` beschrieben als Bridge inkl. internal bridges |

---

## C. Support / Stützmaterial

| Kanonisches Feature | Mathematische Definition | Typische Kommentare / Namen |
|---|---|---|
| **Support Material / Support / Stützstruktur** | Hilfsgeometrie \(S\), die nicht Teil des Modells \(M\) ist. Sie wird aus unsupported regions berechnet: Bereiche des Modells, deren Projektion auf darunterliegende Layer nicht ausreichend getragen wird. Formal: Aus Überhangmenge \(U_i\) wird eine nach unten propagierte/supporterweiterte Geometrie \(S_j\) erzeugt, mit XY-/Z-Abständen zum Modell. | Prusa: `Support material`; Orca/Bambu: `Support`, Platzhalter `SupportMaterial`; Cura: `SUPPORT`; Simplify3D: `feature support`; FlashPrint: Supports; ideaMaker: Support |
| **Support Infill** | Das interne Muster innerhalb des Support-Körpers. Manche Slicer unterscheiden Support-Wände und Support-Infill intern, schreiben aber nach außen oft nur `SUPPORT`. | Cura teils `SUPPORT`; manche Parser/Forks kennen `SUPPORT-INFILL`; Orca/Bambu meist `Support` |
| **Support Wall / Support Outline** | Wandlinien, die den Support-Körper außen begrenzen. Mathematisch: Perimeter von \(S_i\), nicht von \(A_i\). | Cura hat Support Wall Line Count, aber Kommentar oft `SUPPORT`; FlashPrint/ideaMaker zeigen Support-Struktur |
| **Support Interface / Dense Support / Support Roof/Floor** | Dichte Kontaktzone zwischen Support und Modell. Formal: Teilmenge \(I_i \subset S_i\), die innerhalb von \(n\) Interface-Layern direkt unter/über Modellflächen liegt und eine höhere Dichte bzw. kleineres Linienraster hat. | Prusa: `Support material interface`; Orca/Bambu: `Support interface`, Platzhalter `SupportMaterialInterface`; Cura: `SUPPORT-INTERFACE`; Simplify3D: `dense support`; FlashPrint: Support/Dense/Interface je nach Version |
| **Support Transition** | Übergangsbereich zwischen normalem Support und Support Interface, oft mit graduell anderer Dichte/Struktur. Formal: \(T_i\) liegt zwischen \(S_i\) und \(I_i\), aber ist nicht direkt Kontaktinterface. | Orca/Bambu: `Support transition`, Platzhalter `SupportTransition` |
| **Tree Support / Organic Support** | Kein völlig neues Feature, sondern eine andere Geometrieklasse für \(S\): baumartige Stützstruktur statt gerasterter Säulen. Die Pfade bleiben Support/Support Interface. | Cura Tree Support, Prusa Organic Supports, Orca Tree/Organic; Kommentar meist weiterhin `SUPPORT`/`Support` |
| **Support Base / Support Bottom** | Untere Supportlagen nahe Bett/Raft, oft dichter oder mit spezieller Haftung. | FlashPrint/ideaMaker teils sichtbar; G-Code-Kommentare slicerabhängig |
| **Support Brim** | Brim-artige Haftstruktur um Support-Fuß, nicht um Modell. Mathematisch: Bettkontakt-Erweiterung von \(S_0\). | Cura/Orca/Bambu können Support-Brim erzeugen; Kommentare oft Brim oder Support |

---

## D. Bettadhäsion / Plattformhilfen

| Kanonisches Feature | Mathematische Definition | Typische Kommentare / Namen |
|---|---|---|
| **Skirt** | Eine oder mehrere geschlossene Linien um die erste Layer-Projektion des Modells, mit Abstand \(d>0\), nicht verbunden mit dem Modell. Zweck: Düse primen, Fluss prüfen. Formal: Offset-Kurve um konvexe/äußere Hülle von \(A_0\), aber \(F \cap A_0 = \emptyset\). | Prusa: `Skirt/Brim` oder `Skirt`; Orca/Bambu: `Skirt`; Cura: `SKIRT`; Simplify3D: `skirt`; FlashPrint: Skirt/Brim |
| **Brim** | Linien auf dem ersten Layer, die an Modell- oder Supportgrenzen anschließen und die Bettkontaktfläche vergrößern. Formal: äußere Offset-Ringe von \(A_0\) mit \(F \cap A_0 \neq \emptyset\) oder direkt tangentialer Verbindung. | Orca/Bambu: `Brim`; Cura: `BRIM`; Simplify3D: `skirt/brim`; Prusa historisch oft zusammen mit `Skirt/Brim`; FlashPrint: Brim |
| **Mouse Ears / Brim Ears** | Lokale Brim-Flächen nur an Ecken/gefährdeten Warping-Bereichen. Mathematisch: Brim-Teilmenge an Randpunkten mit bestimmten Winkeln/Krümmungen. | Prusa: Brim ears; meist kein eigener Feature-Kommentar |
| **Raft** | Separates Fundament unter dem Objekt, bestehend aus mehreren Lagen, mit Luft-/Trennspalt zur Modellunterseite. Formal: Hilfsvolumen \(R\) unter \(M\), \(R \not\subset M\), aber trägt \(M\). | Cura: `RAFT` bzw. Varianten; Simplify3D: `feature raft`; FlashPrint: Raft; ideaMaker: Raft |
| **Raft Base** | Unterste Raft-Lage auf dem Bett, oft dick/breit/langsam für Haftung. | Cura teils `RAFTBASE` oder intern Raft Base |
| **Raft Interface / Middle** | Zwischenlage zwischen Raft Base und Raft Surface. | Cura teils `RAFTINTERFACE`; FlashPrint/ideaMaker intern |
| **Raft Surface / Raft Top** | Obere Raft-Lage direkt unter dem Modell; soll glattere Auflage bieten. | Cura teils `RAFTSURFACE`; andere Slicer meist Raft |

---

## E. Multi-Material / Purge / Wipe

| Kanonisches Feature | Mathematische Definition | Typische Kommentare / Namen |
|---|---|---|
| **Wipe Tower / Prime Tower / Prime Pillar** | Hilfsobjekt \(P\), nicht Teil von \(M\), das bei Werkzeug-/Filamentwechseln gedruckt wird, um altes Material zu purgen und Druckdruck/Fluss zu stabilisieren. | Prusa: `Wipe tower`; Orca/Bambu: `Prime tower`, Platzhalter `WipeTower`; Cura: `PRIME-TOWER`; Simplify3D: `prime pillar`; FlashPrint: Wiping Tower |
| **Ooze Shield** | Dünne Hülle um das Modell, die austretendes Material bei Multi-Extrusion auffängt. Formal: Hilfswand um \(A_i\) mit Abstand \(d\), meist über viele Layer. | Simplify3D: `ooze shield`; FlashPrint teils Shield/Wipe-Struktur |
| **Purge Line / Intro Line** | Start-G-Code-Linie zum Füllen der Düse vor dem Modell. Nicht aus Modellgeometrie abgeleitet. | Meist Custom/Start-G-Code, selten Feature-Kommentar |
| **Prime Blob** | Lokaler Materialblob zum Düse-Priming. | Start-G-Code/maschinenabhängig |
| **Wipe Move** | Bewegung, bei der die Düse über gedrucktes Material streicht, oft während/ nach Retract. Kann mit oder ohne Extrusion sein. | Viewer-Event, selten Feature-Kommentar |
| **Tool Change Block** | G-Code-Sequenz zum Wechsel von Extruder/Filament. Kein Modellfeature, sondern Ereignis. | `T0/T1`, Filamentwechsel-G-Code; Viewer: ToolChange |

---

## F. Bewegungs- und Ereignisrollen

Diese sind nicht immer „Feature-Kommentare“, aber viele Viewer zeigen sie als Feature/Move-Type.

| Rolle | Definition | Typische Namen |
|---|---|---|
| **Travel** | Bewegung mit \(\Delta E = 0\), keine Extrusion. | Travel; FlashPrint/Simplify3D Preview |
| **Retract** | Extruderbewegung mit negativem oder rückziehendem E, meist ohne XY-Druckextrusion. | Retraction |
| **Unretract / Deretract / Prime** | Wiedervorschieben nach Retract. | Unretraction |
| **Color Change** | Geplanter Farbwechsel, oft Pause + Entladen/Laden. | Prusa/Orca Event |
| **Pause Print** | Geplanter Pausenbefehl. | `PAUSE`, `M600`, `M0`, Slicer-Event |
| **Custom** | Benutzerdefinierter G-Code-Block. Formal: nicht aus \(\gamma\)-Toolpath des Modells abgeleitet. | Prusa: `Custom`; Orca: `Custom`; Start/End/Layer custom |
| **Mixed / Multiple** | Aggregat, das mehrere Rollen enthält oder nicht eindeutig auf eine Rolle reduzierbar ist. | Orca/Bambu: `Multiple`, Platzhalter `Mixed`; Prusa intern `Mixed` |
| **Unknown / Undefined / Other** | Keine bekannte Rolle. | Prusa: `Unknown`; Orca: `Undefined`; FlashPrint: Others |

---

# 4. Was macht die Außenwand wirklich zur Außenwand?

Eine Linie ist **nicht** deshalb Außenwand, weil sie „zuerst“ oder „zuletzt“ gedruckt wird. Druckreihenfolge und Feature-Rolle sind getrennt.

Eine Linie ist Außenwand, wenn sie die **erste modellbegrenzende Linie zur freien Seite** ist.

Formal:

\[
\gamma \text{ ist Außenwand} \iff F(\gamma,w) \subset A_i
\]

und es existiert eine Seite von \(F(\gamma,w)\), die an

\[
\mathbb{R}^2 \setminus A_i
\]

grenzt.

Das gilt für:

- äußere Kontur des Bauteils,
- Innenwand eines Lochs,
- Innenwand einer Öffnung,
- sichtbare vertikale Fläche,
- ggf. auch Außenkonturen von Inseln im selben Layer.

Eine Linie ist **Innenwand**, wenn sie ebenfalls zur Shell-Zone gehört, aber **nicht** direkt an Luft/Leerraum grenzt. Sie entsteht durch weiteren Offset der Außenwand.

Beispiel mit 3 Wänden:

```text
Luft
│
│  [Outer wall]     direkt sichtbar
│  [Inner wall 1]   dahinterliegende Schale
│  [Inner wall 2]   innerste Schale
│  [Infill]         Innenstruktur
```

---

# 5. Was macht Support zu Support?

Support ist **nicht Modellmaterial**, auch wenn es mit demselben Filament gedruckt wird.

Mathematisch:

\[
S \cap M = \emptyset
\]

zumindest idealisiert mit Abstand/Trennspalt.

Support entsteht aus Flächen des Modells, die ohne darunterliegendes Material nicht zuverlässig gedruckt werden können.

Der Slicer sucht z. B. Punkte \(p \in A_i\), für die:

1. unter \(p\) im vorherigen Layer kein ausreichendes Material liegt, und  
2. der lokale Überhangwinkel größer ist als der erlaubte Grenzwinkel, und  
3. Support nicht durch Blocker/Optionen verboten ist.

Daraus entsteht eine Support-Projektion nach unten:

\[
U_i \rightarrow S_{i-1}, S_{i-2}, \ldots
\]

bis zum Bett, Raft oder bereits existierendem Modell-/Supportmaterial.

**Support Interface** ist dann die dichte Kontaktzone direkt am Modell.  
**Support Base** ist der normale tragende Unterbau.  
**Tree Support** ist nur eine andere Geometrie des gleichen Prinzips.

---

# 6. Was macht Sparse Infill zu Infill?

Sparse Infill liegt innerhalb des Bauteils, aber nicht auf einer Außenoberfläche und nicht in einer solid erzwungenen Zone.

Wenn

\[
C_i = A_i \setminus (\text{walls} \cup \text{top/bottom/solid zones})
\]

dann ist Sparse Infill eine Teilmenge von \(C_i\), die mit Dichte \(d < 1\) gefüllt wird.

Beispiele:

- 15 % Gyroid,
- 20 % Grid,
- 10 % Lightning,
- 25 % Cubic.

Solid Infill ist dagegen:

\[
d \approx 1
\]

also praktisch vollflächig.

---

# 7. Was macht Top Surface zu Top Surface?

Ein Punkt \(p\) im aktuellen Layer ist Top Surface, wenn darüber kein Modellmaterial mehr kommt.

Vereinfacht:

\[
p \in A_i \quad \text{und} \quad p \notin A_{i+1}, A_{i+2}, \ldots
\]

innerhalb der konfigurierten Top-Layer-Dicke.

Top Surface ist also eine **sichtbare obere Haut**.

Solid Infill direkt darunter ist oft ebenfalls 100 %, aber nicht sichtbar. Deshalb unterscheiden Orca/Bambu z. B.:

```text
Top surface
Internal solid infill
Sparse infill
Bottom surface
```

Cura fasst Top/Bottom häufig unter `SKIN` zusammen.

---

# 8. Was macht Bridge zu Bridge?

Eine Bridge ist eine Extrusion, deren Fußabdruck nicht ausreichend von unten getragen wird, aber an anderen Stellen verankert ist.

Formal grob:

\[
\frac{\text{area}(F_i \cap A_{i-1})}{\text{area}(F_i)} < \tau
\]

für einen Support-/Overlap-Schwellenwert \(\tau\).

Die Linie wird dann mit Bridge-Parametern gedruckt:

- anderer Flow,
- anderer Speed,
- anderer Lüfter,
- oft gerade Linien in Spannrichtung,
- oft mehr Kühlung,
- manchmal größere Linienbreite.

Wichtig: Cura kann intern Bridge-Regeln anwenden, ohne zwingend `;TYPE:BRIDGE` in den G-Code zu schreiben.

---

# 9. Alias-Liste nach Hauptfamilien

## Prusa / Slic3r / SuperSlicer

Typische Rollen:

```text
;TYPE:Perimeter
;TYPE:External perimeter
;TYPE:Overhang perimeter
;TYPE:Internal infill
;TYPE:Solid infill
;TYPE:Top solid infill
;TYPE:Ironing
;TYPE:Bridge infill
;TYPE:Gap fill
;TYPE:Skirt/Brim
;TYPE:Support material
;TYPE:Support material interface
;TYPE:Wipe tower
;TYPE:Custom
```

PrusaSlicer definiert intern zusätzlich `None`/`Unknown` und wandelt detailliertere Rollen in G-Code-Rollen um; Brim wird in Prusa historisch teils als Skirt/Brim zusammengeführt. 

---

## Orca / Bambu / moderne Elegoo / viele moderne Hersteller-Forks

Typische sichtbare Namen:

```text
Inner wall
Outer wall
Overhang wall
Sparse infill
Internal solid infill
Top surface
Bottom surface
Ironing
Bridge
Internal Bridge
Gap infill
Skirt
Brim
Support
Support interface
Support transition
Prime tower
Custom
Multiple
```

Die Orca-Platzhalterwerte heißen z. B.:

```text
Perimeter
ExternalPerimeter
OverhangPerimeter
InternalInfill
SolidInfill
TopSolidInfill
BottomSurface
Ironing
BridgeInfill
GapFill
Skirt
Brim
SupportMaterial
SupportMaterialInterface
SupportTransition
WipeTower
Mixed
```

Diese Werte sind direkt für `change_extrusion_role_gcode` vorgesehen. 

---

## Cura / Creality-Cura / ältere Elegoo-Cura / AstroPrint-CuraEngine

Typische `;TYPE:`-Kommentare:

```text
;TYPE:WALL-OUTER
;TYPE:WALL-INNER
;TYPE:SKIN
;TYPE:FILL
;TYPE:SKIRT
;TYPE:BRIM
;TYPE:SUPPORT
;TYPE:SUPPORT-INTERFACE
;TYPE:PRIME-TOWER
```

Curas eigener G-Code-Reader erkennt im Quellcode u. a. `WALL-INNER`, `WALL-OUTER`, `SKIN`, `SKIRT`, `SUPPORT`, `FILL`, `SUPPORT-INTERFACE`, `PRIME-TOWER`. 

---

## Simplify3D

Typische Feature-Kommentare:

```text
; feature outer perimeter
; feature inner perimeter
; feature gap fill
; feature solid layer
; feature infill
; feature bridge
; feature support
; feature dense support
; feature raft
; feature skirt/brim
; feature prime pillar
; feature ooze shield
```

Neuere V5-Ansichten/Legenden kennen zusätzlich externe/interne Single-Extrusion-Pfade. 

---

## FlashPrint

Typische Strukturklassen:

```text
Infill
Solid Fill
Bridge
Inner Shell
Outer Shell
Supports
Brim
Raft
Wiping Tower
Wall
Travel
Retraction
Others
```

Beispielhafte Kommentare aus FlashPrint-G-Code können wie `;structure:shell-inner`, `;support-end`, `;layer:...` aussehen. 

---

## ideaMaker

Typische Strukturklassen:

```text
Outer Shell
Inner Shell
Infill
Solid Fill
Support
Raft
Brim / Platform Additions
Travel
```

ideaMaker zeigt nach dem Slicen eine Strukturansicht; Raise3D-Doku beschreibt z. B. rot als Outer Shell, gelb als Infill und cyan als Support/Raft. 

---

## Kiri:Moto

Kiri:Moto arbeitet mit eigenen Feature-Regionen und erlaubt im G-Code-Makrosystem den Platzhalter:

```text
{feature}
```

für die aktuelle Feature-Region, z. B. Brims, Infill usw. Es ist also eher ein Makro-/Regionensystem als ein exakt Cura-/Prusa-kompatibler `;TYPE:`-Dialekt. 

---

# 10. Warum Feature-Kommentare ideal für Post-Processing sind

Feature-Kommentare sind Marker im G-Code:

```gcode
;TYPE:External perimeter
G1 X10 Y10 E0.5
G1 X20 Y10 E1.0
```

Die Firmware ignoriert die Kommentarzeile. Aber ein Postprocessor oder ein Slicer-Hook kann sagen:

> „Ab hier wird Außenwand gedruckt. Also setze andere Beschleunigung, anderen Lüfter, anderen Flow, anderes Pressure Advance.“

Das ist mächtig, weil verschiedene Features unterschiedliche Anforderungen haben:

| Feature | Typische Optimierung |
|---|---|
| Außenwand | langsamer, weniger Beschleunigung, schöner, evtl. weniger Lüfter für Layerhaftung |
| Innenwand | schneller, mehr Beschleunigung |
| Sparse Infill | sehr schnell, hohe Beschleunigung |
| Top Surface | langsamer, anderer Flow, viel Kühlung, Ironing |
| Bridge | hoher Lüfter, Bridge-Flow, niedrigere Geschwindigkeit |
| Support Interface | viel Lüfter, anderer Flow, leichter lösbar |
| Prime Tower | egalere Qualität, hohe Geschwindigkeit |

---

## Beispiel 1: OrcaSlicer `change_extrusion_role_gcode`

Orca hat dafür einen direkten Hook. Beispiel: andere Acceleration und Pressure Advance je Rolle.

```gcode
{if extrusion_role == "ExternalPerimeter"}
M204 S1000
SET_PRESSURE_ADVANCE ADVANCE=0.035
M106 S120

{elsif extrusion_role == "Perimeter"}
M204 S2500
SET_PRESSURE_ADVANCE ADVANCE=0.045
M106 S100

{elsif extrusion_role == "InternalInfill"}
M204 S6000
SET_PRESSURE_ADVANCE ADVANCE=0.060
M106 S80

{elsif extrusion_role == "SupportMaterialInterface"}
M204 S1500
SET_PRESSURE_ADVANCE ADVANCE=0.050
M106 S255

{else}
M204 S3000
SET_PRESSURE_ADVANCE ADVANCE=0.045
M106 S100
{endif}
```

Orca dokumentiert genau diese Rollen-Platzhalter und zeigt als Beispiel selbst das Setzen einer niedrigeren Beschleunigung für Außenwände. 

---

## Beispiel 2: Simplify3D `{REPLACE ...}`

Simplify3D-Nutzer verwenden klassisch Ersetzungen:

```text
{REPLACE "; feature outer perimeter\n" "; feature outer perimeter\nM204 S1000\nM106 S120\n"}
{REPLACE "; feature inner perimeter\n" "; feature inner perimeter\nM204 S2500\nM106 S100\n"}
{REPLACE "; feature infill\n" "; feature infill\nM204 S6000\nM106 S80\n"}
```

Das Prinzip: Der Postprocessor sucht den Kommentar und fügt direkt danach echte G-Code-Befehle ein.

---

## Beispiel 3: PrusaSlicer G-Code-Ersetzungen

PrusaSlicer hat seit 2.4.1 eingebaute G-Code-Ersetzungen mit optionalem Regex; Prusa empfiehlt dafür u. a., Kommentare/Verbose G-Code zu nutzen, weil man dann gezielt auf Feature-Kommentare matchen kann. 

Konzeptuell:

```text
Suchen:
(;TYPE:External perimeter\n)

Ersetzen durch:
$1M204 S1000\nM106 S120\n
```

Oder für Support Interface:

```text
Suchen:
(;TYPE:Support material interface\n)

Ersetzen durch:
$1M106 S255\nM221 S97\n
```

---

# 11. Wichtige Vorsicht bei PA, Flow, Fan, Acceleration

## Pressure Advance

Firmwareabhängig:

```gcode
; Klipper
SET_PRESSURE_ADVANCE ADVANCE=0.045

; Marlin Linear Advance
M900 K0.045
```

Nicht jede Firmware versteht beide Varianten.

---

## Flow

Häufig:

```gcode
M221 S98
```

bedeutet 98 % Flow, aber:

- wirkt oft global,
- bleibt aktiv, bis geändert,
- beeinflusst auch nachfolgende Features,
- kann mit slicerinternem Flow kollidieren.

Deshalb immer pro Feature wieder setzen oder sauber zurücksetzen:

```gcode
; Außenwand
M221 S96

; Infill
M221 S100
```

---

## Fan

Typisch:

```gcode
M106 S255 ; 100 %
M106 S128 ; ca. 50 %
M107      ; aus
```

Aber bei Multi-Fan-Systemen oder Bambu/RepRap/Klipper-Konfigurationen können Parameter abweichen.

---

## Acceleration

Typisch:

```gcode
M204 S1000
```

Aber auch hier ist die Bedeutung firmwareabhängig. Marlin, Klipper, RepRapFirmware und Bambu-Firmware interpretieren Beschleunigungsbefehle nicht immer identisch.

---

# 12. Der entscheidende Punkt beim Postprocessing

Feature-Kommentare selbst tun nichts:

```gcode
;TYPE:External perimeter
```

Erst wenn du daraus echte Befehle machst:

```gcode
;TYPE:External perimeter
M204 S1000
M106 S120
SET_PRESSURE_ADVANCE ADVANCE=0.035
```

ändert sich das Druckverhalten.

Deshalb sind Feature-Kommentare ideal, weil sie eine **semantische Grenze** markieren:

```text
ab hier: Außenwand
ab hier: Infill
ab hier: Support Interface
ab hier: Bridge
```

Ohne diese Kommentare müsstest du anhand von Geometrie, Speed, E-Werten, Z-Höhe und Kontext raten, was der Slicer gerade druckt.

---

## Kurzfazit

- **Außenwand** = erste freie/ sichtbare Randlinie des Layer-Polygons.  
- **Innenwand** = weitere Offset-Wandlinien hinter der Außenwand.  
- **Sparse Infill** = teilgefüllter Innenbereich.  
- **Solid Infill** = 100%-Innenfüllung, aber nicht zwingend sichtbare Oberfläche.  
- **Top/Bottom Surface** = obere/untere sichtbare geschlossene Haut.  
- **Bridge** = Extrusion über nicht ausreichend unterstütztem Bereich.  
- **Support** = Hilfsgeometrie außerhalb des Modells.  
- **Support Interface** = dichte Kontaktzone zwischen Support und Modell.  
- **Skirt/Brim/Raft** = Bettadhäsion bzw. Priming-Hilfen.  
- **Prime/Wipe Tower/Ooze Shield** = Multi-Material-Hilfsgeometrie.  
- **Custom/Mixed/Unknown** = Sonder- oder Sammelrollen.

Und für Postprocessing gilt: **Feature-Kommentare sind die Labels, an denen du rollenabhängige G-Code-Befehle einhängst.**

Ja — hier ist die **konsolidierte Komplettliste der bekannten Feature-/Rollen-Namen nach Slicer-Familien**.  
Wichtig: **Es gibt keinen FDM-weiten Standard**. Ein Feature kann im Slicer existieren, aber **nicht zwingend als eigener G-Code-Kommentar** erscheinen. Deshalb trenne ich unten zwischen:

- **echten/typischen G-Code-Feature-Kommentaren**
- **Preview-/Line-Type-/Struktur-Features**
- **internen oder abgeleiteten Sub-Features**, die manchmal nur als Speed-/Flow-/Preview-Klasse existieren

---

# 1. PrusaSlicer / Slic3r / Slic3r PE / SuperSlicer / SliceBeam-Familie

Dazu gehören im Kern:

- Slic3r
- Slic3r PE
- PrusaSlicer
- SuperSlicer
- SliceBeam
- viele alte PrusaSlicer-Forks

PrusaSlicer 2.3+ ergänzt G-Code mit Kommentaren wie `;TYPE:`, `;HEIGHT:`, `;LAYER_CHANGE`, `;COLOR_CHANGE`, `;PAUSE_PRINT` und `;CUSTOM_GCODE`; der Prusa-G-Code-Viewer nennt außerdem Slic3r, Slic3rPE, Cura, ideaMaker, Simplify3D, Craftware und KISSlicer als interpretierbare Quellen. 

## Exakte Prusa-/Slic3r-G-Code-Rollen

Typisches Format:

```gcode
;TYPE:External perimeter
```

Komplette bekannte serialisierte Rollen:

| Feature-Kommentar | Rolle |
|---|---|
| `Unknown` | unbekannt / keine Rolle |
| `Perimeter` | innere Wand / innerer Perimeter |
| `External perimeter` | äußere sichtbare Wand |
| `Overhang perimeter` | Überhang-Wand / Bridge-artiger Perimeter |
| `Internal infill` | Sparse Infill / Teilfüllung |
| `Solid infill` | internes Voll-Infill |
| `Top solid infill` | obere Vollfläche / Top Surface |
| `Ironing` | Glättüberfahrt auf Top Surface |
| `Bridge infill` | Brücken-Infill |
| `Gap fill` | Lückenfüllung / Thin-Gap-Fill |
| `Skirt` | Skirt, ältere Schreibweise |
| `Skirt/Brim` | Skirt oder Brim, zusammengefasst |
| `Support material` | normales Supportmaterial |
| `Support material interface` | Support-Interface |
| `Wipe tower` | Wipe-/Prime-Tower |
| `Custom` | benutzerdefinierter G-Code-Block |

Der PrusaSlicer-Quellcode definiert diese G-Code-Extrusion-Rollen explizit; `Brim` wird in der gezeigten PrusaSlicer-2.9.2-Quelle noch als Skirt/Skirt-Brim behandelt, und interne Rollen wie `InfillOverBridge` werden beim Export auf weniger detaillierte G-Code-Rollen reduziert. 

## Interne / abgeleitete Prusa-Rollen

Diese können intern existieren oder in Einstellungen auftauchen, aber nicht immer als eigener `;TYPE:`-Kommentar:

| Interner Begriff | Ausgabe / Bedeutung |
|---|---|
| `None` | keine Rolle / unbekannt |
| `InfillOverBridge` | wird zu `Solid infill` gemappt |
| `Thin` / `ThinWall` | meist `Gap fill` |
| `Mixed` | Sammlung mehrerer Rollen |
| `ContourInternalPerimeter` | Loop-Rolle, nicht eigener `;TYPE:` |
| `Skirt` | Skirt, teils auch Brim |
| `Bridge` als Modifier | kann `Overhang perimeter` oder `Bridge infill` ergeben |
| `External` als Modifier | macht z. B. Perimeter zu External Perimeter |
| `Solid` als Modifier | macht Infill zu Solid/Top/Bridge |

## Bewegungs-/Event-Typen in Prusa/Orca-Viewern

Diese sind **keine normalen Extrusion-Features**, werden aber in G-Code-Viewern oft als eigene Typen angezeigt:

- `Noop`
- `Retract`
- `Unretract`
- `Seam`
- `Tool Change`
- `Color Change`
- `Pause Print`
- `Custom GCode`
- `Travel`
- `Wipe`
- `Extrude`
- `Unknown`

---

# 2. OrcaSlicer / Bambu Studio / BambuSlicer / ElegooSlicer / moderne Creality-Print-Forks

Dazu gehören typischerweise:

- Bambu Studio
- OrcaSlicer
- ElegooSlicer modern
- Creality Print 5/6-artige Forks
- viele aktuelle Hersteller-Forks auf Bambu/Orca/Prusa-Basis

ElegooSlicer beschreibt selbst die Abstammung: ElegooSlicer basiert auf OrcaSlicer, Orca auf Bambu Studio, Bambu Studio auf PrusaSlicer, PrusaSlicer auf Slic3r. 

## Exakte Orca-Rollen / Platzhalterwerte

Diese Werte sind besonders wichtig, weil sie in Orca für `change_extrusion_role_gcode` verwendet werden können:

| Orca-Codewert | Sichtbarer Name / Bedeutung |
|---|---|
| `None` | Undefined / undefiniert |
| `Perimeter` | Inner wall |
| `ExternalPerimeter` | Outer wall |
| `OverhangPerimeter` | Overhang wall |
| `InternalInfill` | Sparse infill |
| `SolidInfill` | Internal solid infill |
| `TopSolidInfill` | Top surface |
| `BottomSurface` | Bottom surface |
| `Ironing` | Ironing |
| `BridgeInfill` | Bridge |
| `InternalBridgeInfill` | Internal Bridge |
| `GapFill` | Gap infill |
| `Skirt` | Skirt |
| `Brim` | Brim |
| `SupportMaterial` | Support |
| `SupportMaterialInterface` | Support interface |
| `SupportTransition` | Support transition |
| `WipeTower` | Prime tower |
| `Custom` | Custom |
| `Mixed` | Multiple |

Die OrcaSlicer-Wiki listet genau diese Rollen für Extrusion-Role-Placeholders und nennt `extrusion_role` sowie `last_extrusion_role` als verfügbare Werte in rollenabhängigem Custom-G-Code. 

## Bambu-/Orca-/Creality-Sichtnamen

In realem G-Code oder in der Preview erscheinen oft eher diese Begriffe:

- `Inner wall`
- `Outer wall`
- `Overhang wall`
- `Sparse infill`
- `Internal solid infill`
- `Top surface`
- `Bottom surface`
- `Ironing`
- `Bridge`
- `Internal Bridge`
- `Gap infill`
- `Skirt`
- `Brim`
- `Support`
- `Support interface`
- `Support transition`
- `Prime tower`
- `Custom`
- `Multiple`
- `Undefined`

Creality Print verwendet in aktuellen Versionen ebenfalls Begriffe wie Outer Wall und Sparse Infill; aktuelle Release Notes nennen z. B. `Outer Wall Transition Distance` und neue `Sparse Infill Pattern Types`, was gut zur Orca/Bambu-Terminologie passt. 

---

# 3. Cura / CuraEngine / ältere Creality Slicer / ältere Elegoo-Cura / viele CuraEngine-Forks

Dazu gehören:

- UltiMaker Cura
- CuraEngine
- Creality Slicer 4.x / ältere Creality Print-Versionen
- Elegoo Cura
- viele Hersteller-Slicer auf CuraEngine-Basis
- AstroPrint, wenn CuraEngine gewählt wird

CuraEngine beschreibt die großen Flächenklassen selbst als **walls, skin, infill und support**: Nach dem Layer-Schnitt werden Polygone nach Zweck gruppiert, z. B. ob sie mit Infill, Skin, Walls oder Support gefüllt werden sollen. 

## Offizielle / typische Cura-`;TYPE:`-Kommentare

Typisches Format:

```gcode
;TYPE:WALL-OUTER
```

Die Cura-GCodeReader-Logik erkennt u. a. folgende Typen:

| Cura-Feature | Bedeutung |
|---|---|
| `WALL-INNER` | innere Wand |
| `WALL-OUTER` | äußere Wand |
| `SKIN` | Top-/Bottom-Skin, horizontale geschlossene Haut |
| `SKIRT` | Skirt / teils Skirt-Brim-Hilfsstruktur |
| `SUPPORT` | Support |
| `FILL` | Sparse Infill |
| `SUPPORT-INTERFACE` | Support-Interface |
| `PRIME-TOWER` | Prime Tower |

Diese Typen stehen explizit im Cura-GCodeReader: `WALL-INNER`, `WALL-OUTER`, `SKIN`, `SKIRT`, `SUPPORT`, `FILL`, `SUPPORT-INTERFACE` und `PRIME-TOWER`. 

## Cura-Features, die existieren, aber nicht immer eigener `;TYPE:` sind

Diese können in Einstellungen, Preview, Substrukturen oder Forks vorkommen:

| Feature / Begriff | Hinweis |
|---|---|
| `BRIM` | manchmal eigener Typ in Tools/Forks, offiziell oft Skirt/Adhesion-Kontext |
| `RAFT` | Raft-Hilfsstruktur |
| `RAFTBASE` / `RAFT-BASE` | Raft-Unterlage |
| `RAFTINTERFACE` / `RAFT-INTERFACE` | Raft-Zwischenlage |
| `RAFTSURFACE` / `RAFT-SURFACE` | Raft-Oberfläche |
| `SUPPORT-INFILL` | Support-Infill, oft nur als Support klassifiziert |
| `SUPPORT-WALL` | Support-Außenwand / Support Outline |
| `SUPPORT-ROOF` | oberes Support-Interface |
| `SUPPORT-FLOOR` | unteres Support-Interface |
| `TREE-SUPPORT` | Geometrieart von Support, meist trotzdem `SUPPORT` |
| `BRIDGE` | Bridge-Region; nicht immer eigener `;TYPE:` |
| `WALL-OVERHANG` | Überhang-Wand; häufig über Einstellungen/Preview statt Kommentar |
| `IRONING` | Ironing-Pfade; je nach Version/Fork nicht immer eigener Kommentar |
| `DRAFT-SHIELD` | Draft Shield / Schutzwand |
| `OOZE-SHIELD` | Ooze Shield bei Dual Extrusion |
| `CUSTOM` | Postprocessing-/Custom-Kontext, nicht immer offizieller Cura-Typ |
| `MESH` | `;MESH:...` markiert Modellwechsel, aber kein Feature-Typ |

---

# 4. AstroPrint

AstroPrint ist keine eigene Feature-Kommentar-Familie im engeren Sinn. AstroPrint war/ist slicer-agnostisch und bot Cura Slicing Engine v3.6.0, Cura Engine 15.04 und Slic3r Prusa Edition an. Deshalb gilt:

- AstroPrint + CuraEngine ⇒ Cura-Featureliste
- AstroPrint + Slic3r/Prusa Edition ⇒ Prusa/Slic3r-Featureliste



---

# 5. Simplify3D

Simplify3D verwendet typischerweise Kommentare wie:

```gcode
; feature outer perimeter
```

oder zeigt diese Klassen in der Feature-Type-Preview.

## Klassische Simplify3D-Featuretypen

| Feature | Bedeutung |
|---|---|
| `Travel` | Leerfahrt |
| `Outer Perimeter` | äußerer Perimeter |
| `Inner Perimeter` | innerer Perimeter |
| `Gap Fill` | Lückenfüllung |
| `Solid Layer` | volle Top-/Bottom-/Solid-Schicht |
| `Infill` | Sparse Infill |
| `Bridge` | Brücke |
| `Support` | Support |
| `Dense Support` | dichter Support / Interface |
| `Raft` | Raft |
| `Skirt/Brim` | Skirt oder Brim |
| `Prime Pillar` | Prime-/Purge-Pillar |
| `Ooze Shield` | Ooze Shield / Abstreifwand |

Diese Feature-Type-Legende wird in Simplify3D-Dokumentation/Manuals genau so gezeigt. 

## Zusätzliche Simplify3D-V5-/Preview-/Subfeatures

| Feature | Hinweis |
|---|---|
| `External Single Extrusion` | dünne äußere Einzel-Extrusion |
| `Internal Single Extrusion` | dünne innere Einzel-Extrusion |
| `Dense Infill` | dichteres Infill nahe Top-Bereichen |
| `Solid Diaphragm` | interne horizontale Vollverstärkung |
| `Small Feature Reinforcement` | Verstärkung kleiner Inseln |
| `Support Outline` | Support-Außenkontur |
| `Short Perimeter` | kurze Perimeter-Speed-Klasse |
| `Bridging Perimeter` | Perimeter, der als Bridge behandelt wird |
| `Retraction` | Rückzug, eher Event/Move |
| `Tool Change` | Werkzeugwechsel, eher Event |

Simplify3D V5 Release Notes nennen u. a. Dense Infill, Solid Diaphragms, Small Feature Reinforcement, Support Outline, getrennte Dense-Support-Geschwindigkeiten, Short Perimeters und Bridging-Perimeter-Erkennung. 

---

# 6. ideaMaker / Raise3D

ideaMaker nutzt eine eigene Struktur-/Preview-Terminologie.

## ideaMaker-Strukturfeatures

| Feature | Bedeutung |
|---|---|
| `Infill` | Sparse Infill |
| `Solid Fill` | solide Füllung / Top/Bottom/Solid |
| `Ironing` | Ironing |
| `Bridge` | Bridge |
| `INNER-BRIDGE` | innerer Bridge-Ausgabetyp |
| `Inner Shell` | innere Wand |
| `Outer Shell` | äußere Wand |
| `Support` | Support |
| `Dense Support` | dichter Support / Interface |
| `Support Infill Outlines` | Umrisslinien im Support-Infill |
| `Dense Support Infill Outlines` | Umrisslinien in dichtem Support |
| `Skirt/Brim` | Skirt/Brim |
| `Raft` | Raft |
| `Wipe Wall` | Wipe Wall |
| `Wipe Tower` | Wipe Tower |
| `Tip Tower` | Tower-/Prime-Tower-Variante |
| `Travel` | Leerfahrt |
| `Retraction` | Rückzug |
| `Seams` | Nahtpunkte |

Raise3Ds ideaMaker-Dokumentation beschreibt die Structure-Ansicht mit Support/Raft, Outer Shell, Inner Shell, Infill und Bewegungen; ältere Handbücher zeigen zusätzlich Solid Fill, Bridge, Dense Support, Skirt/Brim, Wipe Wall/Tower, Travel und Retraction. Aktuelle Release Notes nennen außerdem `INNER-BRIDGE` sowie Support-/Dense-Support-Infill-Outlines. 

---

# 7. FlashPrint / FlashForge

FlashPrint verwendet eine eigene „Structure“-Legende und teils Kommentare wie:

```gcode
;structure:solid-fill
;structure:shell-inner
```

## FlashPrint-Strukturfeatures

| Feature | Bedeutung |
|---|---|
| `Infill` | Sparse Infill |
| `Solid Fill` | Solid / Top / Bottom Fill |
| `Bridge` | Bridge |
| `Inner Shell` | innere Wand |
| `Outer Shell` | äußere Wand |
| `Supports` | Support |
| `Brim` | Brim |
| `Raft` | Raft |
| `Wiping Tower` | Wiping-/Prime-Tower |
| `Wall` | generische Wand |
| `Travel` | Leerfahrt |
| `Retraction` | Rückzug |
| `Others` | sonstige / unbekannte Struktur |

Diese Liste erscheint in FlashPrint-/FlashForge-Manuals direkt in der Structure-Preview. 

---

# 8. Kiri:Moto / Grid.Space

Kiri:Moto ist etwas anders: Es arbeitet mit **Feature-Regionen** und bietet in G-Code-Macros den Platzhalter:

```text
{feature}
```

Dieser steht für die aktuelle Feature-Region, z. B. Brims oder Infill. 

## Kiri:Moto-FDM-Feature-/Region-Klassen

| Feature / Region | Bedeutung |
|---|---|
| `Shell` | Wände / Schalen |
| `Outer Shell` | äußere Shell, falls unterschieden |
| `Inner Shell` | innere Shell, falls unterschieden |
| `Sparse Fill` / `Infill` | Teilfüllung |
| `Solid Fill` | solide Füllung |
| `Top Fill` | obere Vollfläche |
| `Bottom Fill` | untere Vollfläche |
| `Bridge` | Bridge / Brückenbereich |
| `Support` | automatische oder gemalte Supportstruktur |
| `Painted Support` | manuell bemalte Supportregion |
| `Brim` | Brim |
| `Belt Lead` | Belt-Printer-Anfahr-/Adhäsionsstreifen |
| `Raft` | Raft |
| `Purge Tower` | Purge-/Prime-Tower |
| `Travel` | Leerfahrt |
| `Retraction` | Rückzug |
| `Custom Feature Macro` | per Macro erzeugte Feature-Transition |

Die Kiri:Moto-Prozessprofile enthalten u. a. Shells, Sparse Fill, Support, Brim, Belt Lead und Raft; Release Notes nennen zusätzlich FDM Feature Macros, Support-Painting, Bridge-Verbesserungen und Purge-Tower-Verbesserungen. 

---

# 9. KISSlicer

KISSlicer schreibt nicht überall so moderne `;TYPE:`-Rollen wie Prusa/Orca/Cura, hat aber eigene Feature-/Pfadklassen.

## KISSlicer-Featureklassen

| Feature | Bedeutung |
|---|---|
| `Perimeter` | äußerer/innerer Loop je nach Kontext |
| `Loops` | Wand-/Shell-Loops |
| `Infill` | internes Infill |
| `Sparse Infill` | Teilfüllung |
| `Solid Infill` | Vollfüllung |
| `Upper Face` | obere Fläche |
| `Lower Face` | untere Fläche |
| `Support` | Support |
| `Support Main` | Hauptsupport |
| `Support Interface` | Kontakt-/Interface-Support, wenn konfiguriert |
| `Gap Fill` / `Crowning` | Füllen kleiner Lücken / dünner Bereiche |
| `Skirt` | Skirt |
| `Prime Pillar` | Prime Pillar |
| `Prime Wall` / `Wipe Wall` | Wipe-/Prime-Wand |
| `Wipe` | Wipe-Bewegung |
| `Travel` | Leerfahrt |
| `Retract` / `De-string` | Rückzug / Entstringing |
| `Raft` | Raft, falls genutzt |

KISSlicer-Dokumentation nennt u. a. Default Object mit Perimeter, Infill und upper/lower faces, Support, Include Comments, Prime Pillar/Skirt/Wall und Wipe-Pillar/Wall-Strategien. 

---

# 10. CraftWare / Craftware

CraftWare wird vom Prusa-G-Code-Viewer als interpretierbarer Slicer genannt, aber die Feature-Kommentar-Ausgabe ist weniger einheitlich dokumentiert als bei Prusa/Cura/Orca. Praktisch relevante Featureklassen sind:

| Feature | Bedeutung |
|---|---|
| `Perimeter` / `Wall` | Wände |
| `Outer Wall` | äußere Wand |
| `Inner Wall` | innere Wand |
| `Infill` | Sparse Infill |
| `Solid Fill` | Vollfüllung |
| `Top/Bottom` | horizontale Hautflächen |
| `Bridge` | Bridge |
| `Support` | Support |
| `Support Interface` | dichter Kontakt-Support |
| `Skirt` | Skirt |
| `Brim` | Brim |
| `Raft` | Raft |
| `Travel` | Leerfahrt |
| `Retraction` | Rückzug |
| `Unknown` | nicht erkannte Rolle |

Für CraftWare/Craftware gilt besonders: Viewer können häufig die Geometrie darstellen, aber nicht immer die Feature-Zeitanteile zuverlässig aus Kommentaren ableiten. Prusa weist allgemein darauf hin, dass bei fremden Slicern manche Feature-Analysen fehlen können, weil der G-Code nicht alle nötigen Informationen enthält. 

---

# 11. MakerBot / MakerWare / Sailfish / ältere X3G-nahe Slicer

Bei älteren MakerBot-/Sailfish-/X3G-nahen Workflows gibt es oft weniger moderne `;TYPE:`-Kommentare. Relevante Featureklassen sind typischerweise:

| Feature | Bedeutung |
|---|---|
| `Perimeter` | Wand |
| `Shell` | Shell/Wandverbund |
| `Infill` | Füllung |
| `Solid Fill` | Vollfüllung |
| `Bridge` | Bridge |
| `Support` | Support |
| `Raft` | Raft |
| `Floor` / `Roof` | Boden-/Deckschichten |
| `Travel` | Leerfahrt |
| `Retract` | Rückzug |
| `Purge` | Prime/Purge-Sequenz |
| `Tool Change` | Werkzeugwechsel |

Diese Familie ist für modernes rollenbasiertes Postprocessing weniger geeignet, weil Feature-Kommentare oft fehlen oder proprietär sind.

---

# 12. Zusammengeführte Masterliste aller Featureklassen

Wenn man **alle Familien zusammenfasst**, ergibt sich diese Masterliste:

## Wände / Shells

- `Outer Wall`
- `Inner Wall`
- `Wall`
- `Shell`
- `Outer Shell`
- `Inner Shell`
- `Perimeter`
- `External perimeter`
- `Inner perimeter`
- `Outer Perimeter`
- `Overhang wall`
- `Overhang perimeter`
- `Short Perimeter`
- `Bridging Perimeter`
- `External Single Extrusion`
- `Internal Single Extrusion`
- `Thin Wall`
- `Loop`
- `Contour`
- `Hole perimeter`

## Infill / Füllung

- `Internal infill`
- `Sparse infill`
- `Infill`
- `FILL`
- `Sparse Fill`
- `Solid infill`
- `Internal solid infill`
- `Solid Fill`
- `Solid Layer`
- `Dense Infill`
- `Solid Diaphragm`
- `Small Feature Reinforcement`
- `Infill Over Bridge`
- `Support Infill`
- `Infill Skin Support`
- `Gap fill`
- `Gap infill`
- `Crowning`
- `Thin Gap Fill`

## Top / Bottom / Skin

- `Top solid infill`
- `Top surface`
- `Top Fill`
- `Top Skin`
- `Top Surface Skin`
- `Bottom surface`
- `Bottom Fill`
- `Bottom Skin`
- `SKIN`
- `Roof`
- `Floor`
- `Upper Face`
- `Lower Face`
- `Solid Top`
- `Solid Bottom`
- `Ironing`

## Bridges / Überhänge

- `Bridge`
- `Bridge infill`
- `Bridge Fill`
- `Bridge Skin`
- `Bridge Wall`
- `Internal Bridge`
- `Internal bridge infill`
- `INNER-BRIDGE`
- `Overhang Wall`
- `Overhang Perimeter`

## Support

- `Support`
- `Supports`
- `Support material`
- `Support Infill`
- `Support Main`
- `Support Wall`
- `Support Outline`
- `Support Infill Outlines`
- `Support Interface`
- `Support material interface`
- `Support interface`
- `Support roof`
- `Support floor`
- `Dense Support`
- `Dense Support Infill Outlines`
- `Support Transition`
- `Tree Support`
- `Organic Support`
- `Painted Support`
- `Manual Support`
- `Support Base`
- `Support Brim`

## Bettadhäsion / Base Features

- `Skirt`
- `Brim`
- `Skirt/Brim`
- `Mouse Ears`
- `Brim Ears`
- `Raft`
- `Raft Base`
- `Raft Interface`
- `Raft Surface`
- `Raft Top`
- `Belt Lead`

## Multi-Material / Purge / Wipe

- `Wipe tower`
- `Prime tower`
- `Prime Pillar`
- `Tip Tower`
- `Wiping Tower`
- `Purge Tower`
- `Purge Block`
- `Wipe Wall`
- `Prime Wall`
- `Ooze Shield`
- `Draft Shield`
- `Purge Line`
- `Prime Blob`
- `Tool Change`
- `Color Change`
- `Filament Change`

## Bewegungen / Events

- `Travel`
- `Retract`
- `Retraction`
- `Unretract`
- `Deretract`
- `Prime`
- `Wipe`
- `Seam`
- `Pause Print`
- `Custom`
- `Custom GCode`
- `Extrude`
- `Noop`
- `Unknown`
- `Undefined`
- `Others`
- `Mixed`
- `Multiple`

---

# 13. Wichtigste Alias-Gruppen

Wenn du einen Parser oder Postprocessor bauen willst, solltest du diese Synonyme zusammenfassen:

| Kanonische Klasse | Aliase |
|---|---|
| Außenwand | `External perimeter`, `Outer wall`, `WALL-OUTER`, `Outer Perimeter`, `Outer Shell`, `shell-outer` |
| Innenwand | `Perimeter`, `Inner wall`, `WALL-INNER`, `Inner Perimeter`, `Inner Shell`, `shell-inner` |
| Sparse Infill | `Internal infill`, `Sparse infill`, `FILL`, `Infill`, `Sparse Fill` |
| Solid Infill | `Solid infill`, `Internal solid infill`, `Solid Fill`, `Solid Layer` |
| Top Surface | `Top solid infill`, `Top surface`, `Top Skin`, `Roof`, `Upper Face` |
| Bottom Surface | `Bottom surface`, `Bottom Skin`, `Floor`, `Lower Face` |
| Skin | `SKIN`, Top/Bottom/Solid surface |
| Bridge | `Bridge infill`, `Bridge`, `Internal Bridge`, `INNER-BRIDGE` |
| Gap Fill | `Gap fill`, `Gap infill`, `Crowning`, `Thin Wall Fill` |
| Support | `Support material`, `Support`, `SUPPORT`, `Supports` |
| Support Interface | `Support material interface`, `Support interface`, `SUPPORT-INTERFACE`, `Dense Support`, `Support Roof/Floor` |
| Skirt/Brim | `Skirt`, `Brim`, `Skirt/Brim`, `SKIRT`, `BRIM` |
| Raft | `Raft`, `RAFT`, `Raft Base`, `Raft Interface`, `Raft Surface` |
| Prime Tower | `Wipe tower`, `Prime tower`, `Prime Pillar`, `Wiping Tower`, `Tip Tower`, `Purge Tower` |
| Custom/Unknown | `Custom`, `Custom GCode`, `Unknown`, `Undefined`, `Others`, `Mixed`, `Multiple` |

---

**Kurz gesagt:**  
Wenn du wirklich „nichts vergessen“ willst, solltest du nicht nur nach `;TYPE:` suchen. Du brauchst eine **Alias-Tabelle**, die Prusa/Orca/Bambu, Cura, Simplify3D, ideaMaker, FlashPrint, Kiri:Moto und Legacy-Slicer zusammenführt. Die Masterliste oben ist dafür die vollständige praktische Taxonomie.
