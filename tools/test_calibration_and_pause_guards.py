#!/usr/bin/env python3
"""Offline regressions for calibration, G28 mode restore, Z_TILT, and layer-pause guards.

All tests render real macro templates with Jinja2 and mock printer states; no
commands are sent to Klipper or any printer. Each bug class includes a counter-
mutation proving the test fails when the old bug is reintroduced.
"""
import configparser
from pathlib import Path
import re
import unittest

import jinja2

ROOT = Path(__file__).resolve().parents[1]


def load_macro(rel_path, section_name):
    cfg = configparser.RawConfigParser(
        delimiters=(':', '='), comment_prefixes=('#', ';'),
        inline_comment_prefixes=(), strict=False)
    cfg.optionxform = str
    cfg.read(ROOT / rel_path, encoding='utf-8')
    return cfg.get(section_name, 'gcode')


def render_gcode(body, printer, params=None, rawparams=''):
    env = jinja2.Environment(
        block_start_string='{%', block_end_string='%}',
        variable_start_string='{', variable_end_string='}',
        comment_start_string='{#', comment_end_string='#}')
    cleaned = '\n'.join(
        '' if ln.lstrip().startswith('#') else ln for ln in body.splitlines())
    out = env.from_string(cleaned).render(
        printer=printer, params=params or {}, rawparams=rawparams)
    return [ln.strip() for ln in out.splitlines() if ln.strip()]


class G28AndProbeGuardTests(unittest.TestCase):
    def _printer(self, mode='idle', saved_mode=''):
        return {
            'gcode_macro _STATE': {'mode': mode, 'led_quiet': False},
            'gcode_macro G28': {'saved_mode': saved_mode},
            'configfile': {'settings': {
                'stepper_z': {}, 'stepper_z1': {}, 'z_tilt': {},
            }},
            'save_variables': {'variables': {'zt_retries': 2, 'zt_tolerance': 0.05}},
            'toolhead': {'homed_axes': 'xyz'},
        }

    def test_g28_restores_entry_mode_not_stale_saved_mode(self):
        body = load_macro('macros/08_print_start_stop.cfg', 'gcode_macro G28')
        # First G28 after boot while PRINT_START has mode='starting' and saved_mode=''.
        lines = render_gcode(body, self._printer(mode='starting', saved_mode=''))
        mode_sets = [ln for ln in lines
                     if ln.startswith('SET_GCODE_VARIABLE MACRO=_STATE VARIABLE=mode ')]
        self.assertEqual(mode_sets, [
            'SET_GCODE_VARIABLE MACRO=_STATE VARIABLE=mode VALUE=\'"homing"\'',
            'SET_GCODE_VARIABLE MACRO=_STATE VARIABLE=mode VALUE=\'"starting"\'',
        ])
        self.assertIn('UPDATE_DELAYED_GCODE ID=_HOMING_GUARD_OFF DURATION=0', lines)
        # Subsequent manual G28 from 'idle' when saved_mode still holds old 'starting'.
        lines2 = render_gcode(body, self._printer(mode='idle', saved_mode='starting'))
        self.assertEqual(lines2[-1],
                         'SET_GCODE_VARIABLE MACRO=_STATE VARIABLE=mode VALUE=\'"idle"\'')
        # Re-entrant or blank mode normalizes to 'idle', never empty or stuck 'homing'.
        for edge in ('', 'homing'):
            el = render_gcode(body, self._printer(mode=edge, saved_mode=''))
            self.assertEqual(el[-1],
                             'SET_GCODE_VARIABLE MACRO=_STATE VARIABLE=mode VALUE=\'"idle"\'')

    def test_old_g28_saved_mode_read_mutation_is_caught(self):
        body = load_macro('macros/08_print_start_stop.cfg', 'gcode_macro G28')
        mutated = body.replace(
            'VALUE=\'"{cur}"\'\n',
            'VALUE=\'"{cur}"\'\n', 1)
        idx = mutated.rfind('VALUE=\'"{cur}"\'')
        self.assertGreater(idx, 0)
        mutated = (mutated[:idx]
                   + 'VALUE=\'"{printer[\'gcode_macro G28\'].saved_mode|default(\'idle\')}"\''
                   + mutated[idx + len('VALUE=\'"{cur}"\''):])
        lines = render_gcode(mutated, self._printer(mode='starting', saved_mode=''))
        self.assertEqual(lines[-1],
                         'SET_GCODE_VARIABLE MACRO=_STATE VARIABLE=mode VALUE=\'""\'')

    def test_homing_guard_off_clears_led_quiet_before_unlocking(self):
        body = load_macro('macros/08_print_start_stop.cfg',
                          'delayed_gcode _HOMING_GUARD_OFF')
        lines = render_gcode(body, self._printer(mode='homing'))
        self.assertIn('_LED_QUIET ON=0', lines)
        self.assertLess(lines.index('_LED_QUIET ON=0'),
                        lines.index('SET_GCODE_VARIABLE MACRO=_STATE VARIABLE=mode VALUE=\'"idle"\''))

    def test_z_tilt_brackets_probe_descent_with_led_quiet(self):
        body = load_macro('macros/11_gantry_sync.cfg', 'gcode_macro Z_TILT')
        lines = render_gcode(body, self._printer(mode='starting'), {'QUIET': '1'})
        on_i = lines.index('_LED_QUIET ON=1')
        zt_i = next(i for i, l in enumerate(lines) if l.startswith('Z_TILT_ADJUST'))
        off_i = lines.index('_LED_QUIET ON=0')
        self.assertLess(on_i, zt_i)
        self.assertLess(zt_i, off_i)


class CalibrationGuardTests(unittest.TestCase):
    def _printer(self, mode='idle', can_extrude=True, rd=33.5):
        return {
            'gcode_macro _STATE': {'mode': mode, 'pause_planned_reason': ''},
            'extruder': {'can_extrude': can_extrude, 'temperature': 210.0, 'target': 210.0},
            'heater_bed': {'temperature': 60.0, 'target': 60.0},
            'configfile': {'settings': {'extruder': {
                'rotation_distance': rd, 'nozzle_diameter': 0.4}}},
            'save_variables': {'variables': {}},
            'toolhead': {'max_accel': 3000, 'homed_axes': 'xyz',
                         'axis_minimum': type('A', (), {'x': 0.0, 'y': 0.0, 'z': -2.0})(),
                         'axis_maximum': type('A', (), {'x': 220.0, 'y': 220.0, 'z': 250.0})()},
            'bed_mesh': {'profiles': {}, 'profile_name': ''},
            'fan': {'speed': 0.0},
        }

    def test_extruder_cal_blocks_printing_cold_and_invalid_measured(self):
        body = load_macro('macros/12_maintenance.cfg', 'gcode_macro CALIBRATE_EXTRUDER')
        # Blocked during printing for both extrude and result.
        out_p = render_gcode(body, self._printer(mode='printing'), {'STEP': 'extrude'})
        self.assertFalse(any(ln.startswith('G1 ') for ln in out_p))
        out_rp = render_gcode(body, self._printer(mode='printing'),
                              {'STEP': 'result', 'MEASURED': '20'})
        self.assertFalse(any('SET_EXTRUDER_ROTATION_DISTANCE' in ln for ln in out_rp))
        # Blocked when extruder is cold.
        out_cold = render_gcode(body, self._printer(mode='idle', can_extrude=False),
                                {'STEP': 'extrude'})
        self.assertFalse(any(ln.startswith('G1 ') for ln in out_cold))
        # Blocked for MEASURED <= 0 and MEASURED >= 120 (0 or negative fed length).
        for bad in ('-5', '0', '120', '121', '200'):
            out_b = render_gcode(body, self._printer(mode='idle'),
                                 {'STEP': 'result', 'MEASURED': bad})
            self.assertFalse(
                any('SET_EXTRUDER_ROTATION_DISTANCE' in ln for ln in out_b),
                f'bad MEASURED={bad} emitted rotation_distance')
        # Valid idle call computes rd_old * (120 - 20) / 100 = 33.5 and extrudes when warm.
        out_ok = render_gcode(body, self._printer(mode='idle', rd=33.5),
                              {'STEP': 'result', 'MEASURED': '20'})
        self.assertIn('SET_EXTRUDER_ROTATION_DISTANCE EXTRUDER=extruder DISTANCE=33.5', out_ok)
        out_ex = render_gcode(body, self._printer(mode='idle', can_extrude=True),
                              {'STEP': 'extrude'})
        self.assertIn('G1 E100 F120', out_ex)

    def test_extruder_cal_mutation_allows_negative_distance(self):
        body = load_macro('macros/12_maintenance.cfg', 'gcode_macro CALIBRATE_EXTRUDER')
        mutated = body.replace('{% elif measured >= 120 %}', '{% elif False %}', 1)
        mutated = mutated.replace('{% if rd_new > 0 %}', '{% if True %}', 1)
        out = render_gcode(mutated, self._printer(mode='idle', rd=33.5),
                           {'STEP': 'result', 'MEASURED': '125'})
        self.assertTrue(any('DISTANCE=-' in ln for ln in out))

    def test_retract_tower_does_not_persist_invalid_inputs(self):
        body = load_macro('macros/12_maintenance.cfg', 'gcode_macro RETRACT_TOWER')
        for bad in (
            {'BLOCKS': '1'},
            {'BLOCKS': '20'},
            {'START': '-1', 'STEP': '0.5', 'BLOCKS': '4'},
            {'START': '2', 'STEP': '3', 'BLOCKS': '5'},   # rmax = 14 > 10
            {'START': '1', 'STEP': '-0.5', 'BLOCKS': '4'},
            {'BLOCK': '0.6', 'LAYER': '0.4'},             # bh / lh = 1.5 < 2
        ):
            out = render_gcode(body, self._printer(mode='idle'), bad)
            saves = [ln for ln in out if ln.startswith('SAVE_VARIABLE ')]
            self.assertEqual(saves, [], f'invalid {bad} persisted variables: {saves}')
        valid = render_gcode(body, self._printer(mode='idle'),
                             {'START': '0.5', 'STEP': '0.5', 'BLOCKS': '4'})
        self.assertTrue(any(ln == 'SAVE_VARIABLE VARIABLE=rt_nb VALUE=4' for ln in valid))

    def test_layer_pause_clears_both_flags_when_coincident(self):
        lm = load_macro('macros/06_temp_controls.cfg', 'gcode_macro LAYER_MARK')
        pr = {
            'gcode_macro _STATE': {
                'mode': 'printing', 'legacy_mode': False, 'layer': 2,
                'total_layers': 20, 'pause_planned_reason': 'user',
                'stop_at_layer': 0, 'file_fan': 0, 'file_hotend_after': 0,
                'file_bed_after': 0, 'cur_feature': 'WALL-OUTER',
                'ignore_overrides': False, 'l1_slow_active': False,
            },
            'save_variables': {'variables': {
                'pause_next_layer': True, 'pause_at_layer': 3,
            }},
            'fan': {'speed': 0.5},
            'extruder': {'target': 210},
            'heater_bed': {'target': 60},
            'gcode_move': {'speed_factor': 1.0,
                           'gcode_position': type('P', (), {'z': 0.6})()},
        }
        out = render_gcode(lm, pr)
        self.assertIn('SAVE_VARIABLE VARIABLE=pause_next_layer VALUE=False', out)
        self.assertIn('SAVE_VARIABLE VARIABLE=pause_at_layer VALUE=0', out)
        self.assertEqual(sum(1 for ln in out if ln.startswith('PAUSE ')), 1)
        # Non-coincident future pause_at_layer=8 MUST stay intact when pausing at layer 3.
        pr['save_variables']['variables']['pause_at_layer'] = 8
        out2 = render_gcode(lm, pr)
        self.assertIn('SAVE_VARIABLE VARIABLE=pause_next_layer VALUE=False', out2)
        self.assertNotIn('SAVE_VARIABLE VARIABLE=pause_at_layer VALUE=0', out2)
        # Counter-mutation: without the coincident clear, pause_at_layer=3 stays stuck.
        pr['save_variables']['variables']['pause_at_layer'] = 3
        mut = lm.replace(
            "{% if sv.pause_at_layer|default(0)|int == n and n > 1 %}\n"
            "SAVE_VARIABLE VARIABLE=pause_at_layer VALUE=0\n"
            "{% endif %}", "", 1)
        self.assertNotEqual(mut, lm)
        out_m = render_gcode(mut, pr)
        self.assertNotIn('SAVE_VARIABLE VARIABLE=pause_at_layer VALUE=0', out_m)
        # Watcher Z-tracker path obeys the same coincident-clear contract.
        sw = load_macro('macros/01_state.cfg', 'delayed_gcode _STATE_WATCHER')
        pr_sw = {
            'gcode_macro _STATE': {
                'mode': 'printing', 'legacy_mode': True, 'layer_marks': False,
                'layer': 2, 'layer_z_max': 0.4, 'layer_z_acc': 2,
                'total_layers': 20, 'pause_planned_reason': 'user',
                'cancel_armed': False, 'file_fan': 0, 'file_hotend_after': 0,
                'file_bed_after': 0, 'ignore_overrides': False,
                'l1_slow_active': False, 'start_stuck': 0, 'state_stuck': 0,
                'led_quiet': False,
            },
            'print_stats': {'state': 'printing', 'filename': 'a.gcode',
                            'total_duration': 10.0, 'print_duration': 10.0},
            'virtual_sdcard': {'progress': 0.2},
            'save_variables': {'variables': {
                'pause_next_layer': True, 'pause_at_layer': 3,
            }},
            'gcode_move': {'speed_factor': 1.0,
                           'gcode_position': type('P', (), {'z': 0.65})()},
            'fan': {'speed': 0.5},
            'extruder': {'target': 210, 'temperature': 210},
            'heater_bed': {'target': 60, 'temperature': 60},
        }
        out_sw = render_gcode(sw, pr_sw)
        self.assertIn('SAVE_VARIABLE VARIABLE=pause_next_layer VALUE=False', out_sw)
        self.assertIn('SAVE_VARIABLE VARIABLE=pause_at_layer VALUE=0', out_sw)

    def test_calibration_pdf_source_matches_macro_contracts(self):
        src = (ROOT / 'tools' / 'make_calibration_pdf.py').read_text(encoding='utf-8')
        # Safety-critical gantry distinction: never claim SYNC_GANTRY needs stepper_z1.
        self.assertNotIn('Nur nötig, wenn `stepper_z1` vorhanden ist', src)
        self.assertIn('verweigert `SYNC_GANTRY`', src)
        self.assertIn('Z_TILT', src)
        # Probe offset fine/coarse step matches lcd_menues.cfg (+/-0.04 and +/-0.12).
        self.assertIn('+0.04', src)
        self.assertIn('+0.12', src)
        self.assertNotIn('TESTZ Z=+0.02', src)
        # Extruder formula uses (120 - Rest) / 100.
        self.assertIn('(120 − Rest) / 100', src)
        # Retract result sets retract_len only; Ironing result does not auto-write overrides.
        self.assertNotIn('übernimmt Länge/Geschwindigkeit', src)
        self.assertIn('retract_len', src)
        self.assertNotIn('übernimmt Tempo + Flow der besten Karte', src)
        self.assertNotIn('mm³/s pro mm/s', src)


if __name__ == '__main__':
    unittest.main(verbosity=2)
