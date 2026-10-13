#!/usr/bin/env bash
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Raz-666 and contributors
# =====================================================================================
#  update.sh - R2 macro system update helper (.50+)
#
#  THE SHORT WAY since .50 - two steps, that is all:
#    1) upload the UPDATE zip in Mainsail into the CONFIG folder
#       (the one where printer.cfg lives - NOT inside the klipper-e3-r2d2
#       subfolder; the upload button / drag&drop in the config file list)
#    2) SSH, one command:
#         bash ~/printer_data/config/klipper-e3-r2d2/update.sh
#       It finds the newest uploaded zip, unzips it OVER the old package
#       folder, checks everything and restarts Klipper + the r2-postproc
#       watcher. variables.cfg and printer.cfg are never touched.
#
#  Manual alternative (identical result):
#         cd ~/printer_data/config
#         unzip -o klipper-e3-r2d2-UPDATE-R2-2026-09-07.50.zip
#         bash klipper-e3-r2d2/update.sh
#
#  Options:  --force      also unpack an OLDER zip (downgrade)
#            --unpacked   internal flag (do not search for zips again)
#
#  R108: the update ALSO asks whether to KEEP or CHANGE the LED settings and
#  the hardware profile (r2_hardware.cfg), shows the moonraker object-
#  processing state with an offer to change it, and re-applies the LED
#  layout to the freshly unpacked 03_leds.cfg. Backup FIRST + verified
#  (cmp) before anything is touched - a failed verify aborts.
# =====================================================================================
set -u
DIR="$(cd "$(dirname "$0")" && pwd)"
CFG="${HOME}/printer_data/config/printer.cfg"
PKG_REL="klipper-e3-r2d2"
MOONRAKER="http://127.0.0.1:7125"
FORCE=0
[ "${1:-}" = "--force" ] && FORCE=1

echo "== R2 update helper =="

CFG_DIR=""
if [ -f "${CFG}" ]; then
    CFG_DIR="$(cd "$(dirname "${CFG}")" && pwd)"
fi

# --- 0) is THIS folder the one Klipper includes? ------------------------------------
if [ -z "${CFG_DIR}" ]; then
    echo "[!] printer.cfg not found at ${CFG}"
    echo "    (edit this script's CFG= line if your config lives elsewhere)"
else
    if grep -q "\[include ${PKG_REL}/macros/01_state.cfg\]" "${CFG}"; then
        EXPECTED="${CFG_DIR}/${PKG_REL}"
        if [ "${DIR}" != "${EXPECTED}" ]; then
            echo "[!] WRONG LOCATION: this script runs in"
            echo "        ${DIR}"
            echo "    but your printer.cfg includes the package at"
            echo "        ${EXPECTED}"
            echo "    -> unzip the zip THERE so it overwrites the old folder:"
            echo "         cd ${CFG_DIR}"
            echo "         unzip -o /path/to/klipper-e3-r2d2-UPDATE-R2-*.zip"
            echo "    then re-run:  bash ${EXPECTED}/update.sh"
            exit 1
        fi
        echo "[ok] this is the included package folder: ${DIR}"
    else
        echo "[i] no '[include ${PKG_REL}/macros/01_state.cfg]' found in ${CFG} yet"
        echo "    (first install? the include check below tells you what to add)"
    fi
fi

# --- 0.5) BACKUP FIRST (R108) - before the zip overwrites anything: every
#     file this run might change gets a copy VERIFIED 1:1 (cmp). Runs on the
#     first invocation only (--unpacked re-runs skip it - by then the files
#     are the NEW ones and the backup of the old ones is already made).
R2_LIB_LOADED=0
if [ "${1:-}" != "--unpacked" ] && [ -n "${CFG_DIR}" ] \
   && [ -f "${DIR}/tools/r2_setup_lib.sh" ]; then
    . "${DIR}/tools/r2_setup_lib.sh"
    r2_lib_init "${CFG_DIR}" "${DIR}" "$(date +%Y%m%d-%H%M%S)" 0 "sudo"
    if ! r2_backup_candidates "${CFG_DIR}/r2_backups/$(date +%Y%m%d-%H%M%S)-update"; then
        echo "[!] update ABORTED by the backup rule - nothing was unpacked or modified"
        exit 1
    fi
    R2_LIB_LOADED=1
fi

# --- 1) unzip an uploaded UPDATE zip over the old folder (NEW in .50) ----------------
if [ "${1:-}" != "--unpacked" ] && [ -n "${CFG_DIR}" ]; then
    CUR="$(sed -n "s/^[[:space:]]*variable_version: *'\(R2-[0-9-]*\.[0-9]*\)'.*/\1/p" \
           "${DIR}/macros/01_state.cfg" 2>/dev/null | head -1)"
    CUR_N="$(printf '%s' "${CUR:-}" | sed -n 's/.*\.\([0-9]*\)$/\1/p')"
    CUR_N="${CUR_N:-0}"
    BEST=""; BEST_N=0
    for Z in "${CFG_DIR}"/klipper-e3-r2d2-UPDATE-R2-*.zip "${DIR}"/klipper-e3-r2d2-UPDATE-R2-*.zip; do
        [ -f "${Z}" ] || continue
        ZN="$(basename "${Z}" | sed -n 's/.*\.\([0-9]*\)\.zip$/\1/p')"
        [ -n "${ZN}" ] || continue
        if [ "${ZN}" -gt "${BEST_N}" ]; then BEST="${Z}"; BEST_N="${ZN}"; fi
    done
    if [ -n "${BEST}" ]; then
        echo "[i] uploaded update zip found: $(basename "${BEST}")  (installed: ${CUR:-unknown})"
        if [ "${BEST_N}" -lt "${CUR_N}" ] && [ "${FORCE}" -eq 0 ]; then
            echo "[!] that zip is OLDER than the installed version - not unpacking it."
            echo "    to downgrade anyway:  bash \"${DIR}/update.sh\" --force"
        else
            echo "[i] unpacking over ${CFG_DIR}/${PKG_REL} ..."
            OK=0
            if command -v unzip >/dev/null 2>&1; then
                (cd "${CFG_DIR}" && unzip -o "${BEST}") || OK=1
            else
                echo "[i] 'unzip' is not installed - using the python3 fallback"
                (cd "${CFG_DIR}" && python3 -m zipfile -e "${BEST}" .) || OK=1
            fi
            if [ "${OK}" -ne 0 ]; then
                echo "[!] unpacking FAILED - nothing was restarted, fix the zip first."
                exit 1
            fi
            echo "[ok] package files replaced - continuing with the NEW update.sh"
            # the unpack just replaced THIS running script file -> switch to the
            # new one (bash would otherwise read garbage at the old byte offset)
            exec bash "${CFG_DIR}/${PKG_REL}/update.sh" --unpacked
        fi
    else
        echo "[i] no klipper-e3-r2d2-UPDATE-R2-*.zip found in ${CFG_DIR}"
        echo "    (to update: upload the new zip in Mainsail into the config folder"
        echo "     next to printer.cfg, then run this script again)"
    fi
fi

# --- 2) the include list --------------------------------------------------------------
if [ -z "${CFG_DIR}" ]; then
    echo "[!] skipping the include check (no printer.cfg)"
else
    MISSING=""
    for f in 01_state 02_sounds 03_leds 04_notify 05_materials 06_temp_controls \
             07_start_confirm 08_print_start_stop 09_pause_filament 10_live_tuning \
             11_gantry_sync 12_maintenance 13_system 14_kamp 15_objects 16_labels 17_generator; do
        if ! grep -q "${PKG_REL}/macros/${f}.cfg" "${CFG}"; then
            MISSING="${MISSING} ${f}"
        fi
    done
    if [ -z "${MISSING}" ]; then
        echo "[ok] all 17 macro files are included in printer.cfg"
    else
        echo "[!] MISSING include lines for:${MISSING}"
        echo "    add at the end of ${CFG}:"
        for m in ${MISSING}; do
            echo "        [include ${PKG_REL}/macros/${m}.cfg]"
        done
        echo "    then re-run this script."
        exit 1
    fi
fi

# --- 3) version check ------------------------------------------------------------------
V="$(sed -n "s/^[[:space:]]*variable_version: *'\(R2-[0-9-]*\.[0-9]*\)'.*/\1/p" \
       "${DIR}/macros/01_state.cfg" 2>/dev/null | head -1)"
echo "[i] package version: ${V:-unknown}"

# --- 4) sanity: the file that halted .47/.48 must be clean ------------------------------
if grep -q 'variable_charset:.*#' "${DIR}/macros/16_labels.cfg" 2>/dev/null; then
    echo "[!] DANGER: variable_charset still contains a '#' - Klipper would halt!"
    echo "    this folder is NOT the .49+ package - re-unzip the current zip."
    exit 1
fi
echo "[ok] no '#' in variable_charset (the .47/.48 boot-blocker is fixed here)"

# --- 4b) R108: LED settings + hardware profile - keep or change? -----------------------
#     The unpack just replaced macros/03_leds.cfg (effect index ranges back
#     to the 1-4 default) - the profile values are re-applied right after.
if [ -f "${DIR}/tools/r2_setup_lib.sh" ]; then
    [ "${R2_LIB_LOADED}" = "0" ] && {
        . "${DIR}/tools/r2_setup_lib.sh"
        r2_lib_init "${CFG_DIR:-${HOME}/printer_data/config}" "${DIR}" "$(date +%Y%m%d-%H%M%S)" 0 "sudo"
        R2_LIB_LOADED=1
    }
    if [ -f "$(r2_hwfile)" ]; then
        echo "[i] hardware profile: $(r2_hwfile)"
        r2_hw_read
        for _k in bed_min_x bed_max_x bed_min_y bed_max_y led_type led_section led_status_n led_bed_n led_nozzle_split; do
            [ -n "${R2_HW[${_k}]:-}" ] && printf '      %-16s %s\n' "${_k}:" "${R2_HW[${_k}]}"
        done
        r2_ask "Keep the current LED + hardware settings?" y
        if [ "${R2_YN}" = "y" ]; then
            r2_apply_led_layout
            echo "[ok] LED layout re-applied to the freshly unpacked 03_leds.cfg"
        else
            r2_hw_wizard
            r2_led_wizard
        fi
    else
        echo "[i] no r2_hardware.cfg yet (pre-R108 install or Ender-3 defaults)"
        r2_ask "Run the hardware + LED wizard now?" n
        [ "${R2_YN}" = "y" ] && { r2_hw_wizard; r2_led_wizard; }
    fi
    r2_object_processing
fi

# --- 5) restart Klipper via Moonraker (works in the red config-error state too) --------
echo "[i] sending FIRMWARE_RESTART via Moonraker..."
SENT=1
if curl -s -f -m 10 -X POST "${MOONRAKER}/printer/firmware_restart" \
        -H 'Content-Type: application/json' -d '{}' >/dev/null 2>&1; then
    SENT=0
elif curl -s -f -m 10 -X POST "${MOONRAKER}/printer/gcode/script" \
        -H 'Content-Type: application/json' \
        -d '{"script": "FIRMWARE_RESTART"}' >/dev/null 2>&1; then
    SENT=0
fi
if [ "${SENT}" -eq 0 ]; then
    echo "[ok] FIRMWARE_RESTART sent - the LCD goes DARK for ~10-60 s,"
    echo "     the boot beep + 'R2 ready' confirm success. Check the console for"
    echo "     'Macro system OK: all 17 modules loaded and current (build ${V:-?})'"
else
    echo "[!] Moonraker unreachable - run FIRMWARE_RESTART in the Mainsail console yourself."
fi

# --- 6) restart the post-processor ------------------------------------------------------
echo "[i] restarting r2-postproc..."
# R133h: kill EVERY r2_postproc process first - a stale watcher from an
# older release (manually started once) survives a service restart and
# keeps pushing its OLD variables (field log .100: unquoted kit_sources
# push = 'Internal error on command:SAVE_VARIABLE' = shutdown mid-print)
# R133i: sudo FIRST - a root-cron / rc.local zombie runs as root and a
# plain user pkill cannot touch it (falls through silently)
(sudo -n pkill -f 'r2_postproc.py' 2>/dev/null || pkill -f 'r2_postproc.py' 2>/dev/null) && sleep 1
if sudo systemctl restart r2-postproc 2>/dev/null; then
    echo "[ok] r2-postproc restarted"
else
    echo "[!] could not restart r2-postproc (sudo?) - run:"
    echo "        sudo systemctl restart r2-postproc"
    echo "    check it is alive:   systemctl status r2-postproc --no-pager"
fi

# --- 7) hint: the environment wizard --------------------------------------------------
if [ -f "${DIR}/setup.sh" ]; then
    echo "[i] environment wizard available (service, KAMP, LED effects, RAM, swap):"
    echo "        bash ${DIR}/setup.sh        (--check = report only)"
fi

echo "== done. Happy printing! =="
