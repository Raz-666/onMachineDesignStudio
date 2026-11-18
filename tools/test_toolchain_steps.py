#!/usr/bin/env python3
# ============================================================================
# test_toolchain_steps.py — Orakel-Tests fuer die System-Adapter (Phase 2b/1)
# ============================================================================
# Ketten laufen mit den ECHTEN Engines (make_range/apply_scale/apply_twist/
# apply_mirror/apply_texture) gegen synthetische, markierte G-Code-Fixtures
# (LAYER_CHANGE/LAYER_MARK/;Z:-Bloecke, Muster: v1_range_cause_check.py).
# Alles offline: keine Moonraker-/Druckerabhaengigkeit, temporaere Verzeichnisse.
# ============================================================================

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


if __name__ == '__main__':
    unittest.main(verbosity=2)
