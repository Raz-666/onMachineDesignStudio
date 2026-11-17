# Offene Fragen an den Nutzer (Stand: 2026-11-17, späte Fortsetzung)

Gesammelt, weil du mehrere Stunden nicht erreichbar bist. Reihenfolge ≈ Auswirkung.
Nichts hierin ist als Freigabe zu lesen; die Regeln aus `UEBERGABE.md` gelten.

## A. Entscheidungen, die nur du treffen kannst

1. **Layer-Zählung (Release-Blocker):** Option A (Status quo + verbindliche Doku der
   Zählkonvention), Option B (Z-Scan nur bei positiver Extrusion + SKIN aus physischen
   Extrusionsschichten, inkl. Migrationsprüfung/Goldens-Neufrieren), oder Option C
   (Kommentarlose Dateien → `TOTAL_LAYERS=0` + Hinweis)? Vorlage mit Belegen und
   Abnahmekriterien: `analyse/LAYER-ZAEHLUNG-DIVERGENZ-SPEZIFIKATION.md`
   (Empfehlung des Analysestands: A sofort, B als eigener Umbau, C nicht).
2. **D1 (offen, MASTER-TODO):** MANUAL.md Kap. 14 kennt die LIVE-Lüfterstufe
   (R175c) nicht — Handbuch nachziehen, ja/nein?
3. **Zwei Briefings:** Rangfolge `R2-D2 – Gesamtbriefing` vs.
   `R2_Vollstaendiges_Startbriefing_…_finalizedByGemini.txt` (STL/OBJ §5.21 vs.
   Abschnitt 24). Zudem: existieren `slicer-families.md`,
   `GCode_Reverse_Engineering_Master_Spezifikation.md` und das referenzierte
   V1-UPDATE-ZIP noch — und wo?
4. **Release:** Soll ein neues Release gebaut werden? Wenn ja: Version/Build
   (z. B. `R2-2026-11-17.1` / `V2`?), Paketinhalt, und ausdrückliche Freigabe
   nach finaler Offline-Suite. Ohne diese Antwort bleibe ich bei
   `R2-2026-11-13.1` / `V1` und baue nichts.
5. **E1/E4 (offen):** `position_min = -6` → Vorschlag `-2` in deiner
   `printer.cfg`? Probe-Trigger/led_effect-/Homing-Abbruch im Print-Start nur
   mit aktueller Konfiguration + Feldlogs + separatem Test-Go — welche
   Dateien/Stände stellst du bereit, und welches Test-Fenster gilt?
6. **521-Crosswalk:** Soll ich als Nächstes die `O`/`G`-Zeilen
   (53 + 62 + 18 = 133 Zeilen) für einen Entscheidungstermin aufbereiten
   (Entscheidungsantwort je Zeile), oder die `P`/`P/G`-Zeilen auf
   Code-/Testreferenzen aufschlüsseln?

## B. Einordnung der letzten Änderungen

7. **PR #13 (gemerged, Basis `4b22e8e`):** Pass-11-Sidecar (`r2-sidecar/1`),
   521-Crosswalk-Vorsortierung, CI-Reparatur (r91; kleinste Textur-Engine-
   Korrektur: jedes eingefügte BUMPS-Sub-Segment trägt wieder `F`). Merge
   erfolgte auf dein ausdrückliches Go, nachdem CI grün war. Soll künftig
   jeder Merge auf grünem CI warten (mein Vorgehen), oder Instant-Merge nach
   explizitem Go genügen?
8. **`.github/workflows/tests.yml`:** Auf `main` liegt seit `17405c1` ein
   Node-24-Update der Actions (nicht aus dieser Sitzung). Bestätigen?
9. **Shadow-Resync:** Soll die Shadow-Rekonstruktion künftig opt-in auf die
   reale R2-Makrosemantik resynchronisieren dürfen (belegte Hypothese statt
   Fail-closed-Invalidierung), oder bleibt Fail-closed die verbindliche
   Semantik? (Aktuell: Fail-closed; die Feldfixtures liefern bewusst
   0 vollständig bekannte Endpunkte.)

## C. Kleinigkeiten / Abwarten

10. `macro_render_test.py` auf dem Merge-Ergebnis `4b22e8e` noch einmal seriell
    protokollieren? (Vor dem Merge auf dem Branch grün; Merge fügte nur das
    Actions-Update hinzu.)
11. `UEBERGABE.md` nennt als historische Referenz weiterhin `8ea17fc`/`fab29dc`
    in Abschnitt 3 — für das Release irgendwann vollständig neu abgleichen,
    oder so stehen lassen als datierten Verlauf?
12. D7d `GENERATORS_TOOLS.pdf` (veraltet, Stand `.142j`): inzwischen aus dem
    aktuellen Code neu gebaut (Versionskopf `R2-2026-11-13.1` auf allen
    12 Seiten, „27 Muster / 27 Vorlagen“-Zeile korrigiert; Inhalt sonst
    unverändert; PR #15 gemerged). Weiterhin offen bleibt die
    Modifier-Einzel-Dokumentation (D4-Umfang: Mathematik pro Modifier).
    Soll D4 als Nächstes kommen?
13. MASTER-TODO `B5` (FeatOn statt Wert 0) — für dich geklärt (abgelehnt mit
    Begründung). Keine Aktion nötig.

## D. Für den Notfall

- Letzte grüne Stände: Review-Gate PASS (`review_checks_dd5058ac_sidecar_20261117.log`),
  Makro 2103/2103 (`macro_render_dd5058ac_texturefix_20261117.log`), CI `suite` pass (7m51s).
- Backout-Referenz: vor PR #13 war `main` bei `846b1e7`; Rückweg = Revert von `4b22e8e`.
