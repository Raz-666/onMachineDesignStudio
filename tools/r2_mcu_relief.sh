#!/usr/bin/env bash
# R2-D2 MCU RELIEF - the printer.cfg settings that cost MCU time, fixed safely.
#
# WHY (analysis of the real printer.cfg, .142c field round):
#   "Timer too close" means the MCU could not schedule a step in time. Three
#   settings in this config push hard against that limit - and two of them
#   are pure waste, not a compromise:
#
#   1) step_pulse_duration: 0.000000100 on ALL FOUR steppers
#      Klipper's comment (which is in the file) says it out loud: "Defining a
#      custom duration completely disables step-on-both-edges". step-on-both-
#      edges fires the step on the rising AND the falling edge = ONE timer
#      interrupt per step instead of TWO. Setting the documented default value
#      explicitly turns that optimiser OFF for no benefit at all.
#      -> Removing the line HALVES the step interrupt load. Free.
#
#   2) minimum_cruise_ratio: 0.85 (default 0.5)
#      This is the modern replacement for max_accel_to_decel. 0.85 means the
#      printer may only "cruise" 85% of the ramp - i.e. it accelerates and
#      decelerates far more aggressively, which means MORE step-rate peaks per
#      millimetre. On a bed-slinger with 6000 mm/s2 this is the single most
#      punishing setting in the file.
#      -> 0.5 (Klipper default) is the safe, printer-friendly value.
#
#   3) [bed_mesh] speed: 300 + [screws_tilt_adjust] speed: 300
#      300 mm/s while probing = the Y bed (heavy!) slams between probe points,
#      and every point is a burst of tiny moves. That burst is exactly the
#      moment the shutdown happens.
#      -> 100 mm/s. Probing takes a little longer, the bus stays calm.
#
#   4) [pwm_cycle_time beeper] cycle_time: 0.001
#      Software PWM at 1 kHz = a permanent 1000 interrupts/second on the MCU,
#      even when nothing beeps. 0.01 (100 Hz) sounds the same for a piezo.
#
#   5) max_accel: 6000 -> 3500 for now
#      Halves the step-rate peaks. Put it back after we know the cause.
#
#   AND THE BIG ONE, NOT CHANGEABLE HERE:
#   6) [mcu] serial: /dev/ttyAMA0 with NO baud: line = 250000 baud.
#      That is the GPIO UART, not USB. Klipper's own docs recommend USB
#      exactly because the serial link is slower - and the header comment of
#      this very printer.cfg says "USB communication". 250000 baud is ~25 kB/s
#      for BOTH directions. A probe cycle (deploy, dwell, sample, retract,
#      stow, next point) is a burst of exactly the kind of tiny moves that
#      saturate it. THIS is the structural suspect.
#      Fix = baud: 1000000 in [mcu] AND the firmware flashed with 1000000.
#      This script does NOT touch it (needs a firmware flash - see the printout).
#
# USAGE
#   bash tools/r2_mcu_relief.sh            # show what it WOULD change (dry run)
#   bash tools/r2_mcu_relief.sh --apply    # change it (backup first)
#   bash tools/r2_mcu_relief.sh --revert   # restore the backup
#   bash tools/r2_mcu_relief.sh --status   # what is set right now
#
# The file is backed up next to itself: printer.cfg.r2bak-<timestamp>
set -u

CFG="${R2_PRINTER_CFG:-$HOME/printer_data/config/printer.cfg}"
STATE="${R2_RELIEF_STATE:-$HOME/printer_data/.r2_relief_backup}"
SUDO=""; [ "$(id -u)" = "0" ] || SUDO="sudo"

ok()   { printf '\033[32m[ok]\033[0m %s\n' "$*"; }
warn() { printf '\033[33m[!]\033[0m %s\n' "$*"; }
err()  { printf '\033[31m[x]\033[0m %s\n' "$*"; }
ask()  { printf '\033[36m->\033[0m %s\n' "$*"; }
hdr()  { printf '\n\033[1m%s\033[0m\n' "$*"; }

# ------------------------------------------------------------------ helpers --
# in_section <file> <section-regex> : print the line numbers of a section
section_body() {   # section_body <section-name-regex>
    awk -v s="$1" '
        BEGIN{IGNORECASE=1}
        $0 ~ "^\\[" s "[] ]" {p=1; print NR": "$0; next}
        p && /^\[/ {p=0}
        p {print NR": "$0}
    ' "$CFG"
}

do_status() {
    hdr "current values in $CFG"
    echo "--- the step-interrupt optimiser ---"
    n=$(grep -c '^[^#]*step_pulse_duration' "$CFG" 2>/dev/null || echo 0)
    if [ "$n" -gt 0 ]; then
        printf '  %s stepper(s) set step_pulse_duration  -> step-on-both-edges is OFF (2 interrupts per step)\n' "$n"
    else
        ok "no step_pulse_duration set -> step-on-both-edges ON (1 interrupt per step) - optimal"
    fi
    echo "--- acceleration / ramp ---"
    grep -nE '^[^#]*minimum_cruise_ratio|^[^#]*max_accel:|^[^#]*max_velocity:' "$CFG" 2>/dev/null | sed 's/^/  /'
    echo "--- probing speed ---"
    section_body bed_mesh | grep -E 'speed|probe_count' | sed 's/^/  bed_mesh: /'
    section_body screws_tilt_adjust | grep -E '^\s*[0-9]+: speed' | sed 's/^/  screws: /'
    echo "--- beeper pwm ---"
    section_body pwm_cycle_time | grep -E 'cycle_time' | sed 's/^/  /'
    echo "--- the link to the MCU (the structural point) ---"
    section_body mcu | grep -E 'serial|baud' | sed 's/^/  /'
    n=$(section_body mcu | grep -c 'baud' || true)
    if [ "${n:-0}" -eq 0 ]; then
        warn "  NO baud: line -> Klipper uses ${R2_DEFAULT_BAUD:-250000} baud on a serial link."
        warn "  1000000 baud (plus a matching firmware flash) is the real fix."
    fi
    [ -f "$STATE" ] && echo "backup exists: $STATE"
}

# apply one regex replacement, section-scoped when a section is given
patch() {   # patch <section|-> <regex> <replacement> <description>
    local sec="$1" re="$2" rep="$3" desc="$4"
    python3 - "$CFG" "$sec" "$re" "$rep" "$desc" <<'PY'
import re, sys
path, sec, rx, rep, desc = sys.argv[1:6]
txt = open(path, encoding='utf-8').read()
lines = txt.split('\n')
out, changed, in_sec = [], 0, (sec == '-')
cur = None
for ln in lines:
    m = re.match(r'^\s*\[([^\]]+)\]', ln)
    if m:
        cur = m.group(1)
        in_sec = (sec == '-') or bool(re.search(sec, cur, re.I))
    if in_sec and not ln.lstrip().startswith('#'):
        new = re.sub(rx, rep, ln)
        if new != ln:
            out.append(new); changed += 1; continue
    out.append(ln)
if changed:
    open(path, 'w', encoding='utf-8').write('\n'.join(out))
print('%-46s %s' % (desc, ('%d line(s) changed' % changed) if changed
                    else 'nothing to change (already ok?)'))
PY
}

# ------------------------------------------------------------------- apply ---
do_apply() {
    [ -r "$CFG" ] || { err "printer.cfg not found at $CFG"; \
                       err "set R2_PRINTER_CFG=/path/to/printer.cfg"; exit 1; }
    hdr "R2 MCU RELIEF - applying"
    if [ ! -f "$STATE" ]; then
        cp -p "$CFG" "$STATE" && ok "backup: $STATE"
    else
        warn "backup already exists ($STATE) - keeping the ORIGINAL one"
    fi

    # 1) the free one: let Klipper use step-on-both-edges again
    patch - '^(\s*)(step_pulse_duration:.*)$' '\1# R2 relief: commented - custom duration disables step-on-both-edges (2x interrupts)\n\1#\2' \
          "step_pulse_duration -> commented (halves step IRQs)"

    # 2) the ramp
    patch - '^(\s*minimum_cruise_ratio:\s*)0\.85(\s.*)?$' '\g<1>0.5\2' \
          "minimum_cruise_ratio 0.85 -> 0.5 (Klipper default)"

    # 3) probing speed
    patch '^bed_mesh$' '^(\s*speed:\s*)300(\s.*)?$' '\g<1>100\2' \
          "bed_mesh speed 300 -> 100"
    patch '^screws_tilt_adjust$' '^(\s*speed:\s*)300(\s.*)?$' '\g<1>100\2' \
          "screws_tilt speed 300 -> 100"

    # 4) beeper pwm load
    patch '^pwm_cycle_time' '^(\s*cycle_time:\s*)0\.001(\s.*)?$' '\g<1>0.01\2' \
          "beeper cycle_time 0.001 -> 0.01 (1000 Hz -> 100 Hz IRQs)"

    # 5) accel for the test window
    patch '^printer$' '^(\s*max_accel:\s*)6000(\s.*)?$' '\g<1>3500\2' \
          "max_accel 6000 -> 3500 (halves step-rate peaks)"

    echo
    ask "Now: sudo systemctl restart klipper"
    ask "Then print. If it runs through, the cause is on this side of the"
    ask "line (MCU load / link speed), not our macro package."
    echo
    warn "Everything back later:  bash $0 --revert"
    hdr "THE STRUCTURAL POINT - read this once"
    echo "  Your [mcu] uses serial: /dev/ttyAMA0 (GPIO UART) with no baud:"
    echo "  line, so it runs at 250000 baud = ~25 kB/s in BOTH directions."
    echo "  Klipper's docs recommend USB exactly because of this. The file"
    echo "  header even says 'USB communication'."
    echo
    echo "  The real fix:"
    echo "    1. add   baud: 1000000   under [mcu]"
    echo "    2. rebuild + flash the SKR firmware with the SAME 1000000"
    echo "       (make menuconfig -> Communication interface: serial"
    echo "        -> baud rate 1000000)"
    echo "    3. restart klipper"
    echo
    echo "  If you would rather go back to USB: change serial: to"
    echo "     serial: /dev/serial/by-id/usb-Klipper_stm32g0b1xx_..."
    echo "  (your commented line still has the exact ID) and flash with"
    echo "  'USB (on PA11/PA12)' instead - that is the robust path and it"
    echo "  needs no baud change at all."
}

do_revert() {
    [ -f "$STATE" ] || { err "no backup at $STATE - nothing to revert"; exit 1; }
    hdr "reverting printer.cfg"
    cp -p "$STATE" "$CFG" && ok "restored from $STATE"
    rm -f "$STATE"
    ask "sudo systemctl restart klipper"
    echo "Note: the RESTORE-CONFIG block at the bottom of printer.cfg"
    echo "(#*# ...) is untouched either way - your PID/mesh values are safe."
}

# ------------------------------------------------------------------- main ----
case "${1:-}" in
    --apply)  do_apply ;;
    --revert) do_revert ;;
    --status) do_status ;;
    -h|--help) sed -n '2,50p' "$0" ;;
    "")
        hdr "DRY RUN - would change (nothing written):"
        [ -r "$CFG" ] || { err "printer.cfg not found at $CFG"; \
                           err "set R2_PRINTER_CFG=/path/to/printer.cfg"; exit 1; }
        echo "  1. step_pulse_duration (all steppers) -> commented  [free: halves step IRQs]"
        echo "  2. minimum_cruise_ratio 0.85 -> 0.5"
        echo "  3. bed_mesh speed 300 -> 100"
        echo "  4. screws_tilt_adjust speed 300 -> 100"
        echo "  5. beeper cycle_time 0.001 -> 0.01"
        echo "  6. max_accel 6000 -> 3500"
        echo
        do_status
        echo
        ask "Apply with:  bash $0 --apply"
        ;;
    *) err "unknown option: $1"; echo "try: $0 --help"; exit 2 ;;
esac
