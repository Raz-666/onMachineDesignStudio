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
SKIP_DIRS = {'.git', '__pycache__', 'testfixtures', 'backups'}
SKIP_SUFFIX = {'.pyc', '.pyo'}
SKIP_LOGS = ('R2-DOCTOR-', '.gcode.txt')


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
        raise SystemExit('usage: build_release_zip.py <version, z.B. 26.3>')
    ver = sys.argv[1]
    bump_version(ver)
    zp = build_zip(ver)
    verify_complete(zp, ver)
    print('OK: complete release R2-%s ready: %s' % (ver, zp))
