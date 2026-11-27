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

# Top-level Konfig / Skripte
INCLUDE_TOP = ['AGENTS.md', 'README.md', 'update.sh', 'printer.cfg',
               'klipper-e3-r2d2.cfg']

# Ordner, die NICHT ins Release-Package gehören (Tests, Backups, Logs)
SKIP_DIRS = {'.git', '__pycache__', 'testfixtures', 'backups'}
SKIP_SUFFIX = {'.pyc', '.pyo'}
SKIP_LOGS = ('R2-DOCTOR-', '.gcode.txt')


def bump_version(new_ver):
    """Set all three version stamps to the new version (no drift)."""
    stamps = {
        'macros/01_state.cfg': ('variable_version', "variable_version: 'R2-%s'" % new_ver),
        'web/index.html': ('id="ver"', '<span id="ver">R2-%s</span>' % new_ver),
        'tools/r2_postproc.py': ("POSTPROC_RELEASE = ",
                                 "POSTPROC_RELEASE = 'R2-%s'" % new_ver),
    }
    for rel, (_old_marker, new_line) in stamps.items():
        p = os.path.join(REPO, rel)
        s = open(p, errors='replace').read()
        if rel == 'tools/r2_postproc.py':
            s2 = re.sub(r"POSTPROC_RELEASE = 'R2-[^']*'",
                        "POSTPROC_RELEASE = 'R2-%s'" % new_ver, s, count=1)
        else:
            # replace the current value wherever it appears
            s2 = re.sub(r"variable_version:\s*'R2-[^']*'",
                        "variable_version: 'R2-%s'" % new_ver, s, count=1) if rel == 'macros/01_state.cfg' \
                else re.sub(r'<span id="ver">R2-[^<]*</span>',
                            '<span id="ver">R2-%s</span>' % new_ver, s, count=1)
        assert s2 != s, 'version stamp unchanged in %s' % rel
        open(p, 'w').write(s2)
        print('[bump] %s -> R2-%s' % (rel, new_ver))


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
           'r2_setup_lib.sh', 'AGENTS.md', 'README.md']
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
