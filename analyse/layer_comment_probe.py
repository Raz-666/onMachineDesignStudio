#!/usr/bin/env python3
"""Metamorphe Schicht-/SKIN-Probe: identische Bewegungen, nur Kommentare variieren.

Ausfuehrung ausschliesslich auf temporaeren synthetischen Dateien. Die Soll-
semantik von SKIN ist ohne Modell-/Slicerbeweis mehrdeutig; hier wird nur die
Abhaengigkeit von optionalen Layer-Kommentaren nachgewiesen.
"""
from pathlib import Path
import sys
import tempfile

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
import r2_postproc as pp

with tempfile.TemporaryDirectory(prefix='r2-layer-comment-') as tmp:
    for label, comments in [('mit_kommentaren',True),('ohne_kommentare',False)]:
        lines=['M83','G90']
        for i in range(3):
            if comments: lines.append(';LAYER_CHANGE')
            lines += [f'G1 X0 Y{i*2}', ';TYPE:WALL-OUTER',
                      f'G1 X20 Y{i*2} Z{0.2*(i+1):.1f} E0.6',
                      ';TYPE:SKIN',f'G1 X0 Y{i*2+1} E0.6']
        f=Path(tmp)/(label+'.gcode'); f.write_text('\n'.join(lines)+'\n')
        res=pp.process(str(f)); output=f.read_text().splitlines()
        info=next((x for x in output if x.startswith('_FILE_INFO ')),'')
        skin=[output[i+1] for i,x in enumerate(output) if x == ';TYPE:SKIN']
        marks=[i for i,x in enumerate(output) if x=='LAYER_MARK']
        print(label,'physical_z_levels=[0.2,0.4,0.6]',
              'method=',res['method'],'reported_layers=',res['layers'],
              'inserted_marks=',len(marks),'skin=',skin,'info=',info)
