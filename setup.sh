#!/usr/bin/env bash
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Raz-666 and contributors
# =====================================================================================
#  setup.sh - R2 macro system ENVIRONMENT WIZARD (R103)
#
#  update.sh only swaps the package files. setup.sh brings the REST of the
#  machine up to spec - everything AROUND the package that the macro system
#  needs (or benefits from) to run stable:
#
#    0. backup FIRST    every file this run might change gets a VERIFIED 1:1
#                       copy (cmp) BEFORE anything else - a failed verify
#                       aborts the run, nothing is ever modified unbacked
#    1. environment     Pi / user / systemd / sudo / git / network
#    2. config location printer.cfg, the 19 include lines, [r2_postproc] bed
#    2b. hardware        r2_hardware.cfg - the SECOND variables file (build
#        profile +      volume, probe offsets, clean/present positions, LED
#        LED wizard    layout). Every value asked + confirmed; survives a
#                       variables.cfg reset. LED chains: neopixel/dotstar,
#                       mainboard pin or EBB CAN split chain
#    3. Klipper stack   klipper / moonraker / mainsail services + API check
#    4. Python          the watcher is stdlib-only -> compile + smoke check
#    5. r2-postproc     systemd unit installed / enabled / running / CURRENT
#                       (the unit file is templated to YOUR user + paths)
#    6. KAMP            optional adaptive meshing & purging - detected,
#                       offered for installation (clone + config patches)
#    7. LED effects     klipper-led_effect (needed by 03_leds.cfg [led_effect])
#    8. RAM + services  top RAM consumers, known-optional services (camera,
#                       octoprint, ModemManager, ...) -> ask before disabling
#    9. swap            usage + vm.swappiness tuning offer
#   10. summary         OK / fixed / needs attention
#
#  Usage:
#    bash klipper-e3-r2d2/setup.sh                 interactive (asks questions)
#    bash klipper-e3-r2d2/setup.sh --check         report only, changes NOTHING
#    bash klipper-e3-r2d2/setup.sh /path/printer.cfg   non-default config
#
#  Safety:
#    - nothing is changed without a confirmation (except: nothing)
#    - every config file edited here gets a .r2bak.<timestamp> backup first
#    - klipper / moonraker / mainsail / r2-postproc are NEVER offered for
#      disabling, wpa_supplicant / ssh / swap neither
#    - EOF on a question (non-interactive SSH) = safe default = "no"
# =====================================================================================
set -u

DIR="$(cd "$(dirname "$0")" && pwd)"
USER_NAME="$(id -un)"
HOME_DIR="${HOME:-/home/${USER_NAME}}"
CFG_DIR_DEFAULT="${HOME_DIR}/printer_data/config"
CFG="${R2_PRINTER_CFG:-${CFG_DIR_DEFAULT}/printer.cfg}"
MOONRAKER="http://127.0.0.1:7125"
KAMP_REPO_URL="https://github.com/kyleisah/Klipper-Adaptive-Meshing-Purging.git"
LED_REPO_URL="https://github.com/julianschill/klipper-led_effect.git"
TS="$(date +%Y%m%d-%H%M%S)"
CHECK_ONLY=0
[ "${1:-}" = "--check" ] && CHECK_ONLY=1
[ "${2:-}" = "--check" ] && CHECK_ONLY=1
case "${1:-}" in
    --check) ;;
    "") ;;
    /*|[a-z]*) CFG="${1}" ;;
esac

# ---- helpers ------------------------------------------------------------------------
SUDO=""
if [ "$(id -u)" -ne 0 ] && command -v sudo >/dev/null 2>&1; then
    SUDO="sudo"
fi
HAVE_SYSTEMD=0
[ -d /run/systemd/system ] && HAVE_SYSTEMD=1
ASK_ANSWER=""

ask_yn() {   # ask_yn "question" y|n  -> ASK_ANSWER=y|n
    local q="$1" d="${2:-n}" a=""
    if [ "${CHECK_ONLY}" -eq 1 ]; then
        echo "[i] (check mode) ${q} -> would ask (default: ${d})"
        ASK_ANSWER="n"      # check mode NEVER acts, no matter the default
        return 0
    fi
    printf '%s' "${q} "
    if [ "${d}" = "y" ]; then printf '[Y/n]: '; else printf '[y/N]: '; fi
    if ! read -r a; then a=""; echo; fi          # EOF -> empty -> default
    a="$(printf '%s' "${a}" | tr '[:upper:]' '[:lower:]')"
    if [ -z "${a}" ]; then ASK_ANSWER="${d}"; return 0; fi
    case "${a}" in y|yes|j|ja) ASK_ANSWER="y" ;; *) ASK_ANSWER="n" ;; esac
}

svc_active() {   # svc_active name -> 0 if running
    [ "${HAVE_SYSTEMD}" -eq 1 ] || return 1
    systemctl is-active --quiet "$1" 2>/dev/null
}

svc_exists() {   # unit exists at all
    [ "${HAVE_SYSTEMD}" -eq 1 ] || return 1
    systemctl list-unit-files "$1.service" 2>/dev/null | grep -q "^$1"
}

hsize() {   # bytes -> human
    if command -v numfmt >/dev/null 2>&1; then
        numfmt --to=iec --suffix=B "$1" 2>/dev/null || echo "${1}B"
    else
        awk -v b="$1" 'BEGIN{split("B KiB MiB GiB",u); i=1
            while (b>=1024 && i<4) {b/=1024; i++}
            printf "%.0f %s", b, u[i]}'
    fi
}

backup_file() {   # backup_file path -> echoes backup name
    [ -f "$1" ] || return 0
    cp "$1" "$1.r2bak.${TS}"
    echo "$1.r2bak.${TS}"
}

RESULT_OK=""
RESULT_FIX=""
RESULT_WARN=""
ok()   { RESULT_OK="${RESULT_OK}\n  [ok]   $*";   echo "[ok]   $*"; }
fix()  { RESULT_FIX="${RESULT_FIX}\n  [fix]  $*";  echo "[fix]  $*"; }
warn() { RESULT_WARN="${RESULT_WARN}\n  [!] $*"; echo "[!] $*"; }
info() { echo "[i]    $*"; }

echo "== R2 environment wizard =="
echo "       package : ${DIR}"
echo "       user    : ${USER_NAME}  (home ${HOME_DIR})"
[ "${CHECK_ONLY}" -eq 1 ] && echo "       MODE    : CHECK ONLY (no changes, no questions)"

# =====================================================================================
#  0) BACKUP FIRST (R108) - before anything else: every file this run might
#     change gets a copy that is VERIFIED 1:1 against the original (cmp).
#     A failed verify ABORTS the whole run - nothing is modified unbacked.
# =====================================================================================
R2_LIB_LOADED=0
if [ -f "${CFG}" ]; then
    CFG_DIR="$(cd "$(dirname "${CFG}")" && pwd)"
fi
if [ -f "${DIR}/tools/r2_setup_lib.sh" ] && [ -n "${CFG_DIR}" ]; then
    . "${DIR}/tools/r2_setup_lib.sh"
    r2_lib_init "${CFG_DIR}" "${DIR}" "${TS}" "${CHECK_ONLY}" "${SUDO}"
    if ! r2_backup_candidates "${CFG_DIR}/r2_backups/${TS}-setup"; then
        echo "[!] setup ABORTED by the backup rule - no file was modified"
        exit 1
    fi
    R2_LIB_LOADED=1
else
    echo "[i] backup step skipped (no printer.cfg found / wizard library missing)"
    if [ -f "${DIR}/tools/r2_setup_lib.sh" ]; then
        . "${DIR}/tools/r2_setup_lib.sh"
        r2_lib_init "${CFG_DIR_DEFAULT}" "${DIR}" "${TS}" "${CHECK_ONLY}" "${SUDO}"
        R2_LIB_LOADED=1
    fi
fi

# =====================================================================================
#  1) environment
# =====================================================================================
echo
echo "--- 1) environment ---------------------------------------------------------------"
command -v git >/dev/null 2>&1 && ok "git available" || warn "git missing (needed for KAMP / LED effects installation)"
if curl -s -f -m 5 -o /dev/null https://github.com 2>/dev/null; then
    ok "internet reachable"
    NET=1
else
    info "github.com not reachable (offline?) - installs would be skipped"
    NET=0
fi
if [ "${HAVE_SYSTEMD}" -eq 1 ]; then
    ok "systemd running (service management available)"
else
    warn "systemd NOT running here (container/chroot?) - service checks skipped"
fi
[ -n "${SUDO}" ] && ok "sudo available" || info "no sudo - privileged steps print manual commands instead"

# =====================================================================================
#  2) config location
# =====================================================================================
echo
echo "--- 2) configuration -------------------------------------------------------------"
CFG_DIR=""
if [ -f "${CFG}" ]; then
    CFG_DIR="$(cd "$(dirname "${CFG}")" && pwd)"
    ok "printer.cfg found: ${CFG}"
else
    warn "printer.cfg not found at ${CFG}"
    info "run again with the path:  bash ${DIR}/setup.sh /path/to/printer.cfg"
fi

if [ -n "${CFG_DIR}" ]; then
    MISSING=""
    # R224 (.136v field review): 19 files - 18_colorpic (R120) and
    # 19_bricks (R121) were never added here, so a missing include for
    # them went undetected although INSTALL.md and _CHECK_INSTALL
    # (the boot selftest) demand them
    for f in 01_state 02_sounds 03_leds 04_notify 05_materials 06_temp_controls \
             07_start_confirm 08_print_start_stop 09_pause_filament 10_live_tuning \
             11_gantry_sync 12_maintenance 13_system 14_kamp 15_objects 16_labels \
             17_generator 18_colorpic 19_bricks; do
        grep -q "macros/${f}.cfg" "${CFG}" || MISSING="${MISSING} ${f}"
    done
    if [ -z "${MISSING}" ]; then
        ok "all 19 macro includes present in printer.cfg"
    else
        warn "missing include lines for:${MISSING}"
        info "   add at the end of printer.cfg:"
        for m in ${MISSING}; do
            info "       [include klipper-e3-r2d2/macros/${m}.cfg]"
        done
        info "   (or run: bash ${DIR}/update.sh  - it checks the same list)"
    fi

    # ---- R2 hardware profile (R108): the SECOND variables file --------------
    # r2_hardware.cfg holds the printer-specific values (bed limits, probe
    # offsets, clean/present positions, LED layout). It is INCLUDED from
    # printer.cfg and survives deleting variables.cfg - resetting the normal
    # settings file can never lose machine compatibility. LCD-editable
    # hardware values (LED areas) persist into it too (R2_PERSIST).
    if [ "${R2_LIB_LOADED}" = "1" ]; then
        if grep -qE '^\[r2_postproc\]' "${CFG}"; then
            warn "LEGACY [r2_postproc] section found - Klipper CANNOT BOOT with it"
            info "   ('Section r2_postproc is not a valid config section' - halt loop!)"
            ask_yn "Migrate it into r2_hardware.cfg now (values kept, backup made, old section only commented out)?" n
            if [ "${ASK_ANSWER}" = "y" ]; then
                if r2_sidecar "${CFG}"; then
                    _raw_vals="$(grep -A6 -E '^\[r2_postproc\]' "${CFG}" | grep -E '^(bed_min_x|bed_max_x|bed_min_y|bed_max_y):' || true)"
                    python3 - "${CFG}" << 'R2PY_RAW'
import re, sys
p = sys.argv[1]
s = open(p, encoding='utf-8', errors='surrogateescape').read()
def comment(m):
    # R113: no rstrip() - it glued the next line onto the last comment line
    return '\n'.join('# [R2-off] ' + l if l.strip() else l for l in m.group(0).split('\n'))
# R113: column-0 comments INSIDE the section are consumed when another
# section line follows (field-log .86 boot halt), trailing comments stay
s = re.sub(r'\n?\[r2_postproc\]\n(?:[ \t]*[A-Za-z_][A-Za-z0-9_]*:[^\n]*\n|[ \t]*\n|(?:[ \t]*#[^\n]*\n)+(?=[ \t]*[A-Za-z_][A-Za-z0-9_]*:))*', comment, s, count=1)
open(p, 'w', encoding='utf-8', errors='surrogateescape').write(s)
R2PY_RAW
                    r2_hw_read
                    while IFS= read -r _rv; do
                        [ -z "${_rv}" ] && continue
                        _rk="${_rv%%:*}"; _rk="${_rk//[[:space:]]/}"
                        _rvv="${_rv#*:}"; _rvv="${_rvv//[[:space:]]/}"
                        R2_HW["${_rk}"]="${_rvv}"
                    done <<< "${_raw_vals}"
                    r2_hw_write
                    r2_ensure_include
                    fix "migrated: [r2_postproc] -> r2_hardware.cfg (old section commented out, values kept)"
                    info "RESTART klipper to confirm it boots now"
                else
                    warn "backup verify failed - migration skipped"
                fi
            fi
        fi
        if [ -f "$(r2_hwfile)" ]; then
            ok "hardware profile present: $(r2_hwfile) (survives variables.cfg resets)"
            r2_ensure_include
            r2_apply_led_layout
            r2_ask "Open the hardware + LED wizard anyway (check / change values)?" n
        else
            info "no r2_hardware.cfg yet - the wizard asks every printer-specific value"
            info "   (build volume, probe offsets, clean/present positions, LED layout)."
            info "   On the Ender-3 reference the defaults are fine - Enter-through takes them."
            r2_ask "Run the hardware + LED wizard now?" n
        fi
        if [ "${R2_YN}" = "y" ]; then
            r2_hw_wizard
            r2_led_wizard
        fi
    else
        info "wizard library not loaded - hardware profile not offered (see step 0)"
    fi
fi

# =====================================================================================
#  3) Klipper stack
# =====================================================================================
echo
echo "--- 3) Klipper / Moonraker / Mainsail --------------------------------------------"
for s in klipper moonraker; do
    if svc_active "${s}"; then
        ok "${s} running"
    elif svc_exists "${s}"; then
        warn "${s} installed but NOT running"
    elif [ "${HAVE_SYSTEMD}" -eq 1 ]; then
        warn "${s} service not found"
    fi
done
# R104.1: Mainsail is static files behind nginx on standard installs - it has
# NO own systemd service there (the old check cried 'not found' on every
# healthy Mainsail box - field log .81)
if svc_active mainsail; then
    ok "mainsail running"
elif svc_active nginx || [ -d "${HOME_DIR}/mainsail" ]; then
    ok "Mainsail present (static files served by nginx - no own service, normal)"
elif [ "${HAVE_SYSTEMD}" -eq 1 ]; then
    info "no mainsail service and no ~/mainsail found - where does the web UI come from?"
fi
if INFO_JSON="$(curl -s -m 5 "${MOONRAKER}/server/info" 2>/dev/null)"; then
    KLIP_STATE="$(printf '%s' "${INFO_JSON}" | sed -n 's/.*"klipper_state": *"\([^"]*\)".*/\1/p')"
    [ -n "${KLIP_STATE}" ] && ok "moonraker API answers (klipper state: ${KLIP_STATE})" \
                            || ok "moonraker API answers"
else
    info "moonraker API not reachable on ${MOONRAKER} (started? port?)"
fi

# =====================================================================================
#  4) Python for the watcher
# =====================================================================================
echo
echo "--- 4) Python (the watcher is stdlib-only) ---------------------------------------"
if command -v python3 >/dev/null 2>&1; then
    PYV="$(python3 -V 2>&1)"
    ok "python3 present (${PYV})"
    if python3 -m py_compile "${DIR}/tools/r2_postproc.py" 2>/dev/null; then
        ok "r2_postproc.py compiles clean"
    else
        warn "r2_postproc.py does NOT compile - package broken?"
    fi
else
    warn "python3 missing!  sudo apt install python3"
fi

# =====================================================================================
#  5) r2-postproc systemd service
# =====================================================================================
echo
echo "--- 5) r2-postproc watcher service ------------------------------------------------"
if [ "${HAVE_SYSTEMD}" -eq 0 ]; then
    info "no systemd here - manual install (see INSTALL.md section 3d):"
    info "   cp ${DIR}/tools/r2-postproc.service /etc/systemd/system/ (edit User= first!)"
else
    GC_DIR="${HOME_DIR}/printer_data/gcodes"
    INSTALLED=0
    if [ "$(systemctl show r2-postproc -p LoadState --value 2>/dev/null)" = "loaded" ]; then
        INSTALLED=1
        EXEC_LINE="$(systemctl show r2-postproc -p ExecStart --value 2>/dev/null | grep -oE '[^ ;]+r2_postproc\.py' | head -1)"
        if svc_active r2-postproc; then
            ok "r2-postproc running"
        else
            warn "r2-postproc installed but NOT running"
        fi
        if [ -n "${EXEC_LINE}" ] && [ "${EXEC_LINE}" != "${DIR}/tools/r2_postproc.py" ]; then
            warn "the running watcher is a DIFFERENT copy:"
            info "   service : ${EXEC_LINE}"
            info "   package : ${DIR}/tools/r2_postproc.py"
            info "   -> two installations? update.sh unpacked here, service still points there."
        fi
    fi
    # R104.1: build the templated unit ONCE - if the installed one is already
    # byte-identical there is NOTHING to do (the old flow asked for sudo and
    # rewrote an unchanged file - field log .81)
    _tmpl_unit="$(mktemp)"
    sed -e "s|^User=.*|User=${USER_NAME}|" \
        -e "s|/home/pi/|${HOME_DIR}/|g" \
        "${DIR}/tools/r2-postproc.service" > "${_tmpl_unit}"
    _unit_current=0
    if [ "${INSTALLED}" -eq 1 ] && cmp -s "${_tmpl_unit}" /etc/systemd/system/r2-postproc.service 2>/dev/null; then
        _unit_current=1
        ok "service unit already current (this package, user ${USER_NAME}) - nothing to do"
    fi
    if [ "${INSTALLED}" -eq 0 ]; then
        warn "r2-postproc service not installed (layer markers / file info / generators need it)"
    fi
    if [ "${INSTALLED}" -eq 0 ]; then
        ask_yn "Install the service now (templated to user '${USER_NAME}', gcodes '${GC_DIR}')?" n
    elif [ "${_unit_current}" -eq 0 ]; then
        ask_yn "Re-install / refresh the service unit from this package?" n
    else
        ASK_ANSWER="n"
    fi
    if [ "${ASK_ANSWER}" = "y" ]; then
        if [ -d "${GC_DIR}" ] || [ -d "${CFG_DIR}" ]; then
            if [ -n "${SUDO}" ] || [ "$(id -u)" -eq 0 ]; then
                ${SUDO} install -m 644 "${_tmpl_unit}" /etc/systemd/system/r2-postproc.service \
                    && ${SUDO} systemctl daemon-reload \
                    && ${SUDO} systemctl enable --now r2-postproc \
                    && fix "r2-postproc installed + enabled + started (user ${USER_NAME})" \
                    || warn "service installation failed - manual steps in INSTALL.md 3d"
            else
                info "no sudo - manual install:"
                info "   sed -i 's|^User=.*|User=${USER_NAME}|; s|/home/pi/|${HOME_DIR}/|g' ${DIR}/tools/r2-postproc.service"
                info "   sudo cp ${DIR}/tools/r2-postproc.service /etc/systemd/system/"
                info "   sudo systemctl daemon-reload && sudo systemctl enable --now r2-postproc"
            fi
        else
            warn "neither ${GC_DIR} nor a config dir found - looked like a wrong machine, skipped"
        fi
    fi
    rm -f "${_tmpl_unit}"
    if svc_active r2-postproc; then
        info "recent watcher log:  journalctl -u r2-postproc -n 20 --no-pager"
    fi
fi

# =====================================================================================
#  6) KAMP (optional, recommended)
# =====================================================================================
echo
echo "--- 6) KAMP (adaptive meshing & purging, optional) --------------------------------"
KAMP_OK=1
KAMP_REPO="${HOME_DIR}/Klipper-Adaptive-Meshing-Purging"
KAMP_CFG_DIR="${CFG_DIR:-${CFG_DIR_DEFAULT}}"
if [ -d "${KAMP_REPO}" ]; then
    ok "KAMP repository present (${KAMP_REPO})"
else
    warn "KAMP repository missing"
    KAMP_OK=0
fi
if [ -L "${KAMP_CFG_DIR}/KAMP" ] || [ -d "${KAMP_CFG_DIR}/KAMP" ]; then
    ok "KAMP config link present (config/KAMP)"
else
    [ "${KAMP_OK}" -eq 1 ] && { warn "KAMP config link (config/KAMP) missing"; KAMP_OK=0; }
fi
if [ -f "${KAMP_CFG_DIR}/KAMP_Settings.cfg" ]; then
    ok "KAMP_Settings.cfg present"
    GREP_INC="$(grep -c '^\[include ./KAMP/' "${KAMP_CFG_DIR}/KAMP_Settings.cfg" 2>/dev/null || echo 0)"
    [ "${GREP_INC}" -ge 1 ] && ok "   ${GREP_INC} KAMP feature(s) enabled" \
                              || warn "   no KAMP feature enabled in KAMP_Settings.cfg"
else
    [ "${KAMP_OK}" -eq 1 ] && { warn "KAMP_Settings.cfg missing"; KAMP_OK=0; }
fi
if [ -n "${CFG_DIR}" ]; then
    grep -q '^\[exclude_object\]' "${CFG}" && ok "[exclude_object] in printer.cfg" \
        || { warn "[exclude_object] missing in printer.cfg (adaptive needs it)"; KAMP_OK=0; }
    grep -q '^\[include KAMP_Settings.cfg\]' "${CFG}" && ok "KAMP include in printer.cfg" \
        || { [ "${KAMP_OK}" -eq 1 ] && { warn "[include KAMP_Settings.cfg] missing in printer.cfg"; KAMP_OK=0; }; }
fi
    # R108: object processing through the wizard library - ALWAYS shows the
    # current state + the full what/why/why-not explanation, offers BOTH
    # directions and applies the change in one of the 4 modes (auto /
    # commented-only / separate txt = safest / skip).
    if [ "${R2_LIB_LOADED}" = "1" ]; then
        r2_object_processing
    elif [ -f "${KAMP_CFG_DIR}/moonraker.conf" ]; then
        info "wizard library not loaded - object processing not offered here"
    else
        info "moonraker.conf not found at ${KAMP_CFG_DIR}/moonraker.conf - cannot check object processing"
    fi

    if [ "${KAMP_OK}" -eq 0 ]; then
        info "without KAMP the system works fine (native ADAPTIVE=1 + own prime line)"
        if [ "${NET}" -eq 1 ] && command -v git >/dev/null 2>&1; then
            ask_yn "Install KAMP now (clone + config patches, backups made)?" n
            if [ "${ASK_ANSWER}" = "y" ]; then
                # R104.1: guarded steps - an existing repo is KEPT (the old
                # blind 'git clone' died with 'destination path already
                # exists' and the flow printed a fix line anyway)
                _kamp_new=0
                if [ ! -d "${KAMP_REPO}" ]; then
                    if (cd "${HOME_DIR}" && git clone --quiet "${KAMP_REPO_URL}"); then
                        _kamp_new=1
                    else
                        warn "KAMP clone failed (network?)"
                    fi
                fi
                ln -sfn "${KAMP_REPO}/Configuration" "${KAMP_CFG_DIR}/KAMP" 2>/dev/null
                if [ ! -f "${KAMP_CFG_DIR}/KAMP_Settings.cfg" ] && [ -f "${KAMP_REPO}/Configuration/KAMP_Settings.cfg" ]; then
                    cp "${KAMP_REPO}/Configuration/KAMP_Settings.cfg" "${KAMP_CFG_DIR}/KAMP_Settings.cfg"
                    _kamp_new=1
                fi
                if [ -f "${KAMP_CFG_DIR}/KAMP_Settings.cfg" ]; then
                    # enable the features we use by default: adaptive mesh + line purge
                    sed -i 's|^#\s*\[include \./KAMP/Adaptive_Meshing.cfg\]|[include ./KAMP/Adaptive_Meshing.cfg]|' \
                           "${KAMP_CFG_DIR}/KAMP_Settings.cfg"
                    sed -i 's|^#\s*\[include \./KAMP/Line_Purge.cfg\]|[include ./KAMP/Line_Purge.cfg]|' \
                           "${KAMP_CFG_DIR}/KAMP_Settings.cfg"
                    if [ "${_kamp_new}" -eq 1 ]; then
                        fix "KAMP installed: repo + config/KAMP + KAMP_Settings.cfg (mesh + line purge on)"
                    else
                        fix "KAMP repaired: link/settings refreshed, mesh + line purge on"
                    fi
                fi
            # printer.cfg: include + exclude_object
            if [ -n "${CFG_DIR}" ] && [ -f "${CFG}" ] && [ "${R2_LIB_LOADED}" = "1" ]; then
                if ! grep -q '^\[include KAMP_Settings.cfg\]' "${CFG}"; then
                    r2_change_block "${CFG}" "KAMP include" "[include KAMP_Settings.cfg]"
                fi
                if ! grep -q '^\[exclude_object\]' "${CFG}"; then
                    r2_change_block "${CFG}" "exclude_object (KAMP adaptive needs it)" "[exclude_object]"
                fi
            fi
            # moonraker.conf: optional update manager entry
            # (object processing has its own dedicated prompt above - never
            # enabled silently, R104.1)
            if [ -f "${MOONRAKER_CONF}" ] && ! grep -q 'Klipper-Adaptive-Meshing-Purging' "${MOONRAKER_CONF}"; then
                ask_yn "Add the moonraker update-manager entry for KAMP?" n
                if [ "${ASK_ANSWER}" = "y" ]; then
                    if [ "${R2_LIB_LOADED}" = "1" ]; then
                        r2_change_block "${MOONRAKER_CONF}" "KAMP update-manager entry" \
"[update_manager Klipper-Adaptive-Meshing-Purging]
type: git_repo
channel: dev
path: ${KAMP_REPO}
origin: ${KAMP_REPO_URL}
managed_services: klipper
primary_branch: main"
                    else
                        backup_file "${MOONRAKER_CONF}" >/dev/null
                        printf '\n[update_manager Klipper-Adaptive-Meshing-Purging]\ntype: git_repo\nchannel: dev\npath: %s\norigin: %s\nmanaged_services: klipper\nprimary_branch: main\n' \
                            "${KAMP_REPO}" "${KAMP_REPO_URL}" >> "${MOONRAKER_CONF}"
                        fix "moonraker.conf: KAMP update-manager entry added"
                    fi
                fi
                info "restart moonraker to activate:  ${SUDO} systemctl restart moonraker"
            fi
            info "then FIRMWARE_RESTART - LCD 'Maintenance > KAMP > status' must say installed"
        fi
    else
        info "offline or no git - KAMP install skipped (manual steps: INSTALL.md 3b)"
    fi
else
    ok "KAMP fully set up"
fi

# =====================================================================================
#  7) LED effects (klipper-led_effect - needed by 03_leds.cfg)
# =====================================================================================
echo
echo "--- 7) LED effects (klipper-led_effect) -------------------------------------------"
KLIPPER_DIR="${R2_KLIPPER_DIR:-${HOME_DIR}/klipper}"
LED_OK=0
if [ -e "${KLIPPER_DIR}/klippy/extras/led_effect.py" ]; then
    ok "led_effect module linked into klipper"
    LED_OK=1
elif [ -d "${HOME_DIR}/klipper-led_effect" ]; then
    warn "klipper-led_effect repo present but module not linked (run its installer)"
else
    warn "klipper-led_effect NOT installed - the [led_effect] sections in 03_leds.cfg"
    info "     would make Klipper refuse to boot. Install it OR comment the sections out."
fi
if [ "${LED_OK}" -eq 0 ]; then
    if [ "${NET}" -eq 1 ] && command -v git >/dev/null 2>&1; then
        ask_yn "Install klipper-led_effect now? (its installer RESTARTS klipper)" n
        if [ "${ASK_ANSWER}" = "y" ]; then
            (
                cd "${HOME_DIR}" \
                && git clone --quiet "${LED_REPO_URL}" \
                && cd klipper-led_effect \
                && ./install-led_effect.sh
            ) && fix "klipper-led_effect installed (klipper restarted by its installer)" \
              || warn "led_effect installation failed - manual: INSTALL.md / KIAUH"
            if [ -f "${MOONRAKER_CONF}" ] && ! grep -q 'update_manager led_effect' "${MOONRAKER_CONF}"; then
                ask_yn "Add the moonraker update-manager entry for led_effect?" n
                if [ "${ASK_ANSWER}" = "y" ]; then
                    if [ "${R2_LIB_LOADED}" = "1" ]; then
                        r2_change_block "${MOONRAKER_CONF}" "led_effect update-manager entry" \
"[update_manager led_effect]
type: git_repo
path: ${HOME_DIR}/klipper-led_effect
origin: ${LED_REPO_URL}
is_system_service: False"
                    else
                        backup_file "${MOONRAKER_CONF}" >/dev/null
                        printf '\n[update_manager led_effect]\ntype: git_repo\npath: %s/klipper-led_effect\norigin: %s\nis_system_service: False\n' \
                            "${HOME_DIR}" "${LED_REPO_URL}" >> "${MOONRAKER_CONF}"
                        fix "moonraker.conf: led_effect update-manager entry added"
                    fi
                fi
            fi
        fi
    else
        info "offline or no git - manual install: cd ~ && git clone ${LED_REPO_URL}"
        info "     cd klipper-led_effect && ./install-led_effect.sh"
    fi
fi
if [ -n "${CFG_DIR}" ]; then
    if grep -q '^\[neopixel' "${CFG}"; then
        ok "[neopixel] section(s) in printer.cfg (LED hardware present)"
    else
        info "no [neopixel] in printer.cfg - if LEDs live in another included file, ignore this"
    fi
fi

# =====================================================================================
#  8) RAM + optional services
# =====================================================================================
echo
echo "--- 8) RAM & services --------------------------------------------------------------"
if command -v free >/dev/null 2>&1; then
    free -h | sed 's/^/     /'
    SWAP_USED="$(awk '/^Swap:/ {print $3}' /proc/meminfo 2>/dev/null)"
    [ -z "${SWAP_USED}" ] && SWAP_USED="$(awk '/^Swap:/ {print $3}' <(free -b 2>/dev/null))"
    info "swap in use is NOT an error - the kernel parks idle pages there. It only"
    info "matters if the printer STUTTERS under load. Freeing RAM = disabling what"
    info "you do not use (below) - that is the honest lever, not fighting the swap."
fi
if [ "${HAVE_SYSTEMD}" -eq 1 ]; then
    echo
    info "top services by RAM:"
    _ram_list="$(systemctl list-units --type=service --state=running --no-legend --no-pager 2>/dev/null \
      | awk '{print $1}' \
      | while read -r s; do
            m="$(systemctl show "$s" -p MemoryCurrent --value 2>/dev/null)"
            case "$m" in ''|'[not set]'|'0') continue ;; esac
            echo "$m $s"
        done | sort -rn | head -12 \
      | while read -r b s; do printf '%9s  %s\n' "$(hsize "$b")" "$s"; done)"
    if [ -n "${_ram_list}" ]; then
        echo "${_ram_list}" | sed 's/^/     /'
    else
        info "   service memory accounting is off on this OS (normal on Raspberry Pi OS)"
        info "   -> HOST_CHECK on the LCD/console shows the per-process RAM instead (ps-based)"
    fi
    echo
    info "known-optional services on a print server (nothing is touched without your OK):"
    # R104.1: iterate an ARRAY, never 'echo | while read' - the old pipe loop fed
    # the confirmation read from the CANDIDATE LIST itself, so the prompts
    # answered themselves and every second candidate was silently skipped
    # (field log .81: ModemManager + triggerhappy 'skipped without a keypress')
    #           unit                what it is                                    why optional
    _CANDS=(
        "ModemManager|mobile-broadband modem manager|no LTE modem on a printer"
        "crowsnest|webcam stack (Mainsail camera)|only if you never use the camera"
        "webcamd|webcam stream (older setups)|only if you never use the camera"
        "octoprint|OctoPrint server|you are using Mainsail instead"
        "octoeverywhere|OctoEverywhere cloud access|only if you do not use it"
        "sonar|webcam presence stats (dw-sonar)|only with a camera you still use"
        "go2rtc|camera streaming helper|only with a camera you still use"
        "KlipperScreen|touchscreen UI|only without a touchscreen"
        "cups|paper printing system|not needed on a 3D printer"
        "triggerhappy|GPIO hotkey daemon|rarely used"
        "moonraker-obico|Obico cloud monitoring|only if you do not use Obico"
        "bluetooth|bluetooth daemon|no BT devices on a print server"
        "hciuart|bluetooth UART helper|same"
    )
    # R149 (.110 field request): anything ELSE running that smells like a
    # second print-server stack (an Elegoo/OctoPrint companion box, a second
    # klipper instance...) gets REPORTED even when it is not on the list -
    # every unknown unit matching these patterns is shown with its RAM.
    _EXTRA="$(systemctl list-units --type=service --state=running --no-legend --no-pager 2>/dev/null \
      | awk '{print $1}' | grep -Ei 'elegoo|octoprint|obico|simplyprint|spaghetti|astroprint' \
      | grep -vxF "$(printf '%s\n' "${_CANDS[@]}" | cut -d'|' -f1)" || true)"
    for _unit in ${_EXTRA}; do
        MEM="$(systemctl show "${_unit}" -p MemoryCurrent --value 2>/dev/null)"
        _mem_txt=""
        case "${MEM}" in ''|'[not set]') ;; *) _mem_txt=" ($(hsize "${MEM}"))" ;; esac
        echo
        warn "ALSO running: ${_unit}${_mem_txt} - not on the known list (looks like a second print-server stack)"
        info "      same options as below apply: leave it, or stop + disable it yourself:"
        info "      sudo systemctl disable --now ${_unit}"
    done
    for _cand in "${_CANDS[@]}"; do
        IFS='|' read -r unit what why <<< "${_cand}"
        if svc_active "${unit}"; then
            MEM="$(systemctl show "${unit}" -p MemoryCurrent --value 2>/dev/null)"
            _mem_txt=""
            case "${MEM}" in ''|'[not set]') ;; *) _mem_txt=" ($(hsize "${MEM}"))" ;; esac
            echo
            warn "${unit} is RUNNING${_mem_txt} - ${what} (${why})"
            if [ "${CHECK_ONLY}" -eq 1 ]; then
                echo "[i] (check mode) would offer to disable ${unit}"
            else
                printf '     disable it now? [y/N]: '
                # read from the TERMINAL (/dev/tty), never from a pipe: this
                # loop must not steal stdin - that was the skip bug. The
                # 2>/dev/null comes FIRST so a missing tty fails silently.
                _ans=""
                if ! read -r _ans 2>/dev/null < /dev/tty; then
                    _ans=""
                    echo
                fi
                case "$(printf '%s' "${_ans}" | tr '[:upper:]' '[:lower:]')" in
                    y|yes|j|ja)
                        if ${SUDO} systemctl disable --now "${unit}" 2>/dev/null; then
                            echo "[fix]  ${unit} disabled + stopped"
                        else
                            echo "[!]    could not disable ${unit} (sudo?) - manual:"
                            echo "       sudo systemctl disable --now ${unit}"
                        fi
                        # R149 (.110 field request): removal instructions per
                        # service - deliberately GUIDED, never automatic: an
                        # uninstall must be a conscious act, the disable above
                        # already frees the RAM.
                        case "${unit}" in
                            octoprint)
                                echo "       want it GONE? that is a manual act:"
                                echo "         systemctl disable --now octoprint"
                                echo "         rm /etc/systemd/system/octoprint.service"
                                echo "         rm -rf ~/oprint ~/.octoprint   (your OctoPrint data!)"
                                echo "         sudo systemctl daemon-reload"
                                ;;
                            crowsnest|sonar|octoeverywhere|moonraker-obico|go2rtc)
                                echo "       want it GONE? its installer ships the remover:"
                                echo "         ~/crowsnest/tools/install -u   (crowsnest)"
                                echo "         or: rm -rf <its folder> + remove its service file,"
                                echo "             then: sudo systemctl daemon-reload"
                                ;;
                        esac
                        ;;
                esac
            fi
        fi
    done
    echo
    info "never touched by this script: klipper, moonraker, mainsail, r2-postproc,"
    info "wpa_supplicant, ssh, swap itself."
else
    info "no systemd - RAM overview via processes:"
    ps aux --sort=-rss 2>/dev/null | head -8 | awk '{printf "     %6.0f MiB  %s\n", $6/1024, $11}'
fi

# =====================================================================================
#  9) swap behaviour
# =====================================================================================
echo
echo "--- 9) swap tuning -----------------------------------------------------------------"
# ---- 9a) zram: compressed swap IN RAM (.110 field request) --------------------------
# The .109 field data: 254MB of swap IN USE on the SD card - every page klippy
# needs back comes from slow SD I/O, the 'Timer too close' amplifier. zram
# keeps a compressed copy in RAM: ~3x effective, no SD wear, no I/O latency.
if swapon --show 2>/dev/null | grep -q '^/dev/zram'; then
    _zram_txt="$(swapon --show 2>/dev/null | awk '$1 ~ /^\/dev\/zram/ {printf "%s %s prio %s\n", $1, $3, $4}' | head -1)"
    fix "zram already active (${_zram_txt}) - compressed RAM swap is doing its job"
else
    info "zram = compressed swap inside RAM (~3x effective, no SD card wear, no"
    info "read-back latency). On a 512MB Pi Zero 2 W this is the single best"
    info "upgrade against 'Timer too close' shutdowns under memory pressure."
    info "needs: internet + sudo (package: zram-tools, ~100KB). undo anytime:"
    info "   sudo apt-get purge zram-tools"
    if [ "${CHECK_ONLY}" -eq 1 ]; then
        echo "[i] (check mode) would offer to install zram-tools + configure 50% RAM, zstd, prio 100"
    else
        ask_yn "Install zram (zram-tools) now?" n
        if [ "${ASK_ANSWER}" = "y" ]; then
            if ${SUDO} apt-get update -qq 2>/dev/null && ${SUDO} apt-get install -y -qq zram-tools >/dev/null 2>&1; then
                printf '# R2 print server - set by setup.sh %s\nALGO=zstd\nPERCENT=50\nPRIORITY=100\n' "${TS}" \
                    | ${SUDO} tee /etc/default/zramswap >/dev/null
                ${SUDO} systemctl restart zramswap 2>/dev/null || ${SUDO} systemctl restart zramswap.service 2>/dev/null
                if swapon --show 2>/dev/null | grep -q '^/dev/zram'; then
                    fix "zram active: $(swapon --show 2>/dev/null | awk '$1 ~ /^\/dev\/zram/ {printf "%s (%s, prio %s)", $1, $3, $4; exit}') - the SD swap is now the overflow, not the workhorse"
                    # the SD swap (dphys-swapfile) stays as the safety net, but it
                    # should not carry the load: offer to shrink it to 200MB -
                    # CONFIG ONLY, applies at the next reboot (a live swapoff on a
                    # box with swap in use can wedge it)
                    if [ -f /etc/dphys-swapfile ] && grep -qE '^CONF_SWAPSIZE=(7[5-9][0-9]|[1-9][0-9]{3,})' /etc/dphys-swapfile 2>/dev/null; then
                        info "your SD swap is large (>=750MB) - with zram taking the load, 200MB"
                        info "is plenty as overflow. Config-only change, applies at the NEXT REBOOT."
                        ask_yn "Shrink the SD swap to 200MB (edit /etc/dphys-swapfile)?" n
                        if [ "${ASK_ANSWER}" = "y" ]; then
                            ${SUDO} sed -i 's/^CONF_SWAPSIZE=.*/CONF_SWAPSIZE=200/' /etc/dphys-swapfile \
                                && fix "SD swap will be 200MB after the next reboot (was: $(grep '^CONF_SWAPSIZE' /etc/dphys-swapfile | cut -d= -f2)MB in the old line)"
                        fi
                    fi
                else
                    warn "zram-tools installed but zram0 did not come up - check:"
                    warn "   systemctl status zramswap; cat /etc/default/zramswap"
                fi
            else
                warn "apt install failed (offline? repo?) - manual:"
                warn "   sudo apt-get install zram-tools"
                warn "   echo -e 'ALGO=zstd\nPERCENT=50\nPRIORITY=100' | sudo tee /etc/default/zramswap"
                warn "   sudo systemctl restart zramswap"
            fi
        fi
    fi
fi
echo
SWAPPINESS="$(cat /proc/sys/vm/swappiness 2>/dev/null || echo '?')"
info "vm.swappiness = ${SWAPPINESS} (default 60 - the kernel swaps out READ-ONLY pages early)"
if [ "${SWAPPINESS}" != "?" ] && [ "${SWAPPINESS}" -gt 10 ] 2>/dev/null; then
    info "print servers prefer 10: keep active printing data in RAM, only truly"
    info "idle pages go to swap. This does NOT disable swap - it just stops the"
    info "kernel from swapping things it will need again soon."
    ask_yn "Set vm.swappiness=10 persistently (/etc/sysctl.d/99-r2-printserver.conf)?" n
    if [ "${ASK_ANSWER}" = "y" ]; then
        if [ -n "${SUDO}" ] || [ "$(id -u)" -eq 0 ]; then
            printf '# R2 print server - set by setup.sh %s\nvm.swappiness = 10\n' "${TS}" \
                | ${SUDO} tee /etc/sysctl.d/99-r2-printserver.conf >/dev/null \
                && ${SUDO} sysctl --system >/dev/null 2>&1 \
                && fix "vm.swappiness=10 persistent (was ${SWAPPINESS})"
        else
            info "no sudo - manual:"
            info "   echo 'vm.swappiness = 10' | sudo tee /etc/sysctl.d/99-r2-printserver.conf"
            info "   sudo sysctl --system"
        fi
    fi
fi

# =====================================================================================
#  10) summary
# =====================================================================================
echo
echo "== summary ========================================================================"
[ -n "${RESULT_OK}" ]   && printf 'OK / healthy:%b\n' "${RESULT_OK}"
[ -n "${RESULT_FIX}" ]  && printf 'Fixed just now:%b\n' "${RESULT_FIX}"
[ -n "${RESULT_WARN}" ] && printf 'Needs your attention (state at start - see what was fixed just now):\n%b\n' "${RESULT_WARN}"
if [ "${R2_LIB_LOADED}" = "1" ] && [ -f "${R2_MODE_FILE}" ]; then
    echo
    echo "[i] manual changes collected in: ${R2_MODE_FILE}"
    echo "    (mode 3 = the SAFEST way: your files were not touched at all -"
    echo "     copy the noted lines to the marked places by hand)"
fi
echo
echo "package version: $(sed -n "s/^[[:space:]]*variable_version: *'\(R2-[0-9-]*\.[0-9]*\)'.*/\1/p" "${DIR}/macros/01_state.cfg" 2>/dev/null | head -1)"
echo "== setup done - happy printing! =="
