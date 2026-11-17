#!/usr/bin/env python3
"""Paket 6 regression & counter-mutation tests for read-only r2_machine.py."""
import hashlib
import json
from pathlib import Path
import shutil
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / 'tools'
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

import r2_machine as machine  # noqa: E402
import r2_offline as offline  # noqa: E402


VALID_PRINTER_CFG = """\
# Synthetic test Klipper profile
[include macros/*.cfg]

[printer]
kinematics: cartesian
max_velocity: 300
max_accel: 3000
max_z_velocity: 10
max_z_accel: 100
square_corner_velocity: 5.0

[stepper_x]
position_min: -5
position_endstop: -5
position_max: 235
homing_speed: 50

[stepper_y]
position_min: -2
position_endstop: -2
position_max: 235
homing_speed: 50

[stepper_z]
position_min: -2
position_max: 250
homing_speed: 8

[stepper_z1]
step_pin: PB1

[extruder]
nozzle_diameter: 0.400
filament_diameter: 1.750
min_temp: 0
max_temp: 280
min_extrude_temp: 170
max_extrude_only_distance: 150.0
pressure_advance: 0.04

[heater_bed]
min_temp: 0
max_temp: 110

[bltouch]
x_offset: -30.0
y_offset: -10.0
#z_offset: 1.000

[bed_mesh]
mesh_min: 15, 15
mesh_max: 200, 220
probe_count: 5, 5
horizontal_move_z: 5.0
fade_start: 1.0
fade_end: 10.0

[z_tilt]
z_positions: -30, 110
  260, 110
points: 45, 120
  225, 120

[gcode_arcs]
resolution: 0.5

[firmware_retraction]
retract_length: 0.8
retract_speed: 35

[exclude_object]
[pause_resume]
[respond]
[save_variables]
filename: ~/printer_data/config/variables.cfg
[virtual_sdcard]
path: ~/printer_data/gcodes
[display]
lcd_type: uc1701

#*# <---------------------- SAVE_CONFIG ---------------------->
#*# DO NOT EDIT THIS BLOCK OR BELOW. The contents are auto-generated.
#*#
#*# [bltouch]
#*# z_offset = 2.345
"""


class MachineProfileTests(unittest.TestCase):
    def test_valid_profile_with_real_repo_macros_and_save_config(self):
        with tempfile.TemporaryDirectory(prefix='r2-mach-') as td:
            td_path = Path(td)
            shutil.copytree(ROOT / 'macros', td_path / 'macros')
            cfg = td_path / 'printer.cfg'
            cfg.write_text(VALID_PRINTER_CFG, encoding='utf-8')
            sha_before = hashlib.sha256(cfg.read_bytes()).hexdigest()

            prof = machine.load_machine_profile(cfg)
            self.assertEqual(sha_before, hashlib.sha256(cfg.read_bytes()).hexdigest())
            self.assertEqual('r2-machine-profile/1', prof['schema'])
            self.assertTrue(prof['valid'], prof['diagnostics'])
            self.assertEqual([], prof['diagnostics'])
            self.assertTrue(prof['r2_studio_prerequisites']['ok'])
            # Exact 30 delayed_gcode timers preserved across macros/*.cfg!
            self.assertEqual(30, prof['macros']['delayed_gcode_count'])
            self.assertGreater(prof['macros']['gcode_macro_count'], 100)
            # SAVE_CONFIG override tracked with provenance
            self.assertAlmostEqual(2.345, prof['probe']['z_offset_mm'], places=4)
            self.assertEqual('save_config', prof['probe']['z_offset_source'])
            self.assertTrue(prof['axes']['z']['dual_z'])
            self.assertEqual([-5.0, 235.0], prof['build_volume_mm']['x'])
            self.assertEqual([-2.0, 235.0], prof['build_volume_mm']['y'])
            self.assertEqual([-2.0, 250.0], prof['build_volume_mm']['z'])
            self.assertTrue(prof['capabilities']['gcode_arcs'])
            self.assertAlmostEqual(0.5, prof['capabilities']['arc_resolution_mm'])

    def test_static_config_diagnostics_catch_bad_mesh_bounds_temps_and_z_tilt(self):
        with tempfile.TemporaryDirectory(prefix='r2-mach-bad-') as td:
            cfg = Path(td) / 'bad.cfg'
            cfg.write_text("""\
[printer]
kinematics: cartesian
max_velocity: not_a_number

[stepper_x]
position_min: 0
position_max: 220

[stepper_y]
position_min: 200
position_max: 100

[extruder]
nozzle_diameter: 2.0
filament_diameter: 1.75
min_temp: 0
max_temp: 250
min_extrude_temp: 260

[bltouch]
x_offset: -40
y_offset: 0
z_offset: 1.5

[bed_mesh]
mesh_min: 10, 10
mesh_max: 200, 200
probe_count: 5, 5

[z_tilt]
points: 10, 10
""", encoding='utf-8')
            prof = machine.load_machine_profile(cfg)
            self.assertFalse(prof['valid'])
            self.assertFalse(prof['r2_studio_prerequisites']['ok'])
            codes = {d['code'] for d in prof['diagnostics']}
            # mesh_max.x=200 with x_offset=-40 requires nozzle_x=240 > position_max=220!
            for want in ('INVALID_NUMBER', 'INVALID_AXIS_RANGE',
                         'NOZZLE_EXCEEDS_FILAMENT', 'INVALID_MIN_EXTRUDE_TEMP',
                         'MESH_OUT_OF_AXIS_RANGE', 'Z_TILT_SINGLE_Z'):
                self.assertIn(want, codes, f'missing {want} in {prof["diagnostics"]}')

    def test_include_security_refuses_traversal_symlink_and_cycle(self):
        with tempfile.TemporaryDirectory(prefix='r2-mach-sec-') as td:
            root = Path(td) / 'cfg'
            root.mkdir()
            outside = Path(td) / 'secret.cfg'
            outside.write_text('[printer]\nkinematics: cartesian\n', encoding='utf-8')

            trav = root / 'trav.cfg'
            trav.write_text('[include ../secret.cfg]\n', encoding='utf-8')
            with self.assertRaises(ValueError):
                machine.load_machine_profile(trav)

            sym_inc = root / 'link.cfg'
            sym_inc.symlink_to(outside)
            uses_sym = root / 'uses_sym.cfg'
            uses_sym.write_text('[include link.cfg]\n', encoding='utf-8')
            with self.assertRaises(ValueError):
                machine.load_machine_profile(uses_sym)
            with self.assertRaises(ValueError):
                machine.load_machine_profile(sym_inc)

            cyc_a = root / 'a.cfg'
            cyc_b = root / 'b.cfg'
            cyc_a.write_text('[include b.cfg]\n', encoding='utf-8')
            cyc_b.write_text('[include a.cfg]\n', encoding='utf-8')
            with self.assertRaises(ValueError):
                machine.load_machine_profile(cyc_a)

    def test_offline_audit_with_machine_config_flags_arc_bounds_and_missing_caps(self):
        with tempfile.TemporaryDirectory(prefix='r2-mach-chk-') as td:
            cfg = Path(td) / 'printer.cfg'
            cfg.write_text("""\
[printer]
kinematics: cartesian
max_velocity: 100
max_accel: 2000
[stepper_x]
position_min: 0
position_max: 100
[stepper_y]
position_min: 0
position_max: 100
[stepper_z]
position_min: 0
position_max: 50
[extruder]
nozzle_diameter: 0.4
filament_diameter: 1.75
""", encoding='utf-8')
            # Arc endpoints X=90 stay <= 100, but arc bulges to X=110 (> 100)!
            # Also uses G3 (no [gcode_arcs]), G10 (no [firmware_retraction]),
            # EXCLUDE_OBJECT (no [exclude_object]), filament 2.85, and F9000 (150 mm/s)!
            gc = Path(td) / 'job.gcode'
            gc.write_text('\n'.join([
                '; filament_diameter = 2.85',
                'EXCLUDE_OBJECT_DEFINE NAME=part',
                'G21', 'G17', 'G90', 'M83',
                'EXCLUDE_OBJECT_START NAME=part',
                'G0 X80 Y30 Z0.2 F9000',
                'G0 X90 Y30 F9000',
                'G3 X90 Y70 I0 J20 E2.5 F1800',   # bulge reaches X=110!
                'G10',
                'EXCLUDE_OBJECT_END NAME=part',
            ]) + '\n', encoding='utf-8')
            out = Path(td) / 'audit.json'
            self.assertEqual(
                0, offline.main(['audit', '--machine-config', str(cfg),
                                 str(gc), str(out)]))
            data = json.loads(out.read_text(encoding='utf-8'))
            self.assertEqual('findings_present', data['audit_summary']['status'])
            mc = data['machine_check']
            self.assertFalse(mc['ok'])
            vcodes = {v['code'] for v in mc['violations']}
            for want in ('OUT_OF_BOUNDS_X', 'MISSING_GCODE_ARCS',
                         'MISSING_FIRMWARE_RETRACTION', 'MISSING_EXCLUDE_OBJECT',
                         'FILAMENT_DIAMETER_MISMATCH'):
                self.assertIn(want, vcodes, f'missing {want} in {mc}')
            acodes = {a['code'] for a in mc['advisories']}
            self.assertIn('SPEED_EXCEEDS_MAX_VELOCITY', acodes)

            # CLI inspect round-trip
            self.assertEqual(0, machine.main(['inspect', str(cfg)]))


if __name__ == '__main__':
    unittest.main()
