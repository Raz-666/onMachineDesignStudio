#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""R278 check: D3/D6 Scientific Generator PDFs — Paket 2 (Konstruktion & Alltag):
  - BRICKS.pdf   (tools/make_bricks_pdf.py)
  - LABELS.pdf   (tools/make_labels_pdf.py)
  - FRAMES.pdf   (tools/make_frames_pdf.py)
  - PLOTTER.pdf  (tools/make_plotter_pdf.py)

Pure stdlib gate (no reportlab/pypdfium2/PIL required!). Runs live algorithmic
pins against r2_postproc (Bricks + BrickKit + Figures, Labels + R170 split +
R168 stamp, Frames FLAT + CASE + HEX, Plotter cal + text + SVG/PNG) and
verifies R252 r2_postproc_next.py parity.
"""
import base64
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


def _write_rgb_png_stdlib(path, rows_rgb):
    """Write an 8-bit RGB PNG using pure stdlib struct + zlib."""
    h = len(rows_rgb)
    w = len(rows_rgb[0])

    def _chunk(tag, payload):
        crc = zlib.crc32(tag + payload) & 0xffffffff
        return struct.pack('>I', len(payload)) + tag + payload + struct.pack('>I', crc)

    raw_scan = b''.join(
        b'\x00' + b''.join(bytes((r, g, b)) for (r, g, b) in row)
        for row in rows_rgb
    )
    ihdr = struct.pack('>IIBBBBB', w, h, 8, 2, 0, 0, 0)
    png = (b'\x89PNG\r\n\x1a\n'
           + _chunk(b'IHDR', ihdr)
           + _chunk(b'IDAT', zlib.compress(raw_scan, 9))
           + _chunk(b'IEND', b''))
    with open(path, 'wb') as f:
        f.write(png)
    return path


def main():
    print('==== R278 D3 CRAFT/DESIGN GENERATOR PDFS CHECK ====')

    specs = [
        ('BRICKS.pdf', 'make_bricks_pdf.py', 6,
         [b'make_bricks', b'make_brick_kit', b'make_figures', b'6,31 mm',
          b'BY_LAYER', b'BY_OBJECT', b'Schritt']),
        ('LABELS.pdf', 'make_labels_pdf.py', 5,
         [b'make_labels', b'_stroke_offsets', b'SMOOTH', b'SCRIPT',
          b'_StampFit168', b'Flip', b'Schritt']),
        ('FRAMES.pdf', 'make_frames_pdf.py', 5,
         [b'make_frame', b'10x15', b'CASE', b'LINES', b'WAVES', b'HEX',
          b'Schritt']),
        ('PLOTTER.pdf', 'make_plotter_pdf.py', 5,
         [b'plot_convert', b'text_convert', b'make_plot_cal', b'R2PLOT',
          b'FILAMENT', b'Otsu', b'Schritt']),
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
              'pages=%d imgs=%d ver=%s' % (pages, imgs, ver_bytes in stream_bytes))

        missing = [n.decode('utf-8') for n in needles if n not in stream_bytes]
        check('%s: mathematical, algorithmic & live-menu key terms present in PDF streams'
              % pdf_name,
              not missing,
              'missing=%s' % missing)

    # ---- Live algorithmic engine pins (pure stdlib!) ----
    with tempfile.TemporaryDirectory(prefix='r278_chk_') as d:
        # 1) Bricks + Figures + Scale=200 +1 wall rule
        out_br = os.path.join(d, 'br')
        os.makedirs(out_br, exist_ok=True)
        _, i_b200 = pp.make_bricks(
            [('B2x4', 1)], scale=200, colors=1, nozzle=0.6, out_dir=out_br)
        check('make_bricks(scale=200): applies R216 +1 wall-loop rule (3 wall loops)',
              any('wall loops 3' in n for n in i_b200.get('notes', [])),
              'notes=%s' % i_b200.get('notes'))

        p_fig, i_fig = pp.make_figures(
            count=1, scale=100.0, mode='PARTS', colors=1, nozzle=0.4, out_dir=out_br)
        fig_gc = open(p_fig, encoding='utf-8').read()
        check('make_figures(PARTS): emits all 5 snap-fit EXCLUDE_OBJECT parts (LEGS/TORSO/ARM1/ARM2/HEAD)',
              i_fig['parts'] == 5
              and all(('NAME=FIG_01_%s' % k) in fig_gc
                      for k in ('LEGS', 'TORSO', 'ARM1', 'ARM2', 'HEAD')))

        # 2) Labels: R170 multi-plate split + R168 stamp with on-plate handle=1
        out_lb = os.path.join(d, 'lb')
        os.makedirs(out_lb, exist_ok=True)
        p_st, i_st = pp.make_labels(
            ['TEST'], w=50.0, h=24.0, font='CAPS', text_layers=4,
            stamp=1, handle=1, color2=False, brim=False, nozzle=0.4, out_dir=out_lb)
        st_gc = open(p_st, encoding='utf-8').read()
        check('make_labels(stamp=1, handle=1): emits mirrored stamp + on-plate NAME=GRIFF',
              bool(i_st.get('stamp')) and bool(i_st.get('handle_plate'))
              and 'NAME=GRIFF' in st_gc)

        _, i_ml = pp.make_labels(
            ['BOX %d' % k for k in range(1, 10)],
            w=95.0, h=48.0, font='COND', mode='fixed', color2=True,
            nozzle=0.4, out_dir=out_lb)
        check('make_labels(8 large labels): R170 splits cleanly into >= 2 plates (_T1, _T2..)',
              i_ml.get('parts', 1) >= 2 and len(i_ml.get('files', [])) >= 2,
              'parts=%s files=%s' % (i_ml.get('parts'), i_ml.get('files')))

        # 3) Frames: CASE mode (depth >= 15) + backplate without brim + HEX front
        out_fr = os.path.join(d, 'fr')
        os.makedirs(out_fr, exist_ok=True)
        _, i_case = pp.make_frame(
            preset='4x5', depth=18.0, frame_w=10.0, closure='SIDE',
            cable=True, front='HEX', nozzle=0.6, out_dir=out_fr)
        check('make_frame(depth=18, SIDE, cable=True, front=HEX): builds CASE mode with cable duct',
              i_case['mode'] == 'CASE' and i_case['cable'] is True and i_case['front'] == 'HEX')

        # 4) Plotter: make_plot_cal + text_convert + plot_convert (RGB PNG)
        out_pl = os.path.join(d, 'pl')
        os.makedirs(out_pl, exist_ok=True)
        p_cal, i_cal = pp.make_plot_cal(out_dir=out_pl)
        cal_gc = open(p_cal, encoding='utf-8').read()
        check('make_plot_cal(): emits _PLOT_START/_PLOT_END, NAME=R2PLOT, 63 dots & 27 strokes',
              i_cal['dots'] == 63 and i_cal['strokes'] == 27
              and '_PLOT_START' in cal_gc and '_PLOT_END' in cal_gc
              and 'NAME=R2PLOT' in cal_gc)

        txt_p = os.path.join(out_pl, 'hello.txt')
        open(txt_p, 'w', encoding='utf-8').write('R2 Plotter\nZeile Zwei ÄÖÜ\n')
        out_txt_gc, n_tl, cap_mm = pp.text_convert(
            txt_p, out=os.path.join(out_pl, 'hello.gcode'))
        check('text_convert(): renders 2 lines at >= 6.0 mm cap height into R2-PLOT g-code',
              n_tl == 2 and cap_mm >= 6.0 and os.path.isfile(out_txt_gc))

        rgb_rows = [[(20, 20, 20) if (12 <= x <= 36 and 12 <= y <= 36) else (250, 250, 250)
                     for x in range(48)] for y in range(48)]
        png_p = _write_rgb_png_stdlib(os.path.join(out_pl, 'sq.png'), rgb_rows)
        n_pens, n_lines = pp.plot_convert(png_p, out=os.path.join(out_pl, 'sq.gcode'))
        check('plot_convert(PNG): Otsu threshold converts square into >= 1 pen band',
              n_pens >= 1 and n_lines > 40)


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

    print('---- %d checks, %d failed ----' % (total, fails))
    sys.exit(1 if fails else 0)


if __name__ == '__main__':
    main()
