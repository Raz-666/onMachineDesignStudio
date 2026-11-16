#!/usr/bin/env python3
"""Rendert das echte LAYER_MARK-Makro unter expliziten synthetischen Zuständen.

Keine Klipper-Verbindung, kein Drucken, keine Befehle werden ausgefuehrt.
Dieser Test kombiniert nicht die zeitliche Simulation des Watchers und weist
kein reales Maschinenereignis nach. Benoetigt jinja2.
"""
from pathlib import Path
from types import SimpleNamespace
from jinja2 import Environment

root=Path(__file__).resolve().parents[1]
text=(root/'macros/06_temp_controls.cfg').read_text(encoding='utf8')
section=text.split('[gcode_macro LAYER_MARK]',1)[1].split('\n[',1)[0]
template=Environment(variable_start_string='{',variable_end_string='}').from_string(section.split('\ngcode:\n',1)[1])
class Obj(dict):
    __getattr__=dict.__getitem__
for layer,stop in [(0,0),(0,1),(1,2),(1,3)]:
    state=SimpleNamespace(mode='printing',layer=layer,total_layers=2,current_type='WALL-OUTER',
                          file_material='PLA',file_hotend_after=0,file_bed_after=0,stop_at_layer=stop)
    printer=Obj({'gcode_macro _STATE':state,'save_variables':SimpleNamespace(variables={}),
                 'gcode_macro _MATERIALS':SimpleNamespace(presets={}),
                 'gcode_move':SimpleNamespace(gcode_position=SimpleNamespace(z=0.4)),
                 'extruder':SimpleNamespace(target=200),'heater_bed':SimpleNamespace(target=60),
                 'fan':SimpleNamespace(speed=0)})
    out=template.render(printer=printer)
    commands=[x.strip() for x in out.splitlines() if x.strip() and not x.strip().startswith('#')]
    stops=[x for x in commands if x.startswith('_END_AT_LAYER ')]
    print(f'simulierter_Vorzustand layer={layer}, stop_at_layer={stop}: '
          f'rendered_stop={stops if stops else "kein"}')
    assert bool(stops)==(stop>0 and layer+1>=stop)
