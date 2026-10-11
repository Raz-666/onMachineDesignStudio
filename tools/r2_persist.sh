#!/usr/bin/env bash
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Raz-666 and contributors
# =====================================================================================
#  r2_persist.sh - R2 hardware profile persister (R108)
#
#  Called from the macros via the shell-command extension:
#     RUN_SHELL_COMMAND CMD=R2_PERSIST PARAMS="led_status_n 3"
#
#  What it does:
#    1) rewrites  variable_<key>: <value>  in r2_hardware.cfg (the SECOND
#       variables file - printer-specific hardware values that survive a
#       reset of the normal variables.cfg)
#    2) led_status_n / led_bed_n ALSO regenerate the [led_effect] index
#       ranges in macros/03_leds.cfg - the effects are static Klipper
#       config, so the new layout applies after the next FIRMWARE_RESTART
#
#  Location independence: this script lives in <config>/klipper-e3-r2d2/tools/
#  and derives every path from its own position (same trick as the service
#  unit templating) - setup.sh only has to bake the absolute command path
#  into [gcode_shell_command R2_PERSIST] in r2_hardware.cfg.
#
#  Safety:
#    - KEY whitelist (nothing else is ever written)
#    - VALUE must be a plain number (no shell injection surface)
#    - r2_hardware.cfg gets a .r2bak sidecar backup BEFORE every edit
# =====================================================================================
set -u

PKG_DIR="$(cd "$(dirname "$0")/.." && pwd)"          # <config>/klipper-e3-r2d2
CFG_DIR="$(cd "${PKG_DIR}/.." && pwd)"               # <config>
HW="${CFG_DIR}/r2_hardware.cfg"
LEDS="${PKG_DIR}/macros/03_leds.cfg"

KEY="${1:-}"
VAL="${2:-}"

[ -z "${KEY}" ] && exit 0

# ---- whitelist: only known hardware keys --------------------------------------------
case "${KEY}" in
    bed_min_x|bed_max_x|bed_min_y|bed_max_y|bed_max_z|probe_x|probe_y|present_x|present_y|wipe_x|wipe_y|\
    led_status_n|led_bed_n|led_bed_on|led_bed_bright|led_nozzle_split)
        ;;
    *)
        echo "[R2_PERSIST] refusing unknown key: ${KEY}"
        exit 1
        ;;
esac

# ---- value must be a plain number ----------------------------------------------------
if ! printf '%s' "${VAL}" | grep -qE '^-?[0-9]+(\.[0-9]+)?$'; then
    echo "[R2_PERSIST] refusing non-numeric value: ${VAL}"
    exit 1
fi

if [ ! -f "${HW}" ]; then
    echo "[R2_PERSIST] ${HW} not found - run setup.sh (hardware wizard) first"
    exit 1
fi

# ---- 1) rewrite the variable line (backup first, verify after) -----------------------
cp "${HW}" "${HW}.r2bak"
sed -i "s|^variable_${KEY}:.*|variable_${KEY}: ${VAL}|" "${HW}"
# key was never there? append it right before the gcode: line of the macro
if ! grep -q "^variable_${KEY}: ${VAL}\$" "${HW}"; then
    sed -i "s|^gcode:|variable_${KEY}: ${VAL}\ngcode:|" "${HW}"
fi
if ! grep -q "^variable_${KEY}: ${VAL}\$" "${HW}"; then
    cp "${HW}.r2bak" "${HW}"          # restore - never leave a half-edit behind
    echo "[R2_PERSIST] edit failed - ${HW} restored from backup"
    exit 1
fi

# ---- 2) LED layout keys: regenerate the [led_effect] index ranges --------------------
if [ "${KEY}" = "led_status_n" ] || [ "${KEY}" = "led_bed_n" ]; then
    python3 - "${HW}" "${LEDS}" << 'R2PERSIST_PY'
import re, sys

hw_path, leds_path = sys.argv[1], sys.argv[2]

def hw_vars(path):
    vals = {}
    inside = False
    try:
        with open(path, errors='replace') as f:
            for l in f:
                ls = l.strip()
                if ls.startswith('[') and ls.endswith(']'):
                    inside = (ls[1:-1].strip().lower() == 'gcode_macro _r2_config')
                    continue
                if inside and ls.startswith('variable_') and ':' in ls:
                    k, v = ls[len('variable_'):].split(':', 1)
                    vals[k.strip()] = v.split('#')[0].strip().strip("'\"")
    except OSError:
        pass
    return vals

v = hw_vars(hw_path)
ltype = v.get('led_type', 'neopixel') or 'neopixel'
lsec  = v.get('led_section', 'printer_leds') or 'printer_leds'
nsec  = v.get('led_nozzle_section', 'nozzle_led') or 'nozzle_led'
sn    = max(0, int(float(v.get('led_status_n', 4) or 4)))
bn    = max(0, int(float(v.get('led_bed_n', 0) or 0)))
split = str(v.get('led_nozzle_split', '0') or '0') == '1'

try:
    with open(leds_path, errors='replace') as f:
        lines = f.read().split('\n')
except OSError:
    sys.exit(0)          # no LED macro file? nothing to regenerate

out = []
cur_eff = None
in_leds_value = False
in_split_comment = 0      # >0 while inside the commented r2_nozzle_on_split block
for l in lines:
    ls = l.lstrip()
    if ls.startswith('[led_effect ') and ls.endswith(']'):
        cur_eff = ls[1:-1].strip().split(None, 1)[1].strip()
        in_leds_value = False
        out.append(l)
        continue
    if cur_eff:
        if ls.startswith('leds:'):
            in_leds_value = True
            out.append(l)
            continue
        if in_leds_value:
            # this non-comment line is the leds VALUE - rewrite it
            if cur_eff == 'r2_nozzle_on':
                new = '%s:%s (%d)' % (ltype, lsec, sn + bn + 1)
            elif cur_eff == 'r2_nozzle_on_split':
                new = '%s:%s' % (ltype, nsec)
            else:
                new = '%s:%s (1-%d)' % (ltype, lsec, sn)
            indent = l[:len(l) - len(ls)]
            out.append(indent + new)
            in_leds_value = False
            continue
    # the commented-out split effect: uncomment when split is ON, keep
    # commented when OFF (idempotent both ways)
    if l.startswith('#[led_effect r2_nozzle_on_split]'):
        in_split_comment = 1
        out.append(l[1:] if split else l)
        continue
    if in_split_comment:
        if l.startswith('#') and ls.startswith('#'):
            out.append(l[1:] if split else l)
            if ls.startswith('#layers'):
                in_split_comment = 0
            continue
        in_split_comment = 0
    out.append(l)

with open(leds_path, 'w', errors='surrogateescape') as f:
    f.write('\n'.join(out))
R2PERSIST_PY
    echo "[R2_PERSIST] LED layout applied - FIRMWARE_RESTART activates the effect ranges"
fi
exit 0
