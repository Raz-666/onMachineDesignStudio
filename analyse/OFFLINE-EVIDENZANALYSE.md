# Offline-Evidenzanalyse — Zwischenstand, kein Release

Der bestehende experimentelle `r2_offline.py report` erzeugt zusätzlich
`analysis.evidence` (Schema `r2-evidence/1`). Die Auswertung nutzt denselben
konservativen Shadow-Zustand wie der übrige Report. Sie liest einen privaten
Snapshot; die Originaldatei und ein bereits vorhandenes Ziel werden nicht
überschrieben. Kein Watcher und kein Drucker werden angesprochen.

- Explizite `EXCLUDE_OBJECT_*`-Namen erhalten stabile dateilokale Kennungen und
  Zähler; widersprüchliche bzw. offene Bereiche erzeugen Warnungen. Das sind
  keine geometrisch identifizierten Bauteile.
- Schichtkommentare und `LAYER_MARK` werden getrennt gezählt. Die numerierten
  Ereignisgrenzen sind **keine** nachgewiesenen physischen Schichten oder
  bauteilbezogene Reihenfolge.
- Feature-Kommentare und `APPLY_TYPE` werden als unbestätigte Quelle mit
  Zeilennummer und bestehender Alias-Tabelle festgehalten. `SKIN` bleibt
  absichtlich zwischen Ober- und Unterseite mehrdeutig, unbekannte Namen
  bleiben unbekannt. Die Alias-Abdeckung ist nicht vollständig: zum Beispiel
  wird `InternalInfill` derzeit nicht erkannt.
- Nur bei bekanntem Anfang und Ende in XY und positivem bekannten E-Delta werden
  Längen, Umgrenzungen und geschlossene XY-Projektionen gezählt. Ein Reset,
  unbekannter Befehl, Retract, Travel, Rollen- oder Objektwechsel beendet den
  aktuellen Pfad. Fläche ist die Summe von projizierten Schleifenflächen, kein
  ermittelter Footprint, kein Lochmodell und kein physisches Volumen. Die
  Koordinaten sind logische G-Code-Werte, keine Maschinenmessung.
- Pattern-Kommentare sind Metadaten, **keine** geometrische Mustererkennung.
  Objektzahl, Gruppen, Marker und Metadaten sind begrenzt; Überschreitung
  bricht den Report vor Veröffentlichung ab. Warnungen sind auf 32 Einträge
  gekürzt; `warning_count` zählt auch ausgelassene Warnungen.
- Hypothetische `--assume-passive`-Befehle sind im Report ausgewiesen, nicht
  verifiziert und nicht für Ableitungen verwendbar.

`tools/test_r2_analysis.py` prüft synthetische Fälle und Gegenmutationen.
`analyse/testprotokolle/offline_evidence_field.log` enthält den Feldlauf auf
Kopien der drei komprimierten Fixtures. Die Annahmen dort ignorieren unter
anderem G28, T0 und Retracteffekte und sind ausdrücklich **keine Aussage**
über die reale Maschine. Bei konservativer Analyse sind wegen unbekannter
Makro-/Initialzustände für diese Fixtures keine Positionsverläufe rekonstruierbar.

Offen bleiben der produktive unveränderliche Datei-/Jobfluss einschließlich
aller Generator-/Watcher-/Startverträge, robuste Zustandsinitialisierung und
Befehlseffekte, vollständige Slicer-Aliase, Objekt-/Schichtrekonstruktion,
Mustererkennung, Tag-Geometrie-Vergleich und produktive Integration. Diese
Auswertung erledigt C1–C5 des MASTER-TODO nicht und ist nicht druckfreigegeben.
