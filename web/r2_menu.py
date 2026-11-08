# r2_menu.py - Moonraker extension: the R2 menu tree as JSON (.136c, R204:
# R211: lookup_component - the REAL moonraker Server API)
# adds /server/r2_menu/live - the pruned printer snapshot for live values;
# R210/.136i: live handler hardened - reason always visible, per-object
# retry, klippy-state precheck, dashboard objects, value pruning)
# ============================================================================
#  INSTALL (one time):
#    cp web/r2_menu.py ~/moonraker/moonraker/components/r2_menu.py
#    # moonraker.conf:
#    [r2_menu]
#    path: ~/klipper-e3-r2d2/web/menu_structure.json
#    sudo systemctl restart moonraker
#
#  ENDPOINTS (same origin as Mainsail - the demo page web/index.html and
#  any other client can fetch them without a second stack or auth dance):
#    GET /server/r2_menu/tree      -> the exported menu tree + meta
#    GET /server/r2_menu/status    -> {ok, sections, sha256, mtime}
#    GET /server/r2_menu/live      -> R201: a minimal PRINTER SNAPSHOT for
#                                     evaluating the menu templates live.
#                                     R204 (.136c): queries ONLY the objects
#                                     the menu templates reference (the
#                                     export's live_objects list - 12 on the
#                                     field Pi, not every gcode_macro!). The
#                                     .136 version queried ~300 macro objects
#                                     and blocked klippy's reactor 0.7 s per
#                                     poll ('Neopixel update did not
#                                     succeed' - the Timer-too-close class).
#                                     Fat values (sd_tree, ...) are pruned so
#                                     the Pi Zero ships bytes, not kilobytes;
#                                     2.5 s cache. {ok: false, reason} while
#                                     klippy is down - raw view then.
#    POST /server/r2_menu/refresh  -> re-run tools/menu_json_export.py
#                                     (if the tool exists on this host)
#    GET /server/r2_menu/pistats   -> R216 (.136n): CPU load + RAM + temp
#                                     of the Pi (read from /proc + sysfs,
#                                     NEVER via klippy - the MCU never
#                                     hears about it). CPU load is a real
#                                     /proc/stat delta (0.25 s window),
#                                     cached 30 s so several open tabs
#                                     share one measurement.
#    GET /server/r2_menu/klippylog?window=3h|day|boot|all
#                                  -> R216 (.136n): klippy.log as JSON
#                                     {ok, text, lines, window} - the page
#                                     turns it into a .txt download. The
#                                     windows: 3h = last three hours,
#                                     day = since midnight, boot = since
#                                     the last Pi boot (/proc/uptime),
#                                     all = the whole log. Tail cap 4000
#                                     lines so a huge log cannot block.
#                                     config: log_path (default
#                                     ~/printer_data/logs/klippy.log).
#
#  WHY THIS SHAPE (the .135 web-UI recommendation, see DISPLAYS_DRUCKER_TESTS
#  section B): the LCD menu (menus/lcd_menues.cfg, 1.910 render tests) stays
#  the ONE truth. We do not rebuild a menu system in a browser - we EXPOSE
#  the existing one. Clients that want live values evaluate the jinja
#  fragments themselves against moonraker's /printer/objects-query (the
#  templates read printer[...] and save_variables - both available there);
#  everything that fires a command uses moonraker's own
#  /printer/gcode/script endpoint. This component is deliberately ~100
#  lines: no state, no polling loops, no websocket fan-out.
#
#  Tested offline by tools/r193_gen_sweep.py (fake moonraker app object:
#  endpoint registration + handler responses + refresh without the tool).
import asyncio
import os
import re
import subprocess

MENU_PATH_DEFAULT = '~/klipper-e3-r2d2/web/menu_structure.json'
EXPORT_TOOL_DEFAULT = '~/klipper-e3-r2d2/tools/menu_json_export.py'


def _tool_from_path(menu_path):
    """R225 (.136w audit): derive the export tool from the menu's json
    path - .../web/menu_structure.json and .../tools/menu_json_export.py
    live in the SAME package root. The DEFAULT tool path only exists
    where the repo sits in $HOME (dev sandbox); on the documented Pi
    install the package lives under ~/printer_data/config/ and the
    refresh silently reloaded the STALE embedded json instead of
    re-exporting (r197 T2 ran green only because the sandbox repo
    happens to sit in $HOME). Returns the candidate path or None."""
    p = (menu_path or '').replace('\\', '/')
    m = re.search(r'^(.*)/web/menu_structure\.json$', p)
    if not m:
        return None
    cand = m.group(1) + '/tools/menu_json_export.py'
    return cand if os.path.isfile(cand) else None
# R204: always served even if an old export lacks live_objects.
# R210 (.136i): + the DASHBOARD set - the page's status strip reads
# temps/fan/feed/flow/PA/accel/progress/layer/feature from these.
DEFAULT_LIVE_OBJECTS = ('gcode_macro _STATE', 'gcode_macro _PREVIEW',
                        'save_variables', 'print_stats', 'gcode_move',
                        'display_status',
                        'extruder', 'heater_bed', 'fan', 'virtual_sdcard',
                        'toolhead')


def load_doc(path):
    import json
    with open(os.path.expanduser(path), 'r') as f:
        return json.load(f)


class R2MenuComponent:
    def __init__(self, config):
        self.server = config.get_server()
        self.path = os.path.expanduser(
            config.get('path', MENU_PATH_DEFAULT))
        # R225 (.136w audit): precedence - (1) an EXPLICIT export_tool
        # (install_web.sh writes it since .136w), (2) the tool derived
        # from the configured json path (same package root - heals every
        # install where the section predates the export_tool line),
        # (3) the $HOME default (dev sandbox).
        _cfg_tool = config.get('export_tool', None)
        _derived = _tool_from_path(self.path)
        if _cfg_tool:
            self.tool = os.path.expanduser(_cfg_tool)
        elif _derived:
            self.tool = _derived
        else:
            self.tool = os.path.expanduser(EXPORT_TOOL_DEFAULT)
        self.log_path = os.path.expanduser(
            config.get('log_path', '~/printer_data/logs/klippy.log'))
        self._pi_cache = None          # R216: 30 s CPU/RAM cache
        self._pi_t = 0.0
        self.lock = asyncio.Lock()
        self.doc = None
        self.last_mtime = 0.0
        self._live_cache = None        # R204: 2.5 s printer-snapshot cache
        self._live_t = 0.0
        self._cf_cache = None          # R219: configfile settings-keys,
        self._cf_t = 0.0               # 60 s cache (megabyte fallback)
        self.server.register_endpoint(
            '/server/r2_menu/tree', ['GET'],
            self._handle_tree)
        self.server.register_endpoint(
            '/server/r2_menu/status', ['GET'],
            self._handle_status)
        self.server.register_endpoint(
            '/server/r2_menu/live', ['GET'],
            self._handle_live)
        self.server.register_endpoint(
            '/server/r2_menu/refresh', ['POST'],
            self._handle_refresh)
        self.server.register_endpoint(          # R216 (.136n)
            '/server/r2_menu/pistats', ['GET'],
            self._handle_pistats)
        self.server.register_endpoint(          # R216 (.136n)
            '/server/r2_menu/klippylog', ['GET'],
            self._handle_klippylog)
        self.server.register_remote_method('r2_menu_refresh', None)
        # R216 field fix (.136n): add_log_rollback_handler does NOT exist
        # in this moonraker build - the call killed the whole component at
        # load time ('Unable to load component: (r2_menu)', the machine
        # panel endpoints never registered). The handler was a dead
        # pass-stub anyway: nothing to roll back, so nothing to register.

    async def _ensure_loaded(self):
        async with self.lock:
            try:
                mt = os.path.getmtime(self.path)
            except OSError:
                self.doc = None
                return
            if self.doc is None or mt != self.last_mtime:
                self.doc = await self.server.event_loop.run_in_thread(
                    load_doc, self.path)
                self.last_mtime = mt

    async def _handle_tree(self, web_request):
        await self._ensure_loaded()
        if self.doc is None:
            raise self.server.error('menu export not found: %s '
                                    '(run tools/menu_json_export.py)'
                                    % self.path, 404)
        return self.doc

    async def _handle_status(self, web_request):
        await self._ensure_loaded()
        if self.doc is None:
            return {'ok': False, 'path': self.path}
        return {'ok': True, 'sections': self.doc.get('sections'),
                'sha256': self.doc.get('sha256'),
                'counts': self.doc.get('counts')}

    def _lookup_klippy_apis(self):
        """R211 (.136i field log: badge 'Server' object has no attribute
        'lookup_object'): moonraker's Server API is lookup_component() -
        this component had called the KLIPPER-config-style lookup_object(),
        so EVERY /live poll failed since the extension existed (raw labels,
        no LCD hiding, no dashboard). The offline fake in r197 had
        implemented the wrong method - a fake RICHER than reality greens
        every offline test while the Pi raises. lookup_component first,
        the old name kept as a fallback."""
        for name in ('lookup_component', 'lookup_object'):
            fn = getattr(self.server, name, None)
            if fn is not None:
                return fn('klippy_apis')
        raise AttributeError(
            'server has neither lookup_component nor lookup_object')

    def _live_wanted(self):
        wanted = set((self.doc or {}).get('live_objects') or ())
        wanted.update(DEFAULT_LIVE_OBJECTS)
        return wanted

    def _prune_status(self, status):
        """R204/R210: ship VALUES, not kilobytes - and only what the menu
        templates actually read. Returns the list of pruned keys."""
        pruned = []
        try:    # save_variables: fat variables (sd_tree, gen_files, ...)
            sv = status.get('save_variables', {}).get('variables', {})
            # R218 (.136o field log: 'SD card menu has no contents'):
            # sd_view is the LCD's CURRENT page (max 40 rows, bounded by
            # design) and the web SD menu templates read exactly this -
            # with long file names its repr crossed the 1200 fat limit
            # and the whole SD list went empty on the page while the LCD
            # showed the files. It is whitelisted here (costs < 3 KB);
            # sd_tree and the other fat vars stay pruned.
            keep_218 = ('sd_view',)
            for k in list(sv):
                if k in keep_218:
                    continue
                try:
                    fat = len(repr(sv[k])) > 1200
                except Exception:                               # noqa: BLE001
                    fat = True
                if fat:
                    pruned.append(k)
                    del sv[k]
        except Exception:                                       # noqa: BLE001
            pass
        try:    # configfile.settings: the menus only test section NAMES
            cf = status.get('configfile')
            if cf and isinstance(cf.get('settings'), dict):
                cf['settings'] = {k: None for k in cf['settings']}
                pruned.append('configfile.settings(values)')
        except Exception:                                       # noqa: BLE001
            pass
        try:    # bed_mesh.profiles: the menus only use the profile NAMES
            bm = status.get('bed_mesh')
            if bm and isinstance(bm.get('profiles'), dict):
                bm['profiles'] = {k: {} for k in bm['profiles']}
                pruned.append('bed_mesh.profiles(values)')
        except Exception:                                       # noqa: BLE001
            pass
        try:    # exclude_object.objects: |length and [i].name only
            eo = status.get('exclude_object')
            if eo and isinstance(eo.get('objects'), list):
                eo['objects'] = [
                    {'name': o.get('name')} for o in eo['objects']
                    if isinstance(o, dict)][:64]
                pruned.append('exclude_object.objects(polygons)')
        except Exception:                                       # noqa: BLE001
            pass
        return pruned

    async def _handle_live(self, web_request):
        """R201/R204/R210: a minimal printer snapshot for live evaluation.

        The page evaluates the menu name:/enable: jinja fragments against
        this data. R204 (.136c field log): query ONLY the objects the
        templates reference - the export's live_objects list, intersected
        with the real object list. The .136 version queried EVERY
        gcode_macro (~300 on the field Pi, each serializing all its
        variables) and blocked klippy's reactor for 0.7 s per poll -
        'Neopixel update did not succeed' right after, the Timer-too-close
        class from .125. PRUNING stays: fat values are dropped and NAMED
        in 'pruned'. Cached 2.5 s (the page polls every 3 s - at most ONE
        real klippy query per poll, shared across tabs).

        R210 (.136h field log: the page badge stuck at 'Klipper nicht
        bereit' although klippy was fine): this handler's failures were
        INVISIBLE - the page threw the reason away and any raised
        ServerError became an HTTP error the page could only read as
        'not ready'. Now: NEVER raise, ALWAYS answer
        {ok, reason | objects, pruned, skipped}, precheck the klippy
        state, and if the batch query fails retry PER OBJECT so one bad
        object cannot kill the whole snapshot (the failing objects are
        named in 'skipped' and the page SHOWS the reason)."""
        import time as _t
        await self._ensure_loaded()      # the doc carries live_objects
        if self._live_cache is not None and _t.monotonic() - self._live_t < 2.5:
            return self._live_cache
        try:
            state = self.server.get_klippy_state()
        except Exception:                                       # noqa: BLE001
            state = 'ready'              # older moonraker: no such method
        if state != 'ready':
            out = {'ok': False, 'reason': 'klippy state: %s' % state}
            return out
        try:
            apis = self._lookup_klippy_apis()
            objs = set(await apis.get_object_list())
        except self.server.error as e:
            return {'ok': False, 'reason': str(e)}
        except Exception as e:                                   # noqa: BLE001
            return {'ok': False, 'reason': 'object list: %s' % e}
        wanted = self._live_wanted()
        # R215 (.136l field log): 'configfile: None' serializes the WHOLE
        # object in klippy - including the raw config text (megabytes on
        # this install). The menus only test section names in .settings,
        # so ask for 'settings' and let _prune_status drop the values.
        # This was the 0.2-0.7 s reactor stall every poll - one of the
        # 'Timer too close' contributors while the page was open.
        want = {o: ('settings' if o == 'configfile' else None)
                for o in objs if o in wanted}
        # R219 (.136q field log: live values '?', Maintenance gone, SD
        # empty - ALL THREE at once): moonraker's query_objects SWALLOWS
        # klippy errors and returns the DEFAULT - a failed batch query
        # came back as a silent {} while this handler said ok:True. The
        # page then built an EMPTY printer: every value '?', every
        # mode-based enable false (whole menus 'vanished') and sd_view
        # undefined (SD list empty). The battery fakes either returned
        # data or RAISED, so the swallow path was never exercised - the
        # R211 lesson (a fake richer than reality) again.
        # New shape: every query runs WITHOUT a default (errors raise),
        # in tiers - (1) the field-list batch, (2) the all-None batch
        # (an older klippy may reject field lists; configfile then rides
        # the 60 s cache so the megabytes transit at most once a minute),
        # (3) per-object (one bad object must not kill the snapshot).
        # An EMPTY result at the end answers ok:False WITH the reason -
        # the page never fakes a printer again.
        status = {}
        skipped = []
        if self._cf_cache is not None and _t.monotonic() - self._cf_t < 60.0:
            want.pop('configfile', None)   # the 60 s settings-keys cache
        try:
            status = dict(await apis.query_objects(want) or {})
        except Exception as e:                                   # noqa: BLE001
            skipped.append('batch: %s' % e)
            try:
                status = dict(await apis.query_objects(
                    {o: None for o in want}) or {})
            except Exception as e2:                              # noqa: BLE001
                skipped.append('plain batch: %s' % e2)
                for o in sorted(want):
                    try:
                        one = await apis.query_objects({o: None}) or {}
                        if one.get(o) is not None:
                            status[o] = one[o]
                    except Exception as e3:                      # noqa: BLE001
                        skipped.append('%s: %s' % (o, e3))
        status = {k: v for k, v in status.items() if v is not None}
        if want and not status:
            out = {'ok': False,
                   'reason': 'status query empty (%s)'
                             % '; '.join(skipped[:3] or ['no objects'])}
            self._live_cache = out
            self._live_t = _t.monotonic()
            return out
        # fill the configfile 60 s cache (pruned to the section-name keys
        # the menus test - the values never survive _prune_status anyway)
        cfv = status.get('configfile')
        if cfv and isinstance(cfv.get('settings'), dict):
            self._cf_cache = {'settings': {k: None
                                           for k in cfv['settings']}}
            self._cf_t = _t.monotonic()
        elif self._cf_cache is not None and 'configfile' in objs:
            status['configfile'] = dict(self._cf_cache)
        pruned = self._prune_status(status)
        # R212 (.136k field log: the generator menu entries vanished from
        # the web-LCD): enables test OBJECT EXISTENCE
        # ('gcode_macro _GENERATORS' in printer) - the LCD's printer knows
        # every klippy object, the snapshot only ships the ~16 with values,
        # so those tests answered False and the page hid the entries. The
        # full object-name list is already fetched here - ship it as
        # 'available' and the page materializes the names it does not have.
        out = {'ok': True, 'objects': status, 'pruned': pruned,
               'available': sorted(objs)}
        if skipped:
            out['skipped'] = skipped
        self._live_cache = out
        self._live_t = _t.monotonic()
        return out

    async def _handle_refresh(self, web_request):
        # the lock guards the SUBPROCESS alone - _ensure_loaded takes it
        # again afterwards (an asyncio.Lock is NOT reentrant: holding it
        # here while _ensure_loaded waits for it deadlocks the endpoint -
        # found by the r197 fake-moonraker test)
        re_exported = False
        async with self.lock:
            # R224 (.136v field review): X_OK was required here although the
            # subprocess runs 'python3 <tool>' - a 0644-unpacked tool (every
            # zip without permission bits) silently skipped the re-export
            # and just reloaded the STALE embedded json. Presence is enough.
            if not os.path.isfile(self.tool):
                pass           # not present - just reload
            else:
                re_exported = True
                try:
                    proc = await asyncio.create_subprocess_exec(
                        'python3', self.tool,
                        stdout=asyncio.subprocess.PIPE,
                        stderr=asyncio.subprocess.STDOUT)
                except (OSError, ValueError) as e:
                    re_exported = False
                    raise self.server.error('refresh failed: %s' % e, 500)
                out, _ = await proc.communicate()
                if proc.returncode != 0:
                    raise self.server.error(
                        'export failed: %s' % out.decode(errors='replace'),
                        500)
                self.doc = None
                self.last_mtime = 0.0
        await self._ensure_loaded()
        if not re_exported:
            return {'ok': self.doc is not None,
                    'reExported': False,
                    'sections': (self.doc or {}).get('sections')}
        return {'ok': self.doc is not None, 'reExported': True,
                'sections': (self.doc or {}).get('sections'),
                'output': (out.decode(errors='replace')
                           if isinstance(out, bytes) else '').strip()}

    async def _handle_pistats(self, web_request):
        """R216 (.136n): Pi CPU/RAM/temp for the web console live strip.

        Reads /proc/stat (a REAL delta over 0.25 s, not the meaningless
        lifetime average), /proc/meminfo and sysfs thermal - all host
        files, nothing goes through klippy, so the MCU load is exactly
        zero. Cached 30 s: the page polls once a minute and several tabs
        share one measurement. The measurement runs in a worker thread -
        the 0.25 s sleep never blocks moonraker's loop."""
        import time as _t
        if self._pi_cache is not None and _t.monotonic() - self._pi_t < 30:
            return self._pi_cache
        out = await self.server.event_loop.run_in_thread(self._pi_measure)
        self._pi_cache = out
        self._pi_t = _t.monotonic()
        return out

    def _pi_measure(self):

        def _read_cpu_ticks():
            with open('/proc/stat', 'r') as f:
                parts = f.readline().split()[1:5]
            vals = [int(x) for x in parts]
            return sum(vals), vals[3]

        import time as _t
        cpu = None
        try:
            total1, idle1 = _read_cpu_ticks()
            _t.sleep(0.25)
            total2, idle2 = _read_cpu_ticks()
            dt, di = total2 - total1, idle2 - idle1
            if dt > 0:
                cpu = max(0.0, min(100.0, 100.0 * (1.0 - di / dt)))
        except Exception:                                       # noqa: BLE001
            cpu = None
        ram_used = ram_total = ram_pct = None
        try:
            info = {}
            with open('/proc/meminfo', 'r') as f:
                for line in f:
                    k, _, v = line.partition(':')
                    info[k.strip()] = int(v.split()[0])       # kB
            ram_total = info.get('MemTotal')
            avail = info.get('MemAvailable')
            if ram_total and avail is not None:
                ram_used = ram_total - avail
                ram_pct = 100.0 * ram_used / ram_total
        except Exception:                                       # noqa: BLE001
            pass
        temp = None
        try:
            with open('/sys/class/thermal/thermal_zone0/temp', 'r') as f:
                temp = int(f.read().strip()) / 1000.0
        except Exception:                                       # noqa: BLE001
            pass
        uptime = None
        try:
            with open('/proc/uptime', 'r') as f:
                uptime = float(f.read().split()[0])
        except Exception:                                       # noqa: BLE001
            pass
        return {'ok': cpu is not None or ram_total is not None,
                'cpu': cpu, 'ram_used_mb': (round(ram_used / 1024.0)
                                            if ram_used is not None
                                            else None),
                'ram_total_mb': (round(ram_total / 1024.0)
                                 if ram_total is not None else None),
                'ram_pct': ram_pct, 'temp_c': temp, 'uptime_s': uptime}

    async def _handle_klippylog(self, web_request):
        """R216 (.136n): klippy.log as JSON for the .txt download button.

        window=3h|day|boot|all - the file read AND the timestamp filter
        run in a worker thread (a big log must never block moonraker's
        loop). Lines without a parseable klippy timestamp keep the
        timestamp of the previous line so context survives the cut.
        Tail cap 4000 lines after the window cut."""
        window = (web_request.get('window', '3h') or '3h').strip().lower()
        if window not in ('3h', 'day', 'boot', 'all'):
            window = '3h'
        return await self.server.event_loop.run_in_thread(
            self._klippylog_read, window)

    def _klippylog_read(self, window):
        import datetime as _dt
        try:
            with open(self.log_path, 'r', errors='replace') as f:
                lines = f.read().split('\n')
        except OSError as e:
            return {'ok': False, 'reason': 'cannot read %s: %s'
                    % (self.log_path, e)}
        cutoff = None
        now = _dt.datetime.now()
        if window == '3h':
            cutoff = now - _dt.timedelta(hours=3)
        elif window == 'day':
            cutoff = now.replace(hour=0, minute=0, second=0,
                                 microsecond=0)
        elif window == 'boot':
            try:
                with open('/proc/uptime', 'r') as f:
                    up = float(f.read().split()[0])
                cutoff = now - _dt.timedelta(seconds=up)
            except Exception:                                   # noqa: BLE001
                cutoff = None                    # fall back to 'all'
        kept = []
        last_ts = None
        for ln in lines:
            ts = None
            if len(ln) > 19 and ln[4] == '-' and ln[7] == '-':
                try:
                    ts = _dt.datetime.strptime(ln[:19],
                                               '%Y-%m-%d %H:%M:%S')
                    last_ts = ts
                except ValueError:
                    ts = None
            eff = ts if ts is not None else last_ts
            if cutoff is not None:
                if eff is None and ln.strip():
                    continue                     # header junk before cut
                if eff is not None and eff < cutoff:
                    continue
            if ln.strip() or ts is not None:
                kept.append(ln)
        kept = kept[-4000:]
        header = ('# klippy.log window=%s (%s .. now) - exported by '
                  'r2_menu.py\n' % (window, cutoff.isoformat(' ')
                                    if cutoff else 'beginning'))
        return {'ok': True, 'window': window,
                'lines': len(kept),
                'text': header + '\n'.join(kept)}


def load_component(config):
    return R2MenuComponent(config)
