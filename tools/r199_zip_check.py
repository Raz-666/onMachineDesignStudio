#!/usr/bin/env python3
"""R199: release-zip layout + version consistency check.

Field bug (.134, user report: "after the update it still shows .133"):
the .134 update zip was built FLAT - no klipper-e3-r2d2/ top-level
folder. update.sh unpacks into ~/printer_data/config, so the flat zip
scattered macros/, tools/, menus/ ... next to printer.cfg while the
package itself stayed .133. Nothing "failed" - the unpack reported ok,
the version check happily printed the old version.

Why no test saw it: r110_setup_sim builds its update zips the CORRECT
way (with the prefix), so every battery ever ran against well-formed
zips. The release artifact itself was never validated.

This check closes the class:
  1. SELF-TEST   - three fixture zips (correct / flat / stale-version)
                   prove the detector works, everywhere, no repo needed.
  2. REPO        - macros/01_state.cfg variable_version must equal
                   tools/r2_postproc.py POSTPROC_RELEASE (the .134 zip
                   at least had consistent versions - but if these two
                   ever drift, every display would lie).
  3. RELEASE     - every klipper-e3-r2d2-UPDATE-*.zip (in ../releases,
                   or given via --zip PATH) must carry the package
                   folder prefix, the three load-bearing files, and its
                   INTERNAL versions (macro + daemon) must match the
                   version in its own FILENAME.

Exit code is the verdict (0 = all green).
"""
import os
import re
import sys
import glob
import zipfile
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
PREFIX = 'klipper-e3-r2d2/'

CHECKS = []
FAILS = []


def ok(msg):
    CHECKS.append(msg)
    print('  [ok]  ' + msg)


def fail(msg):
    FAILS.append(msg)
    CHECKS.append(msg)
    print('  [FAIL] ' + msg)


def check(cond, msg):
    (ok if cond else fail)(msg)
    return cond


# ---------------------------------------------------------------- helpers --
def zip_versions(zpath):
    """(is_flat, macro_version, daemon_release, names) of a zip - or None."""
    try:
        zf = zipfile.ZipFile(zpath)
    except Exception as e:
        print('  [FAIL] cannot open zip: %s (%s)' % (zpath, e))
        return None
    names = zf.namelist()
    flat = not all(n.startswith(PREFIX) for n in names)

    def grab(suffix, pat):
        for n in names:
            if n.startswith(PREFIX) and n.endswith(suffix):
                try:
                    m = re.search(pat, zf.read(n).decode('utf-8', 'replace'))
                except Exception:
                    return None
                if m:
                    return m.group(1)
        return None

    macro = grab('macros/01_state.cfg', r"variable_version:\s*'([^']+)'")
    daemon = grab('tools/r2_postproc.py', r"POSTPROC_RELEASE\s*=\s*'([^']+)'")
    return flat, macro, daemon, names


def check_release_zip(zpath):
    print('  zip: ' + os.path.basename(zpath))
    base = os.path.basename(zpath)
    fn = re.search(r'(R2-[0-9-]+\.[0-9]+[a-z]*)', base)
    if not fn:
        fail('%s: no R2-...NNN version in the filename' % base)
        return
    fnv = fn.group(1)
    r = zip_versions(zpath)
    if r is None:
        return
    flat, macro, daemon, names = r
    check(not flat, '%s: every entry under %s (not flat)' % (base, PREFIX))
    if flat:
        # the rest would only pile on - report the one real disease
        return
    for req in ('macros/01_state.cfg', 'update.sh', 'tools/r2_postproc.py'):
        check(PREFIX + req in names, '%s: contains %s' % (base, req))
    check(macro == fnv, '%s: macro version inside (%s) == filename (%s)'
          % (base, macro, fnv))
    # the daemon stamp may carry a trailing annotation (the .129a hotfix
    # shipped POSTPROC_RELEASE = 'R2-...129a (R170a)') - compare the
    # version TOKEN, not the string formatting
    dtok = re.search(r'(R2-[0-9-]+\.[0-9]+[a-z]*)', daemon or '')
    check(bool(dtok) and dtok.group(1) == fnv,
          '%s: daemon POSTPROC_RELEASE inside (%s) == filename (%s)'
          % (base, dtok.group(1) if dtok else daemon, fnv))


# ------------------------------------------------------------- 1) selftest --
def selftest():
    print('== 1) detector self-test (fixture zips) ==')
    d = tempfile.mkdtemp(prefix='r199_')

    def build(name, prefix, macro_v, daemon_v):
        z = os.path.join(d, name)
        with zipfile.ZipFile(z, 'w') as zf:
            body_state = "variable_version: '%s'\n" % macro_v
            body_daemon = "POSTPROC_RELEASE = '%s'\n" % daemon_v
            zf.writestr(prefix + 'macros/01_state.cfg', body_state)
            zf.writestr(prefix + 'tools/r2_postproc.py', body_daemon)
            zf.writestr(prefix + 'update.sh', '#!/usr/bin/env bash\ntrue\n')
        return z

    good = build('klipper-e3-r2d2-UPDATE-R2-2077-01-01.99.zip', PREFIX,
                 'R2-2077-01-01.99', 'R2-2077-01-01.99')
    flat = build('klipper-e3-r2d2-UPDATE-R2-2077-01-01.98.zip', '',
                 'R2-2077-01-01.98', 'R2-2077-01-01.98')
    stale = build('klipper-e3-r2d2-UPDATE-R2-2077-01-01.97.zip', PREFIX,
                  'R2-2077-01-01.96', 'R2-2077-01-01.96')

    r = zip_versions(good)
    check(r is not None and not r[0], 'detector: correct zip -> not flat')
    check(r is not None and r[1] == 'R2-2077-01-01.99' and r[2] == 'R2-2077-01-01.99',
          'detector: correct zip -> versions readable')
    r = zip_versions(flat)
    check(r is not None and r[0], 'detector: flat zip -> flagged flat')
    r = zip_versions(stale)
    fnv = 'R2-2077-01-01.97'
    check(r is not None and not r[0] and r[1] != fnv,
          'detector: stale-version zip -> version mismatch visible')


# ---------------------------------------------------------------- 2) repo --
def repo_check():
    print('== 2) repo version consistency ==')
    state = os.path.join(REPO, 'macros', '01_state.cfg')
    daemon = os.path.join(REPO, 'tools', 'r2_postproc.py')
    if not (os.path.isfile(state) and os.path.isfile(daemon)):
        print('  [i] not run from the repo - skipped')
        return
    mv = re.search(r"variable_version:\s*'([^']+)'", open(state).read())
    dv = re.search(r"POSTPROC_RELEASE\s*=\s*'([^']+)'", open(daemon).read())
    check(mv is not None and dv is not None,
          'repo: both version stamps parse (macro + daemon)')
    if mv and dv:
        check(mv.group(1) == dv.group(1),
              'repo: variable_version (%s) == POSTPROC_RELEASE (%s)'
              % (mv.group(1), dv.group(1)))


# ------------------------------------------------------------- 3) releases --
def release_check(paths):
    print('== 3) release zips ==')
    for z in paths:
        check_release_zip(z)


def main():
    args = [a for a in sys.argv[1:] if a != '--zip']
    selftest()
    repo_check()
    if args:
        release_check([os.path.abspath(a) for a in args if os.path.isfile(a)])
    else:
        rel = os.path.join(os.path.dirname(REPO), 'releases')
        zips = sorted(glob.glob(os.path.join(rel, 'klipper-e3-r2d2-UPDATE-*.zip')))
        if zips:
            print('  (scanning %s)' % rel)
            release_check(zips)
        else:
            print('  [i] no release zips found (%s) - self-test + repo check only'
                  % rel)
    print()
    print('R199 ZIP CHECK: %d checks, %d FAIL' % (len(CHECKS), len(FAILS)))
    sys.exit(1 if FAILS else 0)


if __name__ == '__main__':
    main()
