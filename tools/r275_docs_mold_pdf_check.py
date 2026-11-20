#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""R275 check: D3/D6 scientific MOLDS.pdf + post-J2 documentation parity
(MANUAL.md §5.22 + §25 index, MANUAL.pdf §5.17-5.22, GENERATORS_TOOLS.pdf
13 generators + real LCD paths, TOOLS_INVENTORY.md). Pure stdlib so it
runs in every test container without reportlab installed.
"""
import ast
import base64
import os
import re
import subprocess
import sys
import zlib

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
sys.path.insert(0, HERE)

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
    joined = b'\n'.join(chunks)
    return pages, imgs, joined


def _eval_gen_list(py_path):
    tree = ast.parse(open(py_path, encoding='utf-8').read())
    for node in tree.body:
        if isinstance(node, ast.Assign):
            for t in node.targets:
                if isinstance(t, ast.Name) and t.id == 'GEN':
                    return ast.literal_eval(node.value)
    return []


def main():
    print('== R275 docs + MOLDS.pdf check ==')

    # ---- A: MANUAL.md parity ---------------------------------------------
    man = open(os.path.join(REPO, 'MANUAL.md'), encoding='utf-8').read()
    check('A1 MANUAL.md has §5.22 Casting molds + real FormUnten/FormOben names',
          '### 5.22 Casting molds' in man
          and 'FormUnten_' in man and 'FormOben_' in man
          and 'MOLD_CREATE' in man and 'MOLD_BLANK_CREATE' in man)

    idx_pos = man.find('## 25.')
    idx_txt = man[idx_pos:] if idx_pos >= 0 else ''
    missing_idx = [m for m in ('MOLD_INFO', 'MOLD_CREATE',
                               'MOLD_BLANK_INFO', 'MOLD_BLANK_CREATE')
                   if m not in idx_txt]
    check('A2 MANUAL.md §25 lists all 4 MOLD public macros',
          not missing_idx, missing_idx)

    r265 = subprocess.run([sys.executable, os.path.join(HERE, 'r265_manual_check.py')],
                          capture_output=True, text=True)
    check('A3 r265_manual_check: 0 unlisted public macros & counts match',
          r265.returncode == 0
          and 'im Code, nicht gelistet: 0 öffentliche' in r265.stdout
          and 'Handbuch sagt' not in r265.stdout,
          r265.stdout[-300:])

    r165 = subprocess.run([sys.executable, os.path.join(HERE, 'r165_doc_check.py')],
                          capture_output=True, text=True)
    check('A4 r165_doc_check clean',
          r165.returncode == 0 and 'clean - documentation matches reality' in r165.stdout,
          r165.stdout[-300:])

    # ---- B: GENERATORS_TOOLS.pdf -----------------------------------------
    mg_path = os.path.join(HERE, 'make_generators_pdf.py')
    gen_list = _eval_gen_list(mg_path)
    gen_keys = [g[0] for g in gen_list]
    bad_paths = [g[2] for g in gen_list if not g[2].startswith('Tools &gt; ')]
    check('B1 make_generators_pdf has 13 generators incl. __mold under Tools >',
          len(gen_list) == 13 and '__mold' in gen_keys and not bad_paths,
          (len(gen_list), bad_paths))

    gt_pdf = os.path.join(REPO, 'GENERATORS_TOOLS.pdf')
    gt_pages, _, gt_blob = _pdf_text_and_pages(gt_pdf)
    check('B2 GENERATORS_TOOLS.pdf includes live LCD rows (Wall/Pour D/Surface/Plane)',
          all(tok in gt_blob for tok in (
              b'Casting molds', b'Wall: mm', b'Pour D: mm', b'Surface', b'Plane')))
    check('B3 GENERATORS_TOOLS.pdf built (>=14 pages) with current R2VER stamp',
          gt_pages >= 14 and R2VER.encode('ascii') in gt_blob,
          (gt_pages, R2VER))

    # ---- C: MANUAL.pdf ---------------------------------------------------
    mp_src = open(os.path.join(HERE, 'make_manual_pdf.py'), encoding='utf-8').read()
    check('C1 make_manual_pdf.py carries §5.17-5.22 + MOLD/TOOLCHAIN/STENCIL index',
          all(tok in mp_src for tok in (
              '5.17', '5.18', '5.19', '5.20', '5.21', '5.22',
              'MOLD_CREATE', 'MOLD_BLANK_CREATE', 'TOOLCHAIN_APPLY', 'STENCIL_CREATE')))

    man_pdf = os.path.join(REPO, 'MANUAL.pdf')
    m_pages, _, m_blob = _pdf_text_and_pages(man_pdf)
    check('C2 MANUAL.pdf built (>=110 pages) with current R2VER stamp',
          m_pages >= 110 and R2VER.encode('ascii') in m_blob
          and b'MOLD_BLANK_CREATE' in m_blob,
          (m_pages, R2VER))

    # ---- D: MOLDS.pdf (D3 + D6 truth contract) ---------------------------
    mm_src = open(os.path.join(HERE, 'make_molds_pdf.py'), encoding='utf-8').read()
    check('D1 make_molds_pdf imports r2_version (no hardcoded R2-2026 stamp)',
          'from r2_version import VERSION' in mm_src
          and not re.search(r'R2-202\d-\d\d-\d\d', mm_src))

    check('D2 make_molds_pdf runs real make_mold + make_mold_blank & reads lcd_menues.cfg',
          'pp.make_mold(' in mm_src and 'pp.make_mold_blank(' in mm_src
          and 'lcd_menues.cfg' in mm_src)

    molds_pdf = os.path.join(REPO, 'MOLDS.pdf')
    md_pages, md_imgs, md_blob = _pdf_text_and_pages(molds_pdf)
    check('D3 MOLDS.pdf built (>=10 pages, >=4 computed figures, R2VER stamped)',
          md_pages >= 10 and md_imgs >= 4 and R2VER.encode('ascii') in md_blob,
          (md_pages, md_imgs))

    check('D4 MOLDS.pdf covers all 3 blank shapes, 3 surfaces, 3 split modes & sectors',
          all(tok.encode('ascii') in md_blob for tok in (
              'MEDALLION', 'PLAQUE', 'BAR',
              'STANDARD', 'FINE', 'FUZZY',
              'AUTO', 'MID', 'OFF', 'MOLD_CREATE', 'MOLD_BLANK_CREATE')))

    # ---- E: Inventory + MASTER-TODO parity -------------------------------
    inv = open(os.path.join(REPO, 'docs', 'TOOLS_INVENTORY.md'), encoding='utf-8').read()
    check('E1 TOOLS_INVENTORY.md lists make_molds_pdf.py, MOLDS.pdf & r275',
          'make_molds_pdf.py' in inv and 'MOLDS.pdf' in inv
          and 'r275_docs_mold_pdf_check.py' in inv)

    todo = open(os.path.join(REPO, 'docs-notes', 'MASTER-TODO.md'), encoding='utf-8').read()
    check('E2 MASTER-TODO.md records R275 under D3/D6',
          'R275' in todo and 'MOLDS.pdf' in todo)

    print('%d/%d checks passed' % (total - fails, total))
    sys.exit(1 if fails else 0)


if __name__ == '__main__':
    main()
