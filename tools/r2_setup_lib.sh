#!/usr/bin/env bash
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Raz-666 and contributors
# =====================================================================================
#  r2_setup_lib.sh - shared wizard library for setup.sh + update.sh (R108)
#
#  Provides:
#    r2_lib_init                 set paths + mode (call first!)
#    r2_ask                      y/n question (EOF-safe, check-mode aware)
#    r2_ask_string               free-text input WITH confirmation
#    r2_confirm_value            numeric input WITH validation AND confirmation
#    r2_choice                   numbered choice WITH confirmation
#    r2_backup_candidates        FIRST STEP ALWAYS: backup every file this run
#                                might change + VERIFY the copies 1:1 (cmp)
#    r2_change_block             show a proposed block change + apply it in one
#                                of 4 modes (auto / commented-only / txt / skip)
#    r2_change_addline           same for a single setting under a config section
#    r2_hw_read / r2_hw_write    the r2_hardware.cfg profile (SECOND variables
#                                file: printer hardware values that survive a
#                                reset of the normal variables.cfg)
#    r2_hw_wizard                ask every hardware parameter (build volume,
#                                probe offsets, clean/present positions)
#    r2_led_wizard               LED chain + areas (status / bed light / nozzle,
#                                neopixel or dotstar, mainboard or EBB CAN;
#                                COLOR ORDER asked per chain - R110)
#    r2_apply_led_layout         regenerate the [led_effect] index ranges
#    r2_object_processing        show + explain + offer the moonraker toggle
#
#  Conventions:
#    - NOTHING is written to a USER file (printer.cfg / moonraker.conf / ...)
#      outside r2_change_* - and those always show the change first
#    - user lines are only ever COMMENTED OUT, never deleted
#    - r2_hardware.cfg is OUR file (setup-generated) - direct writes with a
#      .r2bak sidecar are fine there
# =====================================================================================

# ---- state ---------------------------------------------------------------------------
R2_CFG_DIR=""
R2_PKG_DIR=""
R2_TS=""
R2_CHECK=0
R2_SUDO=""
R2_CHANGE_MODE=""                      # '' ask per change | 1 | 2 | 3 | 4
R2_MODE_REMEMBER=1                      # 0 = ask again for the NEXT change
R2_MODE_FILE=""
R2_VALUE=""
R2_YN=""
declare -A R2_HW

r2_lib_init() {   # r2_lib_init <cfg_dir> <pkg_dir> <timestamp> <check 0/1> <sudo>
    R2_CFG_DIR="$1"
    R2_PKG_DIR="$2"
    R2_TS="$3"
    R2_CHECK="$4"
    R2_SUDO="$5"
    R2_MODE_FILE="${R2_CFG_DIR}/r2_manual_changes.txt"
}

r2_hwfile() { echo "${R2_CFG_DIR}/r2_hardware.cfg"; }
r2_printercfg() { echo "${R2_CFG_DIR}/printer.cfg"; }
r2_moonraker() { echo "${R2_CFG_DIR}/moonraker.conf"; }

# ---- questions -----------------------------------------------------------------------
r2_ask() {   # r2_ask "question" y|n  -> R2_YN=y|n    (EOF = safe default)
    local q="$1" d="${2:-n}" a=""
    if [ "${R2_CHECK}" = "1" ]; then
        echo "[i] (check mode) ${q} -> would ask (default: ${d})"
        R2_YN="${d}"
        return 0
    fi
    printf '%s' "${q} "
    if [ "${d}" = "y" ]; then printf '[Y/n]: '; else printf '[y/N]: '; fi
    if ! read -r a; then a=""; echo; fi
    a="$(printf '%s' "${a}" | tr '[:upper:]' '[:lower:]')"
    if [ -z "${a}" ]; then R2_YN="${d}"; return 0; fi
    case "${a}" in y|yes|j|ja) R2_YN="y" ;; *) R2_YN="n" ;; esac
}

r2_ask_string() {   # r2_ask_string "prompt" "default" -> R2_VALUE
    local prompt="$1" def="$2" a=""
    while :; do
        if [ "${R2_CHECK}" = "1" ]; then
            echo "[i] (check mode) ${prompt} -> would ask (default: ${def})"
            R2_VALUE="${def}"
            return 0
        fi
        printf '     %s [%s]: ' "${prompt}" "${def}"
        if ! read -r a; then a=""; echo; fi
        [ -z "${a}" ] && a="${def}"
        r2_ask "       you entered '${a}' - take it over?" y
        [ "${R2_YN}" = "y" ] && { R2_VALUE="${a}"; return 0; }
        echo "       (asking again - Enter keeps '${def}')"
    done
}

r2_confirm_value() {   # r2_confirm_value "prompt" default min max  -> R2_VALUE
    local prompt="$1" def="$2" min="$3" max="$4" a=""
    # R110 (found by the setup simulation): a DEFAULT outside min..max would
    # loop FOREVER - Enter keeps serving the invalid default, and on EOF
    # (non-interactive run) the loop never ends at all (setup.sh hung).
    # Clamp the default into range first and SAY so.
    if ! awk -v v="${def}" -v lo="${min}" -v hi="${max}" \
            'BEGIN{ exit !(v >= lo && v <= hi) }'; then
        def="$(awk -v v="${def}" -v lo="${min}" -v hi="${max}" \
            'BEGIN{ if (v < lo) printf "%s", lo; else if (v > hi) printf "%s", hi; else printf "%s", v }')"
        echo "       [i] the stored value is outside ${min}..${max} - continuing with ${def}"
    fi
    while :; do
        if [ "${R2_CHECK}" = "1" ]; then
            echo "[i] (check mode) ${prompt} -> would ask (default: ${def})"
            R2_VALUE="${def}"
            return 0
        fi
        printf '     %s [%s]: ' "${prompt}" "${def}"
        if ! read -r a; then a=""; echo; fi
        [ -z "${a}" ] && a="${def}"
        if ! printf '%s' "${a}" | grep -qE '^-?[0-9]+(\.[0-9]+)?$'; then
            echo "       [!] '${a}' is not a number - try again (or press Enter for ${def})"
            continue
        fi
        if awk -v v="${a}" -v lo="${min}" -v hi="${max}" \
               'BEGIN{ exit !(v >= lo && v <= hi) }'; then
            :
        else
            echo "       [!] ${a} is outside ${min}..${max} - try again (or press Enter for ${def})"
            continue
        fi
        # EVERY input is confirmed once more - mistakes can be corrected here
        r2_ask "       you entered '${a}' - take it over?" y
        [ "${R2_YN}" = "y" ] && { R2_VALUE="${a}"; return 0; }
        echo "       (asking again - Enter keeps the default ${def})"
    done
}

r2_choice() {   # r2_choice "prompt" default "opt1" "opt2" ... -> R2_VALUE=index
    local prompt="$1" def="$2"; shift 2
    local opts=("$@") a="" i
    while :; do
        if [ "${R2_CHECK}" = "1" ]; then
            echo "[i] (check mode) ${prompt} -> would ask (default: ${def})"
            R2_VALUE="${def}"
            return 0
        fi
        echo "     ${prompt}"
        i=1
        for o in "${opts[@]}"; do
            printf '       [%d] %s\n' "$i" "$o"
            i=$((i + 1))
        done
        printf '     choice [%s]: ' "${def}"
        if ! read -r a; then a=""; echo; fi
        [ -z "${a}" ] && a="${def}"
        if ! printf '%s' "${a}" | grep -qE '^[0-9]+$' \
           || [ "${a}" -lt 1 ] || [ "${a}" -gt "${#opts[@]}" ]; then
            echo "       [!] pick 1..${#opts[@]} (or press Enter for ${def})"
            continue
        fi
        r2_ask "       you picked '${a}' (${opts[$((a - 1))]}) - take it over?" y
        [ "${R2_YN}" = "y" ] && { R2_VALUE="${a}"; return 0; }
    done
}

r2_ask_color_order() {   # r2_ask_color_order "which LEDs" "GRB" -> R2_VALUE (validated)
    # The BYTE ORDER the LED chip expects - asked EXPLICITLY because a wrong
    # order swaps colors (red glows green). The .83 field log had exactly that
    # class of bug (GRBGR in printer.cfg.example halted Klipper). Menu of the
    # common chips + free input, both validated against what Klipper accepts.
    local which="$1" def="$2" a="" elem ndistinct
    local defidx=8
    case "${def}" in
        GRB)  defidx=1 ;;  RGB)  defidx=2 ;;  BRG)  defidx=3 ;;
        BGR)  defidx=4 ;;  RGBW) defidx=5 ;;  RBG)  defidx=6 ;;  GBR)  defidx=7 ;;
    esac
    while :; do
        if [ "${R2_CHECK}" = "1" ]; then
            echo "[i] (check mode) color order of the ${which} -> would ask (default: ${def})"
            R2_VALUE="${def}"
            return 0
        fi
        echo
        echo "     COLOR ORDER of the ${which} = the byte order the LED CHIP expects."
        echo "     It is NOT a color choice - it is the wiring inside the chip. A wrong"
        echo "     order swaps colors: a RED status then glows GREEN or BLUE."
        echo "     Where to find it: the LED datasheet or the shop page of the strip."
        echo "     Unsure? Take the default - after setup run the LED test (LCD: System >"
        echo "     LED Setup) and if red and green come out swapped, re-run setup.sh and"
        echo "     pick the other order. A wrong order breaks NOTHING - colors just swap."
        r2_choice "color order (Farbreihenfolge) of the ${which}?" "${defidx}" \
            "GRB  - WS2812 / WS2815 / SK6812 ('Neopixel' - the common case)" \
            "RGB  - WS2811 12 V strips, many older 12 V strips" \
            "BRG  - some WS2812 batches and LED panels" \
            "BGR  - APA102 / SK9822 ('dotstar' chips)" \
            "RGBW - SK6812-RGBW with a REAL white 4th chip" \
            "RBG  - rare (clone strips)" \
            "GBR  - rare (clone strips)" \
            "type it myself (or a comma list per LED, e.g. GRB,GRB,RGB)"
        a="${R2_VALUE}"
        case "${a}" in
            1) R2_VALUE="GRB";  return 0 ;;
            2) R2_VALUE="RGB";  return 0 ;;
            3) R2_VALUE="BRG";  return 0 ;;
            4) R2_VALUE="BGR";  return 0 ;;
            5) R2_VALUE="RGBW"; return 0 ;;
            6) R2_VALUE="RBG";  return 0 ;;
            7) R2_VALUE="GBR";  return 0 ;;
        esac
        # --- custom input: validate what Klipper accepts (3/4 letters R/G/B/W,
        #     optional comma list per LED, no duplicated letters in an element)
        r2_ask_string "color_order (letters R/G/B/W only, e.g. GRB; comma list = per LED)" "${def}"
        elem="${R2_VALUE%%,*}"
        ndistinct="$(printf '%s' "${elem}" | fold -w1 | sort -u | wc -l)"
        if printf '%s' "${R2_VALUE}" | grep -qE '^([RGBW]{3}|[RGBW]{4})(,([RGBW]{3}|[RGBW]{4}))*$' \
           && [ "${ndistinct}" -eq "${#elem}" ]; then
            return 0          # R2_VALUE already holds the validated order
        fi
        echo "       [!] '${R2_VALUE}' is not a color order Klipper understands -"
        echo "           3 or 4 DIFFERENT letters out of R/G/B/W (GRB, RGB, RGBW, ...),"
        echo "           optionally comma-separated per LED (GRB,GRB,RGB). Try again."
    done
}

# ---- backup + verify (ALWAYS the first step of setup AND update) ----------------------
r2_backup_one() {   # r2_backup_one <file> <backupdir> -> 0 ok / 1 FATAL (verified!)
    local f="$1" dir="$2" b=""
    [ -f "${f}" ] || return 0
    mkdir -p "${dir}" 2>/dev/null || { echo "[!] cannot create backup dir ${dir}"; return 1; }
    b="${dir}/$(basename "${f}")"
    cp "${f}" "${b}" || { echo "[!] backup FAILED: ${f}"; return 1; }
    if ! cmp -s "${f}" "${b}"; then
        # verify failed ONCE -> retry with a fresh copy, then it is fatal
        echo "[!] backup of ${f} did not verify - retrying once..."
        rm -f "${b}"
        cp "${f}" "${b}" 2>/dev/null
        if ! cmp -s "${f}" "${b}"; then
            echo "[!] BACKUP VERIFY FAILED for ${f} - NOTHING will be changed on this run!"
            return 1
        fi
    fi
    echo "[ok] backup verified 1:1: ${f} -> ${b}"
    return 0
}

r2_backup_candidates() {   # backs up everything this run could possibly touch
    local dir="${1:-${R2_CFG_DIR}/r2_backups/${R2_TS}}"
    local rc=0
    echo "--- backup FIRST (verified copy of everything this run might touch) -------------"
    if [ "${R2_CHECK}" = "1" ]; then
        echo "[i] (check mode) would back up printer.cfg, moonraker.conf, KAMP_Settings.cfg,"
        echo "    r2_hardware.cfg and macros/03_leds.cfg into ${dir}/ and verify them (cmp)"
        return 0
    fi
    local f
    for f in "$(r2_printercfg)" "$(r2_moonraker)" \
             "${R2_CFG_DIR}/KAMP_Settings.cfg" "$(r2_hwfile)" \
             "${R2_PKG_DIR}/macros/03_leds.cfg"; do
        r2_backup_one "${f}" "${dir}" || rc=1
    done
    [ -f /etc/systemd/system/r2-postproc.service ] && { r2_backup_one /etc/systemd/system/r2-postproc.service "${dir}" || rc=1; }
    if [ "${rc}" != "0" ]; then
        echo "[!] ABORT: a backup did not verify - no file will be modified (rule: verify first)"
        return 1
    fi
    echo "[ok] backup complete + verified: ${dir}"
    return 0
}

# ---- the 4 change modes --------------------------------------------------------------
r2_pick_mode() {   # -> R2_CHANGE_MODE (asks once, offers to remember)
    [ -n "${R2_CHANGE_MODE}" ] && return 0
    if [ "${R2_CHECK}" = "1" ]; then R2_CHANGE_MODE="4"; return 0; fi
    local a=""
    echo "     apply this change HOW?"
    echo "       [1] automatically      (your own conflicting lines are only COMMENTED OUT - never deleted)"
    echo "       [2] commented only     (the lines go in commented out - you remove the '# R2> ' marker yourself)"
    echo "       [3] separate txt file  (SAFEST: nothing in your files is touched - you copy by hand)"
    echo "       [4] skip this change"
    while :; do
        printf '     mode [3]: '
        if ! read -r a; then a=""; echo; fi
        [ -z "${a}" ] && a="3"
        case "${a}" in 1|2|3|4) break ;; *) echo "       [!] 1, 2, 3 or 4 (Enter = 3, the safest)";; esac
    done
    R2_CHANGE_MODE="${a}"
    R2_MODE_REMEMBER=1
    if [ "${R2_CHANGE_MODE}" != "4" ]; then
        r2_ask "     remember mode ${R2_CHANGE_MODE} for the rest of this run?" y
        [ "${R2_YN}" = "n" ] && R2_MODE_REMEMBER=0
    fi
    return 0
}

r2_mode_maybe_reset() {   # called AFTER a change ran: forget a not-remembered mode
    [ "${R2_MODE_REMEMBER:-1}" = "0" ] && R2_CHANGE_MODE=""
    return 0
}

r2_sidecar() {   # verified sidecar backup right before ANY user-file write
    local f="$1" b=""
    [ -f "${f}" ] || return 0
    b="${f}.r2bak.${R2_TS}"
    cp "${f}" "${b}" || return 1
    cmp -s "${f}" "${b}" && return 0
    rm -f "${b}"
    return 1
}

r2_txt_note() {   # r2_txt_note "title" "file" "where" "$block"
    local title="$1" file="$2" where="$3" block="$4"
    {
        echo ""
        echo "=== ${title} ==="
        echo "# target file : ${file}"
        echo "# where       : ${where}"
        echo "# (safest way: nothing was written to your files - copy the lines"
        echo "#  below to the marked place by hand. In printer.cfg ALWAYS insert"
        echo "#  BEFORE the '#*#' save_config block!)"
        printf '%s\n' "${block}"
    } >> "${R2_MODE_FILE}"
    echo "[ok] noted in ${R2_MODE_FILE}: ${title}"
}

r2_comment_matching() {   # r2_comment_matching <file> <egrep-regex> [regex] [regex]
    local f="$1"; shift
    local pats=("$@")
    local tmp="${f}.r2tmp.$$"
    [ "${#pats[@]}" -eq 0 ] && return 0
    awk -v pfx='# [R2-off] ' \
        -v re1="${pats[0]:-^^none^^}" -v re2="${pats[1]:-^^none^^}" -v re3="${pats[2]:-^^none^^}" '
        {
            line = $0
            if (line !~ /^[[:space:]]*#/ &&
                (line ~ re1 || line ~ re2 || line ~ re3)) {
                print pfx line
            } else {
                print line
            }
        }' "${f}" > "${tmp}" && mv "${tmp}" "${f}"
}

r2_insert_before_saveconfig() {   # printer.cfg: NEVER after the '#*#' block (.82!)
    # NOTE: the block goes through a TEMP FILE - passing multi-line strings
    # through 'awk -v' silently eats the newlines (mawk) - field log style
    # lesson from the R108 sandbox test. And the save_config marker is
    # matched LITERALLY (-F '#*#') - '^#*#' would match EVERY comment line
    # and drop the include at the top of the file!
    local f="$1" block="$2"
    local tmp="${f}.r2tmp.$$" btmp ln
    btmp="$(mktemp)"
    printf '%s\n' "${block}" > "${btmp}"
    ln="$(grep -n -F -- '#*#' "${f}" | head -1 | cut -d: -f1)"
    if [ -n "${ln}" ]; then
        head -n $((ln - 1)) "${f}" > "${tmp}"
        cat "${btmp}" >> "${tmp}"
        printf '\n' >> "${tmp}"
        tail -n +"${ln}" "${f}" >> "${tmp}"
        mv "${tmp}" "${f}"
    else
        printf '\n' >> "${f}"
        cat "${btmp}" >> "${f}"
    fi
    rm -f "${btmp}"
}

r2_change_block() {   # r2_change_block <file> <title> <block> [comment-regex ...]
    local f="$1" title="$2" block="$3"; shift 3
    local patterns=("$@")
    [ -f "${f}" ] || { echo "[!] ${f} not found - change skipped"; return 1; }
    echo
    echo "  --- proposed change to ${f}: ${title} ---"
    printf '%s\n' "${block}" | sed 's/^/      + /'
    if [ "${#patterns[@]}" -gt 0 ]; then
        echo "      (existing lines of yours matching: ${patterns[*]}"
        echo "       would ONLY be commented out - never deleted)"
    fi
    r2_pick_mode
    case "${R2_CHANGE_MODE}" in
        1)
            r2_sidecar "${f}" || { echo "[!] backup verify failed - change skipped"; return 1; }
            if [ "${#patterns[@]}" -gt 0 ]; then
                r2_comment_matching "${f}" "${patterns[@]}"
            fi
            local hdr="# --- R2 (added by setup.sh ${R2_TS}): ${title}"
            local withhdr
            withhdr="$(printf '%s\n%s' "${hdr}" "${block}")"
            if [ "$(basename "${f}")" = "printer.cfg" ]; then
                r2_insert_before_saveconfig "${f}" "${withhdr}"
            else
                printf '\n%s\n' "${withhdr}" >> "${f}"
            fi
            echo "[fix] ${f}: ${title} (applied)"
            ;;
        2)
            r2_sidecar "${f}" || { echo "[!] backup verify failed - change skipped"; return 1; }
            {
                printf '# vvv R2 suggestion - remove the leading "# R2> " to activate (added %s)\n' "${R2_TS}"
                printf '%s\n' "${block}" | sed 's/^/# R2> /'
            } >> "${f}"
            echo "[ok] ${f}: ${title} inserted COMMENTED - remove the '# R2> ' markers to activate"
            ;;
        3)
            r2_txt_note "${title}" "${f}" "end of file (printer.cfg: before the '#*#' block)" "${block}"
            ;;
        4)
            echo "[i] skipped: ${title}"
            ;;
    esac
    r2_mode_maybe_reset
    return 0
}

r2_change_addline() {   # r2_change_addline <file> <section> <key> <value> <title> [old-regex]
    # single setting under a config section (e.g. moonraker [file_manager])
    local f="$1" section="$2" key="$3" value="$4" title="$5" oldre="${6:-^[[:space:]]*enable_object_processing:}"
    [ -f "${f}" ] || { echo "[!] ${f} not found - change skipped"; return 1; }
    echo
    echo "  --- proposed change to ${f}: ${title} ---"
    if grep -qE "${oldre}" "${f}" 2>/dev/null; then
        echo "      current:"
        grep -nE "${oldre}" "${f}" | head -3 | sed 's/^/        /'
        echo "      new     : ${key}: ${value}   (your line above is only COMMENTED OUT)"
    else
        echo "      current : (not set)"
        echo "      new     : ${key}: ${value}   under [${section}]"
    fi
    r2_pick_mode
    case "${R2_CHANGE_MODE}" in
        1)
            r2_sidecar "${f}" || { echo "[!] backup verify failed - change skipped"; return 1; }
            r2_comment_matching "${f}" "${oldre}"
            if grep -qE "^\[${section}\]" "${f}"; then
                awk -v sec="${section}" -v ins="${key}: ${value}" '
                    !done && $0 ~ "^\\[" sec "\\]" { print; print ins; done = 1; next }
                    { print }
                    END { if (!done) { print ""; print "[" sec "]"; print ins } }
                ' "${f}" > "${f}.r2tmp.$$" && mv "${f}.r2tmp.$$" "${f}"
            else
                printf '\n[%s]\n%s: %s\n' "${section}" "${key}" "${value}" >> "${f}"
            fi
            echo "[fix] ${f}: ${title} (applied)"
            ;;
        2)
            r2_sidecar "${f}" || { echo "[!] backup verify failed - change skipped"; return 1; }
            if grep -qE "^\[${section}\]" "${f}"; then
                awk -v sec="${section}" -v ins="# R2> ${key}: ${value}" '
                    !done && $0 ~ "^\\[" sec "\\]" { print; print ins; done = 1; next }
                    { print }
                ' "${f}" > "${f}.r2tmp.$$" && mv "${f}.r2tmp.$$" "${f}"
            else
                printf '\n[%s]\n# R2> %s: %s\n' "${section}" "${key}" "${value}" >> "${f}"
            fi
            echo "[ok] ${f}: ${title} inserted COMMENTED - remove the '# R2> ' marker to activate"
            ;;
        3)
            r2_txt_note "${title}" "${f}" "under [${section}] (create the section if missing)" "${key}: ${value}"
            ;;
        4)
            echo "[i] skipped: ${title}"
            ;;
    esac
    r2_mode_maybe_reset
    return 0
}

# ---- the hardware profile (r2_hardware.cfg) -------------------------------------------
r2_hw_read() {
    R2_HW=()
    local src="" inside=false ls_ k v
    # 1st: the dedicated profile file, 2nd: a legacy block inside printer.cfg
    for src in "$(r2_hwfile)" "$(r2_printercfg)"; do
        [ -f "${src}" ] || continue
        inside=false
        while IFS= read -r l || [ -n "${l}" ]; do
            ls_="$(printf '%s' "${l}" | sed 's/[[:space:]]*$//')"
            case "${ls_}" in
                \[*\]) case "${ls_}" in
                            "[gcode_macro _R2_CONFIG]") inside=true ;;
                            *) inside=false ;;
                        esac ;;
                *)  if ${inside} && printf '%s' "${ls_}" | grep -q '^variable_'; then
                        k="${ls_%%:*}"; k="${k#variable_}"; k="${k//[[:space:]]/}"
                        v="${ls_#*:}"; v="${v#"${v%%[![:space:]]*}"}"
                        v="${v%%#*}"; v="${v//[[:space:]]/}"
                        v="${v//\'/}"; v="${v//\"/}"
                        R2_HW["${k}"]="${v}"
                    fi ;;
            esac
        done < "${src}"
        # values from the profile file WIN - stop after it if it exists
        [ "${src}" = "$(r2_hwfile)" ] && [ "${#R2_HW[@]}" -gt 0 ] && break
    done
}

r2_hw_write() {   # regenerates r2_hardware.cfg from R2_HW (keeping unknown keys)
    local hw; hw="$(r2_hwfile)"
    local tmp="${hw}.r2tmp.$$"
    {
        echo "# ====================================================================================="
        echo "# R2 hardware profile - generated by the setup wizard ${R2_TS}"
        echo "#"
        echo "# This is the SECOND variables file: printer-specific hardware values"
        echo "# (build volume, probe offset, clean/present positions, LED layout)."
        echo "# It deliberately does NOT live in variables.cfg - resetting your print"
        echo "# settings (deleting variables.cfg) can never lose these. Edit here, via"
        echo "# setup.sh / update.sh, or from the LCD (System > LED Setup)."
        echo "# ====================================================================================="
        echo "[gcode_macro _R2_CONFIG]"
        echo "description: R2 hardware profile (bed limits + positions + LED layout) - macros AND watcher read this"
        for k in bed_min_x bed_max_x bed_min_y bed_max_y bed_max_z \
                 probe_x probe_y present_x present_y wipe_x wipe_y \
                 led_type led_section led_pin led_clk_pin led_chain led_color_order \
                 led_status_n led_bed_n led_bed_on led_bed_bright \
                 led_nozzle_split led_nozzle_section led_nozzle_pin led_nozzle_chain \
                 led_nozzle_color_order; do
            [ -n "${R2_HW[${k}]:-}" ] && printf 'variable_%s: %s\n' "${k}" "${R2_HW[${k}]}"
        done
        # keep keys we do not know (future versions / hand edits)
        local kk
        for kk in "${!R2_HW[@]}"; do
            case "${kk}" in
                bed_min_x|bed_max_x|bed_min_y|bed_max_y|bed_max_z|probe_x|probe_y|\
                present_x|present_y|wipe_x|wipe_y|led_type|led_section|led_pin|\
                led_clk_pin|led_chain|led_color_order|led_status_n|led_bed_n|\
                led_bed_on|led_bed_bright|led_nozzle_split|led_nozzle_section|\
                led_nozzle_pin|led_nozzle_chain|led_nozzle_color_order) ;;
                *) printf 'variable_%s: %s\n' "${kk}" "${R2_HW[${kk}]}" ;;
            esac
        done
        echo "gcode:"
        echo "    # config carrier only - never runs"
        echo ""
        # the LCD persister - ONLY when the shell-command extension exists
        if [ -f "${R2_KLIPPER_DIR:-${HOME}/klipper}/klippy/extras/gcode_shell_command.py" ]; then
            echo "# LCD edits (System > LED Setup) persist through this helper:"
            echo "[gcode_shell_command R2_PERSIST]"
            echo "command: bash ${R2_PKG_DIR}/tools/r2_persist.sh"
            echo "timeout: 10."
            echo "verbose: False"
        else
            echo "# (LCD persistence needs the gcode_shell_command extension - not installed;"
            echo "#  LCD LED edits then apply to the running session only. KIAUH installs it.)"
        fi
    } > "${tmp}"
    [ -f "${hw}" ] && cp "${hw}" "${hw}.r2bak"
    mv "${tmp}" "${hw}"
    echo "[fix] hardware profile written: ${hw}"
}

r2_ensure_include() {   # [include r2_hardware.cfg] in printer.cfg (4 modes)
    local pc; pc="$(r2_printercfg)"
    [ -f "${pc}" ] || return 0
    grep -qE '^\[include r2_hardware\.cfg\]' "${pc}" && return 0
    r2_change_block "${pc}" "include the R2 hardware profile" \
        "[include r2_hardware.cfg]"
}

r2_migrate_legacy_block() {   # active [gcode_macro _R2_CONFIG] inside printer.cfg
    local pc; pc="$(r2_printercfg)"
    [ -f "${pc}" ] || return 1
    grep -qE '^\[gcode_macro _R2_CONFIG\]' "${pc}" || return 1
    echo
    echo "  --- proposed change to ${pc}: move [gcode_macro _R2_CONFIG] to r2_hardware.cfg ---"
    echo "      your values were carried over into the new profile file. The old block"
    echo "      in printer.cfg would be COMMENTED OUT (never deleted) and replaced by"
    echo "      one include line - two active copies would make Klipper refuse to boot."
    r2_pick_mode
    case "${R2_CHANGE_MODE}" in
        1)
            if r2_sidecar "${pc}"; then
                python3 - "${pc}" << 'R2MIG_PY'
import re, sys
p = sys.argv[1]
s = open(p, encoding='utf-8', errors='surrogateescape').read()
def comment(m):
    return '\n'.join('# [R2-off] ' + l if l.strip() else l for l in m.group(0).rstrip().split('\n'))
# consume ONLY macro-block lines: variable_/description:/gcode: headers,
# indented body lines and blanks - a following comment (like our own
# '# --- R2' insert header) must NOT be swallowed
s2 = re.sub(r'\n?\[gcode_macro _R2_CONFIG\]\n(?:[ \t]*(?:variable_|description:|gcode:)[^\n]*\n|[ \t]+[^\n]*\n|[ \t]*\n)*', comment, s, count=1)
inc = '[include r2_hardware.cfg]'
if inc not in s2:
    i = s2.find('\n#*#')
    if i >= 0:
        s2 = s2[:i].rstrip('\n') + '\n\n# --- R2: hardware profile (replaces the commented block above)\n' + inc + s2[i:]
    else:
        s2 = s2.rstrip('\n') + '\n\n# --- R2: hardware profile (replaces the commented block above)\n' + inc + '\n'
open(p, 'w', encoding='utf-8', errors='surrogateescape').write(s2)
R2MIG_PY
                echo "[fix] printer.cfg: old block commented out + [include r2_hardware.cfg] added"
                return 0
            else
                echo "[!] backup verify failed - migration skipped"
                return 1
            fi
            ;;
        2|3)
            r2_txt_note "replace the [gcode_macro _R2_CONFIG] block with the include" "${pc}" \
                "comment out the whole old block (never delete it), then insert BEFORE '#*#'" \
                "[include r2_hardware.cfg]"
            echo "[i] your block stays ACTIVE - r2_hardware.cfg waits unused until you swap by hand"
            echo "    (two active copies would halt Klipper - that is why nothing was written)"
            return 1
            ;;
        4)
            echo "[i] skipped - r2_hardware.cfg waits unused (add the include by hand later)"
            return 1
            ;;
    esac
    r2_mode_maybe_reset
    return 1
}

# ---- LED layout ------------------------------------------------------------------------
r2_apply_led_layout() {   # regenerate [led_effect] ranges from the hw profile
    local hw; hw="$(r2_hwfile)"
    [ -f "${hw}" ] || return 0
    r2_hw_read
    # no LED chain configured (wizard answered 'no LEDs')? nothing to regenerate
    # - and NO phantom led_status_n key may appear in the profile (R110 sim)
    [ -n "${R2_HW[led_type]:-}" ] || return 0
    local sn="${R2_HW[led_status_n]:-4}"
    # r2_persist.sh rewrites the value (same value = no-op edit) AND regenerates
    # the effect ranges + the split-effect comment state - one code path for all
    bash "${R2_PKG_DIR}/tools/r2_persist.sh" led_status_n "${sn}" >/dev/null 2>&1 || \
        echo "[!] LED layout regeneration failed (tools/r2_persist.sh)"
}

r2_led_detect() {   # prints "type section" of the first LED chain found
    local f hit
    for f in "$(r2_printercfg)" "$(r2_hwfile)"; do
        [ -f "${f}" ] || continue
        hit="$(grep -E '^\[(neopixel|dotstar) ' "${f}" 2>/dev/null | head -1 || true)"
        if [ -n "${hit}" ]; then
            printf '%s' "${hit#[}"; printf '\n'
            return 0
        fi
    done
    return 1
}

r2_led_wizard() {
    echo
    echo "--- LED wizard (chain + areas) ----------------------------------------------------"
    if [ "${R2_CHECK}" = "1" ]; then
        echo "[i] (check mode) would run the LED wizard (used? type, pins, chain_count,"
        echo "    COLOR ORDER per chain, status / bed-light / nozzle areas, EBB split,"
        echo "    brightness)"
        return 0
    fi
    r2_hw_read
    local det=""
    det="$(r2_led_detect)" || true
    if [ -n "${det}" ]; then
        echo "[ok] LED chain detected in your config: ${det}"
        r2_ask "Configure LEDs on this printer?" n
    else
        echo "[i] no [neopixel] / [dotstar] found in printer.cfg"
        r2_ask "Use LEDs on this printer (configure them now)?" n
    fi
    [ "${R2_YN}" = "n" ] && { echo "[i] LEDs skipped - everything keeps working without them"; return 0; }

    # --- type + section
    r2_choice "LED type?" "1" "neopixel (WS2812 - one data pin, the common case)" "dotstar (APA102 - data + clock pin)"
    local ltype="neopixel"; [ "${R2_VALUE}" = "2" ] && ltype="dotstar"
    r2_ask_string "section name in the config (letters/digits/_)" "${R2_HW[led_section]:-printer_leds}"
    local lsec; lsec="$(printf '%s' "${R2_VALUE}" | tr -cd '[:alnum:]_')"
    [ -z "${lsec}" ] && lsec="printer_leds"

    # --- pins + chain
    local pin clk cc co
    pin="${R2_HW[led_pin]:-PA8}"
    clk="${R2_HW[led_clk_pin]:-PB0}"
    cc="${R2_HW[led_chain]:-5}"
    co="${R2_HW[led_color_order]:-}"
    if [ -z "${co}" ]; then
        if [ "${ltype}" = "dotstar" ]; then co="BGR"; else co="GRB"; fi
    fi
    if [ "${ltype}" = "neopixel" ]; then
        r2_ask_string "data pin (SKR mini E3 v3: PA8 / EBB42 RGB port: EBB:PD3)" "${pin}"
        pin="${R2_VALUE}"
    else
        r2_ask_string "data_pin" "${pin}"
        pin="${R2_VALUE}"
        r2_ask_string "clock_pin" "${clk}"
        clk="${R2_VALUE}"
    fi
    r2_confirm_value "total LEDs in the main chain" "${cc}" 1 60
    cc="${R2_VALUE}"
    # color order: asked for BOTH types - a dotstar wired as BGR shows the same
    # swapped-color mess as a wrong neopixel order (.83 field log)
    r2_ask_color_order "main-chain LEDs" "${co}"
    co="${R2_VALUE}"

    # --- areas (status / bed light / nozzle)
    r2_confirm_value "status LEDs (animated R2 effects) - first LEDs of the chain" "${R2_HW[led_status_n]:-4}" 0 "${cc}"
    local sn="${R2_VALUE}"
    local maxbed=$((cc - sn)); [ "${maxbed}" -lt 0 ] && maxbed=0
    r2_confirm_value "bed work-light LEDs (steady white, own switch) - after the status LEDs" "${R2_HW[led_bed_n]:-0}" 0 "${maxbed}"
    local bn="${R2_VALUE}"
    local free=$((cc - sn - bn))
    echo "     -> ${sn} status + ${bn} bed + ${free} still free in the chain"
    local noz=3
    if [ "${free}" -ge 1 ]; then
        r2_choice "nozzle LED (work light at the toolhead)?" 1 \
            "last LED of the main chain" \
            "own chain on another board (e.g. the EBB42 over CAN)" \
            "none"
        noz="${R2_VALUE}"
    else
        echo "     (no LEDs left in the main chain - nozzle needs its own chain or none)"
        noz=2
    fi
    local split=0 nsec npin ncc
    nsec="${R2_HW[led_nozzle_section]:-nozzle_led}"
    npin="${R2_HW[led_nozzle_pin]:-EBB:PD3}"
    ncc="${R2_HW[led_nozzle_chain]:-2}"
    if [ "${noz}" = "2" ]; then
        split=1
        r2_ask_string "nozzle chain section name" "${nsec}"
        nsec="$(printf '%s' "${R2_VALUE}" | tr -cd '[:alnum:]_')"
        [ -z "${nsec}" ] && nsec="nozzle_led"
        r2_ask_string "nozzle chain pin (EBB42 RGB port: EBB:PD3)" "${npin}"
        npin="${R2_VALUE}"
        r2_confirm_value "nozzle LEDs in the own chain (max ~15 at full white on the EBB port)" "${ncc}" 1 15
        ncc="${R2_VALUE}"
        r2_ask_color_order "nozzle-chain LEDs" "${R2_HW[led_nozzle_color_order]:-GRB}"
        R2_HW[led_nozzle_color_order]="${R2_VALUE}"
    fi
    r2_confirm_value "bed work-light brightness (0.0-0.5 - the power cap!)" "${R2_HW[led_bed_bright]:-0.4}" 0 0.5
    local bbr="${R2_VALUE}"

    # --- summary + final confirmation
    echo
    echo "     LED setup summary:"
    echo "       main chain : ${ltype} '${lsec}' on pin ${pin}, ${cc} LEDs, color_order ${co}"
    echo "       areas      : LED 1-${sn} status (animated) | LED $((sn + 1))-$((sn + bn)) bed light$( [ "${bn}" = "0" ] && printf ' (off)')"
    if [ "${noz}" = "1" ]; then
        echo "       nozzle     : LED $((sn + bn + 1)) of the main chain"
    elif [ "${noz}" = "2" ]; then
        echo "       nozzle     : OWN chain '${nsec}' on pin ${npin}, ${ncc} LEDs, color_order ${R2_HW[led_nozzle_color_order]:-GRB}"
    else
        echo "       nozzle     : none"
    fi
    echo "       bed light  : brightness ${bbr} (switchable from the LCD)"
    r2_ask "     write this LED setup?" y
    [ "${R2_YN}" = "n" ] && { echo "[i] LED setup discarded"; return 0; }

    R2_HW[led_type]="${ltype}"
    R2_HW[led_section]="${lsec}"
    R2_HW[led_status_n]="${sn}"
    R2_HW[led_bed_n]="${bn}"
    R2_HW[led_bed_bright]="${bbr}"
    R2_HW[led_nozzle_split]="${split}"
    R2_HW[led_nozzle_section]="${nsec}"
    R2_HW[led_pin]="${pin}"
    R2_HW[led_clk_pin]="${clk}"
    R2_HW[led_chain]="${cc}"
    R2_HW[led_color_order]="${co}"
    [ "${split}" = "1" ] && { R2_HW[led_nozzle_pin]="${npin}"; R2_HW[led_nozzle_chain]="${ncc}"; }

    # [neopixel]/[dotstar] section: an existing one in printer.cfg is KEPT as is;
    # otherwise it goes into r2_hardware.cfg (OUR file - no user-file edit!)
    local pc; pc="$(r2_printercfg)"
    local have_sec=0
    if [ -f "${pc}" ] && grep -qE "^\[${ltype} ${lsec}\]" "${pc}"; then
        have_sec=1
        echo "[ok] [${ltype} ${lsec}] already lives in printer.cfg - kept untouched"
        if ! grep -A3 -E "^\[${ltype} ${lsec}\]" "${pc}" | grep -qE '^\s*chain_count:'; then
            echo "[!] that section has no chain_count line - please check it by hand"
        fi
        local _eco
        _eco="$(grep -A8 -E "^\[${ltype} ${lsec}\]" "${pc}" | sed -n 's/^[[:space:]]*color_order:[[:space:]]*//p' | head -1)"
        if [ -n "${_eco}" ]; then
            echo "[i] your section sets color_order ${_eco} (you picked ${co} - the wizard"
            echo "    never edits an existing user section; align them by hand if needed)"
        else
            echo "[i] your section sets NO color_order - Klipper then defaults to GRB"
            echo "    (you picked ${co} - add the line by hand if that is wrong)"
        fi
    fi
    r2_hw_write
    if [ "${have_sec}" = "0" ]; then
        # write the LED section into OUR profile file (direct, sidecar-backed)
        local hw; hw="$(r2_hwfile)"
        cp "${hw}" "${hw}.r2bak"
        {
            echo ""
            echo "# --- LED chain (added by the LED wizard ${R2_TS}) ---"
            echo "[${ltype} ${lsec}]"
            if [ "${ltype}" = "neopixel" ]; then
                echo "pin: ${pin}"
            else
                echo "data_pin: ${pin}"
                echo "clock_pin: ${clk}"
            fi
            echo "chain_count: ${cc}"
            echo "color_order: ${co}"
            if [ "${split}" = "1" ]; then
                echo ""
                echo "[${ltype} ${nsec}]"
                echo "pin: ${npin}"
                echo "chain_count: ${ncc}"
                echo "color_order: ${R2_HW[led_nozzle_color_order]:-GRB}"
            fi
        } >> "${hw}"
        echo "[fix] [${ltype} ${lsec}] written into ${hw} (active via the profile include)"
    fi
    r2_ensure_include
    r2_apply_led_layout
    echo "[i] FIRMWARE_RESTART now activates the LED config (LCD goes dark briefly)."
    echo "    Afterwards: System > LED Setup on the LCD shows + tunes the areas."
}

# ---- hardware wizard --------------------------------------------------------------------
r2_hw_wizard() {
    echo
    echo "--- hardware profile wizard (build volume, probe, positions) ----------------------"
    if [ "${R2_CHECK}" = "1" ]; then
        echo "[i] (check mode) would run the hardware wizard (bed min/max X/Y, Z height,"
        echo "    probe type + x/y offset, nozzle-clean wipe position, part presentation)"
        return 0
    fi
    r2_hw_read
    local hw; hw="$(r2_hwfile)"
    if [ -f "${hw}" ] && [ "${#R2_HW[@]}" -gt 0 ]; then
        echo "[ok] hardware profile exists: ${hw}"
        local k
        for k in bed_min_x bed_max_x bed_min_y bed_max_y bed_max_z probe_x probe_y present_x present_y wipe_x wipe_y; do
            [ -n "${R2_HW[${k}]:-}" ] && printf '       %-12s %s\n' "${k}:" "${R2_HW[${k}]}"
        done
        r2_ask "Keep the current hardware settings?" y
        [ "${R2_YN}" = "y" ] && { r2_ensure_include; r2_apply_led_layout; return 0; }
        echo "[i] re-asking everything (Enter keeps each current value)"
    else
        echo "[i] no hardware profile yet - defaults in brackets fit the Ender-3 reference."
        echo "    EVERY value gets asked - on ANOTHER printer (bed size, probe, ...) answer"
        echo "    them all; each entry is confirmed before it is taken over."
    fi

    r2_confirm_value "printable bed min X (mm)" "${R2_HW[bed_min_x]:-0.0}" -500 500
    R2_HW[bed_min_x]="${R2_VALUE}"
    r2_confirm_value "printable bed max X (mm)" "${R2_HW[bed_max_x]:-220.0}" 20 2000
    R2_HW[bed_max_x]="${R2_VALUE}"
    r2_confirm_value "printable bed min Y (mm)" "${R2_HW[bed_min_y]:--3.0}" -500 500
    R2_HW[bed_min_y]="${R2_VALUE}"
    r2_confirm_value "printable bed max Y (mm)" "${R2_HW[bed_max_y]:-217.0}" 20 2000
    R2_HW[bed_max_y]="${R2_VALUE}"
    r2_confirm_value "build height Z (mm)" "${R2_HW[bed_max_z]:-250.0}" 20 3000
    R2_HW[bed_max_z]="${R2_VALUE}"

    echo
    r2_choice "probe on the toolhead?" "1" \
        "BLTouch" "micro probe (e.g. the MicroProbe)" "other probe (Klicky, Euclid, ...)" "none - manual paper leveling"
    local pt="${R2_VALUE}"
    R2_HW[probe_type]="${pt}"
    if [ "${pt}" != "4" ]; then
        r2_confirm_value "probe X offset (mm, probe-relative; negative = left of the nozzle)" "${R2_HW[probe_x]:-0.0}" -200 200
        R2_HW[probe_x]="${R2_VALUE}"
        r2_confirm_value "probe Y offset (mm; negative = in front of the nozzle)" "${R2_HW[probe_y]:-0.0}" -200 200
        R2_HW[probe_y]="${R2_VALUE}"
        echo "     [i] the offsets live in the hardware profile now. Klipper's own"
        echo "         [probe]/[bltouch] section in printer.cfg stays the truth for probing -"
        echo "         if it has no x_offset/y_offset yet, add yours there by hand."
    else
        R2_HW[probe_x]="${R2_HW[probe_x]:-0.0}"
        R2_HW[probe_y]="${R2_HW[probe_y]:-0.0}"
    fi

    echo
    r2_confirm_value "nozzle-clean (wipe) X, -1 = axis-minimum corner" "${R2_HW[wipe_x]:--1.0}" -1 2000
    R2_HW[wipe_x]="${R2_VALUE}"
    r2_confirm_value "nozzle-clean (wipe) Y, -1 = axis-minimum corner" "${R2_HW[wipe_y]:--1.0}" -1 2000
    R2_HW[wipe_y]="${R2_VALUE}"
    r2_confirm_value "part presentation X after prints" "${R2_HW[present_x]:-10.0}" -500 2000
    R2_HW[present_x]="${R2_VALUE}"
    r2_confirm_value "part presentation Y after prints" "${R2_HW[present_y]:-228.0}" -500 2000
    R2_HW[present_y]="${R2_VALUE}"

    echo
    echo "     hardware profile summary:"
    local k
    for k in bed_min_x bed_max_x bed_min_y bed_max_y bed_max_z probe_x probe_y present_x present_y wipe_x wipe_y; do
        printf '       %-12s %s\n' "${k}:" "${R2_HW[${k}]:-}"
    done
    r2_ask "     write r2_hardware.cfg with these values?" y
    [ "${R2_YN}" = "n" ] && { echo "[i] hardware profile discarded"; return 0; }
    r2_hw_write
    r2_ensure_include
    # a legacy active block in printer.cfg must move (two copies would halt Klipper)
    r2_migrate_legacy_block || true
}

# ---- moonraker object processing ---------------------------------------------------------
r2_object_processing() {   # shows state + explains + offers BOTH directions
    local mr; mr="$(r2_moonraker)"
    echo
    echo "--- moonraker object processing (KAMP adaptive + LCD Skip Objects) ----------------"
    if [ ! -f "${mr}" ]; then
        echo "[i] moonraker.conf not found at ${mr} - nothing to check"
        return 0
    fi
    local cur="not set (moonraker default: off)"
    if grep -qE '^[[:space:]]*enable_object_processing:[[:space:]]*[Tt]rue' "${mr}" 2>/dev/null; then
        cur="ON"
    elif grep -qE '^[[:space:]]*enable_object_processing:[[:space:]]*[Ff]alse' "${mr}" 2>/dev/null; then
        cur="OFF"
    elif grep -qE '^[[:space:]]*#*[[:space:]]*enable_object_processing:' "${mr}" 2>/dev/null; then
        cur="present but commented out (= off)"
    fi
    echo "[i] current setting: ${cur}"
    echo "     WHAT it does: moonraker analyses every UPLOADED g-code file and computes"
    echo "       the object outlines itself. Files whose slicer did not embed them get"
    echo "       object data anyway -> KAMP can mesh/purge adaptively and the LCD"
    echo "       'Skip Objects' menu works for them too."
    echo "     WHY keep it OFF on a small Pi (Pi Zero 2 W / Pi 3): the analysis runs on"
    echo "       every upload and costs RAM + CPU - your own moonraker.conf comment"
    echo "       warns about exactly that. With it off, KAMP meshes full-bed on such"
    echo "       files and the purge falls back to our own line - both fine."
    echo "     WHY turn it ON: strong host (Pi 4/5, x86) or your slicer embeds object"
    echo "       data anyway (OrcaSlicer 'Label objects') - then it costs nothing."
    if [ "${R2_CHECK}" = "1" ]; then
        echo "[i] (check mode) would offer: keep / enable / disable (with the 4 apply modes)"
        return 0
    fi
    r2_choice "object processing?" 1 "keep as is (${cur})" "turn ON (enable_object_processing: True)" "turn OFF (enable_object_processing: False)"
    [ "${R2_VALUE}" = "1" ] && { echo "[ok] kept as is"; return 0; }
    local val="True"; [ "${R2_VALUE}" = "3" ] && val="False"
    r2_change_addline "${mr}" "file_manager" "enable_object_processing" "${val}" \
        "moonraker object processing ${val}"
    echo "[i] restart moonraker to activate:  ${R2_SUDO} systemctl restart moonraker"
}
