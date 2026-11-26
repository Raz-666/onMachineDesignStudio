#!/usr/bin/env python3
"""Paket 4 regression & counter-mutation tests (C1-C5, preview, STL, job service).

Supports `--engine stable` and `--engine next` to verify strict dual-engine parity.
All file operations run inside disposable temporary directories.
"""
import argparse
import ast
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import struct
import sys
import tempfile
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / 'tools'
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

import r2_job_service as js  # noqa: E402

ENGINES = {
    'stable': TOOLS / 'r2_postproc.py',
    'next': TOOLS / 'r2_postproc_next.py',
}
SELECTED_ENGINE = 'stable'
PP = None


def load_engine(which):
    path = ENGINES[which]
    spec = importlib.util.spec_from_file_location(f'r2_pp_{which}', path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _rect_loop(x0, y0, x1, y1, z, e_per_mm=0.05, f=1800):
    pts = [(x1, y0), (x1, y1), (x0, y1), (x0, y0)]
    out = [f'G0 X{x0:.3f} Y{y0:.3f} Z{z:.3f} F6000']
    px, py = x0, y0
    for nx, ny in pts:
        d = ((nx - px) ** 2 + (ny - py) ** 2) ** 0.5
        out.append(f'G1 X{nx:.3f} Y{ny:.3f} E{d * e_per_mm:.5f} F{f}')
        px, py = nx, ny
    return out


def _rect_hatch(x0, y0, x1, y1, z, step=1.0, e_per_mm=0.05, f=1800):
    out = []
    y = y0
    flip = False
    while y <= y1 + 1e-6:
        sx, ex = (x1, x0) if flip else (x0, x1)
        d = abs(ex - sx)
        out.append(f'G0 X{sx:.3f} Y{y:.3f} Z{z:.3f} F6000')
        out.append(f'G1 X{ex:.3f} Y{y:.3f} E{d * e_per_mm:.5f} F{f}')
        y += step
        flip = not flip
    return out


class PostprocPaket4Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        global PP
        PP = load_engine(SELECTED_ENGINE)

    # ---- 4a: _preview_dup_skip state guard --------------------------------
    def test_4a_preview_dup_skip_refuses_when_state_total_layers_missing(self):
        fake_status = {
            'gcode_macro _PREVIEW': {
                'name': 'part.gcode', 'total_layers': 42,
            },
            'gcode_macro _STATE': {'total_layers': 0},
        }
        with tempfile.TemporaryDirectory(prefix='r2-p4a-') as td:
            p = Path(td) / 'part.gcode'
            p.write_text('G28\n', encoding='utf-8')
            PP._preview_remember('part.gcode', str(p), True)
            with mock.patch.object(PP, '_moonraker_status',
                                   return_value=fake_status):
                # _STATE.total_layers is 0 while _PREVIEW has 42 -> must NOT skip!
                self.assertFalse(PP._preview_dup_skip('part.gcode', str(p)))
            # When _STATE.total_layers is populated (>0), true duplicate skips.
            fake_status['gcode_macro _STATE']['total_layers'] = 42
            with mock.patch.object(PP, '_moonraker_status',
                                   return_value=fake_status):
                self.assertTrue(PP._preview_dup_skip('part.gcode', str(p)))
            # Plot/0-layer file (_PREVIEW.total_layers == 0) may still dedup.
            fake_status['gcode_macro _PREVIEW']['total_layers'] = 0
            fake_status['gcode_macro _STATE']['total_layers'] = 0
            with mock.patch.object(PP, '_moonraker_status',
                                   return_value=fake_status):
                self.assertTrue(PP._preview_dup_skip('part.gcode', str(p)))

    # ---- 4b: _GeomScan modal G90/G91 + Klipper E-rel + G92 ----------------
    def test_4b_geomscan_honors_g91_klipper_e_g92_and_inline_comments(self):
        gs = PP._GeomScan()
        lines = [
            'G90 ; M83 G91 must not trigger in comments',
            'M82 ; G91 comment',
            'G0 X10 Y10 Z0.2 F6000',
            'G1 X20 Y10 E0.5 F1800',       # abs E: +0.5 -> extruding
            'G91',                          # Klipper: forces relative E too!
            'G1 X0 Y10 E0.5 F1800',         # rel XYZ (+10Y), rel E (+0.5 -> e=1.0)
            'G90',                          # back to abs XYZ + M82 abs E (e=1.0)
            'G1 X10 Y20 E1.5 F1800',        # abs E 1.0->1.5 (+0.5) -> extruding
            'G92 E0',                       # reset E to 0
            'G1 X10 Y10 E0.5 F1800',        # abs E 0->0.5 (+0.5) -> closes loop!
            'G92 X100 Y100 Z5.0',           # coordinate shift without motion
            'G1 X105 Y100 E0.5 F1800',      # zero delta E -> pure travel
        ]
        for idx, ln in enumerate(lines):
            gs.step(idx, idx, ln)
        self.assertAlmostEqual(gs.x, 105.0, places=4)
        self.assertAlmostEqual(gs.y, 100.0, places=4)
        self.assertAlmostEqual(gs.z, 5.0, places=4)
        self.assertFalse(gs.last_extruding)
        gs.finish()
        self.assertAlmostEqual(gs.tot_len, 40.0, places=3)

        # G90 after M83 keeps E relative.
        gs2 = PP._GeomScan()
        for idx, ln in enumerate([
            'M83', 'G91', 'G1 X10 Y0 Z0.2 E0.5 F1800',
            'G90', 'G1 X20 Y0 E0.5 F1800',
        ]):
            gs2.step(idx, idx, ln)
        self.assertTrue(gs2.last_extruding)
        gs2.finish()
        self.assertAlmostEqual(gs2.tot_len, 20.0, places=3)

    # ---- 4c: _stl_export extrusion gate, G91/G92, atomic STL --------------
    def test_4c_stl_export_rejects_tag_only_and_handles_g91_g92(self):
        with tempfile.TemporaryDirectory(prefix='r2-p4c-') as td:
            # Tag-only file with zero positive extrusion must fail cleanly.
            tag_only = Path(td) / 'tag_only.gcode'
            tag_only.write_text(
                'G90\nM83\n;LAYER:0\n;TYPE:Outer wall\n'
                'G0 X10 Y10 Z0.2 F6000\nG0 X30 Y10 F6000\nG0 X30 Y30 F6000\n',
                encoding='utf-8')
            with self.assertRaises(RuntimeError):
                PP._stl_export(td, 'tag_only.gcode')
            self.assertEqual([], list(Path(td).glob('*.stl*')))
            self.assertEqual([], list(Path(td).glob('.r2stl_*')))

            # Print using G91 (under M82) + G92 E0 exports valid binary STL.
            rel_gc = Path(td) / 'rel_box.gcode'
            rel_gc.write_text('\n'.join([
                'G90', 'M82',
                ';LAYER:0', ';TYPE:Support',
                'G0 X5 Y5 Z0.2 F6000',     # empty support tag -> must NOT leak
                ';TYPE:Outer wall',
                'G0 X20 Y20 Z0.2 F6000',
                'G91',
                'G1 X15 Y0 E0.75 F1800',
                'G1 X0 Y15 E0.75 F1800',
                'G1 X-15 Y0 E0.75 F1800',
                'G1 X0 Y-15 E0.75 F1800',
                'G90', 'G92 E0',
                ';LAYER:1', ';TYPE:Outer wall',
                'G0 X20 Y20 Z0.4 F6000',
                'G1 X35 Y20 E0.75 F1800',
                'G1 X35 Y35 E0.75 F1800',
                'G1 X20 Y35 E0.75 F1800',
                'G1 X20 Y20 E0.75 F1800',
            ]) + '\n', encoding='utf-8')
            stl_path, stl_info = PP._stl_export(td, 'rel_box.gcode')
            self.assertIsInstance(stl_info, dict)
            v = js.validate_job_output(stl_path, root_dir=td)
            self.assertTrue(v['ok'], v)
            self.assertEqual(v['kind'], 'stl')
            self.assertGreater(v['bytes'], 84)
            self.assertEqual([], list(Path(td).glob('.r2stl_*')))

    # ---- 4c2 (R286): _stl_export also_obj - parallel OBJ, vertex-deduped --
    def test_4c2_stl_export_obj_parallel_and_vertex_deduped(self):
        with tempfile.TemporaryDirectory(prefix='r2-p4c2-') as td:
            box = Path(td) / 'box.gcode'
            box.write_text('\n'.join([
                'G90', 'M83',
                ';LAYER:0', ';TYPE:Outer wall',
                'G0 X0 Y0 Z0.2 F6000',
                'G1 X20 Y0 E1.0 F1800',
                'G1 X20 Y20 E1.0 F1800',
                'G1 X0 Y20 E1.0 F1800',
                'G1 X0 Y0 E1.0 F1800',
                ';LAYER:1', ';TYPE:Outer wall',
                'G0 X0 Y0 Z0.4 F6000',
                'G1 X20 Y0 E1.0 F1800',
                'G1 X20 Y20 E1.0 F1800',
                'G1 X0 Y20 E1.0 F1800',
                'G1 X0 Y0 E1.0 F1800',
            ]) + '\n', encoding='utf-8')
            stl_rel, stl_info = PP._stl_export(td, 'box.gcode', also_obj=True)
            self.assertIn('obj', stl_info)
            self.assertIn('obj_vertices', stl_info)
            self.assertGreater(stl_info['obj_vertices'], 0)

            # OBJ file exists next to the STL.
            obj_rel = stl_info['obj']
            self.assertTrue(obj_rel.endswith('_object.obj.gcode'))
            obj_path = Path(td) / obj_rel
            self.assertTrue(obj_path.is_file())

            # Parse OBJ: count v/f, check indices in range, vertex-dedup.
            n_v = n_f = 0
            max_idx = 0
            for ln in obj_path.read_text(encoding='utf-8').splitlines():
                s = ln.strip()
                if s.startswith('v '):
                    n_v += 1
                elif s.startswith('f '):
                    n_f += 1
                    for tok in s[2:].split():
                        try:
                            iv = int(tok.split('/')[0])
                        except ValueError:
                            continue
                        if iv > max_idx:
                            max_idx = iv
            self.assertGreater(n_v, 0)
            self.assertGreater(n_f, 0)
            self.assertLessEqual(max_idx, n_v, 'OBJ index overflow')
            # Vertex dedup: unique vertex lines == reported vertex count.
            self.assertEqual(n_v, stl_info['obj_vertices'])
            # The OBJ and STL share the same triangle count (same mesh).
            self.assertEqual(n_f, stl_info['tris'])
            # No temp leftovers.
            self.assertEqual([], list(Path(td).glob('.r2stl_*')))
            self.assertEqual([], list(Path(td).glob('.r2obj_*')))

            # also_obj=False (default) writes NO obj.
            box2 = Path(td) / 'box2.gcode'
            box2.write_text(box.read_text(encoding='utf-8'), encoding='utf-8')
            stl_rel2, stl_info2 = PP._stl_export(td, 'box2.gcode')
            self.assertNotIn('obj', stl_info2)

    # ---- 4d: C4 cross-slicer aliases, no duplicate keys, inert non-print --
    def test_4d_type_map_has_no_duplicate_keys_and_resolves_c4_aliases(self):
        tree = ast.parse(ENGINES[SELECTED_ENGINE].read_text(encoding='utf-8'))
        found = False
        for node in tree.body:
            if (isinstance(node, ast.Assign)
                    and any(isinstance(t, ast.Name) and t.id == 'TYPE_MAP'
                            for t in node.targets)
                    and isinstance(node.value, ast.Dict)):
                found = True
                keys = [k.value for k in node.value.keys
                        if isinstance(k, ast.Constant)]
                dups = sorted({k for k in keys if keys.count(k) > 1})
                self.assertEqual([], dups, f'duplicate TYPE_MAP keys: {dups}')
        self.assertTrue(found)

        expected = {
            'wipe wall': 'PRIME-TOWER',
            'Wipe pillar': 'PRIME-TOWER',
            'Prime Pillar Path': 'PRIME-TOWER',
            'Flush': 'PRIME-TOWER',
            'flush zone': 'PRIME-TOWER',
            'Gaps in walls': 'GAPS',
            'Crown Path': 'GAPS',
            'crown fill': 'GAPS',
            'gap wall': 'GAPS',
            'Top Solid Fill': 'SURFACE-TOP',
            'top solid shell': 'SURFACE-TOP',
            'Bottom Solid Fill': 'SURFACE-BOTTOM',
            'bottom solid shell': 'SURFACE-BOTTOM',
            'Perimeter Path': 'WALL-OUTER',
            'Hole': 'WALL-INNER',
            'HShell': 'INFILL-SOLID',
            'Pillar Path': 'SUPPORT',
            'None': 'CUSTOM',
            'Other': 'CUSTOM',
        }
        for raw, want in expected.items():
            with self.subTest(raw=raw):
                self.assertEqual(want, PP._canon_type(raw))

        inert_lines = [
            ';TYPE:Destring Path',
            ';TYPE:Wipe Path',
            ';TYPE:Jump Path',
            '; feature Seams',
            '; feature Combing travel',
            ';TYPE:Retraction',
            ';TYPE:Unretraction',
            ';TYPE:Deretract',
            '; feature Non-print move',
            '; feature ToolChanges',
            '; feature ColorChanges',
            '; feature Custom G-code',
        ]
        for line in inert_lines:
            with self.subTest(line=line):
                self.assertIsNone(PP.TYPE_RE.match(line))
                raw_name = line.split(':', 1)[1] if ':' in line else line[10:]
                self.assertEqual('TRAVEL', PP._canon_type(raw_name.strip()))

    # ---- 4e: C2/C3 sequence audit & metamorphic SKIN invariance -----------
    def test_4e_sequence_audit_stacked_brim_by_object_and_commentless_skin(self):
        # Contiguous bed-anchored stacked brim 1..6 is valid.
        seq_stack = [(ln, 'BRIM', 0) for ln in range(1, 7)] + [
            (ln, 'WALL-OUTER', 0) for ln in range(1, 7)
        ]
        self.assertEqual([], PP._sequence_audit193(seq_stack))

        # Detached late brim on layers 5..6 flags S3.
        seq_late = [(1, 'WALL-OUTER', 0), (5, 'BRIM', 0), (6, 'BRIM', 0)]
        self.assertIn('S3 brim beyond the brim window',
                      PP._sequence_audit193(seq_late))

        # Unenclosed stacked top surfaces flag S5; walled multi-top does not.
        seq_unenclosed_top = [
            (1, 'SURFACE-BOTTOM', 0),
            (2, 'SURFACE-TOP', 0),
            (3, 'SURFACE-TOP', 0),
        ]
        self.assertIn('S5 stacked unenclosed top surface',
                      PP._sequence_audit193(seq_unenclosed_top))
        seq_walled_top = [
            (1, 'WALL-OUTER', 0), (1, 'SURFACE-BOTTOM', 0),
            (2, 'WALL-OUTER', 0), (2, 'SURFACE-TOP', 0),
            (3, 'WALL-OUTER', 0), (3, 'SURFACE-TOP', 0),
        ]
        self.assertEqual([], PP._sequence_audit193(seq_walled_top))

        with tempfile.TemporaryDirectory(prefix='r2-p4e-') as td:
            # Sequential by-object print: object 2 at Z=0.2 has BRIM + Cura SKIN.
            seq_gc = Path(td) / 'byobj.gcode'
            lines = ['G90', 'M83',
                     'EXCLUDE_OBJECT_DEFINE NAME=A',
                     'EXCLUDE_OBJECT_DEFINE NAME=B',
                     'EXCLUDE_OBJECT_START NAME=A']
            for k, z in enumerate((0.2, 0.4, 0.6, 0.8, 1.0), 1):
                lines += [f';LAYER:{k - 1}', f';Z:{z:.2f}']
                if k == 1:
                    lines += [';TYPE:SKIRT'] + _rect_loop(5, 5, 35, 35, z)
                lines += [';TYPE:WALL-OUTER'] + _rect_loop(10, 10, 30, 30, z)
                if k in (1, 5):
                    lines += [';TYPE:SKIN'] + _rect_hatch(11, 11, 29, 29, z)
            lines += ['EXCLUDE_OBJECT_END NAME=A',
                      'EXCLUDE_OBJECT_START NAME=B',
                      ';LAYER:5', ';Z:0.20',
                      ';TYPE:BRIM'] + _rect_loop(55, 55, 85, 85, 0.2)
            lines += [';TYPE:WALL-OUTER'] + _rect_loop(60, 60, 80, 80, 0.2)
            lines += [';TYPE:SKIN'] + _rect_hatch(61, 61, 79, 79, 0.2)
            lines += [';LAYER:6', ';Z:0.40',
                      ';TYPE:WALL-OUTER'] + _rect_loop(60, 60, 80, 80, 0.4)
            lines += [';TYPE:SKIN'] + _rect_hatch(61, 61, 79, 79, 0.4)
            lines += ['EXCLUDE_OBJECT_END NAME=B']
            seq_gc.write_text('\n'.join(lines) + '\n', encoding='utf-8')
            s = PP.process(str(seq_gc))
            self.assertNotIn('seq_warn', s)
            txt = seq_gc.read_text(encoding='utf-8')
            # Object B's two SKIN blocks must be BOTTOM (z=0.2) then TOP (z=0.4).
            b_part = txt.split('EXCLUDE_OBJECT_START NAME=B', 1)[1]
            applies = [ln.strip() for ln in b_part.splitlines()
                       if ln.startswith('APPLY_TYPE TYPE=SURFACE-')]
            self.assertEqual(
                ['APPLY_TYPE TYPE=SURFACE-BOTTOM',
                 'APPLY_TYPE TYPE=SURFACE-TOP'], applies)

            # Metamorphic test: Cura SKIN classification identical with and
            # without ;LAYER: comments.
            def _skin_applies(with_comments):
                p = Path(td) / ('cm.gcode' if with_comments else 'nocm.gcode')
                body = ['G90', 'M83']
                for idx, z in enumerate((0.2, 0.4, 0.6)):
                    if with_comments:
                        body.append(f';LAYER:{idx}')
                    body += [';TYPE:WALL-OUTER'] + _rect_loop(10, 10, 25, 25, z)
                    body += [';TYPE:SKIN'] + _rect_hatch(11, 11, 24, 24, z)
                p.write_text('\n'.join(body) + '\n', encoding='utf-8')
                PP.process(str(p))
                return [ln.strip() for ln in p.read_text().splitlines()
                        if ln.startswith('APPLY_TYPE TYPE=SURFACE-')]

            self.assertEqual(_skin_applies(True), _skin_applies(False))
            self.assertEqual(
                ['APPLY_TYPE TYPE=SURFACE-BOTTOM',
                 'APPLY_TYPE TYPE=SURFACE-TOP',
                 'APPLY_TYPE TYPE=SURFACE-TOP'],
                _skin_applies(False))

    # ---- 4f: C1/C5 full-stream tag-vs-geometry audit ----------------------
    def test_4f_audit_tag_geometry_catches_all_six_conflict_classes_past_cap(self):
        with tempfile.TemporaryDirectory(prefix='r2-p4f-') as td:
            p = Path(td) / 'lying_tags.gcode'
            lines = ['G90', 'M83']
            # Pad > 5200 comment/travel lines first to prove no 5000-move cap!
            lines += ['; filler line' for _ in range(5200)]
            # Layer 1 (Z=0.2): base wall + bottom
            lines += [';LAYER_CHANGE', ';Z:0.20',
                      ';TYPE:Outer wall'] + _rect_loop(10, 10, 30, 30, 0.2)
            lines += [';TYPE:Bottom surface'] + _rect_hatch(11, 11, 29, 29, 0.2)
            # Layer 2 (Z=0.4): G6 open hatch labelled Outer wall + G5 floating bridge
            lines += [';LAYER_CHANGE', ';Z:0.40',
                      ';TYPE:Outer wall'] + _rect_hatch(11, 11, 29, 29, 0.4, step=2.0)
            lines += [';TYPE:Bridge'] + _rect_hatch(80, 80, 95, 86, 0.4, step=2.0)
            # Layer 3 (Z=0.6): explicit top + high-flow ironing (G2) + remote ironing (G3)
            lines += [';LAYER_CHANGE', ';Z:0.60',
                      ';TYPE:Top surface'] + _rect_hatch(11, 11, 29, 29, 0.6, step=1.2)
            lines += [';TYPE:Ironing'] + _rect_hatch(
                11, 11, 29, 29, 0.6, step=1.2, e_per_mm=0.05)  # G2 full flow!
            lines += [';TYPE:Ironing'] + _rect_hatch(
                60, 10, 72, 18, 0.6, step=1.5, e_per_mm=0.005)  # G3 no top!
            # Layer 4 (Z=0.8): G4 stacked explicit top over ironed top + G1 floating brim
            lines += [';LAYER_CHANGE', ';Z:0.80',
                      ';TYPE:Top surface'] + _rect_hatch(11, 11, 29, 29, 0.8, step=1.2)
            lines += [';TYPE:Brim'] + _rect_loop(50, 50, 70, 70, 0.8)
            # R281: ironing ON same-layer solid infill (no top surface at
            # all) is LEGAL - Slice Beam irons stepped ceilings exactly this
            # way (field file MAN_V3). The widened G3 support world must NOT
            # fire here, so the G3 count pins it to the remote block alone.
            lines += [';LAYER_CHANGE', ';Z:1.00',
                      ';TYPE:Solid infill']
            lines += _rect_hatch(40, 40, 58, 58, 1.0, step=1.2)
            lines += [';TYPE:Ironing']
            lines += _rect_hatch(40, 40, 58, 58, 1.0, step=0.6, e_per_mm=0.005)
            p.write_text('\n'.join(lines) + '\n', encoding='utf-8')

            s = PP.process(str(p), verify_tagged=True)
            codes = set(s['tag_audit']['by_code'].keys())
            for want in ('G1_FLOATING_ADHESION', 'G2_IRONING_HIGH_FLOW',
                         'G3_IRONING_UNSUPPORTED', 'G4_STACKED_EXPLICIT_TOP',
                         'G5_UNANCHORED_BRIDGE', 'G6_OPEN_HATCH_AS_OUTER_WALL'):
                self.assertIn(want, codes, f'missing {want} in {s["tag_audit"]}')
            # R281: conflicts are a VERDICT - the lying tag world is
            # discarded wholesale and the geometry classifier re-derives
            # every feature (DERIVED=1 + TAGMISMATCH= in _FILE_INFO). The
            # audit itself still reports all six conflict classes above.
            self.assertTrue(s.get('derived', False))
            self.assertEqual(sorted(codes), s.get('tag_mismatch'))
            self.assertIn('TAGMISMATCH=', p.read_text(encoding='utf-8'))
            # R281 mutation pin: exactly ONE G3 (the remote block). The
            # layer-5 ironing riding on solid infill is supported - a G3
            # support world that knows only SURFACE-TOP fires twice here.
            self.assertEqual(
                1, s['tag_audit']['by_code']['G3_IRONING_UNSUPPORTED'],
                f'widened G3 support world broken: {s["tag_audit"]}')

    # ---- 4g: r2_job_service archive, output validation, lifecycle ---------
    def test_4g_original_archive_validator_and_job_registry(self):
        with tempfile.TemporaryDirectory(prefix='r2-p4g-') as td:
            src = Path(td) / 'upload.gcode'
            orig_bytes = (
                b'G90\nM83\n;LAYER:0\n;TYPE:Outer wall\n'
                b'G0 X10 Y10 Z0.2 F6000\nG1 X30 Y10 E1.0 F1800\n'
            )
            src.write_bytes(orig_bytes)
            orig_sha = hashlib.sha256(orig_bytes).hexdigest()

            # process(..., preserve_original=True) saves untouched original first.
            s = PP.process(str(src), preserve_original=td)
            self.assertTrue(s['tagged'])
            self.assertEqual(orig_sha, s['original_sha256'])
            self.assertNotEqual(orig_bytes, src.read_bytes())

            arch = js.OriginalArchive(td)
            self.assertEqual({'ok': True, 'checked': 1, 'errors': []},
                             arch.verify())
            # A second preserve() keeps the FIRST untouched original, not mutated!
            ent2 = arch.preserve(src)
            self.assertTrue(ent2['already_preserved'])
            self.assertEqual(orig_sha, ent2['sha256'])

            # Restore reproduces the exact pre-process upload byte-for-byte.
            arch.restore('upload.gcode')
            self.assertEqual(orig_bytes, src.read_bytes())

            # Counter-mutation: corrupting archived blob MUST fail verify & restore!
            blob = next((Path(td) / '.r2_originals' / 'blobs').glob('*.orig'))
            good_blob = blob.read_bytes()
            blob.write_bytes(good_blob + b'X')
            self.assertFalse(arch.verify()['ok'])
            with self.assertRaises(ValueError):
                arch.restore('upload.gcode')
            blob.write_bytes(good_blob)
            self.assertTrue(arch.verify()['ok'])

            # Security boundaries: protected images, traversal, symlinks refused.
            img = Path(td) / 'photo.png'
            img.write_bytes(b'\x89PNG\r\n\x1a\n')
            with self.assertRaises(ValueError):
                arch.preserve(img)
            self.assertFalse(js.validate_job_output(img, root_dir=td)['ok'])
            with self.assertRaises(ValueError):
                arch.preserve(Path(td) / '..' / 'escape.gcode')
            sym = Path(td) / 'sym.gcode'
            sym.symlink_to(src)
            with self.assertRaises(ValueError):
                arch.preserve(sym)
            self.assertFalse(js.validate_job_output(sym, root_dir=td)['ok'])

            # Output validator rejects NaN G-code, unbalanced EO, bad STL.
            nan_gc = Path(td) / 'nan.gcode'
            nan_gc.write_text('G1 Xnan Y10 E1\n', encoding='utf-8')
            self.assertFalse(js.validate_job_output(nan_gc, root_dir=td)['ok'])

            eo_gc = Path(td) / 'eo.gcode'
            eo_gc.write_text(
                'EXCLUDE_OBJECT_DEFINE NAME=A\nEXCLUDE_OBJECT_START NAME=A\n'
                'G1 X10 Y10 E1\n', encoding='utf-8')
            self.assertFalse(js.validate_job_output(eo_gc, root_dir=td)['ok'])

            zero_stl = Path(td) / 'zero_object.stl.gcode'
            zero_stl.write_bytes(b'\x00' * 80 + struct.pack('<I', 0))
            self.assertFalse(js.validate_job_output(zero_stl, root_dir=td)['ok'])

            degen_stl = Path(td) / 'degen.stl'
            degen_stl.write_bytes(
                b'\x00' * 80 + struct.pack('<I', 1)
                + struct.pack('<12fH', 0, 0, 1, 1, 1, 0, 1, 1, 0, 2, 2, 0, 0))
            self.assertFalse(js.validate_job_output(degen_stl, root_dir=td)['ok'])

            # JobRegistry lifecycle, duplicate suppression, and invalid cleanup.
            reg = js.JobRegistry(max_history=8)
            jid1, ok1 = reg.enqueue('Frame', 'gen:frame', ram_min_mb=60)
            jid_dup, ok_dup = reg.enqueue('Frame', 'gen:frame', ram_min_mb=60)
            self.assertTrue(ok1)
            self.assertFalse(ok_dup)
            self.assertEqual(jid1, jid_dup)
            with self.assertRaises(ValueError):
                reg.transition(jid1, 'succeeded')  # cannot skip running!
            out_ok = Path(td) / 'frame_ok.gcode'
            rec = reg.run_sync(
                jid1,
                lambda: (out_ok.write_text('G28\nG1 X10 Y10 E0.5\n') and None)
                or [out_ok],
                root_dir=td)
            self.assertEqual('succeeded', rec['state'])
            # Terminal jobs release the active key and serialize cleanly to JSON.
            jid2, ok2 = reg.enqueue('Frame', 'gen:frame')
            self.assertTrue(ok2)
            bad_out = Path(td) / 'bad_out.gcode'
            rec2 = reg.run_sync(
                jid2,
                lambda: (bad_out.write_bytes(b'G1 X0\x00Y0\n') and None)
                or [bad_out],
                root_dir=td, remove_invalid_outputs=True)
            self.assertEqual('failed', rec2['state'])
            self.assertFalse(bad_out.exists())
            snap = json.loads(json.dumps(reg.snapshot()))
            self.assertEqual('r2-jobs/1', snap['schema'])
            self.assertEqual([], snap['active_keys'])


def main():
    global SELECTED_ENGINE
    env_eng = os.environ.get('R2_TEST_ENGINE', '').strip().lower()
    default_eng = 'next' if env_eng == 'next' else 'stable'
    ap = argparse.ArgumentParser()
    ap.add_argument('--engine', choices=tuple(ENGINES), default=default_eng)
    args, rest = ap.parse_known_args()
    SELECTED_ENGINE = args.engine
    unittest.main(argv=[sys.argv[0]] + rest)


if __name__ == '__main__':
    main()
