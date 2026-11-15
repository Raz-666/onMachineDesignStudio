# MANUAL.md gegen den CODE — Abgleich (MASTER-TODO D1)

Datum: 2026-08-29 · Stand des Codes: `R2-2026-11-13.1` / `V1`
Werkzeug: `tools/r265_manual_check.py` (prüft) + `tools/r266_manual_index.py`
(baut den Index aus dem Code neu)

**Ergebnis: 4 echte Abweichungen gefunden, 3 behoben, 1 offen (Entscheidung
des Users).** Der Rest sind geprüfte Fehlalarme des Prüfers, dokumentiert
unten — damit niemand sie ein zweites Mal für Fehler hält.

---

## 1. Was geprüft wurde (und was der Prüfer NICHT kann)

| Prüfung | Umfang | Aussagekraft |
|---|---|---|
| **A** Makro-Index (Kap. 25) | 409 Einträge gegen 379 `gcode_macro` + 30 `delayed_gcode` | vollständig: jeder gelistete Name existiert, jeder öffentliche Makro ist gelistet |
| **B** Zahlen im Text | Index-Zahlen, LED-Zustände | zählbar geprüft |
| **C** LCD-Pfade | 158 Paare „Obermenü > erster Unterzweig" gegen 2295 Menüzweige | prüft die **erste** Ebene; tiefere Ebenen nur, wo der Anzeigename exakt passt |
| **D** Variablennamen | in Backticks genannte `ov_*`/`f_*`/`zh_*` | nur was als Code markiert ist |
| **E** Befehle in Code-Blöcken | 27 Blöcke | Befehlszeilen-Form; Prosa wird ignoriert |

**Nicht geprüft** (ehrlich gesagt): ob eine *Erklärung* stimmt. Ob „der
Lüfter hält in Schicht 1" auch wirklich so passiert, prüft nur der Code —
und das tun die 2100 Batterie-Tests, nicht dieses Werkzeug. Der Abgleich
findet Namen, Zahlen und Pfade, keine Physik.

---

## 2. Die vier echten Abweichungen

### 2.1 Makro-Index war vier Releases alt — **behoben**

| | Handbuch behauptete | Code hat |
|---|---|---|
| Einträge | 194 | **409** |
| öffentliche Makros | 239 | **265** |
| interne Makros | 100 | **114** (+ 30 `delayed_gcode`-Hooks) |

75 öffentliche Makros fehlten komplett, darunter ganze Familien:
`BABYSTEP_*`, `BED_SCREWS_*`, `CLEAN_NOZZLE`, `COLORPIC_SET_COLOR`, die
`CALIBRATE_*`-Gruppe und die Plotter-Befehle.

**Behoben** mit `tools/r266_manual_index.py`: Kapitel 25 wird aus den
`.cfg`-Dateien neu gebaut — Name, Datei, Parameter (aus
`params.X|default(Y)` im jeweiligen Makro) und Zählungen. Der **Zweck-Text
bleibt der aus dem Handbuch**, wo er schon stand (Prosa, die stimmte); nur
für neue Einträge wurde `description:` aus dem Code genommen. Wo der Code
keine Beschreibung hat, steht ein aus dem Rumpf abgeleiteter Einzeiler —
keine Erfindung.

Ergebnis: 409 Einträge, 21 Dateiabschnitte, kein gelisteter Name ohne
Code-Gegenstück, kein öffentlicher Makro ungelistet.

### 2.2 Drei LCD-Anzeigenamen stimmten nicht — **behoben**

| Handbuch sagte | LCD sagt wirklich | wo |
|---|---|---|
| `Tools > ColorPic` | **`Tools > ColorPicture`** | Kap. 5 (2×), Kap. 24 |
| `Tools > String art` | **`Tools > ArtisticStrings`** | Kap. 5 |
| `System > Pi shutdown` | **`System > Pi shutdown? arm`**, dann **`>> PI SHUTDOWN NOW`** | Kap. 24 |

Die Namen sind aus `menus/lcd_menues.cfg` (`name:`-Zeile je `[menu …]`)
gelesen, nicht geschätzt. Inhaltlich war die Beschreibung richtig, nur der
Weg dorthin hieß anders.

### 2.3 Der Doc-Check `r165` meldete 5 Verstöße — **behoben, aber es waren meine**

`tools/r165_doc_check.py` prüft die projektweite Regel „keine handgetippte
Versionsnummer" (nach dem Vorfall, dass fünf PDFs vier Releases lang
`.136ai` behaupteten). Meine drei neuen PDF-Bauer hatten:

- in `make_postproc_pdf.py` und `make_preprint_pdf.py` den Stempel
  `R2-2026-11-13.1` **wörtlich** im Text (einmal in einem Beispiel, einmal
  in einer Kapitelzeile),
- in allen drei Bauern **keinen** direkten Import von `r2_version`.

**Behoben:** alle drei importieren jetzt `from r2_version import VERSION as
R2VER` und setzen die Version per Verkettung zusammen. `r165` ist damit
wieder `clean` — das ist der Prüfstein, nicht meine Zusicherung.

### 2.4 OFFEN: Kapitel 14 beschreibt eine Lüfter-Kette, die es so nicht mehr gibt

Das ist der einzige Punkt, bei dem ich **nicht** einfach das Handbuch
angepasst habe, weil die Entscheidung dir gehört.

Kap. 14 (LCD-Referenz) beschreibt den Lüfter-Unterpunkt als „HOLD ersetzt
Datei-Wert, CLAMP begrenzt" — das stimmt weiter. Was dort **fehlt**, ist die
Stufe, die im Code seit R175c **über** allem steht: der absolute
**LIVE-Wert** (`M106: S255 -> LIVE 40% -> S102`, danach werden Hold, Scale,
Clamp und sogar die Schicht-1-Regel übersprungen). Im neuen PDF
(`PREPRINT_LIVETUNING.pdf`, Kap. 8.5) steht die vollständige Kette.

**Zu entscheiden:** Soll das Handbuch die LIVE-Stufe nachziehen (dann
schreibe ich Kap. 14 in einem Durchgang nach, mit der Prioritätsliste wie im
PDF), oder ist das Handbuch bewusst auf dem Stand „nur Pre-Print-Schalter"?

---

## 3. Geprüfte Fehlalarme (damit sie niemand erneut jagt)

Diese sieben Zeilen stehen nach der Reparatur noch in der Liste — jede
einzeln gelesen und als **Prosa, nicht als Menüpfad** bestätigt:

| „Pfad" | was es wirklich ist |
|---|---|
| `Control > Change` | Klippers eigenes Control-Menü (Filamentwechsel), nicht unseres |
| `LIVE > layer-1 fan-off` | Fließtext über die Schicht-1-Regel |
| `Live Tuning > Plotter while plotting` | Pfad + Beschreibungssatz |
| `Maintenance > gen-out decides selected-` | Fließtext (Zeilenumbruch mitten im Satz) |
| `Pre-Print > File info shows` | Pfad + Verb |
| `Pre-Print > Preheat. OFF` | Pfad + Satzanfang |
| `SD Card > the submenu` | Fließtext |

Der Prüfer hätte sie loswerden können, indem er auf „irgendein bekannter
Name irgendwo" matcht — genau dann wäre er wertlos. Deshalb bleiben sie
sichtbar.

---

## 4. Wie man den Abgleich wiederholt

```bash
python3 tools/r265_manual_check.py           # Bericht, Exit 1 bei echten Fehlern
python3 tools/r265_manual_check.py --streng  # auch Hinweise zählen als Fehler
python3 tools/r266_manual_index.py           # Trockenlauf: was würde sich ändern?
python3 tools/r266_manual_index.py --schreiben
```

Nach jeder Änderung am Makro-Bestand gilt: **erst** `r266 --schreiben`,
**dann** `r265`. Sonst schlägt der Prüfer auf einen Index, der den Code
noch nicht kennt — und das ist der Zustand, aus dem dieser Bericht entstand.
