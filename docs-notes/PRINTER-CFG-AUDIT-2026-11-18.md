# printer.cfg-Audit (Nutzer-Datei vom 2026-11-18)
**Quelle:** `my_printer.cfg.txt` (Anhang des Nutzers, 935 Zeilen) · **Status: Vorschläge, NICHT angewendet.**
Jede Änderung an dieser Datei macht der Nutzer selbst auf dem Pi (oder erteilt ein ausdrückliches Go);
kein Go für automatische Übernahme. Rückweg ist immer ein Einzeilen-Revert.

## 1. E4 (MASTER-TODO): `[stepper_z] position_min = -6` → Vorschlag `-2`

**Befund.** Der Z-Achs-Endstop ist `probe:z_virtual_endstop` — die Sonde ist die Referenz. Der
Fehlerfall aus dem Feldlog (.142g, 12.11.) war: Sonde triggert nicht, 4× „No trigger on probe
after full movement“, Düse fuhr auf Z = −6,0. Mit `position_min = -6` erlaubt Klipper genau
diese 6 mm ungehinderte Abfahrt; `position_min = -2` begrenzt denselben Fehler auf 2 mm unter
der Nullebene — immer noch genug Freiraum für das Anfahren (Sonden-Kalibrierfahrt endet oberhalb
von Z0, der virtuelle Endstop triggert vorher), aber die Düse kann das Bett nicht mehr mit 6 mm
Engagement treffen. Zugehörige Werte sind unverändert konsistent:
`[probe] z_offset` aktiv = **0,949** (SAVE_CONFIG-Zeile, der auskommentierte `#z_offset: 1.620`
ist Alt-Text), `[safe_z_home] z_hop: 10` (groß, sicher), `horizontal_move_z: 4` (Mesh/Schrauben).

**Drop-in-Patch (nur diese Zeile):**
```ini
[stepper_z]
position_min: -2        # war: -6  (E4, MASTER-TODO: Sonde löst nicht aus → Z=-6)
```

**Risiko.** Minimal — nur relevant, falls die Sonde auf dem Weg nach unten durch +2 mm Z0 jemals
nicht triggert (dann stoppt der Druckstart mit „No trigger“ statt 6 mm abzufahren). KEIN Go
ohne dass die Sonde grundsätzlich vermessen ist (s. §2).

## 2. E1 (MASTER-TODO): Probe-Trigger im Print-Start — Stand der Absicherung

Der Feld-Fehlerfall (.142g) war: Z-Homing über die Sonde triggerte nicht → Shutdown mitten im
`G28`. Was das System seitdem bereits abfängt (im Code, nicht in dieser Datei):

| Schutz | Stand |
|---|---|
| Homing-Guard `G28` (R255/R256) | Jeder G28 meldet `mode=homing`; Watcher bleibt ruhig; 15-min-Bremse; G28→M99110 Pflicht-Namensregel im Batterie-Test |
| LED-Stummschaltung `_LED_QUIET` (R257) | Um den G28-Aufruf und in Mesh/Schrauben/PROBE_CALIBRATE stumm; `_STATE_WATCHER` heilt Hänger |
| AV-Delay um Homing (R236) | Sound/LED/Echo um 1,5 s verzögert, mode-guarded |
| 380+ Shutdown-Forensik (.142l/R256) | Reaktionspfad (led_effect `_pollProgress`) minimiert |

**Was an DEINER Datei auffällt (nicht ändern ohne Rücksprache):**

1. **Deploy-Wartezeit.** Feldlog-Stand war `G4 P750`, deine Datei fährt `G4 P550`. Falls die
   Sonde mechanisch >0,55 s zum Ausfahren braucht, schlägt sie (selten) nicht rechtzeitig an.
   Vermessen: `PROBE_ACCURACY` nach Deploy; wenn der Trigger unregelmäßig ist, `G4 P750` setzen.
2. **Probe-Pin-Logik.** `^!PC14` mit Kommentar „V2 version, low-level trigger“ — passt zu deinem
   V2-MicroProbe (trigger bei Kontakt = LOW). Nicht umstellen.
3. **`samples: 2` + `samples_tolerance: 0.15` + `median`** — vernünftig; bei sporadischen
   „No trigger“-Meldungen eher `probing_rapid_speed`/Wiederholungen prüfen, nicht die Toleranz lockern.
4. **`[screws_tilt_adjust] speed: 180` und `[bed_mesh] speed: 180`** — dein eigener Kommentar
   warnt vor 300 mm/s (Shutdown bei Y-Schlägen der schweren Achse). 180 mm/s ist näher an der
   sicheren Seite, aber dieselbe Klasse. Vorschlag: **100 mm/s** (verdoppelt nur die Messzeit um
   wenige Sekunden). Kein Auto-Patch — deine Einschätzung?
5. **`home_xy_position: 115,115`** bei 220×220-Bett (Mitte wäre 110,110) und `mesh_max: 200,220`
   — harmlos, kein Absturzgrund; nur zur Kenntnis.
6. **`z_offset` aktiv = 0,949** (SAVE_CONFIG) — der auskommentierte 1,620-Block ist verwirrend,
   aber wirkungslos; Klipper nutzt den SAVE_CONFIG-Wert. Kommentar optional aktualisieren.
7. **`[force_move] enable_force_move: True`** — notwendig für SYNC_GANTRY (dokumentiert), bewusst so lassen.
8. **`stealthchop_threshold: 999` (Z)** — ok für leichte achslastige Bewegung; nicht Teil von E1/E4.

## 3. Ausdrücklich NICHT behauptet

- Keine Vermessung am Drucker. Keine Aussage über Sonden-Mechanik (Federelement, Kontaktzungen,
  Verkabelung PC14). Der E4-Patch ist Schadensbegrenzung, kein Trigger-Fix.
- E1-Abschluss („Print-Start triggert zuverlässig“) ist ohne Testfenster auf dem Drucker nicht erreichbar.
- Die Datei hier ist die **vom 18.11.** — ein danach am Pi geänderter Stand kann abweichen;
  Patches immer gegen die aktuelle Datei auf dem Gerät prüfen.

## 4. Konkrete nächste Schritte (nach deinem Go)

1. `position_min: -2` (§1) — 1 Zeile, Revert-fähig.
2. Probing-Deploy bei Trigger-Problemen auf `G4 P750` anheben (§2.1).
3. Optional: `speed: 100` in `[screws_tilt_adjust]` und `[bed_mesh]` (§2.4).
4. Testfenster: 3× Z-Homing hintereinander + 1× Mesh 5×5 + 1× SCREWS_TILT_CALCULATE;
   danach Feldlog kurz bereitstellen — erst dann E1/E4 abschließen.
