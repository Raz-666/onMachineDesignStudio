#!/usr/bin/env python3
"""Build STARTBRIEFING-CROSSWALK.tsv: per-line disposition for all 521 index rows.

This is a *pre-sort*, not an acceptance matrix. Every of the 521 indexed
source lines in STARTBRIEFING-QUELLENINDEX.tsv inherits the disposition of the
section the (Gemini) source document places it in, using the line ranges and
the P/G/O/E key from analyse/STARTBRIEFING-ANFORDERUNGSABGLEICH.md.

The index's own `abschnitt` column is kept as recorded but is NOT used for the
disposition: its heading tracker stops at lines without bullets (e.g. rows
SB-L81..SB-L128 are §2 content while labelled `1 ROLLE UND ARBEITSWEISE`, and
rows at 1088..1095 are §8 content labelled `7 ...`). Line ranges from the
grouped abgleich are the anchor instead.

Nothing here verifies an individual line. pruefstatus_neu is always
'vererbt_von_Abschnitt; nicht einzeln verifiziert' and the original text is
carried through unchanged. This file must not be read as a release sign-off.
"""
import csv
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INDEX = ROOT / 'analyse/STARTBRIEFING-QUELLENINDEX.tsv'
OUT = ROOT / 'analyse/STARTBRIEFING-CROSSWALK.tsv'

# (von, bis, Sektion, Code) — ranges from analyse/STARTBRIEFING-ANFORDERUNGSABGLEICH.md
RANGES = [
    (7, 68, 'SB §0–1 (7–68)', 'E'),
    (70, 130, 'SB §2 (70–130)', 'P'),
    (132, 190, 'SB §3 (132–190)', 'E'),
    (192, 234, 'SB §4 (192–234)', 'P'),
    (242, 329, 'SB §5.1–5.3 (242–329)', 'P'),
    (330, 398, 'SB §5.4–5.7 (330–398)', 'G'),
    (399, 435, 'SB §5.8–5.9 (399–435)', 'P/G'),
    (436, 478, 'SB §5.10–5.12 (436–478)', 'G'),
    (479, 548, 'SB §5.13–5.14 (479–548)', 'P'),
    (549, 653, 'SB §5.15–5.17 (549–653)', 'P/G'),
    (654, 707, 'SB §5.18–5.20 (654–707)', 'G'),
    (708, 987, 'SB §5.21 (708–987)', 'P/G'),
    (988, 1020, 'SB §5.22 (988–1020)', 'P/G'),
    (1022, 1044, 'SB §6 (1022–1044)', 'P'),
    (1046, 1076, 'SB §7 (1046–1076)', 'P/G'),
    (1078, 1102, 'SB §8 (1078–1102)', 'P'),
    (1104, 1150, 'SB §9 (1104–1150)', 'P'),
    (1151, 1180, 'SB §10 (1151–1180)', 'P/G'),
    (1182, 1206, 'SB §11 (1182–1206)', 'P'),
    (1208, 1265, 'SB §12 (1208–1265)', 'P'),
    (1267, 1278, 'SB §13 (1267–1278)', 'P'),
    (1280, 1310, 'SB §14 (1280–1310)', 'P'),
    (1311, 1381, 'SB §14.1 (1311–1381)', 'O'),
    (1382, 1451, 'SB §14.2 (1382–1451)', 'P/G'),
    (1452, 1509, 'SB §14.3–14.4 (1452–1509)', 'O'),
    (1510, 1538, 'SB §14.5–14.6 (1510–1538)', 'P/G'),
    (1540, 1567, 'SB §15 (1540–1567)', 'O'),
    (1569, 1647, 'SB §16–17 (1569–1647)', 'P'),
    (1649, 1694, 'SB §18–19 (1649–1694)', 'G/P'),
]

KEY = {
    'E': 'beschränkter Arbeitsschritt belegt; keine übergreifende Produktabnahme',
    'P': 'untersuchter Teil vorhanden, insgesamt unvollständig/unverifiziert',
    'G': 'belegte konkrete Abweichung/Spannung, nicht zwingend universell',
    'O': 'noch offen/keine hinreichende Aussage',
    'P/G': 'überwiegend vorhanden; belegte konkrete Abweichungen enthalten',
    'G/P': 'Abweichung belegt; Teil vorhanden',
}
SOURCE = ('analyse/STARTBRIEFING-QUELLENINDEX.tsv; '
          'analyse/STARTBRIEFING-ANFORDERUNGSABGLEICH.md (Schlüssel)')
NOTICE = 'vererbt_von_Abschnitt; nicht einzeln verifiziert'


def classify(line_number):
    for start, end, section, code in RANGES:
        if start <= line_number <= end:
            return section, code
    return 'gap (keine Abgleich-Zeile)', 'O'


def main():
    with INDEX.open(encoding='utf-8', newline='') as handle:
        rows = list(csv.DictReader(handle, delimiter='\t'))
    out_rows = []
    counts = {}
    gaps = []
    for row in rows:
        line = int(row['zeile'])
        section, code = classify(line)
        if 'gap' in section:
            gaps.append(row['quellen_id'])
        counts[code] = counts.get(code, 0) + 1
        out_rows.append({
            'quellen_id': row['quellen_id'],
            'zeile': row['zeile'],
            'text': row['text'],
            'disposition': code,
            'disposition_bedeutung': KEY[code],
            'quelle': SOURCE,
            'abschnitt_vererbt': section,
            'pruefstatus_ursprung': row['pruefstatus'],
            'pruefstatus_neu': NOTICE,
        })
    with OUT.open('w', encoding='utf-8', newline='') as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=['quellen_id', 'zeile', 'text', 'disposition',
                        'disposition_bedeutung', 'quelle',
                        'abschnitt_vererbt', 'pruefstatus_ursprung',
                        'pruefstatus_neu'],
            delimiter='\t', lineterminator='\n')
        writer.writeheader()
        writer.writerows(out_rows)
    print('rows:', len(out_rows))
    for code in sorted(counts):
        print('%s\t%d' % (code, counts[code]))
    print('gaps:', gaps)


if __name__ == '__main__':
    main()
