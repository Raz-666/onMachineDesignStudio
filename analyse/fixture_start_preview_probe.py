#!/usr/bin/env python3
"""Fixture-Startreihenfolge und Preview nur offline/auf temporaeren Kopien.

Originale gzip-Dateien werden lesend geoeffnet und vorher/nachher gehasht.
process() schreibt nur eine temp. Kopie. _moonraker_status wird durch ein
Stub ersetzt; _preview_script erzeugt lediglich Text, kein Netzwerk und keine
Ausfuehrung. Statik dieser Faelle ist kein Live-Zeitablauf/Hardwarebeweis.
"""
from pathlib import Path
from collections import Counter
import gzip, hashlib, re, shutil, sys, tempfile
root=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(root/'tools'))
import r2_postproc as pp
pattern=re.compile(r'^(PRINT_START|START_PRINT|_FILE_INFO|LAYER_MARK)(?:\s|$)',re.I)
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def collect(path):
    counts=Counter(); first={}
    with path.open('rt',encoding='utf8',errors='replace') as f:
        for line_no,line in enumerate(f,1):
            m=pattern.match(line.strip())
            if m:
                name=m.group(1).upper();counts[name]+=1
                if name not in first:first[name]=(line_no,line.strip())
    return counts,first
with tempfile.TemporaryDirectory(prefix='r2-start-preview-') as temp:
    for fixture in sorted((root/'testfixtures').glob('*.gcode.gz')):
        initial_hash=sha(fixture)
        path=Path(temp)/fixture.name.removesuffix('.gz')
        with gzip.open(fixture,'rb') as src, path.open('wb') as dst:shutil.copyfileobj(src,dst)
        initial, start=collect(path)
        result=pp.process(str(path))
        final, after=collect(path)
        assert sha(fixture)==initial_hash
        def fmt(d):
            return {k:(n, re.search(r'\bTOTAL_LAYERS=(\d+)',line).group(1)
                       if re.search(r'\bTOTAL_LAYERS=(\d+)',line) else '-') for k,(n,line) in d.items()}
        print(f'{fixture.name}: sha256={initial_hash}, gzip_unveraendert=True')
        print('  source=',dict(initial),'erstes=',fmt(start))
        print('  temp_nach_process=',dict(final),'erstes=',fmt(after),
              'summary=',{k:result.get(k) for k in ('skipped','method','layers','marks_added')})
        if fixture.name=='bigrose_020mm.gcode.gz':
            assert start['PRINT_START'][0] == 173
            assert after['_FILE_INFO'][0]<after['PRINT_START'][0]
            assert re.search(r'\bTOTAL_LAYERS=250\b',after['PRINT_START'][1])
            raw=after['_FILE_INFO'][1]
            original_status=pp._moonraker_status
            try:
                for state,mode in [('printing','waiting'),('printing','printing'),('standby','idle')]:
                    pp._moonraker_status=lambda state=state,mode=mode:{'print_stats':{'state':state},'gcode_macro _STATE':{'mode':mode}}
                    lines,_=pp._preview_script(str(path))
                    replays=[line for line in lines if line.startswith('_FILE_INFO')]
                    assert bool(replays)==(mode!='printing')
                    assert all(line==raw for line in replays)
                    print(f'  preview_stub print_stats={state}, mode={mode}: _FILE_INFO_replay={bool(replays)}')
            finally:pp._moonraker_status=original_status
            # Identischer vorher bestaetigter Auswahl-Push vorausgesetzt. Der
            # Dedupe-Check betrachtet Dateikey, Alter, ACK und PREVIEW.name;
            # der gesetzte _STATE.total_layers=0 ist eine Stub-Vorbedingung.
            previous=pp._preview_last.copy()
            original_status=pp._moonraker_status
            try:
                pp._preview_remember(path.name, str(path), True)
                at=pp._preview_last['t']+1
                pp._moonraker_status=lambda:{'gcode_macro _PREVIEW':{'name':path.name},
                                              'gcode_macro _STATE':{'total_layers':0}}
                same=pp._preview_dup_skip(path.name,str(path),now=at)
                pp._moonraker_status=lambda:{'gcode_macro _PREVIEW':{'name':'another.gcode'},
                                              'gcode_macro _STATE':{'total_layers':0}}
                changed=pp._preview_dup_skip(path.name,str(path),now=at)
                assert same and not changed
                print('  dedupe_stub: ACK, gleicher Dateikey & PREVIEW.name, 1s, STATE.total_layers=0 -> skip=',same,
                      '; anderer PREVIEW.name -> skip=',changed)
            finally:
                pp._preview_last.clear();pp._preview_last.update(previous)
                pp._moonraker_status=original_status
