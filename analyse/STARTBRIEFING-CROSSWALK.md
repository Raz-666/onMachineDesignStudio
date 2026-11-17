# Startbriefing: Zeilen-Crosswalk (Disposition vorsortiert, Stand 2026-11-17)

**Dies ist ein Vorsortierungsschritt, keine Abnahme und keine neue Aufgabenliste.**
Jede der 521 indexierten Aufzählungszeilen aus `analyse/STARTBRIEFING-QUELLENINDEX.tsv`
(`SB-L*`) erhält in `analyse/STARTBRIEFING-CROSSWALK.tsv` (521 Zeilen + Kopf)
eine Disposition, die **aus dem Abschnitt geerbt** wird, in dem die Zeile im
Gemini-Briefing steht. Die Anker sind die Zeilenbereiche und der
P/G/O/E-Schlüssel aus `analyse/STARTBRIEFING-ANFORDERUNGSABGLEICH.md`.

## Was der Crosswalk leistet — und was nicht

- Jede Zeile trägt: Original-ID, Zeilennummer, unveränderten Originaltext,
  Disposition, deren Bedeutung, Quellverweis, das erbende Abschnittspaar und
  den ausdrücklichen Vermerk `vererbt_von_Abschnitt; nicht einzeln verifiziert`.
- **Keine Zeile ist einzeln verifiziert.** Die Disposition sagt nur, wie der
  Abgleich den naheliegenden Anforderungsteil bewertet hat. Sie ersetzt
  weder den Einzelabgleich noch einen Akzeptanztest, eine Hardwarefreigabe
  oder eine Nutzerentscheidung.
- Der `abschnitt`-Spalte des Quellenindexes wird **nicht** vertraut: ihr
  Überschriften-Tracker blieb an bulletlosen Zwischenzeilen hängen (z. B.
  Zeilen 81–128 als „1 ROLLE UND ARBEITSWEISE“ geführt, obwohl §2-Inhalt;
  Zeilen 1088–1095 als „7“, obwohl §8-Inhalt). Deshalb ankert der Crosswalk
  auf den Zeilenbereichen des gruppierten Abgleichs. Ohne die Original-Quelle
  (nicht im Repo) ist eine feinere Zuordnung nicht belegbar — Lücken (Gaps)
  wären als `O` markiert worden; es gab **keine** (521/521 abgedeckt).
- Anforderungen wurden nicht umgeschrieben, gelöscht oder neu priorisiert.

## Summen nach Disposition

| Disposition | Zeilen | Bedeutung |
|---|---:|---|
| `E` | 20 | beschränkter Arbeitsschritt belegt; keine übergreifende Produktabnahme |
| `P` | 175 | untersuchter Teil vorhanden, insgesamt unvollständig/unverifiziert |
| `G` | 62 | belegte konkrete Abweichung/Spannung, nicht zwingend universell |
| `O` | 53 | noch offen/keine hinreichende Aussage |
| `P/G` | 193 | überwiegend vorhanden; belegte konkrete Abweichungen enthalten |
| `G/P` | 18 | Abweichung belegt; Teil vorhanden |

## Nutzung

Der Crosswalk ersetzt die `Einzelzuordnung offen`-Lücke des Quellenindexes
nicht. Für ein Release braucht es weiterhin: je Zeile einen Code-/Test- oder
Entscheidungsreferenz, die Zusammenführung mit `MASTER-TODO.md` nach
gesonderter Freigabe und den Nutzerentscheid bei den `O`- und `G`-Zeilen.
Reproduzieren: `python3 analyse/crosswalk_disposition.py`
( liest nur den Index und schreibt das TSV neu).
