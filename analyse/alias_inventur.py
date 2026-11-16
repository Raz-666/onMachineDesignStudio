#!/usr/bin/env python3
"""Quellbegriffe und Code-Mappings als Rohindex; keine Ground Truth.

Enthaelt Master-Union-Zeilen mit Backtick-Begriffen und 12 Familienlisten.
Ein Begriff kann Preview, interne Rolle oder Marker sein, nicht zwingend ein
realer ;TYPE:-Kommentar. Vollstaendige Master-Union separat als Kontextindex.
"""
from pathlib import Path
import csv
import re
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
import r2_postproc as pp
src=ROOT/'analyse/uebergabe-quellen/FeatureErkennung.md'
lines=src.read_text(encoding='utf-8').splitlines(); rows=[]; roles=[]; family=''; in_block=False
for num,line in enumerate(lines,1):
    if 9 <= num < 144:
        if line.startswith('## '):family=line[3:].strip()
        if line.startswith('| **'):
            cells=line.split('|'); role=cells[1].strip().replace('**',''); description=cells[2].strip()
            aliases=re.findall(r'`([^`]+)`',description)
            roles.append((num,family,role,description,' / '.join(aliases)))
            for alias in aliases:rows.append(('Master-Union',family,role,num,alias))
    if 146 <= num < 522:
        if line.startswith('## 2.'): family=line[3:].strip()
        if line.startswith('```'):in_block=not in_block;continue
        if in_block and line.strip():
            text=line.strip()
            if text.startswith(('Wenn ','plus ')) or text.endswith(':'): continue
            alias=re.split(r'\s+//|\s+=\s+',text,maxsplit=1)[0].strip()
            rows.append(('Familienliste',family,'',num,alias))
with (ROOT/'analyse/ALIASE-QUELLEN-CODE.tsv').open('w',encoding='utf-8',newline='') as f:
    w=csv.writer(f,delimiter='\t',lineterminator='\n')
    w.writerow(('Quelle','Familie_oder_Gruppe','Quellrolle','Zeile','Originaltext','lookup_type','canon_type','synthetisches_TYPE_RE','Hinweis'))
    for section,family,role,num,raw in rows:
        m=pp.TYPE_RE.match(';TYPE:'+raw)
        w.writerow((section,family,role,num,raw,pp._lookup_type(raw) or '',pp._canon_type(raw),m.group(1) if m else '',
                    'Quellenbegriff; realer Kommentar oder Sollwert nicht bestaetigt'))
    for raw,code in pp.TYPE_MAP.items():
        w.writerow(('TYPE_MAP code','R2','',148,raw,code,pp._canon_type(raw),raw,'Wirksamer Mapping-Eintrag'))
with (ROOT/'analyse/FEATURE-UNION-ROLLEN.tsv').open('w',encoding='utf8',newline='') as f:
    w=csv.writer(f,delimiter='\t',lineterminator='\n')
    w.writerow(('quellzeile','abschnitt','rollenbezeichnung','quelltext_zweite_spalte','backtick_begriffe'));w.writerows(roles)
print(f'{len(rows)} Quellbelege, {len(pp.TYPE_MAP)} wirksame TYPE_MAP-Eintraege; {len(roles)} Union-Zeilen, {sum(not r[4] for r in roles)} ohne Backtick')
