# Running the R2 macro system on OTHER printers

Compatibility report & portability model (R103/R104, status of release .81;
R274 machine-model audit: every claim below that is testable offline is now
PROVEN by `tools/r274_compat_check.py` - synthetic foreign printers against
the config layer, the post-R217 generators and the macro math, see §9).
Scope: **cartesian and CoreXY FDM printers** with Klipper + Moonraker/Mainsail. Not in scope:
delta robots (round bed - the generators place rectangular plates), belt printers, resin.

The system was developed on a heavily modified Ender-3 (BTT SKR Mini E3 V3, BLTouch-class
probe, TMC2209 UART, 5 neopixels, direct drive). This document states honestly what ports
over unchanged, what needs ONE config section, and what is still hardcoded (with a fix plan).

---

## 1. The portability model (three layers)

| Layer | Where it lives | Portable? |
|---|---|---|
| **A. Dynamic** - read from YOUR printer.cfg at runtime | `[gcode_macro _R2_CONFIG]` variables, `[extruder] nozzle_diameter`, `[probe] x/y_offset`, `printer.toolhead.axis_*`, `printer.configfile.settings` | yes - nothing to do |
| **B. Defaults** - variables with Ender-3 fallback values | plot bed/offsets/scale (save_variables, LCD *Tools > Plotter*), wipe area | works, but SET the values once |
| **C. Hardware** - sections that must exist in YOUR printer.cfg | `[neopixel]`, buzzer pin (`M300`), filament sensor, `[tmc2209 ...]` for gantry sync | optional per feature; system degrades gracefully |

The single most important line for any non-Ender-3 machine (layer A):

```ini
[gcode_macro _R2_CONFIG]        # KAMP-style settings macro - R104.2
variable_bed_min_x: 0.0         # left edge of the PRINTABLE area (NOT the stepper range!)
variable_bed_max_x: 220.0
variable_bed_min_y: 0.0
variable_bed_max_y: 220.0
gcode:
    # config carrier only - never runs
```

⚠ A raw custom section (the pre-.82 `[r2_postproc]`) makes Klipper REFUSE to
boot — unknown config section, halt loop (field log .81). A settings macro is
the only valid carrier; `setup.sh` migrates legacy sections automatically.

This is the ONE truth for all generators (frame, labels, ties, angles, bridge, seal, litho,
range, resonance) AND the LCD park/purge corner math. `setup.sh` checks for it and can
add a template. The watcher prints a one-line hint to its journal when it is missing
and falls back to the Ender-3 default (0, -3, 220, 217).

**Important subtlety (by design, R92):** on the reference machine the stepper `position_max`
is deliberately LIFTED beyond the plate (X axis reaches past the bed so the probe can mesh
more of it). That is exactly why the system never uses axis limits for placement - it uses
the `_R2_CONFIG` bed. Your lifted axes (if any) never distort generated plates.

## 2. What is already dynamic (verified in code)

| What | Source | Where used |
|---|---|---|
| Generator bed + margins | `[gcode_macro _R2_CONFIG]` in printer.cfg → `_bed_limits()` (r2_postproc.py) | every generator call in the watcher (labels, ties, angles, litho, seal, frame, bridge, range, resonance) |
| Nozzle diameter (line widths, E/mm, hatch) | `[extruder] nozzle_diameter` → `_gen_nozzle()` | all generators; logs when it differs from 0.6 |
| Prime/purge line placement | bed corners from `_R2_CONFIG` + `[probe] x_offset/y_offset` (08_print_start_stop.cfg `_PRIME_LINE`) | nozzle AND probe stay inside the bed with 5 mm margin; line runs right-to-left, Y only increases |
| Pause / filament-change park | computed at runtime (collision-aware, bed corners from `_R2_CONFIG`, 09_pause_filament.cfg) | `variable_park_x/y` are CHOSEN values, not fixed |
| PRINT_END lift | `min(current Z + 15, axis_maximum.z - 2)` | clamped to any Z height |
| Purge/park Y clamps | `min(axis_maximum.y - 7, 228)` (08: two spots) | follows smaller axes |
| KAMP | auto-detection via printer objects (`_KAMP_Settings` present? override active? object data?) | mesh dispatch, purge dispatch, smart park - works without KAMP at all |
| Bed mesh area | your own `[bed_mesh]` / KAMP adaptive | never overridden by the macros (the beyond-bed X meshing on the reference machine lives in printer.cfg where it belongs) |
| Plotter area, pen offsets, scale, speeds | save_variables (`plot_bed_min_x` ... `plot_off_*`, `plot_scale_*`) - LCD *Tools > Plotter* | `PLT_FRAME` corners test draws the actual area; defaults are the reference machine's 5,5..239,233 |
| Resonance plates | bed via `_bed_limits()`, axes generic x/y | input shaper CSVs from `CALIBRATE_SHAPER`/`DUMP_RESONANCES` |
| Move speeds | Klipper clamps every move to `[printer] max_velocity/max_accel` | fast travel values degrade safely on slower machines |
| Casting molds (R270-R273) | `bed=` + `nozzle=` on every `make_mold` / `make_mold_blank` call (watcher + toolchain both pass the parsed values) | block centered on the bed, wall widths derive from `max(0.4, nozzle*1.08)`; a block that does not fit REFUSES with the mm it needs (measured on 180/250/300mm beds, r274 B1-B6) |
| Textures (R175-R266) + stencils (R267) | `bed=` on `apply_texture` / `make_stencil` | placement clamped to the bed (r274 C1-C2) |

LCD macros use Klipper's native config introspection
(`printer.configfile.settings.get('r2_postproc', {})`) - the same section, one truth,
no duplication.

## 3. Hardcoded spots found (the honest list)

Status after the R104 hardening (release .81) — items 1, 2, 3, 5, 6, 8 are FIXED:

| # | Where | What | Status (.81) |
|---|---|---|---|
| 1 | 08_print_start_stop.cfg `PRINT_END` part presentation | was fixed `G0 X10 Y228` | **FIXED (.81)** — clamped to the axes + `_R2_CONFIG` variable_present_x/y (defaults 10/228 = unchanged reference behavior) |
| 2 | 12_maintenance.cfg `TEMP_TOWER_GEN` / retract tower end park | was fixed `Y190` | **FIXED (.81)** — clamped to `axis_maximum.y - 4` |
| 3 | 12_maintenance.cfg `PLT_FRAME` end park | was fixed `X5 Y190` | **FIXED (.81)** — parks inside the plot-bed variables |
| 4 | 12_maintenance.cfg calibrator prime lines (`X15 Y10` → `X75`) | front-left anchor | OK as-is (fits any bed ≥ 80 mm; the towers themselves place from bed data) |
| 5 | 12_maintenance.cfg `_NOZZLE_WIPE` | pad anchored at axis minimum, fixed 13×13 mm | **FIXED (.81)** — _R2_CONFIG variable_wipe_x/y anchor (default = axis-minimum corner, clamped so the pad stays on the axes) |
| 6 | tools/r2-postproc.service | `User=pi`, `/home/pi` hardcoded | **FIXED (.80/setup.sh)** — setup.sh templates the unit to your user + paths |
| 7 | 11_gantry_sync.cfg `SYNC_GANTRY` | parallel-wired dual-Z + `SET_TMC_CURRENT` (TMC UART) | by design, documented — Ender-3-class gantry only; CoreXY/independent-Z users have Z_TILT/QGL |
| 8 | megatest.py `BED` | was fixed (0,-3,220,217) | **FIXED (.81)** — `--bed=x0,y0,x1,y1` or `--cfg=printer.cfg`; dimension-ValueErrors on a smaller bed count as SKIP (the generators correctly reject what does not fit — verified on 180×180 and a 10..200 bed: 101 runs, 0 FAIL) |

HOST_CHECK's swap verdict also got honest in .81: it now measures swap ACTIVITY
(vmstat si/so) — quietly parked pages after boot are OK (the .80 field log
showed 109 MB of cold swap on a perfectly healthy Pi flagged as „SWAPPING").

## 4. Hardware-dependent components (layer C)

| Feature | Needs | Without it |
|---|---|---|
| LED effects (03_leds.cfg) | `klipper-led_effect` + `[neopixel printer_leds]` (+ optional `[neopixel nozzle_led]`) | Klipper refuses `[led_effect]` sections - comment them out or install the module (`setup.sh` can) |
| LED areas (R108) | hardware profile `r2_hardware.cfg` (setup wizard generates + includes it) - `[neopixel]` OR `[dotstar]`, any section name, mainboard pin or EBB CAN split chain | defaults: 4 status + 0 bed + nozzle as last LED of `printer_leds` (the R2 reference layout - pre-R108 behaviour) |
| LED persistence from the LCD | `gcode_shell_command` extension (KIAUH) + `[gcode_shell_command R2_PERSIST]` (setup.sh writes it into r2_hardware.cfg when the module exists) | System > LED Setup edits apply to the running session only |
| Per-file profiles (R109) | `save_variables` (`file_profiles` dict, `gen_out`, `file_profiles_on`, `file_profiles_autosave`) - LCD *Pre-Print > Profiles* | plain variables.cfg keys, auto-migrated at boot; profile key = path under the gcodes root (any slicer) |
| Hardware profile (R108) | `r2_hardware.cfg` next to printer.cfg: build volume, probe offsets, clean/present positions, LED layout - the SECOND variables file (survives deleting variables.cfg) | Ender-3 reference defaults; `[gcode_macro _R2_CONFIG]` in printer.cfg keeps working (the wizard migrates it - old block only commented out) |
| Sounds (02_sounds.cfg) | buzzer on a pin (`M300`) | silent, everything else works |
| Filament sensor (09_) | `[filament_switch_sensor]` | runout protection inactive |
| LCD menus | a display in Klipper + `menus/lcd_menues.cfg` include | Mainsail console commands work regardless (all GEN_* macros are console-callable with parameters) |

## 5. Kinematics verdict

- **Cartesian (bedslinger, Ender/Prusa-style):** full support - that is the home turf.
- **CoreXY:** full support. The macros only emit X/Y/Z moves, never kinematic assumptions;
  bed limits come from `_R2_CONFIG`, speeds are clamped by Klipper. Skip `SYNC_GANTRY`
  (use Z_TILT_ADJUST/QGL). Input shaper resonance plates work (x/y generic).
- **Delta:** NOT recommended - generators and the plotter assume a rectangular bed.

## 6. Hardening plan

**R104/.82 - APPLIED:** P1 PRINT_END presentation clamp + `present_x/present_y`,
P1 Y190 calibrator parks + PLT_FRAME park, P2 wipe pad anchor (`wipe_x`/`wipe_y`),
P2 `megatest --bed/--cfg` with small-bed SKIP handling. All guarded by the test
suites (suite 1240/1240, golden 23/23, megatest 101/0 on three different beds).

Remaining (P3, cosmetic): calibrator prime-line X75 clamp on ultra-small beds.

## 7. Bring-up checklist for a new printer (fresh install)

1. Unzip the package into the config folder, run `update.sh` (file level: includes check).
2. Run `bash klipper-e3-r2d2/setup.sh` - environment wizard: Python, watcher service
   (templated unit), KAMP, LED effects, RAM hogs, swap tuning. `--check` = report only.
3. Set `[gcode_macro _R2_CONFIG]` bed variables to your REAL printable area.
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
- Still open before publishing: license file + screenshot assets (the R104 hardening is done).

## 9. R274 machine-model audit (offline, measured)

`tools/r274_compat_check.py` (J7) - 24 checks, synthetic foreign printers:

- **Config layer** (A1-A7): `_R2_CONFIG` bed values win; `r2_hardware.cfg`
  overrides `printer.cfg`; missing config falls back to the Ender-3 default
  WITH the one-line hint; insane values (min > max) refuse and fall back;
  the legacy `[r2_postproc]` section still triggers the HALTS-KLIPPER
  warning while its values are read as a courtesy; `nozzle_diameter` is
  parsed from `[extruder]`, clamped to 0.1..2.0, fallback 0.6.
- **Post-R217 generators** (B1-B6, C1-C2) - the R217 matrix predates them,
  so the audit closes the gap: `make_mold` and `make_mold_blank` on
  180/250/300mm beds keep EVERY emitted X/Y inside the bed (the I10 clamp
  proof); an oversized block REFUSES with the mm it needs; wall and brim
  E/mm scale with `max(0.4, nozzle*1.08)` (0.4 -> 0.8 measured 2.14x /
  2.00x) while the block placement does not move. HONEST caveat: the solid
  hatch snaps its line COUNT to the region width, so hatch E/mm adapts
  (measured 1.65x, not 2x) - correct behavior, not a bug. Textures and
  stencils clamp to the foreign bed the same way.
- **Macro math** (D1-D6): `_PRIME_LINE` rendered with Klipper's Jinja
  dialect against four synthetic machines (home 244x238 with -45/-10
  probe, a 300x300 CoreXY with +60/+10 probe, no probe, no `_R2_CONFIG`)
  - the prime line always lands in the probe-safe window AND the probe
  stays on the plate; PRINT_END's lift clamps to `axis_maximum.z - 2`
  (low-Z 180mm machine) and the presentation move clamps to small axes
  (150mm: Y 228 -> 146).
- **Docs parity** (E1-E2): this file and the MASTER-TODO carry the R274
  status.

NOT covered offline (needs real hardware / user decision): actual probe
z-offset quality, display type, audio path, host performance (J3/JJ4
decisions pending), the bring-up checklist of §7 on a real foreign
machine.
