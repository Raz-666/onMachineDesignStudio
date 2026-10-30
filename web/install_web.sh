#!/usr/bin/env bash
# SPDX-License-Identifier: GPL-3.0-or-later
# =====================================================================================
#  install_web.sh - the web-LCD in ONE command (R203, .136b)
#
#  WHAT THIS DOES (and why it is safe):
#    1) copies web/r2_menu.py into moonraker's components/ (the extension
#       that serves the menu tree + live values as JSON)
#    2) appends a marked [r2_menu] section to moonraker.conf (backup first)
#    3) drops a SEPARATE nginx site file (sites-available/r2lcd + symlink)
#       that serves web/index.html on its own port and proxies the API
#       paths to moonraker - your mainsail/fluidd nginx config is NEVER
#       touched, everything is one removable file
#    4) restarts moonraker + reloads nginx (nginx -t gates the reload -
#       on any config error the new file is rolled back)
#
#  THEN OPEN:   http://<pi-ip>:<port>/r2lcd/     (the script prints the URL)
#  Bookmark it on your phone - that is the whole point.
#
#  OPTIONS:   --uninstall    remove everything this script created
#             --status       show what is installed, do nothing
#             --update-only  refresh an EXISTING install (update.sh calls
#                            this after every package update); exits 0 as a
#                            no-op when no web-LCD is installed here

#  R206 (.136e field fix "403 Forbidden") - two stacked causes, both fixed:
#    (1) Moonraker answers 403 to every request whose Origin header it does
#        not know - browsers send Origin on ALL command POSTs (same-origin
#        GETs carry none: the live values worked, every button died since
#        .136b). The nginx site now strips Origin at the proxy AND takes
#        over the browser-CSRF check itself (map at the top of the site
#        file: no Origin or same-origin passes, foreign websites get 403
#        before they ever reach the printer).
#    (2) update.sh never synced web/r2_menu.py into moonraker's
#        components/ - the installer ran once, later extension fixes (the
#        R204 slim query!) never reached the Pi. --update-only refreshes
#        component + nginx site on every package update.
#    R207 (.136e field log - "403 again"): a written site file is not a
#    live config (silent reload failure) and the origin==host comparison
#    must be case-insensitive (browser lowercases Origin, Host goes as
#    typed). The map is ~* now, and the installer SELF-TESTS the live
#    guard after every reload (foreign origin must 403 at the proxy).
#    Site file + symlink are written via sudo when /etc/nginx is not
#    user-writable.
#    R208 (.136f field log - "403 schon beim Oeffnen, auch inkognito"):
#    nginx runs as www-data and could not READ the page under /home/pi -
#    a home-dir serve path depends on traverse permissions that can flip
#    on any update (nginx answers 403 for unreadable static files; the
#    API proxy paths kept working - which is why every proxy test was
#    green while the page would not even load). The page is now served
#    from WEB_ROOT (/var/www/r2lcd, world-readable, outside every home
#    dir), synced here and via --update-only on every package update -
#    and the self-test also GETs the page itself now (a serve path that
#    cannot be read can never pass silently again).
#
#  OVERRIDES (for tests / exotic setups):
#             R2_MOONRAKER_DIR  R2_MOONRAKER_CONF  R2_NGINX_SITES
#             R2_NGINX_EN  R2_NO_SERVICES (skip systemctl calls)
#             R2_WEB_ROOT (serve path, default /var/www/r2lcd)
# =====================================================================================
set -u

WEB_DIR="$(cd "$(dirname "$0")" && pwd)"          # .../klipper-e3-r2d2/web
PKG_DIR="$(dirname "$WEB_DIR")"                   # .../klipper-e3-r2d2
CFG_DIR="$(dirname "$PKG_DIR")"                   # .../printer_data/config
# R208: the SERVE path - deliberately NOT the package dir (nginx/www-data
# must never depend on home-dir traverse permissions)
WEB_ROOT="${R2_WEB_ROOT:-/var/www/r2lcd}"
USER_HOME="${HOME:-/home/pi}"

MODE="install"
[ "${1:-}" = "--uninstall" ] && MODE="uninstall"
[ "${1:-}" = "--status" ] && MODE="status"
[ "${1:-}" = "--update-only" ] && MODE="update-only"

# ---------- locate the pieces (defaults first, env overrides, common paths) ----------
MOON_DIR="${R2_MOONRAKER_DIR:-}"
if [ -z "${MOON_DIR}" ]; then
    for c in "${USER_HOME}/moonraker" "/home/pi/moonraker" \
             "${USER_HOME}/moonraker-env/moonraker"; do
        [ -d "${c}/moonraker/components" ] && MOON_DIR="${c}" && break
    done
fi
COMP_DIR="${MOON_DIR}/moonraker/components"

MR_CONF="${R2_MOONRAKER_CONF:-}"
if [ -z "${MR_CONF}" ]; then
    for c in "${CFG_DIR}/../moonraker.conf" "${USER_HOME}/printer_data/moonraker.conf" \
             "/home/pi/printer_data/moonraker.conf" "${CFG_DIR}/moonraker.conf"; do
        [ -f "$c" ] && MR_CONF="$(readlink -f "$c")" && break
    done
fi

NGX_SITES="${R2_NGINX_SITES:-/etc/nginx/sites-available}"
NGX_EN="${R2_NGINX_EN:-${NGX_SITES%/sites-available}/sites-enabled}"
SITE_FILE="${NGX_SITES}/r2lcd"
SITE_LINK="${NGX_EN}/r2lcd"
PORTS="7126 7186 7196"        # first free one wins
MARK_B="# --- r2_menu (web-LCD) begin ---"
MARK_E="# --- r2_menu (web-LCD) end ---"

svc() {    # systemctl wrapper (skipped when R2_NO_SERVICES=1 or no systemctl)
    if [ "${R2_NO_SERVICES:-0}" = "1" ] || ! command -v systemctl >/dev/null 2>&1; then
        echo "[i] (dry) systemctl $*"
        return 0
    fi
    sudo systemctl "$@"
}

echo "== R2 web-LCD installer =="

# ---------- status ----------
if [ "${MODE}" = "status" ]; then
    echo "component : ${COMP_DIR}/r2_menu.py $([ -f "${COMP_DIR}/r2_menu.py" ] && echo '[ok]' || echo '[missing]')"
    echo "page      : ${WEB_ROOT}/index.html $([ -f "${WEB_ROOT}/index.html" ] && echo '[ok]' || echo '[missing - re-run this installer]')"
    echo "config    : ${MR_CONF:-not found} $([ -f "${MR_CONF:-/nonexistent}" ] && grep -q '^\[r2_menu\]' "${MR_CONF}" 2>/dev/null && echo '[section ok]' || echo '[no section]')"
    echo "nginx     : ${SITE_FILE} $([ -f "${SITE_FILE}" ] && echo '[ok]' || echo '[missing]')"
    if [ -f "${SITE_FILE}" ]; then
        _ST="$(cat "${SITE_FILE}" 2>/dev/null || sudo cat "${SITE_FILE}" 2>/dev/null)"
        P="$(sed -n 's/.*listen \([0-9]*\).*/\1/p' <<<"${_ST}" | head -1)"
        echo "URL       : http://<this-pi>:${P:-?}/r2lcd/"
        grep -q 'r2_csrf_bad' <<<"${_ST}" \
            && echo "CSRF guard: [ok] (R206+, Origin stripped at the proxy)" \
            || echo "CSRF guard: [old site file - re-run this installer]"
    fi
    exit 0
fi

# ---------- uninstall ----------
if [ "${MODE}" = "uninstall" ]; then
    RM_ANY=0
    if [ -e "${SITE_LINK}" ] || [ -e "${SITE_FILE}" ]; then
        if [ -w "${NGX_EN}" ]; then rm -f "${SITE_LINK}"; else sudo rm -f "${SITE_LINK}"; fi
        if [ -w "${NGX_SITES}" ]; then rm -f "${SITE_FILE}"; else sudo rm -f "${SITE_FILE}"; fi
        echo "[ok] nginx site removed (${SITE_FILE})"
        if [ -z "${R2_NO_SERVICES:-}" ] && command -v nginx >/dev/null 2>&1 \
           && [ -d "${NGX_EN}" ]; then
            if sudo nginx -t 2>/dev/null; then sudo systemctl reload nginx \
               && echo "[ok] nginx reloaded"; fi
        fi
        RM_ANY=1
    fi
    if [ -n "${MR_CONF}" ] && grep -q "${MARK_B}" "${MR_CONF}" 2>/dev/null; then
        sed -i "/${MARK_B//\//\\/}/,/${MARK_E//\//\\/}/d" "${MR_CONF}"
        echo "[ok] [r2_menu] section removed from ${MR_CONF}"
        svc restart moonraker >/dev/null && echo "[ok] moonraker restarted"
        RM_ANY=1
    fi
    if [ -f "${COMP_DIR}/r2_menu.py" ]; then
        rm -f "${COMP_DIR}/r2_menu.py"
        echo "[ok] component removed (${COMP_DIR}/r2_menu.py)"
        RM_ANY=1
    fi
    if [ -e "${WEB_ROOT}" ]; then
        if [ -w "$(dirname "${WEB_ROOT}")" ]; then rm -rf "${WEB_ROOT}"
        else sudo rm -rf "${WEB_ROOT}"; fi
        echo "[ok] page removed (${WEB_ROOT})"
        RM_ANY=1
    fi
    [ "${RM_ANY}" = "1" ] || echo "[i] nothing installed - nothing to remove"
    exit 0
fi

# ---------- update-only (used by update.sh): refresh when installed -------
# Never force-installs: this mode is a NO-OP (exit 0) when no web-LCD
# install exists - the web-LCD stays strictly opt-in.
if [ "${MODE}" = "update-only" ]; then
    if [ ! -f "${SITE_FILE}" ] && [ ! -f "${COMP_DIR}/r2_menu.py" ] \
       && ! grep -q '^\[r2_menu\]' "${MR_CONF:-/nonexistent}" 2>/dev/null; then
        echo "[i] web-LCD not installed here - nothing to refresh"
        echo "    (to add it:  bash $0)"
        exit 0
    fi
    echo "[i] web-LCD install detected - refreshing component + nginx site"
    # fall through into the regular (idempotent) install flow below
fi

# ---------- install: sanity ----------
if [ -z "${MOON_DIR}" ] || [ ! -d "${COMP_DIR}" ]; then
    echo "[!] moonraker components folder not found (tried ~/moonraker, /home/pi/moonraker)"
    echo "    set it manually and re-run:"
    echo "      R2_MOONRAKER_DIR=/path/to/moonraker bash $0"
    exit 1
fi
if [ -z "${MR_CONF}" ]; then
    echo "[!] moonraker.conf not found (tried ~/printer_data/moonraker.conf)"
    echo "    set it manually and re-run:"
    echo "      R2_MOONRAKER_CONF=/path/to/moonraker.conf bash $0"
    exit 1
fi
if [ ! -d "${NGX_SITES}" ]; then
    echo "[!] ${NGX_SITES} does not exist - no nginx sites-available layout?"
    echo "    (MainsailOS/FluiddPi have it. Override: R2_NGINX_SITES=... R2_NGINX_EN=...)"
    exit 1
fi

# 1) component
if cmp -s "${WEB_DIR}/r2_menu.py" "${COMP_DIR}/r2_menu.py" 2>/dev/null; then
    echo "[ok] component already current (${COMP_DIR}/r2_menu.py)"
else
    cp "${WEB_DIR}/r2_menu.py" "${COMP_DIR}/r2_menu.py" \
        && echo "[ok] component copied -> ${COMP_DIR}/r2_menu.py"
fi

# 1b) R208: the page itself -> WEB_ROOT (world-readable, outside /home).
# The old alias into the package dir died the moment ANY path component
# lost its x-bit for others (nginx = www-data, 403 on unreadable static
# files - .136f field log; the API paths kept working, which is why every
# proxy test was green while the page would not even load).
if [ ! -f "${WEB_DIR}/index.html" ]; then
    echo "[!] ${WEB_DIR}/index.html not found - broken package?"
    exit 1
fi
if [ -w "$(dirname "${WEB_ROOT}" 2>/dev/null || echo /nonexistent)" ]; then
    mkdir -p "${WEB_ROOT}"; chmod 755 "${WEB_ROOT}"
    cp -f "${WEB_DIR}/index.html" "${WEB_ROOT}/index.html"
    chmod 644 "${WEB_ROOT}/index.html"
else
    sudo mkdir -p "${WEB_ROOT}"
    sudo chmod 755 "${WEB_ROOT}"
    sudo cp -f "${WEB_DIR}/index.html" "${WEB_ROOT}/index.html"
    sudo chmod 644 "${WEB_ROOT}/index.html"
fi
echo "[ok] page installed -> ${WEB_ROOT}/index.html (served by nginx)"

# 2) moonraker.conf section (marked block, backup, idempotent)
if grep -q '^\[r2_menu\]' "${MR_CONF}"; then
    echo "[ok] [r2_menu] section already present in ${MR_CONF}"
else
    cp "${MR_CONF}" "${MR_CONF}.r2bak-$(date +%Y%m%d-%H%M%S)"
    {
        echo ""
        echo "${MARK_B}"
        echo "[r2_menu]"
        echo "path: ${WEB_DIR}/menu_structure.json"
        echo "${MARK_E}"
    } >> "${MR_CONF}"
    echo "[ok] [r2_menu] section added to ${MR_CONF} (backup .r2bak-* saved)"
fi

# 3) nginx site on a free port (separate file - mainsail config stays untouched)
port_free() {          # /dev/tcp probe: connects = busy
    (echo > "/dev/tcp/127.0.0.1/$1") >/dev/null 2>&1 && return 1 || return 0
}
PORT=""
if [ -f "${SITE_FILE}" ]; then
    _SITE_TXT="$(cat "${SITE_FILE}" 2>/dev/null \
                 || sudo cat "${SITE_FILE}" 2>/dev/null)"
    PORT="$(sed -n 's/.*listen \([0-9]*\).*/\1/p' <<<"${_SITE_TXT}" | head -1)"
    if [ -z "${PORT}" ]; then
        echo "[!] cannot read the existing site file (${SITE_FILE}) - not touching it."
        echo "    fix permissions and re-run:  sudo chmod 644 ${SITE_FILE}"
        exit 1
    fi
    echo "[ok] nginx site already present (port ${PORT}) - updating file"
else
    for p in ${PORTS}; do port_free "$p" && PORT="$p" && break; done
    [ -n "${PORT}" ] || { echo "[!] no free port in ${PORTS}"; exit 1; }
fi
# R206: the CSRF map + Origin strip live in the site file itself so the
# guard is refreshed together with the rest (see header). The template is
# written to a temp file first, then installed via sudo when /etc/nginx
# is not user-writable.
_SITE_TMP="$(mktemp)"
cat > "${_SITE_TMP}" <<EOF
# R2-D2 web-LCD (created by web/install_web.sh - remove with --uninstall)
# R206: the two proxy locations strip the Origin header before Moonraker
# (Moonraker 403-rejects every request whose Origin it does not know -
# browsers send Origin on all command POSTs, so every button died while
# the GET live polls worked). nginx takes over the browser-CSRF check:
# the map only lets requests pass whose Origin is empty (same-origin GETs,
# curl, tools) or exactly this site (http://<host> == Host header) - any
# other website's Origin is answered 403 BEFORE it reaches the printer.
# R207: the comparison is CASE-INSENSITIVE (~*) - the browser lowercases
# the Origin but sends the Host exactly as typed (a bookmarked
# http://Ender-3.local:7126/ would have failed the case-sensitive map and
# answered 403 - .136e field suspicion).
map "\$http_origin|\$http_host" \$r2_csrf_bad {
    default                  1;
    "~^\|"                   0;
    "~*^http://([^|]+)\|\1\$" 0;
}
server {
    listen ${PORT};
    location /r2lcd/ {
        alias ${WEB_ROOT}/;
        index index.html;
    }
    location /server/ {
        if (\$r2_csrf_bad) { return 403; }
        proxy_pass http://127.0.0.1:7125;
        proxy_set_header Host \$host;
        proxy_set_header Origin "";
    }
    location /printer/ {
        if (\$r2_csrf_bad) { return 403; }
        proxy_pass http://127.0.0.1:7125;
        proxy_set_header Host \$host;
        proxy_set_header Origin "";
    }
}
EOF
if [ -w "${NGX_SITES}" ]; then
    cp "${_SITE_TMP}" "${SITE_FILE}"
else
    sudo cp "${_SITE_TMP}" "${SITE_FILE}"
    # mktemp creates 0600 - the site file must stay world-readable (status,
    # port detection and every future refresh read it as the normal user)
    sudo chmod 644 "${SITE_FILE}"
fi
rm -f "${_SITE_TMP}"
if [ -w "${NGX_EN}" ]; then
    mkdir -p "${NGX_EN}"
    ln -sfn "${SITE_FILE}" "${SITE_LINK}"
else
    sudo mkdir -p "${NGX_EN}"
    sudo ln -sfn "${SITE_FILE}" "${SITE_LINK}"
fi
if command -v nginx >/dev/null 2>&1 && [ -z "${R2_NO_SERVICES:-}" ]; then
    if ! sudo nginx -t 2>/dev/null; then
        if [ -w "${NGX_EN}" ]; then rm -f "${SITE_LINK}"; else sudo rm -f "${SITE_LINK}"; fi
        if [ -w "${NGX_SITES}" ]; then rm -f "${SITE_FILE}"; else sudo rm -f "${SITE_FILE}"; fi
        echo "[!] nginx rejected the config (nginx -t failed) - site rolled back,"
        echo "    your existing setup is untouched. Open an issue with 'nginx -t' output."
        exit 1
    fi
    sudo systemctl reload nginx && echo "[ok] nginx reloaded"
else
    echo "[i] nginx test/reload skipped (no nginx here or R2_NO_SERVICES)"
fi

# R207 (.136e field log - "403 again" despite the R206 fix): a written site
# file is NOT a live config. If the reload silently failed, nginx keeps
# serving the OLD site (no Origin strip) and every command POST stays 403
# while the page itself loads fine. So PROVE the guard is live, from the
# Pi, with real requests through the site:
#   - a foreign-origin POST must be rejected BY NGINX (403) - moonraker
#     does not even need to be up for this
#   - a same-origin POST must NOT be 403 (200/404/405/502 all prove the
#     request passed the guard)
# On failure: one reload retry, then the exact one-line fix is printed.
if [ "${R2_NO_SERVICES:-0}" != "1" ] && command -v curl >/dev/null 2>&1 \
   && command -v nginx >/dev/null 2>&1; then
    _guard_test() {
        curl -s -o /dev/null -w '%{http_code}' -m 5 -X POST \
             -H "Origin: http://r2-selftest.invalid" --data "" \
             "http://127.0.0.1:${PORT}/server/r2_menu/status" 2>/dev/null
    }
    _same_test() {
        curl -s -o /dev/null -w '%{http_code}' -m 5 -X POST \
             -H "Origin: http://127.0.0.1:${PORT}" --data "" \
             "http://127.0.0.1:${PORT}/server/r2_menu/status" 2>/dev/null
    }
    _page_test() {
        curl -s -o /dev/null -w '%{http_code}' -m 5 \
             "http://127.0.0.1:${PORT}/r2lcd/" 2>/dev/null
    }
    # R208: the PAGE itself is part of the verdict - the .136f field bug
    # (403 on open) was invisible to the old API-only self-test. ALL
    # checks run, then ONE reload retry, then the verdict names WHAT
    # failed (page vs guard).
    _r2_ok() {
        [ "${_PG}" = "200" ] && [ "${_EV}" = "403" ] \
            && [ "${_SO}" != "403" ] && [ -n "${_SO}" ]
    }
    sleep 1
    _EV="$(_guard_test)"; _SO="$(_same_test)"; _PG="$(_page_test)"
    if _r2_ok; then
        echo "[ok] web-LCD guard self-test: page 200, foreign origin rejected"
        echo "     at the proxy (403), same origin passes (${_SO}) - the web-LCD works"
    else
        echo "[i] web-LCD self-test (page=${_PG:-none} foreign=${_EV:-none} same=${_SO:-none})"
        echo "    - retrying one nginx reload ..."
        sudo nginx -s reload 2>/dev/null || sudo systemctl reload nginx 2>/dev/null
        sleep 1
        _EV="$(_guard_test)"; _SO="$(_same_test)"; _PG="$(_page_test)"
        if _r2_ok; then
            echo "[ok] web-LCD guard self-test PASSED after the reload retry"
            echo "     (page 200, foreign origin 403 at the proxy)"
        elif [ "${_PG}" != "200" ]; then
            echo "[!] web-LCD self-test FAILED: the PAGE answers ${_PG:-nothing}"
            echo "    (expected 200) - nginx cannot serve ${WEB_ROOT}/index.html."
            echo "    Check:  ls -la ${WEB_ROOT}"
            echo "            sudo -u www-data head -c 40 ${WEB_ROOT}/index.html"
        else
            echo "[!] web-LCD self-test FAILED (page 200 but foreign=${_EV:-none}"
            echo "    same=${_SO:-none}) - the new site is not active. One command:"
            echo "        sudo systemctl restart nginx"
        fi
    fi
fi

# 4) restart moonraker so the endpoints come up
svc restart moonraker >/dev/null 2>&1 \
    && echo "[ok] moonraker restarted" \
    || echo "[!] could not restart moonraker - run: sudo systemctl restart moonraker"

IP="$(hostname -I 2>/dev/null | awk '{print $1}')"
echo ""
echo "=============================================================="
echo " DONE - open in any browser on your network:"
echo "        http://${IP:-<this-pi-ip>}:${PORT}/r2lcd/"
echo " Bookmark it (phone/desktop) - same menus as the 12864 LCD,"
echo " live values every 3 s, commands send like the console."
echo " Remove anytime:  bash $0 --uninstall"
echo "=============================================================="
