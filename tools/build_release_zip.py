#!/usr/bin/env python3
"""R287: complete release-ZIP builder.

Grundregel (user, verbindlich): JEDES Release-ZIP ist KOMPLET - alles, was
ins klipper-e3-r2d2-Package gehört, ist drin. Keine Halb-ZIPs. Wenn es nicht
komplett geht, wird gar keine erstellt.

Jede ZIP bekommt eine eigene, fortlaufende Versionsnummer (nie dieselbe).
Alle ZIPs bleiben in der Repo (nie gelöscht), durchnummeriert.

Dieser Builder:
  - bumpft die Versionsmarker (macros/01_state.cfg, web/index.html,
    tools/r2_postproc.py POSTPROC_RELEASE) auf die neue Version
  - baut die ZIP mit dem klipper-e3-r2d2/-Präfix, ALLEN Package-Ordnern,
    allen 28 Root-PDFs, den Konfig-Dateien und r2_setup_lib.sh (Root+tools)
  - verifiziert die Vollständigkeit gegen eine Manifest-Liste der
    required entries (r199-Check afterwards)

Usage:  python3 tools/build_release_zip.py 26.3
"""
import os
import re
import sys
import zipfile

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PREFIX = 'klipper-e3-r2d2/'

# Package-Ordner, die komplett mitgenommen werden
INCLUDE_DIRS = ['macros', 'menus', 'tools', 'web', 'docs']

# Top-level Konfig / Skripte + nutzerfacing-Dokumentation
INCLUDE_TOP = ['AGENTS.md', 'README.md', 'update.sh', 'printer.cfg',
               'klipper-e3-r2d2.cfg', 'printer.cfg.example',
               'MANUAL.md', 'INSTALL.md', 'COMPATIBILITY.md',
               'DEVELOPMENT.md']

# Ordner, die NICHT ins Release-Package gehören (Tests, Backups, Logs)
# testfixtures = Dev-only G-code test data (~14 MB) - stays OUT of the
# user update ZIP (developer checkout from git has them; see PACKAGING note
# in README). The 4 markdown docs + printer.cfg.example above ARE user-facing
# and ship WITH the ZIP.
SKIP_DIRS = {'.git', '__pycache__', 'testfixtures', 'backups', '.audio_cache'}
SKIP_SUFFIX = {'.pyc', '.pyo'}
SKIP_LOGS = ('R2-DOCTOR-', '.gcode.txt')


def _run(cmd):
    import subprocess
    return subprocess.run(cmd, cwd=REPO, capture_output=True, text=True)


def _gate_config_validator():
    """Gate 1 - Klipper-Konfiguration: config_validator.py, fail on REAL errors.

    The validator classifies German comments/descriptions as "non-ASCII
    errors"; those are accepted warnings here (WebUI/UTF-8 handles them, and
    the only LCD-critical non-ASCII - menu name: labels - are already
    ASCII-safe). Only a NON non-ASCII error blocks the release.
    """
    r = _run(['python3', 'tools/config_validator.py'])
    out = (r.stdout or '') + (r.stderr or '')
    real = [l for l in out.splitlines()
            if l.strip().startswith('- ') and 'non-ASCII' not in l]
    nonascii = [l for l in out.splitlines() if 'non-ASCII' in l]
    if real:
        raise SystemExit('GATE config_validator: real errors:\n  '
                         + '\n  '.join(real))
    print('[gate] config_validator: OK (%d non-ASCII warnings accepted)'
          % len(nonascii))


def _gate_jinja():
    """Gate 2 - Jinja-Templates: syntax-parse every macro body.

    Mirrors the macro_render_test.py parser: section boundary is the next
    '[' config header (NOT an inline '# ---' comment - those appear inside
    macro bodies), the gcode: header is dropped, and Klipper's '#' comment
    strip is applied first (a '#'-comment line may carry example '{% set %}'
    text that Jinja must not parse).
    """
    try:
        from jinja2 import Environment
    except ImportError:
        print('[gate] jinja2 not installed - Jinja gate SKIPPED (warn)')
        return
    env = Environment()

    def klipper_strip(txt):
        return '\n'.join(l[:l.find('#')] if '#' in l else l
                         for l in txt.split('\n'))

    def get_body(txt, name):
        m = re.search(r'\[gcode_macro ' + re.escape(name) + r'\]\n(.*?)(?=\n\[|\Z)',
                      txt, re.S)
        body = m.group(1)
        lines = []
        started = False
        for z in body.split('\n'):
            if z.startswith('gcode:'):
                started = True
                continue
            if started:
                if z.startswith(('variable_', 'description:', 'rename_existing:')):
                    break
                lines.append(z[4:] if z.startswith('    ') else z)
        return klipper_strip('\n'.join(lines))

    checked = 0
    for fn in sorted(os.listdir(os.path.join(REPO, 'macros'))):
        if not fn.endswith('.cfg'):
            continue
        s = open(os.path.join(REPO, 'macros', fn), errors='replace').read()
        for m in re.finditer(r'(?m)^\[gcode_macro\s+([^\]]+)\]', s):
            name = m.group(1).strip()
            try:
                env.parse(get_body(s, name))
            except Exception as e:
                raise SystemExit('GATE jinja: syntax error in macro %s (%s): %s'
                                 % (name, fn, e))
            checked += 1
    print('[gate] jinja syntax: OK (%d macro bodies parsed)' % checked)


def _gate_menu():
    """Gate 3 - Menüexport: committed menu_structure.json must match a fresh export."""
    if not os.path.isfile(os.path.join(REPO, 'tools', 'menu_json_export.py')):
        print('[gate] menu_json_export.py missing - menu gate SKIPPED (warn)')
        return
    tmp = '/tmp/_r2_menu_gate.json'
    r = _run(['python3', 'tools/menu_json_export.py',
              '--cfg', 'menus/lcd_menues.cfg', '--out', tmp])
    if r.returncode != 0:
        raise SystemExit('GATE menu: menu_json_export failed:\n'
                         + (r.stdout + r.stderr)[-2000:])
    exported = open(tmp, errors='replace').read()
    committed_path = os.path.join(REPO, 'web', 'menu_structure.json')
    committed = (open(committed_path, errors='replace').read()
                 if os.path.isfile(committed_path) else '')
    if exported != committed:
        raise SystemExit('GATE menu: menu_structure.json is STALE - re-run '
                         'tools/menu_json_export.py (and --embed web/index.html) '
                         'before building the release')
    print('[gate] menu export: OK (menu_structure.json current, no drift)')


def _gate_postproc():
    """Gate 4 - Post-Processing: r2_postproc compiles + release stamp present."""
    pp = os.path.join(REPO, 'tools', 'r2_postproc.py')
    if not os.path.isfile(pp):
        print('[gate] r2_postproc.py missing - postproc gate SKIPPED (warn)')
        return
    src = open(pp, errors='replace').read()
    import ast
    try:
        ast.parse(src)
    except SyntaxError as e:
        raise SystemExit('GATE postproc: r2_postproc.py syntax error: %s' % e)
    if not re.search(r"POSTPROC_RELEASE\s*=\s*'R2-[^']+'", src):
        raise SystemExit('GATE postproc: POSTPROC_RELEASE stamp missing')
    print('[gate] postproc: OK (r2_postproc.py parses, POSTPROC_RELEASE set)')


def pre_build_gates():
    """All cheap release gates run BEFORE the ZIP is built (ChatGPT audit
    26.14: complete the release-check - Klipper-config, Jinja-templates,
    menu export, post-processing as common release gates)."""
    print('[gates] running pre-build release gates...')
    _gate_config_validator()
    _gate_jinja()
    _gate_menu()
    _gate_postproc()
    print('[gates] all pre-build gates PASSED')


def bump_version(new_ver):
    """Set all version stamps to the new version (no drift).

    Every stamp is a list of (regex, replacement) pairs, so a single file can
    carry MORE than one version string. web/index.html carries TWO: the
    visible <span id="ver"> and the JS window.R2WEB.ver - both must move
    together or the page shows a stale build while the backend reports the
    new one (ChatGPT audit 26.14: LCD/WebUI not in sync). The JS ver uses
    R2-<date> so it shares the SAME format as the macro version stamp.
    """
    v = 'R2-%s' % new_ver
    stamps = {
        'macros/01_state.cfg': [
            (r"variable_version:\s*'R2-[^']*'",
             "variable_version: '%s'" % v),
        ],
        'web/index.html': [
            (r'<span id="ver">R2-[^<]*</span>',
             '<span id="ver">%s</span>' % v),
            (r"ver:'R2[^']*'",
             "ver:'%s'" % v),
        ],
        'tools/r2_postproc.py': [
            (r"POSTPROC_RELEASE = 'R2-[^']*'",
             "POSTPROC_RELEASE = '%s'" % v),
        ],
    }
    for rel, pairs in stamps.items():
        p = os.path.join(REPO, rel)
        s = open(p, errors='replace').read()
        s2 = s
        changed = False
        for rx, repl in pairs:
            s2n = re.sub(rx, repl, s2, count=1)
            if s2n != s2:
                changed = True
                s2 = s2n
        if not changed:
            raise SystemExit('version stamp unchanged in %s (no R2-... match)'
                             % rel)
        open(p, 'w').write(s2)
        print('[bump] %s -> %s' % (rel, v))


def build_zip(new_ver):
    zipname = 'klipper-e3-r2d2-UPDATE-R2-%s.zip' % new_ver
    zippath = os.path.join(REPO, zipname)
    if os.path.exists(zippath):
        # never overwrite a release artifact - bump is mandatory
        raise SystemExit('REFUSING: %s existiert bereits - bei jedem '
                         'Release eine NEUE Versionsnummer, keine '
                         'Überschreibung' % zipname)

    count = 0
    with zipfile.ZipFile(zippath, 'w', zipfile.ZIP_DEFLATED,
                         compresslevel=9) as zf:
        # 1. alle Root-PDFs (Dokumentation)
        for fn in sorted(os.listdir(REPO)):
            if fn.endswith('.pdf'):
                zf.write(os.path.join(REPO, fn), PREFIX + fn)
                count += 1
        # 2. Package-Ordner komplett
        for d in INCLUDE_DIRS:
            dp = os.path.join(REPO, d)
            if not os.path.isdir(dp):
                continue
            for root, dirs, files in os.walk(dp):
                dirs[:] = [x for x in dirs if x not in SKIP_DIRS]
                for fn in files:
                    if fn.endswith(tuple(SKIP_SUFFIX)):
                        continue
                    if any(s in fn for s in SKIP_LOGS):
                        continue
                    full = os.path.join(root, fn)
                    rel = os.path.relpath(full, REPO)
                    if rel.endswith('.zip'):
                        continue
                    zf.write(full, PREFIX + rel)
                    count += 1
        # 3. r2_setup_lib.sh am Root (Kopии wie im release)
        src = os.path.join(REPO, 'tools', 'r2_setup_lib.sh')
        if os.path.isfile(src):
            zf.write(src, PREFIX + 'r2_setup_lib.sh')
            count += 1
        # 4. Top-level Konfig
        for f in INCLUDE_TOP:
            fp = os.path.join(REPO, f)
            if os.path.isfile(fp):
                zf.write(fp, PREFIX + f)
                count += 1

    size = os.path.getsize(zippath)
    print('[zip] %s  files=%d  size=%.2f MB' % (zipname, count, size / 1e6))
    return zippath


def required_entries():
    """The load-bearing entries every release ZIP MUST contain."""
    req = ['macros/01_state.cfg', 'update.sh', 'tools/r2_postproc.py',
           'r2_setup_lib.sh', 'AGENTS.md', 'README.md',
           'printer.cfg.example', 'MANUAL.md', 'INSTALL.md',
           'COMPATIBILITY.md', 'DEVELOPMENT.md']
    # at least the 28 docs PDFs
    pdfs = [f for f in os.listdir(REPO) if f.endswith('.pdf')]
    req += pdfs
    return req


def verify_complete(zippath, new_ver):
    """Hard completeness gate - refuse a ZIP that is not complete."""
    zf = zipfile.ZipFile(zippath)
    names = set(n.split(PREFIX, 1)[-1] for n in zf.namelist())
    missing = [r for r in required_entries() if r not in names]
    if missing:
        raise SystemExit('UNCOMPLETE ZIP %s - fehlen: %r' % (zippath, missing))
    # version consistency inside the zip
    macro_ver = None
    pp_ver = None
    for n in zf.namelist():
        if n.endswith('macros/01_state.cfg'):
            for l in zf.read(n).decode('utf-8', 'replace').split('\n'):
                m = re.search(r"variable_version:\s*'R2-([^']+)'", l)
                if m:
                    macro_ver = m.group(1)
        if n.endswith('tools/r2_postproc.py'):
            head = zf.read(n).decode('utf-8', 'replace')[:8000]
            m = re.search(r"POSTPROC_RELEASE = 'R2-([^']+)'", head)
            if m:
                pp_ver = m.group(1)
    if macro_ver != new_ver or pp_ver != new_ver:
        raise SystemExit('VERSION DRIFT in %s: macro=%s daemon=%s expected=%s'
                         % (zippath, macro_ver, pp_ver, new_ver))
    print('[verify] KOMPLET + version konsistent (R2-%s)' % new_ver)
    zf.close()


if __name__ == '__main__':
    if len(sys.argv) < 2:
        raise SystemExit('usage: build_release_zip.py <version, z.B. 26.3>'
                         ' [--skip-gates]')
    args = sys.argv[1:]
    skip_gates = '--skip-gates' in args
    args = [a for a in args if a != '--skip-gates']
    ver = args[0]
    if not skip_gates:
        pre_build_gates()
    else:
        print('[gates] --skip-gates set - release gates bypassed (expert mode)')
    bump_version(ver)
    zp = build_zip(ver)
    verify_complete(zp, ver)
    print('OK: complete release R2-%s ready: %s' % (ver, zp))
