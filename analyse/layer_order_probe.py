#!/usr/bin/env python3
"""Simulierte, begrenzte Ereignisreihenfolge mit echten Jinja-Templates.

_STATE_WATCHER: exakt kopierter Z-Tracking-Branch aus dem Produkttext, sein
urspruengliches elif hier als isoliertes if gerendert. Alle hoeher priorisierten
Watcher-Branches werden angenommen als nicht zutreffend; das ist keine
vollstaendige Simulation von Klipper oder seiner zeitlichen Ereignisschleife.
Nur drei explizite SET_GCODE_VARIABLE-Zeilen werden im Speichermodell angewandt.
Keine ausgegebenen Maschinenbefehle ausfuehren.
"""
from pathlib import Path
from types import SimpleNamespace
import re
from jinja2 import Environment

root = Path(__file__).resolve().parents[1]
w = (root / 'macros/01_state.cfg').read_text(encoding='utf8')
opening = "    {% elif st == 'printing' and s.mode == 'printing' and not s.layer_marks %}"
end = "    {% elif st == 'printing' and s.mode == 'paused' %}"
assert w.count(opening) == 1 and w.count(end) == 1
fragment = opening.replace('{% elif ', '{% if ', 1) + w.split(opening, 1)[1].split(end, 1)[0] + '\n    {% endif %}'
txt = (root / 'macros/06_temp_controls.cfg').read_text(encoding='utf8')
macro = txt.split('[gcode_macro LAYER_MARK]', 1)[1].split('\n[', 1)[0].split('\ngcode:\n', 1)[1]
env = Environment(variable_start_string='{', variable_end_string='}')
watcher, marker = env.from_string(fragment), env.from_string(macro)
class Obj(dict):
    def __getattr__(self, name):
        try: return self[name]
        except KeyError as exc: raise AttributeError(name) from exc

def run(order):
    s = SimpleNamespace(mode='printing', layer=0, layer_marks=False, layer_z_max=0., layer_z_acc=0.,
                        total_layers=1, current_type='WALL-OUTER', stop_at_layer=2,
                        file_material='PLA', file_hotend_after=0, file_bed_after=0,
                        ignore_overrides=False)
    sv = {}
    p = Obj({'gcode_macro _STATE': s, 'save_variables': SimpleNamespace(variables=sv),
             'gcode_macro _MATERIALS': SimpleNamespace(presets={}),
             'gcode_move': SimpleNamespace(gcode_position=SimpleNamespace(z=0.0)),
             'extruder': SimpleNamespace(target=200), 'heater_bed': SimpleNamespace(target=60),
             'fan': SimpleNamespace(speed=0)})
    for event, z in order:
        p.gcode_move.gcode_position.z = z
        output = (watcher.render(printer=p, s=s, sv=sv, st='printing') if event == 'watcher'
                  else marker.render(printer=p))
        commands = [line.strip() for line in output.splitlines() if line.strip() and not line.strip().startswith('#')]
        highlights = [c for c in commands if c.startswith(('SET_GCODE_VARIABLE MACRO=_STATE VARIABLE=layer ',
                      'SET_GCODE_VARIABLE MACRO=_STATE VARIABLE=layer_marks ', '_END_AT_LAYER', 'M220 '))]
        print(f'  {event} z={z}: {highlights}')
        for c in commands:
            m = re.fullmatch(r'SET_GCODE_VARIABLE MACRO=_STATE VARIABLE=(layer|layer_marks|layer_z_max|layer_z_acc) VALUE=([^ ]+)', c)
            if m:
                name, value = m.groups()
                parsed = {'True': True, 'False': False}.get(value)
                if parsed is None:
                    parsed = float(value) if '.' in value else int(value)
                setattr(s, name, parsed)
        if event == 'marker':
            marker_stop = any(c.startswith('_END_AT_LAYER ') for c in commands)
    return s, marker_stop

print('A: angenommener Watcher-Tick vor Marker')
a, stop_a = run([('watcher', .2), ('marker', .4)])
assert a.layer == 2 and a.layer_marks and stop_a
print('B: Marker vor erstem angenommenen Watcher-Tick')
b, stop_b = run([('marker', .4), ('watcher', .4)])
assert b.layer == 1 and b.layer_marks and not stop_b
print('Ergebnis:', f'A layer={a.layer:g} marker_stop={stop_a}; B layer={b.layer:g} marker_stop={stop_b}')
print('Grenze: Reihenfolgen vorausgesetzt, Watcher-Hauptkette/Timer/Klipper nicht simuliert.')
