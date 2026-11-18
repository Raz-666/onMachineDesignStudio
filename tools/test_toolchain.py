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
                         ['mirror', 'range', 'scale', 'texture', 'twist'])
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
        """R260: relative Unterordner-Pfade sind ERLAUBT (Range/V02_x.gcode);
        Kletterei ('..'), absolute Pfade und Muell bleiben draussen."""
        plan, errors = toolchain.plan_chain(
            preset_range_texture(), 'unter/ordner/x.gcode')
        self.assertEqual(errors, [])
        self.assertIsNotNone(plan)
        self.assertEqual(plan['steps'][0]['input'], 'unter/ordner/x.gcode')
        # Stem = Basisname (V<nn>_ eines Vorgaenger-Tools faellt weg);
        # der Preset-Tag haengt NUR an der Endausgabe
        self.assertEqual([s['output'] for s in plan['steps']],
                         ['V01_x.gcode', 'V02_x_FensterRinde.gcode'])
        for bad in ('../auserhalb.gcode', '/absolut.gcode',
                    'keine-endung', 'x.GCODE', 'a/../b.gcode'):
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
        """R260: Temps plain, die ENDAUSGABE traegt den Preset-Namen als
        Wortkette ('Fenster + Rinde' -> FensterRinde)."""
        plan, _ = toolchain.plan_chain(preset_range_texture(),
                                       'figur.gcode')
        self.assertEqual(plan['steps'][0]['output'], 'V01_figur.gcode')
        self.assertEqual(plan['steps'][1]['output'],
                         'V02_figur_FensterRinde.gcode')

    def test_first_version_lifts_the_whole_chain(self):
        """R259: der Watcher hebt die V-Nummer auf die naechste freie des
        Ausgabeordners - kein zweiter Lauf kollidiert mit der ersten
        Endausgabe (S22: nichts wird ueberschrieben)."""
        plan, _ = toolchain.plan_chain(preset_range_texture(),
                                       'figur.gcode', first_version=7)
        self.assertEqual([s['output'] for s in plan['steps']],
                         ['V07_figur.gcode', 'V08_figur_FensterRinde.gcode'])
        self.assertEqual(plan['final_output'],
                         'V08_figur_FensterRinde.gcode')
        # die Kette bleibt verkettet: Ausgabe von Schritt 1 = Eingabe von 2
        self.assertEqual(plan['steps'][1]['input'],
                         plan['steps'][0]['output'])
        plan_bad, errors = toolchain.plan_chain(preset_range_texture(),
                                                'figur.gcode',
                                                first_version=0)
        self.assertIsNone(plan_bad)
        self.assertTrue(any('first_version' in e for e in errors), errors)

    def test_r260_naming_translit_tag_and_vstrip(self):
        """R260-Namenspaket: Umlaut-Umschrift (Eingabe UND Preset-Name),
        Preset-Name als Wortkette NUR an der Endausgabe, V<nn>_ einer
        Vorgaenger-Ausgabe faellt aus dem Stem."""
        preset = {'schema': toolchain.SCHEMA, 'name': 'Größer Rahmen',
                  'steps': [{'tool': 'twist', 'params': {'deg': 10}}]}
        plan, errors = toolchain.plan_chain(preset, 'Größer Rahmen.gcode')
        self.assertEqual(errors, [])
        self.assertEqual(plan['steps'][0]['output'],
                         'V01_Groesser_Rahmen_GroesserRahmen.gcode')
        # Unterordner + Vorgaenger-V-Prefix: Stem = Basisname ohne V02_
        plan, errors = toolchain.plan_chain(preset,
                                            'Range/V02_Mein Teil.gcode')
        self.assertEqual(errors, [])
        self.assertEqual(plan['steps'][0]['output'],
                         'V01_Mein_Teil_GroesserRahmen.gcode')

    def test_r260_chain_tag_cuts_at_word_boundary(self):
        self.assertEqual(
            toolchain._chain_tag({'name': 'Scale up + twist'}),
            'ScaleUpTwist')
        # Wortgrenze statt Mitte: 'Mein ganz besonders langer
        # Versuchspreset-Name' -> 23 Zeichen, kein halbes Wort
        self.assertEqual(
            toolchain._chain_tag({'name':
                                  'Mein ganz besonders langer '
                                  'Versuchspreset-Name'}),
            'MeinGanzBesondersLanger')
        self.assertEqual(toolchain._chain_tag({'name': 'x'}), 'X')
        self.assertEqual(toolchain._chain_tag({}), '')
        # ein einzelnes laengeres Wort wird hart am Limit geschnitten
        self.assertEqual(len(toolchain._chain_tag(
            {'name': 'Supercalifragilisticexpialidocious'})), 24)


class PresetFileTests(unittest.TestCase):
    """R259 (Phase 2b/2): Preset-Auswahl als DATEI - load_preset_file ist
    die testbare Aufloesung (der Watcher meldet die Fehler als NOTIFY)."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.dir = self._tmp.name

    def tearDown(self):
        self._tmp.cleanup()

    def _write(self, name, text):
        path = os.path.join(self.dir, name)
        with open(path, 'w', encoding='utf-8') as handle:
            handle.write(text)
        return path

    def test_shipped_example_resolves(self):
        """Das mitgelieferte Beispiel-Preset ist gueltig (der Watcher
        seedy es in den Toolchain-Ordner)."""
        repo_example = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            'presets', 'toolchain', 'scale-twist.json')
        preset, errors = toolchain.load_preset_file(repo_example)
        self.assertIsNotNone(preset)
        self.assertEqual(errors, [])
        self.assertEqual([s['tool'] for s in preset['steps']],
                         ['scale', 'twist'])

    def test_missing_file_is_a_plain_text_error(self):
        preset, errors = toolchain.load_preset_file(
            os.path.join(self.dir, 'gibtsnicht.json'))
        self.assertIsNone(preset)
        self.assertEqual(len(errors), 1)
        self.assertIn('fehlt', errors[0])

    def test_broken_json_names_line_and_column(self):
        path = self._write('broken.json', '{"schema": "r2-toolchain/1",')
        preset, errors = toolchain.load_preset_file(path)
        self.assertIsNone(preset)
        self.assertTrue(any('kein gueltiges JSON' in e for e in errors),
                        errors)

    def test_contract_violations_carry_the_file_name(self):
        path = self._write('boese.json', json.dumps({
            'schema': 'r2-toolchain/1', 'name': 'Boese',
            'steps': [{'tool': 'cake', 'params': {'yaw': 0}}]}))
        preset, errors = toolchain.load_preset_file(path)
        self.assertIsNone(preset)
        # cake ist in der Anker-Registry gar nicht verankert (nur die 5
        # kettenfaehigen Werkzeuge) -> unbekannt, Klartext mit Dateiname
        self.assertTrue(any('boese.json' in e and 'unbekanntes Werkzeug'
                            in e for e in errors), errors)

    def test_forbidden_input_key_rejected_in_a_file(self):
        path = self._write('sneaky.json', json.dumps({
            'schema': 'r2-toolchain/1', 'name': 'Sneaky',
            'steps': [{'tool': 'twist', 'params': {'deg': 30},
                       'file': 'teil.gcode'}]}))
        preset, errors = toolchain.load_preset_file(path)
        self.assertIsNone(preset)
        self.assertTrue(any('file' in e for e in errors), errors)


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
                             'V02_teil_FensterRinde.gcode')

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




class MenuRegistryTests(unittest.TestCase):
    """Registry-Vollstaendigkeit aus web/menu_structure.json (Quelle der
    Wahrheit, exportiert von menu_json_export.py) + Drift-Waechter."""

    def test_menu_file_is_present_and_exported(self):
        data = toolchain.load_menu_data()
        self.assertTrue(data['generator'].startswith('menu_json_export'),
                        data['generator'])
        mods = toolchain._find_node(
            data['tree'], '__main __preprint __mods')
        self.assertIsNotNone(mods)

    def test_build_registry_finds_all_mods_tools(self):
        registry = toolchain.build_registry(toolchain.load_menu_data())
        self.assertEqual(sorted(registry),
                         ['cake', 'mirror', 'offset', 'plot', 'range',
                          'scale', 'texture', 'twist'])
        self.assertEqual(registry['cake']['outputs'], 2)   # H3: PART=BOTH
        for name in ('range', 'scale', 'texture', 'twist', 'mirror', 'plot'):
            self.assertEqual(registry[name]['outputs'], 1)

    def test_menu_derived_ranges_match_the_lcd(self):
        registry = toolchain.build_registry(toolchain.load_menu_data())
        self.assertEqual(registry['twist']['params']['twist_deg'],
                         {'type': 'int', 'required': False,
                          'min': -720, 'max': 720, 'step': 5})
        self.assertEqual(registry['scale']['params']['scale_x']['min'], 25)
        self.assertEqual(registry['scale']['params']['scale_x']['max'], 300)
        self.assertEqual(registry['range']['params']['range_floor']['max'], 10)
        # Dynamische Menue-Grenze (total_layers): keine statische Pruefung.
        start = registry['range']['params']['range_start']
        self.assertEqual(start['min'], 2)
        self.assertNotIn('max', start)
        self.assertIn('note', start)

    def test_anchor_registry_has_no_drift_against_menu(self):
        """CI-Waechter: aendert jemand die LCD-Bereiche, schlaegt das an."""
        drift = toolchain.registry_drift()
        self.assertEqual(drift, [], '\n'.join(drift))

    def test_drift_detector_actually_detects_tampering(self):
        tampered = {tool: dict(spec) for tool, spec
                    in toolchain.TOOL_REGISTRY.items()}
        tampered['scale'] = dict(tampered['scale'])
        tampered['scale']['params'] = dict(tampered['scale']['params'])
        tampered['scale']['params']['x'] = dict(
            tampered['scale']['params']['x'], min=10)
        drift = toolchain.registry_drift(registry=tampered)
        self.assertTrue(any('scale.x' in d for d in drift), drift)

    def test_menu_registry_validates_twist_preset(self):
        registry = toolchain.build_registry(toolchain.load_menu_data())
        preset = {'schema': toolchain.SCHEMA, 'name': 'Verdrillt',
                  'steps': [{'tool': 'twist',
                             'params': {'twist_deg': 90}}]}
        ok, errors = toolchain.validate_preset(preset, registry=registry)
        self.assertTrue(ok, errors)
        preset['steps'][0]['params']['twist_deg'] = 800
        ok, errors = toolchain.validate_preset(preset, registry=registry)
        self.assertFalse(ok)
        self.assertTrue(any('ueber Maximum 720' in e for e in errors), errors)

    def test_cake_is_rejected_in_chains_via_menu_registry(self):
        registry = toolchain.build_registry(toolchain.load_menu_data())
        preset = {'schema': toolchain.SCHEMA, 'name': 'Mit Cake',
                  'steps': [{'tool': 'cake',
                             'params': {'cake_pitch': 15.0}}]}
        ok, errors = toolchain.validate_preset(preset, registry=registry)
        self.assertFalse(ok)
        self.assertTrue(any('mehrere Ausgaben' in e for e in errors), errors)

    def test_corrected_anchor_bounds_follow_the_menu(self):
        """Anker wurden an die Menue-Wahrheit angeglichen (frueher falsch:
        seed 0..999999, floor 0..50, start ab 1)."""
        tex = toolchain.TOOL_REGISTRY['texture']['params']['seed']
        self.assertEqual((tex['min'], tex['max']), (1, 999))
        rng = toolchain.TOOL_REGISTRY['range']['params']
        self.assertEqual(rng['floor']['max'], 10)
        self.assertEqual(rng['start']['min'], 2)
        ok, _ = toolchain.validate_preset(preset_range_texture())
        self.assertTrue(ok)


def _append_runner(tag):
    def runner(step, in_path, out_path):
        with open(in_path, 'r', encoding='utf-8') as handle:
            text = handle.read()
        with open(out_path, 'w', encoding='utf-8') as handle:
            handle.write(text + tag)
    return runner


class ExecutorTests(unittest.TestCase):
    """run_chain: §22-Gates — Validierung je Stufe, Temp-Loeschung erst
    nach Uebernahme, Zustaende, Ausgabemodi, kein Ueberschreiben."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.base = self._tmp.name
        self.input_path = os.path.join(self.base, 'original.gcode')
        with open(self.input_path, 'w', encoding='utf-8') as handle:
            handle.write('G28\n')
        chain = preset_range_texture()
        chain['steps'].insert(1, {'tool': 'scale',
                                  'params': {'x': 120, 'y': 120}})
        self.plan, errors = toolchain.plan_chain(chain, 'original.gcode')
        self.assertEqual(errors, [])
        self.workspace = os.path.join(self.base, 'Toolchain')

    def test_happy_path_deletes_temps_after_takeover_only(self):
        report = toolchain.run_chain(self.plan, self.workspace,
                                     self.input_path,
                                     _append_runner('|R|'))
        self.assertTrue(report['ok'], report)
        self.assertEqual(report['state'], 'success')
        self.assertEqual([r['state'] for r in report['steps']],
                         ['success', 'success', 'success'])
        # V01 + V02 waren temporaer und sind nach Uebernahme geloescht;
        # die Endausgabe V03 bleibt.
        self.assertEqual(len(report['temp_deleted']), 2)
        for gone in report['temp_deleted']:
            self.assertFalse(os.path.exists(gone))
        final = report['final_output']
        self.assertTrue(os.path.isfile(final))
        with open(final, 'r', encoding='utf-8') as handle:
            self.assertEqual(handle.read(), 'G28\n|R||R||R|')

    def test_cancellation_keeps_untaken_temp(self):
        """§22.4-Orakel: Abbruch nach Stufe 2 — V01 ist geloescht (von
        Stufe 2 uebernommen), V02 bleibt (nie uebernommen)."""
        report = toolchain.run_chain(
            self.plan, self.workspace, self.input_path, _append_runner('|R|'),
            cancel_check=lambda idx: idx == 3)
        self.assertFalse(report['ok'])
        self.assertEqual(report['state'], 'cancelled')
        self.assertEqual([r['state'] for r in report['steps']],
                         ['success', 'success', 'queued'])
        v01 = os.path.join(self.workspace, 'V01_original.gcode')
        v02 = os.path.join(self.workspace, 'V02_original.gcode')
        self.assertFalse(os.path.exists(v01))
        self.assertTrue(os.path.exists(v02))

    def test_failure_keeps_temp_and_skips_rest(self):
        def failing_second(step, in_path, out_path):
            if step['job'] == 2:
                raise RuntimeError('Synthese gescheitert')
            _append_runner('|R|')(step, in_path, out_path)
        report = toolchain.run_chain(self.plan, self.workspace,
                                     self.input_path, failing_second)
        self.assertFalse(report['ok'])
        self.assertEqual(report['state'], 'failed')
        self.assertEqual([r['state'] for r in report['steps']],
                         ['success', 'failed', 'queued'])
        self.assertIn('Synthese gescheitert', report['error'])
        # Nachvollziehbarkeit: Stufe-1-Zwischenstand bleibt liegen.
        v01 = os.path.join(self.workspace, 'V01_original.gcode')
        self.assertTrue(os.path.exists(v01))
        self.assertEqual(report['temp_deleted'], [])

    def test_empty_output_fails_validation(self):
        def empty_second(step, in_path, out_path):
            if step['job'] == 2:
                open(out_path, 'w').close()
                return
            _append_runner('|R|')(step, in_path, out_path)
        report = toolchain.run_chain(self.plan, self.workspace,
                                     self.input_path, empty_second)
        self.assertFalse(report['ok'])
        self.assertIn('leer', report['error'])
        self.assertEqual(report['steps'][1]['state'], 'failed')

    def test_existing_final_output_refuses_to_run(self):
        os.makedirs(self.workspace, exist_ok=True)
        final = os.path.join(self.workspace,
                             'V03_original_FensterRinde.gcode')
        with open(final, 'w', encoding='utf-8') as handle:
            handle.write('alt')
        report = toolchain.run_chain(self.plan, self.workspace,
                                     self.input_path, _append_runner('|X|'))
        self.assertFalse(report['ok'])
        self.assertIn('nichts wird ueberschrieben', report['error'])
        self.assertEqual([r['state'] for r in report['steps']],
                         ['queued', 'queued', 'queued'])
        with open(final, 'r', encoding='utf-8') as handle:
            self.assertEqual(handle.read(), 'alt')

    def test_missing_input_fails_before_any_step(self):
        report = toolchain.run_chain(
            self.plan, self.workspace,
            os.path.join(self.base, 'gibt_es_nicht.gcode'),
            _append_runner('|R|'))
        self.assertFalse(report['ok'])
        self.assertIn('Eingabedatei unbrauchbar', report['error'])
        self.assertEqual([r['state'] for r in report['steps']],
                         ['queued', 'queued', 'queued'])

    def test_output_mode_save_calls_no_hook(self):
        calls = []
        report = toolchain.run_chain(self.plan, self.workspace,
                                     self.input_path, _append_runner('|R|'),
                                     output_mode='save',
                                     on_output=lambda m, p: calls.append((m, p)))
        self.assertTrue(report['ok'])
        self.assertEqual(calls, [])

    def test_output_mode_queue_registers_final(self):
        calls = []
        report = toolchain.run_chain(self.plan, self.workspace,
                                     self.input_path, _append_runner('|R|'),
                                     output_mode='queue',
                                     on_output=lambda m, p: calls.append((m, p)))
        self.assertTrue(report['ok'], report)
        self.assertEqual(calls, [('queue', report['final_output'])])

    def test_output_mode_preview_without_hook_fails_registration(self):
        """§22.1: nicht korrekt registriert == nicht erfolgreich."""
        report = toolchain.run_chain(self.plan, self.workspace,
                                     self.input_path, _append_runner('|R|'),
                                     output_mode='preview', on_output=None)
        self.assertFalse(report['ok'])
        self.assertIn('on_output-Hook', report['error'])

    def test_bad_plan_and_mode_are_rejected_upfront(self):
        with self.assertRaises(ValueError):
            toolchain.run_chain({'schema': 'kein-plan'}, self.workspace,
                                self.input_path, _append_runner('|R|'))
        with self.assertRaises(ValueError):
            toolchain.run_chain(self.plan, self.workspace, self.input_path,
                                _append_runner('|R|'), output_mode='drucken')


if __name__ == '__main__':
    unittest.main(verbosity=2)
