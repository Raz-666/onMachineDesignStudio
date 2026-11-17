# Analyse-Unterlagen

Aktueller Einstieg: [Release-Gap-Matrix](RELEASE-GAP-MATRIX.md) gegen `origin/main` `8ea17fc` (17.11.2026). Der [Gesamtbericht und die Entscheidungsvorlage](GESAMTBERICHT-UND-ENTSCHEIDUNGSVORLAGE.md) sind ein historischer Snapshot vor den späteren Merge-PRs; Detail- und Weiterarbeitsberichte sind gemäß ihren Commit-Ständen zu lesen. Weitere Dispositionen, Proben und Testprotokolle liegen in diesem Verzeichnis. Diese Analyse erteilt keine Freigabe für Produktänderungen oder Druckerbewegungen.

## Quellen und Reproduzierbarkeit

Die vom Nutzer bereitgestellten Originaluploads und der Übergabe-Snapshot werden **nicht** im öffentlichen Git-Repository veröffentlicht. Ihre Namen und Prüfsummen stehen in `uebergabe-quellen/SHA256SUMS`. Pfade zu `uebergabe-quellen/` in Berichten und Skripten bezeichnen lokale Dateien, die für eine Wiederholung gegebenenfalls separat bereitgestellt und gegen die Prüfsummen verifiziert werden müssen. Einige Auswertungen enthalten daraus entnommene Textstellen und Befunde. Die Analyseergebnisse und Testlogs werden mit diesem Pull Request veröffentlicht.

Ebenso bleibt die unveränderte Klipper-Parserdatei `klipper-referenz/gcode.py` eine lokale, nicht mitgelieferte Referenz; Quelle, Commit und SHA-256 stehen in `klipper-referenz/QUELLE.md`. Einzelne Proben benötigen diese Datei sowie Jinja2 und funktionieren ohne sie nicht. Testprotokolle beschreiben die tatsächlich verwendeten Grundlagen und die Grenzen der jeweiligen Prüfung.
