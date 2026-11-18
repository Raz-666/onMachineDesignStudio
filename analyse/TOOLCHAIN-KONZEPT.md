# Toolchain-Architektur (Gesamtbriefing §20/§22) — Konzept und Phasenplan

**Status:** Phase 1 umgesetzt (`tools/toolchain.py` + `tools/test_toolchain.py`,
21 Tests). Dieses Dokument ist der vom Gesamtbriefing §20.5 geforderte
Architektur- und Phasenvorschlag — belegt gegen Code, nicht gegen Doku.
Kein Werk der Phase 2–4 ist freigegeben oder umgesetzt; nichts hier greift
in den Druckpfad ein.

---

## 1. Auftrag

Gesamtbriefing §20 („Zentrale Toolchain-Architektur"): mehrere Pre-Print-
Werkzeuge und Generatoren sollen zu einer geordneten Verarbeitungskette
kombiniert werden — jedes Werkzeug baut auf der Ausgabe des vorherigen auf
(§20.1), die Originaldatei bleibt unverändert (§20.2), Zwischenstände sind
temporär und nur so lange gültig, bis der Nachfolger sie übernommen hat
(§20.3/§22.4), Presets enthalten keine fest verdrahtete Eingabedatei (§20.2)
und werden beim Laden auf die aktuell ausgewählte Datei angewendet. Drei
Ebenen (§20.5): Tools / Toolchains / Toolchain-Presets. Die frühere UI-Demo
war ausdrücklich nur ein Interaktionsmodell (§20.4) — hier wird nichts als
fertig behauptet, was nicht existiert.

## 2. Ist-Stand im Code (das Fundament ist vorhanden)

| Baustein | Fundstelle | Bedeutung für die Toolchain |
|---|---|---|
| Trigger-Kette | LCD/Makro → `SAVE_VARIABLE` → Moonraker → Watcher-Poll in `r2_postproc.py` | Ein Toolchain-Start braucht KEINEN neuen Mechanismus — derselbe Weg wie bei jedem Generator |
| Job-Queue, ein Worker | `_spawn_job` (`r2_postproc.py:25949`), `_JOB_STATE` (Key-Dedupe, „one job at a time") | §22.2 Druckpriorität ist bereits Durchsetzung, nicht Absicht: nichts läuft parallel |
| Job-Lifecycle | `JobRegistry.enqueue(name, key, ram_min_mb=60)` (`r2_job_service.py:406`), Zustände, `outputs`/`validation`-Listen pro Job | §22.1-Zustandsmodell existiert; Success-Kriterien (Datei existiert, lesbar, geprüft, registriert) sind ansatzweise die bestehende Ausgabevalidierung |
| RAM-Gates | R223: `ram_min` 60/110 MB je Jobtyp (`.136s`-Feldlog: Photo-Build kollabierte den Host) | Toolchains dürfen die Gates nicht aushebeln — jede Stufe bleibt ein eigener gegateter Job |
| Host-Schutz | `nice`, R148-Watcher-CPU-Fix, Shutdown-Register #6 („eine Job-Queue, ein Worker") | Die historischen „Timer too close"-Fälle aus Hintergrundlast sind genau der Nicht-Verhandlungspunkt von §22.2 |
| Ausgabemodi | `_GEN_OUT_SET OUT=…` (`08_print_start_stop.cfg:718`, `12_maintenance.cfg:2175/2313`; QUEUE/PREVIEW/… via MANUAL Kap. 18) | §21-Ausgabemodi existieren je Generator; eine Toolchain braucht denselben Schalter einmal für die Kette |
| Versionierung/Ordner | `Vnn_…`-Konvention; Cake legt nach `Cake/` ab (H3) | Namensvertrag für Zwischenstände: `V01_…`, `V02_…` je Stufe, Ordner `Toolchain/` (Vorschlag) |
| Beispiel-Werkzeugvertrag | `make_range(src, start, end, floor, top, brim, …)` (`r2_postproc.py:1937`) | Zeigt die Werkzeugform: benannte Parameter, prüfbar, Ausgabe neben der Quelle |

## 3. Der Vertrag von Phase 1 (`tools/toolchain.py`)

- **Preset-Schema `r2-toolchain/1`:** `{schema, name, description?, steps:[{tool,
  params}]}`. §20.2 wird **erzwungen**: Schluessel wie `input/file/src/path`
  sind in jeder Ebene (Preset, Schritt, Parameter) kategorisch verboten —
  Orakeltest prüft genau das.
- **Tool-Registry (quellenbelegt):** `range` (make_range:1937; start/end/
  floor/top/brim, Querschnittsregel start≤end), `scale` (lcd_menues.cfg:3883:
  X/Y 25–300 %, Top 0–300 %), `texture` (17_generator.cfg:1179: 27 Muster-
  Codes; LCD-Bereiche Around 3–80, Height 0.5–200, Depth 0.05–1.0 mm,
  Richtung IN/OUT, Seed). Multi-Output-Werkzeuge (Cake `PART=BOTH` → zwei
  Dateien) werden in Ketten **abgelehnt**, bis die Verzweigungssemantik
  geklärt ist — sie wird nicht erfunden.
- **Validierung:** Typen (bool ist kein int — Python-Falle getestet), Minima/
  Maxima, Enums, Pflicht-/Optionalparameter mit Defaults, Querschnittsregeln,
  Schrittanzahl ≤ 16. Fehler sind Klartext mit Schrittbezug.
- **Plan (`r2-toolchain-plan/1`):** reine Planung — Job N bekommt die Ausgabe
  von Job N−1 als Eingabe, Ausgaben `Vnn_<stem>.gcode` im Ordner `Toolchain/`
  (Vorschlag), Zwischenstände `temp: true`, jede Folge-Stufe trägt
  `requires: validierte Ausgabe von Job N`. **Nichts wird ausgeführt, keine
  Datei geschrieben.**
- 21 Orakel-Tests (`tools/test_toolchain.py`), komplett offline.

## 4. Phasenplan

- **Phase 1 (dieser Stand):** Vertrag + Planung als experimentelles Modul.
  Kein Anschluss an Watcher/Queue/Makros.
- **Phase 2 — Ausführungs-Engine:** Registry-Vollständigung durch Extraktion
  aus den Menü-Daten (`tools/menu_json_export.py` ist die Quelle der Wahrheit
  für Werkzeuge + Wertebereiche, kein zweites Pflegen). Eine Toolchain wird
  als Folge abhängiger Jobs in der BESTEHENDEN Queue abgearbeitet: Job N+1
  startet erst nach Validierung von Job N, Temp-Löschung erst nach Übernahme,
  Fehler-Stufen bleiben nachvollziehbar (§22.4). Ausgabemodus-Schalter für
  die Gesamtkette (§21). Eigene Testbatterie + Gates.
- **Phase 3 — Bedienoberfläche:** LCD `Pre-Print > Toolchain` (Preset wählen,
  auf ausgewählte Datei anwenden, Fortschritt je Stufe); das Web-LCD spiegelt
  automatisch (Menü-JSON-Spiegel, gleiche Makros — kein zweites Frontend).
  Preset-Verwaltung: speichern/laden/löschen am LCD.
- **Phase 4 — Queue-Abhängigkeit & Doku:** §22.3 (Druckstart wartet auf
  Job-Fertigstellung, Nutzer sieht den wahren Zustand), MANUAL-Kapitel,
  Toolchain-Presets im Backup/Paket.

Jede Phase endet mit Commit + Tests + Bericht; kein Sprung ohne grüne Gates.

## 5. Kompatibilität und Host-Schutz (der entscheidende Rand)

- **Drucker-Unabhängigkeit:** Die Toolchain läuft vollständig auf dem Host
  (Python, keine neuen Abhängigkeiten in Phase 1). Die Werkzeuge selbst sind
  bereits maschinenparametrisch (Generator-Matrix `r217_gen_matrix.py`:
  Generator × Düse × Bett, 1423 Checks) — eine Kette erbt das.
- **Druckpriorität (§22.2) bleibt unangetastet:** eine Queue, ein Worker,
  RAM-Gates je Stufe, `nice`. Eine Toolchain verlängert die Hintergrundlast,
  sie erhöht NIEMALS die Parallelität — genau die Lehre aus dem Shutdown-
  Register („Timer too close" kam aus Host-Schüben, nie aus dem MCU).
- **Pi Zero 2 W-Budget:** Beide neuen Recherchen (Gießformen, KI-Brücke)
  warnen zu Recht vor schwerer Geometrie auf dem Host. Regel für Phase 2+:
  was auf dem Host rechnet, läuft als gegateter Queue-Job; was zu schwer ist
  (Boolean-Meshes, Slicen), gehört auf einen externen Dienst (siehe J6) oder
  bleibt außerhalb.
- **Ein Funktionskern, viele Oberflächen (§10):** die Kette wird über
  Makros/`SAVE_VARIABLE` gesteuert — LCD, Web-LCD und Konsole bedienen
  dieselbe Logik ohne zweite Geschäftslogik.

## 6. Offene Punkte (nicht erfunden, sondern benannt)

1. Multi-Output-Werkzeuge in Ketten (Cake-Verzweigung): Semantik klären —
   gilt die Folge für beide Hälften? Wahl pro Zweig?
2. Werkzeug-Kompatibilitätsregeln über Parameter hinaus (z. B. Textur nach
   Range auf Boden/Deckel): in Phase 2 aus den echten Werkzeugverträgen
   ableiten, nicht raten.
3. Abbruch semantik einer laufenden Kette (§22.1 `cancelled`): Rest-Stufen
   verwerfen, aber abgeschlossene Ausgaben behalten — UX-Entscheidung.
4. Preset-Format für die LCD-Verwaltung (Name, Beschreibung, Schrittliste
   als Klartext) — Phase 3.
