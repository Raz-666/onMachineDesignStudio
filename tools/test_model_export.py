"""Model-only shell export: synthetic oracles plus three field files.

The export must exclude every helper role (support, brim, ironing, custom),
close seams only within budget, and produce closed shells over disjoint z
bands whose summed volume is exact. Field results: all self-intersections
are stacking contacts at documented transition planes, never wall
penetrations. Centreline outlines; never export-ready.
"""
import tempfile
from pathlib import Path
import shutil
import unittest

from contour_mesh import binary_stl
from model_export import model_shells
from self_intersect import self_intersections, triangles_from_stl
from test_field_gcode import FIELD_FILES, unpack


def layer(hint, x0, y0, w, h, z, e=0.5):
    corners = [(x0, y0), (x0+w, y0), (x0+w, y0+h), (x0, y0+h), (x0, y0)]
    lines = [';TYPE:'+hint, 'G0 X%s Y%s Z%s' % (x0, y0, z)]
    lines += ['G1 X%s Y%s E%s' % (b[0], b[1], e) for a, b in zip(corners, corners[1:])]
    return lines


def gcode(*layers):
    return 'G21\nG90\nM83\nG92 E0\n'+'\n'.join(
        line for group in layers for line in group)+'\n'


def polygon_layer(hint, n, radius, z):
    import math
    points = [('%.5f' % (radius*math.cos(2*math.pi*i/n)),
               '%.5f' % (radius*math.sin(2*math.pi*i/n)))
              for i in range(n)]
    lines = [';TYPE:'+hint, 'G0 X%s Y%s Z%s' % (points[0][0], points[0][1], z)]
    lines += ['G1 X%s Y%s E0.1' % p for p in points[1:]]
    lines.append('G1 X%s Y%s E0.1' % points[0])
    return lines


class SyntheticTests(unittest.TestCase):
    def run_export(self, text, **kwargs):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)/'model.gcode'
            path.write_text(text)
            kwargs.setdefault('parser_options', dict())
            kwargs.setdefault('seam_gap_mm', 0.001)
            kwargs.setdefault('z_min_mm', 0.0)
            kwargs.setdefault('z_max_mm', 1.0)
            return model_shells(path, **kwargs)

    def audit_self_intersections(self, data, report):
        with tempfile.NamedTemporaryFile(suffix='.stl') as handle:
            handle.write(data)
            handle.flush()
            triangles = triangles_from_stl(handle.name)
        check = self_intersections(triangles, max_reported_pairs=1000000)
        planes = {round(z, 4) for z in report['transition_planes_mm']}
        for i, j in check['intersecting_pairs']:
            zi = {round(v[2], 4) for v in triangles[i]}
            zj = {round(v[2], 4) for v in triangles[j]}
            shared = zi & zj
            self.assertTrue(shared and shared <= planes,
                            'intersection away from transition planes')
        return check

    def test_identical_layers_merge_into_one_prism(self):
        data, report = self.run_export(gcode(
            layer('External perimeter', 0, 0, 20, 10, .24),
            layer('External perimeter', 0, 0, 20, 10, .4),
            layer('External perimeter', 0, 0, 20, 10, .56)))
        self.assertEqual(report['runs'], 1)
        self.assertEqual(report['shells'], 1)
        self.assertEqual(report['outline_changes'], 0)
        self.assertEqual(report['triangles'], 12)
        self.assertAlmostEqual(report['total_volume_mm3'], 20*10*.56, places=9)
        self.assertEqual(report['audit']['vertex_connected_components'], 1)
        self.assertEqual(self.audit_self_intersections(data, report)
                         ['intersecting_pair_count'], 0)

    def test_outline_change_stacks_disjoint_bands(self):
        data, report = self.run_export(gcode(
            layer('External perimeter', 0, 0, 20, 10, .24),
            layer('External perimeter', 0, 0, 20, 10, .4),
            layer('External perimeter', 5, 2.5, 10, 5, .56)))
        self.assertEqual(report['runs'], 2)
        self.assertEqual(report['shells'], 2)
        self.assertEqual(report['transition_planes_mm'], [.4])
        # 20*10*0.4 + 10*5*0.16: bands are disjoint, so the sum is exact.
        self.assertAlmostEqual(report['total_volume_mm3'], 80+8, places=9)
        self.assertEqual(report['audit']['vertex_connected_components'], 2)
        check = self.audit_self_intersections(data, report)
        self.assertGreater(check['intersecting_pair_count'], 0)
        self.assertFalse(report['export_ready'])

    def test_helpers_and_infill_never_contribute_boundary(self):
        model = [layer('External perimeter', 0, 0, 20, 10, .24),
                 layer('Perimeter', 6, 3, 8, 4, .24),
                 layer('Support material', 50, 50, 5, 5, .24),
                 layer('Skirt/Brim', -5, -5, 40, 20, .24),
                 layer('Ironing', 1, 1, 2, 2, .24),
                 layer('Custom', 60, 0, 3, 3, .24),
                 layer('Perimeter', 0, 0, 20, 10, .4),
                 layer('Solid infill', 7, 4, 6, 2, .4)]
        data, report = self.run_export(gcode(*model))
        # Only wall loops are boundary; the inner perimeter pass is dropped
        # (holes are not inferred), helper roles and infill are excluded,
        # yet the infill layer's z still bounds the wall band from above.
        self.assertEqual(report['counts']['wall_loops'], 3)
        self.assertEqual(report['inner_wall_loops_dropped'], 1)
        self.assertEqual(report['counts']['non_wall_role_paths'], 5)
        self.assertEqual(report['shells'], 1)
        self.assertAlmostEqual(report['total_volume_mm3'], 20*10*.4, places=9)

    def test_vertex_budget_counted_not_exported(self):
        data, report = self.run_export(gcode(
            polygon_layer('External perimeter', 300, 10, .24),
            layer('External perimeter', 0, 0, 20, 10, .4)))
        self.assertEqual(report['counts']['vertex_budget_exceeded'], 1)
        self.assertEqual(report['shells'], 1)
        self.assertAlmostEqual(report['total_volume_mm3'], 20*10*.4, places=9)

    def test_validation_rejections(self):
        text = gcode(layer('External perimeter', 0, 0, 20, 10, .24))
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)/'model.gcode'
            path.write_text(text)
            for kwargs in (dict(seam_gap_mm=-.1),
                           dict(seam_gap_mm=float('nan')),
                           dict(z_min_mm=1.0, z_max_mm=0.0),
                           dict(z_min_mm=0.0, z_max_mm=float('inf'))):
                with self.subTest(kwargs=kwargs):
                    call = dict(parser_options=dict(), seam_gap_mm=.001,
                                z_min_mm=0.0, z_max_mm=1.0)
                    call.update(kwargs)
                    self.assertRaises(ValueError, model_shells, path, **call)
            support_only = Path(directory)/'support.gcode'
            support_only.write_text(gcode(layer('Support material', 0, 0, 5, 5, .24)))
            self.assertRaises(ValueError, model_shells, support_only,
                              parser_options=dict(), seam_gap_mm=.1,
                              z_min_mm=0.0, z_max_mm=1.0)


class FieldExportTests(unittest.TestCase):
    @staticmethod
    def export(name, z0, z1):
        path = unpack(name)
        try:
            return model_shells(path, parser_options=FIELD_FILES[name]['options'],
                                seam_gap_mm=0.1, z_min_mm=z0, z_max_mm=z1)
        finally:
            shutil.rmtree(path.parent)

    def assert_clean_window(self, data, report, **pins):
        audit = report['audit']
        self.assertEqual(audit['boundary_edges'], 0)
        self.assertEqual(audit['nonmanifold_edges'], 0)
        self.assertEqual(audit['winding_errors'], 0)
        self.assertEqual(audit['degenerate_faces'], 0)
        self.assertEqual(audit['vertex_connected_components'], report['shells'])
        # Mesh-derived volume equals the construction volume (float32 STL
        # quantisation is the only difference).
        self.assertAlmostEqual(audit['signed_volume'],
                               report['total_volume_mm3'], places=3)
        self.assertAlmostEqual(audit['bbox'][0][2], report['z_span_mm'][0], places=6)
        self.assertAlmostEqual(audit['bbox'][1][2], report['z_levels_mm'][-1], places=4)
        for key, value in pins.items():
            self.assertEqual(report[key], value, key)
        with tempfile.NamedTemporaryFile(suffix='.stl') as handle:
            handle.write(data)
            handle.flush()
            triangles = triangles_from_stl(handle.name)
        check = self_intersections(triangles, max_reported_pairs=1000000)
        planes = {round(z, 4) for z in report['transition_planes_mm']}
        for i, j in check['intersecting_pairs']:
            zi = {round(v[2], 4) for v in triangles[i]}
            zj = {round(v[2], 4) for v in triangles[j]}
            shared = zi & zj
            self.assertTrue(shared and shared <= planes,
                            'intersection away from transition planes')
        return check['intersecting_pair_count']

    def test_man_v3_window_export(self):
        data, report = self.export('MAN_V3', 0.0, 4.0)
        pairs = self.assert_clean_window(
            data, report, levels=16, runs=16, shells=18, outline_changes=15,
            triangles=3676)
        self.assertEqual(pairs, 6244)
        self.assertAlmostEqual(report['total_volume_mm3'], 64.986970, places=4)
        self.assertEqual(report['counts'], dict(extruding_chains=546,
                                                 wall_loops=32,
                                                 non_wall_role_paths=474,
                                                 seam_closed=32,
                                                 seam_over_budget=40,
                                                 vertex_budget_exceeded=0))
        self.assertEqual(report['inner_wall_loops_dropped'], 12)
        self.assertAlmostEqual(report['seam_max_added_edge_mm'], .0605, places=4)

    def test_vwbus_window_export(self):
        data, report = self.export('vwbus', 0.0, 4.0)
        pairs = self.assert_clean_window(
            data, report, levels=18, runs=18, shells=18, outline_changes=17,
            triangles=3332)
        self.assertEqual(pairs, 12564)
        self.assertAlmostEqual(report['total_volume_mm3'], 348.308140, places=4)
        self.assertEqual(report['counts'], dict(extruding_chains=1149,
                                                 wall_loops=45,
                                                 non_wall_role_paths=1092,
                                                 seam_closed=45,
                                                 seam_over_budget=12,
                                                 vertex_budget_exceeded=0))
        self.assertEqual(report['inner_wall_loops_dropped'], 17)

    def test_pumpkin_window_export(self):
        data, report = self.export('Pumpkin_Scream_MULTI-011', 0.0, 4.0)
        pairs = self.assert_clean_window(
            data, report, levels=18, runs=18, shells=21, outline_changes=17,
            triangles=4236)
        self.assertEqual(pairs, 22321)
        self.assertAlmostEqual(report['total_volume_mm3'], 334.336933, places=4)
        self.assertEqual(report['counts'], dict(extruding_chains=769,
                                                 wall_loops=76,
                                                 non_wall_role_paths=535,
                                                 seam_closed=64,
                                                 seam_over_budget=108,
                                                 vertex_budget_exceeded=50))
        self.assertEqual(report['inner_wall_loops_dropped'], 19)


if __name__ == '__main__':
    unittest.main(verbosity=2)
