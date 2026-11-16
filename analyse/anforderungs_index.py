#!/usr/bin/env python3
"""Quellenindizes, keine semantische Anforderungs-/Abnahmematrix."""
from pathlib import Path
import csv
import re

root=Path(__file__).resolve().parents[1]; src=root/'analyse/uebergabe-quellen'
brief=src/'R2_Vollstaendiges_Startbriefing_Coding-KI_finalizedByGemini.txt'
lines=brief.read_text(encoding='utf8').splitlines(); rows=[]; section=''; i=0
while i<len(lines):
    line=lines[i]
    m=re.match(r'^(\d{1,2}(?:\.\d+)*)\.?(?:\s+)([A-ZÄÖÜ][A-ZÄÖÜ /,()–-]+)$',line.strip())
    if m:section=m.group(1)+' '+m.group(2)
    if line.startswith('- '):
        number=i+1; text=[line[2:].strip()];i+=1
        while i<len(lines) and (lines[i].startswith('  ') or lines[i].startswith('\t')) and not re.match(r'^\s*[-*] ',lines[i]):
            if not lines[i].strip():break
            text.append(lines[i].strip());i+=1
        rows.append((f'SB-L{number}',section,number,' '.join(text),'Einzelzuordnung offen'));continue
    i+=1
with (root/'analyse/STARTBRIEFING-QUELLENINDEX.tsv').open('w',encoding='utf8',newline='') as f:
    w=csv.writer(f,delimiter='\t',lineterminator='\n');w.writerow(('quellen_id','abschnitt','zeile','text','pruefstatus'));w.writerows(rows)
master=src/'GCode_Reverse_Engineering_Masterkonzept.md'
sections=[]
for n,line in enumerate(master.read_text(encoding='utf8').splitlines(),1):
    if re.match(r'^#{1,3}\s',line): sections.append((n,line.strip()))
with (root/'analyse/MASTERKONZEPT-ABSCHNITTE.tsv').open('w',encoding='utf8',newline='') as f:
    w=csv.writer(f,delimiter='\t',lineterminator='\n');w.writerow(('zeile','ueberschrift','status'));w.writerows((n,s,'Einzelzuordnung offen') for n,s in sections)
print('Startbriefing-Aufzaehlungen:',len(rows),'Masterkonzept-Ueberschriften:',len(sections))
