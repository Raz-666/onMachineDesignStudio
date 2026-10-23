#!/usr/bin/env python3
"""R166: compile every macro template the way KLIPPER does - not the way we
hope it works.

WHY (field log .124, the boot blocker): update .124 shipped a gcode template
line at COLUMN 0 inside GEN_BRICKKIT/GEN_FIGURES. Klipper does not read the
gcode body with our regexes - configfile.append_fileconfig() strips every
line at the first '#', then feeds the file to
configparser.RawConfigParser(strict=False, inline_comment_prefixes=(';', '#')).
A config parser treats an UNINDENTED line inside a value as a NEW OPTION
(name=value): the gcode: value was silently TRUNCATED at that line, the
template ended inside an open {% if %} and klippy died at connect with
'Error loading template gcode_macro GEN_BRICKKIT:gcode - unexpected end of
template, looking for endif'. The whole battery stayed green because the
render test extracts bodies with regexes that tolerate column-0 lines.

This tool replays the EXACT klipper pipeline:

  1. read file, \\r\\n -> \\n
  2. per-line: cut at the first '#'                      (configfile.py)
  3. RawConfigParser(strict=False, inline_comment_prefixes=(';', '#'))
  4. every [gcode_macro *] / [delayed_gcode *] 'gcode'
     value is compiled with jinja2.Environment('{%', '%}', '{', '}')
     - klipper's single-brace environment (gcode_macro.py)
  5. option allowlist per section type - a column-0 line inside a body
     shows up as a bogus OPTION name and fails here, even when the
     truncated remains of the template would still compile
  6. diff: the body our regexes see vs the body configparser returns -
     any difference beyond comment tails means klipper runs something
     else than the file on screen shows

Exit 0 = klipper will load every template in this repo. Run it in the
battery and in every release smoke test - it is the only check that sees
config parser reality.
"""
import configparser
import io
import os
import re
import sys

import jinja2

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)

# the klipper environment (gcode_macro.py: jinja2.Environment('{%','%}','{','}'))
ENV = jinja2.Environment('{%', '%}', '{', '}')

# what klipper's configfile strips before the parser sees the line
def klipper_strip_hash(data):
    lines = data.split('\n')
    for i, line in enumerate(lines):
        pos = line.find('#')
        if pos >= 0:
            lines[i] = line[:pos]
    return '\n'.join(lines)


def parse_like_klipper(data):
    """return (RawConfigParser) - raises configparser.Error on real breakage"""
    buf = io.StringIO(klipper_strip_hash(data.replace('\r\n', '\n')))
    fc = configparser.RawConfigParser(strict=False,
                                      inline_comment_prefixes=(';', '#'))
    fc.read_file(buf, '<cfg>')
    return fc


# the regex every OTHER tool in this repo uses to pull a gcode body - the
# optimistic view. If it disagrees with configparser, klipper wins.
BODY_RE = re.compile(r'(?m)^gcode:\n(.*?)(?=^\[|\Z)', re.S)

ALLOWED = {
    'gcode_macro': ('description', 'gcode', 'rename_existing'),
    'delayed_gcode': ('description', 'gcode', 'initial_duration'),
}
VARIABLE_PREFIX = 'variable_'

NAIVE_SECTIONS = re.compile(r'(?m)^\[([^\]]+)\]')


def naive_bodies(txt):
    """section header -> regex-extracted gcode body (the optimistic view)"""
    out = {}
    spans = list(NAIVE_SECTIONS.finditer(txt))
    for i, m in enumerate(spans):
        head = m.group(1).strip()
        end = spans[i + 1].start() if i + 1 < len(spans) else len(txt)
        bm = BODY_RE.search(txt, m.end(), end)
        if bm:
            out.setdefault(head, bm.group(1))
    return out


def norm_body(body):
    """normalize for the diff: kill comment tails, blank edges, spacing"""
    out = []
    for ln in body.split('\n'):
        p = ln.find('#')
        if p >= 0:
            ln = ln[:p]
        p = ln.find(';')
        if p >= 0:
            ln = ln[:p]
        ln = ln.rstrip()
        if ln.strip():
            out.append(ln.strip())
    return out


def check_cfg(path):
    """return list of (kind, message) problems for one .cfg file"""
    fails = []
    rel = os.path.relpath(path, ROOT)
    raw = open(path).read()
    try:
        fc = parse_like_klipper(raw)
    except configparser.Error as e:
        return [('FAIL', '%s: configparser cannot even read the file: %s'
                 % (rel, e))]

    naive = naive_bodies(raw)

    for sec in fc.sections():
        parts = sec.split(None, 1)
        stype = parts[0] if parts else sec
        opts = fc.options(sec)
        # ---- option allowlist: a column-0 body line becomes a bogus option
        if stype in ALLOWED:
            for o in opts:
                if (o not in ALLOWED[stype]
                        and not o.startswith(VARIABLE_PREFIX)):
                    fails.append((
                        'FAIL',
                        '%s [%s]: option %r is not a %s option - an '
                        'UNINDENTED line inside the gcode body (klipper '
                        'truncates the template there = boot blocker)'
                        % (rel, sec, o, stype)))
        # ---- template compile: exactly what klippy does at connect
        if stype in ALLOWED and fc.has_option(sec, 'gcode'):
            tpl = fc.get(sec, 'gcode')
            try:
                ENV.from_string(tpl)
            except jinja2.exceptions.TemplateSyntaxError as e:
                lines = tpl.splitlines()
                where = ('line %d: %s' % (e.lineno, lines[e.lineno - 1].strip())
                         if 0 < e.lineno <= len(lines) else 'line %d' % e.lineno)
                fails.append(('FAIL', '%s [%s]: template broken as klipper '
                             'loads it - %s # %s'
                             % (rel, sec, where, e.message)))
            # ---- diff vs the regex view (what every other tool reads)
            if sec in naive and norm_body(tpl) != norm_body(naive[sec]):
                nt, kt = norm_body(naive[sec]), norm_body(tpl)
                idx = next((i for i in range(min(len(nt), len(kt)))
                            if nt[i] != kt[i]), min(len(nt), len(kt)))
                fails.append(('FAIL', '%s [%s]: klipper loads a DIFFERENT '
                             'template than the file shows - first divergence'
                             ' at body line %d: regex=%r configparser=%r'
                             % (rel, sec, idx + 1,
                                nt[idx] if idx < len(nt) else '<end>',
                                kt[idx] if idx < len(kt) else '<end>')))
    return fails


def main():
    targets = []
    for sub in ('macros', 'menus'):
        d = os.path.join(ROOT, sub)
        if os.path.isdir(d):
            targets += sorted(os.path.join(d, f) for f in os.listdir(d)
                              if f.endswith('.cfg'))
    ex = os.path.join(ROOT, 'printer.cfg.example')
    if os.path.isfile(ex):
        targets.append(ex)

    n_tpl = n_sec = 0
    fails = []
    for path in targets:
        rel = os.path.relpath(path, ROOT)
        raw = open(path).read()
        try:
            fc = parse_like_klipper(raw)
        except configparser.Error as e:
            fails.append(('FAIL', '%s: configparser: %s' % (rel, e)))
            continue
        for sec in fc.sections():
            n_sec += 1
            if sec.split(None, 1)[0] in ALLOWED and fc.has_option(sec, 'gcode'):
                n_tpl += 1
        fails += check_cfg(path)

    for kind, msg in fails:
        print('%s %s' % (kind, msg))
    print('%s %-52s %d cfg files, %d sections, %d templates'
          % ('OK  ' if not fails else 'FAIL', 'klipper-parse + jinja compile',
             len(targets), n_sec, n_tpl))
    return 1 if fails else 0


if __name__ == '__main__':
    sys.exit(main())
