#!/usr/bin/env bash
# R2-D2 MENU TEST - switch the LCD menu file out of the config, safely.
#
# WHY (decoded from the field logs, .142c round):
#   In every "Timer too close" the reactor stall reads:
#       Reactor 971.617 busy for 0.677 with:
#       'MenuManager.dispatch_gcode (menu.py:952)',
#       'DelayedGcode._gcode_timer_event' x2,
#       'ClientConnection.process_received.<lambda>' x2
#   Klipper re-evaluates menu name TEMPLATES on every refresh. Our menu file
#   is 20 237 lines with 2 423 menu sections and 483 DYNAMIC name templates
#   (preset lists, SD browser pages, generator state ...). On a Pi Zero 2
#   that is the single biggest synchronous block the reactor can hit - and
#   it is still there when the post-processor service is stopped, because
#   menus are evaluated INSIDE Klipper, not by the daemon.
#
#   The MCU is NOT the problem: the crash logs show mcu_awake=0.013 (1.3 %)
#   and sysload=0.22. Nothing is overloaded - something BLOCKS.
#
# SAFETY: this file contains exactly one macro, the version sentinel
#   [gcode_macro _V16_MENUS] - nothing in the print flow depends on it.
#   Turning it off costs the LCD menus (Mainsail and printing work normally)
#   and makes _CHECK_INSTALL print a harmless "modules missing" hint.
#
# USAGE
#   bash tools/r2_menu_test.sh --off     # comment the include out + restart
#   bash tools/r2_menu_test.sh --on      # put it back + restart
#   bash tools/r2_menu_test.sh --status  # what is set right now
set -u

CFG="${R2_PRINTER_CFG:-$HOME/printer_data/config/printer.cfg}"
INC='klipper-e3-r2d2/menus/lcd_menues.cfg'
SUDO=""; [ "$(id -u)" = "0" ] || SUDO="sudo"

ok()   { printf '\033[32m[ok]\033[0m %s\n' "$*"; }
warn() { printf '\033[33m[!]\033[0m %s\n' "$*"; }
err()  { printf '\033[31m[x]\033[0m %s\n' "$*"; }
ask()  { printf '\033[36m->\033[0m %s\n' "$*"; }

restart_klipper() {
    if systemctl list-units --type=service --all 2>/dev/null | grep -q '^ *klipper\.service'; then
        $SUDO systemctl restart klipper && ok "Klipper restarted" \
            || warn "restart manually: sudo systemctl restart klipper"
    else
        warn "klipper.service not found - restart Klipper your usual way"
    fi
}

check_sentinel() {
    local mf
    mf="$(dirname "$CFG")/$INC"
    if [ -r "$mf" ]; then
        local n
        n=$(grep -c '^\[gcode_macro' "$mf" 2>/dev/null || echo 0)
        if [ "$n" != "1" ]; then
            warn "lcd_menues.cfg now defines $n macros (expected 1 sentinel)."
            warn "Check that no print-critical macro moved into the menu file."
            warn "Continuing anyway - read the numbers above."
        fi
    fi
}

do_status() {
    echo "=========== R2-D2 menu test status ==========="
    if grep -qE "^\[include[[:space:]]+$INC\]" "$CFG" 2>/dev/null; then
        echo "LCD menu file:  INCLUDED (menus active)"
    elif grep -qE "^#[[:space:]]*(R2 menu test:[[:space:]]*)?\[include[[:space:]]*$INC\]" "$CFG" 2>/dev/null; then
        echo "LCD menu file:  COMMENTED OUT (menus off - test mode)"
    else
        echo "LCD menu file:  not found in printer.cfg at all"
    fi
    echo "=============================================="
}

do_off() {
    [ -r "$CFG" ] || { err "printer.cfg not found at $CFG"; \
                       err "set R2_PRINTER_CFG=/path/to/printer.cfg"; exit 1; }
    check_sentinel
    cp -p "$CFG" "$CFG.r2menubak" && ok "backup: $CFG.r2menubak"
    python3 - "$CFG" "$INC" <<'PY'
import re, sys
path, inc = sys.argv[1], sys.argv[2]
txt = open(path, encoding='utf-8').read()
pat = re.compile(r'^(\s*)\[include\s+' + re.escape(inc) + r'\]', re.M)
if not pat.search(txt):
    print('already commented out or not present - nothing to do'); sys.exit(0)
txt = pat.sub(lambda m: m.group(1) + '# R2 menu test: ' +
              '[include ' + inc + ']', txt, count=1)
open(path, 'w', encoding='utf-8').write(txt)
print('include commented out')
PY
    ok "LCD menu file is out of the config"
    restart_klipper
    echo
    ask "Now print the same file again."
    ask "Through  -> the menu was the blocker. Tell me, I rebuild it cheap."
    ask "Still crashes -> not the menu either. Next: the delayed_gcodes."
    ask "Back on:  bash $0 --on"
}

do_on() {
    [ -r "$CFG" ] || { err "printer.cfg not found at $CFG"; exit 1; }
    if [ -f "$CFG.r2menubak" ]; then
        cp -p "$CFG.r2menubak" "$CFG" && ok "printer.cfg restored from backup"
        rm -f "$CFG.r2menubak"
    else
        python3 - "$CFG" "$INC" <<'PY'
import re, sys
path, inc = sys.argv[1], sys.argv[2]
txt = open(path, encoding='utf-8').read()
pat = re.compile(r'^(\s*)#\s*R2 menu test:\s*\[include\s+' + re.escape(inc) + r'\]',
                 re.M)
if not pat.search(txt):
    print('no "R2 menu test" marker found - already active?'); sys.exit(0)
txt = pat.sub(lambda m: m.group(1) + '[include ' + inc + ']', txt, count=1)
open(path, 'w', encoding='utf-8').write(txt)
print('include restored')
PY
        ok "LCD menu file back in the config"
    fi
    restart_klipper
}

case "${1:-}" in
    --off)    do_off ;;
    --on)     do_on ;;
    --status) do_status ;;
    -h|--help) sed -n '2,30p' "$0" ;;
    *) err "unknown option: ${1:-<none>}"; echo "try: $0 --help"; exit 2 ;;
esac
