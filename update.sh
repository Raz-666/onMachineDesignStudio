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
#  R199 (.134 field report): the .134 update zip was built FLAT (no
#  klipper-e3-r2d2/ top-level folder) - unpacking scattered macros/, tools/
#  ... next to printer.cfg and the package itself stayed .133 ("after the
#  update it still shows the old version"). update.sh now REFUSES a zip
#  without the package folder BEFORE unpacking anything, and warns when it
#  finds the remains of the flat .134 zip in the config folder.
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

# R199: list the entries of a zip (unzip when present, python3 fallback)
zip_list() {
    if command -v unzip >/dev/null 2>&1; then
        unzip -Z1 "$1" 2>/dev/null
    else
        python3 -m zipfile -l "$1" 2>/dev/null | awk 'NR>2 {print $1}'
    fi
}

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

# --- 0) R185 (.132): retire superseded files --------------------------------
# unzip -o never DELETES files, so docs retired in .132 would survive every
# update as orphans on the printer. One honest list, removed on every run
# (idempotent - runs in the old script AND again in the re-exec'ed new one).
RETIRE="TESTANLEITUNG_126.md TESTANLEITUNG_127.md TESTANLEITUNG_128.md \
TESTANLEITUNG_129.md TESTANLEITUNG_130.md TESTANLEITUNG_131.md \
AUDIT_REPORT.md docs/ROADMAP_130.md docs/FELDLOG_094_ANTWORT.md"
[ -z "${CFG_DIR}" ] && RETIRE=""
for _r in ${RETIRE}; do
    if [ -e "${CFG_DIR}/${PKG_REL}/${_r}" ]; then
        rm -f "${CFG_DIR}/${PKG_REL}/${_r}"
        echo "[ok] retired: ${_r}"
    fi
done

# --- 1) unzip an uploaded UPDATE zip over the old folder (NEW in .50) ----------------
if [ "${1:-}" != "--unpacked" ] && [ -n "${CFG_DIR}" ]; then
    CUR="$(sed -n "s/^[[:space:]]*variable_version: *'\(R2-[0-9-]*\.[0-9]*[a-z]*\)'.*/\1/p" \
           "${DIR}/macros/01_state.cfg" 2>/dev/null | head -1)"
    CUR_N="$(printf '%s' "${CUR:-}" | sed -n 's/.*\.\([0-9]*\)[a-z]*$/\1/p')"
    CUR_N="${CUR_N:-0}"
    CUR_S="$(printf '%s' "${CUR:-}" | sed -n 's/.*\.[0-9]*\([a-z]*\)$/\1/p')"
    # R174 (.129 field log): hotfix versions carry a LETTER suffix (.129a).
    # The old digits-only parser did not even see '129a.zip' - the update
    # re-applied the stale '.129.zip' from the folder and the hotfix never
    # arrived. Numbers compare numerically, letters lexicographically
    # ('' < a < b), so 129a > 129 and 130 > 129a.
    BEST=""; BEST_N=0; BEST_S=""
    for Z in "${CFG_DIR}"/klipper-e3-r2d2-UPDATE-R2-*.zip "${DIR}"/klipper-e3-r2d2-UPDATE-R2-*.zip; do
        [ -f "${Z}" ] || continue
        ZT="$(basename "${Z}" | sed -n 's/.*\.\([0-9]*\)\([a-z]*\)\.zip$/\1 \2/p')"
        [ -n "${ZT}" ] || continue
        ZN="${ZT%% *}"; ZS="${ZT##* }"
        if [ "${ZN}" -gt "${BEST_N}" ] \
           || { [ "${ZN}" -eq "${BEST_N}" ] && [[ "${ZS}" > "${BEST_S}" ]]; }; then
            BEST="${Z}"; BEST_N="${ZN}"; BEST_S="${ZS}"
        fi
    done
    if [ -n "${BEST}" ]; then
        echo "[i] uploaded update zip found: $(basename "${BEST}")  (installed: ${CUR:-unknown})"
        OLDER=0
        if [ "${BEST_N}" -lt "${CUR_N}" ] \
           || { [ "${BEST_N}" -eq "${CUR_N}" ] && [[ "${BEST_S}" < "${CUR_S}" ]]; }; then
            OLDER=1
        fi
        if [ "${OLDER}" -eq 1 ] && [ "${FORCE}" -eq 0 ]; then
            echo "[!] that zip is OLDER than the installed version - not unpacking it."
            echo "    to downgrade anyway:  bash \"${DIR}/update.sh\" --force"
        else
            [ "${OLDER}" -eq 1 ] && echo "[i] --force: unpacking the OLDER zip anyway"
            # R199 (.134 field report): refuse FLAT zips BEFORE unpacking.
            # A zip without the klipper-e3-r2d2/ top-level folder scatters
            # macros/, tools/ ... next to printer.cfg while the package
            # itself is NOT updated (stays on the old version) - exactly
            # the ".134 shows as .133" field report.
            FLAT=0
            zip_list "${BEST}" | grep -q "^${PKG_REL}/macros/01_state.cfg$" || FLAT=1
            zip_list "${BEST}" | grep -qv "^${PKG_REL}/" && FLAT=1
            if [ "${FLAT}" -eq 1 ]; then
                echo "[!] REFUSED: $(basename "${BEST}") has no ${PKG_REL}/ top-level folder"
                echo "    (a flat zip would unpack macros/, tools/ ... next to your"
                echo "     printer.cfg and the package would NOT be updated -"
                echo "     that is the .134 zip bug: the LCD kept showing .133)"
                echo "    Get a fixed zip; NOTHING was unpacked, nothing restarted."
                exit 1
            fi
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
            # R174 (.129 field log): the applied zip moves to r2_backups -
            # stale zips in the config folder kept winning the 'newest zip'
            # race and re-installed old versions over new ones
            mkdir -p "${CFG_DIR}/r2_backups" 2>/dev/null
            mv "${BEST}" "${CFG_DIR}/r2_backups/" 2>/dev/null || true
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

# --- 2b) R199: remains of the FLAT .134 zip in the config folder? ----------------------
if [ -n "${CFG_DIR}" ] && [ -f "${CFG_DIR}/macros/01_state.cfg" ] \
   && [ -f "${CFG_DIR}/${PKG_REL}/macros/01_state.cfg" ]; then
    echo "[!] found macros/ directly in ${CFG_DIR} - remains of the FLAT .134"
    echo "    update zip (that update never reached the package - this is why"
    echo "    .134 kept showing as .133). After THIS update ran clean ([ok]),"
    echo "    remove the strays (check first that nothing of YOURS lives there):"
    echo "        cd ${CFG_DIR} && ls macros tools web menus 2>/dev/null"
    echo "        rm -rf .github docs macros menus slicer tools"
    echo "        rm -f .gitignore COMPATIBILITY.md DEVELOPMENT.md INSTALL.md ISHAPER.md"
    echo "        rm -f LICENSE MANUAL.md MANUAL.pdf README.md TESTANLEITUNG.md"
    echo "        rm -f printer.cfg.example setup.sh update.sh"
    echo "    printer.cfg and variables.cfg are never part of a zip and stay untouched."
fi

# --- 3) version check ------------------------------------------------------------------
V="$(sed -n "s/^[[:space:]]*variable_version: *'\(R2-[0-9-]*\.[0-9]*[a-z]*\)'.*/\1/p" \
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
UPD_TS="$(date +%s)"
# R205: [r] bracket - an unbracketed root pkill matches its OWN sudo
# wrapper (the pattern rides along in the sudo command line) and would
# signal its own parent mid-run; the bracket keeps the checker out.
(sudo -n pkill -f '[r]2_postproc.py' 2>/dev/null || pkill -f '[r]2_postproc.py' 2>/dev/null) && sleep 1
if sudo systemctl restart r2-postproc 2>/dev/null; then
    echo "[ok] r2-postproc restarted"
else
    echo "[!] could not restart r2-postproc (sudo?) - run:"
    echo "        sudo systemctl restart r2-postproc"
fi
# R166: PROVE the new daemon is the one running. The .123 field log
# (lithophane V2 'still an empty plate') was a watcher that silently kept
# OLD code: pkill or the restart can fail without any error output.
# R205 (.136d field log): the census now SAYS the number + PID. The old
# silent ok sent the user to a hand-run watcher check, and under sudo
# that check lists the sudo+pgrep pair ITSELF as extra processes - which
# read as hidden watchers (there was exactly one). The [r] bracket keeps
# every pattern below from matching the checker's own command line,
# with or without sudo.
sleep 3
STALE=0; RUNNING=0; WLIST=""
if command -v pgrep >/dev/null 2>&1; then
    for PID in $(pgrep -f '[r]2_postproc.py' 2>/dev/null); do
        [ -z "${PID}" ] && continue
        RUNNING=1
        ET="$(ps -o etimes= -p "${PID}" 2>/dev/null | tr -d ' ')"
        case "${ET}" in ''|*[!0-9]*) continue ;; esac
        if [ $(( $(date +%s) - ET )) -lt "${UPD_TS}" ]; then
            STALE=1
            echo "[!] r2-postproc PID ${PID} (user $(ps -o user= -p "${PID}" 2>/dev/null | tr -d ' '))"
            echo "    started BEFORE this update unpacked - it still runs the OLD"
            echo "    generator code. Kill it:  sudo kill ${PID} ; sudo systemctl restart r2-postproc"
        fi
    done
    for PID in $(pgrep -f '[r]2_postproc.py .*--watch' 2>/dev/null); do
        WLIST="${WLIST} ${PID}"
    done
fi
WN=0; for PID in ${WLIST}; do WN=$((WN + 1)); done
if [ "${RUNNING}" -eq 0 ]; then
    echo "[!] NO r2-postproc process is running - generators will not answer!"
    echo "    start it:  sudo systemctl restart r2-postproc"
elif [ "${STALE}" -ne 0 ]; then
    :   # the per-PID warnings above say it all
elif [ "${WN}" -eq 1 ]; then
    echo "[ok] watcher census: exactly 1 r2-postproc watcher (PID$(echo "${WLIST}"))"
    echo "     - started with this update, running the new code"
elif [ "${WN}" -gt 1 ]; then
    echo "[!] watcher census: ${WN} watchers(${WLIST}) - a second watcher would"
    echo "    double every state push. ONE command fixes it (root pkill + restart):"
    echo "        sudo bash ${0}"
else
    echo "[!] no r2-postproc WATCHER is running (only one-shot processes)."
    echo "    start it:  sudo systemctl restart r2-postproc"
fi
# gold check once klippy is back up: the daemon publishes its build stamp
# (postproc_build save_variable). Klippy needs 10-60 s after the restart
# above, so this waits patiently - but ONLY while moonraker answers at
# all (503 = klippy still booting); with no moonraker on the box it
# gives up after two fast tries instead of sleeping.
BUILT=""
TRY=0
while [ "${TRY}" -lt 18 ]; do
    TRY=$((TRY + 1))
    CODE="$(curl -s -m 5 -o /tmp/r2_build_check.json -w '%{http_code}' \
        "${MOONRAKER}/printer/objects/query?save_variables" 2>/dev/null)"
    if [ "${CODE}" = "200" ]; then
        BUILT="$(sed -n 's/.*"postproc_build": *"\([^"]*\)".*/\1/p' \
            /tmp/r2_build_check.json 2>/dev/null)"
        break
    fi
    case "${CODE}" in
        000) [ "${TRY}" -ge 2 ] && break ;;
    esac
    sleep 5
done
rm -f /tmp/r2_build_check.json 2>/dev/null
if [ -n "${BUILT}" ]; then
    if echo "${BUILT}" | grep -q "${V}"; then
        echo "[ok] post-processor reports build '${BUILT}' (matches this release)"
    else
        echo "[!] post-processor reports build '${BUILT}' - expected ${V}."
        echo "    A STALE daemon is generating - restart it: sudo systemctl restart r2-postproc"
    fi
fi

# --- 6b) web-LCD: refresh an EXISTING install (R206) -----------------------
# Field log .136d ("web ui sagt 403 forbidden") had TWO stacked causes:
#   (1) Moonraker answers 403 to any request whose Origin header it does
#       not know - browsers send Origin on EVERY command POST (same-origin
#       GETs carry none: the live values worked, every button died since
#       .136b). The refreshed nginx site strips Origin at the proxy and
#       adds its own browser-CSRF guard.
#   (2) update.sh never synced web/r2_menu.py into moonraker's
#       components/ - the .136b installer ran once, so later extension
#       fixes (the R204 slim query!) never reached the Pi.
# install_web.sh --update-only fixes both - and is a clean NO-OP when no
# web-LCD is installed (this never force-installs anything).
if [ -f "${DIR}/web/install_web.sh" ]; then
    if ! bash "${DIR}/web/install_web.sh" --update-only; then
        echo "[!] web-LCD refresh failed - run:  bash ${DIR}/web/install_web.sh"
    fi
fi

# --- 6c) FINAL watcher census (R207) ----------------------------------------
# The census above ran ~3 s after the restart - BEFORE klippy finished
# booting. The .136d field log showed doubled state pushes right AFTER a
# clean update (every SAVE_VARIABLE twice, ~8 s staggered): a pusher that
# appears late (boot race with cron @reboot / rc.local, or one that the
# early census could not see) slips through that window. This second,
# read-only census runs when klippy is up and the build stamp came back -
# THE truth, printed where the user reads it. Never restarts anything.
sleep 2
STALE=0; RUNNING=0; WLIST=""
if command -v pgrep >/dev/null 2>&1; then
    for PID in $(pgrep -f '[r]2_postproc.py' 2>/dev/null); do
        [ -z "${PID}" ] && continue
        RUNNING=1
        ET="$(ps -o etimes= -p "${PID}" 2>/dev/null | tr -d ' ')"
        case "${ET}" in ''|*[!0-9]*) continue ;; esac
        if [ $(( $(date +%s) - ET )) -lt "${UPD_TS}" ]; then
            STALE=1
            echo "[!] r2-postproc PID ${PID} (user $(ps -o user= -p "${PID}" 2>/dev/null | tr -d ' '))"
            echo "    started BEFORE this update unpacked - it still runs the OLD"
            echo "    generator code. Kill it:  sudo kill ${PID} ; sudo systemctl restart r2-postproc"
        fi
    done
    for PID in $(pgrep -f '[r]2_postproc.py .*--watch' 2>/dev/null); do
        WLIST="${WLIST} ${PID}"
    done
fi
WN=0; for PID in ${WLIST}; do WN=$((WN + 1)); done
if [ "${RUNNING}" -eq 0 ]; then
    echo "[!] final census: NO r2-postproc process is running (klippy is up now)"
    echo "    start it:  sudo systemctl restart r2-postproc"
elif [ "${STALE}" -ne 0 ]; then
    echo "[!] final census: a STALE watcher survived the update - see above"
elif [ "${WN}" -eq 1 ]; then
    echo "[ok] final watcher census (klippy up): exactly 1 watcher (PID$(echo "${WLIST}"))"
elif [ "${WN}" -gt 1 ]; then
    echo "[!] final watcher census: ${WN} watchers(${WLIST}) - THIS is the"
    echo "    doubled-push cause (every state push runs twice). The daemon's"
    echo "    runtime sweep logs the rival's path - see:"
    echo "        journalctl -u r2-postproc -n 40 | grep -A1 'runtime sweep'"
    echo "    One command fixes it:  sudo bash ${0}"
else
    echo "[!] final census: no r2-postproc WATCHER is running (one-shot only)"
    echo "    start it:  sudo systemctl restart r2-postproc"
fi

# --- 7) hint: the environment wizard --------------------------------------------------
if [ -f "${DIR}/setup.sh" ]; then
    echo "[i] environment wizard available (zram vs SD-swap, optional services like"
    echo "        OctoPrint + friends, KAMP, LED effects, RAM, swappiness):"
    echo "        bash ${DIR}/setup.sh        (--check = report only)"
    echo "    (.110: with swap in use on the SD card, zram alone is the biggest"
    echo "     Timer too close relief a Pi Zero 2 W can get - setup.sh section 9)"
fi

echo "== done. Happy printing! =="
