# Offene Fragen an den Nutzer (Stand: 2026-11-18)

Gesammelt aus der Sitzung vom 18.11.2026. Reihenfolge ≈ Auswirkung. Erst wenn hier konkret entschieden ist, sind die zugehörigen Umbauten freigegeben. Die Regeln aus `UEBERGABE.md` gelten weiter.

## A. Entscheidungen, die nur du treffen kannst

1. **Layer-Zählung — ENTSCHIEDEN + UMGESETZT (Option B, R258, 2026-11-18).** Deine Erklärung bat um Alltagsdeutsch: Zählt der Drucker an Slicer-Kommentaren (`;LAYER_CHANGE`), meldete er z. B. 3 Schichten; ohne Kommentare zählte er nur Höhensprünge ab der zweiten Schicht (2 statt 3) und alle SKIN-Flächen galten als Boden. Option B (Umbau) ist jetzt umgesetzt: kommentarlos zählt `rises + big_rises + 1 + bed_returns` (erste Schicht, >0,35-mm-Treppen, Bett-Rückkehrer bei sequentiellem Druck); kommentierte Dateien behalten die Slicer-Anzahl (Fixtures belegten, dass der Scan dort überzählt); SKIN ist in beiden Welten konsistent (BOTTOM/TOP/TOP); Marker-Ausgabe byte-stabil. Belege: `analyse/LAYER-ZAEHLUNG-DIVERGENZ-SPEZIFIKATION.md` §7, `analyse/golden_r258_expected.json`, r81-Re-Freeze (pr03/pr08, je exakt 1 Zeile), Makro 2103/2103, review_checks PASS. **Offen bleibt nur die Feldabnahme am Drucker.**
2. **D1 (offen, MASTER-TODO):** MANUAL.md Kap. 14 kennt die LIVE-Lüfterstufe (R175c) nicht — Handbuch nachziehen, ja/nein?
3. **Zwei Briefings — TEILWEISE BEANTWORTET.** Geliefert am 18.11.2026: `GCode_Reverse_Engineering_Masterkonzept.md` und `Reverse Engineering von G-Code Geometrien.md` (beide Hash-pinned, echt) sowie neu `slicer-families.md` und `Potential performance& compatibility issues.md` (neu, AI-erzeugt, NICHT pinned, nur lokal in `analyse/uebergabe-quellen/`, nicht im Repo). **Offen:** Rangfolge `R2-D2 – Gesamtbriefing` vs. `R2_Vollstaendiges_Startbriefing_…_finalizedByGemini.txt`; ob `GCode_Reverse_Engineering_Master_Spezifikation.md` existiert; wo das V1-UPDATE-ZIP liegt.
4. **Release — ZWEI Stände.** (a) `R2-2026-11-18.1` / `V2` gemergt (PR #18, `0535848`): Paket ohne `analyse/`, `UPDATE-R2-2026-11-18.1.zip`, r199 12/12, Makro 2103/2103, review_checks PASS, megatest 190/190, r81 23/23 (Stamp-Re-Freeze), golden_baseline PASS. (b) NEU: `R2-2026-11-18.2` / `V3` (dieser Branch `arena/4ea70100-...`, Gesamtumbau-Analyse-Engine `tools/gcode_re.py`, Release-Bericht `docs/RELEASE_R2-2026-11-18.2_REPORT.md`): gleiche Gates grün, r81 23/23 (stamp-class Re-Freeze, A/B bewiesen), Makro 2103/2103. **Offen bleibt in beiden:** Feldabnahme am Drucker (Layer-Anzeige nach Update) — der Drucker ist aktuell nicht testbereit.
5. **E1/E4 (offen):** `position_min = -6` → Vorschlag `-2` in deiner `printer.cfg`? Probe-Trigger/led_effect-/Homing-Abbruch im Print-Start nur mit aktueller Konfiguration + Feldlogs + separatem Test-Go — welche Dateien/Stände stellst du bereit, und welches Test-Fenster gilt?
6. **521-Crosswalk:** Soll ich als Nächstes die `O`/`G`-Zeilen (53 + 62 + 18 = 133 Zeilen) für einen Entscheidungstermin aufbereiten (Entscheidungsantwort je Zeile), oder die `P`/`P/G`-Zeilen auf Code-/Testreferenzen aufschlüsseln? (Hinweis: die neuen Slicer-Familien-Notizen können beim Vokabular-Abgleich helfen — werden aber erst verifiziert gegeneinander.)
7. **Neue Analyse-Dateien:** `slicer-families.md` und `Potential performance& compatibility issues.md` sind jetzt lokal abgelegt und ins SHA256-Manifest aufgenommen; ihre Aussagen sind **nicht verifiziert** (u. a. index.html ≈ 888 KB und menu_structure.json > 1 MB behauptet — muss gegen den Code geprüft werden). Soll ich daraus (a) nur einen Backlog-Vorschlag machen, (b) Punkt für Punkt verifizieren und dann korrigierte Doku ableiten, oder (c) liegen lassen?

## B. Einordnung der letzten Änderungen

8. **PR #13 (gemerged, Basis `4b22e8e`):** Pass-11-Sidecar (`r2-sidecar/1`), 521-Crosswalk-Vorsortierung, CI-Reparatur (r91). Merge erfolgte auf dein Go nach grünem CI. Soll künftig jeder Merge auf grünem CI warten (mein Vorgehen), oder Instant-Merge nach explizitem Go genügen?
9. **`.github/workflows/tests.yml`:** Auf `main` liegt seit `17405c1` ein Node-24-Update der Actions (nicht aus dieser Sitzung). Bestätigen?
10. **Shadow-Resync:** Soll die Shadow-Rekonstruktion künftig opt-in auf die reale R2-Makrosemantik resynchronisieren dürfen (belegte Hypothese statt Fail-closed-Invalidierung), oder bleibt Fail-closed die verbindliche Semantik? (Aktuell: Fail-closed; die Feldfixtures liefern bewusst 0 vollständig bekannte Endpunkte.)

## C. Kleinigkeiten / Abwarten

11. `macro_render_test.py` zuletzt seriell auf dem Release-Stand gelaufen (2103/2103, 18.11.2026). OK.
12. `UEBERGABE.md` nennt historische Referenzen `8ea17fc`/`fab29dc` — für das Release irgendwann vollständig neu abgleichen, oder so stehen lassen als datierten Verlauf?
13. D7d `GENERATORS_TOOLS.pdf`: aus aktuellem Code neu gebaut (PR #15, gemerged). Offen bleibt die Modifier-Einzel-Dokumentation (D4). Soll D4 als Nächstes kommen?
14. MASTER-TODO `B5` (FeatOn statt Wert 0) — für dich geklärt (abgelehnt mit Begründung). Keine Aktion nötig.

## D. Für den Notfall

- Letzte grüne Stände (18.11.2026, Releases `R2-2026-11-18.1`/`V2` und `R2-2026-11-18.2`/`V3`): review_checks PASS, Makro 2103/2103, megatest 190/190, r91 PASS, r81 23/23 (Stamp-Re-Freeze), r199 ZIP 12/12. Notfall-Rückweg: Revert des Release-PRs; vorheriger Release `R2-2026-11-13.1`/`V1` liegt im Paket unter `backups/r2_postproc_R2-2026-11-13.1_V1.py`.
