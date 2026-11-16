#!/usr/bin/env python3
"""Lesende Zaehlinventur der Bigrose-Fixture, keine Sollschicht-Behauptung.

Zahl der ;LAYER_CHANGE, LAYER_MARK, ;Z: und exemplarische Z-tragende G0/G1
pro Markerabschnitt; keine Analyse realer Maschinenbewegung oder Extrusionsmenge.
"""
from pathlib import Path
import gzip,hashlib,re,sys
root=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(root/'tools'))
import r2_postproc as pp
p=root/'testfixtures/bigrose_020mm.gcode.gz'
sha=hashlib.sha256(p.read_bytes()).hexdigest()
with gzip.open(p,'rt',encoding='utf8',errors='replace') as f: lines=f.readlines()
marks=[i for i,s in enumerate(lines) if s.strip()=='LAYER_MARK']
changes=[i for i,s in enumerate(lines) if s.strip().upper()==';LAYER_CHANGE']
zcomments=[(i,s.strip()) for i,s in enumerate(lines) if re.match(r'^\s*;\s*Z\s*:',s,re.I)]
print('sha256=',sha,'header=',lines[2].strip())
print('LAYER_CHANGE=',len(changes),'LAYER_MARK=',len(marks),';Z-Kommentare=',len(zcomments))
assert len(marks)==251 and len(changes)==251
prev=-1
for ordinal,i in enumerate(marks,1):
    local=[x for x in changes if prev<x<i]
    if len(local)!=1:print('MARKER MIT NICHT GENAU EINEM VORHERIGEN LAYER_CHANGE:',ordinal,i+1,len(local))
    prev=i
for ordinal in (1,2,3,249,250,251):
    i=marks[ordinal-1]; end=marks[ordinal] if ordinal<len(marks) else len(lines)
    zvals=[]; xy_e=0
    for s in lines[i+1:end]:
        m=pp.MOVE_RE.match(s.strip())
        if m:
            pvals=pp.parse_params(m.group(2))
            if 'Z' in pvals:zvals.append(pvals['Z'])
            if 'E' in pvals and ('X' in pvals or 'Y' in pvals):xy_e+=1
    prior=[s for j,s in zcomments if (marks[ordinal-2] if ordinal>1 else -1)<j<i]
    print(f'Abschnitt {ordinal}: Markerzeile={i+1}, vorherige_Z-Kommentare={prior[-1:]}, '
          f'Z-haltige_G0_G1={len(zvals)}, erste_Z={zvals[:3]}, letzte_Z={zvals[-3:]}, '
          f'Z_minmax={(min(zvals),max(zvals)) if zvals else None}, XY_mit_E={xy_e}')
assert hashlib.sha256(p.read_bytes()).hexdigest()==sha
print('Gzip unveraendert. Z-Werte nur als geschriebene Parameter; Modi und Bedeutung der Layerzahl nicht abgeleitet.')
