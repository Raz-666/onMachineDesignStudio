#!/usr/bin/env bash
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
if sudo systemctl restart r2-postproc 2>/dev/null; then
    echo "[ok] r2-postproc restarted"
else
    echo "[!] could not restart r2-postproc (sudo?) - run:"
    echo "        sudo systemctl restart r2-postproc"
    echo "    check it is alive:   systemctl status r2-postproc --no-pager"
fi

echo "== done. Happy printing! =="
