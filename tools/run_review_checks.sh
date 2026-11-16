#!/usr/bin/env bash
# Offline review checks only. No printer, watcher, updater, or forbidden
# texture/shape test families are started. Use a Python with Jinja2 installed.
set -euo pipefail
cd "$(dirname "$0")/.."
PYTHON="${PYTHON:-python3}"
"$PYTHON" -c 'import jinja2; print("Jinja2", jinja2.__version__)'
command -v node >/dev/null || { echo 'Node required for Web evaluator test' >&2; exit 1; }
REFERENCE=analyse/klipper-referenz/gcode.py
if [[ ! -f "$REFERENCE" ]]; then
    echo 'Pinned Klipper parser missing; see analyse/klipper-referenz/QUELLE.md' >&2
    exit 1
fi
printf '%s  %s\n' a2bcd6949b4263f608eaa71ba1cdfb713553542b7b90de739241b624f06415ae "$REFERENCE" | sha256sum -c -
sha256sum -c backups/SHA256SUMS
"$PYTHON" -m py_compile tools/r2_postproc.py tools/r2_postproc_next.py tools/r2_shadow.py tools/r2_analysis.py tools/r2_offline.py tools/build_review_bundle.py
for engine in active next; do
    for test in test_image_pick_next.py test_queue_next.py test_process_guards.py test_zscan_modes.py test_stl_extrusion_state.py test_object_bbox_modes.py; do
        echo "==== $engine $test"
        R2_TEST_ENGINE="$engine" "$PYTHON" "tools/$test"
    done
done
for test in test_r2_shadow.py test_r2_analysis.py test_r2_offline.py test_override_flow_regressions.py test_review_bundle.py; do
    echo "==== $test"
    "$PYTHON" "tools/$test"
done
echo '==== golden unit'
"$PYTHON" analyse/test_golden_baseline.py
echo '==== golden active'
"$PYTHON" analyse/golden_baseline.py verify --engine stable
echo '==== golden next'
"$PYTHON" analyse/golden_baseline.py verify --engine next
echo '==== dialect corpus'
"$PYTHON" tools/r110_gcode_dialects.py
echo '==== crash guard static checks'
"$PYTHON" tools/r257_crash_guard_check.py
echo '==== whitespace and patch validity'
git diff --check
echo 'PASS review checks; this is not an installation or hardware acceptance'
