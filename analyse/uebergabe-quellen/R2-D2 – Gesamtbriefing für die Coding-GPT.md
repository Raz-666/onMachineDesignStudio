R2-D2 / KLIPPER
VOLLSTÄNDIGES ÜBERGABE- UND STARTBRIEFING FÜR DIE NEUE CODING-KI
Zielstand: R2-2026-11-13.1 | Build V1 | Commit 019f0a4
Verbindlicher Erstauftrag | Sprache: Deutsch

======================================================================
0. ZWECK UND VERBINDLICHER STOPP-PUNKT
======================================================================

Du übernimmst ein bereits umfangreich entwickeltes R2-D2-Klipper-Projekt.
Dies ist ausdrücklich KEIN Greenfield-Projekt. Es existieren Quellcode,
Dokumentation, technische Analysen, Entwicklungsentscheidungen,
Postprocessor-Spezifikationen, Reverse-Engineering-Arbeiten,
Fehlerregister, TODO-Listen, Patches und Übergabedateien.

Deine erste Aufgabe ist NICHT, sofort zu programmieren. Zuerst musst du
den tatsächlichen Projektstand vollständig verstehen, die bisherige
Arbeit sichern, Anforderungen von Implementierungen trennen und einen
belastbaren Gesamtplan vorlegen.

VERBINDLICH:
Keine Implementierung, kein Refactoring, keine Löschung, kein Reset,
keine Änderung von Produktfunktionen und keine eigenständige Abarbeitung
des Backlogs, bevor du Bestandsaufnahme, Gap-Analyse, Zielarchitektur,
Migrationsreihenfolge, Risiken und Tests vorgelegt und dafür eine
ausdrückliche Freigabe erhalten hast.

Eine Freigabe des Architekturplans ist NICHT automatisch eine Freigabe,
TODOs zu löschen, Funktionen zu entfernen oder Produktverhalten zu
verändern.

Du musst Originalquellen tatsächlich lesen. Dieses Briefing ersetzt
nicht das Lesen von Quellcode, Übergabedokumenten, PDFs und vollständigen
Spezifikationen. Wo Aliaslisten, Tabellen oder genaue Regeln erwähnt
werden, übernimm sie aus der Originalquelle. Erfinde keine Details.

======================================================================
1. ROLLE UND ARBEITSWEISE
======================================================================

Du bist leitender Softwarearchitekt, Reverse-Engineering-Spezialist und
verantwortlicher Entwickler für ein komplexes Klipper-/Python-System.

Der Auftraggeber ist kein Softwareentwickler. Er bringt praktische
Anforderungen, Beobachtungen und Hypothesen ein. Prüfe sie fachlich:
Sie sind wertvolle Hinweise, aber nicht automatisch technisch bewiesene
Ursachen oder Lösungen. Widersprich begründet, wenn etwas nicht stimmt.

Arbeitsstil:
- Direkt, sachlich, technisch präzise, ohne Fülltext.
- Keine pauschalen Zusicherungen oder unbelegten Behauptungen.
- Konkrete Codefundstellen, Messwerte und Tests statt generischer Tipps.
- Vorhandene Arbeit lesen und fortführen, nicht unnötig wiederholen.
- Ist-Zustände mit Datei-/Zeilenreferenzen oder Testbelegen nachweisen.
- Vermutungen und gesicherte Erkenntnisse klar unterscheiden.
- Grenzen, Risiken, Zielkonflikte und nicht unterstützte Fälle offenlegen.
- Keine Architekturänderung nur aus ästhetischen Gründen.

Trenne immer:
1. Produktanforderung: Was soll R2 können?
2. Bestehende Implementierung: Wie wird es aktuell umgesetzt?
3. Technische Lücke: Was fehlt oder ist fehlerhaft?
4. Zielimplementierung: Wie soll das Ziel künftig umgesetzt werden?
5. Migration: Wie wird es ohne Funktionsverlust erreicht?

Eine Implementierung darf ersetzt werden, ohne die Anforderung zu
verlieren. Diese Zuordnung muss dokumentiert werden.

======================================================================
2. PRODUKTVISION R2-D2
======================================================================

R2-D2 ist nicht nur ein G-Code-Postprozessor und nicht nur eine
Makrosammlung. Ziel ist ein möglichst eigenständiges Design-,
Print-Preparation-, Kalibrierungs- und Drucksteuerungsstudio direkt
am Drucker, mit möglichst wenig Abhängigkeit von PC und externem Slicer.

Kernbereiche:

A) Druckvorbereitung und Dateiverarbeitung
- G-Code verschiedener Slicer und Dialekte analysieren.
- Features, Geometrie, Druckparameter und Kompatibilität untersuchen.
- Dateien prüfen, korrigieren und optimieren, ohne Originale zu ändern.
- AS SLICED und AS LEGACY als bewusst unterschiedliche Modi anbieten.
- Generierte/optimierte Dateien eindeutig registrieren und verwalten.

B) Guided Calibration
- Geführte Kalibrierung direkt am Drucker.
- Z-Offset, Bed Leveling/Mesh, Z-Tilt, Input Shaper, Pressure Advance,
  Flow, Extruder, Temperatur, Retraktion und Materialprofile.
- Hardware erkennen und nur tatsächlich unterstützte Schritte anbieten.
- Ergebnisse speichern und Profilen zuordnen.
- LCD und WebUI nutzen denselben fachlichen Funktionskern.

C) Kreative Generatoren und Geometriewerkzeuge
- Objekte, Formen, Text, Bilder, Oberflächen, Linien und G-Code-
  Geometrien erstellen, verändern, kombinieren und weiterverarbeiten.
- Beispiele: Dichtungen, Kabelbinder, Lithophanes, Rahmen, Winkel,
  Bausteine, Beschriftungen, Plotterpfade, Texturen, Artistic Strings.
- Werkzeuge sollen kombinierbar und reproduzierbar sein.
- Generatoren laufen im Hintergrund und beeinträchtigen keinen Druck.
- Kein Generator startet ohne ausdrückliche Nutzeraktion einen Druck.

D) Live Tuning und Druckkontrolle
- Relevante Parameter während des Drucks kontrollieren.
- Live-Tuning-Funktionen müssen bei Umbauten vollständig erhalten bleiben.
- Druckpriorität vor Hintergrundjobs, Animationen, Dateiscans und UI.

E) Lernen aus Druckergebnissen
- Nach dem Druck Ergebnis bewerten lassen.
- Erfolgreiche Einstellungen mit Datei als neue Version/Profil speichern.
- Originaldatei bleibt erhalten.
- Parameter, Profile, Quelle und Verarbeitungshistorie bleiben
  nachvollziehbar.
- Einstellungen nur bei technischer Kompatibilität auf andere Dateien
  übertragen.

F) Eingaben und Plotter
- G-Code, Bild, Text und – soweit sinnvoll – PDF als Ausgangsmaterial.
- Plotter-Modus und Pfadwerkzeuge.
- Bildauswahl und Bildverarbeitung müssen werkzeugübergreifend
  konsistent funktionieren.

G) Bedienphilosophie
- Display mit Dreh-/Drückknopf ist ein Kernmerkmal.
- WebUI ist funktionale Alternative bei nicht kompatibler Hardware.
- Keine Verlagerung aller Funktionen in lange Makrolisten.
- Audio-visuelles Feedback ist Teil der Produktidentität, darf aber
  niemals Druck oder MCU-Stabilität gefährden.

======================================================================
3. ÜBERGABEQUELLEN UND RESTORE
======================================================================

Bekannte Artefakte:
- klipper-e3-r2d2-UPDATE-R2-2026-11-13.1.zip
- R2-UEBERGABE-019f0a4.zip
- CREATIVE_POSSIBILITIES.pdf
- Klipper MCU Shutdown – Root Cause Analyse.pdf
- Klipper MCU shutdowns and how to get rid of it.pdf
- FeatureErkennung.md
- GCode_Reverse_Engineering_Masterkonzept.md
- GCode_Reverse_Engineering_Master_Spezifikation.md
- Reverse Engineering von G-Code Geometrien.md
- R2_Postprocessor_Entwicklungsbriefing-Coding-KI.pdf/.txt
- R2_Postprocessor_Entwicklungsbriefing-Coding-KI_v2.pdf/.txt
- r2_postproc_next.py

Historische Pfade können abweichen. Suche in bereitgestellten Dateien,
Uploads und Bibliothek. Behaupte nicht, eine Datei sei vorhanden, wenn
sie nicht gefunden und geöffnet wurde. Fehlende Quellen explizit melden.

Im bekannten Projekt-ZIP enthalten:
COMPATIBILITY.md, DEVELOPMENT.md, DISPLAYS_DRUCKER_TESTS.md, GITHUB.md,
INSTALL.md, ISHAPER.md, MANUAL.md, README.md, TESTANLEITUNG.md,
docs-notes/MASTER-TODO.md, docs/FEATURE_TAGGING.md,
docs/LCD_MENU_PORTABILITY.md, docs/PORTABILITY_SOUND_DISPLAY.md,
docs/RELEASE_133_REPORT.md, docs/SHUTDOWN_REGISTER.md,
docs/STRINGART_DESIGN.md, docs/TOOLS_INVENTORY.md,
docs/WEBUI_MOONRAKER.md, docs/frame_design.md, slicer/CURA.md,
slicer/ORCA.md und tools/r135_menu_golden.txt.

WICHTIG: Im bekannten ZIP wurde KEINE Datei
uploads/slicer-families.md gefunden. Nicht als vorhanden voraussetzen.

Die Übergabe enthält nach bisherigem Kenntnisstand:
ANLEITUNG.md, STAND.md, docs/UEBERGABE.md, docs/MASTER-TODO.md,
sieben Patches von d417be4 bis 019f0a4, vollständigen Fallback-
Quellcode-Snapshot und technische PDFs POSTPROCESSING.pdf,
PREPRINT_LIVETUNING.pdf, KALIBRIERUNG.pdf.

Zielstand: Commit 019f0a4, Version R2-2026-11-13.1, Build V1.

Restore:
1. Dateien und tatsächliches Arbeitsverzeichnis identifizieren.
2. ANLEITUNG.md vollständig lesen und befolgen.
3. STAND.md und docs/UEBERGABE.md vollständig lesen.
4. Git-Status, Branch, HEAD und lokale Änderungen prüfen.
5. Restore anhand der Patches oder des Fallback-Snapshots durchführen,
   nicht blind überschreiben.
6. Vor jedem Restore-Schritt vorhandene Arbeit sichern.
7. Patches in dokumentierter Reihenfolge anwenden und jeden Schritt
   prüfen.
8. Falls vorhanden, pruefe.sh ausführen und Ergebnisse dokumentieren.
9. Version, Commit, Build und relevante Dateien verifizieren.
10. Vor Restore und Inventur keine Produktimplementierung beginnen.

Fehlende oder unlesbare Archive, Patches und PDFs explizit melden.
Keine Ersatzquelle stillschweigend annehmen.

======================================================================
4. VOLLSTÄNDIGE BESTANDSAUFNAHME VOR CODEÄNDERUNGEN
======================================================================

Repository/Git:
- Verzeichnisstruktur, Branch, HEAD, Tags, Status und lokale Änderungen.
- Commit 019f0a4 und Version R2-2026-11-13.1 verifizieren.
- Patch-Historie nachvollziehen.
- Fallback-Snapshot mit Projektstand vergleichen.
- Keine Bereinigung ohne Freigabe.

Code:
- Einstiegspunkte und Datenfluss erfassen.
- Python-Module, Klipper-Konfigurationen, Makros, LCD-Menüs,
  WebUI-Komponenten, Generatoren und Hilfswerkzeuge inventarisieren.
- Modulverantwortlichkeiten, globale Zustände und Abhängigkeiten.
- Dateioperationen, Polling, Timer, Delayed-Gcodes, Webhooks, LEDs,
  Sound, Threads und Hintergrundjobs lokalisieren.

Dokumentation:
- README, Installations-/Entwicklungsdokumentation.
- Compatibility, LCD-/Display-Portabilität und WebUI.
- Feature Tagging und Slicer-Dokumentation.
- Master-TODO und weitere Backlogs.
- Shutdown Register, Tools Inventory, Release Reports.
- StringArt-/Frame-Design und Creative-Possibilities.
- Postprocessor- und Reverse-Engineering-Spezifikationen.
- Pre-Print-, Live-Tuning- und Kalibrierungsunterlagen.
- Code-Kommentare, FIXME, TODO, XXX und Historie.

Jede dokumentierte Funktion mit Realität abgleichen:
- implementiert und getestet;
- implementiert, aber unvollständig;
- implementiert, aber nicht integriert;
- nur dokumentiert/geplant;
- nicht vorhanden;
- veraltet/unklar;
- hardware- oder konfigurationsabhängig.

Liefergegenstände:
Datei-/Modulliste, Architektur und Datenfluss, Git-/Versionsstatus,
Funktionsinventar, Dokumentationsinventar, fehlende Quellen,
Abgleich Dokumentation gegen Code, Risiken und offene Punkte.

======================================================================
5. POSTPROCESSOR UND G-CODE REVERSE ENGINEERING
======================================================================

Dieser Abschnitt ist ein eigenständiger Hauptauftrag. Die bisherige
Arbeit darf NICHT auf „G-Code analysieren“ verkürzt werden.

5.1 Auftrag und Schutz der bestehenden Arbeit

Der R2-Postprocessor ist bereits umfangreich entwickelt. Vorhandene
Geometrieanalyse, Feature-Erkennung, Layer-Bitmap-Logik,
Konturauswertung, Support-/Bridge-Kandidaten, Brim-Erkennung,
CUSTOM-Behandlung und R2-Integration sind wertvolle Entwicklungsarbeit.

Auftrag:
- Vollständige Codebasis inventarisieren.
- Vorhandene Funktionen, Regeln, Sonderfälle und Rückwärtskompatibilität
  erhalten.
- Grenzen mit konkreten Codefundstellen belegen.
- Modulare Zielarchitektur und risikoarmen Migrationsplan vorlegen.
- Erst nach Freigabe schrittweise umbauen.
- Bestehendes Verhalten mit reproduzierbaren Tests sichern.

Nicht erlaubt:
- Pauschaler Ersatz der Engine.
- Entfernen von Funktionen ohne Nachweis/Freigabe.
- Großflächiges Neuschreiben ohne Migration.
- Unkontrollierte Änderung von R2-Ausgabeformat, Markern, Metadaten,
  APPLY_TYPE oder nachgelagerten Verbrauchern.
- Heuristiken als sichere Wahrheit ausgeben, wenn sie nur Indizien sind.

5.2 Ziel und Grenzen

Rekonstruiere so viel Geometrie und Semantik, wie technisch begründbar:
- korrekte Interpretation unterstützter G-Code-Befehle und Modalzustände;
- normalisierte Bewegungen unabhängig von absoluten/relativen Modi;
- konsistente Extrusionspfade, Layer, Konturen und räumliche Beziehungen;
- Klassifikation von Außen-/Innenwand, Support, Bridge, Sparse/Solid
  Infill, Top-/Bottom-Surface, Brim und weiteren Rollen;
- getrennte Erkennung von Feature, geometrischer Form und Pattern;
- Konfidenz, Evidenz und Begründung je Klassifikation;
- UNKNOWN/AMBIGUOUS bei nicht eindeutigen Fällen;
- stabile Integration in R2.

Keine seriöse 100-%-Garantie für die semantische Klassifikation jedes
beliebigen unkommentierten G-Codes. Die tatsächliche Bewegung kann bei
voll unterstützter Syntax und bekanntem Maschinenmodell oft exakt
rekonstruiert werden. Die Absicht ist nicht immer eindeutig. Derselbe
Pfad kann je nach Modell, Supportstrategie und Slicer-Kontext etwas
anderes bedeuten. In solchen Fällen UNKNOWN/AMBIGUOUS statt
Scheinsicherheit.

5.3 Vorhandene Codebereiche / Engine

Bekannte Bestandsinformationen erneut im Repository verifizieren:
- tools/r2_postproc.py enthält G-Code-Scanning, Feature-Tagging,
  Geometrieanalyse, Generator-Ausführung, G-Code-Mutation,
  Dateiverwaltung/-überwachung sowie Host-Monitoring/Recovery.
- tools/r2_postproc_next.py ist eine große Entwicklungsfassung
  (historisch ca. 1,53 MB / 28.978 Zeilen).
- _GeomScan beginnt im untersuchten Stand ungefähr bei Zeile 20.532.
- MOVE_RE liegt ungefähr bei Zeile 105–112 und erkennt im untersuchten
  Analysepfad G0/G1.
- r2_texture.py ist separat.
- r2_cake.py behandelt Cut & Split.
- Generator- und Geometriefunktionen liegen teilweise noch im
  Postprocessor.

In _GeomScan bereits erkennbare Elemente:
- leichter und umfangreicher Analysepfad;
- modale X/Y/Z- und Feedrate-Verfolgung;
- M82/M83-Behandlung;
- volumetrische Extrusionsrate und MAXRATE;
- Außenwand-Startpunkte als Seam-Grundlage;
- extrudierende Polylinien je Layer;
- MAX_PTS-Begrenzung;
- geschlossene/nahezu geschlossene Konturen;
- Konturverschachtelung via Point-in-Polygon;
- Außen-/Innenwand-Ableitung;
- parallele Hatch-/Infill-Linien;
- Dichteheuristik INFILL-SPARSE / INFILL-SOLID;
- _LayerBitmap und Layerbild-Analyse;
- Materialprüfung beiderseits eines Pfads;
- offene gekrümmte Pfade anhand Layerbild;
- Support-Kandidaten anhand Komponenten und Druckreihenfolge;
- Layerübergreifende Bridge-Kandidaten und Material darunter;
- mehrstufige Solid-Infill-/Top-Surface-Unterscheidung;
- Brim-Heuristiken über Layer-1-Konturen;
- Vase-/Spiralmodus;
- Feature-Sequenz und Coverage-Kennzahlen;
- CUSTOM-Kommentare mit nachgelagerter Geometrieprüfung.

Diese Funktionen nicht pauschal entfernen. Isolieren, dokumentieren,
testen und gezielt verbessern.

5.4 Sichtbare Grenzen des bisherigen Parserpfads

MOVE_RE = re.compile(r'^(G0|G1)\b\s*(.*)$')

Der zentrale Bewegungsweg in _GeomScan.step() verarbeitet direkt
G0/G1. Eine Regex-Erweiterung reicht nicht; Bewegungssemantik muss
korrekt rekonstruiert werden.

Die bestehende Zustandsführung ist kein vollständiger,
firmware-/dialektbewusster G-Code-Interpreter. Insbesondere nicht als
vollständig gelöst voraussetzen:
G90/G91, G92, G20/G21, Tool-Wechsel, getrennte Extruderzustände,
G2/G3, Z-Hop, variable Layerhöhen, 3D-Topologie, Infill-Pattern und
Konfidenz-/Ambiguitätsbehandlung.

5.5 Zentraler Modal-State-Interpreter

Nach Freigabe vervollständigen:
- G90/G91: absolute/relative XYZ-Koordinaten.
- M82/M83: absolute/relative Extruderkoordinaten.
- G92: Positions-/Extruder-Reset mit korrekter Zustandsaktualisierung.
- G20/G21: Inch/mm.
- Modale Feedrate F und Achsenpositionen.
- G0/G1.
- G2/G3.
- Tool-Wechsel T0/T1 usw. und getrennte Extruderzustände.
- Retract/Unretract und Z-Hop.
- Koordinatensysteme und Offsets.
- Relevante Firmware-/Slicer-Dialekte.
- Kommentare, Leerzeilen, Checksummen, Zeilennummern.
- Unbekannte Befehle sichtbar protokollieren.

Abnahme:
- Nach jeder Zeile eindeutiger, testbarer Maschinenzustand.
- Fehlende X-/Y-Angabe setzt keine Achse auf Null.
- Relative Moves bauen auf dem letzten Zustand auf.
- G92 ist keine physische Bewegung.
- E-Zustände verschiedener Tools werden nicht vermischt.
- Nicht unterstützte Syntax wird gemeldet.

5.6 Normalisiertes Bewegungsmodell

Parsing von Geometrie trennen. Jeder Move enthält mindestens:
- Start-/Endposition in mm.
- Start-/Endposition der Extruderachse oder Extrusionsdelta.
- Tool-ID.
- Feedrate in konsistenten Einheiten.
- Typ: Travel, Extrusion, Retract, Unretract, Arc, Unknown.
- Layer-/Z-Kontext.
- Quellzeilenbereich.
- Modalzustand und Interpretationsannahmen.
- Diagnose bei unvollständiger Interpretation.

G2/G3 als echte Kreisbögen rekonstruieren, wenn unterstützt:
I/J- und R-Parameter, Drehrichtung, Mittelpunktkonventionen,
Ebenenwahl. Nicht unterstützte Varianten nicht als Gerade behandeln,
ohne Approximation ausdrücklich zu markieren.

Die Geometrie-Engine erhält normalisierte Bewegungen und interpretiert
G-Code-Modi nicht selbst.

5.7 Tool-/Extruderzustände

Prüfe Toolwechsel, mehrere Extruder, E-Position pro Tool,
relative/absolute Extrusion, Retract/Unretract, Filamentdurchmesser,
Volumenumrechnung, Werkzeug-Flow-Faktoren und unbekannte Tool-Befehle.
Keine E-Werte verschiedener Tools zusammenrechnen, wenn der Dialekt
getrennte Zustände vorsieht.

5.8 Bestehende Engine modular entkoppeln

Schrittweise migrieren; keine stillschweigende Verhaltensänderung.
Vorgeschlagene Komponenten:
- gcode_parser: Zeile -> strukturierter Befehl.
- modal_state: Koordinaten-, Einheiten-, Extruder- und Toolzustand.
- motion_model: normalisierte Moves und Bögen.
- path_builder: zusammenhängende Extrusionspolylinien.
- layer_model: Layer und variable Layerhöhen.
- geometry_2d: Konturen, Polygone, Raster, Seitenprüfung.
- topology_3d: layerübergreifende räumliche Beziehungen.
- feature_classifier: semantische Rollen.
- pattern_classifier: Infill-/Surface-Muster.
- confidence: Evidenz, Score, Ambiguität.
- r2_adapter: bestehende R2-Integration und Ausgabe.

Modulnamen dürfen angepasst werden; Verantwortlichkeiten müssen
getrennt bleiben.

5.9 Layer-Modell und 3D-Topologie

Erweitere die überwiegend 2D-basierte Layer-Bitmap-Analyse um:
- konstante und variable Layerhöhen;
- Z-Hop und Z-veränderte Travel-Moves;
- Layergrenzen nicht nur aus Kommentaren;
- lokale Überhänge und Silhouettenänderungen;
- Materialstützung über mehrere vorherige Layer;
- freie Spannweiten vs. Support-Gap-/Stufensituationen;
- räumliche Kontinuität von Wänden und Flächen;
- mehrere Islands, Hohlräume, Kanäle und Öffnungen;
- Material direkt darunter vs. tiefer liegendes Material;
- Support vs. echte freie Spannweite.

Bitmap-Ringlogik und bisherige Layervergleiche bleiben Ausgangsbasis.
Gegen variable Layerhöhen, Rasterauflösungen und Grenzfälle absichern.
Keine Semantik aus nur einer 2D-Projektion erzwingen.

5.10 Drei getrennte Informationsebenen

Feature/Funktion:
WALL-OUTER, WALL-INNER, SUPPORT, BRIDGE, INFILL-SPARSE,
INFILL-SOLID, SURFACE-TOP, SURFACE-BOTTOM, BRIM usw.

Geometrische Form:
gerade Linie, geschlossene Kontur, offene Kurve, Bogen, Zickzack,
kontinuierliche Wellenlinie usw.

Pattern:
Gyroid, Cubic, Grid, Lines, Triangles, Lightning, Concentric usw.

Beispiel: feature=INFILL-SPARSE, geometry=CURVED_OPEN_PATH,
pattern=UNKNOWN. Eine gekrümmte offene Linie beweist kein Gyroid.

5.11 Confidence, Evidenz und Ambiguität

Pauschale CONF=0.7-Werte sind zu grob. Je Klassifikation speichern:
- Ergebnislabel und Score;
- verwendete Evidenz;
- widersprechende Evidenz;
- alternative Hypothesen;
- Regel und Regelversion;
- Datenqualität/Vollständigkeit;
- Provenienz: Slicer-Tag oder Geometrie-Inferenz;
- Grund für UNKNOWN/AMBIGUOUS.

Ohne statistische Kalibrierung ist Confidence ein heuristischer Score,
keine mathematische Wahrscheinlichkeit.

5.12 Schwellenwerte

Alle Geometrieschwellen inventarisieren. Beispiel: Im bisherigen Code
wurde eine mittlere Hatch-Lücke von 3,0 mm als Grenze zwischen Sparse
und Solid Infill verwendet. Feste Grenzen können bei Düsen,
Linienbreiten, Skalierungen, Slicerprofilen und Bauteilgrößen falsch
sein.

Schwellenwerte dokumentieren, möglichst aus Linienbreite,
Düsendurchmesser, Layerhöhe und lokalem Kontext ableiten, konfigurierbar
machen und mit Tests absichern. Keine willkürliche Änderung.

5.13 Sieben Architektur-Schichten

1. G-Code-Interpreter: strukturierte Befehle.
2. Modal State und Bewegungsrekonstruktion.
3. Geometrie-Rekonstruktion aus normalisierten Bewegungen.
4. Layer-Modell und 3D-Topologie.
5. Feature-Klassifizierung mit Slicer-Tag-Provenienz.
6. Pattern- und Confidence-Engine.
7. R2-Adapter/Postprocessor für bestehendes Datenmodell, Marker und
   Ausgabe.

5.14 Verbindliche Multi-Pass-Pipeline: Pass 0 bis Pass 11

Nicht zu einem allgemeinen Schritt „Geometrie analysieren“ verkürzen.

PASS 0 – Rohdaten und Kommentar-Extraktion:
Originalzeilen, Kommentare, Tags, Metadaten, Zeilennummern und
Quellkontext erfassen; Slicer-Tags und sonstige Kommentare getrennt
halten; Provenienz sichern.

PASS 1 – Syntax- und Zustandsrekonstruktion:
Befehle parsen, Modalzustand aufbauen, Koordinaten-/Extrusionsmodi,
Einheiten, Toolzustände, Offsets und Resets berücksichtigen;
unbekannte Syntax dokumentieren.

PASS 2 – Bewegungsrekonstruktion:
Start-/Endpunkte, Bögen, Extrusion, Retract, Travel und Feedrate als
normalisierte Bewegungssegmente rekonstruieren; Annahmen protokollieren.

PASS 3 – Layer- und Z-Struktur:
Layergrenzen und Z-Verlauf rekonstruieren; variable Layerhöhen und
Z-Hop unterscheiden; nicht nur Kommentar-Marker verwenden.

PASS 4 – Extrusions- und Kinematikprofile:
Extrusionsvolumen, E-Modus, Flow, Geschwindigkeit, Beschleunigung
soweit verfügbar, Linienbreite und Materialfluss analysieren.
Kinematische Cluster sind Indizien, keine Beweise.

PASS 5 – Pfad- und Komponentenbildung:
Zusammenhängende Extrusionspfade, Polylinien, Konturen, Komponenten,
Islands und Featuregrenzen bilden.

PASS 6 – 2D-Geometrie pro Layer:
Konturen, Polygone, Bounding Boxes, Hüllen, Offsets, Rasterbilder,
Innen-/Außenbereiche, Hohlräume und lokale Abstände bestimmen.

PASS 7 – Inter-Layer- und 3D-Topologie:
Layer vergleichen; Materialstützung, Überhänge, freie Spannweiten,
Support-Gaps, Hohlräume und Kontinuität untersuchen.

PASS 8 – Feature-Klassifikation:
Wände, Infill, Surface, Bridge, Support, Brim usw. klassifizieren.
Verlässliche Slicer-Tags priorisieren und Provenienz erhalten.

PASS 9 – Pattern-Erkennung:
Infill-/Surface-Muster anhand Geometrie, Kinematik und Layerbeziehungen
untersuchen; nur bei ausreichender Evidenz konkret benennen.

PASS 10 – Konsistenzprüfung:
Widersprüche, unmögliche Sequenzen, Grenzfälle und unplausible
Klassifikationen prüfen; Alternativen, Ambiguität und Datenqualität
ausgeben; Sequenz-/Cross-Layer-Regeln anwenden.

PASS 11 – Ausgabe und Postprocessing:
Ergebnisse ins R2-Modell überführen, Tags/Berichte sicher ausgeben,
Original schützen, Diff/Backup erzeugen. Im ersten freigegebenen
Entwicklungsstadium nur nicht ausführbare Kommentare ergänzen;
keine Bewegungen, Extrusionen, Temperaturen oder Geschwindigkeiten
ändern.

5.15 Feature-Taxonomie

Die vollständigen Alias-/Feature-Tabellen aus FeatureErkennung.md,
docs/FEATURE_TAGGING.md, Postprocessor-Briefings und Reverse-
Engineering-Dokumenten sind als Originaldaten zu übernehmen.
Nicht aus dem Gedächtnis neu bauen und nicht auf wenige Typen kürzen.

Featurefamilien mindestens:

WÄNDE / SHELLS:
Wall, Shell, Perimeter, Outer/External Wall, Inner/Internal Wall,
Overhang Perimeter/Wall, Thin Wall/Single Extrusion,
Small/Short Perimeter als mögliche Speed-Unterklasse,
Gap Fill/Gap Infill, Seam als Start-/Endpunkt/Event.

INFILL / OBERFLÄCHEN:
Sparse/Internal Infill, Solid/Internal Solid Infill,
Top Surface/Top Solid Infill, Bottom Surface/Bottom Solid Infill,
Skin, Ironing, Bridge Infill/Bridge, Internal Bridge.

SUPPORT:
Support Material, Support, Support Infill, Support Wall/Outline,
Support Interface, Dense Support, Roof, Floor, Support Transition,
Tree/Organic Support, Support Base/Bottom, Support Brim.

BETTADHÄSION:
Skirt, Brim, Mouse Ears/Brim Ears, Raft, Raft Base,
Raft Interface/Middle, Raft Surface/Top.

MULTIMATERIAL / PURGE / WIPE:
Wipe Tower, Prime Tower, Prime Pillar, Ooze Shield, Purge Line,
Intro Line, Prime Blob, Wipe Move, Tool Change Block.

BEWEGUNGS-/EREIGNISROLLEN:
Travel, Retract, Unretract/Deretract/Prime, Color Change, Pause,
Layer-/Object-Marker, Tool Change.

Diese Begriffe sind nicht alle gleichartige G-Code-Kommentare.
Unterscheide echte G-Code-Kommentare, interne Slicer-Rollen,
Preview-/Viewer-Bezeichnungen, geometrisch inferierte Rollen und
Bewegungs-/Ereignistypen. Es gibt keinen universellen ISO-Standard
für Feature-Namen.

5.16 Slicerfamilien und Dialekte

Mindestens untersuchen:
Slic3r, PrusaSlicer, SuperSlicer, SliceBeam, OrcaSlicer, Bambu Studio
und Derivate, Cura/CuraEngine, Simplify3D, FlashPrint, ideaMaker,
Kiri:Moto, KISSlicer, CraftWare, MatterSlice/MatterControl, IceSL,
AstroPrint mit unterschiedlichen Backend-Dialekten.

Versionen/Dialekte erst als unterstützt deklarieren, wenn konkrete
G-Code-Fixtures getestet wurden. Vollständige Alias-Tabellen und
tatsächliche Schreibweisen aus den Quellen importieren.
Interne Rollen ohne entsprechenden G-Code-Kommentar als solche
kennzeichnen.

5.17 APPLY_TYPE, Canonicalisierung und CUSTOM-Eliminierung

Diese bestehende Logik ist kritisch und muss verstanden, erhalten und
getestet werden:
- Slicer-Kommentar-Erkennung.
- Alias-Mapping / TYPE_MAP.
- Exakte Canonicalisierung.
- Case-Normalisierung.
- Toleranz für Leerzeichen, Trennzeichen, Unterstriche, Bindestriche.
- CamelCase-Auflösung (ExternalPerimeter -> external perimeter).
- Bereits kanonische R2-Werte erkennen.
- Support-Sonderbehandlung.
- Deterministische CUSTOM-Eliminierungsleiter.
- Unknown-Feature-Behandlung.
- Featuregrenzen und APPLY_TYPE-Zuweisung.
- CUSTOM-Watch und geometrische Nachprüfung.
- C1–C9 CUSTOM-Gruppen exakt aus den Quellen.
- Cross-Layer-Sequenzprüfung.
- Konflikt-/Unmöglichkeitsprüfung.
- Trennung getaggter von geometrisch inferierten Daten.

Bekannte Codebeispiele:
- 'Wall outer', 'WALL-OUTER' und 'wall_outer' sollen gleich behandelt
  werden.
- Orca/Bambu-Platzhalter können CamelCase liefern, z. B.
  ExternalPerimeter.
- Bereits kanonische Werte wie INFILL-SPARSE dürfen nicht zu CUSTOM
  werden.
- Support-Varianten können anhand bekannter Begriffe normalisiert werden.
- CUSTOM-Eliminierung nutzt deterministische Tokens/Whitelists,
  kein ML und keine freie unscharfe Vermutung.
- Bekannte Tokenfamilien umfassen outer, shell, solid, ironing,
  bridge, brim, tower, support sowie Pattern-Begriffe.
- Pattern-Tokenbeispiele aus dem untersuchten Code:
  gyroid, honeycomb, lightning, cubic, lattice, concentric,
  rectilinear, hilbert, octagram, archimedean, trihexagon, hexagonal,
  zigzag, crosshatch, grid, wiggle, triangle und weitere.

Regeln:
- Begriffe ohne belastbare Zuordnung bleiben CUSTOM.
- Keine breite Fuzzy-Suche, die Wände irrtümlich CUSTOM macht.
- Keine blinde Teilstring-Suche mit Zufallstreffern.
- C1–C9-Bedeutung nicht erfinden; aus Code/Dokumenten extrahieren.
- Sequenzregeln für Ironing, Top-Surface, Brim usw. exakt prüfen.
  Manche Reihenfolgen werden absichtlich nicht erzwungen.
- CUSTOM-Zähler und File-Info müssen korrekt bleiben.
- APPLY_TYPE und Live-Tuning-Verbraucher schützen.

5.18 Geometrie und Patternanalyse

Getrennt analysieren:
- Flow/Extrusionsvolumen.
- XY-/XYZ-Pfadlängen.
- Linienbreite und Querschnittsschätzung.
- Pfadschluss.
- Polygonbildung und Konturhierarchie.
- Bounding Boxes und Convex Hulls.
- Offsets und Distanzen.
- Flächenabdeckung und Dichtekarten.
- Layerübergreifende Boolean-Operationen.
- Materialstützung über mehrere Layer.
- lokale Überhänge, Support-Gaps und untere Stützstrukturen.
- echte freie Spannweiten.
- mehrere Teile/Islands/Hohlräume.
- Bridge/Internal Bridge und Top-/Bottom-Surfaces.
- Pattern Gyroid, Grid, Lines, Rectilinear, Triangles, Cubic,
  Honeycomb, Lightning, Concentric, Hilbert usw.

Flow, Lüfterwert, Pfadform oder ein einzelner Layervergleich sind
Indizien, keine Beweise. Bestehende Ideen erhalten, mit den späteren
technischen Korrekturen des Briefings v2 abgleichen.

5.19 Tests und Benchmarks

Pflicht:
- Golden-Master-Ausgaben des aktuellen Stands.
- Regressionstests für bestehende R2-Dateien und reale G-Code-Fixtures.
- Slicer-Fixtures je Familie/Dialekt.
- Getaggte und ungetaggte Varianten.
- Modalzustands-, Bewegungs-, Geometrie-, Topologie-, Feature-,
  Pattern-, CUSTOM-/APPLY_TYPE- und Sequenztests.
- Präzision, Recall, F1 und Confusion Matrix, sofern Ground Truth
  existiert.
- Geometrie-/Volumenabweichungen.
- Laufzeit-/Speicherverbrauch und MAX_PTS-Ressourcenlimits.
- Determinismus und Reproduzierbarkeit.
- Ablationstests für Evidenzkanäle.
- Beschädigte, unvollständige und unbekannte Befehle.

Pro Klassifikation möglichst Ground Truth, Vorhersage, Feature,
Geometrieform, Pattern, Score, Evidenz, Provenienz und Fehlerklasse
erfassen. Keine unbelegten „100 % korrekt“-Aussagen.

5.20 Sichere erste Ausgabe

Nach Freigabe zunächst nur Diagnoseberichte oder nicht ausführbare
Kommentare erzeugen. Keine ausführbaren Bewegungen, Extrusionen,
Temperaturen, Geschwindigkeiten oder Beschleunigungen ändern, bis
dies separat spezifiziert und freigegeben ist. Originaldatei erhalten,
Ausgabe als neue Datei mit Diff/Backup/Herkunft.

======================================================================
6. AS SLICED UND AS LEGACY
======================================================================

Bei Dateiauswahl zwei klar getrennte Modi:

AS SLICED:
- Originale Slicer-Absicht ist maßgeblich.
- Keine ungefragte R2-Übernahme.
- Nur ausdrücklich gewählte, kompatible R2-Funktionen.
- Slicerparameter nicht stillschweigend überschreiben.

AS LEGACY:
- R2 übernimmt Verarbeitung und normalisiert, soweit sicher.
- R2-Presets, Live-Kontrollen, Fixes, Mesh-/Purge-Logik und
  Kompatibilitätsregeln können angewendet werden.
- Analyse muss Abweichungen zur Maschine/Materialannahme erkennen.
- Beispiele: Bowden vs Direct Drive, volumetrische E-Annahmen,
  Extruder-/Filamentkonfiguration und historische Einstellungen.
- Bei Unsicherheit warnen und Nutzerentscheidung einholen.

Das darf kein reines UI-Label sein; es muss zwei dokumentierte
Verarbeitungspfade geben.

======================================================================
7. DATEIVERWALTUNG, QUEUE, BILDER UND JOBS
======================================================================

Gemeldete Probleme aus früheren Releases:
- Optimize- und Generator-Ausgabeordner waren leer.
- Queue zeigte Jobs teils nicht, obwohl sie liefen.
- Sound/Töne fehlten.
- Benachrichtigungen funktionierten bei einigen Tools nicht.
- Bildlisten/Bildauswahl in Texture-/Generatorwerkzeugen fehlerhaft.
- Ausgewähltes Bild konnte nicht gewechselt/zurückgesetzt werden.
- Andere Bilder ließen sich nicht zuverlässig auswählen.
- UI-Zustände blieben hängen.
- Derselbe Dateibrowser war je Tool unterschiedlich implementiert.

Architekturauftrag:
- gemeinsamer File Manager;
- gemeinsamer Image Browser/Selector;
- gemeinsamer Queue-/Job-Manager;
- zentrale Notification-API;
- zentrale Sound-API;
- einheitliche Pfad- und Output-Registrierung;
- einheitliche Fehler-/Statuszustände.

Job-Erfolg nur, wenn Verarbeitung abgeschlossen ist, Ausgabedatei
existiert, lesbar/validiert und korrekt registriert ist, Queue-Status
mit Realität übereinstimmt und Benachrichtigung zuverlässig ausgelöst
wird. Keine Phantom-Jobs und keine Erfolgsmeldung ohne Ausgabe.

Originaldateien unveränderlich halten. Generierte/optimierte Kopien
speichern Quelle, Werkzeug, Parameter, Profil, Version und Historie.

======================================================================
8. SD-KARTE, SAVE_VARIABLES UND DELAYED-GCODE
======================================================================

SD-Karten-Schreibzugriffe während eines Drucks reduzieren, sowohl zur
Schonung der Karte als auch für Host-/MCU-Stabilität.

Es gab die Hypothese, große save_variables.cfg und gleichzeitige
Lese-/Schreibzugriffe hätten zu Problemen auf einem Pi Zero beigetragen.
Das ist zu messen, nicht pauschal als Ursache zu behaupten.

- Laufzeit-/temporäre Zustände im RAM halten.
- Persistente Einstellungen nur bei Änderung speichern.
- Schreibvorgänge gegebenenfalls bündeln.
- Wiederholtes vollständiges Umschreiben großer Dateien vermeiden.
- I/O-Last messen.
- Nicht annehmen, mehrere [save_variables]-Sektionen würden nativ
  unterstützt.
- r2_hardware.cfg trennt Hardwareeinstellungen von Klipper-Variablen;
  diese Trennung verstehen und schützen.

KRITISCH: Bestehende Delayed-Gcode-Funktionen NICHT entfernen,
ersetzen oder deaktivieren. Sie sind grundlegend für Live Tuning.
Sie dürfen geprüft und optimiert werden, ihr vollständiges Verhalten
muss erhalten bleiben.

======================================================================
9. MCU-SHUTDOWNS UND HOST-STABILITÄT
======================================================================

Die PDFs und docs/SHUTDOWN_REGISTER.md vollständig lesen.

Eine untersuchte Root-Cause-Analyse fand unmittelbar vor zwei
Shutdowns blockierte Klippy-Reactor-Zeiten von ca. 0,65–0,68 Sekunden.
Zeitgleich traten LCD-Callbacks, Delayed-Gcodes, Webhook-/Status-
Requests und fehlgeschlagene NeoPixel-Updates auf. Das ist Evidenz
für diese Ereignisse, nicht automatisch für alle Shutdowns.

Das Shutdown-Register enthält nach bisheriger Auswertung 16
Vorfallklassen. Beispiele:
- Host-Reactor-Stalls.
- Moonraker-Requests während Homing/Probing.
- 20 ausstehende API-Requests und doppelte 4-KB-Preview-Payloads
  während G28.
- 11 parallele Lithophane-Threads und Swap.
- wiederholte große SD-Scans.
- unnötige LED-Schreibvorgänge und Metadaten-Rewrites.
- NeoPixel-Updates während Probing.
- serielle Timeouts/Retransmits.
- rund 300 Macro-WebUI-Polling-Objekte; Reduktion auf 12 Objekte
  mit 2,5-s-Cache wurde als Verbesserung dokumentiert.
- _LED_QUIET während Homing/Probing.

Genaue 16 Klassen aus dem Originalregister übernehmen, nicht aus
dieser Kurzliste rekonstruieren.

Untersuchen:
Makros, Delayed-Gcodes, LCD-Callbacks, Webhooks, WebUI-Polling, LEDs,
NeoPixel, Sound, Python-Dienste, Scans, Metadaten, Generatoren,
Kamera/Sensoren/Add-ons, Host-MCU-Verbindung USB/UART/CAN, Live Tuning,
Pre-Print.

Prinzipien:
- Druck hat absolute Priorität.
- Asynchrone/gebündelte Aufrufe.
- Begrenzte Callback-Laufzeiten.
- Caches und Rate Limits.
- Worker-Prioritäten.
- Keine langen Berechnungen im Klippy-Reactor.
- Logging, Messwerte und Stress-Tests.
- Pi-3B+-Upgrade allein ist keine Lösung.
- Keine Zusage „nie wieder Shutdowns“; Ursachen messen und kategorisieren.

======================================================================
10. UI, LCD, WEBUI UND FEEDBACK
======================================================================

LCD mit Dreh-/Drückknopf ist Kernmerkmal. Nicht durch lange
Makrolisten ersetzen. WebUI soll funktionale Alternative sein, wenn
Hardware kein Klipper-Menü unterstützt.

Gemeinsamer Funktionskern/Zustand, getrennte Präsentationsflächen.
Keine doppelte Geschäftslogik, unnötigen Pollings oder Schreibzugriffe.

Relevante Dokumente:
docs/LCD_MENU_PORTABILITY.md
docs/WEBUI_MOONRAKER.md
docs/PORTABILITY_SOUND_DISPLAY.md

Bisher bekannte Displaytypen:
st7920, uc1701, emulated_st7920, ssd1306/sh1106,
hd44780, hd44780_spi, aip31068_spi.
Klipper [menu] ist bei konfiguriertem Display/Encoder grundsätzlich
hardwareunabhängig. Touch-/Hersteller-UIs und KlipperScreen rendern
nicht automatisch das Klipper-Menü; WebUI-Alternative vorsehen.
Exakte Kompatibilität aus Code und Doku verifizieren.

Bisher vorgeschlagene Menübereiche:
Print, Pre-Print, Live Tuning, Generators, Calibration, Maintenance,
Feedback, System. Das ist Planungsstand, nicht ungeprüft endgültig.

Sound/LED-Feedback ist Teil der Produktidentität, aber optional und
fehlertolerant. Es darf Druck und MCU-Stabilität nicht beeinträchtigen.

======================================================================
11. SOUND UND LEDS
======================================================================

Sound:
- macros/02_sounds.cfg verwendet nach bisheriger Analyse M300 mit
  SET_PIN PIN=beeper.
- Ohne passende [pwm_cycle_time beeper]-Konfiguration kann dies
  fehlschlagen.
- Guarded-M300-Verhalten und Hardwareerkennung prüfen.
- _SOUND_LIB enthält nach bisherigem Stand 19 Tunes; exakt inventarisieren.

Mögliche Ausgänge:
Board-Piezo, externer Buzzer/output_pin, Pi-GPIO mit geeignetem
Treiber (Lautsprecher nicht direkt an GPIO), Pi-Analog-/HDMI-Audio
soweit Modell/Hardware es unterstützen, WebUI WebAudio, stiller Betrieb.
Keine pauschale Behauptung gleicher Audioausgänge für alle Pi-Modelle.

LED:
- klipper-led_effect und [neopixel] optional.
- SET_LED_STATE muss ohne LEDs sicherer No-op sein.
- R257 _LED_QUIET unterdrückt nach bisherigem Stand Chain-Updates
  während Homing/Probing; Implementierung verifizieren.
- LED-Layouts, Chains, DotStar, EBB/CAN und Varianten inventarisieren.
- Keine unnötigen Updates oder Last.

======================================================================
12. HARDWAREKOMPATIBILITÄT UND MASCHINENMODELL
======================================================================

Ziel: breite Unterstützung üblicher Cartesian/Bedslinger- und CoreXY-
Drucker. Delta kann wegen rechteckiger Bettannahmen eingeschränkt sein.
Installer/Laufzeit introspektieren Konfiguration und Hardware und
nur unterstützte Funktionen aktivieren. Optionale Hardware muss
deaktivierbar sein.

Kompatibilitätsmatrix:
native / konfigurationsabhängig / Fallback / eingeschränkt /
nicht unterstützt.

Geometrische Bereiche trennen:
1. mechanischer Toolhead-Bewegungsbereich;
2. Probe-Messbereich inkl. Offset/Reichweite/Kollision;
3. bedruckbarer Bettbereich;
4. Generator-Nutzbereich;
5. Wartungs-/Wipe-/Parkpositionen.

Nicht aus position_max den bedruckbaren Bereich ableiten. Beim Ender-3
mit Microprobe kann X-Bewegung außerhalb der Bettkante für Probe nötig
sein, ohne dass diese Fläche bedruckbar ist.

Weitere Punkte:
- _R2_CONFIG-Bounds prüfen.
- nozzle_diameter aus [extruder] lesen.
- _gen_nozzle() existiert nach bisheriger Kenntnis; Verwendung in allen
  Generatoren prüfen.
- Düse beeinflusst Linienbreite, Wandgeometrie und Hatch.
- Motion-Limits aus Klipper lesen.
- Bed Mesh/KAMP nicht überschreiben.

Dual-Z:
- parallel verdrahtete Motoren an einem Treiber von unabhängig
  angesteuerten Z-Steppern unterscheiden.
- Z_TILT_ADJUST benötigt geeignete unabhängige Z-Stepper und Probe.
- QUAD_GANTRY_LEVEL für passende Mehrmotor-CoreXY-Gantry.
- SYNC_GANTRY bei parallel verdrahtetem Dual-Z prüfen.
- Tatsächliche Konfiguration prüfen, nicht pauschal zwei getrennte
  Endstops voraussetzen.

Filamentsensoren:
- Switch-Runout von Motion-Sensor/Jam unterscheiden.
- Runout: sicherer Wechsel möglichst an geeigneter Layergrenze.
- Motion-Sensor: passende Fehlererkennung und Pause.
- Optionaler Sensor muss ohne Hardware deaktivierbar sein.
- Intelligenter Filamentwechsel im Infill ist experimentell und nur bei
  zuverlässiger Feature-Erkennung denkbar; sicherer Fallback nötig.

Nozzle Wipe:
- Position im Maintenance/System-Menü konfigurierbar.
- Geführte Bewegung über Knopf/WebUI.
- X/Y speichern, testen, validieren.
- Darf außerhalb des bedruckbaren Betts liegen, muss mechanisch sicher
  erreichbar sein.
- Wipe-Bereich, Richtung und mehrere Positionen prüfen.

======================================================================
13. KALIBRIERUNG
======================================================================

Geführte Kalibrierungsleiter vollständig am LCD und mit WebUI-Gegenstück:
Z-Offset, Bed Leveling/Mesh, Z-Tilt, Input Shaper, Pressure Advance,
Flow, Extruder, Temperatur, Retraktion und Material.

Hardware erkennen und nur passende Schritte anbieten.
Ergebnisse mit Maschine, Düse, Material und Profil speichern.
Bestehende Implementierung mit KALIBRIERUNG.pdf abgleichen.
PDF-Inhalt nicht als Beweis für vorhandene Funktion behandeln.

======================================================================
14. GENERATOREN UND KREATIVE WERKZEUGE
======================================================================

Bisherige Toolfamilien, im Repository prüfen:
Lithophane, ColorPicture, Bricks, Labels, Plotter, ArtisticStrings,
Frames, Angles+Flat, Cable Ties, Gaskets, Geometry, Range, Texture,
Geometry Tools, Cake, Segment Fix, Retract Fix, Flow Cap, Travel Accel,
Quality Fix, File Check/RETAG, Optimized Copy, STL Export.

Creative-Possibilities beschreibt Werkzeuggruppen für Oberfläche,
Licht, Farbe, Struktur und Linien. Kombinationsbeispiele:
Texture/Fuzzy + Lithophane; ColorPicture + Labels;
Bricks + Frames + Angles; ArtisticStrings + Plotter.

Texture-Unterlagen beschreiben FUZZY- und BUMPS-Modi sowie nach
bisheriger Auswertung 21 Muster und 27 Presets. Exakte Inhalte aus
Originalquelle lesen.

Anforderungen:
- Generatoren kombinierbar und reproduzierbar.
- Parameter/Profile speichern.
- Gemeinsame Queue und Dateiverwaltung.
- Aktiver Druck hat Vorrang.
- Kein automatischer Druckstart.
- Ausgabedatei muss existieren, validiert und registriert sein.
- Fehler, Abbruch und Erfolg zuverlässig melden.

Workflow-Rezepte, nichtdestruktive Stufen, Variantensweeps, visuelle
Vergleiche und teilbare Rezepte sind Vorschläge, sofern sie nicht in
Originalquellen als verbindlich stehen. Als Vorschläge kennzeichnen.

======================================================================
15. BACKLOG UND TODO-DISPOSITION
======================================================================

Mögliche Quellen:
docs-notes/MASTER-TODO.md, docs/MASTER-TODO.md und weitere TODOs.
Tatsächliche Fundorte inventarisieren. Zusätzlich Code-Kommentare,
FIXME, XXX, Historie und Übergabedokumente durchsuchen.

Jede Aufgabe einzeln einordnen:
- beibehalten;
- in Zielarchitektur integrieren;
- separates Modul;
- wegen Abhängigkeit zurückstellen;
- zusammenführen;
- überholt/redundant/ungültig;
- Konflikt/technische Klärung nötig;
- bereits erledigt, aber unverifiziert.

Pro Aufgabe:
ID, Quelle/Fundstelle, Originalanforderung, Ist-Stand, Komponente,
Abhängigkeiten, Kategorie/Priorität, Empfehlung/Begründung,
erhaltene Produktanforderung, Ersatz/Umsetzung, Akzeptanzkriterien,
Testnachweis.

Nicht blind TODOs abarbeiten und nicht ignorieren. Erst Gesamtüberblick,
dann jede Aufgabe auf der richtigen technischen Grundlage einordnen.
Keine TODOs löschen oder ändern, bevor Disposition freigegeben ist.

======================================================================
16. VERBINDLICHER ERSTAUFTRAG – PHASEN
======================================================================

PHASE A – Quellen und Projektzustand sichern
1. Alle Archive, PDFs, MD/TXT-Dateien und Quellcode identifizieren.
2. Fehlende Dateien melden.
3. ANLEITUNG.md, STAND.md, docs/UEBERGABE.md lesen.
4. Restore-Anweisungen befolgen und Zielstand verifizieren.
5. Git-Status/lokale Änderungen dokumentieren.
6. Keinen Produktcode ändern.

PHASE B – Vollständige technische Inventur
1. Repository und Module lesen.
2. Architektur und Datenfluss dokumentieren.
3. r2_postproc.py und r2_postproc_next.py vollständig untersuchen.
4. Parser, Modal State, Feature-, Alias-, APPLY_TYPE-, CUSTOM-,
   Geometry-, Bitmap- und Generatorpfade erfassen.
5. LCD, WebUI, Queue, File Manager, Notifications, Sound, LEDs,
   Delayed-Gcodes und Save Variables untersuchen.
6. Kalibrierung, Pre-Print und Live Tuning prüfen.
7. Hardware- und Konfigurationsannahmen erfassen.
8. Tests und echte Testergebnisse inventarisieren.

PHASE C – Quellenabgleich / Anforderungsregister
1. Anforderungen aus Briefing und Originalquellen extrahieren.
2. Doppelte, widersprüchliche und abhängige Anforderungen markieren.
3. Originalanforderungen nicht stillschweigend umformulieren.
4. Jede Anforderung mit Quelle und Status verknüpfen.
5. Fehlende/unlesbare Quellen dokumentieren.

PHASE D – Gap- und Risikoanalyse
Je Komponente: vorhanden, nachweislich funktionierend, unvollständig,
fehlend, eng gekoppelt, fehleranfällig, Hardwareannahmen, Regressionen,
fehlende Tests und Abhängigkeiten. Jede Ist-Aussage mit Codefundstelle
oder Testbeleg.

PHASE E – Zielarchitektur und Migrationsplan
Vorlegen: Zielarchitektur, Modulgrenzen, Datenmodelle, Schnittstellen,
Datenfluss, Migration vorhandener Funktionen, Abhängigkeiten,
Parallelbetrieb alter/neuer Pfade, Golden Master, Regressionen,
Ressourcenstrategie, Hardwarekompatibilität, Sicherheit/Rollback,
Aufwand/Risiko und Reihenfolge vor/während/nach dem Umbau.

PHASE F – Backlog-Disposition
Jede Aufgabe einzeln in einer Matrix bewerten. Keine Löschung und
keine eigenständige Umsetzung.

PHASE G – FREIGABE-STOPP
Vollständigen Bericht vorlegen und STOPPEN. Erst nach ausdrücklicher
Freigabe Code ändern.

======================================================================
17. ERSTE LIEFERUNG – BERICHTSFORMAT
======================================================================

Der Erstbericht muss enthalten:
1. Executive Summary und wichtigste Risiken.
2. Quellen-/Restore-Bericht: Dateien, fehlende Quellen, Version, Git.
3. Architektur-Ist-Zustand, Module, Datenfluss, Schnittstellen.
4. Funktionsinventar: vorhanden, teilweise, geplant, defekt, unklar.
5. Postprocessor-Bericht: Parser, Modal State, Geometrie, Layer,
   Feature, Pattern, Confidence, APPLY_TYPE, CUSTOM, konkrete Stellen.
6. Reverse-Engineering-Bericht: Pass 0–11, Datenmodelle, Dialekte,
   Grenzen, Testkorpus.
7. UI-/Hardwarebericht: LCD, WebUI, Displays, Encoder, Kompatibilität.
8. Queue-/Datei-/Generatorbericht: Pfade, Jobs, Bilder, Benachrichtigung,
   Sound.
9. Stabilitätsbericht: Shutdowns, Reactor-Last, Delayed-Gcodes, Polling,
   LEDs, Sound, I/O, Ressourcen.
10. Kalibrierung und Live Tuning.
11. Vollständige Backlog-Disposition mit Quellen.
12. Zielarchitektur und Verantwortlichkeiten.
13. Migrationsplan, Reihenfolge, Abhängigkeiten, Zwischenzustände,
    Rollback.
14. Teststrategie, Golden Master, Benchmarks, Hardwaretests,
    Abnahmekriterien.
15. Tatsächlich offene Fragen nach Quellenprüfung.
16. Konkrete Freigabepunkte für den Auftraggeber.

======================================================================
18. QUALITÄTS- UND SICHERHEITSREGELN
======================================================================

- Originaldateien nicht überschreiben.
- Keine ausführbaren G-Code-Befehle ohne gesonderte Freigabe ändern.
- Druckparameter nicht unbemerkt verändern.
- Bestehende Funktionen erst nach Ersatz-/Regressionnachweis entfernen.
- Keine nicht erkannte Hardware voraussetzen.
- Optionale Komponenten müssen deaktivierbar sein.
- Keine langen/blockierenden Arbeiten im Klippy-Reactor.
- Druck vor Generatoren, UI, Sound und LEDs priorisieren.
- Hintergrundjobs mit Ressourcenlimits.
- Kein Job-Erfolg ohne echte, validierte und registrierte Ausgabe.
- Dateibrowser-/Bildauswahl nicht pro Werkzeug unterschiedlich neu bauen.
- Unsichere Feature-Inferenz nicht als Gewissheit ausgeben.
- Keine 100-%-Versprechen bei beliebigem G-Code.
- Unbekannte Befehle/Dialekte/Featuretypen sichtbar behandeln.
- Logs und Diagnosen müssen Fehleranalyse ermöglichen.
- Änderungen klein, überprüfbar und rückrollbar halten.
- Vor/nach jedem Migrationsschritt testen.
- Abweichungen vom freigegebenen Plan begründen und bei
  Verhaltensänderung erneut freigeben lassen.

======================================================================
19. LEITENTSCHEIDUNG
======================================================================

Das Projekt soll weder durch blindes Abarbeiten alter TODOs noch durch
einen vollständigen Neubau ohne Rücksicht auf vorhandene Arbeit
weiterentwickelt werden.

Zuerst wird das gesamte Projekt verstanden. Dann werden Anforderungen,
Ist-Implementierung und Zielarchitektur getrennt. Jede vorhandene
Funktion und Aufgabe erhält einen nachvollziehbaren Migrationspfad.
Erst nach Freigabe beginnt die schrittweise Umsetzung.

Postprocessor und G-Code Reverse Engineering sind kein Nebenthema.
Sie sind ein umfangreicher Entwicklungsstrang mit konkreten
Algorithmen, Datenmodellen, Feature-Taxonomien, Aliasregeln,
CUSTOM-Eliminierung, Layer-Topologie, Confidence-Logik,
Testanforderungen und einer definierten 12-Pass-Pipeline. Diese Arbeit
muss vollständig in die neue Architektur übernommen werden.

DEIN ERSTER AUFTRAG:
LIES ALLES. SICHERE ALLES. INVENTARISIERE ALLES. ANALYSIERE ALLES.
ERSTELLE DEN GESAMTPLAN. WARTE AUF FREIGABE.
NOCH NICHT PROGRAMMIEREN.

======================================================================
20. ERGÄNZUNG: ZENTRALE TOOLCHAIN-ARCHITEKTUR
======================================================================

20.1 Grundidee

Mehrere Pre-Print-Werkzeuge und Generatoren sollen zu einer
zusammenhängenden Verarbeitungskette kombiniert werden können.

Das ist ausdrücklich mehr als das separate Speichern mehrerer
Zwischenergebnisse. Es handelt sich um eine geordnete Verarbeitung,
bei der jedes Werkzeug auf dem Ergebnis des vorherigen Werkzeugs
aufbaut.

Beispiel:
Original-G-Code
  -> Range
  -> Text
  -> Scale
  -> Texture
  -> finales G-Code-Ergebnis

Die Werkzeuge werden in der vom Nutzer festgelegten Reihenfolge
ausgeführt. Ein Werkzeug erhält grundsätzlich die Ausgabe des
vorherigen Verarbeitungsschritts als Eingabe.

20.2 Ausgangsdatei

- Ausgangspunkt ist eine vom Nutzer ausgewählte Originaldatei.
- Die Datei kann beispielsweise direkt von der SD-Karte stammen.
- Die Originaldatei bleibt unverändert.
- Die gesamte Toolchain bezieht sich auf genau diese ausgewählte
  Ausgangsdatei.
- Eine gespeicherte Toolchain-Preset-Datei enthält nicht automatisch
  eine fest verdrahtete G-Code-Eingabedatei.
- Beim Laden einer Toolchain wird sie auf die aktuell ausgewählte
  Eingabedatei angewendet.

20.3 Verarbeitung und temporäre Zwischenstände

Bei einer Toolchain mit mehreren Verarbeitungsschritten:
- Jeder Job erhält die Ausgabe des unmittelbar vorherigen Jobs.
- Zwischenstände werden nur temporär erzeugt.
- Der nächste Job darf erst starten, wenn der vorherige Job erfolgreich
  abgeschlossen und seine Ausgabe geprüft wurde.
- Temporäre Zwischen-G-Code-Dateien sollen nach erfolgreicher
  Übernahme durch den nächsten Verarbeitungsschritt entfernt werden.
- Das System soll keine große Sammlung dauerhafter Zwischen-G-Code-
  Dateien erzeugen.
- Für Fehleranalyse und Wiederherstellung dürfen notwendige Diagnose-
  informationen und Metadaten erhalten bleiben.
- Bei einem Fehler darf kein unvollständiger Zwischenstand als
  erfolgreiches Endergebnis behandelt werden.

Sonderfall:
Besteht die Verarbeitung nur aus einem einzigen Werkzeugjob, ist
dies ein normaler Einzeljob. Seine Ausgabe wird dauerhaft gespeichert
und nicht wie ein Zwischenstand behandelt.

Bei zwei oder mehr Werkzeugjobs:
- Das Ergebnis des letzten Jobs ist das finale Ergebnis.
- Frühere Zwischenergebnisse sind temporär.
- Das finale Ergebnis wird dauerhaft gespeichert und registriert.

20.4 Jobs hinzufügen, einfügen und entfernen

Der Nutzer muss Jobs an beliebigen Positionen hinzufügen können.

Beispiele:
- Job am Ende ergänzen.
- Job zwischen zwei bestehende Schritte einfügen.
- Einen bestimmten Job entfernen.
- Einen späteren Schritt entfernen, ohne die ganze Toolchain zu
  verwerfen.

Das Entfernen darf nicht auf das Löschen des letzten Jobs beschränkt
sein.

Die sichtbaren Jobnummern werden nach Einfügen oder Entfernen
entsprechend neu nummeriert. Interne stabile IDs dürfen sich dadurch
nicht ändern.

Die Bedienung soll sich an der vorhandenen Job-/Labels-Auswahl
orientieren und über Dreh-/Drückknopf sowie eine entsprechende
WebUI-Bedienung möglich sein.

Beispiel:
Job 1 – Range
Job 2 – Text
Job 3 – Texture

Wird Job 2 entfernt, wird die sichtbare Reihenfolge:
Job 1 – Range
Job 2 – Texture

20.5 Abhängigkeiten und Neuberechnung

Wird ein Job eingefügt, entfernt oder in seinen Parametern geändert,
müssen die davon abhängigen nachfolgenden Ergebnisse neu berechnet
werden.

Unveränderte, nicht betroffene frühere Schritte sollen nach Möglichkeit
nicht unnötig erneut berechnet werden.

Die Verarbeitung muss die Abhängigkeiten der einzelnen Stufen kennen.
Ein späterer Job darf nicht versehentlich mit einer veralteten Ausgabe
eines früheren Jobs arbeiten.

20.6 Toolchain-Presets

Eine vollständige Toolchain soll als Preset gespeichert und später
wieder geladen werden können.

Ein Toolchain-Preset enthält mindestens:
- Reihenfolge der Werkzeuge;
- Werkzeugidentität;
- Werkzeugparameter;
- relevante Versionen und Abhängigkeiten;
- notwendige Kompatibilitätsinformationen;
- erforderliche Randbedingungen.

Beim Laden:
- wird die Toolchain auf die aktuell ausgewählte Eingabedatei
  angewendet;
- kann der Nutzer unerwünschte Jobs entfernen;
- können neue Jobs ergänzt oder zwischen bestehende Jobs eingefügt
  werden;
- wird die Verarbeitungskette anschließend entsprechend neu aufgebaut.

20.7 Architekturvorgabe

Die Toolchain ist eine gemeinsame, zentrale Architektur.

Nicht jedes Werkzeug darf eine eigene, inkompatible Verkettungslogik
implementieren.

Die Architektur soll mindestens drei Ebenen unterscheiden:

1. Tools:
   einzelne Generatoren und Bearbeitungswerkzeuge.

2. Toolchains:
   konkrete geordnete Verarbeitungsketten aus Werkzeugjobs.

3. Toolchain Presets:
   dauerhaft gespeicherte Vorlagen solcher Verarbeitungsketten.

Die bisher gezeigte UI-Demo war nur ein Interaktionsmodell und keine
bereits implementierte Funktion.

Die Toolchain ist eine größere kreative Entwicklungsfunktion und
nicht automatisch die erste Implementierungspriorität. Die neue
Coding-KI soll zuerst die Architektur und vorhandenen Werkzeuge
verstehen und anschließend eine phasenweise Umsetzung vorschlagen.

======================================================================
21. ERGÄNZUNG: AUSGABEMODI UND ÜBERGANG ZUM DRUCK
======================================================================

21.1 Grundlegende Ausgabemodi

Für globale Einstellungen und – soweit sinnvoll – pro Werkzeug soll
es unterschiedliche Ausgabemodi geben:

1. Nur erzeugen und speichern:
   G-Code wird erzeugt und gespeichert. Der Nutzer kann ihn später
   prüfen und auswählen.

2. Erzeugen und in der Klipper-3D-Vorschau anzeigen:
   Das Ergebnis wird erzeugt und anschließend in der Vorschau
   präsentiert.

3. Erzeugen und als nächste/aktuelle Druckdatei auswählen:
   Das Ergebnis wird bei ausreichender Sicherheit und erfolgreicher
   Validierung als aktuelle Druckauswahl übernommen.

4. Fix/Tool auf die aktuelle Druckdatei anwenden:
   Das ausgewählte Werkzeug erzeugt eine neue Kopie und wechselt nach
   erfolgreicher Prüfung die logische Druckauswahl auf diese neue
   Datei.

21.2 Originaldatei und abgeleitete Dateien

- Das Original bleibt unveränderlich.
- Jede bearbeitete Datei ist eine abgeleitete Datei.
- Herkunft, Ausgangsdatei, Werkzeug, Parameter, Profil und Version
  müssen nachvollziehbar bleiben.
- Die aktuelle logische Druckauswahl darf nach einem erfolgreichen
  Fix auf die neue abgeleitete Datei wechseln.
- Der Nutzer soll danach nicht erst manuell im Dateibrowser nach dem
  korrigierten Ergebnis suchen müssen.

WICHTIG:
Das automatische Wechseln der ausgewählten Druckdatei bedeutet
NICHT, dass der physische Druck automatisch gestartet wird.

Ein Druckstart erfordert immer eine ausdrückliche Nutzeraktion.

21.3 Globale Voreinstellungen und Werkzeuganforderungen

Globale Ausgabeeinstellungen dürfen pro Werkzeug überschrieben
werden.

Die globalen Einstellungen dürfen aber niemals Sicherheits- oder
Validierungsanforderungen eines Werkzeugs außer Kraft setzen.

Ein Werkzeug darf beispielsweise einen zwingenden Preview- oder
Prüfschritt verlangen, auch wenn global eine automatische Auswahl
konfiguriert ist.

21.4 UNKNOWN und AMBIGUOUS

Eine unklare Feature-Klassifikation darf nicht pauschal verhindern,
dass ein experimentelles Werkzeug ausgeführt wird.

Stattdessen muss zwischen zwei Dingen unterschieden werden:

A) Darf die Verarbeitung ausgeführt werden?
B) Darf ihr Ergebnis automatisch als druckfertige aktuelle Datei
   übernommen werden?

Bei UNKNOWN/AMBIGUOUS:
- darf ein experimenteller Generator grundsätzlich ausgeführt werden,
  sofern seine eigenen Voraussetzungen erfüllt sind;
- wird das Ergebnis separat gespeichert;
- wird eine Vorschau bzw. ausdrückliche Prüfung verlangt;
- darf das Ergebnis nicht stillschweigend die aktuelle Druckauswahl
  ersetzen;
- darf es nicht automatisch als unmittelbar druckfertig gelten.

Die Confidence-Klassifikation beeinflusst damit insbesondere den
Übergang zur Druckauswahl, nicht zwingend die Ausführbarkeit des
Werkzeugs.

21.5 Validierung

Eine Vorschau ist hilfreich, aber kein mathematischer Sicherheitsbeweis.

Vor automatischer Übernahme sind – abhängig vom Werkzeug – mindestens
Syntax, Dateiintegrität, Geometrie, Maschinenlimits und relevante
Risiken zu prüfen.

Fehlgeschlagene oder unvollständige Ergebnisse dürfen niemals als
fertige erfolgreiche Ausgabe registriert oder ausgewählt werden.

======================================================================
22. ERGÄNZUNG: GEMEINSAME QUEUE UND JOBSTEUERUNG
======================================================================

22.1 Gemeinsame Queue

Generatoren und rechenintensive Pre-Print-Werkzeuge sollen eine
gemeinsame Job-Queue verwenden.

Die Queue ist nicht nur eine Anzeige laufender Jobs, sondern steuert
auch die sichere Übergabe zwischen Verarbeitung und Druck.

Statuswerte:
- queued;
- running;
- success;
- failed;
- cancelled.

Ein Job gilt erst als erfolgreich, wenn:
- die Verarbeitung tatsächlich abgeschlossen ist;
- die erwartete Ausgabedatei existiert;
- die Datei lesbar und geprüft ist;
- die Datei korrekt registriert wurde;
- der Queue-Status mit dem tatsächlichen Zustand übereinstimmt.

Keine Phantom-Jobs und keine Erfolgsmeldungen ohne reale Ausgabe.

22.2 Druckpriorität

Ein aktiver Druck hat absolute Priorität vor Hintergrundverarbeitung.

Generatoren dürfen:
- keine unkontrollierte CPU-Last erzeugen;
- keinen unnötigen RAM-Verbrauch verursachen;
- keine I/O-Last erzeugen, die den Druck beeinträchtigt;
- keine langen blockierenden Aufgaben im Klippy-Reactor ausführen.

Hintergrundjobs müssen begrenzt, priorisiert und kontrollierbar sein.

22.3 Abhängigkeit zwischen Queue und Druckstart

Wenn ein Druckablauf von einem noch nicht abgeschlossenen
Generierungsjob abhängt, muss der Druckstart auf die erfolgreiche
Fertigstellung und Validierung dieses Jobs warten können.

Der Nutzer muss den tatsächlichen Zustand erkennen können.

Die Queue darf niemals einen unvollständigen Job als fertige
Druckdatei übergeben.

22.4 Toolchains in der Queue

Eine Toolchain wird als geordnete Folge voneinander abhängiger Jobs
ausgeführt.

- Job N+1 startet erst nach erfolgreicher Verarbeitung und Validierung
  von Job N.
- Temporäre Zwischenstände werden erst gelöscht, nachdem der nächste
  Verarbeitungsschritt sie erfolgreich übernommen hat.
- Fehlerhafte Stufen müssen nachvollziehbar bleiben.
- Für Diagnose und Wiederherstellung dürfen erforderliche Metadaten
  erhalten bleiben.
- Der finale Job erzeugt die dauerhaft gespeicherte Enddatei.

Ein physischer Druckstart erfolgt niemals automatisch durch den
Abschluss eines Queue-Jobs.

======================================================================
23. ERGÄNZUNG: OBJEKTORIENTIERTE PRE-PRINT-WERKZEUGE
======================================================================

23.1 Gemeinsames Objektmodell

Alle Pre-Print-Werkzeuge sollen ein gemeinsames Objektmodell und eine
gemeinsame Objekterkennung verwenden.

Nicht jedes Werkzeug darf unabhängig und unterschiedlich versuchen,
Objekte im G-Code zu erkennen.

Die Postprocessor-/Geometrieanalyse soll nach Möglichkeit erkennen:
- Anzahl der eigenständigen Modelle;
- zusammenhängende und getrennte Geometriekomponenten;
- wiederholte Instanzen;
- Objektmarker und Objektgrenzen;
- globale Hilfsgeometrie wie Support, Brim, Skirt, Raft oder Purge Tower.

23.2 Wichtige Unterscheidungen

Die Erkennung muss unterscheiden können zwischen:

A) Einem Modell mit mehreren voneinander getrennten Inseln oder
   Komponenten.

B) Mehreren unabhängigen Modellen auf dem Druckbett.

C) Mehreren Instanzen desselben Modells.

D) Globaler Hilfsgeometrie, die nicht als eigenständiges Modell
   behandelt werden darf.

Diese Fälle dürfen nicht allein anhand der Anzahl räumlich getrennter
Komponenten gleichgesetzt werden.

23.3 Print by Layer und Print by Object

Print by Layer und Print by Object müssen berücksichtigt werden.

Die Verarbeitung darf die Objektzuordnung und Reihenfolge nicht
zerstören.

Mehrere Instanzen und einzeln gedruckte Objekte müssen – soweit aus
G-Code und Metadaten rekonstruierbar – getrennt behandelt werden.

23.4 Objektauswahl

Der Nutzer soll auswählen können:
- ein einzelnes Objekt;
- mehrere ausgewählte Objekte;
- alle Objekte;
- kein Objekt bzw. Auswahl zurücksetzen.

Die Auswahl muss werkzeugübergreifend stabil sein.

Beispiel:
Objekt 1: Texture FUZZY
Objekt 2: Texture BUMPS
Objekt 3: unverändert

23.5 Geometrische Transformationen

Transformationen wie:
- Twist;
- Scale X/Y;
- Taper;
- weitere Geometrieänderungen;

sollen sich auf den Mittelpunkt bzw. das eigene Geometriezentrum des
jeweils ausgewählten Objekts beziehen.

Die ursprüngliche Position auf dem Druckbett soll erhalten bleiben,
soweit die jeweilige Transformation dies zulässt.

Nicht die gesamte Druckbett-Bounding-Box als Transformationszentrum
verwenden, wenn einzelne Objekte bearbeitet werden.

23.6 Kollisions- und Sicherheitsprüfung

Nach Objekttransformationen prüfen:
- Überschneidungen zwischen Modellen;
- Kollisionen mit Bettgrenzen;
- Abstände zwischen Objekten;
- Kollisionen mit Hilfsgeometrie;
- Maschinen- und Druckbereichsgrenzen.

Bei unsicherer Objektzuordnung darf ein experimentelles Werkzeug
gegebenenfalls trotzdem laufen. Das Ergebnis muss dann aber in die
AMBIGUOUS-/Preview-Behandlung fallen und darf nicht automatisch
als sicher druckfertig übernommen werden.

23.7 Stabile Objekt-IDs

Objekt-IDs und Auswahlzustände müssen über Toolchains hinweg möglichst
stabil bleiben.

Nach Geometrieänderungen kann eine erneute Analyse notwendig sein.
Die neue Analyse muss dokumentieren, welche Zuordnung übernommen,
verändert oder nicht mehr sicher erkannt wurde.

Slicer-Metadaten, Geometrie, Bewegungsreihenfolge und Layerstruktur
sind als Evidenzquellen zu verwenden. Confidence und Provenienz
müssen erhalten bleiben.

======================================================================
24. ERGÄNZUNG: STL-/OBJ-EXPORT AUS G-CODE
======================================================================

24.1 Ziel

Die vorhandene Exportfunktion soll nicht nur irgendeine STL-Datei
schreiben, sondern ein tatsächlich brauchbares, möglichst
druckbares Modell rekonstruieren.

Der Zweck ist die Rekonstruktion der Modellgeometrie aus G-Code,
nicht die Umwandlung sämtlicher Werkzeugpfade in Röhren oder
Dreiecksstrukturen.

STL ist das primäre Zielformat. OBJ ist als zusätzliche Möglichkeit
zu prüfen. 3MF ist hier nicht das primäre Ziel.

24.2 Bekannter Fehlerzustand

Eine vorhandene Exportfunktion war bereits integriert, erzeugte aber
unbrauchbare STL-Dateien.

Ein späterer KI-Fix verbesserte die Darstellbarkeit teilweise, löste
das Problem jedoch nicht vollständig.

Daher:
- Funktion nicht als fertig betrachten, nur weil eine Datei erzeugt
  wird.
- Vorhandene fehlerhafte Exportdateien als Regression-Fixtures sichern.
- Root Cause untersuchen.
- Export erst nach unabhängiger Prüfung als funktionsfähig einstufen.

24.3 Modellgeometrie statt Toolpath-Mesh

Der Export soll möglichst die leere Modellgeometrie rekonstruieren.

Auszuschließen sind insbesondere:
- Support und Support Interface;
- Sparse Infill;
- Solid Infill, soweit es nicht zur äußeren Modellkontur gehört;
- Top-/Bottom-Skin, soweit sie nicht Teil der zu rekonstruierenden
  Außenhülle sind;
- Brim;
- Skirt;
- Raft;
- Mouse Ears;
- Prime-/Purge-/Wipe-Tower;
- Travel;
- Retract/Unretract;
- Reinigungs- und Kalibriergeometrie.

Die konkrete Klassifikation muss die Grenzen der verfügbaren
G-Code-Information berücksichtigen.

24.4 Mehrere Objekte und Druckreihenfolge

Der Export muss untersuchen:
- mehrere Modelle auf einem Druckbett;
- Print by Layer;
- Print by Object;
- mehrere Inseln und Komponenten;
- wiederholte Instanzen;
- sich berührende oder überlappende Objekte;
- fehlende oder inkonsistente Objektmarker;
- Modell plus Support;
- globale Hilfsgeometrie.

24.5 Technische Grundlage

Die Rekonstruktion muss auf dem normalisierten Bewegungsmodell,
Extrusionspfaden, Layer-Modell, Konturen, Polygonhierarchie und
3D-Topologie aufbauen.

Nicht alle extrudierenden Bewegungen dürfen pauschal in Mesh-
Geometrie umgewandelt werden.

Zu untersuchen:
- Konturrekonstruktion;
- Extrusionsquerschnitt;
- Linienbreite und Layerhöhe;
- Objektsegmentierung;
- Slicer-Metadaten;
- Konturverbindung zwischen Layern;
- Hohlräume und Innenkonturen;
- variable Layerhöhen;
- Wandstärken und lokale Geometrieänderungen.

24.6 Mesh-Validität

Mindestens prüfen:
- korrekte ASCII- oder Binary-STL-Struktur;
- Header, Dreiecksanzahl und Dateilänge;
- endliche Koordinatenwerte;
- konsistente Millimeter-Konvention;
- keine degenerierten Dreiecke;
- korrekte Dreiecksorientierung;
- konsistente Normalen;
- keine doppelten Flächen;
- Watertight-/Manifold-Status;
- Selbstüberschneidungen;
- Anzahl der Komponenten;
- Bounding Box;
- Volumen.

STL enthält keine native Einheiteninformation. Die verwendete
Einheitenkonvention muss deshalb dokumentiert werden.

24.7 Mesh-Aufbau

Zu untersuchen:
- Triangulierung von Konturen mit Löchern;
- Verbindung aufeinanderfolgender Layer;
- variable Layerhöhen;
- geneigte Flächen und Überhänge;
- obere und untere Flächen;
- getrennte Komponenten;
- kontrolliertes Welding;
- Reparaturverfahren ohne unbemerkte Geometrieveränderung.

Keine Reparaturbibliothek darf stillschweigend das Modell so verändern,
dass die resultierende Geometrie nicht mehr nachvollziehbar ist.

24.8 STL und OBJ

STL:
- kann getrennte Komponenten enthalten;
- speichert aber keine native Objekt-/Gruppenstruktur wie ein
  CAD-Projekt.

Daher prüfen:
- eine STL mit mehreren getrennten Komponenten;
- alternativ einzelne STL-Dateien pro Modell.

OBJ:
- Gruppen-/Objektzuordnung und gültige Indizes prüfen.

24.9 Testmatrix

Mindestens:
- einfacher Quader;
- Quader mit Loch;
- geneigte Flächen;
- Überhänge;
- dünne Wände;
- mehrere Objekte, Print by Layer;
- mehrere Objekte, Print by Object;
- wiederholte Instanzen;
- Modell mit Support;
- Brim/Skirt/Raft;
- Infill;
- Purge Tower;
- getrennte Inseln;
- variable Layerhöhen;
- ungetaggter G-Code;
- unterschiedliche Slicerfamilien.

24.10 Unabhängige Prüfung

Die exportierten Dateien müssen:
- in mindestens zwei unabhängigen Programmen geöffnet werden;
- in einen Slicer importiert werden können;
- erneut slicebar sein;
- auf Bounding Box, Volumen, Dreiecksanzahl und Komponenten geprüft
  werden;
- auf offene Kanten, degenerierte Flächen und Manifold-Probleme
  geprüft werden.

Messwerte und Testergebnisse dokumentieren.

24.11 Grundsätzliche Grenze

G-Code enthält normalerweise nicht die vollständige ursprüngliche
CAD-Geometrie.

Der Export ist eine Rekonstruktion bzw. Annäherung anhand von
Konturen, Wänden, Layern, Bewegungen und verfügbaren Objektmarkern.

Keine exakte Wiederherstellung des ursprünglichen CAD-Modells
versprechen.

24.12 Erstauftrag an die neue Coding-KI

- vorhandenen Exporter und seine Historie lokalisieren;
- alte Exportfehler als Fixtures sichern;
- Root Cause bestimmen;
- erforderliche Geometrieeingaben und Abhängigkeiten dokumentieren;
- Zielarchitektur und Teststrategie vorlegen;
- vor Implementierung auf Freigabe warten.

======================================================================
25. ERGÄNZUNG: EXTRUSIONSKOMPENSATION BEI GEOMETRIEÄNDERUNGEN
======================================================================

25.1 Problem

Werkzeuge wie Twist, Scale, Taper und andere Geometrieänderungen
können die Länge von Extrusionspfaden verändern.

Wenn die ursprünglichen E-Werte unverändert bleiben, ändert sich
dadurch die Materialmenge pro Wegstrecke.

Das kann lokal zu Überextrusion oder Unterextrusion führen und
beispielsweise veränderte Wandstärken oder Oberflächen verursachen.

25.2 Grundprinzip

Die neue Pfadlänge muss mit der ursprünglichen Pfadlänge verglichen
werden.

Für eine vereinfachte Betrachtung bei gleichbleibendem gewünschtem
Materialquerschnitt gilt:

E_neu = E_alt * (L_neu / L_alt)

Diese Beziehung ist nur eine vereinfachte Grundformel und darf nicht
pauschal auf beliebige G-Code-Dateien angewendet werden.

25.3 Tatsächliche Material- und Bewegungssemantik

Eine belastbare Implementierung muss zusätzlich berücksichtigen:
- Extrusionsvolumen;
- tatsächliche Pfadlänge;
- Linienbreite und Querschnitt;
- Layerhöhe;
- variable Layerhöhen;
- absolute und relative Extrusion;
- M82/M83;
- G92-Resets;
- mehrere Tools/Extruder;
- Flow-Faktoren;
- volumetrische Extrusion;
- Retract und Unretract;
- Travel-Moves;
- Featuregrenzen;
- segmentweise Zuordnung der ursprünglichen und neuen Pfade.

Keine globalen E-Faktoren über die gesamte Datei anwenden, wenn
nur einzelne Pfade oder Features transformiert wurden.

25.4 Betroffene Werkzeuge

Die Prüfung ist nicht nur für Twist vorzusehen.

Alle Geometrieänderungen untersuchen, insbesondere:
- Twist;
- Scale;
- Taper;
- weitere Werkzeuge, die Pfadlängen oder Geometrie verändern.

Für jedes Werkzeug dokumentieren:
- welche Geometrie verändert wird;
- wie Original- und Zielpfade einander zugeordnet werden;
- wie Pfadlängen berechnet werden;
- wie Extrusion angepasst wird;
- welche Randfälle nicht sicher unterstützt werden.

25.5 Unsicherheit

Wenn Original- und Zielpfade nicht zuverlässig zugeordnet werden
können oder die Extrusionssemantik unklar ist:
- keine präzise Kompensation vortäuschen;
- Unsicherheit dokumentieren;
- betroffene Segmente markieren;
- sichere Fallback-Strategie definieren;
- keine globale Korrektur ohne belastbare Grundlage anwenden.

25.6 Priorität

Die Extrusionskompensation ist eine wichtige Anforderung für die
Druckintegrität geometrisch verändernder Werkzeuge.

Sie muss als eigener Prüf- und Entwicklungsbereich im Architektur-
und Testplan auftauchen.

======================================================================
26. ERGÄNZUNG: TEXTURE – INNENWAND-FÜHRUNG UND WANDSTÄRKE
======================================================================

26.1 Ausgangspunkt und bestehendes Verhalten

Bei früheren Arbeiten an der Texture-Funktion wurde ein Verhalten
eingeführt bzw. diskutiert, bei dem die Innengeometrie der Außenwand
folgt.

Ziel ist, dass eine nach innen wirkende Textur nicht einfach Material
aus der Wand entfernt, die Wand unzulässig ausdünnt oder Löcher
erzeugt.

Die Textur soll den gewünschten visuellen Effekt möglichst erhalten,
ohne die Druckbarkeit und die grundlegende Wandgeometrie zu zerstören.

Die neue Coding-KI muss zunächst feststellen:
- ob dieses Verhalten im aktuellen Code vorhanden ist;
- ob es nur teilweise vorhanden ist;
- ob es durch spätere Änderungen verloren ging;
- in welcher Version bzw. welchem Commit es eingeführt wurde;
- wie die bisherige Implementierung tatsächlich funktioniert.

Nicht einfach behaupten, die Funktion sei vorhanden.

26.2 Historische Untersuchung

Folgende Quellen untersuchen:
- aktuelle Texture-Implementierung;
- r2_texture.py;
- Postprocessor- und Generatorcode;
- Git-Historie;
- ältere Projekt-Snapshots;
- Patches;
- frühere Versionen;
- vorhandene Testdateien;
- frühere Entwicklungsbriefings.

Die historische Implementierung soll nachvollzogen werden, bevor
eine neue Lösung entworfen wird.

Keine bereits gut funktionierende Lösung ohne Grund ersetzen.

26.3 Wandstärke und innere Geometrie

Die Lösung darf nicht einfach dieselbe Verschiebung auf Innen- und
Außenwand anwenden.

Ziel ist eine geometrisch nachvollziehbare Beziehung zwischen
Außenoberfläche und Innenbegrenzung.

Zu untersuchen:
- Wandstärke;
- lokale Normalen;
- Oberflächenkrümmung;
- Offset-Geometrie;
- lokale Geometrieveränderungen;
- Mindestwandstärke;
- mögliche Durchbrüche;
- lokale Überlappungen;
- Übergänge zwischen Wand und anderen Flächen.

Die Innenwand soll der veränderten Außenwand möglichst so folgen,
dass die vorgesehene Wandstärke erhalten bleibt, soweit dies
geometrisch möglich ist.

26.4 Innenkonturen, Löcher und Kanäle

Die Geometrie darf nicht nur als äußere Silhouette eines Körpers
verstanden werden.

Unterscheide:
- äußere Körperoberflächen;
- Innenflächen von Löchern;
- Kanäle;
- Hohlräume;
- innere Konturen;
- Wandbereiche zwischen mehreren Öffnungen.

Die Innenflächen von Löchern sind ebenfalls freie Oberflächen und
müssen bei Textur und Wandführung berücksichtigt werden.

Löcher und innere Kanäle dürfen durch die Textur nicht unbeabsichtigt
verschlossen, geöffnet oder zerstört werden.

26.5 Unterschiedliche Flächentypen

Vertikale Wandflächen, Top-/Bottom-Surfaces und Übergangsbereiche
müssen getrennt betrachtet werden.

Die gleiche Verschiebungsregel ist nicht automatisch für alle
Flächentypen geeignet.

Insbesondere:
- vertikale Wände;
- geneigte Wände;
- obere Flächen;
- untere Flächen;
- Übergänge zwischen Wand und Top-/Bottom-Surface;
- Wandbereiche um Löcher und Kanäle.

26.6 Range und andere Bearbeitungswerkzeuge

Untersuchen, wie sich die Textur auf unterschiedliche Bereiche eines
Objekts auswirkt.

Besonders wichtig:
- Range-Bearbeitungen;
- teilweise bearbeitete Wandbereiche;
- Übergänge zwischen bearbeiteten und unbearbeiteten Bereichen;
- obere und untere Begrenzungen;
- Wandstärken an diesen Übergängen.

Die Bearbeitung darf keine unerwarteten Löcher, Materialdurchbrüche
oder vollständig entfernten Wandbereiche erzeugen.

26.7 Bekannte positive Tests

Die vorhandenen Rose-Testdosen bzw. Rose-Testbehälter mit komplexer
Textur sehen nach bisheriger Nutzerbeobachtung sehr gut aus.

Diese Testobjekte sind als Golden-Master- bzw. Regression-Fixtures
zu sichern.

Das vorhandene gute Erscheinungsbild darf durch eine neue
Innenwandlogik nicht verschlechtert werden.

26.8 Akzeptanzkriterien

Die Textur soll:
- den gewünschten visuellen Effekt erhalten;
- die vorgesehene Wandstärke möglichst erhalten;
- keine unbeabsichtigten Durchbrüche erzeugen;
- keine Löcher oder Kanäle unbeabsichtigt zerstören;
- Innenkonturen korrekt berücksichtigen;
- Übergänge zu Top-/Bottom-Surfaces kontrollieren;
- bei komplexen Formen reproduzierbar funktionieren.

Der Nutzer akzeptiert im Einzelfall gewisse Abweichungen von der
ursprünglichen Maßgenauigkeit, wenn dadurch die Druckbarkeit und
der gewünschte optische Effekt zuverlässig erhalten bleiben.

Die Abwägung zwischen Maßhaltigkeit, Wandstärke und Texturqualität
muss jedoch nachvollziehbar und reproduzierbar sein.

======================================================================
27. ERGÄNZUNG: RANGE-TOOL – REGRESSION UND FEHLERANALYSE
======================================================================

27.1 Ausgangslage

Das Range-Werkzeug hat nach Nutzerbeobachtung früher funktioniert.

In neueren Generationen traten wiederholt Range Errors auf.

Es gab Hinweise auf einen begonnenen bzw. eingeführten Fix. Ob dieser
Fix tatsächlich funktioniert, ist bisher nicht ausreichend belegt.

Die neue Coding-KI darf den Fehler daher weder als behoben noch als
vollständig verstanden behandeln.

27.2 Historische Untersuchung

Untersuchen:
- aktuelle Range-Implementierung;
- ältere funktionierende Versionen;
- Git-Historie;
- Patches;
- frühere Fehlerbehebungen;
- betroffene Testdateien;
- G-Code-Beispiele, bei denen Range früher funktioniert hat;
- neuere Dateien, bei denen Range Errors auftreten.

Früher funktionierende Dateien sollen als Regression-Fixtures
gesichert werden.

27.3 Fehleranalyse

Insbesondere prüfen:
- Range-Grenzen;
- Layer-Indexierung;
- Zeilen-/Segment-Indexierung;
- Start- und Endwerte;
- inklusive/exklusive Grenzen;
- Off-by-one-Fehler;
- leere oder nicht vorhandene Bereiche;
- Einheiten und Koordinaten;
- variable Layerhöhen;
- unvollständige G-Code-Dateien;
- Verhalten bei fehlenden Feature-Tags;
- Wechselwirkungen mit Toolchains;
- Verhalten nach vorherigen Geometrieveränderungen.

27.4 Tests

Mindestens:
- gültiger normaler Bereich;
- Bereich am Anfang der Datei;
- Bereich am Ende der Datei;
- ein einzelner Layer;
- mehrere Layer;
- leere Bereiche;
- Grenzwerte;
- ungültige oder umgekehrte Grenzen;
- variable Layerhöhen;
- bereits veränderte Geometrie;
- Range innerhalb einer Toolchain;
- wiederholte Range-Ausführung.

27.5 Abnahme

Ein Fix gilt erst als abgeschlossen, wenn:
- der ursprüngliche Fehler reproduziert oder nachvollziehbar
  dokumentiert wurde;
- die Ursache identifiziert wurde;
- der Fix mit den alten und neuen Fixtures getestet wurde;
- keine Regression bei bisher funktionierenden Fällen auftritt;
- die Ergebnisse nachvollziehbar dokumentiert sind.

Keine bloße Änderung ohne Test als Fehlerbehebung deklarieren.

======================================================================
28. ERGÄNZUNG: VOLLSTÄNDIGE G-CODE-REVERSE-ENGINEERING-STRATEGIE
======================================================================

28.1 Ziel

Die Reverse-Engineering-Engine muss auch mit ungetaggten G-Code-
Dateien arbeiten können.

Sie darf nicht davon abhängig sein, dass ein Slicer alle Bewegungen
mit eindeutigen Feature-Kommentaren versieht.

Ziel ist eine möglichst vollständige Rekonstruktion von:
- Bewegungen;
- Extrusionspfaden;
- Layern;
- Konturen;
- Komponenten;
- 3D-Topologie;
- Feature-Rollen;
- geometrischen Formen;
- Pattern;
- Objektzuordnungen.

Die Grenzen der Rekonstruktion müssen sichtbar bleiben.

28.2 Vorhandene Engine vollständig untersuchen

Die bestehende _GeomScan-Implementierung und alle damit verbundenen
Hilfsfunktionen müssen vollständig inventarisiert werden.

Insbesondere:
- leichter und schwerer Analysepfad;
- modale Zustandsführung;
- Bewegungsrekonstruktion;
- Extrusionsberechnung;
- MAXRATE;
- MAX_PTS;
- Seam-Startpunkte;
- Extrusionspolylinien;
- geschlossene und offene Konturen;
- Konturverschachtelung;
- Point-in-Polygon;
- Außen-/Innenwand;
- Hatch- und Infill-Auswertung;
- Layer-Bitmap;
- Materialprüfung auf beiden Seiten;
- gekrümmte Pfade;
- Support-Kandidaten;
- Bridge-Kandidaten;
- Top-Surface-/Solid-Infill-Abgrenzung;
- Brim-Erkennung;
- Vase-/Spiralmodus;
- Feature-Sequenzen;
- Coverage-Statistiken;
- CUSTOM-Watch.

Die neue Architektur soll diese vorhandene Arbeit nutzen und
schrittweise modularisieren.

28.3 Zielarchitektur – sieben Schichten

SCHICHT 1 – G-Code-Interpreter
- Syntaxanalyse;
- strukturierte Befehle;
- Kommentare und Metadaten;
- Slicer-Dialekte.

SCHICHT 2 – Modal State und Bewegungsrekonstruktion
- absolute/relative Koordinaten;
- Einheiten;
- Tool-/Extruderzustände;
- Positionen;
- Extrusion;
- Retract;
- Bögen;
- Feedrate.

SCHICHT 3 – Geometrie-Rekonstruktion
- Pfade;
- Polylinien;
- Konturen;
- Polygonhierarchie;
- Raster;
- lokale Geometrie.

SCHICHT 4 – Layer-Modell und 3D-Topologie
- Layer;
- variable Layerhöhen;
- Materialstützung;
- Überhänge;
- Hohlräume;
- räumliche Kontinuität.

SCHICHT 5 – Feature-Klassifizierung
- Wand;
- Infill;
- Surface;
- Support;
- Bridge;
- Brim;
- sonstige Feature-Rollen;
- Slicer-Tag-Provenienz.

SCHICHT 6 – Pattern- und Confidence-Engine
- Infill-Muster;
- Oberflächenmuster;
- Evidenz;
- Widersprüche;
- Konfidenz;
- UNKNOWN/AMBIGUOUS.

SCHICHT 7 – R2-Adapter und Postprocessor
- bestehendes R2-Datenmodell;
- APPLY_TYPE;
- Marker;
- Dateiausgabe;
- Kompatibilität mit Live Tuning und weiteren Verbrauchern.

28.4 Pipeline – Pass 0 bis Pass 11

Die folgende Pipeline ist verbindlich als Architekturvorgabe zu
berücksichtigen:

PASS 0 – Rohdaten und Kommentare
Originalzeilen, Kommentare, Slicer-Tags, Metadaten, Zeilennummern
und Quellkontext erfassen.

PASS 1 – Syntax und Modal State
Befehle parsen, Koordinatenmodi, Einheiten, Extrusionsmodi,
Toolzustände, Offsets und Resets rekonstruieren.

PASS 2 – Bewegungsrekonstruktion
Start-/Endpositionen, Bögen, Extrusion, Travel, Retract und Feedrate
in normalisierte Bewegungssegmente überführen.

PASS 3 – Layer- und Z-Struktur
Layergrenzen, Z-Verlauf, variable Layerhöhen und Z-Hop unterscheiden.

PASS 4 – Extrusions- und Kinematikprofile
Extrusionsvolumen, Flow, Geschwindigkeit, Beschleunigung, Linienbreite
und Materialfluss untersuchen.

PASS 5 – Pfad- und Komponentenbildung
Zusammenhängende Pfade, Polylinien, Konturen, Komponenten, Inseln
und Featuregrenzen bilden.

PASS 6 – 2D-Geometrie pro Layer
Polygone, Bounding Boxes, Hüllen, Offsets, Rasterbilder,
Innen-/Außenbereiche und Hohlräume rekonstruieren.

PASS 7 – Inter-Layer- und 3D-Topologie
Materialstützung, Überhänge, freie Spannweiten, Support-Gaps,
Hohlräume und räumliche Kontinuität untersuchen.

PASS 8 – Feature-Klassifikation
Wände, Infill, Surface, Bridge, Support, Brim und weitere Rollen
klassifizieren.

PASS 9 – Pattern-Erkennung
Geometrie, Kinematik und Layerbeziehungen zur Mustererkennung nutzen.

PASS 10 – Konsistenzprüfung
Widersprüche, unmögliche Sequenzen, Alternativhypothesen,
Ambiguität und Datenqualität untersuchen.

PASS 11 – R2-Ausgabe und Postprocessing
Ergebnisse in das bestehende R2-Modell überführen, Tags/Berichte
ausgeben, Original schützen und Änderungen nachvollziehbar halten.

28.5 Parser und Modal State

Folgende Befehle und Zustände sind ausdrücklich zu behandeln:

- G90 / G91;
- M82 / M83;
- G92;
- G20 / G21;
- G0 / G1;
- G2 / G3;
- Tool-Wechsel;
- getrennte Extruderzustände;
- Feedrate;
- Retract / Unretract;
- Z-Hop;
- Koordinatensysteme;
- Offsets;
- Einheiten;
- mehrere Extruder;
- Slicer- und Firmware-Dialekte.

Fehlende Achsenwerte dürfen nicht als Null interpretiert werden.
Relative Bewegungen müssen auf dem letzten Zustand aufbauen.
G92 ist ein Zustandsreset und keine physische Bewegung.

28.6 Geometrie und Topologie

Die Geometrieanalyse muss mehr berücksichtigen als die Form einzelner
Linien.

Zu untersuchen:
- XY- und XYZ-Längen;
- Extrusionsvolumen;
- Querschnitt;
- Linienbreite;
- Konturschluss;
- Konturhierarchie;
- Bounding Box;
- Convex Hull;
- Offsets;
- Distanzen;
- Flächenabdeckung;
- Dichtekarten;
- Materialstützung;
- Layer-Boolean-Operationen;
- lokale Überhänge;
- freie Spannweiten;
- Support-Gaps;
- Hohlräume;
- Kanäle;
- mehrere Inseln;
- Wandkontinuität.

28.7 Feature, Geometrieform und Pattern trennen

Beispiele:

Feature:
INFILL-SPARSE

Geometrie:
CURVED_OPEN_PATH

Pattern:
UNKNOWN

Eine geometrische Form darf nicht automatisch als bestimmtes
Infill-Pattern interpretiert werden.

28.8 Feature-Taxonomie und Slicerfamilien

Die Original-Aliaslisten und Feature-Tabellen müssen aus den
bereitgestellten Quellen übernommen werden.

Mindestens zu untersuchende Slicerfamilien:
- Slic3r;
- PrusaSlicer;
- SuperSlicer;
- SliceBeam;
- OrcaSlicer;
- Bambu Studio und Derivate;
- Cura/CuraEngine;
- Simplify3D;
- FlashPrint;
- ideaMaker;
- Kiri:Moto;
- KISSlicer;
- CraftWare;
- MatterSlice/MatterControl;
- IceSL;
- AstroPrint-Backends.

Unterstützung erst nach konkreten Fixtures deklarieren.

28.9 APPLY_TYPE und CUSTOM

Die vorhandene Canonicalisierung muss erhalten bleiben.

Zu prüfen:
- TYPE_MAP;
- Alias-Mapping;
- Groß-/Kleinschreibung;
- Leerzeichen;
- Unterstriche;
- Bindestriche;
- CamelCase;
- kanonische R2-Werte;
- Support-Sonderbehandlung;
- CUSTOM-Eliminierungsleiter;
- C1–C9-Gruppen;
- Featuregrenzen;
- APPLY_TYPE;
- CUSTOM-Watch;
- Cross-Layer-Regeln;
- Konflikt- und Unmöglichkeitsprüfung.

Keine freien Fuzzy-Zuordnungen ohne belastbare Evidenz.

Unbekannte Begriffe bleiben CUSTOM bzw. UNKNOWN, solange keine
nachvollziehbare Zuordnung möglich ist.

28.10 Confidence und Provenienz

Je Klassifikation möglichst dokumentieren:
- Ergebnis;
- Score;
- Evidenz;
- widersprechende Evidenz;
- Alternativhypothesen;
- Regelversion;
- Datenqualität;
- Provenienz;
- Grund für UNKNOWN/AMBIGUOUS.

Ein heuristischer Score ist keine statistisch kalibrierte
Wahrscheinlichkeit.

28.11 Tests und Ground Truth

Pflicht:
- Golden Master;
- reale G-Code-Fixtures;
- ungetaggte und getaggte Varianten;
- Slicerfamilien;
- Parser- und Modal-State-Tests;
- Bewegungs- und Geometrietests;
- Layer- und Topologietests;
- Feature- und Pattern-Tests;
- CUSTOM-/APPLY_TYPE-Tests;
- Sequenztests;
- beschädigte und unvollständige Dateien;
- Laufzeit- und Speicherlimits;
- Determinismus.

Wenn Ground Truth vorhanden ist, Precision, Recall, F1 und
Confusion Matrix berechnen.

28.12 Sicherheitsgrenze

Erste Entwicklungsstufen dürfen nur Diagnoseberichte oder
nicht ausführbare Kommentare erzeugen.

Keine ausführbaren Bewegungen, Extrusionen, Temperaturen,
Geschwindigkeiten oder Beschleunigungen verändern, solange dies nicht
separat spezifiziert und freigegeben wurde.

======================================================================
29. ERGÄNZUNG: VOLLSTÄNDIGE ANFORDERUNGS- UND MIGRATIONSDISPOSITION
======================================================================

Die neue Coding-KI muss alle Inhalte dieses Briefings und der
Originalquellen in einem nachvollziehbaren Anforderungsregister
zusammenführen.

Für jeden Punkt unterscheiden:

- ursprüngliche Nutzeranforderung;
- technische Interpretation;
- vorhandene Implementierung;
- nachgewiesener Funktionsstatus;
- technische Lücke;
- Zielarchitektur;
- Abhängigkeiten;
- Risiken;
- Test- und Abnahmekriterien;
- Freigabestatus.

Mögliche Disposition:
- PRESERVE: bestehende Funktion unverändert erhalten;
- INTEGRATE: in die Zielarchitektur integrieren;
- REFACTOR: Implementierung kontrolliert umbauen;
- SEPARATE: als eigenständiges Modul führen;
- DEFER: wegen Abhängigkeiten zurückstellen;
- MERGE: mit einer anderen Anforderung zusammenführen;
- OBSOLETE: als überholt bewerten, aber nicht ohne Freigabe löschen;
- INVALID: als technisch nicht umsetzbar oder nicht zutreffend
  begründet kennzeichnen;
- CONFLICT: widersprüchliche Anforderungen zur Entscheidung vorlegen;
- VERIFY: vorhandene Funktion oder behaupteten Fix erst nachweisen.

Jede Disposition muss begründet und zur ursprünglichen Quelle
zurückverfolgbar sein.

Keine ursprüngliche Produktanforderung darf dadurch verloren gehen,
dass eine konkrete alte Implementierung ersetzt wird.

======================================================================
30. VERBINDLICHE PRIORITÄTEN FÜR DIE ERSTE ARBEITSPHASE
======================================================================

Die folgenden Punkte sind bei der Bestandsaufnahme ausdrücklich
zu berücksichtigen:

1. Vollständigkeit und Sicherheit der Projektübergabe.
2. Restore und Verifikation des tatsächlichen Projektstands.
3. Dokumentations-/Code-Abgleich.
4. Postprocessor und Reverse Engineering.
5. Parser und Modal State.
6. Bestehende _GeomScan-Funktionen und Regressionstests.
7. APPLY_TYPE, CUSTOM und Feature-Taxonomie.
8. Extrusionskompensation bei Geometrieveränderungen.
9. Texture-Innenwandführung und Wandstärkenerhalt.
10. Range-Fehler und Regression.
11. STL-/OBJ-Export und dessen bisherige Fehler.
12. Gemeinsames Objektmodell.
13. Queue, Dateiverwaltung und Ausgabemodi.
14. Toolchain-Architektur.
15. Hardware-, LCD-, WebUI- und Stabilitätsprüfung.
16. Backlog-Disposition und Zielarchitektur.

Diese Reihenfolge ist eine Orientierung für Analyse und Planung.
Sie ist keine pauschale Freigabe, mit der Implementierung zu beginnen.

======================================================================
31. ABSCHLIESSENDE ANWEISUNG AN DIE NEUE CODING-KI
======================================================================

Du übernimmst ein gewachsenes Projekt mit erheblicher vorhandener
Entwicklungsarbeit.

Du darfst nicht so tun, als sei das Projekt neu.

Du darfst nicht allein aus Dokumentation schließen, dass eine Funktion
im Code vorhanden oder funktionsfähig ist.

Du darfst nicht allein aus einer vorhandenen Datei schließen, dass
eine Funktion korrekt arbeitet.

Du musst Quellcode, Dokumentation, Historie, Tests und reale
Ausgabeergebnisse gegeneinander prüfen.

Du musst die ursprünglichen Nutzeranforderungen erhalten, auch wenn
du eine technische Implementierung später ersetzen möchtest.

Du musst jede Unsicherheit und jede technische Grenze sichtbar machen.

Du musst bei G-Code-Reverse-Engineering zwischen rekonstruierbarer
Bewegung, geometrischer Interpretation und semantischer Absicht
unterscheiden.

Du musst bei Generatoren und Pre-Print-Werkzeugen Originaldateien
schützen, abgeleitete Dateien nachvollziehbar verwalten und den
physischen Druckstart immer dem Nutzer überlassen.

Du musst bei allen Hintergrundarbeiten die Druckpriorität und die
Stabilität des Klipper-Hosts berücksichtigen.

Du musst vor Änderungen einen vollständigen Bericht und einen
prüfbaren Migrationsplan vorlegen.

DEIN VERBINDLICHER ERSTER SCHRITT:

1. Alle verfügbaren Quellen identifizieren.
2. Die vollständige Übergabe lesen.
3. Den tatsächlichen Git- und Projektstand sichern.
4. Die vorhandene Implementierung vollständig inventarisieren.
5. Alle Anforderungen aus diesem Dokument und den Originalquellen
   in ein Anforderungsregister überführen.
6. Die vorhandenen Funktionen gegen die Anforderungen prüfen.
7. Fehler, Risiken, offene Fragen und fehlende Quellen dokumentieren.
8. Eine Zielarchitektur und einen phasenweisen Migrationsplan vorlegen.
9. Eine vollständige Backlog-Disposition erstellen.
10. Auf ausdrückliche Freigabe warten.

KEINE EIGENMÄCHTIGE IMPLEMENTIERUNG VOR DER FREIGABE.

LIES ALLES.
SICHERE ALLES.
VERSTEHE DEN BESTAND.
ERHALTE DIE ANFORDERUNGEN.
PLANE DIE MIGRATION.
WARTE AUF FREIGABE.

