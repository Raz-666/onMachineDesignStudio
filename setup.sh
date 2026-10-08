#!/usr/bin/env bash
# =====================================================================================
#  setup.sh - R2 macro system ENVIRONMENT WIZARD (R103)
#
#  update.sh only swaps the package files. setup.sh brings the REST of the
#  machine up to spec - everything AROUND the package that the macro system
#  needs (or benefits from) to run stable:
#
#    1. environment     Pi / user / systemd / sudo / git / network
#    2. config location printer.cfg, the 17 include lines, [r2_postproc] bed
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
    for f in 01_state 02_sounds 03_leds 04_notify 05_materials 06_temp_controls \
             07_start_confirm 08_print_start_stop 09_pause_filament 10_live_tuning \
             11_gantry_sync 12_maintenance 13_system 14_kamp 15_objects 16_labels 17_generator; do
        grep -q "macros/${f}.cfg" "${CFG}" || MISSING="${MISSING} ${f}"
    done
    if [ -z "${MISSING}" ]; then
        ok "all 17 macro includes present in printer.cfg"
    else
        warn "missing include lines for:${MISSING}"
        info "   add at the end of printer.cfg:"
        for m in ${MISSING}; do
            info "       [include klipper-e3-r2d2/macros/${m}.cfg]"
        done
        info "   (or run: bash ${DIR}/update.sh  - it checks the same list)"
    fi

    # the ONE bed truth for generators + LCD macros (non-Ender-3 printers MUST set it)
    if grep -qE '^\[r2_postproc\]' "${CFG}"; then
        if grep -qE '^\s*bed_(min|max)_[xy]:' "${CFG}"; then
            ok "[r2_postproc] bed limits present (generators + park corners use them)"
        else
            warn "[r2_postproc] exists but has no bed_min_x/... limits"
        fi
    else
        warn "no [r2_postproc] section in printer.cfg"
        info "   generators currently fall back to the Ender-3 default bed (0 -3 .. 220 217)."
        info "   On ANY other printer add:"
        info "       [r2_postproc]"
        info "       bed_min_x: 0        # left edge of the printable area"
        info "       bed_max_x: 220      # right edge"
        info "       bed_min_y: 0"
        info "       bed_max_y: 220"
        ask_yn "Add this section now with Ender-3 default values? (your machine ran fine without it - the fallback is identical; only useful to tune or on ANOTHER printer)" n
        if [ "${ASK_ANSWER}" = "y" ]; then
            backup_file "${CFG}" >/dev/null
            # R104.1: insert BEFORE a '#*#' SAVE_CONFIG block if present (that
            # block belongs at the very end of the file) - plain append before
            python3 - "${CFG}" << 'PYEOF'
import sys
p = sys.argv[1]
s = open(p, encoding='utf-8', errors='surrogateescape').read()
block = ('\n[r2_postproc]\n'
         '# printable bed area (mm) - ONE truth for generators + park corners\n'
         'bed_min_x: 0\nbed_max_x: 220\nbed_min_y: -3\nbed_max_y: 217\n')
if '[r2_postproc]' not in s:
    i = s.find('\n#*#')
    if i >= 0:
        s = s[:i].rstrip('\n') + '\n' + block + s[i:]
    else:
        s = s.rstrip('\n') + '\n' + block
    open(p, 'w', encoding='utf-8', errors='surrogateescape').write(s)
PYEOF
            fix "[r2_postproc] bed defaults written into printer.cfg (ADJUST the values!)"
        fi
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
        ask_yn "Install the service now (templated to user '${USER_NAME}', gcodes '${GC_DIR}')?" y
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
    MOONRAKER_CONF="${KAMP_CFG_DIR}/moonraker.conf"
    # R104.1: object processing is POLICY, not correctness - False is a
    # DELIBERATE choice on small Pis (our own manual recommends it on the
    # Pi Zero 2 W: object processing costs RAM on every upload). Never nag,
    # only explain. It no longer makes the wizard offer a KAMP install.
    if [ -f "${MOONRAKER_CONF}" ]; then
        if grep -qE '^\s*enable_object_processing:\s*[Tt]rue' "${MOONRAKER_CONF}"; then
            ok "moonraker object processing enabled (KAMP meshes/purges adaptively)"
        elif grep -qE '^\s*enable_object_processing:' "${MOONRAKER_CONF}"; then
            info "moonraker object processing is OFF (deliberate on a Pi Zero 2 W -"
            info "   recommended there! KAMP then meshes full-bed and the purge falls"
            info "   back to our own line - both fine, no action needed)"
        else
            ask_yn "Enable moonraker object processing (needed for adaptive; costs RAM on every upload)?" n
            if [ "${ASK_ANSWER}" = "y" ]; then
                backup_file "${MOONRAKER_CONF}" >/dev/null
                if grep -q '^\[file_manager\]' "${MOONRAKER_CONF}"; then
                    awk -v ins=0 'ins==0 && /^\[file_manager\]/ {print; print "enable_object_processing: True"; ins=1; next} {print}' \
                        "${MOONRAKER_CONF}" > "${MOONRAKER_CONF}.new" \
                        && mv "${MOONRAKER_CONF}.new" "${MOONRAKER_CONF}"
                else
                    printf '\n[file_manager]\nenable_object_processing: True\n' >> "${MOONRAKER_CONF}"
                fi
                fix "moonraker.conf: object processing enabled"
                info "restart moonraker to activate:  ${SUDO} systemctl restart moonraker"
            fi
        fi
    else
        info "moonraker.conf not found at ${MOONRAKER_CONF} - cannot check object processing"
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
            if [ -n "${CFG_DIR}" ] && [ -f "${CFG}" ]; then
                if ! grep -q '^\[include KAMP_Settings.cfg\]' "${CFG}"; then
                    backup_file "${CFG}" >/dev/null
                    printf '\n# KAMP (added by setup.sh %s)\n[include KAMP_Settings.cfg]\n' "${TS}" >> "${CFG}"
                    fix "printer.cfg: [include KAMP_Settings.cfg] added"
                fi
                if ! grep -q '^\[exclude_object\]' "${CFG}"; then
                    backup_file "${CFG}" >/dev/null
                    printf '\n[exclude_object]\n' >> "${CFG}"
                    fix "printer.cfg: [exclude_object] added"
                fi
            fi
            # moonraker.conf: optional update manager entry
            # (object processing has its own dedicated prompt above - never
            # enabled silently, R104.1)
            if [ -f "${MOONRAKER_CONF}" ]; then
                if ! grep -q 'Klipper-Adaptive-Meshing-Purging' "${MOONRAKER_CONF}"; then
                    ask_yn "Add the moonraker update-manager entry for KAMP?" n
                    if [ "${ASK_ANSWER}" = "y" ]; then
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
                    backup_file "${MOONRAKER_CONF}" >/dev/null
                    printf '\n[update_manager led_effect]\ntype: git_repo\npath: %s/klipper-led_effect\norigin: %s\nis_system_service: False\n' \
                        "${HOME_DIR}" "${LED_REPO_URL}" >> "${MOONRAKER_CONF}"
                    fix "moonraker.conf: led_effect update-manager entry added"
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
        "KlipperScreen|touchscreen UI|only without a touchscreen"
        "cups|paper printing system|not needed on a 3D printer"
        "triggerhappy|GPIO hotkey daemon|rarely used"
        "moonraker-obico|Obico cloud monitoring|only if you do not use Obico"
        "bluetooth|bluetooth daemon|no BT devices on a print server"
        "hciuart|bluetooth UART helper|same"
    )
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
echo
echo "package version: $(sed -n "s/^[[:space:]]*variable_version: *'\(R2-[0-9-]*\.[0-9]*\)'.*/\1/p" "${DIR}/macros/01_state.cfg" 2>/dev/null | head -1)"
echo "== setup done - happy printing! =="
