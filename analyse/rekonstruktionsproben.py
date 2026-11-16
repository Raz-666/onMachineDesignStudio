#!/usr/bin/env python3
"""Nicht-invasive Wiederholung ausgewaehlter frueherer Analyseproben.

Ausschliesslich synthetische, temporaere Dateien; Queue-Probe nur im Speicher.
Kein Drucker, kein Moonraker, kein Aendern des Produktbaums. Die Ergebnisse
belegen genau die Testfaelle, nicht allgemeines Verhalten aller G-Code-Dateien.
"""
import ast
import hashlib
import struct
import sys
import tempfile
import threading
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
import r2_postproc as pp

print('=== _GeomScan: Modal-Gegenproben ===')
for name, lines in {
    'G92 reset': ['M82', 'G1 X10 Y0 F1200 E1', 'G92 E0', 'G1 X20 Y0 E0.5'],
    'ohne Reset': ['M82', 'G1 X10 Y0 F1200 E1', 'G1 X20 Y0 E1.5'],
    'relative XYZ': ['G91', 'M83', 'G1 X10 Y0 F1200 E1', 'G1 X10 Y0 E1'],
}.items():
    g = pp._GeomScan()
    for i, line in enumerate(lines): g.step(i, i, line)
    print(f'{name}: x={g.x:g}, e_run={g.e_run:g}, active_poly_length={g._p_len:g}')

with tempfile.TemporaryDirectory(prefix='r2-reaudit-') as tmp:
    root = Path(tmp)
    print('\n=== process: Quelldatei und TAG/optionaler Retract-Fix ===')
    src = ('; R2-POSTPROC v5\n_FILE_INFO RETRACT=slicer\nM83\n'
           'G1 F4800 E-5.2\nG0 X50 Y50 F9000\nG1 F1800 E5.2\n'
           'G1 X60 Y50 E0.5 F1800\n')
    for rewrite, dry in [(False,False),(True,False),(True,True)]:
        f = root / f'tag-{rewrite}-{dry}.gcode'; f.write_text(src)
        before = hashlib.sha256(f.read_bytes()).hexdigest()
        result = pp.process(str(f), retract_rewrite=rewrite, dry=dry)
        after = f.read_text()
        print(f'rewrite={rewrite} dry={dry}: skipped={result["skipped"]} '
              f'pairs={result["retract_pairs"]} unchanged={before == hashlib.sha256(f.read_bytes()).hexdigest()} '
              f'G10={"G10" in after.splitlines()} G11={"G11" in after.splitlines()} '
              f'info_slicer={"_FILE_INFO RETRACT=slicer" in after}')
    f = root/'untagged.gcode'; f.write_text(';TYPE:External perimeter\nG90\nM83\nG1 X0 Y0 Z0.2\nG1 X10 Y0 E1 F1200\n')
    before = f.read_bytes(); result = pp.process(str(f))
    print('untagged default:', 'changed=', before != f.read_bytes(), 'tagged=',result['tagged'],
          'APPLY_TYPE=', b'APPLY_TYPE' in f.read_bytes())

    print('\n=== STL: M82 gegen M83 nach ausgefiltertem Support ===')
    for mode, a, b in [('M82','E1','E2'),('M83','E1','E1')]:
        f = root / f'stl-{mode}.gcode'
        f.write_text(f'{mode}\nG90\nG0 X0 Y0 Z0.2\n;TYPE:Support\nG1 X20 Y0 {a}\n;TYPE:External perimeter\nG1 X40 Y0 {b}\n')
        rel, info = pp._stl_export(tmp,f.name); data = (root / rel).read_bytes(); ys=[]
        for n in range(info['tris']):
            v = struct.unpack_from('<12fH',data,84+50*n)
            ys.extend((v[4],v[7],v[10]))
        print(mode, 'width_mm=',round(max(ys)-min(ys),6),'excluded=',info['excl'],'boxes=',info['boxes'])
    print('\n=== STL: Top+Innenwand, mit und ohne ungenutztes Outer-Tag ===')
    base=('M83\nG90\nG0 X0 Y0 Z0.2\n;TYPE:Top surface\nG1 X20 Y0 E1\n'
          ';TYPE:Inner wall\nG1 X20 Y20 E1\n')
    for label,tail in [('ohne',''),('mit',';TYPE:External perimeter\n')]:
        f=root/f'relax-{label}.gcode'; f.write_text(base+tail)
        _,info=pp._stl_export(tmp,f.name)
        print(label,{k:info[k] for k in ('relaxed','boxes','incl_mm','excl','tris')})

    print('\n=== Polygon-Autoupgrade: Wipe in M82 gegen M83 ===')
    for mode, vals in [('M82',('E1','E2','E1.8')),('M83',('E1','E1','E-0.2'))]:
        f=root/f'polygon-{mode}.gcode'
        f.write_text(f'{pp.TAG}\n{mode}\nG90\nEXCLUDE_OBJECT_DEFINE NAME=o CENTER=5,5\n'
                     'EXCLUDE_OBJECT_START NAME=o\n'
                     f'G1 X0 Y0 {vals[0]}\nG1 X10 Y10 {vals[1]}\nG1 X100 Y100 {vals[2]}\n'
                     'EXCLUDE_OBJECT_END NAME=o\n')
        before=f.read_bytes(); changed=pp._upgrade_center_excludes(str(f))
        define=next(x for x in f.read_text().splitlines() if x.startswith('EXCLUDE_OBJECT_DEFINE'))
        print(mode,'upgraded=',changed,'source_changed=',before != f.read_bytes(),define)

print('\n=== Queue-Kill: isolierter AST mit injiziertem Flag ===')
tree=ast.parse((ROOT/'tools/r2_postproc.py').read_text())
watch=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='watch')
worker=next(n for n in watch.body if isinstance(n,ast.FunctionDef) and n.name=='_job_worker')
state={'queue':[('Testjob','test:1',lambda:None,[],0,0,0,60)],'keys':{'test:1'},
       'busy':False,'lock':threading.Lock(),'thread':None,'zombie':None,'zombie_notice':0,'kill':'SKIP'}
env={'_JOB_STATE':state,'_genq_push':lambda:None}
exec(compile(ast.fix_missing_locations(ast.Module(body=[worker],type_ignores=[])),'tools/r2_postproc.py','exec'),env)
try:
    env['_job_worker']()
except UnboundLocalError as exc:
    print(type(exc).__name__,str(exc),'queue=',len(state['queue']),'keys=',sorted(state['keys']))
else:
    raise AssertionError('Erwartete Probeabweichung nicht eingetreten')
print('Realitaet: Erreichbarkeit des gesetzten Kill-Zustands nicht bewiesen.')
