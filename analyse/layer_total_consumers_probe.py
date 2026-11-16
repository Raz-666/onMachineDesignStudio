#!/usr/bin/env python3
"""Rendert unveraenderte Anzeigen und SET_LAYER_RANGE unter Stub-Zustaenden.
Keine Klipper-Ausfuehrung, keine erzeugte Range-Datei und kein Druckerbefehl.
Untersucht explizit Range im WAITING/IDLE-Zustand, nicht waehrend des Drucks.
"""
from pathlib import Path
from types import SimpleNamespace
from jinja2 import Environment
root=Path(__file__).resolve().parents[1]
env=Environment(variable_start_string='{',variable_end_string='}')
class Obj(dict):
    def __getattr__(self,name):
        try:return self[name]
        except KeyError as exc:raise AttributeError(name) from exc
def section(path,name):
    t=(root/path).read_text(encoding='utf8')
    return t.split('['+name+']',1)[1].split('\n[',1)[0]
def body(path,name):return env.from_string(section(path,name).split('\ngcode:\n',1)[1])
def clean(out):return [c for l in out.splitlines() if (c:=l.strip()) and not c.startswith('#')]
menu=section('menus/lcd_menues.cfg','menu __main __live __file __ly')
name=next(l.removeprefix('name: ') for l in menu.splitlines() if l.startswith('name: '))
label=env.from_string(name)
marker=body('macros/06_temp_controls.cfg','gcode_macro LAYER_MARK')
range_tpl=body('macros/08_print_start_stop.cfg','gcode_macro SET_LAYER_RANGE')
for total in (0,251):
    state=SimpleNamespace(mode='printing',layer=0,total_layers=total,current_type='WALL-OUTER',
                          file_layer_height=0.2,file_material='PLA',file_hotend_after=0,file_bed_after=0)
    printer=Obj({'gcode_macro _STATE':state, 'save_variables':SimpleNamespace(variables={}),
                 'gcode_macro _MATERIALS':SimpleNamespace(presets={}),
                 'gcode_move':SimpleNamespace(gcode_position=SimpleNamespace(z=.2)),
                 'extruder':SimpleNamespace(target=200),'heater_bed':SimpleNamespace(target=60),
                 'fan':SimpleNamespace(speed=0), 'print_stats':SimpleNamespace(filename='example.gcode')})
    displayed=label.render(printer=printer)
    mark_cmds=clean(marker.render(printer=printer))
    message=next(c for c in mark_cmds if c.startswith('M117 Layer '))
    print(f'total_layers={total}: Live-Menue={displayed!r}; Marker={message!r}')
    assert ('x?' in displayed)==(total==0)
    assert ('/251' in message)==(total==251)
    # Range explicitly in a waiting print-dialog: the printing guard rejects
    # direct invocation during an active print.
    state.mode='waiting'
    out=clean(range_tpl.render(printer=printer,params=Obj({'START':10,'END':300,'FILE':'example.gcode'})))
    end=next(c for c in out if c.startswith('SAVE_VARIABLE VARIABLE=range_end '))
    print(f'  mode=waiting; START=10 END=300: {end}')
    assert end.endswith('VALUE='+('300' if total==0 else '251'))
    state.mode='printing'
    blocked=clean(range_tpl.render(printer=printer,params=Obj({'START':10,'END':300,'FILE':'example.gcode'})))
    assert any('only when idle' in c for c in blocked)
    assert not any(c.startswith('SAVE_VARIABLE VARIABLE=range_end') for c in blocked)
print('SET_LAYER_RANGE mode=printing: verweigert; Backend-Range nicht ausgefuehrt.')
