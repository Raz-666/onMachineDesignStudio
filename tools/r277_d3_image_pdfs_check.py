#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""R277 check: D3/D6 Scientific Generator PDFs — Paket 1 (Bild-/Kunst-Familie):
  - STENCIL.pdf    (tools/make_stencil_pdf.py)
  - LITHOPHANE.pdf (tools/make_lithophane_pdf.py)
  - COLORPIC.pdf   (tools/make_colorpic_pdf.py)
  - STRINGART.pdf  (tools/make_stringart_pdf.py)

Pure stdlib gate (no reportlab/pypdfium2 required). Runs live algorithmic pins
against r2_postproc (SPIRAL StringArt unconditionally; image-backed Stencil,
Lithophane, and ColorPic pins whenever PIL is importable) and verifies R252
r2_postproc_next.py parity.
"""
import base64
import math
import os
import re
import struct
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


def _write_gray_png_stdlib(path, rows_u8):
    """Write an 8-bit grayscale PNG using pure stdlib struct + zlib."""
    h = len(rows_u8)
    w = len(rows_u8[0])

    def _chunk(tag, payload):
        crc = zlib.crc32(tag + payload) & 0xffffffff
        return struct.pack('>I', len(payload)) + tag + payload + struct.pack('>I', crc)

    raw_scan = b''.join(b'\x00' + bytes(r) for r in rows_u8)
    ihdr = struct.pack('>IIBBBBB', w, h, 8, 0, 0, 0, 0)
    png = (b'\x89PNG\r\n\x1a\n'
           + _chunk(b'IHDR', ihdr)
           + _chunk(b'IDAT', zlib.compress(raw_scan, 9))
           + _chunk(b'IEND', b''))
    with open(path, 'wb') as f:
        f.write(png)
    return path


def _has_pil():
    try:
        import PIL.Image  # noqa: F401
        return True
    except Exception:
        return False


def main():
    print('==== R277 D3 IMAGE/ART GENERATOR PDFS CHECK ====')

    specs = [
        ('STENCIL.pdf', 'make_stencil_pdf.py', 5,
         [b'make_stencil', b'_stencil_bridges267', b'Schablone1', b'SchabloneNeg',
          b'0.0000 mm', b'Schritt']),
        ('LITHOPHANE.pdf', 'make_lithophane_pdf.py', 6,
         [b'make_lithophane', b'_make_litho_flat', b'Beer-Lambert', b'LITHO_STAND',
          b'PURGE_TOWER', b'Stempel', b'Schritt']),
        ('COLORPIC.pdf', 'make_colorpic_pdf.py', 5,
         [b'make_colorpic', b'COLORPIC_PALETTE', b'_COLORPIC_SWAP', b'M600',
          b'PURGE_TOWER', b'Ironing', b'Schritt']),
        ('STRINGART.pdf', 'make_stringart_pdf.py', 5,
         [b'make_string_art', b'_string_art_plan', b'SPIRAL', b'PHOTO',
          b'0,30 mm', b'0,068', b'Schritt']),
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

        # Guard against literal \n inside FORMULA(...) strings (D6/ReportLab XML rule)
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
              'pages=%d imgs=%d ver=%s' % (pages, imgs, ver_bytes in stream_bytes))

        missing = [n.decode('utf-8') for n in needles if n not in stream_bytes]
        check('%s: mathematical, algorithmic & live-menu key terms present in PDF streams'
              % pdf_name,
              not missing,
              'missing=%s' % missing)

    # ---- Live algorithmic engine pins ----
    with tempfile.TemporaryDirectory(prefix='r277_chk_') as d:
        # 1) StringArt SPIRAL (pure math, no PIL needed)
        out_sa = os.path.join(d, 'sa')
        os.makedirs(out_sa, exist_ok=True)
        p_sa, info_sa = pp.make_string_art(
            None, pattern='SPIRAL', shape='ROUND', diameter=120.0,
            anchors=60, lines=90, arc=2.0, nozzle=0.4, out_dir=out_sa,
        )
        sa_gc = open(p_sa, encoding='utf-8').read()
        z_peaks = [float(m.group(1))
                   for m in re.finditer(r'^G1\s+X[\d.]+\s+Y[\d.]+\s+Z([\d.]+)\s+E', sa_gc, re.M)]
        check('make_string_art(SPIRAL, arc=2.0): generates 90 bowed 3D strands reaching > 4.5 mm Z',
              info_sa['lines'] == 90 and z_peaks and max(z_peaks) > 4.5,
              'lines=%s max_z=%s' % (info_sa.get('lines'), max(z_peaks) if z_peaks else None))

        if _has_pil():
            # 2) Stencil binary logo -> <2% R267 auto-reduction (steps=4 -> 2 plates) + island bridge
            w_im = 96
            logo_rows = []
            for y in range(w_im):
                row = []
                for x in range(w_im):
                    r = math.hypot(x - 48, y - 48)
                    # Black outer ring + floating white island ring + black bullseye
                    val = 15 if (26 <= r <= 36 or r <= 12) else 245
                    row.append(val)
                logo_rows.append(row)
            logo_png = _write_gray_png_stdlib(os.path.join(d, 'Bullseye.png'), logo_rows)
            out_st = os.path.join(d, 'st')
            os.makedirs(out_st, exist_ok=True)
            _, info_st = pp.make_stencil(
                logo_png, steps=4, size_mm=80.0, layer_h=0.2, thick=0.8,
                negative=True, nozzle=0.4, out_dir=out_st,
            )
            tot_bridges = sum(info_st['bridges'])
            check('make_stencil(steps=4 on binary bullseye + negative=True): R267 reduces 4->2 plates + Neg (3 files) with island bridges',
                  info_st['steps'] == 2 and len(info_st['files']) == 3 and tot_bridges >= 2,
                  'steps=%s n_files=%d bridges=%s' % (info_st.get('steps'), len(info_st['files']), info_st.get('bridges')))

            # 3) Lithophane STANDING (side stands) + FLAT stamp=1, handle=2
            out_li = os.path.join(d, 'li')
            os.makedirs(out_li, exist_ok=True)
            p_li_st, info_li_st = pp.make_lithophane(
                logo_png, height_mm=60.0, layer_h=0.16,
                orient='STANDING', frame=True, stands=1, nozzle=0.4, out_dir=out_li,
            )
            li_gc = open(p_li_st, encoding='utf-8').read()
            check('make_lithophane(STANDING, stands=1): emits LITHO_STAND_L and LITHO_STAND_R',
                  'NAME=LITHO_STAND_L' in li_gc and 'NAME=LITHO_STAND_R' in li_gc)

            p_li_stamp, info_li_stamp = pp.make_lithophane(
                logo_png, height_mm=45.0, layer_h=0.16, orient='FLAT',
                levels=3, col_layers=3, stamp=1, handle=2,
                nozzle=0.4, out_dir=out_li,
            )
            check('make_lithophane(FLAT, stamp=1, handle=2): emits Vnn_Stempel + separate Vnn_Griff handle_file',
                  '_Stempel_' in info_li_stamp['file']
                  and '_Griff_' in (info_li_stamp.get('handle_file') or '')
                  and os.path.isfile(os.path.join(out_li, info_li_stamp['handle_file'])),
                  'info=%s' % info_li_stamp)

            # 4) ColorPic 3-band swap=True + ironing=True
            grad_rows = [[int(255 * x / 95.0) for x in range(96)] for _y in range(64)]
            grad_png = _write_gray_png_stdlib(os.path.join(d, 'Ramp.png'), grad_rows)
            out_cp = os.path.join(d, 'cp')
            os.makedirs(out_cp, exist_ok=True)
            p_cp, info_cp = pp.make_colorpic(
                grad_png, width_mm=60.0, bands=3, band_h=0.6,
                layer_h=0.2, colors='WHT,CYA,BLK', swap=True,
                ironing=True, nozzle=0.4, out_dir=out_cp,
            )
            cp_gc = open(p_cp, encoding='utf-8').read()
            check('make_colorpic(bands=3, swap=True, ironing=True): emits 2x M600 + _COLORPIC_SWAP + PURGE_TOWER + IRONING',
                  len(re.findall(r'^M600\b', cp_gc, re.M)) == 2
                  and '_COLORPIC_SWAP' in cp_gc
                  and 'NAME=PURGE_TOWER' in cp_gc
                  and 'APPLY_TYPE TYPE=IRONING' in cp_gc)

    # ---- R252 parity invariant: r2_postproc.py vs r2_postproc_next.py ----
    p1 = open(os.path.join(HERE, 'r2_postproc.py'), encoding='utf-8').read().splitlines()
    p2 = open(os.path.join(HERE, 'r2_postproc_next.py'), encoding='utf-8').read().splitlines()
    diffs = [i for i in range(max(len(p1), len(p2)))
             if (p1[i] if i < len(p1) else None) != (p2[i] if i < len(p2) else None)]
    check('r2_postproc_next.py matches r2_postproc.py except header lines 2-3 (R252 invariant)',
          diffs == [1, 2] and len(p1) == len(p2),
          'diff_lines=%s len=%d/%d' % (diffs[:10], len(p1), len(p2)))

    print('---- %d checks, %d failed ----' % (total, fails))
    sys.exit(1 if fails else 0)


if __name__ == '__main__':
    main()
