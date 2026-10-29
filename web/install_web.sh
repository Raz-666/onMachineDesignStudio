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
#
#  OVERRIDES (for tests / exotic setups):
#             R2_MOONRAKER_DIR  R2_MOONRAKER_CONF  R2_NGINX_SITES
#             R2_NGINX_EN  R2_NO_SERVICES (skip systemctl calls)
# =====================================================================================
set -u

WEB_DIR="$(cd "$(dirname "$0")" && pwd)"          # .../klipper-e3-r2d2/web
PKG_DIR="$(dirname "$WEB_DIR")"                   # .../klipper-e3-r2d2
CFG_DIR="$(dirname "$PKG_DIR")"                   # .../printer_data/config
USER_HOME="${HOME:-/home/pi}"

MODE="install"
[ "${1:-}" = "--uninstall" ] && MODE="uninstall"
[ "${1:-}" = "--status" ] && MODE="status"

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
    echo "config    : ${MR_CONF:-not found} $([ -f "${MR_CONF:-/nonexistent}" ] && grep -q '^\[r2_menu\]' "${MR_CONF}" 2>/dev/null && echo '[section ok]' || echo '[no section]')"
    echo "nginx     : ${SITE_FILE} $([ -f "${SITE_FILE}" ] && echo '[ok]' || echo '[missing]')"
    if [ -f "${SITE_FILE}" ]; then
        P="$(sed -n 's/.*listen \([0-9]*\).*/\1/p' "${SITE_FILE}" | head -1)"
        echo "URL       : http://<this-pi>:${P:-?}/r2lcd/"
    fi
    exit 0
fi

# ---------- uninstall ----------
if [ "${MODE}" = "uninstall" ]; then
    RM_ANY=0
    if [ -e "${SITE_LINK}" ] || [ -e "${SITE_FILE}" ]; then
        rm -f "${SITE_LINK}" "${SITE_FILE}"
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
    [ "${RM_ANY}" = "1" ] || echo "[i] nothing installed - nothing to remove"
    exit 0
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
    PORT="$(sed -n 's/.*listen \([0-9]*\).*/\1/p' "${SITE_FILE}" | head -1)"
    echo "[ok] nginx site already present (port ${PORT}) - updating file"
else
    for p in ${PORTS}; do port_free "$p" && PORT="$p" && break; done
    [ -n "${PORT}" ] || { echo "[!] no free port in ${PORTS}"; exit 1; }
fi
cat > "${SITE_FILE}" <<EOF
# R2-D2 web-LCD (created by web/install_web.sh - remove with --uninstall)
server {
    listen ${PORT};
    location /r2lcd/ {
        alias ${WEB_DIR}/;
        index index.html;
    }
    location /server/ {
        proxy_pass http://127.0.0.1:7125;
        proxy_set_header Host \$host;
    }
    location /printer/ {
        proxy_pass http://127.0.0.1:7125;
        proxy_set_header Host \$host;
    }
}
EOF
mkdir -p "${NGX_EN}"
ln -sfn "${SITE_FILE}" "${SITE_LINK}"
if command -v nginx >/dev/null 2>&1 && [ -z "${R2_NO_SERVICES:-}" ]; then
    if ! sudo nginx -t 2>/dev/null; then
        rm -f "${SITE_LINK}" "${SITE_FILE}"
        echo "[!] nginx rejected the config (nginx -t failed) - site rolled back,"
        echo "    your existing setup is untouched. Open an issue with 'nginx -t' output."
        exit 1
    fi
    sudo systemctl reload nginx && echo "[ok] nginx reloaded"
else
    echo "[i] nginx test/reload skipped (no nginx here or R2_NO_SERVICES)"
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
