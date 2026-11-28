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
#                                COLOR ORDER asked per chain - R110)
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
        echo "    r2_hardware.cfg into ${dir}/ and verify them (cmp)"
        return 0
    fi
    local f
    for f in "$(r2_printercfg)" "$(r2_moonraker)" \
             "${R2_CFG_DIR}/KAMP_Settings.cfg" "$(r2_hwfile)" \
; do
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

r2_hw_needs_literal_fix() {   # 0 = the profile has a value Klipper cannot parse
    # R282 (field boot halt): Klipper runs ast.literal_eval on every
    # variable_* value of a gcode_macro. A bare word (e.g. 'variable_foo:
    # neopixel') is a Name node -> 'not a valid literal', Klipper REFUSES
    # TO BOOT. Heuristic tripwire for the update keep path (the setup sim
    # runs the exact ast parser as the authority): a value is fine when it
    # starts quoted, looks like a number, or is a True/False/None/collection
    # literal - anything else (a bare word) needs the re-render.
    local hw; hw="$(r2_hwfile)"
    [ -f "${hw}" ] || return 1
    local in282=0 l282 v282
    while IFS= read -r l282; do
        case "${l282}" in
            \[*)
                if [ "$(printf '%s' "${l282}" | tr 'A-Z' 'a-z')" = "[gcode_macro _r2_config]" ]; then
                    in282=1
                else
                    in282=0
                fi ;;
            variable_*:*)
                [ "${in282}" = "1" ] || continue
                v282="${l282#*:}"
                v282="${v282#"${v282%%[![:space:]]*}"}"   # leading ws
                v282="${v282%%#*}"                          # trailing comment
                case "${v282}" in
                    "'"*|'"'*|-*|[0-9]*|True|False|None|\[*|\{*|\(*) ;;
                    *) return 0 ;;
                esac ;;
        esac
    done < "${hw}"
    return 1
}

r2_hw_quote() {   # variable value -> a value Klipper can BOOT: plain numbers
                  # raw, everything else a quoted Python string. R282 (field
                  # boot halt): the wizard wrote 'variable_led_type: neopixel'
                  # BARE - Klipper runs ast.literal_eval on every variable_*
                  # value of a gcode_macro and REFUSED TO START ('not a valid
                  # literal: <ast.Name object>'). r2_hw_read strips quotes on
                  # the way in, so old and new files read identically.
    local v="$1"
    if printf '%s' "${v}" | grep -qE '^-?[0-9]+(\.[0-9]+)?$'; then
        printf '%s' "${v}"
    else
        v="${v//\\/\\\\}"
        v="${v//\'/\\\'}"
        printf "'%s'" "${v}"
    fi
}

r2_hw_write() {   # regenerates r2_hardware.cfg from R2_HW (keeping unknown keys)
    local hw; hw="$(r2_hwfile)"
    local tmp="${hw}.r2tmp.$$"
    {
        echo "# ====================================================================================="
        echo "# R2 hardware profile - generated by the setup wizard ${R2_TS}"
        echo "#"
        echo "# This is the SECOND variables file: printer-specific hardware values"
        echo "# (build volume, probe offset, clean/present positions)."
        echo "# It deliberately does NOT live in variables.cfg - resetting your print"
        echo "# settings (deleting variables.cfg) can never lose these. Edit here, via"
        echo "# setup.sh / update.sh."
        echo "# ====================================================================================="
        echo "[gcode_macro _R2_CONFIG]"
        echo "description: R2 hardware profile (bed limits + positions) - macros AND watcher read this"
        for k in bed_min_x bed_max_x bed_min_y bed_max_y bed_max_z \
                 probe_x probe_y present_x present_y wipe_x wipe_y; do
            [ -n "${R2_HW[${k}]:-}" ] && printf 'variable_%s: %s\n' "${k}" "$(r2_hw_quote "${R2_HW[${k}]}")"
        done
        # keep keys we do not know (future versions / hand edits)
        local kk
        for kk in "${!R2_HW[@]}"; do
            case "${kk}" in
                bed_min_x|bed_max_x|bed_min_y|bed_max_y|bed_max_z|probe_x|probe_y|\
                present_x|present_y|wipe_x|wipe_y) ;;
                *) printf 'variable_%s: %s\n' "${kk}" "$(r2_hw_quote "${R2_HW[${kk}]}")" ;;
            esac
        done
        echo "gcode:"
        echo "    # config carrier only - never runs"
        echo ""
        # the LCD persister - ONLY when the shell-command extension exists AND
        # is a VALID Python module. gcode_shell_command (KIAUH) runs the
        # 'command:' value as a SHELL STRING (subprocess.Popen, shell=True) -
        # so 'bash <path>' is the correct form, NOT a Python expression. If the
        # module file itself is corrupted/foreign (invalid Python), Klipper
        # refuses to boot with 'invalid syntax (gcode_shell_command.py, line N)'
        # - in that case we write NO sections at all, so the module is never
        # imported and Klipper boots cleanly (the LCD-persist/audio feature
        # simply stays off until the module is fixed/installed).
        _gsc="${R2_KLIPPER_DIR:-${HOME}/klipper}/klippy/extras/gcode_shell_command.py"
        if [ -f "${_gsc}" ] && python3 -c "compile(open('${_gsc}').read(),'gcode_shell_command.py','exec')" 2>/dev/null; then
            # R286 L1: host audio playback for the klinke/hdmi audio source
            echo "# R286 L1: real 8-bit audio playback on the Pi (klinke/hdmi source):"
            echo "[gcode_shell_command R2_AUDIO_PLAY]"
            echo "command: bash ${R2_PKG_DIR}/tools/r2_audio_play.sh"
            echo "timeout: 10."
            echo "verbose: False"
        else
            echo "# (audio needs a VALID gcode_shell_command module:"
            echo "#  ${_gsc} is missing or not valid Python - section NOT written so"
            echo "#  Klipper boots cleanly. Install/fix the module (KIAUH) to enable.)"
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
    # R113 field-log .86 fix: NEVER rstrip() the match - it ate the trailing
    # newline and glued the next section header onto the last comment line
    # ('# [R2-off] gcode:[extruder]' - the section VANISHED into the comment)
    return '\n'.join('# [R2-off] ' + l if l.strip() else l for l in m.group(0).split('\n'))
# consume ONLY macro-block lines: variable_/description:/gcode: headers,
# indented body lines, blanks AND column-0 comments that are FOLLOWED by
# more block lines (the .82 writer emitted '# optional: ...' inside the
# block - leaving it active glued 'gcode:' onto the previous section =
# 'Option gcode is not valid in section board_pins' boot halt, field
# log .86). A comment AFTER the block (like our own '# --- R2' insert
# header) is still NOT swallowed - the lookahead requires a block line.
s2 = re.sub(r'\n?\[gcode_macro _R2_CONFIG\]\n(?:[ \t]*(?:variable_|description:|gcode:)[^\n]*\n|[ \t]+[^\n]*\n|[ \t]*\n|(?:[ \t]*#[^\n]*\n)+(?=[ \t]*(?:variable_|description:|gcode:)))*', comment, s, count=1)
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
r2_hw_survey() {
    echo
    echo "--- general hardware survey (what this printer has) --------------------------------"
    if [ "${R2_CHECK}" = "1" ]; then
        echo "[i] (check mode) would print the hardware survey"
        return 0
    fi
    local pc hw
    pc="$(r2_printercfg)"
    hw="$(r2_hwfile)"
    r2_hw_read 2>/dev/null || true
    local row

    echo "  component            status on this printer"
    printf '  %-22s %s\n' "----------------------" "----------------------"

    # --- probe: a real probe section in printer.cfg?
    if grep -qE '^\[(probe|bltouch|micro_probe|eulid|klicky)[[:space:]]' "${pc}" 2>/dev/null; then
        row="$(grep -E '^\[(probe|bltouch|micro_probe|eulid|klicky)[[:space:]]' "${pc}" 2>/dev/null | head -1)"
        printf '  %-22s %s\n' "probe" "present - ${row#\[}"
    elif [ "${R2_HW[probe_type]:-}" != "4" ] && [ -n "${R2_HW[probe_type]:-}" ]; then
        printf '  %-22s %s\n' "probe" "profile: ${R2_HW[probe_type]} (add the [probe] section in printer.cfg by hand)"
    else
        printf '  %-22s %s\n' "probe" "none - manual paper leveling"
    fi

    # --- sound: M300 macro present?
    if grep -qE '^\[gcode_macro (M300|_R2_SOUND|R2_SOUND)[[:space:]]' "${pc}" 2>/dev/null \
       || grep -qE '^\[gcode_macro (M300|_R2_SOUND|R2_SOUND)[[:space:]]' "${R2_CFG_DIR}/../macros/02_sounds.cfg" 2>/dev/null; then
        printf '  %-22s %s\n' "sound" "macro present (beep/8-bit WAV)"
    else
        printf '  %-22s %s\n' "sound" "no M300 macro found"
    fi

    # --- filament runout
    if grep -qE '^\[filament_switch|^[ ]*use_filament_sensor[[:space:]]*:[[:space:]]*1' "${pc}" 2>/dev/null; then
        printf '  %-22s %s\n' "filament runout" "sensor enabled"
    else
        printf '  %-22s %s\n' "filament runout" "not enabled"
    fi

    # --- live retraction
    if grep -qE '^\[[[:space:]]*retract_[a-z_]*[[:space:]]' "${pc}" 2>/dev/null; then
        printf '  %-22s %s\n' "live retraction" "[retract_*] present"
    else
        printf '  %-22s %s\n' "live retraction" "not configured"
    fi

    # --- gantry / dual-motor axis
    local gx gy
    gx="$(grep -cE '^stepper_x[0-9]' "${pc}" 2>/dev/null || true)"
    gy="$(grep -cE '^stepper_y[0-9]' "${pc}" 2>/dev/null || true)"
    if [ "${gx}" -ge 2 ] || [ "${gy}" -ge 2 ]; then
        printf '  %-22s %s\n' "gantry" "dual-motor axis (X:${gx} Y:${gy})"
    else
        printf '  %-22s %s\n' "gantry" "single motor per axis"
    fi

    # --- shaper (input shaping)
    if grep -qE '^\[stepper_[xyzab][0-9]*\].*\binput_shaping_[a-z]+_freq' "${pc}" 2>/dev/null \
       || grep -qE '^\[resonance_tester|^[ ]*shaper_[a-z]+_freq' "${pc}" 2>/dev/null; then
        printf '  %-22s %s\n' "shaper" "input shaping configured"
    else
        printf '  %-22s %s\n' "shaper" "not configured (PID/shaper recalibration is hardware-dependent)"
    fi

    # --- LCD
    if grep -qE '^\[lcd_display|^[ ]*lcd_[a-z]+:' "${pc}" 2>/dev/null; then
        printf '  %-22s %s\n' "LCD" "display configured"
    else
        printf '  %-22s %s\n' "LCD" "no LCD section found"
    fi

    echo
    echo "    [i] These are the hardware-dependent parts the system's known limits"
    echo "        refer to (probe / LED / sound / runout / live-retraction / gantry /"
    echo "        shaper / LCD). The hardware wizard below edits build volume / probe"
    echo "        / positions; the LED wizard edits the LED layout - both run next."
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
        [ "${R2_YN}" = "y" ] && { r2_ensure_include; return 0; }
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
