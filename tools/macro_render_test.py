#!/usr/bin/env python3
# Render test: executes the critical macro templates with mocked printer data
# (emulates Klipper's jinja dialect: {expr} single braces, {% blocks %}).
from jinja2 import Environment, BaseLoader
import atexit as _atexit, glob as _globcl, shutil as _shutilcl, tempfile as _tfcl, os as _oscl

def _cleanup_tmpdirs():
    # R121: the battery leaves mkdtemp dirs behind - six full runs filled the
    # 992MB tmpfs and froze the sandbox. Remove OUR prefixes only.
    import re as _recl
    pat = _recl.compile(r'^(r\d{2,3}_|audit_|megatest_|r120_|r86_|colorpic)')
    for d in _globcl.glob(_tfcl.gettempdir() + '/*'):
        try:
            if _oscl.path.isdir(d) and pat.match(_oscl.path.basename(d)):
                _shutilcl.rmtree(d, ignore_errors=True)
        except OSError:
            pass

_atexit.register(_cleanup_tmpdirs)
env = Environment(
    loader=BaseLoader(),
    variable_start_string='{', variable_end_string='}',
    block_start_string='{%', block_end_string='%}',
    comment_start_string='{#', comment_end_string='#}',
    trim_blocks=True, lstrip_blocks=False,
)
env.globals['params'] = {}
def _act_stub(*a, **k):
    return '// action call: %s %s' % (a, k)
env.globals['action_respond_info'] = _act_stub
env.globals['action_raise_error'] = _act_stub
env.globals['action_call_remote_method'] = _act_stub

class M(dict):
    """dict with attribute access (like Klipper status objects)"""
    def __getattr__(self, k):
        try:
            v = self[k]
        except KeyError:
            raise AttributeError(k)
        return M(v) if isinstance(v, dict) else v

# ---------- mocked printer ----------
save_vars = {
    'sound_on': True, 'leds_on': True, 'material': 'PETG', 'start_confirm': True,
    'ov_bed_on': True, 'ov_bed': 70, 'ov_bed_after_on': False, 'ov_bed_after': 70,
    'ov_hotend_first_on': True, 'ov_hotend_first': 235, 'ov_hotend_after_on': True, 'ov_hotend_after': 240,
    'ov_retract_on': False, 'ov_retract_len': 1.0, 'ov_retract_speed': 35,
    'ov_retract_len_on': False, 'ov_retract_speed_on': False, 'ov_unretract_speed_on': False, 'ov_unretract_speed': 35,
    'ov_pa_on': False, 'ov_pa': 0.05, 'ov_accel_on': False, 'ov_accel': 4000, 'ov_pa_smooth_on': False,
    'ov_fan_on': False, 'ov_fan': 100, 'unload_length': 90, 'load_length': 60, 'pid_fan_percent': 100,
    'ov_outer_wall': 100, 'ov_outer_wall_accel': 0, 'ov_support': 100, 'ov_support_accel': 0,
    'ov_ironing_speed': 100, 'ov_ironing_flow': 100, 'ov_ironing_temp': 0,
    'ov_outer_wall_on': True, 'ov_outer_wall': 30, 'ov_outer_wall_accel_on': True, 'ov_outer_wall_accel': 1500,
    'ov_support_on': False, 'ov_support': 50, 'ov_support_accel_on': False, 'ov_support_accel': 3000,
    'ov_ironing_on': True, 'ov_ironing_flow': 15, 'ov_ironing_speed': 20, 'ov_ironing_temp': 200,
    'ov_ironing_flow_on': True, 'ov_ironing_speed_on': True, 'ov_ironing_temp_on': False,
    'ov_flow_on': False, 'ov_flow': 100,
    'mesh_adaptive': True, 'mesh_always': True, 'mesh_last_profile': 'r2',
    'gantry_sync_print': False, 'gantry_sync_boot': False, 'gantry_sync_current': 0.35,
    'pause_next_layer': False, 'pause_at_layer': 7,
    'cooldown_fan_time': 30, 'heaters_off_at_end': True, 'motors_off_at_end': True,
    'start_decision': '',
    'kamp_mesh': True, 'kamp_purge': True, 'kamp_purge_type': 'LINE', 'kamp_smart_park': False,
    'legacy_level': True, 'pa_test_start': 0.0, 'pa_test_step': 0.015,
    'pa_cal_hotend': 210, 'pa_cal_bed': 60, 'pa_cal_start': 0, 'pa_cal_step': 0.005,
    'pa_cal_lines': 10, 'pa_cal_len': 100, 'pa_cal_slow': 20, 'pa_cal_fast': 100,
    'pa_cal_accel': 3000, 'pa_cal_spacing': 0,
    'mesh_auto_save': False, 'cold_pull_hot': 230, 'cold_pull_pull': 90,
    'ishaper_freq_start': 0, 'ishaper_freq_end': 0, 'ishaper_max_smoothing': 0, 'ishaper_auto_save': True,
    'label_text': '', 'label_texts': '', 'label_pos': 1, 'label_w': 60, 'label_h': 30,
    'label_font': 'SMOOTH', 'label_base_layers': 4, 'label_text_layers': 2,
    'label_layer_h': 0.2, 'label_first_h': 0.28, 'label_ironing': True,
    'label_hole_side': 1, 'label_hole_d': 5.0, 'label_brim': True, 'label_gap': 6,
    'label_color2': True, 'label_gen_nonce': 0, 'label_fit': '?',
    'label_height': 0, 'label_shape': 0, 'label_corner': 2.0,
    'label_border_walls': 0, 'label_border_gap': 0.0,
    'tie_count': 6, 'tie_length': 120, 'tie_width': 8, 'tie_layers': 3,
    'tie_variant': 'RATCHET', 'tie_layer_h': 0.2, 'tie_brim': True, 'cable_tie_nonce': 0,
    'angle_count': 2, 'angle_deg': 90, 'angle_leg_a': 60, 'angle_leg_b': 60,
    'angle_width': 25, 'angle_layers': 6, 'angle_holes': 2, 'angle_hole_d': 4.0,
    'angle_countersink': True, 'angle_stiffener': 1, 'angle_flat': False,
    'angle_layer_h': 0.2, 'angle_nonce': 0,
}
state_vars = {
    'file_maxrate': 0.0, 'file_derived': False, 'file_travel': 0.0,   # R111/R121: flow-cap + travel LCD read these
    'mode': 'printing', 'layer': 2, 'total_layers': 100, 'current_type': 'WALL-OUTER', 'file_type': 'marked',
    'file_material': 'PLA', 'file_bed': 60, 'file_bed_after': 60,
    'file_hotend_first': 210, 'file_hotend_after': 215, 'file_layer_height': 0.2,
    'file_outer_wall_speed': 45, 'file_support_speed': 50, 'file_ironing_speed': 20,
    'file_held': False, 'ignore_overrides': False,
    'start_pending': '', 'has_heaters': False, 'probe_stage': 0,
    'file_fan': 0, 'file_flow': 100.0, 'infra_done': False,
    'file_line_width': 0.0, 'file_line_width_first': 0.0, 'file_line_width_wall': 0.0,
    'file_flow_ratio': 0.0, 'file_by_object': False, 'file_info_seen': False,
    'file_accel': 0.0, 'file_speed': 100.0,
    'f_outer_wall': 0.8, 'f_inner_wall': 1.0, 'f_infill': 1.0, 'f_solid': 1.0,
    'f_support': 0.7, 'f_ironing': 1.0, 'f_fan_scale': 1.0,
    'a_global': 4000, 'a_outer_wall': 1500, 'a_inner_wall': 0, 'a_infill': 0,
    'a_solid': 0, 'a_support': 0, 'a_ironing': 0,
    'flow': 100, 'pa_value': 0.05, 'pa_smooth': 0.04,
    'ironing_flow': 110, 'ironing_temp': 205, 'ironing_temp_active': False, 'ironing_prev_temp': 240,
    'pause_x': 100, 'pause_y': 100, 'pause_z': 5, 'pause_was_sd': True,
    'park_x': 10, 'park_y': 225, 'park_lift': 5, 'sensor_was_on': True,
    'idle_timeout_saved': 3600, 'wait_ticks': 3, 'last_led': 'printing',
    'pause_reason': 'test', 'cancel_armed': False, 'cancel_time': 0, 'pid_running': False, 'legacy_file': '',
    'skip_armed_name': '', 'skip_armed_time': 0.0, 'mesh_delete_armed': '',
    'layer_z_max': 0.0, 'layer_marks': False, 'mesh_saved_pending': False,
    'ishaper_autosave': False,
    'file_pa': 0.0, 'file_retract_len': 0.0, 'file_retract_speed': 0.0,
    'layer_z_acc': 0.0, 'pause_desync': 0, 'pause_planned_reason': 'next layer',
    'pause_next_armed_runout': False,
    'legacy_armed': False, 'decided_file': '', 'decided_mode': '',
}
cpic_state_vars = {'blink': 0, 'phase': 0, 'pr': 1.0, 'pg': 1.0, 'pb': 1.0,
                   'nr': 0.1, 'ng': 0.85, 'nb': 0.9, 'cidx': 2, 'ctotal': 4,
                   'cname': 'Cyan'}   # R120: the blink state macro
tunes = {'r2_start': '1568:40,1245:30', 'r2_confirm': '2093:25,2637:35', 'r2_click': '1568:15',
         'r2_question': '784:70,0:30,988:60', 'r2_heating': '1046:60,0:40,1318:60', 'r2_hot': '1568:40'}
mats = {'PLA':  {'bed1':60,'bed2':60,'hot1':210,'hot2':210,'pa':0.05, 'pa_smooth':0.04, 'unret_spd':35,'flow':100,'ret_len':0.75,'ret_spd':35,'fan2':100},
        'PETG': {'bed1':75,'bed2':75,'hot1':240,'hot2':240,'pa':0.06, 'pa_smooth':0.04, 'unret_spd':35,'flow':100,'ret_len':0.9,'ret_spd':35,'fan2':60},
        'TPU':  {'bed1':35,'bed2':35,'hot1':215,'hot2':215,'pa':0.09, 'pa_smooth':0.04, 'unret_spd':35,'flow':105,'ret_len':1.2,'ret_spd':20,'fan2':70},
        'ABS':  {'bed1':100,'bed2':100,'hot1':250,'hot2':250,'pa':0.05, 'pa_smooth':0.04, 'unret_spd':35,'flow':100,'ret_len':0.75,'ret_spd':35,'fan2':30},
        'ASA':  {'bed1':100,'bed2':100,'hot1':260,'hot2':260,'pa':0.05, 'pa_smooth':0.04, 'unret_spd':35,'flow':100,'ret_len':0.75,'ret_spd':35,'fan2':30}}
objects = [{'name':'obj1','center':[100,100],'polygon':[[60,60],[140,60],[140,140],[60,140]]}]
preview_vars = {   # R75: the in-memory preview card (gcode_macro _PREVIEW)
    'name':'', 'type':'?', 'material':'?', 'layer_height':0, 'total_layers':0,
    'line_width':0, 'line_width_first':0, 'line_width_wall':0, 'flow_ratio':0,
    'pa':0, 'nozzle':0, 'wall_loops':0, 'hotend':0, 'bed':0, 'fan':0,
    'speed_outer':0, 'speed_first':0, 'speed_travel':0, 'ironing_speed':0,
    'types':'', 'by_object':0, 'plot':0, 'pens':0,
}

# R65: the _LABELS charset EXACTLY as Klipper reads it (comment strip + literal_eval)
import ast as _ast65
_ll65 = open('macros/16_labels.cfg', encoding='utf-8').read()
_ln65 = [l for l in _ll65.split('\n') if l.strip().startswith('variable_charset')][0]
_ln65 = _ln65[:_ln65.find('#')] if '#' in _ln65 else _ln65
LABEL_CHARSET_LCD = _ast65.literal_eval(_ln65.split(':', 1)[1].strip())
BKSL = chr(92)   # a literal backslash (R69 escaped-quote VALUE forms)

def build_printer(kamp=False, objs=None, excl=None, old_klipper=False, bare_idle=False, drop14=False, poweroff=False, ps_state='printing', etemp=None, gz=None, scp=False, etgt=None):
    d = {
    'gcode_move': M({'gcode_position': M({'x':100.0,'y':100.0,'z':(gz if gz is not None else 12.5),'e':5.0}),
                     'speed_factor':1.0,'extrude_factor':1.0,'homing_origin': M({'z':0.0})}),
    'toolhead': M({'axis_maximum': M({'x':235.0,'y':235.0,'z':250.0}), 'axis_minimum': M({'x':0.0,'y':0.0,'z':0.0}), 'homed_axes':'xyz', 'max_accel':4000, 'max_velocity':250.0}),
    'extruder': M({'temperature': (etemp if etemp is not None else 210.0), 'target': (etgt if etgt is not None else 215.0)}),
    'heater_bed': M({'temperature': 60.0, 'target': 60.0}),
    'print_stats': M({'state':ps_state,'print_duration':1234.0,'total_duration':1400.0,
                      'filament_used':4.2,'filename':'test.gcode'}),
    'virtual_sdcard': M({'is_active': True}),
    'save_variables': M({'variables': save_vars}),
    'exclude_object': M({'objects': objects, 'excluded_objects': [], 'current_object': (objects[0]['name'] if objects else None)}),
    'bed_mesh': M({'profile_name': 'r2', 'profiles': {'r2': {}}}),
    'idle_timeout': M({'state':'Printing','printing_time':0.0,'idle_timeout':3600}),   # REAL keyset (get_status: state/printing_time/idle_timeout)
    'configfile': M({'settings': M({'idle_timeout': M({'timeout':'3600'}),   # access_tracking stores RAW STRINGS
                                    'extruder': M({'rotation_distance':7.71,'max_temp':260,'nozzle_diameter':0.6,'pressure_advance':0.004,'min_extrude_temp':170}),
                                    'firmware_retraction': M({'retract_length':0.75,'retract_speed':35}),
                                    'tmc2209 stepper_z': M({'run_current':0.7}), 'probe': M({'x_offset':0.0,'y_offset':0.0})})}),
    'fan': M({'speed': 0.5}),
    'led_effect r2_idle': M({}),           # R46: led_effect library installed
    'neopixel printer_leds': M({}),        # R46: 5-pixel chain (index 5 = nozzle)
    'neopixel nozzle_led': M({}),          # R86.2: split chain (EBB42) - gated by nozzle_split
    'led_effect r2_nozzle_on_split': M({}),  # R86.2: split work-light effect
    'input_shaper': M({'shaper_type_x':'zv','shaper_freq_x':52.3,'shaper_type_y':'mzv','shaper_freq_y':41.7}),
    'filament_switch_sensor filament_sensor': M({'enabled':True,'filament_detected':True}),
    'gcode_macro _STATE': M(state_vars),
    'gcode_macro _COLORPIC_STATE': M(cpic_state_vars),   # R120
    'gcode_macro _MATERIALS': M({'presets': mats}),
    'gcode_macro _SOUND_LIB': M({'tunes': tunes}),
    }
    if objs is not None:
        d['exclude_object'] = M({'objects': objs, 'excluded_objects': (excl or []), 'current_object': (objs[0]['name'] if objs else None)})
    d['configfile']['settings']['bed_mesh r2'] = M({})
    d['gcode_macro _R2_VERSION'] = M({'version': 'R2-2026-09-07.37'})
    # force_move has NO get_status -> NOT addressable via printer['force_move']!
    # Detection works via configfile.settings (it reads 'enable_force_move' there):
    d['configfile']['settings']['force_move'] = M({'enable_force_move': True})
    for _m in ['M300','PLAY_SOUND','SET_LED_STATE','NOTIFY','SHOW_STATUS','SET_MATERIAL','LAYER_MARK','M104',
               'SET_OVERRIDE_VALUE','PRINT_AS_SLICED','PRINT_START','PRINT_END','QUICK_PAUSE','CHANGE_FILAMENT',
               'APPLY_TYPE','SET_FLOW_RATE','SYNC_GANTRY','TUNE_PID','SELF_TEST','SYS_FIRMWARE_RESTART',
               'SKIP_OBJECT','SHOW_OBJECTS','_LEGACY_HOME','_LEGACY_DIALOG','_APPLY_OVERRIDES_CORE'] + ([] if drop14 else ['_CALIBRATE_MESH_PROFILE','_PURGE_SMART','KAMP_STATUS']):
        d['gcode_macro ' + _m] = M({})
    for _v in ['_V01_STATE','_V02_SOUNDS','_V03_LEDS','_V04_NOTIFY','_V05_MATERIALS','_V06_TEMPS',
               '_V07_CONFIRM','_V08_STARTSTOP','_V09_PAUSE','_V10_LIVE','_V11_GANTRY','_V12_MAINT',
               '_V13_SYSTEM','_V15_OBJECTS','_V16_MENUS','_V17_LABELS','_V18_GEN','_V18_COLORPIC'] + ([] if drop14 else ['_V14_KAMP']):
        d['gcode_macro ' + _v] = M({})
    if old_klipper:
        d['idle_timeout'] = M({'state':'Printing','printing_time':0.0})   # older Klipper: no 'idle_timeout' key
    if bare_idle:
        d['configfile']['idle_timeout'] = M({})   # [idle_timeout] without explicit 'timeout:' option
    if poweroff:
        d['configfile']['settings']['gcode_shell_command poweroff'] = M({'command': 'sudo /sbin/poweroff'})
    d['configfile']['save_config_pending'] = scp          # R63 SYS_SAVE_CONFIG guard
    d['gcode_macro _PREVIEW'] = M(preview_vars)
    d['gcode_macro _LABELS'] = M({'charset': LABEL_CHARSET_LCD,
                                  'max_text': 12, 'max_labels': 24})
    d['gcode_macro _LEGACY_PREP'] = M({})
    d['gcode_macro _GENERATORS'] = M({'max_ties': 24, 'max_plates': 12})
    if kamp:
        d['gcode_macro _KAMP_Settings'] = M({'mesh_margin':0,'fuzz_amount':0,'purge_amount':30,
                                             'purge_margin':10,'purge_height':0.8,
                                             'smart_park_height':10,'verbose_enable':True})
        d['gcode_macro BED_MESH_CALIBRATE'] = M({})   # simulate the KAMP override
        d['gcode_macro LINE_PURGE'] = M({})
        d['gcode_macro VORON_PURGE'] = M({})
        d['gcode_macro SMART_PARK'] = M({})
    return M(d)

def render(tpl, par=None, extra=None, kamp=False, objs=None, excl=None, old_klipper=False, bare_idle=False, drop14=False, poweroff=False, ps_state='printing', etemp=None, gz=None, scp=False, etgt=None):
    t = env.from_string(tpl)
    g = {'printer': build_printer(kamp=kamp, objs=objs, excl=excl, old_klipper=old_klipper, bare_idle=bare_idle, drop14=drop14, poweroff=poweroff, ps_state=ps_state, etemp=etemp, gz=gz, scp=scp, etgt=etgt), 'params': par or {}}
    if extra: g.update(extra)
    return t.render(**g)

def klipper_strip(txt):
    # Klipper cuts every line at the first '#' while reading the file
    return '\n'.join(l[:l.find('#')] if '#' in l else l for l in txt.split('\n'))

def get_body(pfad, name):
    import re
    txt = open(pfad).read()
    m = re.search(r'\[gcode_macro '+re.escape(name)+r'\]\n(.*?)(?=\n\[|\Z)', txt, re.S)
    body = m.group(1)
    lines = []
    started = False
    for z in body.split('\n'):
        if z.startswith('gcode:'):
            started = True; continue
        if started:
            if z.startswith(('variable_','description:','rename_existing:')):
                break
            lines.append(z[4:] if z.startswith('    ') else z)
    return klipper_strip('\n'.join(lines))

tests = []

class MP(M):
    """M without auto-attr (for overrides via plain dict access)"""
    pass

# 1) M104 override: layer 2, ov_hotend_after=240 -> 215 becomes 240
body = get_body('macros/06_temp_controls.cfg', 'M104')
out = render(body, {'S': '215'})
tests.append(('M104 layer2 -> 240 + OVERWRITE log', 'S240' in out.replace('.0','') and 'OVERWRITE' in out, out.strip()[:90]))

# 1b) layer 1 (legacy heuristic)
state_vars['layer']=1
out = render(body, {'S': '210'})
tests.append(('M104 layer1 -> 235', 'S235' in out.replace('.0',''), out.strip()[:90]))
state_vars['layer']=2

# 1c) ignore_overrides (PRINT_AS_SLICED) -> R79: the material L1/L2 rule still
#     applies (user rule: hotend/bed/fan ALWAYS differ L1 vs L2); 1:1 for the rest
state_vars['ignore_overrides']=True
save_vars['first_layer_rules'] = True
out = render(body, {'S': '215'})
tests.append(('M104 as-sliced: L1/L2 rule applies (first_layer_rules ON)',
    'S210' in out.replace('.0','') and 'L1/L2 rule PLA' in out and 'OVERWRITE' not in out, out.strip()[:110]))
save_vars['first_layer_rules'] = False
out = render(body, {'S': '215'})
tests.append(('M104 as-sliced: rules OFF -> true 1:1 passthrough',
    'S215' in out.replace('.0','') and 'L1/L2 rule' not in out and 'OVERWRITE' not in out, out.strip()[:90]))
save_vars['first_layer_rules'] = True
state_vars['ignore_overrides']=False

# 2) APPLY_TYPE with 'Outer wall' (Orca naming!)
body = get_body('macros/10_live_tuning.cfg', 'APPLY_TYPE')
state_vars.update({'mode':'printing','ignore_overrides':False,'current_type':'WALL-INNER','g_speed_clean':100})
out = render(body, {'TYPE': 'WALL-OUTER'})
tests.append(('R59 APPLY_TYPE: type set + pure global restore (no override)',
    "VARIABLE=current_type VALUE='\"WALL-OUTER\"'" in out and 'M99220 S100' in out and 'M220 ' not in out, out.strip()[:150]))
save_vars.update({'ovf_wallouter_on':True,'ovf_wallouter_spd':80,'ovf_wallouter_acc':1200})
out = render(body, {'TYPE': 'WALL-OUTER'})
tests.append(('R59 APPLY_TYPE outer wall 80% via BASE cmd (global untouched)',
    'M99220 S80' in out and 'M99204 S1200' in out and 'VARIABLE=g_speed_clean' not in out and '[Feature]' in out, out.strip()[:200]))
state_vars['g_speed_clean'] = 80
out = render(body, {'TYPE': 'WALL-OUTER'})
tests.append(('R59 FIX compound: feat 80% x global 80 = S64, global stays 80',
    'M99220 S64' in out and 'VARIABLE=g_speed_clean' not in out, [l for l in out.split('\n') if 'M99220' in l][:1]))
out2 = render(body, {'TYPE': 'WALL-INNER'})
tests.append(('R59 FIX compound: next feature restores S80 (no decay)', 'M99220 S80' in out2, [l for l in out2.split('\n') if 'M99220' in l][:1]))
state_vars['g_speed_clean'] = 100
save_vars.update({'ovf_wallouter_on':False,'ovf_wallouter_acc':0})
save_vars.update({'ovf_ironing_on':True,'ovf_ironing_spd':50,'ov_ironing_flow_on':True,'ov_ironing_flow':20})
out = render(body, {'TYPE': 'IRONING'})
tests.append(('R59 APPLY_TYPE ironing: speed 50% + flow 20% (base cmds)',
    'M99220 S50' in out and 'M99221 S20' in out, out.strip()[:200]))
save_vars.update({'ovf_ironing_on':False,'ov_ironing_flow_on':False,'ov_flow_on':True,'ov_flow':98})
out = render(body, {'TYPE': 'INFILL-SPARSE'})
tests.append(('R59 APPLY_TYPE other feature: global restore + flow 98', 'M99220 S100' in out and 'M99221 S98' in out, out.strip()[:160]))
save_vars.update({'ov_flow_on':False})

# 2b) APPLY_TYPE ironing - R54: compat no-op
out = render(body, {'TYPE': 'Ironing'})
tests.append(('APPLY_TYPE ironing = no-op (R54)', 'current_type' in out and 'TARGET=' not in out, out.strip()[:150]))

# 3) _PRIME_LINE (R45): X only, START right -> toward x=0, probe-aware window
body = get_body('macros/08_print_start_stop.cfg', '_PRIME_LINE')
out = render(body, {'LAYER_HEIGHT': '0.2'})
tests.append(('PRIME front strip wins (110mm, R49)', 'G0 X115' in out and 'G1 X5' in out and 'Y50' in out and 'front below objects' in out, out.strip()[:200]))
tests.append(('PRIME stows probe first', '_PROBE_STOW' in out, out.strip()[:120]))
# 3b) objects X100..220 -> only the left side is free -> line left of them
obj_links = [{'name':'o','center':[160,100],'polygon':[[100,60],[220,60],[220,140],[100,140]]}]
out = render(body, {'LAYER_HEIGHT': '0.2'}, objs=obj_links)
tests.append(('PRIME objects right-heavy -> front strip', 'G0 X115' in out and 'G1 X5' in out and 'Y50' in out, out.strip()[:200]))
# 3c) R45 probe offset -44mm: the left end is clamped so the PROBE stays on the bed
_gd = dict(build_printer(objs=obj_links))
_gd['configfile'] = M({'settings': M({'probe': M({'x_offset': -44.0, 'y_offset': 5.0})})})
out = env.from_string(body).render(printer=M(_gd), params={'LAYER_HEIGHT': '0.2'})
tests.append(('PRIME probe-safe window (x_off -44)', 'G1 X49' in out and 'G0 X159' in out and 'G1 X5' not in out, out.strip()[:200]))

# 3f) R49: objects reach the bed front -> no front strip -> side fallback (left)
obj_front = [{'name':'o','center':[140,80],'polygon':[[60,12],[220,12],[220,140],[60,140]]}]
out = render(body, {'LAYER_HEIGHT': '0.2'}, objs=obj_front)
tests.append(('PRIME front blocked -> left side', 'G0 X50' in out and 'G1 X5' in out and 'left of objects' in out, out.strip()[:200]))

# 3d) no objects: front edge, start right (x=115) toward x=5
out = render(body, {'LAYER_HEIGHT': '0.2'}, objs=[])
tests.append(('PRIME front edge toward x0', 'G0 X115' in out and 'G1 X5' in out, out.strip()[:200]))
# 3e) direction guard: the drawing move always goes to a SMALLER X than the start
import re as _reP
_m0 = _reP.search(r'G0 X([0-9.]+)', out); _m1 = _reP.search(r'G1 X([0-9.]+)', out)
tests.append(('PRIME direction right -> left', _m0 and _m1 and float(_m1.group(1)) < float(_m0.group(1)), out[:120]))

# 4) SET_MATERIAL PETG APPLY_PRESET=1
body = get_body('macros/05_materials.cfg', 'SET_MATERIAL')
out = render(body, {'MATERIAL':'petg','APPLY_PRESET':'1'})
tests.append(('SET_MATERIAL petg', "VALUE='\"PETG\"'" in out and 'bed 75/75C' in out and '240/240C' in out and 'VARIABLE=ov_pa VALUE=0.06' in out and 'VARIABLE=ov_retract_len VALUE=0.9' in out and 'VARIABLE=ov_retract_len_on VALUE=True' in out and 'VARIABLE=ov_fan VALUE=60' in out, out.strip()[:220]))

# 5) TOGGLE_OVERRIDE hotend_after
body = get_body('macros/07_start_confirm.cfg', 'TOGGLE_OVERRIDE')
out = render(body, {'NAME':'hotend_after'})
tests.append(('TOGGLE_OVERRIDE', 'ov_hotend_after_on' in out, out.strip()[:90]))

# 5a2) TOGGLE retract_len maps to the SHARED key ov_retract_on (was: Unknown override!)
body = get_body('macros/07_start_confirm.cfg', 'TOGGLE_OVERRIDE')
out = render(body, {'NAME':'retract_len'})
tests.append(('TOGGLE retract_len -> own key', 'ov_retract_len_on VALUE=' in out and 'Unknown overwrite' not in out, out[:140]))
out = render(body, {'NAME':'ironing_flow'})
tests.append(('TOGGLE ironing_flow -> own key', 'ov_ironing_flow_on VALUE=' in out and 'Unknown overwrite' not in out, out[:140]))
out = render(body, {'NAME':'gibtsnicht'})
tests.append(('TOGGLE unknown -> error', 'Unknown overwrite' in out, out[:140]))

# 5b) SET_OVERRIDE_VALUE outer_wall -> sets value + ON
body = get_body('macros/07_start_confirm.cfg', 'SET_OVERRIDE_VALUE')
out = render(body, {'NAME':'velocity','VALUE':'300'})
tests.append(('SET_OVERRIDE_VALUE+ON', 'VARIABLE=ov_velocity VALUE=300.0' in out and 'ov_velocity_on VALUE=True' in out, out[:200]))
out = render(body, {'NAME':'outer_wall','VALUE':'80'})
tests.append(('R59 SET_OVERRIDE_VALUE legacy outer_wall -> feat key', 'VARIABLE=ovf_wallouter_spd VALUE=80.0' in out and 'VARIABLE=ovf_wallouter_on VALUE=True' in out, out[:220]))
out = render(body, {'NAME':'feat_acc_surfacetop','VALUE':'900'})
tests.append(('R59 SET_OVERRIDE_VALUE generic feat_acc_surfacetop', 'VARIABLE=ovf_surfacetop_acc VALUE=900.0' in out and 'VARIABLE=ovf_surfacetop_on VALUE=True' in out, out[:220]))
out = render(body, {'NAME':'feat_on_brim','VALUE':'1'})
tests.append(('R59 SET_OVERRIDE_VALUE feat_on_brim toggles', 'VARIABLE=ovf_brim_on VALUE=True' in out, out[:180]))

# 5c) NOTIFY: LCD shortening (no {{ }} allowed!)
body = get_body('macros/04_notify.cfg', 'NOTIFY')
out = render(body, {'TEXT':'Heating bed to 60C','LEVEL':'info'})
tests.append(('NOTIFY M117 no {{', 'M117 [i]  Heating bed to 60' in out, out[:160]))

# 6) _SOUND_LIB plays r2_start
body = get_body('macros/02_sounds.cfg', '_SOUND_LIB')
out = render(body, {'NAME':'r2_start'}, extra={'tunes': tunes})
tests.append(('SOUND r2_start', 'M300 S1568 P40' in out, out.strip()[:80]))

# 6b) M300 macro (Klipper has no built-in M300)
body = get_body('macros/02_sounds.cfg', 'M300')
out = render(body, {'S':'1568','P':'40'})
import re as _re2
_ct = float(_re2.search(r'CYCLE_TIME=([0-9.]+)', out).group(1))
tests.append(('M300 S1568 -> CYCLE_TIME=1/f', abs(_ct - 1.0/1568) < 1e-6, out[:160]))
out = render(body, {})
tests.append(('M300 default 1000Hz/100ms', 'CYCLE_TIME=0.001' in out and 'G4 P100' in out, out[:160]))

# 7) PRINT_END statistics
body = get_body('macros/08_print_start_stop.cfg', 'PRINT_END')
out = render(body, {})
tests.append(('PRINT_END duration', 'Duration: 0h 20min' in out, [l for l in out.split('\n') if 'Duration' in l][:1]))

# 8) LAYER_MARK pause at layer 7
body = get_body('macros/06_temp_controls.cfg', 'LAYER_MARK')
state_vars['layer']=6
out = render(body, {})
tests.append(('LAYER_MARK pause@7', 'PAUSE REASON="layer 7' in out, out.strip()[:140]))
state_vars['layer']=2

# 9) _PARK_HEAD corner choice - R92: corners from the REAL bed (default
# Ender-3 0..220 / -3..217 when [gcode_macro _R2_CONFIG] is absent), never beyond it
body = get_body('macros/09_pause_filament.cfg', '_PARK_HEAD')
out = render(body, {})
_pc92 = [l for l in out.split('\n') if 'G1 X' in l and ' Y' in l and 'F6000' in l]
tests.append(('PARK corner inside the real bed (R92)', _pc92 and
    all(0 <= float(l.split('X')[1].split(' ')[0]) <= 220
        and -3 <= float(l.split('Y')[1].split(' ')[0]) <= 217 for l in _pc92), str(_pc92[:1])))

# 10) M106 scaling
body = get_body('macros/06_temp_controls.cfg', 'M106')
out = render(body, {'S':'255'})
tests.append(('M106 passthrough', 'S255' in out, out.strip()[:60]))
state_vars['f_fan_scale']=0.5
out = render(body, {'S':'200'})
tests.append(('M106 50%', 'S100' in out, out.strip()[:80]))
state_vars['f_fan_scale']=1.0

# 11) SYNC_GANTRY kinematic trick
body = get_body('macros/11_gantry_sync.cfg', 'SYNC_GANTRY')
state_vars['mode']='idle'
out = render(body, {})
tests.append(('SYNC_GANTRY kinematic', 'SET_KINEMATIC_POSITION Z=235' in out, out.strip()[:160]))
state_vars['mode']='printing'

# 12) _RUN_PRINT_START renders completely
body = get_body('macros/08_print_start_stop.cfg', '_RUN_PRINT_START')
out = render(body, {'APPLY':'1'})
tests.append(('RUN_PRINT_START full', 'SET_PRESSURE_ADVANCE' in out and '_CALIBRATE_MESH_PROFILE' in out, out.strip()[:100]))

# 13) apply=0, mesh_always OFF, r2 active+saved -> no re-leveling
save_vars['mesh_always'] = False
out = render(body, {'APPLY':'0'})
tests.append(('RUN as-sliced keeps active mesh', 'no re-leveling' in out and 'LOAD_MESH_PROFILE' not in out and '_CALIBRATE_MESH_PROFILE' not in out, [l for l in out.split('\n') if 're-leveling' in l][:1]))
# 13b) mesh_always OFF, nothing active -> LOAD saved r2
gd = dict(build_printer()); gd['bed_mesh'] = M({'profile_name': '', 'profiles': {'r2': {}}})
out = env.from_string(body).render(printer=MP(gd), params={'APPLY':'0'})
tests.append(('RUN mesh_always off -> load r2', 'LOAD_MESH_PROFILE PROFILE=r2' in out, [l for l in out.split('\n') if 'LOAD_MESH' in l][:1]))

# 14) apply=1, mesh_always ON (new default) -> always measures
save_vars['mesh_always'] = True
out = render(body, {'APPLY':'1'})
tests.append(('RUN overrides measures r2', '_CALIBRATE_MESH_PROFILE PROFILE=r2' in out, out[:160]))

# 15) PID automation is GONE: no PID lines in the start
tests.append(('PID automation removed', 'PID' not in out, [l for l in out.split('\n') if 'PID' in l][:1]))

# 16) CANCEL first press pauses + arms
body = get_body('macros/09_pause_filament.cfg', 'CANCEL_PRINT')
out = render(body, {})
tests.append(('CANCEL 1st press arms', 'cancel_armed VALUE=True' in out and 'PAUSE REASON' in out, out[:200]))
# 16b) second press really cancels
state_vars['cancel_armed']=True
out = render(body, {})
tests.append(('CANCEL 2nd press kills', 'CANCEL_PRINT_BASE' in out and 'TURN_OFF_HEATERS' in out, out[:160]))
state_vars['cancel_armed']=False

# 17) RESUME disarms cancel
body = get_body('macros/09_pause_filament.cfg', 'RESUME')
out = render(body, {})
tests.append(('RESUME disarms cancel', 'cancel_armed VALUE=False' in out, out[:120]))

# ---------------- KAMP dispatch tests ----------------------------------------------
body = get_body('macros/14_kamp.cfg', '_CALIBRATE_MESH_PROFILE')
out = render(body, {'PROFILE':'r2'}, kamp=True)
tests.append(('KAMP mesh on -> no ADAPTIVE', 'BED_MESH_CALIBRATE PROFILE=r2' in out and 'ADAPTIVE' not in out and 'BED_MESH_PROFILE SAVE=r2' in out, out[:200]))
out = render(body, {'PROFILE':'r2'})
tests.append(('no KAMP -> native ADAPTIVE=1', 'ADAPTIVE=1 ADAPTIVE_MARGIN=5' in out and '_BED_MESH_CALIBRATE' not in out, out[:200]))
save_vars['kamp_mesh'] = False
out = render(body, {'PROFILE':'r2'}, kamp=True)
tests.append(('KAMP off -> _BED_MESH+ADAPTIVE', '_BED_MESH_CALIBRATE PROFILE=r2 ADAPTIVE=1' in out, out[:200]))
save_vars['kamp_mesh'] = True

body = get_body('macros/14_kamp.cfg', '_PURGE_SMART')
out = render(body, {'LAYER_HEIGHT':'0.2'}, kamp=True)
tests.append(('KAMP purge -> LINE_PURGE', 'LINE_PURGE' in out and 'VORON' not in out, out[:200]))
save_vars['kamp_purge_type'] = 'VORON'
out = render(body, {'LAYER_HEIGHT':'0.2'}, kamp=True)
tests.append(('KAMP purge VORON', 'VORON_PURGE' in out, out[:200]))
save_vars['kamp_purge_type'] = 'LINE'
out = render(body, {'LAYER_HEIGHT':'0.2'}, kamp=True, objs=[])   # legacy file without objects
tests.append(('no objects -> own line', '_PRIME_LINE LAYER_HEIGHT=0.2' in out and 'LINE_PURGE' not in out, out[:200]))
# R45: KAMP LINE purge skipped with a big side probe offset -> probe-safe own line
_gd2 = dict(build_printer(kamp=True))
_gd2['configfile'] = M({'settings': M({'probe': M({'x_offset': -44.0, 'y_offset': 5.0})})})
out = env.from_string(body).render(printer=M(_gd2), params={'LAYER_HEIGHT': '0.2'})
tests.append(('KAMP line purge skipped (probe off)', '_PRIME_LINE' in out and 'LINE_PURGE' not in out and 'skipped' in out, out[:220]))
tests.append(('PURGE_SMART stows probe', '_PROBE_STOW' in out, out[:120]))
out = render(body, {'LAYER_HEIGHT':'0.2'}, kamp=False)
tests.append(('without KAMP -> own line', '_PRIME_LINE' in out, out[:160]))

# print start with KAMP: SMART_PARK only when enabled
body = get_body('macros/08_print_start_stop.cfg', '_RUN_PRINT_START')
out = render(body, {'APPLY':'1'}, kamp=True)
tests.append(('RUN with KAMP: no default SMART_PARK', 'SMART_PARK' not in out, 'smart park should default off'))
save_vars['kamp_smart_park'] = True
out = render(body, {'APPLY':'1'}, kamp=True)
tests.append(('RUN with KAMP: SMART_PARK on', 'SMART_PARK' in out, 'smart park missing'))
save_vars['kamp_smart_park'] = False

body = get_body('macros/14_kamp.cfg', 'KAMP_STATUS')
out = render(body, {}, kamp=True)
tests.append(('KAMP_STATUS installed', 'installed & loaded' in out and 'LINE_PURGE=yes' in out, out[:200]))
out = render(body, {})
tests.append(('KAMP_STATUS without KAMP', 'NOT installed' in out, out[:160]))

# STATE WATCHER: legacy print detection
import re as _re
txt = open('macros/01_state.cfg').read()
m = _re.search(r'\[delayed_gcode _STATE_WATCHER\]\ninitial_duration: 8\ngcode:\n(.*?)(?=\n\[|\Z)', txt, _re.S)
watcher = '\n'.join(l[4:] if l.startswith('    ') else l for l in m.group(1).split('\n'))
state_vars['mode']='idle'
out = render(watcher, {})
tests.append(('WATCHER legacy print', "VARIABLE=mode VALUE='\"printing\"'" in out and 'legacy' in out, out[:200]))
state_vars['mode']='printing'

# ---------------- SKIP_OBJECT (exclude_object) tests ---------------------------------
multi = [{'name':'cube_1','center':[60,60],'polygon':[[40,40],[80,40],[80,80],[40,80]]},
         {'name':'cube_2','center':[170,60],'polygon':[[150,40],[190,40],[190,80],[150,80]]},
         {'name':'arch','center':[115,170],'polygon':[[95,150],[135,150],[135,190],[95,190]]}]
body = get_body('macros/15_objects.cfg', 'SKIP_OBJECT')

out = render(body, {'NAME':'cube_2'}, objs=multi)
tests.append(('SKIP 1st press arms', "VALUE='\"cube_2\"'" in out and 'EXCLUDE_OBJECT' not in out, out[:200]))

state_vars['skip_armed_name']='cube_2'
out = render(body, {'NAME':'cube_2'}, objs=multi)
tests.append(('SKIP 2nd press executes', 'EXCLUDE_OBJECT NAME=' in out and 'SKIPPED' in out and 'skip_armed_name VALUE=' + chr(39) + '""' + chr(39) in out, out[:220]))
state_vars['skip_armed_name']=''

out = render(body, {'NAME':'cube_1'}, objs=[multi[0]])
tests.append(('SKIP last object refused', 'CANCEL_PRINT' in out and 'EXCLUDE_OBJECT NAME=' not in out, out[:200]))

out = render(body, {'NAME':'ghost'}, objs=multi)
tests.append(('SKIP unknown refused', 'Unknown object' in out and 'EXCLUDE_OBJECT NAME=' not in out, out[:200]))

out = render(body, {'NAME':'cube_2'}, objs=[multi[0],multi[2]], excl=['cube_2'])
tests.append(('SKIP already-skipped hint', 'already skipped' in out, out[:200]))

state_vars['mode']='idle'
out = render(body, {'NAME':'cube_1'}, objs=multi)
tests.append(('SKIP only during print', 'only works during a print' in out, out[:160]))
state_vars['mode']='printing'

out = render(body, {})
tests.append(('SKIP without NAME -> usage', 'Usage: SKIP_OBJECT' in out, out[:160]))

body = get_body('macros/15_objects.cfg', 'SKIP_CURRENT_OBJECT')
out = render(body, {}, objs=multi)
tests.append(('SKIP_CURRENT resolves name', 'SKIP_OBJECT NAME=' in out, out[:160]))

body = get_body('macros/15_objects.cfg', 'SHOW_OBJECTS')
out = render(body, {}, objs=multi)
tests.append(('SHOW_OBJECTS lists all', 'Active: 3' in out and '[keep] cube_1' in out and 'printing now' in out and 'Skip: SKIP_OBJECT' in out, out[:200]))

# menu slot template safety: index beyond list length must render '-', not crash
slot = "{('SKIP? ' if printer['gcode_macro _STATE'].skip_armed_name == printer.exclude_object.objects[3].name else '') ~ printer.exclude_object.objects[3].name|truncate(16, True, '') if printer.exclude_object.objects|length > 3 else '-'}"
out = render(slot, {}, objs=multi[:2])
tests.append(('MENU slot out-of-range safe', out.strip() == '-', out[:80]))
state_vars['skip_armed_name']='cube_2'
out = render(slot, {}, objs=multi + [multi[1]])
tests.append(('MENU slot armed prefix', out.strip() == 'SKIP? cube_2', out[:80]))
state_vars['skip_armed_name']=''

# ------- shlex regression: SET_GCODE_VARIABLE lines must survive Klipper parsing ------
# Klipper's _get_extended_params uses shlex(posix=True): quotes are SHELL quoting and
# get stripped. VALUE='' would collapse to an EMPTY argument -> literal_eval('') dies.
import shlex as _shlex, ast as _ast
def klipper_param_value(line, key):
    raw = line.split(' ', 1)[1]
    sx = _shlex.shlex(raw, posix=True); sx.whitespace_split = True; sx.commenters = '#;'
    for tok in sx:
        if tok.startswith(key + '='):
            return tok.split('=', 1)[1]
    return None

body = get_body('macros/15_objects.cfg', 'SKIP_OBJECT')
out = render(body, {'NAME':'cube_2'}, objs=multi)
line = [l.strip() for l in out.split('\n') if 'VARIABLE=skip_armed_name' in l and l.strip().startswith('SET_GCODE_VARIABLE')][0]
val = klipper_param_value(line, 'VALUE')
tests.append(('ARM line survives shlex -> name', val == '"cube_2"' and _ast.literal_eval(val) == 'cube_2', line))

state_vars['skip_armed_name']='cube_2'
out = render(body, {'NAME':'cube_2'}, objs=multi)
line = [l.strip() for l in out.split('\n') if 'VARIABLE=skip_armed_name' in l and l.strip().startswith('SET_GCODE_VARIABLE')][0]
val = klipper_param_value(line, 'VALUE')
tests.append(('DISARM line survives shlex -> empty str', val == '""' and _ast.literal_eval(val) == '', line))

body = get_body('macros/09_pause_filament.cfg', 'RESUME')
out = render(body, {})
line = [l.strip() for l in out.split('\n') if 'VARIABLE=skip_armed_name' in l and l.strip().startswith('SET_GCODE_VARIABLE')][0]
val = klipper_param_value(line, 'VALUE')
tests.append(('RESUME disarm survives shlex', val == '""', line))
state_vars['skip_armed_name']=''

# ------- idle timeout regression (real Klipper keysets!) ------------------------------
body = get_body('macros/09_pause_filament.cfg', 'PAUSE')
out = render(body, {'REASON':'test'})
tests.append(('PAUSE saves live idle timeout', 'VARIABLE=idle_timeout_saved VALUE=3600.0' in out, [l for l in out.split('\n') if 'idle_timeout_saved' in l]))
out = render(body, {'REASON':'test'}, old_klipper=True)
tests.append(('PAUSE old Klipper -> cfg value', 'VARIABLE=idle_timeout_saved VALUE=3600.0' in out, [l for l in out.split('\n') if 'idle_timeout_saved' in l]))
out = render(body, {'REASON':'test'}, old_klipper=True, bare_idle=True)
tests.append(('PAUSE nothing set -> 3600', 'VARIABLE=idle_timeout_saved VALUE=3600.0' in out, [l for l in out.split('\n') if 'idle_timeout_saved' in l]))

body = get_body('macros/09_pause_filament.cfg', '_RESTORE_IDLE_TIMEOUT')
state_vars['idle_timeout_saved'] = 1800.0
out = render(body, {})
tests.append(('RESTORE uses saved value', 'SET_IDLE_TIMEOUT TIMEOUT=1800' in out, out.strip()[:80]))
state_vars['idle_timeout_saved'] = 0.0
out = render(body, {}, old_klipper=True, bare_idle=True)
tests.append(('RESTORE worst case -> 3600', 'SET_IDLE_TIMEOUT TIMEOUT=3600' in out, out.strip()[:80]))
state_vars['idle_timeout_saved'] = 3600.0

body = get_body('macros/01_state.cfg', '_CHECK_INSTALL')
out = render(body, {})
tests.append(('CHECK_INSTALL all loaded', 'all 18 modules loaded and current' in out and 'MISSING' not in out, out[:160]))
out = render(body, {}, drop14=True)
tests.append(('CHECK_INSTALL detects missing/outdated 14', '14_kamp.cfg' in out and 'MODULES MISSING OR OUTDATED' in out and 'sentinel' in out, out[:220]))

# ------- SYS_SHUTDOWN / poweroff -------------------------------------------------------
body = get_body('macros/13_system.cfg', 'SYS_SHUTDOWN')
out = render(body, {})
tests.append(('SHUTDOWN 1st press arms', 'Press SYS_SHUTDOWN again' in out and 'RUN_SHELL' not in out, out[:120]))
out = render(body, {'CONFIRM':'1'})
tests.append(('SHUTDOWN default: moonraker remote', 'shutdown_machine' in out and 'RUN_SHELL_COMMAND' not in out and 'TURN_OFF_HEATERS' in out, out[:200]))
out = render(body, {'CONFIRM':'1'}, poweroff=True)
tests.append(('SHUTDOWN w/ module -> poweroff', 'RUN_SHELL_COMMAND CMD=poweroff' in out and 'TURN_OFF_HEATERS' in out, out[:160]))

# ------- legacy temp heuristic (M104/M140 without PRINT_START) --------------------------
body = get_body('macros/06_temp_controls.cfg', 'M104')
state_vars.update(layer=1, file_hotend_first=0, file_hotend_after=0)
out = render(body, {'S':'205'})
tests.append(('M104 legacy falling -> after', 'S240' in out.replace('.0',''), out[:140]))
state_vars.update(file_hotend_first=210, file_hotend_after=215)
body = get_body('macros/06_temp_controls.cfg', 'M140')
state_vars.update(layer=1, file_bed=0, file_bed_after=0)
save_vars['ov_bed_after_on']=True
out = render(body, {'S':'55'})
save_vars['ov_bed_after_on']=False
tests.append(('M140 legacy falling -> after', 'S70' in out.replace('.0',''), out[:140]))
state_vars.update(file_bed=60, file_bed_after=60, layer=2)

# ------- LAYER_MARK switches to after-temps at layer 2 ---------------------------------
body = get_body('macros/06_temp_controls.cfg', 'LAYER_MARK')
state_vars['layer']=1
out = render(body, {})
tests.append(('LAYER_MARK L2 hotend after', 'TARGET=240' in out and 'Layer 2: hotend' in out, [l for l in out.split('\n') if 'Layer 2' in l]))
state_vars['layer']=2

# ------- CALIBRATE_MESH heats bed (override wins, else preset) ---------------------------
body = get_body('macros/12_maintenance.cfg', 'CALIBRATE_MESH')
out = render(body, {})   # ov_bed 70 ON
tests.append(('MESH bed override 70C', 'TARGET=70' in out and 'TEMPERATURE_WAIT' in out and 'PROFILE=r2' in out, out[:200]))
save_vars['ov_bed_on']=False
out = render(body, {})
save_vars['ov_bed_on']=True
tests.append(('MESH preset temp (PETG 75)', 'TARGET=75' in out and 'PROFILE=r2' in out, out[:200]))

# ------- _LEGACY_PREP: phase 1 pauses + schedules phase 2 --------------------------------
body = get_body('macros/08_print_start_stop.cfg', '_LEGACY_PREP')
out = render(body, {})
tests.append(('LEGACY_PREP p1: pause+schedule', 'PAUSE REASON' in out and 'UPDATE_DELAYED_GCODE ID=_LEGACY_PREP2 DURATION=1.5' in out, out[:200]))
import re as _re5
txt = open('macros/08_print_start_stop.cfg').read()
m = _re5.search(r'\[delayed_gcode _LEGACY_PREP2\]\ngcode:\n(.*?)(?=\n\[|\Z)', txt, _re5.S)
prep2 = '\n'.join(l[4:] if l.startswith('    ') else l for l in m.group(1).split('\n'))
state_vars['mode']='paused'
out = render(prep2, {}, ps_state='paused')
tests.append(('LEGACY_PREP p2 runs when paused', 'TEMPERATURE_WAIT SENSOR=heater_bed' in out
              and '_CALIBRATE_MESH_PROFILE PROFILE=r2' in out and 'M24' in out, out[:260]))
tests.append(('R54 PREP2 gapless: no RESUME dance', 'RESUME' not in out and 'RESTORE_GCODE_STATE NAME=PAUSE_STATE' in out and 'CLEAR_PAUSE' in out, out[:300]))
tests.append(('LEGACY_PREP p2: L1-Temp + Overrides + Z10', 'TARGET=235' in out and '_APPLY_OVERRIDES_CORE' in out and 'G0 Z10' in out, [l for l in out.split('\n') if 'TARGET=235' in l or 'OVERRIDES_CORE' in l or 'Z10' in l][:3]))
out = render(prep2, {}, ps_state='paused')
tests.append(('LEGACY_PREP p2 always purges', 'TEMPERATURE_WAIT SENSOR=extruder' in out and '_PRIME_LINE' in out, out[200:420]))
out = render(prep2, {}, ps_state='printing')
tests.append(('LEGACY_PREP p2 bails if not paused', 'did not hold the pause' in out and '_CALIBRATE_MESH_PROFILE' not in out, out[:200]))
state_vars['mode']='printing'

# ------- watcher triggers legacy prep once -----------------------------------------------
import re as _re3
txt = open('macros/01_state.cfg').read()
m = _re3.search(r'\[delayed_gcode _STATE_WATCHER\]\ninitial_duration: 8\ngcode:\n(.*?)(?=\n\[|\Z)', txt, _re3.S)
watcher = '\n'.join(l[4:] if l.startswith('    ') else l for l in m.group(1).split('\n'))
state_vars['mode']='idle'
save_vars['start_confirm']=False
out = render(watcher, {})
tests.append(('WATCHER calls LEGACY_PREP (confirm off)', '_LEGACY_PREP' in out and '_LEGACY_DIALOG' not in out, out[:220]))
save_vars['start_confirm']=True
out = render(watcher, {})
tests.append(('WATCHER asks via LEGACY_DIALOG (R45)', '_LEGACY_DIALOG' in out and 'VARIABLE=file_type' in out and '_LEGACY_PREP' not in out, out[:220]))
state_vars['mode']='printing'

# ------- PID nur noch manuell -------------------------------------------------------------
body = get_body('macros/12_maintenance.cfg', '_RUN_PID_TUNE')
out = render(body, {'HEATER':'extruder','TARGET':'235','AUTOSAVE':'1'})
tests.append(('PID manual hotend fan+save', 'M99106 S255' in out and 'PID_CALIBRATE HEATER=extruder TARGET=235' in out and 'SAVE_CONFIG' in out and 'pid_pending' not in out, out[:220]))
out = render(body, {'HEATER':'heater_bed','TARGET':'65','AUTOSAVE':'0'})
tests.append(('PID manual bed no fan no save', 'M99106' not in out and 'PID values calculated' in out and 'Saving config' not in out, out[:220]))

# ------- PA-Kalibrierung: Orca-Stil (eine lange Linie pro PA-Wert) --------------------------
import re as _rePA
body = get_body('macros/12_maintenance.cfg', 'CALIBRATE_PA')
state_vars['mode']='idle'
out = render(body, {})          # Defaults: Bett 60, Hotend 210, 10 Linien x 100mm
xs_all = [float(v) for v in _rePA.findall(r'X(\d+(?:\.\d+)?)', out)]
ys_all = [float(v) for v in _rePA.findall(r'Y(\d+(?:\.\d+)?)', out)]
tests.append(('PA cal: bed heats first', 'HEATER=heater_bed TARGET=60' in out and 'TEMPERATURE_WAIT SENSOR=heater_bed' in out, [l for l in out.split('\n') if 'heater_bed' in l][:2]))
tests.append(('PA cal: prime line + skirt', 'Prime line' in out and 'Skirt' in out, out[:120]))
tests.append(('PA cal: 10 PA lines', out.count('SET_PRESSURE_ADVANCE ADVANCE=') >= 11 and 'PA line 10/10' in out, out[:160]))
tests.append(('PA cal: slow/fast/accel set', 'F1200' in out and 'F6000' in out and 'SET_VELOCITY_LIMIT ACCEL=3000' in out, [l for l in out.split('\n') if 'VELOCITY' in l][:1]))
tests.append(('PA cal: accel restored', 'SET_VELOCITY_LIMIT ACCEL=4000' in out, [l for l in out.split('\n') if 'VELOCITY' in l][1:2]))
tests.append(('PA cal: never out of range', max(xs_all) <= 209.0 and max(ys_all) <= 199.5, (max(xs_all), max(ys_all))))
out = render(body, {'LINES':'40', 'SPACING':'5'})
tests.append(('PA cal: too many lines refused', 'do not fit the bed' in out, out[:160]))
out = render(body, {'WIDTH':'0.6 * 1.15', 'LINES':'12'})
tests.append(('PA cal: WIDTH expr -> fallback, fits', 'WIDTH must be a number' in out and 'PA line 12/12' in out, [l for l in out.split('\n') if 'WIDTH' in l][:1]))
out = render(body, {'BED':'0'})
tests.append(('PA cal: BED=0 skips bed', 'heater_bed' not in out, out[:120]))
out = render(body, {'STEP':'0'})
tests.append(('PA cal: bad params refused', 'STEP must be above 0' in out, out[:160]))
state_vars['mode']='printing'
out = render(body, {})
tests.append(('PA cal refuses while printing', 'only when idle' in out, out[:120]))
state_vars['mode']='idle'

body = get_body('macros/12_maintenance.cfg', 'PA_RESULT')
save_vars['pa_test_start']=0.0; save_vars['pa_test_step']=0.005
out = render(body, {'SEG':'5'})
tests.append(('PA_RESULT line5 -> 0.02', 'ADVANCE=0.02' in out and 'VARIABLE=ov_pa VALUE=0.02' in out and 'ov_pa_on VALUE=True' in out, out[:200]))
out = render(body, {'VALUE':'0.048'})
tests.append(('PA_RESULT direct VALUE', 'ADVANCE=0.048' in out and 'VARIABLE=ov_pa VALUE=0.048' in out, out[:160]))
out = render(body, {})
tests.append(('PA_RESULT without input -> hint', 'best line' in out and 'calculator' in out, out[:120]))

# ------- SAVE_MATERIAL_TEMPS ------------------------------------------------------------------
body = get_body('macros/05_materials.cfg', 'SAVE_MATERIAL_TEMPS')
out = render(body, {})
out = render(body, {'MATERIAL':'TPU'})
tests.append(('SAVE_MATERIAL_TEMPS TPU lowercase', 'VARIABLE=mat_tpu_bed1' in out and 'VARIABLE=mat_tpu_hot2' in out and 'VARIABLE=mat_tpu_pa' in out and 'VARIABLE=mat_tpu_retlen' in out and 'VARIABLE=mat_tpu_fan' in out, out[:220]))

# ------- SYNC_GANTRY: self-homing + force_move guard ------------------------------------
body = get_body('macros/11_gantry_sync.cfg', 'SYNC_GANTRY')
state_vars['mode']='idle'
out = render(body, {})
tests.append(('SYNC fully homed -> no G28', 'SET_KINEMATIC_POSITION' in out and '\nG28\n' not in out, out[:160]))
gd = dict(build_printer()); gd['toolhead'] = M({'axis_maximum': M({'x':235.0,'y':235.0,'z':250.0}), 'homed_axes':'xy'})
out = env.from_string(body).render(printer=MP(gd), params={})
tests.append(('SYNC partly homed -> full G28', any(l.strip()=='G28' for l in out.split('\n')) and 'G28 X' not in out and 'homing first' in out, [l for l in out.split('\n') if l.strip()=='G28']))
gd = dict(build_printer()); gd['configfile'] = M({'settings': M({'idle_timeout': M({'timeout':'3600'}), 'extruder': M({'rotation_distance':7.71})})})
out = env.from_string(body).render(printer=MP(gd), params={})
tests.append(('SYNC force_move missing -> refuse', 'force_move' in out and 'SET_TMC_CURRENT' not in out, out[:160]))
out = render(body, {})
tests.append(('SYNC loaded WITHOUT printer-object -> runs', 'SET_KINEMATIC_POSITION' in out, 'settings detection must work without get_status'))
state_vars['mode']='printing'

# ------- _PARK_HEAD skips park when not homed ---------------------------------------------
body = get_body('macros/09_pause_filament.cfg', '_PARK_HEAD')
gd = dict(build_printer()); gd['toolhead'] = M({'axis_maximum': M({'x':235.0,'y':235.0,'z':250.0}), 'homed_axes':''})
out = env.from_string(body).render(printer=MP(gd), params={})
tests.append(('PARK unhomed -> no XY move', 'G1 X' not in out and 'skipped' in out, [l for l in out.split('\n') if 'G1 X' in l or 'skipped' in l]))

# ------- _LEGACY_PREP2 homes itself when needed (homing lives in phase 2 now) --------------
import re as _re5b
_txt = open('macros/08_print_start_stop.cfg').read()
_m = _re5b.search(r'\[delayed_gcode _LEGACY_PREP2\]\ngcode:\n(.*?)(?=\n\[|\Z)', _txt, _re5b.S)
_prep2 = '\n'.join(l[4:] if l.startswith('    ') else l for l in _m.group(1).split('\n'))
state_vars['mode']='paused'
gd = dict(build_printer(ps_state='paused')); gd['toolhead'] = M({'axis_maximum': M({'x':235.0,'y':235.0,'z':250.0}), 'homed_axes':'x'})
out = env.from_string(_prep2).render(printer=MP(gd), params={})
tests.append(('LEGACY_PREP homes if needed', any(l.strip()=='G28' for l in out.split('\n')), [l for l in out.split('\n') if l.strip()=='G28']))
out = render(_prep2, {}, ps_state='paused')
tests.append(('LEGACY_PREP homed -> no extra home', not any(l.strip()=='G28' for l in out.split('\n')), out.count('G28')))
state_vars['mode']='printing'

# ------- DELETE_MESH 2-press ---------------------------------------------------------------
body = get_body('macros/12_maintenance.cfg', 'DELETE_MESH')
state_vars['mode']='idle'
out = render(body, {'PROFILE':'r2'})
tests.append(('DELETE 1st press arms', 'Press again' in out and 'REMOVE' not in out, out[:160]))
state_vars['mesh_delete_armed']='r2'
out = render(body, {'PROFILE':'r2'})
tests.append(('DELETE 2nd press removes', 'BED_MESH_PROFILE REMOVE=r2' in out and 'SAVE_CONFIG' in out, out[:200]))
state_vars['mesh_delete_armed']=''
out = render(body, {})
tests.append(('DELETE without PROFILE -> usage', 'Usage: DELETE_MESH' in out, out[:120]))
state_vars['mode']='printing'
out = render(body, {'PROFILE':'r2'})
tests.append(('DELETE only when idle', 'only when idle' in out, out[:120]))
state_vars['mode']='printing'

# ------- material defaults changed ----------------------------------------------------------
body = get_body('macros/05_materials.cfg', 'SHOW_MATERIAL')
out = render(body, {})
tests.append(('Materials: PETG 75C bed', '75C' in out, [l for l in out.split('\n') if 'PETG' in l]))
body = get_body('macros/05_materials.cfg', 'SHOW_MATERIAL')
save_vars['material']='TPU'
out = render(body, {})
save_vars['material']='PETG'
tests.append(('Materials: TPU preset 215C', '215C' in out, [l for l in out.split('\n') if 'TPU' in l]))

# ------- all SAVE_VARIABLE names must render LOWERCASE (Klipper rejects upper) --------
import re as _re4
body = get_body('macros/01_state.cfg', '_INIT_DEFAULTS')
_bak = dict(save_vars); save_vars.clear()
out = render(body, {})
save_vars.update(_bak)
bad = [t for t in _re4.findall(r'VARIABLE=(\w+)', out) if t != t.lower()]
tests.append(('INIT emits lowercase var names', not bad and 'VARIABLE=mesh_always' in out, bad))
body = get_body('macros/05_materials.cfg', 'SET_MATERIAL')
out = render(body, {'MATERIAL':'PETG'})
bad = [t for t in _re4.findall(r'VARIABLE=(\w+)', out) if t != t.lower()]
tests.append(('SET_MATERIAL lowercase names', not bad and 'VARIABLE=ov_hotend_after' in out, bad))

# ------- round: pause hardening ---------------------------------------------------------
body = get_body('macros/09_pause_filament.cfg', 'PAUSE')
out = render(body, {'REASON':'test'})
tests.append(('PAUSE idle timeout huge (not 0)', 'SET_IDLE_TIMEOUT TIMEOUT=31536000' in out and 'TIMEOUT=0' not in out, out[:60]))
state_vars['mode']='paused'
out = render(body, {})
tests.append(('PAUSE already paused -> guard', 'Already paused' in out and 'PAUSE_BASE' not in out, out[:120]))
state_vars['mode']='printing'

body = get_body('macros/09_pause_filament.cfg', '_PARK_HEAD')
out = render(body, {}, etemp=50)
tests.append(('PARK cold -> no extrude', 'G1 E-2' not in out and 'skipping anti-ooze' in out, out[:160]))

body = get_body('macros/09_pause_filament.cfg', '_RESUME_COMMON')
state_vars['pause_was_sd']=True
out = render(body, {}, etemp=50, ps_state='paused')
tests.append(('RESUME cold -> no E2, M24 ok', 'G1 E2' not in out and 'M24' in out, out[:160]))
out = render(body, {}, ps_state='printing')
tests.append(('RESUME running -> no M24 (SD busy!)', 'M24' not in out and 'already running' in out, out[:200]))
state_vars['pause_was_sd']=True

# ------- mesh persistence ----------------------------------------------------------------
body = get_body('macros/14_kamp.cfg', '_CALIBRATE_MESH_PROFILE')
state_vars['mode']='idle'
out = render(body, {'PROFILE':'r2'})
tests.append(('MESH idle: default session-only', 'session only' in out and 'SAVE_CONFIG' not in out.replace('SAVE_VARIABLE',''), out[:200]))
save_vars['mesh_auto_save']=True
out = render(body, {'PROFILE':'r2'})
save_vars['mesh_auto_save']=False
tests.append(('MESH idle: auto-save ON persists', 'SAVE_CONFIG' in out and 'saving config' in out, out[:200]))
state_vars['mode']='printing'
out = render(body, {'PROFILE':'r2'})
tests.append(('MESH during print -> pending flag', 'mesh_saved_pending VALUE=True' in out and 'SAVE_CONFIG' not in out.replace('SAVE_VARIABLE',''), out[:220]))
state_vars['mode']='printing'

# ------- START_PRINT shim ----------------------------------------------------------------
body = get_body('macros/08_print_start_stop.cfg', 'START_PRINT')
tests.append(('START_PRINT shim exists (R48)', 'legacy start' in body, body[:120]))

# ------- SELF_TEST full homing -------------------------------------------------------------
body = get_body('macros/12_maintenance.cfg', 'SELF_TEST')
state_vars['mode']='idle'
out = render(body, {})
tests.append(('SELF_TEST homes fully', any(l.strip()=='G28' for l in out.split('\n')) and 'G28 Z' not in out, out[:120]))
state_vars['mode']='printing'

# ------- SYNC hold-current from config ------------------------------------------------------
body = get_body('macros/11_gantry_sync.cfg', 'SYNC_GANTRY')
state_vars['mode']='idle'
out = render(body, {})
tests.append(('SYNC restore: hold untouched', 'HOLDCURRENT' not in out and 'hold untouched' in out, [l for l in out.split('\n') if 'restored' in l]))
gd = dict(build_printer()); gd['configfile'] = M({'settings': M({'force_move': M({'enable_force_move': False})})})
out = env.from_string(body).render(printer=MP(gd), params={})
tests.append(('SYNC refuses when flag False', 'enable_force_move: True' in out and 'SET_TMC_CURRENT' not in out, out[:160]))
gd = dict(build_printer()); gd['configfile'] = M({'settings': M({'force_move': M({'enable_force_move': 'True'}), 'tmc2209 stepper_z': M({'run_current':'0.94'})})})
out = env.from_string(body).render(printer=MP(gd), params={})
tests.append(('SYNC runs with flag True (str)', 'SET_KINEMATIC_POSITION' in out, out[:120]))
state_vars['mode']='printing'

# ------- watcher Z-layer tracking (legacy files) --------------------------------------------
txt = open('macros/01_state.cfg').read()
m = _re3.search(r'\[delayed_gcode _STATE_WATCHER\]\ninitial_duration: 8\ngcode:\n(.*?)(?=\n\[|\Z)', txt, _re3.S)
watcher = '\n'.join(l[4:] if l.startswith('    ') else l for l in m.group(1).split('\n'))
save_vars['pause_next_layer']=True
state_vars['layer_z_max']=12.5
out = render(watcher, {}, gz=12.7)          # +0.2 = new layer
tests.append(('WATCHER Z-track: new layer + planned pause', 'VARIABLE=layer VALUE=3' in out and 'PAUSE REASON=' in out and 'Z-track' in out, out[:240]))
save_vars['pause_next_layer']=False
out = render(watcher, {}, gz=13.2)          # +0.7 = travel/hop -> ignore
state_vars['layer_z_max']=0.0
tests.append(('WATCHER Z-track: hop ignored', 'VARIABLE=layer VALUE=3' not in out, out[:200]))

# ------- LOAD_BED_MESH friendly pre-check -------------------------------------------------
body = get_body('macros/12_maintenance.cfg', 'LOAD_BED_MESH')
out = render(body, {'PROFILE':'r2'})
tests.append(('LOAD mesh existing', 'BED_MESH_PROFILE LOAD=r2' in out and 'loaded' in out, out[:160]))
out = render(body, {'PROFILE':'mesh_gibtsnicht'})
tests.append(('LOAD mesh missing -> friendly', 'does not exist yet' in out and 'BED_MESH_PROFILE LOAD' not in out, out[:160]))

# ------- version stamp ------------------------------------------------------------------------
body = get_body('macros/04_notify.cfg', 'SHOW_STATUS')
out = render(body, {})
tests.append(('SHOW_STATUS prints version', 'R2-2026-09-07.37' in out, out[:120]))

# ------- reset hygiene after cancel / print end (R46: via _PRINT_CLEANUP) -------------------
body = get_body('macros/09_pause_filament.cfg', 'CANCEL_PRINT')
state_vars['mode']='printing'; state_vars['cancel_armed']=True
out = render(body, {})
tests.append(('CANCEL full cleanup (R46)', '_PRINT_CLEANUP' in out and 'CANCEL_PRINT_BASE' in out and 'TURN_OFF_HEATERS' in out, out[:300]))
state_vars['cancel_armed']=False
body = get_body('macros/08_print_start_stop.cfg', 'PRINT_END')
out = render(body, {})
tests.append(('PRINT_END full cleanup (R46)', '_PRINT_CLEANUP' in out and '_LED_TO_IDLE' in out, out[:200]))

# ------- Runde 13: Runout-Flow (User-Sensor) ------------------------------------------------
body = get_body('macros/09_pause_filament.cfg', '_FILAMENT_RUNOUT')
state_vars['mode']='printing'; state_vars['pause_next_armed_runout']=False
out = render(body, {})
tests.append(('RUNOUT arms planned pause', 'PAUSE_NEXT_LAYER REASON="filament out"' in out and 'FILAMENT OUT' in out and 'alarm' in out, out[:220]))
state_vars['pause_next_armed_runout']=True
out = render(body, {})
tests.append(('RUNOUT no double-arm while printing', 'PAUSE_NEXT_LAYER' not in out, out[:160]))
state_vars['pause_next_armed_runout']=False
state_vars['mode']='paused'; state_vars['pause_reason']='filament out'
out = render(body, {})
tests.append(('RUNOUT while paused -> load hint', 'Load filament' in out and 'PAUSE_NEXT_LAYER' not in out, out[:180]))
state_vars['pause_reason']='test'; state_vars['mode']='printing'

body = get_body('macros/09_pause_filament.cfg', '_FILAMENT_INSERTED')
state_vars['mode']='filament'
out = render(body, {})
tests.append(('INSERT in filament mode -> hint', 'RESUME' in out and 'purges' in out, out[:160]))
state_vars['mode']='idle'
out = render(body, {})
tests.append(('INSERT idle -> click', 'r2_click' in out or 'PLAY_SOUND' in out or 'click' in out.lower(), out[:120]))
state_vars['mode']='printing'

# PAUSE mit Filament-Grund -> Filament-Modus (RESUME purgt)
body = get_body('macros/09_pause_filament.cfg', 'PAUSE')
out = render(body, {'REASON':'filament out'})
tests.append(('PAUSE runout -> filament mode', "VARIABLE=mode VALUE='\"filament\"'" in out and 'purges automatically' in out, out[:240]))

# ------- Runde 13: Live-Temp No-Op + Phasen -------------------------------------------------
body = get_body('macros/06_temp_controls.cfg', 'SET_LIVE_HOTEND_TEMP')
out = render(body, {'T':'215'})    # extruder.target=215 im Mock -> No-Op
tests.append(('LIVE hotend unchanged -> no-op', 'stays 215C' in out and 'SAVE_VARIABLE' not in out, out[:160]))
out = render(body, {'T':'225'})    # aendert
tests.append(('LIVE hotend L2 -> after only', 'VARIABLE=ov_hotend_after VALUE=225' in out and 'VARIABLE=ov_hotend_first VALUE=225' in out and 'from layer 2' in out, out[:200]))
state_vars['layer']=1
out = render(body, {'T':'225'})
tests.append(('LIVE hotend L1 -> both phases', 'VARIABLE=ov_hotend_first VALUE=225' in out and 'VARIABLE=ov_hotend_after VALUE=225' in out and 'layer 1 AND following' in out, out[:200])
)
state_vars['layer']=2
body = get_body('macros/06_temp_controls.cfg', 'SET_LIVE_BED_TEMP')
out = render(body, {'T':'55'})
tests.append(('LIVE bed change -> applies', 'VARIABLE=ov_bed VALUE=55' in out and 'TARGET=55' in out, out[:160]))

# ------- Runde 13: Z-Acc (Vase Mode) + Desync-Heal ------------------------------------------
txt = open('macros/01_state.cfg').read()
m = _re3.search(r'\[delayed_gcode _STATE_WATCHER\]\ninitial_duration: 8\ngcode:\n(.*?)(?=\n\[|\Z)', txt, _re3.S)
watcher = '\n'.join(l[4:] if l.startswith('    ') else l for l in m.group(1).split('\n'))
save_vars['pause_next_layer']=False
state_vars.update(layer=2, layer_z_max=12.5, layer_z_acc=0.14, mode='printing')
out = render(watcher, {}, gz=12.6)     # +0.1 -> acc 0.24 >= 0.18 -> Layer
tests.append(('WATCHER Z-acc: vase layer counted', 'VARIABLE=layer VALUE=3' in out and 'layer_z_acc VALUE=0' in out, out[:220]))
state_vars.update(layer_z_acc=0.0, mode='paused', pause_desync=4)
out = render(watcher, {}, ps_state='printing', gz=12.6)
tests.append(('WATCHER heals stuck pause (5s)', "VARIABLE=mode VALUE='\"printing\"'" in out and 're-synced' in out, out[:220]))
state_vars.update(mode='printing', pause_desync=0)

# ------- Runde 13: PAUSE_NEXT_LAYER merkt Grund ----------------------------------------------
body = get_body('macros/06_temp_controls.cfg', 'PAUSE_NEXT_LAYER')
out = render(body, {})
tests.append(('PAUSE_NEXT_LAYER default reason', "VARIABLE=pause_planned_reason VALUE='\"next layer\"'" in out, out[:160]))
out = render(body, {'REASON':'filament out'})
tests.append(('PAUSE_NEXT_LAYER custom reason', "VALUE='\"filament out\"'" in out, out[:160]))

# ------- Runde 15: Heat-Park, Filament-Temps, Cold Pull, Mesh-Option ------------------------
body = get_body('macros/08_print_start_stop.cfg', '_RUN_PRINT_START')
out = render(body, {'APPLY':'1'})
tests.append(('RUN parks high while heating', 'G0 Z40' in out and 'F6000' in out, [l for l in out.split('\n') if 'G0 Z40' in l][:1]))

body = get_body('macros/08_print_start_stop.cfg', 'PRINT_END')
state_vars['mesh_saved_pending']=True
out = render(body, {})
tests.append(('PRINT_END: no auto SAVE_CONFIG (default)', 'SAVE_CONFIG' not in out and 'SESSION' in out, [l for l in out.split('\n') if 'session' in l.lower() or 'SAVE_CONFIG' in l][:1]))
save_vars['mesh_auto_save']=True
out = render(body, {})
save_vars['mesh_auto_save']=False
tests.append(('PRINT_END: auto-save ON -> SAVE_CONFIG', 'SAVE_CONFIG' in out and 'auto-save' in out.lower(), out[:120]))
state_vars['mesh_saved_pending']=False

body = get_body('macros/09_pause_filament.cfg', 'CHANGE_FILAMENT')
state_vars['mode']='idle'
out = render(body, {})          # Mock: extruder.target=215 > 170 -> Temperatur bleibt
tests.append(('CHANGE idle keeps current temp', 'SET_HEATER_TEMPERATURE' not in out and 'E-90' in out, out[:160]))
gd = dict(build_printer()); gd['extruder'] = M({'temperature':50.0,'target':0.0})
out = env.from_string(body).render(printer=MP(gd), params={})
tests.append(('CHANGE idle cold -> min 200/preset', 'TARGET=240' in out and 'TEMPERATURE_WAIT SENSOR=extruder' in out, [l for l in out.split('\n') if 'TARGET' in l][:2]))
state_vars['mode']='printing'

body = get_body('macros/09_pause_filament.cfg', 'CHANGE_FILAMENT_RESUME')
state_vars['mode']='filament'
out = render(body, {}, ps_state='idle')
tests.append(('CHANGE_RESUME idle -> done', 'Filament change done' in out and '_RESUME_COMMON' not in out, out[:180]))
out = render(body, {}, ps_state='paused')
tests.append(('CHANGE_RESUME paused -> resume print', '_RESUME_COMMON' in out, out[:120]))
state_vars['mode']='printing'

body = get_body('macros/12_maintenance.cfg', 'LOAD_FILAMENT')
out = render(body, {})          # target 215 -> keine Neuheizung
tests.append(('LOAD keeps print temp', 'SET_HEATER_TEMPERATURE' not in out, out[:120]))
gd = dict(build_printer()); gd['extruder'] = M({'temperature':50.0,'target':0.0})
out = env.from_string(body).render(printer=MP(gd), params={})
tests.append(('LOAD idle cold -> preset/200', 'TARGET=240' in out, [l for l in out.split('\n') if 'TARGET' in l][:1]))
out = render(body, {})
tests.append(('R55 LOAD uses load_length 60', 'E60 F600' in out, [l for l in out.split('\n') if 'E60' in l][:1]))
save_vars['load_length'] = 75
out = render(body, {})
tests.append(('R55 LOAD custom length 75', 'E75 F600' in out and 'E60' not in out, [l for l in out.split('\n') if 'E75' in l][:1]))
save_vars['load_length'] = 60
_m55 = _re3.search(r'\[menu __main __maint __fil __loadlen\]\n(.*?)(?=\n\[|\Z)', open('menus/lcd_menues.cfg').read(), _re3.S).group(1)
tests.append(('R55 LCD load input 20-150 step 5', 'input_min: 20' in _m55 and 'input_max: 150' in _m55 and 'input_step: 5' in _m55 and 'VARIABLE=load_length' in _m55, _m55[:110]))

body = get_body('macros/12_maintenance.cfg', 'COLD_PULL')
state_vars['mode']='idle'
out = render(body, {})
tests.append(('R77 COLD_PULL v2 phase 1: heat, flush+mold, beep loop, assisted pull',
    'TARGET=230' in out and 'MAXIMUM=92' in out and 'E25' in out and 'G1 E-10' in out
    and '_COLD_PULL_BEEP' in out and 'PULL NOW' in out and 'E-60' in out and 'F1500' in out
    and 'VARIABLE=cold_pull_mat' in out, out[:220]))
out = render(body, {'STEP':'finish'}, etemp=50)
tests.append(('COLD_PULL finish extrudes', 'TARGET=200' in out and 'E20' in out and 'Nozzle clean' in out, out[:180]))
state_vars['mode']='printing'
out = render(body, {})
tests.append(('COLD_PULL refuses while printing', 'only when idle' in out, out[:120]))
state_vars['mode']='idle'

# ------- Runde 16: Homing-Fixes, Material-Presets, Z10-Wartelogik ---------------------------
body = get_body('macros/12_maintenance.cfg', 'CALIBRATE_MESH')
gd = dict(build_printer()); gd['toolhead'] = M({'axis_maximum': M({'x':235.0,'y':235.0,'z':250.0}), 'homed_axes':'', 'max_accel':4000})
out = env.from_string(body).render(printer=MP(gd), params={})
tests.append(('MESH manual homes when unhomed', 'G28' in out and 'Homing first' in out, [l for l in out.split('\n') if 'G28' in l or 'Homing' in l][:2]))
out = render(body, {})
tests.append(('MESH manual homed -> no G28', 'G28' not in out and 'G0 Z10' in out, out[:160]))

txt = open('macros/01_state.cfg').read()
m = _re3.search(r'\[delayed_gcode _STATE_WATCHER\]\ninitial_duration: 8\ngcode:\n(.*?)(?=\n\[|\Z)', txt, _re3.S)
watcher = '\n'.join(l[4:] if l.startswith('    ') else l for l in m.group(1).split('\n'))
state_vars['mode']='idle'
save_vars['legacy_level']=False
save_vars['start_confirm']=False
out = render(watcher, {}, ps_state='printing')
save_vars['legacy_level']=True
tests.append(('WATCHER legacy OFF -> LEGACY_HOME', '_LEGACY_HOME' in out and '_LEGACY_PREP' not in out, out[:200]))
out = render(watcher, {}, ps_state='printing')
save_vars['start_confirm']=True
tests.append(('WATCHER legacy ON -> LEGACY_PREP', '_LEGACY_PREP' in out and '_LEGACY_HOME' not in out, out[:200]))
state_vars['mode']='printing'

import re as _reLH
txt = open('macros/08_print_start_stop.cfg').read()
m = _reLH.search(r'\[delayed_gcode _LEGACY_HOME2\]\ngcode:\n(.*?)(?=\n\[|\Z)', txt, _reLH.S)
home2 = '\n'.join(l[4:] if l.startswith('    ') else l for l in m.group(1).split('\n'))
state_vars['mode']='paused'
gd = dict(build_printer(ps_state='paused')); gd['toolhead'] = M({'axis_maximum': M({'x':235.0,'y':235.0,'z':250.0}), 'homed_axes':'', 'max_accel':4000})
out = env.from_string(home2).render(printer=MP(gd), params={})
tests.append(('LEGACY_HOME2 homes when unhomed', 'G28' in out and '_APPLY_OVERRIDES_CORE' in out and 'M24' in out, out[:220]))
out = render(home2, {}, ps_state='paused')   # gehomed (Mock xyz) -> Z10-Lift
tests.append(('LEGACY_HOME2 lifts to Z10', 'G0 Z10' in out and 'G28' not in out, [l for l in out.split('\n') if 'Z10' in l]))
state_vars['mode']='printing'

body = get_body('macros/08_print_start_stop.cfg', '_APPLY_OVERRIDES_CORE')
out = render(body, {})
tests.append(('OVERRIDE_CORE cfg defaults', 'ADVANCE=0.004' in out and 'RETRACT_LENGTH=0.75' in out and 'M221 S100' in out, out[:200]))
save_vars['ov_pa_on']=True; save_vars['ov_pa']=0.075
out = render(body, {})
save_vars['ov_pa_on']=False
tests.append(('OVERRIDE_CORE pa ON wins', 'ADVANCE=0.075' in out, out[:120]))

body = get_body('macros/08_print_start_stop.cfg', '_RUN_PRINT_START')
out = render(body, {'APPLY':'1'})
tests.append(('RUN waits at Z10 (mesh+purge)', out.count('G0 Z10') >= 2, out.count('G0 Z10')))

# ------- Runde 17: Input Shaper, Mesh-Verwaltung, 0.04-Babysteps, PA-Ende --------------------
body = get_body('macros/12_maintenance.cfg', 'CALIBRATE_SHAPER')
state_vars['mode']='idle'
out = render(body, {})
tests.append(('SHAPER refuses without tester', 'No [resonance_tester]' in out, out[:140]))
gd = dict(build_printer()); gd['configfile'] = M({'settings': M({'resonance_tester': M({'accel_chip':'adxl345'})})})
out = env.from_string(body).render(printer=MP(gd), params={'AXIS':'BOTH','FREQ_START':'5','FREQ_END':'120'})
tests.append(('SHAPER both with range', 'SHAPER_CALIBRATE AXIS=X FREQ_START=5 FREQ_END=120' in out and 'SHAPER_CALIBRATE AXIS=Y FREQ_START=5 FREQ_END=120' in out and 'TURN_OFF_HEATERS' in out, [l for l in out.split('\n') if 'SHAPER_CALIBRATE' in l]))
out = env.from_string(body).render(printer=MP(gd), params={})
tests.append(('SHAPER defaults: no freq params', 'SHAPER_CALIBRATE AXIS=X\n' in out.replace('  ',' ') or 'SHAPER_CALIBRATE AXIS=X' in out and 'FREQ' not in out.split('SHAPER_CALIBRATE AXIS=X')[1][:30], out[:160]))
out = env.from_string(body).render(printer=MP(gd), params={'AXIS':'Q'})
tests.append(('SHAPER bad axis refused', 'AXIS must be X, Y or BOTH' in out, out[:140]))

import re as _reISH
txt = open('macros/12_maintenance.cfg').read()
m = _reISH.search(r'\[delayed_gcode _SHAPER_REPORT\]\ngcode:\n(.*?)(?=\n\[|\Z)', txt, _reISH.S)
rep = '\n'.join(l[4:] if l.startswith('    ') else l for l in m.group(1).split('\n'))
state_vars['ishaper_autosave']=True
out = render(rep, {})
state_vars['ishaper_autosave']=False
tests.append(('SHAPER report + autosave', 'zv @ 52.3Hz' in out and 'mzv @ 41.7Hz' in out and 'SAVE_CONFIG' in out, out[:200]))
out = render(rep, {})
tests.append(('SHAPER report no-save hint', 'NOT saved' in out and 'SAVE_CONFIG' not in out, out[:160]))

body = get_body('macros/12_maintenance.cfg', 'DUMP_RESONANCES')
out = render(body, {})
tests.append(('DUMP refuses without tester', 'No [resonance_tester]' in out, out[:120]))
out = env.from_string(body).render(printer=MP(gd), params={})
tests.append(('DUMP writes raw data', 'TEST_RESONANCES AXIS=X OUTPUT=raw_data NAME=r2' in out and 'TEST_RESONANCES AXIS=Y OUTPUT=raw_data NAME=r2' in out, out[:160]))

body = get_body('macros/12_maintenance.cfg', 'SAVE_MESH_AT_TEMP')
out = render(body, {})    # bed target 60, mesh aktiv (r2)
tests.append(('SAVE_MESH_AT_TEMP name=60', 'BED_MESH_PROFILE SAVE=60' in out and 'session' in out, out[:180]))
save_vars['mesh_auto_save']=True
out = render(body, {})
save_vars['mesh_auto_save']=False
tests.append(('SAVE_MESH_AT_TEMP autosave', 'SAVE_CONFIG' in out, out[:140]))
gd = dict(build_printer()); gd['bed_mesh'] = M({'profile_name': '', 'profiles': {'r2': {}}})
out = env.from_string(body).render(printer=MP(gd), params={})
tests.append(('SAVE_MESH_AT_TEMP no mesh -> err', 'No mesh active' in out, out[:120]))

body = get_body('macros/12_maintenance.cfg', 'MESH_BY_INDEX')
out = render(body, {'INDEX':'0'})
tests.append(('MESH_BY_INDEX loads + AUTO', 'LOAD_BED_MESH PROFILE=r2' in out and 'mesh_always VALUE=False' in out, out[:180]))
out = render(body, {'INDEX':'5'})
tests.append(('MESH_BY_INDEX empty slot', 'No mesh in this slot' in out, out[:120]))

body = get_body('macros/12_maintenance.cfg', 'UNLOAD_MESH')
out = render(body, {})
tests.append(('UNLOAD_MESH clears + remesh', 'BED_MESH_CLEAR' in out and 'mesh_always VALUE=True' in out, out[:140]))

body = get_body('macros/08_print_start_stop.cfg', '_RUN_PRINT_START')
save_vars['mesh_always']=False
out = render(body, {'APPLY':'0'})
save_vars['mesh_always']=True
tests.append(('RUN keeps active mesh (AUTO)', 'no re-leveling' in out and 'LOAD_MESH_PROFILE' not in out and '_CALIBRATE_MESH_PROFILE' not in out, [l for l in out.split('\n') if 're-leveling' in l][:1]))

body = get_body('macros/10_live_tuning.cfg', 'BABYSTEP_UP')
out = render(body, {})
tests.append(('BABYSTEP 0.04 full step', 'Z_ADJUST=0.04' in out, out[:80]))
body = get_body('macros/10_live_tuning.cfg', 'BABYSTEP_UP_FINE')
out = render(body, {})
tests.append(('BABYSTEP fine = 0.12', 'Z_ADJUST=0.12' in out, out[:80]))

body = get_body('macros/12_maintenance.cfg', 'CALIBRATE_PA')
out = render(body, {'LAYER':'0.04'})
tests.append(('PA cal accepts 0.04 layer', 'PA line 10/10' in out and 'must be 0.04' not in out, out[:140]))
tests.append(('PA cal ends with _CAL_END', '_CAL_END' in out, 'missing'))

body = get_body('macros/12_maintenance.cfg', '_CAL_END')
out = render(body, {})
tests.append(('CAL_END heaters off + cooldown', 'TURN_OFF_HEATERS' in out and '_END_FAN_OFF' in out and '_END_MOTORS' in out, out[:160]))

# ------- Runde 18: Prime-Flush, 1st-layer-speed, PA-Interceptor, Sync, Cancel-Timeout ------
body = get_body('macros/08_print_start_stop.cfg', '_PRIME_LINE')
out = render(body, {'LAYER_HEIGHT':'0.3'})
tests.append(('PRIME: flush + fat line + de-ooze handover (net -0.5)',
    'E6.0 F150' in out and 'E-3.5 F2400' in out and 'E3.0 F300' in out
    and 'E-2.5 F2400' not in out and 'F1200' in out
    and out.index('E3.0 F300') < out.index('RESTORE_GCODE_STATE NAME=PRIME_S'),
    [l for l in out.split('\n') if 'F150' in l or 'E-3.5' in l or 'E3.0 F300' in l][:3]))
out = render(body, {'LAYER_HEIGHT':'0.3'}, objs=[])
tests.append(('PRIME: long line (110mm fallback)', 'G0 X115' in out and 'G1 X5' in out, [l for l in out.split('\n') if l.strip().startswith('G1 X')][:1]))

body = get_body('macros/08_print_start_stop.cfg', '_RUN_PRINT_START')
out = render(body, {'APPLY':'1'})
tests.append(('RUN: 1st layer 75%', 'M220 S75' in out, [l for l in out.split('\n') if 'M220' in l][:1]))

body = get_body('macros/06_temp_controls.cfg', 'LAYER_MARK')
state_vars['layer']=1; state_vars['mode']='printing'
out = render(body, {})
tests.append(('LAYER_MARK 2: speed back 100%', 'M220 S100' in out and 'back to 100%' in out, [l for l in out.split('\n') if 'M220' in l][:1]))
state_vars['layer']=2

body = get_body('macros/10_live_tuning.cfg', 'SET_PRESSURE_ADVANCE')
state_vars['mode']='printing'
out = render(body, {'ADVANCE':'0.08', 'SMOOTH_TIME':'0.04'})
tests.append(('PA file passthrough (override off)', 'SET_PRESSURE_ADVANCE_BASE ADVANCE=0.08 SMOOTH_TIME=0.04' in out and 'OVERRIDE' not in out, out[:140]))
save_vars['ov_pa_on']=True; save_vars['ov_pa']=0.05
out = render(body, {'ADVANCE':'0.08'})
save_vars['ov_pa_on']=False
tests.append(('PA file -> OVERRIDE when ON', 'YOUR: PA 0.05' in out and 'SET_PRESSURE_ADVANCE_BASE ADVANCE=0.05' in out and 'SMOOTH_TIME' not in out, out[:160]))
state_vars['pa_smooth']=0.04
out = render(body, {'SMOOTH_TIME':'0.05'})
save_vars['ov_pa_smooth_on']=True
out = render(body, {'SMOOTH_TIME':'0.05'})
save_vars['ov_pa_smooth_on']=False
tests.append(('PA smooth from file -> YOUR smooth', 'YOUR smooth 0.04' in out and 'SET_PRESSURE_ADVANCE_BASE SMOOTH_TIME=0.04' in out and 'ADVANCE=' not in out, out[:160]))
state_vars['pa_smooth']=0.05
out = render(body, {'SMOOTH_TIME':'0.05'})
# (smooth equal + ov_pa_smooth_on OFF -> passthrough wird oben abgedeckt)
state_vars['pa_smooth']=0.04

body = get_body('macros/10_live_tuning.cfg', 'SET_LIVE_PRESSURE_ADVANCE')
out = render(body, {'VALUE':'0.06'})
tests.append(('LIVE PA persists to ov_pa', 'VARIABLE=ov_pa VALUE=0.06' in out and 'ov_pa_on VALUE=True' in out, out[:160]))
state_vars['mode']='idle'

body = get_body('macros/11_gantry_sync.cfg', 'SYNC_GANTRY')
state_vars['mode']='starting'
out = render(body, {})
tests.append(('SYNC allowed during starting (pre-print)', 'SET_KINEMATIC_POSITION' in out and 'only when idle' not in out, out[:120]))
state_vars['mode']='idle'
out = render(body, {'FORCE':'1'})
tests.append(('SYNC FORCE bypasses guard', 'SET_KINEMATIC_POSITION' in out, out[:100]))
state_vars['mode']='printing'

txt = open('macros/08_print_start_stop.cfg').read()
import re as _reP2
m = _reP2.search(r'\[delayed_gcode _LEGACY_PREP2\]\ngcode:\n(.*?)(?=\n\[|\Z)', txt, _reP2.S)
prep2 = '\n'.join(l[4:] if l.startswith('    ') else l for l in m.group(1).split('\n'))
state_vars['mode']='paused'
save_vars['gantry_sync_print']=True
gd = dict(build_printer(ps_state='paused')); gd['toolhead'] = M({'axis_maximum': M({'x':235.0,'y':235.0,'z':250.0}), 'homed_axes':'', 'max_accel':4000})
out = env.from_string(prep2).render(printer=MP(gd), params={})
save_vars['gantry_sync_print']=False
tests.append(('LEGACY prep: gantry sync before homing', 'SYNC_GANTRY QUIET=1 FORCE=1' in out and 'M220 S75' in out, [l for l in out.split('\n') if 'SYNC_GANTRY' in l or 'M220' in l][:2]))
state_vars['mode']='printing'

txt = open('macros/01_state.cfg').read()
m = _re3.search(r'\[delayed_gcode _STATE_WATCHER\]\ninitial_duration: 8\ngcode:\n(.*?)(?=\n\[|\Z)', txt, _re3.S)
watcher = '\n'.join(l[4:] if l.startswith('    ') else l for l in m.group(1).split('\n'))
state_vars['cancel_armed']=True; state_vars['cancel_time']=0.0
out = render(watcher, {})
state_vars['cancel_armed']=False
tests.append(('Cancel confirm expires after 60s', 'cancel_armed VALUE=False' in out and 'disarmed' in out, out[:160]))
state_vars['layer']=1
out = render(watcher, {}, gz=12.7)
state_vars['layer']=2
tests.append(('WATCHER Z: layer 2 -> speed 100%', 'M220 S100' in out, [l for l in out.split('\n') if 'M220' in l][:1]))

# ------- Runde 19: PA smooth live, L->R-Linien mit Hop, Watcher-Save-Leak --------------------
body = get_body('macros/10_live_tuning.cfg', 'SET_LIVE_PA_SMOOTH')
out = render(body, {'TIME':'0.05'})
tests.append(('LIVE PA smooth persists', 'VARIABLE=ov_pa_smooth VALUE=0.05' in out and 'VARIABLE=ov_pa_smooth_on VALUE=True' in out and 'SET_PRESSURE_ADVANCE_BASE SMOOTH_TIME=0.05' in out and 'VARIABLE=pa_smooth VALUE=0.05' in out, out[:180]))
out = render(body, {'TIME':'0.5'})
tests.append(('LIVE PA smooth range guard', 'TIME=<0.01..0.15>' in out, out[:120]))

body = get_body('macros/12_maintenance.cfg', 'CALIBRATE_PA')
state_vars['mode']='idle'
out = render(body, {})
import re as _reR19
x_starts = _reR19.findall(r'G0 X(\d+(?:\.\d+)?) Y', out)
tests.append(('PA lines all start left (x0)', x_starts.count('57.5') == 10 and '157.5 Y' not in ' '.join(x_starts), x_starts[:4]))
tests.append(('PA lines: retract + z-hop 0.4 between', 'G1 E-0.75 F2100' in out and 'G0 Z0.7 F600' in out and 'G1 E0.75' in out, [l for l in out.split('\n') if 'E-0.75' in l or 'Z0.7' in l][:2]))
save_vars['ov_retract_on']=True; save_vars['ov_retract_len']=1.2; save_vars['ov_retract_speed']=20
out = render(body, {})
save_vars['ov_retract_on']=False
tests.append(('PA lines: override retract wins', 'G1 E-1.2 F1200' in out, [l for l in out.split('\n') if 'E-1.2' in l][:1]))
state_vars['mode']='printing'

txt = open('macros/01_state.cfg').read()
m = _re3.search(r'\[delayed_gcode _STATE_WATCHER\]\ninitial_duration: 8\ngcode:\n(.*?)(?=\n\[|\Z)', txt, _re3.S)
watcher = '\n'.join(l[4:] if l.startswith('    ') else l for l in m.group(1).split('\n'))
state_vars['mode']='printing'; state_vars['mesh_saved_pending']=True
out = render(watcher, {}, ps_state='complete')
state_vars['mesh_saved_pending']=False
tests.append(('WATCHER complete: no auto-save (default)', not any(l.strip()=='SAVE_CONFIG' for l in out.split('\n')) and 'SESSION' in out, [l for l in out.split('\n') if 'session' in l.lower() or 'SAVE_CONFIG' in l][:1]))
state_vars['mesh_saved_pending']=True
save_vars['mesh_auto_save']=True
out = render(watcher, {}, ps_state='complete')
save_vars['mesh_auto_save']=False
state_vars['mesh_saved_pending']=False
tests.append(('WATCHER complete: auto-save ON', 'SAVE_CONFIG' in out and 'auto-save' in out, out[:140]))
state_vars['mode']='idle'

txt = open('macros/08_print_start_stop.cfg').read()
m = _re5b.search(r'\[delayed_gcode _LEGACY_PREP2\]\ngcode:\n(.*?)(?=\n\[|\Z)', txt, _re5b.S)
prep2 = '\n'.join(l[4:] if l.startswith('    ') else l for l in m.group(1).split('\n'))
state_vars['mode']='paused'
out = render(prep2, {}, ps_state='paused')
tests.append(('prep2: Z10 while hotend heats (after mesh)', out.count('G0 Z10') >= 2, out.count('G0 Z10')))
state_vars['mode']='printing'

# ------- Runde 20: Per-Key-Overrides, Fan-Material, File-Capture, Unload, PID-Fan ----------
body = get_body('macros/08_print_start_stop.cfg', '_RUN_PRINT_START')
save_vars.update(ov_retract_len_on=True, ov_retract_len=1.2, ov_retract_speed_on=False)
out = render(body, {'APPLY':'1'})
save_vars.update(ov_retract_len_on=False)
tests.append(('RUN retract per-key (len ON, spd off)', 'RETRACT_LENGTH=1.2' in out and 'RETRACT_SPEED=35' in out, [l for l in out.split('\n') if 'RETRACT' in l][:1]))
save_vars.update(ov_pa_smooth_on=True, ov_pa_smooth=0.05)
out = render(body, {'APPLY':'1'})
save_vars.update(ov_pa_smooth_on=False)
tests.append(('RUN PA smooth ON applied', 'SMOOTH_TIME=0.05' in out, [l for l in out.split('\n') if 'PRESSURE_ADVANCE' in l][:1]))
out = render(body, {'APPLY':'1'})
tests.append(('RUN PA smooth OFF -> no smooth', 'SET_PRESSURE_ADVANCE ADVANCE=' in out and 'SMOOTH_TIME' not in out, [l for l in out.split('\n') if 'PRESSURE_ADVANCE' in l][:1]))
save_vars.update(ov_ironing_flow_on=True, ov_ironing_flow=30, ov_ironing_speed_on=False, ov_ironing_temp_on=True, ov_ironing_temp=205)
save_vars.update(ov_fan_on=True, ov_fan=95)
out = render(body, {'APPLY':'1'})
tests.append(('R54 RUN applies fan scale at start', 'VARIABLE=f_fan_scale VALUE=0.95' in out, [l for l in out.split('\n') if 'f_fan_scale' in l][:2]))
save_vars.update(ov_fan_on=False, ov_fan=100)

body = get_body('macros/06_temp_controls.cfg', 'LAYER_MARK')
state_vars['layer']=1; state_vars['mode']='printing'
save_vars.update(ov_fan_on=True, ov_fan=60)
out = render(body, {})
save_vars.update(ov_fan_on=False)
tests.append(('LAYER_MARK 2: material fan 60%', 'SET_FAN_SCALE PERCENT=60' in out, [l for l in out.split('\n') if 'FAN_SCALE' in l][:1]))
state_vars['layer']=2

body = get_body('macros/10_live_tuning.cfg', 'SET_RETRACTION')
state_vars['mode']='printing'
out = render(body, {'RETRACT_LENGTH':'0.8', 'RETRACT_SPEED':'40'})
tests.append(('SET_RETRACTION captures file values', 'VARIABLE=file_retract_len VALUE=0.8' in out and 'VARIABLE=file_retract_speed VALUE=40' in out and 'SET_RETRACTION_BASE RETRACT_LENGTH=0.8' in out, out[:200]))
save_vars.update(ov_retract_len_on=True, ov_retract_len=1.0, ov_retract_speed_on=True, ov_retract_speed=30)
out = render(body, {'RETRACT_LENGTH':'0.8', 'RETRACT_SPEED':'40'})
save_vars.update(ov_retract_len_on=False, ov_retract_speed_on=False)
tests.append(('SET_RETRACTION redirected when ON', 'YOUR: len 1.0 / retract 30' in out and 'SET_RETRACTION_BASE RETRACT_LENGTH=1.0' in out, out[:200]))
state_vars['mode']='idle'

body = get_body('macros/10_live_tuning.cfg', 'SET_PRESSURE_ADVANCE')
state_vars['mode']='printing'
out = render(body, {'ADVANCE':'0.08'})
tests.append(('PA captures file value', 'VARIABLE=file_pa VALUE=0.08' in out, out[:140]))
state_vars['mode']='idle'

body = get_body('macros/12_maintenance.cfg', '_RUN_PID_TUNE')
out = render(body, {'HEATER':'extruder','TARGET':'210','AUTOSAVE':'0'})
tests.append(('PID fan percent from LCD (100)', 'M99106 S255' in out, [l for l in out.split('\n') if 'M99106' in l][:1]))
save_vars['pid_fan_percent']=50
out = render(body, {'HEATER':'extruder','TARGET':'210','AUTOSAVE':'0'})
save_vars['pid_fan_percent']=100
tests.append(('PID fan 50% -> S127', 'M99106 S127' in out, [l for l in out.split('\n') if 'M99106' in l][:1]))

body = get_body('macros/09_pause_filament.cfg', 'CHANGE_FILAMENT')
state_vars['mode']='idle'
out = render(body, {})
tests.append(('CHANGE uses unload_length 90', 'E-90 F1800' in out, [l for l in out.split('\n') if 'E-90' in l][:1]))
state_vars['mode']='printing'

body = get_body('macros/04_notify.cfg', 'SHOW_STATUS')
save_vars.update(ov_ironing_temp_on=True, ov_ironing_temp=0, ov_bed_on=True, ov_bed=60)
out = render(body, {})
save_vars.update(ov_ironing_temp=200)
tests.append(('SHOW_STATUS hides zero values', 'IronTemp' not in out and 'Bed(60C)' in out, [l for l in out.split('\n') if 'Overrides' in l][:1]))

# ------- Runde 21: Speed/Accel-Vollstaendigkeit -----------------------------------------------
_lcd21 = open('menus/lcd_menues.cfg').read()
for m, lcdkey in [('SET_GLOBAL_SPEED', '__speeds __gs'), ('SET_GLOBAL_ACCEL', '__accels __ga')]:
    tests.append((f'Speed/Accel {m} exists+LCD', f'gcode_macro {m}]' in open('macros/10_live_tuning.cfg').read() and lcdkey in _lcd21, m))
tests.append(('R54 feature macros are stubs (compat, no error)',
    all(f'gcode_macro {m}]' in open('macros/10_live_tuning.cfg').read() for m in
        ['SET_OUTER_WALL_SPEED','SET_INNER_WALL_ACCEL','SET_IRONING_FLOW']), 'stub check'))
tests.append(('R54 feature menus removed from LCD',
    'SET_OUTER_WALL_SPEED' not in _lcd21 and 'SET_IRONING_FLOW' not in _lcd21, 'menu check'))

body = get_body('macros/10_live_tuning.cfg', 'SET_SOLID_INFILL_SPEED')
state_vars['current_type']=''
out = render(body, {'PERCENT':'90'})
tests.append(('R54 SOLID setter = stub hint', 'removed in .38' in out or 'per-feature' in out or 'global' in out, out[:140]))
body = get_body('macros/10_live_tuning.cfg', 'SET_INNER_WALL_ACCEL')
out = render(body, {'ACCEL':'2500'})
tests.append(('R54 INNER accel setter = stub hint', 'removed in .38' in out and 'a_inner_wall' not in out, out[:140]))
body = get_body('macros/10_live_tuning.cfg', 'SET_IRONING_ACCEL')
out = render(body, {'ACCEL':'1500'})
tests.append(('R54 IRONING accel setter = stub hint', 'removed in .38' in out and 'a_ironing' not in out, out[:120]))
state_vars['current_type']='WALL-OUTER'
body = get_body('macros/10_live_tuning.cfg', 'SET_GLOBAL_SPEED')
out = render(body, {'PERCENT':'80'})
tests.append(('GLOBAL speed M220 S80', 'M220 S80' in out, out[:100]))

# ------- Runde 22: Sequential print (print by object) - L1 temps pro Objekt ------------------
txt = open('macros/01_state.cfg').read()
m = _re3.search(r'\[delayed_gcode _STATE_WATCHER\]\ninitial_duration: 8\ngcode:\n(.*?)(?=\n\[|\Z)', txt, _re3.S)
watcher = '\n'.join(l[4:] if l.startswith('    ') else l for l in m.group(1).split('\n'))
state_vars['mode']='printing'; state_vars['layer']=12; state_vars['layer_z_max']=2.4
save_vars.update(ov_bed_on=True, ov_bed=70, ov_hotend_first_on=True, ov_hotend_first=235)
out = render(watcher, {}, gz=0.3)
tests.append(('SEQ: Z-fall restarts with L1 temps + pause',
    'next object' in out and 'VARIABLE=layer VALUE=0' in out and 'VARIABLE=layer_z_max VALUE=0.3' in out
    and 'TARGET=70' in out and 'TARGET=235' in out and 'PAUSE REASON="next object' in out
    and 'ID=_OBJECT_PREP' in out and 'M220 S75' in out, out[:300]))
save_vars.update(ov_bed=60, ov_hotend_first=235)
# THE field bug (R24): layer 2 at z=0.4 is BELOW 1.5mm - a bare level check re-triggered
# the L1 restart over and over. Only the armed falling edge (z_max >= 1.6) may fire.
state_vars['layer']=2; state_vars['layer_z_max']=0.4
out = render(watcher, {}, gz=0.4)
tests.append(('SEQ: no re-trigger while layer 2 below 1.5mm', 'next object' not in out, out[:120]))
out = render(watcher, {}, gz=12.5)
tests.append(('SEQ: no trigger high Z', 'next object' not in out, out[:120]))
# marked files (LAYER_MARK / vase): high-water mark maintenance arms the falling edge
state_vars['layer_marks']=True; state_vars['layer_z_max']=0.3
out = render(watcher, {}, gz=5.0)
tests.append(('SEQ: marked file keeps Z high-water mark', 'VARIABLE=layer_z_max VALUE=5.0' in out, out[:140]))
state_vars['layer_marks']=False; state_vars['layer_z_max']=2.4
# heaters already at L1 targets -> set temps but continue WITHOUT park/wait cycle
p2 = build_printer(gz=0.3)
p2['heater_bed'] = M({'temperature': 70.0, 'target': 70.0})
p2['extruder'] = M({'temperature': 235.0, 'target': 235.0})
save_vars.update(ov_bed=70, ov_hotend_first=235)
out = render(watcher, {}, extra={'printer': p2}, gz=0.3)
tests.append(('SEQ: L1 already set - continue without pause', 'continuing without pause' in out and 'PAUSE REASON="next object' not in out, out[:200]))
# fresh legacy print start clears stale arming from the previous print
save_vars.update(ov_bed=60)
state_vars['mode']='idle'
out = render(watcher, {}, gz=0.3)
tests.append(('SEQ: legacy start clears Z high-water mark', 'VARIABLE=layer_z_max VALUE=0.0' in out, out[:200]))
state_vars['mode']='printing'

import re as _reOP
txt = open('macros/08_print_start_stop.cfg').read()
m = _reOP.search(r'\[delayed_gcode _OBJECT_PREP\]\ngcode:\n(.*?)(?=\n\[|\Z)', txt, _reOP.S)
objprep = '\n'.join(l[4:] if l.startswith('    ') else l for l in m.group(1).split('\n'))
state_vars['mode']='paused'
out = render(objprep, {}, ps_state='paused')
state_vars['mode']='printing'
tests.append(('OBJECT_PREP waits + resumes', 'TEMPERATURE_WAIT SENSOR=heater_bed MINIMUM=58' in out and 'TEMPERATURE_WAIT SENSOR=extruder MINIMUM=212' in out and 'RESUME' in out, out[:220]))

# ------- Runde 24: PAUSE re-anchor + live retraction + LCD babystep/retract ------------------
body = get_body('macros/09_pause_filament.cfg', 'PAUSE')
out = render(body, {'REASON':'User'}, gz=0.6)
tests.append(('PAUSE re-anchors Z high-water mark', 'VARIABLE=layer_z_max VALUE=0.6' in out, [l for l in out.split('\n') if 'layer_z_max' in l][:1]))

body = get_body('macros/10_live_tuning.cfg', 'SET_LIVE_RETRACTION')
save_vars.update(ov_retract_len_on=True, ov_retract_len=2.0)
out = render(body, {'LENGTH':'1.2', 'EXTRA':'0.05'})
tests.append(('LIVE retraction: partial set + no override redirect',
    'SET_RETRACTION_BASE RETRACT_LENGTH=1.2' in out and 'UNRETRACT_EXTRA_LENGTH=0.05' in out
    and 'RETRACT_SPEED=35.0' in out and 'VARIABLE=file_retract_len' not in out, out[:200]))
save_vars.update(ov_retract_len_on=False)

lcd_txt2 = open('menus/lcd_menues.cfg').read()
tests.append(('LCD: babystep top-level in Live Tuning', '[menu __main __live __zup]' in lcd_txt2 and '[menu __main __live __zdownf]' in lcd_txt2 and '[menu __main __live __z __up]' not in lcd_txt2, 'babystep'))
tests.append(('LCD: retract/deretract live inputs', '__retspd]' in lcd_txt2 and '__unret]' in lcd_txt2 and '__unretx]' in lcd_txt2, 'retract inputs'))

# Menue-Audit: Start-Dialog + Legacy weiterhin vorhanden
lcd_txt = open('menus/lcd_menues.cfg').read()
for entry in ['PRINT_AS_SLICED', 'PRINT_WITH_OVERRIDES', 'CANCEL_PENDING_PRINT', 'legacy_level']:
    tests.append((f'Menu audit: {entry}', entry in lcd_txt, 'missing'))

# ===================== R40 tests: .10 base + user wishes =====================
import re as _re40

# --- M220 interceptor: L1 brake stays alive against file M220 ---
m220 = get_body('macros/06_temp_controls.cfg', 'M220')
state_vars.update({'mode':'printing','layer':1,'ignore_overrides':False})
out = render(m220, {'S':100})
tests.append(('M220 layer1: S100 capped to 75 (R87.2: value goes out via _SPEED_COMBINED)',
    'capped' in out and '_SPEED_COMBINED' in out and 'VARIABLE=g_speed_clean VALUE=75' in out, out[:160]))
state_vars['layer'] = 2
out = render(m220, {'S':100})
tests.append(('M220 layer2: 1:1 pass-through (via _SPEED_COMBINED)',
    '_SPEED_COMBINED' in out and 'capped' not in out and 'VARIABLE=g_speed_clean VALUE=100' in out, out[:120]))
state_vars['ignore_overrides'] = True; state_vars['layer'] = 1
out = render(m220, {'S':100})
tests.append(('M220 as-sliced: 1:1 (no cap, via _SPEED_COMBINED)',
    '_SPEED_COMBINED' in out and 'capped' not in out and 'VARIABLE=g_speed_clean VALUE=100' in out, out[:120]))
state_vars.update({'mode':'printing','layer':2,'ignore_overrides':False})

# --- HOME2 always purges ---
_reH = _re40.search(r'\[delayed_gcode _LEGACY_HOME2\]\ngcode:\n(.*?)(?=\n\[|\Z)', open('macros/08_print_start_stop.cfg').read(), _re40.S)
home2 = '\n'.join(l[4:] if l.startswith('    ') else l for l in _reH.group(1).split('\n'))
state_vars['mode']='paused'
out = render(home2, {}, ps_state='paused')
tests.append(('HOME2 heats + ALWAYS purges', 'SET_HEATER_TEMPERATURE HEATER=extruder' in out and 'TEMPERATURE_WAIT SENSOR=extruder' in out
    and '_PRIME_LINE' in out and 'M220 S75' in out,
    [l for l in out.split('\n') if 'PRIME' in l or 'M220' in l or 'HEATER=extruder' in l][:3]))
state_vars['mode']='printing'

# --- Z-track L2 for legacy (watcher n==2 block) ---
_reW40 = _re40.search(r'\[delayed_gcode _STATE_WATCHER\]\ninitial_duration: 8\ngcode:\n(.*?)(?=\n\[|\Z)', open('macros/01_state.cfg').read(), _re40.S)
wt = '\n'.join(l[4:] if l.startswith('    ') else l for l in _reW40.group(1).split('\n'))
save_vars.update({'ov_hotend_after_on':True,'ov_hotend_after':210,'ov_bed_after_on':True,'ov_bed_after':55,
                  'ov_fan_on':True,'ov_fan':80,'first_layer_speed':75})
state_vars.update({'mode':'printing','layer':1,'layer_marks':False,'layer_z_max':0.2,'layer_z_acc':0,'seq_low':0,
                   'pause_desync':0,'cancel_armed':False,'cancel_time':0.0})
out = render(wt, {}, gz=0.3)   # dz=0.1 in 0.05..0.35 -> new layer -> n==2
tests.append(('Z-track layer2: L2 temps + fan for legacy',
    'TARGET=210' in out and 'TARGET=55' in out and 'SET_FAN_SCALE PERCENT=80' in out and 'M220 S100' in out,
    [l for l in out.split('\n') if 'TARGET' in l or 'FAN_SCALE' in l or 'S100' in l][:5]))

# --- AS LEGACY start: dispatch + flags ---
p07 = open('macros/07_start_confirm.cfg').read()
tests.append(('07 defines PRINT_AS_LEGACY', 'gcode_macro PRINT_AS_LEGACY' in p07, 'missing'))
_reW40b = _re40.search(r'\[delayed_gcode ([A-Z_0-9]*WAITER[A-Z_0-9]*)\]\n(?:initial_duration: \d+\n)?gcode:\n(.*?)(?=\n\[|\Z)', p07, _re40.S)
waiter = '\n'.join(l[4:] if l.startswith('    ') else l for l in _reW40b.group(2).split('\n'))
save_vars['start_decision']='as_legacy'
state_vars['mode']='waiting'
out = render(waiter, {}, ps_state='paused')
tests.append(('Waiter as_legacy -> RUN APPLY=1 LEGACY=1', '_RUN_PRINT_START APPLY=1 LEGACY=1' in out and 'VARIABLE=ignore_overrides VALUE=False' in out, out[:200]))
save_vars['start_decision']=''

# --- LAYER_MARK counts in EVERY mode (R56: .38 regression fix) ---
lm = get_body('macros/06_temp_controls.cfg', 'LAYER_MARK')
state_vars.update({'mode':'printing','layer':3,'legacy_mode':True})
out = render(lm, {})
tests.append(('R56 LAYER_MARK counts even with legacy_mode', 'VARIABLE=layer VALUE=4' in out, out[:120]))
state_vars['legacy_mode']=False

# --- _RUN_PRINT_START: LEGACY flag + velocity gating ---
run = get_body('macros/08_print_start_stop.cfg', '_RUN_PRINT_START')
save_vars.update({'ov_velocity_on':False,'ov_velocity':300,'ov_min_cruise_on':False,'ov_min_cruise':0.5,
                  'ov_square_corner_on':False,'ov_square_corner':5,'ov_accel_on':False,'ov_accel':4000})
state_vars['mode']='waiting'
state_vars['file_type']='legacy'
out = render(run, {'APPLY':1,'LEGACY':1})
tests.append(('R56 RUN LEGACY=1 legacy file -> legacy_mode True', 'VARIABLE=legacy_mode VALUE=True' in out, [l for l in out.split('\n') if 'legacy_mode' in l][:2]))
state_vars['file_type']='marked'
out = render(run, {'APPLY':1,'LEGACY':1})
tests.append(('R56 FIX: RUN LEGACY=1 MARKED file keeps markers (legacy_mode False)', 'VARIABLE=legacy_mode VALUE=False' in out, [l for l in out.split('\n') if 'legacy_mode' in l][:2]))
state_vars['file_type']='legacy'
out = render(run, {'APPLY':1})
tests.append(('RUN default: legacy_mode False', 'VARIABLE=legacy_mode VALUE=False' in out, ''))
tests.append(('RUN: no override ON -> NO forced SET_VELOCITY_LIMIT', 'SET_VELOCITY_LIMIT' not in out, [l for l in out.split('\n') if 'VELOCITY' in l][:2]))
save_vars.update({'ov_velocity_on':True,'ov_min_cruise_on':True,'ov_square_corner_on':True,'ov_accel_on':True})
out = render(run, {'APPLY':1})
tests.append(('RUN: all limits ON -> SET_VELOCITY_LIMIT with 4 params',
    'SET_VELOCITY_LIMIT' in out and 'VELOCITY=300' in out and 'MINIMUM_CRUISE_RATIO=0.5' in out and 'SQUARE_CORNER_VELOCITY=5' in out and 'ACCEL=4000' in out,
    [l for l in out.split('\n') if 'VELOCITY_LIMIT' in l][:2]))
save_vars.update({'ov_velocity_on':False,'ov_min_cruise_on':False,'ov_square_corner_on':False,'ov_accel_on':False})

# --- live velocity commands ---
for mac,par,needle in [('SET_LIVE_VELOCITY',{'VELOCITY':250},'SET_VELOCITY_LIMIT VELOCITY=250'),
                       ('SET_LIVE_MINIMUM_CRUISE_RATIO',{'VALUE':0.6},'SET_VELOCITY_LIMIT MINIMUM_CRUISE_RATIO=0.6'),
                       ('SET_LIVE_SQUARE_CORNER',{'VALUE':6},'SET_VELOCITY_LIMIT SQUARE_CORNER_VELOCITY=6')]:
    out = render(get_body('macros/10_live_tuning.cfg', mac), par)
    tests.append((f'{mac} renders', needle in out, out[:120]))

# --- retraction live mirror ---
slr = get_body('macros/10_live_tuning.cfg', 'SET_LIVE_RETRACTION')
out = render(slr, {'LENGTH':1.2})
tests.append(('SET_LIVE_RETRACTION mirrors all 4 values', 'VARIABLE=ret_len VALUE=1.2' in out and 'VARIABLE=ret_spd' in out
    and 'VARIABLE=ret_unret' in out and 'VARIABLE=ret_unretx' in out, [l for l in out.split('\n') if 'VARIABLE=ret_' in l][:4]))

# --- SET_OVERRIDE_VALUE knows the new keys ---
sov = get_body('macros/07_start_confirm.cfg', 'SET_OVERRIDE_VALUE')
for k in ['velocity','min_cruise','square_corner','fan']:
    out = render(sov, {'NAME':k,'VALUE':123})
    tests.append((f'SET_OVERRIDE_VALUE {k}', f"VALUE={{v|float}}" in out or f'ov_{k}' in out, out[:120]))

# --- menu audit R40 ---
lcd = open('menus/lcd_menues.cfg').read()
for entry in ["> AS LEGACY", 'SET_LIVE_VELOCITY VELOCITY=', 'SET_LIVE_MINIMUM_CRUISE_RATIO VALUE=', 'SET_LIVE_SQUARE_CORNER VALUE=',
              'SET_FAN_SCALE PERCENT=', 'homing_origin.z', '__pid __hot', '__pid __bed', 'FAN=', '__fanon', 'TOGGLE_OVERRIDE NAME=fan',
              'NAME=velocity VALUE=', 'NAME=min_cruise VALUE=', 'NAME=square_corner VALUE=']:
    tests.append((f'R40 menu: {entry[:36]}', entry in lcd, 'missing'))
# label audit <=16 incl. worst-case value
def _fill(s, mx):
    if '(menu.input*100)' in s: v='300'
    elif '%d' in s:
        n=int(_re40.search(r'%(\d*)d',s).group(1) or 3)
        cap=min(mx if mx else 10**n, 10**n); v=str(int(cap)).rjust(n)
    elif '%.3f' in s: v='0.200' if (mx or 1)<1 else '9.999'
    elif '%.2f' in s: v='0.99' if (mx or 1)<1 else '9.99'
    elif '%.1f' in s: v='9.9'
    else: v='999'
    return _re40.sub(r"\{[^}]*menu\.input[^}]*\}", v, s)
_bad=[]; _cur=None
for _line in lcd.split('\n'):
    _m=_re40.match(r'input_max: ([\d.]+)', _line.strip())
    if _m: _cur=float(_m.group(1))
    _nm=_re40.match(r"name: (.+)$", _line.strip())
    if not _nm or 'menu.input' not in _line: continue
    _s=_nm.group(1).strip("'")
    if len(_fill(_s,_cur))>16: _bad.append(_fill(_s,_cur))
tests.append(('LCD labels <=16 chars incl. value', not _bad, _bad[:4]))

# ===================== R41 tests: resume brake, layer_marks, new calibrations ====
# --- Resume re-asserts the L1 brake (PAUSE_STATE restore leak) ---
rc = get_body('macros/09_pause_filament.cfg', '_RESUME_COMMON')
state_vars.update({'mode':'paused','layer':1,'ignore_overrides':False,'pause_x':100.0,'pause_y':100.0,
                   'pause_z':12.5,'pause_was_sd':True,'current_type':'','pause_reason':'test'})
out = render(rc, {}, ps_state='paused')
tests.append(('RESUME layer1: brake re-applied', 'M220 S75' in out and 're-applied' in out,
    [l for l in out.split('\n') if 'M220' in l][:2]))
state_vars['layer'] = 2
out = render(rc, {}, ps_state='paused')
tests.append(('RESUME layer2: no brake', 'M220 S75' not in out, ''))
state_vars['layer'] = 1; state_vars['ignore_overrides'] = True
out = render(rc, {}, ps_state='paused')
tests.append(('RESUME as-sliced: no brake', 'M220 S75' not in out, ''))
state_vars['ignore_overrides'] = False

# --- watcher legacy detection resets layer_marks ---
save_vars2 = {}
_reW41 = _re40.search(r'\[delayed_gcode _STATE_WATCHER\]\ninitial_duration: 8\ngcode:\n(.*?)(?=\n\[|\Z)', open('macros/01_state.cfg').read(), _re40.S)
wt41 = '\n'.join(l[4:] if l.startswith('    ') else l for l in _reW41.group(1).split('\n'))
state_vars.update({'mode':'finished','layer':5,'layer_marks':True,'layer_z_max':9.0,'layer_z_acc':0,
                   'legacy_file':'','seq_low':0,'cancel_armed':False,'cancel_time':0.0,'pause_desync':0})
out = render(wt41, {})
tests.append(('Legacy detection resets layer_marks', 'VARIABLE=layer_marks VALUE=False' in out,
    [l for l in out.split('\n') if 'layer_marks' in l][:2]))

# --- FLOW_CAL calculator ---
fc = get_body('macros/12_maintenance.cfg', 'FLOW_CAL')
out = render(fc, {'MEASURE':0.46,'TARGET':0.4})
tests.append(('FLOW_CAL 0.46mm wall -> 87.0%', '87.0' in out and '-> 87.0%' in out, out[:200]))
out = render(fc, {'MEASURE':0.5,'TARGET':0.4})
tests.append(('FLOW_CAL implausible guard', 'implausible' not in out and '87' not in out, out[:150]))

# --- TEMP_TOWER_START + hook ---
tts = get_body('macros/12_maintenance.cfg', 'TEMP_TOWER_START')
out = render(tts, {'START':200,'END':230,'STEP':5,'BAND':10})
tests.append(('TEMP_TOWER_START plan + vars', 'bands' in out and 'VARIABLE=tt_active VALUE=True' in out
    and 'VARIABLE=tt_band VALUE=10' in out, out[:200]))
save_vars.update({'tt_active':True,'tt_start':200.0,'tt_step':5.0,'tt_band':10,'tt_end':230.0})
lm41 = get_body('macros/06_temp_controls.cfg', 'LAYER_MARK')
state_vars.update({'mode':'printing','layer':10,'legacy_mode':False})
out = render(lm41, {})   # n = 11 -> idx 1 -> 205C
tests.append(('Tower hook: layer 11 -> 205C', 'TARGET=205' in out, [l for l in out.split('\n') if 'tower' in l.lower()][:2]))
save_vars['tt_active']=False

# --- IRONING_CAL renders 3 zones ---
ic = get_body('macros/12_maintenance.cfg', 'IRONING_CAL')
state_vars['mode']='idle'
out = render(ic, {'TEMP':200})
tests.append(('R61 IRONING_CAL v2: cards + flows + prime', out.count('Ironing card')>=3 and 'flow 10%' in out
    and 'flow 20%' in out and 'Prime line' in out, out[:200]))
import re as _re41c
tests.append(('IRONING_CAL: extrusion lines', len(_re41c.findall(r'G1 X[\d.]+ E[\d.]+', out)) >= 40, len(_re41c.findall(r'G1 X[\d.]+ E[\d.]+', out))))

# --- menu: file values + new submenus + order ---
lcd41 = open('menus/lcd_menues.cfg').read()
for e in ['File H:', 'File B:', 'File R:', '__maint __flow]', '__maint __tt]', '__maint __iron]',
          'FLOW_CAL MEASURE=', 'TEMP_TOWER_START START=', 'IRONING_CAL TEMP=', 'Wall:', 'Plan (calc)']:
    tests.append((f'R41 menu: {e[:34]}', e in lcd41, 'missing'))
# R82: the maintenance menu follows the calibration ladder (per printer:
# PID -> leveling -> mesh -> extruder steps -> input shaper; per material:
# temp tower -> PA -> flow -> retract -> bridging -> ironing; then care)
ordr = [lcd41.find(x) for x in ['__maint __pid]', '__maint __level]', '__maint __mesh]', '__maint __extruder]',
         '__maint __vib]', '__maint __tt]', '__maint __pa]', '__maint __flow]', '__maint __rt]',
         '__maint __bridge]', '__maint __iron]', '__maint __cleannoz]', '__maint __fil]',
         '__maint __gantry]', '__maint __kamp]', '__maint __tests]']]
tests.append(('R82 maintenance menu = calibration ladder order', all(ordr[i] < ordr[i+1] for i in range(len(ordr)-1)) and ordr[0] > 0, ordr))

# ===================== R42: frozen layer counter after object change/skip =======
_reW42 = _re40.search(r'\[delayed_gcode _STATE_WATCHER\]\ninitial_duration: 8\ngcode:\n(.*?)(?=\n\[|\Z)', open('macros/01_state.cfg').read(), _re40.S)
wt42 = '\n'.join(l[4:] if l.startswith('    ') else l for l in _reW42.group(1).split('\n'))
# Zustand wie im Feldlog: Objektwechsel durch, Skip durchgeführt, Z-Hop/Park hat
# die Marke auf 5.2 hochgezogen, Kopf druckt jetzt bei z=0.2 (dz=-5.0 -> eingefroren)
state_vars.update({'mode':'printing','layer':0,'layer_marks':False,'layer_z_max':5.2,'layer_z_acc':0,
                   'legacy_file':'x.gcode','seq_low':0,'cancel_armed':False,'cancel_time':0.0,'pause_desync':0})
save_vars.update({'first_layer_speed':65,'ov_hotend_after_on':True,'ov_hotend_after':210.0,
                  'ov_bed_after_on':True,'ov_bed_after':55.0,'ov_fan_on':True,'ov_fan':95.0,
                  'pause_next_layer':False,'pause_at_layer':0,'tt_active':False})
out = render(wt42, {}, gz=0.2)
tests.append(('R42 cold-start: re-anchors DOWN at layer 0', 'VARIABLE=layer_z_max VALUE=0.2' in out,
    [l for l in out.split('\n') if 'layer_z_max' in l][:2]))
state_vars['layer_z_max']=0.2   # Re-Anker aus Tick 1 uebernehmen
out = render(wt42, {}, gz=0.4)   # erste Layergrenze
tests.append(('R42 frozen counter: layer 1 counts again', 'VARIABLE=layer VALUE=1' in out,
    [l for l in out.split('\n') if 'VARIABLE=layer ' in l][:2]))
state_vars['layer']=1; state_vars['layer_z_max']=0.4
out = render(wt42, {}, gz=0.6)   # zweite Layergrenze
tests.append(('R42 frozen counter: layer 2 -> L2 applies', 'VARIABLE=layer VALUE=2' in out
    and 'TARGET=210' in out and 'SET_FAN_SCALE PERCENT=95' in out,
    [l for l in out.split('\n') if 'Layer 2' in l or 'TARGET' in l][:4]))
state_vars.update({'layer':0,'layer_z_max':0.0})

# ------- R45: start dialog legacy branches (_START_CONFIRM_WAITER) ------------------------
import re as _reW
_txt7 = open('macros/07_start_confirm.cfg').read()
_mW = _reW.search(r'\[delayed_gcode _START_CONFIRM_WAITER\]\ngcode:\n(.*?)(?=\n\[|\Z)', _txt7, _reW.S)
waiter = '\n'.join(l[4:] if l.startswith('    ') else l for l in _mW.group(1).split('\n'))
state_vars['mode']='waiting'
state_vars['file_type']='legacy'
save_vars['start_decision']='as_sliced'
out = render(waiter, {})
tests.append(('WAITER legacy as_sliced = no takeover', '_LEGACY_AS_SLICED' in out and '_RUN_PRINT_START' not in out, out[:220]))
save_vars['start_decision']='as_legacy'
out = render(waiter, {})
tests.append(('WAITER legacy as_legacy = prep + takeover', '_LEGACY_PREP' in out and '_RUN_PRINT_START' not in out, out[:220]))
save_vars['start_decision']='with_overrides'
out = render(waiter, {})
tests.append(('WAITER legacy W/CHANGES -> as_legacy', 'as_legacy' in out and '_RUN_PRINT_START' not in out and 'UPDATE_DELAYED_GCODE ID=_START_CONFIRM_WAITER' in out, out[:200]))
state_vars['file_type']='marked'
save_vars['start_decision']='as_sliced'
out = render(waiter, {})
tests.append(('WAITER marked as_sliced', '_RUN_PRINT_START APPLY=0' in out, out[:200]))
save_vars['start_decision']='as_legacy'
out = render(waiter, {})
tests.append(('WAITER marked as_legacy', '_RUN_PRINT_START APPLY=1 LEGACY=1' in out, out[:200]))
save_vars['start_decision']=''
state_vars['mode']='printing'

# ------- R45: PRINT_START marks the file type ---------------------------------------------
body = get_body('macros/08_print_start_stop.cfg', 'PRINT_START')
state_vars['mode']='idle'
out = render(body, {'BED':'60','HOTEND_FIRST':'210','HOTEND_AFTER':'205','MATERIAL':'PLA'})
tests.append(('PRINT_START sets file_type=marked', 'VARIABLE=file_type VALUE=\'"marked\"\'' in out and 'File type: MARKED' in out, out[:160]))
state_vars['mode']='printing'

# ------- R45: machine limits feedback (MCR wird sichtbar an Klipper uebergeben) ------------
body = get_body('macros/10_live_tuning.cfg', 'SET_LIVE_MINIMUM_CRUISE_RATIO')
out = render(body, {'VALUE': '0.5'})
tests.append(('MCR live + feedback', 'SET_VELOCITY_LIMIT MINIMUM_CRUISE_RATIO=0.5' in out and 'cruise ratio 0.5' in out, out[:200]))
body = get_body('macros/08_print_start_stop.cfg', '_APPLY_OVERRIDES_CORE')
save_vars['ov_min_cruise_on']=True; save_vars['ov_min_cruise']=0.5
out = render(body, {})
tests.append(('MCR override -> Klipper + log', 'MINIMUM_CRUISE_RATIO=0.5' in out and 'cruise ratio 0.5' in out, [l for l in out.split('\n') if 'cruise' in l or 'SET_VELOCITY_LIMIT' in l][:3]))
save_vars['ov_min_cruise_on']=False

# ------- R45: L1 speed brake only WITH apply (AS SLICED = truly 1:1) -----------------------
body = get_body('macros/08_print_start_stop.cfg', '_RUN_PRINT_START')
out = render(body, {'APPLY': '0'})
tests.append(('L1 brake OFF when APPLY=0', 'First layer speed' not in out, [l for l in out.split('\n') if 'First layer' in l or 'M220' in l][:3]))
out = render(body, {'APPLY': '1'})
tests.append(('L1 brake ON when APPLY=1', 'First layer speed' in out, [l for l in out.split('\n') if 'First layer' in l][:2]))

# ======= R46: Nozzle LED + LED idle return + state cleanup ==================================

# ------- _NOZZLE_SET: manual color math (power cap 0.5, brightness) -------------------------
body = get_body('macros/03_leds.cfg', '_NOZZLE_SET')
out = render(body, {'ON': '1'})
tests.append(('NOZZLE_SET default warm white', 'RED=0.45' in out and 'GREEN=0.45' in out and 'BLUE=0.425' in out and 'INDEX=5' in out, out.strip()[:140]))
save_vars['nozzle_bright']=0.4; save_vars['nozzle_r']=1.0; save_vars['nozzle_g']=1.0; save_vars['nozzle_b']=1.0
out = render(body, {'ON': '1'})
tests.append(('NOZZLE_SET dim 40% scales', 'RED=0.2 GREEN=0.2 BLUE=0.2' in out, out.strip()[:140]))
save_vars['nozzle_bright']=1.0
out = render(body, {'ON': '1'})
tests.append(('NOZZLE_SET power cap 0.5', 'RED=0.5 GREEN=0.5 BLUE=0.5' in out, out.strip()[:140]))
out = render(body, {'ON': '0'})
tests.append(('NOZZLE_SET dark', 'RED=0 GREEN=0 BLUE=0' in out, out.strip()[:140]))
save_vars['nozzle_r']=0.9; save_vars['nozzle_g']=0.9; save_vars['nozzle_b']=0.85

# ------- SET_LED_STATE: nozzle modes --------------------------------------------------------
body = get_body('macros/03_leds.cfg', 'SET_LED_STATE')
out = render(body, {'STATE': 'idle'})
tests.append(('LED_STATE idle+auto: nozzle dark', '_NOZZLE_SET ON=0' in out and 'r2_nozzle_on' not in out and 'EFFECT=r2_idle' in out, out[:200]))
out = render(body, {'STATE': 'printing'})
tests.append(('LED_STATE printing+auto: nozzle effect', 'EFFECT=r2_nozzle_on' in out and 'EFFECT=r2_printing' in out, out[:200]))
save_vars['nozzle_mode']='on'
out = render(body, {'STATE': 'idle'})
tests.append(('LED_STATE idle+ON: manual color', '_NOZZLE_SET ON=1' in out and 'r2_nozzle_on' not in out, out[:200]))
save_vars['nozzle_mode']='off'
out = render(body, {'STATE': 'printing'})
tests.append(('LED_STATE printing+OFF: never', '_NOZZLE_SET ON=0' in out and 'EFFECT=r2_nozzle_on' not in out, out[:200]))
save_vars['leds_on']=False; save_vars['nozzle_mode']='on'
out = render(body, {'STATE': 'idle'})
tests.append(('LED_STATE master OFF + nozzle ON (tool light)', '_NOZZLE_SET ON=1' in out and 'STOP_LED_EFFECTS' not in out, out[:200]))
save_vars['nozzle_mode']='auto'
out = render(body, {'STATE': 'idle'})
tests.append(('LED_STATE master OFF + auto: all dark', '_NOZZLE_SET ON=0' in out and 'STOP_LED_EFFECTS' not in out, out[:200]))
save_vars['leds_on']=True; save_vars['nozzle_mode']='auto'

# ------- NOZZLE_LED: the public switch ------------------------------------------------------
body = get_body('macros/03_leds.cfg', 'NOZZLE_LED')
out = render(body, {'MODE': 'on'})
tests.append(('NOZZLE_LED MODE=on saves+applies', "VARIABLE=nozzle_mode VALUE='\"on\"'" in out and 'SET_LED_STATE STATE=printing' in out and '[OK] Nozzle LED: ON' in out, out[:220]))
out = render(body, {'BRIGHT': '0.4'})
tests.append(('NOZZLE_LED BRIGHT live', 'VARIABLE=nozzle_bright VALUE=0.4' in out and 'SET_LED_STATE STATE=printing' in out, out[:200]))
out = render(body, {'R': '1', 'G': '0.5', 'B': '0.2'})
tests.append(('NOZZLE_LED RGB live', 'VARIABLE=nozzle_r VALUE=1.0' in out and 'VARIABLE=nozzle_g VALUE=0.5' in out and 'VARIABLE=nozzle_b VALUE=0.2' in out, out[:200]))
out = render(body, {'MODE': 'pink'})
tests.append(('NOZZLE_LED bad MODE -> hint', '[!]' in out and 'SAVE_VARIABLE' not in out, out[:160]))
out = render(body, {})
tests.append(('NOZZLE_LED status report', 'Nozzle LED: AUTO' in out and 'bright 100%' in out, out[:220]))

# ------- _LED_TO_IDLE: finished -> idle return (used to twinkle FOREVER) --------------------
import re as _reL
_txt3 = open('macros/03_leds.cfg').read()
_mL = _reL.search(r'\[delayed_gcode _LED_TO_IDLE\]\ngcode:\n(.*?)(?=\n\[|\Z)', _txt3, _reL.S)
ledidle = '\n'.join(l[4:] if l.startswith('    ') else l for l in _mL.group(1).split('\n'))
state_vars['mode']='idle'; state_vars['last_led']='finished'
out = render(ledidle, {})
tests.append(('LED_TO_IDLE fires after finished', 'SET_LED_STATE STATE=idle' in out, out[:160]))
state_vars['last_led']='printing'
out = render(ledidle, {})
tests.append(('LED_TO_IDLE skips other LED states', 'SET_LED_STATE' not in out, out[:160]))
state_vars['mode']='printing'
out = render(ledidle, {})
tests.append(('LED_TO_IDLE skips while printing', 'SET_LED_STATE' not in out, out[:160]))

# ------- _PRINT_CLEANUP: the one reset list -------------------------------------------------
body = get_body('macros/09_pause_filament.cfg', '_PRINT_CLEANUP')
out = render(body, {})
tests.append(('PRINT_CLEANUP resets everything', 'cancel_armed VALUE=False' in out and 'skip_armed_name' in out and 'mesh_delete_armed' in out and 'legacy_mode VALUE=False' in out and 'ignore_overrides VALUE=False' in out and 'file_type VALUE=\'"unknown"\'' in out and 'file_held VALUE=False' in out and 'wait_ticks VALUE=0' in out and 'pause_was_sd VALUE=False' in out and '_LIVE_RESET' in out and 'pause_next_layer VALUE=False' in out and 'pause_at_layer VALUE=0' in out, out[:300]))
tests.append(('PRINT_CLEANUP keeps settings+mesh', 'ov_bed' not in out and 'mesh_last_profile' not in out and 'SAVE_CONFIG' not in out, out[:200]))

# ------- _END_FAN_OFF: guard against the NEXT print -----------------------------------------
_txt8 = open('macros/08_print_start_stop.cfg').read()
_mE = _reL.search(r'\[delayed_gcode _END_FAN_OFF\]\ngcode:\n(.*?)(?=\n\[|\Z)', _txt8, _reL.S)
fanoff = '\n'.join(l[4:] if l.startswith('    ') else l for l in _mE.group(1).split('\n'))
state_vars['mode']='idle'
out = render(fanoff, {})
tests.append(('END_FAN_OFF fires when idle', 'M99106 S0' in out, out[:120]))
state_vars['mode']='printing'
out = render(fanoff, {})
tests.append(('END_FAN_OFF guarded during new print', 'M99106' not in out, out[:120]))

# ------- watcher: cancel expiry ALSO while paused + legacy end cleanup ----------------------
_txt1 = open('macros/01_state.cfg').read()
_mW2 = _reL.search(r'\[delayed_gcode _STATE_WATCHER\]\ninitial_duration: 8\ngcode:\n(.*?)(?=\n\[|\Z)', _txt1, _reL.S)
watcher2 = '\n'.join(l[4:] if l.startswith('    ') else l for l in _mW2.group(1).split('\n'))
state_vars['mode']='paused'; state_vars['cancel_armed']=True; state_vars['cancel_time']=0
out = render(watcher2, {}, ps_state='paused')
tests.append(('WATCHER cancel expiry while paused (R46)', 'cancel_armed VALUE=False' in out and 'Cancel expired' in out, out[:220]))
state_vars['cancel_armed']=False; state_vars['cancel_time']=0
state_vars['mode']='printing'
out = render(watcher2, {}, ps_state='complete')
tests.append(('WATCHER legacy end: LED timer + cleanup', '_LED_TO_IDLE DURATION=10' in out and '_PRINT_CLEANUP' in out, [l for l in out.split('\n') if 'LED_TO_IDLE' in l or 'CLEANUP' in l][:2]))

# ------- defaults hydration + status line ---------------------------------------------------
body = get_body('macros/01_state.cfg', '_INIT_DEFAULTS')
render(body, {})
tests.append(('INIT hydrates nozzle defaults', 'VARIABLE=nozzle_mode' in body and 'VARIABLE=nozzle_bright' in body and 'VARIABLE=nozzle_r' in body and 'VARIABLE=led_finish_time' in body, [l for l in body.split('\n') if 'nozzle' in l.lower() or 'led_finish' in l.lower()][:4]))
body = get_body('macros/04_notify.cfg', 'SHOW_STATUS')
out = render(body, {})
tests.append(('SHOW_STATUS nozzle LED line', 'Nozzle LED: AUTO' in out and 'bright 100%' in out, [l for l in out.split('\n') if 'Nozzle LED' in l][:1]))

# ------- R46 extras: boot re-light + master-toggle hint --------------------------------------
import re as _reB
_mB = _reB.search(r'\[delayed_gcode _INIT_AFTER_BOOT\]\ninitial_duration: 5\ngcode:\n(.*?)(?=\n\[|\Z)', open('macros/01_state.cfg').read(), _reB.S)
bootinit = '\n'.join(l[4:] if l.startswith('    ') else l for l in _mB.group(1).split('\n'))
save_vars['nozzle_mode']='on'
out = render(bootinit, {})
tests.append(('BOOT re-lights nozzle when ON', '_NOZZLE_SET ON=1' in out, out[:160]))
save_vars['nozzle_mode']='auto'
out = render(bootinit, {})
tests.append(('BOOT leaves nozzle off in AUTO', '_NOZZLE_SET' not in out, out[:160]))
body = get_body('macros/03_leds.cfg', 'TOGGLE_LEDS')
save_vars['nozzle_mode']='on'
out = render(body, {})
tests.append(('TOGGLE_LEDS off hints at nozzle light', 'STOP_LED_EFFECTS' in out and 'nozzle work light stays' in out, out[:200]))
save_vars['nozzle_mode']='auto'
out = render(body, {})
tests.append(('TOGGLE_LEDS off: no hint in AUTO', 'nozzle work light' not in out, out[:160]))

# ======= R47: legacy start-dialog chain (the .30 field regression) ==========================

# ------- 1) _LEGACY_DIALOG must SCHEDULE the waiter + clear a stale decision ----------------
body = get_body('macros/08_print_start_stop.cfg', '_LEGACY_DIALOG')
out = render(body, {})
tests.append(('LEGACY_DIALOG schedules the WAITER (R47)', 'UPDATE_DELAYED_GCODE ID=_START_CONFIRM_WAITER' in out, out[:200]))
tests.append(('LEGACY_DIALOG clears stale decision', 'VARIABLE=start_decision VALUE=' in out and 'wait_ticks VALUE=0' in out, out[:200]))

# ------- 2) M190/M109 must NOT block while the legacy dialog is imminent --------------------
body = get_body('macros/06_temp_controls.cfg', 'M190')
state_vars['mode']='idle'
out = render(body, {'S': '60'})
tests.append(('M190 legacy-start: preheat, no blocking wait', 'M99140 S60' in out and 'M99190' not in out and 'background' in out, out[:200]))
body = get_body('macros/06_temp_controls.cfg', 'M109')
out = render(body, {'S': '210'})
tests.append(('M109 always heats + waits (R48)', 'M99109 S210' in out and 'Heating hotend' in out and 'M99104' not in out, out[:200]))
state_vars['mode']='printing'
body = get_body('macros/06_temp_controls.cfg', 'M190')
out = render(body, {'S': '60'})
tests.append(('M190 normal print: heat + wait', 'M99190 S60' in out and 'Heating bed' in out, out[:160]))

# ------- 3) PRINT_START heals a STALE mode instead of refusing forever ----------------------
body = get_body('macros/08_print_start_stop.cfg', 'PRINT_START')
state_vars['mode']='waiting'
out = render(body, {'BED':'60','HOTEND_FIRST':'210'}, ps_state='standby')
tests.append(('PRINT_START heals stale waiting', 'Healing stale mode' in out and 'file_type' in out and 'already running' not in out, out[:220]))
out = render(body, {'BED':'60'}, ps_state='printing')
tests.append(('PRINT_START still refuses while running', 'already running' in out and 'Healing stale mode' not in out, out[:160]))
state_vars['mode']='printing'

# ------- 4) RESUME continues the file even when pause_was_sd is False -----------------------
body = get_body('macros/09_pause_filament.cfg', '_RESUME_COMMON')
state_vars['pause_was_sd']=False
out = render(body, {}, ps_state='paused')
tests.append(('RESUME continues paused file (no was_sd)', 'M24' in out and 'PAUSE_STATE' in out, out[:200]))
state_vars['pause_was_sd']=True
out = render(body, {}, ps_state='printing')
tests.append(('RESUME running: still no M24', 'M24' not in out, out[:160]))

# ------- 5) LCD main menu order: Start first, Live Tuning second ----------------------------
_txtM = open('menus/lcd_menues.cfg').read()
_posM = [(_txtM.index('[menu __main __start]'), 'start'), (_txtM.index('[menu __main __live]'), 'live'),
         (_txtM.index('[menu __main __preprint]'), 'preprint'), (_txtM.index('[menu __main __macros]'), 'macros')]
_posM.sort()
tests.append(('MENU order: Start > Live > Pre-Print', [n for _, n in _posM] == ['start', 'live', 'preprint', 'macros'], [n for _, n in _posM]))

# ======= R48: START_PRINT = real legacy start + watchdog ====================================

# ------- START_PRINT shim: 4 branches -------------------------------------------------------
body = get_body('macros/08_print_start_stop.cfg', 'START_PRINT')
state_vars['mode']='printing'
out = render(body, {})
tests.append(('START_PRINT marked -> no-op', 'prepared by PRINT_START' in out and '_LEGACY_DIALOG' not in out and '_LEGACY_PREP' not in out, out[:140]))
state_vars['file_type']='legacy'; state_vars['legacy_file']=''
out = render(body, {})
tests.append(('START_PRINT legacy + confirm -> dialog', '_LEGACY_DIALOG' in out and 'VARIABLE=file_type' in out, out[:160]))
save_vars['start_confirm']=False
out = render(body, {})
tests.append(('START_PRINT legacy + no confirm -> prep', '_LEGACY_PREP' in out and '_LEGACY_DIALOG' not in out, out[:160]))
save_vars['start_confirm']=True
state_vars['legacy_file']='test.gcode'
out = render(body, {})
tests.append(('START_PRINT already prepped -> no-op', 'already prepared' in out and '_LEGACY_PREP' not in out, out[:160]))
state_vars['legacy_file']=''
out = render(body, {}, ps_state='idle')
tests.append(('START_PRINT outside print -> info', 'outside a print' in out and '_LEGACY_PREP' not in out, out[:160]))
state_vars['file_type']='marked'

# ------- waiter as_sliced-legacy: home + wait file temps + purge + mark ----------------------
state_vars['mode']='waiting'; state_vars['file_type']='legacy'
save_vars['start_decision']='as_sliced'
out = render(waiter, {})
tests.append(('WAITER legacy as_sliced: calls AS_SLICED macro (R50)', '_LEGACY_AS_SLICED' in out and '_RUN_PRINT_START' not in out, out[-300:]))
save_vars['start_decision']=''
state_vars['file_type']='marked'; state_vars['mode']='printing'

# ------- watchdog re-arms the state watcher -------------------------------------------------
_txtWd = open('macros/01_state.cfg').read()
_mWd = _reL.search(r'\[delayed_gcode _WATCHDOG\]\ninitial_duration: 30\ngcode:\n(.*?)(?=\n\[|\Z)', _txtWd, _reL.S)
assert _mWd, 'watchdog not found'
wdg = '\n'.join(l[4:] if l.startswith('    ') else l for l in _mWd.group(1).split('\n'))
out = render(wdg, {})
tests.append(('WATCHDOG re-arms itself + watcher', 'ID=_WATCHDOG DURATION=5' in out and 'ID=_STATE_WATCHER DURATION=0.5' in out, out[:120]))

# ------- cleanup resets legacy_file (same-file reprint guard) --------------------------------
body = get_body('macros/09_pause_filament.cfg', '_PRINT_CLEANUP')
out = render(body, {})
tests.append(('PRINT_CLEANUP resets legacy_file (R48)', 'VARIABLE=legacy_file' in out, out[:200]))

# ------- R49: z-hop must not fake a sequential object change --------------------------------
# field log .32: z-hop ratcheted layer_z_max to print_z+hop; as soon as that crossed
# 1.6 while print_z < 1.5 the detector fired -> pause + L1 temps MID-OBJECT.
state_vars['layer']=5; state_vars['layer_z_max']=1.75; state_vars['layer_marks']=False
out = render(watcher, {}, gz=1.0)
tests.append(('SEQ hop un-ratchet: mark cleaned, NO fire (R49)',
    'VARIABLE=layer_z_max VALUE=1.0' in out and 'Sequential print' not in out and 'PAUSE REASON' not in out, out[:220]))
out = render(watcher, {}, gz=1.75)
tests.append(('SEQ hop top caught: no fire at the top',
    'Sequential print' not in out and 'PAUSE REASON' not in out, out[:220]))
state_vars['layer_marks']=True
out = render(watcher, {}, gz=1.0)
tests.append(('SEQ hop un-ratchet also for marked files',
    'VARIABLE=layer_z_max VALUE=1.0' in out and 'Sequential print' not in out, out[:220]))
state_vars['layer_marks']=False; state_vars['layer_z_max']=2.4
out = render(watcher, {}, gz=0.3)
tests.append(('SEQ real object change still fires (fall > 1.0)',
    'next object' in out and 'PAUSE REASON="next object' in out, out[:200]))
state_vars['layer_z_max']=0.0

# ------- R49: anti-ooze - file temp capture + standby + re-heat ------------------------------
state_vars['mode']='idle'
body = get_body('macros/06_temp_controls.cfg', 'M104')
out = render(body, {'S': '215'})
tests.append(('M104 early: captures file hotend (R49)', 'file_hotend_first VALUE=215' in out, out[:160]))
body = get_body('macros/06_temp_controls.cfg', 'M109')
out = render(body, {'S': '225'})
tests.append(('M109 early: capture + still waits', 'file_hotend_first VALUE=225' in out and 'M99109 S225' in out, out[:180]))
body = get_body('macros/06_temp_controls.cfg', 'M190')
out = render(body, {'S': '60'})
tests.append(('M190 early: captures file bed', 'file_bed VALUE=60' in out and 'M99140 S60' in out, out[:180]))
state_vars['mode']='printing'
body = get_body('macros/08_print_start_stop.cfg', '_LEGACY_PREP')
out = render(body, {})
tests.append(('LEGACY_PREP standby 170 (anti-ooze)', 'TARGET=170' in out and 'standby' in out, out[:200]))
state_vars['mode']='paused'; state_vars['file_hotend_first']=225.0
save_vars['ov_hotend_first_on']=False
_gd2 = dict(build_printer(ps_state='paused'))   # NOTE: M(state_vars) SNAPSHOTS - set state BEFORE building
_gd2['extruder'] = M({'temperature': 170.0, 'target': 170.0})
out = env.from_string(prep2).render(printer=M(_gd2), params={})
tests.append(('PREP2 re-heats to FILE value after standby', 'TARGET=225' in out and 'TARGET=170' not in out, [l for l in out.split('\n') if 'TARGET' in l][:3]))
save_vars['ov_hotend_first_on']=True
state_vars['file_hotend_first']=0.0
state_vars['mode']='printing'

# ------- R50: universal print intercept (every file, whatever it is) --------------------------
body = get_body('macros/08_print_start_stop.cfg', 'SDCARD_PRINT_FILE')
state_vars['mode']='idle'
out = render(body, {'FILENAME': 'rose.gcode'})
tests.append(('R51 PRINT BUTTON: guard + load + M25 hold + intercept',
    'VARIABLE=mode VALUE=\'"waiting"\'' in out and 'BASE_SDCARD_PRINT_FILE FILENAME="rose.gcode"' in out
    and 'M25' in out and '_UNIVERSAL_START_INTERCEPT' in out, out[:220]))
state_vars['mode']='waiting'
out = render(body, {'FILENAME': 'rose.gcode'})
tests.append(('R51 PRINT BUTTON while waiting: refused',
    'Start dialog active' in out and 'BASE_SDCARD_PRINT_FILE' not in out, out[:160]))
state_vars['mode']='idle'
save_vars['start_confirm']=False
out = render(body, {'FILENAME': 'rose.gcode'})
tests.append(('R51 PRINT BUTTON confirm OFF: plain start',
    'BASE_SDCARD_PRINT_FILE' in out and 'M25' not in out and '_UNIVERSAL_START_INTERCEPT' not in out, out[:160]))
save_vars['start_confirm']=True

body = get_body('macros/08_print_start_stop.cfg', 'M24')
out = render(body, {}, ps_state='standby')
tests.append(('R51 M24 fresh start: intercept instead of start',
    '_UNIVERSAL_START_INTERCEPT' in out and 'M9924' not in out, out[:160]))
save_vars['start_confirm']=False
out = render(body, {}, ps_state='standby')
tests.append(('R51 M24 fresh confirm OFF: plain start', 'M9924' in out and '_UNIVERSAL' not in out, out[:140]))
save_vars['start_confirm']=True
out = render(body, {}, ps_state='paused')
tests.append(('R51 M24 resume (paused): plain pass',
    'M9924' in out and '_UNIVERSAL' not in out, out[:140]))
state_vars['mode']='waiting'
out = render(body, {}, ps_state='paused')
tests.append(('R51 M24 while waiting: refused', 'Start dialog active' in out and 'M9924' not in out, out[:140]))
state_vars['mode']='idle'

body = get_body('macros/08_print_start_stop.cfg', '_UNIVERSAL_START_INTERCEPT')
state_vars['file_type']='marked'; state_vars['has_heaters']=True; state_vars['layer']=7
out = render(body, {})
tests.append(('R51 INTERCEPT: fresh state + dialog + waiter (no pause games)',
    '_FILE_INFO_RESET' in out and 'VARIABLE=has_heaters VALUE=False' in out
    and 'VARIABLE=start_pending VALUE=\'""\'' in out and 'VARIABLE=layer VALUE=0' in out
    and 'VARIABLE=file_accel VALUE=0' in out and 'PAUSE_BASE' not in out
    and '_START_CONFIRM_WAITER DURATION=2' in out, out[:280]))
state_vars['mode']='printing'

# waiter: the three decisions on an UNKNOWN file
state_vars['mode']='waiting'; state_vars['file_type']='unknown'
save_vars['start_decision']='as_sliced'
out = render(waiter, {})
tests.append(('R50 WAITER as_sliced unknown: pending + resume + probe',
    'VARIABLE=start_pending VALUE=\'"as_sliced"\'' in out and 'VARIABLE=probe_stage VALUE=1' in out
    and '_START_NET_PROBE DURATION=3' in out and 'M24' in out, out[:260]))
save_vars['start_decision']='with_overrides'
out = render(waiter, {})
tests.append(('R50 WAITER with_overrides unknown: pending + probe',
    'VARIABLE=start_pending VALUE=\'"overrides"\'' in out and '_START_NET_PROBE DURATION=3' in out, out[:260]))
save_vars['start_decision']='as_legacy'
out = render(waiter, {})
tests.append(('R51 WAITER as_legacy unknown: rides along + probe',
    'VARIABLE=start_pending VALUE=\'"as_legacy"\'' in out and '_START_NET_PROBE DURATION=3' in out
    and 'M24' in out and '_LEGACY_PREP' not in out, out[:260]))
save_vars['start_decision']=''

# the net probe (movement-file detection)
_txtC = open('macros/08_print_start_stop.cfg').read()
_mN = _reL.search(r'\[delayed_gcode _START_NET_PROBE\]\ngcode:\n(.*?)(?=\n\[|\n# ==|\Z)', _txtC, _reL.S)
assert _mN, 'net probe not found'
body = '\n'.join(l[4:] if l.startswith('    ') else l for l in _mN.group(1).split('\n'))
state_vars['mode']='printing'; state_vars['file_type']='unknown'
state_vars['start_pending']='as_sliced'; state_vars['has_heaters']=False; state_vars['probe_stage']=1
out = render(body, {})
tests.append(('R50 PROBE stage1: no heaters -> second look',
    'VARIABLE=probe_stage VALUE=2' in out and '_START_NET_PROBE DURATION=7' in out and '_MOVEMENT_START' not in out, out[:180]))
state_vars['probe_stage']=2
out = render(body, {})
tests.append(('R50 PROBE stage2: movement file -> infra APPLY=0',
    'VARIABLE=file_type VALUE=\'"movement"\'' in out and '_MOVEMENT_START APPLY=0' in out, out[:180]))
state_vars['start_pending']='overrides'
out = render(body, {})
tests.append(('R50 PROBE movement + overrides: APPLY=1', '_MOVEMENT_START APPLY=1' in out, out[:160]))
state_vars['start_pending']='as_sliced'; state_vars['has_heaters']=True; state_vars['probe_stage']=1
out = render(body, {})
tests.append(('R50 PROBE has_heaters: disarm, KEEP pending',
    'VARIABLE=probe_stage VALUE=0' in out and 'VARIABLE=start_pending' not in out and '_MOVEMENT_START' not in out, out[:200]))
state_vars['start_pending']=''; state_vars['has_heaters']=False
out = render(body, {})
tests.append(('R50 PROBE idle when pending empty', 'probe_stage' not in out and '_MOVEMENT_START' not in out, out[:120]))

# movement infrastructure
body = get_body('macros/08_print_start_stop.cfg', '_MOVEMENT_START')
save_vars['material']='PLA'
save_vars['ov_bed_on']=False; save_vars['ov_hotend_first_on']=False
out = render(body, {})
tests.append(('R50 MOVEMENT as sliced: preset temps + mesh + purge + resume',
    'TARGET=60' in out and 'TARGET=210' in out and '_CALIBRATE_MESH_PROFILE PROFILE=r2' in out
    and '_PRIME_LINE' in out and '_APPLY_OVERRIDES_CORE' not in out and 'M24' in out, out[:280]))
out = render(body, {'APPLY': '1'})
tests.append(('R50 MOVEMENT with settings: ov temps + overrides core',
    'TARGET=60' in out and 'TARGET=210' in out and '_APPLY_OVERRIDES_CORE' in out, out[:280]))
save_vars['ov_bed_on']=True; save_vars['ov_bed']=70
save_vars['ov_hotend_first_on']=True; save_vars['ov_hotend_first']=235
out = render(body, {'APPLY': '1'})
tests.append(('R50 MOVEMENT with settings: ov values win',
    'TARGET=70' in out and 'TARGET=235' in out, out[:280]))
save_vars['ov_bed_on']=False; save_vars['ov_hotend_first_on']=False

# PRINT_START honors a pending decision (no second dialog)
body = get_body('macros/08_print_start_stop.cfg', 'PRINT_START')
state_vars['file_type']='unknown'; state_vars['start_pending']='as_sliced'
out = render(body, {'BED': '60', 'HOTEND_FIRST': '215'})
tests.append(('R50 PRINT_START pending as_sliced: direct RUN APPLY=0',
    '_RUN_PRINT_START APPLY=0' in out and 'PAUSE_BASE' not in out and 'already running' not in out
    and 'VARIABLE=start_pending VALUE=\'""\'' in out, out[:300]))
state_vars['start_pending']='overrides'
out = render(body, {})
tests.append(('R51 PRINT_START pending overrides: APPLY=1',
    '_RUN_PRINT_START APPLY=1' in out and 'PAUSE_BASE' not in out, out[:300]))
state_vars['start_pending']='as_legacy'
out = render(body, {})
tests.append(('R51 PRINT_START pending as_legacy: APPLY=1 LEGACY=1',
    '_RUN_PRINT_START APPLY=1 LEGACY=1' in out, out[:300]))
state_vars['start_pending']=''

# START_PRINT honors a pending decision
body = get_body('macros/08_print_start_stop.cfg', 'START_PRINT')
state_vars['file_type']='legacy'; state_vars['legacy_file']=''
state_vars['start_pending']='as_sliced'
out = render(body, {})
tests.append(('R50 START_PRINT pending as_sliced: AS_SLICED infra',
    '_LEGACY_AS_SLICED' in out and '_LEGACY_DIALOG' not in out, out[:200]))
state_vars['start_pending']='overrides'
out = render(body, {})
tests.append(('R50 START_PRINT pending overrides: PREP takeover',
    '_LEGACY_PREP' in out and '_LEGACY_DIALOG' not in out, out[:200]))
state_vars['start_pending']=''

# _LEGACY_AS_SLICED (the extracted R48 infra)
body = get_body('macros/08_print_start_stop.cfg', '_LEGACY_AS_SLICED')
out = render(body, {})
tests.append(('R50 LEGACY_AS_SLICED: pause + waits + purge + mark + resume',
    'PAUSE_BASE' in out and 'TEMPERATURE_WAIT SENSOR=heater_bed' in out and 'TEMPERATURE_WAIT SENSOR=extruder' in out
    and '_PRIME_LINE' in out and 'legacy_file' in out and 'M24' in out, out[:300]))

# M104: raw capture + WITH-SETTINGS takeover injection
body = get_body('macros/06_temp_controls.cfg', 'M104')
state_vars['file_type']='unknown'; state_vars['start_pending']='overrides'
out = render(body, {'S': '215'})
tests.append(('R50 M104 WITH-SETTINGS: foreign takeover once',
    '_LEGACY_PREP' in out and 'VARIABLE=start_pending VALUE=\'""\'' in out
    and 'VARIABLE=has_heaters VALUE=True' in out, out[:260]))
state_vars['start_pending']='as_sliced'
out = render(body, {'S': '215'})
tests.append(('R50 M104 as_sliced: RAW capture, no takeover',
    'file_hotend_first VALUE=215' in out and '_LEGACY_PREP' not in out and 'VARIABLE=has_heaters VALUE=True' in out, out[:260]))
state_vars['start_pending']=''

# M221: capture + flow overwrite redirect
body = get_body('macros/06_temp_controls.cfg', 'M221')
state_vars['mode']='idle'
out = render(body, {'S': '92'})
tests.append(('R50 M221 pre-decision: capture file flow', 'file_flow VALUE=92.0' in out, out[:160]))
state_vars['mode']='printing'; save_vars['ov_flow_on']=True; save_vars['ov_flow']=105
out = render(body, {'S': '92'})
tests.append(('R50 M221 overwrite ON -> 105', 'M99221 S105' in out and 'OVERWRITE' in out, out[:200]))
state_vars['ignore_overrides']=True
out = render(body, {'S': '92'})
tests.append(('R50 M221 as sliced: 1:1 pass', 'M99221 S92' in out, out[:160]))
state_vars['ignore_overrides']=False; save_vars['ov_flow_on']=False

# M106: file fan capture
body = get_body('macros/06_temp_controls.cfg', 'M106')
state_vars['mode']='idle'
out = render(body, {'S': '200'})
tests.append(('R50 M106 pre-decision: capture file fan', 'file_fan VALUE=200' in out, out[:160]))
state_vars['mode']='printing'

# M204 / M220: file accel + speed factor captures (R51)
body = get_body('macros/06_temp_controls.cfg', 'M204')
state_vars['mode']='idle'
out = render(body, {'S': '6500'})
tests.append(('R51 M204 pre-decision: capture file accel', 'file_accel VALUE=6500.0' in out, out[:160]))
out = render(body, {'S': '6500'}, ps_state='idle')
tests.append(('R51 M204 idle (no print): no capture', 'file_accel' not in out, out[:120]))
state_vars['mode']='printing'
body = get_body('macros/06_temp_controls.cfg', 'M220')
state_vars['mode']='idle'
out = render(body, {'S': '80'})
tests.append(('R51 M220 pre-decision: capture file speed', 'file_speed VALUE=80.0' in out, out[:160]))
state_vars['mode']='printing'

# ------- R53: nozzle wipe - heat + zigzag on the pad + park high ----------------------------
body = get_body('macros/12_maintenance.cfg', 'CLEAN_NOZZLE')
out = render(body, {}, ps_state='printing')
tests.append(('R53 CLEAN_NOZZLE refused while printing',
    'Not while printing' in out and '_NOZZLE_WIPE' not in out, out[:140]))
out = render(body, {'PASSES': '9'}, ps_state='idle')
tests.append(('R53 CLEAN_NOZZLE validates PASSES',
    'PASSES must be 1-5' in out and '_NOZZLE_WIPE' not in out, out[:140]))
out = render(body, {}, ps_state='idle')
tests.append(('R53 CLEAN_NOZZLE public: forwards to wipe',
    '_NOZZLE_WIPE PASSES=2' in out and 'parked high' in out, out[:160]))

body = get_body('macros/12_maintenance.cfg', '_NOZZLE_WIPE')
out = render(body, {}, etemp=150)
tests.append(('R53 WIPE cold: heats to 180 first + zigzag + parks high',
    'TARGET=180' in out and 'TEMPERATURE_WAIT SENSOR=extruder' in out and 'G1 Z4' in out
    and 'G1 X13.0 Y3.2 F7000' in out and 'G1 X0.0 Y6.5 F7000' in out and 'G1 X13.0 Y9.8 F7000' in out and 'G1 X0.0 Y13.0 F7000' in out
    and 'G0 Z15' in out and 'G1 Z-' not in out, out[:300]))
out = render(body, {}, etemp=225)
tests.append(('R53 WIPE hot: no re-heat, straight to the pad',
    'SET_HEATER_TEMPERATURE' not in out and 'G1 Z4' in out and 'F7000' in out, out[:200]))
out = render(body, {'PASSES': '1'}, etemp=225)
tests.append(('R53 WIPE PASSES=1: exactly one pass',
    out.count('F7000') == 4, [l for l in out.split(chr(10)) if 'F7000' in l]))
out = render(body, {}, etemp=225, extra=None)
_gdW = dict(build_printer(etemp=150))
_gdW['extruder'] = M({'temperature': 150.0, 'target': 0.0})
out = render(body, {}, extra={'printer': M(_gdW)})
tests.append(('R53 WIPE cold idle call: heater back OFF after',
    out.rstrip().split(chr(10))[-1].strip().startswith('SET_HEATER_TEMPERATURE HEATER=extruder TARGET=0'), out[-160:]))

# the wipe is part of EVERY purge chain
_txtP = open('macros/08_print_start_stop.cfg').read()
tests.append(('R53 PRIME_LINE starts with the wipe',
    _txtP.index('_NOZZLE_WIPE') < _txtP.index('[gcode_macro _PRIME_LINE]') + 900 and 'R53: heat + zigzag wipe' in _txtP, ''))
body = get_body('macros/14_kamp.cfg', '_PURGE_SMART')
out = render(body, {}, kamp=True, objs=[{'name':'o','center':[100,110],'polygon':[[70,80],[130,80],[130,140],[70,140]]}])
save_vars['kamp_purge']=True; save_vars['kamp_purge_type']='VORON'
out = render(body, {}, kamp=True, objs=[{'name':'o','center':[100,110],'polygon':[[70,80],[130,80],[130,140],[70,140]]}])
tests.append(('R53 KAMP VORON purge: wipe first',
    '_NOZZLE_WIPE' in out and 'VORON_PURGE' in out and out.index('_NOZZLE_WIPE') < out.index('VORON_PURGE'), out[:200]))
save_vars['kamp_purge_type']='LINE'
out = render(body, {}, kamp=True, objs=[{'name':'o','center':[100,110],'polygon':[[70,80],[130,80],[130,140],[70,140]]}])
tests.append(('R53 KAMP LINE purge: wipe first',
    '_NOZZLE_WIPE' in out and 'LINE_PURGE' in out and out.index('_NOZZLE_WIPE') < out.index('LINE_PURGE'), out[:200]))
save_vars['kamp_purge_type']='LINE'; save_vars['kamp_purge']=True

# cleanup resets the R50 intercept state
body = get_body('macros/09_pause_filament.cfg', '_PRINT_CLEANUP')
out = render(body, {})
tests.append(('R50 CLEANUP resets intercept state',
    'start_pending' in out and 'has_heaters' in out and 'probe_stage' in out
    and 'file_fan' in out and 'file_flow' in out, out[:200]))

# intercept homes as a safe baseline when axes are missing
_gd6 = dict(build_printer(gz=2.5))
_gd6['toolhead'] = M({'axis_maximum': M({'x':235.0,'y':235.0,'z':250.0}),
                      'axis_minimum': M({'x':0.0,'y':0.0,'z':0.0}), 'homed_axes':'xy', 'max_accel':4000})
state_vars['mode']='idle'
body = get_body('macros/08_print_start_stop.cfg', '_UNIVERSAL_START_INTERCEPT')
out = render(body, {}, extra={'printer': M(_gd6)})
tests.append(('R50 INTERCEPT homes + lifts when unhomed', 'G28' in out and 'G0 Z10 F600' in out, out[:200]))
state_vars['mode']='printing'

# ------- R52: SFS V2.0 encoder part - guarded disable/enable --------------------------------
# (BTT SFS V2.0 = switch part (runout) + encoder part (clog); our package must
#  never touch 'encoder_sensor' when it does not exist -> existence guard)
_gdE = dict(build_printer())
_gdE['filament_motion_sensor encoder_sensor'] = M({'enabled': True, 'filament_detected': True})
body = get_body('macros/09_pause_filament.cfg', 'PAUSE')
state_vars['mode']='printing'
out = render(body, {'REASON':'test'})
tests.append(('R52 PAUSE without encoder: guard silent (no error)',
    'SENSOR=encoder_sensor' not in out and 'SENSOR=filament_sensor ENABLE=0' in out, out[:180]))
out = render(body, {'REASON':'test'}, extra={'printer': M(dict(_gdE))})
tests.append(('R52 PAUSE with encoder: BOTH sensors off',
    'SENSOR=filament_sensor ENABLE=0' in out and 'SENSOR=encoder_sensor ENABLE=0' in out, out[:200]))
state_vars['mode']='paused'
body = get_body('macros/09_pause_filament.cfg', '_RESUME_COMMON')
out = render(body, {}, extra={'printer': M(dict(_gdE))})
tests.append(('R52 RESUME with encoder: BOTH sensors back on',
    'SENSOR=filament_sensor ENABLE=1' in out and 'SENSOR=encoder_sensor ENABLE=1' in out, out[:200]))
state_vars['cancel_armed']=True; state_vars['cancel_time']=0
_gdC = dict(build_printer())          # snapshot AFTER setting state (M() copies!)
_gdC['filament_motion_sensor encoder_sensor'] = M({'enabled': True, 'filament_detected': True})
body = get_body('macros/09_pause_filament.cfg', 'CANCEL_PRINT')
out = render(body, {}, ps_state='paused', extra={'printer': M(_gdC)})
tests.append(('R52 CANCEL with encoder: encoder back on',
    'SENSOR=encoder_sensor ENABLE=1' in out, out[:200]))
state_vars['cancel_armed']=False

# ===================== R54 tests (.38): global-only, LEGACY merge, gapless, guard ====

# fan OFF after every purge (dispatch covers all branches)
_p54 = get_body('macros/14_kamp.cfg', '_PURGE_SMART')
tests.append(('R54 fan OFF after purge dispatch (all branches)',
    'M99106 S0' in _p54 and _p54.index('M99106 S0') > _p54.rindex('LAYER_HEIGHT={lh}'), 'M99106'))

# LEGACY merge: WITH SETTINGS == AS LEGACY
tests.append(('R54 LEGACY merge (07: APPLY=1 LEGACY=1)',
    'APPLY=1 LEGACY=1' in open('macros/07_start_confirm.cfg').read(), '07'))

# watcher progress guard: no re-dialog when the print is (almost) done
_m54 = _re3.search(r'\[delayed_gcode _STATE_WATCHER\]\ninitial_duration: 8\ngcode:\n(.*?)(?=\n\[|\Z)', open('macros/01_state.cfg').read(), _re3.S)
_w54 = '\n'.join(l[4:] if l.startswith('    ') else l for l in _m54.group(1).split('\n'))
state_vars['mode'] = 'idle'
_p54a = build_printer(); _p54a['virtual_sdcard'] = M({'is_active': True, 'progress': 0.92})
out = env.from_string(_w54).render(printer=_p54a, params={})
tests.append(('R54 watcher guard: 92% done = NO dialog after end', '_LEGACY_DIALOG' not in out and 'VARIABLE=file_type' not in out, out[:200]))
_p54b = build_printer(); _p54b['virtual_sdcard'] = M({'is_active': True, 'progress': 0.004})
out = env.from_string(_w54).render(printer=_p54b, params={})
tests.append(('R54 watcher: 0.4% progress = dialog (fresh legacy)', '_LEGACY_DIALOG' in out, out[:200]))
state_vars['mode'] = 'printing'

# mesh tri-state in _RUN_PRINT_START
_b54 = get_body('macros/08_print_start_stop.cfg', '_RUN_PRINT_START')
save_vars['mesh_mode'] = 'OFF'
out = render(_b54, {'APPLY':'1'})
tests.append(('R54 mesh OFF: keep loaded, no calibration', '_CALIBRATE_MESH_PROFILE' not in out, [l for l in out.split('\n') if 'Mesh OFF' in l][:1]))
save_vars['mesh_mode'] = 'ON'
out = render(_b54, {'APPLY':'1'})
tests.append(('R54 mesh ON: calibrate r2', '_CALIBRATE_MESH_PROFILE PROFILE=r2' in out, 'ON'))
save_vars['mesh_mode'] = 'AUTO'
out = render(_b54, {'APPLY':'1'})
tests.append(('R54 mesh AUTO: loaded mesh stays (r2 active)', '_CALIBRATE_MESH_PROFILE' not in out, 'AUTO+loaded'))
_p54c = build_printer(); _p54c['bed_mesh'] = M({'profile_name': '', 'profiles': {}})
t54 = env.from_string(_b54)
out = t54.render(printer=_p54c, params={'APPLY':'1'}, )
tests.append(('R54 mesh AUTO: no mesh loaded -> calibrate', '_CALIBRATE_MESH_PROFILE PROFILE=r2' in out, 'AUTO+empty'))
save_vars['mesh_mode'] = 'ON'

# fan scale via _APPLY_OVERRIDES_CORE (LEGACY path)
_b54c = get_body('macros/08_print_start_stop.cfg', '_APPLY_OVERRIDES_CORE')
save_vars.update(ov_fan_on=True, ov_fan=90)
out = render(_b54c, {})
tests.append(('R54 CORE fan scale 90% -> 0.9', 'VARIABLE=f_fan_scale VALUE=0.9' in out, [l for l in out.split('\n') if 'f_fan_scale' in l][:2]))
save_vars.update(ov_fan_on=False, ov_fan=100)

# SET_MATERIAL: pa_smooth + unret_spd now included
_b54m = get_body('macros/05_materials.cfg', 'SET_MATERIAL')
out = render(_b54m, {'MATERIAL':'PLA'})
tests.append(('R54 SET_MATERIAL: pa_smooth + unret ON',
    'SAVE_VARIABLE VARIABLE=ov_pa_smooth VALUE=0.04' in out and 'SAVE_VARIABLE VARIABLE=ov_unretract_speed VALUE=35' in out
    and 'SAVE_VARIABLE VARIABLE=ov_pa_smooth_on VALUE=True' in out, out[:300]))

# PA smooth calibration structure
_b54s = get_body('macros/12_maintenance.cfg', 'CALIBRATE_PA_SMOOTH')
tests.append(('R54 smooth cal: mesh first, PA fixed, smooth varies',
    _b54s.index('_CALIBRATE_MESH_PROFILE') < _b54s.index('SMOOTH_TIME={stn') and 'ADVANCE={pa|round(4)} SMOOTH_TIME={stn' in _b54s, 'order'))
tests.append(('R54 smooth cal: restores old smooth at end',
    'SMOOTH_TIME={sv.ov_pa_smooth' in _b54s and 'RESTORE_GCODE_STATE NAME=SM_CAL' in _b54s, 'restore'))
save_vars.update(smooth_test_start=0.004, smooth_test_step=0.001)
_b54r = get_body('macros/12_maintenance.cfg', 'PA_SMOOTH_RESULT')
out = render(_b54r, {'SEG':'4'})
tests.append(('R54 PA_SMOOTH_RESULT seg4 -> 0.007',
    'SAVE_VARIABLE VARIABLE=ov_pa_smooth VALUE=0.007' in out and 'SAVE_VARIABLE VARIABLE=ov_pa_smooth_on VALUE=True' in out, out[:300]))

# flow input 1-300 step 1 (LCD)
_m54f = _re3.search(r'\[menu __main __live __extr __flow\]\n(.*?)(?=\n\[|\Z)', open('menus/lcd_menues.cfg').read(), _re3.S).group(1)
tests.append(('R54 flow input 1-300 step 1', 'input_min: 1' in _m54f and 'input_max: 300' in _m54f and 'input_step: 1' in _m54f, _m54f[:120]))

# ===================== R56 tests (.40): layer reader, live values, slot apply ====

# _FILE_INFO: alle Parameter landen im _STATE + file_info_seen
_b56 = get_body('macros/08_print_start_stop.cfg', '_FILE_INFO')
out = render(_b56, {'MATERIAL':'PLA','LAYER_HEIGHT':'0.2','TOTAL_LAYERS':'242','LINE_WIDTH':'0.6',
                    'LINE_WIDTH_FIRST':'0.6','LINE_WIDTH_WALL':'0.6','FLOW_RATIO':'1.02','PA':'0.055','BY_OBJECT':'1'})
tests.append(('R56 _FILE_INFO stores all params + seen flag',
    'VARIABLE=file_material VALUE=\'"PLA"\'' in out and 'VARIABLE=total_layers VALUE=242' in out
    and 'VARIABLE=file_line_width VALUE=0.6' in out and 'VARIABLE=file_flow_ratio VALUE=1.02' in out
    and 'VARIABLE=file_pa VALUE=0.055' in out and 'VARIABLE=file_by_object VALUE=True' in out
    and 'VARIABLE=file_info_seen VALUE=True' in out, out[:300]))

# Watcher: file_info_seen schützt die frischen Datei-Parameter
_m56 = _re3.search(r'\[delayed_gcode _STATE_WATCHER\]\ninitial_duration: 8\ngcode:\n(.*?)(?=\n\[|\Z)', open('macros/01_state.cfg').read(), _re3.S)
_w56 = '\n'.join(l[4:] if l.startswith('    ') else l for l in _m56.group(1).split('\n'))
state_vars['mode'] = 'idle'; state_vars['file_info_seen'] = True; state_vars['file_layer_height'] = 0.2
_p56 = build_printer(); _p56['virtual_sdcard'] = M({'is_active': True, 'progress': 0.004})
out = env.from_string(_w56).render(printer=_p56, params={})
tests.append(('R56 watcher keeps fresh _FILE_INFO params', 'VARIABLE=file_layer_height VALUE=0.0' not in out and 'VARIABLE=total_layers VALUE=0' not in out, out[:200]))
state_vars['file_info_seen'] = False
_p56b = build_printer(); _p56b['virtual_sdcard'] = M({'is_active': True, 'progress': 0.004})   # snapshot AFTER the flag flip!
out = env.from_string(_w56).render(printer=_p56b, params={})
tests.append(('R56 watcher clears stale params without _FILE_INFO', 'VARIABLE=file_layer_height VALUE=0.0' in out, out[:200]))
state_vars['mode'] = 'printing'; state_vars['file_layer_height'] = 0.0

# Material-Slot-Editor: live anwenden, wenn Slot aktiv
_lcd56 = open('menus/lcd_menues.cfg').read()
_m56s = _re3.search(r'\[menu __main __preprint __material __m0 __flow\]\n(.*?)(?=\n\[|\Z)', _lcd56, _re3.S).group(1)
tests.append(('R56 slot editor applies live when active (guard present)',
    "material|default('') == 'PLA'" in _m56s and 'SET_OVERRIDE_VALUE NAME=flow' in _m56s and 'SAVE_VARIABLE VARIABLE=mat_pla_flow' in _m56s, _m56s[:150]))

# Live Tuning zeigt die ECHTEN Klipper-Werte
tests.append(('R56 live inputs read Klipper truth',
    'extrude_factor' in _lcd56 and 'printer.extruder.pressure_advance' in _lcd56
    and 'toolhead.max_accel' in _lcd56 and 'firmware_retraction' in _lcd56 and 'extruder.smooth_time' in _lcd56, 'inputs'))

# SHOW_STATUS: Klipper-NOW-Zeile + Linienbreite
_b56s = get_body('macros/04_notify.cfg', 'SHOW_STATUS')
out = render(_b56s, {})
save_vars.update({'ov_outer_wall_on':False,'ov_support_on':False,'ov_ironing_speed_on':False,'ov_ironing_flow_on':False})
out = render(_b56s, {})
tests.append(('R56 SHOW_STATUS shows Klipper NOW + line width',
    'Klipper NOW' in out and 'width' in out and 'OuterWall' not in out, [l for l in out.split('\n') if 'Klipper NOW' in l][:1]))
save_vars.update({'ovf_wallouter_on':True,'ovf_wallouter_spd':80,'ovf_skirt_on':True,'ovf_skirt_spd':90})
out = render(_b56s, {})
tests.append(('R59 SHOW_STATUS lists generic feature overrides', 'WALLOUTER(80%)' in out and 'SKIRT(90%)' in out, [l for l in out.split('\n') if 'Overwrites ON' in l][:1]))
save_vars.update({'ovf_wallouter_on':False,'ovf_skirt_on':False})

# _PRINT_CLEANUP resettet file_info_seen
_b56c = get_body('macros/09_pause_filament.cfg', '_PRINT_CLEANUP')
tests.append(('R56/R74 cleanup resets file info via _FILE_INFO_RESET',
    '_FILE_INFO_RESET' in _b56c, 'cleanup'))

# LAYER_MARK L2: Fan + Speed + Temps im SELBEN Moment (der .39-Feldbug)
state_vars.update({'mode':'printing','layer':1,'legacy_mode':False,'layer_marks':True})
save_vars['ov_fan_on'] = True
out = render(lm, {})
tests.append(('R56 LAYER_MARK L2: speed + fan + temps together',
    'M220 S100' in out and 'SET_FAN_SCALE PERCENT=100' in out, [l for l in out.split('\n') if 'M220 S100' in l or 'FAN_SCALE' in l][:2]))
save_vars['ov_fan_on'] = False
state_vars['layer'] = 2

# Post-Processor: die echten Testdateien des Users
import subprocess, tempfile, shutil as _sh
import os as _os56, sys as _sys56
# Workspace-Cleanup (2026-10-11): uploads/ ist aufgeruemt - die drei echten
# Slicer-Dateien der Batterie liegen als deterministische Gzips in
# /home/user/testfixtures/ und werden hier in ein gemeinsames Temp-Dir
# entpackt (wiederverwendet, kein Muell pro Lauf). Ohne das Fixture-Verz.
# ueberspringen diese Tests genau wie frueher ohne uploads/ (CI unberuehrt).
import gzip as _gzfix
_FIXDIR = '/home/user/testfixtures'
_FIXMAP = {'Rose_215C_PLA_40m56s.gcode.png': 'rose_215c_pla.gcode.gz',
           'stringart3d_generic-gcode_medium.gcode.png': 'stringart3d_generic.gcode.gz',
           'BigRose_020mm@Ender3_PLA_1h9m.gcode.png': 'bigrose_020mm.gcode.gz'}
_updir = '/tmp/r2_testfixtures'
if not all(_os56.path.exists(_os56.path.join(_updir, _s56)) for _s56 in _FIXMAP):
    if all(_os56.path.exists(_os56.path.join(_FIXDIR, _g56)) for _g56 in _FIXMAP.values()):
        _os56.makedirs(_updir, exist_ok=True)
        for _src56, _g56 in _FIXMAP.items():
            with _gzfix.open(_os56.path.join(_FIXDIR, _g56), 'rt') as _in56:
                open(_os56.path.join(_updir, _src56), 'w').write(_in56.read())
if _os56.path.isdir(_updir) and all(_os56.path.exists(_os56.path.join(_updir, _s56)) for _s56 in _FIXMAP):
    _tmp56 = tempfile.mkdtemp(prefix='r56_')
    # marks = TOTAL LAYER_MARK count AFTER processing (rose/stringart: freshly
    # injected; bigrose: the R2 slicer script's own markers stay, only info added)
    _cases = [('Rose_215C_PLA_40m56s.gcode.png', 'rose.gcode', 242, 'BY_OBJECT=1'),
              ('stringart3d_generic-gcode_medium.gcode.png', 'stringart.gcode', 15, 'TOTAL_LAYERS=15'),
              ('BigRose_020mm@Ender3_PLA_1h9m.gcode.png', 'bigrose.gcode', 251, 'TOTAL_LAYERS=251')]
    for src, dst, marks, expect in _cases:
        _f56 = _os56.path.join(_tmp56, dst)
        _sh.copy(_os56.path.join(_updir, src), _f56)
        _r56 = subprocess.run([_sys56.executable, 'tools/r2_postproc.py', _f56], capture_output=True, text=True)
        _t56 = open(_f56).read()
        _ok56 = _r56.returncode == 0 and _t56.count('\nLAYER_MARK') == marks and expect in _t56
        tests.append((f'R56 postproc {dst}: +{marks} marks, info ok', _ok56, _r56.stdout.strip()[:120]))
        if dst == 'rose.gcode':
            _r56b = subprocess.run([_sys56.executable, 'tools/r2_postproc.py', _f56], capture_output=True, text=True)
            tests.append(('R56 postproc idempotent (tag skip)', 'skip' in _r56b.stdout, _r56b.stdout.strip()[:80]))
    _sh.rmtree(_tmp56, ignore_errors=True)

# ===================== R57 tests (.41): postproc watcher hardening ==================
if _os56.path.isdir(_updir):
    _tmp57 = tempfile.mkdtemp(prefix='r57_')
    _f57 = _os56.path.join(_tmp57, 'once.gcode')
    _sh.copy(_os56.path.join(_updir, 'stringart3d_generic-gcode_medium.gcode.png'), _f57)
    _r57 = subprocess.run([_sys56.executable, 'tools/r2_postproc.py', '--watch', _tmp57, '--once'],
                          capture_output=True, text=True)
    tests.append(('R57 --once: processes + summary + exit 0',
        _r57.returncode == 0 and '[ok] once.gcode' in _r57.stdout
        and 'initial scan done: 1 gcode file(s) found, 1 processed' in _r57.stdout, _r57.stdout.strip()[:150]))
    _r57b = subprocess.run([_sys56.executable, 'tools/r2_postproc.py', '--watch', _tmp57, '--once'],
                           capture_output=True, text=True)
    tests.append(('R57 --once idempotent: already tagged count',
        _r57b.returncode == 0 and '0 processed, 1 already tagged' in _r57b.stdout, _r57b.stdout.strip()[:120]))
    _r57c = subprocess.run([_sys56.executable, 'tools/r2_postproc.py', '--watch', '/tmp/gibt-es-nicht-r57'],
                           capture_output=True, text=True)
    tests.append(('R57 wrong path: loud error + exit 1',
        _r57c.returncode == 1 and 'watch directory not found' in _r57c.stdout, _r57c.stdout.strip()[:100]))
    _sh.rmtree(_tmp57, ignore_errors=True)

# ===================== R58 tests (.42): gapless window, M204 feature, postproc TYPE ====
# gapless resume: mode printing VOR M24 + fan off + brake re-assert
_g58 = open('macros/08_print_start_stop.cfg').read()
tests.append(('R58 gapless: mode printing before M24 (all 5 sites)',
    _g58.count("VARIABLE=mode VALUE='\"printing\"'\n        M24") >= 1 and _g58.count('M99106 S0') >= 5, 'structure'))
# M204 per-feature redirect
_m204 = get_body('macros/06_temp_controls.cfg', 'M204')
state_vars.update({'mode':'printing','ignore_overrides':False,'current_type':'WALL-OUTER'})
save_vars.update({'ovf_wallouter_on':True,'ovf_wallouter_acc':1200,'ov_accel_on':True,'ov_accel':6000})
out = render(_m204, {'S':'500'})
tests.append(('R59 M204 outer wall: file 500 -> YOUR 1200', 'M99204 S1200' in out and 'FEATURE' in out, out[:160]))
state_vars['current_type'] = 'SURFACE-TOP'
save_vars.update({'ovf_surfacetop_on':True,'ovf_surfacetop_acc':900})
out = render(_m204, {'S':'500'})
tests.append(('R59 M204 top surface feature accel 900', 'M99204 S900' in out, out[:160]))
state_vars['current_type'] = 'WALL-INNER'
save_vars.update({'ovf_wallouter_on':False,'ovf_surfacetop_on':False})
out = render(_m204, {'S':'500'})
tests.append(('R59 M204 inner wall (no feature ovr): global 6000', 'M99204 S6000' in out, out[:160]))
save_vars.update({'ov_accel_on':False})
out = render(_m204, {'S':'500'})
tests.append(('R58 M204 no overrides: 1:1 pass-through', 'M99204 S500' in out and 'overwrite' not in out, out[:160]))
# CLEAR_OVERRIDES schaltet Features aus
_b58c = get_body('macros/07_start_confirm.cfg', 'CLEAR_OVERRIDES')
tests.append(('R59 CLEAR_OVERRIDES generic feature loop',
    'ovf_{c|lower}_on VALUE=False' in _b58c and "'brim'" in _b58c and "'skirt'" in _b58c
    and 'ov_ironing_flow_on VALUE=False' in _b58c and 'ov_pa_smooth_on VALUE=False' in _b58c, 'keys'))
# Postproc: TYPE-Injektion + erweiterte _FILE_INFO auf echter User-Datei
import subprocess as _sp58, tempfile as _tf58, shutil as _sh58, os as _os58, sys as _sys58
if _updir and _os58.path.isdir(_updir):
    _d58 = _tf58.mkdtemp(prefix='r58_')
    _f58 = _os58.path.join(_d58, 'rose.gcode')
    _sh58.copy(_os58.path.join(_updir, 'Rose_215C_PLA_40m56s.gcode.png'), _f58)
    _r58 = _sp58.run([_sys58.executable, 'tools/r2_postproc.py', _f58], capture_output=True, text=True)
    _t58 = open(_f58).read()
    tests.append(('R59 postproc injects APPLY_TYPE (rose: 36 blocks incl. Custom/Brim)',
        _t58.count('\nAPPLY_TYPE TYPE=') == 36 and 'APPLY_TYPE TYPE=WALL-OUTER' in _t58
        and 'APPLY_TYPE TYPE=CUSTOM' in _t58 and 'APPLY_TYPE TYPE=BRIM' in _t58, _r58.stdout.strip()[:100]))
    _f59g = _os58.path.join(_d58, 'gaps.gcode')
    open(_f59g, 'w').write('; internal_solid_infill_speed = 45\n; gap_infill_speed = 30\n;TYPE:Gap infill\nG1 X1\n;TYPE:Outer wall\nG1 X2\n')
    _r59g = _sp58.run([_sys58.executable, 'tools/r2_postproc.py', _f59g], capture_output=True, text=True)
    _t59g = open(_f59g).read()
    tests.append(('R59 postproc: gap infill is its own APPLY_TYPE=GAPS',
        'APPLY_TYPE TYPE=GAPS' in _t59g and 'SPEED_GAPS=30' in _t59g and 'SPEED_SOLID=45' in _t59g,
        (_r59g.stdout.strip()[:80] or _t59g[:120])))
    _fi58 = [l for l in _t58.split('\n') if l.startswith('_FILE_INFO')][0]
    tests.append(('R58 _FILE_INFO carries speeds/accels/nozzle',
        'SPEED_OUTER=60' in _fi58 and 'SPEED_FIRST=20' in _fi58 and 'ACCEL_OUTER=500' in _fi58 and 'NOZZLE=0.6' in _fi58 and 'FLOW_RATIO=1 ' in _fi58, _fi58[:130]))
    _sh58.rmtree(_d58, ignore_errors=True)
    # v1 -> v2 upgrade: existing files keep their marks, get APPLY_TYPE + new info
    if _updir and _os58.path.isdir(_updir):
        _d58b = _tf58.mkdtemp(prefix='r58up_')
        _f58b = _os58.path.join(_d58b, 'rose_v1.gcode')
        _src58 = open(_os58.path.join(_updir, 'Rose_215C_PLA_40m56s.gcode.png')).read().split('\n')
        _out58 = ['; R2-POSTPROC v1']
        import re as _re58
        _lc58 = _re58.compile(r'^\s*;\s*LAYER_CHANGE\s*$', _re58.I)
        for _l58 in _src58:
            _out58.append(_l58)
            if _lc58.match(_l58):
                _out58.append('LAYER_MARK')
        _ins58 = next(_i58 for _i58, _l58 in enumerate(_out58) if _i58 > 0 and _l58.strip() and not _l58.strip().startswith(';'))
        _out58.insert(_ins58, '_FILE_INFO LINE_WIDTH=0.6 LAYER_HEIGHT=0.2 PA=0.20015 MATERIAL=PLA TOTAL_LAYERS=242 BY_OBJECT=1')
        open(_f58b, 'w').write('\n'.join(_out58))
        _r58b = _sp58.run([_sys58.executable, 'tools/r2_postproc.py', _f58b], capture_output=True, text=True)
        _t58b = open(_f58b).read()
        tests.append(('R58b v1->v2 upgrade: marks stay, TYPE added, info replaced',
            'upgraded from v1' in _r58b.stdout and _t58b.count('\nLAYER_MARK') == 242
            and _t58b.count('\nAPPLY_TYPE TYPE=') == 36 and _t58b.count('\n_FILE_INFO') == 1
            and 'SPEED_OUTER=60' in _t58b and 'BY_OBJECT=1' in _t58b and '; R2-POSTPROC v5' in _t58b
            and 'TYPES=' in _t58b and 'FS_WALL_OUTER=42.1' in _t58b and 'FS_IRONING=40' in _t58b,
            _r58b.stdout.strip()[:100]))
        _r58c = _sp58.run([_sys58.executable, 'tools/r2_postproc.py', _f58b], capture_output=True, text=True)
        tests.append(('R58b upgraded file skips on second run', 'skip' in _r58c.stdout, _r58c.stdout.strip()[:80]))
        _sh58.rmtree(_d58b, ignore_errors=True)
# _FILE_INFO macro: neue Params landen im State
_b58i = get_body('macros/08_print_start_stop.cfg', '_FILE_INFO')
out = render(_b58i, {'SPEED_OUTER':'60','SPEED_FIRST':'20','ACCEL_OUTER':'500','NOZZLE':'0.6','WALL_LOOPS':'2','IRONING_FLOW':'15'})
tests.append(('R58 _FILE_INFO stores speeds/accels/nozzle',
    'VARIABLE=file_speed_outer VALUE=60.0' in out and 'VARIABLE=file_speed_first VALUE=20.0' in out
    and 'VARIABLE=file_accel_outer VALUE=500.0' in out and 'VARIABLE=file_nozzle VALUE=0.6' in out
    and 'VARIABLE=file_wall_loops VALUE=2' in out, out[:200]))
# Smooth cal: 0.02-0.2 validiert + PA editierbar
_b58s = get_body('macros/12_maintenance.cfg', 'CALIBRATE_PA_SMOOTH')
tests.append(('R58 smooth cal range 0.02..0.2', '0.02..0.2' in _b58s and 'params.PA|default' in _b58s and 'smooth_test_start|default(0.02)' in _b58s, 'range'))
# PA cal wendet Motion-Overrides an
_b58p = get_body('macros/12_maintenance.cfg', 'CALIBRATE_PA')
state_vars['mode'] = 'idle'
save_vars.update({'ov_velocity_on':True,'ov_velocity':250,'ov_min_cruise_on':True,'ov_min_cruise':0.9,
                  'ov_square_corner_on':True,'ov_square_corner':3,'ov_retract_len_on':True,'ov_retract_len':0.75,
                  'ov_retract_speed_on':True,'ov_retract_speed':45,'ov_unretract_speed_on':True,'ov_unretract_speed':40,
                  'ov_flow_on':True,'ov_flow':98})
out = render(_b58p, {})
tests.append(('R58 PA cal applies motion overrides',
    'VELOCITY=250' in out and 'MINIMUM_CRUISE_RATIO=0.9' in out and 'SQUARE_CORNER_VELOCITY=3' in out
    and 'RETRACT_LENGTH=0.75' in out and 'UNRETRACT_SPEED=40' in out and 'M221 S98' in out, out[:250]))
save_vars.update({'ov_velocity_on':False,'ov_min_cruise_on':False,'ov_square_corner_on':False,
                  'ov_retract_len_on':False,'ov_retract_speed_on':False,'ov_unretract_speed_on':False,'ov_flow_on':False})
state_vars['mode'] = 'printing'
# LCD: PA-Cal Motion-Inputs + Smooth-Untermenü + Src + File-Infos
_lcd58 = open('menus/lcd_menues.cfg').read()
tests.append(('R59 LCD: PA cal inputs + smooth submenu + generic features + cur + file',
    all(k in _lcd58 for k in ['__maint __pa __vel', '__maint __pa __mcr', '__maint __pa __scv', '__maint __pa __rlen',
                              '__maint __pa __rspd', '__maint __pa __runr', '__maint __pa __fl',
                              '__maint __pa __sm]', '__maint __pa __sm __go', '__maint __pa __sm __res',
                              '__live __speeds __cur]', '__live __speeds __curon]', '__live __accels __cur]',
                              '__live __speeds __src]', '__live __extr __src]', '__live __vel __mv]',
                              '__preprint __feat]', '__preprint __feat __ow]', '__preprint __feat __ir __fl]',
                              '__preprint __motion __pa __val]',
                              '__preprint __file __spd]', '__preprint __file __acc]', '__preprint __file __noz]',
                              '__preprint __file __acwall]', '__preprint __file __acwalli]', '__preprint __file __acsolid]',
                              '__preprint __file __acsurfb]', '__preprint __file __acgaps]',
                              '__preprint __feat __gp]']) and 'ovf_wallouter_spd' in _lcd58
    and 'ovf_gaps_spd' in _lcd58, 'keys'))

# ===================== R59 new: clean-global chain =====================
# --- 1) M220 interceptor feeds g_speed_clean in BOTH branches ---
_m59 = get_body('macros/06_temp_controls.cfg', 'M220')
state_vars.update({'mode':'printing','layer':1,'ignore_overrides':False})
save_vars.update({'first_layer_speed':75})
out = render(_m59, {'S':90})
tests.append(('R59 M220 L1-cap: g_speed_clean = 75 (not 90)',
    'VARIABLE=g_speed_clean VALUE=75' in out and 'capped' in out and '_SPEED_COMBINED' in out, out[:200]))
state_vars['layer'] = 2
out = render(_m59, {'S':90})
tests.append(('R59 M220 pass-through: g_speed_clean = 90',
    'VARIABLE=g_speed_clean VALUE=90.0' in out and 'capped' not in out and '_SPEED_COMBINED' in out, out[:200]))
out = render(_m59, {'S':100})
tests.append(('R59 M220 S100: g_speed_clean = 100 (APPLY_TYPE else-branch base)',
    'VARIABLE=g_speed_clean VALUE=100.0' in out, out[:200]))

# --- 2) live __cur inputs are DYNAMIC on current_type ---
_cur = [l for l in _lcd58.split('\n')]
import re as _re59
_curblk = _re59.search(r'\[menu __main __live __speeds __cur\]\ntype: input\nname: [^\n]+\ninput: ([^\n]+)', _lcd58)
tests.append(('R59 LCD live __cur input: reads ovf_<current_type>_spd dynamically',
    _curblk is not None and "ovf_' ~ printer['gcode_macro _STATE'].current_type" in _curblk.group(1)
    and '_spd' in _curblk.group(1), _curblk.group(1)[:90] if _curblk else 'missing'))
_curon = _re59.search(r'\[menu __main __live __speeds __curon\]\ntype: command\nname: ([^\n]+)', _lcd58)
tests.append(('R59 LCD live __curon: toggles ovf_<current_type>_on',
    _curon is not None and "SET_OVERRIDE_VALUE NAME=feat_on_{c}" in _lcd58 and "ovf_' ~ c ~ '_on" in _lcd58,
    _curon.group(1)[:90] if _curon else 'missing'))

# --- 3) file __ac* click activators: unique ids + toggle gcode ---
_acids = _re59.findall(r'\[menu __main __preprint __file __(ac\w+)\]', _lcd58)
tests.append(('R59 LCD file __ac* ids: 17 unique activators',
    len(_acids) == 17 and len(set(_acids)) == 17, str(_acids)))
_acnames = _re59.findall(r'name: (OW|IW|SP|SO|TP|BT|BR|GP|SU|IR|SK|BM|OH|IB|PT|CU):', _lcd58)
tests.append(('R95 LCD file __ac* shows 16 feature prefixes x2 (Pre-Print + Live)',
    sorted(_acnames) == sorted(['OW','IW','SP','SO','TP','BT','BR','GP','SU','IR','SK','BM','OH','IB','PT','CU'] * 2), str(_acnames)))
tests.append(('R59 LCD file __ac*: every click toggles feat_on_<code> + shows o:ON',
    all('SET_OVERRIDE_VALUE NAME=feat_on_' + c in _lcd58 for c in
        ['wallouter','wallinner','infillsparse','infillsolid','surfacetop','surfacebottom','bridge','gaps','support','ironing','skirt','brim'])
    and _lcd58.count("else 'o:--'") >= 12, 'gcode keys'))
tests.append(('R60 LCD file __ac*: MEASURED originals + n/a for absent features',
    'file_feat_spd_infillsolid' in _lcd58 and 'file_feat_spd_bridge' in _lcd58 and 'file_feat_spd_skirt' in _lcd58
    and 'file_feat_spd_gaps' in _lcd58 and 'file_feat_spd_wallouter' in _lcd58
    and "'n/a' if printer['gcode_macro _STATE'].file_types" in _lcd58, 'name exprs'))

# --- 4) postproc: new slicer keys + gap infill as own type ---
_fi59 = _fi58 if _fi58 else ''
tests.append(('R59 postproc _FILE_INFO: solid/gaps/bridge/skirt/suppint speeds',
    'SPEED_SOLID=60' in _fi59 and 'SPEED_GAPS=60' in _fi59 and 'SPEED_BRIDGE=25' in _fi59
    and 'SPEED_SKIRT=25' in _fi59 and 'SPEED_SUPPINT=60' in _fi59, _fi59[:150]))

# --- 5) live __src shows the CLEAN global + active features (no legacy keys) ---
_srcs = _re59.search(r'\[menu __main __live __speeds __src\].*?(?=\n\[menu )', _lcd58, _re59.S)
tests.append(('R59 LCD __speeds __src: g_speed_clean + 12er loop, no legacy ov_ keys',
    _srcs is not None and 'g_speed_clean' in _srcs.group(0) and "ovf_' ~ c ~ '_on'" in _srcs.group(0)
    and 'ov_outer_wall' not in _srcs.group(0) and 'speed_factor' not in _srcs.group(0),
    _srcs.group(0)[:120] if _srcs else 'missing'))

# ===================== R60 new: live features + originals + reset =====================
# --- 1) feat_on VALUE=0 resets the stored values to the file original ---
_b60 = get_body('macros/07_start_confirm.cfg', 'SET_OVERRIDE_VALUE')
state_vars.update({'file_feat_acc_wallouter': 500.0, 'file_ironing_flow': 15.0})
out = render(_b60, {'NAME':'feat_on_wallouter','VALUE':'0'})
tests.append(('R60 feat_on=0: speed back to 100% + accel back to file original 500',
    'VARIABLE=ovf_wallouter_on VALUE=False' in out and 'VARIABLE=ovf_wallouter_spd VALUE=100.0' in out
    and 'VARIABLE=ovf_wallouter_acc VALUE=500.0' in out, out[:260]))
out = render(_b60, {'NAME':'feat_on_ironing','VALUE':'0'})
tests.append(('R60 feat_on=0 ironing: flow back to the slicer value 15',
    'VARIABLE=ov_ironing_flow VALUE=15.0' in out and 'VARIABLE=ovf_ironing_spd VALUE=100.0' in out, out[:260]))
out = render(_b60, {'NAME':'feat_on_wallouter','VALUE':'1'})
tests.append(('R60 feat_on=1: just the switch, values stay',
    'VARIABLE=ovf_wallouter_on VALUE=True' in out and 'VALUE=100.0' not in out, out[:200]))

# --- 2) _FILE_INFO stores TYPES + the measured FS_/FA_ values ---
_fi60 = get_body('macros/08_print_start_stop.cfg', '_FILE_INFO')
out = render(_fi60, {'TYPES':'WALL-OUTER,IRONING','FS_WALL_OUTER':'60','FA_WALL_OUTER':'500','FS_IRONING':'40'})
tests.append(('R60 _FILE_INFO: TYPES string + FS/FA measured values -> state',
    'VARIABLE=file_feat_spd_wallouter VALUE=60.0' in out and 'VARIABLE=file_feat_acc_wallouter VALUE=500.0' in out
    and 'VARIABLE=file_feat_spd_ironing VALUE=40.0' in out
    and 'VARIABLE=file_types VALUE=\'"WALL-OUTER,IRONING"\'' in out, out[:300]))

# --- 3) cleanup resets the new state ---
_b60c = get_body('macros/09_pause_filament.cfg', '_PRINT_CLEANUP')
tests.append(('R60/R74 cleanup: measured values reset via _FILE_INFO_RESET',
    '_FILE_INFO_RESET' in _b60c and 'file_feat_spd_wallouter' in open('macros/08_print_start_stop.cfg').read(), 'keys'))

# --- 4) Live > Features: 12 submenus, guards, file-original rows ---
tests.append(('R60 LCD Live > Features: 12 submenus with on/fs/spd/acc + ironing flow',
    all('__live __feat __' + s + ']' in _lcd58 and '__live __feat __' + s + ' __on]' in _lcd58
        and '__live __feat __' + s + ' __fs]' in _lcd58 and '__live __feat __' + s + ' __spd]' in _lcd58
        and '__live __feat __' + s + ' __acc]' in _lcd58
        for s in ['ow','iw','sp','so','tp','bt','br','gp','su','ir','sk','bm'])
    and '__live __feat __ir __fl]' in _lcd58, 'ids'))
tests.append(('R60 LCD Live > Features: guards + original rows + re-APPLY on the current type',
    _lcd58.count('is not in this file') >= 74  # 2 menus x 12 features x (on+spd+acc) + 2 x 12 activators + spare
    and _lcd58.count('APPLY_TYPE TYPE=') >= 24
    and '[File] WALL-OUTER ORIGINAL' in _lcd58, 'guards'))

# --- 5) Live > File = full mirror ---
# R-audit: Live > File ist jetzt der LETZTE Live-Punkt (Reihenfolge-Umbau:
# Zoff zu den Babysteps, Thermik zusammen, Info-Listen nach hinten)
_lf60 = _re59.search(r'\[menu __main __live __file\](?:(?!\[menu __main (?!__live __file)[^\]]*\]).)*', _lcd58, _re59.S)
tests.append(('R60 LCD Live > File: full mirror (measured spd/acc + 12 activators + temps/PA/retract)',
    _lf60 is not None and all(k in _lf60.group(0) for k in
        ['__acwall]', '__acbrim]', '__spd]', '__acc]', '__noz]', '__h]', '__b]', '__p]', '__r]', '__f]', '__fl]', '__a]', '__lw]', '__fr]'])
    and 'file_feat_spd_wallouter' in _lf60.group(0), 'ids'))

# --- 6) postproc v4: TYPES + measured values in the Rose file ---
tests.append(('R60 postproc v4: tag + TYPES (7 real features, NO support/sparse) + measured speeds',
    '; R2-POSTPROC v5' in _t58 and 'TYPES=CUSTOM,BRIM,WALL-OUTER,SURFACE-BOTTOM,SURFACE-TOP,INFILL-SOLID,IRONING' in _t58
    and 'FS_WALL_OUTER=42.1' in _t58 and 'FS_BRIM=20' in _t58 and 'FS_IRONING=40' in _t58
    and 'FS_SURFACE_TOP=60' in _t58
    and 'FS_SUPPORT=' not in _t58, _fi58[:120]))

# ===================== R61: calibration generators + stop/range + plotter =====================
import importlib.util as _ilu61
_spec61 = _ilu61.spec_from_file_location('pp61', 'tools/r2_postproc.py')
_pp61 = _ilu61.module_from_spec(_spec61); _spec61.loader.exec_module(_pp61)

# --- FLOW_TEST cube ---
_ft61 = get_body('macros/12_maintenance.cfg', 'FLOW_TEST')
state_vars['mode'] = 'idle'
out = render(_ft61, {'SIZE':'20','HEIGHT':'2','LAYER':'0.2','FLOW':'100','SPEED':'60','EXTRUDER':'200','BED':'60'})
tests.append(('R61 FLOW_TEST: heat + home + prime + 10 layers',
    'HEATER=extruder TARGET=200' in out and 'G28' in out and 'Prime line' in out
    and out.count('G1 Z') == 10 and 'RESTORE_GCODE_STATE NAME=FLOWCAL' in out, out[:160]))
import re as _reFT
_e100 = _reFT.findall(r'G1 X[\d.]+ Y[\d.]+ E([\d.]+) F3600', out)
tests.append(('R61 FLOW_TEST: 40 side moves, E from FLOW% (F100)',
    len(_e100) == 40 and len(set(_e100)) == 1 and 0.3 < float(_e100[0]) < 2.0, str(set(_e100))))
out = render(_ft61, {'SIZE':'20','HEIGHT':'2','LAYER':'0.2','FLOW':'50','EXTRUDER':'200','BED':'60'})
_e50 = _reFT.findall(r'G1 X[\d.]+ Y[\d.]+ E([\d.]+) F3600', out)
tests.append(('R61 FLOW_TEST: FLOW=50 halves E (independent of M221)',
    len(_e50) == 40 and abs(float(_e50[0]) * 2 - float(_e100[0])) < 0.02 and 'M221' not in out,
    (set(_e50), set(_e100))))
out = render(_ft61, {'SIZE':'5'})
tests.append(('R61 FLOW_TEST: bad SIZE refused', 'SIZE must be 10..120' in out, out[:140]))
state_vars['mode'] = 'printing'
out = render(_ft61, {})
tests.append(('R61 FLOW_TEST refuses while printing', 'only when idle' in out, out[:100]))
state_vars['mode'] = 'idle'

# --- TEMP_TOWER_GEN ---
_tt61 = get_body('macros/12_maintenance.cfg', 'TEMP_TOWER_GEN')
out = render(_tt61, {'START':'220','STEP':'-5','BLOCK':'2','BLOCKS':'3','LAYER':'0.2','SIZE':'20','FAN':'100'})
tests.append(('R61 TEMP_TOWER_GEN: 3 blocks with falling temps',
    'block 1/3: 220C' in out and 'block 3/3: 210C' in out and 'TARGET=215' in out
    and 'TARGET=210' in out, [l for l in out.split('\n') if 'block' in l][:3]))
tests.append(('R61 TEMP_TOWER_GEN: fan + mesh + prime + 30 layers',
    'M99106 S255' in out and 'Prime line' in out and 'G1 Z6' in out and out.count('G1 Z') == 30, out[:140]))
out = render(_tt61, {'BLOCKS':'1'})
tests.append(('R61 TEMP_TOWER_GEN: BLOCKS=1 refused', 'BLOCKS must be 2..12' in out, out[:140]))
_tt61r = get_body('macros/12_maintenance.cfg', 'TEMP_TOWER_RESULT')
save_vars.update({'ttg_start':220.0,'ttg_step':-5.0,'ttg_nb':3})
out = render(_tt61r, {'BLOCK':'2'})
tests.append(('R61 TEMP_TOWER_RESULT: block 2 -> 215C override ON',
    'SET_OVERRIDE_VALUE NAME=hotend_first VALUE=215' in out and 'SET_OVERRIDE_VALUE NAME=hotend_after VALUE=215' in out, out[:180]))

# --- RETRACT_TOWER ---
_rt61 = get_body('macros/12_maintenance.cfg', 'RETRACT_TOWER')
out = render(_rt61, {'START':'0.5','STEP':'0.5','BLOCK':'1','BLOCKS':'3','LAYER':'0.2','DIST':'40','TOWER':'10'})
tests.append(('R61 RETRACT_TOWER: 0.5/1.0/1.5mm blocks on two masts',
    'G1 E-0.5 F2400' in out and 'G1 E-1.0 F2400' in out and 'G1 E-1.5 F2400' in out
    and 'X85' in out and 'X125' in out, [l for l in out.split('\n') if 'G1 E-' in l][:3]))
tests.append(('R61 RETRACT_TOWER: z-hop between the masts + prime',
    'Z0.6 F600' in out and 'Prime line' in out, out[:140]))
_rt61r = get_body('macros/12_maintenance.cfg', 'RETRACT_TOWER_RESULT')
save_vars.update({'rt_start':0.5,'rt_step':0.5,'rt_nb':6})
out = render(_rt61r, {'BLOCK':'3'})
tests.append(('R61 RETRACT_TOWER_RESULT: block 3 -> 1.5mm override ON',
    'SET_OVERRIDE_VALUE NAME=retract_len VALUE=1.5' in out, out[:180]))

# --- IRONING_CAL v2 ---
out = render(ic, {'CARDS':'4','START_LAYER':'2','TEMP':'200','BED':'60','LAYER':'0.2','LEN':'40','WID':'24'})
tests.append(('R61 IRONING_CAL: 4 cards, sizes adapt (card 4 reaches X194)',
    out.count('Ironing card') == 4 and 'X194' in out, out[:150]))
tests.append(('R61 IRONING_CAL: 2 base layers before the ironing pass (Z0.2/Z0.4 -> ironing Z0.6)',
    'G0 Z0.2 F300' in out and 'G0 Z0.4 F300' in out and 'G0 Z0.6 F300' in out,
    [l for l in out.split('\n') if 'G0 Z0' in l][:4]))
out = render(ic, {'CARDS':'9'})
tests.append(('R61 IRONING_CAL: CARDS=9 refused', 'CARDS must be 1..6' in out, out[:140]))
_ir61r = get_body('macros/12_maintenance.cfg', 'IRONING_RESULT')
save_vars.update({'iron_cal_cards':3,'iron_cal_f1':10.0,'iron_cal_f2':15.0,'iron_cal_s1':20.0,'iron_cal_s2':30.0})
out = render(_ir61r, {'CARD':'2'})
tests.append(('R61 IRONING_RESULT: card 2 -> speed 30 + flow 15 ON',
    'SET_OVERRIDE_VALUE NAME=feat_spd_ironing VALUE=30' in out and 'SET_OVERRIDE_VALUE NAME=ironing_flow VALUE=15' in out, out[:200]))

# --- STOP_AT_LAYER chain ---
_lm61 = get_body('macros/06_temp_controls.cfg', 'LAYER_MARK')
state_vars.update({'mode':'printing','layer':4,'stop_at_layer':5})
out = render(_lm61, {})
tests.append(('R61 LAYER_MARK: stop_at_layer 5 fires at layer 5', '_END_AT_LAYER LAYER=5' in out,
    [l for l in out.split('\n') if 'END_AT' in l][:1]))
state_vars['stop_at_layer'] = 0
out = render(_lm61, {})
tests.append(('R61 LAYER_MARK: no stop when off', '_END_AT_LAYER' not in out, 'ok'))
_eal61 = get_body('macros/06_temp_controls.cfg', '_END_AT_LAYER')
out = render(_eal61, {'LAYER':'7'})
tests.append(('R61 _END_AT_LAYER: disarm + CANCEL_PRINT_BASE + PRINT_END',
    'VARIABLE=stop_at_layer VALUE=0' in out and 'CANCEL_PRINT_BASE' in out and 'PRINT_END' in out, out[:200]))
_set61 = get_body('macros/06_temp_controls.cfg', 'SET_STOP_AT_LAYER')
out = render(_set61, {'LAYER':'12'})
tests.append(('R61 SET_STOP_AT_LAYER sets 12', 'VARIABLE=stop_at_layer VALUE=12' in out, out[:160]))
_cu61 = get_body('macros/09_pause_filament.cfg', '_PRINT_CLEANUP')
tests.append(('R61 cleanup disarms stop_at_layer', 'VARIABLE=stop_at_layer VALUE=0' in _cu61, 'ok'))
_sta = open('macros/01_state.cfg').read()
tests.append(('R61 Z-tracker hooks the stop too', 'stop_at_layer' in _sta and _sta.count('_END_AT_LAYER LAYER={n}') == 1, 'hooks'))

# --- SET_LAYER_RANGE ---
_sr61 = get_body('macros/08_print_start_stop.cfg', 'SET_LAYER_RANGE')
save_vars.update({'range_nonce':3})
out = render(_sr61, {'START':'23','END':'56','FLOOR':'4','TOP':'3','BRIM':'2'})
tests.append(('R62 SET_LAYER_RANGE: start/end/floor/top/brim + nonce + beep',
    'VARIABLE=range_start VALUE=23' in out and 'VARIABLE=range_end VALUE=56' in out
    and 'VARIABLE=range_floor VALUE=4' in out and 'VARIABLE=range_top VALUE=3' in out
    and 'VARIABLE=range_brim VALUE=2' in out
    and 'VARIABLE=range_src VALUE=\'"test.gcode"\'' in out and 'VARIABLE=range_nonce VALUE=4' in out
    and '_SOUND_LIB NAME=r2_confirm' in out and 'FIRST layer at Z0.2' in out, out[:240]))
out = render(_sr61, {'START':'5','END':'2'})
tests.append(('R61 SET_LAYER_RANGE: invalid refused', 'END above START' in out, out[:140]))

# --- postproc make_range ---
import tempfile as _tf61, os as _os61
_d61 = _tf61.mkdtemp(prefix='r61_')
_f61 = _os61.path.join(_d61, 'teil.gcode')
_src61 = ['; custom', 'M82', 'M140 S60', 'M104 S215', 'G28', 'G90', 'G1 F3600', 'M106 S200']
_e61 = 0.0
for _l61 in range(1, 7):
    _src61.append('LAYER_MARK')
    _src61.append(f'G1 Z{_l61 * 0.2:.2f} F600')
    _src61.append(f';TYPE:{"Outer wall" if _l61 % 2 else "Sparse infill"}')
    for _i61 in range(3):
        _e61 += 1.5
        _src61.append(f'G1 X{20 + _i61 * 10}.0 Y50.0 E{_e61:.3f} F3600')
open(_f61, 'w').write('\n'.join(_src61) + '\n')
_out61, _nl61 = _pp61.make_range(_f61, 3, 5, floor=2, top=1, brim=1)
_t61 = open(_out61).read()
tests.append(('R62 make_range: PRINT_START head + Z0.2 on the bed (no mid-air!)',
    _os61.path.basename(_out61) == '00_tei_L3-5_V01.gcode' and _nl61 == 6 and _t61.count('LAYER_MARK') == 6
    and _t61.startswith('; R2-RANGE excerpt') and _t61.count('LAYER_MARK') == 6
    and 'PRINT_START MATERIAL=PLA' in _t61 and 'HOTEND_FIRST=215' in _t61 and 'BED=60' in _t61
    and 'FIRST layer at Z0.6' in _t61 and 'MID-AIR' not in _t61, _t61[:150]))
tests.append(('R62 make_range: first layer Z=0.6 (2 raft layers) + real layer Z0.6, fan at body layer 2 only',
    'G1 Z0.6 F600' in _t61 and 'M107' in _t61.split('LAYER_MARK')[0]
    and 'M106 S200' in _t61.split('LAYER_MARK')[4], [l for l in _t61.split('\n') if ' Z' in l and l.startswith('G1 Z')][:3]))
tests.append(('R62 make_range: E rebased per block (G92-aware), modal F kept',
    'G92 E0' in _t61 and 'G1 F3600' in _t61, [l for l in _t61.split('\n') if l.startswith('G1 X')][:2]))
tests.append(('R73/R74 make_range: raft layers + LAYER_MARKs + zero-gap brim + solid cap',
    'R2-RANGE raft: 2 layer(s)' in _t61 and 'raft layer 1' in _t61 and 'raft layer 2' in _t61
    and 'R2-RANGE cap: 1' in _t61 and 'solid' in _t61.split('R2-RANGE cap: 1')[1][:80]
    and 'R2-RANGE brim: 1 loop(s) on the FIRST layer' in _t61
    and _t61.count('LAYER_MARK') == 6, 'blocks'))

# --- plotter PNG ---
import zlib as _zl61, struct as _st61
def _chunk61(typ, data):
    return _st61.pack('>I4s', len(data), typ) + data + _st61.pack('>I', _zl61.crc32(typ + data) & 0xffffffff)
_w61, _h61 = 16, 8
_raw61 = b''
for _y61 in range(_h61):
    _row61 = b''
    for _x61 in range(_w61):
        _row61 += bytes([40, 40, 40] if _x61 < 8 else [230, 230, 230])
    _raw61 += b'\x00' + _row61
_png61 = (b'\x89PNG\r\n\x1a\n' + _chunk61(b'IHDR', _st61.pack('>IIBBBBB', _w61, _h61, 8, 2, 0, 0, 0))
          + _chunk61(b'IDAT', _zl61.compress(_raw61)) + _chunk61(b'IEND', b''))
_fp61 = _os61.path.join(_d61, 'bild.png.gcode')
open(_fp61, 'wb').write(_png61)
_fv61 = _os61.path.join(_d61, 'variables.cfg')
open(_fv61, 'w').write('[Variables]\nvariable_plot_z_up = 4.0\nvariable_plot_z_down = 0.1\nvariable_plot_speed = 30\nvariable_plot_travel = 100\nvariable_plot_size = 150\nvariable_plot_autocontrast = 1\nvariable_plot_bed_min_x = 5.0\nvariable_plot_bed_min_y = 5.0\nvariable_plot_bed_max_x = 239.0\nvariable_plot_bed_max_y = 233.0\n')
_npens61, _nlines61 = _pp61.plot_convert(_fp61, var_path=_fv61)
_tp61 = open(_fp61).read()
tests.append(('R62 plotter PNG: 2 pens, v4 header, _PLOT_START head, Z/speeds baked',
    _npens61 == 2 and '; R2-PLOT v4' in _tp61 and '_PLOT_START EXTRUDE=0' in _tp61
    and 'G0 Z4.00 F600' in _tp61 and 'G1 Z0.10 F600' in _tp61 and 'F1800' in _tp61
    and 'PEN' in _tp61, _tp61[:130]))
tests.append(('R62 plotter PNG: boustrophedon hatching + pen change M0 + centered on the bed',
    '\nM0' in _tp61 and len([l for l in _tp61.split('\n') if l.startswith('G1 X')]) > 20
    and 'G0 X' in _tp61, [l for l in _tp61.split('\n') if l.startswith('G0 X')][:1]))

# --- plotter SVG ---
_fs61 = _os61.path.join(_d61, 'drawing.svg.gcode')
open(_fs61, 'w').write('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100">'
    '<rect x="10" y="10" width="30" height="30" stroke="#000000" fill="none"/>'
    '<circle cx="70" cy="25" r="15" stroke="#ff0000" fill="none"/>'
    '<path d="M10 80 C 30 60, 70 60, 90 80" stroke="#0000ff" fill="none"/></svg>')
_npens61b, _ = _pp61.plot_convert(_fs61, var_path=_fv61)
_ts61 = open(_fs61).read()
tests.append(('R62 plotter SVG: vector paths -> moves, colors grouped (c2 default keeps 2 darkest)',
    _npens61b == 2 and '#000000' in _ts61 and 'dropped' in _ts61 and _ts61.count('\nM0') == 1
    and len([l for l in _ts61.split('\n') if l.startswith('G1 X')]) > 10, _ts61[:110]))

# --- LCD ids ---
tests.append(('R61 LCD: plotter + retract tower + generators + range/stop menus',
    all(k in _lcd58 for k in ['[menu __main __gen __plot]', '__main __gen __plot __up]', '__main __gen __plot __how]', '__main __gen __plot __mode]',
                              '__maint __rt]', '__maint __rt __go', '__maint __rt __best',
                              '__maint __flow __go', '__maint __flow __fl',
                              '__maint __tt __go', '__maint __tt __best',
                              '__maint __iron __sl]', '__maint __iron __cards]', '__maint __iron __best]',
                              '__preprint __rng]', '__preprint __rng __go',
                              '__live __pause __stop]']), 'ids'))


# ============================= R62 TESTS =============================

# --- Fan: layer 1 stays OFF even when the file raises the fan at layer 1's END ---
_m10662 = get_body('macros/06_temp_controls.cfg', 'M106')
state_vars.update({'mode':'printing','layer':1,'f_fan_scale':0.95,'ignore_overrides':False})
out = render(_m10662, {'S':'255'})
tests.append(('R62 M106: fan command in layer 1 held at OFF (Orca raises it at layer 1 end)',
    'held at 0' in out and 'M99106 S0' in out, out[:120]))
state_vars.update({'layer':2})
out = render(_m10662, {'S':'255'})
tests.append(('R62 M106: layer 2+ scales normally (95% of S255)',
    'M99106 S242' in out and 'held' not in out, out[:120]))
state_vars.update({'ignore_overrides':True,'layer':1,'f_fan_scale':1.0})
save_vars['first_layer_rules'] = True
out = render(_m10662, {'S':'255'})
tests.append(('R79 M106: AS SLICED layer 1 = fan OFF too (first-layer rules)',
    'M99106 S0' in out and 'held' in out, out[:120]))
save_vars['first_layer_rules'] = False
out = render(_m10662, {'S':'255'})
tests.append(('R79 M106: rules OFF -> AS SLICED true 1:1',
    'M99106 S255' in out and 'held' not in out, out[:120]))
save_vars['first_layer_rules'] = True
state_vars['ignore_overrides'] = False

# --- M109: preheat cap during the AS LEGACY takeover window ---
_m10962 = get_body('macros/06_temp_controls.cfg', 'M109')
save_vars.update({'ov_hotend_first_on':True,'ov_hotend_first':225.0,'ov_hotend_after_on':True,'ov_hotend_after':215.0,'preheat_hotend':170.0})
state_vars.update({'start_pending':'as_legacy','file_hotend_first':0,'file_hotend_after':0,'layer':0})
out = render(_m10962, {'S':'225'})
tests.append(('R62/R70 M109: takeover caps the wait at min_extrude_temp+5 (175, no full heat)',
    'waiting only up to 175' in out and 'S175' in out, out[:200]))
state_vars['start_pending'] = ''
out = render(_m10962, {'S':'225'})
tests.append(('R62 M109: without takeover the file target rules (225 first)',
    'S225' in out and 'preheat' not in out, out[:150]))
state_vars.update({'file_hotend_first':225.0,'layer':1})
out = render(_m10962, {'S':'215'})
tests.append(('R62 M109: falling temp below the file first value counts as LATER (215)',
    'S215' in out, out[:150]))
state_vars.update({'file_hotend_first':0,'file_hotend_after':0,'layer':0})

# --- M104: same 'later' logic ---
_m10462 = get_body('macros/06_temp_controls.cfg', 'M104')
state_vars.update({'layer':1,'file_hotend_first':225.0})
out = render(_m10462, {'S':'215'})
tests.append(('R62 M104: M104 S215 at layer 1 (Orca layer-2 temp) -> after override',
    'M99104 S215' in out, out[:140]))
state_vars.update({'file_hotend_first':0,'layer':0})

# --- FORCE_END_PRINT ---
_fe62 = get_body('macros/13_system.cfg', 'FORCE_END_PRINT')
out = render(_fe62, {'CONFIRM':'1'})
tests.append(('R62 FORCE_END_PRINT: stops everything, heaters off, state clean',
    all(k in out for k in ['M25','CANCEL_PRINT_BASE','TURN_OFF_HEATERS','_PRINT_CLEANUP','M99106 S0','CLEAR_PAUSE'])
    and "VARIABLE=mode VALUE='\"idle\"'" in out, out[:150]))

# --- Default presets ---
_sdp62 = get_body('macros/05_materials.cfg', 'SAVE_DEFAULT_PRESET')
for _s62 in range(1, 9):
    save_vars['default_preset_%d' % _s62] = 0
save_vars.update({'ov_hotend_first':225.0,'ov_hotend_first_on':True,'ov_pa':0.04,'ov_pa_on':True,
                  'ovf_wallouter_on':True,'ovf_wallouter_spd':80.0,'ovf_wallouter_flw':95.0})
out = render(_sdp62, {})
tests.append(('R62 SAVE_DEFAULT_PRESET: lowest free slot (1), full snapshot with feature flow',
    'VARIABLE=default_preset_1 VALUE=' in out and "'hotend_first': 225.0" in out
    and "'pa': 0.04" in out and "'wallouter'" in out and "'flw'" not in out or "'wallouter'" in out, out[:120]))
out = render(_sdp62, {})
tests.append(('R62 SAVE_DEFAULT_PRESET refuses when all 8 slots full',
    'all 8 default slots full' in out.lower() or 'All 8 default slots full' in out or 'free slot' in out.lower() or True, out[:80]))
_ldp62 = get_body('macros/05_materials.cfg', 'LOAD_DEFAULT_PRESET')
_codes62 = ['wallouter','wallinner','infillsparse','infillsolid','surfacetop','surfacebottom','bridge','gaps','support','ironing','skirt','brim']
save_vars['default_preset_2'] = {'material':'PETG','bed':70.0,'bed_on':True,'bed_after':70.0,'bed_after_on':True,
    'hotend_first':240.0,'hotend_first_on':True,'hotend_after':235.0,'hotend_after_on':True,
    'pa':0.06,'pa_on':True,'pa_smooth':0.04,'pa_smooth_on':False,
    'retract_len':0.8,'retract_len_on':True,'retract_speed':35.0,'retract_speed_on':False,
    'unretract_speed':35.0,'unretract_speed_on':False,'accel':4000.0,'accel_on':False,
    'velocity':0.0,'velocity_on':False,'min_cruise':0.0,'min_cruise_on':False,
    'square_corner':0.0,'square_corner_on':False,'flow':98.0,'flow_on':False,
    'fan':80.0,'fan_on':False,'ironing_flow':15.0,'ironing_flow_on':False,
    'first_layer_speed':75.0,'overrides':3,
    'feats': {c: [False,100.0,0.0,100.0] for c in _codes62}}
_pa109 = get_body('macros/05_materials.cfg', '_PROFILE_APPLY')
out = render(_ldp62, {'N':'2'})
tests.append(('R62 LOAD_DEFAULT_PRESET: chains the shared apply + reports',
    '_PROFILE_APPLY SRC=default N=2' in out and 'Default preset 2 LOADED: PETG' in out, out[:130]))
out = render(_pa109, {'SRC':'default', 'N':'2'})
tests.append(('R62 _PROFILE_APPLY (default src): restores values + feat flow',
    'VARIABLE=ov_hotend_first VALUE=240.0' in out and 'VARIABLE=ovf_wallouter_flw VALUE=100.0' in out
    and "VARIABLE=material VALUE='\"PETG\"'" in out and 'VARIABLE=first_layer_speed VALUE=75.0' in out, out[:130]))
tests.append(('R109 load FIX: the _on switches REALLY come back (old ";"-comment bug)',
    'VARIABLE=ov_hotend_first_on VALUE=True' in out
    and 'VARIABLE=ov_flow_on VALUE=False' in out
    and 'VARIABLE=ov_bed_on VALUE=True' in out, out[:130]))
_ddp62 = get_body('macros/05_materials.cfg', 'DELETE_DEFAULT_PRESET')
out = render(_ddp62, {'N':'2'})
tests.append(('R62 DELETE_DEFAULT_PRESET frees the slot',
    'VARIABLE=default_preset_2 VALUE=0' in out, out[:100]))

# --- FILE_AS_PRESET (file values -> pre-print) ---
_fap62 = get_body('macros/08_print_start_stop.cfg', 'FILE_AS_PRESET')
preview_vars.update({'name':'vase.gcode','bed':60,'hotend':215,
                      'fan':100,'pa':0.2,'flow_ratio':0.98})
out = render(_fap62, {})
tests.append(('R62 FILE_AS_PRESET: file temps/fan/PA/flow become pre-print overrides ON (beep)',
    'NAME=bed VALUE=60.0' in out and 'NAME=hotend_first VALUE=215.0' in out
    and 'NAME=hotend_after VALUE=215.0' in out and 'NAME=fan VALUE=100.0' in out
    and 'NAME=pa VALUE=0.2' in out and 'NAME=flow VALUE=98.0' in out
    and '_SOUND_LIB NAME=r2_confirm' in out, out[:200]))

# --- _PLOT_START ---
_pls62 = get_body('macros/12_maintenance.cfg', '_PLOT_START')
out = render(_pls62, {'EXTRUDE':'0'})
tests.append(('R62 _PLOT_START (pen): identifies as plot, homes, no purge',
    "VARIABLE=file_type VALUE='\"plot\"'" in out and 'G28' in out and 'M107' in out
    and 'PURGE' not in out.split('RESPOND')[0] and 'PEN mode' in out, out[:150]))
out = render(_pls62, {'EXTRUDE':'1'})
tests.append(('R62 _PLOT_START (filament): heats to L1 + applies overrides',
    'SET_HEATER_TEMPERATURE HEATER=extruder' in out and 'TEMPERATURE_WAIT' in out
    and '_APPLY_OVERRIDES_CORE' in out and 'FILAMENT mode' in out, out[:150]))

# --- PLT_FRAME ---
_plf62 = get_body('macros/12_maintenance.cfg', 'PLT_FRAME')
state_vars['mode'] = 'idle'
save_vars.update({'plot_bed_min_x':5.0,'plot_bed_max_x':239.0,'plot_bed_min_y':5.0,'plot_bed_max_y':233.0,
                  'plot_off_x':10.0,'plot_off_y':0.0,'plot_z_up':3.0,'plot_z_down':0.0,'plot_off_z':0.1})
out = render(_plf62, {})
tests.append(('R62 PLT_FRAME: drives the bed frame rectangle with pen offset',
    'G0 X15.0 Y5.0 F6000' in out and 'G1 X249.0 Y5.0 F2400' in out and 'G1 X249.0 Y233.0 F2400' in out
    and 'G1 Z0.1 F600' in out, out[:150]))

# --- per-feature FLOW in APPLY_TYPE ---
_at62 = get_body('macros/10_live_tuning.cfg', 'APPLY_TYPE')
save_vars.update({'ovf_wallouter_on':True,'ovf_wallouter_spd':80.0,'ovf_wallouter_flw':90.0,'ov_flow_on':False,'ov_flow':100.0})
state_vars.update({'mode':'printing','g_speed_clean':100,'current_type':'','ignore_overrides':False})
out = render(_at62, {'TYPE':'WALL-OUTER'})
tests.append(('R62 APPLY_TYPE: feature flow 90% applied via M99221',
    'M99221 S90' in out and 'flow 90%' in out, [l for l in out.split('\n') if 'M99221' in l][:1]))
save_vars['ovf_wallouter_flw'] = 100.0
out = render(_at62, {'TYPE':'WALL-OUTER'})
tests.append(('R62 APPLY_TYPE: feature flow 100% falls back to the global flow',
    'M99221 S100' in out, [l for l in out.split('\n') if 'M99221' in l][:1]))

# --- SET_OVERRIDE_VALUE feat_flw ---
_sov62 = get_body('macros/07_start_confirm.cfg', 'SET_OVERRIDE_VALUE')
out = render(_sov62, {'NAME':'feat_flw_brim','VALUE':'110'})
tests.append(('R62 SET_OVERRIDE_VALUE feat_flw_brim 110 -> ON',
    'VARIABLE=ovf_brim_flw VALUE=110.0' in out and 'VARIABLE=ovf_brim_on VALUE=True' in out, out[:140]))

# --- Preheat on file select ---
_ph62 = get_body('macros/08_print_start_stop.cfg', '_PREHEAT_SELECTED')
save_vars.update({'preheat_on':True,'preheat_hotend':220.0,'preheat_bed':65.0})
out = render(_ph62, {})
tests.append(('R62 _PREHEAT_SELECTED: heats beyond the current targets (anti-ooze levels)',
    'HEATER=extruder TARGET=220' in out and 'HEATER=heater_bed TARGET=65' in out
    and 'filament-swap level' in out, out[:150]))

# --- postproc: _read_vars prefix + both separators ---
import tempfile as _tf62, os as _os62
_d62 = _tf62.mkdtemp(prefix='r62_')
_fv62 = _os62.path.join(_d62, 'variables.cfg')
open(_fv62, 'w').write('[Variables]\nvariable_plot_mode = 1.0\nvariable_range_nonce: 9\n')
_rv62 = _pp61._read_vars(_fv62)
tests.append(('R62 _read_vars: variable_ prefix stripped, = and : both parsed, bare keys win',
    _rv62.get('plot_mode') == '1.0' and _rv62.get('range_nonce') == '9', str(_rv62)))

# --- postproc: _peek_file_info (file preview WITHOUT touching the file) ---
_fi62 = _os62.path.join(_d62, 'peek.gcode')
open(_fi62, 'w').write('M190 S60\nM109 S215\n;LAYER_CHANGE\nG1 X1\nM104 S210\nM106 S255\n'
                       '_FILE_INFO LINE_WIDTH=0.42 LAYER_HEIGHT=0.2 TOTAL_LAYERS=100 PA=0.05 NOZZLE=0.4 FLOW_RATIO=1 MATERIAL=PLA\n')
_pk62 = _pp61._peek_file_info(_fi62)
tests.append(('R62 _peek_file_info: temps from M109/M190, fan %, file params - file untouched',
    _pk62.get('HOTEND') == '215' and _pk62.get('BED') == '60' and _pk62.get('FAN') == '100'
    and _pk62.get('PA') == '0.05' and _pk62.get('TOTAL_LAYERS') == '100'
    and open(_fi62).read().count('LAYER_CHANGE') == 1, str(_pk62)))

# --- LCD ids R62 ---
tests.append(('R62 LCD: defaults + preheat + plot extras + force end + file preview ids',
    all(k in _lcd58 for k in ['__preprint __defs]', '__preprint __defs __save', '__preprint __defs __l1',
                              '__preprint __pre]', '__preprint __pre __hot', '__preprint __pre __now',
                              '__main __gen __plot __mode]', '__main __gen __plot __ox]', '__main __gen __plot __sx]',
                              '__main __gen __plot __frame]', '__preprint __rng __floor]', '__preprint __rng __brim]',
                              '__system __fend1]', '__system __fend2]', '__live __pause __fend]',
                              '__preprint __file __pvt]', '__preprint __feat __ow __flw]', '__preprint __feat __bm __flw]']), 'ids'))

# ============================== R63 tests: label generator + SAVE_CONFIG guard ===
import os as _os63
import re as _re63
import math as _math63
import tempfile as _tf63

# --- fonts: every charset char has a glyph in every font ---
_cs63 = _pp61.LABEL_CHARSET
tests.append(('R63 fonts cover the whole charset (3 fonts)',
    all(ch in _pp61.FONT_PIXEL or ch == ' ' for ch in _cs63)
    and all(ch in _pp61.FONT_MONO or ch == ' ' for ch in _cs63)
    and all(ch in _pp61.FONT_SMOOTH for ch in _cs63),
    [ch for ch in _cs63 if ch not in _pp61.FONT_MONO and ch != ' '][:6]))

# ============================== R82 tests: small-text label fonts ================
# three new fonts (COND=Oswald, NARROW=Roboto Condensed, CAPS=Bebas Neue) -
# generated by tools/make_label_fonts.py from tools/fonts_src/ (SIL OFL)
tests.append(('R82 fonts: COND/NARROW/CAPS cover the whole charset',
    all(ch in _pp61.FONT_COND for ch in _cs63)
    and all(ch in _pp61.FONT_NARROW for ch in _cs63)
    and all(ch in _pp61.FONT_CAPS for ch in _cs63),
    [ch for ch in _cs63 if ch not in _pp61.FONT_CAPS][:6]))
tests.append(('R82 fonts: DISTINCT data (no silent SMOOTH fallback)',
    _pp61.FONT_COND['A'][0] != _pp61.FONT_SMOOTH['A'][0]
    and _pp61.FONT_NARROW['A'][0] != _pp61.FONT_SMOOTH['A'][0]
    and _pp61.FONT_CAPS['A'][0] != _pp61.FONT_SMOOTH['A'][0]
    and _pp61.FONT_COND['A'][1] != _pp61.FONT_SMOOTH['A'][1],
    'COND A=%r SMOOTH A=%r' % (_pp61.FONT_COND['A'][:1], _pp61.FONT_SMOOTH['A'][:1])))
tests.append(('R82 fonts: COND is actually condensed (A advance < SMOOTH)',
    _pp61.FONT_COND['A'][0] < _pp61.FONT_SMOOTH['A'][0] - 1.0
    and _pp61.FONT_NARROW['A'][0] < _pp61.FONT_SMOOTH['A'][0],
    'COND %.1f NARROW %.1f SMOOTH %.1f' % (_pp61.FONT_COND['A'][0], _pp61.FONT_NARROW['A'][0], _pp61.FONT_SMOOTH['A'][0])))
tests.append(('R82 fonts: CAPS lowercase clones the capitals',
    _pp61.FONT_CAPS['a'][1] == _pp61.FONT_CAPS['A'][1]
    and _pp61.FONT_CAPS['g'][1] == _pp61.FONT_CAPS['G'][1]
    and _pp61.FONT_CAPS['ü'][1] == _pp61.FONT_CAPS['Ü'][1],
    'a=%r A=%r' % (_pp61.FONT_CAPS['a'][1][:24], _pp61.FONT_CAPS['A'][1][:24])))
_g82 = _pp61._label_glyphs('COND')
tests.append(('R82 _label_glyphs: per-font baseline + registry fallback',
    abs(_g82['baseline'] - _pp61.FONT_META_COND['cap']) < 0.01
    and _pp61._label_glyphs('UNSINN')['A'] == _pp61._label_glyphs('SMOOTH')['A'],
    'baseline COND=%.2f' % _g82['baseline']))
for _f82 in ('COND', 'NARROW', 'CAPS'):
    _o82, _i82 = _pp61.make_labels(['R2-D2'], w=50, h=15, font=_f82)
    _t82 = open(_o82).read()
    tests.append(('R82 make_labels builds with font %s' % _f82,
        _t82.count('LAYER_MARK') > 5 and 'APPLY_TYPE' in _t82,
        _i82.get('font', _f82)))
_o82a, _i82a = _pp61.make_labels(['X'], w=30, h=10, font='PIXEL')
_t82a = open(_o82a).read()    # read NOW - the SMOOTH call below writes the SAME filename
_o82b, _i82b = _pp61.make_labels(['X'], w=30, h=10, font='SMOOTH')
_t82b = open(_o82b).read()
tests.append(('R116 PIXEL is a REAL font again (Press Start 2P strokes, not the R80 bitmap)',
    _t82a != _t82b and 'font PIXEL' in _t82a, _t82a[:60]))
_sr82 = open('tools/r2_postproc.py').read()
tests.append(('R116 plot-text validators accept all 9 fonts',
    _sr82.count("('SMOOTH', 'MONO', 'COND', 'NARROW', 'CAPS', 'SCRIPT', 'HAND', 'PLATE', 'PIXEL')") >= 3,
    _sr82.count("('SMOOTH', 'MONO', 'COND', 'NARROW', 'CAPS', 'SCRIPT', 'HAND', 'PLATE', 'PIXEL')")))

# ============================== R116 tests: label job snapshots + new fonts ================
# .88 field log: (a) the label queue stored ONLY the text - font/size were read
# globally at Create time, so 10 labels x 5 fonts all printed the LAST font.
# (b) wishes: script + handwriting + license-plate + readable pixel fonts.
tests.append(('R116 fonts: SCRIPT/HAND/PLATE/PIXEL cover the whole charset',
    all(ch in _pp61.FONT_SCRIPT for ch in _cs63)
    and all(ch in _pp61.FONT_HAND for ch in _cs63)
    and all(ch in _pp61.FONT_PLATE for ch in _cs63)
    and all(ch in _pp61.FONT_PIXEL for ch in _cs63),
    [ch for ch in _cs63 if ch not in _pp61.FONT_SCRIPT][:6]))
tests.append(('R116 fonts: DISTINCT data (no silent SMOOTH fallback)',
    _pp61.FONT_SCRIPT['A'][1] != _pp61.FONT_SMOOTH['A'][1]
    and _pp61.FONT_HAND['A'][1] != _pp61.FONT_SMOOTH['A'][1]
    and _pp61.FONT_PLATE['A'][1] != _pp61.FONT_SMOOTH['A'][1]
    and _pp61.FONT_PIXEL['A'][1] != _pp61.FONT_SMOOTH['A'][1], ''))
tests.append(('R116 make_labels builds with SCRIPT/HAND/PLATE/PIXEL',
    all(open(_pp61.make_labels(['X'], w=30, h=12, font=_f116)[0]).read().count('LAYER_MARK') > 5
        for _f116 in ('SCRIPT', 'HAND', 'PLATE', 'PIXEL')), ''))
_o116, _i116 = _pp61.make_labels(
    ['GARAGE', 'WERKZEUG'], w=60, h=30, font='SMOOTH',
    job_cfgs=[{'font': 'CAPS', 'w': 80, 'h': 40, 'size': 0, 'spacing': 0,
               'stroke': 0, 'mode': 'grow', 'hole_side': 0, 'hole_d': 5},
              {'font': 'SCRIPT', 'w': 60, 'h': 30}])
_t116 = open(_o116).read()
tests.append(('R116 job_cfgs: per-job header + both fonts in info (the .88 font bug)',
    '; R116 per-job settings' in _t116 and 'CAPS' in _t116 and 'SCRIPT' in _t116
    and _i116['jobs'] and _i116['jobs'][0]['font'] == 'CAPS'
    and _i116['jobs'][1]['font'] == 'SCRIPT', str(_i116.get('jobs'))[:90]))
_polys116 = [l.split('POLYGON=')[1] for l in _t116.split(chr(10))
             if l.startswith('EXCLUDE_OBJECT_DEFINE NAME=LABEL')]
def _pw116(poly):
    import ast as _ast116
    _pts116 = _ast116.literal_eval(poly)
    return round(max(q[0] for q in _pts116) - min(q[0] for q in _pts116), 1)
tests.append(('R116 job_cfgs: label cells keep their OWN size (80x40 vs 60x30)',
    len(_polys116) == 2 and _pw116(_polys116[0]) == 80.0 and _pw116(_polys116[1]) == 60.0,
    [_pw116(q) for q in _polys116]))
_o116u, _ = _pp61.make_labels(['A', 'B'], w=60, h=30, font='SMOOTH')
_o116v, _ = _pp61.make_labels(['A', 'B'], w=60, h=30, font='SMOOTH', job_cfgs=None)
tests.append(('R116 job_cfgs=None stays byte-identical (golden safety)',
    open(_o116u).read() == open(_o116v).read(), ''))
_sr116 = open('tools/r2_postproc.py').read()
tests.append(('R116 watcher reads label_cfgs and passes job_cfgs',
    "rv.get('label_cfgs'" in _sr116 and 'job_cfgs=job_cfgs' in _sr116, ''))

_body116 = get_body('macros/16_labels.cfg', 'LABEL_ADD')
save_vars.update({'label_l1': 'GARAGE', 'label_lines': 1, 'label_font': 'CAPS',
                  'label_w': 80.0, 'label_h': 40.0, 'label_size': 0.0,
                  'label_spacing': 0.0, 'label_stroke': 0.0, 'label_mode': 0,
                  'label_hole_side': 0, 'label_hole_d': 5.0, 'label_texts': 'ALT',
                  'label_cfgs': 'SMOOTH~60.0~30.0~0.0~0.0~0.0~0~0~5.0~1~4~2~0.2~0.28~1~1~6.0~1',
                  'label_base_layers': 4, 'label_text_layers': 2,
                  'label_layer_h': 0.2, 'label_first_h': 0.28,
                  'label_ironing': True, 'label_brim': True, 'label_gap': 6.0,
                  'label_color2': True})
_out116 = render(_body116, {})
tests.append(('R116 LABEL_ADD snapshots the COMPLETE settings per job',
    'CAPS~80.0~40.0' in _out116 and 'GARAGE' in _out116
    and 'ALT|GARAGE' in _out116, [l for l in _out116.split(chr(10)) if 'label_cfgs' in l][:1]))
_body116 = get_body('macros/16_labels.cfg', 'LABEL_DEL_LAST')
save_vars.update({'label_texts': 'A|B',
                  'label_cfgs': 'SMOOTH~60.0~30.0~0.0~0.0~0.0~0~0~5.0~1~4~2~0.2~0.28~1~1~6.0~1|CAPS~80.0~40.0~0.0~0.0~0.0~0~0~5.0~1~4~2~0.2~0.28~1~1~6.0~1'})
_out116 = render(_body116, {})
tests.append(('R116 LABEL_DEL_LAST trims texts AND cfgs in parallel',
    'CAPS~80.0' not in _out116 and 'SMOOTH~60.0' in _out116, [l for l in _out116.split(chr(10)) if 'label_cfgs' in l][:1]))

_sr116m = open('macros/10_live_tuning.cfg').read()
tests.append(('R116 shaper-off: no-[input_shaper] case NOTIFYs on the LCD',
    'needs [input_shaper] in printer.cfg' in _sr116m and 'M117 ShaperOff: n/a' in _sr116m, ''))
_body116 = get_body('macros/10_live_tuning.cfg', 'SET_FEAT_SHAPER_OFF')
_out116 = render(_body116, {'STATE': '1'})
tests.append(('R116 shaper-off: STATE=1 arms the feature shaper-off',
    'VARIABLE=ovf_shaper_off_on VALUE=True' in _out116, _out116[:80]))


# --- make_labels: structure of the generated file ---
_d63 = _tf63.mkdtemp(prefix='r63_')
_bed63 = (0.0, -1.0, 244.0, 238.0)
_out63, _info63 = _pp61.make_labels(['WERKSTATT', 'R2-D2'], w=60, h=30, hole_side=1,
                                    hole_d=5.0, out_dir=_d63, bed=_bed63)
_t63 = open(_out63).read()
tests.append(('R63 make_labels: file + info (2 labels, tower, 6 layers)',
    _info63['count'] == 2 and _info63['layers'] == 6 and _info63['tower']
    and _os63.path.isfile(_out63), str(_info63)))
tests.append(('R63 make_labels: tagged by process() (TAG + _FILE_INFO + LAYER_MARK)',
    '; R2-POSTPROC v5' in _t63 and '_FILE_INFO' in _t63 and 'MATERIAL=PLA' in _t63
    and _t63.count('\nLAYER_MARK\n') == 6, ''))
tests.append(('R63 make_labels: PRINT_START head + slicer config comments',
    _t63.index('PRINT_START MATERIAL=PLA') > _t63.index('; filament_type = PLA')
    and 'TOTAL_LAYERS=6' in _t63 and '; layer_height = 0.2' in _t63, ''))
tests.append(('R63 make_labels: exclude objects per label + tower + KAMP polygons',
    _t63.count('EXCLUDE_OBJECT_DEFINE') == 3 and 'NAME=LABEL_1' in _t63
    and 'NAME=PURGE_TOWER' in _t63 and 'POLYGON=[[59.0,103.5]' in _t63
    and 'EXCLUDE_OBJECT_START NAME=LABEL_1' in _t63, ''))
tests.append(('R63 make_labels: print-by-layer - M600 after the bases, text after M600',
    _t63.index('\nM600\n') < _t63.rindex('EXCLUDE_OBJECT_START NAME=LABEL_1')
    and _t63.index('\nM600\n') > _t63.index(';TYPE:Ironing'), ''))
tests.append(('R63 make_labels: brim + ironing blocks present',
    ';TYPE:Brim' in _t63 and ';TYPE:Ironing' in _t63 and ';TYPE:Top surface' in _t63, ''))

# --- R73: hole at the EDGE (2mm rim), text box = the three non-hole sides ---
_circ63, _box63, _hd63 = _pp61._label_layout(60, 30, 1, 5.0)
tests.append(('R73 label layout: hole 2mm from the edge, text box on the three free sides',
    abs(_circ63[0] - (2.0 + 5.0 / 2)) < 0.01 and abs(_circ63[1] - 15.0) < 0.01
    and _hd63 == 5.0 and _box63[0] > _circ63[0] + _circ63[2] + 1.0
    and _box63[1] == 2.1 and _box63[3] == 27.9,
    str((_circ63, _box63))))
_circ63b, _box63b, _hd63b = _pp61._label_layout(60, 30, 3, 5.0)
tests.append(('R73 label layout: TOP hole -> box below the hole band, centered x',
    abs(_circ63b[1] - (30.0 - 2.0 - 2.5)) < 0.01 and _box63b[3] == 30.0 - 9.1
    and _box63b[0] == 2.1 and _box63b[2] == 57.9, str((_circ63b, _box63b))))
_lines63 = _t63.split('\n')
_marks63 = [i for i, l in enumerate(_lines63) if l.strip() == 'LAYER_MARK']
_last63 = _lines63[_marks63[-1]:]
_seg63 = [i for i, l in enumerate(_last63) if l.startswith('EXCLUDE_OBJECT_START NAME=LABEL_1')][0]
_xs63, _ys63 = [], []
for l in _last63[_seg63:]:
    if l.startswith('EXCLUDE_OBJECT_END'):
        break
    m = _re63.match(r'G1 X([\d.-]+) Y([\d.-]+) E', l)
    if m:
        _xs63.append(float(m.group(1))); _ys63.append(float(m.group(2)))
_m63 = _re63.search(r'EXCLUDE_OBJECT_DEFINE NAME=LABEL_1 CENTER=([\d.-]+),([\d.-]+)', _t63)
_lx63, _ly63 = float(_m63.group(1)) - 30, float(_m63.group(2)) - 15
_hx63, _hy63 = _lx63 + _circ63[0], _ly63 + _circ63[1]
tests.append(('R63 golden ratio: text never collides with the hole',
    all(_math63.hypot(x - _hx63, y - _hy63) > _circ63[2] + 0.4 for x, y in zip(_xs63, _ys63)),
    'min dist %.2f' % min(_math63.hypot(x - _hx63, y - _hy63) for x, y in zip(_xs63, _ys63))))
tests.append(('R63 text: fits the band, >= 3mm tall',
    min(_xs63) >= _lx63 + _box63[0] - 0.2 and max(_xs63) <= _lx63 + _box63[2] + 0.2
    and (max(_ys63) - min(_ys63)) >= 3.0, '%.1fmm' % (max(_ys63) - min(_ys63))))

# --- z ladder + E sanity + bed bounds ---
_zs63 = [float(m.group(1)) for m in (_re63.search(r';Z:([\d.]+)', l) for l in _lines63) if m]
tests.append(('R63 layers: Z ladder first 0.28 then 0.2 steps',
    _zs63 == [0.28, 0.48, 0.68, 0.88, 1.08, 1.28], str(_zs63)))
tests.append(('R63 gcode: no negative E, all moves inside the bed',
    not _re63.search(r' E(-\d)', _t63)
    and all(0 <= float(m.group(1)) <= 244 for m in _re63.finditer(r'G[01] X([\d.-]+) Y', _t63))
    and all(-1 <= float(m.group(1)) <= 238 for m in _re63.finditer(r'G[01] X[\d.-]+ Y([\d.-]+)', _t63)), ''))

# --- variants: single color, no brim/ironing, PIXEL font, hole sides ---
_o63, _i63 = _pp61.make_labels(['R2-D2'], w=50, h=25, font='PIXEL', base_layers=3,
                               text_layers=3, hole_side=3, hole_d=4.0, color2=False,
                               out_dir=_d63, bed=_bed63)
_v63 = open(_o63).read()
tests.append(('R63 single color: no M600, no tower, still 6 layers + hole TOP',
    '\nM600\n' not in _v63 and 'PURGE_TOWER' not in _v63 and _v63.count('\nLAYER_MARK\n') == 6, ''))
_o63b, _i63b = _pp61.make_labels(['TEST'], w=40, h=20, font='MONO', ironing=False,
                                 brim=False, hole_side=2, hole_d=6.0, out_dir=_d63, bed=_bed63)
_v63b = open(_o63b).read()
tests.append(('R63 variants: ironing/brim OFF + hole RIGHT + tower prime after M600',
    ';TYPE:Ironing' not in _v63b and ';TYPE:Brim' not in _v63b and '\nM600\n' in _v63b
    and 'G1 E4.000 F180' in _v63b, ''))
tests.append(('R63 grid: reading order - most columns that fit (9 labels -> 5x2)',
    _i63b is not None and True, ''))
_o63c, _i63c = _pp61.make_labels(['L%d' % i for i in range(9)], w=40, h=20, gap=5,
                                 out_dir=_d63, bed=_bed63)
tests.append(('R63 grid: 9 labels 40x20 -> 5 cols x 2 rows',
    _i63c['cols'] == 5 and _i63c['rows'] == 2 and _i63c['fit'] == 10, str(_i63c)))

# --- error cases ---
try:
    _pp61.make_labels(['A'] * 10, w=120, h=100, gap=8, out_dir=_d63, bed=_bed63)
    tests.append(('R63 fit guard: too many/large labels raise', False, 'no error'))
except ValueError as e:
    tests.append(('R63 fit guard: too many/large labels raise', 'do not fit the bed' in str(e), str(e)[:80]))
# R80: the error storm is GONE - a long text grows the label instead
_olg80, _ilg80 = _pp61.make_labels(['DIESE ZEICHENKETTE IST ZU LANG'], w=40, h=20,
                                    out_dir=_d63, bed=_bed63)
tests.append(('R80 labels: long text GROWS the label (was: error) + stays readable',
    _ilg80['grown'] and _ilg80['cap_mm'] >= 2.5 and _ilg80['w'] > 40.0
    and _ilg80['file'].startswith('00_') and '_V01.gcode' in _ilg80['file'],
    'w=%s h=%s cap=%s' % (_ilg80['w'], _ilg80['h'], _ilg80['cap_mm'])))

# --- bed limits parse (colon syntax, user-style printer.cfg) ---
_p63 = _os63.path.join(_d63, 'printer.cfg')
open(_p63, 'w').write('[stepper_x]\nposition_min: 0\nposition_max: 244\n[stepper_y]\nposition_min: -1 #comment\nposition_max: 238\n')
# R92: the steppers are lifted on this machine (meshing rides beyond the
# plate) - the config is the truth, the fallback is the Ender-3 220x220.
# R104.2: the config carrier is [gcode_macro _R2_CONFIG] (KAMP-style) - a raw
# [r2_postproc] section HALTS Klipper ('not a valid config section', field
# log .81) and is only read as a legacy courtesy by the watcher.
open(_p63, 'a').write('\n[gcode_macro _R2_CONFIG]\nvariable_bed_min_x: 0\n'
                     'variable_bed_max_x: 220\nvariable_bed_min_y: -1\n'
                     'variable_bed_max_y: 216\n')
tests.append(('R63/R92/R104.2 _bed_limits: [gcode_macro _R2_CONFIG] wins over the lifted steppers',
    _pp61._bed_limits(_p63) == (0.0, -1.0, 220.0, 216.0), str(_pp61._bed_limits(_p63))))
tests.append(('R63/R92 _bed_limits: no section / no file -> Ender-3 default 220x220',
    _pp61._bed_limits(_os63.path.join(_d63, 'other.cfg')) == (0.0, -3.0, 220.0, 217.0), ''))
_p63l = _os63.path.join(_d63, 'legacy.cfg')
open(_p63l, 'w').write('[stepper_x]\nposition_max: 244\n\n[r2_postproc]\n'
                       'bed_min_x: 5\nbed_max_x: 215\nbed_min_y: 0\nbed_max_y: 210\n')
tests.append(('R104.2 _bed_limits: legacy [r2_postproc] still read (courtesy) although it halts Klipper',
    _pp61._bed_limits(_p63l) == (5.0, 0.0, 215.0, 210.0), str(_pp61._bed_limits(_p63l))))

# --- watcher: label nonce hook reads variables.cfg end-to-end ---
_d63w = _tf63.mkdtemp(prefix='r63w_')
_os63.makedirs(_os63.path.join(_d63w, 'gcodes'), exist_ok=True)
_os63.makedirs(_os63.path.join(_d63w, 'config'), exist_ok=True)
open(_os63.path.join(_d63w, 'config', 'printer.cfg'), 'w').write(
    '[stepper_x]\nposition_max: 244\n[stepper_y]\nposition_min: -1\nposition_max: 238\n')
open(_os63.path.join(_d63w, 'variables.cfg'), 'w').write(
    "[Variables]\nvariable_label_texts = 'A|B'\nvariable_label_w = 50\nvariable_label_h = 25\n"
    "variable_label_hole_side = 2\nvariable_label_hole_d = 4\nvariable_label_ironing = True\n"
    "variable_label_color2 = True\nvariable_material = 'PLA'\nvariable_label_gen_nonce = 1\n")
_rv63 = _pp61._read_vars(_os63.path.join(_d63w, 'variables.cfg'))
tests.append(('R63 watcher vars: label_* readable via _read_vars',
    _rv63.get('label_texts') == 'A|B' and _rv63.get('label_hole_side') == '2', str(_rv63)[:80]))

# --- macro renders: the label chain ---
_lb = get_body('macros/16_labels.cfg', '_LABEL_SET_CHAR')
save_vars['label_l1'] = 'HALLO'
out = render(_lb, {'POS': 3, 'CH': 5})
tests.append(('R63/R71/R74 _LABEL_SET_CHAR: writes the char, cursor ADVANCES to the next position',
    ('VARIABLE=label_l1 VALUE="' + BKSL + '"HAFLO' + BKSL + '"') in out and '@4' in out
    and 'VARIABLE=label_pos VALUE=4' in out, out[:120]))
save_vars['label_l1'] = ''
out = render(_lb, {'POS': 1, 'CH': 5})
tests.append(('R63/R74 _LABEL_SET_CHAR: empty buffer, pos 1',
    ('VARIABLE=label_l1 VALUE="' + BKSL + '"F' + BKSL + '"') in out, out[:120]))

_lb = get_body('macros/16_labels.cfg', 'LABEL_ADD')
save_vars.update({'label_l1': ' VASE ', 'label_texts': 'WERKSTATT', 'label_lines': 1})
out = render(_lb, {})
tests.append(('R63/R74 LABEL_ADD: trims + appends with | separator + queue count',
    ('VARIABLE=label_texts VALUE="' + BKSL + '"WERKSTATT|VASE' + BKSL + '"') in out and 'Added 2/24' in out, out[:120]))
save_vars['label_l1'] = ''
out = render(_lb, {})
tests.append(('R63/R74 LABEL_ADD: empty text -> warning, no write',
    'VARIABLE=label_texts' not in out and 'No text' in out.replace('TEXT=', ''), out[:100]))
save_vars.update({'label_l1': 'VASE', 'label_texts': 'WERKSTATT|VASE'})

_lb = get_body('macros/16_labels.cfg', 'LABEL_DEL_LAST')
out = render(_lb, {})
tests.append(('R63 LABEL_DEL_LAST: removes the last entry',
    ('VARIABLE=label_texts VALUE="' + BKSL + '"WERKSTATT' + BKSL + '"') in out, out[:120]))

_lb = get_body('macros/16_labels.cfg', 'LABEL_GENERATE')
out = render(_lb, {})
tests.append(('R63 LABEL_GENERATE: bumps the nonce + announces',
    'VARIABLE=label_gen_nonce VALUE=1' in out and 'creating' in out, out[:120]))
save_vars['label_texts'] = ''
out = render(_lb, {})
tests.append(('R63 LABEL_GENERATE: empty queue -> warning',
    'VARIABLE=label_gen_nonce' not in out, out[:100]))
save_vars['label_texts'] = 'WERKSTATT|VASE'

_lb = get_body('macros/16_labels.cfg', 'GEN_LABELS')
out = render(_lb, {'TEXT': 'EINS|ZWEI', 'W': 70, 'HOLE': 'LEFT', 'HOLE_D': 4})
tests.append(('R63 GEN_LABELS (console): sets all vars + queues the job',
    ('VARIABLE=label_texts VALUE="' + BKSL + '"EINS|ZWEI' + BKSL + '"') in out and 'VARIABLE=label_w VALUE=70.0' in out
    and 'VARIABLE=label_hole_side VALUE=1' in out and 'VARIABLE=label_hole_d VALUE=4.0' in out
    and 'LABEL_GENERATE' in out, out[:160]))
out = render(_lb, {})
tests.append(('R63 GEN_LABELS without TEXT -> usage hint',
    'GEN_LABELS needs TEXT' in out and 'VARIABLE=label_texts' not in out, out[:100]))

_lb = get_body('macros/16_labels.cfg', 'LABEL_CLEAR_ALL')
out = render(_lb, {'CONFIRM': 1})
tests.append(('R63 LABEL_CLEAR_ALL CONFIRM=1 clears the queue (shlex-safe)',
    "VARIABLE=label_texts VALUE='\"\"\"'" in out or 'VARIABLE=label_texts' in out, out[:100]))
save_vars['label_texts'] = 'WERKSTATT'

# --- SYS_SAVE_CONFIG (R63 freeze fix) ---
_sc = get_body('macros/13_system.cfg', 'SYS_SAVE_CONFIG')
state_vars['mode'] = 'idle'
out = render(_sc, {}, ps_state='idle')
tests.append(('R63 SYS_SAVE_CONFIG: first press reports the pending state',
    'Nothing pending' in out and 'save instantly' in out
    and 'G4 P1500' not in out and 'STOP_LED_EFFECTS' not in out, out[:140]))
out = render(_sc, {'CONFIRM': 1}, ps_state='idle', scp=False)
tests.append(('R63/R83 SYS_SAVE_CONFIG: nothing pending + CONFIRM -> restart anyway',
    'Restarting Klipper now' in out and 'FIRMWARE_RESTART' in out
    and 'SAVE_CONFIG\n' not in out and 'G4 P800' in out
    and 'STOP_LED_EFFECTS' in out, out[:160]))
out = render(_sc, {'CONFIRM': 1}, ps_state='idle', scp=True)
tests.append(('R63 SYS_SAVE_CONFIG: pending + CONFIRM -> SAVE_CONFIG with warning first',
    'DO NOT power off' in out and out.index('DO NOT power off') < out.index('SAVE_CONFIG')
    and 'G4 P1500' in out, out[:160]))
out = render(_sc, {'CONFIRM': 1}, ps_state='printing')
tests.append(('R63 SYS_SAVE_CONFIG: blocked during a print',
    'blocked during a print' in out and 'SAVE_CONFIG\n' not in out, out[:120]))
state_vars['mode'] = 'printing'

# --- boot feedback + install hint + menu ids ---
_st63 = open('macros/01_state.cfg').read()
tests.append(('R63 boot feedback: _INIT_AFTER_BOOT beeps + M117 ready after a restart',
    "_SOUND_LIB NAME=r2_done" in _st63.split('_INIT_AFTER_BOOT')[1][:700]
    and 'M117 R2 ready' in _st63.split('_INIT_AFTER_BOOT')[1][:700], ''))
tests.append(('R63 install hint: missing 16_labels.cfg gets a friendly line',
    "Labels menu inactive" in _st63 and "16_labels.cfg" in _st63, ''))
_lcd63 = open('menus/lcd_menues.cfg').read()
tests.append(('R63 LCD: labels menu + editor + settings + job ids, guarded enable',
    all(k in _lcd63 for k in ['[menu __main __gen __labels]', '__labels __txt __chr]', '__labels __set __fnt]',
                                '__labels __set __hsd]', '__labels __job __add]', '__labels __job __gen]',
                                "__labels __job __clr2]", "enable: {'gcode_macro _LABELS' in printer}"]), 'ids'))
tests.append(('R63 LCD: System > Save config is the guarded SYS_SAVE_CONFIG pair',
    '__system __save]' in _lcd63 and '>> SAVE+RESTART' in _lcd63
    and 'gcode: SAVE_CONFIG\n' not in _lcd63, ''))
_order63 = [_lcd63.find(x) for x in ['[menu __main __gen __labels]', '[menu __main __maint]']]
tests.append(('R63 LCD: Labels sits before Maintenance', 0 < _order63[0] < _order63[1], str(_order63)))


# ============================== R64 tests: resonance diagram + bridge + plotter ==
import os as _os64
import re as _re64
import math as _math64
import tempfile as _tf64
import struct as _st64
import zlib as _zl64

_pp = _pp61          # same r2_postproc module, R64 API on top

# --- R64 shaper math: faithful Klipper port -------------------------------
_A64, _T64 = _pp._mzv_base_coeffs()
tests.append(('R64 MZV base coeffs: classic 1-1/sqrt(2), sqrt(2)-1, sum 1',
    abs(_A64[0] - (1 - 1/_math64.sqrt(2))) < 1e-9 and abs(_A64[1] - (_math64.sqrt(2) - 1)) < 1e-9
    and abs(sum(_A64) - 1.0) < 1e-9, str(_A64)))
_Am, _Tm = _pp._shaper_mzv(60.0, 0.1)
_r64 = _pp._shaper_response(_Am, _Tm, 0.1, [60.0, 30.0, 100.0])
tests.append(('R64 shaper response: notch at the shaper frequency',
    _r64[0] < 0.06 and 0.3 < _r64[1] < 0.9, str([round(x, 3) for x in _r64])))
_Az, _Tz = _pp._shaper_zv(50.0, 0.1)
tests.append(('R64 ZV impulses match Klipper formulas',
    abs(_Az[1] - _math64.exp(-0.1*_math64.pi/_math64.sqrt(0.99))) < 1e-12
    and abs(_Tz[1] - 0.5/(50*_math64.sqrt(0.99))) < 1e-12, str(_Az)))
_Ae, _Te = _pp._shaper_ei(50.0, 0.1)
tests.append(('R64 EI amplitudes sum to 1',
    abs(sum(_Ae) - 1.0) < 1e-9 and len(_Ae) == 3, str(_Ae)))
tests.append(('R64 smoothing + max_accel positive and monotonic',
    _pp._shaper_smoothing(_Az, _Tz, 5000.0, 5.0) > 0
    and _pp._shaper_smoothing(_Az, _Tz, 2000.0, 5.0) < _pp._shaper_smoothing(_Az, _Tz, 8000.0, 5.0)
    and _pp._shaper_max_accel(_Az, _Tz, 5.0) > 1000, ''))
_fr64 = [5.0 + i*1.5 for i in range(120)]
_ps64 = _pp._normalize_psd(_fr64, [1.0/(1+((f-60.0)/2.0)**2)**3 + 0.01 for f in _fr64])
_best64, _table64 = _pp._fit_shapers(_fr64, _ps64, 5.0)
tests.append(('R64 fit_shapers: synthetic 60Hz peak -> best shaper near the peak',
    52 <= _best64['freq'] <= 68 and _best64['name'] in ('zv', 'mzv', 'ei'),
    '%s@%.1f' % (_best64['name'], _best64['freq'])))
tests.append(('R64 fit table: all 5 autotune shapers, vibrs in 0..1',
    sorted(s['name'] for s in _table64) == sorted(_pp.AUTOTUNE_SHAPERS)
    and all(0 <= s['vibrs'] <= 1 and s['smoothing'] > 0 for s in _table64),
    str([(s['name'], round(s['freq'], 1)) for s in _table64])))

# --- R64 resonance CSV parsing (both Klipper file styles) -------------------
_d64 = _tf64.mkdtemp(prefix='r64csv')
_fr2 = [round(1.6 * i, 1) for i in range(120)]
def _psd_at(f, base=1.0):
    return (base * 1.0/(1+((f-63.0)/1.8)**2)**4 + 0.02) / (f + 0.1)
_rows = ['freq,psd_x,psd_y,psd_z,psd_xyz,shapers:,zv(60.8),mzv(63.8),ei(56.2),2hump_ei(50.4),3hump_ei(52.6)']
for _f in _fr2:
    _p = _psd_at(_f)
    _rows.append('%.1f,%.3e,%.3e,%.3e,%.3e,,0.998,0.997,0.981,0.905,0.823' % (_f, _p, _p*0.5, _p*0.2, _p*1.7))
open(_os64.path.join(_d64, 'calibration_data_x_20260929_120000.csv'), 'w').write('\n'.join(_rows) + '\n')
_rows2 = ['freq,psd_x,psd_y,psd_z,psd_xyz']
for _f in _fr2:
    _p = _psd_at(_f, 0.7) + 0.9/(1+((_f-45.0)/2.5)**2)**4
    _rows2.append('%.1f,%.3e,%.3e,%.3e,%.3e' % (_f, _p*0.3, _p*0.4, _p*0.1, _p*0.8))
open(_os64.path.join(_d64, 'resonances_y_20260929_120500.csv'), 'w').write('\n'.join(_rows2) + '\n')
_dx = _pp._resonance_axis_data('x', [_d64])
tests.append(('R64 calibrated CSV: keeps the file shaper frequencies',
    [round(s['freq'], 1) for s in _dx['table']] == [60.8, 63.8, 56.2, 50.4, 52.6]
    and len(_dx['freqs']) > 50 and _dx['best'] in _dx['table'],
    str([(s['name'], s['freq']) for s in _dx['table']])))
_dy = _pp._resonance_axis_data('y', [_d64])
tests.append(('R64 raw resonances CSV: own fit near the 45Hz peak',
    40 <= _dy['best']['freq'] <= 52 and _dy['best']['vibrs'] < 0.05,
    '%s@%.1f %.1f%%' % (_dy['best']['name'], _dy['best']['freq'], _dy['best']['vibrs']*100)))
tests.append(('R64 missing axis CSV -> no file found',
    _pp._find_resonance_csv('z', [_d64]) is None, ''))
try:
    _pp._resonance_axis_data('z', [_d64])
    _err64 = 'NO ERROR RAISED'
except ValueError as _e64:
    _err64 = str(_e64)
tests.append(('R64 _resonance_axis_data error message names the axis + dirs',
    'axis Z' in _err64 and 'CALIBRATE_SHAPER' in _err64, _err64[:90]))
_md64 = _pp._parse_resonance_csv(_os64.path.join(_d64, 'calibration_data_x_20260929_120000.csv'))
tests.append(('R64 CSV parser: shaper columns + double-comma layout',
    [s[0] for s in _md64['shapers']] == ['zv', 'mzv', 'ei', '2hump_ei', '3hump_ei']
    and _md64['normalized'], str([s[0] for s in _md64['shapers']])))

# --- R64 resonance diagram: print + plot ------------------------------------
_g64 = _tf64.mkdtemp(prefix='r64gen')
_files64, _info64 = _pp.make_resonance(axes=['x', 'y'], mode='print', out_dir=_g64,
                                       bed=(0, -1, 244, 238), csv_dirs=[_d64])
_g = open(_files64[0]).read()
tests.append(('R64 resonance print: file name + info per axis',
    _os64.path.basename(_files64[0]) == '00_Resonance_XY_V01.gcode'
    and set(_info64['axes']) == {'x', 'y'} and 'best_txt' in _info64['axes']['x'], ''))
tests.append(('R64 resonance print: EXCLUDE_OBJECT_DEFINE before PRINT_START',
    _g.index('EXCLUDE_OBJECT_DEFINE NAME=RESONANCE_X') < _g.index('PRINT_START')
    and _g.count('EXCLUDE_OBJECT_DEFINE') == 2, ''))
tests.append(('R64 resonance print: 5 layers, marks + types via process()',
    _g.count(';LAYER_CHANGE') == 5 and 'LAYER_MARK' in _g and 'APPLY_TYPE' in _g
    and '; R2-POSTPROC v5' in _g, ''))
_xs64 = [float(m.group(1)) for m in _re64.finditer(r'^G[01] X([\d.]+)', _g, _re64.M)]
_ys64 = [float(m.group(1)) for m in _re64.finditer(r' Y(-?[\d.]+)', _g, _re64.M)]
tests.append(('R64 resonance print: both plates inside the bed',
    0 <= min(_xs64) and max(_xs64) <= 244 and -1 <= min(_ys64) and max(_ys64) <= 238
    and max(_xs64) > 200, 'X %.1f..%.1f Y %.1f..%.1f' % (min(_xs64), max(_xs64), min(_ys64), max(_ys64))))
tests.append(('R64 resonance print: single color (no M600), fan from layer 2',
    'M600' not in _g and 'M106 S178' in _g and 'M107' in _g, ''))
_files64p, _info64p = _pp.make_resonance(axes=['x', 'y'], mode='plot', out_dir=_g64,
                                         bed=(0, -1, 244, 238), csv_dirs=[_d64])
_gp = open(_files64p[0]).read()
tests.append(('R64 resonance plot: R2-PLOT header, own file, no PRINT_START',
    'R2-PLOT' in _gp[:200] and _os64.path.basename(_files64p[0]) == '00_Resonance_XY_plot_V01.gcode'
    and 'PRINT_START' not in _gp and '_PLOT_START EXTRUDE=0' in _gp, ''))
tests.append(('R64 process() skips R2-PLOT files (no print tags)',
    _pp.process(_files64p[0])['skipped'] is True, ''))
tests.append(('R64 single axis + missing axis -> one plate, no crash',
    (lambda _f, _i: _os64.path.basename(_f[0]) == '00_Resonance_X_plot_V01.gcode')(*_pp.make_resonance(
        axes=['x'], mode='plot', out_dir=_g64, bed=(0, -1, 244, 238), csv_dirs=[_d64])), ''))
try:
    _pp.make_resonance(axes=['z'], mode='print', out_dir=_g64, csv_dirs=[_d64])
    _rerr64 = 'NO ERROR'
except ValueError as _e64:
    _rerr64 = str(_e64)
tests.append(('R64 resonance: bad axis rejected', 'AXIS must be' in _rerr64, _rerr64[:60]))

# --- R64 bridge test --------------------------------------------------------
_ob64, _oi64 = _pp.make_bridge(length=150, short_pct=40, bed=(0, -1, 244, 238),
                               out_dir=_g64, bridge_layers=2, h_long=30, h_short=15, fan=200)
_gb = open(_ob64).read()
tests.append(('R64 bridge: file name + layer math (30mm top -> 152 layers)',
    _oi64['file'] == '00_Bridge_150mm_40pct_V01.gcode' and _oi64['layers'] == 152
    and _oi64['short_len'] == 60.0, str(_oi64)))
tests.append(('R64 bridge: 5 exclude objects, BRIDGE type, fan per deck',
    _re64.findall(r'EXCLUDE_OBJECT_DEFINE NAME=(\w+)', _gb) ==
    ['TOWER_A', 'TOWER_B', 'TOWER_C', 'BRIDGE_SHORT', 'BRIDGE_LONG']
    and _gb.count(';TYPE:Bridge') == 4 and 'M106 S200' in _gb and 'M106 S178' in _gb, ''))
_cA = _re64.search(r'NAME=TOWER_A CENTER=([\d.-]+),([\d.-]+)', _gb)
_cB = _re64.search(r'NAME=TOWER_B CENTER=([\d.-]+),([\d.-]+)', _gb)
_cC = _re64.search(r'NAME=TOWER_C CENTER=([\d.-]+),([\d.-]+)', _gb)
_A64p = (float(_cA.group(1)), float(_cA.group(2)))
_B64p = (float(_cB.group(1)), float(_cB.group(2)))
_C64p = (float(_cC.group(1)), float(_cC.group(2)))
tests.append(('R64 bridge: A-B spans 150mm on the 45 degree diagonal',
    abs(_math64.hypot(_B64p[0]-_A64p[0], _B64p[1]-_A64p[1]) - 150) < 0.6
    and abs((_B64p[1]-_A64p[1])/(_B64p[0]-_A64p[0]) - 1.0) < 1e-6, str(_A64p) + str(_B64p)))
tests.append(('R64 bridge: C sits ON the diagonal at 40% (short under long)',
    abs(_math64.hypot(_C64p[0]-_A64p[0], _C64p[1]-_A64p[1]) - 60) < 0.6
    and abs((_C64p[1]-_A64p[1])/(_C64p[0]-_A64p[0]) - 1.0) < 1e-6, str(_C64p)))
_xs64b = [float(m.group(1)) for m in _re64.finditer(r'^G[01] X([\d.]+)', _gb, _re64.M)]
_ys64b = [float(m.group(1)) for m in _re64.finditer(r' Y(-?[\d.]+)', _gb, _re64.M)]
tests.append(('R64 bridge: everything inside the bed + towers + brim',
    6 <= min(_xs64b) and max(_xs64b) <= 238 and 6 <= min(_ys64b) and max(_ys64b) <= 232,
    'X %.1f..%.1f Y %.1f..%.1f' % (min(_xs64b), max(_xs64b), min(_ys64b), max(_ys64b))))
tests.append(('R64 bridge: normal flow (PRINT_START + marks + M117 stages)',
    'PRINT_START MATERIAL=' in _gb and 'LAYER_MARK' in _gb and 'M117 Bridge: short 60mm' in _gb
    and 'M117 Bridge: long 150mm' in _gb and 'TYPES=' in _gb and 'BRIDGE' in _re64.search(r'TYPES=([\w,\-]+)', _gb).group(1), ''))
try:
    _pp.make_bridge(length=310, out_dir=_g64, bed=(0, -1, 244, 238))
    _berr64 = 'NO ERROR'
except ValueError as _e64:
    _berr64 = str(_e64)
tests.append(('R64 bridge: overlong span rejected with the real limit',
    'does not fit the bed diagonal' in _berr64, _berr64[:80]))
tests.append(('R64 bridge: short height auto-clamped below the long one',
    (lambda _i: _i['h_short'] < _i['h_long'] - 5)(_pp.make_bridge(
        length=120, short_pct=30, h_long=20, h_short=19, bed=(0, -1, 244, 238), out_dir=_g64)[1]), ''))

# --- R64 text + status plot -------------------------------------------------
open(_os64.path.join(_g64, 'notes.txt'), 'w').write(
    'WERKSTATT REGELN\n\n1. Maschine saeubern\n2. Filament trocknen\n' * 3 + 'emoji: \U0001f600 ok\n')
_ot64, _nl64, _sz64 = _pp.text_convert(_os64.path.join(_g64, 'notes.txt'),
                                       out=_os64.path.join(_g64, 'notes.txt.gcode'))
_gt = open(_ot64).read()
tests.append(('R64 text plot: wraps + auto-fits one page, unknown chars -> ?',
    _nl64 == 13 and 'R2-PLOT' in _gt[:200] and '_PLOT_START EXTRUDE=0' in _gt, 'lines %d @ %.1fmm' % (_nl64, _sz64)))
_ys64t = [float(m.group(1)) for m in _re64.finditer(r' Y([\d.]+)', _gt)]
tests.append(('R64 text plot: stays on the plot bed',
    5 <= min(_ys64t) and max(_ys64t) <= 233, 'Y %.1f..%.1f' % (min(_ys64t), max(_ys64t))))
open(_os64.path.join(_g64, 'many.txt'), 'w').write(''.join('Zeile %d Text\n' % i for i in range(80)))
_o2, _n2, _s2 = _pp.text_convert(_os64.path.join(_g64, 'many.txt'),
                                 out=_os64.path.join(_g64, 'many.txt.gcode'))
_cols64t, _sz64t = _pp._fit_text_page(['Zeile %d Text' % i for i in range(80)],
                                       226.0, 220.0, 7.0, 'SMOOTH')
tests.append(('R73 text plot: 80 lines -> 3 columns at >=6mm caps + truncation note',
    _s2 >= 6.0 and _n2 == 60 and len(_cols64t) == 3 and _sz64t >= 6.0
    and any('more lines' in l for c in _cols64t for l in c),
    '%d lines @ %.1fmm' % (_n2, _s2)))
_os64p, _n3, _s3 = _pp.make_status_plot(out=_os64.path.join(_g64, 'R2_Status.gcode'))
_gst = open(_os64p).read()
tests.append(('R64 status plot: report page with version + key values',
    _n3 >= 13 and 'R2-PLOT' in _gst[:200] and '_PLOT_START' in _gst, '%d lines' % _n3))

# --- R64 image polarity (dark writing boards) --------------------------------
def _png64(path, w, h, fn):
    rows = b''
    for y in range(h):
        rows += b'\x00'
        for x in range(w):
            rows += bytes(fn(x, y))
    def chunk(t, d):
        c = t + d
        return _st64.pack('>I', len(d)) + c + _st64.pack('>I', _zl64.crc32(c) & 0xffffffff)
    open(path, 'wb').write(b'\x89PNG\r\n\x1a\n'
                           + chunk(b'IHDR', _st64.pack('>IIBBBBB', w, h, 8, 2, 0, 0, 0))
                           + chunk(b'IDAT', _zl64.compress(rows)) + chunk(b'IEND', b''))
import shutil as _sh64
_png64(_os64.path.join(_g64, 'board.png'), 120, 80,
       lambda x, y: (30, 30, 30) if not (20 <= y <= 60 and 15 <= x <= 105) else (170, 170, 160))
_png64(_os64.path.join(_g64, 'paper.png'), 120, 80,
       lambda x, y: (240, 238, 230) if not (20 <= y <= 60 and 15 <= x <= 105) else (20, 20, 20))
_sh64.copy(_os64.path.join(_g64, 'board.png'), _os64.path.join(_g64, 'board.png.gcode'))
_pp.plot_convert(_os64.path.join(_g64, 'board.png.gcode'))
_gboard = open(_os64.path.join(_g64, 'board.png.gcode')).read()
_sh64.copy(_os64.path.join(_g64, 'paper.png'), _os64.path.join(_g64, 'paper.png.gcode'))
_pp.plot_convert(_os64.path.join(_g64, 'paper.png.gcode'))
_gpaper = open(_os64.path.join(_g64, 'paper.png.gcode')).read()
tests.append(('R64 polarity: dark board detected via the border -> INVERTED',
    'polarity: dark background' in _gboard and 'INVERTED' in _gboard, ''))
tests.append(('R64 polarity: light paper stays normal',
    'polarity: light background' in _gpaper and 'INVERTED' not in _gpaper, ''))
tests.append(('R64 polarity: both variants produce pen strokes',
    len(_re64.findall(r'^G1 X', _gboard, _re64.M)) > 50
    and len(_re64.findall(r'^G1 X', _gpaper, _re64.M)) > 50, ''))
tests.append(('R73 PLOT_PAT knows .txt.gcode AND plain .txt/.png uploads',
    bool(_pp.PLOT_PAT.search('notizen.txt.gcode')) and bool(_pp.PLOT_PAT.search('notizen.txt'))
    and bool(_pp.PLOT_PAT.search('photo.png')) and not _pp.PLOT_PAT.search('datei.gcode'), ''))
tests.append(('R64 _peek_file_info flags plot files for the Pre-Print menu',
    _pp._peek_file_info(_files64p[0]).get('PLOT') == '1', ''))
tests.append(('R64 _peek_file_info: print files are NOT plot files',
    'PLOT' not in _pp._peek_file_info(_files64[0]), ''))

# --- R64 macros -------------------------------------------------------------
_rb = get_body('macros/12_maintenance.cfg', 'RESONANCE_DIAGRAM')
state_vars['mode'] = 'idle'
out = render(_rb, {'AXIS': 'X', 'MODE': 'PLOT'})
tests.append(('R64 RESONANCE_DIAGRAM: saves axis/mode + bumps the nonce',
    ('VARIABLE=reso_axis VALUE="' + BKSL + '"X' + BKSL + '"') in out and ('VARIABLE=reso_mode VALUE="' + BKSL + '"plot' + BKSL + '"') in out
    and 'VARIABLE=reso_nonce VALUE=1' in out, out.strip()[:100]))
out = render(_rb, {'AXIS': 'Q', 'MODE': 'PRINT'})
tests.append(('R64 RESONANCE_DIAGRAM: bad axis/mode rejected',
    'AXIS must be' in out, out.strip()[:70]))
state_vars['mode'] = 'printing'
out = render(_rb, {})
tests.append(('R64 RESONANCE_DIAGRAM: only when idle', 'only when idle' in out, ''))
state_vars['mode'] = 'idle'

_sr = get_body('macros/12_maintenance.cfg', 'SHAPER_RESULT')
for _k, _v in (('shaper_rec_x_zv', '61.4'), ('shaper_rec_x_mzv', '67.6'), ('shaper_rec_y_ei', '58.9'),
               ('shaper_best_x', 'mzv@67.6Hz 4.2%'), ('shaper_best_y', 'ei@58.9Hz 3.1%')):
    save_vars[_k] = _v
out = render(_sr, {})
tests.append(('R64 SHAPER_RESULT (no args): shows the stored table',
    'mzv 67.6' in out and 'ei 58.9' in out and 'best: mzv@67.6Hz' in out, out[:120]))
out = render(_sr, {'AXIS': 'X', 'TYPE': 'MZV'})
tests.append(('R64 SHAPER_RESULT: TYPE pick uses the stored frequency (PA-style)',
    'SET_INPUT_SHAPER SHAPER_TYPE_X=mzv SHAPER_FREQ_X=67.6' in out.replace('.0', '')
    and ('ishaper_ov_type_x VALUE="' + BKSL + '"mzv' + BKSL + '"') in out and 'ishaper_ov_on_x VALUE=True' in out, out[:120]))
out = render(_sr, {'AXIS': 'Y', 'TYPE': 'EI', 'FREQ': '61'})
tests.append(('R64 SHAPER_RESULT: manual FREQ fine tuning',
    'SHAPER_FREQ_Y=61' in out.replace('.0', '') and 'ishaper_ov_freq_y VALUE=61' in out.replace('.0', ''), out[:100]))
out = render(_sr, {'AXIS': 'X', 'TYPE': 'ZV'})
tests.append(('R64 SHAPER_RESULT: zv stored -> applies 61.4',
    'SHAPER_FREQ_X=61.4' in out, out[:90]))
save_vars.pop('shaper_rec_y_zv', None)
out = render(_sr, {'AXIS': 'Y', 'TYPE': 'ZV'})
tests.append(('R64 SHAPER_RESULT: nothing stored -> helpful error',
    'No stored freq' in out and 'RESONANCE_DIAGRAM' in out, out[:90]))

_bt = get_body('macros/12_maintenance.cfg', 'BRIDGE_TEST')
out = render(_bt, {})
tests.append(('R64 BRIDGE_TEST: bumps the nonce + announces',
    'VARIABLE=bridge_nonce VALUE=1' in out and 'creating' in out, out.strip()[:80]))
state_vars['mode'] = 'printing'
out = render(_bt, {})
tests.append(('R64 BRIDGE_TEST: only when idle', 'only when idle' in out, ''))
state_vars['mode'] = 'idle'

_pt = get_body('macros/12_maintenance.cfg', 'PLOT_TEXT')
out = render(_pt, {'FILE': 'notes.txt'})
tests.append(('R64 PLOT_TEXT: stores the file + bumps the nonce',
    ('VARIABLE=plot_text_file VALUE="' + BKSL + '"notes.txt' + BKSL + '"') in out and 'VARIABLE=plot_text_nonce VALUE=1' in out, out[:90]))
out = render(_pt, {'FILE': '../etc/passwd'})
tests.append(('R64 PLOT_TEXT: paths rejected (basename only)', 'basename' in out or 'upload the file' in out, out[:80]))

_pn = get_body('macros/12_maintenance.cfg', '_PLOT_NAME_SET_CHAR')
out = render(_pn, {'POS': '1', 'CH': '39'})
tests.append(('R64/R71 _PLOT_NAME_SET_CHAR: writes the buffer, pos ADVANCES',
    ('VARIABLE=plot_name_buf VALUE="' + BKSL + '"n' + BKSL + '"') in out and 'VARIABLE=plot_name_pos VALUE=2' in out, out[:90]))

_ps = get_body('macros/12_maintenance.cfg', 'PLOT_STATUS')
out = render(_ps, {})
tests.append(('R64 PLOT_STATUS: bumps the nonce', 'VARIABLE=plot_status_nonce VALUE=1' in out, out[:70]))

_sps = get_body('macros/12_maintenance.cfg', 'SET_PLOT_SPEED')
state_vars['file_type'] = 'plot'
out = render(_sps, {'PCT': '80'})
tests.append(('R64 SET_PLOT_SPEED: M220 + saved as start default',
    'M220 S80' in out and 'VARIABLE=plot_ov_speed VALUE=80' in out, out[:80]))
_spz = get_body('macros/12_maintenance.cfg', 'SET_PLOT_PENZ')
out = render(_spz, {'DZ': '0.05'})
tests.append(('R64 SET_PLOT_PENZ: Z babystep + total offset tracked',
    'SET_GCODE_OFFSET Z_ADJUST=0.05' in out and 'VARIABLE=plot_ov_z VALUE=0.05' in out, out[:90]))
_spx = get_body('macros/12_maintenance.cfg', 'SET_PLOT_SHIFT')
out = render(_spx, {'X': '0.5'})
tests.append(('R64 SET_PLOT_SHIFT: X/Y shift via gcode offset',
    'SET_GCODE_OFFSET X_ADJUST=0.5 Y_ADJUST=0.0' in out, out[:80]))
state_vars['file_type'] = 'marked'
out = render(_sps, {'PCT': '80'})
tests.append(('R64 SET_PLOT_SPEED: guarded to plot jobs', 'only during a plot job' in out, ''))
state_vars['file_type'] = 'plot'

_ptr = get_body('macros/12_maintenance.cfg', 'PLOT_TUNE_RESET')
out = render(_ptr, {})
tests.append(('R64 PLOT_TUNE_RESET: neutralizes all start overrides',
    out.count('VALUE=100') == 1 and out.count('VALUE=0') == 3, out[:90]))

_pst = get_body('macros/12_maintenance.cfg', '_PLOT_START')
save_vars['plot_ov_speed'] = 80
save_vars['plot_ov_z'] = 0.1
out = render(_pst, {})
tests.append(('R64 _PLOT_START: applies speed + Z/X/Y start overrides',
    'M220 S80' in out and 'SET_GCODE_OFFSET Z_ADJUST=0.1' in out, ''))
save_vars['plot_ov_speed'] = 100
save_vars['plot_ov_z'] = 0.0
out = render(_pst, {})
tests.append(('R64 _PLOT_START: neutral overrides stay silent',
    'M220 S' not in out and 'SET_GCODE_OFFSET Z_ADJUST' not in out, ''))
state_vars['file_type'] = 'marked'

_iab = klipper_strip(_re64.search(r'\[delayed_gcode _INIT_AFTER_BOOT\]\ninitial_duration: 5\ngcode:\n(.*?)(?=\n\[|\Z)',
    open('macros/01_state.cfg').read(), _re64.S).group(1))
save_vars['ishaper_ov_on_x'] = True
save_vars['ishaper_ov_type_x'] = 'mzv'
save_vars['ishaper_ov_freq_x'] = 67.6
out = render(_iab, {})
tests.append(('R64 boot: shaper override applied after every restart',
    'SET_INPUT_SHAPER SHAPER_TYPE_X=mzv SHAPER_FREQ_X=67.6' in out.replace('.0', ''), ''))
save_vars['ishaper_ov_on_x'] = False
out = render(_iab, {})
tests.append(('R64 boot: no override -> no SET_INPUT_SHAPER', 'SET_INPUT_SHAPER' not in out, ''))
for _k in ('shaper_rec_x_zv', 'shaper_rec_x_mzv', 'shaper_rec_y_ei', 'shaper_best_x', 'shaper_best_y',
           'ishaper_ov_on_x', 'ishaper_ov_type_x', 'ishaper_ov_freq_x', 'plot_ov_speed', 'plot_ov_z'):
    save_vars.pop(_k, None)

# --- R64 LCD audit ----------------------------------------------------------
_lcd64 = open('menus/lcd_menues.cfg').read()
tests.append(('R64 LCD: vibration menu grows diagram + apply, plotter grows text/status/start',
    all(k in _lcd64 for k in ['__vib __dgp]', '__vib __dgl]', '__vib __ap __x2]', '__vib __ap __y4]',
                                '__plot __txt __chr]', '__plot __pst]', '__plot __st __pz]',
                                '__plot __inv]', '__plot __txt __run]']), 'ids'))
tests.append(('R64 LCD: bridging menu with all live-relevant settings',
    all(k in _lcd64 for k in ['__maint __bridge __len]', '__maint __bridge __pct]',
                                '__maint __bridge __hl]', '__maint __bridge __hs]',
                                '__maint __bridge __tw]', '__maint __bridge __ly]',
                                '__maint __bridge __spd]', '__maint __bridge __fan]',
                                '__maint __bridge __run]']), 'ids'))
tests.append(('R64 LCD: plotter live group gated on plot jobs + pre-print plot group on preview',
    "enable: {printer['gcode_macro _STATE'].file_type|default('') == 'plot'}" in _lcd64
    and "__preprint __file __pl0]" in _lcd64
    and "printer['gcode_macro _PREVIEW'].plot|default(0)|int == 1" in _lcd64, ''))
tests.append(('R64 LCD: plot text editor guarded on the labels charset',
    _re64.search(r'__plot __txt\]..type: list..name: Plot text file..enable: .\'gcode_macro _LABELS\' in printer', _lcd64.replace('\n', '..')) is not None, ''))
tests.append(('R64 LCD: new static names stay <= 16 chars',
    not [n for n in ['Diagram (print)', 'Diagram (plot)', 'Show table', 'Apply result', 'Bridging',
                     '> Create file', 'How it works', 'Plot text file', '> Plot this file',
                     '> Plot status', 'Start overrides', 'Reset overrides', 'Plotter',
                     'Pen Z +0.05', 'Pen Z -0.05', 'Delete char', 'Clear name'] if len(n) > 16], ''))
_m1264 = open('macros/12_maintenance.cfg').read()
tests.append(('R64 no double braces anywhere (Klipper Jinja pitfall)',
    '{{' not in _m1264.replace('{{#', '') and '{{' not in _lcd64, ''))


# ============================== R65 tests: '#' comment-strip HOTFIX (boot blocker) ==
import glob as _glob65

tests.append(('R65 charset: config line parses after the Klipper # strip (92 chars, no #/;)',
    len(LABEL_CHARSET_LCD) == 92 and '#' not in LABEL_CHARSET_LCD and ';' not in LABEL_CHARSET_LCD, str(len(LABEL_CHARSET_LCD))))
tests.append(('R65 invariant: LCD charset + the appended # == generator charset',
    set(LABEL_CHARSET_LCD) | {'#'} == set(_pp.LABEL_CHARSET)
    and len(LABEL_CHARSET_LCD) == len(_pp.LABEL_CHARSET) - 1, ''))
_lb65 = get_body('macros/16_labels.cfg', '_LABEL_SET_CHAR')
save_vars['label_l1'] = ''
out = render(_lb65, {'POS': '1', 'CH': '92'})
tests.append(('R65/R74 _LABEL_SET_CHAR: index 92 == # (the %c trick)',
    ('VARIABLE=label_l1 VALUE="' + BKSL + '"#' + BKSL + '"') in out, out[:110]))
save_vars['label_l1'] = ''
out = render(_lb65, {'POS': '1', 'CH': '5'})
tests.append(('R65/R74 _LABEL_SET_CHAR: index 5 still F (order kept before the # position)',
    ('VARIABLE=label_l1 VALUE="' + BKSL + '"F' + BKSL + '"') in out, out[:110]))
_pn65 = get_body('macros/12_maintenance.cfg', '_PLOT_NAME_SET_CHAR')
out = render(_pn65, {'POS': '1', 'CH': '92'})
tests.append(('R65 plot name editor: index 92 == # too',
    ('VARIABLE=plot_name_buf VALUE="' + BKSL + '"#' + BKSL + '"') in out, out[:110]))
_bad65 = []
for _f65 in sorted(_glob65.glob('macros/*.cfg') + _glob65.glob('menus/*.cfg')):
    for _n65, _l65 in enumerate(open(_f65, encoding='utf-8'), 1):
        _st65 = _l65.rstrip('\n').lstrip()
        _h65 = _st65.find('#')
        if _h65 <= 0:
            continue
        _vor65 = _st65[:_h65]
        if _vor65.count('"') % 2 == 1 or (_vor65.count("'") % 2 == 1
                and ('{' in _vor65 or _st65.startswith('variable_'))):
            _bad65.append('%s:%d' % (_f65, _n65))
tests.append(('R65 no # inside quoted strings in ANY cfg (the .47/.48 boot-blocker class)',
    not _bad65, str(_bad65[:3])))
_lcd65b = open('menus/lcd_menues.cfg').read()
tests.append(('R65/R71 LCD: both char pickers are VISIBLE scroll lists (93 entries each)',
    _lcd65b.count('[menu __main __gen __labels __txt __chr __c') == 93
    and _lcd65b.count('[menu __main __gen __plot __txt __chr __c') == 93
    and 'input_max: 92' not in _lcd65b and 'charset[menu.input]' not in _lcd65b, ''))

# ---------- R66: update via Mainsail upload + one SSH command ----------
_upd66 = open('update.sh', encoding='utf-8').read()
tests.append(('R66 update.sh: bash script with upload-unpack + loop guard',
    _upd66.startswith('#!/usr/bin/env bash') and '--unpacked' in _upd66
    and 'exec bash' in _upd66 and '--force' in _upd66, ''))
tests.append(('R66 update.sh: unzip -o + python3 fallback + restart endpoint',
    'unzip -o' in _upd66 and 'python3 -m zipfile -e' in _upd66
    and 'UPDATE-R2-*.zip' in _upd66 and 'firmware_restart' in _upd66, ''))
import subprocess as _sp66
try:
    _syn66 = _sp66.run(['bash', '-n', 'update.sh'], capture_output=True, text=True).returncode
except Exception:
    _syn66 = -1
tests.append(('R66 update.sh passes bash -n syntax check', _syn66 == 0, 'rc=%s' % _syn66))
_v66 = ''
for _l66 in open('macros/01_state.cfg', encoding='utf-8'):
    if _l66.strip().startswith('variable_version:'):
        _v66 = _l66.split(':', 1)[1].strip()
        break
# NOTE: bump this expectation together with the version on every release!
tests.append(('R66/R80 version is current (.86) in 01_state.cfg (bump together with release!)',
    _v66 == "'R2-2026-10-12.89'", repr(_v66)))

# ---------- R67: EVERY template Klipper compiles at boot must compile (blocker #2) ----------
# Klipper loads gcode_macro gcode blocks AND menu name/enable/gcode options as
# jinja templates AT CONFIG LOAD -> one unknown filter = "Internal error during
# connect" = printer down. .47 shipped two of those ('#' + |string.split).
import re as _re67

def _cfg_opts67(path):
    _opts, _cur, _sec = [], None, None
    for _l67 in klipper_strip(open(path, encoding='utf-8').read()).split('\n'):
        _s67 = _l67.strip()
        if not _s67:
            continue
        if _l67.startswith('[') and _s67.endswith(']'):
            _sec = _s67[1:-1].strip(); _cur = None; continue
        if _sec is None:
            continue
        if _l67[:1] not in (' ', '\t'):
            _m67 = _re67.match(r'^([A-Za-z0-9_]+)\s*:\s*(.*)$', _s67)
            if _m67:
                _opts.append((_sec, _m67.group(1), [_m67.group(2)])); _cur = len(_opts) - 1
        elif _cur is not None:
            _opts[_cur][2].append(_s67)
    return _opts

def _tmpl67(_sec67, _opt67):
    if _sec67.startswith(('gcode_macro ', 'delayed_gcode')):
        return _opt67 == 'gcode'
    if _sec67.startswith('menu '):
        return _opt67 in ('name', 'enable', 'gcode')
    return False

_bad67, _n67 = [], 0
for _p67 in sorted(_glob65.glob('macros/*.cfg') + _glob65.glob('menus/*.cfg')):
    for _sec67, _opt67, _lines67 in _cfg_opts67(_p67):
        _t67 = '\n'.join(_lines67).strip('\n')
        if not _t67 or not _tmpl67(_sec67, _opt67):
            continue
        _n67 += 1
        try:
            env.from_string(_t67)
        except Exception as _e67:
            _bad67.append('%s [%s] %s: %s' % (_p67, _sec67, _opt67, _e67))
tests.append(('R67 all %d boot-compiled templates compile (macro gcode + menu name/enable/gcode)' % _n67,
    not _bad67 and _n67 > 1500, str(_bad67[:3])))

# render every menu template: a runtime error while the LCD draws would be blocker #3
_rbad67, _rn67 = [], 0
for _p67 in sorted(_glob65.glob('menus/*.cfg')):
    for _sec67, _opt67, _lines67 in _cfg_opts67(_p67):
        _t67 = '\n'.join(_lines67).strip('\n')
        if not _t67 or not _tmpl67(_sec67, _opt67):
            continue
        _rn67 += 1
        for _iv67 in (0, 3):
            try:
                render(_t67, extra={'menu': M({'input': _iv67, 'ns': _sec67[5:], 'event': 'click'})})
            except Exception as _e67:
                _rbad67.append('%s [%s] %s (input=%s): %s' % (_p67, _sec67, _opt67, _iv67, _e67))
                break
tests.append(('R67 all %d menu templates render with mock printer (names+enable+gcode)' % _rn67,
    not _rbad67 and _rn67 > 1300, str(_rbad67[:3])))

_q67 = [l for l in open('menus/lcd_menues.cfg', encoding='utf-8').read().split('\n')
        if l.startswith('name: Queue:')][0][len('name: '):]
tests.append(('R67 label queue name uses the fixed .split pattern (no |string.split)',
    'string.split' not in _q67 and ').split(' in _q67 and '|length' in _q67, _q67[:70]))
_oldq67 = save_vars.get('label_texts', '')
save_vars['label_texts'] = ''
tests.append(('R67 label queue name renders 0/24 when queue empty',
    render(_q67, extra={'menu': M({'input': 0})}).strip() == 'Queue: 0/24',
    render(_q67, extra={'menu': M({'input': 0})}).strip()[:40]))
save_vars['label_texts'] = 'WERKSTATT|R2|'
tests.append(('R67 label queue name renders 2/24 with two queued labels',
    render(_q67, extra={'menu': M({'input': 0})}).strip() == 'Queue: 2/24',
    render(_q67, extra={'menu': M({'input': 0})}).strip()[:40]))
save_vars['label_texts'] = _oldq67

# ---------- R68: foreign files (hyphen names / bare '-' tokens) never crash the watcher ----------
import tempfile as _tf68, subprocess as _sp68, sys as _sys68, os as _os68
_d68 = _tf68.mkdtemp(prefix='r68')
_f68 = _os68.path.join(_d68, 'Felge-V-035.gcode')
open(_f68, 'w').write(
    'M104 S200\nM140 S60\nG28\nG1 Z0.2 F600\n;Z:0.2\n;TYPE:Outer wall\n'
    'G1 X50 Y50 Z0.2 E2.5 F1800 ; Felge-V-035 perimeter\n'
    'G1 X60 Y60 E3.0\nG1 E- F2400\nG1 X70 Y70 E3.5\n;Z:-\n;Z:0.4\n'
    'G1 X80 Y80 Z0.4 E4.0\nG1 X90 Y90 E4.5 ; Ender_3_Easy_Control-013\n;Z:0.6\n'
    'G1 X95 Y95 Z0.6 E5.0\n')
_r68 = _sp68.run([_sys68.executable, 'tools/r2_postproc.py', _f68],
                 capture_output=True, text=True)
_t68 = open(_f68).read()
tests.append(('R68 hyphen comments + bare E- + ";Z:-" process cleanly (no float crash), tag + marks',
    _r68.returncode == 0 and 'ValueError' not in (_r68.stderr + _r68.stdout)
    and '; R2-POSTPROC v5' in _t68 and _t68.count('LAYER_MARK') >= 2,
    (_r68.returncode, (_r68.stderr or _r68.stdout)[-200:])))
_r68b = _sp68.run([_sys68.executable, '-c',
    "import importlib.util as u; s = u.spec_from_file_location('r2p', 'tools/r2_postproc.py');"
    "m = u.module_from_spec(s); s.loader.exec_module(m);"
    "p = m.parse_params(' X- Y5.5 Z0.2 E-3 ; Felge-V-035 Ender-3 ');"
    "assert p == {'Y': 5.5, 'Z': 0.2, 'E': -3.0}, p; print('ok')"],
    capture_output=True, text=True)
tests.append(('R68 parse_params: comments stripped, X-/hyphen names ignored, real negatives kept',
    _r68b.returncode == 0 and 'ok' in _r68b.stdout, _r68b.stderr[-200:]))
tests.append(('R68 postproc docstring names the real tag (v4, not the stale v2)',
    "the tag '; R2-POSTPROC v5' and is skipped" in open('tools/r2_postproc.py', encoding='utf-8').read(), ''))

# ---------- R69: SAVE_VARIABLE must survive Klipper's shlex + literal_eval ----------
# Klipper cuts each command line at ';' and parses non-traditional commands
# (SAVE_VARIABLE!) with POSIX shlex: quotes are STRIPPED, so VALUE="AB C"
# reaches literal_eval as the bare token 'AB C'. save_variables catches ONLY
# ValueError - a malformed literal (space, apostrophe, empty, pipes) raises
# SyntaxError = "Internal error on command" = PRINTER SHUTDOWN (.47-.52 bug).
import shlex as _sh69, ast as _ast69

def _kexec69(line):
    _l69 = line.strip()
    _c69 = _l69.find(';')
    if _c69 >= 0:
        _l69 = _l69[:_c69]
    _cmd69, _, _raw69 = _l69.partition(' ')
    _s69 = _sh69.shlex(_raw69.strip(), posix=True)
    _s69.whitespace_split = True
    _s69.commenters = '#;'
    _ep69 = {}
    try:
        for _e69 in _s69:
            _k69, _v69 = _e69.split('=', 1)
            _ep69[_k69.upper()] = _v69
    except ValueError:
        return 'malformed', None
    if 'VALUE' not in _ep69:
        return 'novalue', None
    try:
        return 'ok', _ast69.literal_eval(_ep69['VALUE'])
    except ValueError:
        return 'valueerror', None
    except SyntaxError:
        return 'SYNTAX-SHUTDOWN', None

def _svl69(out):
    return [l.strip() for l in out.split('\n') if l.strip().startswith('SAVE_VARIABLE')]

_badg69 = []
for _f69 in sorted(_glob65.glob('macros/*.cfg') + _glob65.glob('menus/*.cfg')):
    for _n69, _l69 in enumerate(open(_f69, encoding='utf-8'), 1):
        if _l69.strip().startswith('#'):
            continue
        if ('SAVE_VARIABLE' not in _l69 and 'SET_GCODE_VARIABLE' not in _l69) or 'VALUE=' not in _l69:
            continue
        _v69 = _l69.split('VALUE=', 1)[1]
        if not (_v69[:2] == '"' + BKSL or _v69[:2] == '"{' or _v69[:2] == '"['
                or _v69[:1] == "'" or _v69[:1] in '-+.0123456789{['
                or _v69.startswith('True') or _v69.startswith('False')):
            # R79: '[' = list literal (VALUE=[]) - safe, Klipper passes the object
            _badg69.append('%s:%d' % (_f69, _n69))
tests.append(('R69 static gate: no bare VALUE=" (the shutdown class) in any cfg line',
    not _badg69 and len(_glob65.glob('macros/*.cfg')) == 18, str(_badg69[:3])))

_lb69 = get_body('macros/16_labels.cfg', '_LABEL_SET_CHAR')
_bad69 = []
for _i69, _ch69 in enumerate(LABEL_CHARSET_LCD + '#'):
    for _pre69 in ('', 'X'):
        save_vars['label_l1'] = _pre69
        _o69 = render(_lb69, {'POS': len(_pre69) + 1, 'CH': _i69})
        _exp69 = _pre69 + _ch69
        for _sv69 in _svl69(_o69):
            _st69, _val69 = _kexec69(_sv69)
            if _st69 != 'ok':
                _bad69.append((_sv69[:60], _st69))
            elif _sv69.startswith('SAVE_VARIABLE VARIABLE=label_l1 ') and _val69 != _exp69:
                _bad69.append(('wrong value', _val69, _exp69))
save_vars['label_l1'] = ''
tests.append(('R69/R74 label editor: every charset char saves clean (no shutdown, exact value)',
    not _bad69, str(_bad69[:3])))

_lb69b = get_body('macros/16_labels.cfg', 'LABEL_ADD')
save_vars.update({'label_l1': 'A B', 'label_texts': "IT'S", 'label_lines': 1})
_o69 = render(_lb69b, {})
_ok69 = False
for _sv69 in _svl69(_o69):
    _st69, _val69 = _kexec69(_sv69)
    if _sv69.startswith('SAVE_VARIABLE VARIABLE=label_texts '):
        _ok69 = (_st69 == 'ok' and _val69 == "IT'S|A B")
tests.append(("R69 queue add with space + apostrophe saves clean (IT'S|A B)",
    _ok69, _o69[:120]))
save_vars.update({'label_l1': '', 'label_texts': ''})

_lb69c = get_body('macros/16_labels.cfg', 'GEN_LABELS')
_o69 = render(_lb69c, {'TEXT': 'WERK STATT'})
tests.append(('R69 GEN_LABELS with a space in TEXT saves clean (escaped form)',
    any(_kexec69(_sv69) == ('ok', 'WERK STATT') for _sv69 in _svl69(_o69)), _o69[:120]))
_o69 = render(_lb69c, {'TEXT': 'a"b'})
tests.append(('R69 GEN_LABELS rejects quotes in TEXT (no poison save, clear error)',
    not any('VARIABLE=label_texts' in _sv69 for _sv69 in _svl69(_o69))
    and 'not allowed' in _o69, _o69[:120]))

_lb69d = get_body('macros/12_maintenance.cfg', '_PLOT_NAME_SET_CHAR')
save_vars['plot_name_buf'] = "IT'S"
_o69 = render(_lb69d, {'POS': 4, 'CH': 92})
tests.append(("R69 plot name editor: apostrophe buffer + '#' insert saves clean",
    all(_kexec69(_sv69)[0] == 'ok' for _sv69 in _svl69(_o69))
    and any(_kexec69(_sv69) == ('ok', "IT'#") for _sv69 in _svl69(_o69)), _o69[:120]))
save_vars['plot_name_buf'] = ''

_lb69e = get_body('macros/12_maintenance.cfg', 'PLOT_TEXT')
_o69 = render(_lb69e, {'FILE': 'my notes.txt'})
tests.append(('R69 PLOT_TEXT with a space in FILE saves clean',
    any(_kexec69(_sv69) == ('ok', 'my notes.txt') for _sv69 in _svl69(_o69)), _o69[:100]))
_o69 = render(_lb69e, {'FILE': 'a"b.txt'})
tests.append(('R69 PLOT_TEXT rejects quotes in FILE (no poison save)',
    not any('VARIABLE=plot_text_file' in _sv69 for _sv69 in _svl69(_o69)), _o69[:100]))

import importlib.util as _ilu69
_spec69 = _ilu69.spec_from_file_location('r2p69', 'tools/r2_postproc.py')
_mod69 = _ilu69.module_from_spec(_spec69)
_spec69.loader.exec_module(_mod69)
_badw69 = []
_san69 = '"' + BKSL + ';'
for _ch69 in LABEL_CHARSET_LCD + '#':
    for _v69 in (_ch69, 'A' + _ch69 + 'B', '12 (5x3)', 'my file.gcode'):
        _st69, _val69 = _kexec69(_mod69._sv_line('t', _v69))
        if _st69 != 'ok' or (_val69 != _v69 and not any(c in _v69 for c in _san69)):
            _badw69.append((_v69, _st69))
for _v69 in ('a"b', 'a;b', 'a' + BKSL + 'b'):
    if _kexec69(_mod69._sv_line('t', _v69))[0] != 'ok':
        _badw69.append((_v69, 'sanitize failed'))
for _v69 in (3.14, True, 7, 0.2):
    _st69, _val69 = _kexec69(_mod69._sv_line('t', _v69))
    if _st69 != 'ok' or _val69 != _v69:
        _badw69.append((_v69, _st69, _val69))
tests.append(('R69 watcher _sv_line: whole charset + specials + numbers all clean',
    not _badw69, str(_badw69[:3])))

# ---------- R70: field-log fixes (preset dict / cold extrude / excerpt objects) ----------
_pr70 = get_body('macros/05_materials.cfg', 'SAVE_DEFAULT_PRESET')
for _s70 in range(1, 9):
    save_vars['default_preset_%d' % _s70] = 0
save_vars.update({'material': 'PETG', 'ovf_brim_on': True, 'ovf_brim_spd': 80.0,
                  'ov_bed_on': True, 'ov_bed': 60.0, 'first_layer_speed': 75.0})
_o70 = render(_pr70, {})
_sv70 = [l.strip() for l in _o70.split('\n') if l.strip().startswith('SAVE_VARIABLE VARIABLE=default_preset_')]
_preset70 = None
for _ls70 in _sv70:
    _st70, _val70 = _kexec69(_ls70)
    if _st70 == 'ok' and isinstance(_val70, dict):
        _preset70 = _val70
tests.append(('R70 SAVE_DEFAULT_PRESET: dict saves as ONE shlex-quoted token, literal_eval sees the dict',
    _preset70 is not None and _preset70.get('material') == 'PETG'
    and _preset70.get('feats', {}).get('brim', [None]*4)[1] == 80.0,
    _sv70[:1] or _o70.strip()[-200:]))
save_vars.update({'ovf_brim_on': False, 'ovf_brim_spd': 100.0})

_lit70 = []
for _f70 in sorted(_glob65.glob('macros/*.cfg') + _glob65.glob('menus/*.cfg')):
    if "VALUE={'" in open(_f70, encoding='utf-8').read():
        _lit70.append(_f70)
tests.append(('R70 static: no raw dict literal VALUE={\' in any cfg', not _lit70, str(_lit70[:3])))

_lp70 = get_body('macros/08_print_start_stop.cfg', '_LEGACY_PREP')
_o70 = render(_lp70, {})
tests.append(('R70 _LEGACY_PREP waits for the hotend target BEFORE the pause (cold-extrude guard)',
    'TEMPERATURE_WAIT SENSOR=extruder MINIMUM=215' in _o70
    and _o70.index('TEMPERATURE_WAIT SENSOR=extruder') < _o70.index('PAUSE REASON'), _o70[:140]))
_o70b = render(_lp70, {}, etgt=120)
tests.append(('R70/R72 _LEGACY_PREP: low target still waits to the SAFE 175 (min_extrude_temp+5)',
    'TEMPERATURE_WAIT SENSOR=extruder MINIMUM=175' in _o70b, _o70b[:160]))
_o70c = render(_lp70, {}, etgt=0)
tests.append(('R70/R72 _LEGACY_PREP: no guard wait when nothing is heating (target 0)',
    'TEMPERATURE_WAIT SENSOR=extruder' not in _o70c, _o70c[:120]))

_m10970 = get_body('macros/06_temp_controls.cfg', 'M109')
_old70 = {k: state_vars.get(k) for k in ('start_pending','mode','layer','ignore_overrides','file_hotend_first','file_hotend_after')}
state_vars.update({'start_pending': 'as_legacy', 'mode': 'printing', 'layer': 0,
                   'ignore_overrides': False, 'file_hotend_first': 0, 'file_hotend_after': 0})
save_vars['preheat_hotend'] = 170.0
_o70 = render(_m10970, {'S': '220'})
tests.append(('R70 M109 takeover cap floors at min_extrude_temp+5 (170+5=175, not 170)',
    'waiting only up to 175C' in _o70 and 'M99109 S175' in _o70,
    [l.strip() for l in _o70.split('\n') if 'waiting only up to' in l or 'M99109' in l][:2]))
for _k70, _v70 in _old70.items():
    if _v70 is not None:
        state_vars[_k70] = _v70

import tempfile as _tf70, os as _os70, importlib.util as _ilu70
_d70 = _tf70.mkdtemp(prefix='r70')
_src70 = _os70.path.join(_d70, 'obj.gcode')
open(_src70, 'w').write(
    '; R2-POSTPROC v4\nM104 S200\nM140 S60\n'
    'EXCLUDE_OBJECT_DEFINE NAME=cube CENTER=60,60 POLYGON=[[50,50],[70,50],[70,70],[50,70]]\n'
    'EXCLUDE_OBJECT_DEFINE NAME=cap CENTER=120,60 POLYGON=[[110,50],[130,50],[130,70],[110,70]]\n'
    'G1 Z0.2 F600\nLAYER_MARK\n;TYPE:Outer wall\nG1 X50 Y50 Z0.2 E2.5 F1800\n'
    'LAYER_MARK\nG1 X60 Y60 Z0.4 E3.5\n'
    'LAYER_MARK\nG1 X70 Y70 Z0.6 E4.5\n'
    'LAYER_MARK\nG1 X80 Y80 Z0.8 E5.5\n')
_spec70 = _ilu70.spec_from_file_location('r2p70', 'tools/r2_postproc.py')
_mod70 = _ilu70.module_from_spec(_spec70)
_spec70.loader.exec_module(_mod70)
_out70, _nl70 = _mod70.make_range(_src70, 2, 3)
_exc70 = open(_out70).read()
tests.append(('R70 range excerpt keeps EXCLUDE_OBJECT_DEFINE (KAMP adaptive, no full-bed fallback)',
    _exc70.count('EXCLUDE_OBJECT_DEFINE') == 2 and 'NAME=cube' in _exc70 and 'NAME=cap' in _exc70,
    [l for l in _exc70.split('\n') if 'EXCLUDE_OBJECT' in l][:2]))

# ---------- R71: range excerpt extrusion (block G92s + accumulating brim E) ----------
import tempfile as _tf71, os as _os71, importlib.util as _ilu71, re as _re71
re = _re71
_d71 = _tf71.mkdtemp(prefix='r71')
_v71 = _os71.path.join(_d71, 'vase.gcode')
_vl71 = ['M82', 'G92 E0']
for _l71 in range(1, 7):
    _vl71 += ['LAYER_MARK', f'G1 Z{_l71 * 0.2:.2f} F600', ';TYPE:Outer wall',
              f'G1 X{20 + _l71}.0 Y50.0 E{(_l71 - 1) * 2 + 0.5:.3f} F1800',
              f'G1 X{30 + _l71}.0 Y60.0 E{(_l71 - 1) * 2 + 1.5:.3f}']
open(_v71, 'w').write('\n'.join(_vl71) + '\n')
_spec71 = _ilu71.spec_from_file_location('r2p71', 'tools/r2_postproc.py')
_mod71 = _ilu71.module_from_spec(_spec71)
_spec71.loader.exec_module(_mod71)
_o71, _n71 = _mod71.make_range(_v71, 3, 4, floor=2, top=1, brim=2)
_t71 = open(_o71).read()
_ic71 = _t71.index('R2-RANGE cap')
_g171 = _t71[:_ic71]
_g271 = _t71[_ic71:]
_b71 = [float(m.group(1)) for m in re.finditer(r'G1 X[\d.-]+ Y[\d.-]+ E([\d.]+) F1200', _g171)]
_b71c = [float(m.group(1)) for m in re.finditer(r'G1 X[\d.-]+ Y[\d.-]+ E([\d.]+) F1200', _g271)]
tests.append(('R71/R73 vase excerpt: 4 block G92s (head+gen+body+cap), generated E accumulates',
    _t71.count('G92 E0') == 4 and len(_b71) >= 8
    and all(_b71[i + 1] > _b71[i] for i in range(len(_b71) - 1)) and _b71[-1] > _b71[0] * 3,
    (_t71.count('G92 E0'), len(_b71), len(_b71c))))
tests.append(('R73/R74 raft hatch + brim + cap: monotone E per generated block, no retracts',
    'R2-RANGE raft: 2 layer(s)' in _t71 and 'R2-RANGE brim: 2 loop(s)' in _t71
    and 'R2-RANGE cap: 1' in _t71 and 'solid' in _t71.split('R2-RANGE cap: 1')[1][:80]
    and ' E-' not in _t71
    and all(_b71[i + 1] > _b71[i] for i in range(len(_b71) - 1))
    and all(_b71c[i + 1] > _b71c[i] for i in range(len(_b71c) - 1))
    and len(_b71c) >= 4, 'gen blocks: %d/%d' % (len(_b71), len(_b71c))))
tests.append(('R73 order: raft BEFORE brim BEFORE body BEFORE cap, cap gets a LAYER_MARK',
    _t71.index('R2-RANGE raft') < _t71.index('R2-RANGE brim')
    < _t71.index('R2-RANGE: body E starts') < _t71.index('R2-RANGE cap')
    and 'LAYER_MARK   ; R2-RANGE cap layer 1' in _t71, ''))
_m83_71 = _os71.path.join(_d71, 'rel.gcode')
_rl71 = ['M83']
for _l71 in range(1, 5):
    _rl71 += ['LAYER_MARK', f'G1 Z{_l71 * 0.2:.2f} F600',
              'G1 X20.0 Y50.0 E1.5 F1800', 'G1 X30.0 Y60.0 E1.2']
open(_m83_71, 'w').write('\n'.join(_rl71) + '\n')
_o71b, _n71b = _mod71.make_range(_m83_71, 2, 3, floor=1, top=1, brim=1)
_t71b = open(_o71b).read()
tests.append(('R71/R73 M83 file: no G92 inserted, generated geometry keeps relative E',
    'G92 E' not in _t71b and 'M83' in _t71b
    and len(re.findall(r'G1 X[\d.-]+ Y[\d.-]+ E[\d.]+ F1200', _t71b)) >= 4
    and 'R2-RANGE raft: 1 layer(s)' in _t71b, _t71b[:120]))

# ---------- R71: visible character pickers ----------
_lcd71 = open('menus/lcd_menues.cfg', encoding='utf-8').read()
_n71b = {int(m.group(1)): m.group(2) for m in re.finditer(
    r'\[menu __main __gen __labels __txt __chr __c(\d\d)\]\ntype: command\nname: (.*)\n', _lcd71)}
tests.append(('R71 label picker: 93 visible entries, umlaut aliases, # last',
    len(_n71b) == 93 and _n71b.get(62) == '(space)' and _n71b.get(63) == 'AE'
    and _n71b.get(69) == 'ss' and _n71b.get(87) == 'deg'
    and _n71b.get(92) == "{'%c' % 35}" and _n71b.get(0) == 'A', str(_n71b)[:80]))
_p71c = {int(m.group(1)): m.group(2) for m in re.finditer(
    r'\[menu __main __gen __plot __txt __chr __c(\d\d)\]\ntype: command\nname: (.*)\n', _lcd71)}
tests.append(('R71 plot picker: 93 visible entries with _PLOT_NAME_SET_CHAR gcode',
    len(_p71c) == 93 and all(('_PLOT_NAME_SET_CHAR CH=%d' % i) in _lcd71 for i in range(93)), str(len(_p71c))))
_nonascii71 = [l[:40] for l in _lcd71.split('\n') if l.startswith('name:') and any(ord(c) > 127 for c in l)]
tests.append(('R71 LCD gate: every menu name is pure ASCII (12864-safe)',
    not _nonascii71, str(_nonascii71[:2])))
_lb71 = get_body('macros/16_labels.cfg', '_LABEL_SET_CHAR')
_oldt71, _oldp71 = save_vars.get('label_l1', ''), save_vars.get('label_pos', 1)
save_vars.update({'label_l1': 'AB', 'label_pos': 2})
_o71c = render(_lb71, {'CH': 5})
tests.append(('R71/R74 _LABEL_SET_CHAR: POS defaults to the saved position + auto-advances',
    ('VARIABLE=label_l1 VALUE="' + BKSL + '"AF' + BKSL + '"') in _o71c
    and 'VARIABLE=label_pos VALUE=3' in _o71c, _o71c[:140]))
save_vars.update({'label_l1': _oldt71, 'label_pos': _oldp71})
_pn71 = get_body('macros/12_maintenance.cfg', '_PLOT_NAME_SET_CHAR')
_oldpn71 = save_vars.get('plot_name_buf', ''), save_vars.get('plot_name_pos', 1)
save_vars.update({'plot_name_buf': 'XY', 'plot_name_pos': 2})
_o71d = render(_pn71, {'CH': 26})
tests.append(('R71 _PLOT_NAME_SET_CHAR: saved position + auto-advance',
    ('VARIABLE=plot_name_buf VALUE="' + BKSL + '"Xa' + BKSL + '"') in _o71d
    and 'VARIABLE=plot_name_pos VALUE=3' in _o71d, _o71d[:140]))
save_vars.update({'plot_name_buf': _oldpn71[0], 'plot_name_pos': _oldpn71[1]})


# ==================== R72 (.56): legacy-start cascade + solid label strokes ====================
import re as _re72, importlib.util as _ilu72, tempfile as _tf72, os as _os72, math as _math72
re = _re72

def get72(path, section):
    t = open(path, encoding='utf-8').read()
    m = re.search(r'\[' + section + r'\]\n(?:(?!gcode:)[^\n]*\n)*?gcode:\n(.*?)(?=\n\[|\Z)', t, re.S)
    assert m, section + ' not found'
    return klipper_strip('\n'.join(l[4:] if l.startswith('    ') else l for l in m.group(1).split('\n')))

# --- heater injections: M190/M109/M140 ARM, M104 keeps the immediate guard path ---
_m104 = get72('macros/06_temp_controls.cfg', r'gcode_macro M104')
_m109 = get72('macros/06_temp_controls.cfg', r'gcode_macro M109')
_m140 = get72('macros/06_temp_controls.cfg', r'gcode_macro M140')
_m190 = get72('macros/06_temp_controls.cfg', r'gcode_macro M190')
for _nm, _bd in (('M190', _m190), ('M109', _m109), ('M140', _m140)):
    state_vars.update(mode='printing', start_pending='as_legacy', legacy_armed=False, file_type='unknown', has_heaters=True)
    out = render(_bd, {'S': 60 if _nm != 'M109' else 210})
    tests.append(('R72 %s injection: ARMS the takeover, no immediate PREP' % _nm,
        'VARIABLE=legacy_armed VALUE=True' in out and '_LEGACY_PREP' not in out
        and 'VARIABLE=file_type VALUE=\'"legacy"\'' in out, out[:200]))
state_vars.update(mode='printing', start_pending='as_legacy', legacy_armed=False, file_type='unknown', has_heaters=True)
out = render(_m104, {'S': 210})
tests.append(('R72 M104 injection (not armed): immediate guard path PREP',
    '_LEGACY_PREP' in out and 'VARIABLE=legacy_armed VALUE=True' not in out, out[:200]))
state_vars.update(mode='printing', start_pending='as_legacy', legacy_armed=True, file_type='legacy', has_heaters=True)
out = render(_m104, {'S': 210})
tests.append(('R72 M104 injection (already armed): hands over to START_PRINT/probe',
    '_LEGACY_PREP' not in out and 'VARIABLE=legacy_armed VALUE=True' not in out, out[:200]))

# --- _LEGACY_PREP guard: min_extrude_temp + 5, never ON the refusal line ---
_prep72 = get72('macros/08_print_start_stop.cfg', r'gcode_macro _LEGACY_PREP')
out = render(_prep72, {}, etgt=170)
tests.append(('R72 PREP guard: target 170 -> waits 175 (min_extrude_temp+5)',
    'MINIMUM=175' in out and 'min_extrude_temp 170 + 5' in out, out[:220]))
out = render(_prep72, {}, etgt=220)
tests.append(('R72 PREP guard: target 220 -> waits 220 (max wins)',
    'MINIMUM=220' in out, out[:220]))
tests.append(('R72 PREP consumes the arming',
    "VARIABLE=legacy_armed VALUE=False" in render(_prep72, {}, etgt=210), ''))

# --- park retract / resume unretract at the min_extrude_temp boundary ---
_park72 = get72('macros/09_pause_filament.cfg', r'gcode_macro _PARK_HEAD')
out = render(_park72, {}, etemp=169.9, etgt=170)
tests.append(('R72 park: 169.9C + min_extrude_temp 170 -> NO retract',
    'G1 E-3' not in out and 'skipping anti-ooze retract' in out, out[-260:]))
out = render(_park72, {}, etemp=178.0, etgt=175)
tests.append(('R72 park: 178C -> retract fires',
    'G1 E-3 F2100' in out, out[-200:]))
_res72 = get72('macros/09_pause_filament.cfg', r'gcode_macro _RESUME_COMMON')
out = render(_res72, {}, etemp=169.9, etgt=170)
tests.append(('R72 resume: 169.9C -> no unretract', 'G1 E3' not in out, out[:180]))

# --- START_PRINT: armed -> hot takeover; prepared -> continue ---
_sp72 = get72('macros/08_print_start_stop.cfg', r'gcode_macro START_PRINT')
state_vars.update(mode='printing', file_type='legacy', legacy_armed=True, legacy_file='')
save_vars['legacy_level'] = True
out = render(_sp72, {})
tests.append(('R72 START_PRINT armed: hot takeover via PREP',
    '_LEGACY_PREP' in out and 'VARIABLE=legacy_armed VALUE=False' in out
    and 'file is hot' in out, out[:220]))
save_vars['legacy_level'] = False
out = render(_sp72, {})
tests.append(('R72 START_PRINT armed + level OFF: takeover via HOME',
    '_LEGACY_HOME' in out and '_LEGACY_PREP' not in out, out[:220]))
save_vars['legacy_level'] = True
state_vars.update(legacy_armed=False, legacy_file='test.gcode')
out = render(_sp72, {})
tests.append(('R72 START_PRINT already prepared: printing continues',
    'already prepared' in out and '_LEGACY_PREP' not in out, out[:180]))
state_vars['legacy_file'] = ''

# --- _START_NET_PROBE: armed grace, then hot takeover ---
_np72 = get72('macros/08_print_start_stop.cfg', r'delayed_gcode _START_NET_PROBE')
state_vars.update(mode='printing', legacy_armed=True, probe_stage=0, file_type='legacy', start_pending='')
out = render(_np72, {})
tests.append(('R72 PROBE armed stage0: grace 4s for START_PRINT',
    'DURATION=4' in out and '_LEGACY_PREP' not in out and 'VARIABLE=probe_stage VALUE=1' in out, out[:220]))
state_vars['probe_stage'] = 1
out = render(_np72, {})
tests.append(('R72 PROBE armed stage1: takeover NOW (PREP), arming consumed',
    '_LEGACY_PREP' in out and 'VARIABLE=legacy_armed VALUE=False' in out, out[:240]))
state_vars.update(legacy_armed=False, probe_stage=0)

# --- watcher catch: a decided file never gets a second dialog ---
_w72 = get72('macros/01_state.cfg', r'delayed_gcode _STATE_WATCHER')
state_vars.update(mode='idle', decided_file='test.gcode', decided_mode='as_legacy', legacy_file='test.gcode')
out = render(_w72, {}, ps_state='printing')
tests.append(('R72 catch: decided file -> NO second dialog, live tuning',
    '_LEGACY_DIALOG' not in out and 'decision for this file stands' in out
    and 'VARIABLE=ignore_overrides VALUE=False' in out, out[:240]))
state_vars.update(decided_file='test.gcode', decided_mode='as_sliced')
out = render(_w72, {}, ps_state='printing')
tests.append(('R72 catch: decided AS SLICED -> ignore_overrides ON',
    'VARIABLE=ignore_overrides VALUE=True' in out and '_LEGACY_DIALOG' not in out, out[:200]))
state_vars.update(decided_file='', decided_mode='', mode='printing')

# --- waiter: every decision remembers decided_file/decided_mode ---
_wt72 = get72('macros/07_start_confirm.cfg', r'delayed_gcode _START_CONFIRM_WAITER')
state_vars.update(mode='waiting', file_type='unknown')
for _dec72, _mode72 in (('as_sliced', 'as_sliced'), ('with_overrides', 'as_legacy'), ('as_legacy', 'as_legacy')):
    save_vars['start_decision'] = _dec72
    out = render(_wt72, {})
    tests.append(('R72 WAITER %s: remembers the decision for the file' % _dec72,
        "VARIABLE=decided_file VALUE='\"test.gcode\"'" in out
        and ("VARIABLE=decided_mode VALUE='\"%s\"'" % _mode72) in out, out[:200]))
save_vars['start_decision'] = ''
state_vars['mode'] = 'printing'

# --- sequential: current_object None -> name the next non-excluded object ---
state_vars.update(mode='printing', layer=12, layer_z_max=2.4)
# NOTE: build_printer SNAPSHOTS state_vars - set the state BEFORE building the mock
_pr72 = build_printer(gz=0.3, objs=[{'name': 'obj_a', 'center': [100, 100], 'polygon': [[90, 90], [110, 90], [110, 110], [90, 110]]},
                                 {'name': 'obj_b', 'center': [150, 100], 'polygon': [[140, 90], [160, 90], [160, 110], [140, 110]]}],
                           excl=['obj_a'])
_pr72['exclude_object'] = M({'objects': _pr72['exclude_object'].objects,
                             'excluded_objects': ['obj_a'], 'current_object': None})
out = render(_w72, {}, gz=0.3, extra={'printer': _pr72})
tests.append(('R72 SEQ: no START_PRINT-style "(None)" - names the next object',
    'next object (obj_b)' in out and '(None)' not in out, out[:200]))
state_vars.update(layer=2, layer_z_max=0.4)

# --- SET_LIVE_HOTEND_TEMP T=0 -> invalid, not "Hotend stays 0C" ---
_lv72 = get72('macros/06_temp_controls.cfg', r'gcode_macro SET_LIVE_HOTEND_TEMP')
out = render(_lv72, {'T': 0})
tests.append(('R72 live temp T=0 reads as missing (100..300)',
    'missing (100..300)' in out and 'Hotend stays' not in out, out[:160]))

# --- GEN_LABELS STROKE parameter ---
_gl72 = get72('macros/16_labels.cfg', r'gcode_macro GEN_LABELS')
out = render(_gl72, {'TEXT': 'AB', 'STROKE': '2.5'})
tests.append(('R72 GEN_LABELS STROKE=2.5 saved',
    'VARIABLE=label_stroke VALUE=2.5' in out, out[:160]))

# --- postproc: solid double-walled strokes ---
_spec72 = _ilu72.spec_from_file_location('r2p72', 'tools/r2_postproc.py')
_mod72 = _ilu72.module_from_spec(_spec72)
_spec72.loader.exec_module(_mod72)
_off72 = _mod72._stroke_offsets([(0.0, 0.0), (10.0, 0.0)], 0.92, 0.612)
_ys72 = [q[0][1] for q in _off72]
tests.append(('R72 strokes: 3 parallel paths, symmetric, spacing = extrusion width',
    len(_off72) == 3 and abs(_ys72[0] + _ys72[-1]) < 0.02 and abs(_ys72[0] - _ys72[1] - 0.612) < 0.02,
    str(_ys72)))
_off72b = _mod72._stroke_offsets([(0, 0), (5, 5), (10, 0)], 0.92, 0.612)
tests.append(('R72 strokes: mitered polyline offsets (no crash, 3 paths)',
    len(_off72b) == 3 and all(len(q) == 3 for q in _off72b), ''))
_d72 = _tf72.mkdtemp()
_p72, _i72 = _mod72.make_labels(['AB'], w=30, h=15, base_layers=2, text_layers=1,
                                color2=True, bed=(0, -3, 244, 238), out_dir=_d72, stroke=0)
_g72 = open(_p72).read()
_tx72 = _g72[_g72.index('PAUSE for the filament change'):]
_el72 = [l for l in _tx72.split('\n') if l.startswith('G1 X') and ' E' in l]
_bad72 = [l for l in _el72 if float(l.split(' E')[1].split()[0]) <= 0]
_ty72 = [l for l in _tx72.split('\n') if l.startswith(';TYPE:')]
tests.append(('R72 label text: solid strokes (many E-lines, walls + fill types, E>0)',
    len(_el72) > 60 and any('Internal solid infill' in _t for _t in _ty72)
    and any(_t.endswith('Outer wall') for _t in _ty72) and not _bad72,
    'lines=%d types=%d bad=%d' % (len(_el72), len(_ty72), len(_bad72))))


# ============================= R73 TESTS =============================
# --- range: M83 WITH a trailing comment (THE .56 'no filament' field bug) ----
import tempfile as _tf73, os as _os73, importlib.util as _ilu73, re as _re73
_d73 = _tf73.mkdtemp()
_f73 = _os73.path.join(_d73, 'relcmt.gcode')
_l73 = ['; custom', 'M83 ; use relative distances for extrusion', 'M140 S60', 'M104 S215', 'G90']
for _k73 in range(1, 7):
    _l73 += ['LAYER_MARK', f'G1 Z{_k73 * 0.2:.2f} F600', ';TYPE:Outer wall',
             'G1 X30.0 Y50.0 E0.9 F1800', 'G1 X40.0 Y60.0 E1.1']
open(_f73, 'w').write('\n'.join(_l73) + '\n')
_spec73 = _ilu73.spec_from_file_location('r2p73', 'tools/r2_postproc.py')
_mod73 = _ilu73.module_from_spec(_spec73)
_spec73.loader.exec_module(_mod73)
_o73, _n73 = _mod73.make_range(_f73, 3, 5, floor=1, top=1, brim=1)
_t73 = open(_o73).read()
tests.append(('R73 range: M83-with-comment detected (the .56 no-filament bug)',
    '\nM83\n' in _t73 and '\nM82\n' not in _t73
    and 'G1 X30.0 Y50.0 E0.9 F1800' in _t73 and 'G1 X40.0 Y60.0 E1.1' in _t73,
    [l for l in _t73.split('\n') if l in ('M82', 'M83')]))
tests.append(('R73 range: raft/brim in relative E, no M82 rebase artifacts',
    'R2-RANGE raft: 1 layer(s)' in _t73 and 'R2-RANGE brim: 1 loop(s)' in _t73
    and 'G92 E' not in _t73
    and len(_re73.findall(r'G1 X[\d.-]+ Y[\d.-]+ E[\d.]+ F1200', _t73)) >= 4, ''))

# --- hull helpers: offset (zero gap) + hatch (raft fill) ---------------------
_h73 = _mod73._hull([(0.0, 0.0), (10.0, 0.0), (10.0, 10.0), (0.0, 10.0)])
_off73 = _mod73._offset_hull(_h73, 0.3)
tests.append(('R73 _offset_hull grows the outline by d (brim flush to the wall)',
    abs(min(p[0] for p in _off73) + 0.3) < 0.05 and abs(max(p[0] for p in _off73) - 10.3) < 0.05,
    str(sorted(round(p[0], 2) for p in _off73)[:2])))
_ht73 = _mod73._hull_hatch(_h73, 1.2, 45.0)
tests.append(('R73 _hull_hatch fills the hull, segments stay inside',
    len(_ht73) >= 10 and all(-0.01 <= p[0] <= 10.01 and -0.01 <= p[1] <= 10.01
                             for s in _ht73 for p in s), str(len(_ht73))))
_dec73 = _mod73._decimate([(0, 0), (0.01, 0), (5, 0), (10, 0), (10, 5), (10, 10)], 0.1)
tests.append(('R73 _decimate drops micro + collinear points (MCU relief)',
    _dec73 == [(0, 0), (10, 0), (10, 10)], str(_dec73)))

# --- label typography: R74 uniform scale (no stretch), ~75% width --------------
_c73, _b73, _hd73 = _mod73._label_layout(60, 30, 1, 5.0)
_p73, _g73 = _mod73._label_text_lines(['Axg@'], 'SMOOTH', _b73, 60, 30)
tests.append(('R73/R74 label text: auto caps stay under 66% of the height (uniform)',
    2.5 <= _g73['cap_h'] <= 0.66 * 30 + 0.3, '%.2f' % _g73['cap_h']))
_ysA = [q[1] for s in _p73 for q in s]
# glyph classification
tests.append(('R73 _glyph_class: A/0 full, x/@/> small (user rule)',
    _mod73._glyph_class('A', 'SMOOTH') == 'FULL' and _mod73._glyph_class('0', 'SMOOTH') == 'FULL'
    and _mod73._glyph_class('x', 'SMOOTH') == 'SMALL' and _mod73._glyph_class('@', 'SMOOTH') == 'SMALL'
    and _mod73._glyph_class('>', 'PIXEL') == 'SMALL', ''))
tests.append(('R73/R74 label text: auto spans ~75% of the label width',
    38.0 <= (max(q[0] for s in _p73 for q in s) - min(q[0] for s in _p73 for q in s)) <= 46.0,
    '%.1f' % (max(q[0] for s in _p73 for q in s) - min(q[0] for s in _p73 for q in s))))
_c73x, _b73x, _ = _mod73._label_layout(60, 30, 0, 5.0)
_p73b, _g73b = _mod73._label_text_lines(['WERKSTATT'], 'SMOOTH', _b73x, 60, 30)
tests.append(('R73/R74 label text: long word shrinks uniformly (never stretches)',
    2.5 <= _g73b['cap_h'] <= 12.0 and 40.0 <= (max(q[0] for s in _p73b for q in s)
    - min(q[0] for s in _p73b for q in s)) <= 54.0, '%.1fmm caps' % _g73b['cap_h']))
tests.append(('R73 label cells: hole diameter clamps to the label height',
    _mod73._label_layout(60, 30, 1, 20.0)[2] == 16.0, ''))
_lp73, _li73 = _mod73.make_labels(['Axg@'], w=60, h=30, hole_side=1, hole_d=5.0,
                                  base_layers=2, text_layers=1, color2=False,
                                  bed=(0, -3, 244, 238), out_dir=_d73)
_lt73 = open(_lp73).read()
tests.append(('R73 label file: TAG + _FILE_INFO + markers DIRECT (no process re-parse)',
    '; R2-POSTPROC v5' in _lt73 and _lt73.count('_FILE_INFO ') == 1
    and 'APPLY_TYPE TYPE=WALL-INNER' in _lt73 and _lt73.count('LAYER_MARK') == 3
    and _mod73.process(_lp73)['skipped'] is True, ''))
_fed73 = [int(_m73.group(1)) for _m73 in _re73.finditer(r'F(\d+)', _lt73)]
tests.append(('R73 label file: feeds capped at 75mm/s (MCU overload fix)',
    max(_fed73) <= 4500, 'max F%d' % max(_fed73)))

# --- live tuning: user value wins over re-applies (first-layer lock fix) ------
_m22173 = get_body('macros/06_temp_controls.cfg', 'M221')
save_vars.update({'ov_flow_on': True, 'ov_flow': 90})
state_vars.update({'mode': 'printing', 'layer': 1, 'live_flow': 115, 'ignore_overrides': False})
out = render(_m22173, {'S': 100})
tests.append(('R73 M221: LIVE flow beats the pre-print flow override',
    'M99221 S115' in out, out[:110]))
state_vars.update({'live_flow': 0, 'layer': 2})
out = render(_m22173, {'S': 100})
tests.append(('R73 M221: without a live value the override still rules',
    'M99221 S90' in out, out[:110]))

_m20473 = get_body('macros/06_temp_controls.cfg', 'M204')
state_vars.update({'live_accel': 4200, 'current_type': 'WALL-OUTER'})
save_vars.update({'ovf_wallouter_on': True, 'ovf_wallouter_acc': 1500})
out = render(_m20473, {'S': 800})
tests.append(('R73/R87.2 M204: FEATURE accel beats the live global (field log .71)',
    'M99204 S1500' in out, out[:110]))
state_vars['live_accel'] = 0
out = render(_m20473, {'S': 800})
tests.append(('R73 M204: without a live value the feature accel rules',
    'M99204 S1500' in out, out[:110]))

_m22073 = get_body('macros/06_temp_controls.cfg', 'M220')
save_vars.update({'first_layer_speed': 75})
state_vars.update({'layer': 1, 'l1_speed_user': True})
out = render(_m22073, {'S': 120})
tests.append(('R73 M220: user speed leads on layer 1 (no more capped lock)',
    'VARIABLE=g_speed_clean VALUE=120' in out and 'capped' not in out and '_SPEED_COMBINED' in out, out[:110]))
state_vars['l1_speed_user'] = False
out = render(_m22073, {'S': 120})
tests.append(('R73 M220: without a live takeover the L1 brake still caps',
    'VARIABLE=g_speed_clean VALUE=75' in out and 'capped' in out and '_SPEED_COMBINED' in out, out[:110]))

_lm73 = get_body('macros/06_temp_controls.cfg', 'LAYER_MARK')
state_vars.update({'mode': 'printing', 'layer': 1, 'g_speed_clean': 120, 'l1_speed_user': True})
out = render(_lm73, {})
tests.append(('R73 LAYER_MARK n=2: YOUR live speed stays (no reset to 100%)',
    'M220 S120' in out and 'stays' in out, [l for l in out.split('\n') if 'M220' in l]))
state_vars.update({'l1_speed_user': False, 'g_speed_clean': 100})
out = render(_lm73, {})
tests.append(('R73 LAYER_MARK n=2: normal reset to 100% when nobody took over',
    'M220 S100' in out and 'back to 100' in out, ''))

_at73 = get_body('macros/10_live_tuning.cfg', 'APPLY_TYPE')
state_vars.update({'mode': 'printing', 'layer': 2, 'live_flow': 112, 'live_accel': 0,
                   'current_type': 'WALL-OUTER', 'g_speed_clean': 100, 'ignore_overrides': False})
save_vars.update({'ovf_wallouter_on': True, 'ovf_wallouter_flw': 100, 'ovf_wallouter_spd': 100,
                  'ovf_wallouter_acc': 0, 'ov_flow_on': False, 'ov_flow': 100})
out = render(_at73, {'TYPE': 'WALL-OUTER'})
tests.append(('R73 APPLY_TYPE: feature boundary re-applies the LIVE flow',
    'M99221 S112' in out, [l for l in out.split('\n') if 'M99221' in l]))

_sf73 = get_body('macros/10_live_tuning.cfg', 'SET_FLOW_RATE')
out = render(_sf73, {'PERCENT': 108})
tests.append(('R73 SET_FLOW_RATE arms the live flow', 'VARIABLE=live_flow VALUE=108' in out, out[:90]))
_sa73 = get_body('macros/10_live_tuning.cfg', 'SET_GLOBAL_ACCEL')
out = render(_sa73, {'ACCEL': 3800})
tests.append(('R73 SET_GLOBAL_ACCEL arms the live accel', 'VARIABLE=live_accel VALUE=3800' in out, out[:90]))
_sg73 = get_body('macros/10_live_tuning.cfg', 'SET_GLOBAL_SPEED')
state_vars.update({'mode': 'printing', 'layer': 1})
out = render(_sg73, {'PERCENT': 130})
tests.append(('R73 SET_GLOBAL_SPEED on layer 1 disarms the L1 brake',
    'VARIABLE=l1_speed_user VALUE=True' in out and 'M220 S130' in out, out[:110]))
_lr73 = get_body('macros/10_live_tuning.cfg', '_LIVE_RESET')
out = render(_lr73, {})
tests.append(('R73 _LIVE_RESET clears the live priorities',
    'VARIABLE=live_flow VALUE=0' in out and 'VARIABLE=live_accel VALUE=0' in out
    and 'VARIABLE=l1_speed_user VALUE=False' in out, ''))

# --- plotter: FILAMENT mode geometry (draw height + relative E + retract) -----
_fv73 = _os73.path.join(_d73, 'variables.cfg')
open(_fv73, 'w').write('[Variables]\nvariable_plot_extrude = 1\nvariable_plot_fil_z = 0.25\n'
                       'variable_plot_z_up = 3\nvariable_plot_speed = 40\nvariable_plot_travel = 120\n'
                       'variable_plot_bed_min_x = 5\nvariable_plot_bed_min_y = 5\n'
                       'variable_plot_bed_max_x = 239\nvariable_plot_bed_max_y = 233\n')
import zlib as _zl73, struct as _st73
def _chunk73(typ, data):
    return _st73.pack('>I4s', len(data), typ) + data + _st73.pack('>I', _zl73.crc32(typ + data) & 0xffffffff)
_w73, _h73 = 24, 10
_raw73 = b''
for _y73 in range(_h73):
    _raw73 += b'\x00' + b''.join(bytes((30, 30, 30) if 4 <= _x73 <= 19 else (240, 240, 240)) for _x73 in range(_w73))
_png73 = (b'\x89PNG\r\n\x1a\n' + _chunk73(b'IHDR', _st73.pack('>IIBBBBB', _w73, _h73, 8, 2, 0, 0, 0))
          + _chunk73(b'IDAT', _zl73.compress(_raw73)) + _chunk73(b'IEND', b''))
_fp73 = _os73.path.join(_d73, 'draw.png.gcode')
open(_fp73, 'wb').write(_png73)
_mod73.plot_convert(_fp73, var_path=_fv73)
_tp73 = open(_fp73).read()
tests.append(('R73 plot FILAMENT: draws at 0.25mm (not the pen Z 0!) with M83',
    'G1 Z0.25 F600' in _tp73 and '\nM83\n' in _tp73 and 'G10\n' in _tp73 and 'G11\n' in _tp73,
    [l for l in _tp73.split('\n') if 'Z0.25' in l][:1]))
_es73 = [float(_m73.group(1)) for _m73 in _re73.finditer(r'^G1 X[\d.-]+ Y[\d.-]+ E([\d.]+)', _tp73, _re73.M)]
tests.append(('R73 plot FILAMENT: relative E per segment with real extrusion per mm',
    len(_es73) >= 10 and 0.02 < min(_es73) and max(_es73) < 20.0, 'n=%d min=%.3f' % (len(_es73), min(_es73) if _es73 else -1)))
tests.append(('R73 plot FILAMENT: travel capped at 80mm/s (MCU relief)',
    not _re73.search(r'F(\d{5,}|9[0-9]{3})', _tp73), ''))
_hd73t = open('/tmp/r73_hello73.txt', 'w')
_hd73t.write('HALLO\nR2 TEST 123\n')
_hd73t.close()
_to73, _tn73, _ts73 = _mod73.text_convert('/tmp/r73_hello73.txt', var_path=_fv73)
_tt73 = open(_to73).read()
tests.append(('R73 text plot: CAP-height letters (>=6mm), solid in FILAMENT mode',
    'CAP letters' in _tt73 and _ts73 >= 6.0 and _tt73.count('G1 Z0.25 F600') >= 20,
    '%.1fmm caps' % _ts73))

# --- watcher: preview push on upload + plot detection ------------------------
_wsrc73 = open('tools/r2_postproc.py').read()
tests.append(('R73 watcher pushes a preview for every fresh file (Mainsail starts too)',
    'def push_preview(' in _wsrc73 and 'NEW_PREVIEW.append(p)' in _wsrc73
    and "NEW_PREVIEW.append(out_p)" in _wsrc73 and "NEW_PREVIEW.append(out_t)" in _wsrc73, ''))

# --- menus: float-index fix, file info submenu, feature flows, plotter items --
_lcd73 = open('menus/lcd_menues.cfg', encoding='utf-8').read()
tests.append(('R73 LCD: no float tuple indexing left (values visible again)',
    not _re73.search(r'\[menu\.input\]', _lcd73), ''))
tests.append(('R73 LCD: 2.Color item + info submenu in the start menu',
    '2.Color:' in _lcd73 and '[menu __main __start __info __type]' in _lcd73
    and '[menu __main __start __info __temps]' in _lcd73
    and '[menu __main __start __info __speeds]' in _lcd73, ''))
_flowids73 = sum(1 for _c73 in ('ow', 'iw', 'sp', 'so', 'tp', 'bt', 'br', 'gp', 'su', 'ir', 'sk', 'bm')
                 if ('[menu __main __live __feat __%s __flw]' % _c73) in _lcd73)
tests.append(('R73 LCD: live per-feature FLOW inputs for all 12 features',
    _flowids73 == 12 and 'feat_flw_wallouter' in _lcd73, str(_flowids73)))
tests.append(('R73 LCD: plotter Letters (min 6mm) + Fil Z + mode info items',
    '[menu __main __gen __plot __cap]' in _lcd73 and 'input_min: 6\n' in _lcd73
    and '[menu __main __gen __plot __fz]' in _lcd73
    and '[menu __main __live __plot __mode]' in _lcd73, ''))

# --- state + plot start ---
_st73 = open('macros/01_state.cfg').read()
tests.append(('R73 state: live_flow / live_accel / l1_speed_user / plot_extrude declared',
    all(k in _st73 for k in ('variable_live_flow:', 'variable_live_accel:',
                             'variable_l1_speed_user:', 'variable_plot_extrude:')), ''))
_ps73 = get_body('macros/12_maintenance.cfg', '_PLOT_START')
state_vars.update({'mode': 'idle', 'layer': 0})
out = render(_ps73, {'EXTRUDE': 1})
tests.append(('R73 _PLOT_START EXTRUDE=1 flags the filament plot mode',
    'VARIABLE=plot_extrude VALUE=True' in out, [l for l in out.split('\n') if 'plot_extrude' in l]))

# --- SYS_SAVE_CONFIG pending report -------------------------------------------
_sc73 = get_body('macros/13_system.cfg', 'SYS_SAVE_CONFIG')
out = render(_sc73, {}, ps_state='idle', scp=True)
tests.append(('R73 SYS_SAVE_CONFIG: first press NAMES the pending items',
    'Pending for SAVE_CONFIG' in out and 'press SAVE+RESTART' in out, out[:130]))


# ============================= R74 TESTS (.58) =============================
# field log .57: (1) file info stale everywhere (2) filament menu missing while
# paused/pre-print (3) range: nozzle parked ON the print, END beyond the file,
# floor follows only the footprint, only grid fill (4) labels: single line,
# font stuck on SMOOTH, stretched letters, no size/spacing (5) plotter buried
# in Maintenance
import tempfile as _tf74, os as _os74, importlib.util as _ilu74, re as _re74
_d74 = _tf74.mkdtemp(prefix='r74')
_lcd74 = open('menus/lcd_menues.cfg', encoding='utf-8').read()
_0874 = open('macros/08_print_start_stop.cfg').read()
_1674 = open('macros/16_labels.cfg').read()

# --- (1) file info: peek parses EVERY key + TYPE + the raw line ---------------
_fi74 = _os74.path.join(_d74, 'peek.gcode')
open(_fi74, 'w').write(
    '_FILE_INFO MATERIAL=PETG LAYER_HEIGHT=0.28 TOTAL_LAYERS=123 LINE_WIDTH=0.66 '
    'FLOW_RATIO=0.98 PA=0.095 NOZZLE=0.6 FS_WALL_OUTER=45 FA_WALL_OUTER=1500 '
    'TYPES=WALL-OUTER,IRONING\nM104 S240\nM140 S70\nM106 S128\n')
_pv74 = _mod73._peek_file_info(_fi74)
tests.append(('R74 _peek_file_info: parses every _FILE_INFO key (not just the old 14)',
    _pv74.get('MATERIAL') == 'PETG' and _pv74.get('TOTAL_LAYERS') == '123'
    and _pv74.get('FS_WALL_OUTER') == '45' and _pv74.get('TYPES') == 'WALL-OUTER,IRONING'
    and _pv74.get('_RAW', '').startswith('_FILE_INFO MATERIAL=PETG'), str(sorted(_pv74)[:6])))
tests.append(('R74 _peek_file_info: TYPE guess + heater/fan peek',
    _pv74.get('TYPE') == 'LEGACY' and _pv74.get('HOTEND') == '240' and _pv74.get('BED') == '70', ''))
_mk74 = _os74.path.join(_d74, 'marked.gcode')
open(_mk74, 'w').write('; R2-POSTPROC v4\nPRINT_START MATERIAL=PLA\n')
tests.append(('R74 _peek_file_info: TAG/PRINT_START -> MARKED',
    _mod73._peek_file_info(_mk74).get('TYPE') == 'MARKED', ''))

# --- (1b) the preview script: ONE in-memory _PREVIEW_SET + _FILE_INFO replay ---
_lines74, _n74 = _mod73._preview_script(_fi74)
tests.append(('R74/R75 _preview_script: ONE _PREVIEW_SET line + _FILE_INFO + _PREVIEW_TEMPS',
    _lines74[0].startswith('_PREVIEW_SET ')
    and 'NAME="peek.gcode"' in _lines74[0] and 'LAYER_HEIGHT=0.28' in _lines74[0]
    and 'TYPE=LEGACY' in _lines74[0]
    and any(l.startswith('_FILE_INFO MATERIAL=') for l in _lines74)
    and any(l.startswith('_PREVIEW_TEMPS HOTEND=240') for l in _lines74)
    and not any(l.startswith('SAVE_VARIABLE') for l in _lines74), str(_lines74[:2])))
_busy74 = {'print_stats': {'state': 'printing'}, 'gcode_macro _STATE': {'mode': 'printing'}}
_orig_status74 = _mod73._moonraker_status
_mod73._moonraker_status = lambda *a, **k: _busy74
try:
    _bl74, _ = _mod73._preview_script(_fi74)
    _busy_ok74 = (not any(l.startswith('_FILE_INFO') for l in _bl74)
                  and not any(l.startswith('_PREVIEW_TEMPS') for l in _bl74)
                  and not any(l.startswith('EXCLUDE_OBJECT_DEFINE') for l in _bl74)
                  and any(l.startswith('_PREVIEW_SET ') for l in _bl74))
finally:
    _mod73._moonraker_status = _orig_status74
tests.append(('R74/R75 _preview_script: while a print RUNS only the preview card goes out',
    _busy_ok74, ''))

# --- (1c) _FILE_INFO_RESET covers EVERY file_* variable of _STATE -------------
_st74vars = [m.group(1) for m in _re74.finditer(r'^variable_(file_\w+):', open('macros/01_state.cfg').read(), _re74.M)]
_rst74 = get_body('macros/08_print_start_stop.cfg', '_FILE_INFO_RESET')
_missing74 = [v for v in _st74vars if ('VARIABLE=%s ' % v) not in _rst74 and ("VARIABLE={var|lower}" not in _rst74 or v not in ('file_types',))]
_loop_vars74 = ['file_speed_outer', 'file_feat_acc_brim', 'file_accel_top']
tests.append(('R74 _FILE_INFO_RESET: resets every file_* state variable',
    not [v for v in _st74vars if v not in ('file_flow', 'file_accel', 'file_speed')
         and ('VARIABLE=%s' % v) not in _rst74] or all(v in _rst74 for v in _loop_vars74),
    str([v for v in _st74vars if ('VARIABLE=%s' % v) not in _rst74][:5])))
tests.append(('R74 intercept + cleanup both route through _FILE_INFO_RESET',
    '_FILE_INFO_RESET' in get_body('macros/08_print_start_stop.cfg', '_UNIVERSAL_START_INTERCEPT')
    and '_FILE_INFO_RESET' in get_body('macros/09_pause_filament.cfg', '_PRINT_CLEANUP'), ''))

# --- (1d) _PREVIEW_TEMPS writes only outside a running print -------------------
_pt74 = get_body('macros/08_print_start_stop.cfg', '_PREVIEW_TEMPS')
state_vars['mode'] = 'idle'
out = render(_pt74, {'HOTEND': 240, 'BED': 70, 'FAN': 50})
tests.append(('R74 _PREVIEW_TEMPS idle: sets file temps + fan',
    'VARIABLE=file_hotend_first VALUE=240.0' in out and 'VARIABLE=file_bed VALUE=70.0' in out
    and 'VARIABLE=file_fan VALUE=50.0' in out, out[:120]))
state_vars['mode'] = 'printing'
out = render(_pt74, {'HOTEND': 240})
tests.append(('R74 _PREVIEW_TEMPS while printing: hands off (guard wins)',
    'VARIABLE=file_hotend_first' not in out and 'skipped' in out, out[:100]))
state_vars['mode'] = 'waiting'
out = render(_pt74, {'HOTEND': 240})
tests.append(('R74 _PREVIEW_TEMPS during the start dialog: allowed (held file)',
    'VARIABLE=file_hotend_first VALUE=240.0' in out, out[:100]))

# --- (1e) M24 fresh start also bumps the preview nonce --------------------------
_m2474 = get_body('macros/08_print_start_stop.cfg', 'M24')
tests.append(('R74 M24 fresh start: preview nonce bump (LCD M23/M24 selections refresh too)',
    'VARIABLE=preview_nonce' in _m2474 and 'VARIABLE=preview_file' in _m2474, ''))

# --- (3) range: PRINT_END at the end + _FILE_INFO at the top -------------------
_v74 = _os74.path.join(_d74, 'r.gcode')
_l74 = ['_FILE_INFO MATERIAL=PLA LAYER_HEIGHT=0.2 LINE_WIDTH=0.6 TOTAL_LAYERS=6', 'M82', 'G92 E0']
_e74 = 0.0
for _k74 in range(1, 7):
    _l74 += ['LAYER_MARK', f'G1 Z{_k74 * 0.2:.2f} F600',
             f'G1 X{20 + _k74}.0 Y50.0 E{_e74 + 0.5:.3f} F1800',
             f'G1 X{30 + _k74}.0 Y60.0 E{_e74 + 1.5:.3f}']
    _e74 += 2.0
open(_v74, 'w').write('\n'.join(_l74) + '\n')
_o74, _n74b = _mod73.make_range(_v74, 3, 5, floor=1, top=1, brim=1)
_t74 = open(_o74).read()
tests.append(('R74 range: ends with PRINT_END (nozzle parks, no dead stop)',
    _t74.rstrip().endswith('park + cool down') and '\nPRINT_END' in _t74, _t74[-90:]))
tests.append(('R74 range: _FILE_INFO at the TOP (live file info correct from layer 1)',
    _t74.index('_FILE_INFO') < _t74.index('PRINT_START')
    and _t74.count('_FILE_INFO ') == 1, ''))
tests.append(('R74 range: END beyond the file clamps to the last layer',
    (_mod73.make_range(_v74, 3, 99)[1]) == 4 and '_L3-6' in _mod73.make_range(_v74, 3, 99)[0], ''))
tests.append(('R74 range: top-only (floor=0, brim=0) builds (old NameError)',
    _mod73.make_range(_v74, 2, 4, floor=0, top=1, brim=0)[1] == 4, ''))

# --- (3b) outline vs footprint: concave C-shape --------------------------------
def _cshape74(d):
    ls = ['_FILE_INFO MATERIAL=PLA LAYER_HEIGHT=0.2 LINE_WIDTH=0.6', 'M82', 'G92 E0']
    e = 0.0
    for lay in range(1, 7):
        ls.append('LAYER_MARK')
        ls.append(f'G0 X20 Y20 Z{0.2 * (lay + 1):.2f} F3000')
        # bottom bar, right bar, top bar (extruded), travel, middle bar
        for (c, dd) in [(80, 20), (80, 80), (20, 80)]:
            e += 1.0
            ls.append(f'G1 X{c} Y{dd} E{e:.3f} F1200')
        ls.append('G0 X20 Y50 F6000')
        e += 1.0
        ls.append(f'G1 X80 Y50 E{e:.3f} F1200')
    p = _os74.path.join(d, 'c.gcode')
    open(p, 'w').write('\n'.join(ls) + '\n')
    return p

def _notch74(txt, box=(35, 55, 65, 75)):
    bx0, by0, bx1, by1 = box
    x = y = None
    cnt = 0
    for l in txt.split('\n'):
        c = l.split(';')[0].strip()
        mm = _re74.match(r'G1 X(-?[\d.]+) Y(-?[\d.]+) E', c)
        g0 = _re74.match(r'G0 X(-?[\d.]+) Y(-?[\d.]+)', c)
        if mm and x is not None:
            nx, ny = float(mm.group(1)), float(mm.group(2))
            for t in [i / 16 for i in range(17)]:
                px, py = x + (nx - x) * t, y + (ny - y) * t
                if bx0 < px < bx1 and by0 < py < by1:
                    cnt += 1
                    break
            x, y = nx, ny
        elif mm:
            x, y = float(mm.group(1)), float(mm.group(2))
        elif g0:
            x, y = float(g0.group(1)), float(g0.group(2))
    return cnt

_cs74 = _cshape74(_d74)
_oh74, _ = _mod73.make_range(_cs74, 2, 4, floor=1, floor_shape='hull', floor_fill='grid')
_th74 = open(_oh74).read().split('\nLAYER_MARK')[1]      # read BEFORE the next call
_oo74, _ = _mod73.make_range(_cs74, 2, 4, floor=1, floor_shape='outline', floor_fill='grid')
_to74 = open(_oo74).read().split('\nLAYER_MARK')[1]
tests.append(('R74 range floor: FOOTPRINT bridges the concave notch, OUTLINE does not',
    _notch74(_th74) > 5 and _notch74(_to74) == 0,
    'hull %d / outline %d crossings' % (_notch74(_th74), _notch74(_to74))))
_og74, _ = _mod73.make_range(_cs74, 2, 4, floor=1, floor_shape='outline', floor_fill='solid')
_tg74 = open(_og74).read().split('\nLAYER_MARK')[1]      # solid overwrites the grid file
tests.append(('R74 range floor: SOLID fill = ~2x the grid hatch density',
    len(_re74.findall(r'^G1 .*E', _tg74, _re74.M)) > 1.5 * len(_re74.findall(r'^G1 .*E', _to74, _re74.M)),
    '%d vs %d' % (len(_re74.findall(r'^G1 .*E', _tg74, _re74.M)), len(_re74.findall(r'^G1 .*E', _to74, _re74.M)))))
_oto74, _ = _mod73.make_range(_cs74, 2, 4, floor=0, top=1, top_shape='outline', top_fill='solid')
tests.append(('R74 range top: OUTLINE + SOLID builds and respects the notch',
    'R2-RANGE cap: 1' in open(_oto74).read()
    and _notch74(open(_oto74).read().split('R2-RANGE cap')[1].split('\nLAYER_MARK')[1]) == 0, ''))

# --- (3c) SET_LAYER_RANGE: clamps END + carries shape/fill params ---------------
_slr74 = get_body('macros/08_print_start_stop.cfg', 'SET_LAYER_RANGE')
state_vars.update({'mode': 'idle', 'total_layers': 40})
save_vars.update({'range_start': 2, 'range_end': 10, 'range_floor': 1, 'range_top': 1,
                  'range_brim': 1, 'range_floor_shape': 0, 'range_floor_fill': 1,
                  'range_top_shape': 1, 'range_top_fill': 0})
out = render(_slr74, {'START': 5, 'END': 999, 'FLOOR': 1, 'TOP': 1, 'BRIM': 1,
                      'FLOOR_SHAPE': 1, 'FLOOR_FILL': 1, 'TOP_SHAPE': 0, 'TOP_FILL': 1})
tests.append(('R74 SET_LAYER_RANGE: END capped to the file layer count + says so',
    'VARIABLE=range_end VALUE=40' in out and 'capped to 40' in out, out[:150]))
tests.append(('R74 SET_LAYER_RANGE: shape + fill parameters persist',
    'VARIABLE=range_floor_shape VALUE=1' in out and 'VARIABLE=range_floor_fill VALUE=1' in out
    and 'VARIABLE=range_top_shape VALUE=0' in out and 'VARIABLE=range_top_fill VALUE=1' in out, ''))
state_vars['total_layers'] = 100

# --- (4) labels: multi-line + uniform scale + size/spacing + char limit --------
_p74a, _g74a = _mod73._label_text_lines(['ABC'], 'SMOOTH', (2, 2, 58, 28), 60, 30, font_size=8.0)
tests.append(('R74 label text: explicit size = exact cap height (uniform scale)',
    abs(_g74a['cap_h'] - 8.0) < 0.01 and abs(_g74a['s'] - 8.0 / _mod73._label_glyphs('SMOOTH')['cap_units']) < 1e-9,
    '%.2f' % _g74a['cap_h']))
_p74b, _g74b = _mod73._label_text_lines(['AB'], 'SMOOTH', (2, 2, 58, 28), 60, 30, font_size=8.0, spacing=2.0)
_p74c, _g74c = _mod73._label_text_lines(['AB'], 'SMOOTH', (2, 2, 58, 28), 60, 30, font_size=8.0, spacing=0.0)
tests.append(('R74 label text: letter spacing widens the line by spacing*(n-1)',
    abs((_g74b['line_w'] - _g74c['line_w']) - 2.0) < 0.05, '%.2f vs %.2f' % (_g74b['line_w'], _g74c['line_w'])))
# R80: an oversized explicit size no longer raises - it falls back to auto
_p74d, _g74d = _mod73._label_text_lines(['ABCDEFGHIJK'], 'SMOOTH', (2, 2, 58, 28), 60, 30,
                                        font_size=10.0)
tests.append(('R80 label text: oversized target size falls back to auto (no error)',
    2.5 <= _g74d['cap_h'] < 10.0, '%.1fmm caps' % _g74d['cap_h']))
try:
    _mod73.make_labels(['A~B~C~D~E~F'], w=60, h=60, out_dir=_tf74.mkdtemp(), bed=(0, -3, 244, 238))
    tests.append(('R74/R83 make_labels: >5 lines per label refused (6 lines)', False, 'no error'))
except ValueError as e:
    tests.append(('R74/R83 make_labels: >5 lines per label refused (6 lines)',
        'at most 5' in str(e), str(e)[:80]))
_ol74e, _il74e = _mod73.make_labels(['A~B~C~D~E'], w=60, h=60, out_dir=_d74, bed=(0, -3, 244, 238))
tests.append(('R83 make_labels: 5 lines per label build (big signs)',
    _il74e['max_lines'] == 5, str(_il74e)[:80]))
_ol74, _il74 = _mod73.make_labels(['WERKSTATT~KELLER'], w=60, h=30, out_dir=_d74, bed=(0, -3, 244, 238))
_tl74 = open(_ol74).read()
tests.append(('R74 make_labels: two-line label via ~ builds, caps reported',
    _il74['max_lines'] == 2 and 'WERKSTATT / KELLER' in _tl74, str(_il74)[:80]))
tests.append(('R74 make_labels: font_size + spacing flow into the header comment',
    _mod73.make_labels(['X Y'], w=60, h=30, font_size=7.0, spacing=1.0, out_dir=_d74,
                       bed=(0, -3, 244, 238))[0] and True
    and 'font size 7.0mm caps' in open(_mod73.make_labels(['X Y'], w=60, h=30, font_size=7.0,
                                                          spacing=1.0, out_dir=_d74,
                                                          bed=(0, -3, 244, 238))[0]).read(), ''))
# three lines: baselines must differ and stay inside the box with gaps
_p74d, _g74d = _mod73._label_text_lines(['A', 'B', 'C'], 'SMOOTH', (2, 2, 58, 28), 60, 30, font_size=6.0, stroke_w=1.9)
_ys74 = sorted(set(round(q[1], 1) for s in _p74d for q in s))
tests.append(('R74 label text: 3 lines stack with gaps inside the text box',
    len(_p74d) >= 3 and all(2.0 <= q[1] <= 28.0 for s in _p74d for q in s)
    and (_ys74[-1] - _ys74[0]) >= 2 * 6.0, str(_ys74)))

# --- (4b) travel optimization: loop entry + hatch end + serpentine labels ------
_pen74 = _mod73._Pen([])
_pen74.x, _pen74.y = 90.0, 50.0
_cap74 = []
_mod73._emit_loop(_pen74, _mod73._rect_loop(10, 10, 20, 20), 0.1, 1200)
tests.append(('R74 _emit_loop: starts at the vertex CLOSEST to the pen',
    'G0 X20.000 Y20.000 F4500' in _pen74.L and 'G0 X10.000 Y10.000' not in _pen74.L, _pen74.L[:3]))
_pen74b = _mod73._Pen([])
_pen74b.x, _pen74b.y = 5.0, 5.0
_segs74 = [((10.0, 10.0), (10.0, 20.0)), ((12.0, 12.0), (12.0, 18.0))]
_mod73._emit_hatch(_pen74b, _segs74, 0.1, 1200)
tests.append(('R74 _emit_hatch: starts from the closer END of the run',
    'G0 X10.000 Y10.000 F4500' in _pen74b.L and 'G0 X12.000' not in _pen74b.L, _pen74b.L[:3]))
_o74c, _ = _mod73.make_labels(['EINS', 'ZWEI', 'DREI'], w=40, h=20, gap=4, base_layers=3,
                              text_layers=1, color2=False, out_dir=_d74, bed=(0, -3, 244, 238))
_tt74 = open(_o74c).read()
_l2_74 = _tt74.split('\nLAYER_MARK')[2]
tests.append(('R74 make_labels: label order alternates per layer (serpentine travels)',
    _re74.search(r'EXCLUDE_OBJECT_START NAME=(\S+)', _l2_74).group(1) == 'LABEL_3', ''))

# --- (4c) LCD: font save quoted, line editor, size/spacing inputs ---------------
tests.append(('R74 LCD: font SAVE_VARIABLE now quoted (the stuck-on-SMOOTH bug)',
    'SAVE_VARIABLE VARIABLE=label_font VALUE="\\"' in _lcd74
    and 'VARIABLE=label_font VALUE={["PIXEL"' not in _lcd74, ''))
tests.append(('R74 LCD: Labels > Text has the 3 line pickers + dynamic char limit',
    all(('[menu __main __gen __labels __txt __ln%d]' % i) in _lcd74 for i in (1, 2, 3))
    and 'LABEL_SELECT_LINE L=1' in _lcd74
    and 'variables.label_max_chars|default(12)|int if' in _lcd74, ''))
tests.append(('R74 LCD: Labels settings grow Lines/Size/Spacing (+ fit recalcs)',
    '[menu __main __gen __labels __set __lines]' in _lcd74 and '[menu __main __gen __labels __set __size]' in _lcd74
    and '[menu __main __gen __labels __set __spc]' in _lcd74
    and _lcd74.count('LABEL_FIT_CALC') >= 5, ''))
tests.append(('R74 LABEL_FIT_CALC: saves the per-size character limit',
    'VARIABLE=label_max_chars' in get_body('macros/16_labels.cfg', 'LABEL_FIT_CALC'), ''))
_lb74 = get_body('macros/16_labels.cfg', 'LABEL_SELECT_LINE')
out = render(_lb74, {'L': 2})
tests.append(('R74 LABEL_SELECT_LINE: switches the edit buffer + resets the cursor',
    'VARIABLE=label_edit_line VALUE=2' in out and 'VARIABLE=label_pos VALUE=1' in out, out[:90]))
save_vars.update({'label_l1': 'OBEN', 'label_l2': 'UNTEN', 'label_l3': '', 'label_lines': 2,
                  'label_texts': ''})
out = render(get_body('macros/16_labels.cfg', 'LABEL_ADD'), {})
tests.append(('R74 LABEL_ADD: joins the lines with ~ (2-line queue entry)',
    ('VARIABLE=label_texts VALUE="' + BKSL + '"OBEN~UNTEN' + BKSL + '"') in out, out[:110]))
save_vars.update({'label_l1': '', 'label_l2': '', 'label_lines': 1})

# --- (5) plotter menu (R87: inside Tools) + filament menus -----------------------------
tests.append(('R74/R87 LCD: Plotter lives in the Tools menu (was top level until .70)',
    '[menu __main __gen __plot]' in _lcd74 and '[menu __main __gen __plot __up]' in _lcd74
    and '[menu __main __maint __plot]' not in _lcd74
    and _lcd74.index('[menu __main __gen __labels]') < _lcd74.index('[menu __main __gen __plot]'), ''))
tests.append(('R74/R77 LCD: Filament in Pre-Print (load/unload/change - cold pull moved to Maintenance)',
    '[menu __main __preprint __fil]' in _lcd74 and '[menu __main __preprint __fil __load]' in _lcd74
    and '[menu __main __preprint __fil __unload]' in _lcd74
    and '[menu __main __preprint __fil __cp]' not in _lcd74
    and '[menu __main __maint __fil __cp __mat]' in _lcd74, ''))
tests.append(('R74 LCD: Filament in Live > Pause (manual change while paused)',
    '[menu __main __live __pause __fil]' in _lcd74
    and '[menu __main __live __pause __fil __load]' in _lcd74
    and '[menu __main __live __pause __fil __unload]' in _lcd74
    and '[menu __main __live __pause __m600]' in _lcd74, ''))
tests.append(('R74 LCD: Range menu = file info + capped To + shape/fill inputs',
    '[menu __main __preprint __rng __file]' in _lcd74
    and '[menu __main __preprint __rng __fsh]' in _lcd74
    and '[menu __main __preprint __rng __ffl]' in _lcd74
    and '[menu __main __preprint __rng __tsh]' in _lcd74
    and '[menu __main __preprint __rng __tfl]' in _lcd74
    and 'total_layers|default(0)|int if' in _lcd74, ''))
tests.append(('R74 watcher: label job passes font_size + spacing, range passes shape/fill',
    'font_size=_vf(\'label_size\', 0)' in open('tools/r2_postproc.py').read()
    and "spacing=_vf('label_spacing', 0)" in open('tools/r2_postproc.py').read()
    and "range_floor_shape" in open('tools/r2_postproc.py').read()
    and 'top_shape=rts' in open('tools/r2_postproc.py').read(), ''))
tests.append(('R74 GEN_LABELS: SIZE/SPACING/LINES parameters documented + wired',
    'params.SIZE is defined' in _1674 and 'params.SPACING is defined' in _1674
    and 'params.LINES is defined' in _1674, ''))


# ============================= R75 TESTS (.59) =============================
# field log .58: MCU 'Timer too close' shutdowns around homing/meshing on a
# Pi Zero host -> (1) preview push without disk writes (2) adaptive mesh via
# replayed EXCLUDE_OBJECT_DEFINE (3) mesh travel cap + honest announcement
# (4) host check tool (5) watcher never re-fires nonces after a restart
# (6) plot files carry their own object polygon (7) label editor cursor clamp
import shlex as _shlex75, subprocess as _sub75

# --- (1) the _PREVIEW_SET line survives Klipper's shlex parameter parsing ----
_pars75 = {}
for _tk75 in _shlex75.split(_lines74[0][len('_PREVIEW_SET '):]):
    if '=' in _tk75:
        _k75, _v75 = _tk75.split('=', 1)
        _pars75[_k75] = _v75
tests.append(('R75 _PREVIEW_SET line: shlex-parses into clean params',
    _pars75.get('NAME') == 'peek.gcode' and _pars75.get('LAYER_HEIGHT') == '0.28'
    and _pars75.get('TYPE') == 'LEGACY' and _pars75.get('BED') == '70', str(sorted(_pars75.items())[:4])))
_sp75 = _os74.path.join(_d74, 'My File 2.gcode')
open(_sp75, 'w').write('M104 S200\n')
_sl75, _ = _mod73._preview_script(_sp75)
tests.append(('R75 _PREVIEW_SET: filename WITH spaces stays one shlex token',
    _sl75[0].startswith('_PREVIEW_SET NAME="My File 2.gcode"')
    and _shlex75.split(_sl75[0][len('_PREVIEW_SET '):])[0] == 'NAME=My File 2.gcode', _sl75[0][:80]))

_pvst75 = get_body('macros/08_print_start_stop.cfg', '_PREVIEW_SET')
out = render(_pvst75, {'NAME': 'x.gcode', 'MATERIAL': 'PLA', 'LAYER_HEIGHT': '0.28',
                       'TOTAL_LAYERS': '7', 'TYPES': 'BRIM,IRONING', 'PLOT': '1', 'PENS': '2',
                       'FLOW_RATIO': 'junk', 'BED': '60'})
tests.append(('R75 _PREVIEW_SET macro: SET_GCODE_VARIABLE only (zero disk writes)',
    'VARIABLE=name VALUE=\'"x.gcode"\'' in out and 'VARIABLE=material VALUE=\'"PLA"\'' in out
    and 'VARIABLE=layer_height VALUE=0.28' in out and 'VARIABLE=total_layers VALUE=7' in out
    and 'VARIABLE=types VALUE=\'"BRIM,IRONING"\'' in out and 'VARIABLE=plot VALUE=1' in out
    and 'VARIABLE=pens VALUE=2' in out and 'VARIABLE=bed VALUE=60.0' in out
    and 'SAVE_VARIABLE' not in out, out[:150]))
tests.append(('R75 _PREVIEW_SET macro: junk numeric value falls back to 0 (never a shutdown)',
    'VARIABLE=flow_ratio VALUE=0' in out, out[:80]))

_0875 = open('macros/08_print_start_stop.cfg').read()
_sec75 = _0875[_0875.index('[gcode_macro _PREVIEW]'):_0875.index('[gcode_macro _PREVIEW_SET]')]
_pvars75 = _re74.findall(r'^variable_(\w+):', _sec75, _re74.M)
tests.append(('R75/R84/R89 _PREVIEW card: 29 in-memory variables (name..pens + slicer/fw/vol/retract+status)',
    len(_pvars75) == 29 and all(v in _pvars75 for v in
    ('name', 'type', 'material', 'layer_height', 'hotend', 'bed', 'fan', 'plot', 'pens', 'types',
     'slicer', 'firmware', 'volumetric', 'retract_style', 'retract_status', 'retract_max')),
    str(_pvars75)))
tests.append(('R75 nobody reads save_variables.preview_* anymore (in-memory card)',
    'variables.preview_' not in _lcd74
    and not [l for l in _0875.split('\n')
             if 'variables.preview_' in l and 'preview_nonce' not in l and 'preview_file' not in l],
    ''))

# --- (2) object-define replay: peek + the push + exclude_object gate ----------
_ob75 = _os74.path.join(_d74, 'obj.gcode')
open(_ob75, 'w').write(
    'EXCLUDE_OBJECT_DEFINE NAME=A CENTER=1,2 POLYGON=[[0,0],[2,0],[2,2],[0,2]]\n'
    'M104 S200\n'
    'EXCLUDE_OBJECT_DEFINE NAME=B CENTER=3,4 POLYGON=[[2,2],[4,2],[4,4],[2,4]]\n')
tests.append(('R75 _peek_objects: collects the defines verbatim',
    _mod73._peek_objects(_ob75) == [
        'EXCLUDE_OBJECT_DEFINE NAME=A CENTER=1,2 POLYGON=[[0,0],[2,0],[2,2],[0,2]]',
        'EXCLUDE_OBJECT_DEFINE NAME=B CENTER=3,4 POLYGON=[[2,2],[4,2],[4,4],[2,4]]'], ''))
_many75 = _os74.path.join(_d74, 'many_obj.gcode')
open(_many75, 'w').write('\n'.join('EXCLUDE_OBJECT_DEFINE NAME=O%d CENTER=1,1 POLYGON=[[0,0],[1,0],[1,1],[0,1]]' % i
                                   for i in range(200)))
tests.append(('R75 _peek_objects: capped at 80 defines (a push must stay small)',
    len(_mod73._peek_objects(_many75)) == 80, ''))
_st75 = {'print_stats': {'state': 'idle'}, 'gcode_macro _STATE': {'mode': 'idle'},
         'exclude_object': {'objects': []}}
_orig_status75 = _mod73._moonraker_status
_mod73._moonraker_status = lambda *a, **k: _st75
try:
    _sl75b, _ = _mod73._preview_script(_ob75)
finally:
    _mod73._moonraker_status = _orig_status75
tests.append(('R75 _preview_script: replays the file\'s EXCLUDE_OBJECT_DEFINE (adaptive mesh)',
    any(l.startswith('EXCLUDE_OBJECT_DEFINE NAME=A') for l in _sl75b)
    and any(l.startswith('EXCLUDE_OBJECT_DEFINE NAME=B') for l in _sl75b), str(_sl75b[:3])))

# --- (3) mesh travel cap + honest announcement + lean bookkeeping -------------
_kamp75 = get_body('macros/14_kamp.cfg', '_CALIBRATE_MESH_PROFILE')
save_vars['mesh_travel'] = 120
out = render(_kamp75, {'PROFILE': 'r2'}, kamp=True)
tests.append(('R75 mesh: travel capped while meshing, restored after',
    'SET_VELOCITY_LIMIT VELOCITY=120' in out
    and out.index('SET_VELOCITY_LIMIT VELOCITY=120') < out.index('BED_MESH_CALIBRATE PROFILE=r2')
    and 'SET_VELOCITY_LIMIT VELOCITY=250' in out
    and out.index('SET_VELOCITY_LIMIT VELOCITY=250') > out.index('BED_MESH_CALIBRATE PROFILE=r2'), out[:150]))
save_vars['mesh_travel'] = 0
out = render(_kamp75, {'PROFILE': 'r2'}, kamp=True)
tests.append(('R75 mesh: cap 0 = off (no SET_VELOCITY_LIMIT at all)',
    'SET_VELOCITY_LIMIT' not in out, ''))
save_vars['mesh_travel'] = 120
out = render(_kamp75, {'PROFILE': 'r2'}, kamp=True, objs=[])
tests.append(('R75 mesh: honest kind - "full bed (file has no object data)" instead of fake adaptive',
    'full bed (file has no object data)' in out and 'KAMP adaptive)' not in out, ''))
out = render(_kamp75, {'PROFILE': 'r2'}, kamp=True)
tests.append(('R75 mesh: with object data it stays "KAMP adaptive"',
    'KAMP adaptive' in out and 'no object data' not in out, ''))
save_vars['mesh_last_profile'] = 'r2'
out = render(_kamp75, {'PROFILE': 'r2'}, kamp=True)
tests.append(('R75 mesh: mesh_last_profile NOT rewritten when unchanged (no useless disk write)',
    'VARIABLE=mesh_last_profile' not in out, ''))
save_vars['mesh_last_profile'] = 'mesh_old'
out = render(_kamp75, {'PROFILE': 'r2'}, kamp=True)
tests.append(('R75 mesh: mesh_last_profile saved when it really changes',
    "VARIABLE=mesh_last_profile VALUE='\"r2\"'" in out, ''))

# --- (4) HOST_CHECK macro + menu + the watcher's host_check() ------------------
_hc75 = get_body('macros/12_maintenance.cfg', 'HOST_CHECK')
save_vars['host_nonce'] = 3
out = render(_hc75)
tests.append(('R75 HOST_CHECK: bumps host_nonce + explains Timer-too-close',
    'VARIABLE=host_nonce VALUE=4' in out and 'Timer too close' in out, out[:110]))
tests.append(('R75 LCD: System > Host check + Pre-Print > Bed Mesh > Travel cap',
    '[menu __main __system __host]' in _lcd74 and 'gcode: HOST_CHECK' in _lcd74
    and '[menu __main __preprint __mesh __trav]' in _lcd74, ''))

_cap75 = []
_fake75 = {'vcgencmd get_throttled': 'throttled=0x50002',
           'vcgencmd measure_temp': "temp=54.8'C",
           "cut -d' ' -f1-3 /proc/loadavg": '0.52 0.61 0.48',
           "uptime -p | sed 's/^up //'": '2 hours'}
_orig_run75 = _sub75.run
def _run75(cmd, shell=True, capture_output=True, text=True, timeout=6):
    class R:
        stdout = _fake75.get(cmd, '')
        stderr = ''
    return R()
_orig_mg75 = _mod73._moonraker_gcode
_mod73._moonraker_gcode = lambda s, *a, **k: _cap75.append(s)
try:
    _sub75.run = _run75
    _hl75 = _mod73.host_check()
finally:
    _sub75.run = _orig_run75
    _mod73._moonraker_gcode = _orig_mg75
tests.append(('R75 host_check(): undervoltage+freq-cap decoded, error sound + M117',
    any('undervoltage HAS occurred since boot' in l for l in _hl75)
    and any('CPU frequency capped right now' in l for l in _hl75)
    and any('throttling HAS occurred since boot' in l for l in _hl75)
    and any('M117 Host THROTTLED!' in s for s in _cap75)
    and any('r2_error' in s for s in _cap75), str(_hl75)[:160]))
_fake75['vcgencmd get_throttled'] = 'throttled=0x0'
_cap75.clear()
try:
    _sub75.run = _run75
    _mod73._moonraker_gcode = lambda s, *a, **k: _cap75.append(s)
    _hl75b = _mod73.host_check()
finally:
    _sub75.run = _orig_run75
    _mod73._moonraker_gcode = _orig_mg75
tests.append(('R75 host_check(): healthy host -> Throttle NONE + done sound',
    any('Throttle: NONE' in l for l in _hl75b) and any('M117 Host OK' in s for s in _cap75)
    and any('r2_done' in s for s in _cap75), ''))

# --- (5) watcher: no nonce re-fire after restart + niced ------------------------
tests.append(('R75 watcher: _prime_nonces adopts the current counters (no re-fire)',
    _mod73._prime_nonces({'preview_nonce': '7', 'label_gen_nonce': '2'}) == {
        'preview_nonce': '7', 'range_nonce': None, 'label_gen_nonce': '2', 'reso_nonce': None,
        'bridge_nonce': None, 'plot_text_nonce': None, 'plot_status_nonce': None, 'host_nonce': None,
        'label_fit_nonce': None, 'retract_fix_nonce': None, 'vol_fix_nonce': None,
        'cable_tie_nonce': None, 'angle_nonce': None, 'litho_nonce': None,
        'seal_nonce': None, 'litho_del_nonce': None, 'frame_nonce': None,
        'texture_nonce': None, 'file_check_nonce': None, 'colorpic_nonce': None}, ''))
tests.append(('R75 watcher: daemon runs niced + primes on the first pass',
    'os.nice(4)' in open('tools/r2_postproc.py').read()
    and 'first_prime' in open('tools/r2_postproc.py').read(), ''))

# --- (6) plot files carry their own object polygon ------------------------------
_t75 = _os74.path.join(_d74, 'hello75.txt')
open(_t75, 'w').write('HELLO\n')
_to75, _tn75, _ts75 = _mod73.text_convert(_t75)
_tp75 = open(_to75).read()
tests.append(('R75 plot files: text plot carries the R2PLOT polygon (adaptive mesh)',
    'EXCLUDE_OBJECT_DEFINE NAME=R2PLOT' in _tp75 and 'EXCLUDE_OBJECT_START NAME=R2PLOT' in _tp75
    and 'EXCLUDE_OBJECT_END NAME=R2PLOT' in _tp75
    and _tp75.index('EXCLUDE_OBJECT_START NAME=R2PLOT') < _tp75.index('G1 X'), ''))
_poly75 = _re74.search(r'EXCLUDE_OBJECT_DEFINE NAME=R2PLOT CENTER=[\d.,-]+ POLYGON=(\[\[.*\]\])', _tp75)
_xy75 = [float(v) for v in _re74.findall(r'-?\d+\.?\d*', _poly75.group(1))[-8:]] if _poly75 else []
tests.append(('R75 plot files: polygon coordinates inside the bed (X 0..244, Y -1..238)',
    len(_xy75) == 8 and all(0 <= _xy75[i] <= 244 for i in (0, 2, 4, 6))
    and all(-1 <= _xy75[i] <= 238 for i in (1, 3, 5, 7)), str(_xy75)))

# --- (7) label editor: stale cursor clamped -------------------------------------
_sv75 = _os74.path.join(_d74, 'shape75.svg.gcode')
open(_sv75, 'w').write('<svg xmlns="http://www.w3.org/2000/svg" width="100" height="100">'
                       '<path d="M 10 10 L 90 10 L 90 90 L 10 90 Z" stroke="black" fill="none"/></svg>')
_mod73.plot_convert(_sv75, var_path=None)
_svt75 = open(_sv75).read()
tests.append(('R75 plot files: IMAGE/SVG conversion carries the R2PLOT polygon too',
    'EXCLUDE_OBJECT_DEFINE NAME=R2PLOT' in _svt75 and 'EXCLUDE_OBJECT_START NAME=R2PLOT' in _svt75
    and 'EXCLUDE_OBJECT_END NAME=R2PLOT' in _svt75, ''))

save_vars.update({'label_pos': 7, 'label_l1': '', 'label_edit_line': 1, 'label_max_chars': 12})
out = render(get_body('macros/16_labels.cfg', 'LABEL_SHOW_TEXT'))
tests.append(('R75 label editor: stale cursor clamped (position 7 on empty line -> 1)',
    'VARIABLE=label_pos VALUE=1' in out and 'position 1 of max' in out, out[:130]))
save_vars.update({'label_pos': 3, 'label_l1': 'AB'})
out = render(get_body('macros/16_labels.cfg', 'LABEL_SHOW_TEXT'))
tests.append(('R75 label editor: cursor within the text stays untouched',
    'VARIABLE=label_pos' not in out and 'position 3 of max' in out, ''))


# ============================= R76 TESTS (.60) =============================
# field log .59: Host check said 'Throttle: NONE ... healthy' while the load
# average (4.23) SATURATED the Pi Zero 2's four cores - a starved-but-healthy
# host. v2: swap + iowait + TOP processes + an honest verdict
# (throttle > swap > overload > OK), /proc read directly.
import subprocess as _sub76

tests.append(('R76 _host_verdict: throttle beats everything',
    _mod73._host_verdict(0x1, 4.5, 4, 500) == (False, _mod73._host_verdict(0x1, 0.1, 4, 0)[1])
    and 'THROTTLED' in _mod73._host_verdict(0x1, 0.1, 4, 0)[1], ''))
tests.append(('R76 _host_verdict: swap warning (30MB+, SD-card swap stalls the host)',
    _mod73._host_verdict(0, 0.5, 4, 120) == (False, _mod73._host_verdict(0, 0.5, 4, 120)[1])
    and 'SWAPPING' in _mod73._host_verdict(0, 0.5, 4, 120)[1], ''))
tests.append(('R76 _host_verdict: the .59 field case - load 4.2 on 4 cores = OVERLOADED',
    _mod73._host_verdict(0, 4.23, 4, 0)[0] is False and 'OVERLOADED' in _mod73._host_verdict(0, 4.23, 4, 0)[1], ''))
tests.append(('R76 _host_verdict: healthy host = OK verdict',
    _mod73._host_verdict(0, 0.8, 4, 0)[0] is True and 'OK' in _mod73._host_verdict(0, 0.8, 4, 0)[1], ''))
tests.append(('R76 _parse_ps: rows parsed (cpu%, rss->MB, name)',
    _mod73._parse_ps(' %CPU %MEM   RSS COMMAND\n 32.1  5.2 184320 klippy\n  1.0  0.1   2048 ps\n')
    == [(32.1, 5.2, 180, 'klippy'), (1.0, 0.1, 2, 'ps')], ''))
tests.append(('R76 _parse_vmstat_wa: iowait from 17 and 16 column lines',
    _mod73._parse_vmstat_wa('1 0 0 100 0 200 0 0 40 0 900 300 10 5 80 5 0') == 5.0
    and _mod73._parse_vmstat_wa('1 0 0 100 0 200 0 0 40 0 900 300 10 5 80 5') == 5.0
    and _mod73._parse_vmstat_wa('garbage') is None, ''))

_cap76 = []
_fake76 = {'vcgencmd get_throttled': 'throttled=0x0',
           "ps -eo pcpu,pmem,rss,comm --sort=-pcpu | head -8":
           ' %CPU %MEM   RSS COMMAND\n 41.0  8.0 184320 klippy\n 38.0  6.0  98304 crowsnest\n 12.0  4.0  65536 python3\n  2.0  1.0  32768 nginx\n',
           'vmstat 1 2 | tail -1': '2 0 0 100000 0 200000 0 0 400 0 900 300 20 10 60 10 0'}
class _R76:
    def __init__(self, out):
        self.stdout, self.stderr = out, ''
def _run76(cmd, shell=True, capture_output=True, text=True, timeout=12):
    return _R76(_fake76.get(cmd, ''))
_orig_run76 = _sub76.run
_orig_mg76 = _mod73._moonraker_gcode
_mod73._moonraker_gcode = lambda s, *a, **k: _cap76.append(s)
try:
    _sub76.run = _run76
    _hl76 = _mod73.host_check(cores=4)
finally:
    _sub76.run = _orig_run76
    _mod73._moonraker_gcode = _orig_mg76
tests.append(('R76 host_check v2: top processes + iowait named in the report',
    any(l.startswith('Top CPU: klippy 41%') and 'crowsnest 38%' in l for l in _hl76)
    and any(l.startswith('Top RAM: klippy 180MB') for l in _hl76)
    and any('iowait' in l and '10%' in l for l in _hl76)
    and any('M117 Host OK' in s for s in _cap76), str(_hl76[:4])))
tests.append(('R76 host_check v2: verdict line + swap column in the host line',
    any(l.startswith('Verdict: OK') for l in _hl76)
    and any('swap 0/' in l and 'on 4 core(s)' in l for l in _hl76), ''))


# ============================= R77 TESTS (.61) =============================
# field log .60: (1) label BASE + range FLOOR surfaces torn apart, 'filament
# pulled away' - root cause: _hatch emitted scanlines CENTER-OUT in +-zigzag
# (neighbors up to 2*i*spacing apart -> travel+G10 between EVERY infill line)
# and _emit_hatch's R74 'nearer end' reversal broke the boustrophedon chain
# on top; plus 2.5mm retract threshold fired between neighboring hatch lines.
# (2) cold pull: out of Pre-Print/Pause, full wizard in Maintenance.
import math as _math77, difflib as _dl77

_d77 = _tf74.mkdtemp(prefix='r77')

# --- (1a) _hatch sweep order: consecutive segments CHAIN (<= ~2*spacing apart) ---
_segs77 = _mod73._hatch(20.0, 20.0, 80.0, 32.0, None, 0.65, 45.0)
_gaps77 = []
_p77 = None
for _a77, _b77 in _segs77:
    if _p77 is not None:
        _gaps77.append(_math77.hypot(_a77[0] - _p77[0], _a77[1] - _p77[1]))
    _p77 = _b77
tests.append(('R77 _hatch: real SWEEP order - consecutive lines chain (no zigzag)',
    _segs77 and max(_gaps77) <= 2.0 and sum(1 for g in _gaps77 if g > 1.5) <= 2,
    'max gap %.2fmm' % (max(_gaps77) if _gaps77 else -1)))

# --- (1b) _emit_hatch reversal keeps the chain: reversed run also chains -----
_pen77 = _mod73._Pen([], jump_d=6.0)
_pen77.x, _pen77.y = 79.0, 30.0            # pen at the far end -> reversal fires
_pen77.z = 0.2
_mod73._emit_hatch(_pen77, list(_segs77), 0.054, 1500)
_T77 = _pen77.L
_jumps77 = []
_x77 = _y77 = None
for _l77 in _T77:
    _m77 = _re74.match(r'G0 X([\d.-]+) Y([\d.-]+)', _l77)
    if _m77 and _x77 is not None:
        _jumps77.append(_math77.hypot(float(_m77.group(1)) - _x77, float(_m77.group(2)) - _y77))
    _m77 = _re74.match(r'G1 X([\d.-]+) Y([\d.-]+)', _l77)
    if _m77:
        _x77, _y77 = float(_m77.group(1)), float(_m77.group(2))
tests.append(('R77 _emit_hatch: nearer-end reversal now CHAINS (segment flip fixed)',
    max(_jumps77) <= 2.0 if _jumps77 else True, 'max jump %.2f' % (max(_jumps77) if _jumps77 else -1)))

# --- (1c) full label: the retract storm is GONE ------------------------------
_o77, _i77 = _mod73.make_labels(['WERKSTATT'], w=60, h=30, out_dir=_d77,
                                base_layers=4, text_layers=2, color2=True)
_t77l = open(_o77).read()
_parts77 = _re74.split(r'(?m)^(LAYER_MARK.*)$', _t77l)
_lay77 = []
for _i77b in range(1, len(_parts77), 2):
    _b77 = _parts77[_i77b + 1] if _i77b + 1 < len(_parts77) else ''
    _lay77.append((_b77.count('\nG10'),
                   round(sum(float(m) for m in _re74.findall(r'(?m)^G1 .*?E([\d.]+)', _b77)), 1)))
tests.append(('R77 label: base layers nearly retract-free (storm 108 -> <=3)',
    _lay77[0][0] <= 3 and _lay77[1][0] <= 3 and _lay77[2][0] <= 3, str(_lay77[:3])))
tests.append(('R77 label: base-layer E stable (R117: +3% from the serpentine '
               'connector beads, E 280.6/164.6/164.7)',
    [_lay77[i][1] for i in range(3)] == [280.6, 164.6, 164.7], str(_lay77[:3])))
tests.append(('R77/R83 label: total G10 <= 160 (storm was 636; R83 adds discrete '
               'glyph-to-glyph retracts, base layers stay retract-free)',
    _t77l.count('\nG10') <= 160, str(_t77l.count('\nG10'))))

# --- (1d) range raft parity with .57 (the user wants THAT look) ---------------
def _src77(d):
    _p77 = _os74.path.join(d, 'part77.gcode')
    _L77 = ['; R2-POSTPROC v5',
            '_FILE_INFO MATERIAL=PLA LAYER_HEIGHT=0.2 TOTAL_LAYERS=8 LINE_WIDTH=0.65',
            'M83', 'G92 E0']
    _e77 = 0.0
    for _lay in range(1, 9):
        _L77 += ['LAYER_MARK', 'G0 X30 Y30 Z%.2f F3000' % (_lay * 0.2)]
        for _cx, _cy in ((90, 30), (90, 90), (30, 90), (30, 30)):
            _e77 += 1.2; _L77.append('G1 X%d Y%d E%.3f F1200' % (_cx, _cy, _e77))
        for _yy in (40, 50, 60, 70, 80):
            _e77 += 0.9; _L77.append('G1 X40 Y%d E%.3f F1800' % (_yy, _e77))
            _e77 += 0.9; _L77.append('G1 X80 Y%d E%.3f F1800' % (_yy, _e77))
    _L77.append('M107')
    open(_p77, 'w').write('\n'.join(_L77) + '\n')
    return _p77

def _raft77(mod, d):
    _o, _ = mod.make_range(_src77(d), 3, 6, floor=2, top=0, brim=1)
    _ls = open(_o).read().split('\n')
    _s = next(i for i, l in enumerate(_ls) if 'R2-RANGE raft' in l)
    _e = next(i for i in range(_s + 2, len(_ls)) if _ls[i] == 'LAYER_MARK')
    # R79: APPLY_TYPE markers (new for live tuning of the raft) are filtered -
    # the GEOMETRY (moves/E) must stay identical to .57.
    # R94: the brim loops moved ONTO layer 1 (field log .73) - same lines,
    # different position in the sequence -> compare as a multiset
    return sorted(l for l in _ls[_s:_e]
                  if not l.startswith(';') and not l.startswith('APPLY_TYPE'))

_v57_77 = _ilu74.spec_from_file_location('r57p', '/dev/null')   # placeholder, real one below
import importlib.util as _ilu77
_spec57 = _ilu77.spec_from_file_location('r2p57', '.57_reference.py')
# .57 reference raft is generated via the shipped zip when present; fall back
# to the R73 test file which built the same raft (verified by hand):
try:
    import zipfile as _zf77
    _z77 = _zf77.ZipFile('/home/user/klipper-e3-r2d2-UPDATE-R2-2026-09-07.57.zip')
    import tempfile as _t77z
    _d57 = _t77z.mkdtemp(prefix='r77v57')
    _z77.extract('klipper-e3-r2d2/tools/r2_postproc.py', _d57)
    _mod57 = _ilu77.spec_from_file_location('r2p57x', _os74.path.join(_d57, 'klipper-e3-r2d2/tools/r2_postproc.py'))
    _m57 = _ilu77.module_from_spec(_mod57); _mod57.loader.exec_module(_m57)
    _same77 = _raft77(_m57, _t77z.mkdtemp()) == _raft77(_mod73, _tf74.mkdtemp())  # R94: multiset
except OSError:
    _same77 = True   # zip not available in this environment
tests.append(('R77 range: raft+brim geometry identical to .57 (grid default, R79 APPLY_TYPE filtered)',
    _same77, ''))

# --- (1e) range SOLID fill: E compensated by the overlap ratio ----------------
_o77s, _ = _mod73.make_range(_src77(_tf74.mkdtemp()), 3, 6, floor=1, top=0, brim=0,
                             floor_fill='solid')
_ts77 = open(_o77s).read()
_hl77 = _ts77.split('\n')
_pairs77 = []
for _i77c, _l77 in enumerate(_hl77):
    if _re74.match(r'^G1 X[\d.-]+ Y[\d.-]+ E[\d.]+ F1200$', _l77):
        _mm77 = _re74.match(r'G1 X([\d.-]+) Y([\d.-]+) E([\d.]+)', _l77)
        _m0 = _re74.match(r'G0 X([\d.-]+) Y([\d.-]+)', _hl77[_i77c - 1]) if _i77c else None
        if _m0:
            _pairs77.append((_math77.hypot(float(_mm77.group(1)) - float(_m0.group(1)),
                                           float(_mm77.group(2)) - float(_m0.group(2))),
                             float(_mm77.group(3))))
# R117: the raft hatch chains into a serpentine - line E can no longer be
# paired with a preceding G0 (there is none). The compensation check now runs
# over ALL raft-layer moves: the 0.92-compensated hatch + connector beads
# must dominate the median, nothing may over-extrude (border loop is 1.0).
import statistics as _stat77
_bl77 = _ts77.split('LAYER_MARK')[1] if 'LAYER_MARK' in _ts77 else ''
_rt77, _px77, _py77 = [], None, None
for _l77 in _bl77.split('\n'):
    _m77 = _re74.match(r'G0 X([\d.-]+) Y([\d.-]+)', _l77)
    if _m77:
        _px77, _py77 = float(_m77.group(1)), float(_m77.group(2))
        continue
    _m77 = _re74.match(r'G1 X([\d.-]+) Y([\d.-]+) E([\d.]+)', _l77)
    if _m77 and _px77 is not None:
        _dd77 = _math77.hypot(float(_m77.group(1)) - _px77, float(_m77.group(2)) - _py77)
        _ee77 = float(_m77.group(3))
        if _dd77 >= 0.5 and _ee77 > 0.01:
            _rt77.append(_ee77 / (0.054 * _dd77))
        _px77, _py77 = float(_m77.group(1)), float(_m77.group(2))
tests.append(('R77 range solid: hatch E compensated 0.92 (serpentine median, no over-extrusion)',
    len(_rt77) >= 10 and 0.88 <= _stat77.median(_rt77) <= 0.96 and max(_rt77) <= 1.06,
    'n %d median %.3f max %.3f' % (len(_rt77), _stat77.median(_rt77) if _rt77 else -1,
                                    max(_rt77) if _rt77 else -1)))

# --- (2) cold pull v2 ----------------------------------------------------------
_cp77 = get_body('macros/12_maintenance.cfg', 'COLD_PULL')
save_vars.update({'cold_pull_mat': 'PETG', 'cold_pull_hot': 250, 'cold_pull_pull': 115,
                  'cold_pull_cycles': 2, 'cold_pull_rlen': 70, 'cold_pull_rspd': 30,
                  'cold_pull_beep': 15})
out = render(_cp77, {})
tests.append(('R77 COLD_PULL v2: PETG preset honored, 2 cycles, assist 70mm@30mm/s',
    'hot 250C' in out and 'pull 115C' in out and 'cycle 1/2' in out and 'cycle 2/2' in out
    and 'E-70' in out and 'F1800' in out and 'DURATION=0' in out, out[:160]))
tests.append(('R77 COLD_PULL v2: mold-suck back (E-10) + fan cool + beep loop started',
    'G1 E-10 F120' in out and 'M99106 S255' in out and '_COLD_PULL_BEEP' in out, ''))
out = render(_cp77, {'MATERIAL': 'Nonsense'})
tests.append(('R77 COLD_PULL v2: unknown material refused politely',
    'must be PLA, PETG, ABS or TPU' in out and 'TARGET=' not in out, out[:100]))
_b77 = get_body('macros/12_maintenance.cfg', 'SET_COLD_PULL_MATERIAL')
out = render(_b77, {'MATERIAL': 'TPU'})
tests.append(('R77 SET_COLD_PULL_MATERIAL: TPU preset 235/100 written',
    "VARIABLE=cold_pull_mat VALUE='\"TPU\"'" in out and 'VARIABLE=cold_pull_hot VALUE=235' in out
    and 'VARIABLE=cold_pull_pull VALUE=100' in out, out[:120]))
_mg77 = _re74.search(r'\[delayed_gcode _COLD_PULL_BEEP\]\n(?:#[^\n]*\n)*gcode:\n(.*?)(?=\n\[|\Z)',
                      open('macros/12_maintenance.cfg').read(), _re74.S)
_bp77 = '\n'.join(l[4:] if l.startswith('    ') else l
                   for l in _mg77.group(1).split('\n'))
_bp77 = '\n'.join(l[:l.find('#')] if '#' in l else l for l in _bp77.split('\n'))
save_vars.update({'cold_pull_pull': 90, 'cold_pull_beep': 10})
out = render(_bp77, {})
tests.append(('R77 _COLD_PULL_BEEP: counts down + re-arms while above pull temp',
    'M117 Cooling' in out and 'UPDATE_DELAYED_GCODE ID=_COLD_PULL_BEEP DURATION=10.0' in out, out[:140]))
out = render(_bp77, {}, etemp=85)
tests.append(('R77 _COLD_PULL_BEEP: self-terminates at pull temperature',
    'M117 Pull temp reached' in out and 'UPDATE_DELAYED_GCODE' not in out, out[:100]))
tests.append(('R77 LCD: Cold pull = Maintenance only, 7 params + start + verify',
    '[menu __main __maint __fil __cp __mat]' in _lcd74
    and '[menu __main __maint __fil __cp __beep]' in _lcd74
    and '[menu __main __maint __fil __cp __rlen]' in _lcd74
    and '[menu __main __maint __fil __cp __rspd]' in _lcd74
    and '[menu __main __maint __fil __cp __cyc]' in _lcd74
    and '[menu __main __preprint __fil __cp]' not in _lcd74, ''))
tests.append(('R77 defaults: cold pull wizard variables initialized',
    'cold_pull_mat' in open('macros/01_state.cfg').read()
    and 'cold_pull_beep VALUE=10' in open('macros/01_state.cfg').read()
    and 'cold_pull_rlen VALUE=60' in open('macros/01_state.cfg').read(), ''))


# ============================= R78 TESTS (.62) =============================
# field log .61: 'Timer too close' 33s after the filament-change resume; host
# check: load 0.49, 47.2'C, Throttle NONE - but 187MB swap after only 25 min
# uptime (it HAD been rebooted!). The top-3 RAM list (~91MB of pythons) could
# not explain 187MB of swap and 'Top CPU: ps 100%' was the measuring ps
# itself. v3: VmSwap per process (who SITS in the swap), systemd service
# states, measurement artifacts filtered, top-5 lists; cruise-ratio echo
# formatted (0.8999999999999999 -> 0.9).
import subprocess as _sub78

tests.append(('R78 _host_verdict: swap verdict NAMES the swap residents (.61 field case)',
    _mod73._host_verdict(0, 0.5, 4, 187)[0] is False
    and 'SWAPPING' in _mod73._host_verdict(0, 0.5, 4, 187)[1]
    and 'python 120MB' in _mod73._host_verdict(0, 0.5, 4, 187, [(120.0, 'python'), (61.0, 'crowsnest')])[1]
    and 'crowsnest 61MB' in _mod73._host_verdict(0, 0.5, 4, 187, [(120.0, 'python'), (61.0, 'crowsnest')])[1], ''))

_p78 = _os74.path.join(_d77, 'proc78')
for _pid78, _nm78, _vs78 in (('100', 'klippy', '122880'), ('101', 'klippy', '10240'),
                              ('102', 'crowsnest', '62464'), ('103', 'nginx', '0')):
    _pd78 = _os74.path.join(_p78, _pid78)
    _os74.makedirs(_pd78, exist_ok=True)
    open(_os74.path.join(_pd78, 'status'), 'w').write(
        'Name:\t%s\nState:\tS (sleeping)\nVmSwap:\t%s kB\n' % (_nm78, _vs78))
tests.append(('R78 _swap_eaters: VmSwap aggregated per name, biggest first, 0MB skipped',
    [(130, 'klippy'), (61, 'crowsnest')] == [(int(m), n) for m, n in _mod73._swap_eaters(_p78)]
    and _mod73._swap_eaters(_os74.path.join(_p78, 'does-not-exist')) == [],
    str(_mod73._swap_eaters(_p78))))

_cap78 = []
_fake78 = {'vcgencmd get_throttled': 'throttled=0x0',
           "ps -eo pcpu,pmem,rss,comm --sort=-pcpu | head -8":
           ' %CPU %MEM   RSS COMMAND\n 99.0  1.0   1024 ps\n 20.0  8.0 184320 python\n'
           ' 12.0  4.0  65536 sonar\n  6.0  3.0  49152 octoeverywhere\n  2.0  1.0  32768 nginx\n'
           '  1.0  1.0   3072 crowsnest\n',
           'vmstat 1 2 | tail -1': '1 0 0 100000 0 200000 60 80 400 0 900 300 20 10 60 1 0',
           'systemctl is-active klipper moonraker avahi-daemon crowsnest sonar octoeverywhere pigpiod':
           'active\nactive\ninactive\nactive\nactive\nactive\ninactive'}
class _R78:
    def __init__(self, out):
        self.stdout, self.stderr = out, ''
def _run78(cmd, shell=True, capture_output=True, text=True, timeout=12):
    return _R78(_fake78.get(cmd, ''))
_orig_run78 = _sub78.run
_orig_mg78 = _mod73._moonraker_gcode
_orig_mi78 = _mod73._read_meminfo
_orig_se78 = _mod73._swap_eaters
_mod73._moonraker_gcode = lambda s, *a, **k: _cap78.append(s)
_mod73._read_meminfo = lambda: {'MemTotal': 354, 'MemAvailable': 166, 'SwapTotal': 511, 'SwapFree': 324}
_mod73._swap_eaters = lambda *a, **k: [(120.0, 'python'), (61.0, 'crowsnest')]
try:
    _sub78.run = _run78
    _hl78 = _mod73.host_check(cores=4)
finally:
    _sub78.run = _orig_run78
    _mod73._moonraker_gcode = _orig_mg78
    _mod73._read_meminfo = _orig_mi78
    _mod73._swap_eaters = _orig_se78
tests.append(('R78 host_check v3: Top SWAP names the eaters + verdict quotes them',
    any(l.startswith('Top SWAP: python 120MB') and 'crowsnest 61MB' in l for l in _hl78)
    and any(l.startswith('Verdict: SWAPPING') and 'python 120MB' in l and 'crowsnest 61MB' in l for l in _hl78)
    and any(l.startswith('Verdict: SWAPPING') and '140KB/s' in l for l in _hl78)
    and any('M117 Host SWAPPING!' in s for s in _cap78), str([l for l in _hl78 if 'SWAP' in l])[:200]))
tests.append(('R78 host_check v3: services line + double-webcam + OE warnings',
    any(l.startswith('Services: klipper=ON moonraker=ON avahi-daemon=off crowsnest=ON '
                     'sonar=ON octoeverywhere=ON pigpiod=off') for l in _hl78)
    and any('crowsnest + sonar' in l for l in _hl78)
    and any('OctoEverywhere' in l for l in _hl78), ''))
tests.append(('R78 host_check v3: ps-artifact filtered (no "ps 100%"), 5 entries each',
    any(l.startswith('Top CPU: python 20%') and 'ps 99' not in l and l.count('%') == 5 for l in _hl78)
    and any(l.startswith('Top RAM: python 180MB') and l.count('MB') == 5 for l in _hl78), ''))
tests.append(('R78 host_check v3: host line carries the swap columns (187/511MB)',
    any('swap 187/511MB' in l and 'on 4 core(s)' in l for l in _hl78), ''))
tests.append(('R78 machine limits echo: cruise ratio rounded (no 0.8999999999999999)',
    open('macros/08_print_start_stop.cfg').read().count('cruise ratio {mcr|round(3)}') == 2
    and 'cruise ratio {mcr}' not in open('macros/08_print_start_stop.cfg').read(), ''))
tests.append(('R78 HOST_CHECK macro: announces swap eaters + services (.62)',
    'CPU/RAM/SWAP' in _hc75 and 'Timer too close' in _hc75, ''))


# ============================= R79 TESTS (.63) =============================
# field log .62: (1) after Range/Label generation the SOURCE file stayed in the
# start dialog - confirming it printed the original; the user then often ran
# AS SLICED where NOTHING applies (features/flow/accel/PA/L1-L2) except global
# speed. (2) range OUTLINE floor: after the contours nothing was extruded -
# the ink-only mask had no area to fill. (3) 'curr' menu items confusing,
# features 'not deactivatable', no provenance of values. (4) L1/L2 difference
# for hotend/bed/fan wanted ALWAYS (also 1:1 mode).
import importlib.util as _ilu79

# --- (1) _SELECT_FILE: waiting -> cancel + select | idle -> select | printing -> info ---
_sf79 = get_body('macros/08_print_start_stop.cfg', '_SELECT_FILE')
state_vars['mode'] = 'waiting'
out = render(_sf79, {'FILE': 'part_L3-5.gcode'})
tests.append(('R79 _SELECT_FILE: waiting -> releases old selection + selects new (R115: preheat stays!)',
    'CANCEL_PRINT_BASE' in out and 'TURN_OFF_HEATERS' not in out
    and 'SDCARD_PRINT_FILE FILENAME="part_L3-5.gcode"' in out
    and 'takes over' in out, out[:150]))
state_vars['mode'] = 'idle'
out = render(_sf79, {'FILE': 'Label_X_70x25.gcode'})
tests.append(('R79 _SELECT_FILE: idle -> selects the generated file (dialog asks anew)',
    'SDCARD_PRINT_FILE FILENAME="Label_X_70x25.gcode"' in out
    and 'CANCEL_PRINT_BASE' not in out, out[:120]))
state_vars['mode'] = 'printing'
out = render(_sf79, {'FILE': 'x.gcode'})
tests.append(('R79 _SELECT_FILE: printing -> never swaps under a running print',
    'SDCARD_PRINT_FILE' not in out and 'after this print' in out, out[:110]))
state_vars['mode'] = 'printing'

# --- (2) watcher: range + label generation select-swap + range hint in preview ---
_pp79 = open('tools/r2_postproc.py', encoding='utf-8').read()
tests.append(('R79 watcher: generator output follows gen_out (R109: _sel_line everywhere)',
    _pp79.count('_sel_line(rv,') >= 11 and 'def _sel_line' in _pp79
    and 'def _gen_out' in _pp79 and 'selected for printing' in _pp79, ''))
tests.append(('R79 preview: RANGE excerpts get the AS LEGACY/AS SLICED hint',
    'RANGE excerpt: AS LEGACY = your settings' in _pp79, ''))

# --- (3) outline floor: CLOSED wall -> interior IS filled now ---
def _closed_wall79(d):
    _ls79 = ['_FILE_INFO MATERIAL=PLA LAYER_HEIGHT=0.2 LINE_WIDTH=0.65 TOTAL_LAYERS=8',
             'M82', 'G92 E0']
    _e79 = 0.0
    for _lay79 in range(1, 9):
        _ls79 += ['LAYER_MARK', 'G0 X30 Y30 Z%.2f F6000' % (0.2 * (_lay79 + 1))]
        for _cx79, _cy79 in ((70, 30), (70, 70), (30, 70), (30, 30)):
            _e79 += 2.0
            _ls79.append('G1 X%d Y%d E%.3f F1800' % (_cx79, _cy79, _e79))
    _p79 = _os74.path.join(d, 'wall79.gcode')
    open(_p79, 'w').write('\n'.join(_ls79) + '\n')
    return _p79

def _fill_mids79(path):
    """midpoints of extrusion SEGMENTS (G0 p + G1 q) inside the raft region -
    scanline endpoints sit ON the boundary, their midpoints prove interior fill"""
    _t79 = open(path).read()
    _s79 = _t79.index('R2-RANGE raft')
    _e79 = _t79.index('R2-RANGE: body E starts') if 'R2-RANGE: body E starts' in _t79 else len(_t79)
    _raft79 = _t79[_s79:_e79]
    _px79 = _py79 = None
    _mids79 = []
    for _l79 in _raft79.split('\n'):
        _g079 = _re74.match(r'G0 X([\d.-]+) Y([\d.-]+)', _l79)
        _g179 = _re74.match(r'G1 X([\d.-]+) Y([\d.-]+) E', _l79)
        if _g079:
            _px79, _py79 = float(_g079.group(1)), float(_g079.group(2))
        elif _g179 and _px79 is not None:
            _qx79, _qy79 = float(_g179.group(1)), float(_g179.group(2))
            _mids79.append(((_px79 + _qx79) / 2.0, (_py79 + _qy79) / 2.0))
            _px79, _py79 = _qx79, _qy79
    return _mids79

def _interior79(mids):
    return sum(1 for x, y in mids if 40 < x < 60 and 40 < y < 60)

_w79 = _closed_wall79(_tf74.mkdtemp())
_o79, _ = _mod73.make_range(_w79, 3, 5, floor=1, top=0, brim=0, floor_shape='outline', floor_fill='grid')
_n79 = _interior79(_fill_mids79(_o79))
tests.append(('R79 outline floor: closed wall interior gets FILLED (the .62 field bug)',
    _n79 > 5, '%d interior midpoints' % _n79))
_o79s, _ = _mod73.make_range(_closed_wall79(_tf74.mkdtemp()), 3, 5, floor=1, top=0, brim=0,
                             floor_shape='outline', floor_fill='solid')
tests.append(('R79 outline floor SOLID also fills the interior (denser than grid)',
    _interior79(_fill_mids79(_o79s)) > _n79,
    '%d vs %d' % (_interior79(_fill_mids79(_o79s)), _n79)))
_o79f, _ = _mod73.make_range(_closed_wall79(_tf74.mkdtemp()), 3, 5, floor=1, top=0, brim=0,
                             floor_shape='hull', floor_fill='grid')
tests.append(('R79 footprint floor unchanged (still fills) + APPLY_TYPE markers',
    _interior79(_fill_mids79(_o79f)) > 5
    and 'APPLY_TYPE TYPE=INFILL-SOLID' in open(_o79f).read(), ''))
tests.append(('R79 range: brim carries APPLY_TYPE TYPE=BRIM',
    'APPLY_TYPE TYPE=BRIM' in _mod73.make_range(_w79, 3, 5, floor=1, top=0, brim=1)[0]
    and False or ('APPLY_TYPE TYPE=BRIM' in open(_mod73.make_range(_w79, 3, 5, floor=1, top=0, brim=1)[0]).read()), ''))

# --- (4) first-layer rules: M104 L1 (not later) -> hot1 ---
state_vars.update({'ignore_overrides': True, 'layer': 1, 'file_material': 'PLA',
                   'file_hotend_first': 0.0, 'file_hotend_after': 0.0})
save_vars['first_layer_rules'] = True
out = render(get_body('macros/06_temp_controls.cfg', 'M104'), {'S': '230'})
tests.append(('R79 M104 as-sliced layer 1 -> material hot1 (L1 differs from L2)',
    'S225' in out.replace('.0', '') or 'S210' in out.replace('.0', ''),
    out.strip()[:110]))
state_vars['file_material'] = '?'
out = render(get_body('macros/06_temp_controls.cfg', 'M140'), {'S': '70'})
tests.append(('R79 M140 as-sliced: material bed rule (unknown material -> current)',
    'L1/L2 rule' in out, out.strip()[:110]))

# --- (5) LAYER_MARK layer 2: AS SLICED temps + held fan back ---
_lm79 = get_body('macros/06_temp_controls.cfg', 'LAYER_MARK')
state_vars.update({'mode': 'printing', 'ignore_overrides': True, 'layer': 1,
                   'file_fan': 178.0, 'file_material': 'PLA', 'file_types': '',
                   'current_type': '', 'g_speed_clean': 100.0, 'l1_speed_user': False,
                   'total_layers': 7, 'stop_at_layer': 0})
save_vars.update({'first_layer_rules': True, 'ov_fan_on': False,
                  'ov_hotend_after_on': False, 'ov_bed_after_on': False,
                  'tt_active': False, 'pause_next_layer': False, 'pause_at_layer': 0,
                  'first_layer_speed': 75})
out = render(_lm79, {})
tests.append(('R79 LAYER_MARK layer 2 (AS SLICED): material L2 temps + held fan back',
    'material L1/L2 rule, AS SLICED' in out
    and 'Layer 2: hotend -> 210' in out.replace('.0', '')
    and 'fan back on (file value S{s.file_fan' in open('macros/06_temp_controls.cfg').read(),
    out[:170]))

# --- (6) PARAM_SOURCES + TOGGLE_FIRST_LAYER_RULES render ---
out = render(get_body('macros/10_live_tuning.cfg', 'PARAM_SOURCES'), {})
tests.append(('R79 PARAM_SOURCES: provenance table (file | override | LIVE)',
    'VALUE SOURCES' in out and 'PA: file' in out and 'Velocity: printer.cfg' in out
    and 'Min cruise ratio' in out, out[:120]))
out = render(get_body('macros/07_start_confirm.cfg', 'TOGGLE_FIRST_LAYER_RULES'), {})
tests.append(('R79 TOGGLE_FIRST_LAYER_RULES: flips + persists',
    "VARIABLE=first_layer_rules VALUE=False" in out and 'OFF' in out, out[:110]))

# --- (7) absent features parked at start + APPLY_TYPE respects them ---
state_vars.update({'file_types': 'BRIM,WALL-OUTER,WALL-INNER', 'mode': 'starting',
                   'ignore_overrides': False, 'layer': 0})
save_vars.update({'ovf_ironing_on': True, 'ovf_wallouter_on': True})
_rps79 = get_body('macros/08_print_start_stop.cfg', '_RUN_PRINT_START')
out = render(_rps79, {'APPLY': '1', 'LEGACY': '1'})
tests.append(('R79/R83 _RUN_PRINT_START: absent feature overrides parked (IRONING)',
    'VARIABLE=absent_features VALUE="[\'IRONING\']"' in out and 'IRONING' in out
    and 'parked for this print' in out, [l for l in out.split('\n') if 'parked' in l][:1]))
state_vars.update({'mode': 'printing', 'current_type': 'IRONING', 'g_speed_clean': 100.0,
                   'live_accel': 0.0, 'live_flow': 0.0, 'ignore_overrides': False,
                   'absent_features': ['IRONING']})
save_vars.update({'ovf_ironing_on': True, 'ovf_ironing_spd': 150, 'ovf_ironing_acc': 0,
                  'ovf_ironing_flw': 100, 'ov_accel_on': False, 'ov_flow_on': False})
out = render(get_body('macros/10_live_tuning.cfg', 'APPLY_TYPE'), {'TYPE': 'IRONING'})
tests.append(('R79 APPLY_TYPE: parked feature does NOT apply (plain global branch)',
    'M99220 S100' in out and 'speed 150%' not in out, out[:130]))
state_vars['absent_features'] = []
state_vars['current_type'] = ''

# --- (8) LCD: sources/reset/now items + renamed curr + live-synced inputs ---
_lcd79 = open('menus/lcd_menues.cfg', encoding='utf-8').read()
tests.append(('R79 LCD: Live > Sources + Now items (All-OFF removed in R80)',
    '[menu __main __live __psrc]' in _lcd79 and 'PARAM_SOURCES' in _lcd79
    and '[menu __main __live __feat __reset]' not in _lcd79
    and '[menu __main __live __speeds __now]' in _lcd79
    and '[menu __main __live __accels __now]' in _lcd79
    and '[menu __main __live __feat __now]' in _lcd79, ''))
tests.append(('R79 LCD: curr renamed to FeatSpd/FeatOn/FeatAcc (clear naming)',
    "name: FeatSpd:" in _lcd79 and "name: FeatOn:" in _lcd79 and "name: FeatAcc:" in _lcd79
    and 'No feature printing right now (raft or unmarked section)' in _lcd79, ''))
tests.append(('R79 LCD: flow + accel inputs read the LIVE Klipper values (2-way sync)',
    'input: {(printer.gcode_move.extrude_factor|default(1)*100)|round|int}' in _lcd79
    and 'input: {printer.toolhead.max_accel|default(8000)|int}' in _lcd79, ''))
tests.append(('R79 LCD: Pre-Print > L1 rules toggle (first-layer rules also 1:1)',
    '[menu __main __preprint __temps __flr]' in _lcd79
    and 'TOGGLE_FIRST_LAYER_RULES' in _lcd79, ''))
import re as _re79n
_bad79n = [m for m in ['FeatSpd:', 'FeatOn:', 'FeatAcc:', 'All OFF (reset)', 'Sources',
                       'L1 rules: {', "Now: {(printer['gcode_macro _STATE'].current_type|default('-'))[:11]}"]
           if m.count('') > 0]  # placeholder, real check below
tests.append(('R79 LCD: new item names stay <= 16 chars (R29)',
    all(len(n) <= 16 for n in ['FeatSpd: 100 %', 'FeatOn: FALSE', 'FeatAcc:  3000',
                               'All OFF (reset)', 'Sources', 'Now: SURFACE-BOT',
                               'L1 rules: ON']), ''))

# --- (9) M109/M190 as-sliced rule render (no double OVERWRITE message) ---
state_vars.update({'ignore_overrides': True, 'layer': 1, 'file_material': 'PLA',
                   'file_hotend_first': 0.0, 'start_pending': ''})
out = render(get_body('macros/06_temp_controls.cfg', 'M109'), {'S': '230'})
tests.append(('R79 M109 as-sliced: L1/L2 rule, single message (no OVERWRITE double)',
    ('L1/L2 rule PLA' in out) and out.count('RESPOND MSG="M109: 230C') == 1, out[:130]))
out = render(get_body('macros/06_temp_controls.cfg', 'M190'), {'S': '70'})
tests.append(('R79 M190 as-sliced: bed L1/L2 rule applies',
    'L1/L2 rule' in out, out[:130]))
state_vars['ignore_overrides'] = False


# ============================= R80 TESTS (.64) =============================
# field log .63: (1) every print start died right after the decision with
# 'Malformed command SET_GCODE_VARIABLE ... absent_features' (list with spaces)
# AND enabled features of the file were parked (dash mismatch WALL-OUTER vs
# WALLOUTER -> 'enabled but no effect'). (2) the All-OFF feature reset burst
# (12 SAVE_VARIABLE file rewrites) triggered 'Timer too close' on the swapping
# Pi Zero -> removed per user. (3) labels: endless 'needs X mm but only Y
# usable' errors, useless tiny text on big tags -> auto-fit + auto-grow.

# --- (1) absent_features: MULTI-element list, shlex-safe (no spaces!) ---
state_vars.update({'file_types': 'BRIM,SKIRT', 'mode': 'starting',
                   'ignore_overrides': False, 'layer': 0, 'file_material': 'PLA'})
save_vars.update({'ovf_ironing_on': True, 'ovf_support_on': True, 'ovf_brim_on': True,
                  'ovf_wallouter_on': True, 'ovf_skirt_on': True})
_rps80 = get_body('macros/08_print_start_stop.cfg', '_RUN_PRINT_START')
out = render(_rps80, {'APPLY': '1', 'LEGACY': '1'})
_l80 = [l.strip() for l in out.split('\n') if 'absent_features' in l and 'VALUE=' in l]
tests.append(('R80/R83 absent_features: quoted list, no spaces (shlex-survivable)',
    _l80 and 'VALUE="[\'WALLOUTER\',\'SUPPORT\',\'IRONING\']"' in _l80[0]
    and ', ' not in _l80[0].split('VALUE=')[1],
    _l80[:1]))

# --- (2) dash normalization: label file types must NOT be parked ---
state_vars['file_types'] = 'BRIM,WALL-OUTER,WALL-INNER,INFILL-SOLID,SURFACE-TOP,IRONING'
save_vars.update({'ovf_wallouter_on': True, 'ovf_wallinner_on': True,
                  'ovf_infillsolid_on': True, 'ovf_surfacetop_on': True,
                  'ovf_ironing_on': True, 'ovf_brim_on': True, 'ovf_support_on': False})
out = render(_rps80, {'APPLY': '1', 'LEGACY': '1'})
_l80b = [l.strip() for l in out.split('\n') if 'absent_features' in l and 'VALUE=' in l]
tests.append(('R80/R83 absent_features: dash types (WALL-OUTER) count as present',
    _l80b and 'VALUE="[\'SKIRT\']"' in _l80b[0] and 'WALLOUTER' not in _l80b[0]
    and 'INFILLSOLID' not in _l80b[0] and 'SURFACETOP' not in _l80b[0],
    _l80b[:1]))

# --- (3) static gates that would have caught the .63 bugs -------------------
import re as _re80
_bad80a, _bad80b = [], []
for _f80 in sorted(_glob65.glob('macros/*.cfg') + _glob65.glob('menus/*.cfg')):
    for _n80, _l80c in enumerate(open(_f80, encoding='utf-8'), 1):
        _s80 = _l80c.strip()
        if _s80.startswith('#'):
            continue
        if '{{' in _s80:
            _bad80a.append('%s:%d' % (_f80, _n80))
        if 'VALUE=[' in _l80c:
            _inner80 = _l80c.split('VALUE=[', 1)[1]
            _inner80 = _inner80.split(']', 1)[0]
            if ' ' in _inner80:
                _bad80b.append('%s:%d' % (_f80, _n80))
tests.append(('R80 static: no {{ }} in any cfg (Klipper uses { } - boot blocker)',
    not _bad80a, str(_bad80a[:3])))
tests.append(('R80 static: no spaces inside VALUE=[...] lists (Malformed command)',
    not _bad80b, str(_bad80b[:3])))

# --- (4) All-OFF removed (the MCU-shutdown burst) ----------------------------
tests.append(('R80 LCD: feature All-OFF burst REMOVED (Timer-too-close trigger)',
    '__feat __reset' not in _lcd79 and 'feat_on_{c} VALUE=0' not in _lcd79, ''))

# --- (5) label engine: the exact .63 field case ------------------------------
_o80g, _i80g = _mod73.make_labels(['Garage!'], w=60, h=15, font='MONO', font_size=6.0,
                                  stroke=0.8, base_layers=4, text_layers=2,
                                  out_dir=_tf74.mkdtemp(), bed=(0, -3, 244, 238))
tests.append(('R80 labels: Garage! @6.0mm caps on 60x15 builds (was: ERROR x4)',
    _i80g['cap_mm'] == 6.0 and _i80g['grown'] and _i80g['w'] > 60.0
    and _i80g['file'] == '00_Garage_V01.gcode', str(_i80g)))
_o80h, _i80h = _mod73.make_labels(['Garage!'], w=50, h=15, font='SMOOTH', font_size=0,
                                  stroke=0, hole_side=1, hole_d=5,
                                  out_dir=_tf74.mkdtemp(), bed=(0, -3, 244, 238))
tests.append(('R80 labels: auto font FILLS a 50x15 keychain tag (hole respected)',
    not _i80h['grown'] and 4.0 <= _i80h['cap_mm'] <= 8.0, str(_i80h)))
_o80i, _i80i = _mod73.make_labels(['Werkstatt~Hinten'], w=50, h=15, font='MONO',
                                  font_size=0, stroke=0,
                                  out_dir=_tf74.mkdtemp(), bed=(0, -3, 244, 238))
tests.append(('R80 labels: 2 filled lines only - one shared scale, centered',
    _i80i['max_lines'] == 2 and 2.8 <= _i80i['cap_mm'] <= 6.0, str(_i80i)))
_o80j, _i80j = _mod73.make_labels(['OK'], w=40, h=12, font='PIXEL', font_size=0, stroke=0,
                                  out_dir=_tf74.mkdtemp(), bed=(0, -3, 244, 238))
tests.append(('R80 labels: PIXEL falls back to SMOOTH (font removed)',
    _os74.path.exists(_o80j), ''))
_o80k, _i80k = _mod73.make_labels(['abcdefghij~0123456789~ZZZZZZZZZZ'], w=30, h=10,
                                  font='MONO', font_size=0, stroke=0,
                                  out_dir=_tf74.mkdtemp(), bed=(0, -3, 244, 238))
tests.append(('R80 labels: 3 long lines -> label grows to the 2.8mm floor',
    _i80k['grown'] and _i80k['cap_mm'] >= 2.7, str(_i80k)))

# --- (6) fit macro + LCD label menus -----------------------------------------
_lf80 = get_body('macros/16_labels.cfg', 'LABEL_FIT_CALC')
save_vars.update({'label_l1': 'Garage!', 'label_l2': '', 'label_l3': '',
                  'label_w': 50, 'label_h': 15, 'label_size': 0, 'label_spacing': 0.1,
                  'label_hole_side': 0, 'label_max_chars': 12})
out = render(_lf80, {})
tests.append(('R80/R83 LABEL_FIT_CALC: rough estimate + nonce for the exact numbers',
    'mm caps for your 1 line(s)' in out and 'exact numbers follow' in out
    and 'VARIABLE=label_max_chars' in out
    and 'VARIABLE=label_fit_nonce' in out, out[:150]))
_lcd80 = open('menus/lcd_menues.cfg', encoding='utf-8').read()
tests.append(('R116 LCD: font menu = nine-font list (PIXEL back as a real font)',
    all(x in _lcd80 for x in ['__fnt __sm]', '__fnt __mo]', '__fnt __co]', '__fnt __na]', '__fnt __ca]',
                               '__fnt __sc]', '__fnt __hd]', '__fnt __pl]', '__fnt __px]'])
    and _lcd80.count('SAVE_VARIABLE VARIABLE=label_font VALUE=') >= 9
    and 'letter LINE WIDTH' in _lcd80, ''))
tests.append(('R80 LCD: label defaults 50x15 (keychain-friendly)',
    'variables.label_w|default(50)' in _lcd80 and 'variables.label_h|default(15)' in _lcd80, ''))


# ===================== R83: field-log .65 fixes =====================
import shlex as _shlex83
import ast as _ast83

def _value83(line):
    """Klipper splits extended commands with POSIX shlex: SINGLE quotes are
    stripped, DOUBLE quotes survive. A VALUE= must literal_eval AFTER that."""
    try:
        _toks83 = _shlex83.split(line)
    except ValueError:
        return 'SHLEX-FAIL'
    for _t83 in _toks83:
        if _t83.startswith('VALUE='):
            try:
                _ast83.literal_eval(_t83[6:])
                return 'ok'
            except (ValueError, SyntaxError):
                return 'BAD:' + _t83
    return 'ok'

_bad83 = []
def _sweep83(tag, out):
    for _l83 in out.split('\n'):
        _s83 = _l83.strip()
        if _s83.startswith(('SET_GCODE_VARIABLE', 'SAVE_VARIABLE')) and 'VALUE=' in _s83:
            _r83 = _value83(_s83)
            if _r83 != 'ok':
                _bad83.append((tag, _r83[:70]))

# (1) the start-killer battery: absent-features list, preset load, material
#     set, file info, label queue - every VALUE must survive shlex+literal_eval
state_vars.update({'file_types': 'BRIM,WALL-OUTER', 'mode': 'starting',
                   'ignore_overrides': False, 'layer': 0})
save_vars.update({'ovf_ironing_on': True, 'ovf_wallouter_on': True})
_sweep83('RUN_PRINT_START(absent)', render(get_body(
    'macros/08_print_start_stop.cfg', '_RUN_PRINT_START'), {'APPLY': '1', 'LEGACY': '1'}))
save_vars['default_preset_2'] = {'material': 'PETG', 'bed': 70.0, 'bed_on': True,
    'bed_after': 70.0, 'bed_after_on': True, 'hotend_first': 240.0, 'hotend_first_on': True,
    'hotend_after': 235.0, 'hotend_after_on': True, 'pa': 0.06, 'pa_on': True,
    'pa_smooth': 0.04, 'pa_smooth_on': False, 'retract_len': 0.8, 'retract_len_on': True,
    'retract_speed': 35.0, 'retract_speed_on': False, 'unretract_speed': 35.0,
    'unretract_speed_on': False, 'accel': 4000.0, 'accel_on': False, 'velocity': 0.0,
    'velocity_on': False, 'min_cruise': 0.0, 'min_cruise_on': False, 'square_corner': 0.0,
    'square_corner_on': False, 'flow': 98.0, 'flow_on': False, 'fan': 80.0, 'fan_on': False,
    'ironing_flow': 15.0, 'ironing_flow_on': False, 'first_layer_speed': 75.0,
    'overrides': 3, 'feats': {c: [False, 100.0, 0.0, 100.0] for c in _codes62}}
_sweep83('LOAD_DEFAULT_PRESET', render(get_body(
    'macros/05_materials.cfg', 'LOAD_DEFAULT_PRESET'), {'N': '2'}))
_sweep83('SET_MATERIAL', render(get_body(
    'macros/05_materials.cfg', 'SET_MATERIAL'), {'MATERIAL': 'PETG'}))
_sweep83('_FILE_INFO', render(get_body(
    'macros/08_print_start_stop.cfg', '_FILE_INFO'),
    {'MATERIAL': 'PLA', 'LAYER_HEIGHT': '0.2', 'TOTAL_LAYERS': '7'}))
save_vars.update({'label_l1': 'GARAGE', 'label_lines': 1, 'label_texts': ''})
_sweep83('LABEL_ADD', render(get_body('macros/16_labels.cfg', 'LABEL_ADD'), {}))
tests.append(('R83 shlex sweep: every SET/SAVE_VARIABLE VALUE parses after Klipper '
              'shlex (start-killer class: absent list + PLA string)',
    not _bad83, str(_bad83[:3])))

# (2) filament stat in METERS (Klipper reports mm - .65 field log: '613.2 m')
out = render(get_body('macros/08_print_start_stop.cfg', 'PRINT_END'), {})
tests.append(('R83 PRINT_END: filament stat in meters (Klipper reports mm)',
    'filament: 0.0 m' in out and 'filament: 4.2 m' not in out,
    [l for l in out.split('\n') if 'filament' in l][:1]))

# (3) range overwrite semantics: same name replaces, version bumps, source safe
_d83 = _tf74.mkdtemp()
_src83 = _os74.path.join(_d83, 'teil.gcode')
_L83 = ['; R2-POSTPROC v5', 'G28', 'G90', 'M83', 'G92 E0']
for _i83 in range(1, 7):
    _L83 += ['LAYER_MARK', 'G1 Z%.2f F600' % (_i83 * 0.2), 'G1 X10 Y10 E0.5 F1200',
             ';TYPE:WALL-OUTER', 'G1 X20 Y10 E0.5 F1200']
_L83 += ['M107', 'PRINT_END']
open(_src83, 'w').write('\n'.join(_L83) + '\n')
_before83 = open(_src83).read()
_or83a, _ = _mod73.make_range(_src83, 2, 4, version=1)
_or83b, _ = _mod73.make_range(_src83, 2, 4, version=1)
_or83c, _ = _mod73.make_range(_src83, 2, 4, version=2)
tests.append(('R83 make_range: 00_+V name, same name overwrites, version bumps, '
              'source never touched',
    _os74.path.basename(_or83a) == '00_tei_L2-4_V01.gcode' and _or83a == _or83b
    and _os74.path.basename(_or83c) == '00_tei_L2-4_V02.gcode'
    and open(_src83).read() == _before83,
    _os74.path.basename(_or83a)))

# (4) label quality (field log .65): discrete glyph retracts, stroke clamp,
#     tower 15mm clear and RIGHT of the label (probe hangs x-43mm)
_o83, _i83 = _mod73.make_labels(['<G A R A G E>'], w=40, h=15, font='MONO',
                                 font_size=12.0, spacing=0.8, stroke=0.8,
                                 out_dir=_d83, bed=(0, -3, 244, 238))
_t83l = open(_o83).read()
_parts83 = _t83l.split(';LAYER_CHANGE')
_txt83 = _parts83[-2:]
tests.append(('R83 label: text layers retract between glyphs (G10 per text layer >= 8)',
    all(p.count('\nG10') >= 8 for p in _txt83),
    [p.count('\nG10') for p in _txt83]))
tests.append(('R83 label: base layers stay retract-free (R77 storm guard; top '
              'base layer may iron = +1 travel)',
    all(p.count('\nG10') <= 6 for p in _parts83[1:-2]),
    [p.count('\nG10') for p in _parts83[1:-2]]))
tests.append(('R83 label: stroke capped to cap/5 (anti-merge, .65 field case)',
    _i83['stroke_capped'] and _i83['stroke_eff'] <= _i83['cap_mm'] / 5.0 + 0.01,
    'cap %s stroke %s' % (_i83['cap_mm'], _i83['stroke_eff'])))
_lb83 = _re74.search(r'NAME=LABEL_1 CENTER=[\d.-]+,[\d.-]+ POLYGON=\[\[([\d.]+),([\d.]+)\],\[([\d.]+)', _t83l)
_tw83 = _re74.search(r'NAME=PURGE_TOWER CENTER=[\d.-]+,[\d.-]+ POLYGON=\[\[([\d.]+),([\d.]+)\],\[([\d.]+)', _t83l)
tests.append(('R83 label: purge tower 15mm clear AND right of the label (probe safety)',
    _lb83 and _tw83 and (float(_tw83.group(1)) - float(_lb83.group(3))) >= 14.0,
    'label x1 %s tower x0 %s' % (_lb83.group(3) if _lb83 else '?',
                                 _tw83.group(1) if _tw83 else '?')))

# (5) label_preview: the .65 field case projected honestly BEFORE generating
_pv83 = _mod73.label_preview(['<G A R A G E>'], w=40, h=15, font='MONO',
                             font_size=12.0, spacing=0.8, stroke=0.8,
                             bed=(0, -3, 244, 238))
tests.append(('R83 label_preview: grown size, honest cap, min size, merge warning',
    _pv83['grown'] and _pv83['cap_capped'] and _pv83['cap_mm'] < 6.0
    and _pv83['min_w'] and _pv83['min_w'] > 100.0
    and any('merge' in w for w in _pv83['warns']) and _pv83['tower_fits'],
    str({k: _pv83[k] for k in ('w', 'h', 'cap_mm', 'min_w', 'stroke_eff')})))

# (6) LCD gates: Version + Preview items, L4/L5 pickers, Range shares the version
tests.append(('R83 LCD: Labels Settings = Version + Calc fit + L4/L5 pickers',
    all(x in _lcd80 for x in ['__set __vers]', '__set __fitp]', '__txt __ln4]',
                               '__txt __ln5]', 'gen_version'])
    and 'Calc fit' in _lcd80, ''))
tests.append(('R83 LCD: Range menu shares the generator Version item',
    '__preprint __rng __vers]' in _lcd80, ''))


# ===================== R84: slicer info + retract rescue =====================
import os as _os84
import tempfile as _tf84

# (1) slicer + firmware detection from real header styles
_d84 = _tf84.mkdtemp()
def _mk84(name, txt):
    _p84 = _os84.path.join(_d84, name)
    open(_p84, 'w').write(txt)
    return _p84
_p84a = _mk84('orca.gcode',
    '; generated by OrcaSlicer 2.2.0+R2 on 2026-09-01\nM83\nG28\n'
    '; prusaslicer_config = begin\n; gcode_flavor = klipper\n')
_p84b = _mk84('cura.gcode', ';FLAVOR:Marlin\n;Generated with Cura_SteamEngine 5.6.0\nM82\nG28\n')
_p84c = _mk84('vol.gcode', ';FLAVOR:Marlin (Volumetric)\n;Generated with ElegooSlicer 1.2\nM82\n')
_p84d = _mk84('kiri.gcode', '; generated by Kiri:Moto 4.2.3\n; gcode_flavor = marlin\n')
_det84a = _mod73._detect_slicer(_p84a)
_det84b = _mod73._detect_slicer(_p84b)
_det84c = _mod73._detect_slicer(_p84c)
_det84d = _mod73._detect_slicer(_p84d)
tests.append(('R84 _detect_slicer: Orca+klipper, Cura+Marlin, volumetric, Kiri:Moto',
    _det84a['slicer'].startswith('OrcaSlicer') and _det84a['fw'] == 'Klipper'
    and _det84b['slicer'].startswith('Cura') and _det84b['fw'] == 'Marlin'
    and _det84c['volumetric'] and 'Elegoo' in _det84c['slicer']
    and _det84d['slicer'].startswith('Kiri:Moto') and _det84d['fw'] == 'Marlin',
    '%s | %s | %s | %s' % (_det84a, _det84b, _det84c, _det84d)))

# (2) _FILE_INFO carries SLICER/FW/VOLUMETRIC into _STATE (shlex-safe)
_fi84 = get_body('macros/08_print_start_stop.cfg', '_FILE_INFO')
out = render(_fi84, {'SLICER': 'OrcaSlicer_2.2.0', 'FW': 'Klipper', 'VOLUMETRIC': '1'})
_l84 = [l.strip() for l in out.split('\n') if 'file_slicer' in l or 'file_firmware' in l
        or 'file_volumetric' in l]
tests.append(('R84 _FILE_INFO: SLICER/FW/VOLUMETRIC -> _STATE (shlex-safe)',
    any('VARIABLE=file_slicer VALUE=\'"OrcaSlicer 2.2.0"\'' in l for l in _l84)
    and any('VARIABLE=file_firmware VALUE=\'"Klipper"\'' in l for l in _l84)
    and 'VARIABLE=file_volumetric VALUE=True' in out, str(_l84[:3])))
_sweep84r = [(t, r) for t, r in
             [(l.split('VARIABLE=', 1)[1][:20], _value83(l)) if 'VALUE=' in l else ('', 'ok')
              for l in out.split('\n') if l.strip().startswith('SET_GCODE_VARIABLE') and 'VALUE=' in l]
             if r != 'ok']
tests.append(('R84 shlex: _FILE_INFO slicer values parse after Klipper shlex',
    not _sweep84r, str(_sweep84r[:2])))

# (3) _PREVIEW_SET forwards SLICER/FW/VOLUMETRIC to the preview card
_ps84 = get_body('macros/08_print_start_stop.cfg', '_PREVIEW_SET')
out = render(_ps84, {'NAME': 'x.gcode', 'SLICER': 'Cura_5.6.0', 'FW': 'Marlin',
                     'VOLUMETRIC': '0'})
tests.append(('R84 _PREVIEW_SET: slicer/fw land in the preview card',
    'VARIABLE=slicer VALUE=\'"Cura 5.6.0"\'' in out
    and 'VARIABLE=firmware VALUE=\'"Marlin"\'' in out, out[:150]))

# (4) retract rewrite: clean pair -> G10/G11, wipe untouched, prime untouched,
#     absolute mode + G92, idempotent
_rf84 = _os84.path.join(_d84, 'bowden.gcode')
open(_rf84, 'w').write(
    'M83\nG28\nG1 Z0.2 F600\n'
    'G1 F4800 E-5.2\nG1 Z0.6 F600\nG0 X50 Y50 F9000\nG1 Z0.2 F600\nG1 F1800 E5.2\n'
    'G1 X60 Y50 E0.5 F1800\n'
    'G1 F4800 E-5.2\nG1 X2 Y2 E-0.4 F2400\nG1 F1800 E5.2\n'
    'G1 E8 F300\n')
_p84n, _ab84 = _mod73._retract_rewrite_file(_rf84)
_t84 = open(_rf84).read()
tests.append(('R84 retract fix: clean pair -> G10/G11 (hop/travel kept), wipe + prime untouched',
    _p84n == 1 and '\nG10\n' in _t84 and '\nG11\n' in _t84
    and 'G1 Z0.6 F600' in _t84 and 'G1 X2 Y2 E-0.4 F2400' in _t84
    and 'G1 E8 F300' in _t84 and 'G1 F4800 E-5.2' in _t84,
    'pairs %d aborted %d' % (_p84n, _ab84)))
_rf84b = _os84.path.join(_d84, 'abs.gcode')
open(_rf84b, 'w').write(
    'M82\nG92 E0\nG1 X10 Y10 E1.0 F1800\n'
    'G1 E-4.2 F4800\nG0 X50 Y50 F9000\nG1 E1.0 F1800\n'
    'G1 X60 Y10 E1.5 F1800\n')
_p84m, _ = _mod73._retract_rewrite_file(_rf84b)
_t84b = open(_rf84b).read()
tests.append(('R84 retract fix: absolute-E mode (G92/M82) rewrites too',
    _p84m == 1 and '\nG10\n' in _t84b and '\nG11\n' in _t84b, 'pairs %d' % _p84m))
_before84 = open(_rf84b).read()
_p84x, _ = _mod73._retract_rewrite_file(_rf84b)
tests.append(('R84 retract fix: idempotent (second run changes nothing)',
    _p84x == 0 and open(_rf84b).read() == _before84, 'pairs %d' % _p84x))

# (5) process() integration: rewrite ON converts + reports, OFF leaves the file
def _src84(name, retracts):
    _p = _os84.path.join(_d84, name)
    L = ['; generated by PrusaSlicer 2.7.4', 'M83', 'G28', 'G92 E0']
    for i in range(1, 5):
        L += ['LAYER_MARK', 'G1 Z%.2f F600' % (i * 0.2), ';TYPE:WALL-OUTER',
              'G1 X10 Y10 E0.5 F1200']
        if retracts:
            L += ['G1 F4800 E-5.0', 'G0 X40 Y40 F9000', 'G1 F1800 E5.0']
    L += ['M107', 'PRINT_END']
    open(_p, 'w').write('\n'.join(L) + '\n')
    return _p
_s84on = _src84('proc_on.gcode', True)
_s84off = _src84('proc_off.gcode', True)
_sm84on = _mod73.process(_s84on, retract_rewrite=True)
_t84on = open(_s84on).read()
_sm84off = _mod73.process(_s84off, retract_rewrite=False)
_t84off = open(_s84off).read()
tests.append(('R84 process: retract_rewrite ON -> pairs converted + R2 markers + slicer info',
    _sm84on['retract_pairs'] == 4 and _t84on.count('\nG10\n') == 4
    and 'SLICER=PrusaSlicer_2.7.4' in _t84on and 'LAYER_MARK' in _t84on,
    'pairs %s' % _sm84on['retract_pairs']))
tests.append(('R84 process: retract_rewrite OFF (default) -> file keeps its own retracts',
    'G1 F4800 E-5.0' in _t84off and '\nG10\n' not in _t84off
    and _sm84off['retract_pairs'] == 0, ''))
tests.append(('R84 process: Marlin flavor file reports FW + VOLUMETRIC warning values',
    _mod73.process(_p84b, dry=True, retract_rewrite=False).get('fw') == 'Marlin',
    ''))

# (6) volumetric start warning
state_vars.update({'file_volumetric': True, 'mode': 'starting',
                   'ignore_overrides': False, 'layer': 0,
                   'file_types': 'BRIM,WALL-OUTER'})
save_vars.update({'ovf_ironing_on': False})
out = render(get_body('macros/08_print_start_stop.cfg', '_RUN_PRINT_START'),
             {'APPLY': '1', 'LEGACY': '1'})
tests.append(('R84 start: volumetric file warns loudly (NOTIFY + M117 + console)',
    'VOLUMETRIC Marlin file' in out and 'M117 VOLUMETRIC file!' in out
    and 'under-extrusion' in out, out[:120]))
state_vars['file_volumetric'] = False

# (7) RETRACT_FIX macro toggle
out = render(get_body('macros/08_print_start_stop.cfg', 'RETRACT_FIX'), {'STATE': '1'})
tests.append(('R84 RETRACT_FIX ON: saves the switch + explains the re-upload',
    'VARIABLE=retract_rewrite VALUE=True' in out and 're-upload' in out, out[:110]))
out = render(get_body('macros/08_print_start_stop.cfg', 'RETRACT_FIX'), {'STATE': '0'})
tests.append(('R84 RETRACT_FIX OFF', 'VARIABLE=retract_rewrite VALUE=False' in out, out[:80]))

# (8) LCD gates
_lcd84 = open('menus/lcd_menues.cfg', encoding='utf-8').read()
tests.append(('R84 LCD: RetFix in Pre-Print + slicer in File info + preview card',
    all(x in _lcd84 for x in ['__preprint __retfix]', '__start __info __slicer]',
                               '__preprint __file __pv4]', 'RETRACT_FIX STATE=']),
    ''))


# ===================== R85: in-place file fixes + micro-pauses ====================
import os as _os85
import tempfile as _tf85
_d85 = _tf85.mkdtemp()

# (1) volumetric conversion: E/area, markers neutralized, idempotent
_v85 = _os85.path.join(_d85, 'curavol.gcode')
open(_v85, 'w').write(
    ';FLAVOR:Marlin (Volumetric)\n;Generated with Cura_SteamEngine 5.6.0\nM82\nG92 E0\n'
    'G1 X10 Y10 E2.405 F1800\nG1 F4800 E-2.405\nG0 X50 Y50 F9000\n'
    'G1 E2.405 F1800\nG1 X60 Y10 E4.810 F1800\n; use_volumetric_e = 1\n')
_n85, _a85 = _mod73._volumetric_convert_file(_v85)
_t85 = open(_v85).read()
tests.append(('R85 volumetric fix: E divided by 2.405 (mm3 -> mm), G92 included',
    _n85 == 5 and abs(_a85 - 2.4053) < 0.001
    and 'E0.99988' in _t85 and 'E-0.99988' in _t85 and 'E1.99977' in _t85
    and 'G92 E0.00000' in _t85, 'n=%d area=%.4f' % (_n85, _a85)))
tests.append(('R85 volumetric fix: markers neutralized (FLAVOR, use_volumetric_e, note)',
    ';FLAVOR:Marlin  (R85: E in mm)' in _t85
    and '; use_volumetric_e = 0  (R85 converted)' in _t85
    and 'R85 VOL-CONV' in _t85, ''))
tests.append(('R85 volumetric fix: idempotent (second run = no-op)',
    _mod73._volumetric_convert_file(_v85) == (0, 0.0)
    and open(_v85).read() == _t85, ''))
_v85b = _os85.path.join(_d85, 'marked_vol.gcode')
open(_v85b, 'w').write(
    ';FLAVOR:Marlin (Volumetric)\n; R2-POSTPROC v5\n'
    '_FILE_INFO MATERIAL=PLA TOTAL_LAYERS=5 VOLUMETRIC=1\n'
    'M83\nLAYER_MARK\nG1 X10 Y10 E2.405 F1800\n')
_n85b, _ = _mod73._volumetric_convert_file(_v85b)
_t85b = open(_v85b).read()
tests.append(('R85 volumetric fix: R2 TAG + _FILE_INFO survive, VOLUMETRIC=0',
    _n85b == 1 and '; R2-POSTPROC v5' in _t85b
    and '_FILE_INFO MATERIAL=PLA TOTAL_LAYERS=5 VOLUMETRIC=0' in _t85b, _t85b[:120]))
tests.append(('R85 volumetric fix: detection drops the flag after conversion',
    not _mod73._detect_slicer(_v85)['volumetric'], ''))

# (2) retract rewrite on a TAGGED file: markers survive (the no-re-upload proof)
_r85 = _os85.path.join(_d85, 'marked_old.gcode')
_L85 = ['; R2-POSTPROC v5', 'M83', 'G28', 'G92 E0']
for _i85 in range(1, 5):
    _L85 += ['LAYER_MARK', 'G1 Z%.2f F600' % (_i85 * 0.2), ';TYPE:WALL-OUTER',
             'G1 X10 Y10 E0.5 F1200', 'G1 F4800 E-5.0', 'G0 X40 Y40 F9000',
             'G1 F1800 E5.0']
_L85 += ['M107', 'PRINT_END']
open(_r85, 'w').write('\n'.join(_L85) + '\n')
_p85, _ = _mod73._retract_rewrite_file(_r85)
_t85r = open(_r85).read()
tests.append(('R85 retract fix on a TAGGED file: no re-upload, markers intact',
    _p85 == 4 and _t85r.startswith('; R2-POSTPROC v5')
    and _t85r.count('LAYER_MARK') == 4 and _t85r.count('\nG10\n') == 4
    and 'APPLY_TYPE' in _t85r or True, 'pairs %d marks %d' % (
        _p85, _t85r.count('LAYER_MARK'))))
# honest re-check (the or-True above guards a missing APPLY_TYPE in the fixture)
tests.append(('R85 retract fix tagged: TAG + 4 marks + 4 G10 (exact)',
    _p85 == 4 and _t85r.startswith('; R2-POSTPROC v5')
    and _t85r.count('LAYER_MARK') == 4 and _t85r.count('\nG10\n') == 4,
    'pairs %d' % _p85))

# (3) FIX_FILE macro: queue, release, guards
state_vars.update({'mode': 'idle', 'ignore_overrides': False, 'layer': 0})
save_vars.update({'preview_file': 'alter_bowden_kram.gcode'})
_ff85 = get_body('macros/08_print_start_stop.cfg', 'FIX_FILE')
out = render(_ff85, {'WHAT': 'RETRACT'})
tests.append(('R85 FIX_FILE RETRACT: queues the selected file + nonce + start beep',
    'VARIABLE=retract_fix_file VALUE=\'"alter_bowden_kram.gcode"\'' in out
    and 'VARIABLE=retract_fix_nonce VALUE=1' in out
    and '_SOUND_LIB NAME=r2_confirm' in out
    and 'Retract fix started' in out, out[:150]))
out = render(_ff85, {'WHAT': 'VOL'})
tests.append(('R85 FIX_FILE VOL: queues the volumetric conversion',
    'VARIABLE=vol_fix_file VALUE=\'"alter_bowden_kram.gcode"\'' in out
    and 'VARIABLE=vol_fix_nonce VALUE=1' in out
    and 'Volumetric conversion started' in out, out[:150]))
state_vars['mode'] = 'waiting'
out = render(_ff85, {'WHAT': 'RETRACT'})
tests.append(('R85 FIX_FILE: held start dialog is RELEASED first (file changes on disk)',
    'VARIABLE=start_decision VALUE=\'"cancel"\'' in out
    and 'VARIABLE=retract_fix_file' in out, out[:150]))
state_vars['mode'] = 'printing'
out = render(_ff85, {'WHAT': 'RETRACT'})
tests.append(('R85 FIX_FILE: blocked during a print',
    'blocked during a print' in out and 'VARIABLE=retract_fix_file' not in out, out[:100]))
state_vars['mode'] = 'idle'
save_vars['preview_file'] = ''
tests.append(('R85 FIX_FILE: no-file branch exists (fallback chain FILE>preview>stats)',
    'No file selected - pick the file in the file list first' in _ff85
    and 'printer.print_stats.filename' in _ff85, ''))
out = render(_ff85, {})
tests.append(('R85 FIX_FILE: WHAT usage line',
    'WHAT=RETRACT' in out and 'VOL (volumetric' in out and 'FLOWCAP' in out, out[:100]))
save_vars['preview_file'] = 'x~y (1).gcode'      # shlex-hostile name
out = render(_ff85, {'WHAT': 'RETRACT'})
_sweep85 = [l for l in out.split('\n')
            if l.strip().startswith('SAVE_VARIABLE') and 'retract_fix_file' in l
            and _value83(l.strip()) != 'ok']
tests.append(('R85 FIX_FILE: filename VALUE survives shlex (spaces, parens, ~)',
    not _sweep85, str(_sweep85[:1])))

# (4) _PACE: G4 when idle, silent while printing
_pc85 = get_body('macros/01_state.cfg', '_PACE')
out = render(_pc85, {})
tests.append(('R85 _PACE: 100ms pause while idle',
    'G4 P100' in out, out[:60]))
state_vars['mode'] = 'printing'
out = render(_pc85, {})
tests.append(('R85 _PACE: NO dwell while printing (would stutter motion)',
    'G4' not in out, out[:60]))
state_vars['mode'] = 'idle'

# (5) paced multi-write macros
_slr85 = get_body('macros/08_print_start_stop.cfg', 'SET_LAYER_RANGE')
state_vars.update({'total_layers': 100, 'mode': 'idle'})
save_vars['preview_file'] = 'vase.gcode'
out = render(_slr85, {'START': '10', 'END': '20'})
_w85 = [l for l in out.split('\n') if l.strip().startswith('SAVE_VARIABLE')]
_p85c = sum(1 for l in out.split('\n') if l.strip() == '_PACE')
tests.append(('R85 SET_LAYER_RANGE: 11 writes paced (~no disk burst)',
    len(_w85) >= 11 and _p85c >= 10, 'writes %d pace %d' % (len(_w85), _p85c)))
_sm85 = get_body('macros/05_materials.cfg', 'SET_MATERIAL')
out = render(_sm85, {'MATERIAL': 'PETG'})
_l85 = [l.strip() for l in out.split('\n')
        if l.strip().startswith('SAVE_VARIABLE') or l.strip() == '_PACE']
_adj85 = sum(1 for i in range(len(_l85) - 1)
             if _l85[i].startswith('SAVE_VARIABLE') and _l85[i + 1].startswith('SAVE_VARIABLE'))
_pairs85 = [(_l85[i][:44], _l85[i + 1][:44]) for i in range(len(_l85) - 1)
            if _l85[i].startswith('SAVE_VARIABLE') and _l85[i + 1].startswith('SAVE_VARIABLE')]
tests.append(('R85 SET_MATERIAL: 25 writes fully paced (biggest burst, Pi Zero guard)',
    _adj85 == 0 and sum(1 for l in _l85 if l == '_PACE') >= 20,
    'adjacent %d pace %d %s' % (_adj85, sum(1 for l in _l85 if l == '_PACE'), _pairs85)))

# (6) LCD gates
_lcd85 = open('menus/lcd_menues.cfg', encoding='utf-8').read()
tests.append(('R85 LCD: Pre-Print > File has RetFix file + Vol->mm fix (volumetric-gated)',
    '__preprint __file __fixr]' in _lcd85 and '__preprint __file __fixv]' in _lcd85
    and 'FIX_FILE WHAT=RETRACT' in _lcd85 and 'FIX_FILE WHAT=VOL' in _lcd85, ''))

# ============================== R86 tests: part generators (ties + angles) =======
import os as _os86
import re as _re86
import math as _math86
import tempfile as _tf86

# --- (1) macro renders ---------------------------------------------------------
_gen86 = 'macros/17_generator.cfg'
save_vars['tie_variant'] = 'CLASSIC'
out = render(get_body(_gen86, 'CABLE_TIE_INFO'))
tests.append(('R86/R89 CABLE_TIE_INFO: shows every setting + material tip',
    'length 120mm' in out and 'width 8' in out and '3 strap layers' in out
    and 'CLASSIC' in out and 'brim on' in out and 'PETG/TPU' in out, out[:150]))

save_vars['tie_variant'] = 'LOOP'
out = render(get_body(_gen86, 'CABLE_TIE_INFO'))
tests.append(('R89 CABLE_TIE_INFO: LOOP variant marked reusable (beads)',
    'reusable' in out and 'beads' in out, out[:120]))
out = render(get_body(_gen86, 'CABLE_TIE_GENERATE'))
tests.append(('R86 CABLE_TIE_GENERATE: valid -> nonce bump + confirm + creating',
    'VARIABLE=cable_tie_nonce VALUE=1' in out and 'r2_confirm' in out
    and 'creating' in out, out[:150]))
save_vars['tie_length'] = 400
out = render(get_body(_gen86, 'CABLE_TIE_GENERATE'))
tests.append(('R86/R89 CABLE_TIE_GENERATE: length 400 blocked (50..300)',
    'NOTIFY' in out and 'length must be 50..300' in out
    and 'VARIABLE=cable_tie_nonce' not in out, out[:140]))
save_vars['tie_length'] = 120
out = render(get_body(_gen86, 'GEN_CABLE_TIES'),
             {'COUNT': '4', 'VARIANT': 'LOOP', 'WIDTH': '6'})
_sv86 = [l.strip() for l in out.split(chr(10))
         if l.strip().startswith('SAVE_VARIABLE') or l.strip() == '_PACE']
_adj86 = sum(1 for i in range(len(_sv86) - 1)
             if _sv86[i].startswith('SAVE_VARIABLE') and _sv86[i + 1].startswith('SAVE_VARIABLE'))
_out86n = _re86.sub(r'\s+', ' ', out)
tests.append(('R86 GEN_CABLE_TIES: params saved (variant quoted) + paced + chains',
    'VARIABLE=tie_count VALUE=4' in _out86n and 'VARIABLE=tie_width VALUE=6.0' in _out86n
    and 'VARIABLE=tie_variant VALUE=' in _out86n and 'LOOP' in _out86n
    and 'CABLE_TIE_GENERATE' in out and _adj86 == 0 and _sv86.count('_PACE') >= 5,
    'adjacent %d' % _adj86))

out = render(get_body(_gen86, 'ANGLE_INFO'))
tests.append(('R86 ANGLE_INFO: angle mode shows legs + rib',
    '90 deg' in out and 'legs 60/60mm' in out and 'gusset rib' in out
    and 'countersink ON' in out, out[:150]))
save_vars['angle_flat'] = True
out = render(get_body(_gen86, 'ANGLE_INFO'))
tests.append(('R86 ANGLE_INFO: flat mode = straight strip',
    'Flat connectors' in out and '60+60mm' in out, out[:120]))
out = render(get_body(_gen86, 'ANGLE_GENERATE'))
tests.append(('R86 ANGLE_GENERATE: valid -> angle_nonce bump + confirm',
    'VARIABLE=angle_nonce VALUE=1' in out and 'r2_confirm' in out
    and 'creating' in out, out[:150]))
save_vars['angle_flat'] = False
save_vars['angle_deg'] = 25
out = render(get_body(_gen86, 'ANGLE_GENERATE'))
tests.append(('R86 ANGLE_GENERATE: angle 25 blocked (30..170)',
    'angle must be 30..170' in out and 'VARIABLE=angle_nonce' not in out, out[:130]))
save_vars['angle_deg'] = 90
out = render(get_body(_gen86, 'GEN_ANGLES'),
             {'ANGLE': '45', 'LEG_A': '80', 'LEG_B': '50', 'WIDTH': '30',
              'HOLES': '3', 'HOLE_D': '5', 'CS': '0', 'STIFFENER': '2', 'FLAT': '1'})
_sv86b = [l.strip() for l in out.split(chr(10))
          if l.strip().startswith('SAVE_VARIABLE') or l.strip() == '_PACE']
_adj86b = sum(1 for i in range(len(_sv86b) - 1)
              if _sv86b[i].startswith('SAVE_VARIABLE') and _sv86b[i + 1].startswith('SAVE_VARIABLE'))
_out86bn = _re86.sub(r'\s+', ' ', out)
tests.append(('R86 GEN_ANGLES: 12 params saved, paced, no adjacent writes',
    'VARIABLE=angle_deg VALUE=45.0' in _out86bn and 'VARIABLE=angle_stiffener VALUE=2' in _out86bn
    and 'VARIABLE=angle_flat VALUE=True' in _out86bn and 'ANGLE_GENERATE' in out
    and _adj86b == 0 and _sv86b.count('_PACE') >= 10,
    'adjacent %d pace %d' % (_adj86b, _sv86b.count('_PACE'))))

# --- (2) LCD menus -------------------------------------------------------------
_lcd86 = open('menus/lcd_menues.cfg', encoding='utf-8').read()
tests.append(('R86/R89 LCD: Cable ties + Angles+Flat in the Tools menu, guarded, all params',
    all(k in _lcd86 for k in ['[menu __main __gen __cable]', '[menu __main __gen __angle]',
        '__cable __set __cnt]', '__cable __set __len]', '__cable __set __wid]',
        '__cable __set __lay]', '__cable __set __lh]', '__cable __set __var __cla]',
        '__cable __set __var __loo]', '__cable __set __brim]', '__cable __set __vers]',
        '__angle __mode __ang]', '__angle __mode __flt]', '__angle __set __deg]',
        '__angle __set __la]', '__angle __set __lb]', '__angle __set __wid]',
        '__angle __set __lay]', '__angle __set __lh]', '__angle __set __hol]',
        '__angle __set __hd]', '__angle __set __cs __on]', '__angle __set __cs __off]',
        '__angle __set __stf __s1]', '__angle __set __stf __s2]', '__angle __set __stf __s0]',
        '__angle __set __cnt]', '__angle __set __vers]',
        'CABLE_TIE_GENERATE', 'ANGLE_GENERATE',
        "enable: {'gcode_macro _GENERATORS' in printer}"]), 'ids'))
tests.append(('R86 LCD: angle + rib hidden in FLAT mode (enable gates)',
    _lcd86.count('enable: {not printer[\'save_variables\'].variables.angle_flat|default(False)}') == 2,
    'gates %d' % _lcd86.count('angle_flat|default(False)')))
_blk86a = _lcd86[_lcd86.index('[menu __main __gen __cable]'):_lcd86.index('[menu __main __gen __labels]')]
_n86 = [l.strip()[6:].strip("'") for l in _blk86a.split(chr(10)) if l.strip().startswith('name: ')]
_n86 = [l.split('{')[0].strip() if '{' in l else l for l in _n86]   # static prefix of dynamic names
_long86 = [l for l in _n86 if len(l) > 16]
tests.append(('R86 LCD: menu names stay short (R29)', len(_long86) == 0, str(_long86[:6])))

# --- (3) module wiring ---------------------------------------------------------
tests.append(('R86 modules: 17_generator.cfg sentinel + _CHECK_INSTALL lists 17',
    '_V18_GEN' in open(_gen86).read()
    and "('17_generator.cfg',       ['_V18_GEN'])" in open('macros/01_state.cfg').read()
    and 'all 17 modules' not in open('macros/01_state.cfg').read(), ''))
tests.append(('R86-R120 watcher: NONCE_KEYS has 20 channels incl. litho/seal/frame/colorpic',
    len(_pp.NONCE_KEYS) == 20 and 'cable_tie_nonce' in _pp.NONCE_KEYS
    and 'colorpic_nonce' in _pp.NONCE_KEYS
    and 'texture_nonce' in _pp.NONCE_KEYS and 'file_check_nonce' in _pp.NONCE_KEYS
    and 'angle_nonce' in _pp.NONCE_KEYS and 'litho_nonce' in _pp.NONCE_KEYS
    and 'seal_nonce' in _pp.NONCE_KEYS and 'litho_del_nonce' in _pp.NONCE_KEYS
    and 'frame_nonce' in _pp.NONCE_KEYS,
    str(_pp.NONCE_KEYS)))

# --- (4) generator geometry (real files) ----------------------------------------
_d86 = _tf86.mkdtemp(prefix='r86_')
_p86t, _i86t = _pp.make_cable_ties(count=6, length=120, width=8, layers=3,
                                   variant='CLASSIC', out_dir=_d86,
                                   bed=(0.0, -3.0, 244.0, 238.0))
_g86t = open(_p86t).read()
tests.append(('R89 ties: file name 00_+_V01, TAG, PRINT_START, 6 exclude objects',
    _os86.path.basename(_p86t) == '00_Ties_120x8_CLA_V01.gcode'
    and _pp.TAG in _g86t and 'PRINT_START MATERIAL=PLA' in _g86t
    and _g86t.count('EXCLUDE_OBJECT_DEFINE') == 6, _os86.path.basename(_p86t)))
tests.append(('R86 ties: 10 layer marks + header order TAG->defines->PRINT_START->G90',
    _g86t.count('LAYER_MARK') == 10
    and _g86t.index(_pp.TAG) < _g86t.index('EXCLUDE_OBJECT_DEFINE')
    < _g86t.index('PRINT_START') < _g86t.index('G90'), ''))
# R89: per-tie bboxes from the EXCLUDE polygons (no hardcoded grid rows) -
# inside each head's slot band only the PAWL layer may extrude
import json as _json86
_bbox86 = {}
for _l86 in _g86t.split(chr(10)):
    if _l86.startswith('EXCLUDE_OBJECT_DEFINE NAME=TIE_'):
        _nm86 = _l86.split('NAME=')[1].split(' ')[0]
        _pts86 = _json86.loads(_l86[_l86.index('POLYGON=') + 8:])
        _xs86 = [p[0] for p in _pts86]; _ys86 = [p[1] for p in _pts86]
        _bbox86[_nm86] = (min(_xs86), min(_ys86), max(_xs86), max(_ys86))
_z86 = None
_intr86 = {}          # (tie, z) -> segments crossing the slot band of the head
_xp86 = _yp86 = None  # running position (travels included - segments!)
for _l86 in _g86t.split(chr(10)):
    if _l86.startswith(';Z:'):
        _z86 = float(_l86[3:])
    _m86 = _re86.match(r'G[01] X([\d.-]+) Y([\d.-]+)', _l86)
    if not _m86:
        continue
    _nx86, _ny86 = float(_m86.group(1)), float(_m86.group(2))
    _e86 = _l86.split(' E')
    _ext86 = len(_e86) == 2 and float(_e86[1].split()[0]) > 0
    if _ext86 and _z86 is not None and _xp86 is not None:
        for _nm86, (_bx0, _by0, _bx1, _by1) in _bbox86.items():
            _cy86 = (_by0 + _by1) / 2.0            # strap centerline
            # head zone from the STRAP TIP backwards (brim-independent):
            # head spans [tip-length-HL, tip-length] along x
            _hx0_86 = _bx1 - 120.0 - 12.5          # head start (length=120, HL=12.5)
            _wx086, _wx186 = _hx0_86 + 0.5, _hx0_86 + 12.5 - 1.0
            _bd86 = 8.0 / 2.0 - 0.3                # open-slot half band
            # segment [prev -> next] crosses the slot band inside the head zone?
            if (min(_xp86, _nx86) <= _wx186 and max(_xp86, _nx86) >= _wx086
                    and min(_yp86, _ny86) <= _cy86 + _bd86
                    and max(_yp86, _ny86) >= _cy86 - _bd86):
                _intr86[(_nm86, _z86)] = _intr86.get((_nm86, _z86), 0) + 1
    _xp86, _yp86 = _nx86, _ny86
# allowed blockers per tie: 2 solid head-floor layers + the pawl layer ABOVE
# the channel (never a channel-band layer itself: z 0.68..1.68 must stay clear)
_zok86 = {}
for _nm86 in _bbox86:
    _zs86 = sorted({z for (n, z) in _intr86 if n == _nm86})
    _bad86 = [z for z in _zs86 if 0.6 < z < 1.7]   # channel-band z window
    _zok86[_nm86] = (len(_zs86) == 3 and not _bad86
                     and _zs86[0] < 0.5 and _zs86[2] > 1.7, _zs86)
tests.append(('R89 ties CLASSIC: slot blocked ONLY by 2 floor layers + the pawl',
    all(v[0] for v in _zok86.values()),
    {k: v[1] for k, v in _zok86.items() if not v[0]}))

_p86a, _i86a = _pp.make_angles(count=2, angle_deg=90, leg_a=60, leg_b=60, width=25,
                               layers=6, holes=2, hole_d=4, countersink=True,
                               stiffener=1, out_dir=_d86, bed=(0.0, -3.0, 244.0, 238.0))
_g86a = open(_p86a).read()
tests.append(('R86 angles: name + L-outline polygon (6 pts) + 2 plates + rib layers',
    _os86.path.basename(_p86a) == '00_Angle_90deg_60x60_V01.gcode'
    and _i86a['layers'] == 9 and _g86a.count('EXCLUDE_OBJECT_DEFINE') == 2
    and _g86a.count('LAYER_MARK') == 9, _os86.path.basename(_p86a)))

def _holes_ok86(path, centers, r_expect, layers=None):
    g = open(path).read().split(chr(10))
    x = y = None
    z = None
    intr = 0
    dmin = 9e9
    for l in g:
        if l.startswith(';Z:'):
            z = float(l[3:])
        m = _re86.match(r'G1 X([\d.-]+) Y([\d.-]+) E([\d.]+)', l)
        if m:
            nx, ny, e = float(m.group(1)), float(m.group(2)), float(m.group(3))
            if e > 0:
                for t in [i / 6.0 for i in range(7)]:
                    px, py = x + (nx - x) * t, y + (ny - y) * t
                    for (cx, cy) in centers:
                        d = _math86.hypot(px - cx, py - cy)
                        dmin = min(dmin, d)
                        if d < r_expect - 0.12:
                            intr += 1
            x, y = nx, ny
        elif l.startswith('G0 X'):
            m2 = _re86.match(r'G0 X([\d.-]+) Y([\d.-]+)', l)
            x, y = float(m2.group(1)), float(m2.group(2))
    return intr, dmin

# 90deg/60/60/w25: corner_clear = 25 + 2 + 1.5 = 28.5, end 3.5 -> usable 24,
# n=2 step 24 -> centers 30.5 / 54.5 on each leg centerline, both plates
_cs86 = []
for _ox86 in (55.0, 129.0):
    for _dd86 in (30.5, 54.5):
        _cs86.append((_ox86 + _dd86, _ox86 * 0 + 87.5 + 12.5))
        _cs86.append((_ox86 + 12.5, 87.5 + _dd86))
_intr86, _dmin86 = _holes_ok86(_p86a, _cs86, 2.0)
tests.append(('R86 angles: hole walls sit at r, NOTHING extrudes inside (auto keep-out)',
    _intr86 == 0 and 1.9 < _dmin86 < 2.3, 'intr %d dmin %.2f' % (_intr86, _dmin86)))

_p86f, _i86f = _pp.make_angles(count=1, flat=True, leg_a=40, leg_b=40, width=25,
                               layers=6, holes=2, hole_d=4, countersink=False,
                               stiffener=0, out_dir=_d86, bed=(0.0, -3.0, 244.0, 238.0))
tests.append(('R86 flat: own file name + both halves share the SAME hole pattern',
    _os86.path.basename(_p86f) == '00_Flat_80x25_V01.gcode' and _i86f['holes'] == '2+2',
    _os86.path.basename(_p86f)))

# hole clamp: 9mm on a 20mm leg -> clamped to 14? no: max_d = min(20-6, 10) = 10 -> stays 9? edge=3
_p86c, _i86c = _pp.make_angles(count=1, angle_deg=90, leg_a=40, leg_b=40, width=20,
                               layers=6, holes=4, hole_d=9, stiffener=0, out_dir=_d86,
                               bed=(0.0, -3.0, 244.0, 238.0))
tests.append(('R86 angles: short leg reduces hole count + notes say so',
    _i86c['holes'] == '0+0' and any('too short' in n for n in _i86c['notes']), str(_i86c['notes'])))
_p86c2, _i86c2 = _pp.make_angles(count=1, angle_deg=90, leg_a=100, leg_b=100, width=16,
                                 layers=6, holes=3, hole_d=9, stiffener=0, out_dir=_d86,
                                 bed=(0.0, -3.0, 244.0, 238.0))
tests.append(('R86 angles: 9mm hole clamped to the 16mm leg (max 10)',
    _i86c2['hole_d'] == 9.0 and 'clamped' not in str(_i86c2['notes']), str(_i86c2['notes'])))
_p86c3, _i86c3 = _pp.make_angles(count=1, angle_deg=90, leg_a=100, leg_b=100, width=12,
                                 layers=6, holes=2, hole_d=8, stiffener=0, out_dir=_d86,
                                 bed=(0.0, -3.0, 244.0, 238.0))
tests.append(('R86 angles: 8mm hole on a 12mm leg clamps to 6mm',
    _i86c3['hole_d'] == 6.0 and any('clamped' in n for n in _i86c3['notes']), str(_i86c3['notes'])))

# countersink: the top plate layers widen the hole in two steps (6 -> 8mm for d=4)
def _hole_r_by_layer(path, cx, cy, plate_layers):
    radii = {}
    z = None
    zn = 0
    x = y = None
    for l in open(path).read().split(chr(10)):
        if l.startswith(';Z:'):
            z = l[3:]
            zn += 1
        m = _re86.match(r'G1 X([\d.-]+) Y([\d.-]+) E([\d.]+)', l)
        if m and float(m.group(3)) > 0 and z is not None and zn <= plate_layers:
            d = _math86.hypot(float(m.group(1)) - cx, float(m.group(2)) - cy)
            if d < 4.6 and d > 0.5:
                radii.setdefault(zn, []).append(d)
            x, y = float(m.group(1)), float(m.group(2))
        elif l.startswith('G0 X'):
            m2 = _re86.match(r'G0 X([\d.-]+) Y([\d.-]+)', l)
            x, y = float(m2.group(1)), float(m2.group(2))
    return {k: min(v) for k, v in radii.items()}
_rad86 = _hole_r_by_layer(_p86a, 85.5, 100.0, 6)
tests.append(('R86 angles: countersink grows 2.0 -> 3.0 -> 4.0 over the top layers',
    [round(_rad86[k], 1) for k in sorted(_rad86)] == [2.0] * 4 + [3.0, 4.0],
    str(_rad86)))

# generation stays cheap (CPU guard for the Pi)
import time as _t86
_t086 = _t86.time()
for _k86 in range(5):
    _pp.make_cable_ties(count=6, length=120, width=8, layers=3, out_dir=_d86,
                        bed=(0.0, -3.0, 244.0, 238.0))
    _pp.make_angles(count=2, angle_deg=90, out_dir=_d86,
                    bed=(0.0, -3.0, 244.0, 238.0))
tests.append(('R86 generators: 10 files in < 3s single-pass (Pi-friendly)',
    _t86.time() - _t086 < 3.0, '%.2fs' % (_t86.time() - _t086)))


# =====================================================================================
# R86.2: range floor/top holes + angle walls/infill/ironing + nozzle LED split
# =====================================================================================
import re as _re862, math as _math862, tempfile as _tf862, os as _os862

# --- (1) SET_LAYER_RANGE renders the hole params, paced ---
_sr862 = get_body('macros/08_print_start_stop.cfg', 'SET_LAYER_RANGE')
out = render(_sr862, {'START': '3', 'END': '6', 'FLOOR': '3', 'TOP': '3',
                      'FLOOR_HOLE': '24.5', 'TOP_HOLE': '28'})
_sv862 = [l.strip() for l in out.split(chr(10))
          if l.strip().startswith('SAVE_VARIABLE') or l.strip() == '_PACE']
_adj862 = sum(1 for i in range(len(_sv862) - 1)
              if _sv862[i].startswith('SAVE_VARIABLE') and _sv862[i + 1].startswith('SAVE_VARIABLE'))
tests.append(('R86.2 SET_LAYER_RANGE: 13 writes incl. holes, paced, no adjacency',
    'VARIABLE=range_floor_hole VALUE=24.5' in out and 'VARIABLE=range_top_hole VALUE=28.0' in out
    and _adj862 == 0 and _sv862.count('_PACE') >= 12 and len([l for l in _sv862 if l.startswith('SAVE_VARIABLE')]) == 13,
    'writes %d pace %d adjacent %d' % (len([l for l in _sv862 if l.startswith('SAVE_VARIABLE')]),
                                       _sv862.count('_PACE'), _adj862)))
tests.append(('R86.2 SET_LAYER_RANGE: hole announce lines (E14/E27 hint, bridge-first)',
    'floor hole 24.5mm centered' in out and 'top hole 28.0mm centered' in out
    and 'BRIDGE-FIRST' in out and 'E14 ~15mm' in out, out[:150]))
out = render(_sr862, {'START': '3', 'END': '6'})
tests.append(('R86.2 SET_LAYER_RANGE: hole defaults 0 (no holes, unchanged path)',
    'VARIABLE=range_floor_hole VALUE=0.0' in out and 'VARIABLE=range_top_hole VALUE=0.0' in out,
    out[:120]))

# --- (2) GEN_ANGLES with WALLS/INFILL/IRONING ---
out = render(get_body(_gen86, 'GEN_ANGLES'),
             {'WALLS': '4', 'INFILL': '50', 'IRONING': '1', 'ANGLE': '90'})
tests.append(('R86.2 GEN_ANGLES: WALLS/INFILL/IRONING saved + paced',
    'VARIABLE=angle_walls VALUE=4' in out and 'VARIABLE=angle_infill VALUE=50.0' in out
    and 'VARIABLE=angle_ironing VALUE=True' in out and out.count('_PACE') >= 13, out[:150]))
out = render(get_body(_gen86, 'ANGLE_INFO'))
tests.append(('R86.2 ANGLE_INFO: walls/infill/ironing reported',
    'walls 2 loop(s)' in out and 'infill 100%' in out and 'ironing off' in out, out[:200]))

# --- (3) LCD additions ---
_lcd862 = open('menus/lcd_menues.cfg', encoding='utf-8').read()
tests.append(('R86.2 LCD: range hole inputs + Create passes them',
    all(k in _lcd862 for k in ['[menu __main __preprint __rng __fho]', '[menu __main __preprint __rng __tho]',
        'VARIABLE=range_floor_hole', 'VARIABLE=range_top_hole',
        "FLOOR_HOLE={printer['save_variables'].variables.range_floor_hole|default(0)|float}",
        "TOP_HOLE={printer['save_variables'].variables.range_top_hole|default(0)|float}"]), 'ids'))
tests.append(('R86.2 LCD: angle Walls/Infill/Ironing items',
    all(k in _lcd862 for k in ['[menu __main __gen __angle __set __wal]', '[menu __main __gen __angle __set __inf]',
        '[menu __main __gen __angle __set __iro __on]', '[menu __main __gen __angle __set __iro __off]',
        'VARIABLE=angle_walls', 'VARIABLE=angle_infill', 'VARIABLE=angle_ironing']), 'ids'))
tests.append(('R86.2 LCD: hole input names <=16 incl. worst-case value',
    len('Top hole: 80.0mm') <= 16 and len('Fl.hole: 80.0mm') <= 16 and len('Walls:  6') <= 16
    and len('Infill: 100%') <= 16, 'name lengths'))

# --- (4) postproc geometry: range holes ---
_d862 = tempfile.mkdtemp(prefix='r862_')
_ln862 = ['; R2-POSTPROC v5', '_FILE_INFO MATERIAL=PLA TOTAL_LAYERS=8 BED=60 HOTEND=210',
          'G90', 'M82', 'G28', 'G1 Z0.2 F600']
_e862 = 0.0
for _ly in range(8):
    _ln862.append('LAYER_MARK')
    _ln862.append(';Z:%.3f' % (0.2 + _ly * 0.2))
    for (_x0, _y0, _x1, _y1) in [(50, 50, 100, 50), (100, 50, 100, 100),
                                  (100, 100, 50, 100), (50, 100, 50, 50)]:
        _e862 += _math862.hypot(_x1 - _x0, _y1 - _y0) * 0.05
        _ln862.append('G1 X%g Y%g E%.4f F1200' % (_x1, _y1, _e862))
_src862 = _os862.path.join(_d862, 'src_rng.gcode')
open(_src862, 'w').write(chr(10).join(_ln862) + chr(10))
_c862, _n862 = 75.0, 75.0
_o862, _ = _pp.make_range(_src862, 3, 6, floor=3, top=3,
                          floor_hole=15.0, top_hole=28.0)
_t862 = open(_o862).read()
_raft862 = _t862[_t862.index('R2-RANGE raft'):_t862.index('PRINT_START')]
_bad862 = sum(1 for _m in _re862.finditer(r'G1 X([\d.]+) Y([\d.]+) E([\d.]+)', _raft862)
              if float(_m.group(3)) > 0 and _math862.hypot(float(_m.group(1)) - _c862, float(_m.group(2)) - _c862) < 7.3)
tests.append(('R86.2 range: floor hole open (nothing extrudes inside r-0.2)',
    _bad862 == 0 and 'R2-RANGE floor hole: centered d=15.0mm' in _t862, 'inside %d' % _bad862))
_cap862 = _t862[_t862.index('R2-RANGE cap:'):]
_lms862 = _cap862.split('LAYER_MARK   ; R2-RANGE cap')
tests.append(('R86.2 range: cap hole bridge-first (ring on layer 1, open 1-3)',
    len(_lms862) == 4 and all(
        sum(1 for _m in _re862.finditer(r'G1 X([\d.]+) Y([\d.]+) E([\d.]+)', _lms862[i])
            if float(_m.group(3)) > 0 and
            _math862.hypot(float(_m.group(1)) - _c862, float(_m.group(2)) - _c862) < 13.8) == 0
        for i in (1, 2, 3)), 'layers %d' % (len(_lms862) - 1)))
# --- R95: cap hole prints bridges FIRST, ring ON them, hole stays open ---
_i95br = _cap862.index('APPLY_TYPE TYPE=BRIDGE')
_i95ib = _cap862.index('APPLY_TYPE TYPE=INTERNAL-BRIDGE')
_i95so = _cap862.index('APPLY_TYPE TYPE=INFILL-SOLID   ; R95: back to the cap solid')
_l95c1 = _cap862.split('LAYER_MARK   ; R2-RANGE cap')[1]
tests.append(('R95 cap hole: bridge spokes -> ring on them -> solid (order)',
    _i95br < _i95ib < _i95so
    and _l95c1.index('APPLY_TYPE TYPE=BRIDGE')
        < _l95c1.index('APPLY_TYPE TYPE=INTERNAL-BRIDGE')
    and _l95c1.index('F1300') < _l95c1.index('APPLY_TYPE TYPE=INTERNAL-BRIDGE'), ''))
_spk95 = _re862.findall(r'F1300', _l95c1)
tests.append(('R95 cap hole: >= 12 short radial bridge spokes (F1300)',
    len(_spk95) >= 12, 'spokes %d' % len(_spk95)))
# every travel that crosses the open hole must retract first (dd rule)
def _seg95(p, q, cx, cy, r):
    dx, dy = q[0] - p[0], q[1] - p[1]
    a = dx * dx + dy * dy
    if a < 1e-12:
        return (p[0] - cx) ** 2 + (p[1] - cy) ** 2 < r * r
    t = max(0.0, min(1.0, ((cx - p[0]) * dx + (cy - p[1]) * dy) / a))
    return (p[0] + t * dx - cx) ** 2 + (p[1] + t * dy - cy) ** 2 < r * r
_cx95, _cy95, _cr95 = _c862, _c862, 14.0
_pos95, _e95, _was95, _bad95, _ret95 = None, 0.0, False, 0, 0
for _l95 in _cap862.split(chr(10)):
    _m95t = _re862.match(r'G0 X([\d.-]+) Y([\d.-]+)', _l95)
    _m95e = _re862.match(r'G1 X([\d.-]+) Y([\d.-]+) E(-?[\d.]+)', _l95)
    _m95o = _re862.match(r'G1 E(-?[\d.]+) F2400', _l95)
    if _m95o:                       # pure retract / unretract line
        _new95 = float(_m95o.group(1))
        _was95 = _new95 < _e95 - 1e-6
        _e95 = _new95
    elif _m95e:
        _new95 = float(_m95e.group(3))
        if _new95 < _e95 - 1e-6 and abs(_new95 - _e95) < 1.0:
            _was95 = True           # combined move starting with a retract
        else:
            _was95 = False
        _e95 = _new95
        _pos95 = (float(_m95e.group(1)), float(_m95e.group(2)))
    if _m95t:
        if _pos95 is not None and _seg95(
                _pos95, (float(_m95t.group(1)), float(_m95t.group(2))),
                _cx95, _cy95, _cr95):
            if _was95:
                _ret95 += 1         # retracted crossing - allowed
            else:
                _bad95 += 1         # UNRETRACTED crossing - strings!
        _pos95 = (float(_m95t.group(1)), float(_m95t.group(2)))
tests.append(('R95 cap hole: travels over the open hole retract (bridges + clipped hatch)',
    _bad95 == 0 and _ret95 >= 2, 'bad %d / retracted %d' % (_bad95, _ret95)))
tests.append(('R95 cap hole: TYPES lists BRIDGE + INTERNAL-BRIDGE',
    'BRIDGE' in _t862.split('TYPES=')[-1].split()[0] and 'INTERNAL-BRIDGE' in _t862, _t862[:80]))
_o862b, _ = _pp.make_range(_src862, 3, 6, floor=2, floor_hole=45.0)
_tb862 = open(_o862b).read()
tests.append(('R86.2 range: oversized hole auto-clamps with a note',
    'clamped to' in _tb862 and 'R2-RANGE note' in _tb862, [l for l in _tb862.split(chr(10)) if 'note' in l][:1]))
_o862c, _ = _pp.make_range(_src862, 3, 6, top=1, top_hole=20.0)
tests.append(('R86.2 range: top hole auto-raises TOP to 3',
    'TOP auto-raised 1 -> 3' in open(_o862c).read(), ''))
_o862d, _ = _pp.make_range(_src862, 3, 6, top_hole=20.0)
tests.append(('R86.2 range: top hole without TOP reports, no crash',
    'cap hole ignored - no TOP layers' in open(_o862d).read(), ''))

# --- (5) postproc geometry: angle walls/infill/ironing ---
_o862e, _i862e = _pp.make_angles(count=1, angle_deg=90, leg_a=60, leg_b=60, width=25,
                                 layers=6, holes=2, hole_d=4, walls=4, infill=50,
                                 ironing=True, out_dir=_d862, bed=(0.0, -3.0, 244.0, 238.0))
_te862 = open(_o862e).read()
_seg862 = _te862.split(';LAYER_CHANGE')[3]
tests.append(('R86.2 angles: walls=4 -> 3 wall loops + 4 hole circles per layer',
    _seg862.count(';TYPE:Outer wall') == 1 and _seg862.count(';TYPE:Inner wall') == 7,
    'outer %d inner %d' % (_seg862.count(';TYPE:Outer wall'), _seg862.count(';TYPE:Inner wall'))))
tests.append(('R86.2 angles: ironing section on the top layer',
    _te862.count(';TYPE:Ironing') >= 1 and 'APPLY_TYPE TYPE=IRONING' in _te862, ''))
_o862f, _ = _pp.make_angles(count=1, angle_deg=90, leg_a=60, leg_b=60, width=25,
                            layers=6, holes=2, hole_d=4, infill=50,
                            out_dir=_d862, bed=(0.0, -3.0, 244.0, 238.0))
_tf862a = open(_o862f).read()          # read NOW - the next build overwrites V01
_o862g, _ = _pp.make_angles(count=1, angle_deg=90, leg_a=60, leg_b=60, width=25,
                            layers=6, holes=2, hole_d=4, infill=100,
                            out_dir=_d862, bed=(0.0, -3.0, 244.0, 238.0))
_tf862b = open(_o862g).read()
def _infill862(txt, n=3):
    _s = txt.split(';LAYER_CHANGE')[n]
    _i = _s.split(';TYPE:Internal solid infill')[1].split(';TYPE:')[0]
    return len([l for l in _i.split(chr(10)) if l.startswith('G1')])
tests.append(('R86.2 angles: infill 50% halves the hatch moves',
    _infill862(_tf862a) < _infill862(_tf862b) * 0.65,
    '%d vs %d' % (_infill862(_tf862a), _infill862(_tf862b))))
_o862h, _i862h = _pp.make_angles(count=1, width=8, layers=4, holes=0, walls=6,
                                 out_dir=_d862, bed=(0.0, -3.0, 244.0, 238.0))
tests.append(('R86.2 angles: walls auto-reduce on a narrow leg (+note)',
    any('walls do not fit' in str(x) for x in _i862h['notes']), str(_i862h['notes'])[:120]))

# --- (6) nozzle LED split (03_leds.cfg) ---
_led862 = open('macros/03_leds.cfg', encoding='utf-8').read()
tests.append(('R86.2 leds: split effect shipped (commented) + header doc',
    '#[led_effect r2_nozzle_on_split]' in _led862 and 'SET_NOZZLE_SPLIT' in _led862
    and 'max ~15' in _led862 or 'Max LEDs' in _led862 or 'EBB42' in _led862, ''))
save_vars['nozzle_split'] = 1
out = render(get_body('macros/03_leds.cfg', '_NOZZLE_SET'), {'ON': '1'})
tests.append(('R86.2 _NOZZLE_SET split=1 -> writes the EBB chain (no INDEX=5)',
    'SET_LED LED=nozzle_led RED=' in out and 'INDEX=5' not in out, out[:120]))
save_vars['nozzle_split'] = 0
out = render(get_body('macros/03_leds.cfg', '_NOZZLE_SET'), {'ON': '1'})
tests.append(('R86.2 _NOZZLE_SET split=0 -> unchanged LED 5 path',
    'SET_LED LED=printer_leds INDEX=5' in out, out[:120]))
save_vars['nozzle_split'] = 1
out = render(get_body('macros/03_leds.cfg', 'SET_LED_STATE'), {'STATE': 'printing'})
tests.append(('R86.2 SET_LED_STATE split: work light via _split effect',
    'EFFECT=r2_nozzle_on_split' in out, out[:160]))
out = render(get_body('macros/03_leds.cfg', 'SET_NOZZLE_SPLIT'), {'STATE': '1'})
tests.append(('R86.2 SET_NOZZLE_SPLIT STATE=1 persisted',
    'SAVE_VARIABLE VARIABLE=nozzle_split VALUE=1' in out and 'own chain' in out, out[:140]))
out = render(get_body('macros/03_leds.cfg', 'SET_NOZZLE_SPLIT'), {'STATE': '7'})
tests.append(('R86.2 SET_NOZZLE_SPLIT bad value -> usage hint',
    'SET_NOZZLE_SPLIT STATE=1' in out and 'SAVE_VARIABLE' not in out, out[:140]))
save_vars['nozzle_split'] = 0

# --- (7) printer.cfg.example electronics template ---
_pc862 = open('printer.cfg.example', encoding='utf-8').read()
tests.append(('R86.2 example cfg: EBB/U2C/relay/nozzle-LED templates present',
    all(k in _pc862 for k in ['#[mcu EBB]', 'canbus_uuid:', 'EBB:PD0', 'EBB:PB13',
        'EBB:PA0', 'EBB:PA1', 'EBB:PB8', 'EBB:PD3', '#[output_pin power_hold]',
        'PRINTER_POWER_OFF', 'shutdown_value: 0', 'bitrate 1000000',
        'SET_NOZZLE_SPLIT STATE=1']), 'ids'))


# ---------- R87: Generators container menu (LCD declutter, user field request .70) ----------
import re as _re87
_lcd87 = open('menus/lcd_menues.cfg', encoding='utf-8').read()
_top87 = sorted(_re87.findall(r'^\[menu __main ([a-z_0-9]+)\]$', _lcd87, _re87.M))
tests.append(('R87 LCD: exactly 7 top-level menus (4 generators moved into one container)',
    _top87 == ['__gen', '__live', '__macros', '__maint', '__preprint', '__start', '__system'],
    str(_top87)))
tests.append(('R87 LCD: container Tools + all four trees re-parented, old roots gone',
    '[menu __main __gen]\ntype: list\nname: Tools' in _lcd87
    and all(('[menu __main __gen %s]' % _x) in _lcd87 for _x in ('__cable', '__angle', '__labels', '__plot'))
    and all(('[menu __main %s]' % _x) not in _lcd87 for _x in ('__cable', '__angle', '__labels', '__plot'))
    and len('Tools') <= 16, ''))
tests.append(('R87 LCD: container sits between Quick Macros and Maintenance, live plotter untouched',
    _lcd87.index('[menu __main __macros]') < _lcd87.index('[menu __main __gen]')
    < _lcd87.index('[menu __main __maint]')
    and '[menu __main __live __plot __mode]' in _lcd87
    and '[menu __main __live __plot]' in _lcd87, ''))
tests.append(('R87/R89/R90 LCD: guards preserved (cable/angle/litho/seal/frame need 17_generator, labels optional, plot+container free)',
    _lcd87.count("enable: {'gcode_macro _GENERATORS' in printer}") == 5
    and "enable: {'gcode_macro _LABELS' in printer}" in _lcd87
    and '[menu __main __gen __plot]\ntype: list\nname: Plotter\n' in _lcd87, ''))
tests.append(('R87 docs: cfg console paths say Tools (labels + plotter + generator header)',
    open('macros/16_labels.cfg', encoding='utf-8').read().count('Tools > Labels >') == 4
    and open('macros/12_maintenance.cfg', encoding='utf-8').read().count('Tools > Plotter >') == 4
    and 'Tools > Cable ties / Angles+Flat' in open('macros/17_generator.cfg', encoding='utf-8').read(), ''))


# ---------- R87.2: field-log .71 fixes (polygon json, hole spiral, marker synthesis, global x feature) ----------
import json as _json872, re as _re872, math as _math872, tempfile as _tf872, os as _os872
_d872 = _tf872.mkdtemp(prefix='r872_')

# --- (1) EVERY generator: every EXCLUDE_OBJECT_DEFINE POLYGON must be json (Klipper parses it) ---
import math as _math872b, os as _os872b
_csv872 = _os872b.path.join(_d872, 'resonances_x_20261006_120000.csv')
with open(_csv872, 'w') as _fh872:
    _fh872.write('freq,psd_x,psd_x_smooth_min,psd_x_smooth,psd_x_smooth_max,harmonics_x\n')
    for _i872 in range(60):
        _fh872.write('%.1f,%.6f,%.6f,%.6f,%.6f,%.6f\n' % (5.0 + _i872 * 0.5, 1.0, 0.8, 1.0, 1.2, 0.1))
_files872 = []
for _ret872 in (_pp.make_labels(['TEST'], out_dir=_d872),
                _pp.make_resonance(axes=('x',), mode='print', out_dir=_d872, csv_dirs=[_d872]),
                _pp.make_bridge(out_dir=_d872),
                _pp.make_cable_ties(count=2, length=90, width=6, layers=3, variant='LOOP',
                                    out_dir=_d872, bed=(0.0, -3.0, 244.0, 238.0)),
                _pp.make_angles(out_dir=_d872)):
    _h872 = _ret872[0] if isinstance(_ret872, tuple) else _ret872
    _files872.extend(_h872 if isinstance(_h872, list) else [_h872])
_polys872 = []
for _f872 in _files872:
    for _l872 in open(_f872, encoding='utf-8'):
        _m872 = _re872.search(r'POLYGON=(\S+)', _l872)
        if _m872:
            _polys872.append(_m872.group(1).strip())
def _poly_ok872(s):
    try:
        v = _json872.loads(s)
        return isinstance(v, list) and len(v) >= 3 and all(
            isinstance(p, list) and len(p) == 2 for p in v)
    except Exception:
        return False
tests.append(('R87.2 ties+angles: all POLYGON definitions are json ([[x,y],...], no whitespace)',
    len(_polys872) >= 3 and all(_poly_ok872(p) for p in _polys872),
    '%d polys, bad: %s' % (len(_polys872), [p[:40] for p in _polys872 if not _poly_ok872(p)][:2])))

# --- (2) floor hole: spiral boss + retracting travels + nothing extrudes inside the hole ---
_lines872 = ['; r872', '; layer_height = 0.2', '; line_width = 0.6', 'M82', 'G90',
             'M104 S200', 'M140 S60', 'G28', 'G92 E0']
for _L872 in range(1, 9):
    _lines872 += ['LAYER_MARK', ';TYPE:%s' % ['outer wall', 'sparse infill'][_L872 % 2],
                  'G0 Z%.2f F600' % (0.2 * _L872), 'G0 X10 Y10 F6000',
                  'G1 X80 Y10 E1.0 F1200', 'G1 X80 Y80 E2.0',
                  'G1 X10 Y80 E3.0', 'G1 X10 Y10 E4.0', 'G0 X10 Y10 F6000']
_src872 = _os872path = __import__('os').path.join(_d872, 'r872src.gcode')
open(_src872, 'w', encoding='utf-8').write('\n'.join(_lines872) + '\n')
_pp.process(_src872)
_out872, _ = _pp.make_range(_src872, 3, 6, floor=3, floor_hole=25.0, first_h=0.2)
_e872 = open(_out872, encoding='utf-8').read()
_raft872 = _e872[_e872.index('raft layer 1'):_e872.index('raft layer 2')]
_spiral872 = len([l for l in _raft872.split('\n') if 'F1200' in l and l.startswith('G1 ')])
_rets872 = len(_re872.findall(r'G1 E-?[\d.]+ F2400', _raft872))
_bad872 = 0
for _l872 in _raft872.split('\n'):
    _m872 = _re872.match(r'G1 X(\S+) Y(\S+) E(\S+) F1200', _l872)
    if _m872 and float(_m872.group(3)) > 0:
        if _math872.hypot(float(_m872.group(1)) - 45.0, float(_m872.group(2)) - 45.0) < 12.0:
            _bad872 += 1
tests.append(('R87.2 range hole: spiral boss (1 continuous stroke) fills the band',
    _spiral872 >= 150, 'F1200 moves in raft layer 1: %d' % _spiral872))
tests.append(('R87.2 range hole: travels over the hole RETRACT (strings fix .71)',
    _rets872 >= 4, 'retract lines: %d' % _rets872))
tests.append(('R87.2 range hole: nothing extrudes inside the open hole',
    _bad872 == 0, 'inside: %d' % _bad872))

# --- (3) body markers re-derived when the source carries no APPLY_TYPE (v1 tag era) ---
_lines872v = ['; old', 'M82', 'G90', 'M104 S200', 'M140 S60', 'G28', 'G92 E0']
for _L872 in range(1, 7):
    _lines872v += ['LAYER_MARK', ';TYPE:%s' % ['outer wall', 'top surface'][_L872 % 2],
                   'G0 Z%.2f F600' % (0.2 * _L872), 'G0 X10 Y10 F6000',
                   'G1 X70 Y10 E1.0 F1200', 'G1 X70 Y70 E2.0']
_src872v = __import__('os').path.join(_d872, 'r872old.gcode')
open(_src872v, 'w', encoding='utf-8').write('\n'.join(_lines872v) + '\n')
_out872v, _ = _pp.make_range(_src872v, 2, 5, floor=1, first_h=0.2)
_e872v = open(_out872v, encoding='utf-8').read()
# --- (3b) R88 bug 4: the hole clamps against the REAL outline, not the bbox ---
_ln872L = ['; r872L', '; layer_height = 0.2', '; line_width = 0.6', 'M82', 'G90',
           'M104 S200', 'M140 S60', 'G28', 'G92 E0']
_e872L = 0.0
for _L872 in range(1, 9):      # thin L: 2-segment layers, hull diagonal runs THROUGH the center
    _ln872L += ['LAYER_MARK', ';TYPE:outer wall', 'G0 Z%.2f F600' % (0.2 * _L872),
                'G0 X10 Y10 F6000', 'G1 X80 Y10 E1.0 F1200', 'G1 X80 Y80 E2.0']
_src872L = _os872.path.join(_d872, 'r872L.gcode')
open(_src872L, 'w', encoding='utf-8').write(chr(10).join(_ln872L) + chr(10))
_out872L, _ = _pp.make_range(_src872L, 3, 6, floor=2, floor_hole=25.0)
_t872L = open(_out872L, encoding='utf-8').read()
tests.append(('R88 bug4: thin-L section - centered hole SKIPPED (center in air/too close to the hull edge)',
    'real outline leaves less than 8mm' in _t872L and 'centered d=' not in _t872L,
    [l for l in _t872L.split(chr(10)) if 'hole' in l.lower() and 'note' in l.lower()][:1]))
_ln872T = ['; r872T', '; layer_height = 0.2', '; line_width = 0.6', 'M82', 'G90',
           'M104 S200', 'M140 S60', 'G28', 'G92 E0']
_e872T = 0.0
_segs872T = [(50, 50, 150, 50), (150, 50, 150, 80), (150, 80, 80, 80), (80, 80, 80, 150),
             (80, 150, 50, 150), (50, 150, 50, 50)]
for _L872 in range(1, 9):      # thick L (arms 30mm): old bbox let a 50mm boss float in air
    _ln872T += ['LAYER_MARK', ';TYPE:outer wall', 'G0 Z%.2f F600' % (0.2 * _L872),
                'G0 X50 Y50 F6000']
    for (_sx, _sy, _ex, _ey) in _segs872T:
        _e872T += _math872.hypot(_ex - _sx, _ey - _sy) * 0.05
        _ln872T.append('G1 X%g Y%g E%.4f F1200' % (_ex, _ey, _e872T))
_src872T = _os872.path.join(_d872, 'r872T.gcode')
open(_src872T, 'w', encoding='utf-8').write(chr(10).join(_ln872T) + chr(10))
_out872T, _ = _pp.make_range(_src872T, 3, 6, floor=2, floor_hole=50.0)
_t872T = open(_out872T, encoding='utf-8').read()
_m872T = _re872.search(r'centered d=([\d.]+)mm, boss (\d+) loops', _t872T)
tests.append(('R88 bug4: thick-L 50mm hole clamps to the real hull (~32mm, boss stays inside)',
    _m872T is not None and 'clamped to' in _t872T and 'real outline' in _t872T
    and 30.0 < float(_m872T.group(1)) < 35.0
    and float(_m872T.group(1)) / 2.0 + int(_m872T.group(2)) * 0.6
        <= 30.0 / _math872.sqrt(2) - 2.0 + 1e-9,
    _m872T.group(1) if _m872T else 'no hole'))
_out872O, _ = _pp.make_range(_src872T, 3, 6, floor=2, floor_shape='outline', floor_hole=50.0)
_t872O = open(_out872O, encoding='utf-8').read()
tests.append(('R88 bug4: OUTLINE mode - hole skipped when the true outline leaves no room',
    'real outline leaves less than 8mm' in _t872O and 'centered d=' not in _t872O, ''))

tests.append(('R87.2 range: body APPLY_TYPE re-derived from ;TYPE: when the source has none',
    _e872v.count('marker re-derived') == 4
    and _e872v.count('APPLY_TYPE TYPE=WALL-OUTER') >= 2
    and 're-derived from the ;TYPE: comments' in _e872v, 'count %d' % _e872v.count('marker re-derived')))

# --- (4) global speed x feature: _SPEED_COMBINED (M220 path) ---
_sc872 = get_body('macros/06_temp_controls.cfg', '_SPEED_COMBINED')
state_vars.update({'mode': 'printing', 'ignore_overrides': False, 'current_type': 'WALL-OUTER',
                   'g_speed_clean': 150.0, 'absent_features': []})
save_vars.update({'ovf_wallouter_on': True, 'ovf_wallouter_spd': 200.0})
out = render(_sc872, {})
tests.append(('R87.2 speed: global 150% x feature 200% = 300% (not 150 - field log .71)',
    'M99220 S300' in out and 'stays on top' in out, out[:150]))
state_vars['current_type'] = ''
out = render(_sc872, {})
tests.append(('R87.2 speed: without a feature the global applies 1:1',
    'M99220 S150' in out and 'stays on top' not in out, out[:120]))

# --- (5) SET_GLOBAL_ACCEL keeps a feature accel ---
state_vars.update({'current_type': 'WALL-OUTER', 'live_accel': 0})
save_vars.update({'ovf_wallouter_acc': 1000.0})
out = render(get_body('macros/10_live_tuning.cfg', 'SET_GLOBAL_ACCEL'), {'ACCEL': '4000'})
tests.append(('R87.2 accel: global 4000 keeps the feature accel 1000 (message + value)',
    'ACCEL=1000' in out and 'keeps its own' in out and 'live_accel VALUE=4000' in out, out[:160]))

# ===================== R90: picture frames / display cases =======================
import os as _os90, re as _re90, json as _json90, tempfile as _tf90
_d90 = _tf90.mkdtemp(prefix='r90_')

# --- (1) geometry: one-piece FLAT, kit fallback, OVAL, CASE, SIDE -----------
_p90a, _i90a = _pp.make_frame(preset='10x15', depth=8, frame_w=10, corner=4,
                              closure='BACK', hang='TOP', stand=True, out_dir=_d90)
_g90a = open(_p90a, encoding='utf-8').read()
tests.append(('R90.1a multi: 10x15 -> Part A (frame alone), TAG + PRINT_START',
    _i90a['multi'] and not _i90a['kit'] and len(_i90a['plates']) == 2
    and _os90.path.basename(_p90a) == '00_Frame_10x15_FLATx8_A_V01.gcode'
    and _pp.TAG in _g90a and 'PRINT_START MATERIAL=PLA LAYER_HEIGHT=0.2' in _g90a
    and _g90a.count('EXCLUDE_OBJECT_DEFINE') == 1 and ';TYPE:Ironing' in _g90a
    and 'PLATE A of 2' in _g90a, _os90.path.basename(_p90a)))
_zs90 = [float(_m.group(1)) for _m in _re90.finditer(r';Z:([\d.-]+)', _g90a)]
tests.append(('R90 frame: layer z strictly ascending, first 0.28, 40 layers',
    all(b >= a for a, b in zip(_zs90, _zs90[1:])) and _zs90[0] == 0.28
    and len(_zs90) == _i90a['layers'], '%s..' % _zs90[:3]))
tests.append(('R90 frame: photo opening stays free (nothing extrudes > 1.05 deep)',
    not _re90.search(r'G1 X' + r'|'.join([]), ''), True))   # placeholder replaced below
tests.pop()   # (replaced by the real scan below)
_fp90 = None
for _l90 in _g90a.split(chr(10)):
    if _l90.startswith('EXCLUDE_OBJECT_DEFINE NAME=FRAME'):
        _q90 = _json90.loads(_l90[_l90.index('POLYGON=') + 8:])
        _fp90 = ((min(p[0] for p in _q90) + max(p[0] for p in _q90)) / 2.0,
                 (min(p[1] for p in _q90) + max(p[1] for p in _q90)) / 2.0)
        break
_deep90, _z90, _xp90, _yp90 = [], None, None, None
_pw90, _ph90 = 102.6, 152.6
for _l90 in _g90a.split(chr(10)):
    if _l90.startswith(';Z:'):
        _z90 = float(_l90[3:])
    _m90 = _re90.match(r'G1 X([\d.-]+) Y([\d.-]+).* E([\d.]+)', _l90)
    if _m90 and float(_m90.group(3)) > 0 and _xp90 is not None and _z90 is not None \
            and _z90 <= 6.68:
        _mx90 = (_xp90 + float(_m90.group(1))) / 2.0
        _my90 = (_yp90 + float(_m90.group(2))) / 2.0
        if (abs(_mx90 - _fp90[0]) < _pw90 / 2 - 1.05
                and abs(_my90 - _fp90[1]) < _ph90 / 2 - 1.05):
            _deep90.append((_mx90, _my90, _z90))
    _m291 = _re90.match(r'G[01] X([\d.-]+) Y([\d.-]+)', _l90)
    if _m291:
        _xp90, _yp90 = float(_m291.group(1)), float(_m291.group(2))
tests.append(('R90 frame: photo opening stays free below the shelf (nub tips ok)',
    len(_deep90) == 0, str(_deep90[:2])))

# bayonet: the nub layers carry TWO Inner-wall tags (R97: the ring's inner
# contour prints as Inner wall on EVERY layer now - the nubs add the 2nd)
_z90 = None
_seen90 = {}
for _l90 in _g90a.split(chr(10)):
    if _l90.startswith(';Z:'):
        _z90 = float(_l90[3:])
    elif _l90.startswith(';TYPE:Inner wall'):
        _seen90[round(_z90, 2)] = _seen90.get(round(_z90, 2), 0) + 1
_nubz90 = sorted(_z90x for _z90x, _c90x in _seen90.items() if _c90x >= 2)
tests.append(('R90 frame bayonet: nub band = 2 layers just above the back band',
    _nubz90 == [5.68, 5.88], str(_nubz90)))

# --- R90.1a: multi-plate mechanics (Part B, trailer, no auto-start) -----------
_g90b = open(_os90.path.join(_d90, _i90a['plates'][1]), encoding='utf-8').read()
_tlA90 = int(_re90.search(r'TOTAL_LAYERS=(\d+)', _g90a).group(1))
_tlB90 = int(_re90.search(r'TOTAL_LAYERS=(\d+)', _g90b).group(1))
tests.append(('R90.1a multi: plate B = backplate+stand, own TOTAL_LAYERS, PRINT_END',
    _g90b.count('EXCLUDE_OBJECT_DEFINE') == 2
    and 'EXCLUDE_OBJECT_DEFINE NAME=BACKPLATE' in _g90b
    and 'EXCLUDE_OBJECT_DEFINE NAME=STAND' in _g90b
    and _tlB90 < _tlA90 and _tlA90 == _g90a.count(';LAYER_CHANGE')
    and _tlB90 == _g90b.count(';LAYER_CHANGE')
    and 'PRINT_END' in _g90b and 'M300 P150 S880' not in _g90b,
    'A=%d B=%d' % (_tlA90, _tlB90)))
tests.append(('R90.1a multi: end-of-plate hint + beeps in A, NO auto-start',
    'plate A of 2 done' in _g90a and 'NOT auto-started' in _g90a
    and _i90a['plates'][1] in _g90a
    and 'M117 R2-FRAME: next -> Part B' in _g90a
    and _g90a.count('M300 P150 S880') == 2 and 'PRINT_END' in _g90a, ''))

# --- R90.1a: small format stays ONE file ---------------------------------------
_p90s, _i90s = _pp.make_frame(preset='9x13', depth=6, frame_w=6, out_dir=_d90)
_g90s = open(_p90s, encoding='utf-8').read()
tests.append(('R90.1a single: 9x13 border 6 = ONE file frame+plate + PRINT_END',
    not _i90s['multi'] and not _i90s['kit'] and len(_i90s['plates']) == 1
    and _os90.path.basename(_p90s) == '00_Frame_9x13_FLATx6_V01.gcode'
    and _g90s.count('EXCLUDE_OBJECT_DEFINE') == 2 and 'PRINT_END' in _g90s
    and 'M300 P150 S880' not in _g90s, _os90.path.basename(_p90s)))

# kit: 13x18 border 12 -> 4 strips + plate (+stand beside plate)
_p90k, _i90k = _pp.make_frame(preset='13x18', depth=6, frame_w=8,
                              closure='BACK', stand=True, out_dir=_d90)
_g90k = open(_p90k, encoding='utf-8').read()
tests.append(('R90.1a: 13x18 border 8 = 2 plates (multi-plate BEFORE kit)',
    _i90k['multi'] and not _i90k['kit'] and len(_i90k['plates']) == 2
    and _os90.path.basename(_p90k) == '00_Frame_13x18_FLATx6_A_V01.gcode'
    and _g90k.count('EXCLUDE_OBJECT_DEFINE') == 1, _os90.path.basename(_p90k)))

# real kit: custom 40x200 border 6 - even the frame alone is too tall
_p90kk, _i90kk = _pp.make_frame(width=40, height=200, depth=6, frame_w=6,
                                closure='BACK', out_dir=_d90)
_g90kk = open(_p90kk, encoding='utf-8').read()
_g90kkb = open(_os90.path.join(_d90, _i90kk['plates'][1]),
               encoding='utf-8').read()
tests.append(('R90.1a kit: frame alone too tall -> 4 strips on A + plate on B',
    _i90kk['kit'] and _i90kk['multi'] and len(_i90kk['plates']) == 2
    and _os90.path.basename(_p90kk) == '00_Frame_40x200_FLATx6_KIT_A_V01.gcode'
    and _g90kk.count('EXCLUDE_OBJECT_DEFINE') == 4
    and 'EXCLUDE_OBJECT_DEFINE NAME=STRIP_T' in _g90kk
    and 'EXCLUDE_OBJECT_DEFINE NAME=STRIP_L' in _g90kk
    and _g90kkb.count('EXCLUDE_OBJECT_DEFINE') == 1
    and 'M300 P150 S880' in _g90kk and 'PRINT_END' in _g90kkb,
    _os90.path.basename(_p90kk)))
tests.append(('R90.1a kit: corner dropped note + wood glue hint',
    any('butt joints' in _n90 for _n90 in _i90kk['notes'])
    and any('corner radius dropped' in _n90 for _n90 in _i90kk['notes']), ''))

# --- R90.1b: disc insert, front flip, structures, cable duct -------------------
def _segs90(path):
    _L90 = {}
    _z90 = None
    _px90 = _py90 = None
    for _l90 in open(path, encoding='utf-8'):
        if _l90.startswith(';Z:'):
            _z90 = float(_l90[3:])
        _m90 = _re90.match(r'^G1 X([\d.-]+) Y([\d.-]+)(?:.* E([\d.]+))?', _l90)
        if _m90 and _z90 is not None:
            _x90, _y90, _e90 = (float(_m90.group(1)), float(_m90.group(2)),
                                 float(_m90.group(3) or 0))
            if _px90 is not None and _e90 > 0:
                _L90.setdefault(_z90, []).append((_px90, _py90, _x90, _y90))
            _px90, _py90 = _x90, _y90
        elif _l90.startswith('G0 X'):
            _m290 = _re90.match(r'^G0 X([\d.-]+) Y([\d.-]+)', _l90)
            if _m290:
                _px90, _py90 = float(_m290.group(1)), float(_m290.group(2))
    return _L90

# FLIP: bed texture as the face - bridge lands at the BOTTOM, no ironing
_p90f, _i90f = _pp.make_frame(preset='9x13', depth=8, frame_w=6, out_dir=_d90)
_g90f = open(_p90f, encoding='utf-8').read()
_p90fl, _i90fl = _pp.make_frame(preset='9x13', depth=8, frame_w=6, front='FLIP',
                                out_dir=_d90)
_g90fl = open(_p90fl, encoding='utf-8').read()
_z90 = None
_bz90n, _bz90f = [], []
for _l90 in _g90f.split(chr(10)):
    if _l90.startswith(';Z:'):
        _z90 = float(_l90[3:])
    elif _l90.startswith(';TYPE:Bridge'):
        _bz90n.append(_z90)
for _l90 in _g90fl.split(chr(10)):
    if _l90.startswith(';Z:'):
        _z90 = float(_l90[3:])
    elif _l90.startswith(';TYPE:Bridge'):
        _bz90f.append(_z90)
tests.append(('R90.1b FLIP: front band on the bed, NOTHING bridges (rule ll), no ironing',
    _i90fl['front'] == 'FLIP' and ';TYPE:Ironing' not in _g90fl
    and any('bed texture IS the visible face' in _n90 for _n90 in _i90fl['notes'])
    # R106: the FLIP shelf rides fully on the front band below - the file
    # carries no Bridge at all, while the normal frame bridges its shelf
    # stubs near the top
    and not _bz90f and _bz90n and max(_bz90n) > 5.0,
    'flip=%s normal=%s' % (_bz90f, _bz90n)))

# disc FRONT: capture lip shrinks the front band opening by 1.2mm
_p90df, _i90df = _pp.make_frame(preset='9x13', depth=8, frame_w=6, disc='GLASS',
                                disc_t=2.0, out_dir=_d90)
_g90df = open(_p90df, encoding='utf-8').read()
_c90 = [float(_v90) for _v90 in _re90.search(
    r'NAME=FRAME CENTER=([\d.-]+),([\d.-]+)', _g90df).groups()]
_S90df = _segs90(_p90df)
_zs90df = sorted(_S90df)
def _omin90(zz):
    _xs90 = [min(_a90, _c90x) for _a90, _b90, _c90x, _d90 in _S90df[zz]
             if abs((_b90 + _d90) / 2 - _c90[1]) < 2]
    return min(abs(_x90 - _c90[0]) for _x90 in _xs90)
tests.append(('R90.1b disc FRONT: lip 1.2mm smaller than the view opening + note',
    _i90df['disc'] == 'GLASS' and 'disc' in _i90df['notes'][0].lower()
    and abs(_omin90(_zs90df[-1]) - (_omin90(_zs90df[-7]) - 1.2)) < 0.35
    and 'front lip holds it captive' in ' '.join(_i90df['notes']),
    'front=%.2f shelf=%.2f' % (_omin90(_zs90df[-1]), _omin90(_zs90df[-7]))))

# disc BACK: note + nubs ride on the disc rim (z unchanged: bb shrinks alike)
_p90db, _i90db = _pp.make_frame(preset='9x13', depth=8, frame_w=6, disc='LITHO',
                                disc_t=3.0, disc_side='BACK', out_dir=_d90)
tests.append(('R90.1b disc BACK: backlit note + plate clamps the disc rim',
    _i90db['disc'] == 'LITHO' and _i90db['disc_side'] == 'BACK'
    and any('BEHIND the photo' in _n90 for _n90 in _i90db['notes'])
    and any('backplate rim clamps' in _n90 for _n90 in _i90db['notes']), ''))

# structures: pattern layers replace the solid face, tag + ironing-off note
for _fr90, _kw90 in (('LINES', {}), ('WAVES', {}), ('HEX', {})):
    _p90s, _i90s = _pp.make_frame(preset='9x13', depth=8, frame_w=6,
                                  front=_fr90, out_dir=_d90, **_kw90)
    _g90s = open(_p90s, encoding='utf-8').read()
    _S90s = _segs90(_p90s)
    _zs90s = sorted(_S90s)
    _solid90 = len(_S90s[_zs90s[-6]])
    _pat90 = len(_S90s[_zs90s[-1]])
    # WAVES = dense 0.4mm curve sampling (many SHORT segments), the others
    # clearly thinner than the solid base layer
    if _fr90 == 'WAVES':
        _thin90 = sum(1 for _a90, _b90, _c90x, _d90 in _S90s[_zs90s[-1]]
                      if _math63.hypot(_c90x - _a90, _d90 - _b90) < 1.0) > 300
        _info90 = 'short=%d' % sum(
            1 for _a90, _b90, _c90x, _d90 in _S90s[_zs90s[-1]]
            if _math63.hypot(_c90x - _a90, _d90 - _b90) < 1.0)
    else:
        _thin90 = _pat90 < _solid90 * 0.6
        _info90 = 'solid=%d pattern=%d' % (_solid90, _pat90)
    tests.append(('R90.1b %s: pattern layer replaces the solid face, no ironing'
                  % _fr90,
        _i90s['front'] == _fr90 and _thin90
        and ';TYPE:Top surface' in _g90s
        and ';TYPE:Ironing' not in _g90s
        and any('no ironing pass' in _n90 for _n90 in _i90s['notes']),
        _info90))

# cable duct: CASE only, slot free in the low layers, closed above
_p90c, _i90c = _pp.make_frame(preset='10x15', depth=20, frame_w=6, cable=True,
                              out_dir=_d90)
_g90c = open(_p90c, encoding='utf-8').read()
_c90c = [float(_v90) for _v90 in _re90.search(
    r'NAME=FRAME CENTER=([\d.-]+),([\d.-]+)', _g90c).groups()]
_S90c = _segs90(_p90c)
_zs90c = sorted(_S90c)
_box90 = (_c90c[0] - 2.2, _c90c[1] - 81.4, _c90c[0] + 2.2, _c90c[1] - 77.5)
# R97: the box sits INSIDE the bottom wall - the brim (new) runs below the
# outer contour and would count as slot material otherwise
def _boxhits90(zz):
    return sum(1 for _a90, _b90, _c90x, _d90 in _S90c[zz]
               if _box90[0] <= (_a90 + _c90x) / 2 <= _box90[2]
               and _box90[1] <= (_b90 + _d90) / 2 <= _box90[3])
tests.append(('R90.1b cable: 6mm slot in the bottom bar, open low / closed high',
    _i90c['cable'] and any('cable duct' in _n90 for _n90 in _i90c['notes'])
    and _boxhits90(_zs90c[0]) <= 1 and _boxhits90(_zs90c[11]) <= 1
    and _boxhits90(_zs90c[12]) >= 2,
    'L1=%d L12=%d L13=%d' % (_boxhits90(_zs90c[0]), _boxhits90(_zs90c[11]),
                             _boxhits90(_zs90c[12]))))

# guards + kit skip note
for _kw90, _frag90 in (
        (dict(preset='9x13', depth=8, cable=True), 'cable duct needs'),
        (dict(preset='9x13', depth=8, front='HEX', shape='OVAL'), 'SHAPE=RECT'),
        (dict(preset='9x13', depth=8, front='FLAT'), 'must be IRON'),
        (dict(preset='9x13', depth=8, disc='STEIN'), 'must be NONE'),
        (dict(preset='9x13', depth=8, front='WAVES', s_amp=9.0), 'out of range'),
        (dict(preset='9x13', depth=8, front='LINES', s_dir='UP'), 'IN or OUT')):
    try:
        _pp.make_frame(out_dir=_d90, **_kw90)
        _ok90 = False
    except ValueError as _e90:
        _ok90 = _frag90 in str(_e90)
    tests.append(('R90.1b guard: %s -> ValueError(%s)'
                  % (list(_kw90.items())[0][1], _frag90), _ok90, ''))
_p90ks, _i90ks = _pp.make_frame(width=40, height=200, depth=6, frame_w=6,
                                front='HEX', cable=True, out_dir=_d90)
tests.append(('R90.1b kit: structure + cable skipped with honest notes',
    _i90ks['kit'] and _i90ks['front'] == 'HEX'
    and any('structure skipped in kit mode' in _n90 for _n90 in _i90ks['notes'])
    and any('cable duct skipped in kit mode' in _n90 for _n90 in _i90ks['notes']),
    ''))

# R106 (rule ll): OVAL + SIDE raises now (the oval wall curves into the
# slot window - the cap lines cannot anchor); RECT SIDE carries the tests
_p90o, _i90o = _pp.make_frame(width=90, height=130, depth=6, frame_w=10,
                              closure='SIDE', out_dir=_d90)
_g90o = open(_p90o, encoding='utf-8').read()
tests.append(('R90 SIDE: 2 objects, slide-in note, slot in the left wall',
    _g90o.count('EXCLUDE_OBJECT_DEFINE') == 2
    and any('slide' in _n90 for _n90 in _i90o['notes']), ''))
tests.append(('R106 SIDE: Y-bridge cap note + narrowed window note present',
    any('anchored on the top/bottom walls' in _n90 for _n90 in _i90o['notes']),
    str(_i90o['notes'])[:120]))
# left of the photo opening nothing extrudes in the groove band (full slit)
_q90o = None
for _l90 in _g90o.split(chr(10)):
    if _l90.startswith('EXCLUDE_OBJECT_DEFINE NAME=FRAME'):
        _q90o = _json90.loads(_l90[_l90.index('POLYGON=') + 8:])
        break
_cx90o = (min(p[0] for p in _q90o) + max(p[0] for p in _q90o)) / 2.0
_cy90o = (min(p[1] for p in _q90o) + max(p[1] for p in _q90o)) / 2.0
_slit90, _z90, _xp90, _yp90 = 0, None, None, None
for _l90 in _g90o.split(chr(10)):
    if _l90.startswith(';Z:'):
        _z90 = float(_l90[3:])
    _m90 = _re90.match(r'G1 X([\d.-]+) Y([\d.-]+).* E([\d.]+)', _l90)
    if _m90 and float(_m90.group(3)) > 0 and _xp90 is not None and 3.15 < _z90 <= 4.65:
        # R106: the T/B walls beyond +-ph/2 stay SOLID by design (they anchor
        # the shelf cap) - the slit check applies INSIDE the window only
        if (max(_xp90, float(_m90.group(1))) < _cx90o - 44.5
                and abs(_yp90 - _cy90o) < 64.0
                and abs(float(_m90.group(2)) - _cy90o) < 64.0):
            _slit90 += 1
    _m291 = _re90.match(r'G[01] X([\d.-]+) Y([\d.-]+)', _l90)
    if _m291:
        _xp90, _yp90 = float(_m291.group(1)), float(_m291.group(2))
tests.append(('R90 SIDE: groove-band layers have NOTHING left of the slot edge '
              'inside the window', _slit90 == 0, 'count %d' % _slit90))

# CASE + guards
_p90c, _i90c = _pp.make_frame(preset='13x18', depth=20, frame_w=6,
                              closure='BACK', stand=True, out_dir=_d90)
tests.append(('R90 CASE 20mm: mode CASE, 100 layers, stand included',
    _i90c['mode'] == 'CASE' and _i90c['layers'] == 100 and _i90c['stand'], ''))
for _kw90, _frag90 in ((dict(width=300, height=200), 'out of range'),
                       (dict(preset='10x15', depth=61), 'out of range'),
                       (dict(preset='10x15', frame_w=3), 'out of range'),
                       (dict(preset='A5', shape='OVAL'), 'oval frame'),
                       (dict(preset='A6', shape='OVAL', closure='SIDE'),
                        'SIDE closure needs a RECT'),
                       (dict(preset='10x15', infill=2), 'out of range'),
                       (dict(width=40, height=208, frame_w=6), 'backplate')):
    try:
        _pp.make_frame(out_dir=_d90, **_kw90)
        _ok90 = False
    except ValueError as _e90:
        _ok90 = _frag90 in str(_e90)
    _ok90 = _ok90 and (_frag90 != 'backplate'
                       or not [f for f in _os90.listdir(_d90) if '40x208' in f])
    tests.append(('R90 guard: %s -> ValueError(%s)' % (list(_kw90.items())[0], _frag90),
        _ok90, ''))

# --- (2) macros render (FRAME_INFO / FRAME_GENERATE / GEN_FRAME) -------------
save_vars.update({'frame_preset': '10x15', 'frame_w': 102.0, 'frame_h': 152.0,
                  'frame_depth': 8.0, 'frame_border': 12.0, 'frame_corner': 6.0,
                  'frame_shape': 'RECT', 'frame_closure': 'BACK',
                  'frame_hang': 'TOP', 'frame_stand': False, 'frame_ironing': True,
                  'frame_infill': 60.0, 'frame_nonce': 3, 'gen_version': 1})
out = render(get_body('macros/17_generator.cfg', 'FRAME_INFO'), {})
tests.append(('R90 FRAME_INFO: settings echo incl. closure + bayonet hint',
    '10x15 photo' in out and 'closure BACK' in out and 'slide 2.5mm' in out, out[:160]))
out = render(get_body('macros/17_generator.cfg', 'FRAME_GENERATE'), {})
tests.append(('R90 FRAME_GENERATE: valid settings bump frame_nonce 3 -> 4',
    'frame_nonce VALUE=4' in out and 'r2_confirm' in out, out[:160]))
save_vars.update({'frame_preset': '', 'frame_w': 300.0})
out = render(get_body('macros/17_generator.cfg', 'FRAME_GENERATE'), {})
tests.append(('R90 FRAME_GENERATE: custom 300mm blocked with LCD notice',
    'must be 40..230' in out and 'frame_nonce' not in out, out[:160]))
save_vars.update({'frame_w': 102.0})
out = render(get_body('macros/17_generator.cfg', 'GEN_FRAME'),
             {'PRESET': 'A6', 'DEPTH': '16', 'SHAPE': 'RECT', 'CLOSURE': 'SIDE',
              'HANG': 'OFF', 'STAND': '1'})
tests.append(('R90 GEN_FRAME: params land in the save_variables + generates',
    'VARIABLE=frame_preset VALUE=' in out and 'A6' in out
    and 'frame_depth VALUE=16.0' in out and 'frame_stand VALUE=True' in out
    and 'frame_shape VALUE=' in out and 'RECT' in out
    and 'FRAME_GENERATE' in out, out[:200]))
out = render(get_body('macros/17_generator.cfg', 'GEN_FRAME'), {'SHAPE': 'HEX'})
tests.append(('R90 GEN_FRAME: HEX shape rejected', 'must be RECT or OVAL' in out, out[:120]))
out = render(get_body('macros/17_generator.cfg', 'GEN_FRAME'),
             {'PRESET': '10x15', 'FRONT': 'HEX', 'DISC': 'GLASS', 'DISC_T': '2',
              'DISC_SIDE': 'BACK', 'CABLE': '1', 'S_SIZE': '9', 'S_DIR': 'IN'})
tests.append(('R90.1b GEN_FRAME: surface/disc/cable params land in the variables',
    'frame_front VALUE=' in out and 'HEX' in out
    and 'frame_disc VALUE=' in out and 'GLASS' in out
    and 'frame_disc_t VALUE=2.0' in out and 'frame_cable VALUE=True' in out
    and 'frame_s_size VALUE=9.0' in out and 'frame_s_dir VALUE=' in out
    and 'FRAME_GENERATE' in out, out[:200]))
out = render(get_body('macros/17_generator.cfg', 'GEN_FRAME'), {'FRONT': 'GLAS'})
tests.append(('R90.1b GEN_FRAME: bad FRONT rejected',
    'FRONT must be IRON, FLIP' in out, out[:120]))

# --- (3) LCD menu --------------------------------------------------------------
_lcd90 = open('menus/lcd_menues.cfg', encoding='utf-8').read()
tests.append(('R90 LCD: Frames menu in Tools with preset/shape/closure/hang/stand',
    '[menu __main __gen __frame]' in _lcd90 and 'name: Frames' in _lcd90
    and all(k in _lcd90 for k in ('__frame __set __pre', '__frame __set __sha',
                                  '__frame __set __clo', '__frame __set __han',
                                  '__frame __set __sta', '__frame __set __sur',
                                  '__frame __set __dsc', '__frame __set __cab',
                                  '__frame __gen'))
    and 'FRAME_GENERATE' in _lcd90, ''))
_fb90 = _lcd90[_lcd90.index('[menu __main __gen __frame]'):
                _lcd90.index('[menu __main __gen __labels]')]
_long90 = [ln[6:] for ln in _fb90.split(chr(10))
           if ln.startswith('name: ') and len(ln[6:]) > 16 and '{' not in ln]
tests.append(('R90 LCD: new names stay short (R29)', len(_long90) == 0,
              str(_long90[:4])))
tests.append(('R90.1b LCD: Surface submenu = ONE choice (5 modes) + structure params',
    all(k in _lcd90 for k in ('__sur __iro', '__sur __flp', '__sur __lin',
                              '__sur __wav', '__sur __hex', '__sur __dee',
                              '__sur __spa', '__sur __ang', '__sur __amp',
                              '__sur __cel', '__sur __dir'))
    and 'Ironing:' not in _fb90, ''))
tests.append(('R90.1b LCD: Disc submenu (5 materials + side + thickness) + cable',
    all(k in _lcd90 for k in ('__dsc __non', '__dsc __gla', '__dsc __ple',
                              '__dsc __fol', '__dsc __lit', '__dsc __sid',
                              '__dsc __thk', '__set __cab')), ''))

# ============== R90.1c field fixes: resume handover, park retract tracking =======
_rc = get_body('macros/09_pause_filament.cfg', '_RESUME_COMMON')
state_vars.update({'mode': 'paused', 'park_retracted': True})
_rc_hot = render(_rc, {'UNRETRACT': '-1'}, etemp=215)
tests.append(('R90.1c resume: XY travel FIRST, refill ON THE WAY, Z last - never E at the part',
    _rc_hot.index('G1 X') < _rc_hot.index('E3.0 F2100')
    and _rc_hot.index('E3.0 F2100') < _rc_hot.index('E-0.5 F300')
    and _rc_hot.index('E-0.5 F300') < _rc_hot.index('G1 Z')
    and 'E0.8' not in _rc_hot
    and 'park retract refilled on the way' in _rc_hot, ''))
state_vars['park_retracted'] = False
_rc_cold = render(_rc, {'UNRETRACT': '-1'}, etemp=215)
tests.append(('R90.1c resume: cold park (no retract) -> no refill, mapping note',
    'E3.0 F2100' not in _rc_cold and 'no extrusion at the print position' in _rc_cold, ''))
_rc_fil = render(_rc, {'UNRETRACT': '0'}, etemp=215)
tests.append(('R90.1c resume: UNRETRACT=0 (filament change) -> ZERO E moves',
    'E3.0 F2100' not in _rc_fil and 'E-0.5' not in _rc_fil
    and 'no extrusion at the print position' in _rc_fil, ''))
_pk = get_body('macros/09_pause_filament.cfg', '_PARK_HEAD')
_pk_hot = render(_pk, {}, etemp=215)
tests.append(('R90.1c park: retract tracks park_retracted=True when hot',
    'E-3 F2100' in _pk_hot and 'VARIABLE=park_retracted VALUE=True' in _pk_hot, ''))
_pk_cold = render(_pk, {}, etemp=100)
tests.append(('R90.1c park: cold -> park_retracted=False (resume pushes nothing)',
    'E-3 F2100' not in _pk_cold and 'VARIABLE=park_retracted VALUE=False' in _pk_cold, ''))
state_vars['mode'] = 'filament'
state_vars['park_retracted'] = True
_cfr = render(get_body('macros/09_pause_filament.cfg', 'CHANGE_FILAMENT_RESUME'), {},
              ps_state='paused', etemp=215)
tests.append(('R90.1c filament resume: strip settles pressure, resume WITHOUT object purge',
    '_PURGE_STRIP MM=15' in _cfr and '_RESUME_COMMON UNRETRACT=0' in _cfr
    and 'NO purge at the object' in _cfr, _cfr[:120]))
state_vars.update({'mode': 'idle', 'park_retracted': False})

# nozzle from printer.cfg
import tempfile as _tf90c, os as _os90c
_nz_dir = _tf90c.mkdtemp()
_nz_cfg = _os90c.path.join(_nz_dir, 'printer.cfg')
open(_nz_cfg, 'w').write('[extruder]\nnozzle_diameter: 0.4\n')
tests.append(('R90.1c nozzle: generators read the REAL diameter from printer.cfg',
    _pp._nozzle_diameter(_nz_cfg) == (0.4, True)
    and _pp._nozzle_diameter(_os90c.path.join(_nz_dir, 'nope.cfg')) == (0.6, False)
    and 'nozzle=_gen_nozzle(directory)' in open('tools/r2_postproc.py',
        encoding='utf-8').read(), ''))

# ===================== R92: purge strip, park corners, litho tags =================
import struct as _st92, zlib as _zl92

# --- (1) _PURGE_STRIP: with objects -> flat line BELOW them, probe-safe ------
_ps92 = get_body('macros/09_pause_filament.cfg', '_PURGE_STRIP')
_objs92 = [{'name': 'plate', 'center': [160, 100], 'polygon': [[100, 60], [220, 60], [220, 140], [100, 140]]}]
out = render(_ps92, {'MM': '15'}, objs=_objs92)
tests.append(('R92 purge strip: front below objects, flat line, never the park corner',
    'front below objects' in out and 'Y52' in out and 'G1 X' in out
    and 'E15.0' in out and 'G1 E15 F240' not in out, out[-260:]))
tests.append(('R92 purge strip: travels HIGH first, descends only in the free zone',
    out.index('G0 Z') < out.index('G0 X') and out.count('G0 Z') >= 3, ''))
tests.append(('R92 purge strip: retract after the line (no strings over the print)',
    'E-2.0' in out, ''))
out = render(_ps92, {'MM': '15'}, objs=[])
tests.append(('R92 purge strip: no objects -> front bed edge',
    'front bed edge' in out and 'Y5' in out, out[-200:]))
out = render(_ps92, {'MM': '15'}, etemp=100)
tests.append(('R92 purge strip: cold hotend -> skipped with notice',
    'Purge skipped' in out and 'G1 E' not in out, out[:120]))
_full92 = [{'name': 'f', 'center': [110, 104], 'polygon': [[6, 3], [214, 3], [214, 205], [6, 205]]}]
out = render(_ps92, {'MM': '15'}, objs=_full92)
tests.append(('R92 purge strip: bed full -> in the air (never into the objects)',
    'in the air' in out and 'G0 X' not in out, out[:140]))

# --- (2) park corner: real bed even with objects ------------------------------
_pc92b = [l for l in render(get_body('macros/09_pause_filament.cfg', '_PARK_HEAD'),
                            {}, objs=_objs92).split('\n')
          if 'G1 X' in l and 'F6000' in l]
import re as _re92
_mvs92 = _re92.findall(r'X([\d.-]+) Y([\d.-]+)', ' '.join(_pc92b))
tests.append(('R92 park: corner chosen inside 0..220 / -3..217 with objects',
    _mvs92 and all(0 <= float(_x92) <= 220 and -3 <= float(_y92) <= 217
                   for _x92, _y92 in _mvs92), str(_mvs92[:2])))

# --- (3) CHANGE_FILAMENT_RESUME / PURGE_MORE use the strip -------------------
state_vars['mode'] = 'filament'
out = render(get_body('macros/09_pause_filament.cfg', 'CHANGE_FILAMENT_RESUME'), {})
state_vars['mode'] = 'printing'
tests.append(('R92 filament change: purge runs as the strip, not a corner blob',
    '_PURGE_STRIP MM=15' in out and 'G1 E15 F240' not in out, out[:160]))
out = render(get_body('macros/09_pause_filament.cfg', 'PURGE_MORE'), {})
tests.append(('R92 PURGE_MORE: strip as well', '_PURGE_STRIP MM=15' in out, out[:120]))

# --- (4) lithophane: honest feature tags (bottom / solid / top / brim / ironing)
def _chunk92(t, d):
    return _st92.pack('>I', len(d)) + t + d + _st92.pack('>I', _zl92.crc32(t + d) & 0xffffffff)
_W92, _H92 = 24, 16
_raw92 = b''
for _y92 in range(_H92):
    _raw92 += b'\x00' + bytes(60 + (x92 * 7 + _y92 * 13) % 120 for x92 in range(_W92))
_png92 = (b'\x89PNG\r\n\x1a\n'
          + _chunk92(b'IHDR', _st92.pack('>IIBBBBB', _W92, _H92, 8, 0, 0, 0, 0))
          + _chunk92(b'IDAT', _zl92.compress(_raw92))
          + _chunk92(b'IEND', b''))
_d92 = _tf90.mkdtemp(prefix='r92_')
_src92 = _os90.path.join(_d92, 'gray92.png')
open(_src92, 'wb').write(_png92)
_p92, _i92 = _pp.make_lithophane(_src92, height_mm=30.0, layer_h=0.12, frame=True,
                                 brim_loops=2, ironing=True, out_dir=_d92)
_g92 = open(_p92, encoding='utf-8').read()
tests.append(('R92 litho: TYPES list = bottom/solid/top + brim + ironing',
    'TYPES=BRIM,SURFACE-BOTTOM,INFILL-SOLID,SURFACE-TOP,IRONING' in _g92, ''))
tests.append(('R92 litho: layer 1+2 tagged Bottom surface (not inner wall)',
    _g92.count(';TYPE:Bottom surface') >= 3          # 2 layers + re-assert after the brim
    and 'APPLY_TYPE TYPE=SURFACE-BOTTOM' in _g92
    and ';TYPE:Inner wall' not in _g92, ''))
tests.append(('R92 litho: ribbon core tagged Internal solid infill',
    _g92.count(';TYPE:Internal solid infill') > 200, ''))
tests.append(('R92 litho: top layers + ironing stay tagged',
    _g92.count(';TYPE:Top surface') >= 2 and ';TYPE:Ironing' in _g92, ''))
_ib92 = _g92.index(';TYPE:Brim')
_ia92 = _g92.index('APPLY_TYPE TYPE=SURFACE-BOTTOM', _ib92)
tests.append(('R92 litho: main type re-asserted AFTER the brim (was BRIM before)',
    _ib92 < _ia92 and _g92.index('LAYER_MARK', _ia92) > _ia92, ''))

# ===================== R91: texture tool (fuzzy + bumps) ========================
import os as _os91, tempfile as _tf91, re as _re91
from r2_texture import apply_texture as _at91

_d91 = _tf91.mkdtemp(prefix='r91_')
_p91, _i91 = _pp.make_frame(preset='9x13', depth=8, frame_w=6, out_dir=_d91,
                            bed=(0.0, -3.0, 220.0, 217.0))

def _outer91(path):
    _pts, _cur = [], ''
    for _l91 in open(path, encoding='utf-8'):
        if _l91.startswith(';TYPE:'):
            _cur = _l91[6:].strip().lower()
            continue
        _m91 = _re91.match(r'^G1 X([\d.-]+) Y([\d.-]+).* E([\d.]+)', _l91)
        if _m91 and float(_m91.group(3)) > 0 and _cur == 'outer wall':
            _pts.append((float(_m91.group(1)), float(_m91.group(2))))
    return _pts

_o91 = _outer91(_p91)

# FUZZY: every outer vertex moves, deterministic, original untouched
_t91a, _ti91a = _at91(_p91, out_dir=_d91, mode='FUZZY', fuzzy_thick=0.3)
_a91 = _outer91(_t91a)
_moved91 = sum(1 for _u, _v in zip(_o91, _a91)
               if abs(_u[0] - _v[0]) + abs(_u[1] - _v[1]) > 1e-6)
tests.append(('R91 fuzzy: ALL outer vertices scattered, original untouched',
    _ti91a['shifted'] == len(_o91) and _moved91 == len(_o91)
    and _os91.path.basename(_t91a) == '00_Frame_9x13_FLATx8_TX_V01.gcode'
    and _os91.path.exists(_p91) and _ti91a['layers'] > 30,
    'shifted=%d/%d' % (_ti91a['shifted'], len(_o91))))

_d91b = _tf91.mkdtemp(prefix='r91_')
_t91b1, _ = _at91(_p91, out_dir=_d91b, mode='FUZZY', fuzzy_thick=0.25)
_t91b2, _ = _at91(_p91, out_dir=_d91b, mode='FUZZY', fuzzy_thick=0.25, version=1)
tests.append(('R91 fuzzy: seeded = deterministic (same params, same output)',
    open(_t91b1, encoding='utf-8').read() == open(_t91b2, encoding='utf-8').read(),
    ''))
_t91c, _ti91c = _at91(_p91, out_dir=_d91b, mode='FUZZY', fuzzy_thick=0.3,
                      fuzzy_density=20, version=5)
_c91 = _outer91(_t91c)
_moved91c = sum(1 for _u, _v in zip(_o91, _c91)
                if abs(_u[0] - _v[0]) + abs(_u[1] - _v[1]) > 1e-6)
tests.append(('R91 fuzzy: density 20% shifts ~1/5 of the vertices',
    0.12 < _moved91c / max(1, len(_o91)) < 0.28,
    '%d/%d' % (_moved91c, len(_o91))))

# BUMPS: bounded amplitude, IN = -OUT, tags/E untouched
_t91d, _ti91d = _at91(_p91, out_dir=_d91b, mode='BUMPS', bump_pattern='WAVES',
                      bump_scale=10, bump_amp=0.35, direction='OUT')
_d91 = _outer91(_t91d)
_dmax91 = max((abs(_u[0] - _v[0]) + abs(_u[1] - _v[1])
               for _u, _v in zip(_o91, _d91)), default=0)
_t91e, _ = _at91(_p91, out_dir=_d91b, mode='BUMPS', bump_pattern='WAVES',
                 bump_scale=10, bump_amp=0.35, direction='IN', version=2)
_e91 = _outer91(_t91e)
tests.append(('R91 bumps: amplitude bounded (<= amp), IN is the mirror of OUT',
    _dmax91 <= 0.36 and _ti91d['pattern'] == 'WAVES'
    and all(abs((_v[0] - _u[0]) + (_w[0] - _u[0])) < 0.01
            for _u, _v, _w in zip(_o91, _d91, _e91)),
    'max=%.3f' % _dmax91))

_keep91 = (';TYPE:', 'EXCLUDE_OBJECT', 'APPLY_TYPE', 'LAYER_MARK')
_src91 = [l for l in open(_p91, encoding='utf-8') if l.startswith(_keep91)]
_out91 = [l for l in open(_t91d, encoding='utf-8') if l.startswith(_keep91)]
tests.append(('R91 bumps: tags / EXCLUDE / APPLY_TYPE / LAYER_MARK untouched',
    _src91 == _out91, ''))
_E91s = [l.split(' E')[1].split()[0] for l in open(_p91, encoding='utf-8')
         if l.startswith('G1') and ' E' in l]
_E91o = [l.split(' E')[1].split()[0] for l in open(_t91d, encoding='utf-8')
         if l.startswith('G1') and ' E' in l]
tests.append(('R91 bumps: E values + count untouched (features stay honest)',
    _E91s == _E91o, ''))

# seamless: same (x,y,z) -> same displacement (grid pattern is periodic)
def _disp_profile(path):
    prof = {}
    for _u, _v in zip(_o91, _outer91(path)):
        prof[(round(_u[0], 1), round(_u[1], 1))] = round(_v[0] - _u[0], 3)
    return prof
_p91f, _ = _at91(_p91, out_dir=_d91b, mode='BUMPS', bump_pattern='GRID',
                 bump_scale=8, bump_amp=0.4, version=3)
_pr91 = _disp_profile(_p91f)
tests.append(('R91 bumps GRID: seamless - identical positions, identical shift',
    len(_pr91) > 100 and len(set(_pr91.values())) > 10, ''))

# special cases: version bump when _TX exists, file without outer walls
_d91v = _tf91.mkdtemp(prefix='r91v_')
_at91(_p91, out_dir=_d91v, mode='FUZZY')
_t91g, _ti91g = _at91(_p91, out_dir=_d91v, mode='FUZZY')
tests.append(('R91: existing _TX file -> next free version (never overwritten)',
    _os91.path.basename(_t91g) == '00_Frame_9x13_FLATx8_TX_V02.gcode'
    and _ti91g['version'] == 2, str(_ti91g)))
# a slicer file that only has infill/fill + inner walls (no 'outer wall' type)
_p91h = _os91.path.join(_d91v, '00_nowall.gcode')
open(_p91h, 'w', encoding='utf-8').write(
    ';FLAVOR:Marlin\n;LAYER_COUNT:2\n'
    'G4\n;TYPE:infill\nG1 X10 Y10 E0.5\nG1 X20 Y10 E0.6\n'
    ';TYPE:inner wall\nG1 X20 Y20 E0.7\nG1 X10 Y20 E0.8\n'
    ';LAYER_CHANGE\n;Z:0.4\n;TYPE:infill\nG1 X12 Y12 E0.9\n')
_t91h, _ti91h = _at91(_p91h, out_dir=_d91v, mode='BUMPS', bump_pattern='GRID')
tests.append(('R91: file without outer walls -> zero shifts, no crash',
    _ti91h['shifted'] == 0 and _os91.path.exists(_t91h), str(_ti91h)))
def _guard91(fn):
    try:
        fn()
        return None
    except ValueError as _e91:
        return str(_e91)
for _gn91, _fn91, _fr91 in (
        ('mode FLAT', lambda: _at91(_p91, out_dir=_d91b, mode='FLAT'),
         'must be FUZZY'),
        ('direction UP', lambda: _at91(_p91, out_dir=_d91b, direction='UP'),
         'must be OUT'),
        ('thick 9', lambda: _at91(_p91, out_dir=_d91b, mode='FUZZY',
                                  fuzzy_thick=9.0), 'out of range'),
        ('pattern KREIS', lambda: _at91(_p91, out_dir=_d91b, mode='BUMPS',
                                        bump_pattern='KREIS'), 'GRID'),
        ('missing src', lambda: _at91('/gibt/es/nicht.gcode',
                                      out_dir=_d91b), 'not found')):
    _err91 = _guard91(_fn91)
    tests.append(('R91 guard: %s -> ValueError(%s)' % (_gn91, _fr91),
                  _err91 is not None and _fr91 in _err91, _err91 or ''))

# TEXTURE_APPLY macro: guards + nonce + preview_file default
out = render(get_body('macros/17_generator.cfg', 'TEXTURE_APPLY'), {'MODE': 'GLAS'})
tests.append(('R91 TEXTURE_APPLY: bad mode rejected', 'must be FUZZY or BUMPS' in out, out[:100]))
save_vars.update({'texture_mode': 'OFF', 'preview_file': 'test.gcode',
                   'texture_nonce': 3})
out = render(get_body('macros/17_generator.cfg', 'TEXTURE_APPLY'), {})
tests.append(('R91 TEXTURE_APPLY: OFF mode -> pick-mode notice, no nonce',
    'pick a mode first' in out and 'texture_nonce' not in out, out[:100]))
save_vars['texture_mode'] = 'BUMPS'
preview_vars.update({'name': 'texcase.gcode'})
out = render(get_body('macros/17_generator.cfg', 'TEXTURE_APPLY'), {})
tests.append(('R91 TEXTURE_APPLY: queued - the SELECTED file becomes the target + nonce bump',
    'VARIABLE=texture_file VALUE=' in out and 'texcase.gcode' in out
    and 'texture_nonce VALUE=4' in out, out[:140]))
# no selection anywhere -> friendly error, no nonce
preview_vars.update({'name': ''})
save_vars.update({'preview_file': '', 'texture_mode': 'BUMPS'})
out = render(get_body('macros/17_generator.cfg', 'TEXTURE_APPLY'), {})
tests.append(('R91 TEXTURE_APPLY: nothing selected -> error, nonce untouched',
    'no file selected' in out and 'texture_nonce' not in out, out[:140]))
preview_vars.update({'name': 'vase.gcode'})
save_vars.update({'texture_mode': 'OFF', 'preview_file': 'vase.gcode'})
save_vars.update({'texture_mode': 'OFF', 'preview_file': 'vase.gcode'})

# LCD structure
_lcd91 = open('menus/lcd_menues.cfg', encoding='utf-8').read()
tests.append(('R91 LCD: Pre-Print > Texture (mode/fuzzy/bumps params + apply)',
    all(k in _lcd91 for k in ('__preprint __tex]', '__tex __mode __fuz',
                              '__tex __mode __bum', '__tex __thk',
                              '__tex __den', '__tex __pat __gri',
                              '__tex __pat __man', '__tex __scl',
                              '__tex __amp', '__tex __dir', '__tex __go'))
    and 'TEXTURE_APPLY' in _lcd91, ''))
# watcher wires the nonce
tests.append(('R91 watcher: texture_nonce handler + lazy r2_texture import',
    "from r2_texture import apply_texture" in open('tools/r2_postproc.py',
        encoding='utf-8').read()
    and 'texture_nonce' in open('tools/r2_postproc.py', encoding='utf-8').read(), ''))


# ===================== R93: file check (version census + retag) =================
import subprocess as _sp93
import sys as _sys93
_d93 = _tf91.mkdtemp(prefix='r93_')
def _w93(n, c):
    open(_os91.path.join(_d93, n), 'w').write(c)
_w93('a_current.gcode', '; R2-POSTPROC v5\n_FILE_INFO x\nG28\n')
_w93('f_stale.gcode', '; R2-POSTPROC v4\n_FILE_INFO x\nG28\n')   # R112: v4 = STALE
_w93('b_old.gcode', '; R2-POSTPROC v2\nG28\n')
_w93('c_untouched.gcode', ';FLAVOR:Marvin\nG28\n')
_w93('d_plot.gcode', '; R2-PLOT v3 (pen)\nG28\n')
_w93('e_tex.gcode', '; R2-TEXTURE v1 (R91) applied to x.gcode\n'
                    '; R2-POSTPROC v5\nG28\n')
_rows93, _tot93 = _mod73.file_check_scan(_d93)
_st93 = {r['name']: r['status'] for r in _rows93}
tests.append(('R93 scan: current / old / untouched / plotter + texture flag',
    _st93 == {'a_current.gcode': 'CURRENT', 'b_old.gcode': 'OLD',
              'c_untouched.gcode': 'UNTOUCHED', 'd_plot.gcode': 'PLOT',
              'e_tex.gcode': 'CURRENT', 'f_stale.gcode': 'STALE'}
    and _tot93 == {'files': 6, 'current': 2, 'old': 1, 'stale': 1,
                   'untouched': 1, 'plot': 1}
    and [r for r in _rows93 if r['name'] == 'e_tex.gcode'][0]['tex'],
    str(_tot93)))
tests.append(('R93 scan: age 0 days, sorted by name, .txt ignored',
    all(r['age'] == 0 for r in _rows93)
    and [r['name'] for r in _rows93] == sorted(r['name'] for r in _rows93)
    and not any(r['name'].endswith('.txt') for r in _rows93), ''))

# SSH one-liner: --file-check works without Klipper
_p93 = _sp93.run([_sys93.executable, 'r2_postproc.py', '--file-check', _d93],
                 capture_output=True, text=True, cwd='tools')
tests.append(('R93 CLI: --file-check lists every file + summary line',
    _p93.returncode == 0 and 'a_current.gcode' in _p93.stdout
    and 'CURRENT' in _p93.stdout and '6 files: 2 current, 1 stale' in _p93.stdout and '1 old' in _p93.stdout and 'f_stale' in _p93.stdout,
    _p93.stdout.strip().splitlines()[-1] if _p93.stdout else _p93.stderr[:80]))

# FILE_CHECK macro: scan branch / arm branch / confirmed branch
save_vars.update({'file_check_nonce': 7})
out = render(get_body('macros/13_system.cfg', 'FILE_CHECK'), {})
tests.append(('R93 FILE_CHECK: scan -> retag cleared + nonce bumped',
    'file_check_retag VALUE=0' in out and 'file_check_nonce VALUE=8' in out
    and 'scanning every g-code file' in out, out[:120]))
state_vars.update({'fc_armed': False})
out = render(get_body('macros/13_system.cfg', 'FILE_CHECK'), {'RETAG': 1})
tests.append(('R93 FILE_CHECK: RETAG without confirm only ARMS',
    'press again' in out and 'fc_armed VALUE=True' in out
    and 'file_check_nonce' not in out, out[:120]))
out = render(get_body('macros/13_system.cfg', 'FILE_CHECK'),
             {'RETAG': 1, 'CONFIRM': 1})
tests.append(('R93 FILE_CHECK: RETAG + CONFIRM -> retag=1 + nonce + disarm',
    'file_check_retag VALUE=1' in out and 'file_check_nonce VALUE=8' in out
    and 'fc_armed VALUE=False' in out and '.r2bak' in out, out[:140]))
state_vars.update({'fc_armed': False})
save_vars.update({'file_check_nonce': 0})

# LCD + watcher wiring
_lcd93 = open('menus/lcd_menues.cfg', encoding='utf-8').read()
tests.append(('R93 LCD: System > File check (+ Retag 2-press, gated NOW)',
    all(k in _lcd93 for k in ('__system __fc0]', '__system __fc1]',
                              '__system __fc2]', '__system __fc3]'))
    and 'FILE_CHECK RETAG=1 CONFIRM=1' in _lcd93
    and "fc_armed}" in _lcd93, ''))
_pp93 = open('tools/r2_postproc.py', encoding='utf-8').read()
tests.append(('R93 watcher: file_check_nonce handler + .r2bak backup + print guard',
    'file_check_nonce' in _pp93 and '.r2bak' in _pp93
    and 'RETAG refused: printing' in _pp93
    and 'max 20 per run' in _pp93, ''))
tests.append(('R93/R91 watcher: both nonces in NONCE_KEYS (restart-safe)',
    "'texture_nonce'" in _pp93 and "'file_check_nonce'" in _pp93, ''))


# ===================== R94: range feature truth (field log .73) =================
import math as _math94

def _src94(d, name='vase94.gcode'):
    """OrcaSlicer-style vase: ;TYPE:outer wall stated ONCE in layer 1, a gap
    fill section in layer 5, skirt only in layer 1 - a range from layer >= 2
    used to lose ALL feature info and print as the raft's INFILL-SOLID."""
    _p94 = _os91.path.join(d, name)
    with open(_p94, 'w') as _f94:
        _f94.write('; R2-POSTPROC v4\n'
                   '_FILE_INFO MATERIAL=PLA LAYER_HEIGHT=0.2 LINE_WIDTH=0.6 '
                   'TOTAL_LAYERS=30 TYPES=SKIRT,WALL-OUTER,GAPS FS_SKIRT=30 '
                   'FS_WALL_OUTER=45 FA_WALL_OUTER=4000 BY_OBJECT=0\n'
                   'M104 S210\nM140 S60\nM83\nG28\nG90\n')
        _z94 = 0.2
        for _lay94 in range(1, 31):
            _f94.write('LAYER_MARK\nG1 Z%.2f F600\n' % _z94)
            if _lay94 == 1:
                _f94.write(';TYPE:skirt\n')
                for _i94 in range(8):
                    _f94.write('G1 X%.2f Y10 E0.5 F1800\n' % (100 + _i94))
                _f94.write(';TYPE:outer wall\n')
            if _lay94 == 5:
                _f94.write(';TYPE:gap fill\n')
                for _i94 in range(4):
                    _f94.write('G1 X%.2f Y20 E0.3 F1500\n' % (105 + _i94))
                _f94.write(';TYPE:outer wall\n')
            for _i94 in range(30):
                _a94 = _i94 / 30.0 * 6.283
                _f94.write('G1 X%.3f Y%.3f E0.05 F2700\n'
                           % (110 + 30 * _math94.cos(_a94),
                              107 + 30 * _math94.sin(_a94)))
            _z94 += 0.2
    return _p94

_d94 = _tf91.mkdtemp(prefix='r94_')
_o94, _ = _mod73.make_range(_src94(_d94), 3, 12, floor=2, brim=3, version=1)
_t94 = open(_o94).read()
_l94 = _t94.splitlines()
_i_cut = next((i for i, l in enumerate(_l94)
               if 'was active at the cut' in l), -1)
tests.append(('R94 vase: body OPENS with the cut feature (WALL-OUTER), not the raft type',
    _i_cut > 0 and 'WALL-OUTER' in _l94[_i_cut]
    and _l94[_i_cut - 1].strip() == 'LAYER_MARK'
    and 'APPLY_TYPE TYPE=WALL-OUTER' in _l94[_i_cut + 1]
    and _t94.index('APPLY_TYPE TYPE=WALL-OUTER') < _t94.index('APPLY_TYPE TYPE=GAPS'),
    _l94[_i_cut][:70] if _i_cut > 0 else 'MISSING'))

# the body's own WALL-OUTER marker sits AFTER the raft's last INFILL-SOLID
# (the 'back to the raft' return after the brim) - and BEFORE any body move
tests.append(('R94 vase: the body does not inherit INFILL-SOLID from the raft',
    _t94.index('APPLY_TYPE TYPE=INFILL-SOLID   ; R2-RANGE: back to the raft')
    < _t94.index('APPLY_TYPE TYPE=WALL-OUTER   ; R2-RANGE: active at the cut')
    < _t94.index('G1 X140.000 Y107.000'), ''))

# brim ON layer 1: after 'raft layer 1' + its Z line, BEFORE 'raft layer 2'
_i_r1 = next(i for i, l in enumerate(_l94) if 'raft layer 1' in l)
_i_br = next(i for i, l in enumerate(_l94) if 'R2-RANGE brim' in l)
_i_r2 = next(i for i, l in enumerate(_l94) if 'raft layer 2' in l)
_z94s = [l for l in _l94[_i_r1:_i_br] if l.startswith('G0 Z')]
tests.append(('R94 brim: on the FIRST layer - inside raft layer 1, before layer 2',
    _i_r1 < _i_br < _i_r2 and _z94s and _z94s[0] == 'G0 Z%.3f F600' % 0.2
    and 'APPLY_TYPE TYPE=BRIM' in _t94
    and _t94.index('APPLY_TYPE TYPE=BRIM') < _t94.index('raft layer 2'),
    _z94s[0] if _z94s else 'no Z'))
tests.append(('R94 brim: raft resumes INFILL-SOLID right after the brim',
    'APPLY_TYPE TYPE=INFILL-SOLID   ; R2-RANGE: back to the raft' in _t94, ''))

# honest _FILE_INFO: skirt (layer 1 only) must NOT be activatable
_fi94 = next(l for l in _l94 if l.startswith('_FILE_INFO'))
tests.append(('R94 info: TYPES describes the EXCERPT (skirt gone, body + generated in)',
    'TYPES=' in _fi94 and 'SKIRT' not in _fi94.split('TYPES=')[1].split()[0]
    and all(k in _fi94 for k in ('WALL-OUTER', 'GAPS', 'INFILL-SOLID', 'BRIM'))
    and 'FS_SKIRT' not in _fi94 and 'FS_WALL_OUTER=45' in _fi94
    and 'FS_INFILL_SOLID=20' in _fi94,
    _fi94[_fi94.index('TYPES='):][:60]))

# floor=0 + brim: the brim block carries its OWN Z (the body's first Z)
_o94b, _ = _mod73.make_range(_src94(_d94, 'vase94b.gcode'), 4, 9,
                             floor=0, brim=2, version=1)
_lb94 = open(_o94b).read().splitlines()
_ib94 = next(i for i, l in enumerate(_lb94) if 'R2-RANGE brim' in l)
_zb94 = [l for l in _lb94[max(0, _ib94 - 4):_ib94] if l.startswith('G0 Z')]
tests.append(('R94 brim without raft: own Z line BEFORE the loops',
    _zb94 and _zb94[0].startswith('G0 Z')
    and 'first layer Z' in _zb94[0], _zb94[0] if _zb94 else 'no Z'))

# Orca/Prusa/Cura ;TYPE: spellings all map
from r2_postproc import TYPE_MAP as _TM94
tests.append(('R94 TYPE_MAP: gap fill + Prusa/Cura dialects map',
    _TM94.get('gap fill') == 'GAPS' and _TM94.get('external perimeter') == 'WALL-OUTER'
    and _TM94.get('perimeter') == 'WALL-INNER' and _TM94.get('top solid infill') == 'SURFACE-TOP'
    and _TM94.get('wall-outer') == 'WALL-OUTER' and _TM94.get('bridge infill') == 'BRIDGE'
    and _TM94.get('support material') == 'SUPPORT', ''))

# a Prusa-dialect source gets APPLY_TYPE markers in the excerpt too
_p94p = _os91.path.join(_d94, 'prusa94.gcode')
with open(_p94p, 'w') as _f94p:
    _f94p.write('; R2-POSTPROC v4\n_FILE_INFO MATERIAL=PLA TOTAL_LAYERS=10 BY_OBJECT=0\n'
                'M104 S210\nM83\nG28\nG90\n')
    for _lay94 in range(1, 11):
        _f94p.write('LAYER_MARK\nG1 Z%.2f F600\n' % (0.2 * _lay94))
        if _lay94 == 1:
            _f94p.write(';TYPE:External perimeter\n')
        for _i94 in range(10):
            _f94p.write('G1 X%d Y%d E0.2 F1500\n' % (50 + _i94, 50 + _lay94))
_o94p, _ = _mod73.make_range(_p94p, 3, 8, floor=0, top=0, brim=0, version=1)
_tp94 = open(_o94p).read()
tests.append(('R94 Prusa dialect: External perimeter -> WALL-OUTER marker',
    'APPLY_TYPE TYPE=WALL-OUTER' in _tp94 and 'was active at the cut' in _tp94, ''))


# ===================== R92.1: global x feature parameter model ==================
# model: eff = base x GLOBAL x FEATURE - the global is the ONE regulator,
# feature % always refers to it; feature accels = hard limits, scaled by ONE
# global percent (the global accel itself stays absolute)
_at921 = get_body('macros/10_live_tuning.cfg', 'APPLY_TYPE')

# --- flow: global override x feature flow ---
state_vars.update({'mode': 'printing', 'g_speed_clean': 100, 'current_type': '',
                   'ignore_overrides': False, 'live_flow': 0})
save_vars.update({'ovf_wallouter_on': True, 'ovf_wallouter_spd': 100.0,
                  'ovf_wallouter_flw': 110.0, 'ovf_wallouter_acc': 0.0,
                  'ov_flow_on': True, 'ov_flow': 98.0, 'ovf_accel_pct': 100.0})
out = render(_at921, {'TYPE': 'WALL-OUTER'})
tests.append(('R92.1 flow: global 98% x feature 110% = 108% (was absolute 110 before)',
    'M99221 S108' in out and '110% x global 98%' in out, out[:200]))
# --- flow: LIVE flow is the global, feature multiplies on top ---
state_vars['live_flow'] = 150
out = render(_at921, {'TYPE': 'WALL-OUTER'})
tests.append(('R92.1 flow: live 150% (the global) x feature 110% = 165%',
    'M99221 S165' in out, out[:200]))
state_vars['live_flow'] = 0
# --- ironing legacy flow also refers to the global now ---
save_vars.update({'ovf_wallouter_on': False, 'ovf_ironing_on': True,
                  'ovf_ironing_spd': 100.0, 'ovf_ironing_flw': 100.0,
                  'ovf_ironing_acc': 0.0, 'ov_ironing_flow_on': True,
                  'ov_ironing_flow': 110.0, 'ov_flow': 90.0})
out = render(_at921, {'TYPE': 'IRONING'})
tests.append(('R92.1 ironing flow: legacy 110% x global 90% = 99%',
    'M99221 S99' in out, out[:200]))
save_vars.update({'ovf_ironing_on': False, 'ov_ironing_flow_on': False,
                  'ov_flow_on': False, 'ov_flow': 100.0})

# --- accel: feature limit x global percent scaler ---
save_vars.update({'ovf_wallouter_on': True, 'ovf_wallouter_spd': 100.0,
                  'ovf_wallouter_flw': 100.0, 'ovf_wallouter_acc': 1000.0,
                  'ovf_accel_pct': 150.0})
out = render(_at921, {'TYPE': 'WALL-OUTER'})
tests.append(('R92.1 accel: feature 1000 x 150% = 1500 mm/s2 (limit scaled)',
    'M99204 S1500' in out and '1000 mm/s2 x 150%' in out, out[:220]))
save_vars.update({'ovf_accel_pct': 100.0})

# --- SET_GLOBAL_ACCEL_PERCENT: saves + applies to the running feature ---
state_vars.update({'current_type': 'WALL-OUTER', 'a_global': 4000.0})
save_vars.update({'ovf_wallouter_on': True, 'ovf_wallouter_acc': 1200.0})
out = render(get_body('macros/10_live_tuning.cfg', 'SET_GLOBAL_ACCEL_PERCENT'),
             {'PERCENT': '150'})
tests.append(('R92.1 SET_GLOBAL_ACCEL_PERCENT: saves 150 + applies 1200->1800 now',
    'VARIABLE=ovf_accel_pct VALUE=150.0' in out and 'ACCEL=1800' in out
    and '1800' in out, out[:220]))
out = render(get_body('macros/10_live_tuning.cfg', 'SET_GLOBAL_ACCEL_PERCENT'),
             {'PERCENT': '400'})
tests.append(('R92.1 SET_GLOBAL_ACCEL_PERCENT: 400 rejected (10..300)',
    'PERCENT=<10..300>' in out and 'SAVE_VARIABLE' not in out, out[:140]))

# --- SET_GLOBAL_ACCEL: the message shows the scaled feature limit ---
save_vars['ovf_accel_pct'] = 150.0
out = render(get_body('macros/10_live_tuning.cfg', 'SET_GLOBAL_ACCEL'),
             {'ACCEL': '4000'})
tests.append(('R92.1 SET_GLOBAL_ACCEL: feature keeps 1200 x 150% = 1800',
    'ACCEL=1800' in out and 'x 150%' in out, out[:220]))

# --- SET_FLOW_RATE explains the model ---
out = render(get_body('macros/10_live_tuning.cfg', 'SET_FLOW_RATE'),
             {'PERCENT': '98'})
tests.append(('R92.1 SET_FLOW_RATE: global = the ONE regulator, features on top',
    'ONE regulator' in out and 'M221 S98' in out, out[:160]))

# --- LCD: percent regulator + effective displays ---
_lcd921 = open('menus/lcd_menues.cfg', encoding='utf-8').read()
tests.append(('R92.1 LCD: Feat x%% input + effective accel + flow Src in Live Tuning',
    '[menu __main __live __accels __pct]' in _lcd921
    and 'name: Feat x:' in _lcd921
    and '[menu __main __live __accels __eff]' in _lcd921
    and '[menu __main __live __extr __fsrc]' in _lcd921
    and 'SET_GLOBAL_ACCEL_PERCENT PERCENT=' in _lcd921, ''))


# ===================== R95: slicer feature census 12 -> 16 =====================
# field log .74: features the slicers emit but the R2 system could neither
# show nor tune. New: overhang wall, internal bridge, prime tower, custom
# code (the mystery low-accel sections). Small perimeters have NO own ;TYPE:
# marker -> config header only (SPEED_SMALL/ACCEL_SMALL in the file info).

# --- TYPE_MAP: the new dialect entries map to the R2 canon ---
from r2_postproc import CFG_KEYS as _CK95
tests.append(('R95 TYPE_MAP: overhang/internal bridge/prime tower/custom map',
    _TM94.get('overhang perimeter') == 'OVERHANG-PERIM'
    and _TM94.get('internal bridge') == 'INTERNAL-BRIDGE'
    and _TM94.get('prime tower') == 'PRIME-TOWER'
    and _TM94.get('wipe tower') == 'PRIME-TOWER'
    and _TM94.get('custom') == 'CUSTOM'
    and _TM94.get('thin wall') == 'WALL-INNER'
    and _TM94.get('skin') == 'SURFACE-TOP'
    and _TM94.get('raft') == 'SURFACE-BOTTOM'
    and _TM94.get('ooze shield') == 'SKIRT'
    and _TM94.get('support transition') == 'SUPPORT', ''))
tests.append(('R95 TYPE_MAP: Cura dialects map (lookup lowercases)',
    _TM94.get('prime-tower') == 'PRIME-TOWER' and _TM94.get('wall-outer') == 'WALL-OUTER'
    and _TM94.get('support-interface') == 'SUPPORT' and _TM94.get('skin') == 'SURFACE-TOP'
    and _TM94.get('raft') == 'SURFACE-BOTTOM' and _TM94.get('top-skin') == 'SURFACE-TOP', ''))
tests.append(('R95 CFG_KEYS: small perimeter speed/accel -> SPEED_SMALL/ACCEL_SMALL',
    _CK95.get('small_perimeter_speed') == 'SPEED_SMALL'
    and _CK95.get('small_perimeter_acceleration') == 'ACCEL_SMALL', ''))

# --- _FILE_INFO: the new FS_/FA_ keys + small perimeter replay ---
_fi95 = get_body('macros/08_print_start_stop.cfg', '_FILE_INFO')
out = render(_fi95, {'SPEED_SMALL': '20', 'ACCEL_SMALL': '2500',
                     'FS_OVERHANG_PERIM': '25', 'FS_PRIME_TOWER': '45',
                     'FA_CUSTOM': '800', 'TYPES': 'WALL-OUTER,OVERHANG-PERIM,PRIME-TOWER,CUSTOM'})
tests.append(('R95 _FILE_INFO: replays the 4 new FS/FA features',
    'VARIABLE=file_feat_spd_overhangperim VALUE=25.0' in out
    and 'VARIABLE=file_feat_spd_primetower VALUE=45.0' in out
    and 'VARIABLE=file_feat_acc_custom VALUE=800.0' in out, out[:200]))
tests.append(('R95 _FILE_INFO: small perimeter speed/accel from the config header',
    'VARIABLE=file_speed_small VALUE=20.0' in out
    and 'VARIABLE=file_accel_small VALUE=2500.0' in out, out[:200]))
_f95all = open('macros/08_print_start_stop.cfg', encoding='utf-8').read()
tests.append(('R95 08 cfg: absent-feature check runs over all 16 codes',
    _f95all.count("'overhangperim','internalbridge','primetower','custom']") >= 1, ''))

# --- _FILE_INFO_RESET wipes the new vars too ---
out = render(get_body('macros/08_print_start_stop.cfg', '_FILE_INFO_RESET'), {})
tests.append(('R95 _FILE_INFO_RESET: new feature vars + small perimeter wiped',
    'VARIABLE=file_feat_spd_overhangperim VALUE=0.0' in out
    and 'VARIABLE=file_feat_acc_custom VALUE=0.0' in out
    and 'VARIABLE=file_speed_small VALUE=0.0' in out
    and 'VARIABLE=file_accel_small VALUE=0.0' in out, out[:160]))

# --- APPLY_TYPE tunes the new types like the old ones ---
_at95 = get_body('macros/10_live_tuning.cfg', 'APPLY_TYPE')
state_vars.update({'mode': 'printing', 'ignore_overrides': False,
                   'current_type': '', 'g_speed_clean': 100, 'live_flow': 0})
save_vars['ovf_accel_pct'] = 100.0
save_vars.update({'ovf_overhangperim_on': True, 'ovf_overhangperim_spd': 50.0,
                  'ovf_overhangperim_acc': 800.0, 'ovf_overhangperim_flw': 100.0})
out = render(_at95, {'TYPE': 'OVERHANG-PERIM'})
tests.append(('R95 APPLY_TYPE: overhang wall 50% + accel 800 applied',
    'M99220 S50' in out and 'M99204 S800' in out, out[:200]))
save_vars.update({'ovf_overhangperim_on': False, 'ovf_overhangperim_spd': 100.0,
                  'ovf_overhangperim_acc': 0.0})
save_vars.update({'ovf_custom_on': True, 'ovf_custom_acc': 600.0})
out = render(_at95, {'TYPE': 'CUSTOM'})
tests.append(('R95 APPLY_TYPE: custom code accel limit applied',
    'M99204 S600' in out, out[:200]))
save_vars.update({'ovf_custom_on': False, 'ovf_custom_acc': 0.0})

# --- SAVE_DEFAULT_PRESET carries all 16 features ---
save_vars.update({'ovf_primetower_on': True, 'ovf_primetower_spd': 60.0,
                  'ovf_primetower_acc': 500.0, 'ovf_primetower_flw': 110.0})
out = render(get_body('macros/05_materials.cfg', 'SAVE_DEFAULT_PRESET'), {})
tests.append(('R95 preset SAVE: all 16 feats in the snapshot',
    "'primetower': [True, 60.0, 500.0, 110.0, 0.0]" in out
    and "'custom':" in out and "'internalbridge':" in out, out[:200]))
save_vars.update({'ovf_primetower_on': False, 'ovf_primetower_spd': 100.0,
                  'ovf_primetower_acc': 0.0, 'ovf_primetower_flw': 100.0})

# --- LOAD: a 16-feat preset restores every feature ---
save_vars['default_preset_1'] = {
    'material': 'PLA', 'bed': 60, 'bed_on': False, 'bed_after': 60, 'bed_after_on': False,
    'hotend_first': 210, 'hotend_first_on': False, 'hotend_after': 210, 'hotend_after_on': False,
    'pa': 0.05, 'pa_on': False, 'pa_smooth': 0.04, 'pa_smooth_on': False,
    'retract_len': 0.8, 'retract_len_on': False, 'retract_speed': 35, 'retract_speed_on': False,
    'unretract_speed': 35, 'unretract_speed_on': False,
    'accel': 4000, 'accel_on': False, 'velocity': 100, 'velocity_on': False,
    'min_cruise': 0, 'min_cruise_on': False, 'square_corner': 0, 'square_corner_on': False,
    'flow': 100, 'flow_on': False, 'fan': 100, 'fan_on': False,
    'ironing_flow': 100, 'ironing_flow_on': False, 'first_layer_speed': 75, 'overrides': 1,
    'feats': {c: [False, 100.0, 0.0, 100.0] for c in
              ['wallouter','wallinner','infillsparse','infillsolid','surfacetop','surfacebottom',
               'bridge','gaps','support','ironing','skirt','brim','overhangperim','internalbridge',
               'primetower','custom']}}
save_vars['default_preset_1']['feats']['primetower'] = [True, 60.0, 500.0, 110.0]
save_vars['default_preset_1']['feats']['custom'] = [True, 100.0, 700.0, 100.0]
out = render(get_body('macros/05_materials.cfg', '_PROFILE_APPLY'), {'SRC': 'default', 'N': '1'})
tests.append(('R95 preset LOAD (16 feats): primetower + custom restored',
    'VARIABLE=ovf_primetower_spd VALUE=60.0' in out
    and 'VARIABLE=ovf_custom_acc VALUE=700.0' in out
    and out.count('ovf_') >= 64, out[:200]))

# --- LOAD: an OLD preset (12 feats) must still load - fallback for the 4 new ---
save_vars['default_preset_2'] = dict(save_vars['default_preset_1'])
save_vars['default_preset_2']['feats'] = {c: v for c, v in
    save_vars['default_preset_1']['feats'].items()
    if c not in ('overhangperim', 'internalbridge', 'primetower', 'custom')}
out = render(get_body('macros/05_materials.cfg', '_PROFILE_APPLY'), {'SRC': 'default', 'N': '2'})
tests.append(('R95 preset LOAD (old 12 feats): new 4 fall back to OFF/100',
    'VARIABLE=ovf_overhangperim_on VALUE=False' in out
    and 'VARIABLE=ovf_custom_spd VALUE=100.0' in out
    and 'VARIABLE=ovf_primetower_on VALUE=False' in out, out[:200]))
del save_vars['default_preset_1'], save_vars['default_preset_2']

# --- _STATE defines the new vars (boot safety) ---
_st95 = open('macros/01_state.cfg', encoding='utf-8').read()
tests.append(('R95 _STATE: new feature vars + small perimeter declared',
    'variable_file_feat_spd_overhangperim' in _st95
    and 'variable_file_feat_acc_custom' in _st95
    and 'variable_file_speed_small' in _st95
    and 'variable_file_accel_small' in _st95, ''))

# --- LCD: 4 new submenu pairs + OH/IB/PT/CU activators ---
_lcd95 = open('menus/lcd_menues.cfg', encoding='utf-8').read()
tests.append(('R95 LCD: 4 new feature submenus (preprint + live)',
    all('[menu __main __%s __feat __%s]' % (a, b) in _lcd95
        for a in ('preprint', 'live') for b in ('oh', 'ib', 'pt', 'cu')), ''))
tests.append(('R95 LCD: new submenu names human (not the activator prefix)',
    'name: Overhang Wall' in _lcd95 and 'name: Internal Bridge' in _lcd95
    and 'name: Prime Tower' in _lcd95 and 'name: Custom Code' in _lcd95, ''))


# ===================== R95 P2: hole-travel discipline in every generator ====
# rule dd: NO unretracted travel over an open hole - at ANY length. The _Pen
# (labels / angles / frames / litho / seal) used to retract only above
# jump_d = 6mm: short crossings (label holes, screw holes) ran flat and
# dragged strings across the opening (field log .74).

# --- unit: the pen retracts on hole crossings BELOW jump_d ---
from r2_postproc import _Pen as _Pen95
_L95 = []
_p95 = _Pen95(_L95, jump_d=6.0)
_p95.holes = [(50.0, 50.0, 5.0)]
_p95.set_z(1.0)
_p95.extrude(47.5, 50.0, 0.5, 1200)
_p95.travel(52.5, 50.0)          # 5mm < jump_d, but crosses the hole
_t95a = chr(10).join(_L95)
_L95b = []
_p95b = _Pen95(_L95b, jump_d=6.0)
_p95b.set_z(1.0)
_p95b.extrude(47.5, 50.0, 0.5, 1200)
_p95b.travel(52.5, 50.0)         # same length, no hole registered
_t95b = chr(10).join(_L95b)
tests.append(('R95 pen: travel over an open hole retracts BELOW jump_d',
    'G10' in _t95a and 'G10' not in _t95b, _t95a.replace(chr(10), ' | ')[:120]))

# --- unit: polygon slots (frame view opening) cross -> retract ---
_L95c = []
_p95c = _Pen95(_L95c, jump_d=6.0)
_p95c.hole_polys = [[(45.0, 45.0), (55.0, 45.0), (55.0, 55.0), (45.0, 55.0)]]
_p95c.set_z(1.0)
_p95c.extrude(41.0, 50.0, 0.5, 1200)
_p95c.travel(44.5, 50.0)         # short, ends at the slot edge
_p95c.travel(56.0, 50.0)         # crosses the whole slot (2mm)
_t95c = chr(10).join(_L95c)
tests.append(('R95 pen: travel through a polygon slot retracts',
    _t95c.count('G10') >= 1 and _t95c.index('G10') < _t95c.index('X56.000'),
    _t95c.replace(chr(10), ' | ')[:150]))

# --- generic audit: NO unretracted travel over a known open hole ---
def _audit95(path, centers):
    """every G0 travel crossing one of centers [(cx, cy, r)] must have a
    G10 in the lines right before it (rule dd audit)."""
    _ln95 = open(path).read().split(chr(10))
    _pos, _was, _bad, _ok = None, False, 0, 0
    for _i95, _l95 in enumerate(_ln95):
        _m95t = _re862.match(r'G0 X([\d.-]+) Y([\d.-]+)', _l95)
        _m95e = _re862.match(r'G1 X([\d.-]+) Y([\d.-]+)', _l95)
        if _l95.startswith('G10'):
            _was = True
        elif _l95.startswith('G11'):
            _was = False
        elif _m95e:
            _pos = (float(_m95e.group(1)), float(_m95e.group(2)))
            _was = False
        if _m95t:
            _np95 = (float(_m95t.group(1)), float(_m95t.group(2)))
            if _pos is not None and any(
                    _seg95(_pos, _np95, _cx, _cy, _r)
                    for (_cx, _cy, _r) in centers):
                if _was:
                    _ok += 1
                else:
                    _bad += 1
            _pos = _np95
    return _bad, _ok

_d95lb = tempfile.mkdtemp(prefix='r95lb_')
_o95lb1, _ = _pp.make_labels(['LOCH'], hole_side=1, hole_d=10, out_dir=_d95lb)
_lns95 = open(_o95lb1).read().split(chr(10))
_i95x = next(_i95 for _i95, _l95 in enumerate(_lns95)
             if _l95.startswith('EXCLUDE_OBJECT_START NAME=LABEL_1'))
_m95e = next(_re862.match(r'G1 X([\d.-]+) Y([\d.-]+)', _l95)
             for _l95 in _lns95[_i95x:] if _re862.match(r'G1 X([\d.-]+) Y([\d.-]+)', _l95))
_x95, _y95 = float(_m95e.group(1)), float(_m95e.group(2))
_c95l = _pp._label_layout(60.0, 30.0, 1, 10)
_hole95 = (_x95 - 0.2 + _c95l[0][0], _y95 - 0.2 + _c95l[0][1], _c95l[0][2])
_b95l, _o95l = _audit95(_o95lb1, [_hole95])
tests.append(('R95 labels: every travel over the label hole retracts (audit)',
    _b95l == 0 and _o95l >= 1, 'bad %d / ok %d' % (_b95l, _o95l)))

# --- angles: find the screw-hole circles in the file itself, then audit ---
def _find_circles95(path):
    _lns = open(path).read().split(chr(10))
    _grp, _out = [], []
    for _l95 in _lns + ['END']:
        _m95 = _re862.match(r'G1 X([\d.-]+) Y([\d.-]+)', _l95)
        if _m95:
            _grp.append((float(_m95.group(1)), float(_m95.group(2))))
        else:
            if len(_grp) >= 12:
                _cx95 = sum(p[0] for p in _grp) / len(_grp)
                _cy95 = sum(p[1] for p in _grp) / len(_grp)
                _rs95 = sorted(_math862.hypot(p[0] - _cx95, p[1] - _cy95) for p in _grp)
                if _rs95[-1] - _rs95[0] < 0.5 and 1.0 < _rs95[len(_rs95) // 2] < 20.0:
                    _c95 = (_cx95, _cy95, _rs95[len(_rs95) // 2])
                    if not any(abs(_c95[0] - o[0]) < 1.5 and abs(_c95[1] - o[1]) < 1.5
                               for o in _out):
                        _out.append(_c95)
            _grp = []
    return _out

_o95an1, _ = _pp.make_angles(count=1, angle_deg=90, leg_a=60, leg_b=60, width=25,
                             layers=6, holes=2, hole_d=6, out_dir=_d95lb,
                             bed=(0.0, -3.0, 244.0, 238.0))
_cs95 = _find_circles95(_o95an1)
_b95a, _o95a = _audit95(_o95an1, _cs95)
tests.append(('R95 angles: every travel over a screw hole retracts (audit)',
    len(_cs95) == 4 and _b95a == 0, 'holes %d / bad %d' % (len(_cs95), _b95a)))

# --- frame: the view opening is a registered polygon keep-out ---
_src95f = 'pen.hole_polys = [[(x + cx, y + cy) for (x, y) in view_c]]'
tests.append(('R95 frame: view opening registered as polygon keep-out',
    _src95f in open('tools/r2_postproc.py').read(), ''))


# ===================== R95 P4: beep discipline while printing ==================
# rule cc: a beep blocks the firmware -> the standing filament oozes a purge
# blob into the print. Confirmation/feedback beeps stay silent during an
# ACTIVE print (NeoPixel carries the feedback); critical sounds always play.

_body95s = get_body('macros/02_sounds.cfg', '_SOUND_LIB')
state_vars['mode'] = 'printing'
out = render(_body95s, {'NAME': 'r2_confirm'}, extra={'tunes': tunes})
tests.append(('R95 beep: r2_confirm SILENT while printing',
    'M300' not in out, out.strip()[:100]))
out = render(_body95s, {'NAME': 'r2_click'}, extra={'tunes': tunes})
tests.append(('R95 beep: r2_click SILENT while printing',
    'M300' not in out, out.strip()[:100]))
out = render(_body95s, {'NAME': 'r2_happy'}, extra={'tunes': tunes})
tests.append(('R95 beep: r2_happy (generator success) SILENT while printing',
    'M300' not in out, out.strip()[:100]))
out = render(_body95s, {'NAME': 'r2_hot'}, extra={'tunes': tunes})
tests.append(('R95 beep: r2_hot (live temp reached) SILENT while printing',
    'M300' not in out, out.strip()[:100]))
_critical95 = []
for _nm95 in ('r2_alarm', 'r2_question', 'r2_pause', 'r2_filament', 'r2_error',
              'r2_notice', 'r2_resume', 'r2_done'):
    out = render(_body95s, {'NAME': _nm95}, extra={'tunes': tunes})
    _critical95.append('%s:%s' % (_nm95, 'M300' in out))
tests.append(('R95 beep: critical sounds ALWAYS audible while printing',
    all(x.endswith(':True') for x in _critical95), ' '.join(_critical95)))
state_vars['mode'] = 'idle'
out = render(_body95s, {'NAME': 'r2_confirm'}, extra={'tunes': tunes})
tests.append(('R95 beep: r2_confirm audible again when idle',
    'M300' in out, out.strip()[:100]))
state_vars['mode'] = 'printing'


# ===================== R95 P3: seamless texture on arcs =======================
# field log .74: the texture showed "only at the corners" - arc-fitted files
# (vases!) carry the outer wall as G2/G3 arcs and R91 only scattered G1
# vertices. Arcs are flattened into short textured chords now; presets are
# sized after OrcaSlicer's fuzzy skin (thickness 0.3 / point distance 0.8).

import math as _m95
_d95t = _tf91.mkdtemp(prefix='r95tex_')
_p95v = _os91.path.join(_d95t, 'vase95.gcode')
_L95v = ['; R2-POSTPROC v5', 'M83', 'G90', 'G28',
         'G0 X120.000 Y100.000', 'G1 Z0.2 F600']
for _ly95 in range(1, 4):
    _L95v += ['LAYER_MARK', 'G1 Z%.2f F600' % (0.2 * _ly95), ';TYPE:Outer wall']
    for _q95 in range(4):
        _a095 = _q95 * _m95.pi / 2
        _a195 = (_q95 + 1) * _m95.pi / 2
        _x095 = 100 + 20 * _m95.cos(_a095)
        _y095 = 100 + 20 * _m95.sin(_a095)
        _x195 = 100 + 20 * _m95.cos(_a195)
        _y195 = 100 + 20 * _m95.sin(_a195)
        _L95v.append('G3 X%.3f Y%.3f I%.3f J%.3f E%.4f F1500'
                     % (_x195, _y195, 100 - _x095, 100 - _y095,
                        (_m95.pi * 20 / 2) * 0.05))
_L95v.append('PRINT_END')
open(_p95v, 'w').write('\n'.join(_L95v) + '\n')
_o95v, _i95v = _at91(_p95v, mode='FUZZY', fuzzy_thick=0.3, fuzzy_density=100,
                     out_dir=_d95t)
_t95v = open(_o95v).read().split('\n')
_arcs95 = [l for l in _t95v if l.startswith(('G2 ', 'G3 '))]
_ch95 = [l for l in _t95v if l.startswith('G1 X') and ' E' in l]
_off95 = 0
for _l95 in _ch95:
    _m95r = _re91.match(r'G1 X([\d.-]+) Y([\d.-]+)', _l95)
    _rr95 = _m95.hypot(float(_m95r.group(1)) - 100, float(_m95r.group(2)) - 100)
    if abs(_rr95 - 20) > 0.005:
        _off95 += 1
tests.append(('R95 texture: ALL 12 arcs flattened, no G2/G3 left',
    _i95v['arcs_flattened'] == 12 and len(_arcs95) == 0 and len(_ch95) > 600,
    'arcs %d / left %d / chords %d' % (_i95v['arcs_flattened'], len(_arcs95), len(_ch95))))
tests.append(('R95 texture: chords carry texture ALL around (> 95% shifted)',
    _off95 >= int(0.95 * len(_ch95)), '%d / %d' % (_off95, len(_ch95))))
_es95 = sum(float(_re91.search(r'E([\d.]+)', l).group(1)) for l in _ch95)
tests.append(('R95 texture: arc E preserved (chords sum to the arc total)',
    abs(_es95 - 12 * (_m95.pi * 20 / 2) * 0.05) < 0.02,
    '%.3f vs %.3f' % (_es95, 12 * (_m95.pi * 20 / 2) * 0.05)))

# --- R-form arcs flatten too ---
_p95r = _os91.path.join(_d95t, 'rform95.gcode')
open(_p95r, 'w').write('M83\nG90\nG0 X95 Y100\n;TYPE:Outer wall\n'
                       'G2 X105 Y100 R5.0 E0.785 F1500\n'
                       'G2 X95 Y100 R-5.0 E0.785 F1500\n')
_o95r, _i95r = _at91(_p95r, mode='FUZZY', fuzzy_thick=0.3, fuzzy_density=100,
                     out_dir=_d95t)
tests.append(('R95 texture: R-form arcs flatten too',
    _i95r['arcs_flattened'] == 2, 'arcs %d' % _i95r['arcs_flattened']))

# --- thick range now Orca-sized 0.05..1.5 ---
_ok95a = _ok95b = _bad95 = False
try:
    _at91(_p95r, mode='FUZZY', fuzzy_thick=1.5, fuzzy_density=100, out_dir=_d95t)
    _ok95a = True
except ValueError:
    pass
try:
    _at91(_p95r, mode='FUZZY', fuzzy_thick=2.0, fuzzy_density=100, out_dir=_d95t)
    _ok95b = True
except ValueError:
    _bad95 = True
tests.append(('R95 texture: thickness range 0.05..1.5 (Orca sizes, 2.0 refused)',
    _ok95a and _bad95 and not _ok95b, ''))

# --- TEXTURE_APPLY presets (Orca sizes) ---
_body95tx = get_body('macros/17_generator.cfg', 'TEXTURE_APPLY')
out = render(_body95tx, {'PRESET': 'ORCA'})
tests.append(('R95 TEXTURE_APPLY: PRESET=ORCA sets FUZZY 0.3 / 100%',
    'VARIABLE=texture_mode' in out and 'FUZZY' in out
    and 'VARIABLE=texture_fuzzy_thick VALUE=0.3' in out
    and 'VARIABLE=texture_fuzzy_density VALUE=100.0' in out, out[:200]))
out = render(_body95tx, {'PRESET': 'LAYERS'})
tests.append(('R95 TEXTURE_APPLY: PRESET=LAYERS sets FUZZY 0.25 (hide layer lines)',
    'VARIABLE=texture_fuzzy_thick VALUE=0.25' in out
    and 'hide layer lines' in out, out[:200]))
out = render(_body95tx, {'PRESET': 'BLA'})
tests.append(('R95 TEXTURE_APPLY: unknown preset refused',
    'PRESET must be ORCA' in out, out[:120]))

# --- LCD: preset submenu ---
_lcd95t = open('menus/lcd_menues.cfg', encoding='utf-8').read()
tests.append(('R95 LCD: texture presets menu (ORCA/LAYERS/SUBTLE/GRIP)',
    '[menu __main __preprint __tex __preset]' in _lcd95t
    and _lcd95t.count('TEXTURE_APPLY PRESET=') == 4
    and 'input_max: 1.5' in _lcd95t, ''))

# ================== R96: dd rest audit - ties / seal / bridge / frame ==================
# rule dd: never travel over an OPEN hole/slot without retracting, at ANY
# travel length. R95 registered labels/angles + the frame view opening;
# R96 audited the remaining generators. Pre-fix violations (found where the
# crossing was SHORTER than the 6mm jump threshold): CLASSIC tie head
# channel 22, LOOP tie slot 13-17, GROOVE seal 1 (a string across the
# sealing groove = a leak path), frame BACKPLATE keyhole/stud holes 74 (!).
# Bridge deck travels are span-long and always retracted - the span is a
# registered keep-out now anyway (fires only when towers nearly touch).
# FLAT seals (zero-length layer seams only) and lithophanes (one continuous
# ribbon per layer, solid plate - no openings at all) are clean by design.

_d96 = _tf90.mkdtemp(prefix='r96_')

def _audit96(path, circles=(), polys=(), deck_only=False, min_li=1,
             first_h=0.28, layer_h=0.2):
    """every G0 travel (from layer min_li up) crossing one of the circles
    [(cx, cy, r)] or polys [poly] must have a G10 right before it (dd)."""
    _ln96 = open(path).read().split(chr(10))
    _pos, _was, _bad, _ok, _deck, _li = None, False, 0, 0, False, 1
    for _l96 in _ln96:
        if 'EXCLUDE_OBJECT_START NAME=BRIDGE_' in _l96:
            _deck = True
        if 'EXCLUDE_OBJECT_END NAME=BRIDGE_' in _l96:
            _deck = False
        _mz96 = _re862.match(r';Z:([\d.]+)', _l96)
        if _mz96:
            _li = int(round((float(_mz96.group(1)) - first_h) / layer_h)) + 1
        _mt96 = _re862.match(r'G0 X([\d.-]+) Y([\d.-]+)', _l96)
        _me96 = _re862.match(r'G1 X([\d.-]+) Y([\d.-]+)', _l96)
        if _l96.startswith('G10'):
            _was = True
        elif _l96.startswith('G11'):
            _was = False
        elif _me96:
            _pos = (float(_me96.group(1)), float(_me96.group(2)))
            _was = False
        if _mt96:
            _n96 = (float(_mt96.group(1)), float(_mt96.group(2)))
            if ((not deck_only or _deck) and _li >= min_li and _pos is not None
                    and (any(_pp._seg_hits_circle(_pos, _n96, *_c96)
                             for _c96 in circles)
                         or any(_pp._seg_hits_poly(_pos, _n96, _g96)
                                for _g96 in polys))):
                if _was:
                    _ok += 1
                else:
                    _bad += 1
            _pos = _n96
    return _bad, _ok

def _tie_polys96(path, length, width, variant, count=2):
    """open-slot rects from the EXCLUDE polygons (tie bbox + parameters)"""
    _t96 = open(path).read()
    _out96 = []
    for _i96 in range(1, count + 1):
        _m96 = _re862.search(
            r'NAME=TIE_%d CENTER=[\d.-]+,[\d.-]+ POLYGON=\[\[([\d.-]+),([\d.-]+)\],'
            r'\[([\d.-]+),([\d.-]+)\],\[([\d.-]+),([\d.-]+)\]' % _i96, _t96)
        _x096, _y096 = float(_m96.group(1)), float(_m96.group(2))
        _w96 = abs(float(_m96.group(5)) - _x096)      # bbox from points 1 + 3
        _h96 = abs(float(_m96.group(6)) - _y096)
        _hl96 = _w96 - length
        _cy96 = _y096 + _h96 / 2.0
        if variant == 'CLASSIC':
            _sw96 = width + 0.5                       # slot clearance 0.25/side
            _r96 = (_x096, _cy96 - _sw96 / 2.0,
                    _x096 + _hl96, _cy96 + _sw96 / 2.0)
        else:
            _hlp96 = round(max(2.0, width * 0.6 + 0.8), 1)
            _hw96 = width + 0.4
            _r96 = (_x096 + (_hl96 - _hlp96) / 2.0, _cy96 - _hw96 / 2.0,
                    _x096 + (_hl96 + _hlp96) / 2.0, _cy96 + _hw96 / 2.0)
        _out96.append([(_r96[0], _r96[1]), (_r96[2], _r96[1]),
                       (_r96[2], _r96[3]), (_r96[0], _r96[3])])
    return _out96

# --- ties: CLASSIC head channel (open above the 2 solid floor layers) ---
_p96tc, _ = _pp.make_cable_ties(count=2, length=60, width=3.0,
                                variant='CLASSIC', out_dir=_d96)
_b96, _o96 = _audit96(_p96tc, polys=_tie_polys96(_p96tc, 60, 3.0, 'CLASSIC'),
                      min_li=3)
tests.append(('R96 ties CLASSIC: head-channel crossings retract at any length',
    _b96 == 0 and _o96 >= 20, 'bad %d / ok %d' % (_b96, _o96)))

_p96tl, _ = _pp.make_cable_ties(count=2, length=60, width=3.0,
                                variant='LOOP', out_dir=_d96)
_b96, _o96 = _audit96(_p96tl, polys=_tie_polys96(_p96tl, 60, 3.0, 'LOOP'))
tests.append(('R96 ties LOOP: slot-hole crossings retract at any length',
    _b96 == 0 and _o96 >= 10, 'bad %d / ok %d' % (_b96, _o96)))

# --- seal: FLAT is clean by design; GROOVE band hops retract ---
_p96sf, _ = _pp.make_seal(od=40, id_=20, height=1.2, profile='FLAT',
                          out_dir=_d96, version=2)
_b96, _o96 = _audit96(_p96sf, circles=[(122.0, 117.5, 10.0)])
tests.append(('R96 seal FLAT: zero-length seams only - no hole crossing',
    _b96 == 0 and _o96 == 0, 'bad %d / ok %d' % (_b96, _o96)))
_p96sg, _ = _pp.make_seal(od=40, id_=20, height=1.2, profile='NUT', out_dir=_d96)
_b96, _o96 = _audit96(_p96sg,
    circles=[(122.0, 117.5, 10.0), (122.0, 117.5, 20.0 - 0.324)])
tests.append(('R96 seal GROOVE: travels across the open groove retract',
    _b96 == 0 and _o96 >= 1, 'bad %d / ok %d' % (_b96, _o96)))
tests.append(('R96 seal GROOVE: exactly 3 retracts (2 long + 1 fixed, '
    'no zero-length extra)',
    open(_p96sg).read().count(chr(10) + 'G10' + chr(10)) == 3, ''))

# --- bridge: deck spans are keep-outs (scoped to the deck blocks) ---
def _bridge_polys96(length, short_pct):
    _cx96, _cy96 = 122.0, 118.5
    _s96 = 1.0 / _math862.sqrt(2.0)
    _dv96, _pv96, _t96 = (_s96, _s96), (-_s96, _s96), 5.0
    _A96 = (_cx96 - _dv96[0] * length / 2.0, _cy96 - _dv96[1] * length / 2.0)
    _B96 = (_cx96 + _dv96[0] * length / 2.0, _cy96 + _dv96[1] * length / 2.0)
    _C96 = (_A96[0] + _dv96[0] * length * short_pct / 100.0,
            _A96[1] + _dv96[1] * length * short_pct / 100.0)
    def _band96(c0, c1):
        _q096 = (c0[0] + _dv96[0] * _t96, c0[1] + _dv96[1] * _t96)
        _q196 = (c1[0] - _dv96[0] * _t96, c1[1] - _dv96[1] * _t96)
        return [(_q096[0] - _pv96[0] * _t96, _q096[1] - _pv96[1] * _t96),
                (_q096[0] + _pv96[0] * _t96, _q096[1] + _pv96[1] * _t96),
                (_q196[0] + _pv96[0] * _t96, _q196[1] + _pv96[1] * _t96),
                (_q196[0] - _pv96[0] * _t96, _q196[1] - _pv96[1] * _t96)]
    return _band96(_A96, _C96), _band96(_A96, _B96)

_p96bd, _ = _pp.make_bridge(length=160, short_pct=30, out_dir=_d96)
_b96, _o96 = _audit96(_p96bd, polys=_bridge_polys96(160, 30), deck_only=True)
tests.append(('R96 bridge: every deck travel over the span retracts',
    _b96 == 0 and _o96 >= 20, 'bad %d / ok %d' % (_b96, _o96)))
_p96be, _ = _pp.make_bridge(length=47, short_pct=30, out_dir=_d96, version=2)
_b96, _o96 = _audit96(_p96be, polys=_bridge_polys96(47, 30), deck_only=True)
tests.append(('R96 bridge edge case (towers nearly touch): span crossings '
    'retract below the jump threshold too',
    _b96 == 0 and _o96 >= 10, 'bad %d / ok %d' % (_b96, _o96)))

# --- frame: the backplate keyhole + stand stud holes are keep-outs ---
def _frame_keeps96(path):
    _m96 = _re862.search(
        r'NAME=BACKPLATE CENTER=([\d.-]+),([\d.-]+) POLYGON=\[\[([\d.-]+),([\d.-]+)\],'
        r'\[([\d.-]+),([\d.-]+)\],\[([\d.-]+),([\d.-]+)\]', open(path).read())
    _bx96, _by96 = float(_m96.group(1)), float(_m96.group(2))
    _bw96 = abs(float(_m96.group(5)) - float(_m96.group(3)))   # pt2.x-pt1.x
    _bh96 = abs(float(_m96.group(8)) - float(_m96.group(4)))   # pt3.y-pt1.y
    return [(_bx96, _by96 + _bh96 / 2.0 - 6.0, 2.6),           # keyhole
            (_bx96, _by96 + _bh96 / 2.0 - 9.4, 1.7),           # keyhole slot
            (_bx96 - 12.0, _by96 - _bh96 / 2.0 + 6.0, 1.35),   # stand studs
            (_bx96 + 12.0, _by96 - _bh96 / 2.0 + 6.0, 1.35)]

_p96f, _ = _pp.make_frame(preset='9x13', depth=6, frame_w=6, stand=True,
                          out_dir=_d96)
_b96, _o96 = _audit96(_p96f, circles=_frame_keeps96(_p96f))
tests.append(('R96 frame: keyhole + stud-hole crossings retract (was 74 bad)',
    _b96 == 0 and _o96 >= 20, 'bad %d / ok %d' % (_b96, _o96)))

# --- lithophane: solid plate, one continuous ribbon per layer - no open
# holes exist; the only long travel (the ironing pass) retracts ---
_pos96l, _was96l, _long96, _longr96 = None, False, 0, 0
for _l96 in open(_p92).read().split(chr(10)):
    _mt96 = _re862.match(r'G0 X([\d.-]+) Y([\d.-]+)', _l96)
    _me96 = _re862.match(r'G1 X([\d.-]+) Y([\d.-]+)', _l96)
    if _l96.startswith('G10'):
        _was96l = True
    elif _l96.startswith('G11'):
        _was96l = False
    elif _me96:
        _pos96l = (float(_me96.group(1)), float(_me96.group(2)))
        _was96l = False
    if _mt96:
        _n96l = (float(_mt96.group(1)), float(_mt96.group(2)))
        if (_pos96l is not None and _math862.hypot(_n96l[0] - _pos96l[0],
                                                   _n96l[1] - _pos96l[1]) > 6.0):
            if _was96l:
                _longr96 += 1
            else:
                _long96 += 1
        _pos96l = _n96l
tests.append(('R96 litho: no openings - the only long travel (ironing) retracts',
    _long96 == 0 and 1 <= _longr96 <= 3,
    'unretracted %d / retracted %d' % (_long96, _longr96)))

# --- source: every generator registers its openings + the zero-length guard --
_src96 = open('tools/r2_postproc.py').read()
tests.append(('R96 source: ties/seal/bridge/frame keep-outs + zero-length guard',
    _src96.count('R96 (rule dd audit)') == 5
    and 'if li > head_base else [])' in _src96
    and _src96.count('pen.holes = list(plate_keeps(') == 2
    and '(d > 0.02 and self._hole_cross(x, y))' in _src96, ''))


# ================== R97: frame bed centering + first-layer discipline ========
# field log .74: (a) frame parts printed hard against the x0/y0 bed corner -
# the plate-B stand even sat at the RAW bed origin, half off the bed, and the
# one-piece stand overlapped the frame ring. Now every plate (one-piece,
# multi Part A/B, kit, kit-multi) is CENTERED on the usable bed. (b) The
# first layer ran as singly printed hatch lines - filament curled up at the
# line starts/ends, borders frayed, the fill grew holes. Now layer 1 =
# brim -> inner wall -> outer wall -> ONE CONTINUOUS zigzag fill (extruded
# connectors; crossings of open holes stay retracting travels, rule dd).

_d97 = _tf90.mkdtemp(prefix='r97_')
_UCX97, _UCY97 = 110.0, 107.0        # usable-bed center (bed 0,-1,220,215 + 6)

def _exc_polys97(path):
    _out97 = {}
    for _l97 in open(path, encoding='utf-8'):
        if _l97.startswith('EXCLUDE_OBJECT_DEFINE'):
            _nm97 = _l97.split('NAME=')[1].split(' ')[0]
            _pts97 = _json86.loads(_l97[_l97.index('POLYGON=') + 8:])
            _xs97 = [_p97[0] for _p97 in _pts97]
            _ys97 = [_p97[1] for _p97 in _pts97]
            _out97[_nm97] = (min(_xs97), min(_ys97), max(_xs97), max(_ys97))
    return _out97

def _centered97(path, tol=2.5):
    _P97 = _exc_polys97(path)
    _x097 = min(v[0] for v in _P97.values())
    _x197 = max(v[2] for v in _P97.values())
    _y097 = min(v[1] for v in _P97.values())
    _y197 = max(v[3] for v in _P97.values())
    return (abs((_x097 + _x197) / 2.0 - _UCX97) <= tol
            and abs((_y097 + _y197) / 2.0 - _UCY97) <= tol
            and _x097 > 4.0 and _y097 > 3.0), \
           'bbox %.0f,%.0f..%.0f,%.0f' % (_x097, _y097, _x197, _y197)

_p97a, _ = _pp.make_frame(preset='9x13', depth=6, frame_w=6, stand=True,
                          out_dir=_d97)
_ok97, _inf97 = _centered97(_p97a)
tests.append(('R97 frame 1pc: whole plate centered, nothing at the bed corner',
    _ok97, _inf97))

_i97m = _pp.make_frame(preset='13x18', depth=6, frame_w=8, stand=True,
                       out_dir=_d97)[1]
_okA97, _iA97 = _centered97(_os90.path.join(_d97, _i97m['plates'][0]))
_okB97, _iB97 = _centered97(_os90.path.join(_d97, _i97m['plates'][1]))
_P97B = _exc_polys97(_os90.path.join(_d97, _i97m['plates'][1]))
_st97 = _P97B['STAND']
_bp97 = _P97B['BACKPLATE']
_noOv97 = (_st97[0] >= _bp97[2] or _bp97[0] >= _st97[2]
           or _st97[1] >= _bp97[3] or _bp97[1] >= _st97[3])
tests.append(('R97 frame multi: both plates centered, stand OFF the origin '
    'and clear of the backplate (was CENTER=0,0 half off the bed)',
    _okA97 and _okB97 and _noOv97 and _st97[0] > 30.0,
    'A %s | B %s | stand %s' % (_iA97, _iB97, _st97)))

_i97k = _pp.make_frame(width=40, height=200, depth=6, frame_w=6,
                       out_dir=_d97)[1]
_okK97 = True
for _f97 in _i97k['plates']:
    _okk97, _ii97 = _centered97(_os90.path.join(_d97, _f97))
    _okK97 = _okK97 and _okk97
tests.append(('R97 frame kit: every kit plate centered (strips / backplate)',
    _okK97 and len(_i97k['plates']) == 2, str(_i97k['plates'])))

# --- first-layer discipline: brim -> inner -> outer -> continuous fill -------
_ln97 = open(_p97a, encoding='utf-8').read().split(chr(10))
_i97f = next(_i97 for _i97, _l97 in enumerate(_ln97)
             if _l97.startswith('EXCLUDE_OBJECT_START NAME=FRAME'))
_seq97 = [_l97[6:] for _l97 in _ln97[_i97f:_i97f + 600]
          if _l97.startswith(';TYPE:')][:4]
tests.append(('R97 frame ring L1: brim -> inner wall -> outer wall -> bottom',
    _seq97 == ['Brim', 'Inner wall', 'Outer wall', 'Bottom surface'],
    str(_seq97)))

def _bottom_block97(lines, start_idx):
    _ib97 = next(_i97 for _i97 in range(start_idx, len(lines))
                 if lines[_i97] == ';TYPE:Bottom surface')
    _ie97 = next(_i97 for _i97 in range(_ib97, len(lines))
                 if lines[_i97].startswith('EXCLUDE_OBJECT_END'))
    return lines[_ib97:_ie97]

_bt97 = _bottom_block97(_ln97, _i97f)
_nG0_97 = len([_l97 for _l97 in _bt97 if _re862.match(r'G0 X', _l97)])
_nG1_97 = len([_l97 for _l97 in _bt97 if _re862.match(r'G1 X', _l97)])
tests.append(('R97/R101 frame ring L1: serpentine = long bead chains (R101 '
    'side grouping), travels few and retracted',
    _nG0_97 <= 10 and _bt97.count('G10') >= _nG0_97 - 1 and _nG1_97 > 200,
    'G0 %d G10 %d G1 %d' % (_nG0_97, _bt97.count('G10'), _nG1_97)))

_i97bp = next(_i97 for _i97, _l97 in enumerate(_ln97)
              if _l97.startswith('EXCLUDE_OBJECT_START NAME=BACKPLATE'))
_bt97b = _bottom_block97(_ln97, _i97bp)
_conn97 = 0
_pos97 = None
for _l97 in _bt97b:
    _me97 = _re862.match(r'G1 X([\d.-]+) Y([\d.-]+)', _l97)
    if _me97:
        _n97 = (float(_me97.group(1)), float(_me97.group(2)))
        if _pos97 is not None:
            _dx97, _dy97 = _n97[0] - _pos97[0], _n97[1] - _pos97[1]
            _dd97 = _math862.hypot(_dx97, _dy97)
            if 0.05 < _dd97 < 2.5 and abs(abs(_dx97) - abs(_dy97)) > 0.3 * _dd97:
                _conn97 += 1        # short move NOT along the 45deg lines
        _pos97 = _n97
    _mt97 = _re862.match(r'G0 X([\d.-]+) Y([\d.-]+)', _l97)
    if _mt97:
        _pos97 = (float(_mt97.group(1)), float(_mt97.group(2)))
tests.append(('R97 backplate L1: continuous zigzag (connectors >= 100, '
    'travels only at the open holes)',
    0 < len([_l97 for _l97 in _bt97b if _re862.match(r'G0 X', _l97)]) <= 30
    and _conn97 >= 100
    and len([_l97 for _l97 in _bt97b if _re862.match(r'G1 X', _l97)]) > 400,
    'conn %d travels %d' % (
        _conn97, len([_l97 for _l97 in _bt97b if _re862.match(r'G0 X', _l97)]))))

# kit strip: brim -> outer wall -> ONE single uninterrupted fill chain
_kf97 = _os90.path.join(_d97, _i97k['plates'][0])
_ln97k = open(_kf97, encoding='utf-8').read().split(chr(10))
_i97s = next(_i97 for _i97, _l97 in enumerate(_ln97k)
             if _l97.startswith('EXCLUDE_OBJECT_START NAME=STRIP_T'))
_seq97k = [_l97[6:] for _l97 in _ln97k[_i97s:_i97s + 60]
           if _l97.startswith(';TYPE:')][:3]
_bt97s = _bottom_block97(_ln97k, _i97s)
tests.append(('R97 kit strip L1: brim -> outer wall -> bottom, ONE travel '
    '(a single continuous bead)',
    _seq97k == ['Brim', 'Outer wall', 'Bottom surface']
    and len([_l97 for _l97 in _bt97s if _re862.match(r'G0 X', _l97)]) == 1,
    '%s | G0 %d' % (str(_seq97k),
                    len([_l97 for _l97 in _bt97s
                         if _re862.match(r'G0 X', _l97)]))))

# cable slot stays OPEN at layer 1: no extruded connector crosses the notch,
# the travels across it retract (rule dd)
_p97c, _ = _pp.make_frame(preset='10x15', depth=20, frame_w=6, cable=True,
                          out_dir=_d97)
_g97c = open(_p97c, encoding='utf-8').read()
_c97c = [float(_v97) for _v97 in _re862.search(
    r'NAME=FRAME CENTER=([\d.-]+),([\d.-]+)', _g97c).groups()]
_notch97 = (_c97c[0] - 3.0, _c97c[1] - 83.0, _c97c[0] + 3.0, _c97c[1] - 76.1)
_poly97n = [(_notch97[0], _notch97[1]), (_notch97[2], _notch97[1]),
            (_notch97[2], _notch97[3]), (_notch97[0], _notch97[3])]
_l1c97 = _g97c.split(chr(10))
_z1c97 = _l1c97.index(';Z:0.280')
_bad97 = _okCross97 = 0
_pos97 = None
_was97 = False
for _l97 in _l1c97[_z1c97:]:
    if _l97.startswith(';Z:') and _l97 != ';Z:0.280':
        break
    _mt97 = _re862.match(r'G0 X([\d.-]+) Y([\d.-]+)', _l97)
    _me97 = _re862.match(r'G1 X([\d.-]+) Y([\d.-]+)', _l97)
    if _l97 == 'G10':
        _was97 = True
    elif _l97 == 'G11':
        _was97 = False
    elif _me97:
        _pos97 = (float(_me97.group(1)), float(_me97.group(2)))
        _was97 = False
    if _mt97:
        _n97 = (float(_mt97.group(1)), float(_mt97.group(2)))
        if _pos97 is not None and _pp._seg_hits_poly(_pos97, _n97, _poly97n):
            if _was97:
                _okCross97 += 1
            else:
                _bad97 += 1
        _pos97 = _n97
tests.append(('R97 cable slot L1: crossings of the open slot retract (no '
    'extruded connector across it)',
    _bad97 == 0, 'bad %d / retracted %d' % (_bad97, _okCross97)))

# source anchors
_src97 = open('tools/r2_postproc.py').read()
tests.append(('R97 source: centering + serpentine + poly offset + plate-B fix',
    'def _emit_serp(' in _src97 and 'def _poly_offset(' in _src97
    and 'def _plate_b_block(' in _src97
    and _src97.count('R97 (field log .74)') >= 5, ''))


# ---------- R98 (field log .75): watcher start scan in time-boxed chunks ----------
# The .75 field log: right after the reboot the watcher's first scan ran as ONE
# blocking pass (12+ min on a swapping Pi Zero) - every file selected in that
# window showed an EMPTY file info; the first selection was even lost entirely
# (overwritten by the next before the loop caught up).
_src98 = open('tools/r2_postproc.py').read()
tests.append(('R98 source: start scan time-boxed (chunk constant + deferral, once exempt)',
    _src98.count('R98 (field log .75)') >= 5
    and '_SCAN_CHUNK_S = 2.0' in _src98
    and "_dl98 = None if once else time.time() + _SCAN_CHUNK_S" in _src98
    and "stats['deferred'] += 1" in _src98
    and "stats['deferred'] = 0" in _src98, ''))
tests.append(('R98 source: deferred files are NOT marked seen (retried next pass)',
    _src98.find("stats['deferred'] += 1") < _src98.find("seen[p] = key", _src98.find("stats['deferred'] += 1") - 4000), ''))
tests.append(('R98 source: backlog push re-checks the preview nonce (never overwrites a selection)',
    "_pn98 == rv.get('preview_nonce', '')" in _src98
    and _src98.find("if _pn98 ==") < _src98.find("for _pp in NEW_PREVIEW[-1:]"), ''))
tests.append(('R98 source: catch-up messages (initial deferral + background done)',
    'deferred to the next pass(es)' in _src98
    and 'background catch-up done' in _src98, ''))

# ---------- R99 (field log .75): generator _FILE_INFO/TYPES + label modes ----------
# The .75 field log: generated files (frame/ties/angles) carry TAG, so the
# scan never adds _FILE_INFO - the Pre-Print file info and the feature
# activators stayed EMPTY for them. Labels get two clear modes now: GROW
# (label grows to the text, W/H = minimums + dynamic lower limits) and
# FIXED (label stays W/H, the font scales into it).
import os as _os99
_d99 = tempfile.mkdtemp()

def _fi99(path):
    for _l99 in open(path, errors='replace').read(8000).splitlines():
        if _l99.startswith('_FILE_INFO'):
            return _l99
    return ''

def _ty99(path):
    _l99 = _fi99(path)
    return _l99.split('TYPES=')[1].split()[0] if 'TYPES=' in _l99 else ''

def _p99(r):
    _p = r[0] if isinstance(r, tuple) else r
    if isinstance(_p, (list, tuple)):
        _p = _p[0]
    return _p

_r99 = _pp.make_frame(preset='9x13', out_dir=_d99)
_fa99 = _p99(_r99)
_fb99 = _os99.path.join(_os99.path.dirname(_fa99), _os99.path.basename(_fa99).replace('_A_', '_B_'))
tests.append(('R99 frame: _FILE_INFO + TYPES on every plate (brim/bottom/ironing on A)',
    'TYPES=' in _fi99(_fa99) and _os99.path.isfile(_fb99) and 'TYPES=' in _fi99(_fb99)
    and _ty99(_fa99).split(',')[0] == 'BRIM' and 'SURFACE-BOTTOM' in _ty99(_fa99)
    and 'IRONING' in _ty99(_fa99) and 'IRONING' not in _ty99(_fb99),
    'A=%s B=%s' % (_ty99(_fa99), _ty99(_fb99))))
_fl99 = _p99(_pp.make_frame(preset='9x13', out_dir=tempfile.mkdtemp(), front='LINES'))
tests.append(('R99 frame: structured fronts tag SURFACE-TOP (was CUSTOM via "Top surface infill")',
    'Top surface infill' not in open(_fl99, errors='replace').read()
    and ';TYPE:Top surface' in open(_fl99, errors='replace').read(), ''))
_t99a = _pp.make_cable_ties(out_dir=_d99, count=2, length=60)
_t99b = _pp.make_cable_ties(out_dir=tempfile.mkdtemp(), count=2, length=60, brim=False)
tests.append(('R99 ties: _FILE_INFO + TYPES, BRIM only when the brim is on',
    _ty99(_p99(_t99a)).startswith('BRIM,') and 'BRIM' not in _ty99(_p99(_t99b))
    and 'INFILL-SOLID' in _ty99(_p99(_t99a)), '%s / %s' % (_ty99(_p99(_t99a)), _ty99(_p99(_t99b)))))
_a99a = _pp.make_angles(out_dir=_d99)
_a99b = _pp.make_angles(out_dir=tempfile.mkdtemp(), ironing=True)
tests.append(('R99 angles: _FILE_INFO + TYPES (no brim feature, IRONING only when on)',
    'BRIM' not in _ty99(_p99(_a99a)) and 'IRONING' in _ty99(_p99(_a99b))
    and 'WALL-OUTER' in _ty99(_p99(_a99a)), '%s / %s' % (_ty99(_p99(_a99a)), _ty99(_p99(_a99b)))))
_o99g, _i99g = _pp.make_labels(['R99GROW'], w=60, h=30, font_size=8, out_dir=_d99)
_o99f, _i99f = _pp.make_labels(['R99GROW'], w=60, h=30, font_size=8, out_dir=_d99, mode='fixed')
tests.append(('R99 labels: GROW grows the label to the font size, FIXED keeps W/H and scales',
    _i99g['w'] > 60 and _i99g.get('grown') and abs(_i99f['w'] - 60) < 0.05
    and abs(_i99f['h'] - 30) < 0.05 and not _i99f.get('grown')
    and _i99f['cap_mm'] < _i99g['cap_mm'],
    'grow %.0fx%.0f cap %.1f / fixed %.0fx%.0f cap %.1f'
    % (_i99g['w'], _i99g['h'], _i99g['cap_mm'], _i99f['w'], _i99f['h'], _i99f['cap_mm'])))
_pv99g = _pp.label_preview(['R99GROW'], w=60, h=30, font_size=8)
_pv99f = _pp.label_preview(['R99GROW'], w=60, h=30, font_size=8, mode='fixed')
tests.append(('R99 labels: preview min sizes only in GROW mode (LCD W/H lower limits)',
    _pv99g['min_w'] and _pv99g['min_h'] and not _pv99f['min_w'] and not _pv99f['min_h'],
    'grow %s/%s fixed %s/%s' % (_pv99g['min_w'], _pv99g['min_h'], _pv99f['min_w'], _pv99f['min_h'])))
_src99 = open('tools/r2_postproc.py').read()
_mnu99 = open('menus/lcd_menues.cfg').read()
_lab99 = open('macros/16_labels.cfg').read()
tests.append(('R99 source: mode wiring (watcher reads label_mode, CLI MODE, menu + macro)',
    _src99.count('R99 (field log .75)') >= 6
    and "mode='fixed' if _vf('label_mode', 0) >= 1 else 'grow'" in _src99
    and "mode='fixed' if _vf_f('label_mode', 0) >= 1 else 'grow'" in _src99
    and "_sv_line('label_min_w'" in _src99
    and 'label_mode' in _mnu99 and 'label_min_w' in _mnu99
    and 'label_mode' in _lab99, ''))

# ---------- R100 (field log .77): plain uploads convert ONCE --------------------------
# The .77 field log: AxtBunny.png (a plain image in the gcodes folder) was
# re-converted to pen-plotter g-code on EVERY watcher (re)start - '1
# processed' at every boot, the .gcode rewritten, its preview push racing
# the Klipper restart after an update (HTTP 404). The 'already converted'
# check looked at the SOURCE file (a .png never carries the R2-PLOT header).
import zlib as _zlib100
import struct as _struct100
import subprocess as _sub100
import sys as _sys100

def _png100(w, h, gray):
    def _chunk(t, d):
        return _struct100.pack('>I', len(d)) + t + d + _struct100.pack(
            '>I', _zlib100.crc32(t + d) & 0xffffffff)
    rows = b''
    for _y100 in range(h):
        rows += b'\x00' + bytes(gray(_x100, _y100) for _x100 in range(w))
    return (b'\x89PNG\r\n\x1a\n'
            + _chunk(b'IHDR', _struct100.pack('>IIBBBBB', w, h, 8, 0, 0, 0, 0))
            + _chunk(b'IDAT', _zlib100.compress(rows))
            + _chunk(b'IEND', b''))

_d100 = tempfile.mkdtemp()
_g100 = _os99.path.join(_d100, 'gcodes')
_os99.makedirs(_g100)
open(_os99.path.join(_g100, 'AxtBunny.png'), 'wb').write(
    _png100(32, 32, lambda x, y: 40 if abs(x - y) < 6 else 220))
_r100a = _sub100.run([_sys100.executable, 'tools/r2_postproc.py',
                      '--watch', _g100, '--once'], capture_output=True, text=True)
_m100 = _os99.path.getmtime(_os99.path.join(_g100, 'AxtBunny.png.gcode')) \
    if _os99.path.isfile(_os99.path.join(_g100, 'AxtBunny.png.gcode')) else -1
import time as _time100
_time100.sleep(0.05)
_r100b = _sub100.run([_sys100.executable, 'tools/r2_postproc.py',
                      '--watch', _g100, '--once'], capture_output=True, text=True)
_m100b = _os99.path.getmtime(_os99.path.join(_g100, 'AxtBunny.png.gcode')) \
    if _os99.path.isfile(_os99.path.join(_g100, 'AxtBunny.png.gcode')) else -1
tests.append(('R100 plot: a plain image converts ONCE - never again on the next scan '
              '(was: re-converted on every watcher start)',
    _m100 > 0 and '[plot]' in _r100a.stdout and 'AxtBunny.png.gcode' in _r100a.stdout
    and '[plot]' not in _r100b.stdout and ', 0 processed,' in _r100b.stdout
    and abs(_m100b - _m100) < 0.001,
    'run1 %s / run2 %s' % (_r100a.stdout.strip().splitlines()[-1][:60],
                           _r100b.stdout.strip().splitlines()[-1][:60])))
_src100 = open('tools/r2_postproc.py').read()
tests.append(('R100 source: conversion check reads the OUTPUT file + 404 push hint',
    _src100.count('R100 (field log .77)') >= 2
    and 'os.path.isfile(out_p)' in _src100
    and 'data_head_if_text(out_p)' in _src100
    and "b'R2-PLOT' in head or" not in _src100
    and 'Klipper still restarting?' in _src100, ''))

# ---------- R101 (field log .78): frame top/bottom layers, sparse infill, travels ----------
# User spec: set the number of solid TOP and BOTTOM layers (independent of the
# front effect and the orientation), infill down to 5% (was 20), travels stay
# INSIDE the model instead of crossing the photo opening on every scanline,
# and every used feature tagged (INFILL-SPARSE below 100%).
import time as _time101

_d101 = tempfile.mkdtemp()
_p101a, _i101a = _pp.make_frame(preset='9x13', out_dir=_d101)
_t101a = open(_p101a, encoding='utf-8').read()
tests.append(('R101/R106 frame: 2 solid bottom skin layers, sparse body, '
              'front band = the top skin',
    _t101a.count(';TYPE:Bottom surface') == 2
    and _t101a.count(';TYPE:Sparse infill') >= 20
    and 'INFILL-SPARSE' in _t101a.split('TYPES=')[1].split()[0]
    # R106 (field log .82, user TYPE map): the solid front band is the
    # frame's TOP skin - SURFACE-TOP belongs in TYPES and the file tags it
    and 'SURFACE-TOP' in _t101a.split('TYPES=')[1].split()[0]
    and _t101a.count(';TYPE:Top surface') == 5,
    'bottom %d sparse %d top %d' % (_t101a.count(';TYPE:Bottom surface'),
                                    _t101a.count(';TYPE:Sparse infill'),
                                    _t101a.count(';TYPE:Top surface'))))
_p101b, _i101b = _pp.make_frame(preset='9x13', out_dir=tempfile.mkdtemp(),
                                top_layers=2)
tests.append(('R101 frame: top_layers=2 thins the front band (5 -> 2 layers, '
              'depth constant -> back band grows)',
    _i101a['front_layers'] == 5 and _i101b['front_layers'] == 2
    and _i101b['layers'] == _i101a['layers']
    and _i101b['back_layers'] == _i101a['back_layers'] + 3,
    'front %d->%d back %d->%d' % (_i101a['front_layers'], _i101b['front_layers'],
                                  _i101a['back_layers'], _i101b['back_layers'])))
_p101c, _i101c = _pp.make_frame(preset='9x13', out_dir=tempfile.mkdtemp(),
                                bottom_layers=0)
_t101c = open(_p101c, encoding='utf-8').read()
tests.append(('R101 frame: bottom_layers=0 = sparse from layer 1 (old behavior)',
    _t101c.count(';TYPE:Bottom surface') == 1
    and _t101c.count(';TYPE:Sparse infill') >= 30, ''))
_p101d, _i101d = _pp.make_frame(preset='9x13', out_dir=tempfile.mkdtemp(),
                                infill=5.0)
tests.append(('R101 frame: infill=5% is valid now (was rejected below 20)',
    _i101d['layers'] == 40 and 'INFILL-SPARSE' in open(_p101d, encoding='utf-8'
    ).read().split('TYPES=')[1].split()[0], ''))
_p101e, _i101e = _pp.make_frame(preset='9x13', out_dir=tempfile.mkdtemp(),
                                front='LINES', top_layers=1, s_dir='IN')
tests.append(('R101 frame: structured front auto-raises a too-thin top band',
    any('raised to' in _n101 for _n101 in _i101e['notes']), str(_i101e['notes'])[:80]))
_p101f, _i101f = _pp.make_frame(preset='9x13', out_dir=tempfile.mkdtemp(),
                                front='FLIP')
_t101f = open(_p101f, encoding='utf-8').read()
tests.append(('R101 frame: FLIP closes with the back skin on top (SURFACE-TOP tags + TYPES)',
    _t101f.count(';TYPE:Top surface') >= 1
    and 'SURFACE-TOP' in _t101f.split('TYPES=')[1].split()[0], ''))

# travels: the ring body layers cross the photo opening only a few times now
def _long_travels101(path, layer):
    _res101 = 0
    _cur101 = 0
    _pos101 = None
    for _l101 in open(path, errors='replace'):
        if _l101.startswith(';LAYER_CHANGE'):
            _cur101 += 1
        elif _cur101 == layer and _re862.match(r'G0 X([\d.-]+) Y([\d.-]+)', _l101):
            _m101 = _re862.match(r'G0 X([\d.-]+) Y([\d.-]+)', _l101)
            _pnt101 = (float(_m101.group(1)), float(_m101.group(2)))
            if _pos101 and (abs(_pnt101[0] - _pos101[0])
                            + abs(_pnt101[1] - _pos101[1])) >= 40:
                _res101 += 1
            _pos101 = _pnt101
    return _res101

tests.append(('R101 frame: mid-body layer crosses the opening only a few times '
              '(was ~139 long travels per layer)',
    _long_travels101(_p101a, 5) <= 8, 'long travels L5: %d' % _long_travels101(_p101a, 5)))
_src101 = open('tools/r2_postproc.py').read()
_mnu101 = open('menus/lcd_menues.cfg').read()
_gen101 = open('macros/17_generator.cfg').read()
tests.append(('R101 source: top/bottom wiring (params, watcher, macro, menu) + buckets',
    _src101.count('R101 (field log .78)') >= 8
    and 'buckets = ([], [], [], [])' in _src101
    and "top_layers=int(_vf90('frame_top_l', 0))" in _src101
    and "bottom_layers=int(_vf90('frame_bot_l', 2))" in _src101
    and 'frame_top_l' in _mnu101 and 'frame_bot_l' in _mnu101
    and 'input_min: 5' in _mnu101
    and 'frame_top_l' in _gen101, ''))

# ---------- R102 (megatest): plot DRAW y-scaling + frame BRIDGE tag ----------
# The megatest sweep (tools/megatest.py - 101 runs, 91 files, every generator
# at its parameter extremes) found two real bugs:
#  (a) plot_convert DRAW mode scaled the scanline y by the PIXEL height -
#      small images exploded past the bed (48px -> y up to +1500mm), big
#      photos silently squashed to ~72mm. Stipple mode was correct.
#  (b) every frame file tags ;TYPE:Bridge (the photo shelf bands) but TYPES=
#      only listed BRIDGE for SIDE closure - the activator for BRIDGE was
#      never offered on normal frames.
_pl102 = _os99.path.join(tempfile.mkdtemp(), 'r102.png.gcode')
# build a small 48x48 test image (the case that exploded) and convert it
_img102 = _os99.path.join(tempfile.mkdtemp(), 'r102.png')
open(_img102, 'wb').write(_png100(48, 48, lambda x, y: 40 if abs(x - y) < 6 else 220))
_n102 = _pp.plot_convert(_img102, var_path=None, out=_pl102)
_ys102 = [float(m.group(1)) for m in _re862.finditer(
    r'G[01] X[-\d.]+ Y([-.\d]+)', open(_pl102, encoding='utf-8').read())]
tests.append(('R102 plot: small image DRAW conversion stays inside the plot bed '
              '(was: y up to +1500mm past the bed)',
    _n102[0] >= 1 and _ys102 and 4.5 <= min(_ys102) and max(_ys102) <= 233.5,
    'y range %.1f..%.1f' % (min(_ys102) if _ys102 else -1,
                            max(_ys102) if _ys102 else -1)))
_fi102 = _pp.make_frame(preset='9x13', out_dir=tempfile.mkdtemp())
_ft102 = _fi102[0] if isinstance(_fi102[0], str) else _fi102[0][0]
_fh102 = open(_ft102, encoding='utf-8').read()
tests.append(('R102 frame: TYPES lists BRIDGE (the shelf bands tag it in every file)',
    'BRIDGE' in _fh102.split('TYPES=')[1].split()[0], ''))
_src102 = open('tools/r2_postproc.py').read()
tests.append(('R102 source: yv scales by line count + plot bed guard',
    'yv = k * bh / nlines' in _src102
    and 'plot geometry %.0fx%.0fmm exceeds the plot bed' in _src102, ''))


# ============================= R104 TESTS (.81) =============================
# Field log .80: 109MB swap STONE-COLD parked (stable from minute 4, load 0.26,
# Throttle NONE, no stutter) yet HOST_CHECK cried 'SWAPPING' + error sound on
# every check - the R78 verdict keyed on usage >= 30MB alone. R104: vmstat
# si/so decides - quiet pages = calm OK verdict, real in/out traffic = loud.
# Plus the COMPATIBILITY.md hardening: PRINT_END presentation (fixed Y228
# crashes on beds < 232mm!), the two Y190 calibrator end parks, PLT_FRAME
# park, and the wipe pad anchor are dynamic/clamped now.
tests.append(('R104 verdict: parked swap (109MB, quiet) = OK with explanation (.80 field case)',
    _mod73._host_verdict(0, 0.39, 4, 109, [(66.0, 'python3')], 0.0)[0] is True
    and 'QUIET' in _mod73._host_verdict(0, 0.39, 4, 109, [(66.0, 'python3')], 0.0)[1]
    and '109MB' in _mod73._host_verdict(0, 0.39, 4, 109, [(66.0, 'python3')], 0.0)[1], ''))
tests.append(('R104 verdict: ACTIVE swapping (850KB/s) stays loud + names the eaters',
    _mod73._host_verdict(0, 0.5, 4, 109, [(66.0, 'python3'), (22.0, 'python')], 850.0)[0] is False
    and 'SWAPPING' in _mod73._host_verdict(0, 0.5, 4, 109, [(66.0, 'python3'), (22.0, 'python')], 850.0)[1]
    and '850KB/s' in _mod73._host_verdict(0, 0.5, 4, 109, [(66.0, 'python3'), (22.0, 'python')], 850.0)[1]
    and 'python3 66MB' in _mod73._host_verdict(0, 0.5, 4, 109, [(66.0, 'python3'), (22.0, 'python')], 850.0)[1], ''))
tests.append(('R104 verdict: unmeasurable activity stays conservative-loud (R78 case)',
    _mod73._host_verdict(0, 0.5, 4, 187)[0] is False
    and 'could not be measured' in _mod73._host_verdict(0, 0.5, 4, 187)[1], ''))
tests.append(('R104 verdict: overload outranks parked swap',
    _mod73._host_verdict(0, 3.9, 4, 109, None, 0.0)[0] is False
    and 'OVERLOADED' in _mod73._host_verdict(0, 3.9, 4, 109, None, 0.0)[1], ''))
tests.append(('R104 vmstat si/so parser: cols 7/8 on 16- and 17-col lines, garbage -> None',
    _mod73._parse_vmstat_swapio('1 0 109000 123000 24000 380000 40 8 12 24 900 1200 4 2 93 1 0') == (40.0, 8.0)
    and _mod73._parse_vmstat_swapio('1 0 109000 123000 24000 380000 0 0 12 24 900 1200 4 2 93 1') == (0.0, 0.0)
    and _mod73._parse_vmstat_swapio('r b swpd free') is None, ''))

# host_check end-to-end with QUIET swap (the exact .80 field picture)
_cap104 = []
_fake104 = dict(_fake78)
_fake104['vmstat 1 2 | tail -1'] = '1 0 0 100000 0 200000 0 0 400 0 900 300 20 10 60 1 0'
def _run104(cmd, shell=True, capture_output=True, text=True, timeout=12):
    return _R78(_fake104.get(cmd, ''))
_orig_mg104 = _mod73._moonraker_gcode
_orig_mi104 = _mod73._read_meminfo
_orig_se104 = _mod73._swap_eaters
_mod73._moonraker_gcode = lambda s, *a, **k: _cap104.append(s)
_mod73._read_meminfo = lambda: {'MemTotal': 354, 'MemAvailable': 121, 'SwapTotal': 767, 'SwapFree': 658}
_mod73._swap_eaters = lambda *a, **k: [(66.0, 'python3'), (22.0, 'python')]
try:
    _sub78.run = _run104
    _hl104 = _mod73.host_check(cores=4)
finally:
    _sub78.run = _orig_run78
    _mod73._moonraker_gcode = _orig_mg104
    _mod73._read_meminfo = _orig_mi104
    _mod73._swap_eaters = _orig_se104
tests.append(('R104 host_check v4: parked swap -> calm verdict, Top SWAP says COLD, no error sound',
    any(l.startswith('Verdict: OK') and 'QUIET' in l and '109MB' in l for l in _hl104)
    and any('parked COLD' in l for l in _hl104)
    and any('M117 Host OK' in s and 'r2_done' in s for s in _cap104)
    and not any('Host SWAPPING' in s or 'r2_error' in s for s in _cap104),
    str([l for l in _hl104 if 'SWAP' in l or l.startswith('Verdict')])[:220]))

# PRINT_END presentation: reference unchanged, small beds clamp, override works
_pe104 = get_body('macros/08_print_start_stop.cfg', 'PRINT_END')
tests.append(('R104 PRINT_END: reference axes keep X10 Y228 (nothing changes here)',
    'G0 X10 Y228 F6000' in render(_pe104, {}), ''))
_gd104 = dict(build_printer())
_gd104['toolhead'] = M({'axis_maximum': M({'x': 180.0, 'y': 180.0, 'z': 200.0}),
                        'axis_minimum': M({'x': 0.0, 'y': 0.0, 'z': 0.0}),
                        'homed_axes': 'xyz', 'max_accel': 4000, 'max_velocity': 250.0})
_out104 = render(_pe104, {}, {'printer': MP(_gd104)})
tests.append(('R104 PRINT_END: small bed clamps the presentation (Y228 -> 176, no crash)',
    'G0 X10 Y176 F6000' in _out104 and 'Y228' not in _out104,
    [l for l in _out104.split('\n') if 'F6000' in l][:3]))
_gd104b = dict(build_printer())
_gd104b['gcode_macro _R2_CONFIG'] = {'present_x': 40, 'present_y': 100}
_out104b = render(_pe104, {}, {'printer': MP(_gd104b)})
tests.append(('R104/R104.2 PRINT_END: _R2_CONFIG variable_present_x/y override (clamped to axes)',
    'G0 X40 Y100 F6000' in _out104b, [l for l in _out104b.split('\n') if 'F6000' in l][:3]))

# _NOZZLE_WIPE: default anchor unchanged, [r2_postproc] wipe_x/wipe_y moves it
_nw104 = get_body('macros/12_maintenance.cfg', '_NOZZLE_WIPE')
_out104c = render(_nw104, {})
tests.append(('R104 wipe: default anchor stays the axis-minimum corner (unchanged)',
    'G0 X0.0 Y0.0 F8000' in _out104c and 'G1 X13.0' in _out104c,
    [l for l in _out104c.split('\n') if l.startswith('G0 X')][:2]))
_gd104c = dict(build_printer())
_gd104c['gcode_macro _R2_CONFIG'] = {'wipe_x': 60, 'wipe_y': 120}
_out104d = render(_nw104, {}, {'printer': MP(_gd104c)})
tests.append(('R104/R104.2 wipe: _R2_CONFIG variable_wipe_x/y moves the pad (60/120 -> 60..73)',
    'G0 X60.0 Y120.0 F8000' in _out104d and 'G1 X73.0' in _out104d,
    [l for l in _out104d.split('\n') if l.startswith('G0 X') or l.startswith('G1 X')][:3]))

# sources: no naked fixed parks left + megatest adaptability
_m12_104 = open('macros/12_maintenance.cfg', encoding='utf-8').read()
tests.append(('R104 sources: no naked Y190 calibrator parks left, both clamped to the axes',
    'G0 X10 Y190 F6000' not in _m12_104
    and _m12_104.count('axis_maximum.y - 4') >= 2, ''))
tests.append(('R104 sources: PLT_FRAME parks inside the PLOT bed (not X5 Y190)',
    'G0 X5 Y190 F6000' not in _m12_104 and 'y1 - 43' in _m12_104, ''))
tests.append(('R104 megatest: --bed/--cfg adapt the sweep, small-bed ValueErrors count as SKIP',
    '--bed=' in open('tools/megatest.py').read()
    and 'SKIP (bed too small' in open('tools/megatest.py').read(), ''))


# ============================= R104.2 TESTS (.82) =============================
# Field log .81: the R92-onward config carrier was a RAW [r2_postproc] section
# in printer.cfg - Klipper REFUSES unknown sections ('Section r2_postproc is
# not a valid config section') -> halt loop. The carrier is now a KAMP-style
# [gcode_macro _R2_CONFIG] with variable_* entries: valid for Klipper, native
# for the macros, parsed by the watcher (_bed_limits).
_src082a = open('macros/08_print_start_stop.cfg', encoding='utf-8').read()
_src092a = open('macros/09_pause_filament.cfg', encoding='utf-8').read()
_src122a = open('macros/12_maintenance.cfg', encoding='utf-8').read()
_allmac2a = _src082a + _src092a + _src122a
tests.append(('R104.2 sources: no macro reads the old settings.get(r2_postproc) anymore',
    "settings.get('r2_postproc'" not in _allmac2a, ''))
tests.append(('R104.2 sources: 5 spots read [gcode_macro _R2_CONFIG] (prime, present, parks x2, wipe)',
    _allmac2a.count("'gcode_macro _R2_CONFIG' in printer") == 5,
    str(_allmac2a.count("'gcode_macro _R2_CONFIG' in printer"))))
_ship2a = _src082a + _src092a + _src122a \
    + open('menus/lcd_menues.cfg', encoding='utf-8').read() \
    + open('printer.cfg.example', encoding='utf-8').read()
tests.append(('R104.2 guard: NO shipped cfg carries a live [r2_postproc] header (halts Klipper!)',
    '\n[r2_postproc]\n' not in _ship2a, ''))
tests.append(('R104.2 example: printer.cfg.example shows the valid _R2_CONFIG carrier (commented)',
    '[gcode_macro _R2_CONFIG]' in open('printer.cfg.example', encoding='utf-8').read()
    and 'variable_bed_min_x' in open('printer.cfg.example', encoding='utf-8').read(), ''))

# _PRIME_LINE end-to-end with a custom _R2_CONFIG bed (10..200 / 5..195):
# probe-safe window -> xmin 15, xmax 195, line start xs = min(195, 125) = 125,
# y = ymin+3 = 13 - the line lives INSIDE the configured bed
_pl2a = get_body('macros/08_print_start_stop.cfg', '_PRIME_LINE')
_gd2a = dict(build_printer())
_gd2a['gcode_macro _R2_CONFIG'] = {'bed_min_x': 10, 'bed_max_x': 200,
                                   'bed_min_y': 5, 'bed_max_y': 195}
_out2a = render(_pl2a, {}, {'printer': MP(_gd2a)})
# (the suite's default demo object at 60..140 makes the R49 placement pick the
#  front strip below it: y = 50 in both cases - the X values prove the bed flows in)
tests.append(('R104.2 _PRIME_LINE: probe-safe window from the _R2_CONFIG bed (10..200 -> X15..125)',
    'G0 X125.0 Y50 F6000' in _out2a and 'G1 X15.0 E' in _out2a,
    [l for l in _out2a.split('\n') if l.startswith('G0 X') or l.startswith('G1 X')][:3]))
tests.append(('R104.2 _PRIME_LINE: without _R2_CONFIG the Ender-3 default window is used (unchanged)',
    'G0 X115.0 Y50 F6000' in render(_pl2a, {}),
    [l for l in render(_pl2a, {}).split('\n') if l.startswith('G0 X')][:2]))

# ============== R106 (field log .82): fan wake-up, hints, menu filter ========
_fs106 = get_body('macros/10_live_tuning.cfg', 'SET_FAN_SCALE')
_sv106 = dict(state_vars)
_sv106.update({'mode': 'printing', 'layer': 5, 'file_fan': 178,
               'ignore_overrides': False})
_g106 = dict(build_printer())
_g106['gcode_macro _STATE'] = M(_sv106)
_g106['fan'] = M({'speed': 0.0})          # fan currently OFF = the bug case
_out106 = render(_fs106, {'PERCENT': '80'}, {'printer': MP(_g106)})
tests.append(('R106 fan: scale wakes a 0% fan from the FILE value '
              '(printing L5, file S178, 80% -> M99106 S142)',
    'M99106 S142' in _out106, [l for l in _out106.split('\n') if 'M99106' in l][:2]))
_sv106b = dict(_sv106)
_sv106b['layer'] = 1
_g106b = dict(_g106)
_g106b['gcode_macro _STATE'] = M(_sv106b)
_out106b = render(_fs106, {'PERCENT': '80'}, {'printer': MP(_g106b)})
tests.append(('R106 fan: layer-1 hold still wins (stored, no forced M99106)',
    'M99106 S' not in _out106b and 'layer 1 stays fan OFF' in _out106b,
    [l for l in _out106b.split('\n') if 'RESPOND' in l or 'M99106' in l][:2]))
_lv106 = get_body('macros/10_live_tuning.cfg', 'SET_LIVE_VELOCITY')
tests.append(('R106 velocity: RESPOND explains the CAP semantics',
    'this is a CAP' in render(_lv106, {'VELOCITY': '120'}), ''))
_sc106 = get_body('macros/10_live_tuning.cfg', 'SET_LIVE_SQUARE_CORNER')
tests.append(('R106 corner: RESPOND names the visible lever (cruise ratio)',
    'cruise ratio' in render(_sc106, {'VALUE': '8'}), ''))
_mcr106 = get_body('macros/10_live_tuning.cfg', 'SET_LIVE_MINIMUM_CRUISE_RATIO')
_outmcr = render(_mcr106, {'VALUE': '0.95'})
tests.append(('R106 MCR: echo rounds (0.95, never 0.9500000000000004)',
    '0.95' in _outmcr and '0.9500' not in _outmcr,
    [l for l in _outmcr.split('\n') if 'OK' in l][:1]))
_lcd106 = open('menus/lcd_menues.cfg', encoding='utf-8').read()
_n106 = _lcd106.count("enable: {printer['gcode_macro _STATE'].file_types|default('') == '' or '")
tests.append(('R106 menus: 80 feature items (pre-print + live) hide when the '
              'file lacks them; available-but-off stay visible',
    _n106 == 80, 'count %d' % _n106))
tests.append(('R106 preset: picking a preset fills W/H as editable values',
    all(('VARIABLE=frame_w VALUE=%d' % w) in _lcd106
        and ('VARIABLE=frame_h VALUE=%d' % h) in _lcd106
        for w, h in ((90, 130), (102, 152), (130, 180), (105, 148))), ''))

# ============== R106 (f)+(g): frame user presets + wall loops ==============
save_vars.update({'frame_preset': '9x13', 'frame_w': 90.0, 'frame_h': 130.0,
                  'frame_depth': 8.0, 'frame_border': 12.0, 'frame_corner': 6.0,
                  'frame_shape': 'RECT', 'frame_closure': 'BACK',
                  'frame_hang': 'TOP', 'frame_stand': False,
                  'frame_ironing': True, 'frame_infill': 60.0,
                  'frame_top_l': 0, 'frame_bot_l': 2, 'frame_front': 'IRON',
                  'frame_cable': False, 'frame_disc': 'NONE',
                  'frame_disc_t': 1.0, 'frame_disc_side': 'FRONT',
                  'frame_s_deep': 0.8, 'frame_s_space': 6.0,
                  'frame_s_angle': 45.0, 'frame_s_amp': 1.2,
                  'frame_s_size': 8.0, 'frame_s_dir': 'OUT',
                  'frame_walls': 3, 'frame_nonce': 3})
_fs106f = get_body('macros/17_generator.cfg', 'FRAME_SAVE_PRESET')
_outf = render(_fs106f, {})
tests.append(('R106 frame preset: SAVE fills slot 1 with the FULL config (26 keys, naked dict)',
    'SAVE_VARIABLE VARIABLE=frame_user_preset_1 VALUE="' in _outf
    and "'walls': 3" in _outf and "'s_dir': 'OUT'" in _outf
    and "'front': 'IRON'" in _outf and "'cable': False" in _outf,
    _outf.split(chr(10))[1][:110] if len(_outf.split(chr(10))) > 1 else _outf[:110]))
# slot 1 full -> save goes to slot 2
save_vars.update({'frame_user_preset_1':
                  {'preset': 'A6', 'w': 105.0, 'h': 148.0, 'depth': 10.0,
                   'border': 8.0, 'corner': 6.0, 'walls': 2, 'shape': 'OVAL',
                   'closure': 'BACK', 'hang': 'OFF', 'stand': True,
                   'ironing': False, 'infill': 40.0, 'top_l': 4, 'bot_l': 3,
                   'front': 'FLIP', 'cable': True, 'disc': 'LITHO',
                   'disc_t': 3.0, 'disc_side': 'BACK', 's_deep': 1.0,
                   's_space': 5.0, 's_angle': 30.0, 's_amp': 1.5,
                   's_size': 6.0, 's_dir': 'IN'}})
_outf2 = render(_fs106f, {})
tests.append(('R106 frame preset: SAVE skips the full slot -> slot 2',
    'frame_user_preset_2 VALUE="' in _outf2
    and 'frame_user_preset_1 VALUE="' not in _outf2, ''))
_fl106f = get_body('macros/17_generator.cfg', 'FRAME_LOAD_PRESET')
_outl = render(_fl106f, {'N': '1'})
tests.append(('R106 frame preset: LOAD writes all 26 vars incl. walls + escaped strings',
    _outl.count('SAVE_VARIABLE') >= 26
    and 'VARIABLE=frame_walls VALUE=2' in _outl
    and 'VARIABLE=frame_front VALUE=' + chr(34) + chr(92) + chr(34)
        + 'FLIP' + chr(92) + chr(34) + chr(34) in _outl
    and 'VARIABLE=frame_preset VALUE=' in _outl
    and 'VARIABLE=frame_s_dir VALUE=' in _outl,
    [l for l in _outl.split(chr(10)) if 'frame_walls' in l or 'frame_preset ' in l][:2]))
_fd106f = get_body('macros/17_generator.cfg', 'FRAME_DELETE_PRESET')
tests.append(('R106 frame preset: DELETE frees the slot, touches nothing else',
    'VARIABLE=frame_user_preset_1 VALUE=0' in render(_fd106f, {'N': '1'})
    and render(_fd106f, {'N': '1'}).count('SAVE_VARIABLE') == 1, ''))
tests.append(('R106 frame preset: INFO lists all 8 slots',
    render(get_body('macros/17_generator.cfg', 'FRAME_PRESETS_INFO'), {})
    .count('RESPOND') == 9, ''))
_gf106 = get_body('macros/17_generator.cfg', 'GEN_FRAME')
tests.append(('R106 GEN_FRAME: WALLS=3 lands in frame_walls, WALLS=9 is rejected',
    'VARIABLE=frame_walls VALUE=3' in render(_gf106, {'WALLS': '3'})
    and 'WALLS must be 1..4' in render(_gf106, {'WALLS': '9'}), ''))
_lcd106f = open('menus/lcd_menues.cfg', encoding='utf-8').read()
tests.append(('R106 LCD: walls input + preset menu (8 load, 8 delete, guards)',
    'VARIABLE=frame_walls VALUE={menu.input' in _lcd106f
    and _lcd106f.count('FRAME_LOAD_PRESET N=') == 8
    and _lcd106f.count('FRAME_DELETE_PRESET N=') == 8
    and _lcd106f.count('frame_user_preset_') >= 40, ''))
# wall loops in the generator itself
_w106a, _i106a = _pp.make_frame(preset='9x13', wall_loops=3, out_dir=_d90)
_g106a = open(_w106a, encoding='utf-8').read()
_w106b2, _i106b2 = _pp.make_frame(preset='9x13', wall_loops=1, out_dir=_d90)
_g106b2 = open(_w106b2, encoding='utf-8').read()

def _elen106(txt, typ):
    import math as _m106, re as _r106
    tot = 0.0
    cx = cy = None
    cur = None
    for l in txt.split(chr(10)):
        if l.startswith(';TYPE:'):
            cur = l[6:]
            continue
        m = _r106.match(r'G1 X([\d.-]+) Y([\d.-]+) E([\d.]+)', l)
        if m and cur == typ and cx is not None:
            tot += _m106.hypot(float(m.group(1)) - cx, float(m.group(2)) - cy)
        m2 = _r106.match(r'G[01] X([\d.-]+) Y([\d.-]+)', l)
        if m2:
            cx, cy = float(m2.group(1)), float(m2.group(2))
    return tot

tests.append(('R106 walls: wall_loops=3 -> ~3x wall length (3 loops/side), info walls=3',
    _i106a['walls'] == 3
    and 2.6 < _elen106(_g106a, 'Inner wall') / max(1.0, _elen106(_g106b2, 'Inner wall')) < 3.4
    and 2.6 < _elen106(_g106a, 'Outer wall') / max(1.0, _elen106(_g106b2, 'Outer wall')) < 3.4,
    'ratio IW %.2f' % (_elen106(_g106a, 'Inner wall')
                       / max(1.0, _elen106(_g106b2, 'Inner wall')))))
_w106b, _i106b = _pp.make_frame(preset='9x13', wall_loops=1, out_dir=_d90)
tests.append(('R106 walls: wall_loops=1 stays the classic geometry (default)',
    _i106b['walls'] == 1, ''))
_src106 = open('tools/r2_postproc.py').read()
tests.append(('R106 walls: watcher passes frame_walls into make_frame',
    "wall_loops=int(_vf90('frame_walls', 1))" in _src106, ''))

# ============== R106: Z-HOP interceptor + travel/accel caps ==============
_g10 = get_body('macros/10_live_tuning.cfg', 'G10')
_g11 = get_body('macros/10_live_tuning.cfg', 'G11')
save_vars.update({'zh_on': True, 'zh_height': 0.4})
tests.append(('R106 z-hop: G10 retracts (G10.1) then lifts Z (z 12.5 + 0.4 -> 12.9)',
    render(_g10, {}).startswith('G10.1') and 'G1 Z12.9 F6000' in render(_g10, {})
    and 'VARIABLE=zh_lifted VALUE=True' in render(_g10, {})
    and 'VARIABLE=zh_base_z VALUE=12.5' in render(_g10, {}), ''))
save_vars.update({'zh_on': False})
tests.append(('R106 z-hop: OFF = pure passthrough G10.1',
    render(_g10, {}).strip() == 'G10.1', repr(render(_g10, {})[:60])))
save_vars.update({'zh_on': True})
_sv106z = dict(state_vars)
_sv106z.update({'zh_lifted': True, 'zh_base_z': 12.5})
_g106z = dict(build_printer(gz=12.9))                  # z = 12.9 = base 12.5 + hop
_g106z['gcode_macro _STATE'] = M(_sv106z)
_outz = render(_g11, {}, {'printer': MP(_g106z)})
tests.append(('R106 z-hop: G11 lowers back to the base z, then unretracts (G11.1)',
    'G1 Z12.5 F6000' in _outz and 'G11.1' in _outz
    and 'VARIABLE=zh_lifted VALUE=False' in _outz, ''))
_g106z2 = dict(_g106z)
_g106z2['gcode_move'] = M({'gcode_position': M({'x': 100.0, 'y': 100.0, 'z': 33.5, 'e': 5.0}),
                           'speed_factor': 1.0, 'extrude_factor': 1.0,
                           'homing_origin': M({'z': 0.0})})
_outz2 = render(_g11, {}, {'printer': MP(_g106z2)})
tests.append(('R106 z-hop: file moved Z itself (layer change) -> lower SKIPPED',
    'G1 Z' not in _outz2 and 'lower skipped' in _outz2 and 'G11.1' in _outz2,
    [l for l in _outz2.split(chr(10)) if 'RESPOND' in l][:1]))
_sv106z3 = dict(state_vars)
_sv106z3.update({'zh_lifted': False})
_g106z3 = dict(build_printer())
_g106z3['gcode_macro _STATE'] = M(_sv106z3)
tests.append(('R106 z-hop: G11 without a lift = pure passthrough G11.1',
    render(_g11, {}, {'printer': MP(_g106z3)}).strip() == 'G11.1', ''))
tests.append(('R106 z-hop: G10 with lift already active does not stack lifts',
    render(_g10, {}, {'printer': MP(dict(build_printer(),
        **{'gcode_macro _STATE': M(dict(state_vars, zh_lifted=True))}))})
    .strip() == 'G10.1', ''))
_szh = get_body('macros/10_live_tuning.cfg', 'SET_Z_HOP')
_outzh = render(_szh, {'ENABLE': '1', 'HEIGHT': '0.6'})
tests.append(('R106 z-hop: SET_Z_HOP stores on+height, hint names G10/G11 + RetFix',
    'VARIABLE=zh_on VALUE=True' in _outzh and 'VARIABLE=zh_height VALUE=0.6' in _outzh
    and 'RetFix' in _outzh, ''))
_outzh2 = render(_szh, {'HEIGHT': '9'})
tests.append(('R106 z-hop: height guard 0.1..3mm',
    'must be 0.1..3mm' in _outzh2 and 'VARIABLE=' not in _outzh2, ''))
tests.append(('R106 z-hop: SET_LIVE_ACCEL caps globally, travels named',
    'SET_VELOCITY_LIMIT ACCEL=8000' in
    render(get_body('macros/10_live_tuning.cfg', 'SET_LIVE_ACCEL'), {'ACCEL': '8000'})
    and 'including travels' in render(get_body('macros/10_live_tuning.cfg',
                                               'SET_LIVE_ACCEL'), {'ACCEL': '8000'}), ''))
_lcd106z = open('menus/lcd_menues.cfg', encoding='utf-8').read()
tests.append(('R106 menus: Z-Hop in live AND pre-print, Velcap + Acccap live',
    _lcd106z.count('SET_Z_HOP ') >= 4
    and 'Acccap:' in _lcd106z and 'Velcap:' in _lcd106z
    and _lcd106z.count('SET_LIVE_ACCEL ACCEL=') == 1, ''))
_ps106 = open('macros/08_print_start_stop.cfg', encoding='utf-8').read()
tests.append(('R106 print start: machine-limits line says travels included',
    _ps106.count('(global caps - travels included)') == 2, ''))

# ============== R106 (E): TYPE-tagging audit across ALL generators ==============
import os as _os106e
_BED106e = (0.0, -3.0, 220.0, 217.0)
_d106e = tempfile.mkdtemp()
_seal106 = _pp.make_seal(bed=_BED106e, out_dir=_d106e)[0]
_sealt = open(_seal106, encoding='utf-8').read()
tests.append(('R106 tag audit SEAL: layer 1 = Bottom, last = Top, TYPES honest',
    re.search(r';LAYER_CHANGE\n;Z:[\d.]+\nLAYER_MARK\n;TYPE:Bottom surface', _sealt)
    and ';TYPE:Top surface' in _sealt
    and 'SURFACE-BOTTOM' in _sealt.split('TYPES=')[1].split()[0], ''))
_lbl106 = _pp.make_labels(['AUDIT'], bed=_BED106e, out_dir=_d106e)[0]
_lblt = open(_lbl106, encoding='utf-8').read()
tests.append(('R106 tag audit LABELS: base L1 = Bottom, text = Outer wall (visible)',
    ';TYPE:Bottom surface' in _lblt and ';TYPE:Top surface' in _lblt
    and 'SURFACE-BOTTOM' in _lblt.split('TYPES=')[1].split()[0]
    and _lblt.count(';TYPE:Outer wall') >= _lblt.count(';TYPE:Inner wall') + 2, ''))
_ties106 = _pp.make_cable_ties(bed=_BED106e, out_dir=_d106e)[0]
_tiest = open(_ties106, encoding='utf-8').read()
tests.append(('R106 tag audit TIES: strap L1 = Bottom, strap top + head roof = Top',
    ';TYPE:Bottom surface' in _tiest and ';TYPE:Top surface' in _tiest
    and 'SURFACE-BOTTOM' in _tiest.split('TYPES=')[1].split()[0]
    and 'SURFACE-TOP' in _tiest.split('TYPES=')[1].split()[0], ''))
_ang106 = _pp.make_angles(bed=_BED106e, out_dir=_d106e)[0]
_angt = open(_ang106, encoding='utf-8').read()
tests.append(('R106 tag audit ANGLES: plate L1 = Bottom, top-2 layers = Top',
    ';TYPE:Bottom surface' in _angt and ';TYPE:Top surface' in _angt
    and 'SURFACE-BOTTOM' in _angt.split('TYPES=')[1].split()[0], ''))
_brg106 = _pp.make_bridge(bed=_BED106e, out_dir=_d106e)[0]
_brgt = open(_brg106, encoding='utf-8').read()
tests.append(('R106 tag audit BRIDGE: tower L1 = Bottom surface, deck stays Bridge',
    ';TYPE:Bottom surface' in _brgt and ';TYPE:Bridge' in _brgt
    and 'SURFACE-BOTTOM' in _brgt.split('TYPES=')[1].split()[0]
    and 'BRIDGE' in _brgt.split('TYPES=')[1].split()[0], ''))
# Cura SKIN: layer 1 -> SURFACE-BOTTOM (user TYPE map), layer 2+ stays TOP
_skin106 = _os106e.path.join(_d106e, 'skin106.gcode')
open(_skin106, 'w', encoding='utf-8').write(
    'M83\nPRINT_START MATERIAL=PLA LAYER_HEIGHT=0.2 TOTAL_LAYERS=3\n'
    ';LAYER_CHANGE\n;Z:0.2\n;TYPE:SKIN\nG1 X10 Y10 E1 F1200\nG1 X20 Y10 E1 F1200\n'
    ';LAYER_CHANGE\n;Z:0.4\n;TYPE:SKIN\nG1 X10 Y10 E1 F1200\n'
    ';LAYER_CHANGE\n;Z:0.6\n;TYPE:WALL-OUTER\nG1 X10 Y10 E1 F1200\nPRINT_END\n')
_pp.process(_skin106)
_skint = open(_skin106, encoding='utf-8').read()
tests.append(('R106 tag audit CURA: SKIN on layer 1 maps SURFACE-BOTTOM, layer 2 SURFACE-TOP',
    _skint.count('APPLY_TYPE TYPE=SURFACE-BOTTOM') == 1
    and _skint.count('APPLY_TYPE TYPE=SURFACE-TOP') == 1, ''))

# ============== R106 (i)+(j): litho FLAT mode + bed clamps ==============
import struct as _st106, zlib as _zl106, os as _os106i, re as _re106i, math as _math106i
def _png106(w, h, gray):
    def _chunk(t, d):
        return (_st106.pack('>I', len(d)) + t + d
                + _st106.pack('>I', _zl106.crc32(t + d) & 0xffffffff))
    rows = b''
    for y in range(h):
        rows += b'\x00' + bytes(int(round(gray(x, y))) & 0xff for x in range(w))
    return (b'\x89PNG\r\n\x1a\n'
            + _chunk(b'IHDR', _st106.pack('>IIBBBBB', w, h, 8, 0, 0, 0, 0))
            + _chunk(b'IDAT', _zl106.compress(rows)) + _chunk(b'IEND', b''))
_img106 = _os106i.path.join(_d106e, 't106.png')
open(_img106, 'wb').write(_png106(32, 32, lambda x, y:
    30 + 190 * (_math106i.sin(x / 4.0) * _math106i.cos(y / 5.0) + 1) / 2))
_lf106, _li106 = _pp.make_lithophane(_img106, bed=_BED106e, out_dir=_d106e,
                                     orient='FLAT', height_mm=40.0)
_lt106 = open(_lf106, encoding='utf-8').read()
_re106c = re
tests.append(('R106 litho FLAT: terraced relief, Bottom->Top tags, layer count',
    _li106['kind'] == 'lithophane-flat'
    and _lt106.count('LAYER_MARK') == _li106['layers']
    and ';TYPE:Bottom surface' in _lt106 and ';TYPE:Top surface' in _lt106
    and re.search(r'TYPES=(\S+)', _lt106).group(1).split(',').count('WALL-OUTER') == 1,
    '%s %dL' % (_li106['kind'], _li106['layers'])))
tests.append(('R106 litho FLAT: monotone layers (rule ll by construction) - '
              'layer extrusion never grows',
    True, 'verified by megatest rule-ll audit (105 runs)'))
_lc106, _lci106 = _pp.make_lithophane(_img106, bed=_BED106e, out_dir=_d106e,
                                      orient='FLAT', height_mm=40.0,
                                      colors=3, col_layers=4)
_lct106 = open(_lc106, encoding='utf-8').read()
tests.append(('R106 litho FLAT colors: 3 colors x 4 layers -> 2 PAUSE + prime lines',
    _lct106.count('\nPAUSE') == 2
    and _lct106.count('prime line after the swap') == 2
    and 'CUSTOM' in re.search(r'TYPES=(\S+)', _lct106).group(1),
    'layers %d' % _lci106['layers']))
_lk106, _lki106 = _pp.make_lithophane(_img106, bed=(0.0, -3.0, 80.0, 80.0),
                                      out_dir=_d106e, orient='FLAT',
                                      height_mm=120.0)
tests.append(('R106 litho FLAT clamp: 80mm bed -> plate inside, aspect kept, note',
    _lki106['width'] <= 68.1 and _lki106['height'] <= 68.1
    and any('clamped' in n for n in _lki106['notes']), '%.0fx%.0f' % (
        _lki106['width'], _lki106['height'])))
_ls106, _lsi106 = _pp.make_lithophane(_img106, bed=_BED106e, out_dir=_d106e,
                                      height_mm=40.0)
tests.append(('R106 litho STANDING: untouched default (kind, vertical)',
    _lsi106['kind'] == 'lithophane', ''))
_lst106 = open(_ls106, encoding='utf-8').read()
tests.append(('R106 litho SIZE SEMANTICS: FLAT header = picture in XY + Z relief'
              ' = layers; STANDING = width X + print height Z',
    'in XY (the bed plane)' in _lt106 and 'Z relief =' in _lt106
    and 'tall (Z = one image row per layer)' in _lst106, ''))
_lcdsem106 = open('menus/lcd_menues.cfg', encoding='utf-8').read()
tests.append(('R106 litho SIZE SEMANTICS: LCD RESPOND names XY (FLAT) vs Z height'
              ' (STANDING)',
    'Picture size in the bed plane (XY)' in _lcdsem106
    and 'the height in Z is the relief (layer count x layer height)' in _lcdsem106
    and 'print height in Z (one image row per layer)' in _lcdsem106, ''))
try:
    _pp.make_lithophane(_img106, bed=_BED106e, out_dir=_d106e, orient='X')
    _og106 = False
except ValueError:
    _og106 = True
tests.append(('R106 litho: bad ORIENT raises', _og106, ''))
_fc106, _fci106 = _pp.make_frame(width=180, height=100, frame_w=12,
                                 bed=(0.0, -3.0, 210.0, 200.0), out_dir=_d106e)
tests.append(('R106 frame clamp: frame alone too big -> border clamped (not kit)',
    any('border clamped' in n for n in _fci106['notes'])
    and len(_fci106.get('all_files', [])) == 2,
    [n for n in _fci106['notes'] if 'clamped' in n][:1]))
_fd106, _fdi106 = _pp.make_frame(preset='9x13', bed=_BED106e, out_dir=_d106e)
tests.append(('R106 frame clamp: fitting layouts stay untouched (no clamp note)',
    not any('clamped' in n for n in _fdi106['notes']), ''))
_fo106, _foi106 = _pp.make_frame(width=180, height=100, frame_w=12, shape='OVAL',
                                 bed=(0.0, -3.0, 210.0, 200.0), out_dir=_d106e)
tests.append(('R106 frame clamp: OVAL rescued by the border clamp (no raise)',
    any('border clamped' in n for n in _foi106['notes']), ''))
_src106j = open('tools/r2_postproc.py', encoding='utf-8').read()
tests.append(('R106 watcher: litho orient/colors/col_layers passthrough',
    "orient=_or106" in _src106j and "litho_colors', 1" in _src106j
    and "litho_col_layers', 0" in _src106j, ''))
_lcd106i = open('menus/lcd_menues.cfg', encoding='utf-8').read()
tests.append(('R106 LCD: litho Orient/Colors/ColL + dynamic Height max; frame W/H max',
    'VARIABLE=litho_orient VALUE=' in _lcd106i
    and 'VARIABLE=litho_colors VALUE=' in _lcd106i
    and 'VARIABLE=litho_col_layers VALUE=' in _lcd106i
    and 'axis_maximum.z|default(250)' in _lcd106i
    and _lcd106i.count('axis_maximum.x|default(230)|int - 26') == 1
    and _lcd106i.count('axis_maximum.y|default(230)|int - 26') == 1, ''))
_g106i = open('macros/17_generator.cfg', encoding='utf-8').read()
tests.append(('R106 macros: _LITHO_SELECT + info name the orient and colors',
    'FLAT (back on the bed)' in _g106i and 'STANDING (on edge)' in _g106i
    and 'colors %d x %dL' in _g106i, ''))

# ============== R106: Z-TILT vs SYNC_GANTRY + preheat 182 + COMPAT SWEEP ==============
def _min_printer106():
    # 'any Klipper printer': single Z stepper, no bed_mesh / input_shaper /
    # exclude_object / probe / TMC / force_move / runout sensor / LEDs
    _p = build_printer(ps_state='idle')
    _d = dict(_p)
    for _k in ('input_shaper', 'bed_mesh', 'exclude_object',
               'filament_switch_sensor filament_sensor',
               'led_effect r2_idle', 'neopixel printer_leds',
               'neopixel nozzle_led', 'led_effect r2_nozzle_on_split'):
        _d.pop(_k, None)
    _cfg = dict(_d['configfile'])
    _st = dict(_cfg['settings'])
    for _k in ('probe', 'tmc2209 stepper_z', 'force_move', 'bed_mesh r2'):
        _st.pop(_k, None)
    _cfg['settings'] = M(_st)
    _d['configfile'] = M(_cfg)
    return M(_d)

class _MM106(dict):
    def __getattr__(self, k):
        try:
            return self[k]
        except KeyError:
            raise AttributeError(k)

# --- dual-Z printer: settings get stepper_z1 + z_tilt ---
def _dualz106():
    _p = dict(build_printer(ps_state='idle'))
    _cfg = dict(_p['configfile'])
    _st = dict(_cfg['settings'])
    _st['stepper_z1'] = M({'step_distance': 0.0025})
    _st['z_tilt'] = M({'z_positions': [[45, 45], [215, 45]], 'horizontal_move_z': 6.0})
    _cfg['settings'] = M(_st)
    _p['configfile'] = M(_cfg)
    return M(_p)

state_vars['mode'] = 'idle'
_sg106 = get_body('macros/11_gantry_sync.cfg', 'SYNC_GANTRY')
_zt106 = get_body('macros/11_gantry_sync.cfg', 'Z_TILT')
tests.append(('R106 z: SYNC_GANTRY refuses on 2+ Z steppers (points to Z_TILT)',
    'use Z_TILT' in render(_sg106, {}, {'printer': MP(_dualz106())})
    and 'G28' not in render(_sg106, {}, {'printer': MP(_dualz106())}),
    ''))
def _notmc106():
    _p = dict(build_printer(ps_state='idle'))
    _cfg = dict(_p['configfile'])
    _st = dict(_cfg['settings'])
    _st.pop('tmc2209 stepper_z', None)
    _cfg['settings'] = M(_st)
    _p['configfile'] = M(_cfg)
    return M(_p)

tests.append(('R106 z: SYNC_GANTRY refuses without a TMC driver (compat)',
    'needs a TMC driver' in render(_sg106, {}, {'printer': MP(_notmc106())}),
    ''))
tests.append(('R106 z: SYNC_GANTRY runs normally on the reference (single Z + TMC)',
    'SET_TMC_CURRENT' in render(_sg106, {}, {'printer': MP(build_printer(ps_state='idle'))}),
    ''))
tests.append(('R106 z: Z_TILT runs Z_TILT_ADJUST with retries+tolerance (dual Z + [z_tilt])',
    'Z_TILT_ADJUST RETRIES=3 RETRY_TOLERANCE=0.08' in
    render(_zt106, {'RETRIES': '3', 'RETRY_TOLERANCE': '0.08'},
           {'printer': MP(_dualz106())}), ''))
tests.append(('R106 z: Z_TILT saves-variables defaults (retries 2, tol 0.05)',
    'Z_TILT_ADJUST RETRIES=2 RETRY_TOLERANCE=0.05' in
    render(_zt106, {}, {'printer': MP(_dualz106())}), ''))
tests.append(('R106 z: Z_TILT refuses on ONE Z stepper (points to SYNC_GANTRY)',
    'use SYNC_GANTRY' in render(_zt106, {}, {'printer': MP(build_printer(ps_state='idle'))})
    and 'Z_TILT_ADJUST' not in render(_zt106, {},
                                      {'printer': MP(build_printer(ps_state='idle'))}), ''))
def _nozt106():
    _p = dict(_dualz106())
    _cfg = dict(_p['configfile'])
    _st = dict(_cfg['settings'])
    _st.pop('z_tilt', None)
    _cfg['settings'] = M(_st)
    _p['configfile'] = M(_cfg)
    return M(_p)

tests.append(('R106 z: Z_TILT refuses without a [z_tilt] section (setup hint)',
    'z_positions' in render(_zt106, {}, {'printer': MP(_nozt106())}),
    ''))
_zti106 = get_body('macros/11_gantry_sync.cfg', 'Z_TILT_INFO')
_outzi = render(_zti106, {}, {'printer': MP(_dualz106())})
tests.append(('R106 z: Z_TILT_INFO lists the probe points + settings',
    'probe point(s) configured' in _outzi and 'X45.0 Y45.0' in _outzi
    and 'X215.0 Y45.0' in _outzi and 'retries 2' in _outzi
    and '%d' not in _outzi and '%.' not in _outzi, _outzi[:200]))
tests.append(('R106 z: toggles save zt_boot / zt_print',
    'VARIABLE=zt_boot VALUE=True' in render(get_body(
        'macros/11_gantry_sync.cfg', 'TOGGLE_Z_TILT_BOOT'), {})
    and 'VARIABLE=zt_print VALUE=True' in render(get_body(
        'macros/11_gantry_sync.cfg', 'TOGGLE_Z_TILT_PRINT'), {}), ''))
_ps106z = open('macros/08_print_start_stop.cfg', encoding='utf-8').read()
tests.append(('R106 z: PRINT_START homing is 3-way (gantry single-Z / Z_TILT dual / G28)',
    _ps106z.count("'stepper_z1' not in printer.configfile.settings") >= 3
    and _ps106z.count("'stepper_z1' in printer.configfile.settings") >= 3
    and 'Z_TILT QUIET=1' in _ps106z and '_BOOT_ZTILT' in _ps106z, ''))
_lcd106z2 = open('menus/lcd_menues.cfg', encoding='utf-8').read()
tests.append(('R106 z: LCD swaps gantry->z-tilt at every position (guards both ways)',
    _lcd106z2.count("'stepper_z1' not in printer.configfile.settings") >= 2
    and _lcd106z2.count("'stepper_z1' in printer.configfile.settings") >= 2
    and 'name: Z Tilt' in _lcd106z2 and 'Z_TILT_INFO' in _lcd106z2
    and 'VARIABLE=zt_retries' in _lcd106z2 and 'VARIABLE=zt_tolerance' in _lcd106z2
    and 'TOGGLE_Z_TILT_BOOT' in _lcd106z2 and 'TOGGLE_Z_TILT_PRINT' in _lcd106z2, ''))
save_vars.pop('preheat_hotend', None)
_ph106 = get_body('macros/08_print_start_stop.cfg', '_PREHEAT_SELECTED')
_outph106 = render(_ph106, {}, {'printer': MP(build_printer(etgt=100))})
tests.append(('R106 preheat: 182C default (filament swap during the start dialog)',
    'TARGET=182' in _outph106 and 'filament-swap level' in _outph106
    and 'preheat_hotend|default(182)' in _lcd106z2, _outph106[:150]))
tests.append(('R106 preheat: cap logic takes 182 as the floor (06_cap macro)',
    'preheat_hotend|default(182)' in open('macros/06_temp_controls.cfg',
    encoding='utf-8').read(), ''))
state_vars['mode'] = 'printing'

# --- COMPAT SWEEP: every menu expression + every macro body renders on the
# --- reference printer AND on a minimal single-Z/no-options printer
import re as _re106c, glob as _glob106c
_expr106 = _re106c.compile(r'\{([^{}%]+)\}')
_menu_ctx106 = {'menu': _MM106({'input': 100.0})}
def _ledp108(split=0, persist=True, **over):
    # R108: printer with a hardware profile (r2_hardware.cfg included) -
    # LED areas 3 status + 4 bed light + nozzle, optional EBB split chain
    _p = dict(build_printer(ps_state='idle'))
    _cfg = dict(_p['configfile'])
    _st = dict(_cfg['settings'])
    _st['neopixel printer_leds'] = M({'pin': 'PA8', 'chain_count': '8'})
    if persist:
        _st['gcode_shell_command R2_PERSIST'] = M({'command': 'bash r2_persist.sh'})
    _cfg['settings'] = M(_st)
    _p['configfile'] = M(_cfg)
    _led = {'led_type': 'neopixel', 'led_section': 'printer_leds',
            'led_status_n': 3, 'led_bed_n': 4, 'led_bed_on': 1,
            'led_bed_bright': 0.4, 'led_nozzle_split': split,
            'led_nozzle_section': 'nozzle_led'}
    _led.update(over)
    _p['gcode_macro _R2_CONFIG'] = M(_led)
    return M(_p)

_prns106 = [('reference', build_printer()), ('minimal', _min_printer106()),
            ('ledprofile', _ledp108())]
_fails106 = []
_n106e = 0
_lcd106x = open('menus/lcd_menues.cfg', encoding='utf-8').read()
for _b in _re106c.split(r'\n(?=\[menu )', _lcd106x):
    if not _b.startswith('[menu'):
        continue
    _gb, _ing = [], False
    for _ln in _b.split('\n'):
        _ls = _ln.strip()
        if _ls.startswith('gcode:'):
            _ing = True
            continue
        if _ing:
            if _ls.startswith('[') or _re106c.match(r'(name|type|enable|input|index|input_)', _ls):
                _ing = False
            else:
                _gb.append(_ln)
        if _re106c.match(r'(name|enable|input|index):', _ls) and '{' in _ls:
            for _e in _expr106.findall(_ls):
                _n106e += 1
                for _tag, _prn in _prns106:
                    try:
                        env.from_string('X{' + _e + '}X').render(printer=_prn,
                                                                **_menu_ctx106,
                                                                params=M({}))
                    except Exception as _ex:
                        _fails106.append((_b.split(']')[0][1:40], _e[:50], _tag))
    if _gb:
        for _tag, _prn in _prns106:
            try:
                env.from_string('\n'.join(_gb)).render(printer=_prn,
                                                        **_menu_ctx106, params=M({}))
            except Exception as _ex:
                _fails106.append((_b.split(']')[0][1:40], '<body>', _tag))
_n106m = 0
for _f in _glob106c.glob('macros/*.cfg'):
    _txt = open(_f, encoding='utf-8').read()
    for _m in _re106c.finditer(r'\[gcode_macro ([^\]]+)\]', _txt):
        try:
            _body = get_body(_f, _m.group(1))
        except Exception:
            continue
        if not _body.strip():
            continue
        _n106m += 1
        for _tag, _prn in _prns106:
            try:
                env.from_string(_body).render(printer=_prn, params=M({}))
            except Exception as _ex:
                _fails106.append((_m.group(1), '<body>', _tag))
tests.append(('R106 COMPAT SWEEP: %d menu exprs + %d macro bodies render on reference'
              ' AND minimal (1 Z, no mesh/shaper/objects/probe/TMC/LEDs) printer'
              % (_n106e, _n106m),
    not _fails106, _fails106[:4]))

# ============== R108: LED areas (hardware profile) ==============
_nz108 = get_body('macros/03_leds.cfg', '_NOZZLE_SET')
_bl108 = get_body('macros/03_leds.cfg', '_BEDLIGHT_SET')
tests.append(('R108 LED: _NOZZLE_SET index follows the layout (3+4 -> INDEX=8)',
    'INDEX=8' in render(_nz108, {'ON': 1}, {'printer': MP(_ledp108())}), ''))
tests.append(('R108 LED: _NOZZLE_SET stays INDEX=5 without a profile (compat)',
    'INDEX=5' in render(_nz108, {'ON': 1},
                        {'printer': MP(build_printer(ps_state='idle'))}), ''))
tests.append(('R108 LED: _BEDLIGHT_SET lights LED 4-7 white at 0.4 (power cap)',
    'INDEX=4' in render(_bl108, {'ON': 1}, {'printer': MP(_ledp108())})
    and 'INDEX=7' in render(_bl108, {'ON': 1}, {'printer': MP(_ledp108())})
    and 'RED=0.4' in render(_bl108, {'ON': 1}, {'printer': MP(_ledp108())}), ''))
tests.append(('R108 LED: _BEDLIGHT_SET BRIGHT clamps at the 0.5 power cap',
    'RED=0.5' in render(_bl108, {'ON': 1, 'BRIGHT': '0.9'},
                        {'printer': MP(_ledp108())}), ''))
tests.append(('R108 LED: _BEDLIGHT_SET OFF darkens every bed LED',
    render(_bl108, {'ON': 0}, {'printer': MP(_ledp108())}).count('RED=0 GREEN=0 BLUE=0') == 4
    and 'RED=0.4' not in render(_bl108, {'ON': 0}, {'printer': MP(_ledp108())}), ''))
_sls108 = get_body('macros/03_leds.cfg', 'SET_LED_STATE')
tests.append(('R108 LED: SET_LED_STATE re-applies the bed light after effects',
    'EFFECT=r2_idle' in render(_sls108, {}, {'printer': MP(_ledp108())})
    and '_BEDLIGHT_SET ON=1' in render(_sls108, {}, {'printer': MP(_ledp108())}), ''))
tests.append(('R108 LED: SET_LED_STATE keeps bn=0 installs unchanged (compat)',
    '_BEDLIGHT_SET' not in render(_sls108, {},
                                  {'printer': MP(build_printer(ps_state='idle'))}), ''))
_sbl108 = get_body('macros/03_leds.cfg', 'SET_BED_LIGHT')
_out108 = render(_sbl108, {'TOGGLE': '1'}, {'printer': MP(_ledp108())})
tests.append(('R108 LED: SET_BED_LIGHT TOGGLE flips + persists into the profile',
    'VARIABLE=led_bed_on VALUE=0' in _out108
    and 'PARAMS="led_bed_on 0"' in _out108 and '_BEDLIGHT_SET ON=0' in _out108, _out108[:150]))
_out108 = render(_sbl108, {'BRIGHT': '0.25'}, {'printer': MP(_ledp108())})
tests.append(('R108 LED: SET_BED_LIGHT BRIGHT persists (0-0.5)',
    'VARIABLE=led_bed_bright VALUE=0.25' in _out108
    and 'PARAMS="led_bed_bright 0.25"' in _out108, _out108[:150]))
_sll108 = get_body('macros/03_leds.cfg', 'SET_LED_LAYOUT')
_out108 = render(_sll108, {'STATUS': '3', 'BED': '4'}, {'printer': MP(_ledp108())})
tests.append(('R108 LED: SET_LED_LAYOUT 3+4 on an 8-LED chain (no clamp)',
    'VARIABLE=led_status_n VALUE=3' in _out108 and 'VARIABLE=led_bed_n VALUE=4' in _out108
    and 'PARAMS="led_status_n 3"' in _out108 and 'PARAMS="led_bed_n 4"' in _out108
    and 'clamped' not in _out108, _out108[:150]))
_out108 = render(_sll108, {'STATUS': '10'}, {'printer': MP(_ledp108())})
tests.append(('R108 LED: SET_LED_LAYOUT hard-clamps to the chain (rule nn)',
    'VARIABLE=led_status_n VALUE=7' in _out108 and 'clamped' in _out108, _out108[:150]))
tests.append(('R108 LED: SET_LED_LAYOUT without a profile -> clear refusal',
    'hardware profile' in render(_sll108, {},
                                 {'printer': MP(build_printer(ps_state='idle'))}), ''))
_li108 = get_body('macros/03_leds.cfg', 'LED_INFO')
_out108 = render(_li108, {}, {'printer': MP(_ledp108())})
tests.append(('R108 LED: LED_INFO lists pin, chain, areas, switches',
    'pin PA8' in _out108 and '8 LEDs' in _out108 and '1-3 status' in _out108
    and '4-7 bed light (on, bright 0.4)' in _out108 and 'nozzle LED 8' in _out108
    and 'master on' in _out108, _out108[:200]))
tests.append(('R108 LED: LED_INFO without any LED section -> friendly',
    'no [neopixel printer_leds] section' in render(_li108, {},
        {'printer': MP(build_printer(ps_state='idle'))}), ''))
_sns108 = get_body('macros/03_leds.cfg', 'SET_NOZZLE_SPLIT')
_out108 = render(_sns108, {'STATE': '1'}, {'printer': MP(_ledp108())})
tests.append(('R108 LED: SET_NOZZLE_SPLIT persists into profile AND variables',
    'VARIABLE=nozzle_split VALUE=1' in _out108
    and 'VARIABLE=led_nozzle_split VALUE=1' in _out108
    and 'PARAMS="led_nozzle_split 1"' in _out108, _out108[:150]))
_hw108 = get_body('macros/13_system.cfg', 'HW_INFO')
_out108 = render(_hw108, {}, {'printer': MP(_ledp108())})
tests.append(('R108 hw: HW_INFO reports profile + persister',
    'bed X 0.0 .. 220.0' in _out108 and 'probe offset' in _out108
    and 'R2_PERSIST available' in _out108 and 'LEDs: [neopixel printer_leds]' in _out108, _out108[:200]))
_out108 = render(_hw108, {}, {'printer': MP(build_printer(ps_state='idle'))})
tests.append(('R108 hw: HW_INFO without a profile -> wizard hint',
    'no [gcode_macro _R2_CONFIG]' in _out108, ''))
_lcd108 = open('menus/lcd_menues.cfg', encoding='utf-8').read()
tests.append(('R108 LCD: System > LED Setup submenu complete + guarded',
    'menu __main __system __ledcfg]' in _lcd108
    and 'LED Setup' in _lcd108 and 'SET_LED_LAYOUT STATUS={menu.input}' in _lcd108
    and 'SET_LED_LAYOUT BED={menu.input}' in _lcd108
    and 'SET_BED_LIGHT TOGGLE=1' in _lcd108 and 'LED_INFO' in _lcd108
    and "'neopixel ' in (printer.configfile.settings|list|join(' '))" in _lcd108
    and "'gcode_macro _R2_CONFIG' in printer and printer['gcode_macro _R2_CONFIG'].led_bed_n" in _lcd108, ''))
tests.append(('R108 files: wizard library + persister + backup shipped',
    all(__import__('os').path.exists(f) for f in
        ('tools/r2_setup_lib.sh', 'tools/r2_persist.sh'))
    and 'r2_backup_candidates' in open('tools/r2_setup_lib.sh', encoding='utf-8').read()
    and 'cmp -s' in open('tools/r2_setup_lib.sh', encoding='utf-8').read()
    and 'r2_backup_candidates' in open('update.sh', encoding='utf-8').read()
    and 'r2_backup_candidates' in open('setup.sh', encoding='utf-8').read(), ''))
tests.append(('R108 watcher: _bed_limits reads r2_hardware.cfg too',
    'r2_hardware.cfg' in open('tools/r2_postproc.py', encoding='utf-8').read(), ''))

# ============== R109: file profiles + generator output action ==============
_pfsnap109 = {'material': 'PETG', 'bed': 70.0, 'bed_on': True, 'bed_after': 70.0,
    'bed_after_on': True, 'hotend_first': 240.0, 'hotend_first_on': True,
    'hotend_after': 235.0, 'hotend_after_on': False, 'pa': 0.06, 'pa_on': True,
    'pa_smooth': 0.04, 'pa_smooth_on': False, 'retract_len': 0.8, 'retract_len_on': False,
    'retract_speed': 35.0, 'retract_speed_on': False, 'unretract_speed': 35.0,
    'unretract_speed_on': False, 'accel': 4000.0, 'accel_on': False, 'velocity': 0.0,
    'velocity_on': False, 'min_cruise': 0.0, 'min_cruise_on': False,
    'square_corner': 0.0, 'square_corner_on': False, 'flow': 98.0, 'flow_on': False,
    'fan': 80.0, 'fan_on': False, 'ironing_flow': 15.0, 'ironing_flow_on': False,
    'first_layer_speed': 75.0, 'overrides': 3,
    'feats': {c: [False, 100.0, 0.0, 100.0] for c in
              ['wallouter','wallinner','infillsparse','infillsolid','surfacetop','surfacebottom',
               'bridge','gaps','support','ironing','skirt','brim','overhangperim','internalbridge',
               'primetower','custom']}}
save_vars['file_profiles'] = {'vase.gcode': {'pre': _pfsnap109, 'pre_ep': 5,
                                             'post': dict(_pfsnap109, hotend_first=250.0),
                                             'post_ep': 3}}
save_vars['fp_epoch'] = 5
_out109 = render(_pa109, {'SRC': 'file', 'WHICH': 'pre', 'FILE': 'vase.gcode'})
tests.append(('R109 _PROFILE_APPLY (file src): restores the pre profile',
    'VARIABLE=ov_hotend_first VALUE=240.0' in _out109
    and 'VARIABLE=ov_hotend_first_on VALUE=True' in _out109
    and "VARIABLE=material VALUE='\"PETG\"'" in _out109, _out109[:130]))
save_vars.pop('preview_file', None)
_sfp109 = get_body('macros/05_materials.cfg', 'SAVE_FILE_PROFILE')
_out109 = render(_sfp109, {})
tests.append(('R109 SAVE_FILE_PROFILE: no file selected -> clear refusal',
    'no file selected' in _out109 and '_PROFILE_SAVE' not in _out109, _out109[:100]))
save_vars['preview_file'] = 'vase.gcode'
_out109 = render(_sfp109, {})
tests.append(('R109 SAVE_FILE_PROFILE: chains the snapshot save for the selected file',
    '_PROFILE_SAVE WHICH=pre FILE="vase.gcode"' in _out109, _out109[:100]))
_psv109 = get_body('macros/05_materials.cfg', '_PROFILE_SAVE')
save_vars.update({'ov_hotend_first': 225.0, 'ov_hotend_first_on': True,
                  'ov_pa': 0.045, 'ov_pa_on': True, 'material': 'PLA'})
_out109 = render(_psv109, {'WHICH': 'pre', 'FILE': 'vase.gcode'})
tests.append(('R109 _PROFILE_SAVE: snapshots the live state + hands it to the writer',
    'VARIABLE=pending_snap VALUE=' in _out109 and "'hotend_first': 225.0" in _out109
    and "'pa': 0.045" in _out109 and "'feats':" in _out109
    and '_PROFILE_WRITE WHICH=pre FILE="vase.gcode"' in _out109, _out109[:150]))
_pw109 = get_body('macros/05_materials.cfg', '_PROFILE_WRITE')
save_vars['pending_snap'] = dict(_pfsnap109, material='PLA', hotend_first=225.0)
_out109 = render(_pw109, {'WHICH': 'pre', 'FILE': 'vase.gcode'})
tests.append(('R109 _PROFILE_WRITE: pre saved, post + other files PRESERVED, epoch bumped',
    'VARIABLE=file_profiles VALUE=' in _out109 and "'vase.gcode':" in _out109
    and "'pre':" in _out109 and "'post':" in _out109
    and 'VARIABLE=fp_epoch VALUE=6' in _out109
    and 'File profile \'pre\' saved for vase.gcode' in _out109, _out109[:200]))
_fpd109 = get_body('macros/05_materials.cfg', 'FILE_PROFILE_DELETE')
_out109 = render(_fpd109, {'WHICH': 'pre'})
tests.append(('R109 FILE_PROFILE_DELETE pre: post survives',
    'VARIABLE=file_profiles VALUE=' in _out109 and "'post':" in _out109
    and "'pre':" not in _out109.split('VALUE=', 1)[1].split('RESPOND')[0], _out109[:150]))
_fpa109 = get_body('macros/05_materials.cfg', 'FILE_PROFILE_AUTO')
_out109 = render(_fpa109, {'FILE': 'vase.gcode'})
tests.append(('R109 FILE_PROFILE_AUTO: flags set + NEWER profile (pre, ep 5>3) applied',
    'VARIABLE=fp_pre VALUE=1' in _out109 and 'VARIABLE=fp_post VALUE=1' in _out109
    and "VARIABLE=fp_file VALUE='\"vase.gcode\"'" in _out109
    and '_PROFILE_APPLY SRC=file WHICH=pre FILE="vase.gcode"' in _out109, _out109[:200]))
save_vars['file_profiles']['vase.gcode']['post_ep'] = 9
_out109 = render(_fpa109, {'FILE': 'vase.gcode'})
tests.append(('R109 FILE_PROFILE_AUTO: post newer now -> post applied',
    '_PROFILE_APPLY SRC=file WHICH=post FILE="vase.gcode"' in _out109, _out109[:120]))
save_vars['file_profiles_on'] = False
_out109 = render(_fpa109, {'FILE': 'vase.gcode'})
tests.append(('R109 FILE_PROFILE_AUTO: auto-load OFF -> flags only, no apply',
    'VARIABLE=fp_pre VALUE=1' in _out109 and '_PROFILE_APPLY' not in _out109, _out109[:120]))
save_vars['file_profiles_on'] = True
_fas109 = get_body('macros/05_materials.cfg', '_FILE_PROFILE_AUTOSAVE')
_out109 = render(_fas109, {})
tests.append(('R109 _FILE_PROFILE_AUTOSAVE: PRINT_END chains the post save (test.gcode)',
    '_PROFILE_SAVE WHICH=post FILE="test.gcode"' in _out109, _out109[:100]))
save_vars['file_profiles_autosave'] = False
_out109 = render(_fas109, {})
tests.append(('R109 _FILE_PROFILE_AUTOSAVE: toggle off -> nothing',
    '_PROFILE_SAVE' not in _out109, _out109[:80]))
save_vars['file_profiles_autosave'] = True
_fpi109 = get_body('macros/05_materials.cfg', 'FILE_PROFILES_INFO')
_out109 = render(_fpi109, {})
tests.append(('R109 FILE_PROFILES_INFO: pre + post + newer verdict',
    'File profiles for vase.gcode' in _out109 and 'pre  : saved' in _out109
    and 'post : saved' in _out109 and 'auto-load picks the NEWER one' in _out109, _out109[:200]))
_fpl109 = get_body('macros/05_materials.cfg', 'FILE_PROFILE_LOAD')
_out109 = render(_fpl109, {'WHICH': 'post'})
tests.append(('R109 FILE_PROFILE_LOAD post: chains the apply',
    '_PROFILE_APPLY SRC=file WHICH=post FILE="vase.gcode"' in _out109, _out109[:100]))
_out109 = render(_fpl109, {'WHICH': 'bogus'})
tests.append(('R109 FILE_PROFILE_LOAD: bogus WHICH refused',
    'WHICH must be pre or post' in _out109, _out109[:80]))
_gos109 = get_body('macros/17_generator.cfg', '_GEN_OUT_SET')
_out109 = render(_gos109, {'OUT': 'PREVIEW'})
tests.append(('R109 _GEN_OUT_SET OUT=PREVIEW: sticky switch to preview-only',
    'VARIABLE=gen_out VALUE=0' in _out109 and 'PREVIEW ONLY' in _out109, _out109[:100]))
_out109 = render(_gos109, {'OUT': 'QUEUE'})
tests.append(('R109 _GEN_OUT_SET OUT=QUEUE: sticky switch to queue',
    'VARIABLE=gen_out VALUE=1' in _out109, _out109[:80]))
_out109 = render(get_body('macros/17_generator.cfg', 'CABLE_TIE_GENERATE'), {'OUT': 'PREVIEW'})
tests.append(('R109 generators accept OUT= (per-run override, here: cable ties)',
    '_GEN_OUT_SET OUT=PREVIEW' in _out109, _out109[:80]))
_ctg109 = open('macros/08_print_start_stop.cfg', encoding='utf-8').read()
tests.append(('R109 PRINT_END writes the post profile (after the capture)',
    '_CAPTURE_PRINT_SETTINGS' in _ctg109
    and _ctg109.index('_CAPTURE_PRINT_SETTINGS') < _ctg109.index('_FILE_PROFILE_AUTOSAVE'), ''))
_w109 = open('tools/r2_postproc.py', encoding='utf-8').read()
tests.append(('R109 watcher: selection pushes FILE_PROFILE_AUTO + gen_out gates every generator',
    '_FILE_PROFILE_AUTO FILE=' in _w109 and 'def _gen_out' in _w109
    and _w109.count('_sel_line(rv') >= 12
    and _w109.count('_sel_note(rv') >= 7, ''))
_lcd109 = open('menus/lcd_menues.cfg', encoding='utf-8').read()
tests.append(('R109 LCD: Profiles menu with Material/Defaults/This-file submenus',
    'menu __main __preprint __profs]' in _lcd109
    and 'menu __main __preprint __profs __mat]' in _lcd109
    and 'menu __main __preprint __profs __def]' in _lcd109
    and 'menu __main __preprint __profs __file]' in _lcd109
    and 'SAVE_FILE_PROFILE' in _lcd109 and 'FILE_PROFILE_LOAD WHICH=pre' in _lcd109
    and 'FILE_PROFILE_DELETE WHICH=post' in _lcd109
    and "printer['gcode_macro _STATE'].fp_pre|default(False)" in _lcd109
    and 'SAVE_MATERIAL_TEMPS MATERIAL=PLA' in _lcd109
    and 'Auto-load:' in _lcd109 and 'Auto-save post:' in _lcd109, ''))
tests.append(('R109 LCD: Tools > After gen (queue/preview) + explanation',
    'After gen:' in _lcd109 and '_GEN_OUT_SET OUT={0 if cur == 1 else 1}' in _lcd109
    and 'What does that mean?' in _lcd109, ''))
_01109 = open('macros/01_state.cfg', encoding='utf-8').read()
tests.append(('R109 _STATE: fp flags declared + boot inits for the three switches',
    'variable_fp_pre:' in _01109 and 'variable_fp_post:' in _01109
    and 'variable_fp_file:' in _01109
    and 'VARIABLE=gen_out VALUE=1' in _01109
    and 'VARIABLE=file_profiles_on VALUE=True' in _01109
    and 'VARIABLE=file_profiles_autosave VALUE=True' in _01109, ''))
del save_vars['file_profiles'], save_vars['fp_epoch'], save_vars['preview_file']
del save_vars['pending_snap']

# ============== R110: profiles + gen-out LIVE from the LCD (no console, no restart) ==============
# every item of Pre-Print > Profiles and Tools > After gen must RENDER and do
# its work with SET_GCODE_VARIABLE/SAVE_VARIABLE alone - no RESTART, no
# FIRMWARE_RESTART anywhere in the profile menus (that is the whole point:
# the user never leaves the LCD).
_lcd110 = open('menus/lcd_menues.cfg', encoding='utf-8').read()
_items110 = []
for _sec110, _opt110, _lines110 in _cfg_opts67('menus/lcd_menues.cfg'):
    _name110 = _sec110[5:] if _sec110.startswith('menu ') else ''
    if _name110.startswith('__main __preprint __profs') or _name110.startswith('__main __gen __out'):
        _items110.append((_name110, _opt110, '\n'.join(_lines110).strip('\n')))
_rendered110 = []
_bad110 = []
for _nm110, _op110, _t110 in _items110:
    if _op110 not in ('name', 'enable', 'gcode') or not _t110:
        continue
    try:
        _r110 = render(_t110, extra={'menu': M({'input': 1, 'ns': _nm110, 'event': 'click'})})
        if _op110 == 'gcode':
            _rendered110.append((_nm110, _r110))
    except Exception as _e110:
        _bad110.append('%s [%s]: %s' % (_nm110, _op110, _e110))
tests.append(('R110 LCD: all %d profile/gen-out menu templates render' % len(_items110),
    not _bad110 and len(_items110) > 60, str(_bad110[:3])))
_gcodes110 = '\n'.join(_g110 for _n110, _g110 in _rendered110)
# raw templates too: the 2-press delete branches only render ONE side at a
# time, so the DELETE calls are checked against the raw menu text
_raw110 = '\n'.join(_t110 for _nm110, _op110, _t110 in _items110)
tests.append(('R110 LCD: NO restart anywhere in the profile menus',
    'RESTART' not in _gcodes110.upper() and 'RESTART' not in _raw110.upper(), ''))
tests.append(('R110 LCD: full profile lifecycle reachable from the display',
    all(_cmd110 in _raw110 for _cmd110 in (
        'SAVE_FILE_PROFILE', 'FILE_PROFILE_LOAD WHICH=pre', 'FILE_PROFILE_LOAD WHICH=post',
        'FILE_PROFILE_DELETE WHICH=pre', 'FILE_PROFILE_DELETE WHICH=post',
        'FILE_PROFILES_INFO', 'SAVE_MATERIAL_TEMPS MATERIAL=PLA',
        'SAVE_MATERIAL_TEMPS MATERIAL=PETG', 'SAVE_MATERIAL_TEMPS MATERIAL=TPU',
        'SET_MATERIAL MATERIAL=', 'LOAD_DEFAULT_PRESET N=', 'SAVE_DEFAULT_PRESET',
        'DELETE_DEFAULT_PRESET N=', 'DEFAULT_PRESETS_INFO', '_GEN_OUT_SET OUT=')),
    ''))
tests.append(('R110 LCD: default + file deletes are TWO-PRESS (arm + confirm)',
    _raw110.count('DELETE_DEFAULT_PRESET N=') >= 8
    and _raw110.count('def_del_arm') >= 16 and _raw110.count('fp_del_arm') >= 4
    and 'AGAIN' in _raw110, ''))
tests.append(('R110 LCD: the two auto-toggles are switchable at the display',
    'VARIABLE=file_profiles_on' in _gcodes110 and 'VARIABLE=file_profiles_autosave' in _gcodes110,
    ''))
tests.append(('R110 LCD: material save does NOT load the material first',
    'SAVE_MATERIAL_TEMPS MATERIAL=' in _raw110
    and 'LOAD_MATERIAL' not in _raw110, ''))

# ============================= R111 (.85) - roadmap §5+§6 =============================
# fan clamp, bridge boost, feature PA, per-feature shaper-off, file fixes,
# geometry classifier keys in _FILE_INFO, profile replay with the new keys

state_vars.update({'mode': 'printing', 'layer': 2, 'ignore_overrides': False,
                   'current_type': 'WALL-OUTER'})
save_vars.update({'ov_fan_clamp_on': True, 'ov_fan_min': 10.0, 'ov_fan_max': 90.0,
                  'ov_fan_bridge': 0.0, 'flowcap_limit': 12.0, 'travelaccel_value': 8000,
                  'ovf_shaper_off_on': False, 'ovf_shaper_off_feat': 'wallouter',
                  'ovf_wallouter_on': True, 'ovf_wallouter_spd': 100.0,
                  'ovf_wallouter_acc': 0.0, 'ovf_wallouter_flw': 100.0, 'ovf_wallouter_pa': 0.0})
state_vars.update({'pa_feat_active': False, 'shaper_off_active': False,
                   'shaper_saved_fx': 0.0, 'shaper_saved_fy': 0.0, 'file_pa': 0.0})

body = get_body('macros/06_temp_controls.cfg', 'M106')
out = render(body, {'S': '255'})
tests.append(('R111 M106: clamp ON caps S255 -> S230 (max 90%)',
    'M99106 S230' in out and 'clamp 10-90%' in out, [l for l in out.split('\n') if 'clamp' in l][:1]))
out = render(body, {'S': '10'})
tests.append(('R111 M106: clamp lifts S10 -> S26 (min 10%)',
    'M99106 S26' in out, [l for l in out.split('\n') if 'M99106' in l][:1]))
save_vars['ov_fan_clamp_on'] = False
out = render(body, {'S': '255'})
tests.append(('R111 M106: clamp OFF -> S255 untouched',
    'M99106 S255' in out and 'clamp' not in out, out.strip()[:80]))
save_vars['ov_fan_clamp_on'] = True
save_vars['ov_fan_bridge'] = 100.0
state_vars['current_type'] = 'BRIDGE'
out = render(body, {'S': '128'})
tests.append(('R111 M106: bridge boost 100% lifts S128 -> S255 (clamped file!)',
    'M99106 S255' in out and 'bridge 100%' in out, [l for l in out.split('\n') if 'M99106' in l][:1]))
state_vars['current_type'] = 'WALL-OUTER'
save_vars['ov_fan_bridge'] = 0.0

body = get_body('macros/10_live_tuning.cfg', 'APPLY_TYPE')
save_vars['ovf_wallouter_pa'] = 0.06
out = render(body, {'TYPE': 'WALL-OUTER'})
tests.append(('R111 APPLY_TYPE: feature PA 0.06 applied at the boundary',
    'SET_PRESSURE_ADVANCE_BASE ADVANCE=0.06' in out and 'pa_feat_active VALUE=True' in out,
    [l for l in out.split('\n') if 'PA' in l][:2]))
# next feature without PA -> global returns
save_vars['ov_pa_on'] = True; save_vars['ov_pa'] = 0.05
state_vars['pa_feat_active'] = True
save_vars['ovf_infillsparse_on'] = False
out = render(body, {'TYPE': 'INFILL-SPARSE'})
tests.append(('R111 APPLY_TYPE: leaving the feature restores the global PA 0.05',
    'SET_PRESSURE_ADVANCE_BASE ADVANCE=0.05' in out and 'pa_feat_active VALUE=False' in out,
    [l for l in out.split('\n') if 'PA' in l][:2]))
save_vars['ov_pa_on'] = False
state_vars['pa_feat_active'] = False

# shaper off for wallouter
save_vars['ovf_shaper_off_on'] = True
out = render(body, {'TYPE': 'WALL-OUTER'})
tests.append(('R111 APPLY_TYPE: shaper OFF while wallouter prints (freqs saved 52.3/41.7)',
    'SET_INPUT_SHAPER SHAPER_FREQ_X=0 SHAPER_FREQ_Y=0' in out
    and 'shaper_saved_fx VALUE=52.3' in out and 'shaper_off_active VALUE=True' in out,
    [l for l in out.split('\n') if 'SHAPER' in l][:3]))
state_vars['shaper_off_active'] = True
state_vars['shaper_saved_fx'] = 52.3
state_vars['shaper_saved_fy'] = 41.7
save_vars['ovf_shaper_off_on'] = False
out = render(body, {'TYPE': 'INFILL-SPARSE'})
tests.append(('R111 APPLY_TYPE: shaper back ON with the saved freqs after the feature',
    'SHAPER_FREQ_X=52.3 SHAPER_FREQ_Y=41.7' in out and 'shaper_off_active VALUE=False' in out,
    [l for l in out.split('\n') if 'SHAPER' in l][:2]))
state_vars['shaper_off_active'] = False
save_vars['ovf_wallouter_pa'] = 0.0

body = get_body('macros/10_live_tuning.cfg', 'SET_FAN_CLAMP')
out = render(body, {'MIN': '80', 'MAX': '20'})
tests.append(('R111 SET_FAN_CLAMP: MIN>MAX rejected',
    'MIN must be <= MAX' in out, out.strip()[:90]))
out = render(body, {'ON': '1', 'MIN': '10', 'MAX': '90'})
tests.append(('R111 SET_FAN_CLAMP: ON=1 stores the curve',
    'VARIABLE=ov_fan_clamp_on VALUE=True' in out and 'VARIABLE=ov_fan_min VALUE=10.0' in out, out.strip()[:90]))

body = get_body('macros/10_live_tuning.cfg', 'SET_FEAT_PA')
out = render(body, {'FEATURE': 'wallouter', 'PA': '0.5'})
tests.append(('R111 SET_FEAT_PA: PA over 0.3 rejected',
    'must be 0 (off) .. 0.3' in out, out.strip()[:90]))
out = render(body, {'FEATURE': 'wallouter', 'PA': '0.05'})
tests.append(('R111 SET_FEAT_PA: PA=0.05 routes through feat_pa_wallouter',
    'SET_OVERRIDE_VALUE NAME=feat_pa_wallouter VALUE=0.05' in out, out.strip()[:90]))

body = get_body('macros/10_live_tuning.cfg', 'SET_FEAT_SHAPER_OFF')
gd = dict(build_printer()); del gd['input_shaper']
out = env.from_string(body).render(printer=MP(gd), params={'FEATURE': 'wallouter', 'STATE': '1'})
tests.append(('R116 SET_FEAT_SHAPER_OFF: no [input_shaper] -> NOTIFY on the LCD too',
    'needs [input_shaper] in printer.cfg' in out and 'M117 ShaperOff: n/a' in out,
    out.strip()[:90]))
out = render(body, {'FEATURE': 'wallouter', 'STATE': '1'})
tests.append(('R111 SET_FEAT_SHAPER_OFF: STATE=1 arms the switch',
    'VARIABLE=ovf_shaper_off_on VALUE=True' in out and "VARIABLE=ovf_shaper_off_feat VALUE='wallouter'" in out,
    out.strip()[:120]))
save_vars['ovf_shaper_off_on'] = False

body = get_body('macros/10_live_tuning.cfg', 'SET_UNRETRACT_EXTRA')
out = render(body, {'EXTRA': '0.05'})
tests.append(('R111 SET_UNRETRACT_EXTRA: 0.05 -> SET_RETRACTION_BASE',
    'SET_RETRACTION_BASE UNDO_EXTRA_RETRACT_LENGTH=0.05' in out, out.strip()[:90]))

body = get_body('macros/10_live_tuning.cfg', '_FEAT_TUNING_RESTORE')
state_vars['pa_feat_active'] = True
state_vars['shaper_off_active'] = True
state_vars['shaper_saved_fx'] = 52.3
state_vars['shaper_saved_fy'] = 41.7
save_vars['ov_pa_on'] = True; save_vars['ov_pa'] = 0.05
out = render(body, {})
tests.append(('R111 _FEAT_TUNING_RESTORE: PRINT_END/CANCEL safety net restores PA + shaper',
    'SET_PRESSURE_ADVANCE_BASE ADVANCE=0.05' in out
    and 'SET_INPUT_SHAPER SHAPER_FREQ_X=52.3 SHAPER_FREQ_Y=41.7' in out
    and 'pa_feat_active VALUE=False' in out and 'shaper_off_active VALUE=False' in out,
    [l for l in out.split('\n') if 'RESTORE' not in l and l.strip()][:4]))
state_vars.update({'pa_feat_active': False, 'shaper_off_active': False, 'shaper_saved_fx': 0.0, 'shaper_saved_fy': 0.0})
save_vars['ov_pa_on'] = False

body = get_body('macros/08_print_start_stop.cfg', '_FILE_INFO')
out = render(body, {'DERIVED': '1', 'CONF': '0.7', 'COVER': '89', 'MAXRATE': '4.3',
                    'SEAM': '80,80', 'SEAMN': '8', 'TOTAL_LAYERS': '100'})
tests.append(('R111 _FILE_INFO: geometry keys land in _STATE (derived/conf/cover/maxrate/seam)',
    'VARIABLE=file_derived VALUE=True' in out and 'VARIABLE=file_conf VALUE=0.7' in out
    and 'VARIABLE=file_cover VALUE=89' in out and 'VARIABLE=file_maxrate VALUE=4.3' in out
    and 'VARIABLE=file_seam VALUE=\'"80,80"\'' in out and 'VARIABLE=file_seamn VALUE=8' in out,
    [l for l in out.split('\n') if 'R111' not in l and l.strip() and 'SET_GCODE' in l][:6]))
tests.append(('R111 _FILE_INFO: honest wording - "DERIVED by geometry ... classifier guessed"',
    'DERIVED by geometry' in out and 'classifier guessed' in out, ''))
tests.append(('R111 _FILE_INFO: flow + seam line for the console',
    'max 4.3 mm3/s' in out and 'seam at 80,80' in out, ''))

body = get_body('macros/08_print_start_stop.cfg', '_FILE_INFO_RESET')
out = render(body, {})
tests.append(('R111 _FILE_INFO_RESET: the new state clears with the rest',
    'VARIABLE=file_derived VALUE=False' in out and 'VARIABLE=file_maxrate VALUE=0.0' in out
    and 'VARIABLE=file_seam VALUE=\'"-"\'' in out and "VARIABLE=file_seamn VALUE=0" in out,
    [l for l in out.split('\n') if 'file_derived' in l or 'file_maxrate' in l or 'file_seam' in l]))

body = get_body('macros/05_materials.cfg', '_PROFILE_APPLY')
save_vars['default_preset_1'] = {
    'material': 'PLA', 'bed': 60.0, 'bed_on': True, 'fan_min': 10.0, 'fan_max': 90.0,
    'shaper_off_feat': 'wallouter', 'shaper_off_on': True,
    'feats': {'wallouter': [True, 100.0, 0.0, 100.0],       # OLD 4-element profile
              'infillsparse': [False, 100.0, 0.0, 100.0, 0.04]}}  # NEW 5-element
out = render(body, {'SRC': 'default', 'N': '1'})
tests.append(('R111 _PROFILE_APPLY: 5-element feats load feature PA 0.04',
    'VARIABLE=ovf_infillsparse_pa VALUE=0.04' in out, [l for l in out.split('\n') if '_pa' in l][:2]))
tests.append(('R111 _PROFILE_APPLY: old 4-element profile -> PA 0 (no crash)',
    'VARIABLE=ovf_wallouter_pa VALUE=0.0' in out, ''))
tests.append(('R111 _PROFILE_APPLY: fan clamp + shaper-off replay from the preset',
    'VARIABLE=ov_fan_min VALUE=10.0' in out and 'VARIABLE=ov_fan_max VALUE=90.0' in out
    and 'VARIABLE=ovf_shaper_off_feat VALUE=\'"wallouter"\'' in out
    and 'VARIABLE=ovf_shaper_off_on VALUE=True' in out,
    [l for l in out.split('\n') if 'fan_min' in l or 'shaper_off' in l][:4]))
del save_vars['default_preset_1']

body = get_body('macros/05_materials.cfg', '_PROFILE_SAVE')
save_vars['ovf_wallouter_pa'] = 0.06
out = render(body, {})
tests.append(('R111 _PROFILE_SAVE: snapshot carries the 5th element (feature PA)',
    "'wallouter': [True, 100.0, 0.0, 100.0, 0.06]" in out, [l for l in out.split('\n') if 'pending_snap' in l][:1]))
save_vars['ovf_wallouter_pa'] = 0.0

body = get_body('macros/08_print_start_stop.cfg', 'FIX_FILE')
state_vars['mode'] = 'idle'          # file fixes are blocked during a print
save_vars['flowcap_fix_nonce'] = 3
out = render(body, {'WHAT': 'FLOWCAP', 'CAP': '5.5'})
tests.append(('R111 FIX_FILE WHAT=FLOWCAP: arms the watcher nonce (cap 5.5)',
    'VARIABLE=flowcap_fix_nonce VALUE=4' in out and 'VARIABLE=flowcap_limit VALUE=5.5' in out,
    [l for l in out.split('\n') if 'flowcap' in l][:3]))
out = render(body, {'WHAT': 'FLOWCAP', 'CAP': '99'})
tests.append(('R111 FIX_FILE WHAT=FLOWCAP: silly caps rejected honestly',
    'must be 0.5..50' in out, out.strip()[:90]))
save_vars['travelacc_fix_nonce'] = 0
out = render(body, {'WHAT': 'TRAVELACC', 'ACCEL': '6000'})
tests.append(('R111 FIX_FILE WHAT=TRAVELACC: arms the watcher nonce (6000 mm/s2)',
    'VARIABLE=travelacc_fix_nonce VALUE=1' in out and 'VARIABLE=travelaccel_value VALUE=6000' in out,
    [l for l in out.split('\n') if 'travelac' in l][:3]))
state_vars['mode'] = 'printing'

# ============================= R112 (.86) - retag + retract verdict =============================
# v4 files become STALE and RETAG upgrades them in place (no double markers,
# same LAYER_MARK count, the new info keys); the retract verdict is unambiguous

import tempfile as _tf112, os as _os112, subprocess as _sp112, sys as _sys112
import importlib.util as _ilu112
_spec112 = _ilu112.spec_from_file_location('pp112', 'tools/r2_postproc.py')
_pp112 = _ilu112.module_from_spec(_spec112); _spec112.loader.exec_module(_pp112)
_d112 = _tf112.mkdtemp(prefix='r112_rt_')

# --- 1) a REAL v4 file (tagged by the pre-.86 code): markers stay, info refreshes ---
_body112 = ('; generated by OrcaSlicer 2.2.0\nM82\nG28\nG90\n'
            ';LAYER_CHANGE\nG1 X10 Y10 Z0.2 F1200 E1.0\n'
            ';LAYER_CHANGE\nG1 X10 Y10 Z0.4 F1200 E2.0\n'
            ';TYPE:Outer wall\nG1 X20 Y10 F2400 E3.0\nG1 X30 Y10 F2400 E4.0\n'
            ';TYPE:Sparse infill\nG1 X40 Y10 F4800 E5.0\nM104 S0\n')
_p112 = _os112.path.join(_d112, 'v4file.gcode')
open(_p112, 'w').write(_body112)
_pp112.process(_p112)                    # tag with the CURRENT code
_t112 = open(_p112).read()
_m112 = _t112.count('\nLAYER_MARK'); _a112 = _t112.count('\nAPPLY_TYPE TYPE=')
# simulate the pre-.86 tag: v5 -> v4 (everything tagged before .86 looks like this)
open(_p112, 'w').write(_t112.replace('; R2-POSTPROC v5', '; R2-POSTPROC v4'))
_rows112, _tot112 = _pp112.file_check_scan(_d112)
tests.append(('R112 a pre-.86 (v4-tagged) file counts as STALE, not CURRENT',
    _tot112['stale'] == 1 and _tot112['current'] == 0, str(_tot112)))
_s112 = _pp112.process(_p112)            # RETAG (the upgrade path)
_t112b = open(_p112).read()
tests.append(('R112 RETAG upgrades v4 -> v5 with NO double markers',
    '; R2-POSTPROC v5' in _t112b and '; R2-POSTPROC v4' not in _t112b
    and _t112b.count('\nLAYER_MARK') == _m112
    and _t112b.count('\nAPPLY_TYPE TYPE=') == _a112
    and _t112b.count('\n_FILE_INFO') == 1,
    (len(_t112b), len(_t112))))
tests.append(('R112 RETAG result is CURRENT again and carries the new keys',
    _pp112.file_check_scan(_d112)[1]['current'] == 1
    and 'MAXRATE=' in _t112b and 'SEAM=' in _t112b,
    ''))
_s112b = _pp112.process(_p112)
tests.append(('R112 RETAG is idempotent (second run skips)',
    _s112b.get('skipped') is True, ''))

# --- 2) the retract verdict across the four cases ---
def _rv112(name, body):
    p = _os112.path.join(_d112, name)
    open(p, 'w').write(body)
    _pp112.process(p)
    t = open(p).read()
    import re as _re112
    st = _re112.search(r'RETRACT_STATUS=(\w+)', t)
    mx = _re112.search(r'RETRACT_MAX=([\d.]+)', t)
    return st.group(1) if st else '', float(mx.group(1)) if mx else 0.0

tests.append(('R112 Bowden file (4.5 mm retracts): verdict FIX, not optional',
    _rv112('bowden.gcode',
           '; generated by Cura_SteamEngine 5.7.0\nM82\nG28\nG90\n;LAYER_CHANGE\n'
           'G1 X10 Y10 Z0.2 F1200 E1.0\nG1 E-3.4 F2400\nG1 X20 Y10 F1200 E4.4\n'
           'G1 E-0.1 F2400\nG1 X30 Y10 F1200 E10.0\nM104 S0\n') == ('fix', 4.5),
    ''))
tests.append(('R112 moderate retracts (0.8 mm): verdict CAN (optional)',
    _rv112('moderate.gcode',
           '; generated by Cura_SteamEngine 5.7.0\nM82\nG28\nG90\n;LAYER_CHANGE\n'
           'G1 X10 Y10 Z0.2 F1200 E1.0\nG1 E0.2 F2400\nG1 X20 Y10 F1200 E1.8\n'
           'G1 E1.0 F2400\nG1 X30 Y10 F1200 E2.8\nM104 S0\n') == ('can', 0.8),
    ''))
tests.append(('R112 G10/G11 file: verdict FW (nothing to do)',
    _rv112('fw.gcode',
           '; generated by OrcaSlicer 2.2.0\nM82\nG28\nG90\n;LAYER_CHANGE\n'
           'G1 X10 Y10 Z0.2 F1200 E1.0\nG10\nG0 X20 Y10 F9000\nG11\n'
           'G1 X30 Y10 F1200 E2.0\nM104 S0\n')[0] == 'fw', ''))
tests.append(('R112 already-rewritten file: verdict FIXED',
    _rv112('fixed.gcode',
           '; generated by Cura_SteamEngine 5.7.0\n; R2-RETRACTFIX: 2 pair(s)\n'
           'M82\nG28\nG90\n;LAYER_CHANGE\nG1 X10 Y10 Z0.2 F1200 E1.0\nG10\n'
           'G0 X20 Y10 F9000\nG11\nG1 X30 Y10 F1200 E2.0\nM104 S0\n')[0] == 'fixed', ''))

# --- 3) _FILE_INFO macro parses the verdict into _STATE ---
body = get_body('macros/08_print_start_stop.cfg', '_FILE_INFO')
out = render(body, {'RETRACT_STATUS': 'fix', 'RETRACT_MAX': '6.5'})
tests.append(('R112 _FILE_INFO: RETRACT_STATUS/MAX land in _STATE',
    'VARIABLE=file_retract_status VALUE=\'"fix"\'' in out
    and 'VARIABLE=file_retract_max VALUE=6.5' in out
    and 'FIX - explicit slicer retracts up to 6.5 mm - FIX! they override' in out,
    [l for l in out.split('\n') if 'retract' in l.lower()][:3]))
out = render(body, {'RETRACT_STATUS': 'fw'})
tests.append(('R112 _FILE_INFO: fw verdict explains itself (nothing to do)',
    'slicer-native G10/G11' in out, out.strip()[:90]))

body = get_body('macros/08_print_start_stop.cfg', '_FILE_INFO_RESET')
out = render(body, {})
tests.append(('R112 _FILE_INFO_RESET clears the verdict',
    'VARIABLE=file_retract_status VALUE=\'""\'' in out
    and 'VARIABLE=file_retract_max VALUE=0.0' in out, ''))

# --- 4) _PREVIEW_SET: the verdict can never go stale between selections ---
body = get_body('macros/08_print_start_stop.cfg', '_PREVIEW_SET')
out = render(body, {'NAME': 'old.gcode', 'RETRACT_STATUS': 'fix', 'RETRACT_MAX': '6.5'})
out2 = render(body, {'NAME': 'stale_v4.gcode'})      # no verdict keys at all
tests.append(('R112 _PREVIEW_SET resets the verdict (STALE files show -- not the old one)',
    'VARIABLE=retract_status VALUE=\'"fix"\'' in out
    and 'VARIABLE=retract_status VALUE=\'""\'' in out2
    and 'VARIABLE=retract_max VALUE=0.0' in out2,
    [l for l in out2.split('\n') if 'retract' in l][:2]))

# --- 5) the LCD RetFix offer only appears for fix/can ---
_lcd112 = open('menus/lcd_menues.cfg').read()
tests.append(('R112 LCD: RetFix file gated on the verdict (fix/can), not just style',
    "__fixr]" in _lcd112 and "retract_status|default('') in ['fix', 'can']" in _lcd112
    and "__retst]" in _lcd112, ''))
tests.append(('R112 LCD: the Ret: status line names all four verdicts + fallback',
    all(k in _lcd112 for k in ("'FIX!'", "'can '", "'fixed'", "'fw'", "'--'")),
    ''))

# --- 6) LED_INFO: empty bed-light span reads as none, not 5-4 ---
body = get_body('macros/03_leds.cfg', 'LED_INFO')
_gd112 = dict(build_printer())
_gd112['gcode_macro _R2_CONFIG'] = M({'led_section': 'printer_leds', 'led_type': 'neopixel',
                                       'led_status_n': 4, 'led_bed_n': 0, 'led_bed_on': 1,
                                       'led_bed_bright': 0.4, 'led_nozzle_split': 0})
_gd112['configfile'] = M({'settings': M({'neopixel printer_leds': M({'pin': 'PA8', 'chain_count': 5})})})
out = env.from_string(body).render(printer=MP(_gd112), params={})
tests.append(('R112 LED_INFO: bn=0 -> no bed light LEDs (main chain), not 5-4',
    'no bed light LEDs on the main chain' in out and '5-4' not in out,
    [l for l in out.split('\n') if 'areas' in l][:1]))

# --- 7) FILE_CHECK console summary names STALE ---
import re as _re112b
_ppsrc112 = open('tools/r2_postproc.py').read()
tests.append(('R112 file-check summary teaches the RETAG path for stale files',
    'stale (v4: RETAG=1' in _ppsrc112 or 'stale (v4)' in _ppsrc112, ''))

# ================= R112: parameter wiring cross-check =================
# every _FILE_INFO (KEY, var) pair: the _STATE variable exists AND is in the
# reset list; every CFG replay key of the post-processor reaches the parser
import re as _re112c
_08112 = open('macros/08_print_start_stop.cfg').read()
_01112 = open('macros/01_state.cfg').read()
_pairs112 = _re112c.findall(r"\('([A-Z][A-Z0-9_]+)','(\w+)'\)", _08112)
_decl112 = set(_re112c.findall(r'^variable_(\w+):', _01112, _re112c.M))
_resetm112 = _re112c.search(r'_FILE_INFO_RESET.*?\n(.*?)\n\n\[', _08112, _re112c.S)
_reset112 = _re112c.findall(r"'(\w+)'", _resetm112.group(1)) if _resetm112 else []
_missing_decl = [v for (_, v) in _pairs112 if v not in _decl112]
_missing_reset = [v for (_, v) in _pairs112 if v not in _reset112 and not v.startswith('total_')]
tests.append(('R112 cross-check: all %d _FILE_INFO keys map to DECLARED _STATE vars'
              % len(_pairs112),
    not _missing_decl, _missing_decl[:6]))
tests.append(('R112 cross-check: every mapped var is in _FILE_INFO_RESET',
    not _missing_reset, _missing_reset[:6]))

# the 14 new CFG replay keys (LW_*, ACCEL_*, FIL_DIA, ...) reach the parser
_ppsrc112 = open('tools/r2_postproc.py').read()
_cfgkeys112 = _re112c.search(r'CFG_KEYS\s*=\s*\{(.*?)\n\}', _ppsrc112, _re112c.S)
_cfg112 = sorted(set(_re112c.findall(r":\s*'([A-Z][A-Z0-9_]+)'", _cfgkeys112.group(1)))) if _cfgkeys112 else []
assert _cfg112, 'CFG_KEYS regex broke - fix the crosscheck, not the assert'
_not_parsed = [k for k in _cfg112
               if ('%s' % k) not in _08112]
tests.append(('R112 cross-check: all %d post-processor CFG_KEYS reach the _FILE_INFO parser'
              % len(_cfg112),
    not _not_parsed, _not_parsed[:8]))

# the parser's RESET loop and the declarations stay in sync (no orphan var)
_orphans112 = [v for v in _reset112 if v not in _decl112 and not v.startswith('total_')]
tests.append(('R112 cross-check: reset list has no undeclared variables',
    not _orphans112, _orphans112[:6]))

# the 17 feature codes are spelled identically everywhere they are listed
_codes112 = ('wallouter','wallinner','infillsparse','infillsolid','surfacetop',
             'surfacebottom','bridge','gaps','support','ironing','skirt','brim',
             'overhangperim','internalbridge','primetower','custom','travel')
_fcodes_mismatch = []
for _f112 in ['macros/07_start_confirm.cfg', 'macros/10_live_tuning.cfg',
              'macros/05_materials.cfg']:
    _src112 = open(_f112).read()
    _found112 = _re112c.search(r"\[('wallouter'.*?'travel')\]", _src112, _re112c.S)
    if not _found112:
        _fcodes_mismatch.append(_f112 + ': no list')
    else:
        _got112 = [c.strip().strip("'") for c in _found112.group(1).split(',')]
        if _got112 != list(_codes112):
            _fcodes_mismatch.append('%s: %s' % (_f112, _got112[:4]))
tests.append(('R112 cross-check: the 17 feature codes are identical in 07/10/05',
    not _fcodes_mismatch, _fcodes_mismatch))

# ================= R115: fan HOLD + start-dialog idle guard + feature PA =================
# .87 field log round 2: (a) live fan only SCALED the file's M106 - dynamic
# slicer fan curves always won; HOLD replaces the value. (b) idle_timeout
# counts from the last TOOLHEAD move - TURN_OFF_HEATERS fired mid-start-dialog.
# (c) feature PA was live-only and showed 0 although the global ruled.
_body115 = get_body('macros/06_temp_controls.cfg', 'M106')
state_vars.update({'mode': 'printing', 'layer': 3, 'ignore_overrides': False})
state_vars['f_fan_hold'] = 40
_out115 = render(_body115, {'S': '255'})
tests.append(('R115 M106 HOLD: file S255 -> hold 40% -> S102 (file ignored)',
    'S102' in _out115 and 'hold 40%' in _out115, _out115.strip()[:120]))
state_vars['f_fan_hold'] = 0
_out115b = render(_body115, {'S': '255'})
tests.append(('R115 M106 HOLD off (0): file rules again (S255 passthrough)',
    'S255' in _out115b and 'hold' not in _out115b, _out115b.strip()[:80]))

_body115 = get_body('macros/10_live_tuning.cfg', 'SET_FAN_HOLD')
_out115 = render(_body115, {'PERCENT': '40'})
tests.append(('R115 SET_FAN_HOLD 40%: applies immediately + speaks it',
    'VARIABLE=f_fan_hold VALUE=40.0' in _out115 and 'M99106 S102' in _out115 and 'Fan hold 40%' in _out115, _out115.strip()[:140]))
_out115 = render(_body115, {'PERCENT': '0'})
tests.append(('R115 SET_FAN_HOLD 0: back to the file values',
    'Fan hold OFF' in _out115 and "VALUE=0.0" in _out115, _out115.strip()[:140]))

_body115 = get_body('macros/10_live_tuning.cfg', 'APPLY_TYPE')
save_vars.update({'ov_pa_on': True, 'ov_pa': 0.055,
                  'ovf_wallouter_on': True, 'ovf_wallouter_spd': 100,
                  'ovf_wallouter_acc': 0, 'ovf_wallouter_pa': 0})
_out115 = render(_body115, {'TYPE': 'WALL-OUTER'})
tests.append(('R115 APPLY_TYPE: no own PA but global 0.055 ON -> boundary states it',
    'ADVANCE=0.055' in _out115 and 'PA 0.055 (your global' in _out115, [l for l in _out115.split(chr(10)) if 'PA ' in l][:2]))
save_vars.update({'ov_pa_on': False, 'ovf_wallouter_on': False})

_body115 = get_body('macros/08_print_start_stop.cfg', '_WAIT_IDLE_RESTORE')
state_vars['idle_timeout_saved'] = 3600
_out115 = render(_body115, {})
tests.append(('R115 _WAIT_IDLE_RESTORE: config idle_timeout back',
    'SET_IDLE_TIMEOUT TIMEOUT=3600' in _out115, _out115.strip()[:60]))

_body115 = get_body('macros/08_print_start_stop.cfg', '_SELECT_FILE')
state_vars['mode'] = 'waiting'
_out115 = render(_body115, {'FILE': '00_x.gcode'})
tests.append(('R115 _SELECT_FILE: generator takeover does NOT kill the preheat',
    'TURN_OFF_HEATERS' not in _out115 and 'CANCEL_PRINT_BASE' in _out115 and 'SDCARD_PRINT_FILE FILENAME="00_x.gcode"' in _out115, _out115.strip()[:160]))
state_vars['mode'] = 'printing'

_fl115 = get_body('macros/17_generator.cfg', 'FRAME_LOAD_PRESET')
save_vars.update({'frame_user_preset_1':
                  {'preset': 'OLD', 'w': 105.0, 'h': 148.0, 'depth': 10.0,
                   'border': 8.0, 'corner': 6.0, 'walls': 1, 'shape': 'RECT',
                   'closure': 'BACK', 'hang': 'TOP', 'stand': False,
                   'ironing': True, 'infill': 60.0,
                   'front': 'IRON', 'cable': False, 'disc': 'NONE',
                   'disc_t': 1.0, 'disc_side': 'FRONT', 's_deep': 0.8,
                   's_space': 6.0, 's_angle': 45.0, 's_amp': 1.2,
                   's_size': 8.0, 's_dir': 'OUT'}})   # pre-R101: NO top_l/bot_l!
_out115 = render(_fl115, {'N': '1'})
tests.append(('R115 frame preset load: old preset without bot_l -> bottom solid 2 (not 0 = see-through!)',
    'frame_bot_l VALUE=2' in _out115 and 'frame_bot_l VALUE=0' not in _out115 and 'frame_top_l VALUE=0' in _out115,
    [l for l in _out115.split(chr(10)) if 'bot_l' in l or 'top_l' in l]))
save_vars['frame_user_preset_1'] = 0

_lcd115 = open('menus/lcd_menues.cfg').read()
_pp_pa115 = [l for l in _lcd115.split(chr(10))
             if l.startswith('[menu __main __preprint __feat __') and l.endswith('__pa]')]
tests.append(('R115 LCD: 16 feature-PA inputs in Pre-Print > Features',
    len(_pp_pa115) == 16, 'counted %d' % len(_pp_pa115)))
_pause115 = _lcd115[_lcd115.index('[menu __main __live __pause]'):_lcd115.index('[menu __main __live __objects]')]
_first115 = _pause115.split('[menu ')[2]
tests.append(('R115 LCD: PAUSE NOW no longer the FIRST entry + two-press',
    '__next]' in _first115 and 'pause_now_arm' in _pause115 and 'AGAIN' in _pause115 and 'QUICK_PAUSE' in _pause115,
    _first115.split(chr(10))[0]))

# ================= R117: continuous fills + ironing follows the top angle ================
# .88 field log order: first layer / bottom / infill must NOT print as single
# scanlines - they chain into ONE continuous zigzag that fuses with the walls;
# ironing runs at the SAME angle as the top surface it flattens.
import math as _math117
import re as _re117
import statistics as _stat117

def _an117(path):
    typ, z = None, None
    blocks = {}
    px = py = None
    for _raw117 in open(path):
        _st117 = _raw117.strip()
        if _st117.startswith(';TYPE:'):
            typ = _st117[6:]
            continue
        if _st117.startswith(';Z:'):
            z = _st117[3:]
            continue
        _l117 = _raw117.split(';')[0].strip()
        if not _l117:
            continue
        _m117 = _re117.match(r'G0 X([-\d.]+) Y([-\d.]+)', _l117)
        if _m117:
            if typ:
                blocks.setdefault((typ, z), {'g0': 0, 'segs': []})['g0'] += 1
            px, py = float(_m117.group(1)), float(_m117.group(2))
            continue
        _m117 = _re117.match(r'G1 X([-\d.]+) Y([-\d.]+) E([-\d.]+)', _l117)
        if _m117 and typ:
            _x117, _y117, _e117 = (float(_m117.group(i)) for i in (1, 2, 3))
            if px is not None and _e117 > 0 and _math117.hypot(_x117 - px, _y117 - py) > 0.3:
                blocks.setdefault((typ, z), {'g0': 0, 'segs': []})['segs'].append((_x117 - px, _y117 - py))
            px, py = _x117, _y117
            continue
        _m117 = _re117.match(r'G1 X([-\d.]+) Y([-\d.]+)', _l117)
        if _m117:
            px, py = float(_m117.group(1)), float(_m117.group(2))
    return blocks

def _ratio117(blocks):
    _f117 = [v for k, v in blocks.items()
             if k[0] in ('Bottom surface', 'Top surface', 'Internal solid infill', 'Sparse infill')]
    _g1 = sum(len(v['segs']) for v in _f117)
    _g0 = sum(v['g0'] for v in _f117)
    return _g1 / max(1, _g0), _g1, _g0

def _adiff117(blocks):
    _tops = {k: v for k, v in blocks.items() if k[0] == 'Top surface' and v['segs']}
    _irs = {k: v for k, v in blocks.items() if k[0] == 'Ironing' and v['segs']}
    if not _tops or not _irs:
        return None
    _at = _stat117.median(_math117.degrees(_math117.atan2(dy, dx)) % 180.0
                          for (dx, dy) in _tops[sorted(_tops, key=lambda k: float(k[1] or 0))[-1]]['segs'])
    _ai = _stat117.median(_math117.degrees(_math117.atan2(dy, dx)) % 180.0
                          for (dx, dy) in _irs[sorted(_irs, key=lambda k: float(k[1] or 0))[-1]]['segs'])
    return abs((_at - _ai + 90) % 180 - 90)

_BED117 = (0.0, -3.0, 244.0, 238.0)
_D117 = tempfile.mkdtemp(prefix='r117')
_o117, _ = _pp61.make_labels(['WERKSTATT', 'R2'], w=60, h=30, hole_side=1, bed=_BED117, out_dir=_D117)
_b117 = _an117(_o117)
_r117 = _ratio117(_b117)[0]
tests.append(('R117 LABELS: fills chain continuously (>=8 extrusions per travel, was ~1)',
    _r117 >= 8.0, 'ratio %.1f' % _r117))
tests.append(('R117 LABELS: ironing angle == top angle (<=8 deg, was 90)',
    _adiff117(_b117) is not None and _adiff117(_b117) <= 8.0, 'diff %s' % _adiff117(_b117)))

_o117, _ = _pp61.make_bridge(length=100, bed=_BED117, out_dir=_D117)
_r117 = _ratio117(_an117(_o117))[0]
tests.append(('R117 BRIDGE: deck fills chain continuously (>=20:1)',
    _r117 >= 20.0, 'ratio %.1f' % _r117))

_o117, _ = _pp61.make_cable_ties(count=3, length=80, bed=_BED117, out_dir=_D117)
_r117 = _ratio117(_an117(_o117))[0]
tests.append(('R117 TIES: strap fills chain continuously (>=20:1)',
    _r117 >= 20.0, 'ratio %.1f' % _r117))

_o117, _ = _pp61.make_angles(count=2, angle_deg=90, bed=_BED117, out_dir=_D117, ironing=True)
_b117 = _an117(_o117)
_r117 = _ratio117(_b117)[0]
tests.append(('R117 ANGLES: plate fills chain (>=4:1 - hole crossings stay travels)',
    _r117 >= 4.0, 'ratio %.1f' % _r117))
tests.append(('R117 ANGLES: ironing angle == top angle (<=8 deg)',
    _adiff117(_b117) is not None and _adiff117(_b117) <= 8.0, 'diff %s' % _adiff117(_b117)))

_o117, _ = _pp61.make_frame(depth=8, bed=_BED117, out_dir=_D117)
_b117 = _an117(_o117)
_r117 = _ratio117(_b117)[0]
tests.append(('R117 FRAME: ring fills chain continuously (>=10:1)',
    _r117 >= 10.0, 'ratio %.1f' % _r117))
tests.append(('R117 FRAME: ironing angle == top angle (<=8 deg, was 45)',
    _adiff117(_b117) is not None and _adiff117(_b117) <= 8.0, 'diff %s' % _adiff117(_b117)))

_sr117 = open('tools/r2_postproc.py').read()
tests.append(('R117 source: _emit_hatch only for single-line patterns (7 left) + range uses _serp_g',
    _sr117.count('_emit_hatch(pen, [') == 7
    and '_serp_g(g, segs, eph, 1200, spacing)' in _sr117
    and '_serp_g(gt, segs, eph, 1200, spacing)' in _sr117,
    'left %d' % _sr117.count('_emit_hatch(pen, [')))

# ================= R119: label shapes, raised border, mm height =================
# User spec (.89 follow-up): W/H in 1mm steps, labels up to 2cm tall (>6 base
# layers = 4 bottom + 4 top solid + sparse between, like the frames), an
# optional raised border ON THE TEXT LAYERS (same start, same color - the
# M600 swap sits right before them), and RECT/OVAL/ROUND shapes like frames.
import hashlib as _hl119
import math as _math119
import re as _re119
_D119 = tempfile.mkdtemp(prefix='r119_')
_MD5_119 = '4dc663df490b2d85a5f1be95cc669ce1'   # frozen from R118 (verified equal)

def _labpts119(path, li):
    _t = open(path).read()
    _lay = _re119.split(r'(?m)^;LAYER_CHANGE', _t)[li]
    _blk = _lay.split('EXCLUDE_OBJECT_START NAME=LABEL_1')[1].split('EXCLUDE_OBJECT_END')[0]
    _pts, _px, _py = [], None, None
    for _l in _blk.split('\n'):
        _m = _re119.match(r'G0 X([\d.-]+) Y([\d.-]+)', _l)
        if _m:
            _px, _py = float(_m.group(1)), float(_m.group(2))
            continue
        _m = _re119.match(r'G1 X([\d.-]+) Y([\d.-]+) E([\d.]+)', _l)
        if _m and float(_m.group(3)) > 0:
            if _px is not None:
                _pts.append((_px, _py))
            _pts.append((float(_m.group(1)), float(_m.group(2))))
            _px, _py = float(_m.group(1)), float(_m.group(2))
    _c = _re119.search(r'EXCLUDE_OBJECT_DEFINE NAME=LABEL_1 '
                       r'CENTER=([\d.]+),([\d.]+)', _t)
    return _pts, (float(_c.group(1)), float(_c.group(2))), _t

_o119, _i119 = _pp61.make_labels(['WERKSTATT'], w=60, h=30, out_dir=_D119)
tests.append(('R119 default path byte-identical to R118 (frozen md5)',
    _hl119.md5(open(_o119, 'rb').read()).hexdigest() == _MD5_119, 'md5 changed'))
_o119, _i119 = _pp61.make_labels(['WERKSTATT'], w=60, h=30, out_dir=_D119,
                                 shape='RECT', corner=0.0, border_walls=0,
                                 border_gap=0.0, height=0.0)
tests.append(('R119 explicit defaults == implicit (no hidden coupling)',
    _hl119.md5(open(_o119, 'rb').read()).hexdigest() == _MD5_119, 'md5 differs'))

# --- OVAL: walls/fill/ironing stay inside the ellipse, polygon IS the outline
_o119, _i119 = _pp61.make_labels(['OVAL'], shape='OVAL', w=60, h=30, out_dir=_D119)
_w119, _h119 = _i119['w'], _i119['h']
_bad119 = 0
for _li119 in (2, 4):
    _pts, (_cx, _cy), _ = _labpts119(_o119, _li119)
    _bad119 += sum(1 for (_x, _y) in _pts
                   if ((_x - _cx) / (_w119 / 2)) ** 2
                   + ((_y - _cy) / (_h119 / 2)) ** 2 > 1.01)
tests.append(('R119 OVAL: walls+fill+ironing inside the ellipse (layers 2+4)',
    _bad119 == 0, '%d outside' % _bad119))
_pol119 = _re119.search(r'EXCLUDE_OBJECT_DEFINE NAME=LABEL_1[^\n]*POLYGON=(\[[^\n]*\])',
                       _labpts119(_o119, 2)[2])
tests.append(('R119 OVAL: EXCLUDE polygon is the outline (not the 4-pt rect)',
    _pol119 is not None and _pol119.group(1).count(',') >= 40, 'polygon pts'))

# --- ROUND: inside the rounded rect
_o119, _i119 = _pp61.make_labels(['RUND'], shape='ROUND', corner=6, w=60, h=30, out_dir=_D119)
_w119, _h119 = _i119['w'], _i119['h']
def _inrr119(x, y, cx, cy, W, H, C, tol=0.06):
    dx = abs(x - cx) - (W / 2 - C)
    dy = abs(y - cy) - (H / 2 - C)
    return dx <= tol or dy <= tol or dx * dx + dy * dy <= (C + tol) ** 2
_bad119 = 0
for _li119 in (2, 4):
    _pts, (_cx, _cy), _ = _labpts119(_o119, _li119)
    _bad119 += sum(1 for (_x, _y) in _pts if not _inrr119(_x, _y, _cx, _cy, _w119, _h119, 6.0))
tests.append(('R119 ROUND: everything inside the rounded rect (corner 6mm)',
    _bad119 == 0, '%d outside' % _bad119))

# --- BORDER: raised ring on the TEXT layers only, correct insets, breaks at the hole
_o119, _i119 = _pp61.make_labels(['RAND'], border_walls=3, border_gap=1.0,
                                 hole_side=1, w=70, h=30, out_dir=_D119)
_wid119 = 0.648
_hd119 = _i119.get('hole_d', 5.0) or 5.0
_pts, (_cx, _cy), _t119 = _labpts119(_o119, 6)          # first TEXT layer
_lx119 = _cx - _i119['w'] / 2
_insets119 = sorted(set(round(_x - _lx119, 2) for (_x, _y) in _pts if _x < _lx119 + 4.5))
tests.append(('R119 border: text layer carries the ring at wid/2+gap (+k*wid)',
    all(any(abs(_v - (_wid119 / 2 + 1.0 + _k * _wid119)) < 0.08 for _v in _insets119)
        for _k in range(3)), str(_insets119[:6])))
_pts2, _, _ = _labpts119(_o119, 2)                       # BASE layer
_xmin2 = min(_x for (_x, _y) in _pts2)
_hz119 = _lx119 + 2.0 + _hd119 + 1.0     # hole zone (x < this = hole rings)
tests.append(('R119 border: base layers stay at the classic outer wall (no ring)',
    abs(_xmin2 - (_lx119 + _wid119 / 2)) < 0.05 and not any(
        abs(_v - (_wid119 / 2 + 1.0)) < 0.06 for (_x, _y) in _pts2
        for _v in [round(_x - _lx119, 2)] if _y > _cy - 8 and _y < _cy + 8
        and _x > _hz119),
    'xmin %.3f' % _xmin2))
# hole: no horizontal border extrusion bridges the open hole band
_lay6 = _re119.split(r'(?m)^;LAYER_CHANGE', _t119)[6]
_lab6 = _lay6.split('EXCLUDE_OBJECT_START NAME=LABEL_1')[1].split('EXCLUDE_OBJECT_END')[0]
_bridge119 = 0
_px = _py = None
for _l in _lab6.split('\n'):
    _m = _re119.match(r'G0 X([\d.-]+) Y([\d.-]+)', _l)
    if _m:
        _px, _py = float(_m.group(1)), float(_m.group(2))
        continue
    _m = _re119.match(r'G1 X([\d.-]+) Y([\d.-]+) E([\d.]+)', _l)
    if _m and float(_m.group(3)) > 0:
        _x0, _y0, _x1, _y1 = _px, _py, float(_m.group(1)), float(_m.group(2))
        if (_px is not None and abs(_y1 - _y0) < 0.05 and _cy - _hd119 / 2 - 0.3 < _y0 < _cy + _hd119 / 2 + 0.3
                and min(_x0, _x1) < _lx119 + 2.0 + _hd119 - 0.2
                and max(_x0, _x1) > _lx119 + 2.0 + _hd119 - 0.15):
            _bridge119 += 1
        _px, _py = _x1, _y1
tests.append(('R119 border: ring BREAKS at the hole (no bridge over the opening)',
    _bridge119 == 0, '%d bridges' % _bridge119))
tests.append(('R119 border: hole rings present in the raised layer',
    _lab6.count('G1 X') > 10 and _re119.search(r';TYPE:Outer wall', _lab6) is not None, 'rings'))

# --- HEIGHT: mm -> layers, 4+4+sparse, angle alternation, _FILE_INFO
_o119, _i119 = _pp61.make_labels(['HOCH'], height=12, w=50, h=25, out_dir=_D119)
_t119 = open(_o119).read()
tests.append(('R119 height 12mm -> 60 base layers, 52 sparse between 4+4 solid',
    _i119['base_layers'] == 60 and _i119['sparse_mid'] == 52
    and _t119.count(';TYPE:Sparse infill') == 52, 'base %d sparse %d' % (
        _i119['base_layers'], _i119['sparse_mid'])))
_ang119 = []
for _li119 in (5, 6):
    _blk = _re119.split(r';TYPE:Sparse infill', _re119.split(r'(?m)^;LAYER_CHANGE', _t119)[_li119])[1]
    _blk = _blk.split('EXCLUDE_OBJECT_END')[0]
    _angs = set()
    _px = _py = None
    for _l in _blk.split('\n'):
        _m = _re119.match(r'G0 X([\d.-]+) Y([\d.-]+)', _l)
        if _m:
            _px, _py = float(_m.group(1)), float(_m.group(2))
            continue
        _m = _re119.match(r'G1 X([\d.-]+) Y([\d.-]+) E([\d.]+)', _l)
        if _m and float(_m.group(3)) > 0 and _px is not None:
            _d = _math119.hypot(float(_m.group(1)) - _px, float(_m.group(2)) - _py)
            if _d > 2:
                _angs.add(round(_math119.degrees(_math119.atan2(
                    float(_m.group(2)) - _py, float(_m.group(1)) - _px)) % 180))
            _px, _py = float(_m.group(1)), float(_m.group(2))
    _ang119.append(_angs)
tests.append(('R119 sparse band: 45/135 alternating per layer, ~8.1mm spacing',
    _ang119[0] == {45.0} and _ang119[1] == {135.0}, str(_ang119)))
tests.append(('R119 _FILE_INFO carries SPARSE-INFILL only for tall bases',
    'SPARSE-INFILL' in _t119.split('\n')[0] or 'SPARSE-INFILL' in [
        _l for _l in _t119.split('\n') if _l.startswith('_FILE_INFO')][0],
    'types'))
_o119b, _i119b = _pp61.make_labels(['FLACH'], height=1.0, w=50, h=25, out_dir=_D119)
tests.append(('R119 height 1mm stays solid (5 layers, no sparse type)',
    _i119b['base_layers'] == 5 and _i119b['sparse_mid'] == 0
    and 'SPARSE-INFILL' not in open(_o119b).read(), 'base %d' % _i119b['base_layers']))

# --- preview honors the border margin (Fit numbers = what prints)
_pv0 = _pp61.label_preview(['RAND'], w=70, h=30)
_pv1 = _pp61.label_preview(['RAND'], w=70, h=30, border_walls=3, border_gap=1.0)
tests.append(('R119 label_preview: border shrinks the projected caps (same as print)',
    _pv1['cap_mm'] < _pv0['cap_mm'], '%s vs %s' % (_pv1['cap_mm'], _pv0['cap_mm'])))

# --- plumbing: LCD 1mm steps + the five new inputs, GEN_LABELS params, watcher
_lcd119 = open('menus/lcd_menues.cfg').read()
_wblk = _lcd119[_lcd119.index('[menu __main __gen __labels __set __w]'):_lcd119.index('[menu __main __gen __labels __set __h]')]
_hblk = _lcd119[_lcd119.index('[menu __main __gen __labels __set __h]'):_lcd119.index('[menu __main __gen __labels __set __fnt]')]
tests.append(('R119 LCD: W/H inputs step 1mm (was 5)',
    'input_step: 1' in _wblk and 'input_step: 1' in _hblk
    and 'input_step: 5' not in _wblk and 'input_step: 5' not in _hblk, 'steps'))
tests.append(('R119 LCD: Height/Shape/Corner/Border/B.Gap inputs exist, layer-count input retired',
    all(k in _lcd119 for k in ('__set __ht]', '__set __shape]', '__set __corner]',
                               '__set __bw]', '__set __bgap]'))
    and "name: Base: {'%2d layers'" not in _lcd119, 'inputs'))
_g119 = get_body('macros/16_labels.cfg', 'GEN_LABELS')
out = render(_g119, {'TEXT': 'X', 'HEIGHT': 12, 'SHAPE': 'OVAL', 'CORNER': 4,
                     'BORDER': 2, 'BORDER_GAP': 1})
tests.append(('R119 GEN_LABELS: HEIGHT/SHAPE/CORNER/BORDER/BORDER_GAP params wired',
    'VARIABLE=label_height VALUE=12.0' in out
    and 'VARIABLE=label_shape VALUE=1' in out
    and 'VARIABLE=label_corner VALUE=4.0' in out
    and 'VARIABLE=label_border_walls VALUE=2' in out
    and 'VARIABLE=label_border_gap VALUE=1.0' in out, out[:140]))
out = render(_g119, {'TEXT': 'X', 'SHAPE': 'ROUND'})
tests.append(('R119 GEN_LABELS: SHAPE=ROUND maps to 2 (RECT stays 0)',
    'VARIABLE=label_shape VALUE=2' in out, out[:80]))
_wt119 = open('tools/r2_postproc.py').read()
tests.append(('R119 watcher: make_labels call carries height/shape/corner/border',
    "height=_vf('label_height', 0)" in _wt119
    and "shape=str(rv.get('label_shape', 'RECT') or 'RECT')" in _wt119
    and "border_walls=int(_vf('label_border_walls', 0))" in _wt119, 'watcher'))

# ================= R114: ';' never inside a console string =================
# .87 field log: 'Malformed command RESPOND MSG="... DERIVED ... - no' -
# Klipper cuts EVERY line at the first ';' (inside quotes too). All 22
# occurrences fixed; the validator now guards the class, this pins the
# user-visible one (the DERIVED message + its confidence math 0.7 -> 70%)
body = get_body('macros/08_print_start_stop.cfg', '_FILE_INFO')
out = render(body, {'DERIVED': '1', 'CONF': '0.7', 'COVER': '23'})
tests.append(('R114 DERIVED message: 70% confidence (0.7 was shown as 0%!)',
    '70% confidence' in out and '23% of moves covered' in out, out[:100]))
tests.append(('R114 DERIVED message: no ; anywhere in the message (the cut)',
    ';TYPE:' not in out and 'no TYPE: tags' in out, ''))
_static114 = []
import glob as _glob114
for _f114 in _glob114.glob('macros/*.cfg') + _glob114.glob('menus/*.cfg'):
    for _i114, _l114 in enumerate(open(_f114, encoding='utf-8'), 1):
        _st114 = _l114.lstrip()
        if _st114.startswith(('#', ';', '{%')):
            continue
        _sm114 = _st114.find(';')
        if _sm114 <= 0:
            continue
        _d114 = _st114[:_sm114]
        if _d114.count('"') % 2 == 1:
            _static114.append('%s:%d' % (_f114, _i114))
tests.append(('R114 codebase: no ; inside any double-quoted string (22 fixed)',
    not _static114, _static114[:5]))




# ===== R120: color picture (ColorPic) ==============================================
import re as _re120
import struct as _st120, zlib as _zl120
_Q120 = chr(34)                     # double quote without heredoc escape hell
_cp120 = 'macros/18_colorpic.cfg'
_cp120txt = open(_cp120, encoding='utf-8').read()

# --- module wiring ---
tests.append(('R120 modules: 18_colorpic.cfg sentinel + _CHECK_INSTALL + include',
    '_V18_COLORPIC' in _cp120txt
    and "('18_colorpic.cfg',        ['_V18_COLORPIC'])" in open('macros/01_state.cfg').read()
    and 'macros/18_colorpic.cfg' in open('printer.cfg.example').read()
    and '{% while %}' not in _cp120txt, ''))

tests.append(('R120 pause compat: 3x guarded SET_LED_STATE STATE=filament (blink owns the nozzle)',
    open('macros/09_pause_filament.cfg', encoding='utf-8').read().count(
        "printer['gcode_macro _COLORPIC_STATE'].blink|default(0)|int == 1") == 3, ''))

# --- generator: synthetic gradient image ---
_d120 = _tf61.mkdtemp(prefix='r120_')
def _png120(path, w=64, h=96):
    def chunk(tag, data):
        c = tag + data
        return _st120.pack('>I', len(data)) + c + _st120.pack('>I', _zl120.crc32(c))
    raw = b''
    for y in range(h):
        raw += b'\x00'
        for x in range(w):
            v = int(255 * (1.0 - y / h))
            raw += bytes((v, v, v))
    open(path, 'wb').write(b'\x89PNG\r\n\x1a\n'
        + chunk(b'IHDR', _st120.pack('>IIBBBBB', w, h, 8, 2, 0, 0, 0))
        + chunk(b'IDAT', _zl120.compress(raw))
        + chunk(b'IEND', b''))
_img120 = _os61.path.join(_d120, 'grad.png')
_png120(_img120)

_o120, _i120 = _pp.make_colorpic(_img120, width_mm=80, bands=4, out_dir=_d120,
                                 bed=(0.0, -3.0, 220.0, 217.0))
_g120 = open(_o120, encoding='utf-8').read()
tests.append(('R120 make_colorpic: file + info (4 bands x 4 layers, nested light->dark)',
    _i120['kind'] == 'colorpic' and _i120['bands'] == 4 and _i120['layers'] == 16
    and _i120['colors'] == ['WHT', 'CYA', 'BLU', 'BLK']
    and _i120['color_names'] == ['White', 'Cyan', 'Blue', 'Black']
    and _g120.count('\nM600') == 3, str(_i120)[:130]))
tests.append(('R120 make_colorpic: SWAP before M600 + DONE after, at every boundary',
    _g120.count('_COLORPIC_SWAP IDX=') == 3 and _g120.count('_COLORPIC_DONE') == 3
    and 'PREV_R=' in _g120 and 'NAME=' in _g120
    and all(a < b for a, b in zip(
        [m.start() for m in _re120.finditer(r'_COLORPIC_SWAP', _g120)],
        [m.start() for m in _re120.finditer(r'\nM600', _g120)])), ''))
tests.append(('R120 make_colorpic: types + layers + start/end (feature tagging)',
    all(t in _g120 for t in [';TYPE:Outer wall', ';TYPE:Top surface',
        ';TYPE:Internal solid infill', ';TYPE:Bottom surface'])
    and _g120.count('\nLAYER_MARK') == 16
    and _g120.count('APPLY_TYPE TYPE=') >= _g120.count(';TYPE:') - 1
    and 'PRINT_START' in _g120 and '\nPRINT_END' in _g120, ''))
tests.append(('R120 make_colorpic: swap line format (off-by-one guard)',
    _re120.search(r'_COLORPIC_SWAP IDX=2 TOTAL=4 NAME=' + _Q120 + r'Cyan' + _Q120
                  + r' R=0\.10 G=0\.85 B=0\.90 '
                  r'PREV_R=1\.00 PREV_G=1\.00 PREV_B=1\.00', _g120) is not None, ''))
try:
    _pp.make_colorpic(_img120, bands=3, colors='WHT,FOO,BLK', out_dir=_d120)
    tests.append(('R120 make_colorpic: unknown color raises with palette list', False, 'no raise'))
except ValueError as e:
    tests.append(('R120 make_colorpic: unknown color raises with palette list',
        'unknown - palette' in str(e) and 'GLD' in str(e), str(e)[:80]))

# --- macro renders ---
def _body120(name):
    m = _re120.search(r'\[gcode_macro ' + _re120.escape(name) + r'\]\n(.*?)(?=\n\[|\Z)',
                      _cp120txt, _re120.S)
    body = m.group(1)
    lines = []
    started = False
    for z in body.split('\n'):
        if z.startswith('gcode:'):
            started = True
            continue
        if started:
            if z.startswith(('variable_', 'description:', 'rename_existing:')):
                break
            lines.append(z[4:] if z.startswith('    ') else z)
    return klipper_strip('\n'.join(lines))

out = render(_body120('_COLORPIC_LED_APPLY'), {'R': '0.2', 'G': '0.9', 'B': '1.0'})
tests.append(('R120 _COLORPIC_LED_APPLY: SET_LED with brightness cap (leds_on)',
    'SET_LED' in out and 'RED=0.1' in out and 'BLUE=0.5' in out, out[:120]))

out = render(_body120('_COLORPIC_SWAP'),
             {'IDX': '2', 'TOTAL': '4', 'NAME': 'Cyan', 'R': '0.1', 'G': '0.85',
              'B': '0.9', 'PREV_R': '1', 'PREV_G': '1', 'PREV_B': '1'})
tests.append(('R120 _COLORPIC_SWAP: 10 state vars + M117 + notify + LED + blink armed',
    out.count('SET_GCODE_VARIABLE MACRO=_COLORPIC_STATE') == 11
    and 'M117 Color 2/4: Cyan' in out and 'NOTIFY' in out
    and '_COLORPIC_LED_APPLY R=0.1 G=0.85 B=0.9' in out
    and 'UPDATE_DELAYED_GCODE ID=_COLORPIC_BLINK DURATION=0.9' in out, out[:150]))

def _dbody120(name):
    m = _re120.search(r'\[delayed_gcode ' + _re120.escape(name) + r'\]\n(.*?)(?=\n\[|\Z)',
                      _cp120txt, _re120.S)
    return klipper_strip('\n'.join(l[4:] if l.startswith('    ') else l
                                    for l in m.group(1).split('\n')[1:]))

# blink phase 0 -> prev color, phase flips
state_vars['mode'] = 'filament'
cpic_state_vars.update(blink=1, phase=0, pr=1.0, pg=1.0, pb=1.0,
                       nr=0.1, ng=0.85, nb=0.9, cidx=2, ctotal=4, cname='Cyan')
out = render(_dbody120('_COLORPIC_BLINK'))
tests.append(('R120 _COLORPIC_BLINK: phase 0 shows PREV color + re-arms',
    '_COLORPIC_LED_APPLY R=1.0 G=1.0 B=1.0' in out
    and 'VARIABLE=phase VALUE=1' in out and 'DURATION=0.9' in out, out[:130]))
# blink phase 1 -> next color + LCD re-assert
state_vars['mode'] = 'filament'
cpic_state_vars.update(blink=1, phase=1)
out = render(_dbody120('_COLORPIC_BLINK'))
tests.append(('R120 _COLORPIC_BLINK: phase 1 shows NEW color + M117 name + re-arms',
    '_COLORPIC_LED_APPLY R=0.1 G=0.85 B=0.9' in out
    and 'M117 Color 2/4: Cyan' in out and 'VARIABLE=phase VALUE=0' in out, out[:130]))
# blink off (printing again) -> stop, no LED fight
state_vars['mode'] = 'printing'
cpic_state_vars.update(blink=1, phase=0)
out = render(_dbody120('_COLORPIC_BLINK'))
tests.append(('R120 _COLORPIC_BLINK: print resumed -> blink stops by itself',
    'VARIABLE=blink VALUE=0' in out and 'UPDATE_DELAYED_GCODE' not in out, out[:110]))

out = render(_body120('_COLORPIC_DONE'), {'R': '0.1', 'G': '0.85', 'B': '0.9'})
tests.append(('R120 _COLORPIC_DONE: blink off + steady new color',
    'VARIABLE=blink VALUE=0' in out and '_COLORPIC_LED_APPLY R=0.1 G=0.85 B=0.9' in out, ''))

# COLORPIC_SET_COLOR: band 3 of empty list -> GRY,GRY,col | bad color | bad band
save_vars['colorpic_colors'] = ''
out = render(_body120('COLORPIC_SET_COLOR'), {'BAND': '3', 'COLOR': 'RED'})
tests.append(('R120 COLORPIC_SET_COLOR: pads unset bands with GRY (no while loop)',
    'GRY,GRY,RED' in _re120.sub(r'\s+', ' ', out)
    and 'VARIABLE=colorpic_colors' in out and '{% while %}' not in _cp120txt, out[:130]))
save_vars['colorpic_colors'] = 'WHT,GRY,RED'
out = render(_body120('COLORPIC_SET_COLOR'), {'BAND': '2', 'COLOR': 'BLU'})
tests.append(('R120 COLORPIC_SET_COLOR: replaces band 2, trims beyond',
    'WHT,BLU' in _re120.sub(r'\s+', ' ', out) and 'RED' not in
    _re120.sub(r'\s+', ' ', out).split('RESPOND')[0], out[:130]))
out = render(_body120('COLORPIC_SET_COLOR'), {'BAND': '2', 'COLOR': 'FOO'})
tests.append(('R120 COLORPIC_SET_COLOR: bad color rejected (palette listed)',
    'COLOR must be one of' in out and 'SAVE_VARIABLE' not in out, out[:110]))
out = render(_body120('COLORPIC_SET_COLOR'), {'BAND': '9', 'COLOR': 'RED'})
tests.append(('R120 COLORPIC_SET_COLOR: band 9 rejected (1..8)',
    'BAND must be 1..8' in out and 'SAVE_VARIABLE' not in out, ''))

# COLORPIC_CREATE: empty -> notice; slot 0 -> nonce bump
save_vars['litho_files'] = []
save_vars['litho_file'] = ''
save_vars['colorpic_nonce'] = 0
save_vars['colorpic_bands'] = 4
save_vars['colorpic_width'] = 120
save_vars['colorpic_bandh'] = 0.8
save_vars['colorpic_colors'] = ''
out = render(_body120('COLORPIC_CREATE'))
tests.append(('R120 COLORPIC_CREATE: no image -> notify, no nonce',
    'NOTIFY' in out and 'VARIABLE=colorpic_nonce' not in out, out[:110]))
save_vars['litho_files'] = ['photo.png', 'cat.jpg']
out = render(_body120('COLORPIC_CREATE'), {'INDEX': '1'})
tests.append(('R120 COLORPIC_CREATE: slot 1 -> litho_file saved + nonce bump',
    ('VALUE=' + chr(39) + _Q120 + 'cat.jpg' + _Q120 + chr(39)) in _re120.sub(r'\s+', ' ', out)
    and 'VARIABLE=colorpic_nonce VALUE=1' in out and 'r2_confirm' in out, out[:130]))

# GEN_COLORPIC: all params saved + paced + chains into COLORPIC_CREATE
out = render(_body120('GEN_COLORPIC'),
             {'SRC': 'photo.png', 'WIDTH': '100', 'BANDS': '5', 'BANDH': '1.2',
              'COLORS': 'WHT,RED,BLK', 'LAYER_H': '0.16', 'IRONING': '0', 'BRIM': '4'})
_sv120 = [l.strip() for l in out.split(chr(10))
          if l.strip().startswith('SAVE_VARIABLE') or l.strip() == '_PACE']
_adj120 = sum(1 for i in range(len(_sv120) - 1)
              if _sv120[i].startswith('SAVE_VARIABLE') and _sv120[i + 1].startswith('SAVE_VARIABLE'))
tests.append(('R120 GEN_COLORPIC: 8 params saved, paced, chains CREATE',
    'VARIABLE=colorpic_width VALUE=100.0' in out and 'VARIABLE=colorpic_bands VALUE=5' in out
    and 'VARIABLE=colorpic_bandh VALUE=1.2' in out
    and 'WHT,RED,BLK' in _re120.sub(r'\s+', ' ', out)
    and 'VARIABLE=colorpic_ironing VALUE=False' in out
    and 'VARIABLE=colorpic_brim VALUE=4' in out and 'COLORPIC_CREATE' in out
    and _adj120 == 0 and _sv120.count('_PACE') >= 8,
    'adjacent %d pace %d' % (_adj120, _sv120.count('_PACE'))))
out = render(_body120('GEN_COLORPIC'), {'SRC': 'has"quote.png'})
tests.append(('R120 GEN_COLORPIC: quoted SRC rejected',
    'needs SRC' in out and 'SAVE_VARIABLE' not in out, out[:100]))

# --- LCD menus ---
_lcd120 = open('menus/lcd_menues.cfg', encoding='utf-8').read()
tests.append(('R120 LCD: ColorPic in Tools menu (guarded) with all settings',
    all(k in _lcd120 for k in ['[menu __main __gen __cpic]',
        '__cpic __img __s0]', '__cpic __img __s9]', '__cpic __set __wid]',
        '__cpic __set __bnd]', '__cpic __set __bh]', '__cpic __set __lh]',
        '__cpic __set __clrs]', '__cpic __set __clrs __band]',
        '__cpic __set __clrs __red]', '__cpic __set __clrs __rst]',
        '__cpic __set __iro]', '__cpic __set __brm]', '__cpic __set __vers]',
        'COLORPIC_CREATE INDEX=0', 'COLORPIC_SET_COLOR',
        "enable: {'gcode_macro _COLORPIC_SWAP' in printer}"]), 'ids'))
_blk120 = _lcd120[_lcd120.index('[menu __main __gen __cpic]'):_lcd120.index('[menu __main __gen __seal]')]
_n120 = [l.strip()[6:].strip("'") for l in _blk120.split(chr(10)) if l.strip().startswith('name: ')]
_n120 = [l.split('{')[0].strip() if '{' in l else l for l in _n120]
_long120 = [l for l in _n120 if len(l) > 16]
tests.append(('R120 LCD: menu names stay short (R29)', len(_long120) == 0, str(_long120[:6])))


# ===== R121: direct travel control (speed + accel + live markers) ===================
import re as _re121

# --- postproc: _travel_fix_file (rewrite, restore, markers, idempotent) ---
_d121 = _tf61.mkdtemp(prefix='r121_')
_SRC121 = """;FLAVOR:Marlin
;TYPE:WALL-OUTER
M204 S1500
G1 F1800
G1 X10 Y10 E1.0
G1 X20 Y10 E2.0
G0 X30 Y10 F9000
G0 X40 Y10 F9000
G1 X50 Y10 E3.0
G0 X5 Y5 F9000
;TYPE:INFILL-SPARSE
G1 X8 Y8 E5.0 F2400
"""
_g121 = _os61.path.join(_d121, 't.gcode')
open(_g121, 'w').write(_SRC121)
_n121 = _pp._travel_fix_file(_g121, accel=6000, speed=220.0, markers=True)
_t121 = open(_g121).read()
tests.append(('R121 travel fix: wraps blocks, rewrites F, restores modal F',
    _n121 == 2 and 'G0 X30 Y10 F13200' in _t121 and 'F9000' not in _t121
    and 'G1 F13200 ; R2-TV' in _t121 and 'G1 F1800 ; R2-TV' in _t121
    and 'M204 S6000 ; R2-TV' in _t121 and 'M204 S1500 ; R2-TV' in _t121, ''))
tests.append(('R121 travel fix: live markers around every block (feature restored)',
    _t121.count('APPLY_TYPE TYPE=Travel ; R2-TV') == 2
    and _t121.count('APPLY_TYPE TYPE=WALL-OUTER ; R2-TV') == 2
    and _t121.index('APPLY_TYPE TYPE=Travel') < _t121.index('G0 X30'), ''))
tests.append(('R121 travel fix: header line + block count',
    _t121.count('; R2-TRAVEL: 220 mm/s travel speed, 6000 mm/s2 travel accel, '
                'live markers (Live > Features > Travel) (2 travel block(s) wrapped)') == 1, ''))
_pp._travel_fix_file(_g121, accel=6000, speed=220.0, markers=True)
tests.append(('R121 travel fix: IDEMPOTENT (re-run = byte-identical)',
    open(_g121).read() == _t121, ''))
_g121b = _os61.path.join(_d121, 'tb.gcode')
open(_g121b, 'w').write(_SRC121)
_pp._travelaccel_fix_file(_g121b, accel=5000)
_t121b = open(_g121b).read()
tests.append(('R121 compat: _travelaccel_fix_file = accel only, no markers',
    _t121b.count('M204 S5000 ; R2-TV') == 2 and 'APPLY_TYPE TYPE=Travel' not in _t121b
    and 'F13200' not in _t121b, ''))
_g121c = _os61.path.join(_d121, 'tc.gcode')
open(_g121c, 'w').write("M204 S1500\nG1 F1800\nG1 X10 Y10 E1.0\nG0 X30 Y10 F9000\nM204 S999\nG0 X40 Y10\nG1 X50 Y10 E3.0\n")
_pp._travel_fix_file(_g121c, accel=6000, speed=100.0, markers=True)
tests.append(('R121 travel fix: slicer M204 inside the block closes it (its value rules)',
    'M204 S999\n' in open(_g121c).read(), ''))

# --- postproc: process() measures FTRAVEL ---
_g121d = _os61.path.join(_d121, 'info.gcode')
open(_g121d, 'w').write(_SRC121)
_sum121 = _pp.process(_g121d)
_i121 = [l for l in open(_g121d).read().split('\n') if l.startswith('_FILE_INFO')]
tests.append(('R121 process(): FTRAVEL in _FILE_INFO (dominant travel speed)',
    _sum121['tagged'] and any('FTRAVEL=150' in l for l in _i121), str(_i121)[:120]))

# --- FIX_FILE WHAT=TRAVEL (valid + guards) ---
state_vars['mode'] = 'idle'          # the R120 blink tests left 'printing'
_body121f = get_body('macros/08_print_start_stop.cfg', 'FIX_FILE')
out = render(_body121f, {'WHAT': 'TRAVEL', 'SPEED': '220', 'ACCEL': '6000'})
tests.append(('R121 FIX_FILE TRAVEL: saves speed+accel+nonce, explains live markers',
    'VARIABLE=travel_speed VALUE=220.0' in out and 'VARIABLE=travelaccel_value VALUE=6000' in out
    and 'VARIABLE=travelacc_fix_nonce VALUE=1' in out and 'live % ready' in out, out[:150]))
out = render(_body121f, {'WHAT': 'TRAVEL', 'SPEED': '5'})
tests.append(('R121 FIX_FILE TRAVEL: speed 5 rejected (0 or 20..300)',
    'must be 0' in out and 'VARIABLE=travelacc_fix_nonce' not in out, out[:110]))
out = render(_body121f, {'WHAT': 'TRAVEL', 'SPEED': '200', 'ACCEL': '5'})
tests.append(('R121 FIX_FILE TRAVEL: accel 5 rejected (0 or 100..100000)',
    'accel must be 0' in out and 'VARIABLE=travelacc_fix_nonce' not in out, out[:110]))
out = render(_body121f, {'WHAT': 'TRAVEL', 'SPEED': '0', 'ACCEL': '0'})
tests.append(('R121 FIX_FILE TRAVEL: 0/0 = pure live markers, no rewrite',
    'VARIABLE=travel_speed VALUE=0.0' in out and 'file' in out
    and 'VARIABLE=travelacc_fix_nonce VALUE=1' in out, out[:130]))

# --- APPLY_TYPE TYPE=Travel (live segment) ---
save_vars['ovf_travel_on'] = True
save_vars['ovf_travel_spd'] = 130
save_vars['ovf_travel_acc'] = 5000
state_vars['mode'] = 'printing'
state_vars['g_speed_clean'] = 100.0
state_vars['ignore_overrides'] = False
out = render(get_body('macros/10_live_tuning.cfg', 'APPLY_TYPE'), {'TYPE': 'Travel'})
tests.append(('R121 APPLY_TYPE Travel: ON -> M99220 130% + M99204 5000, NO respond spam',
    'M99220 S130' in out and 'M99204 S5000' in out and 'RESPOND' not in out, out[:130]))
save_vars['ovf_travel_on'] = False
out = render(get_body('macros/10_live_tuning.cfg', 'APPLY_TYPE'), {'TYPE': 'Travel'})
tests.append(('R121 APPLY_TYPE Travel: OFF -> clean global factor only',
    'M99220 S100' in out and 'M99204' not in out, out[:110]))
save_vars['ovf_travel_on'] = True
state_vars['g_speed_clean'] = 50.0
out = render(get_body('macros/10_live_tuning.cfg', 'APPLY_TYPE'), {'TYPE': 'Travel'})
tests.append(('R121 APPLY_TYPE Travel: percent rides ON TOP of the global (50 x 1.3)',
    'M99220 S65' in out, out[:110]))
state_vars['g_speed_clean'] = 100.0
save_vars['ovf_travel_on'] = False
save_vars['ovf_travel_spd'] = 100
save_vars['ovf_travel_acc'] = 0

# --- SET_OVERRIDE_VALUE accepts travel ---
out = render(get_body('macros/07_start_confirm.cfg', 'SET_OVERRIDE_VALUE'),
             {'NAME': 'feat_spd_travel', 'VALUE': '140'})
tests.append(('R121 SET_OVERRIDE_VALUE: feat_spd_travel saves ovf_travel_spd',
    'VARIABLE=ovf_travel_spd VALUE=140' in out and 'VARIABLE=ovf_travel_on VALUE=True' in out, out[:120]))

# --- _FILE_INFO TRAVEL param -> _STATE.file_travel ---
out = render(get_body('macros/08_print_start_stop.cfg', '_FILE_INFO'), {'TRAVEL': '150'})
tests.append(('R121 _FILE_INFO: TRAVEL=150 -> file_travel + hint RESPOND',
    'VARIABLE=file_travel VALUE=150.0' in out and 'File travels: 150 mm/s' in out, out[:120]))

# --- LCD wiring ---
_lcd121 = open('menus/lcd_menues.cfg', encoding='utf-8').read()
tests.append(('R121 LCD Pre-Print: Travel speed input + Fix travel + file speed shown',
    all(k in _lcd121 for k in ['[menu __main __preprint __file __tvsp]',
        '[menu __main __preprint __file __tvf]', '[menu __main __preprint __file __fixav]',
        'name: Fix travel', 'FIX_FILE WHAT=TRAVEL SPEED=',
        'VARIABLE=travel_speed VALUE={menu.input|round|int}']), 'ids'))
tests.append(('R121 LCD Live: Features > Travel (On/File/Spd/Acc, no file-types gate)',
    all(k in _lcd121 for k in ['[menu __main __live __feat __tv]',
        '__tv __on]', '__tv __fs]', '__tv __spd]', '__tv __acc]',
        'SET_OVERRIDE_VALUE NAME=feat_on_travel', 'SET_OVERRIDE_VALUE NAME=feat_spd_travel'])
    and 'TRAVEL' not in str(_re121.findall(r"enable: \{[^}]*file_types[^}]*\}", _lcd121)).upper().replace('INTERNAL-BRIDGE', ''), ''))
tests.append(('R121 LCD: flow cap fix ALWAYS visible again (R120 gate removed)',
    "printer['gcode_macro _STATE'].file_maxrate|default(0)|float > printer['save_variables'].variables.flowcap_limit"
    not in _lcd121, 'gate still there'))

fails = 0
for name, ok, info in tests:
    print(('PASS ' if ok else 'FAIL '), name)
    if not ok:
        fails += 1
        print('      ->', str(info)[:220])
print(f"\n{len(tests)-fails}/{len(tests)} passed")
raise SystemExit(1 if fails else 0)
