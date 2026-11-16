#!/usr/bin/env python3
"""Lesende, statische CFG-Textinventur von SET_OVERRIDE_VALUE-Aufrufen.
Keine Jinja-Auswertung, keine Aussage ueber Erreichbarkeit oder abschliessende
Control-Flow-Analyse. Kommentare am Zeilenbeginn ausgenommen; Zeichenfolgen,
Zweige und Include-/Visibility-Kontext beduerfen manueller Nachpruefung.
"""
from collections import Counter
from pathlib import Path
import csv,re
root=Path(__file__).resolve().parents[1]
scalar=set('bed bed_after hotend_first hotend_after pa retract_len retract_speed unretract_speed accel ironing_flow pa_smooth flow velocity min_cruise square_corner fan'.split())
rows=[]
paths=sorted((root/'macros').glob('*.cfg'))+sorted((root/'menus').glob('*.cfg'))
for path in paths:
    section=''
    for no,line in enumerate(path.read_text(encoding='utf8').splitlines(),1):
        stripped=line.strip()
        if stripped.startswith('#'):continue
        if stripped.startswith('[') and stripped.endswith(']'):section=stripped[1:-1]
        match=re.search(r'\bSET_OVERRIDE_VALUE\s+NAME=([^\s]+)',line)
        if not match:continue
        name=match.group(1);dynamic=('{' in name or '}' in name)
        if dynamic:kind='dynamisch_ungeklaert'
        elif name in scalar:kind='skalar_betroffener_setterzweig'
        elif name.startswith('feat_') or name in ('outer_wall','outer_wall_accel','support','support_accel','ironing_speed'):kind='feature_oder_alias'
        else:kind='sonstige'
        rows.append([str(path.relative_to(root)),no,section,name,kind,stripped])
out=root/'analyse/OVERRIDE-AUFRUFE.tsv'
with out.open('w',encoding='utf8',newline='') as f:
    writer=csv.writer(f,delimiter='\t');writer.writerow(['datei','zeile','sektion','name','klasse','quelltext']);writer.writerows(rows)
print('Geltungsbereich: macros/*.cfg und menus/*.cfg; Textstellen, keine Laufzeiterreichbarkeit.')
print('CFG-Dateien:',len(paths),'Kandidatenzeilen:',len(rows))
print('Klassen:',dict(sorted(Counter(x[4] for x in rows).items())))
print('Skalare Aufrufe je NAME:',dict(sorted(Counter(x[3] for x in rows if x[4]=='skalar_betroffener_setterzweig').items())))
print('Dynamische NAMEs:',dict(sorted(Counter(x[3] for x in rows if x[4]=='dynamisch_ungeklaert').items())))
print('TSV:',out.relative_to(root))
