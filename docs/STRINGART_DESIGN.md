# R171/R178 — String-Art-Generator (fertig in .130: Engine R171, Menü/Makro/Watcher R178)

## Woher das Design kommt

Der Nutzer druckte mit .128 ein generisches StringArt3D-File erfolgreich
(`testfixtures/stringart3d_generic.gcode.gz`, Feldbeweis ✅). Die Analyse
dieses Feldbewiesen Files ist die Architektur-Vorlage — R171 baut sie als
nativen Generator nach, mit allem, was das System sonst auszeichnet
(PRINT_START, _FILE_INFO, Feature-Tags, Exclude-Objekte, Geschwindigkeits-
Normalisierung, V-Dateinamen, LCD/Mainsail-Anbindung).

## Die bewiesene Architektur (aus dem Fixture gemessen)

| Element | Messwert | Umsetzung in `make_string_art` |
|---|---|---|
| Kreis | 180 mm, 600 Anker, 1700 Fäden | Parameter `diameter/anchors/lines` (Defaults 180/300/1700) |
| Ankerring | Wände + Solid, Z 0,2…2,4 (12 Lagen 0,2), erste Lage Fan aus, Adhäsions-Fuß | Ring aus 2 Wänden + konzentrischem Solid, Brim, `M107` erste Lage |
| Faden-Bänder | 6 Z-Bänder: +0,20/+0,40/+0,55/+0,60/+0,75/+0,95 über Ringoberkante | exakt diese Leiter (`LADDER`) |
| Faden-Emission | Safe-Z-Hop (Band+0,35) → Travel → Abtauchen → Prime → Wickel-Curl am Anker (r≈0,3, Mikrosegmente) → Sehne (~5-mm-Segmente) → Retract; 1783 Retracts ≈ 1/Faden | der `_Pen` macht G10/Hop/G11 von selbst; Curls + 5-mm-Sehnen; F1500 |
| Faden-Querschnitt | E/mm ≈ 0,034 bei 0,5 Breite → ~0,07 mm dick | `Emm = wid * 0.068` |
| Kühlung | „pla_ring_cooling_ramp" | `M106 S60..S260` pro Band (60+40·Band) |
| Abschluss | Finishing Ring 1/2 + Cover Ring (3,4/3,6/3,8 bei Ring 2,4) | 3 Schleifen bei +1,05/+1,25/+1,45 |

## Muster

- **PHOTO**: Bild (png/jpg) → Gitter im Kreis, dunkel = will Faden.
  Greedy: pro Runde zufälliger Kandidaten-Subset (Standard 240), beste
  Sehne legt ab, Residuum sinkt um `thread_dark=0.10`. Pi-Zero-freundlich
  (~40 M einfache Ops für 1700 Fäden). Seeded → reproduzierbar.
- **SPIRAL**: klassisch k → k+n/3, kein Bild nötig — ideal für den
  ersten Testdruck.

## System-Anbindung (Stand dieser Sitzung: Generator + Tests fertig)

- [x] `make_string_art()` + `_string_art_plan()` in tools/r2_postproc.py
- [x] R171-Batterietests (Architektur, PHOTO-Reproduzierbarkeit, Guards)
- [x] LCD-Menü (R178, Tools > String art): Pattern/Ring/Anchors/Strands,
      Img (Root-Bildliste wie Litho, Zyklus + Index), How?, My presets,
      Doppelklick-Weave — in `menus/lcd_menues.cfg`
- [x] `STRINGART_APPLY` + `STRINGART_IMG` (macros/17_generator.cfg,
      kein eigenes 17_stringart.cfg nötig) + Watcher-Dispatch
      (`stringart_nonce`, Ausgabe in StringArt/, Job-Queue R160b)
- [x] MANUAL §5.14 + README-Zeile + PDF-Kapitel 5.14 + TESTANLEITUNG_130
- [x] Version .130 / R178, Commit (ZIP baut der Nutzer wie immer)

## Offene Punkte für die Feldrunde

- Ankerzahl 600 (Fixture) vs. 300 (Default): 600 auf 180 mm = 0,94 mm
  Abstand — logische Punkte auf dem Ring, drucktechnisch unkritisch;
  Default erst mal 300 (übersichtlicher im Menü), bis 600 gemessen.
- Fadenkreuzungen im selben Band verschmelzen (im Feldbeweis i. O.);
  Band-Reihenfolge = Blöcke wie im Fixture. Alternative round-robin
  nur falls der Feldtest Anlass gibt.
- Kein Purge-Turm (einfarbig). Farbwechsel mitten in den Bändern wäre
  denkbar (Bänder 1–3 Farbe A, 4–6 Farbe B) — zurückgestellt.
