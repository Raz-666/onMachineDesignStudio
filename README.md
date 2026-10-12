# Ender-3 "R2-D2" - complete Klipper macro system (ENGLISH)

For your modded Ender-3 (linear rails, dual Z in parallel, SKR Mini E3 V3.0,
5 neopixel LEDs, direct drive with BMG, BTT filament sensor, MicroProbe,
Creality 12864 LCD, Mainsail) - **with feedback about EVERYTHING**: R2-D2 beeper
sounds + LED effects (klipper-led_effect) + LCD + Mainsail console at once.

> This is the ENGLISH rewrite: all macros, menus, messages and comments use
> standard community naming. It replaces the earlier German version completely.

---

## What you get

| Feature | Where |
|---|---|
| **Asked before every print**: print as sliced OR with changes (material, temps 1st/following layers, retract, PA, accel, outer wall/support speed+accel, ironing flow/speed/temp, flow) | LCD "Start Print?" + "Pre-Print" / Mainsail `PRINT_AS_SLICED` / `PRINT_WITH_OVERRIDES` |
| **Old gcode files just work**: a state watcher detects prints that never call PRINT_START -> overrides + live tuning activate anyway; M104/M109/M140/M190/M204 are intercepted and redirected | automatic |
| **Everything LIVE during the print**: speed & accel separately for outer wall/inner wall/infill/support/ironing, flow, PA, retract, ironing (flow/temp/speed), fan scaling, temperatures, babystepping | LCD "Live Tuning" / Mainsail |
| **Dynamic print start**: reads the file's temps, loads the material's mesh or re-levels (adaptive!), PID deviation check based on the steady print temperature | automatic (08_) |
| **Material presets** (PLA/PETG/ABS/ASA/TPU): bed + hotend (layer 1 / from layer 2) + PA + flow + retraction - LCD-editable, saveable, loadable into the pre-print overrides | LCD "Pre-Print > Material" |
| **PA calibration (Orca style)**: one long line per PA value - speeds, accel, spacing, line length all on the LCD; prime line + skirt; calculator (best line or direct value -> PA saved) | LCD "Maintenance > PA Cal." |
| **Cold pull nozzle cleaning** + filament load/unload/change at the right temperatures (print temp while printing, min 200C in idle) | LCD "Maintenance > Filament" |
| **Input shaper calibration** (accelerometer): freq range, max smoothing, auto-save, raw-data dump - full guide in ISHAPER.md | LCD "Maintenance > Vibration Cal." |
| **Mesh management**: save with the bed temperature as name, live list of existing meshes, load + keep active for prints, unload to re-level next print | LCD "Maintenance > Bed Mesh" |
| **Z babystepping in 0.04 mm full steps** ("magic 4" - matches the Ender-3 Z motor step) | LCD "Live Tuning" + probe calibration |
| **Mesh persistence is YOUR choice**: default session-only (no SAVE_CONFIG after prints) - toggle "Save after print" to automate | LCD "Bed Mesh" menus |
| **Safe pause**: lifts only up to Z-max, park corner far away from the objects (object data!), anti-ooze retract, sensor muted, idle timeout infinite; **quick pause NOW** or **gentle pause at next layer / layer N** | `PAUSE` / `QUICK_PAUSE` / `PAUSE_NEXT_LAYER` / `PAUSE_AT_LAYER` |
| **Filament change without abort** (M600, multi-color): park, unload, purge, continue | `CHANGE_FILAMENT` / `M600` |
| **Filament runout**: R2 ALARM (red strobe + siren), safe pause, no wasted filament | automatic |
| **Cancel protection**: first press pauses safely, second press confirms, RESUME disarms - a mis-press can never abort a print | `CANCEL_PRINT` |
| **Skip single objects**: failed part? Exclude it right at the display and save the rest of the print (2-press confirmation, last-object protection, works while paused too) | LCD "Live Tuning > Objects" / `SKIP_OBJECT` / `SKIP_CURRENT_OBJECT` / `SHOW_OBJECTS` |
| **Dual-Z gantry sync** by gently bumping the top stop (reduced current) - manual, after boot or before prints | `SYNC_GANTRY` |
| **Maintenance/calibration**: PID (hotend WITH fan!), bed mesh, bed screws (SCREWS_TILT), probe offset, extruder calibration, retract test, self test | LCD "Maintenance" |
| **System on the LCD**: FW restart, host restart, shutdown, save config (each double-press) | LCD "System" |
| **KAMP compatible**: detects installed KAMP automatically - adaptive mesh via KAMP, LINE/VORON purge, optional Smart Park (each toggleable, fallback to native ADAPTIVE / own prime line) | LCD "Maintenance > KAMP" |
| **Old files fully automatic**: pause at start -> bed to temp -> mesh -> prime line -> continue; falling temps in the file are detected as 'layer 2' | LCD Pre-Print > Bed Mesh > 'Level old files' |
| **Power off from the LCD**: heaters safe + Pi shutdown (needs gcode-shell-command, 2-press) | `SYS_SHUTDOWN` |
| **Manual PID tuning**: hotend (WITH part fan) + bed at any temperature, anytime - no material binding, no automatic tuning | LCD Maintenance > PID Tuning / `TUNE_PID` |
| **Boot self-check**: console confirms `Macro system OK: all modules loaded`; a missing include OR an outdated file copy is reported loudly with the exact filename | `_CHECK_INSTALL` |
| **R2-D2**: 19 sounds + 12 LED effects woven into every flow; LEDs capped at 50% brightness | automatic |

---

## Files

```
klipper-e3-r2d2/
├── printer.cfg.example         reference config (SKR Mini E3 V3.0 pins) + include list
├── macros/
│   ├── 01_state.cfg            persistent + volatile state, defaults, STATE WATCHER
│   ├── 02_sounds.cfg           M300 (official Klipper sample) + R2-D2 sound library
│   ├── 03_leds.cfg             LED effects (led_effect) + SET_LED_STATE
│   ├── 04_notify.cfg           NOTIFY = LCD+Mainsail+LED+sound / SHOW_STATUS
│   ├── 05_materials.cfg        material presets + SET_MATERIAL
│   ├── 06_temp_controls.cfg    M104/M109/M140/M190/M106/M204 interception + LAYER_MARK
│   ├── 07_start_confirm.cfg    start dialog poller + override setters/toggles
│   ├── 08_print_start_stop.cfg PRINT_START/PRINT_END, mesh+PID decisions, prime line
│   ├── 09_pause_filament.cfg   PAUSE/PARK/RESUME/CANCEL/M600/runout
│   ├── 10_live_tuning.cfg      APPLY_TYPE + all live SET_* controllers
│   ├── 11_gantry_sync.cfg      dual-Z synchronization
│   ├── 12_maintenance.cfg      PID/mesh/screws/offsets/extruder/self test
│   ├── 13_system.cfg           restarts/shutdown/info
│   ├── 14_kamp.cfg             KAMP compatibility (mesh/purge/smart park dispatch)
│   └── 15_objects.cfg          skip single objects (SKIP_OBJECT, 2-press confirm)
├── menus/lcd_menues.cfg        the complete English LCD menu tree (12864)
├── slicer/
│   ├── ORCA.md / CURA.md       step-by-step slicer setup
│   ├── orca_klipper_features.py    Orca/Prusa post-processing (APPLY_TYPE)
│   └── cura_KlipperFeatureTypes.py Cura script (APPLY_TYPE+LAYER_MARK+object box)
└── tools/
    ├── config_validator.py     validates all templates/variables (python3 tools/config_validator.py)
    └── macro_render_test.py    30+ logic tests with a mocked printer
```

See **INSTALL.md** for setup in ~10 minutes and **MANUAL.md** for the complete
operating manual (every LCD item, every macro, every automatic event explained). (including migration from the old
German version!).

---

## The most important behaviors (by design)

1. **PID tuning is manual**: Maintenance > PID Tuning, any temperature, anytime
   (hotend with part fan, then SAVE_CONFIG - Klipper restarts once). No automatic
   tuning in the print start anymore.
2. **ONE bed mesh profile `r2`**: re-measured every print by default - adaptive
   (KAMP) when the file has object data. "Re-mesh every: AUTO" instead loads the
   saved r2 mesh. Materials no longer carry meshes.
3. **Old files without markers**: the setters apply the speed factor IMMEDIATELY
   via M220 when no feature type is known - you always get instant feedback.
   With the post-processing script the change is applied per feature boundary.
4. **Live retract** requires firmware retraction (Orca checkbox / Cura
   experimental) - otherwise the retract override only applies at print start.
5. **"PRINT_AS_SLICED" = truly 1:1**: this decision bypasses ALL overrides for
   exactly this print (including the M104/M109 interceptors). "PRINT_WITH_OVERRIDES"
   applies overrides + material preset + the matching mesh.
6. **Mainsail = LCD**: every menu action is a macro with a speaking English name
   and description -> identical in Mainsail. The start dialog also accepts
   Mainsail's resume button as "print as sliced".
7. **KAMP**: support detects automatically what is installed (setup: INSTALL.md
   section 3b). Mesh results are additionally saved as material profiles - the
   material logic survives KAMP.
8. **LEDs at max 50%**: all colors are capped at <= 0.5. Please keep new effects
   that way, too (protects the board, as requested).
9. **Comments & braces in macros** (important for your own edits!): Klipper cuts
   every line at the first `#` - comments always on their OWN line, never
   `{# ... #}` inline. Expressions use single braces `{...}` - `{{...}}` is
   invalid in Klipper. Booleans are Python style `True`/`False` (never `true`).
   `tools/config_validator.py` checks all of this.

## Safety notes

- Stay and watch the first `SYNC_GANTRY` run (documented in 11_gantry_sync.cfg).
- MicroProbe `x_offset/y_offset/z_offset` and the `[screws_tilt_adjust]` positions
  must be adapted once to your setup (marked ADJUST).
- Test the runout once: pull the filament out of the sensor during a print ->
  it must alarm + park safely (never cancel!).

## Latest additions

| Version | Highlights |
|---|---|
| **.92 (R131)** | **Documentation overhaul**: manual + PDF brought up to date - stale passages replaced (litho FLAT step print, frame snap-in closure, also the printer-side LCD texts), four new detailed generator chapters (bricks, brick kits, figures, ColorPic), menu reference / cheat sheet / macro index extended. render 1595/1595. |
| **.91 (R130)** | **HOTFIX**: .90 boot blocker - COLORPIC_CREATE used the non-existent Jinja filter `endswith` (since .82, only reached the printer with .90). Fixed with slicing; both the template gate (AST walk over all 3663 boot templates) and the config validator now catch unknown filter/test names statically. render 1595/1595. |
| **.90 (R129)** | **Bricks, kits, figures + the field-log round**: building bricks with the exact system geometry (45-part catalog), the kit generator (a sliced file becomes a stylized kit - support/brim never flow in), 5-part figures (100% = original size and system-true), the lithophane FLAT mode rebuilt as a clean STEP print (the wavy-relief field bug), frame backplate snap-in + photo-opening play, doubled label spacing, a purge tower with every filament change and a full-system release gate (tools/systemtest.py - every generator, every invariant). |
| **.55 (R71)** | **Range extrusion fixed + visible character editor**: range excerpts printed almost dry — the brim reset absolute E to the segment value every line and floor/top copies started at E≈0 without a `G92 E0` between blocks (huge phantom retracts ground the filament). Now: brim E accumulates, every block gets its own G92 E0 (M82 only), brim prints before the floor layers. The LCD character pickers became **visible scroll lists** (one entry per character, click inserts and advances; umlauts show LCD-safe aliases AE/OE/UE/ss/deg, the printed text keeps the real glyphs). |
| **.54 (R70)** | **Field-log fixes**: (1) `SAVE_DEFAULT_PRESET` never worked in the field — the preset dict's spaces broke Klipper's shlex ("Malformed command"); now saved in the escaped form as a real dict. (2) AS LEGACY takeover could cold-extrude ("Extrude below minimum temp" — the file's own prime lines run before the pause engages); _LEGACY_PREP now waits for the hotend target BEFORE pausing and the M109 preheat cap floors at min_extrude_temp+5. (3) Layer-range excerpts keep the source's EXCLUDE_OBJECT_DEFINE blocks, so KAMP meshes adaptively instead of falling back to a full-bed mesh. |
| **.53 (R69)** | **HOTFIX**: `SAVE_VARIABLE` could SHUT DOWN the printer — Klipper strips the quotes (POSIX shlex) and only catches ValueError, so any string with a space, an apostrophe, an empty value or the label queue's pipes raised SyntaxError = "Internal error on command" = shutdown. All R63/R64 string saves (label text/queue, plot-name editor, reso/shaper/plot-file stores, 4 watcher pushes) moved to the escaped quote form + quote/backslash validation + an `_sv_line` builder in the watcher. New test gate replays Klipper's exact parser over every cfg line and sweeps the whole charset through the label editor. Also removed `;` from the charset (Klipper cuts every command line at the first `;` — it could never be saved). |
| **.52 (R68)** | **HOTFIX**: the watcher crashed on 5 foreign files with `ValueError: could not convert string to float: '-'` — the G0/G1 parameter regex accepted digit-less tokens, so hyphenated names in trailing comments (`; Felge-V-035`) or bare `E-` tokens killed the whole processing run (files stayed untagged forever). Fixed: comments stripped before parsing, regex requires a digit, per-token guard; phantom params from comment text (`; Ender-3` → `R=-3`) gone too. Affected files are picked up automatically on the next service start. |
| **.51 (R67)** | **HOTFIX**: 2nd boot blocker from .47 — the label job-queue menu name used the non-existent Jinja filter `\|string.split` → "Internal error during connect" right after the `#` fix surfaced. Fixed with the proven `.split()` pattern; new test gate compiles ALL ~1565 boot-compiled templates (macro gcode + menu name/enable/gcode) and renders every menu template — this error class can never ship again. |
| **.50 (R66)** | **Update via browser, one command**: upload the ZIP in Mainsail's config folder (where printer.cfg lives, next to `klipper-e3-r2d2`) and run `bash ~/printer_data/config/klipper-e3-r2d2/update.sh` — it unpacks the newest uploaded ZIP over the old folder, checks everything and restarts (python3 fallback if `unzip` is missing, downgrade guard). |
| **.49 (R65)** | **HOTFIX**: `#` in `variable_charset` halts Klipper at boot (config comment strip) — charset fixed, `#` still pickable on the LCD (last entry), validator now emulates Klipper's strip + literal_eval and scans all cfg lines for `#` inside quotes. |
| **.48 (R64)** | **Resonance diagram**: the shaper CSVs become a printed (or pen-plotted) plate — PSD curve, all 5 shaper curves, shaper table with the winner boxed; pick it in `Vibration Cal. > Apply result` (frequency from the table, live + boot override, faithful port of Klipper's fit math). **Bridging test**: two towers diagonally + a short span (10–50 %) clearly below on its own lower tower, everything live-tunable. **Plotter**: text files (`PLOT_TEXT`) + status report (`PLOT_STATUS`) on one auto-fitted page, dark writing boards auto-inverted (border heuristic), start overrides + live plotter menu. **Simplified update** (`update.sh`, no new includes since .47). |
| **.47 (R63)** | Label generator (golden-ratio plates, 3 fonts, holes, 2 colors, purge tower), guarded Save config, config review. |

## License

GPL-3.0-or-later — see [LICENSE](LICENSE). Built field-log driven and test
gated: [DEVELOPMENT.md](DEVELOPMENT.md) tells the story,
[COMPATIBILITY.md](COMPATIBILITY.md) what it takes to run on your printer.

[![tests](https://github.com/Raz-666/klipper-e3-r2d2/actions/workflows/tests.yml/badge.svg)](https://github.com/Raz-666/klipper-e3-r2d2/actions/workflows/tests.yml)
