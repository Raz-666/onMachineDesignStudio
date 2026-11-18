#!/usr/bin/env python3
# ============================================================================
# test_toolchain_steps.py — Orakel-Tests fuer die System-Adapter (Phase 2b/1)
# ============================================================================
# Ketten laufen mit den ECHTEN Engines (make_range/apply_scale/apply_twist/
# apply_mirror/apply_texture) gegen synthetische, markierte G-Code-Fixtures
# (LAYER_CHANGE/LAYER_MARK/;Z:-Bloecke, Muster: v1_range_cause_check.py).
# Alles offline: keine Moonraker-/Druckerabhaengigkeit, temporaere Verzeichnisse.
# ============================================================================

import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import toolchain  # noqa: E402
import toolchain_steps  # noqa: E402


def layered_fixture(total_layers=6, size=20.0, x0=100.0, y0=100.0):
    """Synthetische, markierte Datei: total_layers Schichten, pro Schicht
    eine quadratische Aussenwand (APPLY_TYPE WALL-OUTER) mit E."""
    lines = ['; synthetic chain fixture', 'M83', 'G21', 'G90']
    for layer in range(1, total_layers + 1):
        z = 0.2 * layer
        lines.append(';LAYER_CHANGE')
        lines.append('LAYER_MARK')
        lines.append(';Z:%.3f' % z)
        lines.append('APPLY_TYPE TYPE=WALL-OUTER')
        corners = [(x0, y0), (x0 + size, y0), (x0 + size, y0 + size),
                   (x0, y0 + size), (x0, y0)]
        lines.append('G0 X%.3f Y%.3f Z%.3f F3600' % (x0, y0, z))
        for cx, cy in corners[1:]:
            lines.append('G1 X%.3f Y%.3f E0.20 F1800' % (cx, cy))
    lines.append('_FILE_INFO MATERIAL=PLA LAYER_HEIGHT=0.2 '
                 'TOTAL_LAYERS=%d LINE_WIDTH=0.6 SLICER=R2_GEN' % total_layers)
    return '\n'.join(lines) + '\n'


def g1_x_span(path):
    xs = []
    with open(path, 'r', encoding='utf-8') as handle:
        for line in handle:
            if line.startswith(('G1', 'G0')) and ' X' in line:
                try:
                    xs.append(float(line.split(' X')[1].split()[0]))
                except (ValueError, IndexError):
                    pass
    return (min(xs), max(xs)) if xs else (None, None)


class SystemAdapterTests(unittest.TestCase):

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.base = self._tmp.name
        self.input_path = os.path.join(self.base, 'kette.gcode')
        with open(self.input_path, 'w', encoding='utf-8') as handle:
            handle.write(layered_fixture())

    def _plan(self, steps, name='kette.gcode', menu=False):
        preset = {'schema': toolchain.SCHEMA, 'name': 'Adapterkette',
                  'steps': steps}
        registry = None
        if menu:
            registry = toolchain.build_registry(toolchain.load_menu_data())
        plan, errors = toolchain.plan_chain(preset, name, registry=registry)
        self.assertEqual(errors, [])
        return plan

    def _run(self, plan, output_mode='save', on_output=None,
             input_path=None):
        return toolchain.run_chain(
            plan, os.path.join(self.base, 'Toolchain'),
            input_path or self.input_path,
            lambda step, in_p, out_p: toolchain_steps.system_step_runner(
                step['tool'], step.get('params', {}))(step, in_p, out_p),
            output_mode=output_mode, on_output=on_output)

    def test_system_tools_are_menu_tools(self):
        menu = toolchain.build_registry(toolchain.load_menu_data())
        for tool in toolchain_steps.SYSTEM_TOOLS:
            self.assertIn(tool, menu)

    def test_unknown_tool_has_no_adapter(self):
        with self.assertRaises(ValueError):
            toolchain_steps.system_step_runner('cake', {})

    def test_range_step_writes_the_planned_name(self):
        plan = self._plan([{'tool': 'range',
                            'params': {'start': 2, 'end': 4}}])
        report = self._run(plan)
        self.assertTrue(report['ok'], report['error'])
        final = report['final_output']
        self.assertTrue(os.path.basename(final).startswith('V01_kette'))
        with open(final, 'r', encoding='utf-8') as handle:
            body = handle.read()
        self.assertIn('G1', body)
        # Ausgabe ist ein echte Range-Extrakt: PRINT_END der Range-Engine.
        self.assertIn('R2-RANGE', body)

    def test_full_chain_range_scale_twist(self):
        plan = self._plan([
            {'tool': 'range', 'params': {'start': 2, 'end': 5}},
            {'tool': 'scale', 'params': {'x': 150, 'y': 150}},
            {'tool': 'twist', 'params': {'deg': 25}},
        ])
        report = self._run(plan)
        self.assertTrue(report['ok'], report['error'])
        self.assertEqual([r['state'] for r in report['steps']],
                         ['success', 'success', 'success'])
        # §22.4: beide Zwischenstaende nach Uebernahme geloescht, Ende bleibt.
        self.assertEqual(len(report['temp_deleted']), 2)
        for gone in report['temp_deleted']:
            self.assertFalse(os.path.exists(gone))
        final = report['final_output']
        self.assertTrue(os.path.isfile(final))
        with open(self.input_path, 'r', encoding='utf-8') as handle:
            original = handle.read()
        with open(final, 'r', encoding='utf-8') as handle:
            result = handle.read()
        self.assertNotEqual(original, result)
        self.assertIn('G1', result)

    def test_scale_halves_the_x_span(self):
        plan = self._plan([{'tool': 'scale',
                            'params': {'x': 50, 'y': 100}}])
        report = self._run(plan)
        self.assertTrue(report['ok'], report['error'])
        lo_in, hi_in = g1_x_span(self.input_path)
        lo_out, hi_out = g1_x_span(report['final_output'])
        span_in = hi_in - lo_in
        span_out = hi_out - lo_out
        self.assertAlmostEqual(span_in, 20.0, places=3)
        self.assertAlmostEqual(span_out, 10.0, places=2)

    def test_mirror_keeps_the_span(self):
        plan = self._plan([{'tool': 'mirror',
                            'params': {'axis': 'x'}}])
        report = self._run(plan)
        self.assertTrue(report['ok'], report['error'])
        _, hi_in = g1_x_span(self.input_path)
        _, hi_out = g1_x_span(report['final_output'])
        self.assertAlmostEqual(hi_in - hi_out, 0.0, places=1)

    def test_mirror_accepts_the_lcd_index(self):
        plan = self._plan([{'tool': 'mirror',
                            'params': {'mirror_axis': 1}}], menu=True)
        report = self._run(plan)
        self.assertTrue(report['ok'], report['error'])

    def test_texture_step_on_outer_walls(self):
        plan = self._plan([{'tool': 'texture',
                            'params': {'pattern': 'BARK',
                                       'scale_mm': 12.0,
                                       'zsize_mm': 18.0,
                                       'depth_mm': 0.3}}])
        report = self._run(plan)
        self.assertTrue(report['ok'], report['error'])
        self.assertTrue(os.path.isfile(report['final_output']))

    def test_engine_guard_error_fails_the_chain_traceably(self):
        """Engine-Guard-Fehler wird zum fehlgeschlagenen Schritt mit
        Ursache im Bericht; Stufe 2 bleibt queued. Nebenerkenntnis
        (verhalten wie geliefert, nicht geraten): make_range klemmt 'end'
        auf die echte Schichtzahl der Datei — end=99 auf 6 Schichten
        druckt 2..6; nur ein dadurch leeres Fenster (end <= start) ist
        ein Fehler mit Klartext-Ursache."""
        short_input = os.path.join(self.base, 'kurz.gcode')
        with open(short_input, 'w', encoding='utf-8') as handle:
            handle.write(layered_fixture(total_layers=2))
        plan = self._plan([
            {'tool': 'range', 'params': {'start': 2, 'end': 3}},
            {'tool': 'scale', 'params': {'x': 100, 'y': 100}},
        ], name='kurz.gcode')
        report = self._run(plan, input_path=short_input)
        self.assertFalse(report['ok'])
        self.assertEqual(report['state'], 'failed')
        self.assertEqual([r['state'] for r in report['steps']],
                         ['failed', 'queued'])
        self.assertIn('LAYERS', report['error'].upper())
        # und der Gegenbeweis: dieselbe Kette auf der 6-Schicht-Datei
        # (end=3 passt) laeuft durch
        plan_ok = self._plan([
            {'tool': 'range', 'params': {'start': 2, 'end': 3}},
            {'tool': 'scale', 'params': {'x': 110, 'y': 110}},
        ])
        report_ok = self._run(plan_ok)
        self.assertTrue(report_ok['ok'], report_ok['error'])

    def test_output_mode_queue_hook_with_real_chain(self):
        plan = self._plan([{'tool': 'scale',
                            'params': {'x': 80, 'y': 80}}])
        calls = []
        report = self._run(plan, output_mode='queue',
                           on_output=lambda m, p: calls.append((m, p)))
        self.assertTrue(report['ok'], report['error'])
        self.assertEqual(calls, [('queue', report['final_output'])])

    def test_menu_named_params_work_too(self):
        """Preset mit Menü-Parameternamen (twist_deg) laeuft durch denselben
        Adapter wie Anker-Namen (deg)."""
        plan = self._plan([{'tool': 'twist',
                            'params': {'twist_deg': 10}}], menu=True)
        report = self._run(plan)
        self.assertTrue(report['ok'], report['error'])


class PresetFileChainTests(unittest.TestCase):
    """R259 (Phase 2b/2): der WEG DES NUTZERS, end-to-end offline.

    Preset-DATEI (wie vom SD-Browser gepickt) -> load_preset_file ->
    plan_chain(first_version wie der Watcher: _next_gen_version) ->
    run_chain mit plan_step_runner (gemischte Kette, echte Engines) ->
    Endausgabe validiert, temporäre Zwischenstände aufgeräumt (S22.4).
    """

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.base = self._tmp.name
        self.gcodes = os.path.join(self.base, 'gcodes')
        os.makedirs(self.gcodes)
        self.input_path = os.path.join(self.gcodes, 'kette.gcode')
        with open(self.input_path, 'w', encoding='utf-8') as handle:
            handle.write(layered_fixture())
        self.preset_path = os.path.join(self.gcodes, 'scale-twist.json')
        with open(self.preset_path, 'w', encoding='utf-8') as handle:
            handle.write(json.dumps({
                'schema': toolchain.SCHEMA, 'name': 'Scale up + twist',
                'steps': [{'tool': 'scale',
                           'params': {'x': 110, 'y': 110}},
                          {'tool': 'twist', 'params': {'deg': 45}}]}))

    def test_full_chain_from_a_preset_file(self):
        preset, errors = toolchain.load_preset_file(self.preset_path)
        self.assertEqual(errors, [])
        plan, errors = toolchain.plan_chain(preset, 'kette.gcode',
                                            first_version=3)
        self.assertEqual(errors, [])
        # R260: Temps plain, Endausgabe mit Preset-Wortkette
        # ('Scale up + twist' -> ScaleUpTwist)
        self.assertEqual([s['output'] for s in plan['steps']],
                         ['V03_kette.gcode',
                          'V04_kette_ScaleUpTwist.gcode'])
        workspace = os.path.join(self.gcodes, 'Toolchain')
        runner = toolchain_steps.plan_step_runner(plan)
        seen = []
        report = toolchain.run_chain(plan, workspace, self.input_path,
                                     runner, output_mode='queue',
                                     on_output=lambda m, p: seen.append(
                                         (m, os.path.basename(p))))
        self.assertTrue(report['ok'], report['error'])
        final = report['final_output']
        self.assertEqual(os.path.basename(final),
                         'V04_kette_ScaleUpTwist.gcode')
        self.assertTrue(os.path.isfile(final))
        # S22.4: der Zwischenstand V03 ist erst NACH uebernahme geloescht
        self.assertEqual(report['temp_deleted'],
                         [os.path.join(workspace, 'V03_kette.gcode')])
        self.assertFalse(os.path.exists(
            os.path.join(workspace, 'V03_kette.gcode')))
        # scale 110% ist sichtbar groesser geworden (echte Engine)
        lo, hi = g1_x_span(final)
        src_lo, src_hi = g1_x_span(self.input_path)
        self.assertGreater(hi - lo, (src_hi - src_lo) * 1.05)
        # queue-Registrierung (S21): der Hook sah die Endausgabe
        self.assertEqual(seen, [('queue', 'V04_kette_ScaleUpTwist.gcode')])

    def test_second_run_lifts_version_and_collides_with_nothing(self):
        """Der Watcher vergibt _next_gen_version: Lauf 2 schreibt V05/V06,
        die Endausgabe von Lauf 1 (V04) bleibt unangetastet (S22)."""
        preset, _ = toolchain.load_preset_file(self.preset_path)
        workspace = os.path.join(self.gcodes, 'Toolchain')
        for version, expect in ((3, 'V04_kette_ScaleUpTwist.gcode'),
                                (5, 'V06_kette_ScaleUpTwist.gcode')):
            plan, _ = toolchain.plan_chain(preset, 'kette.gcode',
                                           first_version=version)
            report = toolchain.run_chain(
                plan, workspace, self.input_path,
                toolchain_steps.plan_step_runner(plan))
            self.assertTrue(report['ok'], report['error'])
            self.assertEqual(os.path.basename(report['final_output']),
                             expect)
        self.assertTrue(os.path.isfile(
            os.path.join(workspace, 'V04_kette_ScaleUpTwist.gcode')))
        self.assertTrue(os.path.isfile(
            os.path.join(workspace, 'V06_kette_ScaleUpTwist.gcode')))

    def test_r260_chain_from_a_subfolder_input(self):
        """R260: Ketten-Quelle darf in einem Unterordner liegen (z. B. eine
        Range-Ausgabe) — Stem = Basisname ohne V-Praefix, Endausgabe im
        Toolchain-Ordner getaggt, echte Engines, S22.4."""
        sub = os.path.join(self.gcodes, 'Range')
        os.makedirs(sub, exist_ok=True)
        sub_input = os.path.join(sub, 'V02_kette.gcode')
        with open(sub_input, 'w', encoding='utf-8') as handle:
            handle.write(layered_fixture())
        preset, _ = toolchain.load_preset_file(self.preset_path)
        plan, errors = toolchain.plan_chain(preset, 'Range/V02_kette.gcode')
        self.assertEqual(errors, [])
        workspace = os.path.join(self.gcodes, 'Toolchain')
        report = toolchain.run_chain(
            plan, workspace, sub_input,
            toolchain_steps.plan_step_runner(plan))
        self.assertTrue(report['ok'], report['error'])
        self.assertEqual(os.path.basename(report['final_output']),
                         'V02_kette_ScaleUpTwist.gcode')
        self.assertTrue(os.path.isfile(report['final_output']))
        self.assertFalse(os.path.exists(
            os.path.join(workspace, 'V01_kette.gcode')))   # Temp weg

    def test_broken_preset_file_fails_cleanly_before_any_job(self):
        with open(self.preset_path, 'w', encoding='utf-8') as handle:
            handle.write('{"schema": "r2-toolchain/1"')
        preset, errors = toolchain.load_preset_file(self.preset_path)
        self.assertIsNone(preset)
        self.assertTrue(any('JSON' in e for e in errors), errors)


class SystemWiringTests(unittest.TestCase):
    """R259-Quellverdrahtung: Makro -> Nonce -> Watcher -> Job -> Menü.
    Diese Guards sichern die Nahtstellen, die offline nicht lauffaehig
    sind (Moonraker/Queue) - das Muster: macro_render_test R224-Tests."""

    ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    @classmethod
    def _read(cls, *parts):
        with open(os.path.join(cls.ROOT, *parts), encoding='utf-8') as fh:
            return fh.read()

    def test_watcher_dispatch_and_registrations(self):
        src = self._read('tools', 'r2_postproc.py')
        self.assertIn("'toolchain_nonce')", src.split('NONCE_KEYS = (')[1])
        self.assertIn("'toolchain': 'Toolchain',", src)
        self.assertIn("'toolchain_nonce')", src.split('_freeze133 = (')[1])
        self.assertIn("last_toolchain_nonce = _np.get('toolchain_nonce')",
                      src)
        self.assertIn("rv.get('toolchain_nonce', '')", src)
        self.assertIn("_spawn_job('Toolchain',", src)
        # der SD-Browser zeigt .json (Preset-Pick), R259
        self.assertIn("'.json')", src.split('_SD_EXT151 = (')[1][:220])

    def test_job_uses_this_watchers_engines(self):
        """Der Job injiziert das laufende Modul als _PP - r2_postproc wird
        nie ein zweites Mal geladen (Pi Zero 2 W RAM). Die Injektion prueft
        hasattr (apply_scale/apply_twist/make_range): fremde __main__
        (Tests, andere Einspruenge) fallen auf den eigenen Modul-Ladefall
        zurueck."""
        src = self._read('tools', 'r2_postproc.py')
        self.assertIn('_tcst._PP = _me259', src)
        self.assertIn("sys.modules.get('__main__')", src)
        self.assertIn("hasattr(_me259, _f259)", src)

    def test_macro_and_lcd_and_pick_wired(self):
        macro = self._read('macros', '17_generator.cfg')
        self.assertIn('SAVE_VARIABLE VARIABLE=toolchain_nonce '
                      'VALUE={sv.toolchain_nonce|default(0)|int + 1}', macro)
        self.assertIn('_GEN_GO KEY=toolchain', macro)
        lcd = self._read('menus', 'lcd_menues.cfg')
        self.assertIn('[menu __main __preprint __mods __toolchain __go]',
                      lcd)
        self.assertIn('TOOLCHAIN_APPLY CONFIRM=1', lcd)
        pick = self._read('macros', '13_system.cfg')
        self.assertIn("low.endswith('.json')", pick)
        self.assertIn('SAVE_VARIABLE VARIABLE=toolchain_preset', pick)

    def test_menu_export_carries_the_toolchain_node(self):
        data = toolchain.load_menu_data()
        node = toolchain._find_node(
            data['tree'], '__main __preprint __mods __toolchain')
        self.assertIsNotNone(node)
        kids = [c['id'].split()[-1] for c in node.get('children') or []]
        self.assertEqual(kids, ['__preset', '__src', '__how', '__go'])

    def test_example_preset_ships_and_matches_the_tool_set(self):
        path = os.path.join(self.ROOT, 'presets', 'toolchain',
                            'scale-twist.json')
        preset, errors = toolchain.load_preset_file(path)
        self.assertEqual(errors, [])
        for step in preset['steps']:
            self.assertIn(step['tool'], toolchain_steps.SYSTEM_TOOLS)

    def test_r260_translit_twins_stay_in_sync(self):
        """R260: die Umschrift-Maps sind ZWILLINGE (toolchain._TRANSLIT
        fuer den Plan, r2_postproc._translit_name fuer die Engines) —
        dieser Wächter verhindert Drift. Plus das Verhaltens-Orakel:
        'Größer Rahmen' -> Groesser_Rahmen statt Gr_er_Rahmen."""
        pp, _tex = toolchain_steps._engines()
        self.assertEqual(toolchain._TRANSLIT,
                         {'ä': 'ae', 'ö': 'oe', 'ü': 'ue', 'ß': 'ss',
                          'Ä': 'Ae', 'Ö': 'Oe', 'Ü': 'Ue'})
        self.assertEqual(pp._translit_name('Größer'),
                         toolchain._translit('Größer'))
        self.assertEqual(pp._gen_stem('Größer Rahmen.png'),
                         'Groesser_Rahmen')
        self.assertEqual(
            toolchain._sanitize_stem('Größer Rahmen'), 'Groesser_Rahmen')
        # ASCII-Namen bleiben unberuehrt (Bestandsschutz)
        self.assertEqual(pp._gen_stem('rose_215c_pla.gcode'),
                         'rose_215c_pla')


if __name__ == '__main__':
    unittest.main(verbosity=2)
