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
"$PYTHON" -m py_compile \
    tools/r2_postproc.py \
    tools/r2_postproc_next.py \
    tools/r2_cake.py \
    tools/r2_job_service.py \
    tools/r2_shadow.py \
    tools/r2_analysis.py \
    tools/r2_offline.py \
    tools/r2_sidecar.py \
    tools/gcode_re.py \
    tools/r2_machine.py \
    tools/menu_json_export.py \
    tools/make_calibration_pdf.py \
    tools/make_cakesplit_pdf.py \
    tools/build_review_bundle.py
echo '==== engine parity (lines 4+ byte-identical)'
"$PYTHON" -c "
p1 = open('tools/r2_postproc.py', 'rb').read().splitlines(True)
p2 = open('tools/r2_postproc_next.py', 'rb').read().splitlines(True)
assert p1[3:] == p2[3:], 'r2_postproc.py and r2_postproc_next.py diverged!'
print('OK:', len(p1), 'lines in strict parity')
"
for engine in active next; do
    for test in \
        test_image_pick_next.py \
        test_queue_next.py \
        test_process_guards.py \
        test_zscan_modes.py \
        test_stl_extrusion_state.py \
        test_object_bbox_modes.py \
        test_postproc_c1_c5_and_jobs.py
    do
        echo "==== $engine $test"
        R2_TEST_ENGINE="$engine" "$PYTHON" "tools/$test"
    done
done
for test in \
    test_r2_shadow.py \
    test_r2_analysis.py \
    test_r2_offline.py \
    test_r2_sidecar.py \
    test_gcode_re.py \
    test_shadow_analysis_audit_v2.py \
    test_r2_machine.py \
    test_cake_layers_h2.py \
    test_calibration_and_pause_guards.py \
    test_override_flow_regressions.py \
    test_review_bundle.py
do
    echo "==== $test"
    "$PYTHON" "tools/$test"
done
echo '==== golden unit'
"$PYTHON" analyse/test_golden_baseline.py
echo '==== golden active'
"$PYTHON" analyse/golden_baseline.py verify --engine stable
echo '==== golden next'
"$PYTHON" analyse/golden_baseline.py verify --engine next
echo '==== R81 golden check & V1 range check'
"$PYTHON" tools/r81_golden_check.py
"$PYTHON" tools/v1_range_cause_check.py
echo '==== dialect corpus, tag ladder & vocabulary'
"$PYTHON" tools/r110_gcode_dialects.py
"$PYTHON" tools/r190_tag_ladder.py
"$PYTHON" tools/r225_audit_fixes.py
"$PYTHON" tools/r229_vocab_rest.py
"$PYTHON" tools/r230_infill_patterns.py
echo '==== cfg, macro, doc, web-UI & crash guards'
"$PYTHON" tools/r165_doc_check.py
"$PYTHON" tools/r166_template_check.py
"$PYTHON" tools/r218_webui_check.py
"$PYTHON" tools/r255_homing_guard_check.py
"$PYTHON" tools/r257_crash_guard_check.py
echo '==== whitespace and patch validity'
git diff --check
echo 'PASS review checks; this is not an installation or hardware acceptance'
