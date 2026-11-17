#!/usr/bin/env python3
"""Paket 5 regression & counter-mutation tests for r2_shadow, r2_analysis, r2_offline."""
import hashlib
import json
import math
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

TOOLS = Path(__file__).resolve().parent
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

import r2_analysis as analysis  # noqa: E402
import r2_offline as offline    # noqa: E402
import r2_shadow as shadow      # noqa: E402


def _run_analysis(text, **shadow_kwargs):
    st = shadow.Shadow(**shadow_kwargs)
    tr = analysis.Tracker()
    for lno, raw in enumerate(text.splitlines(keepends=True), 1):
        rec = st.process(raw, lno)
        tr.observe(raw, rec)
    return tr.finish()


class ShadowAndAnalysisV2Tests(unittest.TestCase):
    def test_g17_xy_arcs_semicircle_fullcircle_helical_and_cardinal_bounds(self):
        s = shadow.Shadow(enable_arcs=True)
        for i, cmd in enumerate(('G21', 'G17', 'G90', 'M83',
                                 'G0 X10 Y0 Z0.2 F6000'), 1):
            self.assertIn(s.process(cmd + '\n', i)['kind'], ('mode', 'move'))

        # CCW semicircle from (10, 0) to (-10, 0) centered at (0, 0): crosses (0, +10)!
        semi = s.process('G3 X-10 Y0 I-10 J0 E1.5 F1800\n', 10)
        self.assertEqual('arc', semi['kind'])
        self.assertFalse(semi['clockwise'])
        self.assertAlmostEqual(10.0, semi['radius_mm'], places=5)
        self.assertAlmostEqual(math.pi * 10.0, semi['arc_length_mm'], places=4)
        self.assertAlmostEqual(1.5, semi['commanded_e_delta_mm'], places=5)
        bx0, by0, bx1, by1 = semi['bounds_xy_mm']
        self.assertAlmostEqual(-10.0, bx0, places=5)
        self.assertAlmostEqual(0.0, by0, places=5)
        self.assertAlmostEqual(10.0, bx1, places=5)
        self.assertAlmostEqual(10.0, by1, places=5)  # cardinal bulge captured!

        # CW helical full circle from (-10, 0) back to (-10, 0), center (0, 0), Z 0.2->0.4
        full = s.process('G2 X-10 Y0 Z0.4 I10 J0 E3.0 F1800\n', 11)
        self.assertEqual('arc', full['kind'])
        self.assertTrue(full['clockwise'])
        self.assertAlmostEqual(2.0 * math.pi * 10.0, full['arc_length_mm'], places=4)
        self.assertAlmostEqual(0.4, full['end_mm']['Z'], places=5)
        for got, want in zip(full['bounds_xy_mm'], (-10.0, -10.0, 10.0, 10.0)):
            self.assertAlmostEqual(want, got, places=5)
        pts = shadow.sample_arc_points(full, resolution_mm=2.0)
        self.assertGreater(len(pts), 20)
        self.assertAlmostEqual(0.2, pts[0][2], places=5)
        self.assertAlmostEqual(0.4, pts[-1][2], places=5)

        # Klipper G91 + M82 forces relative E on G2/G3 arcs too.
        s.process('M82\n', 12)
        s.process('G92 E5\n', 13)
        s.process('G91\n', 14)
        rel_arc = s.process('G2 X10 Y10 I10 J0 E0.8 F1200\n', 15)
        self.assertEqual('arc', rel_arc['kind'])
        self.assertEqual('relative', rel_arc['e_mode'])
        self.assertAlmostEqual(0.8, rel_arc['commanded_e_delta_mm'], places=5)
        self.assertAlmostEqual(5.8, s.e, places=5)
        self.assertAlmostEqual(0.0, rel_arc['end_mm']['X'], places=5)
        self.assertAlmostEqual(10.0, rel_arc['end_mm']['Y'], places=5)

    def test_arcs_fail_closed_on_g18_g19_bad_radius_zero_radius_r_param(self):
        cases = [
            ['G21', 'G90', 'M83', 'G18'],                          # XZ plane
            ['G21', 'G90', 'M83', 'G19'],                          # YZ plane
            ['G21', 'G17', 'G90', 'M83', 'G0 X0 Y0',
             'G2 X10 Y0 I2 J0 E1'],                                # r0=2 vs r1=8!
            ['G21', 'G17', 'G90', 'M83', 'G0 X0 Y0',
             'G2 X0 Y0 I0 J0 E1'],                                 # zero radius!
            ['G21', 'G17', 'G90', 'M83', 'G0 X0 Y0',
             'G2 X10 Y0 R5 E1'],                                   # R-form rejected
            ['G21', 'G17', 'G90', 'M83', 'G2 X10 Y0 I5 J0 E1'],    # unknown start XY
        ]
        for seq in cases:
            with self.subTest(last=seq[-1]):
                st = shadow.Shadow(enable_arcs=True)
                last = None
                for idx, ln in enumerate(seq, 1):
                    last = st.process(ln + '\n', idx)
                self.assertEqual('unknown', last['kind'])
                self.assertIsNone(st.units_mm)
                self.assertIsNone(st.position['X'])

    def test_motors_off_firmware_retract_and_optin_passive_provenance(self):
        st = shadow.Shadow(assume_klipper_defaults=True,
                           firmware_retract=True,
                           klipper_passive=True,
                           verified_r2_passive=True)
        st.process('G92 E0\n', 1)
        st.process('G0 X10 Y20 Z0.2 F6000\n', 2)
        r_r2 = st.process('APPLY_TYPE TYPE=WALL-OUTER\n', 3)
        self.assertEqual('verified_r2_passive', r_r2['kind'])
        r_kp = st.process('EXCLUDE_OBJECT_START NAME=part1\n', 4)
        self.assertEqual('klipper_passive', r_kp['kind'])
        r_ret = st.process('G10\n', 5)
        self.assertEqual('firmware_retract', r_ret['kind'])
        self.assertTrue(r_ret['retracted'])
        r_unr = st.process('G11\n', 6)
        self.assertFalse(r_unr['retracted'])
        # Position survived all passive + fw-retract events
        mv = st.process('G1 X30 Y20 E1.0 F1800\n', 7)
        self.assertEqual((10.0, 20.0), (mv['start_mm']['X'], mv['start_mm']['Y']))

        # Partial M84 X invalidates only X and E; Y and Z and G90 stay intact!
        mo = st.process('M84 X\n', 8)
        self.assertEqual('motors_off', mo['kind'])
        self.assertEqual(['X'], mo['disabled_axes'])
        self.assertIsNone(st.position['X'])
        self.assertEqual(20.0, st.position['Y'])
        self.assertEqual(0.2, st.position['Z'])
        self.assertTrue(st.xyz_absolute)

        # Full M18 invalidates all XYZ and E.
        mo2 = st.process('M18\n', 9)
        self.assertEqual(['X', 'Y', 'Z'], mo2['disabled_axes'])
        self.assertEqual({'X': None, 'Y': None, 'Z': None}, st.position)
        self.assertIsNone(st.e)

    def test_pass_3_to_10_units_zhops_vase_arcs_topology_support_and_conflicts(self):
        # 1. Z-hops do NOT inflate physical layer count; outer+nested loops detected.
        gcode = '\n'.join([
            '; filament_diameter = 1.75',
            'EXCLUDE_OBJECT_DEFINE NAME=box',
            'G21', 'G17', 'G90', 'M83',
            'EXCLUDE_OBJECT_START NAME=box',
            ';TYPE:Outer wall',
            'G0 X10 Y10 Z0.2 F6000',
            'G1 X50 Y10 E2.0 F1800',
            'G1 X50 Y50 E2.0 F1800',
            'G1 X10 Y50 E2.0 F1800',
            'G1 X10 Y10 E2.0 F1800',
            'G10',
            'G0 Z0.8 F3000',                # Z-hop up
            'G0 X20 Y20 F9000',
            'G0 Z0.2 F3000',                # Z-hop down
            'G11',
            ';TYPE:Inner wall',
            'G1 X40 Y20 E1.0 F1800',        # nested loop inside outer wall!
            'G1 X40 Y40 E1.0 F1800',
            'G1 X20 Y40 E1.0 F1800',
            'G1 X20 Y20 E1.0 F1800',
            # Layer 2 at Z=0.4 directly over layer 1 + an arc on right side
            'G0 X10 Y10 Z0.4 F6000',
            ';TYPE:Outer wall',
            'G1 X50 Y10 E2.0 F1800',
            'G3 X50 Y50 I0 J20 E3.14 F1800',  # bulges out to X=70!
            'G1 X10 Y50 E2.0 F1800',
            'G1 X10 Y10 E2.0 F1800',
            'EXCLUDE_OBJECT_END NAME=box',
        ]) + '\n'
        ev = _run_analysis(gcode, enable_arcs=True, firmware_retract=True,
                           klipper_passive=True)
        self.assertEqual('r2-evidence/1', ev['schema'])
        ul = ev['units_and_layers']
        self.assertEqual(1, ul['unit_count'])
        self.assertEqual(2, ul['physical_extrusion_layers'])
        self.assertEqual(1, ul['z_hop_count'])
        self.assertEqual(1, ev['kinematics']['arc_extruding_moves'])
        self.assertEqual(1, ev['kinematics']['firmware_retracts'])
        self.assertEqual(1, ev['kinematics']['firmware_deretracts'])
        # Footprint captures arc bulge out to X=70!
        fp = ev['object_footprints'][0]
        self.assertEqual('box', fp['object_name'])
        self.assertAlmostEqual(70.0, fp['bounds_xy_mm'][2], places=3)
        # Topology: outer + nested loop both counted
        self.assertGreaterEqual(ev['topology_2d']['outer_closed_loops'], 2)
        self.assertEqual(1, ev['topology_2d']['nested_closed_loops'])
        self.assertGreater(ev['support_3d']['supported_ratio'], 0.5)
        self.assertEqual([], ev['sequence_and_tag_audit']['geometry_conflicts'])

        # 2. Continuous spiral vase detection
        vase_lines = ['G21', 'G90', 'M83', 'G0 X20 Y0 Z0.2 F6000']
        z = 0.2
        for k in range(1, 41):
            ang = 2.0 * math.pi * (k / 20.0)
            z += 0.01
            vase_lines.append(
                f'G1 X{20 * math.cos(ang):.3f} Y{20 * math.sin(ang):.3f} '
                f'Z{z:.3f} E0.3 F1800')
        ev_vase = _run_analysis('\n'.join(vase_lines) + '\n')
        self.assertTrue(ev_vase['units_and_layers']['vase_mode_likely'])

    def test_offline_audit_mode_detects_conflicts_and_preserves_source(self):
        with tempfile.TemporaryDirectory(prefix='r2-p5-off-') as td:
            src = Path(td) / 'bad.gcode'
            out = Path(td) / 'audit.json'
            lines = [
                'G21', 'G90', 'M83',
                ';LAYER_CHANGE', ';Z:0.20',
                ';TYPE:Ironing',                       # S1 + S2!
                'G0 X10 Y10 Z0.20 F6000',
                'G1 X30 Y10 E0.1 F1200',
                ';LAYER_CHANGE', ';Z:0.40',
                ';TYPE:Bridge',                        # G5 unanchored bridge!
                'G0 X80 Y80 Z0.40 F6000',
                'G1 X95 Y80 E0.8 F1200',
                'G0 X80 Y82 Z0.40 F6000',
                'G1 X95 Y82 E0.8 F1200',
            ]
            raw = ('\n'.join(lines) + '\n').encode('utf-8')
            src.write_bytes(raw)
            sha_before = hashlib.sha256(raw).hexdigest()

            rc = offline.main(['audit', str(src), str(out)])
            self.assertEqual(0, rc)
            self.assertEqual(sha_before, hashlib.sha256(src.read_bytes()).hexdigest())
            data = json.loads(out.read_text(encoding='utf-8'))
            self.assertEqual('audit', data['mode'])
            self.assertEqual('findings_present', data['audit_summary']['status'])
            self.assertGreaterEqual(data['audit_summary']['sequence_violation_count'], 2)
            self.assertIn('G5_UNANCHORED_BRIDGE', data['tag_geometry_audit']['by_code'])
            self.assertIn(
                'G5_UNANCHORED_BRIDGE',
                data['analysis']['evidence']['sequence_and_tag_audit']['geometry_conflicts_by_code'],
            )

            # derive MUST reject report/audit-only flags.
            der_out = Path(td) / 'derived.gcode'
            self.assertEqual(
                1, offline.main(['derive', '--enable-arcs', str(src), str(der_out)]))
            self.assertFalse(der_out.exists())

            # Counter-mutation: if arc geometry silently returns chord bbox,
            # semicircle cardinal-extrema assertion MUST catch it!
            def _broken_arc(sx, sy, ex, ey, i_off, j_off, cw):
                cx, cy, r, sw, al, _ = orig_arc(sx, sy, ex, ey, i_off, j_off, cw)
                return cx, cy, r, sw, al, [min(sx, ex), min(sy, ey), max(sx, ex), max(sy, ey)]

            orig_arc = shadow._arc_geometry_xy
            with mock.patch.object(shadow, '_arc_geometry_xy', side_effect=_broken_arc):
                st = shadow.Shadow(assume_klipper_defaults=True, enable_arcs=True)
                st.process('G0 X10 Y0 Z0.2\n', 1)
                rec = st.process('G3 X-10 Y0 I-10 J0 E1\n', 2)
                self.assertNotAlmostEqual(10.0, rec['bounds_xy_mm'][3], places=2)


if __name__ == '__main__':
    unittest.main()
