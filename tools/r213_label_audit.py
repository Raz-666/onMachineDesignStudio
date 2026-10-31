#!/usr/bin/env python3
"""R213 audit: EVERY menu name/input/enable through the SHIPPED evaluator.

Reports every label that renders raw (null or leftover braces) - exactly
what the field sees as 'kryptische Bezeichnungen'."""
import json, os, re, subprocess, sys, tempfile

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
html = open(os.path.join(REPO, 'web', 'index.html'), encoding='utf-8').read()
A = '// ==== R201 live evaluator'
B = '// ==== end R201 live evaluator ===='
evaljs = html[html.index(A):html.index(B) + len(B)]

doc = json.load(open(os.path.join(REPO, 'web', 'menu_structure.json')))
items = []


def walk(n, path):
    for c in n.get('children') or []:
        items.append((c, path))
        walk(c, path + [c.get('id')])


walk(doc['tree'], [])

# the r197 /live fixture shape (printing) - plus an idle variant
FIX = json.loads(subprocess.run(
    [sys.executable, '-c',
     'import json,sys;'
     'sys.argv=["x"];'
     'exec(open("tools/r197_gen_sweep.py").read().split("    _eval_js =")[0].'
     'split("def fake_moonraker")[0]) if False else None'],
    capture_output=True, text=True).stdout or 'null') if False else None

# build the fixture inline (mirror of r197's FIX)
sys.path.insert(0, os.path.join(REPO, 'tools'))
FIX = {
    'gcode_macro _STATE': {
        'mode': 'printing', 'layer': 42, 'total_layers': 100,
        'current_type': 'WALL-OUTER', 'file_type': 'marked',
        'file_material': 'PLA', 'file_bed': 60, 'file_bed_after': 60,
        'file_hotend_first': 210, 'file_hotend_after': 215,
        'file_layer_height': 0.2, 'file_nozzle': 0.6, 'file_wall_loops': 2,
        'file_flow_ratio': 0.98, 'file_line_width': 0.62,
        'file_pa': 0.05, 'file_slicer': 'PrusaSlicer_2.7',
        'file_firmware': 'Marlin', 'file_by_object': 1,
        'file_feat_spd_wallouter': 45, 'file_speed_first': 20,
        'file_ironing_speed': 30, 'file_retract_len': 0.8,
        'file_retract_speed': 35, 'opt_pending': False, 'fc_armed': False,
        'fc2_armed': False, 'file_volumetric': False,
    },
    'gcode_macro _PREVIEW': {'name': 'rose.gcode', 'type': 'marked'},
    'gcode_macro _R2_CONFIG': {'led_status_n': 4, 'led_bed_n': 2,
                               'led_bed_on': 1, 'led_bed_bright': 0.4,
                               'led_nozzle_split': 0},
    'save_variables': {'variables': {
        'material': 'PLA', 'opt_cnt': 3, 'opt_list': 'a.gcode|b.gcode',
        'sound_on': True, 'leds_on': True, 'kamp_mesh': True,
        'kamp_purge': True, 'kamp_purge_type': 'LINE',
        'kamp_smart_park': False, 'nozzle_split': 0, 'nozzle_mode': 'auto',
        'zt_boot': True, 'zt_print': True, 'z_offset': 0.1,
    }},
    'print_stats': {'state': 'printing', 'filename': 'rose.gcode',
                    'print_duration': 1200, 'total_duration': 1300},
    'gcode_move': {'speedfactor': 1.0, 'extrude_factor': 1.0,
                   'speed': 1200.0, 'homing_origin': [0, 0, 0.1]},
    'heater_bed': {'temperature': 59.8, 'target': 60},
    'extruder': {'temperature': 214.5, 'target': 215},
    'fan': {'speed': 0.85},
    'display_status': {'progress': 0.42, 'message': 'Printing'},
    'configfile': {'settings': {'neopixel caselight': None,
                                'bed_mesh': None}},
    'exclude_object': {'objects': [{'name': 'Object_1'},
                                   {'name': 'Object_2'}],
                       'current_object': 'Object_1', 'excluded_objects': []},
    'input_shaper': {'shaper_type_x': 'mzv', 'shaper_freq_x': 38.2,
                     'shaper_type_y': 'ei', 'shaper_freq_y': 32.0},
}

names = [(c, p) for c, p in items if c.get('name')]
harness = (evaljs + '\n'
           'const DATA = ' + json.dumps(FIX) + ';\n'
           + 'const ITEMS = ' + json.dumps(
               [{'id': c['id'], 'name': c.get('name'),
                 'input': c.get('input'), 'enable': c.get('enable'),
                 'type': c.get('type')} for c, p in names]) + ';\n'
           + """
const badName=[], badIn=[], badEn=[], okEn=[];
for(const it of ITEMS){
  if(it.name){
    const v=evalName(it.name,DATA);
    if(v==null||/[{}]/.test(v)) badName.push({id:it.id,out:v==null?null:String(v).slice(0,60),raw:String(it.name).slice(0,90)});
  }
  if(it.input){
    const v=evalName(it.input,DATA);
    if(v==null||/[{}]/.test(v)) badIn.push({id:it.id,out:v==null?null:String(v).slice(0,50)});
  }
  if(it.enable){
    const v=evalEnable(it.enable,DATA);
    if(v===null) badEn.push({id:it.id,raw:String(it.enable).slice(0,80)});
    else okEn.push(v);
  }
}
console.log(JSON.stringify({n:ITEMS.length,badName,badIn,badEn,shown:okEn.filter(Boolean).length}));
""")
open('/tmp/r213_audit.js', 'w').write(harness)
r = subprocess.run(['node', '/tmp/r213_audit.js'], capture_output=True,
                   text=True, timeout=180)
if r.returncode != 0:
    print('node failed:', r.stderr[-500:])
    sys.exit(1)
res = json.loads(r.stdout.strip().splitlines()[-1])
print('items:', res['n'])
print('== RAW NAMES (kryptisch):', len(res['badName']))
for b in res['badName'][:60]:
    print('  %-52s -> %r  raw=%r' % (b['id'][-52:], b['out'], b['raw'][:80]))
print('== RAW INPUTS:', len(res['badIn']))
for b in res['badIn'][:20]:
    print('  %-52s -> %r' % (b['id'][-52:], b['out']))
print('== UNDECIDABLE ENABLES:', len(res['badEn']))
for b in res['badEn'][:25]:
    print('  %-52s %r' % (b['id'][-52:], b['raw']))
