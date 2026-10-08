# Running the R2 macro system on OTHER printers

Compatibility report & portability model (R103, status of release .80 / commit after `007523d`).
Scope: **cartesian and CoreXY FDM printers** with Klipper + Moonraker/Mainsail. Not in scope:
delta robots (round bed - the generators place rectangular plates), belt printers, resin.

The system was developed on a heavily modified Ender-3 (BTT SKR Mini E3 V3, BLTouch-class
probe, TMC2209 UART, 5 neopixels, direct drive). This document states honestly what ports
over unchanged, what needs ONE config section, and what is still hardcoded (with a fix plan).

---

## 1. The portability model (three layers)

| Layer | Where it lives | Portable? |
|---|---|---|
| **A. Dynamic** - read from YOUR printer.cfg at runtime | `[r2_postproc]` bed limits, `[extruder] nozzle_diameter`, `[probe] x/y_offset`, `printer.toolhead.axis_*`, `printer.configfile.settings` | yes - nothing to do |
| **B. Defaults** - variables with Ender-3 fallback values | plot bed/offsets/scale (save_variables, LCD *Tools > Plotter*), wipe area | works, but SET the values once |
| **C. Hardware** - sections that must exist in YOUR printer.cfg | `[neopixel]`, buzzer pin (`M300`), filament sensor, `[tmc2209 ...]` for gantry sync | optional per feature; system degrades gracefully |

The single most important line for any non-Ender-3 machine (layer A):

```ini
[r2_postproc]
bed_min_x: 0        # left edge of the PRINTABLE area (NOT the stepper range!)
bed_max_x: 220
bed_min_y: 0
bed_max_y: 220
```

This is the ONE truth for all generators (frame, labels, ties, angles, bridge, seal, litho,
range, resonance) AND the LCD park/purge corner math. `setup.sh` checks for it and can
append a template. The watcher prints a one-line hint to its journal when it is missing
and falls back to the Ender-3 default (0, -3, 220, 217).

**Important subtlety (by design, R92):** on the reference machine the stepper `position_max`
is deliberately LIFTED beyond the plate (X axis reaches past the bed so the probe can mesh
more of it). That is exactly why the system never uses axis limits for placement - it uses
the `[r2_postproc]` bed. Your lifted axes (if any) never distort generated plates.

## 2. What is already dynamic (verified in code)

| What | Source | Where used |
|---|---|---|
| Generator bed + margins | `[r2_postproc]` in printer.cfg → `_bed_limits()` (r2_postproc.py) | every generator call in the watcher (labels, ties, angles, litho, seal, frame, bridge, range, resonance) |
| Nozzle diameter (line widths, E/mm, hatch) | `[extruder] nozzle_diameter` → `_gen_nozzle()` | all generators; logs when it differs from 0.6 |
| Prime/purge line placement | bed corners from `[r2_postproc]` + `[probe] x_offset/y_offset` (08_print_start_stop.cfg `_PRIME_LINE`) | nozzle AND probe stay inside the bed with 5 mm margin; line runs right-to-left, Y only increases |
| Pause / filament-change park | computed at runtime (collision-aware, bed corners from `[r2_postproc]`, 09_pause_filament.cfg) | `variable_park_x/y` are CHOSEN values, not fixed |
| PRINT_END lift | `min(current Z + 15, axis_maximum.z - 2)` | clamped to any Z height |
| Purge/park Y clamps | `min(axis_maximum.y - 7, 228)` (08: two spots) | follows smaller axes |
| KAMP | auto-detection via printer objects (`_KAMP_Settings` present? override active? object data?) | mesh dispatch, purge dispatch, smart park - works without KAMP at all |
| Bed mesh area | your own `[bed_mesh]` / KAMP adaptive | never overridden by the macros (the beyond-bed X meshing on the reference machine lives in printer.cfg where it belongs) |
| Plotter area, pen offsets, scale, speeds | save_variables (`plot_bed_min_x` ... `plot_off_*`, `plot_scale_*`) - LCD *Tools > Plotter* | `PLT_FRAME` corners test draws the actual area; defaults are the reference machine's 5,5..239,233 |
| Resonance plates | bed via `_bed_limits()`, axes generic x/y | input shaper CSVs from `CALIBRATE_SHAPER`/`DUMP_RESONANCES` |
| Move speeds | Klipper clamps every move to `[printer] max_velocity/max_accel` | fast travel values degrade safely on slower machines |

LCD macros use Klipper's native config introspection
(`printer.configfile.settings.get('r2_postproc', {})`) - the same section, one truth,
no duplication.

## 3. Hardcoded spots found (the honest list)

| # | Where | What | Risk on other printers | Severity |
|---|---|---|---|---|
| 1 | 08_print_start_stop.cfg:1656 (`PRINT_END` part presentation) | `G0 X10 Y228` | **Y228 crashes** on machines with Y axis < ~232 mm | **must fix** |
| 2 | 12_maintenance.cfg:1170 (`TEMP_TOWER_GEN` end park) | `Y190` | out of bounds on beds < ~195 mm | should fix |
| 3 | 12_maintenance.cfg:1746 (`PLT_FRAME` end park) | `X5 Y190` | fine here (plot area 233) - should clamp to plot bed vars | should fix |
| 4 | 12_maintenance.cfg:1148/1420/1547 (cold pull / atomic pull) | `X15 Y10`, `X75` | near axis-min anchor - OK on cartesian/CoreXY, clamp advisable | minor |
| 5 | 12_maintenance.cfg `_NOZZLE_WIPE` | wipe pad anchored at `axis_minimum` + fixed 13x13 mm | works, but the pad position is NOT selectable (front-left assumed) | improvement |
| 6 | tools/r2-postproc.service | `User=pi`, `/home/pi` hardcoded | wrong user/paths on other installs | **fixed by setup.sh** (templates the unit) |
| 7 | 11_gantry_sync.cfg `SYNC_GANTRY` | parallel-wired dual-Z + `SET_TMC_CURRENT` (TMC UART) | Ender-3-class gantry only; CoreXY/independent-Z users have Z_TILT/QGL | by design, documented |
| 8 | megatest.py `BED` | fixed (0,-3,220,217) for the invariant checks | test tool only - should accept the bed as arg | minor |

## 4. Hardware-dependent components (layer C)

| Feature | Needs | Without it |
|---|---|---|
| LED effects (03_leds.cfg) | `klipper-led_effect` + `[neopixel printer_leds]` (+ optional `[neopixel nozzle_led]`) | Klipper refuses `[led_effect]` sections - comment them out or install the module (`setup.sh` can) |
| Sounds (02_sounds.cfg) | buzzer on a pin (`M300`) | silent, everything else works |
| Filament sensor (09_) | `[filament_switch_sensor]` | runout protection inactive |
| LCD menus | a display in Klipper + `menus/lcd_menues.cfg` include | Mainsail console commands work regardless (all GEN_* macros are console-callable with parameters) |

## 5. Kinematics verdict

- **Cartesian (bedslinger, Ender/Prusa-style):** full support - that is the home turf.
- **CoreXY:** full support. The macros only emit X/Y/Z moves, never kinematic assumptions;
  bed limits come from `[r2_postproc]`, speeds are clamped by Klipper. Skip `SYNC_GANTRY`
  (use Z_TILT_ADJUST/QGL). Input shaper resonance plates work (x/y generic).
- **Delta:** NOT recommended - generators and the plotter assume a rectangular bed.

## 6. Recommended hardening plan (R104 proposal - not yet applied)

1. **P1 - PRINT_END presentation position (#1):** clamp to `min(Y228, axis_maximum.y - 4)`
   and optionally read `present_x`/`present_y` from `[r2_postproc]` (defaults = today's values,
   so the reference machine does not change behavior).
2. **P1 - Y190 parks (#2, #3):** clamp to the plot bed variables (they describe the real
   travel area on the pen-plotter machines) / axis limits.
3. **P2 - wipe area (#5):** `wipe_x`/`wipe_y` (anchor override) in `[r2_postproc]`,
   default = axis-minimum corner (unchanged behavior).
4. **P2 - megatest (#8):** `--bed` argument, default from printer.cfg.
5. **P3 - cold-pull clamps (#4).**
6. All of it guarded by the existing test suites (1226/1226, golden 23/23, megatest 101/0).

## 7. Bring-up checklist for a new printer (fresh install)

1. Unzip the package into the config folder, run `update.sh` (file level: includes check).
2. Run `bash klipper-e3-r2d2/setup.sh` - environment wizard: Python, watcher service
   (templated unit), KAMP, LED effects, RAM hogs, swap tuning. `--check` = report only.
3. Set `[r2_postproc]` bed limits to your REAL printable area.
4. Check `[probe] x_offset/y_offset` are correct (the prime line safety depends on them).
5. *Tools > Plotter*: set plot bed + pen offsets, run the `PLT_FRAME` corners test.
6. `SYNC_GANTRY`: only for parallel-wired dual-Z - skip otherwise.
7. First print: small part, watch homing, purge line placement, end presentation.
8. Optional hardcore self-test: `python3 tools/megatest.py` (101 generator runs with
   invariant checks; exit 0 = ok).

## 8. GitHub / community readiness

- `setup.sh` gives a single interactive entry point for environment bring-up (fresh and
  update paths) - tested in a full simulation including KAMP installation.
- This file documents the portability contract; the hardening plan above is the road to
  "no Ender-3 coordinate left in a movement command".
- Still open before publishing: license file, screenshot assets, and the R104 hardening.
