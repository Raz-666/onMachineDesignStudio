# Fortschreibung: Ursache der Rose-Zustandsinvalidierung

Belegte Folge: Zeile 95 `START_PRINT` invalidiert den unbekannten Zustand.
Zeilen 96–98 deklarieren G90/G21/M83 neu; aber Zeile 100
`SET_PRESSURE_ADVANCE` invalidiert ihn im strikten Modus erneut. Danach
scheitern G92/Bewegungen an unbekannten Einheiten/Modi; Objektmarkierungen
lösen weitere Invalidierungen aus. Keine pauschale „kaputte Geometrie“.

`collect_contours(..., klipper_passive=True)` / CLI `--klipper-passive` reicht
nun die **bereits vorhandene optionale Shadow-Fähigkeit** durch. Standard
bleibt strikt. Alle Optionen stehen im Ergebnis. Keine neuen Anfangswerte,
keine Makroausführung, kein Ignorieren beliebiger Befehle. START_PRINT bleibt
unbekannt; Erholung nur durch spätere explizite Dateideklarationen/Bewegungen.
Der Repo-Override `macros/10_live_tuning.cfg::SET_PRESSURE_ADVANCE` wurde gelesen;
das optionale Modell betrifft logische Koordinaten, nicht reale PA-/Druckeffekte.
Der gesamte optionale Klipper-Befehlssatz ist keine Hardware-/Makrofreigabe.

Rose-Gegenprobe: vollständig gescannt, unbekannte Records **148529 → 1**
(Zeile 95), unbekannte Bewegungskoordinaten **4**, nichtplanare Extrusion
**45285**, offene Ketten **41445**, Konturpunktbudget **2**. Weiterhin
**0 exakte geschlossene Konturen**. Nächster Engpass: offene/nonplanare Pfade,
Nahtlücken und konservative Konturvalidierung, nicht fehlende Mode-Defaults.

Zusätzlicher Fix im neuen Kontursammler: Feed-only und unveränderte Position
bei ΔE=0 erhalten Ketten. Retract, Travel und reine positive E-Moves brechen
sie weiterhin. Dadurch keine falsche Unterbrechung durch F-Zeilen.

**12/12 Integrationstests**, einschließlich Rose mit Quell-Hashvergleich;
**16/16 Kontur**, **5/5 Mesh**, **3/3 E-State**, **10/10 RE** erneut bestanden.
Tests erzwingen: Klipper-Modell opt-in, fehlende G21-/unbekannte Makrosemantik
wird nicht geraten; keine zusätzlichen Ausgabedateien. Aktiver Export bleibt
unverändert, keine STL-/Slicer-/Hardware-Abnahme.

---

# Fortschreibung: Anschluss an normalisierte G-Code-Bewegungen

`tools/gcode_contours.py` liest Quelldateien ausschließlich über den vorhandenen
`r2_shadow.Shadow`-Parser. Keine zweite Interpretation von G90/G91/M82/M83.
Exakt geschlossene, planare Extrusionsketten werden mit Punkten, Z, Tool,
Quellenzeilen und kommandiertem Filament als Kandidaten ausgegeben.
Koordinaten bleiben im Shadow-Befehlsbezug, nicht behauptet als Maschinengeometrie.

Keine Endpunktrundung, kein Zusammenlegen naher Z-Ebenen. Travels, unbekannte
Zustände und nichtplanare Extrusion trennen Ketten. Validierung verwirft
selbstschneidende geschlossene Konturen. Endliche Budgets für Zeilenlänge,
Zeilenanzahl, Konturpunkte und Schleifenzahl; Abbruch wird ausgewiesen.
Erste acht unbekannte Record-Gründe bleiben im Bericht zur Diagnose.
`export_ready` bleibt bewusst false: Wandbreite, Feature-/Objekt-/Lochzuordnung
sind nicht belegt. Skirt/Support-Loops dürfen nicht als Modell ausgegeben werden.

Tests: **7/7 Integration**, **16/16 Kontur**, **5/5 Mesh**, **3/3 E-State**;
zusätzlich bestehende RE-Suite **10/10**. Quelle bleibt byte-identisch, keine
zusätzlichen Dateien. M82/M83/G91, Ebenen .20/.23, unbekannte Makros,
Seamlücke, Travel-Unterbrechung, Spiralpfad, Budgets und Bowtie geprüft.
Ein anfänglich fehlerhaftes Testfixture enthielt G0 mit positiver E-Extrusion;
das ist kein Travel. Korrigiert auf G0 ohne E, keine Parser-Sonderbehandlung.

Feldgegenprobe `testfixtures/rose_215c_pla.gcode.gz` (temporär entpackt): Scan
vollständig, **0 Konturen / 148529 unbekannte Records** im bewusst strikten
Parsermodus. Kein Erfolg behauptet. Nächster Engpass ist damit belegte
Modal-/Makrosemantik vor Konturrekonstruktion, nicht blindes STL-Schreiben.
Aktiver Exporter und Druckpfad unverändert. Keine neue Hardware-Abnahme.

---

# Fortschreibung: Schichtverbindung für skalierte/verschobene Konturen

Neue API `loft_mesh(boundary, sections, holes=...)` in `tools/contour_mesh.py`.
Jede Sektion gibt `(Z, positiver Maßstab, X-Versatz, Y-Versatz)` vor. Außenring
und alle Löcher erhalten dieselbe Transformation. Zwischen den Höhen wird
linear verbunden, nur ganz unten/oben gibt es Deckflächen. Das unterstützt
Verjüngung, Verbreiterung und Neigung bei konstanter Polygon-/Lochtopologie.
Es ist **keine automatische Zuordnung beliebiger G-Code-Schichtkonturen**.

Mathematische Grenze: positive gleichförmige Skalierung plus Translation
erhält die validierte Polygonhierarchie auch zwischen zwei Sektionen.
Rotation, getrennte Lochbewegung, Öffnen/Schließen von Löchern, Split/Merge
und allgemeine Querschnittswechsel werden von dieser API nicht angeboten.
Skalierung erfolgt um XY=(0,0), danach Translation; nicht still um den Schwerpunkt.

Ressourcen: 2–64 Sektionen, bestehendes Konturbudget 256, STL-Budget maximal
32768 Dreiecke. Z muss endlich und streng aufsteigend sein. Koordinatengrenzen
werden nach Transformation geprüft; beim Float32-Schreiben kollabierende
Dreiecke führen zum Abbruch. Keine Verbindung zum Watcher/aktiven Exporter.

Nachweis: **16/16 Konturtests, 5/5 Mesh-Tests, 3/3 aktive E-State-Tests**.
Volumenorakel je Höhenintervall: A·h·(s0²+s0·s1+s1²)/3, dabei ist A die
Ausgangsfläche abzüglich Löcher. Geprüft: Verjüngung, Verbreiterung, variable
Höhen, seitliche Verschiebungen, konkaves L, Lochführung, beide Umlaufrichtungen,
Euler-Topologie und Abwesenheit interner Deckel. Negativtests: fehlende,
doppelte/absteigende Höhen, Null-/Negativmaßstab, NaN, Budgetüberschreitung,
Koordinatenausbruch und Float32-Höhenkollaps.

Offen bleibt die Rekonstruktion echter physischer Konturen aus dem normalisierten
Bewegungsmodell sowie allgemeines Matching; kein vollständiger STL-/Release-
Nachweis, kein unabhängiger Slicer-Reimport. Frühere Zwischenstände folgen.

---

# Fortschreibung: explizite Durchgangslöcher

`prism_mesh(..., holes=[...])` unterstützt jetzt mehrere disjunkte,
explizit als Löcher klassifizierte Ringe. Außen-/Lochkonturen dürfen konkav
sein und beide Umlaufrichtungen verwenden. Nach Validierung werden Löcher
über sichtbare, flächenlose Brücken an den Deckelring angeschlossen;
Ear-Clipping trianguliert die Materialfläche. Die Brücken erzeugen keine
zusätzlichen Seitenwände. Lochwände zeigen mit ihren Normalen in den Hohlraum.
Zusätzlich wird die Deckelfläche gegen Außenfläche minus Lochflächen geprüft.

Ablehnung statt Reparatur: berührende, kreuzende, überlappende, außerhalb
liegende oder ineinander verschachtelte Löcher. Verschachtelte Inseln brauchen
eine explizite Objekt-/Polygonhierarchie. Gemeinsames Budget von 256 Punkten
inklusive Brücken; keine Echtzeit-/Watcher-Integration.

Nachweise: **11/11 Konturtests**, **5/5 Mesh-Tests**, **3/3 aktive E-State-Tests**.
Quadrat 10×10 mit Loch 4×4, Höhe 2: 168 mm³; konkave Außenkontur mit zwei
Löchern: 152 mm³; konkaves Loch: 186 mm³. Drei Löcher zusätzlich in neun
Größen-/Positionskombinationen. Prüfer findet keine offenen/nichtmannigfaltigen
Kanten, doppelten/degenerierten Flächen oder falschen Normalen. Euler-Test
(V−E+F = 2−2h) und Deckel-Punktproben prüfen, dass Durchgangslöcher offen bleiben.

Weiterhin experimenteller Geometriebaustein, kein G-Code-Rekonstruktor:
wechselnde Schichtkonturen, Topologiewechsel, Linienbreitenkorrektur und
G-Code-Anbindung fehlen. Keine unabhängige Slicer-Abnahme oder Hardwaretests.
Die nachfolgenden Abschnitte dokumentieren frühere Zwischenstände.

---

# Fortschreibung: erster Kontur-Oberflächenbaustein

`tools/contour_mesh.py` rekonstruiert die Oberfläche eines geraden Prismas aus
**einer bereits klassifizierten physischen Außenkontur** und zwei Z-Grenzen.
Dies ist ausdrücklich noch kein G-Code-Exporter: Düsenmittellinien dürfen
nicht ohne Linienbreiten-/Lochklassifikation als Eingabe verwendet werden.

- Einfache konvexe und konkave Polygone, beide Umlaufrichtungen, expliziter
  oder impliziter Ringschluss. Ear-Clipping statt Dreiecksfächer (letzterer
  würde bei konkaven Formen Material in Aussparungen erzeugen).
- Nur Seitenfläche, Boden und Deckel; keine doppelten Zwischenlayer-Deckel.
- Selbstkreuzungen/-berührungen, wiederholte Punkte, kollineare Ecken,
  nichtendliche Werte und ungültige Höhen werden abgelehnt, nicht repariert.
- Konservatives Rechenbudget: höchstens 256 Konturpunkte. Kein Pi-/Watcher-
  Anschluss. STL-Float32-Konvertierung erfolgt vor Normalenberechnung;
  dadurch zusammenfallende Dreiecke führen zum Fehler statt kaputter Ausgabe.

Nachweise: `tools/test_contour_mesh.py` **6/6**; bestehende Mesh-Tests **5/5**
und aktive Extrusionstests **3/3** erneut bestanden. Analytische Sollwerte:
Quadergrundfläche 200 mm² × Höhe 10 mm = 2000 mm³; konkave L-Grundfläche
5 mm² × Höhe 2 mm = 10 mm³. Innenaussparung zusätzlich durch Punktproben
auf jedem Deckeldreieck geprüft. Rechteck 20 × .5 × .4 mm: 12 Dreiecke,
4 mm³, keine doppelten Flächen oder nichtmannigfaltigen Kanten. Dieser letzte
Fall zeigt einen fehlerfreien **neuen Oberflächenbaustein**, repariert aber
noch nicht den alten Exportpfad (dessen Reproduzierer bleibt bestehen).

Nächste Integration braucht Lochkonturen, Konturzuordnung zwischen Layern,
Linienbreitenkorrektur und Anbindung an das normalisierte Bewegungsmodell.
Nicht unterstützt: Löcher, wechselnde Querschnitte, beliebige Toolpaths.
Keine Selbstschnittprüfung allgemeiner 3D-Meshes, kein unabhängiger Slicer-
Reimport, keine Export-/Hardware-Abnahme. Produktpfad unverändert.

---

# Fortschreibung: neue Offline-Mesh-Prüfung

Der frühere Bericht darunter ist eine vorläufige Bestandsaufnahme, keine
vollständige Abnahme. Insbesondere war „inhaltlich identisch“ für die beiden
Briefings nicht belegt. Die Behauptung zur Entfernung der kürzesten Segmente
ist irreführend: der betrachtete Writer faltet Layer-Bänder (jede k-te Höhe).

Jetzt implementiert: `tools/stl_audit.py`, ausschließlich offline und nicht im
Watcher/Druckpfad. Prüft Binärlänge, endliche Werte, Bounding Box, orientiertes
Volumen, Normalen, degenerierte/doppelte Flächen, offene/nichtmannigfaltige
Kanten, Kantenorientierung und über exakt gleiche Vertices verbundene Komponenten.
Kein automatisches Welding, keine Reparatur, keine Selbstschnittprüfung.
Speicher wächst mit der Mesh-Größe; NICHT im Echtzeitpfad verwenden. Das greift
auch den Ressourcen-Hinweis aus `Potential performance& compatibility issues.md`
auf. Die RE-Recherche (Ansätze C/D: Konturen und Schichtvergleich) passt zur
notwendigen späteren Rekonstruktion; reine Box-Geometrie erfüllt §24.3 nicht.

Tests: `tools/test_stl_mesh.py` (5 Tests) und aktiver
`tools/test_stl_extrusion_state.py` (3 Tests) bestanden.
- Einzelbahn: 12 Dreiecke, Volumen 2 mm³, vier Achsrichtungen und Translation;
  keine offenen Kanten, Duplikate, Normalen- oder Orientierungsfehler.
- Zwei identische Bahnen auf Z=.2/.4: 24 Dreiecke, Volumensumme 4 mm³,
  **2 doppelte Flächen und 5 nichtmannigfaltige Kanten**. Ursache: jede Bahn
  erhält eigene obere/untere Deckflächen; die gemeinsame Grenzfläche bleibt
  doppelt im Export. Als Fehler-Reproduzierer gesichert, NICHT als bestandenes
  Export-Abnahmekriterium. Test muss bei Reparatur auf Null-Fehler-Soll wechseln.
- Beschädigte Dateilänge, NaN, umgedrehte, doppelte und fehlende Dreiecke
  werden vom unabhängigen Prüfer erkannt.

Weiter offen: Kontur-/Hohlraumrekonstruktion, Überschneidungen, reale historische
Fehlexporte, vollständige §24-Testmatrix, unabhängige Programme und Slicer-Reimport.
Keine Produktänderung, kein vollständiger Release, keine Hardware-Abnahme.

---

# STL-Export — Bestandsaufnahme (2026-11-18, Nutzer-Auftrag)

**Auftrag (Nutzer, 18.11.2026):** Der STL-Export ist „schon ein großer Auftrag" —
zuerst das ganze Projekt und alle verfügbaren Informationen prüfen, dann selbst
im Repo nach den relevanten Stellen suchen; der nächste Agent soll
**nicht blind suchen müssen**. Dieser Bericht ist Schritt 1 (nur Lesen, keine
Codeänderung). Zusammengestellt nach dem vollständigen Durchlauf durch
`tools/r2_postproc.py` (main `e2b42bc`) und den zugehörigen Tests.

Belegtes Briefing-Soll: `R2-D2 – Gesamtbriefing für die Coding-GPT.md`, §24
„ERGÄNZUNG: STL-/OBJ-EXPORT AUS G-CODE" (lokal in `analyse/uebergabe-quellen/`,
SHA256 `926438eb…`); inhaltlich identisch mit
`R2_Vollstaendiges_Startbriefing_Coding-KI_finalizedByGemini.txt` §5.21.

---

## 1. Verifizierter Ist-Stand (Code, nicht Doku)

Ort: `tools/r2_postproc.py`, `_stl_export` ab **Zeile 18719** (Kommentarblock
„R214 (.136m, field wish): G-code -> STL, OBJECT ONLY" ab Zeile 18687).
Versionen: R214 (Grundgerüst) → R216 (Z-Cluster-Layer, Decimation, Viewer-Budget)
→ R238 (`.stl.gcode` gilt als Datendatei, Zeile 18572 `_is_data_file`) →
R253 (TYPE=MARKED-Dateien ohne Oberflächen-Tags, Header-Guard).

### 1.1 Ablauf (3 Durchgänge + Ausgabe)

| Pass | Zeile | Funktion |
|---|---|---|
| 0a `_kinds214` | ~18733 | Liest nur `;TYPE:`- und `APPLY_TYPE`-Zeilen, zählt welche Feature-Arten **tatsächlich extrudieren** (finite positive-E XY-Moves), sammelt Z-Werte; ignoriert leere Header-Stubs. |
| 1 `runs` | ~18848 | Vollständiger Durchlauf: G90/G91, M82/M83, G92 (X/Y/Z/E), Arc-Endpoints (G2/G3 → gerade Segmente), Z über `_zq216` gequantelt (Spiral-Vasen mergen). Zusammenhängende kollineare Segmente werden gemergt (Cross-Threshold 0.12, Breiten-Delta ≤ 0.12 mm). Z-Hop-/G92-E-Semantik: exkludierte Bewegungen aktualisieren den E-Stand weiterhin korrekt. |
| 2 `z_h` | ~19001 | Layer-Höhen aus **Z-Clustern** (gequantelten Werte = echte Layer-Bänder; erster Layer sitzt auf dem Bett). |
| 2.5 `_dec216` | ~19017 | Ist `_nseg216 > 45000`, werden die **kürzesten** Segmente (Mikrotextur) weg-dezimiert; Schritt `ceil(segs/45000)`; gemeldet als `decimated/decim_step` im Info-Dict. |
| 3 `_tri` | ~19060 | Binary-STL schreiben: 80-Byte-Klinke + uint32-Anzahl (hinterher gepatcht via Seek), atomare `mkstemp` + `os.replace`. Jeder Ribbon ist ein geschlossener Kasten (12 facets); degenerierte Facets werden still übersprungen; nicht-finite Punkte still übersprungen. |
| Header-Guard | ~19155 | Nach dem Schreiben: Datei muss mit `R2 object-only STL` beginnen (Feldfall .142h: Watcher hatte einem 44-MB-Export Text vor den Binary-Header gehängt — kein Viewer konnte die Datei öffnen). |

### 1.2 Was ausgeschlossen wird (Zeilen 18694–18716)

`SUPPORT, SKIRT, BRIM, PRIME-TOWER, CUSTOM, IRONING, TRAVEL` sowie seit R216
zusätzlich `INFILL-SPARSE, INFILL-SOLID, WALL-INNER, GAPS` — der Export ist
bewusst nur das **äußere Häutchen** (Wall-Outer, Top, Bottom, Bridges,
Overhangs). Gegenbeispiel (`_STL_SURFACE214`): fehlt in einer Datei **jede**
Oberflächen-Art (z. B. Kiri:Moto `; shell`, untagged Vase), **relaxiert** der
Exporter die inneren Wände wieder herein und **sagt das** (`relaxed: True`,
Meldung) statt zu scheitern — vorher starb der Export mit
`'no object extrusion found'`. Untagged Dateien (`untyped: True`) können gar
nicht filtern; alles Extrudierende landet im Mesh.

### 1.3 Qualitätssicherungen im Code

- `_STL_MAX_BOXES214 = 150_000` (harter Abbruch, deklariert),
  `_STL_TARGET_BOXES216 = 45_000` (Viewer-Budget, gemeldet).
- Band-Faltung bei Decimation (`zb + (zt-zb)*dec`, jede k-te Band).
- Info-Dict: `boxes/tris/layers/runs/incl_mm/excl/capped/untyped/relaxed/decimated/decim_step/segments` — wird vom LCD (`System > Export STL`) ausgegeben.
- `tools/test_stl_extrusion_state.py`: M82/M83/G92-Parität der gefilterten
  E-Zustände + Vergleich gegen `backups/r2_postproc_R2-2026-11-13.1_V1.py`.
  Das Fixture-Set `testfixtures/rose_215c_pla.gcode.gz`, `bigrose_020mm.gcode.gz`,
  `stringart3d_generic.gcode.gz` liegt bereit (Golden Master).

## 2. Bekannte Feld- und Fehlerlage (Evidenz)

1. **Historischer Zustand (Briefing §24):** Exporte ließen sich in keinem
   getesteten Programm öffnen; ein späterer KI-Fix machte sie teilweise
   sichtbar, aber weiterhin formal/geometrisch fehlerhaft.
2. **Feldfall .142h (R253):** 44-MB-Export (`LampOpenE27.gcode`) — der
   Live-Watcher klassifizierte die `.stl.gcode` als Druckdatei und hängte
   Text davor; Datei für keinen Viewer ladbar. Behoben durch
   Data-File-Klassifizierung (R238) + Header-Guard (R253). **Damit ist der
   Übertragungs-/Korruptionsmodus adressiert — nicht die Mesh-Qualität.**
3. **R253 (.142i):** TYPE=MARKED-Dateien ohne `;TYPE:`-Kommentar starben mit
   `'no object extrusion found'` → relaxiertes Häutchen + `APPLY_TYPE`-Parsing
   ergänzt.
4. `git log`-Historie: R214 → R216 → R238 → R253 zeigen, dass der Exporter
   wiederholt gepatcht, aber **nie mit einem End-zu-End-Test** (öffnen in zwei
   unabhängigen Programmen, Reimport in Slicer, erneuter Slice) abgenommen
   wurde. Es existiert **kein** Fixture mit Ground-Truth-Modell (bbox/Volumen
   bekannt) und **kein** Facetten-Orientierungs-/Duplikat-/Manifold-Test.

## 3. Offene technische Risiken (aus dem Code, nicht spekulativ)

1. **Kein Welded Mesh.** Jeder Ribbon ist eine eigenständige geschlossene
   Box; benachbarte Segmente teilen keine Vertices → STL ist eine Suppe
   überlappender Boxen. Slicer unionen das meist, Briefing §24.6/24.7 fordert
   aber Watertight/Manifold, keine Doppelflächen, korrekte Orientierung,
   Volumen, Komponenten-Zählung — **das kann der Export heute nicht
   nachweisen, weil es gar keinen Prüfer dafür gibt.**
2. **Band-Decimation verändert Geometrie unsichtbar.** Weg-dezimierte
   Mikrosegmente (Texturen) werden „benachbarte Band übernommen" — korrekt nur
   im Mittel; für glatte Flächen (Top/Bottom) kann es Löcher in der Außenwand
   öffnen. Bisher nur durch ein Viewer-Budget motiviert, nicht messbar
   verifiziert.
3. **Spiral-/Vase-Z-Quantisierung** merge-Bänder, die bei völlig anderen
   Höhen liegen (`_zq216` bündele nahe Werte); die erste Schicht sitzt auf
   dem Bett (`max(0.0, zv - lh)`) — für Vase-Mode mit 0-Anlauf versehentlich
   falsch interpretierbar (erste „Schicht" 0,05 mm).
4. **Arc als Gerade** (G2/G3 → Endpoints): Konturfehler bis ~ sagitta
   (bei r2-Fixtures selten, aber **nicht markiert**, obwohl Briefing §5.6/§24.5
   Approximation ausdrücklich auszeichnen will).
5. **Breite aus E abgeleitet** (`w = de·A_fil/(seg·h)`, geclamped 0,30–1,5 mm):
   über-/unterextrudierte Dateien bekommen falsche Ribbon-Breiten; angrenzende
   Wände können auseinanderklaffen (kein Overlap) → **Löcher im Häutchen**.
6. **Stil-Heuristik beim Merging** (`cross < 0.12`, `abs(Δw) < 0.12`) erzeugt
   keine Fehlermeldung — Merge-Fehler landen still im Mesh.
7. **Overlapping Facets:** Box-Deckel benachbarter Layer koplanar (zb == zt
   vorheriger Layer) → Z-Fighting-Duplikatfacetten bei Viewern; Volumen via
   Divergenztheorem wäre aus heutigen Daten zwar summierbar, aber keine
   Prüfung rechnet das nach.
8. **Fehlende OBJ-Ausgabe** vollständig offen (Briefing erlaubt OBJ als
   Zusatzkandidat, kein Ziel zwingend).
9. **Variable Layerhöhen** über Z-Quantisierung approx.; echte Slicer mit
   adaptiven Schichthöhen → Bänder werden gerundet, Maßhaltigkeit weicht ab.
10. **Kein Reimport-/Slicer-Test.** „In zwei unabhängigen Programmen öffnen"
    ist mit den heutigen Fixtures offline zumindest als Parser-Orakel testbar
    (eigener Mini-STL-Parser: Facettenanzahl, bbox, Volumen über
    Divergenztheorem, Dedup-Zählung, Winding-Konsistenz) — fehlt heute.

## 4. Testlücken (konkret)

- kein synthetisches Orakel-Modell mit bekannter Soll-bbox/Soll-Volumen;
- kein Winding/Normalen-Konsistenz-Test (heute werden Normalen zwar aus den
  Kanten gebildet, aber nichts prüft deren konsistente Außenorientierung);
- kein Dedup-Test (gleiche Facet über zwei Pfade);
- kein Decimal-/Fold-Pfad-Test (dezimierte Dateien öffnen korrekt?);
- kein RETAG-Pfad-Test („erst File check, dann exportieren");
- keine Messung, ob Retracts/Z-Hops versehentlich extrudieren (de>0-Filter
  hilft, aber nicht belegt).

## 5. Vorgeschlagener, phasenweiser Plan (Umsetzung noch NICHT freigegeben)

**Phase 2 — Orakel-Kit (offline, ohne Drucker, mit Nutzer-Go oder nach
Freigabe):** `analyse/stl_oracle.py` — reiner STL-Binärparser: Facettezahl,
bbox, Volumen (Divergenztheorem), Winding-Dominanz (outward), degenerate &
duplicate Facette-Zähler, Komponenten-Zähler (Union-Find über geteilte
Vertices mit ε). Fixtures: synthetischer Quader 20×20×10 (Flow exakt), Vase
(Spiral), Zwei-Objekt by-layer, ungetaggt, TYPE=MARKED-relaxed.

**Phase 3 — Root Cause:** Orakel auf `rose_215c_pla.gcode.gz` + synthetische
Fälle laufen lassen; Abweichungen tabellieren (bbox-Fehler, Volumen-Fehler,
Schlupfloch-Quellen); daraus minimale, testbelegte Fixes (Winding-Fix,
Dedup, optional Vertex-Welding hinter Flag, Cap-Orientierung, Markierung von
Bogen-Approximationen im Info-Dict, ehrlich dezimierte Bänder protokollieren).
Kein Redesign, kein Ribbon→Surface-Konverter vor Phase 4.

**Phase 4 — Feldabnahme (nur mit Nutzer + Drucker/PC):** reale Datei aus dem
Bestand (z. B. LampOpenE27, Rose-Dose) → Export → öffnen in 2 Programmen
(z. B. Blender + Microsoft 3D Viewer / Slicer) → Reimport + Reslice →
Screenshots → `docs/STL-EXPORT-ABNAHME.md`. Erst danach Freigabe „STL export
funktioniert“.

## 6. Was der nächste Agent NICHT tun soll

- Den Exporter nicht refactoren/ersetzen vor Phase 3-Evidenz (Originalschutz,
  MASTER-TODO/D6, Briefing §5.1).
- Keine 100-%-/„funktioniert“-Aussagen ohne Phase-2/4-Nachweise.
- Keine Behauptung, `my_printer.cfg` sei relevant für den STL-Pfad — sie ist
  relevant für E1/E4/Sondenthemen, nicht für Mesh.
- slicer-families.md / Potential-performance-compatibility sind
  **Recherche-Ideen**, keine Verifikation — abgeglichene Aussagen immer gegen
  Code/Fixtures belegen.

## 7. Referenzen

- Code: `tools/r2_postproc.py` Z. 18572, 18687–19200 (Exporter), 18848 (Pass 1), 19001/19017 (Z-Cluster, Decimation), 19060–19175 (Writer, Header-Guard).
- Tests: `tools/test_stl_extrusion_state.py` (M82/M83/G92-Parität).
- Fixtures: `testfixtures/rose_215c_pla.gcode.gz`, `bigrose_020mm.gcode.gz`, `stringart3d_generic.gcode.gz`; Backup `backups/r2_postproc_R2-2026-11-13.1_V1.py`.
- Briefing: Gesamtbriefing §24 (lokal), `UEBERGABE.md` Feldnotiz .142h/.142i; `docs/TOOLS_INVENTORY.md` (STL-Export-Eintrag); `docs/RELEASE_R2-2026-11-18.2_REPORT.md`.
