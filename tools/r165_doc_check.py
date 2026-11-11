#!/usr/bin/env python3
"""R165: documentation-reality cross-check (audit points 8 + 10).

The MANUAL may only describe what ACTUALLY works (.121 user rule). This
tool verifies the documented surface against the source of truth:

  1. every `UPPER_CASE` token in MANUAL.md (chapters, not the historical
     Appendix D) is a real macro (ours, or a template in
     printer.cfg.example) or a known Klipper command
  2. every documented `MACRO PARAM=VALUE ...` call example: each PARAM
     must be read by that macro (params.PARAM in its body)
  3. every documented LCD path "A > B" (chapters only) must exist in the
     menu tree - with honest shorthand tolerance: parenthetical label
     suffixes, dynamic "Label: {value}" rows, ON/OFF state suffixes,
     arm/confirm suffixes, '/' alternatives and prose words glued to the
     path ends. A path only fails when NO reading of it exists.
  4. menu label hygiene: near-duplicate labels inside the SAME parent,
     unicode ellipsis vs '...', double spaces, stray edge spaces
  5. the console samples of ch. 18 (fenced lines) must match a REAL
     message template (macros + r2_postproc messages)

Exit 0 = documentation and reality agree.
"""
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
MAC_DIR = os.path.join(ROOT, 'macros')
MENU = os.path.join(ROOT, 'menus', 'lcd_menues.cfg')
MANUAL = os.path.join(ROOT, 'MANUAL.md')
EXAMPLE = os.path.join(ROOT, 'printer.cfg.example')

KLIPPER = set('''
ACCEPT ABORT ACTIVATE_EXTRUDER BED_MESH_CALIBRATE BED_MESH_CLEAR
BED_MESH_PROFILE BED_MESH_REMOVE CANCEL_PRINT DUMP_TMC EXCLUDE_OBJECT_DEFINE
EXCLUDE_OBJECT_START EXCLUDE_OBJECT_END FIRMWARE_RESTART FORCE_MOVE GET_POSITION
HELP INIT_TMC M115 M117 M118 M220 M221 M400 M600 M876 PAUSE PROBE
PROBE_ACCURACY PROBE_CALIBRATE QUERY_FILAMENT_SENSOR QUERY_PROBE QUERY_TMC
RESTART RESPOND RESTORE_GCODE_STATE SAVE_CONFIG SAVE_GCODE_STATE
SAVE_VARIABLE SDCARD_PRINT_FILE SDCARD_RESET_FILE SET_DISPLAY_GROUP
SET_FILAMENT_SENSOR SET_GCODE_OFFSET SET_GCODE_VARIABLE SET_HEATER_TEMPERATURE
SET_KINEMATIC_POSITION SET_LED SET_LED_TEMPLATE SET_PIN SET_PRESSURE_ADVANCE
SET_PRINT_STATS_INFO SET_TMC_CURRENT SET_VELOCITY_LIMIT STATUS TESTZ
TEMPERATURE_WAIT TURN_OFF_HEATERS UPDATE_DELAYED_GCODE Z_ENDSTOP_CALIBRATE
Z_OFFSET_APPLY_ENDSTOP Z_OFFSET_APPLY_PROBE
'''.split())

# documented tokens that are VALUES / keys / name suffixes, not commands
DOC_ONLY = set('''BRIM BRIDGE FILL SKIN SKIRT SUPPORT RETAG MAXRATE TYPE_MAP
CUSTOMGROUPS CUSTOMRES CUSTOMBLOCKS
_TX'''.split())   # CUSTOM*: _FILE_INFO keys (R213), not macros

findings = []


def load_macro_sections():
    """{macro_name: body} over macros/*.cfg, menus/*.cfg and the
    (commented) templates in printer.cfg.example"""
    secs = {}
    paths = []
    for d in (MAC_DIR, os.path.join(ROOT, 'menus')):
        if os.path.isdir(d):
            paths += [os.path.join(d, f) for f in sorted(os.listdir(d))
                      if f.endswith('.cfg')]
    if os.path.isfile(EXAMPLE):
        paths.append(EXAMPLE)
    for path in paths:
        cur, body = None, []
        for line in open(path, encoding='utf-8'):
            # '#' comment-tolerant: printer.cfg.example ships its macro
            # templates commented out
            m = re.match(r'#?\[(gcode_macro|delayed_gcode) ([^\]]+)\]', line)
            if m:
                if cur:
                    secs[cur] = '\n'.join(body)
                cur, body = m.group(2).strip(), []
                continue
            if cur is not None:
                body.append(line)
        if cur:
            secs[cur] = '\n'.join(body)
    return secs


def load_user_facing_strings():
    out = []
    pat_resp = re.compile(r'(?:RESPOND|NOTIFY)\s+(?:MSG|TEXT)\s*=\s*"([^"]*)"')
    for fn in sorted(os.listdir(MAC_DIR)):
        if fn.endswith('.cfg'):
            txt = open(os.path.join(MAC_DIR, fn), encoding='utf-8').read()
            out += pat_resp.findall(txt)
            out += re.findall(r'\bM117\s+([^;{\n]+)', txt)
            out += re.findall(r"'([A-Za-z][^']{5,})'", txt)
    tool = open(os.path.join(HERE, 'r2_postproc.py'), encoding='utf-8').read()
    out += re.findall(r"notes\.append\(\s*'([^']+)", tool)
    out += re.findall(r'RESPOND MSG=\\"([^\\"]*)', tool)
    out += re.findall(r"RESPOND MSG='([^']+)'", tool)
    return [s for s in out if s.strip()]


def load_menu_tree():
    nodes, children = {}, {}
    for line in open(MENU, encoding='utf-8'):
        m = re.match(r'\[menu (.+)\]', line.strip())
        if not m:
            continue
        pid = m.group(1).strip()
        parent = ' '.join(pid.split()[:-1]) if ' ' in pid else None
        nodes[pid] = {'name': None, 'parent': parent}
        children.setdefault(parent, []).append(pid)
    cur = None
    for line in open(MENU, encoding='utf-8'):
        t = line.strip()
        m = re.match(r'\[menu (.+)\]', t)
        if m:
            cur = m.group(1).strip()
            continue
        if cur and nodes.get(cur, {}).get('name') is None:
            m = re.match(r'name:\s*(.+)', t)
            if m:
                nodes[cur]['name'] = m.group(1).strip()
    return nodes, children


def menu_paths(nodes, children):
    paths = set()

    def walk(pid, acc):
        nm = nodes[pid]['name']
        if nm:
            acc = acc + [nm]          # dynamic labels too - the matcher
            paths.add(tuple(s.strip() for s in acc))   # knows the shorthand
        for c in children.get(pid, []):
            walk(c, acc)

    for c in children.get(None, []):
        walk(c, [])
    return paths


def norm(s):
    return re.sub(r'\s+', ' ', s.strip().lower())


def seg_matches_label(seg, label):
    """one documented path segment vs one menu label (honest shorthand)"""
    l = label.strip()
    l = re.sub(r'\s*\([^)]*\)\s*$', '', l)          # 'File (G-code)' -> 'File'
    if '{' in l:                                     # dynamic row
        pre = l.split('{')[0].rstrip(':').strip()
        if seg == norm(pre):
            return True
        return seg in norm(l)                        # toggle pairs etc.
    l2 = re.sub(r'\s+(on|off)$', '', l, flags=re.I)  # 'Overwrites OFF'
    l2 = re.sub(r'\s*\?\s*(arm)?$', '', l2)          # 'Save config? arm'
    l2 = re.sub(r'\s*(\.\.\.|\.)$', '', l2)         # 'Load mesh...'
    l2 = re.sub(r'^>\s*', '', l2)                    # '> Create'
    return seg == norm(l) or seg == norm(l2)


def path_exists(segs, mpaths):
    """segs (normed) exists as a consecutive chain in the menu tree"""
    for p in mpaths:
        if len(p) < len(segs):
            continue
        for i in range(len(p) - len(segs) + 1):
            window = p[i:i + len(segs)]
            ok = True
            for seg, label in zip(segs, window):
                if not seg_matches_label(seg, label):
                    ok = False
                    break
            if ok:
                return True
    return False


def _segclean(s):
    s = s.strip().rstrip('.,;:!)').strip()
    return norm(s)


def path_candidates(raw):
    """shorthand-tolerant readings of one captured 'A > B > C' string"""
    base = [norm(s) for s in raw.split(' > ')]
    base = [s for s in base if s]
    cands = [base]
    # cut segments at ' (' (prose parenthesis glued to the path)
    cut = [norm(s.split(' (')[0]) if ' (' in s else s for s in base]
    if cut != base:
        cands.append(cut)
    # strip trailing punctuation off every segment
    cl = [_segclean(s) for s in base]
    if cl != base:
        cands.append([s for s in cl if s])
    # drop trailing prose words off the LAST segment (down to 1 word)
    words = base[-1].split()
    for k in range(1, len(words)):
        t = _segclean(' '.join(words[:-k]))
        if t:
            cands.append(base[:-1] + [t])
    # slash alternatives: 'Hot / Bed / Fan' style (original kept too)
    out = []
    for c in cands:
        out.append(c)
        if any('/' in s for s in c):
            variants = [[]]
            for s in c:
                if '/' in s:
                    variants = [v + [norm(p)] for v in variants
                                for p in s.split('/')]
                else:
                    variants = [v + [s] for v in variants]
            out += [v for v in variants if all(v)]
    # subchains (prose glued before the real path start)
    subs = []
    for c in out:
        for i in range(len(c)):
            subs.append(c[i:])
    return out + subs


def manual_lines():
    """(ln, line, in_appendix) - Appendix D is historical, skipped"""
    lines = open(MANUAL, encoding='utf-8').read().splitlines()
    res, appendix = [], False
    for ln, l in enumerate(lines, 1):
        if l.startswith('## Appendix D'):
            appendix = True
        res.append((ln, l, appendix))
    return res


def main():
    macros = load_macro_sections()
    strings = load_user_facing_strings()
    nodes, children = load_menu_tree()
    mpaths = menu_paths(nodes, children)
    mlines = manual_lines()

    # ---------------- 1) documented macro tokens --------------------------
    tok_re = re.compile(r'`([A-Z_][A-Z0-9_]{1,})`')
    seen = {}
    for ln, line, appendix in mlines:
        if appendix:
            continue
        for tok in tok_re.findall(line):
            seen.setdefault(tok, ln)
    for tok, ln in sorted(seen.items()):
        if re.match(r'^[GM]\d+$', tok) or tok in KLIPPER or tok in DOC_ONLY:
            continue
        if tok not in macros:
            findings.append(('macro token', ln,
                             '`%s` is not a macro in macros/ and not a '
                             'known Klipper command' % tok))

    # ---------------- 2) documented call examples -------------------------
    call_re = re.compile(r'`([A-Z_][A-Z0-9_]{1,})((?:\s+[A-Z_][A-Z0-9_]*='
                         r'[^`\s]+)+)`')
    for ln, line, appendix in mlines:
        if appendix:
            continue
        for m in call_re.finditer(line):
            name, argstr = m.group(1), m.group(2)
            if name not in macros or name in KLIPPER:
                continue
            keys = re.findall(r'([A-Z_][A-Z0-9_]*)=', argstr)
            body = macros[name]
            for k in keys:
                if ('params.' + k) not in body:
                    findings.append(('call example', ln,
                                     '`%s %s=...`: macro %s never reads '
                                     'params.%s' % (name, k, name, k)))

    # ---------------- 3) documented LCD paths ------------------------------
    path_re = re.compile(r'(?<![A-Za-z-])\b([A-Z][A-Za-z0-9 &(+)/\'!.-]{2,30})'
                         r'(?: > ([A-Z][A-Za-z0-9 &(+)/\'!.-]{1,32}))+')
    n_paths = 0
    for ln, line, appendix in mlines:
        if appendix or ('|---' in line):
            continue
        for m in path_re.finditer(line):
            segs = [norm(s) for s in m.group(0).split(' > ')]
            if not any(s.startswith('start') for s in segs):
                n_paths += 1
                if not any(path_exists(c, mpaths)
                           for c in path_candidates(m.group(0))
                           if len(c) >= 1):
                    findings.append(('lcd path', ln,
                                     'path "%s" not found in the menu tree'
                                     % m.group(0)))

    # ---------------- 4) menu label hygiene --------------------------------
    by_parent = {}
    for pid, nd in nodes.items():
        nm = nd['name']
        if nm and '{' not in nm and len(nm.strip()) > 2:
            by_parent.setdefault(nd['parent'], set()).add(
                (norm(nm), pid, nm))
    for parent, items in by_parent.items():
        seen_norm = {}
        for nrm, pid, nm in sorted(items):
            base = re.sub(r'\s*\?\s*(arm)?$', '', nrm)
            base = re.sub(r'\s+(on|off)$', '', base)
            if base in seen_norm:
                findings.append(('menu label', 0,
                                 'parent %s: near-duplicate %r and %r'
                                 % (parent, seen_norm[base], nm)))
            seen_norm.setdefault(base, nm)
    for pid, nd in nodes.items():
        nm = nd['name']
        if not nm or '{' in nm:
            continue
        why = []
        if '…' in nm:
            why.append('unicode ellipsis (use ...)')
        if '  ' in nm:
            why.append('double space')
        if nm != nm.strip():
            why.append('stray edge spaces')
        if why:
            findings.append(('menu label', 0, '%r (%s): %s'
                             % (nm, pid, ', '.join(why))))

    # ---------------- 5) ch.18 console samples (fenced only) ---------------
    in18 = False
    fence = False
    samples = []
    for ln, line, appendix in mlines:
        if line.startswith('## 18'):
            in18 = True
        elif in18 and line.startswith('## 19'):
            break
        elif in18:
            if line.startswith('```'):
                fence = not fence
                continue
            if fence and line.strip():
                samples.append((ln, line.strip()))
    klipper_own = ('File opened', 'File selected', 'Done printing', '// ',
                   'ok ', 'Recv:', 'Send:', 'Stats ')
    for ln, sample in samples:
        if any(sample.startswith(p) for p in klipper_own):
            continue
        for part in re.split(r'\s+/\s+|\s+·\s+', sample):
            words = [w for w in re.findall(r'[A-Za-z]{4,}', part)
                     if w.lower() not in ('your', 'file', 'with', 'from',
                                          'whichever')]
            if len(words) < 3:
                continue
            words.sort(key=len, reverse=True)
            key = [w.lower() for w in words[:3]]
            if not any(all(k in s.lower() for k in key) for s in strings):
                findings.append(('console sample', ln,
                                 'ch.18 sample "%s" has no matching message '
                                 'template in the sources' % part[:70]))

    # ---- R246d: the two staleness classes that hid for four releases ----
    import glob
    # (1) no document may carry a HAND-TYPED release stamp - every builder
    #     must import r2_version. Field history: all five PDFs still said
    #     .136ai after four releases because the stamp was hard-coded and
    #     nobody diffs a PDF.
    for bp in sorted(glob.glob(os.path.join(ROOT, 'tools', 'make_*_pdf.py'))):
        bs = open(bp, encoding='utf-8').read()
        if 'from r2_version import' not in bs:
            findings.append(('version rule', None,
                             '%s does not import r2_version - its stamp can '
                             'go stale silently' % os.path.basename(bp)))
        for hard in re.findall(r'R2-20\d\d-\d\d-\d\d\.\d+[a-z]*', bs):
            findings.append(('version rule', None,
                             '%s carries a HAND-TYPED stamp %r - read it from '
                             'r2_version instead' % (os.path.basename(bp), hard)))
    # (2) the MANUAL's texture catalogue must match the code's pattern list.
    #     Field history: it said "21 patterns on 3 pages" while the code had
    #     27 on 4 pages, and five patterns had no name in the docs at all.
    try:
        gen = open(os.path.join(ROOT, 'macros', '17_generator.cfg'),
                   encoding='utf-8').read()
        m_codes = re.search(r'variable_tx_codes:\s*\[([^\]]+)\]', gen)
        m_names = re.search(r'variable_tx_names:\s*\[([^\]]+)\]', gen)
        codes = re.findall(r"'([^']+)'", m_codes.group(1)) if m_codes else []
        names = re.findall(r"'([^']+)'", m_names.group(1)) if m_names else []
        manual = open(os.path.join(ROOT, 'MANUAL.md'),
                      encoding='utf-8').read()
        if codes:
            stated = re.search(r'\*\*(\d+) patterns on (\d+) pages', manual)
            if not stated:
                findings.append(('texture catalogue', None,
                                 'MANUAL.md no longer states the pattern count '
                                 'in the "N patterns on M pages" form'))
            else:
                if int(stated.group(1)) != len(codes):
                    findings.append(('texture catalogue', None,
                                     'MANUAL.md says %s patterns, the code has '
                                     '%d' % (stated.group(1), len(codes))))
                want_pages = (len(codes) + 7) // 8
                if int(stated.group(2)) != want_pages:
                    findings.append(('texture catalogue', None,
                                     'MANUAL.md says %s pattern pages, 8 slots '
                                     'per page means %d'
                                     % (stated.group(2), want_pages)))
            for nm in names:
                if nm.lower() not in manual.lower():
                    findings.append(('texture catalogue', None,
                                     'pattern %r exists in the code but has no '
                                     'name in MANUAL.md' % nm))
    except OSError:
        pass
    # (2b) the PDF builders state the same count - they are hand-written
    #      documents and repeated the "21 patterns" claim for four releases
    #      (TEXTURING.pdf even SKIPPED the six preset-less patterns while
    #      its build message counted 27).
    for bname in ('make_manual_pdf.py', 'make_texture_pdf.py'):
        bpath = os.path.join(ROOT, 'tools', bname)
        try:
            btxt = open(bpath, encoding='utf-8').read()
        except OSError:
            continue
        for m_cnt in re.finditer(r'(\d+) patterns on (\d+) pages', btxt):
            if int(m_cnt.group(1)) != len(codes):
                findings.append(('texture catalogue', None,
                                 '%s states %s patterns, the code has %d'
                                 % (bname, m_cnt.group(1), len(codes))))
            want_pages = (len(codes) + 7) // 8
            if int(m_cnt.group(2)) != want_pages:
                findings.append(('texture catalogue', None,
                                 '%s states %s pattern pages, 8 slots per page '
                                 'means %d' % (bname, m_cnt.group(2),
                                               want_pages)))
    # (3) the inventory document must exist and carry the current version
    inv = os.path.join(ROOT, 'docs', 'TOOLS_INVENTORY.md')
    if not os.path.isfile(inv):
        findings.append(('tools inventory', None,
                         'docs/TOOLS_INVENTORY.md is missing'))
    else:
        itxt = open(inv, encoding='utf-8').read()
        st = re.search(r"variable_version:\s*'([^']+)'",
                       open(os.path.join(ROOT, 'macros', '01_state.cfg'),
                            encoding='utf-8').read())
        if st and st.group(1) not in itxt:
            findings.append(('tools inventory', None,
                             'docs/TOOLS_INVENTORY.md does not carry the '
                             'current version %r' % st.group(1)))

    print('==== R165 DOC CHECK: %d macro tokens, %d lcd paths, %d menu '
          'parents, %d ch.18 samples ===='
          % (len(seen), n_paths, len(by_parent), len(samples)))
    if findings:
        for (kind, ln, msg) in findings:
            print('  [%s] MANUAL:%s  %s' % (kind, ln or '-', msg))
        print('==== R165 DOC CHECK: %d FINDINGS ====' % len(findings))
        sys.exit(1)
    print('==== R165 DOC CHECK: clean - documentation matches reality ====')
    sys.exit(0)


if __name__ == '__main__':
    main()
