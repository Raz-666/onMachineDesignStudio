#!/usr/bin/env bash
# R2-D2 TRIAGE - collect EVERYTHING in ONE file, so nobody has to ask again.
#
# WHY: the last rounds cost days because information came in pieces. This
# script reads every fact needed to decide "our package or the machine"
# and writes them into a single, small, sendable file.
#
#   bash tools/r2_triage.sh
#   -> writes  ~/r2_triage_<timestamp>.txt   (and prints the path)
#
# It changes NOTHING. No sudo needed (uses it only to READ a few files
# when available). Send the whole file - it contains no toolpaths, no
# credentials, only printer/config/health data.
set -u

OUT="${HOME}/r2_triage_$(date +%Y%m%d-%H%M%S).txt"
SUDO=""; [ "$(id -u)" = "0" ] || SUDO="sudo"
CFG_DIR="${R2_CFG_DIR:-$HOME/printer_data/config}"
DATA_DIR="${R2_DATA_DIR:-$HOME/printer_data}"

sec() { printf '\n\n################ %s ################\n' "$*" >> "$OUT"; }
run() { printf '\n$ %s\n' "$*" >> "$OUT"; eval "$@" >> "$OUT" 2>&1 || \
        echo "  (command failed / not available)" >> "$OUT"; }
grab() {   # grab <file> [max lines] - tails a file into the report
    local f="$1" n="${2:-200}"
    printf '\n----- %s (last %s lines) -----\n' "$f" "$n" >> "$OUT"
    if [ -r "$f" ]; then tail -n "$n" "$f" >> "$OUT"
    else echo "  (not readable: $f)" >> "$OUT"; fi
}

{
echo "R2-D2 TRIAGE"
echo "generated: $(date -Iseconds)"
echo "host: $(uname -a)"
} > "$OUT"

# ---------------------------------------------------------------- version ---
sec "1. WHAT VERSION IS ACTUALLY INSTALLED"
grab "$CFG_DIR/klipper-e3-r2d2/macros/01_state.cfg" 12
run "grep -m1 'variable_version' '$CFG_DIR/klipper-e3-r2d2/macros/01_state.cfg' 2>/dev/null"
run "grep -m1 'POSTPROC_BUILD' '$CFG_DIR/klipper-e3-r2d2/tools/r2_postproc.py' 2>/dev/null"
run "cd '$CFG_DIR/klipper-e3-r2d2' 2>/dev/null && git log --oneline -3 2>/dev/null || echo '(no git)'"
run "ls -la '$CFG_DIR/klipper-e3-r2d2/tools/r2_postproc.py' 2>/dev/null"

# ------------------------------------------------------------------ health --
sec "2. HOST HEALTH (the zero-2-w budget)"
run "free -h"
run "cat /proc/loadavg"
run "nproc"
run "cat /proc/mounts | grep -w /proc"
run "vcgencmd measure_temp 2>/dev/null || echo '(vcgencmd n/a)'"
run "vcgencmd get_throttled 2>/dev/null || echo '(n/a)'"
run "df -h '$DATA_DIR' 2>/dev/null"
run "vmstat 1 3 2>/dev/null || echo '(no vmstat)'"

# --------------------------------------------------------------- services ---
sec "3. SERVICES"
run "systemctl is-active klipper moonraker r2-postproc crowsnest 2>/dev/null"
run "systemctl status r2-postproc --no-pager -l 2>/dev/null | head -20"
run "pgrep -af '[r]2_postproc.py' || echo '(no watcher running)'"

# --------------------------------------------------------- our runner state --
sec "4. EMERGENCY STATE (is safe mode active?)"
run "cat '$HOME/printer_data/.r2_emergency_state' 2>/dev/null || echo '(emergency mode never used)'"
run "grep -E 'mesh_mode|mesh_always' '$DATA_DIR/variables.cfg' 2>/dev/null || echo '(variables.cfg not found)'"
run "grep -c 'r2_menu' '$DATA_DIR/moonraker.conf' 2>/dev/null || echo '0'"

# ------------------------------------------------------------ printer.cfg ---
sec "5. printer.cfg - the sections that decide MCU load"
if [ -r "$CFG_DIR/printer.cfg" ]; then
    for S in stepper_x stepper_y stepper_z extruder probe bed_mesh tmc2209 \
             tmc2208 idle_timeout printer mcu; do
        printf '\n----- [%s] -----\n' "$S" >> "$OUT"
        _blk="$(awk -v s="[$S" '
            index($0, s) == 1 {p=1; print; next}
            p && /^\[/ {p=0}
            p {print}
        ' "$CFG_DIR/printer.cfg" 2>/dev/null | grep -vE '^\s*(#|$)')"
        if [ -n "$_blk" ]; then printf '%s\n' "$_blk" >> "$OUT"
        else echo "  (section not present in printer.cfg)" >> "$OUT"; fi
    done
else
    echo "  printer.cfg NOT READABLE at $CFG_DIR/printer.cfg" >> "$OUT"
    echo "  (set R2_CFG_DIR=/path/to/config if it lives elsewhere)" >> "$OUT"
fi

# ---------------------------------------------------------------- the crash --
sec "6. THE LAST CRASH (this is the evidence)"
KLIPPY=""
for f in "$DATA_DIR/logs/klippy.log" "$HOME/klippy.log" \
         "$HOME/printer_data/logs/klippy.log"; do
    [ -r "$f" ] && KLIPPY="$f" && break
done
if [ -n "$KLIPPY" ]; then
    printf '\nusing: %s (%s lines)\n' "$KLIPPY" "$(wc -l < "$KLIPPY")" >> "$OUT"
    printf '\n----- last MCU shutdown context (120 lines before) -----\n' >> "$OUT"
    L="$(grep -n 'Timer too close\|MCU .* shutdown\|is_shutdown\|Communication with MCU' "$KLIPPY" | tail -1 | cut -d: -f1)"
    if [ -n "$L" ]; then
        S=$(awk -v l="$L" 'BEGIN{print (l>120)? l-120 : 1}')
        sed -n "${S},${L}p" "$KLIPPY" >> "$OUT"
        printf '\n----- everything after it (40 lines) -----\n' >> "$OUT"
        sed -n "$((L+1)),$((L+40))p" "$KLIPPY" >> "$OUT"
    else
        echo "  NO shutdown found in this log - last 60 lines instead:" >> "$OUT"
        tail -60 "$KLIPPY" >> "$OUT"
    fi
    printf '\n----- reactor stall lines (the smoking gun) -----\n' >> "$OUT"
    grep -E 'busy for [0-9]+\.[0-9]+' "$KLIPPY" | tail -20 >> "$OUT" \
        || echo "  (none)" >> "$OUT"
    printf '\n----- every shutdown this log, with timestamp -----\n' >> "$OUT"
    grep -E 'MCU .*shutdown|Timer too close' "$KLIPPY" | tail -20 >> "$OUT" || true
else
    echo "klippy.log not found" >> "$OUT"
fi
for f in "$DATA_DIR/logs/moonraker.log"; do grab "$f" 40; done

# ------------------------------------------------------------ our own logs ---
sec "7. OUR WATCHER LOG"
run "journalctl -u r2-postproc --no-pager -n 60 2>/dev/null || echo '(no journal access)'"

# ------------------------------------------------------------ web extension --
sec "8. WEB EXTENSION"
run "grep -A4 -n 'r2_menu' '$DATA_DIR/moonraker.conf' 2>/dev/null || echo '(not installed)'"
run "ls -la '$DATA_DIR'/*.log 2>/dev/null | head -5"

# ------------------------------------------------------------------ summary --
sec "9. QUICK SELF-ASSESSMENT"
{
echo "An attempt at a summary (read by a human, not authoritative):"
echo "  klipper active ....... $(systemctl is-active klipper 2>/dev/null)"
echo "  watcher active ....... $(systemctl is-active r2-postproc 2>/dev/null)"
echo "  our version .......... $(grep -m1 'variable_version' "$CFG_DIR/klipper-e3-r2d2/macros/01_state.cfg" 2>/dev/null | tr -d ' ')"
echo "  mesh_mode ............ $(grep -m1 'mesh_mode' "$DATA_DIR/variables.cfg" 2>/dev/null | tr -d ' ')"
if [ -n "$KLIPPY" ]; then
  echo "  shutdowns in log ..... $(grep -c 'Timer too close' "$KLIPPY" 2>/dev/null)"
fi
echo "  free RAM ............ $(free -m 2>/dev/null | awk '/Mem:/{print $7" MB available"}')"
echo "  swap used ........... $(free -m 2>/dev/null | awk '/Swap:/{print $3" MB"}')"
} >> "$OUT"

echo >> "$OUT"
echo "=== END OF TRIAGE ===" >> "$OUT"

SZ="$(du -h "$OUT" | cut -f1)"
echo
echo "==============================================================="
echo "  TRIAGE WRITTEN: $OUT   ($SZ)"
echo "==============================================================="
echo "  Send this ONE file. Nothing else is needed."
echo
echo "  Quick look at the decisive line:"
grep -A2 'QUICK SELF-ASSESSMENT' "$OUT" | tail -n +2 | sed 's/^/   /'
echo
