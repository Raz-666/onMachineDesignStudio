#!/usr/bin/env python3
"""Rendert das echte LAYER_MARK-Template unter zwei synthetischen Zuständen.

Kein Klipper, keine Bewegung und keine Befehlsausfuehrung. Die beiden
Vorbedingungen sind moegliche Zustandswerte, kein Nachweis fuer ein reales
Timing des asynchronen _STATE_WATCHER.
Benötigt jinja2 (z. B. /tmp/r2-c7804-venv/bin/python).
"""
from pathlib import Path
from types import SimpleNamespace
import re
from jinja2 import Environment

root=Path(__file__).resolve().parents[1]
text=(root/'macros/06_temp_controls.cfg').read_text(encoding='utf8')
section=text.split('[gcode_macro LAYER_MARK]',1)[1].split('\n[',1)[0]
body=section.split('\ngcode:\n',1)[1]
env=Environment(variable_start_string='{',variable_end_string='}')
template=env.from_string(body)
class Obj(dict):
    __getattr__=dict.__getitem__
for layer in (0,1):
    state=SimpleNamespace(mode='printing',layer=layer,total_layers=2,current_type='WALL-OUTER',
                          file_material='PLA',file_hotend_after=0,file_bed_after=0)
    printer=Obj({'gcode_macro _STATE':state,'save_variables':SimpleNamespace(variables={}),
                 'gcode_macro _MATERIALS':SimpleNamespace(presets={}),
                 'gcode_move':SimpleNamespace(gcode_position=SimpleNamespace(z=0.4)),
                 'extruder':SimpleNamespace(target=200),
                 'heater_bed':SimpleNamespace(target=60),
                 'fan':SimpleNamespace(speed=0)})
    output=template.render(printer=printer)
    commands=[x.strip() for x in output.splitlines() if x.strip() and not x.strip().startswith('#')]
    interesting=[x for x in commands if x.startswith(('SET_GCODE_VARIABLE MACRO=_STATE VARIABLE=layer ',
                                                       'SET_PRINT_STATS_INFO CURRENT_LAYER=', 'M220 ',
                                                       'SET_HEATER_TEMPERATURE ', 'M106 '))]
    print('initial_layer=',layer,'=>',interesting)
