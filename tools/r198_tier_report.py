#!/usr/bin/env python3
"""r198_tier_report.py - the .135 TEST TIER RUNNER (user request: separate
tests for normal users, power users, developers, a hardcore deep test, a
real stress test + function test, and the generator/tool sweep).

One command, one table per tier. Every tier runs the batteries that model
its user; nothing is skipped silently - a missing tool file FAILS its row.

  python3 tools/r198_tier_report.py             # all tiers, full report
  python3 tools/r198_tier_report.py --tier normal
  python3 tools/r198_tier_report.py --tier hardcore
  python3 tools/r198_tier_report.py --list

Tier map (documented in DISPLAYS_WEB_UI.pdf / TESTANLEITUNG.md):
  normal    what a normal user touches: journeys, system files, docs
  power     setup, field fixes, coverage, audits, templates, stamps, serial
  developer render goldens, geometry, aircheck
  hardcore  the tagging ladder, the generator+tool sweep, spell lint, audit
  stress    the 46k-check endurance run
  function  end-to-end workflows + the printer/mode matrix
"""
import argparse
import os
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))

TIERS = {
    'normal': [
        ('r141_journeys', 'user journeys (LCD, Mainsail, console)'),
        ('systemtest', 'system files + install'),
        ('config_validator', 'config sanity'),
        ('r165_doc_check', 'documentation matches reality'),
    ],
    'power': [
        ('megatest', 'generators + chains end to end'),
        ('r110_setup_sim', 'setup/update/check scenarios'),
        ('r142_field_coverage', 'field-fix regression coverage'),
        ('r143_user_audit', 'user-facing audit'),
        ('r166_template_check', 'klipper-parse + jinja compile'),
        ('r168_stampcheck', 'stamp fit goldens'),
        ('r164_serial_budget', 'serial/timeout budget'),
    ],
    'developer': [
        ('macro_render_test', '1.910 menu/macro renders'),
        ('r81_golden_check', 'postproc output goldens'),
        ('r111_geom_test', 'geometry classifier'),
        ('r167_aircheck', 'generator bridge air scan'),
    ],
    'hardcore': [
        ('r190_tag_ladder', 'feature tagging, 5 levels + rules'),
        ('r197_gen_sweep', 'ALL generators x parameters + tools'),
        ('r225_audit_fixes', '.136w audit round: web refresh, Cura box, '
         'Mainsail meta vs moonraker, families vocabulary, stray tags'),
        ('r226_field_fixes', '.136x field round: KAMP polygon crash, '
         'gen_busy reconcile, klippy.log sections'),
        ('r227_reconcile_fix', '.136y hotfix: reconcile string-parse + '
         'latch, moonraker restart in update.sh'),
        ('r228_pause_storm', '.136z pause storm: watcher 3-tick follow, '
         'sensor grace, arm expiry, banner gate'),
        ('r229_vocab_rest', '.136aa vocabulary rest list: inert move '
         'annotations, purge class, infill patterns'),
        ('r199_zip_check', 'release-zip layout + version consistency'),
        ('audit_sweep', 'all-file audit sweep'),
        # r142_spell_lint stays OUT of the tiers on purpose: it is a hint
        # lint (word-form suggestions, ~113 benign suspects) - a gate would
        # cry wolf; run it manually when editing user-facing strings
    ],
    'stress': [
        ('r140_stress', 'stress: 46k checks, endurance'),
    ],
    'function': [
        ('r187_matrix', 'workflow matrix (printer modes)'),
        ('systemtest', 'system function'),
    ],
}

TIMEOUT = 1900


def run_one(tool, desc):
    path = os.path.join(HERE, tool + '.py')
    if not os.path.isfile(path):
        return (tool, desc, 'MISSING', 0.0, 'no such tool')
    t0 = time.time()
    try:
        r = subprocess.run([sys.executable, '-u', path],
                           capture_output=True, text=True, timeout=TIMEOUT,
                           cwd=os.path.dirname(HERE))
        out = (r.stdout + r.stderr).strip().split('\n')
        dt = time.time() - t0
        tail = out[-1][:110] if out else '(no output)'
        # the exit code IS the verdict - every battery exits 1 on any
        # FAIL (a tail regex would misread '0 FAIL' as a failure)
        ok = r.returncode == 0
        return (tool, desc, 'PASS' if ok else 'FAIL', dt, tail)
    except subprocess.TimeoutExpired:
        return (tool, desc, 'TIMEOUT', time.time() - t0, 'over %ds' % TIMEOUT)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--tier', choices=list(TIERS) + ['all'], default='all')
    ap.add_argument('--list', action='store_true')
    args = ap.parse_args()
    if args.list:
        for t, items in TIERS.items():
            print('%-9s %s' % (t, ', '.join(i[0] for i in items)))
        return 0
    tiers = list(TIERS) if args.tier == 'all' else [args.tier]
    n_ok = n_bad = 0
    for t in tiers:
        print('\n===== TIER: %s =====' % t.upper())
        rows = []
        for (tool, desc) in TIERS[t]:
            sys.stdout.write('  running %-20s %s ... ' % (tool, desc))
            sys.stdout.flush()
            r = run_one(tool, desc)
            rows.append(r)
            print('%s (%.0fs)' % (r[2], r[3]))
        print('\n  %-22s %-8s %-8s %s' % ('tool', 'result', 'secs', 'tail'))
        print('  ' + '-' * 100)
        for (tool, desc, st, dt, tail) in rows:
            print('  %-22s %-8s %-8.0f %s' % (tool, st, dt, tail))
            if st == 'PASS':
                n_ok += 1
            else:
                n_bad += 1
    print('\nR198 TIER REPORT: %d pass, %d fail (tiers: %s)'
          % (n_ok, n_bad, ', '.join(tiers)))
    return 1 if n_bad else 0


if __name__ == '__main__':
    sys.exit(main())
