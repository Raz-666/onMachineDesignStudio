#!/usr/bin/env python3
"""_ZScan + process(): Z-Hop mit XY-Reise, E=0 oder XY-Rueckzug.

Synthetische zwei Druck-Z-Ebenen (0.2/0.4), zwei Extrusionsmodi. Der einzige
Unterschied zwischen 'ohne E' und 'E null' ist bei M83 E0 bzw. bei M82 der
unveraenderte absolute E-Wert; physisch wird in beiden Faellen kein E bewegt.
R258 (Option B): der Fehlmarker ist GEFIXT - _ZScan emittiert nur noch bei
positivem E-Delta; die Probe belegt bei allen sechs Faellen fake_mark=False.
Alles passiert in TemporaryDirectory; es werden keine Befehle ausgefuehrt.
"""
from pathlib import Path
import hashlib
import sys
import tempfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
import r2_postproc as pp

CASES = [
    ('M83', 'ohne E', ''), ('M83', 'E null', ' E0'),
    ('M83', 'Rueckzug', ' E-0.2'),
    ('M82', 'ohne E', ''), ('M82', 'E null', ' E1'),
    ('M82', 'Rueckzug', ' E0.8'),
]
with tempfile.TemporaryDirectory(prefix='r2-zhop-eprobe-') as tmp:
    for mode, label, eword in CASES:
        # Extrusionswerte der nachfolgenden Druckbewegungen sind hier
        # festgelegt; fuer die untersuchte Zwischenbewegung ist ihre Wirkung
        # auf Position und E-Zustand klar angegeben.
        e1, e2 = ('E1', 'E1') if mode == 'M83' else ('E2', 'E3')
        travel = 'G1 X12 Y0' + eword
        text = (f'{mode}\nG90\n;TYPE:External perimeter\n'
                f'G1 X10 Y0 Z0.2 E1\nG0 Z0.4\n{travel}\n'
                f'G0 Z0.2\nG1 X20 Y0 {e1}\nG0 Z0.4\nG1 X30 Y0 {e2}\n')
        file = Path(tmp) / (mode + '-' + label.replace(' ', '-') + '.gcode')
        file.write_text(text, encoding='utf-8')
        before = hashlib.sha256(file.read_bytes()).hexdigest()
        result = pp.process(str(file))
        out = file.read_text(encoding='utf-8').splitlines()
        marks = [out[i+1] for i, line in enumerate(out[:-1]) if line == 'LAYER_MARK']
        info = next((line for line in out if line.startswith('_FILE_INFO ')), '')
        fake = travel in marks
        print(f'{mode:3} {label:8}: reported_layers={result["layers"]} '
              f'inserted={len(marks)} fake_mark_before_hop_move={fake}; '
              f'mark_before={marks}; {info}')
        assert fake == False, 'R258: hop move with E0/negative E must NEVER carry a layer mark (e_delta > 0 gate)'
        assert before != hashlib.sha256(file.read_bytes()).hexdigest(), 'process sollte nur die TEMP-Kopie veraendern'
