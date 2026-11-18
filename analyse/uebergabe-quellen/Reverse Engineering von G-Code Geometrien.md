*Hinweis vorab zur PDF-Erstellung: Als KI-Sprachmodell kann ich keine direkte `.pdf`-Datei als Download generieren. Ich habe dieses Dokument jedoch als **umfassendes Whitepaper im Markdown-Format** strukturiert. Du kannst es direkt kopieren und in einem Tool wie Typora, Obsidian oder einem Online-Markdown-to-PDF-Konverter einfügen – oder einfach hier im Browser **Strg+P** (bzw. Cmd+P) drücken und "Als PDF speichern" wählen. Es ist exakt dafür formatiert.*

---

# G-Code Reverse Engineering: Die ultimative Taxonomie und geometrische Erkennungs-Matrix für 3D-Druck-Features

Dieses Dokument liefert die vollständige mathematische, logische und topologische Grundlage, um **geslicten G-Code (der keine Kommentare enthält) blind per Reverse Engineering zu decodieren**. Es listet alle existierenden Features und Muster aller Slicer-Familien auf und definiert die Algorithmen zur Erkennung.

---Mit dieser Kombination aus mehrstufigem Parsing, Vektor-Kalkül, Booleschen Operationen zwischen den Z-Layern und Flow-Analyse ist es **mathematisch unausweichlich**, jedes Feature exakt zu rekonstruieren, selbst wenn der Slicer jeden einzelnen erklärenden Kommentar aus der Datei gelöscht hat.


## TEIL 1: Vollständige Taxonomie der Features und Muster

### 1.1 Feature-Typen (Universell)
Jeder G-Code-Pfad lässt sich in exakt eine dieser ontologischen Kategorien einordnen:

1.  **Perimeter (Wände):**
    *   *Outer Perimeter:* Äußerste geschlossene Kontur (direkter Kontakt zur Umgebung).
    *   *Inner Perimeter:* Innere geschlossene Konturen.
    *   *Overhang Perimeter:* Wandbereiche ohne Unterstützung im Layer $N-1$.
    *   *Thin Wall / Single Extrusion:* Wand, die exakt eine Linienbreite dick ist (keine Innen/Außen-Paare).
2.  **Surfaces & Solid Infill (Solide Flächen, Dichte $\approx$ 100%):**
    *   *Bottom Surface:* Unterste Schicht (Luft oder Bett darunter).
    *   *Top Surface:* Oberste Schicht (Luft darüber).
    *   *Solid Infill:* Versteckende dichte Schichten zwischen Top/Bottom und Sparse Infill.
    *   *Ironing:* Glättungspfade (Extrusion $E \approx 0$).
3.  **Sparse Infill (Spärliche Füllung, Dichte < 100%):**
    *   *Internal Infill:* Die innere Gitterstruktur.
    *   *Gap Fill:* Dynamische Einzellinien zum Füllen sub-dimensionaler Lücken zwischen Perimetern.
4.  **Bridges (Brücken):**
    *   *Bridge Infill:* Freischwebende Bahnen, an Ankerpunkten befestigt.
    *   *Internal Bridge:* Brücken über spärlichem Infill.
5.  **Support (Stützstrukturen):**
    *   *Support Base / Normal:* Der Hauptkörper der Stütze.
    *   *Support Interface (Roof/Floor):* Dichte Übergangsschicht (meist 2-4 Layer) direkt am Bauteil.
    *   *Support Transition:* Übergangszone zwischen Base und Interface.
6.  **Helper (Hilfsobjekte außerhalb des Modells):**
    *   *Skirt:* Umrandung (Kontaktlos).
    *   *Brim:* Umrandung (Bauteilkontakt).
    *   *Raft (Base/Interface/Surface):* Unterbau.
    *   *Prime Tower / Wipe Tower / Prime Pillar:* Reinigungsstrukturen.
    *   *Ooze Shield / Wipe Wall:* Schutzwände bei Dual-Extrusion.

### 1.2 Alle Füllmuster (Infill Patterns)
Die Muster zur Füllung des Kerns definieren die XY-Bewegungsvektoren.

*   **Linear & Raster:** Rectilinear, Aligned Rectilinear, Grid, Triangles, Stars / Tri-Hexagon, Cubic, Adaptive Cubic, Support Cubic, Quarter Cubic, Line, Cross, Cross 3D, Zig-Zag.
*   **Kurvig & Organisch:** Gyroid, Honeycomb, 3D Honeycomb, Concentric, Hilbert Curve, Archimedean Chords, Octagram Spiral, Lightning, Organic/Tree (bei Supports).

### 1.3 Alle Surface-Muster (Top/Bottom/Solid/Interface)
Diese werden primär für dichte Oberflächen ($100\%$ Dichte) genutzt:
*   *Monotonic / Monotonic Lines:* Parallele Linien, strikt in eine Richtung gezeichnet (kein Hin-und-Her-Wechseln der Bereiche), verhindert Lichtbrechungs-Artefakte.
*   *Rectilinear:* Klassisches Zick-Zack (oft im $45^\circ$-Winkel).
*   *Concentric:* Konzentrische Ringe von außen nach innen.
*   *Snug:* Spezielles Support-Muster, das die Umrisse des Überhangs exakt umschließt.

---

## TEIL 2: Algorithmen zum Reverse Engineering (Erkennung ohne Kommentare)

Wenn ein G-Code nackt vorliegt (nur $G1 X.. Y.. Z.. E.. F..$), müssen wir aus den Variablen Koordinaten, Fluss und Geschwindigkeit auf die Geometrie schließen. Dies erfordert ein kaskadierendes System aus Mathematik, Topologie und Ausschlussverfahren.

### Ansatz A: Multi-Pass-Analyse (Die Makro-Architektur)
Um G-Code zu decodieren, darf man ihn nicht nur zeilenweise von oben nach unten lesen. Man benötigt mehrere Durchläufe (Passes), um ein Zustandsmodell aufzubauen.

*   **Pass 1 (Z-Parsing & Bounding Box):**
    *   *Aktion:* Scanne die gesamte Datei nach Z-Werten. Erstelle ein Array aller Layer $L_0$ bis $L_{max}$.
    *   *Berechnung:* Ermittle pro Layer die 2D-Bounding-Box $[X_{min}, X_{max}, Y_{min}, Y_{max}]$.
    *   *Erkenntnis:* Trennt den Code in diskrete, mathematisch analysierbare 2D-Ebenen.
*   **Pass 2 (Geschwindigkeits- und Extrusions-Profiling):**
    *   *Aktion:* Sammle alle vorkommenden Feedrates ($F$) und Extrusionsraten ($E_{mm} / \text{Distanz}$).
    *   *Erkenntnis:* Bildet Cluster. Cluster 1 (sehr schnell, wenig Fluss) = Travel. Cluster 2 (langsam, exakter Fluss) = Outer Perimeter. Cluster 3 (schnell, normaler Fluss) = Infill.
*   **Pass 3 (Objekt-Trennung & Hilfsstrukturen):**
    *   *Aktion:* Finde zusammenhängende Graphen (Pfade) in Layer 0.
    *   *Ausschlussverfahren:* Das äußerste Polygon, das nicht gefüllt wird und keine inneren Pfade berührt, ist der **Skirt**. Polygone, die am Modell kleben, aber in $Z > 0$ verschwinden, sind der **Brim**.

### Ansatz B: Komplexe Mathematik (Pfad-Kinematik)
Jede Zeile $G1 X_{i} Y_{i} E_{i}$ ist ein Vektor $\vec{v}$.

1.  **Längen- und Volumenberechnung:**
    *   Länge: $L = \sqrt{(X_i - X_{i-1})^2 + (Y_i - Y_{i-1})^2}$
    *   Fluss-Ratio (Flow): $W = \frac{\Delta E}{L}$ (Extrudiertes Material pro mm).
2.  **Extrusions-Logik zur Feature-Erkennung:**
    *   Ist $W \approx 0$ und $F$ hoch $\rightarrow$ **Travel Move**.
    *   Ist $W > 0$ sehr klein, Distanz $L$ moderat, $F$ moderat, Abstand zu anderen Linien sehr eng $\rightarrow$ **Ironing** (Glättung).
    *   Ist $W \gg W_{standard}$ (Extremer Fluss, dicke Linien) $\rightarrow$ Oft **Bridge Infill** (da Brücken ohne Bettkontakt mehr Material brauchen, um nicht zu reißen, oft rund statt platt gedrückt).
3.  **Winkel- und Kurvenanalyse (Derivation der Pfade):**
    *   Skalarprodukt zweier aufeinanderfolgender Vektoren $\vec{v}_1, \vec{v}_2$: $\cos(\theta) = \frac{\vec{v}_1 \cdot \vec{v}_2}{|\vec{v}_1| |\vec{v}_2|}$
    *   *Gyroid Infill:* $\theta$ ändert sich stetig und glatt (Sinuswelle), es gibt keine Winkel $< 90^\circ$.
    *   *Rectilinear Infill / Solid:* Häufige $90^\circ$ oder $180^\circ$ (Zick-Zack) Umkehrungen.
    *   *Perimeter:* Geschlossene, meist glatte Polygone ohne plötzliche $180^\circ$-Wenden.

### Ansatz C: 2D XY Schicht- und Pfadanalyse (Intra-Layer Topologie)
Betrachten wir einen einzelnen Layer $L_n$ in 2D.

1.  **Die Geschlossen-Loop-Regel (Erkennung von Perimetern):**
    *   *Bedingung:* Wenn ein zusammenhängender Extrusionspfad $P_1 \rightarrow P_2 \dots \rightarrow P_k$ die Eigenschaft $P_k = P_1$ besitzt (Startpunkt = Endpunkt), ist es fast garantiert ein **Perimeter**, **Hole** (Loch-Wand), **Skirt** oder ein **Ooze Shield**.
    *   *Unterscheidung:* Ray-Casting. Wir schießen einen mathematischen Strahl vom Rand der Bounding Box in das Zentrum. Der erste geschlossene Loop, den der Strahl trifft, ist der **Outer Perimeter**. Der zweite ist der **Inner Perimeter**.
2.  **Liniendichte-Analyse (Solid vs. Sparse Infill):**
    *   Sei $D$ der orthogonale Abstand zwischen zwei parallelen Bahnen. Sei $w$ die theoretische Linienbreite.
    *   *Bedingung:* Wenn $D \approx w$ (Bahnen berühren sich lückenlos) $\rightarrow$ **Solid Infill**, **Top** oder **Bottom Surface**.
    *   *Bedingung:* Wenn $D \gg w$ (z.B. $D = 5w$) $\rightarrow$ **Sparse Infill**.
3.  **Lücken-Logik (Gap Fill Erkennung):**
    *   *Symptomatik:* Kurze, unregelmäßige Vektoren ($L$ sehr klein), die zwischen zwei erkannten Perimetern liegen, wo der Abstand kleiner als $2w$ ist. Der Fluss $W$ variiert hier stark, weil der Slicer den Flow drosselt, um Über-Extrusion in der Lücke zu vermeiden.

### Ansatz D: Schichtvergleich in der Z-Achse (Inter-Layer Topologie)
Das mächtigste Werkzeug. Features definieren sich oft dadurch, was *unter* oder *über* ihnen ist.
Wir definieren das "Solide Polygon" $S_n$ als die Fläche in Layer $n$, die mit Material gefüllt ist.

1.  **Top Surface (Oberste Schicht) Erkennung:**
    *   *Bedingung:* Berechne die Boolesche Differenz $S_n \setminus S_{n+1}$.
    *   *Resultat:* Bereiche, die in Layer $n$ gedruckt werden, in Layer $n+1$ aber leer sind (Luft), sind zwingend **Top Surface**.
2.  **Bottom Surface / Overhang / Bridge Erkennung:**
    *   *Bedingung:* Berechne Boolesche Differenz $S_n \setminus S_{n-1}$.
    *   *Resultat:* Bereiche in Layer $n$, unter denen in $n-1$ Nichts ist.
    *   *Unterscheidung Bridge vs. Overhang:* Wenn dieser schwebende Bereich am Rand einer geschlossenen Perimeter-Schleife liegt $\rightarrow$ **Overhang Perimeter**. Besteht der Bereich aus parallelen Linien, die an *zwei* Enden in soliden $n-1$ Bereichen verankert sind $\rightarrow$ **Bridge Infill**.
3.  **Support-Erkennung durch Isolation:**
    *   *Regel:* Supportstrukturen liegen fast immer *außerhalb* des inneren Perimeters des Hauptmodells.
    *   *Vergleich:* Wenn ein Polygon in Layer $n$ keine Schnittmenge mit den Haupt-Modell-Polygonen aus Layer $n \dots n+k$ hat, aber langsam in Z-Richtung wächst, bis es schließlich die *Unterseite* (Bottom Surface) eines Überhangs berührt, ist es **Support**.
4.  **Support Interface Erkennung:**
    *   *Verlauf in Z:* Ein Support-Turm hat Schicht $n-10$ bis $n-3$ eine Dichte von $15\%$ (Support Base). In Schicht $n-2$ und $n-1$ steigt die Liniendichte plötzlich auf $>80\%$ (Abstand $D \approx w$). Dies ist mathematisch einwandfrei als **Support Interface** identifizierbar.

### Ansatz E: Das Logische Ausschlussverfahren (Die finale Filter-Matrix)
Wenn die obigen Methoden kombiniert werden, lässt sich jeder Pfad durch Eliminierung zuordnen:

1.  *Ist es Extrusion?* (Nein $\rightarrow$ Travel. Ja $\rightarrow$ Weiter).
2.  *Ist Z = 0 und außerhalb der Modellprojektion?* (Ja $\rightarrow$ Skirt/Brim/Raft. Nein $\rightarrow$ Weiter).
3.  *Ist es ein geschlossener Loop?* (Ja $\rightarrow$ Perimeter. Welche Ebene? Äußerste = Outer. Sonst = Inner. Nein $\rightarrow$ Weiter).
4.  *Gibt es Material direkt darunter ($N-1$)?* (Nein $\rightarrow$ Bridge oder Overhang. Ja $\rightarrow$ Weiter).
5.  *Gibt es Material direkt darüber ($N+1$)?* (Nein $\rightarrow$ Top Surface. Ja $\rightarrow$ Weiter).
6.  *Ist die Liniendichte hoch ($D \approx w$)?* (Ja $\rightarrow$ Solid Infill. Nein $\rightarrow$ Weiter).
7.  *Liegt es außerhalb der Perimeter, stützt aber das Modell?* (Ja $\rightarrow$ Support. Nein $\rightarrow$ Weiter).
8.  *Was bleibt übrig?* $\rightarrow$ **Sparse Infill** oder **Gap Fill** (abhängig von Pfadlänge).

---

## ZUSAMMENFASSUNG: Die Erkennungs-Matrix (Cheat Sheet)

| Gesuchtes Feature | Kinetische Signatur (Flow/Speed) | Intra-Layer Topologie (XY) | Inter-Layer Topologie (Z) |
| :--- | :--- | :--- | :--- |
| **Outer Perimeter** | Langsam, konstanter Flow. | Äußerster geschlossener Loop. | Keine Relevanz. |
| **Inner Perimeter** | Medium, konstanter Flow. | Innere geschlossene Loops. | Keine Relevanz. |
| **Top Surface** | Langsam/Medium, Flow 100%. | Parallele Linien, Linienabstand $\approx w$. | Keine Extrusion in Z+1 an dieser XY-Koordinate. |
| **Bottom Surface** | Langsam, oft erhöhter Flow. | Parallele Linien, Linienabstand $\approx w$. | Keine Extrusion in Z-1 an dieser XY-Koordinate. |
| **Sparse Infill** | Schnell, teils dickerer Flow. | Geometrisches Raster, Linienabstand $\gg w$. | Umschlossen von Perimetern. |
| **Bridge Infill** | Langsam/Medium, Flow modifiziert. | Parallele Gerade, exakt 2 Ankerpunkte. | Schwebt vollständig in der Luft (Z-1 ist leer). |
| **Ironing** | Extrem langsam, Flow $\approx 1\%-5\%$. | Sehr enges, paralleles Zick-Zack-Raster. | Immer auf einer Top Surface. |
| **Support Base** | Sehr schnell, oft Unter-Extrusion. | Spärliches Gitter, offen oder organisch. | Liegt außerhalb der X/Y Projektion des Modells. |
| **Support Interface**| Medium/Schnell, Flow 100%. | Sehr dichtes Raster ($D \approx w$). | Unterbricht die Support Base in $Z-1$, stützt in $Z+1$ das Modell. |
| **Gap Fill** | Variiert start (dynamisch), Zitterbewegungen. | Sub-dimensionale Räume ($< 2w$). | Gefangen zwischen Perimetern. |

Mit dieser Kombination aus mehrstufigem Parsing, Vektor-Kalkül, Booleschen Operationen zwischen den Z-Layern und Flow-Analyse ist es **mathematisch unausweichlich**, jedes Feature exakt zu rekonstruieren, selbst wenn der Slicer jeden einzelnen erklärenden Kommentar aus der Datei gelöscht hat.

Ja. **Hier ist die Master-Liste der bekannten FDM/FFF-Feature-Rollen über die großen Slicer-Familien hinweg**. Wichtig: Manche Einträge sind **echte G-Code-Kommentare** wie `;TYPE:...`, manche sind **Preview-/Strukturtypen**, und manche sind **interne Rollen**, die nicht immer 1:1 als Kommentar ausgegeben werden.

**Ganz wichtig:** Es gibt keinen ISO-Standard für diese Feature-Namen. „Alle“ heißt hier: alle öffentlich dokumentierten, im Quellcode sichtbaren oder in Preview-Legenden belegten Rollen der relevanten Familien Prusa/Slic3r/SuperSlicer, Bambu/Orca/Elegoo/Creality-modern, Cura/CuraEngine, Simplify3D, FlashPrint, ideaMaker, Kiri:Moto, KISSlicer, CraftWare, MatterSlice/MatterControl und IceSL.

---

Hier ist das ultimative, tiefgehende Kompendium zur **G-Code-Geometrie-Analyse und zum Reverse Engineering**. 

*Hinweis vorab zur PDF-Erstellung:* Als KI-Sprachmodell kann ich dir nicht direkt eine `.pdf`-Datei als Download generieren. **Aber:** Ich habe dieses Dokument perfekt in Markdown formatiert. Du kannst diesen Text einfach kopieren, in einen Markdown-Editor (wie Typora, Obsidian oder dillinger.io) einfügen und von dort mit einem Klick als perfekt gesetztes PDF (inkl. Inhaltsverzeichnis und mathematischen Formeln) exportieren. Alternativ reicht im Browser oft `Strg+P` $\rightarrow$ "Als PDF speichern".

---

# Das G-Code Reverse Engineering Kompendium
**Mathematische, topologische und kinetische Analyse von Slicer-Geometrien zum effektiven Ausschlussverfahren ohne Metadaten.**

Wenn ein Slicer keine `;TYPE:`-Kommentare schreibt, besteht die Datei nur aus Koordinaten ($X, Y, Z$) und Extrusionswerten ($E$). Um herauszufinden, *was* der Drucker gerade druckt, müssen wir den Code durch verschiedene analytische Brillen betrachten.

---

## TEIL 1: TABELLEN & LISTEN (Die zu erkennenden Muster)

Bevor wir analysieren, müssen wir die Zielmuster exakt definieren. 

### 1.1 Füllmuster (Sparse Infill) - Geometrische Signaturen
| Muster | Geometrische Vektor-Signatur in der 2D-Schicht ($L_n$) | Schichtvergleich ($L_n$ vs. $L_{n+1}$) |
| :--- | :--- | :--- |
| **Rectilinear / Lines** | Parallele Liniensegmente mit konstanten Abständen. | Rotation der Vektoren um 90° im nächsten Layer. |
| **Grid** | Sich kreuzende, orthogonal zueinander stehende Linien *im selben Layer*. | Exakte Kopie im nächsten Layer (oft versetzt). |
| **Triangles / Tri-Hex** | Drei Sets von parallelen Linien, die sich in 60°/120°-Winkeln schneiden. | Konstantes Muster, baut vertikale Säulen auf. |
| **Cubic / Octet** | Sich kreuzende Linien. | Linien verschieben sich (Translation) pro Layer in XY, um 3D-Volumen (Würfel/Tetraeder) zu formen. |
| **Gyroid** | Kontinuierliche Kurven (Splines/Arcs) ohne Kreuzungen im Layer. Keine scharfen Winkel. | Kurven invertieren ihre Phase/Richtung periodisch in Z. |
| **Concentric** | Geschlossene Polygone (Loops), die sich nicht kreuzen. | Skalierung (Offset) nach innen, Geometrie folgt der Außenwand. |
| **Lightning** | Baumartige, verästelte Linienstrukturen. | Beginnen an den Wänden und wachsen mit ansteigendem Z nach innen, um Top-Schichten zu stützen. |
| **Honeycomb** | Kurze Vektoren, die Sechsecke (Waben) bilden. Zick-Zack-Pfad mit 60°/120°-Knicken. | Exakte Kopie im nächsten Layer. |

### 1.2 Top / Bottom / Solid Muster
Diese Muster weisen immer eine Fülldichte von ca. 100% auf (Extrusionsbreite $\approx$ Linienabstand).
| Muster | Vektor-Signatur & Kinetik |
| :--- | :--- |
| **Rectilinear** | Dicht aneinander liegende parallele Linien. Richtungswechsel oft mit kurzen Travel-Moves. |
| **Monotonic** | Wie Rectilinear, aber Vektoren werden *immer* in dieselbe Richtung aufgebaut (z.B. streng von links nach rechts). Keine Sprünge zurück. |
| **Concentric** | Konzentrische, dichte Offsets. Endet oft in einem zentralen kleinen Gap Fill. |
| **Hilbert Curve** | Extrem kurze, orthogonale Vektoren (Fraktale). Ständiger Richtungswechsel (90°), langsame Geschwindigkeit, stotternde Kinetik. |
| **Archimedean** | Spiraliger, kontinuierlicher Pfad von der Mitte nach außen (oder umgekehrt). |

### 1.3 Support & Interface Muster
| Muster | Vektor-Signatur ($L_n$) | Topologische Z-Signatur |
| :--- | :--- | :--- |
| **Grid / Zig-Zag** | Weites Gitter oder kontinuierliche Zick-Zack-Mäander. | Liegt streng *unterhalb* eines Überhangs. |
| **Snug / Organic / Tree** | Komplexe organische Formen, zylindrische/röhrenartige Perimeter. | Verjüngt sich nach oben (Tree) oder folgt eng dem Modell (Snug). |
| **Interface (Dense)** | Muster wie Rectilinear oder Concentric, sehr dicht (>80%). | Existiert *nur* 1-4 Layer direkt unter/über dem Modell. Z-Abstand zum Modell weicht vom Standard-Layer ab! |

---

## TEIL 2: DIE 6 ANSÄTZE ZUR GEOMETRIE-ERKENNUNG (Reverse Engineering)

Um aus purem G-Code `G1 X10 Y10 E0.5 F3000` das Feature zu erkennen, nutzen wir ein mehrstufiges Ausschlussverfahren (Multi-Pass-Analyse).

### Ansatz A: Kinetische & Komplexe Mathematische Analyse (1D)
Hier betrachten wir nur den einzelnen G-Code-Befehl und berechnen die physikalischen Eigenschaften der Extrusion.

**1. Die Geschwindigkeits-Signatur ($F$-Wert)**
*   $F$ (Feedrate) ändert sich je nach Feature. Im Slicer-Profil sind Geschwindigkeiten definiert.
*   *Logik:* $V_{OuterWall} < V_{InnerWall} \ll V_{Infill}$.
*   *Ausschluss:* Langsame kontinuierliche Fahrten sind Wände oder Oberflächen. Sehr schnelle Fahrten sind Infill.

**2. Die Extrusions-Volumen-Gleichung (Flow-Analyse)**
Sei $d_{xy}$ die euklidische Distanz des Moves: $d_{xy} = \sqrt{(X_2-X_1)^2 + (Y_2-Y_1)^2}$.
Sei $E$ das extrudierte Filament.
Das extrudierte Volumen $V$ ist: $V = E \cdot \pi \cdot (d_{fil}/2)^2$ (mit $d_{fil} = 1.75$ mm).
Die Querschnittsfläche der Linie $A = V / d_{xy}$.

*   **Reguläre Extrusion (Wände/Infill):** $A \approx W \cdot H$ (Linienbreite $\times$ Layerhöhe, abzüglich elliptischer Ränder).
*   **Bridge-Erkennung (Brücken):** Bei Brücken wird das Filament nicht auf das Bett gequetscht, sondern in die Luft gezogen. Der Querschnitt ist ein runder Faden!
    *   *Mathematischer Beweis:* Wenn $A \approx \pi \cdot (H/2)^2$, und die Kühlung (M106 S255) auf 100% springt, ist dieser Vektor **zweifelsfrei eine Brücke**.
*   **Gap Fill / Ironing:** Wenn $A \ll W \cdot H$ (extrem wenig Extrusion pro Strecke) oder $E \approx 0$ bei langsamer Fahrt, ist es **Ironing**. Wechselt $A$ stark und oszilliert, ist es **Gap Fill**.

### Ansatz B: 2D XY Schicht- und Pfadanalyse (Vektorgeometrie)
Wir betrachten alle zusammenhängenden Extrusionen innerhalb *einer* Schicht ($L_n$).

**1. Die Loop-Erkennung (Perimeter)**
*   Sei ein Pfad $P = \{v_1, v_2, ..., v_k\}$ eine Sequenz von Vektoren.
*   Wenn $Start(v_1) \approx End(v_k)$ (der Pfad schließt sich selbst zu einem Polygon), ist dieses Polygon eine Kontur.
*   *Zuweisung:* Geschlossene, nicht selbst-schneidende Polygone sind **Perimeter**, **Brim**, **Skirt** oder **Hole-Wände**.

**2. Bounding-Box und Konvexe Hülle (Skirt/Brim Identifikation)**
*   Ist das Polygon $P$ vollständig isoliert von allen anderen Polygonen der Schicht?
*   Umschließt das Polygon $P$ die konvexe Hülle aller anderen Geometrien?
*   *Logik:* Wenn ja, und es ist Schicht 0 $\rightarrow$ **Skirt**. Wenn es die Geometrie berührt $\rightarrow$ **Brim**.

**3. Winkel-Analyse (Infill vs. Solid)**
*   Berechnung des Winkels $\theta$ zwischen aufeinanderfolgenden Linien (nach einem Travel-Move).
*   *Logik:* Sind viele parallele Linien mit Abstand $d \approx W$ (Düse) vorhanden, ist es **Solid Infill / Top / Bottom**. Sind die Abstände $d \gg W$, ist es **Sparse Infill**.
*   Kreuzen sich Vektoren (Schnittpunkt-Mathematik in 2D) innerhalb desselben Pfades, ist es z.B. **Grid Infill**.

### Ansatz C: Schichtvergleich / 3D Topologie (Z-Analyse)
Das stärkste Werkzeug. Wir betrachten drei Schichten gleichzeitig: $L_{n-1}$ (unten), $L_n$ (aktuell), und $L_{n+1}$ (oben). Wir konvertieren die Pfade in gefüllte 2D-Polygone (Boolean Maps).

**Mathematische Mengenlehre für Features:**
1.  **Bottom Surface (Unterste Schicht):**
    *   Menge $M = Polygon(L_n) \setminus Polygon(L_{n-1})$.
    *   *Definition:* Jeder Bereich von $L_n$, der *nicht* von Material im Layer darunter gestützt wird. Befindet er sich auf $Z=0$ (oder Raft-Höhe), ist es **Bottom Surface**.
2.  **Top Surface (Oberste Schicht):**
    *   Menge $M = Polygon(L_n) \setminus Polygon(L_{n+1})$.
    *   *Definition:* Material in der aktuellen Schicht, über dem in der nächsten Schicht *nichts* mehr gedruckt wird.
3.  **Overhang (Überhang-Perimeter):**
    *   Randkurve von $Polygon(L_n)$, die außerhalb von $Polygon(L_{n-1})$ liegt.
    *   *Kinetische Bestätigung:* F-Wert sinkt drastisch, Lüfter-Wert (M106) steigt.
4.  **Support-Identifikation (Stützstruktur):**
    *   Geometrien, die in Schicht $L_n$ exakt unterhalb der überhängenden Bereiche $M_{overhang}$ von $L_{n+k}$ liegen, aber *niemals* Teil des Haupt-Bounding-Volumens des Modells sind.
5.  **Support Interface (Dichte Grenzschicht):**
    *   Betrachte $Z_n - Z_{n-1}$. Ist das Delta plötzlich größer als die normale Layerhöhe (z.B. 0.25mm statt 0.2mm)? Dies ist der Z-Abstand (Z-Gap) des Supports! Das Polygon in $L_{n-1}$ war **Support Interface**.

### Ansatz D: Multi-Pass-Analyse (Der Algorithmus fürs Reverse Engineering)
Um den G-Code per Skript oder logischer Deduktion fehlerfrei zu taggen, wendet man ein Ausschlussverfahren in mehreren "Pässen" (Durchläufen) an:

*   **Pass 1: Z-Extraktion & Segmentierung**
    *   Trenne den G-Code anhand von Z-Änderungen in Schichten auf.
    *   Trenne Extrusionen ($E > 0$) von Travels ($E \le 0$).
*   **Pass 2: Die Kinetische Klassifizierung (Parameter-Clustering)**
    *   Gruppiere alle Bewegungen nach ihrer Geschwindigkeit ($F$) und Linienbreite ($A$).
    *   *Ergebnis:* Du hast nun Gruppen wie "Cluster 1 (schnell, dünn)", "Cluster 2 (langsam, dick)".
*   **Pass 3: Die Geometrische Klassifizierung (2D)**
    *   Welche Pfade sind geschlossen (Loops)? $\rightarrow$ **Cluster: Perimeter**.
    *   Das äußerste Loop eines jeden Clusters $\rightarrow$ **Outer Wall**.
    *   Innere Loops $\rightarrow$ **Inner Walls**.
*   **Pass 4: Topologische Klassifizierung (3D)**
    *   Führe den Schichtvergleich (Ansatz C) durch.
    *   Ist das Raster-Muster von nichts überdeckt? $\rightarrow$ Tagge es als **Top Solid**.
    *   Ist das Raster-Muster frei schwebend? $\rightarrow$ Tagge es als **Bridge**.
*   **Pass 5: Verfeinerung & Reste (Pattern Recognition)**
    *   Analysiere die übrig gebliebenen Zick-Zack- oder Kurven-Muster im Modellkern.
    *   Trifft Kurve, ändert Phase in Z? $\rightarrow$ **Gyroid Infill**.
    *   Kreuzt sich im 90° Winkel? $\rightarrow$ **Grid Infill**.
    *   Stotternde kleine Vektoren an engen Stellen? $\rightarrow$ **Gap Fill**.

---

## TEIL 3: VOLLSTÄNDIGE SYNTHESE (Feature-Identitäts-Matrix)

Hier ist die Matrix, wie man *jedes* Feature mathematisch zweifelsfrei im Code identifiziert, ohne Kommentare zu lesen:

| Feature (Slicer-übergreifend) | Bedingung 1 (Geometrie/Pfad) | Bedingung 2 (Topologie) | Bedingung 3 (Kinetik/Extrusion) |
| :--- | :--- | :--- | :--- |
| **Skirt** | Layer == 0, Geschlossener Loop | Liegt außerhalb BoundingBox des Modells | Berührt das Modell nicht |
| **Brim** | Layer == 0, Konzentrische Loops | - | Berührt Kontur des Modells (Abstand 0) |
| **Outer Wall / External Perimeter** | Geschlossener Loop | Äußerste Begrenzung des Modells | Niedrige Geschwindigkeit, optimale Kühlung |
| **Inner Wall / Perimeter** | Geschlossener Loop | Liegt exakt um $W$ nach innen versetzt zur Outer Wall | Höhere Geschwindigkeit als Outer Wall |
| **Overhang Perimeter** | Geschlossener Loop (Teilstück) | Liegt topologisch auf leerem Raum ($L_n \setminus L_{n-1}$) | Geschwindigkeit sinkt stark, Lüfter 100% |
| **Bottom Solid** | Dichtes Zick-Zack/Raster | Liegt topologisch auf leerem Raum oder Bett | Normale/langsame Geschwindigkeit |
| **Top Solid** | Dichtes Zick-Zack/Raster | Wird von $L_{n+1}$ nicht mehr überdeckt | Oft Monotonic-Pfad, langsame Geschwindigkeit |
| **Solid Infill** | Dichtes Zick-Zack/Raster | Liegt zwischen Sparse Infill und Top/Bottom Surface | Höhere Geschwindigkeit als Top/Bottom |
| **Sparse Infill** | Weitmaschiges Vektor-Muster | Liegt im Kern, von $L_{n+1}$ überdeckt | Höchste Geschwindigkeit im G-Code |
| **Bridge** | Gerade, parallele Linien | Beidseitig auf Perimeter verankert, sonst schwebend | $E/D$ Verhältnis = Runder Faden (Flow $\approx$ 1.0) |
| **Gap Fill** | Oszillierende, sehr kurze Vektoren | Liegt zwischen zwei Perimetern, wo Abstand $< 2W$ | Variabler Flow, stotternde Geschwindigkeit |
| **Ironing** | Dichtes Zick-Zack-Muster | Topologisch = Top Surface | $E \approx 0$ bis $10\%$, extrem geringer Flow |
| **Support (Normal)** | Eigene Bounding Box | Vertikal projiziert unter Überhängen | Dünne Linienbreite, schnelles Muster |
| **Support Interface** | Dichtes Raster-Muster | 1-3 Layer direkt unter Überhang ($L_n \setminus L_{n-1}$) | Abstand zu $L_{n+1}$ (Modell) ist oft Z-Gap > Layerhöhe |
| **Wipe / Prime Tower** | Isoliertes Quadrat/Kreis | Existiert über gesamte Z-Höhe konstant | Wird meist direkt nach Toolchange ($T0/T1$) angefahren |

---

### Fazit für das Post-Processing & Reverse Engineering
Mit diesem Regelwerk lässt sich ein Parser schreiben (z.B. in Python mit Bibliotheken wie `Shapely` für die 2D-Polygon-Boolean-Operationen), der einen völlig unbekannten, nackten G-Code einliest, die Geometrie voxelisiert oder vektorisiert und zu 100% akkurat wieder mit `;TYPE:`-Tags versieht. 

Genau so arbeiten moderne G-Code-Viewer (wie der von PrusaSlicer oder OctoPrint-Gcode-Viewer): Sie verlassen sich nicht nur auf Kommentare, sondern extrapolieren die Ansichten durch genau diese kinetischen und topologischen Analysen (Flow-Berechnung, Vektor-Geschlossenheit).


---

Das ist eine Aufgabe von der Komplexität einer Masterarbeit in angewandter Informatik / Computational Geometry. 

 Ich habe dieses Dokument exakt wie ein **wissenschaftliches Whitepaper / Skriptum** strukturiert. Du kannst diesen Text einfach kopieren, in Word, Google Docs oder ein Markdown-Tool (wie Obsidian/Typora) einfügen und als PDF exportieren. Die Formatierung (Überschriften, Listen, Formeln) wird perfekt übernommen.

Hier ist das vollständige Kompendium zum **Reverse Engineering von G-Code Geometrien**.

---

# WHITE PAPER: G-Code Reverse Engineering & Geometrie-Klassifizierung

## INHALTSVERZEICHNIS
1. Vollständige Nomenklatur der Features
2. Vollständige Nomenklatur der Muster (Infill, Support, Surfaces)
3. Reverse Engineering: Erkennungsmethodik (Der Algorithmus)
    * 3.1 Eindimensionale Heuristik (Logik & Parameter)
    * 3.2 2D-XY Pfadanalyse (Intra-Layer Geometrie)
    * 3.3 3D-Schichtvergleich (Inter-Layer Topologie)
    * 3.4 Komplexe Mathematik & Vektoranalyse
    * 3.5 Multi-Pass-Analyse & Ausschlussverfahren

---

## TEIL 1: Vollständige Nomenklatur der Features

Wenn wir reinen G-Code ohne Kommentare betrachten, ist ein "Feature" ein Vektorpfad mit spezifischen Extrusions-Eigenschaften. 

### 1.1 Wände (Perimeter / Shells)
*   **Outer Wall (Außenwand):** Der äußerste, geschlossene Polygon-Pfad eines Layers, der das Modell begrenzt.
*   **Inner Wall (Innenwand):** Geschlossene Polygon-Pfade, die exakte innere Offsets (Versätze) der Outer Wall im Abstand der Linienbreite $w$ sind.
*   **Overhang Perimeter:** Eine Wall, deren Pfad im Layer $L_n$ keine tragende Geometrie im Layer $L_{n-1}$ hat.
*   **Thin Wall / Single Extrusion:** Ein nicht geschlossener Pfad (Linie), der Wände modelliert, die dünner sind als $2w$.

### 1.2 Oberflächen (Surfaces / Skins)
*   **Bottom Surface:** Dicht aneinander liegende parallele Pfade ($>95\%$ Deckung), deren Projektion auf Layer $L_{n-1}$ in den leeren Raum fällt (oder auf Support).
*   **Top Surface:** Die absolut oberste dichte Schicht ($>95\%$ Deckung), über der in Layer $L_{n+1}$ leeres Raumvolumen folgt.
*   **Solid Infill (Top/Bottom):** Dichte Schichten, die sich als Puffer *zwischen* Top/Bottom Surfaces und dem Sparse Infill befinden.
*   **Ironing:** Eine Zick-Zack-Trajektorie über einer Top Surface, bei der $E \approx 0$ (Extrusion fast null), um Material zu schmelzen und zu glätten.

### 1.3 Füllungen (Infill & Internals)
*   **Sparse Infill:** Pfade im Inneren des Modells, die ein geometrisches Muster bilden und eine Dichte $d \ll 100\%$ aufweisen.
*   **Gap Fill:** Kurze, variable Einzelpfade oder enge Zick-Zack-Muster, die in Hohlräume geschrieben werden, die kleiner als $2w$ sind.
*   **Bridge Infill:** Geradlinige, dichte Pfade im Raum, die an exakt zwei Rändern (Ankerpunkten) von bestehender Geometrie im selben Layer getragen werden, aber unten leer sind.

### 1.4 Hilfsstrukturen (Externals)
*   **Skirt:** Geschlossene Loops auf Layer 0, die eine Convex Hull (konvexe Hülle) um das gesamte Druckbett-Layout bilden, ohne Kontakt zum Modell.
*   **Brim:** Offsets der untersten Modellschicht auf Layer 0, die direkten Kontakt zum Modell haben.
*   **Support (Normal):** Spärliche Muster, die außerhalb der Modellgrenzen in Z-Richtung gedruckt werden, um Überhänge zu stützen.
*   **Support (Tree/Organic):** Fraktale, röhrenförmige Pfade, die sich von Layer 0 nach oben verästeln.
*   **Support Interface:** Dichte Flächen ($d \approx 80\%$), die das obere Ende (Dach) oder untere Ende (Boden) des Supports bilden, meist 1-3 Layer dick.
*   **Prime Tower / Wipe Tower:** Isolierte, meist rechteckige Prismen, die parallel zum Modell gedruckt werden, charakterisiert durch hohe Geschwindigkeiten und Materialwechsel.
*   **Ooze Shield:** Ein dünner, geschlossener Perimeter, der in einem festen Abstand $D$ um das gesamte Modell auf jedem Layer gezogen wird.

---

## TEIL 2: Vollständige Nomenklatur der Muster

Um ein Muster im G-Code zu identifizieren, analysiert man die Winkel und Schnittpunkte der Liniensegmente über mehrere Schichten.

### 2.1 Sparse Infill Muster
1.  **Rectilinear:** Parallele Linien in $L_n$. In $L_{n+1}$ um 90° gedreht. Linien kreuzen sich *nicht* auf demselben Layer.
2.  **Grid:** Parallele Linien in 0° und 90° (oder 45°/-45°). Sie kreuzen sich *auf demselben Layer* (erzeugt Mikrokollisionen der Düse).
3.  **Triangles:** 3 Sets von parallelen Linien (0°, 60°, 120°), die sich im selben Layer kreuzen.
4.  **Cubic / Tri-Hexagon:** Fraktale Verschiebungen von Dreiecken über die Z-Achse, um 3D-Kuben zu bilden.
5.  **Gyroid:** Stetig differenzierbare, sinusförmige Kurven ohne harte Ecken. Im G-Code eine endlose Kette von G1-Befehlen mit winzigen $\Delta X, \Delta Y$ und stetig wechselnden Winkeln. Kreuzt sich *nie* im selben Layer.
6.  **Honeycomb:** Klassische Hexagone (Bienenwaben). Charakteristisch durch 120°-Winkelwechsel nach kurzen, geraden Segmenten.
7.  **Concentric:** Geschlossene Loops, die iterative Offsets der Außenwand ins Innere darstellen.
8.  **Lightning:** Fraktale Verästelungen, die im leeren Raum beginnen und sich nur nach oben hin zu Top-Surfaces ausbreiten, um diese punktuell zu stützen.
9.  **Hilbert Curve / Archimedean Chords / Octagram Spiral:** Mathematische Raumfüllungskurven. Ein einziger, nicht unterbrochener Pfad pro Layer.

### 2.2 Top/Bottom/Solid & Interface Muster
1.  **Monotonic / Monotonic Lines:** Wie Rectilinear, aber die Vektoren werden zwingend immer in eine Richtung abgefahren (z. B. immer von links nach rechts fortschreitend), um Lichtreflexionsfehler zu vermeiden.
2.  **Zig-Zag:** Ein einziger durchgehender Pfad, der am Rand des Polygons scharf umkehrt, anstatt abzusetzen.
3.  **Concentric:** Wie beim Infill, meist für runde Bauteile genutzt.

---

## TEIL 3: Reverse Engineering (Erkennungsmethodik)

Wie erkennt man diese Features in einer gigantischen Textdatei mit Millionen Koordinaten? Wir nutzen eine Analyse-Pipeline, die von simplen Heuristiken bis zu boolescher Algebra reicht.

### 3.1 Eindimensionale Heuristik (Logik, Listen & Parameter)
*Jeder G1-Befehl ($G1 X Y E F$) wird isoliert betrachtet.*

*   **Flow-Analyse ($E/D$ Ratio):** 
    Berechne die 2D-Distanz $D = \sqrt{\Delta X^2 + \Delta Y^2}$. Das Verhältnis $E_{ratio} = \frac{\Delta E}{D}$ definiert das Volumen. 
    *   $E_{ratio} \le 0 \rightarrow$ Travel (Leerfahrt).
    *   $E_{ratio} \approx \text{Standard} \rightarrow$ Normaler Druck.
    *   $E_{ratio} \gg \text{Standard} \rightarrow$ Bridge (Brücken extrudieren oft dicker, da sie nicht auf eine vorherige Schicht gepresst werden) oder Gap Fill.
    *   $E_{ratio} \approx 0.1 \times \text{Standard} \rightarrow$ Ironing.
*   **Speed-Analyse ($F$-Wert):** 
    Erstelle ein Histogramm aller F-Werte (Feedrate). Slicer clustern Geschwindigkeiten.
    *   Maximaler F-Wert: Travels / Infill.
    *   Minimaler F-Wert: Bottom Surface / Outer Walls.
    *   Mittelwert: Inner Walls / Solid Infill.

### 3.2 2D-XY Schicht- & Pfadanalyse (Intra-Layer)
*Wir betrachten alle Linien eines Layers $L_n$ als Graphen auf einer 2D-Ebene.*

*   **Pfadschließung (Closed Loop Detection):**
    Wenn ein Pfad bei Koordinate $A$ startet und nach $k$ Vektoren wieder exakt bei $A$ ankommt (Startpunkt = Endpunkt), ist es eine **Loop**.
    *   *Erkenntnis:* Loops sind fast immer Wände (Perimeter), Skirts oder Support-Umrandungen.
*   **Bounding Box & Convex Hull (Konvexe Hülle):**
    Berechne die konvexe Hülle für alle Extrusionspunkte in $L_n$. 
    *   Pfade, die auf dieser Hülle liegen, sind zwingend **Outer Walls** (oder Support-Außenkanten).
*   **Polygon-Offset-Analyse (Ray-Casting):**
    Schieße einen virtuellen Strahl (Ray) vom Modellmittelpunkt nach außen. Zähle die Schnittpunkte mit geschlossenen Loops. 
    *   Der äußerste Schnittpunkt = Outer Wall. 
    *   Der nächste nach innen = Inner Wall 1. 
    *   Dieses Verfahren klassifiziert Shells mathematisch einwandfrei.

### 3.3 3D-Schichtvergleich (Inter-Layer Topologie / Boolesche Logik)
*Wir vergleichen Layer $L_n$ mit $L_{n-1}$ (darunter) und $L_{n+1}$ (darüber). Dies ist die mächtigste Methode.*

Wir wandeln Extrusionspfade durch Aufdickung (Minkowski-Summe mit einem Kreis des Radius $w/2$) in 2D-Flächen (Polygone $P$) um.

*   **Erkennung von Top Surfaces:**
    Fläche $\text{Top} = P_n \setminus P_{n+1}$.
    *Logik:* Was in Layer $n$ gedruckt wird, aber in Layer $n+1$ komplett leer ist (Luft), muss eine Top-Surface sein.
*   **Erkennung von Bottom Surfaces:**
    Fläche $\text{Bottom} = P_n \setminus P_{n-1}$.
    *Logik:* Gedrucktes Material in Layer $n$, das in Layer $n-1$ leeren Raum unter sich hat.
*   **Erkennung von Bridges (Brücken):**
    Ein Pfad in $P_n$ verläuft über eine Distanz $> x$ mm ohne Schnittmenge mit $P_{n-1}$. Wenn die Endpunkte des Pfades eine Schnittmenge mit $P_n$ (Anker) haben, ist es zwingend eine Brücke.
*   **Erkennung von Support:**
    Support ist Geometrie in $L_n$, deren Boolesche Schnittmenge mit dem tatsächlichen 3D-Modell (oder den dichten Bereichen von Top/Bottom) gleich null ist, sich aber vertikal nach oben fortsetzt, bis sie auf ein Bottom-Surface trifft.

### 3.4 Komplexe Mathematik & Vektoranalyse
*Mustererkennung im Infill durch Vektor-Skalarprodukte und Krümmung (Curvature).*

Gegeben seien aufeinanderfolgende Vektoren $\vec{v_1}, \vec{v_2}, \vec{v_3}$.
*   **Winkelberechnung (Dot Product):** $\cos(\theta) = \frac{\vec{v_1} \cdot \vec{v_2}}{|\vec{v_1}||\vec{v_2}|}$
    *   Wenn $\theta \approx 90^\circ$ regelmäßig auftritt $\rightarrow$ **Grid / Rectilinear / Zig-Zag**.
    *   Wenn $\theta \approx 60^\circ \text{ und } 120^\circ$ $\rightarrow$ **Triangles / Honeycomb**.
*   **Krümmung (Gyroid-Detection):**
    Ein Gyroid-Muster besteht aus Mikrosegmenten. Die Ableitung des Winkels $\frac{d\theta}{ds}$ (Krümmung über Distanz $s$) beschreibt eine stetige Sinuswelle. Ein Gyroid lässt sich durch Fourier-Transformation der Winkeländerungen eindeutig von geraden Linien unterscheiden.
*   **Gap Fill Detection (Varianzanalyse):**
    Gap Fill zeichnet sich durch extreme hochfrequente Änderungen der Richtung (Zick-Zack auf kleinstem Raum) aus. Die Varianz der Vektorlängen $|\vec{v}|$ ist extrem hoch, während die Durchschnittslänge extrem niedrig ist.

### 3.5 Multi-Pass-Analyse & Ausschlussverfahren (Der Algorithmus)
Um einen G-Code "blind" vollständig zu klassifizieren, nutzt ein Parser mehrere Durchläufe (Passes):

**Pass 1: Z-Parsing & Bounding Box**
*   Lese alle `Z`-Koordinaten, bilde Schichten ($L_0, L_1, ... L_k$).
*   Berechne für das gesamte Volumen $X_{min}, X_{max}, Y_{min}, Y_{max}$.

**Pass 2: Base Elimination (Die offensichtlichen Dinge entfernen)**
1.  Filtere alle Travels ($E \le 0$).
2.  Auf Layer 0: Finde den Ring, der alle anderen Koordinaten umschließt und Abstand $>0$ hat $\rightarrow$ als **Skirt** taggen und aus dem Array entfernen.
3.  Suche isolierte Strukturen (X/Y Bounds winzig im Vergleich zum Bauraum), die über alle Schichten perfekt senkrecht in Z wachsen $\rightarrow$ **Prime Tower**, entfernen.

**Pass 3: Feature-Klassifizierung pro Schicht ($L_n$)**
1.  Wandle alle restlichen G1-Befehle in Flächen (Polygone) um.
2.  Finde die äußere Kontur (Union aller Flächen) $\rightarrow$ Der Rand dieser Kontur ist die **Outer Wall**.
3.  Führe ein inneres Offset der Outer Wall um $-w$ aus $\rightarrow$ Was damit überlappt, ist **Inner Wall**.
4.  Führe Pass 3 für Layer $n-1$ und $n+1$ aus.
5.  Führe die Boolesche Subtraktion $L_n \setminus L_{n+1}$ durch $\rightarrow$ Ergebnis = **Top Surfaces**.
6.  Führe $L_n \setminus L_{n-1}$ durch $\rightarrow$ Ergebnis = **Bottom Surfaces / Bridges**.
7.  Was jetzt noch in $L_n$ übrig bleibt, liegt *im Inneren* und ist *kein* Top/Bottom.
    *   Prüfe die Flächendichte (Area Coverage).
    *   Dichte $> 80\% \rightarrow$ **Solid Infill**.
    *   Dichte $< 50\% \rightarrow$ **Sparse Infill**.
    *   Pfad liegt komplett außerhalb der Modell-Outer-Wall $\rightarrow$ **Support**.
8.  Prüfe die Infill-Vektoren mit der Mathematik aus 3.4, um das spezifische Muster (Gyroid, Grid etc.) zu benennen.

---

### ZUSAMMENFASSUNG FÜR DIE ENTWICKLUNG

Wenn du einen G-Code-Viewer oder Post-Prozessor schreibst, der Slicer-unabhängig (ohne Kommentare) funktioniert, implementierst du exakt das **Ausschlussverfahren (3.5)** gekoppelt mit der **3D-Topologie-Logik (3.3)**. 

Bibliotheken wie `Clipper2` (für C++/Python/C#) oder `Shapely` (Python) sind dafür zwingend erforderlich, um die G1-Linien in Polygone umzuwandeln und die Schnittmengen (Intersections) sowie Differenzen (Differences) zu berechnen. Erst die Mathematik der Booleschen Polygone ermöglicht eine zu 100 % eindeutige Zuweisung von Wänden, Infill und Surfaces, völlig unabhängig davon, ob der G-Code aus Cura, Prusa, Simplify3D oder einem unbekannten Cloud-Slicer stammt.

---






---

# 1. Master-Union aller Feature-Typen

## A. Objekt-Wände / Shells / Perimeter

| Feature | Alias / Slicer-Namen |
|---|---|
| **Unknown / Undefined / None / Other / Noop** | `Unknown`, `Undefined`, `None`, `Others`, `Other`, `Noop` |
| **Outer Wall / Außenwand** | `External perimeter`, `ExternalPerimeter`, `Outer wall`, `WALL-OUTER`, `Outer Perimeter`, `Outer Shell`, `Perimeter Path` |
| **Inner Wall / Innenwand** | `Perimeter`, `Internal perimeter`, `Inner wall`, `WALL-INNER`, `Inner Perimeter`, `Inner Shell`, `Loop Path`, `Loop` |
| **Generic Wall / Shell** | `Wall`, `Shell`, `HShell`, `Skin`, `Surface`, je nach Slicer |
| **Overhang Wall / Überhang-Wand** | `Overhang perimeter`, `OverhangPerimeter`, `Overhang wall` |
| **Floating Vertical Shell** | `FloatingVerticalShell`, Bambu-spezifisch |
| **Hole Perimeter / Lochwand** | interne Loop-Rollen wie `Hole`, `PerimeterHole`; meist als Outer/Inner Wall sichtbar |
| **Second Perimeter / zweiter Wandloop** | `SecondPerimeter`, interne Loop-Rolle; meist als Inner Wall sichtbar |
| **Contour Internal Perimeter** | `ContourInternalPerimeter`, interne Slic3r/Prusa-artige Loop-Rolle |
| **Thin Wall / Dünnwand** | `Thin wall`, `Single extrusion wall`, `External Single Extrusion`, `Internal Single Extrusion` |
| **External Single Extrusion** | Simplify3D: sehr schmale äußere Geometrie, die mit einer einzelnen Linie statt normalen Perimetern gedruckt wird |
| **Internal Single Extrusion** | Simplify3D: schmale innere Bereiche, die als einzelne Linie gefüllt werden |
| **Gap Fill / Lückenfüllung** | `Gap fill`, `GapFill`, `Gap infill`, `Gaps in walls`, `Gaps in skin`, `Fill thin gaps` |
| **Crown Path** | KISSlicer-spezifisch; kleine obere/feine Deckflächen- bzw. Restpfade |
| **OuterHair / InnerHair** | CraftWare-Preview-Begriffe für sehr feine Außen-/Innenlinien |

PrusaSlicer/Slic3r definiert u. a. `Perimeter`, `ExternalPerimeter`, `OverhangPerimeter`, `GapFill` und interne Loop-Rollen; Orca/Bambu erweitert diese Liste um Rollen wie `BottomSurface`, `InternalBridgeInfill`, `Brim` und `SupportTransition`, während Cura eine eigene `WALL-OUTER`/`WALL-INNER`-Taxonomie nutzt. 

---

## B. Infill / Füllung / Oberflächen

| Feature | Alias / Slicer-Namen |
|---|---|
| **Sparse Infill / Teilfüllung** | `Internal infill`, `InternalInfill`, `Sparse infill`, `FILL`, `Infill`, `Sparse Infill Path` |
| **Stacked Sparse Infill** | KISSlicer: sparse infill, das nicht auf jedem Layer, sondern gestapelt gedruckt wird |
| **Solid Infill / Vollfüllung** | `Solid infill`, `SolidInfill`, `Internal solid infill`, `Solid Fill`, `Solid Layer`, `Solid Path` |
| **Top Solid Infill / Top Surface** | `Top solid infill`, `TopSolidInfill`, `Top surface`, `Top Solid Fill`, `Skin` |
| **Bottom Surface** | `BottomSurface`, `Bottom surface`, `Bottom solid infill`, bei Cura meist `SKIN` |
| **Skin** | Cura-Sammelbegriff für Top-/Bottom-/geschlossene Oberflächenbereiche |
| **Surface Mode** | Cura: nur Oberflächenlinien bei Surface Mode `Surface`/`Both`; nicht immer eigenes `;TYPE:` |
| **Infill Over Bridge** | Prusa-interne reichere Rolle; wird nicht immer als eigene G-Code-Rolle serialisiert |
| **Bridge Infill / Bridge** | `Bridge infill`, `BridgeInfill`, `Bridge`, `Bridge Path` |
| **Internal Bridge / Inner Bridge** | `InternalBridgeInfill`, `Internal Bridge`, `Inner Bridge`, interne Brücken über Infill/Hohlräumen |
| **Ironing** | `Ironing`; Glättpfad über Top-Surfaces |
| **Support Ironing** | Bambu-spezifische Support-Glättrolle |
| **Progressive / Adaptive Infill** | IceSL/andere: Infill mit variabler Dichte; meist trotzdem als Infill klassifiziert |

CuraEngine beschreibt Infill-Muster nicht nur für Sparse Infill, sondern auch für Support, Skin und Ironing; außerdem erzeugt Cura eigene Bereiche für Infill, Walls, Gaps, Skin, Skin-Gaps und Ironing. 

---

## C. Support / Stützmaterial

| Feature | Alias / Slicer-Namen |
|---|---|
| **Support Material / Support** | `Support material`, `SupportMaterial`, `Support`, `SUPPORT`, `Supports`, `Support Path` |
| **Support Base / Support Body** | normaler Support-Unterbau; oft nur `Support` |
| **Support Infill** | Support-Füllmuster; bei vielen Slicern nicht separat kommentiert |
| **Support Wall / Support Perimeter / Sheathed Support** | Support-Außenwand; KISSlicer: `Sheathed Support`; Cura: Support-Wall-Optionen, meist `SUPPORT` |
| **Support Interface** | `Support material interface`, `SupportMaterialInterface`, `Support interface`, `SUPPORT-INTERFACE`, `Dense Support`, `Support Interface Path` |
| **Support Roof** | obere Support-Interface-Zone direkt unter dem Modell |
| **Support Floor** | untere Support-Interface-Zone über Modellflächen, wenn Support von oben/innen relevant ist |
| **Dense Support** | Simplify3D/ideaMaker: dichter Support am Kontaktbereich |
| **Support Transition** | `SupportTransition`, `Support transition`; Orca/Bambu-Übergangsbereich zwischen Base-Support und Interface |
| **Tree Support / Organic Support** | geometrische Support-Variante; Rolle bleibt meist `Support`/`Support interface` |
| **Pillar Support / Support Pillar** | säulenartige Supports; KISSlicer `Pillar Path`; Simplify3D hat Support-Pillar-Auflösung |
| **Soft Support** | CraftWare: `SoftSupport` |
| **Support Brim / Support Base Brim** | Haftlinien um Support-Füße; oft als Brim oder Support klassifiziert |
| **Inner Support Base** | Cura-Einstellung für Support-Basis im ersten Layer |

Prusa/Slic3r unterscheidet Support und Support Interface, Orca/Bambu zusätzlich Support Transition; ideaMaker und Simplify3D zeigen Dense Support als eigene Kategorie. 

---

## D. Bettadhäsion / Basisstrukturen

| Feature | Alias / Slicer-Namen |
|---|---|
| **Skirt** | `Skirt`, `SKIRT`, `Skirt Path` |
| **Brim** | `Brim`, `BRIM`, `Skirt/Brim` |
| **Skirt/Brim kombiniert** | Prusa klassifiziert Brim historisch teilweise als Skirt; Simplify3D nutzt `Skirt/Brim` |
| **Mouse Ears / Brim Ears** | lokale Brim-Inseln an Ecken; meist kein eigener Kommentar |
| **Raft** | `Raft`, `RAFT`, `Raft Path` |
| **Raft Base** | Cura: Raft-Unterlage/Basis |
| **Raft Middle / Raft Interface** | Cura: mittlere Raft-Zone |
| **Raft Top / Raft Surface** | Cura: obere Raft-Schicht, auf der das Modell sitzt |
| **Prime Blob** | Cura/maschinenabhängig; Start-Priming-Blob |
| **Pre-extrusion / Purge line / Intro line** | Start-G-Code-Priming, meist Custom/Start-G-Code |

Cura beschreibt Skirt, Brim und Raft als Build-Plate-Adhesion-Typen; der Raft ist dort in Base/Middle/Top bzw. Base/Middle/Surface-Bereiche gegliedert. 

---

## E. Multi-Material / Purge / Wipe

| Feature | Alias / Slicer-Namen |
|---|---|
| **Wipe Tower** | `Wipe tower`, `WipeTower` |
| **Prime Tower** | `Prime tower`, `PRIME-TOWER` |
| **Prime Pillar** | Simplify3D/KISSlicer: `Prime Pillar Path`, `Prime Pillar` |
| **Tip Tower** | ideaMaker-ältere/abweichende Bezeichnung |
| **Wiping Tower** | FlashPrint: `Wiping Tower` |
| **Ooze Shield** | Simplify3D: `Ooze Shield`; Cura: Ooze shield feature |
| **Wipe Wall** | ideaMaker: `Wipe Wall`; FlashPrint: `Wall` als Dual-Extruder-Abstreifwand |
| **Draft Shield** | Cura: Draft shield; meist nicht eigener `;TYPE:` |
| **Flush / Flushing** | Bambu: `Flush`; Purge-/Flush-Material |
| **Flush into Infill** | Bambu/Orca-Funktion; landet geometrisch meist als Infill |
| **Flush into Support** | Bambu/Orca-Funktion; landet geometrisch meist als Support |
| **Flush into Object** | Bambu/Orca-Funktion; landet im gewählten Objektbereich |
| **Wipe Move** | Abstreifbewegung, häufig Bewegungsevent statt Extrusionsrolle |
| **Tool-change purge** | Werkzeugwechsel-Reinigung, oft im Toolchange-G-Code |

Bambu Studio führt im Quellcode zusätzlich zu üblichen Rollen u. a. `erFlush` und `erSupportIroning`, während Orca die Rollen für `change_extrusion_role_gcode` dokumentiert. 

---

## F. Bewegungen / Events / Marker

| Feature / Event | Alias / Slicer-Namen |
|---|---|
| **Travel / Move / Jump** | `Travel`, `Move`, `Jump`, `Non-print move`, `Destring/Wipe/Jump Path` |
| **Extrude generic** | generische Extrusion ohne genauere Rolle |
| **Retract** | `Retract`, `Retraction` |
| **Unretract / Deretract / Prime** | `Unretract`, `Unretraction`, `Deretract` |
| **Seam** | `Seam`, `Seams` |
| **Tool Change** | `Tool Change`, `ToolChanges` |
| **Color Change** | `Color Change`, `ColorChanges`, `COLOR_CHANGE` |
| **Pause Print** | `Pause Print`, `PausePrint`, `PAUSE_PRINT` |
| **Custom G-code** | `Custom`, `Custom G-code`, `CUSTOM_GCODE` |
| **Mixed / Multiple** | `Mixed`, `Multiple`, mehrere Rollen in einer Sammlung |
| **Layer Change** | `LAYER_CHANGE`, `LAYER:n`, `layer N`, kein Druckfeature, aber wichtiger Marker |
| **Before Layer Change** | `BEFORE_LAYER_CHANGE` |
| **After Layer Change** | `AFTER_LAYER_CHANGE` |
| **Object Start / Object End** | `EXCLUDE_OBJECT_START`, `EXCLUDE_OBJECT_END`, Objektlabeling |
| **Mesh Marker** | Cura: `;MESH:...` |

Orca/Prusa-G-Code-Viewer kennen neben Extrusionsrollen auch Move-/Event-Typen wie Retract, Unretract, Seam, Tool Change, Color Change, Pause Print, Travel und Wipe. 

---

# 2. Nach Slicer-Familie: konkrete Feature-Listen

## 2.1 Slic3r / PrusaSlicer / SuperSlicer / SliceBeam / AstroPrint-Slic3r

Typische G-Code-Rollen:

```text
None / Unknown
Perimeter
External perimeter
Overhang perimeter
Internal infill
Solid infill
Top solid infill
Ironing
Bridge infill
Gap fill
Skirt
Support material
Support material interface
Wipe tower
Custom
Mixed              // intern / Sammlung
Infill over bridge // intern reichere Rolle
```

PrusaSlicer serialisiert in der G-Code-Rollenliste u. a. `Perimeter`, `ExternalPerimeter`, `OverhangPerimeter`, `InternalInfill`, `SolidInfill`, `TopSolidInfill`, `Ironing`, `BridgeInfill`, `GapFill`, `Skirt`, `SupportMaterial`, `SupportMaterialInterface`, `WipeTower` und `Custom`; außerdem steht im Code, dass Brim aktuell als Skirt markiert werden kann. 

---

## 2.2 OrcaSlicer / Bambu Studio / ElegooSlicer / Creality Print modern / Anycubic Slicer Next / QIDI Studio / Snapmaker Orca / Sovol-Orca

Orca-kompatible Rollen:

```text
Undefined / Unknown
Perimeter                    = Inner wall
ExternalPerimeter             = Outer wall
OverhangPerimeter             = Overhang wall
InternalInfill                = Sparse infill
SolidInfill                   = Internal solid infill
TopSolidInfill                = Top surface
BottomSurface                 = Bottom surface
Ironing
BridgeInfill                  = Bridge, inkl. internal bridges
InternalBridgeInfill          = Internal bridge
GapFill                       = Gap infill
Skirt
Brim
SupportMaterial               = Support
SupportMaterialInterface      = Support interface
SupportTransition             = Support transition
WipeTower                     = Prime tower
Custom
Mixed / Multiple
```

Bambu-spezifische bzw. zusätzlich sichtbare/interne Rollen:

```text
FloatingVerticalShell
SupportIroning
Flush
PerimeterHole       // Loop-Flag
SecondPerimeter     // Loop-Flag
Hole                // Loop-Flag
Internal loop       // Loop-Flag
Skirt loop          // Loop-Flag
```

Orca dokumentiert die `extrusion_role`-Werte explizit für `change_extrusion_role_gcode`; Bambu Studio enthält zusätzlich Rollen wie `erFloatingVerticalShell`, `erSupportIroning` und `erFlush`. Elegoo gibt an, dass ElegooSlicer auf OrcaSlicer basiert; aktuelle Creality-Print-Generationen sind ebenfalls Orca/Slic3r-artig, während ältere Creality-Slicer Cura-basiert waren. 

---

## 2.3 Cura / CuraEngine / UltiMaker Cura / alte Creality-Cura / alte Elegoo-Cura / AstroPrint-Cura

Cura-`TYPE`-Kommentare bzw. vom Cura-G-Code-Reader erkannte Typen:

```text
WALL-INNER
WALL-OUTER
SKIN
SKIRT
SUPPORT
FILL
SUPPORT-INTERFACE
PRIME-TOWER
```

Cura-Features, die intern/preview-/settingsseitig existieren, aber nicht immer als eigener `;TYPE:`-Kommentar erscheinen:

```text
Prime blob
Skirt
Brim
Raft
Raft Base
Raft Middle / Raft Interface
Raft Top / Raft Surface
Ooze shield
Draft shield
Support
Support interface
Infill
Inner walls
Outer wall
Gaps in walls
Skin
Gaps in skin
Ironing
Surface Mode
Travel
Retraction
Combing travel
```

Der Cura-G-Code-Reader weist `WALL-INNER`, `WALL-OUTER`, `SKIN`, `SKIRT`, `SUPPORT`, `FILL`, `SUPPORT-INTERFACE` und `PRIME-TOWER` festen Layer-Polygon-Typen zu; CuraEngine beschreibt zusätzlich die feste Druckreihenfolge mit Prime Blob, Prime Tower, Skirt/Brim/Raft, Ooze Shield, Draft Shield, Support, Infill, Inner Walls, Outer Wall, Wall-Gaps, Skin, Skin-Gaps, Ironing und Surface Mode. 

---

## 2.4 Simplify3D

Simplify3D-Feature-Typen:

```text
Travel
Outer Perimeter
Inner Perimeter
External Single Extrusion
Internal Single Extrusion
Gap Fill
Solid Layer
Infill
Bridge
Support
Dense Support
Raft
Skirt/Brim
Prime Pillar
Ooze Shield
```

Simplify3D-Preview-Legenden führen diese Feature-Typen auf; die offiziellen Simplify3D-Artikel zu dünnen Wänden beschreiben zusätzlich external/internal single extrusions als Spezialfälle für sehr schmale Geometrie. 

---

## 2.5 FlashPrint / FlashForge

FlashPrint-Strukturtypen:

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

In FlashPrint-Preview-Legenden werden genau diese Strukturklassen gezeigt; FlashForge-Dokumentation beschreibt außerdem `Wall` als Hilfswand zum Entfernen/Abstreifen von austretendem Material bei Dual-Color-/Dual-Extrusion-Drucken. 

---

## 2.6 ideaMaker / Raise3D

ideaMaker-Strukturtypen:

```text
Infill
Solid Fill
Ironing
Bridge
Inner Shell
Outer Shell
Support
Dense Support
Skirt/Brim
Raft
Wipe Wall
Wipe Tower
Tip Tower        // ältere/abweichende Bezeichnung
Travel
Retraction
Seams
Inner Bridge     // neuere/aktuelle Funktionsbezeichnung im Kontext inner bridge structures
```

Raise3D-Dokumentation zeigt in der Strukturansicht u. a. Outer Shell, Inner Shell, Infill, Solid Fill, Brim und Travel; weitere ideaMaker-Preview-Legenden listen Infill, Solid Fill, Ironing, Bridge, Inner Shell, Outer Shell, Support, Dense Support, Skirt/Brim, Raft, Wipe Wall, Wipe Tower, Travel, Retraction und Seams. Neuere Release Notes erwähnen zusätzlich „inner Bridge structure“. 

---

## 2.7 Kiri:Moto

Kiri:Moto arbeitet weniger mit einem standardisierten `;TYPE:`-Dialekt, sondern mit Feature-Regionen und Makros. Bekannte/übliche FDM-Feature-Gruppen:

```text
Feature region
Shell / wall
Outer shell / outer wall
Inner shell / inner wall
Thin wall
Infill
Sparse infill
Solid fill / solid areas
Top/bottom solid areas
Bridge / interior bridge
Base
Skirt
Brim
Raft
Support
Support columns
Travel
Retraction
Tool / nozzle transitions
Custom feature transition macros
```

Kiri:Moto dokumentiert Makros für Feature-Übergänge; dort existiert `{feature}` als „feature region of the print“, z. B. Brims und Infill. Die Release Notes nennen außerdem FDM-G-Code-Feature-Makros für Transitionen. 

---

## 2.8 KISSlicer

KISSlicer-Path-Type-Liste:

```text
Pillar Path
Raft Path
Support Interface Path
Support (may Stack) Path
Perimeter Path
Loop Path
Solid Path
Sparse Infill Path
Stacked Sparse Infill Path
Destring/Wipe/Jump Path
Crown Path
Prime Pillar Path
Skirt Path
```

Zusätzlich als definierte Begriffe:

```text
Skin
Infill
Raft
Brim
Skirt
Loops
Perimeter
Support
Prime pillar
Wipe pillar / wall
```

KISSlicer-Handbücher zeigen diese Path-Color-Key-Liste und definieren Perimeter, Skin, Loops, Infill, Raft, Brim und Skirt. 

---

## 2.9 CraftWare / CraftBot

CraftWare-Preview-Featuretypen:

```text
Unknown
Perimeter
Loop
HShell
Infill
Support
SoftSupport
Skirt
Raft
OuterHair
InnerHair
Travel
```

Eine CraftWare/CraftBot-Preview-Legende listet diese Kategorien explizit. `HShell` ist dabei sinngemäß eine horizontale Shell-/Top-Bottom-Flächenklasse; `OuterHair` und `InnerHair` sind CraftWare-eigene Begriffe für sehr feine Außen-/Innenpfade. 

---

## 2.10 MatterSlice / MatterControl

MatterSlice-/MatterControl-Featuregruppen:

```text
Outside Perimeter
Inside Perimeter
Perimeters
Top Solid Infill
Infill
Solid infill / top-bottom layers
Thin gaps / Fill Thin Gaps
Bridge / Bridges
Support Material
Support Interface
Support Perimeter
Raft
Skirt
Brim
Travel
Retraction
Wipe before/after retract
Tool change
Layer change
Custom G-code
```

MatterControl-Dokumentation und Setting-Listen führen u. a. Outside Perimeter, Inside Perimeters, Top Solid Infill, Bridges, Support Material, Support Interface, Support-Perimeter-Optionen, Fill Thin Gaps, Raft, Skirt/Brim und Retract/Wipe-Funktionen auf. 

---

## 2.11 IceSL

IceSL ist weniger ein klassischer Kommentar-Dialekt-Slicer, aber die relevanten Feature-/Pfadklassen sind:

```text
Perimeter
Infill
Progressive / variable infill
Support
Bridge support / disposable bridge structure
Raft
Brim
Shield brim
Skirt / priming outline, falls im Profil genutzt
Multi-material paths
Non-planar surface paths
```

IceSL dokumentiert u. a. Perimeter-Priorität, Raft-Layer-Höhe, Shield-Brim-Konturen, Support-Print-Speed und Infill-Type; die Feature-Seite nennt zudem nichtplanare Oberflächen, progressive Infill-Muster und eine Support-Technik mit disposable bridge structure. 

---

## 2.12 AstroPrint

AstroPrint ist keine eigene Feature-Taxonomie, sondern nutzt je nach Auswahl **CuraEngine** oder **Slic3r/Prusa Edition**:

```text
Wenn CuraEngine gewählt:
WALL-INNER
WALL-OUTER
SKIN
SKIRT
SUPPORT
FILL
SUPPORT-INTERFACE
PRIME-TOWER
plus Cura-spezifische Features

Wenn Slic3r/Prusa Edition gewählt:
Perimeter
External perimeter
Internal infill
Solid infill
Top solid infill
Bridge infill
Gap fill
Support material
Support material interface
Wipe tower
Custom
```

AstroPrint dokumentiert, dass sein Cloud Slicer mit Cura oder Slic3r/Prusa Edition slicen kann; der Feature-Dialekt folgt entsprechend dem gewählten Backend. 

---

# 3. Kompakt: wirklich alle eindeutigen Namen als Roh-Liste

```text
Unknown
Undefined
None
Other
Others
Noop
Mixed
Multiple
Custom
Custom G-code

Perimeter
Internal perimeter
Inner wall
Inner Wall
Inner Shell
Loop
Loop Path
ContourInternalPerimeter
SecondPerimeter
PerimeterHole
Hole
External perimeter
ExternalPerimeter
Outer wall
Outer Wall
Outer Shell
Outer Perimeter
Perimeter Path
WALL-INNER
WALL-OUTER
Wall
Shell
HShell
Overhang perimeter
OverhangPerimeter
Overhang wall
FloatingVerticalShell
Thin wall
External Single Extrusion
Internal Single Extrusion
Gap fill
GapFill
Gap infill
Gaps in walls
Gaps in skin
Fill Thin Gaps
Crown Path
OuterHair
InnerHair

Internal infill
InternalInfill
Sparse infill
Sparse Infill Path
Stacked Sparse Infill Path
FILL
Infill
Solid infill
SolidInfill
Internal solid infill
Solid Fill
Solid Layer
Solid Path
Top solid infill
TopSolidInfill
Top surface
Top Solid Fill
Bottom surface
BottomSurface
Skin
SKIN
Surface Mode
InfillOverBridge
Bridge infill
BridgeInfill
Bridge
InternalBridgeInfill
Internal Bridge
Inner Bridge
Ironing
SupportIroning
Progressive Infill
Adaptive Infill

Support material
SupportMaterial
Support
SUPPORT
Supports
Support Path
Support base
Support body
Support infill
Support wall
Support perimeter
Sheathed Support
Support material interface
SupportMaterialInterface
Support interface
SUPPORT-INTERFACE
Support Interface Path
Dense Support
Support Roof
Support Floor
SupportTransition
Support transition
Tree Support
Organic Support
Pillar Support
Pill