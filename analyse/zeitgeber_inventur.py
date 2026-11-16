#!/usr/bin/env python3
"""Lesende, heuristische delayed_gcode-/Aufrufinventur, keine Produktmutation.

Nur macros/*.cfg und menus/*.cfg; keine Interpretation von Jinja, Includes,
Quote-Kontext oder Kontrollfluss. Kommentare, die mit # oder ; anfangen, werden
ignoriert; Text in sonstigen Strings kann Fehlreferenzen erzeugen. Dynamische
IDs / Aufrufe aus Python oder anderen Dateien bleiben ausserhalb des Scopes.
Keine Erreichbarkeits- oder Laufzeitbehauptung.
"""
from collections import defaultdict
from pathlib import Path
import csv, re

root=Path(__file__).resolve().parents[1]
files=sorted((root/'macros').glob('*.cfg'))+sorted((root/'menus').glob('*.cfg'))
section_re=re.compile(r'^\s*\[delayed_gcode\s+([^\]\s]+)\]\s*$',re.I)
any_section_re=re.compile(r'^\s*\[')
ref_re=re.compile(r'\bUPDATE_DELAYED_GCODE\s+ID=([A-Za-z0-9_]+)(?=\s|$)',re.I)
initial_re=re.compile(r'^\s*initial_duration\s*:\s*(.*?)\s*$',re.I)
decl=[]; refs=defaultdict(list); dynamic=[]
for file in files:
    rel=file.relative_to(root).as_posix(); current=None
    for lineno,line in enumerate(file.read_text(encoding='utf8').splitlines(),1):
        stripped=line.strip()
        if not stripped or stripped.startswith(('#',';')):continue
        m=section_re.match(line)
        if m:
            current={'id':m.group(1),'file':rel,'line':lineno,'initial':''};decl.append(current)
        elif any_section_re.match(line):current=None
        if current:
            m=initial_re.match(line)
            if m:current['initial']=m.group(1)
        if 'UPDATE_DELAYED_GCODE' in line.upper():
            matches=list(ref_re.finditer(line))
            if not matches:dynamic.append(f'{rel}:{lineno}')
            for match in matches:refs[match.group(1)].append(f'{rel}:{lineno}')
ids={x['id'] for x in decl}
path=root/'analyse/ZEITGEBER-INVENTAR.tsv'
with path.open('w',encoding='utf8',newline='') as out:
    w=csv.writer(out,delimiter='\t',lineterminator='\n')
    w.writerow(('id','definition','initial_duration_roh','textreferenzen_anzahl','textreferenzen'))
    for d in decl:
        r=refs.get(d['id'],[])
        w.writerow((d['id'],f"{d['file']}:{d['line']}",d['initial'],len(r),'; '.join(r)))
print(f'Untersuchte CFG-Dateien={len(files)}, delayed_gcode-Sektionen={len(decl)}, '
      f'Duplikatnamen={len(decl)-len(ids)}, statische_Referenzen={sum(map(len,refs.values()))}')
print('Ohne Textreferenz (nicht gleich ungenutzt):',', '.join(d['id'] for d in decl if not refs.get(d['id'])) or '-')
print('IDs referenziert, hier nicht definiert:',', '.join(sorted(set(refs)-ids)) or '-')
print('Dynamische/unerkannte Aufrufe:',', '.join(dynamic) or '-')
print('Initial duration explizit:',', '.join(f"{d['id']}={d['initial']}" for d in decl if d['initial']) or '-')
print('Scopes/Grenzen: nur macros/*.cfg + menus/*.cfg; kein Jinja-/Zeitablauf/Hardware-Check.')
