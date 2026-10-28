# R186/R187 — Release .133 Report
**Datum:** 2026-10-28 · **Basis:** HEAD `107f831` (R185/.132) → .133
**Status: alles uncommitted bis zum Final-Commit; Batterie komplett grün (siehe unten).**

---

## 1. Deine vier Feldmeldungen — was daraus wurde

### 1.1 Range-Makro: „Top wird nicht gedruckt" (Outline UND Footprint) — GEFIXT (R186)
**Ursache:** Der „ist diese Range schon frisch erzeugt?"-Check (`_pat62`) ignorierte
die Parameter — zusammen mit dem R186-Primed-Mechanismus (`_freeze133`/`_core_stamp`)
konnte ein Re-Fire nach dem Boot den Job fälschlich als erledigt betrachten und den
Top-Wiederholungs-Pass komplett überspringen.
**Fix:** Skip-Komplett-Entfernung (R160b-Naming bleibt). Neuer Drill pro Druck.
**Beweis:** Verifikationsmatrix über 8 Kombinationen (Outline/Footprint × mit/ohne
Loch × Floor-Varianten) — Top-Layer in allen Fällen vorhanden, Z-Histogramm sauber.

### 1.2 „Lücke kurz vor Druckende, letzte Schichten in der Luft" — GEFIXT (R187)
**Ursache:** Der Z-Scan in `make_range` lief bereits beim ersten Body-Start-Z vorbei:
`z0`/`z_end_body` zeigten auf Nachbar-Layer, der Cap-Aufbau (`(z_end_body − dz) +
(i+1)·lh`) erzeugte eine ~0.4mm-Lücke + Extrusionen mit Z=None im 3D-Viewer.
**Fix:** Pass-A-Tracker (`_pre_z187`, `_z_eff187`, `_z_first_ext187`/`_z_last_ext187`,
`_z_in_body_z187`) — z0/z_end_body sind jetzt das Z, das bei der ERSTEN/LETZTEN
Body-Extrusion wirksam ist; Pass B (`_a_eff187`) entscheidet den pre_a-Segmentstart.
**Beweis:** Extrusions-Z-Histogramm (curz-Tracking) über 8 Kombis: None:0, keine
Lücke >0.33mm, Z-Staffel exakt 0.2…1.6 (+1.8 mit Floor). r81 danach 23/23
byte-identisch.

### 1.3 Textur-Höhenverlust — GEFIXT (R186, r2_texture.py)
Der Emissions-Pass trackte Z nicht: Muster wurde auf Höhe 0 gerechnet, Z-Variation
ging verloren, Z-lose Dateien waren stilles No-Op. Jetzt: `cur_z_e`-Tracking für
G0/G1+Arcs, `_shift_txt`-Fallback, BUMPS ohne Z → lauter `ValueError` (nie wieder
still). Beweis: 16-Eck mit Layer-Z — Versätze wie designed.

### 1.4 Browser: „nur eine Seite / nicht alle Dateien" — GEFIXT + BEWESEN
Forensik-Ergebnis (kein Reload-Beweis möglich, aber jede Komponente gemessen):
- **sd_tree ist vollständig:** Fake-Moonraker-Test mit 120 Dateien in einem
  Unterordner → alle 120 im Baum (keine 40er-Kappe im Baum!), Push ~3.5KB —
  kein Größenproblem bei realistischen Karten.
- **Paging-Mathematik korrekt:** `maxp=(len−1)//40`, `__pgu` genau dann sichtbar,
  wenn die aktuelle Seite voll ist; 40 LCD-Slots vorhanden; Listen scrollen.
- **Die echte Kappe war die Gen-files-Liste:** 12 Slots + `[:12]` im Watcher —
  ältere Generator-Dateien waren dort UNERREICHBAR. Jetzt **24 Select- + 24
  Delete-Slots**, Watcher pusht die 24 neuesten.
- Stale-Bäume nach fehlgeschlagenem Push werden seit R152 jeden Zyklus erneut
  geschoben (Cache zählt erst bei HTTP 200).

### 1.5 Browser-Sortierung (dein Wunsch) — IMPLEMENTIERT (R187)
- **Root:** Ordner zuerst (A–Z), dann Dateien A–Z (wie vorher — Finden statt grabbeln).
- **Unterordner:** **neueste Datei ganz oben** (mtime absteigend), Ordner danach A–Z.
- Gilt konsistent: der Watcher liefert die Ordnung im Baum, SDNAV_GO/UP/PAGE/HOME
  schneiden nur Seiten daraus, der View-Sync des Watchers ebenso.
- Alle Info-Texte (RESPOND, How-it-works, Header-Kommentare) auf den neuen Stand.

---

## 2. Kollisions-Audit (Dateinamen / strukturelle Kollisionen)

**Frage:** Kann generierter G-Code wegen Namensgleichheit nicht gespeichert werden?

**Antwort: Nein — Speichern schlägt nie fehl.** Jede Generator-Schreibstelle läuft
über Nie-Überschreiben (V-Nummer pro Ordner, nie wiederverwendet; Buchstaben-Varianten
V05b/V05c… zählen mit). Gefunden und gefixt wurden dabei drei Lücken:

| Fund | Risiko vorher | Fix (R187) |
|---|---|---|
| `apply_scale` nutzte den **rohen Quell-Stem** | `Dad's vase.gcode` → `Dad's vase_S120-100.gcode`: gespeichert, aber vom LCD-Browser **unsichtbar** (Quotes-Filter) | Stem wird sanitisiert (`[^A-Za-z0-9._-]`→`_`), leer→`MODEL`. Bewiesen: `Dad_s_vase_gro_S120-100.gcode` |
| `_dedupe_gen_fname` gab nach 26 Buchstaben (b..z) auf | 27. Kollision = **stilles Überschreiben** | Nach b..z weiter mit V06, V07… bis frei. Bewiesen: V05+b..z belegt → V06 |
| `make_range` hatte **kein** Dedupe-Netz | Race-Fenster (zwei Creates in einem Atemzug / manuell reingeworfene Datei) | `_dedupe_gen_fname` nachgezogen. Bewiesen: V01_Vase_L3-9 → zweiter Lauf V02 |

Namens-Quellen-Audit: alle V-Generatoren sanitisieren (Labels via
`_safe_label_name`, Quellen via `_gen_stem`, Interne numerisch); Range-Tag strippt
alles Nicht-Alphanumerische; Resonance/Ties/Bridge/Seal/PlotCal rein numerisch oder
intern. Strukturell: gleichlautende Namen unterschiedlicher Parameter tragen
unterschiedliche V-Nummern (LCD-Konvention seit R158: Nummer vorne, immer sichtbar).

**Bonus-Fund:** `make_frame(preset=…)` bei Tippfehler fiel **still** auf 148×210
zurück und redete später wirr von Split-Kits. Jetzt: klare Verweigerung mit der
kompletten Preset-Liste (`unknown frame preset 'xx99' - 9x13/10x15/13x18/A6/PASS/
MINI/4x5 or '' for custom W/H`). Custom-W/H (preset='') unverändert.

---

## 3. Vier-Augen-Pass: Tools & Generatoren auf Herz und Nieren

### 3.1 Verweigerungs-Sweep (11 Live-Proben, alle sauber)
scale 400% · scale No-Op · Range start>end · Range auf unprozessierter Datei ·
Textur ohne Outer-Wall/ohne Z · Litho Handle=1 · Litho STANDING+Stamp ·
Litho Bild fehlt · Labels leerer Text · Frame-Preset-Tippfehler (→ neuer Fix) ·
StringArt unbekanntes Muster. Jede Verweigerung nennt Grund UND den Ausweg
(z. B. „set Orient=FLAT first (LCD: Litho > Orient)").

### 3.2 Parameter-Variations-Hämmer (alle grün, siehe 5)
r140_stress (46.775 Checks), r187_matrix (1.356), megatest (190 Läufe),
r141_journeys (2.342, inkl. Journey F).

### 3.3 Feedback-/Informations-Flüsse (Auditiert, keine Lücke gefunden)
- **Job-Lebenszyklus:** Doppel-Druck → „already running or queued"; Warten →
  Grund („printer is busy…" / „only XmB RAM free — it builds when…"); Start →
  Chirp + M117; Abbruch → RESPOND ABORTED + Grund + Fehlerton; Fertig →
  Dateiname + Geometrie + Notizen + „selected for printing".
- **Während des Drucks:** Farbwechsel (M117 + RESPOND), Platten-Fortschritt
  („plate A of 2 done — next file: …"), Brücken-/Plotter-Pen-Hinweise.
- **Browser:** jede Navigation antwortet (Eintragszahl + Sortierungs-Hinweis,
  jetzt mtime-bewusst formuliert).
- **Stille-Wächter:** Stale-Daemon-Sirene (R166), File-Check/Re-Fix mit
  Zwei-Druck-Armierung, Versionierungs-Regeln (nie Überschreiben) mit
  LCD-erklärtexten.

### 3.4 Aufgeräumt
- `tools/r95_featext.py` retiriert (One-Shot-Migrationsgenerator 12→16 Codes,
  keine Referenzen mehr im Repo/Docs).
- `r167_aircheck` hing an `/home/user/uploads/Bun2.jpg` (Opfer der
  Workspace-Bereinigung) → synthetisches Referenzfoto, überall lauffähig.
- `r168_stampcheck` nutzte `handle=1` für Litho (vor-R170-API) → `handle=2`
  (separate Griffdatei — genau das, was der Test ohnehin liest).
- `r142_spell_lint`: Whitelist um legitime Fachwörter ergänzt (img, zsize,
  re-fix, …). **Hinweis:** braucht `pip install pyspellchecker` pro frischer
  Session (wie reportlab/pypdf), sonst schlägt die No-Dictionary-Heuristik fehl.

---

## 4. Portabilität (Displays / Web-UI)

| Oberfläche | Deckung | Anmerkungen |
|---|---|---|
| **LCD 12864 (20×4, Menübaum)** | Voll | Alle Menü-Templates single-brace Jinja (R155-Regel, von r166 geprüft: 2.586 Sektionen / 360 Templates klipper-parse-kompatibel); Listen scrollen, 40 Browser-Slots + 24+24 Gen-files-Slots rein Menü-seitig, kein Firmware-Limit |
| **Kleinere Text-Displays (16×2 hd44780)** | Funktional | M117/RESPOND funktionieren; Menü-Namen sind auf ~15 Zeichen getrimmt entworfen (V-Nummer vorne = immer unterscheidbar); line_length=16 nur Config |
| **Mainsail / Fluidd (Web)** | Voll | Alle Meldungen laufen über RESPOND/NOTIFY (Konsole) + M117 (Statuszeile); Datei-Browser = Moonraker-eigene (unbegrenzt); Gen-files-Liste ist LCD-only, im Web über den Dateibrowser erreichbar |
| **Sounds/Chirps** | Voll | `_SOUND_LIB`/`_PLAY_JOB_START` etc. laufen über den konfigurierten Output (LED/PIEZO), web-seitig als Konsole sichtbar |
| **Klipper-Updates** | Geschützt | Stale-Daemon-Sirene (R166) meldet, wenn laufender Watcher älter als die Macros auf Disk ist; r110_setup_sim prüft 10 Szenarien (install/update/check/EOF/Idempotenz) |

Bewusst NICHT portabel (Projekt-Entscheidung): Menüstruktur ist an das 20×4-Layout
optimiert (truncate(13/14) auf Namen); wer ein 16×2-Display konfiguriert, sieht
gekürzte Labels, verliert aber keine Funktion.

---

## 5. Gesamtbatterie .133 (alles NACH allen Änderungen)

| Suite | Ergebnis |
|---|---|
| macro_render_test | **1895/1895** |
| systemtest | 214 Checks / 26 Dateien / 0 FAIL |
| megatest | 190 Läufe / 194 Dateien / 0 FAIL |
| r81_golden_check | 23/23 byte-identisch (R117-Referenz) |
| r91_simulate | ALL PASSED |
| r110_setup_sim | 10/10 Szenarien |
| r110_gcode_dialects | 13/13 Familien, 46/46 Feature-Treffer |
| r111_geom_test | alle Checks grün |
| r140_stress | 46.775 Checks / 0 FAIL |
| r141_journeys | 2.342 Checks / 0 FAIL |
| r142_field_coverage | 129 Checks / 0 FAIL |
| r142_spell_lint | 1.652 Strings / 0 Verdächtige |
| r143_user_audit | 68 Checks / 0 FAIL / 0 Findings |
| r164_serial_budget | 18 Dateien / 0 FAIL / 0 Warn |
| r165_doc_check | clean (45 Makro-Token, 159 LCD-Pfade, 227 Menü-Parents) |
| r166_template_check | 21 cfg / 2.586 Sektionen / 360 Templates OK |
| r167_aircheck | 6 Checks / 0 FAIL (jetzt mit synthetischem Referenzfoto) |
| r168_stampcheck | 19 Checks / 0 FAIL (handle=2) |
| r187_matrix | 1.356 Checks / 0 FAIL |
| audit_sweep | 82 Dateien / 0 FAIL |
| config_validator | keine Fehler |

r95_featext: **retiriert** (kein Bestandteil mehr).

## 6. Geänderte Dateien (.133)

- `tools/r2_postproc.py` — R186 (Range-Skip weg, Textur-/Range-Z-Fixes, figures-Zweipass,
  `_layout_gap`), R187 (make_range Z-Tracker), Browser-Sortierung (Root A-Z,
  Unterordner mtime-desc), Gen-files-Kappe 12→24, Kollisions-Fixes (scale-Sanitizer,
  dedupe-Erschöpfung, Range-Dedupe-Netz), Frame-Preset-Validierung
- `tools/r2_texture.py` — R186 Z-Tracking im Emissions-Pass, BUMPS-ohne-Z-ValueError
- `macros/13_system.cfg` — SDNAV-Header + Sortierungs-RESPOND
- `menus/lcd_menues.cfg` — 24 Select- + 24 Delete-Slots, Info-Texte, R114-Semikolon-Fix
- Tests: macro_render_test (R91-Metrik euklidisch, R135-Whitelist, R146-48-Slots),
  r142_field_coverage, r142_spell_lint, r167, r168, r91, r111, r140, r141, r143,
  r81, r110, r187_matrix (neu)
- Entfernt: `tools/r95_featext.py`
