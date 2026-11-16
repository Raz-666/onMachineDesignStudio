#!/usr/bin/env python3
"""Originaltemplates PRINT_START/_LIVE_RESET rendern und Ausgabeordnung pruefen.

Jinja-Ausgaben werden NICHT ausgefuehrt. Der kleine Auswertungsmechanismus
verfolgt ausschliesslich total_layers und ersetzt dabei den ausgegebenen
_LIVE_RESET-Aufruf durch dessen separat gerenderten Originaltemplate-Text.
Kein vollstaendiges Klippermodell und keine Druckerbefehle.
"""
from pathlib import Path
from types import SimpleNamespace
import sys
import tempfile
from jinja2 import Environment
root=Path(__file__).resolve().parents[1]
sys.path.insert(0, str(root/'tools'))
import r2_postproc as pp
env=Environment(variable_start_string='{',variable_end_string='}')
def get(file,name):
    text=(root/file).read_text(encoding='utf8')
    sec=text.split('[gcode_macro '+name+']',1)[1].split('\n[',1)[0]
    return env.from_string(sec.split('\ngcode:\n',1)[1])
class Obj(dict):
    def __getattr__(self,name):
        try:return self[name]
        except KeyError as exc:raise AttributeError(name) from exc
def commands(out):return [x for line in out.splitlines() if (x:=line.strip()) and not x.startswith('#')]
start=get('macros/08_print_start_stop.cfg','PRINT_START')
reset=get('macros/10_live_tuning.cfg','_LIVE_RESET')
p=Obj({'gcode_macro _STATE':SimpleNamespace(mode='idle',start_pending=''),
       'save_variables':SimpleNamespace(variables={'start_confirm':False}),
       'print_stats':SimpleNamespace(state='printing',filename='synthetic.gcode'),
       'configfile':SimpleNamespace(settings=Obj({'printer':Obj({'max_accel':3000})}))})
rendered=commands(start.render(printer=p,params=Obj({'TOTAL_LAYERS':30})))
reset_out=commands(reset.render(printer=p))
total_cmd='SET_GCODE_VARIABLE MACRO=_STATE VARIABLE=total_layers VALUE=30'
zero_cmd='SET_GCODE_VARIABLE MACRO=_STATE VARIABLE=total_layers VALUE=0'
assert total_cmd in rendered and '_LIVE_RESET' in rendered and zero_cmd in reset_out
assert rendered.index(total_cmd)<rendered.index('_LIVE_RESET')
print('PRINT_START TOTAL_LAYERS=30:', total_cmd, 'vor _LIVE_RESET')
print('_LIVE_RESET:',zero_cmd)
# Flatten only the nested macro to expose output order, not execute commands.
flat=[]
for command in rendered:
    flat.extend(reset_out if command == '_LIVE_RESET' else [command])
values=[c for c in flat if c.startswith('SET_GCODE_VARIABLE MACRO=_STATE VARIABLE=total_layers ')]
assert values == [total_cmd, zero_cmd], values
print('Synthetisch entfaltete Befehlsfolge:',values)
print('Ergebnis der beiden SET-Anweisungen ohne spaetere Setzer: 0; keine Klipper-Ausfuehrung.')
# Startzweige: ergebnisorientierte reine Renderproben; kein Ablauf von
# _RUN_PRINT_START, PAUSE_BASE oder _DIALOG_PEEK wird hier angenommen.
for label,mode,pending,confirm in [('ohne Dialog','idle','',False),
                                   ('mit Dialog','idle','',True),
                                   ('Entscheidung vorgemerkt','printing','as_sliced',True),
                                   ('Guard verweigert','printing','',True)]:
    p['gcode_macro _STATE']=SimpleNamespace(mode=mode,start_pending=pending)
    p['save_variables'].variables={'start_confirm':confirm}
    out=commands(start.render(printer=p,params=Obj({'TOTAL_LAYERS':30})))
    has_reset='_LIVE_RESET' in out
    assert has_reset == (label!='Guard verweigert')
    assert (total_cmd in out)==has_reset
    if has_reset:assert out.index(total_cmd)<out.index('_LIVE_RESET')
    peek=any(c.split()[0]=='_DIALOG_PEEK' for c in out)
    if label=='mit Dialog':assert peek
    if label=='Entscheidung vorgemerkt':assert not peek and any(c.startswith('_RUN_PRINT_START ') for c in out)
    print(f'  Startzweig {label}: total_then_reset={has_reset}; DIALOG_PEEK={peek}')
# Zeige die Dateireihenfolge fuer eine synthetische Datei: process() darf NUR
# diese temporaere Kopie veraendern. Slicer-/R2-Sonderfaelle sind nicht abgedeckt.
with tempfile.TemporaryDirectory(prefix='r2-start-total-') as temp:
    path=Path(temp)/'example.gcode'
    layers=''.join(f';LAYER_CHANGE\nG1 X{10+i} Y10 Z{0.2*(i+1):.1f} E1\n' for i in range(30))
    path.write_text('PRINT_START TOTAL_LAYERS=30\nM83\n;TYPE:External perimeter\n'+layers)
    pp.process(str(path))
    lines=path.read_text().splitlines()
    selected=[line for line in lines if line.startswith(('_FILE_INFO ', 'PRINT_START '))]
    assert len(selected)==2 and selected[0].startswith('_FILE_INFO ') and selected[1].startswith('PRINT_START '),selected
    print('process() auf Temp-Datei, relevante Dateireihenfolge:', selected)
