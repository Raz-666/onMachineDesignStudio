#!/usr/bin/env python3
"""Offline-rendern von CALIBRATE_EXTRUDER mit synthetischen Zustaenden.
Kein Klipper, keine Ausfuehrung; Client-/Menue-Erreichbarkeit und moegliche
Firmware-Grenzen werden NICHT modelliert. Ergebnisse sind nicht Druckbefehle.
"""
from pathlib import Path
from types import SimpleNamespace
from jinja2 import Environment
root=Path(__file__).resolve().parents[1]
text=(root/'macros/12_maintenance.cfg').read_text(encoding='utf8')
sec=text.split('[gcode_macro CALIBRATE_EXTRUDER]',1)[1].split('\n[',1)[0]
t=Environment(variable_start_string='{',variable_end_string='}').from_string(sec.split('\ngcode:\n',1)[1])
class Obj(dict):
    def __getattr__(self,k):
        try:return self[k]
        except KeyError as exc:raise AttributeError(k) from exc
def render(mode,params):
    p=Obj({'gcode_macro _STATE':SimpleNamespace(mode=mode),
           'configfile':SimpleNamespace(settings=Obj({'extruder':Obj(rotation_distance=7.0)}))})
    return [s for l in t.render(printer=p,params=Obj(params)).splitlines() if (s:=l.strip()) and not s.startswith('#')]
for mode,step,measured in [('printing','heat',None),('printing','extrude',None),('idle','extrude',None),
                           ('printing','result',20),('idle','result',0),('idle','result',120),('idle','result',121)]:
    params={'STEP':step}
    if measured is not None:params['MEASURED']=str(measured)
    out=render(mode,params)
    signals=[s for s in out if s.startswith(('NOTIFY ', 'G1 E100 ', 'SET_EXTRUDER_ROTATION_DISTANCE '))]
    print(f'mode={mode}, STEP={step}, MEASURED={measured}:',signals)
    if step=='heat':assert any('Only when idle' in s for s in signals)
    if step=='extrude':assert 'G1 E100 F120' in signals
    if step=='result' and measured==20:assert 'SET_EXTRUDER_ROTATION_DISTANCE EXTRUDER=extruder DISTANCE=7.0' in signals
    if step=='result' and measured==0:assert not any(s.startswith('SET_EXTRUDER_ROTATION_DISTANCE') for s in signals)
    if step=='result' and measured==120:assert 'SET_EXTRUDER_ROTATION_DISTANCE EXTRUDER=extruder DISTANCE=0.0' in signals
    if step=='result' and measured==121:assert 'SET_EXTRUDER_ROTATION_DISTANCE EXTRUDER=extruder DISTANCE=-0.07' in signals
print('LCD Maintenance ist fuer mode=printing ausgeblendet; direkte API-/Console-Aufrufe und Firmwaregrenzen hier nicht ausgefuehrt.')
