#!/usr/bin/env python3
"""Dokument-/Template-Gegenprobe: kein Klipper, keine Befehlsausfuehrung.

Rendert die Originaltemplates von SYNC_GANTRY und Z_TILT mit synthetischen
Konfigurationen. Aussagen ueber Verkabelung, top stop oder reale Hardware sind
nicht aus diesen Stubs ableitbar. Mutiert keine Produktdatei.
"""
from pathlib import Path
from types import SimpleNamespace
from jinja2 import Environment

root=Path(__file__).resolve().parents[1]
text=(root/'macros/11_gantry_sync.cfg').read_text(encoding='utf8')
env=Environment(variable_start_string='{',variable_end_string='}')
def template(name):
    sec=text.split('[gcode_macro '+name+']',1)[1].split('\n[',1)[0]
    return env.from_string(sec.split('\ngcode:\n',1)[1])
class Obj(dict):
    def __getattr__(self,key):
        try:return self[key]
        except KeyError as exc:raise AttributeError(key) from exc
def commands(text):
    return [s for l in text.splitlines() if (s:=l.strip()) and not s.startswith('#')]
sync,tilt=template('SYNC_GANTRY'),template('Z_TILT')
for name,cfg in [
    ('one, guards satisfied',{'force_move':Obj(enable_force_move=True),'tmc2209 stepper_z':Obj(run_current=.8)}),
    ('stepper_z1, no z_tilt',{'stepper_z1':{},'force_move':Obj(enable_force_move=True),'tmc2209 stepper_z':Obj(run_current=.8)}),
    ('stepper_z1 and z_tilt',{'stepper_z1':{},'z_tilt':{},'force_move':Obj(enable_force_move=True),'tmc2209 stepper_z':Obj(run_current=.8)}),
    ('one, force_move missing',{'tmc2209 stepper_z':Obj(run_current=.8)}),
    ('one, TMC2208 only',{'force_move':Obj(enable_force_move=True),'tmc2208 stepper_z':Obj(run_current=.8)})]:
    p=Obj({'gcode_macro _STATE':SimpleNamespace(mode='idle'),
           'save_variables':SimpleNamespace(variables={}),
           'configfile':SimpleNamespace(settings=Obj(cfg)),
           'toolhead':SimpleNamespace(homed_axes='xyz',axis_maximum=SimpleNamespace(z=250))})
    out_sync=commands(sync.render(printer=p,params=Obj({'QUIET':'1'})))
    out_tilt=commands(tilt.render(printer=p,params=Obj({'QUIET':'1'})))
    def select(out):return [c.split('#',1)[0].strip() for c in out if c.startswith(('NOTIFY ','G28','G1 Z','SET_TMC_CURRENT','SET_KINEMATIC_POSITION','Z_TILT_ADJUST'))]
    print(name, '\n  SYNC_GANTRY:',select(out_sync),'\n  Z_TILT:',select(out_tilt))
    s='\n'.join(out_sync);t='\n'.join(out_tilt)
    if name=='one, guards satisfied':assert 'SET_KINEMATIC_POSITION Z=' in s and 'Z_TILT_ADJUST' not in t
    if name=='stepper_z1, no z_tilt':assert 'use Z_TILT' in s and 'SET_KINEMATIC_POSITION Z=' not in s and 'needs a [z_tilt]' in t
    if name=='stepper_z1 and z_tilt':assert 'use Z_TILT' in s and 'SET_KINEMATIC_POSITION Z=' not in s and 'Z_TILT_ADJUST RETRIES=' in t
    if name=='one, force_move missing':assert 'needs [force_move]' in s and 'SET_KINEMATIC_POSITION Z=' not in s
    if name=='one, TMC2208 only':assert 'needs a TMC driver' in s and 'SET_KINEMATIC_POSITION Z=' not in s
print('Nur Template-Ausgaben, keine Befehle ausgefuehrt; mechanische Eignung nicht getestet.')
