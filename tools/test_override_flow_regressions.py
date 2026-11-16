#!/usr/bin/env python3
"""Offline regressions for override activation and flow-calibration targets.

No commands are sent to Klipper. When the pinned Klipper parser reference is
available, the render is dispatched to a handler that writes to a Python dict.
Otherwise parser-dispatch tests are explicitly skipped (never reported as pass).
"""
import ast
import configparser
import hashlib
import io
import importlib.util
import json
from pathlib import Path
import re
import shutil
import subprocess
from types import SimpleNamespace
import unittest

from jinja2 import Environment

ROOT = Path(__file__).resolve().parents[1]
REF = ROOT / 'analyse/klipper-referenz/gcode.py'
REF_HASH = 'a2bcd6949b4263f608eaa71ba1cdfb713553542b7b90de739241b624f06415ae'
ENV = Environment(variable_start_string='{', variable_end_string='}')
KEYS = ('bed', 'bed_after', 'hotend_first', 'hotend_after', 'pa', 'retract_len',
        'retract_speed', 'unretract_speed', 'accel', 'ironing_flow', 'pa_smooth',
        'flow', 'velocity', 'min_cruise', 'square_corner', 'fan')


class Obj(dict):
    def __getattr__(self, key):
        try: return self[key]
        except KeyError as exc: raise AttributeError(key) from exc


def section(file, name, kind='gcode_macro'):
    source = (ROOT / file).read_text(encoding='utf-8')
    return source.split('[' + kind + ' ' + name + ']', 1)[1].split('\n[', 1)[0]


def template(file, name, kind='gcode_macro'):
    return ENV.from_string(section(file, name, kind).split('\ngcode:\n', 1)[1])


def printer(sv, nozzle=0.4):
    return Obj({'save_variables': SimpleNamespace(variables=sv),
                'configfile': SimpleNamespace(settings=Obj({'extruder': {'nozzle_diameter': nozzle}}))})


def render(t, sv, params=None, nozzle=0.4, menu=None):
    return t.render(printer=printer(sv, nozzle), params=Obj(params or {}), menu=menu)


def active_lines(text):
    return [x.strip() for x in text.splitlines() if x.strip() and not x.lstrip().startswith('#')]


class RenderRegressionTests(unittest.TestCase):
    def test_changed_cfg_sections_parse_and_compile_like_klipper(self):
        sections = [('macros/02_sounds.cfg', 'gcode_macro M300'),
                    ('macros/07_start_confirm.cfg', 'gcode_macro SET_OVERRIDE_VALUE'),
                    ('macros/12_maintenance.cfg', 'gcode_macro FLOW_CAL'),
                    ('macros/12_maintenance.cfg', 'gcode_macro CALIBRATE_PA'),
                    ('macros/08_print_start_stop.cfg', 'gcode_macro PRINT_START'),
                    ('macros/06_temp_controls.cfg', 'gcode_macro PAUSE_AT_LAYER'),
                    ('macros/12_maintenance.cfg', 'gcode_macro IRONING_CAL'),
                    ('macros/12_maintenance.cfg', 'gcode_macro IRONING_RESULT'),
                    ('menus/lcd_menues.cfg', 'menu __main __maint __flow __targ'),
                    ('menus/lcd_menues.cfg', 'menu __main __maint __iron __how')]
        for file, header in sections:
            with self.subTest(section=header):
                data = (ROOT / file).read_text(encoding='utf8').replace('\r\n', '\n')
                data = '\n'.join(line.split('#', 1)[0] for line in data.split('\n'))
                parser = configparser.RawConfigParser(strict=False, inline_comment_prefixes=(';', '#'))
                parser.read_file(io.StringIO(data))
                self.assertIn('gcode', parser[header])
                ENV.from_string(parser[header]['gcode'])
                if 'input' in parser[header]: ENV.from_string(parser[header]['input'])

    def test_m300_optional_beeper_and_mutation(self):
        body = section('macros/02_sounds.cfg', 'M300').split('\ngcode:\n', 1)[1]
        tone = ENV.from_string(body)
        for devices, expected in ((Obj(), False), (Obj({'output_pin beeper': {}}), False),
                                  (Obj({'pwm_cycle_time beeper': {}}), True)):
            with self.subTest(devices=devices):
                out = active_lines(tone.render(printer=devices, params=Obj({'S': '1000', 'P': '40'})))
                pins = [line for line in out if line.startswith('SET_PIN ')]
                self.assertEqual(2 if expected else 0, len(pins))
                self.assertEqual(expected, any(line == 'G4 P40' for line in out))
        guard = "'pwm_cycle_time beeper' in printer"
        self.assertEqual(1, body.count(guard))
        mutant = ENV.from_string(body.replace(guard, 'True'))
        out = active_lines(mutant.render(printer=Obj(), params=Obj()))
        with self.assertRaises(AssertionError):
            self.assertFalse(any(line.startswith('SET_PIN ') for line in out))

    def test_flow_old_target_mutation_is_caught(self):
        body = section('macros/12_maintenance.cfg', 'FLOW_CAL').split('\ngcode:\n', 1)[1]
        new = 'params.TARGET|default(sv.flow_cal_target|default(noz))|float'
        self.assertEqual(1, body.count(new))
        mutated = ENV.from_string(body.replace(new, 'params.TARGET|default(noz)|float'))
        lines = active_lines(render(mutated, Obj({'flow_cal_target': 0.6}), {'MEASURE': '0.5'}))
        self.assertIn('SAVE_VARIABLE VARIABLE=flow_cal_result VALUE=80.0', lines)
        with self.assertRaises(AssertionError):
            self.assertIn('SAVE_VARIABLE VARIABLE=flow_cal_result VALUE=120.0', lines)

    def test_scalar_setters_render_separate_commands_in_order(self):
        setter = template('macros/07_start_confirm.cfg', 'SET_OVERRIDE_VALUE')
        for key in KEYS:
            for prior in (False, True):
                with self.subTest(key=key, prior=prior):
                    sv = Obj({'ov_' + key + '_on': prior})
                    lines = active_lines(render(setter, sv, {'NAME': key, 'VALUE': '42'}))
                    value = 'SAVE_VARIABLE VARIABLE=ov_%s VALUE=42.0' % key
                    flag = 'SAVE_VARIABLE VARIABLE=ov_%s_on VALUE=True' % key
                    self.assertIn(value, lines)
                    self.assertIn(flag, lines)
                    self.assertLess(lines.index(value), lines.index(flag))
                    self.assertFalse(any('; SAVE_VARIABLE' in line for line in lines))
                    if key in ('retract_len', 'retract_speed', 'unretract_speed'):
                        self.assertLess(lines.index(flag), lines.index('_APPLY_OV_RETRACT'))
                    if key == 'accel': self.assertLess(lines.index(flag), lines.index('_SYNC_OV_ACCEL'))

    def test_feature_and_alias_setters_remain_distinct(self):
        setter = template('macros/07_start_confirm.cfg', 'SET_OVERRIDE_VALUE')
        cases = [('outer_wall', 'ovf_wallouter_spd', 'ovf_wallouter_on'),
                 ('feat_spd_ironing', 'ovf_ironing_spd', 'ovf_ironing_on'),
                 ('feat_flw_support', 'ovf_support_flw', 'ovf_support_on')]
        for name, value, flag in cases:
            with self.subTest(name=name):
                lines = active_lines(render(setter, Obj(), {'NAME': name, 'VALUE': '42'}))
                self.assertIn('SAVE_VARIABLE VARIABLE=%s VALUE=42.0' % value, lines)
                self.assertIn('SAVE_VARIABLE VARIABLE=%s VALUE=True' % flag, lines)

    def test_invalid_name_and_missing_value_do_not_save(self):
        setter = template('macros/07_start_confirm.cfg', 'SET_OVERRIDE_VALUE')
        for params in ({'NAME': 'unknown', 'VALUE': '42'}, {'NAME': 'flow'}):
            with self.subTest(params=params):
                lines = active_lines(render(setter, Obj(), params))
                self.assertFalse(any(line.startswith('SAVE_VARIABLE ') for line in lines))
                self.assertTrue(any(line.startswith('NOTIFY ') for line in lines))

    def test_flow_target_explicit_then_saved_then_nozzle(self):
        flow = template('macros/12_maintenance.cfg', 'FLOW_CAL')
        cases = [(Obj({'flow_cal_target': 0.6}), {'MEASURE': '0.5'}, 0.4, 120),
                 (Obj({'flow_cal_target': 0.6}), {'MEASURE': '0.5', 'TARGET': '0.5'}, 0.4, 100),
                 (Obj(), {'MEASURE': '0.5'}, 0.4, 80),
                 (Obj(), {'MEASURE': '0.5'}, 0.6, 120)]
        for sv, params, nozzle, expected in cases:
            with self.subTest(sv=sv, params=params, nozzle=nozzle):
                lines = active_lines(render(flow, sv, params, nozzle))
                self.assertIn('SAVE_VARIABLE VARIABLE=flow_cal_result VALUE=%.1f' % expected, lines)

    def test_menu_target_defaults_to_current_nozzle(self):
        text = section('menus/lcd_menues.cfg', '__main __maint __flow __targ', 'menu')
        expression = next(line.split('input:', 1)[1].strip() for line in text.splitlines() if line.startswith('input:'))
        value = ENV.from_string(expression).render(printer=printer(Obj(), nozzle=0.6))
        self.assertEqual('0.6', value)
        value = ENV.from_string(expression).render(printer=printer(Obj({'flow_cal_target': 0.5}), nozzle=0.6))
        self.assertEqual('0.5', value)
        p = printer(Obj())
        del p.configfile.settings['extruder']
        self.assertEqual('0.4', ENV.from_string(expression).render(printer=p))

    @unittest.skipUnless(shutil.which('node'), 'Node required to test shipped Web evaluator')
    def test_web_fallback_target_and_ironing_help_match_lcd(self):
        html = (ROOT / 'web/index.html').read_text(encoding='utf8')
        match = re.search(r'^const EMBEDDED_MENU_JSON = (\{.*\});$', html, re.M)
        self.assertIsNotNone(match)
        docs = [json.loads((ROOT / 'web/menu_structure.json').read_text()), json.loads(match.group(1))]
        def find(node, target):
            if node.get('id') == target: return node
            for child in node.get('children', []):
                result = find(child, target)
                if result is not None: return result
            return None
        lcd = section('menus/lcd_menues.cfg', '__main __maint __flow __targ', 'menu')
        expr = next(line.split('input:', 1)[1].strip() for line in lcd.splitlines() if line.startswith('input:'))
        for doc in docs:
            target = find(doc['tree'], '__main __maint __flow __targ')
            self.assertIsNotNone(target)
            self.assertEqual(expr, target['input'])
            help_node = find(doc['tree'], '__main __maint __iron __how')
            self.assertTrue(any('no overrides applied' in line for line in help_node['gcode']))
        a, b = '// ==== R201 live evaluator', '// ==== end R201 live evaluator ===='
        js = html[html.index(a):html.index(b) + len(b)]
        js += '\nconst e=' + json.dumps(expr) + ';\n'
        js += '''
const p={'save_variables':{variables:{}},configfile:{settings:{extruder:{nozzle_diameter:0.6}}}};
if(evalName(e,p)!=='0.6')throw new Error('wrong nozzle');
p.save_variables.variables.flow_cal_target=0.5;
if(evalName(e,p)!=='0.5')throw new Error('wrong saved target');
delete p.save_variables.variables.flow_cal_target;delete p.configfile.settings.extruder;
if(evalName(e,p)!=='0.4')throw new Error('wrong fallback');
'''
        proc = subprocess.run(['node', '-'], input=js, text=True, capture_output=True)
        self.assertEqual(0, proc.returncode, proc.stderr)

    def test_print_start_declared_total_survives_live_reset_in_all_branches(self):
        start = template('macros/08_print_start_stop.cfg', 'PRINT_START')
        reset = template('macros/10_live_tuning.cfg', '_LIVE_RESET')
        rp = printer(Obj())
        rp.configfile.settings['printer'] = Obj({'max_accel': 3000})
        reset_lines = active_lines(reset.render(printer=rp, params=Obj()))
        self.assertIn('SET_GCODE_VARIABLE MACRO=_STATE VARIABLE=total_layers VALUE=0', reset_lines)
        cases = [('idle', '', 'standby', True), ('idle', '', 'standby', False),
                 ('waiting', 'as_sliced', 'printing', True), ('waiting', 'as_legacy', 'printing', True),
                 ('starting', '', 'standby', True)]
        for mode, pending, status, confirm in cases:
            with self.subTest(mode=mode, pending=pending, status=status, confirm=confirm):
                p = printer(Obj({'start_confirm': confirm}))
                p['gcode_macro _STATE'] = Obj({'mode': mode, 'start_pending': pending})
                p['print_stats'] = SimpleNamespace(state=status, filename='file.gcode')
                lines = active_lines(start.render(printer=p, params=Obj({'TOTAL_LAYERS': '251'})))
                def total_after(lines):
                    total = None
                    for line in lines:
                        if line == '_LIVE_RESET': total = 0  # actual nested reset's total_layers write
                        if line.startswith('SET_GCODE_VARIABLE MACRO=_STATE VARIABLE=total_layers VALUE='):
                            total = int(line.rsplit('=', 1)[1])
                    return total
                self.assertEqual(251, total_after(lines))
                self.assertLess(lines.index('_LIVE_RESET'), lines.index('SET_GCODE_VARIABLE MACRO=_STATE VARIABLE=total_layers VALUE=251'))
                mutant = lines[:]
                index = mutant.index('SET_GCODE_VARIABLE MACRO=_STATE VARIABLE=total_layers VALUE=251')
                mutant.remove(mutant[index]); mutant.insert(mutant.index('_LIVE_RESET'), 'SET_GCODE_VARIABLE MACRO=_STATE VARIABLE=total_layers VALUE=251')
                self.assertEqual(0, total_after(mutant))
        p = printer(Obj()); p['gcode_macro _STATE'] = Obj({'mode': 'printing', 'start_pending': ''})
        p['print_stats'] = SimpleNamespace(state='printing', filename='file.gcode')
        lines = active_lines(start.render(printer=p, params=Obj({'TOTAL_LAYERS': '251'})))
        self.assertNotIn('_LIVE_RESET', lines)  # existing duplicate-start guard remains

    def test_first_layer_pause_rejected_explicitly_not_silently_armed(self):
        t = template('macros/06_temp_controls.cfg', 'PAUSE_AT_LAYER')
        one = active_lines(render(t, Obj(), {'LAYER': '1'}))
        self.assertFalse(any(line.startswith('SAVE_VARIABLE ') for line in one))
        self.assertTrue(any('Layer 1 pause unsupported' in line for line in one))
        two = active_lines(render(t, Obj(), {'LAYER': '2'}))
        self.assertIn('SAVE_VARIABLE VARIABLE=pause_at_layer VALUE=2', two)

    def test_pa_calibration_respects_each_independent_retraction_flag(self):
        cal = template('macros/12_maintenance.cfg', 'CALIBRATE_PA')
        for mask in range(8):
            with self.subTest(mask=mask):
                sv = Obj({'ov_retract_len': 1.2, 'ov_retract_speed': 50,
                          'ov_unretract_speed': 60, 'ov_retract_on': True,
                          'ov_retract_len_on': bool(mask & 1),
                          'ov_retract_speed_on': bool(mask & 2),
                          'ov_unretract_speed_on': bool(mask & 4)})
                p = printer(sv)
                p['gcode_macro _STATE'] = SimpleNamespace(mode='idle')
                p['toolhead'] = SimpleNamespace(axis_maximum=SimpleNamespace(x=235, y=235), max_accel=4000)
                p['firmware_retraction'] = SimpleNamespace(retract_length=0.8, retract_speed=30, unretract_speed=25)
                p['bed_mesh'] = SimpleNamespace(profiles={}, profile_name='')
                lines = active_lines(cal.render(printer=p, params=Obj({'LINES': '3', 'BASE': '0'})))
                rl, rs, us = (1.2 if mask & 1 else 0.8), (50 if mask & 2 else 30), (60 if mask & 4 else 25)
                self.assertIn('G1 E-%s F%s.0' % (rl, rs * 60), lines)
                retractions = [line for line in lines if line.startswith('SET_RETRACTION ')]
                self.assertEqual(['SET_RETRACTION RETRACT_LENGTH=%s RETRACT_SPEED=%s UNRETRACT_SPEED=%s' % (rl, rs, us)] if mask else [], retractions)
        # No firmware retraction object: never emit SET_RETRACTION.
        del p['firmware_retraction']
        lines = active_lines(cal.render(printer=p, params=Obj({'LINES': '3', 'BASE': '0'})))
        self.assertFalse(any(line.startswith('SET_RETRACTION ') for line in lines))

    def test_invalid_measure_does_not_save_result(self):
        flow = template('macros/12_maintenance.cfg', 'FLOW_CAL')
        for measure in ('0', '0.05', '2.1'):
            lines = active_lines(render(flow, Obj({'flow_cal_target': 0.6}), {'MEASURE': measure}))
            self.assertFalse(any('VARIABLE=flow_cal_result' in line for line in lines))


@unittest.skipUnless(REF.exists(), 'pinned Klipper parser reference not provided; see analyse/klipper-referenz/QUELLE.md')
class ParserDispatchTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if hashlib.sha256(REF.read_bytes()).hexdigest() != REF_HASH:
            raise AssertionError('wrong pinned Klipper parser checksum')
        spec = importlib.util.spec_from_file_location('klipper_gcode_ref', REF)
        cls.ref = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cls.ref)

    def dispatcher(self, sv):
        ref = self.ref
        class Dispatcher(ref.GCodeDispatch):
            def __init__(self):
                self.events = []
                self.gcode_handlers = {'SAVE_VARIABLE': self.save}
                self.printer = SimpleNamespace(send_event=lambda *x: None, invoke_shutdown=lambda *x: None)
            def respond_info(self, *args, **kwargs): pass
            def respond_raw(self, *args, **kwargs): pass
            def _respond_error(self, msg): raise AssertionError(msg)
            def cmd_default(self, cmd): self.events.append(('stub', cmd.get_command()))
            def save(self, cmd):
                parsed = self._get_extended_params(cmd)
                key = parsed.get('VARIABLE')
                value = ast.literal_eval(parsed.get('VALUE'))
                sv[key] = value
                self.events.append(('save', key, value))
            def execute(self, text): self._process_commands(active_lines(text), need_ack=False)
        return Dispatcher()

    def test_all_scalar_branches_set_value_and_flag_through_real_parser(self):
        setter = template('macros/07_start_confirm.cfg', 'SET_OVERRIDE_VALUE')
        for key in KEYS:
            for prior in (False, True):
                with self.subTest(key=key, prior=prior):
                    sv = Obj({'ov_' + key + '_on': prior})
                    d = self.dispatcher(sv)
                    d.execute(render(setter, sv, {'NAME': key, 'VALUE': '42'}))
                    self.assertEqual(42, sv['ov_' + key])
                    self.assertIs(sv['ov_' + key + '_on'], True)
                    self.assertIn(('save', 'ov_' + key + '_on', True), d.events)

    def test_flow_result_to_override_dispatch(self):
        sv = Obj({'flow_cal_target': 0.6, 'ov_flow_on': False})
        flow = template('macros/12_maintenance.cfg', 'FLOW_CAL')
        apply = template('macros/12_maintenance.cfg', 'FLOW_CAL_APPLY')
        setter = template('macros/07_start_confirm.cfg', 'SET_OVERRIDE_VALUE')
        d = self.dispatcher(sv)
        d.execute(render(flow, sv, {'MEASURE': '0.5'}))
        self.assertEqual(120.0, sv['flow_cal_result'])
        call = next(line for line in active_lines(render(apply, sv)) if line.startswith('SET_OVERRIDE_VALUE '))
        args = dict(part.split('=', 1) for part in call.split()[1:])
        d.execute(render(setter, sv, args))
        self.assertEqual(120, sv['ov_flow'])
        self.assertIs(sv['ov_flow_on'], True)

    def test_ironing_snapshot_and_result_for_all_six_cards(self):
        cal = template('macros/12_maintenance.cfg', 'IRONING_CAL')
        result = template('macros/12_maintenance.cfg', 'IRONING_RESULT')
        sv = Obj({'iron_result_valid': True, 'iron_result_cards': 2})
        p = printer(sv)
        p['gcode_macro _STATE'] = SimpleNamespace(mode='idle')
        p['toolhead'] = SimpleNamespace(homed_axes='xyz', axis_maximum=SimpleNamespace(y=220))
        p['bed_mesh'] = SimpleNamespace(profiles={}, profile_name='')
        params = Obj({'CARDS': '6', 'START_LAYER': '1', 'WID': '2',
                      **{'F%d' % c: str(10 + c) for c in range(1, 7)},
                      **{'S%d' % c: str(30 + c) for c in range(1, 7)}})
        lines = active_lines(cal.render(printer=p, params=params))
        # Never dispatch movement/heater commands: only model the SAVE_VARIABLE lines.
        saves = [line for line in lines if line.startswith('SAVE_VARIABLE ')]
        self.assertEqual('SAVE_VARIABLE VARIABLE=iron_result_valid VALUE=False', saves[0])
        self.assertEqual('SAVE_VARIABLE VARIABLE=iron_result_valid VALUE=True', saves[-1])
        d = self.dispatcher(sv)
        d.execute('\n'.join(saves[:-1]))
        self.assertIs(sv['iron_result_valid'], False)
        interrupted = render(result, sv, {'CARD': '4'})
        self.assertIn('no completed card snapshot', interrupted)
        d.execute(saves[-1])
        for c in range(1, 7):
            with self.subTest(card=c):
                out = render(result, sv, {'CARD': str(c)})
                self.assertIn('flow %s.0%% of full line, speed %s.0mm/s' % (10+c, 30+c), out)
                self.assertFalse(any(line.startswith(('SET_OVERRIDE_VALUE ', 'SAVE_VARIABLE ')) for line in active_lines(out)))
        self.assertIn('CARD must be', render(result, sv, {'CARD': '7'}))
        del sv['iron_result_s4']
        self.assertIn('snapshot incomplete', render(result, sv, {'CARD': '4'}))

    def test_old_semicolon_mutation_is_caught_by_parser(self):
        body = section('macros/07_start_confirm.cfg', 'SET_OVERRIDE_VALUE').split('\ngcode:\n', 1)[1]
        old = 'SAVE_VARIABLE VARIABLE=ov_flow VALUE={v|float}\n            SAVE_VARIABLE VARIABLE=ov_flow_on VALUE=True'
        self.assertEqual(1, body.count(old))
        mutated = ENV.from_string(body.replace(old, old.replace('\n            ', ' ; ')))
        sv = Obj({'ov_flow_on': False})
        d = self.dispatcher(sv)
        d.execute(render(mutated, sv, {'NAME': 'flow', 'VALUE': '42'}))
        self.assertEqual(42, sv['ov_flow'])
        self.assertIs(sv['ov_flow_on'], False)
        with self.assertRaises(AssertionError):
            self.assertIs(sv['ov_flow_on'], True)


if __name__ == '__main__':
    unittest.main(verbosity=2)
