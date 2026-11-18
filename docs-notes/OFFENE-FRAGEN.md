# Offene Fragen an den Nutzer (Stand: 2026-11-18, aktualisiert nach D5/D3/D4-Entscheidung)

Gesammelt aus der Sitzung vom 18.11.2026. Reihenfolge ≈ Auswirkung. Erst wenn hier konkret entschieden ist, sind die zugehörigen Umbauten freigegeben. Die Regeln aus `UEBERGABE.md` gelten weiter.

## A. Entscheidungen, die nur du treffen kannst

1. **Layer-Zählung — ENTSCHIEDEN + UMGESETZT (Option B, R258, 2026-11-18).** Deine Erklärung bat um Alltagsdeutsch: Zählt der Drucker an Slicer-Kommentaren (`;LAYER_CHANGE`), meldete er z. B. 3 Schichten; ohne Kommentare zählte er nur Höhensprünge ab der zweiten Schicht (2 statt 3) und alle SKIN-Flächen galten als Boden. Option B (Umbau) ist jetzt umgesetzt: kommentarlos zählt `rises + big_rises + 1 + bed_returns` (erste Schicht, >0,35-mm-Treppen, Bett-Rückkehrer bei sequentiellem Druck); kommentierte Dateien behalten die Slicer-Anzahl (Fixtures belegten, dass der Scan dort überzählt); SKIN ist in beiden Welten konsistent (BOTTOM/TOP/TOP); Marker-Ausgabe byte-stabil. Belege: `analyse/LAYER-ZAEHLUNG-DIVERGENZ-SPEZIFIKATION.md` §7, `analyse/golden_r258_expected.json`, r81-Re-Freeze (pr03/pr08, je exakt 1 Zeile), Makro 2103/2103, review_checks PASS. **Offen bleibt nur die Feldabnahme am Drucker.**
2. **D1 — JA, freigegeben.** MANUAL.md Kap. 14 um die LIVE-Bedienung ergänzt; PDF-Ausbau bleibt zurückgestellt.
3. **Zwei Briefings — BEANTWORTET (2026-11-18).** Der Nutzer hat am 18.11.2026 sechs Quellen erneut bereitgestellt (Uploads, SHA256 geprüft): maßgeblich ist **`R2-D2 – Gesamtbriefing für die Coding-GPT.md`** (926438eb…, neu — enthält die STL-Export-Ergänzung §24 und alle Ergänzungen 20–31). Die Datei `R2_Vollstaendiges_Startbriefing_Coding-KI_finalizedByGemini.txt` (766a0bc…) ist die frühere Fassung desselben Dokuments (STL dort als §5.21) und bleibt nur Referenz. `GCode_Reverse_Engineering_Masterkonzept.md` (c5a1400…) = Grundgedanke/Konzept, `Reverse Engineering von G-Code Geometrien.md` (8db2965…) = Detaildokument. `slicer-families.md` / `Potential performance& compatibility issues.md` = AI-erzeugte Notizen (aa1aece… / 9eeb66f…), **Inhalt ungeprüft**, nie als Beleg. `GCode_Reverse_Engineering_Master_Spezifikation.md` wurde **nie bereitgestellt** (kein Upload) — als nicht vorhanden vermerkt. Offen bleibt nur: wo das V1-UPDATE-ZIP liegt (Item 4, Feldabnahme-Frage).
4. **Release — ZWEI Stände.** (a) `R2-2026-11-18.1` / `V2` gemergt (PR #18, `0535848`): Paket ohne `analyse/`, `UPDATE-R2-2026-11-18.1.zip`, r199 12/12, Makro 2103/2103, review_checks PASS, megatest 190/190, r81 23/23 (Stamp-Re-Freeze), golden_baseline PASS. (b) NEU: `R2-2026-11-18.2` / `V3` (dieser Branch `arena/4ea70100-...`, Gesamtumbau-Analyse-Engine `tools/gcode_re.py`, Release-Bericht `docs/RELEASE_R2-2026-11-18.2_REPORT.md`): gleiche Gates grün, r81 23/23 (stamp-class Re-Freeze, A/B bewiesen), Makro 2103/2103. **Offen bleibt in beiden:** Feldabnahme am Drucker (Layer-Anzeige nach Update) — der Drucker ist aktuell nicht testbereit. **UPDATE 2026-11-18:** V1-UPDATE-ZIP gefunden und geprüft (167 Einträge, kein `analyse/`, interner Stempel `R2-2026-11-13.1`; SHA256 `6234496e…`; lokal unter `releases/…-2026-11-13.1.zip`, nicht im Repo).
5. **E1/E4 (offen):** `position_min = -6` → Vorschlag `-2` in deiner `printer.cfg`? Probe-Trigger/led_effect-/Homing-Abbruch im Print-Start nur mit aktueller Konfiguration + Feldlogs + separatem Test-Go — welche Dateien/Stände stellst du bereit, und welches Test-Fenster gilt?
6. **Gesamtprüfung — BEAUFTRAGT.** Alle Anforderungen einzeln gegen Code und Tests prüfen, einschließlich offener und teilweise umgesetzter Punkte. Die Abkürzungen waren das Missverständnis, keine fehlende Freigabe.
7. **Recherche-Dateien — GEKLÄRT.** Alle Uploads berücksichtigen: RE, Slicer-Familien, Mathematik und Performance-/Kompatibilitätshinweise als Hilfestellung nutzen und relevante Aussagen verifizieren. Nicht ignorieren.

## B. Einordnung der letzten Änderungen

8. **Merge-Verfahren:** Weiterhin grünes CI und ausdrückliches Merge-Go; keine erneute Grundsatzfrage nötig.
9. **`.github/workflows/tests.yml`:** Node-24-Update der Actions seit `17405c1`. **BESTÄTIGT durch den Nutzer 2026-11-18** („die Empfehlung von GitHub, das habe ich gemacht und hoffe es war richtig“).
10. **Shadow-Resync:** Technische Prüfaufgabe innerhalb der Gesamtprüfung, keine erneut an den Nutzer gerichtete Fachfrage. Bis zu belegter Entscheidung bestehendes Fail-closed-Verhalten erhalten.

## C. Kleinigkeiten / Abwarten

11. `macro_render_test.py` zuletzt seriell auf dem Release-Stand gelaufen (2103/2103, 18.11.2026). OK.
12. `UEBERGABE.md` nennt historische Referenzen `8ea17fc`/`fab29dc` — **ENTSCHIEDEN 2026-11-18 (vom Nutzer an die Agenten-Handoff-Übergabe gekoppelt):** Bleibt als datierter Verlauf; neue Agenten starten über `AGENTS.md`. §6 von UEBERGABE zeigt jetzt auf `AGENTS.md`.
13. D7d `GENERATORS_TOOLS.pdf`: aus aktuellem Code neu gebaut (PR #15, gemerged). Offen bleibt die Modifier-Einzel-Dokumentation (D4). **Entscheidung 2026-11-18: D3/D4 zurückgestellt** (Drucker im Umbau); Reihenfolge orientiert sich an den übrigen offenen Punkten (D1, Items 2–10), Umfang (>15 Einzel-PDFs vs. Gesamtwerk) noch nicht final. **D5 erledigt** (Commit `9468051`, `CREATIVE_POSSIBILITIES.pdf` 10 Seiten).
14. MASTER-TODO `B5` (FeatOn statt Wert 0) — für dich geklärt (abgelehnt mit Begründung). Keine Aktion nötig.

## D. Für den Notfall

- Letzte grüne Stände (18.11.2026, Releases `R2-2026-11-18.1`/`V2` und `R2-2026-11-18.2`/`V3`): review_checks PASS, Makro 2103/2103, megatest 190/190, r91 PASS, r81 23/23 (Stamp-Re-Freeze), r199 ZIP 12/12. Notfall-Rückweg: Revert des Release-PRs; vorheriger Release `R2-2026-11-13.1`/`V1` liegt im Paket unter `backups/r2_postproc_R2-2026-11-13.1_V1.py`.

## E. Neue Anfragen (Sitzung nach `bdb8b03`)

15. **STL-§24-Fertigstellung zurückgestellt** — vom Nutzer bestätigt; neue
    Rekonstruktionsrichtung „Punktfolke + Haut“ (organische Formen) ist in
    MASTER-TODO J1 notiert. Wiederaufnahme erst nach ausdrücklichem Go.
16. **Gießformen-Pre-Print-Tool (J2):** Du hast eine weitere Pre-Print-
    Aufgabe in Aussicht gestellt. Bitte bei Zuweisung klären: Was genau soll
    das Werkzeug erzeugen (zweiteilige Gießform? Negativform? aus vorhandenem
    G-Code oder aus Generatoren-Geometrie? Toleranzen/Ausgieser/Luftkanäle?).
17. **UI-Einbindung der Web-LCD (J3):** iframe in Mainsail ist nicht möglich
    (kein Custom-Panel-Mechanismus). Optionen: eigener Port (heute gebaut),
    Pfad im Mainsail-vhost (gleiche URL) oder beides — welche Variante soll
    der Standard für fremde Drucker werden?
18. **Audio-Weg (J4):** MCU-Piezo (heute) / Pi-Klinke (nur Modelle mit
    Analog-Ausgang, z. B. 3B+) / GPIO-Piezo mit Treiber / WebAudio im
    Browser / still — was ist der Zielweg für die Standard-Installation auf
    fremden Klipper-Druckern? (Eigener Drucker: Pi Zero 2 W ohne Klinke.)
