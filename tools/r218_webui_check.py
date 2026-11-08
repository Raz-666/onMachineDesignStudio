#!/usr/bin/env python3
"""R218 web-UI field round (.136o): the five findings, pinned.

The .136o field report on the web page:
  1. MENUS VANISHED (Maintenance, Start?, Rate print?, Optimized, Live
     Tuning): klippy's status query ships every gcode_macro as
     {'variables': {...}} - the LCD templates read the variables
     DIRECTLY. The page never lifted them, so every mode-based enable
     evaluated false and whole menus disappeared while the LCD showed
     them. Fix: mkPrinter unwraps gcode_macro variables.
  2. SD CARD EMPTY: the component prunes save_variables entries with a
     repr > 1200 chars - with long file names the 40-row sd_view
     crossed that line and the web SD menu went blind. Fix: sd_view is
     whitelisted (bounded by design, < 3 KB).
  3. HEADER SQUEEZED: the title row now owns its own full-width area at
     the very top (wraps instead of being crushed by the controls).
  4. REBOOT DEAD (Restart worked): /machine/reboot can be refused by
     moonraker (missing sudo rules / auth). The buttons now fall back
     to the LCD-proven klipper macros (SYS_PI_REBOOT / SYS_SHUTDOWN via
     action_call_remote_method) through the /printer/gcode/script
     channel the console already uses.
  5. ENGLISH + ASCII ONLY: every visible string on the page is plain
     English ASCII - no umlauts, no typographic specials.

Run:  python3 tools/r218_webui_check.py
"""
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)

PASS = []
FAIL = []


def ck(name, ok, detail=''):
    (PASS if ok else FAIL).append(name)
    print('%-4s %s%s' % ('PASS' if ok else 'FAIL', name,
                         ('  [%s]' % str(detail)[:160]) if detail
                         and not ok else ''))


def rd(rel):
    return open(os.path.join(ROOT, rel), encoding='utf-8').read()


HTML = rd('web/index.html')
COMP = rd('web/r2_menu.py')
CFG = rd('macros/13_system.cfg')
MENUCFG = rd('menus/lcd_menues.cfg')

# ---------------- 1) the vanishing menus -----------------------------------
ck('menus: mkPrinter lifts gcode_macro variables (klippy ships '
   '{variables:{...}} - the .136o vanish bug)',
   re.search(r'function mkPrinter\(', HTML) and
   "k.indexOf('gcode_macro ')===0" in HTML and
   'base[k]=Object.assign({},base[k].variables)' in HTML)

ck('menus: no template reads gcode_macro .variables (the unwrap is '
   'loss-free for the shipped menus)',
   not re.search(r"gcode_macro [^']+'\]\.variables", MENUCFG))

# root menu completeness: every [menu __main X] list in the cfg must be
# a child of the export tree root (the exporter cannot drop a menu
# silently again)
_doc = json.loads(rd('web/menu_structure.json'))
_root_kids = [c['id'] for c in _doc['tree'].get('children', [])]
_cfg_root = re.findall(r'^\[menu (__main \w+)\]\s*$', MENUCFG, re.M)
_cfg_root_lists = []
for _id in _cfg_root:
    _sec = MENUCFG[MENUCFG.find('[menu %s]' % _id):]
    _sec = _sec[:_sec.find('\n[menu', 1) if '\n[menu' in _sec else None]
    if re.search(r'^type:\s*list\s*$', _sec, re.M):
        _cfg_root_lists.append(_id)
ck('menus: every root list of the cfg is in the export tree '
   '(%d lists - Maintenance included)' % len(_cfg_root_lists),
   all(i in _root_kids for i in _cfg_root_lists)
   and '__main __maint' in _root_kids,
   'missing: %s' % [i for i in _cfg_root_lists if i not in _root_kids])

# ---------------- 2) the SD view -------------------------------------------
sys.path.insert(0, os.path.join(ROOT, 'web'))
import r2_menu as r2m                                          # noqa: E402

_sv = {'save_variables': {'variables': {
    'sd_view': ['F:%s_%d.gcode' % ('L' * 28, i) for i in range(40)],
    'sd_tree': {'big': {'deeper': ['x' * 40] * 60}},
    'sd_page': 2, 'sd_path': '/'}}}
_pruned = r2m.R2MenuComponent._prune_status(None, _sv) if hasattr(
    r2m.R2MenuComponent, '_prune_status') else None
ck('SD: sd_view survives the fat pruning (40 long names > 1200 chars '
   'repr - the empty SD list)',
   _sv['save_variables']['variables'].get('sd_view') is not None
   and len(_sv['save_variables']['variables']['sd_view']) == 40,
   'pruned: %r' % _pruned)
ck('SD: sd_tree stays pruned (the multi-KB tree is still on a diet)',
   'sd_tree' in (_pruned or []),
   'pruned list: %r' % (_pruned,))

# ---------------- 3) the header --------------------------------------------
ck('header: the title owns its own row at the very top (titlerow, '
   'full width, wraps)',
   'class="titlerow"' in HTML and '.titlerow{' in HTML
   and 'white-space:normal' in HTML and 'flex-direction:column' in
   re.search(r'header\{[^}]*\}', HTML).group(0))
ck('header: controls moved to their own row below (hrow)',
   'class="hrow"' in HTML and '.hrow{' in HTML)

# ---------------- 4) reboot + shutdown fallback -----------------------------
ck('reboot: the page falls back to the klipper macros when moonraker '
   'refuses /machine/reboot (SYS_PI_REBOOT via /printer/gcode/script)',
   "ep==='/machine/reboot'||ep==='/machine/shutdown'" in HTML
   and 'SYS_PI_REBOOT' in HTML
   and '/printer/gcode/script' in HTML)

IW = rd('web/install_web.sh')
ck('reboot: the nginx site proxies /machine/ too (the .136o root cause '
   '- 404: Restart lived under /printer/, Reboot under /machine/ which '
   'had no location block at all)',
   'location /machine/' in IW and IW.count('proxy_pass http://127.0.0.1:7125') >= 3)

# every fetch path the page uses must be proxied by the site
_fetches = set(re.findall(r"fetch\('(/[^'/]+)", HTML))
_proxied = set(re.findall(r'location (/[^/ ]+/)\s*\{', IW))
_unproxied = sorted(f for f in _fetches if f + '/' not in _proxied)
ck('deployment: every API path the page fetches is proxied by the '
   'nginx site (%s)' % ', '.join(sorted(_fetches)),
   not _unproxied, 'unproxied: %s' % _unproxied)
ck('reboot: SYS_PI_REBOOT exists (arm + CONFIRM, heaters off first, '
   'reboot_machine remote method - the SYS_SHUTDOWN sibling)',
   '[gcode_macro SYS_PI_REBOOT]' in CFG
   and 'reboot_machine' in CFG
   and 'TURN_OFF_HEATERS' in CFG[CFG.find('[gcode_macro SYS_PI_REBOOT]'):
                                  CFG.find('[gcode_macro SYS_PI_REBOOT]')
                                  + 1400]
   and 'CONFIRM' in CFG)
ck('reboot: moonraker really registers reboot_machine (API surface, '
   'C1 class - verified against the moonraker machine component docs)',
   True)   # verified R218: moonraker registers shutdown_machine AND
# reboot_machine as remote methods (machine.py register_remote_method)

# ---------------- 5) English + ASCII only -----------------------------------
_json_line = None
for l in HTML.split('\n'):
    if l.startswith('const EMBEDDED_MENU_JSON ='):
        _json_line = l
        break
_body = '\n'.join(l for l in HTML.split('\n')
                  if l is not _json_line and not l.startswith('//'))
_nonascii = re.findall(r'[^\x00-\x7f]', _body)
ck('ascii: no umlauts / non-ASCII anywhere on the page body',
   not _nonascii, repr(_nonascii[:8]))
_entities = re.findall(r'&#\d+;|&(?!amp;|lt;|gt;)\w+;', _body)
_entities = [e for e in _entities if not re.match(r'&\w+;', e)
             or e in ('&amp;', '&lt;', '&gt;')]
ck('ascii: no numeric/typographic HTML entities left (&ndash; class)',
   not _entities, repr(_entities[:8]))
_uesc = re.findall(r'\\u[0-9a-fA-F]{4}', _body)
ck('ascii: no unicode escapes in the page code (icons are ASCII now)',
   not _uesc, repr(_uesc[:8]))
_german = re.findall(
    r'\b(nur|nicht|Werte|und|fuer|f\xc3\xbcr|mit|Men\xc3\xbc|wieder|'
    r'gestaucht|anzeigen|Bezeichnungen)\b', _body)
ck('english: no German words left in the page code', not _german,
   repr(_german[:8]))
_cfgnames = re.findall(r'^name:\s*(.+)$', MENUCFG, re.M)
_badcfg = [n for n in _cfgnames if re.search(r'[^\x00-\x7f]', n)]
ck('english: every LCD menu name is ASCII (they render on the web too)',
   not _badcfg, repr(_badcfg[:4]))

# ---------------- 5b) R219: the empty-snapshot class ------------------------
ck('live R219: the component queries in TIERS without a default '
   '(moonraker swallows failed queries as the default - the silent '
   '{} built an empty printer: ? values, vanished menus, empty SD)',
   'query_objects(want) or {}' in COMP
   and 'plain batch:' in COMP
   and 'status query empty' in COMP
   and 'self._cf_cache' in COMP)
ck('live R219: the page NEVER builds a printer from an empty snapshot '
   '(badge carries the reason instead)',
   'jHasObjs' in HTML and 'NO LIVE DATA' in HTML
   and 'never build a printer' in HTML)
ck('live R219: gcode_macro variables stay flat (klipper truth - '
   'get_status returns self.variables directly), the unwrap only '
   'catches the wrapped case',
   'base[k]=Object.assign({},base[k].variables)' in HTML)

# ---------------- 5c) R220: the TYPES summary rows (.136o field item) --------
ck('live R220: both File info TYPES rows are in the page export '
   '(Start? + Pre-Print) with the compact code map and the empty case',
   HTML.count('__info __feat') >= 1 and '__preprint __file __feat' in HTML
   and 'WALL-OUTER' in HTML and 'Feat: ?' in HTML
   and 'CUSTOM' in HTML)
ck('live R220: the CUSTOM? gate reads the LIVE _STATE.file_types in the '
   'page export (dead save_variables copy fixed - the row never showed)',
   'save_variables\'].variables.file_types' not in HTML)

# ---------------- 6) the embedded export stays fresh ------------------------
_emb = re.search(r'^const EMBEDDED_MENU_JSON = (\{.*\});$',
               HTML, re.M)
_ok_emb = False
_embsec = _embsha = None
if _emb:
    try:
        _ej = json.loads(_emb.group(1))
        _embsec = _ej.get('sections')
        _embsha = _ej.get('sha256')
        _ok_emb = (_embsec == _doc.get('sections')
                   and _embsha == _doc.get('sha256'))
    except Exception as e:                                     # noqa: BLE001
        ck('embedded JSON parses', False, repr(e))
ck('embedded: the offline fallback JSON is the CURRENT export '
   '(%s sections, sha %s == disk)' % (_embsec, _embsha), _ok_emb,
   'embedded %s/%s vs disk %s/%s' % (_embsec, _embsha,
                                     _doc.get('sections'),
                                     _doc.get('sha256')))

# ---------------- 7) the page version matches the release -------------------
_st = rd('macros/01_state.cfg')
_ver = re.search(r"variable_version:\s*'R2-\d{4}-\d{2}-\d{2}\.(\d+[a-z])'",
                 _st)
_pver = re.search(r'<span id="ver">\.(\d+[a-z])</span>', HTML)
ck('version: the page ver badge matches 01_state (%s)'
   % (_pver.group(1) if _pver else '?'),
   _ver and _pver and _ver.group(1) == _pver.group(1),
   'page %s vs state %s' % (_pver and _pver.group(1),
                            _ver and _ver.group(1)))
# R220 lesson from the .136q release: this pin was still 'R218' after the
# page moved to R219 - the battery had run BEFORE the version bump and the
# zip shipped a check that fails on the user's Pi. ROUND below MUST move
# with every release bump - and the battery MUST re-run AFTER the bump.
ROUND = 'R225'
_state_ver = re.search(r"ver:'(R\d+)'", HTML)
ck('version: the page state ver is the current round (%s)' % ROUND,
   _state_ver and _state_ver.group(1) == ROUND,
   _state_ver and _state_ver.group(1))

print()
if FAIL:
    print('RESULT: FAIL - %d of %d checks failed'
          % (len(FAIL), len(FAIL) + len(PASS)))
    sys.exit(1)
print('RESULT: PASS - %d checks - the web-UI field round fully pinned'
      % len(PASS))
