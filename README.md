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
| **.104 (R135)** | **The menu restructure - one screen, one job.** Nothing was lost - an inventory test (tools/r135_menu_golden.txt, 1657 pre-restructure paths) proves every vanished path is a documented merge/rename. Pre-Print: **Offset X/Y/Z** at the very top (X/Y/Z plus fine rows with HALVED 0.05 mm steps, realtime MOVE=1), File info directly below - the fixes (RetFix ON/file, travel accel, flow cap + values) now a submenu of File - Profiles next. **Velocity** (ex-Motion): retraction + accel/vel/MCR/corner + Z-Hop (the duplicated top-level Z-Hop entries are gone). The four quick lists **Spd/Acc/PA/Flw per feat** absorb the old top-level Speeds/Accels/Flow menus and now lead with their GLOBALS (1st-layer speed, global accel + ON, global PA + smooth + File PA, global flow + ON) plus a Now row naming the active feature - identical in Live Tuning and Pre-Print. The Plotter sections (PEN FILE, pen speed, Pen Z, shifts) moved to the END of both panels and appear ONLY for plot files (_PREVIEW.plot or file_type plot). Klipper stock menus **OctoPrint / Temperature / Setup hidden** (enable {False} overrides - the documented menu.cfg merge; everything exists in the R2 menus), SD Card browser / Control / Tune stay. Bonus fixes: the dead duplicate temp-tower entry ([menu __maint __tt __go] twice) - "Start tower" is now __gen and reachable; a latent format bug in the new offset rows was caught by the render suite ('%.2f' not '.2f'). Docs: MANUAL ch. 3.4 + 14 menu tables rewritten, INSTALL updated. Battery: megatest 157/163/0, render 1621 (+10 R135), systemtest 221/0, stress/journeys/coverage/spell/audit re-run after the version bump, validator clean (stock-override whitelist). |
| **.103 (R134)** | **Plot-on-selection - the plotter becomes a choice, not a side effect**: uploading an image/text/PDF never converts anything anymore. The old flow auto-converted EVERY matching upload (`*.png`, `*.jpg.gcode`, `*.txt` ...) in the background - including every plain image uploaded as a litho/colorpic source (field log .101: `AxtBunny.png` grew an unrequested `AxtBunny.png.gcode` twin) - unpredictable background work on the Zero 2 W plus clutter in the file list. NEW flow: upload the PLAIN file (`photo.png`, `notes.txt`, `plan.pdf`, `drawing.svg` - the `.gcode` tail is dead), SELECT it in the file list (LCD or Mainsail) - `SDCARD_PRINT_FILE` detects the source extension, switches to plot mode and bumps `plot_nonce`; the watcher generates `00_Plot_<name>_V01.gcode` on demand like every other generator (one job at a time, never while printing, Maintenance > gen-out decides selected-for-start vs preview only for the 3D view). Pen mode stays unheated (no bed, no hotend, no purge), FILAMENT mode heats to the material preset - unchanged `_PLOT_START` semantics. A busy printer refuses the selection with a clear message instead of ever BASE-starting an image as g-code; an already-converted plot g-code selected again is re-selected, never regenerated; a raw `.gcode`-tailed upload (old habit) is left byte-identical with a rename hint. Litho/ColorPic outputs never collided (`00_Litho_*`/`00_ColorPic_*`) - but their SOURCE images stopped spawning plot twins. Docs (MANUAL ch. 5.3, INSTALL) updated; behavioral tests pin: no twin on any scan pass, hint not a rewrite, selection flow, busy refuse. Battery: megatest 157/163/0, render 1611, systemtest 221, stress 46596, journeys 1807, coverage 99, spell 1506/0, audit 0, validator clean. |
| **.102 (R133i)** | **Field log .101: the takeover guard itself was the bug - a one-shot must never kill**: the .101 takeover hook ran for EVERY invocation, so an SSH `--file-check` diagnostic killed the LIVE systemd watcher (PID 574, reported as 'stale duplicate' - which it was NOT) and every generator fell silent until the next boot: litho/ColorPic presses echoed their settings but nothing was ever built. The takeover now runs in `--watch` daemon mode ONLY; a manual `--watch` never kills the SUPERVISED systemd instance (cgroup check - the manual start exits politely, the supervised one wins); `--file-check` now reports the watcher state and warns LOUDLY when no watcher is running. Plus the runtime hole the same log exposed: pre-.98 zombies never write the lock, so a zombie starting AFTER the good watcher stayed invisible forever - NEW `_watch_duplicate_sweep()` scans /proc once a minute (no subprocess, cheap on the Zero 2 W) and stops ANY other r2_postproc process, any version, lock or not; a ROOT duplicate (root cron / rc.local relic) gets a loud how-to-stop respond (user pi cannot signal root). update.sh tries `sudo -n pkill` first. Fixed the display float artifact `3 x 0.6 = 1.7999999999999998mm` (in Jinja a trailing `\|round` binds to the right operand only - the whole product is now parenthesized and renders `1.8mm`). Behavioral tests pin both: a fake watcher + lock survives an ordinary `--file-check` untouched, and the thickness echo rounds. Battery: megatest 157/163/0, render 1605, systemtest 221, stress 46596, journeys 1807, coverage 93, spell 1502/0, audit 0, validator clean. |
| **.101 (R133h)** | **THE SHUTDOWN killer is dead - one watcher, ever (field log .100)**: a zombie pre-.98 watcher (started manually once, outside systemd) survived every update, ran parallel to the systemd watcher (doubling every console message) and pushed its stale kit-source list as a BARE unquoted value - `ast.literal_eval` SyntaxError = `Internal error on command:SAVE_VARIABLE` = printer shutdown (struck in idle; the same push mid-print would have killed the print). NOT a concurrency/rate problem: Klipper serializes all gcode in one mutex, a single malformed push suffices - micro-pauses would have changed nothing. Fixes: `_watch_lock_takeover()` (lock + loud takeover: RESPOND, SIGTERM, 5s, SIGKILL, atexit cleanup), update.sh pkills stray watchers before the systemd restart, a SAVE_VARIABLE pipeline lint (every rendered macro save, every menu save and every watcher push format goes through Klipper's EXACT shlex + literal_eval pipeline - a bare value can never ship again), and the gen_files push is now a real list (was a string; the LCD would have shown single-character slots). Verify after updating: `pgrep -af r2_postproc` shows exactly ONE process, then FIRMWARE_RESTART. Battery: megatest 157/163/0, render 1603, systemtest 221, stress 46596, journeys 1807, coverage 84, spell 1502/0, audit 0, validator clean. |
| **.100 (R133g)** | **THE lithophane inversion - found via the user's 3-tone test image**: every lithophane since R89 printed as a NEGATIVE (bright = thick, the white sky became the tallest step and the drawing became the base - 'a surface with hard valleys/mountains, not even remotely recognizable'). _litho_grid now outputs dark = 1.0 = thickest, which fixes STANDING, FLAT and ColorPic in one stroke. FLAT + ColorPic no longer mirror the image (the mirror is the STANDING backlit recipe) and print with the image top at the BACK - the picture reads correct from the printer front. Quantization now snaps to the NEAREST level (a clean 3-tone image keeps its gray even with the contrast boost on). Semantic coverage checks with a marker image pin polarity, orientation and the layer math. Battery: megatest 157/163/0, render 1601, systemtest 221, stress 46596, journeys 1807, coverage 84, spell 1502/0, audit 0, validator clean. |
| **.99 (R133f)** | **THE regeneration loop is dead** - the root cause of files reappearing after every reboot/update since .90: the four newer generator nonce channels (ColorPic, Bricks, Kit, Figures) and plot_cal were NEVER primed at watcher start, so every restart saw their stored nonces as 'new' and re-fired the user's old jobs (beeps, boot load, SD stress - and a full disk can kill SAVE_VARIABLE with an internal error). Every nonce channel is now primed AND a coverage check forbids ever adding an unprimed one. **Naming overhaul**: the Vers setting is retired - versions bump themselves (V01, V02, ...; regenerating NEVER overwrites, a deleted highest number is reused), file names use the FULL source name (no [:8] cut) plus generator info (Figure names carry SINGLE/PARTS). **Tools > Gen files**: every 00_ output on the display - press to select (start dialog catches it), Delete file = 2-press; only 00_ outputs are ever deletable. Fixed: the litho Delete-image slots were wired to LITHO_CREATE (creating instead of deleting!). Battery: megatest 157/163/0, render 1601, systemtest 221, stress 46596, journeys 1807, coverage 77, spell 0, audit 0, validator clean. |
| **.98 (R133e)** | **Kit source = YOUR selection + malformed-command fix**: the kit generator now takes the file SELECTED in the file list (the in-memory _PREVIEW card, same pattern as Texture) - the .97 pushed 5-newest-files list is GONE and so are the Job-1..5 menu entries; a missing selection is a clear error (Pick a file) instead of silently building from a guessed newest job. Mainsail keeps SRC=/INDEX=. Fixed: the queue-clear RESPOND had its closing quote misplaced after a semicolon, which the printer rejected as malformed command (field log .97). Journeys simulate the selection via the card. |
| **.97 (R133d)** | **Start-phase protection + no more zombie files**: the busy probe now includes the R2 _STATE mode - homing, heating, mesh and purge run while print_stats still says standby (the .96 field log shut down with 'Missed scheduling of next digital out event' while the bed heated and a litho job churned); a RUNNING job now holds cooperatively (2s ticks) as soon as the machine turns busy. Priming fix: nonce adoption always uses the FULL variable set (a watcher restart mid-print used to prime from the frozen subset -> the first idle pass re-fired every old generator job and recreated deleted files). NEW GEN_QUEUE_CANCEL (LCD Tools > Cancel job queue) drops pending jobs - the .95/.96 chaos had queued a pile that kept writing files after every printer restart (FIRMWARE_RESTART does not restart the watcher). |
| **.96 (R133c)** | **Host overload cured - one job at a time**: the field log caught ELEVEN litho threads running at once (every Create press spawned its own thread) until the Pi Zero drowned in swap and klipper starved (MCU 'Timer too close' while HOMING). Generator jobs now run through a single deduplicated queue (a duplicate press answers 'already running'), the worker requeues while a print runs (print always first), the scan pauses while a job works, micro-pauses yield the CPU in the litho/ColorPic hot loops, and the R75 niceness stays (klipper always wins). Also fixed: the kit success message crashed on a list (%d) since R125 - every finished kit LOOKED like an error; kit source picking plot files; stale kit AUTO menu texts; MOVERATE stamping moved from file selection (full-file scan froze the LCD) into the job worker. |
| **.95 (R133b)** | **'Timer too close' safety net**: FIX_FILE WHAT=SEGMENTS heals micro-segment floods in ANY selected file (<0.1mm hops merge, E preserved, worst rate into the file info as MOVERATE) - selection WARNS about hot files before they print (M117 + console); fixed _patch_info_kv (called by the flowcap fix since R111 but never defined - NameError was swallowed, MAXRATE never landed); LCD Pre-Print > File > Segment fix. |
| **.94 (R133)** | **Field-log round + true-proportion figures**: CAPS font rebuilt (5 corrupt glyphs made the printer loop over the 'O' and extrude blobs), the flowcap/travel fixes never ran (watcher blocks were missing), fix-reselect cleared itself while the fix was still queued, FIXED-mode label creation crashed (KeyError grown), MCU 'Timer too close' protection (no scan/generator jobs while printing, 12s poll, <0.1mm vertex merge = under the 400 moves/s serial budget), calib towers guard LAYER/WIDTH/LINES junk. Figures REBUILT at true proportions (feet 15.4x7.8, trapezoid torso 15.43->10.59, head O10.2x8.5, hip pivot + chamber, shoulder pins, turnable head, lying arms - two walls everywhere, never vase). Kits: AUTO picks the fine plate grid for small models + slope bricks at step edges. New: r142_field_coverage (every field bug pinned), r142_spell_lint, journeys 1801 checks. |
| **.93 (R132)** | **Bricks round 2 + hardcore stress test**: catalog 45 -> 76 codes (slopes, inverted slopes, arches, technic/axle, round: 9 LCD catalog groups), figures MODE=SINGLE (one fused piece) + COLORS/BRIM/COLORMODE, bricks COLORS/MODE/BRIM, print-by-layer or print-by-object for everything, centered layout as a general rule for ALL generators, fix-then-reload flow (RetractFix/FlowCap/Travel/Vol reload the file automatically - only Start needs confirming). 7 real bugs the stress test dug up (unbalanced Jinja in GEN_BRICKS, split TUNE_PID call, open RESPOND quote, missing M83 in bricks/figures/kit, trailing ;TYPE:Custom, kit without LAYER_MARK/APPLY_TYPE canonical). New tools/r140_stress.py (41k checks: render matrix, lint, regressions, Jinja balance). Analyses: sound/display portability, Web-UI on Moonraker, LCD menus on other displays (docs/). render 1601/1601, megatest 163 files, stress 41k, systemtest 221/0. |
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
