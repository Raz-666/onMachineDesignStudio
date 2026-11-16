#!/usr/bin/env python3
"""Vorschlagsmatrix aus dem einzigen Master-TODO; schreibt nur analyse/."""
import csv,re
from pathlib import Path
R=Path(__file__).resolve().parents[1]
s=(R/'docs-notes/MASTER-TODO.md').read_text()
pat=re.compile(r'^- \[([ x])\] \*\*([A-H]\d+)(?:\s+[—–-]|\s*—)(.*?)\*\*(.*?)(?=\n- \[[ x]\]|\n## |\Z)', re.M|re.S)
# Kategorie | Prio | Komponente | Abhängigkeit | Vorschlag/Ist | Abnahme | Beleg
D={
'A1':('Erledigt unverifiziert','P1','LCD/Dateien','Dateischutz','Symlink-Konzept im Bestand; reale Ordnerauswahl und Kollisionen offen','alle Outputs auswählen ohne Quelle zu überschreiben','MASTER-TODO:11; Generatorbericht'),
'A2':('Konflikt/technische Klärung','P1','Live/Ironing','Override-Setter','Anzeige im Menü belegt; Wertwirkung wegen skalarem Flag gesondert prüfen','angezeigter und tatsächlich wirksamer Flow stimmen','override_bedienpfade_probe.log'),
'A3':('Erledigt unverifiziert','P1','Quality/Speed Fix','Geometrie/Golden','UI queuet richtige Namen; geometrische Verhaltensgarantie nicht abgenommen','Travel/Surface/Retract/Hop/Ironing mit Orakel','macro_render_test.log:1130'),
'B1':('Erledigt unverifiziert','P2','LCD Live','Web-Sync','vier Listen direkt unter Live laut Rendercheck','am LCD/Web alle erreichbar','macro_render_test.log:652'),
'B2':('Erledigt unverifiziert','P2','LCD Live','B1','Features-Zweig entfernt laut Tests; keine unbelegte Funktionsgleichheit','alle nötigen Werte/Flags über Schnellzugriff erreichbar','macro_render_test.log:641-653'),
'B3':('Erledigt unverifiziert','P3','LCD Live','B1','Titel vorhanden laut Backlog; Sichtbarkeit real offen','vier Titel bei realem Display','MASTER-TODO:43'),
'B4':('Erledigt unverifiziert','P3','LCD Live','B1','Duplikate laut Rendercheck entfernt','keine Doppelzeile; Einstellung erreichbar','macro_render_test.log:639'),
'B5':('Beibehalten','P1','Live Feature','Feature-Flags','Zero-Deaktivierung abgelehnt; FeatOn erhalten','0 nicht als generischer OFF-Schalter; ON/OFF geprüft','MASTER-TODO:47; macro_render_test.log:1075'),
'G1':('Wegen Abhängigkeit zurückstellen','GESPERRT','Textur','separate Freigabe','keine neue Arbeit; Originalforderung erhalten','nur nach Freigabe Materialstruktur anhand echter Algorithmen prüfen','MASTER-TODO:80'),
'G2':('Wegen Abhängigkeit zurückstellen','GESPERRT','Textur Tilt','separate Freigabe','keine Änderung oder neue Prüfung','erst nach Freigabe Tilt-Entscheid und Regression','MASTER-TODO:86'),
'G3':('Wegen Abhängigkeit zurückstellen','GESPERRT','Textur Presets','G1/Freigabe','Presets nicht ändern','Mapping und Parameter pro akzeptiertem Muster','MASTER-TODO:89'),
'G4':('Wegen Abhängigkeit zurückstellen','GESPERRT','Textur Abtastung','G1/Freigabe','keine Implementierung','Wand und E-Erhalt auf Vase und weiteren Korpora','MASTER-TODO:92'),
'G5':('Wegen Abhängigkeit zurückstellen','GESPERRT','Geometriegenerator','separate Freigabe','Regressionsprüfung gesperrt; gemischter r217-Lauf gestartet und abgebrochen; genaue Ausführung unbekannt','nach Freigabe Form/Geometrie regressiv prüfen','MASTER-TODO:95; r217_current.log'),
'H1':('Erledigt unverifiziert','P1','Range/Cake','H2','synthetischer Guard besteht; kein Hardwarebeweis','inkonsistenter Schnitt wird erklärt verweigert, valide Range bleibt nutzbar','v1_range.log 8/8'),
'H2':('In Zielarchitektur integrieren','P1','Cake/Layer','Modalzustand/Layervertrag','Markerreparatur noch offen; keine reine Guard-Lösung','Schnittstruktur und Layerverbraucher korrekt und reproduzierbar','MASTER-TODO:113; Schichtbericht'),
'H3':('Konflikt/technische Klärung','P2','Cake UX','Nutzerentscheidung','Platten/Reorient/Restmaterial nicht entschieden','Spezifikation anhand konkreter Beispiele akzeptiert','MASTER-TODO:117'),
'C1':('In Zielarchitektur integrieren','P1','Postprozessor','Originalschutz/Shadow','TAG-Frühabbruch belegt; Rewrite kann vorher Datei ändern','Tags diagnostisch vergleichen ohne Bewegungsänderung','rekonstruktionsproben.log'),
'C2':('In Zielarchitektur integrieren','P1','Layer/Geometrie','Objekte/Ground Truth','globale Regeln können bei mehrteiligen Modellen falsch warnen','Regel pro Einheit; Kontexte und Gegenbeispiele validieren','field_fixture_probe.log; Masterkonzept'),
'C3':('In Zielarchitektur integrieren','P1','Brim/Objekte','Objektidentität','Brim erster Layer der Einheit, nicht der ganzen Datei','Layer-23-neue Einheit und höhergezogener Brim unterscheiden','MASTER-TODO:133; Feldfixture'),
'C4':('Wegen Abhängigkeit zurückstellen','P1','Slicer-Aliase','fehlende slicer-families.md','vorhandene Union ist kein Ersatz für fehlendes Original','versionierter Dialektkorpus und Ausschlusskriterien','ALIASE-QUELLEN-CODE.tsv; r110.log'),
'C5':('In Zielarchitektur integrieren','P1','Watcher/Diagnose','C1-C4, Laufzeitbudget','keine generelle abgesicherte Echtzeit-Gegenprüfung belegt','Widerspruch meldet Evidenz ohne Eingriff in Druck','Masterkonzept; r255.log'),
'D1':('Erledigt unverifiziert','P2','Handbuch','Lüfterentscheidung','Indexprüfungen gelaufen; Kap14 LIVE-Lüfter offen','Dokutext und tatsächliche Kette abgeglichen','r265.log; MANUAL-CODE-ABGLEICH.md'),
'D7':('Konflikt/technische Klärung','P2','PDF-Fundament','D7d/Textursperre','D7a-c vorhanden; D7d und Textur-Rückteil explizit gesperrt; Checkbox widersprüchlich','Fundament+Inhalt getrennt abnehmen; kein Textur-Rückteil vor Go','MASTER-TODO:156-178'),
'D2':('Wegen Abhängigkeit zurückstellen','GESPERRT','Textur-PDF','G1-G4 und Freigabe','kein Eingriff an Texturmaterial','Abbildungen aus finalem echtem Algorithmus/Parametern','MASTER-TODO:179'),
'D3':('Wegen Abhängigkeit zurückstellen','P3','Generator-Doku','Inventar/validierte Funktion/G-Sperre','Bedarf erhalten; keine pauschale Abnahme vorhandener PDFs','pro Generator Parameter, realer Algorithmus und Beispiele','MASTER-TODO:181; Generatorbericht'),
'D4':('Wegen Abhängigkeit zurückstellen','P3','Modifier-Doku','D3/geprüfte Mathematik/G-Sperre','keine PDF-Produktion','Formeln und Bedienung durch reale Ergebnisse geprüft','MASTER-TODO:184'),
'D5':('Wegen Abhängigkeit zurückstellen','P3','Kreativ-Doku','D3/D4/G-Sperre','Kreativ-PDF vorhanden, Erfüllung der Originalforderung nicht abgenommen','Ketten/Fehlersuche und gewünschter Schlusssatz prüfen','MASTER-TODO:186'),
'D6':('Beibehalten','P1','Alle Dokumente','Datenherkunft','verbindliche Regel statt separate einmalige Aufgabe','jeder Bildinhalt aus echtem Algorithmus und echten Parametern','MASTER-TODO:190'),
'E1':('Konflikt/technische Klärung','P0','Probe/Host/MCU','Feldlog/Hardwarefreigabe','historische Behauptung nicht unabh. geprüft; Probe und Reactor getrennt untersuchen','ohne Bewegung zuerst Konfiguration/Log; später beaufsichtigte Sicherheitsprüfung','MASTER-TODO:196; r255/r257'),
'E2':('Erledigt unverifiziert','P1','Input Shaper','Hardwarekonfiguration','manueller Pfad beschrieben, kein Maschinennachweis','Override/Restore/kein Sensor auf geeigneter Testinstanz','MASTER-TODO:210'),
'E3':('Erledigt unverifiziert','P0','LED/Probe','E1','statischer und mutierter Guard-Test grün; Drucker offen','LED-Zustand und Queue/Last bei echtem Homing nach Freigabe','r257.log 15+7'),
'E4':('Konflikt/technische Klärung','P0','Probe/Z-Limit','E1 und Nutzerfreigabe','-2 nur Vorschlag, keine Änderung an realer printer.cfg','Homing/Probe mit verifizierter Maschine und sicherem Verfahren','MASTER-TODO:233'),
}
rows=list(pat.finditer(s)); found={m.group(2) for m in rows}
assert found==set(D), (sorted(found-set(D)), sorted(set(D)-found))
out=R/'analyse/BACKLOG-DISPOSITION.tsv'
with out.open('w',encoding='utf-8',newline='') as f:
 w=csv.writer(f,delimiter='\t'); w.writerow(['ID','Quelle_Zeile','Checkbox','Originalforderung','Kategorie_Vorschlag','Prioritaet','Komponente','Abhaengigkeiten','Ist_und_Empfehlung','Erhaltene_Anforderung','Ersatz_oder_Umsetzung','Akzeptanzkriterium','Testbeleg_oder_Grenze'])
 for m in rows:
  status,id,title,rest=m.groups(); line=s[:m.start()].count('\n')+1
  original=' '.join((title+rest).split()); category,priority,comp,dep,recommend,accept,evidence=D[id]
  w.writerow([id,f'docs-notes/MASTER-TODO.md:{line}',status,original,category,priority,comp,dep,recommend,'Originalforderung unverändert, siehe Originalforderung','Vorschlag: Bestand erhalten und im zugeordneten Modul prüfen; keine Umsetzung beschlossen',accept,evidence])
print(f'{len(rows)} einzeln disponierte IDs -> {out.relative_to(R)}')
