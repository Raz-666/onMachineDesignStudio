#!/usr/bin/env python3
"""Offline-Renderprobe FLOW_CAL und RETRACT_TOWER_RESULT.

Originaltemplates, keine Klipper-Verbindung, KEINE Befehlsausfuehrung.
Zustandsmodell wendet ausschliesslich ausgegebene flow_cal_*-Zuweisungen in
Memory an. Simulator ist kein Modell von Hardware, Druck oder Menue-Timing.
"""
from pathlib import Path
from types import SimpleNamespace
import re
from jinja2 import Environment
root=Path(__file__).resolve().parents[1]
text=(root/'macros/12_maintenance.cfg').read_text(encoding='utf8')
env=Environment(variable_start_string='{',variable_end_string='}')
def template(name):
    sec=text.split('[gcode_macro '+name+']',1)[1].split('\n[',1)[0]
    return env.from_string(sec.split('\ngcode:\n',1)[1])
class Obj(dict):
    def __getattr__(self,k):
        try:return self[k]
        except KeyError as exc:raise AttributeError(k) from exc
def commands(txt):return [s for l in txt.splitlines() if (s:=l.strip()) and not s.startswith('#')]
flow=template('FLOW_CAL');retr=template('RETRACT_TOWER_RESULT')
sv=Obj({'flow_cal_target':0.6,'flow_cal_meas':0.44,'flow_cal_result':0,
        'rt_nb':6,'rt_start':0.5,'rt_step':0.5,'rt_rspeed':40})
p=Obj({'save_variables':SimpleNamespace(variables=sv),
       'configfile':SimpleNamespace(settings=Obj({'extruder':{'nozzle_diameter':0.4}}))})
def render_flow(params):return commands(flow.render(printer=p,params=Obj(params)))
def results(out):return [s for s in out if s.startswith(('SAVE_VARIABLE VARIABLE=flow_cal_result','RESPOND MSG="Flow cal: wall'))]
# Same saved target, same measurement; only passing TARGET differs.
a=results(render_flow({'MEASURE':'0.5'}));b=results(render_flow({'MEASURE':'0.5','TARGET':'0.6'}))
print('saved target=0.6, nozzle=0.4, MEASURE=0.5 ->',a)
print('same but explicitly TARGET=0.6 ->',b)
assert any('VALUE=80.0' in s for s in a)
assert any('VALUE=120.0' in s for s in b)
# Menu order: target's menu line separately saves flow_cal_target; its macro
# uses old measured value. Apply only emitted flow_cal SAVE_VARIABLEs to a dict.
sv['flow_cal_target']=0.6
for label,ps in [('Target-Menue-Aufruf',{'TARGET':'0.6'}),('danach Wall-GO',{'MEASURE':'0.5'})]:
    out=render_flow(ps)
    for cmd in out:
        m=re.fullmatch(r'SAVE_VARIABLE VARIABLE=(flow_cal_meas|flow_cal_result) VALUE=([-0-9.]+)',cmd)
        if m:sv[m.group(1)]=float(m.group(2))
    print(label,results(out),'Modellwerte=',{k:sv[k] for k in ('flow_cal_target','flow_cal_meas','flow_cal_result')})
assert sv['flow_cal_target']==.6 and sv['flow_cal_result']==80.0
# No result execution: note only whether the rendered template emits setters.
for block in (0,3,7):
    out=commands(retr.render(printer=p,params=Obj({'BLOCK':str(block)})))
    setters=[s for s in out if s.startswith('SET_OVERRIDE_VALUE ')]
    print('RETRACT_TOWER_RESULT BLOCK=',block,'setters=',setters)
    if block==3:assert setters==['SET_OVERRIDE_VALUE NAME=retract_len VALUE=1.5']
    else:assert not setters
print('Keine Maschinenausfuehrung; FLOW_CAL-Beispiel ist synthetisch.')
