#!/usr/bin/env bash
# R2-D2 EMERGENCY MODE - get printing again, with a guaranteed way back.
#
# WHAT IT DOES (in this order, each step is printed):
#   1. stops the r2-postproc service        -> our whole host side is off
#   2. sets mesh_mode = "OFF" in variables.cfg -> no probe scan after G28
#      (that is the seam where the 'Timer too close' fires: our start macro
#       runs _CALIBRATE_MESH_PROFILE directly after the homing)
#   3. optionally removes the web-UI extension (--web-off) -> no status polling
#   4. restarts Klipper so the config is read clean
#
# EVERY change is backed up first. One command brings it all back:
#       bash r2_emergency.sh --revert
#
# USAGE
#   bash tools/r2_emergency.sh              # safe mode (steps 1+2+4)
#   bash tools/r2_emergency.sh --web-off    # also remove the web extension
#   bash tools/r2_emergency.sh --revert     # undo EVERYTHING, back to normal
#   bash tools/r2_emergency.sh --status     # what is on, what is off
#
# Nothing here deletes a print file, a mesh profile or a setting you made.
set -u

CFG_DIR="${R2_CFG_DIR:-$HOME/printer_data/config}"
VAR_FILE="${R2_VAR_FILE:-$HOME/printer_data/variables.cfg}"
SERVICE="r2-postproc"
STATE="${R2_STATE_FILE:-$HOME/printer_data/.r2_emergency_state}"
HERE="$(cd "$(dirname "$0")" && pwd)"

c_ok()   { printf '\033[32m[ok]\033[0m %s\n' "$*"; }
c_warn() { printf '\033[33m[!]\033[0m %s\n' "$*"; }
c_err()  { printf '\033[31m[x]\033[0m %s\n' "$*"; }
c_ask()  { printf '\033[36m->\033[0m %s\n' "$*"; }

need_sudo() {
    if [ "$(id -u)" = "0" ]; then echo ""; else echo "sudo"; fi
}
SUDO="$(need_sudo)"

# ---------------------------------------------------------------- helpers ---
save_state() {   # key value  (append, so --revert knows the original)
    echo "$1=$2" >> "$STATE"
}

state_get() {
    [ -f "$STATE" ] || { echo ""; return; }
    grep "^$1=" "$STATE" | tail -1 | cut -d= -f2-
}

backup_file() {
    local f="$1"
    [ -f "$f" ] || return 0
    local b="${f}.r2bak-$(date +%Y%m%d-%H%M%S)"
    cp -p "$f" "$b" && c_ok "Backup: $b"
    echo "$b"
}

# write a variable into variables.cfg, creating [Variables] if needed
set_var() {
    local key="$1" val="$2"
    python3 - "$VAR_FILE" "$key" "$val" <<'PY'
import re, sys, os
path, key, val = sys.argv[1], sys.argv[2], sys.argv[3]
if not os.path.isfile(path):
    open(path, 'w').write('[Variables]\n%s = %s\n' % (key, val))
    print('created %s with %s = %s' % (path, key, val)); sys.exit(0)
txt = open(path).read()
pat = re.compile(r'^(\s*)%s\s*=.*$' % re.escape(key), re.M)
if pat.search(txt):
    old = pat.search(txt).group(0).split('=', 1)[1].strip()
    open(path, 'w').write(pat.sub('%s = %s' % (key, val), txt, count=1))
    print('%s: %s -> %s' % (key, old, val))
elif '[Variables]' in txt:
    idx = txt.index('[Variables]') + len('[Variables]')
    txt = txt[:idx] + '\n' + '%s = %s' % (key, val) + txt[idx:]
    open(path, 'w').write(txt)
    print('%s added = %s' % (key, val))
else:
    open(path, 'a').write('\n[Variables]\n%s = %s\n' % (key, val))
    print('[Variables] block added with %s = %s' % (key, val))
PY
}

get_var() {
    [ -f "$VAR_FILE" ] || { echo "(missing)"; return; }
    python3 - "$VAR_FILE" "$1" <<'PY'
import re, sys
txt = open(sys.argv[1]).read()
m = re.search(r'^\s*%s\s*=\s*(.+)$' % re.escape(sys.argv[2]), txt, re.M)
print(m.group(1).strip() if m else '(not set)')
PY
}

restart_klipper() {
    c_ask "Restarting Klipper..."
    if systemctl list-units --type=service --all 2>/dev/null | grep -q '^ *klipper\.service'; then
        $SUDO systemctl restart klipper && c_ok "Klipper restarted" \
            || c_warn "klipper restart failed - check: systemctl status klipper"
    else
        c_warn "klipper.service not found - restart it the way you normally do"
    fi
}

svc_status() {
    systemctl is-active "$SERVICE" 2>/dev/null || true
}

# ------------------------------------------------------------------ status --
do_status() {
    echo "=========== R2-D2 emergency status ==========="
    printf 'service %-14s %s\n' "$SERVICE" "$(svc_status || echo inactive)"
    printf 'mesh_mode %-12s %s\n' "" "$(get_var mesh_mode)"
    printf 'mesh_always %-10s %s\n' "" "$(get_var mesh_always)"
    if [ -f "$STATE" ]; then
        echo "--- this script changed (original values) ---"
        sort -u "$STATE" | sed 's/^/    /'
    else
        echo "--- this script has not changed anything yet ---"
    fi
    local mr
    for mr in "$HOME/printer_data/moonraker.conf" "$CFG_DIR/../moonraker.conf"; do
        [ -f "$mr" ] || continue
        if grep -q '^\[r2_menu\]' "$mr" 2>/dev/null; then
            echo "web extension  ACTIVE   ($mr has [r2_menu])"
        else
            echo "web extension  off      ($mr has no [r2_menu])"
        fi
        break
    done
    echo "=============================================="
}

# ------------------------------------------------------------------- safe ---
do_safe() {
    local web_off="${1:-no}"
    echo "=========== R2-D2 EMERGENCY MODE ==========="
    echo "Goal: print today. Our host side off, no probe scan after homing."
    echo

    # --- 1) our service
    local was
    was="$(svc_status || true)"
    if [ -z "$(state_get service_was)" ]; then save_state service_was "${was:-unknown}"; fi
    if [ "$was" = "active" ]; then
        $SUDO systemctl stop "$SERVICE" && c_ok "service $SERVICE stopped" \
            || c_err "could not stop $SERVICE"
    else
        c_ok "service $SERVICE already not running (${was:-inactive})"
    fi

    # --- 2) mesh off (the seam: _CALIBRATE_MESH_PROFILE right after G28)
    if [ -z "$(state_get mesh_mode_was)" ]; then
        save_state mesh_mode_was "$(get_var mesh_mode)"
        save_state mesh_always_was "$(get_var mesh_always)"
    fi
    local bk
    bk="$(backup_file "$VAR_FILE")"
    if [ -n "$bk" ]; then save_state varfile_backup "$bk"; fi
    set_var mesh_mode '"OFF"' >/dev/null && c_ok "mesh_mode = OFF (no mesh/probe scan after homing)"
    set_var mesh_always 'False' >/dev/null && c_ok "mesh_always = False (belt and braces)"

    # --- 3) web extension
    if [ "$web_off" = "yes" ]; then
        if [ -f "$HERE/../web/install_web.sh" ]; then
            save_state web_was "on"
            bash "$HERE/../web/install_web.sh" --uninstall \
                && c_ok "web extension removed from moonraker.conf"
            $SUDO systemctl restart moonraker 2>/dev/null \
                && c_ok "Moonraker restarted" \
                || c_warn "restart Moonraker by hand: sudo systemctl restart moonraker"
        else
            c_warn "web/install_web.sh not found - skipping the web step"
        fi
    fi

    # --- 4) klipper restart
    restart_klipper

    echo
    echo "================= NEXT ================="
    c_ask "Now print ONE file, the way you always do."
    c_ask "It runs through?  -> keep printing like this. Tell me the result."
    c_ask "Still crashes?   -> it is NOT our package. Send me the triage file:"
    echo "        bash $HERE/r2_triage.sh"
    echo
    c_ask "Everything back to normal later:  bash $0 --revert"
    c_warn "While the service is off: new files get NO layer markers and NO"
    c_warn "file info - they still print, but live tuning/menu info stays empty."
    echo "========================================"
}

# ----------------------------------------------------------------- revert ---
do_revert() {
    echo "=========== R2-D2 - BACK TO NORMAL ==========="
    local mm ma bk mw ww
    mm="$(state_get mesh_mode_was)";   ma="$(state_get mesh_always_was)"
    bk="$(state_get varfile_backup)";  mw="$(state_get service_was)"
    ww="$(state_get web_was)"

    if [ -n "$bk" ] && [ -f "$bk" ]; then
        cp -p "$bk" "$VAR_FILE" && c_ok "variables.cfg restored from $bk"
    else
        [ -n "$mm" ] && set_var mesh_mode "$mm" >/dev/null && c_ok "mesh_mode -> $mm"
        [ -n "$ma" ] && set_var mesh_always "$ma" >/dev/null && c_ok "mesh_always -> $ma"
    fi

    if [ -n "$ww" ] && [ -f "$HERE/../web/install_web.sh" ]; then
        bash "$HERE/../web/install_web.sh" >/dev/null 2>&1 \
            && c_ok "web extension reinstalled"
        $SUDO systemctl restart moonraker 2>/dev/null || true
    fi

    if [ "$mw" = "active" ] || [ -z "$mw" ]; then
        $SUDO systemctl start "$SERVICE" 2>/dev/null \
            && c_ok "service $SERVICE started" \
            || c_warn "start it by hand: sudo systemctl start $SERVICE"
    fi

    restart_klipper
    rm -f "$STATE"
    c_ok "state file removed - next emergency run starts fresh"
    echo "=============================================="
}

# ------------------------------------------------------------------ main ----
case "${1:-}" in
    --status)    do_status ;;
    --revert)    do_revert ;;
    --web-off)   do_safe yes ;;
    -h|--help)   sed -n '2,30p' "$0" ;;
    "")          do_safe no ;;
    *)           c_err "unknown option: $1"; echo "try: $0 --help"; exit 2 ;;
esac
