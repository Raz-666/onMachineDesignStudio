#!/usr/bin/env python3
"""menu_json_export.py - lcd_menues.cfg -> menu_structure.json (.135, R196)

THE WEB-UI MIDDLE WAY (documented in DISPLAYS_DRUCKER_TESTS.md / the displays
PDF): no own web stack (Mainsail exists, it wins by being there), no second
menu truth to maintain. The SINGLE SOURCE OF TRUTH stays menus/lcd_menues.cfg
with its 1.910 render tests - and this tool EXPORTS that truth as JSON:

  - structure: the full [menu ...] tree (2.276 sections), parent/child from
    the section path
  - semantics: type (list/command/input), the RAW jinja name/enable templates,
    gcode actions, input ranges - everything the LCD shows, machine-readable
  - meta: counts + a content hash, so the moonraker extension and the demo
    page can detect a stale export

Output default: web/menu_structure.json. With --embed <page> the JSON is
injected into the page's EMBEDDED_MENU_JSON placeholder (the workspace
preview has no network - a self-contained page previews perfectly and the
live page still prefers fetching /server/r2_menu/tree first).

Deterministic, read-only, no printer needed. Tested by r193 checks
(tools/r190_tag_ladder.py does NOT cover this - the gen sweep does).
"""
import argparse
import hashlib
import json
import os
import re

SEC_RE = re.compile(r'^\[menu\s+([^\]]+)\]')
KEY_RE = re.compile(r'^([A-Za-z_][A-Za-z0-9_]*)\s*:\s*(.*)$')

# keys the exporter forwards (everything the LCD semantics need)
FWD_KEYS = ('type', 'name', 'enable', 'index', 'input', 'input_min',
            'input_max', 'input_step', 'realtime', 'description')


def parse_menu_cfg(path):
    """-> ordered list of dicts: {path: [...], key: value} per section."""
    sections = []
    cur = None
    last_key = None
    with open(path, 'r', errors='replace') as f:
        for raw in f:
            line = raw.rstrip('\n')
            if not line.strip():
                continue
            if not line.strip().startswith(('#', ';')):
                m = SEC_RE.match(line.strip())
                if m:
                    cur = {'__path': [p for p in m.group(1).split() if p]}
                    sections.append(cur)
                    last_key = None
                    continue
            if cur is None:
                continue
            if line[:1] not in (' ', '\t'):
                m = KEY_RE.match(line)
                if m:
                    last_key = m.group(1)
                    val = m.group(2).strip()
                    if val == '' or val == '""':
                        # multi-line value starts here (gcode: etc.)
                        cur[last_key] = ''
                    else:
                        cur[last_key] = val
                # a comment or junk line at key level ends continuation
                if line.strip().startswith(('#', ';')):
                    last_key = None
                continue
            # indented -> continuation of the last key
            if last_key is not None:
                add = line.strip()
                if add and not add.startswith(('#', ';')):
                    cur[last_key] = (cur[last_key] + '\n' + add).strip('\n')
                else:
                    last_key = None
    return sections


def _stripq(v):
    """R201: remove ONE layer of surrounding quotes. Klipper's menu parser
    keeps the quotes in the raw option value (they matter for its own
    parsing), but the JSON export carries VALUES - a web client should
    not have to know that lcd_menues.cfg quotes its name:/enable: strings
    (the .135 page showed '> PRINT AS SLICED' WITH quotes as the label).
    Only a matching OUTER pair is stripped - quotes inside the text stay."""
    if isinstance(v, str) and len(v) >= 2 and v[0] == v[-1] and v[0] in ('\"', "'"):
        return v[1:-1]
    return v


def build_tree(sections):
    """-> nested {id, type, name, enable, gcode, input*, children[]}."""
    nodes = {}
    root = None
    for sec in sections:
        path = sec['__path']
        if not path:
            continue
        node = {'id': ' '.join(path)}
        for k in FWD_KEYS:
            if k in sec and sec[k] != '':
                node[k] = sec[k]
        for k in ('name', 'enable'):
            if k in node:
                node[k] = _stripq(node[k])
        gcode = sec.get('gcode', '')
        if gcode:
            node['gcode'] = [l for l in gcode.split('\n') if l.strip()]
        node['children'] = []
        # duplicate section paths MERGE like Klipper's parser does (the
        # later section's options win, children accumulate) - R197b found
        # four zombie copies in the field menu; the export must never
        # silently drop or duplicate nodes because of them
        ex = nodes.get(tuple(path))
        if ex is not None:
            ex.update({k: v for k, v in node.items() if k != 'children'})
            node = ex
        else:
            nodes[tuple(path)] = node
        if len(path) == 1 and root is None:
            root = node
        elif len(path) > 1:
            parent = nodes.get(tuple(path[:-1]))
            if parent is not None:
                parent['children'].append(node)
            else:
                # orphan (no parent section) - keep it visible under a
                # synthetic __orphan root instead of losing it
                orph = nodes.setdefault(('__orphan',),
                                        {'id': '__orphan', 'name': '(orphan)',
                                         'type': 'list', 'children': []})
                orph['children'].append(node)
    return root, nodes


def extract_live_objects(sections):
    """R204 (.136c field log): the EXACT set of printer objects the menu
    name:/enable: templates reference - the live endpoint queries ONLY
    these. The .136 version queried every gcode_macro object (~300 on the
    field Pi, each serializing ALL its variables) and blocked klippy's
    reactor for 0.7 s per poll -> 'Neopixel update did not succeed' in the
    console, the exact 'Timer too close' class from .125. Scanning the
    templates keeps the set self-maintaining: a new menu object reference
    lands in the export automatically."""
    objs = set()
    for sec in sections:
        for k in ('name', 'enable'):
            v = sec.get(k, '')
            if not v or '{' not in v:
                continue
            for m in re.finditer(r"printer\[['\"]([^'\"]+)['\"]\]", v):
                objs.add(m.group(1))
            for m in re.finditer(r'printer\.([a-z_][a-z0-9_]*)', v):
                objs.add(m.group(1))
    return sorted(objs)


def export(cfg_path, out_path=None, page=None):
    sections = parse_menu_cfg(cfg_path)
    root, nodes = build_tree(sections)
    counts = {}
    for n in nodes.values():
        counts[n.get('type', '?')] = counts.get(n.get('type', '?'), 0) + 1
    payload = json.dumps(root, ensure_ascii=False, separators=(',', ':'))
    doc = {
        'generator': 'menu_json_export.py (.136e R206)',
        'source': os.path.basename(cfg_path),
        'sections': len(sections),
        'counts': counts,
        'sha256': hashlib.sha256(payload.encode('utf-8')).hexdigest()[:16],
        'live_objects': extract_live_objects(sections),   # R204
        'tree': root,
    }
    text = json.dumps(doc, ensure_ascii=False, indent=1)
    if out_path:
        os.makedirs(os.path.dirname(out_path) or '.', exist_ok=True)
        with open(out_path, 'w') as f:
            f.write(text + '\n')
    if page:
        import re as _re
        with open(page, 'r', errors='replace') as f:
            html = f.read()
        # compact form keeps the page readable; replaces BOTH the fresh
        # placeholder and a previously embedded payload (re-embeds work).
        # raw_decode finds the exact END of the old JSON - a regex would
        # stop at the first ';' inside a menu template string.
        block = 'const EMBEDDED_MENU_JSON = %s;' % json.dumps(
            doc, ensure_ascii=False)
        marker = '/*EMBEDDED_MENU_JSON*/'
        pre = 'const EMBEDDED_MENU_JSON = '
        if marker in html:
            html = html.replace(marker, json.dumps(doc, ensure_ascii=False))
        elif pre in html:
            i = html.index(pre) + len(pre)
            try:
                _doc, j = json.JSONDecoder().raw_decode(html, i)
            except ValueError:
                raise SystemExit('%s: embedded JSON does not parse' % page)
            html = html[:i] + json.dumps(doc, ensure_ascii=False) + html[j:]
        else:
            raise SystemExit('%s: no %s placeholder' % (page, marker))
        with open(page, 'w') as f:
            f.write(html)
    return doc


def main():
    here = os.path.dirname(os.path.abspath(__file__))
    repo = os.path.dirname(here)
    ap = argparse.ArgumentParser()
    ap.add_argument('--cfg', default=os.path.join(repo, 'menus',
                                                  'lcd_menues.cfg'))
    ap.add_argument('--out', default=os.path.join(repo, 'web',
                                                  'menu_structure.json'))
    ap.add_argument('--embed', default=None,
                    help='inject the JSON into this HTML page '
                         '(replaces /*EMBEDDED_MENU_JSON*/)')
    args = ap.parse_args()
    doc = export(args.cfg, args.out, args.embed)
    print('menu export: %d sections, counts %s, sha %s -> %s'
          % (doc['sections'], doc['counts'], doc['sha256'],
             args.out + (' + embedded into ' + args.embed if args.embed
                         else '')))


if __name__ == '__main__':
    main()
