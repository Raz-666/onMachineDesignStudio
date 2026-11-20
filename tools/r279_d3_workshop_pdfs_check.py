#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""R279 check: D3/D6 Scientific Generator PDFs — Paket 3 (Werkstatt & Grundkörper,
Abschluss aller 13 von 13 Einzel-Generator-PDFs!):
  - ANGLES.pdf     (tools/make_angles_pdf.py)
  - CABLETIES.pdf  (tools/make_cableties_pdf.py)
  - GASKETS.pdf    (tools/make_gaskets_pdf.py)
  - GEOMETRY.pdf   (tools/make_geometry_pdf.py)

Pure stdlib gate (no reportlab/pypdfium2/PIL required at test time!). Runs live
algorithmic pins against r2_postproc (Angles auto-clamp + FLAT splice, Cable ties
CLASSIC + LOOP honest TYPES, Seal NUT + narrow-band auto-fallback, Shape VASE
3D helix + POLY sleeve, Bridge >= 10 mm air-gap clamp), verifies all 13/13 D3
PDFs exist in the repo root, and checks R252 r2_postproc_next.py parity.
"""
import base64
import os
import re
import sys
import tempfile
import zlib

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
sys.path.insert(0, HERE)

import r2_postproc as pp  # noqa: E402
from r2_version import VERSION as R2VER  # noqa: E402

fails = 0
total = 0


def check(name, cond, detail=''):
    global fails, total
    total += 1
    if cond:
        print('  ok   ' + name)
    else:
        fails += 1
        print('  FAIL ' + name + (' -> ' + str(detail) if detail else ''))


def _pdf_text_and_pages(pdf_path):
    raw = open(pdf_path, 'rb').read()
    pages = len(re.findall(rb'/Type\s*/Page[^s]', raw))
    imgs = len(re.findall(rb'/Subtype\s*/Image', raw))
    chunks = [raw]
    for m in re.finditer(rb'stream[\r\n]+(.*?)[\r\n]*endstream', raw, re.S):
        s = m.group(1).strip()
        s_a85 = s[:-2] if s.endswith(b'~>') else s
        for dec in (lambda b: zlib.decompress(base64.a85decode(b)),
                    lambda _b: zlib.decompress(s)):
            try:
                chunks.append(dec(s_a85))
                break
            except Exception:
                pass
    joined = b'\n'.join(chunks).replace(b'\\(', b'(').replace(b'\\)', b')')
    return pages, imgs, joined


def main():
    print('==== R279 D3 WORKSHOP/GEOMETRY GENERATOR PDFS CHECK (13/13 COMPLETE) ====')

    specs = [
        ('ANGLES.pdf', 'make_angles_pdf.py', 5,
         [b'make_angles', b'_poly_hatch', b'Countersunk', b'Stepped',
          b'FLAT', b'PLATE_1', b'Schritt']),
        ('CABLETIES.pdf', 'make_cableties_pdf.py', 5,
         [b'make_cable_ties', b'CLASSIC', b'LOOP', b'Pawl', b'TIE_',
          b'hole_polys', b'Schritt']),
        ('GASKETS.pdf', 'make_gaskets_pdf.py', 5,
         [b'make_seal', b'FLAT', b'NUT', b'1,67', b'0,95',
          b'Ironing', b'Schritt']),
        ('GEOMETRY.pdf', 'make_geometry_pdf.py', 5,
         [b'make_shape', b'make_bridge', b'CYLINDER', b'TRIANGLE',
          b'VASE', b'BRIDGE_LONG', b'Schritt']),
    ]

    ver_bytes = R2VER.encode('utf-8')
    hardcoded_ver_re = re.compile(r'R2-202\d-\d\d-\d\d')

    for pdf_name, builder_name, min_pages, needles in specs:
        pdf_p = os.path.join(REPO, pdf_name)
        bld_p = os.path.join(HERE, builder_name)
        src = open(bld_p, encoding='utf-8').read() if os.path.isfile(bld_p) else ''

        check('%s: exists, imports r2_version, uses re.split menu parser, no hardcoded version'
              % builder_name,
              bool(src)
              and 'from r2_version import VERSION' in src
              and 're.split(r\'(?m)^(?=\\[menu )\'' in src
              and '.render()' in src
              and not hardcoded_ver_re.search(src))

        formula_blocks = re.findall(r'FORMULA\((.*?)\n\s*\)', src, re.S)
        bad_nl = [fb for fb in formula_blocks if r'\n' in fb]
        check('%s: FORMULA() blocks use <br/> instead of literal \\n'
              % builder_name,
              len(formula_blocks) >= 1 and not bad_nl,
              'bad_formula_blocks=%d' % len(bad_nl))

        exists = os.path.isfile(pdf_p) and open(pdf_p, 'rb').read(5) == b'%PDF-'
        pages, imgs, stream_bytes = _pdf_text_and_pages(pdf_p) if exists else (0, 0, b'')
        check('%s: valid PDF >= %d pages with >= 2 live PNG figures and current R2VER (%s)'
              % (pdf_name, min_pages, R2VER),
              exists and pages >= min_pages and imgs >= 2 and ver_bytes in stream_bytes,
              'exists=%s pages=%d imgs=%d' % (exists, pages, imgs))

        missing = [nd.decode('utf-8') for nd in needles if nd not in stream_bytes]
        check('%s: mathematical, algorithmic & live-menu key terms present in PDF streams'
              % pdf_name,
              not missing,
              'missing=%s' % missing)

    # ---- Full 13/13 D3 generator PDF suite inventory check -----------------
    all_13_d3 = (
        'MOLDS.pdf',
        'STENCIL.pdf', 'LITHOPHANE.pdf', 'COLORPIC.pdf', 'STRINGART.pdf',
        'BRICKS.pdf', 'LABELS.pdf', 'FRAMES.pdf', 'PLOTTER.pdf',
        'ANGLES.pdf', 'CABLETIES.pdf', 'GASKETS.pdf', 'GEOMETRY.pdf',
    )
    missing_d3 = [fn for fn in all_13_d3 if not os.path.isfile(os.path.join(REPO, fn))]
    check('All 13/13 individual D3 scientific generator PDFs exist in repo root',
          not missing_d3,
          'missing=%s' % missing_d3)

    # ---- Live algorithmic engine pins --------------------------------------
    with tempfile.TemporaryDirectory(prefix='r279_gate_') as td:
        # 1. make_angles: narrow-leg auto-clamp (hole_d, hole count, walls) + FLAT mode
        f_ac, i_ac = pp.make_angles(
            count=1, angle_deg=90, leg_a=34, leg_b=50, width=10, layers=6,
            holes=5, hole_d=8.0, countersink=True, stiffener=0, flat=False,
            walls=6, infill=100, nozzle=0.6, out_dir=td,
        )
        txt_ac = open(f_ac, encoding='utf-8').read()
        check('make_angles(width=10, d=8, holes=5, walls=6): clamps d->4.0mm, holes & walls',
              abs(i_ac['hole_d'] - 4.0) < 1e-6
              and i_ac['walls'] == 4
              and i_ac['holes'] == '2+5'
              and 'NAME=PLATE_1' in txt_ac,
              str(i_ac))

        f_fl, i_fl = pp.make_angles(
            count=1, leg_a=45, leg_b=45, width=20, layers=5,
            holes=2, hole_d=4.0, flat=True, nozzle=0.4, out_dir=td,
        )
        check('make_angles(flat=True): builds 180-deg symmetric splice strip (Vnn_Flat_*)',
              i_fl['kind'] == 'FLAT' and '_Flat_' in i_fl['file'] and i_fl['stiffener'] == 0,
              str(i_fl))

        # 2. make_cable_ties: CLASSIC vs LOOP (honest R197 TYPES= without SURFACE-TOP)
        f_tc, i_tc = pp.make_cable_ties(
            count=3, length=100, width=6.0, layers=3, variant='CLASSIC',
            brim=True, nozzle=0.4, out_dir=td,
        )
        txt_tc = open(f_tc, encoding='utf-8').read()
        f_tl, i_tl = pp.make_cable_ties(
            count=2, length=100, width=6.0, layers=3, variant='LOOP',
            brim=False, nozzle=0.4, out_dir=td,
        )
        txt_tl = open(f_tl, encoding='utf-8').read()
        check('make_cable_ties(CLASSIC vs LOOP): head-only brim, TIE_k objects & honest R197 TYPES',
              i_tc['layers'] == 10
              and 'NAME=TIE_3' in txt_tc
              and 'SURFACE-TOP' in txt_tc
              and i_tl['layers'] == 5
              and 'SURFACE-TOP' not in txt_tl,
              'cla_L=%d loo_L=%d' % (i_tc['layers'], i_tl['layers']))

        # 3. make_seal: NUT dual-lip + Ironing vs narrow-band NUT->FLAT fallback
        f_sn, i_sn = pp.make_seal(
            od=48.0, id_=24.0, height=2.0, profile='NUT', ironing=True,
            layer_h=0.2, nozzle=0.4, out_dir=td,
        )
        txt_sn = open(f_sn, encoding='utf-8').read()
        _f_sf, i_sf = pp.make_seal(
            od=24.0, id_=20.4, height=1.2, profile='NUT', ironing=False,
            layer_h=0.2, nozzle=0.4, out_dir=td,
        )
        check('make_seal(NUT): builds GROOVE + IRONING on wide ring & falls back to FLAT on narrow ring',
              i_sn['profile'] == 'GROOVE'
              and 'APPLY_TYPE TYPE=IRONING' in txt_sn
              and i_sf['profile'] == 'FLAT'
              and any('groove skipped' in n for n in i_sf['notes']),
              'wide=%s narrow=%s' % (i_sn['profile'], i_sf['profile']))

        # 4. make_shape: VASE mode continuous 3D Z-helix + honest R217 TYPES
        f_sv, i_sv = pp.make_shape(
            shape='CYLINDER', size_x=40, size_y=40, corners=0, height=16,
            walls=1, infill=30, base=3, nozzle=0.4, out_dir=td,
        )
        txt_sv = open(f_sv, encoding='utf-8').read()
        z_vals = [float(m.group(1)) for m in re.finditer(r'G1 X[0-9.]+ Y[0-9.]+ Z([0-9.]+) E', txt_sv)]
        check('make_shape(walls=1): emits continuous 3D Z-helix (vase=True, top=0, R217 honest TYPES)',
              i_sv['vase'] is True
              and i_sv['top'] == 0
              and len(z_vals) > 500
              and z_vals[-1] > z_vals[0] + 10.0
              and 'WALL-INNER' not in txt_sv,
              'helix_segs=%d' % len(z_vals))

        # 5. make_bridge: >= 10.0 mm vertical clearance clamp + 5 EXCLUDE_OBJECTs
        f_br, i_br = pp.make_bridge(
            length=150.0, short_pct=30, h_long=26.0, h_short=22.0,
            tower=10.0, bridge_layers=1, nozzle=0.4, out_dir=td,
        )
        txt_br = open(f_br, encoding='utf-8').read()
        check('make_bridge(h_long=26, h_short=22): enforces >= 10 mm air gap & 5 EXCLUDE_OBJECTs',
              (i_br['h_long'] - i_br['h_short']) >= 9.99
              and all(('NAME=%s' % nm) in txt_br
                      for nm in ('TOWER_A', 'TOWER_B', 'TOWER_C', 'BRIDGE_SHORT', 'BRIDGE_LONG')),
              'dz=%.2f' % (i_br['h_long'] - i_br['h_short']))

    # ---- Docs & R252 parity checks -----------------------------------------
    inv = open(os.path.join(REPO, 'docs', 'TOOLS_INVENTORY.md'), encoding='utf-8').read()
    todo = open(os.path.join(REPO, 'docs-notes', 'MASTER-TODO.md'), encoding='utf-8').read()
    check('TOOLS_INVENTORY.md & MASTER-TODO.md list R279 builders + mark D3 as [x] completed',
          all(k in inv for k in ('make_angles_pdf.py', 'make_cableties_pdf.py',
                                 'make_gaskets_pdf.py', 'make_geometry_pdf.py',
                                 'r279_d3_workshop_pdfs_check.py'))
          and '- [x] **D3 — Pro Generator eine wissenschaftliche PDF**' in todo)

    p_main = open(os.path.join(HERE, 'r2_postproc.py'), encoding='utf-8').read().splitlines()
    p_next = open(os.path.join(HERE, 'r2_postproc_next.py'), encoding='utf-8').read().splitlines()
    check('r2_postproc_next.py matches r2_postproc.py except header lines 2-3 (R252 invariant)',
          len(p_main) == len(p_next)
          and p_main[0] == p_next[0]
          and p_main[3:] == p_next[3:])

    print('---- %d checks, %d failed ----' % (total, fails))
    sys.exit(1 if fails else 0)


if __name__ == '__main__':
    main()
