#!/usr/bin/env python3
"""R234 (.136ae) field check: string art pick save + RAM gate + --git updates.

Field log 2026-11-09 (on .136ad, right after the odometer fix landed):
  !! Malformed command 'SAVE_VARIABLE VARIABLE=stringart_imgwh
     VALUE="\\"1024x1024\\"" if dim != '' else '""''
  [queue] StringArt waits: only 88MB RAM free, image builds want 110MB

Two bugs, one round:
  A) STRINGART_PICK wrote the VALUE of stringart_imgwh with a Python-style
     conditional OUTSIDE the jinja braces - the literal text
     " if dim != '' else '\"\"'" rode along on every photo pick (2x per
     pick), klipper rejected the command and stringart_imgwh NEVER saved.
     The LCD's '(no img)' label and every imgwh consumer ran on stale data.
  B) The queue's RAM floor for string art was still 110MB (R223, when
     full-res photo decodes really died there) - the R232 planner peaks
     at a MEASURED ~37MB, so builds waited for a Pi restart although
     88MB free were plenty. Now 64MB (litho/colorpic keep 110 - never
     re-measured).

Plus R234's headline feature: update.sh --git (GitHub updates, no zip).
This audit proves all three:

  A) renders the REAL STRINGART_PICK body through a klipper-EXACT jinja
     environment (single braces, NO trim_blocks - the big harness merges
     lines klipper keeps apart, error class 172) and runs the emitted
     SAVE_VARIABLE lines through klipper's OWN parsing chain:
     shlex(posix=True, whitespace_split, commenters '#;') ->
     ast.literal_eval. The value must roundtrip to the picked 'WxH'.
     The OLD field-log line is fed through the same chain as a negative
     control (it does not survive it - proving the detector bites).
  B) static pins: string art floor 64, litho/colorpic 110 (count), the
     wait notice still names the per-job number.
  C) END-TO-END git updates with throwaway sandboxes (HOME redirected,
     a bare repo plays GitHub): update path (.136ad clone -> origin has
     .136ae -> pulled + full choreography), up-to-date path, local-changes
     refusal, --git --force, not-a-repo error, and the downgrade guard
     (an origin BEHIND the install is refused - odometer rule, R233).

Run:  python3 tools/r234_field_check.py
"""
import ast
import os
import re
import shlex
import subprocess
import sys
import tempfile
import shutil

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REPO = HERE
PASS = 0
FAIL = 0


def ok(msg):
    global PASS
    PASS += 1
    print('  [ok] %s' % msg)


def bad(msg):
    global FAIL
    FAIL += 1
    print('  [!!] FAIL: %s' % msg)


def check(name, cond, info=''):
    if cond:
        ok(name)
    else:
        bad('%s%s' % (name, (' (%s)' % info) if info else ''))


# ===========================================================================
print('--- A) STRINGART_PICK: the imgwh save survives klipper\'s parser ------')

from jinja2 import Environment, BaseLoader   # noqa: E402

# klipper's gcode_macro.py builds exactly this - trim_blocks stays OFF
env = Environment(loader=BaseLoader(),
                  block_start_string='{%', block_end_string='%}',
                  variable_start_string='{', variable_end_string='}',
                  comment_start_string='{#', comment_end_string='#}')


def _act_stub(*a, **k):
    return ''


env.globals['action_respond_info'] = _act_stub
env.globals['action_raise_error'] = _act_stub
env.globals['action_call_remote_method'] = _act_stub

cfg = open(os.path.join(REPO, 'macros', '17_generator.cfg'),
           encoding='utf-8').read()
m = re.search(r'^\[gcode_macro STRINGART_PICK\]\n.*?^gcode:\n(.*?)(?=^\[)',
              cfg, re.S | re.M)
body = m.group(1) if m else None
check('A0: STRINGART_PICK body found in 17_generator.cfg', body is not None)
if not body:
    sys.exit(1)

_tpl = env.from_string(body)


def klippy_parse(line):
    """klipper's extended-gcode parameter chain: shlex -> k=v pairs."""
    lex = shlex.shlex(line, posix=True)
    lex.whitespace_split = True
    lex.commenters = '#;'
    toks = list(lex)
    pars = {}
    for t in toks:
        if '=' in t:
            k, v = t.split('=', 1)
            pars[k] = v
    return pars, toks


def render_pick(files, dims, index):
    # R246: the image list lives in the _SDM RAM mirror, not in
    # save_variables - the mock carries both worlds like the real printer
    printer = {'save_variables': {'variables': {
        'stringart_shape': 1, 'stringart_arl': 1, 'stringart_w': 102}},
        'gcode_macro _SDM': {
            'litho_files': files, 'litho_dims': dims}}
    old = env.globals.get('params')
    env.globals['params'] = {'INDEX': str(index)}
    try:
        out = _tpl.render(printer=printer)
    finally:
        env.globals['params'] = old
    return out


def save_line(out, var):
    for ln in out.splitlines():
        s = ln.strip()
        if s.startswith('SAVE_VARIABLE VARIABLE=%s ' % var):
            return s
    return None


# A1: the field-log case - a photo with header dims gets a CLEAN save
out = render_pick(['Bun4.jpg', 'Bun2.jpg'], ['1024x1024', '1920x1080'], 1)
# comments in the macro body ride along as gcode comment lines - the
# malformed-class check must look at CODE lines only
_code = '\n'.join(l for l in out.splitlines()
                  if not l.strip().startswith('#'))
check('A1: no literal python conditional rides along any more',
      ' if dim != ' not in _code and "else '\"\"'" not in _code)
ln = save_line(out, 'stringart_imgwh')
check('A1: the imgwh SAVE_VARIABLE line exists', ln is not None, ln)
pars, toks = klippy_parse(ln)
val = ast.literal_eval(pars['VALUE'])
check("A1: imgwh VALUE roundtrips through shlex+literal_eval -> '1920x1080'",
      val == '1920x1080', repr(val))
check('A1: the command parses as the name + exactly VARIABLE+VALUE '
      '(nothing trailing)',
      len(toks) == 3 and toks[0] == 'SAVE_VARIABLE'
      and set(pars) == {'VARIABLE', 'VALUE'}, str(toks))
ln_src = save_line(out, 'stringart_src')
pars_src, toks_src = klippy_parse(ln_src)
check("A1: sibling stringart_src still roundtrips -> 'Bun2.jpg'",
      ast.literal_eval(pars_src['VALUE']) == 'Bun2.jpg')
ln_ar = save_line(out, 'stringart_ar')
pars_ar, _ = klippy_parse(ln_ar)
check('A1: stringart_ar saved as a plain float literal',
      isinstance(ast.literal_eval(pars_ar['VALUE']), float))

# A2: legacy state without dims - the empty fallback must be a CLEAN save
out2 = render_pick(['Bun4.jpg', 'Bun2.jpg'], [], 1)
_code2 = '\n'.join(l for l in out2.splitlines()
                   if not l.strip().startswith('#'))
check('A2: no malformed text in the no-dims render either',
      ' if dim != ' not in _code2)
ln2 = save_line(out2, 'stringart_imgwh')
pars2, toks2 = klippy_parse(ln2)
check("A2: legacy pick (no dims) saves an EMPTY imgwh",
      ast.literal_eval(pars2['VALUE']) == '' and len(toks2) == 3,
      '%r %r' % (pars2.get('VALUE'), toks2))

# A3: negative control - the OLD field-log line dies in the same parser
OLD = ('SAVE_VARIABLE VARIABLE=stringart_imgwh '
       'VALUE="\\"1024x1024\\"" if dim != \'\' else \'""\'')
pars3, toks3 = klippy_parse(OLD)
check('A3: the OLD field-log line does NOT parse as VARIABLE+VALUE alone '
      '(this is what klipper rejected)',
      len(toks3) > 2 or set(pars3) != {'VARIABLE', 'VALUE'}, str(toks3))

# ===========================================================================
print('--- B) the queue RAM floor: string art 64MB, litho/colorpic 110 -------')
src = open(os.path.join(REPO, 'tools', 'r2_postproc.py'),
           encoding='utf-8').read()
check('B1: string art job spawns with ram_min=64 (R234)',
      'ram_min=64)' in src and 'MEASURED ~37MB peak' in src)
check('B2: litho + colorpic + stencil keep their 110MB floor '
      '(image-class jobs, not re-measured)',
      src.count('ram_min=110') == 3)
check('B3: the wait notice still names the per-job floor',
      'image builds ' in src and 'want %dMB - a PI restart frees it ' in src)
check('B4: the queue comment documents the R234 split',
      'string art only needs 64MB since the' in src)

# ===========================================================================
print('--- C) update.sh --git: GitHub updates without a zip -------------------')
upd = open(os.path.join(REPO, 'update.sh'), encoding='utf-8').read()
check('C0: --git mode exists + hands over to the full choreography',
      '"${1:-}" = "--git"' in upd
      and 'exec bash "${DIR}/update.sh" --unpacked' in upd)
check('C0: git downgrade guard runs on the odometer (r2_sfx_val)',
      'r2_sfx_val "${GIT_NEW_S:-}"' in upd)
check('C0: local modifications are protected (stash hint, --force override)',
      'git -C ${DIR} stash' in upd and '--git --force' in upd)
check('C0: --force is seen in ANY argument position',
      'for _a in ${@+"$@"}' in upd)
check('C0: the no-zip hint points at --git + GITHUB.md',
      'straight from your clone' in upd
      and os.path.isfile(os.path.join(REPO, 'GITHUB.md')))


def sh(cmd, cwd=None, env=None, inp=None, timeout=300):
    e = dict(os.environ)
    if env:
        e.update(env)
    return subprocess.run(cmd, shell=True, cwd=cwd, env=e,
                          input=inp, capture_output=True, text=True,
                          timeout=timeout)


NEED = ['git', 'bash', 'tar']
for t in NEED:
    if shutil.which(t) is None:
        print('  [!!] FAIL: tool %r missing - the E2E part cannot run' % t)
        sys.exit(1)

TMP = tempfile.mkdtemp(prefix='r234_')
try:
    # the last PRE---git stand: the PARENT of the commit that introduced
    # --git in update.sh (R234 = 0de9a7c, the .136ad zip era was b07fbdb).
    # NOTE: HEAD itself is --git-capable since .136ae - pinning HEAD here
    # made G0 silently test the wrong scenario (found in the R235 battery).
    _intro = sh("git log -S'--git' --reverse --format=%H -- update.sh",
                cwd=REPO).stdout.split()
    OLD_SHA = (sh('git rev-parse %s^' % _intro[0], cwd=REPO).stdout.strip()
               if _intro else
               sh('git rev-parse HEAD', cwd=REPO).stdout.strip())
    BR = sh('git branch --show-current', cwd=REPO).stdout.strip() or 'master'

    def ver_of(path):
        try:
            s = open(path, encoding='utf-8').read()
        except OSError:
            return None
        m2 = re.search(r"variable_version: '(R2-[\d-]+\.\d+[a-z]*)'", s)
        return m2.group(1) if m2 else None

    NEW_VER = ver_of(os.path.join(REPO, 'macros', '01_state.cfg'))

    # seed = full history + the CURRENT working tree. TWO commits on top:
    #   BASE_SHA - the tree as-is but with the version rolled back one
    #              step: a --git-CAPABLE install one release behind
    #              (update.sh already knows --git, version is older)
    #   SEED_SHA - the real tree: what GitHub will have once this release
    #              is pushed
    seed = os.path.join(TMP, 'seed')
    sh('git clone -q %r %r' % (REPO, seed))
    sh("git config user.email r234@test && git config user.name r234",
       cwd=seed)
    sh('(cd %r && tar cf - --exclude=.git --exclude=watch_state.json '
       '--exclude=watcher.lock --exclude=r2d2-repo.bundle '
       "--exclude='__pycache__' --exclude='*.pyc' .) | (cd %r && tar xf -)"
       % (REPO, seed))
    # R241+V1: versions are DATE-based (R2-YYYY-MM-DD.n) - the letter
    # odometer died with the scheme change. The honest predecessor is the
    # version the COMMITTED tree carries (the working tree is the new
    # release about to ship): read it from git, never hardcode a date.
    _prev = sh("git show HEAD:macros/01_state.cfg", cwd=REPO).stdout
    m3 = re.search(r"variable_version: '(R2-[\d-]+\.\d+[a-z]*)'", _prev)
    PREV_VER = (m3.group(1) if m3 else NEW_VER)
    if PREV_VER == NEW_VER:
        # release already committed - fall back one real commit
        _prev2 = sh("git show HEAD~1:macros/01_state.cfg", cwd=REPO).stdout
        m4 = re.search(r"variable_version: '(R2-[\d-]+\.\d+[a-z]*)'", _prev2)
        PREV_VER = (m4.group(1) if m4 else NEW_VER)
    st = os.path.join(seed, 'macros', '01_state.cfg')
    _txt = open(st, encoding='utf-8').read().replace(NEW_VER, PREV_VER)
    open(st, 'w', encoding='utf-8').write(_txt)
    sh('git add -A && git commit -qm "simulated base (git-capable, %s)"'
       % PREV_VER, cwd=seed)
    BASE_SHA = sh('git rev-parse HEAD', cwd=seed).stdout.strip()
    _txt2 = open(st, encoding='utf-8').read().replace(PREV_VER, NEW_VER)
    open(st, 'w', encoding='utf-8').write(_txt2)
    sh('git add -A && git commit -qm "simulated %s state"' % NEW_VER,
       cwd=seed)
    SEED_SHA = sh('git rev-parse HEAD', cwd=seed).stdout.strip()
    check('C1: seed built (base %s=%s, new %s=%s)'
          % (BASE_SHA[:7], PREV_VER, SEED_SHA[:7], NEW_VER),
          BASE_SHA != SEED_SHA
          and ver_of(st) == NEW_VER)

    bare = os.path.join(TMP, 'gh.git')            # plays GitHub
    sh('git init -q --bare %r' % bare)
    # the fake GitHub must serve the branch it was given: a bare repo's
    # HEAD stays on its init default (master/main) and a clone of it
    # would check out NOTHING (unborn HEAD) - update.sh then fetches the
    # default name and dies on a ref that was never pushed
    sh("git -C %r symbolic-ref HEAD refs/heads/%s" % (bare, BR))
    sh('git push -q %r %s:refs/heads/%s' % (bare, BR, BR), cwd=seed)
    bare_old = os.path.join(TMP, 'gh-old.git')    # plays a ROLLED-BACK GitHub
    sh('git init -q --bare %r' % bare_old)
    sh("git -C %r symbolic-ref HEAD refs/heads/%s" % (bare_old, BR))
    sh('git push -q %r %s:refs/heads/%s' % (bare_old, BASE_SHA, BR),
       cwd=os.path.join(TMP, 'seed'))

    def mk_sb(name):
        sb = os.path.join(TMP, name)
        cfgd = os.path.join(sb, 'home', 'printer_data', 'config')
        os.makedirs(cfgd)
        incs = ['01_state 02_sounds 03_leds 04_notify 05_materials '
                '06_temp_controls 07_start_confirm 08_print_start_stop '
                '09_pause_filament 10_live_tuning 11_gantry_sync '
                '12_maintenance 13_system 14_kamp 15_objects 16_labels '
                '17_generator 18_colorpic 19_bricks']
        for f in incs[0].split():
            with open(os.path.join(cfgd, 'printer.cfg'), 'a') as fh:
                fh.write('[include klipper-e3-r2d2/macros/%s.cfg]\n' % f)
        return sb, cfgd

    def run_git(sb, *args):
        pkg = os.path.join(sb, 'home', 'printer_data', 'config',
                           'klipper-e3-r2d2')
        return sh('bash %r/update.sh %s' % (pkg, ' '.join(args)),
                  env={'HOME': os.path.join(sb, 'home'), 'TERM': 'dumb'},
                  inp='')

    # G0: a PRE---git install (b07fbdb, the .136ad zip era) treats --git as
    # an unknown no-op argument - no crash, normal flow, nothing changes.
    # This is WHY GITHUB.md migrates by CLONING, not by running --git on
    # the old unzipped folder.
    sb0, cfgd0 = mk_sb('g0')
    sh('git clone -q %r %r' % (bare, os.path.join(cfgd0, 'klipper-e3-r2d2')))
    sh('git checkout -q -B %s %s' % (BR, OLD_SHA),
       cwd=os.path.join(cfgd0, 'klipper-e3-r2d2'))
    _v0 = ver_of(os.path.join(cfgd0, 'klipper-e3-r2d2', 'macros',
                              '01_state.cfg'))
    r = run_git(sb0, '--git')
    log = r.stdout + r.stderr
    check('G0: pre---git update.sh ignores --git WITHOUT crashing',
          r.returncode == 0 and '== done. Happy printing! ==' in log
          and 'fetching origin' not in log)
    got0 = ver_of(os.path.join(cfgd0, 'klipper-e3-r2d2', 'macros',
                               '01_state.cfg'))
    check('G0: the old install stays on its version (clone to migrate!)',
          got0 == _v0 and got0 != NEW_VER, '%s -> %s' % (_v0, got0))

    # G1: the update path - --git-capable clone one release behind, origin
    # has the new state -> fetch + reset + full choreography
    sb, cfgd = mk_sb('g1')
    sh('git clone -q %r %r' % (bare, os.path.join(cfgd, 'klipper-e3-r2d2')))
    sh('git reset -q --hard %s' % BASE_SHA,
       cwd=os.path.join(cfgd, 'klipper-e3-r2d2'))
    r = run_git(sb, '--git')
    log = r.stdout + r.stderr
    check('G1: exit 0', r.returncode == 0, log[-300:])
    check('G1: fetch + move announced',
          'fetching origin %s' % BR in log and 'updating ' in log, log[-300:])
    check('G1: package reset to origin, NEW update.sh continues',
          'package files are at origin' in log
          and 'continuing with the NEW update.sh' in log)
    check('G1: full choreography ran to the end',
          '== done. Happy printing! ==' in log)
    got = ver_of(os.path.join(cfgd, 'klipper-e3-r2d2', 'macros',
                              '01_state.cfg'))
    check('G1: installed version is now %s' % NEW_VER, got == NEW_VER, got)
    check('G1: the clone stays a git repo (future --git runs)',
          os.path.isdir(os.path.join(cfgd, 'klipper-e3-r2d2', '.git')))

    # G2: up to date - safe re-run with the full choreography
    r = run_git(sb, '--git')
    log = r.stdout + r.stderr
    check('G2: exit 0 + "already up to date"',
          r.returncode == 0 and 'already up to date' in log)
    check('G2: the choreography runs anyway (migration safety)',
          '== done. Happy printing! ==' in log)

    # G3: local modifications refuse (without --force)
    statef = os.path.join(cfgd, 'klipper-e3-r2d2', 'macros', '01_state.cfg')
    with open(statef, 'a') as fh:
        fh.write('# local edit\n')
    r = run_git(sb, '--git')
    log = r.stdout + r.stderr
    check('G3: local changes block the update + stash hint',
          r.returncode != 0 and 'LOCAL changes' in log
          and 'stash' in log)
    check('G3: nothing was reset (version file still carries the edit)',
          '# local edit' in open(statef).read())

    # G4: --git --force overrides
    r = run_git(sb, '--git', '--force')
    log = r.stdout + r.stderr
    check('G4: --git --force proceeds (both flags seen)',
          r.returncode == 0 and 'overwriting the local changes' in log
          and '== done. Happy printing! ==' in log)
    check('G4: the edit is gone (reset to origin state)',
          '# local edit' not in open(statef).read())

    # G5: not a git repository (the plain unzipped folder)
    sb5, cfgd5 = mk_sb('g5')
    os.makedirs(os.path.join(cfgd5, 'klipper-e3-r2d2'), exist_ok=True)
    sh('(cd %r && tar cf - --exclude=.git --exclude=watch_state.json '
       '--exclude=watcher.lock --exclude=r2d2-repo.bundle '
       "--exclude='__pycache__' --exclude='*.pyc' .) | (cd %r && tar xf -)"
       % (REPO, os.path.join(cfgd5, 'klipper-e3-r2d2')))
    r = run_git(sb5, '--git')
    log = r.stdout + r.stderr
    check('G5: a non-clone folder gets a clear error + GITHUB.md pointer',
          r.returncode != 0 and 'not a git repository' in log
          and 'GITHUB.md' in log)

    # G6: the downgrade guard - origin BEHIND the installed version
    sb6, cfgd6 = mk_sb('g6')
    sh('git clone -q %r %r' % (bare, os.path.join(cfgd6, 'klipper-e3-r2d2')))
    sh('git remote set-url origin %r' % bare_old,
       cwd=os.path.join(cfgd6, 'klipper-e3-r2d2'))
    r = run_git(sb6, '--git')
    log = r.stdout + r.stderr
    check('G6: a rolled-back origin is refused (odometer rule)',
          r.returncode != 0 and 'origin is OLDER' in log
          and 'Nothing was changed' in log)
    got6 = ver_of(os.path.join(cfgd6, 'klipper-e3-r2d2', 'macros',
                               '01_state.cfg'))
    check('G6: the installed files really were not touched', got6 == NEW_VER,
          got6)
    r = run_git(sb6, '--git', '--force')
    log = r.stdout + r.stderr
    check('G6: --force pulls the older state when asked knowingly',
          r.returncode == 0 and 'pulling the OLDER origin state' in log)
finally:
    shutil.rmtree(TMP, ignore_errors=True)

print()
print('R234 FIELD CHECK: %d pass, %d fail' % (PASS, FAIL))
sys.exit(1 if FAIL else 0)
