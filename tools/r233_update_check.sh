#!/usr/bin/env bash
# =====================================================================================
#  r233_update_check.sh - R233 (.136ad): the update.zip version gate audit
#
#  FIELD REPORT (.136ad, 2026-11-09): "das Update scheint seit Version
#  Punkt 136 Z nicht mehr zu funktionieren ... er macht immer wieder nur Z
#  drauf, anstatt die anderen Version, obwohl die alle hochgeladen sind."
#  Root cause: the hotfix letters are an ODOMETER (.136z -> .136aa ->
#  .136ab -> .136ac), but update.sh compared them as plain strings, and
#  'ac' < 'z' is TRUE lexicographically - every zip after .136z failed
#  the OLDER check, was refused as a "downgrade" and never unpacked.
#  The fix (r2_sfx_val) counts the suffix arithmetically: ''=0, a..z =
#  1..26, aa=27, ab=28 ... az=52, ba=53 ...
#
#  This audit proves the fix at three levels:
#   A) r2_sfx_val - extracted VERBATIM from update.sh (sed -n + eval):
#      pinned odometer values + the full a..z / aa..zz walk (+1 steps)
#   B) the section-1 gate formulas (documented mirror of the two compare
#      lines; kept honest by level C) over the field pairs, side by side
#      with the OLD string rule that produced the field log - plus
#      static proof that the old string compares are GONE from update.sh
#   C) END-TO-END with the real scripts and real zips in throwaway
#      sandboxes (HOME redirected - nothing outside is ever touched):
#        S1  .136z package (authentic git aa53fec) + zips {.136ac, NEW},
#            no --force    -> REFUSED, package stays .136z (the exact
#            field reproduction - the printer "macht nur Z draus")
#        S2  same + --force -> the NEW zip wins the selection, unpacks,
#            re-execs the NEW update.sh, runs to "== done", package
#            version == NEW, the fixed gate is now installed
#        S2b the NEW script again, the stale .136ac zip left in the
#            folder        -> REFUSED (a real downgrade stays one)
#        S3  .136z package + FIXED update.sh + NEW zip, NO --force
#                       -> UNPACKED (the fix itself: from .136ad on no
#                          --force is needed any more)
#        S4  NEW package + .136z zip      -> REFUSED (downgrade guard)
#        S5  NEW package + NEW zip (same version) -> re-applied (idempotent)
#        D1  install_web.sh --update-only with a BARE [r2_menu] section
#            and an [update_manager] 'path:' AFTER it: no sed crash, the
#            conf stays byte-identical (the repaired patch must never
#            inject export_tool into a foreign section)
#        D2  same with 'path:' INSIDE [r2_menu]: export_tool lands behind
#            exactly that line - and nowhere else
#
#  Run:  bash tools/r233_update_check.sh
# =====================================================================================
set -u
HERE="$(cd "$(dirname "$0")/.." && pwd)"
UPD="${HERE}/update.sh"
WEBI="${HERE}/web/install_web.sh"
PASS=0; FAIL=0

ok()  { PASS=$((PASS + 1)); printf '  [ok] %s\n' "$1"; }
bad() { FAIL=$((FAIL + 1)); printf '  [!!] FAIL: %s\n' "$1"; }
chk() { local n="$1"; shift; if "$@"; then ok "${n}"; else bad "${n}"; fi; }
chk_str() {  # chk_str <name> <got> <want>
    if [ "$2" = "$3" ]; then ok "$1"; else bad "$1 (got '$2' want '$3')"; fi
}

# =====================================================================================
echo "--- A) r2_sfx_val, extracted VERBATIM from update.sh -------------------------------"
FN="$(sed -n '/^r2_sfx_val()/,/^}/p' "${UPD}")"
if [ -z "${FN}" ]; then
    echo "  [!!] FAIL: r2_sfx_val() not found in ${UPD}"
    exit 1
fi
eval "${FN}"

chk_str "sfx('')  = 0  (bare release)"        "$(r2_sfx_val '')"    0
chk_str "sfx(a)   = 1"                        "$(r2_sfx_val 'a')"   1
chk_str "sfx(b)   = 2"                        "$(r2_sfx_val 'b')"   2
chk_str "sfx(y)   = 25"                       "$(r2_sfx_val 'y')"   25
chk_str "sfx(z)   = 26  (the field version)"  "$(r2_sfx_val 'z')"   26
chk_str "sfx(aa)  = 27  (first 2-letter)"     "$(r2_sfx_val 'aa')"  27
chk_str "sfx(ab)  = 28"                       "$(r2_sfx_val 'ab')"  28
chk_str "sfx(ac)  = 29  (the uploaded zip)"   "$(r2_sfx_val 'ac')"  29
chk_str "sfx(ad)  = 30  (this release)"       "$(r2_sfx_val 'ad')"  30
chk_str "sfx(az)  = 52"                       "$(r2_sfx_val 'az')"  52
chk_str "sfx(ba)  = 53"                       "$(r2_sfx_val 'ba')"  53
chk_str "sfx(zz)  = 702"                      "$(r2_sfx_val 'zz')"  702
chk_str "sfx(aaa) = 703"                      "$(r2_sfx_val 'aaa')" 703

WALK_OK=1; EXPECT=1
for c in {a..z}; do
    [ "$(r2_sfx_val "${c}")" = "${EXPECT}" ] || WALK_OK=0
    EXPECT=$((EXPECT + 1))
done
for c1 in {a..z}; do
    for c2 in {a..z}; do
        [ "$(r2_sfx_val "${c1}${c2}")" = "${EXPECT}" ] || WALK_OK=0
        EXPECT=$((EXPECT + 1))
    done
done
chk "odometer walk a..z,aa..zz counts +1 (702 steps, ends at $(r2_sfx_val zz))" \
    [ "${WALK_OK}" = 1 ]

# =====================================================================================
echo "--- B) the section-1 gate: selection + OLDER (mirror of the update.sh lines) --------"

# the FIXED rule, exactly as update.sh compares since R233
newer_than() {   # newer_than <n1> <s1> <n2> <s2> : is v1 strictly newer than v2?
    [ "$1" -gt "$3" ] && return 0
    if [ "$1" -eq "$3" ] && [ "$(r2_sfx_val "$2")" -gt "$(r2_sfx_val "$4")" ]; then
        return 0
    fi
    return 1
}
# the OLD rule (pre-R233, for the side-by-side verdict) - numbers numeric,
# letters as a plain string
old_newer_than() {
    [ "$1" -gt "$3" ] && return 0
    if [ "$1" -eq "$3" ] && [[ "$2" > "$4" ]]; then return 0; fi
    return 1
}
gate() {   # gate <label> <zn> <zs> <cur_n> <cur_s> <newer|older-or-equal>
    local label="$1" zn="$2" zs="$3" cn="$4" cs="$5" want="$6" got
    if newer_than "${zn}" "${zs}" "${cn}" "${cs}"; then got="newer"; else got="older-or-equal"; fi
    chk_str "gate: .${zn}${zs} vs installed .${cn}${cs} -> ${want}  (${label})" \
        "${got}" "${want}"
}
gate "THE field case"       136 ac 136 z  newer
gate "this release"        136 ad 136 z  newer
gate "rollover start"      136 aa 136 z  newer
gate "real downgrade"      136 z  136 ac older-or-equal
gate "real downgrade 2"    136 z  136 ad older-or-equal
gate "same version"        136 ad 136 ad older-or-equal
gate "R174 hotfix letter"  129 a  129 '' newer
gate "R174 reverse"        129 '' 129 a  older-or-equal
gate "number dominates"    130 '' 129 a  newer
gate "big jump"            136 ac 50  '' newer
gate "future number guard" 136 ad 137 '' older-or-equal

if old_newer_than 136 ac 136 z; then
    bad "OLD rule accepts .136ac over .136z (the bug should reproduce)"
else
    ok "OLD rule refuses .136ac over .136z  <- the field bug, reproduced"
fi
if newer_than 136 ac 136 z; then
    ok "NEW rule accepts  .136ac over .136z  <- the fix"
else
    bad "NEW rule still refuses .136ac over .136z"
fi

# the selection loop, mirrored (BEST over num:sfx pairs, worst start 0:'')
sel_best() {
    local best_n=0 best_s="" p n s
    for p in "$@"; do
        n="${p%%:*}"; s="${p##*:}"
        if [ "${n}" -gt "${best_n}" ] \
           || { [ "${n}" -eq "${best_n}" ] \
                && [ "$(r2_sfx_val "${s}")" -gt "$(r2_sfx_val "${best_s}")" ]; }; then
            best_n="${n}"; best_s="${s}"
        fi
    done
    echo "${best_n}:${best_s}"
}
chk_str "selection {50, 129a, 129, 136z, 136ac} -> 136ac" \
    "$(sel_best 50: 129:a 129: 136:z 136:ac)" "136:ac"
chk_str "selection {136z, 136aa} -> 136aa (2 letters BEAT z now)" \
    "$(sel_best 136:z 136:aa)" "136:aa"
chk_str "selection {136ac, 136ad} -> 136ad" \
    "$(sel_best 136:ac 136:ad)" "136:ad"
chk_str "selection {136ad, 136z} -> 136ad (the field folder)" \
    "$(sel_best 136:ad 136:z)" "136:ad"

# static proof in the shipped files
N="$(grep -c 'r2_sfx_val' "${UPD}")"
if [ "${N}" -ge 5 ]; then
    ok "update.sh references r2_sfx_val ${N}x (def + both gates)"
else
    bad "update.sh references r2_sfx_val only ${N}x (want >= 5)"
fi
chk "old string compare gone from the selection loop" \
    bash -c "! grep -qF '[[ \"\${ZS}\" > \"\${BEST_S}\" ]]' '${UPD}'"
chk "old string compare gone from the OLDER gate" \
    bash -c "! grep -qF '[[ \"\${BEST_S}\" < \"\${CUR_S}\" ]]' '${UPD}'"
chk "install_web.sh: the broken s/// sed is gone" \
    bash -c "! grep -qF 's/^\(path: .*\)$/\1\nexport_tool:' '${WEBI}'"
chk "install_web.sh: the unbounded r2_menu..path: sed range is gone" \
    bash -c "! grep -qF \"sed -i '/^\\\\[r2_menu\\\\]/,/^path:/\" '${WEBI}'"
chk "install_web.sh: the bounded awk patch is in place" \
    grep -qF 'awk -v pkg="${PKG_DIR}"' "${WEBI}"

# =====================================================================================
echo "--- C) END-TO-END: real update.sh, real zips, throwaway sandboxes -------------------"

NEED_T="git zip unzip tar mktemp"
for t in ${NEED_T}; do
    if ! command -v "${t}" >/dev/null 2>&1; then
        echo "  [!!] FAIL: tool '${t}' missing - the E2E part cannot run"
        exit 1
    fi
done

# frozen history: the version the field report is stuck on, and the zip it
# uploaded (both commits are pinned - they never move again)
OLD_C=aa53fec      # R228 (.136z)
AC_C=7003b8f       # R231/R232 (.136ac)
OLD_VER='R2-2026-11-08.136z'
AC_VER='R2-2026-11-08.136ac'
for c in ${OLD_C} ${AC_C}; do
    git -C "${HERE}" cat-file -e "${c}^{commit}" 2>/dev/null \
        || { echo "  [!!] FAIL: commit ${c} not found in ${HERE}"; exit 1; }
done

# the version THIS working tree carries, parsed exactly like update.sh does
ver_of() {
    sed -n "s/^[[:space:]]*variable_version: *'\(R2-[0-9-]*\.[0-9]*[a-z]*\)'.*/\1/p" "$1" 2>/dev/null | head -1
}
vn() { printf '%s' "${1:-}" | sed -n 's/.*\.\([0-9]*\)[a-z]*$/\1/p'; }
vs() { printf '%s' "${1:-}" | sed -n 's/.*\.[0-9]*\([a-z]*\)$/\1/p'; }

NEW_VER="$(ver_of "${HERE}/macros/01_state.cfg")"
if [ -z "${NEW_VER}" ]; then
    echo "  [!!] FAIL: no variable_version in ${HERE}/macros/01_state.cfg"
    exit 1
fi
NEW_N="$(vn "${NEW_VER}")"; NEW_S="$(vs "${NEW_VER}")"
OLD_N="$(vn "${OLD_VER}")"; OLD_S="$(vs "${OLD_VER}")"
if [ "${NEW_VER}" = "${OLD_VER}" ] || [ "${NEW_VER}" = "${AC_VER}" ]; then
    echo "  [!!] FAIL: the working tree still carries ${NEW_VER} - the E2E zip"
    echo "      names would collide with the frozen history zips. Bump the"
    echo "      release first (this audit ships WITH .136ad)."
    exit 1
fi
chk "precondition: the working tree version .${NEW_N}${NEW_S} is newer than .136z" \
    newer_than "${NEW_N}" "${NEW_S}" "${OLD_N}" "${OLD_S}"

# --- build the zips ------------------------------------------------------------------
TMP="$(mktemp -d "${TMPDIR:-/tmp}/r233.XXXXXX")"
SBS=("${TMP}")
cleanup() { local d; for d in ${SBS[@]+"${SBS[@]}"}; do rm -rf "${d}"; done; }
trap cleanup EXIT

# the NEW zip from THIS working tree, laid out like the release zip
# (git archive content: no .git, no runtime state)
STAGE="${TMP}/stage"
mkdir -p "${STAGE}/klipper-e3-r2d2"
( cd "${HERE}" && tar cf - \
      --exclude=.git --exclude=watch_state.json --exclude=watcher.lock \
      --exclude='__pycache__' --exclude='*.pyc' . ) \
    | ( cd "${STAGE}/klipper-e3-r2d2" && tar xf - )
NEWZIP="${TMP}/klipper-e3-r2d2-UPDATE-${NEW_VER}.zip"
( cd "${STAGE}" && zip -qr "${NEWZIP}" klipper-e3-r2d2 )

# the authentic history zips, built exactly like the shipped ones
ACZIP="${TMP}/klipper-e3-r2d2-UPDATE-${AC_VER}.zip"
OZIP="${TMP}/klipper-e3-r2d2-UPDATE-${OLD_VER}.zip"
git -C "${HERE}" archive --format=zip --prefix=klipper-e3-r2d2/ -o "${ACZIP}" "${AC_C}"
git -C "${HERE}" archive --format=zip --prefix=klipper-e3-r2d2/ -o "${OZIP}"  "${OLD_C}"
chk "history zip .136z really contains version ${OLD_VER}" \
    bash -c "unzip -p '${OZIP}' klipper-e3-r2d2/macros/01_state.cfg | grep -qF \"variable_version: '${OLD_VER}'\""

mk_sb() {   # fresh sandbox: fake HOME + printer.cfg with all 19 includes
    local sb f
    sb="$(mktemp -d "${TMP}/sb.XXXXXX")"
    SBS+=("${sb}")
    mkdir -p "${sb}/home/printer_data/config"
    for f in 01_state 02_sounds 03_leds 04_notify 05_materials 06_temp_controls \
             07_start_confirm 08_print_start_stop 09_pause_filament 10_live_tuning \
             11_gantry_sync 12_maintenance 13_system 14_kamp 15_objects 16_labels \
             17_generator 18_colorpic 19_bricks; do
        printf '[include klipper-e3-r2d2/macros/%s.cfg]\n' "${f}" \
            >> "${sb}/home/printer_data/config/printer.cfg"
    done
    echo "${sb}"
}
install_pkg() {   # install_pkg <sb> <git-commit | STAGE>
    local sb="$1" src="$2"
    if [ "${src}" = "STAGE" ]; then
        cp -a "${STAGE}/klipper-e3-r2d2" "${sb}/home/printer_data/config/"
    else
        ( cd "${sb}/home/printer_data/config" \
            && git -C "${HERE}" archive --format=tar \
                   --prefix=klipper-e3-r2d2/ "${src}" | tar -x )
    fi
}
pkg_ver() { ver_of "$1/home/printer_data/config/klipper-e3-r2d2/macros/01_state.cfg"; }
ver_is()  { [ "$(pkg_ver "$1")" = "$2" ]; }
fis2()    { [ -f "$1" ] && [ -f "$2" ]; }
run_upd() {   # run_upd <sb> [args...]
    local sb="$1"; shift
    env HOME="${sb}/home" TERM=dumb \
        bash "${sb}/home/printer_data/config/klipper-e3-r2d2/update.sh" "$@" \
        </dev/null >"${sb}/log" 2>&1
}
has()     { grep -qF "$2" "${1}/log"; }
lacks()   { ! grep -qF "$2" "${1}/log"; }
cfgdir()  { echo "$1/home/printer_data/config"; }

# --- S1: the field reproduction - old script, newer zips, no --force ------------------
SB="$(mk_sb)"
install_pkg "${SB}" "${OLD_C}"
cp "${ACZIP}" "${NEWZIP}" "$(cfgdir "${SB}")/"
run_upd "${SB}"
chk "S1: the old script picks the NEWEST zip (${NEW_VER})" \
    has "${SB}" "uploaded update zip found: klipper-e3-r2d2-UPDATE-${NEW_VER}.zip"
if [ "${NEW_N}" = "136" ]; then
    chk "S1: ...and refuses it as OLDER (the field bug, live)" \
        has "${SB}" "that zip is OLDER than the installed version - not unpacking it."
    chk "S1: package stays on ${OLD_VER}" ver_is "${SB}" "${OLD_VER}"
    chk "S1: both zips stay in the config folder (nothing was unpacked)" \
        fis2 "$(cfgdir "${SB}")/klipper-e3-r2d2-UPDATE-${AC_VER}.zip" \
             "$(cfgdir "${SB}")/klipper-e3-r2d2-UPDATE-${NEW_VER}.zip"
else
    # R241 (.137+): a BARE number is past the whole .136 series - even the
    # OLD string gate sees 137 > 136z, so the letter-era field bug cannot
    # (and must not) reproduce. The old script ACCEPTS instead - pinned as
    # a real field guarantee: .137 flashes from ANY historical install,
    # even a pre-odometer one, without --force.
    chk "S1: ...and ACCEPTS it (bare .${NEW_N} beats the old string gate too)" \
        lacks "${SB}" "that zip is OLDER"
    chk "S1: package updates straight to ${NEW_VER}" ver_is "${SB}" "${NEW_VER}"
    chk "S1: the stale ${AC_VER} zip stays untouched in the config folder" \
        test -f "$(cfgdir "${SB}")/klipper-e3-r2d2-UPDATE-${AC_VER}.zip"
fi
chk "S1: the run does not abort (the field log showed the same)" \
    has "${SB}" "== done. Happy printing! =="

# the hard pin of THIS release: the old gate must refuse .136ad over .136z
# (a future .137+ release changes the premise - then this pins the new one)
if [ "${NEW_N}" = "136" ]; then
    if lacks "${SB}" "that zip is OLDER"; then
        bad "S1 hard pin: .136${NEW_S} must be refused by the OLD gate"
    else
        ok "S1 hard pin: OLD gate refuses .136${NEW_S} over .136z (odometer gap)"
    fi
else
    echo "  [i] S1 hard pin: .${NEW_N}${NEW_S} is past the .136 series - the old"
    echo "      gate ACCEPTS it by NUMBER (no odometer needed) - the field"
    echo "      guarantee of the bare renumber: it updates ANY historical install"
fi

# --- S2: the recovery path - --force once, exactly as the field needs it --------------
SB="$(mk_sb)"
install_pkg "${SB}" "${OLD_C}"
cp "${ACZIP}" "${NEWZIP}" "$(cfgdir "${SB}")/"
run_upd "${SB}" --force
if [ "${NEW_N}" = "136" ]; then
    chk "S2: --force announces the deliberate downgrade" \
        has "${SB}" "[i] --force: unpacking the OLDER zip anyway"
else
    # R241 (.137+): the zip is not older - nothing to announce, --force
    # is simply not needed any more from a .136z-era install
    chk "S2: no downgrade announce (.${NEW_N} is simply newer)" \
        lacks "${SB}" "[i] --force: unpacking the OLDER zip anyway"
fi
chk "S2: the NEW zip is the one unpacked" \
    has "${SB}" "unpacking over $(cfgdir "${SB}")/klipper-e3-r2d2"
chk "S2: the run re-execs the NEW update.sh" \
    has "${SB}" "continuing with the NEW update.sh"
chk "S2: package version is now ${NEW_VER}" ver_is "${SB}" "${NEW_VER}"
chk "S2: the FIXED gate is installed (r2_sfx_val in the live update.sh)" \
    grep -q 'r2_sfx_val' "$(cfgdir "${SB}")/klipper-e3-r2d2/update.sh"
chk "S2: the new script reports the new version" \
    has "${SB}" "[i] package version: ${NEW_VER}"
chk "S2: the applied zip moved to r2_backups" \
    fis2 "$(cfgdir "${SB}")/r2_backups/klipper-e3-r2d2-UPDATE-${NEW_VER}.zip" \
         "$(cfgdir "${SB}")/klipper-e3-r2d2-UPDATE-${AC_VER}.zip"
chk "S2: the run completes" has "${SB}" "== done. Happy printing! =="

# --- S2b: the NEW gate vs the stale zip left behind ------------------------------------
run_upd "${SB}"
chk "S2b: the new script finds the stale ${AC_VER} zip" \
    has "${SB}" "uploaded update zip found: klipper-e3-r2d2-UPDATE-${AC_VER}.zip"
chk "S2b: ...and refuses it (a real downgrade - not the odometer bug)" \
    has "${SB}" "that zip is OLDER than the installed version - not unpacking it."
chk "S2b: package stays on ${NEW_VER}" ver_is "${SB}" "${NEW_VER}"

# --- S3: the fix itself - .136z package, FIXED gate, NO --force ------------------------
SB="$(mk_sb)"
install_pkg "${SB}" "${OLD_C}"
cp "${UPD}" "$(cfgdir "${SB}")/klipper-e3-r2d2/update.sh"
cp "${NEWZIP}" "$(cfgdir "${SB}")/"
run_upd "${SB}"
chk "S3: the fixed gate does NOT call the zip older" \
    lacks "${SB}" "that zip is OLDER than the installed version"
chk "S3: the zip is unpacked without --force" \
    has "${SB}" "unpacking over $(cfgdir "${SB}")/klipper-e3-r2d2"
chk "S3: package version is ${NEW_VER}" ver_is "${SB}" "${NEW_VER}"
chk "S3: the run completes" has "${SB}" "== done. Happy printing! =="

# --- S4: downgrade guard - .136z zip vs the new package -------------------------------
SB="$(mk_sb)"
install_pkg "${SB}" "STAGE"
cp "${OZIP}" "$(cfgdir "${SB}")/"
run_upd "${SB}"
chk "S4: a .136z zip is refused over ${NEW_VER}" \
    has "${SB}" "that zip is OLDER than the installed version - not unpacking it."
chk "S4: package stays on ${NEW_VER}" ver_is "${SB}" "${NEW_VER}"

# --- S5: idempotent - same version again ----------------------------------------------
SB="$(mk_sb)"
install_pkg "${SB}" "STAGE"
cp "${NEWZIP}" "$(cfgdir "${SB}")/"
run_upd "${SB}"
chk "S5: an equal version is not 'older'" \
    lacks "${SB}" "that zip is OLDER than the installed version"
chk "S5: it re-applies cleanly (idempotent)" \
    has "${SB}" "unpacking over $(cfgdir "${SB}")/klipper-e3-r2d2"
chk "S5: package version is ${NEW_VER}" ver_is "${SB}" "${NEW_VER}"

# =====================================================================================
echo "--- D) install_web.sh --update-only: the r2_menu patch, sandboxed ---------------------"

mk_web() {   # sandbox with a web-LCD 'installed' + the trap layout in moonraker.conf
    local sb root
    sb="$(mktemp -d "${TMP}/web.XXXXXX")"
    SBS+=("${sb}")
    root="${sb}/root"
    mkdir -p "${root}/home/moonraker/moonraker/components" \
             "${root}/etc/nginx/sites-available" "${root}/etc/nginx/sites-enabled" \
             "${root}/var/www" "${root}/config"
    # component + site file + section -> --update-only detects an install
    cp "${STAGE}/klipper-e3-r2d2/web/r2_menu.py" "${root}/home/moonraker/moonraker/components/"
    printf '# R2-D2 web-LCD (created by web/install_web.sh - remove with --uninstall)\nserver {\n    listen 7126;\n}\n' \
        > "${root}/etc/nginx/sites-available/r2lcd"
    ln -s "${root}/etc/nginx/sites-available/r2lcd" "${root}/etc/nginx/sites-enabled/r2lcd"
    cat > "${root}/config/moonraker.conf" <<'MREOF'
[server]
host: 0.0.0.0
port: 7125

[r2_menu]

[update_manager client mainsail]
type: git_repo
path: ~/mainsail
channel: stable
MREOF
    echo "${sb}"
}
run_web() {   # run_web <sb> [mode] -> sets RE_RC
    local sb="$1" root="${1}/root"; shift
    # no R2_MOONRAKER_DIR override: the default detection must find
    # ${root}/home/moonraker/moonraker/components on its own (like on a Pi)
    env HOME="${root}/home" TERM=dumb \
        R2_MOONRAKER_CONF="${root}/config/moonraker.conf" \
        R2_NGINX_SITES="${root}/etc/nginx/sites-available" \
        R2_NGINX_EN="${root}/etc/nginx/sites-enabled" \
        R2_WEB_ROOT="${root}/var/www/r2lcd" \
        R2_NO_SERVICES=1 \
        bash "${STAGE}/klipper-e3-r2d2/web/install_web.sh" "$@" \
        </dev/null >"${sb}/log" 2>&1
    RE_RC=$?
}

# D1: the field layout - bare [r2_menu], a foreign path: AFTER it
SB="$(mk_web)"
cp "${SB}/root/config/moonraker.conf" "${SB}/before.conf"
run_web "${SB}" --update-only
chk "D1: exit 0" [ "${RE_RC}" = 0 ]
chk "D1: no 'sed: unknown option' garbage any more" lacks "${SB}" "unknown option to"
chk "D1: the [i] fallback prints (no path: in [r2_menu])" \
    has "${SB}" "[r2_menu] has no path: line - r2_menu.py derives the tool from the json path instead"
chk "D1: moonraker.conf stays BYTE-identical (nothing injected anywhere)" \
    cmp -s "${SB}/before.conf" "${SB}/root/config/moonraker.conf"
chk "D1: the foreign [update_manager] path: line is untouched" \
    grep -q '^path: ~/mainsail$' "${SB}/root/config/moonraker.conf"
chk "D1: component + page + site refreshed" \
    has "${SB}" "web-LCD install detected - refreshing component + nginx site"

# D2: the R225 target layout - path: INSIDE [r2_menu]
SB="$(mk_web)"
sed -i '/^\[r2_menu\]/a path: /var/www/r2lcd/menu_structure.json' "${SB}/root/config/moonraker.conf"
run_web "${SB}" --update-only
chk "D2: exit 0" [ "${RE_RC}" = 0 ]
chk "D2: no 'sed: unknown option' garbage any more" lacks "${SB}" "unknown option to"
chk "D2: export_tool was added" \
    has "${SB}" "[r2_menu] export_tool added"
chk "D2: ...behind the [r2_menu] path: line, with the real package path" \
    bash -c "grep -A1 '^path: /var/www/r2lcd/menu_structure.json$' '${SB}/root/config/moonraker.conf' | grep -qF 'export_tool: ${STAGE}/klipper-e3-r2d2/tools/menu_json_export.py'"
chk "D2: the foreign [update_manager] path: got NOTHING" \
    bash -c "! grep -A1 '^path: ~/mainsail$' '${SB}/root/config/moonraker.conf' | grep -q export_tool"
chk "D2: exactly ONE export_tool line in the whole conf" \
    bash -c "[ \"\$(grep -c '^export_tool:' '${SB}/root/config/moonraker.conf')\" = 1 ]"

# =====================================================================================
echo ""
echo "R233 UPDATE CHECK: ${PASS} pass, ${FAIL} fail"
[ "${FAIL}" -eq 0 ] || exit 1
exit 0
