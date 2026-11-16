#!/usr/bin/env python3
"""Originaltemplates PAUSE_AT_LAYER und LAYER_MARK mit synthetischen Zustaenden.

Jinja-Rendering und minimale, explizite Modellfortschreibung ausschliesslich im
Speicher. Keine Klipper-Ereignisschleife, kein Drucker, keine Befehlsausfuehrung.
Zwischen Markern wird fuer die Sequenz ein erfolgreicher Resume angenommen.
"""
from pathlib import Path
from types import SimpleNamespace
import re
from jinja2 import Environment

cfg = (Path(__file__).resolve().parents[1] / 'macros/06_temp_controls.cfg').read_text(encoding='utf8')
env = Environment(variable_start_string='{', variable_end_string='}')
def template(name):
    sec = cfg.split('[gcode_macro ' + name + ']', 1)[1].split('\n[', 1)[0]
    return env.from_string(sec.split('\ngcode:\n', 1)[1])
marker, setter = template('LAYER_MARK'), template('PAUSE_AT_LAYER')
class Obj(dict):
    def __getattr__(self, name):
        try:
            return self[name]
        except KeyError as exc:
            raise AttributeError(name) from exc
def commands(rendered):
    return [s for line in rendered.splitlines() if (s := line.strip()) and not s.startswith('#')]
def printer(layer, sv, mode='printing'):
    state = SimpleNamespace(mode=mode, layer=layer, total_layers=3, current_type='WALL-OUTER',
                            file_material='PLA', file_hotend_after=0, file_bed_after=0,
                            stop_at_layer=0, pause_planned_reason='scheduled')
    return Obj({'gcode_macro _STATE': state, 'save_variables': SimpleNamespace(variables=sv),
                'gcode_macro _MATERIALS': SimpleNamespace(presets={}),
                'gcode_move': SimpleNamespace(gcode_position=SimpleNamespace(z=0.4)),
                'extruder': SimpleNamespace(target=200), 'heater_bed': SimpleNamespace(target=60),
                'fan': SimpleNamespace(speed=0)})
def render(layer, sv, mode='printing'):
    return commands(marker.render(printer=printer(layer, sv, mode)))
def events(out):
    return [c for c in out if c.startswith(('SAVE_VARIABLE VARIABLE=pause_', 'PAUSE REASON='))]

# Setter accepts 1, but the marker condition requires n > 1.
set1 = commands(setter.render(params=Obj({'LAYER': 1})))
assert 'SAVE_VARIABLE VARIABLE=pause_at_layer VALUE=1' in set1
print('PAUSE_AT_LAYER LAYER=1 setter:', [c for c in set1 if c.startswith('SAVE_VARIABLE')])
for layer in (0, 1):
    out = render(layer, Obj({'pause_at_layer': 1}))
    assert not events(out)
    print(f'Vorzustand layer={layer}, pause_at_layer=1:', events(out))

cases = [
    ('at target', 1, {'pause_at_layer': 2}, ['SAVE_VARIABLE VARIABLE=pause_at_layer VALUE=0', 'PAUSE REASON="layer 2 (planned)"']),
    ('before target', 0, {'pause_at_layer': 2}, []),
    ('already past', 2, {'pause_at_layer': 2}, []),
    ('next only', 1, {'pause_next_layer': True}, ['SAVE_VARIABLE VARIABLE=pause_next_layer VALUE=False', 'PAUSE REASON="scheduled (layer 2)"']),
    ('both at target', 1, {'pause_next_layer': True, 'pause_at_layer': 2}, ['SAVE_VARIABLE VARIABLE=pause_next_layer VALUE=False', 'PAUSE REASON="scheduled (layer 2)"']),
]
for label, layer, values, expected in cases:
    found = events(render(layer, Obj(values)))
    print(f'{label}:', found)
    assert found == expected, (label, found, expected)
assert events(render(1, Obj({'pause_at_layer': 2}), mode='paused')) == []

# Only SAVE_VARIABLE emitted by the rendered template is applied to an in-memory
# dictionary. We assume later resume with mode=printing and the next marker.
sv = Obj({'pause_next_layer': True, 'pause_at_layer': 2})
for layer in (1, 2):
    found = events(render(layer, sv))
    for command in found:
        m = re.fullmatch(r'SAVE_VARIABLE VARIABLE=(pause_next_layer|pause_at_layer) VALUE=(False|0)', command)
        if m:
            sv[m.group(1)] = False if m.group(2) == 'False' else 0
    print(f'sequence marker n={layer+1}: events={found}; afterwards={dict(sv)}')
    if layer == 1:
        assert sv == {'pause_next_layer': False, 'pause_at_layer': 2}
    else:
        assert not found and sv['pause_at_layer'] == 2
print('Grenze: synthetische Reihenfolge/Resume, keine Klipper-Ausfuehrung.')
