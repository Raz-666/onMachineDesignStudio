#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""R276 check: D4/D6 Pre-Print geometry modifier mathematics PDFs
(SCALE.pdf, TWIST.pdf, MIRROR.pdf, RANGE.pdf, TOOLCHAIN.pdf) + R276 engine
fixes in apply_twist() and apply_mirror() (M82 + G2/G3 arc extrusion sync,
single-axis modal X/Y rotation, and header EXCLUDE_OBJECT_DEFINE mirroring
under OBJ=<name>) + r2_postproc_next.py parity.

Pure stdlib so it runs in every CI/Pi environment without reportlab/pypdfium2.
"""
import base64
import math
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


def _sum_pos_de_m82(gcode_path):
    from r2_texture import _parse_move, _parse_arc
    last_e = 0.0
    tot = 0.0
    neg_jumps = 0
    with open(gcode_path, encoding='utf-8', errors='replace') as f:
        for raw in f:
            ls = raw.split(';', 1)[0].strip()
            if ls.startswith('G92'):
                m = re.search(r'E(-?[\d.]+)', ls)
                if m:
                    last_e = float(m.group(1))
                continue
            g = _parse_move(ls)
            ev = g[4] if g is not None else None
            if ev is None:
                ga = _parse_arc(ls)
                if ga is not None:
                    ev = ga[7]
            if ev is not None:
                de = ev - last_e
                if de > 0:
                    tot += de
                elif de < -0.001:
                    neg_jumps += 1
                last_e = ev
    return tot, neg_jumps


def main():
    print('==== R276 D4 MODIFIER PDFS & ISOMETRIC ARC-SYNC CHECK ====')

    specs = [
        ('SCALE.pdf', 'make_scale_pdf.py', 5,
         [b'SCALE_APPLY', b'apply_scale', b'ezmax', b'Top X', b'Blind']),
        ('TWIST.pdf', 'make_twist_pdf.py', 5,
         [b'TWIST_APPLY', b'apply_twist', b'SO(2)', b'R_circ', b'Blind']),
        ('MIRROR.pdf', 'make_mirror_pdf.py', 5,
         [b'MIRROR_APPLY', b'apply_mirror', b'POLYGON=', b'RIGHT_HOOK', b'Blind']),
        ('RANGE.pdf', 'make_range_pdf.py', 5,
         [b'make_range', b'SET_STOP_AT_LAYER', b'FOOTPRINT', b'OUTLINE', b'inside']),
        ('TOOLCHAIN.pdf', 'make_toolchain_pdf.py', 5,
         [b'TOOLCHAIN_APPLY', b'r2-toolchain/1', b'run_chain', b'SET_GCODE_OFFSET', b'Blind']),
    ]

    ver_bytes = R2VER.encode('utf-8')
    hardcoded_ver_re = re.compile(r'R2-202\d-\d\d-\d\d')

    for pdf_name, builder_name, min_pages, needles in specs:
        pdf_p = os.path.join(REPO, pdf_name)
        bld_p = os.path.join(HERE, builder_name)

        check('%s: builder exists, imports r2_version directly, uses doc.render(), no hardcoded version'
              % builder_name,
              os.path.isfile(bld_p)
              and 'from r2_version import VERSION' in open(bld_p, encoding='utf-8').read()
              and '.render()' in open(bld_p, encoding='utf-8').read()
              and not hardcoded_ver_re.search(open(bld_p, encoding='utf-8').read()))

        exists = os.path.isfile(pdf_p) and open(pdf_p, 'rb').read(5) == b'%PDF-'
        pages, imgs, stream_bytes = _pdf_text_and_pages(pdf_p) if exists else (0, 0, b'')
        check('%s: valid PDF >= %d pages with >= 2 live PNG figures and current R2VER (%s)'
              % (pdf_name, min_pages, R2VER),
              exists and pages >= min_pages and imgs >= 2 and ver_bytes in stream_bytes,
              'pages=%d imgs=%d ver=%s' % (pages, imgs, ver_bytes in stream_bytes))

        missing = [n.decode('utf-8') for n in needles if n not in stream_bytes]
        check('%s: mathematical & blind-operation key terms present in PDF streams'
              % pdf_name,
              not missing,
              'missing=%s' % missing)

    # ---- R276 engine regression pins (M82 + G1 + G2/G3 + single-axis + OBJ=) ----
    with tempfile.TemporaryDirectory(prefix='r276_chk_') as d:
        # 1) M82 file with G1 walls, single-axis G1 X... move, and G2 arc
        m82_src = os.path.join(d, 'm82_arc_singleaxis.gcode')
        with open(m82_src, 'w', encoding='utf-8') as f:
            f.write('M82\nG90\nG92 E0\n')
            f.write('G0 X90.000 Y90.000 Z0.200 F6000\n')
            f.write('G1 X130.000 E1.50000 F1800\n')          # single-axis X move!
            f.write('G1 Y120.000 E2.60000 F1800\n')          # single-axis Y move!
            f.write('G2 X110.000 Y120.000 I-10.000 J0.000 E3.70000 F1500\n')
            f.write('G1 X90.000 Y90.000 Z1.000 E5.00000 F1800\n')
            f.write('G2 X110.000 Y90.000 I10.000 J0.000 E6.10000 F1500\n')

        e_ref, nj_ref = _sum_pos_de_m82(m82_src)

        tw_out, tw_info = pp.apply_twist(m82_src, deg=90.0, out_dir=d)
        e_tw, nj_tw = _sum_pos_de_m82(tw_out)
        check('apply_twist (M82 + G2 + single-axis G1): zero negative E jumps & exact ΣΔE invariance',
              nj_ref == 0 and nj_tw == 0 and abs(e_tw - e_ref) < 1e-4
              and tw_info['arcs_flattened'] == 2,
              'ref=%.5f tw=%.5f neg_jumps=%d' % (e_ref, e_tw, nj_tw))

        mr_out, mr_info = pp.apply_mirror(m82_src, axis='x', out_dir=d)
        e_mr, nj_mr = _sum_pos_de_m82(mr_out)
        check('apply_mirror (M82 + G2): zero negative E jumps & exact ΣΔE invariance',
              nj_mr == 0 and abs(e_mr - e_ref) < 1e-4
              and mr_info['arcs_flattened'] == 2,
              'ref=%.5f mr=%.5f neg_jumps=%d' % (e_ref, e_mr, nj_mr))

        # 2) Multi-object M82 plate with arcs + OBJ=RIGHT: header EXCLUDE_OBJECT_DEFINE
        #    for RIGHT must mirror while LEFT stays untouched, and ΣΔE stays exact
        plate = os.path.join(d, 'plate_m82_arc.gcode')
        with open(plate, 'w', encoding='utf-8') as f:
            f.write('EXCLUDE_OBJECT_DEFINE NAME=LEFT CENTER=50.000,100.000 '
                    'POLYGON=[[40.000,90.000],[60.000,90.000],[60.000,110.000]]\n')
            f.write('EXCLUDE_OBJECT_DEFINE NAME=RIGHT CENTER=155.000,100.000 '
                    'POLYGON=[[140.000,90.000],[180.000,90.000],[180.000,110.000]]\n')
            f.write('M82 ; absolute E with comment\nG90\nG92 E0\n')
            f.write('EXCLUDE_OBJECT_START NAME=LEFT\n')
            f.write('G0 X40.000 Y90.000 Z0.200 F6000\n')
            f.write('G1 X60.000 Y90.000 E1.00000 F1800\n')
            f.write('EXCLUDE_OBJECT_END NAME=LEFT\n')
            f.write('EXCLUDE_OBJECT_START NAME=RIGHT\n')
            f.write('G0 X140.000 Y90.000 Z0.200 F6000\n')
            f.write('G1 X160.000 Y90.000 E2.00000 F1800\n')
            f.write('G2 X180.000 Y90.000 I10.000 J0.000 E3.50000 F1500\n')
            f.write('EXCLUDE_OBJECT_END NAME=RIGHT\n')

        ep_ref, _ = _sum_pos_de_m82(plate)
        po_out, _ = pp.apply_mirror(plate, axis='x', obj='RIGHT', out_dir=d)
        ep_out, njp_out = _sum_pos_de_m82(po_out)
        ptxt = open(po_out, encoding='utf-8').read()
        # RIGHT bbox X is [140..180] -> cx = 160 -> mirrored header CENTER X = 2*160 - 155 = 165.000!
        check('apply_mirror OBJ=RIGHT (M82 + arc): exact ΣΔE & zero jumps after sibling object',
              njp_out == 0 and abs(ep_out - ep_ref) < 1e-4,
              'ref=%.5f out=%.5f neg_jumps=%d' % (ep_ref, ep_out, njp_out))
        check('apply_mirror OBJ=RIGHT: mirrors RIGHT EXCLUDE_OBJECT_DEFINE in header, keeps LEFT intact',
              'NAME=LEFT CENTER=50.000,100.000' in ptxt
              and 'NAME=RIGHT CENTER=165.000,100.000' in ptxt
              and 'POLYGON=[[180.000,90.000],[140.000,90.000]' in ptxt,
              ptxt.splitlines()[:4])


    # ---- R252/R285 engine invariant -------------------------------------
    # R252 pinned BYTE parity; R285 makes it honest: _next carries the
    # experimental strands (R281 verdicts, R288/R289 bricks, plus the
    # R283/R285/R287/R290 contract) that stable lacks. The invariant now:
    # identical 3-line header, EVERY main body line also in next (main is
    # a subsequence of next), and next's extra body mentions ONLY the
    # approved experimental R-tags.
    import difflib as _dl_parity
    _pm = open(os.path.join(HERE, 'r2_postproc.py'), encoding='utf-8').read().splitlines()
    _pn = open(os.path.join(HERE, 'r2_postproc_next.py'), encoding='utf-8').read().splitlines()
    _m_only = []
    _n_only = []
    for _tg, _a, _b, _c, _d in _dl_parity.SequenceMatcher(
            None, _pm[3:], _pn[3:], autojunk=False).get_opcodes():
        if _tg == 'equal':
            continue
        _m_only.extend(_pm[3:][_a:_b])
        _n_only.extend(_pn[3:][_c:_d])
    _n_tags = set(re.findall(r'\bR2[0-9][0-9]\b', '\n'.join(_n_only)))
    check('R252/R285 engine invariant: same header, main body subset of next, '
          'next extras only the approved experimental strands',
          _pm[:3] == _pn[:3]
          and not _m_only
          and _n_tags <= {'R212', 'R225', 'R226', 'R281', 'R283', 'R285',
                          'R288', 'R289', 'R290'},
          'main-only=%d next-only-tags=%s' % (len(_m_only), sorted(_n_tags)))

    # ---- Inventory & MASTER-TODO parity ----
    inv = open(os.path.join(REPO, 'docs', 'TOOLS_INVENTORY.md'), encoding='utf-8').read()
    check('TOOLS_INVENTORY.md lists all 5 D4 builders + r276_d4_modifier_pdfs_check.py',
          all(k in inv for k in (
              'make_scale_pdf.py', 'make_twist_pdf.py', 'make_mirror_pdf.py',
              'make_range_pdf.py', 'make_toolchain_pdf.py',
              'r276_d4_modifier_pdfs_check.py')))

    todo = open(os.path.join(REPO, 'docs-notes', 'MASTER-TODO.md'), encoding='utf-8').read()
    check('MASTER-TODO.md marks D4 as [x] completed with R276 summary',
          '- [x] **D4 — Pro Modifikator (Pre-Print-Geometrie-Tools) eine PDF**' in todo
          and 'SCALE.pdf' in todo and 'TOOLCHAIN.pdf' in todo)

    print('==== R276 RESULT: %d/%d passed (%d failed) ===='
          % (total - fails, total, fails))
    sys.exit(1 if fails else 0)


if __name__ == '__main__':
    main()
