#!/usr/bin/env python3
"""Repo-Fixtures lesen, Prozessierung nur auf Temporaerkopien; keine Druckausgabe."""
from collections import Counter, defaultdict
from pathlib import Path
import csv
import gzip
import hashlib
import re
import shutil
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
import r2_postproc as pp

rows=[]
with tempfile.TemporaryDirectory(prefix='r2-fixtures-') as tmp:
    for archive in sorted((ROOT/'testfixtures').glob('*.gcode.gz')):
        sha=hashlib.sha256(archive.read_bytes()).hexdigest()
        src=Path(tmp)/(archive.name+'.raw'); dst=Path(tmp)/archive.name.removesuffix('.gz')
        with gzip.open(archive,'rb') as f, src.open('wb') as out: shutil.copyfileobj(f,out)
        shutil.copyfile(src,dst)
        tags=defaultdict(list); layer=0; obj=''; z=''; brim=[]; n=0
        with src.open('r',errors='replace') as f:
            for n,line in enumerate(f,1):
                s=line.strip()
                if pp.LAYER_COMMENT.match(line): layer+=1
                if s.startswith(';Z:'): z=s[3:]
                if s.startswith('EXCLUDE_OBJECT_START '):
                    m=re.search(r'\bNAME=(\S+)',s); obj=m.group(1) if m else ''
                elif s.startswith('EXCLUDE_OBJECT_END'): obj=''
                m=pp.TYPE_RE.match(line)
                if m:
                    name=m.group(1); tags[name].append(n)
                    if name.strip().lower()=='brim': brim.append((n,layer,z,obj))
        print('\n',archive.name,'lines=',n,'distinct_markers=',len(tags),'brim=',brim)
        res=pp.process(str(dst))
        print('summary:',{k:res.get(k) for k in ('skipped','tagged','layers','by_object','types','slicer','custom_groups','seq_warn')})
        direct=defaultdict(Counter); insert=Counter(); mismatch=[]
        with src.open('r',errors='replace') as a,dst.open('r',errors='replace') as b:
            old=a.readline(); previous=None
            for out in b:
                s=out.rstrip('\r\n')
                if old and s == old.rstrip('\r\n'):
                    m=pp.TYPE_RE.match(old); previous=m.group(1) if m else None
                    old=a.readline();continue
                kind=next((x for x in (pp.TAG,'_FILE_INFO','LAYER_MARK','APPLY_TYPE') if s==x or s.startswith(x+' ')),None)
                if kind:
                    insert[kind]+=1
                    if kind=='APPLY_TYPE' and previous:
                        m=re.search(r'\bTYPE=(\S+)',s)
                        if m:direct[previous][m.group(1)]+=1
                    previous=None;continue
                mismatch.append(s[:100]);break
            equal=not mismatch and not old and not a.readline()
        print('source_lines_equal_ignoring_eol=',equal,'inserted=',dict(insert),
              'gzip_unchanged=',sha==hashlib.sha256(archive.read_bytes()).hexdigest(),'mismatch=',mismatch)
        for name, positions in tags.items():
            mapping=', '.join(f'{k}:{v}' for k,v in sorted(direct[name].items()))
            rows.append((archive.name,sha,name,positions[0],len(positions),pp._canon_type(name),mapping))
            print(' ',name,'count=',len(positions),'canon=',pp._canon_type(name),'direct_apply=',mapping or '-')
with (ROOT/'analyse/FELDFIXTURE-TAGS.tsv').open('w',encoding='utf8',newline='') as f:
    w=csv.writer(f,delimiter='\t',lineterminator='\n')
    w.writerow(('fixture','gzip_sha256','alias','erste_zeile','anzahl','canon_funktion','apply_direkt_nach_kommentar'));w.writerows(rows)
print('\nFixture/Alias-Kombinationen:',len(rows))
