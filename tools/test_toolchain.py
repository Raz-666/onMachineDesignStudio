#!/usr/bin/env python3
# ============================================================================
# test_toolchain.py — Orakel-Tests fuer den Toolchain-Preset-Vertrag (Phase 1)
# ============================================================================
# Alle Orakel sind synthetisch und komplett offline. Getestet wird NUR der
# Vertrag (Validierung + Planung) — es gibt bewusst keinen Ausfuehrungs- und
# keinen Datei-Schreibtest, weil Phase 1 nichts ausfuehrt.
# ============================================================================

import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import toolchain  # noqa: E402


def preset_range_texture():
    """§20.1-Beispielkette in klein: Fenster ziehen, dann Textur auflegen."""
    return {
        'schema': toolchain.SCHEMA,
        'name': 'Fenster + Rinde',
        'description': 'Range 10-40, dann BARK auf die Aussenwand',
        'steps': [
            {'tool': 'range',
             'params': {'start': 10, 'end': 40, 'floor': 2, 'brim': 4}},
            {'tool': 'texture',
             'params': {'pattern': 'BARK', 'scale_mm': 12.0,
                        'zsize_mm': 18.0, 'depth_mm': 0.45}},
        ],
    }


class RegistryTests(unittest.TestCase):

    def test_registry_selfcheck(self):
        """Jedes Registry-Werkzeug ist vollstaendig und widerspruchsfrei."""
        report = toolchain.registry_report()
        self.assertEqual(sorted(report),
                         ['range', 'scale', 'texture'])
        for tool, spec in toolchain.TOOL_REGISTRY.items():
            self.assertIsInstance(spec['title'], str)
            self.assertGreater(len(spec['params']), 0)
            self.assertLessEqual(len(spec['params']),
                                 toolchain.MAX_PARAMS_PER_STEP)
            for name, pspec in spec['params'].items():
                self.assertIn(pspec['type'], ('int', 'number', 'enum'))
                if pspec['type'] in ('int', 'number'):
                    self.assertLess(pspec['min'], pspec['max'])
                    if 'default' in pspec:
                        self.assertGreaterEqual(pspec['default'], pspec['min'])
                        self.assertLessEqual(pspec['default'], pspec['max'])
                if pspec['type'] == 'enum':
                    self.assertGreater(len(pspec['values']), 0)

    def test_texture_pattern_enum_is_the_27_code_list(self):
        """Die 27 Muster stammen aus macros/17_generator.cfg:1179."""
        self.assertEqual(len(toolchain.TEXTURE_PATTERNS), 27)
        self.assertIn('BARK', toolchain.TEXTURE_PATTERNS)
        self.assertIn('MACRAME', toolchain.TEXTURE_PATTERNS)
        self.assertIn('MAP', toolchain.TEXTURE_PATTERNS)


class ValidationTests(unittest.TestCase):

    def test_valid_preset_passes(self):
        ok, errors = toolchain.validate_preset(preset_range_texture())
        self.assertTrue(ok, errors)
        self.assertEqual(errors, [])

    def test_unknown_tool_rejected(self):
        preset = preset_range_texture()
        preset['steps'][1]['tool'] = 'slicer'
        ok, errors = toolchain.validate_preset(preset)
        self.assertFalse(ok)
        self.assertTrue(any('unbekanntes Werkzeug' in e for e in errors),
                        errors)

    def test_unknown_param_rejected(self):
        preset = preset_range_texture()
        preset['steps'][0]['params']['speed'] = 100
        ok, errors = toolchain.validate_preset(preset)
        self.assertFalse(ok)
        self.assertTrue(any('kennt Parameter "speed" nicht' in e
                            for e in errors), errors)

    def test_out_of_range_rejected(self):
        preset = {
            'schema': toolchain.SCHEMA, 'name': 'Skalieren',
            'steps': [{'tool': 'scale', 'params': {'x': 10, 'y': 100}}],
        }
        ok, errors = toolchain.validate_preset(preset)
        self.assertFalse(ok)
        self.assertTrue(any('"x" = 10 unter Minimum 25' in e for e in errors),
                        errors)

    def test_missing_required_rejected(self):
        preset = {
            'schema': toolchain.SCHEMA, 'name': 'Ohne Ende',
            'steps': [{'tool': 'range', 'params': {'start': 5}}],
        }
        ok, errors = toolchain.validate_preset(preset)
        self.assertFalse(ok)
        self.assertTrue(any('Pflichtparameter "end" fehlt' in e
                            for e in errors), errors)

    def test_preset_must_not_contain_input_file(self):
        """§20.2-Orakel: Presets enthalten NIEMALS eine Eingabedatei."""
        for mutation in (
                {'input': '/sd/kette.gcode'},
                {'file': 'x.gcode'},
                {'source': 'orte/irgendwo.gcode'},
        ):
            preset = preset_range_texture()
            preset.update(mutation)
            ok, errors = toolchain.validate_preset(preset)
            self.assertFalse(ok, mutation)
            self.assertTrue(any('verboten' in e for e in errors),
                            (mutation, errors))
        # Auch innerhalb eines Schritts und der Parameter:
        preset = preset_range_texture()
        preset['steps'][0]['input'] = 'geheim.gcode'
        ok, errors = toolchain.validate_preset(preset)
        self.assertFalse(ok)
        preset = preset_range_texture()
        preset['steps'][1]['params']['src'] = 'geheim.gcode'
        ok, errors = toolchain.validate_preset(preset)
        self.assertFalse(ok)

    def test_empty_steps_rejected(self):
        preset = {'schema': toolchain.SCHEMA, 'name': 'Leer', 'steps': []}
        ok, errors = toolchain.validate_preset(preset)
        self.assertFalse(ok)
        self.assertTrue(any('"steps"' in e for e in errors), errors)

    def test_wrong_schema_and_name_rejected(self):
        ok, errors = toolchain.validate_preset({'schema': 'r2-x/9',
                                                'name': 'x', 'steps': []})
        self.assertFalse(ok)
        self.assertTrue(any('"schema"' in e for e in errors), errors)
        preset = preset_range_texture()
        preset['name'] = '../pfad/teufel'
        ok, errors = toolchain.validate_preset(preset)
        self.assertFalse(ok)
        self.assertTrue(any('"name"' in e for e in errors), errors)

    def test_bool_is_not_an_int(self):
        """True ist in Python ein int — der Vertrag darf das nicht durchlassen."""
        preset = preset_range_texture()
        preset['steps'][0]['params']['start'] = True
        ok, errors = toolchain.validate_preset(preset)
        self.assertFalse(ok)
        self.assertTrue(any('falschen Typ' in e for e in errors), errors)

    def test_enum_rejected_for_unknown_pattern(self):
        preset = preset_range_texture()
        preset['steps'][1]['params']['pattern'] = 'BARKK'
        ok, errors = toolchain.validate_preset(preset)
        self.assertFalse(ok)
        self.assertTrue(any('"pattern" hat falschen Typ' in e
                            for e in errors), errors)

    def test_cross_rule_range_window(self):
        preset = preset_range_texture()
        preset['steps'][0]['params'] = {'start': 40, 'end': 10}
        ok, errors = toolchain.validate_preset(preset)
        self.assertFalse(ok)
        self.assertTrue(any('"start" (40) muss <= "end" (10)' in e
                            for e in errors), errors)

    def test_multi_output_tool_rejected_in_chains(self):
        """Cake (PART=BOTH -> 2 Dateien) hat in Ketten noch keine Semantik."""
        original = toolchain.TOOL_REGISTRY
        patched = dict(original)
        patched['cake'] = {'title': 'Cake', 'outputs': 2, 'params': {},
                           'rules': []}
        try:
            toolchain.TOOL_REGISTRY = patched
            preset = {'schema': toolchain.SCHEMA, 'name': 'Mit Cake',
                      'steps': [{'tool': 'cake', 'params': {}}]}
            ok, errors = toolchain.validate_preset(preset)
            self.assertFalse(ok)
            self.assertTrue(any('mehrere Ausgaben' in e for e in errors),
                            errors)
        finally:
            toolchain.TOOL_REGISTRY = original

    def test_json_roundtrip_preserves_validation(self):
        ok1, errors1 = toolchain.validate_preset(preset_range_texture())
        reloaded = json.loads(json.dumps(preset_range_texture()))
        ok2, errors2 = toolchain.validate_preset(reloaded)
        self.assertEqual((ok1, errors1), (ok2, errors2))


class PlanTests(unittest.TestCase):

    def test_plan_chains_outputs_and_marks_temps(self):
        plan, errors = toolchain.plan_chain(preset_range_texture(),
                                            'rose_215c_pla.gcode')
        self.assertEqual(errors, [])
        self.assertEqual(plan['schema'], toolchain.PLAN_SCHEMA)
        self.assertEqual(len(plan['steps']), 2)
        first, second = plan['steps']
        # §20.1: jedes Werkzeug erhaelt die Ausgabe des vorherigen.
        self.assertEqual(first['input'], 'rose_215c_pla.gcode')
        self.assertEqual(second['input'], first['output'])
        # §20.3/§22.4: nur die letzte Stufe ist dauerhaft.
        self.assertTrue(first['temp'])
        self.assertFalse(second['temp'])
        self.assertEqual(plan['final_output'], second['output'])
        self.assertEqual(plan['temp_outputs'], 1)
        self.assertIn('validierte Ausgabe von Job 1', second['requires'])
        # Defaults werden aufgeloest (direction/seed bei texture).
        self.assertEqual(second['params']['direction'], 'OUT')
        self.assertEqual(second['params']['seed'], 1)

    def test_plan_rejects_path_like_input(self):
        for bad in ('../auserhalb.gcode', 'unter/ordner/x.gcode',
                    'keine-endung', 'x.GCODE'):
            plan, errors = toolchain.plan_chain(preset_range_texture(), bad)
            self.assertIsNone(plan, bad)
            self.assertTrue(errors, bad)

    def test_plan_requires_valid_preset(self):
        preset = preset_range_texture()
        preset['steps'][0]['params']['start'] = 99
        plan, errors = toolchain.plan_chain(preset, 'x.gcode')
        self.assertIsNone(plan)
        self.assertTrue(errors)

    def test_output_naming_follows_version_convention(self):
        plan, _ = toolchain.plan_chain(preset_range_texture(),
                                       'figur.gcode')
        self.assertEqual(plan['steps'][0]['output'], 'V01_figur.gcode')
        self.assertEqual(plan['steps'][1]['output'], 'V02_figur.gcode')


class CliTests(unittest.TestCase):

    def test_cli_reports_validation_and_plan(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, 'preset.json')
            with open(path, 'w', encoding='utf-8') as handle:
                json.dump(preset_range_texture(), handle)
            import io
            import contextlib
            buffer = io.StringIO()
            with contextlib.redirect_stdout(buffer):
                exit_code = toolchain.main([path, '--input', 'teil.gcode'])
            self.assertEqual(exit_code, 0)
            report = json.loads(buffer.getvalue())
            self.assertTrue(report['ok'])
            self.assertEqual(report['plan']['final_output'],
                             'V02_teil.gcode')

    def test_cli_fails_cleanly_on_invalid_preset(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, 'bad.json')
            with open(path, 'w', encoding='utf-8') as handle:
                json.dump({'schema': 'falsch', 'name': 'x', 'steps': []},
                          handle)
            import io
            import contextlib
            buffer = io.StringIO()
            with contextlib.redirect_stdout(buffer):
                exit_code = toolchain.main([path])
            self.assertEqual(exit_code, 1)
            report = json.loads(buffer.getvalue())
            self.assertFalse(report['ok'])
            self.assertTrue(report['errors'])


if __name__ == '__main__':
    unittest.main(verbosity=2)
