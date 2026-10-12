# Web UI feasibility - the LCD menu as a website on the Klipper host

Analysis R132 (release .93). Question from the field: *is a web UI that looks
and behaves like the LCD menu feasible - hosted by the Klipper server itself,
no extra server, just one more site on Moonraker?*

**Verdict up front: yes, and it is cheap.** The menu tree is declarative config
(`menus/lcd_menues.cfg`), the actions are plain gcode macros, and Moonraker
exposes everything a browser needs over one WebSocket. The only correction to
the "no extra server" premise: **Moonraker itself stopped serving static files
in 2020** - the UI's bytes come from the *already-running* nginx (the one that
serves Mainsail), which is not an additional daemon but an additional site
block. On a MainsailOS/FluiddPi box that is literally one config file and one
folder.

---

## 1. The architecture that falls out of the existing design

```
Browser (phone/PC)                     Klipper host
+-------------------------------+     +--------------------------------------+
| static SPA (one folder, no    |     | nginx :80/:443                       |
| build step - vanilla HTML/JS) |<----|   /r2/      -> /var/www/r2ui (NEW)   |
|                               |     |   /         -> Mainsail (existing)   |
| WebSocket: JSON-RPC           |<----|   /websocket, /server/*, /printer/*  |
|  - printer.gcode.script       |     |        -> Moonraker :7125 (existing) |
|  - printer.objects.subscribe  |     +--------------------------------------+
|  - server.files.*             |     | Moonraker -> Klipper (unix socket)   |
+-------------------------------+     +--------------------------------------+
```

Nothing new runs as a daemon. The UI is *dumb*: it renders a tree and sends
the same macro strings the LCD sends.

### 1.1 The Moonraker API is sufficient (verified against the docs)

| UI need | Moonraker endpoint (WebSocket JSON-RPC) |
|---|---|
| Send `GEN_BRICKS ...`, `FIX_FILE WHAT=RETRACT`, dialog answers | `printer.gcode.script` `{"script": "..."}` |
| Live state (`_STATE.mode`, dialogs, `save_variables`) | `printer.objects.query` / `printer.objects.subscribe` on `gcode_macro _STATE`, `save_variables`, `print_stats`, `display_status` |
| Macro list + descriptions (fallback panel) | `printer.objects.list` + query |
| File list after a generator finished | `server.files.list` `{"root": "gcodes"}` |
| Know when a generated file appears | `server.files.list` subscription notifications (file_manager watches with inotify) |
| Progress / layer display | `printer.objects.subscribe` on `virtual_sdcard`, `print_stats` (the macros already emit `M117` + `display_status`) |
| Web-UI beep mirror (optional) | none - the browser plays the tune locally |

Key detail: `save_variables` is a queryable Klipper object - the whole
`brick_jobs` queue, `preview_file`, `sound_on`, profile flags ... arrive as
one JSON object, exactly what the LCD renders via Jinja in its `name:` lines.

### 1.2 One source of truth - compile the cfg, don't fork it

The decisive trick (and why this is days, not weeks): **generate the UI tree
from `menus/lcd_menues.cfg`** instead of hand-writing a second menu:

1. A small Python script (runs in the repo's toolchain, output committed)
   parses the `[menu ...]` sections:
   * `type: list` -> submenu page,
   * `type: command` + `gcode:` -> button that sends those lines verbatim,
   * `type: input` + `input_min/max/step` -> number stepper bound to the same
     `SAVE_VARIABLE`,
   * `enable:` lines translate 1:1 - they are Jinja over the same queryable
     objects (`{'gcode_macro _BRICKS' in printer}` becomes a key check in the
     JSON state),
   * `name:` templates (`{'%2d' % menu.input}`, `printer['save_variables']...`)
     render client-side from the subscribed state with the same expressions.
2. The generator also emits the 19-entry `_SOUND_LIB` tune table as JSON, so
   optional browser beeps use the *identical* melody data.

Menu changes in the cfg automatically appear in the web UI on the next build -
the R29 "names stay short" discipline even carries over to the phone.

### 1.3 What the web UI can do *better* than a 12864 LCD

* Real dialogs: the start-confirm flow (`AS_LEGACY` / `AS_SLICED` / cancel)
  becomes two big buttons driven by the subscribed `start_pending` state -
  the same release-the-dialog semantics fixed in R132 (rule vvvv).
* The bricks queue as a list with per-code delete (the LCD only shows a
  joined string).
* Generators with previews: `server.files.list` + metadata (height, layers,
  filament) right next to the CREATE button.
* No 60 s menu timeout, no four-line ceiling.

## 2. Hosting - the honest answer to "no extra server"

### 2.1 What Moonraker can and cannot do

* **Cannot:** serve the UI's files. Static file serving was removed from
  Moonraker in v0.05-alpha (April 2020, "Static files no longer served by the
  API server"); its HTTP server (port 7125) speaks API only. There is no
  config option to change that.
* **Can:** everything else - WebSocket, JSON-RPC, auth, file watching.

### 2.2 The recommended setup (no new daemon)

On MainsailOS / FluiddPi / any manual install that already fronts Moonraker
with nginx, the existing server block already contains the proxy lines every
Klipper frontend needs:

```nginx
location /websocket { proxy_pass http://apiserver/websocket; ... }
location ~ ^/(printer|api|access|machine|server)/ { proxy_pass http://apiserver$request_uri; ... }
```

The R2 UI needs exactly one addition:

```nginx
location /r2/ {
    alias /var/www/r2ui/;          # the generated SPA folder
    try_files $uri $uri/ /r2/index.html;
}
```

Result: `http://printer.local/r2/` - a second website on the same nginx that
already runs for Mainsail. Zero additional processes, zero additional ports,
WebSocket and API routes reused as-is. This is the practical reading of
"weitere Website auf dem Moonraker-Host".

### 2.3 Edge cases

| Case | Handling |
|---|---|
| Bare Klipper install, no nginx at all | `sudo apt install nginx` (one static server) or run the UI from any webspace - it only needs reachability of `ws://printer:7125/websocket` |
| HTTPS Mainsail (self-signed) | serve `/r2/` from the same vhost - no mixed content, `wss://` just works |
| Remote access (Obico, OctoEverywhere ...) | the tunnel proxies Moonraker; the UI works through it like Mainsail does |
| Opening the single HTML file via `file://` | works only when the browser permits a cross-origin WebSocket from a `null` origin - unreliable across browsers, **not** the supported path |
| Auth | same trust model as Mainsail: LAN-trusted or Moonraker API key; the UI sends the key as `X-Api-Key` once and stores it in `localStorage` |

## 3. Effort, risks, plan

| Step | Estimate | Notes |
|---|---|---|
| cfg -> JSON menu compiler | ~0.5 day | parser + expression shim for the ~12 `name:`/`enable:` patterns actually used |
| SPA shell (tree, buttons, steppers, state subscription) | ~1 day | vanilla JS, no framework, one file + the JSON |
| Dialogs + bricks queue view | ~0.5 day | the flows that justify the UI |
| nginx snippet + INSTALL section | ~0.1 day | documented in `INSTALL.md` |
| **Total** | **~2 days** | all of it offline-testable against a mock state JSON |

Risks / limits:

* **Long macros block the gcode thread** - unchanged from the LCD; the UI must
  not flood `printer.gcode.script` (the macros already `_PACE` themselves).
* **No file upload needed** - generators run host-side via the watcher; the UI
  only triggers and lists. Deliberately out of scope.
* **Menu syntax drift** - the compiler lives in the repo's test battery
  (`macro_render_test.py` grows a "web tree compiles" check), so a cfg change
  that breaks the UI fails CI, not the field.
* **Two-way state** - the UI never writes state directly; it always sends the
  same `SAVE_VARIABLE`-carrying macros the LCD uses. Single writer, no races.

## 4. Recommendation

Build it as described (compiler + static SPA + nginx location). It reuses the
entire existing macro surface, keeps one source of truth, needs no extra
server process, and gives headless / touch-screen / remote users the exact
LCD workflow - including the R132 auto-reload-after-fix flow, which is pure
macro state and therefore free in the web UI.

## Sources

- Moonraker dev changelog (static file serving removed, v0.05-alpha 2020):
  https://moonraker.readthedocs.io/en/stable/dev_changelog/
- Moonraker installation (nginx note, frontend serving):
  https://moonraker.readthedocs.io/en/latest/installation/
- Moonraker configuration (`[server]`, `[file_manager]`, ports):
  https://moonraker.readthedocs.io/en/latest/configuration/
- Typical nginx site config for a Klipper frontend (proxy locations):
  https://ballaswag.github.io/blog/understanding-a-typical-klipper-setup-klipper-moonraker-mainsail/fluidd-nginx-camera/
