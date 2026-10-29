# r2_menu.py - Moonraker extension: the R2 menu tree as JSON (.135, R196)
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
import subprocess

MENU_PATH_DEFAULT = '~/klipper-e3-r2d2/web/menu_structure.json'
EXPORT_TOOL_DEFAULT = '~/klipper-e3-r2d2/tools/menu_json_export.py'


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
        self.server.register_endpoint(
            '/server/r2_menu/tree', ['GET'],
            self._handle_tree)
        self.server.register_endpoint(
            '/server/r2_menu/status', ['GET'],
            self._handle_status)
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
