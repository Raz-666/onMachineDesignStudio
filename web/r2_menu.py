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
import argparse
import asyncio
import os
import re
import subprocess

MENU_PATH_DEFAULT = '~/klipper-e3-r2d2/web/menu_structure.json'
EXPORT_TOOL_DEFAULT = '~/klipper-e3-r2d2/tools/menu_json_export.py'
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
        self.tool = os.path.expanduser(
            config.get('export_tool', EXPORT_TOOL_DEFAULT))
        self.lock = asyncio.Lock()
        self.doc = None
        self.last_mtime = 0.0
        self._live_cache = None        # R204: 2.5 s printer-snapshot cache
        self._live_t = 0.0
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
        self.server.register_remote_method('r2_menu_refresh', None)
        self.server.add_log_rollback_handler(self._handle_shutdown)

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
            for k in list(sv):
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
        want = {o: None for o in objs if o in wanted}
        status = {}
        skipped = []
        try:
            status = dict(await apis.query_objects(want, default={}) or {})
        except Exception as e:                                   # noqa: BLE001
            for o in sorted(want):
                try:
                    one = await apis.query_objects({o: None}, default={}) or {}
                    if one.get(o) is not None:
                        status[o] = one[o]
                except Exception as e2:                          # noqa: BLE001
                    skipped.append('%s: %s' % (o, e2))
        status = {k: v for k, v in status.items() if v is not None}
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
            if not (os.path.isfile(self.tool)
                    and os.access(self.tool, os.X_OK)):
                pass           # not executable / not present - just reload
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

    def _handle_shutdown(self):
        pass


def load_component(config):
    return R2MenuComponent(config)
