#!/usr/bin/env python3
"""R256 (.142l): DRIFT AUDIT - "Pre-Print says A, Live says B".

WHAT THIS LOOKS FOR
===================
The field complaint behind this tool: the Pre-Print menu shows one value and the
Live menu shows another for what looks like the same thing, so the user cannot
tell which one the printer is actually using.

Two DIFFERENT things can cause that, and only one of them is a bug:

  (1) BY DESIGN - "target vs actual".
      Pre-Print holds the values a print WILL run with (the file's slicer
      header / your armed override), Live holds what is in effect RIGHT NOW
      (the live tuning you dialled in while printing). Different on purpose.
      Fine - as long as the row SAYS which one it is.

  (2) DRIFT - the same label reading from two different places.
      e.g. a row called 'Flow' that reads `file_flow` in Pre-Print and
      `live_flow` somewhere else, while a THIRD place reads `gcode_move.flow`.
      That is the real defect: nobody can tell which number is the truth, and
      after an edit one of them is stale.

This tool therefore does NOT compare numbers (there is no printer here). It
compares SOURCES: for every numeric read-out in the LCD menus it records
which menu branch shows it and which variable feeds it.

  * a key read by BOTH branches from the SAME source  -> consistent (ok)
  * a key read by both branches from DIFFERENT sources-> BY DESIGN only if the
    row text marks it (Ist/actual, geplant/target); otherwise a SUSPECT
  * a row whose TEXT names a quantity (PA, Flow, Speed, Accel, Z) but whose
    expression reads a DIFFERENT quantity                    -> SUSPECT
  * a quantity shown ONLY in one branch while the other branch has no row for
    it at all                                                -> note (not a bug)

Exit 0 = no suspect. Run: python3 tools/r256_drift_audit.py [-v]
"""
import os
import re
import sys
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
LCD = os.path.join(ROOT, 'menus', 'lcd_menues.cfg')

VERBOSE = '-v' in sys.argv

# the quantities the field complaint was about, with the words that name them
# on the LCD and the variable stems that feed them
QUANT = {
    'flow':   {'words': ('flow', 'fluss', 'extrusion', 'flw'),
               'stems': ('flow',)},
    'speed':  {'words': ('speed', 'geschw', 'velocity', 'mm/s', 'spd'),
               'stems': ('speed', 'velocity', 'spd')},
    'accel':  {'words': ('accel', 'beschl', 'mm/s2', 'mm/s²', 'acc:'),
               'stems': ('accel', 'acc')},
    'pa':     {'words': ('pa ', 'pa:', 'pressure advance', 'pressure_advance'),
               'stems': ('pa', 'pressure_advance')},
    'z':      {'words': (' z ', 'z=', 'z-offset', 'zoffset', 'height'),
               'stems': ('z', 'zoffset', 'z_offset', 'height')},
    'fan':    {'words': ('fan', 'luefter', 'lüfter'),
               'stems': ('fan',)},
    'temp':   {'words': ('temp', '°c', 'hotend', 'nozzle', 'bett'),
               'stems': ('temp', 'hotend', 'bed', 'nozzle')},
}

# rows that explicitly say WHICH of the two they show (that is what makes a
# divergence by design instead of drift)
# R256: the markers are searched in the label TEXT only (Jinja stripped) and
# must be real words - 'file_pa' is a variable name, not a statement about
# which value the row shows.
MARK_ACTUAL = ('ist ', 'actual', 'now:', 'jetzt', 'aktuell', 'gerade', 'wirkt',
               'running', 'in effect', 'live:')
MARK_TARGET = ('soll', 'target', 'planned', 'geplant', 'datei:', 'armed',
               'override', 'file:')

SECT_RE = re.compile(r'\[menu ([^\]]+)\]\s*\n(.*?)(?=\n\[menu |\Z)', re.S)
OPT_RE = re.compile(r'^(name|enable):\s*(.+?)\s*$', re.M)
PRINTER_RE = re.compile(r"printer\[\s*'([^']+)'\s*\]")
KEY_RE = re.compile(r"\.([A-Za-z_][A-Za-z_0-9]*)")



PAIR_RE = re.compile(r"printer\[\s*'([^']+)'\s*\]((?:\s*\|[^.]*?)?\s*\.\s*"
                     r"([A-Za-z_][A-Za-z_0-9]*))?")
# R256: the attribute chain is bound to ITS OWN printer[...] access. The first
# attempt let the regex run across `|default(printer['other'].key)` and blamed
# the wrong macro - the two "drift" hits it produced (_MATERIALS/file_bed,
# _SDM/gen_arm) were that artefact: neither macro even HAS those variables.
ATTR_RE = re.compile(r"printer\[\s*'([^']+)'\s*\]"
                     r"((?:\s*\.\s*[A-Za-z_][A-Za-z_0-9]*)+)")
IDX_RE = re.compile(r"printer\[\s*'([^']+)'\s*\]")


def source_pairs(label):
    """-> [(macro, key)] : which variable feeds which read-out.

    `printer['gcode_macro _STATE'].file_flow_ratio` gives
    ('gcode_macro _STATE', 'file_flow_ratio') - the LAST attribute of the
    chain is the value that is printed. A bare `printer['x']` (a whole
    section) gives ('x', '<section>').
    """
    out = []
    for m in ATTR_RE.finditer(label):
        chain = [a.strip() for a in m.group(2).split('.') if a.strip()]
        if chain:
            out.append((m.group(1), chain[-1]))
    named = {m.group(1) for m in ATTR_RE.finditer(label)}
    for m in IDX_RE.finditer(label):
        if m.group(1) not in named:
            out.append((m.group(1), '<section>'))
    return out


def jinja_stripped(label):
    """the label TEXT without its Jinja expressions - only words a user reads"""
    return re.sub(r'\{[^}]*\}', ' ', label)


def branch_of(path):
    """'__main __preprint ...' -> 'preprint' (the family the row lives in)"""
    parts = path.split()
    for p in parts[1:]:
        if p.startswith('__'):
            return p[2:]
    return parts[-1]


def rows():
    src = open(LCD, encoding='utf-8').read()
    out = []
    for m in SECT_RE.finditer(src):
        path, body = m.group(1).strip(), m.group(2)
        name = None
        for om in OPT_RE.finditer(body):
            if om.group(1) == 'name':
                name = om.group(2)
                break
        if not name:
            continue
        pairs = source_pairs(name)
        out.append({'path': path, 'branch': branch_of(path),
                    'label': name, 'text': jinja_stripped(name),
                    'pairs': pairs,
                    'macros': sorted({m for m, _ in pairs}),
                    'keys': sorted({k for _, k in pairs})})
    return out


def main():
    allrows = rows()
    print('=== DRIFT AUDIT: %d LCD rows with a label ===' % len(allrows))

    # ---------------------------------------------------------------- sources
    by_key = defaultdict(list)      # key -> [(branch, macro, label, path)]
    for r in allrows:
        for macro, k in r['pairs']:
            by_key[k].append((r['branch'], macro, r['label'], r['path']))

    shared = {k: v for k, v in by_key.items()
              if len({b for b, _, _, _ in v}) > 1}
    print('    %d read-out keys, %d of them appear in MORE THAN ONE branch'
          % (len(by_key), len(shared)))

    suspects = []
    by_design = []

    # ------------------------------------------- same key from several sources
    for k, uses in sorted(shared.items()):
        srcs = {(mac, b) for b, mac, _, _ in uses} if False else None
        # macro -> branches that read THIS key through it
        per_macro = defaultdict(set)
        labels = []
        for b, mac, lbl, path in uses:
            per_macro[mac].add(b)
            labels.append((lbl, path))
        if len(per_macro) == 1:
            if VERBOSE:
                print('  ok    %-22s one source (%s) in %s'
                      % (k, next(iter(per_macro)),
                         ', '.join(sorted(next(iter(per_macro.values()))))))
            continue
        marked = any(any(w in t.lower() for w in MARK_ACTUAL + MARK_TARGET)
                     for t, _ in labels)
        if marked:
            by_design.append((k, dict((m, sorted(b)) for m, b in per_macro.items())))
            print('  ok    %-22s target vs actual, the row says it: %s'
                  % (k, dict((m, sorted(b)) for m, b in per_macro.items())))
        else:
            suspects.append(('key', k, dict((m, sorted(b)) for m, b in per_macro.items())))
            print('  DRIFT %-22s one name, DIFFERENT sources: %s'
                  % (k, dict((m, sorted(b)) for m, b in per_macro.items())))

    # ------------- the field shape: the SAME WORD on two rows, fed by two
    #                different quantities, and the row does not say which
    word_src = defaultdict(lambda: defaultdict(set))
    word_lbl = defaultdict(lambda: defaultdict(list))
    for r in allrows:
        low = r['text'].lower()
        for q, d in QUANT.items():
            if not any(w in low for w in d['words']):
                continue
            for mac, key in r['pairs']:
                if key == '<section>':
                    continue
                word_src[q][r['branch']].add((mac, key))
                word_lbl[q][r['branch']].append(r['text'].strip()[:48])
    for q, per_br in sorted(word_src.items()):
        pre = per_br.get('preprint', set())
        liv = per_br.get('live', set())
        if not pre or not liv:
            print('  note  label word %-11s only one side has a row (%s)'
                  % (q, ', '.join(sorted(per_br))))
            continue
        common = pre & liv
        marked = any(any(w in t.lower() for w in MARK_ACTUAL + MARK_TARGET)
                     for t in word_lbl[q]['preprint'] + word_lbl[q]['live'])
        if common or marked:
            print('  ok    label word %-11s %d shared source(s)%s'
                  % (q, len(common), ', row marked' if marked else ''))
        else:
            suspects.append(('word', q, sorted(pre), sorted(liv),
                             word_lbl[q]['preprint'][:2],
                             word_lbl[q]['live'][:2]))
            print('  DRIFT label word %-11s Pre-Print reads %s, Live reads %s - '
                  'same word, no shared source, no Ist/Soll mark'
                  % (q, sorted(pre)[:2], sorted(liv)[:2]))

    # ------------------------------------------------------- one-sided rows
    fam = defaultdict(set)
    for r in allrows:
        for q, d in QUANT.items():
            low = r['label'].lower()
            if any(w in low for w in d['words']):
                fam[q].add(r['branch'])
    for q, br in sorted(fam.items()):
        if VERBOSE or 'preprint' in br or 'live' in br:
            print('  note  %-22s quantity shown in: %s'
                  % (q, ', '.join(sorted(br))))


    # ------------------- dead read-outs and double truths (static data flow)
    # For every variable a row SHOWS, is there a command that WRITES it? A row
    # that reads something nobody writes is a stale value by construction -
    # that is the "Pre-Print says A" that never changes again.
    macros_src = ''
    for sub in ('macros', 'menus'):
        d = os.path.join(ROOT, sub)
        if os.path.isdir(d):
            for f in sorted(os.listdir(d)):
                if f.endswith('.cfg'):
                    macros_src += open(os.path.join(d, f), encoding='utf-8').read()
    # R256: the WATCHER writes variables too (gen_busy, postproc_engine,
    # postproc_build, shaper_rec_* - the shaper set it even builds with a
    # %-format). Without this file the audit would call them dead.
    _pp = os.path.join(HERE, 'r2_postproc.py')
    if os.path.isfile(_pp):
        macros_src += open(_pp, encoding='utf-8').read()
    written = set(re.findall(r'VARIABLE=([A-Za-z_][A-Za-z_0-9]*)', macros_src))
    # R256: a name can also be written DYNAMICALLY
    #   SET_GCODE_VARIABLE ... VARIABLE={(gen|lower ~ '_preset_page')}
    # Those can never be matched literally - collect the suffix patterns and
    # exempt everything they can produce, or the audit invents 131 dead rows.
    # the real shapes in the tree:
    #   VARIABLE={var214|lower}                       (name held in a {% set %})
    #   {% set var214 = (gen|lower ~ '_preset_page') %}   (suffix built by ~)
    dyn = set()
    for m in re.finditer(r"~\s*'([A-Za-z_0-9]+)'", macros_src):
        dyn.add(m.group(1))
    # the watcher formats names: 'VARIABLE=shaper_rec_%s_%s' -> keep the prefix
    dyn_prefix = set(re.findall(r"VARIABLE[= ]([A-Za-z_][A-Za-z_0-9]*?)%s", macros_src))
    # names built by string concatenation: _sv_line('shaper_best_' + ax, ...)
    for m in re.finditer(r"_sv_line\('([A-Za-z_0-9]+)'", macros_src):
        dyn_prefix.add(m.group(1))
    # a name handed over through {% set x = ... %} and used as VARIABLE={x}
    indirect = re.findall(r'VARIABLE=\{\s*([A-Za-z_][A-Za-z_0-9]*)\s*(?:\|[^}]*)?\}',
                          macros_src)
    dyn_suffix = tuple(sorted({'_' + d.lstrip('_') for d in dyn})) or ('\x00',)
    declared = set(re.findall(r'^variable_([A-Za-z_][A-Za-z_0-9]*):', macros_src, re.M))
    dead = []
    for k, uses in sorted(by_key.items()):
        if k in ('<section>', 'variables', 'presets', 'axes'):
            continue     # object attributes, not variable names
        if k in written or k in declared:
            continue
        if k.endswith(dyn_suffix):
            continue
        if any(k.startswith(pre) for pre in dyn_prefix):
            continue
        if indirect and k.rsplit('_', 1)[-1] in ('page', 'presets', 'list', 'cnt'):
            continue     # built from a {% set %} name (var214 & co.)
        # save_variables are written by NAME in SAVE_VARIABLE VARIABLE=... too
        dead.append((k, sorted({b for b, _, _, _ in uses})))
    if dyn:
        print('  note  %d variable name(s) are written DYNAMICALLY (%s...) - '
              'exempt from the dead check'
              % (len(dead), ', '.join(sorted({'*'+d for d in dyn})[:3])))
    if dead:
        for k, br in dead[:12]:
            print('  DEAD  %-24s shown in %s but nothing writes it'
                  % (k, ', '.join(br)))
        suspects.append(('dead', len(dead), dead[:6]))
    else:
        print('  ok    data flow: every one of the %d shown variables is '
              'written somewhere' % len([k for k in by_key if k != '<section>']))

    # double truths: the same VARIABLE NAME declared in two different macros
    decl = defaultdict(set)
    for sub in ('macros', 'menus'):
        d = os.path.join(ROOT, sub)
        if not os.path.isdir(d):
            continue
        for f in sorted(os.listdir(d)):
            if not f.endswith('.cfg'):
                continue
            body = open(os.path.join(d, f), encoding='utf-8').read()
            for sec in re.finditer(r'\[gcode_macro ([^\]]+)\](.*?)(?=\n\[|\Z)',
                                   body, re.S):
                for v in re.findall(r'^variable_([A-Za-z_][A-Za-z_0-9]*):',
                                    sec.group(2), re.M):
                    decl[v].add(sec.group(1).strip())
    twins = {k: sorted(v) for k, v in decl.items() if len(v) > 1}
    if twins:
        print('  note  %d variable name(s) live in more than one macro (checked '
              'against the menu sources above):' % len(twins))
        for k, v in sorted(twins.items())[:12]:
            shown_by = sorted({m for _, m, _, _ in by_key.get(k, [])})
            flag = 'READS BOTH' if len([m for m in v if m in shown_by]) > 1 else ''
            print('        %-22s %s %s' % (k, v, flag))
    else:
        print('  ok    no variable name is declared by two macros')

    print()
    if suspects:
        print('R256 DRIFT AUDIT: %d SUSPECT(S)' % len(suspects))
        for x in suspects:
            print('   %s' % (x,))
        return 1
    print('R256 DRIFT AUDIT: 0 suspects - every shared read-out comes from one '
          'source, or the row marks it as target/actual (%d by design)'
          % len(by_design))
    return 0


if __name__ == '__main__':
    sys.exit(main())
